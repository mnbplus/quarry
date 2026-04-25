"""Title and text normalization, tokenization, and language detection."""
from __future__ import annotations

import re
from typing import Iterable
from urllib.parse import unquote


CHINESE_RE = re.compile(r"[\u4e00-\u9fff]")
LATIN_RE = re.compile(r"[A-Za-z]")
TOKEN_RE = re.compile(r"[\u4e00-\u9fff]+|[a-z0-9]+", re.I)
BRACKET_RE = re.compile(r"[\[\]\(\)\{\}]")
EN_ALIAS_PAREN_RE = re.compile(r"[\(\uff08]([A-Za-z][^()\uff08\uff09]{1,100})[\)\uff09]")
EN_ALIAS_RE = re.compile(r"([A-Za-z][A-Za-z0-9\s\.\-:']{2,100})")
YEAR_RE = re.compile(r"\b(19|20)\d{2}\b")
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

STOPWORDS = {
    "the",
    "a",
    "an",
    "and",
    "of",
    "to",
    "for",
    "in",
    "on",
    "with",
    "at",
}


def compact_spaces(text: str) -> str:
    return re.sub(r"\s+", " ", text or "").strip()


def has_chinese(text: str) -> bool:
    return bool(CHINESE_RE.search(text or ""))


def has_latin(text: str) -> bool:
    return bool(LATIN_RE.search(text or ""))


def detect_language_mix(text: str) -> str:
    has_cn = has_chinese(text)
    has_en = has_latin(text)
    if has_cn and has_en:
        return "mixed"
    if has_cn:
        return "chinese"
    if has_en:
        return "latin"
    return "unknown"


def unique_preserve(items: Iterable[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for item in items:
        if not item:
            continue
        key = item.lower()
        if key in seen:
            continue
        seen.add(key)
        out.append(item)
    return out


def normalize_title(text: str) -> str:
    cleaned = re.sub(r"<[^>]+>", " ", text or "")
    cleaned = unquote(cleaned)
    cleaned = compact_spaces(cleaned)
    return cleaned.strip(" -_|[]()")


def normalize_key(text: str) -> str:
    cleaned = normalize_title(text).lower()
    return re.sub(r"[^a-z0-9\u4e00-\u9fff]+", "", cleaned)


def _strip_title_noise(text: str) -> str:
    value = compact_spaces(unquote(text or "")).lower()
    # Strip pan extraction code prefixes (e.g. "提取码：ZTMY]仙逆" → "仙逆")
    value = re.sub(r"提取码[：:]\s*\w+[\]】\s]", " ", value)
    value = YEAR_RE.sub(" ", value)
    value = RELEASE_NOISE_RE.sub(" ", value)
    value = re.sub(r"[-_.:,/\\]+", " ", value)
    value = BRACKET_RE.sub(" ", value)
    value = re.sub(r"\b(?:proper|repack|extended|limited|complete|dual|multi)\b", " ", value)
    return compact_spaces(value)


def title_tokens(text: str, keep_numeric: bool = False) -> list[str]:
    tokens: list[str] = []
    for token in TOKEN_RE.findall(_strip_title_noise(text)):
        lowered = token.lower()
        if lowered in STOPWORDS:
            continue
        if not keep_numeric and lowered.isdigit():
            continue
        if len(lowered) == 1 and not CHINESE_RE.search(lowered):
            continue
        tokens.append(lowered)
    return tokens


def title_core(text: str) -> str:
    return " ".join(title_tokens(text))


def text_contains_any(text: str, terms: Iterable[str]) -> bool:
    lowered = (text or "").lower()
    return any(term.lower() in lowered for term in terms)


def token_overlap_score(query_tokens: list[str], title_tokens_: list[str]) -> float:
    """Recall-weighted overlap between query and title tokens.

    Uses F-beta scoring to handle the asymmetry between short queries
    and long fansub-style titles.  When the title is much longer than
    the query (3x+), beta=2 is used so that recall dominates.  For
    moderately-sized titles, balanced F1 is used to avoid over-promoting
    mention-only matches (e.g. ``Breaking Bad`` appearing inside
    ``The Writers Room S01E01 Breaking Bad``).
    """
    if not query_tokens or not title_tokens_:
        return 0.0
    query_set = set(query_tokens)
    title_set = set(title_tokens_)
    shared = query_set & title_set
    if not shared:
        return 0.0
    recall = len(shared) / len(query_set)
    precision = len(shared) / len(title_set)
    # Use recall-heavy F2 only when title is much longer (fansub scenario)
    beta = 2.0 if len(title_set) >= 3 * len(query_set) else 1.0
    score = (1 + beta ** 2) * (precision * recall) / (beta ** 2 * precision + recall)
    return round(score, 4)


def _clean_alias(value: str) -> str:
    cleaned = compact_spaces(BRACKET_RE.sub(" ", value))
    cleaned = YEAR_RE.sub(" ", cleaned)
    cleaned = RELEASE_NOISE_RE.sub(" ", cleaned)
    cleaned = compact_spaces(cleaned)
    return cleaned.strip(" -_|")


def extract_english_alias(text: str) -> str:
    from .url_utils import is_video_url
    if is_video_url(text):
        return ""
    if has_chinese(text):
        match = EN_ALIAS_PAREN_RE.search(text or "")
        if match:
            return _clean_alias(match.group(1))
        match = EN_ALIAS_RE.search(text or "")
        if match:
            return _clean_alias(match.group(1))
        return ""
    if has_latin(text):
        return _clean_alias(text)
    return ""


def extract_chinese_alias(text: str) -> str:
    chunks = re.findall(r"[\u4e00-\u9fff0-9\uff1a:\u00b7\-\s]{2,80}", text or "")
    cleaned = [compact_spaces(chunk) for chunk in chunks if has_chinese(chunk)]
    return cleaned[0] if cleaned else ""
