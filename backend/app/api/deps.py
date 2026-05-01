from collections.abc import AsyncGenerator

from fastapi import Cookie, Depends, HTTPException
from jose import JWTError, jwt
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.db.session import get_db
from app.services.auth import COOKIE_NAME, JWT_ALGORITHM


async def get_db_session(db: AsyncSession = Depends(get_db)) -> AsyncSession:
    return db


async def get_current_user(token: str | None = Cookie(default=None, alias=COOKIE_NAME)) -> dict[str, str]:
    if not token:
        raise HTTPException(
            status_code=401,
            detail={"error": "unauthorized", "message": "Missing auth cookie"},
        )

    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[JWT_ALGORITHM])
        email = payload.get("sub")
        if not email:
            raise HTTPException(
                status_code=401,
                detail={"error": "unauthorized", "message": "Invalid token payload"},
            )
    except JWTError as exc:
        raise HTTPException(
            status_code=401,
            detail={"error": "unauthorized", "message": "Invalid token"},
        ) from exc

    return {"email": email}
