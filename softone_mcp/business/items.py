"""
Item business logic.

Layer contract:
    - Return raw payload dicts. No {ok, data} envelope.
    - Raise domain exceptions on business-rule violations
      (e.g. ItemNotFoundError, ValueError for bad inputs).
    - Let SoftOneError propagate for anything the agent layer should surface as-is
      (auth failures, transport errors, unknown SoftOne error codes, etc.).
"""
from __future__ import annotations

from typing import Any

from .exceptions import ItemNotFoundError
from .ports import ItemRepository
from .translate import translate_softone_not_found


def create_item_bl(
    items: ItemRepository,
    code: str,
    name: str,
    **optional_fields: Any,
) -> dict[str, Any]:
    """Create a item after validating required fields."""
    if not code.strip() or not name.strip():
        raise ValueError("Item code and name are required")
    return items.create(code=code, name=name, **optional_fields)


def get_item_bl(
    items: ItemRepository,
    key: int,
    locateinfo: str = "",
) -> dict[str, Any]:
    """
    Fetch a item by id.

    Translates SoftOne's "data does not exist" (and empty-result payloads) into
    `ItemNotFoundError` so callers can handle "not found" uniformly.
    """
    response = translate_softone_not_found(
        lambda: items.get(key=key, locateinfo=locateinfo),
        exc_factory=lambda: ItemNotFoundError(key),
    )

    # Some SoftOne responses are `success=True` with an empty ITEM list.
    rows = ((response.get("data") or {}).get("ITEM")) or []
    if not rows:
        raise ItemNotFoundError(key)

    return response


def update_item_bl(
    items: ItemRepository,
    key: int,
    **fields: Any,
) -> dict[str, Any]:
    """Patch an item. Empty patches are allowed (no-op)."""
    return items.update(key=key, **fields)


def delete_item_bl(
    items: ItemRepository,
    key: int,
) -> dict[str, Any]:
    """Delete an item by id. Propagates SoftOneError on failure."""
    return items.delete(key=key)


def get_stock_balance_bl(
    items: ItemRepository,
    *,
    key: int,
) -> dict[str, Any]:
    """
    Return stock/reserved/available for an item.

    Raises ItemNotFoundError if the item does not exist.
    """
    snap = translate_softone_not_found(
        lambda: items.get_snapshot(key=key),
        exc_factory=lambda: ItemNotFoundError(key),
    )
    stock = int(snap.get("stock") or 0)
    reserved = int(snap.get("reserved") or 0)
    return {
        "item_id": int(snap.get("id") or key),
        "stock": stock,
        "reserved": reserved,
        "available": max(0, stock - reserved),
    }


def inventory_adjustment_bl(
    items: ItemRepository,
    *,
    key: int,
    delta_qty: int,
) -> dict[str, Any]:
    """
    Adjust an item's stock by delta_qty with safety guards.

    Guards:
    - Stock cannot go negative.
    - Stock cannot drop below RESERVED (otherwise availability becomes negative).
    """
    bal = get_stock_balance_bl(items, key=key)
    stock = int(bal["stock"])
    reserved = int(bal["reserved"])

    new_stock = stock + int(delta_qty)
    if new_stock < 0:
        raise ValueError("Adjustment would make stock negative")
    if new_stock < reserved:
        raise ValueError("Adjustment would make stock less than reserved")

    items.update(key=key, stock=str(new_stock))
    return {
        "item_id": bal["item_id"],
        "prev_stock": stock,
        "new_stock": new_stock,
        "reserved": reserved,
        "available": max(0, new_stock - reserved),
        "delta_qty": int(delta_qty),
    }


def search_items_bl(
    items: ItemRepository,
    *,
    q: str,
    limit: int | None = None,
) -> dict[str, Any]:
    q = q.strip()
    if not q:
        raise ValueError("q is required")
    rows = items.search(q=q, limit=limit)
    return {"q": q, "items": rows, "limit": limit}
