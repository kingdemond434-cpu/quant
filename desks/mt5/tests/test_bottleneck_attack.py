"""THE 24/7 MAXIMISER: one binding constraint, named from measurement, funded through the
machinery that already exists.

What these pin:
  * each of the four bottlenecks is measured from a PEER artifact, with a named fallback, and an
    absent peer is UNMEASURED rather than zero (L1.28a) -- a bottleneck nobody measured cannot be
    reported as solved;
  * plumbing past its escalation window binds outright, because every other measurement is then a
    measurement of a stopped machine;
  * every shift is >= 1.0. This organ has no instrument for starving a department, and a test
    fails the moment one is added (growth governance Rule 2 / never reduce aggressiveness);
  * the shift actually REACHES the budget: `research_auction` blends it with `bottleneck_law`'s
    by MAXIMUM, and the auction's factors are what `research_budget.budget_s` multiplies;
  * the trend is derived from a real history file and says UNMEASURED on the first pass rather
    than inventing a direction.
"""
from __future__ import annotations

import json
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

DESK = Path(__file__).resolve().parents[1]
ROOT = DESK.parents[1]
for p in (str(DESK), str(DESK / "research"), str(ROOT)):
    if p not in sys.path:
        sys.path.insert(0, p)

from desks.mt5.research import bottleneck_attack as ba  # noqa: E402

NOW = datetime(2026, 9, 23, 12, 0, tzinfo=UTC)


def _reports(tmp_path: Path) -> Path:
    d = tmp_path / "desks" / "mt5" / "reports"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _write(d: Path, name: str, doc: object) -> None:
    (d / name).write_text(json.dumps(doc), encoding="utf-8")


# ------------------------------------------------------------------------------- measurement
def test_conversion_debt_reads_the_peer_organ_when_it_has_landed(tmp_path: Path) -> None:
    _write(_reports(tmp_path), "CONVERSION_MAXIMISER.json",
           {"debt_after": {"total_debt": 4000, "components": {"unprocessed_forever": 4000}},
            "new_cells": 0})
    row = ba.measure_conversion_debt(tmp_path)
    assert row["source"] == "reports/CONVERSION_MAXIMISER.json"
    assert row["value"] == 4000 and 0.0 < row["severity"] < 1.0


def test_an_absent_peer_is_unmeasured_never_zero(tmp_path: Path) -> None:
    _reports(tmp_path)
    for row in (ba.measure_judging(tmp_path), ba.measure_enrolment(tmp_path),
                ba.measure_plumbing(tmp_path)):
        assert row["severity"] is None, row["bottleneck"]
        assert row["status"] == "UNMEASURED"
        assert row["basis"], "an UNMEASURED verdict must name why"


def test_judging_is_priced_in_hours_of_queue_at_the_measured_rate(tmp_path: Path) -> None:
    _write(_reports(tmp_path), "GAUNTLET_BACKPRESSURE.json",
           {"windows": {"24h": {"testing": {"per_hour": 100.0, "pass_rate": 0.1},
                                "backlog": {"born_minus_judged": 4800}}}})
    row = ba.measure_judging(tmp_path)
    assert row["value"] == 48.0                      # 4800 cells at 100/h
    assert row["severity"] == round(48.0 / (48.0 + 24.0), 4)


def test_a_judge_ahead_of_the_births_is_not_binding(tmp_path: Path) -> None:
    _write(_reports(tmp_path), "GAUNTLET_BACKPRESSURE.json",
           {"windows": {"24h": {"testing": {"per_hour": 100.0},
                                "backlog": {"born_minus_judged": -2400}}}})
    row = ba.measure_judging(tmp_path)
    assert row["severity"] == 0.0
    assert "AHEAD" in row["basis"]


def test_enrolment_falls_back_to_the_latency_stage_the_desk_already_publishes(
        tmp_path: Path) -> None:
    _write(_reports(tmp_path), "RESEARCH_LATENCY.json",
           {"stages": [{"stage": "certified->forward", "median_h": 72.0, "p90_h": 200.0,
                        "n": 9}]})
    row = ba.measure_enrolment(tmp_path)
    assert row["value"] == 72.0 and row["source"] == "reports/RESEARCH_LATENCY.json"
    assert row["severity"] == round(72.0 / 96.0, 4)


def test_an_untimed_enrolment_stage_with_a_visible_queue_is_still_measured(
        tmp_path: Path) -> None:
    """A median nobody computed is not the same fact as a queue nobody is draining."""
    _write(_reports(tmp_path), "FORWARD_SLOT_RANKER.json", {"n_waiting": 40})
    row = ba.measure_enrolment(tmp_path)
    assert row["severity"] is not None and row["value"] == 40
    assert "UNMEASURED" in row["basis"]


def test_plumbing_past_its_window_scores_one_and_binds_outright(tmp_path: Path) -> None:
    d = _reports(tmp_path)
    _write(d, "PLUMBING_WATCHDOG.json", {"n_defects": 1, "n_past_escalation_window": 1,
                                         "at": NOW.isoformat()})
    _write(d, "CONVERSION_MAXIMISER.json", {"debt_after": {"total_debt": 10_000_000}})
    rows = [ba.measure_conversion_debt(tmp_path), ba.measure_judging(tmp_path),
            ba.measure_enrolment(tmp_path), ba.measure_plumbing(tmp_path)]
    assert ba.measure_plumbing(tmp_path)["severity"] == 1.0
    bind = ba.binding(rows)
    assert bind["bottleneck"] == "plumbing_defects" and bind["owner"] == "meta"


def test_open_defects_under_the_window_are_scored_but_do_not_dominate(tmp_path: Path) -> None:
    _write(_reports(tmp_path), "PLUMBING_WATCHDOG.json",
           {"n_defects": 2, "n_past_escalation_window": 0})
    row = ba.measure_plumbing(tmp_path)
    assert row["severity"] == round(2.0 / 12.0, 4)


# --------------------------------------------------------------------------- binding and shift
def test_the_binding_one_is_the_highest_severity() -> None:
    rows = [ba._row("conversion_debt", severity=0.2, value=1, unit="u", basis="b", source="s"),
            ba._row("judging_throughput", severity=0.9, value=1, unit="u", basis="b", source="s"),
            ba._row("enrolment_latency", severity=None, value="UNMEASURED", unit="u", basis="b",
                    source="s"),
            ba._row("plumbing_defects", severity=0.1, value=1, unit="u", basis="b", source="s")]
    bind = ba.binding(rows)
    assert bind["bottleneck"] == "judging_throughput" and bind["owner"] == "validate"
    assert bind["unmeasured"] == ["enrolment_latency"]


def test_a_tie_goes_upstream_because_relieving_a_starved_stage_moves_nothing() -> None:
    rows = [ba._row("conversion_debt", severity=0.5, value=1, unit="u", basis="b", source="s"),
            ba._row("enrolment_latency", severity=0.5, value=1, unit="u", basis="b", source="s")]
    assert ba.binding(rows)["bottleneck"] == "conversion_debt"


def test_an_all_unmeasured_desk_has_a_binding_constraint_and_it_is_the_measuring() -> None:
    rows = [ba._row(n, severity=None, value="UNMEASURED", unit="u", basis="b", source="absent")
            for n in ba.OWNER]
    bind = ba.binding(rows)
    assert bind["bottleneck"] == "UNMEASURED"
    assert "measurement" in bind["why"]


def test_no_shift_is_ever_below_one_this_organ_cannot_starve_anything() -> None:
    for sev in (0.0, 0.25, 0.5, 0.99, 1.0):
        for name, owner in ba.OWNER.items():
            shift = ba.compute_shift({"bottleneck": name, "owner": owner, "severity": sev})
            assert min(shift.values()) >= 1.0, (name, sev, shift)
            assert shift[owner] == round(min(ba.MAX_SHIFT, 1.0 + sev), 3)
            assert max(shift.values()) <= ba.MAX_SHIFT


def test_an_unmeasured_binding_constraint_moves_nothing_rather_than_guessing() -> None:
    assert set(ba.compute_shift({"severity": None}).values()) == {1.0}


# --------------------------------------------------------------------------------- the trend
def test_the_trend_answers_is_it_getting_better(tmp_path: Path) -> None:
    h = tmp_path / "hist.jsonl"
    rows_then = [ba._row("conversion_debt", severity=0.8, value=9, unit="u", basis="b",
                         source="s")]
    ba.append_history(rows_then, {"bottleneck": "conversion_debt"}, NOW - timedelta(hours=20), h)
    rows_now = [ba._row("conversion_debt", severity=0.3, value=3, unit="u", basis="b",
                        source="s")]
    tr = ba.trend(rows_now, NOW, h)
    assert tr["conversion_debt"]["direction"] == "improving"
    assert tr["conversion_debt"]["delta"] == -0.5
    assert tr["samples"] == 1


def test_a_first_pass_has_no_trend_and_says_so(tmp_path: Path) -> None:
    rows = [ba._row("plumbing_defects", severity=0.4, value=4, unit="u", basis="b", source="s")]
    tr = ba.trend(rows, NOW, tmp_path / "absent.jsonl")
    assert tr["plumbing_defects"]["direction"] == "UNMEASURED"
    assert tr["samples"] == 0


def test_a_sample_older_than_the_window_is_not_the_comparison(tmp_path: Path) -> None:
    h = tmp_path / "hist.jsonl"
    old = [ba._row("plumbing_defects", severity=0.9, value=9, unit="u", basis="b", source="s")]
    ba.append_history(old, {"bottleneck": "plumbing_defects"}, NOW - timedelta(days=5), h)
    tr = ba.trend(old, NOW, h)
    assert tr["samples"] == 0 and tr["plumbing_defects"]["direction"] == "UNMEASURED"


# ------------------------------------------------------------------- the pass, and the wiring
def test_the_pass_publishes_the_binding_constraint_and_what_it_moved(tmp_path: Path) -> None:
    d = _reports(tmp_path)
    _write(d, "PLUMBING_WATCHDOG.json", {"n_defects": 0, "n_past_escalation_window": 0})
    _write(d, "GAUNTLET_BACKPRESSURE.json",
           {"windows": {"24h": {"testing": {"per_hour": 10.0},
                                "backlog": {"born_minus_judged": 1000}}}})
    doc = ba.run(budget_s=10.0, root=tmp_path, now=NOW, write=False,
                 history=tmp_path / "h.jsonl")
    assert doc["binding"]["bottleneck"] == "judging_throughput"
    assert doc["compute_shift"]["validate"] > 1.0
    assert len(doc["bottlenecks"]) == 4
    assert doc["moved"]["consumers"], "an organ must name who reads what it wrote"
    assert "trend_24h" in doc and doc["n_unmeasured"] >= 0


def test_the_shift_reaches_the_budget_through_the_auction_by_maximum_never_minimum() -> None:
    """`research_auction.build(bottleneck=...)` is what feeds `research_budget.budget_s`. Two
    demand signals for one auction blend by MAXIMUM: a department two organs both call starved is
    not funded less because one of them is more cautious about it."""
    src = (ROOT / "desks/mt5/research/research_auction.py").read_text(encoding="utf-8")
    assert "BOTTLENECK_ATTACK.json" in src
    assert "_attack" in src and "max(float(_merged.get(" in src
    i_read = src.index("_attack = _read(ATTACK)")
    i_bids = src.index("rows = bids(departments")
    assert i_read < i_bids, "the blend must happen before the bids are taken"


def test_the_organ_never_writes_a_peers_artifact() -> None:
    """conversion_maximiser, judging_throughput and the forward enrolment organ belong to other
    builders; compute_policy has exactly one writer. Consuming is the whole contract."""
    src = (ROOT / "desks/mt5/research/bottleneck_attack.py").read_text(encoding="utf-8")
    assert 'OUT = REPORTS / "BOTTLENECK_ATTACK.json"' in src
    for foreign in ("CONVERSION_MAXIMISER.json", "JUDGING_THROUGHPUT.json",
                    "GAUNTLET_BACKPRESSURE.json", "RESEARCH_LATENCY.json",
                    "compute_policy.json", "BOTTLENECK_LAW.json"):
        assert f'write_report({foreign}' not in src
        assert f'"{foreign}").write_text' not in src


def test_every_bottleneck_has_an_owning_department_the_auction_can_price() -> None:
    from desks.mt5.research.research_auction import DEFAULT_DEPARTMENTS
    for name, owner in ba.OWNER.items():
        assert owner in DEFAULT_DEPARTMENTS, f"{name} is owned by a department nobody prices"
