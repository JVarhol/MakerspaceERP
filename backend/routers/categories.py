from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import func
from typing import List

from ..database import get_db
from ..models import Category, Item
from ..schemas import CategoryCreate, CategoryUpdate, CategoryOut

from ..auth import get_current_user, require_permission
router = APIRouter(prefix="/api/categories", tags=["categories"], dependencies=[Depends(get_current_user)])
_W = Depends(require_permission('categories', 'write'))


def _publish_cat(db, cat):
    try:
        from .. import mqtt_service, ha_service
        count = db.query(func.count(Item.id)).filter(Item.category_id == cat.id).scalar() or 0
        if mqtt_service._is_module_mqtt_enabled(db, "categories"):
            mqtt_service.publish_category_discovery(cat.id, cat.name)
            mqtt_service.publish_category_state(cat.id, cat.name, count)
        if ha_service._is_module_ha_enabled(db, "categories"):
            ha_service.push_category_state(cat.id, cat.name, count)
    except Exception:
        pass


@router.get("", response_model=List[CategoryOut])
def list_categories(db: Session = Depends(get_db)):
    return db.query(Category).order_by(Category.name).all()


@router.post("", response_model=CategoryOut, status_code=201)
def create_category(data: CategoryCreate, _w=_W, db: Session = Depends(get_db)):
    cat = Category(**data.model_dump())
    db.add(cat)
    db.commit()
    db.refresh(cat)
    _publish_cat(db, cat)
    return cat


@router.get("/{cat_id}", response_model=CategoryOut)
def get_category(cat_id: int, db: Session = Depends(get_db)):
    cat = db.get(Category, cat_id)
    if not cat:
        raise HTTPException(404, "Category not found")
    return cat


@router.patch("/{cat_id}", response_model=CategoryOut)
def update_category(cat_id: int, data: CategoryUpdate, _w=_W, db: Session = Depends(get_db)):
    cat = db.get(Category, cat_id)
    if not cat:
        raise HTTPException(404, "Category not found")
    for k, v in data.model_dump(exclude_none=True).items():
        setattr(cat, k, v)
    db.commit()
    db.refresh(cat)
    _publish_cat(db, cat)
    return cat


@router.delete("/{cat_id}", status_code=204)
def delete_category(cat_id: int, _w=_W, db: Session = Depends(get_db)):
    cat = db.get(Category, cat_id)
    if not cat:
        raise HTTPException(404, "Category not found")
    try:
        from .. import mqtt_service
        mqtt_service.remove_category_discovery(cat_id)
    except Exception:
        pass
    db.delete(cat)
    db.commit()
