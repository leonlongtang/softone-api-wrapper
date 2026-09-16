"""Payments + cross-object behavior: invoice status auto-recompute.

The interesting part of payments isn't the row insert -- it's the side
effect: every set/del recomputes the parent invoice's status from
SUM(payments.amount) so callers don't have to drive that themselves.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from mock_db.mock_ws import handle_request


def _get_invoice_status(sid: str, db_path: Path, invoice_id: int) -> str:
    resp = handle_request(
        {"service": "getData", "clientID": sid, "OBJECT": "INVOICE", "KEY": invoice_id},
        db_path=db_path,
    )
    return resp["data"]["INVOICE"][0]["STATUS"]


def _add_payment(sid: str, db_path: Path, *, invoice_id: int, amount: float) -> dict[str, Any]:
    return handle_request(
        {
            "service": "setData",
            "clientID": sid,
            "OBJECT": "PAYMENT",
            "data": {"PAYMENT": [{"INVOICE_ID": invoice_id, "AMOUNT": amount}]},
        },
        db_path=db_path,
    )


def _del_payment(sid: str, db_path: Path, payment_id: int) -> dict[str, Any]:
    return handle_request(
        {"service": "delData", "clientID": sid, "OBJECT": "PAYMENT", "KEY": str(payment_id)},
        db_path=db_path,
    )


class TestInvoiceStatusRecompute:
    """Invoice 2 is unpaid (amount 80, no payments) in the seed -- ideal
    sandbox for driving status transitions through payments."""

    def test_partial_payment_makes_invoice_partial(
        self, final_session: str, db_path: Path
    ) -> None:
        assert _get_invoice_status(final_session, db_path, 2) == "unpaid"

        _add_payment(final_session, db_path, invoice_id=2, amount=30.0)

        assert _get_invoice_status(final_session, db_path, 2) == "partial"

    def test_full_payment_makes_invoice_paid(
        self, final_session: str, db_path: Path
    ) -> None:
        _add_payment(final_session, db_path, invoice_id=2, amount=80.0)
        assert _get_invoice_status(final_session, db_path, 2) == "paid"

    def test_overpayment_still_marks_paid(
        self, final_session: str, db_path: Path
    ) -> None:
        # No "amount > due" check today (we deferred that decision -- see
        # turn 4 of the conversation). This test pins the current behavior
        # so we notice if it changes.
        _add_payment(final_session, db_path, invoice_id=2, amount=200.0)
        assert _get_invoice_status(final_session, db_path, 2) == "paid"

    def test_payment_deletion_can_demote_invoice_status(
        self, final_session: str, db_path: Path
    ) -> None:
        # Invoice 1 is fully paid by payment 1 in the seed. Delete that
        # payment and the invoice should drop back to 'unpaid'.
        assert _get_invoice_status(final_session, db_path, 1) == "paid"
        _del_payment(final_session, db_path, 1)
        assert _get_invoice_status(final_session, db_path, 1) == "unpaid"

    def test_partial_then_topup_to_paid(
        self, final_session: str, db_path: Path
    ) -> None:
        # Two partial payments that sum to the full amount.
        _add_payment(final_session, db_path, invoice_id=2, amount=20.0)
        assert _get_invoice_status(final_session, db_path, 2) == "partial"

        _add_payment(final_session, db_path, invoice_id=2, amount=60.0)
        assert _get_invoice_status(final_session, db_path, 2) == "paid"


class TestPaymentValidation:
    def test_zero_amount_payment_rejected_by_schema(
        self, final_session: str, db_path: Path
    ) -> None:
        # Schema CHECK (amount > 0). The brain layer doesn't pre-validate
        # this -- we let the schema be the source of truth. The error
        # propagates as a raw IntegrityError because no brain wrapper
        # catches it -- which is acceptable since this is a malformed
        # request, not a business rule violation.
        with pytest.raises(Exception):  # noqa: BLE001 -- accept either WsError or IntegrityError
            _add_payment(final_session, db_path, invoice_id=2, amount=0)

    def test_missing_invoice_id_is_rejected(
        self, final_session: str, db_path: Path
    ) -> None:
        from mock_db.mock_ws import WsError

        with pytest.raises(WsError) as exc_info:
            handle_request(
                {
                    "service": "setData",
                    "clientID": final_session,
                    "OBJECT": "PAYMENT",
                    "data": {"PAYMENT": [{"AMOUNT": 50}]},  # no INVOICE_ID
                },
                db_path=db_path,
            )
        assert exc_info.value.code == -9  # invalid request
