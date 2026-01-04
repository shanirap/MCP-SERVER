# Debug Companion MCP (Pytest Debugging Agent)

Local MCP server that helps an AI coding agent debug Python projects by turning `pytest` failures into:
- Exact failure locations (`file:line`)
- A focused code context window around the failure
- Optional LLM suggestion (Gemini) for a fix

## Why this exists
When an agent gets a long pytest output, it often wastes time hunting for the real failure spot.
This server extracts the actionable bits and returns them in a structured, tool-friendly way.

## Requirements
- Python 3.12+
- uv

## Install
```bash
uv sync
```

## Run the MCP server
```bash
uv run python server.py
```

## Tools
- `ping` — health check
- `run_pytest(target, max_output_lines=200, timeout_seconds=30)` — run pytest safely (bounded output + timeout)
- `extract_failures(pytest_output, limit=5, base_dir=".")` — parse `file.py:line` locations from pytest output
- `open_context(path, line, radius=12, base_dir=".")` — return a code window around a line
- `debug_project(target, ...)` — orchestrates:
  `run_pytest → extract_failures → open_context → (optional) Gemini analysis`

## Quick demo
Run on the intentionally failing demo project:
```text
debug_project(target="demo_project")
```

Expected output (example):
```text
Failures:
- demo_project/some_module.py:42

Context (±12):
  36 def divide(a, b):
  37     ...
  42     return a / b
```

## Demo project
- `demo_project/` — minimal demo with an intentional failing test (fast to understand)
