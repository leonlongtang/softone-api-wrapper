from __future__ import annotations

import argparse
import asyncio

from config import load_dotenv

from agent_platform.orchestrator.graph import build_orchestrator
from agent_platform.orchestrator.state import OrchestratorState
from agent_platform.runtime.claude_sdk_runtime import ClaudeSdkRuntime
from agent_platform.runtime.ollama_runtime import OllamaRuntime
from agent_platform.settings import configure_logging, load_agent_platform_settings
from agent_platform.specs import finance_agent_spec, inventory_agent_spec, sales_agent_spec


def _build_argparser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="SoftOne agent platform (multi-runtime + LangGraph orchestrator).")
    p.add_argument("prompt", nargs="?", default="", help="Optional single-turn prompt. If omitted, run REPL.")
    p.add_argument("--mode", choices=["single", "orchestrator"], default="orchestrator")
    p.add_argument("--runtime", choices=["ollama", "claude"], default="ollama", help="Default runtime for single mode.")
    p.add_argument("--agent", choices=["sales", "inventory", "finance"], default="sales", help="AgentSpec for single mode.")
    p.add_argument("--debug", action="store_true", help="Enable MCP tool I/O tracing (Ollama runtime).")
    return p


async def _run_single(*, prompt: str, agent_name: str, runtime_name: str, debug: bool) -> None:
    specs = {
        "sales": sales_agent_spec(),
        "inventory": inventory_agent_spec(),
        "finance": finance_agent_spec(),
    }
    spec = specs[agent_name]

    async with OllamaRuntime(debug=debug) as ollama, ClaudeSdkRuntime() as claude:
        runtime = claude if runtime_name == "claude" else ollama
        from agent_platform.runtime.base import RunContext

        ctx = RunContext()
        text = await runtime.run_turn(spec=spec, user_text=prompt, context=ctx)
        print(text)


async def _run_orchestrator_repl(*, initial: str, debug: bool) -> None:
    async with OllamaRuntime(debug=debug) as ollama, ClaudeSdkRuntime() as claude:
        app = build_orchestrator(ollama=ollama, claude=claude)
        state: OrchestratorState = {"failures": 0, "artifacts": {}}

        # If we have an initial prompt, run once and exit.
        if initial.strip():
            state["user_text"] = initial.strip()
            state = await app.ainvoke(state)  # type: ignore[attr-defined]
            print(state.get("response") or "")
            return

        print("SoftOne Orchestrator (LangGraph). Type /exit to quit.")
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
            state["user_text"] = user_text
            state = await app.ainvoke(state)  # type: ignore[attr-defined]
            print(f"\nAgent[{state.get('route')}|{state.get('runtime')}]: {state.get('response') or ''}")


async def main() -> None:
    load_dotenv()

    args = _build_argparser().parse_args()
    settings = load_agent_platform_settings(cli_debug=bool(args.debug))
    configure_logging(debug=settings.debug)

    if args.mode == "single":
        if not args.prompt.strip():
            raise SystemExit("Single mode requires a prompt argument.")
        await _run_single(
            prompt=args.prompt,
            agent_name=args.agent,
            runtime_name=args.runtime,
            debug=settings.debug,
        )
        return

    await _run_orchestrator_repl(initial=args.prompt, debug=settings.debug)


if __name__ == "__main__":
    asyncio.run(main())

