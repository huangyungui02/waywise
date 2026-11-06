"""FastAPI 会话接口，使用官方存储和 Vercel AI 流协议。"""

from dataclasses import asdict, replace
from uuid import uuid4

import anyio
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic_ai import Agent, RunContext
from pydantic_ai.capabilities import Hooks
from pydantic_ai.ui.vercel_ai import VercelAIAdapter
from pydantic_ai.ui.vercel_ai.request_types import SubmitMessage, TextUIPart
from pydantic_ai.usage import UsageLimits
from pydantic_ai_harness import StepPersistence
from pydantic_ai_harness.step_persistence import SqliteStepStore
from pydantic_ai_harness.step_persistence.conversations import (
    ConversationSummary,
    SqliteConversationStore,
)
from starlette.background import BackgroundTask

from agent import create_agent
from settings import ROOT, Settings
from trip import TripStore


def create_app(
    settings: Settings | None = None, agent: Agent[TripStore, str] | None = None
) -> FastAPI:
    settings = settings or Settings()
    database = settings.database_path
    database.parent.mkdir(parents=True, exist_ok=True)
    conversations = SqliteConversationStore(database=database)
    steps = SqliteStepStore(database=database)
    trips = TripStore(database=database)
    agent = agent or create_agent(settings)
    busy: set[str] = set()
    api = FastAPI(title="国内旅行助手")

    async def load(conversation_id: str):
        try:
            saved = await conversations.get(conversation_id=conversation_id)
        except LookupError:
            raise HTTPException(404, "会话不存在") from None
        if saved.summary.outcome == "running" and conversation_id not in busy:
            runs = await steps.list_runs(conversation_id=conversation_id)
            snapshot = (
                await steps.latest_snapshot(
                    run_id=max(runs, key=lambda r: r.started_at).run_id
                )
                if runs
                else None
            )
            await conversations.save(
                summary=replace(saved.summary, outcome="cancelled"),
                messages=snapshot.messages if snapshot else saved.messages,
            )
            saved = await conversations.get(conversation_id=conversation_id)
        return saved

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
        saved = await load(conversation_id)
        trip = await anyio.to_thread.run_sync(trips.get, conversation_id)
        return {
            "summary": asdict(saved.summary),
            "messages": [
                m.model_dump(mode="json", by_alias=True, exclude_none=True)
                for m in VercelAIAdapter.dump_messages(saved.messages, sdk_version=6)
            ],
            "trip": trip.model_dump(mode="json") if trip else None,
        }

    @api.delete("/api/conversations/{conversation_id}", status_code=204)
    async def delete_conversation(conversation_id: str):
        if conversation_id in busy:
            raise HTTPException(409, "请先停止当前回复，再删除会话")
        saved = await load(conversation_id)
        await conversations.delete(source=saved.summary)
        await anyio.to_thread.run_sync(trips.delete, conversation_id)

    @api.post("/api/conversations/{conversation_id}/chat")
    async def chat(conversation_id: str, body: SubmitMessage):
        saved = await load(conversation_id)
        if conversation_id in busy:
            raise HTTPException(409, "当前会话正在回复，请稍候")
        if not body.messages or body.messages[-1].role != "user":
            raise HTTPException(422, "请发送一条文本消息")
        latest = body.messages[-1]
        texts = [part.text for part in latest.parts if isinstance(part, TextUIPart)]
        text = "\n".join(texts).strip()
        if len(texts) != len(latest.parts) or not text:
            raise HTTPException(422, "请发送一条非空文本消息")
        # FastAPI 校验协议请求；官方适配器负责消息转换和服务端历史合并。
        body.messages = [latest]
        adapter = VercelAIAdapter(
            agent, body, sdk_version=6, manage_message_history="server"
        )
        busy.add(conversation_id)
        try:
            if not saved.messages:
                await conversations.name(
                    source=saved.summary, title=text[:40], manual=True
                )
                saved = await load(conversation_id)
            messages = [*saved.messages, *adapter.messages]
            summary = await conversations.save(
                summary=replace(saved.summary, outcome="running"),
                messages=messages,
            )
        except BaseException:
            busy.discard(conversation_id)
            raise

        run_id = str(uuid4())
        hooks = Hooks()

        @hooks.on.run
        async def persist_run(ctx: RunContext[TripStore], *, handler):
            try:
                result = await handler()
            except BaseException:
                # 包括浏览器断连；只恢复最后一个完整步骤，不重放未完成的工具。
                with anyio.CancelScope(shield=True):
                    snapshot = await steps.latest_snapshot(run_id=run_id)
                    await conversations.save(
                        summary=replace(summary, outcome="cancelled"),
                        messages=snapshot.messages if snapshot else messages,
                    )
                raise
            else:
                with anyio.CancelScope(shield=True):
                    await conversations.save(
                        summary=replace(summary, outcome="completed"),
                        messages=result.all_messages(),
                    )
                return result
            finally:
                busy.discard(conversation_id)

        response = adapter.streaming_response(
            adapter.run_stream(
                message_history=saved.messages,
                conversation_id=conversation_id,
                run_id=run_id,
                deps=trips,
                usage_limits=UsageLimits(request_limit=None),
                capabilities=[hooks, StepPersistence(store=steps)],
            )
        )
        # 覆盖运行建立前失败的情况；不自行包装或消费事件流。
        response.background = BackgroundTask(busy.discard, conversation_id)
        return response

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
