from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class ThreadResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    title: str
    updated_at: datetime


class ThreadCreateRequest(BaseModel):
    title: str | None = None


class ThreadUpdateRequest(BaseModel):
    title: str


class MessageAttachments(BaseModel):
    """Attachments stored in a message (JSONB)."""
    images: list[str] | None = None


class MessageResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    role: str
    content: str
    created_at: datetime
    attachments: dict | None = None
