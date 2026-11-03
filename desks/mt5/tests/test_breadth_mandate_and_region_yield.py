"""Rows 72 and 75: the breadth mandate moves every hour, the three never-attempted clusters are
reachable, and every source-registry region reports what it yields.

WHAT THIS PINS, on synthetic bars and artifacts only:
  * the mandate counts clusters from JUDGE_COVERAGE's per-family census (never a whole-docket
    load), judges EVERY declared cluster with zero cells, and refuses an oversized docket as
    UNMEASURED instead of loading it;
  * `jump` classifies into news_reaction, `entry_alpha` into execution_entry, `implied_vol` into
    options_implied; both new families are registered where the sealed gauntlet looks and judged
    BUILDABLE;
  * entry_alpha changes ONLY the entry (a better resting limit, R geometry unchanged);
    implied_vol emits nothing without its series and trades both modes with it, with no lookahead;
  * the forcer writes the mandate, mints EXACT_RECIPE cells for a zero-cell cluster, and names a
    DATA_GAP (minting nothing) when the implied series is unreadable;
  * the liveness fence is RED when a scheduled leg's artifact is stale, GREEN when fresh,
    UNSCHEDULED for a contract with no clock, UNMEASURED when the cycle source is unreadable;
  * the region yield report covers every registry's regions, is RED for sources with zero
    measured output, UNMEASURED when its counters are absent, and is wired as an hourly leg.
"""
from __future__ import annotations

import importlib.util
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

from mt5desk import families_cluster_reach as reach  # noqa: E402
from mt5desk import families_orthogonal as fo  # noqa: E402
from mt5desk.families import family_trend_ma_cross  # noqa: E402


def _load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture()
def mandate():
    return _load("check_breadth_mandate_t", _ROOT / "scripts" / "check_breadth_mandate.py")


@pytest.fixture()
def liveness():
    return _load("check_leg_artifact_liveness_t",
                 _ROOT / "scripts" / "check_leg_artifact_liveness.py")


def _bars(seed: int = 1, days: int = 600) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    dates = pd.bdate_range("2022-01-03", periods=days, tz="UTC")
    idx = pd.DatetimeIndex([d + pd.Timedelta(hours=h) for d in dates for h in range(24)])
    close = 100.0 * np.exp(np.cumsum(rng.normal(0.0, 0.002, len(idx))))
    open_ = np.r_[close[0], close[:-1]]
    return pd.DataFrame({"open": open_, "high": np.maximum(open_, close) * 1.0005,
                         "low": np.minimum(open_, close) * 0.9995, "close": close,
                         "tick_volume": 100}, index=idx)


def _vix_file(tmp: Path, days: int = 600, seed: int = 7) -> Path:
    rng = np.random.default_rng(seed)
    dates = pd.bdate_range("2022-01-03", periods=days)
    vals = np.clip(18 + np.cumsum(rng.normal(0, 0.8, days)) * 0.3, 9, 80)
    p = tmp / "fred_macro.json"
    p.write_text(json.dumps({"series": {"VIXCLS": [[str(d.date()), float(v)]
                                                   for d, v in zip(dates, vals, strict=True)]}}))
    return p


# ------------------------------------------------------------------- classification ---
def test_the_three_never_attempted_clusters_have_a_family():
    from libs.research.alpha_clusters import classify_family
    assert classify_family("jump") == "news_reaction"
    assert classify_family("entry_alpha") == "execution_entry"
    assert classify_family("implied_vol") == "options_implied"
    assert classify_family("event_reaction") == "event_surprise"   # scheduled stays scheduled


@pytest.mark.parametrize("name", ("entry_alpha", "implied_vol"))
def test_new_families_registered_and_buildable(name):
    from mt5desk import families_specialist as fs
    from research import axis_registry
    from research import gauntlet_buildability as gb
    assert fo.ORTHOGONAL_FAMILIES[name] is fs.SPECIALIST_FAMILIES[name]
    assert name in fo.FAMILY_INPUTS
    assert gb.family_verdict(name)[0] == gb.BUILDABLE
    assert name in axis_registry.FAMILY_TABLE
    assert "entry_alpha" in fs.unwrappable()


def test_implied_vol_is_exogenous_not_price_only():
    from research import gauntlet_buildability as gb
    assert gb.information_class("implied_vol") == gb.EXOGENOUS
    assert gb.information_class("entry_alpha") == gb.PRICE_ONLY
    assert any("VIXCLS" in p for p in gb.foreign_series("implied_vol"))


# ------------------------------------------------------------------------ entry alpha ---
def test_entry_alpha_changes_only_the_entry():
    df = _bars()
    base = family_trend_ma_cross(df)
    got = reach.family_entry_alpha(df, base_family="trend_ma_cross", offset_atr=0.5, wait_bars=4)
    assert base and len(got) == len(base)
    for b, e in zip(base, got, strict=True):
        assert e.time == b.time and e.side == b.side and e.wait_bars == 4
        assert e.trigger is not None
        ref = float(df["close"].loc[b.time])
        assert e.side * (ref - e.trigger) > 0                       # a BETTER price: a limit
        assert abs((e.trigger - e.stop) - (ref - b.stop)) < 1e-9 * ref   # same risk distance
        assert abs((e.target - e.trigger) - (b.target - ref)) < 1e-9 * ref


@pytest.mark.parametrize("kw", ({"offset_atr": 0.0}, {"wait_bars": 0},
                                {"base_family": "entry_alpha"}, {"base_family": "nope"}))
def test_entry_alpha_refuses_malformed_cells(kw):
    assert reach.family_entry_alpha(_bars(days=120), **kw) == []


def test_sealed_build_cell_builds_entry_alpha():
    import external_gauntlet as eg
    df = _bars(days=400)
    cell = eg.build_cell("IDX", "entry_alpha", {"base_family": "trend_ma_cross"}, {},
                         h1_override=df)
    assert cell is not None, eg.LAST_BUILD_FAILURE
    assert cell["sigs"]


# ------------------------------------------------------------------------ implied vol ---
def test_implied_vol_needs_its_series(tmp_path, monkeypatch):
    monkeypatch.setattr(reach, "FRED_MACRO", tmp_path / "absent.json")
    monkeypatch.setattr(reach, "LAKE", tmp_path)
    assert reach.family_implied_vol(_bars()) == []
    ok, why = reach.source_state("VIXCLS")
    assert not ok and "VIXCLS" in why


def test_implied_vol_trades_both_modes_without_lookahead(tmp_path, monkeypatch):
    monkeypatch.setattr(reach, "FRED_MACRO", _vix_file(tmp_path))
    monkeypatch.setattr(reach, "LAKE", tmp_path)
    df = _bars()
    h = reach.family_implied_vol(df, mode="harvest", z_entry=0.5)
    s = reach.family_implied_vol(df, mode="stress", z_entry=0.5)
    assert h and s
    assert {x.side for x in h} == {1} and {x.side for x in s} == {-1}
    cut = df.index[len(df) * 2 // 3]
    dirty = df.copy()
    m = dirty.index >= cut
    for c in ("open", "high", "low", "close"):
        dirty.loc[m, c] = dirty.loc[m, c].to_numpy() * 1.3
    before = [(x.time, x.side) for x in h if x.time < cut - pd.Timedelta(days=3)]
    after = [(x.time, x.side) for x in reach.family_implied_vol(dirty, mode="harvest",
                                                                z_entry=0.5)
             if x.time < cut - pd.Timedelta(days=3)]
    assert before == after


# ------------------------------------------------------------------------ the mandate ---
def _judge_doc(at: datetime, mined: dict[str, int]) -> dict:
    return {"at": at.isoformat(), "families": {f: {"mined": n} for f, n in mined.items()}}


def test_mandate_counts_from_judge_coverage_and_checks_every_declared_cluster(
        tmp_path, monkeypatch, mandate):
    jc = tmp_path / "JUDGE_COVERAGE.json"
    jc.write_text(json.dumps(_judge_doc(datetime.now(UTC), {"jump": 40, "carry": 10})))
    monkeypatch.setattr(mandate, "JUDGE_COVERAGE", jc)
    monkeypatch.setattr(mandate, "BREADTH", tmp_path / "absent_breadth.json")
    monkeypatch.setattr(mandate, "FORCER", tmp_path / "absent_forcer.json")
    monkeypatch.setattr(mandate, "DOCKET", tmp_path / "absent_docket.json")
    doc = mandate.check()
    assert doc["cluster_cell_counts"]["news_reaction"] == 40
    assert "JUDGE_COVERAGE" in doc["counts_basis"]
    verdicts = {r["cluster"]: r["verdict"] for r in doc["clusters"]}
    # EFFECTIVE_BREADTH is absent, yet every zero-cell declared cluster is judged
    assert verdicts["execution_entry"] == "NEVER_ATTEMPTED"
    assert verdicts["options_implied"] == "NEVER_ATTEMPTED"
    assert "news_reaction" not in verdicts and "macro_rates" not in verdicts
    assert doc["declared_clusters"] == 15


def test_a_stale_judge_census_and_a_huge_docket_read_unmeasured(tmp_path, monkeypatch, mandate):
    jc = tmp_path / "JUDGE_COVERAGE.json"
    jc.write_text(json.dumps(_judge_doc(datetime.now(UTC) - timedelta(days=5), {"jump": 4})))
    big = tmp_path / "docket.json"
    big.write_text("[" + " " * 200 + "]")
    monkeypatch.setattr(mandate, "JUDGE_COVERAGE", jc)
    monkeypatch.setattr(mandate, "DOCKET", big)
    monkeypatch.setattr(mandate, "DOCKET_FALLBACK_MAX_BYTES", 10)
    monkeypatch.setattr(mandate, "BREADTH", tmp_path / "absent.json")
    counts, why = mandate._cluster_counts()
    assert counts == {} and why.startswith("UNMEASURED")


def test_mandate_joins_the_forcer(tmp_path, monkeypatch, mandate):
    jc = tmp_path / "JUDGE_COVERAGE.json"
    jc.write_text(json.dumps(_judge_doc(datetime.now(UTC), {"carry": 10})))
    forcer = tmp_path / "EMPTY_CLUSTER_FORCER.json"
    forcer.write_text(json.dumps({"generated_utc": "x", "clusters": [
        {"cluster": "execution_entry", "verdict": "FORCED", "cells_minted": 6,
         "families": ["entry_alpha"]},
        {"cluster": "options_implied", "verdict": "DATA_GAP", "data_gap": "no VIXCLS here"}]}))
    for k, v in (("JUDGE_COVERAGE", jc), ("FORCER", forcer), ("BREADTH", tmp_path / "a.json")):
        monkeypatch.setattr(mandate, k, v)
    verdicts = {r["cluster"]: r for r in mandate.check()["clusters"]}
    assert verdicts["execution_entry"]["verdict"] == "FORCED_PENDING"
    assert verdicts["options_implied"]["verdict"] == "UNMEASURED"
    assert "VIXCLS" in verdicts["options_implied"]["why"]


# ------------------------------------------------------------------------- the forcer ---
@pytest.fixture()
def forcer():
    from research import empty_cluster_forcer as ecf
    return ecf


def test_forcer_mints_exact_recipes_for_zero_cell_clusters(forcer, monkeypatch, tmp_path):
    monkeypatch.setattr(reach, "FRED_MACRO", tmp_path / "absent.json")
    monkeypatch.setattr(reach, "LAKE", tmp_path)
    monkeypatch.setattr(forcer, "BREADTH", tmp_path / "absent.json")
    monkeypatch.setattr(forcer, "_symbols_for",
                        lambda fam, uni, turn: ["EURUSD", "GBPUSD", "USDJPY", "AUDUSD",
                                                "USDCAD", "EURJPY", "XAUUSD"])
    m = {"empty": ["execution_entry", "options_implied"],
         "cluster_cell_counts": {"execution_entry": 0, "options_implied": 0}}
    doc = forcer.plan(m)
    rows = {r["cluster"]: r for r in doc["clusters"]}
    assert rows["execution_entry"]["verdict"] == "FORCED"
    assert rows["execution_entry"]["cells_minted"] == forcer.CELLS_PER_CLUSTER
    assert rows["options_implied"]["verdict"] == "DATA_GAP"
    assert "VIXCLS" in rows["options_implied"]["data_gap"]
    cells = doc["cells"]
    assert cells and all(c["family"] == "entry_alpha" and isinstance(c["params"], dict)
                         for c in cells)
    from research.miner_candidate_compiler import compile_row
    cands, disp = compile_row("breadth", cells[0], {"EURUSD", "GBPUSD", "USDJPY", "AUDUSD",
                                                     "USDCAD", "EURJPY", "XAUUSD"})
    assert disp == "EXACT_RECIPE" and cands[0]["family"] == "entry_alpha"


def test_forcer_mints_implied_vol_when_the_series_is_readable(forcer, monkeypatch, tmp_path):
    monkeypatch.setattr(reach, "FRED_MACRO", _vix_file(tmp_path))
    monkeypatch.setattr(reach, "LAKE", tmp_path)
    monkeypatch.setattr(forcer, "BREADTH", tmp_path / "absent.json")
    monkeypatch.setattr(forcer, "_read", lambda p, d=None: (
        {"US500": {}, "US30": {}, "NAS100": {}} if p == forcer.UNIVERSE else (d or {})))
    doc = forcer.plan({"empty": ["options_implied"],
                       "cluster_cell_counts": {"options_implied": 0}})
    row = doc["clusters"][0]
    assert row["verdict"] == "FORCED" and row["cells_minted"] == 6
    assert {c["symbols"][0] for c in doc["cells"]} <= {"US500", "US30", "NAS100"}
    assert {c["params"]["mode"] for c in doc["cells"]} == {"harvest", "stress"}


# --------------------------------------------------------------------- liveness fence ---
def _cycle(tmp: Path, legs: list[str]) -> Path:
    p = tmp / "hourly_cycle.py"
    p.write_text("\n".join(f'x = _costed("{leg}", lambda: 0)' for leg in legs))
    return p


def test_liveness_red_green_unscheduled_unmeasured(tmp_path, liveness):
    now = datetime.now(UTC)
    (tmp_path / "fresh.json").write_text(json.dumps({"generated_utc": now.isoformat()}))
    (tmp_path / "stale.json").write_text(json.dumps(
        {"generated_utc": (now - timedelta(days=5)).isoformat()}))
    contracts = {"a": (("fresh.json", 3.0),), "b": (("stale.json", 3.0),),
                 "c": (("missing.json", 3.0),), "d": (("fresh.json", 3.0),)}
    doc = liveness.check(now=now, root=tmp_path, contracts=contracts,
                         cycle=_cycle(tmp_path, ["a", "b", "c"]),
                         marker=tmp_path / "no_marker.json")
    v = {r["leg"]: r["verdict"] for r in doc["rows"]}
    assert v == {"a": "GREEN", "b": "RED", "c": "RED", "d": "UNSCHEDULED"}
    assert doc["status"] == "RED" and set(doc["red"]) == {"b", "c", "d"}
    um = liveness.check(now=now, root=tmp_path, contracts={"a": (("fresh.json", 3.0),)},
                        cycle=tmp_path / "unreadable.py", marker=tmp_path / "x.json")
    assert um["status"] == "UNMEASURED"


def test_liveness_contracts_are_scheduled_in_the_real_cycle(liveness):
    legs = liveness.scheduled_legs()
    assert legs is not None
    for leg in liveness.CONTRACTS:
        assert leg in legs, leg
    assert "leg_artifact_liveness" in legs


# ----------------------------------------------------------------------- region yield ---
def test_region_yield_red_unmeasured_and_ranked(tmp_path, monkeypatch):
    from research import region_yield as ry
    src = {"regions": {"ar": {}, "br": {}, "cn": {}},
           "grounds": [{"name": "g_ar", "region": "ar"}, {"name": "g_br1", "region": "br"},
                       {"name": "g_br2", "region": "br"}, {"name": "g_cn", "region": "cn"}]}
    (tmp_path / "src.json").write_text(json.dumps(src))
    (tmp_path / "cg.json").write_text(json.dumps({"sources": [{"region": "sa"}]}))
    (tmp_path / "asia.json").write_text(json.dumps({"sources": [{"country": "kr"}]}))
    (tmp_path / "countries" / "ae").mkdir(parents=True)
    (tmp_path / "countries" / "ae" / "pack.py").write_text("")
    (tmp_path / "claims.jsonl").write_text(json.dumps({"region": "cn"}) + "\n")
    (tmp_path / "stats.json").write_text(json.dumps({"vectors": {
        "g_cn": {"rows": 5, "datasets": 1}, "g_ar": {"rows": 0}, "g_br1": {"rows": 0}}}))
    for k, v in (("SOURCES", "src.json"), ("CULTURE_GAP", "cg.json"), ("ASIA", "asia.json"),
                 ("CLAIMS", "claims.jsonl"), ("VECTOR_STATS", "stats.json"),
                 ("DATASETS", "absent.jsonl"), ("CELL_CULTURE", "absent.json"),
                 ("FRONTIER", "absent.json")):
        monkeypatch.setattr(ry, k, tmp_path / v)
    monkeypatch.setattr(ry, "COUNTRIES", tmp_path / "countries")
    monkeypatch.setattr(ry, "REPORTS", tmp_path)
    doc = ry.build()
    rows = {r["region"]: r for r in doc["regions"]}
    assert {"ar", "br", "cn", "sa", "kr", "ae"} <= set(rows)       # every registry's regions
    assert rows["br"]["sources"] == 2 and rows["br"]["verdict"] == "RED"
    assert rows["ar"]["verdict"] == "RED" and rows["cn"]["verdict"] == "YIELDING"
    assert rows["cn"]["claims"] == 1 and rows["cn"]["rows"] == 6
    assert rows["cn"]["cells_minted"] == "UNMEASURED"           # CELL_CULTURE absent
    assert doc["status"] == "RED" and "br" in doc["red"]
    ranks = [r["region"] for r in doc["regions"]]
    assert ranks.index("br") < ranks.index("ar") < ranks.index("cn")  # RED first, more sources


def test_region_yield_without_counters_is_unmeasured(tmp_path, monkeypatch):
    from research import region_yield as ry
    (tmp_path / "src.json").write_text(json.dumps({"grounds": [{"name": "g", "region": "cl"}]}))
    for k in ("CULTURE_GAP", "ASIA", "CLAIMS", "VECTOR_STATS", "DATASETS", "CELL_CULTURE",
              "FRONTIER"):
        monkeypatch.setattr(ry, k, tmp_path / f"absent_{k}")
    monkeypatch.setattr(ry, "SOURCES", tmp_path / "src.json")
    monkeypatch.setattr(ry, "COUNTRIES", tmp_path / "none")
    monkeypatch.setattr(ry, "REPORTS", tmp_path)
    doc = ry.build()
    assert doc["regions"][0]["verdict"] == "UNMEASURED" and doc["status"] == "UNMEASURED"


def test_both_new_legs_are_wired_hourly():
    import hourly_cycle as hc
    from libs.research import layers
    for leg in ("region_yield", "leg_artifact_liveness"):
        assert leg in hc.CORE_LEGS
        assert leg in hc.LEG_DEPARTMENT
        assert layers.LEG_LAYER[leg] == "meta"
    src = (_DESK / "research" / "hourly_cycle.py").read_text(encoding="utf-8")
    assert '_costed("region_yield"' in src and '_costed("leg_artifact_liveness"' in src
    assert '_costed("empty_cluster_forcer"' in src
