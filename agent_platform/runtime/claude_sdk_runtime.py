from __future__ import annotations

import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from claude_agent_sdk import (
    AssistantMessage,
    ClaudeAgentOptions,
    ClaudeSDKClient,
    ResultMessage,
    TextBlock,
    ToolUseBlock,
)

from agent_platform.agent_spec import AgentSpec
from agent_platform.mcp_config import REPO_ROOT
from agent_platform.prompting import PromptPolicy, build_system_prompt
from agent_platform.runtime.base import RunContext, RuntimeAdapter
from agent_platform.tool_registry import MCP_SERVER_NAME, claude_allowed_tools_for_agent, mcp_prefixed_tool_name


@dataclass
class ClaudeSdkRuntime(RuntimeAdapter):
    """Claude Agent SDK runtime adapter.

    Notes:
    - The SDK manages its own MCP subprocess lifecycle.
    - Session state (mock session store) lives inside that subprocess, so any
      session_id created in another runtime is not portable here.
    """

    name: str = "claude"
    repo_root: Path = REPO_ROOT
    prompt_policy: PromptPolicy = PromptPolicy()

    model: str | None = None
    fallback_model: str | None = None

    _client_cm: Any | None = None
    _client: ClaudeSDKClient | None = None

    def _options_for_spec(self, spec: AgentSpec) -> ClaudeAgentOptions:
        model = (os.getenv("CLAUDE_MODEL") or "").strip() or self.model
        fallback_model = (os.getenv("CLAUDE_FALLBACK_MODEL") or "").strip() or self.fallback_model

        bad = [t for t in spec.tool_names if t.startswith("mcp__")]
        if bad:
            raise ValueError(
                "AgentSpec.tool_names must contain raw MCP tool names (not Claude-prefixed names).\n"
                f"- agent: {spec.name}\n"
                f"- invalid: {bad}\n"
            )

        # Claude should connect inside its own MCP process.
        session_instruction = (
            "SESSION\n"
            f"- Start by calling `{mcp_prefixed_tool_name('softone_connect_default', server_name=MCP_SERVER_NAME)}`.\n"
            "- Capture the returned `session_id` and pass it to every subsequent tool call.\n"
            "- If a tool returns ok:false with an auth/session error, stop and report it."
        )
        system_prompt = build_system_prompt(
            base=spec.system_prompt,
            session_instruction=session_instruction,
            policy=self.prompt_policy,
            extra_resource_uris=spec.resource_uris,
        )

        allowed = claude_allowed_tools_for_agent(spec.tool_names)
        # If specs are misconfigured, fail safe: don't allow everything.
        if not allowed:
            allowed = [f"mcp__{MCP_SERVER_NAME}__softone_connect_default"]

        return ClaudeAgentOptions(
            cwd=str(self.repo_root),
            mcp_servers={
                MCP_SERVER_NAME: {
                    "type": "stdio",
                    "command": sys.executable,
                    "args": ["-m", "softone_mcp.server"],
                    "env": {**os.environ},
                }
            },
            allowed_tools=allowed,
            system_prompt=system_prompt,
            model=model,
            fallback_model=fallback_model,
        )

    async def __aenter__(self) -> "ClaudeSdkRuntime":
        # Lazy; we open per call to keep behavior explicit.
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        if self._client_cm is not None:
            await self._client_cm.__aexit__(exc_type, exc, tb)
        self._client_cm = None
        self._client = None

    async def _ensure_client(self, spec: AgentSpec) -> ClaudeSDKClient:
        if self._client is not None:
            return self._client
        options = self._options_for_spec(spec)
        self._client_cm = ClaudeSDKClient(options=options)
        self._client = await self._client_cm.__aenter__()
        return self._client

    async def set_model(self, model: str) -> None:
        """Switch model on the active client (interactive use)."""
        if self._client is None:
            self.model = model
            return
        await self._client.set_model(model)

    async def run_turn(self, *, spec: AgentSpec, user_text: str, context: RunContext) -> str:
        client = await self._ensure_client(spec)

        chunks: list[str] = []
        await client.query(user_text)
        async for msg in client.receive_response():
            if isinstance(msg, AssistantMessage):
                for block in msg.content:
                    if isinstance(block, TextBlock):
                        chunks.append(block.text)
                    elif isinstance(block, ToolUseBlock):
                        # Keep tool calls out of the end-user text; runtimes may
                        # implement structured logging later.
                        continue
            elif isinstance(msg, ResultMessage):
                # ResultMessage may contain a final short result string.
                if msg.result:
                    chunks.append(str(msg.result))

        return "".join(chunks).strip()

