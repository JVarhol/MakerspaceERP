from sqlalchemy import (
    Column, Integer, String, Float, ForeignKey, Text, DateTime, Boolean, UniqueConstraint
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from .database import Base


class Material(Base):
    __tablename__ = "materials"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False, unique=True)
    description = Column(Text, nullable=True)
    color = Column(String, default="#6366f1")
    notes = Column(Text, nullable=True)


class Category(Base):
    __tablename__ = "categories"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False, unique=True)
    parent_id = Column(Integer, ForeignKey("categories.id"), nullable=True)
    color = Column(String, default="#6366f1")
    icon = Column(String, default="📦")
    default_unit_name = Column(String, nullable=True)
    default_package_behavior = Column(String, nullable=True)  # bulk | spool

    parent = relationship("Category", remote_side=[id], backref="children")
    items = relationship("Item", back_populates="category")


class Location(Base):
    __tablename__ = "locations"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    description = Column(Text, nullable=True)
    parent_id = Column(Integer, ForeignKey("locations.id"), nullable=True)
    location_type = Column(String, default="bin")  # shed, desk, bin, shelf, drawer, other

    parent = relationship("Location", remote_side=[id], backref="children")
    item_locations = relationship("ItemLocation", back_populates="location")


class Item(Base):
    __tablename__ = "items"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False, index=True)
    description = Column(Text, nullable=True)
    barcode = Column(String, nullable=True, unique=True, index=True)
    sku = Column(String, nullable=True, index=True)
    category_id = Column(Integer, ForeignKey("categories.id"), nullable=True)
    unit_type = Column(String, default="quantity")  # quantity | weight | volume
    unit_name = Column(String, default="pcs")       # pcs, g, kg, ml, L, oz, ft, m …
    quantity = Column(Float, default=0.0)
    min_quantity = Column(Float, default=0.0)       # low-stock threshold
    package_size = Column(Float, nullable=True)     # e.g. 1000 (g per spool)
    package_unit = Column(String, nullable=True)    # e.g. "spool", "roll", "bag"
    material = Column(String, nullable=True)        # e.g. PLA, ABS, M2, etc.
    color = Column(String, nullable=True)           # e.g. Black, Red, Natural
    manufacturer = Column(String, nullable=True)
    price = Column(Float, nullable=True)            # unit cost price
    date_purchased = Column(String, nullable=True)  # ISO date string
    packages_json = Column(Text, nullable=True)     # JSON array of spool states
    package_behavior = Column(String, default='bulk')  # bulk | spool
    expiry_date = Column(String, nullable=True)     # ISO date string
    image_url = Column(String, nullable=True)
    notes = Column(Text, nullable=True)
    is_assembly   = Column(Boolean, default=False)
    mqtt_exposed  = Column(Boolean, default=False)
    ha_exposed    = Column(Boolean, default=False)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    category = relationship("Category", back_populates="items")
    locations = relationship("ItemLocation", back_populates="item", cascade="all, delete-orphan")
    supplier_links = relationship("SupplierLink", back_populates="item", cascade="all, delete-orphan")
    transactions = relationship("Transaction", back_populates="item", cascade="all, delete-orphan")


class Project(Base):
    __tablename__ = "projects"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    description = Column(Text, nullable=True)
    status = Column(String, default="planning")  # planning | active | complete | archived
    labor_hours = Column(Float, default=0.0)
    labor_rate  = Column(Float, default=0.0)   # cost per hour
    markup_pct  = Column(Float, default=0.0)   # markup percentage (e.g. 15 = 15%)
    created_at = Column(DateTime, server_default=func.now())

    items = relationship("ProjectItem", back_populates="project", cascade="all, delete-orphan")


class ProjectItem(Base):
    __tablename__ = "project_items"
    __table_args__ = (UniqueConstraint("project_id", "item_id"),)

    id = Column(Integer, primary_key=True, index=True)
    project_id = Column(Integer, ForeignKey("projects.id"), nullable=False)
    item_id = Column(Integer, ForeignKey("items.id"), nullable=False)
    quantity_needed = Column(Float, default=1.0)
    notes = Column(Text, nullable=True)

    project = relationship("Project", back_populates="items")
    item = relationship("Item")


class ItemLocation(Base):
    __tablename__ = "item_locations"
    __table_args__ = (UniqueConstraint("item_id", "location_id"),)

    id = Column(Integer, primary_key=True, index=True)
    item_id = Column(Integer, ForeignKey("items.id"), nullable=False)
    location_id = Column(Integer, ForeignKey("locations.id"), nullable=False)
    quantity = Column(Float, default=0.0)

    item = relationship("Item", back_populates="locations")
    location = relationship("Location", back_populates="item_locations")


class SupplierLink(Base):
    __tablename__ = "supplier_links"

    id = Column(Integer, primary_key=True, index=True)
    item_id = Column(Integer, ForeignKey("items.id"), nullable=False)
    url = Column(String, nullable=False)
    supplier_name = Column(String, nullable=True)   # Amazon, AliExpress, DigiKey …
    price = Column(Float, nullable=True)
    currency = Column(String, default="USD")
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime, server_default=func.now())

    item = relationship("Item", back_populates="supplier_links")


class Transaction(Base):
    __tablename__ = "transactions"

    id = Column(Integer, primary_key=True, index=True)
    item_id = Column(Integer, ForeignKey("items.id"), nullable=False)
    transaction_type = Column(String, nullable=False)  # add | remove | adjustment | move
    quantity_change = Column(Float, nullable=False)
    quantity_before = Column(Float, nullable=False)
    quantity_after = Column(Float, nullable=False)
    from_location_id = Column(Integer, ForeignKey("locations.id"), nullable=True)
    to_location_id = Column(Integer, ForeignKey("locations.id"), nullable=True)
    notes = Column(Text, nullable=True)
    created_by = Column(String, nullable=True)  # username, 'MQTT', 'System', etc.
    created_at = Column(DateTime, server_default=func.now())

    item = relationship("Item", back_populates="transactions")
    from_location = relationship("Location", foreign_keys=[from_location_id])
    to_location = relationship("Location", foreign_keys=[to_location_id])


class PurchaseOrder(Base):
    __tablename__ = "purchase_orders"

    id = Column(Integer, primary_key=True, index=True)
    po_number = Column(String, nullable=True)        # e.g. PO-0001
    # Legacy single-item columns (kept for migration compat)
    item_id = Column(Integer, ForeignKey("items.id"), nullable=True)
    quantity_ordered = Column(Float, nullable=True)
    quantity_received = Column(Float, default=0.0)
    supplier_name = Column(String, nullable=True)
    expected_date = Column(String, nullable=True)   # ISO date string
    notes = Column(Text, nullable=True)
    status = Column(String, default="pending")       # pending | partial | received | cancelled
    created_at = Column(DateTime, server_default=func.now())

    item = relationship("Item")
    line_items = relationship("PurchaseOrderItem", back_populates="po",
                              cascade="all, delete-orphan", order_by="PurchaseOrderItem.id")


class PurchaseOrderItem(Base):
    __tablename__ = "po_items"

    id = Column(Integer, primary_key=True, index=True)
    po_id = Column(Integer, ForeignKey("purchase_orders.id", ondelete="CASCADE"), nullable=False)
    item_id = Column(Integer, ForeignKey("items.id"), nullable=False)
    quantity_ordered = Column(Float, nullable=False)
    quantity_received = Column(Float, default=0.0)
    notes = Column(Text, nullable=True)
    status = Column(String, default="pending")       # pending | partial | received | cancelled
    created_at = Column(DateTime, server_default=func.now())

    po = relationship("PurchaseOrder", back_populates="line_items")
    item = relationship("Item")


class Asset(Base):
    __tablename__ = "assets"

    id            = Column(Integer, primary_key=True, index=True)
    name          = Column(String, nullable=False, index=True)
    description   = Column(Text, nullable=True)
    asset_tag     = Column(String, nullable=True, unique=True, index=True)
    category      = Column(String, nullable=True)
    location_id   = Column(Integer, ForeignKey("locations.id"), nullable=True)
    status        = Column(String, default="available")  # available | checked_out | maintenance | retired
    serial_number = Column(String, nullable=True)
    manufacturer  = Column(String, nullable=True)
    model         = Column(String, nullable=True)
    purchase_date = Column(String, nullable=True)
    purchase_price= Column(Float, nullable=True)
    image_url     = Column(String, nullable=True)
    notes         = Column(Text, nullable=True)
    mqtt_exposed  = Column(Boolean, default=False)
    ha_exposed    = Column(Boolean, default=False)
    created_at    = Column(DateTime, server_default=func.now())

    location  = relationship("Location")
    checkouts = relationship("AssetCheckout", back_populates="asset", cascade="all, delete-orphan")


class AssetCheckout(Base):
    __tablename__ = "asset_checkouts"

    id              = Column(Integer, primary_key=True, index=True)
    asset_id        = Column(Integer, ForeignKey("assets.id"), nullable=False)
    checked_out_by  = Column(String, nullable=False)
    checked_out_at  = Column(DateTime, server_default=func.now())
    expected_return = Column(String, nullable=True)
    returned_at     = Column(DateTime, nullable=True)
    notes           = Column(Text, nullable=True)

    asset = relationship("Asset", back_populates="checkouts")


class CategoryField(Base):
    __tablename__ = "category_fields"

    id            = Column(Integer, primary_key=True, index=True)
    category_id   = Column(Integer, ForeignKey("categories.id", ondelete="CASCADE"), nullable=False)
    field_name    = Column(String, nullable=False)
    field_type    = Column(String, default="text")   # text | number | select | checkbox | date
    field_options = Column(Text, nullable=True)      # JSON array string for select type
    required      = Column(Boolean, default=False)
    sort_order    = Column(Integer, default=0)

    category = relationship("Category", backref="custom_fields")
    values   = relationship("ItemFieldValue", back_populates="field", cascade="all, delete-orphan")


class ItemFieldValue(Base):
    __tablename__ = "item_field_values"
    __table_args__ = (UniqueConstraint("item_id", "field_id"),)

    id       = Column(Integer, primary_key=True, index=True)
    item_id  = Column(Integer, ForeignKey("items.id", ondelete="CASCADE"), nullable=False)
    field_id = Column(Integer, ForeignKey("category_fields.id", ondelete="CASCADE"), nullable=False)
    value    = Column(Text, nullable=True)

    item  = relationship("Item")
    field = relationship("CategoryField", back_populates="values")


class Kit(Base):
    __tablename__ = "kits"

    id          = Column(Integer, primary_key=True, index=True)
    name        = Column(String, nullable=False)
    description = Column(Text, nullable=True)
    notes       = Column(Text, nullable=True)
    color       = Column(String, default="#6366f1")
    icon        = Column(String, default="🧰")
    created_at  = Column(DateTime, server_default=func.now())

    kit_items = relationship("KitItem", back_populates="kit", cascade="all, delete-orphan")


class KitItem(Base):
    __tablename__ = "kit_items"
    __table_args__ = (UniqueConstraint("kit_id", "item_id"),)

    id       = Column(Integer, primary_key=True, index=True)
    kit_id   = Column(Integer, ForeignKey("kits.id", ondelete="CASCADE"), nullable=False)
    item_id  = Column(Integer, ForeignKey("items.id", ondelete="CASCADE"), nullable=False)
    quantity = Column(Float, default=1.0)

    kit  = relationship("Kit", back_populates="kit_items")
    item = relationship("Item")


class AssemblyComponent(Base):
    __tablename__ = "assembly_components"
    __table_args__ = (UniqueConstraint("assembly_id", "component_id"),)

    id               = Column(Integer, primary_key=True, index=True)
    assembly_id      = Column(Integer, ForeignKey("items.id", ondelete="CASCADE"), nullable=False)
    component_id     = Column(Integer, ForeignKey("items.id", ondelete="CASCADE"), nullable=False)
    quantity_per_unit = Column(Float, default=1.0)

    assembly  = relationship("Item", foreign_keys=[assembly_id])
    component = relationship("Item", foreign_keys=[component_id])


class AppSetting(Base):
    __tablename__ = "app_settings"

    id    = Column(Integer, primary_key=True, index=True)
    key   = Column(String, unique=True, nullable=False, index=True)
    value = Column(Text, nullable=True)   # JSON string


class User(Base):
    __tablename__ = "users"

    id            = Column(Integer, primary_key=True, index=True)
    username      = Column(String, unique=True, nullable=False, index=True)
    full_name     = Column(String, nullable=True)
    email         = Column(String, unique=True, nullable=True, index=True)
    password_hash = Column(String, nullable=False)
    role          = Column(String, default="user")        # admin | user
    permissions   = Column(Text, nullable=True)           # JSON: per-section permissions
    is_active     = Column(Boolean, default=True)
    force_pw_change = Column(Boolean, default=False)
    preferences   = Column(Text, nullable=True)            # JSON: {theme, custom_theme}
    created_at    = Column(DateTime, server_default=func.now())
    last_login    = Column(DateTime, nullable=True)
