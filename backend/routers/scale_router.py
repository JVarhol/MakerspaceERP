"""
Scale Router — weigh-to-count via MQTT scale
  GET  /api/scale/reading   → current reading, tare, net, config
  POST /api/scale/tare      → save tare weight {value: float}
  POST /api/scale/configure → subscribe scale topic live without restart
"""
from __future__ import annotations
import json
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import AppSetting

router = APIRouter(prefix="/api/scale", tags=["scale"])


def _get_cfg(db: Session) -> dict:
    row = db.query(AppSetting).filter(AppSetting.key == "scale").first()
    return json.loads(row.value) if row and row.value else {}


def _get_tare(db: Session) -> float:
    row = db.query(AppSetting).filter(AppSetting.key == "scale_tare").first()
    try:
        return float(row.value) if row and row.value else 0.0
    except Exception:
        return 0.0


@router.get("/reading")
def get_reading(db: Session = Depends(get_db)):
    from .. import mqtt_service
    reading = mqtt_service.get_scale_reading()
    tare    = _get_tare(db)
    cfg     = _get_cfg(db)
    net     = round(reading - tare, 4) if reading is not None else None
    status = mqtt_service.get_status()
    base   = status.get("base_topic", "makerspace")
    mode = cfg.get("mode", "ha_entity")
    return {
        "reading":       reading,
        "tare":          tare,
        "net":           net,
        "unit":          cfg.get("unit", "g"),
        "mode":          mode,
        "set_topic":     f"{base}/scale/set" if mode == "ha_entity" else cfg.get("topic", ""),
        "state_topic":   f"{base}/scale/state",
        "enabled":       cfg.get("enabled", False),
        "connected":     status["connected"],
    }


@router.post("/tare")
def set_tare(body: dict, db: Session = Depends(get_db)):
    value = float(body.get("value", 0.0))
    row = db.query(AppSetting).filter(AppSetting.key == "scale_tare").first()
    if row:
        row.value = str(value)
    else:
        db.add(AppSetting(key="scale_tare", value=str(value)))
    db.commit()
    return {"tare": value}


@router.post("/publish-discovery")
def publish_discovery():
    """Publish HA number entity discovery for the scale."""
    from .. import mqtt_service
    ok = mqtt_service.publish_scale_discovery()
    return {"status": "published" if ok else "not_connected"}


@router.post("/configure")
def configure_scale(db: Session = Depends(get_db)):
    """Re-subscribe scale topic after settings change without restart."""
    from .. import mqtt_service
    cfg = _get_cfg(db)
    if cfg.get("enabled"):
        mqtt_service.configure_scale(
            mode  = cfg.get("mode", "ha_entity"),
            topic = cfg.get("topic", ""),
            unit  = cfg.get("unit", "g"),
        )
        status = mqtt_service.get_status()
        base   = status.get("base_topic", "makerspace")
        mode   = cfg.get("mode", "ha_entity")
        active_topic = f"{base}/scale/set" if mode == "ha_entity" else cfg.get("topic", "")
        return {"status": "configured", "mode": mode, "active_topic": active_topic}
    return {"status": "disabled"}
