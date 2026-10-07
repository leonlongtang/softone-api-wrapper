"""LangGraph orchestrator: route each turn, run the agent, recover or escalate on tool errors."""

from __future__ import annotations

import os
from contextlib import AsyncExitStack, asynccontextmanager
from dataclasses import dataclass
from typing import Any, AsyncIterator, Callable, TypedDict

from langgraph.constants import END, START
from langgraph.graph.state import StateGraph

from agent_platform.gate import WriteGate
from agent_platform.router import CLARIFY_QUESTION, DEPARTMENTS, hybrid_route
from agent_platform.runtimes.base import BAD_TOOL_INPUT, HISTORY_KEY, RunContext, RuntimeAdapter, ToolError
from agent_platform.specs import SPECS, AgentSpec

SESSION_ID_KEY = "session_id"
PENDING_USER_TEXT_KEY = "pending_user_text"
LAST_ROUTE_KEY = "last_route"
GATE_KEY = "write_gate"


class OrchestratorState(TypedDict, total=False):
    user_text: str
    route: str  # a department, or "clarify"
    runtime: str  # which runtime answered: "ollama", "claude", or "router" for a clarify
    response: str
    # Cross-turn state: session_id, pending clarify text, last department, write gate, history.
    artifacts: dict[str, Any]


@dataclass(frozen=True, slots=True)
class RuntimePolicy:
    """Cost-aware runtime choice: run on `default`; rerun a turn whose tool call failed on `escalate_to`."""

    default: str = "ollama"
    escalate_to: str | None = "claude"


def _looks_like_session_error(err: dict) -> bool:
    msg = str(err.get("message") or "").lower()
    code = err.get("code")
    # Keep this conservative: only reconnect on obvious auth/session failures.
    if isinstance(code, int) and code in {-401, 401, 403}:
        return True
    if any(k in msg for k in ("session", "not authenticated", "unauthorized", "forbidden", "auth")):
        return True
    return False


def _transcript(artifacts: dict[str, Any], last: int = 8) -> str:
    """Plain-text tail of the shared conversation (user and assistant turns only)."""
    msgs = [m for m in artifacts.get(HISTORY_KEY) or [] if getattr(m, "type", "") in ("human", "ai") and m.content]
    lines = [f"{'User' if m.type == 'human' else 'Assistant'}: {m.content}" for m in msgs[-last:]]
    return "\n".join(lines) or "(none)"


def build_orchestrator(
    *,
    ollama: RuntimeAdapter,
    claude: RuntimeAdapter,
    policy: RuntimePolicy | None = None,
    router: Callable[[str], str] = hybrid_route,
):
    policy = policy or RuntimePolicy()

    async def router_node(state: OrchestratorState) -> OrchestratorState:
        text = (state.get("user_text") or "").strip()
        artifacts = state.setdefault("artifacts", {})
        artifacts.setdefault(GATE_KEY, WriteGate()).start_turn(text)
        pending = artifacts.pop(PENDING_USER_TEXT_KEY, None)

        if pending and text.lower() in DEPARTMENTS:
            # Reply to a clarify: send the original request to the chosen department.
            state["route"], state["user_text"] = text.lower(), pending
        else:
            route = router(text)
            # Follow-ups without department words ("yes", "47") stay with the current department.
            state["route"] = artifacts.get(LAST_ROUTE_KEY, "clarify") if route == "unknown" else route

        if state["route"] in DEPARTMENTS:
            artifacts[LAST_ROUTE_KEY] = state["route"]
        else:
            state["route"], state["runtime"], state["response"] = "clarify", "router", CLARIFY_QUESTION
            artifacts[PENDING_USER_TEXT_KEY] = text
        return state

    async def run(runtime_name: str, spec: AgentSpec, state: OrchestratorState, text: str | None = None) -> str:
        runtime = claude if runtime_name == "claude" else ollama
        artifacts = state["artifacts"]
        # Only Ollama keeps a host-managed MCP session; Claude connects inside its own MCP subprocess.
        ctx = RunContext(
            session_id=artifacts.get(SESSION_ID_KEY) if runtime_name == "ollama" else None,
            artifacts=artifacts,
            gate=artifacts[GATE_KEY],
        )
        ensure_connected = getattr(runtime, "ensure_connected", None)
        if ensure_connected:
            await ensure_connected(ctx)
        reply = await runtime.run_turn(spec=spec, user_text=text or state.get("user_text") or "", context=ctx)
        if runtime_name == "ollama" and ctx.session_id:
            artifacts[SESSION_ID_KEY] = ctx.session_id
        state["runtime"] = runtime_name
        return reply

    async def run_agent_node(state: OrchestratorState) -> OrchestratorState:
        if state["route"] == "clarify":
            return state
        state = await run_with_recovery(state)
        # Show the exact blocked write calls ourselves rather than trusting the model's summary.
        if pending := state["artifacts"][GATE_KEY].pending_summary():
            state["response"] = f"{(state.get('response') or '').rstrip()}\n\n{pending}"
        return state

    async def run_with_recovery(state: OrchestratorState) -> OrchestratorState:
        spec = SPECS[state["route"]]
        runtime_name = policy.default
        try:
            state["response"] = await run(runtime_name, spec, state)
            return state
        except ToolError as te:
            error = te
            if runtime_name == "ollama" and _looks_like_session_error(te.error):
                # Session expired: reconnect once and rerun the same turn.
                state["artifacts"].pop(SESSION_ID_KEY, None)
                try:
                    state["response"] = await run(runtime_name, spec, state)
                    return state
                except ToolError as retry_te:
                    error = retry_te

        msg = str(error.error.get("message") or error)
        details = error.error.get("details")
        msg += f"\nDetails: {details}" if details else ""

        escalate_to = policy.escalate_to
        # Only a model mistake (malformed tool input) is worth a stronger model. A business-rule
        # error ("invoice needs a confirmed order") is the answer: relay it to the user.
        if escalate_to in (None, runtime_name) or error.error.get("code") != BAD_TOOL_INPUT:
            state["runtime"] = runtime_name
            state["response"] = f"{msg}\n\nTell me how you want to adjust the inputs, and I'll retry."
            return state
        try:
            # Claude has its own MCP session and no memory of the local conversation: hand it the context.
            handoff = (
                f"A local model failed this request with a tool error: {msg}\n\n"
                f"Recent conversation:\n{_transcript(state['artifacts'])}\n\n"
                f"Latest user message: {state.get('user_text') or ''}"
            )
            state["response"] = await run(escalate_to, spec, state, text=handoff)
        except Exception as exc:  # noqa: BLE001 - report any escalation failure to the user
            state["runtime"] = runtime_name
            state["response"] = f"{msg}\n\nEscalation to {escalate_to} failed: {exc}"
        return state

    graph = StateGraph(OrchestratorState)
    graph.add_node("router", router_node)
    graph.add_node("run_agent", run_agent_node)
    graph.add_edge(START, "router")
    graph.add_edge("router", "run_agent")
    graph.add_edge("run_agent", END)
    return graph.compile()


def escalation_enabled() -> bool:
    return bool(os.getenv("ANTHROPIC_API_KEY", "").strip())


@asynccontextmanager
async def open_orchestrator(runtime: str = "ollama", *, debug: bool = False) -> AsyncIterator[Any]:
    """Start the runtimes for one chat and yield its orchestrator; they shut down on exit."""
    from agent_platform.runtimes.claude import ClaudeSdkRuntime
    from agent_platform.runtimes.ollama import OllamaRuntime

    if runtime == "claude":
        policy = RuntimePolicy(default="claude", escalate_to=None)
    else:
        policy = RuntimePolicy(escalate_to="claude" if escalation_enabled() else None)
    async with AsyncExitStack() as stack:
        claude = await stack.enter_async_context(ClaudeSdkRuntime())
        # runtime="claude" never touches Ollama; the policy never picks the "ollama" slot.
        ollama = claude if runtime == "claude" else await stack.enter_async_context(OllamaRuntime(debug=debug))
        yield build_orchestrator(ollama=ollama, claude=claude, policy=policy)
