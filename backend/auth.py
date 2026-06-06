"""
JWT authentication utilities and dependencies.
"""
from __future__ import annotations
import json
import os
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import JWTError, jwt
from passlib.context import CryptContext
from sqlalchemy.orm import Session

from .database import get_db
from .models import User

# ── Config ────────────────────────────────────────────────────────────────────

def _get_secret_key() -> str:
    """Load JWT secret from env, then DB, then generate and persist a new one."""
    env_key = os.getenv("JWT_SECRET", "")
    if env_key and env_key != "change-me-in-production-use-a-long-random-string":
        return env_key
    # Try to load from DB
    try:
        from .database import SessionLocal
        from .models import AppSetting
        db = SessionLocal()
        row = db.query(AppSetting).filter(AppSetting.key == "_jwt_secret").first()
        if row and row.value:
            db.close()
            return row.value
        # Generate and persist a new secret
        import secrets
        key = secrets.token_hex(32)
        db.add(AppSetting(key="_jwt_secret", value=key))
        db.commit()
        db.close()
        print("Generated new JWT secret and stored in database.")
        return key
    except Exception as e:
        import secrets
        print(f"Warning: could not persist JWT secret ({e}), using temporary key")
        return secrets.token_hex(32)

SECRET_KEY = _get_secret_key()
ALGORITHM  = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES  = 60
REFRESH_TOKEN_EXPIRE_DAYS    = 7

pwd_ctx  = CryptContext(schemes=["bcrypt"], deprecated="auto")
security = HTTPBearer(auto_error=False)

# ── Default permissions ───────────────────────────────────────────────────────

DEFAULT_USER_PERMISSIONS = {
    "items":          {"read": True,  "write": True},
    "assets":         {"read": True,  "write": True},
    "locations":      {"read": True,  "write": True},
    "categories":     {"read": True,  "write": True},
    "materials":      {"read": True,  "write": True},
    "transactions":   {"read": True},
    "projects":       {"read": True,  "write": True},
    "purchase_orders":{"read": True,  "write": True},
    "kits":           {"read": True,  "write": True},
    "reports":        {"read": True},
    "trends":         {"read": True},
    "settings":       False,
    "users":          False,
}

ADMIN_PERMISSIONS = {k: ({"read": True, "write": True} if isinstance(v, dict) else True)
                    for k, v in DEFAULT_USER_PERMISSIONS.items()}
ADMIN_PERMISSIONS["settings"] = True
ADMIN_PERMISSIONS["users"]    = True


# ── Password helpers ──────────────────────────────────────────────────────────

def hash_password(password: str) -> str:
    return pwd_ctx.hash(password)

def verify_password(plain: str, hashed: str) -> bool:
    return pwd_ctx.verify(plain, hashed)


# ── JWT helpers ───────────────────────────────────────────────────────────────

def create_access_token(user_id: int, username: str, role: str) -> str:
    expire = datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    return jwt.encode(
        {"sub": str(user_id), "username": username, "role": role,
         "type": "access", "exp": expire},
        SECRET_KEY, algorithm=ALGORITHM,
    )

def create_refresh_token(user_id: int) -> str:
    expire = datetime.now(timezone.utc) + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)
    return jwt.encode(
        {"sub": str(user_id), "type": "refresh", "exp": expire},
        SECRET_KEY, algorithm=ALGORITHM,
    )

def decode_token(token: str) -> Optional[dict]:
    try:
        return jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    except JWTError:
        return None


# ── FastAPI dependencies ──────────────────────────────────────────────────────

def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
    db: Session = Depends(get_db),
) -> User:
    exc = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Not authenticated",
        headers={"WWW-Authenticate": "Bearer"},
    )
    if not credentials:
        raise exc
    payload = decode_token(credentials.credentials)
    if not payload or payload.get("type") != "access":
        raise exc
    user = db.get(User, int(payload["sub"]))
    if not user or not user.is_active:
        raise exc
    return user

def require_admin(user: User = Depends(get_current_user)) -> User:
    if user.role != "admin":
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Admin access required")
    return user

def get_permissions(user: User) -> dict:
    if user.role == "admin":
        return ADMIN_PERMISSIONS
    try:
        return json.loads(user.permissions or "{}") or DEFAULT_USER_PERMISSIONS
    except Exception:
        return DEFAULT_USER_PERMISSIONS

def can(user: User, section: str, action: str = "read") -> bool:
    if user.role == "admin":
        return True
    perms = get_permissions(user)
    p = perms.get(section, False)
    if isinstance(p, dict):
        return p.get(action, False)
    return bool(p)

def require_permission(section: str, action: str = "read"):
    def dep(user: User = Depends(get_current_user)) -> User:
        if not can(user, section, action):
            raise HTTPException(status.HTTP_403_FORBIDDEN,
                                f"Permission denied: {section}.{action}")
        return user
    return dep


# ── First-run admin setup ─────────────────────────────────────────────────────

def ensure_admin_exists(db: Session) -> None:
    """Create default admin account if no users exist."""
    if db.query(User).count() == 0:
        admin = User(
            username="admin",
            full_name="Administrator",
            password_hash=hash_password("admin123"),
            role="admin",
            permissions=json.dumps(ADMIN_PERMISSIONS),
            force_pw_change=True,
        )
        db.add(admin)
        db.commit()
        print("⚠ Created default admin user (admin / admin123) — change password immediately!")
