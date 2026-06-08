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
from typing import Any, List

from collections import defaultdict
from time import time as _time

from fastapi import APIRouter, Depends, HTTPException, Request, status
from typing import Optional
from pydantic import BaseModel
from sqlalchemy.orm import Session

# ── Rate limiter ──────────────────────────────────────────────────────────────
_login_attempts: dict = defaultdict(list)  # ip → [timestamps]
_MAX_ATTEMPTS   = 10
_WINDOW_SECONDS = 900  # 15 minutes

def _get_client_ip(request: Request) -> str:
    """Return real client IP, honouring X-Forwarded-For set by a reverse proxy."""
    xff = request.headers.get("X-Forwarded-For")
    if xff:
        return xff.split(",")[0].strip()
    return request.client.host if request.client else "unknown"

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
    revoke_token, is_token_revoked, cleanup_expired_tokens,
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
    user_presets: Optional[dict] = None  # {name: {varName: value}} – null clears all
    dark_preset: Optional[str] = None    # name of selected dark-mode preset
    light_preset: Optional[str] = None   # name of selected light-mode preset
    sidebar_prefs: Optional[dict] = None          # {nav-id: bool} visibility
    sidebar_order: Optional[List[Any]] = None     # [nav-id | {type,id,label}] – null clears
    settings_tabs_order: Optional[List[str]] = None  # [tab-id, ...]
    settings_tabs_vis: Optional[dict] = None         # {tab-id: bool}
    dashboard_widgets: Optional[List[Any]] = None    # [{id, visible}] – null clears
    dashboard_cols: Optional[int] = None              # stat-card column count (1-4)


class LogoutBody(BaseModel):
    refresh_token: Optional[str] = None

@router.post("/api/auth/login")
def login(body: LoginBody, request: Request, db: Session = Depends(get_db)):
    ip = _get_client_ip(request)
    _check_rate_limit(ip)
    user = db.query(User).filter(User.username == body.username).first()
    if not user or not verify_password(body.password, user.password_hash):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid username or password")
    _login_attempts.pop(ip, None)
    if not user.is_active:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Account disabled")
    user.last_login = datetime.now(timezone.utc)
    db.commit()
    # Periodically clean expired blocklist entries
    try: cleanup_expired_tokens(db)
    except Exception: pass
    return {
        "access_token":  create_access_token(user.id, user.username, user.role, user.token_version),
        "refresh_token": create_refresh_token(user.id, user.token_version),
        "token_type":    "bearer",
        "user": _user_dict(user),
    }


@router.post("/api/auth/refresh")
def refresh_token(body: RefreshBody, db: Session = Depends(get_db)):
    payload = decode_token(body.refresh_token)
    if not payload or payload.get("type") != "refresh":
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid refresh token")
    jti = payload.get("jti")
    if jti and is_token_revoked(jti, db):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Token has been revoked")
    user = db.get(User, int(payload["sub"]))
    if not user or not user.is_active:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "User not found")
    # Reject tokens issued before a password change (token_version mismatch)
    if payload.get("tv", 0) != user.token_version:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Token invalidated — please log in again")
    return {
        "access_token": create_access_token(user.id, user.username, user.role, user.token_version),
        "token_type": "bearer",
    }


@router.post("/api/auth/logout", status_code=204)
def logout(body: LogoutBody = LogoutBody(), db: Session = Depends(get_db)):
    if body.refresh_token:
        payload = decode_token(body.refresh_token)
        if payload and payload.get("jti") and payload.get("exp"):
            from datetime import datetime, timezone
            expires_at = datetime.fromtimestamp(payload["exp"], tz=timezone.utc)
            try: revoke_token(payload["jti"], expires_at, db)
            except Exception: pass
    return None


@router.post("/api/auth/revoke-sessions", status_code=204)
def revoke_all_sessions(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Invalidate all refresh tokens for this user by bumping token_version."""
    user.token_version = (user.token_version or 0) + 1
    db.commit()
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
    user.token_version = (user.token_version or 0) + 1  # invalidate all existing refresh tokens
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
        existing["custom_theme"] = body.custom_theme
    if "user_presets" in body.model_fields_set:
        existing["user_presets"] = body.user_presets
    if body.dark_preset is not None:
        existing["dark_preset"] = body.dark_preset
    if body.light_preset is not None:
        existing["light_preset"] = body.light_preset
    if body.sidebar_prefs is not None:
        existing["sidebar_prefs"] = body.sidebar_prefs
    if "sidebar_order" in body.model_fields_set:
        existing["sidebar_order"] = body.sidebar_order
    if body.settings_tabs_order is not None:
        existing["settings_tabs_order"] = body.settings_tabs_order
    if body.settings_tabs_vis is not None:
        existing["settings_tabs_vis"] = body.settings_tabs_vis
    if "dashboard_widgets" in body.model_fields_set:
        existing["dashboard_widgets"]= body.dashboard_widgets
    if body.dashboard_cols is not None:
        existing["dashboard_cols"] = body.dashboard_cols
    user.preferences = json.dumps(existing)
    db.commit()
