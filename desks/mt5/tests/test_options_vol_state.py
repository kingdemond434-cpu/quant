"""The options and volatility state (options_implied cluster): Cboe research-only lake packs and
the licensed own-bar substitute packs that mint cells.

Covers: the index-history and put/call parsers on documented-format fixtures, the terms row and
its access labels (PUBLIC_WITH_TERMS, research-only, redistribution withheld, fenced from cells),
point-in-time stamping at availability, the Cboe-derived state (variance risk premium against the
desk's own bars, term slopes, VVIX/VIX, GVZ and OVX premiums), the substitute features (realised
term structure, vol-of-vol, realised skew, range-vol jumps, gold/oil ratio), liveness RED after
more than two empty runs, the 403 hard stop, and the substitutes reaching pack_cells and the
exogenous_conditioner family while the Cboe packs are held by the fence.
"""
from __future__ import annotations

import json
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

DESK = Path(__file__).resolve().parents[1]
ROOT = DESK.parents[1]
for _p in (str(ROOT), str(DESK), str(DESK / "research")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from libs.data import terms_fence as tf  # noqa: E402
from libs.research import access_classifier as ac  # noqa: E402
from research import options_implied as O  # noqa: E402
from research import pack_cells as PC  # noqa: E402
from research import source_drain as SD  # noqa: E402

FIX = DESK / "tests" / "fixtures" / "options_vol"
NOW = datetime(2026, 11, 2, 12, 0, tzinfo=UTC)
CDN = "https://cdn.cboe.com/api/global/us_indices/daily_prices/VIX_History.csv"


@pytest.fixture()
def lake(tmp_path):
    return tmp_path / "lake" / "series"


def _run(lake: Path, bars: Path, now: datetime, fetch) -> dict:
    return O.run(now=now, bars=bars, symbols=[], fetch=fetch, lake=lake,
                 liveness=lake.parent / "doors.json")


# ------------------------------------------------------------------------------ parsers ----
def test_index_parser_reads_close_and_single_column_files():
    vix = O.cboe_index_frame((FIX / "VIX_History.csv").read_bytes(), "VIX")
    assert vix.index[-1] == pd.Timestamp("2026-10-31") and vix.iloc[-1] == pytest.approx(15.94)
    assert vix.index[0] == pd.Timestamp("1990-01-02")            # MM/DD/YYYY, never day-first
    vvix = O.cboe_index_frame((FIX / "VVIX_History.csv").read_bytes(), "VVIX")
    assert vvix.iloc[-1] == pytest.approx(86.95)
    skew = O.cboe_index_frame((FIX / "SKEW_History.csv").read_bytes(), "SKEW")
    assert skew.iloc[-2] == pytest.approx(139.52)
    with pytest.raises(ValueError):
        O.cboe_index_frame((FIX / "served.html").read_bytes(), "VIX")


def test_put_call_parser_skips_the_disclaimer_block():
    pc = O.cboe_pc_frame((FIX / "totalpc.csv").read_bytes())
    assert len(pc) == 3
    assert pc.loc[pd.Timestamp("2019-10-04")] == pytest.approx(0.88)
    with pytest.raises(ValueError):
        O.cboe_pc_frame((FIX / "served.html").read_bytes())


# -------------------------------------------------------------------------------- terms ----
def test_terms_row_is_research_only_with_redistribution_withheld():
    row = tf.SOURCE_POLICY[O.CBOE_ROW]
    assert row["access_label"] == "PUBLIC_WITH_TERMS"
    assert row["redistribute"] is False and row["live_sizing_input"] is False
    assert tf.terms_state(O.CBOE_ROW) == "READ"
    assert "not intended for trading purposes" in row["terms"]["clauses"]["4"]
    assert row["terms"]["checked_at"] == "2026-11-03"
    # mined: the fetch is never held; live input is refused (research only)
    assert tf.platform_of_url(CDN) is None
    assert tf.input_source(CDN) == O.CBOE_ROW
    # the label is DERIVED by the access router, and redistribution fails closed
    v = ac.classify(row["access_meta"])
    assert v.access_label == "PUBLIC_WITH_TERMS" and not v.redistribute_allowed
    assert v.may("alpha_input")
    t = O.cboe_terms()
    assert t["live_sizing_input"] is False and t["research"] is True
    assert t["missed_growth"]["delta_elogw"] == "UNMEASURED"
    assert t["macro_view_vix_lean"]["state"] == "NOT_RESTORED"
    assert t["mints_cells"] is False
    assert "mt5vol_" in t["missed_growth"]["substitute"]


def test_doors_cover_every_index_and_ratio_on_the_cboe_cdn():
    doors = O.cboe_doors()
    names = {d["pack"] for d in doors}
    for sym in ("VIX", "VIX9D", "VIX3M", "VVIX", "SKEW", "OVX", "GVZ"):
        assert f"cboe_{sym.lower()}" in names
    for kind in ("total", "index", "equity"):
        assert f"cboe_pc_{kind}" in names
    assert all(d["url"].startswith("https://cdn.cboe.com/") for d in doors)
    assert all(tf.source_of_url(d["url"]) == O.CBOE_ROW for d in doors)


def test_registry_rows_fence_cboe_and_let_the_substitutes_mint():
    rows = {r["id"]: r for r in O.pack_rows()}
    reg = {r["id"]: r for r in json.loads(O.REGISTRY.read_text("utf-8"))["sources"]}
    for pid, r in rows.items():
        assert reg.get(pid) == r, pid                    # the registry carries every pack row
        assert r["role"] == O.LANDED_ROLE and 0 < len(r["targets"]) <= 8
        if pid.startswith("cboe_"):
            assert PC._fenced_pack(r) == O.CBOE_ROW, pid  # research-only: no cell
        else:
            assert PC._fenced_pack(r) is None, pid        # licensed own bars: cells
    assert {"US500", "NAS100", "USDJPY", "XAUUSD"} <= set(rows["mt5vol_us500"]["targets"])
    assert set(rows["mt5vol_xtiusd"]["targets"]) == {"XTIUSD", "XBRUSD"}
    assert rows["cboe_gvz"]["targets"] == ["XAUUSD"]


# --------------------------------------------------------------------- end to end, PIT ----
def _bdays() -> pd.DatetimeIndex:
    return pd.bdate_range("2025-03-03", "2026-10-30")


def _index_csv(sym: str, seed: int) -> bytes:
    rng = np.random.default_rng(seed)
    days = _bdays()
    lvl = {"VIX": 18.0, "VIX9D": 17.0, "VIX3M": 20.0, "VVIX": 90.0, "SKEW": 135.0,
           "OVX": 35.0, "GVZ": 16.0}[sym]
    v = lvl * np.exp(np.cumsum(rng.normal(0, 0.03, len(days))) * 0.3)
    if sym in ("VVIX", "SKEW"):
        lines = [f"DATE,{sym}"] + [f"{d:%m/%d/%Y},{x:.2f}" for d, x in zip(days, v, strict=True)]
    else:
        lines = ["DATE,OPEN,HIGH,LOW,CLOSE"] + [
            f"{d:%m/%d/%Y},{x:.4f},{x * 1.02:.4f},{x * 0.98:.4f},{x:.4f}"
            for d, x in zip(days, v, strict=True)]
    return ("\n".join(lines) + "\n").encode()


def _pc_csv(seed: int) -> bytes:
    rng = np.random.default_rng(seed)
    days = _bdays()
    head = ['"Cboe  Total Exchange Volume and Put/Call Ratios",,,,', ",,,,",
            "DATE,CALLS,PUTS,TOTAL,P/C Ratio"]
    rows = []
    for d in days:
        c = int(rng.integers(900_000, 1_100_000))
        p = int(c * rng.uniform(0.6, 1.1))
        rows.append(f"{d.month}/{d.day}/{d.year},{c},{p},{c + p},{p / c:.2f}")
    return ("\n".join(head + rows) + "\n").encode()


def _fake_fetch(calls: list[str], fail: str | None = None):
    def fetch(url: str) -> tuple[bytes | None, str]:
        calls.append(url)
        if fail:
            return None, fail
        name = url.rsplit("/", 1)[-1]
        if name.endswith("_History.csv"):
            sym = name[: -len("_History.csv")]
            return _index_csv(sym, seed=len(sym) * 7 + ord(sym[0])), ""
        return _pc_csv(seed=len(name)), ""
    return fetch


def _bars(seed: int) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    idx = pd.date_range("2025-03-01", "2026-10-31 23:00", freq="h", tz="UTC")
    close = 100.0 * np.exp(np.cumsum(rng.normal(0, 0.002, len(idx))))
    return pd.DataFrame({"open": close, "high": close * 1.001, "low": close * 0.999,
                         "close": close}, index=idx)


@pytest.fixture()
def bars_dir(tmp_path):
    b = tmp_path / "bars"
    b.mkdir()
    for i, sym in enumerate(("US500", "XAUUSD", "XTIUSD")):
        _bars(11 + i).to_parquet(b / f"{sym}_H1.parquet")
    return b


def _avail_lag(df: pd.DataFrame) -> pd.Series:
    return (pd.to_datetime(df["available_time"], utc=True)
            - pd.to_datetime(df["event_time"]).dt.tz_localize("UTC"))


def test_run_lands_pit_stamped_packs_and_the_derived_state(lake, bars_dir):
    calls: list[str] = []
    rep = _run(lake, bars_dir, NOW, _fake_fetch(calls))
    c = rep["cboe"]
    assert rep["status"] == "OK" and c["status"] == "OK" and not c["red_doors"]
    assert len(calls) == 10 and c["fetched"] == 10
    vix = pd.read_csv(lake / "cboe_vix.csv")
    # PUBLICATION, never the period date: the close of day D is knowable at D+1 12:00 UTC
    lag = _avail_lag(vix)
    assert lag.min() == pd.Timedelta(hours=O.CBOE_RELEASE_H) == lag.max()
    side = json.loads((lake / "cboe_vix.pit.json").read_text("utf-8"))
    assert side["frames"][0]["status"] == "STAMPED" and side["n_rows"] == len(vix)
    st = pd.read_csv(lake / "cboe_vol_state.csv")
    assert {"vrp", "vrp_log_ratio", "vix9d_vix", "vix_vix3m", "vvix_vix"} <= set(st.columns)
    assert (_avail_lag(st) >= pd.Timedelta(hours=36)).all()
    for pack, col in (("cboe_gold_vol_premium", "gvz_vrp"), ("cboe_oil_vol_premium", "ovx_vrp")):
        assert pd.read_csv(lake / f"{pack}.csv")[col].notna().sum() > 250, pack
    # the VRP is VIX^2 minus the realised variance of the desk's own US500 bars, same day
    vixs = O.cboe_index_frame(_index_csv("VIX", seed=3 * 7 + ord("V")), "VIX")
    rv = O.proxy_features(_bars(11))["rv_21d"]
    rv.index = rv.index.tz_localize(None)
    row = st.dropna(subset=["vrp"]).iloc[-1]
    day = pd.Timestamp(row["event_time"])
    assert row["vrp"] == pytest.approx((vixs.loc[day] / 100.0) ** 2 - rv.loc[day] ** 2,
                                       rel=1e-9)
    # the report carries counts and dates, never Cboe's values (redistribution withheld)
    assert f"{vixs.iloc[-1]:.4f}" not in json.dumps(rep, default=str)


def test_substitute_packs_carry_the_licensed_features(lake, bars_dir):
    rep = _run(lake, bars_dir, NOW, _fake_fetch([]))
    subs = rep["cboe"]["substitutes"]
    for sym in ("US500", "XAUUSD", "XTIUSD"):
        df = pd.read_csv(lake / f"{O.substitute_pack_id(sym)}.csv")
        assert {"rv_5d", "rv_21d", "rv_63d", "rv_term_5_21", "rv_term_21_63",
                "vol_of_vol_63d", "rskew_63d", "parkinson_21d", "garman_klass_21d",
                "gk_jump"} <= set(df.columns)
        lag = _avail_lag(df)
        assert lag.min() == pd.Timedelta(hours=O.OWN_BARS_RELEASE_H) == lag.max()
    assert subs["mt5vol_nas100"]["status"] == "UNMEASURED"       # no bars: says so, never 0
    ratio = pd.read_csv(lake / f"{O.GOLD_OIL_PACK}.csv")
    assert ratio["gold_oil_rv_ratio"].dropna().gt(0).all()


def test_substitute_features_are_causal():
    b = _bars(11)
    f = O.substitute_features(b.loc[:"2026-06-30"])
    g = O.substitute_features(b)
    common = f.dropna().index
    assert len(common) > 100
    pd.testing.assert_frame_equal(f.loc[common], g.loc[common])


def test_landing_is_append_only_and_a_revision_is_never_back_dated(lake):
    days = pd.date_range("2026-01-01", periods=5, freq="D")
    f = pd.DataFrame({"x": [1.0, 2.0, 3.0, 4.0, 5.0]}, index=days)
    O.write_lake_pack("t", f, release_h=24, now=NOW, lake=lake)
    later = NOW + timedelta(days=1)
    r = O.write_lake_pack("t", f.assign(x=[1.0, 2.0, 3.0, 4.0, 9.0]), release_h=24,
                          now=later, lake=lake)
    assert r["rows_added"] == 1
    df = pd.read_csv(lake / "t.csv")
    rev = df[df["vintage_id"] == 2].iloc[0]
    assert pd.Timestamp(rev["available_time"]) == pd.Timestamp(later)
    assert O.lake_series("t", "x", lake).iloc[-1] == 5.0           # first vintage kept


def test_a_fresh_door_is_not_refetched_within_its_refresh(lake, bars_dir):
    calls: list[str] = []
    _run(lake, bars_dir, NOW, _fake_fetch(calls))
    n = len(calls)
    rep = _run(lake, bars_dir, NOW + timedelta(hours=2), _fake_fetch(calls))
    assert len(calls) == n and rep["cboe"]["fresh_skipped"] == 10
    assert rep["cboe"]["status"] == "OK"                       # fresh is not an empty run


def test_liveness_goes_red_after_more_than_two_empty_runs_and_recovers(lake, bars_dir):
    calls: list[str] = []
    bad = _fake_fetch(calls, fail="http_404")
    seen = []
    for k in range(3):
        rep = _run(lake, bars_dir, NOW + timedelta(hours=24 * k), bad)
        seen.append(rep["status"])
    assert not seen[0].startswith("RED") and not seen[1].startswith("RED")
    assert seen[2].startswith("RED") and "cboe_vix" in seen[2]
    assert rep["cboe"]["doors"]["cboe_vix"]["empty_streak"] == 3
    assert rep["cboe"]["red_after_empty_runs"] == 2
    ok = _run(lake, bars_dir, NOW + timedelta(days=4), _fake_fetch(calls))
    assert ok["status"] == "OK" and ok["cboe"]["doors"]["cboe_vix"]["empty_streak"] == 0


def test_a_403_is_a_hard_stop_for_the_whole_site(lake, bars_dir):
    calls: list[str] = []
    rep = _run(lake, bars_dir, NOW, _fake_fetch(calls, fail="http_403"))
    assert len(calls) == 1                                     # no sibling door, no retry
    assert rep["cboe"]["held"] == "http_403"
    assert rep["cboe"]["missed_growth"]["delta_elogw"] == "UNMEASURED"


# ------------------------------------------------------------------- the cell path ----
def test_substitutes_reach_pack_cells_and_the_conditioner_cboe_is_held(lake, bars_dir,
                                                                        monkeypatch):
    from mt5desk.family_exogenous_conditioner import family_exogenous_conditioner
    _run(lake, bars_dir, NOW, _fake_fetch([]))
    monkeypatch.setattr(SD, "SERIES", lake)
    monkeypatch.setattr(SD, "VAULT", lake.parent / "vault")
    rows = {r["id"]: r for r in O.pack_rows()}
    for pid in ("mt5vol_us500", "cboe_vol_state"):
        ch = SD.chain_for(rows[pid], {}, {})
        assert ch["stage_reached"] == "represented", (pid, ch)
    path = lake / "mt5vol_us500.csv"
    sigs, _n, why = PC.signals_of(path)
    assert {"rv_term_5_21", "vol_of_vol_63d", "gk_jump"} <= set(sigs) and not why
    res = PC.emit_for(rows["mt5vol_us500"], sigs, PC.targets_of(rows["mt5vol_us500"]),
                      dry_run=True)
    assert res["emitted"] > 0
    sig = family_exogenous_conditioner(_bars(11), source="mt5vol_us500", signal="gk_jump",
                                       transform="level_z", threshold=0.5, series_root=lake)
    assert sig                                                   # features reach the cell path
    # the Cboe packs are represented and still held: the fence is the reason, by name
    assert PC._fenced_pack(rows["cboe_vol_state"]) == O.CBOE_ROW
