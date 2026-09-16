"""INVOICE (business invoice) object handlers.

Note: this is the order-side `invoices_business` table, NOT the eInvoice
signature lookup table (`invoices`) -- that one lives in services/einvoice.py.

Brain rules enforced here:
    - customer must exist on create / update
    - order_id (if given) must exist
    - one invoice per order_id (the "already invoiced" rule)
"""
from __future__ import annotations

import sqlite3
from typing import Any

from ..errors import WsError, WS_INVALID_REQUEST, WS_NOT_FOUND
from .validators import (
    assert_customer_exists,
    assert_no_existing_invoice,
    assert_order_exists,
    delete_with_fk_guard,
)


def get_invoice(conn: sqlite3.Connection, key: Any) -> dict[str, Any]:
    inv = conn.execute(
        "SELECT id, customer_id, order_id, amount, status, created_at "
        "FROM invoices_business WHERE id = ?",
        (int(key),),
    ).fetchone()
    if inv is None:
        raise WsError(WS_NOT_FOUND, "Invalid request, Data does not exist.")
    data = {
        "INVOICE": [
            {
                "ID": inv["id"],
                "CUSTOMER_ID": inv["customer_id"],
                "ORDER_ID": inv["order_id"],
                "AMOUNT": inv["amount"],
                "STATUS": inv["status"],
                "CREATED_AT": inv["created_at"],
            }
        ]
    }
    return {"success": True, "readOnly": True, "data": data}


def set_invoice(conn: sqlite3.Connection, key: Any, data: dict[str, Any]) -> dict[str, Any]:
    inv_rows = data.get("INVOICE") or []
    if not inv_rows:
        raise WsError(WS_INVALID_REQUEST, "Invalid Request. Ensure that your request is valid")
    inv_row = inv_rows[0]

    def g(field: str) -> Any:
        return inv_row.get(field)

    if key is None or str(key).strip() == "":
        # Create path.
        customer_id = assert_customer_exists(conn, g("CUSTOMER_ID"))
        raw_order_id = g("ORDER_ID")
        order_id_val: int | None = None
        if raw_order_id is not None and str(raw_order_id).strip() != "":
            order_id_val = assert_order_exists(conn, raw_order_id)
            # ChatGPT's "already invoiced" rule. The schema's
            # ux_invoice_per_order partial unique index would also catch this,
            # but raising the structured WsError early gives agents a clean
            # business error instead of a generic IntegrityError.
            assert_no_existing_invoice(conn, order_id_val)
        amount = float(g("AMOUNT") or 0.0)
        status = str(g("STATUS") or "unpaid")
        (mx,) = conn.execute("SELECT COALESCE(MAX(id), 0) + 1 AS next_id FROM invoices_business").fetchone()
        inv_id = int(mx)
        conn.execute(
            "INSERT INTO invoices_business(id, customer_id, order_id, amount, status) VALUES (?,?,?,?,?)",
            (inv_id, customer_id, order_id_val, amount, status),
        )
    else:
        # Update path.
        inv_id = int(key)
        if conn.execute("SELECT 1 FROM invoices_business WHERE id=?", (inv_id,)).fetchone() is None:
            raise WsError(WS_NOT_FOUND, "Invalid request, Data does not exist.")

        if "CUSTOMER_ID" in inv_row:
            new_cid = assert_customer_exists(conn, g("CUSTOMER_ID"))
            conn.execute(
                "UPDATE invoices_business SET customer_id=? WHERE id=?",
                (new_cid, inv_id),
            )
        if "ORDER_ID" in inv_row:
            raw_new_order = g("ORDER_ID")
            new_order: int | None = None
            if raw_new_order is not None and str(raw_new_order).strip() != "":
                new_order = assert_order_exists(conn, raw_new_order)
                # `exclude_invoice_id` so this invoice doesn't trip the rule
                # against itself.
                assert_no_existing_invoice(conn, new_order, exclude_invoice_id=inv_id)
            conn.execute(
                "UPDATE invoices_business SET order_id=? WHERE id=?",
                (new_order, inv_id),
            )
        if "AMOUNT" in inv_row:
            conn.execute(
                "UPDATE invoices_business SET amount=? WHERE id=?",
                (float(g("AMOUNT") or 0.0), inv_id),
            )
        if "STATUS" in inv_row:
            conn.execute(
                "UPDATE invoices_business SET status=? WHERE id=?",
                (str(g("STATUS") or "unpaid"), inv_id),
            )

    conn.commit()
    return {"success": True, "id": str(inv_id)}


def del_invoice(conn: sqlite3.Connection, key: Any) -> dict[str, Any]:
    cur = delete_with_fk_guard(
        conn, "DELETE FROM invoices_business WHERE id = ?", (int(key),),
        what=f"invoice {int(key)}",
    )
    if cur.rowcount == 0:
        raise WsError(WS_NOT_FOUND, "Invalid request, Data does not exist.")
    conn.commit()
    return {"success": True}
