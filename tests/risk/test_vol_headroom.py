"""VOL-TARGET HEADROOM (R0107, L1.28a) -- the ceiling measures, and it refuses.

WHY THE POSITIVE CONTROL IS THE FIRST TEST HERE. This desk has paid for shipping fences that
were only ever observed REJECTING: a gauntlet never shown to pass a known-good alpha, a causal
guard that reported ok=True on the exact leak its docstring claimed to reject. A vol ceiling
that reads UNMEASURED on today's molded NAV chain looks identical to one that is simply broken,
and today's chain is molded, so the refusal path is the only one production can exercise. So the
measuring path is pinned against a synthetic venue-truth series with a Sharpe computed by hand.

The refusal tests then prove the fence is not welded shut in the other direction either: each
one shows a SPECIFIC input being turned away for a SPECIFIC stated reason, not a blanket no.
"""

from __future__ import annotations

import json
import math
from datetime import date, timedelta
from pathlib import Path

import pytest

from libs.risk.vol_headroom import (
    PERIODS_PER_YEAR,
    from_nav_chain,
    kelly_vol_ceiling,
)

_VENUE_TRUTH = "LIVE (binance) -- post-Gate-0"


def _write_chain(path: Path, rows: list[dict]) -> Path:
    path.write_text("".join(json.dumps(r) + "\n" for r in rows), "utf-8")
    return path


def _series(n: int, *, mean: float, amp: float, mode: str = _VENUE_TRUTH,
            start: float = 10_000.0, step_days: int = 1) -> list[dict]:
    """Equity rows whose log returns alternate ``mean +/- amp`` -- sd is known by construction."""
    rows, equity, day = [], start, date(2026, 1, 1)
    rows.append({"date": day.isoformat(), "equity_marked": equity, "mode": mode})
    for i in range(n):
        equity *= math.exp(mean + (amp if i % 2 == 0 else -amp))
        day += timedelta(days=step_days)
        rows.append({"date": day.isoformat(), "equity_marked": round(equity, 6), "mode": mode})
    return rows


# --------------------------------------------------------------------------- the arithmetic


def test_kelly_vol_ceiling_is_fraction_times_sharpe() -> None:
    """sigma_book = f * S. The identity the whole module rests on."""
    assert kelly_vol_ceiling(2.0, 0.5) == pytest.approx(1.0)
    assert kelly_vol_ceiling(1.2, 1 / 3) == pytest.approx(0.4)


def test_non_positive_sharpe_permits_zero_volatility() -> None:
    """An edge indistinguishable from zero is allocated ZERO -- so there is no budget to spend."""
    assert kelly_vol_ceiling(0.0, 0.5) == 0.0
    assert kelly_vol_ceiling(-1.5, 0.5) == 0.0


def test_default_cap_is_the_rail_not_a_local_constant() -> None:
    """The cap comes from KellyLimits so a rail change propagates; it is never re-typed here."""
    from libs.risk.config import KellyLimits
    assert kelly_vol_ceiling(2.0) == pytest.approx(KellyLimits().hard_max * 2.0)


# --------------------------------------------------------------------- POSITIVE CONTROL


def test_measures_a_venue_truth_series_with_demonstrated_sharpe(tmp_path: Path) -> None:
    """THE POSITIVE CONTROL: given real fills and enough of them, the ceiling MEASURES.

    500 daily observations with mean/sd = 0.1 gives t ~ 2.23 (clears the evidence bar) and an
    annualized Sharpe of 0.1 * sqrt(365) ~ 1.91, so the half-Kelly ceiling is ~0.955.
    """
    mean, amp = 0.001, 0.01
    chain = _write_chain(tmp_path / "nav.jsonl", _series(500, mean=mean, amp=amp))

    h = from_nav_chain(chain)

    assert h.measured, f"positive control must measure, got: {h.reason}"
    assert h.n_obs == 500
    assert h.sharpe_ann == pytest.approx((mean / amp) * math.sqrt(PERIODS_PER_YEAR), rel=0.02)
    assert h.ceiling_vol_ann == pytest.approx(0.5 * h.sharpe_ann, rel=1e-6)
    assert h.realized_vol_ann == pytest.approx(amp * math.sqrt(PERIODS_PER_YEAR), rel=0.02)
    assert 0.0 < h.utilisation < 1.0
    assert h.headroom == pytest.approx(h.ceiling_vol_ann - h.realized_vol_ann)


def test_over_kelly_breach_is_visible_as_utilisation_above_one(tmp_path: Path) -> None:
    """The breach direction must be REPORTABLE, not clamped -- an over-limit read is the alarm."""
    chain = _write_chain(tmp_path / "nav.jsonl", _series(500, mean=0.001, amp=0.01))
    h = from_nav_chain(chain, kelly_cap=0.01)      # an absurdly tight cap forces the breach

    assert h.measured
    assert h.headroom < 0, "realized vol above the ceiling must show NEGATIVE headroom"
    assert h.utilisation > 1.0, "a breach must read above 1.0, never clamp to a comfortable 100%"


# ------------------------------------------------------------------------- the refusals


def test_refuses_a_molded_curve(tmp_path: Path) -> None:
    """A simulated equity series must never set a risk ceiling (L1.45: no sizing on fiction)."""
    rows = _series(500, mean=0.001, amp=0.01)
    for r in rows:
        r["molded_curve_usd"] = r["equity_marked"]

    h = from_nav_chain(_write_chain(tmp_path / "nav.jsonl", rows))

    assert not h.measured
    assert h.utilisation == 0.0, "unmeasured counts as ZERO utilisation, never as healthy"
    assert "molded" in h.reason


def test_refuses_paper_and_testnet_modes(tmp_path: Path) -> None:
    for mode in ("PAPER (testnet) -- pre-Gate-0", "SHADOW", "backtest replay"):
        rows = _series(500, mean=0.001, amp=0.01, mode=mode)
        h = from_nav_chain(_write_chain(tmp_path / f"nav_{abs(hash(mode))}.jsonl", rows))
        assert not h.measured, f"{mode!r} is not venue truth and must be refused"


def test_row_without_a_mode_fails_closed(tmp_path: Path) -> None:
    """Missing provenance is never evidence of a real fill (L1.46)."""
    rows = [{"date": r["date"], "equity_marked": r["equity_marked"]}
            for r in _series(500, mean=0.001, amp=0.01)]
    h = from_nav_chain(_write_chain(tmp_path / "nav.jsonl", rows))
    assert not h.measured


def test_refuses_an_undemonstrated_sharpe_and_reports_observations_not_days(
    tmp_path: Path,
) -> None:
    """A hot streak must not license leverage: too few observations -> no ceiling (L1.29/L1.48)."""
    chain = _write_chain(tmp_path / "nav.jsonl", _series(25, mean=0.0001, amp=0.02))

    h = from_nav_chain(chain)

    assert not h.measured
    assert h.ceiling_vol_ann == 0.0, "no ceiling may be published from an unestablished Sharpe"
    assert h.realized_vol_ann > 0.0, "the realized vol is still reported -- only the CEILING is not"
    assert "observation" in h.reason
    assert "day" not in h.reason.replace("days", "").replace("day", ""), "shortfall is in obs"


def test_the_same_underlying_process_annualizes_alike_however_it_is_sampled(
    tmp_path: Path,
) -> None:
    """Sampling cadence must not change the answer -- that is what r/sqrt(dt) buys.

    Under a random walk a 3-day move has sqrt(3) times the sd of a 1-day move. So a series
    sampled every 3 days with moves of ``amp*sqrt(3)`` is the SAME underlying process as a daily
    series with moves of ``amp``, and both must report the same annualized volatility.
    """
    k = math.sqrt(3)
    daily = _write_chain(tmp_path / "d.jsonl",
                         _series(500, mean=0.001, amp=0.01, step_days=1))
    every3 = _write_chain(tmp_path / "g.jsonl",
                          _series(500, mean=0.001 * k, amp=0.01 * k, step_days=3))

    h_daily, h_gap = from_nav_chain(daily), from_nav_chain(every3)

    assert h_daily.measured and h_gap.measured
    assert h_gap.realized_vol_ann == pytest.approx(h_daily.realized_vol_ann, rel=0.02), (
        "the same process sampled 3-daily must annualize to the same volatility")
    assert h_gap.sharpe_ann == pytest.approx(h_daily.sharpe_ann, rel=0.02)


def test_a_gap_is_not_silently_counted_as_one_day(tmp_path: Path) -> None:
    """THE BUG THIS PREVENTS: identical moves spaced 3 days apart are NOT 3x the daily risk.

    Without the sqrt(dt) normalization both series below would report the same volatility, and
    the desk would read a sparsely-stamped chain as far riskier than it is -- inflating the
    denominator of every utilisation reading taken against it.
    """
    daily = _write_chain(tmp_path / "d.jsonl", _series(500, mean=0.001, amp=0.01, step_days=1))
    every3 = _write_chain(tmp_path / "g.jsonl", _series(500, mean=0.001, amp=0.01, step_days=3))

    h_daily, h_gap = from_nav_chain(daily), from_nav_chain(every3)

    assert h_gap.realized_vol_ann == pytest.approx(
        h_daily.realized_vol_ann / math.sqrt(3), rel=0.02), (
        "a 3-day move carries sqrt(3) LESS daily risk than the same move made in one day")


def test_missing_and_corrupt_inputs_refuse_rather_than_guess(tmp_path: Path) -> None:
    absent = from_nav_chain(tmp_path / "does_not_exist.jsonl")
    assert not absent.measured and "unreadable" in absent.reason

    junk = (tmp_path / "junk.jsonl")
    junk.write_text("{not json\nalso not json\n", "utf-8")
    assert not from_nav_chain(junk).measured


def test_the_live_nav_chain_is_refused_today(tmp_path: Path) -> None:
    """PINS THE PRODUCTION STATE: every real NAV row is paper/molded, so the fence reads zero.

    This is the assertion that must FLIP when the desk goes live. If it starts failing because
    the chain now carries venue truth, that is the fence beginning to work -- update it then.
    """
    live = Path(__file__).resolve().parents[2] / "data/nav_attestation.jsonl"
    if not live.exists():
        pytest.skip("no NAV chain on this host")
    h = from_nav_chain(live)
    assert not h.measured
    assert h.utilisation == 0.0
