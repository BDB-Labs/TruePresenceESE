"""
TruePresence Auth Router

Handles user authentication, JWT token issuance, and user management.
Roles: super_admin | reviewer | observer
"""

import os
import logging
from datetime import datetime, timezone, timedelta
from typing import Optional, List
from fastapi import APIRouter, HTTPException, Depends, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel, EmailStr
from passlib.context import CryptContext
from jose import JWTError, jwt
from truepresence.db import get_db

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/auth", tags=["auth"])

SECRET_KEY = os.environ.get("JWT_SECRET", "change-me-in-production")
ALGORITHM = "HS256"
TOKEN_EXPIRE_HOURS = 24

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
bearer_scheme = HTTPBearer()

ROLE_HIERARCHY = {
    "super_admin": 3,
    "reviewer": 2,
    "observer": 1,
}


# ── Models ────────────────────────────────────────────────────────────────────

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


# ── Helpers ───────────────────────────────────────────────────────────────────

def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)


def create_token(user_id: int, email: str, role: str, tenant_id: str) -> str:
    payload = {
        "sub": str(user_id),
        "email": email,
        "role": role,
        "tenant_id": tenant_id,
        "exp": datetime.now(timezone.utc) + timedelta(hours=TOKEN_EXPIRE_HOURS),
    }
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


def decode_token(token: str) -> dict:
    try:
        return jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    except JWTError as e:
        raise HTTPException(status_code=401, detail=f"Invalid token: {e}")


def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme)) -> dict:
    return decode_token(credentials.credentials)


def require_role(minimum_role: str):
    """Dependency — enforces minimum role level."""
    def checker(user: dict = Depends(get_current_user)) -> dict:
        user_level = ROLE_HIERARCHY.get(user.get("role"), 0)
        required_level = ROLE_HIERARCHY.get(minimum_role, 0)
        if user_level < required_level:
            raise HTTPException(status_code=403, detail="Insufficient permissions")
        return user
    return checker


# ── Routes ────────────────────────────────────────────────────────────────────

@router.post("/login", response_model=TokenResponse)
def login(request: LoginRequest):
    """Authenticate user and return JWT."""
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT * FROM users WHERE email = %s AND active = TRUE",
                (request.email.lower(),)
            )
            user = cur.fetchone()

    if not user or not verify_password(request.password, user["password"]):
        raise HTTPException(status_code=401, detail="Invalid email or password")

    # Update last_login
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE users SET last_login = NOW() WHERE id = %s",
                (user["id"],)
            )

    token = create_token(user["id"], user["email"], user["role"], user["tenant_id"])
    logger.info(f"Login: {user['email']} ({user['role']})")

    return TokenResponse(
        access_token=token,
        user={
            "id": user["id"],
            "email": user["email"],
            "name": user["name"],
            "role": user["role"],
            "tenant_id": user["tenant_id"],
        }
    )


@router.get("/me")
def get_me(user: dict = Depends(get_current_user)):
    """Return current user info from token."""
    return user


@router.post("/users", dependencies=[Depends(require_role("super_admin"))])
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
                    (request.email.lower(), request.name, hash_password(request.password),
                     request.role, request.tenant_id)
                )
                new_user = cur.fetchone()
            except Exception as e:
                if "unique" in str(e).lower():
                    raise HTTPException(status_code=409, detail="Email already exists")
                raise

    logger.info(f"Created user: {new_user['email']} ({new_user['role']})")
    return dict(new_user)


@router.get("/users", dependencies=[Depends(require_role("super_admin"))])
def list_users():
    """List all users — super_admin only."""
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT id, email, name, role, tenant_id, active, created_at, last_login FROM users ORDER BY created_at DESC"
            )
            return cur.fetchall()


@router.patch("/users/{user_id}", dependencies=[Depends(require_role("super_admin"))])
def update_user(user_id: int, request: UpdateUserRequest):
    """Update user role, active status, or tenant — super_admin only."""
    fields = {k: v for k, v in request.model_dump().items() if v is not None}
    if not fields:
        raise HTTPException(status_code=400, detail="No fields to update")
    if "role" in fields and fields["role"] not in ROLE_HIERARCHY:
        raise HTTPException(status_code=400, detail=f"Invalid role: {fields['role']}")

    set_clause = ", ".join(f"{k} = %s" for k in fields)
    values = list(fields.values()) + [user_id]

    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                f"UPDATE users SET {set_clause} WHERE id = %s RETURNING id, email, name, role, active, tenant_id",
                values
            )
            updated = cur.fetchone()

    if not updated:
        raise HTTPException(status_code=404, detail="User not found")
    return dict(updated)


@router.delete("/users/{user_id}", dependencies=[Depends(require_role("super_admin"))])
def deactivate_user(user_id: int):
    """Deactivate a user (soft delete) — super_admin only."""
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE users SET active = FALSE WHERE id = %s RETURNING id, email",
                (user_id,)
            )
            user = cur.fetchone()

    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    logger.info(f"Deactivated user: {user['email']}")
    return {"status": "deactivated", "user_id": user_id}
