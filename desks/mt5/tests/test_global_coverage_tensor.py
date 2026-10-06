"""THE GLOBAL COVERAGE TENSOR -- proven-path coverage, the three numbers, source ROI, missions.

    python -m pytest desks/mt5/tests/test_global_coverage_tensor.py -q -p no:cacheprovider

What is fenced here, and why each is worth a test:

  * THE CRO CYCLE'S CONTRACT (PR #154): the five top-level keys of GLOBAL_COVERAGE_TENSOR.json
    and the three of SOURCE_ROI.json are read by exact name, so a rename breaks a reader;
  * CELLS ARE MECHANISTICALLY GENERATED, never the literal product, and every region gets the
    same template in each of its languages;
  * REGISTERED OR FETCHED ALONE IS NOT COVERAGE: it raises the nominal share and never the
    proven-path share; a proven cell needs every link, and an `observations` refusal is not an
    outcome;
  * ONE LADDER: the principal's stages are a view of the world ladder;
  * MISSIONS name the cell and the one move, land in the intelligence seat the compiler reads,
    and the throttle reorders and defers but never reaches zero;
  * THE RETIRE FLAG needs adequate sampling and zero novel information, and redirects budget;
  * THE DELTA CURSOR reads only what was appended.
"""
from __future__ import annotations

import json
import sqlite3
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest

DESK = Path(__file__).resolve().parents[1]
ROOT = DESK.parents[1]
for _p in (str(ROOT), str(DESK), str(DESK / "research")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import global_coverage_tensor as G  # noqa: E402

from libs.research import coverage as CV  # noqa: E402

NOW = datetime(2026, 9, 30, 12, 0, tzinfo=UTC)


@pytest.fixture
def desk(tmp_path, monkeypatch):
    data, reports = tmp_path / "data", tmp_path / "reports"
    (data / "hypotheses").mkdir(parents=True)
    reports.mkdir()
    paths = {
        "OUT": reports / "GLOBAL_COVERAGE_TENSOR.json", "ROI_OUT": reports / "SOURCE_ROI.json",
        "STATE": data / "global_coverage" / "state.json",
        "MISSIONS_DIR": data / "intelligence" / "global_coverage",
        "GRAPH": data / "hypothesis_graph.jsonl",
        "GATE_LEDGER": data / "hypotheses" / "gate_verdict_ledger.jsonl",
        "UNIVERSE_DIR": data / "universe", "DEEP_FOREST": data / "deep_forest_sources.json",
        "SURVIVORS": reports / "UNIVERSAL_SURVIVORS.json", "SLEEVES": data / "sleeves.json",
        "BACKPRESSURE": reports / "GAUNTLET_BACKPRESSURE.json",
        "BREADTH": reports / "EFFECTIVE_BREADTH.json",
        "MINING_DB": data / "mining" / "mining.db",
        "MINING_METRICS": reports / "mining" / "MINING_METRICS.json",
    }
    for name, p in paths.items():
        monkeypatch.setattr(G, name, p)
    monkeypatch.setattr(G, "INTEL_ROOTS", (data / "intelligence",))
    paths["INTEL"] = data / "intelligence"
    paths["DATA"] = data
    return paths


def _conn() -> sqlite3.Connection:
    c = sqlite3.connect(":memory:")
    c.row_factory = sqlite3.Row
    return c


def _jsonl(path: Path, rows: list[dict[str, Any]], mode: str = "w") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open(mode, encoding="utf-8") as fh:
        for r in rows:
            fh.write(json.dumps(r) + "\n")


def _born(n: int, sym: str = "EURUSD", fam: str = "overnight_drift",
          seat: str = "arxiv", hours_ago: float = 5.0) -> dict[str, Any]:
    return {"id": f"{seat}.{sym}.{fam}.{n}", "symbol": sym, "family": fam,
            "params": {"session": "asia"}, "source": f"miner:{seat}", "fate": "BORN",
            "at": (NOW - timedelta(hours=hours_ago)).isoformat()}


def _verdict(sym: str = "EURUSD", fam: str = "overnight_drift", *, passed: Any = False,
             gate: str = "in_sample_screen", hours_ago: float = 1.0) -> dict[str, Any]:
    return {"at": (NOW - timedelta(hours=hours_ago)).isoformat(), "cell": f"{sym}.{fam}.x",
            "sym": sym, "family": fam, "passed": passed,
            "terminal_gate": "PASSED" if passed else gate}


def _seat(desk: dict[str, Path], name: str, *, pit: bool) -> None:
    d = desk["INTEL"] / name
    d.mkdir(parents=True, exist_ok=True)
    row: dict[str, Any] = {"title": "a claim", "url": "https://example.org"}
    if pit:
        row["available_time"] = NOW.isoformat()
    (d / "rows.json").write_text(json.dumps([row]), "utf-8")


def _build(**kw: Any) -> dict[str, Any]:
    return G.build(now=NOW, conn=_conn(), budget_s=120, **kw)


# ---------------------------------------------------------------------------- the CRO contract
def test_the_cro_cycle_reads_these_exact_keys(desk):
    """PR #154 reads GLOBAL_COVERAGE_TENSOR.json and SOURCE_ROI.json by exact field name."""
    _seat(desk, "arxiv", pit=True)
    _jsonl(desk["GRAPH"], [_born(1)])
    _jsonl(desk["GATE_LEDGER"], [_verdict()])
    _build()
    doc = json.loads(desk["OUT"].read_text("utf-8"))
    for key in ("nominal", "distinct", "effective_independent", "proven_path_covered_share",
                "top_missions"):
        assert key in doc, key
    assert isinstance(doc["nominal"], int) and doc["nominal"] > doc["distinct"] > 0
    assert isinstance(doc["top_missions"], list) and doc["top_missions"]
    assert {"cell", "stage", "next_move", "evig"} <= set(doc["top_missions"][0])
    roi = json.loads(desk["ROI_OUT"].read_text("utf-8"))
    for key in ("funnel", "info_gain_per_compute_hour", "incremental_keff"):
        assert key in roi, key
    funnel = roi["funnel"]["seat:arxiv"]
    assert set(funnel) == {"fetched", "extracted", "compiled", "judged", "survived", "forward",
                           "live"}


# ------------------------------------------------------------------------------- the generator
def test_cells_are_generated_by_compatibility_never_the_literal_product():
    actors = G.mechanism_actor()
    gen, meta = G.generate(actors)
    vocab = G.vocabulary(actors)
    assert not meta["truncated"]
    assert len(gen) < CV.nominal_cells(vocab) / 1_000
    for coords in list(gen.values())[:5000]:
        v = dict(zip(CV.GLOBAL_AXES, coords, strict=True))
        prof = G.profile(v["mechanism"])
        assert v["source_class"] in prof["sources"]
        assert v["instrument"] in G.TRANSMISSIONS[v["asset_transmission"]]
        assert v["asset_transmission"] in prof["transmissions"]
        assert v["participant"] == actors[v["mechanism"]]


def test_every_region_gets_the_same_template_in_each_of_its_languages():
    gen, _ = G.generate(G.mechanism_actor())
    per_region_lang: dict[tuple[str, str], int] = {}
    for coords in gen.values():
        k = (coords[0], coords[1])
        per_region_lang[k] = per_region_lang.get(k, 0) + 1
    expected = {(r, lang) for r, (_c, langs) in G.REGIONS.items() for lang in langs}
    assert set(per_region_lang) == expected
    assert len(set(per_region_lang.values())) == 1, "one civilisation deeper than another"


def test_the_24_source_classes_are_the_principals_and_all_are_reachable():
    assert len(CV.SOURCE_CLASSES) == 24 and len(set(CV.SOURCE_CLASSES)) == 24
    used = {sc for p in G.MECHANISM_PROFILES.values() for sc in p["sources"]}
    assert used == set(CV.SOURCE_CLASSES), set(CV.SOURCE_CLASSES) - used
    assert set(G.MECHANISM_PROFILES) == set(G.mechanism_actor())


# --------------------------------------------------------------------------------- one ladder
def test_the_principal_ladder_is_a_view_of_the_world_ladder():
    assert set(CV.PRINCIPAL_OF_WORLD) == set(CV.WORLD_LADDER)
    assert set(CV.PRINCIPAL_OF_WORLD.values()) <= set(CV.PRINCIPAL_LADDER)
    assert CV.ladder_of(CV.GLOBAL) is CV.WORLD_LADDER_SPEC
    assert CV.principal_view("TESTING") == {"stage": "COMPILED", "terminal": None}
    assert CV.principal_view("FAILED") == {"stage": "JUDGED", "terminal": "FAILED"}
    assert CV.principal_view("FAILED", "NO_EDGE")["terminal"] == "NO_EDGE"
    assert CV.principal_view("DECAYED")["terminal"] == "LOW_EV_RETIRED"
    with pytest.raises(ValueError):
        CV.principal_view("FAILED", "MAYBE")
    assert CV.terminal_of_gate_class("cost_killed") == "NOT_TRADEABLE"
    assert CV.terminal_of_gate_class(None) is None


# ------------------------------------------------------------------------- the proven path
def test_registered_or_fetched_alone_is_nominal_never_proven(desk):
    _seat(desk, "arxiv", pit=True)
    doc = _build()
    cov = doc["coverage"]
    assert cov["nominal_covered"] > 0
    assert cov["proven_path_covered"] == 0 and cov["measured_outcome"] == 0
    assert doc["proven_path_covered_share"] == 0.0


def test_a_proven_cell_needs_every_link_and_a_real_outcome(desk):
    _seat(desk, "arxiv", pit=True)
    _seat(desk, "reddit", pit=False)
    _jsonl(desk["GRAPH"], [_born(1, seat="arxiv"),
                           _born(2, sym="GBPUSD", seat="reddit")])
    _jsonl(desk["GATE_LEDGER"], [_verdict("EURUSD"), _verdict("GBPUSD")])
    doc = _build()
    assert doc["coverage"]["measured_outcome"] == 2
    assert doc["coverage"]["proven_path_covered"] == 1, "a seat with no PIT stamp is not proven"
    roi = doc["_roi"]["sources"]
    assert roi["seat:arxiv"]["proven_links"]["pit"] is True
    assert roi["seat:reddit"]["proven_links"]["pit"] is False
    assert doc["principal_ladder"]["terminals"]["NO_EDGE"] == 2


def test_an_observations_refusal_is_not_a_measured_outcome(desk):
    _seat(desk, "arxiv", pit=True)
    _jsonl(desk["GRAPH"], [_born(1)])
    _jsonl(desk["GATE_LEDGER"], [_verdict(gate="observations")])
    doc = _build()
    assert doc["coverage"]["measured_outcome"] == 0
    assert doc["_roi"]["sources"]["seat:arxiv"]["funnel"]["judged"] == 1.0


def test_a_banned_family_never_enters_the_tensor(desk):
    _seat(desk, "arxiv", pit=True)
    _jsonl(desk["GRAPH"], [_born(1, fam="discovered")])
    doc = _build()
    assert doc["observations"]["evidence"]["banned_family_rows"] == 1
    assert all(m.get("family") != "discovered" for m in doc["missions"]["rows"])


# ------------------------------------------------------------------------------- the missions
def test_missions_name_the_cell_and_one_move_and_reach_the_compiler_seat(desk):
    _seat(desk, "arxiv", pit=True)
    doc = _build()
    rows = doc["missions"]["rows"]
    assert G.MISSION_FLOOR <= len(rows) <= G.MAX_MISSIONS
    for m in rows:
        assert m["cell"] and m["next_move"] and m["stage"] in CV.PRINCIPAL_LADDER
    assert len({m["next_move"] for m in rows}) == len(rows), "one move, one mission"
    files = list(desk["MISSIONS_DIR"].glob("missions_*.json"))
    assert len(files) == 1
    donated = json.loads(files[0].read_text("utf-8"))["rows"]
    assert len(donated) == len(rows)
    assert all(r["kind"] == "coverage_gap" and r["available_time"] for r in donated)
    regions = {m["values"]["region"] for m in rows}
    assert len(regions) >= 4, "the mission set is broad, not one face of the tensor"


def test_the_throttle_reorders_and_defers_but_never_reaches_zero(desk):
    desk["BACKPRESSURE"].write_text(json.dumps({"at": NOW.isoformat(), "windows": {"24h": {
        "intake": {"born_cells": 1000}, "testing": {"cells_judged": 100}}}}), "utf-8")
    _seat(desk, "arxiv", pit=True)          # acquired ground: there is something to convert
    doc = _build()
    thr = doc["throttle"]
    assert thr["engaged"] and thr["factor"] == pytest.approx(0.1)
    assert thr["missions"] == G.MISSION_FLOOR
    assert thr["onboarding_missions_max"] == 1
    assert len(doc["missions"]["rows"]) == G.MISSION_FLOOR
    onboarding = [m for m in doc["missions"]["rows"] if m["kind"] == "onboarding"]
    assert len(onboarding) <= 1, "onboarding is cut first while there is ground to convert"
    assert doc["missions"]["deferred"] > 0


def test_a_throttle_on_an_absent_or_stale_reading_never_engages():
    assert G.throttle({"status": "UNMEASURED", "ratio": None})["engaged"] is False
    stale = {"status": "MEASURED", "ratio": 0.2, "age_h": G.THROTTLE_MAX_AGE_H + 1}
    assert G.throttle(stale)["engaged"] is False
    assert G.throttle({"status": "MEASURED", "ratio": 0.0})["missions"] == G.MISSION_FLOOR


# ------------------------------------------------------------------------------- source ROI
def _roi_fixture(measured: float, days: float) -> tuple[G.Sources, dict[str, Any], G.Store]:
    src = G.Sources()
    for sid in ("seat:a", "seat:b"):
        row = src.add(sid, origin="test", source_class="market_native")
        row.update({"acquired": True, "pit": True})
    state = G.load_state()
    for sid in ("seat:a", "seat:b"):
        c = G._src_counts(state, sid)
        c.update({"judged": measured, "measured": measured,
                  "first_at": (NOW - timedelta(days=days)).isoformat(),
                  "last_measured_at": NOW.isoformat()})
    store = G.Store(state)
    actors = G.mechanism_actor()
    coords = G.observed_coords("trend_persistence", "fx_major", region="global", language="en",
                               source_class="market_native", horizon="1d", session="all",
                               actors=actors)
    for sid in ("seat:a", "seat:b"):     # both reach the SAME cell: neither adds novel information
        store.observe(coords, "FAILED", source=sid, why="test", terminal="NO_EDGE")
    return src, state, store


def test_the_retire_flag_needs_adequate_sampling_and_zero_novel_information():
    src, state, store = _roi_fixture(G.RETIRE_MIN_JUDGED + 50, G.RETIRE_MIN_DAYS + 1)
    roi = G.source_roi(src, state, store, now=NOW, judge_per_hour=10.0,
                       book={"status": "UNMEASURED"}, live_mechs=set())
    flag = roi["seat:a"]["auto_retire"]
    assert flag["flag"] is True and flag["action"] == "REDIRECT_BUDGET"
    assert roi["seat:a"]["info_gain_per_compute_hour"] == 0.0
    assert roi["seat:a"]["incremental_keff"] == G.UNMEASURED
    assert "seat:a" in src.rows, "a flagged source is never deleted"
    src, state, store = _roi_fixture(G.RETIRE_MIN_JUDGED - 1, G.RETIRE_MIN_DAYS + 1)
    roi = G.source_roi(src, state, store, now=NOW, judge_per_hour=10.0,
                       book={"status": "UNMEASURED"}, live_mechs=set())
    assert roi["seat:a"]["auto_retire"]["flag"] is False


def test_incremental_keff_uses_the_books_own_correlation():
    src, state, store = _roi_fixture(10, 1)
    actors = G.mechanism_actor()
    coords = G.observed_coords("carry_rollover", "fx_major", region="global", language="en",
                               source_class="market_native", horizon="5d", session="all",
                               actors=actors)
    store.observe(coords, "CERTIFIED", source="seat:a", why="test")
    book = {"status": "MEASURED", "n_nominal": 31.0, "k_eff": 1.324, "rho_book": 0.747,
            "rho_cross": 0.21}
    new = G.source_roi(src, state, store, now=NOW, judge_per_hour=10.0, book=book,
                       live_mechs=set())["seat:a"]["incremental_keff"]
    held = G.source_roi(src, state, store, now=NOW, judge_per_hour=10.0, book=book,
                        live_mechs={"carry_rollover"})["seat:a"]["incremental_keff"]
    assert new > held > 0, "a survivor in an occupied mechanism buys less breadth"
    assert G.source_roi(src, state, store, now=NOW, judge_per_hour=10.0, book=book,
                        live_mechs=set())["seat:b"]["incremental_keff"] == 0.0


# ------------------------------------------------------------------------------ the cursor
def test_the_delta_cursor_reads_only_what_was_appended(desk):
    _seat(desk, "arxiv", pit=True)
    _jsonl(desk["GRAPH"], [_born(1)])
    first = _build()
    assert first["observations"]["evidence"]["graph_births"] == 1
    assert first["state"]["cursor"]["hypothesis_graph"]["mode"] == "backfill"
    _jsonl(desk["GRAPH"], [_born(2, sym="GBPUSD")], mode="a")
    second = _build()
    assert second["observations"]["evidence"]["graph_births"] == 1
    assert second["state"]["cursor"]["hypothesis_graph"]["mode"] == "delta"
    state = json.loads(desk["STATE"].read_text("utf-8"))
    assert state["sources"]["seat:arxiv"]["compiled"] == 2


def test_dry_run_writes_nothing(desk):
    _seat(desk, "arxiv", pit=True)
    doc = _build(dry_run=True)
    assert doc["dry_run"] is True
    assert not desk["OUT"].exists() and not desk["ROI_OUT"].exists()
    assert not desk["STATE"].exists()
    assert not list(desk["MISSIONS_DIR"].glob("*.json")) if desk["MISSIONS_DIR"].exists() else True


def test_absent_inputs_are_named_unmeasured(desk):
    doc = _build()
    assert "gate_verdict_ledger" in doc["unmeasured"]
    assert "mining.db (PR #133)" in doc["unmeasured"]
    assert doc["effective_independent"] == G.UNMEASURED
