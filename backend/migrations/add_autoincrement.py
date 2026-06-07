"""
Migration: Add AUTOINCREMENT to all primary-key columns
Run on the server ONCE with the service stopped:

    sudo systemctl stop makerspace-erp
    cd /opt/makerspace-erp
    venv/bin/python -m backend.migrations.add_autoincrement
    sudo systemctl start makerspace-erp

What it does:
  For every table — renames it to _old, recreates it with AUTOINCREMENT,
  copies all rows, drops the _old table, and restores any indexes.
  Foreign keys are disabled during the operation so order doesn't matter.
  A backup is written to /opt/makerspace-erp/data/makerspace_pre_autoincrement.db
  before any changes are made.
"""

import re
import shutil
import sqlite3
from pathlib import Path

DB_PATH   = Path("/opt/makerspace-erp/data/makerspace.db")
BACKUP    = DB_PATH.with_name("makerspace_pre_autoincrement.db")

# All tables in safe migration order (parents before children,
# but we disable FK enforcement anyway so order is just for clarity)
TABLES = [
    "app_settings",
    "users",
    "materials",
    "categories",
    "locations",
    "items",
    "projects",
    "project_items",
    "item_locations",
    "supplier_links",
    "transactions",
    "purchase_orders",
    "po_items",
    "assets",
    "asset_checkouts",
    "category_fields",
    "item_field_values",
    "kits",
    "kit_items",
    "assembly_components",
]


def patch_ddl(ddl: str) -> str | None:
    """
    Given a CREATE TABLE statement, return a version where the INTEGER
    PRIMARY KEY column has the AUTOINCREMENT keyword added.
    Returns None if AUTOINCREMENT is already present or not applicable.
    """
    if "AUTOINCREMENT" in ddl.upper():
        return None  # already done

    # Match: <colname> INTEGER PRIMARY KEY  (case-insensitive, optional NOT NULL etc.)
    patched, n = re.subn(
        r"(\bINTEGER\s+PRIMARY\s+KEY\b)(?!\s+AUTOINCREMENT)",
        r"\1 AUTOINCREMENT",
        ddl,
        flags=re.IGNORECASE,
    )
    return patched if n > 0 else None


def migrate_table(cur: sqlite3.Cursor, table: str) -> str:
    # Get current DDL
    cur.execute(
        "SELECT sql FROM sqlite_master WHERE type='table' AND name=?", (table,)
    )
    row = cur.fetchone()
    if row is None:
        return f"  {table}: SKIP (table not found)"

    original_ddl = row[0]
    new_ddl = patch_ddl(original_ddl)
    if new_ddl is None:
        return f"  {table}: SKIP (AUTOINCREMENT already present)"

    # Rename old table
    cur.execute(f'ALTER TABLE "{table}" RENAME TO "{table}_old"')

    # Create new table with AUTOINCREMENT
    cur.execute(new_ddl)

    # Copy all data
    cur.execute(f'INSERT INTO "{table}" SELECT * FROM "{table}_old"')

    # Drop old table
    cur.execute(f'DROP TABLE "{table}_old"')

    return f"  {table}: OK"


def get_indexes(cur: sqlite3.Cursor, table: str) -> list[str]:
    cur.execute(
        "SELECT sql FROM sqlite_master WHERE type='index' AND tbl_name=? AND sql IS NOT NULL",
        (table,),
    )
    return [r[0] for r in cur.fetchall()]


def main() -> None:
    if not DB_PATH.exists():
        print(f"ERROR: database not found at {DB_PATH}")
        return

    print(f"Backing up database to {BACKUP} …")
    shutil.copy2(DB_PATH, BACKUP)
    print("Backup complete.\n")

    con = sqlite3.connect(DB_PATH)
    cur = con.cursor()

    try:
        cur.execute("PRAGMA foreign_keys = OFF")
        cur.execute("BEGIN")

        for table in TABLES:
            # Capture existing indexes before we rename
            indexes = get_indexes(cur, table)

            result = migrate_table(cur, table)
            print(result)

            # Recreate indexes on new table
            for idx_sql in indexes:
                try:
                    cur.execute(idx_sql)
                except Exception as e:
                    print(f"    index warning: {e}")

        con.commit()
        print("\nAll tables migrated. Enabling foreign keys …")
        cur.execute("PRAGMA foreign_keys = ON")
        print("Done.")

    except Exception as e:
        con.rollback()
        print(f"\nERROR: {e}")
        print("Transaction rolled back. Your database is unchanged.")
        print(f"The backup at {BACKUP} is also available.")
        raise
    finally:
        con.close()


if __name__ == "__main__":
    main()
