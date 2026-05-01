from collections.abc import AsyncIterator
import re
import uuid

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models.message import Message
from app.models.thread import Thread
from app.services import chat_service
from app.services.thread_service import generate_title

router = APIRouter()


class SimpleChatRequest(BaseModel):
    message: str
    thread_id: str | None = None


class ThreadCreateRequest(BaseModel):
    first_message: str | None = None


class ThreadUpdateRequest(BaseModel):
    title: str


class MessageOut(BaseModel):
    id: str
    role: str
    content: str
    created_at: str

    model_config = {"from_attributes": True}


class ThreadOut(BaseModel):
    id: str
    title: str
    created_at: str
    updated_at: str


def _auto_title(first_message: str | None) -> str:
    if not first_message:
        return "New Chat"

    words = re.sub(r"\s+", " ", first_message.strip()).split(" ")
    title = " ".join(words[:6]).strip()
    if len(words) > 6:
        title += "..."
    return title[:80] or "New Chat"


async def _sse_stream(
    message: str,
    user_email: str,
    db: AsyncSession,
    thread_id: str,
    auto_title: bool,
    is_new_thread: bool,
) -> AsyncIterator[str]:
    if is_new_thread:
        yield f"event: thread\ndata: {thread_id}\n\n"

    assistant_parts: list[str] = []
    async for token in chat_service.stream_response(
        message, [], user_email, db, thread_id=thread_id
    ):
        assistant_parts.append(token)
        safe = token.replace("\r", "")
        for line in safe.split("\n"):
            yield f"data: {line}\n"
        yield "\n"

    if auto_title:
        try:
            new_title = await generate_title(message, "".join(assistant_parts), user_email)
        except Exception:
            new_title = ""
        if new_title:
            try:
                thread_uuid = uuid.UUID(thread_id)
                row = await db.scalar(
                    select(Thread).where(
                        Thread.id == thread_uuid,
                        Thread.user_email == user_email,
                    )
                )
                if row is not None:
                    row.title = new_title
                    await db.commit()
                    safe_title = new_title.replace("\r", "").replace("\n", " ")
                    yield f"event: title\ndata: {safe_title}\n\n"
            except Exception:
                pass

    yield "event: done\ndata: [DONE]\n\n"


@router.post("/simple-chat")
async def simple_chat(
    payload: SimpleChatRequest,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> StreamingResponse:
    auto_title = False
    is_new_thread = False
    if payload.thread_id is None:
        thread = Thread(
            id=uuid.uuid4(),
            user_email=current_user["email"],
            title="New Chat",
        )
        db.add(thread)
        await db.commit()
        thread_id = str(thread.id)
        auto_title = True
        is_new_thread = True
    else:
        try:
            thread_uuid = uuid.UUID(payload.thread_id)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail={"error": "bad_request", "message": "Invalid thread id"}) from exc

        thread_row = await db.scalar(
            select(Thread).where(
                Thread.id == thread_uuid,
                Thread.user_email == current_user["email"],
            )
        )
        if thread_row is None:
            raise HTTPException(status_code=404, detail={"error": "not_found", "message": "Thread not found"})
        thread_id = payload.thread_id
        # Also auto-name if existing thread still has the placeholder/auto-truncated title
        # AND has no prior assistant messages yet.
        if thread_row.title in (None, "", "New Chat"):
            auto_title = True

    return StreamingResponse(
        _sse_stream(payload.message, current_user["email"], db, thread_id, auto_title, is_new_thread),
        media_type="text/event-stream",
    )


@router.get("/simple-chat/history", response_model=list[MessageOut])
async def chat_history(
    thread_id: str,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[Message]:
    try:
        thread_uuid = uuid.UUID(thread_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail={"error": "bad_request", "message": "Invalid thread id"}) from exc

    thread_row = await db.scalar(
        select(Thread).where(Thread.id == thread_uuid, Thread.user_email == current_user["email"])
    )
    if thread_row is None:
        raise HTTPException(status_code=404, detail={"error": "not_found", "message": "Thread not found"})

    result = await db.execute(
        select(Message)
        .where(Message.user_email == current_user["email"], Message.thread_id == thread_id)
        .order_by(Message.created_at.asc())
    )
    rows = result.scalars().all()
    return [
        MessageOut(
            id=str(r.id),
            role=r.role,
            content=r.content,
            created_at=r.created_at.isoformat(),
        )
        for r in rows
    ]


@router.get("/simple-chat/threads", response_model=list[ThreadOut])
async def list_threads(
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[ThreadOut]:
    result = await db.execute(
        select(Thread)
        .where(Thread.user_email == current_user["email"])
        .order_by(Thread.updated_at.desc())
    )
    rows = result.scalars().all()
    return [
        ThreadOut(
            id=str(r.id),
            title=r.title,
            created_at=r.created_at.isoformat(),
            updated_at=r.updated_at.isoformat(),
        )
        for r in rows
    ]


@router.post("/simple-chat/threads", response_model=ThreadOut)
async def create_thread(
    payload: ThreadCreateRequest,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ThreadOut:
    thread = Thread(
        id=uuid.uuid4(),
        user_email=current_user["email"],
        title=_auto_title(payload.first_message),
    )
    db.add(thread)
    await db.commit()
    await db.refresh(thread)
    return ThreadOut(
        id=str(thread.id),
        title=thread.title,
        created_at=thread.created_at.isoformat(),
        updated_at=thread.updated_at.isoformat(),
    )


@router.patch("/simple-chat/threads/{thread_id}", response_model=ThreadOut)
async def update_thread(
    thread_id: str,
    payload: ThreadUpdateRequest,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ThreadOut:
    try:
        thread_uuid = uuid.UUID(thread_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail={"error": "bad_request", "message": "Invalid thread id"}) from exc

    thread = await db.scalar(
        select(Thread).where(Thread.id == thread_uuid, Thread.user_email == current_user["email"])
    )
    if thread is None:
        raise HTTPException(status_code=404, detail={"error": "not_found", "message": "Thread not found"})

    thread.title = payload.title.strip()[:80] or "New Chat"
    await db.commit()
    await db.refresh(thread)

    return ThreadOut(
        id=str(thread.id),
        title=thread.title,
        created_at=thread.created_at.isoformat(),
        updated_at=thread.updated_at.isoformat(),
    )


@router.delete("/simple-chat/threads/{thread_id}")
async def delete_thread(
    thread_id: str,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, str]:
    try:
        thread_uuid = uuid.UUID(thread_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail={"error": "bad_request", "message": "Invalid thread id"}) from exc

    thread = await db.scalar(
        select(Thread).where(Thread.id == thread_uuid, Thread.user_email == current_user["email"])
    )
    if thread is None:
        raise HTTPException(status_code=404, detail={"error": "not_found", "message": "Thread not found"})

    await db.execute(delete(Message).where(Message.user_email == current_user["email"], Message.thread_id == thread_id))
    await db.delete(thread)
    await db.commit()
    return {"status": "ok"}
