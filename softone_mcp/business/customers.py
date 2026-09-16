"""
Customer business logic.

Layer contract:
    - Return raw payload dicts. No {ok, data} envelope.
    - Raise domain exceptions on business-rule violations
      (e.g. CustomerNotFoundError, ValueError for bad inputs).
    - Let SoftOneError propagate for anything the agent layer should surface as-is
      (auth failures, transport errors, unknown SoftOne error codes, etc.).
"""
from __future__ import annotations

from typing import Any

from .ports import CustomerRepository
from .exceptions import CustomerNotFoundError
from .translate import translate_softone_not_found


def create_customer_bl(
    customers: CustomerRepository,
    code: str,
    name: str,
    **optional_fields: Any,
) -> dict[str, Any]:
    """Create a customer after validating required fields."""
    if not code.strip() or not name.strip():
        raise ValueError("Customer code and name are required")
    return customers.create(code=code, name=name, **optional_fields)


def get_customer_bl(
    customers: CustomerRepository,
    key: int,
    locateinfo: str = "",
) -> dict[str, Any]:
    """
    Fetch a customer by id.

    Translates SoftOne's "data does not exist" (and empty-result payloads) into
    `CustomerNotFoundError` so callers can handle "not found" uniformly.
    """
    response = translate_softone_not_found(
        lambda: customers.get(key=key, locateinfo=locateinfo),
        exc_factory=lambda: CustomerNotFoundError(key),
    )

    # Some SoftOne responses are `success=True` with an empty CUSTOMER list.
    rows = ((response.get("data") or {}).get("CUSTOMER")) or []
    if not rows:
        raise CustomerNotFoundError(key)

    return response


def update_customer_bl(
    customers: CustomerRepository,
    key: int,
    **fields: Any,
) -> dict[str, Any]:
    """Patch a customer. Empty patches are allowed (no-op)."""
    return customers.update(key=key, **fields)


def delete_customer_bl(
    customers: CustomerRepository,
    key: int,
) -> dict[str, Any]:
    """Delete a customer by id. Propagates SoftOneError on failure."""
    return customers.delete(key=key)


def search_customers_bl(
    customers: CustomerRepository,
    *,
    q: str,
    limit: int | None = None,
) -> dict[str, Any]:
    q = q.strip()
    # In the mock backend, allow empty q as a convenience for "list customers".
    # In non-mock mode, the underlying client still rejects this to avoid
    # accidental reliance on mock-only listing behavior.
    rows = customers.search(q=q, limit=limit)
    return {"q": q, "customers": rows, "limit": limit}
