"""离线业务测试的 SDK 边界替身；真实 Redis 协议由显式联调覆盖。"""

import asyncio
import json
from types import SimpleNamespace
from uuid import uuid4

from redis_fastapi import StreamEvent
from redis_fastapi.exceptions import StreamCursorAhead, StreamNotFound


class LocalStreams:
    def __init__(self, client):
        self.client = client
        self.tasks = set()

    async def detect(self):
        return True

    def key(self, scope, stream_id):
        return f"test-stream:{scope}:{stream_id}"

    async def open(self, *, scope, stream_id=None):
        stream_id = stream_id or uuid4().hex
        key = self.key(scope, stream_id)
        client = self.client()
        await client.rpush(key, "null")

        async def append(type, data, final=False):
            index = await client.rpush(
                key, json.dumps({"type": type, "data": data, "final": final})
            )
            return f"{index}-0"

        async def finish(type, data=None):
            writer.finished = True
            return await append(type, data, True)

        writer = SimpleNamespace(
            stream_id=stream_id,
            scope=scope,
            append=append,
            finish=finish,
            finished=False,
        )
        return writer

    def spawn(self, writer, fn):
        async def run():
            try:
                await fn(writer)
            except asyncio.CancelledError:
                await writer.finish("stream.end", {"reason": "cancelled"})
            finally:
                if not writer.finished:
                    await writer.finish("stream.end", {"reason": "done"})

        task = asyncio.create_task(run())
        self.tasks.add(task)
        task.add_done_callback(self.tasks.discard)
        return task

    async def follow(self, stream_id, *, scope, after="0-0"):
        client = self.client()
        key = self.key(scope, stream_id)
        count = await client.llen(key)
        if not count:
            raise StreamNotFound("missing")
        index = int(after.split("-")[0])
        if index > count:
            raise StreamCursorAhead("ahead")
        reader = LocalReader(client, key, index)
        if index:
            previous = json.loads(await client.lindex(key, index - 1))
            reader.ended = bool(previous and previous["final"])
        return reader

    async def aclose(self):
        tasks = list(self.tasks)
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks)


class LocalReader:
    def __init__(self, client, key, index):
        self.client, self.key, self.index = client, key, index
        self.ended = False

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        await self.aclose()

    async def aclose(self):
        self.ended = True

    def __aiter__(self):
        return self

    async def __anext__(self):
        while not self.ended:
            raw = await self.client.lindex(self.key, self.index)
            if raw is None:
                await asyncio.sleep(0.01)
                continue
            self.index += 1
            data = json.loads(raw)
            if data is None:
                continue
            self.ended = data["final"]
            return StreamEvent(id=f"{self.index}-0", **data)
        raise StopAsyncIteration
