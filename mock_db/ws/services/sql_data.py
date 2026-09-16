"""SqlData service: read seeded SQL-script results.

Mirrors SoftOne's "SQL Scripts" feature where named scripts return tabular
data. The mock only stores pre-seeded rows -- there's no actual SQL
execution against arbitrary tables.
"""
from __future__ import annotations

import sqlite3
from typing import Any


def sql_data_service(payload: dict[str, Any], conn: sqlite3.Connection) -> dict[str, Any]:
    sql_name = str(payload.get("SqlName", ""))
    rows = conn.execute(
        "SELECT mtrl, code, name, pricew, pricer FROM sql_rows "
        "WHERE script_name = ? ORDER BY id",
        (sql_name,),
    ).fetchall()
    return {
        "success": True,
        "totalcount": len(rows),
        "rows": [
            {
                "MTRL": r["mtrl"],
                "CODE": r["code"],
                "NAME": r["name"],
                "PRICEW": r["pricew"],
                "PRICER": r["pricer"],
            }
            for r in rows
        ],
    }
