"""Write gate: writes need an explicit yes, approve only what was blocked, once."""

from __future__ import annotations

import asyncio

import pytest

pytest.importorskip("langgraph")

from agent_platform.gate import READ_PREFIXES, WRITE_TOOLS, WriteGate, is_approval
from agent_platform.graph import GATE_KEY, build_orchestrator
from agent_platform.runtimes.base import RunContext
from tests.test_agent_layer import FakeRuntime


def test_every_server_tool_is_a_known_write_or_a_read() -> None:
    # A new write tool must be added to WRITE_TOOLS, or it would run ungated.
    from softone_mcp.server import mcp

    names = {t.name for t in asyncio.run(mcp.list_tools())}
    unclassified = {n for n in names - WRITE_TOOLS if not n.startswith(READ_PREFIXES)}
    assert unclassified <= {"softone_connect_default", "get_context"}
    assert WRITE_TOOLS <= names


@pytest.mark.parametrize("text", ["yes", "Yes, go", "y", "ok", "go ahead", "confirm", "approve it"])
def test_approval_words(text: str) -> None:
    assert is_approval(text)


@pytest.mark.parametrize("text", ["no", "wait", "make it 2 units", "yesterday's orders", ""])
def test_non_approvals(text: str) -> None:
    assert not is_approval(text)


def test_yes_approves_only_blocked_tools_once() -> None:
    g = WriteGate()
    g.start_turn("create an order for 47")
    assert g.check("get_customer", {}) is None  # reads always pass
    assert g.check("create_order", {"customer_id": 47}) is not None

    g.start_turn("yes")
    assert g.check("create_order", {"customer_id": 47}) is None
    assert g.check("create_order", {"customer_id": 47}) is not None  # single use
    assert g.check("delete_customer", {"customer_id_or_name": 47}) is not None  # never approved


def test_duplicate_call_after_approval_never_writes_twice() -> None:
    g = WriteGate()
    g.start_turn("create an order")
    g.check("create_order", {"customer_id": 47})
    g.start_turn("yes")
    assert g.check("create_order", {"customer_id": 47}) is None
    assert "already ran" in g.check("create_order", {"customer_id": 47})
    assert not g.blocked  # a duplicate isn't presented as a new approval


def test_session_id_is_not_part_of_call_identity() -> None:
    g = WriteGate()
    g.start_turn("pay")
    g.check("record_payment", {"session_id": "A", "invoice_id": 2})
    g.start_turn("yes")
    assert g.check("record_payment", {"session_id": "A", "invoice_id": 2}) is None
    assert "already ran" in g.check("record_payment", {"session_id": "B", "invoice_id": 2})


def test_any_other_reply_clears_pending_approval() -> None:
    g = WriteGate()
    g.start_turn("create an order")
    g.check("create_order", {})
    g.start_turn("actually, wait")
    g.start_turn("yes")
    assert g.check("create_order", {}) is not None


class WritingRuntime(FakeRuntime):
    """Tries to create an order every turn, like a model that has all the inputs."""

    async def run_turn(self, *, spec, user_text: str, context: RunContext) -> str:  # type: ignore[override]
        blocked = context.gate.check("create_order", {"session_id": "S", "customer_id": 47})
        return "waiting for approval" if blocked else "order 5003 created"


def test_orchestrator_blocks_then_runs_write_after_yes_in_same_department() -> None:
    app = build_orchestrator(ollama=WritingRuntime("ollama"), claude=FakeRuntime("claude"))
    state = asyncio.run(app.ainvoke({"artifacts": {}, "user_text": "create an order for customer 47"}))
    assert state["route"] == "sales"
    assert 'create_order({"customer_id": 47})' in state["response"]  # exact call shown, session_id hidden

    state = asyncio.run(app.ainvoke({**state, "user_text": "yes"}))
    assert state["route"] == "sales"  # "yes" has no department words but stays with sales
    assert state["response"] == "order 5003 created"
    assert not state["artifacts"][GATE_KEY].blocked


def test_ollama_wrapper_blocks_write_without_calling_mcp() -> None:
    from pydantic import BaseModel

    from agent_platform.runtimes.ollama import _wrap_tool

    class Args(BaseModel):
        customer_id: int

    class FakeMcpTool:
        name, description, args_schema = "create_order", "", Args
        calls = 0

        async def ainvoke(self, kwargs):
            FakeMcpTool.calls += 1
            return {"ok": True, "data": {"order_id": 5003}}

    gate = WriteGate()
    gate.start_turn("create an order")
    out = asyncio.run(_wrap_tool(FakeMcpTool(), gate=gate, debug=False).ainvoke({"customer_id": 47}))
    assert "BLOCKED" in str(out) and FakeMcpTool.calls == 0

    gate.start_turn("yes")
    out = asyncio.run(_wrap_tool(FakeMcpTool(), gate=gate, debug=False).ainvoke({"customer_id": 47}))
    assert FakeMcpTool.calls == 1 and "5003" in str(out)


def test_claude_permission_callback_gates_writes_and_enforces_allowlist() -> None:
    from claude_agent_sdk import PermissionResultAllow, PermissionResultDeny

    from agent_platform.mcp_tools import mcp_prefixed_tool_name as mcp
    from agent_platform.runtimes.claude import ClaudeSdkRuntime
    from agent_platform.specs import SPECS

    runtime = ClaudeSdkRuntime()
    runtime._spec = SPECS["finance"]

    def ask(tool: str) -> object:
        return asyncio.run(runtime._can_use_tool(tool, {"invoice_id": 1, "amount": 10}, None))

    assert isinstance(ask(mcp("softone_connect_default")), PermissionResultAllow)
    assert isinstance(ask(mcp("get_invoice")), PermissionResultAllow)
    assert isinstance(ask(mcp("create_order")), PermissionResultDeny)  # sales tool, not finance's
    assert isinstance(ask("Bash"), PermissionResultDeny)
    denied = ask(mcp("record_payment"))
    assert isinstance(denied, PermissionResultDeny) and "BLOCKED" in denied.message

    runtime._gate.start_turn("yes")
    assert isinstance(ask(mcp("record_payment")), PermissionResultAllow)

    runtime._spec = SPECS["sales"]  # department switch: same client, different allowlist
    assert isinstance(ask(mcp("get_invoice")), PermissionResultDeny)
