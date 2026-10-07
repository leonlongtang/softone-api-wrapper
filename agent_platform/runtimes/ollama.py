"""Ollama runtime: a local model driving MCP tools over one persistent MCP session."""

from __future__ import annotations

import asyncio
import json
import logging
import os
import traceback
from contextlib import suppress
from dataclasses import dataclass, field
from typing import Any

from agent_platform.gate import WriteGate
from agent_platform.mcp_tools import CONNECT_TOOL_NAME, MCP_SERVER_NAME, mcp_server_params
from agent_platform.prompting import PromptPolicy, build_system_prompt
from agent_platform.runtimes.base import RunContext, RuntimeAdapter, ToolError
from agent_platform.specs import AgentSpec

logger = logging.getLogger(__name__)

HISTORY_KEY = "ollama_history"
DEFAULT_MODEL = "qwen2.5:7b"


def _env_int(name: str, default: int) -> int:
    raw = (os.getenv(name) or "").strip()
    if not raw:
        return default
    try:
        return int(raw)
    except ValueError:
        return default


def _short_json(obj: Any, max_len: int = 1200) -> str:
    try:
        s = json.dumps(obj, default=str, ensure_ascii=False)
    except TypeError:
        s = repr(obj)
    return s if len(s) <= max_len else s[: max_len - 3] + "..."


def _normalize(result: Any) -> Any:
    """Unwrap langchain-mcp-adapters content-block outputs into a dict when possible."""
    if isinstance(result, dict):
        return result
    if isinstance(result, list):
        texts = [
            i.get("text", "")
            for i in result
            if isinstance(i, dict) and i.get("type") == "text" and isinstance(i.get("text"), str)
        ]
        if texts:
            try:
                parsed = json.loads("".join(texts).strip())
            except json.JSONDecodeError:
                return result
            if isinstance(parsed, dict):
                return parsed
    if isinstance(result, str):
        try:
            parsed = json.loads(result.strip())
        except json.JSONDecodeError:
            return result
        if isinstance(parsed, dict):
            return parsed
    return result


def _build_retry_question(tool_name: str, error: dict[str, Any]) -> str:
    message = str(error.get("message") or "Tool failed.")
    details = error.get("details")
    if not isinstance(details, dict):
        details = {}

    if "available" in details:
        available = details.get("available")
        return f"{message} Only {available} available. Do you want me to retry with {available}, or cancel?"
    if "outstanding" in details:
        outstanding = details.get("outstanding")
        return (
            f"{message} Outstanding is {outstanding}. Do you want me to retry with {outstanding}, or cancel?"
        )
    if "max" in details:
        max_value = details.get("max")
        return f"{message} The maximum allowed is {max_value}. Do you want me to retry with {max_value}, or cancel?"
    if "min" in details:
        min_value = details.get("min")
        return f"{message} The minimum allowed is {min_value}. Do you want me to retry with {min_value}, or cancel?"

    if details:
        return (
            f"{message} ({tool_name} details: {json.dumps(details, ensure_ascii=False)}) How do you want to proceed?"
        )
    return f"{message} How do you want to proceed?"


def _wrap_tool(tool: Any, *, gate: WriteGate, debug: bool) -> Any:
    """Preserve args_schema; enforce the write gate; normalize the result; raise ToolError on ok:false."""

    from langchain_core.tools import StructuredTool
    from langchain_core.tools.base import ToolException

    async def _call(**kwargs: Any) -> Any:
        # LLMs sometimes send explicit nulls; most MCP tool schemas model
        # optional fields by omitting them (not by passing null).
        kwargs = {k: v for k, v in kwargs.items() if v is not None}
        if refusal := gate.check(tool.name, kwargs):
            # Returned to the model, not raised: a gated write is not a tool failure to escalate.
            logger.debug("[gate] blocked %s %s", tool.name, _short_json(kwargs))
            return {"blocked": True, "message": refusal}
        if debug:
            logger.debug("[mcp] -> %s %s", tool.name, _short_json(kwargs))
        # Retry connect + read-only tools once on transient exceptions; never retry writes.
        attempts = 0
        while True:
            try:
                raw = await tool.ainvoke(kwargs)
                break
            except ToolException as exc:
                # Tool input validation errors (e.g. pydantic schema mismatch) should not crash the REPL.
                # Convert to ToolError so the orchestrator can ask the user to adjust inputs.
                raise ToolError(
                    tool_name=str(tool.name),
                    error={
                        "code": "BAD_TOOL_INPUT",
                        "message": str(exc),
                        "details": {"tool": str(tool.name)},
                    },
                ) from exc
            except Exception as exc:
                attempts += 1
                is_transient = isinstance(exc, (TimeoutError, ConnectionError, OSError))
                is_connect = tool.name == CONNECT_TOOL_NAME
                is_read = (
                    tool.name.startswith(("get_", "list_", "search_"))
                    or tool.name in {"check_inventory", "get_stock_balance", "get_context"}
                )
                can_retry = attempts <= 1 and is_transient and (is_connect or is_read)
                if debug:
                    logger.debug("[mcp] !! %s\n%s", tool.name, traceback.format_exc())
                if not can_retry:
                    raise
                # Small backoff; keep deterministic & bounded.
                await asyncio.sleep(0.25)
        result = _normalize(raw)
        if debug:
            logger.debug("[mcp] <- %s %s", tool.name, _short_json(result))

        if isinstance(result, dict) and result.get("ok") is False:
            err_obj = result.get("error")
            if not isinstance(err_obj, dict):
                err_obj = {"message": str(err_obj) if err_obj else "Tool failed."}
            raise ToolError(tool_name=str(tool.name), error=err_obj)
        return result

    return StructuredTool.from_function(
        coroutine=_call,
        name=tool.name,
        description=tool.description or "",
        args_schema=tool.args_schema,
    )


async def _connect(raw_tools_by_name: dict[str, Any], *, debug: bool) -> str | None:
    tool = raw_tools_by_name.get(CONNECT_TOOL_NAME)
    if tool is None:
        logger.warning("%s not found in MCP tools.", CONNECT_TOOL_NAME)
        return None
    # Retry connect once on transient errors.
    for attempt in range(2):
        try:
            raw = await tool.ainvoke({})
            break
        except Exception as exc:
            is_transient = isinstance(exc, (TimeoutError, ConnectionError, OSError))
            logger.warning("Connect failed (attempt %s): %s", attempt + 1, exc)
            if debug:
                logger.exception("Connect exception")
            if attempt == 0 and is_transient:
                await asyncio.sleep(0.25)
                continue
            return None
    envelope = _normalize(raw)
    if debug:
        logger.debug("[mcp] connect normalized %s", _short_json(envelope))
    if isinstance(envelope, dict) and envelope.get("ok") is True:
        sid = (envelope.get("data") or {}).get("session_id")
        if isinstance(sid, str) and sid:
            return sid
    logger.warning("Connect returned no session_id: %r", envelope)
    return None


async def _check_ollama(model: str) -> None:
    """Fail fast with an actionable message instead of a deep httpx traceback."""
    import ollama

    hint = "Or run with `--runtime claude` (needs ANTHROPIC_API_KEY)."
    try:
        await ollama.AsyncClient().show(model)
    except ollama.ResponseError as exc:
        if exc.status_code == 404:
            raise RuntimeError(f"Ollama model `{model}` is not pulled. Run `ollama pull {model}`. {hint}") from exc
        raise
    except Exception as exc:  # connection refused surfaces as several exception types
        raise RuntimeError(f"Ollama is not reachable ({exc}). Start it with `ollama serve`. {hint}") from exc


@dataclass
class OllamaRuntime(RuntimeAdapter):
    """Ollama runtime with a persistent MCP session."""

    name: str = "ollama"
    model: str = field(default_factory=lambda: os.getenv("OLLAMA_MODEL") or DEFAULT_MODEL)
    debug: bool = False
    prompt_policy: PromptPolicy = field(default_factory=PromptPolicy)

    _session_cm: Any | None = None
    _session: Any | None = None
    _raw_tools_by_name: dict[str, Any] | None = None

    async def __aenter__(self) -> OllamaRuntime:
        # Lazy imports keep CLI startup fast.
        from langchain_mcp_adapters.client import MultiServerMCPClient
        from langchain_mcp_adapters.tools import load_mcp_tools

        await _check_ollama(self.model)
        startup_timeout_s = _env_int("OLLAMA_MCP_STARTUP_TIMEOUT_S", 20)
        client = MultiServerMCPClient({MCP_SERVER_NAME: {"transport": "stdio", **mcp_server_params()}})
        # Hold one live MCP session for the entire runtime lifetime.
        self._session_cm = client.session(MCP_SERVER_NAME)
        logger.debug("[ollama_runtime] opening MCP session (timeout=%ss)", startup_timeout_s)
        self._session = await asyncio.wait_for(self._session_cm.__aenter__(), timeout=startup_timeout_s)
        logger.debug("[ollama_runtime] loading MCP tools (timeout=%ss)", startup_timeout_s)
        raw_tools = await asyncio.wait_for(load_mcp_tools(self._session), timeout=startup_timeout_s)
        self._raw_tools_by_name = {t.name: t for t in raw_tools}
        logger.debug("[ollama_runtime] loaded %s tools", len(self._raw_tools_by_name))
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        if self._session_cm is not None:
            with suppress(Exception):
                await self._session_cm.__aexit__(exc_type, exc, tb)
        self._session_cm = None
        self._session = None
        self._raw_tools_by_name = None

    async def ensure_connected(self, context: RunContext) -> None:
        if context.session_id:
            return
        if not self._raw_tools_by_name:
            raise RuntimeError("OllamaRuntime not initialized (use `async with`).")
        sid = await _connect(self._raw_tools_by_name, debug=self.debug)
        if sid:
            context.session_id = sid
            return
        raise RuntimeError("Startup connect failed (no session_id). Check SOFTONE_* configuration.")

    def _system_prompt(self, *, spec: AgentSpec, session_id: str) -> str:
        session_instruction = (
            "SESSION\n"
            "- A SoftOne session is already open. Use this exact session_id on every tool call:\n"
            f"    session_id = {session_id}\n"
            "- Never invent a different session_id. Never reconnect. If a tool returns an auth/session error, tell the user and stop."
        )
        return build_system_prompt(
            base=spec.system_prompt,
            session_instruction=session_instruction,
            policy=self.prompt_policy,
            extra_resource_uris=spec.resource_uris,
        )

    def _business_tools_for_spec(self, spec: AgentSpec, gate: WriteGate) -> list[Any]:
        if not self._raw_tools_by_name:
            raise RuntimeError("OllamaRuntime not initialized (use `async with`).")
        available = set(self._raw_tools_by_name.keys())
        requested = set(spec.tool_names)
        requested.discard(CONNECT_TOOL_NAME)

        missing = sorted(requested - available)
        if missing:
            available_sorted = sorted(available)
            raise RuntimeError(
                "AgentSpec references MCP tools that are not available.\n"
                f"- agent: {spec.name}\n"
                f"- missing: {missing}\n"
                f"- available: {available_sorted}\n"
            )

        raw_tools = [
            t
            for name, t in self._raw_tools_by_name.items()
            if name in requested and name != CONNECT_TOOL_NAME
        ]
        return [_wrap_tool(t, gate=gate, debug=self.debug) for t in raw_tools]

    async def run_turn(self, *, spec: AgentSpec, user_text: str, context: RunContext) -> str:
        from langchain.agents import create_agent
        from langchain_core.messages import AIMessage, HumanMessage
        from langchain_ollama import ChatOllama

        await self.ensure_connected(context)
        assert context.session_id

        # One conversation shared by all departments, so a handoff (sales creates
        # order 5003, then "invoice that order" goes to finance) keeps its context.
        # Only the system prompt and tool allowlist change per department.
        messages: list[Any] = context.artifacts.get(HISTORY_KEY) or []
        agent = create_agent(
            ChatOllama(model=self.model),
            self._business_tools_for_spec(spec, context.gate),
            system_prompt=self._system_prompt(spec=spec, session_id=context.session_id),
        )

        messages.append(HumanMessage(content=user_text))
        try:
            result = await agent.ainvoke({"messages": messages})
            context.artifacts[HISTORY_KEY] = result["messages"]
            return str(result["messages"][-1].content)
        except ToolError as te:
            messages.append(AIMessage(content=_build_retry_question(tool_name=te.tool_name, error=te.error)))
            context.artifacts[HISTORY_KEY] = messages
            raise
        except Exception:
            if self.debug:
                logger.exception("OllamaRuntime.run_turn failed")
            raise

