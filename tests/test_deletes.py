"""delData: every per-OBJECT delete path goes through `delete_with_fk_guard`,
which converts sqlite3.IntegrityError into WsError(2003, ...).

Without these tests, the schema-level FK rules would still apply but the
mock would surface them as 500-shaped raw exceptions instead of structured
SoftOne-style errors -- which is exactly what we don't want for agent UX.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from mock_db.mock_ws import WsError, handle_request


def _del(sid: str, db_path: Path, obj: str, key: Any) -> dict[str, Any]:
    return handle_request(
        {"service": "delData", "clientID": sid, "OBJECT": obj, "KEY": str(key)},
        db_path=db_path,
    )


class TestFkBlockedDeletes:
    """Each case below has dependent rows in the seed -- the delete must be
    rejected with code 2003 (referential integrity), NOT 2001 (not found)."""

    def test_customer_with_orders_cannot_be_deleted(
        self, final_session: str, db_path: Path
    ) -> None:
        with pytest.raises(WsError) as exc_info:
            _del(final_session, db_path, "CUSTOMER", 47)
        assert exc_info.value.code == 2003
        assert "customer 47" in exc_info.value.message

    def test_order_with_invoice_cannot_be_deleted(
        self, final_session: str, db_path: Path
    ) -> None:
        # Order 5001 has invoice 1.
        with pytest.raises(WsError) as exc_info:
            _del(final_session, db_path, "ORDER", 5001)
        assert exc_info.value.code == 2003

    def test_item_referenced_by_order_line_cannot_be_deleted(
        self, final_session: str, db_path: Path
    ) -> None:
        # Item 1001 is on order 5001's line. This is the bug from a few
        # turns ago -- used to silently CASCADE and erase historical orders.
        with pytest.raises(WsError) as exc_info:
            _del(final_session, db_path, "ITEM", 1001)
        assert exc_info.value.code == 2003


class TestSafeDeletes:
    """Deletes that have no dependents must succeed cleanly."""

    def test_invoice_without_payments_can_be_deleted(
        self, final_session: str, db_path: Path
    ) -> None:
        # Invoice 5 (ad-hoc, no payments) is deletable.
        resp = _del(final_session, db_path, "INVOICE", 5)
        assert resp == {"success": True}

    def test_invoice_with_payments_cascades_them(
        self, final_session: str, db_path: Path
    ) -> None:
        # Documented schema choice: payments.invoice_id is ON DELETE CASCADE
        # (mock-cleanup convenience). Pinning the behavior so we know
        # immediately if it ever changes.
        resp = _del(final_session, db_path, "INVOICE", 1)
        assert resp == {"success": True}

        # Payment 1 belonged to invoice 1; the cascade should have removed
        # it. handle_request surfaces missing rows as WsError(2001).
        with pytest.raises(WsError) as exc_info:
            handle_request(
                {"service": "getData", "clientID": final_session,
                 "OBJECT": "PAYMENT", "KEY": 1},
                db_path=db_path,
            )
        assert exc_info.value.code == 2001


class TestDeleteNotFound:
    def test_deleting_unknown_id_returns_2001(
        self, final_session: str, db_path: Path
    ) -> None:
        with pytest.raises(WsError) as exc_info:
            _del(final_session, db_path, "ORDER", 99999)
        assert exc_info.value.code == 2001

    def test_missing_key_returns_invalid_request(
        self, final_session: str, db_path: Path
    ) -> None:
        with pytest.raises(WsError) as exc_info:
            handle_request(
                {"service": "delData", "clientID": final_session, "OBJECT": "ORDER"},
                db_path=db_path,
            )
        assert exc_info.value.code == -9
