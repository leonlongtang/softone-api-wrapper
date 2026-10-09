"""Web UI backend: turn diff over the mock DB, and the HTTP API driven by a fake orchestrator."""

from __future__ import annotations

import sqlite3
from contextlib import asynccontextmanager, closing
from pathlib import Path

import pytest

pytest.importorskip("langgraph")

from starlette.testclient import TestClient

from agent_platform.gate import WriteGate
from agent_platform.graph import GATE_KEY
from agent_platform.web.db import diff, snapshot
from agent_platform.web.server import create_app
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


class FakeOrchestrator:
    """Blocks create_order until "yes", then writes it to the DB, like a real agent behind the gate."""

    def __init__(self, db: Path) -> None:
        self.db = db

    async def ainvoke(self, state: dict) -> dict:
        gate = state["artifacts"].setdefault(GATE_KEY, WriteGate())
        gate.start_turn(state["user_text"])
        if gate.check("create_order", {"customer_id": 47}) is None:
            with closing(sqlite3.connect(self.db)) as conn, conn:  # commit, then close (Windows locks open files)
                conn.execute("INSERT INTO orders (id, customer_id, status, total) VALUES (5006, 47, 'Draft', 0)")
        response = f"done\n\n{gate.pending_summary()}" if gate.blocked else "done"  # as graph.run_agent_node does
        return {**state, "route": "sales", "runtime": "fake", "response": response}


def test_api_turns_report_trace_pending_and_diff(tmp_path: Path) -> None:
    db = tmp_path / "mock.db"
    build_db(db)

    @asynccontextmanager
    async def open_chat(runtime: str):
        yield FakeOrchestrator(db)

    with TestClient(create_app(open_chat=open_chat, db_path=db)) as client:
        assert client.post("/api/chat", json={"runtime": "ollama"}).json()["ready"]
        assert any(t["write"] for t in client.get("/api/info").json()["tools"]["sales"])

        first = client.post("/api/turn", json={"text": "create an order"}).json()
        assert first["pending"] and first["diff"] == []
        assert first["response"] == "done"  # the page's approval card replaces the CLI's "Needs your approval" text
        assert first["trace"] == [{"tool": "create_order", "args": {"customer_id": 47}, "status": "blocked"}]

        second = client.post("/api/turn", json={"text": "yes"}).json()
        assert not second["pending"] and second["trace"][0]["status"] == "ran"
        assert [(c["table"], c["op"], c["key"]) for c in second["diff"]] == [("orders", "insert", [5006])]
        assert any(r["id"] == 5006 for r in client.get("/api/db").json()["orders"])

        client.post("/api/reset")
        assert not any(r["id"] == 5006 for r in client.get("/api/db").json()["orders"])
