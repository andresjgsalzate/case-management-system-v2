from redis.asyncio import Redis, ConnectionPool

from backend.src.core.config import get_settings

_pool: ConnectionPool | None = None
_redis: Redis | None = None


async def init_redis() -> None:
    global _pool, _redis
    settings = get_settings()
    _pool = ConnectionPool.from_url(
        settings.REDIS_URL,
        encoding="utf-8",
        decode_responses=True,
        max_connections=20,
    )
    _redis = Redis(connection_pool=_pool)


async def close_redis() -> None:
    global _redis, _pool
    if _redis:
        await _redis.aclose()
        _redis = None
    if _pool:
        await _pool.aclose()
        _pool = None


def get_redis() -> Redis:
    if _redis is None:
        raise RuntimeError("Redis not initialized. Call init_redis() first.")
    return _redis
