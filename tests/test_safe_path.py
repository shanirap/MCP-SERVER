import os
from pathlib import Path
import pytest

import server as mod


def test_safe_path_relative_ok(tmp_path, monkeypatch):
    # English comment: Move ROOT_DIR to an isolated temp folder
    monkeypatch.setattr(mod, "ROOT_DIR", tmp_path)

    p = mod._safe_path("a/b.txt")
    assert str(p).endswith(str(Path("a/b.txt")))
    assert tmp_path in p.parents


def test_safe_path_relative_escape_blocked(tmp_path, monkeypatch):
    monkeypatch.setattr(mod, "ROOT_DIR", tmp_path)

    with pytest.raises(ValueError):
        mod._safe_path("../outside.txt")


def test_safe_path_absolute_inside_root_allowed(tmp_path, monkeypatch):
    monkeypatch.setattr(mod, "ROOT_DIR", tmp_path)

    f = tmp_path / "x.py"
    f.write_text("print('x')", encoding="utf-8")

    p = mod._safe_path(str(f))
    assert p.resolve() == f.resolve()


def test_safe_path_absolute_outside_root_requires_allowlist(tmp_path, monkeypatch):
    monkeypatch.setattr(mod, "ROOT_DIR", tmp_path)

    outside = tmp_path.parent / "outside"
    outside.mkdir(exist_ok=True)
    f = outside / "z.py"
    f.write_text("pass", encoding="utf-8")

    monkeypatch.delenv("MCP_ALLOWED_ROOTS", raising=False)
    with pytest.raises(ValueError):
        mod._safe_path(str(f))


def test_safe_path_absolute_outside_root_allowed_by_allowlist(tmp_path, monkeypatch):
    monkeypatch.setattr(mod, "ROOT_DIR", tmp_path)

    outside = tmp_path.parent / "allowed_root"
    outside.mkdir(exist_ok=True)
    f = outside / "ok.py"
    f.write_text("pass", encoding="utf-8")

    monkeypatch.setenv("MCP_ALLOWED_ROOTS", str(outside))
    p = mod._safe_path(str(f))
    assert p.resolve() == f.resolve()

def test_safe_path_empty_rejected(tmp_path, monkeypatch):
    monkeypatch.setattr(mod, "ROOT_DIR", tmp_path)
    with pytest.raises(ValueError):
        mod._safe_path("")
    with pytest.raises(ValueError):
        mod._safe_path("   ")

