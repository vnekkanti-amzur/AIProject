import uuid
from collections.abc import AsyncIterator

from app.ai.chains.chat_chain import build_chat_chain
from app.models.message import Message
from sqlalchemy.ext.asyncio import AsyncSession


async def stream_response(
    message: str,
    history: list,
    user_email: str,
    db: AsyncSession,
    thread_id: str | None = None,
) -> AsyncIterator[str]:
    resolved_thread_id = thread_id or str(uuid.uuid4())

    db.add(
        Message(
            thread_id=resolved_thread_id,
            user_email=user_email,
            role="user",
            content=message,
        )
    )
    await db.commit()

    chain = build_chat_chain()
    assistant_parts: list[str] = []

    async for chunk in chain.astream(
        {"human_input": message, "history": history},
        config={"metadata": {"user_email": user_email}},
    ):
        text = str(chunk)
        assistant_parts.append(text)
        yield text

    db.add(
        Message(
            thread_id=resolved_thread_id,
            user_email=user_email,
            role="assistant",
            content="".join(assistant_parts),
        )
    )
    await db.commit()
