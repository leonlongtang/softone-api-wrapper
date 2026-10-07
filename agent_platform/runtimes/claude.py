"""Claude Agent SDK runtime: Claude drives the same MCP tools in its own MCP subprocess."""

from __future__ import annotations

import os
from dataclasses import dataclass, field

from claude_agent_sdk import (
    AssistantMessage,
    ClaudeAgentOptions,
    ClaudeSDKClient,
    ResultMessage,
    TextBlock,
)

from agent_platform.mcp_tools import (
    CONNECT_TOOL_NAME,
    MCP_SERVER_NAME,
    REPO_ROOT,
    claude_allowed_tools_for_agent,
    mcp_prefixed_tool_name,
    mcp_server_params,
)
from agent_platform.prompting import PromptPolicy, build_system_prompt
from agent_platform.runtimes.base import RunContext, RuntimeAdapter
from agent_platform.specs import AgentSpec

SESSION_INSTRUCTION = (
    "SESSION\n"
    f"- Start by calling `{mcp_prefixed_tool_name(CONNECT_TOOL_NAME)}`.\n"
    "- Capture the returned `session_id` and pass it to every subsequent tool call.\n"
    "- If a tool returns ok:false with an auth/session error, stop and report it."
)


@dataclass
class ClaudeSdkRuntime(RuntimeAdapter):
    """Claude Agent SDK runtime.

    The SDK runs its own MCP subprocess, so Claude connects there itself (session ids
    from the Ollama runtime aren't portable). Switching department rebuilds the client
    with the new prompt and allowlist and resumes the same Claude conversation.
    """

    name: str = "claude"
    prompt_policy: PromptPolicy = field(default_factory=PromptPolicy)

    _client: ClaudeSDKClient | None = None
    _spec_name: str | None = None
    _conversation_id: str | None = None

    def _options_for_spec(self, spec: AgentSpec) -> ClaudeAgentOptions:
        params = mcp_server_params()
        return ClaudeAgentOptions(
            cwd=str(REPO_ROOT),
            mcp_servers={
                MCP_SERVER_NAME: {"type": "stdio", "command": params["command"], "args": params["args"], "env": params["env"]}
            },
            tools=[],  # no built-in Claude Code tools (Bash, Read, ...): MCP tools only
            allowed_tools=claude_allowed_tools_for_agent(spec.tool_names),
            system_prompt=build_system_prompt(
                base=spec.system_prompt,
                session_instruction=SESSION_INSTRUCTION,
                policy=self.prompt_policy,
                extra_resource_uris=spec.resource_uris,
            ),
            model=os.getenv("CLAUDE_MODEL", "").strip() or None,
            fallback_model=os.getenv("CLAUDE_FALLBACK_MODEL", "").strip() or None,
            resume=self._conversation_id,
        )

    async def __aenter__(self) -> ClaudeSdkRuntime:
        return self  # the client is opened lazily on the first turn

    async def __aexit__(self, exc_type, exc, tb) -> None:
        await self._close()

    async def _close(self) -> None:
        if self._client is not None:
            await self._client.disconnect()
        self._client = None

    async def run_turn(self, *, spec: AgentSpec, user_text: str, context: RunContext) -> str:
        if self._client is None or self._spec_name != spec.name:
            await self._close()
            self._client = ClaudeSDKClient(options=self._options_for_spec(spec))
            await self._client.connect()
            self._spec_name = spec.name

        texts: list[str] = []
        result: str | None = None
        await self._client.query(user_text)
        async for msg in self._client.receive_response():
            if isinstance(msg, AssistantMessage):
                texts += [b.text for b in msg.content if isinstance(b, TextBlock)]  # tool-use blocks stay hidden
            elif isinstance(msg, ResultMessage):
                self._conversation_id = msg.session_id
                result = msg.result
        # ResultMessage.result repeats the final assistant text; prefer it over joining every block.
        return (result or "\n".join(texts)).strip()
