"""THE SIX COMMITTEES: deterministic specialist ensembles that challenge and never decide.

NO NETWORK, NO DESK STATE. Every run is handed planted subjects and a `tmp_path` state
directory. The load-bearing properties:

  * exactly six committees, every seat typed and trapped, every trap caught, no clean twin failed;
  * escalation climbs only while a level is unresolved, and a decisive objection's saved
    experiments are credited to the seat that made it;
  * a seat sees its own evidence partition only, and never sits for a subject that lacks it;
  * calibration settles on strictly newer evidence or a graph fate, never on the same evidence;
  * contradictions are between committees; a split inside one is its minority report;
  * a redundant seat retires on evidence, UNMEASURED never retires or re-weights anything;
  * the health file carries the six fields the CRO's committee duty reads for every specialist;
  * nothing here can certify, allocate, size or trade.
"""
from __future__ import annotations

import json
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

_DESK = Path(__file__).resolve().parents[1]
_ROOT = _DESK.parent.parent
for _p in (str(_DESK), str(_DESK / "research"), str(_ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import committee_ensembles as ens  # noqa: E402

from libs.research import committee_engine as ce  # noqa: E402

HEALTH_FIELDS = ("calibration", "false_alarm_rate", "experiments_saved", "overlap",
                 "ablation_value", "roi")


@pytest.fixture
def desk(tmp_path, monkeypatch):
    for name in ("STATE", "FINDINGS", "PREMORTEMS"):
        monkeypatch.setattr(ens, name, tmp_path / "committees" / f"{name.lower()}.json")
    monkeypatch.setattr(ens, "REPORT", tmp_path / "reports" / "COMMITTEES.json")
    monkeypatch.setattr(ens, "HEALTH", tmp_path / "reports" / "COMMITTEE_HEALTH.json")
    monkeypatch.setattr(ens, "_program", lambda: {"census": {"LIVE": 9, "NEVER": 1},
                                                  "legs": {}, "k_eff": 6.0,
                                                  "bench_cells": []})
    return tmp_path


def _planted() -> dict[str, list[ce.Subject]]:
    good_cell = ens._momentum_cell(12)
    return {
        ens.SCIENTIFIC: [
            ce.Subject(ens.SCIENTIFIC, "g_bad", {"mechanism": {"note": "", "status": "UNNAMED",
                                                               "params": {}},
                                                 "cell": ens._cell(ens._bars(seed=11),
                                                                   ens._longs(ens._bars(seed=11),
                                                                              5), 0.02)},
                       keys={"symbol": "EURUSD", "cell": "cell_bad"}, claim="bad"),
            ce.Subject(ens.SCIENTIFIC, "g_good", {"mechanism": {"note": "stops beyond the Asia "
                                                                "range are run at the open",
                                                                "status": "NAMED",
                                                                "params": {"lookback": 20}},
                                                  "cell": good_cell},
                       keys={"symbol": "GBPUSD", "cell": "cell_good"}, claim="good")],
        ens.FORENSIC: [ce.Subject(ens.FORENSIC, "rec1", {"record": ens._GOOD | {"win_pct": 2296}},
                                  keys={"symbol": "XAUUSD"})],
        ens.PORTFOLIO: [ce.Subject(ens.PORTFOLIO, "book", {"daily_r": ens._book()},
                                   keys={"book": "live"})],
        ens.EXECUTION: [ce.Subject(ens.EXECUTION, "desk", {"trades": ens._TRADES_COSTLY},
                                   keys={"symbol": "EURUSD"})],
        ens.DATA: [ce.Subject(ens.DATA, "EURUSD_H1", {"bars": ens._clean_frame(),
                                                      "tail": {"last_bar_age_h": 1.0}},
                              keys={"symbol": "EURUSD"})],
        ens.META: [],
    }


# ------------------------------------------------------------------------ the roster
def test_exactly_six_committees_every_seat_typed_and_trapped():
    assert len(ens.COMMITTEES) == 6 == len(set(ens.COMMITTEES)) == len(ens.TITLES)
    names = [s.name for s in ens.SEATS]
    assert len(names) == len(set(names))
    for c in ens.COMMITTEES:
        assert len(ens.seats_of(c)) >= 5, c
    for s in ens.SEATS:
        assert s.committee in ens.COMMITTEES and s.level in ce.LEVELS
        assert s.trap is not None and s.clean is not None, s.name
        assert s.failure_class and s.cost_s > 0


@pytest.mark.parametrize("seed", [0, 491_337, 2_026_093_020])
def test_every_seat_catches_its_trap_and_passes_its_clean_twin(seed):
    traps = ce.run_traps(ens.SEATS, seed)
    missed = [k for k, v in traps.items() if not v.get("caught")]
    alarms = [k for k, v in traps.items() if v.get("false_alarm")]
    assert missed == [] and alarms == []


def test_traps_are_regenerated_from_the_pass_seed():
    sp = next(s for s in ens.SEATS if s.name == "record_sample")
    assert sp.trap(1) != sp.trap(2) and sp.trap(1) == sp.trap(1)
    bars = next(s for s in ens.SEATS if s.name == "gaps")
    assert len(bars.trap(1)) != len(bars.trap(2))


def test_the_placebo_clean_twin_reads_no_future_bar():
    """The clean twin's signals must be a function of bars already closed at signal time."""
    cell = ens._event_cell(19)
    df, sigs = cell["df"], cell["signals"]
    pos = {t: i for i, t in enumerate(df.index)}
    for s in sigs:
        i = pos[s.time]
        wick_low = df["low"].iloc[i] < min(df["open"].iloc[i], df["close"].iloc[i]) * 0.995
        assert (s.side > 0) == bool(wick_low)


def test_no_committee_holds_authority():
    src = (_DESK / "research" / "committee_ensembles.py").read_text()
    for organ in ("gateway", "promoter", "allocat", "sleeves.json", "proposer_seat",
                  "UNIVERSAL_SURVIVORS"):
        assert f"import {organ}" not in src and f"from {organ}" not in src
    assert "sleeves.json" not in src and "proposer_seat" not in src


# ------------------------------------------------------------------------ the engine
def _sp(name, level, fn, partition="p", cost=0.01):
    return ce.Specialist(name, "c", partition, level, name.upper(), cost,
                         lambda part, key, _n=name: fn(_n, part))


def _res(verdict, strength):
    return lambda n, part: ce.Result(n, verdict, strength, n.upper() if verdict != ce.PASS
                                     else "", {"saw": sorted(part)}, "", 0.0)


def test_decisive_objection_stops_the_climb_and_credits_what_it_saved():
    seats = [_sp("a", 0, _res(ce.FAIL, 0.9)), _sp("b", 1, _res(ce.PASS, 0.9), cost=5.0)]
    ex = ce.examine(ce.Subject("c", "k", {"p": {"x": 1}}), seats, ce.blank_state(), 10.0)
    assert ex["levels"] == [0] and ex["verdict"] == ce.FAIL
    assert ex["saved_s"] == {"a": 5.0}


def test_weak_evidence_climbs():
    seats = [_sp("a", 0, _res(ce.PASS, 0.2)), _sp("b", 1, _res(ce.FAIL, 0.5)),
             _sp("c", 2, _res(ce.PASS, 0.7))]
    ex = ce.examine(ce.Subject("c", "k", {"p": {"x": 1}}), seats, ce.blank_state(), 10.0)
    assert ex["levels"] == [0, 1, 2] and ex["saved_s"] == {}


def test_a_seat_sees_only_its_partition_and_skips_subjects_without_it():
    seen = {}

    def spy(n, part):
        seen[n] = part
        return ce.Result(n, ce.PASS, 0.9, "", {}, "", 0.0)
    seats = [_sp("a", 0, spy, "prices"), _sp("b", 0, spy, "fills")]
    ex = ce.examine(ce.Subject("c", "k", {"prices": {"close": 1}, "secret": {"pnl": 9}}),
                    seats, ce.blank_state(), 10.0)
    assert seen == {"a": {"close": 1}}
    assert [r["specialist"] for r in ex["results"]] == ["a"]


def test_selection_orders_by_information_per_second_and_skips_retired():
    state = ce.blank_state()
    state["seats"] = {"slow": {"measured": 10, "fails": 5, "mean_cost_s": 10.0},
                      "fast": {"measured": 10, "fails": 5, "mean_cost_s": 0.1},
                      "sure": {"measured": 100, "fails": 0, "mean_cost_s": 0.1}}
    state["retired"] = {"gone": {}}
    seats = [_sp(n, 0, _res(ce.PASS, 0.9)) for n in ("slow", "fast", "sure", "gone")]
    picked = [s.name for s in ce.select(seats, state, 0, 100.0)]
    assert picked[0] == "fast" and "gone" not in picked and picked.index("sure") > 0


def test_a_crashing_or_unloadable_seat_is_unmeasured_not_a_verdict():
    def boom(n, part):
        raise RuntimeError("no bars")
    lazy = ce.Lazy(lambda: (_ for _ in ()).throw(LookupError("absent")))
    ex = ce.examine(ce.Subject("c", "k", {"p": {"x": 1}, "q": lazy}),
                    [_sp("a", 0, boom), _sp("b", 0, _res(ce.FAIL, 0.9), "q")],
                    ce.blank_state(), 10.0)
    assert {r["verdict"] for r in ex["results"]} == {ce.UNMEASURED}
    assert ex["verdict"] == ce.UNMEASURED


def test_minority_report_and_cross_committee_contradiction():
    ex = ce.examine(ce.Subject("c", "k", {"p": {}}),
                    [_sp("a", 0, _res(ce.FAIL, 0.5)), _sp("b", 0, _res(ce.PASS, 0.9)),
                     _sp("d", 0, _res(ce.PASS, 0.9))], ce.blank_state(), 10.0)
    assert [m["specialist"] for m in ex["minority"]] == ["a"]
    rows = [{"committee": "sim", "key": "x", "keys": {"symbol": "EURUSD"},
             "results": [{"specialist": "s", "verdict": ce.PASS, "probes": "COST_DEATH"}]},
            {"committee": "live", "key": "y", "keys": {"symbol": "EURUSD"},
             "results": [{"specialist": "l", "verdict": ce.FAIL, "probes": "COST_DEATH"}]},
            {"committee": "sim", "key": "z", "keys": {"symbol": "GBPUSD"},
             "results": [{"specialist": "s", "verdict": ce.PASS, "probes": "COST_DEATH"},
                         {"specialist": "t", "verdict": ce.FAIL, "probes": "COST_DEATH"}]}]
    out = ce.contradictions(rows)
    assert len(out) == 1 and out[0]["value"] == "EURUSD"
    assert out[0]["pass"] == {"sim": ["s"]} and out[0]["fail"] == {"live": ["l"]}


def test_calibration_settles_only_on_newer_evidence():
    state = ce.blank_state()
    ex = {"committee": "c", "key": "k", "fingerprint": "f1", "keys": {},
          "results": [{"specialist": "a", "verdict": ce.FAIL, "strength": 0.8, "cost_s": 0.0}]}
    ce.update_state(state, [ex], {})
    ce.update_state(state, [ex], {})                      # the same claim twice: kept once
    assert len(state["pending"]) == 1 and state["pending"][0]["p_fail"] == 0.9
    same = ens._outcome_fn([ex], {})
    assert ce.settle(state, same) == 0                   # same evidence: nothing settles
    newer = dict(ex, fingerprint="f2")
    assert ce.settle(state, ens._outcome_fn([newer], {})) == 1
    assert state["seats"]["a"]["brier_sum"] == pytest.approx(0.01)
    assert ce.calibrated_weight(state, "a") == pytest.approx(0.99)


def test_fate_seats_settle_on_the_graph():
    state = ce.blank_state()
    ex = {"committee": ens.SCIENTIFIC, "key": "g", "fingerprint": "f", "keys": {"cell": "n1"},
          "results": [{"specialist": "cost_surface", "verdict": ce.PASS, "strength": 0.5,
                       "cost_s": 0.0}]}
    ce.update_state(state, [ex], {})
    assert ce.settle(state, ens._outcome_fn([], {"n1": {"fate": "PROPOSED"}})) == 0
    assert ce.settle(state, ens._outcome_fn([], {"n1": {"fate": "FAILED"}})) == 1
    assert state["seats"]["cost_surface"]["brier_sum"] == pytest.approx(0.75 ** 2)


def _day(i):
    return (datetime(2026, 9, 1, tzinfo=UTC) + timedelta(days=i)).date().isoformat()


def _rows(n, dear_unique=False, prefix="k"):
    out = []
    for i in range(n):
        res = [{"specialist": "dear", "verdict": ce.FAIL, "strength": .9, "cost_s": 5.0},
               {"specialist": "dark", "verdict": ce.UNMEASURED, "strength": 0, "cost_s": 0.0}]
        if not dear_unique:
            res.append({"specialist": "cheap", "verdict": ce.FAIL, "strength": .9,
                        "cost_s": 0.01})
        out.append({"committee": "c", "key": f"{prefix}{i}", "fingerprint": "f", "keys": {},
                    "results": res, "retired_skipped": []})
    return out


def test_retirement_is_the_14_day_ablation_rule_with_a_reopen_path():
    seats = [_sp("dear", 0, _res(ce.FAIL, 0.9), cost=5.0), _sp("cheap", 0, _res(ce.FAIL, 0.9)),
             _sp("dark", 0, _res(ce.UNMEASURED, 0.0))]
    state = ce.blank_state()
    for d in range(ce.RETIRE_WINDOW_DAYS - 1):           # 13 days: too short a history
        rows = _rows(10)
        ce.record_day(state, rows, seats, ce.overlap(rows, seats), _day(d))
        assert ce.retire(state, seats, _day(d))["retired"] == []
    rows = _rows(10)
    last = _day(ce.RETIRE_WINDOW_DAYS - 1)
    ce.record_day(state, rows, seats, ce.overlap(rows, seats), last)
    out = ce.retire(state, seats, last)
    # Both FAIL on every subject, so NEITHER has ablation value: both retire. UNMEASURED never.
    assert sorted(out["retired"]) == ["cheap", "dear"] and "dark" not in state["retired"]
    assert state["retired"]["dear"]["reopen"]
    # A retired seat sits only on probe subjects, and the skips are billed.
    fp_probe = next(f"{i:08x}" for i in range(1000) if ce.is_probe(f"{i:08x}"))
    fp_plain = next(f"{i:08x}" for i in range(1000) if not ce.is_probe(f"{i:08x}"))
    assert [s.name for s in ce.plan(seats, state, 0, 99.0, None, probe=False)[0]] == ["dark"]
    assert "dear" in [s.name for s in ce.plan(seats, state, 0, 99.0, None, probe=True)[0]]
    assert ce.is_probe(fp_probe) and not ce.is_probe(fp_plain)
    skipped = [{"retired_skipped": ["dear"], "results": []}]
    ce.record_day(state, skipped, [], {}, last)
    assert state["missed"]["dear"]["subjects"] == 1 and state["missed"]["dear"]["bits"] > 0
    # A probe's unique catch inside the window re-opens it.
    rows = _rows(3, dear_unique=True, prefix="p")
    nxt = _day(ce.RETIRE_WINDOW_DAYS)
    ce.record_day(state, rows, seats, ce.overlap(rows, seats), nxt)
    assert ce.retire(state, seats, nxt)["reopened"] == ["dear"]


def test_a_seat_that_misses_its_trap_is_broken():
    state = ce.blank_state()
    ce.update_state(state, [], {"a": {"trap": ce.PASS, "caught": False}})
    assert "a" in state["broken"]
    ce.update_state(state, [], {"a": {"trap": ce.FAIL, "caught": True}})
    assert "a" in state["broken"]                        # 1 of 2 is below the floor
    for _ in range(8):
        ce.update_state(state, [], {"a": {"trap": ce.FAIL, "caught": True}})
    assert "a" not in state["broken"]


def test_experiments_rank_by_gain_per_second_and_queue_the_next_seat():
    rows = [{"committee": ens.FORENSIC, "key": "e1", "fingerprint": "f", "keys": {},
             "verdict": ce.FAIL,
             "results": [{"specialist": "effect_multiplicity", "verdict": ce.FAIL,
                          "strength": 0.6, "failure_class": "SELECTION_BIAS",
                          "recommended_test": "effect_sample", "info_gain": 0.0,
                          "cost_s": 0.0},
                         {"specialist": "x", "verdict": ce.UNMEASURED, "strength": 0.0,
                          "failure_class": "", "recommended_test": "a slow audit",
                          "info_gain": 0.0, "cost_s": 0.0}]}]
    exps = ce.compile_experiments(rows, {"effect_sample": 0.001, "a slow audit": 100.0})
    assert [e["test"] for e in exps] == ["effect_sample", "a slow audit"]
    q = ens._queue(exps)
    assert q == [{"committee": ens.FORENSIC, "subject": "e1", "test": "effect_sample",
                  "level": 1, "gain_per_s": exps[0]["gain_per_s"]}]
    tree = ce.falsification_tree(rows[0], exps)
    assert tree["branches"][0]["failure_class"] == "SELECTION_BIAS"
    assert "effect_sample" in tree["branches"][0]["experiments"]


# ------------------------------------------------------------------------ the pass
def test_a_pass_writes_the_report_the_health_and_the_order_hints(desk):
    doc = ens.run(budget_s=60, subjects=_planted(), fates={})
    rep = json.loads(ens.REPORT.read_text())
    assert set(rep["committees"]) == set(ens.COMMITTEES)
    assert rep["law"].startswith("Committees challenge")
    health = json.loads(ens.HEALTH.read_text())
    assert set(health["committees"]) == set(ens.COMMITTEES)
    for name, row in health["specialists"].items():
        for f in HEALTH_FIELDS:
            assert f in row, (name, f)
    assert "ORDER DECIDES WHAT FITS" in health["budget_disclosure"]
    assert health["committees"][ens.SCIENTIFIC]["verdict"] == "HEALTHY"
    hints = json.loads(ens.PREMORTEMS.read_text())
    assert set(hints) == {"cell_bad"} and hints["cell_bad"]["source"] == "committees"
    bad = next(e for e in doc["examined"] if e["key"] == "g_bad")
    assert bad["verdict"] == ce.FAIL
    good = next(e for e in doc["examined"] if e["key"] == "g_good")
    assert good["levels"][-1] == 4                        # a survivor climbs the whole battery
    fo = next(e for e in doc["examined"] if e["key"] == "rec1")
    assert fo["results"][0]["failure_class"] == "DATA_DEFECT" and fo["levels"] == [0]


def test_unchanged_evidence_is_not_re_examined_until_it_is_due(desk):
    subs = _planted()
    ens.run(budget_s=60, subjects=subs, fates={}, now_ts=1_000_000.0)
    again = ens.run(budget_s=60, subjects=_planted(), fates={}, now_ts=1_000_060.0)
    assert again["committees"][ens.DATA]["examined"] == 0
    later = ens.run(budget_s=60, subjects=_planted(), fates={},
                    now_ts=1_000_000.0 + ens.REMEASURE_H * 3600 + 1)
    assert later["committees"][ens.DATA]["due"] == 1


def test_budget_moves_to_information_and_unmeasured_moves_nothing():
    state = {"shares": dict(ens.BASE_SHARE)}
    per = {c: {"status": "RAN", "measured": 50, "seconds": 10.0, "unique": 5, "fails": 10}
           for c in ens.COMMITTEES}
    per[ens.FORENSIC] = {"status": "RAN", "measured": 50, "seconds": 10.0, "unique": 0,
                         "fails": 0}
    per[ens.META] = {"status": "RAN", "measured": 0, "seconds": 10.0}
    before = dict(state["shares"])
    after = ens._reweight(state, per, "2026-09-30")
    assert after[ens.FORENSIC] < before[ens.FORENSIC]
    assert sum(after.values()) == pytest.approx(1.0, abs=1e-3)
    assert min(after.values()) >= ens.SHARE_FLOOR
    assert state["committee_days"][ens.META]["2026-09-30"]["floor_passes"] == 0


def test_a_committee_that_adds_nothing_is_retired_and_readmitted_on_evidence():
    state = {"shares": {c: (ens.SHARE_FLOOR if c == ens.FORENSIC else 0.2)
                        for c in ens.COMMITTEES}}
    per = {c: {"measured": 50, "seconds": 10.0, "unique": 5, "fails": 10}
           for c in ens.COMMITTEES}
    per[ens.FORENSIC] = {"measured": 50, "seconds": 10.0, "unique": 0, "fails": 0}
    for d in range(ce.RETIRE_WINDOW_DAYS - 1):
        ens._reweight(state, per, _day(d))
        assert ens.FORENSIC not in state["retired_committees"]
    ens._reweight(state, per, _day(ce.RETIRE_WINDOW_DAYS - 1))
    assert ens.FORENSIC in state["retired_committees"]
    # It keeps running at the floor as a probe; a unique catch re-admits it.
    per[ens.FORENSIC] = {"measured": 50, "seconds": 10.0, "unique": 3, "fails": 3}
    ens._reweight(state, per, _day(ce.RETIRE_WINDOW_DAYS))
    assert ens.FORENSIC not in state["retired_committees"]


def test_a_certified_survivors_red_team_claim_is_not_scored_by_its_certificate():
    state = ce.blank_state()
    ex = {"committee": ens.SCIENTIFIC, "key": "survivor:c1", "fingerprint": "f",
          "keys": {"cell": "n1"},
          "results": [{"specialist": "cost_surface", "verdict": ce.FAIL, "strength": 0.9,
                       "cost_s": 0.0}]}
    ce.update_state(state, [ex], {})
    assert ce.settle(state, ens._outcome_fn([], {"n1": {"fate": "CERTIFIED"}})) == 0
    assert ce.settle(state, ens._outcome_fn([], {"n1": {"fate": "FAILED"}})) == 1
    assert state["seats"]["cost_surface"]["brier_sum"] == pytest.approx(0.05 ** 2)


def test_every_seat_is_scored_on_its_traps_as_ground_truth():
    state = ce.blank_state()
    ce.update_state(state, [], {"a": {"trap": ce.FAIL, "trap_strength": 0.9, "caught": True,
                                      "clean": ce.PASS, "clean_strength": 0.8,
                                      "false_alarm": False}})
    s = state["seats"]["a"]
    assert s["trap_settled"] == 2
    assert s["trap_brier_sum"] == pytest.approx(0.05 ** 2 + 0.1 ** 2)
    assert ce.calibrated_weight(state, "a") > 0.99


def test_falsifier_looks_are_charged_once_over_the_union(desk, monkeypatch):
    monkeypatch.setattr(ens, "TRIAL_UNION", desk / "committees" / "union.txt")
    monkeypatch.setattr(ens, "TRIAL_DONATIONS", desk / "intelligence" / "committee_ensembles")
    ex = [{"committee": ens.SCIENTIFIC, "key": "g", "keys": {"cell": "n1"},
           "results": [{"specialist": "cost_surface", "verdict": ce.PASS},
                       {"specialist": "truncation", "verdict": ce.UNMEASURED},
                       {"specialist": "mechanism_named", "verdict": ce.PASS}]}]
    assert ens._charge_trials(ex, True)["new_in_union"] == 1
    assert ens._charge_trials(ex, True)["new_in_union"] == 0
    files = list((desk / "intelligence" / "committee_ensembles").glob("discoveries_*.json"))
    doc = json.loads(files[0].read_text())
    assert doc["tests_run"] == 1 and doc["discoveries"] == []


def test_read_health_is_never_healthy_when_absent_or_stale(tmp_path):
    p = tmp_path / "h.json"
    assert ens.read_health(p)["verdict"] == ce.UNMEASURED
    at = datetime(2026, 9, 30, 12, tzinfo=UTC)
    p.write_text(json.dumps({"generated_utc": at.isoformat(), "committees": {
        c: {"verdict": "HEALTHY"} for c in ens.COMMITTEES}}))
    assert ens.read_health(p, now=at + timedelta(hours=1))["verdict"] == "HEALTHY"
    assert ens.read_health(p, now=at + timedelta(hours=5))["verdict"] == "STALE"


def test_the_six_run_every_hour():
    src = (_DESK / "research" / "hourly_cycle.py").read_text()
    assert ('"committee_ensembles", "research/committee_ensembles.py", "--once", '
            '"--budget-s", "300"') in src
    assert '"committee_ensembles": cme' in src
    from libs.research import layers
    assert layers.LEG_LAYER["committee_ensembles"] == "prediction"


def test_the_gauntlets_survivors_are_red_teamed_first_from_l1(monkeypatch):
    import types
    fake = types.SimpleNamespace(load_certificates=lambda: (
        {"c1": {"shadow_spec": {"symbol": "EURUSD", "family": "carry", "params": {"k": 1}}},
         "c2": {"shadow_spec": {}}}, "stub"))
    monkeypatch.setitem(sys.modules, "falsifier_run", fake)
    subs = ens.survivor_subjects()
    assert [s.key for s in subs] == ["survivor:c1"] and subs[0].level == 1
    assert subs[0].committee == ens.SCIENTIFIC and "mechanism" not in subs[0].evidence
    state = ce.blank_state()
    bank = ce.Subject(ens.SCIENTIFIC, "b", {"mechanism": {"note": ""}})
    subs[0].evidence["cell"] = ens._momentum_cell(12)
    ex, _counts = ens._examine_committee(ens.SCIENTIFIC, [bank, subs[0]], state, 60.0, 0.0)
    assert ex[0]["key"] == "survivor:c1" and ex[0]["levels"][0] == 1


def test_dead_organs_never_judges_the_desk_from_a_non_trading_hosts_attestation():
    sp = next(s for s in ens.SEATS if s.name == "dead_organs")
    census = {"LIVE": 126, "NEVER": 715, "MISSING": 47}
    r = ce.run_seat(sp, {"program": {"census": census, "host_role": "non_trading_host"}}, "p")
    assert r.verdict == ce.UNMEASURED
    r = ce.run_seat(sp, {"program": {"census": census, "host_role": "trading_host"}}, "p")
    assert r.verdict == ce.FAIL
