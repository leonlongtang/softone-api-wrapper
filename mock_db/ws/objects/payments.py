"""PAYMENT object handlers.

Side effect: every set/del recomputes the parent invoice's `status` from
`SUM(payments.amount)` so callers see consistent paid/partial/unpaid values
without having to drive that themselves.
"""
from __future__ import annotations

import sqlite3
from typing import Any

from ..errors import WsError, WS_INVALID_REQUEST, WS_NOT_FOUND
from .validators import delete_with_fk_guard


def _refresh_invoice_status(conn: sqlite3.Connection, invoice_id: int) -> None:
    """Recompute the invoice status from the sum of its payments.

    Called after every payment change. The schema CHECK constraint allows
    only 'unpaid' / 'partial' / 'paid'; this function only ever writes those.
    """
    inv = conn.execute(
        "SELECT amount FROM invoices_business WHERE id=?", (invoice_id,)
    ).fetchone()
    if inv is None:
        return
    (paid_sum,) = conn.execute(
        "SELECT COALESCE(SUM(amount), 0) AS paid_sum FROM payments WHERE invoice_id=?",
        (invoice_id,),
    ).fetchone()
    due = float(inv["amount"])
    ps = float(paid_sum)
    if ps >= due and due > 0:
        status = "paid"
    elif ps > 0:
        status = "partial"
    else:
        status = "unpaid"
    conn.execute(
        "UPDATE invoices_business SET status=? WHERE id=?", (status, invoice_id)
    )


def get_payment(conn: sqlite3.Connection, key: Any) -> dict[str, Any]:
    pay = conn.execute(
        "SELECT id, invoice_id, amount, payment_date FROM payments WHERE id = ?",
        (int(key),),
    ).fetchone()
    if pay is None:
        raise WsError(WS_NOT_FOUND, "Invalid request, Data does not exist.")
    data = {
        "PAYMENT": [
            {
                "ID": pay["id"],
                "INVOICE_ID": pay["invoice_id"],
                "AMOUNT": pay["amount"],
                "PAYMENT_DATE": pay["payment_date"],
            }
        ]
    }
    return {"success": True, "readOnly": True, "data": data}


def set_payment(conn: sqlite3.Connection, key: Any, data: dict[str, Any]) -> dict[str, Any]:
    pay_rows = data.get("PAYMENT") or []
    if not pay_rows:
        raise WsError(WS_INVALID_REQUEST, "Invalid Request. Ensure that your request is valid")
    pay_row = pay_rows[0]

    def g(field: str) -> Any:
        return pay_row.get(field)

    if key is None or str(key).strip() == "":
        invoice_id = int(g("INVOICE_ID") or 0)
        if invoice_id == 0:
            raise WsError(WS_INVALID_REQUEST, "Invalid Request. Ensure that your request is valid")
        (mx,) = conn.execute("SELECT COALESCE(MAX(id), 0) + 1 AS next_id FROM payments").fetchone()
        pay_id = int(mx)
        conn.execute(
            "INSERT INTO payments(id, invoice_id, amount, payment_date) "
            "VALUES (?,?,?,COALESCE(?, CURRENT_TIMESTAMP))",
            (pay_id, invoice_id, float(g("AMOUNT") or 0.0), g("PAYMENT_DATE")),
        )
        _refresh_invoice_status(conn, invoice_id)
    else:
        pay_id = int(key)
        existing = conn.execute(
            "SELECT invoice_id FROM payments WHERE id=?", (pay_id,)
        ).fetchone()
        if existing is None:
            raise WsError(WS_NOT_FOUND, "Invalid request, Data does not exist.")
        invoice_id = int(existing["invoice_id"])
        if "AMOUNT" in pay_row:
            conn.execute(
                "UPDATE payments SET amount=? WHERE id=?",
                (float(g("AMOUNT") or 0.0), pay_id),
            )
        if "PAYMENT_DATE" in pay_row:
            conn.execute(
                "UPDATE payments SET payment_date=? WHERE id=?",
                (str(g("PAYMENT_DATE") or ""), pay_id),
            )
        _refresh_invoice_status(conn, invoice_id)

    conn.commit()
    return {"success": True, "id": str(pay_id)}


def del_payment(conn: sqlite3.Connection, key: Any) -> dict[str, Any]:
    """Delete a payment + refresh its parent invoice's status.

    Note: payments don't reference any further child rows, so the FK guard
    here will never actually fire -- but using it keeps every del_X path
    uniform.
    """
    ex = conn.execute(
        "SELECT invoice_id FROM payments WHERE id=?", (int(key),)
    ).fetchone()
    if ex is None:
        raise WsError(WS_NOT_FOUND, "Invalid request, Data does not exist.")
    invoice_id = int(ex["invoice_id"])

    cur = delete_with_fk_guard(
        conn, "DELETE FROM payments WHERE id = ?", (int(key),),
        what=f"payment {int(key)}",
    )
    if cur.rowcount == 0:
        raise WsError(WS_NOT_FOUND, "Invalid request, Data does not exist.")

    _refresh_invoice_status(conn, invoice_id)
    conn.commit()
    return {"success": True}
