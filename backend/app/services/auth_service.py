from datetime import UTC, datetime, timedelta

from fastapi import HTTPException, Response
from jose import jwt
from passlib.context import CryptContext
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.user import User
from app.schemas.auth import LoginRequest, RegisterRequest, UserResponse

COOKIE_NAME = "access_token"
JWT_ALGORITHM = "HS256"

_pwd = CryptContext(schemes=["bcrypt"], deprecated="auto")


def _create_jwt(sub: str) -> str:
    expire = datetime.now(UTC) + timedelta(minutes=settings.JWT_EXPIRE_MINUTES)
    return jwt.encode({"sub": sub, "exp": expire}, settings.SECRET_KEY, algorithm=JWT_ALGORITHM)


def _set_auth_cookie(response: Response, token: str) -> None:
    response.set_cookie(
        key=COOKIE_NAME,
        value=token,
        httponly=True,
        samesite="lax",
        secure=settings.ENVIRONMENT != "development",
        max_age=settings.JWT_EXPIRE_MINUTES * 60,
    )


async def register_user(
    db: AsyncSession, payload: RegisterRequest, response: Response
) -> UserResponse:
    existing = await db.scalar(select(User).where(User.email == payload.email))
    if existing is not None:
        raise HTTPException(
            status_code=409,
            detail={"error": "user_exists", "message": "Email already registered"},
        )
    user = User(email=payload.email, hashed_password=_pwd.hash(payload.password))
    db.add(user)
    await db.commit()
    _set_auth_cookie(response, _create_jwt(user.email))
    return UserResponse(email=user.email)


async def login_user(
    db: AsyncSession, payload: LoginRequest, response: Response
) -> UserResponse:
    user = await db.scalar(select(User).where(User.email == payload.email))
    if (
        user is None
        or not user.hashed_password
        or not _pwd.verify(payload.password, user.hashed_password)
    ):
        raise HTTPException(
            status_code=401,
            detail={"error": "invalid_credentials", "message": "Invalid email or password"},
        )
    _set_auth_cookie(response, _create_jwt(user.email))
    return UserResponse(email=user.email)


def clear_auth_cookie(response: Response) -> None:
    response.delete_cookie(COOKIE_NAME)
