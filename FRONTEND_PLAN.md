# Frontend plan

A local web UI to chat with the agents and see what each turn did to the database. It is for you as a test bench
and for reviewers as the README demo. Run it with `python -m agent_platform.web` and open `http://127.0.0.1:8000`.

## Decisions

- **Stack.** Starlette + uvicorn, both already installed with `mcp`. One static `index.html` with plain JS. No new
  dependencies and no build step.
- **One chat at a time.** Local only (`127.0.0.1`), single user, no login, no saved history. The runtime
  (Ollama or Claude) is picked when a new chat starts. Escalation follows the CLI rule (on only if
  `ANTHROPIC_API_KEY` is set) and is shown as a badge.
- **Layout.** Chat on the left. Every reply gets a `department · runtime` badge, a **tool-call trace** and a
  **turn diff**. Database tabs on the right: the 6 business tables with changed rows highlighted, plus a
  **Tools** tab.
- **Turn diff.** The business rows a turn inserted, updated or deleted, before → after. It comes from a snapshot
  of `customers`, `items`, `orders`, `order_items`, `invoices_business` and `payments`, taken before and after
  the turn and compared by primary key.
- **Tool-call trace.** `WriteGate.check()` already sees every business tool call on both runtimes, so it
  records `(tool, args, status)` for the turn. Each status is one of ran, blocked or already-done. The trace has
  no tool results; the turn diff shows the effects.
- **Tools tab.** Each department's allowlist from `SPECS`, every tool tagged read or write from `WRITE_TOOLS`,
  with its one-line MCP description. There is no "run tool" button, because it would bypass the router and the
  gate.
- **Approve and Reject buttons** just send "yes" or "no". There is no second approval path.
- **Markdown replies** are rendered with `marked` + `DOMPurify` from a CDN, falling back to plain text.
- **One turn at a time.** Input is disabled while a turn runs, with a spinner and elapsed time. A failed turn
  shows an error bubble and the chat continues.
- **Reset DB** deletes the mock SQLite file (it is reseeded) and starts a new chat. The DB panel and Reset are
  hidden when `SOFTONE_MOCK=false`.

## Checklist

- [ ] 1. Gate records a per-turn tool-call trace (+ tests)
- [ ] 2. DB snapshot + turn diff for the 6 business tables (+ tests)
- [ ] 3. Starlette server: new chat, turn, db, reset, tools (+ test with a fake orchestrator)
- [ ] 4. `index.html`: chat, badges, trace, diff, approve buttons, DB tabs, Tools tab
- [ ] 5. Real run, screenshot, README (Quickstart command, Demo screenshot, "Turn diff" in glossary)
