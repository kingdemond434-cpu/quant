"""THE INGESTION-EXPLOITATION CONTRACT: a disposition for every ingested unit, or a discovery.

Every path the organ reads is redirected into `tmp_path` and the registry is a throwaway file
(`registry.set_path`), so no test here can touch the box's real ledger, tape or axes.

The tests that matter most are the ones that pin the REFUSALS. `exploitation_share` is a number
somebody will quote, so the two ways to fake it are fenced by name: a unit may not become
EXPLOITED because THIS organ handed it over (the denominator trick), and a unit with no ingestion
stamp may not claim the grace window and sit as PENDING forever.
"""
from __future__ import annotations

import json
import os
import sys
import time
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest

_DESK = Path(__file__).resolve().parents[1]
for _p in (str(_DESK), str(_DESK / "research"), str(_DESK.parent.parent)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from libs.moat import registry as R  # noqa: E402
from research import ingestion_ledger as IL  # noqa: E402

NOW = datetime(2026, 9, 17, 12, 0, tzinfo=UTC)
OLD = NOW - timedelta(days=9)
FRESH = NOW - timedelta(hours=2)

AXIS_SERIES = {"axis": "macro_state", "id": "fred_series", "at": "2026-09-16T00:00:00+00:00",
               "vintage_note": "revisions are not applied backwards",
               "series": {"VIXCLS": {"what": "volatility index", "points": [{"d": "2026-09-01",
                                                                             "v": 15.0}]},
                          "DGS10": {"what": "10 year yield", "points": [{"d": "2026-09-01",
                                                                         "v": 4.0}]}}}
AXIS_PANEL = {"axis": "positioning", "id": "cftc_cot_legacy", "at": "2026-09-16T00:00:00+00:00",
              "knowable_lag_days": 3, "symbols": ["EURUSD", "XAUUSD"],
              "rows": [{"symbol": "EURUSD", "knowable_at": "2026-09-09", "net_pct_oi": 0.2}]}
#: Two seat donations in two FILES. One file per row is the granularity the desk's own compiler
#: works at (`intel:<seat>:<file>`), so a converted handoff must credit its own row's file and
#: not the seat's whole directory.
INTEL_ONE = {"source": "factor_residual", "discoveries": [
    {"id": "resid-1", "symbol": "EURUSD", "family": "asia_momentum",
     "mechanism": "risk carried out of tokyo is repriced in london"}]}
INTEL_TWO = {"source": "factor_residual", "discoveries": [
    {"id": "resid-2", "symbol": "GBPUSD", "family": "level_breakout",
     "mechanism": "a breakout through the level runs the resting stops"}]}


def _write(path: Path, payload: Any, when: datetime | None = None) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(payload if isinstance(payload, str) else json.dumps(payload), "utf-8")
    if when is not None:
        stamp = when.timestamp()
        os.utime(path, (stamp, stamp))
    return path


@pytest.fixture
def desk(tmp_path, monkeypatch):
    """The contract pointed at a synthetic tree and a throwaway registry."""
    monkeypatch.setattr(R, "BACKUP", tmp_path / "no_backup")
    R.set_path(tmp_path / "alpha_registry.sqlite")
    paths = {
        "NORMALIZED": tmp_path / "moat" / "normalized_intel",
        "AXES": tmp_path / "axes", "TAPE_TICKS": tmp_path / "tape" / "ticks",
        "UNIVERSE": tmp_path / "universe", "MOAT_SERIES": tmp_path / "moat_series",
        "SHADOW_DIR": tmp_path / "shadow", "LIVE_LEDGER": tmp_path / "live_ledger.jsonl",
        "MACRO_REPORT": tmp_path / "MACRO_INTELLIGENCE.json",
        "LEDGER": tmp_path / "ingestion_ledger.jsonl",
        "OUT": tmp_path / "INGESTION_EXPLOITATION.json",
    }
    for name, path in paths.items():
        monkeypatch.setattr(IL, name, path)
    monkeypatch.setattr(IL, "INTEL_DIRS", (tmp_path / "intelligence",))
    # The downstream-consumer artifacts are REAL paths on the box. Left unredirected they would
    # make every test read the live allocator and cost surface, and a test that passes because of
    # what the box happens to hold is not a test.
    consumers = {state: tmp_path / f"{state}.json" for state in IL.CONSUMER_ARTIFACTS}
    monkeypatch.setattr(IL, "CONSUMER_ARTIFACTS", consumers)
    yield {"tmp": tmp_path, "paths": {**paths, **consumers}}
    R.set_path(None)


def _populate(desk, *, old: bool = True) -> None:
    """The synthetic tree. DECLARED stamps move with `old` too: a source's own knowable_at beats
    the file's mtime by design, so a 'fresh' tree with stale declarations is not a fresh tree."""
    tmp, p = desk["tmp"], desk["paths"]
    when = OLD if old else FRESH
    declared = when.isoformat()
    _write(p["NORMALIZED"] / "src_a" / "abc123.json",
           {"doc_id": "doc-1", "source_id": "src_a", "capture_sha": "abc123",
            "knowable_at": declared, "text": "a claim"}, when)
    _write(p["AXES"] / "fred.json", {**AXIS_SERIES, "at": declared}, when)
    _write(p["AXES"] / "cot.json", {**AXIS_PANEL, "at": declared}, when)
    _write(tmp / "intelligence" / "factor_residual" / "one.json", INTEL_ONE, when)
    _write(tmp / "intelligence" / "factor_residual" / "two.json", INTEL_TWO, when)
    day = when.date().isoformat()         # a tape day's own date IS its knowable stamp
    _write(p["TAPE_TICKS"] / "EURUSD" / f"{day}.parquet", "PAR1", when)
    _write(p["TAPE_TICKS"] / "NOKJPY" / f"{day}.parquet", "PAR1", when)
    _write(p["UNIVERSE"] / "EURUSD_H1.parquet", "PAR1", when)
    _write(p["UNIVERSE"] / "NOKJPY_H1.parquet", "PAR1", when)
    _write(p["MOAT_SERIES"] / "spread" / "EURUSD.parquet", "PAR1", when)
    _write(p["SHADOW_DIR"] / "ledger_EURUSD_asia.json", [], when)
    _write(p["LIVE_LEDGER"], json.dumps({"sleeve": "xau_scalp", "symbol": "XAUUSD",
                                         "r_multiple": 0.4}), when)


def _claim(conn, claim_id: str, kind: str, instruments: list[str]) -> None:
    conn.execute("INSERT INTO claims(claim_id, created_at, doc_id, source_id, text, language, "
                 "knowable_at, instruments_json, kind) VALUES(?,?,?,?,?,?,?,?,?)",
                 (claim_id, OLD.isoformat(), "doc-1", "src_a", "the ECB held rates", "en",
                  OLD.isoformat(), json.dumps(instruments), kind))
    conn.commit()


def _run(**kw: Any) -> dict[str, Any]:
    return IL.build(now=NOW, **kw)


# --------------------------------------------------------------------------- the units
def test_every_ingestion_kind_on_this_box_becomes_a_unit(desk):
    _populate(desk)
    conn = R.connect()
    _claim(conn, "claim-1", "news", ["EURUSD"])
    _claim(conn, "claim-2", "analysis", [])
    conn.close()
    doc = _run()
    kinds = doc["units_by_kind"]
    assert kinds["normalized_doc"] == 1
    assert kinds["axis_series"] == 4          # 2 fred series + 2 cot symbols
    assert kinds["intel_row"] == 2
    assert kinds["tape_day"] == 2
    assert kinds["universe_bars"] == 2
    assert kinds["moat_series"] == 1
    assert kinds["sleeve_ledger"] == 2        # the shadow ledger and the live ledger's own sleeve
    assert kinds["news_claim"] == 1 and kinds["claim"] == 1


def test_an_absent_source_is_a_named_gap_not_a_clean_sweep(desk):
    doc = _run()
    what = " ".join(g["what"] for g in doc["unmeasured"])
    why = " ".join(g["why"] for g in doc["unmeasured"])
    assert "normalized_intel" in what and "axes" in what and "ticks" in what
    assert "UNMEASURED, not zero" in why
    assert doc["units_scanned"] == 0
    assert doc["exploitation_share"] is None


# --------------------------------------------------------------------------- the dispositions
def test_a_candidate_that_names_the_instrument_exploits_its_bars_and_its_tape(desk):
    _populate(desk)
    R.enqueue_candidate(family="asia_momentum", symbol="EURUSD", params={"rr": 2.0},
                        origin="DESK", chart="H1")
    doc = _run()
    bars = doc["dispositions"]["universe_bars"]
    tape = doc["dispositions"]["tape_day"]
    assert bars["EXPLOITED"] == 1 and bars["STRANDED"] == 1
    assert tape["EXPLOITED"] == 1 and tape["STRANDED"] == 1


def test_a_discovery_that_names_a_document_exploits_it(desk):
    _populate(desk)
    R.record_discovery(source_id="src_a", source_type="collector", mechanism="a claim",
                       origin="EXTERNAL", payload={"doc_id": "doc-1"})
    doc = _run()
    assert doc["dispositions"]["normalized_doc"]["EXPLOITED"] == 1


def test_a_blocked_discovery_is_a_lawful_disposition_not_a_stranding(desk):
    _populate(desk)
    did, _ = R.record_discovery(source_id="intel:factor_residual", source_type="intelligence",
                                mechanism="unknown", origin="EXTERNAL",
                                payload={"unit_id": "resid-1"})
    R.set_discovery_state(did, "BLOCKED", reason="no registered family implements it")
    doc = _run()
    rows = doc["dispositions"]["intel_row"]
    assert rows["BLOCKED"] == 1 and rows["STRANDED"] == 1


def test_a_freshly_ingested_unit_is_pending_and_an_old_one_is_stranded(desk):
    _populate(desk, old=False)
    doc = _run()
    assert doc["totals"]["PENDING"] == doc["units_scanned"]
    assert doc["totals"]["STRANDED"] == 0
    assert doc["exploitation_share"] is None          # nothing is past grace: UNMEASURED
    assert any("UNMEASURED" in g["why"] for g in doc["unmeasured"])


def test_a_unit_with_no_ingestion_stamp_may_not_claim_the_grace_window(desk):
    unit = IL.Unit("intel_row", "nowhere#1", at="")
    verdict, why = IL.disposition(unit, IL.Index(), set(), NOW, 24.0)
    assert verdict == "STRANDED"
    assert "UNMEASURED recency" in why


def test_macro_intelligence_consumption_is_its_own_disposition(desk):
    _populate(desk)
    _write(desk["paths"]["MACRO_REPORT"],
           {"consumed_units": ["axis_series:fred:VIXCLS", "axis_series:cot:EURUSD"]})
    doc = _run()
    assert doc["dispositions"]["axis_series"]["EXPLOITED_MACRO"] == 2


def test_the_exploitation_share_is_over_units_past_the_grace_window(desk):
    _populate(desk)
    R.enqueue_candidate(family="asia_momentum", symbol="EURUSD", params={}, origin="DESK",
                        chart="H1")
    doc = _run()
    t = doc["totals"]
    expected = (t["EXPLOITED"] + t["EXPLOITED_MACRO"] + t["BLOCKED"]) / doc["units_past_grace"]
    assert doc["pass_share"] == pytest.approx(expected)
    assert doc["units_past_grace"] == doc["units_scanned"] - t["PENDING"]
    # With an empty ledger the population IS this pass, so the two agree; they part company only
    # once the rotating cursor has shown the ledger units this pass did not reach.
    assert doc["exploitation_share"] == pytest.approx(expected)
    assert doc["population"]["units"] == doc["units_scanned"]


def test_the_fenced_share_is_the_population_not_the_rotating_slice(desk):
    """One pass heavy on seat rows and the next heavy on tape are the same tree; a ratchet on the
    slice would be a ratchet on where the cursor landed."""
    _populate(desk)
    R.enqueue_candidate(family="asia_momentum", symbol="EURUSD", params={}, origin="DESK",
                        chart="H1")
    monkey = dict(IL.KIND_CAP)
    try:
        IL.KIND_CAP["intel_row"] = 0          # a slice with no seat rows at all
        first = _run()
        IL.KIND_CAP["intel_row"] = 600
        IL.KIND_CAP["tape_day"] = 0           # and one with no tape
        second = _run()
    finally:
        IL.KIND_CAP.clear()
        IL.KIND_CAP.update(monkey)
    assert second["population"]["units"] > second["units_scanned"]
    assert second["pass_share"] != pytest.approx(second["exploitation_share"])
    assert abs(second["exploitation_share"] - first["exploitation_share"]) \
        < abs(second["pass_share"] - first["pass_share"])


# --------------------------------------------------------------------------- the handoff
def test_a_stranded_unit_becomes_a_discovery_exactly_once(desk):
    _populate(desk)
    first = _run()
    assert first["stranded_handed_to_compiler"] == first["totals"]["STRANDED"] > 0
    handed = R.discoveries(limit=500)
    mine = [d for d in handed if d["source_type"] == "ingestion"]
    assert len(mine) == first["stranded_handed_to_compiler"]
    assert {d["state"] for d in mine} == {"UNPROCESSED"}
    payload = json.loads(mine[0]["payload_json"])
    assert payload["why"] == "ingested and unexploited"
    assert payload["unit_kind"] and payload["unit_id"]

    second = _run()
    assert second["stranded_handed_to_compiler"] == 0
    assert second["stranded_already_handed"] == second["totals"]["STRANDED"]
    assert len([d for d in R.discoveries(limit=500) if d["source_type"] == "ingestion"]) \
        == len(mine)


def test_the_organs_own_handoff_does_not_make_the_unit_exploited(desk):
    """The denominator trick, fenced: measuring may not be what closes the debt."""
    _populate(desk)
    first = _run()
    second = _run()
    assert second["totals"]["STRANDED"] == first["totals"]["STRANDED"]
    assert second["exploitation_share"] == first["exploitation_share"]
    assert second["index"]["own_handoffs_held_out"] > 0


def test_a_handoff_that_actually_converted_does_count(desk):
    _populate(desk)
    _run()
    mine = [d for d in R.discoveries(limit=500) if d["source_type"] == "ingestion"]
    target = next(d for d in mine if json.loads(d["payload_json"])["unit_kind"] == "intel_row")
    R.set_discovery_state(target["discovery_id"], "COMPILED", compiled_cells=4)
    doc = _run()
    assert doc["dispositions"]["intel_row"]["EXPLOITED"] == 1


# ------------------------------------------------- the downstream state and the three labels
def test_every_qualified_datum_carries_exactly_one_downstream_state(desk):
    _populate(desk)
    doc = _run()
    assert set(doc["downstream_states"]) == set(IL.DOWNSTREAM_STATES)
    assert sum(doc["downstream_states"].values()) == doc["units_scanned"]
    assert doc["downstream_rule"] == IL.DOWNSTREAM_RULE
    assert "No qualified datum is allowed to sit in storage" in IL.DOWNSTREAM_RULE
    assert "ACCESS_UNCLEAR included" in IL.DOWNSTREAM_RULE
    rows = [json.loads(line) for line in
            desk["paths"]["LEDGER"].read_text("utf-8").strip().splitlines()]
    assert all(r["downstream_state"] in IL.DOWNSTREAM_STATES for r in rows)
    assert all(r["downstream_why"] for r in rows)


def test_the_state_is_awaiting_experiment_when_no_consumer_has_reached_it(desk):
    _populate(desk)
    doc = _run()
    assert doc["downstream_states"]["AWAITING_EXPERIMENT"] > 0
    row = next(json.loads(line) for line in
               desk["paths"]["LEDGER"].read_text("utf-8").strip().splitlines()
               if json.loads(line)["downstream_state"] == "AWAITING_EXPERIMENT")
    assert "an experiment is owed" in row["downstream_why"]


@pytest.mark.parametrize(("state", "artifact"), [
    ("PORTFOLIO_INPUT", "PORTFOLIO_INPUT"), ("EXECUTION_INPUT", "EXECUTION_INPUT"),
    ("INTERACTION_INPUT", "INTERACTION_INPUT")])
def test_an_artifact_that_names_a_datum_gives_it_that_consumer_state(desk, state, artifact):
    _populate(desk)
    _write(desk["paths"][artifact], {"rows": [{"symbol": "NOKJPY"}]})
    doc = _run()
    assert doc["downstream_states"][state] > 0


def test_macro_consumption_is_the_world_model_state(desk):
    _populate(desk)
    _write(desk["paths"]["MACRO_REPORT"], {"consumed_units": ["axis_series:fred:VIXCLS"]})
    doc = _run()
    assert doc["downstream_states"]["WORLD_MODEL_INPUT"] == 1


def test_a_blocked_discovery_is_negative_knowledge(desk):
    _populate(desk)
    did, _ = R.record_discovery(source_id="intel:factor_residual", source_type="intelligence",
                                mechanism="unknown", origin="EXTERNAL",
                                payload={"unit_id": "resid-1"})
    R.set_discovery_state(did, "BLOCKED", reason="no registered family implements it")
    doc = _run()
    assert doc["downstream_states"]["NEGATIVE_KNOWLEDGE"] == 1


def test_a_killed_candidate_leaves_its_datum_retired_with_evidence(desk):
    _populate(desk)
    cid, _ = R.enqueue_candidate(family="carry", symbol="NOKJPY", params={}, origin="DESK",
                                 chart="H1")
    R.mark_candidate(cid, "judged", terminal_gate="deflated_sharpe", survived=0,
                     judged_at=OLD.isoformat())
    doc = _run()
    assert doc["downstream_states"]["RETIRED_WITH_EVIDENCE"] > 0
    assert doc["predictive_states"]["NOT_PREDICTIVE"] > 0


def test_a_survivor_makes_its_datum_predictive(desk):
    _populate(desk)
    cid, _ = R.enqueue_candidate(family="carry", symbol="NOKJPY", params={}, origin="DESK",
                                 chart="H1")
    R.mark_candidate(cid, "survived", terminal_gate="forward", survived=1)
    doc = _run()
    assert doc["predictive_states"]["PREDICTIVE"] > 0


def test_the_three_labels_are_independent_and_all_present(desk):
    _populate(desk)
    doc = _run()
    assert set(doc["access_labels"]) <= set(IL.ACCESS_LABELS)
    assert set(doc["credibility"]) <= set(IL.CREDIBILITY_LABELS)
    assert set(doc["predictive_states"]) <= set(IL.PREDICTIVE_STATES)
    for name in ("access_labels", "credibility", "predictive_states"):
        assert sum(doc[name].values()) == doc["units_scanned"]
    assert doc["access_labels"]["OPEN_DATA"] == 4          # the two axis files
    assert doc["access_labels"]["USER_SUBMITTED"] == 2     # the seat donations
    assert doc["credibility"]["AUTHORITATIVE"] >= 4


def test_a_contradicted_claim_is_kept_as_a_narrative_feature_never_deleted(desk):
    _populate(desk)
    conn = R.connect()
    _claim(conn, "claim-1", "news", ["EURUSD"])
    conn.execute("INSERT INTO claim_edges(from_claim, to_claim, relation, created_at) "
                 "VALUES(?,?,?,?)", ("claim-0", "claim-1", "CONTRADICTS", OLD.isoformat()))
    conn.commit()
    conn.close()
    doc = _run()
    assert doc["credibility"]["CONTRADICTED"] == 1
    assert doc["predictive_states"]["NARRATIVE_FEATURE"] == 1
    assert doc["units_by_kind"]["news_claim"] == 1        # kept, not dropped
    row = next(json.loads(line) for line in
               desk["paths"]["LEDGER"].read_text("utf-8").strip().splitlines()
               if json.loads(line)["kind"] == "news_claim")
    assert row["access_label"] == "PUBLIC"              # credibility never moves access
    assert row["credibility"] == "CONTRADICTED"
    assert row["predictive_state"] == "NARRATIVE_FEATURE"


def test_an_unclear_source_is_qualified_labelled_and_handed_to_the_compiler(desk):
    """LAWS 5e (2026-09-23). This test asserted the opposite until then: an ACCESS_UNCLEAR row
    was QUARANTINED -- no downstream state, never handed to the compiler, its content unconsumed.
    That was a discovery brake, and the row it silenced was an INGESTED-AND-UNEXPLOITED datum the
    desk already held. The label survives; the quarantine does not."""
    _populate(desk)
    conn = R.connect()
    conn.execute("INSERT INTO sources(source_id, status, first_seen) VALUES(?,?,?)",
                 ("src_a", "walled", OLD.isoformat()))
    conn.commit()
    conn.close()
    doc = _run()
    assert doc["access_labels"]["ACCESS_UNCLEAR"] == 1
    assert doc["quarantined"] == 0, "the access quarantine was deleted on 2026-09-23"
    assert not IL.QUARANTINED_ACCESS
    assert "ACCESS_UNCLEAR" in IL.QUALIFIED_ACCESS
    row = next(json.loads(line) for line in
               desk["paths"]["LEDGER"].read_text("utf-8").strip().splitlines()
               if json.loads(line)["kind"] == "normalized_doc")
    assert row["downstream_state"] in IL.DOWNSTREAM_STATES
    assert "metadata kept, content not consumed" not in (row["downstream_why"] or "")


def test_a_refused_access_label_never_becomes_an_alpha_input(desk):
    unit = IL.Unit("normalized_doc", "leak-1", access_label="CONFIDENTIAL_MNPI")
    state, why = IL.downstream_state(unit, IL.Index(), set(), {})
    assert state is None
    assert "material non-public information" in why
    assert unit.refused and not unit.qualified
    conn = R.connect()
    try:
        assert IL.hand_to_compiler([unit], conn) == (0, 0)
        assert R.discoveries(limit=10, conn=conn) == []
    finally:
        conn.close()


def test_a_datum_re_ingested_with_no_consumer_is_a_data_stranding_defect(desk):
    _populate(desk)
    first = _run()
    assert first["n_stranded_data"] == 0
    assert first["stranded_data_measured"] is False      # one pass cannot show a re-ingestion
    assert first["passes"] == 1
    second = _run()
    assert second["passes"] == 2 and second["stranded_data_measured"] is True
    assert second["n_stranded_data"] > 0
    row = second["stranded_data"][0]
    assert row["ingestions"] >= IL.STRANDING_INGESTIONS
    assert row["access_label"] in IL.QUALIFIED_ACCESS
    assert {"unit_id", "kind", "dataset", "path", "predictive_state"} <= set(row)
    third = _run()
    assert third["stranded_data"][0]["ingestions"] >= 3


def test_a_datum_that_reaches_a_consumer_leaves_the_stranding_count(desk):
    _populate(desk)
    _run()
    second = _run()
    stranded = {r["unit_id"] for r in second["stranded_data"]}
    assert stranded
    _write(desk["paths"]["MACRO_REPORT"],
           {"consumed_units": [f"{r['kind']}:{r['unit_id']}" for r in second["stranded_data"]]})
    third = _run()
    assert not ({r["unit_id"] for r in third["stranded_data"]} & stranded)


# --------------------------------------------------------------------------- the artifacts
def test_the_jsonl_is_appended_one_row_per_unit_per_pass(desk):
    _populate(desk)
    first = _run()
    rows = desk["paths"]["LEDGER"].read_text("utf-8").strip().splitlines()
    assert len(rows) == first["units_scanned"]
    row = json.loads(rows[0])
    assert set(row) >= {"at", "kind", "dataset", "unit_id", "disposition", "why", "pit",
                        "downstream_state", "downstream_why", "access_label", "credibility",
                        "predictive_state", "ingestions"}
    _run()
    assert len(desk["paths"]["LEDGER"].read_text("utf-8").strip().splitlines()) \
        == 2 * first["units_scanned"]


def test_the_report_carries_a_per_dataset_block_with_its_pit_basis(desk):
    _populate(desk)
    doc = _run()
    datasets = doc["datasets"]
    assert "axis:fred" in datasets and "axis:cot" in datasets
    assert datasets["axis:fred"]["units"] == 2
    assert datasets["axis:fred"]["pit_stamped"] == 2          # the file declares a vintage note
    assert datasets["tape_day"]["pit_stamped"] == 2           # the day IS the knowable date
    assert datasets["moat_series"]["pit_stamped"] == 0
    assert "UNMEASURED" in datasets["moat_series"]["pit_basis"]
    assert sum(b["units"] for b in datasets.values()) == doc["units_scanned"]


def test_dry_run_writes_nothing_and_records_nothing(desk):
    _populate(desk)
    doc = _run(dry_run=True)
    assert doc["totals"]["STRANDED"] > 0
    assert doc["stranded_handed_to_compiler"] == 0
    assert not desk["paths"]["LEDGER"].exists()
    assert not desk["paths"]["OUT"].exists()
    assert R.discoveries(limit=50) == []


def test_the_budget_rotates_so_a_capped_pass_still_reaches_everything(desk):
    _populate(desk)
    monkey = dict(IL.KIND_CAP)
    try:
        IL.KIND_CAP["tape_day"] = 1
        first = _run()
        second = _run()
    finally:
        IL.KIND_CAP.clear()
        IL.KIND_CAP.update(monkey)
    seen = {json.loads(line)["unit_id"] for line in
            desk["paths"]["LEDGER"].read_text("utf-8").strip().splitlines()
            if json.loads(line)["kind"] == "tape_day"}
    assert first["units_by_kind"]["tape_day"] == 1
    assert second["not_reached"]["tape_day"] == 1
    assert seen == {"EURUSD/2026-09-08", "NOKJPY/2026-09-08"}


def test_a_huge_axis_panel_is_read_by_header_not_parsed(desk, monkeypatch):
    """`bis.json` is 81 MB on the box and 271 MB parsed; the header carries what this organ
    needs, and a full parse hourly is how a ledger becomes the outage on an 8 GB machine."""
    monkeypatch.setattr(IL, "AXIS_FULL_BYTES", 256)
    path = _write(desk["paths"]["AXES"] / "bis.json",
                  json.dumps({"axis": "policy", "at": "2026-09-12T00:00:00+00:00",
                              "shape": "(symbol, knowable_at, carry_differential)",
                              "symbols": ["EURUSD", "AUDJPY"],
                              "rows": [{"symbol": "EURUSD", "knowable_at": "1999-01"}] * 40},
                             indent=1), OLD)
    assert path.stat().st_size > 256
    header = IL._axis_header(path)
    assert header["_head_only"] is True
    assert header["symbols"] == ["EURUSD", "AUDJPY"]
    assert "rows" not in header
    units = IL.axis_units(path)
    assert {u.unit_id for u in units} == {"bis:EURUSD", "bis:AUDJPY"}
    assert all(u.pit for u in units)          # the file's own `shape` names knowable_at


def test_the_pass_is_bounded_by_its_deadline(desk):
    _populate(desk)
    started = time.monotonic()
    doc = _run(budget_s=0.0)
    assert time.monotonic() - started < 30.0
    assert doc["budget"]["reached_deadline"] is True
    assert "intel_row" not in doc["units_by_kind"]     # the first kind the deadline gates
