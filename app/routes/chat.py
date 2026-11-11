"""持久回复的发送、停止和重连。"""

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from pydantic_ai.ui.vercel_ai.request_types import SubmitMessage

from app.chat.response import stream_response
from app.chat.workflows import Replies
from app.dependencies import get_replies, require_conversation

router = APIRouter(
    prefix="/api/conversations", dependencies=[Depends(require_conversation)]
)


@router.get("/{conversation_id}/chat/stream")
async def resume_chat(
    conversation_id: str,
    replies: Replies = Depends(get_replies),
    run_id: str | None = None,
):
    run = await replies.latest(conversation_id)
    if run is None:
        if run_id is not None:
            raise HTTPException(409, "回复已更新，请重新同步")
        return Response(status_code=204)
    if run_id is not None and run.workflow_id != run_id:
        raise HTTPException(409, "回复已更新，请重新同步")
    return await stream_response(run.workflow_id)


@router.post("/{conversation_id}/chat/stop", status_code=204)
async def stop_chat(conversation_id: str, replies: Replies = Depends(get_replies)):
    await replies.stop(conversation_id)


@router.post("/{conversation_id}/chat")
async def chat(
    conversation_id: str, body: SubmitMessage, replies: Replies = Depends(get_replies)
):
    run_id = await replies.start(conversation_id, body)
    return await stream_response(run_id)
