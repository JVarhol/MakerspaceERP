"""
MQTT Service — runs paho-mqtt in a background thread.

Topics (base = cfg['base_topic'], default 'makerspace'):
  Publish:  {base}/items/{id}/state          → quantity (float as string)
            {base}/items/{id}/attributes      → JSON {name, unit, category}
  Subscribe:{base}/items/{id}/set            → set quantity
  Discovery:homeassistant/number/makerspace_{id}/config
"""
from __future__ import annotations
import json
import logging
import threading
from typing import Optional

log = logging.getLogger("mqtt_service")

_client = None
_config: dict = {}
_connected = False
_status_msg = "Not configured"
_lock = threading.Lock()

# Scale
_scale_reading: Optional[float] = None
_scale_topic: str = ""        # topic being listened to (either mode)
_scale_mode: str = ""         # 'subscribe' | 'ha_entity'
_scale_unit: str = "g"


# ── Public API ────────────────────────────────────────────────────────────────

def get_status() -> dict:
    return {
        "connected": _connected,
        "message":   _status_msg,
        "broker":    _config.get("broker", ""),
        "port":      _config.get("port", 1883),
        "base_topic":_config.get("base_topic", "makerspace"),
    }


def get_scale_reading() -> Optional[float]:
    """Return the most recent weight reading from the configured scale topic."""
    return _scale_reading


def configure_scale(mode: str = "ha_entity", topic: str = "", unit: str = "g") -> None:
    """Subscribe to the appropriate scale topic based on mode.

    mode='subscribe'  — ERP listens to a user-specified topic (scale publishes there).
    mode='ha_entity'  — ERP creates a writable number entity in HA; HA writes to
                        {base}/scale/set, ERP publishes state to {base}/scale/state.
    """
    global _scale_topic, _scale_mode, _scale_unit
    _scale_mode = mode
    _scale_unit = unit
    base = _config.get("base_topic", "makerspace")

    if mode == "ha_entity":
        _scale_topic = f"{base}/scale/set"
    else:  # subscribe
        _scale_topic = topic

    if _connected and _client and _scale_topic:
        try:
            _client.subscribe(_scale_topic)
            log.info(f"Scale subscribed ({mode}): {_scale_topic}")
            if mode == "ha_entity":
                publish_scale_discovery()
        except Exception as e:
            log.warning(f"Scale subscribe failed: {e}")


def publish_scale_discovery() -> bool:
    """Publish HA auto-discovery for the scale.

    ha_entity mode  → writable number entity (HA can set the value).
    subscribe mode  → read-only sensor entity (HA mirrors the scale value).
    Returns True on success.
    """
    if not _connected or not _client:
        return False
    base = _config.get("base_topic", "makerspace")
    unit = _scale_unit or "g"

    if _scale_mode == "ha_entity":
        config = {
            "name":          "Makerspace Scale",
            "unique_id":     "makerspace_scale_weight",
            "state_topic":   f"{base}/scale/state",
            "command_topic": f"{base}/scale/set",
            "unit_of_measurement": unit,
            "min":    0,
            "max":    99999,
            "step":   0.1,
            "mode":   "box",
            "device": {
                "identifiers": ["makerspace_erp"],
                "name":        "Makerspace ERP",
                "model":       "Inventory Manager",
                "manufacturer":"HomeERP",
            },
        }
        discovery_topic = "homeassistant/number/makerspace_scale/config"
    else:
        # subscribe mode: sensor that mirrors the external scale
        config = {
            "name":          "Makerspace Scale",
            "unique_id":     "makerspace_scale_weight",
            "state_topic":   _scale_topic,
            "unit_of_measurement": unit,
            "device_class":  "weight",
            "state_class":   "measurement",
            "device": {
                "identifiers": ["makerspace_erp"],
                "name":        "Makerspace ERP",
                "model":       "Inventory Manager",
                "manufacturer":"HomeERP",
            },
        }
        discovery_topic = "homeassistant/sensor/makerspace_scale/config"

    try:
        _client.publish(discovery_topic, json.dumps(config), retain=True)
        if _scale_mode == "ha_entity" and _scale_reading is not None:
            _client.publish(f"{base}/scale/state", str(_scale_reading), retain=True)
        log.info(f"Scale HA discovery published ({_scale_mode})")
        return True
    except Exception as e:
        log.warning(f"Scale discovery failed: {e}")
        return False


def connect(cfg: dict, db=None) -> dict:
    global _client, _config, _connected, _status_msg
    import paho.mqtt.client as mqtt

    disconnect()  # clean up any existing connection

    _config = cfg
    broker   = cfg.get("broker", "")
    port     = int(cfg.get("port", 1883))
    username = cfg.get("username", "")
    password = cfg.get("password", "")
    client_id = cfg.get("client_id", "makerspace-erp")

    def on_connect(client, userdata, flags, rc):
        global _connected, _status_msg
        with _lock:
            if rc == 0:
                _connected = True
                _status_msg = f"Connected to {broker}:{port}"
                log.info(_status_msg)
                _subscribe_all(client, db)
            else:
                _connected = False
                _status_msg = f"Connection failed (rc={rc})"
                log.warning(_status_msg)

    def on_disconnect(client, userdata, rc):
        global _connected, _status_msg
        with _lock:
            _connected = False
            _status_msg = "Disconnected" if rc == 0 else f"Disconnected unexpectedly (rc={rc})"

    def on_message(client, userdata, msg):
        _handle_message(msg)

    c = mqtt.Client(client_id=client_id)
    if username:
        c.username_pw_set(username, password or None)
    # TLS support
    if cfg.get("use_tls"):
        import ssl
        ca_cert = cfg.get("ca_cert_path") or None
        try:
            c.tls_set(ca_certs=ca_cert, cert_reqs=ssl.CERT_REQUIRED if ca_cert else ssl.CERT_NONE)
            if not ca_cert:
                c.tls_insecure_set(True)
        except Exception as e:
            log.warning(f"TLS setup warning: {e}")
    c.on_connect    = on_connect
    c.on_disconnect = on_disconnect
    c.on_message    = on_message

    try:
        c.connect(broker, port, keepalive=60)
        c.loop_start()
        _client = c
        _status_msg = f"Connecting to {broker}:{port}…"
        return {"status": "connecting", "broker": broker, "port": port}
    except Exception as e:
        _status_msg = f"Failed to connect: {e}"
        _connected = False
        return {"status": "error", "message": str(e)}


def disconnect():
    global _client, _connected, _status_msg
    if _client:
        try:
            _client.loop_stop()
            _client.disconnect()
        except Exception:
            pass
        _client = None
    _connected = False
    _status_msg = "Disconnected"


def publish_item_state(item_id: int, name: str, quantity: float, unit: str, category: str = ""):
    """Called after any quantity change on an exposed item."""
    if not _connected or not _client:
        return
    base = _config.get("base_topic", "makerspace")
    try:
        _client.publish(f"{base}/items/{item_id}/state", str(quantity), retain=True)
        _client.publish(f"{base}/items/{item_id}/attributes",
                        json.dumps({"name": name, "unit": unit, "category": category}),
                        retain=True)
    except Exception as e:
        log.warning(f"MQTT publish failed: {e}")


def publish_discovery_for_item(item) -> bool:
    """Publish HA auto-discovery config for one item. Returns True on success."""
    if not _connected or not _client:
        return False
    base   = _config.get("base_topic", "makerspace")
    uid    = f"makerspace_{item.id}"
    cat    = item.category.name if item.category else ""
    config = {
        "name":                item.name,
        "unique_id":           uid,
        "state_topic":         f"{base}/items/{item.id}/state",
        "command_topic":       f"{base}/items/{item.id}/set",
        "unit_of_measurement": item.unit_name,
        "min":    0,
        "max":    999999,
        "step":   0.001,
        "mode":   "box",
        "device": {
            "identifiers": ["makerspace_erp"],
            "name":        "Makerspace ERP",
            "model":       "Inventory Manager",
            "manufacturer":"HomeERP",
        },
        "json_attributes_topic": f"{base}/items/{item.id}/attributes",
    }
    try:
        _client.publish(f"homeassistant/number/{uid}/config",
                        json.dumps(config), retain=True)
        # Immediately publish current state
        publish_item_state(item.id, item.name, item.quantity, item.unit_name, cat)
        return True
    except Exception as e:
        log.warning(f"Discovery publish failed for item {item.id}: {e}")
        return False


def remove_discovery_for_item(item_id: int):
    """Remove HA discovery (send empty payload to remove entity)."""
    if not _connected or not _client:
        return
    uid = f"makerspace_{item_id}"
    try:
        _client.publish(f"homeassistant/number/{uid}/config", "", retain=True)
    except Exception as e:
        log.warning(f"Discovery remove failed: {e}")


def publish_all_discovery(items) -> int:
    count = 0
    for item in items:
        if publish_discovery_for_item(item):
            count += 1
    return count



# ── Asset MQTT ────────────────────────────────────────────────────────────────

def publish_asset_state(asset_id: int, name: str, status: str, asset_tag: str = "",
                        location: str = "", checked_out_by: str = ""):
    """Publish asset status and attributes."""
    if not _connected or not _client:
        return
    base = _config.get("base_topic", "makerspace")
    try:
        _client.publish(f"{base}/assets/{asset_id}/state", status, retain=True)
        _client.publish(f"{base}/assets/{asset_id}/attributes",
                        json.dumps({
                            "name": name,
                            "asset_tag": asset_tag,
                            "location": location,
                            "checked_out_by": checked_out_by,
                        }), retain=True)
    except Exception as e:
        log.warning(f"MQTT asset publish failed: {e}")


def publish_asset_discovery(asset) -> bool:
    """Publish HA auto-discovery for asset as a select entity."""
    if not _connected or not _client:
        return False
    base = _config.get("base_topic", "makerspace")
    uid  = f"makerspace_asset_{asset.id}"
    loc  = asset.location.name if asset.location else ""
    config = {
        "name":          asset.name,
        "unique_id":     uid,
        "state_topic":   f"{base}/assets/{asset.id}/state",
        "command_topic": f"{base}/assets/{asset.id}/set",
        "options":       ["available", "checked_out", "maintenance", "retired"],
        "device": {
            "identifiers": ["makerspace_erp"],
            "name":        "Makerspace ERP",
            "model":       "Inventory Manager",
            "manufacturer":"HomeERP",
        },
        "json_attributes_topic": f"{base}/assets/{asset.id}/attributes",
    }
    try:
        _client.publish(f"homeassistant/select/{uid}/config",
                        json.dumps(config), retain=True)
        co = next((c for c in asset.checkouts if c.returned_at is None), None)
        publish_asset_state(
            asset.id, asset.name, asset.status,
            asset.asset_tag or "", loc,
            co.checked_out_by if co else "",
        )
        return True
    except Exception as e:
        log.warning(f"Asset discovery failed for {asset.id}: {e}")
        return False


def remove_asset_discovery(asset_id: int):
    if not _connected or not _client:
        return
    uid = f"makerspace_asset_{asset_id}"
    try:
        _client.publish(f"homeassistant/select/{uid}/config", "", retain=True)
    except Exception:
        pass

# ── Internal helpers ──────────────────────────────────────────────────────────

def _subscribe_all(client, db=None):
    base = _config.get("base_topic", "makerspace")
    # Subscribe wildcard for all item set commands
    client.subscribe(f"{base}/items/+/set")
    log.info(f"Subscribed to {base}/items/+/set")
    client.subscribe(f"{base}/assets/+/set")
    log.info(f"Subscribed to {base}/assets/+/set")

    # Subscribe to scale topic if configured
    if _scale_topic:
        client.subscribe(_scale_topic)
        log.info(f"Scale topic subscribed ({_scale_mode}): {_scale_topic}")
        if _scale_mode == 'ha_entity':
            publish_scale_discovery()

    # Publish current state for all exposed items
    if db is not None:
        try:
            from .models import Item
            items = db.query(Item).filter(Item.mqtt_exposed == True).all()
            for item in items:
                cat = item.category.name if item.category else ""
                publish_item_state(item.id, item.name, item.quantity, item.unit_name, cat)
                publish_discovery_for_item(item)
            # Also publish exposed assets
            from .models import Asset
            from sqlalchemy.orm import joinedload
            assets = db.query(Asset).options(
                joinedload(Asset.location), joinedload(Asset.checkouts)
            ).filter(Asset.mqtt_exposed == True).all()
            for asset in assets:
                publish_asset_discovery(asset)
        except Exception as e:
            log.warning(f"Failed to publish initial states: {e}")


def _handle_message(msg):
    """Handle incoming set command for items and assets."""
    global _scale_reading
    import re
    # Check for scale reading
    if _scale_topic and msg.topic == _scale_topic:
        try:
            _scale_reading = float(msg.payload.decode().strip())
            log.debug(f"Scale reading: {_scale_reading}")
            # Echo back to state topic in ha_entity mode
            if _scale_mode == 'ha_entity' and _client:
                base_t = _config.get('base_topic', 'makerspace')
                _client.publish(f"{base_t}/scale/state", str(_scale_reading), retain=True)
        except Exception:
            log.warning(f"Invalid scale payload: {msg.payload}")
        return
    # Check if it's an asset command
    ma = re.match(rf"^{re.escape(base)}/assets/(\d+)/set$", msg.topic)
    if ma:
        _handle_asset_message(int(ma.group(1)), msg.payload.decode())
        return
    m = re.match(rf"^{re.escape(base)}/items/(\d+)/set$", msg.topic)
    if not m:
        return
    item_id = int(m.group(1))
    try:
        new_qty = float(msg.payload.decode())
    except Exception:
        log.warning(f"Invalid MQTT payload for item {item_id}: {msg.payload}")
        return

    # Create a new DB session for this thread
    try:
        from .database import SessionLocal
        from .models import Item, Transaction
        db = SessionLocal()
        try:
            item = db.get(Item, item_id)
            if not item or not item.mqtt_exposed:
                return
            before = item.quantity
            item.quantity = round(new_qty, 6)
            db.add(Transaction(
                item_id=item_id,
                transaction_type="adjustment",
                quantity_change=round(new_qty - before, 6),
                quantity_before=before,
                quantity_after=item.quantity,
                notes="Set via MQTT / Home Assistant",
                created_by="MQTT",
            ))
            db.commit()
            cat = item.category.name if item.category else ""
            publish_item_state(item_id, item.name, item.quantity, item.unit_name, cat)
            log.info(f"MQTT set item {item_id} qty {before} → {new_qty}")
        finally:
            db.close()
    except Exception as e:
        log.error(f"MQTT message handler error: {e}")


def _handle_asset_message(asset_id: int, payload: str):
    """Handle MQTT set for asset: checkout or status change."""
    VALID = {"available", "checked_out", "maintenance", "retired"}
    new_status = payload.strip().lower()
    if new_status not in VALID:
        log.warning(f"Invalid asset status from MQTT: {payload}")
        return
    try:
        from .database import SessionLocal
        from .models import Asset, AssetCheckout
        from sqlalchemy.orm import joinedload
        from datetime import datetime as dt
        db = SessionLocal()
        try:
            asset = db.query(Asset).options(
                joinedload(Asset.location), joinedload(Asset.checkouts)
            ).filter(Asset.id == asset_id).first()
            if not asset or not asset.mqtt_exposed:
                return
            open_co = next((c for c in asset.checkouts if c.returned_at is None), None)
            if new_status == "checked_out" and asset.status != "checked_out":
                co = AssetCheckout(asset_id=asset_id, checked_out_by="Home Assistant")
                db.add(co)
                asset.status = "checked_out"
            elif new_status == "available" and open_co:
                open_co.returned_at = dt.utcnow()
                asset.status = "available"
            else:
                asset.status = new_status
            db.commit()
            db.refresh(asset)
            loc = asset.location.name if asset.location else ""
            new_co = next((c for c in asset.checkouts if c.returned_at is None), None)
            publish_asset_state(asset_id, asset.name, asset.status,
                                asset.asset_tag or "", loc,
                                new_co.checked_out_by if new_co else "")
            log.info(f"MQTT set asset {asset_id} status → {new_status}")
        finally:
            db.close()
    except Exception as e:
        log.error(f"MQTT asset handler error: {e}")
