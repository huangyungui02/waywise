"""显式联调 SDK 的真实 Redis 事件重放、独立订阅与结束语义。"""

import asyncio
from uuid import uuid4

import anyio
import pytest
from redis.asyncio import ConnectionPool, Redis
from redis_fastapi import StreamBackend
from redis_fastapi.config import get_settings
from redis_fastapi.exceptions import StreamCursorAhead, StreamNotFound


def test_live_sdk_streams(request, monkeypatch):
    url = request.config.getoption("--redis-url")
    if url is None:
        pytest.skip("通过 --redis-url 显式启用真实 Redis 联调")
    prefix = f"travel-agent-test-{uuid4().hex}"
    monkeypatch.setenv("REDIS_PREFIX", prefix)
    monkeypatch.setenv("REDIS_STREAM_DONE_TTL", "1")
    get_settings.cache_clear()

    async def check():
        pool = ConnectionPool.from_url(url, decode_responses=True, socket_timeout=30)
        async with Redis.from_pool(pool) as redis:
            streams = StreamBackend(lambda: redis)
            try:
                assert await streams.detect() is True
                writer = await streams.open(scope="conversation", stream_id="run")
                first = await writer.append("ui", "first")
                received = [[], []]

                async def subscribe(index):
                    async with await streams.follow(
                        "run", scope="conversation", after=first
                    ) as reader:
                        received[index].extend([event async for event in reader])

                with anyio.fail_after(5):
                    async with anyio.create_task_group() as tasks:
                        tasks.start_soon(subscribe, 0)
                        tasks.start_soon(subscribe, 1)
                        await anyio.sleep(0.05)
                        second = await writer.append("ui", "second")
                        final = await writer.finish("result", {"outcome": "completed"})
                assert received[0] == received[1]
                assert [event.id for event in received[0]] == [second, final]
                async with await streams.follow(
                    "run", scope="conversation", after=final
                ) as reader:
                    assert [event async for event in reader] == []
                with pytest.raises(StreamCursorAhead):
                    await streams.follow(
                        "run", scope="conversation", after="999999999999999-0"
                    )
                await anyio.sleep(1.1)
                with pytest.raises(StreamNotFound):
                    await streams.follow("run", scope="conversation")
            finally:
                await streams.aclose()
                async for key in redis.scan_iter(match=f"{prefix}*"):
                    await redis.delete(key)

    try:
        asyncio.run(check())
    finally:
        get_settings.cache_clear()
