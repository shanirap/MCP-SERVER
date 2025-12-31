# Debug Companion MCP (Pytest Debugging Agent)

A local MCP server that helps an AI coding agent debug Python projects by:
- Running pytest safely via subprocess
- Extracting failure locations (file:line)
- Opening code context around the failure
- (Optional) Asking Gemini for a fix suggestion

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

## Available tools
- `ping` — health check
- `run_pytest(target, max_output_lines, timeout_seconds)` — run pytest safely
- `extract_failures(pytest_output, limit, base_dir)` — parse `file.py:line:` from pytest output
- `open_context(path, line, radius, base_dir)` — return a code window around a line
- `debug_project(target, ...)` — orchestrates:
  `run_pytest → extract_failures → open_context → (optional) Gemini analysis`

## Recommended demo flow
1. Run `debug_project` on `demo_project` (intentionally contains a failing test).
2. Observe: extracted `file:line` + code context window.
3. Apply the suggested fix (or a one-line fix manually).
4. Re-run → tests pass.

## Environment variables
- `GEMINI_API_KEY` — enable Gemini analysis (optional)
- `MCP_ALLOWED_ROOTS` — allow access to absolute paths outside the server root (optional)

## CI
GitHub Actions runs server tests on each push/PR:
- workflow: `.github/workflows/tests.yml`

## Notes
- `demo_project` is intended for demonstration and may contain a deliberate failing test.
- Server tests live under `tests/`.
