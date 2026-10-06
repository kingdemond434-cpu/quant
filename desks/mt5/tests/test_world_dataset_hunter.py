"""The world dataset hunter: discovery, PIT merge, quality, mapping, registry, research door.

No network: every HTTP call goes through an injected fetcher that serves canned DBnomics-shaped
payloads or raises the classified failure a blocked host would.
"""
from __future__ import annotations

import json
import os
import stat
import sys
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

import pandas as pd
import pytest

DESK = Path(__file__).resolve().parents[1]
ROOT = DESK.parents[1]
for _p in (str(ROOT), str(DESK), str(DESK / "research")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from research import universe_policy as up  # noqa: E402
from research import world_dataset_hunter as W  # noqa: E402

NOW = datetime(2026, 9, 30, 12, 0, tzinfo=UTC)

UNIVERSE_ROWS = {
    "AUDUSD": {"asset_class": "Forex", "currency_profit": "USD"},
    "EURUSD": {"asset_class": "Forex", "currency_profit": "USD"},
    "XAUUSD": {"asset_class": "Commodities", "currency_profit": "USD"},
    "AUS200": {"asset_class": "Indices", "currency_profit": "AUD"},
    "UST10Y": {"asset_class": "Bonds", "currency_profit": "USD"},
    "3M": {"asset_class": "Equities", "currency_profit": "USD"},
}

HAND_REGISTRY = {
    "schema_version": 1, "note": "hand registry",
    "datasets": {
        "fred_macro": {"lifecycle": "CORE", "series": ["DGS10"]},
        "bis_eer": {"lifecycle": "DISCOVERED", "status": "blocked"},
        "gdelt": {"lifecycle": "DISCOVERED", "status": "not yet fetched"},
        "cot": {"lifecycle": "CORE"},
    },
}


@pytest.fixture()
def box(tmp_path, monkeypatch):
    store = tmp_path / "world_datasets"
    uni = tmp_path / "universe.json"
    uni.write_text(json.dumps(UNIVERSE_ROWS), "utf-8")
    reg = tmp_path / "data_registry.json"
    reg.write_text(json.dumps(HAND_REGISTRY), "utf-8")
    monkeypatch.setattr(W, "STORE", store)
    monkeypatch.setattr(W, "OBS", store / "obs")
    monkeypatch.setattr(W, "CATALOG", store / "catalog.json")
    monkeypatch.setattr(W, "EXPOSURE", store / "exposure.json")
    monkeypatch.setattr(W, "KEYS", store / "keys.json")
    monkeypatch.setattr(W, "HISTORY", store / "hunt_history.jsonl")
    monkeypatch.setattr(W, "REGISTRY", reg)
    monkeypatch.setattr(W, "UNIVERSE", uni)
    monkeypatch.setattr(W, "REPORT", tmp_path / "DATASET_HUNT.json")
    monkeypatch.setattr(W, "DESK", tmp_path)
    monkeypatch.setattr(W, "MIN_REQUEST_GAP_S", 0.0)
    monkeypatch.setattr(up, "UNIVERSE", uni)
    monkeypatch.setattr(W, "_free_disk_ok", lambda: (True, {"free_gb": 99.0}))
    up._registry.cache_clear()
    W._universe_at.cache_clear()
    W._exposure_at.cache_clear()
    W._keys_at.cache_clear()
    W._frame_at.cache_clear()
    yield tmp_path
    up._registry.cache_clear()


def _monthly(n: int, end: date = date(2026, 8, 1)) -> tuple[list[str], list[float]]:
    periods, values = [], []
    y, m = end.year, end.month
    for i in range(n):
        periods.append(f"{y:04d}-{m:02d}")
        values.append(1.0 + 0.01 * i + (0.5 if i % 7 == 0 else 0.0))
        m -= 1
        if m == 0:
            y, m = y - 1, 12
    return periods[::-1], values


def _daily(n: int, end: date = date(2026, 9, 28)) -> tuple[list[str], list[float]]:
    days = [end - timedelta(days=i) for i in range(n)][::-1]
    return [d.isoformat() for d in days], [100 + (i % 17) * 0.3 for i in range(n)]


def _fake(routes: dict[str, object]):
    """A fetcher: first route whose key is a substring of the URL wins; else a blocked host."""
    calls: list[str] = []

    def fetch(url: str, timeout: float) -> bytes:
        calls.append(url)
        for frag, payload in routes.items():
            if frag in url:
                if isinstance(payload, Exception):
                    raise payload
                return json.dumps(payload).encode() if not isinstance(payload, bytes) \
                    else payload
        raise W.FetchError("blocked_proxy", url)

    fetch.calls = calls  # type: ignore[attr-defined]
    return fetch


def _dbnomics_routes(revise: bool = False) -> dict[str, object]:
    mp, mv = _monthly(60)
    if revise:
        mv = list(mv)
        mv[-1] = mv[-1] + 5.0
    dp, dv = _daily(400)
    return {
        "/providers?": {"providers": {"docs": [{"code": "BIS", "name": "Bank for International "
                                                 "Settlements", "region": "World"}],
                                      "num_found": 1}},
        "/datasets/BIS?": {"datasets": {"docs": [
            {"code": "WS_CBPOL", "name": "Central bank policy rates", "nb_series": 2},
            {"code": "WS_GONE", "name": "Discontinued table", "nb_series": 1}],
            "num_found": 2}},
        "/series/BIS/WS_CBPOL?": {"series": {"num_found": 2, "docs": [
            {"series_code": "M.AU", "series_name": "Policy rate - Australia - Monthly",
             "@frequency": "monthly", "dimensions": {"FREQ": "M", "REF_AREA": "AU"},
             "period": mp, "value": mv},
            {"series_code": "D.XM", "series_name": "Policy rate - Euro area - Daily",
             "@frequency": "daily", "dimensions": {"FREQ": "D", "REF_AREA": "XM"},
             "period": dp, "value": [*dv[:-1], "NA"]},
        ]}},
        "/series/BIS/WS_GONE?": W.FetchError("not_found_404", "gone"),
        "/search?": {"results": {"docs": [{"provider_code": "IMF", "code": "IFS",
                                           "name": "International Financial Statistics"}]}},
    }


# ---------------------------------------------------------------------------- periods ----
@pytest.mark.parametrize("period,freq,end,inferred", [
    ("2026-08", "monthly", date(2026, 8, 31), "monthly"),
    ("2026-Q2", "", date(2026, 6, 30), "quarterly"),
    ("2025", "", date(2025, 12, 31), "annual"),
    ("2026-02", "", date(2026, 2, 28), "monthly"),
    ("2026-09-28", "daily", date(2026, 9, 28), "daily"),
    ("2026-W01", "", date(2026, 1, 4), "weekly"),
    ("2026-S1", "", date(2026, 6, 30), "bi-annual"),
    ("20260915", "", date(2026, 9, 15), "daily"),
])
def test_period_end_is_the_last_day_the_period_describes(period, freq, end, inferred):
    got, f = W.period_end(period, freq)
    assert got == end and f == inferred


def test_period_end_refuses_what_it_cannot_read():
    assert W.period_end("not a period")[0] is None


# ------------------------------------------------------------------------ PIT merge ----
def test_a_revision_is_a_new_row_and_the_first_vintage_is_what_research_sees():
    p, v = _monthly(40)
    series = [{"code": "S", "freq": "monthly", "points": list(zip(p, v, strict=True))}]
    frame, added = W.merge_observations(None, series, now=NOW)
    assert added == 40 and (frame["vintage"] == 1).all()
    # the same fetch again appends nothing
    frame2, added2 = W.merge_observations(frame, series, now=NOW + timedelta(hours=1))
    assert added2 == 0 and len(frame2) == 40
    # a revised last value AND a new period, seen three days later
    later = NOW + timedelta(days=3)
    revised = [(p[-1], v[-1] + 9.0), ("2026-09", 7.0)]
    frame3, added3 = W.merge_observations(
        frame2, [{"code": "S", "freq": "monthly", "points": revised}], now=later)
    assert added3 == 2 and len(frame3) == 42
    rev = frame3[(frame3["period"] == p[-1])].sort_values("vintage")
    assert list(rev["vintage"]) == [1, 2] and rev["value"].iloc[0] == v[-1]
    s = W.pit_series(frame3, "S")
    # the revision never leaks: the value for that period is still the first vintage
    assert v[-1] + 9.0 not in set(s.round(9))
    # the new September print was WATCHED arriving: keyed on the later of its modelled
    # publication (period_end + 20d = 2026-10-20) and the instant the box first read it
    sept_key = next(t for t, val in s.items() if val == 7.0)
    assert sept_key == max(pd.Timestamp("2026-10-20", tz="UTC"), pd.Timestamp(later))


def test_backfilled_history_is_keyed_on_publication_lag_not_period():
    p, v = _monthly(40)
    frame, _ = W.merge_observations(None, [{"code": "S", "freq": "monthly",
                                            "points": list(zip(p, v, strict=True))}], now=NOW)
    s = W.pit_series(frame, "S")
    first_end = pd.Timestamp(W.period_end(p[0], "monthly")[0], tz="UTC")
    assert s.index.min() == first_end + pd.Timedelta(days=20)


# ------------------------------------------------------------------------- quality ----
def test_quality_names_the_failure():
    p, v = _monthly(60)
    pts = list(zip(p, v, strict=True))
    assert W.quality(pts, "monthly", now=NOW)[:2] == (True, "ok")
    assert W.quality(pts[:10], "monthly", now=NOW)[1] == "too_short"
    assert W.quality([(a, 1.0) for a, _ in pts], "monthly", now=NOW)[1] == "constant"
    old_p, old_v = _monthly(60, end=date(2019, 1, 1))
    assert W.quality(list(zip(old_p, old_v, strict=True)), "monthly",
                     now=NOW)[1] == "stale_discontinued"
    assert W.quality([], "monthly", now=NOW)[1] == "no_observations"


# ------------------------------------------------------------------------- mapping ----
def test_country_currency_commodity_map_to_hypothesis_lane_only(box):
    m = W.map_series("Policy rate - Australia", {"REF_AREA": "AU"})
    assert m["countries"] == ["AU"] and m["currencies"] == ["AUD"]
    insts = W.instruments_for(m["currencies"], m["stems"])
    assert set(insts) == {"AUDUSD", "AUS200"}
    g = W.map_series("LBMA gold price, US dollar", {})
    insts = W.instruments_for(g["currencies"], g["stems"])
    assert "XAUUSD" in insts and "UST10Y" in insts and "3M" not in insts
    us = W.instruments_for(["USD"], [])
    assert "3M" not in us                           # never a statistical conditioner on a share


def test_iso3_and_euro_area_codes_map():
    m = W.map_series("x", {"geo": "DEU", "COUNTERPART_AREA": "XM"})
    assert "EUR" in m["currencies"] and "DE" in m["countries"]


# ---------------------------------------------------------------------- full pass ----
def test_a_pass_discovers_fetches_registers_and_exposes(box):
    fetch = _fake(_dbnomics_routes())
    rep = W.run(budget_s=60, fetch=fetch, now=NOW)
    t = rep["totals"]
    assert t["providers_discovered"] == 1
    assert t["datasets_discovered"] >= 3             # 2 listed + the legacy search seed + direct
    assert t["datasets_fetched"] == 1 and t["datasets_quality_passed"] == 1
    assert t["series_ingested"] == 2 and t["series_quality_passed"] == 2
    assert t["rows_per_day"] == W.UNMEASURED        # one pass is not a day
    assert rep["failures_by_reason"].get("series:not_found_404") == 1
    assert rep["pass"]["network"] == "OK"
    assert Path(W.REPORT).exists()

    reg = json.loads(Path(W.REGISTRY).read_text("utf-8"))["datasets"]
    row = reg["world:BIS/WS_CBPOL"]
    assert row["lifecycle"] == "QUALITY-PASSED" and row["research_exposed"] is True
    assert reg["world:BIS/WS_GONE"]["lifecycle"] == "DISCOVERED"
    # hand rows: never demoted, never rewritten beyond the attempt record
    assert reg["fred_macro"]["lifecycle"] == "CORE" and reg["cot"]["lifecycle"] == "CORE"
    assert "hunter_attempt" in reg["gdelt"] and reg["gdelt"]["lifecycle"] == "DISCOVERED"
    assert reg["gdelt"]["hunter_attempt"]["reason"] == "blocked_proxy"
    assert "hunter_attempt" in reg["bis_eer"]

    # the research door: AUDUSD sees the Australian series, the share CFD sees nothing
    idx = pd.date_range("2022-01-01", "2026-09-30", freq="h", tz="UTC")
    got = W.world_series_for("AUDUSD", idx, now=NOW)
    key = W.series_key("BIS", "WS_CBPOL", "M.AU")
    assert f"world_{key}" in got
    s = got[f"world_{key}"]
    assert s.index.equals(idx) and s.notna().sum() > 1000
    assert W.world_series_for("3M", idx, now=NOW) == {}


def test_second_pass_resumes_and_a_revision_appends(box):
    W.run(budget_s=60, fetch=_fake(_dbnomics_routes()), now=NOW)
    cat = json.loads(Path(W.CATALOG).read_text("utf-8"))
    assert cat["datasets"]["BIS/WS_CBPOL"]["series_offset"] == 0      # sweep closed
    later = NOW + timedelta(days=8)
    rep = W.run(budget_s=60, fetch=_fake(_dbnomics_routes(revise=True)), now=later)
    assert rep["pass"]["rows_appended"] >= 1
    frame = pd.read_parquet(W.dataset_path("BIS", "WS_CBPOL"))
    assert frame["vintage"].max() == 2


def test_a_blocked_network_is_reported_not_zeroed(box):
    rep = W.run(budget_s=30, fetch=_fake({}), now=NOW)
    assert rep["pass"]["network"] == "BLOCKED"
    assert "blocked_proxy" in rep["pass"]["network_blocked_by"]
    assert rep["totals"]["datasets_fetched"] in (W.UNMEASURED, 0)
    assert rep["totals"]["providers_discovered"] == W.UNMEASURED


def test_paging_advances_the_series_cursor(box, monkeypatch):
    monkeypatch.setattr(W, "SERIES_PAGE", 1)
    routes = _dbnomics_routes()
    doc = routes["/series/BIS/WS_CBPOL?"]
    doc["series"]["docs"] = doc["series"]["docs"][:1]          # a page of one, of two
    W.run(budget_s=60, fetch=_fake(routes), now=NOW)
    cat = json.loads(Path(W.CATALOG).read_text("utf-8"))
    assert cat["datasets"]["BIS/WS_CBPOL"]["series_offset"] == 1
    assert cat["datasets"]["BIS/WS_CBPOL"]["next_due"] is None


# ------------------------------------------------------------------ direct parsing ----
def test_bis_flat_zip_and_json_records_parse():
    import io
    import zipfile
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("x.csv", "KEY,FREQ,REF_AREA,TIME_PERIOD,OBS_VALUE\n"
                             "M.AU,M:Monthly,AU:Australia,2026-01,4.1\n"
                             "M.AU,M:Monthly,AU:Australia,2026-02,4.2\n")
    df = W.frame_from_payload(buf.getvalue(), "bis_flat_zip", {})
    assert set(df["series_code"]) == {"M.AU"} and df["REF_AREA"].iloc[0] == "AU"
    ser = W.series_from_long(df)
    assert ser[0]["freq"] == "monthly" and ser[0]["dims"]["REF_AREA"] == "AU"
    recs = json.dumps({"data": [{"record_date": "2026-08-31", "security_desc": "Bills",
                                 "avg_interest_rate_amt": "4.9"}]}).encode()
    df2 = W.frame_from_payload(recs, "json_records", {"data_key": "data",
                                                      "date_col": "record_date",
                                                      "code_col": "security_desc",
                                                      "value_col": "avg_interest_rate_amt"})
    assert df2["value"].iloc[0] == 4.9 and df2["period"].iloc[0] == "2026-08-31"
    with pytest.raises(W.FetchError):
        W.frame_from_payload(b"<!DOCTYPE html><html></html>", "csv", {})


# ------------------------------------------------------------------- windows safety ----
def test_write_json_replaces_a_read_only_destination(tmp_path):
    p = tmp_path / "ro.json"
    p.write_text("{}", "utf-8")
    os.chmod(p, stat.S_IREAD)
    W.write_json(p, {"a": 1})
    assert json.loads(p.read_text("utf-8")) == {"a": 1}
    assert not list(tmp_path.glob("*.tmp"))


def test_low_disk_stands_fetching_down_and_says_so(box, monkeypatch):
    monkeypatch.setattr(W, "_free_disk_ok", lambda: (False, {"free_gb": 0.5, "floor_gb": 3.0}))
    rep = W.run(budget_s=30, fetch=_fake(_dbnomics_routes()), now=NOW)
    assert "stood down" in rep["pass"]["stood_down"]
    assert rep["totals"]["datasets_discovered"] == 2          # discovery still ran
    assert rep["totals"]["datasets_fetched"] == 0



# ------------------------------------------------------ the consumer: world_macro_state ----
def _fixture_store(box) -> str:
    """One monthly Australian policy-rate series in the hunter's store; returns its key."""
    from collections import Counter

    import numpy as np
    periods, _ = _monthly(96, end=date(2026, 8, 1))
    rng = np.random.default_rng(7)
    vals = [float(v) for v in np.cumsum(rng.normal(0, 0.25, len(periods))) + 3.0]
    W.ingest_series("BIS", "WS_CBPOL", "Central bank policy rates",
                    [{"code": "M.AU", "name": "Policy rate - Australia", "freq": "monthly",
                      "dims": {"REF_AREA": "AU"},
                      "points": list(zip(periods, vals, strict=True))}],
                    now=NOW, base_score=5.0, qstats=Counter())
    W.build_exposure(NOW)
    W._keys_at.cache_clear()
    W._frame_at.cache_clear()
    W._exposure_at.cache_clear()
    return W.series_key("BIS", "WS_CBPOL", "M.AU")


def _bars(n: int = 30000) -> pd.DataFrame:
    import numpy as np
    idx = pd.date_range(end="2026-09-29 23:00", periods=n, freq="h", tz="UTC")
    rng = np.random.default_rng(11)
    close = pd.Series(0.65 + np.cumsum(rng.normal(0, 0.0008, n)), index=idx)
    return pd.DataFrame({"open": close.shift(1).fillna(close.iloc[0]), "high": close + 0.001,
                         "low": close - 0.001, "close": close, "tick_volume": 100.0},
                        index=idx)


PARAMS = {"z_obs": 24, "z_lo": 0.5, "z_hi": 99.0, "direction": "short", "hold_bars": 24}


def test_world_macro_state_is_registered_and_admitted():
    from mt5desk import families_orthogonal as fo

    from research import family_policy
    assert fo.ORTHOGONAL_FAMILIES["world_macro_state"].__name__ == "family_world_macro_state"
    assert "world_macro_state" in fo.FAMILY_INPUTS
    assert fo.FAMILY_TIMEFRAMES["world_macro_state"][0] == ("H1", "H4", "D1")
    assert not family_policy.family_banned("world_macro_state")
    assert family_policy.family_banned("discovered")


def test_the_sealed_gauntlet_rebuilds_the_cell_identically(box):
    """Through `external_gauntlet.build_cell` -- the judge's own door, imported, not edited."""
    from desks.mt5.scripts import external_gauntlet as gauntlet
    key = _fixture_store(box)
    df = _bars()
    params = {"series_key": key, **PARAMS}
    a = gauntlet.build_cell("AUDUSD", "world_macro_state", dict(params), {}, h1_override=df)
    b = gauntlet.build_cell("AUDUSD", "world_macro_state", dict(params), {}, h1_override=df)
    assert a is not None and b is not None, gauntlet.LAST_BUILD_FAILURE
    sa = [(s.time, s.side, s.ttl_bars) for s in a["sigs"]]
    sb = [(s.time, s.side, s.ttl_bars) for s in b["sigs"]]
    assert sa and sa == sb
    assert {s[1] for s in sa} == {-1}
    # the forward clock's call shape produces the same signals from the same identity
    from mt5desk import families_orthogonal as fo
    from mt5desk.family_call import signals
    fwd = signals(fo.ORTHOGONAL_FAMILIES["world_macro_state"], df, side=-1, params=params)
    assert [(s.time, s.side) for s in fwd] == [(t, sd) for t, sd, _ in sa]


def test_the_family_is_point_in_time():
    """The z needs a full window of the series' own prints; nothing earlier is emitted."""
    from mt5desk.family_world_macro import world_state_z
    s = pd.Series(range(40), index=pd.date_range("2024-01-31", periods=40, freq="ME", tz="UTC"),
                  dtype=float)
    z = world_state_z(s + (s % 3), 24)
    assert z.index.min() == s.index[23]


def test_an_absent_series_yields_no_signals_not_an_error(box):
    from mt5desk.family_world_macro import family_world_macro_state
    assert family_world_macro_state(_bars(2000), series_key="wdeadbeef0000", **PARAMS) == []
    assert family_world_macro_state(_bars(2000), series_key="", **PARAMS) == []


def test_the_proposer_mints_world_macro_state_cells_from_the_exposure(box, monkeypatch):
    from research import proposer_common as pc
    from research import world_macro_proposer as P
    _fixture_store(box)
    df = _bars()
    monkeypatch.setattr(P, "REPORT", box / "WORLD_MACRO_PROPOSER.json")
    monkeypatch.setattr(pc, "bars", lambda sym: df)
    monkeypatch.setattr(pc, "cost_frac", lambda sym, meta, close: 0.0)
    monkeypatch.setattr(pc, "artifact_hours", lambda d: {})
    rep = P.run(budget_s=120, now=NOW, donate=False)
    assert rep["status"] == "OK" and rep["symbols_available"] >= 1
    assert rep["tests_run"] > 0
    assert json.loads((box / "WORLD_MACRO_PROPOSER.json").read_text("utf-8"))["family"] == \
        "world_macro_state"
    cur = json.loads((W.STORE / "proposer_cursor.json").read_text("utf-8"))
    assert "next" in cur


def test_the_proposer_reports_unmeasured_before_any_exposure(box, monkeypatch):
    from research import world_macro_proposer as P
    monkeypatch.setattr(P, "REPORT", box / "WORLD_MACRO_PROPOSER.json")
    rep = P.run(budget_s=10, now=NOW, donate=False)
    assert rep["status"] == W.UNMEASURED and rep["tests_run"] == W.UNMEASURED


def test_hourly_cycle_runs_hunter_then_its_consumer():
    src = (DESK / "research" / "hourly_cycle.py").read_text("utf-8")
    acq = src.index('acq = _costed("acquire_datasets"')
    wdh = src.index('wdh = _costed("world_dataset_hunt"')
    wmp = src.index('wmp = _costed("world_macro_proposer"')
    census = src.index('sxc = _costed("source_experiment_census"')
    assert acq < wdh < wmp < census
    assert '"world_dataset_hunt": wdh' in src and '"world_macro_proposer": wmp' in src
    assert '"world_dataset_hunt": 1_020' in src and '"world_macro_proposer": 1_020' in src
    layers = (ROOT / "libs" / "research" / "layers.py").read_text("utf-8")
    assert '"world_dataset_hunt": "information"' in layers
    assert '"world_macro_proposer": "prediction"' in layers


def test_the_banned_discovered_path_is_not_fed():
    es = (DESK / "research" / "edge_search.py").read_text("utf-8")
    fam = (DESK / "mt5desk" / "families_orthogonal.py").read_text("utf-8")
    assert "world_series_for" not in es and "ext_world_" not in es
    assert "world_feature" not in fam
