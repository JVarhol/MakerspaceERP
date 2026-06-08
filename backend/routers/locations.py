from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import func
from typing import List

from ..database import get_db
from ..models import Location, ItemLocation
from ..schemas import LocationCreate, LocationUpdate, LocationOut

from ..auth import get_current_user, require_permission, can
from ..models import User
router = APIRouter(prefix="/api/locations", tags=["locations"], dependencies=[Depends(get_current_user)])
_W = Depends(require_permission('locations', 'write'))


def _is_restricted(loc: Location, db) -> bool:
    """Returns True if the location or any ancestor is restricted."""
    visited = set()
    current = loc
    while current:
        if current.id in visited:
            break
        visited.add(current.id)
        if current.is_restricted:
            return True
        if current.parent_id:
            current = db.get(Location, current.parent_id)
        else:
            break
    return False


def _publish_loc(db, loc):
    """Publish location state if module enabled."""
    try:
        from .. import mqtt_service, ha_service
        count = db.query(func.count(ItemLocation.id)).filter(ItemLocation.location_id == loc.id).scalar() or 0
        if mqtt_service._is_module_mqtt_enabled(db, "locations"):
            mqtt_service.publish_location_discovery(loc.id, loc.name)
            mqtt_service.publish_location_state(loc.id, loc.name, count, loc.location_type or "")
        if ha_service._is_module_ha_enabled(db, "locations"):
            ha_service.push_location_state(loc.id, loc.name, count, loc.location_type or "")
    except Exception:
        pass


@router.get("", response_model=List[LocationOut])
def list_locations(_cu: User = Depends(get_current_user), db: Session = Depends(get_db)):
    locs = db.query(Location).order_by(Location.name).all()
    if not can(_cu, 'restricted_locations'):
        locs = [l for l in locs if not _is_restricted(l, db)]
    return locs


@router.post("", response_model=LocationOut, status_code=201)
def create_location(data: LocationCreate, _w=_W, db: Session = Depends(get_db)):
    loc = Location(**data.model_dump())
    db.add(loc)
    db.commit()
    db.refresh(loc)
    _publish_loc(db, loc)
    return loc


@router.get("/{loc_id}", response_model=LocationOut)
def get_location(loc_id: int, db: Session = Depends(get_db)):
    loc = db.get(Location, loc_id)
    if not loc:
        raise HTTPException(404, "Location not found")
    return loc


@router.patch("/{loc_id}", response_model=LocationOut)
def update_location(loc_id: int, data: LocationUpdate, _w=_W, db: Session = Depends(get_db)):
    loc = db.get(Location, loc_id)
    if not loc:
        raise HTTPException(404, "Location not found")
    for k, v in data.model_dump(exclude_none=True).items():
        setattr(loc, k, v)
    db.commit()
    db.refresh(loc)
    _publish_loc(db, loc)
    return loc


@router.delete("/{loc_id}", status_code=204)
def delete_location(loc_id: int, _w=_W, db: Session = Depends(get_db)):
    loc = db.get(Location, loc_id)
    if not loc:
        raise HTTPException(404, "Location not found")
    try:
        from .. import mqtt_service
        mqtt_service.remove_location_discovery(loc_id)
    except Exception:
        pass
    db.delete(loc)
    db.commit()
