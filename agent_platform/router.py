"""Deterministic keyword router: a department, "clarify" on conflicting signals, "unknown" on none."""

from __future__ import annotations

import re

DEPARTMENTS = ("sales", "inventory", "finance")

FINANCE = {"invoice", "invoices", "payment", "payments", "pay", "paid", "unpaid", "refund", "receivable", "receivables"}
INVENTORY = {"stock", "inventory", "item", "items", "sku", "warehouse", "catalog", "product", "products"}
SALES = {"order", "orders", "customer", "customers", "quote", "sales"}

MONEY_MOVES = {"payment", "payments", "pay", "paid", "unpaid", "refund"}
ORDER_ACTIONS = {"create", "new", "place", "approve", "cancel"}
STOCK_QUESTIONS = {"stock", "available", "availability", "warehouse"}

ITEM_WORDS = {"item", "items", "product", "products"}
ITEM_CHANGES = {"create", "update", "adjust", "delete", "rename", "restock"}

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


def is_item_detail(user_text: str) -> bool:
    """Items named with no stock question or item edit, e.g. "5 of item 1002 and 7 of 1005".
    Mid-order that answers the sales agent (which has the item lookup tools), not inventory."""
    words = set(re.findall(r"[a-z]+", (user_text or "").lower()))
    return bool(words & ITEM_WORDS) and not words & (INVENTORY - ITEM_WORDS) and not words & (STOCK_QUESTIONS | ITEM_CHANGES)
