# Changelog

## ALPHA v1.6.55 — 2026-06-12

### Security
- **IDOR fix — project tasks**: any authenticated user could read/edit/delete tasks on projects they didn't own. Added `_check_project_access()` helper in `project_tasks_router.py` that verifies the requesting user is the project assignee or has an explicit `ProjectShare` entry before allowing list/create/update/delete/reorder operations.
- **IDOR fix — asset bookings**: `PATCH /{asset_id}/bookings/{bid}` was missing the `_cu` parameter entirely — no ownership check. Added `_cu=Depends(get_current_user)`, raises 403 if not admin and `b.username != _cu.username`.
- **IDOR fix — asset incidents**: `PATCH /{asset_id}/incidents/{iid}` had the same issue. Added `_cu=Depends(get_current_user)`, raises 403 if not admin and `i.reported_by != _cu.username`.
- **IDOR fix — LOTO records**: `PUT /loto/{rid}` and `DELETE /loto/{rid}` had no ownership check — any authenticated user could modify any LOTO record. Added `current_user` dependency; raises 403 unless `record.created_by == current_user.username` or user is admin.

### Check-In
- **All users see who's checked in**: the "Currently In" list now shows all members for all users, not just the current user's own session.
- **Login check-in prompt**: after login, the app checks `/api/checkin/me`; if the user is not currently checked in, a dialog asks if they'd like to check in now.
- **Logout check-in prompt**: before logging out, if the user is checked in a dialog asks if they'd like to check out first. Logout proceeds regardless of choice.
- **New API endpoint** `GET /api/checkin/me`: returns the current user's check-in status (`checked_in`, `session_id`, `checked_in_at`, `member_id`) without requiring admin.
- **Self checkout relaxed**: `PATCH /api/checkin/{sid}/checkout` now allows users to check out their own session (previously admin-only).
- **Member ID removed from Currently In cards**: the "Currently In" cards no longer display the member ID field to reduce clutter.

### Asset Checkout
- **Certification check on checkout**: when the certifications feature is enabled, checking out an asset now verifies the user is certified before showing the checkout form. Shows an error prompt if not certified.
- **Duration picker**: when the bookings feature is enabled, the checkout modal shows duration options (1h, 2h, 4h, 8h, Custom) and calculates an expected return time automatically.
- **Booking conflict validation**: the checkout form checks for upcoming confirmed bookings that would overlap with the selected duration. A warning is shown and checkout is blocked if a conflict exists.
- **Graceful feature fallback**: if bookings are off, checkout works as before (simple return-date input); if certifications are also off, no pre-check occurs.

### Mobile
- **Updated "More" menu**: the mobile More page now reflects all features added since v1.5.x, organized into labeled sections (Management, Staff Tools, Admin Tools) with feature-flag guards so items only appear when the relevant feature is enabled.

### UI
- **Sticky sidebar footer**: the username/logout bar at the bottom of the left sidebar is now sticky — it stays visible while the nav list scrolls.

---

## ALPHA v1.6.3 — 2026-06-07

### Check-In
- **Max capacity setting restricted to admins**: the capacity configuration option in Check In settings is now hidden from non-admin users.

### Theme
- **Field/Input Background color control**: Settings → Theme now includes a "Field / Input Background" color picker that sets `--bg-input`. Included in dark/light presets and the theme reset list.

### Assets — Certifications
- **Certification enforcement on bookings**: non-admin users attempting to book an asset they are not certified for receive a 403 from the API. The frontend pre-checks certification status before showing the booking form and blocks the UI if not certified.
- **Certification Manager page**: admins see all certifications across all users; regular users see only their own. Accessible via the sidebar when the `asset_certifications` feature is enabled.

---

## ALPHA v1.6.0 — 2026-06-07

### Users & Roles
- **Staff role**: new role between `user` and `admin`. Staff are created with elevated defaults (purchase approver, restricted-location read access) but permissions are fully customizable just like regular users.

### Member Check-In
- **Member Check-In feature** (feature flag: `member_checkin`): track who is currently in the space. Members scan or enter their member ID to check in and out. The Check In nav item is hidden when the feature is disabled.

### Searchable User Picker
- **Searchable dropdowns on all assignee/user fields**: project assignee, task assignee, cert manager user picker, and maintenance assignment fields all use a searchable combobox instead of a plain `<select>`.

---

## ALPHA v1.5.x — 2026-06-06

### Projects
- **Kanban project board**: the Projects page is now a 5-column kanban board (Planning, Active, On Hold, Complete, Archived). Projects are draggable between columns.
- **Full-page project detail**: clicking a project opens a full-page view via `pushState` routing instead of a modal. The browser Back button returns to the project board.
- **Per-project task board**: each project detail page includes a 4-column task kanban (To Do, In Progress, Review, Done) with draggable task cards.
- **Task management**: create, edit, delete, and reorder tasks. Tasks have title, description, status, priority (low/normal/high/urgent), assignee, team, due date, and color.

### Teams
- **Teams / Groups**: create named teams with a color. Assign members with a role. Used for task assignment and notifications.

### Notifications
- **User notification system**: per-user notifications with severity levels. Notifications are triggered by purchase request workflows, task assignments, and LOTO events. A bell icon in the header shows unread count.

### Purchase Requests
- **Purchase request feature** (feature flag): users submit requests for items; staff/admin can approve or deny. Approved requests can be converted to purchase orders. Approved POs that are marked as purchased generate an invoice automatically.

### Permissions
- **User permission profile templates**: define reusable permission sets and apply them to new users instead of configuring each permission individually.

### Fix
- **Check In nav item not hidden**: fixed a bug where the `nav-check-in` sidebar item was visible even when the `member_checkin` feature was disabled.

---

## ALPHA v1.4.13 — 2026-06-06

### Scale / Weighing
- **Spool scale weighing** — open spool rows in item detail now show a ⚖️ button (when scale is enabled). Places the spool on the scale, subtracts the empty spool hub weight, and updates the spool's remaining quantity directly. Empty spool weight is saved per item so you only enter it once.
- **Scale in Add/Edit Item form** — a ⚖️ button appears next to the Quantity and Loose fields in the item form. Expands an inline panel (no modal takeover) showing live scale reading, tare, and calculated quantity. For spool items shows empty spool weight subtraction; for bulk items shows weight-per-unit division.
- **Set unit weight from scale** — in the form scale panel, a 📏 Set from scale button reads the current net weight as the unit weight and syncs it back to the item's Weight/unit field on apply.

### Branding
- **Settings → 🖼️ Branding tab** — set a custom logo image URL or upload an image file. Logo replaces the default "⚙️ Makerspace ERP" text in the sidebar. Set a custom favicon URL or upload a .ico/.png/.svg. Both apply live and persist across sessions via the server-side settings store.

### Item Merge
- **Merge items** — item detail view has a new ⇄ Merge button. Opens a modal to search for another item, shows a preview with ✓ KEEP / 🗑 DELETE labels, and a ⇄ Swap button to flip which item is kept. Merging sums quantities, combines spool package arrays, merges location quantities (adding where locations overlap, adopting new ones), and re-parents all transactions, supplier links, PO lines, project items, kit items, assembly components, and custom field values. The absorbed item is permanently deleted and a merge transaction is logged.
- **Location merge control** — an expandable 📍 Location merging section in the merge preview lets you choose which location on the primary each source location's quantity merges into, rather than always defaulting to the same-named location.
- **Bulk merge** — selecting 2 or more items in the Items list shows a ⇄ Merge button in the bulk action bar. Opens a modal listing all selected items; click one to designate it as the primary (green = keep, red = delete). Merges all others into it sequentially. Includes the same location merge control section.

### Kit CSV Import
- **Import components from CSV** — the Kit Components modal has a new ⬆ CSV button. Accepts a CSV with `name`, `quantity`, and optional `sku`, `barcode`, `unit` columns. Each row is fuzzy-matched against existing inventory: exact matches are auto-confirmed, partial matches show a dropdown pre-populated with candidates, and unmatched rows default to creating a new item.
- **Search or add new** — every row in the import review has a 🔍 Search button that expands a live search box filtering all inventory items, and a ＋ New item button to explicitly create a new inventory item with zero stock.
- **Example CSV download** — a ⬇ Example button next to the CSV upload button downloads a sample CSV to show the expected format.

### Scan Barcode
- **Photo fallback** — a 📁 Scan from Photo button now appears on the Scan Barcode page. Works over plain HTTP (no HTTPS required), opens the device camera on mobile or a file picker on desktop, and decodes the barcode from the image using the same Html5Qrcode library. Includes a note explaining why live camera streaming requires HTTPS.
- **Improved error messages** — camera errors now show the actual error text instead of "undefined".

### Locations
- **Custom location types** — the Type field in Add/Edit Location is now a select dropdown showing all built-in and custom types. A ＋ button expands an inline input to add a new custom type, which is saved to localStorage and immediately available. Custom types are listed below with ✕ buttons to delete them.

### UI Polish
- **Page descriptions** — fixed Settings, Projects, Locations, Materials, and Categories pages where the subtitle text was floating to the right as a flex sibling of the title. All page descriptions now sit flush left directly below the page title.

---

## ALPHA v1.3.96 and earlier

Initial release. Core inventory management, locations, categories, transactions, purchase orders, assets, projects, kits, assemblies, MQTT/Home Assistant integration, scale weighing for bulk items, barcode scanning, shelf map, reports, multi-user auth.
