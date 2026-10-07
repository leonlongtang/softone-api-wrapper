"""LangGraph orchestrator: route each turn, run the agent, recover or escalate on tool errors."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, TypedDict

from langgraph.constants import END, START
from langgraph.graph.state import StateGraph

from agent_platform.router import CLARIFY_QUESTION, DEPARTMENTS, hybrid_route
from agent_platform.runtimes.base import RunContext, RuntimeAdapter, ToolError
from agent_platform.specs import SPECS, AgentSpec

SESSION_ID_KEY = "session_id"
PENDING_USER_TEXT_KEY = "pending_user_text"


class OrchestratorState(TypedDict, total=False):
    user_text: str
    route: str  # a department, or "clarify"
    runtime: str  # which runtime answered: "ollama", "claude", or "router" for a clarify
    response: str
    # Cross-turn state: session_id, pending clarify text, conversation history.
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
        pending = artifacts.pop(PENDING_USER_TEXT_KEY, None)

        if pending and text.lower() in DEPARTMENTS:
            # Reply to a clarify: send the original request to the chosen department.
            state["route"], state["user_text"] = text.lower(), pending
        else:
            state["route"] = router(text)

        if state["route"] == "clarify":
            state["runtime"], state["response"] = "router", CLARIFY_QUESTION
            artifacts[PENDING_USER_TEXT_KEY] = text
        return state

    async def run(runtime_name: str, spec: AgentSpec, state: OrchestratorState) -> str:
        runtime = claude if runtime_name == "claude" else ollama
        artifacts = state["artifacts"]
        # Only Ollama keeps a host-managed MCP session; Claude connects inside its own MCP subprocess.
        ctx = RunContext(session_id=artifacts.get(SESSION_ID_KEY) if runtime_name == "ollama" else None, artifacts=artifacts)
        ensure_connected = getattr(runtime, "ensure_connected", None)
        if ensure_connected:
            await ensure_connected(ctx)
        text = await runtime.run_turn(spec=spec, user_text=state.get("user_text") or "", context=ctx)
        if runtime_name == "ollama" and ctx.session_id:
            artifacts[SESSION_ID_KEY] = ctx.session_id
        state["runtime"] = runtime_name
        return text

    async def run_agent_node(state: OrchestratorState) -> OrchestratorState:
        if state["route"] == "clarify":
            return state
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
        if escalate_to in (None, runtime_name):
            state["runtime"] = runtime_name
            state["response"] = f"{msg}\n\nTell me how you want to adjust the inputs, and I'll retry."
            return state
        try:
            # Escalation reruns the same request; Claude doesn't see the Ollama conversation.
            state["response"] = await run(escalate_to, spec, state)
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
