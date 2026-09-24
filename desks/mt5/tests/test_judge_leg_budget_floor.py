"""A price may lengthen the judge's leg. It may never cut it short of the judge's own stop.

MEASURED ON THE TRADING BOX 2026-09-24, from `data/compute_ledger.jsonl`. Every
`external_gauntlet` row over two days:

    09-23  19:12 TIMEOUT 1,102s   20:24 TIMEOUT 1,101s   21:33 TIMEOUT 1,100s
           22:50 TIMEOUT 1,100s
    09-24  00:36 exit -1 2,724s   02:27 exit -1 1,569s   04:02 TIMEOUT 4,581s
           06:43 exit -1   414s   08:10 exit -1   866s   09:40 exit -1   760s
           11:10 exit  1  2,358s

ZERO successful outcomes on 18, 19, 20, 22, 23 and 24 September. The four 1,100-second rows are
`LEG_BUDGET_SEC["external_gauntlet"] = 3000` after `cycle_pricing.applied_budget` multiplied it
by a rank factor near 0.37 -- and 1,100 is 41% of `FRESH_BUILD_BUDGET_SEC`, the point where the
sealed judge STOPS building and writes `universal_gates_external.json`. The judge was being
killed before it could write, every hour, and the leg reported TIMEOUT, which reads as "slow"
and was "structurally unable to finish".

`cycle_pricing` floors a priced budget only at `SCOUT_MIN_S`, so every "the cap sits above the
organ's own budget" comment in `LEG_BUDGET_SEC` could be undone by one hour's rank.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

_DESK = Path(__file__).resolve().parents[1]
for _p in (str(_DESK / "research"), str(_DESK)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import hourly_cycle as hc  # noqa: E402

PRICING = (_DESK / "research" / "cycle_pricing.py").read_text("utf-8")
SEALED = (_DESK / "scripts" / "external_gauntlet.py").read_text("utf-8")


def test_the_pricer_still_has_no_floor_of_its_own() -> None:
    """The reason this floor lives in the cycle: the pricer bounds every leg at one scout
    minimum and knows nothing about any organ's own stopping point."""
    assert "applied = max(SCOUT_MIN_S, round(base_i * factor))" in PRICING


def test_the_floor_is_the_sealed_judges_own_build_budget() -> None:
    assert hc.LEG_BUDGET_FLOOR_SEC["external_gauntlet"] == 2_700
    assert 'os.environ.get("GAUNTLET_FRESH_BUDGET_SEC", "2700")' in SEALED, \
        "the sealed default moved; re-read the floor rather than assuming it"


def test_the_floor_follows_the_budget_that_was_actually_applied(
        monkeypatch: pytest.MonkeyPatch) -> None:
    """`judging_throughput.apply_env` puts the measured budget in this process's environment
    before the judge's leg runs; the floor reads it there rather than repeating a number."""
    monkeypatch.delenv("GAUNTLET_FRESH_BUDGET_SEC", raising=False)
    assert hc._leg_floor_s("external_gauntlet") == 2_700
    monkeypatch.setenv("GAUNTLET_FRESH_BUDGET_SEC", "8640")
    assert hc._leg_floor_s("external_gauntlet") == 8_640
    # ONE WAY ONLY: a smaller or unreadable value never lowers the sealed default.
    monkeypatch.setenv("GAUNTLET_FRESH_BUDGET_SEC", "600")
    assert hc._leg_floor_s("external_gauntlet") == 2_700
    monkeypatch.setenv("GAUNTLET_FRESH_BUDGET_SEC", "not a number")
    assert hc._leg_floor_s("external_gauntlet") == 2_700


def test_no_other_leg_gains_a_floor_by_accident() -> None:
    assert hc._leg_floor_s("weak_signals") == 0
    assert set(hc.LEG_BUDGET_FLOOR_SEC) == {"external_gauntlet"}


def test_the_base_budget_covers_a_measured_full_pass() -> None:
    """A cold full pass measures ~134 minutes (8,040 s). 3,000 could not finish one even before
    the pricer touched it."""
    assert hc.LEG_BUDGET_SEC["external_gauntlet"] >= 8_040
    assert hc.LEG_BUDGET_SEC["external_gauntlet"] >= hc.LEG_BUDGET_FLOOR_SEC["external_gauntlet"]


def test_the_floor_is_applied_between_the_price_and_the_run() -> None:
    src = (_DESK / "research" / "hourly_cycle.py").read_text("utf-8")
    body = src[src.index("def _producer_impl("):src.index("def execution_twin(")]
    price = body.index("budget, _price_rec = _priced_budget(")
    floor = body.index("_floor = _leg_floor_s(name)")
    run = body.index("timeout=budget")
    assert price < floor < run
    assert "if _floor and budget < _floor:" in body
    # the record says the floor bound, so a reader can tell a floored hour from a priced one
    assert '"floor_s": _floor, "priced_s": budget' in body


def test_the_publication_leg_has_room_for_the_recovery_it_now_does() -> None:
    """`canon_publication` reads the judge's 88 MB gate output and streams the docket for the
    params of the cells it is recovering, under its own 240 s budget."""
    import canon_publication as cp
    assert hc.LEG_BUDGET_SEC["canon_publication"] > cp.RECOVERY_BUDGET_SEC
