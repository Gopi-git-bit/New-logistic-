"""Authentication boundary for the deterministic API core."""

from __future__ import annotations

from dataclasses import dataclass

import jwt
from fastapi import HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer


@dataclass(frozen=True)
class AuthenticatedSubject:
    external_subject: str


security = HTTPBearer(auto_error=False)


def authenticate_subject(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None,
) -> AuthenticatedSubject:
    settings = request.app.state.settings
    if credentials is None:
        raise HTTPException(
            status_code=401,
            detail={
                "code": "UNAUTHENTICATED",
                "message": "Authentication is required",
                "retryable": False,
            },
        )
    if settings.auth_mode != "test_jwt" or settings.app_env not in {
        "development",
        "test",
    }:
        raise HTTPException(
            status_code=503,
            detail={
                "code": "AUTH_UNAVAILABLE",
                "message": "Authentication is not configured",
                "retryable": True,
            },
        )
    try:
        payload = jwt.decode(
            credentials.credentials,
            settings.auth_jwt_secret,
            algorithms=["HS256"],
            audience="zippy-api",
            options={"require": ["sub", "aud", "exp"]},
        )
    except jwt.ExpiredSignatureError as exc:
        raise HTTPException(
            status_code=401,
            detail={
                "code": "TOKEN_EXPIRED",
                "message": "Authentication token expired",
                "retryable": False,
            },
        ) from exc
    except jwt.InvalidTokenError as exc:
        raise HTTPException(
            status_code=401,
            detail={
                "code": "INVALID_TOKEN",
                "message": "Authentication token is invalid",
                "retryable": False,
            },
        ) from exc
    subject = payload.get("sub")
    if not isinstance(subject, str) or not subject:
        raise HTTPException(
            status_code=401,
            detail={
                "code": "INVALID_TOKEN",
                "message": "Authentication token has no subject",
                "retryable": False,
            },
        )
    return AuthenticatedSubject(external_subject=subject)
