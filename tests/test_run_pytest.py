import subprocess
from types import SimpleNamespace
import pytest

import server as mod


def test_run_pytest_success_mocked(tmp_path, monkeypatch):
    monkeypatch.setattr(mod, "ROOT_DIR", tmp_path)

    target_dir = tmp_path / "demo_project"
    target_dir.mkdir()
    (target_dir / "test_dummy.py").write_text("def test_ok(): assert True", encoding="utf-8")

    
    def fake_run(*args, **kwargs):
        return SimpleNamespace(returncode=0, stdout="OK\n", stderr="")


    monkeypatch.setattr(mod.subprocess, "run", fake_run)

    res = mod.run_pytest(target="demo_project", max_output_lines=10, timeout_seconds=10)
    assert res["ok"] is True
    assert res["exit_code"] == 0
    assert "pytest" in " ".join(res["cmd"])
    assert res["cwd"] == str(tmp_path)


def test_run_pytest_timeout(tmp_path, monkeypatch):
    monkeypatch.setattr(mod, "ROOT_DIR", tmp_path)

    target_dir = tmp_path / "demo_project"
    target_dir.mkdir()

    def fake_run(*args, **kwargs):
        raise subprocess.TimeoutExpired(
            cmd=["pytest"],
            timeout=5,
            output="A\nB\n",
            stderr="ERR\n",
        )


    monkeypatch.setattr(mod.subprocess, "run", fake_run)

    res = mod.run_pytest(target="demo_project", timeout_seconds=5, max_output_lines=2)
    assert res["ok"] is False
    assert "timed out" in res["error"]
    assert "output_tail" in res


def test_run_pytest_missing_target(tmp_path, monkeypatch):
    monkeypatch.setattr(mod, "ROOT_DIR", tmp_path)
    res = mod.run_pytest(target="no_such_folder")
    assert res["ok"] is False
    assert "target not found" in res["error"]

def test_run_pytest_clamps_timeout_and_max_output_lines(tmp_path, monkeypatch):
    monkeypatch.setattr(mod, "ROOT_DIR", tmp_path)

    target_dir = tmp_path / "demo_project"
    target_dir.mkdir()

    seen = {"timeout": None}

    def fake_run(cmd, cwd, capture_output, text, timeout, env, stdin):
        seen["timeout"] = timeout
        raise subprocess.TimeoutExpired(
            cmd=cmd,
            timeout=timeout,
            output="L1\nL2\nL3\nL4\nL5\n",
            stderr="ERR\n",
        )

    monkeypatch.setattr(mod.subprocess, "run", fake_run)

    res = mod.run_pytest(target="demo_project", timeout_seconds=1, max_output_lines=1)

    assert res["ok"] is False
    assert seen["timeout"] == 5  # clamped to min 5
    assert "timed out (5s)" in res["error"]
    assert res["output_tail"].count("\n") == 0  # max_output_lines=1 => single line
def test_run_pytest_external_target_sets_cwd_to_external_dir(tmp_path, monkeypatch):
    root = tmp_path / "root"
    root.mkdir()
    monkeypatch.setattr(mod, "ROOT_DIR", root)

    external = tmp_path / "external_project"
    external.mkdir()

    monkeypatch.setenv("MCP_ALLOWED_ROOTS", str(external))

    def fake_run(cmd, cwd, capture_output, text, timeout, env, stdin):
        return SimpleNamespace(returncode=0, stdout="OK\n", stderr="")

    monkeypatch.setattr(mod.subprocess, "run", fake_run)

    res = mod.run_pytest(target=str(external), timeout_seconds=10, max_output_lines=10)
    assert res["ok"] is True
    assert res["cwd"] == str(external)
