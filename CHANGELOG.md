# Changelog

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
