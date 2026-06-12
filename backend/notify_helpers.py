"""
Shared notification helpers used across multiple routers.
"""
from __future__ import annotations
import json
from typing import Optional

from sqlalchemy.orm import Session
from .models import Notification, User


def notify_user(db: Session, user_id: int, title: str, body: str = None,
                level: str = "info", source_type: str = None, source_id: int = None):
    """Send a notification to a specific user."""
    n = Notification(
        user_id=user_id, title=title, body=body, level=level,
        source_type=source_type, source_id=source_id,
    )
    db.add(n)


def notify_role(db: Session, role_flag: str, title: str, body: str = None,
                level: str = "info", source_type: str = None, source_id: int = None):
    """
    Notify all users whose permissions JSON contains role_flag: true.
    Also notifies admins.
    """
    users = db.query(User).filter(User.is_active == True).all()
    for u in users:
        try:
            perms = json.loads(u.permissions or "{}")
        except Exception:
            perms = {}
        is_admin = (u.role == "admin")
        has_flag = perms.get(role_flag, {}).get("read", False) if isinstance(perms.get(role_flag), dict) else bool(perms.get(role_flag, False))
        if is_admin or has_flag:
            notify_user(db, u.id, title, body, level, source_type, source_id)


def notify_team(db: Session, team_id: int, title: str, body: str = None,
                level: str = "info", source_type: str = None, source_id: int = None):
    """Notify all members of a team."""
    from .models import TeamMember
    members = db.query(TeamMember).filter(TeamMember.team_id == team_id).all()
    for m in members:
        notify_user(db, m.user_id, title, body, level, source_type, source_id)
