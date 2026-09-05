"""The order-book-state primitives: the residualisation, the alignment, and the depth parser.

WHAT THESE PIN, AND WHY EACH ONE EXISTS. Resting-depth state is CONCURRENT with price, so a naive
screen of it manufactures an IC that is a restatement of the bar that just finished. Every prior
kill on the neighbouring informed-order-flow class died exactly there. So the tests are about the
three things that decide whether a screen built on this module is worth anything:

  * the residualisation really removes the same-period component, and cannot see forward;
  * the alignment really excludes the bar containing the snapshot;
  * the depth parser drops what it cannot read rather than coercing it to a zero that would read
    as a real, balanced, empty book.

PROVENANCE (2026-09-05). These are the venue-neutral half of the retired
`test_orderbook_state_screen.py`, which also drove a crypto-exchange screening script and that
script's recorded tape. The script and the tape are gone with the crypto desk; the primitives are
not, because they were never about a venue. Every assertion below is carried over UNCHANGED in
substance -- no tolerance was widened, no gate dropped -- and the fixtures are synthetic arrays
with a known answer, so they run on any box with no tape at all. When the MT5 tick/DOM recorder
lands, the end-to-end cells that were lost belong back on top of these.
"""
from __future__ import annotations

import numpy as np
import pytest

from libs.research.orderbook_state import (
    Alignment,
    bar_close_states,
    boundary_prices,
    contiguous_mask,
    depth_snapshots,
    period_returns,
    residualise,
    snapshot_states,
    withdrawal_asymmetry,
)

BAR_MS = 60_000
T0 = 1_767_225_600_000          # 2026-01-01T00:00:00Z, a real UTC instant


# --------------------------------------------------------------- the residualisation itself

def test_residualisation_removes_same_period_correlation() -> None:
    """THE LOAD-BEARING CLAIM, on a fixture where the answer is known: a state that is 91%
    same-period return must come out of `residualise` essentially orthogonal to it."""
    rng = np.random.default_rng(3)
    ret = rng.normal(0, 0.01, 2000)
    state = 0.9 * (ret / ret.std()) + rng.normal(0, 0.4, 2000)

    before = float(np.corrcoef(state, ret)[0, 1])
    resid = residualise(state, ret, min_obs=60)
    ok = np.isfinite(resid)
    after = float(np.corrcoef(resid[ok], ret[ok])[0, 1])

    assert before > 0.85, "fixture is not contaminated, so it tests nothing"
    assert abs(after) < 0.05, f"same-period correlation survived residualisation: {after}"
    assert int(ok.sum()) == 2000 - 60, "warmup must be exactly min_obs bars, no more, no fewer"


def test_residualisation_preserves_a_genuine_lead() -> None:
    """De-contamination must not be de-signalling. A state that leads keeps its forward IC."""
    rng = np.random.default_rng(5)
    ret = rng.normal(0, 0.01, 3000)
    fwd = np.roll(ret, -1)
    state = 0.9 * (ret / ret.std()) + 0.20 * (fwd / ret.std()) + rng.normal(0, 0.5, 3000)

    resid = residualise(state, ret, min_obs=60)
    ok = np.isfinite(resid)
    ok[-1] = False                                   # last bar has no forward return
    assert abs(float(np.corrcoef(resid[ok], fwd[ok])[0, 1])) > 0.15


def test_residualise_cannot_see_forward() -> None:
    """THE PROPERTY THAT MAKES THE RESIDUAL TRADEABLE. Perturbing a FUTURE return must leave every
    earlier residual bit-identical -- a full-sample beta would change all of them, silently, and
    would look exactly like preprocessing."""
    rng = np.random.default_rng(9)
    ret = rng.normal(0, 0.01, 800)
    state = 0.7 * (ret / ret.std()) + rng.normal(0, 0.5, 800)

    base = residualise(state, ret, min_obs=60)
    poked = ret.copy()
    poked[500] += 5.0                                # a return that has not happened yet at k<500
    after = residualise(state, poked, min_obs=60)

    assert np.array_equal(base[:500], after[:500], equal_nan=True)
    assert not np.array_equal(base[500:], after[500:], equal_nan=True), \
        "the perturbation must matter from its own bar onward, or the test proves nothing"


def test_residualise_rejects_mismatched_lengths() -> None:
    with pytest.raises(ValueError, match="length mismatch"):
        residualise(np.zeros(10), np.zeros(11))


# ------------------------------------------------------------------------- alignment is law

def test_bar_close_takes_the_last_snapshot_strictly_inside_the_bar() -> None:
    al = Alignment(bar_ms=BAR_MS)
    rows = [
        {"t": T0 + 10_000, "b": [[100.0, 1.0]], "a": [[101.0, 9.0]]},
        {"t": T0 + 59_999, "b": [[100.0, 9.0]], "a": [[101.0, 1.0]]},
        {"t": T0 + 60_000, "b": [[100.0, 1.0]], "a": [[101.0, 1.0]]},
    ]
    ms, states = snapshot_states(rows)
    edges, closes = bar_close_states(ms, states, alignment=al)

    assert edges.tolist() == [T0 + 60_000, T0 + 120_000]
    # bar 0 closes on the 59_999ms snapshot (9 bid vs 1 ask -> +0.8), NOT the one AT the edge,
    # which belongs to bar 1 because the interval is half-open.
    assert closes["obi_touch"][0] == pytest.approx(0.8)
    assert closes["obi_touch"][1] == pytest.approx(0.0)


def test_target_is_priced_at_or_after_the_bar_edge_never_inside_it() -> None:
    """A snapshot at t never sees the bar containing t: prints strictly inside bar k cannot reach
    the price that opens the forward window at b_k."""
    al = Alignment(bar_ms=BAR_MS)
    edges = np.array([T0 + BAR_MS, T0 + 2 * BAR_MS], dtype="int64")
    t_ms = np.array([T0 + 5, T0 + BAR_MS - 1, T0 + BAR_MS, T0 + 2 * BAR_MS], dtype="int64")
    t_px = np.array([1.0, 2.0, 3.0, 4.0])

    p = boundary_prices(t_ms, t_px, edges, alignment=al)
    assert p.tolist() == [3.0, 4.0]                  # the AT-edge prints, not the inside ones

    # Rewriting every print INSIDE the bars leaves the boundary prices untouched.
    t_px2 = np.array([999.0, 888.0, 3.0, 4.0])
    assert boundary_prices(t_ms, t_px2, edges, alignment=al).tolist() == [3.0, 4.0]


def test_decision_lag_can_only_move_the_target_later() -> None:
    al0 = Alignment(bar_ms=BAR_MS)
    al1 = Alignment(bar_ms=BAR_MS, decision_lag_ms=500)
    edges = np.array([T0 + BAR_MS], dtype="int64")
    t_ms = np.array([T0 + BAR_MS, T0 + BAR_MS + 400, T0 + BAR_MS + 900], dtype="int64")
    t_px = np.array([10.0, 11.0, 12.0])

    assert boundary_prices(t_ms, t_px, edges, alignment=al0)[0] == pytest.approx(10.0)
    assert boundary_prices(t_ms, t_px, edges, alignment=al1)[0] == pytest.approx(12.0)


def test_period_return_is_contemporaneous_not_forward() -> None:
    """The screening harness does the forward shift itself; handing it an already-forward target
    makes it shift twice, which its own lookahead rail then reads as misalignment."""
    r = period_returns(np.array([100.0, 110.0, 121.0]))
    assert np.isnan(r[0])
    assert r[1] == pytest.approx(0.10)
    assert r[2] == pytest.approx(0.10)


def test_gapped_bars_are_dropped_not_priced() -> None:
    al = Alignment(bar_ms=BAR_MS)
    edges = np.array([T0 + BAR_MS, T0 + 2 * BAR_MS, T0 + 50 * BAR_MS], dtype="int64")
    m = contiguous_mask(edges, alignment=al)
    assert m.tolist() == [False, True, False]


def test_alignment_is_echoed_and_declares_its_lookahead_risk() -> None:
    d = Alignment(bar_ms=BAR_MS).as_dict()
    assert d["excludes_current_bar"] is True
    assert d.get("lookahead_risk")
    assert d["horizon_days"] == pytest.approx(BAR_MS / 86_400_000.0)


@pytest.mark.parametrize("bad", [{"bar_ms": 0}, {"bar_ms": BAR_MS, "decision_lag_ms": -1}])
def test_alignment_rejects_impossible_rules(bad: dict[str, int]) -> None:
    with pytest.raises(ValueError):
        Alignment(**bad)


# ------------------------------------------------------------------- the depth parser itself

def test_levels_are_sorted_so_index_zero_really_is_the_touch() -> None:
    """A feed is not obliged to sort. Every primitive indexes [0] as the touch, so an unsorted
    snapshot would silently price the WRONG level and read as microstructure."""
    rows = [{"t": T0, "b": [[99.0, 1.0], [100.0, 5.0]], "a": [[102.0, 3.0], [101.0, 7.0]]}]
    (ms, bp, bs, ap, asz), = depth_snapshots(rows)
    assert ms == T0
    assert bp.tolist() == [100.0, 99.0] and bs.tolist() == [5.0, 1.0]
    assert ap.tolist() == [101.0, 102.0] and asz.tolist() == [7.0, 3.0]


def test_a_crossed_book_is_dropped_rather_than_priced() -> None:
    """bid >= ask is physically impossible and means a torn snapshot. Pricing one yields a
    NEGATIVE spread -- "the venue pays us to trade" -- the exciting artifact that survives review."""
    rows = [
        {"t": T0, "b": [[101.0, 1.0]], "a": [[100.0, 1.0]]},        # crossed
        {"t": T0 + 1, "b": [[100.0, 1.0]], "a": [[100.0, 1.0]]},    # locked
        {"t": T0 + 2, "b": [[100.0, 1.0]], "a": [[101.0, 1.0]]},    # clean
    ]
    assert [s[0] for s in depth_snapshots(rows)] == [T0 + 2]


def test_snapshots_come_back_in_time_order_whatever_order_they_arrived() -> None:
    rows = [
        {"t": T0 + 200, "b": [[100.0, 1.0]], "a": [[101.0, 1.0]]},
        {"t": T0, "b": [[100.0, 1.0]], "a": [[101.0, 1.0]]},
        {"t": T0 + 100, "b": [[100.0, 1.0]], "a": [[101.0, 1.0]]},
    ]
    assert [s[0] for s in depth_snapshots(rows)] == [T0, T0 + 100, T0 + 200]


@pytest.mark.parametrize("keys", [("b", "a"), ("bids", "asks")])
def test_both_side_spellings_are_read(keys: tuple[str, str]) -> None:
    """A recorder that spells the sides out must not read as an empty book -- the silent-zero bug
    that a second, narrower reader would reintroduce."""
    bid, ask = keys
    rows = [{"t": T0, bid: [["100.0", "2.0"]], ask: [["101.0", "3.0"]]}]
    snaps = depth_snapshots(rows)
    assert len(snaps) == 1
    assert snaps[0][2].tolist() == [2.0] and snaps[0][4].tolist() == [3.0]


def test_an_unreadable_level_is_dropped_never_coerced_to_zero() -> None:
    """A zero size is a REAL book state (the level is quoted and empty). Inventing one out of a
    malformed row manufactures a withdrawal event that never happened."""
    rows = [{"t": T0,
             "b": [[100.0, 4.0], ["oops", 1.0], [99.0, None], [98.0, 2.0]],
             "a": [[101.0, 1.0]]}]
    (_, bp, bs, _, _), = depth_snapshots(rows)
    assert bp.tolist() == [100.0, 98.0]
    assert bs.tolist() == [4.0, 2.0]
    assert 0.0 not in bs.tolist()


def test_an_empty_side_is_not_a_book() -> None:
    rows = [{"t": T0, "b": [], "a": [[101.0, 1.0]]},
            {"t": T0 + 1, "b": [[100.0, 1.0]], "a": []}]
    assert depth_snapshots(rows) == []


def test_state_primitives_are_nan_not_zero_when_unmeasurable() -> None:
    """A zero imbalance is a real, balanced book -- the opposite of "could not be read"."""
    rows = [{"t": T0, "b": [[100.0, 0.0]], "a": [[101.0, 0.0]]}]
    _, states = snapshot_states(rows)
    assert np.isnan(states["obi_touch"][0])
    assert np.isnan(states["obi_deep"][0])
    assert states["depth_bid"][0] == 0.0             # the SUM is genuinely measured at zero


def test_withdrawal_is_not_netted_against_replenishment() -> None:
    """Netting additions against removals averages the exact event of interest into invisibility:
    size vanishing before a move is not cancelled by size arriving after it."""
    bid = np.array([100.0, 50.0, 50.0])              # bid halves, then holds
    ask = np.array([100.0, 100.0, 200.0])            # ask holds, then doubles
    w = withdrawal_asymmetry(bid, ask)
    assert np.isnan(w[0])                            # no previous bar
    assert w[1] > 0.0, "the bid withdrew and the ask did not -- that is a signed asymmetry"
    assert w[2] < 0.0 or w[2] == pytest.approx(0.0), "an ADDITION is never counted as a withdrawal"
