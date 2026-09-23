"""A spread is identical whether it was a fee or a warning. Only the markout tells them apart.

WHAT THIS GUARDS. `mt5desk/markout.py` measures intent against fill -- execution quality against
what the desk asked for. `fill_markout` measures fill against the MID FROM THE TAPE, which is the
only way to see whether the quote the desk crossed was about to move. A fill whose markout is
negative was adversely selected; one whose markout is positive took liquidity ahead of a move it
was right about. The spread paid is the same in both cases, so no amount of slippage measurement
can separate them, and the separation is what decides market versus limit.

THE THREE PROPERTIES THAT DECIDE WHETHER THE NUMBER IS REAL:

    A HORIZON THAT HAS NOT ELAPSED IS REFUSED. This is the trap the whole file is built around.
    Markout at h is not knowable until h has passed, so scoring today's fills from a truncated
    tape hands back a partial or zero move and drags the estimate toward "no adverse selection"
    EXACTLY AS THE SAMPLE GROWS. The bias points at the reassuring answer and gets stronger with
    more data, which is the worst combination a statistic can have.

    THE LOOKUP IS AT-OR-BEFORE, NEVER NEAREST. A nearest-quote lookup returns quotes from AFTER
    the instant asked about; at a one-second horizon that is most of the answer, and the markout
    would be reading the very move it is supposed to be predicting.

    A MISSING QUOTE IS UNMEASURED, NEVER ZERO. If the tape has no quote near the fill, the mid at
    fill is unknown and so is everything derived from it. Substituting a quote from an hour
    earlier produces an error the size of the effect (L1.28a).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pytest

_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from libs.research.fill_markout import (  # noqa: E402
    BUY,
    MAX_STALE_MS,
    MIN_FILLS,
    SELL,
    Fill,
    by_cohort,
    census,
    cohort,
    load_fills,
    mark,
)

POINT = 0.01


def _tape(n: int = 1000, *, start_ms: int = 1_000_000, step_ms: int = 100,
          mid0: float = 100.0, drift: float = 0.0, half_spread: float = 0.05):
    """A quote tape with a controllable drift, so a markout has a known right answer."""
    ts = np.arange(n, dtype=np.int64) * step_ms + start_ms
    mid = mid0 + drift * np.arange(n, dtype=float)
    return ts, mid - half_spread, mid + half_spread


def _fill(ts_ms: int, price: float, direction: int = BUY, **kw) -> Fill:
    return Fill(ts_ms=ts_ms, price=price, direction=direction, symbol="X", **kw)


# ---------------------------------------------------------------- the point-in-time refusal ----
def test_a_horizon_past_the_end_of_the_tape_is_refused_not_scored():
    """The bias this prevents points at the reassuring answer and grows with the sample."""
    ts, bid, ask = _tape(n=100, step_ms=100)          # 10 seconds of tape
    f = _fill(int(ts[-1]) - 500, 100.05)              # 0.5s before the tape ends
    m = mark(f, ts, bid, ask, point=POINT)
    assert m.measured
    assert m.markout_pts[1_000] is None, "a 1s horizon 0.5s from the end is not knowable"
    assert m.markout_pts[300_000] is None
    assert m.effective_cost_pts is not None, "the cost at the fill IS knowable"


def test_the_refusal_is_counted_by_name_rather_than_dropped():
    ts, bid, ask = _tape(n=100, step_ms=100)
    marked = [mark(_fill(int(ts[-1]) - 200, 100.05), ts, bid, ask, point=POINT)
              for _ in range(5)]
    got = cohort(marked, 5_000, min_fills=1)
    assert got["status"] == "UNMEASURED"
    assert got["refused"]["horizon_not_elapsed"] == 5
    assert got["refused"]["no_tape_at_fill"] == 0


def test_a_truncated_tape_never_reports_a_clean_cohort():
    """The whole failure mode in one assertion: no tape, no verdict -- not a zero markout."""
    ts, bid, ask = _tape(n=50, step_ms=100)
    marked = [mark(_fill(int(ts[-1]), 100.05), ts, bid, ask, point=POINT) for _ in range(200)]
    for h in (1_000, 30_000):
        assert cohort(marked, h)["status"] == "UNMEASURED"


# ---------------------------------------------------------------------------- the lookup -------
def test_the_mid_lookup_never_reaches_forward():
    """At a one-second horizon a nearest-quote lookup is most of the answer."""
    ts = np.array([0, 10_000], dtype=np.int64)
    bid, ask = np.array([99.95, 199.95]), np.array([100.05, 200.05])
    m = mark(_fill(1_000, 100.05), ts, bid, ask, point=POINT)
    assert m.mid_at_fill == 100.0, "it took the quote from AFTER the fill"


def test_a_fill_with_no_quote_close_enough_is_unmeasured():
    ts = np.array([0], dtype=np.int64)
    bid, ask = np.array([99.95]), np.array([100.05])
    m = mark(_fill(MAX_STALE_MS + 1, 100.05), ts, bid, ask, point=POINT)
    assert not m.measured
    assert m.mid_at_fill is None and m.effective_cost_pts is None
    assert all(v is None for v in m.markout_pts.values())
    assert "no quote within" in m.why


def test_a_fill_before_the_tape_starts_is_unmeasured():
    ts, bid, ask = _tape(start_ms=1_000_000)
    assert not mark(_fill(500_000, 100.05), ts, bid, ask, point=POINT).measured


# ------------------------------------------------------------------------------ the sign -------
def test_a_buy_the_market_runs_away_from_is_adverse():
    """Mid falls after a buy: the quote crossed was about to move, and the spread was a warning."""
    ts, bid, ask = _tape(n=6000, drift=-0.001)
    m = mark(_fill(int(ts[0]), 100.05, BUY), ts, bid, ask, point=POINT)
    assert m.markout_pts[30_000] < 0
    assert m.effective_cost_pts == pytest.approx(5.0)      # crossed half a spread = 0.05 = 5 pts


def test_a_sell_the_market_runs_away_from_is_adverse_with_the_same_sign():
    """Direction-adjusted, so a bad buy and a bad sell must not cancel in a mean."""
    ts, bid, ask = _tape(n=6000, drift=+0.001)
    m = mark(_fill(int(ts[0]), 99.95, SELL), ts, bid, ask, point=POINT)
    assert m.markout_pts[30_000] < 0
    assert m.effective_cost_pts == pytest.approx(5.0)


def test_a_fill_ahead_of_a_move_it_was_right_about_is_positive():
    ts, bid, ask = _tape(n=6000, drift=+0.001)
    m = mark(_fill(int(ts[0]), 100.05, BUY), ts, bid, ask, point=POINT)
    assert m.markout_pts[30_000] > 0


def test_realised_spread_is_what_the_other_side_kept():
    """cost - markout. A clean fill leaves the LP less than the quoted spread suggests."""
    ts, bid, ask = _tape(n=6000, drift=+0.001)
    m = mark(_fill(int(ts[0]), 100.05, BUY), ts, bid, ask, point=POINT)
    assert m.realised_spread_pts(30_000) == pytest.approx(
        m.effective_cost_pts - m.markout_pts[30_000])
    assert m.realised_spread_pts(30_000) < m.effective_cost_pts


# ------------------------------------------------------------------------------ cohorts --------
def test_a_small_cohort_is_unmeasured_and_says_why():
    ts, bid, ask = _tape(n=6000)
    marked = [mark(_fill(int(ts[0]) + i, 100.05), ts, bid, ask, point=POINT)
              for i in range(MIN_FILLS - 1)]
    got = cohort(marked, 30_000)
    assert got["status"] == "UNMEASURED" and got["n"] == MIN_FILLS - 1
    assert "random walk" in got["why"]


def test_the_median_survives_one_release_print_that_the_mean_does_not():
    """A cohort whose mean is far worse than its median is hurt by rare events, which wants a
    different fix than one that is uniformly toxic -- so both are reported."""
    ts, bid, ask = _tape(n=6000, drift=0.0)
    marked = [mark(_fill(int(ts[0]) + i, 100.05), ts, bid, ask, point=POINT)
              for i in range(MIN_FILLS + 5)]
    spike = np.array(ts, dtype=np.int64), np.array(bid), np.array(ask)
    sb = spike[1].copy()
    sa = spike[2].copy()
    sb[300:] -= 50.0
    sa[300:] -= 50.0
    marked.append(mark(_fill(int(ts[0]), 100.05), spike[0], sb, sa, point=POINT))
    got = cohort(marked, 30_000)
    assert got["status"] == "MEASURED"
    assert got["markout_mean_pts"] < got["markout_median_pts"]


def test_cohorts_split_only_on_axes_a_policy_has_a_lever_on():
    """A number with no available action attached to it is a report, not a decision input."""
    ts, bid, ask = _tape(n=6000)
    marked = [mark(_fill(int(ts[0]), 100.05, order_type="market", sleeve="a"),
                   ts, bid, ask, point=POINT)]
    for key in ("sleeve", "order_type", "hour", "symbol"):
        assert by_cohort(marked, key, min_fills=1)
    with pytest.raises(ValueError, match="lever"):
        by_cohort(marked, "ticket")


def test_market_and_limit_are_split_because_that_is_the_decision():
    ts, bid, ask = _tape(n=6000, drift=-0.001)
    marked = ([mark(_fill(int(ts[0]) + i, 100.05, order_type="market"), ts, bid, ask, point=POINT)
               for i in range(MIN_FILLS)]
              + [mark(_fill(int(ts[0]) + i, 100.00, order_type="limit"), ts, bid, ask, point=POINT)
                 for i in range(MIN_FILLS)])
    got = by_cohort(marked, "order_type", horizon_ms=30_000)
    assert got["market"]["status"] == "MEASURED" and got["limit"]["status"] == "MEASURED"
    assert got["limit"]["effective_cost_median_pts"] < got["market"]["effective_cost_median_pts"]


# ------------------------------------------------------------------------------- loading -------
def test_a_row_without_a_side_is_skipped_not_defaulted(tmp_path):
    """A guessed direction contributes its markout with the sign reversed, which moves the
    estimate toward zero and looks like data."""
    p = tmp_path / "deals.jsonl"
    p.write_text("\n".join(json.dumps(r) for r in [
        {"ts_ms": 1, "price": 100.0, "side": "buy", "ticket": "ok"},
        {"ts_ms": 2, "price": 100.0},                       # no side
        {"ts_ms": 3, "side": "sell"},                       # no price
        {"price": 100.0, "side": "sell"},                   # no stamp
        {"ts_ms": 5, "price": 100.0, "side": "short", "ticket": "ok2"},
        "not json",
    ] if isinstance(r, dict)) + "\nnot json\n", encoding="utf-8")
    got = load_fills(p)
    assert [f.ticket for f in got] == ["ok", "ok2"]
    assert got[1].direction == SELL


def test_an_absent_journal_is_empty_not_an_error(tmp_path):
    assert load_fills(tmp_path / "nope.jsonl") == []


def test_zero_fills_census_is_unmeasured_throughout():
    """The desk's live state today: the module measures the FIRST fill, and says so until then."""
    doc = census([])
    assert doc["n_fills"] == 0 and doc["n_priced"] == 0
    assert all(v["status"] == "UNMEASURED" for v in doc["all"].values())
    assert "truncated tape" in doc["rule"]


def test_a_bad_point_size_refuses_rather_than_guessing():
    ts, bid, ask = _tape()
    m = mark(_fill(int(ts[0]), 100.05), ts, bid, ask, point=0.0)
    assert not m.measured and "guesses a unit" in m.why


def test_the_module_reads_exactly_one_path():
    """Zero promotion authority, and one reader so the surface stays auditable."""
    src = (_ROOT / "libs" / "research" / "fill_markout.py").read_text(encoding="utf-8")
    assert src.count("read_text(") == 1
    for forbidden in ("write_text(", "subprocess", "import pandas", "def promote", "def size"):
        assert forbidden not in src, f"fill_markout reached for {forbidden}"
