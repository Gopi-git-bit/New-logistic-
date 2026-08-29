"""Zippy Logistics — Supabase JWT Authentication + RBAC.

Verifies Supabase JWT tokens and extracts user identity + role.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from enum import Enum
from typing import Optional

import jwt
from fastapi import Depends, HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer


class UserRole(str, Enum):
    """User roles from the users table."""
    ADMIN = "admin"
    CUSTOMER = "customer"
    DRIVER = "driver"
    TRANSPORT_COMPANY = "transport_company"


@dataclass
class UserIdentity:
    """Authenticated user identity."""
    user_id: str
    email: str
    role: UserRole
    active_role: Optional[UserRole] = None


security = HTTPBearer(auto_error=False)


def _get_jwt_secret() -> str:
    """Get JWT secret from environment."""
    import os
    return os.environ.get("SUPABASE_JWT_SECRET", "")


def decode_supabase_jwt(token: str) -> dict:
    """Decode and verify a Supabase JWT token."""
    secret = _get_jwt_secret()
    if not secret:
        raise HTTPException(status_code=500, detail="JWT secret not configured")

    try:
        payload = jwt.decode(
            token,
            secret,
            algorithms=["HS256"],
            options={"verify_aud": False},
        )
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token")

    return payload


def extract_user_identity(payload: dict) -> UserIdentity:
    """Extract user identity from JWT payload."""
    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(status_code=401, detail="Missing user ID in token")

    email = payload.get("email", "")
    role_str = payload.get("role", "customer")

    try:
        role = UserRole(role_str)
    except ValueError:
        role = UserRole.CUSTOMER

    return UserIdentity(
        user_id=user_id,
        email=email,
        role=role,
        active_role=role,
    )


async def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
) -> UserIdentity:
    """Dependency: Extract authenticated user from JWT."""
    if not credentials:
        raise HTTPException(status_code=401, detail="Missing authorization header")

    payload = decode_supabase_jwt(credentials.credentials)
    return extract_user_identity(payload)


def require_role(*allowed_roles: UserRole):
    """Dependency factory: Require specific roles."""
    async def _check(user: UserIdentity = Depends(get_current_user)) -> UserIdentity:
        effective_role = user.active_role or user.role
        if effective_role not in allowed_roles:
            raise HTTPException(
                status_code=403,
                detail=f"Role '{effective_role.value}' not in allowed roles: {[r.value for r in allowed_roles]}",
            )
        return user
    return _check
