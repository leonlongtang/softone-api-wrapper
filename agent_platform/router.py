from __future__ import annotations


def hybrid_route(user_text: str) -> str:
    """Hybrid deterministic router.

    - Routes to a department when signals are strong.
    - Returns \"clarify\" when ambiguous (caller should ask a question and stop).
    """
    t = (user_text or "").lower().strip()
    if not t:
        return "clarify"

    finance = any(k in t for k in ("invoice", "invoices", "payment", "paid", "refund", "unpaid", "ar"))
    inventory = any(k in t for k in ("stock", "inventory", "item", "items", "sku", "warehouse", "catalog"))
    sales = any(k in t for k in ("order", "orders", "customer", "customers", "quote", "sales"))

    # Strong single-signal cases.
    if finance and not inventory and not sales:
        return "finance"
    if inventory and not finance and not sales:
        return "inventory"
    if sales and not finance and not inventory:
        return "sales"

    # Conflict resolution heuristics.
    if finance and sales:
        # If the user mentions unpaid/paid/payment/refund, prioritize finance.
        if any(k in t for k in ("unpaid", "paid", "payment", "refund", "balance due", "receipt")):
            return "finance"
        # Otherwise, if they clearly want to create/modify an order, prioritize sales.
        if any(k in t for k in ("create order", "new order", "approve order", "cancel order")):
            return "sales"
        return "clarify"

    if inventory and sales:
        # Stock questions are usually inventory; order actions are usually sales.
        if any(k in t for k in ("stock", "availability", "available", "warehouse")):
            return "inventory"
        if any(k in t for k in ("create order", "approve order", "cancel order")):
            return "sales"
        return "clarify"

    if finance and inventory:
        # Rare, but ambiguous without more info.
        return "clarify"

    # No strong signals.
    return "clarify"


def clarify_question() -> str:
    return (
        "I can help, but your request is ambiguous.\n"
        "Please clarify what you want to do (one sentence), for example:\n"
        "- \"Create an order for customer ACME for 2x IT-CHAIR\"\n"
        "- \"Check inventory for IT-DESK\"\n"
        "- \"Invoice order 5001\"\n"
        "\n"
        "Reply with the exact action you want, plus any IDs/codes you already have."
    )


