from __future__ import annotations

import os
from typing import Callable

from langgraph.constants import END, START
from langgraph.graph.state import StateGraph

from agent_platform.errors import ToolError
from agent_platform.orchestrator.policy import RuntimePolicy
from agent_platform.orchestrator.router import clarify_question, hybrid_route
from agent_platform.orchestrator.artifacts import (
    PENDING_USER_TEXT_KEY,
    SESSION_ID_KEY,
)
from agent_platform.orchestrator.state import OrchestratorState
from agent_platform.runtime.base import RunContext, RuntimeAdapter
from agent_platform.specs import ops_workflows_agent_spec


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

    # V1: single workflow-first agent spec (no department multi-agent logic).
    spec = ops_workflows_agent_spec()

    async def router_node(state: OrchestratorState) -> OrchestratorState:
        user_text = state.get("user_text") or ""
        artifacts = state.setdefault("artifacts", {})

        # If we previously asked the user to clarify the department, treat the
        # next message as the selection (clarify/proceed).
        pending = artifacts.get(PENDING_USER_TEXT_KEY)
        selection = (user_text or "").strip().lower()
        if isinstance(pending, str) and pending.strip() and selection in {"proceed", "continue", "ok"}:
            state["route"] = "ops"
            state["user_text"] = pending
            artifacts.pop(PENDING_USER_TEXT_KEY, None)
        else:
            routed = router(user_text)
            # V1: keep only ambiguity detection. Any non-clarify route maps to ops.
            state["route"] = "clarify" if routed == "clarify" else "ops"
        state.setdefault("failures", 0)
        if state.get("route") == "clarify":
            state["runtime"] = "router"
            state["response"] = clarify_question()
            artifacts[PENDING_USER_TEXT_KEY] = user_text
        return state

    async def run_agent_node(state: OrchestratorState) -> OrchestratorState:
        if state.get("route") == "clarify":
            # Ambiguous routing: ask a single question and stop (no tool calls).
            return state
        failures = int(state.get("failures") or 0)
        runtime_name = policy.choose(failures=failures)
        state["runtime"] = runtime_name

        ctx = RunContext(
            session_id=state.get("artifacts", {}).get(SESSION_ID_KEY),
            artifacts=state.get("artifacts") or {},
        )

        runtime = claude if runtime_name == "claude" else ollama
        try:
            # If the runtime supports host-managed sessions, bootstrap a session when missing.
            ensure_connected = getattr(runtime, "ensure_connected", None)
            if callable(ensure_connected):
                await ensure_connected(ctx)
            text = await runtime.run_turn(spec=spec, user_text=state.get("user_text") or "", context=ctx)
            state["response"] = text
            state["artifacts"] = ctx.artifacts
            # Persist session_id only for the Ollama runtime (host-managed persistent session).
            if runtime_name == "ollama" and ctx.session_id:
                state["artifacts"][SESSION_ID_KEY] = ctx.session_id
            return state
        except ToolError as te:
            # Session recovery (ollama only): reconnect once and rerun the same turn.
            if runtime_name == "ollama" and _looks_like_session_error(te.error):
                state.setdefault("artifacts", {}).pop(SESSION_ID_KEY, None)
                ctx.session_id = None
                ensure_connected = getattr(runtime, "ensure_connected", None)
                if callable(ensure_connected):
                    try:
                        await ensure_connected(ctx)
                        text = await runtime.run_turn(spec=spec, user_text=state.get("user_text") or "", context=ctx)
                        state["runtime"] = "ollama"
                        state["response"] = text
                        state["artifacts"] = ctx.artifacts
                        if ctx.session_id:
                            state["artifacts"][SESSION_ID_KEY] = ctx.session_id
                        return state
                    except Exception:
                        # Fall through to the normal error handling below.
                        pass

            # Ollama runtime raises ToolError on ok:false. Optionally escalate to Claude.
            state["failures"] = failures + 1
            should_escalate = policy.choose(failures=state["failures"]) == "claude"

            msg = str(te.error.get("message") or te)
            details = te.error.get("details")
            details_text = f"\nDetails: {details}" if details else ""

            if should_escalate:
                if not (os.getenv("ANTHROPIC_API_KEY") or "").strip():
                    state["response"] = (
                        f"{msg}{details_text}\n\n"
                        "Escalation to Claude is configured, but `ANTHROPIC_API_KEY` is not set. "
                        "Set it in `.env` and retry if you want Claude-based recovery."
                    )
                    return state
                # Rerun the *same user_text* using Claude. Note: Claude runtime must connect in its own MCP subprocess.
                try:
                    text = await claude.run_turn(spec=spec, user_text=state.get("user_text") or "", context=RunContext())
                    state["runtime"] = "claude"
                    state["response"] = text
                    return state
                except Exception as exc:  # noqa: BLE001
                    state["response"] = (
                        f"{msg}{details_text}\n\n"
                        f"Escalation to Claude failed: {exc}"
                    )
                    return state

            state["response"] = (
                f"{msg}{details_text}\n\n"
                "Tell me how you want to adjust the inputs, and I’ll retry."
            )
            return state

    graph = StateGraph(OrchestratorState)
    graph.add_node("router", router_node)
    graph.add_node("run_agent", run_agent_node)
    graph.add_edge(START, "router")
    graph.add_edge("router", "run_agent")
    graph.add_edge("run_agent", END)
    return graph.compile()

