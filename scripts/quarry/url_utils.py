"""URL, provider, and platform detection utilities."""
from __future__ import annotations

import re
from urllib.parse import unquote, urlparse

from .text_utils import compact_spaces, normalize_key


VIDEO_URL_HINTS = (
    "http://",
    "https://",
    "www.",
    "youtu",
    "bilibili",
    "b23.tv",
    "tiktok",
    "douyin",
    "instagram",
    "twitter",
    "x.com",
    "weibo",
    "vimeo",
    "reddit",
)

DOMAIN_PROVIDER_MAP = {
    "aliyundrive.com": "aliyun",
    "alipan.com": "aliyun",
    "pan.quark.cn": "quark",
    "pan.baidu.com": "baidu",
    "115.com": "115",
    "115cdn.com": "115",
    "mypikpak.com": "pikpak",
    "pan.pikpak.com": "pikpak",
    "drive.uc.cn": "uc",
    "pan.xunlei.com": "xunlei",
    "123pan.com": "123",
    "123684.com": "123",
    "123865.com": "123",
    "123912.com": "123",
    "cloud.189.cn": "tianyi",
    "mega.nz": "mega",
    "mediafire.com": "mediafire",
    "drive.google.com": "gdrive",
    "onedrive.live.com": "onedrive",
    "cowtransfer.com": "cowtransfer",
    "lanzou": "lanzou",
    "lanzoux.com": "lanzou",
    "lanzouq.com": "lanzou",
}

PLATFORM_MAP = {
    "youtube.com": "YouTube",
    "youtu.be": "YouTube",
    "bilibili.com": "Bilibili",
    "b23.tv": "Bilibili",
    "tiktok.com": "TikTok",
    "douyin.com": "Douyin",
    "instagram.com": "Instagram",
    "twitter.com": "Twitter/X",
    "x.com": "Twitter/X",
    "weibo.com": "Weibo",
    "v.qq.com": "Tencent Video",
    "iqiyi.com": "iQIYI",
    "youku.com": "Youku",
    "acfun.cn": "AcFun",
    "nicovideo.jp": "NicoNico",
    "twitch.tv": "Twitch",
    "vimeo.com": "Vimeo",
    "facebook.com": "Facebook",
    "reddit.com": "Reddit",
}


def is_video_url(text: str) -> bool:
    lowered = (text or "").lower()
    return any(hint in lowered for hint in VIDEO_URL_HINTS)


def detect_platform(url: str) -> str:
    lowered = (url or "").lower()
    for domain, name in PLATFORM_MAP.items():
        if domain in lowered:
            return name
    return "Unknown"


def infer_provider_from_url(url: str) -> str:
    parsed = urlparse(url or "")
    host = parsed.netloc.lower()
    for domain, provider in DOMAIN_PROVIDER_MAP.items():
        if domain in host:
            return provider
    if (url or "").startswith("magnet:"):
        return "magnet"
    if (url or "").startswith("ed2k://"):
        return "ed2k"
    return "other"


def extract_password(text: str) -> str:
    decoded = unquote(text or "")
    match = re.search(r"[?&](?:password|pwd|pass)=([^&#]+)", decoded, re.I)
    if match:
        return match.group(1).strip()
    match = re.search(r"(?:\u63d0\u53d6\u7801|\u63d0\u53d6\u78bc|\u5bc6\u7801)[:\uff1a ]*([A-Za-z0-9]{4,8})", decoded)
    if match:
        return match.group(1)
    match = re.search(r"\?([A-Za-z0-9]{4,8})$", decoded)
    if match:
        return match.group(1)
    return ""


def clean_share_url(url: str) -> str:
    decoded = unquote(url or "")
    decoded = re.sub(r"[?&](?:password|pwd|pass)=[^&#]*", "", decoded, flags=re.I)
    decoded = re.sub(r"(?:\u63d0\u53d6\u7801|\u63d0\u53d6\u78bc|\u5bc6\u7801)[:\uff1a ]*[A-Za-z0-9]{4,8}", "", decoded)
    return decoded.rstrip("?&#, ").strip()


def extract_share_id(url: str, provider_hint: str = "") -> str:
    cleaned = clean_share_url(url)
    parsed = urlparse(cleaned)
    path = parsed.path.rstrip("/")
    if cleaned.startswith("magnet:"):
        match = re.search(r"btih:([A-Fa-f0-9]+)", cleaned)
        return match.group(1).lower() if match else normalize_key(cleaned)[:32]
    if cleaned.startswith("ed2k://"):
        return normalize_key(cleaned)[:32]
    if provider_hint == "baidu":
        match = re.search(r"/s/([A-Za-z0-9_-]+)", path)
        if match:
            return match.group(1)
    parts = [part for part in path.split("/") if part]
    return parts[-1] if parts else parsed.netloc.lower()
