"""The Auditor adjudicates the robot reviewer (audit_gate.ADJUDICABLE; zuck 2026-11-10 "Auditor
sign-off is enough"): on the registry / authority path only, a failed or unavailable
independent-review stops blocking a head the Auditor CLEARed after that review finished, when
the box's copy of the Auditor's registry agrees and no changed path is protected. Every other
way through fails closed. The end-to-end cases run the REAL authority and the REAL box gate
against the sandbox's fake GitHub."""

from __future__ import annotations

import importlib.util
import json
import os
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest

pytest.importorskip("cryptography")

ROOT = Path(__file__).resolve().parents[2]
_spec = importlib.util.spec_from_file_location(
    "authority_sandbox", ROOT / "ops/release/authority/sandbox.py"
)
assert _spec is not None and _spec.loader is not None
sb_mod = importlib.util.module_from_spec(_spec)
sys.modules["authority_sandbox"] = sb_mod
_spec.loader.exec_module(sb_mod)
H1, H2 = sb_mod.H1, sb_mod.H2
CODE = "desks/mt5/research/some_family.py"
REVIEW_DONE = "2026-11-04T10:00:00Z"
AFTER, BEFORE = "2026-11-04T11:00:00Z", "2026-11-04T09:00:00Z"


def _comment(body: str, at: str, assoc: str = "OWNER") -> dict[str, Any]:
    return {"body": body, "created_at": at, "updated_at": at, "author_association": assoc,
            "user": {"login": "kingdemond434-cpu"}}  # fmt: skip


def _run(name: str, concl: str | None, *, done: str | None = REVIEW_DONE,
         started: str = "2026-11-04T09:30:00Z", rid: int = 7) -> dict[str, Any]:  # fmt: skip
    return {"id": rid, "name": name, "status": "completed" if concl else "in_progress",
            "conclusion": concl, "started_at": started, "completed_at": done,
            "app": {"slug": "github-actions"}}  # fmt: skip


@pytest.fixture
def ag() -> Any:
    return sb_mod._load("audit_gate", ROOT / ".github" / "scripts" / "audit_gate.py")


def _yes(_r: Any) -> bool:
    return True


# --------------------------------------------------------------------- the comment side


def test_only_a_newer_exact_head_clear_adjudicates_a_failed_review(ag: Any) -> None:
    runs = [_run("independent-review", "failure")]
    clear = ag.verdicts([_comment(f"AUDIT CLEAR {H1}", AFTER)])
    ok, why = ag.review_adjudicated(clear, H1, runs, _yes, [CODE])
    assert ok and "adjudicates independent-review" in why
    # every way it must NOT hold
    assert not ag.review_adjudicated([], H1, runs, _yes, [CODE])[0]
    assert not ag.review_adjudicated(clear, H2, runs, _yes, [CODE])[0]  # no carry-over
    early = ag.verdicts([_comment(f"AUDIT CLEAR {H1}", BEFORE)])
    ok, why = ag.review_adjudicated(early, H1, runs, _yes, [CODE])
    assert not ok and "has not seen its findings" in why
    same = ag.verdicts([_comment(f"AUDIT CLEAR {H1}", REVIEW_DONE)])
    assert not ag.review_adjudicated(same, H1, runs, _yes, [CODE])[0]  # not newer
    held = ag.verdicts([_comment(f"AUDIT CLEAR {H1}", AFTER),
                        _comment(f"AUDIT HOLD {H1}", "2026-11-04T11:30:00Z")])  # fmt: skip
    assert not ag.review_adjudicated(held, H1, runs, _yes, [CODE])[0]
    stranger = ag.verdicts([_comment(f"AUDIT CLEAR {H1}", AFTER, assoc="NONE")])
    assert not ag.review_adjudicated(stranger, H1, runs, _yes, [CODE])[0]
    edited = _comment(f"AUDIT CLEAR {H1}", AFTER)
    edited["updated_at"] = "2026-11-04T11:05:00Z"
    assert not ag.review_adjudicated(ag.verdicts([edited]), H1, runs, _yes, [CODE])[0]


def test_a_review_that_passed_or_has_not_finished_is_not_adjudicated(ag: Any) -> None:
    clear = ag.verdicts([_comment(f"AUDIT CLEAR {H1}", AFTER)])
    assert not ag.review_adjudicated(clear, H1, [], _yes, [CODE])[0]
    passed = [_run("independent-review", "success")]
    assert not ag.review_adjudicated(clear, H1, passed, _yes, [CODE])[0]
    running = [_run("independent-review", None, done=None)]
    assert not ag.review_adjudicated(clear, H1, running, _yes, [CODE])[0]
    # a re-run started after the CLEAR is the newest run: the old CLEAR has not seen it
    rerun = [_run("independent-review", "failure"),
             _run("independent-review", "failure", started="2026-11-04T11:30:00Z",
                  done="2026-11-04T12:30:00Z", rid=8)]  # fmt: skip
    assert not ag.review_adjudicated(clear, H1, rerun, _yes, [CODE])[0]
    # a run the provenance check rejects is not the reviewer
    assert not ag.review_adjudicated(clear, H1, [_run("independent-review", "failure")],
                                     lambda r: False, [CODE])[0]  # fmt: skip
    timeless = [_run("independent-review", "failure", done=None)]
    timeless[0]["status"] = "completed"
    assert not ag.review_adjudicated(clear, H1, timeless, _yes, [CODE])[0]


@pytest.mark.parametrize("path", [
    ".github/scripts/audit_gate.py",
    ".github/workflows/ci.yml",
    "ops/release/authority/policy.py",
    "ops/release/ceilings.json",
    "data/secrets/x.json",
])  # fmt: skip
def test_a_protected_path_is_never_adjudicated(ag: Any, path: str) -> None:
    runs = [_run("independent-review", "failure")]
    clear = ag.verdicts([_comment(f"AUDIT CLEAR {H1}", AFTER)])
    ok, why = ag.review_adjudicated(clear, H1, runs, _yes, [CODE, path])
    assert not ok and "protected path" in why
    assert ag.never_adjudicated([]) is not None  # nothing listed is never


def test_every_formerly_protected_and_listed_pattern_is_never_adjudicated(ag: Any) -> None:
    extra = ag.protected_patterns()
    assert extra, "ops/release/protected_paths.txt must be readable here"
    for pat in (*ag.PROTECTED, *ag.FORMERLY_PROTECTED, *extra):
        name = pat.replace("*", "x")
        assert ag.never_adjudicated([name]) is not None, pat


def test_an_unreadable_protected_list_adjudicates_nothing(ag: Any, tmp_path: Path) -> None:
    ag.PROTECTED_FILE = tmp_path / "missing.txt"
    assert "unreadable" in str(ag.never_adjudicated([CODE]))


def test_only_the_reviewer_is_adjudicable(ag: Any) -> None:
    assert ag.ADJUDICABLE == ("independent-review",)
    assert not set(ag.ADJUDICABLE) & set(ag.GATING_JOBS)
    assert "replay-shadow" not in ag.ADJUDICABLE and "risk-invariants" not in ag.ADJUDICABLE


# --------------------------------------------------------------------- the second record

_NOW = datetime(2026, 11, 4, 12, 0, tzinfo=UTC)


def _rows(tmp: Path, rows: list[dict[str, Any]], age_h: float = 0.5) -> str:
    f = tmp / "auditor_rows.jsonl"
    f.write_text("".join(json.dumps(r) + "\n" for r in rows), encoding="utf-8")
    t = (_NOW - timedelta(hours=age_h)).timestamp()
    os.utime(f, (t, t))
    return str(f)


def _row(**kw: Any) -> dict[str, Any]:
    return {"pr": 41, "sha": H1, "verdict": "CLEAR", "at": "2026-11-04T11:00:00+00:00", **kw}


def test_the_auditor_registry_must_be_configured_fresh_and_agree(
    ag: Any, tmp_path: Path, monkeypatch: Any
) -> None:
    monkeypatch.delenv(ag.AUDITOR_ROWS_ENV, raising=False)
    assert not ag.auditor_row_agrees(41, H1, now=_NOW)[0]  # unset: never
    assert not ag.auditor_row_agrees(41, H1, str(tmp_path / "none"), _NOW)[0]
    ok, why = ag.auditor_row_agrees(41, H1, _rows(tmp_path, [_row()]), _NOW)
    assert ok and "agrees" in why
    ok, why = ag.auditor_row_agrees(41, H1, _rows(tmp_path, [_row()], age_h=6.5), _NOW)
    assert not ok and "stale" in why
    assert not ag.auditor_row_agrees(41, H1, _rows(tmp_path, [_row()], age_h=-1.0), _NOW)[0]
    assert not ag.auditor_row_agrees(41, H1, _rows(tmp_path, [_row(pr=40)]), _NOW)[0]
    assert not ag.auditor_row_agrees(41, H1, _rows(tmp_path, [_row(sha=H2)]), _NOW)[0]
    held = [_row(), _row(verdict="HOLD")]
    assert not ag.auditor_row_agrees(41, H1, _rows(tmp_path, held), _NOW)[0]
    f = tmp_path / "auditor_rows.jsonl"
    f.write_text(json.dumps(_row()) + "\nnot json\n", encoding="utf-8")
    t = _NOW.timestamp()
    os.utime(f, (t, t))
    assert not ag.auditor_row_agrees(41, H1, str(f), _NOW)[0]  # one bad line: no rows


# --------------------------------------------------------------------- the decision


def _decide(**facts: Any) -> tuple[str, list[str]]:
    pol = sb_mod._load("p_adj", ROOT / "ops/release/authority/policy.py")
    base = {"open": True, "same_repo": True, "base_ok": True, "cls": "AUTO", "patch_id": "p",
            "checks": ("fail", "failed: independent-review (failure)"), "fresh": True}  # fmt: skip
    return pol.decide({**base, **facts})  # type: ignore[no-any-return]


def _adj(state: str = "pass", jobs: tuple[str, ...] = ("independent-review",)) -> dict[str, Any]:
    return {"jobs": list(jobs), "why": "the Auditor's CLEAR adjudicates", "checks": (state, "x")}


def test_decide_clears_only_when_every_other_job_passed() -> None:
    v, why = _decide(adjudication=_adj())
    assert v == "CLEAR" and "adjudicates" in why[0]
    assert _decide()[0] == "FAIL"
    assert _decide(adjudication=_adj("fail"))[0] == "FAIL"  # e.g. replay-shadow also red
    assert _decide(adjudication=_adj("pending"))[0] == "WAIT"
    assert _decide(adjudication=_adj(jobs=()))[0] == "FAIL"  # the second record did not agree
    assert _decide(adjudication=_adj(jobs=()), review_queued=True)[0] == "WAIT"
    assert _decide(adjudication=_adj(), review_queued=True)[0] == "CLEAR"  # unavailable review
    assert _decide(adjudication=_adj(), fresh=False, fresh_why="behind")[0] == "WAIT"
    assert _decide(adjudication=_adj(), hold="AUDIT HOLD abc")[0] == "HOLD"
    assert _decide(adjudication=_adj(), deactivated=True)[0] == "WAIT"
    assert _decide(adjudication=_adj(), cls="CONTROLLER")[0] == "FAIL"  # never a check change
    assert _decide(adjudication=_adj(), cls="ROOT", cls_reasons=["x"])[0] == "HOLD"


# --------------------------------------------------------------------- end to end


class _Case:
    """An AUTO-tier code change whose reviewer failed at REVIEW_DONE."""

    def __init__(self, tmp: Path, monkeypatch: Any, files: tuple[str, ...] = (CODE,)) -> None:
        self.sb = sb = sb_mod.Sandbox(tmp, files=files)
        sb.gh.conclusion["independent-review"] = "failure"
        # as on LIVE since 2026-10-29: zuck typed both switches
        sb.gh.board.append({**sb.gh.board[0], "body": sb.ag.ACTIVATE_AUTO})
        plain = sb.gh.runs

        def runs() -> list[dict[str, Any]]:
            return [{**r, "completed_at": REVIEW_DONE} for r in plain()]

        sb.gh.runs = runs
        self.rows = tmp / "auditor_rows.jsonl"
        monkeypatch.setenv(sb.ag.AUDITOR_ROWS_ENV, str(self.rows))

    def comment(self, verdict: str = "CLEAR", at: str = AFTER, sha: str = H1) -> None:
        self.sb.gh.comments.append(_comment(f"AUDIT {verdict} {sha}", at))

    def sync(self, *rows: dict[str, Any]) -> None:
        """The box's copy of the Auditor's registry, written now by the sandbox clock."""
        if rows or not self.rows.exists():
            self.rows.write_text("".join(json.dumps(r) + "\n" for r in rows), encoding="utf-8")
        t = self.sb.clock.t.timestamp()
        os.utime(self.rows, (t, t))

    def window(self) -> None:
        self.sb.gate()  # the veto notice
        self.sb.clock.advance(hours=24, minutes=1)

    def merged(self) -> bool:
        return bool(self.sb.gh.merges())


@pytest.fixture
def case(tmp_path: Path, monkeypatch: Any) -> _Case:
    return _Case(tmp_path, monkeypatch)


def test_a_failed_review_alone_still_blocks(case: _Case) -> None:
    assert case.sb.authority()[0] == "FAIL"
    case.window()
    case.sb.gate()
    assert not case.merged() and case.sb.notices == []


def test_the_auditors_clear_and_registry_merge_it_after_the_window(case: _Case) -> None:
    case.comment()
    case.sync(_row())
    v, why = case.sb.authority()
    assert v == "CLEAR" and "adjudicates independent-review" in why[0]
    case.sb.gate()
    assert len(case.sb.notices) == 1 and not case.merged()  # the notice, never an instant merge
    case.sb.clock.advance(hours=23, minutes=59)
    case.sync()
    case.sb.gate()
    assert not case.merged()  # the window is not shortened
    case.sb.clock.advance(minutes=2)
    case.sync()
    case.sb.gate()
    (m,) = case.sb.gh.merges()
    assert m["sha"] == H1 and "registry CLEAR" in m["commit_title"]


def test_a_comment_without_the_registry_row_merges_nothing(case: _Case) -> None:
    case.comment()  # what an author thread could post on its own PR
    v, why = case.sb.authority()
    assert v == "FAIL" and "not adjudicated" in why[0]
    case.window()
    case.sb.gate()
    assert not case.merged() and case.sb.notices == []


def test_a_registry_copy_gone_stale_by_window_end_merges_nothing(case: _Case) -> None:
    case.comment()
    case.sync(_row())
    assert case.sb.authority()[0] == "CLEAR"
    case.window()  # 24 h pass and nothing re-synced the copy: a HOLD could be missing
    case.sb.gate()
    assert not case.merged()
    case.sync()  # a fresh copy that still agrees
    case.sb.gate()
    assert case.merged()


def test_a_hold_in_the_synced_registry_at_window_end_merges_nothing(case: _Case) -> None:
    case.comment()
    case.sync(_row())
    assert case.sb.authority()[0] == "CLEAR"
    case.window()
    case.sync(_row(), _row(verdict="HOLD"))
    case.sb.gate()
    assert not case.merged()


def test_a_hold_comment_during_the_window_is_a_veto(case: _Case) -> None:
    case.comment()
    case.sync(_row())
    assert case.sb.authority()[0] == "CLEAR"
    case.window()
    case.sync()
    case.comment("HOLD", at="2026-11-04T13:00:00Z")
    case.sb.gate()
    assert not case.merged()


def test_a_clear_older_than_the_review_run_merges_nothing(case: _Case) -> None:
    case.comment(at=BEFORE)
    case.sync(_row())
    assert case.sb.authority()[0] == "FAIL"
    case.window()
    case.sync()
    case.sb.gate()
    assert not case.merged()


@pytest.mark.parametrize("job", ["replay-shadow", "risk-invariants", "quality"])
def test_no_other_red_job_is_ever_adjudicated(case: _Case, job: str) -> None:
    case.sb.gh.conclusion[job] = "failure"
    case.comment()
    case.sync(_row())
    assert case.sb.authority()[0] == "FAIL"
    case.window()
    case.sync()
    case.sb.gate()
    assert not case.merged()


def test_a_change_to_a_check_is_never_adjudicated(tmp_path: Path, monkeypatch: Any) -> None:
    case = _Case(tmp_path, monkeypatch, files=(CODE, ".github/workflows/ci.yml"))
    case.comment()
    case.sync(_row())
    assert case.sb.authority()[0] == "FAIL"
    case.window()
    case.sync()
    case.sb.gate()
    assert not case.merged()


def test_it_takes_the_window_and_is_never_quarantined_or_merged_at_once(case: _Case) -> None:
    case.comment()
    case.sync(_row())
    assert case.sb.authority()[0] == "CLEAR"
    case.sb.gate()
    assert not case.merged() and len(case.sb.notices) == 1
    assert not [w for w in case.sb.gh.writes if "/labels" in w[1]]  # no quarantine label
    case.sb.clock.advance(hours=24, minutes=1)
    case.sync()
    case.sb.gate()
    assert case.merged()


def test_with_live_auto_merge_switched_off_nothing_merges(case: _Case) -> None:
    case.sb.gh.board.pop()  # only ACTIVATE RELEASE CONTROLLER stands
    case.comment()
    case.sync(_row())
    case.sb.authority()
    case.window()
    case.sync()
    case.sb.gate()
    assert not case.merged() and case.sb.notices == []


def test_a_deactivate_during_the_window_is_a_veto(case: _Case) -> None:
    case.comment()
    case.sync(_row())
    assert case.sb.authority()[0] == "CLEAR"
    case.window()
    case.sync()
    case.sb.gh.board.append({**case.sb.gh.board[0], "body": case.sb.ag.DEACTIVATE,
                             "created_at": "2026-11-05T00:00:00Z",
                             "updated_at": "2026-11-05T00:00:00Z"})  # fmt: skip
    case.sb.gate()
    assert not case.merged()


def test_zucks_own_path_is_unchanged_and_needs_no_registry(case: _Case) -> None:
    case.comment()
    case.sb.gh.board.append({**case.sb.gh.board[0], "body": case.sb.ag.APPROVE,
                             "created_at": "2026-11-04T11:30:00Z",
                             "updated_at": "2026-11-04T11:30:00Z"})  # fmt: skip
    case.sb.gate()
    (m,) = case.sb.gh.merges()
    assert "audit CLEAR" in m["commit_title"]
