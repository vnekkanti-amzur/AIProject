from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.db.session import get_db
from app.schemas.chat import ChatMessageRequest
from app.services import chat_service

router = APIRouter()


@router.post("/stream")
async def stream_chat(
    payload: ChatMessageRequest,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> StreamingResponse:
    return StreamingResponse(
        chat_service.stream_response(
            payload.message,
            [],
            current_user["email"],
            db,
            payload.thread_id,
            [item.stored_name for item in payload.attachments],
        ),
        media_type="text/event-stream",
    )
