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


def _c(body: str, at: datetime, edited: bool = False, who: str = "OWNER") -> dict[str, Any]:
    t = at.strftime("%Y-%m-%dT%H:%M:%SZ")
    up = (at + timedelta(minutes=1)).strftime("%Y-%m-%dT%H:%M:%SZ") if edited else t
    return {"body": body, "created_at": t, "updated_at": up, "author_association": who}


TRUSTED = ("OWNER", "MEMBER", "COLLABORATOR")


def test_the_window_is_72h_from_the_anchored_notice_for_this_head() -> None:
    sent = rp.notices([_c(rp.notice_comment(H1, "armed 1, delivered 1"), T0)], TRUSTED)
    assert sent == [(T0, H1)]
    assert rp.window([], H1, T0)[0] == "none"
    assert rp.window(sent, H2, T0)[0] == "none"  # a new push: a new notice
    assert rp.window(sent, H1, T0 + timedelta(hours=71))[0] == "open"
    assert rp.window(sent, H1, T0 + timedelta(hours=72, minutes=1))[0] == "elapsed"
    assert rp.window(sent, H1, T0 - timedelta(hours=1))[0] == "none"  # dated in the future


def test_only_an_unedited_trusted_notice_comment_counts() -> None:
    body = rp.notice_comment(H1, "delivered 1")
    assert rp.notices([_c(body, T0, edited=True)], TRUSTED) == []
    assert rp.notices([_c(body, T0, who="NONE")], TRUSTED) == []
    assert rp.notices([_c("x " + body, T0)], TRUSTED) == []
    assert rp.notices([_c(f"ROOT NOTICE {H1} delivered: ", T0)], TRUSTED) == []


def test_anything_red_held_or_off_after_the_notice_voids_it() -> None:
    sent = [(T0, H1)]
    late = T0 + timedelta(hours=80)
    later = (T0 + timedelta(hours=10)).isoformat()
    hold = [{"verdict": "HOLD", "at": later}]
    assert rp.window(sent, H1, late, rp.voids(hold, {}, [], "OFF", TRUSTED))[0] == "none"
    red = {"replay-shadow": [{"status": "completed", "conclusion": "failure",
                              "completed_at": later}]}  # fmt: skip
    assert rp.window(sent, H1, late, rp.voids([], red, [], "OFF", TRUSTED))[0] == "none"
    off = [_c("OFF", T0 + timedelta(hours=5))]
    assert rp.window(sent, H1, late, rp.voids([], {}, off, "OFF", TRUSTED))[0] == "none"
    edit = [_c("anything", T0 + timedelta(hours=5), edited=True)]
    assert rp.window(sent, H1, late, rp.voids([], {}, edit, "OFF", TRUSTED))[0] == "none"
    # the same events BEFORE the notice void nothing (a re-run failure that led to it)
    early = (T0 - timedelta(hours=1)).isoformat()
    red_before = {"replay-shadow": [{"status": "completed", "conclusion": "failure",
                                     "completed_at": early}]}  # fmt: skip
    v = rp.voids([{"verdict": "CLEAR", "at": later}], red_before, [], "OFF", TRUSTED)
    assert rp.window(sent, H1, late, v)[0] == "elapsed"
    # a new notice after the void starts a new window
    assert rp.window([*sent, (T0 + timedelta(hours=11), H1)], H1, late,
                     rp.voids(hold, {}, [], "OFF", TRUSTED))[0] == "open"  # fmt: skip
    bad_time = [{"verdict": "HOLD", "at": "garbage"}]
    assert rp.window(sent, H1, late, rp.voids(bad_time, {}, [], "OFF", TRUSTED))[0] == "none"


def test_the_notice_names_the_pr_the_head_and_the_files_in_plain_words() -> None:
    title, body = rp.notice(41, H1, ["b.py", "a.py"])
    assert "#41" in title and "CHANGES HOW MERGES ARE APPROVED" in title and "72 h" in title
    assert H1 in body and "a.py, b.py" in body and "AUDIT HOLD" in body


# ------------------------------------------------------------------- end to end (sandbox)


@pytest.fixture
def sb(tmp_path: Path) -> Any:
    box = sb_mod.Sandbox(tmp_path, files=(GATE,))
    box.level2 = True  # the sitting's end state: GitHub enforces the authority's status
    box.repin_marker.write_text("abc repin.py\n")
    return box


def _cycle(sb: Any, hours: float) -> None:
    sb.clock.advance(hours=hours)
    sb.authority()
    sb.gate()


def test_a_root_pr_merges_72h_after_its_anchored_notice_with_no_owner_step(sb: Any) -> None:
    sb.audit_clear()
    v, why = sb.authority()
    assert v == "WAIT" and "no delivered ROOT notice" in why[0]  # no attestation before the notice
    sb.gate()
    assert len(sb.root_notices) == 1 and sb.gh.merges() == []
    assert "#41" in sb.root_notices[0][0] and GATE in sb.root_notices[0][1]
    anchored = [c for c in sb.gh.comments if str(c["body"]).startswith("ROOT NOTICE")]
    assert len(anchored) == 1 and H1 in anchored[0]["body"]
    _cycle(sb, 24.1)
    assert sb.gh.merges() == []  # 24 h is not enough for ROOT
    _cycle(sb, 48)
    v, why = sb.authority()
    assert v == "CLEAR" and why[0].startswith("ROOT path")
    sb.gate()
    m = sb.gh.merges()
    assert len(m) == 1 and m[0]["sha"] == H1 and "ROOT path" in m[0]["commit_title"]
    assert len(sb.root_notices) == 1 and sb.notices == []  # never the 24 h registry notice
    inflight = json.loads((sb.registry.parent / "ROOT_INFLIGHT.json").read_text())
    assert inflight["pr"] == 41 and inflight["head"] == H1


def test_the_root_path_is_off_until_level2_and_the_repin_service(sb: Any) -> None:
    sb.audit_clear()
    for off in ("level2", "marker"):
        if off == "level2":
            sb.level2 = False
        else:
            sb.level2 = True
            sb.repin_marker.unlink()
        sb.gate()
        _cycle(sb, 80)
        assert sb.gh.merges() == [] and sb.root_notices == [], off


def test_the_level2_status_for_root_is_success_only_on_the_full_clear(sb: Any) -> None:
    a = sb.auth
    assert a.status_for({"cls": "ROOT"}, "WAIT", ["x"], since=None, veto_h=24)[0] != "success"
    assert a.status_for({"cls": "ROOT"}, "CLEAR", ["x"], since=None, veto_h=24)[0] == "success"


def _past_window(sb: Any) -> None:
    sb.gate()
    for _ in range(3):
        _cycle(sb, 30)


@pytest.mark.parametrize("comment,row", [(True, False), (False, True), (False, False)])
def test_one_auditor_record_alone_merges_nothing(sb: Any, comment: bool, row: bool) -> None:
    sb.audit_clear(comment=comment, row=row)
    _past_window(sb)
    assert sb.gh.merges() == [] and sb.root_notices == []


def test_an_undelivered_notice_starts_no_window(sb: Any) -> None:
    sb.audit_clear()
    sb.root_notify_out = (0, "armed 1, delivered 0")
    _past_window(sb)
    assert sb.gh.merges() == [] and len(sb.root_notices) == 4
    assert not any(str(c["body"]).startswith("ROOT NOTICE") for c in sb.gh.comments)


def test_a_hold_posted_in_the_window_stops_it_and_a_new_clear_restarts_it(sb: Any) -> None:
    sb.audit_clear()
    sb.gate()
    sb.clock.advance(hours=10)
    at = sb.clock.t.strftime("%Y-%m-%dT%H:%M:%SZ")
    sb.gh.comments.append({"body": f"AUDIT HOLD {H1}", "created_at": at, "updated_at": at,
                           "author_association": "OWNER",
                           "performed_via_github_app": None})  # fmt: skip
    _cycle(sb, 70)
    assert sb.gh.merges() == []
    sb.audit_clear()  # a new CLEAR: the old notice is void, a new one is sent
    sb.gate()
    assert len(sb.root_notices) == 2
    _cycle(sb, 24)
    assert sb.gh.merges() == []


def test_an_earlier_root_merge_in_flight_blocks_the_next(sb: Any) -> None:
    (sb.registry.parent / "ROOT_INFLIGHT.json").write_text(json.dumps({"pr": 7, "head": H2}))
    sb.audit_clear()
    _past_window(sb)
    assert sb.gh.merges() == [] and sb.root_notices == []


def test_the_inflight_mark_is_written_before_the_merge_or_nothing_merges(sb: Any) -> None:
    sb.audit_clear()
    sb.gate()
    sb.clock.advance(hours=73)
    assert sb.authority()[0] == "CLEAR"
    (sb.registry.parent / "ROOT_INFLIGHT.json").mkdir()  # cannot be written as a file
    sb.gate()
    assert sb.gh.merges() == []


def test_a_root_row_in_the_unsigned_registry_clears_nothing(tmp_path: Path) -> None:
    box = sb_mod.Sandbox(tmp_path, files=(".github/workflows/ci.yml",))
    row = {"pr": 41, "sha": H1, "verdict": "CLEAR", "at": "2026-11-01T00:00:00Z", "root": True}
    box.registry.write_text(json.dumps(row) + "\n")
    import os

    os.environ.pop(box.ag.AUTHORITY_PUBKEY_ENV, None)
    with box.wired():
        os.environ.pop(box.ag.AUTHORITY_PUBKEY_ENV, None)
        box.ag.run("o/r", 41, box.ag.LIVE, 0.0, box=True)
    assert box.gh.merges() == []  # the 24 h window still applies: a notice, no merge yet


def test_a_failed_review_is_rerun_automatically_before_any_attestation(sb: Any) -> None:
    sb.gh.conclusion["independent-review"] = "failure"
    sb.audit_clear()
    assert sb.authority()[0] == "WAIT"
    sb.gate()
    reruns = [p for (_m, p, _d) in sb.gh.writes if p.endswith("/rerun")]
    assert len(reruns) == 1 and sb.gh.merges() == [] and sb.root_notices == []


def test_no_rerun_while_a_hold_stands_or_merges_are_off(sb: Any) -> None:
    sb.gh.conclusion["independent-review"] = "failure"
    sb.audit_clear()
    at = sb.clock.t.strftime("%Y-%m-%dT%H:%M:%SZ")
    sb.gh.comments.append({"body": f"AUDIT HOLD {H1}", "created_at": at, "updated_at": at,
                           "author_association": "OWNER",
                           "performed_via_github_app": None})  # fmt: skip
    sb.gate()
    assert not [p for (_m, p, _d) in sb.gh.writes if p.endswith("/rerun")]


def test_a_failing_trusted_eval_blocks(sb: Any) -> None:
    sb.gh.trusted_eval = "failure"
    sb.audit_clear()
    assert sb.authority()[0] == "FAIL"
    _past_window(sb)
    assert sb.gh.merges() == []


@pytest.mark.parametrize("form", [
    "globals()['REGISTRY_HOLD_H'] = 1.0",
    "setattr(sys.modules[__name__], 'REGISTRY_HOLD_H', 1.0)",
    "vars()['REGISTRY_HOLD_H'] = 1.0",
    "sys.modules[__name__].__dict__['REGISTRY_HOLD_H'] = 1.0",
    "exec('REGISTRY_HOLD_H = 1.0')",
])  # fmt: skip
def test_an_indirect_rebinding_of_a_sealed_value_is_sealed(form: str) -> None:
    base = "REGISTRY_HOLD_H = 24.0\n"
    assert rp.sealed_touch([GATE], lambda n: base, lambda n: base + form + "\n")


def test_sealed_values_match_paths_case_insensitively() -> None:
    base = "REGISTRY_HOLD_H = 24.0\n"
    got = rp.sealed_touch([GATE.upper()], lambda n: base, lambda n: "REGISTRY_HOLD_H = 1.0\n")
    assert got


@pytest.mark.parametrize("text", ["see line 42 of gate.py", "L42 is wrong", "lines 3-9"])
def test_other_line_citations_rule_out_the_rerun(text: str) -> None:
    assert rp.failure_flags([text])


def test_the_whole_authority_and_trusted_eval_are_sealed() -> None:
    none = lambda n: None  # noqa: E731
    for f in ("ops/release/authority/policy.py", "ops/release/authority/attestation.py",
              "ops/release/authority/pin_root.py", "ops/release/authority/authority.py",
              ".github/workflows/trusted-eval.yml"):  # fmt: skip
        assert rp.sealed_touch([f], none, none), f
    assert rp.sealed_touch([".github/scripts/audit_gate.py"], none, none) == []
