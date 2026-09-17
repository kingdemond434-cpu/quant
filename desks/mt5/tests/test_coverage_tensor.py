"""THE COVERAGE TENSOR ORGAN -- the states come from evidence, the holes become work.

    python -m pytest desks/mt5/tests/test_coverage_tensor.py -q -p no:cacheprovider

What is fenced here:

  * EVERY LADDER STATE COMES FROM A PLANTED ARTIFACT, and the cell it lands on is asserted by
    name. A state reachable only by reading the real box is a state no test can falsify;
  * AN ABSENT EVIDENCE SOURCE IS NAMED UNMEASURED and the rung stays at the floor -- never a
    zero, never a clean verdict (L1.28a);
  * A HOLE BECOMES WORK: a `coverage_gap` discovery in state UNPROCESSED whose payload names the
    cell and the ONE move that raises it a rung, plus a `frontier_map` row;
  * RE-RUNNING DUPLICATES NOTHING (content-hash idempotence), which is what makes an hourly leg
    safe;
  * `--dry-run` WRITES NO BYTE -- this organ runs on the box holding live positions;
  * FLOORS RATCHET UP ONLY, across passes, through the stored floors file;
  * `covered()` REFUSES FIVE OBVIOUS SOURCES through the organ's own country reading;
  * THE THREE NAMED FRONTIER ROWS of LAWS 5f appear in the report with their state.

No network: the organ reads files and the tmp registry only.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

import pytest

_DESK = Path(__file__).resolve().parents[1]
_ROOT = _DESK.parent.parent
for _p in (str(_DESK), str(_DESK / "research"), str(_ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from libs.moat import registry as R  # noqa: E402
from libs.research import country_lab as CL  # noqa: E402
from libs.research import coverage as CV  # noqa: E402
from research import coverage_tensor as CT  # noqa: E402
from research import universe_policy as UP  # noqa: E402

#: The broker registry the fixture desk trades. `Apple` is the event lane and must never be
#: hunted; `USDIDR` and `USDKRW` are the two countries' own instruments.
UNIVERSE = {
    "EURUSD": {"asset_class": "forex"},
    "USDJPY": {"asset_class": "forex"},
    "AUDUSD": {"asset_class": "forex"},
    "USDIDR": {"asset_class": "Forex Exotics"},
    "USDKRW": {"asset_class": "Forex Exotics"},
    "XAUUSD": {"asset_class": "commodities"},
    "Apple": {"asset_class": "Equities"},
}
BARS = ("EURUSD_H1", "USDJPY_H1", "AUDUSD_H1", "USDIDR_H1", "XAUUSD_H1", "Apple_H1")

SLEEVES = {"sleeves": [
    {"name": "xau_asia", "symbol": "XAUUSD", "family": "asia_momentum", "session": "asia",
     "exec": "family_market", "status": "LIVE"},
    # A DIFFERENT COORDINATE from the failed verdict below on purpose: DECAYED outranks FAILED,
    # so a retirement on the same (asset, mechanism) would legitimately absorb it.
    {"name": "idr_dead", "symbol": "USDIDR", "family": "trend_ma_cross", "session": "all",
     "status": "RETIRED"},
]}
SURVIVORS = {"n": 1, "survivors": {"u.1": {
    "cell": "USDJPY overnight_gap_decay asia", "sym": "USDJPY",
    "shadow_spec": {"family": "overnight_gap_decay", "selector": "asia", "params": {}}}}}
FORWARD = {"family_budget": {"clocks": {"AUDUSD.overnight_gap_decay.asia": {"family": "x"}}}}
GATE_ROWS = [{"at": "2026-09-17T00:00:00+00:00", "cell": "EURUSD.carry.p=1", "sym": "EURUSD",
              "family": "carry", "passed": False, "terminal_gate": "cost"}]
FORGE = {"series": [{"symbol": "USDJPY", "transform": "surprise", "information": "supply_chain"}]}


def _pack(code: str, *, region: str, langs: tuple[str, ...], instruments: tuple[str, ...],
          layers: int, verified: bool = True) -> Any:
    """A country pack with `layers` of the ten mapped, so the coverage rule has something to
    refuse. Every other layer is left UNMAPPED, which is what the rule is about."""
    sources = tuple(CL.SourceRow(id=f"{code}-{layer}", layer=layer, label=f"{layer} root",
                                 roots=(f"https://{layer}.{code}",), verified=verified)
                    for layer in CV.SOURCE_LAYERS[:layers])
    return CL.CountryPack(code=code, name=code.upper(), region_command=region, currency="XXX",
                          executable_instruments=instruments, native_languages=langs,
                          sources=sources)


PACKS: dict[str, Any] = {}


@pytest.fixture()
def desk(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """A whole desk in a tmp tree plus a tmp registry, on the `tests/moat/test_registry.py`
    fixture pattern: the real backup is never touched and the path is restored on teardown."""
    data, reports = tmp_path / "data", tmp_path / "reports"
    (data / "universe").mkdir(parents=True)
    (data / "hypotheses").mkdir(parents=True)
    (data / "axes").mkdir(parents=True)
    (reports / "shadow").mkdir(parents=True)
    (data / "universe" / "universe.json").write_text(json.dumps(UNIVERSE), encoding="utf-8")
    for name in BARS:
        (data / "universe" / f"{name}.parquet").write_bytes(b"PAR1")
    (data / "axes" / "cot.json").write_text("{}", encoding="utf-8")
    (data / "sleeves.json").write_text(json.dumps(SLEEVES), encoding="utf-8")
    (data / "forward_reconcile.json").write_text(json.dumps(FORWARD), encoding="utf-8")
    (data / "hypotheses" / "gate_verdict_ledger.jsonl").write_text(
        "\n".join(json.dumps(r) for r in GATE_ROWS), encoding="utf-8")
    (reports / "UNIVERSAL_SURVIVORS.json").write_text(json.dumps(SURVIVORS), encoding="utf-8")
    # DELIBERATELY ABSENT: the representation forge report, the ingestion ledger, the
    # certificates directory and GOLD_RETIRED -- each must read UNMEASURED by name.

    for attr, path in (("DATA", data), ("REPORTS", reports),
                       ("UNIVERSE_JSON", data / "universe" / "universe.json"),
                       ("UNIVERSE_DIR", data / "universe"), ("SLEEVES", data / "sleeves.json"),
                       ("CERT_DIR", data / "certificates"),
                       ("SURVIVORS", reports / "UNIVERSAL_SURVIVORS.json"),
                       ("GATE_LEDGER", data / "hypotheses" / "gate_verdict_ledger.jsonl"),
                       ("FORWARD_DATA", data / "forward_reconcile.json"),
                       ("FORWARD_REPORT", reports / "forward_reconcile.json"),
                       ("SHADOW_STATE", reports / "shadow" / "shadow_state.json"),
                       ("INGESTION_REPORT", reports / "INGESTION_LEDGER.json"),
                       ("INGESTION_EXPLOIT", reports / "INGESTION_EXPLOITATION.json"),
                       ("INGESTION_JSONL", data / "ingestion_ledger.jsonl"),
                       ("FORGE_REPORT", reports / "REPRESENTATION_FORGE.json"),
                       # The forge MODULE too: a sibling builder landed one on the real tree
                       # mid-session and the basis silently stopped reading UNMEASURED here. An
                       # organ whose reading depends on the tree outside its fixture is untestable.
                       ("FORGE_MODULE", tmp_path / "research" / "representation_forge.py"),
                       ("GOLD_RETIRED", data / "GOLD_RETIRED.json"),
                       ("AXES_DIR", data / "axes"),
                       ("COUNTRIES_DIR", tmp_path / "research" / "countries"),
                       ("CURSOR", data / "coverage_cursor.json"),
                       ("FLOORS", data / "coverage_floors.json"),
                       ("OUT", reports / "COVERAGE_TENSOR.json")):
        monkeypatch.setattr(CT, attr, path)
    packs_dir = tmp_path / "research" / "countries"
    for code in ("id", "kr"):
        (packs_dir / code).mkdir(parents=True)
    PACKS.clear()
    PACKS["id"] = _pack("id", region="asia", langs=("id",), instruments=("USDIDR",), layers=5)
    PACKS["kr"] = _pack("kr", region="asia", langs=("ko",), instruments=("USDKRW",), layers=10)
    monkeypatch.setattr(CL, "PACK_RESOLVER", lambda code: PACKS.get(code))
    CL._PACK_CACHE.clear()

    monkeypatch.setattr(UP, "UNIVERSE", data / "universe" / "universe.json")
    UP._registry.cache_clear()
    monkeypatch.setattr(R, "BACKUP", tmp_path / "no_such_backup")
    R.set_path(tmp_path / "registry.sqlite")
    yield tmp_path
    UP._registry.cache_clear()
    CL._PACK_CACHE.clear()
    R.set_path(None)


@pytest.fixture()
def built(desk: Path) -> dict[str, Any]:
    return CT.build(budget_s=60.0, top_k=12)


def _states(doc: dict[str, Any], tensor: str) -> dict[str, int]:
    return doc["tensors"][tensor]["histogram"]


# --------------------------------------------------------------- every state comes from evidence
def test_the_planted_evidence_lands_on_the_cell_it_names(built: dict[str, Any]) -> None:
    hist = _states(built, CV.WORLD)
    assert hist["INGESTED"] > 0, "the bar estate and the axis series"
    assert hist["LIVE"] >= 1 and hist["DECAYED"] >= 1, "a LIVE sleeve and a RETIRED one"
    assert hist["CERTIFIED"] >= 1, "the survivor ledger"
    assert hist["FORWARD"] >= 1, "the forward reconcile roster"
    assert hist["FAILED"] >= 1, "the gate verdict ledger"
    obs = built["tensors"][CV.WORLD]["observations"]
    assert set(obs) >= {"INGESTED", "LIVE", "DECAYED", "CERTIFIED", "FORWARD", "FAILED"}


def test_the_event_lane_is_never_hunted_and_the_hypothesis_lane_is(built: dict[str, Any]) -> None:
    lanes = built["lanes"]
    assert lanes["event_lane_assets"] == 1 and lanes["hypothesis_assets"] == 6
    sizes = built["tensors"][CV.WORLD]["vocabulary_sizes"]
    assert sizes["asset"] == 6, "Apple is a share CFD: the event lane, never a hypothesis axis"


def test_the_absent_sources_are_named_unmeasured_and_their_rungs_stay_at_the_floor(
        built: dict[str, Any]) -> None:
    unmeasured = built["unmeasured"]
    for name in ("representation_forge_report", "ingestion_ledger", "certificates_dir",
                 "gold_retired"):
        assert name in unmeasured, f"{name} was absent and must be named, not read as zero"
        assert "UNMEASURED" in unmeasured[name] or "not on this box" in unmeasured[name]
    assert _states(built, CV.WORLD)["REPRESENTED"] == 0, \
        "no forge report: the REPRESENTED rung is unmeasured, and it stays empty rather than "\
        "being imputed from the candidates below it"
    assert built["representation_basis"].startswith(CV.UNMEASURED)


def test_the_forest_tensor_separates_a_declared_source_from_a_fetched_one(desk: Path) -> None:
    PACKS["id"] = _pack("id", region="asia", langs=("id",), instruments=("USDIDR",), layers=5,
                        verified=False)
    CL._PACK_CACHE.clear()
    doc = CT.build(budget_s=60.0, top_k=6)
    hist = _states(doc, CV.FOREST)
    assert hist["VERIFIED"] == 10, "Korea's ten fetched layers"
    assert hist["DISCOVERED"] == 5, "Indonesia's five declared-but-never-fetched layers"
    assert doc["tensors"][CV.FOREST]["source_layers"] == list(CV.SOURCE_LAYERS)


# ------------------------------------------------------------------- the country coverage rule
def test_covered_refuses_five_obvious_sources_through_the_organ(built: dict[str, Any]) -> None:
    """Indonesia has five verified layers and Korea has ten; neither is COVERED, and the report
    says which condition each one failed."""
    per_country = built["coverage"]["by_country"]
    idn = per_country["id"]
    assert idn["covered"] is False and idn["state"] == "MAPPING"
    assert len(idn["condition_layers"]["unmapped"]) == 5
    kor = per_country["kr"]
    assert kor["condition_layers"]["met"] is True, "all ten layers mapped"
    assert kor["state"] in ("STALLED", "COVERED")
    assert kor["covered"] is (kor["state"] == "COVERED")
    assert built["coverage"]["n_covered"] == sum(
        1 for v in per_country.values() if v.get("covered"))
    assert "five obvious sources is not coverage" in built["coverage"]["rule"]


def test_a_country_whose_discovery_stopped_is_stalled_not_covered(desk: Path) -> None:
    doc = CT.build(budget_s=60.0, top_k=6)
    assert doc["coverage"]["by_country"]["kr"]["state"] == "STALLED", \
        "ten layers mapped and no scout row in the window: the scouts ran out of ideas"
    conn = R.connect()
    try:
        conn.execute("INSERT INTO sources(source_id, kind, language, country, first_seen, "
                     "last_crawled, status, meta_json) VALUES(?,?,?,?,?,?,?,?)",
                     ("kr:new-forum", "forum", "ko", "kr", R.now(), R.now(), "registered",
                      json.dumps({"layer": "retail_ecology", "access_label": "PUBLIC"})))
        conn.commit()
    finally:
        conn.close()
    again = CT.build(budget_s=60.0, top_k=6)
    kor = again["coverage"]["by_country"]["kr"]
    assert kor["state"] == "COVERED" and kor["covered"] is True
    assert kor["condition_discovery"]["per_day"] > 0
    assert again["coverage"]["by_region"]["asia"]["covered"] == 1


# --------------------------------------------------------------------- the holes become the work
def test_a_hole_becomes_a_coverage_gap_discovery_that_names_the_next_move(
        built: dict[str, Any]) -> None:
    assert built["frontier"]["n_holes"] > 0
    handed = built["frontier"]["handed_to_the_machine"]
    assert handed["discoveries_recorded"] > 0 and handed["frontier_rows"] > 0
    rows = R.discoveries(state="UNPROCESSED", origin="DESK")
    gaps = [r for r in rows if r["source_type"] == CT.SOURCE_TYPE]
    assert gaps, "the holes reached the registry as discoveries the compiler can pick up"
    payload = json.loads(gaps[0]["payload_json"])
    assert payload["kind"] == "coverage_gap"
    assert payload["tensor"] in (CV.WORLD, CV.FOREST)
    assert payload["state"] in CV.WORLD_LADDER + CV.FOREST_LADDER
    assert payload["next_state"] and payload["next_move"], \
        "a frontier row must say what moves it ONE rung, or it is a report and not work"
    assert payload["evig_breakdown"]["prior_p_edge"] > 0
    assert "|" in payload["cell"] and payload["values"]
    top = built["frontier"]["top"][0]
    assert top["score"] >= built["frontier"]["top"][-1]["score"], "ranked by EVIG, descending"
    assert set(top["breakdown"]) >= {"prior_p_edge", "reachability", "novelty", "capacity", "cost"}


def test_rerunning_the_same_face_duplicates_nothing(desk: Path) -> None:
    """The hourly leg re-enumerates ground it already handed over, so the same hole must be the
    same discovery. The cursor is rewound so the second pass ranks the SAME face -- otherwise the
    rotation would be doing the de-duplication and the content hash would stay untested."""
    first = CT.build(budget_s=60.0, top_k=12)
    n_first = len(R.discoveries(limit=5000))
    assert first["frontier"]["handed_to_the_machine"]["discoveries_recorded"] > 0
    CT.CURSOR.write_text(json.dumps({CV.WORLD: 0, CV.FOREST: 0}), encoding="utf-8")
    second = CT.build(budget_s=60.0, top_k=12)
    assert second["frontier"]["cursor"] == {CV.WORLD: 0, CV.FOREST: 0}
    assert len(R.discoveries(limit=5000)) == n_first, \
        "content-hash idempotence: the same hole is the same discovery"
    assert second["frontier"]["handed_to_the_machine"]["discoveries_recorded"] == 0
    assert second["frontier"]["handed_to_the_machine"]["discoveries_seen"] > 0
    conn = R.connect()
    try:
        cells = [r[0] for r in conn.execute("SELECT cell FROM frontier_map")]
    finally:
        conn.close()
    assert len(cells) == len(set(cells)), "frontier_map is an UPSERT on the cell"
    assert all(c.startswith("coverage:") for c in cells), \
        "this organ's rows never collide with the scout swarm's"


def test_the_frontier_rows_leave_the_chao1_columns_unmeasured(desk: Path) -> None:
    """`global_research_os.unseen_mass` divides by these; a 0 here would tell it a country's
    ground is exhausted when this organ measured no such thing."""
    CT.build(budget_s=60.0, top_k=6)
    conn = R.connect()
    try:
        rows = conn.execute("SELECT chao1_unseen, n_distinct, n_singletons FROM frontier_map "
                            "LIMIT 5").fetchall()
    finally:
        conn.close()
    assert rows
    for row in rows:
        assert row["chao1_unseen"] is None and row["n_distinct"] is None
        assert row["n_singletons"] is None


def test_the_axis_rotation_advances_so_other_faces_are_reached_next_pass(desk: Path) -> None:
    first = CT.build(budget_s=60.0, top_k=6)
    assert first["frontier"]["cursor"] == {CV.WORLD: 0, CV.FOREST: 0}
    stored = json.loads(CT.CURSOR.read_text(encoding="utf-8"))
    assert stored[CV.WORLD] == first["frontier"]["cursor_next"][CV.WORLD] != 0
    second = CT.build(budget_s=60.0, top_k=6)
    assert second["frontier"]["cursor"][CV.WORLD] == stored[CV.WORLD]
    assert len(first["frontier"]["scans"][CV.WORLD]) == CT.SUBSETS_PER_PASS
    first_axes = first["frontier"]["scans"][CV.WORLD][0]["axes"]
    second_axes = second["frontier"]["scans"][CV.WORLD][0]["axes"]
    assert first_axes != second_axes, "a pass that re-ranks the same face forever covers one face"
    assert first_axes == list(CT.WORLD_ROTATION[0])


def test_a_truncated_enumeration_says_so(desk: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(CT, "MAX_ENUMERATE", 7)
    doc = CT.build(budget_s=60.0, top_k=4)
    scans = doc["frontier"]["scans"][CV.WORLD]
    assert scans and scans[0]["truncated"] is True and scans[0]["enumerated"] == 7, \
        "a truncated scan that reports a clean count is worse than no scan at all"


# --------------------------------------------------------------------------- the box's own safety
def test_dry_run_writes_nothing(desk: Path) -> None:
    doc = CT.build(budget_s=60.0, dry_run=True, top_k=6)
    assert doc["dry_run"] is True
    for path in (CT.OUT, CT.CURSOR, CT.FLOORS):
        assert not path.exists(), f"{path} was written by a dry run"
    assert R.discoveries(limit=100) == [], "no discovery is recorded by a dry run"
    conn = R.connect()
    try:
        assert conn.execute("SELECT COUNT(*) FROM frontier_map").fetchone()[0] == 0
    finally:
        conn.close()
    assert doc["frontier"]["handed_to_the_machine"]["discoveries_seen"] > 0, \
        "a dry run still measures what it would have handed over"


def test_floors_ratchet_up_only_across_passes(desk: Path) -> None:
    CT.build(budget_s=60.0, top_k=6)
    floors = json.loads(CT.FLOORS.read_text(encoding="utf-8"))
    assert floors["world_cells"] > 0
    CT.FLOORS.write_text(json.dumps({**floors, "world_cells": floors["world_cells"] + 10_000}),
                         encoding="utf-8")
    doc = CT.build(budget_s=60.0, top_k=6)
    raised = json.loads(CT.FLOORS.read_text(encoding="utf-8"))
    assert raised["world_cells"] == floors["world_cells"] + 10_000, \
        "coverage floors ratchet UP only (L1.50): a lower measurement never lowers a floor"
    assert doc["floors"]["below_floor"]["world_cells"]["current"] == floors["world_cells"]


# ------------------------------------------------------------- the three named rows of LAWS 5f
def test_the_named_frontier_rows_are_explicit_rows_with_a_state(built: dict[str, Any]) -> None:
    rows = {r["label"]: r for r in built["frontier"]["named_examples"]}
    assert set(rows) == {"indonesia_nickel_china_cycle_aud_asia_risk_off",
                         "korea_semiconductor_supply_chain_jpy_asia",
                         "russia_energy_shipping_brent_eurusd",
                         "russia_energy_shipping_local_sources"}
    idn = rows["indonesia_nickel_china_cycle_aud_asia_risk_off"]
    assert idn["state"] == "UNOBSERVED" and idn["next_move"].startswith("hunt a source")
    assert idn["values"]["asset"] == "AUDUSD" and idn["values"]["regime"] == "risk_off"
    kor = rows["korea_semiconductor_supply_chain_jpy_asia"]
    assert kor["values"]["sector"] == "semiconductors"
    assert kor["state"] == "UNOBSERVED", "no candidate history on that exact cell today"
    forest_row = rows["russia_energy_shipping_local_sources"]
    assert forest_row["tensor"] == CV.FOREST
    assert forest_row["values"]["source_class"] == "physical_economy"
    assert forest_row["next_move"].startswith("hunt this ground")


def test_the_cli_runs_once_and_reports(desk: Path, capsys: pytest.CaptureFixture[str]) -> None:
    assert CT.main(["--once", "--budget-s", "30", "--dry-run", "--top", "4"]) == 0
    out = capsys.readouterr().out
    assert "coverage tensor: world" in out and "forest" in out
    assert "--dry-run: nothing written" in out
    assert "UNMEASURED:" in out
