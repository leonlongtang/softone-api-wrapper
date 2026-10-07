"""MCP-facing business paths and new tools (mock DB + SoftOneClient.mock)."""
from __future__ import annotations

import os
from pathlib import Path

import pytest

os.environ.setdefault("SOFTONE_MOCK", "true")

from config import load_config
from softone_mcp.business.customers import create_customer_bl, delete_customer_bl, search_customers_bl
from softone_mcp.business.invoices import list_invoices_bl
from softone_mcp.business.items import (
    create_item_bl,
    delete_item_bl,
    get_stock_balance_bl,
    inventory_adjustment_bl,
    search_items_bl,
)
from softone_mcp.business.orders import cancel_order_bl, get_order_lines_bl, list_orders_bl
from softone_mcp.business.payments import list_payments_for_invoice_bl
from softone_mcp.internal.adapters.repositories import (
    SoftOneCustomerRepository,
    SoftOneInvoiceRepository,
    SoftOneItemRepository,
    SoftOneOrderItemsRepository,
    SoftOneOrderRepository,
    SoftOnePaymentRepository,
)
from softone_wrapper import SoftOneClient


@pytest.fixture
def mcp_client(db_path: Path) -> SoftOneClient:
    return SoftOneClient.mock(db_path=db_path)


@pytest.fixture
def session_id(mcp_client: SoftOneClient) -> str:
    cfg = load_config()
    start = mcp_client.start_connection(
        base_url=cfg.base_url,
        username=cfg.username,
        password=cfg.password,
        app_id=cfg.app_id,
        company="1000",
        branch="1000",
        module="0",
        refid="1",
    )
    assert start.session is not None
    return start.session.session_id


def test_get_order_lines_bl_returns_lines_for_seeded_order(
    mcp_client: SoftOneClient,
    session_id: str,
) -> None:
    orders = SoftOneOrderRepository(mcp_client, session_id)
    orderitems = SoftOneOrderItemsRepository(mcp_client, session_id)
    data = get_order_lines_bl(orders, orderitems, order_id=5001)
    assert data["order_id"] == 5001
    assert len(data["lines"]) >= 1
    row = data["lines"][0]
    assert "item_id" in row and "quantity" in row and "unit_price" in row


def test_get_context_reads_selection_fields(mcp_client: SoftOneClient, session_id: str) -> None:
    ctx = mcp_client.get_session_context(session_id=session_id)
    assert ctx["session_id"] == session_id
    # selection is fixed by the fixture
    assert ctx["company"] == "1000"
    assert ctx["branch"] == "1000"
    assert ctx["module"] == "0"
    assert ctx["refid"] == "1"


def test_list_orders_bl_returns_seeded_orders(mcp_client: SoftOneClient, session_id: str) -> None:
    orders = SoftOneOrderRepository(mcp_client, session_id)
    data = list_orders_bl(orders, status="", customer_id=None, limit=10)
    assert "orders" in data
    assert any(int(o["id"]) == 5001 for o in data["orders"])


def test_cancel_order_bl_deletes_draft_only(mcp_client: SoftOneClient, session_id: str) -> None:
    from softone_mcp.business.exceptions import InvalidOrderStatusError

    orders = SoftOneOrderRepository(mcp_client, session_id)

    # 5005 is seeded as Draft
    resp = cancel_order_bl(orders, order_id=5005)
    assert resp["order_id"] == 5005
    assert resp["deleted"] is True

    # Cancelling a Confirmed order should be blocked
    with pytest.raises(InvalidOrderStatusError):
        cancel_order_bl(orders, order_id=5001)


def test_get_stock_balance_bl_for_seeded_item(mcp_client: SoftOneClient, session_id: str) -> None:
    items = SoftOneItemRepository(mcp_client, session_id)
    bal = get_stock_balance_bl(items, key=1001)
    assert bal["item_id"] == 1001
    assert bal["stock"] >= 0
    assert bal["reserved"] >= 0
    assert bal["available"] == max(0, bal["stock"] - bal["reserved"])


def test_inventory_adjustment_bl_guards_reserved(mcp_client: SoftOneClient, session_id: str) -> None:
    items = SoftOneItemRepository(mcp_client, session_id)
    bal = get_stock_balance_bl(items, key=1001)

    # OK: add stock
    adj = inventory_adjustment_bl(items, key=1001, delta_qty=1)
    assert adj["new_stock"] == bal["stock"] + 1

    # Not OK: drop below reserved
    reserved = int(adj["reserved"])
    new_stock = int(adj["new_stock"])
    bad_delta = -(new_stock - reserved + 1)
    with pytest.raises(ValueError):
        inventory_adjustment_bl(items, key=1001, delta_qty=bad_delta)


def test_search_customers_bl_returns_matches(mcp_client: SoftOneClient, session_id: str) -> None:
    customers = SoftOneCustomerRepository(mcp_client, session_id)
    data = search_customers_bl(customers, q="Soft", limit=5)
    assert data["q"] == "Soft"
    assert len(data["customers"]) >= 1
    assert any("Soft" in (c["name"] or "") for c in data["customers"])


def test_list_invoices_bl_filters(mcp_client: SoftOneClient, session_id: str) -> None:
    invoices = SoftOneInvoiceRepository(mcp_client, session_id)
    data = list_invoices_bl(invoices, status="unpaid", customer_id=None)
    assert "invoices" in data
    assert all(inv["status"] == "unpaid" for inv in data["invoices"])


def test_search_items_bl_returns_matches(mcp_client: SoftOneClient, session_id: str) -> None:
    items = SoftOneItemRepository(mcp_client, session_id)
    data = search_items_bl(items, q="Laptop", limit=5)
    assert data["q"] == "Laptop"
    assert len(data["items"]) >= 1
    assert any("Laptop" in (it["name"] or "") for it in data["items"])


def test_get_order_lines_bl_unknown_order(
    mcp_client: SoftOneClient,
    session_id: str,
) -> None:
    from softone_mcp.business.exceptions import OrderNotFoundError

    orders = SoftOneOrderRepository(mcp_client, session_id)
    orderitems = SoftOneOrderItemsRepository(mcp_client, session_id)
    with pytest.raises(OrderNotFoundError):
        get_order_lines_bl(orders, orderitems, order_id=999999)


def test_list_payments_for_invoice_bl(
    mcp_client: SoftOneClient,
    session_id: str,
) -> None:
    invoices = SoftOneInvoiceRepository(mcp_client, session_id)
    payments = SoftOnePaymentRepository(mcp_client, session_id)
    data = list_payments_for_invoice_bl(invoices, payments, invoice_id=1)
    assert data["invoice_id"] == 1
    assert len(data["payments"]) >= 1
    assert data["payments"][0]["invoice_id"] == 1


def test_list_payments_for_invoice_bl_missing_invoice(
    mcp_client: SoftOneClient,
    session_id: str,
) -> None:
    from softone_mcp.business.exceptions import InvoiceNotFoundError

    invoices = SoftOneInvoiceRepository(mcp_client, session_id)
    payments = SoftOnePaymentRepository(mcp_client, session_id)
    with pytest.raises(InvoiceNotFoundError):
        list_payments_for_invoice_bl(invoices, payments, invoice_id=999999)


def test_create_and_delete_customer_roundtrip(
    mcp_client: SoftOneClient,
    session_id: str,
) -> None:
    customers = SoftOneCustomerRepository(mcp_client, session_id)
    created = create_customer_bl(
        customers,
        code="DEL-TEST-001",
        name="Delete Me Customer",
        email="",
        phone="",
    )
    cid = int(created.get("id") or 0)
    assert cid > 0
    delete_customer_bl(customers, key=cid)


def test_create_and_delete_item_roundtrip(
    mcp_client: SoftOneClient,
    session_id: str,
) -> None:
    items = SoftOneItemRepository(mcp_client, session_id)
    created = create_item_bl(
        items,
        code="DEL-ITEM-001",
        name="Delete Me Item",
        price="",
        stock="",
    )
    iid = int(created.get("id") or 0)
    assert iid > 0
    delete_item_bl(items, key=iid)
