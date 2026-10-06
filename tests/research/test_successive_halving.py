"""Successive halving: cheap rungs first, a rung that admits nothing stops the ladder and is
flagged, a predicate that raises is a bug and never a rejection, and a rung that kills a genuine
survivor is DEFECTIVE."""
from __future__ import annotations

import pytest

from libs.research import successive_halving as sh


def _rung(name: str, pred, cost: float, expected: float | None = None) -> sh.Rung:  # type: ignore[no-untyped-def]
    return sh.Rung(name=name, predicate=pred, cost_hint=cost, why="t", expected_survival=expected)


def test_ordering_names_every_expensive_rung_above_a_cheap_one() -> None:
    rungs = [_rung("cheap", bool, 1), _rung("dear", bool, 10), _rung("mid", bool, 5),
             _rung("dearer", bool, 20)]
    (problem,) = sh.check_ordering(rungs)
    assert "rung 2 'mid' (cost 5) is cheaper than rung 1 'dear' (cost 10)" in problem
    assert sh.check_ordering(rungs[:2]) == [] and sh.check_ordering([]) == []


def test_run_narrows_and_reports_each_toll() -> None:
    rungs = [_rung("even", lambda x: x % 2 == 0, 1, expected=0.5),
             _rung("big", lambda x: x >= 10, 2)]
    survivors, res = sh.run(range(20), rungs)
    assert survivors == [10, 12, 14, 16, 18]
    assert [(r.name, r.entered, r.survived, r.killed) for r in res] == [
        ("even", 20, 10, 10), ("big", 10, 5, 5)]
    assert res[0].survival_rate == 0.5 and res[0].note == "" and not res[0].suspicious


def test_far_from_expected_survival_is_noted_both_ways() -> None:
    _, low = sh.run(range(100), [_rung("r", lambda x: x < 5, 1, expected=0.5)])
    assert "far from the expected 0.500" in low[0].note          # 0.05 < 0.5 / 4
    _, high = sh.run(range(100), [_rung("r", lambda x: x < 90, 1, expected=0.1)])
    assert "far from the expected" in high[0].note               # 0.9 > 0.1 * 4
    _, ok = sh.run(range(100), [_rung("r", lambda x: x < 40, 1, expected=0.5)])
    assert ok[0].note == ""


def test_a_rung_that_admits_zero_stops_the_ladder_and_is_flagged() -> None:
    rungs = [_rung("none", lambda x: False, 1), _rung("never", lambda x: True, 2)]
    survivors, res = sh.run([1, 2, 3], rungs)
    assert survivors == [] and len(res) == 1
    assert res[0].suspicious and "admitted ZERO of 3" in res[0].note
    # without stop_on_empty the next rung records that it entered empty, then stops
    _, res2 = sh.run([1, 2, 3], rungs, stop_on_empty=False)
    assert [r.name for r in res2] == ["none", "never"]
    assert res2[1].entered == 0 and res2[1].suspicious and "entered empty" in res2[1].note


def test_empty_input_is_suspicious_not_a_clean_pass() -> None:
    survivors, res = sh.run([], [_rung("a", bool, 1)])
    assert survivors == [] and res[0].suspicious and res[0].survival_rate == 0.0


def test_a_raising_predicate_is_an_error_not_a_rejection() -> None:
    def boom(x: int) -> bool:
        raise ValueError("bad field")
    with pytest.raises(RuntimeError, match="rung 'boom' raised ValueError"):
        sh.run([1], [_rung("boom", boom, 1)])


def test_audit_rung_finds_false_kills_and_ignores_erroring_oracles() -> None:
    def oracle(x: int) -> bool:
        if x == 3:
            raise KeyError(x)
        return x > 4
    sound = sh.audit_rung([1, 2, 3], oracle)
    assert sound["verdict"] == "SOUND" and sound["false_kills"] == 0 and sound["checked"] == 3
    bad = sh.audit_rung([1, 5, 6, 7], oracle)
    assert bad["verdict"] == "DEFECTIVE" and bad["false_kills"] == 3
    assert bad["false_kill_rate"] == 0.75
    assert sh.audit_rung([], oracle)["false_kill_rate"] == 0.0
