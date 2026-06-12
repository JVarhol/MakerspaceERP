from __future__ import annotations
from typing import List, Optional
from datetime import datetime
from pydantic import BaseModel, ConfigDict, HttpUrl, field_validator


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
    is_restricted: bool = False
    bin_id: Optional[str] = None
    icon: Optional[str] = None

class LocationCreate(LocationBase):
    pass

class LocationUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    parent_id: Optional[int] = None
    location_type: Optional[str] = None
    is_restricted: Optional[bool] = None
    bin_id: Optional[str] = None
    icon: Optional[str] = None

class LocationOut(LocationBase):
    id: int
    class Config:
        from_attributes = True


# ── Supplier ──────────────────────────────────────────────────────────────────

class SupplierBase(BaseModel):
    name: str
    contact_name: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    address: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    zip: Optional[str] = None
    country: Optional[str] = None
    website: Optional[str] = None
    account_number: Optional[str] = None
    notes: Optional[str] = None

class SupplierCreate(SupplierBase):
    pass

class SupplierUpdate(BaseModel):
    name: Optional[str] = None
    contact_name: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    address: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    zip: Optional[str] = None
    country: Optional[str] = None
    website: Optional[str] = None
    account_number: Optional[str] = None
    notes: Optional[str] = None

class SupplierOut(SupplierBase):
    id: int
    created_at: Optional[datetime] = None
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
    effective_restricted: bool = False
    class Config:
        from_attributes = True


# ── Item ──────────────────────────────────────────────────────────────────────

class ItemBase(BaseModel):
    name: str
    description: Optional[str] = None
    barcode: Optional[str] = None
    sku: Optional[str] = None
    alt_skus: Optional[str] = None
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
    unit_weight: Optional[float] = None
    spool_empty_weight: Optional[float] = None
    is_assembly: bool = False
    mqtt_exposed: bool = False
    ha_exposed: bool = False
    is_hazmat: bool = False
    sds_url: Optional[str] = None

class ItemCreate(ItemBase):
    supplier_links: List[SupplierLinkCreate] = []

class ItemUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    barcode: Optional[str] = None
    sku: Optional[str] = None
    alt_skus: Optional[str] = None
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
    unit_weight: Optional[float] = None
    spool_empty_weight: Optional[float] = None
    is_assembly: Optional[bool] = None
    mqtt_exposed: Optional[bool] = None
    ha_exposed: Optional[bool] = None
    is_hazmat: Optional[bool] = None
    sds_url: Optional[str] = None

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
    alt_skus: Optional[str] = None
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
    unit_weight: Optional[float] = None
    spool_empty_weight: Optional[float] = None
    is_hazmat: bool = False
    sds_url: Optional[str] = None
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
    from_location_name: Optional[str] = None
    to_location_name: Optional[str] = None
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
    assigned_to: Optional[str] = None

class ProjectCreate(ProjectBase):
    pass

class ProjectUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    status: Optional[str] = None
    labor_hours: Optional[float] = None
    labor_rate: Optional[float] = None
    markup_pct: Optional[float] = None
    assigned_to: Optional[str] = None

class ProjectTimeEntryOut(BaseModel):
    id: int
    project_id: int
    user: Optional[str] = None
    clock_in: Optional[datetime] = None
    clock_out: Optional[datetime] = None
    hours: Optional[float] = None
    description: Optional[str] = None
    created_at: Optional[datetime] = None
    class Config:
        from_attributes = True

class ProjectTimeEntryCreate(BaseModel):
    clock_in: Optional[datetime] = None
    clock_out: Optional[datetime] = None
    hours: Optional[float] = None
    description: Optional[str] = None

class ProjectTimeEntryUpdate(BaseModel):
    clock_out: Optional[datetime] = None
    hours: Optional[float] = None
    description: Optional[str] = None

class ProjectOut(ProjectBase):
    id: int
    created_at: Optional[datetime] = None
    items: List[ProjectItemOut] = []
    time_entries: List[ProjectTimeEntryOut] = []
    shares: List[str] = []

    @field_validator('shares', mode='before')
    @classmethod
    def coerce_shares(cls, v):
        if not v:
            return []
        return [x.username if hasattr(x, 'username') else str(x) for x in v]

    model_config = ConfigDict(from_attributes=True)


# ── Purchase Orders ───────────────────────────────────────────────────────────

class POItemCreate(BaseModel):
    item_id: int
    quantity_ordered: float
    unit_price: Optional[float] = None
    notes: Optional[str] = None

class POItemUpdate(BaseModel):
    quantity_ordered: Optional[float] = None
    unit_price: Optional[float] = None
    notes: Optional[str] = None
    status: Optional[str] = None

class POItemReceive(BaseModel):
    quantity_received: float
    notes: Optional[str] = None
    location_id: Optional[int] = None

class POItemOut(BaseModel):
    id: int
    po_id: int
    item_id: int
    quantity_ordered: float
    quantity_received: float
    unit_price: Optional[float] = None
    notes: Optional[str] = None
    status: str
    item: Optional[ItemSummary] = None
    class Config:
        from_attributes = True

class PurchaseOrderCreate(BaseModel):
    supplier_id: Optional[int] = None
    supplier_name: Optional[str] = None
    expected_date: Optional[str] = None
    notes: Optional[str] = None
    items: List[POItemCreate] = []
    # Legacy single-item fields (still accepted for backward compat)
    item_id: Optional[int] = None
    quantity_ordered: Optional[float] = None

class PurchaseOrderUpdate(BaseModel):
    po_number: Optional[str] = None
    supplier_id: Optional[int] = None
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
    supplier_id: Optional[int] = None
    supplier_name: Optional[str] = None
    supplier: Optional[SupplierOut] = None
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
    mqtt_exposed: bool = False
    ha_exposed: bool = False

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
    booked_by: Optional[str] = None   # set at query time when an active booking exists
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
    item_locations: List[ItemLocationOut] = []
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

class KitRestockBody(BaseModel):
    """Optional body for kit restock. location_overrides maps item_id -> location_id."""
    location_overrides: Optional[dict] = None


# ── Pull Tickets ──────────────────────────────────────────────────────────────

class PullTicketLineOut(BaseModel):
    id: int
    ticket_id: int
    item_id: int
    quantity_needed: float
    quantity_pulled: float
    from_location_id: Optional[int] = None
    status: str
    notes: Optional[str] = None
    item_name: Optional[str] = None
    item_unit: Optional[str] = None
    from_location_name: Optional[str] = None
    class Config:
        from_attributes = True

class PullTicketOut(BaseModel):
    id: int
    ticket_number: Optional[str] = None
    status: str
    pull_type: str
    to_location_id: Optional[int] = None
    project_id: Optional[int] = None
    notes: Optional[str] = None
    created_by: Optional[str] = None
    created_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    to_location_name: Optional[str] = None
    project_name: Optional[str] = None
    lines: List[PullTicketLineOut] = []
    class Config:
        from_attributes = True

class PullTicketCreate(BaseModel):
    pull_type: str = "out_of_inventory"  # out_of_inventory | move_location | assign_project
    to_location_id: Optional[int] = None
    project_id: Optional[int] = None
    notes: Optional[str] = None
    ticket_number: Optional[str] = None

class PullTicketUpdate(BaseModel):
    pull_type: Optional[str] = None
    to_location_id: Optional[int] = None
    project_id: Optional[int] = None
    notes: Optional[str] = None
    status: Optional[str] = None
    ticket_number: Optional[str] = None

class PullTicketLineCreate(BaseModel):
    item_id: int
    quantity_needed: float = 1.0
    from_location_id: Optional[int] = None
    notes: Optional[str] = None

class PullLineAction(BaseModel):
    """Used for pulling a line item: how much to pull and optional override location."""
    quantity: Optional[float] = None
    from_location_id: Optional[int] = None


# ── Service ───────────────────────────────────────────────────────────────────

class ServiceBase(BaseModel):
    name: str
    category: str = "other"       # fee | labor | materials | other
    description: Optional[str] = None
    unit_price: float = 0.0
    default_markup_pct: float = 0.0
    use_markup: bool = False
    is_active: bool = True

class ServiceCreate(ServiceBase):
    pass

class ServiceUpdate(BaseModel):
    name: Optional[str] = None
    category: Optional[str] = None
    description: Optional[str] = None
    unit_price: Optional[float] = None
    default_markup_pct: Optional[float] = None
    use_markup: Optional[bool] = None
    is_active: Optional[bool] = None

class ServiceOut(ServiceBase):
    id: int
    created_at: Optional[datetime] = None
    class Config:
        from_attributes = True


# ── Invoice ───────────────────────────────────────────────────────────────────

class InvoiceLineBase(BaseModel):
    line_type: str = "part"        # part | labor | service
    description: str = ""
    quantity: float = 1.0
    unit_price: float = 0.0
    markup_pct: float = 0.0
    use_markup: bool = False
    item_id: Optional[int] = None
    service_id: Optional[int] = None
    sort_order: int = 0

class InvoiceLineCreate(InvoiceLineBase):
    pass

class InvoiceLineUpdate(BaseModel):
    line_type: Optional[str] = None
    description: Optional[str] = None
    quantity: Optional[float] = None
    unit_price: Optional[float] = None
    markup_pct: Optional[float] = None
    use_markup: Optional[bool] = None
    item_id: Optional[int] = None
    service_id: Optional[int] = None
    sort_order: Optional[int] = None

class InvoiceLineOut(InvoiceLineBase):
    id: int
    invoice_id: int
    class Config:
        from_attributes = True

class InvoiceBase(BaseModel):
    project_id: Optional[int] = None
    invoice_type: str = "invoice"  # quote | invoice
    status: str = "draft"          # draft | sent | accepted | paid | void
    invoice_number: Optional[str] = None
    client_name: Optional[str] = None
    client_address: Optional[str] = None
    invoice_date: Optional[str] = None
    due_date: Optional[str] = None
    notes: Optional[str] = None
    terms: Optional[str] = None
    tax_pct: float = 0.0

class InvoiceCreate(InvoiceBase):
    lines: List[InvoiceLineCreate] = []

class InvoiceUpdate(BaseModel):
    project_id: Optional[int] = None
    invoice_type: Optional[str] = None
    status: Optional[str] = None
    invoice_number: Optional[str] = None
    client_name: Optional[str] = None
    client_address: Optional[str] = None
    invoice_date: Optional[str] = None
    due_date: Optional[str] = None
    notes: Optional[str] = None
    terms: Optional[str] = None
    tax_pct: Optional[float] = None

class InvoiceOut(InvoiceBase):
    id: int
    created_at: Optional[datetime] = None
    sent_at: Optional[datetime] = None
    paid_at: Optional[datetime] = None
    project_name: Optional[str] = None
    lines: List[InvoiceLineOut] = []
    model_config = ConfigDict(from_attributes=True)
