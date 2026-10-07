"""Web UI backend: turn diff over the mock DB, and the HTTP API driven by a fake orchestrator."""

from __future__ import annotations

import sqlite3
from pathlib import Path

from agent_platform.web.db import diff, snapshot
from mock_db.create_and_seed import build_db


def test_turn_diff_reports_inserts_updates_deletes(tmp_path: Path) -> None:
    db = tmp_path / "mock.db"
    build_db(db)
    before = snapshot(db)
    conn = sqlite3.connect(db)
    conn.execute("UPDATE orders SET status = 'Confirmed' WHERE id = 5005")
    conn.execute("INSERT INTO order_items (order_id, product_id, quantity, price) VALUES (5001, 1005, 3, 9.5)")
    conn.execute("DELETE FROM payments WHERE id = 1")
    conn.commit()
    conn.close()

    changes = {(c["table"], c["op"]): c for c in diff(before, snapshot(db))}
    assert set(changes) == {("orders", "update"), ("order_items", "insert"), ("payments", "delete")}
    upd = changes[("orders", "update")]
    assert upd["key"] == [5005] and upd["changed"] == ["status"] and upd["after"]["status"] == "Confirmed"
    assert changes[("order_items", "insert")]["key"] == [5001, 1005]  # composite primary key
    assert changes[("payments", "delete")]["after"] is None


def test_no_changes_is_an_empty_diff(tmp_path: Path) -> None:
    db = tmp_path / "mock.db"
    build_db(db)
    assert diff(snapshot(db), snapshot(db)) == []
