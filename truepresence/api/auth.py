"""
TruePresence Auth Router

Handles user authentication, JWT token issuance, and user management.
Roles: super_admin | admin | reviewer | observer
"""

from __future__ import annotations

import hashlib
import hmac
import logging
import os
import secrets
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError as JoseJWTError
from jose import jwt
from pydantic import BaseModel

from truepresence.api.rate_limit import limiter as http_limiter
from truepresence.db import get_db
from truepresence.runtime.distributed import DistributedRuntime

logger = logging.getLogger(__name__)


def _redis_url() -> str:
    return os.environ.get("REDIS_URL", "redis://localhost:6379/0")

router = APIRouter(prefix="/auth", tags=["auth"])

ALGORITHM = "HS256"
TOKEN_EXPIRE_HOURS = 24
DEV_FALLBACK_SECRET = "truepresence-dev-only-jwt-secret"

ROLE_HIERARCHY = {
    "super_admin": 4,
    "admin": 3,
    "reviewer": 2,
    "observer": 1,
}


def _is_explicit_development_mode() -> bool:
    mode = (
        os.environ.get("TRUEPRESENCE_ENV")
        or os.environ.get("APP_ENV")
        or os.environ.get("ENVIRONMENT")
        or ""
    ).strip().lower()
    return mode in {"dev", "development", "local", "test"}


def _allow_dev_jwt_fallback() -> bool:
    flag = os.environ.get("TRUEPRESENCE_ALLOW_DEV_AUTH", "").strip().lower()
    return _is_explicit_development_mode() and flag in {"1", "true", "yes", "on"}


def resolve_jwt_secret() -> str:
    secret = os.environ.get("JWT_SECRET")
    if secret:
        return secret
    if _allow_dev_jwt_fallback():
        logger.warning("JWT_SECRET missing; using explicit development fallback secret")
        return DEV_FALLBACK_SECRET
    raise RuntimeError(
        "JWT_SECRET is required. Enable TRUEPRESENCE_ALLOW_DEV_AUTH in explicit development mode only."
    )


SECRET_KEY = resolve_jwt_secret()


def get_secret_key() -> str:
    return SECRET_KEY


bearer_scheme = HTTPBearer()


def _hash_password_fallback(password: str) -> str:
    salt = secrets.token_hex(16)
    iterations = 600_000
    derived = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt.encode("utf-8"), iterations)
    return f"pbkdf2_sha256${iterations}${salt}${derived.hex()}"


def _verify_password_fallback(plain: str, hashed: str) -> bool:
    try:
        scheme, iteration_text, salt, digest = hashed.split("$", 3)
    except ValueError:
        return False
    if scheme != "pbkdf2_sha256":
        return False
    derived = hashlib.pbkdf2_hmac("sha256", plain.encode("utf-8"), salt.encode("utf-8"), int(iteration_text))
    return hmac.compare_digest(derived.hex(), digest)


try:
    from passlib.context import CryptContext
except ModuleNotFoundError:
    pwd_context = None
else:
    pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


class LoginRequest(BaseModel):
    email: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: dict


class CreateUserRequest(BaseModel):
    email: str
    name: str
    password: str
    role: str = "reviewer"
    tenant_id: str = "default"


class UpdateUserRequest(BaseModel):
    name: Optional[str] = None
    role: Optional[str] = None
    active: Optional[bool] = None
    tenant_id: Optional[str] = None


def hash_password(password: str) -> str:
    if pwd_context is not None:
        return pwd_context.hash(password)
    return _hash_password_fallback(password)


def verify_password(plain: str, hashed: str) -> bool:
    if pwd_context is not None and not hashed.startswith("pbkdf2_sha256$"):
        return pwd_context.verify(plain, hashed)
    return _verify_password_fallback(plain, hashed)


def create_token(user_id: int, email: str, role: str, tenant_id: str) -> str:
    payload = {
        "sub": str(user_id),
        "email": email,
        "role": role,
        "tenant_id": tenant_id,
        "exp": datetime.now(timezone.utc) + timedelta(hours=TOKEN_EXPIRE_HOURS),
    }
    return jwt.encode(payload, get_secret_key(), algorithm=ALGORITHM)


def decode_token(token: str) -> dict:
    try:
        return jwt.decode(token, get_secret_key(), algorithms=[ALGORITHM])
    except JoseJWTError as exc:
        logger.warning("Token verification failed: %s", exc)
        raise HTTPException(status_code=401, detail="Invalid or expired token") from exc


def _load_current_user_record(user_id: str) -> Dict[str, Any]:
    # Try cache first
    try:
        dist = DistributedRuntime(redis_url=_redis_url())
        cache_key = f"user_cache:{user_id}"
        cached_user = dist.load_session(cache_key)
        if cached_user:
            return cached_user
    except Exception as e:
        logger.warning("User cache miss or error: %s", e)

    try:
        with get_db() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT id, email, name, role, tenant_id, active FROM users WHERE id = %s",
                    (int(user_id),),
                )
                user = cur.fetchone()
    except Exception as exc:
        logger.error("Failed to load current user from database", exc_info=True)
        raise HTTPException(status_code=503, detail="Authentication backend unavailable") from exc

    if not user:
        raise HTTPException(status_code=401, detail="User is no longer valid")
    if not user["active"]:
        raise HTTPException(status_code=401, detail="User account is inactive")

    user_dict = dict(user)

    # Store in cache for 1 hour
    try:
        dist = DistributedRuntime(redis_url=_redis_url())
        dist.store_session(f"user_cache:{user_id}", user_dict)
    except Exception as exc:
        logger.warning("Failed to store user record in cache (non-fatal): %s", exc)

    return user_dict


def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme)) -> dict:  # noqa: B008
    claims = decode_token(credentials.credentials)
    user = _load_current_user_record(claims.get("sub", ""))

    if claims.get("email") and claims["email"].lower() != user["email"].lower():
        raise HTTPException(status_code=401, detail="User is no longer valid")
    if claims.get("tenant_id") and claims["tenant_id"] != user["tenant_id"]:
        raise HTTPException(status_code=401, detail="Tenant mismatch")

    return user


    """Only the platform super_admin role may manage auth directory users."""
    if user.get("role") != "super_admin":
        raise HTTPException(status_code=403, detail="Super admin access required")
    return user


@router.post("/login", response_model=TokenResponse)
@http_limiter.limit("15/minute")
def login(request: Request, credentials: LoginRequest):
    """Authenticate user and return JWT."""
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT * FROM users WHERE email = %s AND active = TRUE",
                (credentials.email.lower(),),
            )
            user = cur.fetchone()

    if not user or not verify_password(credentials.password, user["password"]):
        raise HTTPException(status_code=401, detail="Invalid email or password")

    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE users SET last_login = NOW() WHERE id = %s",
                (user["id"],),
            )

    token = create_token(user["id"], user["email"], user["role"], user["tenant_id"])
    logger.info("Login: %s (%s)", user["email"], user["role"])

    return TokenResponse(
        access_token=token,
        user={
            "id": user["id"],
            "email": user["email"],
            "name": user["name"],
            "role": user["role"],
            "tenant_id": user["tenant_id"],
        },
    )


@router.get("/me")
def get_me(user: dict = Depends(get_current_user)):  # noqa: B008
    """Return authoritative current user info from the database."""
    return user


@router.post("/users", dependencies=[Depends(require_super_admin)])
def create_user(request: CreateUserRequest):
    """Create a new user — super_admin only."""
    if request.role not in ROLE_HIERARCHY:
        raise HTTPException(status_code=400, detail=f"Invalid role. Must be one of: {list(ROLE_HIERARCHY.keys())}")

    with get_db() as conn:
        with conn.cursor() as cur:
            try:
                cur.execute(
                    """INSERT INTO users (email, name, password, role, tenant_id)
                       VALUES (%s, %s, %s, %s, %s) RETURNING id, email, name, role, tenant_id, created_at""",
                    (
                        request.email.lower(),
                        request.name,
                        hash_password(request.password),
                        request.role,
                        request.tenant_id,
                    ),
                )
                new_user = cur.fetchone()
            except Exception as exc:
                if "unique" in str(exc).lower():
                    raise HTTPException(status_code=409, detail="Email already exists") from exc
                raise

    logger.info("Created user: %s (%s)", new_user["email"], new_user["role"])
    return dict(new_user)


@router.get("/users", dependencies=[Depends(require_super_admin)])
def list_users():
    """List all users — super_admin only."""
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT id, email, name, role, tenant_id, active, created_at, last_login FROM users ORDER BY created_at DESC"
            )
            return cur.fetchall()


@router.patch("/users/{user_id}", dependencies=[Depends(require_super_admin)])
def update_user(user_id: int, request: UpdateUserRequest):
    """Update user role, active status, or tenant — super_admin only."""
    VALID_USER_COLUMNS = {"name", "role", "active", "tenant_id"}

    fields = {k: v for k, v in request.model_dump().items() if v is not None}
    if not fields:
        raise HTTPException(status_code=400, detail="No fields to update")

    # Filter to only valid columns
    fields = {k: v for k, v in fields.items() if k in VALID_USER_COLUMNS}
    if not fields:
        raise HTTPException(status_code=400, detail="No valid fields to update")

    if "role" in fields and fields["role"] not in ROLE_HIERARCHY:
        raise HTTPException(status_code=400, detail=f"Invalid role: {fields['role']}")

    set_clause = ", ".join(f"{k} = %s" for k in fields)
    values = list(fields.values()) + [user_id]

    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                f"UPDATE users SET {set_clause} WHERE id = %s RETURNING id, email, name, role, active, tenant_id",
                values,
            )
            updated = cur.fetchone()

    if not updated:
        raise HTTPException(status_code=404, detail="User not found")

    # Invalidate cache
    try:
        DistributedRuntime(redis_url=_redis_url()).delete_session(f"user_cache:{user_id}")
    except Exception as exc:
        logger.warning("Failed to invalidate user cache after update (non-fatal): %s", exc)

    return dict(updated)


@router.delete("/users/{user_id}", dependencies=[Depends(require_super_admin)])
def deactivate_user(user_id: int):
    """Deactivate a user (soft delete) — super_admin only."""
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE users SET active = FALSE WHERE id = %s RETURNING id, email",
                (user_id,),
            )
            user = cur.fetchone()

    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # Invalidate cache
    try:
        DistributedRuntime(redis_url=_redis_url()).delete_session(f"user_cache:{user_id}")
    except Exception as exc:
        logger.warning("Failed to invalidate user cache after deactivation (non-fatal): %s", exc)

    logger.info("Deactivated user: %s", user["email"])
    return {"status": "deactivated", "user_id": user_id}
