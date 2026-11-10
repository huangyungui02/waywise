"""FastAPI 会话接口，使用官方存储和 Vercel AI 流协议。"""

from contextlib import asynccontextmanager
from typing import Any, cast

import logfire
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic_ai import Agent
from redis.asyncio import Redis
from redis_fastapi import StreamBackend
from redis_fastapi.config import get_settings as redis_settings
from redis_fastapi.exceptions import StreamError
from redis_fastapi.streams import check_stream_settings, stream_error_handler

from app.agent import create_agent
from app.db.travel import TravelStore
from app.replies import Replies
from app.routes import chat, conversations
from app.settings import ROOT, Settings


def create_app() -> FastAPI:
    settings = Settings()
    database = settings.database_path
    database.parent.mkdir(parents=True, exist_ok=True)
    store = TravelStore(database=database)
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
        store=store,
        redis=redis,
        streams=streams,
        max_concurrent_runs=settings.max_concurrent_runs,
    )

    @asynccontextmanager
    async def lifespan(api: FastAPI):
        async with redis, store:
            await redis.ping()
            await streams.detect()
            await store.conversations.recover_interrupted_runs()
            api.state.replies = replies
            api.state.store = store
            try:
                yield
            finally:
                await streams.aclose()

    api = FastAPI(title="知途 · Waywise", lifespan=lifespan)
    api.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_methods=["GET", "POST", "PATCH", "DELETE"],
        allow_headers=["Content-Type"],
        expose_headers=["x-vercel-ai-ui-message-stream"],
    )
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

    @api.get("/api/health")
    async def health():
        return {"status": "ok"}

    api.include_router(conversations.router)
    api.include_router(chat.router)

    # 开发时 Vite 代理 /api；构建后由同一个 FastAPI 服务托管静态页面。
    dist = ROOT / "frontend" / "build"
    if dist.is_dir():
        api.mount("/_app", StaticFiles(directory=dist / "_app"), name="assets")

        @api.get("/{path:path}", include_in_schema=False)
        async def frontend(path: str):
            if path.startswith("api/"):
                raise HTTPException(404)
            return FileResponse(dist / "index.html")

    return api
