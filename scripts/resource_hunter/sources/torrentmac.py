"""TorrentMac native search adapter for Mac software/games."""
from __future__ import annotations
import re
import urllib.parse
import concurrent.futures
from .base import HTTPClient, SourceAdapter
from ..common import normalize_title, parse_quality_tags, quality_display_from_tags
from ..models import SearchIntent, SearchResult

_ARTICLE_SPLIT_RE = re.compile(r'<article id="post-\d+"')
_TITLE_RE = re.compile(r'<h2 class="post-title">\s*<a href="([^"]+)"[^>]*>\s*(.*?)\s*</a>', re.IGNORECASE | re.DOTALL)
_DATE_RE = re.compile(r'<time datetime="([^"]+)">', re.IGNORECASE)
_TORRENT_LINK_RE = re.compile(r'href="([^"]+?\.torrent)"', re.IGNORECASE)


class TorrentMacSource(SourceAdapter):
    name = "torrentmac"
    channel = "torrent"
    priority = 3

    def _fetch_torrent_link(self, url: str, http_client: HTTPClient) -> str | None:
        try:
            html = http_client.get_text(url, timeout=5)
            match = _TORRENT_LINK_RE.search(html)
            if match:
                return match.group(1)
        except Exception:
            pass
        return None

    def search(self, query: str, intent: SearchIntent, limit: int, page: int, http_client: HTTPClient) -> list[SearchResult]:
        # TorrentMac is strictly a software/games site for Mac
        if intent.kind not in ("software", "general", "game"):
            return []

        # Pagination starts at 1, handled by path `/page/N/`
        query_encoded = urllib.parse.quote_plus(query)
        if page > 1:
            url = f"https://www.torrentmac.net/page/{page}/?s={query_encoded}"
        else:
            url = f"https://www.torrentmac.net/?s={query_encoded}"
            
        payload = http_client.get_text(url)

        # Pre-parse basic info from the list page
        items = []
        blocks = _ARTICLE_SPLIT_RE.split(payload)
        for block in blocks[1:]:
            title_match = _TITLE_RE.search(block)
            if not title_match:
                continue
                
            detail_url = title_match.group(1)
            raw_title = title_match.group(2).strip()
            # Clean up HTML entities in title
            raw_title = raw_title.replace("&#8211;", "-").replace("&#8217;", "'")
            title = normalize_title(raw_title)
            
            date_match = _DATE_RE.search(block)
            date_str = date_match.group(1).strip() if date_match else ""
            
            items.append({
                "title": title,
                "url": detail_url,
                "date": date_str
            })
            
            if len(items) >= limit:
                break

        if not items:
            return []

        # Concurrently fetch detail pages to get .torrent links
        results: list[SearchResult] = []
        with concurrent.futures.ThreadPoolExecutor(max_workers=len(items)) as executor:
            future_to_item = {
                executor.submit(self._fetch_torrent_link, item["url"], http_client): item
                for item in items
            }
            
            for future in concurrent.futures.as_completed(future_to_item):
                item = future_to_item[future]
                torrent_url = future.result()
                
                # If we couldn't extract the direct torrent link, fallback to the detail page URL 
                # but mark provider as "torrentmac" so intelligent agents know it's a landing page
                final_link = torrent_url if torrent_url else item["url"]
                provider = "torrent" if torrent_url else "torrentmac"
                
                quality_tags = parse_quality_tags(item["title"])
                
                # TorrentMac doesn't expose seeders/leechers or size easily without full scraping
                # We use default 1 seeder to indicate it's active
                results.append(
                    SearchResult(
                        channel="torrent", normalized_channel="torrent",
                        source=self.name, upstream_source=self.name, provider=provider,
                        title=item["title"], link_or_magnet=final_link,
                        share_id_or_info_hash="",
                        size="", seeders=1,
                        quality=quality_display_from_tags(quality_tags), quality_tags=quality_tags,
                        raw={"title": item["title"], "date": item["date"]},
                    )
                )

        # Sort results to maintain original order since as_completed scrambles it
        # We can sort by the index in the original items list
        item_indices = {item["url"]: idx for idx, item in enumerate(items)}
        results.sort(key=lambda r: item_indices.get(r.raw.get("url", ""), 0))
        
        return results[:limit]
