"""
api.auth_routes
---------------
/auth/register, /auth/login, /auth/logout, /auth/me

Tokens are returned in an HttpOnly cookie. The frontend just needs to
include credentials: 'include' on every request — no manual header juggling.
"""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Cookie, HTTPException, Request, Response
from pydantic import BaseModel

from core.auth import (
    AuthError,
    InvalidCredentials,
    User,
    UserAlreadyExists,
    authenticate,
    create_token,
    lookup_token,
    register_user,
    revoke_token,
)
from core.config import get_settings
from core.logging_setup import get_logger

log = get_logger(__name__)

router = APIRouter(prefix="/auth", tags=["auth"])


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------

class CredentialsBody(BaseModel):
    username: str
    password: str


class UserResponse(BaseModel):
    id: int
    username: str


# ---------------------------------------------------------------------------
# Cookie helpers
# ---------------------------------------------------------------------------

def _set_cookie(response: Response, token: str) -> None:
    settings = get_settings()
    response.set_cookie(
        key=settings.auth.session_cookie,
        value=token,
        max_age=settings.auth.session_ttl_seconds,
        httponly=True,
        # In prod (frontend and backend on different domains) browsers REQUIRE
        # SameSite=None + Secure=True or the cookie is silently dropped.
        # Locally we want SameSite=Lax + non-secure so cookies survive http://.
        samesite=settings.auth.cookie_samesite,
        secure=settings.auth.cookie_secure,
        path="/",
    )


def _clear_cookie(response: Response) -> None:
    settings = get_settings()
    response.delete_cookie(
        key=settings.auth.session_cookie,
        path="/",
        samesite=settings.auth.cookie_samesite,
        secure=settings.auth.cookie_secure,
    )


# ---------------------------------------------------------------------------
# Public dependency for other route modules
# ---------------------------------------------------------------------------

def current_user(request: Request) -> User:
    """FastAPI dependency. Raises 401 if no valid token."""
    cookie_name = get_settings().auth.session_cookie
    token = request.cookies.get(cookie_name)
    user = lookup_token(token) if token else None
    if not user:
        raise HTTPException(status_code=401, detail="Authentication required")
    return user


def optional_user(request: Request) -> Optional[User]:
    """Dependency that returns None instead of 401 — used by routes that
    accept both anonymous and authenticated callers."""
    cookie_name = get_settings().auth.session_cookie
    token = request.cookies.get(cookie_name)
    return lookup_token(token) if token else None


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@router.post("/register", response_model=UserResponse, status_code=201)
def register(body: CredentialsBody, response: Response):
    try:
        user = register_user(body.username, body.password)
    except UserAlreadyExists as e:
        raise HTTPException(status_code=409, detail=str(e))
    except AuthError as e:
        raise HTTPException(status_code=400, detail=str(e))
    token = create_token(user.id)
    _set_cookie(response, token)
    return UserResponse(id=user.id, username=user.username)


@router.post("/login", response_model=UserResponse)
def login(body: CredentialsBody, response: Response):
    try:
        user = authenticate(body.username, body.password)
    except InvalidCredentials as e:
        raise HTTPException(status_code=401, detail=str(e))
    token = create_token(user.id)
    _set_cookie(response, token)
    return UserResponse(id=user.id, username=user.username)


@router.post("/logout", status_code=204)
def logout(
    response: Response,
    session_token: Optional[str] = Cookie(default=None, alias="ip_session"),
):
    if session_token:
        revoke_token(session_token)
    _clear_cookie(response)


@router.get("/me", response_model=UserResponse)
def me(request: Request) -> UserResponse:
    user = current_user(request)
    return UserResponse(id=user.id, username=user.username)
