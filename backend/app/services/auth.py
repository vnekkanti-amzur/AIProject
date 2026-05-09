from datetime import UTC, datetime, timedelta
from typing import Any
from urllib.parse import urlencode

import httpx
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

GOOGLE_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
GOOGLE_USERINFO_URL = "https://www.googleapis.com/oauth2/v3/userinfo"

_pwd = CryptContext(schemes=["pbkdf2_sha256", "bcrypt"], deprecated="auto")


def _ensure_amzur_email(email: str) -> None:
    if not email.strip().lower().endswith("@amzur.com"):
        raise HTTPException(
            status_code=403,
            detail={
                "error": "forbidden_domain",
                "message": "Only Amzur users are allowed to register",
            },
        )


def create_jwt(sub: str) -> str:
    expire = datetime.now(UTC) + timedelta(minutes=settings.JWT_EXPIRE_MINUTES)
    return jwt.encode({"sub": sub, "exp": expire}, settings.SECRET_KEY, algorithm=JWT_ALGORITHM)


def set_auth_cookie(response: Response, token: str) -> None:
    response.set_cookie(
        key=COOKIE_NAME,
        value=token,
        httponly=True,
        samesite="lax",
        secure=settings.ENVIRONMENT != "development",
        max_age=settings.JWT_EXPIRE_MINUTES * 60,
    )


def clear_auth_cookie(response: Response) -> None:
    response.delete_cookie(COOKIE_NAME)


async def register_user(
    db: AsyncSession, payload: RegisterRequest, response: Response
) -> UserResponse:
    _ensure_amzur_email(payload.email)

    existing = await db.scalar(select(User).where(User.email == payload.email))
    if existing is not None:
        raise HTTPException(
            status_code=409,
            detail={"error": "user_exists", "message": "Email already registered"},
        )

    user = User(email=payload.email, hashed_password=_pwd.hash(payload.password), google_id=None)
    db.add(user)
    await db.commit()

    set_auth_cookie(response, create_jwt(user.email))
    return UserResponse(email=user.email)


async def login_user(db: AsyncSession, payload: LoginRequest, response: Response) -> UserResponse:
    _ensure_amzur_email(payload.email)

    user = await db.scalar(select(User).where(User.email == payload.email))
    if user is None or not user.hashed_password or not _pwd.verify(payload.password, user.hashed_password):
        raise HTTPException(
            status_code=401,
            detail={"error": "invalid_credentials", "message": "Invalid email or password"},
        )

    # Transparently upgrade legacy password hashes after a successful login.
    if _pwd.needs_update(user.hashed_password):
        user.hashed_password = _pwd.hash(payload.password)
        await db.commit()

    set_auth_cookie(response, create_jwt(user.email))
    return UserResponse(email=user.email)


def build_google_authorize_url() -> str:
    params = {
        "client_id": settings.GOOGLE_CLIENT_ID,
        "redirect_uri": settings.GOOGLE_REDIRECT_URI,
        "response_type": "code",
        "scope": "openid email profile",
        "access_type": "offline",
        "prompt": "consent",
    }
    return f"{GOOGLE_AUTH_URL}?{urlencode(params)}"


async def _exchange_google_code(code: str) -> str:
    payload = {
        "code": code,
        "client_id": settings.GOOGLE_CLIENT_ID,
        "client_secret": settings.GOOGLE_CLIENT_SECRET,
        "redirect_uri": settings.GOOGLE_REDIRECT_URI,
        "grant_type": "authorization_code",
    }
    async with httpx.AsyncClient(timeout=20.0) as client:
        token_res = await client.post(GOOGLE_TOKEN_URL, data=payload)
        if token_res.status_code != 200:
            raise HTTPException(
                status_code=400,
                detail={"error": "google_oauth_failed", "message": "Failed to exchange auth code"},
            )
        token_json = token_res.json()

    access_token = token_json.get("access_token")
    if not access_token:
        raise HTTPException(
            status_code=400,
            detail={"error": "google_oauth_failed", "message": "Missing access token"},
        )
    return access_token


async def _fetch_google_profile(access_token: str) -> dict[str, Any]:
    async with httpx.AsyncClient(timeout=20.0) as client:
        userinfo_res = await client.get(
            GOOGLE_USERINFO_URL,
            headers={"Authorization": f"Bearer {access_token}"},
        )
        if userinfo_res.status_code != 200:
            raise HTTPException(
                status_code=400,
                detail={"error": "google_oauth_failed", "message": "Failed to fetch Google profile"},
            )
        return userinfo_res.json()


async def login_with_google(db: AsyncSession, code: str) -> User:
    access_token = await _exchange_google_code(code)
    profile = await _fetch_google_profile(access_token)

    email = profile.get("email")
    google_id = profile.get("sub")
    if not email or not google_id:
        raise HTTPException(
            status_code=400,
            detail={"error": "google_oauth_failed", "message": "Invalid Google profile payload"},
        )

    _ensure_amzur_email(email)

    by_google_id = await db.scalar(select(User).where(User.google_id == google_id))
    if by_google_id is not None:
        return by_google_id

    by_email = await db.scalar(select(User).where(User.email == email))
    if by_email is not None:
        by_email.google_id = google_id
        await db.commit()
        await db.refresh(by_email)
        return by_email

    user = User(email=email, google_id=google_id, hashed_password=None)
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user
