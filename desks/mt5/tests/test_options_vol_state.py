"""The options and volatility state from Cboe's public daily files (options_implied cluster).

Covers: the index-history and put/call parsers on documented-format fixtures, the terms row and
its access labels (PUBLIC_WITH_TERMS, research-only, redistribution withheld), point-in-time
stamping at availability, the derived state (variance risk premium against the desk's own bars,
term-structure slope, VVIX/VIX, GVZ and OVX premiums), liveness RED after more than two empty
runs, the 403 hard stop, and the state reaching the cell path as the `implied_vol` family.
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
from libs.research import alpha_clusters as acl  # noqa: E402
from research import options_implied as O  # noqa: E402
from research import world_dataset_hunter as W  # noqa: E402
from research import world_macro_proposer as WMP  # noqa: E402

FIX = DESK / "tests" / "fixtures" / "options_vol"
NOW = datetime(2026, 11, 2, 12, 0, tzinfo=UTC)
CDN = "https://cdn.cboe.com/api/global/us_indices/daily_prices/VIX_History.csv"


@pytest.fixture()
def store(tmp_path, monkeypatch):
    s = tmp_path / "world_datasets"
    monkeypatch.setattr(W, "STORE", s)
    monkeypatch.setattr(W, "OBS", s / "obs")
    monkeypatch.setattr(W, "KEYS", s / "keys.json")
    monkeypatch.setattr(W, "EXPOSURE", s / "exposure.json")
    W._universe_at.cache_clear()
    return tmp_path


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


def test_doors_cover_every_index_and_ratio_on_the_cboe_cdn():
    doors = O.cboe_doors()
    names = {d["dataset"] for d in doors}
    for sym in ("VIX", "VIX9D", "VIX3M", "VVIX", "SKEW", "OVX", "GVZ"):
        assert f"{sym}_HISTORY" in names
    for kind in ("TOTAL", "INDEX", "EQUITY"):
        assert f"PC_{kind}" in names
    assert all(d["url"].startswith("https://cdn.cboe.com/") for d in doors)
    assert all(tf.source_of_url(d["url"]) == O.CBOE_ROW for d in doors)


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


def test_run_lands_pit_stamped_state_mapped_to_its_instruments(store, bars_dir):
    calls: list[str] = []
    rep = O.run(now=NOW, bars=bars_dir, symbols=[], fetch=_fake_fetch(calls))
    c = rep["cboe"]
    assert c["status"] == "OK" and not c["red_doors"]
    assert len(calls) == 10
    frame = pd.read_parquet(W.dataset_path("CBOE", "VIX_HISTORY"))
    # PUBLICATION, never the period date: the close of day D is knowable at D+1 12:00 UTC
    lag = (frame["available_time"] - frame["period_end"])
    assert lag.min() == pd.Timedelta(hours=O.CBOE_RELEASE_H) == lag.max()
    meta = json.loads(W.meta_path("CBOE", "VIX_HISTORY").read_text("utf-8"))
    insts = set(meta["series"]["vix"]["instruments"])
    assert {"US500", "NAS100", "XAUUSD", "USDJPY", "EURJPY", "GBPJPY", "AUDJPY"} <= insts
    assert "EURUSD" not in insts
    gvz = json.loads(W.meta_path("CBOE", "GVZ_HISTORY").read_text("utf-8"))
    assert gvz["series"]["gvz"]["instruments"] == ["XAUUSD"]
    ovx = json.loads(W.meta_path("CBOE", "OVX_HISTORY").read_text("utf-8"))
    assert set(ovx["series"]["ovx"]["instruments"]) == {"XTIUSD", "XBRUSD"}
    eq = json.loads(W.meta_path(O.STATE_PROVIDER, "EQUITY_VOL_STATE").read_text("utf-8"))
    assert {"vrp", "vrp_log_ratio", "vix9d_vix", "vix_vix3m", "vvix_vix",
            "pc_total", "pc_index", "pc_equity"} <= set(eq["series"])
    assert all(s["quality"] == "PASS" for s in eq["series"].values())
    for ds, code in (("GOLD_VOL_PREMIUM", "gvz_vrp"), ("OIL_VOL_PREMIUM", "ovx_vrp")):
        m = json.loads(W.meta_path(O.STATE_PROVIDER, ds).read_text("utf-8"))
        assert m["series"][code]["quality"] == "PASS", (ds, m["series"][code])
    st = pd.read_parquet(W.dataset_path(O.STATE_PROVIDER, "EQUITY_VOL_STATE"))
    assert ((st["available_time"] - st["period_end"]) >= pd.Timedelta(hours=36)).all()
    # the VRP is VIX^2 minus the realised variance of the desk's own US500 bars, same day
    vix = O.cboe_index_frame(_index_csv("VIX", seed=3 * 7 + ord("V")), "VIX")
    rv = O.proxy_features(_bars(11))["rv_21d"]
    rv.index = rv.index.tz_localize(None)
    vrp = st[st["series_code"] == "vrp"].set_index("period")["value"]
    day = vrp.index[-1]
    want = (vix.loc[pd.Timestamp(day)] / 100.0) ** 2 - rv.loc[pd.Timestamp(day)] ** 2
    assert vrp.iloc[-1] == pytest.approx(want, rel=1e-9)
    # the report carries counts and dates, never Cboe's values (redistribution withheld)
    assert f"{vix.iloc[-1]:.4f}" not in json.dumps(rep, default=str)


def test_a_fresh_door_is_not_refetched_within_its_refresh(store, bars_dir):
    calls: list[str] = []
    O.run(now=NOW, bars=bars_dir, symbols=[], fetch=_fake_fetch(calls))
    n = len(calls)
    rep = O.run(now=NOW + timedelta(hours=2), bars=bars_dir, symbols=[],
                fetch=_fake_fetch(calls))
    assert len(calls) == n and rep["cboe"]["fresh_skipped"] == 10
    assert rep["cboe"]["status"] == "OK"                       # fresh is not an empty run


def test_liveness_goes_red_after_more_than_two_empty_runs_and_recovers(store, bars_dir):
    calls: list[str] = []
    bad = _fake_fetch(calls, fail="http_404")
    seen = []
    for k in range(3):
        rep = O.run(now=NOW + timedelta(hours=24 * k), bars=bars_dir, symbols=[], fetch=bad)
        seen.append(rep["status"])
    assert not seen[0].startswith("RED") and not seen[1].startswith("RED")
    assert seen[2].startswith("RED") and "VIX_HISTORY" in seen[2]
    assert rep["cboe"]["doors"]["CBOE/VIX_HISTORY"]["empty_streak"] == 3
    assert rep["cboe"]["red_after_empty_runs"] == 2
    ok = O.run(now=NOW + timedelta(days=4), bars=bars_dir, symbols=[], fetch=_fake_fetch(calls))
    assert ok["status"] == "OK" and ok["cboe"]["doors"]["CBOE/VIX_HISTORY"]["empty_streak"] == 0


def test_a_403_is_a_hard_stop_for_the_whole_site(store, bars_dir):
    calls: list[str] = []
    rep = O.run(now=NOW, bars=bars_dir, symbols=[], fetch=_fake_fetch(calls, fail="http_403"))
    assert len(calls) == 1                                     # no sibling door, no retry
    assert rep["cboe"]["held"] == "http_403"
    assert rep["cboe"]["missed_growth"]["delta_elogw"] == "UNMEASURED"


# ------------------------------------------------------------------- the cell path ----
def test_implied_vol_family_is_registered_and_files_into_the_options_cluster():
    from mt5desk import family_world_macro as F
    from mt5desk.families_orthogonal import ORTHOGONAL_FAMILIES
    assert ORTHOGONAL_FAMILIES["implied_vol"] is F.family_implied_vol
    assert acl.classify_family("implied_vol") == "options_implied"
    want = frozenset({O.CBOE_PROVIDER, O.STATE_PROVIDER})
    assert want == F.IMPLIED_PROVIDERS


def test_options_state_reaches_the_proposer_as_implied_vol_cells(store, bars_dir):
    from mt5desk import family_world_macro as F
    O.run(now=NOW, bars=bars_dir, symbols=[], fetch=_fake_fetch([]))
    W.build_exposure(NOW)
    vrp = W.series_key(O.STATE_PROVIDER, "EQUITY_VOL_STATE", "vrp")
    proxy = W.series_key("MT5_PROXY", "RVOL_US500", "rv_21d")
    assert vrp in W.exposed_keys("US500", now=NOW, doc=W._exposure_doc())
    assert WMP.family_for_key(vrp) == "implied_vol"
    assert WMP.family_for_key(proxy) == "world_macro_state"   # realised is never implied
    d = _bars(11)
    params = {"series_key": vrp, "z_obs": 24, "z_lo": -99.0, "z_hi": 99.0,
              "direction": "long", "hold_bars": 24}
    sig = F.family_implied_vol(d, **params)
    assert sig and all(s.tag.startswith("implied_vol:") for s in sig)
    # same identity, same trades as the generic state family: only the cluster label differs
    base = F.family_world_macro_state(d, **params)
    assert [s.time for s in sig] == [s.time for s in base]
    assert F.family_implied_vol(d, **{**params, "series_key": proxy}) == []
