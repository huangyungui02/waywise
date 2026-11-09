"""Redis 检查点、原生事件游标、订阅广播和自动过期。"""

import asyncio
import json

import anyio
from fakeredis.aioredis import FakeRedis
from pydantic_ai.ui.vercel_ai.response_types import DataChunk, DoneChunk

from replies import ReplyStore


def test_reply_checkpoint_replaces_previous_events_and_deletes():
    async def check():
        async with FakeRedis(decode_responses=True) as redis:
            store = ReplyStore(redis, retention_seconds=60)
            messages = [{"id": "user", "role": "user", "parts": []}]
            await store.begin("conversation", "first", messages)
            first = await store.append("first", '{"type":"start","messageId":"first"}')
            second = await store.append("first", '{"type":"text-start","id":"text"}')
            checkpoint = await store.snapshot("conversation")
            assert checkpoint["cursor"] == second
            assert checkpoint["messages"] == messages
            assert checkpoint["outcome"] == "running"
            assert await redis.ttl(store.metadata("first")) == -1
            await store.finish("first", "completed")
            checkpoint = await store.snapshot("conversation")
            assert checkpoint["outcome"] == "completed"
            assert await ReplyStore(redis).snapshot("conversation") == checkpoint
            assert 0 < await redis.ttl(store.stream("first")) <= 60
            tail = [chunk async for chunk in store.events("first", first)]
            assert [
                json.loads(c.encode(6))
                for c in tail
                if not isinstance(c, (DataChunk, DoneChunk))
            ] == [{"type": "text-start", "id": "text"}]
            assert isinstance(tail[-1], DoneChunk)
            await store.begin("conversation", "second", messages)
            assert not await redis.exists(
                store.stream("first"), store.metadata("first")
            )
            checkpoint = await store.snapshot("conversation")
            assert checkpoint["cursor"] == "0-0"
            assert checkpoint["events"] == []
            await store.append("second", '{"type":"start","messageId":"second"}')
            await store.interrupt("conversation")
            assert (await store.snapshot("conversation"))["outcome"] == "cancelled"
            await store.delete("conversation")
            assert await store.snapshot("conversation") is None
            assert not await redis.exists(
                store.stream("second"), store.metadata("second")
            )

    asyncio.run(check())


def test_blocking_read_broadcasts_to_each_subscriber_and_finishes():
    async def check():
        async with FakeRedis(decode_responses=True) as redis:
            store = ReplyStore(redis)
            await store.begin("conversation", "run", [])
            received = [[], []]

            async def subscribe(index):
                async for chunk in store.events("run"):
                    received[index].append(chunk.encode(6))

            with anyio.fail_after(3):
                async with anyio.create_task_group() as tasks:
                    tasks.start_soon(subscribe, 0)
                    tasks.start_soon(subscribe, 1)
                    await anyio.sleep(0.05)
                    await store.append(
                        "run", '{"type":"text-delta","id":"text","delta":"继续"}'
                    )
                    await store.finish("run", "completed")
            assert received[0] == received[1]
            assert "继续" in str(received[0])
            assert received[0][-1] == "[DONE]"
            # TTL 到期只影响恢复流，详情将退回官方 SQLite 历史。
            for key in (
                store.pointer("conversation"),
                store.metadata("run"),
                store.stream("run"),
            ):
                await redis.expire(key, 0)
            assert await store.snapshot("conversation") is None

    asyncio.run(check())


def test_live_redis_streams(request):
    """显式开启；只创建 UUID 隔离键，不清空或扫描用户 Redis。"""
    from uuid import uuid4

    import pytest
    from redis.asyncio import ConnectionPool, Redis

    url = request.config.getoption("--redis-url")
    if url is None:
        pytest.skip("通过 --redis-url 显式启用真实 Redis 联调")

    async def check():
        pool = ConnectionPool.from_url(url, decode_responses=True, protocol=2)
        async with Redis.from_pool(pool) as redis:
            assert await redis.ping()
            store = ReplyStore(
                redis, retention_seconds=60, prefix=f"travel-agent:test:{uuid4()}"
            )
            try:
                await store.begin("conversation", "run", [])
                first = await store.append("run", '{"type":"start","messageId":"run"}')
                checkpoint = await store.snapshot("conversation")
                assert checkpoint["cursor"] == first
                received = [[], []]

                async def subscribe(index):
                    async for chunk in store.events("run", first):
                        received[index].append(chunk.encode(6))

                with anyio.fail_after(5):
                    async with anyio.create_task_group() as tasks:
                        tasks.start_soon(subscribe, 0)
                        tasks.start_soon(subscribe, 1)
                        await anyio.sleep(0.05)
                        await store.append(
                            "run",
                            '{"type":"text-delta","id":"text","delta":"真实 Redis"}',
                        )
                        await store.finish("run", "completed")
                assert received[0] == received[1]
                assert "真实 Redis" in str(received[0])
                assert received[0][-1] == "[DONE]"
                assert 0 < await redis.ttl(store.stream("run")) <= 60
                final = await store.snapshot("conversation")
                assert final["outcome"] == "completed"
                assert len(final["events"]) == 2
                tail = [c async for c in store.events("run", final["cursor"])]
                assert len(tail) == 1 and isinstance(tail[0], DoneChunk)
            finally:
                await store.delete("conversation")
            assert not await redis.exists(
                store.pointer("conversation"),
                store.metadata("run"),
                store.stream("run"),
            )

    asyncio.run(check())
