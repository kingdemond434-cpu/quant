"""The research-integrity door: a NEW certificate starts a forward clock only when the latest
placebo audit caught every planted trap AND an independent rebuild under the same spec is
REPLICATED. Running clocks are never touched, and the door is not a quota.
"""
from __future__ import annotations

import json
import sys
import types
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest

DESK = Path(__file__).resolve().parents[1]
ROOT = DESK.parents[1]
for _p in (str(DESK / "research"), str(DESK), str(ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import admission_integrity as ai  # noqa: E402

NOW = datetime(2026, 9, 30, 12, 0, tzinfo=UTC)
SPEC = {"symbol": "EURUSD", "family": "overnight_gap_decay", "selector": "asia",
        "side": None, "params": {"rr": 1.0}}


def _placebo(tmp: Path, status: str, blind: list[str], age_h: float = 1.0) -> Path:
    p = tmp / "PLACEBO_AUDIT.json"
    p.write_text(json.dumps({"status": status, "blind_to": blind, "audit_recall": 0.8,
                             "measured_at": (NOW - timedelta(hours=age_h)).isoformat()}), "utf-8")
    return p


def _verdicts(tmp: Path, rows: dict[str, dict[str, Any]]) -> Path:
    p = tmp / "verdicts.json"
    p.write_text(json.dumps({"certificates": rows}), "utf-8")
    return p


def _fp(spec: dict[str, Any] = SPEC) -> str:
    return ai.spec_fingerprint(spec["symbol"], spec["family"], spec["selector"], spec["side"],
                               spec["params"])


def test_a_certifier_that_admitted_a_planted_trap_raises_the_program_alarm(tmp_path):
    a = ai.placebo_alarm(_placebo(tmp_path, "GATE_BLIND", ["sign_flip"]), NOW)
    assert a["state"] == ai.ALARM and a["blocks"] and "sign_flip" in a["why"]
    # an alarm is lifted by an audit that clears it, never by the audit going quiet
    stale = ai.placebo_alarm(_placebo(tmp_path, "GATE_BLIND", ["sign_flip"], age_h=200), NOW)
    assert stale["blocks"]


def test_clear_welded_stale_and_absent_audits_raise_no_alarm(tmp_path):
    assert ai.placebo_alarm(_placebo(tmp_path, "OK", []), NOW)["state"] == ai.CLEAR
    welded = ai.placebo_alarm(_placebo(tmp_path, "GATE_WELDED", []), NOW)
    assert not welded["blocks"]
    stale = ai.placebo_alarm(_placebo(tmp_path, "OK", [], age_h=100), NOW)
    assert stale["state"] == ai.UNMEASURED and not stale["blocks"]
    absent = ai.placebo_alarm(tmp_path / "none.json", NOW)
    assert absent["state"] == ai.UNMEASURED and not absent["blocks"]


def test_only_a_replicated_verdict_under_the_same_spec_releases_a_certificate(tmp_path):
    clear = _placebo(tmp_path, "OK", [])
    kw = {"symbol": SPEC["symbol"], "family": SPEC["family"], "selector": SPEC["selector"],
          "side": SPEC["side"], "params": SPEC["params"]}
    ok = ai.IntegrityGate.load(placebo=clear, now=NOW, verdicts=_verdicts(
        tmp_path, {"c1": {"verdict": "REPLICATED", "fp": _fp()}}))
    assert ok.hold("c1", **kw) is None
    # never judged, judged under another spec, mismatched, unmeasured: all wait, all by name
    assert ok.hold("c2", **kw).startswith(ai.HELD_UNREPLICATED + " (UNREACHED)")
    other = ai.IntegrityGate.load(placebo=clear, now=NOW, verdicts=_verdicts(
        tmp_path, {"c1": {"verdict": "REPLICATED", "fp": "0" * 16}}))
    assert "STALE_SPEC" in other.hold("c1", **kw)
    bad = ai.IntegrityGate.load(placebo=clear, now=NOW, verdicts=_verdicts(
        tmp_path, {"c1": {"verdict": "MISMATCH", "fp": _fp(), "why": ["SIGN"]}}))
    assert bad.hold("c1", **kw).startswith(ai.HELD_MISMATCH)
    unm = ai.IntegrityGate.load(placebo=clear, now=NOW, verdicts=_verdicts(
        tmp_path, {"c1": {"verdict": "UNMEASURED", "fp": _fp(), "why": ["no rule"]}}))
    assert "UNMEASURED" in unm.hold("c1", **kw)
    # the alarm outranks even a replicated certificate
    alarm = ai.IntegrityGate.load(placebo=_placebo(tmp_path, "GATE_BLIND", ["info_delay"]),
                                  now=NOW, verdicts=_verdicts(
                                      tmp_path, {"c1": {"verdict": "REPLICATED", "fp": _fp()}}))
    assert alarm.hold("c1", **kw).startswith(ai.HELD_PLACEBO)


def test_the_fingerprint_is_the_spec_not_the_spelling_of_an_absent_side():
    a = ai.spec_fingerprint("X", "f", "asia", None, {"b": 1, "a": 2})
    assert a == ai.spec_fingerprint("X", "f", "asia", "", {"a": 2, "b": 1})
    assert a != ai.spec_fingerprint("X", "f", "asia", "SHORT", {"a": 2, "b": 1})
    assert a != ai.spec_fingerprint("X", "f", "asia", None, {"a": 3, "b": 1})
    # the admission door defaults an absent family to the breakout; so must the fingerprint
    assert (ai.spec_fingerprint("X", None, "asia", None, {})
            == ai.spec_fingerprint("X", "session_range_breakout", "asia", None, {}))


def _runs() -> list[dict[str, Any]]:
    return [
        {"certificate": "old", "symbol": "EURUSD", "selector": "asia",
         "family": "overnight_gap_decay", "condition": None, "params": {}, "side": None},
        {"certificate": "new", "symbol": "GBPUSD", "selector": "asia",
         "family": "overnight_gap_decay", "condition": None, "params": {}, "side": None},
    ]


def test_every_certificate_gets_a_clock_and_the_door_holds_only_new_clocks_promotion(
        tmp_path, monkeypatch):
    """Principal 2026-11-13: "All certs passed go on forward clocks immediately". The door no
    longer withholds a clock; it stamps a NEW clock's promotion, and a clock that predates the
    door keeps the promotion path it always had."""
    import shadow_forward as sf
    shadow = tmp_path / "shadow"
    shadow.mkdir()
    old_key = sf.sleeve_key("EURUSD", "asia", {}, "overnight_gap_decay", "LONG")
    new_key = sf.sleeve_key("GBPUSD", "asia", {}, "overnight_gap_decay", "LONG")
    (shadow / "shadow_state.json").write_text(json.dumps({old_key: {"status": "ACTIVE"}}))
    monkeypatch.setattr(sf, "SHADOW_DIR", shadow)
    monkeypatch.setattr(sf, "_frozen_clock_params", lambda: {})
    monkeypatch.setitem(sys.modules, "shadow_admission",
                        types.SimpleNamespace(authorized_runs=lambda base: _runs()))
    monkeypatch.setattr(ai, "PLACEBO_REPORT", _placebo(tmp_path, "GATE_BLIND", ["sign_flip"]))
    monkeypatch.setattr(ai, "REPLICATION_VERDICTS", tmp_path / "none.json")
    rows = sf.certified_sleeves()
    assert sorted(r[0] for r in rows) == ["EURUSD", "GBPUSD"]   # BOTH on a clock, at once
    holds = {r[0]: sf._row_hold(r) for r in rows}
    assert holds["EURUSD"] == ""                                 # predates the door: untouched
    assert holds["GBPUSD"].startswith(ai.HELD_PLACEBO)           # new: promotion held
    assert [h["certificate"] for h in sf.HELD_AT_INTEGRITY] == ["new"]

    # the new clock now exists WITH its stamp: it is re-asked, never grandfathered
    (shadow / "shadow_state.json").write_text(json.dumps({
        old_key: {"status": "ACTIVE"},
        new_key: {"status": "ACTIVE", ai.PROMOTION_HOLD_FIELD: holds["GBPUSD"]}}))
    rows = sf.certified_sleeves()
    assert {r[0]: sf._row_hold(r) for r in rows}["GBPUSD"].startswith(ai.HELD_PLACEBO)

    # the alarm clears and the certificate is replicated: the hold lifts on the very next pass
    fp = ai.spec_fingerprint("GBPUSD", "overnight_gap_decay", "asia", None, {})
    monkeypatch.setattr(ai, "PLACEBO_REPORT", _placebo(tmp_path, "OK", []))
    monkeypatch.setattr(ai, "REPLICATION_VERDICTS", _verdicts(
        tmp_path, {"new": {"verdict": "REPLICATED", "fp": fp}}))
    monkeypatch.setattr(ai, "placebo_alarm",
                        lambda path=None, now=None: {"state": ai.CLEAR, "blocks": False})
    rows = sf.certified_sleeves()
    assert sorted(r[0] for r in rows) == ["EURUSD", "GBPUSD"]
    assert all(sf._row_hold(r) == "" for r in rows)
    assert sf.HELD_AT_INTEGRITY == []


def test_stamp_hold_sets_and_lifts_and_denies_promotion_authority():
    row: dict[str, Any] = {"promotion_authority": True}
    ai.stamp_hold(row, "HELD_UNREPLICATED (UNREACHED): x")
    assert row[ai.PROMOTION_HOLD_FIELD].startswith("HELD_UNREPLICATED")
    assert row["promotion_authority"] is False
    ai.stamp_hold(row, None)
    assert ai.PROMOTION_HOLD_FIELD not in row


def test_lane_hold_keys_and_promotion_hold_read_every_lane(tmp_path):
    (tmp_path / "shadow_state.json").write_text(json.dumps(
        {"A.asia": {"status": "ACTIVE", ai.PROMOTION_HOLD_FIELD: "HELD_X"},
         "B.asia": {"status": "ACTIVE"}}))
    (tmp_path / "qquant_shadow_state.json").write_text(json.dumps(
        {"qquant.c1": {"status": "ACTIVE", ai.PROMOTION_HOLD_FIELD: "HELD_Y"}}))
    assert ai.lane_hold_keys(tmp_path) == {"A.asia", "qquant.c1"}
    assert ai.promotion_hold("qquant.c1", tmp_path) == "HELD_Y"
    assert ai.promotion_hold("B.asia", tmp_path) is None


def test_the_census_calls_a_clockless_certificate_missing_whatever_the_door_says(tmp_path):
    """The door's verdict no longer files a clockless certificate under `held` (which never went
    OVERDUE): every clockless certificate is MISSING and overdue after one cycle."""
    import forward_enrolment as fe
    gate = ai.IntegrityGate(alarm={"state": ai.ALARM, "blocks": True, "why": "blind"})
    runs = _runs()
    stamps = {("GBPUSD", "overnight_gap_decay", "asia", "LONG"):
              (NOW - timedelta(hours=30)).isoformat(),
              ("EURUSD", "overnight_gap_decay", "asia", "LONG"):
              (NOW - timedelta(hours=30)).isoformat()}
    body = fe.census(runs, {}, stamps, NOW, gate=gate)
    assert body["n_held"] == 0 and body["n_missing"] == 2 and len(body["overdue"]) == 2
    assert all(m["promotion_hold"].startswith(ai.HELD_PLACEBO) for m in body["missing"])
    plain = fe.census(runs, {}, stamps, NOW)
    assert plain["n_missing"] == 2 and len(plain["overdue"]) == 2 and plain["n_held"] == 0


def test_the_census_counts_clocks_accruing_under_a_promotion_hold():
    import forward_enrolment as fe
    import shadow_forward as sf
    runs = _runs()[1:]
    key = sf.sleeve_key("GBPUSD", "asia", {}, "overnight_gap_decay", "LONG")
    clocks = {key: {"status": "ACTIVE", "lane": "shadow_state.json",
                    fe.PROMOTION_HOLD_FIELD: "HELD_UNREPLICATED (UNREACHED): pending"}}
    body = fe.census(runs, clocks, {}, NOW)
    assert body["n_enrolled"] == 1 and body["n_missing"] == 0
    assert body["n_promotion_held"] == 1
    assert body["promotion_hold_by_reason"] == {"HELD_UNREPLICATED (UNREACHED)": 1}


@pytest.mark.parametrize("status", ["HELD_PLACEBO_ALARM", "ACTIVE"])
def test_lane_clock_keys_reads_every_lane(tmp_path, status):
    (tmp_path / "shadow_state.json").write_text(json.dumps({"A.asia": {"status": status}}))
    (tmp_path / "scalp_shadow_state.json").write_text(json.dumps({"sleeves": {"s1": {}}}))
    keys = ai.lane_clock_keys(tmp_path)
    assert "s1" in keys
    assert ("A.asia" in keys) is (status == "ACTIVE")
