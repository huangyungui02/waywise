"""Redis Streams 保存临时输出，官方适配器负责协议，内存只管理执行。"""

import json
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from uuid import uuid4
from typing import cast

import anyio
from pydantic_ai import CancellationToken
from pydantic_ai.ui.vercel_ai import VercelAIAdapter
from pydantic_ai.ui.vercel_ai.response_types import BaseChunk, DataChunk, DoneChunk
from redis.asyncio import Redis
from redis.exceptions import WatchError

from trip import Trip, TripStore


class RecordedChunk(BaseChunk):
    """复用官方编码保存的事件，不重新实现协议转换。"""

    encoded: str

    def encode(self, sdk_version: int) -> str:
        return self.encoded


@dataclass
class ReplyStore:
    redis: Redis
    retention_seconds: int = 86400
    prefix: str = "travel-agent:replies"

    def pointer(self, conversation_id: str) -> str:
        return f"{self.prefix}:conversation:{conversation_id}"

    def metadata(self, run_id: str) -> str:
        return f"{self.prefix}:run:{run_id}"

    def stream(self, run_id: str) -> str:
        return f"{self.prefix}:run:{run_id}:events"

    async def begin(self, conversation_id: str, run_id: str, messages: list[dict]):
        pointer = self.pointer(conversation_id)
        previous = cast(str | None, await self.redis.get(pointer))
        async with self.redis.pipeline(transaction=True) as pipe:
            if previous:
                pipe.delete(self.metadata(previous), self.stream(previous))
            pipe.set(pointer, run_id)
            pipe.hset(
                self.metadata(run_id),
                mapping={
                    "conversation_id": conversation_id,
                    "outcome": "running",
                    "messages": json.dumps(messages, ensure_ascii=False),
                },
            )
            await pipe.execute()

    async def append(self, run_id: str, event: str) -> str:
        return cast(str, await self.redis.xadd(self.stream(run_id), {"event": event}))

    async def finish(self, run_id: str, outcome: str):
        conversation_id = cast(
            str | None, await self.redis.hget(self.metadata(run_id), "conversation_id")
        )
        if conversation_id is None:
            return
        async with self.redis.pipeline(transaction=True) as pipe:
            pipe.hset(self.metadata(run_id), "outcome", outcome)
            # 结束标记也进入 Stream，唤醒所有独立订阅者。
            pipe.xadd(self.stream(run_id), {"outcome": outcome})
            for key in (
                self.pointer(conversation_id),
                self.metadata(run_id),
                self.stream(run_id),
            ):
                pipe.expire(key, self.retention_seconds)
            await pipe.execute()

    async def snapshot(self, conversation_id: str):
        pointer = self.pointer(conversation_id)
        async with self.redis.pipeline(transaction=True) as pipe:
            while True:
                try:
                    # WATCH 保证读取期间指针未被下一轮运行替换或过期。
                    await pipe.watch(pointer)
                    run_id = cast(str | None, await pipe.get(pointer))
                    if run_id is None:
                        await pipe.unwatch()
                        return None
                    pipe.multi()
                    pipe.hgetall(self.metadata(run_id))
                    pipe.xrange(self.stream(run_id))
                    metadata, rows = await pipe.execute()
                    if not metadata:
                        return None
                    return {
                        "run_id": run_id,
                        "messages": json.loads(metadata["messages"]),
                        "outcome": metadata["outcome"],
                        "cursor": rows[-1][0] if rows else "0-0",
                        "events": [
                            json.loads(fields["event"])
                            for _, fields in rows
                            if "event" in fields
                        ],
                    }
                except WatchError:
                    continue

    async def events(self, run_id: str, after: str = "0-0") -> AsyncIterator[BaseChunk]:
        while True:
            outcome = await self.redis.hget(self.metadata(run_id), "outcome")
            rows = cast(
                list[tuple[str, list[tuple[str, dict[str, str]]]]],
                await self.redis.xread(
                    {self.stream(run_id): after},
                    count=256,
                    block=1000 if outcome == "running" else None,
                ),
            )
            for _, entries in rows:
                for cursor, fields in entries:
                    if "outcome" in fields:
                        yield DoneChunk()
                        return
                    yield RecordedChunk(encoded=fields["event"])
                    yield DataChunk(
                        type="data-progress",
                        data={"runId": run_id, "cursor": cursor},
                        transient=True,
                    )
                    after = cursor
            if not rows and outcome != "running":
                yield DoneChunk()
                return

    async def delete(self, conversation_id: str):
        pointer = self.pointer(conversation_id)
        run_id = cast(str | None, await self.redis.get(pointer))
        async with self.redis.pipeline(transaction=True) as pipe:
            pipe.delete(pointer)
            if run_id:
                pipe.delete(self.metadata(run_id), self.stream(run_id))
            await pipe.execute()

    async def interrupt(self, conversation_id: str):
        run_id = cast(str | None, await self.redis.get(self.pointer(conversation_id)))
        if (
            run_id
            and await self.redis.hget(self.metadata(run_id), "outcome") == "running"
        ):
            await self.finish(run_id, "cancelled")


@dataclass
class RunningReply:
    adapter: VercelAIAdapter[TripStore, str | Trip]
    store: ReplyStore
    run_id: str = field(default_factory=lambda: str(uuid4()))
    cancellation: CancellationToken = field(default_factory=CancellationToken)
    ready: anyio.Event = field(default_factory=anyio.Event)
    finished: anyio.Event = field(default_factory=anyio.Event)

    async def append(self, chunk: BaseChunk) -> None:
        if not isinstance(chunk, DoneChunk):
            await self.store.append(self.run_id, chunk.encode(6))

    def finish(self) -> None:
        self.ready.set()
        self.finished.set()

    def response(self, after: str = "0-0"):
        response = self.adapter.streaming_response(
            self.store.events(self.run_id, after)
        )
        response.headers["Cache-Control"] = "no-store"
        response.headers["X-Accel-Buffering"] = "no"
        return response
