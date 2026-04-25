# Local Customization Directory

This directory is your **safe zone** for custom configurations. It is:

- ✅ **Gitignored** — never tracked by version control
- ✅ **Update-safe** — never overwritten by `git pull` or ZIP updates
- ✅ **Auto-loaded** — the engine discovers and loads everything here on startup

## Directory Structure

```
local/
├── sources/          # Custom source adapters (auto-registered)
│   └── my_source.py  # Your custom SourceAdapter subclass
├── config.json       # Ranking weight overrides
└── .env              # (alternative location for environment variables)
```

## Custom Source Adapters

Drop any `.py` file into `local/sources/` that defines a `SourceAdapter` subclass.
The engine auto-discovers and registers it on startup.

Example `local/sources/my_tracker.py`:

```python
from resource_hunter.sources.base import SourceAdapter, HTTPClient
from resource_hunter.models import SearchIntent, SearchResult

class MyTrackerSource(SourceAdapter):
    name = "mytracker"
    channel = "torrent"
    priority = 3

    def search(self, query, intent, limit, page, http_client):
        # Your custom search logic here
        return []
```

## Config Overrides

Create `local/config.json` to override ranking weights without editing source code:

```json
{
  "resolution_4k_bonus": 25,
  "lossless_bonus": 20,
  "pan_provider_scores": {
    "aliyun": 15,
    "quark": 14
  }
}
```

## Environment Variables

You can also place a `.env` file here (in addition to the project root `.env`).
Local `.env` values take priority over root `.env`.
