"""
Router: Member Check-In / Check-Out
  POST /api/checkin/scan           - scan member_id → toggle in or out
  GET  /api/checkin/active         - currently checked-in members
  GET  /api/checkin/sessions       - history (admin: all; user: own)
  GET  /api/checkin/stats          - hourly/daily aggregates for graph
  GET  /api/checkin/lookup         - search by member_id or username (admin)
  PATCH /api/checkin/{sid}/checkout - admin: manually check out a session
  POST /api/checkin/generate-member-id - admin: assign auto-generated member_id
"""
from __future__ import annotations
from datetime import datetime, timezone
from typing import Optional
import random, string

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..database import get_db
from ..auth import get_current_user
from ..models import User, MemberCheckIn

router = APIRouter(prefix="/api/checkin", tags=["checkin"],
                   dependencies=[Depends(get_current_user)])


# ── helpers ────────────────────────────────────────────────────────────────────

def _session_out(s: MemberCheckIn) -> dict:
    return {
        "id":               s.id,
        "username":         s.username,
        "member_id":        s.member_id,
        "checked_in_at":    s.checked_in_at.isoformat() if s.checked_in_at else None,
        "checked_out_at":   s.checked_out_at.isoformat() if s.checked_out_at else None,
        "duration_minutes": s.duration_minutes,
        "notes":            s.notes,
    }


def _now_utc() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _generate_member_id(db: Session) -> str:
    """Generate a unique 6-digit member ID not already in use."""
    for _ in range(100):
        mid = str(random.randint(100000, 999999))
        if not db.query(User).filter(User.member_id == mid).first():
            return mid
    raise RuntimeError("Could not generate unique member ID")


def _do_checkout(s: MemberCheckIn) -> None:
    now = _now_utc()
    s.checked_out_at = now
    delta = (now - s.checked_in_at).total_seconds() / 60.0
    s.duration_minutes = round(delta, 1)


# ── schemas ────────────────────────────────────────────────────────────────────

class ScanIn(BaseModel):
    member_id: str
    notes: Optional[str] = None


class CheckoutPatch(BaseModel):
    notes: Optional[str] = None


# ── endpoints ─────────────────────────────────────────────────────────────────

@router.post("/scan")
def scan(body: ScanIn,
         _cu: User = Depends(get_current_user),
         db: Session = Depends(get_db)):
    """
    Look up a member_id; toggle check-in or check-out.
    Non-admins may only scan their OWN member_id.
    """
    target = db.query(User).filter(User.member_id == body.member_id).first()
    if not target:
        raise HTTPException(404, f"No user found with member ID {body.member_id}")

    # Permission: non-admins can only scan their own ID
    if _cu.role != "admin" and target.username != _cu.username:
        raise HTTPException(403, "You can only scan your own member ID")

    # Is there an open session?
    active = db.query(MemberCheckIn).filter(
        MemberCheckIn.username == target.username,
        MemberCheckIn.checked_out_at.is_(None),
    ).first()

    if active:
        # Check OUT
        _do_checkout(active)
        if body.notes:
            active.notes = body.notes
        db.commit()
        db.refresh(active)
        return {"action": "out", "session": _session_out(active),
                "full_name": target.full_name or target.username}
    else:
        # Check IN
        s = MemberCheckIn(
            username=target.username,
            member_id=body.member_id,
            checked_in_at=_now_utc(),
            notes=body.notes,
        )
        db.add(s)
        db.commit()
        db.refresh(s)
        return {"action": "in", "session": _session_out(s),
                "full_name": target.full_name or target.username}


@router.get("/active")
def list_active(_cu: User = Depends(get_current_user),
                db: Session = Depends(get_db)):
    """Currently checked-in members. All authenticated users see who is in the space."""
    q = db.query(MemberCheckIn).filter(MemberCheckIn.checked_out_at.is_(None))
    rows = q.order_by(MemberCheckIn.checked_in_at).all()
    out = []
    for s in rows:
        d = _session_out(s)
        u = db.query(User).filter(User.username == s.username).first()
        d["full_name"] = u.full_name if u else s.username
        out.append(d)
    return out


@router.get("/me")
def my_status(_cu: User = Depends(get_current_user),
              db: Session = Depends(get_db)):
    """Return the current user's check-in status."""
    active = db.query(MemberCheckIn).filter(
        MemberCheckIn.username == _cu.username,
        MemberCheckIn.checked_out_at.is_(None),
    ).first()
    return {
        "checked_in":   active is not None,
        "session_id":   active.id if active else None,
        "checked_in_at": active.checked_in_at.isoformat() if active else None,
        "member_id":    _cu.member_id,
    }


@router.get("/sessions")
def list_sessions(
    username: Optional[str] = Query(None),
    limit: int = Query(100, le=500),
    _cu: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Session history. Non-admins are restricted to their own sessions."""
    q = db.query(MemberCheckIn)
    if _cu.role != "admin":
        q = q.filter(MemberCheckIn.username == _cu.username)
    elif username:
        q = q.filter(MemberCheckIn.username == username)
    rows = q.order_by(MemberCheckIn.checked_in_at.desc()).limit(limit).all()
    out = []
    for s in rows:
        d = _session_out(s)
        u = db.query(User).filter(User.username == s.username).first()
        d["full_name"] = u.full_name if u else s.username
        out.append(d)
    return out


@router.get("/stats")
def get_stats(_cu: User = Depends(get_current_user),
              db: Session = Depends(get_db)):
    """
    Returns hourly_counts (0-23) and daily_counts (0=Mon … 6=Sun)
    based on check_in timestamps of all completed sessions.
    """
    rows = (
        db.query(MemberCheckIn)
        .filter(MemberCheckIn.checked_out_at.isnot(None))
        .all()
    )
    hourly = [0] * 24
    daily  = [0] * 7
    for s in rows:
        dt = s.checked_in_at
        if dt:
            hourly[dt.hour] += 1
            daily[dt.weekday()] += 1   # 0=Monday
    return {"hourly": hourly, "daily": daily, "total_sessions": len(rows)}


@router.get("/lookup")
def lookup(q: str = Query(..., min_length=1),
           _cu: User = Depends(get_current_user),
           db: Session = Depends(get_db)):
    """Search users by member_id or username substring. Admin only."""
    if _cu.role != "admin":
        raise HTTPException(403, "Admin only")
    from sqlalchemy import or_
    users = (
        db.query(User)
        .filter(or_(
            User.member_id.ilike(f"%{q}%"),
            User.username.ilike(f"%{q}%"),
            User.full_name.ilike(f"%{q}%"),
        ))
        .limit(20)
        .all()
    )
    results = []
    for u in users:
        active = db.query(MemberCheckIn).filter(
            MemberCheckIn.username == u.username,
            MemberCheckIn.checked_out_at.is_(None),
        ).first()
        last = (
            db.query(MemberCheckIn)
            .filter(MemberCheckIn.username == u.username,
                    MemberCheckIn.checked_out_at.isnot(None))
            .order_by(MemberCheckIn.checked_in_at.desc())
            .first()
        )
        results.append({
            "username":    u.username,
            "full_name":   u.full_name,
            "member_id":   u.member_id,
            "checked_in":  active is not None,
            "active_since": active.checked_in_at.isoformat() if active else None,
            "last_visit":   last.checked_in_at.isoformat() if last else None,
        })
    return results


@router.patch("/{sid}/checkout")
def manual_checkout(sid: int, body: CheckoutPatch,
                    _cu: User = Depends(get_current_user),
                    db: Session = Depends(get_db)):
    """Check out a session. Admins can check out anyone; users can only check out their own session."""
    s = db.query(MemberCheckIn).filter(MemberCheckIn.id == sid).first()
    if not s:
        raise HTTPException(404, "Session not found")
    if _cu.role != "admin" and s.username != _cu.username:
        raise HTTPException(403, "You can only check out your own session")
    if s.checked_out_at:
        raise HTTPException(400, "Session already closed")
    _do_checkout(s)
    if body.notes:
        s.notes = body.notes
    db.commit()
    db.refresh(s)
    return _session_out(s)


@router.post("/generate-member-id")
def generate_id_for_user(
    username: str = Query(...),
    _cu: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Admin: assign an auto-generated member_id to a user."""
    if _cu.role != "admin":
        raise HTTPException(403, "Admin only")
    u = db.query(User).filter(User.username == username).first()
    if not u:
        raise HTTPException(404, "User not found")
    if not u.member_id:
        u.member_id = _generate_member_id(db)
        db.commit()
    retu