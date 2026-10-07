"""ITEM (product/SKU) object handlers."""
from __future__ import annotations

import sqlite3
from typing import Any

from ..errors import WS_INVALID_REQUEST, WS_NOT_FOUND, WsError
from .validators import delete_with_fk_guard


def get_item(conn: sqlite3.Connection, key: Any) -> dict[str, Any]:
    item = conn.execute(
        "SELECT id, code, name, price, stock, reserved, created_at FROM items WHERE id = ?",
        (int(key),),
    ).fetchone()
    if item is None:
        raise WsError(WS_NOT_FOUND, "Invalid request, Data does not exist.")
    data = {
        "ITEM": [
            {
                "ID": item["id"],
                "CODE": item["code"],
                "NAME": item["name"],
                "PRICE": item["price"],
                "STOCK": item["stock"],
                "RESERVED": item["reserved"],
                "CREATED_AT": item["created_at"],
            }
        ]
    }
    return {"success": True, "readOnly": True, "data": data}


def set_item(conn: sqlite3.Connection, key: Any, data: dict[str, Any]) -> dict[str, Any]:
    """Insert or PATCH-update an item.

    No "brain" rules here -- ITEMs are master data and the schema's CHECK
    constraints (price >= 0, stock >= 0, reserved >= 0) are sufficient. The
    business layer is responsible for stock changes via reservation/invoice
    flows; raw setData ITEM is a low-level escape hatch.
    """
    item_rows = data.get("ITEM") or []
    if not item_rows:
        raise WsError(WS_INVALID_REQUEST, "Invalid Request. Ensure that your request is valid")
    item_row = item_rows[0]

    def g(field: str) -> Any:
        return item_row.get(field)

    if key is None or str(key).strip() == "":
        (mx,) = conn.execute("SELECT COALESCE(MAX(id), 0) + 1 AS next_id FROM items").fetchone()
        item_id = int(mx)
        conn.execute(
            "INSERT INTO items(id, code, name, price, stock, reserved) VALUES (?,?,?,?,?,?)",
            (
                item_id,
                str(g("CODE") or f"AUTO-{item_id}"),
                str(g("NAME") or ""),
                float(g("PRICE") or 0.0),
                int(g("STOCK") or 0),
                int(g("RESERVED") or 0),
            ),
        )
    else:
        item_id = int(key)
        # PATCH semantics: only update fields that were sent.
        if "CODE" in item_row:
            conn.execute("UPDATE items SET code=? WHERE id=?", (str(g("CODE")), item_id))
        if "NAME" in item_row:
            conn.execute("UPDATE items SET name=? WHERE id=?", (str(g("NAME")), item_id))
        if "PRICE" in item_row:
            conn.execute("UPDATE items SET price=? WHERE id=?", (float(g("PRICE")), item_id))
        if "STOCK" in item_row:
            conn.execute("UPDATE items SET stock=? WHERE id=?", (int(g("STOCK")), item_id))
        if "RESERVED" in item_row:
            conn.execute("UPDATE items SET reserved=? WHERE id=?", (int(g("RESERVED")), item_id))

    conn.commit()
    return {"success": True, "id": str(item_id)}


def del_item(conn: sqlite3.Connection, key: Any) -> dict[str, Any]:
    cur = delete_with_fk_guard(
        conn, "DELETE FROM items WHERE id = ?", (int(key),),
        what=f"item {int(key)}",
    )
    if cur.rowcount == 0:
        raise WsError(WS_NOT_FOUND, "Invalid request, Data does not exist.")
    conn.commit()
    return {"success": True}
