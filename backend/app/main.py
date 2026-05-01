from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

from app.api import chat, simple_chat
from app.api.router import api_router
from app.core.config import settings
from app.db.session import engine


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Pre-warm the DB connection pool so the first request doesn't pay for
    # cold-start DNS / TLS handshake (which has been flaky on Win + Py 3.14).
    try:
        async with engine.connect() as conn:
            await conn.execute(text("select 1"))
        print("[startup] DB pre-warm OK")
    except Exception as exc:  # noqa: BLE001
        print(f"[startup] DB pre-warm FAILED: {exc!r}")
    yield


app = FastAPI(title=settings.APP_NAME, lifespan=lifespan)

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
