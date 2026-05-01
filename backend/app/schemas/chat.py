from pydantic import BaseModel


class ChatRequest(BaseModel):
    thread_id: str | None = None
    message: str


class ChatResponse(BaseModel):
    thread_id: str
    message: str


# Backward-compatible aliases for existing imports.
ChatMessageRequest = ChatRequest
ChatMessageResponse = ChatResponse
