"""Deterministic keyword router: a department, "clarify" on conflicting signals, "unknown" on none."""

from __future__ import annotations

import re

DEPARTMENTS = ("sales", "inventory", "finance")

FINANCE = {"invoice", "invoices", "payment", "payments", "pay", "paid", "unpaid", "refund", "receivable", "receivables"}
INVENTORY = {"stock", "inventory", "item", "items", "sku", "warehouse", "catalog", "product", "products", "reserved"}
SALES = {"order", "orders", "customer", "customers", "quote", "sales"}

MONEY_MOVES = {"payment", "payments", "pay", "paid", "unpaid", "refund"}
ORDER_ACTIONS = {"create", "new", "place", "approve", "cancel"}
STOCK_QUESTIONS = {"stock", "available", "availability", "warehouse", "reserved"}

ITEM_CHANGES = {"create", "update", "adjust", "delete", "rename", "restock"}

# Mid-conversation, naming something the current department's own tools can look up is detail
# for that department, not a new request: sales has the item tools, finance has get_order/list_orders.
# The words after each set are actions that do start a new request in the other department.
FOLLOW_UP_DETAIL = {
    "sales": ({"item", "items", "product", "products"}, STOCK_QUESTIONS | ITEM_CHANGES),
    "finance": ({"order", "orders", "customer", "customers"}, ORDER_ACTIONS),
}

CLARIFY_QUESTION = (
    "Your request could belong to more than one department. Either rephrase it as one action, e.g.\n"
    '- "Create an order for customer 47: 1x item 1001"\n'
    '- "Check stock for item 1001"\n'
    '- "Invoice order 5001"\n'
    "or reply `sales`, `inventory` or `finance` to send your original request there."
)


def hybrid_route(user_text: str) -> str:
    """Return a department, "clarify" (caller asks CLARIFY_QUESTION), or "unknown" (no signal:
    a follow-up like "yes" or "47", which the caller keeps with the current department)."""
    words = set(re.findall(r"[a-z]+", (user_text or "").lower()))
    finance, inventory, sales = bool(words & FINANCE), bool(words & INVENTORY), bool(words & SALES)

    if not (finance or inventory or sales):
        return "unknown"
    if finance + inventory + sales == 1:
        return "finance" if finance else "inventory" if inventory else "sales"

    if finance and not inventory:
        if words & MONEY_MOVES or "invoice" in words:  # paying, or invoicing an order, is finance work
            return "finance"
        if words & ORDER_ACTIONS:
            return "sales"
    if inventory and sales and not finance:
        if words & STOCK_QUESTIONS:
            return "inventory"
        if words & ORDER_ACTIONS:  # "create an order ... 2x item 1001"
            return "sales"
    return "clarify"


def is_follow_up_detail(user_text: str, current: str | None) -> bool:
    """True when the message only names things `current` can look up, with no action that starts
    a new request: "5 of item 1002" mid-order (sales), "only the ones for customer 47" (finance)."""
    nouns, actions = FOLLOW_UP_DETAIL.get(current or "", (set(), set()))
    words = set(re.findall(r"[a-z]+", (user_text or "").lower()))
    signal = words & (FINANCE | INVENTORY | SALES)
    return bool(signal) and signal <= nouns and not words & actions


def named_department(user_text: str) -> str | None:
    """The one department a reply names ("sales please", "send it to finance"), else None.
    A rephrased request ("check inventory for item 1001") has other signals and isn't a choice."""
    words = set(re.findall(r"[a-z]+", (user_text or "").lower()))
    named = [d for d in DEPARTMENTS if d in words]
    if len(named) != 1 or (words & (FINANCE | INVENTORY | SALES)) - {named[0]}:
        return None
    return named[0]
