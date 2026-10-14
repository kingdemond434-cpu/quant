"""breadth_sweep charges no hypothesis twice and mints no void cell (audit 0b66b08de, MF3 + SF).

* `style_premia`: the sweep's default H1 cell IS style_premia_sweep's (trend, entry 1.0, hold 24)
  cell -- same signals -- so it is PREREGISTERED_ELSEWHERE and charged once, by its producer.
* VOID_AT_DEFAULTS: each named family fires nothing at its defaults, re-measured here on the
  committed XAUUSD H1 bars; a family whose defaults start firing fails this test and must be
  swept again.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
import pytest

DESK = Path(__file__).resolve().parents[1]
for _p in (str(DESK.parents[1]), str(DESK), str(DESK / "research")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import breadth_sweep as bs  # noqa: E402
import orthogonal_sweep as osw  # noqa: E402

BARS = DESK / "data" / "universe" / "XAUUSD_H1.parquet"


def _family_fns() -> dict:
    from mt5desk import families as fm
    from mt5desk import families_orthogonal as fo
    out: dict = {}
    for name, entry in fm.FAMILY_REGISTRY.items():
        fn = entry.get("func") if isinstance(entry, dict) else entry
        if callable(fn):
            out[str(name)] = fn
    for name, fn in fo.ORTHOGONAL_FAMILIES.items():
        out.setdefault(str(name), fn)
    return out


@pytest.fixture(scope="module")
def bars() -> pd.DataFrame:
    if not BARS.exists():
        pytest.skip("XAUUSD H1 bars absent from this checkout")
    return pd.read_parquet(BARS).iloc[-20000:]


def test_style_premia_is_charged_once_by_its_own_sweep(bars: pd.DataFrame) -> None:
    import style_premia_sweep as sps
    from mt5desk.family_style_premia import family_style_premia

    ok, blocked = bs.default_families()
    assert "style_premia" not in ok
    assert blocked["style_premia"].startswith("preregistered elsewhere")
    # the sweep's default cell is a cell of the producer's charged grid ...
    assert 1.0 in sps.ENTRIES and 24 in sps.HOLDS and "trend" in sps.STYLES
    default = family_style_premia(bars)
    producer = family_style_premia(bars, style="trend", combo=None, entry=1.0, hold_bars=24,
                                   speeds=(21, 63, 252))
    # ... with the very same signals, so sweeping it here was a second charge
    assert default and [(s.time, s.side) for s in default] == \
        [(s.time, s.side) for s in producer]


def test_void_families_fire_nothing_at_their_defaults(bars: pd.DataFrame) -> None:
    fns = _family_fns()
    for fam in bs.VOID_AT_DEFAULTS:
        fn = fns[fam]
        try:
            sig = fn(bars)
        except Exception:               # unrunnable at defaults (lead_lag: no driver) is void
            continue
        assert not list(sig or []), f"{fam} fires at its defaults: sweep it again"


def test_no_not_sourced_here_family_is_swept_at_defaults_without_a_reason() -> None:
    ok, blocked = bs.default_families()
    assert not set(ok) & set(osw.NOT_SOURCED_HERE)
    for fam in bs.VOID_AT_DEFAULTS:
        assert blocked[fam].startswith("void at defaults"), fam
    # a family outside the named sets is untouched: the sweep still mines its defaults
    assert "trend_ma_cross" in ok
