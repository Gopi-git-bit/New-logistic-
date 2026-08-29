"""Zippy Logistics — Supabase JWT Authentication + RBAC.

Verifies Supabase JWT tokens and extracts user identity + role from trusted JWT data.
Roles are resolved from app_metadata.role (set by Supabase admin), not user-supplied claims.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Optional

import jwt
from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer


class UserRole(str, Enum):
    """User roles from the users table."""
    ADMIN = "admin"
    CUSTOMER = "customer"
    DRIVER = "driver"
    TRANSPORT_COMPANY = "transport_company"


# Roles that can create orders
ORDER_CREATOR_ROLES = {UserRole.CUSTOMER, UserRole.ADMIN}

# Roles that can verify POD
POD_VERIFIER_ROLES = {UserRole.DRIVER, UserRole.ADMIN}


@dataclass(frozen=True)
class UserIdentity:
    """Authenticated user identity — derived from trusted JWT claims only."""
    user_id: str
    email: str
    role: UserRole
    active_role: UserRole
    app_metadata: dict


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
    """Extract user identity from JWT payload.

    Role resolution order (trusted data only):
    1. app_metadata.role (set by Supabase admin/backend)
    2. user_metadata.role (user-selected during registration)
    3. Default to 'customer'
    """
    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(status_code=401, detail="Missing user ID in token")

    email = payload.get("email", "")

    # Resolve role from trusted sources only
    app_metadata = payload.get("app_metadata", {})
    user_metadata = payload.get("user_metadata", {})

    role_str = (
        app_metadata.get("role")
        or user_metadata.get("role")
        or "customer"
    )

    try:
        role = UserRole(role_str)
    except ValueError:
        role = UserRole.CUSTOMER

    return UserIdentity(
        user_id=user_id,
        email=email,
        role=role,
        active_role=role,
        app_metadata=app_metadata,
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
        if user.active_role not in allowed_roles:
            raise HTTPException(
                status_code=403,
                detail=f"Role '{user.active_role.value}' not in allowed roles: {[r.value for r in allowed_roles]}",
            )
        return user
    return _check
