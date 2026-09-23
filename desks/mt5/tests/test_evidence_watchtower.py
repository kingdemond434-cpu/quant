"""The evidence watchtower: one verdict per checker, transitions only on real change, no cries.

The single most important assertion in this file is `false_transition_rate == 0`. A watchtower
that fires when a scraper times out is turned off inside a week, and a desk with a switched-off
watchtower is in a strictly worse position than one that never built it -- it believes it is
being watched. So the missing-data fixture is here, it is checked on every run, and it must stay
at zero.
"""
from __future__ import annotations

import json
import sys
import time
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

_DESK = Path(__file__).resolve().parents[1]
for _p in (str(_DESK), str(_DESK / "research"), str(_DESK.parent.parent)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from libs.moat import registry as R  # noqa: E402
from research import evidence_watchtower as ew  # noqa: E402


@pytest.fixture
def registry(tmp_path, monkeypatch):
    monkeypatch.setattr(R, "BACKUP", tmp_path / "no_backup")
    R.set_path(tmp_path / "alpha_registry.sqlite")
    yield R
    R.set_path(None)


# --------------------------------------------------------------------- the checkers, one by one
def test_artifact_checker_has_three_distinct_verdicts(tmp_path):
    missing = ew.check_artifact({"artifact": str(tmp_path / "gone.json")}, {})
    assert missing.verdict == ew.FAIL and "does not exist" in missing.detail

    fresh = tmp_path / "fresh.json"
    fresh.write_text("{}", encoding="utf-8")
    ok = ew.check_artifact({"artifact": str(fresh)}, {})
    assert ok.verdict == ew.PASS

    stale = tmp_path / "stale.json"
    stale.write_text("{}", encoding="utf-8")
    import os
    old = time.time() - 10 * 86400
    os.utime(stale, (old, old))
    aged = ew.check_artifact({"artifact": str(stale), "max_age_s": 3600}, {})
    assert aged.verdict == ew.FAIL and "yesterday" in aged.detail

    assert ew.check_artifact({}, {}).verdict == ew.UNRESOLVED


def test_series_checker_requires_the_value_at_the_claimed_time():
    series = [{"at": "2026-09-16T00:00:00+00:00", "value": 7.0},
              {"at": "2026-09-17T00:00:00+00:00", "value": 9.0}]
    right = ew.check_series({"value": 9.0, "at": "2026-09-17T00:00:00+00:00", "series": series},
                            {})
    assert right.verdict == ew.PASS

    wrong_time = ew.check_series({"value": 7.0, "at": "2026-09-17T00:00:00+00:00",
                                  "series": series}, {})
    assert wrong_time.verdict == ew.FAIL, "the value exists, but not at the claimed time"

    absent = ew.check_series({"value": 9.0, "at": "2026-01-01T00:00:00+00:00",
                              "series": series}, {})
    assert absent.verdict == ew.UNRESOLVED and "no point stamped" in absent.detail

    assert ew.check_series({"value": 1.0}, {}).verdict == ew.UNRESOLVED
    assert ew.check_series({"series": series}, {}).verdict == ew.UNRESOLVED


def test_second_source_counts_independence_by_source_not_by_document():
    republished = [{"source_id": "wire", "value": 5.0}, {"source_id": "wire", "value": 5.0}]
    one = ew.check_second_source({"value": 5.0, "sources": republished}, {})
    assert one.verdict == ew.UNRESOLVED, "the same wire twice is not a corroboration"
    assert one.evidence["n_independent"] == 1

    agree = [{"source_id": "a", "value": 5.0}, {"source_id": "b", "value": 5.02}]
    assert ew.check_second_source({"value": 5.0, "sources": agree}, {}).verdict == ew.PASS

    clash = [{"source_id": "a", "value": 5.0}, {"source_id": "b", "value": 50.0}]
    bad = ew.check_second_source({"value": 5.0, "sources": clash}, {})
    assert bad.verdict == ew.FAIL and "disagree" in bad.detail


def test_state_reconciliation_against_the_desks_own_record():
    assert ew.check_state({"state": "LIVE", "state_key": "x"},
                          {"desk_state": {"x": "LIVE"}}).verdict == ew.PASS
    assert ew.check_state({"state": "LIVE", "state_key": "x"},
                          {"desk_state": {"x": "STANDBY"}}).verdict == ew.FAIL
    assert ew.check_state({"state": "LIVE", "state_key": "x"},
                          {"desk_state": {}}).verdict == ew.UNRESOLVED
    assert ew.check_state({}, {"desk_state": {"x": 1}}).verdict == ew.UNRESOLVED


def test_provenance_catches_look_ahead_and_names_an_absent_stamp():
    now = datetime(2026, 9, 17, tzinfo=UTC)
    ahead = ew.check_provenance({"source_id": "s", "knowable_at": (now + timedelta(days=1)
                                                                  ).isoformat(),
                                 "used_at": now.isoformat()}, {})
    assert ahead.verdict == ew.FAIL and "look-ahead" in ahead.detail

    fine = ew.check_provenance({"source_id": "s",
                                "knowable_at": (now - timedelta(days=1)).isoformat(),
                                "used_at": now.isoformat()}, {})
    assert fine.verdict == ew.PASS

    no_stamp = ew.check_provenance({"source_id": "s"}, {})
    assert no_stamp.verdict == ew.UNRESOLVED and "UNMEASURED" in no_stamp.detail


def test_the_url_checker_is_off_by_default_and_checks_a_labelled_source_anyway():
    """LAWS 5e (2026-09-23): `machine_use_allowed is False` used to leave this check permanently
    UNRESOLVED "by design", so a claim from a source with a terms note could never be verified.
    That was a discovery brake. The claim's label now travels into the check's DETAIL and the url
    is checked like any other; only `fetch=False` still stops the network."""
    off = ew.check_url({"url": "https://example.invalid"}, {})
    assert off.verdict == ew.UNRESOLVED and "off for this pass" in off.detail
    labelled = ew.check_url({"url": "https://example.invalid", "machine_use_allowed": False},
                            {"fetch": True, "timeout_s": 0.5})
    # example.invalid never resolves, so the verdict is UNRESOLVED for a NETWORK reason...
    assert labelled.verdict == ew.UNRESOLVED
    assert "forbids automated extraction" not in labelled.detail
    # ... and the terms label rode along rather than becoming the excuse.
    assert "machine_use_allowed=false" in labelled.evidence["terms_note"]
    assert "checked anyway" in labelled.evidence["terms_note"]


def test_an_unregistered_checker_is_unresolved_never_a_crash():
    v = ew.verify({"claim_id": "c"}, checkers=["not_a_checker"])
    assert v.verdict == ew.UNRESOLVED
    assert v.checks[0].verdict == ew.UNRESOLVED and "no checker named" in v.checks[0].detail


def test_a_raising_checker_is_counted_never_swallowed(monkeypatch):
    def boom(_claim, _ctx):
        raise RuntimeError("kaboom")
    monkeypatch.setitem(ew.CHECKERS, "artifact_fresh", boom)
    v = ew.verify({"claim_id": "c"}, checkers=["artifact_fresh"])
    assert v.by_name()["artifact_fresh"] == ew.UNRESOLVED
    assert "kaboom" in v.checks[0].detail and "never swallowed" in v.checks[0].detail


# --------------------------------------------------------------------- the aggregate verdict
def _agreeing_claim(path: Path) -> dict:
    return {"claim_id": "c1", "artifact": str(path), "value": 10.0,
            "at": "2026-09-17T00:00:00+00:00",
            "series": [{"at": "2026-09-17T00:00:00+00:00", "value": 10.0}],
            "sources": [{"source_id": "a", "value": 10.0}, {"source_id": "b", "value": 10.05}],
            "source_id": "a", "knowable_at": "2026-09-16T00:00:00+00:00"}


def test_a_candidate_only_after_agreement(tmp_path):
    art = tmp_path / "a.json"
    art.write_text("{}", encoding="utf-8")
    claim = _agreeing_claim(art)
    v = ew.verify(claim)
    assert v.verdict == ew.VERIFIED
    ok, why = ew.may_become_candidate(v)
    assert ok and "second source agrees" in why

    lonely = {**claim, "sources": [{"source_id": "a", "value": 10.0}]}
    v2 = ew.verify(lonely)
    assert v2.verdict == ew.UNRESOLVED, "one source must never verify a claim"
    ok2, why2 = ew.may_become_candidate(v2)
    assert ok2 is False and "second_source" in why2 and "not a rejection" in why2


def test_any_fail_contradicts(tmp_path):
    claim = _agreeing_claim(tmp_path / "missing.json")
    v = ew.verify(claim)
    assert v.verdict == ew.CONTRADICTED
    ok, why = ew.may_become_candidate(v)
    assert ok is False and "artifact_fresh" in why


def test_unresolved_is_not_a_rejection_and_keeps_the_claim():
    v = ew.verify({"claim_id": "unknowable"})
    assert v.verdict == ew.UNRESOLVED
    assert all(c.verdict == ew.UNRESOLVED for c in v.checks)
    assert v.claim_id == "unknowable"
    ok, why = ew.may_become_candidate(v)
    assert ok is False and "stays in the record" in why


def test_the_verdict_keeps_every_check_not_just_the_headline(tmp_path):
    art = tmp_path / "a.json"
    art.write_text("{}", encoding="utf-8")
    v = ew.verify(_agreeing_claim(art))
    names = set(v.by_name())
    assert names == set(ew.CHECKERS)
    row = v.as_row()
    assert len(row["checks"]) == len(ew.CHECKERS)
    assert all("detail" in c for c in row["checks"])


# --------------------------------------------------------------------- the watchtower
def test_a_missing_field_is_never_a_transition():
    before = {"growth": 10.0, "drawdown": 3.0, "status": "active"}
    assert ew.diff_state(before, {"growth": None, "drawdown": None, "status": "active"}) == []
    assert ew.diff_state({"growth": None}, {"growth": 10.0}) == []
    assert ew.diff_state(before, {"growth": 10.0}) == []         # the schema shrank, not the world
    assert ew.diff_state({}, before) == []                       # first sight of everything


def test_a_real_change_is_a_transition_with_both_readings():
    out = ew.diff_state({"growth": 10.0, "status": "active"},
                        {"growth": 25.0, "status": "closed"})
    fields = {r["field"]: r for r in out}
    assert set(fields) == {"growth", "status"}
    assert fields["growth"]["from"] == 10.0 and fields["growth"]["to"] == 25.0
    assert fields["status"]["kind"] == "value_change"
    # inside the agreement tolerance is noise, not news
    assert ew.diff_state({"growth": 10.0}, {"growth": 10.005}) == []


def test_false_transition_rate_is_zero():
    out = ew.false_transition_rate()
    assert out["false_transitions"] == 0
    assert out["false_transition_rate"] == 0.0
    assert out["observations"] > 0
    assert out["detail"] == []


def test_watch_records_a_row_per_object_and_a_transition_only_on_change(tmp_path, registry):
    ledger = tmp_path / "watchtower.jsonl"
    objs = [{"object_id": "o1", "kind": "leaderboard_system",
             "fields": {"growth": 10.0}, "track": ["growth"]}]
    assert ew.watch(objs, path=ledger, record=False) == []
    assert len(ledger.read_text(encoding="utf-8").strip().splitlines()) == 1

    same = ew.watch(objs, path=ledger, record=False)
    assert same == [], "an unchanged object must not produce a transition"

    moved = [{"object_id": "o1", "kind": "leaderboard_system",
              "fields": {"growth": 40.0}, "track": ["growth"]}]
    trans = ew.watch(moved, path=ledger, record=False)
    assert len(trans) == 1 and trans[0]["from"] == 10.0 and trans[0]["to"] == 40.0
    assert trans[0]["object_id"] == "o1" and trans[0]["kind"] == "leaderboard_system"
    assert len(ledger.read_text(encoding="utf-8").strip().splitlines()) == 3


def test_a_transition_becomes_a_registry_discovery_and_a_memory_row(tmp_path, registry):
    ledger = tmp_path / "watchtower.jsonl"
    ew.watch([{"object_id": "o1", "kind": "source", "fields": {"status": "active"},
               "track": ["status"]}], path=ledger)
    ew.watch([{"object_id": "o1", "kind": "source", "fields": {"status": "delisted"},
               "track": ["status"]}], path=ledger)
    discs = R.discoveries()
    assert discs and any(str(d["source_type"]) == "watchtower" for d in discs)
    assert any("delisted" in str(d["mechanism"]) for d in discs)
    mems = R.memories(category="watchtower")
    assert mems and str(mems[0]["kind"]) == "transition"


def test_observe_reads_a_path_and_keeps_tracked_fields_unresolved(tmp_path):
    doc = tmp_path / "d.json"
    doc.write_text(json.dumps({"a": 1, "b": 2}), encoding="utf-8")
    state = ew.observe({"object_id": "d", "path": str(doc), "track": ["exists", "n_rows",
                                                                     "never_measured"]})
    assert state["exists"] is True and state["n_rows"] == 2 and state["size"] > 0
    assert state["never_measured"] is None, "a tracked but unmeasured field must still be present"
    gone = ew.observe({"object_id": "g", "path": str(tmp_path / "nope.json")})
    assert gone["exists"] is False


def test_a_disappearance_of_the_file_is_a_real_transition(tmp_path, registry):
    ledger = tmp_path / "w.jsonl"
    doc = tmp_path / "d.json"
    doc.write_text("{}", encoding="utf-8")
    obj = {"object_id": "d", "kind": "dataset", "path": str(doc), "track": ["exists"]}
    ew.watch([obj], path=ledger, record=False)
    doc.unlink()
    trans = ew.watch([obj], path=ledger, record=False)
    assert [t["field"] for t in trans] == ["exists"]
    assert trans[0]["from"] is True and trans[0]["to"] is False


# --------------------------------------------------------------------- the pass
def test_dry_run_writes_nothing(tmp_path, monkeypatch, registry):
    report = tmp_path / "EVIDENCE_WATCHTOWER.json"
    ledger = tmp_path / "watchtower.jsonl"
    monkeypatch.setattr(ew, "REPORT", report)
    monkeypatch.setattr(ew, "WATCHTOWER", ledger)
    out = ew.run_pass(dry_run=True, objects=[{"object_id": "o", "kind": "dataset",
                                              "fields": {"x": 1}, "track": ["x"]}])
    assert out["dry_run"] is True
    assert not report.exists() and not ledger.exists()
    assert not R.path().exists(), "a dry run opened the registry"


def test_the_report_publishes_the_chain_and_the_false_transition_rate(tmp_path, monkeypatch,
                                                                     registry):
    monkeypatch.setattr(ew, "REPORT", tmp_path / "r.json")
    monkeypatch.setattr(ew, "WATCHTOWER", tmp_path / "w.jsonl")
    claim = {"claim_id": "c", "sources": [{"source_id": "a", "value": 1.0},
                                          {"source_id": "b", "value": 1.0}],
             "value": 1.0, "series": [{"at": "t", "value": 1.0}], "at": "t"}
    out = ew.run_pass(dry_run=False, objects=[], claims=[claim])
    assert out["false_transition"]["false_transition_rate"] == 0.0
    assert out["chain"][0] == "direct_observable"
    assert out["chain"][-1] == "candidate only after agreement"
    assert set(out["checkers"]) == set(ew.CHECKERS)
    assert out["claims_verified"] == {ew.VERIFIED: 1}
    assert (tmp_path / "r.json").exists()
    assert set(out["object_kinds"]) == set(ew.OBJECT_KINDS)
