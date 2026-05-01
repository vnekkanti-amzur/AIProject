from functools import lru_cache

from langchain_openai import ChatOpenAI

from app.core.config import settings


@lru_cache
def get_chat_llm() -> ChatOpenAI:
    """Return a singleton ChatOpenAI client routed via the Amzur LiteLLM proxy."""
    return ChatOpenAI(
        model=settings.LLM_MODEL,
        base_url=settings.LITELLM_PROXY_URL,
        api_key=settings.LITELLM_API_KEY,
        temperature=0.2,
        timeout=30,
        max_retries=2,
    )


__all__ = ["get_chat_llm"]
