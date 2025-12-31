from typing import Any, Dict
from pathlib import Path


def debug_project_impl(
    *,
    target: str,
    root_dir: Path,
    run_pytest_fn,
    extract_failures_fn,
    open_context_fn,
    analyze_fn,
    max_output_lines: int,
    timeout_seconds: int,
    failure_limit: int,
    radius: int,
) -> Dict[str, Any]:
    test_res = run_pytest_fn(
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

    fails_res = extract_failures_fn(pytest_output=output_tail, limit=failure_limit, base_dir=pytest_cwd)
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

    ctx_path = (first.get("path_for_open_context") or first.get("path") or "").strip()
    ctx_base = (first.get("open_context_base_dir") or "").strip()

    ctx_res = open_context_fn(path=ctx_path, line=line_no, radius=radius, base_dir=ctx_base)
    if not ctx_res.get("ok"):
        return {
            "ok": True,
            "stage": "open_context",
            "msg": "Got failure location but could not open file context",
            "pytest": test_res,
            "failure": first,
            "context": ctx_res,
            "debug_info": {"used_path": ctx_path, "used_base_dir": ctx_base, "pytest_cwd": pytest_cwd},
        }

    content = ctx_res.get("content") or []
    context_text = "\n".join([f'{x.get("line")}: {x.get("text")}' for x in content])

    gem_res = analyze_fn(error_message=output_tail, code_context=context_text)

    return {
        "ok": True,
        "stage": "done",
        "pytest": test_res,
        "failure": first,
        "context": ctx_res,
        "gemini": gem_res,
    }
