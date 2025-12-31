import os
from pathlib import Path
from typing import List


def _split_allowed_roots(raw: str) -> List[str]:
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
        return path == root or path.is_relative_to(root)
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


def safe_path(user_path: str, root_dir: Path) -> Path:
    s = (user_path or "").strip()
    if s == "":
        raise ValueError("path is empty")

    p = Path(s).expanduser()
    root = root_dir.resolve()

    if not p.is_absolute():
        resolved = (root_dir / p).resolve()
        if resolved != root and root not in resolved.parents:
            raise ValueError("path escapes root directory")
        return resolved

    resolved = p.resolve()

    if resolved == root or root in resolved.parents:
        return resolved

    allowed_roots = _get_allowed_roots()
    if not allowed_roots:
        raise ValueError("absolute paths are disabled (set MCP_ALLOWED_ROOTS)")

    if not _is_within_allowed_roots(resolved, allowed_roots):
        raise ValueError("path is outside allowed roots")

    return resolved
