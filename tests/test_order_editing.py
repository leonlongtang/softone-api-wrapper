from __future__ import annotations

from pathlib import Path

import pytest

from config import load_config
from softone_wrapper import SoftOneClient
from softone_mcp.business.exceptions import InvalidOrderStatusError
from softone_mcp.business.orders import add_order_line_bl, update_order_notes_bl
from softone_mcp.internal.adapters.inventory import SoftOneInventoryService
from softone_mcp.internal.adapters.repositories import (
    SoftOneCustomerRepository,
    SoftOneItemRepository,
    SoftOneOrderItemsRepository,
    SoftOneOrderRepository,
)


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


def test_update_order_notes_draft_only(mcp_client: SoftOneClient, session_id: str) -> None:
    orders = SoftOneOrderRepository(mcp_client, session_id)

    # 5001 is seeded as Confirmed.
    with pytest.raises(InvalidOrderStatusError):
        update_order_notes_bl(orders, order_id=5001, notes="new notes")

    # 5005 is seeded as Draft.
    resp = update_order_notes_bl(orders, order_id=5005, notes="hello")
    assert resp.get("success") is True


def test_add_order_line_draft_only(mcp_client: SoftOneClient, session_id: str) -> None:
    customers = SoftOneCustomerRepository(mcp_client, session_id)
    items = SoftOneItemRepository(mcp_client, session_id)
    orders = SoftOneOrderRepository(mcp_client, session_id)
    orderitems = SoftOneOrderItemsRepository(mcp_client, session_id)
    inventory = SoftOneInventoryService(mcp_client, session_id)

    # 5001 is seeded as Confirmed.
    with pytest.raises(InvalidOrderStatusError):
        add_order_line_bl(
            customers,
            items,
            orders,
            orderitems,
            inventory,
            order_id=5001,
            item_id=1001,
            quantity=1,
        )

    # 5005 is seeded as Draft.
    out = add_order_line_bl(
        customers,
        items,
        orders,
        orderitems,
        inventory,
        order_id=5005,
        item_id=1001,
        quantity=1,
    )
    assert out.get("id") == 5005

