# Polish plan

Goal: a hackathon reviewer skimming for ~1 minute sees a working, honest, clean agent platform.
Branch `polish`, one commit per item, fast-forward merge on sign-off. This file is deleted in the last commit.

## Done means

- A fresh clone works via the README quickstart (uv **or** pip), first try, on mock data.
- README first screen: pitch, mermaid architecture diagram, real demo transcript.
- Every README claim is true in code. Tests + ruff pass in CI, with a badge.
- `agent_platform/` reads in 30 seconds: router -> department specs -> runtimes, plus a write gate.

## Checklist

- [x] **1. Install fixes.** Package config so `pip install -e .` works; declare `mcp`; pytest/ruff as a dev
      group; empty `.env` values fall back to mock defaults; drop the duplicate `pytest.ini`.
- [x] **2. One package, one CLI.** Merge `agent_core/` into `agent_platform/` (delete the shims); delete
      `agent/`, `apps/` and `agent_platform/run.py`. Single entrypoint `python -m agent_platform` with
      `--runtime ollama|claude`; Claude escalation only when `ANTHROPIC_API_KEY` is set; a one-line hint
      when Ollama isn't running.
- [x] **3. Remove clutter.** Delete `cursorrules.md`, `tools/`, `docs/TODO.md`, `mcp_server.py`,
      `simple_route`, `ToolMeta`; move `softone.md` to `docs/`; drop Obsidian wording and ignore line;
      `main.py` becomes a test; drop "V1/later" comments. Docs: regenerate the stale tools catalog from the
      live server (+ drift test), fix stale tool names, convert wiki-links.
- [x] **4. Real department routing.** Route -> sales/inventory/finance spec; delete `ops`, move workflow
      tools to sales; a clarify reply of `sales|inventory|finance` sends the original text there; one shared
      conversation history across departments; Claude runtime rebuilds its client when the spec changes.
- [x] **5. Write-confirmation gate (code-enforced).** Write tools blocked until the user's next turn starts
      with a fixed approval word; a yes approves only the previously blocked tool names, once each. Both
      runtimes; tests.
- [x] **6. Lint.** Pin ruff defaults + `I` in `pyproject.toml`; clean.
- [ ] **7. CI.** GitHub Actions: pytest + ruff; badge in README.
- [ ] **8. README.** Pitch, mermaid diagram, real demo transcript (local Ollama; no paid API calls),
      quickstart, 4-line glossary (department agent, route, runtime, escalation), 2-3 doc links.
- [ ] **9. Final check.** Fresh clone -> quickstart -> tests; delete this file.
