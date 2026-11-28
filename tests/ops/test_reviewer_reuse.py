"""The independent reviewer reads one change once (2026-11-18, CI wall-clock).

Pins: the change key ignores blob ids and hunk line numbers (a clean merge-in of LIVE) and nothing
else; an earlier success is reused only from this PR's own release-gates runs, inside REUSE_DAYS,
with the same key; every screen still runs first; the reuse step never fails the job; and the
workflow skips the download and the models only on a hit."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path
from typing import Any

import pytest

ROOT = Path(__file__).resolve().parents[2]
_spec = importlib.util.spec_from_file_location(
    "independent_review_reuse_t", ROOT / "ops/release/independent_review.py"
)
assert _spec is not None and _spec.loader is not None
ir = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(ir)

REPO = "o/r"
OLD = "a" * 40
HEAD = "b" * 40
BASE = "c" * 40
NOW = 1_800_000_000.0  # 2027-01-15


def _diff(
    body: str, index: str = "index 111..222 100644", at: str = "@@ -1,2 +1,3 @@ def f"
) -> str:
    return "\n".join(
        ["diff --git a/x.py b/x.py", index, "--- a/x.py", "+++ b/x.py", at, " keep", body, ""]
    )


def test_key_ignores_blob_ids_and_line_numbers_only() -> None:
    one = ir.change_key(_diff("+new"))
    assert one == ir.change_key(
        _diff("+new", index="index 999..888 100644", at="@@ -40,2 +41,3 @@ def f")
    )
    assert one != ir.change_key(_diff("+other"))
    assert one != ir.change_key(_diff("+new", at="@@ -1,2 +1,3 @@ def g"))
    assert one != ir.change_key(_diff("+new").replace(" keep", " changed"))


def _stamp(days_ago: float) -> str:
    import time

    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(NOW - days_ago * 86400))


def _run(**kw: Any) -> dict[str, Any]:
    run = {
        "id": 9,
        "path": ir.WORKFLOW,
        "event": "pull_request",
        "head_repository": {"full_name": REPO},
        "pull_requests": [{"number": 7}],
        "created_at": _stamp(1),
        "head_sha": OLD,
    }
    run.update(kw)
    return run


def _fake(
    monkeypatch: pytest.MonkeyPatch, runs: list[dict[str, Any]], conclusion: str, old_diff: str
) -> list[str]:
    calls: list[str] = []

    def gh(*args: str) -> str:
        calls.append(args[0])
        if "/runs?" in args[0]:
            return json.dumps({"workflow_runs": runs})
        if args[0].endswith("/jobs?filter=all"):
            return json.dumps({"jobs": [{"name": "independent-review", "conclusion": conclusion}]})
        if "/compare/" in args[0]:
            return old_diff
        raise AssertionError(args)

    monkeypatch.setattr(ir, "_gh", gh)
    return calls


def _hit(
    monkeypatch: pytest.MonkeyPatch, run: dict[str, Any], conclusion: str = "success", old: str = ""
) -> str | None:
    _fake(monkeypatch, [run], conclusion, old or _diff("+new", index="index 5..6 100644"))
    got: str | None = ir.earlier_success(
        REPO, 7, "feature", BASE, HEAD, ir.change_key(_diff("+new")), now=NOW
    )
    return got


def test_same_change_after_merge_in_is_reused(monkeypatch: pytest.MonkeyPatch) -> None:
    assert _hit(monkeypatch, _run()) == "9"


@pytest.mark.parametrize(
    "run,conclusion,old",
    [
        (_run(), "failure", ""),
        (_run(), "success", _diff("+different")),
        (_run(created_at=_stamp(8)), "success", ""),
        (_run(pull_requests=[{"number": 8}]), "success", ""),
        (_run(head_repository={"full_name": "fork/r"}), "success", ""),
        (_run(path=".github/workflows/ci.yml"), "success", ""),
        (_run(event="pull_request_target"), "success", ""),
    ],
)
def test_anything_else_is_read_in_full(
    monkeypatch: pytest.MonkeyPatch, run: dict[str, Any], conclusion: str, old: str
) -> None:
    assert _hit(monkeypatch, run, conclusion, old) is None


def test_reuse_step_never_fails_and_writes_hit(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    out = tmp_path / "out"
    monkeypatch.setenv("GITHUB_OUTPUT", str(out))
    args = ["--reuse-only", "--repo", REPO, "--pr", "7", "--head", HEAD, "--base-sha", BASE]

    def boom(*_: str) -> str:
        raise RuntimeError("api down")

    monkeypatch.setattr(ir, "_gh", boom)
    assert ir.main(args) == 0 and not out.exists()

    pr = {"head": {"sha": HEAD, "ref": "feature"}, "changed_files": 1}
    monkeypatch.setattr(ir, "screened", lambda a: (_diff("+new"), pr))
    monkeypatch.setattr(ir, "earlier_success", lambda *a, **k: "9")
    assert ir.main(args) == 0
    assert out.read_text(encoding="utf-8") == "hit=true\n"


def test_a_screen_hit_is_never_reused(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setenv("GITHUB_OUTPUT", str(tmp_path / "out"))
    moved = {"head": {"sha": OLD, "ref": "feature"}, "changed_files": 1}
    monkeypatch.setattr(
        ir, "_gh", lambda *a: json.dumps(moved) if "/pulls/" in a[0] else _diff("+new")
    )
    monkeypatch.setattr(
        ir, "earlier_success", lambda *a, **k: pytest.fail("looked up after a screen hit")
    )
    assert (
        ir.main(["--reuse-only", "--repo", REPO, "--pr", "7", "--head", HEAD, "--base-sha", BASE])
        == 0
    )
    assert not (tmp_path / "out").exists()
    assert "REVIEW_FAIL" not in capsys.readouterr().out  # the review step says it, once


def test_workflow_skips_models_only_on_a_hit() -> None:
    text = (ROOT / ".github/workflows/release-gates.yml").read_text(encoding="utf-8")
    job = text.split("  independent-review:", 1)[1]
    assert "actions: read" in job
    reuse = job.index("--reuse-only")
    serve = job.index("Serve the pinned open-weight reviewers")
    review = job.index("Review the whole diff")
    assert reuse < serve < review
    assert job.count("if: steps.reuse.outputs.hit != 'true'") == 2
    # the step runs LIVE's script: one without --reuse-only (or any crash) must not fail the job
    step = job[job.index("id: reuse") : serve]
    assert '|| echo "reuse: not checked' in step and "continue-on-error" not in step
