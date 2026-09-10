"""A certificate is only as good as the cost it was judged at, and the cost has an hour on it.

WHAT THIS GUARDS. `entry_timing` compares two numbers the desk already owns -- the spread
`mt5desk/engine.py:124` bills every backtest (`universe.json -> median_spread_pts`) against the
spread the tape measured at each hour (`cost_surface.json -> hours[H].p50`) -- and asks whether
each cell's OWN `stress_costs` gate, which ran at 3x, ever reached the hours the cell can fire
in. On the live canon it found 15 of 66 certificates outside their own gate, EURCHF at 30x, and
6 symbols charged ZERO spread.

THE TESTS THAT MATTER ARE THE ONES ABOUT WHAT IT REFUSES TO DO:

    IT NEVER SETS ITS OWN BAR. `STRESS_MULTIPLE` is the gauntlet's 3x. A test pins the constant,
    because the moment this file picks its own number it stops being a check on a gate that ran
    and becomes a second, unreviewed hurdle -- and a hurdle nobody agreed to is how a desk starts
    refusing trades for reasons no one can name.

    IT NEVER LEAVES THE SESSION. The selector IS the mechanism: an Asian-session range breakout
    entered an hour later is a different and uncertified strategy. Every hour it prices must come
    from the certificate's own window.

    IT NEVER READS AN UNMEASURED HOUR AS CHEAP. `cost_surface` returns None for a cell it did not
    measure precisely so a caller cannot read one by accident. A window with no measured hour is
    UNMEASURED, never COVERED (L1.28a).

    ZERO CHARGED IS A BUG, NOT A CHEAP SYMBOL. Six symbols are billed 0.0 points. No multiple of
    zero exists, and reporting them as infinitely understated -- or as covered -- would both be
    wrong; they get their own count and their own sentence.

    IT READS THE REGISTRY, NOT THE SURFACE'S CACHED COPY OF IT. `cost_surface.json` caches
    `pooled_median_spread_pts` at build time and it has drifted: GBPJPY reads 1.0 there against
    13.0 in the registry today. The engine bills the registry, so a cost claim checked against
    the stale cache would find fault with symbols that are fine and clear ones that are not.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))
_DESK = _ROOT / "desks" / "mt5"
for _p in (str(_DESK), str(_DESK / "research")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from desks.mt5.research import entry_timing as et  # noqa: E402


def _desk(tmp: Path, *, hours: dict[int, float | None], charged: float | None,
          selector: str = "asia", symbol: str = "TESTFX") -> Path:
    """A throwaway desk carrying one symbol, one certificate and a surface with given hours."""
    data = tmp / "desks" / "mt5" / "data"
    (data / "universe").mkdir(parents=True, exist_ok=True)
    surface = {"schema": "cost-surface-1", "symbols": {symbol: {"hours": {
        str(h): ({"status": "MEASURED", "p50": v} if v is not None else {"status": "UNMEASURED"})
        for h, v in hours.items()}}}}
    (data / "cost_surface.json").write_text(json.dumps(surface), encoding="utf-8")
    meta = {"symbol": symbol}
    if charged is not None:
        meta["median_spread_pts"] = charged
    (data / "universe" / "universe.json").write_text(
        json.dumps({"symbols": {symbol: meta}}), encoding="utf-8")
    (data / "UNIVERSAL_SURVIVORS.canon.json").write_text(json.dumps({"survivors": {
        "k": {"cell": f"{symbol}.fam", "sym": symbol,
              "shadow_spec": {"symbol": symbol, "selector": selector}}}}), encoding="utf-8")
    return tmp


def test_the_bar_is_the_gauntlets_and_not_this_files():
    """The moment this picks its own number it becomes a hurdle nobody agreed to."""
    assert et.STRESS_MULTIPLE == 3.0, (
        "STRESS_MULTIPLE mirrors external_gauntlet's stress_costs `exp_x3`. Changing it here "
        "would silently disagree with a gate that already ran on every certificate")


def test_every_priced_hour_comes_from_the_certificates_own_window():
    """The selector IS the mechanism; an hour outside it prices a strategy nobody certified."""
    for selector, (start, live) in et.WINDOWS.items():
        hours = et.entry_hours(selector)
        assert hours[0] == start
        assert len(hours) == live + 1
        assert all(0 <= h <= 23 for h in hours)
    assert et.entry_hours("not_a_session") == ()
    assert et.entry_hours("") == ()


def test_an_unknown_selector_prices_nothing_rather_than_defaulting_to_asia(tmp_path):
    """65 of 66 survivors are asia, so a default would be right 65 times and silently wrong once."""
    root = _desk(tmp_path, hours=dict.fromkeys(range(24), 10.0), charged=1.0, selector="mystery")
    rows = et.assess(root)
    assert rows[0].verdict == et.UNMEASURED
    assert "not a window this desk executes" in rows[0].why
    assert rows[0].hours == ()


def test_a_window_with_no_measured_hour_is_unmeasured_never_covered(tmp_path):
    """Scoring a window on the hours that happened to be measured reports cheapest where it is
    only best-known."""
    root = _desk(tmp_path, hours=dict.fromkeys(range(24)), charged=1.0)
    row = et.assess(root)[0]
    assert row.verdict == et.UNMEASURED
    assert row.understatement is None


def test_a_dear_hour_inside_the_window_is_uncovered_and_names_the_hour(tmp_path):
    """This is the live finding: EURCHF fires at hour 7 at 30x what it was charged."""
    hours = dict.fromkeys(range(24), 2.0)
    hours[9] = 30.0                      # inside the asia window (7..19)
    root = _desk(tmp_path, hours=hours, charged=1.0)
    row = et.assess(root)[0]
    assert row.verdict == et.UNCOVERED
    assert row.understatement == 30.0
    assert "hour 9" in row.why and "3.0x" in row.why


def test_a_dear_hour_outside_the_window_does_not_condemn_the_cell(tmp_path):
    """Hour 0 is the dearest hour on most of this universe and no asia entry can reach it."""
    hours = dict.fromkeys(range(24), 2.0)
    hours[0] = 500.0                     # outside asia's 7..19
    root = _desk(tmp_path, hours=hours, charged=1.0)
    row = et.assess(root)[0]
    assert row.verdict == et.COVERED
    assert row.understatement == 2.0
    assert 0 not in row.hours


def test_exactly_at_the_stress_multiple_is_covered(tmp_path):
    """The gate ran AT 3x, so 3x is inside what it tested and only above it is not."""
    root = _desk(tmp_path, hours=dict.fromkeys(range(24), 3.0), charged=1.0)
    assert et.assess(root)[0].verdict == et.COVERED
    root2 = _desk(tmp_path / "b", hours=dict.fromkeys(range(24), 3.001), charged=1.0)
    assert et.assess(root2)[0].verdict == et.UNCOVERED


def test_zero_charged_is_a_cost_bug_and_not_a_cheap_symbol(tmp_path):
    """Six live symbols are billed 0.0 points. No multiple of zero exists in either direction."""
    root = _desk(tmp_path, hours=dict.fromkeys(range(24), 14.0), charged=0.0)
    row = et.assess(root)[0]
    assert row.verdict == et.UNMEASURED
    assert "no spread at all" in row.why and "cost bug" in row.why
    assert row.understatement is None
    gaps = et.symbol_gaps(root)
    assert gaps and gaps[0]["zero_charged"] is True


def test_a_symbol_missing_from_the_registry_is_said_not_assumed(tmp_path):
    root = _desk(tmp_path, hours=dict.fromkeys(range(24), 14.0), charged=None)
    row = et.assess(root)[0]
    assert row.verdict == et.UNMEASURED
    assert "not in the universe registry" in row.why


def test_the_charged_figure_comes_from_the_registry_not_the_surfaces_stale_copy(tmp_path):
    """GBPJPY reads 1.0 in the cached copy and 13.0 in the registry. The engine bills the
    registry, so checking against the cache finds fault with symbols that are fine."""
    root = _desk(tmp_path, hours=dict.fromkeys(range(24), 13.0), charged=13.0)
    surface_path = root / "desks" / "mt5" / "data" / "cost_surface.json"
    doc = json.loads(surface_path.read_text(encoding="utf-8"))
    doc["symbols"]["TESTFX"]["pooled_median_spread_pts"] = 1.0      # the drifted cache
    surface_path.write_text(json.dumps(doc), encoding="utf-8")
    row = et.assess(root)[0]
    assert row.charged == 13.0, "the stale cached copy was read instead of the registry"
    assert row.verdict == et.COVERED


def test_in_window_ratio_prices_the_timing_and_not_the_symbol(tmp_path):
    hours = dict.fromkeys(range(24), 2.0)
    hours[8], hours[0] = 8.0, 999.0
    root = _desk(tmp_path, hours=hours, charged=4.0)
    row = et.assess(root)[0]
    assert row.in_window_ratio == 4.0, "the ratio must ignore hour 0, which asia cannot reach"


def test_census_counts_and_the_rule_states_the_restraint(tmp_path):
    hours = dict.fromkeys(range(24), 2.0)
    hours[9] = 30.0
    doc = et.census(_desk(tmp_path, hours=hours, charged=1.0))
    assert doc["n_certificates"] == 1 and doc["gate_never_reached"] == 1
    assert doc["stress_multiple"] == 3.0
    assert "vetoes" in doc["rule"] and "allocator" in doc["rule"]
    assert doc["worst_cells"][0]["understatement"] == 30.0


def test_it_never_sizes_vetoes_or_writes_a_registry():
    """A module that quietly refused an hour would be reducing the book by fiat, and one that
    rewrote a charged cost would retroactively re-judge every certificate that used it."""
    src = (_ROOT / "desks" / "mt5" / "research" / "entry_timing.py").read_text(encoding="utf-8")
    for forbidden in ("universe.json\", \"w", "lot", "volume", "risk_pct", "subprocess",
                      "def veto", "def size", "def block"):
        assert forbidden not in src, f"entry_timing reached for {forbidden}"
    # It writes exactly one path, and it is a report.
    assert src.count("write_text(") == 1
    assert et.OUT_REL.startswith("desks/mt5/reports/")


@pytest.mark.parametrize("selector", sorted(et.WINDOWS))
def test_no_window_wraps_onto_itself(selector):
    """A 12-hour TTL cannot cover the same hour twice, or a dear hour would be double counted."""
    hours = et.entry_hours(selector)
    assert len(set(hours)) == len(hours)
