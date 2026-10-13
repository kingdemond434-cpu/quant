"""THE FOUR ASIA LATENT DATASETS, THE ASIA EVENT OBJECTS AND THE TRANSMISSION FAILURE MEMORY.

Package P5 of the 2026-10-06 Asia audit. Every input here is a SYNTHETIC FIXTURE written in the
exact shape the axis door publishes (`alt_proxies.axis_doc`: `series["<name>.value"].points`,
each point carrying `d`, `v`, `available_time`, `published_time`, `event_time`,
`first_seen_at`, `revision_time`, `vintage_id`, `pit_quality`) and, for the funding state, the
rows shape of `data/axes/bis.json` (`rows[{symbol, knowable_at, carry_differential}]`). The
values are generated from a KNOWN latent AR(1) factor so the tests can assert what the model
must recover. Live yield of every input is UNMEASURED until the trading box runs the leg.

What is proved:
  * a vintage is POINT-IN-TIME: rebuilding from inputs truncated at D reproduces the vintage at D;
  * the ledger is APPEND-ONLY: a later pass adds lines and never rewrites one;
  * not-yet-collected inputs read NOT_YET_COLLECTED with their delivering package, unconfirmed
    terms read BLOCKED_ON_TERMS, and no price series is fused;
  * the consumers read the states: FieldCatalogue (axis door), exogenous_conditioner (lake),
    state_vector_build.world_conditioning (allocation intel), and the event lifecycle;
  * Asian events are scoped by currency and instrument (a Korean print is not a EURUSD event);
  * every latent look is charged, null passes included;
  * asia_transmission keeps failures after a later success, and the battery passes --propose.
"""
from __future__ import annotations

import json
import sys
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import pytest

_DESK = Path(__file__).resolve().parents[1]
_ROOT = _DESK.parent.parent
for _p in (str(_DESK), str(_DESK / "research"), str(_ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from libs.regime import event_state as es  # noqa: E402
from research import asia_transmission as at  # noqa: E402
from research import macro_state_engine as mse  # noqa: E402

NOW = datetime(2026, 9, 30, 12, 0, tzinfo=UTC)


def _factor(n: int, seed: int) -> np.ndarray:
    rng = np.random.default_rng(seed)
    f = np.zeros(n)
    for i in range(1, n):
        f[i] = 0.9 * f[i - 1] + rng.normal(0, 0.45)
    return f


def _series_doc(stem: str, series: dict[str, list[tuple[str, datetime, float]]]) -> dict[str, Any]:
    """An axis doc in alt_proxies.axis_doc's shape: (period, available_time, value) per point."""
    out: dict[str, Any] = {}
    for name, pts in series.items():
        out[name] = {"what": name, "n": len(pts), "points": [
            {"d": d, "v": v, "available_time": t.isoformat(), "published_time": t.isoformat(),
             "event_time": d, "first_seen_at": t.isoformat(), "revision_time": None,
             "vintage_id": f"{stem}:{name}:{d}:{t.isoformat()}", "pit_quality": "pit"}
            for d, t, v in pts]}
    return {"axis": "alt_proxy", "id": stem, "series": out}


def _write_fixture(axes: Path, end: datetime | None = None) -> None:
    """Korea 10/20-day exports + semis (10-daily), Singapore TEU (monthly), BIS rows (daily)."""
    axes.mkdir(parents=True, exist_ok=True)
    start = datetime(2024, 1, 1, tzinfo=UTC)
    days = (datetime(2026, 9, 29, tzinfo=UTC) - start).days
    f = _factor(days + 1, seed=7)
    rng = np.random.default_rng(11)
    kr_avg, kr_semi, sg = [], [], []
    d = start
    while d <= datetime(2026, 9, 29, tzinfo=UTC):
        k = (d - start).days
        if d.day in (11, 21):
            t = d + timedelta(hours=2)
            kr_avg.append((d.date().isoformat(), t, 5.0 + 6.0 * f[k] + rng.normal(0, 1.5)))
            kr_semi.append((d.date().isoformat(), t, 10.0 + 12.0 * f[k] + rng.normal(0, 4)))
        if d.day == 15:
            sg.append((d.date().isoformat(), d + timedelta(hours=5),
                       3200.0 + 150.0 * f[k] + rng.normal(0, 40)))
        d += timedelta(days=1)
    if end is not None:
        kr_avg = [p for p in kr_avg if p[1] <= end]
        kr_semi = [p for p in kr_semi if p[1] <= end]
        sg = [p for p in sg if p[1] <= end]
    (axes / "alt_kr_exports_early.json").write_text(json.dumps(_series_doc(
        "alt_kr_exports_early", {"daily_avg_yoy.value": kr_avg, "semis_yoy.value": kr_semi})))
    (axes / "alt_sg_port_throughput.json").write_text(json.dumps(_series_doc(
        "alt_sg_port_throughput", {"container_throughput_k_teu.value": sg})))
    rows = []
    day, rate = date(2023, 1, 2), 4.0
    while day <= date(2026, 9, 28):
        if day.weekday() < 5:
            if day.day == 1:
                rate += float(rng.choice([-0.25, 0.0, 0.25]))
            if end is None or datetime(day.year, day.month, day.day, tzinfo=UTC) \
                    + timedelta(days=1) <= end:
                for sym, off in (("USDJPY", 0.0), ("AUDJPY", -0.5)):
                    rows.append({"symbol": sym, "knowable_at": day.isoformat(), "base": "X",
                                 "quote": "JPY", "base_rate": rate + off, "quote_rate": 0.25,
                                 "carry_differential": rate + off - 0.25})
        day += timedelta(days=1)
    (axes / "bis.json").write_text(json.dumps({"axis": "policy", "id": "bis_policy_rates",
                                               "rows": rows}, indent=1))


@pytest.fixture()
def world(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    _write_fixture(tmp_path / "axes")
    monkeypatch.setattr(mse, "_terms", lambda sid: "confirmed")
    for name, rel in (("AXES_DIR", "axes"), ("LATENT_DIR", "latent"),
                      ("LAKE_SERIES", "series"), ("LATENT_INTEL", "reports/LI.json"),
                      ("ASIA_EVENTS", "latent/asia_events.json"),
                      ("ASIA_EVENTS_LEDGER", "latent/asia_events.jsonl"),
                      ("NULL_TRIALS", "null.jsonl"),
                      ("SURVIVORS", "reports/UNIVERSAL_SURVIVORS.json")):
        monkeypatch.setattr(mse, name, tmp_path / rel)
    return tmp_path


def _run(world: Path, now: datetime = NOW, specs: tuple[mse.LatentSpec, ...] | None = None,
         ) -> dict[str, Any]:
    return mse.build_latent(now, budget_s=120.0, apply=True, cells=False,
                            specs=specs or (mse.LATENT_BY_ID["asia_export"],
                                            mse.LATENT_BY_ID["asia_funding"]),
                            environ={})


# ------------------------------------------------------------------------------- the datasets
def test_vintages_are_built_published_and_carry_the_sensor_contract(world: Path) -> None:
    rep = _run(world)
    ds = rep["datasets"]["asia_export"]
    assert ds["status"] == "OK" and ds["n_vintages"] > 50
    assert ds["n_inputs_collected"] >= 3 and ds["price_inputs"] == []
    led = mse.read_ledger(world / "latent" / "latent_asia_export.vintages.jsonl")
    last = led[-1]
    for k in ("dataset_id", "observation_id", "entity", "geography", "metric", "value", "unit",
              "event_time", "scheduled_time", "publication_time", "knowable_at",
              "expected_value", "consensus", "raw_surprise", "surprise_z", "revision_of",
              "revision_delta", "measurement_uncertainty", "provenance_hash"):
        assert k in last, k
    assert last["consensus"] is None and "UNMEASURED" in last["consensus_status"]
    assert last["uncertainty"] > 0 and last["baseline_level"] is not None
    # The planted factor loads POSITIVELY on every Korean export input: the model recovered it.
    loads = {c["input"]: c["loading"] for c in last["components"]}
    assert loads["kr_exports_daily_avg"] > 0.3 and loads["kr_semis_exports"] > 0.3
    # Kalman level and the equal-weight baseline describe the same state.
    lv = np.array([r["level"] for r in led[-200:]])
    ew = np.array([r["baseline_level"] for r in led[-200:]])
    assert float(np.corrcoef(lv, ew)[0, 1]) > 0.5
    # Publication: axis door, lake envelope, allocation intel.
    assert (world / "axes" / "latent_asia_export.json").exists()
    assert (world / "series" / "latent_asia_export.csv").exists()
    intel = json.loads((world / "reports" / "LI.json").read_text())
    assert "USDKRW" in intel["instruments"] and "AUDJPY" in intel["instruments"]


def test_inputs_not_collected_are_named_never_substituted(world: Path,
                                                          monkeypatch: pytest.MonkeyPatch,
                                                          ) -> None:
    monkeypatch.setattr(mse, "_terms",
                        lambda sid: "to_confirm" if sid == "cn_sge_premium" else "confirmed")
    rep = _run(world, specs=(mse.LATENT_BY_ID["cn_physical_gold"],
                             mse.LATENT_BY_ID["asia_export"]))
    gold = {r["input"]: r for r in rep["datasets"]["cn_physical_gold"]["inputs"]}
    assert gold["sge_premium"]["status"] == "BLOCKED_ON_TERMS:to_confirm"
    assert gold["india_gold_imports"]["status"] == "UNMEASURED"
    assert gold["swiss_gold_exports"]["status"] == "NOT_YET_COLLECTED"
    assert "swiss_customs_gold" in gold["swiss_gold_exports"]["why"]
    assert rep["datasets"]["cn_physical_gold"]["status"].startswith("UNMEASURED")
    assert not (world / "axes" / "latent_cn_physical_gold.json").exists()
    exp = {r["input"]: r for r in rep["datasets"]["asia_export"]["inputs"]}
    assert exp["kr_mof_teu"]["status"] == "BLOCKED_ON_KEY:DATA_GO_KR_KEY"
    assert exp["tw_export_orders"]["status"] == "NOT_YET_COLLECTED"


def test_a_vintage_is_point_in_time(world: Path, tmp_path_factory: pytest.TempPathFactory,
                                    monkeypatch: pytest.MonkeyPatch) -> None:
    """Rebuild from inputs TRUNCATED at D: the vintage at D must be the same number."""
    spec = (mse.LATENT_BY_ID["asia_export"],)
    _run(world, specs=spec)
    full = mse.read_ledger(world / "latent" / "latent_asia_export.vintages.jsonl")
    cut = datetime(2026, 3, 20, tzinfo=UTC)
    at_d = [r for r in full if datetime.fromisoformat(r["knowable_at"]) <= cut][-1]
    other = tmp_path_factory.mktemp("trunc")
    _write_fixture(other / "axes", end=cut)
    for name, rel in (("AXES_DIR", "axes"), ("LATENT_DIR", "latent"),
                      ("LAKE_SERIES", "series"), ("LATENT_INTEL", "LI.json")):
        monkeypatch.setattr(mse, name, other / rel)
    _run(world, now=NOW, specs=spec)
    trunc = mse.read_ledger(other / "latent" / "latent_asia_export.vintages.jsonl")
    same = [r for r in trunc if r["knowable_at"] == at_d["knowable_at"]]
    assert same, "the truncated world must reach the same release date"
    for k in ("level", "uncertainty", "baseline_level", "pca_level", "surprise_z"):
        assert same[-1][k] == at_d[k], k


def test_the_ledger_is_append_only(world: Path) -> None:
    spec = (mse.LATENT_BY_ID["asia_funding"],)
    _run(world, now=datetime(2026, 6, 30, tzinfo=UTC), specs=spec)
    path = world / "latent" / "latent_asia_funding.vintages.jsonl"
    before = path.read_text().splitlines()
    rep = _run(world, now=NOW, specs=spec)
    after = path.read_text().splitlines()
    assert after[: len(before)] == before
    assert len(after) > len(before) and rep["datasets"]["asia_funding"]["new_vintages"] > 0
    # A third pass on the same clock owes nothing and appends nothing.
    _run(world, now=NOW, specs=spec)
    assert path.read_text().splitlines() == after


# ------------------------------------------------------------------------------- consumers
def test_field_catalogue_and_conditioner_read_the_latent_state(world: Path) -> None:
    _run(world)
    from mt5desk.family_exogenous_conditioner import conditioner

    from libs.research.alpha_dsl import FieldCatalogue
    cat = FieldCatalogue(axes_dir=world / "axes")
    f = cat.by_name("latent_asia_export.level")
    assert f is not None and f.causal() and f.availability == "available_time"
    idx = pd.date_range("2026-01-01", "2026-09-29", freq="D", tz="UTC")
    s = cat.series(f, idx)
    assert s is not None and int(s.notna().sum()) > 100
    c = conditioner("latent_asia_export", "level", "level_z", root=world / "series")
    assert c is not None and len(c) > 50


def test_state_vector_merges_the_latent_states(world: Path,
                                               monkeypatch: pytest.MonkeyPatch) -> None:
    _run(world)
    import state_vector_build as svb
    rows, _why = svb.world_conditioning(["USDKRW", "EURUSD"])
    latent = [r for r in rows.get("USDKRW", []) if r.get("kind") == "latent_state"]
    assert latent and latent[0]["src"] == "latent_asia_export"
    assert latent[0]["authority"] == "none" and latent[0]["sign"] == -1
    assert not [r for r in rows.get("EURUSD", []) if r.get("kind") == "latent_state"]


# ------------------------------------------------------------------------------- events
def test_asian_events_are_scoped_by_currency_and_instrument() -> None:
    rows = es.asia_schedule(date(2026, 9, 1), date(2026, 9, 30))
    kinds = {r["rule"] for r in rows}
    assert {"cn_cfets_fix", "cn_lpr", "cn_nbs_pmi", "shfe_weekly_inventory", "kr_exports_10d",
            "kr_exports_20d", "kr_kospi200_expiry", "jp_gotobi_fix"} <= kinds
    assert es.relevant(rows, "EURUSD") == []
    assert {r["rule"] for r in es.relevant(rows, "XCUUSD")} == {"shfe_weekly_inventory",
                                                                 "cn_nbs_pmi"}
    assert "jp_gotobi_fix" in {r["rule"] for r in es.relevant(rows, "USDJPY")}
    assert "jp_gotobi_fix" not in {r["rule"] for r in es.relevant(rows, "EURJPY")}
    exp = next(r for r in rows if r["rule"] == "kr_kospi200_expiry")
    assert exp["quadruple_witching"] and exp["impact"] == "high"
    assert exp["event_date"].startswith("2026-09-10T06:20")
    # An FX-calendar row with no currency stays global, exactly as before.
    ff = {"impact": "High", "title": "G20", "event_date": "2026-09-02T12:00:00Z"}
    assert es.relevant([ff], "EURUSD") == [ff]


def test_event_lifecycle_expectation_surprise_revision_decay() -> None:
    rows = [r for r in es.asia_schedule(date(2026, 1, 1), date(2026, 9, 30))
            if r["rule"] == "kr_exports_10d"]
    pts = []
    for i, r in enumerate(rows):
        t = datetime.fromisoformat(r["scheduled_time"]) + timedelta(hours=1)
        pts.append({"d": r["event_date"][:10], "v": float(i % 3), "available_time": t.isoformat(),
                    "vintage_id": f"v{i}"})
    last = rows[-1]
    t_rel = datetime.fromisoformat(last["scheduled_time"]) + timedelta(hours=1)
    pts[-1]["v"] = 9.0
    before = es.event_lifecycle(last, t_rel - timedelta(hours=3), pts)
    assert before["stage"] == es.EXPECTATION and before["value"] is None
    assert before["expected_value"] is not None
    now = t_rel + timedelta(hours=2)
    obj = es.event_lifecycle(last, now, pts)
    assert obj["stage"] == es.SURPRISE_MEASURED and obj["value"] == 9.0
    prior = [p["v"] for p in pts[:-1]][-es.EXPECTATION_N:]
    assert obj["expected_value"] == pytest.approx(sum(prior) / len(prior))
    assert obj["raw_surprise"] == pytest.approx(9.0 - obj["expected_value"])
    assert obj["surprise_z"] is not None and obj["consensus"] is None
    # A revision knowable LATER than `now` is not read at `now` (PIT) ...
    rev = {"d": pts[-1]["d"], "v": 7.5, "available_time": (t_rel + timedelta(hours=10))
           .isoformat(), "vintage_id": "rev"}
    assert es.event_lifecycle(last, now, [*pts, rev])["revision_of"] is None
    # ... and is once it is.
    later = es.event_lifecycle(last, t_rel + timedelta(hours=11), [*pts, rev])
    assert later["stage"] == es.REVISED and later["revision_delta"] == pytest.approx(-1.5)
    gone = es.event_lifecycle(last, t_rel + timedelta(days=30), [*pts, rev])
    assert gone["stage"] == es.DECAYED
    # A rule with no collected sensor never invents a value.
    fix = next(r for r in es.asia_schedule(date(2026, 9, 1), date(2026, 9, 3))
               if r["rule"] == "cn_cfets_fix")
    o = es.event_lifecycle(fix, NOW, [])
    assert o["value"] is None and o["sensor_status"].startswith("UNMEASURED")


def test_event_objects_reach_the_state_vector(world: Path,
                                              monkeypatch: pytest.MonkeyPatch) -> None:
    now = datetime(2026, 9, 21, 4, 0, tzinfo=UTC)
    rep = mse.build_asia_events(now, world / "axes", apply=True)
    assert rep["n_events"] > 0 and (world / "latent" / "asia_events.jsonl").exists()
    doc = json.loads((world / "latent" / "asia_events.json").read_text())
    kr = [o for o in doc["events"] if o["rule"] == "kr_exports_20d"
          and o["scheduled_time"].startswith("2026-09-21")]
    assert kr and kr[0]["value"] is not None and kr[0]["expected_value"] is not None
    import state_vector_build as svb
    monkeypatch.setattr(svb, "ASIA_EVENTS", world / "latent" / "asia_events.json")
    ev, why = svb.event_state(now, ["USDKRW", "EURUSD"])
    assert why == ""
    assert ev["n_asia_rows"] > 0
    assert any(o["event_id"].startswith("kr_exports_20d") for o in
               ev["per_symbol"]["USDKRW"].get("asia_events", []))
    assert "asia_events" not in ev["per_symbol"]["EURUSD"]
    # The ledger keeps stage changes and never duplicates one.
    n = len((world / "latent" / "asia_events.jsonl").read_text().splitlines())
    mse.build_asia_events(now, world / "axes", apply=True)
    assert len((world / "latent" / "asia_events.jsonl").read_text().splitlines()) == n


# ------------------------------------------------------------------------------- cells
def test_every_latent_look_is_charged_even_when_nothing_passes(
        world: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from research import proposer_common as pc
    spec = mse.LATENT_BY_ID["asia_export"]
    ledgers = {spec.id: [{"level": 0.1}] * mse.MIN_CELL_VINTAGES}
    row = {"cell": "USDKRW.exogenous_conditioner.latent_asia_export.level", "symbol": "USDKRW",
           "params": {"signal": "level", "side_when_high": -1}, "dataset": spec.id,
           "t_gross": 0.2, "clears_cost": False, "n_independent": 40}
    monkeypatch.setattr(mse, "direct_latent_cells", lambda s, r, n: ([dict(row)], 4))
    monkeypatch.setattr(mse, "regime_children",
                        lambda specs, root, state: ([], 2, [], {"session_range_breakout": 2}))
    monkeypatch.setattr(pc, "donate", lambda *a, **k: pytest.fail("nothing passed"))
    rep = mse.latent_cells([spec], ledgers, world / "series", {}, NOW, apply=True)
    assert rep["tests_run"] == 6 and rep["proposed_direct"] == 0
    charged = [json.loads(x) for x in (world / "null.jsonl").read_text().splitlines()]
    assert charged[-1]["tests_run"] == 6
    assert charged[-1]["by_family"] == {"exogenous_conditioner": 4, "session_range_breakout": 2}


def test_a_passing_latent_cell_is_donated_with_the_whole_pass_charged(
        world: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from research import proposer_common as pc
    spec = mse.LATENT_BY_ID["asia_export"]
    ledgers = {spec.id: [{"level": 0.1}] * mse.MIN_CELL_VINTAGES}
    row = {"cell": "AUDUSD.exogenous_conditioner.latent_asia_export.level", "symbol": "AUDUSD",
           "params": {"source": "latent_asia_export", "signal": "level",
                      "side_when_high": 1}, "dataset": spec.id,
           "t_gross": 9.0, "clears_cost": True, "n_independent": 400}
    monkeypatch.setattr(mse, "direct_latent_cells", lambda s, r, n: ([dict(row)], 7))
    monkeypatch.setattr(mse, "regime_children", lambda specs, root, state: ([], 0, [], {}))
    sent: list[tuple[str, list[dict[str, Any]], int]] = []
    monkeypatch.setattr(pc, "donate",
                        lambda src, c, n: sent.append((src, c, n)) or Path("intake.json"))
    rep = mse.latent_cells([spec], ledgers, world / "series", {}, NOW, apply=True)
    assert sent and sent[0][0] == mse.LATENT_SOURCE and sent[0][2] == 7
    cand = sent[0][1][0]
    assert cand["family"] == "exogenous_conditioner" and cand["available_time"]
    assert cand["params"]["source"] == "latent_asia_export" and cand["falsifier"]
    assert rep["path"] == "intake.json" and not (world / "null.jsonl").exists()


# ------------------------------------------------------------------------------- transmission
def test_transmission_failures_survive_a_later_success(tmp_path: Path) -> None:
    led = tmp_path / "edges.jsonl"
    fail = {"name": "china_industrial_to_aud", "driver": "AUS200", "target": "AUDUSD",
            "verdict": "REFUTED", "why": "wrong sign", "asia_hours": {"t": -3.4, "lag": 2}}
    ok = {**fail, "verdict": "TRANSMISSION", "why": "present in Asian hours"}
    at.remember([fail], "2026-10-01T00:00:00+00:00", led)
    at.remember([ok], "2026-10-02T00:00:00+00:00", led)
    mem = at.failure_memory(led)["china_industrial_to_aud"]
    assert mem["measured"] == 2 and mem["failed"] == 1 and mem["refuted"] == 1
    assert mem["contradicted"] and mem["last_failure"]["why"] == "wrong sign"
    assert mem["last_held"]["verdict"] == "TRANSMISSION"


def test_transmission_null_pass_is_charged_and_battery_proposes(tmp_path: Path) -> None:
    p = tmp_path / "null.jsonl"
    assert at.charge_null(8, "2026-10-01T00:00:00+00:00", p)
    assert json.loads(p.read_text())["by_family"] == {"lead_lag": 8}
    assert not at.charge_null(0, "x", tmp_path / "none.jsonl")
    from research import batteries
    entry = [e for e in batteries.ORGANS if e.path.endswith("asia_transmission.py")]
    assert entry and "--propose" in entry[0].argv


# ------------------------------------------------------------------- budget: mining never shrinks
class _Clock:
    """A fake monotonic clock: `step` seconds pass on every read, `jump()` moves it on."""

    def __init__(self, step: float = 0.0) -> None:
        self.t, self.step = 1_000.0, step

    def monotonic(self) -> float:
        self.t += self.step
        return self.t

    def jump(self, s: float) -> None:
        self.t += s


@pytest.mark.parametrize("latent_s", [0.0, 140.0, 900.0])
def test_edge_scan_keeps_its_whole_budget_whatever_the_latent_build_costs(
        monkeypatch: pytest.MonkeyPatch, latent_s: float) -> None:
    """The edge scan's deadline is ITS start + budget_s, never shortened by the latent build."""
    import types
    clock = _Clock()
    monkeypatch.setattr(mse, "time", types.SimpleNamespace(monotonic=clock.monotonic))
    seen: dict[str, Any] = {}

    def fake_latent(now: datetime, *, budget_s: float, apply: bool) -> dict[str, Any]:
        seen["latent_budget"] = budget_s
        clock.jump(latent_s)
        return {"datasets": {}}

    def fake_hunt(pairs: list[dict[str, Any]], *, deadline: float, n_perm: int,
                  ) -> tuple[list[Any], list[Any], dict[str, Any]]:
        seen["deadline"], seen["scan_start"] = deadline, clock.t
        return [], [], {"pairs": 1, "measured": 0, "unmeasured": 0, "tests_run": 0,
                        "skipped_budget": 0, "n_perm": n_perm}

    monkeypatch.setattr(mse, "build_latent", fake_latent)
    monkeypatch.setattr(mse, "build_asia_events",
                        lambda now, axes, apply, deadline=None: {"n_events": 0})
    monkeypatch.setattr(mse, "build_blocks", lambda: ({}, {"n_blocks": 0}, {}))
    monkeypatch.setattr(mse, "graph_pairs", lambda: ([{"src": "A", "dst": "B"}], {}))
    monkeypatch.setattr(mse, "hunt_edges", fake_hunt)
    monkeypatch.setattr(mse, "global_factors", lambda blocks: {})
    monkeypatch.setattr(mse, "fred_levels", lambda: {})
    monkeypatch.setattr(mse, "fred_vintages", lambda: {})
    monkeypatch.setattr(mse, "_registry", lambda: {})
    rep = mse.build(budget_s=600.0, apply=False, latent_budget_s=150.0)
    assert seen["latent_budget"] == 150.0
    assert seen["deadline"] == pytest.approx(seen["scan_start"] + 600.0)
    assert rep["latent_budget_s"] == 150.0 and rep["latent_spent_s"] >= latent_s


def test_the_cli_and_the_hourly_leg_carry_the_latent_budget_on_top() -> None:
    from research import hourly_cycle as hc
    src = Path(hc.__file__).read_text("utf-8")
    assert '"--latent-budget-s", "150"' in src
    # The leg's cap sits above scan budget + latent budget, so neither half is killed.
    assert hc.LEG_BUDGET_SEC["macro_state_engine"] >= 600 + 150
    assert mse.LATENT_BUDGET_S == 150.0


def test_the_latent_build_stops_inside_its_own_budget(world: Path,
                                                      monkeypatch: pytest.MonkeyPatch) -> None:
    import types
    clock = _Clock()                            # time passes only when an input is loaded
    monkeypatch.setattr(mse, "time", types.SimpleNamespace(monotonic=clock.monotonic))
    real_load = mse.load_input
    loaded: list[str] = []

    def slow_load(inp: Any, *a: Any) -> Any:    # the first load spends the whole 1 s budget
        loaded.append(inp.id)
        clock.jump(10.0)
        return real_load(inp, *a)

    monkeypatch.setattr(mse, "load_input", slow_load)
    spec0 = mse.LATENT_BY_ID["asia_export"]
    rep = mse.build_latent(NOW, budget_s=1.0, apply=True, cells=False, specs=(spec0,),
                           environ={})
    ds = rep["datasets"]["asia_export"]
    # Input loading is bounded: one input loaded, every later one NAMED as skipped.
    assert loaded == [spec0.inputs[0].id]
    later = [f"asia_export.{i.id}" for i in spec0.inputs[1:]]
    assert rep["skipped_inputs"]["inputs"] == later and rep["skipped_inputs"]["n"] == len(later)
    assert all(r["status"] == "SKIPPED_BUDGET" for r in ds["inputs"][1:])
    assert all(rep["fed"]["datasets"][k]["status"] != "FED" for k in later)
    # ... and the vintage build stops on the same deadline, owing what it did not reach.
    assert ds["new_vintages"] == 0 and ds["release_dates_owed"] > 0
    # Cells past the deadline are named, never screened, and charge nothing.
    spec = mse.LATENT_BY_ID["asia_export"]
    monkeypatch.setattr(mse, "direct_latent_cells",
                        lambda s, r, n: pytest.fail("screened past the latent deadline"))
    monkeypatch.setattr(mse, "regime_children",
                        lambda *a: pytest.fail("children past the latent deadline"))
    cells = mse.latent_cells([spec], {spec.id: [{"level": 0.1}] * mse.MIN_CELL_VINTAGES},
                             world / "series", {}, NOW, apply=False, deadline=0.0)
    assert cells["tests_run"] == 0
    assert "budget" in cells["skipped"][spec.id] and "budget" in cells["skipped"][
        "regime_children"]


# ------------------------------------------------------------------- the dataset rule (D18)
def test_the_latent_artifact_publishes_fed_and_unfed_inputs(world: Path) -> None:
    rep = _run(world)
    intel = json.loads((world / "reports" / "LI.json").read_text())
    fed = intel["fed"]
    assert fed == {**rep["fed"]}
    rows = fed["datasets"]
    ok = rows["asia_export.kr_exports_daily_avg"]
    assert ok["status"] == "FED" and ok["consumed_this_pass"]
    assert ok["last_fed_at"] == NOW.isoformat(timespec="seconds")
    assert ok["census_id"] == "axis:alt_kr_exports_early"
    pend = rows["asia_export.tw_export_orders"]
    assert pend["status"] == "UNFED" and pend["last_fed_at"] is None
    names = {u["dataset"] for u in fed["unfed"]}
    assert "asia_export.tw_export_orders" in names
    assert "asia_export.kr_exports_daily_avg" not in names
    assert fed["unfed_count"] == fed["unfed_datasets"] == len(fed["unfed"]) > 0
    assert fed["datasets_held"] == fed["fed"] + fed["unfed_count"] and fed["target"] == 0
    for u in fed["unfed"]:
        assert set(u) >= {"dataset", "kind", "status", "last_fed_at"}


def test_an_input_that_stops_arriving_keeps_its_last_fed_time_then_goes_stale(
        world: Path) -> None:
    spec = (mse.LATENT_BY_ID["asia_export"],)
    _run(world, specs=spec)
    (world / "axes" / "alt_sg_port_throughput.json").unlink()
    later = NOW + timedelta(hours=6)
    rows = _run(world, now=later, specs=spec)["fed"]["datasets"]
    sg = rows["asia_export.sg_port_teu"]
    assert sg["status"] == "FED" and not sg["consumed_this_pass"]       # inside the 24h window
    assert sg["last_fed_at"] == NOW.isoformat(timespec="seconds")
    fed = _run(world, now=NOW + timedelta(hours=30), specs=spec)["fed"]
    sg = fed["datasets"]["asia_export.sg_port_teu"]
    assert sg["status"] == "STALE" and sg["last_fed_at"] == NOW.isoformat(timespec="seconds")
    assert "asia_export.sg_port_teu" in {u["dataset"] for u in fed["unfed"]}


def test_real_reads_go_to_the_dataset_use_census_under_its_own_ids(
        world: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    import types
    calls: list[tuple[str, dict[str, Any], str]] = []
    fake = types.ModuleType("libs.data.dataset_use")
    fake.record_reads = (  # type: ignore[attr-defined]
        lambda consumer, datasets, *, use, now=None: calls.append(
            (consumer, dict(datasets), use)) or True)
    monkeypatch.setitem(sys.modules, "libs.data.dataset_use", fake)
    import libs.data
    monkeypatch.setattr(libs.data, "dataset_use", fake, raising=False)
    rep = _run(world)
    assert calls and calls[0][0] == mse.FED_CONSUMER and calls[0][2] == "regime_state"
    assert "axis:alt_kr_exports_early" in calls[0][1] and "axis:bis" in calls[0][1]
    assert rep["fed"]["census_record"].startswith("recorded")


def test_bis_terms_are_confirmed_with_evidence_in_the_axis_terms_table() -> None:
    from research import alt_proxies as ap
    # Axis-only: never fetched by alt_proxies, so never a TERMS row (TERMS == BY_ID holds).
    assert "bis_policy_rates" not in ap.TERMS and "bis_policy_rates" not in ap.BY_ID
    assert ap.AXIS_TERMS["bis_policy_rates"][0] == "confirmed"
    assert set(ap.AXIS_TERMS) == set(ap.AXIS_TERMS_EVIDENCE)
    assert all(v[0] in ap.TERMS_VALUES for v in ap.AXIS_TERMS.values())
    ev = ap.AXIS_TERMS_EVIDENCE["bis_policy_rates"]
    assert ev["terms_url"].startswith("https://") and "unrestricted" in ev["terms_quote"]
    assert mse._terms("bis_policy_rates") == "confirmed"
    assert mse._terms("no_such_source") == "unknown_source"
    bis = [i for i in mse.LATENT_BY_ID["asia_funding"].inputs if i.axis == "bis"]
    assert bis and all(i.terms_source == "bis_policy_rates" for i in bis)


def test_a_bis_input_is_blocked_when_its_axis_terms_row_is_absent(
        monkeypatch: pytest.MonkeyPatch) -> None:
    from research import alt_proxies as ap
    monkeypatch.setattr(ap, "AXIS_TERMS", {})
    assert mse._terms("bis_policy_rates") == "unknown_source"


# --------------------------------------------------------------- fed block: timestamps (D18)
def _consumed(fed: bool = False) -> dict[str, dict[str, Any]]:
    inp = mse.LATENT_BY_ID["asia_export"].inputs[0]
    return {f"asia_export.{inp.id}": {"inp": inp, "rec": {"status": "ABSENT"}, "fed": fed}}


def test_a_naive_last_fed_at_is_read_as_utc_and_says_so() -> None:
    key = next(iter(_consumed()))
    naive = (NOW - timedelta(hours=2)).replace(tzinfo=None).isoformat(timespec="seconds")
    got = mse.fed_block(_consumed(), {key: naive}, NOW)        # used to raise TypeError
    row = got["datasets"][key]
    assert row["status"] == "FED" and "UTC" in row["tz_assumed"]
    old = (NOW - timedelta(hours=30)).replace(tzinfo=None).isoformat(timespec="seconds")
    assert mse.fed_block(_consumed(), {key: old}, NOW)["datasets"][key]["status"] == "STALE"


def test_a_future_last_fed_at_is_a_defect_never_fed() -> None:
    key = next(iter(_consumed()))
    for future in ((NOW + timedelta(hours=3)).isoformat(timespec="seconds"),
                   (NOW + timedelta(hours=3)).replace(tzinfo=None).isoformat()):
        got = mse.fed_block(_consumed(), {key: future}, NOW)
        row = got["datasets"][key]
        assert row["status"] == "DEFECT" and "future" in row["defect"]
        assert row["last_fed_at"] is None                      # never carried into state
        assert key in {u["dataset"] for u in got["unfed"]} and got["unfed_count"] == 1


# ------------------------------------------------------- Asia events: bounded by the deadline
def test_the_asia_events_step_is_bounded_by_the_latent_deadline(
        world: Path, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    out, led = tmp_path / "ev.json", tmp_path / "ev.jsonl"
    rep = mse.build_asia_events(NOW, world / "axes", True, out_path=out, ledger_path=led,
                                deadline=0.0)
    assert rep["status"].startswith("SKIPPED_BUDGET") and rep["sensors_not_reached"]
    assert not out.exists() and not led.exists()               # nothing partial published
    # build() never starts the step once the latent build has spent its budget.
    import types
    clock = _Clock()
    monkeypatch.setattr(mse, "time", types.SimpleNamespace(monotonic=clock.monotonic))

    def spent_latent(now: datetime, *, budget_s: float, apply: bool) -> dict[str, Any]:
        clock.jump(budget_s + 1.0)
        return {"datasets": {}}

    monkeypatch.setattr(mse, "build_latent", spent_latent)
    monkeypatch.setattr(mse, "build_asia_events",
                        lambda *a, **k: pytest.fail("Asia events ran past the latent deadline"))
    monkeypatch.setattr(mse, "build_blocks", lambda: ({}, {"n_blocks": 0}, {}))
    monkeypatch.setattr(mse, "graph_pairs", lambda: ([], {}))
    monkeypatch.setattr(mse, "global_factors", lambda blocks: {})
    monkeypatch.setattr(mse, "fred_levels", lambda: {})
    monkeypatch.setattr(mse, "fred_vintages", lambda: {})
    monkeypatch.setattr(mse, "_registry", lambda: {})
    got = mse.build(budget_s=600.0, apply=False, latent_budget_s=150.0)
    assert got["asia_events"]["status"].startswith("SKIPPED_BUDGET")
