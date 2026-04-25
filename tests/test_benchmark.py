from resource_hunter.benchmark import run_benchmark_suite
from resource_hunter.common import parse_quality_tags
from resource_hunter.intent import parse_intent
from resource_hunter.models import SearchResult
from resource_hunter.ranking import score_result


def test_benchmark_suite_passes_gate():
    payload = run_benchmark_suite()
    assert payload["pass"] is True
    assert payload["search_cases"] == 180
    assert payload["video_cases"] == 20


def test_release_parser_distinguishes_dts_and_cam():
    tags = parse_quality_tags("Breaking Bad S01E01 1080p BluRay DTS-HD MA 5.1 REMUX")
    assert tags["source_type"] == "bluray"
    assert tags["audio_codec"] == "dts-hd"
    assert tags["pack"] == "remux"


def test_music_lossless_preference_downgrades_mp3():
    intent = parse_intent("Jay Chou Fantasy 无损", explicit_kind="music")
    flac = score_result(
        SearchResult(
            channel="pan",
            source="2fun",
            provider="aliyun",
            title="Jay Chou - Fantasy FLAC",
            link_or_magnet="https://example.com/flac",
            share_id_or_info_hash="flac",
        ),
        intent,
        cache=None,
    )
    mp3 = score_result(
        SearchResult(
            channel="pan",
            source="2fun",
            provider="aliyun",
            title="Jay Chou - Fantasy MP3",
            link_or_magnet="https://example.com/mp3",
            share_id_or_info_hash="mp3",
        ),
        intent,
        cache=None,
    )
    assert flac.score > mp3.score
    assert mp3.tier != "top"
