"""The world factory: one hourly account of every source organ, and the clock the media miners lacked."""
from __future__ import annotations

import json
import re
import sqlite3
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

DESK = Path(__file__).resolve().parents[1]
ROOT = DESK.parents[1]
for _p in (str(ROOT), str(DESK), str(DESK / "research")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from research import world_factory as wf  # noqa: E402

NOW = datetime(2026, 9, 30, 12, 0, tzinfo=UTC)
ROSTER = json.loads((DESK / "data" / "world_factory_sources.json").read_text("utf-8"))


def _redirect(monkeypatch, tmp_path: Path) -> dict[str, Path]:
    paths = {
        "COMPUTE_LEDGER": tmp_path / "compute_ledger.jsonl",
        "FETCH_RUNS": tmp_path / "alt_fetch_runs.jsonl",
        "COMPILED": tmp_path / "miner_candidates.json",
        "REGISTRY": tmp_path / "alpha_registry.sqlite",
        "RUNS": tmp_path / "world_factory_runs.jsonl",
        "CURSOR": tmp_path / "world_factory_cursor.json",
        "REPORT": tmp_path / "WORLD_FACTORY.json",
    }
    for k, v in paths.items():
        monkeypatch.setattr(wf, k, v)
    intel = (tmp_path / "intel_desk", tmp_path / "intel_root")
    monkeypatch.setattr(wf, "INTEL_ROOTS", intel)
    paths["INTEL"] = intel[0]
    return paths


# ------------------------------------------------------------------------------------ roster
def test_media_units_are_exactly_the_run_all_miners_roster_plus_the_seed_sweep() -> None:
    src = (DESK / "side_channels" / "run_all_miners.py").read_text("utf-8")
    block = src.split("ALL_MINERS = [", 1)[1].split("]", 1)[0]
    names = set(re.findall(r'\("([a-z0-9_]+)",', block))
    units = {u["name"] for u in ROSTER["media_units"]}
    assert names <= units, sorted(names - units)
    assert "seed_miners" in units
    for u in ROSTER["media_units"]:
        assert (DESK / "side_channels" / f"{u['module']}.py").exists(), u["module"]
        assert u.get("licence") and u.get("seats") and u.get("timeout_s")


def test_every_source_names_a_licence_and_an_organ_or_says_why_it_is_missing() -> None:
    for s in ROSTER["sources"]:
        assert s.get("licence"), s["id"]
        if not (ROOT / s["organ"]).exists():
            assert "NOT merged" in str((s.get("clock") or {}).get("note")), s["id"]


def test_the_roster_hard_codes_no_forest() -> None:
    assert not [s for s in ROSTER["sources"] if s.get("kind") == "forest"]
    ids = {s["id"] for s in wf.forest_sources()}
    assert {"forest_china", "forest_japan", "forest_africa", "forest_latam"} <= ids


# ------------------------------------------------------------------------------------ yields
def test_seat_yield_counts_rows_and_donations_and_absence_is_unmeasured(monkeypatch,
                                                                       tmp_path) -> None:
    p = _redirect(monkeypatch, tmp_path)
    seat = p["INTEL"] / "event_surprise"
    seat.mkdir(parents=True)
    (seat / "discoveries_1.json").write_text(json.dumps(
        {"source": "event_surprise", "discoveries": [{}, {}, {}], "counts": {"donated": 3}}))
    (seat / "discoveries_2.json").write_text(json.dumps([{"a": 1}, {"a": 2}]))
    old = seat / "discoveries_0.json"
    old.write_text(json.dumps([{"x": 1}]))
    import os
    t = (NOW - timedelta(days=3)).timestamp()
    os.utime(old, (t, t))
    since = datetime.now(tz=UTC) - timedelta(hours=24)
    got = wf.seat_yield(["event_surprise"], since)
    assert got["files"] == 2 and got["rows"] == 5 and got["donated"] == 3
    none = wf.seat_yield(["no_such_seat"], since)
    assert none["rows"] == wf.UNMEASURED and none["donated"] == wf.UNMEASURED
    bare = p["INTEL"] / "earnings"
    bare.mkdir()
    (bare / "discoveries_x.json").write_text(json.dumps([{"t": 1}]))
    b = wf.seat_yield(["earnings"], since)
    assert b["rows"] == 1 and b["donated"] == wf.UNMEASURED     # bare rows carry no counter


def test_leg_runs_counts_timeouts_and_ignores_rows_outside_the_window(tmp_path) -> None:
    led = tmp_path / "cl.jsonl"
    rows = [{"at": (NOW - timedelta(hours=1)).isoformat(), "run": "compile_candidates",
             "outcome": "TIMEOUT", "wall_s": 900},
            {"at": (NOW - timedelta(hours=2)).isoformat(), "run": "world_crawler",
             "outcome": "ok", "wall_s": 10},
            {"at": (NOW - timedelta(days=3)).isoformat(), "run": "world_crawler",
             "outcome": "ok", "wall_s": 10}]
    led.write_text("\n".join(json.dumps(r) for r in rows) + "\n")
    got = wf.leg_runs(NOW - timedelta(hours=24), led)
    assert got["compile_candidates"]["timeouts"] == 1 and got["compile_candidates"]["ok"] == 0
    assert got["world_crawler"]["runs"] == 1
    assert wf.leg_runs(NOW, tmp_path / "absent.jsonl") is None


def test_registry_yield_is_read_only_and_groups_by_generator(tmp_path) -> None:
    db = tmp_path / "r.sqlite"
    c = sqlite3.connect(db)
    c.execute("CREATE TABLE research_candidates (id TEXT, created_at TEXT, generator TEXT, "
              "judged_at TEXT)")
    recent = (NOW - timedelta(hours=2)).isoformat(timespec="seconds")
    old = (NOW - timedelta(days=5)).isoformat(timespec="seconds")
    c.executemany("INSERT INTO research_candidates VALUES (?,?,?,?)", [
        ("a", recent, "forest_china", None), ("b", old, "forest_china", old),
        ("c", recent, "event_surprise", None)])
    c.commit()
    c.close()
    got = wf.registry_yield(NOW - timedelta(hours=24), db)
    assert got["status"] == "MEASURED"
    assert got["by_generator"]["forest_china"] == {"total": 2, "born_in_window": 1, "judged": 1}
    assert wf.registry_yield(NOW, tmp_path / "none.sqlite")["status"] == wf.UNMEASURED


# ------------------------------------------------------------------------------------ measure
def test_measure_with_no_inputs_says_unmeasured_never_zero_and_names_the_holes(monkeypatch,
                                                                              tmp_path) -> None:
    _redirect(monkeypatch, tmp_path)
    doc = wf.measure(NOW)
    assert doc["n_sources"] >= len(ROSTER["sources"]) + len(ROSTER["media_units"]) + 17
    assert doc["inputs"]["compute_ledger"] == wf.UNMEASURED
    assert doc["inputs"]["registry"] == wf.UNMEASURED
    by = {r["id"]: r for r in doc["sources"]}
    assert by["world_crawler"]["cells_reaching_docket"] == wf.UNMEASURED
    assert by["world_crawler"]["ran"]["status"] == wf.UNMEASURED
    holes = {(h["source"], h["hole"]) for h in doc["holes"]}
    assert ("world_dataset_hunter", "ORGAN_NOT_ON_THIS_TREE") in holes or \
        (ROOT / "desks/mt5/research/world_dataset_hunter.py").exists()
    assert ("mass_screen", "ORGAN_NOT_ON_THIS_TREE") in holes or \
        (ROOT / "desks/mt5/research/mass_screen.py").exists()
    # coverage is MEASURED against the grounds file, per forest
    cov = by["forest_europe"]["coverage"]
    assert "ch" in cov["regions_with_grounds"]
    assert doc["coverage"]["n_regions"] >= 90 and doc["coverage"]["n_languages"] >= 24


def test_measure_joins_ledger_seats_compiler_and_registry_per_source(monkeypatch,
                                                                     tmp_path) -> None:
    p = _redirect(monkeypatch, tmp_path)
    now = datetime.now(tz=UTC)
    p["COMPUTE_LEDGER"].write_text("\n".join(json.dumps(r) for r in [
        {"at": now.isoformat(), "run": "event_surprise", "outcome": "ok", "wall_s": 5},
        {"at": now.isoformat(), "run": "compile_candidates", "outcome": "TIMEOUT",
         "wall_s": 900}]) + "\n")
    seat = p["INTEL"] / "event_surprise"
    seat.mkdir(parents=True)
    (seat / "discoveries_1.json").write_text(json.dumps(
        {"discoveries": [{}, {}], "counts": {"donated": 2}}))
    p["COMPILED"].write_text(json.dumps({"compiled_at": now.isoformat(), "per_source": {
        "event_surprise": {"rows": 2, "candidates": 8, "deepening": 0}}}))
    c = sqlite3.connect(p["REGISTRY"])
    c.execute("CREATE TABLE research_candidates (id TEXT, created_at TEXT, generator TEXT, "
              "judged_at TEXT)")
    c.execute("INSERT INTO research_candidates VALUES ('x', ?, 'event_surprise', NULL)",
              (now.isoformat(timespec="seconds"),))
    c.commit()
    c.close()
    doc = wf.measure(now)
    r = {x["id"]: x for x in doc["sources"]}["event_surprise"]
    assert r["ran"]["runs"] == 1 and r["ran"]["ok"] == 1
    assert r["hypotheses_minted"] == 2 and r["cells_donated_contract"] == 2
    assert r["cells_compiled"] == 8 and r["cells_donated"] == 10
    assert r["cells_reaching_docket"] == 1
    holes = {(h["source"], h["hole"]) for h in doc["holes"]}
    assert ("miner_candidate_compiler", "TIMES_OUT_EVERY_PASS") in holes
    out = wf.write(doc)
    assert json.loads(out.read_text("utf-8"))["n_sources"] == doc["n_sources"]


# ------------------------------------------------------------------------------------ mining
def test_mine_runs_never_run_units_first_and_defers_the_rest_to_the_next_pass(monkeypatch,
                                                                             tmp_path) -> None:
    p = _redirect(monkeypatch, tmp_path)
    p["CURSOR"].write_text(json.dumps({"central_bank": "2026-09-30T10:00:00+00:00"}))
    calls: list[str] = []

    def fake(unit, timeout):
        calls.append(unit["name"])
        return {"status": "ok", "rows": 4, "seconds": 1.0}

    # budget for two units only: each unit needs min(timeout, 60) s plus the reserve
    ticks = iter(range(0, 10_000, 100))
    monkeypatch.setattr(wf.time, "monotonic", lambda: float(next(ticks)))
    doc = wf.mine(330.0, runner=fake)
    assert calls and calls[0] != "central_bank"          # the run unit waits behind never-run
    assert doc["deferred"]
    runs = [json.loads(x) for x in p["RUNS"].read_text().splitlines()]
    assert [r["unit"] for r in runs] == calls and all(r["rows"] == 4 for r in runs)
    cur = json.loads(p["CURSOR"].read_text())
    assert set(calls) <= set(cur)
    ur = wf._unit_runs(datetime.now(tz=UTC) - timedelta(hours=1))
    assert ur[calls[0]]["rows"] == 4


def test_order_units_is_least_recently_run_first() -> None:
    units = [{"name": "a"}, {"name": "b"}, {"name": "c"}]
    cur = {"a": "2026-09-30T11:00:00+00:00", "c": "2026-09-30T09:00:00+00:00"}
    assert [u["name"] for u in wf.order_units(units, cur)] == ["b", "c", "a"]


# ------------------------------------------------------------------------------------ wiring
def test_both_legs_are_clocked_budgeted_departmented_and_layered() -> None:
    from libs.research import layers
    cycle = (DESK / "research" / "hourly_cycle.py").read_text(encoding="utf-8")
    assert '_costed("world_factory"' in cycle and '_costed("world_media_miners"' in cycle
    assert '"world_factory": wfy' in cycle and '"world_media_miners": wmm' in cycle
    import hourly_cycle as hc
    assert "world_factory" in hc.CORE_LEGS
    assert hc.department_of("world_media_miners") == "intel"
    assert hc.LEG_BUDGET_SEC["world_media_miners"] > 1400
    assert hc.LEG_BUDGET_SEC["world_factory"] >= 120
    assert layers.LEG_LAYER["world_factory"] == "meta"
    assert layers.LEG_LAYER["world_media_miners"] == "information"


def test_every_new_ground_names_its_licence_and_its_region_is_indexed() -> None:
    src = json.loads((DESK / "data" / "deep_forest_sources.json").read_text("utf-8"))
    added = [g for g in src["grounds"] if str(g.get("added", "")).startswith("2026-09-30")]
    assert len(added) >= 90
    for g in added:
        assert g.get("licence") and g["region"] in src["regions"]


def test_forest_country_coverage_only_ratchets_up() -> None:
    """Floors ratchet UP only (L1.50): 105 forest countries had a ground on 2026-09-30."""
    g = wf.grounds_index()
    served = sum(len(wf.forest_coverage(s, g)["regions_with_grounds"])
                 for s in wf.forest_sources())
    assert served >= 105


# ------------------------------------------------------------------------------- alt data
ALT = json.loads((DESK / "data" / "alt_dataset_sources.json").read_text("utf-8"))


def test_alt_rows_cover_satellite_supply_chain_and_patents_with_licences_and_instruments() -> None:
    universe = set(json.loads((DESK / "data" / "universe" / "universe.json").read_text("utf-8")))
    classes = {r["class"] for r in ALT["rows"]}
    assert {"satellite", "supply_chain", "patents"} <= classes
    for r in ALT["rows"]:
        for key in ("id", "cadence", "auth", "licence", "machine_use_allowed", "cursor", "region",
                    "language", "mechanism"):
            assert r.get(key) is not None, (r["name"], key)
        assert set(r["instruments"]) <= universe, (r["name"], set(r["instruments"]) - universe)
        if not r["fetch"]:
            assert r.get("blocker"), r["name"]      # a registered gap says what stops it
        if r["auth"] != "none":
            assert not r["fetch"]                   # a keyed row is never fetched
    assert len({r["id"] for r in ALT["rows"]}) == len(ALT["rows"])


def test_the_acquirer_reads_fetchable_alt_rows_after_its_seeds_and_skips_keyed(monkeypatch,
                                                                              tmp_path) -> None:
    from research import acquire_datasets as ad
    monkeypatch.setattr(ad, "REGISTRY", tmp_path / "registry.json")
    monkeypatch.setattr(ad, "WORLD", tmp_path / "world")
    urls = [u for u, _h in ad._endpoints(10_000)]
    n_seed = len(ad._SEED_ENDPOINTS)
    alt = [ad._alt_url(r) for r in ad.alt_rows() if ad._alt_fetchable(r)]
    assert alt and urls[n_seed:n_seed + len(alt)] == alt
    blocked = {ad._alt_url(r) for r in ad.alt_rows() if not ad._alt_fetchable(r)}
    assert blocked and not blocked & set(urls[n_seed:n_seed + len(alt)])
    assert not [u for u in urls if "patentsview" in u or "sentinel-hub" in u]
    assert all("{today}" not in u for u in urls)


def test_nasa_power_and_arcgis_payloads_parse_into_dated_series() -> None:
    from research import acquire_datasets as ad
    days = {f"2025{m:02d}{d:02d}": float(m * 31 + d) for m in range(1, 13) for d in range(1, 29)}
    power = {"properties": {"parameter": {"T2M_MAX": days,
                                          "PRECTOTCORR": {k: (-999.0 if i == 0 else i % 17)
                                                          for i, k in enumerate(days)}}}}
    df = ad._parse(json.dumps(power).encode(), "https://power.larc.nasa.gov/api/x")
    dated = ad._dated(df)
    assert dated is not None and len(dated) == 336 and dated.index.min().year == 2025
    assert df["PRECTOTCORR"].isna().sum() == 1                 # the -999 fill is not a value
    base = 1_700_000_000_000
    arc = {"features": [{"attributes": {"date": base + i * 86_400_000, "n_tanker": 30 + i % 11}}
                        for i in range(260)]}
    df2 = ad._parse(json.dumps(arc).encode(), "https://services9.arcgis.com/x/query")
    dated2 = ad._dated(df2)
    assert dated2 is not None and dated2.index.min().year == 2023   # epoch-ms, not 1970
    fred = b"observation_date,TSIFRGHT\n" + b"".join(
        f"20{y:02d}-{m:02d}-01,{100 + y + m}\n".encode() for y in range(0, 20) for m in range(1, 13))
    assert ad._dated(ad._parse(fred, "https://fred.stlouisfed.org/graph/fredgraph.csv")) is not None


def test_alt_measurement_names_unattempted_platforms_and_the_missing_cell_route(tmp_path) -> None:
    cov = tmp_path / "cov.json"
    cov.write_text(json.dumps({"platforms": {
        "amarkets": {"last_attempt": "2026-09-12T04:01:59+00:00", "last_state": "ok",
                     "best_rows": 115},
        "hfm_pamm": {"last_attempt": "2026-09-12T04:01:55+00:00",
                     "last_state": "error:HTTPError", "best_rows": 0}}}))
    got = wf.alt_platforms(NOW - timedelta(hours=24), cov)
    assert got["attempted_in_window"] == 0 and got["yielding"] == 0 and got["n"] == 2
    fresh = wf.alt_platforms(datetime(2026, 9, 11, tzinfo=UTC), cov)
    assert fresh["yielding"] == 1
    acq = tmp_path / "acq.json"
    row = next(r for r in ALT["rows"] if r["fetch"] and "{today}" in r["url"])
    acq.write_text(json.dumps({"by_url": {row["url"].replace("{today}", "20260930"): {
        "status": "SUCCESS", "series": ["power_x"], "at": "2026-09-30T10:00:00+00:00"}}}))
    alt = wf.alt_datasets(NOW, acquired_path=acq)
    by = {r["name"]: r for r in alt["rows"]}
    assert by[row["name"]]["status"] == "SUCCESS"
    assert any(r["status"] == "REGISTERED_BLOCKED" for r in alt["rows"])
    assert alt["by_class"]["patents"]["fetchable"] == 0
    assert "world_macro_state" in alt["cell_route"]
