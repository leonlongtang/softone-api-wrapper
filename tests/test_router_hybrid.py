from __future__ import annotations

from agent_platform.router import hybrid_route


def test_hybrid_route_finance() -> None:
    assert hybrid_route("List unpaid invoices for customer 47") == "finance"
    assert hybrid_route("record payment for invoice 123") == "finance"


def test_hybrid_route_inventory() -> None:
    assert hybrid_route("check stock balance for item 1001") == "inventory"
    assert hybrid_route("inventory adjustment for sku ABC") == "inventory"


def test_hybrid_route_sales() -> None:
    assert hybrid_route("create sales order for customer SoftOne") == "sales"
    assert hybrid_route("approve order 5001") == "sales"


def test_hybrid_route_clarify_when_ambiguous() -> None:
    assert hybrid_route("help me with this") == "clarify"
    assert hybrid_route("") == "clarify"



def test_invoicing_an_order_is_finance() -> None:
    assert hybrid_route("Invoice order 5001") == "finance"
    assert hybrid_route("invoice that order") == "finance"


def test_order_with_items_is_sales() -> None:
    assert hybrid_route("Create an order for customer 47: 1x item 1001") == "sales"


def test_whole_words_only() -> None:
    # "search" and "warehouse" contain "ar"; that must not look like accounts receivable.
    assert hybrid_route("search items named chair") == "inventory"
    assert hybrid_route("what's in the warehouse") == "inventory"


def test_listing_orders_and_invoices_is_ambiguous() -> None:
    assert hybrid_route("orders and invoices for customer 47") == "clarify"
