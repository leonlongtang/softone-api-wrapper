"""
Internal CRUD helpers for the ITEM object.

Layer contract:
    - Return the raw payload that `SoftOneClient` returns. No MCP envelope.
    - Raise SoftOneError on any SoftOne-level failure (just let it propagate).
    - Never import or call ok()/err(). The envelope is owned by agent_tools.
"""
from __future__ import annotations

from typing import Any

from softone_wrapper import SoftOneClient


ITEM_OPTIONAL_KEYS: tuple[str, ...] = (
    "price",
    "stock",
)


def items_create(
    client: SoftOneClient,
    session_id: str,
    code: str,
    name: str,
    **optional_fields: Any,
) -> dict[str, Any]:
    """Create a item and return SoftOne's raw setData response."""
    item_row: dict[str, Any] = {"CODE": code, "NAME": name}
    for key in ITEM_OPTIONAL_KEYS:
        value = optional_fields.get(key, "")
        if isinstance(value, str):
            value = value.strip()
        if value in (None, ""):
            continue
        item_row[key.upper()] = value

    return client.setData(
        session_id=session_id,
        OBJECT="ITEM",
        KEY=None,
        data={"ITEM": [item_row]},
    )


def items_get(
    client: SoftOneClient,
    session_id: str,
    key: int,
    locateinfo: str = "",
) -> dict[str, Any]:
    """Fetch a item by id and return SoftOne's raw getData response."""
    return client.getData(
        session_id=session_id,
        OBJECT="ITEM",
        KEY=key,
        FORM="",
        LOCATEINFO=locateinfo,
    )


def items_update(
    client: SoftOneClient,
    session_id: str,
    key: int,
    **fields: Any,
) -> dict[str, Any]:
    """Patch a item. Returns SoftOne's raw setData response."""
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
        OBJECT="ITEM",
        KEY=str(key),
        data={"ITEM": [patch]},
    )


def items_delete(
    client: SoftOneClient,
    session_id: str,
    key: int,
) -> dict[str, Any]:
    """Delete a item by id. Returns SoftOne's raw delData response."""
    return client.delData(
        session_id=session_id,
        OBJECT="ITEM",
        KEY=key,
        FORM="",
    )


def items_search(
    client: SoftOneClient,
    session_id: str,
    *,
    q: str,
    limit: int | None = None,
) -> list[dict[str, Any]]:
    """
    Search items by name/code (mock-only for now).

    Delegates to `SoftOneClient.search_items`, which raises SoftOneError
    in non-mock mode to prevent accidental reliance on mock-only behavior.
    """
    return client.search_items(session_id=session_id, q=q, limit=limit)
