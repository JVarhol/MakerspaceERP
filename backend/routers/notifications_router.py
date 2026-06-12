"""
Notifications Router
  GET    /api/notifications            → get my notifications (unread first)
  POST   /api/notifications/{id}/read  → mark one read
  POST   /api/notifications/read-all   → mark all mine read
  DELETE /api/notifications/{id}       → delete one
  GET    /api/notifications/count      → unread count (for badge)
"""
from __future__ import annotations
from typing import Optional

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import Notification
from ..auth import get_current_user

router = APIRouter(tags=["notifications"], dependencies=[Depends(get_current_user)])


def _out(n: Notification) -> dict:
    return {
        "id":          n.id,
        "user_id":     n.user_id,
        "title":       n.title,
        "body":        n.body,
        "level":       n.level,
        "source_type": n.source_type,
        "source_id":   n.source_id,
        "is_read":     n.is_read,
        "created_at":  n.created_at.isoformat() if n.created_at else None,
    }


@router.get("/api/notifications")
def get_notifications(db: Session = Depends(get_db),
                      current_user=Depends(get_current_user)):
    notifs = (db.query(Notification)
                .filter(Notification.user_id == current_user.id)
                .order_by(Notification.is_read, Notification.created_at.desc())
                .limit(100)
                .all())
    return [_out(n) for n in notifs]


@router.get("/api/notifications/count")
def count_notifications(db: Session = Depends(get_db),
                        current_user=Depends(get_current_user)):
    count = (db.query(Notification)
               .filter(Notification.user_id == current_user.id,
                       Notification.is_read == False)
               .count())
    return {"unread": count}


@router.post("/api/notifications/{nid}/read")
def mark_read(nid: int, db: Session = Depends(get_db),
              current_user=Depends(get_current_user)):
    n = db.query(Notification).filter(
        Notification.id == nid,
        Notification.user_id == current_user.id,
    ).first()
    if n:
        n.is_read = True
        db.commit()
    return {"ok": True}


@router.post("/api/notifications/read-all")
def mark_all_read(db: Session = Depends(get_db),
                  current_user=Depends(get_current_user)):
    (db.query(Notification)
       .filter(Notification.user_id == current_user.id,
               Notification.is_read == False)
       .update({"is_read": True}))
    db.commit()
    return {"ok": True}


@router.delete("/api/notifications/{nid}", status_code=204)
def delete_notification(nid: int, db: Session = Depends(get_db),
                        current_user=Depends(get_current_user)):
    n = db.query(Notification).filter(
        Notification.id == nid,
        Notification.user_id == current_user.id,
    ).first()
    if n:
        db.delete(n); db.commit()
