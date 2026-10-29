from fastapi import HTTPException, status
from redis.asyncio import Redis

from alphaview_common.settings import get_common_settings

redis = Redis.from_url(get_common_settings().redis_url, decode_responses=True)


async def enforce(key: str, limit: int, window_seconds: int) -> None:
    """Fixed-window limiter; raises 429 when `limit` is exceeded within the window."""
    bucket = f"rl:{key}"
    count = await redis.incr(bucket)
    if count == 1:
        await redis.expire(bucket, window_seconds)
    if count > limit:
        raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, "Rate limit exceeded, try again later")
