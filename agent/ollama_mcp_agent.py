"""SoftOne MCP agent (Ollama runtime), powered by the shared agent platform.

Run from the repo root:
    python -m agent.ollama_mcp_agent          # interactive chat (Ollama)
    python -m agent.ollama_mcp_agent "Prompt" # single-turn

The implementation lives in `agent_platform/` so both Claude and Ollama
entrypoints share the same agent definitions and prompt policy.
"""
from __future__ import annotations

import asyncio
import os

from config import load_dotenv

async def main() -> None:
    load_dotenv()
    from agent_platform.runtime.base import RunContext
    from agent_platform.runtime.ollama_runtime import OllamaRuntime
    from agent_platform.specs import sales_agent_spec

    # Single-turn mode (explicit prompt argument).
    import sys

    prompt = sys.argv[1].strip() if len(sys.argv) > 1 else ""
    debug = (os.getenv("OLLAMA_MCP_DEBUG") or "").strip().lower() in {"1", "true", "yes"}

    async with OllamaRuntime(debug=debug) as runtime:
        ctx = RunContext()
        spec = sales_agent_spec()
        if prompt:
            text = await runtime.run_turn(spec=spec, user_text=prompt, context=ctx)
            print(text)
            return

        print("SoftOne MCP Agent (interactive, Ollama). Type /exit to quit.")
        while True:
            try:
                user_text = input("\nYou: ").strip()
            except (EOFError, KeyboardInterrupt):
                print()
                return
            if not user_text:
                continue
            if user_text.lower() in {"/exit", "/quit", "exit", "quit"}:
                return
            if user_text.lower() in {"/debug on", "/debug"}:
                runtime.debug = True
                print("- Debug ON")
                continue
            if user_text.lower() == "/debug off":
                runtime.debug = False
                print("- Debug OFF")
                continue
            try:
                text = await runtime.run_turn(spec=spec, user_text=user_text, context=ctx)
                print(f"\nAgent: {text}")
            except Exception as exc:
                print(f"\n! Agent error: {exc}")


if __name__ == "__main__":
    asyncio.run(main())
