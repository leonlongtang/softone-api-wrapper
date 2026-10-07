"""
Invoice business logic.

Layer contract:
    - Return raw payload dicts (normalized where it helps agents consume them).
    - Raise domain exceptions on business-rule violations
      (OrderNotFoundError, InvalidOrderStatusError, InvoiceNotFoundError,
       InvalidPaymentTermsError).
    - Let SoftOneError propagate for anything else.
"""
from __future__ import annotations

from datetime import date, timedelta
from typing import Any

from .exceptions import (
    InvalidOrderStatusError,
    InvalidPaymentTermsError,
    InvoiceNotFoundError,
    OrderNotFoundError,
)
from .ports import InventoryService, InvoiceRepository, OrderRepository
from .translate import translate_softone_not_found

PAYMENT_TERMS_DAYS: dict[str, int] = {
    "due_on_receipt": 0,
    "net_30": 30,
    "net_60": 60,
    "net_90": 90,
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _resolve_due_date(payment_terms: str) -> str:
    """
    Convert payment terms to a concrete ISO due date.

    Raises InvalidPaymentTermsError for unknown terms.
    """
    terms = payment_terms.strip().lower()
    if terms not in PAYMENT_TERMS_DAYS:
        raise InvalidPaymentTermsError(payment_terms)
    return (date.today() + timedelta(days=PAYMENT_TERMS_DAYS[terms])).isoformat()


def _normalize_invoice(response: dict[str, Any]) -> dict[str, Any]:
    """Flatten a raw INVOICE getData response into an agent-friendly dict."""
    row = ((response.get("data") or {}).get("INVOICE") or [{}])[0]
    return {
        "id": int(row.get("ID") or 0),
        "customer_id": int(row.get("CUSTOMER_ID") or 0),
        "order_id": row.get("ORDER_ID"),
        "amount": float(row.get("AMOUNT") or 0.0),
        "status": row.get("STATUS") or "",
        "created_at": row.get("CREATED_AT") or "",
    }


# ---------------------------------------------------------------------------
# Business logic functions
# ---------------------------------------------------------------------------

def create_invoice_bl(
    orders: OrderRepository,
    invoices: InvoiceRepository,
    inventory: InventoryService,
    order_id: int,
    payment_terms: str = "net_30",
) -> dict[str, Any]:
    """
    Generate an invoice from a Confirmed order.

    Workflow:
      1. Fetch the order — must exist and be Confirmed.
      2. Resolve due date from payment_terms.
      3. Create the invoice row (customer_id + total come from the order).
      4. Deduct stock and release reservations.
      5. Return the normalized invoice with _meta attached.

    Raises:
        OrderNotFoundError, InvalidOrderStatusError, InvalidPaymentTermsError.
    """
    # 1. Validate order exists and is Confirmed.
    order = translate_softone_not_found(
        lambda: orders.get(order_id=order_id),
        exc_factory=lambda: OrderNotFoundError(order_id),
    )

    current_status = order.get("status")
    if current_status != "Confirmed":
        raise InvalidOrderStatusError(
            order_id, current_status or "None", "Confirmed"
        )

    # 2. Resolve due date (raises InvalidPaymentTermsError on unknown terms).
    due_date = _resolve_due_date(payment_terms)

    # 3. Create the invoice. Mock-backed columns are only
    #    (customer_id, order_id, amount, status) — terms/dates are tracked in
    #    _meta so the agent can still see them.
    invoice_id = invoices.create(
        customer_id=int(order["customer_id"]),
        amount=float(order["total"]),
        order_id=order_id,
        status="unpaid",
    )

    # 4. Deduct stock — stock truly leaves inventory at invoice time.
    inventory.deduct_for_order(order_id=order_id)

    # 5. Fetch, normalize, attach meta, return.
    invoice = _normalize_invoice(invoices.get(invoice_id=invoice_id))
    invoice["_meta"] = {
        "payment_terms": payment_terms,
        "due_date": due_date,
        "sourced_from_order": order_id,
    }
    return invoice


def get_unpaid_invoices_bl(
    invoices: InvoiceRepository,
    customer_id: int | None = None,
) -> dict[str, Any]:
    """
    Fetch all unpaid invoices, optionally filtered by customer.

    Delegates directly to the mock-only filter branch of `invoices_get`, which
    returns `{"invoices": [...], "filter": {...}}`. In non-mock mode, the
    internal layer raises SoftOneError and the agent layer surfaces it.
    """
    return invoices.list(filter={"status": "unpaid", "customer_id": customer_id})


def list_invoices_bl(
    invoices: InvoiceRepository,
    *,
    status: str = "",
    customer_id: int | None = None,
) -> dict[str, Any]:
    """
    List invoices (mock-only for now).

    Delegates to the mock-only filter branch of `invoices_get`.
    """
    return invoices.list(filter={"status": status, "customer_id": customer_id})


def get_invoice_bl(
    invoices: InvoiceRepository,
    invoice_id: int,
) -> dict[str, Any]:
    """
    Fetch a single invoice by ID (normalized).

    Raises InvoiceNotFoundError if the invoice does not exist.
    """
    response = translate_softone_not_found(
        lambda: invoices.get(invoice_id=invoice_id),
        exc_factory=lambda: InvoiceNotFoundError(invoice_id),
    )

    invoice = _normalize_invoice(response)
    if not invoice["id"]:
        # Rare: SoftOne returned success=True with an empty INVOICE list.
        raise InvoiceNotFoundError(invoice_id)
    return invoice
