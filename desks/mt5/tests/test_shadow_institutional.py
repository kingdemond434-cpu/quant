"""The shadow-institutional stack on planted ground: every claim measured, nothing touched.

Nothing here reads the box. The axis store, the universe, the fixtures and the report all live in
`tmp_path`, and the canonical registry is a fresh sqlite file whose backup points at a path that
does not exist, so `connect()` builds an empty schema rather than restoring the moat copy.

The tests that matter most are the REFUSALS. A guard that fetches a source whose terms forbid
machine use is not a bug the next session finds in a report -- it is the desk breaking a promise
it made in writing, so `test_forbidden_endpoint_is_never_fetched` monkeypatches `urlopen` to a
function that FAILS THE TEST IF IT IS CALLED.
"""
from __future__ import annotations

import json
import sys
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any

import numpy as np
import pytest

_DESK = Path(__file__).resolve().parents[1]
for _p in (str(_DESK.parent.parent), str(_DESK), str(_DESK / "research")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import shadow_institutional as si  # noqa: E402

from libs.moat import registry as R  # noqa: E402

NOW = datetime(2026, 9, 17, 12, 0, tzinfo=UTC)


def _days(n: int, start: str = "2024-01-01") -> list[str]:
    d0 = date.fromisoformat(start)
    return [(d0 + timedelta(days=i)).isoformat() for i in range(n)]


def _series(n: int, *, slope: float = 0.0, noise: float = 0.0, seed: int = 7
            ) -> list[tuple[str, float]]:
    rng = np.random.default_rng(seed)
    return [(d, slope * i + (noise * float(rng.normal()) if noise else 0.0))
            for i, d in enumerate(_days(n))]


@pytest.fixture
def tree(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> dict[str, Path]:
    """An empty synthetic desk: axes, universe, fixtures, report, and an empty registry."""
    paths = {"axes": tmp_path / "data" / "axes",
             "universe": tmp_path / "data" / "universe",
             "fixtures": tmp_path / "data" / "shadow_fixtures",
             "report": tmp_path / "reports" / "SHADOW_INSTITUTIONAL.json",
             "desk": tmp_path}
    for p in ("axes", "universe", "fixtures"):
        paths[p].mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(si, "AXES", paths["axes"])
    monkeypatch.setattr(si, "UNIVERSE", paths["universe"])
    monkeypatch.setattr(si, "FIXTURES", paths["fixtures"])
    monkeypatch.setattr(si, "OUT", paths["report"])
    monkeypatch.setattr(R, "BACKUP", tmp_path / "no_backup")
    R.set_path(tmp_path / "alpha_registry.sqlite")
    yield paths
    R.set_path(None)


# ------------------------------------------------------------------------------ the sensor table
def test_declared_sensor_table_is_a_sensor_table() -> None:
    every = [s for rows in si.ENSEMBLES.values() for s in rows] + list(si.CRYPTO_SENSORS)
    assert si.check_sensors(every) == []
    assert len(si.ENSEMBLES) == 5
    for latent, rows in si.ENSEMBLES.items():
        assert len(rows) >= si.MIN_SENSORS, latent
        assert all(s.latent == latent for s in rows)


def test_every_crypto_sensor_names_mt5_consumers() -> None:
    """The mandate line 'informs an MT5 instrument', enforced by the table rather than by hope."""
    for s in si.CRYPTO_SENSORS:
        assert s.consumers, s.sensor_id
        assert all(c in si.MT5_TARGETS for c in s.consumers), s.sensor_id
    # ... and the checker actually refuses one that does not.
    rogue = si.Sensor(sensor_id="rogue", latent="global_risk_appetite", what="btc for its own sake",
                      fetch_class="public_endpoint", source="x", cadence="5min", pit_lag_days=0.0,
                      machine_use_allowed=True, licence="public", sign=1, consumers=("BTCUSD",),
                      url="https://example.invalid/x")
    problems = si.check_sensors([rogue])
    assert any("not MT5 targets" in p for p in problems)


def test_terms_refusal_is_declared_and_cannot_be_a_fetch_class() -> None:
    refused = [s for s in si.CRYPTO_SENSORS if not s.machine_use_allowed]
    assert [s.sensor_id for s in refused] == ["cboe_delayed_surface"]
    assert refused[0].fetch_class == si.UNMEASURED
    assert refused[0].licence
    bad = si.Sensor(sensor_id="bad", latent="global_risk_appetite", what="x",
                    fetch_class="public_endpoint", source="x", cadence="daily", pit_lag_days=0.0,
                    machine_use_allowed=False, licence="terms forbid it", sign=1,
                    consumers=("US500",), url="https://example.invalid/x")
    assert any("may not be a fetch class" in p for p in si.check_sensors([bad]))


def test_forbidden_endpoint_is_never_fetched(tree: dict[str, Path],
                                             monkeypatch: pytest.MonkeyPatch) -> None:
    def _boom(*_a: Any, **_k: Any) -> Any:
        raise AssertionError("the guard opened a socket for a source whose terms forbid it")

    monkeypatch.setattr(si.urllib.request, "urlopen", _boom)
    guard = si.Guard(budget_s=5.0, no_fetch=False, fixtures=tree["fixtures"])
    cboe = next(s for s in si.CRYPTO_SENSORS if not s.machine_use_allowed)
    payload, why = guard.get(cboe)
    assert payload is None
    assert why.startswith("REFUSED by terms")
    assert guard.refused == [{"sensor": cboe.sensor_id, "why": why}]
    assert guard.calls == 0


def test_guard_reads_a_fixture_in_no_fetch_mode(tree: dict[str, Path]) -> None:
    sensor = next(s for s in si.CRYPTO_SENSORS if s.sensor_id == "deribit_atm_iv")
    (tree["fixtures"] / "deribit_atm_iv.json").write_text(
        json.dumps({"result": [{"d": "2026-09-16", "mark": 0.41}]}), encoding="utf-8")
    guard = si.Guard(no_fetch=True, fixtures=tree["fixtures"])
    payload, why = guard.get(sensor)
    assert why.startswith("fixture")
    assert si.parse_points(payload) == [("2026-09-16", 0.41)]
    missing, why2 = guard.get(next(s for s in si.CRYPTO_SENSORS if s.sensor_id == "btc_ofi"))
    assert missing is None and "no fixture" in why2


# -------------------------------------------------------------------------------- the fusion
def test_planted_sensors_fuse_with_an_uncertainty_band() -> None:
    readings = {"a": _series(120, slope=1.0), "b": _series(120, slope=1.0),
                "c": [(d, -v) for d, v in _series(120, slope=1.0)]}
    signs = {"a": 1, "b": 1, "c": -1}
    est = si.fuse("planted", readings, signs, declared=3)
    assert est.status == "MEASURED"
    assert est.n_sensors_used == 3
    assert sum(est.weights.values()) == pytest.approx(1.0, abs=1e-5)   # published to 6 dp
    # all three agree once the sign is applied, so the band is ~0 and n_present is complete
    assert est.points[-1]["n_present"] == 3
    assert est.points[-1]["sd"] == pytest.approx(0.0, abs=1e-9)
    assert est.points[-1]["v"] > est.points[0]["v"]


def test_a_disagreeing_sensor_widens_the_band() -> None:
    agree = si.fuse("agree", {"a": _series(120, slope=1.0), "b": _series(120, slope=1.0)},
                    {"a": 1, "b": 1})
    fight = si.fuse("fight", {"a": _series(120, slope=1.0), "b": _series(120, slope=1.0)},
                    {"a": 1, "b": -1})
    assert agree.points[-1]["sd"] < fight.points[-1]["sd"]


def test_one_sensor_is_unmeasured_not_a_latent() -> None:
    est = si.fuse("thin", {"a": _series(120, slope=1.0)}, {"a": 1}, declared=8)
    assert est.status == si.UNMEASURED
    assert est.n_sensors_used == 1
    assert "cannot disagree with itself" in est.equal_weight_reason
    assert est.points == []


def test_lead_lag_weight_prefers_the_sensor_that_leads() -> None:
    rng = np.random.default_rng(3)
    n = 400
    days = _days(n)
    drive = np.cumsum(rng.normal(size=n))
    target = list(zip(days, (float(v) for v in drive), strict=False))
    lead = list(zip(days, (float(v) for v in np.diff(drive, append=drive[-1])), strict=False))
    noise = list(zip(days, (float(v) for v in rng.normal(size=n)), strict=False))
    w_lead, _lag, n_lead = si.lead_lag_weight(lead, target)
    w_noise, _l2, _n2 = si.lead_lag_weight(noise, target)
    assert n_lead == n
    assert w_lead > w_noise


def test_short_overlap_falls_back_to_equal_weights_and_says_so() -> None:
    est = si.fuse("thin", {"a": _series(80, slope=1.0), "b": _series(80, slope=-1.0)},
                  {"a": 1, "b": -1}, target=_series(10, slope=1.0))
    assert est.status == "MEASURED"
    assert set(est.weights.values()) == {0.5}
    assert "equal weights, declared" in est.equal_weight_reason


def test_stored_latent_carries_pit_stamps_and_is_append_only(tree: dict[str, Path]) -> None:
    est = si.fuse("china_activity", {"a": _series(60, slope=1.0), "b": _series(60, slope=1.0)},
                  {"a": 1, "b": 1}, lag_days=20.0)
    doc = si.store_latent(tree["axes"], est, dry_run=False)
    path = tree["axes"] / "shadow_china_activity.json"
    assert path.exists()
    point = doc["points"][0]
    for field in ("period_time", "publication_time", "available_time", "knowable_at",
                  "vintage_id", "sd", "n_present"):
        assert field in point, field
    assert point["available_time"][:10] > point["period_time"][:10]  # the 20-day lag is applied
    again = si.store_latent(tree["axes"], est, dry_run=False)
    assert again["added"] == 0
    assert again["n"] == doc["n"]


def test_dry_run_writes_nothing(tree: dict[str, Path]) -> None:
    est = si.fuse("usd_liquidity", {"a": _series(60, slope=1.0), "b": _series(60, slope=1.0)},
                  {"a": 1, "b": 1})
    si.store_latent(tree["axes"], est, dry_run=True)
    assert not (tree["axes"] / "shadow_usd_liquidity.json").exists()


def test_axis_reader_handles_all_three_shapes_on_this_tree(tree: dict[str, Path]) -> None:
    (tree["axes"] / "fredlike.json").write_text(json.dumps(
        {"series": {"X": {"points": [{"d": "2026-01-01", "v": 1.0},
                                     {"d": "2026-01-02", "v": 2.0}]}}}), encoding="utf-8")
    (tree["axes"] / "krlike.json").write_text(json.dumps(
        {"points": [{"knowable_at": "2026-01-03", "value": 3.0, "v": 3.0}]}), encoding="utf-8")
    (tree["axes"] / "cotlike.json").write_text(json.dumps(
        {"rows": [{"symbol": "XAUUSD", "knowable_at": "2026-01-01", "net_pct_oi": 0.4},
                  {"symbol": "AUDUSD", "knowable_at": "2026-01-01", "net_pct_oi": 0.2},
                  {"symbol": "XAUUSD", "knowable_at": "2026-01-08", "net_pct_oi": 0.6}]}),
        encoding="utf-8")
    assert si.read_axis_points(tree["axes"], "fredlike") == [("2026-01-01", 1.0),
                                                             ("2026-01-02", 2.0)]
    assert si.read_axis_points(tree["axes"], "krlike") == [("2026-01-03", 3.0)]
    # the flat rows shape: the field averages across markets, and a symbol prefix selects one
    assert si.read_axis_points(tree["axes"], "cotlike", "net_pct_oi") == [
        ("2026-01-01", pytest.approx(0.3)), ("2026-01-08", pytest.approx(0.6))]
    assert si.read_axis_points(tree["axes"], "cotlike", "XAUUSD.net_pct_oi") == [
        ("2026-01-01", 0.4), ("2026-01-08", 0.6)]
    assert si.read_axis_points(tree["axes"], "absent") == []


# --------------------------------------------------------------------- the disagreement dataset
def test_disagreement_is_built_from_planted_legs() -> None:
    doc = si.disagreement({"retail": _series(60, slope=1.0),
                           "institutional": _series(60, slope=-1.0),
                           "macro": _series(60, slope=1.0)})
    assert doc["status"] == "MEASURED"
    assert doc["legs_present"] == ["institutional", "macro", "retail"]
    missing = {row["leg"] for row in doc["legs_unmeasured"]}
    assert missing == {"derivatives", "options", "news"}
    last = doc["points"][-1]
    assert last["n_legs"] == 3
    assert set(last["legs"]) == {"retail", "institutional", "macro"}
    assert last["v"] > 0.0          # retail and the COT are on opposite sides: real disagreement
    assert last["max_gap"] >= last["v"]


def test_agreeing_legs_disagree_less_than_fighting_ones() -> None:
    same = si.disagreement({"retail": _series(60, slope=1.0),
                            "institutional": _series(60, slope=1.0)})
    fight = si.disagreement({"retail": _series(60, slope=1.0),
                             "institutional": _series(60, slope=-1.0)})
    assert same["points"][-1]["v"] < fight["points"][-1]["v"]


def test_one_leg_is_not_a_disagreement() -> None:
    doc = si.disagreement({"retail": _series(60, slope=1.0)})
    assert doc["points"] == []
    assert doc["status"] == si.UNMEASURED


# ------------------------------------------------------------------------------- vault and gaps
def test_vault_manifest_measures_depth_and_names_what_is_absent(tmp_path: Path) -> None:
    (tmp_path / "data").mkdir()
    corpus = tmp_path / "data" / "fill_corpus.jsonl"
    corpus.write_text("\n".join(json.dumps({"decided_at": f"2026-0{m}-01T00:00:00+00:00"})
                                for m in (1, 2, 3)), encoding="utf-8")
    ticks = tmp_path / "data" / "tape" / "ticks" / "XAUUSD"
    ticks.mkdir(parents=True)
    for day in ("2026-09-01", "2026-09-10"):
        (ticks / f"{day}.parquet").write_bytes(b"x")
    doc = si.vault_manifest(tmp_path)
    by = {r["kind"]: r for r in doc["streams"]}
    assert by["own_fills"]["status"] == "ARCHIVING"
    assert by["own_fills"]["first"] == "2026-01-01"
    assert by["own_fills"]["depth_days"] == 60
    assert by["broker_tick_tape"]["depth_days"] == 10
    assert by["broker_tick_tape"]["n_symbols"] == 1
    assert by["own_deals"]["status"] == si.UNMEASURED
    assert "not on this box" in by["own_deals"]["why"]
    assert doc["deepest_days"] == 60
    assert doc["n_archiving"] == 2


def test_gap_map_has_a_measured_status_on_every_row(tmp_path: Path) -> None:
    latents = {"china_activity": si.fuse("china_activity",
                                         {"a": _series(60, slope=1.0), "b": _series(60, slope=1.0)},
                                         {"a": 1, "b": 1}, declared=8),
               "usd_liquidity": si.fuse("usd_liquidity", {"a": _series(60, slope=1.0)},
                                        {"a": 1}, declared=8),
               "industrial_cycle": si.fuse("industrial_cycle", {}, {}, declared=6),
               "retail_crowding": si.fuse("retail_crowding", {}, {}, declared=7),
               "global_risk_appetite": si.fuse("global_risk_appetite", {}, {}, declared=7)}
    vault = si.vault_manifest(tmp_path)
    rows = si.gap_map(latents, vault,
                      [s for v in si.ENSEMBLES.values() for s in v] + list(si.CRYPTO_SENSORS))
    assert len(rows) == len(si.GAP_MAP)
    assert all(r["status"] for r in rows)
    by = {r["capability"]: r for r in rows}
    # PARTIAL, not SHADOWED: china_activity is fused from two planted sensors, usd_liquidity has
    # one and industrial_cycle none, so two thirds of this capability has no proxy standing in.
    macro = by["proprietary macro feed"]
    assert macro["status"] == "PARTIAL"
    assert macro["detail"]["below_sensor_floor"] == ["industrial_cycle", "usd_liquidity"]
    assert macro["detail"]["latents"]["china_activity"] == 2
    assert "usd_liquidity" in macro["missing"]
    # SHADOWED means every latent the row names is actually estimated here
    alt = by["private alt data (satellite counts, card panels)"]
    assert alt["status"] == "PARTIAL"           # china_activity yes, industrial_cycle no
    assert alt["detail"]["below_sensor_floor"] == ["industrial_cycle"]
    dealer = by["dealer positioning / prime-broker flow"]
    assert dealer["status"] == si.UNMEASURED    # retail_crowding has no sensor on this tree
    assert "retail_crowding" in dealer["missing"]
    assert by["colocation / sub-millisecond execution"]["status"] == "CANNOT_REPRODUCE"
    assert by["satellite imagery vendor"]["status"] == "DECLARED_ONLY"
    assert by["decades of clean history"]["status"] == si.UNMEASURED   # empty tmp tree
    options = by["options surface (vendor)"]
    assert options["detail"]["deribit_sensors_declared"] >= 5
    assert "cboe_delayed_surface" in options["detail"]["refused_for_terms"]
    # every row that is not fully shadowed NAMES what is missing
    for r in rows:
        if r["status"] in (si.UNMEASURED, "PARTIAL", "DECLARED_ONLY"):
            assert r.get("missing"), r["capability"]


def test_gap_map_says_shadowed_only_when_every_named_latent_is_measured(tmp_path: Path) -> None:
    def _fused() -> si.LatentEstimate:
        return si.fuse("x", {"a": _series(60, slope=1.0), "b": _series(60, slope=1.0)},
                       {"a": 1, "b": 1}, declared=8)

    latents = {name: _fused() for name in si.ENSEMBLES}
    rows = {r["capability"]: r for r in si.gap_map(latents, si.vault_manifest(tmp_path), [])}
    assert rows["proprietary macro feed"]["status"] == "SHADOWED"
    assert "missing" not in rows["proprietary macro feed"]
    assert rows["dealer positioning / prime-broker flow"]["status"] == "SHADOWED"


# -------------------------------------------------------------------------------- discoveries
def test_discoveries_are_recorded_once_per_target_and_horizon(tree: dict[str, Path]) -> None:
    est = si.fuse("china_activity", {"a": _series(60, slope=1.0), "b": _series(60, slope=1.0)},
                  {"a": 1, "b": 1}, declared=8)
    conn = R.connect()
    try:
        first = si.record_discoveries({"china_activity": est}, conn=conn, dry_run=False,
                                      targets=("AUDUSD", "USDCNH"), horizons=("1d", "5d"))
        assert first["seen"] == 4
        assert first["recorded"] == 4
        rows = R.discoveries(conn=conn)
        assert len(rows) == 4
        assert {r["generator"] for r in rows} == {"shadow:china_activity"}
        assert {json.loads(r["assets_json"])[0] for r in rows} == {"AUDUSD", "USDCNH"}
        again = si.record_discoveries({"china_activity": est}, conn=conn, dry_run=False,
                                      targets=("AUDUSD", "USDCNH"), horizons=("1d", "5d"))
        assert again["seen"] == 4
        assert again["recorded"] == 0
        assert len(R.discoveries(conn=conn)) == 4
    finally:
        conn.close()


def test_discovery_dry_run_records_nothing(tree: dict[str, Path]) -> None:
    est = si.fuse("china_activity", {"a": _series(60, slope=1.0), "b": _series(60, slope=1.0)},
                  {"a": 1, "b": 1}, declared=8)
    out = si.record_discoveries({"china_activity": est}, dry_run=True, targets=("AUDUSD",),
                                horizons=("1d",))
    assert out["seen"] == 1 and out["recorded"] == 0
    conn = R.connect()
    try:
        assert R.discoveries(conn=conn) == []
    finally:
        conn.close()


# ------------------------------------------------------------------------------------ the pass
def test_whole_pass_on_a_planted_tree_writes_axes_and_a_report(tree: dict[str, Path]) -> None:
    (tree["axes"] / "fred.json").write_text(json.dumps(
        {"series": {"VIXCLS": {"points": [{"d": d, "v": float(i % 7)}
                                          for i, d in enumerate(_days(400))]},
                    "BAMLH0A0HYM2": {"points": [{"d": d, "v": float(i % 5)}
                                                for i, d in enumerate(_days(400))]},
                    "T10Y2Y": {"points": [{"d": d, "v": float(i % 3)}
                                          for i, d in enumerate(_days(400))]}}}),
        encoding="utf-8")
    doc = si.run(no_fetch=True, dry_run=False, desk=tree["desk"], axes=tree["axes"],
                 universe=tree["universe"], fixtures=tree["fixtures"],
                 report_path=tree["report"])
    assert doc["sensor_problems"] == []
    assert tree["report"].exists()
    risk = next(r for r in doc["ensembles"] if r["latent"] == "global_risk_appetite")
    assert risk["status"] == "MEASURED"
    assert risk["n_sensors_used"] == 3
    assert (tree["axes"] / "shadow_global_risk_appetite.json").exists()
    # every other latent is UNMEASURED BY NAME on a tree with nothing planted for it
    china = next(r for r in doc["ensembles"] if r["latent"] == "china_activity")
    assert china["status"] == si.UNMEASURED
    assert china["unmeasured"]
    assert doc["sensor_counts"][si.REFUSED] == len(
        [s for rows in si.ENSEMBLES.values() for s in rows
         if not s.machine_use_allowed] + [s for s in si.CRYPTO_SENSORS
                                          if not s.machine_use_allowed])
    assert doc["discoveries"]["seen"] > 0
    assert doc["gap_map"] and all(r["status"] for r in doc["gap_map"])


def test_whole_pass_dry_run_writes_nothing(tree: dict[str, Path]) -> None:
    doc = si.run(no_fetch=True, dry_run=True, desk=tree["desk"], axes=tree["axes"],
                 universe=tree["universe"], fixtures=tree["fixtures"],
                 report_path=tree["report"])
    assert doc["dry_run"] is True
    assert not tree["report"].exists()
    assert list(tree["axes"].glob("shadow_*.json")) == []
