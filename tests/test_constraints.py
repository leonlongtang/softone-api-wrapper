"""Schema-level rules: CHECK, FK behavior, partial unique indexes.

These tests bypass the WS layer (raw sqlite3 connection) so they verify
the *storage* contract independently of the brain validators in
`mock_db/ws/objects/validators.py`. If a brain validator is removed, the
schema must still reject bad data -- that's defense in depth.
"""
from __future__ import annotations

import sqlite3

import pytest


# ---------------------------------------------------------------------------
# CHECK constraints
# ---------------------------------------------------------------------------

class TestCheckConstraints:
    def test_orders_status_must_be_draft_or_confirmed(self, raw_conn: sqlite3.Connection) -> None:
        with pytest.raises(sqlite3.IntegrityError, match="status"):
            raw_conn.execute(
                "INSERT INTO orders(id, customer_id, status, total) VALUES (9001, 47, 'pending', 100)"
            )

    def test_items_stock_cannot_be_negative(self, raw_conn: sqlite3.Connection) -> None:
        with pytest.raises(sqlite3.IntegrityError, match="stock"):
            raw_conn.execute(
                "INSERT INTO items(id, code, name, price, stock, reserved) VALUES (9001,'X','x',1,-1,0)"
            )

    def test_items_reserved_cannot_be_negative(self, raw_conn: sqlite3.Connection) -> None:
        with pytest.raises(sqlite3.IntegrityError, match="reserved"):
            raw_conn.execute(
                "INSERT INTO items(id, code, name, price, stock, reserved) VALUES (9002,'Y','y',1,5,-1)"
            )

    def test_order_items_quantity_must_be_positive(self, raw_conn: sqlite3.Connection) -> None:
        with pytest.raises(sqlite3.IntegrityError, match="quantity"):
            raw_conn.execute(
                "INSERT INTO order_items(order_id, product_id, quantity, price) VALUES (5005, 1002, 0, 25)"
            )

    def test_order_items_price_cannot_be_negative(self, raw_conn: sqlite3.Connection) -> None:
        with pytest.raises(sqlite3.IntegrityError, match="price"):
            raw_conn.execute(
                "INSERT INTO order_items(order_id, product_id, quantity, price) VALUES (5005, 1003, 1, -1)"
            )

    def test_payments_amount_must_be_strictly_positive(self, raw_conn: sqlite3.Connection) -> None:
        with pytest.raises(sqlite3.IntegrityError, match="amount"):
            raw_conn.execute("INSERT INTO payments(invoice_id, amount) VALUES (1, 0)")
        with pytest.raises(sqlite3.IntegrityError, match="amount"):
            raw_conn.execute("INSERT INTO payments(invoice_id, amount) VALUES (1, -50)")

    def test_invoices_amount_cannot_be_negative(self, raw_conn: sqlite3.Connection) -> None:
        with pytest.raises(sqlite3.IntegrityError, match="amount"):
            raw_conn.execute(
                "INSERT INTO invoices_business(id, customer_id, amount) VALUES (9001, 47, -1)"
            )

    def test_invoices_status_vocabulary(self, raw_conn: sqlite3.Connection) -> None:
        with pytest.raises(sqlite3.IntegrityError, match="status"):
            raw_conn.execute(
                "INSERT INTO invoices_business(id, customer_id, amount, status) "
                "VALUES (9002, 47, 1, 'cancelled')"
            )


# ---------------------------------------------------------------------------
# FK behavior (RESTRICT vs CASCADE)
# ---------------------------------------------------------------------------

class TestForeignKeyBehavior:
    def test_cannot_delete_item_referenced_by_order_line(self, raw_conn: sqlite3.Connection) -> None:
        # Item 1001 is on order 5001's line. Schema is ON DELETE RESTRICT
        # (the bug we fixed two turns ago -- used to be CASCADE).
        with pytest.raises(sqlite3.IntegrityError):
            raw_conn.execute("DELETE FROM items WHERE id = 1001")

    def test_cannot_delete_customer_with_orders(self, raw_conn: sqlite3.Connection) -> None:
        with pytest.raises(sqlite3.IntegrityError):
            raw_conn.execute("DELETE FROM customers WHERE trdr = 47")

    def test_cannot_delete_order_with_invoice(self, raw_conn: sqlite3.Connection) -> None:
        # Order 5001 has invoice 1.
        with pytest.raises(sqlite3.IntegrityError):
            raw_conn.execute("DELETE FROM orders WHERE id = 5001")

    def test_deleting_draft_order_cascades_to_lines(self, raw_conn: sqlite3.Connection) -> None:
        # Order 5005 is Draft and has no invoice -- order_items should
        # cascade away with the order.
        before = raw_conn.execute(
            "SELECT COUNT(*) FROM order_items WHERE order_id = 5005"
        ).fetchone()[0]
        assert before > 0, "seed expectation: order 5005 has lines"

        raw_conn.execute("DELETE FROM orders WHERE id = 5005")

        after = raw_conn.execute(
            "SELECT COUNT(*) FROM order_items WHERE order_id = 5005"
        ).fetchone()[0]
        assert after == 0

    def test_deleting_invoice_cascades_to_payments(self, raw_conn: sqlite3.Connection) -> None:
        # payments.invoice_id is intentionally ON DELETE CASCADE (mock-cleanup
        # convenience). If we ever flip this to RESTRICT we should know.
        before = raw_conn.execute(
            "SELECT COUNT(*) FROM payments WHERE invoice_id = 1"
        ).fetchone()[0]
        assert before > 0

        raw_conn.execute("DELETE FROM invoices_business WHERE id = 1")

        after = raw_conn.execute(
            "SELECT COUNT(*) FROM payments WHERE invoice_id = 1"
        ).fetchone()[0]
        assert after == 0


# ---------------------------------------------------------------------------
# Partial unique indexes
# ---------------------------------------------------------------------------

class TestPartialUniqueIndexes:
    def test_one_invoice_per_order_id(self, raw_conn: sqlite3.Connection) -> None:
        # Order 5001 already has invoice 1 from the seed.
        with pytest.raises(sqlite3.IntegrityError, match="order_id"):
            raw_conn.execute(
                "INSERT INTO invoices_business(id, customer_id, order_id, amount, status) "
                "VALUES (9001, 47, 5001, 100, 'unpaid')"
            )

    def test_multiple_ad_hoc_invoices_for_same_customer_allowed(
        self, raw_conn: sqlite3.Connection
    ) -> None:
        # NULL order_id is excluded from the partial index by design --
        # ad-hoc invoices coexist freely.
        raw_conn.execute(
            "INSERT INTO invoices_business(id, customer_id, order_id, amount, status) "
            "VALUES (9100, 51, NULL, 50, 'unpaid')"
        )
        raw_conn.execute(
            "INSERT INTO invoices_business(id, customer_id, order_id, amount, status) "
            "VALUES (9101, 51, NULL, 75, 'unpaid')"
        )

    def test_afm_unique_when_present(self, raw_conn: sqlite3.Connection) -> None:
        # Customer 47 has AFM '999863881' from seed.
        with pytest.raises(sqlite3.IntegrityError, match="afm"):
            raw_conn.execute(
                "INSERT INTO customers(trdr, code, name, afm) "
                "VALUES (9001, '900', 'Dup', '999863881')"
            )

    def test_multiple_customers_with_null_afm_allowed(
        self, raw_conn: sqlite3.Connection
    ) -> None:
        # NULL is excluded from the partial index. Real ERP semantics:
        # unregistered counterparts are allowed.
        raw_conn.execute(
            "INSERT INTO customers(trdr, code, name, afm) VALUES (9100, '910', 'NoAfm A', NULL)"
        )
        raw_conn.execute(
            "INSERT INTO customers(trdr, code, name, afm) VALUES (9101, '911', 'NoAfm B', NULL)"
        )
