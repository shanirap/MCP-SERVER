from pathlib import Path
import pytest

import server as mod


def test_extract_failures_parses_file_line(tmp_path, monkeypatch):
    monkeypatch.setattr(mod, "ROOT_DIR", tmp_path)

    out = "demo_project/test_calc.py:12: AssertionError\nother stuff\n"
    res = mod.extract_failures(pytest_output=out, limit=10, base_dir=str(tmp_path))
    assert res["ok"] is True
    assert res["count"] >= 1
    assert res["failures"][0]["line"] == 12


def test_open_context_reads_window(tmp_path, monkeypatch):
    monkeypatch.setattr(mod, "ROOT_DIR", tmp_path)

    f = tmp_path / "x.py"
    f.write_text("\n".join([f"line{i}" for i in range(1, 101)]), encoding="utf-8")

    res = mod.open_context(path="x.py", line=50, radius=5)
    assert res["start_line"] == 45
    assert res["end_line"] == 55
def test_extract_failures_dedupe_and_limit(tmp_path, monkeypatch):
    monkeypatch.setattr(mod, "ROOT_DIR", tmp_path)

    out = "\n".join([
        "a.py:10: AssertionError",
        "a.py:10: AssertionError",  # duplicate
        "b.py:20: ValueError",
        "c.py:30: TypeError",
    ])

    res = mod.extract_failures(pytest_output=out, limit=2, base_dir=str(tmp_path))
    assert res["ok"] is True
    assert res["count"] == 2
    assert res["failures"][0]["line"] == 10
    assert res["failures"][1]["line"] == 20

def test_open_context_bounds_and_missing_file(tmp_path, monkeypatch):
    monkeypatch.setattr(mod, "ROOT_DIR", tmp_path)

    f = tmp_path / "x.py"
    f.write_text("\n".join([f"line{i}" for i in range(1, 11)]), encoding="utf-8")

    res1 = mod.open_context(path="x.py", line=0, radius=1)
    assert res1["ok"] is True
    assert res1["focus_line"] == 1
    assert res1["start_line"] == 1
    assert res1["end_line"] == 6  # radius is clamped to min 5

    res2 = mod.open_context(path="x.py", line=999, radius=1)
    assert res2["ok"] is True
    assert res2["focus_line"] == 10

    res3 = mod.open_context(path="no_such.py", line=1, radius=5)
    assert res3["ok"] is False
