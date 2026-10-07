"""Business-rule validations enforced by `mock_db/ws/objects/`.

These are the rules a real SoftOne WS would surface BEFORE persistence.
Each test runs a single setData call through `handle_request` and asserts
on the structured WsError code/message rather than letting raw
sqlite3.IntegrityError leak through.

Code 2010 = WS_BUSINESS_RULE (mock-only convention).
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from mock_db.mock_ws import WsError, handle_request

# ---------------------------------------------------------------------------
# Tiny helpers used across test classes -- not pytest fixtures because they
# wrap behavior the tests assert against, not setup data.
# ---------------------------------------------------------------------------

def _set_order(sid: str, db_path: Path, *, key: Any = None, **fields: Any) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "service": "setData",
        "clientID": sid,
        "OBJECT": "ORDER",
        "data": {"ORDER": [fields.get("order_row", {})]},
    }
    if key is not None:
        payload["KEY"] = str(key)
    if "lines" in fields:
        payload["data"]["ORDERITEMS"] = fields["lines"]
    return handle_request(payload, db_path=db_path)


def _set_invoice(sid: str, db_path: Path, *, key: Any = None, **inv_fields: Any) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "service": "setData",
        "clientID": sid,
        "OBJECT": "INVOICE",
        "data": {"INVOICE": [inv_fields]},
    }
    if key is not None:
        payload["KEY"] = str(key)
    return handle_request(payload, db_path=db_path)


# ---------------------------------------------------------------------------
# ORDER setData: brain rules
# ---------------------------------------------------------------------------

class TestOrderCreate:
    def test_happy_path_creates_draft_order(self, final_session: str, db_path: Path) -> None:
        resp = _set_order(
            final_session, db_path,
            order_row={"CUSTOMER_ID": 47, "STATUS": "Draft"},
            lines=[{"PRODUCT_ID": 1002, "QUANTITY": 2}],
        )
        assert resp["success"] is True
        assert resp["id"]  # auto-assigned id

    def test_missing_customer_id_is_rejected(self, final_session: str, db_path: Path) -> None:
        with pytest.raises(WsError) as exc_info:
            _set_order(final_session, db_path, order_row={})
        assert exc_info.value.code == 2010
        assert "CUSTOMER_ID" in exc_info.value.message

    def test_nonexistent_customer_is_rejected(self, final_session: str, db_path: Path) -> None:
        with pytest.raises(WsError) as exc_info:
            _set_order(final_session, db_path, order_row={"CUSTOMER_ID": 99999})
        assert exc_info.value.code == 2010
        assert "Customer 99999" in exc_info.value.message

    def test_invalid_status_is_rejected(self, final_session: str, db_path: Path) -> None:
        # Pre-CHECK-constraint era used 'pending'/'completed'. New brain
        # vocabulary is Draft/Confirmed only.
        with pytest.raises(WsError) as exc_info:
            _set_order(
                final_session, db_path,
                order_row={"CUSTOMER_ID": 47, "STATUS": "pending"},
            )
        assert exc_info.value.code == 2010
        assert "pending" in exc_info.value.message


class TestOrderLines:
    def test_line_with_nonexistent_item_is_rejected(
        self, final_session: str, db_path: Path
    ) -> None:
        with pytest.raises(WsError) as exc_info:
            _set_order(
                final_session, db_path,
                order_row={"CUSTOMER_ID": 47},
                lines=[{"PRODUCT_ID": 99999, "QUANTITY": 1}],
            )
        assert exc_info.value.code == 2010
        assert "Item 99999" in exc_info.value.message

    def test_line_qty_exceeding_stock_is_rejected(
        self, final_session: str, db_path: Path
    ) -> None:
        # Item 1002 has stock=46 from seed. Asking for 10000 must fail
        # with the structured stock error, not a CHECK exception.
        with pytest.raises(WsError) as exc_info:
            _set_order(
                final_session, db_path,
                order_row={"CUSTOMER_ID": 47},
                lines=[{"PRODUCT_ID": 1002, "QUANTITY": 10000}],
            )
        assert exc_info.value.code == 2010
        assert "Insufficient stock" in exc_info.value.message
        assert "1002" in exc_info.value.message

    def test_zero_quantity_line_is_rejected(self, final_session: str, db_path: Path) -> None:
        with pytest.raises(WsError) as exc_info:
            _set_order(
                final_session, db_path,
                order_row={"CUSTOMER_ID": 47},
                lines=[{"PRODUCT_ID": 1002, "QUANTITY": 0}],
            )
        assert exc_info.value.code == 2010
        assert "positive" in exc_info.value.message

    def test_total_is_recomputed_from_lines(self, final_session: str, db_path: Path) -> None:
        # 2x of item 1002 (price 25) + 1x of item 1003 (price 80) = 130
        resp = _set_order(
            final_session, db_path,
            order_row={"CUSTOMER_ID": 47, "STATUS": "Draft"},
            lines=[
                {"PRODUCT_ID": 1002, "QUANTITY": 2},
                {"PRODUCT_ID": 1003, "QUANTITY": 1},
            ],
        )
        order_id = resp["id"]

        get_resp = handle_request(
            {"service": "getData", "clientID": final_session,
             "OBJECT": "ORDER", "KEY": order_id},
            db_path=db_path,
        )
        assert get_resp["data"]["ORDER"][0]["TOTAL"] == pytest.approx(130.0)


class TestOrderStatusTransitions:
    def test_draft_to_confirmed_is_legal(self, final_session: str, db_path: Path) -> None:
        # Order 5005 starts as Draft in seed.
        resp = _set_order(
            final_session, db_path, key=5005,
            order_row={"STATUS": "Confirmed"},
        )
        assert resp["success"] is True

    def test_confirmed_back_to_draft_is_rejected(
        self, final_session: str, db_path: Path
    ) -> None:
        # Order 5001 is Confirmed in seed -- regression must be blocked.
        with pytest.raises(WsError) as exc_info:
            _set_order(
                final_session, db_path, key=5001,
                order_row={"STATUS": "Draft"},
            )
        assert exc_info.value.code == 2010
        assert "Confirmed -> Draft" in exc_info.value.message

    def test_self_loop_status_allowed(self, final_session: str, db_path: Path) -> None:
        # Confirmed -> Confirmed is a no-op but not illegal.
        resp = _set_order(
            final_session, db_path, key=5001,
            order_row={"STATUS": "Confirmed"},
        )
        assert resp["success"] is True

    def test_update_nonexistent_order_is_rejected(
        self, final_session: str, db_path: Path
    ) -> None:
        with pytest.raises(WsError) as exc_info:
            _set_order(
                final_session, db_path, key=99999,
                order_row={"STATUS": "Confirmed"},
            )
        assert exc_info.value.code == 2010
        assert "Order 99999" in exc_info.value.message


# ---------------------------------------------------------------------------
# INVOICE setData: brain rules (the "already invoiced" rule + neighbors)
# ---------------------------------------------------------------------------

class TestInvoiceCreate:
    def test_happy_path_creates_ad_hoc_invoice(
        self, final_session: str, db_path: Path
    ) -> None:
        resp = _set_invoice(
            final_session, db_path,
            CUSTOMER_ID=47, AMOUNT=50,
        )
        assert resp["success"] is True

    def test_missing_customer_id_is_rejected(
        self, final_session: str, db_path: Path
    ) -> None:
        with pytest.raises(WsError) as exc_info:
            _set_invoice(final_session, db_path, AMOUNT=100)
        assert exc_info.value.code == 2010
        assert "CUSTOMER_ID" in exc_info.value.message

    def test_nonexistent_customer_is_rejected(
        self, final_session: str, db_path: Path
    ) -> None:
        with pytest.raises(WsError) as exc_info:
            _set_invoice(final_session, db_path, CUSTOMER_ID=99999, AMOUNT=100)
        assert exc_info.value.code == 2010

    def test_nonexistent_order_is_rejected(self, final_session: str, db_path: Path) -> None:
        with pytest.raises(WsError) as exc_info:
            _set_invoice(
                final_session, db_path,
                CUSTOMER_ID=47, ORDER_ID=99999, AMOUNT=100,
            )
        assert exc_info.value.code == 2010
        assert "Order 99999" in exc_info.value.message

    def test_already_invoiced_order_is_rejected(
        self, final_session: str, db_path: Path
    ) -> None:
        # ChatGPT's "already invoiced" rule: order 5001 has invoice 1.
        with pytest.raises(WsError) as exc_info:
            _set_invoice(
                final_session, db_path,
                CUSTOMER_ID=47, ORDER_ID=5001, AMOUNT=1225,
            )
        assert exc_info.value.code == 2010
        assert "already been invoiced" in exc_info.value.message
        assert "invoice 1" in exc_info.value.message

    def test_multiple_ad_hoc_invoices_for_same_customer_allowed(
        self, final_session: str, db_path: Path
    ) -> None:
        # NULL order_id case must NOT trip the "already invoiced" rule.
        resp1 = _set_invoice(final_session, db_path, CUSTOMER_ID=51, AMOUNT=100)
        resp2 = _set_invoice(final_session, db_path, CUSTOMER_ID=51, AMOUNT=200)
        assert resp1["success"] and resp2["success"]
        assert resp1["id"] != resp2["id"]


class TestInvoiceUpdate:
    def test_retargeting_to_invoiced_order_is_rejected(
        self, final_session: str, db_path: Path
    ) -> None:
        # Invoice 5 is ad-hoc (NULL order_id). Try to retarget it onto
        # order 5001 (already invoiced by invoice 1) -- must be rejected.
        with pytest.raises(WsError) as exc_info:
            _set_invoice(final_session, db_path, key=5, ORDER_ID=5001)
        assert exc_info.value.code == 2010

    def test_can_clear_order_id_back_to_null(
        self, final_session: str, db_path: Path
    ) -> None:
        # Invoice 1 -> order 5001. Clearing the order_id releases the unique
        # slot and turns it into an ad-hoc invoice.
        resp = _set_invoice(final_session, db_path, key=1, ORDER_ID=None)
        assert resp["success"] is True
