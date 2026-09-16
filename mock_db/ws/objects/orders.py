"""ORDER object handlers.

Owns the brain rules around orders:
    - customer must exist on create
    - status vocabulary + legal transitions
    - per-line item existence + raw stock check
    - total recompute from lines
"""
from __future__ import annotations

import sqlite3
from typing import Any

from ..errors import WsError, WS_INVALID_REQUEST, WS_NOT_FOUND, WS_BUSINESS_RULE
from .validators import (
    ALLOWED_ORDER_STATUSES,
    assert_customer_exists,
    assert_item_and_stock,
    assert_order_exists,
    assert_order_status_transition,
    delete_with_fk_guard,
)


def get_order(conn: sqlite3.Connection, key: Any) -> dict[str, Any]:
    order = conn.execute(
        "SELECT id, customer_id, status, total, created_at FROM orders WHERE id = ?",
        (int(key),),
    ).fetchone()
    if order is None:
        raise WsError(WS_NOT_FOUND, "Invalid request, Data does not exist.")

    lines = conn.execute(
        """
        SELECT oi.product_id, oi.quantity, oi.price, i.code AS product_code, i.name AS product_name
        FROM order_items oi
        LEFT JOIN items i ON i.id = oi.product_id
        WHERE oi.order_id = ?
        ORDER BY oi.product_id
        """,
        (int(key),),
    ).fetchall()

    data: dict[str, Any] = {
        "ORDER": [
            {
                "ID": order["id"],
                "CUSTOMER_ID": order["customer_id"],
                "STATUS": order["status"],
                "TOTAL": order["total"],
                "CREATED_AT": order["created_at"],
            }
        ],
        "ORDERITEMS": [
            {
                "PRODUCT_ID": r["product_id"],
                "QUANTITY": r["quantity"],
                "PRICE": r["price"],
                "PRODUCT_CODE": r["product_code"],
                "PRODUCT_NAME": r["product_name"],
            }
            for r in lines
        ],
    }
    return {"success": True, "readOnly": True, "data": data}


def set_order(conn: sqlite3.Connection, key: Any, data: dict[str, Any]) -> dict[str, Any]:
    """Insert or update an order (and optional ORDERITEMS).

    Validates *all* lines up front so we never half-create an order whose
    second line would have failed. The lines REPLACE the existing set
    (matches the existing setData ORDER semantics in mock_ws.py).
    """
    order_rows = data.get("ORDER") or []
    if not order_rows:
        raise WsError(WS_INVALID_REQUEST, "Invalid Request. Ensure that your request is valid")
    order_row = order_rows[0]

    # Validate ORDERITEMS up front -- product existence, qty > 0, qty <= stock.
    pending_lines: list[tuple[int, int, float | None]] = []
    if "ORDERITEMS" in data:
        for ln in data.get("ORDERITEMS") or []:
            product_id = int(ln.get("PRODUCT_ID") or ln.get("PRODUCTID") or 0)
            qty = int(ln.get("QUANTITY") or 0)
            assert_item_and_stock(conn, product_id, qty)
            raw_price = ln.get("PRICE")
            price: float | None = float(raw_price) if raw_price is not None else None
            pending_lines.append((product_id, qty, price))

    if key is None or str(key).strip() == "":
        # Create path -- validate customer + status, then insert.
        customer_id = assert_customer_exists(
            conn,
            order_row.get("CUSTOMER_ID") or order_row.get("CUSTOMERID"),
        )
        requested_status = str(order_row.get("STATUS") or "Draft")
        if requested_status not in ALLOWED_ORDER_STATUSES:
            raise WsError(
                WS_BUSINESS_RULE,
                f"Invalid order status '{requested_status}'. "
                f"Allowed: {list(ALLOWED_ORDER_STATUSES)}",
            )
        (mx,) = conn.execute("SELECT COALESCE(MAX(id), 0) + 1 AS next_id FROM orders").fetchone()
        order_id = int(mx)
        conn.execute(
            "INSERT INTO orders(id, customer_id, status, total) VALUES (?,?,?,?)",
            (order_id, customer_id, requested_status, 0.0),
        )
    else:
        # Update path -- validate that the order exists and the status
        # transition is legal.
        order_id = assert_order_exists(conn, key)
        if "STATUS" in order_row:
            cur_row = conn.execute(
                "SELECT status FROM orders WHERE id = ?", (order_id,)
            ).fetchone()
            current = str(cur_row["status"])
            new = str(order_row["STATUS"])
            assert_order_status_transition(current, new)
            conn.execute("UPDATE orders SET status=? WHERE id=?", (new, order_id))

    # Replace lines if provided. Already validated above.
    if "ORDERITEMS" in data:
        conn.execute("DELETE FROM order_items WHERE order_id=?", (order_id,))
        for product_id, qty, price in pending_lines:
            if price is None:
                item = conn.execute(
                    "SELECT price FROM items WHERE id=?", (product_id,)
                ).fetchone()
                price = float(item["price"]) if item else 0.0
            conn.execute(
                "INSERT INTO order_items(order_id, product_id, quantity, price) VALUES (?,?,?,?)",
                (order_id, product_id, qty, float(price)),
            )

    # Recompute total from lines (idempotent).
    (tot,) = conn.execute(
        "SELECT COALESCE(SUM(quantity * price), 0) AS total FROM order_items WHERE order_id=?",
        (order_id,),
    ).fetchone()
    conn.execute("UPDATE orders SET total=? WHERE id=?", (float(tot), order_id))

    conn.commit()
    return {"success": True, "id": str(order_id)}


def del_order(conn: sqlite3.Connection, key: Any) -> dict[str, Any]:
    cur = delete_with_fk_guard(
        conn, "DELETE FROM orders WHERE id = ?", (int(key),),
        what=f"order {int(key)}",
    )
    if cur.rowcount == 0:
        raise WsError(WS_NOT_FOUND, "Invalid request, Data does not exist.")
    conn.commit()
    return {"success": True}
