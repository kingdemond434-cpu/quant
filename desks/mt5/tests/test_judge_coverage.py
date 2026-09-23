"""The judge covers every family that holds an unjudged cell, every hour, and the backlog falls."""
from __future__ import annotations

import json
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

DESK = Path(__file__).resolve().parents[1]
ROOT = DESK.parent.parent
for _p in (str(DESK), str(ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from research import judge_coverage as jc  # noqa: E402

sys.path.insert(0, str(ROOT / "scripts"))
import check_judge_coverage as fence  # noqa: E402

NOW = datetime(2026, 9, 23, 12, 0, tzinfo=UTC)


def _rows(spec: dict[str, int], *, age_h: float = 5.0) -> list[dict]:
    seen = (NOW - timedelta(hours=age_h)).isoformat()
    out: list[dict] = []
    for fam, n in spec.items():
        for i in range(n):
            out.append({"symbol": f"S{i}", "family": fam, "params": {"rr": 1.0 + i},
                        "first_seen": seen})
    return out


def test_allocate_gives_every_backlogged_family_a_share() -> None:
    """COVERAGE, NOT ROTATION: the nine-cell family is reached in the same hour as the 55,190."""
    quota = jc.allocate({"big": 55_190, "small": 9, "mid": 700}, capacity=1_000)
    assert set(quota) == {"big", "small", "mid"}
    assert all(v >= 1 for v in quota.values())
    assert quota["small"] <= 9, "a quota is a promise to drain, never a licence to re-judge"
    assert quota["big"] > quota["mid"] > 0, "the remainder is proportional to backlog"


def test_allocate_never_exceeds_a_family_backlog() -> None:
    quota = jc.allocate({"a": 3, "b": 2}, capacity=10_000)
    assert quota == {"a": 3, "b": 2}


def test_coverage_order_makes_every_prefix_family_balanced() -> None:
    """ORDER IS SELECTION: whatever prefix the judge's budget reaches carries every family."""
    rows = _rows({"big": 400, "small": 5, "mid": 60})
    quota = jc.allocate({"big": 400, "small": 5, "mid": 60}, capacity=100)
    ordered = jc.coverage_order(rows, quota)
    assert len(ordered) == len(rows), "no row is ever dropped by the ordering"
    head = {r["family"] for r in ordered[:100]}
    assert head == {"big", "small", "mid"}


def test_build_publishes_the_per_family_table(tmp_path: Path) -> None:
    ledger = tmp_path / "gate.jsonl"
    ledger.write_text(json.dumps({
        "at": (NOW - timedelta(minutes=10)).isoformat(), "cell": "S0.alpha.p=x",
        "family": "alpha", "passed": False, "terminal_gate": "in_sample_screen"}) + "\n", "utf-8")
    doc = jc.build(_rows({"alpha": 40, "beta": 6}), ledger=ledger,
                   ratchet=tmp_path / "absent.json", now=NOW)
    assert doc["verdict"] == "COVERED"
    for fam in ("alpha", "beta"):
        row = doc["families"][fam]
        assert row["mined"] > 0 and row["unjudged"] > 0 and row["queued"] > 0
        assert row["oldest_unjudged_age_h"] == pytest.approx(5.0, abs=0.05)
        assert row["window_h"] >= jc.WINDOW_H
    assert doc["totals"]["families_starved"] == 0


def test_a_not_run_deferral_is_not_a_verdict(tmp_path: Path) -> None:
    """The trap that starved 1,544 cells forever: a stamp is not a verdict."""
    ledger = tmp_path / "gate.jsonl"
    ledger.write_text(json.dumps({
        "at": NOW.isoformat(), "cell": "c1", "family": "alpha", "passed": None,
        "terminal_gate": None, "downstream_status": "NOT_RUN_BUILD_BUDGET_DEFERRED"}) + "\n",
        "utf-8")
    seen, total, window = jc.judged_index(ledger, now=NOW)
    assert seen == set() and total == {} and window == {}


def test_banned_family_gets_no_quota(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """The scarce judge is never allocated to a family that cannot reach the book."""
    monkeypatch.setattr(jc, "banned_from_capital", lambda: frozenset({"discovered"}))
    monkeypatch.setattr(jc, "STUDY_BANK", tmp_path / "none.json")
    doc = jc.build(_rows({"discovered": 500, "alpha": 20}), ledger=tmp_path / "no.jsonl",
                   ratchet=tmp_path / "no.json", now=NOW)
    assert doc["quota"].get("discovered") is None
    assert doc["families"]["discovered"]["judging_status"] == "STUDY_ONLY"
    assert doc["families"]["discovered"]["mined"] == 500, "mining stays unrestricted and counted"
    assert doc["totals"]["study_only_total"] == 500
    assert doc["totals"]["unjudged_total"] == 20


def test_order_docket_returns_every_row(tmp_path: Path) -> None:
    rows = _rows({"alpha": 30, "beta": 4})
    ordered, doc = jc.order_docket(list(rows), publish=False, now=NOW)
    assert len(ordered) == len(rows)
    assert all("_cell" not in r for r in ordered), "the internal identity never ships downstream"
    assert doc["totals"]["families_with_backlog"] >= 1


def test_fence_fails_a_starved_family(tmp_path: Path) -> None:
    report = tmp_path / "JUDGE_COVERAGE.json"
    report.write_text(json.dumps({
        "at": NOW.isoformat(),
        "families": {"alpha": {"unjudged": 900, "queued": 0, "judged_window": 0, "quota": 0,
                               "window_h": 1.0, "oldest_unjudged_age_h": 2.0}},
        "totals": {}}), "utf-8")
    doc = fence.judge(report, now=NOW)
    assert doc["verdict"] == "FAIL"
    assert "alpha" in doc["why"]


def _age_report(tmp_path: Path, **row: object) -> Path:
    report = tmp_path / "JUDGE_COVERAGE.json"
    base: dict[str, object] = {"unjudged": 40, "queued": 10, "judged_window": 12, "quota": 10,
                               "window_h": 4.0, "carried": 30, "prior_unjudged": 50}
    base.update(row)
    report.write_text(json.dumps({"at": NOW.isoformat(), "families": {"alpha": base},
                                  "totals": {}}), "utf-8")
    return report


def test_fence_fails_an_oldest_cell_that_did_not_move(tmp_path: Path) -> None:
    """Served this hour, past twice its own window, and the oldest still did not move."""
    doc = fence.judge(_age_report(tmp_path, oldest_unjudged_age_h=600.0,
                                  prior_oldest_age_h=599.0), now=NOW)
    assert doc["verdict"] == "FAIL"
    assert any(c["metric"] == "oldest_unjudged" and c["state"] == "FAIL" for c in doc["checks"])


def test_fence_does_not_fail_an_age_that_is_falling(tmp_path: Path) -> None:
    """An age rises with the clock; only its MOVEMENT is the desk's to control."""
    doc = fence.judge(_age_report(tmp_path, oldest_unjudged_age_h=300.0,
                                  prior_oldest_age_h=600.0), now=NOW)
    assert doc["verdict"] == "PASS"
    assert any(c["metric"] == "oldest_unjudged" and c["state"] == "WARN" for c in doc["checks"])


def test_fence_does_not_fail_an_age_on_its_first_reading(tmp_path: Path) -> None:
    """A metric enters at its measurement, never at an invented zero (L1.28a)."""
    doc = fence.judge(_age_report(tmp_path, oldest_unjudged_age_h=632.9), now=NOW)
    assert doc["verdict"] == "PASS"


def test_fence_fails_a_family_that_drained_nothing(tmp_path: Path) -> None:
    report = tmp_path / "JUDGE_COVERAGE.json"
    report.write_text(json.dumps({
        "at": NOW.isoformat(),
        "families": {"alpha": {"unjudged": 50, "queued": 10, "judged_window": 7, "quota": 10,
                               "window_h": 5.0, "oldest_unjudged_age_h": 2.0,
                               "carried": 50, "prior_unjudged": 50}},
        "totals": {}}), "utf-8")
    doc = fence.judge(report, now=NOW)
    assert doc["verdict"] == "FAIL"
    assert any(c["metric"] == "carried_backlog" and c["state"] == "FAIL"
               for c in doc["checks"])


def test_fence_is_unmeasured_when_nothing_was_judged(tmp_path: Path) -> None:
    """Nothing drained because nothing ran: that is the gauntlet's clock, not intake's failure."""
    report = tmp_path / "JUDGE_COVERAGE.json"
    report.write_text(json.dumps({
        "at": NOW.isoformat(),
        "families": {"alpha": {"unjudged": 50, "queued": 10, "judged_window": 0, "quota": 10,
                               "window_h": 5.0, "oldest_unjudged_age_h": 2.0,
                               "carried": 50, "prior_unjudged": 50}},
        "totals": {}}), "utf-8")
    doc = fence.judge(report, now=NOW)
    assert doc["verdict"] == "PASS"
    assert any(c["metric"] == "carried_backlog" and c["state"] == "UNMEASURED"
               for c in doc["checks"])


def test_fence_passes_when_the_backlog_fell(tmp_path: Path) -> None:
    report = tmp_path / "JUDGE_COVERAGE.json"
    report.write_text(json.dumps({
        "at": NOW.isoformat(),
        "families": {"alpha": {"unjudged": 30, "queued": 10, "judged_window": 20, "quota": 10,
                               "window_h": 3.0, "oldest_unjudged_age_h": 2.0,
                               "carried": 30, "prior_unjudged": 50, "drained": 20}},
        "totals": {}}), "utf-8")
    doc = fence.judge(report, now=NOW)
    assert doc["verdict"] == "PASS"


def test_fence_is_unmeasured_without_state(tmp_path: Path) -> None:
    doc = fence.judge(tmp_path / "absent.json", now=NOW)
    assert doc["verdict"] == "UNMEASURED"
    assert fence.judge(tmp_path / "absent.json", require_state=True, now=NOW)["verdict"] == "FAIL"


def test_live_family_names_covers_more_than_the_decorated_registry() -> None:
    """NO FIXED FAMILY SET: the live set is the union of every resolvable population."""
    from mt5desk.families import get_all_family_names, live_family_names
    live = set(live_family_names())
    assert live >= set(get_all_family_names())
    assert len(live) > len(get_all_family_names())


def test_the_floor_survives_the_value_ranking() -> None:
    """THE BREADTH MANDATE IS NOT NEGOTIABLE: value orders the remainder, never the floor."""
    backlog = {"rich": 900, "poor": 40, "tiny": 3}
    ranking = [{"family": "rich"}, {"family": "poor"}, {"family": "tiny"}]
    quota = jc.allocate(backlog, capacity=1_000, ranking=ranking)
    assert all(quota[f] >= 1 for f in backlog), "every family with backlog keeps a floor"
    assert quota["tiny"] == 3


def test_the_remainder_goes_down_the_ranking() -> None:
    """A lower-ranked family gets remainder only once every higher one is fully drained."""
    backlog = {"best": 500, "worst": 500}
    ranking = [{"family": "best"}, {"family": "worst"}]
    quota = jc.allocate(backlog, capacity=600, ranking=ranking)
    assert quota["best"] == 500, "the highest ev/judge-second family is drained first"
    assert quota["worst"] < quota["best"]


def test_an_unseen_family_ranks_on_the_optimistic_bound() -> None:
    """Optimism under uncertainty: a new family is explored, never buried at zero."""
    rows = _rows({"brand_new_family_xyz": 5})
    ranking = jc.rank_by_value({"brand_new_family_xyz": 5}, rows, capacity=100)
    assert ranking[0]["prior_status"] == "PRIOR"
    assert ranking[0]["p_optimistic"] > ranking[0]["p"]
    assert ranking[0]["ev_per_judge_second"] > 0


def test_bar_cost_makes_the_denominator_real() -> None:
    """A judge-second is spent in BARS: an M5 cell costs about twelve H1 cells."""
    h1 = jc.rank_by_value({"f": 1}, [{"family": "f", "params": {}}], capacity=100)[0]
    m5 = jc.rank_by_value({"f": 1}, [{"family": "f", "params": {"timeframe": "M5"}}],
                          capacity=100)[0]
    assert m5["cost_s_per_cell"] > 10 * h1["cost_s_per_cell"]
    assert m5["ev_per_judge_second"] < h1["ev_per_judge_second"]


def test_build_publishes_the_opportunity_cost(tmp_path: Path) -> None:
    doc = jc.build(_rows({"alpha": 40, "beta": 6}), ledger=tmp_path / "no.jsonl",
                   ratchet=tmp_path / "no.json", now=NOW)
    t = doc["totals"]
    for key in ("value_at_risk", "value_deferred", "value_forgone_per_hour", "hours_to_drain",
                "capacity_short"):
        assert key in t
    assert doc["value_ranking"] and doc["value_ranking"][0]["rank"] == 1


def test_learn_priors_charges_each_verdict_once(tmp_path: Path) -> None:
    """A posterior fed the same ledger twice is confident about nothing."""
    ledger = tmp_path / "gate.jsonl"
    ledger.write_text("".join(json.dumps({
        "at": f"2026-09-23T0{i}:00:00+00:00", "cell": f"c{i}", "family": "alpha",
        "passed": False, "terminal_gate": "in_sample_screen"}) + "\n" for i in range(3)), "utf-8")
    first = jc.learn_priors(ledger, since="", state_dir=tmp_path)
    assert first["recorded"] == 3 and first["families"] == 1
    again = jc.learn_priors(ledger, since=str(first["cursor"]), state_dir=tmp_path)
    assert again["recorded"] == 0, "the cursor stops a verdict being charged twice"


def test_fence_fails_a_remainder_that_ignored_the_ranking(tmp_path: Path) -> None:
    report = tmp_path / "JUDGE_COVERAGE.json"
    report.write_text(json.dumps({
        "at": NOW.isoformat(),
        "families": {"top": {"unjudged": 100, "queued": 5, "judged_window": 9, "quota": 5,
                             "window_h": 20.0, "oldest_unjudged_age_h": 1.0},
                     "low": {"unjudged": 100, "queued": 90, "judged_window": 9, "quota": 90,
                             "window_h": 2.0, "oldest_unjudged_age_h": 1.0}},
        "value_ranking": [
            {"family": "top", "rank": 1, "unjudged": 100, "quota": 5, "remainder": 0,
             "ev_per_judge_second": 9.0},
            {"family": "low", "rank": 2, "unjudged": 100, "quota": 90, "remainder": 85,
             "ev_per_judge_second": 1.0}],
        "totals": {}}), "utf-8")
    doc = fence.judge(report, now=NOW)
    assert doc["verdict"] == "FAIL"
    assert any(c["metric"] == "remainder_follows_ranking" and c["state"] == "FAIL"
               for c in doc["checks"])


def _gates(tmp_path: Path, *verdicts: dict) -> Path:
    p = tmp_path / "universal_gates_external.json"
    p.write_text(json.dumps({"verdicts": list(verdicts)}), "utf-8")
    return p


def test_every_unknown_gets_a_named_reason(tmp_path: Path) -> None:
    """The UNKNOWN class stops existing as a category: an unnamed terminal state IS the defect."""
    gates = _gates(
        tmp_path,
        {"cell": "A.f.p=1", "sym": "NOSUCHSYM", "family": "f", "days": 0, "unmeasured": True,
         "stages": {"observations": {"why": "no daily series"}}},
        {"cell": "B.f.p=2", "sym": "XAUUSD", "family": "f", "days": 0, "unmeasured": True,
         "stages": {"observations": {"why": "no daily series"}}},
        {"cell": "C.f.p=3", "sym": "XAUUSD", "family": "f", "days": 20, "unmeasured": True,
         "stages": {"observations": {"why": "only 20 daily observations"}}},
        {"cell": "D.f.p=4", "sym": "XAUUSD", "family": "f", "days": 900, "passed": True})
    named = jc.name_unknowns(gates)
    assert set(named) == {"A.f.p=1", "B.f.p=2", "C.f.p=3"}, "a judged cell is not an UNKNOWN"
    assert named["A.f.p=1"]["reason"] == "missing_bars"
    assert named["B.f.p=2"]["reason"] == "never_fires"
    assert named["C.f.p=3"]["reason"] == "too_rare"
    assert all(n["route"] for n in named.values()), "a named reason without an owner is a bucket"
    doc = jc.unknown_breakdown(gates)
    assert doc["unknown_total"] == 3 and doc["named_cells"] == 3
    assert doc["by_reason"] == {"missing_bars": 1, "never_fires": 1, "too_rare": 1}


def test_missing_bars_are_not_filtered_but_routed(tmp_path: Path) -> None:
    """A missing bar file is the conversion organ's gap to close, never a spec to park."""
    named = {"A": {"reason": "missing_bars", "sym": "NOSUCHSYM", "bar_bytes": 0},
             "B": {"reason": "never_fires", "sym": "NOSUCHSYM", "bar_bytes": 0}}
    bank = tmp_path / "bank.json"
    out = jc.update_unrunnable_bank(named, at="2026-09-23T12:00:00", path=bank)
    assert out["parked_this_pass"] == 1
    assert set(jc.unrunnable_bank(bank)) == {"B"}


def test_a_parked_cell_is_readmitted_when_its_bars_grow(tmp_path: Path) -> None:
    """A spec that never fired on a short history can fire on a longer one: a filter, not a ban."""
    bank = tmp_path / "bank.json"
    bank.write_text(json.dumps({"B": {"reason": "never_fires", "sym": "XAUUSD",
                                      "bar_bytes": -1}}), "utf-8")
    out = jc.update_unrunnable_bank({}, at="2026-09-23T13:00:00", path=bank)
    assert out["readmitted_on_bar_growth"] == 1
    assert jc.unrunnable_bank(bank) == {}


def test_fence_fails_an_unnamed_unknown(tmp_path: Path) -> None:
    report = tmp_path / "JUDGE_COVERAGE.json"
    report.write_text(json.dumps({
        "at": NOW.isoformat(),
        "families": {"a": {"unjudged": 1, "queued": 1, "judged_window": 1, "quota": 1,
                           "window_h": 1.0}},
        "totals": {"unknown_total": 100, "unknown_share": 0.5, "unknown_unnamed": 7}}), "utf-8")
    doc = fence.judge(report, now=NOW)
    assert doc["verdict"] == "FAIL"
    assert any(c["metric"] == "unknown_ratchet" and c["state"] == "FAIL" for c in doc["checks"])


def test_fence_fails_an_unknown_share_that_stalled(tmp_path: Path) -> None:
    report = tmp_path / "JUDGE_COVERAGE.json"
    report.write_text(json.dumps({
        "at": NOW.isoformat(),
        "families": {"a": {"unjudged": 1, "queued": 1, "judged_window": 1, "quota": 1,
                           "window_h": 1.0}},
        "totals": {"unknown_total": 100, "unknown_share": 0.5, "unknown_unnamed": 0,
                   "prior_unknown_share": 0.5, "unrunnable_bank": 40}}), "utf-8")
    doc = fence.judge(report, now=NOW)
    assert doc["verdict"] == "FAIL"
    assert any("stalled" in str(c.get("why")) for c in doc["checks"])


def test_fence_passes_an_unknown_share_that_fell(tmp_path: Path) -> None:
    report = tmp_path / "JUDGE_COVERAGE.json"
    report.write_text(json.dumps({
        "at": NOW.isoformat(),
        "families": {"a": {"unjudged": 1, "queued": 1, "judged_window": 1, "quota": 1,
                           "window_h": 1.0}},
        "totals": {"unknown_total": 10, "unknown_share": 0.1, "unknown_unnamed": 0,
                   "prior_unknown_share": 0.5, "unrunnable_bank": 40}}), "utf-8")
    assert fence.judge(report, now=NOW)["verdict"] == "PASS"


def test_an_unmeasured_verdict_moves_no_pass_probability(tmp_path: Path) -> None:
    """UNKNOWN is 'nobody looked', never evidence against the family (research_priors' own rule)."""
    ledger = tmp_path / "gate.jsonl"
    ledger.write_text(json.dumps({
        "at": "2026-09-23T01:00:00+00:00", "cell": "c1", "family": "alpha", "passed": False,
        "terminal_gate": "UNKNOWN"}) + "\n", "utf-8")
    jc.learn_priors(ledger, since="", state_dir=tmp_path)
    sys.path.insert(0, str(ROOT))
    from libs.research.research_priors import prior_for
    pr = prior_for("family", "alpha", state_dir=tmp_path)
    assert pr.mean == 0.5, "an unmeasured cell must not move the Beta"
    assert pr.outcomes.get("unmeasured", 0) > 0, "but it is recorded in the Dirichlet"
