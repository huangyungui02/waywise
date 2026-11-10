"""回复发送、停止与 Redis 流恢复接口。"""

from fastapi import APIRouter, HTTPException
from fastapi.responses import Response
from pydantic_ai.ui.vercel_ai import VercelAIAdapter
from pydantic_ai.ui.vercel_ai.request_types import SubmitMessage

from app.dependencies import RepliesDep, load_conversation
from app.replies import stream_response


router = APIRouter(prefix="/api/conversations")


@router.get("/{conversation_id}/chat/stream")
async def resume_chat(
    replies: RepliesDep,
    conversation_id: str,
    run_id: str | None = None,
    after: str = "0-0",
):
    await load_conversation(conversation_id, replies)
    checkpoint = await replies.recovery(conversation_id)
    if checkpoint is None:
        if run_id is not None:
            raise HTTPException(409, "回复流已过期，请重新同步")
        return Response(status_code=204)
    if run_id is not None and checkpoint["run_id"] != run_id:
        raise HTTPException(409, "回复已更新，请重新同步")
    adapter = VercelAIAdapter(
        replies.agent, SubmitMessage(id=conversation_id, messages=[]), sdk_version=6
    )
    return await stream_response(
        adapter, replies.streams, conversation_id, checkpoint["run_id"], after
    )


@router.post("/{conversation_id}/chat/stop", status_code=204)
async def stop_chat(replies: RepliesDep, conversation_id: str):
    await load_conversation(conversation_id, replies)
    await replies.stop(conversation_id)


@router.post("/{conversation_id}/chat")
async def chat(replies: RepliesDep, conversation_id: str, body: SubmitMessage):
    await load_conversation(conversation_id, replies)
    reply = await replies.start(conversation_id, body)
    return await stream_response(
        reply.adapter, replies.streams, conversation_id, reply.run_id
    )
