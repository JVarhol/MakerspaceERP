"""
Router: category custom fields + item field values
Endpoints:
  GET    /api/categories/{cat_id}/fields
  POST   /api/categories/{cat_id}/fields
  PATCH  /api/categories/{cat_id}/fields/{field_id}
  DELETE /api/categories/{cat_id}/fields/{field_id}
  GET    /api/items/{item_id}/field-values
  POST   /api/items/{item_id}/field-values   (bulk upsert)
"""
from __future__ import annotations
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import Category, CategoryField, Item, ItemFieldValue

router = APIRouter(tags=["custom-fields"])


# ── Pydantic schemas ──────────────────────────────────────────────────────────

class FieldCreate(BaseModel):
    field_name: str
    field_type: str = "text"        # text | number | select | checkbox | date
    field_options: Optional[str] = None   # JSON string e.g. '["Red","Blue"]'
    required: bool = False
    sort_order: int = 0

class FieldUpdate(BaseModel):
    field_name: Optional[str] = None
    field_type: Optional[str] = None
    field_options: Optional[str] = None
    required: Optional[bool] = None
    sort_order: Optional[int] = None

class FieldOut(BaseModel):
    id: int
    category_id: int
    field_name: str
    field_type: str
    field_options: Optional[str] = None
    required: bool
    sort_order: int
    class Config:
        from_attributes = True

class FieldValueIn(BaseModel):
    field_id: int
    value: Optional[str] = None

class FieldValueOut(BaseModel):
    field_id: int
    field_name: str
    field_type: str
    value: Optional[str] = None
    class Config:
        from_attributes = True


# ── Category fields CRUD ──────────────────────────────────────────────────────

@router.get("/api/categories/{cat_id}/fields", response_model=List[FieldOut])
def list_fields(cat_id: int, db: Session = Depends(get_db)):
    cat = db.get(Category, cat_id)
    if not cat:
        raise HTTPException(404, "Category not found")
    return (
        db.query(CategoryField)
        .filter(CategoryField.category_id == cat_id)
        .order_by(CategoryField.sort_order, CategoryField.id)
        .all()
    )


@router.post("/api/categories/{cat_id}/fields", response_model=FieldOut, status_code=201)
def create_field(cat_id: int, body: FieldCreate, db: Session = Depends(get_db)):
    cat = db.get(Category, cat_id)
    if not cat:
        raise HTTPException(404, "Category not found")
    field = CategoryField(category_id=cat_id, **body.model_dump())
    db.add(field)
    db.commit()
    db.refresh(field)
    return field


@router.patch("/api/categories/{cat_id}/fields/{field_id}", response_model=FieldOut)
def update_field(cat_id: int, field_id: int, body: FieldUpdate, db: Session = Depends(get_db)):
    field = db.query(CategoryField).filter(
        CategoryField.id == field_id,
        CategoryField.category_id == cat_id,
    ).first()
    if not field:
        raise HTTPException(404, "Field not found")
    for k, v in body.model_dump(exclude_none=True).items():
        setattr(field, k, v)
    db.commit()
    db.refresh(field)
    return field


@router.delete("/api/categories/{cat_id}/fields/{field_id}", status_code=204)
def delete_field(cat_id: int, field_id: int, db: Session = Depends(get_db)):
    field = db.query(CategoryField).filter(
        CategoryField.id == field_id,
        CategoryField.category_id == cat_id,
    ).first()
    if not field:
        raise HTTPException(404, "Field not found")
    db.delete(field)
    db.commit()


# ── Item field values ─────────────────────────────────────────────────────────

@router.get("/api/items/{item_id}/field-values", response_model=List[FieldValueOut])
def get_field_values(item_id: int, db: Session = Depends(get_db)):
    item = db.get(Item, item_id)
    if not item:
        raise HTTPException(404, "Item not found")
    # Return values joined with field metadata so the client has all it needs
    values = (
        db.query(ItemFieldValue)
        .filter(ItemFieldValue.item_id == item_id)
        .all()
    )
    return [
        FieldValueOut(
            field_id=v.field_id,
            field_name=v.field.field_name,
            field_type=v.field.field_type,
            value=v.value,
        )
        for v in values
    ]


@router.post("/api/items/{item_id}/field-values", status_code=204)
def save_field_values(item_id: int, body: List[FieldValueIn], db: Session = Depends(get_db)):
    """Bulk upsert: replace all custom field values for this item."""
    item = db.get(Item, item_id)
    if not item:
        raise HTTPException(404, "Item not found")
    # Delete existing values for the submitted field_ids
    field_ids = [v.field_id for v in body]
    db.query(ItemFieldValue).filter(
        ItemFieldValue.item_id == item_id,
        ItemFieldValue.field_id.in_(field_ids),
    ).delete(synchronize_session=False)
    # Insert new values (skip blank ones)
    for v in body:
        if v.value is not None and v.value != "":
            db.add(ItemFieldValue(item_id=item_id, field_id=v.field_id, value=v.value))
    db.commit()
