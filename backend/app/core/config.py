from functools import lru_cache
from pathlib import Path
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from pydantic_settings import BaseSettings, SettingsConfigDict

# backend/app/core/config.py -> backend/.env (3 levels up from this file)
_ENV_FILE = Path(__file__).resolve().parents[2] / ".env"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=str(_ENV_FILE), env_file_encoding="utf-8", extra="ignore")

    SECRET_KEY: str = "change-me"
    JWT_EXPIRE_MINUTES: int = 480
    APP_NAME: str = "amzur-ai-chat"
    ENVIRONMENT: str = "development"
    FRONTEND_URL: str = "http://localhost:5173"

    DATABASE_URL: str = "postgresql+asyncpg://user:pass@host:5432/dbname"

    LITELLM_PROXY_URL: str = "https://litellm.amzur.com"
    LITELLM_API_KEY: str = ""
    LLM_MODEL: str = "gemini/gemini-2.5-flash"
    LITELLM_EMBEDDING_MODEL: str = "text-embedding-3-large"
    IMAGE_GEN_MODEL: str = "gemini/imagen-4.0-fast-generate-001"

    GOOGLE_CLIENT_ID: str | None = None
    GOOGLE_CLIENT_SECRET: str | None = None
    GOOGLE_REDIRECT_URI: str = "http://localhost:8000/api/auth/google/callback"

    CHROMA_PERSIST_DIR: str = "./chroma_db"
    GOOGLE_SERVICE_ACCOUNT_JSON: str | None = None

    SUPABASE_URL: str = ""
    SUPABASE_ANON_KEY: str = ""
    SUPABASE_SERVICE_ROLE_KEY: str = ""

    MAX_UPLOAD_MB: int = 20
    UPLOAD_DIR: str = "./uploads"


def _build_sync_db_url(async_url: str) -> str:
    sync_url = async_url.replace("+asyncpg", "+psycopg2")

    # asyncpg often uses `ssl=require`, while psycopg2 expects `sslmode=require`.
    split = urlsplit(sync_url)
    pairs = parse_qsl(split.query, keep_blank_values=True)
    normalized: list[tuple[str, str]] = []
    for key, value in pairs:
        if key == "ssl":
            normalized.append(("sslmode", value))
        else:
            normalized.append((key, value))

    return urlunsplit((split.scheme, split.netloc, split.path, urlencode(normalized), split.fragment))


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
