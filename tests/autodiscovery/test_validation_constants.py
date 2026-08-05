"""Constant-drift fences for the central validator's header constants (mutation survivors).

`data/mutation_score.json` (run 2026-07-30) records NINE surviving mutants against
`libs/autodiscovery/validation.py`, and every one of them is a numeric constant in the module
header: the annualisation factor and its multiplication, the DSR bar, the PBO bar, the desk-equity
fallback, the venue minimum notional, the execution-viability multiple, and the `> 0` guard on the
venue-truth rung of the equity ladder. Surviving means NO test pinned them -- any of those numbers
could have been edited, or the annualisation silently turned into a DIVISION, and the suite would
still have gone green.

WHAT THAT RUN IS AND IS NOT EVIDENCE OF. It was budget-truncated: 14 of 137 sites attempted, taken
in SOURCE ORDER, so the sample is a PREFIX of the file and not a sample at all. Its 35.7% kill rate
is therefore not a strength measurement of this module and is deliberately not treated as one here.
What IS evidence is the nine specific survivors -- those exact mutations were applied and no test
noticed. This file kills each of them.

VERIFIED TO BITE. Every test below was checked by applying its mutation to validation.py by hand,
observing the test FAIL, and reverting. A test that passes both before and after its mutation has
pinned nothing, so the verification is the deliverable, not the green run.

TIGHTEN-ONLY. Nothing here changes a threshold's value and nothing here relaxes a bar. Where a
constant is a declared policy number the test pins it AND says why that exact value is
load-bearing; where a constant has a behavioural consequence the test feeds data whose VERDICT
flips when the constant is wrong. A pin with no reason is a change-detector that the next person
deletes, and deleting it is the correct response to it.
"""

from __future__ import annotations

import inspect
import json
import math
from collections.abc import Iterator
from pathlib import Path

import numpy as np
import pytest

from libs.autodiscovery import validation as V
from libs.autodiscovery.models import Family, Hypothesis, ValidationVerdict
from libs.validation.campaign_window import CAMPAIGN_ALPHA
from libs.validation.dsr import sharpe_ratio
from libs.validation.economic_prior import MechanismType

#: A synthetic candidate. `failure_modes` is non-empty so the `economic_mechanism` gate passes and
#: the gate under test is the only thing deciding the assertion.
_HYP = Hypothesis(
    family=Family.LIQUIDITY, subtype="constant-pin", symbol="BTCUSDT", params={},
    mechanism=MechanismType.LIQUIDITY, edge_source="synthetic constant fence",
    failure_modes=["synthetic control -- never tradeable"],
)

#: Two peer Sharpes: `deflated_sharpe_ratio` needs >=2 estimates to form a variance. The value is
#: irrelevant on the per-candidate path, where the deflation is switched off (R0224).
_SHARPE_ESTIMATES = np.array([0.1, 0.2])


def _exact_sharpe_series(per_bar_sharpe: float, n: int = 300, seed: int = 11) -> np.ndarray:
    """A deterministic series whose PER-BAR Sharpe is exactly `per_bar_sharpe`.

    Standardising the draw first (mean 0, std 1 at ddof=1) makes mean/std land on the target to
    machine precision, so the DSR brackets below are reproducible rather than seed-lucky.
    """
    z = np.random.default_rng(seed).normal(0.0, 1.0, n)
    z = (z - z.mean()) / z.std(ddof=1)
    return np.asarray(z * 0.01 + per_bar_sharpe * 0.01, dtype="float64")


def _score(returns: np.ndarray, *, pc_pbo: float = 0.4, pc_p: float = 0.01) -> ValidationVerdict:
    """Run the REAL `validate()` on the per-candidate seam.

    `pc_pbo`/`pc_p` select the per-candidate path, which is the one production campaigns take and
    the one where DSR's multiplicity deflation is switched off (R0224) -- so the DSR the gate sees
    is the plain PSR of this series and the brackets below are exactly reproducible.
    """
    return V.validate(
        returns, hypothesis=_HYP, n_trials=1, sharpe_estimates=_SHARPE_ESTIMATES,
        returns_matrix=returns.reshape(-1, 1), pc_pbo=pc_pbo, pc_p=pc_p,
    )


@pytest.fixture
def isolated_equity(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[Path]:
    """Cut every rung of the equity ladder loose from the real desk.

    `_desk_equity_usd` reads the NAV chain through `live_book_usd` (ABSOLUTE path, so chdir does
    not mask it) and then two RELATIVE artifacts. Silencing the first and chdir'ing for the rest is
    what makes these tests about the constants rather than about whatever the book is today.
    """
    import libs.research.capacity_policy as cp
    monkeypatch.setattr(cp, "live_book_usd", lambda fallback=0.0, ledger=None: float(fallback))
    monkeypatch.chdir(tmp_path)
    yield tmp_path


class TestAnnualisationFactor:
    """`_PERIODS_PER_YEAR = 24 * 260` -- three survivors: `Mult -> Div`, `24 -> 25`, `260 -> 261`.

    The constant converts a PER-BAR Sharpe into an annual one at `validation.py:611`
    (`sharpe_ratio(arr) * np.sqrt(_PERIODS_PER_YEAR)`). It is 24 hourly bars x 260 trading days,
    and it is the ONLY frequency assumption in the validator -- `validate()` takes no frequency
    argument, so this number decides every `annual_sharpe` the desk stores
    (`libs/autodiscovery/memory.py:85`), reports and ranks rejects by
    (`scripts/run_rejection_rescore.py:107`).

    R0086 SEPARATELY FLAGS THIS CONSTANT as inflating annual Sharpe ~4.1x when the input is DAILY
    rather than hourly (sqrt(6240/365) = 4.135). That is a live, ledgered defect and it is NOT
    fixed here -- these tests pin the constant's VALUE and its MULTIPLICATIVE FORM so the fix, when
    it lands, is a deliberate visible change rather than the silent drift this module was open to.
    """

    def test_periods_per_year_is_hours_times_trading_days(self) -> None:
        """24 hourly bars x 260 trading days = 6240. Both factors are load-bearing and mean
        different things: 24 is the bar frequency (crypto trades around the clock), 260 is the
        annual trading-day count. Drift in either silently rescales every Sharpe the desk has ever
        stored, and nothing downstream can detect a Sharpe that is uniformly wrong."""
        assert V._PERIODS_PER_YEAR == 24 * 260
        assert V._PERIODS_PER_YEAR == 6240

    def test_annualising_is_multiplication_not_division(self) -> None:
        """THE `Mult -> Div` SURVIVOR, and the one with no plausible innocent reading. `24 / 260`
        is 0.0923: annualisation would SHRINK a Sharpe by 3.3x instead of growing it by 79x, a
        260x error in the reported number, and it would still be a perfectly valid float that
        every gate accepts. Pinning the integer TYPE is what makes the form untouchable -- true
        division always yields a float, so this assertion cannot be satisfied by a divided
        constant however the operands are chosen."""
        assert isinstance(V._PERIODS_PER_YEAR, int)
        assert V._PERIODS_PER_YEAR > 24
        assert V._PERIODS_PER_YEAR > 260
        assert V._PERIODS_PER_YEAR == 24 * 260

    def test_annual_sharpe_is_the_per_bar_sharpe_scaled_by_sqrt_6240(self) -> None:
        """THE BEHAVIOURAL HALF: what the constant actually does to a verdict's metrics. The
        literal 6240.0 here is deliberate -- deriving the expectation from `_PERIODS_PER_YEAR`
        would make the assertion true for any value the module happens to hold, which is exactly
        how these three mutants survived."""
        arr = _exact_sharpe_series(0.10)
        res = _score(arr)
        assert res.metrics.annual_sharpe == pytest.approx(
            sharpe_ratio(arr) * math.sqrt(6240.0), rel=1e-12)

    def test_the_annualisation_is_frequency_blind_which_is_R0086(self) -> None:
        """PINS THE DEFECT WHERE IT LIVES, rather than leaving it to a ledger row nobody re-reads.

        `validate()` has no frequency/periods parameter, so a DAILY return series is annualised
        with the HOURLY factor and its reported Sharpe is sqrt(6240/365) = 4.135x too large. That
        is live today: `libs/autodiscovery/crypto_adapter.py:54` defaults the lab to `Timeframe.D1`
        and `scripts/run_xsec_funding.py:44` reads D1 bars straight into `validate()`.

        This test asserts the CURRENT behaviour, not the desired one. It is the falsifier for
        R0086: the moment someone makes annualisation frequency-aware this goes red, which is
        correct -- that fix must update this fence consciously, not slide past it.
        """
        params = inspect.signature(V.validate).parameters
        assert not [p for p in params if "period" in p or "freq" in p or "annual" in p], (
            "validate() has grown a frequency argument -- R0086 has been addressed and this "
            "fence, plus the sqrt(6240) expectation above, must be re-derived deliberately"
        )
        daily_like = _exact_sharpe_series(0.10)
        assert _score(daily_like).metrics.annual_sharpe == pytest.approx(
            sharpe_ratio(daily_like) * math.sqrt(6240.0), rel=1e-12), (
            "a daily series is still annualised with the hourly factor (R0086, ~4.135x)"
        )


class TestDsrThreshold:
    """`_DSR_THRESHOLD = 0.95` -- survivor `0.95 -> 1.95`."""

    def test_the_bar_is_one_minus_the_desk_alpha(self) -> None:
        """0.95 is not a taste. DSR is P(true Sharpe > the deflated benchmark), so the bar is
        1 - alpha at the desk's standing alpha of 0.05 -- the same alpha `CAMPAIGN_ALPHA` carries
        into the campaign window. Tying the two here means the number cannot drift away from the
        alpha it is supposed to express without one of these two assertions firing."""
        assert V._DSR_THRESHOLD == 0.95
        assert CAMPAIGN_ALPHA == 0.05
        assert math.isclose(V._DSR_THRESHOLD, 1.0 - CAMPAIGN_ALPHA)

    def test_the_bar_is_an_attainable_probability(self) -> None:
        """THE `0.95 -> 1.95` SURVIVOR IN ONE LINE, and the reason it is worth its own assertion:
        DSR is a probability in [0, 1], so ANY bar at or above 1.0 welds the gate permanently shut
        and rejects every candidate the desk will ever generate. That failure is invisible in a
        gate histogram -- it reads as a perfectly rigorous 0% pass rate (L1.43)."""
        assert 0.0 < V._DSR_THRESHOLD < 1.0

    def test_a_candidate_just_above_the_bar_passes_and_just_below_fails(self) -> None:
        """THE BEHAVIOURAL HALF, bracketed tight enough to be a pin rather than a smoke test:
        measured DSR 0.9573 must pass and 0.9393 must fail, so the bar is fenced to roughly
        +/-0.01 around 0.95 in BOTH directions. The upward half kills the recorded survivor; the
        downward half is what stops the bar being quietly loosened to buy survivors, which is the
        move this desk's standing directive forbids outright."""
        strong = _score(_exact_sharpe_series(0.10))
        weak = _score(_exact_sharpe_series(0.09))
        assert strong.metrics.dsr > V._DSR_THRESHOLD > weak.metrics.dsr
        assert strong.gates["dsr"] is True
        assert weak.gates["dsr"] is False


class TestPboThreshold:
    """`_PBO_THRESHOLD = 0.5` -- survivor `0.5 -> 1.5`."""

    def test_the_bar_is_the_coin_flip(self) -> None:
        """PBO is the probability that the configuration selected in-sample ranks in the BOTTOM
        HALF out-of-sample. 0.5 is therefore the coin flip: at 0.5 the selection procedure carries
        exactly no information, and anything above it means the backtest ranking is worse than
        useless. It is the same bar `PBOResult.overfit` uses -- the constant exists here for
        attribution, not to hold a second, different opinion."""
        assert V._PBO_THRESHOLD == 0.5

    def test_the_bar_is_inside_the_range_pbo_can_take(self) -> None:
        """THE `0.5 -> 1.5` SURVIVOR. PBO is a probability, so a bar at or above 1.0 is passed by
        every candidate including a perfectly overfit one -- the gate keeps reporting True in every
        artifact while protecting nothing. That is the `beats_baselines` failure verbatim: a gate
        that read green for months because nobody could fail it."""
        assert 0.0 < V._PBO_THRESHOLD < 1.0

    def test_an_overfit_candidate_fails_and_the_bar_itself_passes(self) -> None:
        """THE BEHAVIOURAL HALF. A candidate whose own CSCV-PBO is 0.51 -- worse than a coin flip
        -- must fail the gate, and one sitting exactly ON 0.5 must pass, because the comparison is
        `<=`. Together they pin the value to a 0.01-wide window in both directions, so neither a
        loosened bar nor a silently tightened one survives."""
        assert _score(_exact_sharpe_series(0.10), pc_pbo=0.51).gates["pbo"] is False
        assert _score(_exact_sharpe_series(0.10), pc_pbo=0.50).gates["pbo"] is True


class TestDeskEquityFallback:
    """`_DESK_EQUITY_FALLBACK_USD = 1.0e3` -- survivor `1000.0 -> 1001.0`."""

    def test_the_fallback_is_the_documented_thousand_dollars(self) -> None:
        """The last rung of the equity ladder, reached only when venue truth, the live web artifact
        and the local config are ALL unreadable. $1,000 is the principal's stated deploy floor
        ("capital deploys from ~$1k"), and the value has to be a small POSITIVE number for two
        reasons the module spells out: zero would mark every edge OUTGROWN and empty the shortlist
        on an unreadable file, and an institutional round number would resurrect the $100k floor
        L1.18a exists to kill. A drifting fallback silently rescales every capacity band computed
        while the ladder is down."""
        assert V._DESK_EQUITY_FALLBACK_USD == 1000.0

    def test_an_unreadable_desk_falls_back_to_exactly_that_number(
            self, isolated_equity: Path) -> None:
        """BEHAVIOURAL, and it is the assertion the existing capacity suite could not make:
        `test_missing_state_falls_back_without_crashing` compares `_desk_equity_usd()` to the
        constant itself, so it holds for ANY value the constant takes -- which is precisely why
        `1000.0 -> 1001.0` survived. This compares to the literal."""
        assert V._desk_equity_usd() == 1000.0

    def test_the_fallback_sets_the_runway_clock(self, isolated_equity: Path) -> None:
        """The consequence that reaches a decision: `capacity_runway_days` divides the outgrowth
        equity by the CURRENT book, so on an unreadable desk the fallback IS the denominator, and
        runway is what orders the forward-slot queue (shortest expiry first). The expectation is
        built from literals for the same reason as above."""
        expected = 365.0 * math.log((3000.0 / 0.10) / 1000.0) / 1.0
        assert V.capacity_runway_days(3000.0) == pytest.approx(expected, rel=1e-9)


class TestExecutionViabilityFloor:
    """`_VENUE_MIN_NOTIONAL_FALLBACK_USD = 10.0` and the `20.0` multiple -- two survivors,
    `10.0 -> 11.0` and `20.0 -> 21.0`.

    Together they are `_EXEC_VIABILITY_FLOOR_USD`, the ONLY absolute capacity floor the desk
    permits: below a handful of economic round-trips at venue minimums, execution physics (L1.5)
    kills an edge at ANY equity. Every other capacity bar is a ratio to the book.
    """

    def test_the_venue_minimum_fallback_is_the_binance_class_minimum(self) -> None:
        """$10 is the Binance-class minimum order notional, and since R0218 it is the FALLBACK for
        an unmeasured venue rather than a restatement of policy. Its value carries the tighten-only
        rule: a measured venue minimum may RAISE the floor, never lower it below this, because the
        recorded truth (spot_min 5.0) sits BELOW 10.0 and adopting it outright would loosen the
        SUB-VIABLE gate. Drift here moves the floor for every candidate on a checkout where the
        capacity simulator has never run."""
        assert V._VENUE_MIN_NOTIONAL_FALLBACK_USD == 10.0
        assert V._VENUE_MIN_NOTIONAL_USD >= V._VENUE_MIN_NOTIONAL_FALLBACK_USD, "tighten-only"

    def test_the_floor_is_twenty_venue_minimums(self) -> None:
        """20 is "a handful of economic round-trips": fewer than ~20 venue-minimum notionals of
        capacity leaves no room for a few round-trips plus their costs. Asserting the RATIO rather
        than the dollar figure is deliberate -- it kills `20.0 -> 21.0` while surviving a
        legitimate measured raise of the venue minimum, which the tighten-only rule allows."""
        assert math.isclose(V._EXEC_VIABILITY_FLOOR_USD / V._VENUE_MIN_NOTIONAL_USD, 20.0)

    def test_the_floor_is_two_hundred_dollars_today(self) -> None:
        """The composed value, pinned as a number because both survivors move it and only one of
        them moves the ratio above. $200 = 20 x $10 holds while no measured venue minimum exceeds
        the $10 fallback (`venue_min_notional_usd()` is absent or below it in this checkout). If a
        measured raise ever lands this figure moves UP and only up -- update it upward, never
        down, and never by lowering a constant to make the test pass."""
        assert V._EXEC_VIABILITY_FLOOR_USD == 200.0

    def test_a_two_hundred_dollar_edge_is_admitted_and_a_smaller_one_is_sub_viable(self) -> None:
        """THE BEHAVIOURAL HALF: the verdict flips across the floor. $200 of capacity on a $1,000
        book is ADMIT (the 10% slice is $100, so the floor is the binding rule here), and a cent
        below it is SUB-VIABLE -- the desk's only genuine capacity rejection. Raising either
        constant pushes the floor to $210 or $220 and turns the $200 edge into a rejection, which
        is a REAL tightening of a statistical bar smuggled in as a typo."""
        assert V.capacity_status(200.0, equity_usd=1000.0) == "ADMIT"
        assert V.capacity_status(199.99, equity_usd=1000.0) == "SUB-VIABLE"


class TestVenueTruthRungGuard:
    """`if venue > 0:` in `_desk_equity_usd` -- survivor `0 -> 1`.

    The guard separates "the NAV chain gave a reading" from "there was nothing to read". It is
    called with `fallback=0.0` precisely so that 0.0 means ABSENT and any positive number means
    MEASURED; the comparison is what encodes that contract.
    """

    def test_any_positive_venue_reading_outranks_the_local_config(
            self, isolated_equity: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """THE `0 -> 1` SURVIVOR, and it is the two-source equity bug pointed back at itself. With
        `> 1` a genuine sub-$1 venue reading falls THROUGH to `cashcarry_config.json` -- the exact
        rung whose disagreement with venue truth ($4,500 config vs $13,155 measured) had the whole
        gauntlet sizing edges against a book 2.9x too small. The ladder's contract is that a
        reading outranks a config, not that a LARGE ENOUGH reading does."""
        import libs.research.capacity_policy as cp
        (isolated_equity / "data").mkdir()
        (isolated_equity / "data/cashcarry_config.json").write_text(
            json.dumps({"capital": 4500.0}), "utf-8")
        monkeypatch.setattr(cp, "live_book_usd", lambda fallback=0.0, ledger=None: 0.75)
        assert V._desk_equity_usd() == 0.75
        monkeypatch.setattr(cp, "live_book_usd", lambda fallback=0.0, ledger=None: 1.0)
        assert V._desk_equity_usd() == 1.0, "a $1 reading is a reading; `> 1` would discard it"

    def test_a_zero_reading_means_absent_and_falls_through(
            self, isolated_equity: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """The other direction, which keeps the test above from being satisfied by deleting the
        guard: 0.0 is the sentinel for an unreadable ledger, so it must NOT be adopted as an equity
        of zero -- zero equity marks every edge OUTGROWN and empties the shortlist, making an
        unreadable file the most destructive possible answer."""
        import libs.research.capacity_policy as cp
        (isolated_equity / "data").mkdir()
        (isolated_equity / "data/cashcarry_config.json").write_text(
            json.dumps({"capital": 4500.0}), "utf-8")
        monkeypatch.setattr(cp, "live_book_usd", lambda fallback=0.0, ledger=None: 0.0)
        assert V._desk_equity_usd() == 4500.0
