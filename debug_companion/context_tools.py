import re
from pathlib import Path
from typing import Any, Dict, List, Optional

from debug_companion.path_safety import safe_path


def extract_failures_impl(*, pytest_output: str, limit: int, base_dir: str, root_dir: Path) -> Dict[str, Any]:
    text = (pytest_output or "")
    if text.strip() == "":
        return {"ok": False, "error": "pytest_output is empty"}

    lim = max(1, min(int(limit), 50))
    pattern = re.compile(r"(?P<file>[A-Za-z0-9_./\\:\-]+\.py):(?P<line>\d+):")

    failures: List[Dict[str, Any]] = []
    seen = set()

    safe_base: Optional[Path] = None
    if base_dir.strip():
        try:
            safe_base = safe_path(base_dir, root_dir=root_dir)
        except Exception:
            safe_base = None

    for m in pattern.finditer(text):
        f_raw = m.group("file")
        f_norm = f_raw.replace("\\", "/")
        line = int(m.group("line"))
        key = (f_norm, line)
        if key in seen:
            continue
        seen.add(key)

        item: Dict[str, Any] = {"path": f_norm, "line": line}

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
            try:
                abs_p = Path(resolved_abs).resolve()
                root = root_dir.resolve()
                if abs_p == root or root in abs_p.parents:
                    item["path_for_open_context"] = abs_p.relative_to(root).as_posix()
                    item["open_context_base_dir"] = ""
                else:
                    item["path_for_open_context"] = resolved_abs
                    item["open_context_base_dir"] = ""
            except Exception:
                item["path_for_open_context"] = f_norm
                item["open_context_base_dir"] = str(safe_base) if safe_base else ""
        else:
            item["path_for_open_context"] = f_norm
            item["open_context_base_dir"] = str(safe_base) if safe_base else ""

        failures.append(item)
        if len(failures) >= lim:
            break

    return {"ok": True, "count": len(failures), "failures": failures}


def open_context_impl(*, path: str, line: int, radius: int, base_dir: str, root_dir: Path) -> Dict[str, Any]:
    raw = (path or "").strip()
    if raw == "":
        return {"ok": False, "error": "path is empty"}

    try:
        p = Path(raw).expanduser()
        if (not p.is_absolute()) and base_dir.strip():
            base = safe_path(base_dir, root_dir=root_dir)
            candidate = (base / p).resolve()
            file_path = safe_path(str(candidate), root_dir=root_dir)
        else:
            file_path = safe_path(raw, root_dir=root_dir)
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
