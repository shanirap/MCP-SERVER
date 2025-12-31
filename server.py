import logging
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

try:
    import google.generativeai as genai
except ImportError:  # pragma: no cover
    genai = None

from dotenv import load_dotenv
from mcp.server.fastmcp import FastMCP

load_dotenv()

# IMPORTANT: Do not print to stdout in stdio servers. Use logging (stderr) only.
logging.basicConfig(level=logging.INFO)
log = logging.getLogger("debug-companion")

mcp = FastMCP("debug-companion")

ROOT_DIR = Path(__file__).resolve().parent
DEFAULT_TARGET = "demo_project"


# -----------------------------------------------------------------------------
# SAFE PATH ACCESS (allow absolute paths only under allowlisted roots)
# -----------------------------------------------------------------------------

def _split_allowed_roots(raw: str) -> List[str]:
    """
    Windows typical separator is ';'. Unix is ':' (os.pathsep).
    We accept both.
    """
    s = (raw or "").strip()
    if not s:
        return []
    parts: List[str] = []
    for chunk in s.split(";"):
        parts.extend(chunk.split(os.pathsep))
    return [p.strip().strip('"') for p in parts if p.strip()]


def _parse_allowed_roots(raw: str) -> List[Path]:
    roots: List[Path] = []
    for p in _split_allowed_roots(raw):
        try:
            roots.append(Path(p).expanduser().resolve())
        except Exception:
            pass
    return roots


def _get_allowed_roots() -> List[Path]:
    return _parse_allowed_roots(os.environ.get("MCP_ALLOWED_ROOTS", ""))


def _is_relative_to(path: Path, root: Path) -> bool:
    try:
        return path == root or path.is_relative_to(root)  # py3.9+
    except Exception:
        try:
            path.relative_to(root)
            return True
        except Exception:
            return False


def _is_within_allowed_roots(p: Path, allowed_roots: List[Path]) -> bool:
    rp = p.resolve()
    for root in allowed_roots:
        if _is_relative_to(rp, root):
            return True
    return False


def _safe_path(user_path: str) -> Path:
    """
    Resolve a path safely.

    Rules:
    - Relative paths are resolved under ROOT_DIR.
    - Absolute paths are allowed if:
        (a) they are inside ROOT_DIR, OR
        (b) they are inside one of allowed roots (MCP_ALLOWED_ROOTS)
    """
    s = (user_path or "").strip()
    if s == "":
        raise ValueError("path is empty")

    p = Path(s).expanduser()
    root = ROOT_DIR.resolve()

    # Relative path -> resolve under ROOT_DIR
    if not p.is_absolute():
        resolved = (ROOT_DIR / p).resolve()
        if resolved != root and root not in resolved.parents:
            raise ValueError("path escapes root directory")
        return resolved

    # Absolute path
    resolved = p.resolve()

    # Always allow absolute paths that stay inside ROOT_DIR
    if resolved == root or root in resolved.parents:
        return resolved

    # Otherwise require allowlist
    allowed_roots = _get_allowed_roots()
    if not allowed_roots:
        raise ValueError("absolute paths are disabled (set MCP_ALLOWED_ROOTS)")

    if not _is_within_allowed_roots(resolved, allowed_roots):
        raise ValueError("path is outside allowed roots")

    return resolved


# -----------------------------------------------------------------------------
# TOOLS
# -----------------------------------------------------------------------------

@mcp.tool()
def ping() -> Dict[str, Any]:
    return {"ok": True, "msg": "pong"}


@mcp.tool()
def run_pytest(target: str = "", max_output_lines: int = 250, timeout_seconds: int = 30) -> Dict[str, Any]:
    """
    Run pytest using a subprocess (safe for stdio MCP servers).

    - Uses current interpreter: sys.executable -m pytest
    - Disables plugin autoload to avoid hangs
    - stdin is DEVNULL to prevent waiting for input
    - Runs from the project directory (cwd) for better compatibility
    """
    tgt = (target or "").strip() or DEFAULT_TARGET

    try:
        tgt_path = _safe_path(tgt)
    except Exception as e:
        return {"ok": False, "error": str(e)}

    if not tgt_path.exists():
        return {"ok": False, "error": f"target not found: {tgt}"}

    max_output_lines = max(1, min(int(max_output_lines), 2000))
    timeout_seconds = max(5, min(int(timeout_seconds), 300))

    cmd = [
        sys.executable, "-m", "pytest",
        "-q",
        "--maxfail=1",
        str(tgt_path),
    ]

    env = dict(os.environ)
    env["PYTEST_DISABLE_PLUGIN_AUTOLOAD"] = "1"

    root = ROOT_DIR.resolve()
    tp = tgt_path.resolve()

    if tp == root or root in tp.parents:
        # פרויקט שנמצא בתוך ROOT_DIR -> כמו פעם
        project_cwd = str(root)
    else:
        # פרויקט חיצוני -> להריץ מתוך התיקייה שלו
        project_cwd = str(tp if tp.is_dir() else tp.parent)

    log.info("Running: %s", " ".join(cmd))
    log.info("CWD: %s", project_cwd)

    try:
        proc = subprocess.run(
            cmd,
            cwd=project_cwd,
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
            env=env,
            stdin=subprocess.DEVNULL,
        )
    except subprocess.TimeoutExpired as e:
        stdout = getattr(e, "stdout", None)
        if stdout is None:
            stdout = getattr(e, "output", "")

        stderr = getattr(e, "stderr", "") or ""
        out = (stdout or "") + ("\n" + stderr if stderr else "")

        lines = out.splitlines()
        tail = lines[-max_output_lines:]
        return {
            "ok": False,
            "error": f"pytest timed out ({timeout_seconds}s)",
            "cmd": cmd,
            "target": tgt,
            "output_tail": "\n".join(tail),
            "output_line_count": len(lines),
            "python": sys.executable,
            "cwd": project_cwd,
        }
    except Exception as e:
        return {
            "ok": False,
            "error": f"failed to run pytest: {e}",
            "cmd": cmd,
            "target": tgt,
            "python": sys.executable,
            "cwd": project_cwd,
        }

    output = (proc.stdout or "") + ("\n" + proc.stderr if proc.stderr else "")
    lines = output.splitlines()
    tail = lines[-max_output_lines:]

    return {
        "ok": True,
        "target": tgt,
        "exit_code": int(proc.returncode),
        "cmd": cmd,
        "output_tail": "\n".join(tail),
        "output_line_count": len(lines),
        "python": sys.executable,
        "cwd": project_cwd,
    }


@mcp.tool()
def extract_failures(pytest_output: str, limit: int = 10, base_dir: str = "") -> Dict[str, Any]:
    """
    Extract failure locations from pytest text output.

    If base_dir is provided (usually pytest cwd), we also compute:
    - resolved_path (absolute)
    - path_for_open_context + open_context_base_dir
      so the next tool call can work as a pipeline without guessing.
    """
    text = (pytest_output or "")
    if text.strip() == "":
        return {"ok": False, "error": "pytest_output is empty"}

    lim = max(1, min(int(limit), 50))

    pattern = re.compile(r"(?P<file>[A-Za-z0-9_./\\:\-]+\.py):(?P<line>\d+):")
    failures: List[Dict[str, Any]] = []
    seen = set()

    # Normalize base_dir once (optional)
    safe_base: Optional[Path] = None
    if base_dir.strip():
        try:
            safe_base = _safe_path(base_dir)
        except Exception:
            safe_base = None  # still return raw paths

    for m in pattern.finditer(text):
        f_raw = m.group("file")
        f_norm = f_raw.replace("\\", "/")
        line = int(m.group("line"))
        key = (f_norm, line)
        if key in seen:
            continue
        seen.add(key)

        item: Dict[str, Any] = {"path": f_norm, "line": line}

        # If we can, compute a resolved absolute path
        resolved_abs: Optional[str] = None
        try:
            p = Path(f_raw).expanduser()
            if p.is_absolute():
                resolved_abs = str(p.resolve())
            elif safe_base is not None:
                resolved_abs = str((safe_base / p).resolve())
        except Exception:
            resolved_abs = None

        if resolved_abs:
            item["resolved_path"] = resolved_abs

            # Prepare best inputs for open_context:
            # - If resolved_abs is inside ROOT_DIR => pass path relative to ROOT_DIR (no allowlist needed)
            # - Else pass absolute (requires MCP_ALLOWED_ROOTS)
            try:
                abs_p = Path(resolved_abs).resolve()
                root = ROOT_DIR.resolve()
                if abs_p == root or root in abs_p.parents:
                    rel_to_root = abs_p.relative_to(root).as_posix()
                    item["path_for_open_context"] = rel_to_root
                    item["open_context_base_dir"] = ""
                else:
                    item["path_for_open_context"] = resolved_abs
                    item["open_context_base_dir"] = ""
            except Exception:
                # Fallback: still allow open_context to use base_dir with raw relative path
                item["path_for_open_context"] = f_norm
                item["open_context_base_dir"] = str(safe_base) if safe_base else ""
        else:
            # We couldn't resolve: keep raw and suggest base_dir for open_context
            item["path_for_open_context"] = f_norm
            item["open_context_base_dir"] = str(safe_base) if safe_base else ""

        failures.append(item)
        if len(failures) >= lim:
            break

    return {"ok": True, "count": len(failures), "failures": failures}

@mcp.tool()
def open_context(path: str, line: int, radius: int = 25, base_dir: str = "") -> Dict[str, Any]:
    """
    Return code context around a line number in a file.

    Behavior:
    - If `path` is relative:
        - if base_dir is provided: resolve relative to base_dir first.
        - else: resolve under ROOT_DIR.
    - If `path` is absolute: validated via _safe_path.
    """
    raw = (path or "").strip()
    if raw == "":
        return {"ok": False, "error": "path is empty"}

    try:
        p = Path(raw).expanduser()

        if (not p.is_absolute()) and base_dir.strip():
            # base_dir can be absolute (project cwd) or relative (under ROOT_DIR)
            base = _safe_path(base_dir)
            candidate = (base / p).resolve()
            file_path = _safe_path(str(candidate))
        else:
            file_path = _safe_path(raw)

    except Exception as e:
        return {"ok": False, "error": str(e)}

    if not file_path.exists() or not file_path.is_file():
        return {"ok": False, "error": f"file not found: {path}"}

    r = max(5, min(int(radius), 120))

    try:
        content = file_path.read_text(encoding="utf-8", errors="replace")
    except Exception as e:
        return {"ok": False, "error": f"failed reading file: {e}"}

    lines = content.splitlines()
    if not lines:
        return {"ok": False, "error": "file is empty"}

    try:
        focus = int(line)
    except Exception:
        focus = 1

    focus = max(1, min(focus, len(lines)))
    start = max(1, focus - r)
    end = min(len(lines), focus + r)

    window = [{"line": i, "text": lines[i - 1]} for i in range(start, end + 1)]

    return {
        "ok": True,
        "path": str(file_path),
        "focus_line": focus,
        "start_line": start,
        "end_line": end,
        "content": window,
    }


def _get_gemini_model() -> Optional[Any]:
    """
    Lazily initialize Gemini model so the tool works even if env vars are set after import.
    """
    if genai is None:
        return None
    api_key = (os.environ.get("GEMINI_API_KEY") or "").strip()
    if not api_key:
        return None

    try:
        genai.configure(api_key=api_key)
        return genai.GenerativeModel("gemini-1.5-flash")
    except Exception as e:
        log.warning("Failed to init Gemini model: %s", e)
        return None


@mcp.tool()
def analyze_error_with_gemini(error_message: str, code_context: str = "") -> Dict[str, Any]:
    """
    Send the error and code context to Gemini API for analysis and fix suggestions.
    """
    model = _get_gemini_model()
    if model is None:
        return {"ok": False, "error": "Gemini API Key not configured or model init failed"}

    prompt = f"""
I have a Python test failure.

Error message:
{error_message}

Code context:
{code_context}

Please explain why this error is happening and suggest a fix.
""".strip()

    try:
        response = model.generate_content(prompt)
        return {"ok": True, "analysis": getattr(response, "text", str(response))}
    except Exception as e:
        return {"ok": False, "error": str(e)}


# -----------------------------------------------------------------------------
# ORCHESTRATOR TOOL
# -----------------------------------------------------------------------------
@mcp.tool()
def debug_project(
    target: str,
    max_output_lines: int = 1200,
    timeout_seconds: int = 60,
    failure_limit: int = 1,
    radius: int = 35,
) -> Dict[str, Any]:
    """
    Pipeline:
      run_pytest -> extract_failures (with base_dir=pytest_cwd) -> open_context -> analyze_error_with_gemini
    """
    test_res = run_pytest(
        target=target,
        max_output_lines=max_output_lines,
        timeout_seconds=timeout_seconds,
    )
    if not test_res.get("ok"):
        return {"ok": False, "stage": "run_pytest", "details": test_res}

    exit_code = int(test_res.get("exit_code", 0))
    output_tail = (test_res.get("output_tail") or "")
    pytest_cwd = (test_res.get("cwd") or "").strip()

    if exit_code == 0:
        return {"ok": True, "stage": "done", "msg": "All tests passed", "pytest": test_res}

    # IMPORTANT: pass pytest_cwd as base_dir so relative failure paths (e.g. test_calc.py) can be resolved
    fails_res = extract_failures(pytest_output=output_tail, limit=failure_limit, base_dir=pytest_cwd)
    if not fails_res.get("ok") or fails_res.get("count", 0) == 0:
        return {
            "ok": True,
            "stage": "extract_failures",
            "msg": "Tests failed but could not parse a file:line location from output_tail",
            "pytest": test_res,
            "extract": fails_res,
        }

    first = fails_res["failures"][0]
    line_no = int(first.get("line", 1))

    # Use the prepared fields from extract_failures for a clean pipeline
    ctx_path = (first.get("path_for_open_context") or first.get("path") or "").strip()
    ctx_base = (first.get("open_context_base_dir") or "").strip()

    ctx_res = open_context(path=ctx_path, line=line_no, radius=radius, base_dir=ctx_base)
    if not ctx_res.get("ok"):
        return {
            "ok": True,
            "stage": "open_context",
            "msg": "Got failure location but could not open file context",
            "pytest": test_res,
            "failure": first,
            "context": ctx_res,
            "debug_info": {
                "used_path": ctx_path,
                "used_base_dir": ctx_base,
                "pytest_cwd": pytest_cwd,
            },
        }

    content = ctx_res.get("content") or []
    context_text = "\n".join([f'{x.get("line")}: {x.get("text")}' for x in content])

    gem_res = analyze_error_with_gemini(
        error_message=output_tail,
        code_context=context_text,
    )

    return {
        "ok": True,
        "stage": "done",
        "pytest": test_res,
        "failure": first,
        "context": ctx_res,
        "gemini": gem_res,
    }

if __name__ == "__main__":
    mcp.run()
