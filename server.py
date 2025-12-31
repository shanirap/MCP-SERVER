import logging
import os
import re
import subprocess  # <-- NEW: tests expect server.subprocess
import sys
from pathlib import Path
from typing import Any, Dict

from dotenv import load_dotenv
from mcp.server.fastmcp import FastMCP

from debug_companion.path_safety import safe_path as _safe_path_core
from debug_companion.pytest_runner import run_pytest_impl
from debug_companion.context_tools import extract_failures_impl, open_context_impl
from debug_companion.gemini_client import analyze_error_with_gemini_impl
from debug_companion.orchestrator import debug_project_impl

try:
    import google.generativeai as genai
except ImportError:  # pragma: no cover
    genai = None

load_dotenv()

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("debug-companion")

mcp = FastMCP("debug-companion")

# Keep these globals for tests that monkeypatch them
ROOT_DIR = Path(__file__).resolve().parent
DEFAULT_TARGET = "demo_project"


# --- BACKWARD COMPATIBILITY for tests ---
def _safe_path(user_path: str) -> Path:
    # Uses current ROOT_DIR (which tests monkeypatch)
    return _safe_path_core(user_path, root_dir=ROOT_DIR)


@mcp.tool()
def ping() -> Dict[str, Any]:
    return {"ok": True, "msg": "pong"}


@mcp.tool()
def run_pytest(target: str = "", max_output_lines: int = 250, timeout_seconds: int = 30) -> Dict[str, Any]:
    return run_pytest_impl(
        target=target,
        root_dir=ROOT_DIR,
        default_target=DEFAULT_TARGET,
        max_output_lines=max_output_lines,
        timeout_seconds=timeout_seconds,
        logger=log,
        subprocess_run=subprocess.run,  # <-- CRITICAL: uses server.subprocess.run
    )


@mcp.tool()
def extract_failures(pytest_output: str, limit: int = 10, base_dir: str = "") -> Dict[str, Any]:
    return extract_failures_impl(
        pytest_output=pytest_output,
        limit=limit,
        base_dir=base_dir,
        root_dir=ROOT_DIR,
    )


@mcp.tool()
def open_context(path: str, line: int, radius: int = 25, base_dir: str = "") -> Dict[str, Any]:
    return open_context_impl(
        path=path,
        line=line,
        radius=radius,
        base_dir=base_dir,
        root_dir=ROOT_DIR,
    )


@mcp.tool()
def analyze_error_with_gemini(error_message: str, code_context: str = "") -> Dict[str, Any]:
    return analyze_error_with_gemini_impl(
        genai_module=genai,
        logger=log,
        error_message=error_message,
        code_context=code_context,
    )


@mcp.tool()
def debug_project(
    target: str,
    max_output_lines: int = 1200,
    timeout_seconds: int = 60,
    failure_limit: int = 1,
    radius: int = 35,
) -> Dict[str, Any]:
    return debug_project_impl(
        target=target,
        root_dir=ROOT_DIR,
        run_pytest_fn=lambda **kw: run_pytest(**kw),
        extract_failures_fn=lambda **kw: extract_failures(**kw),
        open_context_fn=lambda **kw: open_context(**kw),
        analyze_fn=lambda **kw: analyze_error_with_gemini(**kw),
        max_output_lines=max_output_lines,
        timeout_seconds=timeout_seconds,
        failure_limit=failure_limit,
        radius=radius,
    )


if __name__ == "__main__":
    mcp.run()
