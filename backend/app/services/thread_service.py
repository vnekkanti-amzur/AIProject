"""Thread-related helpers: CRUD + smart title generation via LLM."""
from __future__ import annotations

import re
from uuid import UUID

from fastapi import HTTPException
from langchain_core.messages import HumanMessage, SystemMessage
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.llm import get_chat_llm
from app.models.message import Message
from app.models.thread import Thread

DEFAULT_TITLE = "New chat"


def _coerce_uuid(thread_id: str | UUID) -> UUID:
    if isinstance(thread_id, UUID):
        return thread_id
    try:
        return UUID(str(thread_id))
    except (ValueError, AttributeError) as exc:
        raise HTTPException(
            status_code=400,
            detail={"error": "invalid_thread_id", "message": "thread_id must be a UUID"},
        ) from exc


async def list_threads(db: AsyncSession, user_email: str) -> list[Thread]:
    result = await db.execute(
        select(Thread)
        .where(Thread.user_email == user_email)
        .order_by(Thread.updated_at.desc())
    )
    return list(result.scalars().all())


async def get_thread(db: AsyncSession, user_email: str, thread_id: str | UUID) -> Thread:
    tid = _coerce_uuid(thread_id)
    result = await db.execute(
        select(Thread).where(Thread.id == tid, Thread.user_email == user_email)
    )
    thread = result.scalar_one_or_none()
    if thread is None:
        raise HTTPException(
            status_code=404,
            detail={"error": "not_found", "message": "Thread not found"},
        )
    return thread


async def create_thread(
    db: AsyncSession, user_email: str, title: str | None = None
) -> Thread:
    thread = Thread(user_email=user_email, title=title or DEFAULT_TITLE)
    db.add(thread)
    await db.commit()
    await db.refresh(thread)
    return thread


async def update_thread_title(
    db: AsyncSession, user_email: str, thread_id: str | UUID, title: str
) -> Thread:
    thread = await get_thread(db, user_email, thread_id)
    thread.title = title.strip()[:255] or DEFAULT_TITLE
    await db.commit()
    await db.refresh(thread)
    return thread


async def delete_thread(
    db: AsyncSession, user_email: str, thread_id: str | UUID
) -> None:
    thread = await get_thread(db, user_email, thread_id)
    await db.execute(
        delete(Message).where(Message.thread_id == str(thread.id))
    )
    await db.delete(thread)
    await db.commit()


async def list_messages(
    db: AsyncSession, user_email: str, thread_id: str | UUID
) -> list[Message]:
    thread = await get_thread(db, user_email, thread_id)
    result = await db.execute(
        select(Message)
        .where(Message.thread_id == str(thread.id))
        .order_by(Message.created_at.asc())
    )
    return list(result.scalars().all())

_TITLE_SYSTEM = (
    "You generate ultra-short conversation titles. "
    "Given a user question and the assistant's answer, return ONLY the title. "
    "Rules: max 6 words, no quotes, no trailing punctuation, Title Case, "
    "describe the topic (not the action). Examples: 'Chicken Biryani Recipe', "
    "'Async Await In Python', 'Deploying To Production Safely'."
)


def _sanitize(raw: str) -> str:
    title = raw.strip().strip('"').strip("'")
    title = title.splitlines()[0] if title else ""
    title = re.sub(r"\s+", " ", title)
    title = title.rstrip(".!?,:;")
    return title[:80]


async def generate_title(question: str, answer: str, user_email: str) -> str:
    """Ask the LLM for a 3-6 word topic title. Returns '' on failure."""
    if not question.strip():
        return ""

    llm = get_chat_llm()
    answer_excerpt = (answer or "").strip()[:600]
    prompt = (
        f"User question:\n{question.strip()[:600]}\n\n"
        f"Assistant answer (excerpt):\n{answer_excerpt}\n\n"
        "Title:"
    )
    try:
        result = await llm.ainvoke(
            [SystemMessage(content=_TITLE_SYSTEM), HumanMessage(content=prompt)],
            config={"metadata": {"user_email": user_email, "purpose": "thread_title"}},
        )
    except Exception:
        return ""

    return _sanitize(getattr(result, "content", "") or "")
