from aifunnel.cache.ttl import TTLCache

stats_cache: TTLCache[dict[str, int]] = TTLCache(ttl_seconds=3.0)
funnel_id_cache: TTLCache[int] = TTLCache(ttl_seconds=60.0)

__all__ = ["TTLCache", "stats_cache", "funnel_id_cache"]
