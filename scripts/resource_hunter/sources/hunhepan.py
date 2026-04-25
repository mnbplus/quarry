"""Hunhepan pan search source adapter."""
from __future__ import annotations
import os
import urllib.parse
from .base import HTTPClient, SourceAdapter, _flatten_pan_payload
from ..models import SearchIntent, SearchResult


class HunhepanSource(SourceAdapter):
    name = "hunhepan"
    channel = "pan"
    priority = 3

    def search(self, query: str, intent: SearchIntent, limit: int, page: int, http_client: HTTPClient) -> list[SearchResult]:
        token = os.environ.get("HUNHEPAN_TOKEN", "").strip()
        if not token:
            raise RuntimeError("HUNHEPAN_TOKEN is not configured")
            
        url = f"https://hunhepan.com/open/search/disk?token={token}"
        payload_data = {
            "q": query,
            "page": page,
            "size": limit,
            "time": "",
            "type": "",
            "exact": True
        }
        headers = {
            "Referer": "https://hunhepan.com/"
        }
        
        try:
            payload = http_client.post_json(url, json_data=payload_data, headers=headers)
            if not isinstance(payload, dict):
                return []
            if payload.get("code") not in (200, 0, None) and payload.get("msg"):
                raise RuntimeError(f"hunhepan auth error: {payload.get('msg', 'unknown')}")
            return _flatten_pan_payload(payload, self.name)
        except Exception as exc:
            raise RuntimeError(f"hunhepan source error: {exc}") from exc
