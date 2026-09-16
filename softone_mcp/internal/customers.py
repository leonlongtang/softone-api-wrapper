"""
Internal CRUD helpers for the CUSTOMER object.

Layer contract:
    - Return the raw payload that `SoftOneClient` returns. No MCP envelope.
    - Raise SoftOneError on any SoftOne-level failure (just let it propagate).
    - Never import or call ok()/err(). The envelope is owned by agent_tools.
"""
from __future__ import annotations

from typing import Any

from softone_wrapper import SoftOneClient


CUSTOMER_OPTIONAL_KEYS: tuple[str, ...] = (
    "afm",
    "email",
    "phone",
    "address",
    "balance",
    "created_at",
)


def customers_search(
    client: SoftOneClient,
    session_id: str,
    *,
    q: str,
    limit: int | None = None,
) -> list[dict[str, Any]]:
    """
    Search customers by name/code/afm (mock-only for now).

    Delegates to `SoftOneClient.search_customers`, which raises SoftOneError
    in non-mock mode to prevent accidental reliance on mock-only behavior.
    """
    return client.search_customers(session_id=session_id, q=q, limit=limit)


def customers_create(
    client: SoftOneClient,
    session_id: str,
    code: str,
    name: str,
    **optional_fields: Any,
) -> dict[str, Any]:
    """Create a customer and return SoftOne's raw setData response."""
    customer_row: dict[str, Any] = {"CODE": code, "NAME": name}
    for key in CUSTOMER_OPTIONAL_KEYS:
        value = optional_fields.get(key, "")
        if isinstance(value, str):
            value = value.strip()
        if value in (None, ""):
            continue
        customer_row[key.upper()] = value

    return client.setData(
        session_id=session_id,
        OBJECT="CUSTOMER",
        KEY=None,
        data={"CUSTOMER": [customer_row]},
    )


def customers_get(
    client: SoftOneClient,
    session_id: str,
    key: int,
    locateinfo: str = "",
) -> dict[str, Any]:
    """Fetch a customer by id and return SoftOne's raw getData response."""
    return client.getData(
        session_id=session_id,
        OBJECT="CUSTOMER",
        KEY=key,
        FORM="",
        LOCATEINFO=locateinfo,
    )


def customers_update(
    client: SoftOneClient,
    session_id: str,
    key: int,
    **fields: Any,
) -> dict[str, Any]:
    """Patch a customer. Returns SoftOne's raw setData response."""
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
        # Nothing to send — mimic a no-op success so callers don't need to special-case.
        return {
            "success": True,
            "id": str(key),
            "note": "No fields provided; nothing to update.",
        }

    return client.setData(
        session_id=session_id,
        OBJECT="CUSTOMER",
        KEY=str(key),
        data={"CUSTOMER": [patch]},
    )


def customers_delete(
    client: SoftOneClient,
    session_id: str,
    key: int,
) -> dict[str, Any]:
    """Delete a customer by id. Returns SoftOne's raw delData response."""
    return client.delData(
        session_id=session_id,
        OBJECT="CUSTOMER",
        KEY=key,
        FORM="",
    )
