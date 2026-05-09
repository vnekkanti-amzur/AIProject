from uuid import UUID

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.db.session import get_db
from app.schemas.thread import (
    MessageResponse,
    ThreadCreateRequest,
    ThreadResponse,
    ThreadUpdateRequest,
)
from app.services import thread_service

router = APIRouter()


@router.get("", response_model=list[ThreadResponse])
async def list_threads(
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[ThreadResponse]:
    threads = await thread_service.list_threads(db, current_user["email"])
    return [ThreadResponse.model_validate(t) for t in threads]


@router.post("", response_model=ThreadResponse, status_code=status.HTTP_201_CREATED)
async def create_thread(
    payload: ThreadCreateRequest,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ThreadResponse:
    thread = await thread_service.create_thread(
        db, current_user["email"], payload.title
    )
    return ThreadResponse.model_validate(thread)


@router.patch("/{thread_id}", response_model=ThreadResponse)
async def update_thread(
    thread_id: UUID,
    payload: ThreadUpdateRequest,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ThreadResponse:
    thread = await thread_service.update_thread_title(
        db, current_user["email"], thread_id, payload.title
    )
    return ThreadResponse.model_validate(thread)


@router.delete("/{thread_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_thread(
    thread_id: UUID,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    await thread_service.delete_thread(db, current_user["email"], thread_id)


@router.get("/{thread_id}/messages", response_model=list[MessageResponse])
async def list_messages(
    thread_id: UUID,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[MessageResponse]:
    messages = await thread_service.list_messages(
        db, current_user["email"], thread_id
    )
    return [MessageResponse.model_validate(m) for m in messages]
