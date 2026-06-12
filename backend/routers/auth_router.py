"""
Router: Authentication
  POST /api/auth/login        - get access + refresh tokens
  POST /api/auth/refresh      - exchange refresh for new access token
  POST /api/auth/logout       - revoke refresh token
  GET  /api/auth/me           - current user info
  POST /api/auth/change-password - change own password
"""
from __future__ import annotations
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status, Response, Request
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import User
from ..auth import (
    verify_password, hash_password,
    create_access_token, create_refresh_token, decode_token,
    revoke_token, is_token_revoked,
    get_current_user, get_permissions,
    REFRESH_TOKEN_EXPIRE_DAYS,
)

router = APIRouter(prefix="/api/auth", tags=["auth"])


# ── Schemas ────────────────────────────────────────────────────────────────────

class LoginRequest(BaseModel):
    username: str
    password: str

class RefreshRequest(BaseModel):
    refresh_token: str

class LogoutRequest(BaseModel):
    refresh_token: Optional[str] = None

class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str


# ── Helpers ────────────────────────────────────────────────────────────────────

def _user_dict(user: User) -> dict:
    return {
        "id":              user.id,
        "username":        user.username,
        "full_name":       user.full_name,
        "email":           user.email,
        "role":            user.role,
        "permissions":     get_permissions(user),
        "is_active":       user.is_active,
        "force_pw_change": user.force_pw_change,
        "member_id":       user.member_id,
    }


# ── Endpoints ──────────────────────────────────────────────────────────────────

@router.post("/login")
def login(body: LoginRequest, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.username == body.username).first()
    if not user or not verify_password(body.password, user.password_hash):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid username or password")
    if not user.is_active:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Account is disabled")

    # Update last login
    user.last_login = datetime.now(timezone.utc).replace(tzinfo=None)
    db.commit()

    access  = create_access_token(user.id, user.username, user.role, user.token_version or 0)
    refresh = create_refresh_token(user.id, user.token_version or 0)

    return {
        "access_token":  access,
        "refresh_token": refresh,
        "token_type":    "bearer",
        "user":          _user_dict(user),
    }


@router.post("/refresh")
def refresh_token(body: RefreshRequest, db: Session = Depends(get_db)):
    payload = decode_token(body.refresh_token)
    if not payload or payload.get("type") != "refresh":
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid refresh token")

    # Check revocation list
    jti = payload.get("jti")
    if jti and is_token_revoked(jti, db):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Token has been revoked")

    user = db.get(User, int(payload["sub"]))
    if not user or not user.is_active:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "User not found or inactive")

    # Check token version (session revocation)
    if payload.get("tv", 0) != (user.token_version or 0):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Session has been revoked")

    access = create_access_token(user.id, user.username, user.role, user.token_version or 0)
    return {"access_token": access, "token_type": "bearer"}


@router.post("/logout")
def logout(body: LogoutRequest, db: Session = Depends(get_db)):
    if body.refresh_token:
        payload = decode_token(body.refresh_token)
        if payload and payload.get("type") == "refresh":
            jti = payload.get("jti")
            exp = payload.get("exp")
            if jti and exp:
                from datetime import datetime, timezone
                expires_at = datetime.fromtimestamp(exp, tz=timezone.utc)
                revoke_token(jti, expires_at, db)
    return {"detail": "Logged out"}


@router.get("/me")
def me(user: User = Depends(get_current_user)):
    return _user_dict(user)


@router.post("/change-password")
def change_password(
    body: ChangePasswordRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if not verify_password(body.current_password, user.password_hash):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Current password is incorrect")
    if len(body.new_password) < 8:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Password must be at least 8 characters")
    user.password_hash = hash_password(body.new_password)
    user.force_pw_change = False
    db.commit()
    return {"detail": "Password changed successfully"}
