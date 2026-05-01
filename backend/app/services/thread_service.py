"""Thread-related helpers: smart title generation via LLM."""
from __future__ import annotations

import re

from langchain_core.messages import HumanMessage, SystemMessage

from app.ai.llm import get_chat_llm

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
