"""
Internal CRUD helpers for ORDERITEMS (the lines attached to an ORDER).

Layer contract:
    - Return raw payloads. No MCP envelope.
    - Let SoftOneError propagate.
    - Raise ValueError for malformed numeric inputs.
"""
from __future__ import annotations

from typing import Any

from softone_wrapper import SoftOneClient


def _line_to_softone_row(line: dict[str, Any]) -> dict[str, Any]:
    """Convert a business-layer line dict to a SoftOne ORDERITEMS row."""
    row: dict[str, Any] = {
        "PRODUCT_ID": int(line["product_id"]),
        "QUANTITY": int(line["quantity"]),
    }
    price = str(line.get("price") or "").strip()
    if price:
        row["PRICE"] = float(price)
    return row


def orderitems_replace_lines(
    client: SoftOneClient,
    session_id: str,
    order_id: int,
    lines: list[dict[str, Any]],
) -> dict[str, Any]:
    """Replace all ORDERITEMS for an order with the given lines."""
    payload = {
        "ORDER": [{}],
        "ORDERITEMS": [_line_to_softone_row(ln) for ln in lines],
    }
    return client.setData(
        session_id=session_id,
        OBJECT="ORDER",
        KEY=str(order_id),
        data=payload,
    )


def orderitems_add_line(
    client: SoftOneClient,
    session_id: str,
    order_id: int,
    line: dict[str, Any] | None = None,
    merge_if_exists: bool = True,
    **fields: Any,
) -> dict[str, Any]:
    """
    Append (or merge) a single line to an order's ORDERITEMS.

    Accepts either:
      - `line`: a dict with keys {product_id, quantity, price?}.
      - Keyword args `item_id`/`product_id`, `quantity`, `unit_price`/`price`
        (business-layer convenience).
    """
    if line is None:
        if "item_id" in fields:
            fields["product_id"] = fields.pop("item_id")
        if "unit_price" in fields and "price" not in fields:
            fields["price"] = fields.pop("unit_price")
        if "product_id" not in fields or "quantity" not in fields:
            raise ValueError(
                "orderitems_add_line requires either `line` or "
                "(`item_id`/`product_id` and `quantity`)."
            )
        line = {
            "product_id": fields["product_id"],
            "quantity": fields["quantity"],
            "price": fields.get("price", ""),
        }

    cur = client.getData(session_id=session_id, OBJECT="ORDER", KEY=order_id, FORM="")
    existing_lines = list(((cur.get("data") or {}).get("ORDERITEMS")) or [])

    # Build a mutable normalized list from existing rows.
    norm: list[dict[str, Any]] = [
        {
            "PRODUCT_ID": int(r.get("PRODUCT_ID") or 0),
            "QUANTITY": int(r.get("QUANTITY") or 0),
            "PRICE": float(r.get("PRICE") or 0.0),
        }
        for r in existing_lines
    ]

    new_row = _line_to_softone_row(line)

    if merge_if_exists:
        merged = False
        for r in norm:
            if int(r["PRODUCT_ID"]) == int(new_row["PRODUCT_ID"]):
                r["QUANTITY"] = int(r["QUANTITY"]) + int(new_row["QUANTITY"])
                if "PRICE" in new_row:
                    r["PRICE"] = float(new_row["PRICE"])
                merged = True
                break
        if not merged:
            norm.append(
                {
                    "PRODUCT_ID": int(new_row["PRODUCT_ID"]),
                    "QUANTITY": int(new_row["QUANTITY"]),
                    **({"PRICE": float(new_row["PRICE"])} if "PRICE" in new_row else {}),
                }
            )
    else:
        norm.append(
            {
                "PRODUCT_ID": int(new_row["PRODUCT_ID"]),
                "QUANTITY": int(new_row["QUANTITY"]),
                **({"PRICE": float(new_row["PRICE"])} if "PRICE" in new_row else {}),
            }
        )

    out_lines: list[dict[str, Any]] = []
    for r in norm:
        row = {"PRODUCT_ID": int(r["PRODUCT_ID"]), "QUANTITY": int(r["QUANTITY"])}
        if "PRICE" in r:
            row["PRICE"] = float(r["PRICE"])
        out_lines.append(row)

    payload = {"ORDER": [{}], "ORDERITEMS": out_lines}
    return client.setData(
        session_id=session_id,
        OBJECT="ORDER",
        KEY=str(order_id),
        data=payload,
    )


def orderitems_remove_line(
    client: SoftOneClient,
    session_id: str,
    order_id: int,
    product_id: int,
) -> dict[str, Any]:
    """Remove all ORDERITEMS rows for the given product on the given order."""
    cur = client.getData(session_id=session_id, OBJECT="ORDER", KEY=order_id, FORM="")
    existing_lines = list(((cur.get("data") or {}).get("ORDERITEMS")) or [])

    kept: list[dict[str, Any]] = []
    removed = 0
    for r in existing_lines:
        pid = int(r.get("PRODUCT_ID") or 0)
        if pid == int(product_id):
            removed += 1
            continue
        kept.append(
            {
                "PRODUCT_ID": pid,
                "QUANTITY": int(r.get("QUANTITY") or 0),
                "PRICE": float(r.get("PRICE") or 0.0),
            }
        )

    if removed == 0:
        # No-op: caller can interpret `note` as "nothing changed".
        return {
            "success": True,
            "id": str(order_id),
            "note": f"Product {product_id} not present; nothing removed.",
        }

    payload = {
        "ORDER": [{}],
        "ORDERITEMS": [
            {
                "PRODUCT_ID": int(r["PRODUCT_ID"]),
                "QUANTITY": int(r["QUANTITY"]),
                "PRICE": float(r["PRICE"]),
            }
            for r in kept
        ],
    }
    return client.setData(
        session_id=session_id,
        OBJECT="ORDER",
        KEY=str(order_id),
        data=payload,
    )


def orderitems_get_lines(
    client: SoftOneClient,
    session_id: str,
    order_id: int,
) -> list[dict[str, Any]]:
    """
    Return normalized order lines for an order.

    Business-layer friendly shape:
        [{ "item_id": int, "quantity": int, "unit_price": float }, ...]
    """
    cur = client.getData(session_id=session_id, OBJECT="ORDER", KEY=order_id, FORM="")
    raw_lines = list(((cur.get("data") or {}).get("ORDERITEMS")) or [])

    return [
        {
            "item_id": int(r.get("PRODUCT_ID") or 0),
            "quantity": int(r.get("QUANTITY") or 0),
            "unit_price": float(r.get("PRICE") or 0.0),
        }
        for r in raw_lines
    ]
