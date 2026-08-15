"""PERP FUNDING vs MARGIN BORROW -- the cost bases, which is where this comparison goes wrong.

Interest is charged on the BORROWED part; funding is charged on the WHOLE notional. Comparing the
raw rates gets the sign right by luck on today's numbers and the magnitude wrong always, and it
flips outright at high leverage. These pin the adjustment, the direction, and the refusals.
"""

from __future__ import annotations

import pytest
import scripts.compare_funding_vs_borrow as C


class TestTheCostBases:
    def test_margin_is_charged_on_the_borrowed_part_only(self) -> None:
        # At 2x, half the notional is borrowed, so the cost per unit of notional is HALF the rate.
        assert C.breakeven_funding(0.051, 2.0) == pytest.approx(0.0255)

    def test_an_unlevered_book_borrows_nothing_so_any_funding_loses(self) -> None:
        # Not degenerate -- it is the real answer. At 1x there is no loan to compare against.
        assert C.breakeven_funding(0.051, 1.0) == 0.0
        assert C.breakeven_funding(0.051, 0.5) == 0.0

    def test_margins_advantage_SHRINKS_as_leverage_rises(self) -> None:
        # (f-1)/f -> 1, so the break-even climbs toward the raw borrow rate. This is the term a
        # naive rate-vs-rate comparison drops, and dropping it flips the answer at high f.
        lo = C.breakeven_funding(0.051, 1.5)
        mid = C.breakeven_funding(0.051, 3.0)
        hi = C.breakeven_funding(0.051, 20.0)
        assert lo < mid < hi < 0.051
        assert hi == pytest.approx(0.051 * 19 / 20)

    def test_it_never_exceeds_the_raw_borrow_rate(self) -> None:
        for f in (1.01, 2.0, 5.0, 100.0, 1e6):
            assert C.breakeven_funding(0.051, f) <= 0.051


class TestTheAnswerOnRealisticNumbers:
    def test_typical_major_funding_loses_to_margin_at_the_books_leverage(self) -> None:
        # ~0.01% per 8h stamp = 0.03%/day = ~11%/yr, against a 2.31x break-even near 2.9%/yr.
        typical_annual = 0.0001 * 3 * 365
        assert typical_annual > C.breakeven_funding(0.051, 2.31) * 3, (
            "the headline case must come out clearly against perps, or the comparison is too "
            "close to justify skipping the build")

    def test_negative_funding_is_the_case_where_perp_WINS(self) -> None:
        # Shorts pay longs in bearish regimes and a perp long is PAID. The script must be able to
        # report this rather than smoothing it away, or it can only ever say no.
        assert C.breakeven_funding(0.051, 2.31) > -0.02


class TestItRefusesRatherThanGuesses:
    def test_an_unreadable_borrow_rate_is_UNMEASURED_not_a_placeholder(
            self, monkeypatch: pytest.MonkeyPatch) -> None:
        # A guessed cost of capital is how the account got capped at 1x once already.
        import libs.execution.binance_margin_live as m

        monkeypatch.setattr(m, "borrow_rate", lambda *_a, **_k: (None, "venue down"))
        rep = C.build(("BTCUSDT",))
        assert rep["verdict"] == "UNMEASURED"
        assert "breakeven_funding_annual" not in rep

    def test_a_missing_funding_series_is_UNMEASURED_not_zero_funding(
            self, monkeypatch: pytest.MonkeyPatch) -> None:
        import scripts.collect_perp_funding as F

        monkeypatch.setattr(F, "load", lambda _s: {})
        rep = C.build(("BTCUSDT",), borrow_rate=0.051)
        assert rep["symbols"]["BTCUSDT"]["state"] == "NO-FUNDING-SERIES"
        assert rep["verdict"] == "UNMEASURED"

    def test_a_thin_series_is_refused_rather_than_averaged(
            self, monkeypatch: pytest.MonkeyPatch) -> None:
        import scripts.collect_perp_funding as F

        thin = {f"2026-01-{i:02d}": 0.0001 for i in range(1, 10)}
        monkeypatch.setattr(F, "load", lambda _s: thin)
        rep = C.build(("BTCUSDT",), borrow_rate=0.051)
        assert rep["symbols"]["BTCUSDT"]["state"] == "NO-FUNDING-SERIES"


class TestTheVerdictOnPlantedSeries:
    @staticmethod
    def _series(daily: float, n: int = 200) -> dict[str, float]:
        return {f"d{i}": daily for i in range(n)}

    def test_expensive_funding_resolves_to_MARGIN(
            self, monkeypatch: pytest.MonkeyPatch) -> None:
        import scripts.collect_perp_funding as F

        monkeypatch.setattr(F, "load", lambda _s: self._series(0.0003))    # ~11%/yr
        rep = C.build(("BTCUSDT",), leverage=2.31, borrow_rate=0.051)
        assert rep["verdict"] == "MARGIN"
        assert rep["symbols"]["BTCUSDT"]["excess_of_perp_over_margin"] > 0

    def test_negative_funding_resolves_to_PERP(self, monkeypatch: pytest.MonkeyPatch) -> None:
        import scripts.collect_perp_funding as F

        monkeypatch.setattr(F, "load", lambda _s: self._series(-0.0001))
        rep = C.build(("BTCUSDT",), leverage=2.31, borrow_rate=0.051)
        assert rep["verdict"] == "PERP"
        assert rep["symbols"]["BTCUSDT"]["share_days_negative"] == 1.0

    def test_the_access_gate_is_reported_even_when_cost_favours_perp(
            self, monkeypatch: pytest.MonkeyPatch) -> None:
        # A cost verdict of PERP on an account that may not open one must not read as a green light.
        import scripts.collect_perp_funding as F

        monkeypatch.setattr(F, "load", lambda _s: self._series(-0.0001))
        rep = C.build(("BTCUSDT",), leverage=2.31, borrow_rate=0.051)
        assert rep["verdict"] == "PERP"
        assert "MiCA" in rep["access"]["recorded_finding"]
        assert "ACCESS STILL GATES THIS" in rep["why"]

    def test_the_median_is_used_so_one_squeeze_cannot_decide_a_venue(
            self, monkeypatch: pytest.MonkeyPatch) -> None:
        import scripts.collect_perp_funding as F

        # 199 cheap days and one enormous squeeze stamp. The MEAN crosses the break-even; the
        # median does not, and a standing venue choice must not turn on a single print.
        s = self._series(0.00001, 199)
        s["squeeze"] = 5.0
        monkeypatch.setattr(F, "load", lambda _s: s)
        rep = C.build(("BTCUSDT",), leverage=2.31, borrow_rate=0.051)
        row = rep["symbols"]["BTCUSDT"]
        assert row["mean_annual"] > row["median_annual"]
        assert row["cheaper"] == "PERP"


class TestTheCapabilityArgumentIsKeptSeparate:
    def test_the_short_capability_is_named_and_not_counted_as_a_saving(
            self, monkeypatch: pytest.MonkeyPatch) -> None:
        import scripts.collect_perp_funding as F

        monkeypatch.setattr(F, "load", lambda _s: {f"d{i}": 0.0003 for i in range(200)})
        note = C.build(("BTCUSDT",), borrow_rate=0.051)["capability_note"]
        assert "short" in note.lower()
        assert "never as a funding saving" in note
