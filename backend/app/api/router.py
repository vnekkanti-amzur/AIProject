from fastapi import APIRouter

from app.api.routes import auth, chat, health, threads


api_router = APIRouter()
api_router.include_router(health.router, prefix="/health", tags=["health"])
api_router.include_router(auth.router, prefix="/auth", tags=["auth"])
api_router.include_router(chat.router, prefix="/chat", tags=["chat"])
api_router.include_router(threads.router, prefix="/threads", tags=["threads"])
