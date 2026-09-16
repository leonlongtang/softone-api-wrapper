## Department Orchestrator CLI

Interactive CLI chat that routes each message to one of:
- Sales
- Inventory
- Finance

It uses the existing orchestrator graph and runtimes in this repo.

### Run

From the repo root:

```bash
.\.venv\Scripts\python.exe apps\cli_orchestrator\run.py
```

Or as a module (also works well with tooling):

```bash
.\.venv\Scripts\python.exe -m apps.cli_orchestrator.run
```

Optional single-turn:

```bash
.\.venv\Scripts\python.exe apps\cli_orchestrator\run.py "List unpaid invoices for customer 47"
```

