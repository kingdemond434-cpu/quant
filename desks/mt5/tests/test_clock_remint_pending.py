"""A re-seal never retires a forward clock whose certificate is only waiting to be re-judged.

Audit 2026-10-13 (T8 blocker a): a re-seal changes the attestation, `remint_partition` lifts every
old-header row into `pending_rejudge`, `authorized_runs` stops returning them, and the strict
CLOCK-IF-AND-ONLY-IF-CERTIFICATE audit then retired every clock the desk held. A certificate
under re-mint is still a certificate: its clock is kept until the judge rules.
"""
from __future__ import annotations

import json
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
DESK = ROOT / "desks" / "mt5"
for _p in (str(ROOT), str(DESK), str(DESK / "research")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import clock_certificate as cc  # noqa: E402
import clock_liveness as cl  # noqa: E402


def _clock(key: str) -> dict:
    return {"lane": "main", "key": key, "symbol": key.split(".")[0], "timeframe": "H1",
            "verdict": "ACCRUING", "status": "ACTIVE"}


def _audit(tmp_path: Path, clocks: list, roster: set, pending: set | None, *,
           verdicts: list | None = None, canon_doc: dict | None = None,
           apply: bool = False, **kw) -> dict:
    canon = tmp_path / "canon.json"
    canon.write_text(json.dumps(canon_doc or {"n": 1, "survivors": {"a": {}}}),
                     encoding="utf-8")
    (tmp_path / "v.jsonl").write_text(
        "".join(json.dumps(v) + "\n" for v in (verdicts or [])), encoding="utf-8")
    return cc.audit(clocks, roster=roster, apply=apply, canon_path=canon,
                    verdict_path=tmp_path / "v.jsonl", ledger_path=tmp_path / "b.json",
                    queue_path=tmp_path / "q.jsonl", pending=pending, **kw)


def _verdict(gate: str, *, passed: bool = False) -> dict:
    return {"sym": "EURUSD", "family": "carry", "cell": "EURUSD.carry.x",
            "at": "2026-10-20T00:00:00+00:00", "downstream_status": "JUDGED",
            "terminal_gate": gate, "passed": passed}


KEY = "EURUSD.carry.continuous"


def test_a_pending_clock_the_judge_has_rejected_breaches_and_retires(tmp_path: Path) -> None:
    """THE MUST-FIX OF #351: still in the pending block, off the roster, and REJECTED by the
    judge at a gate no parameters can change -- LIVE retires it, and so must this state."""
    out = _audit(tmp_path, [_clock(KEY)], set(), {KEY}, verdicts=[_verdict("economic_prior")])
    assert out["remint_pending"] == 0 and out["breached"] == 1
    assert [r["key"] for r in out["retire"]] == [KEY]
    assert out["retire"][0]["retired_reason"] == "JUDGE_REJECTED"
    assert "REJECTED" in out["rows"][0]["why"]
    assert out["remint_pending_overdue"] == 0 and out["remint_pending_oldest_age_s"] == 0.0


def test_the_rejection_retires_it_whichever_waiting_branch_would_have_kept_it(
        tmp_path: Path) -> None:
    """Listed by engine key AND parked by cell in the canon: the outcome is LIVE's, a breach."""
    canon = {"n": 1, "survivors": {"a": {}}, "pending_rejudge": {"external.x": {
        "shadow_spec": {"symbol": "EURUSD", "family": "carry", "selector": "continuous",
                        "params": {}}}}}
    for pending in ({KEY}, None):
        out = _audit(tmp_path, [_clock(KEY)], set(), pending, canon_doc=canon,
                     verdicts=[_verdict("economic_prior")])
        assert out["breached"] == 1 and out["remint_pending"] == 0
        assert out["pending_rejudge"] == 0 and len(out["retire"]) == 1


def test_a_verdict_that_is_not_this_clocks_rejection_keeps_it_pending(tmp_path: Path) -> None:
    for v in (_verdict("deflated_sharpe"),                     # a sibling's, parameter-dependent
              {**_verdict("economic_prior"), "downstream_status": "NOT_RUN_QUEUED"},
              _verdict("walk_forward", passed=True)):
        out = _audit(tmp_path, [_clock(KEY)], set(), {KEY}, verdicts=[v])
        assert out["remint_pending"] == 1 and out["breached"] == 0 and not out["retire"]


def test_the_wait_is_aged_from_the_canons_pending_since_and_alarms_past_the_bound(
        tmp_path: Path) -> None:
    now = datetime(2026, 11, 1, tzinfo=UTC)
    young = (now - timedelta(hours=2)).isoformat()
    out = _audit(tmp_path, [_clock(KEY)], set(), {KEY}, now=now, pending_since={KEY: young})
    assert out["remint_pending_oldest_age_s"] == 2 * 3600.0
    assert out["remint_pending_overdue"] == 0
    assert out["rows"][0]["pending_since"] == young
    old = (now - timedelta(seconds=cc.REMINT_PENDING_ALARM_S + 60)).isoformat()
    out = _audit(tmp_path, [_clock(KEY)], set(), {KEY}, now=now, pending_since={KEY: old})
    assert out["remint_pending_overdue"] == 1 and out["rows"][0]["remint_pending_overdue"]
    # AN ALARM, NEVER A RETIREMENT: the certificate was not rejected, so the clock is kept.
    assert out["remint_pending"] == 1 and out["breached"] == 0 and not out["retire"]


def test_a_row_with_no_pending_since_is_aged_from_the_pass_that_first_saw_it(
        tmp_path: Path) -> None:
    t0 = datetime(2026, 11, 1, tzinfo=UTC)
    first = _audit(tmp_path, [_clock(KEY)], set(), {KEY}, now=t0, apply=True)
    assert first["remint_pending_oldest_age_s"] == 0.0
    later = t0 + timedelta(seconds=cc.REMINT_PENDING_ALARM_S + 3600)
    # a canon stamp YOUNGER than what this audit already saw cannot make the wait look shorter
    out = _audit(tmp_path, [_clock(KEY)], set(), {KEY}, now=later, apply=True,
                 pending_since={KEY: (later - timedelta(hours=1)).isoformat()})
    assert out["remint_pending_oldest_age_s"] == cc.REMINT_PENDING_ALARM_S + 3600
    assert out["remint_pending_overdue"] == 1
    assert json.loads((tmp_path / "b.json").read_text("utf-8"))["remint_first_seen"] == {
        KEY: t0.isoformat()}


def test_pending_roster_since_carries_the_canons_stamp(tmp_path: Path, monkeypatch) -> None:
    import shadow_forward as sf
    spec = {"symbol": "EURUSD", "selector": "continuous", "family": "carry",
            "params": {"lookback": 20}, "side": "SHORT"}
    (tmp_path / "reports").mkdir()
    (tmp_path / "reports" / "UNIVERSAL_SURVIVORS.json").write_text(json.dumps(
        {"pending_rejudge": {"external.x": {"shadow_spec": spec,
                                            "pending_since": "2026-10-30T00:00:00+00:00"},
                             "external.y": {"shadow_spec": {**spec, "symbol": "GBPUSD"}}}}),
        encoding="utf-8")
    monkeypatch.setattr(cl, "DESK", tmp_path)
    since, _ = cl.pending_roster_since()
    assert since == {
        sf.sleeve_key("EURUSD", "continuous", {"lookback": 20}, "carry", "SHORT"):
            "2026-10-30T00:00:00+00:00",
        sf.sleeve_key("GBPUSD", "continuous", {"lookback": 20}, "carry", "SHORT"): None}
    assert cl.pending_roster()[0] == set(since)


def test_a_clock_whose_certificate_is_pending_rejudge_is_kept(tmp_path: Path) -> None:
    out = _audit(tmp_path, [_clock("EURUSD.carry.continuous")], set(),
                 {"EURUSD.carry.continuous"})
    assert out["breached"] == 0 and not out["retire"]
    assert out["remint_pending"] == 1
    assert out["unbacked_live"] == 0 and out["awaiting"] == 0
    assert "pending_rejudge" in out["rows"][0]["why"]


def test_a_clock_with_no_certificate_anywhere_is_still_retired(tmp_path: Path) -> None:
    out = _audit(tmp_path, [_clock("EURUSD.carry.continuous")], set(), {"GBPUSD.carry.x"})
    assert out["breached"] == 1 and len(out["retire"]) == 1
    assert out["remint_pending"] == 0


def test_a_backed_clock_stays_backed(tmp_path: Path) -> None:
    out = _audit(tmp_path, [_clock("EURUSD.carry.continuous")], {"EURUSD.carry.continuous"},
                 {"EURUSD.carry.continuous"})
    assert out["counts"][cc.BACKED] == 1 and out["remint_pending"] == 0


def test_without_a_pending_set_the_strict_rule_is_unchanged(tmp_path: Path) -> None:
    out = _audit(tmp_path, [_clock("EURUSD.carry.continuous")], set(), None)
    assert out["breached"] == 1


def test_pending_roster_keys_match_the_engine_key(tmp_path: Path, monkeypatch) -> None:
    import shadow_forward as sf
    spec = {"symbol": "EURUSD", "selector": "continuous", "family": "carry",
            "params": {"lookback": 20}, "side": "SHORT"}
    reports = tmp_path / "reports"
    reports.mkdir()
    (reports / "UNIVERSAL_SURVIVORS.json").write_text(json.dumps(
        {"survivors": {}, "pending_rejudge": {"external.x": {"shadow_spec": spec}}}),
        encoding="utf-8")
    monkeypatch.setattr(cl, "DESK", tmp_path)
    keys, why = cl.pending_roster()
    assert keys == {sf.sleeve_key("EURUSD", "continuous", {"lookback": 20}, "carry", "SHORT")}
    assert "1 certificate row" in why


def test_an_undeclared_side_contributes_both_directions(tmp_path: Path, monkeypatch) -> None:
    import shadow_forward as sf
    spec = {"symbol": "EURUSD", "selector": "continuous", "family": "carry", "params": {}}
    (tmp_path / "data").mkdir()
    (tmp_path / "data" / "UNIVERSAL_SURVIVORS.canon.json").write_text(json.dumps(
        {"pending_rejudge": {"external.x": {"shadow_spec": spec}}}), encoding="utf-8")
    monkeypatch.setattr(cl, "DESK", tmp_path)
    keys, _ = cl.pending_roster()
    assert keys == {sf.sleeve_key("EURUSD", "continuous", {}, "carry", s)
                    for s in ("LONG", "SHORT")}


def test_an_unreadable_canon_keeps_nothing(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(cl, "DESK", tmp_path)
    keys, _ = cl.pending_roster()
    assert keys == set()
