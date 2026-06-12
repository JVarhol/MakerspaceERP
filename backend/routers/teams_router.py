"""
Teams Router
  GET    /api/teams              → list teams
  POST   /api/teams              → create team
  GET    /api/teams/{id}         → get team + members
  PATCH  /api/teams/{id}         → update team
  DELETE /api/teams/{id}         → delete team
  POST   /api/teams/{id}/members → add member
  DELETE /api/teams/{id}/members/{uid} → remove member
  GET    /api/teams/{id}/notify  → send notification to team
"""
from __future__ import annotations
import json
from typing import Optional, List

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session, joinedload

from ..database import get_db
from ..models import Team, TeamMember, User, Notification
from ..auth import get_current_user, require_admin

router = APIRouter(tags=["teams"], dependencies=[Depends(get_current_user)])


class TeamCreate(BaseModel):
    name:        str
    description: Optional[str] = None
    color:       Optional[str] = "#6366f1"

class TeamUpdate(BaseModel):
    name:        Optional[str] = None
    description: Optional[str] = None
    color:       Optional[str] = None

class MemberAdd(BaseModel):
    user_id: int
    role:    Optional[str] = "member"

class TeamNotify(BaseModel):
    title:       str
    body:        Optional[str] = None
    level:       Optional[str] = "info"
    source_type: Optional[str] = None
    source_id:   Optional[int] = None


def _member_out(m: TeamMember) -> dict:
    return {
        "id":       m.id,
        "team_id":  m.team_id,
        "user_id":  m.user_id,
        "role":     m.role,
        "username": m.user.username if m.user else None,
        "full_name":m.user.full_name if m.user else None,
    }

def _team_out(t: Team, include_members: bool = True) -> dict:
    d = {
        "id":          t.id,
        "name":        t.name,
        "description": t.description,
        "color":       t.color,
        "created_at":  t.created_at.isoformat() if t.created_at else None,
        "member_count": len(t.members),
    }
    if include_members:
        d["members"] = [_member_out(m) for m in t.members]
    return d

def _q(db):
    return db.query(Team).options(
        joinedload(Team.members).joinedload(TeamMember.user)
    )


@router.get("/api/teams")
def list_teams(db: Session = Depends(get_db)):
    return [_team_out(t) for t in _q(db).order_by(Team.name).all()]


@router.post("/api/teams", status_code=201)
def create_team(body: TeamCreate, _=Depends(require_admin), db: Session = Depends(get_db)):
    if db.query(Team).filter(Team.name == body.name).first():
        raise HTTPException(400, "Team name already exists")
    t = Team(name=body.name, description=body.description, color=body.color or "#6366f1")
    db.add(t); db.commit(); db.refresh(t)
    return _team_out(_q(db).filter(Team.id == t.id).first())


@router.get("/api/teams/{tid}")
def get_team(tid: int, db: Session = Depends(get_db)):
    t = _q(db).filter(Team.id == tid).first()
    if not t: raise HTTPException(404, "Team not found")
    return _team_out(t)


@router.patch("/api/teams/{tid}")
def update_team(tid: int, body: TeamUpdate, _=Depends(require_admin), db: Session = Depends(get_db)):
    t = db.get(Team, tid)
    if not t: raise HTTPException(404, "Team not found")
    if body.name is not None:        t.name        = body.name
    if body.description is not None: t.description = body.description
    if body.color is not None:       t.color       = body.color
    db.commit()
    return _team_out(_q(db).filter(Team.id == tid).first())


@router.delete("/api/teams/{tid}", status_code=204)
def delete_team(tid: int, _=Depends(require_admin), db: Session = Depends(get_db)):
    t = db.get(Team, tid)
    if not t: raise HTTPException(404, "Team not found")
    db.delete(t); db.commit()


@router.post("/api/teams/{tid}/members", status_code=201)
def add_member(tid: int, body: MemberAdd, _=Depends(require_admin), db: Session = Depends(get_db)):
    if not db.get(Team, tid): raise HTTPException(404, "Team not found")
    if not db.get(User, body.user_id): raise HTTPException(404, "User not found")
    existing = db.query(TeamMember).filter(
        TeamMember.team_id == tid, TeamMember.user_id == body.user_id).first()
    if existing:
        existing.role = body.role or "member"
        db.commit(); db.refresh(existing)
        return _member_out(existing)
    m = TeamMember(team_id=tid, user_id=body.user_id, role=body.role or "member")
    db.add(m); db.commit(); db.refresh(m)
    return _member_out(m)


@router.delete("/api/teams/{tid}/members/{uid}", status_code=204)
def remove_member(tid: int, uid: int, _=Depends(require_admin), db: Session = Depends(get_db)):
    m = db.query(TeamMember).filter(
        TeamMember.team_id == tid, TeamMember.user_id == uid).first()
    if not m: raise HTTPException(404, "Member not found")
    db.delete(m); db.commit()


@router.post("/api/teams/{tid}/notify")
def notify_team(tid: int, body: TeamNotify,
                current_user=Depends(get_current_user),
                db: Session = Depends(get_db)):
    """Send a notification to every member of a team."""
    t = _q(db).filter(Team.id == tid).first()
    if not t: raise HTTPException(404, "Team not found")
    sent = 0
    for m in t.members:
        n = Notification(
            user_id=m.user_id,
            title=body.title,
            body=body.body,
            level=body.level or "info",
            source_type=body.source_type,
            source_id=body.source_id,
        )
        db.add(n)
        sent += 1
    db.commit()
    return {"sent": sent}
