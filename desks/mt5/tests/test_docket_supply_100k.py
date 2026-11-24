"""Docket supply >= 100k new buildable, non-exotic cells a day (2026-11-24).

`breadth_sweep` minted every default family at ONE parameter point per (symbol, chart, session),
a grid that was exhausted within days, so it added ~0 cells a pass. These tests pin the widening:
the parameter-variant walk, the same-class relative_value pairs, the exotic ban, the pace and its
missed-growth line, and that every minted cell is buildable by the judge's own checks.

Every input is synthetic or redirected into `tmp_path`; nothing here reads or writes box state.
"""
from __future__ import annotations

import inspect
import json
import sys
from contextlib import contextmanager
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

_DESK = Path(__file__).resolve().parents[1]
for _p in (str(_DESK), str(_DESK / "research"), str(_DESK.parent.parent)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from research import breadth_sweep as bs  # noqa: E402
from research import gauntlet_buildability as gb  # noqa: E402
from research import job_lock  # noqa: E402
from research import universe_policy as up  # noqa: E402


def _key(r: dict) -> str:
    return json.dumps([r.get("symbol"), r.get("family"), r.get("params") or {}],
                      sort_keys=True, default=str)


def _frame(n: int = 2500, seed: int = 3) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    c = 100 * np.exp(np.cumsum(rng.normal(0, 0.002, n)))
    idx = pd.date_range("2024-01-01", periods=n, freq="h", tz="UTC")
    return pd.DataFrame({"open": c, "high": c * 1.001, "low": c * 0.999, "close": c,
                         "tick_volume": 100, "spread": 2}, index=idx)


@pytest.fixture
def registry(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    uni = tmp_path / "universe.json"
    uni.write_text(json.dumps({
        "EURUSD": {"asset_class": "Forex"}, "GBPUSD": {"asset_class": "Forex"},
        "USDJPY": {"asset_class": "Forex"}, "USDZAR": {"asset_class": "Forex Exotics"},
        "USDMXN": {"asset_class": "Forex Exotics"}, "US500": {"asset_class": "Indices"},
        "NAS100": {"asset_class": "Indices"}, "XAUUSD": {"asset_class": "Commodities"},
        "AAPL": {"asset_class": "Equities"},
    }), "utf-8")
    monkeypatch.setattr(up, "UNIVERSE", uni)
    up._registry.cache_clear()
    yield uni
    up._registry.cache_clear()


# ------------------------------------------------------------------ the variant points
def test_variants_move_lengths_jointly_and_never_touch_calendar_or_categorical_knobs() -> None:
    vs = bs.param_variants("trend_ma_cross")
    assert vs[0] == {} and len(vs) == 15, vs
    d = bs._family_defaults("trend_ma_cross")
    for v in vs[1:]:
        p = {**d, **v}
        assert p["fast_ema"] < p["slow_ema"], v           # the ordering a joint scale keeps
        assert set(v) <= set(d), "a variant only carries keys in the family's signature"
    # Hours stay where the family put them; only lengths and rr move.
    for v in bs.param_variants("asia_momentum"):
        assert not {"asia_start", "asia_end"} & set(v), v
    for v in bs.param_variants("lvc_asia_london"):
        assert not [k for k in v if "minute" in k], v
    # No duplicate points, and a family with nothing to scale keeps only its defaults.
    assert len({json.dumps(v, sort_keys=True) for v in vs}) == len(vs)
    assert bs.param_variants("regime_split") == [{}]


def test_every_minted_variant_binds_the_judges_call_exactly_as_its_defaults_do() -> None:
    """The judge_build_preflight check, applied to every variant point of every default family:
    Python must be able to bind `fn(h1, side=1, **params)` -- and a variant never adds a
    required-parameter miss, a chart refusal or a family verdict the default did not have."""
    sweepable, _blocked = bs.default_families()
    table = gb._family_table()
    for fam in sweepable:
        fn = table[fam]
        sig = inspect.signature(fn)
        base = gb.cell_verdict(fam, {})[0]
        for v in bs.param_variants(fam):
            assert gb.cell_verdict(fam, v)[0] == base, (fam, v)
            if base != gb.BUILDABLE:
                continue
            # The judge calls fn(h1, side=1, **p) and falls back to fn(h1, **p) on TypeError.
            try:
                sig.bind(None, side=1, **v)
            except TypeError:
                sig.bind(None, **v)                          # raises on any unbound name


def test_variants_never_raise_where_the_defaults_build() -> None:
    """Built for real on synthetic bars: every price-only family that builds at its defaults
    also builds at every variant point (no exception a variant alone introduces)."""
    bars = _frame()
    supplied = gb.supplied_families()
    table = gb._family_table()
    sweepable, _blocked = bs.default_families()
    checked = 0
    for fam in sorted(sweepable):
        if fam in supplied or gb.information_class(fam) != gb.PRICE_ONLY:
            continue
        if gb.cell_verdict(fam, {})[0] != gb.BUILDABLE:
            continue
        fn = table[fam]

        def call(_fn=fn, **p):
            try:
                return _fn(bars, side=1, **p)
            except TypeError as exc:                         # the judge's own fallback
                if "side" not in str(exc):
                    raise
                return _fn(bars, **p)
        try:
            call()
        except Exception:
            continue                                         # not buildable here at defaults
        for v in bs.param_variants(fam)[1:]:
            call(**v)
        checked += 1
    assert checked >= 40, checked


# ------------------------------------------------------------------ the exotic ban
def test_exotics_are_never_swept_and_core_holds_none(registry: Path, tmp_path: Path,
                                                     monkeypatch: pytest.MonkeyPatch) -> None:
    assert bs.is_exotic("USDZAR") and bs.is_exotic("usdmxn") and not bs.is_exotic("EURUSD")
    assert not {"USDZAR", "USDMXN"} & set(bs.CORE)
    bars = tmp_path / "bars"
    bars.mkdir()
    for s in ("EURUSD", "USDZAR", "USDMXN", "US500", "AAPL"):
        (bars / f"{s}_H1.parquet").write_bytes(b"")
    monkeypatch.setattr(bs, "UNIVERSE", bars)
    syms = bs._with_bars()
    assert "EURUSD" in syms and "US500" in syms
    assert not {"USDZAR", "USDMXN", "AAPL"} & set(syms)
    assert bs._equities_with_bars() == ["AAPL"]
    # A pair or factor leg that is exotic is refused too.
    spec = {"pairs": (("EURUSD", "USDZAR"), ("EURUSD", "GBPUSD"))}
    assert bs._targets("relative_value", spec, ["EURUSD", "GBPUSD"]) == [
        ("EURUSD", {"peer_symbol": "GBPUSD"})]


def test_relative_value_is_widened_to_every_same_class_pair(registry: Path) -> None:
    syms = ["EURUSD", "GBPUSD", "USDJPY", "USDZAR", "US500", "NAS100", "XAUUSD"]
    pairs = bs.class_pairs(syms)
    assert ("EURUSD", "GBPUSD") in pairs and ("NAS100", "US500") in pairs
    assert not [p for p in pairs if "USDZAR" in p], "no exotic leg"
    assert ("EURUSD", "US500") not in pairs, "cross-class residuals are cross_asset_residual's"
    targets = bs._targets("relative_value", bs.READY["relative_value"], syms)
    assert ("NAS100", {"peer_symbol": "US500"}) in targets


# ------------------------------------------------------------------ the walk
def _walk_env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(bs, "_charts_for", lambda sym: ["M15", "H1", "D1"])


def test_the_walk_mints_only_never_seen_buildable_cells_and_resumes_at_its_cursor(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _walk_env(tmp_path, monkeypatch)
    fams = ["trend_ma_cross", "mean_reversion_rsi", "relative_value"]
    seen: set[str] = set()
    w1 = bs.VariantWalk(fams, ["EURUSD", "XAUUSD"], cursor=0, budget_s=60, per_run=50)
    first = w1(seen, 10_000, _key)
    assert len(first) == 50, "the pace binds below the room it was offered"
    for r in first:
        tf = (r["params"] or {}).get("timeframe", "H1")
        assert gb.cell_verdict(r["family"], r["params"], tf)[0] == gb.BUILDABLE, r
        assert r["family"] != "relative_value", "a family that needs a peer is never walked bare"
    w2 = bs.VariantWalk(fams, ["EURUSD", "XAUUSD"], cursor=w1.state()["next"], budget_s=60,
                        per_run=50)
    second = w2(seen, 10_000, _key)
    k1, k2 = {_key(r) for r in first}, {_key(r) for r in second}
    assert k2 and not k1 & k2, "the next pass mints new cells, never the same ones"
    assert w2.state()["start"] == w1.state()["next"]
    # Walked to exhaustion, every point appears once and the cursor wraps.
    w3 = bs.VariantWalk(fams, ["EURUSD", "XAUUSD"], cursor=0, budget_s=60, per_run=10**9)
    rest = w3(seen, 10**9, _key)
    allk = k1 | k2 | {_key(r) for r in rest}
    assert len(allk) == len(first) + len(second) + len(rest)
    assert w3.state()["wrapped"] and w3(seen, 10**9, _key) == []
    ranks = {r["variant_rank"] for r in rest}
    assert max(ranks) >= 14, "every variant rank is reached"


def test_cross_sectional_books_reach_share_cfds_and_nothing_else_does(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _walk_env(tmp_path, monkeypatch)
    fam = sorted(up.CROSS_SECTIONAL_FAMILIES)[0]
    w = bs.VariantWalk([fam, "trend_ma_cross"], ["EURUSD"], equities=["AAPL"], cursor=0,
                       budget_s=60, per_run=10**9)
    rows = w(set(), 10**9, _key)
    on_share = {r["family"] for r in rows if r["symbol"] == "AAPL"}
    assert on_share == {fam}


def test_apply_fills_the_room_with_variants_and_bills_the_pace(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    docket = tmp_path / "docket.json"
    docket.write_text(json.dumps([{"symbol": "EURUSD", "family": "trend_ma_cross",
                                   "params": {}}]), "utf-8")
    monkeypatch.setattr(bs, "DOCKET", docket)

    @contextmanager
    def owned(name, **kwargs):
        yield True

    monkeypatch.setattr(job_lock, "exclusive_job", owned)
    _walk_env(tmp_path, monkeypatch)
    walk = bs.VariantWalk(["trend_ma_cross"], ["EURUSD"], cursor=0, budget_s=60, per_run=7)
    added, total = bs.apply([{"symbol": "EURUSD", "family": "trend_ma_cross", "params": {}}],
                            max_new=100, extra=walk)
    assert (added, total) == (7, 8)
    rows = json.loads(docket.read_text())
    assert len({_key(r) for r in rows}) == 8, "never a duplicate of the bank"
    lines = bs.supply_missed_growth(walk.state(), added, 100)
    assert [ln["rail"] for ln in lines] == ["breadth_sweep.VARIANT_PER_RUN"]
    assert lines[0]["verdict"] == "UNMEASURED" and lines[0]["value"] is None
    # The run cap still bounds everything together, and its own line appears when it binds.
    walk2 = bs.VariantWalk(["trend_ma_cross"], ["EURUSD"], cursor=walk.state()["next"],
                           budget_s=60, per_run=50)
    added2, _ = bs.apply([], max_new=3, extra=walk2)
    assert added2 == 3
    assert "breadth_sweep.MAX_NEW_PER_RUN" in [
        ln["rail"] for ln in bs.supply_missed_growth(walk2.state(), added2, 3)]


def test_the_report_carries_the_walk_and_its_missed_growth_line(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(bs, "REPORT", tmp_path / "BREADTH_SWEEP.json")
    state = {"room": 5, "minted": 5, "wrapped": False, "next": 9, "positions": 40}
    doc = bs.write_report([], [], 5, 5, state)
    assert doc["variant_walk"] == state
    assert doc["missed_growth"][-1]["rail"] == "breadth_sweep.VARIANT_PER_RUN"
    doc2 = bs.write_report([], [], 5, 5, state)
    assert len(doc2["missed_growth"]) == 2, "the ledger accumulates across passes"


def test_the_pace_clears_the_supply_floor_inside_the_judges_capacity() -> None:
    per_day = bs.VARIANT_PER_RUN * 24
    assert per_day >= bs.SUPPLY_TARGET_PER_DAY
    assert per_day <= 300_000, "inside the judge's measured low-end build capacity"
    assert bs.MAX_NEW_PER_RUN >= bs.VARIANT_PER_RUN
