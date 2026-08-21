"""Classification and coverage for the full broker offering.

The hardcoded 32-name list meant nine energy/index symbols were requested, not offered by
Vantage, and silently skipped -- so those asset classes were never tested and nothing recorded
that they were MISSING rather than REJECTED. These pin the classifier and the coverage report
that make that distinction visible.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

_DESK = Path(__file__).resolve().parents[1]
if str(_DESK) not in sys.path:
    sys.path.insert(0, str(_DESK))

from mt5desk.universe import MIN_BARS, Instrument, asset_class, classify_all, coverage  # noqa: E402


@pytest.mark.parametrize("sym,expected", [
    ("XAUUSD", "metal"), ("XAGUSD", "metal"),
    ("BTCUSD", "crypto"), ("ETHUSD", "crypto"),
    ("WTI", "energy"), ("BRENT", "energy"), ("USOIL", "energy"), ("UKOIL", "energy"),
    ("US500", "index"), ("NAS100", "index"), ("JP225", "index"), ("GER40", "index"),
    ("EURUSD", "fx_major"), ("USDJPY", "fx_major"),
    ("EURJPY", "fx_cross"), ("AUDCAD", "fx_cross"), ("CHFJPY", "fx_cross"),
])
def test_symbols_land_in_the_right_class(sym, expected):
    assert asset_class(sym) == expected


def test_metals_are_not_read_as_fx():
    """XAUUSD ends in USD and would classify as FX if FX were tested first. Ordering bug that
    would put gold -- the desk's only live book -- in the wrong bucket on every report."""
    assert asset_class("XAUUSD") == "metal"
    assert asset_class("XAGUSD") == "metal"


def test_unknown_is_reported_not_raised():
    """Broker symbol sets change. An unrecognised name must be surfaced, never crash a sweep."""
    assert asset_class("SOMETHING_NEW_2027") == "unknown"
    assert asset_class("") == "unknown"


def _inst(sym="EURUSD", **kw):
    base = dict(symbol=sym, asset_class=asset_class(sym), bars=5000, contract_size=100_000.0,
                tick_size=1e-5, tick_value=0.62, min_volume=0.01, volume_step=0.01,
                median_spread_pts=16.0)
    base.update(kw)
    return Instrument(**base)


def test_an_uncosted_symbol_is_refused():
    """A zero tick_size or contract_size backtests as though trading were FREE, which produces
    the best-looking cells in the sweep. More dangerous than an absent instrument."""
    assert _inst().usable
    assert not _inst(tick_size=0.0).usable
    assert not _inst(contract_size=0.0).usable


def test_short_history_is_refused():
    assert not _inst(bars=MIN_BARS - 1).usable
    assert _inst(bars=MIN_BARS).usable


def test_spread_cost_is_in_account_currency_not_quote_currency():
    """THE UNITS BUG THIS FENCES. spread * tick_size * contract_size gives the QUOTE currency, so
    a JPY-quoted pair reads ~150x dearer than a USD-quoted one and every JPY cross looks
    unaffordable -- and the JPY crosses are where this desk's surviving edges live. tick_value is
    already in account currency and is the only basis instruments can be compared on."""
    eur = _inst("EURUSD", median_spread_pts=12.0, tick_value=0.8641,
                tick_size=1e-5, contract_size=100_000.0)
    jpy = _inst("CADJPY", median_spread_pts=15.0, tick_value=0.5424,
                tick_size=1e-3, contract_size=100_000.0)
    assert eur.spread_cost_per_lot == pytest.approx(10.37, abs=0.01)
    assert jpy.spread_cost_per_lot == pytest.approx(8.14, abs=0.01)
    # the JPY cross is CHEAPER than the major, which the quote-currency formula inverted
    assert jpy.spread_cost_per_lot < eur.spread_cost_per_lot
    wrong = jpy.median_spread_pts * jpy.tick_size * jpy.contract_size
    assert wrong == pytest.approx(1500.0), "the old formula no longer reproduces its own bug"


def test_unusable_symbols_are_kept_not_dropped():
    """Silently shrinking the universe is how the energy complex went missing. A caller must be
    able to say how much of the offering was excluded and why."""
    got = classify_all({
        "EURUSD": {"bars": 5000, "contract_size": 1e5, "tick_size": 1e-5,
                   "tick_value": 0.62, "median_spread_pts": 16.0},
        "WEIRD": {"bars": 10, "contract_size": 0, "tick_size": 0,
                  "tick_value": 0, "median_spread_pts": 0},
    })
    assert len(got) == 2, "an unusable symbol was dropped instead of reported"
    weird = next(i for i in got if i.symbol == "WEIRD")
    assert not weird.usable
    assert any("insufficient history" in n for n in weird.notes)
    assert any("no cost model" in n for n in weird.notes)


def test_coverage_counts_usable_separately_from_present():
    rep = coverage(classify_all({
        "EURUSD": {"bars": 5000, "contract_size": 1e5, "tick_size": 1e-5,
                   "tick_value": 0.62, "median_spread_pts": 16.0},
        "XAUUSD": {"bars": 5000, "contract_size": 100, "tick_size": 0.01,
                   "tick_value": 1.0, "median_spread_pts": 48.0},
        "BTCUSD": {"bars": 10, "contract_size": 1, "tick_size": 0.01,
                   "tick_value": 1.0, "median_spread_pts": 500.0},
    }))
    assert rep["fx_major"]["usable"] == 1
    assert rep["metal"]["usable"] == 1
    assert rep["crypto"] == {"usable": 0, "unusable": 1}, (
        "a class present but unusable must not read as covered")


def test_the_real_universe_on_disk_classifies_cleanly():
    """Against the actual universe.json, so the classifier is checked on real names.

    THE PIN HERE USED TO BE `len(usable) == 19` AND `stale == [AUDCAD, AUDNZD, NZDCAD]`, and both
    halves were retired by a genuine universe refresh rather than by a regression:

      - the stale summary metadata was fixed upstream, so AUDNZD and NZDCAD now carry real bar
        counts and there is no unusable symbol left to name;
      - EURAUD and GBPAUD were added;
      - AUDCAD WAS DROPPED FROM THE VENUE SNAPSHOT ENTIRELY.

    That last one is not cosmetic and is asserted separately below -- hunt12 published five
    AUDCAD survivors, so the desk holds gated cells naming an instrument the broker no longer
    lists. The count is deliberately NOT re-pinned to 23: a fixed number here fails on every
    legitimate universe refresh and teaches whoever is on shift to edit the number rather than
    read it, which is how the previous pin died. What must hold is that every symbol classifies
    and every symbol is usable; growth is expected.
    """
    import json
    p = _DESK / "data" / "universe" / "universe.json"
    if not p.exists():
        pytest.skip("universe.json not present")
    raw = json.loads(p.read_text(encoding="utf-8"))
    inst = classify_all(raw)
    unknown = [i.symbol for i in inst if i.asset_class == "unknown"]
    assert not unknown, f"unclassified symbols in the live universe: {unknown}"
    usable = sorted(i.symbol for i in inst if i.usable)
    stale = sorted(i.symbol for i in inst if not i.usable)
    assert not stale, (
        f"symbols present but unusable: {stale}. Every symbol carried real bar counts at the "
        f"2026-08-20 refresh, so an unusable one is stale summary metadata to chase, not a pin "
        f"to widen")
    assert len(usable) >= 19, f"universe shrank below the 2026-08 floor: {usable}"


def test_audcad_left_the_universe_and_its_survivors_are_therefore_unpriceable():
    """A gated cell naming an instrument the venue no longer lists cannot reach capital.

    hunt12 published five AUDCAD survivors. AUDCAD is absent from the current snapshot, so any
    consumer that does `meta[sym]` on a survivor list raises KeyError mid-run -- which is how
    `portfolio_projection` died rather than reporting a smaller book. The refusal has to be
    explicit and named (L1.28a): the sleeve is UNPRICEABLE, which is a real answer, and is not
    the same as the sleeve being absent or having failed.
    """
    import json
    p = _DESK / "data" / "universe" / "universe.json"
    if not p.exists():
        pytest.skip("universe.json not present")
    raw = json.loads(p.read_text(encoding="utf-8"))
    assert "AUDCAD" not in raw, (
        "AUDCAD is back in the venue snapshot -- delete this test and re-admit its hunt12 "
        "survivors through the universal gate rather than assuming the old results still stand")
