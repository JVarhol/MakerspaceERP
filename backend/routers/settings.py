"""
Router: App Settings (server-side key-value store)
  GET  /api/settings/{key}
  POST /api/settings/{key}
  GET  /api/mqtt/status
  POST /api/mqtt/connect
  POST /api/mqtt/disconnect
  POST /api/mqtt/publish-discovery
"""
from __future__ import annotations
import json
import os
import uuid
from pathlib import Path
from typing import Optional
from pydantic import BaseModel
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import AppSetting

UPLOADS_DIR = Path(os.getenv("UPLOADS_DIR", "/opt/makerspace-erp/data/uploads"))
BRANDING_DIR = UPLOADS_DIR / "branding"
ALLOWED_IMAGE_TYPES = {
    "image/jpeg": ".jpg",
    "image/png": ".png",
    "image/gif": ".gif",
    "image/webp": ".webp",
    "image/x-icon": ".ico",
    "image/vnd.microsoft.icon": ".ico",
}

from ..auth import get_current_user
router = APIRouter(tags=["settings"], dependencies=[Depends(get_current_user)])


def _get(db: Session, key: str) -> dict | None:
    row = db.query(AppSetting).filter(AppSetting.key == key).first()
    if not row or not row.value:
        return None
    try:
        return json.loads(row.value)
    except Exception:
        return None


def _set(db: Session, key: str, value: dict) -> None:
    row = db.query(AppSetting).filter(AppSetting.key == key).first()
    if row:
        row.value = json.dumps(value)
    else:
        row = AppSetting(key=key, value=json.dumps(value))
        db.add(row)
    db.commit()


SENSITIVE_FIELDS = {
    "mqtt": ["password"],
    "ha":   ["token"],
}

# ── Asset upload (must be before generic /{key} routes) ───────────────────────

DEFAULT_UPLOAD_MB = 5

@router.post("/api/settings/upload-asset")
async def upload_asset(file: UploadFile = File(...), db: Session = Depends(get_db)):
    # Respect admin-configured upload size limit (default 5 MB)
    limits = _get(db, "upload_limits") or {}
    try:
        max_mb = max(1, int(limits.get("max_mb", DEFAULT_UPLOAD_MB)))
    except (ValueError, TypeError):
        max_mb = DEFAULT_UPLOAD_MB
    max_bytes = max_mb * 1024 * 1024

    content_type = file.content_type or ""
    ext = ALLOWED_IMAGE_TYPES.get(content_type)
    if not ext:
        if file.filename:
            suffix = Path(file.filename).suffix.lower()
            # SVG excluded — can contain executable script tags
            if suffix in {".jpg", ".jpeg", ".png", ".gif", ".webp", ".ico"}:
                ext = suffix if suffix != ".jpeg" else ".jpg"
    if not ext:
        raise HTTPException(400, f"Unsupported file type: {content_type or 'unknown'}. SVG files are not permitted.")
    BRANDING_DIR.mkdir(parents=True, exist_ok=True)
    filename = f"{uuid.uuid4().hex}{ext}"
    dest = BRANDING_DIR / filename
    data = await file.read(max_bytes + 1)
    if len(data) > max_bytes:
        raise HTTPException(413, f"File too large (max {max_mb} MB)")
    dest.write_bytes(data)
    return {"url": f"/uploads/branding/{filename}"}


# ── Generic key-value settings ────────────────────────────────────────────────

@router.get("/api/settings/{key}")
def get_setting(key: str, db: Session = Depends(get_db)):
    val = _get(db, key)
    if val and key in SENSITIVE_FIELDS:
        val = dict(val)
        for field in SENSITIVE_FIELDS[key]:
            if field in val and val[field]:
                val[field] = "***SAVED***"
    return {"key": key, "value": val}


@router.post("/api/settings/{key}")
def set_setting(key: str, body: dict, db: Session = Depends(get_db)):
    if key in SENSITIVE_FIELDS:
        existing = _get(db, key) or {}
        for field in SENSITIVE_FIELDS[key]:
            if body.get(field) == "***SAVED***":
                body[field] = existing.get(field, "")
    _set(db, key, body)
    masked = dict(body)
    for field in SENSITIVE_FIELDS.get(key, []):
        if masked.get(field):
            masked[field] = "***SAVED***"
    return {"key": key, "value": masked}


# ── MQTT management endpoints ─────────────────────────────────────────────────

@router.get("/api/mqtt/status")
def mqtt_status():
    from .. import mqtt_service
    return mqtt_service.get_status()


@router.post("/api/mqtt/connect")
def mqtt_connect(db: Session = Depends(get_db)):
    from .. import mqtt_service
    cfg = _get(db, "mqtt")
    if not cfg or not cfg.get("broker"):
        raise HTTPException(400, "MQTT not configured — save settings first")
    result = mqtt_service.connect(cfg, db)
    return result


@router.post("/api/mqtt/disconnect")
def mqtt_disconnect():
    from .. import mqtt_service
    mqtt_service.disconnect()
    return {"status": "disconnected"}


@router.post("/api/mqtt/publish-discovery")
def publish_discovery(db: Session = Depends(get_db)):
    from .. import mqtt_service
    from ..models import Item
    items = db.query(Item).filter(Item.mqtt_exposed == True).all()
    count = mqtt_service.publish_all_discovery(items)
    return {"published": count}

# ── Home Assistant REST API endpoints ─────────────────────────────────────────

@router.get("/api/ha/status")
def ha_status():
    from .. import ha_service
    return ha_service.get_status()


@router.post("/api/ha/test")
def ha_test(db: Session = Depends(get_db)):
    cfg = _get(db, "ha")
    if not cfg or not cfg.get("url") or not cfg.get("token"):
        raise HTTPException(400, "HA not configured — save settings first")
    from .. import ha_service
    return ha_service.test_connection(cfg)


@router.post("/api/ha/configure")
def ha_configure(db: Session = Depends(get_db)):
    from .. import ha_service
    cfg = _get(db, "ha")
    if cfg:
        ha_service.configure(cfg)
    return {"status": "configured"}


@router.post("/api/ha/push-all")
def ha_push_all(db: Session = Depends(get_db)):
    from .. import ha_service
    from ..models import Item, Asset
    from sqlalchemy.orm import joinedload
    items  = db.query(Item).filter(Item.ha_exposed == True).all()
    assets = db.query(Asset).options(
        joinedload(Asset.location), joinedload(Asset.checkouts)
    ).filter(Asset.ha_exposed == True).all()
    ic = ha_service.push_all_items(items)
    ac = ha_service.push_all_assets(assets)
    return {"items_pushed": ic, "assets_pushed": ac}


@router.post("/api/mqtt/publish-module-discovery")
def publish_module_discovery(db: Session = Depends(get_db)):
    """Bulk-publish MQTT discovery + state for all enabled modules."""
    from .. import mqtt_service
    mqtt_service.publish_all_modules(db)
    # Also publish items/assets (existing)
    from ..models import Item, Asset
    from sqlalchemy.orm import joinedload
    items  = db.query(Item).filter(Item.mqtt_exposed == True).all()
    assets = db.query(Asset).options(joinedload(Asset.location), joinedload(Asset.checkouts)).filter(Asset.mqtt_exposed == True).all()
    ic = mqtt_service.publish_all_discovery(items)
    for a in assets:
        mqtt_service.publish_asset_discovery(a)
    return {"ok": True, "items_published": ic, "assets_published": len(assets)}


@router.post("/api/ha/push-modules")
def ha_push_modules(db: Session = Depends(get_db)):
    """Push HA state for all enabled modules."""
    from .. import ha_service
    counts = ha_service.push_all_modules(db)
    return {"ok": True, "counts": counts}


@router.post("/api/dashboard/publish-integration")
def publish_dashboard_integration(db: Session = Depends(get_db)):
    """Publish dashboard widget values to MQTT and/or HA for all enabled widgets."""
    from .. import mqtt_service, ha_service
    mqtt_count = mqtt_service.publish_all_dashboard_widgets(db)
    ha_count   = ha_service.push_all_dashboard_widgets(db)
    return {"ok": True, "mqtt_published": mqtt_count, "ha_pushed": ha_count}


@router.post("/api/locate/{item_id}")
def locate_item(item_id: int, db: Session = Depends(get_db)):
    """Publish a locate request for an item to MQTT and/or HA.

    Publishes:
      MQTT: {base}/locate/bin_id  and  {base}/locate/location_path
      HA:   sensor.makerspace_locate_bin_id  and  sensor.makerspace_locate_location_path
    """
    from .. import mqtt_service, ha_service
    from ..models import Item, ItemLocation, Location

    item = db.get(Item, item_id)
    if not item:
        raise HTTPException(404, "Item not found")

    # Build bin_id and location_path from the item's primary location
    # (use the first location with the most stock, or just the first one)
    il = (db.query(ItemLocation)
            .filter(ItemLocation.item_id == item_id)
            .order_by(ItemLocation.quantity.desc())
            .first())
    bin_id = ""
    location_path = ""
    if il and il.location:
        loc: Location = il.location
        bin_id = loc.bin_id or ""
        parts = []
        if loc.location_type:
            parts.append(loc.location_type)
        parts.append(loc.name)
        if loc.bin_id:
            parts.append(f"Bin: {loc.bin_id}")
        location_path = " / ".join(parts)

    mqtt_settings = _get(db, "mqtt") or {}
    ha_settings   = _get(db, "ha") or {}

    mqtt_ok = False
    ha_ok   = False
    if mqtt_settings.get("locate_enabled") and mqtt_service.get_status().get("connected"):
        mqtt_ok = mqtt_service.publish_locate_item(item_id, item.name, bin_id, location_path)
    if ha_settings.get("locate_enabled"):
        ha_ok = ha_service.push_locate_item(item_id, item.name, bin_id, location_path)

    return {
        "ok": True,
        "item_id": item_id,
        "item_name": item.name,
        "bin_id": bin_id,
        "location_path": location_path,
        "mqtt_published": mqtt_ok,
        "ha_pushed": ha_ok,
    }


class LocateSearchingBody(BaseModel):
    active: bool
    item_id: Optional[int] = None
    item_name: Optional[str] = ""


@router.post("/api/locate/searching")
def locate_searching(body: LocateSearchingBody, db: Session = Depends(get_db)):
    """Publish or clear the locate/searching topic on MQTT.

    Publishes {base}/locate/searching → JSON with active flag.
    Called when user opens locate (active=true) and when modal closes (active=false).
    """
    from .. import mqtt_service

    mqtt_settings = _get(db, "mqtt") or {}
    if not (mqtt_settings.get("locate_enabled") and mqtt_service.get_status().get("connected")):
        return {"ok": True, "published": False, "reason": "MQTT locate not enabled"}

    ok = mqtt_service.publish_locate_searching(body.active, body.item_id, body.item_name or "")
    return {"ok": True, "published": ok}


