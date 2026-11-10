"""THE ROOT PATH (root_path.py, SEALED): after the final sitting a ROOT PR merges with no owner
step only with the Auditor's comment AND registry row, a class-ROOT attestation, every ROOT job
green (one automatic re-run of a failure that names nothing), the base's trusted-eval, and 72 h
since a DELIVERED notice for that exact head; one at a time; never the sealed core."""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest

ROOT = Path(__file__).resolve().parents[2]
import importlib.util  # noqa: E402
import sys  # noqa: E402


def _load(name: str, path: Path) -> Any:
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


rp = _load("root_path_t", ROOT / "ops/release/authority/root_path.py")
sb_mod = _load("authority_sandbox_rp", ROOT / "ops/release/authority/sandbox.py")
H1, H2 = sb_mod.H1, sb_mod.H2
T0 = datetime(2026, 11, 11, tzinfo=UTC)
GATE = ".github/scripts/audit_gate.py"


# ------------------------------------------------------------------- the sealed core


def test_sealed_core_files_and_sealed_values() -> None:
    none = lambda n: None  # noqa: E731
    assert rp.sealed_touch(["ops/release/authority/root_path.py"], none, none)
    assert rp.sealed_touch(["OPS/release/authority/ROOT_POLICY.json"], none, none)
    assert rp.sealed_touch(["scripts/x.py"], none, none) == []
    base = 'REGISTRY_HOLD_H = 24.0\nREGISTRY_NOTIFY_ENV = "QUANT_REGISTRY_NOTIFY"\n'
    same = lambda n: base  # noqa: E731
    assert rp.sealed_touch([GATE], same, same) == []
    shorter = lambda n: base.replace("24.0", "1.0")  # noqa: E731
    assert "REGISTRY_HOLD_H" in rp.sealed_touch([GATE], same, shorter)[0]
    # an untouched file is never read
    assert rp.sealed_touch(["scripts/x.py"], same, shorter) == []


@pytest.mark.parametrize("head", [
    'REGISTRY_HOLD_H = 24.0\nREGISTRY_HOLD_H = 1.0\n',          # re-bound
    'REGISTRY_HOLD_H = 24.0\ndef f():\n    global REGISTRY_HOLD_H\n',
    'REGISTRY_HOLD_H = 24.0\nREGISTRY_HOLD_H += 1\n',
    'REGISTRY_HOLD_H = float("24")\n',                           # not a literal
    'REGISTRY_HOLD_H = 24.0\nfor REGISTRY_HOLD_H in (1,): pass\n',
    'REGISTRY_HOLD_H = 24.0\nfrom x import *\n',
    'REGISTRY_HOLD_H = (\n',                                    # unparseable
    '',                                                         # removed
])  # fmt: skip
def test_a_sealed_value_that_cannot_be_pinned_down_is_sealed(head: str) -> None:
    base = "REGISTRY_HOLD_H = 24.0\n"
    assert rp.sealed_touch([GATE], lambda n: base, lambda n: head)


def test_adding_an_absent_sealed_value_with_its_pinned_value_is_not_a_change() -> None:
    p = "ops/release/auditor_sync.py"
    good = 'REF = "refs/heads/audit-registry"\n'
    assert rp.sealed_touch([p], lambda n: None, lambda n: good) == []
    bad = 'REF = "refs/heads/elsewhere"\n'
    assert rp.sealed_touch([p], lambda n: None, lambda n: bad)


def test_the_sealed_values_are_the_live_values() -> None:
    for (path, name), pinned in rp.SEALED_VALUES.items():
        f = ROOT / path
        if f.exists():
            got = rp.py_constant(f.read_text("utf-8"), name)
            assert got in (None, pinned), (path, name, got)


def test_only_a_root_file_only_change_is_eligible() -> None:
    assert rp.eligible(["root file .github/scripts/audit_gate.py"])[0]
    assert not rp.eligible([])[0]
    assert not rp.eligible(["root file ops/release/authority/root_path.py"])[0]
    assert not rp.eligible(["root file a.py", "envelope: MAX_RISK_FRAC lowered"])[0]
    assert not rp.eligible(["root file a.py", "ops/release/protected_paths.txt lost 1 entry"])[0]
    assert not rp.eligible(["root file a.py", "sealed value x:Y changes"])[0]


# ------------------------------------------------------------------- the jobs


def _ok(**over: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    good = {"status": "completed", "conclusion": "success", "flags": []}
    return {n: over.get(n.replace("-", "_"), [good]) for n in rp.ROOT_JOBS}


FAIL = {"status": "completed", "conclusion": "failure", "flags": []}


def test_jobs_pass_pending_and_missing() -> None:
    assert rp.jobs(_ok())[0] == "pass"
    assert rp.jobs(_ok(quality=[{"status": "in_progress"}]))[0] == "pending"
    a = _ok()
    del a["coverage-floor"]
    assert rp.jobs(a)[0] == "pending"


def test_one_rerun_of_a_review_or_replay_failure_that_names_nothing() -> None:
    assert rp.jobs(_ok(independent_review=[FAIL]))[:3:2] == ("rerun", "independent-review")
    assert rp.jobs(_ok(replay_shadow=[FAIL]))[2] == "replay-shadow"
    rerun = {"status": "queued"}
    assert rp.jobs(_ok(replay_shadow=[FAIL, rerun]))[0] == "pending"
    assert rp.jobs(_ok(replay_shadow=[FAIL, FAIL]))[0] == "fail"  # the second failure blocks
    assert rp.jobs(_ok(replay_shadow=[FAIL, {**FAIL, "conclusion": "success"}]))[0] == "pass"


@pytest.mark.parametrize("bad", [
    {**FAIL, "flags": ["its failure cites a line"]},
    {**FAIL, "flags": None},                          # annotations unreadable
])  # fmt: skip
def test_no_rerun_when_the_failure_names_something_or_cannot_be_read(bad: Any) -> None:
    assert rp.jobs(_ok(independent_review=[bad]))[0] == "fail"


def test_no_rerun_for_any_other_job() -> None:
    assert rp.jobs(_ok(quality=[FAIL]))[0] == "fail"
    assert rp.jobs(_ok(risk_invariants=[FAIL]))[0] == "fail"


def test_an_unavailable_reviewer_is_queued_and_does_not_use_up_the_rerun() -> None:
    un = {**FAIL, "unavailable": True}
    assert rp.jobs(_ok(independent_review=[un]))[0] == "pending"
    assert rp.jobs(_ok(independent_review=[un, FAIL]))[0] == "rerun"


@pytest.mark.parametrize("text,flag", [
    ("REVIEW_FAIL ops/x.py:12 is wrong", "cites a line"),
    ("REVIEW_FAIL the reviewer flagged a change to control machinery", "control"),
    ("REVIEW_FAIL the reviewer flagged a risk increase", "risk"),
    ("REVIEW_FAIL qwen voted FAIL (its findings are in the job log)", "may cite a line"),
])  # fmt: skip
def test_failure_flags(text: str, flag: str) -> None:
    assert any(flag in f for f in rp.failure_flags([text]))
    assert rp.failure_flags(["Process completed with exit code 1."]) == []


# ------------------------------------------------------------------- records and window


def test_both_auditor_records_must_name_the_exact_head() -> None:
    assert rp.registry_agrees([{"pr": 41, "sha": H1, "verdict": "CLEAR"}], 41, H1)[0]
    assert not rp.registry_agrees([{"pr": 41, "sha": H1, "verdict": "CLEAR"}], 41, H2)[0]
    rows = [{"pr": 41, "sha": H1, "verdict": "CLEAR"}, {"pr": 41, "sha": H1, "verdict": "HOLD"}]
    assert not rp.registry_agrees(rows, 41, H1)[0]
    assert not rp.registry_agrees([], 41, H1)[0]
    assert rp.comment_clear([{"verdict": "CLEAR", "sha": H1}], H1)[0]
    assert not rp.comment_clear([{"verdict": "CLEAR", "sha": H1}], H2)[0]
    assert not rp.comment_clear([], H1)[0]


def test_a_receipt_needs_exit_0_and_a_delivery() -> None:
    assert rp.receipt(0, "armed 2, delivered 1")
    assert rp.receipt(0, "armed 2, delivered 0") is None
    assert rp.receipt(1, "armed 2, delivered 1") is None
    assert rp.receipt(0, "") is None


def test_the_window_is_72h_from_a_delivered_notice_for_this_head() -> None:
    rec = {"head": H1, "at": T0.isoformat(), "receipt": "delivered 1"}
    assert rp.window(None, H1, T0)[0] == "none"
    assert rp.window(rec, H2, T0)[0] == "none"  # a new push: a new notice
    assert rp.window({**rec, "receipt": ""}, H1, T0)[0] == "none"
    assert rp.window(rec, H1, T0 + timedelta(hours=71))[0] == "open"
    assert rp.window(rec, H1, T0 + timedelta(hours=72, minutes=1))[0] == "elapsed"
    assert rp.window({**rec, "at": "2026-11-11T00:00:00"}, H1, T0)[0] == "none"  # no zone
    assert rp.window(rec, H1, T0 - timedelta(hours=1))[0] == "none"  # dated in the future


def test_the_notice_names_the_pr_the_head_and_the_files_in_plain_words() -> None:
    title, body = rp.notice(41, H1, ["b.py", "a.py"])
    assert "#41" in title and "CHANGES HOW MERGES ARE APPROVED" in title and "72 h" in title
    assert H1 in body and "a.py, b.py" in body and "AUDIT HOLD" in body


# ------------------------------------------------------------------- end to end (sandbox)


@pytest.fixture
def sb(tmp_path: Path) -> Any:
    return sb_mod.Sandbox(tmp_path, files=(GATE,))


def test_a_root_pr_merges_after_72h_from_its_delivered_notice_with_no_owner_step(sb: Any) -> None:
    v, why = sb.authority()
    assert v == "CLEAR" and why[0].startswith("ROOT path")
    sb.audit_clear()
    sb.gate()
    assert len(sb.root_notices) == 1 and sb.gh.merges() == []
    assert "#41" in sb.root_notices[0][0] and GATE in sb.root_notices[0][1]
    sb.clock.advance(hours=24, minutes=1)
    sb.authority()  # the attestation is renewed inside its 48 h life, as the service does
    sb.gate()
    assert sb.gh.merges() == []  # 24 h is not enough for ROOT
    sb.clock.advance(hours=48)
    sb.authority()
    sb.gate()
    m = sb.gh.merges()
    assert len(m) == 1 and m[0]["sha"] == H1 and "ROOT path" in m[0]["commit_title"]
    assert len(sb.root_notices) == 1 and sb.notices == []  # never the 24 h registry notice
    inflight = json.loads((sb.registry.parent / "ROOT_INFLIGHT.json").read_text())
    assert inflight["pr"] == 41 and inflight["head"] == H1


def _past_window(sb: Any) -> None:
    sb.gate()
    for _ in range(2):
        sb.clock.advance(hours=37)
        sb.authority()
        sb.gate()


@pytest.mark.parametrize("comment,row", [(True, False), (False, True), (False, False)])
def test_one_auditor_record_alone_merges_nothing(sb: Any, comment: bool, row: bool) -> None:
    sb.authority()
    sb.audit_clear(comment=comment, row=row)
    _past_window(sb)
    assert sb.gh.merges() == [] and sb.root_notices == []


def test_an_undelivered_notice_starts_no_window(sb: Any) -> None:
    sb.authority()
    sb.audit_clear()
    sb.root_notify_out = (0, "armed 1, delivered 0")
    _past_window(sb)
    assert sb.gh.merges() == [] and len(sb.root_notices) == 3


def test_a_hold_posted_in_the_window_stops_it(sb: Any) -> None:
    sb.authority()
    sb.audit_clear()
    sb.gate()
    sb.gh.comments.append({"body": f"AUDIT HOLD {H1}", "created_at": "2026-11-05T00:00:00Z",
                           "updated_at": "2026-11-05T00:00:00Z", "author_association": "OWNER",
                           "performed_via_github_app": None})  # fmt: skip
    _past_window(sb)
    assert sb.gh.merges() == []


def test_an_earlier_root_merge_in_flight_blocks_the_next(sb: Any) -> None:
    (sb.registry.parent / "ROOT_INFLIGHT.json").write_text(json.dumps({"pr": 7, "head": H2}))
    sb.authority()
    sb.audit_clear()
    _past_window(sb)
    assert sb.gh.merges() == [] and sb.root_notices == []


def test_a_failed_review_is_rerun_automatically_before_any_attestation(sb: Any) -> None:
    sb.gh.conclusion["independent-review"] = "failure"
    assert sb.authority()[0] == "WAIT"
    sb.audit_clear()
    sb.gate()
    reruns = [p for (_m, p, _d) in sb.gh.writes if p.endswith("/rerun")]
    assert len(reruns) == 1 and sb.gh.merges() == []


def test_a_failing_trusted_eval_blocks(sb: Any) -> None:
    sb.gh.trusted_eval = "failure"
    assert sb.authority()[0] == "FAIL"
    sb.audit_clear()
    _past_window(sb)
    assert sb.gh.merges() == []
