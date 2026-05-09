from pydantic import BaseModel


class ChatAttachment(BaseModel):
    stored_name: str


class MessageAttachments(BaseModel):
    """Attachments stored in a message (JSONB)."""
    images: list[str] | None = None


class ChatRequest(BaseModel):
    thread_id: str | None = None
    message: str
    attachments: list[ChatAttachment] = []


class ChatResponse(BaseModel):
    thread_id: str
    message: str


class ChatMessageDetail(BaseModel):
    """Extended message response with attachments."""
    id: str
    role: str
    content: str
    attachments: MessageAttachments | None = None
    created_at: str


class UploadedFileResponse(BaseModel):
    original_name: str
    stored_name: str
    content_type: str | None = None
    size_bytes: int
    category: str


# Backward-compatible aliases for existing imports.
ChatMessageRequest = ChatRequest
ChatMessageResponse = ChatResponse
