"""getData service: per-OBJECT read dispatch.

Reads the SoftOne `OBJECT` field and routes to the right object's
`get_<object>` function. Each object handler is responsible for
SoftOne-shaped response normalization and `LOCATEINFO` filtering where
relevant.
"""
from __future__ import annotations

import sqlite3
from typing import Any, Callable

from ..errors import WsError, WS_BUSINESS_GENERIC
from ..objects.customers import get_customer
from ..objects.invoices import get_invoice
from ..objects.items import get_item
from ..objects.orders import get_order
from ..objects.payments import get_payment


# Each handler accepts (conn, key); CUSTOMER also accepts a `locateinfo`
# string (handled via a closure below) because SoftOne's CUSTOMER getData
# supports field-level filtering via LOCATEINFO and our other objects don't.
_GETTERS: dict[str, Callable[..., dict[str, Any]]] = {
    "ORDER": get_order,
    "ITEM": get_item,
    "INVOICE": get_invoice,
    "PAYMENT": get_payment,
}


def get_data_service(payload: dict[str, Any], conn: sqlite3.Connection) -> dict[str, Any]:
    obj = str(payload.get("OBJECT", "")).upper()
    key = payload.get("KEY")

    if obj == "CUSTOMER":
        # CUSTOMER is the only object that honors LOCATEINFO (CUSEXTRA child).
        return get_customer(conn, key, locateinfo=str(payload.get("LOCATEINFO", "")))

    handler = _GETTERS.get(obj)
    if handler is None:
        raise WsError(WS_BUSINESS_GENERIC, "Business error")
    return handler(conn, key)
