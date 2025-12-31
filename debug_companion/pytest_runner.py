import os
import subprocess
import sys
from pathlib import Path
from typing import Any, Callable, Dict

from debug_companion.path_safety import safe_path


def run_pytest_impl(
    *,
    target: str,
    root_dir: Path,
    default_target: str,
    max_output_lines: int,
    timeout_seconds: int,
    logger,
    subprocess_run: Callable[..., Any],  # <-- NEW
) -> Dict[str, Any]:
    tgt = (target or "").strip() or default_target

    try:
        tgt_path = safe_path(tgt, root_dir=root_dir)
    except Exception as e:
        return {"ok": False, "error": str(e)}

    if not tgt_path.exists():
        return {"ok": False, "error": f"target not found: {tgt}"}

    max_output_lines = max(1, min(int(max_output_lines), 2000))
    timeout_seconds = max(5, min(int(timeout_seconds), 300))

    cmd = [sys.executable, "-m", "pytest", "-q", "--maxfail=1", str(tgt_path)]

    env = dict(os.environ)
    env["PYTEST_DISABLE_PLUGIN_AUTOLOAD"] = "1"

    root = root_dir.resolve()
    tp = tgt_path.resolve()
    if tp == root or root in tp.parents:
        project_cwd = str(root)
    else:
        project_cwd = str(tp if tp.is_dir() else tp.parent)

    logger.info("Running: %s", " ".join(cmd))
    logger.info("CWD: %s", project_cwd)

    try:
        proc = subprocess_run(
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

    output = (getattr(proc, "stdout", "") or "") + (
        "\n" + getattr(proc, "stderr", "") if getattr(proc, "stderr", "") else ""
    )
    lines = output.splitlines()
    tail = lines[-max_output_lines:]

    return {
        "ok": True,
        "target": tgt,
        "exit_code": int(getattr(proc, "returncode", 0)),
        "cmd": cmd,
        "output_tail": "\n".join(tail),
        "output_line_count": len(lines),
        "python": sys.executable,
        "cwd": project_cwd,
    }
