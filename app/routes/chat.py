"""回复发送、停止与 Redis 流恢复接口。"""

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from pydantic_ai.ui.vercel_ai import VercelAIAdapter
from pydantic_ai.ui.vercel_ai.request_types import SubmitMessage

from app.dependencies import get_replies, require_conversation
from app.replies import Replies
from app.streams import stream_response

router = APIRouter(
    prefix="/api/conversations", dependencies=[Depends(require_conversation)]
)


@router.get("/{conversation_id}/chat/stream")
async def resume_chat(
    conversation_id: str,
    replies: Replies = Depends(get_replies),
    run_id: str | None = None,
    after: str = "0-0",
):
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
async def stop_chat(conversation_id: str, replies: Replies = Depends(get_replies)):
    await replies.stop(conversation_id)


@router.post("/{conversation_id}/chat")
async def chat(
    conversation_id: str,
    body: SubmitMessage,
    replies: Replies = Depends(get_replies),
):
    reply = await replies.start(conversation_id, body)
    return await stream_response(
        reply.adapter, replies.streams, conversation_id, reply.run_id
    )
