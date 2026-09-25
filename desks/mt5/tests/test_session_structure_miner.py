"""A SESSION IS DERIVED FROM THE INSTRUMENT'S OWN BARS, OR IT IS NOT MINTED.

The defect this miner exists to stop, measured on the box 2026-09-23: 1,174 of 2,248
`session_range_breakout` verdicts NEVER FIRED, and 255 more fired too rarely to judge. A cell
whose range window is inherited from gold is aimed at hours another instrument may not trade in
at all -- BTCUSD's quiet block is 07-14 broker time, so gold's window builds its range through
BTCUSD's active stretch and takes the breakout at its quietest hour.

The tests pull in both directions on purpose. One half insists a real quiet run produces cells
aimed at THAT instrument. The other insists that an instrument with no measurable structure, an
untradeable one, or a single-name share mints NOTHING -- because the cheapest way to look
productive here is to mint a guessed window everywhere, which is exactly what produced the 1,174.
"""

from __future__ import annotations

import sys
from pathlib import Path

_DESK = Path(__file__).resolve().parents[1]
_ROOT = _DESK.parent.parent
for _p in (str(_DESK), str(_DESK / "research"), str(_ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from research import session_structure_miner as ssm  # noqa: E402

UNMEASURED = ssm.UNMEASURED


def _profile(quiet: set[int], loud: float = 0.010, calm: float = 0.001) -> dict:
    return {"status": "MEASURED",
            "median_range_by_hour": {h: (calm if h in quiet else loud) for h in range(24)},
            "bars_by_hour": dict.fromkeys(range(24), 400), "n_bars": 9600}


# ------------------------------------------------------------------ deriving the real window
def test_a_daytime_quiet_run_becomes_an_explicit_window() -> None:
    """BTCUSD's shape: quiet 07-13, so the range is 07-14 and the breakout is at 14:00."""
    w = ssm.derive_window(_profile({7, 8, 9, 10, 11, 12, 13}))
    assert w["status"] == "MEASURED"
    assert w["range_start"] == 7 and w["range_end"] == 14
    assert w["signal_at"] == 14
    assert w["wraps_midnight"] is False and w["truncated_hours"] == []


def test_a_wrapping_quiet_run_keeps_its_post_midnight_half_and_says_what_it_lost() -> None:
    """USDJPY's shape: quiet 20-23 and 00-05. The family cannot express a wrapping window, so the
    truncation must be NAMED rather than silently producing an empty range."""
    w = ssm.derive_window(_profile({20, 21, 22, 23, 0, 1, 2, 3, 4, 5}))
    assert w["status"] == "MEASURED"
    assert w["wraps_midnight"] is True
    assert w["range_end"] is None, "the `hour < range_start` form is the only one that works here"
    assert w["range_start"] == 6 and w["signal_at"] == 6
    assert w["truncated_hours"] == [20, 21, 22, 23]
    assert "wraps midnight" in w["truncation_why"]


def test_the_derived_window_is_never_empty_for_the_family() -> None:
    """The failure that produced 1,174 dead cells: `range_end < range_start` builds NO range."""
    for quiet in ({7, 8, 9, 10}, {20, 21, 22, 23, 0, 1, 2}, {1, 2, 3, 4, 5, 6}):
        w = ssm.derive_window(_profile(quiet))
        if w["status"] != "MEASURED":
            continue
        if w["range_end"] is None:
            assert w["range_start"] > 0, "`hour < 0` is empty"
        else:
            assert w["range_end"] > w["range_start"], (
                "(hour >= range_start) & (hour < range_end) is EMPTY when range_end <= "
                "range_start -- this cell could never fire")


# --------------------------------------------------------------- refusing to guess a window
def test_an_instrument_with_no_quiet_run_mints_nothing() -> None:
    flat = {"status": "MEASURED",
            "median_range_by_hour": dict.fromkeys(range(24), 0.004),
            "bars_by_hour": dict.fromkeys(range(24), 400), "n_bars": 9600}
    w = ssm.derive_window(flat)
    assert w["status"] == UNMEASURED
    assert ssm.cells_for("FLATUSD", w) == [], "no structure is UNMEASURED, never a guessed window"


def test_a_two_hour_lull_is_not_a_session() -> None:
    w = ssm.derive_window(_profile({3, 4}))
    assert w["status"] == UNMEASURED and "quiet run" in w["why"]


def test_an_absent_profile_is_unmeasured_not_a_default_window() -> None:
    w = ssm.derive_window({"status": UNMEASURED, "why": "no bars on this host"})
    assert w["status"] == UNMEASURED
    assert ssm.cells_for("NOBARS", w) == []


# ------------------------------------------------------------------- what gets minted, and how
def test_the_boundary_is_swept_not_fixed() -> None:
    w = ssm.derive_window(_profile({7, 8, 9, 10, 11, 12, 13}))
    cells = ssm.cells_for("BTCUSD", w)
    hours = {c["params"]["signal_at"] for c in cells}
    assert hours == {14, 15}, "the derived hour AND its neighbour, or a one-hour fit is invisible"
    assert len(cells) == 2 * len(ssm.RR_SWEEP) * len(ssm.WAIT_BARS_SWEEP)
    for c in cells:
        assert c["family"] == "session_range_breakout"
        assert c["symbols"] == ["BTCUSD"]
        assert isinstance(c["params"], dict) and c["params"]["range_start"] == 7


def test_minted_rows_are_ordinary_exact_recipe_donations() -> None:
    """No privileged path: the compiler's EXACT_RECIPE branch needs family + params + symbols."""
    w = ssm.derive_window(_profile({7, 8, 9, 10, 11, 12, 13}))
    for c in ssm.cells_for("ETHUSD", w):
        assert isinstance(c.get("family"), str)
        assert isinstance(c.get("params"), dict)
        assert isinstance(c.get("symbols"), list) and c["symbols"]
        assert c.get("mechanism"), "a donated row states its mechanism, not just its parameters"


def test_no_gate_threshold_or_cost_is_touched() -> None:
    """The bar never moves. This miner aims cells; it must not price or judge them."""
    text = (Path(ssm.__file__)).read_text(encoding="utf-8")
    for forbidden in ("gate_spec", "dsr_threshold", "n_trials", "cost_multiplier",
                      "UNIVERSAL_SURVIVORS", "pbo_max"):
        assert f'"{forbidden}"' not in text and f"'{forbidden}'" not in text, (
            f"{forbidden} appears as a value this module handles; the gates and the canonical "
            f"certificate store are read-only to everything outside the sealed gauntlet")


# --------------------------------------------------------------------- instrument eligibility
def test_untradeable_and_single_name_instruments_are_refused_by_name() -> None:
    registry = {
        "EURJPY": {"trade_mode": 4, "category": "Forex Crosses"},
        "SUGAR": {"trade_mode": 3, "category": "Soft Commodities"},
        "Apple": {"trade_mode": 4, "category": "US Shares"},
    }
    keep, why = ssm.eligible_symbols(registry)
    assert "SUGAR" in why and "CLOSE_ONLY" in why["SUGAR"], (
        "93 session_range_breakout verdicts died at symbol_eligibility on CLOSE_ONLY symbols; "
        "compute spent on an instrument the account cannot open is spent for nothing")
    assert "Apple" in why, "single names are traded on news, never hunted statistically"
    assert "EURJPY" not in why or "no H1 bars" in why.get("EURJPY", ""), (
        f"an eligible FX cross must not be refused for any other reason: {why.get('EURJPY')}")
    assert isinstance(keep, list)
