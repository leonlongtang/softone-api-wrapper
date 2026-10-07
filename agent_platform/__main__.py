"""CLI: python -m agent_platform [--runtime ollama|claude] [--debug] ["one-shot prompt"]"""

from __future__ import annotations

import argparse
import asyncio
import logging
import os
from contextlib import AsyncExitStack

from config import load_dotenv


def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(prog="python -m agent_platform", description="SoftOne multi-agent orchestrator.")
    p.add_argument("prompt", nargs="?", default="", help="Run one turn and exit. Omit for an interactive chat.")
    p.add_argument(
        "--runtime",
        choices=["ollama", "claude"],
        default="ollama",
        help="ollama (default): local model, escalates failed turns to Claude if ANTHROPIC_API_KEY is set. "
        "claude: Claude Agent SDK only.",
    )
    p.add_argument("--debug", action="store_true", help="Log every MCP tool call and result.")
    return p.parse_args()


async def _chat(*, prompt: str, runtime: str, debug: bool) -> None:
    # Heavy imports after arg parsing so `--help` is instant.
    from agent_platform.graph import OrchestratorState, RuntimePolicy, build_orchestrator
    from agent_platform.runtimes.claude import ClaudeSdkRuntime
    from agent_platform.runtimes.ollama import OllamaRuntime

    if runtime == "claude":
        policy = RuntimePolicy(default="claude", escalate_to=None)
    else:
        policy = RuntimePolicy(escalate_to="claude" if os.getenv("ANTHROPIC_API_KEY", "").strip() else None)

    async with AsyncExitStack() as stack:
        claude = await stack.enter_async_context(ClaudeSdkRuntime())
        # --runtime claude never touches Ollama; the policy never picks the "ollama" slot.
        ollama = claude if runtime == "claude" else await stack.enter_async_context(OllamaRuntime(debug=debug))
        app = build_orchestrator(ollama=ollama, claude=claude, policy=policy)
        state: OrchestratorState = {"artifacts": {}}

        async def turn(text: str) -> None:
            nonlocal state
            state["user_text"] = text
            state = await app.ainvoke(state)
            print(f"\n[{state.get('route')} | {state.get('runtime')}] {state.get('response') or ''}")

        if prompt.strip():
            await turn(prompt.strip())
            return

        print("SoftOne agents (sales / inventory / finance). Type /exit to quit.")
        while True:
            try:
                text = input("\nYou: ").strip()
            except (EOFError, KeyboardInterrupt):
                print()
                return
            if text.lower() in {"/exit", "/quit", "exit", "quit"}:
                return
            if text:
                await turn(text)


def main() -> None:
    load_dotenv()
    args = _parse_args()
    debug = args.debug or os.getenv("OLLAMA_MCP_DEBUG", "").strip().lower() in {"1", "true", "yes"}
    logging.basicConfig(level=logging.WARNING, format="%(levelname)s %(name)s: %(message)s")
    if debug:
        logging.getLogger("agent_platform").setLevel(logging.DEBUG)
    try:
        asyncio.run(_chat(prompt=args.prompt, runtime=args.runtime, debug=debug))
    except RuntimeError as exc:
        raise SystemExit(f"error: {exc}") from None


if __name__ == "__main__":
    main()
