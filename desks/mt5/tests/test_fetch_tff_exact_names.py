"""fetch_tff matches one exact CFTC contract per slug, never a substring.

The substring match had eur.parquet carrying 189 EURO FX weeks, 184 EUR/GBP cross weeks and
77 EUR/JPY cross weeks; these tests pin the exact-name rule that replaced it.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

pd = pytest.importorskip("pandas")

DESK = Path(__file__).resolve().parents[1]
for _p in (str(DESK), str(DESK.parent.parent)):
    if _p not in sys.path:
        sys.path.insert(0, _p)


def test_exact_names_never_swallow_a_cross_contract() -> None:
    from mt5desk import fetch_tff

    cme = " - CHICAGO MERCANTILE EXCHANGE"
    df = pd.DataFrame({"Market_and_Exchange_Names": ["EURO FX" + cme,
                                                     "EURO FX/JAPANESE YEN XRATE" + cme,
                                                     "EURO FX/BRITISH POUND XRATE" + cme],
                       "Report_Date_as_YYYY-MM-DD": ["2026-08-11"] * 3,
                       "Open_Interest_All": [700000, 21455, 30000]})
    eur = dict(fetch_tff.TARGETS)["eur"]
    got = fetch_tff.pick(df, eur)
    assert list(got["market"]) == ["EURO FX" + cme]
    assert list(fetch_tff.pick(df, dict(fetch_tff.TARGETS)["eurjpy"])["oi"]) == [21455]


