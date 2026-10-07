"""
Internal CRUD helpers for the PAYMENT object.

Layer contract:
    - Return raw payloads. No MCP envelope.
    - Let SoftOneError propagate.
"""
from __future__ import annotations

from typing import Any

from softone_wrapper import SoftOneClient
from softone_wrapper.domain.errors import SoftOneError

SOFTONE_BAD_INPUT_CODE = -9


def payments_create(
    client: SoftOneClient,
    session_id: str,
    invoice_id: int,
    amount: float,
    payment_date: str = "",
) -> dict[str, Any]:
    """Create a PAYMENT row and return SoftOne's raw setData response."""
    row: dict[str, Any] = {
        "INVOICE_ID": int(invoice_id),
        "AMOUNT": float(amount),
    }
    if payment_date.strip():
        row["PAYMENT_DATE"] = payment_date

    return client.setData(
        session_id=session_id,
        OBJECT="PAYMENT",
        KEY=None,
        data={"PAYMENT": [row]},
    )


def payments_get(
    client: SoftOneClient,
    session_id: str,
    key: int,
) -> dict[str, Any]:
    """Fetch a PAYMENT by id. Returns SoftOne's raw getData response."""
    return client.getData(
        session_id=session_id,
        OBJECT="PAYMENT",
        KEY=key,
        FORM="",
    )


def payments_delete(
    client: SoftOneClient,
    session_id: str,
    key: int,
) -> dict[str, Any]:
    """Delete a PAYMENT by id. Returns SoftOne's raw delData response."""
    return client.delData(
        session_id=session_id,
        OBJECT="PAYMENT",
        KEY=key,
        FORM="",
    )


def payments_list_for_invoice(
    client: SoftOneClient,
    session_id: str,
    invoice_id: int,
) -> list[dict[str, Any]]:
    """
    List every PAYMENT row attached to an invoice.

    Mock-only. In live mode this raises SoftOneError — the real SoftOne WS
    doesn't expose a "list payments by invoice" endpoint in the same shape,
    and the business layer should be updated once we know the real one.

    Returned shape:
        [{"id": int, "invoice_id": int, "amount": float, "payment_date": str}]
    """
    try:
        return client.list_payments_for_invoice(
            session_id=session_id,
            invoice_id=int(invoice_id),
        )
    except SoftOneError:
        # Preserve the historical error contract for this helper.
        raise
