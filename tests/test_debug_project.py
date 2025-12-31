import pytest
import server as mod


def test_debug_project_pipeline(monkeypatch):
    def fake_run_pytest(target, max_output_lines, timeout_seconds):
        return {"ok": True, "exit_code": 1, "output_tail": "t.py:7: AssertionError", "cwd": "/tmp"}

    def fake_extract_failures(pytest_output, limit, base_dir):
        return {"ok": True, "count": 1, "failures": [{"path_for_open_context": "t.py", "line": 7}]}

    def fake_open_context(path, line, radius, base_dir):
        return {"ok": True, "content": [{"line": 7, "text": "assert 1 == 2"}]}

    def fake_gemini(error_message, code_context):
        return {"ok": True, "analysis": "fix the assertion"}

    monkeypatch.setattr(mod, "run_pytest", fake_run_pytest)
    monkeypatch.setattr(mod, "extract_failures", fake_extract_failures)
    monkeypatch.setattr(mod, "open_context", fake_open_context)
    monkeypatch.setattr(mod, "analyze_error_with_gemini", fake_gemini)

    res = mod.debug_project(target="demo_project")
    assert res["ok"] is True
    assert res["stage"] == "done"
    assert res["gemini"]["ok"] is True

def test_debug_project_all_tests_pass(monkeypatch):
    def fake_run_pytest(target, max_output_lines, timeout_seconds):
        return {"ok": True, "exit_code": 0, "output_tail": "OK", "cwd": "X"}

    monkeypatch.setattr(mod, "run_pytest", fake_run_pytest)

    res = mod.debug_project(target="demo_project")
    assert res["ok"] is True
    assert res["stage"] == "done"
    assert res["msg"] == "All tests passed"


def test_debug_project_extract_failures_not_found(monkeypatch):
    def fake_run_pytest(target, max_output_lines, timeout_seconds):
        return {"ok": True, "exit_code": 1, "output_tail": "FAILED but no file line here", "cwd": "X"}

    def fake_extract_failures(pytest_output, limit, base_dir):
        return {"ok": True, "count": 0, "failures": []}

    monkeypatch.setattr(mod, "run_pytest", fake_run_pytest)
    monkeypatch.setattr(mod, "extract_failures", fake_extract_failures)

    res = mod.debug_project(target="demo_project")
    assert res["ok"] is True
    assert res["stage"] == "extract_failures"


def test_debug_project_open_context_failure(monkeypatch):
    def fake_run_pytest(target, max_output_lines, timeout_seconds):
        return {"ok": True, "exit_code": 1, "output_tail": "t.py:7: AssertionError", "cwd": "X"}

    def fake_extract_failures(pytest_output, limit, base_dir):
        return {
            "ok": True,
            "count": 1,
            "failures": [{"path_for_open_context": "t.py", "open_context_base_dir": "", "line": 7}],
        }

    def fake_open_context(path, line, radius, base_dir):
        return {"ok": False, "error": "file not found"}

    monkeypatch.setattr(mod, "run_pytest", fake_run_pytest)
    monkeypatch.setattr(mod, "extract_failures", fake_extract_failures)
    monkeypatch.setattr(mod, "open_context", fake_open_context)

    res = mod.debug_project(target="demo_project")
    assert res["ok"] is True
    assert res["stage"] == "open_context"
