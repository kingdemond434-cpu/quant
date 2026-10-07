"""ARCH-26: the full funnel, discovery -> portfolio decisions, measured from the artifacts that own
each stage, the limiting stage named, and compute shifted at it with exploration protected.

Pure fixtures: every artifact is injected or written under tmp_path; no tracked file is touched.
"""
from __future__ import annotations

import json
import math
import sqlite3
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
DESK = ROOT / "desks" / "mt5"
for _p in (str(ROOT), str(DESK / "research"), str(DESK)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import bottleneck_law  # noqa: E402
import full_funnel as ff  # noqa: E402
import research_auction  # noqa: E402

NOW = datetime(2026, 10, 7, 12, 0, tzinfo=UTC)
FRESH = (NOW - timedelta(hours=2)).isoformat()
LEGS = ({"acquire_datasets": "regions", "dukascopy_backfill": "data", "lake_promote": "data",
         "world_crawler": "intel", "deep_forest": "intel", "forest_china": "china",
         "external_gauntlet": "validate", "pf_allocator": "forward"},
        ("data", "regions", "intel", "discovery", "validate", "forward", "meta", "china"))


def _world(tmp: Path, urls: list[str]) -> Path:
    d = tmp / "world"
    d.mkdir()
    if not urls:  # no crawler output at all: the stage's artifact is ABSENT, not empty
        return d
    (d / f"discoveries_{(NOW - timedelta(hours=3)).strftime('%Y%m%d_%H%M')}.json").write_text(
        json.dumps([{"host": "h", "endpoints": urls}]), "utf-8")
    return d


def _acquired(n_series: int, n_pit: int) -> dict:
    series = {f"s{i}": {"rows": 500, "first": "2000-01-01", "last": "2026-10-01",
                        "acquired_at": FRESH, "pit_authority": i < n_pit}
              for i in range(n_series)}
    by_url = {f"https://x/{i}": {"series": [f"s{i}"]} for i in range(n_series)}
    return {"by_url": by_url, "series": series, "updated_at": FRESH}


def _registry(tmp: Path, judged: int, fed: list[str]) -> sqlite3.Connection:
    c = sqlite3.connect(tmp / "reg.sqlite")
    c.execute("CREATE TABLE research_candidates (id TEXT, judged_at TEXT, required_data_json "
              "TEXT, params_json TEXT, exact_rules TEXT)")
    for i in range(judged + 2):
        req = json.dumps([f"ext_{fed[i]}"]) if i < len(fed) else "[]"
        c.execute("INSERT INTO research_candidates VALUES (?,?,?,?,?)",
                  (f"c{i}", FRESH if i < judged else None, req, "{}", ""))
    c.commit()
    return c


def _build(tmp: Path, *, acquired: dict | None, conn: sqlite3.Connection | None,
           survivors: dict | None = None, sleeves: dict | None = None,
           urls: list[str] | None = None, bar_dir: Path | None = None) -> dict:
    shadow = tmp / "shadow"
    shadow.mkdir(exist_ok=True)
    (shadow / "shadow_state.json").write_text(json.dumps(
        {"a": {"status": "ACTIVE", "last_attempt_at": FRESH}}), "utf-8")
    fc = tmp / "pf_forecast_log.jsonl"
    fc.write_text(json.dumps({"t": FRESH, "book": {"x": 0.1, "y": 0.0}}) + "\n", "utf-8")
    world = _world(tmp, urls if urls is not None else [f"https://x/{i}" for i in range(10)])
    return ff.build(now=NOW, conn=conn, world_dir=world, acquired=acquired, grounds=None,
                    survivors=survivors if survivors is not None else
                    {"survivors": {"a": {}, "b": {}, "c": {}}, "swept_at": FRESH},
                    shadow_dir=shadow,
                    sleeves=sleeves if sleeves is not None else
                    {"sleeves": [{"name": "a", "status": "LIVE"},
                                 {"name": "b", "status": "STANDBY"}]},
                    forecast_path=fc, decision_path=tmp / "absent.jsonl",
                    bar_dir=bar_dir if bar_dir is not None else tmp / "no_bars", legs=LEGS)


def test_every_stage_is_measured_from_its_owning_artifact(tmp_path: Path) -> None:
    conn = _registry(tmp_path, judged=6, fed=["s0", "s1"])
    doc = _build(tmp_path, acquired=_acquired(5, 4), conn=conn)
    st = doc["stages"]
    assert list(st) == list(ff.STAGES)
    assert all(st[s]["measured"] for s in ff.STAGES), doc["unmeasured"]
    assert st["discovery"]["count"] == 10            # crawler endpoints U acquirer urls
    assert st["acquisition"]["count"] == 5
    assert st["usable_observations"]["count"] == 4
    assert st["usable_observations"]["observations"] == 2000
    assert st["tested_hypotheses"]["count"] == 6
    assert st["qualified_forecasts"]["count"] == 3
    assert st["qualified_forecasts"]["components"]["forward_clocks_accruing"] == 1
    assert st["portfolio_decisions"]["count"] == 2  # LIVE 'a' U allocator-weighted 'x'
    t = {r["stage"]: r for r in doc["transitions"]}
    assert t["discovery->acquisition"]["advanced"] == 5
    assert t["acquisition->usable_observations"]["ratio"] == 0.8
    assert t["usable_observations->tested_hypotheses"]["advanced"] == 2
    assert t["tested_hypotheses->qualified_forecasts"]["ratio"] == 0.5
    assert all(r["measured"] and not r["stale"] for r in doc["transitions"])
    assert st["acquisition"]["throughput_7d"] == 5


def test_absent_artifacts_are_unmeasured_never_zero_and_never_limiting(tmp_path: Path) -> None:
    empty = sqlite3.connect(tmp_path / "stub.sqlite")
    empty.execute("CREATE TABLE research_candidates (id TEXT, judged_at TEXT, "
                  "required_data_json TEXT, params_json TEXT, exact_rules TEXT)")
    doc = _build(tmp_path, acquired=None, conn=empty, urls=[])
    st = doc["stages"]
    for s in ("discovery", "acquisition", "usable_observations", "tested_hypotheses"):
        assert st[s]["measured"] is False and st[s]["count"] == ff.UNMEASURED, s
        assert st[s]["reason"]
    assert any("stub is not a zero" in u for u in doc["unmeasured"])
    unmeasured_t = [r for r in doc["transitions"] if not r["measured"]]
    assert len(unmeasured_t) == 4 and all(r["ratio"] is None for r in unmeasured_t)
    lim = doc["limiting"]
    assert lim is None or lim["stage"] == "qualified_forecasts->portfolio_decisions"
    # nothing measured at all -> UNMEASURED headline, no shift
    assert ff.limiting([r for r in doc["transitions"] if not r["measured"]]) is None


def test_the_limiting_stage_is_the_lowest_fresh_ratio_and_routes_to_its_organs(
        tmp_path: Path) -> None:
    conn = _registry(tmp_path, judged=6, fed=["s0", "s1", "s2", "s3"])
    doc = _build(tmp_path, acquired=_acquired(5, 1), conn=conn)   # 1 of 5 series usable
    lim = doc["limiting"]
    assert lim["stage"] == "acquisition->usable_observations" and lim["ratio"] == 0.2
    route = doc["route"]
    assert route["applied"] and route["data_stage"]
    assert set(route["departments"]) == {"regions", "data"}, "acquisition/backfill organs"
    assert doc["compute_shift"]["data"] == doc["compute_shift"]["regions"] == 1.8
    assert doc["stage_shares"]["usable_observations"] > doc["stage_shares"]["acquisition"]
    # a stale limiting stage is named but moves no compute
    stale = dict(lim, stale=True)
    shift, r = ff.compute_shift(stale, LEGS[0], LEGS[1])
    assert not r["applied"] and "stale" in r["why"]
    assert set(shift.values()) == {1.0}


def test_the_exploration_floor_holds_whatever_binds(tmp_path: Path) -> None:
    for name in ff.ROUTE_LEGS:
        lim = {"stage": name, "ratio": 0.0, "in": 10, "unit": "x", "stale": False,
               "backlog": 10}
        shares = ff.stage_shares(lim)
        assert math.isclose(sum(shares.values()), 1.0, abs_tol=1e-6)
        assert min(shares.values()) >= ff.STAGE_FLOOR - 1e-9
        assert shares["discovery"] >= ff.STAGE_FLOOR + ff.EXPLORATION_FLOOR - 1e-9
        shift, route = ff.compute_shift(lim, LEGS[0], LEGS[1])
        assert min(shift.values()) >= 1.0, "nothing is cut: total mining never falls"
        g = math.exp(sum(math.log(shift[d]) for d in LEGS[1]) / len(LEGS[1]))
        for d in route["protected"]:
            # the auction divides by the geometric mean: at or above it, a generating
            # department's cleared factor is never below its no-shift factor
            assert shift[d] >= g - 1e-6, (name, d)
        assert set(route["protected"]) == set(LEGS[1]) - {"meta"}
        assert route["may_pay"] == ["meta"]


# ------------------------------------------------- the audit of #272 (2026-10-07), item by item
AUCTION_DEPTS = ("japan", "regions", "data", "intel", "discovery", "validate", "macro",
                 "execution", "forward", "meta", "mathlab", "rest", "china", "korea")
PAYERS = {"meta", "rest", "execution"}


def test_protection_is_by_role_so_japan_and_every_region_are_covered() -> None:
    legs = {**LEGS[0], "japan_department": "japan", "forest_korea": "korea",
            "some_new_lab": "newlab"}
    depts = (*AUCTION_DEPTS, "newlab")
    prot = ff.generating_departments(depts)
    assert "japan" in prot and "newlab" in prot and "korea" in prot
    assert set(prot) == set(depts) - PAYERS
    lim = {"stage": "acquisition->usable_observations", "ratio": 0.0, "in": 9, "unit": "series",
           "stale": False, "backlog": 9}
    shift, route = ff.compute_shift(lim, legs, depts)
    g = math.exp(sum(math.log(shift[d]) for d in depts) / len(depts))
    assert shift["japan"] >= g - 1e-6 and "japan" in route["protected"]
    assert all(shift[d] == 1.0 for d in PAYERS)


def _auction(shift: dict, attack: dict, monkeypatch: pytest.MonkeyPatch) -> dict:
    monkeypatch.setattr(research_auction, "leg_departments", lambda: ({}, AUCTION_DEPTS))
    # unequal but inside the clip, so a rise or a fall is visible in the cleared factor
    hours = {d: 1.0 + 0.05 * i for i, d in enumerate(AUCTION_DEPTS)}
    yields = {d: 20 + (i % 3) for i, d in enumerate(AUCTION_DEPTS)}
    return research_auction.build(
        now=NOW, bounty={}, replenish={}, hours=hours, yields=yields,
        departments=AUCTION_DEPTS, bottleneck={"compute_shift": shift}, attack=attack)


def test_the_auctions_cleared_output_never_reduces_a_generating_department(
        monkeypatch: pytest.MonkeyPatch) -> None:
    """Asserted on research_auction.build()'s FACTORS, the number research_budget multiplies --
    with the funnel's shift AND a judging-backlog attack blended in, the case that cleared
    mathlab, macro, data and japan below par before."""
    before = _auction({}, {}, monkeypatch)["factors"]
    lim = {"stage": "acquisition->usable_observations", "ratio": 0.1, "in": 9, "unit": "series",
           "stale": False, "backlog": 8}
    legs = {"acquire_datasets": "regions", "lake_promote": "data", "dukascopy_backfill": "data"}
    shift, _ = ff.compute_shift(lim, legs, AUCTION_DEPTS)
    after_doc = _auction(shift, {"compute_shift": {"validate": 2.0}}, monkeypatch)
    after = after_doc["factors"]
    for d in set(AUCTION_DEPTS) - PAYERS:
        assert after[d] >= before[d] - 1e-4, (d, before[d], after[d])
    assert after["data"] > before["data"] and after["regions"] > before["regions"]
    assert after["validate"] > before["validate"], "the judge's backlog lands on the judge"
    assert all(after[d] <= before[d] for d in PAYERS), "only the non-generating roles pay"
    assert any(after[d] < before[d] for d in PAYERS)


def test_one_nan_cell_never_blanks_the_funnel(tmp_path: Path,
                                              monkeypatch: pytest.MonkeyPatch) -> None:
    acq = _acquired(5, 4)
    acq["series"]["s0"]["rows"] = float("nan")
    acq["series"]["s1"]["rows"] = "junk"
    conn = _registry(tmp_path, judged=6, fed=["s0"])
    doc = _build(tmp_path, acquired=acq, conn=conn)
    st = doc["stages"]
    assert st["acquisition"]["measured"] and st["acquisition"]["rows_unparseable"] == 2
    assert st["usable_observations"]["count"] == 2, "an unparseable count clears no floor"
    assert st["usable_observations"]["components"]["rows_unparseable"] == 2
    # a measurement that raises anyway is that stage's UNMEASURED; the other five stand
    monkeypatch.setattr(ff, "measure_tested",
                        lambda *a, **k: (_ for _ in ()).throw(ValueError("boom")))
    second = tmp_path / "second"
    second.mkdir()
    doc2 = _build(second, acquired=_acquired(5, 4), conn=conn)
    t = doc2["stages"]["tested_hypotheses"]
    assert t["measured"] is False and "ValueError: boom" in t["reason"]
    assert all(doc2["stages"][s]["measured"] for s in ff.STAGES if s != "tested_hypotheses")
    assert doc2["cost"]["wall_s"] >= 0


def test_the_leg_always_publishes_and_records_its_cost(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from libs.moat import registry
    monkeypatch.setattr(registry, "remember", lambda *a, **k: None)
    out = tmp_path / "rep" / "BOTTLENECK_LAW.json"
    funnel_out = out.parent / "FUNNEL_BOTTLENECK.json"
    # 1) the full funnel raises: the law publishes, and the funnel file is an UNMEASURED stub
    monkeypatch.setattr(ff, "build", lambda **k: (_ for _ in ()).throw(ValueError("nan")))
    monkeypatch.setattr(bottleneck_law, "registry_counts", lambda conn=None: {})
    assert bottleneck_law.main(["--out", str(out)]) == 0
    law = json.loads(out.read_text("utf-8"))
    fun = json.loads(funnel_out.read_text("utf-8"))
    assert fun["headline"].startswith("UNMEASURED: full funnel not measured: ValueError")
    assert law["cost"]["wall_s"] >= 0 and "peak_rss_mb" in law["cost"]
    p = law["cost"]["peak_rss_mb"]
    assert p == "UNMEASURED" or (isinstance(p, float) and p > 0)
    # 2) the law itself raises: both files are still written, stamped, UNMEASURED, no shift
    funnel_out.write_text("{}", "utf-8")
    monkeypatch.setattr(bottleneck_law, "build", lambda **k: 1 / 0)
    assert bottleneck_law.main(["--out", str(out)]) == 0
    law = json.loads(out.read_text("utf-8"))
    assert law["headline"].startswith("UNMEASURED: bottleneck law not built: ZeroDivisionError")
    assert law["compute_shift"] == {}
    assert json.loads(funnel_out.read_text("utf-8"))["headline"].startswith("UNMEASURED")
    # 3) a NaN survivor count in the law's own roster is a zero flow, never an exception
    assert bottleneck_law.roster_counts({}, {"n": float("nan")})["certified"] == 0


def test_a_survivors_file_with_no_list_and_no_count_is_unmeasured(tmp_path: Path) -> None:
    q = ff.measure_qualified({"swept_at": FRESH}, tmp_path, NOW)
    assert q["measured"] is False and "neither" in q["reason"]
    assert ff.measure_qualified({"n": 4}, tmp_path, NOW)["count"] == 4
    assert ff.measure_qualified({"survivors": []}, tmp_path, NOW)["count"] == 0


def test_a_missing_ratio_moves_nothing() -> None:
    for bad in (None, float("nan"), "0.1"):
        lim = {"stage": "acquisition->usable_observations", "ratio": bad, "in": 9,
               "unit": "series", "stale": False, "backlog": 9}
        shift, route = ff.compute_shift(lim, LEGS[0], LEGS[1])
        assert not route["applied"] and "no measured ratio" in route["why"], bad
        assert set(shift.values()) == {1.0}


def test_a_real_zero_with_no_timestamp_is_not_hidden_as_stale() -> None:
    stages = {s: {"stage": s, "measured": True, "count": 5, "as_of": None} for s in ff.STAGES}
    stages["acquisition"].update(names={"a", "b"})
    stages["usable_observations"].update(count=0, names=set())
    stages["discovery"].update(urls={"u"})
    stages["acquisition"]["urls"] = {"u"}
    trans = {t["stage"]: t for t in ff.transitions(stages, NOW)}
    z = trans["acquisition->usable_observations"]
    assert z["ratio"] == 0.0 and z["stale"] is False and z["age_unmeasured"] is True
    lim = ff.limiting(list(trans.values()))
    assert lim["stage"] == "acquisition->usable_observations"
    shift, route = ff.compute_shift(lim, LEGS[0], LEGS[1])
    assert route["applied"] and shift["data"] == 2.0
    old = dict(stages["acquisition"], as_of=(NOW - timedelta(days=9)).isoformat())
    assert ff.transitions({**stages, "acquisition": old}, NOW)[1]["stale"] is True


def test_bottleneck_law_merges_the_funnel_and_the_leg_is_registered(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from libs.moat import registry
    monkeypatch.setattr(registry, "remember", lambda *a, **k: None)  # no canonical-store write
    conn = _registry(tmp_path, judged=6, fed=["s0"])
    funnel = _build(tmp_path, acquired=_acquired(5, 1), conn=conn)
    merged = bottleneck_law.merge_funnel({"validate": 1.5, "intel": 1.0}, funnel, LEGS[1])
    assert merged["validate"] == 1.5 and merged["data"] == 1.8, "maximum per department"
    assert min(merged.values()) >= 1.0
    doc = bottleneck_law.build(now=NOW, conn=conn, sleeves_doc={"sleeves": []},
                               survivors_doc={"survivors": {}}, funnel=funnel)
    assert doc["funnel_headline"].startswith("limiting acquisition->usable_observations")
    assert doc["compute_shift"]["data"] == 1.8
    out = tmp_path / "rep" / "BOTTLENECK_LAW.json"
    bottleneck_law.publish(doc, out)
    written = json.loads((out.parent / "FUNNEL_BOTTLENECK.json").read_text("utf-8"))
    assert written["limiting"]["stage"] == "acquisition->usable_observations"
    # the hourly leg that runs it (III.16): bottleneck_law is a costed leg with a department
    src = (DESK / "research" / "hourly_cycle.py").read_text("utf-8")
    assert '_costed("bottleneck_law"' in src and '"bottleneck_law": btl' in src
    import hourly_cycle
    assert hourly_cycle.LEG_DEPARTMENT.get("bottleneck_law") == "meta"
    assert "full_funnel" in (DESK / "research" / "bottleneck_law.py").read_text("utf-8")


def _bars(tmp: Path) -> Path:
    import pandas as pd
    d = tmp / "universe"
    d.mkdir()
    for name, n, end in (("EURUSD_H1", 300, NOW - timedelta(hours=1)),
                         ("XAUUSD_M5", 120, NOW - timedelta(days=20))):
        t = pd.date_range(end=end, periods=n, freq="h", tz="UTC")
        pd.DataFrame({"close": [1.0] * n, "time": t}).to_parquet(d / f"{name}.parquet")
    return d


def test_mt5_bar_rows_are_their_own_component_and_absence_is_unmeasured(tmp_path: Path) -> None:
    conn = _registry(tmp_path, judged=6, fed=["s0"])
    doc = _build(tmp_path, acquired=_acquired(5, 4), conn=conn, bar_dir=_bars(tmp_path))
    u = doc["stages"]["usable_observations"]
    c = u["components"]
    assert c["mt5_bar_files"] == 2 and c["mt5_bar_rows"] == 420
    assert c["mt5_bar_rows_by_timeframe"] == {"H1": 300, "M5": 120}
    assert c["mt5_bar_files_fresh_7d"] == 1
    assert c["mt5_bar_last"].startswith((NOW - timedelta(hours=1)).strftime("%Y-%m-%dT%H"))
    assert c["external_observations"] == 2000 and u["observations"] == 2420
    assert u["count"] == 4, "bars never enter the acquirer-unit series count"
    t = {r["stage"]: r for r in doc["transitions"]}
    assert t["acquisition->usable_observations"]["ratio"] == 0.8
    empty = tmp_path / "e"
    empty.mkdir()
    for d in (tmp_path / "e", empty / "missing"):
        u2 = ff.with_bars(ff.measure_usable(None, NOW), ff.measure_mt5_bars(d, NOW))
        assert u2["components"]["mt5_bar_rows"] == ff.UNMEASURED
        assert u2["components"]["mt5_bar_reason"]
        assert u2["measured"] is False and "observations" not in u2


def test_certified_rate_is_from_gated_at_and_clocks_match_by_exact_identity(
        tmp_path: Path) -> None:
    spec = {"symbol": "XAUUSD", "selector": "asia", "family": "session_range_breakout",
            "params": {"rr": 1.5, "wait_bars": 8}}
    carry = {"symbol": "CHFNOK", "selector": "asia", "family": "carry",
             "params": {"input_symbol": "CHFNOK"}}
    surv = {"swept_at": FRESH, "survivors": {
        "external.XAUUSD.session_range_breakout.rr=1.5_wb=8":
            {"gated_at": (NOW - timedelta(days=2)).isoformat(), "shadow_spec": spec},
        "external.CHFNOK.carry.p=1": {"gated_at": (NOW - timedelta(days=30)).isoformat(),
                                      "shadow_spec": carry},
        "qquant.h.AUDNZD x": {"gated_at": (NOW - timedelta(days=1)).isoformat(),
                              "shadow_spec": {}},
        "external.EURUSD.carry.p=2": {"gated_at": (NOW - timedelta(days=3)).isoformat(),
                                      "shadow_spec": {"symbol": "EURUSD", "selector": "asia",
                                                      "family": "carry", "params": {}}}}}
    shadow = tmp_path / "shadow"
    shadow.mkdir()
    (shadow / "shadow_state.json").write_text(json.dumps({
        "XAUUSD.asia#rr=1.5_wait_bars=8": {"status": "ACTIVE", "forward_start": FRESH},
        "CHFNOK.carry.asia#input_symbol=CHFNOK": {"status": "ACTIVE"},
        "EURUSD.carry.asia": {"status": "RETIRED_ORPHAN"},          # not accruing: not counted
        "GBPUSD.vol_mean_reversion.continuous": {"status": "ACTIVE"},
        "OTHER.asia": {"status": "ACTIVE", "certificate": {"cell": "qquant.h.AUDNZD x"}}}),
        "utf-8")
    q = ff.measure_qualified(surv, shadow, NOW)
    assert q["throughput_7d"] == 3 and q["components"]["certified_7d"] == 3
    assert q["components"]["forward_clocks_accruing"] == 4
    assert q["components"]["forward_clocks_started_7d"] == 1
    m = q["clock_match"]
    assert m["matched"] == 3 and m["matched_by"] == {"named": 1, "key": 0, "spec": 2}
    assert m["unmatched"] == 1 and m["unmatched_sample"] == ["GBPUSD.vol_mean_reversion.continuous"]
    assert q["components"]["clocks_matched_to_a_certified_spec"] == 3
    # one certificate without its stamp makes the rate UNMEASURED, never an undercount
    surv["survivors"]["external.CHFNOK.carry.p=1"].pop("gated_at")
    assert ff.measure_qualified(surv, shadow, NOW)["throughput_7d"] == ff.UNMEASURED
