"""回复启动、停止、并发限制与单轮执行；后台任务由 Redis SDK 持有。"""

import asyncio
import json
from dataclasses import dataclass, field
from functools import partial
from uuid import uuid4

import anyio
import logfire
from fastapi import HTTPException
from pydantic_ai import Agent, AgentRunResult, CancellationToken, Conversation
from pydantic_ai.exceptions import RunCancelled
from pydantic_ai.messages import ModelMessage
from pydantic_ai.ui.vercel_ai import VercelAIAdapter
from pydantic_ai.ui.vercel_ai.request_types import SubmitMessage, TextUIPart
from pydantic_ai.ui.vercel_ai.response_types import DoneChunk
from pydantic_ai.usage import UsageLimits
from redis.asyncio import Redis
from redis_fastapi import StreamBackend, StreamWriter
from redis_fastapi.config import get_settings as redis_settings
from redis_fastapi.exceptions import StreamNotFound

from app.db.travel import TravelStore
from app.models.arrangements import TravelArrangements


@dataclass
class RunningReply:
    adapter: VercelAIAdapter[TravelStore, str | TravelArrangements]
    run_id: str = field(default_factory=lambda: str(uuid4()))
    cursor: str = "0-0"
    cancellation: CancellationToken = field(default_factory=CancellationToken)
    ready: anyio.Event = field(default_factory=anyio.Event)
    task: asyncio.Task | None = None


@dataclass
class Replies:
    agent: Agent[TravelStore, str | TravelArrangements]
    store: TravelStore
    redis: Redis
    streams: StreamBackend
    max_concurrent_runs: int
    busy: set[str] = field(default_factory=set, init=False)
    running: dict[str, RunningReply] = field(default_factory=dict, init=False)

    @staticmethod
    def recovery_key(conversation_id: str) -> str:
        return f"travel-agent:recovery:{conversation_id}"

    async def recovery(self, conversation_id: str):
        data = await self.redis.get(self.recovery_key(conversation_id))
        if data is None:
            return None
        saved = json.loads(data)
        try:
            reader = await self.streams.follow(saved["run_id"], scope=conversation_id)
            await reader.aclose()
        except StreamNotFound:
            return None
        reply = self.running.get(conversation_id)
        return {**saved, "cursor": reply.cursor if reply else None}

    @staticmethod
    def _user_text(body: SubmitMessage) -> str:
        if not body.messages or body.messages[-1].role != "user":
            raise HTTPException(422, "请发送一条文本消息")
        latest = body.messages[-1]
        texts = [part.text for part in latest.parts if isinstance(part, TextUIPart)]
        text = "\n".join(texts).strip()
        if len(texts) != len(latest.parts) or not text:
            raise HTTPException(422, "请发送一条非空文本消息")
        return text

    async def start(self, conversation_id: str, body: SubmitMessage) -> RunningReply:
        if conversation_id in self.busy:
            raise HTTPException(409, "当前会话正在回复，请稍候")
        if len(self.running) >= self.max_concurrent_runs:
            raise HTTPException(429, "同时进行的旅行咨询较多，请稍后再试")
        text = self._user_text(body)
        # 只接受本轮用户消息，历史由服务端和官方适配器合并。
        body.messages = body.messages[-1:]
        adapter = VercelAIAdapter(
            self.agent, body, sdk_version=6, manage_message_history="server"
        )
        reply = RunningReply(adapter)
        adapter.server_message_id = reply.run_id
        self.busy.add(conversation_id)
        self.running[conversation_id] = reply
        try:
            # 取得执行名额后重读，避免等待 SQLite 时上一轮刚好完成而使用旧历史。
            saved = await self.store.conversations.load(conversation_id)
            if saved is None:
                raise HTTPException(404, "会话不存在")
            if not saved.messages:
                await self.store.conversations.rename(conversation_id, text[:40])
            history = list(saved.messages)
            messages = [*history, *adapter.messages]
            writer = await self.streams.open(
                scope=conversation_id, stream_id=reply.run_id
            )
            await self.store.conversations.save_messages(saved, messages, "running")
            await self.redis.set(
                self.recovery_key(conversation_id),
                json.dumps(
                    {
                        "run_id": reply.run_id,
                        "messages": [
                            m.model_dump(mode="json", by_alias=True, exclude_none=True)
                            for m in VercelAIAdapter.dump_messages(
                                messages, sdk_version=6
                            )
                        ],
                    },
                    ensure_ascii=False,
                ),
                ex=redis_settings().stream_max_run,
            )
            execution = _ReplyExecution(
                reply=reply,
                store=self.store,
                conversation=saved,
                messages=messages,
                history=history,
                first_message=text if not history else None,
            )
            reply.task = self.streams.spawn(
                writer, partial(self._produce, execution=execution)
            )
        except BaseException:
            self._release(conversation_id, reply)
            raise
        reply.ready.set()
        return reply

    async def stop(self, conversation_id: str):
        if reply := self.running.get(conversation_id):
            reply.cancellation.cancel()
            if reply.task is not None:
                await reply.task

    def _release(self, conversation_id: str, reply: RunningReply):
        self.running.pop(conversation_id, None)
        self.busy.discard(conversation_id)
        reply.ready.set()

    async def _produce(self, writer: StreamWriter, *, execution: "_ReplyExecution"):
        try:
            outcome = await execution.produce(writer)
        finally:
            self._release(execution.conversation.conversation_id, execution.reply)
        await writer.finish("result", {"outcome": outcome})

    async def clear_recovery(self, conversation_id: str):
        await self.redis.delete(self.recovery_key(conversation_id))


@dataclass
class _ReplyExecution:
    """一轮回复的历史、保存结果和官方适配器回调。"""

    reply: RunningReply
    store: TravelStore
    conversation: Conversation
    messages: list[ModelMessage]
    history: list[ModelMessage]
    first_message: str | None
    outcome: str | None = field(default=None, init=False)

    async def _save(self, outcome: str, messages: list[ModelMessage]):
        await self.store.conversations.save_messages(
            self.conversation, messages, outcome
        )
        self.outcome = outcome

    async def completed(self, result: AgentRunResult):
        await self._save("completed", result.all_messages())
        if self.first_message is not None:
            model = self.reply.adapter.agent.model
            assert model is not None
            await self.store.conversations.generate_title(
                model, self.conversation.conversation_id, self.first_message
            )

    async def cancelled(self, result: RunCancelled):
        await self._save("cancelled", result.all_messages())

    async def produce(self, writer: StreamWriter):
        interrupted = False
        try:
            async for chunk in self.reply.adapter.run_stream(
                message_history=self.history,
                conversation_id=self.conversation.conversation_id,
                run_id=self.reply.run_id,
                deps=self.store,
                usage_limits=UsageLimits(request_limit=None),
                cancellation_token=self.reply.cancellation,
                on_complete=self.completed,
                on_cancel=self.cancelled,
            ):
                if not isinstance(chunk, DoneChunk):
                    self.reply.cursor = await writer.append("ui", chunk.encode(6))
        except anyio.get_cancelled_exc_class():
            interrupted = True
            raise
        except Exception:  # noqa: BLE001 — 后台任务统一记录失败并保存本轮状态。
            logfire.exception("后台回复执行失败")
        finally:
            with anyio.CancelScope(shield=True):
                if self.outcome is None:
                    await self._save(
                        "cancelled" if interrupted else "failed", self.messages
                    )
        return self.outcome
