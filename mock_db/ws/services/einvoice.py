"""eInvoice service: signature lookup.

NOT a CRUD endpoint -- this returns the stored MyData / signature blob for a
(doc_key, template) pair. Uses the `invoices` table (not `invoices_business`,
which is the order-side business invoice).
"""
from __future__ import annotations

import sqlite3
from typing import Any

from ..errors import WsError, WS_NOT_FOUND


def einvoice_service(payload: dict[str, Any], conn: sqlite3.Connection) -> dict[str, Any]:
    key = str(payload.get("key", ""))
    template = str(payload.get("template", ""))
    inv = conn.execute(
        """
        SELECT integritySignature, signature, uid, mark, authenticationCode
        FROM invoices
        WHERE doc_key = ? AND template = ?
        """,
        (key, template),
    ).fetchone()
    if inv is None:
        raise WsError(WS_NOT_FOUND, "Invalid request, Data does not exist.")
    return {
        "success": True,
        "data": {
            "integritySignature": inv["integritySignature"],
            "signature": inv["signature"],
            "uid": inv["uid"],
            "mark": inv["mark"],
            "authenticationCode": inv["authenticationCode"],
        },
    }
