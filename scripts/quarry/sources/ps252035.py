"""ps.252035.xyz pan search source adapter."""
from __future__ import annotations
import os
from .base import HTTPClient, SourceAdapter, _flatten_pan_payload
from ..models import SearchIntent, SearchResult


class Ps252035Source(SourceAdapter):
    name = "ps.252035"
    channel = "pan"
    priority = 2

    def search(self, query: str, intent: SearchIntent, limit: int, page: int, http_client: HTTPClient) -> list[SearchResult]:
        token = os.environ.get("PANSOU_TOKEN", "").strip()
        if not token:
            raise RuntimeError("PANSOU_TOKEN is not configured")
            
        url = "https://ps.252035.xyz/api/search"
        payload_data = {
            "kw": query,
            "page": page,
        }
        headers = {
            "Authorization": f"Bearer {token}",
            "Referer": "https://ps.252035.xyz/"
        }
        
        payload = http_client.post_json(url, json_data=payload_data, headers=headers)
        if not isinstance(payload, dict):
            return []
        
        if payload.get("code") == "AUTH_TOKEN_MISSING" or payload.get("error"):
            raise RuntimeError(f"ps.252035 auth error: {payload.get('error', 'unknown')}")
            
        return _flatten_pan_payload(payload, self.name)
