"""
Internal CRUD helpers for the ORDER object.

Layer contract:
    - `orders_create/update/delete` return raw SoftOne responses.
    - `orders_get` returns SoftOne's raw getData response.
    - `orders_get_normalized` is a convenience helper that flattens the raw
      response into an adapter/business-friendly dict.
    - Let SoftOneError propagate.
"""
from __future__ import annotations

from typing import Any

from softone_wrapper import SoftOneClient


def orders_list(
    client: SoftOneClient,
    session_id: str,
    *,
    filter: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """
    List orders (mock-only for now).

    In mock mode, delegates to `SoftOneClient.list_orders` which queries the
    sqlite DB directly. In non-mock mode, `SoftOneClient` raises SoftOneError.
    """
    filter = filter or {}
    status = (filter.get("status") or "").strip()
    customer_id = filter.get("customer_id")
    limit = filter.get("limit")

    orders = client.list_orders(
        session_id=session_id,
        status=status,
        customer_id=int(customer_id) if customer_id is not None else None,
        limit=int(limit) if limit is not None else None,
    )
    return {"orders": orders, "filter": {"status": status, "customer_id": customer_id, "limit": limit}}


def orders_create(
    client: SoftOneClient,
    session_id: str,
    customer_id: int,
    status: str = "",
    lines: list[dict[str, int | float]] | None = None,
    **fields: Any,
) -> dict[str, Any]:
    """
    Create an ORDER header (and optionally ORDERITEMS in the same call).

    Business layer is free to pass extra header fields (e.g. order_date, total,
    notes) via **fields — empty strings / None are dropped.
    """
    order_row: dict[str, Any] = {"CUSTOMER_ID": customer_id}
    if status.strip():
        order_row["STATUS"] = status

    for k, v in fields.items():
        if v is None:
            continue
        if isinstance(v, str) and not v.strip():
            continue
        order_row[k.upper()] = v

    data: dict[str, Any] = {"ORDER": [order_row]}
    if lines:
        data["ORDERITEMS"] = [
            {
                "PRODUCT_ID": int(line["product_id"]),
                "QUANTITY": int(line["quantity"]),
                **({"PRICE": float(line["price"])} if "price" in line else {}),
            }
            for line in lines
        ]

    return client.setData(
        session_id=session_id,
        OBJECT="ORDER",
        KEY=None,
        data=data,
    )


def orders_get(
    client: SoftOneClient,
    session_id: str,
    key: int,
) -> dict[str, Any]:
    """
    Fetch an ORDER and return SoftOne's raw getData response.

    Raises SoftOneError(2001) if the order does not exist.
    """
    return client.getData(session_id=session_id, OBJECT="ORDER", KEY=key, FORM="")


def orders_get_normalized(
    client: SoftOneClient,
    session_id: str,
    key: int,
) -> dict[str, Any]:
    """
    Fetch an ORDER and return a normalized flat dict.

    Shape:
        {
          "id": int, "customer_id": int, "status": str, "total": float,
          "created_at": str,
          "lines": [{ "item_id", "quantity", "unit_price",
                      "product_code", "product_name" }, ...]
        }
    """
    resp = orders_get(client, session_id, key)
    data = resp.get("data") or {}
    header = ((data.get("ORDER") or [None])[0]) or {}
    raw_lines = list(data.get("ORDERITEMS") or [])

    return {
        "id": int(header.get("ID") or key),
        "customer_id": int(header.get("CUSTOMER_ID") or 0),
        "status": header.get("STATUS"),
        "total": float(header.get("TOTAL") or 0.0),
        "created_at": header.get("CREATED_AT") or "",
        "lines": [
            {
                "item_id": int(ln.get("PRODUCT_ID") or 0),
                "quantity": int(ln.get("QUANTITY") or 0),
                "unit_price": float(ln.get("PRICE") or 0.0),
                "product_code": ln.get("PRODUCT_CODE") or "",
                "product_name": ln.get("PRODUCT_NAME") or "",
            }
            for ln in raw_lines
        ],
    }


def orders_update(
    client: SoftOneClient,
    session_id: str,
    key: int,
    **fields: Any,
) -> dict[str, Any]:
    """Patch an ORDER header. Empty patches return a synthetic no-op response."""
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
        OBJECT="ORDER",
        KEY=str(key),
        data={"ORDER": [patch]},
    )


def orders_delete(
    client: SoftOneClient,
    session_id: str,
    key: int,
) -> dict[str, Any]:
    """Delete an ORDER by id. Returns SoftOne's raw delData response."""
    return client.delData(
        session_id=session_id,
        OBJECT="ORDER",
        KEY=key,
        FORM="",
    )
