"""
Home Assistant REST API Service
Pushes item quantities and asset statuses directly to HA via its REST API.
Uses a long-lived access token — no broker required.

HA state entities created:
  sensor.makerspace_item_{id}   → state = quantity, attrs = {name, unit, category, low_stock}
  sensor.makerspace_asset_{id}  → state = status,   attrs = {name, asset_tag, location, checked_out_by}

HA can write back to the ERP directly via its REST API:
  PATCH http://{erp_host}:8080/api/items/{id}   {"quantity": x}
  POST  http://{erp_host}:8080/api/assets/{id}/checkout  or /return
"""
from __future__ import annotations
import json
import logging
import threading
from typing import Optional

import httpx

log = logging.getLogger("ha_service")

_config: dict = {}
_lock = threading.Lock()


# ── Public API ────────────────────────────────────────────────────────────────

def configure(cfg: dict):
    global _config
    with _lock:
        _config = cfg


def get_status() -> dict:
    return {
        "configured": bool(_config.get("url") and _config.get("token")),
        "url": _config.get("url", ""),
    }


def test_connection(cfg: dict) -> dict:
    """Test HA connection by hitting /api/ endpoint."""
    try:
        r = httpx.get(
            cfg["url"].rstrip("/") + "/api/",
            headers=_headers(cfg),
            timeout=5,
            verify=cfg.get("verify_ssl", True),
        )
        if r.status_code == 200:
            return {"ok": True, "message": f"Connected — HA version: {r.json().get('version','?')}"}
        return {"ok": False, "message": f"HTTP {r.status_code}: {r.text[:100]}"}
    except Exception as e:
        return {"ok": False, "message": str(e)}


def push_item_state(item_id: int, name: str, quantity: float, unit: str,
                    category: str = "", low_stock: bool = False):
    """Push item quantity as a HA sensor state (non-blocking)."""
    cfg = _get_cfg()
    if not cfg:
        return
    threading.Thread(
        target=_set_state,
        args=(cfg, f"sensor.makerspace_item_{item_id}", str(quantity), {
            "friendly_name": f"Makerspace: {name}",
            "unit_of_measurement": unit,
            "category": category,
            "low_stock": low_stock,
            "item_id": item_id,
            "icon": "mdi:package-variant",
        }),
        daemon=True,
    ).start()


def push_asset_state(asset_id: int, name: str, status: str,
                     asset_tag: str = "", location: str = "", checked_out_by: str = ""):
    """Push asset status as a HA sensor state (non-blocking)."""
    cfg = _get_cfg()
    if not cfg:
        return
    threading.Thread(
        target=_set_state,
        args=(cfg, f"sensor.makerspace_asset_{asset_id}", status, {
            "friendly_name": f"Makerspace Asset: {name}",
            "asset_tag": asset_tag,
            "location": location,
            "checked_out_by": checked_out_by,
            "asset_id": asset_id,
            "icon": "mdi:tools",
        }),
        daemon=True,
    ).start()


def push_all_items(items) -> int:
    """Push state for all ha_exposed items. Returns count pushed."""
    cfg = _get_cfg()
    if not cfg:
        return 0
    count = 0
    for item in items:
        cat = item.category.name if item.category else ""
        low = item.quantity <= item.min_quantity and item.min_quantity > 0
        ok = _set_state(cfg, f"sensor.makerspace_item_{item.id}", str(item.quantity), {
            "friendly_name": f"Makerspace: {item.name}",
            "unit_of_measurement": item.unit_name,
            "category": cat,
            "low_stock": low,
            "item_id": item.id,
            "icon": "mdi:package-variant",
        })
        if ok:
            count += 1
    return count


def push_all_assets(assets) -> int:
    """Push state for all ha_exposed assets. Returns count pushed."""
    cfg = _get_cfg()
    if not cfg:
        return 0
    count = 0
    for asset in assets:
        co = next((c for c in asset.checkouts if c.returned_at is None), None)
        loc = asset.location.name if asset.location else ""
        ok = _set_state(cfg, f"sensor.makerspace_asset_{asset.id}", asset.status, {
            "friendly_name": f"Makerspace Asset: {asset.name}",
            "asset_tag": asset.asset_tag or "",
            "location": loc,
            "checked_out_by": co.checked_out_by if co else "",
            "asset_id": asset.id,
            "icon": "mdi:tools",
        })
        if ok:
            count += 1
    return count


# ── Internal ──────────────────────────────────────────────────────────────────

def _get_cfg() -> Optional[dict]:
    with _lock:
        cfg = dict(_config)
    if not cfg.get("url") or not cfg.get("token"):
        return None
    return cfg


def _headers(cfg: dict) -> dict:
    return {
        "Authorization": f"Bearer {cfg['token']}",
        "Content-Type": "application/json",
    }


def _set_state(cfg: dict, entity_id: str, state: str, attributes: dict) -> bool:
    try:
        url = cfg["url"].rstrip("/") + f"/api/states/{entity_id}"
        r = httpx.post(
            url,
            headers=_headers(cfg),
            json={"state": state, "attributes": attributes},
            timeout=5,
            verify=cfg.get("verify_ssl", True),
        )
        if r.status_code in (200, 201):
            return True
        log.warning(f"HA push failed for {entity_id}: {r.status_code} {r.text[:100]}")
        return False
    except Exception as e:
        log.warning(f"HA push error for {entity_id}: {e}")
        return False
