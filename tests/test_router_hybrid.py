from __future__ import annotations

from agent_platform.orchestrator.router import hybrid_route


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

