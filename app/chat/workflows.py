"""一轮旅行咨询由 DBOS 工作流持有，HTTP 请求只提交和订阅。"""

from uuid import uuid4

import logfire
from dbos import (
    DBOS,
    DBOSConfiguredInstance,
    PropagateOtelContext,
    SetEnqueueOptions,
    SetWorkflowID,
    error,
)
from fastapi import HTTPException
from pydantic_ai import Agent
from pydantic_ai.messages import ModelMessage
from pydantic_ai.run import AgentRunResultEvent
from pydantic_ai.ui.vercel_ai import VercelAIAdapter
from pydantic_ai.ui.vercel_ai.request_types import SubmitMessage, TextUIPart
from pydantic_ai.usage import UsageLimits

from app.db.travel import TravelStore
from app.models.arrangements import TravelArrangements

from .streams import STREAM, partial_messages, snapshot

QUEUE = "conversations"
ACTIVE = {"ENQUEUED", "PENDING", "DELAYED", "SUSPENDED"}


@DBOS.dbos_class()
class Replies(DBOSConfiguredInstance):
    def __init__(
        self, agent: Agent[TravelStore, str | TravelArrangements], store: TravelStore
    ):
        super().__init__("travel-agent")
        self.agent = agent
        self.store = store

    async def latest(self, conversation_id: str):
        runs = await DBOS.list_workflows_async(
            workflow_id_prefix=f"{conversation_id}/reply/",
            name="Replies.execute",
            sort_desc=True,
            limit=1,
            load_output=True,
        )
        return runs[0] if runs else None

    async def outcome(self, conversation_id: str, fallback: str):
        run = await self.latest(conversation_id)
        if run is None:
            return "cancelled" if fallback == "running" else fallback
        if run.status == "SUCCESS":
            return run.output
        return {
            "ENQUEUED": "queued",
            "PENDING": "running",
            "CANCELLED": "cancelled",
        }.get(run.status, "failed")

    async def recovery(self, conversation_id: str):
        run = await self.latest(conversation_id)
        if run is None:
            return None
        baseline = await DBOS.get_event_async(
            run.workflow_id, "baseline", timeout_seconds=0
        )
        if baseline is None:
            # 尚未执行的排队回复也能立即显示用户输入。
            saved = await self.store.conversations.load(conversation_id)
            body = SubmitMessage.model_validate_json(run.input["args"][2])
            adapter = VercelAIAdapter(self.agent, body, sdk_version=6)
            baseline = self.ui_messages([*saved.messages, *adapter.messages])
        records = await snapshot(f"{run.workflow_id}/generation")
        return {
            "run_id": run.workflow_id,
            "cursor": str(len(records)) if run.status in ACTIVE else None,
            "messages": baseline,
        }

    @staticmethod
    def ui_messages(messages):
        return [
            message.model_dump(mode="json", by_alias=True, exclude_none=True)
            for message in VercelAIAdapter.dump_messages(messages, sdk_version=6)
        ]

    async def submit(self, conversation_id, operation, payload):
        try:
            with (
                PropagateOtelContext(),
                SetWorkflowID(f"{conversation_id}/{operation}/{uuid4()}"),
                SetEnqueueOptions(deduplication_id=conversation_id),
            ):
                return await DBOS.enqueue_workflow_async(
                    QUEUE, self.execute, conversation_id, operation, payload
                )
        except error.DBOSQueueDeduplicatedError:
            raise HTTPException(409, "当前会话正在处理，请稍候") from None

    async def start(self, conversation_id: str, body: SubmitMessage):
        if not body.messages or body.messages[-1].role != "user":
            raise HTTPException(422, "请发送一条文本消息")
        latest = body.messages[-1]
        texts = [part.text for part in latest.parts if isinstance(part, TextUIPart)]
        if len(texts) != len(latest.parts) or not "\n".join(texts).strip():
            raise HTTPException(422, "请发送一条非空文本消息")
        body.messages = body.messages[-1:]
        handle = await self.submit(conversation_id, "reply", body.model_dump_json())
        return handle.workflow_id

    async def stop(self, conversation_id: str):
        run = await self.latest(conversation_id)
        if run is None or run.status not in ACTIVE:
            return
        with SetWorkflowID(f"{run.workflow_id}/stop"):
            handle = await DBOS.start_workflow_async(self.cancel_reply, run.workflow_id)
        await handle.get_result()

    @DBOS.workflow()
    async def cancel_reply(self, run_id: str):
        await DBOS.send_async(run_id, True, topic="stop")
        run = await DBOS.get_workflow_status_async(run_id)
        if run.status == "ENQUEUED":
            await DBOS.resume_workflow_async(run_id)
        execution = await DBOS.get_event_async(
            run_id, "execution", timeout_seconds=3600
        )
        if execution:
            await DBOS.cancel_workflow_async(execution)
        handle = await DBOS.retrieve_workflow_async(run_id)
        await handle.get_result()

    @DBOS.step()
    async def prepare(self, conversation_id: str, payload: str):
        saved = await self.store.conversations.load(conversation_id)
        if saved is None:
            raise ValueError("会话不存在")
        body = SubmitMessage.model_validate_json(payload)
        adapter = VercelAIAdapter(self.agent, body, sdk_version=6)
        return saved.messages, adapter.messages

    @DBOS.step()
    async def save(
        self, conversation_id: str, messages: list[ModelMessage], outcome: str
    ):
        # 重读后保存：即使业务提交后进程退出、DBOS 尚未记下步骤结果，重放也不会重复追加。
        saved = await self.store.conversations.load(conversation_id)
        if saved is not None:
            await self.store.conversations.save_messages(saved, messages, outcome)

    @DBOS.step()
    async def rename_initial(self, conversation_id, incoming):
        text = "\n".join(str(p.content) for m in incoming for p in m.parts)
        await self.store.conversations.rename(conversation_id, text[:40])

    @DBOS.step()
    async def title(self, conversation_id, text):
        await self.store.conversations.generate_title(
            self.agent.model, conversation_id, text
        )

    @DBOS.step()
    async def mutate(self, conversation_id, operation, payload):
        if operation == "delete":
            await self.store.delete_conversation(conversation_id)
            return None
        try:
            result = await self.store.arrangements.confirm(conversation_id, payload)
            return result.model_dump(mode="json")
        except ValueError as exc:
            return {"error": str(exc)}

    @DBOS.workflow()
    async def generate(
        self, conversation_id: str, messages: list[ModelMessage], run_id: str
    ):
        result = await self.agent.run(
            message_history=messages,
            conversation_id=conversation_id,
            run_id=run_id,
            deps=self.store,
            usage_limits=UsageLimits(request_limit=None),
        )
        await DBOS.write_stream_async(
            STREAM, ("result", "result", AgentRunResultEvent(result))
        )
        return result.all_messages()

    @DBOS.step()
    async def partial_messages(self, execution_id: str, baseline):
        return partial_messages(await snapshot(execution_id), baseline)

    @DBOS.workflow()
    async def execute(self, conversation_id: str, operation: str, payload: str):
        if operation != "reply":
            return await self.mutate(conversation_id, operation, payload)
        try:
            history, incoming = await self.prepare(conversation_id, payload)
            messages = [*history, *incoming]
            await DBOS.set_event_async("baseline", self.ui_messages(messages))
            await self.save(conversation_id, messages, "running")
            if not history:
                await self.rename_initial(conversation_id, incoming)
        except Exception:
            await DBOS.set_event_async("execution", "")
            raise
        if await DBOS.recv_async(topic="stop", timeout_seconds=0):
            await DBOS.set_event_async("execution", "")
            await self.save(conversation_id, messages, "cancelled")
            return "cancelled"
        with PropagateOtelContext(), SetWorkflowID(f"{DBOS.workflow_id}/generation"):
            execution = await DBOS.start_workflow_async(
                self.generate, conversation_id, messages, DBOS.workflow_id
            )
        await DBOS.set_event_async("execution", execution.workflow_id)
        try:
            completed = await execution.get_result()
        except error.DBOSAwaitedWorkflowCancelledError:
            partial = await self.partial_messages(execution.workflow_id, messages)
            await self.save(conversation_id, partial, "cancelled")
            return "cancelled"
        except Exception:
            logfire.exception("旅行回复执行失败")
            partial = await self.partial_messages(execution.workflow_id, messages)
            await self.save(conversation_id, partial, "failed")
            raise
        await self.save(conversation_id, completed, "completed")
        if not history:
            text = "\n".join(str(p.content) for m in incoming for p in m.parts)
            await self.title(conversation_id, text)
        return "completed"
