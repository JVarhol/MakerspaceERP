"""
Router: Authentication
  POST /api/auth/login    → {access_token, refresh_token, user}
  POST /api/auth/refresh  → {access_token}
  POST /api/auth/logout   → 204
  GET  /api/auth/me       → current user info
  POST /api/auth/change-password
"""
from __future__ import annotations
import json
from datetime import datetime, timezone

from collections import defaultdict
from time import time as _time

from fastapi import APIRouter, Depends, HTTPException, Request, status
from typing import Optional
from pydantic import BaseModel
from sqlalchemy.orm import Session

# ── Simple in-memory rate limiter ─────────────────────────────────────────────
_login_attempts: dict = defaultdict(list)  # ip → [timestamps]
_MAX_ATTEMPTS   = 10
_WINDOW_SECONDS = 900  # 15 minutes

def _check_rate_limit(ip: str):
    now = _time()
    attempts = [t for t in _login_attempts[ip] if now - t < _WINDOW_SECONDS]
    _login_attempts[ip] = attempts
    if len(attempts) >= _MAX_ATTEMPTS:
        wait = int(_WINDOW_SECONDS - (now - attempts[0]))
        raise HTTPException(
            status.HTTP_429_TOO_MANY_REQUESTS,
            f"Too many login attempts. Try again in {wait // 60}m {wait % 60}s."
        )
    _login_attempts[ip].append(now)

from ..database import get_db
from ..models import User
from ..auth import (
    verify_password, hash_password,
    create_access_token, create_refresh_token, decode_token,
    get_current_user, get_permissions,
)

router = APIRouter(tags=["auth"])


class LoginBody(BaseModel):
    username: str
    password: str

class RefreshBody(BaseModel):
    refresh_token: str

class ChangePasswordBody(BaseModel):
    current_password: str
    new_password: str

class PreferencesBody(BaseModel):
    theme: Optional[str] = None          # "dark" | "light"
    custom_theme: Optional[dict] = None  # CSS var overrides or null to clear


@router.post("/api/auth/login")
def login(body: LoginBody, request: Request, db: Session = Depends(get_db)):
    ip = request.client.host if request.client else "unknown"
    _check_rate_limit(ip)
    user = db.query(User).filter(User.username == body.username).first()
    if not user or not verify_password(body.password, user.password_hash):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid username or password")
    # Clear attempts on successful login
    _login_attempts.pop(ip, None)
    if not user.is_active:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Account disabled")

    # Update last login
    user.last_login = datetime.now(timezone.utc)
    db.commit()

    return {
        "access_token":  create_access_token(user.id, user.username, user.role),
        "refresh_token": create_refresh_token(user.id),
        "token_type":    "bearer",
        "user": _user_dict(user),
    }


@router.post("/api/auth/refresh")
def refresh_token(body: RefreshBody, db: Session = Depends(get_db)):
    payload = decode_token(body.refresh_token)
    if not payload or payload.get("type") != "refresh":
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid refresh token")
    user = db.get(User, int(payload["sub"]))
    if not user or not user.is_active:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "User not found")
    return {
        "access_token": create_access_token(user.id, user.username, user.role),
        "token_type": "bearer",
    }


@router.post("/api/auth/logout", status_code=204)
def logout():
    # Client-side token deletion; no server-side state
    return None


@router.get("/api/auth/me")
def me(user: User = Depends(get_current_user)):
    return _user_dict(user)


@router.post("/api/auth/change-password", status_code=204)
def change_password(
    body: ChangePasswordBody,
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


def _user_dict(user: User) -> dict:
    prefs = None
    if user.preferences:
        try: prefs = json.loads(user.preferences)
        except Exception: pass
    return {
        "id":               user.id,
        "username":         user.username,
        "full_name":        user.full_name,
        "email":            user.email,
        "role":             user.role,
        "permissions":      get_permissions(user),
        "force_pw_change":  user.force_pw_change,
        "last_login":       user.last_login.isoformat() if user.last_login else None,
        "preferences":      prefs,
    }


@router.patch("/api/auth/preferences", status_code=204)
def save_preferences(
    body: PreferencesBody,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    existing = {}
    if user.preferences:
        try: existing = json.loads(user.preferences)
        except Exception: pass
    if body.theme is not None:
        existing["theme"] = body.theme
    if "custom_theme" in body.model_fields_set:
        existing["custom_theme"] = body.custom_theme  # None clears it
    user.preferences = json.dumps(existing)
    db.commit()
