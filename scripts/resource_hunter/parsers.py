"""Release tag and quality parsing utilities."""
from __future__ import annotations

import re
from typing import Any

from .text_utils import text_contains_any, unique_preserve

# --- Regex patterns ---

RELEASE_NOISE_RE = re.compile(
    r"\b(?:"
    r"s\d{1,2}e\d{1,3}|season\s*\d{1,2}|episode\s*\d{1,3}|ep\s*\d{1,3}|"
    r"2160p|1440p|1080p|720p|480p|4k|uhd|"
    r"bluray|blu-ray|bdrip|brrip|web-dl|webdl|webrip|hdtv|dvdrip|"
    r"remux|hdr10\+?|hdr|dolby\s*vision|dovi|hevc|avc|x265|x264|h\.?265|h\.?264|"
    r"dts(?:-hd)?|truehd|atmos|aac|ac3|ddp|flac|mp3|"
    r"10bit|8bit|multi|dual\s*audio|subbed|subtitle|subtitles|"
    r"camrip|hdcam|hd-ts|hdts|telesync|telecine|ts"
    r")\b",
    re.I,
)
YEAR_RE = re.compile(r"\b(19|20)\d{2}\b")
SEASON_EPISODE_RE = re.compile(r"(?:s(?P<season>\d{1,2})[ ._-]*e(?P<episode>\d{1,3})|\b(?P<season2>\d{1,2})x(?P<episode2>\d{1,3})\b)", re.I)
QUALITY_RESOLUTION_RE = re.compile(r"\b(4320p|2160p|1440p|1080p|720p|480p)\b", re.I)
VERSION_RE = re.compile(r"\b(?:v(?:ersion)?\s*)?(\d+(?:\.\d+){0,3}|20\d{2})\b", re.I)
BOOK_FORMAT_RE = re.compile(r"\b(pdf|epub|mobi|azw3)\b", re.I)

SOURCE_PATTERNS = (
    (re.compile(r"\b(?:blu[- ]?ray|bdrip|brrip)\b", re.I), "bluray"),
    (re.compile(r"\b(?:web[- ]?dl|webdl)\b", re.I), "web-dl"),
    (re.compile(r"\b(?:webrip)\b", re.I), "webrip"),
    (re.compile(r"\b(?:hdtv)\b", re.I), "hdtv"),
    (re.compile(r"\b(?:dvdrip)\b", re.I), "dvdrip"),
    (re.compile(r"\b(?:hdcam|camrip|cam)\b", re.I), "cam"),
    (re.compile(r"\b(?:hdts|hd-ts|telesync|telecine)\b", re.I), "cam"),
    (re.compile(r"\b(?:remux)\b", re.I), "remux"),
)

AUDIO_CODEC_PATTERNS = (
    (re.compile(r"\b(?:dts[- ]?hd(?:\s*ma)?|dtshd)\b", re.I), "dts-hd"),
    (re.compile(r"\b(?:truehd|atmos)\b", re.I), "truehd"),
    (re.compile(r"\b(?:ddp|eac3)\b", re.I), "ddp"),
    (re.compile(r"\b(?:ac3)\b", re.I), "ac3"),
    (re.compile(r"\b(?:aac)\b", re.I), "aac"),
    (re.compile(r"\b(?:flac)\b", re.I), "flac"),
    (re.compile(r"\b(?:mp3)\b", re.I), "mp3"),
    (re.compile(r"\b(?:dts)\b", re.I), "dts"),
)

VIDEO_CODEC_PATTERNS = (
    (re.compile(r"\b(?:h\.?265|x265|hevc)\b", re.I), "hevc"),
    (re.compile(r"\b(?:h\.?264|x264|avc)\b", re.I), "avc"),
    (re.compile(r"\b(?:xvid)\b", re.I), "xvid"),
)

PACK_PATTERNS = (
    (re.compile(r"\b(?:remux)\b", re.I), "remux"),
    (re.compile(r"\b(?:repack)\b", re.I), "repack"),
    (re.compile(r"\b(?:proper)\b", re.I), "proper"),
)

HDR_PATTERNS = (
    (re.compile(r"\bhdr10\+?\b", re.I), "hdr10"),
    (re.compile(r"\bdovi\b|\bdolby\s*vision\b", re.I), "dolby-vision"),
    (re.compile(r"\bhdr\b", re.I), "hdr"),
)

SUBTITLE_TERMS = (
    "\u4e2d\u5b57",
    "\u5b57\u5e55",
    "subtitle",
    "subtitles",
    "subbed",
    "sub",
)
LOSSLESS_TERMS = ("flac", "\u65e0\u635f", "ape", "alac", "wav")
LOSSY_TERMS = ("mp3", "aac", "ogg", "wma", "m4a")

# --- Music-specific patterns ---
SAMPLE_RATE_RE = re.compile(r"(\d+(?:\.\d+)?)\s*k?Hz", re.I)
BIT_DEPTH_RE = re.compile(r"(\d+)[\s-]*bit", re.I)
HIRES_RE = re.compile(r"\b(?:hi[\s-]?res|high[\s-]?resolution|hires)\b", re.I)
MUSIC_SOURCE_PATTERNS = (
    (re.compile(r"\b(?:Mora|Qobuz|Tidal|Deezer|OTOTOY|e[\s-]?onkyo|Bandcamp|KKBOX)(?:\.\w+)?\b", re.I), "web-hires"),
    (re.compile(r"\bCD\b"), "cd"),
    (re.compile(r"\bvinyl\b", re.I), "vinyl"),
    (re.compile(r"\b(?:iTunes|Spotify|Apple\s*Music|Amazon\s*Music|NetEase|QQ\s*Music)\b", re.I), "web"),
)


# --- Functions ---


def extract_year(text: str) -> str:
    match = YEAR_RE.search(text or "")
    return match.group(0) if match else ""


def extract_versions(text: str) -> list[str]:
    values = [item.group(1) for item in VERSION_RE.finditer(text or "")]
    return unique_preserve(values)


def extract_book_formats(text: str) -> list[str]:
    return unique_preserve([item.group(1).lower() for item in BOOK_FORMAT_RE.finditer(text or "")])


def extract_season_episode(text: str) -> tuple[int | None, int | None]:
    match = SEASON_EPISODE_RE.search(text or "")
    if match:
        season = match.group("season") or match.group("season2")
        episode = match.group("episode") or match.group("episode2")
        return (int(season) if season else None, int(episode) if episode else None)
    en_match = re.search(r"season\s*(\d{1,2}).{0,10}?episode\s*(\d{1,3})", text or "", re.I)
    if en_match:
        return int(en_match.group(1)), int(en_match.group(2))
    cn_match = re.search(r"\u7b2c\s*(\d{1,2})\s*\u5b63", text or "")
    ep_match = re.search(r"\u7b2c\s*(\d{1,3})\s*\u96c6", text or "")
    return (
        int(cn_match.group(1)) if cn_match else None,
        int(ep_match.group(1)) if ep_match else None,
    )


def _detect_source_type(lowered: str) -> str:
    for pattern, label in SOURCE_PATTERNS:
        if pattern.search(lowered):
            return label
    return ""


def _detect_codec(lowered: str, patterns: tuple[tuple[re.Pattern[str], str], ...]) -> str:
    for pattern, label in patterns:
        if pattern.search(lowered):
            return label
    return ""


def _detect_music_source(text: str) -> str:
    for pattern, label in MUSIC_SOURCE_PATTERNS:
        if pattern.search(text):
            return label
    return ""


def _parse_sample_rate(text: str) -> float:
    """Extract sample rate in kHz. Returns 0.0 if not found."""
    match = SAMPLE_RATE_RE.search(text or "")
    if not match:
        return 0.0
    value = float(match.group(1))
    # Normalize: values like 44100/48000/96000 are in Hz, convert to kHz
    if value > 1000:
        value = value / 1000.0
    return round(value, 1)


def _parse_bit_depth(text: str) -> int:
    """Extract bit depth. Returns 0 if not found."""
    match = BIT_DEPTH_RE.search(text or "")
    if not match:
        return 0
    depth = int(match.group(1))
    return depth if depth in (8, 16, 24, 32) else 0


def parse_release_tags(text: str) -> dict[str, Any]:
    lowered = (text or "").lower()
    resolution_match = QUALITY_RESOLUTION_RE.search(lowered)
    resolution = resolution_match.group(1).lower() if resolution_match else ""
    if not resolution and re.search(r"\b(?:4k|uhd)\b", lowered):
        resolution = "2160p"
    hdr_flags = [label for pattern, label in HDR_PATTERNS if pattern.search(lowered)]
    source_type = _detect_source_type(lowered)
    pack = _detect_codec(lowered, PACK_PATTERNS)
    subtitle = text_contains_any(text, SUBTITLE_TERMS)
    lossless = any(term in lowered for term in LOSSLESS_TERMS)
    lossy = any(term in lowered for term in LOSSY_TERMS)
    book_format = next((item.lower() for item in extract_book_formats(lowered)), "")

    # Music-specific quality parsing
    sample_rate = _parse_sample_rate(text)
    bit_depth = _parse_bit_depth(text)
    hires_explicit = bool(HIRES_RE.search(text or ""))
    music_source = _detect_music_source(text or "")
    # Hi-Res: lossless + (24-bit or sample_rate > 44.1kHz or explicit Hi-Res tag)
    hires = lossless and (bit_depth >= 24 or sample_rate > 44.1 or hires_explicit)
    # Audio quality tier
    if hires:
        audio_quality_tier = "hires"
    elif lossless:
        audio_quality_tier = "lossless"
    elif lossy:
        audio_quality_tier = "lossy"
    else:
        audio_quality_tier = ""

    return {
        "resolution": resolution,
        "source_type": source_type,
        "audio_codec": _detect_codec(lowered, AUDIO_CODEC_PATTERNS),
        "video_codec": _detect_codec(lowered, VIDEO_CODEC_PATTERNS),
        "pack": pack,
        "hdr_flags": hdr_flags,
        "subtitle": subtitle,
        "lossless": lossless,
        "lossy": lossy,
        "format": book_format,
        "book_format": book_format,
        "sample_rate_khz": sample_rate,
        "bit_depth": bit_depth,
        "hires": hires,
        "music_source": music_source,
        "audio_quality_tier": audio_quality_tier,
    }


def parse_quality_tags(text: str) -> dict[str, Any]:
    tags = parse_release_tags(text)
    # Alias for backward compatibility
    tags["source"] = tags["source_type"]
    return tags


def quality_display_from_tags(tags: dict[str, Any]) -> str:
    bits: list[str] = []
    if tags.get("book_format"):
        bits.append(tags["book_format"])
    elif tags.get("hires"):
        bits.append("hi-res")
        if tags.get("sample_rate_khz"):
            bits.append(f"{tags['sample_rate_khz']}kHz")
        if tags.get("bit_depth"):
            bits.append(f"{tags['bit_depth']}bit")
    elif tags.get("lossless"):
        bits.append("lossless")
        if tags.get("sample_rate_khz"):
            bits.append(f"{tags['sample_rate_khz']}kHz")
        if tags.get("bit_depth"):
            bits.append(f"{tags['bit_depth']}bit")
    elif tags.get("lossy"):
        codec = tags.get("audio_codec", "")
        bits.append(codec if codec else "lossy")
    elif tags.get("resolution"):
        bits.append(tags["resolution"])
    if tags.get("music_source") and tags["music_source"] not in {"web"}:
        bits.append(tags["music_source"])
    elif tags.get("source_type") and tags["source_type"] not in {"cam"}:
        bits.append(tags["source_type"])
    if tags.get("pack"):
        bits.append(tags["pack"])
    return " ".join(unique_preserve(bits))


def infer_quality(text: str) -> str:
    return quality_display_from_tags(parse_quality_tags(text))
