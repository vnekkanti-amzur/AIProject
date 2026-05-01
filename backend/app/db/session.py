from collections.abc import AsyncGenerator
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import settings


def _build_async_db_url(db_url: str) -> str:
    if db_url.startswith("postgresql+asyncpg://"):
        normalized = db_url
    elif db_url.startswith("postgresql://"):
        normalized = db_url.replace("postgresql://", "postgresql+asyncpg://", 1)
    else:
        normalized = db_url

    # asyncpg rejects `sslmode=...`; it expects `ssl=...`.
    split = urlsplit(normalized)
    pairs = parse_qsl(split.query, keep_blank_values=True)
    mapped: list[tuple[str, str]] = []
    for key, value in pairs:
        if key == "sslmode":
            mapped.append(("ssl", value))
        else:
            mapped.append((key, value))

    return urlunsplit((split.scheme, split.netloc, split.path, urlencode(mapped), split.fragment))


engine = create_async_engine(
    _build_async_db_url(settings.DATABASE_URL),
    future=True,
    echo=False,
    connect_args={"statement_cache_size": 0},
)
SessionLocal = async_sessionmaker(bind=engine, expire_on_commit=False, class_=AsyncSession)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with SessionLocal() as session:
        yield session
