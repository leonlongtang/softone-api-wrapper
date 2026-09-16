"""Business-rule validators ("the brain") used by setData / delData handlers.

A real SoftOne WS validates inputs before persisting -- it doesn't just shovel
rows into storage and let DB constraints fire. These helpers move that
SoftOne-like behavior into the mock so callers see clean WsError responses
instead of raw `sqlite3.IntegrityError` leaking through.

Each helper returns nothing on success and raises WsError on violation.

IMPORTANT: keep these *SoftOne-like* validations only -- field shape, status
vocabulary, FK existence, "already invoiced" guards. Company-policy logic
(auto-approve thresholds, payment terms, invoice generation rules) belongs
in `softone_mcp/business/`, not here.
"""
from __future__ import annotations

import sqlite3
from typing import Any

from ..errors import WsError, WS_BUSINESS_RULE, WS_FK_BLOCKED


# Allowed order status vocabulary + legal transitions. Mirrors the schema's
# CHECK constraint, but enforced earlier so callers get a structured error
# rather than a CHECK-constraint exception. 'Confirmed' -> 'Draft' is
# explicitly disallowed: real ERPs don't let you un-confirm an order; you'd
# cancel it instead.
ALLOWED_ORDER_STATUSES: tuple[str, ...] = ("Draft", "Confirmed")
ALLOWED_ORDER_TRANSITIONS: frozenset[tuple[str, str]] = frozenset({
    ("Draft", "Draft"),
    ("Draft", "Confirmed"),
    ("Confirmed", "Confirmed"),
})


def assert_customer_exists(conn: sqlite3.Connection, customer_id: Any) -> int:
    """Return the customer_id as int after confirming the row exists."""
    if customer_id is None or str(customer_id).strip() == "":
        raise WsError(WS_BUSINESS_RULE, "CUSTOMER_ID is required")
    cid = int(customer_id)
    if conn.execute("SELECT 1 FROM customers WHERE trdr = ?", (cid,)).fetchone() is None:
        raise WsError(WS_BUSINESS_RULE, f"Customer {cid} does not exist")
    return cid


def assert_order_exists(conn: sqlite3.Connection, order_id: Any) -> int:
    if order_id is None or str(order_id).strip() == "":
        raise WsError(WS_BUSINESS_RULE, "ORDER_ID is required")
    oid = int(order_id)
    if conn.execute("SELECT 1 FROM orders WHERE id = ?", (oid,)).fetchone() is None:
        raise WsError(WS_BUSINESS_RULE, f"Order {oid} does not exist")
    return oid


def assert_item_and_stock(
    conn: sqlite3.Connection, product_id: Any, qty: int
) -> None:
    """Validate that the product exists and has at least `qty` units in stock.

    Note: this is the *raw* stock check (qty <= items.stock), not a
    capacity-aware one (qty <= stock - reserved). The order-create flow
    reserves stock BEFORE lines arrive at setData ORDER, so a capacity check
    here would reject legitimate flows. The race-condition fix for the
    reservation layer belongs in `softone_mcp/business/orders.py`.
    """
    if product_id is None or str(product_id).strip() == "":
        raise WsError(WS_BUSINESS_RULE, "PRODUCT_ID is required on every order line")
    pid = int(product_id)
    row = conn.execute("SELECT stock FROM items WHERE id = ?", (pid,)).fetchone()
    if row is None:
        raise WsError(WS_BUSINESS_RULE, f"Item {pid} does not exist")
    if qty <= 0:
        raise WsError(WS_BUSINESS_RULE, f"Quantity must be positive on item {pid} (got {qty})")
    available = int(row["stock"])
    if qty > available:
        raise WsError(
            WS_BUSINESS_RULE,
            f"Insufficient stock for item {pid}: requested {qty}, available {available}",
        )


def assert_order_status_transition(current: str, new: str) -> None:
    if new not in ALLOWED_ORDER_STATUSES:
        raise WsError(
            WS_BUSINESS_RULE,
            f"Invalid order status '{new}'. Allowed: {list(ALLOWED_ORDER_STATUSES)}",
        )
    if (current, new) not in ALLOWED_ORDER_TRANSITIONS:
        raise WsError(
            WS_BUSINESS_RULE,
            f"Illegal order status transition: {current} -> {new}",
        )


def assert_no_existing_invoice(
    conn: sqlite3.Connection,
    order_id: int | None,
    *,
    exclude_invoice_id: int | None = None,
) -> None:
    """Reject if `order_id` is already invoiced.

    NULL order_id is allowed (ad-hoc invoices). When updating, pass
    `exclude_invoice_id` so the invoice doesn't trip the rule against itself.
    """
    if order_id is None:
        return
    if exclude_invoice_id is None:
        row = conn.execute(
            "SELECT id FROM invoices_business WHERE order_id = ?",
            (int(order_id),),
        ).fetchone()
    else:
        row = conn.execute(
            "SELECT id FROM invoices_business WHERE order_id = ? AND id != ?",
            (int(order_id), int(exclude_invoice_id)),
        ).fetchone()
    if row is not None:
        raise WsError(
            WS_BUSINESS_RULE,
            f"Order {order_id} has already been invoiced (invoice {row['id']})",
        )


def delete_with_fk_guard(
    conn: sqlite3.Connection, sql: str, params: tuple, *, what: str
) -> sqlite3.Cursor:
    """Run a DELETE; convert FK violations into WsError(WS_FK_BLOCKED) so
    callers get a structured "row is referenced" error instead of a raw
    IntegrityError.
    """
    try:
        return conn.execute(sql, params)
    except sqlite3.IntegrityError:
        raise WsError(
            WS_FK_BLOCKED,
            f"Cannot delete {what}: it is referenced by other records",
        )
