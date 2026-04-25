"""EZTV TV torrent source adapter."""
from __future__ import annotations
import urllib.parse
from .base import HTTPClient, SourceAdapter, _format_size, _make_magnet
from ..common import extract_share_id, normalize_title, parse_quality_tags, quality_display_from_tags
from ..models import SearchIntent, SearchResult


class EZTVSource(SourceAdapter):
    name = "eztv"
    channel = "torrent"
    priority = 1

    def search(self, query: str, intent: SearchIntent, limit: int, page: int, http_client: HTTPClient) -> list[SearchResult]:
        url = "https://eztv.re/api/get-torrents?" + urllib.parse.urlencode(
            {"imdb_id": 0, "limit": max(limit * 3, 20), "page": page, "keywords": query}
        )
        payload = http_client.get_json(url)
        if not isinstance(payload, dict):
            return []
        items = payload.get("torrents") or []
        results: list[SearchResult] = []
        for item in items[: max(limit * 3, 12)]:
            title = normalize_title(item.get("title", ""))
            magnet = item.get("magnet_url") or ""
            info_hash = (item.get("hash") or "").lower()
            if not magnet and info_hash:
                magnet = _make_magnet(info_hash, title)
            if not title or not magnet:
                continue
            quality_tags = parse_quality_tags(title)
            results.append(
                SearchResult(
                    channel="torrent", normalized_channel="torrent",
                    source=self.name, upstream_source=self.name, provider="magnet",
                    title=title, link_or_magnet=magnet,
                    share_id_or_info_hash=info_hash or extract_share_id(magnet, "magnet"),
                    size=_format_size(item.get("size_bytes", 0)),
                    seeders=int(item.get("seeds", 0)),
                    quality=quality_display_from_tags(quality_tags), quality_tags=quality_tags,
                    raw=item,
                )
            )
        return results
