from __future__ import annotations

import asyncio
from dataclasses import dataclass, field

import pytest

# Agent-platform orchestrator depends on langgraph; skip these tests if not installed.
pytest.importorskip("langgraph")

from agent_platform.graph import SESSION_ID_KEY, RuntimePolicy, build_orchestrator
from agent_platform.mcp_tools import CONNECT_TOOL_NAME, MCP_SERVER_NAME, claude_allowed_tools_for_agent
from agent_platform.prompting import PromptPolicy, build_system_prompt
from agent_platform.runtimes.base import BAD_TOOL_INPUT, RunContext, RuntimeAdapter, ToolError
from agent_platform.specs import SPECS


def test_build_system_prompt_dedups_resources_and_includes_envelope() -> None:
    policy = PromptPolicy()
    prompt = build_system_prompt(
        base="BASE",
        session_instruction="SESSION",
        policy=policy,
        extra_resource_uris=("softone://capabilities", "softone://contracts/order"),
    )

    # De-duped: capabilities appears once even though it's in defaults + extras.
    assert prompt.count("softone://capabilities") == 1
    assert "softone://contracts/order" in prompt
    assert "TOOL RESPONSE ENVELOPE" in prompt
    assert prompt.endswith("\n")


def test_claude_allowed_tools_prefixes_and_includes_connect() -> None:
    allowed = claude_allowed_tools_for_agent(("get_customer", "get_customer", "create_order"))
    assert allowed[0] == f"mcp__{MCP_SERVER_NAME}__{CONNECT_TOOL_NAME}"
    assert allowed.count(f"mcp__{MCP_SERVER_NAME}__get_customer") == 1
    assert f"mcp__{MCP_SERVER_NAME}__create_order" in allowed


@dataclass
class FakeRuntime(RuntimeAdapter):
    """Records which department ran; optionally fails like a real tool error."""

    name: str
    fail: bool = False
    error_code: str = BAD_TOOL_INPUT
    seen: list[str] = field(default_factory=list)

    async def ensure_connected(self, context: RunContext) -> None:
        context.session_id = context.session_id or "SID-123"

    async def run_turn(self, *, spec, user_text: str, context: RunContext) -> str:  # type: ignore[override]
        self.seen.append(spec.name)
        if self.fail:
            raise ToolError(tool_name="create_order", error={"code": self.error_code, "message": "boom"})
        return f"{spec.name}: {user_text}"


def _turn(app, state: dict, text: str) -> dict:
    return asyncio.run(app.ainvoke({**state, "user_text": text}))  # type: ignore[attr-defined]


def test_routes_each_request_to_its_department() -> None:
    ollama, claude = FakeRuntime("ollama"), FakeRuntime("claude")
    app = build_orchestrator(ollama=ollama, claude=claude)
    state: dict = {"artifacts": {}}
    for text in ("approve order 5001", "check stock for item 1001", "list unpaid invoices"):
        state = _turn(app, state, text)
    assert ollama.seen == ["sales", "inventory", "finance"]
    assert claude.seen == []


def test_clarify_then_department_reply_runs_original_request() -> None:
    ollama = FakeRuntime("ollama")
    app = build_orchestrator(ollama=ollama, claude=FakeRuntime("claude"))
    state = _turn(app, {"artifacts": {}}, "orders and invoices for customer 47")
    assert state["route"] == "clarify" and ollama.seen == []

    state = _turn(app, state, "finance")
    assert state["route"] == "finance"
    assert state["response"] == "finance: orders and invoices for customer 47"


def test_tool_error_escalates_that_turn_only() -> None:
    ollama, claude = FakeRuntime("ollama", fail=True), FakeRuntime("claude")
    app = build_orchestrator(ollama=ollama, claude=claude)
    state = _turn(app, {"artifacts": {}}, "approve order 5001")
    assert state["runtime"] == "claude" and claude.seen == ["sales"]
    assert "Latest user message: approve order 5001" in state["response"]  # Claude got the handoff context

    ollama.fail = False
    state = _turn(app, state, "approve order 5002")
    assert state["runtime"] == "ollama"  # escalation isn't sticky


def test_business_rule_error_is_relayed_not_escalated() -> None:
    ollama = FakeRuntime("ollama", fail=True, error_code="INVALID_STATUS")
    claude = FakeRuntime("claude")
    state = _turn(build_orchestrator(ollama=ollama, claude=claude), {"artifacts": {}}, "approve order 5001")
    assert state["runtime"] == "ollama" and "boom" in state["response"] and claude.seen == []


def test_tool_error_without_escalation_asks_user() -> None:
    app = build_orchestrator(
        ollama=FakeRuntime("ollama", fail=True), claude=FakeRuntime("claude"), policy=RuntimePolicy(escalate_to=None)
    )
    state = _turn(app, {"artifacts": {}}, "approve order 5001")
    assert state["runtime"] == "ollama" and "boom" in state["response"]


def test_session_id_persisted_for_ollama_only() -> None:
    app = build_orchestrator(ollama=FakeRuntime("ollama"), claude=FakeRuntime("claude"))
    assert _turn(app, {"artifacts": {}}, "approve order 5001")["artifacts"][SESSION_ID_KEY] == "SID-123"

    app2 = build_orchestrator(ollama=FakeRuntime("ollama"), claude=FakeRuntime("claude"), policy=RuntimePolicy(default="claude"))
    assert SESSION_ID_KEY not in _turn(app2, {"artifacts": {}}, "approve order 5001")["artifacts"]


def test_department_specs_reference_real_mcp_tools() -> None:
    from softone_mcp.server import mcp

    real = {t.name for t in asyncio.run(mcp.list_tools())}
    for spec in SPECS.values():
        assert set(spec.tool_names) <= real, spec.name
    assert {"workflow_create_order", "workflow_order_to_cash"} <= set(SPECS["sales"].tool_names)
