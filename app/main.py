"""FastAPI 会话接口，使用官方存储和 Vercel AI 流协议。"""

import asyncio
from contextlib import asynccontextmanager
from typing import Any, cast

import logfire
from dbos import DBOS
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic_ai import Agent

from app.agent import create_agent
from app.chat.retention import clean_workflow_history
from app.chat.workflows import Replies
from app.db.travel import TravelStore
from app.routes import chat, conversations
from app.settings import Settings


def create_app() -> FastAPI:
    settings = Settings()

    store = TravelStore(settings.database_url.get_secret_value())
    DBOS(
        config={
            "name": "travel-agent",
            "system_database_url": (
                settings.dbos_database_url or settings.database_url
            ).get_secret_value(),
            "enable_otlp": bool(settings.logfire_token.get_secret_value()),
        }
    )
    agent = create_agent(settings)
    replies = Replies(agent=agent, store=store)

    @asynccontextmanager
    async def lifespan(api: FastAPI):
        async with store:
            DBOS.launch()
            await asyncio.to_thread(
                DBOS.apply_schedules,
                [
                    {
                        "schedule_name": "workflow-history-retention",
                        "workflow_fn": clean_workflow_history,
                        "schedule": "0 * * * *",
                        "context": settings.dbos_retention_days,
                    }
                ],
            )
            await DBOS.register_queue_async(
                "conversations",
                global_concurrency=settings.max_concurrent_runs,
                polling_interval_sec=0.1,
            )
            api.state.replies = replies
            api.state.store = store
            try:
                yield
            finally:
                await asyncio.to_thread(DBOS.destroy)

    api = FastAPI(title="知途 · Waywise", lifespan=lifespan)
    api.state.settings = settings
    api.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_methods=["GET", "POST", "PATCH", "DELETE"],
        allow_headers=["Content-Type", "Authorization"],
        expose_headers=["x-vercel-ai-ui-message-stream"],
    )

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

    return api
