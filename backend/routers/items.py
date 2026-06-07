from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import or_
from typing import List, Optional
from difflib import SequenceMatcher

from ..database import get_db
from ..models import Item, SupplierLink, ItemLocation, Location, ItemFieldValue, Transaction, AssemblyComponent, KitItem, ProjectItem
from ..auth import decode_token

_security = HTTPBearer(auto_error=False)

def _optional_username(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(_security),
    db: Session = Depends(get_db),
) -> Optional[str]:
    if not credentials:
        return None
    payload = decode_token(credentials.credentials)
    if not payload:
        return None
    from ..models import User
    user = db.get(User, int(payload.get("sub", 0)))
    return user.username if user else None
from ..schemas import (
    ItemCreate, ItemUpdate, ItemOut, ItemSummary,
    SupplierLinkCreate, SupplierLinkOut,
    TransactionCreate, TransactionOut,
)

router = APIRouter(prefix="/api/items", tags=["items"])


def _load_item(db: Session, item_id: int) -> Item:
    item = (
        db.query(Item)
        .options(
            joinedload(Item.category),
            joinedload(Item.locations).joinedload(ItemLocation.location),
            joinedload(Item.supplier_links),
        )
        .filter(Item.id == item_id)
        .first()
    )
    if not item:
        raise HTTPException(404, "Item not found")
    return item


@router.get("/similar", response_model=List[ItemSummary])
def find_similar_items(
    name: str = Query(..., min_length=2),
    exclude_id: Optional[int] = None,
    db: Session = Depends(get_db),
):
    name_lower = name.lower().strip()
    first4 = name_lower[:4]
    candidates = (
        db.query(Item)
        .options(joinedload(Item.category))
        .filter(
            or_(
                Item.name.ilike(f"%{name_lower}%"),
                Item.name.ilike(f"{first4}%"),
            )
        )
        .limit(50)
        .all()
    )
    scored = []
    for item in candidates:
        if exclude_id and item.id == exclude_id:
            continue
        ratio = SequenceMatcher(None, name_lower, item.name.lower()).ratio()
        if ratio >= 0.60:
            scored.append((ratio, item))
    scored.sort(key=lambda x: -x[0])
    results = []
    for _, item in scored[:6]:
        summary = ItemSummary.model_validate(item)
        summary.low_stock = item.quantity <= item.min_quantity and item.min_quantity > 0
        results.append(summary)
    return results


@router.get("", response_model=List[ItemSummary])
def list_items(
    q: Optional[str] = Query(None),
    is_assembly: Optional[bool] = Query(None),
    category_id: Optional[int] = None,
    low_stock: Optional[bool] = None,
    location_id: Optional[int] = None,
    skip: int = 0,
    limit: int = 200,
    db: Session = Depends(get_db),
):
    query = db.query(Item).options(
        joinedload(Item.category),
        joinedload(Item.locations).joinedload(ItemLocation.location),
    )
    if q:
        like = f"%{q}%"
        query = (
            query
            .outerjoin(ItemFieldValue, ItemFieldValue.item_id == Item.id)
            .filter(
                or_(
                    Item.name.ilike(like),
                    Item.sku.ilike(like),
                    Item.barcode.ilike(like),
                    Item.material.ilike(like),
                    Item.color.ilike(like),
                    Item.manufacturer.ilike(like),
                    ItemFieldValue.value.ilike(like),
                )
            )
            .distinct()
        )
    if category_id is not None:
        query = query.filter(Item.category_id == category_id)
    if is_assembly is not None:
        query = query.filter(Item.is_assembly == is_assembly)
    if location_id is not None:
        query = query.join(Item.locations).filter(ItemLocation.location_id == location_id)

    items = query.offset(skip).limit(limit).all()
    results = []
    for item in items:
        d = ItemSummary.model_validate(item)
        d.low_stock = item.quantity <= item.min_quantity and item.min_quantity > 0
        if low_stock is not None and d.low_stock != low_stock:
            continue
        results.append(d)
    return results


@router.post("", response_model=ItemOut, status_code=201)
def create_item(data: ItemCreate, db: Session = Depends(get_db)):
    links = data.supplier_links
    item_data = data.model_dump(exclude={"supplier_links"})
    item = Item(**item_data)
    db.add(item)
    db.flush()
    for link in links:
        db.add(SupplierLink(item_id=item.id, **link.model_dump()))
    db.commit()
    return _load_item(db, item.id)


@router.get("/barcode/{barcode}", response_model=ItemOut)
def get_by_barcode(barcode: str, db: Session = Depends(get_db)):
    item = db.query(Item).filter(Item.barcode == barcode).first()
    if not item:
        raise HTTPException(404, "No item with that barcode")
    return _load_item(db, item.id)


@router.get("/{item_id}", response_model=ItemOut)
def get_item(item_id: int, db: Session = Depends(get_db)):
    return _load_item(db, item_id)


@router.patch("/{item_id}", response_model=ItemOut)
def update_item(item_id: int, data: ItemUpdate, db: Session = Depends(get_db)):
    item = db.get(Item, item_id)
    if not item:
        raise HTTPException(404, "Item not found")
    for k, v in data.model_dump(exclude_none=True).items():
        setattr(item, k, v)
    db.commit()
    if item.ha_exposed:
        try:
            from .. import ha_service
            cat = item.category.name if item.category else ""
            low = item.quantity <= item.min_quantity and item.min_quantity > 0
            ha_service.push_item_state(item.id, item.name, item.quantity, item.unit_name, cat, low)
        except Exception:
            pass
    return _load_item(db, item_id)


@router.delete("/{item_id}", status_code=204)
def delete_item(item_id: int, db: Session = Depends(get_db)):
    item = db.get(Item, item_id)
    if not item:
        raise HTTPException(404, "Item not found")
    db.delete(item)
    db.commit()


@router.post("/{item_id}/suppliers", response_model=SupplierLinkOut, status_code=201)
def add_supplier(item_id: int, data: SupplierLinkCreate, db: Session = Depends(get_db)):
    if not db.get(Item, item_id):
        raise HTTPException(404, "Item not found")
    link = SupplierLink(item_id=item_id, **data.model_dump())
    db.add(link)
    db.commit()
    db.refresh(link)
    return link


@router.delete("/{item_id}/suppliers/{link_id}", status_code=204)
def delete_supplier(item_id: int, link_id: int, db: Session = Depends(get_db)):
    link = db.query(SupplierLink).filter(
        SupplierLink.id == link_id, SupplierLink.item_id == item_id
    ).first()
    if not link:
        raise HTTPException(404, "Supplier link not found")
    db.delete(link)
    db.commit()


@router.post("/{item_id}/locations/{location_id}", response_model=ItemOut)
def set_item_location(
    item_id: int,
    location_id: int,
    qty: float = Query(0.0),
    db: Session = Depends(get_db),
):
    if not db.get(Item, item_id):
        raise HTTPException(404, "Item not found")
    if not db.get(Location, location_id):
        raise HTTPException(404, "Location not found")
    il = (
        db.query(ItemLocation)
        .filter(ItemLocation.item_id == item_id, ItemLocation.location_id == location_id)
        .first()
    )
    if il:
        il.quantity = qty
    else:
        il = ItemLocation(item_id=item_id, location_id=location_id, quantity=qty)
        db.add(il)
    db.commit()
    return _load_item(db, item_id)


@router.delete("/{item_id}/locations/{location_id}", response_model=ItemOut)
def remove_item_location(item_id: int, location_id: int, db: Session = Depends(get_db)):
    il = (
        db.query(ItemLocation)
        .filter(ItemLocation.item_id == item_id, ItemLocation.location_id == location_id)
        .first()
    )
    if il:
        db.delete(il)
        db.commit()
    return _load_item(db, item_id)


@router.post("/{item_id}/transactions", response_model=TransactionOut, status_code=201)
def create_transaction(
    item_id: int,
    data: TransactionCreate,
    db: Session = Depends(get_db),
    username: Optional[str] = Depends(_optional_username),
):
    from ..models import Transaction
    item = db.get(Item, item_id)
    if not item:
        raise HTTPException(404, "Item not found")
    before = item.quantity
    after = before + data.quantity_change
    if after < 0:
        raise HTTPException(400, "Quantity cannot go negative")
    item.quantity = after
    tx = Transaction(
        item_id=item_id,
        transaction_type=data.transaction_type,
        quantity_change=data.quantity_change,
        quantity_before=before,
        quantity_after=after,
        from_location_id=data.from_location_id,
        to_location_id=data.to_location_id,
        notes=data.notes,
        created_by=username,
    )
    db.add(tx)
    db.commit()
    db.refresh(tx)
    if item.ha_exposed:
        try:
            from .. import ha_service
            cat = item.category.name if item.category else ""
            low = item.quantity <= item.min_quantity and item.min_quantity > 0
            ha_service.push_item_state(item.id, item.name, item.quantity, item.unit_name, cat, low)
        except Exception:
            pass
    return tx


@router.get("/{item_id}/transactions", response_model=List[TransactionOut])
def list_item_transactions(
    item_id: int,
    limit: int = 50,
    db: Session = Depends(get_db),
):
    from ..models import Transaction
    if not db.get(Item, item_id):
        raise HTTPException(404, "Item not found")
    return (
        db.query(Transaction)
        .filter(Transaction.item_id == item_id)
        .order_by(Transaction.created_at.desc())
        .limit(limit)
        .all()
    )


# ── Assembly components ───────────────────────────────────────────────────────

@router.get("/{item_id}/components")
def list_components(item_id: int, db: Session = Depends(get_db)):
    item = db.get(Item, item_id)
    if not item:
        raise HTTPException(404, "Item not found")
    comps = db.query(AssemblyComponent).filter(AssemblyComponent.assembly_id == item_id).all()
    return [
        {
            "id": c.id,
            "component_id": c.component_id,
            "component_name": c.component.name if c.component else None,
            "component_unit": c.component.unit_name if c.component else None,
            "quantity_per_unit": c.quantity_per_unit,
            "in_stock": c.component.quantity if c.component else 0,
        }
        for c in comps
    ]


@router.post("/{item_id}/components", status_code=201)
def add_component(item_id: int, body: dict, db: Session = Depends(get_db)):
    item = db.get(Item, item_id)
    if not item or not item.is_assembly:
        raise HTTPException(400, "Item is not an assembly")
    comp_id = body.get("component_id")
    qty = float(body.get("quantity_per_unit", 1.0))
    if not comp_id:
        raise HTTPException(400, "component_id required")
    comp = db.get(Item, comp_id)
    if not comp:
        raise HTTPException(404, "Component item not found")
    existing = db.query(AssemblyComponent).filter(
        AssemblyComponent.assembly_id == item_id,
        AssemblyComponent.component_id == comp_id,
    ).first()
    if existing:
        existing.quantity_per_unit = qty
        db.commit()
        return {"id": existing.id, "component_id": comp_id, "quantity_per_unit": qty}
    ac = AssemblyComponent(assembly_id=item_id, component_id=comp_id, quantity_per_unit=qty)
    db.add(ac)
    db.commit()
    db.refresh(ac)
    return {"id": ac.id, "component_id": comp_id, "quantity_per_unit": qty}


@router.delete("/{item_id}/components/{comp_id}", status_code=204)
def remove_component(item_id: int, comp_id: int, db: Session = Depends(get_db)):
    ac = db.query(AssemblyComponent).filter(
        AssemblyComponent.assembly_id == item_id,
        AssemblyComponent.id == comp_id,
    ).first()
    if not ac:
        raise HTTPException(404, "Component not found")
    db.delete(ac)
    db.commit()


@router.post("/{item_id}/build")
def build_assembly(item_id: int, db: Session = Depends(get_db)):
    """Build 1x assembly: deduct components, increment assembly stock, log transactions."""
    assembly = db.get(Item, item_id)
    if not assembly or not assembly.is_assembly:
        raise HTTPException(400, "Item is not an assembly")
    comps = db.query(AssemblyComponent).filter(AssemblyComponent.assembly_id == item_id).all()
    if not comps:
        raise HTTPException(400, "Assembly has no components defined")
    shortfalls = []
    for c in comps:
        part = db.get(Item, c.component_id)
        if not part or part.quantity < c.quantity_per_unit:
            shortfalls.append(
                f"{part.name if part else c.component_id}: need {c.quantity_per_unit}, have {part.quantity if part else 0}"
            )
    if shortfalls:
        raise HTTPException(409, "Insufficient stock: " + "; ".join(shortfalls))
    for c in comps:
        part = db.get(Item, c.component_id)
        before = part.quantity
        part.quantity = round(before - c.quantity_per_unit, 6)
        db.add(Transaction(
            item_id=part.id,
            transaction_type="remove",
            quantity_change=-c.quantity_per_unit,
            quantity_before=before,
            quantity_after=part.quantity,
            notes=f"Built: {assembly.name} x1",
        ))
    asm_before = assembly.quantity
    assembly.quantity = round(asm_before + 1, 6)
    db.add(Transaction(
        item_id=assembly.id,
        transaction_type="add",
        quantity_change=1,
        quantity_before=asm_before,
        quantity_after=assembly.quantity,
        notes="Assembly built from components",
    ))
    db.commit()
    db.refresh(assembly)
    return {"built": 1, "assembly_qty": assembly.quantity}


# ── Merge ─────────────────────────────────────────────────────────────────────

@router.post("/{primary_id}/merge")
def merge_items(primary_id: int, body: dict, db: Session = Depends(get_db)):
    """Merge source item into primary: re-parent all relations, sum quantities, delete source."""
    import json as _json
    source_id = body.get("source_id")
    if not source_id:
        raise HTTPException(400, "source_id required")
    if primary_id == source_id:
        raise HTTPException(400, "Cannot merge an item with itself")

    primary = db.get(Item, primary_id)
    source  = db.get(Item, source_id)
    if not primary:
        raise HTTPException(404, "Primary item not found")
    if not source:
        raise HTTPException(404, "Source item not found")

    source_qty = source.quantity or 0

    # 1. Sum quantities
    primary.quantity = round((primary.quantity or 0) + source_qty, 6)

    # 2. Merge packages_json
    try:
        pkgs_p = _json.loads(primary.packages_json or "[]")
        pkgs_s = _json.loads(source.packages_json or "[]")
        if pkgs_s:
            primary.packages_json = _json.dumps(pkgs_p + pkgs_s)
    except Exception:
        pass

    # 3. Merge item_locations (with optional location_map overrides)
    # location_map: {str(source_location_id): target_location_id_on_primary}
    raw_map = body.get("location_map", {})
    location_map = {int(k): int(v) for k, v in raw_map.items() if v}

    primary_locs = {il.location_id: il for il in
                    db.query(ItemLocation).filter(ItemLocation.item_id == primary_id).all()}
    for il in db.query(ItemLocation).filter(ItemLocation.item_id == source_id).all():
        target_loc_id = location_map.get(il.location_id, il.location_id)
        if target_loc_id in primary_locs:
            primary_locs[target_loc_id].quantity = round(
                (primary_locs[target_loc_id].quantity or 0) + (il.quantity or 0), 6)
            db.delete(il)
        else:
            # Adopt: redirect to target location (may be same or remapped)
            il.item_id = primary_id
            if target_loc_id != il.location_id:
                il.location_id = target_loc_id

    # 4. Re-parent transactions
    for t in db.query(Transaction).filter(Transaction.item_id == source_id).all():
        t.item_id = primary_id

    # 5. Re-parent supplier links
    for sl in db.query(SupplierLink).filter(SupplierLink.item_id == source_id).all():
        sl.item_id = primary_id

    # 6. Re-parent project_items
    existing_proj = {pi.project_id for pi in
                     db.query(ProjectItem).filter(ProjectItem.item_id == primary_id).all()}
    for pi in db.query(ProjectItem).filter(ProjectItem.item_id == source_id).all():
        if pi.project_id in existing_proj:
            db.delete(pi)
        else:
            pi.item_id = primary_id

    # 7. Re-parent po_items
    from ..models import POItem
    for poi in db.query(POItem).filter(POItem.item_id == source_id).all():
        poi.item_id = primary_id

    # 8. Re-parent kit_items
    existing_kits = {ki.kit_id for ki in
                     db.query(KitItem).filter(KitItem.item_id == primary_id).all()}
    for ki in db.query(KitItem).filter(KitItem.item_id == source_id).all():
        if ki.kit_id in existing_kits:
            db.delete(ki)
        else:
            ki.item_id = primary_id

    # 9. Re-parent assembly_components
    existing_asms = {ac.assembly_id for ac in
                     db.query(AssemblyComponent).filter(AssemblyComponent.component_id == primary_id).all()}
    for ac in db.query(AssemblyComponent).filter(AssemblyComponent.component_id == source_id).all():
        if ac.assembly_id in existing_asms:
            db.delete(ac)
        else:
            ac.component_id = primary_id
    for ac in db.query(AssemblyComponent).filter(AssemblyComponent.assembly_id == source_id).all():
        ac.assembly_id = primary_id

    # 10. Re-parent item_field_values
    existing_fields = {fv.field_id for fv in
                       db.query(ItemFieldValue).filter(ItemFieldValue.item_id == primary_id).all()}
    for fv in db.query(ItemFieldValue).filter(ItemFieldValue.item_id == source_id).all():
        if fv.field_id in existing_fields:
            db.delete(fv)
        else:
            fv.item_id = primary_id

    # 11. Log merge transaction
    qty_before = round(primary.quantity - source_qty, 6)
    db.add(Transaction(
        item_id=primary_id,
        transaction_type="adjustment",
        quantity_change=source_qty,
        quantity_before=qty_before,
        quantity_after=primary.quantity,
        notes=f"Merged from: {source.name} (id {source_id})",
    ))

    # 12. Delete source and commit
    db.flush()
    db.delete(source)
    db.commit()
    db.refresh(primary)

    from ..schemas import ItemOut
    return ItemOut.model_validate(primary)
