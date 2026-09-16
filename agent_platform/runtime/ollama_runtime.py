from __future__ import annotations

import json
import logging
import os
import sys
import asyncio
import traceback
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from contextlib import suppress

from agent_platform.agent_spec import AgentSpec
from agent_platform.errors import ToolError
from agent_platform.mcp_config import REPO_ROOT, softone_stdio_server_config
from agent_platform.prompting import PromptPolicy, build_system_prompt
from agent_platform.runtime.base import RunContext, RuntimeAdapter
from agent_platform.tool_registry import CONNECT_TOOL_NAME
from agent_platform.orchestrator.artifacts import OLLAMA_HISTORY_KEY


def _env_truthy(name: str) -> bool:
    return (os.getenv(name) or "").strip().lower() in {"1", "true", "yes", "y", "on"}

logger = logging.getLogger(__name__)

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


def _wrap_tool(tool: Any, *, debug: bool) -> Any:
    """Preserve args_schema; normalize return value; raise ToolError on ok:false."""

    # Lazy imports: avoid heavy dependency import at CLI startup.
    from langchain_core.tools import StructuredTool  # noqa: WPS433
    from langchain_core.tools.base import ToolException  # noqa: WPS433

    async def _call(**kwargs: Any) -> Any:
        # LLMs sometimes send explicit nulls; most MCP tool schemas model
        # optional fields by omitting them (not by passing null).
        kwargs = {k: v for k, v in kwargs.items() if v is not None}
        if debug:
            logger.debug("[mcp] -> %s %s", tool.name, _short_json(kwargs))
        # Retry policy (V1): retry connect + read-only tools once on transient exceptions.
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


@dataclass
class OllamaRuntime(RuntimeAdapter):
    """Ollama runtime with a persistent MCP session."""

    name: str = "ollama"
    repo_root: Path = REPO_ROOT
    model: str = "qwen2.5:7b"
    debug: bool = False
    prompt_policy: PromptPolicy = PromptPolicy()

    _client: MultiServerMCPClient | None = None
    _session_cm: Any | None = None
    _session: Any | None = None
    _raw_tools_by_name: dict[str, Any] | None = None

    async def __aenter__(self) -> "OllamaRuntime":
        # Lazy imports: avoid heavy dependency import at CLI startup.
        from langchain_mcp_adapters.client import MultiServerMCPClient  # noqa: WPS433
        from langchain_mcp_adapters.tools import load_mcp_tools  # noqa: WPS433

        startup_timeout_s = _env_int("OLLAMA_MCP_STARTUP_TIMEOUT_S", 20)
        cfg = softone_stdio_server_config(repo_root=self.repo_root)
        logger.info("[ollama_runtime] starting MCP server: %s %s (cwd=%s)", cfg.command, cfg.args, cfg.cwd)
        self._client = MultiServerMCPClient(
            {
                cfg.name: {
                    "transport": cfg.transport,
                    "command": cfg.command,
                    "args": cfg.args,
                    "cwd": cfg.cwd,
                    "env": cfg.env,
                }
            }
        )
        # Hold one live MCP session for the entire runtime lifetime.
        self._session_cm = self._client.session(cfg.name)
        logger.info("[ollama_runtime] opening MCP session (timeout=%ss)", startup_timeout_s)
        self._session = await asyncio.wait_for(self._session_cm.__aenter__(), timeout=startup_timeout_s)
        logger.info("[ollama_runtime] loading MCP tools (timeout=%ss)", startup_timeout_s)
        raw_tools = await asyncio.wait_for(load_mcp_tools(self._session), timeout=startup_timeout_s)
        self._raw_tools_by_name = {t.name: t for t in raw_tools}
        logger.info("[ollama_runtime] loaded %s tools", len(self._raw_tools_by_name))
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        if self._session_cm is not None:
            with suppress(Exception):
                await self._session_cm.__aexit__(exc_type, exc, tb)
        self._client = None
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

    def _build_system_message(self, *, spec: AgentSpec, session_id: str) -> SystemMessage:
        # Lazy import.
        from langchain_core.messages import SystemMessage  # noqa: WPS433

        session_instruction = (
            "SESSION\n"
            "- A SoftOne session is already open. Use this exact session_id on every tool call:\n"
            f"    session_id = {session_id}\n"
            "- Never invent a different session_id. Never reconnect. If a tool returns an auth/session error, tell the user and stop."
        )
        sys_prompt = build_system_prompt(
            base=spec.system_prompt,
            session_instruction=session_instruction,
            policy=self.prompt_policy,
            extra_resource_uris=spec.resource_uris,
        )
        return SystemMessage(content=sys_prompt)

    def _business_tools_for_spec(self, spec: AgentSpec) -> list[Any]:
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
        return [_wrap_tool(t, debug=self.debug) for t in raw_tools]

    async def run_turn(self, *, spec: AgentSpec, user_text: str, context: RunContext) -> str:
        # Lazy imports: only pull these in when we actually run a turn.
        from langchain.agents import create_agent  # noqa: WPS433
        from langchain_core.messages import AIMessage, HumanMessage  # noqa: WPS433
        from langchain_ollama import ChatOllama  # noqa: WPS433

        await self.ensure_connected(context)
        assert context.session_id

        # Keep per-agent chat history in the shared context.
        history_by_agent = context.artifacts.setdefault(OLLAMA_HISTORY_KEY, {})
        messages: list[Any] = history_by_agent.get(spec.name) or [self._build_system_message(spec=spec, session_id=context.session_id)]

        tools = self._business_tools_for_spec(spec)
        llm = ChatOllama(model=(os.getenv("OLLAMA_MODEL") or self.model))
        agent = create_agent(llm, tools)

        messages.append(HumanMessage(content=user_text))
        try:
            result = await agent.ainvoke({"messages": messages})
            messages = result["messages"]
            history_by_agent[spec.name] = messages
            return str(messages[-1].content)
        except ToolError as te:
            ask = _build_retry_question(tool_name=te.tool_name, error=te.error)
            messages.append(AIMessage(content=ask))
            history_by_agent[spec.name] = messages
            raise
        except Exception:
            if self.debug:
                logger.exception("OllamaRuntime.run_turn failed")
            raise

