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


def test_the_enrolment_engine_holds_only_new_certificates_and_never_a_running_clock(
        tmp_path, monkeypatch):
    import shadow_forward as sf
    shadow = tmp_path / "shadow"
    shadow.mkdir()
    old_key = sf.sleeve_key("EURUSD", "asia", {}, "overnight_gap_decay", "LONG")
    (shadow / "shadow_state.json").write_text(json.dumps({old_key: {"status": "ACTIVE"}}))
    monkeypatch.setattr(sf, "SHADOW_DIR", shadow)
    monkeypatch.setattr(sf, "_frozen_clock_params", lambda: {})
    monkeypatch.setitem(sys.modules, "shadow_admission",
                        types.SimpleNamespace(authorized_runs=lambda base: _runs()))
    monkeypatch.setattr(ai, "PLACEBO_REPORT", _placebo(tmp_path, "GATE_BLIND", ["sign_flip"]))
    monkeypatch.setattr(ai, "REPLICATION_VERDICTS", tmp_path / "none.json")
    rows = sf.certified_sleeves()
    assert [r[0] for r in rows] == ["EURUSD"]            # the running clock keeps its row
    assert [h["certificate"] for h in sf.HELD_AT_INTEGRITY] == ["new"]
    assert sf.HELD_AT_INTEGRITY[0]["reason"].startswith(ai.HELD_PLACEBO)

    # the alarm clears and the certificate is replicated: it enrols on the very next pass
    fp = ai.spec_fingerprint("GBPUSD", "overnight_gap_decay", "asia", None, {})
    monkeypatch.setattr(ai, "PLACEBO_REPORT", _placebo(tmp_path, "OK", []))
    monkeypatch.setattr(ai, "REPLICATION_VERDICTS", _verdicts(
        tmp_path, {"new": {"verdict": "REPLICATED", "fp": fp}}))
    monkeypatch.setattr(ai, "placebo_alarm",
                        lambda path=None, now=None: {"state": ai.CLEAR, "blocks": False})
    rows = sf.certified_sleeves()
    assert sorted(r[0] for r in rows) == ["EURUSD", "GBPUSD"]
    assert sf.HELD_AT_INTEGRITY == []


def test_the_enrolment_census_names_a_held_certificate_and_never_calls_it_overdue(tmp_path):
    import forward_enrolment as fe
    gate = ai.IntegrityGate(alarm={"state": ai.ALARM, "blocks": True, "why": "blind"})
    runs = _runs()
    stamps = {("GBPUSD", "overnight_gap_decay", "asia", "LONG"):
              (NOW - timedelta(hours=30)).isoformat(),
              ("EURUSD", "overnight_gap_decay", "asia", "LONG"):
              (NOW - timedelta(hours=30)).isoformat()}
    body = fe.census(runs, {}, stamps, NOW, gate=gate)
    assert body["n_held"] == 2 and body["n_missing"] == 0 and body["overdue"] == []
    assert all(h["held"].startswith(ai.HELD_PLACEBO) for h in body["held"])
    # without a gate the census is exactly what it always was
    plain = fe.census(runs, {}, stamps, NOW)
    assert plain["n_missing"] == 2 and len(plain["overdue"]) == 2 and plain["n_held"] == 0


@pytest.mark.parametrize("status", ["HELD_PLACEBO_ALARM", "ACTIVE"])
def test_lane_clock_keys_reads_every_lane(tmp_path, status):
    (tmp_path / "shadow_state.json").write_text(json.dumps({"A.asia": {"status": status}}))
    (tmp_path / "scalp_shadow_state.json").write_text(json.dumps({"sleeves": {"s1": {}}}))
    keys = ai.lane_clock_keys(tmp_path)
    assert "s1" in keys
    assert ("A.asia" in keys) is (status == "ACTIVE")


# ---------------------------------------------------------------- 2026-10-06 audit: scoped hold
def test_the_hold_applies_only_to_families_the_replication_lane_has_a_rule_for(tmp_path):
    """Growth Governance Rule 1: a family with no written replication rule can never read
    REPLICATED, so holding it would be a permanent veto. It proceeds and is counted by name."""
    clear = _placebo(tmp_path, "OK", [])
    gate = ai.IntegrityGate.load(placebo=clear, now=NOW, verdicts=_verdicts(tmp_path, {}),
                                 rule_families=frozenset({"overnight_gap_decay"}))
    kw = {"symbol": "EURUSD", "selector": "asia", "side": None, "params": {}}
    assert gate.hold("ruled", family="overnight_gap_decay", **kw).startswith(
        ai.HELD_UNREPLICATED)
    assert gate.hold("unruled", family="dav_range_filter_adx", **kw) is None
    s = gate.summary()
    assert s["n_held"] == 1 and s["held_by_kind"] == {ai.HELD_UNREPLICATED: 1}
    assert s["proceeded_without_rule"] == {"unruled": "dav_range_filter_adx"}
    assert s["n_proceeded_without_rule"] == 1 and s["missed_growth_rail"] == "replication_hold"
    # asking twice does not double-count; an absent family is the breakout, which has a rule
    gate.hold("ruled", family="overnight_gap_decay", **kw)
    assert gate.summary()["n_held"] == 1
    br = ai.IntegrityGate.load(placebo=clear, now=NOW, verdicts=_verdicts(tmp_path, {}),
                               rule_families=frozenset({"session_range_breakout"}))
    assert br.hold("b", family=None, **kw) is not None
    # the placebo alarm is about the certifier, so it still holds a family with no rule
    alarm = ai.IntegrityGate.load(placebo=_placebo(tmp_path, "GATE_BLIND", ["x"]), now=NOW,
                                  verdicts=_verdicts(tmp_path, {}), rule_families=frozenset())
    assert alarm.hold("u", family="dav_range_filter_adx", **kw).startswith(ai.HELD_PLACEBO)


def test_the_live_rule_set_is_the_replication_spec_book():
    import replication_civilization as rc
    fams, src = ai.replication_rule_families()
    assert fams == frozenset(rc.SPEC_BOOK) and src.endswith("SPEC_BOOK")
    assert ai.IntegrityGate.load(placebo=Path("/nonexistent"), now=NOW).rule_families == fams


def test_an_unreadable_rule_book_keeps_the_hold_for_every_family_and_says_so(tmp_path):
    gate = ai.IntegrityGate(alarm={"blocks": False}, rule_families=None)
    assert gate.hold("x", symbol="EURUSD", family="anything", selector="", side=None,
                     params={}) is not None
    assert gate.summary()["rule_families"] == ai.UNMEASURED


def test_the_hold_has_a_missed_growth_line(tmp_path, monkeypatch):
    import missed_growth as mg
    [r] = [x for x in mg.all_rails() if x.name == "replication_hold"]
    assert r.measure == "measure_replication_hold" and r.measure in mg.MEASURES
    assert len([x for x in mg.all_rails() if x.name == "replication_hold"]) == 1
    monkeypatch.setattr(mg, "FORWARD_ENROLMENT", tmp_path / "absent.json")
    assert mg.measure_replication_hold(r, {}, {})["verdict"] == mg.UNMEASURED
    doc = {"held": [{"key": "k1", "family": "overnight_gap_decay", "clockless_hours": 5.0,
                     "held": "HELD_UNREPLICATED (UNREACHED): x"},
                    {"key": "k2", "family": "monday_gap", "clockless_hours": 2.5,
                     "held": "HELD_REPLICATION_MISMATCH: y"},
                    {"key": "k3", "family": "dow_effect", "clockless_hours": 9.0,
                     "held": "HELD_PLACEBO_ALARM: z"}],
           "integrity": {"n_proceeded_without_rule": 7}}
    p = tmp_path / "FORWARD_ENROLMENT.json"
    p.write_text(json.dumps(doc), "utf-8")
    monkeypatch.setattr(mg, "FORWARD_ENROLMENT", p)
    m = mg.measure_replication_hold(r, {}, {})
    assert m["verdict"] == mg.UNMEASURED and m["n_held"] == 2 and m["n_placebo_held"] == 1
    assert m["deferred_clock_hours"] == 7.5 and m["n_proceeded_without_rule"] == 7
    assert m["ledger_line"]["deferred_clock_hours"] == 7.5
    # the binding hold lands in the ledger as an UNPRICED line (value null, never 0.0)
    ledger = tmp_path / "missed_growth.jsonl"
    monkeypatch.setattr(mg, "LEDGER", ledger)
    monkeypatch.setattr(mg, "OUT", tmp_path / "MISSED_GROWTH.json")
    monkeypatch.setattr(mg, "CALIBRATION", tmp_path / "rail_calibration.json")
    monkeypatch.setattr(mg, "ALLOC", tmp_path / "absent_alloc.json")
    out = mg.run(write=True, today="2026-10-06")
    rows = [json.loads(ln) for ln in ledger.read_text("utf-8").splitlines() if ln.strip()]
    [line] = [x for x in rows if x["rail"] == "replication_hold"]
    assert line["value"] is None and line["unpriced"] and line["n_held"] == 2
    assert out["rails"]["replication_hold"]["verdict"] == mg.UNMEASURED
    p.write_text(json.dumps({"held": [], "integrity": {}}), "utf-8")
    m = mg.measure_replication_hold(r, {}, {})
    assert m["verdict"] == mg.NOT_BINDING and m["sample"] and m["value_logw_per_day"] == 0.0
