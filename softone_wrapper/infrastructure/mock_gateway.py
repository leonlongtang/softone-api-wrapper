from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any

from .gateway import SoftOneGateway


class MockGateway(SoftOneGateway):
    """
    Gateway that uses the local mock implementation in `mock_db/mock_ws.py`.

    `base_url` is accepted for interface compatibility but not used.

    Optional `db_path` overrides the SQLite file (used by tests with a temp DB).
    """

    def __init__(self, db_path: Path | None = None) -> None:
        from mock_db.mock_ws import WsError, handle_request  # local import to keep optional
        from mock_db.ws.session import DEFAULT_DB_PATH

        self._handle_request = handle_request
        self._WsError = WsError
        self._db_path: Path = db_path if db_path is not None else DEFAULT_DB_PATH

    def call(self, *, base_url: str, payload: dict[str, Any]) -> dict[str, Any]:
        try:
            return self._handle_request(payload, db_path=self._db_path)
        except self._WsError as e:
            return e.to_response()

    # ---------------------------------------------------------------------
    # Mock-only query helpers (sqlite-backed)
    # ---------------------------------------------------------------------

    def resolve_customer_id(self, q: str) -> int | None:
        """
        Resolve a customer name/code to a TRDR id in the mock DB.

        Tries exact match first, then LIKE match. Returns None if not found.
        """
        q = q.strip()
        if not q:
            return None

        conn = sqlite3.connect(self._db_path)
        conn.row_factory = sqlite3.Row
        try:
            row = conn.execute(
                "SELECT trdr AS id FROM customers WHERE code = ? OR name = ? ORDER BY trdr LIMIT 1",
                (q, q),
            ).fetchone()
            if row:
                return int(row["id"])

            row = conn.execute(
                "SELECT trdr AS id FROM customers WHERE code LIKE ? OR name LIKE ? ORDER BY trdr LIMIT 1",
                (f"%{q}%", f"%{q}%"),
            ).fetchone()
            return int(row["id"]) if row else None
        finally:
            conn.close()

    def resolve_item_id(self, q: str) -> int | None:
        """
        Resolve an item name/code to an item id in the mock DB.

        Tries exact match first, then LIKE match. Returns None if not found.
        """
        q = q.strip()
        if not q:
            return None

        conn = sqlite3.connect(self._db_path)
        conn.row_factory = sqlite3.Row
        try:
            row = conn.execute(
                "SELECT id AS id FROM items WHERE code = ? OR name = ? ORDER BY id LIMIT 1",
                (q, q),
            ).fetchone()
            if row:
                return int(row["id"])

            row = conn.execute(
                "SELECT id AS id FROM items WHERE code LIKE ? OR name LIKE ? ORDER BY id LIMIT 1",
                (f"%{q}%", f"%{q}%"),
            ).fetchone()
            return int(row["id"]) if row else None
        finally:
            conn.close()

    def search_customers(self, *, q: str, limit: int | None = None) -> list[dict[str, Any]]:
        q = q.strip()
        if not q:
            return []

        lim = int(limit) if limit is not None else 10

        conn = sqlite3.connect(self._db_path)
        conn.row_factory = sqlite3.Row
        try:
            rows = conn.execute(
                "SELECT trdr AS id, code, name, afm "
                "FROM customers "
                "WHERE code LIKE ? OR name LIKE ? OR afm LIKE ? "
                "ORDER BY trdr "
                "LIMIT ?",
                (f"%{q}%", f"%{q}%", f"%{q}%", lim),
            ).fetchall()
            return [
                {
                    "id": int(r["id"]),
                    "code": r["code"],
                    "name": r["name"],
                    "afm": r["afm"],
                }
                for r in rows
            ]
        finally:
            conn.close()

    def search_items(self, *, q: str, limit: int | None = None) -> list[dict[str, Any]]:
        q = q.strip()
        if not q:
            return []

        lim = int(limit) if limit is not None else 10

        conn = sqlite3.connect(self._db_path)
        conn.row_factory = sqlite3.Row
        try:
            rows = conn.execute(
                "SELECT id, code, name, price, stock, reserved "
                "FROM items "
                "WHERE code LIKE ? OR name LIKE ? "
                "ORDER BY id "
                "LIMIT ?",
                (f"%{q}%", f"%{q}%", lim),
            ).fetchall()
            return [
                {
                    "id": int(r["id"]),
                    "code": r["code"],
                    "name": r["name"],
                    "price": float(r["price"]),
                    "stock": int(r["stock"]),
                    "reserved": int(r["reserved"]),
                }
                for r in rows
            ]
        finally:
            conn.close()

    def list_invoices(
        self, *, status: str = "", customer_id: int | None = None
    ) -> list[dict[str, Any]]:
        status = status.strip()

        where: list[str] = []
        params: list[Any] = []
        if status:
            where.append("status = ?")
            params.append(status)
        if customer_id is not None:
            where.append("customer_id = ?")
            params.append(int(customer_id))

        sql = (
            "SELECT id, customer_id, order_id, amount, status, created_at "
            "FROM invoices_business"
        )
        if where:
            sql += " WHERE " + " AND ".join(where)
        sql += " ORDER BY id DESC"

        conn = sqlite3.connect(self._db_path)
        conn.row_factory = sqlite3.Row
        try:
            rows = conn.execute(sql, params).fetchall()
            return [
                {
                    "id": int(r["id"]),
                    "customer_id": int(r["customer_id"]),
                    "order_id": r["order_id"],
                    "amount": float(r["amount"]),
                    "status": r["status"],
                    "created_at": r["created_at"],
                }
                for r in rows
            ]
        finally:
            conn.close()

    def list_orders(
        self,
        *,
        status: str = "",
        customer_id: int | None = None,
        limit: int | None = None,
    ) -> list[dict[str, Any]]:
        status = status.strip()

        where: list[str] = []
        params: list[Any] = []
        if status:
            where.append("status = ?")
            params.append(status)
        if customer_id is not None:
            where.append("customer_id = ?")
            params.append(int(customer_id))

        sql = "SELECT id, customer_id, status, total, created_at FROM orders"
        if where:
            sql += " WHERE " + " AND ".join(where)
        sql += " ORDER BY id DESC"
        if limit is not None:
            sql += " LIMIT ?"
            params.append(int(limit))

        conn = sqlite3.connect(self._db_path)
        conn.row_factory = sqlite3.Row
        try:
            rows = conn.execute(sql, params).fetchall()
            return [
                {
                    "id": int(r["id"]),
                    "customer_id": int(r["customer_id"]),
                    "status": r["status"],
                    "total": float(r["total"]),
                    "created_at": r["created_at"],
                }
                for r in rows
            ]
        finally:
            conn.close()

    def list_payments_for_invoice(self, invoice_id: int) -> list[dict[str, Any]]:
        conn = sqlite3.connect(self._db_path)
        conn.row_factory = sqlite3.Row
        try:
            rows = conn.execute(
                "SELECT id, invoice_id, amount, payment_date "
                "FROM payments WHERE invoice_id = ? ORDER BY id",
                (int(invoice_id),),
            ).fetchall()
            return [
                {
                    "id": int(r["id"]),
                    "invoice_id": int(r["invoice_id"]),
                    "amount": float(r["amount"]),
                    "payment_date": r["payment_date"],
                }
                for r in rows
            ]
        finally:
            conn.close()

