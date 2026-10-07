"""Claude Agent SDK runtime: Claude drives the same MCP tools in its own MCP subprocess."""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass, field
from typing import Any

from claude_agent_sdk import (
    AssistantMessage,
    ClaudeAgentOptions,
    ClaudeSDKClient,
    PermissionResultAllow,
    PermissionResultDeny,
    ResultMessage,
    TextBlock,
)

from agent_platform.gate import WriteGate
from agent_platform.mcp_tools import (
    CONNECT_TOOL_NAME,
    MCP_SERVER_NAME,
    REPO_ROOT,
    mcp_prefixed_tool_name,
    mcp_server_params,
)
from agent_platform.prompting import PromptPolicy, build_system_prompt
from agent_platform.runtimes.base import RunContext, RuntimeAdapter
from agent_platform.specs import SPECS, AgentSpec

logger = logging.getLogger(__name__)

SESSION_INSTRUCTION = (
    "SESSION\n"
    f"- Start by calling `{mcp_prefixed_tool_name(CONNECT_TOOL_NAME)}`.\n"
    "- Capture the returned `session_id` and pass it to every subsequent tool call.\n"
    "- If a tool returns ok:false with an auth/session error, stop and report it."
)


def _system_prompt(policy: PromptPolicy) -> str:
    briefs = "\n\n".join(f"=== DEPARTMENT: {s.name} ===\n{s.system_prompt.strip()}" for s in SPECS.values())
    return build_system_prompt(
        base=(
            "You are one of several SoftOne ERP department agents. Each user message starts with "
            "`[department: <name>]`: act as that department, follow its brief below, and use only its tools "
            "(others are refused).\n\n" + briefs
        ),
        session_instruction=SESSION_INSTRUCTION,
        policy=policy,
        extra_resource_uris=tuple(dict.fromkeys(u for s in SPECS.values() for u in s.resource_uris)),
    )


@dataclass
class ClaudeSdkRuntime(RuntimeAdapter):
    """Claude Agent SDK runtime: one client, one MCP subprocess, one conversation for the whole chat.

    Switching department doesn't rebuild the client (a new client would mean a new MCP process,
    whose in-memory session store doesn't know the old session_id). Instead every turn is tagged
    with its department, and `can_use_tool` enforces that department's allowlist and the write gate
    on every call.
    """

    name: str = "claude"
    prompt_policy: PromptPolicy = field(default_factory=PromptPolicy)

    _client: ClaudeSDKClient | None = None
    _spec: AgentSpec | None = None
    _gate: WriteGate = field(default_factory=WriteGate)

    def _options(self) -> ClaudeAgentOptions:
        params = mcp_server_params()
        return ClaudeAgentOptions(
            cwd=str(REPO_ROOT),
            mcp_servers={
                MCP_SERVER_NAME: {"type": "stdio", "command": params["command"], "args": params["args"], "env": params["env"]}
            },
            tools=[],  # no built-in Claude Code tools (Bash, Read, ...): MCP tools only
            setting_sources=[],  # ignore the developer's own Claude Code settings and hooks: reproducible agent
            allowed_tools=[],  # nothing auto-approved: every call, connect included, goes through can_use_tool
            can_use_tool=self._can_use_tool,
            system_prompt=_system_prompt(self.prompt_policy),
            model=os.getenv("CLAUDE_MODEL", "").strip() or None,
            fallback_model=os.getenv("CLAUDE_FALLBACK_MODEL", "").strip() or None,
        )

    async def _can_use_tool(self, tool_name: str, tool_input: dict[str, Any], _ctx: Any) -> Any:
        tool = tool_name.removeprefix(mcp_prefixed_tool_name(""))
        spec = self._spec
        if tool == CONNECT_TOOL_NAME:
            return PermissionResultAllow()
        if spec is None or tool == tool_name or tool not in spec.tool_names:
            return PermissionResultDeny(message=f"`{tool_name}` is not available to the {spec and spec.name} agent.")
        refusal = self._gate.check(tool, tool_input)
        logger.debug("[gate] %s %s %s", "deny" if refusal else "allow", tool, tool_input)
        return PermissionResultDeny(message=refusal) if refusal else PermissionResultAllow()

    async def __aenter__(self) -> ClaudeSdkRuntime:
        return self  # the client is opened lazily on the first turn

    async def __aexit__(self, exc_type, exc, tb) -> None:
        if self._client is not None:
            await self._client.disconnect()
        self._client = None

    async def run_turn(self, *, spec: AgentSpec, user_text: str, context: RunContext) -> str:
        self._spec, self._gate = spec, context.gate
        if self._client is None:
            self._client = ClaudeSDKClient(options=self._options())
            await self._client.connect()

        texts: list[str] = []
        result: str | None = None
        await self._client.query(f"[department: {spec.name}]\n{user_text}")
        async for msg in self._client.receive_response():
            logger.debug("[claude] <- %s %s", type(msg).__name__, str(msg)[:200])
            if isinstance(msg, AssistantMessage):
                texts += [b.text for b in msg.content if isinstance(b, TextBlock)]  # tool-use blocks stay hidden
            elif isinstance(msg, ResultMessage):
                result = msg.result
        # ResultMessage.result repeats the final assistant text; prefer it over joining every block.
        return (result or "\n".join(texts)).strip()
