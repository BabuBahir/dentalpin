"""Session cookies (ADR 0023, issue #353).

The backend sets the tokens as ``HttpOnly; Secure; SameSite=Lax`` cookies
so JS never sees them; the refresh cookie is path-scoped to the one
endpoint that consumes it. A third, JS-readable ``dp_csrf`` cookie is the
double-submit token: cookie-authenticated unsafe requests must echo it in
``X-CSRF-Token`` (``dependencies.get_auth_token``).
"""

from __future__ import annotations

import secrets

from fastapi import Response

from app.config import settings

ACCESS_COOKIE = "dp_access"
REFRESH_COOKIE = "dp_refresh"
CSRF_COOKIE = "dp_csrf"
CSRF_HEADER = "X-CSRF-Token"
REFRESH_COOKIE_PATH = "/api/v1/auth/refresh"
SAFE_METHODS = frozenset({"GET", "HEAD", "OPTIONS"})


def _secure() -> bool:
    # Plain http://localhost in dev/e2e can't carry Secure cookies.
    return settings.ENVIRONMENT == "production"


def new_csrf_token() -> str:
    return secrets.token_urlsafe(32)


def set_session_cookies(
    response: Response, *, access_token: str, refresh_token: str, csrf_token: str
) -> None:
    access_ttl = settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60
    refresh_ttl = settings.REFRESH_TOKEN_EXPIRE_DAYS * 24 * 3600
    response.set_cookie(
        ACCESS_COOKIE,
        access_token,
        max_age=access_ttl,
        httponly=True,
        secure=_secure(),
        samesite="lax",
        path="/",
    )
    response.set_cookie(
        REFRESH_COOKIE,
        refresh_token,
        max_age=refresh_ttl,
        httponly=True,
        secure=_secure(),
        samesite="lax",
        path=REFRESH_COOKIE_PATH,
    )
    response.set_cookie(
        CSRF_COOKIE,
        csrf_token,
        max_age=refresh_ttl,
        httponly=False,  # the double-submit half JS must read
        secure=_secure(),
        samesite="lax",
        path="/",
    )


def clear_session_cookies(response: Response) -> None:
    response.delete_cookie(ACCESS_COOKIE, path="/")
    response.delete_cookie(REFRESH_COOKIE, path=REFRESH_COOKIE_PATH)
    response.delete_cookie(CSRF_COOKIE, path="/")
