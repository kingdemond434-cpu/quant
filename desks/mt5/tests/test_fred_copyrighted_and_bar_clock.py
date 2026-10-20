"""FOLLOW-UP TO THE YAHOO CUT (2026-10-14), tested as behaviour, no network.

1. FRED series owned by third parties (their FRED notes carry a copyright notice) are an
   IDEAS_ONLY row `fred_copyrighted`: refused as live input before any request, UNMEASURED with
   a missed_growth line; the gold fix rides on MT5 XAUUSD under its own name; a realised-vol
   proxy from own bars is published under its OWN name, never as VIX.
2. The ideas-lane Yahoo readers (earnings_miner, the source-route probe) go through the polite
   door: honest UA, robots, holds, no retry.
3. BAR_CLOCK.json carries provenance: own_tick_tape where the desk's own tape re-measured a
   season (broker time_msc vs OUR recv_utc), yahoo_inferred_legacy (kept, never dropped) where
   it has not.
"""
from __future__ import annotations

import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import pytest

DESK = Path(__file__).resolve().parents[1]
ROOT = DESK.parents[1]
for _p in (str(DESK / "research"), str(DESK), str(ROOT), str(ROOT / "scripts")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import free_data as fd  # noqa: E402
import futures_lead_lag as fll  # noqa: E402
import macro_desk  # noqa: E402
import missed_growth as mg  # noqa: E402
import run_hunt23  # noqa: E402

from libs.data import polite_fetch as pf  # noqa: E402
from libs.data import terms_fence as tf  # noqa: E402
from libs.research import bar_clock  # noqa: E402

THIRD_PARTY = ("VIXCLS", "BAMLH0A0HYM2", "UMCSENT", "GOLDAMGBD228NLBM")


# ------------------------------------------------------------------ 1. the register
def test_the_fred_copyrighted_row_quotes_fred_and_each_series_notes() -> None:
    row = tf.SOURCE_POLICY["fred_copyrighted"]
    assert tf.status("fred_copyrighted") == tf.IDEAS_ONLY
    assert tf.terms_state("fred_copyrighted") == "READ"
    assert set(row["series"]) == set(THIRD_PARTY)
    cl = row["terms"]["clauses"]
    assert "cannot give you such permission" in cl["faq:cannot"]
    assert "MUST CONTACT THE DATA OWNER" in cl["tou:third_party"]
    notes = row["terms"]["series_notes"]
    assert "Chicago Board Options Exchange" in notes["VIXCLS"]
    assert "prior written permission of ICE Data Indices" in notes["BAMLH0A0HYM2"]
    assert notes["GOLDAMGBD228NLBM"].startswith("UNREADABLE"), "deleted from FRED: fail closed"
    for sid in THIRD_PARTY:
        assert tf.fred_series_source(sid) == "fred_copyrighted"
        assert tf.fred_series_source(sid.lower()) == "fred_copyrighted"
    for sid in ("DGS10", "DTWEXBGS", "SOFR", "CP0000EZ19M086NEST", "DCOILWTICO"):
        assert tf.fred_series_source(sid) is None, sid
    # the series' own page is the route, and it is never live input
    assert tf.input_source("https://fred.stlouisfed.org/series/VIXCLS") == "fred_copyrighted"
    assert tf.input_source("https://fred.stlouisfed.org/series/VIXCLS9D") is None
    assert tf.input_source("https://fred.stlouisfed.org/series/DGS10") is None


def test_a_third_party_series_is_refused_before_any_request(
        monkeypatch: pytest.MonkeyPatch) -> None:
    touched: list[str] = []
    monkeypatch.setattr(fd, "_get", lambda url, *a, **k: touched.append(url) or b"")
    monkeypatch.setattr(fd, "_cache_get", lambda k: touched.append(k) or None)
    monkeypatch.setattr(fd, "_fred_alternate", lambda *a: touched.append("mirror") or {"x": 1})
    for sid in THIRD_PARTY:
        assert fd.fred_series(sid) is None
        assert fd.fred_series(sid, vintage="2026-01-01") is None
    assert touched == [], "no URL, no cache read, no mirror for a third-party series"
    fd.fred_series("DGS10")
    assert any("DGS10" in t for t in touched), "a public-domain series is still fetched"


def test_the_refusal_carries_its_missed_growth_line() -> None:
    cut = fd.fred_refusal("VIXCLS", "macro_desk.state")
    assert cut is not None and cut["status"] == fd.UNMEASURED_NO_LICENSED_SOURCE
    line = cut["missed_growth"]
    assert line["delta_elogw"] == "UNMEASURED" and line["kind"] == "ideas_only_refusal"
    assert line["policy_row"] == "fred_copyrighted" and "Chicago" in line["fred_notes"]
    gold = fd.fred_refusal("GOLDAMGBD228NLBM", "x", substituted=True)
    assert gold is not None and gold["status"] == "SUBSTITUTED"
    assert gold["substitute"] == "mt5_own_bars:XAUUSD"
    assert fd.fred_refusal("DGS10", "x") is None


def test_series_state_never_fetches_a_third_party_series(
        monkeypatch: pytest.MonkeyPatch) -> None:
    asked: list[str] = []
    monkeypatch.setattr(fd, "fred_series", lambda sid, *a, **k: asked.append(sid) or None)
    got = macro_desk.series_state("BAMLH0A0HYM2")
    assert asked == [] and got["ok"] is False
    assert got["status"] == fd.UNMEASURED_NO_LICENSED_SOURCE
    assert got["missed_growth"]["delta_elogw"] == "UNMEASURED"


def _h1(u: Path, symbol: str, days: int = 60, level: float = 100.0) -> None:
    u.mkdir(parents=True, exist_ok=True)
    idx = pd.date_range("2026-05-01", periods=days * 24, freq="h", tz="UTC")
    close = level * np.exp(np.cumsum(np.random.default_rng(3).normal(0, 0.002, len(idx))))
    pd.DataFrame({"close": close}, index=idx).to_parquet(u / f"{symbol}_H1.parquet")


def test_the_anchors_drop_third_party_history_and_publish_the_rv_proxy_under_its_own_name(
        monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    u = tmp_path / "universe"
    for sym in ("USDX", "US500", "XAUUSD", "XTIUSD"):
        _h1(u, sym)
    monkeypatch.setattr(fd, "UNIVERSE_DIR", u)
    monkeypatch.setattr(macro_desk, "ANCHORS_F", tmp_path / "anchors.pkl")
    monkeypatch.setattr(macro_desk, "ANCHORS_PROV_F", tmp_path / "anchors.provenance.json")
    monkeypatch.setattr(macro_desk, "log", lambda m: None)
    asked: list[str] = []

    def fake(sid: str, *a: Any, **k: Any) -> dict[str, float]:
        asked.append(sid)
        return {f"2026-06-{d:02d}": 4.0 for d in range(1, 29)}
    monkeypatch.setattr(fd, "fred_series", fake)
    old = pd.DataFrame({"VIXCLS": [15.0, 16.0], "GOLDAMGBD228NLBM": [1500.0, 1510.0],
                        "DGS10": [3.9, 3.95]},
                       index=pd.to_datetime(["2020-01-02", "2020-01-03"]))
    old.to_pickle(tmp_path / "anchors.pkl")

    macro_desk.anchors()

    assert not set(asked) & set(THIRD_PARTY), "a third-party series was requested"
    df = pd.read_pickle(tmp_path / "anchors.pkl")  # noqa: S301 -- this test wrote it
    for c in ("VIXCLS", "GOLDAMGBD228NLBM", "VIX"):
        assert c not in df.columns, c
    assert df["DGS10"].loc["2020-01-02"] == 3.9
    assert df["GC"].notna().any(), "gold rides on MT5 XAUUSD under its own name"
    rv = df[macro_desk.RV_PROXY].dropna()
    assert len(rv) > 0 and (rv > 0).all()
    prov = json.loads((tmp_path / "anchors.provenance.json").read_text("utf-8"))
    fc = prov["fred_copyrighted"]
    assert fc["VIXCLS"]["status"] == fd.UNMEASURED_NO_LICENSED_SOURCE
    assert fc["GOLDAMGBD228NLBM"]["status"] == "SUBSTITUTED"
    assert fc["GOLDAMGBD228NLBM"]["carried_as"] == "GC"
    assert fc[macro_desk.RV_PROXY]["status"] == "MEASURED_OWN_BARS"
    assert "NOT VIX" in fc[macro_desk.RV_PROXY]["label"]
    fred_lines = [x for x in prov["missed_growth"] if x.get("policy_row") == "fred_copyrighted"]
    assert {x["fred_series"] for x in fred_lines} == {"VIXCLS", "GOLDAMGBD228NLBM"}


def test_the_rv_proxy_is_unmeasured_without_us500() -> None:
    cols: dict[str, pd.Series] = {}
    out = macro_desk.fred_copyrighted_columns(cols)
    assert macro_desk.RV_PROXY not in cols
    assert out[macro_desk.RV_PROXY]["status"] == "UNMEASURED_NO_BARS_ON_HOST"
    assert out["GOLDAMGBD228NLBM"]["status"] == fd.UNMEASURED_NO_LICENSED_SOURCE


def test_macro_state_reads_gold_from_own_bars_and_publishes_the_cut(
        monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr(macro_desk, "STATE_F", tmp_path / "macro_state.json")
    monkeypatch.setattr(macro_desk, "log", lambda m: None)
    asked: list[str] = []

    def fake(sid: str, *a: Any, **k: Any) -> dict[str, float]:
        asked.append(sid)
        return {f"2025-{m:02d}-{d:02d}": 1.0 + m / 10 + d / 100
                for m in range(1, 13) for d in range(1, 29)}
    monkeypatch.setattr(fd, "fred_series", fake)
    monkeypatch.setattr(fd, "mt5_daily", lambda s, *a: {"2026-10-01": 2650.0} if s == "XAUUSD"
                        else None)
    macro_desk.build_state()
    st = json.loads((tmp_path / "macro_state.json").read_text("utf-8"))
    assert not set(asked) & set(THIRD_PARTY)
    assert st["states"]["GOLD_USD"] == 2650.0
    assert st["states"]["GOLD_USD_SOURCE"].startswith("mt5_own_bars:XAUUSD")
    assert st["states"]["RISK_STATE"] is None, "both risk inputs are third-party: UNMEASURED"
    assert set(st["unmeasured_no_licensed_source"]) == {"VIXCLS", "BAMLH0A0HYM2", "UMCSENT"}
    assert st["fred_copyrighted"]["GOLDAMGBD228NLBM"]["status"] == "SUBSTITUTED"
    assert all(x["delta_elogw"] == "UNMEASURED" for x in st["missed_growth"])


def test_hunt23_never_falls_back_to_vixcls(monkeypatch: pytest.MonkeyPatch) -> None:
    idx = pd.date_range("2024-01-01", periods=300, freq="D")
    anch = pd.DataFrame({"VIXCLS": np.linspace(10, 30, 300),
                         "GOLDAMGBD228NLBM": np.linspace(1800, 2000, 300)}, index=idx)
    monkeypatch.setattr(run_hunt23, "_anchor_cache", anch)
    monkeypatch.setattr(run_hunt23, "UNMEASURED", {})
    assert not len(run_hunt23._pick(anch, "VIX", "VIXCLS"))
    assert not len(run_hunt23._pick(anch, "GC", "GOLDAMGBD228NLBM"))
    assert run_hunt23.fam_anc_jpy_risk_lag(pd.DataFrame(), pd.DataFrame(), 1) == []
    row = run_hunt23.UNMEASURED["anc_jpy_risk_lag"]
    assert row["status"] == fd.UNMEASURED_NO_LICENSED_SOURCE
    assert row["missed_growth"]["delta_elogw"] == "UNMEASURED"


def test_the_bill_separates_the_fred_cut_from_the_yahoo_cut(tmp_path: Path) -> None:
    a = tmp_path / "a.json"
    a.write_text(json.dumps({"missed_growth": [
        fd.fred_cut_line("VIXCLS", "macro_desk.anchors",
                         status=fd.UNMEASURED_NO_LICENSED_SOURCE),
        fd.yahoo_cut_line("^TNX", "macro_desk.anchors", status="SUBSTITUTED")]}), "utf-8")
    fred = mg.fred_copyrighted_cut_lines((("macro_desk.anchors", a),
                                          ("run_hunt23", tmp_path / "no.json")))
    assert fred["n_cut"] == 1 and fred["verdict"] == "UNMEASURED"
    assert fred["unmeasured_no_licensed_source"] == ["macro_desk.anchors:VIXCLS"]
    assert fred["organs_without_artifact"] == ["run_hunt23"]
    yahoo = mg.yahoo_cut_lines((("macro_desk.anchors", a),))
    assert yahoo["n_cut"] == 1 and yahoo["lines"][0]["yahoo_symbol"] == "^TNX"


# ------------------------------------------------------------------ 2. the polite door
def _resp(url: str, **k: Any) -> pf.Response:
    return pf.Response(url=url, **k)


def test_earnings_miner_reads_through_the_polite_door_and_stops_on_a_hold() -> None:
    import side_channels.earnings_miner as em
    src = (DESK / "side_channels" / "earnings_miner.py").read_text("utf-8")
    assert "import requests" not in src and "requests.get" not in src
    calls: list[tuple[str, dict[str, Any]]] = []

    def get(url: str, **k: Any) -> pf.Response:
        calls.append((url, k))
        return _resp(url, status=429, verdict="HELD", error="HELD: HTTP 429")
    rows = em.mine_earnings_calendar(get=get)
    assert len(calls) == 1, "a hold is a hard stop: no further page this sweep"
    url, k = calls[0]
    assert k["live_input"] is False and k["retries"] == 0
    assert k["headers"]["User-Agent"] == pf.DESK_UA
    assert rows == [{**rows[0], "kind": "walled", "verdict": "HELD"}]
    assert rows[0]["terms_status"] == "IDEAS_ONLY"


def test_earnings_miner_labels_its_rows_ideas_only() -> None:
    import side_channels.earnings_miner as em

    def get(url: str, **k: Any) -> pf.Response:
        return _resp(url, status=200, text="EarningsDate Oct 30, 2026")
    rows = em.mine_earnings_calendar(get=get)
    assert rows and all(r["terms_status"] == "IDEAS_ONLY" for r in rows)
    assert rows[0]["url"].startswith("https://finance.yahoo.com/quote/")


def test_the_route_probe_reaches_yahoo_only_through_the_polite_door() -> None:
    import check_source_routes as csr
    route = next(r for r in csr.ROUTES if r["name"] == "yahoo_chart")
    assert route["polite"] is True and route["terms_status"] == "IDEAS_ONLY"
    calls: list[dict[str, Any]] = []

    def refused(url: str, **k: Any) -> pf.Response:
        calls.append(k)
        return _resp(url, verdict="ROBOTS_DISALLOW", error="ROBOTS_DISALLOW: /v8/")
    got = csr.probe(route, get=refused)
    assert got["status"] == "REFUSED" and got["via"] == "polite_fetch"
    assert calls[0]["retries"] == 0

    def ok(url: str, **k: Any) -> pf.Response:
        return _resp(url, status=200, content_type="application/json",
                     body=b'{"chart": {"result": []}}' * 4)
    assert csr.probe(route, get=ok)["status"] == "OK"

    def html(url: str, **k: Any) -> pf.Response:
        return _resp(url, status=200, content_type="text/html", body=b"<html>" + b"x" * 200)
    assert csr.probe(route, get=html)["status"] == "MOVED"


# ------------------------------------------------------------------ 3. the bar clock
def _tape(root: Path, sym: str, day: str, offset_h: float, n: int = 500,
          lag_s: float = 2.0, recv: bool = True) -> None:
    d = root / sym
    d.mkdir(parents=True, exist_ok=True)
    t0 = datetime.fromisoformat(day).replace(hour=10, tzinfo=UTC).timestamp() * 1000
    true_ms = t0 + np.arange(n) * 1000.0
    frame = pd.DataFrame({"time_msc": (true_ms + offset_h * 3_600_000).astype("int64"),
                          "bid": 100.0, "ask": 100.1})
    if recv:
        frame["recv_utc"] = pd.to_datetime(true_ms + lag_s * 1000, unit="ms", utc=True)
    frame.to_parquet(d / f"{day}.parquet")


def test_the_tape_measures_the_offset_from_broker_stamp_against_receipt(tmp_path: Path) -> None:
    root = tmp_path / "ticks"
    _tape(root, "XAUUSD", "2026-07-01", 3)
    _tape(root, "EURUSD", "2026-07-02", 3, lag_s=40)
    _tape(root, "EURUSD", "2026-10-14", 3)            # shoulder: measures neither season
    _tape(root, "GBPUSD", "2026-07-03", 3, recv=False)  # no receipt clock: not a reading
    got = fll.tape_offsets(root)
    s = got["per_season"]["summer"]
    assert s["offset_h"] == 3 and s["agrees_across_pairs"] and s["n_days"] == 2
    assert got["per_season"]["winter"]["offset_h"] is None
    assert got["measured_seasons"] == ["summer"] and got["unresolved_days"] == 1


def test_a_stalled_recorder_or_disagreeing_days_resolve_nothing(tmp_path: Path) -> None:
    root = tmp_path / "ticks"
    _tape(root, "XAUUSD", "2026-07-01", 3, lag_s=1800)   # 30 min receipt lag
    assert fll.tape_offsets(root)["per_season"]["summer"]["offset_h"] is None
    _tape(root, "EURUSD", "2026-07-02", 3)
    _tape(root, "GBPUSD", "2026-07-02", 2)
    s = fll.tape_offsets(root)["per_season"]["summer"]
    assert s["offset_h"] is None and s["agrees_across_pairs"] is False


def test_the_clock_is_stamped_never_dropped(tmp_path: Path) -> None:
    legacy = {"at": "2026-09-10", "per_season": {
        "summer": {"offset_h": 3, "agrees_across_pairs": True},
        "winter": {"offset_h": 2, "agrees_across_pairs": True}}}
    root = tmp_path / "ticks"
    _tape(root, "XAUUSD", "2026-07-01", 3)
    doc = fll.stamp_clock(legacy, fll.tape_offsets(root))
    assert doc["per_season"]["summer"]["provenance"] == fll.PROV_TAPE
    assert doc["per_season"]["summer"]["legacy_offset_h"] == 3
    assert doc["per_season"]["winter"] == {**legacy["per_season"]["winter"],
                                           "provenance": fll.PROV_LEGACY}
    assert doc["provenance"] == "mixed" and doc["varies_with_dst"] is True
    assert doc["remeasure_needed"]["delta_elogw"] == "UNMEASURED"
    clock = tmp_path / "desks" / "mt5" / "reports" / "BAR_CLOCK.json"
    clock.parent.mkdir(parents=True)
    clock.write_text(json.dumps(doc), "utf-8")
    assert bar_clock.offsets(tmp_path) == {"summer": 3, "winter": 2}, "offsets survive the stamp"
    assert bar_clock.provenance(tmp_path) == {
        "overall": "mixed", "per_season": {"summer": fll.PROV_TAPE, "winter": fll.PROV_LEGACY}}
    # an unstamped (pre-cut) file reads as what it was
    clock.write_text(json.dumps(legacy), "utf-8")
    assert bar_clock.provenance(tmp_path)["overall"] == fll.PROV_LEGACY
    assert fll.stamp_clock({}, {"per_season": {}}) == {}


def test_a_full_tape_replaces_the_legacy_stamp(tmp_path: Path) -> None:
    root = tmp_path / "ticks"
    _tape(root, "XAUUSD", "2026-07-01", 3)
    _tape(root, "XAUUSD", "2026-01-05", 2)
    doc = fll.stamp_clock({"per_season": {"summer": {"offset_h": 3}}}, fll.tape_offsets(root))
    assert doc["provenance"] == fll.PROV_TAPE and "remeasure_needed" not in doc
    assert doc["per_season"]["winter"]["offset_h"] == 2
