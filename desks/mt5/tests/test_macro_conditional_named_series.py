"""A `macro_conditional` cell conditions on the series its identity NAMES (2026-11-10).

Global data's audit: the gauntlet and the forward clock called `_macro_series(index)` with no
name, so a DGS10 cell, a VIX cell and an HY-spread cell all rebuilt on the first available series
-- the dollar -- while each was charged as its own trial. The forward path and the FAMILY ITSELF
now read through `orthogonal_sweep.macro_for_cell`, which honours the name, the cell's own
publication lag, and refuses BY NAME what it cannot honour instead of falling back to the dollar.
The sealed gauntlet is untouched: it still hands the dollar, and a named cell ignores it."""
from __future__ import annotations

import contextlib
import importlib
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

DESK = Path(__file__).resolve().parents[1]
for _p in (str(DESK / "research"), str(DESK), str(DESK.parents[1])):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import orthogonal_sweep as osw  # noqa: E402

DAYS = pd.date_range("2020-01-01", periods=900, freq="D", tz="UTC")


def _rows(seed: int) -> list[list]:
    v = np.cumsum(np.random.default_rng(seed).normal(size=len(DAYS)))
    return [[d.strftime("%Y-%m-%d"), float(x)] for d, x in zip(DAYS, v, strict=True)]


@pytest.fixture
def fred(monkeypatch: pytest.MonkeyPatch) -> dict:
    doc = {"series": {"DTWEXBGS": _rows(1), "DGS10": _rows(2), "VIXCLS": _rows(3),
                      "UNRATE": _rows(4), "DFII10": _rows(5)}}
    # BOTH NAMES OF THE ONE MODULE: the desk imports it as `research.orthogonal_sweep` where
    # the package is on the path and as `orthogonal_sweep` where only the folder is, and under
    # pytest both are, so they are two module objects reading one file.
    mods = [osw]
    with contextlib.suppress(ImportError):
        mods.append(importlib.import_module("research.orthogonal_sweep"))
    for mod in mods:
        monkeypatch.setattr(mod, "_read",
                            lambda p: doc if p.name == "fred_macro.json" else None)
    return doc


IDX = pd.date_range("2022-01-03", periods=2000, freq="h", tz="UTC")


def test_a_named_cell_reads_its_own_series_not_the_dollar(fred: dict) -> None:
    dollar, _ = osw.macro_for_cell(IDX, {"input_source": "fred:DTWEXBGS"})
    ten_year, why = osw.macro_for_cell(IDX, {"input_source": "fred:DGS10"})
    vix, _ = osw.macro_for_cell(IDX, {"macro_series": "VIXCLS"})
    real, _ = osw.macro_for_cell(IDX, {"input_source": "DFII10"})       # the event graph's form
    assert why == "ok"
    for s in (ten_year, vix, real):
        assert s is not None and not np.allclose(s.to_numpy(), dollar.to_numpy(),
                                                 equal_nan=True)
    pd.testing.assert_series_equal(ten_year, osw._macro_series(IDX, "DGS10"))


def test_an_unnamed_cell_keeps_the_legacy_default(fred: dict) -> None:
    for params in ({}, {"input_source": "fred:macro"}, {"input_source": ""}):
        got, why = osw.macro_for_cell(IDX, params)
        assert why == "ok"
        pd.testing.assert_series_equal(got, osw._macro_series(IDX))
    assert osw._macro_series_name() == "DTWEXBGS"


def test_a_name_it_cannot_honour_is_refused_by_name_never_the_dollar(fred: dict) -> None:
    for params, word in (({"input_source": "fred:UNRATE"}, "UNRATE"),
                         ({"input_source": "fred:DGS2"}, "DGS2"),
                         ({"input_source": "fred:DGS10", "transform": "zscore"}, "zscore")):
        got, why = osw.macro_for_cell(IDX, params)
        assert got is None and word in why


def test_the_cells_publication_lag_is_honoured_and_never_under_a_day(fred: dict) -> None:
    one, _ = osw.macro_for_cell(IDX, {"input_source": "fred:DGS10"})
    zero, _ = osw.macro_for_cell(IDX, {"input_source": "fred:DGS10", "publication_lag_d": 0})
    late, _ = osw.macro_for_cell(IDX, {"input_source": "fred:DGS10", "publication_lag_d": 45})
    pd.testing.assert_series_equal(one, zero)
    pd.testing.assert_series_equal(late, osw._macro_series(IDX, "DGS10", lag_d=45))
    assert not late.equals(one)


def _bars_frame() -> pd.DataFrame:
    rng = np.random.default_rng(11)
    c = 1.1 * np.exp(np.cumsum(rng.normal(0, 1e-3, len(IDX))))
    df = pd.DataFrame({"open": np.concatenate([[c[0]], c[:-1]]), "close": c}, index=IDX)
    df["high"] = df[["open", "close"]].max(axis=1) * 1.0003
    df["low"] = df[["open", "close"]].min(axis=1) * 0.9997
    return df


def test_the_family_reads_its_own_named_series_whatever_it_is_handed(fred: dict) -> None:
    """THE SEALED GAUNTLET STILL HANDS EVERY CELL THE DOLLAR. A cell that names its series must
    not trade on it: the family rebuilds the named one itself and ignores the handed default."""
    from mt5desk.families_orthogonal import family_macro_conditional as fam
    df = _bars_frame()
    dollar = osw._macro_series(IDX)

    def stance(sigs: list) -> list:
        return [(s.time, s.side) for s in sigs]

    # a series whose regime differs from the dollar's on these bars, so the two bets differ
    base = stance(fam(df, macro=dollar))
    name = next(n for n in ("DGS10", "VIXCLS", "DFII10")
                if stance(fam(df, macro=osw._macro_series(IDX, n))) != base)
    own = fam(df, macro=osw._macro_series(IDX, name))
    handed_dollar = fam(df, macro=dollar, macro_series=name)
    assert own and stance(handed_dollar) == stance(own) != stance(fam(df, macro=dollar))
    # the sweep's own identity keys are honoured, not refused: lag and transform go to the reader
    lagged = fam(df, macro=dollar, macro_series=name, publication_lag_d=45,
                 transform="trailing_pct_rank")
    assert stance(lagged) == stance(fam(df, macro=osw._macro_series(IDX, name, lag_d=45)))
    # an unnamed cell with the sweep's lag and transform is the legacy dollar cell
    legacy = fam(df, macro=None, publication_lag_d=1, transform="trailing_pct_rank")
    assert stance(legacy) == stance(fam(df, macro=dollar))
    # and what the reader cannot honour is a build failure BY NAME, never the dollar
    for bad in ({"macro_series": "UNRATE"}, {"macro_series": "DGS2"},
                {"macro_series": "DGS10", "transform": "zscore"}):
        with pytest.raises(ValueError, match="macro_conditional"):
            fam(df, macro=dollar, **bad)


def test_the_sealed_call_keeps_the_keys_the_family_now_takes() -> None:
    """`cell_modifiers.split` moves a key to the refused modifiers only when the family does not
    accept it, so accepting them is what turns NOT_RUN_MODIFIER into a judged cell."""
    from mt5desk import cell_modifiers
    from mt5desk.families_orthogonal import family_macro_conditional as fam
    params = {"macro_series": "DGS10", "publication_lag_d": 1, "transform": "trailing_pct_rank",
              "regime_high": 0.7}
    kwargs, mods = cell_modifiers.split(fam, params)
    assert kwargs == params and not mods and cell_modifiers.refusal(mods) is None


def test_the_forward_path_reads_through_the_shared_reader() -> None:
    inputs = (DESK / "mt5desk" / "family_inputs.py").read_text("utf-8")
    assert "inputs.macro_for_cell(h1.index, params)" in inputs
    assert "inputs._macro_series(h1.index)" not in inputs


def test_every_daily_series_is_swept_or_named_as_not(fred: dict, monkeypatch: pytest.MonkeyPatch
                                                     ) -> None:
    import breadth_sweep as bs
    assert set(bs.MACRO_SERIES_SWEPT) | set(bs.MACRO_SERIES_NOT_SWEPT) == set(
        osw.DAILY_MACRO_SERIES)
    assert not set(bs.MACRO_SERIES_SWEPT) & set(bs.MACRO_SERIES_NOT_SWEPT)
    grid = bs.READY["macro_conditional"]["grid"]
    named = [g["macro_series"] for g in grid if "macro_series" in g]
    assert set(named) == set(bs.MACRO_SERIES_SWEPT)
    unnamed = [g for g in grid if "macro_series" not in g]
    # the legacy cells are untouched, so no existing row is re-minted or re-charged
    assert unnamed == [{"regime_high": h, "side_in_high": s, "rr": 2.0, "ttl_bars": 96,
                        "atr_n": 20} for h in (0.5, 0.7) for s in (1, -1)]
    assert len(grid) == len(unnamed) * (1 + len(bs.MACRO_SERIES_SWEPT))
    # a series the store does not hold is set aside by name, not sent to the judge to fail
    monkeypatch.setattr(bs, "_MACRO_HELD", {})
    bs.LAST_SET_ASIDE.clear()
    assert bs._macro_held("DGS10") and not bs._macro_held("DGS2")
    assert not bs._testable("macro_conditional", {"macro_series": "DGS2"})
    assert any(r["verdict"] == "INPUT_NOT_HELD" for r in bs.LAST_SET_ASIDE.values())
    bs.LAST_SET_ASIDE.clear()
    # AN UNREADABLE STORE IS ONE ROW, however many named cells it set aside
    for mod in {id(m): m for m in (osw, sys.modules.get("research.orthogonal_sweep"))
                if m is not None}.values():
        monkeypatch.setattr(mod, "_read", lambda p: None)
    monkeypatch.setattr(bs, "_MACRO_HELD", {})
    for name in bs.MACRO_SERIES_SWEPT:
        for chart in ("H1", "H4"):
            assert not bs._testable("macro_conditional",
                                    {"macro_series": name, "timeframe": chart})
    rows = [r for r in bs.LAST_SET_ASIDE.values() if r["family"] == "macro_conditional"]
    assert len(rows) == 1 and rows[0]["verdict"] == "INPUT_STORE_UNREADABLE"
    assert rows[0]["cells"] == 2 * len(bs.MACRO_SERIES_SWEPT)
    bs.LAST_SET_ASIDE.clear()


def test_a_row_naming_its_series_only_by_input_source_is_counted_by_name() -> None:
    """The sealed gauntlet pops `input_source` before the family sees it, so such a row still
    rebuilds on the dollar. Until the evaluator can be re-signed it is at least VISIBLE."""
    import breadth_sweep as bs
    docket = [
        {"symbol": "EURUSD", "family": "macro_conditional", "params": {}},
        {"symbol": "EURUSD", "family": "macro_conditional",
         "params": {"input_source": "fred:DTWEXBGS", "transform": "trailing_pct_rank"}},
        {"symbol": "EURUSD", "family": "macro_conditional", "params": {"input_source": "macro"}},
        {"symbol": "EURUSD", "family": "macro_conditional",
         "params": {"input_source": "fred:DGS10", "macro_series": "DGS10"}},
        {"symbol": "XAUUSD", "family": "macro_conditional",
         "params": {"input_source": "fred:DFII10"}},
        {"symbol": "XAUUSD", "family": "carry", "params": {"input_source": "fred:DGS10"}},
        "not a row",
    ]
    got = bs.count_macro_input_source_only(docket)
    assert got["rows"] == 1
    assert got["sample"] == [{"symbol": "XAUUSD", "input_source": "fred:DFII10"}]
    bs.MACRO_INPUT_SOURCE_ONLY.update(rows=None, sample=[])


def test_the_forward_call_drops_what_the_reader_consumed() -> None:
    from mt5desk.family_inputs import runtime_call_params, strip_identity_keys
    params = {"input_source": "fred:DGS10", "macro_series": "DGS10", "publication_lag_d": 45,
              "transform": "trailing_pct_rank", "regime_high": 0.7, "timeframe": "H1"}
    for call in (strip_identity_keys("macro_conditional", params),
                 runtime_call_params("macro_conditional", params)):
        assert call == {"regime_high": 0.7}
    # another family still sees them, so cell_modifiers keeps refusing them there by name
    assert "transform" in strip_identity_keys("carry", params)
