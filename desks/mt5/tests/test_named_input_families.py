"""A lead_lag driver and a triangle's legs reach the family from their NAMES, and a triangle minted
without legs gets them from the quote set.

Measured 2026-09-30 on a 6,000-cell census of the docket committed 2026-09-29: not one lead_lag or
triangle cell was judgeable. The judge's `build_cell` (sealed) has no branch for either family, so
it passed `driver_symbol` / `leg_b_symbol` through as strings and never loaded the frames, and
1,720 of 1,796 triangle rows named no legs at all. Every such cell read UNKNOWN / "never fires".
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

DESK = Path(__file__).resolve().parents[1]
ROOT = DESK.parent.parent
for _p in (str(DESK), str(ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from mt5desk import family_inputs  # noqa: E402
from mt5desk.family_lead_lag import family_lead_lag  # noqa: E402
from mt5desk.family_triangle import family_triangle  # noqa: E402
from research import discovery_compiler as dc  # noqa: E402
from research import orthogonal_sweep  # noqa: E402
from research import transformation_miners as TM  # noqa: E402


def _bars(n: int = 2_000, freq: str = "1h", seed: int = 0, level: float = 1.0) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    idx = pd.date_range("2024-01-01", periods=n, freq=freq, tz="UTC")
    close = level * np.exp(np.cumsum(rng.normal(0, 0.002, n)))
    return pd.DataFrame({"open": close, "high": close * 1.001, "low": close * 0.999,
                         "close": close}, index=idx)


@pytest.fixture
def store(monkeypatch):
    """A fake parquet store: {(symbol, chart): frame}, read by `orthogonal_sweep._bars`."""
    held: dict[tuple[str, str], pd.DataFrame] = {}
    asked: list[tuple[str, str]] = []

    def _fake(symbol: str, timeframe: str = "H1"):
        asked.append((symbol, timeframe))
        return held.get((symbol, timeframe))

    monkeypatch.setattr(orthogonal_sweep, "_bars", _fake)
    return held, asked


def test_bars_named_reads_the_frames_own_chart(store) -> None:
    held, asked = store
    m15 = _bars(freq="15min")
    held[("USDJPY", "M15")] = _bars(freq="15min", seed=1)
    assert family_inputs.bars_named("USDJPY", m15) is held[("USDJPY", "M15")]
    assert asked == [("USDJPY", "M15")], "never the H1 default under an M15 cell"
    assert family_inputs.bars_named("GBPUSD", m15) is None, "no bars stays None"
    assert family_inputs.bars_named("", m15) is None


def test_lead_lag_named_driver_fires_exactly_as_a_handed_driver(store) -> None:
    held, _ = store
    target, driver = _bars(seed=2), _bars(seed=3)
    held[("EURUSD", "H1")] = driver
    handed = family_lead_lag(target, driver=driver, driver_symbol="EURUSD", entry_z=1.0)
    named = family_lead_lag(target, driver_symbol="EURUSD", entry_z=1.0)
    assert handed, "the fixture must fire for the comparison to mean anything"
    assert [(s.time, s.side) for s in named] == [(s.time, s.side) for s in handed]
    assert family_lead_lag(target, driver_symbol="NOSUCH", entry_z=1.0) == [], \
        "a driver with no bars still refuses"
    assert family_lead_lag(target, entry_z=1.0) == [], "no driver named still refuses"


def test_triangle_named_legs_fire_exactly_as_handed_legs(store) -> None:
    held, _ = store
    b, c = _bars(seed=4, level=1.1), _bars(seed=5, level=150.0)
    rng = np.random.default_rng(6)
    a = b.copy()
    a["close"] = b["close"] * c["close"] * np.exp(rng.normal(0, 0.0005, len(b)))
    a["open"], a["high"], a["low"] = a["close"], a["close"] * 1.001, a["close"] * 0.999
    held[("EURUSD", "H1")], held[("USDJPY", "H1")] = b, c
    kw = {"sign_b": 1, "sign_c": 1, "entry_z": 1.5}
    handed = family_triangle(a, leg_b=b, leg_c=c, **kw)
    named = family_triangle(a, leg_b_symbol="EURUSD", leg_c_symbol="USDJPY", **kw)
    assert handed
    assert [(s.time, s.side) for s in named] == [(s.time, s.side) for s in handed]
    assert family_triangle(a, leg_b_symbol="EURUSD", **kw) == [], "one leg is no triangle"


META = {s: {"asset_class": "Forex", "bars": 40_000}
        for s in ("EURUSD", "USDJPY", "EURJPY", "GBPUSD", "GBPJPY", "EURGBP")}
META["XAUUSD"] = {"asset_class": "Metals", "bars": 40_000}


def _ctx(bars=lambda s, c: True) -> TM.Context:
    return TM.Context(instruments={"forex": [s for s in META if s != "XAUUSD"],
                                   "metals": ["XAUUSD"]},
                      families=frozenset({"triangle"}), defaults={},
                      bars_available=bars, lane_ok=lambda s: True)


def _child(symbol: str, chart: str = "H1", **params: object) -> dict:
    return {"family": "triangle", "symbol": symbol, "chart": chart, "params": dict(params),
            "content_hash": "0" * 32}


def test_a_legless_triangle_is_closed_through_the_quote_set() -> None:
    out = dc.complete_inputs(_child("EURJPY", session="ny"), _ctx(), META)
    p = out["params"]
    assert (p["leg_b_symbol"], p["leg_c_symbol"]) == ("EURUSD", "USDJPY"), "USD pivot first"
    assert (p["sign_b"], p["sign_c"]) == (1, 1)
    assert p["session"] == "ny", "the rest of the identity is kept"
    assert out["input_completed"] == "leg_b_symbol"
    assert out["content_hash"] != "0" * 32
    usd = dc.complete_inputs(_child("EURUSD"), _ctx(), META)["params"]
    assert {usd["leg_b_symbol"], usd["leg_c_symbol"]} == {"EURJPY", "USDJPY"} or \
        {usd["leg_b_symbol"], usd["leg_c_symbol"]} == {"EURGBP", "GBPUSD"}
    # the named legs must actually imply the target: log(EURUSD) = sb*log(b) + sc*log(c)
    from research.triangle_miner import fx_pairs, orient
    tri = orient("EURUSD", usd["leg_b_symbol"], usd["leg_c_symbol"], fx_pairs(META))
    assert tri is not None and (tri.sign_b, tri.sign_c) == (usd["sign_b"], usd["sign_c"])


def test_a_triangle_leg_must_hold_bars_on_the_childs_chart() -> None:
    ctx = _ctx(bars=lambda s, c: not (s == "USDJPY" and c == "M15"))
    p = dc.complete_inputs(_child("EURJPY", chart="M15"), ctx, META)["params"]
    assert "USDJPY" not in (p["leg_b_symbol"], p["leg_c_symbol"])
    assert {p["leg_b_symbol"], p["leg_c_symbol"]} == {"EURGBP", "GBPJPY"}


def test_named_or_unclosable_triangles_are_left_exactly_as_written() -> None:
    named = _child("EURJPY", leg_b_symbol="EURGBP", leg_c_symbol="GBPJPY")
    assert dc.complete_inputs(named, _ctx(), META) is named
    metal = _child("XAUUSD")
    assert dc.complete_inputs(metal, _ctx(), META) is metal, "not a currency pair: no triangle"
    lonely = _child("EURJPY")
    assert dc.complete_inputs(lonely, _ctx(bars=lambda s, c: False), META) is lonely
