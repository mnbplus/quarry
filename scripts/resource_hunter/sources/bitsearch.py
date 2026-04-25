"""Bitsearch (formerly SolidTorrents) native search adapter."""
from __future__ import annotations
import html
import re
import urllib.parse
from .base import HTTPClient, SourceAdapter, _clean_magnet
from ..common import extract_share_id, normalize_title, parse_quality_tags, quality_display_from_tags
from ..models import SearchIntent, SearchResult

# We split by the result block container to avoid regex bleeding
_BLOCK_SPLIT_RE = re.compile(r'<div class="bg-white rounded-lg shadow-sm border border-gray-200 p-6')
_TITLE_RE = re.compile(r'<h3 class="text-base[^"]*">\s*<a href="/torrent/[^"]+"[^>]*>\s*(.*?)\s*</a>', re.IGNORECASE | re.DOTALL)
_SIZE_RE = re.compile(r'<i class="fas fa-download"></i>\s*<span>([^<]+)</span>', re.IGNORECASE)
_DATE_RE = re.compile(r'<i class="fas fa-calendar"></i>\s*<span>([^<]+)</span>', re.IGNORECASE)
_SEEDERS_RE = re.compile(r'<i class="fas fa-arrow-up"></i>\s*<span class="font-medium">(\d+)</span>', re.IGNORECASE)
_MAGNET_RE = re.compile(r'href="(magnet:\?[^"]+)"', re.IGNORECASE)


class BitsearchSource(SourceAdapter):
    name = "bitsearch"
    channel = "torrent"
    priority = 2

    def search(self, query: str, intent: SearchIntent, limit: int, page: int, http_client: HTTPClient) -> list[SearchResult]:
        # Bitsearch pagination starts at 1
        url = f"https://bitsearch.to/search?q={urllib.parse.quote(query)}&page={page}"
        payload = http_client.get_text(url)

        results: list[SearchResult] = []
        blocks = _BLOCK_SPLIT_RE.split(payload)
        
        # Skip the first split as it's the header
        for block in blocks[1:]:
            title_match = _TITLE_RE.search(block)
            if not title_match:
                continue
            
            title = normalize_title(title_match.group(1).strip())
            
            # The HTML contains encoded characters like &#x3D; for =
            magnet_match = _MAGNET_RE.search(block)
            if not magnet_match:
                continue
                
            raw_magnet = html.unescape(magnet_match.group(1))
            info_hash = extract_share_id(raw_magnet, provider_hint="magnet")
            if not info_hash:
                continue

            size_match = _SIZE_RE.search(block)
            size_str = size_match.group(1).strip() if size_match else ""
            
            date_match = _DATE_RE.search(block)
            date_str = date_match.group(1).strip() if date_match else ""

            seeders_match = _SEEDERS_RE.search(block)
            seeders = int(seeders_match.group(1)) if seeders_match else 0

            quality_tags = parse_quality_tags(title)

            results.append(
                SearchResult(
                    channel="torrent", normalized_channel="torrent",
                    source=self.name, upstream_source=self.name, provider="magnet",
                    title=title, link_or_magnet=_clean_magnet(raw_magnet),
                    share_id_or_info_hash=info_hash,
                    size=size_str, seeders=seeders,
                    quality=quality_display_from_tags(quality_tags), quality_tags=quality_tags,
                    raw={"title": title, "seeders": seeders, "date": date_str},
                )
            )

            if len(results) >= limit:
                break

        return results
