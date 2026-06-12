"""
Router: Asset Maintenance Scheduling
  GET    /api/assets/{aid}/maintenance              → schedules + recent logs
  POST   /api/assets/{aid}/maintenance              → create schedule
  PATCH  /api/assets/{aid}/maintenance/{mid}        → update schedule
  DELETE /api/assets/{aid}/maintenance/{mid}        → delete schedule
  POST   /api/assets/{aid}/maintenance/{mid}/complete → mark complete
  GET    /api/maintenance/upcoming                  → all upcoming/overdue (dashboard)
"""
from __future__ import annotations
import json
from datetime import date, timedelta
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session, joinedload

from ..database import get_db
from ..models import Asset, AssetMaintenanceSchedule, AssetMaintenanceLog, AppSetting
from ..notify_helpers import notify_role

from ..auth import get_current_user
router = APIRouter(tags=["maintenance"], dependencies=[Depends(get_current_user)])

_TODAY = lambda: date.today().isoformat()


# ── Helpers ───────────────────────────────────────────────────────────────────

def _warn_days(db: Session) -> int:
    row = db.query(AppSetting).filter(AppSetting.key == "maintenance_warn_days").first()
    try:
        return int(row.value) if row and row.value else 14
    except Exception:
        return 14


def _status(next_due: Optional[str], warn_days: int) -> str:
    if not next_due:
        return "ok"
    today = date.today()
    due   = date.fromisoformat(next_due)
    if due < today:
        return "overdue"
    if due <= today + timedelta(days=warn_days):
        return "due_soon"
    return "ok"


def _schedule_out(s: AssetMaintenanceSchedule, warn_days: int) -> dict:
    return {
        "id":            s.id,
        "asset_id":      s.asset_id,
        "task_name":     s.task_name,
        "interval_days": s.interval_days,
        "next_due":      s.next_due,
        "assigned_to":   s.assigned_to,
        "notes":         s.notes,
        "created_at":    s.created_at.isoformat() if s.created_at else None,
        "status":        _status(s.next_due, warn_days),
        "is_recurring":  s.interval_days is not None,
    }


def _log_out(log: AssetMaintenanceLog) -> dict:
    return {
        "id":          log.id,
        "asset_id":    log.asset_id,
        "schedule_id": log.schedule_id,
        "task_name":   log.task_name,
        "done_at":     log.done_at,
        "done_by":     log.done_by,
        "notes":       log.notes,
        "created_at":  log.created_at.isoformat() if log.created_at else None,
    }


# ── Schemas ───────────────────────────────────────────────────────────────────

class ScheduleCreate(BaseModel):
    task_name:     str
    interval_days: Optional[int] = None   # None = one-time
    next_due:      Optional[str] = None   # YYYY-MM-DD
    assigned_to:   Optional[str] = None
    notes:         Optional[str] = None

class ScheduleUpdate(BaseModel):
    task_name:     Optional[str] = None
    interval_days: Optional[int] = None
    next_due:      Optional[str] = None
    assigned_to:   Optional[str] = None
    notes:         Optional[str] = None

class CompleteBody(BaseModel):
    done_at:   Optional[str] = None   # defaults to today
    done_by:   Optional[str] = None
    notes:     Optional[str] = None
    next_due:  Optional[str] = None   # override auto-calculated next due


# ── Per-asset routes ──────────────────────────────────────────────────────────

@router.get("/api/assets/{aid}/maintenance")
def list_maintenance(aid: int, db: Session = Depends(get_db)):
    if not db.get(Asset, aid):
        raise HTTPException(404, "Asset not found")
    warn = _warn_days(db)
    schedules = (db.query(AssetMaintenanceSchedule)
                 .filter(AssetMaintenanceSchedule.asset_id == aid)
                 .order_by(AssetMaintenanceSchedule.next_due)
                 .all())
    logs = (db.query(AssetMaintenanceLog)
            .filter(AssetMaintenanceLog.asset_id == aid)
            .order_by(AssetMaintenanceLog.done_at.desc())
            .limit(50).all())
    return {
        "schedules": [_schedule_out(s, warn) for s in schedules],
        "logs":      [_log_out(l) for l in logs],
    }


@router.post("/api/assets/{aid}/maintenance", status_code=201)
def create_schedule(aid: int, body: ScheduleCreate, db: Session = Depends(get_db)):
    if not db.get(Asset, aid):
        raise HTTPException(404, "Asset not found")
    s = AssetMaintenanceSchedule(
        asset_id=aid,
        task_name=body.task_name,
        interval_days=body.interval_days,
        next_due=body.next_due,
        assigned_to=body.assigned_to,
        notes=body.notes,
    )
    db.add(s); db.commit(); db.refresh(s)
    return _schedule_out(s, _warn_days(db))


@router.patch("/api/assets/{aid}/maintenance/{mid}")
def update_schedule(aid: int, mid: int, body: ScheduleUpdate, db: Session = Depends(get_db)):
    s = db.query(AssetMaintenanceSchedule).filter(
        AssetMaintenanceSchedule.id == mid,
        AssetMaintenanceSchedule.asset_id == aid,
    ).first()
    if not s:
        raise HTTPException(404, "Schedule not found")
    for k, v in body.model_dump(exclude_none=True).items():
        setattr(s, k, v)
    db.commit(); db.refresh(s)
    return _schedule_out(s, _warn_days(db))


@router.delete("/api/assets/{aid}/maintenance/{mid}", status_code=204)
def delete_schedule(aid: int, mid: int, db: Session = Depends(get_db)):
    s = db.query(AssetMaintenanceSchedule).filter(
        AssetMaintenanceSchedule.id == mid,
        AssetMaintenanceSchedule.asset_id == aid,
    ).first()
    if not s:
        raise HTTPException(404, "Schedule not found")
    db.delete(s); db.commit()


@router.post("/api/assets/{aid}/maintenance/{mid}/complete")
def complete_schedule(aid: int, mid: int, body: CompleteBody, db: Session = Depends(get_db)):
    s = db.query(AssetMaintenanceSchedule).filter(
        AssetMaintenanceSchedule.id == mid,
        AssetMaintenanceSchedule.asset_id == aid,
    ).first()
    if not s:
        raise HTTPException(404, "Schedule not found")

    done_at = body.done_at or _TODAY()

    # Log the completion
    log = AssetMaintenanceLog(
        asset_id=aid,
        schedule_id=mid,
        task_name=s.task_name,
        done_at=done_at,
        done_by=body.done_by,
        notes=body.notes,
    )
    db.add(log)

    # Notify that maintenance was completed
    asset = db.get(Asset, aid)
    notify_role(db, "assets",
                f"🔧 Maintenance Completed: {s.task_name}",
                f"Asset: {asset.name if asset else aid}. Done by: {body.done_by or 'unknown'}.",
                level="success", source_type="asset", source_id=aid)

    # Calculate next due date for recurring schedules
    if s.interval_days:
        if body.next_due:
            s.next_due = body.next_due
        else:
            base = date.fromisoformat(done_at)
            s.next_due = (base + timedelta(days=s.interval_days)).isoformat()
    else:
        # One-time: clear the due date (task done)
        s.next_due = None

    db.commit(); db.refresh(s)
    warn = _warn_days(db)
    return {
        "schedule": _schedule_out(s, warn),
        "log":      _log_out(log),
    }


# ── Dashboard: upcoming / overdue across all assets ───────────────────────────

@router.get("/api/maintenance/upcoming")
def upcoming_maintenance(db: Session = Depends(get_db)):
    warn = _warn_days(db)
    schedules = (db.query(AssetMaintenanceSchedule)
                 .options(joinedload(AssetMaintenanceSchedule.asset))
                 .filter(AssetMaintenanceSchedule.next_due.isnot(None))
                 .order_by(AssetMaintenanceSchedule.next_due)
                 .all())
    result = []
    for s in schedules:
        st = _status(s.next_due, warn)
        if st in ("overdue", "due_soon"):
            out = _schedule_out(s, warn)
            out["asset_name"] = s.asset.name if s.asset else "?"
            out["asset_tag"]  = s.asset.asset_tag if s.asset else None
            result.append(out)
    return {"items": result, "warn_days": warn}
