from sqlalchemy import (
    Column, Integer, String, Float, ForeignKey, Text, DateTime, Boolean, UniqueConstraint
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from .database import Base


class Material(Base):
    __tablename__ = "materials"

    id = Column(Integer, primary_key=True, autoincrement=True, index=True)
    name = Column(String, nullable=False, unique=True)
    description = Column(Text, nullable=True)
    color = Column(String, default="#6366f1")
    notes = Column(Text, nullable=True)


class Category(Base):
    __tablename__ = "categories"

    id = Column(Integer, primary_key=True, autoincrement=True, index=True)
    name = Column(String, nullable=False, unique=True)
    parent_id = Column(Integer, ForeignKey("categories.id"), nullable=True)
    color = Column(String, default="#6366f1")
    icon = Column(String, default="📦")
    default_unit_name = Column(String, nullable=True)
    default_package_behavior = Column(String, nullable=True)

    parent = relationship("Category", remote_side=[id], backref="children")
    items = relationship("Item", back_populates="category")


class Location(Base):
    __tablename__ = "locations"

    id = Column(Integer, primary_key=True, autoincrement=True, index=True)
    name = Column(String, nullable=False)
    description = Column(Text, nullable=True)
    parent_id = Column(Integer, ForeignKey("locations.id"), nullable=True)
    location_type = Column(String, default="bin")
    is_restricted = Column(Boolean, default=False)
    bin_id = Column(String, nullable=True)
    icon = Column(String, nullable=True)

    parent = relationship("Location", remote_side=[id], backref="children")
    item_locations = relationship("ItemLocation", back_populates="location")


class Item(Base):
    __tablename__ = "items"

    id = Column(Integer, primary_key=True, autoincrement=True, index=True)
    name = Column(String, nullable=False, index=True)
    description = Column(Text, nullable=True)
    barcode = Column(String, nullable=True, unique=True, index=True)
    sku = Column(String, nullable=True, index=True)
    alt_skus = Column(Text, nullable=True)  # comma-separated alternative SKUs/barcodes
    category_id = Column(Integer, ForeignKey("categories.id"), nullable=True)
    unit_type = Column(String, default="quantity")
    unit_name = Column(String, default="pcs")
    quantity = Column(Float, default=0.0)
    min_quantity = Column(Float, default=0.0)
    package_size = Column(Float, nullable=True)
    package_unit = Column(String, nullable=True)
    material = Column(String, nullable=True)
    color = Column(String, nullable=True)
    manufacturer = Column(String, nullable=True)
    price = Column(Float, nullable=True)
    date_purchased = Column(String, nullable=True)
    packages_json = Column(Text, nullable=True)
    package_behavior = Column(String, default='bulk')
    expiry_date = Column(String, nullable=True)
    image_url = Column(String, nullable=True)
    notes = Column(Text, nullable=True)
    unit_weight   = Column(Float, nullable=True)      # grams per unit (for scale weighing)
    spool_empty_weight = Column(Float, nullable=True) # grams, empty spool hub tare for scale weighing
    is_assembly   = Column(Boolean, default=False)
    mqtt_exposed  = Column(Boolean, default=False)
    ha_exposed    = Column(Boolean, default=False)
    is_hazmat     = Column(Boolean, default=False)
    sds_url       = Column(String, nullable=True)   # path/URL to uploaded SDS PDF
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    category = relationship("Category", back_populates="items")
    locations = relationship("ItemLocation", back_populates="item", cascade="all, delete-orphan")
    supplier_links = relationship("SupplierLink", back_populates="item", cascade="all, delete-orphan")
    transactions = relationship("Transaction", back_populates="item", cascade="all, delete-orphan")


class Project(Base):
    __tablename__ = "projects"

    id = Column(Integer, primary_key=True, autoincrement=True, index=True)
    name = Column(String, nullable=False)
    description = Column(Text, nullable=True)
    status = Column(String, default="planning")
    labor_hours = Column(Float, default=0.0)
    labor_rate  = Column(Float, default=0.0)
    markup_pct  = Column(Float, default=0.0)
    assigned_to = Column(String, nullable=True)
    created_at = Column(DateTime, server_default=func.now())

    items        = relationship("ProjectItem",    back_populates="project", cascade="all, delete-orphan")
    time_entries = relationship("ProjectTimeEntry", back_populates="project", cascade="all, delete-orphan", order_by="ProjectTimeEntry.created_at.desc()")
    tasks        = relationship("ProjectTask",      back_populates="project", cascade="all, delete-orphan", order_by="ProjectTask.position")
    shares       = relationship("ProjectShare",     back_populates="project", cascade="all, delete-orphan")


class ProjectItem(Base):
    __tablename__ = "project_items"
    __table_args__ = (UniqueConstraint("project_id", "item_id"),)

    id = Column(Integer, primary_key=True, autoincrement=True, index=True)
    project_id = Column(Integer, ForeignKey("projects.id"), nullable=False)
    item_id = Column(Integer, ForeignKey("items.id"), nullable=False)
    quantity_needed = Column(Float, default=1.0)
    notes = Column(Text, nullable=True)

    project = relationship("Project", back_populates="items")
    item = relationship("Item")


class ProjectShare(Base):
    __tablename__ = "project_shares"
    __table_args__ = (UniqueConstraint("project_id", "username"),)

    id         = Column(Integer, primary_key=True, autoincrement=True, index=True)
    project_id = Column(Integer, ForeignKey("projects.id"), nullable=False)
    username   = Column(String, nullable=False)
    created_at = Column(DateTime, server_default=func.now())

    project = relationship("Project", back_populates="shares")


class ItemLocation(Base):
    __tablename__ = "item_locations"
    __table_args__ = (UniqueConstraint("item_id", "location_id"),)

    id = Column(Integer, primary_key=True, autoincrement=True, index=True)
    item_id = Column(Integer, ForeignKey("items.id"), nullable=False)
    location_id = Column(Integer, ForeignKey("locations.id"), nullable=False)
    quantity = Column(Float, default=0.0)

    item = relationship("Item", back_populates="locations")
    location = relationship("Location", back_populates="item_locations")


class SupplierLink(Base):
    __tablename__ = "supplier_links"

    id = Column(Integer, primary_key=True, autoincrement=True, index=True)
    item_id = Column(Integer, ForeignKey("items.id"), nullable=False)
    url = Column(String, nullable=False)
    supplier_name = Column(String, nullable=True)
    price = Column(Float, nullable=True)
    currency = Column(String, default="USD")
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime, server_default=func.now())

    item = relationship("Item", back_populates="supplier_links")


class Transaction(Base):
    __tablename__ = "transactions"

    id = Column(Integer, primary_key=True, autoincrement=True, index=True)
    item_id = Column(Integer, ForeignKey("items.id"), nullable=False)
    transaction_type = Column(String, nullable=False)
    quantity_change = Column(Float, nullable=False)
    quantity_before = Column(Float, nullable=False)
    quantity_after = Column(Float, nullable=False)
    from_location_id = Column(Integer, ForeignKey("locations.id"), nullable=True)
    to_location_id = Column(Integer, ForeignKey("locations.id"), nullable=True)
    notes = Column(Text, nullable=True)
    created_by = Column(String, nullable=True)
    created_at = Column(DateTime, server_default=func.now())

    item = relationship("Item", back_populates="transactions")
    from_location = relationship("Location", foreign_keys=[from_location_id])
    to_location = relationship("Location", foreign_keys=[to_location_id])


class PurchaseOrder(Base):
    __tablename__ = "purchase_orders"

    id = Column(Integer, primary_key=True, autoincrement=True, index=True)
    po_number = Column(String, nullable=True)
    item_id = Column(Integer, ForeignKey("items.id"), nullable=True)
    quantity_ordered = Column(Float, nullable=True)
    quantity_received = Column(Float, default=0.0)
    supplier_id = Column(Integer, ForeignKey("suppliers.id"), nullable=True)
    supplier_name = Column(String, nullable=True)
    expected_date = Column(String, nullable=True)
    notes = Column(Text, nullable=True)
    status = Column(String, default="pending")
    created_at = Column(DateTime, server_default=func.now())

    item = relationship("Item")
    supplier = relationship("Supplier", back_populates="purchase_orders")
    line_items = relationship("PurchaseOrderItem", back_populates="po",
                              cascade="all, delete-orphan", order_by="PurchaseOrderItem.id")


class PurchaseOrderItem(Base):
    __tablename__ = "po_items"

    id = Column(Integer, primary_key=True, autoincrement=True, index=True)
    po_id = Column(Integer, ForeignKey("purchase_orders.id", ondelete="CASCADE"), nullable=False)
    item_id = Column(Integer, ForeignKey("items.id"), nullable=False)
    quantity_ordered = Column(Float, nullable=False)
    quantity_received = Column(Float, default=0.0)
    unit_price = Column(Float, nullable=True)
    notes = Column(Text, nullable=True)
    status = Column(String, default="pending")
    created_at = Column(DateTime, server_default=func.now())

    po = relationship("PurchaseOrder", back_populates="line_items")
    item = relationship("Item")


class Asset(Base):
    __tablename__ = "assets"

    id            = Column(Integer, primary_key=True, autoincrement=True, index=True)
    name          = Column(String, nullable=False, index=True)
    description   = Column(Text, nullable=True)
    asset_tag     = Column(String, nullable=True, unique=True, index=True)
    category      = Column(String, nullable=True)
    location_id   = Column(Integer, ForeignKey("locations.id"), nullable=True)
    status        = Column(String, default="available")
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
    maintenance_schedules = relationship("AssetMaintenanceSchedule", back_populates="asset", cascade="all, delete-orphan")
    bookings       = relationship("AssetBooking",       back_populates="asset", cascade="all, delete-orphan")
    certifications = relationship("AssetCertification", back_populates="asset", cascade="all, delete-orphan")
    incidents      = relationship("AssetIncident",      back_populates="asset", cascade="all, delete-orphan")


class AssetCheckout(Base):
    __tablename__ = "asset_checkouts"

    id              = Column(Integer, primary_key=True, autoincrement=True, index=True)
    asset_id        = Column(Integer, ForeignKey("assets.id"), nullable=False)
    checked_out_by  = Column(String, nullable=False)
    checked_out_at  = Column(DateTime, server_default=func.now())
    expected_return = Column(String, nullable=True)
    returned_at     = Column(DateTime, nullable=True)
    notes           = Column(Text, nullable=True)

    asset = relationship("Asset", back_populates="checkouts")


class CategoryField(Base):
    __tablename__ = "category_fields"

    id            = Column(Integer, primary_key=True, autoincrement=True, index=True)
    category_id   = Column(Integer, ForeignKey("categories.id", ondelete="CASCADE"), nullable=False)
    field_name    = Column(String, nullable=False)
    field_type    = Column(String, default="text")
    field_options = Column(Text, nullable=True)
    required      = Column(Boolean, default=False)
    sort_order    = Column(Integer, default=0)
    show_in_list  = Column(Boolean, default=False)

    category = relationship("Category", backref="custom_fields")
    values   = relationship("ItemFieldValue", back_populates="field", cascade="all, delete-orphan")


class ItemFieldValue(Base):
    __tablename__ = "item_field_values"
    __table_args__ = (UniqueConstraint("item_id", "field_id"),)

    id       = Column(Integer, primary_key=True, autoincrement=True, index=True)
    item_id  = Column(Integer, ForeignKey("items.id", ondelete="CASCADE"), nullable=False)
    field_id = Column(Integer, ForeignKey("category_fields.id", ondelete="CASCADE"), nullable=False)
    value    = Column(Text, nullable=True)

    item  = relationship("Item")
    field = relationship("CategoryField", back_populates="values")


class Kit(Base):
    __tablename__ = "kits"

    id          = Column(Integer, primary_key=True, autoincrement=True, index=True)
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

    id       = Column(Integer, primary_key=True, autoincrement=True, index=True)
    kit_id   = Column(Integer, ForeignKey("kits.id", ondelete="CASCADE"), nullable=False)
    item_id  = Column(Integer, ForeignKey("items.id", ondelete="CASCADE"), nullable=False)
    quantity = Column(Float, default=1.0)

    kit  = relationship("Kit", back_populates="kit_items")
    item = relationship("Item")


class AssemblyComponent(Base):
    __tablename__ = "assembly_components"
    __table_args__ = (UniqueConstraint("assembly_id", "component_id"),)

    id                = Column(Integer, primary_key=True, autoincrement=True, index=True)
    assembly_id       = Column(Integer, ForeignKey("items.id", ondelete="CASCADE"), nullable=False)
    component_id      = Column(Integer, ForeignKey("items.id", ondelete="CASCADE"), nullable=False)
    quantity_per_unit = Column(Float, default=1.0)

    assembly  = relationship("Item", foreign_keys=[assembly_id])
    component = relationship("Item", foreign_keys=[component_id])


class AssetMaintenanceSchedule(Base):
    __tablename__ = "asset_maintenance_schedules"

    id            = Column(Integer, primary_key=True, autoincrement=True, index=True)
    asset_id      = Column(Integer, ForeignKey("assets.id", ondelete="CASCADE"), nullable=False)
    task_name     = Column(String, nullable=False)
    interval_days = Column(Integer, nullable=True)   # None = one-time task
    next_due      = Column(String, nullable=True)    # YYYY-MM-DD
    assigned_to   = Column(String, nullable=True)
    notes         = Column(Text, nullable=True)
    created_at    = Column(DateTime, server_default=func.now())

    asset = relationship("Asset", back_populates="maintenance_schedules")
    logs  = relationship("AssetMaintenanceLog", back_populates="schedule",
                         cascade="all, delete-orphan")


class AssetMaintenanceLog(Base):
    __tablename__ = "asset_maintenance_logs"

    id          = Column(Integer, primary_key=True, autoincrement=True, index=True)
    asset_id    = Column(Integer, ForeignKey("assets.id", ondelete="CASCADE"), nullable=False)
    schedule_id = Column(Integer, ForeignKey("asset_maintenance_schedules.id", ondelete="SET NULL"), nullable=True)
    task_name   = Column(String, nullable=False)
    done_at     = Column(String, nullable=False)
    done_by     = Column(String, nullable=True)
    notes       = Column(Text, nullable=True)
    created_at  = Column(DateTime, server_default=func.now())

    asset    = relationship("Asset")
    schedule = relationship("AssetMaintenanceSchedule", back_populates="logs")


class Supplier(Base):
    __tablename__ = "suppliers"

    id             = Column(Integer, primary_key=True, autoincrement=True, index=True)
    name           = Column(String, nullable=False)
    contact_name   = Column(String, nullable=True)
    email          = Column(String, nullable=True)
    phone          = Column(String, nullable=True)
    address        = Column(String, nullable=True)
    city           = Column(String, nullable=True)
    state          = Column(String, nullable=True)
    zip            = Column(String, nullable=True)
    country        = Column(String, nullable=True)
    website        = Column(String, nullable=True)
    account_number = Column(String, nullable=True)
    notes          = Column(Text, nullable=True)
    created_at     = Column(DateTime, server_default=func.now())

    purchase_orders = relationship("PurchaseOrder", back_populates="supplier")


class AppSetting(Base):
    __tablename__ = "app_settings"

    id    = Column(Integer, primary_key=True, autoincrement=True, index=True)
    key   = Column(String, unique=True, nullable=False, index=True)
    value = Column(Text, nullable=True)


class User(Base):
    __tablename__ = "users"

    id              = Column(Integer, primary_key=True, autoincrement=True, index=True)
    username        = Column(String, unique=True, nullable=False, index=True)
    full_name       = Column(String, nullable=True)
    email           = Column(String, unique=True, nullable=True, index=True)
    password_hash   = Column(String, nullable=False)
    role            = Column(String, default="user")
    permissions     = Column(Text, nullable=True)
    is_active       = Column(Boolean, default=True)
    force_pw_change = Column(Boolean, default=False)
    preferences     = Column(Text, nullable=True)
    token_version   = Column(Integer, default=0, nullable=False)
    member_id       = Column(String, unique=True, nullable=True, index=True)
    created_at      = Column(DateTime, server_default=func.now())
    last_login      = Column(DateTime, nullable=True)


class TokenBlocklist(Base):
    """Revoked refresh token JTIs — checked on /api/auth/refresh."""
    __tablename__ = "token_blocklist"

    jti        = Column(String, primary_key=True)
    expires_at = Column(DateTime, nullable=False)


class PullTicket(Base):
    """A pick/pull ticket — requests to remove or move items from inventory."""
    __tablename__ = "pull_tickets"

    id            = Column(Integer, primary_key=True, autoincrement=True, index=True)
    ticket_number = Column(String, nullable=True, index=True)
    # open | partial | completed | putback
    status        = Column(String, default="open", nullable=False)
    # out_of_inventory | move_location | assign_project
    pull_type     = Column(String, default="out_of_inventory", nullable=False)
    to_location_id = Column(Integer, ForeignKey("locations.id", ondelete="SET NULL"), nullable=True)
    project_id    = Column(Integer, ForeignKey("projects.id", ondelete="SET NULL"), nullable=True)
    notes         = Column(Text, nullable=True)
    created_by    = Column(String, nullable=True)
    created_at    = Column(DateTime, server_default=func.now())
    completed_at  = Column(DateTime, nullable=True)

    lines       = relationship("PullTicketLine", back_populates="ticket", cascade="all, delete-orphan")
    to_location = relationship("Location", foreign_keys=[to_location_id])
    project     = relationship("Project", foreign_keys=[project_id])


class PullTicketLine(Base):
    """Individual line item on a pull ticket."""
    __tablename__ = "pull_ticket_lines"

    id               = Column(Integer, primary_key=True, autoincrement=True, index=True)
    ticket_id        = Column(Integer, ForeignKey("pull_tickets.id", ondelete="CASCADE"), nullable=False)
    item_id          = Column(Integer, ForeignKey("items.id", ondelete="CASCADE"), nullable=False)
    quantity_needed  = Column(Float, nullable=False, default=1.0)
    quantity_pulled  = Column(Float, default=0.0)
    from_location_id = Column(Integer, ForeignKey("locations.id", ondelete="SET NULL"), nullable=True)
    # open | partial | pulled | putback
    status           = Column(String, default="open", nullable=False)
    notes            = Column(Text, nullable=True)

    ticket        = relationship("PullTicket", back_populates="lines")
    item          = relationship("Item")
    from_location = relationship("Location", foreign_keys=[from_location_id])


class ProjectTimeEntry(Base):
    """Clock-in / clock-out or manually-added hours on a project."""
    __tablename__ = "project_time_entries"

    id          = Column(Integer, primary_key=True, autoincrement=True, index=True)
    project_id  = Column(Integer, ForeignKey("projects.id", ondelete="CASCADE"), nullable=False)
    user        = Column(String, nullable=True)           # username who logged it
    clock_in    = Column(DateTime, nullable=True)         # None for manual entries
    clock_out   = Column(DateTime, nullable=True)         # None while active / manual
    hours       = Column(Float, nullable=True)            # computed or manually set
    description = Column(Text, nullable=True)             # what was worked on
    created_at  = Column(DateTime, server_default=func.now())

    project = relationship("Project", back_populates="time_entries")


# ── Services ──────────────────────────────────────────────────────────────────

class Service(Base):
    """Billable services — fees, touch labor, etc."""
    __tablename__ = "services"

    id               = Column(Integer, primary_key=True, autoincrement=True, index=True)
    name             = Column(String, nullable=False)
    category         = Column(String, default="other")   # fee | labor | materials | other
    description      = Column(Text, nullable=True)
    unit_price       = Column(Float, default=0.0)
    default_markup_pct = Column(Float, default=0.0)
    use_markup       = Column(Boolean, default=False)    # True = apply markup, False = straight cost
    is_active        = Column(Boolean, default=True)
    created_at       = Column(DateTime, server_default=func.now())


# ── Invoices ──────────────────────────────────────────────────────────────────

class Invoice(Base):
    __tablename__ = "invoices"

    id             = Column(Integer, primary_key=True, autoincrement=True, index=True)
    project_id     = Column(Integer, ForeignKey("projects.id", ondelete="SET NULL"), nullable=True)
    invoice_type   = Column(String, default="invoice")   # quote | invoice
    status         = Column(String, default="draft")     # draft | sent | accepted | paid | void
    invoice_number = Column(String, nullable=True)
    client_name    = Column(String, nullable=True)
    client_address = Column(Text, nullable=True)
    invoice_date   = Column(String, nullable=True)
    due_date       = Column(String, nullable=True)
    notes          = Column(Text, nullable=True)
    terms          = Column(Text, nullable=True)
    tax_pct        = Column(Float, default=0.0)
    created_at     = Column(DateTime, server_default=func.now())
    sent_at        = Column(DateTime, nullable=True)
    paid_at        = Column(DateTime, nullable=True)

    project = relationship("Project")
    lines   = relationship("InvoiceLine", back_populates="invoice",
                           cascade="all, delete-orphan",
                           order_by="InvoiceLine.sort_order")


class InvoiceLine(Base):
    __tablename__ = "invoice_lines"

    id          = Column(Integer, primary_key=True, autoincrement=True, index=True)
    invoice_id  = Column(Integer, ForeignKey("invoices.id", ondelete="CASCADE"), nullable=False)
    line_type   = Column(String, default="part")   # part | labor | service
    description = Column(String, nullable=False, default="")
    quantity    = Column(Float, default=1.0)
    unit_price  = Column(Float, default=0.0)
    markup_pct  = Column(Float, default=0.0)       # only applied when use_markup=True
    use_markup  = Column(Boolean, default=False)   # False for labor lines
    item_id     = Column(Integer, ForeignKey("items.id", ondelete="SET NULL"), nullable=True)
    service_id  = Column(Integer, ForeignKey("services.id", ondelete="SET NULL"), nullable=True)
    sort_order  = Column(Integer, default=0)

    invoice = relationship("Invoice", back_populates="lines")


# ── Location map image ─────────────────────────────────────────────────────────
# Added as a separate table so large base64 blobs don't bloat every location query

class LocationMapImage(Base):
    """Stores an optional background image for a shelf-map location."""
    __tablename__ = "location_map_images"

    location_id = Column(Integer, ForeignKey("locations.id", ondelete="CASCADE"), primary_key=True)
    image_data  = Column(Text, nullable=True)   # base64 data-URI
    updated_at  = Column(DateTime, server_default=func.now(), onupdate=func.now())


# ── Purchase Requests ─────────────────────────────────────────────────────────

class PurchaseRequest(Base):
    __tablename__ = "purchase_requests"

    id              = Column(Integer, primary_key=True, autoincrement=True, index=True)
    request_number  = Column(String, nullable=True, index=True)
    # draft | pending_approval | approved | ordered | received | rejected | cancelled
    status          = Column(String, default="draft")
    supplier_id     = Column(Integer, ForeignKey("suppliers.id", ondelete="SET NULL"), nullable=True)
    supplier_name   = Column(String, nullable=True)
    requested_by    = Column(String, nullable=True)
    approved_by     = Column(String, nullable=True)
    purchased_by    = Column(String, nullable=True)
    approved_at     = Column(DateTime, nullable=True)
    purchased_at    = Column(DateTime, nullable=True)
    notes           = Column(Text, nullable=True)
    urgency         = Column(String, default="normal")   # low | normal | high | critical
    created_at      = Column(DateTime, server_default=func.now())
    updated_at      = Column(DateTime, server_default=func.now(), onupdate=func.now())

    supplier = relationship("Supplier")
    lines    = relationship("PurchaseRequestLine", back_populates="request",
                            cascade="all, delete-orphan", order_by="PurchaseRequestLine.id")


class PurchaseRequestLine(Base):
    __tablename__ = "purchase_request_lines"

    id           = Column(Integer, primary_key=True, autoincrement=True, index=True)
    request_id   = Column(Integer, ForeignKey("purchase_requests.id", ondelete="CASCADE"), nullable=False)
    item_id      = Column(Integer, ForeignKey("items.id", ondelete="SET NULL"), nullable=True)
    description  = Column(String, nullable=False, default="")
    quantity     = Column(Float, default=1.0)
    unit_price   = Column(Float, nullable=True)
    notes        = Column(Text, nullable=True)
    # open | ordered | received | cancelled
    line_status  = Column(String, default="open")

    request = relationship("PurchaseRequest", back_populates="lines")
    item    = relationship("Item")


# ── Notifications / Alerts ────────────────────────────────────────────────────

class Notification(Base):
    __tablename__ = "notifications"

    id          = Column(Integer, primary_key=True, autoincrement=True, index=True)
    user_id     = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=True)   # None = broadcast to role
    target_role = Column(String, nullable=True)   # e.g. "approver" — send to everyone with this role flag
    title       = Column(String, nullable=False)
    body        = Column(Text, nullable=True)
    # info | warning | success | error
    level       = Column(String, default="info")
    # purchase_request | pull_ticket | system | general
    source_type = Column(String, nullable=True)
    source_id   = Column(Integer, nullable=True)
    is_read     = Column(Boolean, default=False)
    created_at  = Column(DateTime, server_default=func.now())


# ── User Permission Profiles ──────────────────────────────────────────────────

class UserPermissionProfile(Base):
    """Named permission preset — apply to a user to bulk-set their permissions."""
    __tablename__ = "user_permission_profiles"

    id          = Column(Integer, primary_key=True, autoincrement=True, index=True)
    name        = Column(String, nullable=False, unique=True)
    description = Column(Text, nullable=True)
    role        = Column(String, default="user")   # user | manager
    permissions = Column(Text, nullable=True)      # JSON — same shape as User.permissions
    created_at  = Column(DateTime, server_default=func.now())


# ── Location Map Images ───────────────────────────────────────────────────────


class LotoRecord(Base):
    __tablename__ = "loto_records"

    id              = Column(Integer, primary_key=True, autoincrement=True, index=True)
    title           = Column(String, nullable=False)
    asset_id        = Column(Integer, ForeignKey("assets.id", ondelete="SET NULL"), nullable=True)
    machine_name    = Column(String, nullable=True)
    machine_id      = Column(String, nullable=True)
    location        = Column(String, nullable=True)
    department      = Column(String, nullable=True)
    status          = Column(String, default="draft")
    procedure_steps = Column(Text, nullable=True)   # JSON list
    energy_sources  = Column(Text, nullable=True)   # JSON list
    ppe_required    = Column(Text, nullable=True)   # JSON list
    authorized_by   = Column(String, nullable=True)
    reviewed_by     = Column(String, nullable=True)
    review_date     = Column(String, nullable=True)
    notes           = Column(Text, nullable=True)
    created_by      = Column(String, nullable=True)
    created_at      = Column(DateTime, server_default=func.now())
    updated_at      = Column(DateTime, server_default=func.now(), onupdate=func.now())

    asset    = relationship("Asset", foreign_keys=[asset_id])
    lockouts = relationship("LotoLockout", back_populates="record", cascade="all, delete-orphan")


class LotoLockout(Base):
    __tablename__ = "loto_lockouts"

    id          = Column(Integer, primary_key=True, autoincrement=True, index=True)
    record_id   = Column(Integer, ForeignKey("loto_records.id", ondelete="CASCADE"), nullable=False)
    locked_by   = Column(String, nullable=False)
    locked_at   = Column(DateTime, server_default=func.now())
    released_at = Column(DateTime, nullable=True)
    notes       = Column(Text, nullable=True)

    record = relationship("LotoRecord", back_populates="lockouts")


# ── Purchase Requests ─────────────────────────────────────────────────────────

class Team(Base):
    __tablename__ = "teams"

    id          = Column(Integer, primary_key=True, autoincrement=True, index=True)
    name        = Column(String, nullable=False, unique=True)
    description = Column(Text, nullable=True)
    color       = Column(String, default="#6366f1")
    created_at  = Column(DateTime, server_default=func.now())

    members = relationship("TeamMember", back_populates="team", cascade="all, delete-orphan")


class TeamMember(Base):
    __tablename__ = "team_members"

    id      = Column(Integer, primary_key=True, autoincrement=True, index=True)
    team_id = Column(Integer, ForeignKey("teams.id", ondelete="CASCADE"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    role    = Column(String, default="member")

    team = relationship("Team", back_populates="members")
    user = relationship("User")


# ── Project Tasks (Kanban) ───────────────────��──────────────────────────────��─

class ProjectTask(Base):
    __tablename__ = "project_tasks"

    id          = Column(Integer, primary_key=True, autoincrement=True, index=True)
    project_id  = Column(Integer, ForeignKey("projects.id", ondelete="CASCADE"), nullable=False)
    title       = Column(String, nullable=False)
    description = Column(Text, nullable=True)
    status      = Column(String, default="todo")
    priority    = Column(String, default="normal")
    assignee    = Column(String, nullable=True)
    team_id     = Column(Integer, ForeignKey("teams.id", ondelete="SET NULL"), nullable=True)
    due_date    = Column(String, nullable=True)
    color       = Column(String, nullable=True)
    position    = Column(Integer, default=0)
    created_by  = Column(String, nullable=True)
    checklist   = Column(Text, nullable=True)   # JSON: [{text, done}, ...]
    created_at  = Column(DateTime, server_default=func.now())
    updated_at  = Column(DateTime, server_default=func.now(), onupdate=func.now())

    project = relationship("Project", back_populates="tasks")
    team    = relationship("Team")


# ── Asset Extras ────────────────────────────────────────────────────────────────

class AssetBooking(Base):
    """Time-slot reservation for a machine/asset."""
    __tablename__ = "asset_bookings"

    id       = Column(Integer, primary_key=True, autoincrement=True, index=True)
    asset_id = Column(Integer, ForeignKey("assets.id", ondelete="CASCADE"), nullable=False)
    username = Column(String, nullable=False)
    title    = Column(String, nullable=True)    # purpose / project label
    start_dt = Column(String, nullable=False)   # ISO 8601 datetime
    end_dt   = Column(String, nullable=False)   # ISO 8601 datetime
    notes    = Column(Text, nullable=True)
    status   = Column(String, default="upcoming")  # upcoming / active / complete / cancelled
    created_at = Column(DateTime, server_default=func.now())

    asset = relationship("Asset", back_populates="bookings")


class AssetCertification(Base):
    """Records that a user is trained/certified on a specific asset."""
    __tablename__ = "asset_certifications"
    __table_args__ = (UniqueConstraint("asset_id", "username"),)

    id           = Column(Integer, primary_key=True, autoincrement=True, index=True)
    asset_id     = Column(Integer, ForeignKey("assets.id", ondelete="CASCADE"), nullable=False)
    username     = Column(String, nullable=False)
    certified_by = Column(String, nullable=True)
    certified_at = Column(String, nullable=True)   # date string YYYY-MM-DD
    expires_at   = Column(String, nullable=True)   # optional expiry
    notes        = Column(Text, nullable=True)

    asset = relationship("Asset", back_populates="certifications")


class AssetIncident(Base):
    """Incident / breakage log entry tied to an asset."""
    __tablename__ = "asset_incidents"

    id               = Column(Integer, primary_key=True, autoincrement=True, index=True)
    asset_id         = Column(Integer, ForeignKey("assets.id", ondelete="CASCADE"), nullable=False)
    reported_by      = Column(String, nullable=False)
    incident_type    = Column(String, default="other")   # breakage / malfunction / near_miss / injury / other
    severity         = Column(String, default="low")     # low / medium / high / critical
    description      = Column(Text, nullable=False)
    out_of_service   = Column(Boolean, default=False)
    resolved         = Column(Boolean, default=False)
    resolved_at      = Column(String, nullable=True)
    resolved_by      = Column(String, nullable=True)
    resolution_notes = Column(Text, nullable=True)
    created_at       = Column(DateTime, server_default=func.now())

    asset = relationship("Asset", back_populates="incidents")


class MemberCheckIn(Base):
    """Space check-in / check-out session for a member."""
    __tablename__ = "member_checkins"

    id               = Column(Integer, primary_key=True, autoincrement=True, index=True)
    username         = Column(String, nullable=False, index=True)
    member_id        = Column(String, nullable=True)
    checked_in_at    = Column(DateTime, nullable=False, server_default=func.now())
    checked_out_at   = Column(DateTime, nullable=True)
    duration_minutes = Column(Float, nullable=True)
    notes            = Column(Text, nullable=True)
