"""FastAPI 会话接口，使用官方存储和 Vercel AI 流协议。"""

from contextlib import asynccontextmanager
from dataclasses import asdict
from typing import Any, cast

import anyio
import logfire
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic_ai import Agent
from pydantic_ai.ui.vercel_ai import VercelAIAdapter
from pydantic_ai.ui.vercel_ai.request_types import SubmitMessage
from pydantic_ai_harness.step_persistence import SqliteStepStore
from pydantic_ai_harness.step_persistence.conversations import (
    ConversationSummary,
    SqliteConversationStore,
)
from redis.asyncio import Redis
from redis_fastapi import StreamBackend
from redis_fastapi.config import get_settings as redis_settings
from redis_fastapi.exceptions import StreamError
from redis_fastapi.streams import check_stream_settings, stream_error_handler

from agent import create_agent
from replies import Replies, stream_response
from settings import ROOT, Settings
from trip import Trip, TripStore


def create_app() -> FastAPI:
    settings = Settings()
    database = settings.database_path
    database.parent.mkdir(parents=True, exist_ok=True)
    conversations = SqliteConversationStore(database=database)
    steps = SqliteStepStore(database=database)
    trips = TripStore(database=database)
    redis = Redis.from_url(
        settings.redis_url.get_secret_value(),
        decode_responses=True,
        protocol=2,
        socket_connect_timeout=5,
        socket_timeout=redis_settings().socket_timeout,
    )
    check_stream_settings()
    streams = StreamBackend(lambda: redis)
    agent = create_agent(settings)
    replies = Replies(
        agent=agent,
        conversations=conversations,
        steps=steps,
        trips=trips,
        redis=redis,
        streams=streams,
        max_concurrent_runs=settings.max_concurrent_runs,
    )

    @asynccontextmanager
    async def lifespan(api: FastAPI):
        async with redis:
            await redis.ping()
            await streams.detect()
            await replies.recover_interrupted_runs()
            try:
                yield
            finally:
                await streams.aclose()

    api = FastAPI(title="国内旅行助手", lifespan=lifespan)
    api.add_exception_handler(StreamError, stream_error_handler)

    if token := settings.logfire_token.get_secret_value():
        telemetry = logfire.configure(
            local=True,
            token=token,
            send_to_logfire=True,
            service_name="travel-agent",
            environment=settings.logfire_environment,
            console=False,
        )
        telemetry.instrument_pydantic_ai(
            cast(Agent[Any, str], agent),
            include_content=settings.logfire_include_content,
            include_binary_content=False,
        )
        telemetry.instrument_fastapi(
            api,
            capture_headers=False,
            request_attributes_mapper=lambda request, attributes: None,
            excluded_urls=r"/api/health$|/assets/.*",
        )

    async def load(conversation_id: str):
        try:
            return await conversations.get(conversation_id=conversation_id)
        except LookupError:
            raise HTTPException(404, "会话不存在") from None

    @api.get("/api/health")
    async def health():
        return {"status": "ok"}

    @api.get("/api/conversations")
    async def list_conversations():
        return [asdict(item) for item in await conversations.listing()]

    @api.post("/api/conversations", status_code=201)
    async def new_conversation():
        summary = await conversations.save(
            summary=ConversationSummary(workspace=str(ROOT), title="新的旅行"),
            messages=[],
        )
        return asdict(summary)

    @api.get("/api/conversations/{conversation_id}")
    async def get_conversation(conversation_id: str):
        if reply := replies.running.get(conversation_id):
            await reply.ready.wait()
        saved = await load(conversation_id)
        state = await anyio.to_thread.run_sync(trips.get_state, conversation_id)
        checkpoint = await replies.recovery(conversation_id)
        return {
            "recovery": checkpoint,
            "summary": asdict(saved.summary),
            "messages": [
                m.model_dump(mode="json", by_alias=True, exclude_none=True)
                for m in VercelAIAdapter.dump_messages(saved.messages, sdk_version=6)
            ],
            **{
                key: value.model_dump(mode="json") if isinstance(value, Trip) else value
                for key, value in state.items()
            },
        }

    @api.post("/api/conversations/{conversation_id}/proposals/{proposal_id}/confirm")
    async def confirm_proposal(conversation_id: str, proposal_id: str):
        await load(conversation_id)
        if conversation_id in replies.busy:
            raise HTTPException(409, "请等待当前回复结束后确认")
        replies.busy.add(conversation_id)
        try:
            trip = await anyio.to_thread.run_sync(
                trips.confirm, conversation_id, proposal_id
            )
        except ValueError as error:
            raise HTTPException(409, str(error)) from None
        finally:
            replies.busy.discard(conversation_id)
        return trip.model_dump(mode="json")

    @api.delete("/api/conversations/{conversation_id}", status_code=204)
    async def delete_conversation(conversation_id: str):
        saved = await load(conversation_id)
        if conversation_id in replies.busy:
            raise HTTPException(409, "请先停止当前回复，再删除会话")
        replies.busy.add(conversation_id)
        try:
            await conversations.delete(source=saved.summary)
            await anyio.to_thread.run_sync(trips.delete, conversation_id)
            await redis.delete(replies.recovery_key(conversation_id))
        finally:
            replies.busy.discard(conversation_id)

    @api.get("/api/conversations/{conversation_id}/chat/stream")
    async def resume_chat(
        conversation_id: str,
        run_id: str | None = None,
        after: str = "0-0",
    ):
        await load(conversation_id)
        checkpoint = await replies.recovery(conversation_id)
        if checkpoint is None:
            if run_id is not None:
                raise HTTPException(409, "回复流已过期，请重新同步")
            return Response(status_code=204)
        if run_id is not None and checkpoint["run_id"] != run_id:
            raise HTTPException(409, "回复已更新，请重新同步")
        adapter = VercelAIAdapter(
            agent, SubmitMessage(id=conversation_id, messages=[]), sdk_version=6
        )
        return await stream_response(
            adapter, streams, conversation_id, checkpoint["run_id"], after
        )

    @api.post("/api/conversations/{conversation_id}/chat/stop", status_code=204)
    async def stop_chat(conversation_id: str):
        await load(conversation_id)
        await replies.stop(conversation_id)

    @api.post("/api/conversations/{conversation_id}/chat")
    async def chat(conversation_id: str, body: SubmitMessage):
        await load(conversation_id)
        reply = await replies.start(conversation_id, body)
        return await stream_response(
            reply.adapter, streams, conversation_id, reply.run_id
        )

    # 开发时 Vite 代理 /api；构建后由同一个 FastAPI 服务托管静态页面。
    dist = ROOT / "frontend" / "dist"
    if dist.is_dir():
        api.mount("/assets", StaticFiles(directory=dist / "assets"), name="assets")

        @api.get("/{path:path}", include_in_schema=False)
        async def frontend(path: str):
            if path.startswith("api/"):
                raise HTTPException(404)
            return FileResponse(dist / "index.html")

    return api
