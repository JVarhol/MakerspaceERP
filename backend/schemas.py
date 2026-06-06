from __future__ import annotations
from typing import List, Optional
from datetime import datetime
from pydantic import BaseModel, HttpUrl


# ── Material ──────────────────────────────────────────────────────────────────

class MaterialBase(BaseModel):
    name: str
    description: Optional[str] = None
    color: str = "#6366f1"
    notes: Optional[str] = None
    mqtt_exposed: Optional[bool] = None
class MaterialCreate(MaterialBase):
    pass

class MaterialUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    color: Optional[str] = None
    notes: Optional[str] = None

class MaterialOut(MaterialBase):
    id: int
    class Config:
        from_attributes = True


# ── Category ─────────────────────────────────────────────────────────────────

class CategoryBase(BaseModel):
    name: str
    parent_id: Optional[int] = None
    color: str = "#6366f1"
    icon: str = "📦"
    default_unit_name: Optional[str] = None
    default_package_behavior: Optional[str] = None  # bulk | spool

class CategoryCreate(CategoryBase):
    pass

class CategoryUpdate(BaseModel):
    name: Optional[str] = None
    parent_id: Optional[int] = None
    color: Optional[str] = None
    icon: Optional[str] = None
    default_unit_name: Optional[str] = None
    default_package_behavior: Optional[str] = None

class CategoryOut(CategoryBase):
    id: int
    class Config:
        from_attributes = True


# ── Location ──────────────────────────────────────────────────────────────────

class LocationBase(BaseModel):
    name: str
    description: Optional[str] = None
    parent_id: Optional[int] = None
    location_type: str = "bin"

class LocationCreate(LocationBase):
    pass

class LocationUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    parent_id: Optional[int] = None
    location_type: Optional[str] = None

class LocationOut(LocationBase):
    id: int
    class Config:
        from_attributes = True


# ── Supplier Link ─────────────────────────────────────────────────────────────

class SupplierLinkBase(BaseModel):
    url: str
    supplier_name: Optional[str] = None
    price: Optional[float] = None
    currency: str = "USD"
    notes: Optional[str] = None

class SupplierLinkCreate(SupplierLinkBase):
    pass

class SupplierLinkOut(SupplierLinkBase):
    id: int
    item_id: int
    created_at: Optional[datetime] = None
    class Config:
        from_attributes = True


# ── Item Location ─────────────────────────────────────────────────────────────

class ItemLocationOut(BaseModel):
    id: int
    location_id: int
    location: LocationOut
    quantity: float
    class Config:
        from_attributes = True


# ── Item ──────────────────────────────────────────────────────────────────────

class ItemBase(BaseModel):
    name: str
    description: Optional[str] = None
    barcode: Optional[str] = None
    sku: Optional[str] = None
    category_id: Optional[int] = None
    unit_type: str = "quantity"   # quantity | weight | volume
    unit_name: str = "pcs"
    quantity: float = 0.0
    min_quantity: float = 0.0
    package_size: Optional[float] = None
    package_unit: Optional[str] = None
    material: Optional[str] = None
    color: Optional[str] = None
    manufacturer: Optional[str] = None
    price: Optional[float] = None
    date_purchased: Optional[str] = None
    packages_json: Optional[str] = None
    package_behavior: str = 'bulk'  # bulk | spool
    expiry_date: Optional[str] = None
    image_url: Optional[str] = None
    notes: Optional[str] = None
    is_assembly: bool = False
    mqtt_exposed: bool = False
    ha_exposed: bool = False

class ItemCreate(ItemBase):
    supplier_links: List[SupplierLinkCreate] = []

class ItemUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    barcode: Optional[str] = None
    sku: Optional[str] = None
    category_id: Optional[int] = None
    unit_type: Optional[str] = None
    unit_name: Optional[str] = None
    quantity: Optional[float] = None
    min_quantity: Optional[float] = None
    package_size: Optional[float] = None
    package_unit: Optional[str] = None
    material: Optional[str] = None
    color: Optional[str] = None
    manufacturer: Optional[str] = None
    price: Optional[float] = None
    date_purchased: Optional[str] = None
    packages_json: Optional[str] = None
    package_behavior: Optional[str] = None
    expiry_date: Optional[str] = None
    image_url: Optional[str] = None
    notes: Optional[str] = None
    is_assembly: Optional[bool] = None
    mqtt_exposed: Optional[bool] = None
    ha_exposed: Optional[bool] = None

class ItemOut(ItemBase):
    id: int
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    category: Optional[CategoryOut] = None
    locations: List[ItemLocationOut] = []
    supplier_links: List[SupplierLinkOut] = []
    class Config:
        from_attributes = True

class ItemSummary(BaseModel):
    id: int
    name: str
    barcode: Optional[str] = None
    sku: Optional[str] = None
    unit_type: str
    unit_name: str
    quantity: float
    min_quantity: float
    package_size: Optional[float] = None
    package_unit: Optional[str] = None
    material: Optional[str] = None
    color: Optional[str] = None
    manufacturer: Optional[str] = None
    price: Optional[float] = None
    date_purchased: Optional[str] = None
    category: Optional[CategoryOut] = None
    locations: List[ItemLocationOut] = []
    packages_json: Optional[str] = None
    package_behavior: str = 'bulk'
    low_stock: bool = False
    class Config:
        from_attributes = True


# ── Transaction ───────────────────────────────────────────────────────────────

class TransactionCreate(BaseModel):
    transaction_type: str           # add | remove | adjustment | move
    quantity_change: float
    from_location_id: Optional[int] = None
    to_location_id: Optional[int] = None
    notes: Optional[str] = None

class TransactionOut(BaseModel):
    id: int
    item_id: int
    transaction_type: str
    quantity_change: float
    quantity_before: float
    quantity_after: float
    from_location_id: Optional[int] = None
    to_location_id: Optional[int] = None
    notes: Optional[str] = None
    created_by: Optional[str] = None
    created_at: Optional[datetime] = None
    class Config:
        from_attributes = True


# ── Barcode lookup ────────────────────────────────────────────────────────────

class BarcodeLookupResult(BaseModel):
    barcode: str
    name: Optional[str] = None
    description: Optional[str] = None
    image_url: Optional[str] = None
    source: Optional[str] = None


# ── URL metadata ──────────────────────────────────────────────────────────────

class UrlMetaResult(BaseModel):
    url: str
    title: Optional[str] = None
    supplier_name: Optional[str] = None
    price: Optional[float] = None


# ── Project ───────────────────────────────────────────────────────────────────

class ProjectItemBase(BaseModel):
    item_id: int
    quantity_needed: float = 1.0
    notes: Optional[str] = None

class ProjectItemCreate(ProjectItemBase):
    pass

class ProjectItemOut(ProjectItemBase):
    id: int
    item: Optional[ItemSummary] = None
    class Config:
        from_attributes = True

class ProjectBase(BaseModel):
    name: str
    description: Optional[str] = None
    status: str = "planning"
    labor_hours: float = 0.0
    labor_rate: float = 0.0
    markup_pct: float = 0.0

class ProjectCreate(ProjectBase):
    pass

class ProjectUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    status: Optional[str] = None
    labor_hours: Optional[float] = None
    labor_rate: Optional[float] = None
    markup_pct: Optional[float] = None

class ProjectOut(ProjectBase):
    id: int
    created_at: Optional[datetime] = None
    items: List[ProjectItemOut] = []
    class Config:
        from_attributes = True


# ── Purchase Orders ───────────────────────────────────────────────────────────

class POItemCreate(BaseModel):
    item_id: int
    quantity_ordered: float
    notes: Optional[str] = None

class POItemUpdate(BaseModel):
    quantity_ordered: Optional[float] = None
    notes: Optional[str] = None
    status: Optional[str] = None

class POItemReceive(BaseModel):
    quantity_received: float
    notes: Optional[str] = None

class POItemOut(BaseModel):
    id: int
    po_id: int
    item_id: int
    quantity_ordered: float
    quantity_received: float
    notes: Optional[str] = None
    status: str
    item: Optional[ItemSummary] = None
    class Config:
        from_attributes = True

class PurchaseOrderCreate(BaseModel):
    supplier_name: Optional[str] = None
    expected_date: Optional[str] = None
    notes: Optional[str] = None
    items: List[POItemCreate] = []
    # Legacy single-item fields (still accepted for backward compat)
    item_id: Optional[int] = None
    quantity_ordered: Optional[float] = None

class PurchaseOrderUpdate(BaseModel):
    po_number: Optional[str] = None
    supplier_name: Optional[str] = None
    expected_date: Optional[str] = None
    notes: Optional[str] = None
    status: Optional[str] = None

class PurchaseOrderReceive(BaseModel):
    quantity_received: float
    notes: Optional[str] = None

class PurchaseOrderOut(BaseModel):
    id: int
    po_number: Optional[str] = None
    supplier_name: Optional[str] = None
    expected_date: Optional[str] = None
    notes: Optional[str] = None
    status: str
    created_at: Optional[datetime] = None
    line_items: List[POItemOut] = []
    # Legacy fields for backward compat
    item_id: Optional[int] = None
    quantity_ordered: Optional[float] = None
    quantity_received: Optional[float] = None
    item: Optional[ItemSummary] = None
    class Config:
        from_attributes = True


# ── Assets ───────────────────────────────────────────────────────────────────

class AssetCheckoutCreate(BaseModel):
    checked_out_by: str
    expected_return: Optional[str] = None
    notes: Optional[str] = None

class AssetCheckoutOut(BaseModel):
    id: int
    asset_id: int
    checked_out_by: str
    checked_out_at: Optional[datetime] = None
    expected_return: Optional[str] = None
    returned_at: Optional[datetime] = None
    notes: Optional[str] = None
    class Config:
        from_attributes = True

class AssetBase(BaseModel):
    name: str
    description: Optional[str] = None
    asset_tag: Optional[str] = None
    category: Optional[str] = None
    location_id: Optional[int] = None
    serial_number: Optional[str] = None
    manufacturer: Optional[str] = None
    model: Optional[str] = None
    purchase_date: Optional[str] = None
    purchase_price: Optional[float] = None
    image_url: Optional[str] = None
    notes: Optional[str] = None

class AssetCreate(AssetBase):
    pass

class AssetUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    asset_tag: Optional[str] = None
    category: Optional[str] = None
    location_id: Optional[int] = None
    status: Optional[str] = None
    serial_number: Optional[str] = None
    manufacturer: Optional[str] = None
    model: Optional[str] = None
    purchase_date: Optional[str] = None
    purchase_price: Optional[float] = None
    image_url: Optional[str] = None
    notes: Optional[str] = None
    mqtt_exposed: Optional[bool] = None
    ha_exposed: Optional[bool] = None

class AssetOut(AssetBase):
    id: int
    status: str
    created_at: Optional[datetime] = None
    location: Optional[LocationOut] = None
    checkouts: List[AssetCheckoutOut] = []
    current_checkout: Optional[AssetCheckoutOut] = None
    class Config:
        from_attributes = True


# ── Dashboard stats ───────────────────────────────────────────────────────────

class DashboardStats(BaseModel):
    total_items: int
    low_stock_items: int
    total_locations: int
    total_categories: int
    recent_transactions: List[TransactionOut] = []


# ── Kit ───────────────────────────────────────────────────────────────────────

class KitItemOut(BaseModel):
    id: int
    item_id: int
    quantity: float
    item_name: Optional[str] = None
    item_unit: Optional[str] = None
    class Config:
        from_attributes = True

class KitBase(BaseModel):
    name: str
    description: Optional[str] = None
    notes: Optional[str] = None
    color: str = "#6366f1"
    icon: str = "🧰"

class KitCreate(KitBase):
    pass

class KitUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    notes: Optional[str] = None
    color: Optional[str] = None
    icon: Optional[str] = None

class KitOut(KitBase):
    id: int
    kit_items: List[KitItemOut] = []
    class Config:
        from_attributes = True

class KitItemCreate(BaseModel):
    item_id: int
    quantity: float = 1.0


# ── Assembly ──────────────────────────────────────────────────────────────────

class AssemblyComponentOut(BaseModel):
    id: int
    component_id: int
    component_name: Optional[str] = None
    component_unit: Optional[str] = None
    quantity_per_unit: float
    in_stock: Optional[float] = None
    class Config:
        from_attributes = True

class AssemblyComponentCreate(BaseModel):
    component_id: int
    quantity_per_unit: float = 1.0


# ── App Settings ──────────────────────────────────────────────────────────────

class SettingOut(BaseModel):
    key: str
    value: Optional[str] = None
    class Config:
        from_attributes = True
