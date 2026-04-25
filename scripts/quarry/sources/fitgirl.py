"""FitGirl Repacks search source adapter (RSS)."""
from __future__ import annotations
import re
import urllib.parse
from xml.etree import ElementTree
from .base import HTTPClient, SourceAdapter, _clean_magnet
from ..common import extract_share_id, normalize_title, parse_quality_tags, quality_display_from_tags
from ..models import SearchIntent, SearchResult

_MAGNET_RE = re.compile(r'href="(magnet:\?xt=urn:btih:[^"]+)"', re.IGNORECASE)


class FitGirlSource(SourceAdapter):
    name = "fitgirl"
    channel = "torrent"
    priority = 3

    def search(self, query: str, intent: SearchIntent, limit: int, page: int, http_client: HTTPClient) -> list[SearchResult]:
        if page > 1:
            return []  # RSS search usually doesn't paginate well with this basic URL structure
            
        url = f"https://fitgirl-repacks.site/feed/?s={urllib.parse.quote(query)}"
        payload = http_client.get_text(url)
        
        try:
            root = ElementTree.fromstring(payload)
        except ElementTree.ParseError:
            return []

        results: list[SearchResult] = []
        for item in root.findall("./channel/item")[: max(limit * 3, 10)]:
            title = normalize_title(item.findtext("title", ""))
            if not title:
                continue

            # Skip informational posts
            if "upcoming repacks" in title.lower() or "updates digest" in title.lower():
                continue

            content = item.findtext("{http://purl.org/rss/1.0/modules/content/}encoded", "")
            if not content:
                continue

            magnet_match = _MAGNET_RE.search(content)
            magnet = magnet_match.group(1) if magnet_match else ""
            if not magnet:
                continue

            info_hash = extract_share_id(magnet, provider_hint="magnet")
            quality_tags = parse_quality_tags(title)

            results.append(
                SearchResult(
                    channel="torrent", normalized_channel="torrent",
                    source=self.name, upstream_source=self.name, provider="magnet",
                    title=title, link_or_magnet=_clean_magnet(magnet),
                    share_id_or_info_hash=info_hash,
                    quality=quality_display_from_tags(quality_tags), quality_tags=quality_tags,
                    raw={"title": title, "category": item.findtext("category", "Game")},
                )
            )
        return results
