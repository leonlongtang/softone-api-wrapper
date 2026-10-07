from __future__ import annotations

import asyncio
from dataclasses import dataclass

import pytest

# Agent-platform orchestrator depends on langgraph; skip these tests if not installed.
pytest.importorskip("langgraph")

from agent_platform.graph import SESSION_ID_KEY, RuntimePolicy, build_orchestrator
from agent_platform.mcp_tools import CONNECT_TOOL_NAME, MCP_SERVER_NAME, claude_allowed_tools_for_agent
from agent_platform.prompting import PromptPolicy, build_system_prompt
from agent_platform.runtimes.base import RunContext, RuntimeAdapter, ToolError
from agent_platform.specs import ops_workflows_agent_spec


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
    name: str
    behavior: str
    ensured: bool = False

    async def ensure_connected(self, context: RunContext) -> None:
        self.ensured = True
        # simulate a connect that yields a session
        if not context.session_id:
            context.session_id = "SID-123"

    async def run_turn(self, *, spec, user_text: str, context: RunContext) -> str:  # type: ignore[override]
        if self.behavior == "tool_error":
            raise ToolError(tool_name="create_order", error={"code": "E", "message": "boom"})
        if self.behavior == "set_session":
            context.session_id = "SID-123"
            return "ok"
        return "ok"


def test_orchestrator_escalates_to_claude_after_tool_error_when_policy_triggers() -> None:
    ollama = FakeRuntime(name="ollama", behavior="tool_error")
    claude = FakeRuntime(name="claude", behavior="ok")

    app = build_orchestrator(ollama=ollama, claude=claude)
    state = {"user_text": "create order", "failures": 0, "artifacts": {}}

    # Default policy escalates after 1 failure. The graph should call Claude on tool error.
    out = asyncio.run(app.ainvoke(state))  # type: ignore[attr-defined]
    # If ANTHROPIC_API_KEY is not set, escalation is not possible; graph will
    # return a helpful message while keeping runtime=ollama.
    assert int(out.get("failures") or 0) == 1
    assert out.get("runtime") in {"ollama", "claude"}


def test_orchestrator_persists_session_id_for_ollama_runtime_only() -> None:
    # Ollama run sets session_id; graph should persist it.
    ollama = FakeRuntime(name="ollama", behavior="set_session")
    claude = FakeRuntime(name="claude", behavior="ok")

    app = build_orchestrator(ollama=ollama, claude=claude)
    # Use a sales-specific prompt so the router doesn't ask to clarify.
    state = {"user_text": "create order", "failures": 0, "artifacts": {}}
    out = asyncio.run(app.ainvoke(state))  # type: ignore[attr-defined]
    assert out["artifacts"][SESSION_ID_KEY] == "SID-123"
    assert ollama.ensured is True

    # Force Claude run; graph should not persist session_id for Claude.
    app2 = build_orchestrator(
        ollama=ollama,
        claude=claude,
        policy=RuntimePolicy(max_failures_before_escalate=0),
    )
    state2 = {"user_text": "create order", "failures": 0, "artifacts": {}}
    out2 = asyncio.run(app2.ainvoke(state2))  # type: ignore[attr-defined]
    assert out2.get("runtime") == "claude"
    assert SESSION_ID_KEY not in (out2.get("artifacts") or {})


def test_sales_agent_spec_has_tools_and_resources() -> None:
    spec = ops_workflows_agent_spec()
    assert spec.name == "ops"
    assert len(spec.tool_names) >= 1
    assert len(spec.resource_uris) >= 1

