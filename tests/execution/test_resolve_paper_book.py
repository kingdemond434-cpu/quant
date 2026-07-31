

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
