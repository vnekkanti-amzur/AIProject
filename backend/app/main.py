from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import chat, simple_chat
from app.api.router import api_router
from app.core.config import settings


app = FastAPI(title=settings.APP_NAME)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:5174"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router, prefix="/api")
app.include_router(chat.router, prefix="/api", tags=["chat"])
app.include_router(simple_chat.router, prefix="/api", tags=["simple-chat"])


@app.get("/health", tags=["health"])
async def health_check() -> dict[str, str]:
    return {"status": "ok"}
