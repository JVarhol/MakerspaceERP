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
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import AppSetting

router = APIRouter(tags=["settings"])


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
    # Preserve existing sensitive values if placeholder submitted
    if key in SENSITIVE_FIELDS:
        existing = _get(db, key) or {}
        for field in SENSITIVE_FIELDS[key]:
            if body.get(field) == "***SAVED***":
                body[field] = existing.get(field, "")
    _set(db, key, body)
    # Return masked version
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
