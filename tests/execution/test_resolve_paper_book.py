

# --- the payoff shape is MEASURED, not assumed --------------------------------------------------

def test_payoff_stays_assumed_until_there_is_enough_record():
    """A payoff ratio off a handful of trades would move the Kelly sizer on noise."""
    from scripts.resolve_paper_book import realised_payoff
    out = realised_payoff([{"realised_R": 3.0} for _ in range(5)])
    assert out["state"] == "ASSUMED"
    assert out["ratio"] == 3.0 and "ASSUMPTION" in out["why"]


def test_measured_payoff_moves_the_breakeven_the_assumption_hid():
    """The steepest gradient on the desk, and it was never aggregated from the marks.

    Every money figure downstream -- the 31.1% breakeven, the Kelly odds, the promotion bar --
    rests on a 3:1 winner shape that was assumed. A sleeve realising 2.27:1 needs a 37.9% hit
    rate to break even, not 31.1%: a 6.8pp swing that is invisible while the shape is assumed,
    and that lands the required rate ABOVE the hit rate the desk is aiming at.
    """
    from scripts.resolve_paper_book import realised_payoff
    book = [{"realised_R": 2.5} for _ in range(8)] + [{"realised_R": -1.1} for _ in range(16)]
    out = realised_payoff(book)
    assert out["state"] == "MEASURED"
    assert out["ratio"] == 2.273
    assert out["breakeven_hit"] > 0.311            # the assumption was flattering
    assert round(out["breakeven_hit"], 3) == 0.379
    assert out["vs_assumption"] < 0                # and says so directionally


# --- how far to let a winner breathe is MEASURED, not chosen ------------------------------------

def _runner_row(entry=100.0, r=2.0):
    return {"direction": "LONG", "entry_ref": entry, "invalidation": entry - r,
            "sizing": {"risk_fraction": 0.06, "leverage": 6.7},
            "management": {"r_price": r,
                           "stages": [{"units": 1.0, "stop": entry - r, "trigger": entry}]}}


def _bars(path):
    out, t = [], 0
    for px in path:
        out.append((t, px, px + 0.4, px - 0.4, px))
        t += 900_000
    return out


def test_trail_width_changes_the_winner_shape():
    """The trail was hardcoded at 1R -- one constant setting the steepest term in the identity."""
    from scripts.resolve_paper_book import walk_ladder
    bars = _bars([100, 102, 104, 106, 108, 110, 109, 107, 105, 104, 104])   # +5R then back to +2R
    tight = walk_ladder(_runner_row(), bars, trail_r=0.5)["realised_R"]
    wide = walk_ladder(_runner_row(), bars, trail_r=3.0)["realised_R"]
    assert tight > wide          # a peak-then-retrace pays the tighter trail
    # ...and the reverse shape pays the wider one, which is why it cannot be settled by opinion
    trend = _bars([100, 102, 101, 104, 103, 106, 105, 108, 107, 110, 112])
    assert (walk_ladder(_runner_row(), trend, trail_r=1.5)["realised_R"]
            > walk_ladder(_runner_row(), trend, trail_r=0.5)["realised_R"])


def test_sweep_ranks_by_log_growth_and_keeps_the_losers_visible():
    """Ranked by E[log], never hit rate or mean R.

    Widening RAISES the winner multiple and LOWERS the hit rate together, so either one alone can
    be improved while compounding falls. The rejected widths stay in the output so the trade-off
    is visible rather than asserted.
    """
    from scripts.resolve_paper_book import TRAIL_WIDTHS, trail_sweep, walk_ladder
    bars = _bars([100, 102, 104, 106, 108, 110, 109, 107, 105, 104, 104])
    swept = []
    for tr in TRAIL_WIDTHS:
        a = walk_ladder(_runner_row(), bars, trail_r=tr)
        swept.append({"trail_r": tr, "realised_R": a["realised_R"],
                      "equity_return": a["equity_return"]})
    s = trail_sweep(swept)
    assert len(s["widths"]) == len(TRAIL_WIDTHS)          # every candidate reported, not just best
    assert s["best_trail_r"] == max(s["widths"], key=lambda r: r["g_per_trade"])["trail_r"]
    assert "E[log]" in s["why"]


def test_sweep_refuses_when_nothing_was_re_walked():
    from scripts.resolve_paper_book import trail_sweep
    assert trail_sweep([])["state"] == "UNMEASURED"
