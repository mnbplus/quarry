"""Configurable ranking weights and scoring parameters.

All scoring magic numbers are centralized here so they can be
overridden via JSON config or programmatic injection without
touching the ranking algorithm itself.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any


@dataclass
class RankingConfig:
    """All tunable weights used by ``ranking.score_result``."""

    # --- Bucket base scores ---
    bucket_exact_title_episode: int = 150
    bucket_exact_title_family: int = 140
    bucket_title_family_match: int = 92
    bucket_episode_only_match: int = 18
    bucket_weak_context_match: int = -8

    # --- Title signal bonuses ---
    exact_core_bonus: int = 30
    phrase_match_bonus: int = 16
    overlap_multiplier: int = 24
    year_match_bonus: int = 10
    season_match_bonus: int = 10
    episode_match_bonus: int = 14

    # --- Resolution bonuses ---
    resolution_4k_bonus: int = 18
    resolution_1080p_bonus: int = 10
    resolution_720p_bonus: int = 4

    # --- Source type bonuses ---
    bluray_source_bonus: int = 8
    webdl_source_bonus: int = 5
    webrip_hdtv_bonus: int = 2
    cam_penalty: int = -28
    remux_bonus: int = 6
    hdr_per_flag_bonus: int = 4
    hdr_max_bonus: int = 8

    # --- Preference bonuses ---
    subtitle_bonus: int = 12
    wants_4k_bonus: int = 20
    lossless_bonus: int = 16
    lossless_mismatch_penalty: int = -28
    hires_bonus: int = 12
    music_hires_source_bonus: int = 8
    music_cd_source_bonus: int = 6
    music_lossy_penalty: int = -12
    book_format_bonus: int = 8
    book_format_match_bonus: int = 10
    book_format_mismatch_penalty: int = -18
    platform_hint_match_bonus: int = 10
    platform_hint_mismatch_penalty: int = -18

    # --- Channel bonuses ---
    pan_password_bonus: int = 6

    # --- Seeder scoring ---
    seeder_divisor: int = 6
    seeder_cap: int = 240

    # --- Bucket penalties ---
    episode_only_penalty: int = -48
    weak_context_penalty: int = -32

    # --- Pan provider scores ---
    pan_provider_scores: dict[str, int] = field(default_factory=lambda: {
        "aliyun": 12, "quark": 11, "115": 10, "pikpak": 9, "uc": 8,
        "baidu": 7, "123": 6, "xunlei": 5, "tianyi": 4, "magnet": 3, "other": 1,
    })

    def bucket_base_score(self, bucket: str) -> int:
        return {
            "exact_title_episode": self.bucket_exact_title_episode,
            "exact_title_family": self.bucket_exact_title_family,
            "title_family_match": self.bucket_title_family_match,
            "episode_only_match": self.bucket_episode_only_match,
            "weak_context_match": self.bucket_weak_context_match,
        }.get(bucket, 0)

    def pan_provider_score(self, provider: str) -> int:
        return self.pan_provider_scores.get(provider, self.pan_provider_scores.get("other", 1))

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "RankingConfig":
        known_fields = {f.name for f in cls.__dataclass_fields__.values()}
        filtered = {k: v for k, v in data.items() if k in known_fields}
        return cls(**filtered)

    @classmethod
    def from_file(cls, path: Path) -> "RankingConfig":
        text = path.read_text(encoding="utf-8")
        data = json.loads(text)
        return cls.from_dict(data)

    def save(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(self.to_dict(), indent=2), encoding="utf-8")


# Module-level default instance
DEFAULT_CONFIG = RankingConfig()
