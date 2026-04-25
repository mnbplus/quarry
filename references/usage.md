# Quarry Usage

## Search

Main command:

```bash
python3 scripts/hunt.py search "<query>" [options]
```

Key options:

- `--kind movie|tv|anime|music|software|book|general`
- `--channel both|pan|torrent`
- `--quick`
- `--sub`
- `--4k`
- `--json`
- `--json-version 2|3`
- `--page`
- `--limit`

Examples:

```bash
python3 scripts/hunt.py search "Oppenheimer 2023" --kind movie --4k
python3 scripts/hunt.py search "Breaking Bad S01E01" --tv
python3 scripts/hunt.py search "Attack on Titan" --anime --sub
python3 scripts/hunt.py search "Three Body Problem epub" --book --channel pan
python3 scripts/hunt.py search "Jay Chou Fantasy lossless" --music --quick
python3 scripts/hunt.py search "Adobe Photoshop 2024" --software --json
python3 scripts/hunt.py benchmark
```

## Video

Public video URLs go through the `video` subcommands:

```bash
python3 scripts/hunt.py video info "https://youtu.be/..."
python3 scripts/hunt.py video probe "https://www.bilibili.com/video/BV..."
python3 scripts/hunt.py video download "https://youtu.be/..." best
python3 scripts/hunt.py video download "https://youtu.be/..." balanced
python3 scripts/hunt.py video download "https://youtu.be/..." small
python3 scripts/hunt.py video download "https://youtu.be/..." audio
python3 scripts/hunt.py video subtitle "https://youtu.be/..." --lang zh-Hans,zh,en
```

Download presets:

- `best`: highest quality available
- `balanced`: prefer <=1080p
- `small`: prefer <=720p
- `audio`: audio only

## JSON

`search --json` returns JSON v3 by default:

- `schema_version`
- `query`
- `intent`
- `plan`
- `results`
- `suppressed`
- `warnings`
- `source_status`
- `meta`

Each item in `results` includes:

- `channel`
- `normalized_channel`
- `source`
- `upstream_source`
- `provider`
- `title`
- `link_or_magnet`
- `password`
- `share_id_or_info_hash`
- `canonical_identity`
- `size`
- `seeders`
- `quality`
- `tier`
- `score`
- `reasons`
- `penalties`
- `evidence`
- `source_health`
- `raw`

Use `--json-version 2` only for temporary compatibility with legacy consumers.

## Benchmark

Run the offline regression gate:

```bash
python3 scripts/hunt.py benchmark
python3 scripts/hunt.py benchmark --json
```

## Operational notes

- The engine caches normalized responses, source health, alias resolution, and recent video manifests in SQLite
- `sources` shows recent health snapshots; `sources --probe` actively checks sources
- `doctor` reports binaries, cache paths, recent source state, and deterministic video manifests
- No login, no cookie injection, no DRM bypass
