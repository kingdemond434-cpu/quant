"""`macro_fair_value`: three macro fair values as dated events the sealed gauntlet can judge.

  0. each basis fires on a constructed event, on the named side, in the named direction;
  1. each basis refuses BY NAME when its input is absent (a TypeError the builder names);
  2. no basis uses a value before its knowable instant (one look-ahead test per basis);
  3. the family, its proposer and the hourly leg are wired, and the proposer writes its report.
All inputs are synthetic; nothing touches the network.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

DESK = Path(__file__).resolve().parents[1]
ROOT = DESK.parent.parent
for _p in (str(DESK / "scripts"), str(DESK), str(ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from mt5desk import family_macro_fair_value as F  # noqa: E402


def _bars(n: int = 6000, end: str = "2026-06-30 23:00", seed: int = 5,
          base: float = 1.1) -> pd.DataFrame:
    idx = pd.date_range(end=end, periods=n, freq="h", tz="UTC")
    rng = np.random.default_rng(seed)
    close = pd.Series(base * np.exp(np.cumsum(rng.normal(0, 0.0006, n))), index=idx)
    return pd.DataFrame({"open": close.shift(1).fillna(close.iloc[0]), "high": close * 1.001,
                         "low": close * 0.999, "close": close, "tick_volume": 100.0}, index=idx)


@pytest.fixture
def axes(tmp_path, monkeypatch):
    monkeypatch.setattr(F, "AXES", tmp_path)
    F._points.cache_clear()
    F._stamped.cache_clear()
    F._vintage.cache_clear()

    def write(name: str, doc: dict) -> Path:
        path = tmp_path / f"{name}.json"
        path.write_text(json.dumps(doc), "utf-8")
        F._points.cache_clear()
        F._stamped.cache_clear()
        F._vintage.cache_clear()
        return path
    yield write
    F._points.cache_clear()
    F._stamped.cache_clear()
    F._vintage.cache_clear()


# ------------------------------------------------------------------------- net liquidity
_WEDS = pd.date_range("2025-06-04", "2026-06-24", freq="W-WED", tz="UTC")
_SPIKE = pd.Timestamp("2026-04-01", tz="UTC")           # a Wednesday


def _fred(stamped: bool, spike: float = 400_000.0, after: float = 0.0) -> dict:
    # bounded weekly noise: a sine never reaches 3 sigma of its own trailing history
    walcl, level = [], 7_000_000.0
    for i, d in enumerate(_WEDS):
        level += 5_000 * np.sin(1.3 * i) + (spike if d == _SPIKE else 0.0)
        level += after if d > _SPIKE else 0.0
        walcl.append(level)

    def pts(days, vals):
        out = []
        for d, v in zip(days, vals, strict=True):
            p = {"d": str(d.date()), "v": float(v)}
            if stamped:
                p["knowable_at"] = str((d + pd.Timedelta(days=1)).date())
            out.append(p)
        return out
    return {"series": {
        "WALCL": {"points": pts(_WEDS, walcl), "vintage": "first_release"},
        "WTREGEN": {"points": pts(_WEDS, [700_000.0] * len(_WEDS)), "vintage": "first_release"}}}


def test_net_liquidity_fires_on_a_constructed_injection_after_the_thursday_print(axes):
    axes("fred", _fred(stamped=True))
    nl = F.net_liquidity()
    # RRP is in billions: 7.0m - 0.7m - 100bn*1000 per print, keyed on Thursday
    assert nl.index[0] == _WEDS[0] + pd.Timedelta(days=1)
    sig = F.family_macro_fair_value(_bars(), basis="net_liquidity", move="up", min_abs=3.0,
                                    direction="long", window=20, hold_bars=24)
    assert len(sig) == 1 and sig[0].side == 1
    # knowable Thursday 2026-04-02 (16:30 ET): entry from Friday 00:00 UTC + 3h broker offset
    floor = pd.Timestamp("2026-04-03 03:00", tz="UTC")
    assert floor <= sig[0].time < floor + pd.Timedelta(hours=2)
    assert F.family_macro_fair_value(_bars(), basis="net_liquidity", move="down", min_abs=3.0,
                                     direction="long", window=20) == []


def test_net_liquidity_without_a_knowable_stamp_waits_a_publication_day(axes):
    axes("fred", _fred(stamped=False))
    sig = F.family_macro_fair_value(_bars(), basis="net_liquidity", move="up", min_abs=3.0,
                                    direction="short", window=20)
    assert len(sig) == 1 and sig[0].side == -1
    assert sig[0].time >= pd.Timestamp("2026-04-03 03:00", tz="UTC")


def test_net_liquidity_never_reads_a_print_before_it_is_knowable(axes):
    """Prints after the cutoff can change nothing that entered before it."""
    axes("fred", _fred(stamped=True))
    a = F.family_macro_fair_value(_bars(), basis="net_liquidity", move="up", min_abs=3.0,
                                  direction="long", window=20)
    axes("fred", _fred(stamped=True, after=900_000.0))   # every later week a huge injection
    b = F.family_macro_fair_value(_bars(), basis="net_liquidity", move="up", min_abs=3.0,
                                  direction="long", window=20)
    cut = pd.Timestamp("2026-04-03 03:00", tz="UTC")
    assert [s.time for s in a if s.time <= cut] == [s.time for s in b if s.time <= cut]
    assert a and all(s.time >= cut for s in a)
    # the z of print k reads only the changes before k
    z1 = F.prior_z(pd.Series(np.r_[np.arange(30.0), 99.0]), 10)
    z2 = F.prior_z(pd.Series(np.r_[np.arange(30.0), 1e9]), 10)
    assert z1.iloc[:-1].equals(z2.iloc[:-1])


def test_net_liquidity_refuses_by_name_when_a_series_is_absent(axes):
    doc = _fred(stamped=True)
    del doc["series"]["WTREGEN"]
    axes("fred", doc)
    with pytest.raises(F.MacroFairValueUnavailable, match=F.ABSENT_FRED) as exc:
        F.family_macro_fair_value(_bars(), basis="net_liquidity", direction="long")
    assert "WTREGEN" in str(exc.value) and isinstance(exc.value, TypeError)
    axes("fred", {"series": {}})                     # the tree's real shape on a failed fetch
    with pytest.raises(F.MacroFairValueUnavailable, match="WALCL, WTREGEN"):
        F.net_liquidity()


def test_a_latest_revised_fred_frame_never_reaches_a_cell(axes):
    """Audit #904: FRED serves the latest revision. A series the axis does not declare
    first-release or vintage-stable refuses by name, whatever its values."""
    doc = _fred(stamped=True)
    del doc["series"]["WTREGEN"]["vintage"]
    axes("fred", doc)
    with pytest.raises(F.MacroFairValueUnavailable, match=F.UNVINTAGED_FRED) as exc:
        F.family_macro_fair_value(_bars(), basis="net_liquidity", direction="long")
    assert "WTREGEN" in str(exc.value) and "WALCL" not in str(exc.value).split(" in ")[0]
    doc["series"]["WTREGEN"]["vintage"] = "latest"
    axes("fred", doc)
    with pytest.raises(F.MacroFairValueUnavailable, match=F.UNVINTAGED_FRED):
        F.net_liquidity()
    doc["series"]["WTREGEN"]["vintage"] = "vintage_stable"
    axes("fred", doc)
    assert len(F.net_liquidity()) == len(_WEDS)


# ---------------------------------------------------------------------- rate differential
def _bis(pair: str = "AUDUSD", hike: str = "2026-03-18", step: float = 0.5) -> dict:
    days = pd.date_range("2025-06-01", "2026-06-30", freq="D")
    # a monthly row: not a day, ignored by the reader
    rows = [{"symbol": pair, "knowable_at": "2025-06", "carry_differential": 9.9}]
    for d in days:
        v = 1.0 + (step if d >= pd.Timestamp(hike) else 0.0)
        rows.append({"symbol": pair, "knowable_at": str(d.date()), "carry_differential": v})
    rows.append({"symbol": "EURUSD", "knowable_at": "2026-03-18", "carry_differential": -5.0})
    return {"symbols": [pair, "EURUSD"], "rows": rows}


def test_rate_differential_fires_toward_the_widened_advantage(axes):
    axes("bis", _bis())
    sig = F.family_macro_fair_value(_bars(), basis="rate_differential", symbol="AUDUSD",
                                    move="up", min_abs=0.25, direction="long",
                                    lookback_days=21, hold_bars=24)
    assert len(sig) == 1 and sig[0].side == 1
    floor = pd.Timestamp("2026-03-19 03:00", tz="UTC")
    assert floor <= sig[0].time < floor + pd.Timedelta(hours=2)
    assert F.family_macro_fair_value(_bars(), basis="rate_differential", symbol="AUDUSD",
                                     move="down", min_abs=0.25, direction="short") == []


def test_rate_differential_never_reads_a_day_before_it_is_knowable(axes):
    axes("bis", _bis(hike="2026-03-18"))
    a = F.family_macro_fair_value(_bars(), basis="rate_differential", symbol="AUDUSD",
                                  move="up", min_abs=0.25, direction="long", lookback_days=21)
    # entering ON the decision day would have been a look-ahead: the day carries no hour
    assert a and all(s.time >= pd.Timestamp("2026-03-19 03:00", tz="UTC") for s in a)
    axes("bis", _bis(hike="2026-05-20"))            # a later hike moves nothing before it
    b = F.family_macro_fair_value(_bars(), basis="rate_differential", symbol="AUDUSD",
                                  move="up", min_abs=0.25, direction="long", lookback_days=21)
    assert all(s.time >= pd.Timestamp("2026-05-21 03:00", tz="UTC") for s in b)


def test_rate_differential_refuses_by_name_for_a_pair_the_axis_does_not_carry(axes):
    axes("bis", _bis())
    with pytest.raises(F.MacroFairValueUnavailable, match=F.ABSENT_BIS):
        F.family_macro_fair_value(_bars(), basis="rate_differential", symbol="USDCAD",
                                  direction="long")
    (F.AXES / "bis.json").unlink()
    F._points.cache_clear()
    with pytest.raises(TypeError, match=F.ABSENT_BIS):
        F.family_macro_fair_value(_bars(), basis="rate_differential", symbol="AUDUSD",
                                  direction="long")


# ------------------------------------------------------------------------- terms of trade
def _tot_frames(n: int = 3000, shock_at: int = 2500, shock: float = 0.03):
    idx = pd.date_range(end="2026-06-30 23:00", periods=n, freq="h", tz="UTC")
    rng = np.random.default_rng(7)
    lc, lg, lo = (np.cumsum(rng.normal(0, 0.003, n)) for _ in range(3))
    y = 0.4 * lc + 0.3 * lg + 0.2 * lo + rng.normal(0, 0.0005, n)
    y[shock_at:] += shock                               # AUD rich against its basket from here

    def frame(logp, base):
        c = pd.Series(base * np.exp(logp), index=idx)
        return pd.DataFrame({"open": c, "high": c * 1.0005, "low": c * 0.9995, "close": c,
                             "tick_volume": 1.0}, index=idx)
    return frame(y, 0.66), {"XCUUSD": frame(lc, 4.5), "XAUUSD": frame(lg, 2300.0),
                            "XTIUSD": frame(lo, 75.0)}


def test_terms_of_trade_fades_a_constructed_dislocation(axes):
    d, peers = _tot_frames()
    sig = F.family_macro_fair_value(d, basis="terms_of_trade", symbol="AUDUSD", move="up",
                                    min_abs=6.0, direction="short", window=480, hold_bars=24,
                                    peers=peers)
    shock_bar = d.index[2500]
    assert sig and sig[0].side == -1
    # the residual of bar t uses bar t's close: the first entry is the bar AFTER the shock bar
    assert sig[0].time == d.index[2501]
    assert all(s.time > shock_bar for s in sig)


def test_terms_of_trade_never_fits_on_the_bar_it_scores(axes):
    """Truncating the future changes no residual z already computed."""
    d, peers = _tot_frames()
    full = F.tot_residual_z(d, "AUDUSD", 240, peers)
    cut = 1800
    part = F.tot_residual_z(d.iloc[:cut], "AUDUSD", 240,
                            {k: v.iloc[:cut] for k, v in peers.items()})
    common = part.index
    assert len(common) > 1000
    np.testing.assert_allclose(full.loc[common].to_numpy(), part.to_numpy(), rtol=1e-6,
                               atol=1e-6)
    # the first scored bar is `window` bars in: nothing is scored on its own fit
    assert full.index[0] == d.index[240]
    # USDCAD's inverted quote is the CAD reading negated, from the same fit
    cad = d.copy()
    cad[["open", "high", "low", "close"]] = 1.0 / d[["open", "high", "low", "close"]]
    usd_z = F.tot_residual_z(cad, "USDCAD", 240, peers)
    aud_like = F.tot_residual_z(d.rename(columns={}), "USDCAD", 240, peers)
    np.testing.assert_allclose(usd_z.to_numpy(), -aud_like.to_numpy(), rtol=1e-5, atol=1e-5)


def test_terms_of_trade_refuses_by_name_without_its_basket(axes, monkeypatch):
    d, peers = _tot_frames()
    from mt5desk import family_inputs
    monkeypatch.setattr(family_inputs, "bars_named", lambda s, like: None)
    with pytest.raises(F.MacroFairValueUnavailable, match=F.ABSENT_TOT) as exc:
        F.family_macro_fair_value(d, basis="terms_of_trade", symbol="AUDUSD",
                                  direction="short", peers={"XAUUSD": peers["XAUUSD"]})
    assert "XCUUSD" in str(exc.value) and "XTIUSD" in str(exc.value)
    with pytest.raises(TypeError, match=F.ABSENT_TOT):
        F.family_macro_fair_value(d, basis="terms_of_trade", symbol="EURUSD", direction="long")


# ----------------------------------------------------------------------------- the wiring
def test_unknown_recipe_values_refuse_quietly_and_side_is_ignored(axes):
    d = _bars()
    for kw in ({"basis": ""}, {"basis": "vibes"}, {"basis": "net_liquidity", "move": "both"},
               {"basis": "net_liquidity", "direction": "sideways"},
               {"basis": "rate_differential", "symbol": ""},
               {"basis": "net_liquidity", "min_abs": -1.0}):
        assert F.family_macro_fair_value(d, **kw) == []
    axes("bis", _bis())
    a = F.family_macro_fair_value(d, side=-1, basis="rate_differential", symbol="AUDUSD",
                                  min_abs=0.25, direction="long", lookback_days=21)
    assert a and all(s.side == 1 for s in a)


def test_the_family_and_its_proposer_are_wired():
    from mt5desk.families_orthogonal import FAMILY_INPUTS, ORTHOGONAL_FAMILIES

    from research import axis_registry, hourly_cycle, orthogonal_sweep
    assert ORTHOGONAL_FAMILIES["macro_fair_value"] is F.family_macro_fair_value
    assert "macro_fair_value" in FAMILY_INPUTS
    assert "macro_fair_value" in orthogonal_sweep.NOT_SOURCED_HERE
    assert axis_registry.FAMILY_TABLE["macro_fair_value"][0] == "macro_release"
    assert "macro_fair_value_proposer" in hourly_cycle.LEG_BUDGET_SEC
    assert "macro_fair_value_proposer" in hourly_cycle.LEG_DEPARTMENT
    src = (DESK / "research" / "hourly_cycle.py").read_text("utf-8")
    assert "research/macro_fair_value_proposer.py" in src
    from libs.research.layers import LEG_LAYER
    assert LEG_LAYER["macro_fair_value_proposer"] == "prediction"
    assert "desks/mt5/mt5desk/family_macro_fair_value.py" in (
        ROOT / "ops" / "money_closure.txt").read_text("utf-8").split()


def test_the_proposer_parks_absent_bases_by_name_and_writes_its_report(axes, tmp_path,
                                                                        monkeypatch):
    from research import macro_fair_value_proposer as P
    from research import proposer_common as pc
    axes("fred", {"series": {}})
    axes("bis", _bis())
    d, peers = _tot_frames(n=3000)
    frames = {"AUDUSD": d, **peers}
    monkeypatch.setattr(P, "REPORT", tmp_path / "MACRO_FAIR_VALUE_PROPOSER.json")
    monkeypatch.setattr(P, "MIN_BARS", 500)
    meta = {s: {"asset_class": "Forex", "currency_profit": "USD"}
            for s in ("AUDUSD", "NZDUSD", "USDCAD", "EURUSD")}
    meta.update({s: {"asset_class": "Commodities", "currency_profit": "USD"}
                 for s in ("XAUUSD", "XCUUSD", "XTIUSD")})
    monkeypatch.setattr(pc, "universe_meta", lambda: meta)
    monkeypatch.setattr(pc, "bars", lambda s: frames.get(s))
    monkeypatch.setattr(pc, "cost_frac", lambda s, m, c: 0.0001)
    from research import universe_policy as up
    monkeypatch.setattr(up, "may_hypothesise", lambda s, family=None: True)
    # the real screen needs 30 trades; a stand-in exercises the charge and the ranking
    monkeypatch.setattr(pc, "screen", lambda d, sig, cost, unf: (
        {"t_gross": 3.0 + len(sig) / 100, "clears_cost": True, "n_independent": len(sig)}
        if sig else None))
    rep = P.run(budget_s=120, donate=False)
    doc = json.loads(P.REPORT.read_text("utf-8"))
    assert doc["status"] == rep["status"] == "OK"
    assert doc["bases"]["net_liquidity"]["parked_reason"] == F.ABSENT_FRED
    assert doc["bases"]["rate_differential"]["symbols"] == ["AUDUSD", "EURUSD"]  # axis roster
    assert set(doc["bases"]["terms_of_trade"]["symbols"]) == {"AUDUSD", "NZDUSD", "USDCAD"}
    # AUDUSD carries rate_differential (2 x 2 x 2) and terms_of_trade (2 x 2 x 2); only variants
    # that fired reach the screen, and every one of them is charged on every row
    assert isinstance(doc["tests_run"], int) and 1 <= doc["tests_run"] <= 16
    assert doc["skipped"].get("EURUSD") == "no or too few H1 bars"
    assert all(r["n_tests_sweep"] == doc["tests_run"] for r in doc["proposals"])
    # everything parked: UNMEASURED, never zero
    axes("bis", {"symbols": [], "rows": []})
    monkeypatch.setattr(pc, "bars", lambda s: None)
    rep = P.run(budget_s=30, donate=False)
    assert rep["status"] == "UNMEASURED" and rep["tests_run"] == "UNMEASURED"
    assert rep["bases"]["terms_of_trade"]["parked_reason"] == F.ABSENT_TOT
