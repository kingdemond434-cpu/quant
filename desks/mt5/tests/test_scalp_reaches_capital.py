"""A matured scalp clock can become LIVE. Until 2026-09-05 it could not, ever.

THE DEFECT, in one line: `pf_allocator.py` did not contain the string "scalp" anywhere, so no
scalp sleeve had ever been priced. Follow that through the promoter and the lane is a dead end by
construction, with every artifact reading healthy the whole way down:

    scalp_shadow      matures a clock to PROMOTION_CANDIDATE on 50 forward trades, positive
                      expectancy, inside its drawdown bound
    promote_scalp     builds the exact recipe off the clock and asks `capital_verdict`
    admission_of      finds no allocator row answering to the sleeve, and returns (None, "not in
                      the priced universe") -- which is CORRECT: nobody had looked
    capital_verdict   UNMEASURED, because an unmeasured marginal is not a positive one
    _door_status      writes LIVE only on a MEASURED admission -> STANDBY

So a scalp sleeve with a perfect forward record lands on the roster at STANDBY and stays there
for ever. The promoter logs PROMOTED, the clock reads PROMOTION_CANDIDATE, the allocator says
nothing at all, and no line anywhere says "this can never become live".

IT IS THE SAME DEFECT AS THE 65 UNEXECUTABLE CERTIFICATES, one lane over: evidence matures, and
the path from evidence to capital was never wired. `certified_evidence`'s own docstring records
the first instance of it -- "the overlap is zero ... a certified sleeve could not be funded
because it was never priced". This is the third.

WHAT IS NOT CHANGED, and must not be: the gates, the bar, or who decides. `scalp_evidence` prices
the lane's FORWARD ledger only -- the historical rows that selected the spec are excluded, because
pricing a sleeve on the evidence that chose it is the overfit the whole gauntlet exists to refuse
-- and the allocator's dE[log W] still decides whether the sleeve gets heat. A refusal on that
basis is a capital judgement and stays. What ends is the silence.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

_DESK = Path(__file__).resolve().parents[1]
for _p in (str(_DESK), str(_DESK / "research"), str(_DESK.parent.parent)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

pa = pytest.importorskip("pf_allocator")
pr = pytest.importorskip("promoter")

_NAME = "XAUUSD_M5_gold_scalp_london"


def _ledger(shadow: Path, name: str, *, forward: int = 25, historical: int = 30) -> Path:
    rows = [{"r": 0.4, "entry_time": f"2026-08-{(d % 28) + 1:02d}T09:{d % 60:02d}:00",
             "exit_time": f"2026-08-{(d % 28) + 1:02d}T10:{d % 60:02d}:00", "phase": "forward"}
            for d in range(forward)]
    rows += [{"r": 9.9, "entry_time": "2026-07-01T09:00:00", "phase": "historical"}
             for _ in range(historical)]
    path = shadow / f"ledger_{name}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(rows), "utf-8")
    return path


@pytest.fixture
def shadow(tmp_path, monkeypatch):
    """A stand-in desk root, so the reader is exercised without touching the real reports."""
    base = tmp_path / "desk"
    (base / "reports" / "shadow").mkdir(parents=True)
    monkeypatch.setattr(pa, "BASE", base)
    return base / "reports" / "shadow"


class TestTheScalpLaneIsPricedAtAll:
    def test_a_forward_ledger_becomes_a_daily_series(self, shadow) -> None:
        _ledger(shadow, _NAME)
        series, acct = pa.scalp_evidence()
        assert acct["priced"] == 1 and acct["ledgers"] == 1
        assert _NAME in series, "the scalp clock is still not in the priced universe"
        assert len(series[_NAME]) >= 2

    def test_historical_trades_are_excluded_from_the_price(self, shadow) -> None:
        """The rows that SELECTED the spec are in-sample for this lane. Pricing a sleeve on the
        evidence that chose it is the overfit the ten gates exist to refuse -- and here it would
        also be enormous: the fixture's historical rows carry 9.9R each against 0.4R forward."""
        _ledger(shadow, _NAME, forward=25, historical=30)
        series, _ = pa.scalp_evidence()
        assert series[_NAME].sum() == pytest.approx(25 * 0.4)

    def test_the_series_is_date_indexed_so_the_bootstrap_can_align_it(self, shadow) -> None:
        """`sample_worlds` stacks sleeves by POSITION. A series on its own clock pairs a scalp
        Tuesday with a gold Thursday and manufactures diversification that does not exist --
        measured once already at a reported 2.8e14% annual growth."""
        _ledger(shadow, _NAME)
        series, _ = pa.scalp_evidence()
        idx = list(series[_NAME].index)
        assert idx == sorted(idx)
        assert all(hasattr(d, "year") for d in idx), "the index is not dates"

    def test_trades_on_the_same_day_are_summed_not_listed(self, shadow) -> None:
        """A scalp lane takes several trades a day by construction; one row per trade would give
        the allocator a series whose 'days' are not days."""
        path = shadow / f"ledger_{_NAME}.json"
        path.write_text(json.dumps([
            {"r": 0.5, "exit_time": "2026-08-03T09:00:00", "phase": "forward"},
            {"r": 0.25, "exit_time": "2026-08-03T14:00:00", "phase": "forward"},
            {"r": -0.1, "exit_time": "2026-08-04T09:00:00", "phase": "forward"},
        ]), "utf-8")
        series, _ = pa.scalp_evidence()
        assert len(series[_NAME]) == 2
        assert series[_NAME].iloc[0] == pytest.approx(0.75)


class TestItRefusesRatherThanInventing:
    def test_a_clock_with_one_forward_day_is_refused_by_name(self, shadow) -> None:
        _ledger(shadow, _NAME, forward=1, historical=50)
        series, acct = pa.scalp_evidence()
        assert _NAME not in series
        assert "forward day" in acct["refused"][_NAME]

    def test_a_clock_with_no_forward_trades_at_all_is_refused(self, shadow) -> None:
        _ledger(shadow, _NAME, forward=0, historical=50)
        series, acct = pa.scalp_evidence()
        assert _NAME not in series and _NAME in acct["refused"]

    def test_an_unreadable_ledger_is_named_not_skipped(self, shadow) -> None:
        (shadow / f"ledger_{_NAME}.json").write_text("{not json", "utf-8")
        series, acct = pa.scalp_evidence()
        assert _NAME not in series and _NAME in acct["refused"]

    def test_an_absent_shadow_directory_reports_the_path(self, tmp_path, monkeypatch) -> None:
        monkeypatch.setattr(pa, "BASE", tmp_path / "nothing")
        series, acct = pa.scalp_evidence()
        assert series == {} and "absent on this host" in acct["refused"]["shadow"]

    def test_rows_without_a_timestamp_or_an_r_are_dropped_not_guessed(self, shadow) -> None:
        (shadow / f"ledger_{_NAME}.json").write_text(json.dumps([
            {"r": 0.5, "exit_time": "2026-08-03T09:00:00", "phase": "forward"},
            {"r": 0.5, "phase": "forward"},                       # no stamp
            {"exit_time": "2026-08-04T09:00:00", "phase": "forward"},   # no r
            {"r": 0.5, "exit_time": "2026-08-05T09:00:00", "phase": "forward"},
        ]), "utf-8")
        series, _ = pa.scalp_evidence()
        assert series[_NAME].sum() == pytest.approx(1.0)


class TestTheJoinToThePromoterCloses:
    """The allocator pricing it is only half: the promoter has to FIND the row."""

    def test_the_allocator_name_is_the_key_the_promoter_joins_on(self, shadow) -> None:
        """`_join_keys` puts the raw sleeve name first, so naming the allocator's sleeve after the
        clock makes the most specific key match directly. A second naming convention here would
        reproduce the exact join failure this whole change removes."""
        _ledger(shadow, _NAME)
        series, _ = pa.scalp_evidence()
        (allocator_name,) = series
        assert allocator_name.lower() in pr._join_keys(
            _NAME, "XAUUSD", "gold_scalp", _NAME)

    def test_a_priced_admitted_scalp_reaches_LIVE(self) -> None:
        """END TO END on the promoter's own door. This is the assertion that was impossible
        before: an admitted scalp candidate produces status LIVE with real heat."""
        view = {"fresh": True,
                "candidates": pr._index({_NAME: {"symbol": "XAUUSD", "family": "gold_scalp",
                                                 "selector": _NAME, "admit": True,
                                                 "delta_elogw_per_day": 0.0004,
                                                 "heat_earned": 0.03,
                                                 "why": "raises robust growth"}})}
        cap = pr.capital_verdict(view, _NAME, symbol="XAUUSD", family="gold_scalp",
                                 selector=_NAME)
        assert cap["status"] == "LIVE", cap["why"]
        assert cap["risk_frac"] > 0
        assert pr._door_status(cap) == "LIVE"

    def test_an_unpriced_scalp_still_reads_UNMEASURED_and_never_LIVE(self) -> None:
        """THE OLD BEHAVIOUR, kept as the fence. If the allocator ever stops pricing the lane the
        symptom returns silently, so the distinction is pinned: not in the priced universe means
        UNMEASURED and STANDBY -- never LIVE, and never mistaken for a refusal."""
        cap = pr.capital_verdict({"fresh": True, "candidates": {}}, _NAME, symbol="XAUUSD",
                                 family="gold_scalp", selector=_NAME)
        assert cap["status"] == "UNMEASURED"
        assert pr._door_status(cap) == "STANDBY"
        assert "not in the priced universe" in cap["why"]

    def test_a_refusal_on_growth_is_a_refusal_and_says_so(self) -> None:
        """The gate that must STILL bind. A scalp the book does not want reads STANDBY on a
        measured judgement -- which is a different sentence from 'nobody looked', and only one of
        the two is a defect."""
        view = {"fresh": True,
                "candidates": pr._index({_NAME: {"symbol": "XAUUSD", "family": "gold_scalp",
                                                 "selector": _NAME, "admit": False,
                                                 "why": "does not raise robust growth"}})}
        cap = pr.capital_verdict(view, _NAME, symbol="XAUUSD", family="gold_scalp",
                                 selector=_NAME)
        assert cap["status"] == "STANDBY" and "standby on the current reading" in cap["why"]


def test_the_allocator_actually_calls_the_scalp_reader() -> None:
    """A function nothing calls is the defect in a new costume -- this desk has shipped that
    twice today already (the deepening worker, the clock healer)."""
    src = (_DESK / "research" / "pf_allocator.py").read_text("utf-8")
    code = "\n".join(ln for ln in src.splitlines() if not ln.lstrip().startswith("#"))
    assert "scalp, scalp_acct = scalp_evidence()" in code
    assert "align(align(daily, certified), scalp)" in code
    assert '"scalp_library": scalp_acct' in code
