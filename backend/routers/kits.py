"""
Router: Kits — stock replenishment bundles
  GET    /api/kits
  POST   /api/kits
  GET    /api/kits/{kit_id}
  PATCH  /api/kits/{kit_id}
  DELETE /api/kits/{kit_id}
  POST   /api/kits/{kit_id}/items          (add component)
  DELETE /api/kits/{kit_id}/items/{ki_id}  (remove component)
  POST   /api/kits/{kit_id}/restock        (add all components to inventory)
"""
from __future__ import annotations
from typing import List

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import Kit, KitItem, Item, Transaction, ItemLocation
from ..schemas import KitCreate, KitUpdate, KitOut, KitItemCreate, KitItemOut, KitRestockBody

from ..auth import get_current_user, require_permission
router = APIRouter(tags=["kits"], dependencies=[Depends(get_current_user)])
_W = Depends(require_permission('kits', 'write'))



def _publish_kit(db, kit):
    try:
        from .. import mqtt_service, ha_service
        if not kit.kit_items:
            buildable = 0
        else:
            min_b = None
            for ki in kit.kit_items:
                it = db.get(Item, ki.item_id)
                if not it or ki.quantity <= 0:
                    min_b = 0; break
                b = int(it.quantity // ki.quantity)
                if min_b is None or b < min_b:
                    min_b = b
            buildable = min_b or 0
        if mqtt_service._is_module_mqtt_enabled(db, "kits"):
            mqtt_service.publish_kit_discovery(kit.id, kit.name)
            mqtt_service.publish_kit_state(kit.id, kit.name, buildable, len(kit.kit_items))
        if ha_service._is_module_ha_enabled(db, "kits"):
            ha_service.push_kit_state(kit.id, kit.name, buildable, len(kit.kit_items))
    except Exception:
        pass

@router.get("/api/kits", response_model=List[KitOut])
def list_kits(db: Session = Depends(get_db)):
    kits = db.query(Kit).order_by(Kit.name).all()
    return [_kit_out(k) for k in kits]


@router.post("/api/kits", response_model=KitOut, status_code=201)
def create_kit(body: KitCreate, _w=_W, db: Session = Depends(get_db)):
    kit = Kit(**body.model_dump())
    db.add(kit)
    db.commit()
    db.refresh(kit)
    _publish_kit(db, kit)
    return _kit_out(kit)


@router.get("/api/kits/{kit_id}", response_model=KitOut)
def get_kit(kit_id: int, db: Session = Depends(get_db)):
    kit = db.get(Kit, kit_id)
    if not kit:
        raise HTTPException(404, "Kit not found")
    return _kit_out(kit)


@router.patch("/api/kits/{kit_id}", response_model=KitOut)
def update_kit(kit_id: int, body: KitUpdate, _w=_W, db: Session = Depends(get_db)):
    kit = db.get(Kit, kit_id)
    if not kit:
        raise HTTPException(404, "Kit not found")
    for k, v in body.model_dump(exclude_none=True).items():
        setattr(kit, k, v)
    db.commit()
    db.refresh(kit)
    _publish_kit(db, kit)
    return _kit_out(kit)


@router.delete("/api/kits/{kit_id}", status_code=204)
def delete_kit(kit_id: int, _w=_W, db: Session = Depends(get_db)):
    kit = db.get(Kit, kit_id)
    if not kit:
        raise HTTPException(404, "Kit not found")
    try:
        from .. import mqtt_service
        mqtt_service.remove_kit_discovery(kit_id)
    except Exception:
        pass
    db.delete(kit)
    db.commit()


@router.post("/api/kits/{kit_id}/items", response_model=KitItemOut, status_code=201)
def add_kit_item(kit_id: int, body: KitItemCreate, _w=_W, db: Session = Depends(get_db)):
    kit = db.get(Kit, kit_id)
    if not kit:
        raise HTTPException(404, "Kit not found")
    item = db.get(Item, body.item_id)
    if not item:
        raise HTTPException(404, "Item not found")
    # Update qty if already exists
    existing = db.query(KitItem).filter(
        KitItem.kit_id == kit_id, KitItem.item_id == body.item_id
    ).first()
    if existing:
        existing.quantity = body.quantity
        db.commit()
        db.refresh(existing)
        return _ki_out(existing)
    ki = KitItem(kit_id=kit_id, item_id=body.item_id, quantity=body.quantity)
    db.add(ki)
    db.commit()
    db.refresh(ki)
    return _ki_out(ki)


@router.delete("/api/kits/{kit_id}/items/{ki_id}", status_code=204)
def remove_kit_item(kit_id: int, ki_id: int, _w=_W, db: Session = Depends(get_db)):
    ki = db.query(KitItem).filter(KitItem.id == ki_id, KitItem.kit_id == kit_id).first()
    if not ki:
        raise HTTPException(404, "Kit item not found")
    db.delete(ki)
    db.commit()


@router.post("/api/kits/{kit_id}/restock", status_code=200)
def restock_kit(kit_id: int, body: KitRestockBody = None, _w=_W, db: Session = Depends(get_db)):
    """Add one kit's worth of all components to inventory.

    Optional body: { location_overrides: { "<item_id>": <location_id>, ... } }
    When a location_id is provided for an item, that ItemLocation's quantity is also incremented.
    """
    kit = db.get(Kit, kit_id)
    if not kit:
        raise HTTPException(404, "Kit not found")
    if not kit.kit_items:
        raise HTTPException(400, "Kit has no components")
    overrides = {}
    if body and body.location_overrides:
        overrides = {int(k): int(v) for k, v in body.location_overrides.items()}
    updated = []
    for ki in kit.kit_items:
        item = db.get(Item, ki.item_id)
        if not item:
            continue
        before = item.quantity
        item.quantity = round(before + ki.quantity, 6)
        # Update per-location quantity if a location was specified
        loc_id = overrides.get(ki.item_id)
        if loc_id:
            il = db.query(ItemLocation).filter(
                ItemLocation.item_id == ki.item_id,
                ItemLocation.location_id == loc_id,
            ).first()
            if il:
                il.quantity = round((il.quantity or 0) + ki.quantity, 6)
            else:
                db.add(ItemLocation(item_id=ki.item_id, location_id=loc_id, quantity=ki.quantity))
        db.add(Transaction(
            item_id=item.id,
            transaction_type="add",
            quantity_change=ki.quantity,
            quantity_before=before,
            quantity_after=item.quantity,
            to_location_id=loc_id or None,
            notes=f"Kit restocked: {kit.name}",
        ))
        updated.append({"item_id": item.id, "added": ki.quantity})
    db.commit()
    db.refresh(kit)
    _publish_kit(db, kit)
    return {"restocked": len(updated), "items": updated}


# ── Helpers ───────────────────────────────────────────────────────────────────

def _kit_out(kit: Kit) -> dict:
    return KitOut(
        id=kit.id, name=kit.name, description=kit.description,
        notes=kit.notes, color=kit.color, icon=kit.icon,
        kit_items=[_ki_out(ki) for ki in kit.kit_items],
    )

def _ki_out(ki: KitItem) -> KitItemOut:
    locs = []
    if ki.item:
        for il in ki.item.locations:
            try:
                from ..schemas import ItemLocationOut
                locs.append(ItemLocationOut.model_validate(il))
            except Exception:
                pass
    return KitItemOut(
        id=ki.id, item_id=ki.item_id, quantity=ki.quantity,
        item_name=ki.item.name if ki.item else None,
        item_unit=ki.item.unit_name if ki.item else None,
        item_locations=locs,
    )
