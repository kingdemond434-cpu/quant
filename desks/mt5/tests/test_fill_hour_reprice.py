"""Every certificate is priced at the hour it fills; a dead-book fill gets shifted children."""
from __future__ import annotations

import json
import sys
import types
from pathlib import Path

import numpy as np
import pandas as pd

DESK = Path(__file__).resolve().parents[1]
for _p in (str(DESK), str(DESK / "research")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from mt5desk.families_orthogonal import family_overnight_gap_decay  # noqa: E402
from research import fill_hour_reprice as fh  # noqa: E402


def _bars(days: int = 40) -> pd.DataFrame:
    """H1 bars, 24 a day, each day opening 1.0 above the prior close (a gap every morning)."""
    idx = pd.date_range("2026-01-05", periods=24 * days, freq="h", tz="UTC")
    rows, px = [], 100.0
    for t in idx:
        if t.hour == 0:
            px += 1.0                                    # the overnight gap
        rows.append((px, px + 0.1, px - 0.1, px))
    o, h, lo, c = (np.array(x) for x in zip(*rows, strict=True))
    return pd.DataFrame({"open": o, "high": h, "low": lo, "close": c}, index=idx)


def test_the_default_entry_is_unchanged_and_entry_hour_moves_only_the_fill() -> None:
    df = _bars()
    base = family_overnight_gap_decay(df, gap_atr=0.1)
    shifted = family_overnight_gap_decay(df, gap_atr=0.1, entry_hour=10)
    assert base and len(base) == len(shifted)
    assert all(s.time.hour == 0 for s in base)          # signal on the day's first bar
    assert all(s.time.hour == 9 for s in shifted)       # next-open fill is the 10:00 bar
    for b, s in zip(base, shifted, strict=True):
        assert (b.side, b.stop, b.target) == (s.side, s.stop, s.target)
        assert b.time.date() == s.time.date()


def test_a_day_without_the_entry_hour_trades_nothing() -> None:
    df = _bars()
    df = df[~((df.index.hour == 10) & (df.index.day % 2 == 0))]
    shifted = family_overnight_gap_decay(df, gap_atr=0.1, entry_hour=10)
    assert shifted and all(s.time.day % 2 == 1 for s in shifted)


def test_stats_ratio_and_verdicts() -> None:
    assert fh.stats([0.5])["status"].startswith("UNMEASURED")
    s = fh.stats([1.0, -1.0, 1.0, 1.0])
    assert s["n"] == 4 and s["exp_r"] == 0.5 and s["status"] == "MEASURED"
    surface = {"symbols": {"USDZAR": {"hours": {"1": {"status": "MEASURED", "p50": 1496.0}}}}}
    meta = {"USDZAR": {"median_spread_pts": 329.0}}
    fill, pooled, ratio = fh.ratio_of(surface, meta, "USDZAR", 1)
    assert (fill, pooled, ratio) == (1496.0, 329.0, 4.547)
    assert fh.ratio_of(surface, meta, "USDZAR", None)[2] is None      # no hour: unpriced
    assert fh.ratio_of(surface, {}, "USDZAR", 1)[2] is None           # no pooled: unpriced
    assert fh.verdict_of(False, {}) == "OUT_OF_SCOPE"
    assert fh.verdict_of(True, {"status": "MEASURED", "exp_r": -0.1}) == "NEGATIVE_AT_FILL_HOUR"
    assert fh.verdict_of(True, {"status": "MEASURED", "exp_r": 0.1}) == "SURVIVES_FILL_HOUR"
    assert fh.verdict_of(True, {"status": "UNMEASURED: x"}).startswith("UNMEASURED")


def _desk(tmp_path: Path, monkeypatch, replays: dict[str, dict]) -> list[list[dict]]:
    (tmp_path / "universe").mkdir()
    uni = tmp_path / "universe" / "universe.json"
    uni.write_text(json.dumps({"USDZAR": {"median_spread_pts": 329.0},
                               "XAUUSD": {"median_spread_pts": 16.0}}), "utf-8")
    surf = tmp_path / "cost_surface.json"
    surf.write_text(json.dumps({"symbols": {
        "USDZAR": {"hours": {"1": {"status": "MEASURED", "p50": 1496.0}}},
        "XAUUSD": {"hours": {"8": {"status": "MEASURED", "p50": 16.0}}}}}), "utf-8")
    sleeves = tmp_path / "sleeves.json"
    sleeves.write_text(json.dumps({"sleeves": [
        {"name": "usdzar_gap", "status": "LIVE",
         "certificate": {"cell": "external.USDZAR.overnight_gap_decay.p=x"}}]}), "utf-8")
    monkeypatch.setattr(fh, "SURVIVOR_FILES", (tmp_path / "absent.json",))
    for attr, path in (("UNIVERSE", uni), ("SURFACE", surf), ("SLEEVES", sleeves),
                       ("OUT", tmp_path / "FILL_HOUR_REPRICE.json"),
                       ("DONATED", tmp_path / "donated.json")):
        monkeypatch.setattr(fh, attr, path)
    survivors = [
        {"key": "external.USDZAR.overnight_gap_decay.p=x", "symbol": "USDZAR",
         "family": "overnight_gap_decay", "params": {}},
        {"key": "external.XAUUSD.session_range_breakout.rr=2.5", "symbol": "XAUUSD",
         "family": "session_range_breakout", "params": {"rr": 2.5}}]
    monkeypatch.setitem(sys.modules, "external_gauntlet", types.ModuleType("external_gauntlet"))
    pg = types.ModuleType("research.portfolio_gap")
    pg.load_survivors = lambda: survivors            # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "research.portfolio_gap", pg)
    monkeypatch.setattr(fh, "_replay",
                        lambda _eg, sym, fam, params, _m: replays[f"{sym}|{params}"])
    donations: list[list[dict]] = []

    def _donate(cands, ledger):
        donations.append(cands)
        for c in cands:
            ledger[c["key"]] = "t"
        fh.DONATED.write_text(json.dumps(ledger), "utf-8")
        return len(cands)
    monkeypatch.setattr(fh, "donate", _donate)
    return donations


def _rep(hour: int, exp_r: float) -> dict:
    m = {"status": "MEASURED", "n": 50, "t": 1.0}
    return {"fill_hour": hour, "cost_basis": f"fill_hour_{hour:02d}_spread",
            "at_pooled": {**m, "exp_r": 0.25}, "at_fill_hour": {**m, "exp_r": exp_r},
            "at_fill_hour_2x": {**m, "exp_r": exp_r - 0.3}}


def test_a_live_certificate_negative_at_its_fill_hour_alarms_and_spawns_children(
        tmp_path, monkeypatch) -> None:
    donations = _desk(tmp_path, monkeypatch, {
        "USDZAR|{}": _rep(1, -0.17),
        "XAUUSD|{'rr': 2.5}": _rep(8, 0.3),
        "USDZAR|{'entry_hour': 10}": _rep(10, 0.05),
        "USDZAR|{'entry_hour': 15}": _rep(15, -0.02)})
    rc = fh.run(force=True)
    doc = json.loads(fh.OUT.read_text("utf-8"))
    zar = doc["certificates"]["external.USDZAR.overnight_gap_decay.p=x"]
    assert zar["in_scope"] and zar["ratio"] == 4.547 and zar["fill_hour"] == 1
    assert zar["verdict"] == "NEGATIVE_AT_FILL_HOUR" and zar["live_sleeve"] == "usdzar_gap"
    assert rc == 1 and doc["alarm"][0]["sleeve"] == "usdzar_gap"
    xau = doc["certificates"]["external.XAUUSD.session_range_breakout.rr=2.5"]
    assert xau["in_scope"] is False and xau["verdict"] == "OUT_OF_SCOPE"
    kids = doc["children"]
    assert set(kids) == {"external.USDZAR.overnight_gap_decay.p=x|entry_hour=10",
                         "external.USDZAR.overnight_gap_decay.p=x|entry_hour=15"}
    assert all(k["parent"] == "external.USDZAR.overnight_gap_decay.p=x" for k in kids.values())
    assert len(donations) == 1 and len(donations[0]) == 2
    assert {c["screen"] for c in donations[0]} == {0.05, -0.02}   # the gauntlet decides, not us
    fh.run(force=True)
    assert len(donations) == 1, "a donated child is never re-donated"
    assert fh.run() == 1, "a fresh report short-circuits and keeps its alarm"


def test_no_surface_is_unmeasured_never_clean(tmp_path, monkeypatch) -> None:
    _desk(tmp_path, monkeypatch, {})
    fh.SURFACE.unlink()
    assert fh.run(force=True) == 0
    assert json.loads(fh.OUT.read_text("utf-8"))["status"].startswith("UNMEASURED")


def test_the_replay_prices_the_same_signals_three_ways() -> None:
    from mt5desk.engine import Costs
    df = _bars()
    sigs = family_overnight_gap_decay(df, gap_atr=0.1, rr=0.5)
    meta = {"contract_size": 1e5, "tick_size": 1e-5, "tick_value": 1.0,
            "median_spread_pts": 300.0}
    eg = types.SimpleNamespace(
        build_cell=lambda *_a: {"df": df, "sigs": sigs, "_fill_hour": 1,
                                "_cost_basis": "fill_hour_01_spread",
                                "costs": Costs.from_symbol(meta, spread_pts=1500.0)},
        costs_for=lambda _s, _m: Costs.from_symbol(meta))
    rep = fh._replay(eg, "USDZAR", "overnight_gap_decay", {}, {})
    pooled, fill, fill2 = rep["at_pooled"], rep["at_fill_hour"], rep["at_fill_hour_2x"]
    assert rep["fill_hour"] == 1 and pooled["n"] == fill["n"] == fill2["n"] > 2
    assert pooled["exp_r"] > fill["exp_r"] > fill2["exp_r"]
    eg.build_cell = lambda *_a: {"df": df, "sigs": sigs, "_fill_hour": 1,
                                 "_cost_basis": "pooled_median_spread",
                                 "costs": Costs.from_symbol(meta)}
    assert fh._replay(eg, "USDZAR", "overnight_gap_decay", {}, {})["at_fill_hour"][
        "status"].startswith("UNMEASURED")


def test_a_certificate_whose_cost_stress_never_bit_is_flagged_and_alarms_when_live() -> None:
    surv = {"survivors": {
        "external.AUDCHF.overnight_gap_decay.p=x": {"gates": {
            "expected_value": {"ev": 0.2377}, "stress_costs": {"exp_x3": 0.2377}}},
        "external.EURCHF.discovered.p=y": {"gates": {
            "expected_value": {"ev": 0.4764}, "stress_costs": {"exp_x3": 0.5471}}},
        "external.USDZAR.overnight_gap_decay.p=x": {"gates": {
            "expected_value": {"ev": 0.3321}, "stress_costs": {"exp_x3": 0.2442}}},
        "external.X.f.p=z": {"gates": {"expected_value": {"ev": -0.1},
                                       "stress_costs": {"exp_x3": -0.1}}},
        "external.Y.f.p=w": {"gates": {"expected_value": {"ev": 0.3}}}}}
    got = fh.cost_never_charged(surv)
    assert {k for k, v in got.items() if v["verdict"] == "COST_NEVER_CHARGED"} == {
        "external.AUDCHF.overnight_gap_decay.p=x", "external.EURCHF.discovered.p=y"}
    assert got["external.Y.f.p=w"]["verdict"].startswith("UNMEASURED"), \
        "a certificate without its stress number is unmeasured, never clean"
    assert "external.USDZAR.overnight_gap_decay.p=x" not in got
    assert fh.cost_never_charged(None) == {} and fh.cost_never_charged({"survivors": []}) == {}


def test_a_live_unbitten_certificate_raises_the_alarm(tmp_path, monkeypatch) -> None:
    _desk(tmp_path, monkeypatch, {
        "USDZAR|{}": _rep(1, 0.05), "XAUUSD|{'rr': 2.5}": _rep(8, 0.3),
        "USDZAR|{'entry_hour': 10}": _rep(10, 0.05), "USDZAR|{'entry_hour': 15}": _rep(15, 0.0)})
    surv = tmp_path / "surv.json"
    surv.write_text(json.dumps({"survivors": {"external.USDZAR.overnight_gap_decay.p=x": {
        "gates": {"expected_value": {"ev": 0.33}, "stress_costs": {"exp_x3": 0.33}}}}}), "utf-8")
    monkeypatch.setattr(fh, "SURVIVOR_FILES", (surv,))
    assert fh.run(force=True) == 1
    doc = json.loads(fh.OUT.read_text("utf-8"))
    assert doc["cost_never_charged"]["external.USDZAR.overnight_gap_decay.p=x"][
        "sleeve"] == "usdzar_gap"
    assert doc["summary"]["cost_never_charged"] == 1
    assert any("cost never charged" in a.get("why", "") for a in doc["alarm"])


def test_the_charge_check_runs_without_a_cost_surface_and_flags_standby(
        tmp_path, monkeypatch) -> None:
    _desk(tmp_path, monkeypatch, {})
    fh.SURFACE.unlink()
    fh.SLEEVES.write_text(json.dumps({"sleeves": [
        {"name": "audchf_gap", "status": "STANDBY",
         "certificate": {"cell": "external.AUDCHF.overnight_gap_decay.p=x"}}]}), "utf-8")
    surv = tmp_path / "surv.json"
    surv.write_text(json.dumps({"survivors": {"external.AUDCHF.overnight_gap_decay.p=x": {
        "gates": {"expected_value": {"ev": 0.24}, "stress_costs": {"exp_x3": 0.24}}}}}), "utf-8")
    monkeypatch.setattr(fh, "SURVIVOR_FILES", (surv,))
    assert fh.run(force=True) == 1
    doc = json.loads(fh.OUT.read_text("utf-8"))
    assert doc["status"].startswith("UNMEASURED")
    row = doc["cost_never_charged"]["external.AUDCHF.overnight_gap_decay.p=x"]
    assert row["roster_status"] == "STANDBY" and row["sleeve"] == "audchf_gap"
    assert doc["alarm"][0]["roster_status"] == "STANDBY"


def test_the_alarm_exit_is_a_verdict_in_the_hourly_cycle() -> None:
    from research import hourly_cycle as hc
    assert 1 in hc.VERDICT_EXITS["fill_hour_reprice"]
