"""
Internal CRUD helpers for the INVOICE object.

Layer contract:
    - Return raw payloads. No MCP envelope.
    - Let SoftOneError propagate.
    - `invoices_get` supports a mock-only `filter={...}` branch that queries the
      `invoices_business` table directly (useful for "list unpaid invoices"
      style tools). In non-mock mode, the filter branch raises SoftOneError.
"""
from __future__ import annotations

from typing import Any

from softone_wrapper import SoftOneClient
from softone_wrapper.domain.errors import SoftOneError

SOFTONE_BAD_INPUT_CODE = -9


def invoices_create(
    client: SoftOneClient,
    session_id: str,
    customer_id: int,
    amount: float,
    order_id: int | None = None,
    status: str = "",
) -> dict[str, Any]:
    """
    Create an INVOICE row and return SoftOne's raw setData response.

    Mock-backed columns: (customer_id, order_id, amount, status). Anything else
    is ignored by the mock backend.
    """
    row: dict[str, Any] = {"CUSTOMER_ID": int(customer_id), "AMOUNT": float(amount)}
    if order_id is not None:
        row["ORDER_ID"] = int(order_id)
    if status.strip():
        row["STATUS"] = status

    return client.setData(
        session_id=session_id,
        OBJECT="INVOICE",
        KEY=None,
        data={"INVOICE": [row]},
    )


def invoices_get(
    client: SoftOneClient,
    session_id: str,
    key: int | None = None,
    *,
    filter: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """
    Fetch a single invoice (by id) or list invoices in mock mode (via filter).

    - If `key` is provided: returns SoftOne's raw getData response
      (`{"success": True, "data": {"INVOICE": [...]}}`).
    - If `filter` is provided: mock-only — returns
      `{"invoices": [...], "filter": {...}}` by querying `invoices_business`.
      Raises SoftOneError in non-mock mode.
    """
    if filter is not None:
        status = (filter.get("status") or "").strip()
        customer_id = filter.get("customer_id")
        invoices = client.list_invoices(
            session_id=session_id,
            status=status,
            customer_id=int(customer_id) if customer_id is not None else None,
        )
        return {"invoices": invoices, "filter": {"status": status, "customer_id": customer_id}}

    if key is None:
        raise SoftOneError(
            SOFTONE_BAD_INPUT_CODE,
            "Invalid request. Provide `key` or `filter`.",
            {},
        )

    return client.getData(
        session_id=session_id,
        OBJECT="INVOICE",
        KEY=key,
        FORM="",
    )


def invoices_update(
    client: SoftOneClient,
    session_id: str,
    key: int,
    **fields: Any,
) -> dict[str, Any]:
    """Patch an INVOICE. Empty patches return a synthetic no-op response."""
    patch: dict[str, Any] = {}
    for k, v in fields.items():
        if isinstance(v, str):
            v = v.strip()
            if not v:
                continue
        elif v is None:
            continue
        patch[k.upper()] = v

    if not patch:
        return {
            "success": True,
            "id": str(key),
            "note": "No fields provided; nothing to update.",
        }

    return client.setData(
        session_id=session_id,
        OBJECT="INVOICE",
        KEY=str(key),
        data={"INVOICE": [patch]},
    )


def invoices_delete(
    client: SoftOneClient,
    session_id: str,
    key: int,
) -> dict[str, Any]:
    """Delete an INVOICE by id. Returns SoftOne's raw delData response."""
    return client.delData(
        session_id=session_id,
        OBJECT="INVOICE",
        KEY=key,
        FORM="",
    )
