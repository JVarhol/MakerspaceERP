"""
Router: User management (admin only)
  GET    /api/users
  POST   /api/users
  GET    /api/users/{uid}
  PATCH  /api/users/{uid}
  DELETE /api/users/{uid}
"""
from __future__ import annotations
import json, random
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import User, UserPermissionProfile
from ..auth import (
    hash_password, require_admin, get_permissions,
    DEFAULT_USER_PERMISSIONS, ADMIN_PERMISSIONS, STAFF_DEFAULT_PERMISSIONS,
)

router = APIRouter(tags=["users"])


class UserCreate(BaseModel):
    username: str
    full_name: Optional[str] = None
    email: Optional[str] = None
    password: str
    role: str = "user"
    permissions: Optional[dict] = None
    is_active: bool = True

class UserUpdate(BaseModel):
    full_name: Optional[str] = None
    email: Optional[str] = None
    password: Optional[str] = None
    role: Optional[str] = None
    permissions: Optional[dict] = None
    is_active: Optional[bool] = None
    force_pw_change: Optional[bool] = None
    member_id: Optional[str] = None


def _out(u: User) -> dict:
    return {
        "id":             u.id,
        "username":       u.username,
        "full_name":      u.full_name,
        "email":          u.email,
        "role":           u.role,
        "permissions":    get_permissions(u),
        "is_active":      u.is_active,
        "force_pw_change":u.force_pw_change,
        "last_login":     u.last_login.isoformat() if u.last_login else None,
        "created_at":     u.created_at.isoformat() if u.created_at else None,
        "member_id":      u.member_id,
    }


@router.get("/api/users")
def list_users(_: User = Depends(require_admin), db: Session = Depends(get_db)):
    return [_out(u) for u in db.query(User).order_by(User.username).all()]


@router.post("/api/users", status_code=201)
def create_user(body: UserCreate, _: User = Depends(require_admin), db: Session = Depends(get_db)):
    if db.query(User).filter(User.username == body.username).first():
        raise HTTPException(400, "Username already exists")
    if len(body.password) < 8:
        raise HTTPException(400, "Password must be at least 8 characters")
    perms = body.permissions or (ADMIN_PERMISSIONS if body.role == "admin" else DEFAULT_USER_PERMISSIONS)
    user = User(
        username=body.username,
        full_name=body.full_name,
        email=body.email,
        password_hash=hash_password(body.password),
        role=body.role,
        permissions=json.dumps(perms),
        is_active=body.is_active,
        force_pw_change=True,
    )
    db.add(user); db.commit(); db.refresh(user)
    # Auto-assign a member_id if none
    if not user.member_id:
        for _ in range(100):
            mid = str(random.randint(100000, 999999))
            if not db.query(User).filter(User.member_id == mid).first():
                user.member_id = mid
                break
        db.commit(); db.refresh(user)
    return _out(user)


@router.get("/api/users/{uid}")
def get_user(uid: int, _: User = Depends(require_admin), db: Session = Depends(get_db)):
    u = db.get(User, uid)
    if not u: raise HTTPException(404, "User not found")
    return _out(u)


@router.patch("/api/users/{uid}")
def update_user(uid: int, body: UserUpdate, admin: User = Depends(require_admin), db: Session = Depends(get_db)):
    u = db.get(User, uid)
    if not u: raise HTTPException(404, "User not found")
    if uid == admin.id and body.role and body.role != "admin":
        raise HTTPException(400, "Cannot demote yourself")
    if body.full_name is not None: u.full_name = body.full_name
    if body.email is not None: u.email = body.email
    if body.role is not None: u.role = body.role
    if body.is_active is not None: u.is_active = body.is_active
    if body.force_pw_change is not None: u.force_pw_change = body.force_pw_change
    if body.permissions is not None: u.permissions = json.dumps(body.permissions)
    if body.member_id is not None: u.member_id = body.member_id or None
    if body.password:
        if len(body.password) < 8:
            raise HTTPException(400, "Password must be at least 8 characters")
        u.password_hash = hash_password(body.password)
    db.commit(); db.refresh(u)
    return _out(u)


@router.delete("/api/users/{uid}", status_code=204)
def delete_user(uid: int, admin: User = Depends(require_admin), db: Session = Depends(get_db)):
    if uid == admin.id:
        raise HTTPException(400, "Cannot delete your own account")
    u = db.get(User, uid)
    if not u: raise HTTPException(404, "User not found")
    db.delete(u); db.commit()


@router.post("/api/users/{uid}/revoke-sessions", status_code=204)
def admin_revoke_user_sessions(uid: int, admin: User = Depends(require_admin), db: Session = Depends(get_db)):
    """Admin: invalidate all refresh tokens for a user by bumping their token_version."""
    u = db.get(User, uid)
    if not u: raise HTTPException(404, "User not found")
    u.token_version = (u.token_version or 0) + 1
    db.commit()
