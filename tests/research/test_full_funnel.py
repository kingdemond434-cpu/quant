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
        g = math.exp(sum(math.log(v) for v in shift.values()) / len(shift))
        for d in route["protected_exploration"]:
            # the auction divides by the geometric mean: at or above it, exploration's
            # cleared share is never below its no-shift share
            assert shift[d] >= g - 1e-6, (name, d)
        assert {"intel", "discovery", "china"} <= set(route["protected_exploration"])
    # and through the real clearing: a protected department's factor does not fall
    depts = ("data", "intel", "validate", "forward")
    bids = {d: {"bid": 1.0} for d in depts}
    before = research_auction.clear(bids)
    shift = ff.exploration_guard({"data": 2.0}, depts, ["intel"])
    after = research_auction.clear({d: {"bid": shift[d]} for d in depts})
    assert after["intel"] >= before["intel"] and after["data"] > before["data"]


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
