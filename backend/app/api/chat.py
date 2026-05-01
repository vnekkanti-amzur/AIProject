from collections.abc import AsyncIterator

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.db.session import get_db
from app.schemas.chat import ChatRequest
from app.services import chat_service

router = APIRouter()


async def _sse_stream(payload: ChatRequest, user_email: str, db: AsyncSession) -> AsyncIterator[str]:
    """Wrap model tokens into SSE frames for incremental browser delivery."""
    async for token in chat_service.stream_response(
        payload.message,
        [],
        user_email,
        db,
        payload.thread_id,
    ):
        text = str(token).replace("\r", "")
        # SSE requires each newline to be sent as its own data line.
        lines = text.split("\n")
        yield "".join(f"data: {line}\n" for line in lines) + "\n"

    yield "event: done\ndata: [DONE]\n\n"


@router.post("/chat")
async def chat(
    payload: ChatRequest,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> StreamingResponse:
    return StreamingResponse(
        _sse_stream(payload, current_user["email"], db),
        media_type="text/event-stream",
    )
