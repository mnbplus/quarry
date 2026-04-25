from __future__ import annotations

import json
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any

from .pan_probe import PanLinkProber

from .benchmark import run_benchmark_suite
from .cache import ResourceCache
from .config import DEFAULT_CONFIG, RankingConfig
from .intent import AliasResolver, build_plan, enrich_intent_with_aliases
from .models import SearchIntent, SearchPlan, SearchResult, SourceStatus
from .ranking import deduplicate_results, diversify_results, score_result, source_health, source_is_degraded
from .sources import HTTPClient, SourceAdapter, default_adapters, profile_for


def _load_local_config() -> RankingConfig:
    """Load user ranking overrides from ``local/config.json`` if it exists."""
    local_config = Path(__file__).resolve().parent.parent.parent / "local" / "config.json"
    if local_config.is_file():
        try:
            return RankingConfig.from_file(local_config)
        except Exception:
            pass  # broken config → fall back to defaults
    return DEFAULT_CONFIG


def _classify_failure_kind(error: str) -> str:
    lowered = (error or "").lower()
    if lowered.startswith("http 4"):
        return "http_4xx"
    if lowered.startswith("http 5"):
        return "http_5xx"
    if "invalid json" in lowered:
        return "json"
    if "unexpected pan payload shape" in lowered or "unexpected payload type" in lowered:
        return "schema"
    if "ssl" in lowered or "timed out" in lowered or "urlopen error" in lowered:
        return "network"
    if "circuit open" in lowered:
        return "circuit_open"
    return "unknown"


class ResourceHunterEngine:
    def __init__(self, cache: ResourceCache | None = None, http_client: HTTPClient | None = None) -> None:
        self.cache = cache or ResourceCache()
        self.http_client = http_client or HTTPClient(retries=1, default_timeout=10)
        self.alias_resolver = AliasResolver()
        self.pan_sources, self.torrent_sources = default_adapters()
        self.pan_prober = PanLinkProber()
        self.config = _load_local_config()
        try:
            self.cache.cleanup()
        except Exception:
            pass

    def _resolve_aliases(self, intent: SearchIntent) -> SearchIntent:
        alias_resolution = self.alias_resolver.resolve(intent, self.cache, self.http_client)
        return enrich_intent_with_aliases(intent, alias_resolution)

    def _cache_key(self, intent: SearchIntent, plan: SearchPlan, page: int, limit: int) -> str:
        payload = json.dumps(
            {
                "schema_version": "3",
                "intent": intent.to_dict(),
                "plan": plan.to_dict(),
                "page": page,
                "limit": limit,
            },
            sort_keys=True,
            ensure_ascii=False,
        )
        return __import__("hashlib").sha256(payload.encode("utf-8")).hexdigest()

    def _catalog_for_channel(self, channel: str) -> list[SourceAdapter]:
        return self.pan_sources if channel == "pan" else self.torrent_sources

    def _ordered_sources(self, channel: str, plan: SearchPlan, intent: SearchIntent) -> list[SourceAdapter]:
        preferred_names = plan.preferred_pan_sources if channel == "pan" else plan.preferred_torrent_sources
        preferred = {name: index for index, name in enumerate(preferred_names)}
        catalog = [
            source
            for source in self._catalog_for_channel(channel)
            if source.supports(intent)
        ]
        return sorted(
            catalog,
            key=lambda item: (
                preferred.get(item.name, 999) + (100 if source_is_degraded(self.cache, item.name) else 0),
                item.priority,
            ),
        )

    def _search_source(
        self,
        source: SourceAdapter,
        channel: str,
        queries: list[str],
        intent: SearchIntent,
        page: int,
        limit: int,
    ) -> tuple[SourceStatus, list[SearchResult]]:
        profile = profile_for(source.name)
        current_health = source_health(self.cache, source.name)
        degraded_before = bool(current_health.get("degraded"))
        if self.cache.should_skip_source(source.name, profile.cooldown_seconds, profile.failure_threshold):
            status = SourceStatus(
                source=source.name,
                channel=channel,
                priority=source.priority,
                ok=False,
                skipped=True,
                degraded=True,
                degraded_reason="circuit_open",
                recovery_state="cooldown",
                last_success_epoch=current_health.get("last_success_epoch"),
                error="circuit open from recent failures",
                failure_kind="circuit_open",
            )
            self.cache.record_source_status(status)
            return status, []

        status = SourceStatus(
            source=source.name,
            channel=channel,
            priority=source.priority,
            ok=True,
            skipped=False,
            degraded=degraded_before,
            degraded_reason=current_health.get("degraded_reason", ""),
            recovery_state=current_health.get("recovery_state", "healthy"),
            last_success_epoch=current_health.get("last_success_epoch"),
        )
        results: list[SearchResult] = []
        client = HTTPClient(retries=profile.retries, default_timeout=profile.timeout)
        query_budget = 1 if (profile.default_degraded or degraded_before) else profile.query_budget
        for query in queries[:query_budget]:
            if not query:
                continue
            started = time.time()
            try:
                batch = source.search(query, intent, limit, page, client)
                status.latency_ms = int((time.time() - started) * 1000)
                status.ok = True
                status.error = ""
                status.failure_kind = ""
                if batch:
                    status.degraded = source_health(self.cache, source.name).get("degraded", degraded_before)
                    status.degraded_reason = current_health.get("degraded_reason", "")
                    status.recovery_state = "healthy" if not status.degraded else "recovering"
                    results.extend(batch)
                    break
            except Exception as exc:
                status.ok = False
                status.latency_ms = int((time.time() - started) * 1000)
                status.error = str(exc)[:200]
                status.failure_kind = _classify_failure_kind(status.error)
                status.degraded = profile.default_degraded or degraded_before
                status.degraded_reason = status.failure_kind or "request_failure"
                status.recovery_state = "recovering" if status.degraded else "degraded"
        self.cache.record_source_status(status)
        return status, results

    def _probe_pan_results(self, results: list[SearchResult]) -> list[SearchResult]:
        """Probe pan links for viability and demote dead links to 'risky'."""
        pan_candidates = [
            (i, r) for i, r in enumerate(results)
            if r.channel == "pan" and r.tier in ("top", "related")
        ]
        if not pan_candidates:
            return results
        probe_items = [(r.link_or_magnet, r.provider) for _, r in pan_candidates]
        probe_results = self.pan_prober.probe_batch(probe_items, max_workers=4)
        for (idx, result), probe in zip(pan_candidates, probe_results):
            result.source_health["link_alive"] = probe.alive
            result.source_health["link_probe_reason"] = probe.reason
            if probe.title:
                result.source_health["link_title"] = probe.title
            if probe.alive is False:
                result.tier = "risky"
                result.penalties.append("dead link detected")
                result.score -= 50
        return results

    def search(
        self,
        intent: SearchIntent,
        plan: SearchPlan | None = None,
        page: int = 1,
        limit: int = 8,
        use_cache: bool = True,
        probe_links: bool = True,
    ) -> dict[str, Any]:
        intent = self._resolve_aliases(intent)
        plan = plan or build_plan(intent)
        cache_key = self._cache_key(intent, plan, page, limit)
        if use_cache:
            cached = self.cache.get_search_cache(cache_key)
            if cached:
                cached.setdefault("meta", {})
                cached["meta"]["cached"] = True
                return cached

        results: list[SearchResult] = []
        statuses: list[SourceStatus] = []
        warnings: list[str] = []

        for channel in plan.channels:
            queries = plan.pan_queries if channel == "pan" else plan.torrent_queries
            ordered_sources = self._ordered_sources(channel, plan, intent)
            with ThreadPoolExecutor(max_workers=min(4, len(ordered_sources) or 1)) as executor:
                futures = [
                    executor.submit(self._search_source, source, channel, queries, intent, page, limit)
                    for source in ordered_sources
                ]
                for future in as_completed(futures):
                    status, source_results = future.result()
                    statuses.append(status)
                    results.extend(source_results)

        scored = [score_result(result, intent, cache=self.cache) for result in results]
        deduped = deduplicate_results(scored)
        if probe_links:
            deduped = self._probe_pan_results(deduped)
        ordered = diversify_results(deduped)
        suppressed = [
            {
                "title": item.title,
                "source": item.source,
                "tier": item.tier,
                "reason": item.match_bucket,
                "score": item.score,
            }
            for item in ordered
            if item.tier == "risky"
        ]
        statuses.sort(key=lambda item: (item.channel, item.priority, item.source))

        if not ordered:
            warnings.append("no results returned from active sources")

        response = {
            "schema_version": "3",
            "query": intent.original_query,
            "intent": intent.to_dict(),
            "plan": plan.to_dict(),
            "results": [result.to_public_dict() for result in ordered],
            "suppressed": suppressed,
            "warnings": warnings,
            "source_status": [status.to_dict() for status in statuses],
            "meta": {
                "cached": False,
                "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                "limit": limit,
                "page": page,
                "candidate_count": len(ordered),
                "effective_limit": min(limit, 4) if intent.quick else limit,
                "alias_resolution": intent.alias_resolution,
                "resolved_titles": intent.resolved_titles,
                "resolved_year": intent.resolved_year or intent.year,
            },
        }
        if use_cache:
            self.cache.set_search_cache(cache_key, response, ttl_seconds=300)
        return response

    def source_catalog(self, probe: bool = False) -> dict[str, Any]:
        sources: list[dict[str, Any]] = []
        cached_status = {row["source"]: row for row in self.cache.list_source_statuses()}
        all_sources = self.pan_sources + self.torrent_sources
        for adapter in sorted(all_sources, key=lambda item: (item.channel, item.priority, item.name)):
            status_info = cached_status.get(adapter.name, {})
            if probe:
                profile = profile_for(adapter.name)
                started = time.time()
                ok, error = adapter.healthcheck(HTTPClient(retries=profile.retries, default_timeout=profile.timeout))
                status = SourceStatus(
                    source=adapter.name,
                    channel=adapter.channel,
                    priority=adapter.priority,
                    ok=ok,
                    skipped=False,
                    degraded=False if ok and not profile.default_degraded else profile.default_degraded and not ok,
                    degraded_reason="" if ok else (_classify_failure_kind(error) or "probe_failure"),
                    recovery_state="healthy" if ok else "degraded",
                    last_success_epoch=self.cache.latest_success_epoch(adapter.name),
                    error=error,
                    failure_kind="probe_ok" if ok else _classify_failure_kind(error),
                    latency_ms=int((time.time() - started) * 1000),
                )
                self.cache.record_source_status(status)
                status_info = status.to_dict()
            if status_info:
                latest_health = {
                    "degraded": bool(status_info.get("degraded")),
                    "degraded_reason": status_info.get("degraded_reason", ""),
                    "recovery_state": status_info.get("recovery_state", "unknown"),
                    "last_success_epoch": status_info.get("last_success_epoch"),
                    "failure_kind": status_info.get("failure_kind", ""),
                }
            else:
                latest_health = source_health(self.cache, adapter.name)
            sources.append(
                {
                    "source": adapter.name,
                    "channel": adapter.channel,
                    "priority": adapter.priority,
                    "capability": adapter.capability_profile(),
                    "recent_status": {
                        "ok": bool(status_info.get("ok")) if status_info else None,
                        "skipped": bool(status_info.get("skipped")) if status_info else False,
                        "degraded": latest_health["degraded"],
                        "degraded_reason": latest_health.get("degraded_reason", ""),
                        "recovery_state": latest_health.get("recovery_state", "unknown"),
                        "last_success_epoch": latest_health.get("last_success_epoch"),
                        "latency_ms": status_info.get("latency_ms"),
                        "error": status_info.get("error", ""),
                        "failure_kind": latest_health.get("failure_kind", ""),
                        "checked_at": status_info.get("checked_at"),
                    },
                }
            )
        return {"schema_version": "3", "sources": sources, "meta": {"probe": probe}}

    def run_benchmark(self) -> dict[str, Any]:
        return run_benchmark_suite()


__all__ = ["ResourceHunterEngine", "build_plan", "source_health", "source_is_degraded"]
