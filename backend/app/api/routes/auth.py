from urllib.parse import quote_plus

from fastapi import APIRouter, Depends, Query, Response
from fastapi.responses import RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.config import settings
from app.db.session import get_db
from app.schemas.auth import (
    LoginRequest,
    MessageResponse,
    RegisterRequest,
    UserResponse,
)
from app.services import auth

router = APIRouter()


@router.post("/register", response_model=UserResponse)
async def register(
    payload: RegisterRequest,
    response: Response,
    db: AsyncSession = Depends(get_db),
) -> UserResponse:
    return await auth.register_user(db, payload, response)


@router.post("/login", response_model=UserResponse)
async def login(
    payload: LoginRequest,
    response: Response,
    db: AsyncSession = Depends(get_db),
) -> UserResponse:
    return await auth.login_user(db, payload, response)


@router.post("/logout", response_model=MessageResponse)
async def logout(response: Response) -> MessageResponse:
    auth.clear_auth_cookie(response)
    return MessageResponse(message="Logged out")


@router.get("/me", response_model=UserResponse)
async def me(current_user: dict = Depends(get_current_user)) -> UserResponse:
    return UserResponse(email=current_user["email"])


@router.get("/google/login")
async def google_login() -> RedirectResponse:
    return RedirectResponse(url=auth.build_google_authorize_url(), status_code=302)


@router.get("/google/callback")
async def google_callback(
    db: AsyncSession = Depends(get_db),
    code: str | None = Query(default=None),
    error: str | None = Query(default=None),
) -> RedirectResponse:
    frontend_callback = f"{settings.FRONTEND_URL}/auth/callback"

    if error is not None:
        return RedirectResponse(
            url=f"{frontend_callback}?error={quote_plus(error)}",
            status_code=302,
        )

    if code is None:
        return RedirectResponse(
            url=f"{frontend_callback}?error={quote_plus('missing_code')}",
            status_code=302,
        )

    user = await auth.login_with_google(db, code)
    redirect = RedirectResponse(url=frontend_callback, status_code=302)
    auth.set_auth_cookie(redirect, auth.create_jwt(user.email))
    return redirect
