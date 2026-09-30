"""The institutional footprint: atlas rows, latent states with intervals, dealer scenarios, the
coverage grid and the one-door cells -- tested on the properties that make them honest.
"""
from __future__ import annotations

import importlib
import json
import sys
from pathlib import Path
from typing import Any

import pytest

DESK = Path(__file__).resolve().parents[1]
ROOT = DESK.parent.parent
for _p in (str(DESK), str(DESK / "research"), str(ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

np = pytest.importorskip("numpy")
pd = pytest.importorskip("pandas")
pytest.importorskip("yaml")

from research.countries.institutional import ontology as onto  # noqa: E402

from research import institutional_footprint as ifp  # noqa: E402


@pytest.fixture()
def lake(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setattr(ifp, "SERIES", tmp_path / "series")
    monkeypatch.setattr(ifp, "STATE_DIR", tmp_path / "state")
    monkeypatch.setattr(ifp, "EMITTED", tmp_path / "state" / "cells_emitted.json")
    monkeypatch.setattr(ifp, "FETCH_STATE", tmp_path / "state" / "fetch_state.json")
    monkeypatch.setattr(ifp, "WATCH_STATE", tmp_path / "state" / "watch_state.json")
    monkeypatch.setattr(ifp, "CULTURE_LOG", tmp_path / "state" / "cell_culture.jsonl")
    monkeypatch.setattr(ifp, "RULINGS", tmp_path / "rulings.json")
    return tmp_path


# ------------------------------------------------------------------ the atlas
def test_atlas_rows_are_canonical_and_lawful() -> None:
    rows = ifp.load_roster()
    assert len(rows) >= 150
    ids = [r["id"] for r in rows]
    assert len(ids) == len(set(ids)), "a canonical id is defined twice"
    universe = set(json.loads((DESK / "data" / "universe" / "universe.json").read_text("utf-8")))
    for r in rows:
        parts = r["id"].split(".")
        assert parts[0] == "institutional" and len(parts) == 4, r["id"]
        assert parts[1] == r["jurisdiction"] and r["jurisdiction"] in onto.JURISDICTION_CODES
        assert r["source_class"] in onto.CLASS_IDS, r["id"]
        assert r["fetcher"] == "owned" and r["owner"] == "institutional_footprint"
        assert set(r["targets"]) <= universe, r["id"]
        for f in ("source_culture", "participant_structure", "failure_mode_hypothesis",
                  "crowding_prior"):
            assert r.get(f), (r["id"], f)
        # No crypto venue is ever a source (mandate 2026-08-18); a public chain is a sensor.
        assert not any(v in str(r.get("url", "")).lower()
                       for v in ("binance", "bybit", "okx", "hyperliquid", "coinbase.com"))


def test_every_state_names_known_actors_and_tradable_assets() -> None:
    universe = set(json.loads((DESK / "data" / "universe" / "universe.json").read_text("utf-8")))
    for st in onto.LATENT_STATES:
        assert st["actor"] in onto.ACTORS
        assert set(st["assets"]) <= universe, st["id"]
        assert st["evidence"] and all(sign in (1, -1) and w > 0 for _k, sign, w in st["evidence"])


def test_seven_statuses_and_unsearched_is_not_one_of_them() -> None:
    assert len(onto.COVERAGE_STATUSES) == 7
    assert onto.UNSEARCHED not in onto.COVERAGE_STATUSES
    assert set(onto.COVERAGE_STATUSES) >= onto.CLOSED_STATUSES


# ------------------------------------------------------------------ states
def test_unmeasured_inputs_widen_the_interval_and_min_inputs_refuses() -> None:
    st = {"id": "x", "evidence": (("a.z", 1, 1.0), ("b.z", 1, 1.0), ("c.z", 1, 1.0)),
          "min_inputs": 1}
    full = ifp.fuse(st, {"a.z": 2.0, "b.z": 2.0, "c.z": 2.0})
    one = ifp.fuse(st, {"a.z": 2.0})
    assert full["lo"] < full["p"] < full["hi"] and full["coverage"] == 1.0
    assert (one["hi"] - one["lo"]) > (full["hi"] - full["lo"])
    assert one["coverage"] == pytest.approx(1 / 3, abs=1e-3)
    refused = ifp.fuse({**st, "min_inputs": 2}, {"a.z": 2.0})
    assert refused["p"] is None and refused["reason"].startswith("UNMEASURED")


def test_a_stopped_feed_goes_dark_not_flat() -> None:
    weekly = pd.Series(np.arange(10.0), index=pd.date_range("2026-01-02", periods=10,
                                                            freq="7D", tz="UTC"))
    idx = pd.date_range("2026-01-02", periods=120, freq="1D", tz="UTC")
    out = ifp.carry_forward(weekly, idx)
    last = weekly.index[-1]
    assert out[idx <= last + pd.Timedelta(days=17)].notna().iloc[-1]
    assert out[idx > last + pd.Timedelta(days=18)].isna().all()


def _bars(returns: np.ndarray) -> pd.DataFrame:
    idx = pd.date_range("2026-01-01", periods=len(returns), freq="1h", tz="UTC")
    return pd.DataFrame({"close": 100.0 * np.exp(np.cumsum(returns))}, index=idx)


def test_dealer_gamma_is_a_scenario_posterior_that_reads_behaviour() -> None:
    rng = np.random.default_rng(7)
    e = rng.normal(0, 1e-3, 24 * 60)
    revert = np.empty_like(e)
    trend = np.empty_like(e)
    revert[0] = trend[0] = e[0]
    for i in range(1, len(e)):
        revert[i] = -0.4 * revert[i - 1] + e[i]
        trend[i] = 0.4 * trend[i - 1] + e[i]
    lg = ifp.dealer_gamma_posterior(_bars(revert)).iloc[-1]
    sg = ifp.dealer_gamma_posterior(_bars(trend)).iloc[-1]
    for row in (lg, sg):
        total = row[["p_dealer_long_gamma", "p_dealer_neutral", "p_dealer_short_gamma"]].sum()
        assert total == pytest.approx(1.0)
    assert lg["p_dealer_long_gamma"] > 0.9 and sg["p_dealer_short_gamma"] > 0.9


def test_cot_is_available_on_friday_not_tuesday(tmp_path: Path) -> None:
    d = tmp_path / "cot_tff"
    d.mkdir()
    dates = pd.date_range("2025-01-07", periods=60, freq="7D", tz="UTC")     # Tuesdays
    pd.DataFrame({"report_date": dates, "market": "EURO FX - CME", "oi": 1000.0,
                  "dealer_l": 100.0, "dealer_s": 300.0, "am_l": 400.0, "am_s": 200.0,
                  "lm_l": np.linspace(100, 400, 60), "lm_s": 150.0}).to_parquet(d / "eur.parquet")
    f = ifp.cot_features(tmp_path)["EURUSD"]
    assert (f.index.dayofweek == 4).all()                    # Friday
    assert f["cot.lev_net_pct"].dropna().iloc[-1] == pytest.approx(1.0)


# ------------------------------------------------------------------ recipes
def test_recipes_parse_their_documented_shapes() -> None:
    fred = {"fetch": {"series": {"custody_total": "WMTSECL1"}}}
    body = b"observation_date,WMTSECL1\n2026-09-02,2800000\n2026-09-09,2810000\n"
    df, why = ifp._fred_csv(fred, lambda url: (200, body, ""))
    assert not why and list(df.columns) == ["event_time", "custody_total"] and len(df) == 2
    ny = {"fetch": {"url": "https://x/{start}/{end}", "path": ["repo", "operations"],
                    "date": "operationDate", "value": "totalAmtAccepted", "group": "operationType"}}
    doc = {"repo": {"operations": [
        {"operationDate": "2026-09-01", "totalAmtAccepted": 5, "operationType": "Repo"},
        {"operationDate": "2026-09-01", "totalAmtAccepted": 7, "operationType": "Reverse Repo"}]}}
    df, why = ifp._nyfed_json(ny, lambda url: (200, json.dumps(doc).encode(), ""))
    assert not why and {"repo", "reverse_repo"} <= set(df.columns)
    fd = {"fetch": {"url": "u", "date": "auction_date",
                    "fields": ["indirect_bidder_accepted", "total_accepted"]}}
    doc = {"data": [{"auction_date": "2026-09-10", "indirect_bidder_accepted": "60",
                     "total_accepted": "100"}]}
    df, why = ifp._fiscaldata(fd, lambda url: (200, json.dumps(doc).encode(), ""))
    assert df["indirect_share"].iloc[0] == pytest.approx(0.6)
    df, why = ifp._fred_csv(fred, lambda url: (503, b"", "busy"))
    assert df is None and "503" in why


def test_a_frame_is_never_available_before_its_publication_lag(lake: Path) -> None:
    df = pd.DataFrame({"event_time": pd.date_range("2026-01-01", periods=3, freq="D", tz="UTC"),
                       "v": [1.0, 2.0, 3.0]})
    ifp.write_frame("institutional.us.x.y", df, lag_hours=ifp.lag_hours_of(
        {"publication_lag_days": 3}))
    got = ifp.read_frame("institutional.us.x.y")
    assert ((got["available_time"] - got["event_time"]) == pd.Timedelta(hours=96)).all()


# ------------------------------------------------------------------ cells and coverage
def test_cells_go_through_the_one_door_once(lake: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[dict[str, Any]] = []

    def fake_enqueue(**kw: Any) -> tuple[str, bool]:
        calls.append(kw)
        return f"cand{len(calls)}", True
    import libs.moat.registry as reg
    monkeypatch.setattr(reg, "enqueue_candidate", fake_enqueue)
    plans = [{"source": "institutional_state.XAUUSD", "signal": "p_physical_tightness",
              "symbol": "XAUUSD", "source_id": "institutional.us.cme.comex_warehouse_stocks",
              "source_ids": ["institutional.us.cme.comex_warehouse_stocks"], "kind": "state",
              "culture": {"source_culture": "US/en", "participant_structure": "physical_flow",
                          "failure_mode_hypothesis": "x.", "crowding_prior": "medium"}}]
    first = ifp.emit_cells(plans, deadline=1e18)
    n = len(ifp.TRANSFORMS) * len(ifp.SIDES) * len(ifp.CHARTS)
    assert first["cells_created"] == n and len(calls) == n
    assert all(c["family"] == "exogenous_conditioner" and c["source_id"] for c in calls)
    assert all(c["source_culture"] == "US/en" for c in calls)
    second = ifp.emit_cells(plans, deadline=1e18)
    assert second["cells_attempted"] == 0 and len(calls) == n       # charged once, never again
    assert "institutional.us.cme.comex_warehouse_stocks" in second["sources_credited"]


def test_every_cell_of_the_grid_has_exactly_one_status(lake: Path) -> None:
    rows = ifp.load_roster()
    cov = ifp.coverage(rows, rulings={})
    allowed = set(onto.COVERAGE_STATUSES) | {onto.UNSEARCHED}
    for j, cells in cov["grid"].items():
        assert set(cells) == set(onto.CLASS_IDS), j
        assert all(c["status"] in allowed for c in cells.values())
    assert set(onto.JURISDICTION_CODES) <= set(cov["grid"])
    assert "ACTIVE" not in cov["status_counts"]        # nothing fetched, nothing credited
    assert cov["search_queue"], "an UNSEARCHED cell a peer covers must be asked for"


def test_active_is_measured_not_declared(lake: Path) -> None:
    row = {"id": "institutional.us.fed.rrp_overnight", "jurisdiction": "us",
           "source_class": "central_bank_operations", "declared_status": "ACTIVE_CANDIDATE"}
    assert ifp.row_status(row, {}, {}, set()) == "DISCOVERED_NOT_INGESTED"
    ifp.write_frame(row["id"], pd.DataFrame({"event_time": ["2026-09-01"], "v": [1.0]}),
                    lag_hours=24)
    assert ifp.row_status(row, {}, {}, set()) == "DISCOVERED_NOT_INGESTED"
    assert ifp.row_status(row, {}, {}, {row["id"]}) == "ACTIVE"


def test_the_watcher_opens_a_future_source_when_it_publishes(lake: Path) -> None:
    rows = [{"id": "institutional.us.finra.slate_securities_lending", "declared_status": "WATCH",
             "fetch": {"kind": "watch", "probe": "https://p", "markers": ["SLATE data is now"]}}]
    st = ifp.watch(rows, lambda url: (200, b"nothing yet", ""), deadline=1e18)
    assert st[rows[0]["id"]]["status"] == "WATCH"
    st = ifp.watch(rows, lambda url: (200, b"... SLATE data is now available ...", ""),
                   deadline=1e18)
    assert st[rows[0]["id"]]["status"] == "DISCOVERED_NOT_INGESTED"


# ------------------------------------------------------------------ the packs
def test_every_country_pack_carries_the_common_schema() -> None:
    packs = sorted(p.parent.name for p in (DESK / "research" / "countries").glob("*/pack.py"))
    assert len(packs) >= 70
    for code in packs:
        mod = importlib.import_module(f"research.countries.{code}.pack")
        fp = mod.INSTITUTIONAL_FOOTPRINT
        assert fp["schema"] == "institutional_footprint/1", code
        assert set(fp["classes"]) == set(onto.CLASS_IDS), code
        assert set(fp["roles"]) == set(onto.JURISDICTION_ROLES), code
    us = importlib.import_module("research.countries.us.pack").INSTITUTIONAL_FOOTPRINT
    assert "institutional.us.cftc.cot_tff" in us["sources"]


def test_regimes_react_to_crossings_not_drift() -> None:
    ages = {"US500": {"short_crowding": {"p": 0.8, "lo": 0.6, "hi": 0.9},
                      "repo_funding_stress": {"p": 0.75, "lo": 0.2, "hi": 0.95},
                      "dealer_long_gamma": {"p": 0.2}, "dealer_neutral": {"p": 0.3},
                      "dealer_short_gamma": {"p": 0.5}}}
    r = ifp.regimes(ages)["US500"]
    assert r["short_crowding"] == "HIGH"
    assert r["repo_funding_stress"] == "NEUTRAL"          # the interval straddles one half
    assert r["dealer_gamma"] == "dealer_short_gamma"
