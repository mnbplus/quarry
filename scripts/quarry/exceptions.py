"""Custom exception hierarchy for quarry.

Provides structured error types so callers can distinguish between
network failures, parse errors, rate limits, and source unavailability
instead of catching generic RuntimeError everywhere.
"""
from __future__ import annotations


class ResourceHunterError(Exception):
    """Base class for all quarry errors."""


class SourceError(ResourceHunterError):
    """Base class for source adapter errors."""

    def __init__(self, message: str, source: str = "", url: str = "") -> None:
        super().__init__(message)
        self.source = source
        self.url = url


class SourceNetworkError(SourceError):
    """Network-level failure: timeout, DNS, connection refused, SSL."""


class SourceParseError(SourceError):
    """Response was received but could not be parsed (HTML changed, invalid JSON)."""


class SourceRateLimitError(SourceError):
    """Source returned HTTP 429 or equivalent throttle signal."""


class SourceUnavailableError(SourceError):
    """Source is down or returned 5xx / connection refused."""


class CacheError(ResourceHunterError):
    """Error reading or writing the SQLite cache."""


class BinaryNotFoundError(ResourceHunterError):
    """A required external binary (yt-dlp, ffmpeg) was not found."""
