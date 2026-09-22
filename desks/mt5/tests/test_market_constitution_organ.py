"""The market-constitution organ on a synthetic desk: tmp registry, placebo null, dry-run."""
from __future__ import annotations

import json
import sys
from datetime import date
from pathlib import Path

import numpy as np
import pytest

_DESK = Path(__file__).resolve().parents[1]
_ROOT = _DESK.parents[1]
for _p in (str(_ROOT), str(_DESK), str(_DESK / "research")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import market_constitution as org  # noqa: E402

from libs.moat import registry as R  # noqa: E402
from libs.research import country_lab as lab  # noqa: E402
from libs.research import market_constitution as mc  # noqa: E402

UNIVERSE = {"JPN225": {"asset_class": "Indices"}, "HK50": {"asset_class": "Indices"},
            "USDKRW": {"asset_class": "Forex Exotics"}, "USDJPY": {"asset_class": "Forex"},
            "CHINAH": {"asset_class": "Indices"}, "USDCNH": {"asset_class": "Forex Exotics"},
            "XAUUSD": {"asset_class": "Metals"}, "EURUSD": {"asset_class": "Forex"},
            "Apple": {"asset_class": "US Share CFDs"}}
SEEDS = {"JPN225": 1, "HK50": 2, "USDKRW": 3, "USDJPY": 4, "CHINAH": 5, "USDCNH": 6,
         "XAUUSD": 7, "EURUSD": 8}
TODAY = date(2026, 9, 22)
CHANGE = np.datetime64("2024-11-05")


def _tape(symbol: str) -> lab.Bars:
    """An hourly tape from 2023-01-02; JPN225 carries the closing-auction effect after
    2024-11-05 in its 06:00 UTC bar, every other symbol is pure noise."""
    rng = np.random.default_rng(SEEDS[symbol])
    t0 = np.datetime64("2023-01-02", "h")
    times = np.arange(t0, t0 + np.timedelta64(1100 * 24, "h"),
                      np.timedelta64(1, "h")).astype("datetime64[ns]")
    r = rng.normal(0, 1e-3, times.size)
    if symbol == "JPN225":
        hours = (times.astype("datetime64[h]") - times.astype("datetime64[D]")).astype(int)
        r[(times >= CHANGE) & (hours == 6)] *= 4.0
    return lab.Bars(symbol=symbol, timeframe="H1", times=times, close=np.exp(np.cumsum(r)) * 100)


@pytest.fixture
def desk(tmp_path, monkeypatch):
    d = tmp_path / "desk"
    (d / "data" / "universe").mkdir(parents=True)
    (d / "data" / "universe" / "universe.json").write_text(json.dumps(UNIVERSE), encoding="utf-8")
    monkeypatch.setattr(org, "_DESK", d)
    monkeypatch.setattr(org, "UNIVERSE", d / "data" / "universe" / "universe.json")
    monkeypatch.setattr(org, "RULE_STATES_DIR", d / "data" / "rule_states")
    monkeypatch.setattr(org, "INTEL_DIR", d / "data" / "intelligence" / "market_constitution")
    monkeypatch.setattr(org, "REPORT", d / "reports" / "MARKET_CONSTITUTION.json")
    monkeypatch.setattr(org, "CONSTRAINTS", d / "data" / "market_constraints.json")
    monkeypatch.setattr(org, "load_bars",
                        lambda s, timeframe="H1": _tape(s) if s in SEEDS else None)
    monkeypatch.setattr(org, "pack_venues", lambda: ([], ["packs stubbed"]))
    monkeypatch.setattr(org, "_holiday_sets", lambda years: ({}, ["holidays stubbed"]))
    monkeypatch.setattr(org, "_may_hypothesise", lambda: org._fallback_may_hypothesise)
    monkeypatch.setattr(org, "MAX_STAMP_BARS", 3000)
    monkeypatch.setattr(R, "BACKUP", tmp_path / "no_backup")
    R.set_path(tmp_path / "alpha_registry.sqlite")
    yield d
    R.set_path(None)


def test_dry_run_writes_nothing(desk, capsys):
    assert org.main(["--once", "--budget-s", "30", "--dry-run"]) == 0
    assert not (desk / "reports").exists() and not (desk / "data" / "rule_states").exists()
    assert not (desk / "data" / "intelligence").exists()
    assert not (desk / "data" / "market_constraints.json").exists()
    assert R.discoveries() == [] and R.memories(category=org.SOURCE) == []
    out = capsys.readouterr().out
    assert "dry run" in out and "tse_closing_auction_2024" in out


def test_live_pass_measures_registers_donates_and_stamps(desk):
    rep = org.run_once(60, dry_run=False, today=TODAY)
    by = {s["change_id"]: s for s in rep["studies"]}
    tse = by["tse_closing_auction_2024"]
    assert tse["verdict"] == "MEASURED"
    r0 = tse["results"][0]
    assert r0["symbol"] == "JPN225" and r0["control"] == "HK50"
    assert r0["did"] > 0 and r0["p_placebo"] <= 0.05 and r0["n_placebo"] >= mc.MIN_PLACEBOS
    assert by["tse_random_close_2027"]["verdict"] == "PROSPECTIVE"
    assert by["krx_vi_activations"]["verdict"] == "UNMEASURED"
    curbs = by["cffex_curbs_2015"]
    assert curbs["verdict"] == "UNMEASURED"
    assert "outside the tape" in curbs["results"][0]["why"]
    assert any(u["change_id"] == "cffex_curbs_2015" for u in rep["unmeasured"])
    # the registry: measured results are discoveries, the 2027 change is a preregistration
    assert rep["registry"]["discoveries_created"] >= 1
    discs = R.discoveries(origin="DESK")
    assert any(d["source_type"] == "rule_state_effect" for d in discs)
    keys = [m.get("memory_key") or "" for m in R.memories(category=org.SOURCE)]
    assert any("tse_random_close_2027" in k for k in keys)
    assert rep["registry"]["preregistered"]
    # the donation, in the compiler's own shape
    assert rep["donations"]["n"] >= 1 and rep["donations"]["path"]
    files = list((desk / "data" / "intelligence" / "market_constitution").glob("discoveries_*"))
    assert len(files) == 1
    rows = json.loads(files[0].read_text("utf-8"))["discoveries"]
    assert all(r["kind"] == "hypothesis" and r["symbols"] and r["rule_state"] for r in rows)
    assert all(r["family"] in ("session_range_breakout", "overnight_gap_decay") for r in rows)
    assert any(r["symbols"] == ["JPN225"] for r in rows)
    assert all("asian session" in r["claim"] for r in rows)
    # the stamps and the report
    assert (desk / "reports" / "MARKET_CONSTITUTION.json").exists()
    stamped = {s["venue"] for s in rep["stamps"] if s["verdict"] == "STAMPED"}
    assert {"TSE", "KRX", "SSE_SZSE", "FUSION"} <= stamped
    states = desk / "data" / "rule_states"
    assert (states / "tse.parquet").exists() or (states / "tse.json").exists()
    assert rep["reading_list"] and rep["venues"]["n_unverified_rules"] > 0
    # a second pass finds its own discoveries rather than minting them again
    rep2 = org.run_once(60, dry_run=False, today=TODAY)
    assert rep2["registry"]["discoveries_created"] == 0
    assert rep2["registry"]["discoveries_existing"] >= 1


def test_placebo_null_is_drawn_from_dates_away_from_the_change(desk):
    bars = org.load_bars("JPN225")
    days, share = mc.window_share_by_day(bars.times, bars.close, ("06:00", "07:00"))
    assert days.size == share.size and share.min() >= 0.0 and share.max() <= 1.0
    ps = mc.placebo_dates(days, CHANGE, org.PRE_DAYS, org.POST_DAYS, org.PLACEBO_STEP)
    assert ps.size >= mc.MIN_PLACEBOS and CHANGE not in ps
    gap = np.abs((ps - CHANGE).astype("timedelta64[D]").astype(int))
    assert (gap >= org.PRE_DAYS + org.POST_DAYS).all()


def test_budget_exhaustion_names_the_venues_it_skipped(desk, monkeypatch):
    class Clock:
        t = 0.0

        def monotonic(self) -> float:
            self.t += 10.0
            return self.t

    monkeypatch.setattr(org, "time", Clock())
    rep = org.run_once(5, dry_run=True, today=TODAY)
    assert rep["stamps"] == [] and set(rep["stamps_skipped_for_budget"]) >= {"TSE", "KRX"}
    assert rep["studies"]                                   # the studies ran before the clock


def test_constraints_are_compiled_for_the_gateway_door_and_the_campaign_runner(desk):
    """Step 6: the registry joined to the rules in force lands as data/market_constraints.json;
    the gateway door stamps it on the roster as an INPUT (never a filter) and the campaign
    runner records it beside its coverage numbers; an absent file is UNMEASURED by name."""
    import importlib.util

    from mt5desk import decision_core as core

    rep = org.run_once(60, dry_run=False, today=TODAY)
    c = rep["constraints"]
    assert c["status"] == "MEASURED" and c["n_symbols"] == len(UNIVERSE)
    assert Path(c["path"]) == Path("data/market_constraints.json")
    assert c["consumers"] == list(org.CONSTRAINT_CONSUMERS)
    doc = json.loads((desk / "data" / "market_constraints.json").read_text("utf-8"))
    assert doc["writer"].endswith("market_constitution.py") and doc["consumers"]
    gold = doc["symbols"]["XAUUSD"]
    assert gold["instrument_class"] == "metals"
    assert gold["sessions"]["state_now"] == "CONTINUOUS"          # Tuesday 12:00 UTC
    assert gold["halts"]["desk_close_utc"] == "19:30"
    assert gold["settlement"]["rollover_hour_utc"] == 21
    # this fixture's registry carries only the asset class: tick and margin are UNMEASURED by
    # name on every row, and the file says so in its own counts
    assert gold["status"] == "UNMEASURED" and gold["tick"]["status"] == "UNMEASURED"
    assert doc["unmeasured_axes"]["tick"] == len(UNIVERSE)
    assert doc["unmeasured_axes"]["margin"] == len(UNIVERSE)
    assert doc["symbols"]["Apple"]["instrument_class"] == "equities"
    # THE GATEWAY DOOR: the clauses ride on the sleeve row; an unknown symbol gets nothing.
    rows = [{"symbol": "XAUUSD", "name": "a"}, {"symbol": "apple", "name": "b"},
            {"symbol": "ZZZ", "name": "c"}]
    assert core.stamp_market_constraints(rows, desk / "data" / "market_constraints.json") == 2
    got = rows[0]["constraints"]
    assert got["session_state"] == "CONTINUOUS" and got["input_not_cap"] is True
    assert got["rollover_hour_utc"] == 21 and got["desk_close_utc"] == "19:30"
    assert got["margin"] == "UNMEASURED" and got["status"] == "UNMEASURED"
    assert got["at"] == doc["generated_at"] and got["rule_version"] == gold["rule_version"]
    assert rows[1]["constraints"]["instrument_class"] == "equities"   # case-folded lookup
    assert "constraints" not in rows[2]
    assert core.stamp_market_constraints(rows, desk / "data" / "absent.json") == 0
    # THE ROSTER HOOK reads the file beside sleeves.json on the way through the live policy.
    sleeves = desk / "data" / "sleeves.json"
    sleeves.write_text(json.dumps({"sleeves": [
        {"name": "gold_asia_t", "symbol": "XAUUSD", "family": "session_range_breakout",
         "timeframe": "H1", "session": "asia", "status": "LIVE", "risk_frac": 0.005}]}),
        encoding="utf-8")
    kept, _notes = core.load_sleeves_verbose(sleeves)
    assert [k.get("constraints", {}).get("session_state") for k in kept] in (["CONTINUOUS"], [])
    # THE CAMPAIGN RUNNER records which docket symbols ran under a compiled constitution.
    src = _DESK / "side_channels" / "run_external_backtest.py"
    spec = importlib.util.spec_from_file_location("_reb_under_test", src)
    assert spec is not None and spec.loader is not None
    reb = importlib.util.module_from_spec(spec)
    try:
        spec.loader.exec_module(reb)
    except Exception as exc:                                   # a clone with no registry
        pytest.skip(f"campaign runner not importable here: {type(exc).__name__}: {exc}")
    cov = reb.constraints_coverage(["XAUUSD", "eurusd", "NOPE", ""],
                                   path=desk / "data" / "market_constraints.json")
    assert cov["status"] == "MEASURED" and cov["docket_symbols"] == 3
    assert cov["with_constraints"] == 2 and cov["without_constraints"] == ["NOPE"]
    assert cov["by_status"] == {"UNMEASURED": 2} and cov["generated_at"] == doc["generated_at"]
    absent = reb.constraints_coverage(["XAUUSD"], path=desk / "data" / "absent.json")
    assert absent["status"] == "UNMEASURED" and "market_constitution" in absent["why"]
