"""calculate service.

In real SoftOne, `calculate` runs server-side computations on a record
without persisting (e.g., totals, computed fields). For the mock we treat
it as a read-only preview and just delegate to getData -- the incoming
`data` payload is ignored.

Limited to CUSTOMER / ORDER / ITEM to mirror the real-world surface where
PAYMENT / INVOICE don't have meaningful pre-persist calculations.
"""
from __future__ import annotations

import sqlite3
from typing import Any

from ..errors import WsError, WS_BUSINESS_GENERIC
from .get_data import get_data_service


_CALCULABLE = frozenset({"CUSTOMER", "ORDER", "ITEM"})


def calculate_service(payload: dict[str, Any], conn: sqlite3.Connection) -> dict[str, Any]:
    obj = str(payload.get("OBJECT", "")).upper()
    if obj not in _CALCULABLE:
        raise WsError(WS_BUSINESS_GENERIC, "Business error")

    # Forward to getData with the same OBJECT/KEY/LOCATEINFO. We hand the
    # caller the same response shape as a getData call, which is what the
    # real WS does for inert calculate calls.
    return get_data_service(
        {
            "OBJECT": obj,
            "KEY": payload.get("KEY"),
            "FORM": payload.get("FORM", ""),
            "LOCATEINFO": payload.get("LOCATEINFO", ""),
        },
        conn,
    )
