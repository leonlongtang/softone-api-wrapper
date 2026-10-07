"""setData service: per-OBJECT write dispatch.

Each object handler is responsible for its own brain rules
(see ws/objects/validators.py and per-object docstrings).
"""
from __future__ import annotations

import sqlite3
from typing import Any, Callable

from ..errors import WS_BUSINESS_GENERIC, WsError
from ..objects.customers import set_customer
from ..objects.invoices import set_invoice
from ..objects.items import set_item
from ..objects.orders import set_order
from ..objects.payments import set_payment

_SETTERS: dict[str, Callable[..., dict[str, Any]]] = {
    "CUSTOMER": set_customer,
    "ORDER": set_order,
    "ITEM": set_item,
    "INVOICE": set_invoice,
    "PAYMENT": set_payment,
}


def set_data_service(payload: dict[str, Any], conn: sqlite3.Connection) -> dict[str, Any]:
    obj = str(payload.get("OBJECT", "")).upper()
    key = payload.get("KEY")
    data = payload.get("data") or {}

    handler = _SETTERS.get(obj)
    if handler is None:
        raise WsError(WS_BUSINESS_GENERIC, "Business error")
    return handler(conn, key, data)
