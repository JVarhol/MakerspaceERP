# Makerspace ERP — User Guide

> **Version:** ALPHA v1.6.4  
> **Status:** Pre-release draft — for internal use only. Remove before public release.

---

## ✏️ How to Edit This Guide

This guide is written in **GitHub Flavored Markdown (GFM)**. It renders automatically on GitHub and can be edited in any text editor, VS Code, or directly in GitHub's web editor (click the pencil ✏️ icon on the file page).

### Adding Screenshots

Create an `images/` folder in this repository and drop screenshots there. Replace placeholder comments like this:

```
<!-- TODO: screenshot -->
```

…with actual image references like this:

```markdown
![Dashboard overview](images/dashboard-overview.png)
```

### Collapsible Sections

GitHub supports `<details>` blocks for collapsible content — useful for step-by-step walkthroughs you don't want cluttering the main flow:

```markdown
<details>
<summary>Click to expand</summary>

Content goes here.

</details>
```

### Tips for Reformatting

- Use `##` for major sections, `###` for subsections, `####` for fine detail
- Use `> **Note:**` for callout boxes
- Use ` ```bash ` fenced blocks for commands
- Tables: use `| Col | Col |` syntax — GitHub renders them automatically

---

## 📋 Table of Contents

- [Getting Started](#getting-started)
  - [Logging In](#logging-in)
  - [First Login & Password Change](#first-login--password-change)
  - [Navigating the App](#navigating-the-app)
- [Dashboard](#dashboard)
- [Inventory](#inventory)
  - [Items](#items)
  - [Categories & Custom Fields](#categories--custom-fields)
  - [Locations & Shelf Map](#locations--shelf-map)
  - [Transactions](#transactions)
  - [Kits & Assemblies](#kits--assemblies)
- [Assets](#assets)
  - [Asset List](#asset-list)
  - [Checking Out & Returning Assets](#checking-out--returning-assets)
  - [Maintenance Scheduling](#maintenance-scheduling)
  - [Machine Bookings](#machine-bookings)
  - [Certification Manager](#certification-manager)
  - [Incident Log](#incident-log)
  - [LOTO Integration from an Asset](#loto-integration-from-an-asset)
- [Projects](#projects)
  - [Project Board (Kanban)](#project-board-kanban)
  - [Creating & Managing Projects](#creating--managing-projects)
  - [Project Task Board](#project-task-board)
  - [Time Tracking](#time-tracking)
  - [Materials & Labor](#materials--labor)
  - [Generating a Project Invoice or Quote](#generating-a-project-invoice-or-quote)
- [Invoices & Quotes](#invoices--quotes)
  - [Creating an Invoice or Quote](#creating-an-invoice-or-quote)
  - [Invoice Editor](#invoice-editor)
  - [Line Items & Markup](#line-items--markup)
  - [Printing & PDF Export](#printing--pdf-export)
- [Purchase Requests](#purchase-requests)
  - [Submitting a Request](#submitting-a-request)
  - [Approval Workflow](#approval-workflow)
  - [Ordering & Receiving](#ordering--receiving)
- [Member Check-In](#member-check-in)
- [LOTO Manager](#loto-manager)
  - [Creating a Procedure](#creating-a-procedure)
  - [Starting a Lockout](#starting-a-lockout)
  - [Releasing a Lockout](#releasing-a-lockout)
  - [Printing LOTO Cards](#printing-loto-cards)
  - [Linking Procedures to Assets](#linking-procedures-to-assets)
- [Teams](#teams)
- [Suppliers](#suppliers)
- [Services](#services)
- [Users & Permissions](#users--permissions)
  - [Roles](#roles)
  - [Permission Sections](#permission-sections)
  - [Creating a User](#creating-a-user)
  - [Permission Profile Templates](#permission-profile-templates)
- [Notifications](#notifications)
- [Settings](#settings)
  - [General Settings](#general-settings)
  - [Theme & Appearance](#theme--appearance)
  - [Features Tab](#features-tab)
  - [Layout Manager](#layout-manager)
  - [Support](#support)
- [Sidebar Navigation](#sidebar-navigation)
- [Tips & Shortcuts](#tips--shortcuts)
- [Troubleshooting](#troubleshooting)

---

## Getting Started

### Logging In

Navigate to your Makerspace ERP URL in any modern browser. Enter your **username** and **password** on the login screen.

<!-- TODO: screenshot — login screen -->

> **Note:** The app works in Chrome, Firefox, Edge, and Safari. A minimum screen width of 768px is recommended.

### First Login & Password Change

If an administrator created your account, you will be prompted to set a new password on your first login. Passwords must be at least **8 characters** long.

To change your password at any time, open **Settings → Account**.

### Navigating the App

The left sidebar is your primary navigation. It is divided into collapsible sections — click any section header to expand or collapse it. The app remembers your collapsed/expanded preferences between sessions.

<!-- TODO: screenshot — sidebar with sections labeled -->

The sidebar sections are:

| Section | Contains |
|---|---|
| **Overview** | Dashboard |
| **Inventory** | Items, Shelf Map, Transactions, Kits |
| **Operations** | Projects, Assets, Check-In |
| **Purchasing** | Purchase Requests, Suppliers |
| **Finance** | Invoices |
| **Safety** | LOTO Manager |
| **Catalog** | Services |
| **Administration** | Users, Teams, Settings |

Click any item to navigate to that page. The currently active page is highlighted in the sidebar.

---

## Dashboard

The dashboard gives you an at-a-glance summary of the entire system.

<!-- TODO: screenshot — dashboard overview -->

**Widgets shown:**

- **Low Stock** — Items whose current quantity is at or below their reorder point
- **Checked-Out Assets** — Equipment currently signed out, with who has it and expected return date (overdue items highlighted in red)
- **Upcoming Maintenance** — Asset maintenance tasks due soon or overdue
- **Active Lockouts** — Any LOTO lockouts currently in effect
- **Recent Transactions** — Latest inventory movements
- **Project Activity** — Open projects and recent time entries
- **Members Checked In** — Current occupancy count (if Member Check-In is enabled)

Click any row in a dashboard widget to jump directly to that record.

---

## Inventory

### Items

The **Items** page lists every part, material, and consumable tracked in the system.

<!-- TODO: screenshot — items list with search bar -->

#### Searching & Filtering

Use the search bar at the top to filter by name, SKU, or description. You can also filter by:
- **Category** — dropdown filter on the right
- **Location** — filter to a specific shelf or bin
- **Low stock only** — toggle to show only items at or below reorder point

#### Adding an Item

1. Click **＋ Add Item**
2. Fill in the required **Name** field and any optional fields (SKU, category, unit, reorder point, cost, supplier, notes)
3. If your category has **custom fields** defined, they will appear at the bottom of the form
4. Click **Save**

<!-- TODO: screenshot — add item form -->

#### Item Detail

Click any item name or row to open its detail panel. From here you can:

- View **current stock levels** across all locations
- See the **transaction history** (all additions, removals, transfers)
- **Adjust quantity** — log a stock count correction
- **Transfer** — move stock between locations
- Open the **Shelf Map** and visually locate the bin this item is stored in (🗺 **Locate on Shelf** button)
- Edit or delete the item

<!-- TODO: screenshot — item detail modal -->

#### Locating an Item on the Shelf Map

If an item is assigned to one or more locations, click **🗺 Locate on Shelf** in the item detail. The app will navigate to the Shelf Map view and highlight the bin containing that item with a red glow.

### Categories & Custom Fields

Categories let you group items and attach custom metadata fields that only appear for items in that category.

Go to **Settings → Categories** to manage categories. For each category you can define:

| Field Type | Use Case |
|---|---|
| Text | Part number, color, notes |
| Number | Voltage, thread pitch, diameter |
| Select | Status (new/used/damaged) |
| Checkbox | Is it RoHS compliant? |
| Date | Expiry date, calibration date |

Custom field values are shown in the item list if **Show in list** is enabled for that field.

### Locations & Shelf Map

Locations are organized in a **tree hierarchy**: Rooms → Cabinets → Shelves → Bins. Each location can have a type (shelf, bin, room, etc.) and an optional icon.

#### Shelf Map View

The Shelf Map gives you a **visual grid** of all locations. Switch between root-level views using the breadcrumb navigation.

<!-- TODO: screenshot — shelf map grid view -->

**Edit Mode** (toggle the ✎ Edit button in the toolbar):
- Drag bins to reorder them
- Click a bin to rename it or change its type
- Resize bins using the handles

#### Uploading a Background Image

In Edit mode, when you are viewing a location that has child bins, a **🖼 Image** button appears in the toolbar. Click it to upload a photo of the actual cabinet or shelf. The photo becomes the background of that location's map view, making it easy to visually match the on-screen grid to the real-world layout.

<!-- TODO: screenshot — shelf map with cabinet photo as background -->

Supported formats: JPEG, PNG, GIF, WebP. The image is stored in the database (no external file hosting needed).

#### Restricted Locations

Any location can be marked as **Restricted**. Users without the **View Restricted Locations** permission cannot see that location or any of its child bins. Useful for locked storage areas or hazmat cabinets.

### Transactions

Every quantity change is logged as a transaction. Transaction types:

| Type | Description |
|---|---|
| **Add** | Stock received or manually added |
| **Remove** | Stock consumed or written off |
| **Transfer** | Moved between locations |
| **Adjustment** | Manual count correction |
| **Pull** | Issued to a project via a pull ticket |

The **Transactions** page shows the full audit trail with timestamps, quantities, and the user who made the change.

### Kits & Assemblies

**Kits** are pre-defined collections of items that can be pulled from inventory together in one action (e.g., a "Soldering Kit" containing solder, flux, and tip cleaner).

**Assemblies** track bills of materials — when you build an assembly, the component items are consumed from stock and the finished assembly is added.

---

## Assets

Assets are tracked equipment — tools, machines, printers, test equipment, and anything else that needs to be signed out or maintained.

### Asset List

<!-- TODO: screenshot — asset grid with status badges -->

Assets are shown as cards grouped by status:

- 🟢 **Available** — ready to check out
- 🟡 **Checked Out** — currently with someone
- 🔴 **Other** — under maintenance, retired, etc.

A **🔒** badge on a card means the asset has an active LOTO lockout. A **🔴 Maint** or **🟡 Maint** badge means a maintenance task is overdue or coming due.

### Checking Out & Returning Assets

**To check out an available asset:**
1. Click the asset card to open its detail, or click **Check Out** directly on the card
2. Enter the name of the person checking it out
3. Optionally set an expected return date
4. Click **Check Out**

<!-- TODO: screenshot — checkout modal -->

**To return an asset:**
1. Click **Return** on the card or **Return Asset** in the detail modal
2. The asset status changes back to Available and the return is logged

The asset detail panel shows the full **checkout history** — who had it, when it was taken out, and when it was returned.

### Maintenance Scheduling

Each asset can have one or more maintenance tasks. Open an asset and scroll to the **🔧 Maintenance** section.

Click **＋ Add Task** to create a maintenance schedule:

| Field | Description |
|---|---|
| Task Name | What needs to be done (e.g., "Oil spindle bearings") |
| Interval | Recurring (every N days) or one-time |
| Next Due Date | When the next service is due |
| Assigned To | Person or team responsible |

Task status indicators:
- 🟢 On schedule
- 🟡 Due soon (within the warning window)
- 🔴 Overdue

Click **✓ Done** to log a completion and automatically schedule the next occurrence for recurring tasks.

### Machine Bookings

The **Bookings** section in an asset's detail lets members reserve time on shared equipment.

**To book a machine:**
1. Open the asset detail
2. Scroll to **📅 Bookings**
3. Click **＋ Book**
4. Set your start and end time, add optional notes
5. The system checks for conflicts — overlapping bookings are rejected automatically

> **Note:** If the **Certification** feature is enabled, you must be certified on a machine before you can book it. See [Certification Manager](#certification-manager) below.

Members can only cancel or edit their own bookings. Admins can modify any booking.

### Certification Manager

> **Requires the Asset Certifications feature to be enabled in Settings → Features.**

The Certification Manager tracks which users are authorized to operate each piece of equipment.

**Admin view (Settings → Certifications or via the sidebar):**
- See all certifications across all assets
- Add or revoke certifications for any user
- Set expiry dates — expired certifications are flagged and block bookings

**User view:**
- Users see only their own certifications
- Shows which machines they are certified on and when certifications expire

**Booking enforcement:** If certifications are enabled, non-admin users are blocked from booking a machine they are not certified on, both in the UI and at the API level. Admins can always book any machine.

<!-- TODO: screenshot — certification manager -->

### Incident Log

Each asset has an **Incident Log** for recording breakdowns, damage, or safety issues.

**To log an incident:**
1. Open the asset detail
2. Scroll to **⚠️ Incidents**
3. Click **＋ Log Incident**
4. Fill in the incident type, severity, description
5. Check **Out of Service** if the machine should be taken offline — this automatically changes the asset status to Out of Service

**To resolve an incident:**
1. Click **Resolve** on the incident row
2. Enter the resolver's name and resolution notes
3. If no other out-of-service incidents remain, the asset status returns to Available automatically

Members can only edit incidents they reported. Admins can edit any incident.

### LOTO Integration from an Asset

Every asset has a **🔒 LOTO Procedures** section in its detail modal. See the [LOTO Manager](#loto-manager) section for full details on creating procedures.

**From the asset modal you can:**
- See all linked LOTO procedures and whether any are currently locked out
- Click **⚡ Lock Out Asset** to initiate a lockout against any linked procedure
- Click **＋ New Procedure** to create a new LOTO procedure pre-linked to this asset

---

## Projects

Projects track work orders, jobs, and fabrication tasks. They tie together time, materials, tasks, and billing.

### Project Board (Kanban)

The main Projects view is a **5-column Kanban board**:

| Column | Meaning |
|---|---|
| **Planning** | Not yet started |
| **Active** | Currently in progress |
| **On Hold** | Paused |
| **Complete** | Work finished |
| **Archived** | Closed/filed away |

Each project appears as a card showing its name, assignee, and task summary. Drag cards between columns to change status, or click a card to open the full project detail.

<!-- TODO: screenshot — project kanban board -->

Click **＋ New Project** in the toolbar to create a project.

### Creating & Managing Projects

Click any project card to open the **full-page project detail** (the URL updates so you can bookmark or share it, and the browser Back button returns you to the board).

The project detail includes:

- **Header** — name, status, assignee, description, edit controls
- **Task Board** — per-project task kanban (see below)
- **Time Clock** — log and view labor hours
- **Materials** — items pulled from inventory
- **Invoices & Quotes** — billing documents linked to this project
- **Pull Ticket** — issue inventory to the project

### Project Task Board

Each project has its own **4-column task board** for breaking work into actionable items:

| Column | Meaning |
|---|---|
| **To Do** | Not yet started |
| **In Progress** | Being worked on |
| **Review** | Awaiting review or approval |
| **Done** | Complete |

**Adding a task:**
1. Click **＋ Add Task** in any column (the new task defaults to that column's status)
2. Fill in the title, description, priority, assignee, team, due date, and color label
3. Click **Save**

**Managing tasks:**
- Drag task cards between columns to update status
- Click a card to open the edit modal for full details
- Priority levels: Low / Normal / High / Urgent (color-coded)
- Tasks can be assigned to an individual user or a team

> **Access control:** Users can only see and modify tasks on projects they own or have been explicitly shared on. Admins have access to all projects.

<!-- TODO: screenshot — project task board -->

### Time Tracking

The **⏱ Time Clock** section in the project detail lets you log labor hours.

**Clock in/out method:**
1. Expand the Time Clock section
2. Click **Clock In** — enter the worker's name
3. When work is done, click **Clock Out** — hours are calculated automatically

**Manual entry:** Click **＋ Add Time Entry** to log hours directly with a description (useful for after-the-fact logging).

All time entries are shown in the panel with the worker name, date, hours, and description. Total hours are summed at the top.

<!-- TODO: screenshot — time clock section expanded -->

### Materials & Labor

The **Materials** section in the project detail shows all items that have been pulled from inventory for this project via **Pull Tickets**.

To pull materials:
1. Open the project
2. Click **＋ Pull Ticket**
3. Search for items and enter quantities
4. Submit — stock is deducted from inventory and logged against the project

### Generating a Project Invoice or Quote

Once work is complete, generate a billing document directly from the project:

1. Open the project detail
2. Scroll to **Invoices & Quotes**
3. Click **🧾 New Invoice** or **📋 New Quote**
4. Enter client billing information in the popup
5. The system pre-populates line items from the project's pulled materials and logged labor hours
6. The invoice opens in the **Invoice Editor** for review and adjustment before sending

<!-- TODO: screenshot — project invoices panel -->

---

## Invoices & Quotes

### Creating an Invoice or Quote

**From the Invoices tab** (not tied to a project):
1. Click **＋ Invoice** or **＋ Quote**
2. Enter client details (name, address, invoice date, due date)
3. Add line items manually
4. Save

**From a project:** See [Generating a Project Invoice or Quote](#generating-a-project-invoice-or-quote) above.

### Invoice Editor

The invoice editor is the main workspace for building and finalizing billing documents.

<!-- TODO: screenshot — invoice editor with line items -->

**Header fields:**
- Invoice / Quote number (auto-generated, editable)
- Client name and address
- Invoice date and due date
- Status (Draft → Sent → Accepted → Paid → Void)
- Tax percentage

**Line item types:**

| Type | Description |
|---|---|
| **Part** | Inventory item — pulls name and cost from item record |
| **Labor** | Time-based charge — markup is always 0% |
| **Service** | From the Services catalog |
| **Custom** | Free-form description and price |

### Line Items & Markup

Parts and services can have a **markup percentage** applied. The unit price stored in the system is the **base cost**; the markup is calculated at display and print time.

> **Example:** A part costs $10.00 with a 25% markup → billed at $12.50

Labor lines always use the straight rate with no markup.

Drag line items to reorder them. Click the × button to remove a line.

### Printing & PDF Export

Click **🖨 Print / PDF** in the invoice editor. A print-ready view opens in a new window formatted for A4/Letter paper. Use your browser's Print dialog to:
- Print to a physical printer
- Save as PDF (choose "Save as PDF" in the printer dropdown)

The printed invoice includes your business details, client info, itemized line items, subtotal, tax, and total.

---

## Purchase Requests

The Purchase Request system manages the full procurement cycle from request to receipt.

### Submitting a Request

Any user can submit a purchase request:

1. Navigate to **🛒 Purchase Requests**
2. Click **＋ New Request**
3. Select a **Supplier** (optional at this stage)
4. Set **Urgency**: Low / Normal / High / Critical
5. Add line items — search for existing inventory items or type a custom description
6. Add notes and click **Submit Request**

<!-- TODO: screenshot — new purchase request form -->

The request moves to **Submitted** status and approvers are notified automatically.

### Approval Workflow

Users with the **Purchase Approver** permission see all submitted requests.

**To approve:**
1. Open the request
2. Review the line items, supplier, and urgency
3. Click **✅ Approve** — the request moves to Approved and purchasers are notified

**To reject:**
1. Click **✗ Reject** — optionally add a rejection reason in the notes

Status flow:

```
Draft → Submitted → Approved → Ordered → Received
                 ↘ Rejected
```

### Ordering & Receiving

Users with the **Purchase Purchaser** permission can advance approved requests:

**Mark as Ordered:**
1. Open an approved request
2. Click **📦 Mark as Ordered** — records the date and purchaser name
3. Status moves to **Ordered**

**Mark as Received:**
1. Click **✓ Received** — records receipt date
2. Status moves to **Received**
3. Individual line items can be marked received separately if a partial order arrives

---

## Member Check-In

> **Requires the Member Check-In feature to be enabled in Settings → Features.**

The **Check-In** page lets members sign in and out of the makerspace, and lets staff monitor current occupancy.

<!-- TODO: screenshot — member check-in page -->

### Checking In & Out

1. Navigate to **Check-In** in the sidebar
2. Enter your **Member ID** or name
3. Click **Check In** — your arrival is recorded with a timestamp
4. When leaving, return to the page and click **Check Out**

The page shows a live **current occupancy count** and a list of members currently signed in.

### Capacity Limit

> **Admin only.** An administrator can set the maximum allowed occupancy in the Check-In settings (⚙ Config button on the Check-In page). When the space is at capacity, new check-ins are blocked until someone checks out.

### Check-In History

Staff can view the full check-in history log, including timestamps and session durations, to understand usage patterns.

---

## LOTO Manager

LOTO (Lockout / Tag-out) procedures protect workers from unexpected equipment energization during maintenance. The LOTO Manager stores procedures, tracks active lockouts, and generates printable lockout cards.

> **Access:** Users with the LOTO Manager permission can create and manage procedures. Admins have full access. Users can only edit or delete procedures they created.

### Creating a Procedure

1. Navigate to **🔒 LOTO Manager**
2. Click **＋ New Procedure**
3. Fill in:

| Field | Description |
|---|---|
| Title | Descriptive name (e.g., "CNC Router Full Lockout") |
| Linked Asset | Optional — link to an asset in the Asset Manager |
| Machine Name | Plain-text machine description |
| Machine ID / Tag | Asset tag or equipment ID |
| Location | Where the machine is located |
| Department | Responsible department |
| Energy Sources | List each energy source: type, location, isolation method |
| PPE Required | Personal protective equipment needed |
| Shutdown Procedure Steps | Numbered steps in order |
| Authorized By | Name of the person who approved this procedure |
| Review Date | When the procedure was last reviewed |

<!-- TODO: screenshot — new LOTO procedure form -->

### Starting a Lockout

**From the LOTO Manager list:**
1. Find the procedure row
2. Click **🔒 Lock Out** — enter your name and optional notes
3. The row changes to 🔴 status showing the active lockout count

**From an Asset:**
1. Open the asset detail
2. Click **⚡ Lock Out Asset**
3. Select which procedure to lock out (or create a new one)

<!-- TODO: screenshot — lockout confirmation dialog -->

> **Important:** The system records the lockout but does not replace physical locks and tags. Always apply physical lockout devices per your safety program.

### Releasing a Lockout

**Release all lockouts on a procedure:**
- Click **🔓 Release All** on the procedure row in the LOTO Manager

**Release a specific lockout:**
- Open the procedure (click **View**) and release individual lockout entries from the detail panel

**From an Asset:**
- The LOTO panel in the asset detail shows active lockouts with a **🔓 Release** button

### Printing LOTO Cards

Click **🖨 Print** on any procedure row. A formatted lockout card opens containing:

- Equipment identification
- Energy source table with isolation points
- PPE requirements
- Shutdown procedure steps
- Authorization and review information
- Space for physical tag information

Use your browser's Print → Save as PDF to create a PDF version. Print and laminate for posting on equipment.

<!-- TODO: screenshot — printed LOTO card -->

### Linking Procedures to Assets

Linking a LOTO procedure to an asset enables:
- The 🔒 badge on asset cards when a lockout is active
- The LOTO panel in the asset detail showing all procedures
- Quick lockout/release directly from the asset view
- Clickable asset links in the LOTO Manager list

To link: either select the asset in the **Linked Asset** dropdown when creating a procedure, or use **＋ New Procedure** from within the asset detail (the link is set automatically).

---

## Teams

Teams let you group users for assignment to project tasks and maintenance jobs.

Navigate to **Teams** in the Administration section of the sidebar.

**Creating a team:**
1. Click **＋ New Team**
2. Give the team a name and a color label
3. Add members by selecting users from the searchable dropdown
4. Each member can have a role within the team (e.g., Lead, Member)

**Using teams:**
- Teams appear in the **Assignee** dropdown on project task cards — assign a task to a whole team instead of an individual
- Teams appear in the **Assigned To** field on maintenance tasks
- Team color labels appear on task cards for quick visual identification

<!-- TODO: screenshot — teams page -->

---

## Suppliers

The Suppliers page manages your vendor list.

Each supplier record includes:
- Name, contact person, email, phone
- Website and address
- Notes

Suppliers are referenced in **Purchase Requests** and can be linked to inventory items as the preferred source.

<!-- TODO: screenshot — suppliers list -->

---

## Services

The **Services** catalog stores billable line items you use repeatedly on invoices — shop fees, labor rates, standard charges, etc.

Each service has:

| Field | Description |
|---|---|
| Name | Display name on invoices |
| Category | Fee / Labor / Materials / Other |
| Unit Price | Base rate |
| Markup % | Applied on top of unit price when billing |
| Use Markup | Toggle — some services bill at cost, others with markup |
| Active | Inactive services don't appear in invoice dropdowns |

When adding a service line to an invoice, select from the catalog and the price and markup pre-fill automatically.

---

## Users & Permissions

> **Admin only.** Navigate to **Settings → Users**.

### Roles

There are three roles:

| Role | Access |
|---|---|
| **Admin** | Full access to all features including user management and settings. Bypasses all permission checks. |
| **Staff** | Elevated default permissions (includes Purchase Approver and Restricted Locations access). Individual permissions are still configurable per user. |
| **User** | Standard access determined by individual permissions. |

> **Note:** Staff accounts cannot access the admin-only areas (user management, system settings). Only Admin accounts have that access.

### Permission Sections

Each user has granular read/write permissions for each module:

| Permission | Controls |
|---|---|
| Inventory | View and edit items, locations, transactions |
| Assets | View and manage assets, checkouts |
| Projects | View and manage projects |
| Invoices | View and create invoices |
| Suppliers | View and manage supplier list |
| Services | View and manage services catalog |
| Users | View and manage user accounts (admin sub-permission) |
| Settings | Access to app settings |
| Shelf Map | View and edit the shelf map |
| View Restricted Locations | See locations marked as restricted |
| Purchase Approver | Approve or reject purchase requests |
| Purchase Purchaser | Mark requests as ordered/received |
| LOTO Manager | Create and manage LOTO procedures |

**Read** permission allows viewing. **Write** permission allows creating, editing, and deleting. Write always requires Read.

### Creating a User

1. Go to **Settings → Users**
2. Click **＋ Add User**
3. Enter username, full name, email, and a temporary password
4. Set the role (Admin / Staff / User) and configure permissions
5. Click **Save** — the user will be prompted to change their password on first login

<!-- TODO: screenshot — add user form with permission checkboxes -->

### Permission Profile Templates

Profiles let you save a named set of permissions and apply them quickly to new or existing users.

**Creating a profile:**
1. Click **🏷 Profiles** next to the Add User button
2. Click **＋ New Profile**
3. Give it a name (e.g., "Shop Floor Operator"), set the role, and configure permissions
4. Save

**Applying a profile:**
- When creating or editing a user, click **Load Profile** and select from the saved profiles
- The permission checkboxes update instantly — you can still adjust individual permissions before saving

**Feature tier presets:** In the Features tab, admins can apply a preset (Basic / Standard / Full) to quickly enable a sensible bundle of features at once, then fine-tune individual toggles as needed.

---

## Notifications

The 🔔 bell icon at the bottom of the sidebar shows your unread notification count.

<!-- TODO: screenshot — notification bell with badge -->

Click the bell to open the **Notification Panel**, which lists all your notifications newest-first. Click any notification to jump to the relevant record. Click **Mark All Read** to clear the badge.

**Notifications are sent automatically for:**

| Event | Who is Notified |
|---|---|
| Purchase request submitted | All users with Purchase Approver permission |
| Purchase request approved | All users with Purchase Purchaser permission |
| Purchase request rejected | The original submitter |
| LOTO lockout started | All users with LOTO Manager permission |
| LOTO lockout released | All users with LOTO Manager permission |

Notifications are delivered in real-time (the app polls every 30 seconds automatically).

---

## Settings

Navigate to **Settings** via the sidebar (admin users only for most tabs).

### General Settings

Covers application-wide configuration including:
- Business name and address (used on invoice headers)
- Currency symbol
- Tax rate defaults
- Date format
- MQTT and Home Assistant integration settings

<!-- TODO: screenshot — general settings tab -->

### Theme & Appearance

The **Theme** tab lets you customize the app's color scheme.

**Dark / Light mode:** Click the sun/moon toggle in the top toolbar to switch instantly. The preference is saved per browser.

**Custom theme colors:** Expand the Theme tab in Settings to configure individual color variables:

| Setting | Controls |
|---|---|
| Accent color | Buttons, links, active highlights |
| Background | Main page background |
| Card background | Sidebar and card surfaces |
| Field / Input Background | Color of input fields and form controls |
| Text colors | Primary and secondary text |

**Presets:** Click **Dark Preset** or **Light Preset** to restore the default palette for that mode. Individual variables can be adjusted after applying a preset.

<!-- TODO: screenshot — theme settings panel -->

### Features Tab

> **Admin only.**

The Features tab lets you enable or disable entire modules and sub-features globally. Disabled features are hidden from the sidebar and from all users.

<!-- TODO: screenshot — features tab with toggles -->

Available feature toggles include:

- Invoicing (and sub-toggle: Project Invoicing)
- Suppliers
- LOTO Manager
- Purchase Requests
- Projects (and sub-toggle: Time Clock)
- Assets (and sub-toggles: Bookings, Certifications, Incidents)
- Member Check-In
- Shelf Map
- Services

**Tier presets:** Use the **Basic / Standard / Full** preset buttons to apply a curated bundle of feature toggles at once. Useful for quickly setting up a new installation.

Changes take effect immediately for all users without requiring a page reload.

### Layout Manager

The Layout Manager controls which **Settings tabs** are visible in the navigation.

Each tab has a checkbox — uncheck it to hide that tab from the settings sidebar.

> **Note:** The **☕ Support** tab is always visible and cannot be hidden.

<!-- TODO: screenshot — layout manager tab list -->

### Support

The Support tab contains a link to the developer's Buy Me a Coffee page. This tab is always present regardless of layout manager settings.

---

## Sidebar Navigation

The left sidebar is divided into **collapsible sections**. Click any section header (the rows with ▾ arrows) to collapse or expand that section. The collapsed/expanded state is saved per-browser automatically.

**Keyboard tip:** The sidebar has no keyboard shortcut by default, but clicking any nav item focuses it and Enter activates it.

### Sidebar Footer

The bottom of the sidebar shows:
- 🔔 **Notification bell** with unread count badge
- Current logged-in username
- App version number

---

## Tips & Shortcuts

### General

- **Click any page title row** in a table to open that record's detail
- **Breadcrumbs** in the shelf map let you navigate up the location hierarchy quickly
- **Toast notifications** appear in the bottom-right corner to confirm actions or report errors — they auto-dismiss after a few seconds
- **Searchable dropdowns** — any user/assignee field with a search icon supports typing to filter the list

### Inventory

- Set **Reorder Points** on items so the dashboard flags them when stock is low
- Use **Bulk Pull Tickets** to issue multiple items to a project in one action
- The **Locate on Shelf** button in item details highlights the bin on the shelf map — useful for training new staff

### Assets

- Use **asset tags** (e.g., printed QR codes or barcodes) to make checkout faster — search by tag in the asset list
- Set maintenance schedules immediately when adding new equipment so nothing falls through the cracks
- Link LOTO procedures to assets right away so the lockout badge appears on the card when maintenance is in progress
- Enable **Certifications** to require operator training before allowing machine bookings

### Projects

- Use the **Kanban board** to see all project statuses at a glance — drag cards to update status without opening the detail
- Break projects into **tasks** on the per-project task board to track granular progress
- Assign tasks to **Teams** when the work involves a group rather than one person
- Generate invoices directly from a project to pre-populate billing with actual materials and labor

### Invoices

- **Quotes** and **Invoices** use the same editor — convert a quote to an invoice by changing the type in the editor header
- The **markup** on parts is baked into the printed price — your internal costs stay private
- Invoice numbers are auto-generated but can be edited to match your existing numbering scheme

### LOTO

- Print and **laminate** LOTO cards for each machine — store them in a pocket near the lockout station
- A procedure can have multiple **active lockouts** simultaneously (e.g., two technicians both lock out the same machine for group lockout)
- The 🔴 badge on an asset card in the asset grid means a lockout is active — don't check out a locked-out asset for normal use

### Purchase Requests

- Set the **Urgency** field accurately — it's visible to approvers and helps prioritize the queue
- Add **notes** when rejecting a request to give the submitter actionable feedback
- Partial receiving is supported — mark individual lines received as stock arrives

---

## Troubleshooting

### Page Not Loading / Blank Screen

1. Hard-refresh the browser: `Ctrl+Shift+R` (Windows/Linux) or `Cmd+Shift+R` (Mac)
2. Clear browser cache and cookies for the app's domain
3. Check with your administrator that the backend service is running

### "Something went wrong" Error Toast

This usually means the backend returned an error. Common causes:
- Trying to delete a record that is referenced by another record (e.g., deleting a location that has items in it)
- Session expired — refresh the page and log in again
- Server-side error — your administrator can check the logs with `sudo journalctl -u makerspace-erp -n 50`

### Permissions Errors / "Access Denied"

If a button is missing or a page shows "Access denied," contact your administrator to review your user permissions under **Settings → Users**.

For project tasks specifically: users can only see tasks on projects they own or have been shared on. If you cannot see expected tasks, ask the project owner to share the project with you.

### Booking Blocked

If you cannot book a machine, check:
1. **Certification** — if certifications are enabled, you must be certified on that machine. Contact an admin to add your certification.
2. **Time conflict** — the selected time slot may be taken. Try a different time window.
3. **Asset status** — a machine marked Out of Service or under a LOTO lockout cannot be booked.

### Changes Not Saving

- Ensure all required fields (marked with *) are filled in
- Check for a red error toast in the bottom-right corner — it will describe what validation failed

---

*Guide generated for Makerspace ERP ALPHA v1.6.4. Remove this file before public release.*
