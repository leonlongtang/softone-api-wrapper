"""
Payment business logic.

Layer contract:
    - Return raw payload dicts.
    - Raise domain exceptions on business-rule violations:
        * ValueError for non-positive amounts.
        * InvoiceNotFoundError when the target invoice doesn't exist.
        * InvoiceAlreadyPaidError when outstanding balance is 0.
        * PaymentExceedsBalanceError when amount > outstanding.
        * PaymentNotFoundError for missing payments on read/delete.
    - Let SoftOneError propagate for anything else.

Payment policy (strict): once an invoice is `paid`, no more payments are
accepted — refund an existing payment first. A single payment may never
exceed the invoice's outstanding balance (no implicit over-payments / credit
accounts). Loosen this here if your business rules allow partial over-pay.
"""
from __future__ import annotations

from typing import Any

from .exceptions import (
    InvoiceAlreadyPaidError,
    PaymentExceedsBalanceError,
    PaymentNotFoundError,
)
from .invoices import get_invoice_bl
from .ports import InvoiceRepository, PaymentRepository
from .translate import translate_softone_not_found


def _invoice_outstanding_balance(
    invoices: InvoiceRepository,
    payments: PaymentRepository,
    invoice_id: int,
) -> tuple[dict[str, Any], float]:
    """
    Fetch the invoice and compute its outstanding balance.

    Returns (invoice, outstanding). `outstanding` is rounded to 2 decimals and
    clamped at 0 — over-payments that somehow slipped in historically will
    surface as `outstanding == 0` rather than a negative number.

    Raises InvoiceNotFoundError if the invoice doesn't exist.
    """
    invoice = get_invoice_bl(invoices, invoice_id)
    rows = payments.list_for_invoice(invoice_id=invoice_id)
    paid_sum = sum(p["amount"] for p in rows)
    outstanding = max(0.0, round(float(invoice["amount"]) - paid_sum, 2))
    return invoice, outstanding


def record_payment_bl(
    invoices: InvoiceRepository,
    payments: PaymentRepository,
    invoice_id: int,
    amount: float,
    payment_date: str = "",
) -> dict[str, Any]:
    """
    Record a payment against an invoice.

    Enforces the strict policy:
      1. amount must be positive.
      2. invoice must exist.
      3. invoice must not already be fully paid.
      4. amount must not exceed the outstanding balance.

    The mock backend automatically refreshes the invoice status
    (unpaid → partial → paid) based on sum(payments) after the insert.

    Raises:
        ValueError, InvoiceNotFoundError, InvoiceAlreadyPaidError,
        PaymentExceedsBalanceError.
    """
    if amount <= 0:
        raise ValueError("Payment amount must be positive")

    _invoice, outstanding = _invoice_outstanding_balance(
        invoices, payments, invoice_id
    )

    if outstanding <= 0:
        raise InvoiceAlreadyPaidError(invoice_id)

    if amount > outstanding:
        raise PaymentExceedsBalanceError(invoice_id, amount, outstanding)

    return payments.create(invoice_id=invoice_id, amount=amount, payment_date=payment_date)


def get_payment_bl(
    payments: PaymentRepository,
    key: int,
) -> dict[str, Any]:
    """
    Fetch a single payment by ID.

    Translates SoftOne's "data does not exist" into PaymentNotFoundError.
    """
    return translate_softone_not_found(
        lambda: payments.get(payment_id=key),
        exc_factory=lambda: PaymentNotFoundError(key),
    )


def list_payments_for_invoice_bl(
    invoices: InvoiceRepository,
    payments: PaymentRepository,
    invoice_id: int,
) -> dict[str, Any]:
    """
    List payments recorded against an invoice.

    Raises InvoiceNotFoundError if the invoice does not exist.
    """
    get_invoice_bl(invoices, invoice_id)
    rows = payments.list_for_invoice(invoice_id=invoice_id)
    return {"invoice_id": invoice_id, "payments": rows}


def delete_payment_bl(
    payments: PaymentRepository,
    key: int,
) -> dict[str, Any]:
    """
    Delete (refund) a payment. The mock backend rolls the invoice status back.

    Raises PaymentNotFoundError if the payment does not exist.
    """
    return translate_softone_not_found(
        lambda: payments.delete(payment_id=key),
        exc_factory=lambda: PaymentNotFoundError(key),
    )
