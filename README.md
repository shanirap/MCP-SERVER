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

## CI
GitHub Actions runs server tests on each push/PR:
- workflow: `.github/workflows/tests.yml`

## Tools
- `ping` — health check
- `run_pytest(target, max_output_lines=200, timeout_seconds=30)` — run pytest safely (bounded output + timeout)
- `extract_failures(pytest_output, limit=5, base_dir=".")` — parse `file.py:line` locations from pytest output
- `open_context(path, line, radius=12, base_dir=".")` — return a code window around a line
- `debug_project(target, ...)` — orchestrates:
  `run_pytest → extract_failures → open_context → (optional) Gemini analysis`
  
### Safety
pytest runs with a timeout + output cap, and file access is restricted to the server root unless explicitly allowlisted via `MCP_ALLOWED_ROOTS`.

## Quick demo
Run on the intentionally failing demo project:
```text
debug_project(target="demo_project")
```

Expected output (example):
```text
Failures:
- demo_project/test_calc.py:11 (test_divide_by_zero) — Failed: DID NOT RAISE ZeroDivisionError

Context (±12):
  10 def test_divide_by_zero():
  11     with pytest.raises(ZeroDivisionError):
  12         _ = divide(10, 0)
```

## Demo project
- `demo_project/` — minimal demo with an intentional failing test (fast to understand)

## Environment variables
- `GEMINI_API_KEY` — enable Gemini analysis (optional)
- `MCP_ALLOWED_ROOTS` — allow access to absolute paths outside the server root (optional)

## Future work (ideas)
- **Test scaffolding (opt-in):** detect projects with no tests and optionally generate a minimal smoke test skeleton (e.g., `tests/test_smoke.py`) to validate imports / basic execution before running deeper debugging flows.
- **Richer failure parsing:** better extraction for parameterized tests and multi-traceback outputs.
- **Autofix loop:** apply a patch (manual approval) → re-run pytest → summarize diff + results.

> Note: Automatically generating meaningful tests is highly project-specific. The goal would be lightweight scaffolding (opt-in), not replacing real, requirement-driven tests.


