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


# ======================== A TICKER ROOT IS A WORD, NOT A PREFIX ========================
#
# THE DEFECT, measured on the trading box 2026-09-24. The root lists were matched with a bare
# `startswith`/`in`, so a root that happened to open an English word claimed the instrument:
# UnionPacific, UnitedHealth and UnitedParcelService read `crypto` ("UNI" = Uniswap),
# GoldmanSachs read `metal` ("GOLD") and Nike read `index` ("NIK" = Nikkei). Five US share CFDs
# in the hypothesis-discovery lane, which the two-lane order (principal 2026-09-06) puts in the
# news/earnings lane -- and `libs/portfolio/robust_elog._asset_class` POOLS sleeves by this same
# class for correlation shrinkage, so UnionPacific was borrowing BTCUSD's mean and GoldmanSachs
# was borrowing gold's.

@pytest.mark.parametrize("sym", [
    "UnionPacific", "UnitedHealth", "UnitedParcelService",   # read `crypto` -- "UNI"
    "GoldmanSachs",                                          # read `metal`  -- "GOLD"
    "Nike",                                                  # read `index`  -- "NIK"
])
def test_share_cfds_named_after_a_ticker_root_are_equities(sym):
    """By name: these five are the measured casualties and a later edit may not lose them."""
    assert asset_class(sym) == "equity"


@pytest.mark.parametrize("sym,expected", [
    ("BTCUSD", "crypto"), ("ETHUSD", "crypto"), ("ADAUSD", "crypto"),
    ("AVAXUSD", "crypto"), ("BCHUSD", "crypto"), ("UNIUSD", "crypto"),
    ("XAUUSD", "metal"), ("XAGEUR", "metal"), ("GOLD", "metal"),
    ("UST05Y", "bond"), ("UST10Y", "bond"), ("UKGILT", "bond"),
    ("EUSTX50", "index"), ("GER40", "index"), ("NETH25", "index"),
    ("SUGARRAW", "soft"), ("UKCOCOA", "soft"), ("USCOCOA", "soft"),
])
def test_the_real_ticker_roots_still_reach_their_class(sym, expected):
    """The other direction, in the same breath: fixing the false positives by deleting the true
    positives is the failure mode. `UNIUSD` is the Uniswap CFD and stays crypto; `SUGARRAW`,
    `UKCOCOA` and `USCOCOA` are why the soft list must keep matching mid-symbol."""
    assert asset_class(sym) == expected


@pytest.mark.parametrize("name", [
    "Solaris", "SolarEdge",     # SOL
    "Unilever", "Uniswap",      # UNI
    "Dotdash",                  # DOT
    "LinkedIn",                 # LINK
    "Ethan",                    # ETH
    "GoldFields",               # GOLD
])
def test_a_crypto_ticker_inside_a_company_name_is_not_crypto(name):
    """THE RULE, not the five symbols: the match must be WORD-BOUNDARY anchored.

    None of these is on the broker's list today, which is the point -- a symbol exception list is
    right on the day it is written and silently wrong the day the broker adds a name. The case the
    broker already supplies is the boundary: a root followed by a lower-case letter is the opening
    of a word, never a ticker.
    """
    assert asset_class(name) == "equity"


def test_a_ticker_root_is_bounded_at_both_ends_of_a_broker_code():
    """`UST|05Y` is a Treasury note and `UST|EC` is the Nasdaq index. Only the TAIL tells them
    apart, and the prefix-only repair of 2026-08-28 could not: it read USTEC as a bond."""
    assert asset_class("UST05Y") == "bond"
    assert asset_class("USTEC") == "index"


def test_no_symbol_the_registry_calls_an_equity_reads_as_a_hypothesis_class():
    """The general property, driven over MetaTrader's OWN registry rather than a symbol list.

    This is what would have caught the defect the day the whole-broker expansion landed: every
    single-name share the broker declares must read as a share to the desk's classifier too, or
    the trial budget the two-lane order reserved for FX and metals is spent on equities anyway.
    """
    import json
    p = _DESK / "data" / "universe" / "universe.json"
    if not p.exists():
        pytest.skip("universe.json not present")
    registry = json.loads(p.read_text(encoding="utf-8"))
    leaked = {
        sym: asset_class(sym)
        for sym, row in registry.items()
        if isinstance(row, dict)
        and str(row.get("asset_class") or row.get("category") or "").strip().lower().startswith(
            ("equit", "share", "stock"))
        and asset_class(sym) != "equity"
    }
    assert not leaked, (
        "the pattern classifier hands these single-name shares to a hypothesis class, so they "
        f"spend trial budget the two-lane order reserved for FX and metals: {leaked}")


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
    """Against the live universe.json -- the whole broker offering, so the classifier is checked
    on real names. This test used to pin `usable == 19` from the 22-symbol era; the law is now
    the WHOLE offering ("maximum classes, no limitations"), so the pins are floors and breadth --
    coverage ratchets UP (L1.50) and an exact count would make growth read as a failure."""
    import json
    p = _DESK / "data" / "universe" / "universe.json"
    if not p.exists():
        pytest.skip("universe.json not present")
    inst = classify_all(json.loads(p.read_text(encoding="utf-8")))
    unknown = [i.symbol for i in inst if i.asset_class == "unknown"]
    assert not unknown, f"unclassified symbols in the live universe: {unknown}"
    usable = [i for i in inst if i.usable]
    assert len(usable) >= 240, f"usable coverage may only ratchet UP, got {len(usable)}"
    # Usable breadth for the classes whose cost model is measured today. Index and equity rows
    # arrived from the whole-broker expansion WITHOUT tick_value (the collector never asked MT5
    # for it -- fixed in expand_universe.py the same day), so demanding their usable-breadth
    # here would assert data that is still being collected; they are pinned as PRESENT, and the
    # moment the collection lands these move into the usable loop below and RATCHET (L1.50).
    # RATCHET (L1.50). The 2026-08-27 collection brought the whole broker offering with
    # tick_value attached -- 251 symbols, 248 costed -- so equity, index, soft and bond moved
    # from "present but uncostable" to USABLE and may never silently fall back.
    classes = {i.asset_class for i in usable}
    for cls in ("fx_major", "fx_cross", "fx_exotic", "metal", "crypto",
                "equity", "index", "soft", "bond"):
        assert cls in classes, f"asset class {cls} has zero usable symbols"
    unknown_usable = [i.symbol for i in usable if i.asset_class == "unknown"]
    assert not unknown_usable, f"tradable symbols the classifier cannot name: {unknown_usable}"
