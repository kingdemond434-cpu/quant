"""Participant-flow features, point-in-time revisions, the growth decomposition and the
grammar generators -- everything the 2026-09-04 extension added, pinned on synthetic data.

What is pinned:

  * the four flow features are causal (the store's own falsifier accepts them), degrade to
    all-NaN WITH a recorded reason rather than raising, and `cot_z` sees a report only from
    its release time -- never from its report date;
  * a feature that reads files outside the bars carries their identity in its id, so a
    refreshed COT file cannot be served from the cache under the old id;
  * `pit.revise` chains a stamped copy to its predecessor, never mutates the input, floors the
    revision's availability at the revision time, and keeps the payload hash a function of
    content alone; `latest_as_of` serves the vintage that existed at the decision time;
  * every growth term is present with value / basis / why, reads UNMEASURED with the path
    named when its artifact is absent, and the sizing term charges timidity with the stated
    formula;
  * the flow sampler only ever produces valid trees and moves toward transitions the history
    rewarded; symbolic regression fits on the first 70% only and reports the holdout;
  * the evolution records which generator made every individual and honours the weight file.
"""
from __future__ import annotations

import hashlib
import json
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

_DESK = Path(__file__).resolve().parents[1]
_ROOT = _DESK.parent.parent
for p in (str(_DESK), str(_DESK / "research"), str(_ROOT)):
    if p not in sys.path:
        sys.path.insert(0, p)

from libs.data import feature_store as fs  # noqa: E402
from libs.data import pit  # noqa: E402
from libs.research import alpha_grammar as ag  # noqa: E402
from libs.research import coevolution  # noqa: E402
from libs.research import generators as gen  # noqa: E402
from research import allocator_attribution as attr  # noqa: E402
from research import alpha_evolution  # noqa: E402


def _bars(n: int = 1500, seed: int = 0, start: str = "2025-01-06") -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    idx = pd.date_range(start, periods=n, freq="h", tz="UTC")
    close = 100.0 + np.cumsum(rng.normal(scale=0.1, size=n))
    df = pd.DataFrame({"open": np.r_[close[0], close[:-1]], "high": close + 0.1,
                       "low": close - 0.1, "close": close,
                       "spread": rng.integers(10, 20, n).astype(float),
                       "tick_volume": rng.integers(50, 500, n).astype(float)}, index=idx)
    df.index.name = "time"
    return df


def _cot_table(dates: pd.DatetimeIndex, net: np.ndarray) -> pd.DataFrame:
    """A legacy-shaped COT table: net speculative position = noncomm long - short."""
    return pd.DataFrame({"report_date": dates, "commodity_name": "X",
                         "contract_market_name": "X", "open_interest_all": 1000,
                         "noncomm_positions_long_all": (1000 + net).astype(int),
                         "noncomm_positions_short_all": 1000,
                         "comm_positions_long_all": 0, "comm_positions_short_all": 0})


@pytest.fixture
def cot_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """A synthetic COT source in place of the desk's, with gold, aud and jpy markets."""
    d = tmp_path / "cot"
    d.mkdir()
    dates = pd.date_range("2024-01-02", periods=120, freq="7D", tz="UTC")     # Tuesdays
    rng = np.random.default_rng(1)
    for stem, scale in (("gold", 100.0), ("aud", 50.0), ("jpy", 70.0)):
        _cot_table(dates, np.cumsum(rng.normal(scale=scale, size=len(dates)))).to_parquet(
            d / f"{stem}.parquet")
    monkeypatch.setattr(fs, "COT_SOURCES", ((d, "noncomm_positions_long_all",
                                              "noncomm_positions_short_all"),))
    return d


@pytest.fixture
def universe_json(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    p = tmp_path / "universe.json"
    p.write_text(json.dumps({"XAUUSD": {"swap_long": -61.76, "swap_short": 29.45},
                             "NOSWAP": {"symbol": "NOSWAP"}}))
    monkeypatch.setattr(fs, "UNIVERSE_JSON", p)
    monkeypatch.setattr(fs, "_UNIVERSE_CACHE", {"key": None, "doc": {}})
    return p


# --------------------------------------------------------------------------- flow features
def test_tick_imbalance_is_bounded_signed_and_causal(tmp_path: Path) -> None:
    store = fs.FeatureStore(tmp_path / "store")
    df = _bars(400)
    v = store.get("tick_imbalance", df, {"w": 24}, check_causal=True)
    fin = v[np.isfinite(v)]
    assert fin.size > 300 and (np.abs(fin) <= 1.0 + 1e-12).all()
    assert np.isnan(v[:23]).all()                                   # warm-up
    up = df.copy()
    up["close"] = up["open"] + 1.0                                   # every bar closes up
    assert np.allclose(store.get("tick_imbalance", up, {"w": 24})[23:], 1.0)
    dn = df.copy()
    dn["close"] = dn["open"] - 1.0
    assert np.allclose(store.get("tick_imbalance", dn, {"w": 24})[23:], -1.0)


def test_tick_imbalance_without_tick_volume_is_nan_with_the_reason(tmp_path: Path) -> None:
    store = fs.FeatureStore(tmp_path / "store")
    v = store.get("tick_imbalance", _bars(200).drop(columns=["tick_volume"]), {},
                  check_causal=True)
    assert np.isnan(v).all() and "tick_volume" in fs.LAST_REASON["tick_imbalance"]


def test_session_participation_compares_an_hour_with_its_own_history(tmp_path: Path) -> None:
    store = fs.FeatureStore(tmp_path / "store")
    df = _bars(24 * 40)
    df["tick_volume"] = 100.0
    hour = df.index.hour
    pos = np.where(hour == 10)[0]
    df.iloc[pos[25], df.columns.get_loc("tick_volume")] = 200.0     # one busy 10:00
    v = store.get("session_participation", df, {"n": 20}, check_causal=True)
    assert v[pos[25]] == pytest.approx(np.log(2.0))
    assert np.isnan(v[pos[:20]]).all()                               # needs 20 prior 10:00s
    assert v[pos[21]] == pytest.approx(0.0)
    # The busy bar is in the NEXT bar's reference window, not its own.
    assert v[pos[26]] == pytest.approx(0.0)                          # median of 20 with one 200
    assert np.isnan(store.get("session_participation", df.drop(columns=["tick_volume"]),
                              {})).all()
    assert "tick_volume" in fs.LAST_REASON["session_participation"]


def test_swap_features_are_static_per_symbol_and_nan_when_unknown(
        tmp_path: Path, universe_json: Path) -> None:
    store = fs.FeatureStore(tmp_path / "store")
    df = _bars(300)
    diff = store.get("swap_diff", df, {"symbol": "XAUUSD"}, check_causal=True)
    assert np.allclose(diff, -61.76 - 29.45)
    assert np.allclose(store.get("swap_long", df, {"symbol": "XAUUSD"}, check_causal=True),
                       -61.76)
    assert np.allclose(store.get("swap_short", df, {"symbol": "XAUUSD"}, check_causal=True),
                       29.45)
    assert np.isnan(store.get("swap_diff", df, {"symbol": "ZZZ"}, check_causal=True)).all()
    assert "ZZZ" in fs.LAST_REASON["swap_diff"]
    assert np.isnan(store.get("swap_diff", df, {"symbol": "NOSWAP"})).all()
    assert "swap_long" in fs.LAST_REASON["swap_diff"]


def test_an_external_input_is_part_of_the_feature_id(tmp_path: Path,
                                                      universe_json: Path) -> None:
    """A re-quoted swap must not be served from the cache under the old id."""
    store = fs.FeatureStore(tmp_path / "store")
    df = _bars(300)
    a = store.get("swap_diff", df, {"symbol": "XAUUSD"})
    universe_json.write_text(json.dumps({"XAUUSD": {"swap_long": -10.0, "swap_short": 1.0}}))
    import os
    os.utime(universe_json, (universe_json.stat().st_atime, universe_json.stat().st_mtime + 5))
    b = store.get("swap_diff", df, {"symbol": "XAUUSD"})
    assert store.misses == 2 and a[0] != b[0] and b[0] == pytest.approx(-11.0)
    assert fs.feature_id("x", {}, "d") != fs.feature_id("x", {}, "d", external="f:1")
    assert fs.feature_id("x", {}, "d") == fs.feature_id("x", {}, "d", external=None)


def test_cot_z_is_point_in_time_and_z_scored(tmp_path: Path, cot_dir: Path) -> None:
    store = fs.FeatureStore(tmp_path / "store")
    df = _bars(24 * 400, start="2024-06-03")                          # ~400 days of H1
    v = store.get("cot_z", df, {"symbol": "XAUUSD", "w": 20}, check_causal=True)
    assert "cot_z" not in fs.LAST_REASON and "gold.parquet" in fs.LAST_DETAIL["cot_z"]
    rep = pd.read_parquet(cot_dir / "gold.parquet")
    net = (rep["noncomm_positions_long_all"] - rep["noncomm_positions_short_all"]).astype(float)
    r = net.rolling(20, min_periods=20)
    z = ((net - r.mean()) / r.std()).to_numpy()
    release = (rep["report_date"] + fs.COT_RELEASE_LAG).to_numpy()
    for k in range(40, 60):
        t_release = pd.Timestamp(release[k])
        before = df.index.get_indexer([t_release - timedelta(hours=1)])[0]
        at = df.index.get_indexer([t_release])[0]
        assert at > 0 and before >= 0
        assert v[at] == pytest.approx(z[k])                          # knowable at release
        assert v[before] == pytest.approx(z[k - 1])                  # NOT one hour earlier
    changes = np.where(np.diff(np.nan_to_num(v, nan=-1e9)) != 0)[0] + 1
    assert len(changes) > 30
    assert all(df.index[i].dayofweek == 4 and df.index[i].hour == 21 for i in changes)


def test_cot_z_pairs_are_base_minus_quote_and_usd_is_the_numeraire(
        tmp_path: Path, cot_dir: Path) -> None:
    store = fs.FeatureStore(tmp_path / "store")
    df = _bars(24 * 300, start="2024-06-03")
    aud = store.get("cot_z", df, {"symbol": "AUDUSD", "w": 20}, check_causal=True)
    jpy = store.get("cot_z", df, {"symbol": "USDJPY", "w": 20}, check_causal=True)
    cross = store.get("cot_z", df, {"symbol": "AUDJPY", "w": 20}, check_causal=True)
    ok = np.isfinite(aud) & np.isfinite(jpy) & np.isfinite(cross)
    assert ok.sum() > 1000
    assert np.allclose(cross[ok], aud[ok] + jpy[ok])                  # +aud, -jpy = aud + usdjpy
    assert fs.cot_legs("USDJPY") == [("jpy", -1.0)] and fs.cot_legs("XAUUSD") == [("gold", 1.0)]
    assert fs.cot_legs("US500") == [("sp500", 1.0)] and fs.cot_legs("USDCNH") == []


def test_cot_z_degrades_with_a_reason_never_an_exception(tmp_path: Path, cot_dir: Path) -> None:
    store = fs.FeatureStore(tmp_path / "store")
    df = _bars(300)
    assert np.isnan(store.get("cot_z", df, {"symbol": "USDCNH"}, check_causal=True)).all()
    assert "no CFTC market" in fs.LAST_REASON["cot_z"]
    assert np.isnan(store.get("cot_z", df, {"symbol": "EURUSD"}, check_causal=True)).all()
    assert "eur" in fs.LAST_REASON["cot_z"] and "no COT file" in fs.LAST_REASON["cot_z"]
    early = _bars(300, start="2020-01-06")                            # before any report
    assert np.isnan(store.get("cot_z", early, {"symbol": "XAUUSD", "w": 5})).all()
    assert "no report available" in fs.LAST_REASON["cot_z"]
    (cot_dir / "silver.parquet").write_bytes(b"not a parquet")
    assert np.isnan(store.get("cot_z", df, {"symbol": "XAGUSD"})).all()
    assert "silver.parquet" in fs.LAST_REASON["cot_z"]


def test_cot_z_honours_a_rows_own_available_time(tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
                                                 ) -> None:
    d = tmp_path / "cot2"
    d.mkdir()
    dates = pd.date_range("2024-01-02", periods=30, freq="7D", tz="UTC")
    tab = _cot_table(dates, np.cumsum(np.random.default_rng(2).normal(scale=50.0, size=30)))
    tab["available_time"] = dates + pd.Timedelta(days=10)             # a slow publisher
    tab.to_parquet(d / "gold.parquet")
    monkeypatch.setattr(fs, "COT_SOURCES", ((d, "noncomm_positions_long_all",
                                              "noncomm_positions_short_all"),))
    df = _bars(24 * 250, start="2024-01-01")
    v = fs.FeatureStore(tmp_path / "s").get("cot_z", df, {"symbol": "XAUUSD", "w": 5},
                                             check_causal=True)
    changes = np.where(np.diff(np.nan_to_num(v, nan=-1e9)) != 0)[0] + 1
    assert len(changes) > 10
    assert all(df.index[i].dayofweek == 4 and df.index[i].hour == 0 for i in changes)


def test_vocab_carries_the_flow_features_and_every_entry_is_causal(
        tmp_path: Path, cot_dir: Path, universe_json: Path) -> None:
    names = {n for n, _ in coevolution.VOCAB}
    assert {"tick_imbalance", "session_participation", "swap_diff", "cot_z"} <= names
    store = fs.FeatureStore(tmp_path / "store")
    df = _bars(24 * 60, start="2025-01-06")
    for name, params in coevolution.VOCAB:
        assert name in fs.REGISTRY
        assert store.get(name, df, params, check_causal=True).shape == (len(df),)


# --------------------------------------------------------------------------- revisions
def test_revise_chains_a_stamped_copy_and_never_mutates_the_input() -> None:
    row = {"title": "x", "found_at": "2026-01-02T03:04:05+00:00", "symbol": "XAUUSD", "v": 1}
    s = pit.stamp(row, "src", source_version="v1", now=datetime(2026, 5, 1, tzinfo=UTC))
    r1 = pit.revise({**s, "v": 2}, revision_of=s["payload_hash"], reason="restated",
                    source="src", now=datetime(2026, 6, 1, tzinfo=UTC))
    assert "revision_id" not in s and s["v"] == 1
    assert r1["revision_n"] == 1 and r1["revision_of"] == s["payload_hash"]
    assert r1["revision_reason"] == "restated"
    assert r1["revision_time"] == "2026-06-01T00:00:00+00:00"
    assert r1["available_time"] == "2026-06-01T00:00:00+00:00"       # floored at revision
    assert r1["revision_id"] == hashlib.sha256(
        f"{s['payload_hash']}{r1['payload_hash']}".encode()).hexdigest()[:16]
    assert pit.is_stamped(r1) and r1["payload_hash"] != s["payload_hash"]
    r2 = pit.revise(r1, revision_of=r1["payload_hash"], reason="again", source="src2",
                    now=datetime(2026, 7, 1, tzinfo=UTC))
    assert r2["revision_n"] == 2 and r2["revision_of"] == r1["payload_hash"]
    assert r2["source"] == "src2" and r2["revision_id"] != r1["revision_id"]


def test_payload_hash_is_content_only_and_stamp_fields_are_unchanged() -> None:
    assert pit.STAMP_FIELDS == ("event_time", "available_time", "ingested_time",
                                "source_version", "payload_hash")
    row = {"a": 1, "b": "x"}
    assert pit.payload_hash(row) == pit.payload_hash({**row, "revision_n": 3,
                                                       "revision_id": "abc", "payload_hash": "z"})
    assert pit.payload_hash(row) != pit.payload_hash({**row, "a": 2})
    same = pit.revise(pit.stamp(row, "s", source_version="v"), revision_of="h", reason="noop",
                      source="s", now=datetime(2026, 1, 1, tzinfo=UTC))
    assert same["payload_hash"] == pit.payload_hash({**row, "source": "s"})


def test_latest_as_of_serves_the_vintage_that_existed_at_the_decision_time() -> None:
    s = pit.stamp({"symbol": "XAUUSD", "v": 1, "found_at": "2026-01-02T00:00:00+00:00"}, "src",
                  source_version="v", now=datetime(2026, 1, 2, tzinfo=UTC))
    r1 = pit.revise({**s, "v": 2}, revision_of=s["payload_hash"], reason="r", source="src",
                    now=datetime(2026, 6, 1, tzinfo=UTC))
    other = pit.stamp({"symbol": "EURUSD", "v": 9}, "src", source_version="v",
                      now=datetime(2026, 3, 1, tzinfo=UTC))
    rows = [r1, other, s, {"symbol": "GBPUSD", "v": 0}]                 # unstamped: never
    at = lambda t: [(g["symbol"], g["v"]) for g in                     # noqa: E731
                    pit.latest_as_of(rows, ("symbol",), t)]
    assert at(datetime(2026, 5, 15, tzinfo=UTC)) == [("EURUSD", 9), ("XAUUSD", 1)]
    assert at(datetime(2026, 6, 15, tzinfo=UTC)) == [("XAUUSD", 2), ("EURUSD", 9)]
    assert at(datetime(2025, 1, 1, tzinfo=UTC)) == []
    c = pit.census(rows)
    assert c["rows"] == 4 and c["n_revised"] == 1 and c["max_revision_n"] == 1
    assert c["stamped"] == 3 and c["stamped_frac"] == 0.75


# --------------------------------------------------------------------------- growth decomposition
GROWTH_TERMS = ("alpha", "selection", "state", "sizing", "diversification", "execution", "exit",
                "cost", "veto")


@pytest.fixture
def desk(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    (tmp_path / "reports").mkdir()
    (tmp_path / "data").mkdir()
    monkeypatch.setattr(attr, "BASE", tmp_path)
    monkeypatch.setattr(attr, "FORECASTS", tmp_path / "data" / "pf_forecast_log.jsonl")
    monkeypatch.setattr(attr, "LIVE", tmp_path / "data" / "live_ledger.jsonl")
    monkeypatch.setattr(attr, "realized_daily", lambda: ({}, attr.UNMEASURED))
    monkeypatch.setattr(attr, "_heat_bars", lambda: (0.20, 0.30, "test"))
    return tmp_path


def test_every_growth_term_is_present_and_unmeasured_names_its_path(desk: Path) -> None:
    doc = attr.build()
    assert set(doc["terms"]) == {"edge", "correlation", "execution", "regime"}
    assert doc["residual"] == attr.UNMEASURED
    gd = doc["growth_decomposition"]
    assert tuple(gd["terms"]) == GROWTH_TERMS
    for name, t in gd["terms"].items():
        assert {"value", "basis", "why"} <= set(t), name
        assert t["value"] == attr.UNMEASURED
    assert "ALLOCATOR_PROOF.json" in gd["terms"]["selection"]["why"]
    assert "EXIT_ACCOUNTS.json" in gd["terms"]["exit"]["why"]
    assert "FILL_SURFACE.json" in gd["terms"]["cost"]["why"]
    assert "pf_forecast_log.jsonl" in gd["terms"]["sizing"]["why"]
    assert gd["residual"]["value"] == attr.UNMEASURED
    assert "never distributed" in gd["residual"]["why"]
    assert list(gd["rules"]) == list(attr.GOVERNANCE_RULES)
    assert sorted(gd["unmeasured"]) == sorted(GROWTH_TERMS) and gd["measured"] == []


def test_governance_rules_are_verbatim_in_the_docstring_and_the_report() -> None:
    flat = " ".join(str(attr.__doc__).split())
    for rule in attr.GOVERNANCE_RULES:
        assert rule in flat
    assert ("Every risk reduction mechanism must prove that it increases robust forward "
            "E[log W].") in attr.GOVERNANCE_RULES
    assert ("Every strong opportunity must be allowed to increase capital above normal when "
            "the evidence supports it.") in attr.GOVERNANCE_RULES


def _write(desk: Path, name: str, doc: dict) -> None:
    (desk / "reports" / name).write_text(json.dumps(doc), "utf-8")


def test_growth_terms_read_their_artifacts(desk: Path) -> None:
    _write(desk, "ALLOCATOR_PROOF.json", {"passed": True, "total_heat_equalised": 0.2,
                                          "scores": {"dynamic": {"mean_log_growth": 0.0010},
                                                     "equal_weight": {"mean_log_growth": 0.0004}}})
    _write(desk, "pf_allocation.json", {"effective_heat": {"nominal": 0.12, "effective": 0.08,
                                                            "n_eff": {"factor": 2.1}}})
    _write(desk, "EXIT_ACCOUNTS.json", {"summary": {"capture_ratio": {"value": 0.55}}, "n": 40})
    _write(desk, "FILL_SURFACE.json", {"n_fills": 3, "slip_w": [0.0001], "slip_resid_sd": 0.0002})
    _write(desk, "FILTER_VALUE.json", {"filters": {"a": {"filter_value_r": -1.5},
                                                   "b": {"filter_value_r": 0.5}}})
    _write(desk, "MISSED_GROWTH.json", {"rails": {
        "a": {"verdict": "EARNS_ITS_PLACE", "value_logw_per_day": 0.0002},
        "b": {"verdict": "UNMEASURED", "today": {"value_logw_per_day": 0.0}},
        "c": {"verdict": "EARNS_ITS_PLACE", "value_logw_per_veto": 0.0001, "n": 3}}})
    now = datetime.now(UTC).isoformat()
    attr.FORECASTS.write_text("\n".join(json.dumps(
        {"t": now, "total_heat": h, "expected_log_per_day": g, "book": {}})
        for h, g in ((0.10, 0.0005), (0.14, 0.0007))), "utf-8")
    gd = attr.build()["growth_decomposition"]
    t = gd["terms"]
    assert t["selection"]["value"] == pytest.approx(0.0006)
    assert "ALLOCATOR_PROOF.json" in t["selection"]["basis"]
    assert t["diversification"]["value"] == pytest.approx(0.04)
    assert t["exit"]["value"] == 0.55 and t["exit"]["n"] == 40
    assert t["cost"]["value"] == attr.UNMEASURED and "mean_slip_measured" in t["cost"]["why"]
    assert t["cost"]["n_fills"] == 3
    # veto: priced rails in log-wealth (0.0002 + 3 x 0.0001); the UNMEASURED rail is listed,
    # never counted; the R total is beside, never summed in.
    assert t["veto"]["value"] == pytest.approx(0.0005)
    assert t["veto"]["rails_unmeasured"] == ["b"]
    assert t["veto"]["filter_value_r_total"] == pytest.approx(-1.0)
    # sizing: mean heat 0.12 under the 0.20 floor, mean expected 0.0006/day
    s = t["sizing"]
    assert s["value"] == pytest.approx((0.20 - 0.12) * 0.0006 / 0.12)
    assert s["under_floor"] and not s["above_ceiling"] and "UNDER THE FLOOR" in s["reading"]
    assert s["heat_floor"] == 0.20 and s["heat_ceiling"] == 0.30
    assert sorted(gd["measured"]) == ["diversification", "exit", "selection", "sizing", "veto"]
    # the FILL_SURFACE pair, once the surface carries it, is signed like execution
    _write(desk, "FILL_SURFACE.json", {"n_fills": 30, "mean_slip_modelled": 0.0001,
                                       "mean_slip_measured": 0.0003})
    assert attr._cost_term()["value"] == pytest.approx(-0.0002)


def test_sizing_inside_the_band_charges_nothing_and_a_dead_book_is_unmeasured(desk: Path) -> None:
    now = datetime.now(UTC).isoformat()
    attr.FORECASTS.write_text(json.dumps({"t": now, "total_heat": 0.25,
                                          "expected_log_per_day": 0.001, "book": {}}), "utf-8")
    s = attr.build()["growth_decomposition"]["terms"]["sizing"]
    assert s["value"] == 0.0 and not s["under_floor"] and "inside the band" in s["reading"]
    attr.FORECASTS.write_text(json.dumps({"t": now, "total_heat": 0.0,
                                          "expected_log_per_day": 0.0, "book": {}}), "utf-8")
    s = attr.build()["growth_decomposition"]["terms"]["sizing"]
    assert s["value"] == attr.UNMEASURED and "no heat" in s["why"]
    attr.FORECASTS.write_text(json.dumps({"t": now, "total_heat": 0.35,
                                          "expected_log_per_day": 0.001, "book": {}}), "utf-8")
    s = attr.build()["growth_decomposition"]["terms"]["sizing"]
    assert s["value"] == 0.0 and s["above_ceiling"] and "ABOVE THE CEILING" in s["reading"]


# --------------------------------------------------------------------------- generators
def test_flow_sampler_only_makes_valid_trees_and_is_flat_without_history() -> None:
    rng = np.random.default_rng(0)
    flat = gen.FlowSampler()
    for _ in range(150):
        e = flat.sample(rng, 3, allow_drivers=False)
        assert ag.is_valid(e, allow_drivers=False) and ag.depth(e) <= 3 and not isinstance(e, str)
        assert not (ag.terminals_in(e) & set(ag.DRIVER_TERMINALS))
    assert flat.weight("delta", "close") == flat.weight("corr", "spread") == 1.0
    assert gen.transitions(["delta", "close", 24]) == {(gen.ROOT_NODE, "delta"),
                                                       ("delta", "close")}
    assert gen.transitions(["sub", "close", ["max", "high", 48]]) == {
        (gen.ROOT_NODE, "sub"), ("sub", "close"), ("sub", "max"), ("max", "high")}


def test_flow_sampler_moves_toward_rewarded_transitions() -> None:
    hist = [(["delta", "close", 24], 3.0), (["delta", "close", 48], 2.5),
            (["corr", "spread", "spread", 5], -9.0), (["zscore", "range", 24], -9.0),
            (["mean", "atr", 12], float("nan"))]                        # non-finite: skipped
    fl = gen.FlowSampler(hist)
    assert fl.n_history == 4
    assert fl.weight("delta", "close") > 1.0 > fl.weight("corr", "spread")
    assert fl.weight("mean", "atr") == 1.0                              # unseen: at the prior
    assert fl.mean_fitness("delta", "close") < 3.0                      # smoothed toward the mean
    rng = np.random.default_rng(1)
    hot = np.mean([("delta", "close") in gen.transitions(fl.sample(rng, 3))
                   for _ in range(300)])
    cold = np.mean([("delta", "close") in gen.transitions(gen.FlowSampler().sample(rng, 3))
                    for _ in range(300)])
    assert hot > 0.1 > cold
    assert fl.table(2)[0]["weight"] >= fl.table(2)[1]["weight"]


def test_flow_sampler_falls_back_to_random_expr_when_nothing_validates(
        monkeypatch: pytest.MonkeyPatch) -> None:
    calls = {"n": 0}

    def _never(e: object, allow_drivers: bool = True) -> bool:
        calls["n"] += 1
        return False
    monkeypatch.setattr(ag, "is_valid", _never)
    e = gen.FlowSampler().sample(np.random.default_rng(0), 3)
    assert isinstance(e, str) and e in ag.TERMINALS                    # random_expr's own floor
    assert calls["n"] >= gen.MAX_TRIES


def test_symbolic_regression_fits_the_train_slice_and_reports_the_holdout() -> None:
    rng = np.random.default_rng(3)
    df = _bars(2000, seed=5)
    frames = ag.terminal_frames(df, raw=df)
    target = ag.evaluate(["delta", "close", 5], frames)
    e = gen.symbolic_regression(rng, frames, target, iters=120, allow_drivers=False)
    assert ag.is_valid(e, allow_drivers=False)
    fit = gen.LAST_FIT
    assert fit["n_train"] == 1400 and fit["n_holdout"] == 600 and fit["iters"] == 120
    assert fit["train_mse"] is not None and fit["train_mse"] < 2.0     # 2.0 = no relation
    assert fit["holdout_mse"] is not None and "never used" in fit["rule"]


def test_symbolic_regression_degrades_to_random_when_the_target_is_unusable() -> None:
    rng = np.random.default_rng(0)
    df = _bars(300)
    frames = ag.terminal_frames(df, raw=df)
    e = gen.symbolic_regression(rng, frames, pd.Series(np.nan, index=df.index))
    assert ag.is_valid(e) and "random_expr" in gen.LAST_FIT["why"]
    assert ag.is_valid(gen.symbolic_regression(rng, {}, pd.Series(dtype=float)))


def test_generator_surface_and_weight_table(tmp_path: Path) -> None:
    assert list(gen.GENERATORS) == ["random", "gflow", "symreg"]
    rng = np.random.default_rng(0)
    df = _bars(600)
    frames = ag.terminal_frames(df, raw=df)
    hist = [(["delta", "close", 24], 1.0)]
    for name, g in gen.GENERATORS.items():
        e = g(rng, frames, frames["ret"], hist, False, 3)
        assert ag.is_valid(e, allow_drivers=False), name
    assert {gen.choose_generator(rng, {"symreg": 1.0}) for _ in range(20)} == {"symreg"}
    assert {gen.choose_generator(rng, None) for _ in range(200)} == set(gen.GENERATORS)
    assert {gen.choose_generator(rng, {"zzz": 1.0}) for _ in range(200)} == set(gen.GENERATORS)
    assert {gen.choose_generator(rng, {"random": 0.0, "gflow": 0.0}) for _ in range(200)} \
        == set(gen.GENERATORS)
    p = tmp_path / "generator_weights.json"
    assert gen.load_weights(p) == (None, "generator_weights.json absent: uniform")
    p.write_text(json.dumps({"weights": {"random": 0.2, "gflow": 0.5, "symreg": 0.3, "x": 9}}))
    w, basis = gen.load_weights(p)
    assert w == {"random": 0.2, "gflow": 0.5, "symreg": 0.3} and "generator_weights" in basis
    p.write_text(json.dumps({"symreg": 2}))
    assert gen.load_weights(p)[0] == {"symreg": 2.0}
    p.write_text("{not json")
    assert gen.load_weights(p)[0] is None and "unreadable" in gen.load_weights(p)[1]
    p.write_text(json.dumps({"weights": {"nobody": 1}}))
    assert gen.load_weights(p)[0] is None


# --------------------------------------------------------------------------- the evolution hook
def _evo_bars(n: int = 3000, seed: int = 7) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    idx = pd.date_range("2025-01-06", periods=n, freq="h", tz="UTC")
    close = 100.0 + np.cumsum(rng.normal(scale=0.1, size=n))
    df = pd.DataFrame({"open": np.r_[close[0], close[:-1]],
                       "high": close + rng.uniform(0.02, 0.15, n),
                       "low": close - rng.uniform(0.02, 0.15, n), "close": close,
                       "tick_volume": rng.integers(50, 500, n).astype(float),
                       "spread": rng.integers(10, 20, n).astype(float)}, index=idx)
    df.index.name = "time"
    return df


def test_every_individual_records_its_generator(tmp_path: Path,
                                                monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(alpha_evolution, "GENERATOR_WEIGHTS", tmp_path / "absent.json")
    # pop must exceed ELITE for any child to be bred: the elite fills the next generation first.
    ev = alpha_evolution.evolve("SYN", _evo_bars(), cost=0.0002, drivers={}, survivors=None,
                                seed=1, budget_s=120.0, pop=alpha_evolution.ELITE + 4, gens=2)
    rows = list(ev.rows.values())
    allowed = set(gen.GENERATORS) | {"mutate", "crossover"}
    assert len(rows) >= 12 and all(r["generator"] in allowed for r in rows)
    assert {r["generator"] for r in rows} & {"mutate", "crossover"}
    assert ev.generator_weights["weights"] is None and "uniform" in ev.generator_weights["basis"]
    assert ev.generator_failures == []
    y = alpha_evolution.generator_yield(rows)
    assert sum(v["tried"] for v in y.values()) == len(rows)
    assert all({"tried", "full", "proposed", "best_fitness"} <= set(v) for v in y.values())


def test_the_weight_file_steers_fresh_individuals(tmp_path: Path,
                                                  monkeypatch: pytest.MonkeyPatch) -> None:
    w = tmp_path / "generator_weights.json"
    w.write_text(json.dumps({"weights": {"symreg": 1.0}}))
    monkeypatch.setattr(alpha_evolution, "GENERATOR_WEIGHTS", w)
    ev = alpha_evolution.evolve("SYN", _evo_bars(seed=3), cost=0.0002, drivers={},
                                survivors=None, seed=2, budget_s=120.0,
                                pop=alpha_evolution.ELITE + 2, gens=2)
    made = {r["generator"] for r in ev.rows.values()}
    assert "symreg" in made and not made & {"random", "gflow"}
    assert ev.generator_weights["weights"] == {"symreg": 1.0}


def test_a_broken_generator_costs_one_individual_not_the_sweep(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    w = tmp_path / "generator_weights.json"
    w.write_text(json.dumps({"gflow": 1.0}))
    monkeypatch.setattr(alpha_evolution, "GENERATOR_WEIGHTS", w)

    def _boom(*a: object, **k: object) -> object:
        raise RuntimeError("sampler down")
    monkeypatch.setitem(gen.GENERATORS, "gflow", _boom)
    ev = alpha_evolution.evolve("SYN", _evo_bars(seed=4), cost=0.0002, drivers={},
                                survivors=None, seed=3, budget_s=120.0, pop=6, gens=1)
    assert len(ev.rows) >= 6
    assert ev.generator_failures and all("sampler down" in f for f in ev.generator_failures)
    assert {r["generator"] for r in ev.rows.values()} <= {"random", "mutate", "crossover"}
