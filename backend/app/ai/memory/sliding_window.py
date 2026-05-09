"""Sliding-window conversational memory backed by PostgreSQL.

The last N messages of a thread are loaded fresh from the database on every
request (per AD-05) and exposed as a LangChain ``ChatMessageHistory`` so chains
receive them as ``BaseMessage`` instances via the prompt's ``history``
placeholder.
"""

from __future__ import annotations

from langchain_core.chat_history import InMemoryChatMessageHistory
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage
from sqlalchemy import desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.message import Message

DEFAULT_WINDOW_SIZE = 5


async def count_thread_messages(
    db: AsyncSession,
    thread_id: str,
    user_email: str,
) -> int:
    """Return the total number of messages in ``thread_id`` for ``user_email``."""
    result = await db.execute(
        select(func.count(Message.id)).where(
            Message.thread_id == str(thread_id),
            Message.user_email == user_email,
        )
    )
    return int(result.scalar_one() or 0)


async def fetch_recent_messages(
    db: AsyncSession,
    thread_id: str,
    user_email: str,
    limit: int = DEFAULT_WINDOW_SIZE,
) -> list[Message]:
    """Return the ``limit`` most recent messages for ``thread_id`` owned by ``user_email``.

    The query orders by ``created_at DESC`` with ``LIMIT`` so the database does
    the trimming, then the result is reversed in Python so the caller gets the
    rows in chronological (oldest → newest) order — the order the LLM prompt
    template expects.

    Filtering on ``user_email`` in addition to ``thread_id`` enforces ownership
    at the query layer; a thread belonging to another user returns an empty
    list rather than leaking history.
    """
    result = await db.execute(
        select(Message)
        .where(
            Message.thread_id == str(thread_id),
            Message.user_email == user_email,
        )
        # Include id as a tiebreaker for deterministic ordering when messages
        # share the same timestamp resolution.
        .order_by(desc(Message.created_at), desc(Message.id))
        .limit(limit)
    )
    rows = list(result.scalars().all())
    rows.reverse()
    return rows


async def fetch_recent_user_messages(
    db: AsyncSession,
    thread_id: str,
    user_email: str,
    limit: int = DEFAULT_WINDOW_SIZE,
) -> list[Message]:
    """Return the most recent user-authored messages for a thread in chronological order.

    This preserves the last N facts or instructions the user explicitly provided,
    instead of allowing assistant replies to consume the whole window.
    """
    result = await db.execute(
        select(Message)
        .where(
            Message.thread_id == str(thread_id),
            Message.user_email == user_email,
            Message.role == "user",
        )
        .order_by(desc(Message.created_at), desc(Message.id))
        .limit(limit)
    )
    rows = list(result.scalars().all())
    rows.reverse()
    return rows


async def load_window_history(
    db: AsyncSession,
    thread_id: str,
    user_email: str,
    window_size: int = DEFAULT_WINDOW_SIZE,
) -> InMemoryChatMessageHistory:
    """Return an ``InMemoryChatMessageHistory`` with the most recent ``window_size`` messages.

    Wraps :func:`fetch_recent_messages` and converts each row into the matching
    LangChain ``BaseMessage`` subclass so the result can be dropped straight
    into a prompt template's ``history`` placeholder.
    """
    rows = await fetch_recent_messages(
        db, thread_id, user_email, limit=window_size
    )
    history = InMemoryChatMessageHistory()
    for row in rows:
        history.add_message(_to_lc_message(row.role, row.content))
    return history


def _to_lc_message(role: str, content: str) -> BaseMessage:
    if role == "user":
        return HumanMessage(content=content)
    if role == "assistant":
        return AIMessage(content=content)
    return SystemMessage(content=content)
