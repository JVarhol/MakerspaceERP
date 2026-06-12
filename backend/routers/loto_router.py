"""
LOTO (Lockout / Tag-out) Router
  GET    /api/loto                      → list all records (filter: ?asset_id=)
  POST   /api/loto                      → create record
  GET    /api/loto/{id}                 → get record + active lockouts
  PUT    /api/loto/{id}                 → update record
  DELETE /api/loto/{id}                 → delete record
  POST   /api/loto/{id}/lockout         → start a lockout event
  POST   /api/loto/{id}/release/{lid}   → release a lockout
  GET    /api/loto/{id}/lockouts        → list lockout events for a record
  GET    /api/loto/active               → all currently active lockouts (with asset info)
"""
from __future__ import annotations
import json
from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session, joinedload

from ..database import get_db
from ..models import LotoRecord, LotoLockout, Asset
from ..notify_helpers import notify_role
from ..auth import get_current_user

router = APIRouter(tags=["loto"], dependencies=[Depends(get_current_user)])


# ── Schemas ───────────────────────────────────────────────────────────────────

class LotoRecordCreate(BaseModel):
    title:           str
    asset_id:        Optional[int]  = None
    machine_name:    Optional[str]  = None
    machine_id:      Optional[str]  = None
    location:        Optional[str]  = None
    department:      Optional[str]  = None
    status:          Optional[str]  = "draft"
    procedure_steps: Optional[list] = None
    energy_sources:  Optional[list] = None
    ppe_required:    Optional[list] = None
    authorized_by:   Optional[str]  = None
    reviewed_by:     Optional[str]  = None
    review_date:     Optional[str]  = None
    notes:           Optional[str]  = None

class LotoRecordUpdate(LotoRecordCreate):
    title: Optional[str] = None

class LockoutCreate(BaseModel):
    locked_by: str
    notes:     Optional[str] = None


# ── Helpers ───────────────────────────────────────────────────────────────────

def _record_out(r: LotoRecord, include_lockouts: bool = False) -> dict:
    active_lockouts = [l for l in (r.lockouts or []) if l.released_at is None]
    d = {
        "id":              r.id,
        "title":           r.title,
        "asset_id":        r.asset_id,
        "asset_name":      r.asset.name if r.asset else None,
        "asset_tag":       r.asset.asset_tag if r.asset else None,
        "machine_name":    r.machine_name,
        "machine_id":      r.machine_id,
        "location":        r.location,
        "department":      r.department,
        "status":          r.status,
        "procedure_steps": json.loads(r.procedure_steps or "[]"),
        "energy_sources":  json.loads(r.energy_sources  or "[]"),
        "ppe_required":    json.loads(r.ppe_required     or "[]"),
        "authorized_by":   r.authorized_by,
        "reviewed_by":     r.reviewed_by,
        "review_date":     r.review_date,
        "notes":           r.notes,
        "created_by":      r.created_by,
        "created_at":      r.created_at.isoformat() if r.created_at else None,
        "updated_at":      r.updated_at.isoformat() if r.updated_at else None,
        "active_lockout_count": len(active_lockouts),
        "is_locked_out":   len(active_lockouts) > 0,
    }
    if include_lockouts:
        d["lockouts"] = [_lockout_out(l) for l in (r.lockouts or [])]
        d["active_lockouts"] = [_lockout_out(l) for l in active_lockouts]
    return d

def _lockout_out(l: LotoLockout) -> dict:
    return {
        "id":          l.id,
        "record_id":   l.record_id,
        "locked_by":   l.locked_by,
        "locked_at":   l.locked_at.isoformat() if l.locked_at else None,
        "released_at": l.released_at.isoformat() if l.released_at else None,
        "active":      l.released_at is None,
        "notes":       l.notes,
    }

def _q(db):
    return (db.query(LotoRecord)
              .options(joinedload(LotoRecord.asset),
                       joinedload(LotoRecord.lockouts)))


# ── Routes ────────────────────────────────────────────────────────────────────

@router.get("/api/loto/active")
def list_active_lockouts(db: Session = Depends(get_db)):
    """All currently active (unreleased) lockouts across all records."""
    lockouts = (db.query(LotoLockout)
                  .filter(LotoLockout.released_at == None)
                  .options(joinedload(LotoLockout.record).joinedload(LotoRecord.asset))
                  .all())
    result = []
    for lo in lockouts:
        d = _lockout_out(lo)
        d["record_title"] = lo.record.title if lo.record else None
        d["asset_id"]     = lo.record.asset_id if lo.record else None
        d["asset_name"]   = lo.record.asset.name if (lo.record and lo.record.asset) else None
        result.append(d)
    return result


@router.get("/api/loto")
def list_records(asset_id: Optional[int] = Query(None),
                 db: Session = Depends(get_db)):
    q = _q(db)
    if asset_id is not None:
        q = q.filter(LotoRecord.asset_id == asset_id)
    records = q.order_by(LotoRecord.updated_at.desc()).all()
    return [_record_out(r) for r in records]


@router.post("/api/loto", status_code=201)
def create_record(body: LotoRecordCreate, db: Session = Depends(get_db),
                  current_user=Depends(get_current_user)):
    r = LotoRecord(
        title=body.title,
        asset_id=body.asset_id,
        machine_name=body.machine_name,
        machine_id=body.machine_id,
        location=body.location,
        department=body.department,
        status=body.status or "draft",
        procedure_steps=json.dumps(body.procedure_steps or []),
        energy_sources=json.dumps(body.energy_sources   or []),
        ppe_required=json.dumps(body.ppe_required        or []),
        authorized_by=body.authorized_by,
        reviewed_by=body.reviewed_by,
        review_date=body.review_date,
        notes=body.notes,
        created_by=current_user.username,
    )
    db.add(r); db.commit(); db.refresh(r)
    return _record_out(_q(db).filter(LotoRecord.id == r.id).first())


@router.get("/api/loto/{rid}")
def get_record(rid: int, db: Session = Depends(get_db)):
    r = _q(db).filter(LotoRecord.id == rid).first()
    if not r:
        raise HTTPException(404, "Record not found")
    return _record_out(r, include_lockouts=True)


@router.put("/api/loto/{rid}")
def update_record(rid: int, body: LotoRecordUpdate, db: Session = Depends(get_db),
                  current_user=Depends(get_current_user)):
    r = db.get(LotoRecord, rid)
    if not r:
        raise HTTPException(404, "Record not found")
    if current_user.role != "admin" and r.created_by != current_user.username:
        raise HTTPException(403, "You can only edit LOTO records you created")
    for k, v in body.model_dump(exclude_none=True).items():
        if k in ("procedure_steps", "energy_sources", "ppe_required"):
            setattr(r, k, json.dumps(v))
        else:
            setattr(r, k, v)
    db.commit()
    return _record_out(_q(db).filter(LotoRecord.id == rid).first(), include_lockouts=True)


@router.delete("/api/loto/{rid}", status_code=204)
def delete_record(rid: int, db: Session = Depends(get_db),
                  current_user=Depends(get_current_user)):
    r = db.get(LotoRecord, rid)
    if not r:
        raise HTTPException(404, "Record not found")
    if current_user.role != "admin" and r.created_by != current_user.username:
        raise HTTPException(403, "You can only delete LOTO records you created")
    db.delete(r); db.commit()


@router.get("/api/loto/{rid}/lockouts")
def list_lockouts(rid: int, db: Session = Depends(get_db)):
    lockouts = (db.query(LotoLockout)
                  .filter(LotoLockout.record_id == rid)
                  .order_by(LotoLockout.locked_at.desc())
                  .all())
    return [_lockout_out(l) for l in lockouts]


@router.post("/api/loto/{rid}/lockout", status_code=201)
def start_lockout(rid: int, body: LockoutCreate, db: Session = Depends(get_db)):
    r = db.get(LotoRecord, rid)
    if not r:
        raise HTTPException(404, "Record not found")
    lo = LotoLockout(record_id=rid, locked_by=body.locked_by, notes=body.notes)
    db.add(lo)
    db.commit()
    db.refresh(lo)
    # Notify users with loto_manage permission
    asset_info = f" on {r.asset.name}" if r.asset else ""
    notify_role(db, "loto_manage",
                f"🔒 LOTO Lockout Started: {r.title}{asset_info}",
                f"Locked out by {body.locked_by}. {body.notes or ''}".strip(),
                level="warning", source_type="loto_record", source_id=rid)
    db.commit()
    return _lockout_out(lo)


@router.post("/api/loto/{rid}/release/{lid}")
def release_lockout(rid: int, lid: int, db: Session = Depends(get_db)):
    lo = db.query(LotoLockout).filter(
        LotoLockout.id == lid, LotoLockout.record_id == rid).first()
    if not lo:
        raise HTTPException(404, "Lockout not found")
    lo.released_at = datetime.utcnow()
    db.commit()
    db.refresh(lo)
    r2 = _q(db).filter(LotoRecord.id == rid).first()
    asset_info2 = f" on {r2.asset.name}" if (r2 and r2.asset) else ""
    notify_role(db, "loto_manage",
                f"🔓 LOTO Released: {r2.title if r2 else rid}{asset_info2}",
                f"Released by lockout #{lid}.",
                level="info", source_type="loto_record", source_id=rid)
    db.commit()
    return _lockout_out(lo)
