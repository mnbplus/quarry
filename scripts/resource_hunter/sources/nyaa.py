"""Nyaa.si anime/general torrent source adapter (RSS)."""
from __future__ import annotations
import urllib.parse
from xml.etree import ElementTree
from .base import HTTPClient, SourceAdapter, TRACKERS, _clean_magnet
from ..common import extract_share_id, normalize_title, parse_quality_tags, quality_display_from_tags
from ..models import SearchIntent, SearchResult

_NS = "{https://nyaa.si/xmlns/nyaa}"


class NyaaSource(SourceAdapter):
    name = "nyaa"
    channel = "torrent"
    priority = 1

    def search(self, query: str, intent: SearchIntent, limit: int, page: int, http_client: HTTPClient) -> list[SearchResult]:
        category = "1_2" if intent.kind == "anime" else "0_0"
        url = f"https://nyaa.si/?f=0&c={category}&q={urllib.parse.quote(query)}&page=rss"
        payload = http_client.get_text(url)
        root = ElementTree.fromstring(payload)
        results: list[SearchResult] = []
        for item in root.findall("./channel/item")[: max(limit * 3, 12)]:
            title = normalize_title(item.findtext("title", ""))
            if not title:
                continue

            # Nyaa RSS provides infoHash but NOT magnetUri — construct magnet from hash
            magnet = item.findtext(f"{_NS}magnetUri", "")
            info_hash = ""
            if magnet:
                info_hash = extract_share_id(magnet, provider_hint="magnet")
            else:
                info_hash = item.findtext(f"{_NS}infoHash", "")
                if info_hash:
                    magnet = f"magnet:?xt=urn:btih:{info_hash}&dn={urllib.parse.quote(title)}{TRACKERS}"

            if not magnet:
                continue

            seeders = int(item.findtext(f"{_NS}seeders", "0"))
            quality_tags = parse_quality_tags(title)
            results.append(
                SearchResult(
                    channel="torrent", normalized_channel="torrent",
                    source=self.name, upstream_source=self.name, provider="magnet",
                    title=title, link_or_magnet=_clean_magnet(magnet),
                    share_id_or_info_hash=info_hash,
                    size=item.findtext(f"{_NS}size", ""),
                    seeders=seeders,
                    quality=quality_display_from_tags(quality_tags), quality_tags=quality_tags,
                    raw={"title": title, "seeders": seeders},
                )
            )
        return results
