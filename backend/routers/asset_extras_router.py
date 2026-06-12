"""
Router: Asset Extras — Machine Booking, Certifications, Incident Log
  GET  /api/assets/{id}/bookings            - list bookings for asset
  POST /api/assets/{id}/bookings            - create booking
  PATCH /api/assets/{id}/bookings/{bid}     - update (cancel/status)
  DELETE /api/assets/{id}/bookings/{bid}    - delete booking

  GET  /api/assets/bookings/all             - upcoming bookings across all assets (calendar view)

  GET  /api/assets/{id}/certifications      - list certified users for asset
  POST /api/assets/{id}/certifications      - add certification
  DELETE /api/assets/{id}/certifications/{cid} - revoke certification
  GET  /api/assets/certifications/mine      - assets the current user is certified on

  GET  /api/assets/{id}/incidents           - list incidents for asset
  POST /api/assets/{id}/incidents           - log new incident
  PATCH /api/assets/{id}/incidents/{iid}    - resolve / update incident
  DELETE /api/assets/{id}/incidents/{iid}   - delete incident
"""
from __future__ import annotations
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..database import get_db
from ..auth import get_current_user, require_permission
from ..models import Asset, AssetBooking, AssetCertification, AssetIncident

router = APIRouter(prefix="/api/assets", tags=["asset-extras"],
                   dependencies=[Depends(get_current_user)])

_W = Depends(require_permission('assets', 'write'))


# ── Pydantic schemas ────────────────────────────────────────────────────────────

class BookingIn(BaseModel):
    username:  str
    title:     Optional[str] = None
    start_dt:  str
    end_dt:    str
    notes:     Optional[str] = None
    status:    Optional[str] = "upcoming"

class BookingPatch(BaseModel):
    title:    Optional[str] = None
    start_dt: Optional[str] = None
    end_dt:   Optional[str] = None
    notes:    Optional[str] = None
    status:   Optional[str] = None

class CertIn(BaseModel):
    username:     str
    certified_by: Optional[str] = None
    certified_at: Optional[str] = None
    expires_at:   Optional[str] = None
    notes:        Optional[str] = None

class IncidentIn(BaseModel):
    reported_by:   str
    incident_type: Optional[str] = "other"
    severity:      Optional[str] = "low"
    description:   str
    out_of_service: Optional[bool] = False

class IncidentPatch(BaseModel):
    incident_type:    Optional[str] = None
    severity:         Optional[str] = None
    description:      Optional[str] = None
    out_of_service:   Optional[bool] = None
    resolved:         Optional[bool] = None
    resolved_at:      Optional[str] = None
    resolved_by:      Optional[str] = None
    resolution_notes: Optional[str] = None


def _asset_or_404(db: Session, asset_id: int) -> Asset:
    a = db.query(Asset).filter(Asset.id == asset_id).first()
    if not a:
        raise HTTPException(404, f"Asset {asset_id} not found")
    return a


def _booking_dict(b: AssetBooking) -> dict:
    return {
        "id": b.id, "asset_id": b.asset_id, "username": b.username,
        "title": b.title, "start_dt": b.start_dt, "end_dt": b.end_dt,
        "notes": b.notes, "status": b.status,
        "created_at": b.created_at.isoformat() if b.created_at else None,
        "asset_name": b.asset.name if b.asset else None,
    }


def _cert_dict(c: AssetCertification) -> dict:
    return {
        "id": c.id, "asset_id": c.asset_id, "username": c.username,
        "certified_by": c.certified_by, "certified_at": c.certified_at,
        "expires_at": c.expires_at, "notes": c.notes,
    }


def _incident_dict(i: AssetIncident) -> dict:
    return {
        "id": i.id, "asset_id": i.asset_id, "reported_by": i.reported_by,
        "incident_type": i.incident_type, "severity": i.severity,
        "description": i.description, "out_of_service": i.out_of_service,
        "resolved": i.resolved, "resolved_at": i.resolved_at,
        "resolved_by": i.resolved_by, "resolution_notes": i.resolution_notes,
        "created_at": i.created_at.isoformat() if i.created_at else None,
    }


# ── Bookings ───────────────────────────────────────────────────────────────────

@router.get("/bookings/all")
def list_all_bookings(db: Session = Depends(get_db)):
    """All upcoming/active bookings across every asset (for calendar view)."""
    now = datetime.now(timezone.utc).isoformat()
    rows = (
        db.query(AssetBooking)
        .join(Asset)
        .filter(AssetBooking.status.in_(["upcoming", "active"]))
        .order_by(AssetBooking.start_dt)
        .all()
    )
    return [_booking_dict(b) for b in rows]


@router.get("/{asset_id}/bookings")
def list_bookings(asset_id: int, db: Session = Depends(get_db)):
    _asset_or_404(db, asset_id)
    rows = (
        db.query(AssetBooking)
        .filter(AssetBooking.asset_id == asset_id)
        .order_by(AssetBooking.start_dt)
        .all()
    )
    return [_booking_dict(b) for b in rows]


@router.post("/{asset_id}/bookings")
def create_booking(asset_id: int, body: BookingIn,
                   _cu=Depends(get_current_user), db: Session = Depends(get_db)):
    _asset_or_404(db, asset_id)
    # Certification check (if booking for self and user is not admin)
    if _cu.role != "admin" and body.username == _cu.username:
        from datetime import date
        cert = db.query(AssetCertification).filter(
            AssetCertification.asset_id == asset_id,
            AssetCertification.username == _cu.username,
        ).first()
        if not cert:
            raise HTTPException(403, "You are not certified to book this machine")
        if cert.expires_at:
            try:
                exp = date.fromisoformat(cert.expires_at[:10])
                if exp < date.today():
                    raise HTTPException(403, f"Your certification expired on {cert.expires_at[:10]}")
            except ValueError:
                pass
    # Overlap check (same asset, non-cancelled)
    overlaps = (
        db.query(AssetBooking)
        .filter(
            AssetBooking.asset_id == asset_id,
            AssetBooking.status.notin_(["cancelled", "complete"]),
            AssetBooking.start_dt < body.end_dt,
            AssetBooking.end_dt   > body.start_dt,
        )
        .first()
    )
    if overlaps:
        raise HTTPException(
            409,
            f"Time slot conflicts with existing booking by {overlaps.username} "
            f"({overlaps.start_dt[:16]} – {overlaps.end_dt[:16]})"
        )
    b = AssetBooking(asset_id=asset_id, **body.model_dump())
    db.add(b)
    db.commit()
    db.refresh(b)
    return _booking_dict(b)


@router.patch("/{asset_id}/bookings/{bid}")
def update_booking(asset_id: int, bid: int, body: BookingPatch,
                   _cu=Depends(get_current_user), db: Session = Depends(get_db)):
    b = db.query(AssetBooking).filter(
        AssetBooking.id == bid, AssetBooking.asset_id == asset_id).first()
    if not b:
        raise HTTPException(404, "Booking not found")
    if _cu.role != "admin" and b.username != _cu.username:
        raise HTTPException(403, "You can only modify your own bookings")
    for k, v in body.model_dump(exclude_none=True).items():
        setattr(b, k, v)
    db.commit()
    db.refresh(b)
    return _booking_dict(b)


@router.delete("/{asset_id}/bookings/{bid}")
def delete_booking(asset_id: int, bid: int, _w=_W, db: Session = Depends(get_db)):
    b = db.query(AssetBooking).filter(
        AssetBooking.id == bid, AssetBooking.asset_id == asset_id).first()
    if not b:
        raise HTTPException(404, "Booking not found")
    db.delete(b)
    db.commit()
    return {"ok": True}


# ── Certifications ─────────────────────────────────────────────────────────────

@router.get("/certifications/all")
def all_certifications(_cu=Depends(get_current_user), db: Session = Depends(get_db)):
    """Admin: all certifications across all assets, enriched with asset name."""
    from ..auth import require_admin
    if _cu.role != "admin":
        from fastapi import HTTPException
        raise HTTPException(403, "Admin only")
    rows = db.query(AssetCertification).join(Asset).order_by(Asset.name, AssetCertification.username).all()
    out = []
    for cert in rows:
        d = _cert_dict(cert)
        d["asset_name"] = cert.asset.name if cert.asset else str(cert.asset_id)
        out.append(d)
    return out


@router.get("/certifications/check")
def check_certification(
    asset_id: int,
    _cu=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Check if the current user is certified (and not expired) for an asset."""
    from datetime import date
    cert = db.query(AssetCertification).filter(
        AssetCertification.asset_id == asset_id,
        AssetCertification.username == _cu.username,
    ).first()
    if not cert:
        return {"certified": False, "reason": "not_certified"}
    if cert.expires_at:
        try:
            exp = date.fromisoformat(cert.expires_at[:10])
            if exp < date.today():
                return {"certified": False, "reason": "expired", "expired_at": cert.expires_at}
        except ValueError:
            pass
    return {"certified": True, "certified_at": cert.certified_at, "expires_at": cert.expires_at}


@router.get("/certifications/mine")
def my_certifications(_cu=Depends(get_current_user), db: Session = Depends(get_db)):
    rows = (
        db.query(AssetCertification)
        .join(Asset)
        .filter(AssetCertification.username == _cu.username)
        .all()
    )
    return [_cert_dict(c) for c in rows]


@router.get("/{asset_id}/certifications")
def list_certifications(asset_id: int, db: Session = Depends(get_db)):
    _asset_or_404(db, asset_id)
    rows = db.query(AssetCertification).filter(
        AssetCertification.asset_id == asset_id).all()
    return [_cert_dict(c) for c in rows]


@router.post("/{asset_id}/certifications")
def add_certification(asset_id: int, body: CertIn, _w=_W,
                      db: Session = Depends(get_db)):
    _asset_or_404(db, asset_id)
    existing = db.query(AssetCertification).filter(
        AssetCertification.asset_id == asset_id,
        AssetCertification.username == body.username).first()
    if existing:
        # Update instead of duplicate
        for k, v in body.model_dump(exclude_none=True).items():
            setattr(existing, k, v)
        db.commit()
        db.refresh(existing)
        return _cert_dict(existing)
    c = AssetCertification(asset_id=asset_id, **body.model_dump())
    db.add(c)
    db.commit()
    db.refresh(c)
    return _cert_dict(c)


@router.delete("/{asset_id}/certifications/{cid}")
def revoke_certification(asset_id: int, cid: int, _w=_W,
                         db: Session = Depends(get_db)):
    c = db.query(AssetCertification).filter(
        AssetCertification.id == cid,
        AssetCertification.asset_id == asset_id).first()
    if not c:
        raise HTTPException(404, "Certification not found")
    db.delete(c)
    db.commit()
    return {"ok": True}


# ── Incidents ──────────────────────────────────────────────────────────────────

@router.get("/{asset_id}/incidents")
def list_incidents(asset_id: int, db: Session = Depends(get_db)):
    _asset_or_404(db, asset_id)
    rows = (
        db.query(AssetIncident)
        .filter(AssetIncident.asset_id == asset_id)
        .order_by(AssetIncident.created_at.desc())
        .all()
    )
    return [_incident_dict(i) for i in rows]


@router.post("/{asset_id}/incidents")
def log_incident(asset_id: int, body: IncidentIn, db: Session = Depends(get_db)):
    a = _asset_or_404(db, asset_id)
    i = AssetIncident(asset_id=asset_id, **body.model_dump())
    db.add(i)
    # If out_of_service, mark asset status
    if body.out_of_service:
        a.status = "out_of_service"
    db.commit()
    db.refresh(i)
    return _incident_dict(i)


@router.patch("/{asset_id}/incidents/{iid}")
def update_incident(asset_id: int, iid: int, body: IncidentPatch,
                    _cu=Depends(get_current_user), db: Session = Depends(get_db)):
    i = db.query(AssetIncident).filter(
        AssetIncident.id == iid, AssetIncident.asset_id == asset_id).first()
    if not i:
        raise HTTPException(404, "Incident not found")
    if _cu.role != "admin" and i.reported_by != _cu.username:
        raise HTTPException(403, "You can only modify incidents you reported")
    data = body.model_dump(exclude_none=True)
    for k, v in data.items():
        setattr(i, k, v)
    # If marking resolved, set resolved_at if not provided
    if data.get("resolved") and not data.get("resolved_at"):
        i.resolved_at = datetime.now().strftime("%Y-%m-%d")
    # If no longer out_of_service after resolve, restore asset
    if data.get("resolved"):
        a = db.query(Asset).filter(Asset.id == asset_id).first()
        if a and a.status == "out_of_service":
            # Only restore if no other open OOS incidents
            other_oos = db.query(AssetIncident).filter(
                AssetIncident.asset_id == asset_id,
                AssetIncident.id != iid,
                AssetIncident.out_of_service == True,
                AssetIncident.resolved == False,
            ).first()
            if not other_oos:
                a.status = "available"
    db.commit()
    db.refresh(i)
    return _incident_dict(i)


@router.delete("/{asset_id}/incidents/{iid}")
def delete_incident(asset_id: int, iid: int, _w=_W,
                    db: Session = Depends(get_db)):
    i = db.query(AssetIncident).filter(
        AssetIncident.id == iid, AssetIncident.asset_id == asset_id).first()
    if not i:
        raise HTTPException(404, "Incident not found")
    db.delete(i)
    db.commit()
    return {"ok": True}
