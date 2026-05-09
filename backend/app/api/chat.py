from collections.abc import AsyncIterator

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.db.session import get_db
from app.schemas.chat import ChatRequest, UploadedFileResponse
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
        [item.stored_name for item in payload.attachments],
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


@router.post("/chat/uploads", response_model=list[UploadedFileResponse], status_code=status.HTTP_201_CREATED)
async def upload_chat_files(
    files: list[UploadFile] = File(...),
    current_user: dict = Depends(get_current_user),
) -> list[UploadedFileResponse]:
    uploads: list[chat_service.IncomingUpload] = []
    for file in files:
        content = await file.read()
        uploads.append(
            chat_service.IncomingUpload(
                original_name=file.filename or "file",
                content_type=file.content_type,
                content=content,
            )
        )

    try:
        stored = await chat_service.store_uploads(uploads, current_user["email"])
    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail={"error": "invalid_upload", "message": str(exc)},
        ) from exc

    return [
        UploadedFileResponse(
            original_name=item.original_name,
            stored_name=item.stored_name,
            content_type=item.content_type,
            size_bytes=item.size_bytes,
            category=item.category,
        )
        for item in stored
    ]
