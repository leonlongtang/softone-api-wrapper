"""delData service: per-OBJECT delete dispatch.

FK violations are converted into `WsError(WS_FK_BLOCKED)` inside each
object handler via `validators.delete_with_fk_guard`, so callers always see
structured errors instead of raw `sqlite3.IntegrityError`.
"""
from __future__ import annotations

import sqlite3
from typing import Any, Callable

from ..errors import WsError, WS_BUSINESS_GENERIC, WS_INVALID_REQUEST
from ..objects.customers import del_customer
from ..objects.invoices import del_invoice
from ..objects.items import del_item
from ..objects.orders import del_order
from ..objects.payments import del_payment


_DELETERS: dict[str, Callable[..., dict[str, Any]]] = {
    "CUSTOMER": del_customer,
    "ORDER": del_order,
    "ITEM": del_item,
    "INVOICE": del_invoice,
    "PAYMENT": del_payment,
}


def del_data_service(payload: dict[str, Any], conn: sqlite3.Connection) -> dict[str, Any]:
    obj = str(payload.get("OBJECT", "")).upper()
    # Optional FORM field is accepted for interface parity with the docs even
    # though the mock doesn't act on it.
    _ = payload.get("FORM", "")

    key = payload.get("KEY")
    if key is None and "ΚΕΥ" in payload:
        # Docs show the Greek key in one example; accept both.
        key = payload.get("ΚΕΥ")
    if key is None:
        raise WsError(WS_INVALID_REQUEST, "Invalid Request. Ensure that your request is valid")

    handler = _DELETERS.get(obj)
    if handler is None:
        raise WsError(WS_BUSINESS_GENERIC, "Business error")
    return handler(conn, key)
