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
        # The atlas name, or -- when another lane registered the dataset first -- that lane's
        # id with the atlas name kept as `atlas_id` (one canonical id per dataset).
        parts = str(r.get("atlas_id") or r["id"]).split(".")
        assert parts[0] == "institutional" and len(parts) == 4, r["id"]
        assert parts[1] == r["jurisdiction"] and r["jurisdiction"] in onto.JURISDICTION_CODES
        assert r["id"].startswith("institutional.") or r.get("atlas_id"), r["id"]
        # A bare host would shift the registry's attribution for every row on that host.
        assert "/" in str(r["url"]).split("://", 1)[-1].rstrip("/"), r["id"]
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
    idx = pd.DatetimeIndex(f.index)
    # Never before the Friday 21:00 UTC release of its own week; later only for holiday weeks
    # and the 2025 shutdown backlog. And monotone: no later read leaks an earlier backlog row.
    first = pd.DatetimeIndex(dates[: len(idx[:5])]) + pd.Timedelta(days=3, hours=21)
    assert (idx[:5] >= first).all()
    # A backlog lands at one instant and keeps only its latest week: never more stamps than weeks.
    assert len(idx) <= len(dates) and idx.is_unique and idx.is_monotonic_increasing
    assert (idx[:5].dayofweek.isin([4, 0])).all()
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
    learned = {"side": -1, "train_end": "2024-01-01T00:00:00+00:00", "train_events": 40,
               "train_edge": -0.001}
    first = ifp.emit_cells(plans, deadline=1e18, side_fn=lambda *a, **k: learned)
    n = len(ifp.TRANSFORMS_STATE) * len(ifp.CHARTS)
    assert first["cells_created"] == n and len(calls) == n
    assert all(c["family"] == "exogenous_conditioner" and c["source_id"] for c in calls)
    assert all(c["source_culture"] == "US/en" for c in calls)
    # ONE side per cell, the learned one; never the mirror pair.
    assert {c["params"]["side_when_high"] for c in calls} == {-1}
    assert len({(c["params"]["transform"], c["chart"]) for c in calls}) == n
    # The delta threshold is in probability units: a state can actually cross it.
    deltas = [c["params"]["threshold"] for c in calls if c["params"]["transform"] == "delta"]
    assert deltas and all(0 < t < 1 for t in deltas)
    second = ifp.emit_cells(plans, deadline=1e18, side_fn=lambda *a, **k: learned)
    assert second["cells_attempted"] == 0 and len(calls) == n       # charged once, never again
    assert "institutional.us.cme.comex_warehouse_stocks" in second["sources_credited"]


def test_a_cell_whose_side_cannot_be_learned_is_not_minted(lake: Path) -> None:
    plans = [{"source": "s", "signal": "p_x", "symbol": "XAUUSD", "source_id": "a",
              "source_ids": ["a"], "inputs": [], "kind": "state", "culture": {}}]
    out = ifp.emit_cells(plans, deadline=1e18, side_fn=lambda *a, **k: None)
    assert out["cells_attempted"] == 0 and out["side_not_learned"] == len(ifp.TRANSFORMS_STATE)
    assert "a" not in out["sources_credited"]


def test_the_side_is_learned_on_the_training_span_only() -> None:
    idx = pd.date_range("2024-01-01", periods=4000, freq="h", tz="UTC")
    rng = np.random.default_rng(3)
    m = pd.Series(np.where(np.arange(4000) % 50 < 25, 2.0, -2.0), index=idx)
    # Training half: high conditioner -> price rises. Second half: the relation flips, and the
    # choice must not see it.
    drift = np.where(np.arange(4000) < 2000, 1.0, -1.0) * np.sign(m.to_numpy()) * 1e-3
    close = pd.Series(100 * np.exp(np.cumsum(drift + rng.normal(0, 1e-5, 4000))), index=idx)
    got = ifp.learn_side("s", "c", "level_z", 1.0, "XAUUSD",
                         bars=pd.DataFrame({"close": close}), cond=m)
    assert got is not None and got["side"] == 1
    assert pd.Timestamp(got["train_end"]) < idx[2100]
    few = ifp.learn_side("s", "c", "level_z", 5.0, "XAUUSD",
                         bars=pd.DataFrame({"close": close}), cond=m)
    assert few is None                                   # no event beyond the threshold


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


def test_active_is_measured_not_declared_and_decays(lake: Path) -> None:
    import os
    row = {"id": "institutional.us.fed.rrp_overnight", "jurisdiction": "us",
           "source_class": "central_bank_operations", "declared_status": "ACTIVE_CANDIDATE"}
    now = ifp.now_utc()
    fed = {row["id"]: now.isoformat()}
    assert ifp.row_status(row, {}, {}, {}) == "DISCOVERED_NOT_INGESTED"
    ifp.write_frame(row["id"], pd.DataFrame({"event_time": ["2026-09-01"], "v": [1.0]}),
                    lag_hours=24)
    assert ifp.row_status(row, {}, {}, {}) == "DISCOVERED_NOT_INGESTED"
    assert ifp.row_status(row, {}, {}, fed) == "ACTIVE"
    # Not fed for 31 days: no longer ACTIVE.
    old = {row["id"]: (now - ifp.timedelta(days=31)).isoformat()}
    assert ifp.row_status(row, {}, {}, old) == "DISCOVERED_NOT_INGESTED"
    # Fed, but the frame has not been refreshed for 31 days: no longer ACTIVE either.
    t = (now - ifp.timedelta(days=31)).timestamp()
    os.utime(ifp.series_path(row["id"]), (t, t))
    assert ifp.row_status(row, {}, {}, fed) == "DISCOVERED_NOT_INGESTED"


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
    assert "pack_us_us_cftc_cot" in us["sources"]


def test_a_stale_state_is_unmeasured_everywhere_it_is_published() -> None:
    idx = pd.DatetimeIndex([ifp.now_utc() - ifp.timedelta(days=200),
                            ifp.now_utc() - ifp.timedelta(days=1)])
    f = pd.DataFrame({"p_short_crowding": [0.9, np.nan], "p_short_crowding_lo": [0.8, np.nan],
                      "p_short_crowding_hi": [0.95, np.nan],
                      "p_repo_funding_stress": [0.1, 0.9],
                      "p_repo_funding_stress_lo": [0.05, 0.7],
                      "p_repo_funding_stress_hi": [0.2, 0.95]}, index=idx)
    ages = ifp.state_ages({"US500": f})["US500"]
    assert ages["short_crowding"]["status"] == "UNMEASURED" and ages["short_crowding"]["p"] is None
    assert ages["repo_funding_stress"]["status"] == "MEASURED"
    r = ifp.regimes({"US500": ages})["US500"]
    assert r["short_crowding"] == "UNMEASURED" and r["repo_funding_stress"] == "HIGH"


def test_a_calendar_alone_never_measures_a_state() -> None:
    st = next(s for s in onto.LATENT_STATES if s["id"] == "passive_forced_flow")
    got = ifp.fuse(st, {"calendar.index_event": 1.0, "calendar.month_end": 1.0})
    assert got["p"] is None and got["reason"].startswith("UNMEASURED")
    assert ifp.fuse(st, {"calendar.index_event": 1.0, "ici.etf_issuance_z": 1.0})["p"] is not None


# ------------------------------------------------------------------ point in time
def test_cot_follows_the_cftc_calendar() -> None:
    rd = pd.Series(pd.to_datetime(["2024-06-25", "2024-07-02", "2025-10-07", "2026-02-03"],
                                  utc=True))
    rel = ifp.cot_release_times(rd)
    assert rel.iloc[0] == pd.Timestamp("2024-06-28 21:00", tz="UTC")     # Friday, after 15:30 ET
    assert rel.iloc[1] == pd.Timestamp("2024-07-08 21:00", tz="UTC")     # July 4 week: Monday
    assert rel.iloc[2] >= pd.Timestamp("2026-01-31", tz="UTC")          # 2025 shutdown backlog
    assert rel.iloc[3] == pd.Timestamp("2026-02-06 21:00", tz="UTC")
    # Winter release is 20:30 UTC: the stamp is never before it.
    assert (rel.dt.hour >= 21).all() or rel.iloc[2].hour == 0
    assert ifp.cot_release_times(rd, {"exact": {"2025-10-07": "2025-11-19T20:30:00Z"}}).iloc[2] \
        == pd.Timestamp("2025-11-19 20:30", tz="UTC")


def test_ftd_rows_are_stamped_at_the_file_posting() -> None:
    assert ifp.ftd_available("2026-03-01", "a") == pd.Timestamp("2026-04-05", tz="UTC")
    assert ifp.ftd_available("2026-03-01", "b") == pd.Timestamp("2026-04-21", tz="UTC")


def test_a_revised_series_never_reaches_a_state_or_a_cell(lake: Path,
                                                          monkeypatch: pytest.MonkeyPatch) -> None:
    row = {"id": "institutional.us.fed.h8_bank_balance_sheet", "targets": ["US500"],
           "pit_grade": "LATEST_REVISED",
           "fetch": {"kind": "fred_csv", "series": {"bank_securities": "X"}}}
    csv = "DATE,X\n" + "\n".join(f"2020-01-{d:02d},{d}" for d in range(1, 29)) + "\n"
    monkeypatch.delenv("FRED_API_KEY", raising=False)
    df, _ = ifp._fred_csv(row, lambda url: (200, csv.encode(), ""))
    assert df.attrs["pit_grade"] == ifp.LATEST_REVISED
    big = pd.DataFrame({"event_time": pd.date_range("2020-01-01", periods=80, freq="7D",
                                                    tz="UTC"),
                        "bank_securities": np.arange(80.0)})
    ifp.write_frame(row["id"], big, lag_hours=262, pit_grade=ifp.LATEST_REVISED)
    monkeypatch.setattr(ifp, "_may_hunt", lambda s: True)
    assert ifp.planned_cells({}, [row]) == []
    assert "h8.securities_chg_z" not in ifp.macro_features([row])
    ifp.write_frame(row["id"], big, lag_hours=262, pit_grade=ifp.FIRST_RELEASE)
    assert ifp.planned_cells({}, [row])


def test_alfred_keeps_the_first_vintage_at_its_release_day(monkeypatch: pytest.MonkeyPatch) -> None:
    row = {"id": "x", "fetch": {"kind": "fred_csv", "series": {"v": "S"}, "revisable": True}}
    doc = {"observations": [
        {"date": "2020-01-01", "value": "1.0", "realtime_start": "2020-01-10"},
        {"date": "2020-01-01", "value": "9.0", "realtime_start": "2021-01-10"},
        {"date": "2020-01-08", "value": ".", "realtime_start": "2020-01-17"}]}
    monkeypatch.setenv("FRED_API_KEY", "k-not-a-real-key")
    seen: list[str] = []

    def get(url: str) -> tuple[int, bytes, str]:
        seen.append(url)
        return 200, json.dumps(doc).encode(), ""
    df, why = ifp._fred_csv(row, get)
    assert df.attrs["pit_grade"] == ifp.FIRST_RELEASE and why == ""
    assert df["v"].tolist() == [1.0]                        # the first release, not the revision
    assert pd.Timestamp(df["available_time"].iloc[0]) > pd.Timestamp("2020-01-10", tz="UTC")
    _, why = ifp._fred_csv(row, lambda url: (500, b"", f"boom {url}"))
    assert "k-not-a-real-key" not in why                    # a key never reaches a log


def test_a_series_mints_only_with_sixty_vintages(lake: Path,
                                                 monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(ifp, "_may_hunt", lambda s: True)
    row = {"id": "institutional.us.x.y", "targets": ["US500"], "pit_grade": "FIRST_RELEASE"}
    for n, want in ((ifp.MIN_VINTAGES - 1, False), (ifp.MIN_VINTAGES, True)):
        df = pd.DataFrame({"event_time": pd.date_range("2020-01-01", periods=n, freq="D",
                                                       tz="UTC"), "v": np.arange(float(n))})
        ifp.write_frame(row["id"], df, lag_hours=24)
        assert bool(ifp.planned_cells({}, [row])) is want


def test_a_state_cell_is_credited_to_the_sources_it_is_built_from() -> None:
    st = {"id": "s", "evidence": (("cot.lev_net_pct", 1, 0.5), ("nyfed.rrp_chg_z", 1, 1.0),
                                  ("calendar.month_end", 1, 2.0), ("ofr.hf_leverage_z", 1, 0.8))}
    n = ifp.MIN_VINTAGES
    panel = pd.DataFrame({"cot.lev_net_pct": np.ones(n), "nyfed.rrp_chg_z": np.ones(n),
                          "calendar.month_end": np.ones(n),
                          "ofr.hf_leverage_z": [1.0] * 5 + [np.nan] * (n - 5)})
    src = {"cot.lev_net_pct": ifp.COT_SOURCE_ID, "nyfed.rrp_chg_z": "institutional.us.nyfed.r",
           "calendar.month_end": "calendar", "ofr.hf_leverage_z": "institutional.us.ofr.h"}
    att = ifp.state_attribution(st, panel, src)
    assert att["source_id"] == "institutional.us.nyfed.r"       # heaviest measured atlas input
    assert att["source_ids"] == sorted([ifp.COT_SOURCE_ID, "institutional.us.nyfed.r"])


def test_every_feature_source_is_in_the_atlas_and_jurisdictions_are_unique() -> None:
    ids = {r["id"] for r in ifp.load_roster()}
    assert {sid for sid, *_ in ifp.MACRO_FEATURES} <= ids
    assert ifp.COT_SOURCE_ID in ids
    js = onto.coverage_jurisdictions()
    assert len(js) == len(set(js))


def test_regimes_react_to_crossings_not_drift() -> None:
    ages = {"US500": {"short_crowding": {"p": 0.8, "lo": 0.6, "hi": 0.9},
                      "repo_funding_stress": {"p": 0.75, "lo": 0.2, "hi": 0.95},
                      "dealer_long_gamma": {"p": 0.2}, "dealer_neutral": {"p": 0.3},
                      "dealer_short_gamma": {"p": 0.5}}}
    r = ifp.regimes(ages)["US500"]
    assert r["short_crowding"] == "HIGH"
    assert r["repo_funding_stress"] == "NEUTRAL"          # the interval straddles one half
    assert r["dealer_gamma"] == "dealer_short_gamma"


def test_a_role_ruling_closes_the_role_gap(lake: Path) -> None:
    rows = ifp.load_roster()
    open_ = ifp.coverage(rows, rulings={})["role_gaps"]
    j, gaps = next((j, g) for j, g in open_.items() if g and j in onto.JURISDICTION_CODES)
    ruled = {"cells": {}, "roles": {f"{j}|{gaps[0]}": {"status": "NOT_PUBLISHED",
                                                       "reason": "none"}}}
    cov = ifp.coverage(rows, rulings=ruled)
    assert gaps[0] not in cov["role_gaps"][j]
    assert not any(q.get("jurisdiction") == j and q.get("role") == gaps[0]
                   for q in cov["search_queue"])


def test_an_atlas_url_is_verified_on_the_box_and_a_dead_one_is_re_asked(lake: Path) -> None:
    rows = [{"id": "institutional.xx.a.b", "url": "https://a/b"}]
    st = ifp.verify_urls(rows, lambda url: (404, b"", ""), deadline=1e18)
    assert st[rows[0]["id"]]["status"] == "RETRY"
    st = ifp.verify_urls(rows, lambda url: (404, b"", ""), deadline=1e18)
    assert st[rows[0]["id"]]["status"] == "BROKEN"
    st = ifp.verify_urls(rows, lambda url: (200, b"ok", ""), deadline=1e18)
    assert st[rows[0]["id"]]["status"] == "VERIFIED"
