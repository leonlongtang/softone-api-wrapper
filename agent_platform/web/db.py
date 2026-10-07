"""Read the mock ERP's business tables and diff two snapshots: what a turn changed in the database."""

from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any

from mock_db.ws.session import DEFAULT_DB_PATH

TABLES = ("customers", "items", "orders", "order_items", "invoices_business", "payments")

Snapshot = dict[str, dict[tuple, dict[str, Any]]]  # table -> primary key -> row


def primary_key(conn: sqlite3.Connection, table: str) -> list[str]:
    cols = sorted((r[5], r[1]) for r in conn.execute(f"PRAGMA table_info({table})") if r[5])
    return [name for _, name in cols]


def snapshot(db_path: Path = DEFAULT_DB_PATH) -> Snapshot:
    if not db_path.exists():
        return {t: {} for t in TABLES}
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        out: Snapshot = {}
        for table in TABLES:
            pk = primary_key(conn, table)
            rows = [dict(r) for r in conn.execute(f"SELECT * FROM {table}")]
            out[table] = {tuple(r[k] for k in pk): r for r in rows}
        return out
    finally:
        conn.close()


def diff(before: Snapshot, after: Snapshot) -> list[dict[str, Any]]:
    """Rows inserted, updated or deleted between two snapshots, as before/after pairs."""
    changes = []
    for table in TABLES:
        old, new = before.get(table, {}), after.get(table, {})
        for key in sorted(old.keys() | new.keys(), key=repr):
            a, b = old.get(key), new.get(key)
            if a == b:
                continue
            op = "insert" if a is None else "delete" if b is None else "update"
            changed = sorted(k for k in (a or {}) | (b or {}) if (a or {}).get(k) != (b or {}).get(k))
            changes.append({"table": table, "op": op, "key": list(key), "before": a, "after": b, "changed": changed})
    return changes
