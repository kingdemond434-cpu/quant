"""The graveyard records what a cell died of WITH the numbers, so a near miss is not a failure."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from libs.research import hypothesis_graph as hg  # noqa: E402

GATES = {
    "economic_prior": {"passed": True},
    "in_sample_screen": {"passed": True, "sharpe": 1.2},
    "deflated_sharpe": {"passed": False, "dsr": 0.94},
    "pbo": {"passed": True, "pbo": 0.21},
    "walk_forward": {"passed": False, "oos_sharpe": -0.1},
    "observations": {"passed": True, "days": 400},
}


def test_a_death_names_the_first_gate_that_refused_and_keeps_the_numbers() -> None:
    p = hg.death_profile(GATES, hg.FAILED)
    assert p["terminal_gate"] == "deflated_sharpe", "the ten-gate order decides, not dict order"
    assert p["failed"] == ["deflated_sharpe", "walk_forward"]
    assert p["passed"] == ["economic_prior", "in_sample_screen", "observations", "pbo"]
    assert p["readings"] == {"sharpe": 1.2, "dsr": 0.94, "pbo": 0.21,
                             "wf_oos_sharpe": -0.1, "days": 400.0}
    assert p["sample_days"] == 400.0 and p["n_gates"] == 6
    assert p["correlation_profile"].startswith("ABSENT")


def test_a_survivor_and_an_unjudged_cell_carry_no_death() -> None:
    assert hg.death_profile(GATES, hg.CERTIFIED) == {}
    assert hg.death_profile({}, hg.FAILED) == {}, "no gates is 'never judged', not 'died'"
    assert hg.death_profile(None, hg.FAILED) == {}


def test_the_row_carries_the_profile_only_when_it_died() -> None:
    dead = hg.Node(symbol="EURUSD", family="f", params={}, fate=hg.FAILED, gates=GATES).to_row()
    alive = hg.Node(symbol="EURUSD", family="f", params={}, fate=hg.CERTIFIED,
                    gates=GATES).to_row()
    assert dead["death"]["terminal_gate"] == "deflated_sharpe"
    assert "death" not in alive


def test_prior_failures_reports_how_close_the_region_came(tmp_path: Path) -> None:
    g = hg.Graph(tmp_path / "graph.jsonl")
    near = dict(GATES)
    far = {"economic_prior": {"passed": False}, "deflated_sharpe": {"passed": False, "dsr": 0.1}}
    # Two distinct cells inside ONE region: REGION_WIDTH buckets rr by 0.5, so 1.5 and 1.7 are
    # the same ground with different ids. The same id twice would supersede, not accumulate.
    g.append(hg.Node(symbol="EURUSD", family="f", params={"rr": 1.5}, fate=hg.FAILED, gates=near))
    g.append(hg.Node(symbol="EURUSD", family="f", params={"rr": 1.7}, fate=hg.FAILED, gates=far))
    pf = g.prior_failures("EURUSD", "f", {"rr": 1.5})
    assert pf["n_failed"] == 2 and pf["profiles"] == 2
    assert pf["terminal_gates"] == {"deflated_sharpe": 1, "economic_prior": 1}
    assert pf["best_readings"]["dsr"] == 0.94, "the region's BEST reading, not its last"
    untouched = g.prior_failures("XAUUSD", "f", {})
    assert untouched["n_failed"] == 0 and untouched["best_readings"] == {}


def test_an_old_row_without_a_death_block_is_still_profiled(tmp_path: Path) -> None:
    """Rows written before this landed carry `gates` and no `death`; the region query rebuilds
    the profile from the gates rather than reporting the history as unmeasured."""
    p = tmp_path / "graph.jsonl"
    g = hg.Graph(p)
    node = hg.Node(symbol="GBPJPY", family="f", params={}, fate=hg.FAILED, gates=GATES)
    row = node.to_row()
    row.pop("death")
    import json
    p.write_text(json.dumps(row) + "\n", "utf-8")
    g = hg.Graph(p)
    pf = g.prior_failures("GBPJPY", "f", {})
    assert pf["profiles"] == 1 and pf["terminal_gates"] == {"deflated_sharpe": 1}

def test_a_gate_that_refuses_without_a_number_is_still_the_terminal_gate() -> None:
    """REGRESSION: the gate order was derived from the readings table, which does not list
    `economic_prior` or `symbol_eligibility` -- so a cell rejected at Gate 1, before it was ever
    built, was reported as dying of its deflated Sharpe."""
    p = hg.death_profile({"economic_prior": {"passed": False},
                          "deflated_sharpe": {"passed": False, "dsr": 0.1}}, hg.FAILED)
    assert p["terminal_gate"] == "economic_prior"
    assert hg.GATE_ORDER.index("economic_prior") < hg.GATE_ORDER.index("deflated_sharpe")
