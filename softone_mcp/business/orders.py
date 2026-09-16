"""
Order business logic.

Layer contract:
    - Return raw payload dicts (the normalized order from `orders_get`).
    - Raise domain exceptions on business-rule violations
      (OrderNotFoundError, InvalidOrderStatusError, InsufficientStockError,
       CustomerNotFoundError, ItemNotFoundError, ValueError).
    - Let SoftOneError propagate for anything else.
"""
from __future__ import annotations

from datetime import date
from typing import Any

from .exceptions import (
    CustomerNotFoundError,
    InsufficientStockError,
    InvalidOrderStatusError,
    ItemNotFoundError,
    OrderNotFoundError,
)
from .ports import (
    CustomerRepository,
    InventoryService,
    ItemLineInput,
    ItemRepository,
    OrderItemsRepository,
    OrderRepository,
)
from .translate import translate_softone_not_found

# Orders with a total below this threshold are auto-approved (Confirmed)
# instead of being left as Draft. Tune to match your business rules.
AUTO_APPROVE_THRESHOLD = 1000.0


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _resolve_items(
    items_repo: ItemRepository,
    items: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """
    For each requested line, fetch the item and validate stock.
    Returns enriched lines with current price attached.

    Expected input format:
        [{"item_id": 101, "quantity": 2}, ...]

    Raises ItemNotFoundError (from ItemRepository.get()) or InsufficientStockError.
    """
    enriched: list[dict[str, Any]] = []
    for line in items:
        item_id = int(line["item_id"])
        qty = int(line["quantity"])

        snap = translate_softone_not_found(
            lambda: items_repo.get_snapshot(key=item_id),
            exc_factory=lambda: ItemNotFoundError(item_id),
        )

        if snap["stock"] < qty:
            raise InsufficientStockError(item_id, qty, snap["stock"])

        enriched.append(
            {
                "item_id": item_id,
                "quantity": qty,
                "unit_price": snap["price"],
            }
        )
    return enriched


def _calculate_total(enriched_lines: list[dict[str, Any]]) -> float:
    """Sum qty × unit_price across all lines, rounded to 2 decimals."""
    return round(
        sum(line["quantity"] * line["unit_price"] for line in enriched_lines), 2
    )


def _determine_status(total: float) -> str:
    """Auto-approve small orders; everything else starts as Draft."""
    return "Confirmed" if total < AUTO_APPROVE_THRESHOLD else "Draft"


def _determine_status_with_policy(total: float, *, auto_approve_policy: str) -> str:
    """
    Deterministically decide initial order status based on an explicit policy.

    Policies:
      - never: always Draft
      - if_under_threshold: Draft/Confirmed based on AUTO_APPROVE_THRESHOLD
      - always: always Confirmed
    """
    policy = (auto_approve_policy or "").strip().lower()
    if policy == "never":
        return "Draft"
    if policy == "always":
        return "Confirmed"
    if policy in ("if_under_threshold", "if-under-threshold", "threshold"):
        return _determine_status(total)
    raise ValueError(
        "Invalid auto_approve_policy. Expected one of: never, if_under_threshold, always."
    )


# ---------------------------------------------------------------------------
# Business logic functions
# ---------------------------------------------------------------------------

def create_order_bl(
    customers: CustomerRepository,
    items_repo: ItemRepository,
    orders: OrderRepository,
    orderitems: OrderItemsRepository,
    inventory: InventoryService,
    customer_id: int,
    items: list[dict[str, Any]],
    notes: str = "",
    auto_approve_policy: str = "if_under_threshold",
) -> dict[str, Any]:
    """
    Full create-order workflow:

      1. Validate customer exists.
      2. Validate each item exists and has sufficient stock.
      3. Calculate total + resolve auto-approval status.
      4. Reserve stock (lock qty, don't deduct).
      5. Create order header.
      6. Add order lines.
      7. Return the normalized order (with _meta summary attached).

    Raises:
        CustomerNotFoundError, ItemNotFoundError, InsufficientStockError,
        ValueError (on empty items).
    """
    if not items:
        raise ValueError("Order must contain at least one item")

    # 1. Validate customer (raises CustomerNotFoundError on miss).
    translate_softone_not_found(
        lambda: customers.get(key=customer_id, locateinfo=""),
        exc_factory=lambda: CustomerNotFoundError(customer_id),
    )

    # 2. Validate items + stock.
    enriched = _resolve_items(items_repo, items)

    # 3. Pre-compute pricing/status so we never persist a half-built order.
    total = _calculate_total(enriched)
    status = _determine_status_with_policy(total, auto_approve_policy=auto_approve_policy)

    # 4. Reserve stock.
    reserve_lines: list[ItemLineInput] = [
        {"item_id": int(ln["item_id"]), "quantity": int(ln["quantity"])}
        for ln in enriched
    ]
    token = inventory.reserve(lines=reserve_lines)

    try:
        # 5. Create order header.
        order_id = orders.create(
            customer_id=int(customer_id),
            order_date=date.today().isoformat(),
            total=total,
            status=status,
            notes=notes,
        )

        # 6. Add order lines one-by-one (merge on duplicate product_id).
        for line in enriched:
            orderitems.add_line(
                order_id=order_id,
                item_id=int(line["item_id"]),
                quantity=int(line["quantity"]),
                unit_price=float(line["unit_price"]),
            )

        # 7. Return the fully-hydrated order (adapter provides normalized dict).
        order = orders.get(order_id=order_id)
        order["_meta"] = {
            "auto_approved": status == "Confirmed",
            "total": total,
            "lines_count": len(enriched),
        }
        return order
    except Exception:
        inventory.rollback(token=token)
        raise


def approve_order_bl(
    orders: OrderRepository,
    order_id: int,
) -> dict[str, Any]:
    """
    Approve a Draft order → move it to Confirmed.

    Raises:
        OrderNotFoundError, InvalidOrderStatusError.
    """
    order = translate_softone_not_found(
        lambda: orders.get(order_id=order_id),
        exc_factory=lambda: OrderNotFoundError(order_id),
    )

    current_status = order.get("status")
    if current_status != "Draft":
        raise InvalidOrderStatusError(order_id, current_status or "None", "Draft")

    return orders.update(order_id=order_id, status="Confirmed")


def get_order_bl(
    orders: OrderRepository,
    order_id: int,
) -> dict[str, Any]:
    """Fetch a single order by ID (normalized). Raises OrderNotFoundError."""
    return translate_softone_not_found(
        lambda: orders.get(order_id=order_id),
        exc_factory=lambda: OrderNotFoundError(order_id),
    )


def get_order_lines_bl(
    orders: OrderRepository,
    orderitems: OrderItemsRepository,
    order_id: int,
) -> dict[str, Any]:
    """
    Fetch normalized line items for an order.

    Raises OrderNotFoundError if the order does not exist.
    """
    get_order_bl(orders, order_id)
    lines = orderitems.get_lines(order_id=order_id)
    return {"order_id": order_id, "lines": lines}


def list_orders_bl(
    orders: OrderRepository,
    *,
    customer_id: int | None = None,
    status: str = "",
    limit: int | None = None,
) -> dict[str, Any]:
    """
    List orders (mock-only for now).

    Returns the raw list payload from the adapter/repository:
        {"orders": [...], "filter": {...}}
    """
    flt: dict[str, Any] = {"status": status}
    if customer_id is not None:
        flt["customer_id"] = int(customer_id)
    if limit is not None:
        flt["limit"] = int(limit)
    return orders.list(filter=flt)


def cancel_order_bl(
    orders: OrderRepository,
    *,
    order_id: int,
) -> dict[str, Any]:
    """
    Cancel an order safely.

    MVP semantics: only Draft orders may be cancelled, and cancellation is
    implemented as deletion (mock DB has no 'Cancelled' status).

    Raises:
        OrderNotFoundError, InvalidOrderStatusError.
    """
    order = translate_softone_not_found(
        lambda: orders.get(order_id=order_id),
        exc_factory=lambda: OrderNotFoundError(order_id),
    )
    current_status = order.get("status")
    if current_status != "Draft":
        raise InvalidOrderStatusError(order_id, current_status or "None", "Draft")

    resp = orders.delete(order_id=order_id)
    return {"order_id": order_id, "deleted": True, "response": resp}


def update_order_notes_bl(
    orders: OrderRepository,
    *,
    order_id: int,
    notes: str,
) -> dict[str, Any]:
    """Update a Draft order's notes (header-only)."""
    order = translate_softone_not_found(
        lambda: orders.get(order_id=order_id),
        exc_factory=lambda: OrderNotFoundError(order_id),
    )
    current_status = order.get("status")
    if current_status != "Draft":
        raise InvalidOrderStatusError(order_id, current_status or "None", "Draft")
    return orders.update(order_id=order_id, notes=notes)


def add_order_line_bl(
    customers: CustomerRepository,
    items_repo: ItemRepository,
    orders: OrderRepository,
    orderitems: OrderItemsRepository,
    inventory: InventoryService,
    *,
    order_id: int,
    item_id: int,
    quantity: int,
) -> dict[str, Any]:
    """Add (merge) one line to a Draft order and update totals/reservations."""
    if quantity <= 0:
        raise ValueError("quantity must be > 0")

    order = translate_softone_not_found(
        lambda: orders.get(order_id=order_id),
        exc_factory=lambda: OrderNotFoundError(order_id),
    )
    current_status = order.get("status")
    if current_status != "Draft":
        raise InvalidOrderStatusError(order_id, current_status or "None", "Draft")

    # Validate customer exists (order.customer_id must be valid).
    customer_id = int(order.get("customer_id") or 0)
    translate_softone_not_found(
        lambda: customers.get(key=customer_id, locateinfo=""),
        exc_factory=lambda: CustomerNotFoundError(customer_id),
    )

    # Validate item + stock + get price.
    enriched = _resolve_items(items_repo, [{"item_id": int(item_id), "quantity": int(quantity)}])
    line = enriched[0]

    token = inventory.reserve(lines=[{"item_id": int(item_id), "quantity": int(quantity)}])
    try:
        orderitems.add_line(
            order_id=int(order_id),
            item_id=int(item_id),
            quantity=int(quantity),
            unit_price=float(line["unit_price"]),
        )

        # Recompute total from current lines.
        lines = orderitems.get_lines(order_id=int(order_id))
        total = _calculate_total(
            [
                {
                    "item_id": int(ln["item_id"]),
                    "quantity": int(ln["quantity"]),
                    "unit_price": float(ln["unit_price"]),
                }
                for ln in lines
            ]
        )
        orders.update(order_id=int(order_id), total=total)
        out = orders.get(order_id=int(order_id))
        out["_meta"] = {"total": total, "line_added": {"item_id": int(item_id), "quantity": int(quantity)}}
        return out
    except Exception:
        inventory.rollback(token=token)
        raise


def remove_order_line_bl(
    orders: OrderRepository,
    orderitems: OrderItemsRepository,
    inventory: InventoryService,
    *,
    order_id: int,
    item_id: int,
) -> dict[str, Any]:
    """Remove all lines for an item from a Draft order and release reservations."""
    order = translate_softone_not_found(
        lambda: orders.get(order_id=order_id),
        exc_factory=lambda: OrderNotFoundError(order_id),
    )
    current_status = order.get("status")
    if current_status != "Draft":
        raise InvalidOrderStatusError(order_id, current_status or "None", "Draft")

    # Determine how much to release from reservations based on existing lines.
    lines = orderitems.get_lines(order_id=int(order_id))
    to_release = sum(int(ln.get("quantity") or 0) for ln in lines if int(ln.get("item_id") or 0) == int(item_id))
    if to_release > 0:
        inventory.release(lines=[{"item_id": int(item_id), "quantity": int(to_release)}])

    resp = orderitems.remove_line(order_id=int(order_id), item_id=int(item_id))

    # Recompute total after removal.
    new_lines = orderitems.get_lines(order_id=int(order_id))
    total = _calculate_total(
        [
            {
                "item_id": int(ln["item_id"]),
                "quantity": int(ln["quantity"]),
                "unit_price": float(ln["unit_price"]),
            }
            for ln in new_lines
        ]
    )
    orders.update(order_id=int(order_id), total=total)
    out = orders.get(order_id=int(order_id))
    out["_meta"] = {"total": total, "line_removed": {"item_id": int(item_id)}, "response": resp}
    return out
