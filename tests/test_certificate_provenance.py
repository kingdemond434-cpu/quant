"""THE PROVENANCE CHAIN MUST NOT BE BREAKABLE BY A TRANSFORM.

The recurring failure on this desk is a fact that exists in one place and is silently lost by the
next organ: three copies of "what counts as code" halted trading for seventeen days, two copies of
"what counts as a ten-gate pass" voided 158 certificates. These tests exist so provenance does not
become the third.

Each `test_drop_*` removes the producer from exactly ONE link of the chain and asserts the desk
says UNMEASURED rather than naming somebody. The chain is:

    docket row / registry candidate / hypothesis-graph node   the producer is recorded here
    gate verdict                                              carries the graph edge
    certificate                                               carries neither, and never will --
                                                              the gauntlet that writes it is sealed

And `test_symbol_family_is_never_an_attribution` pins the specific bug this module replaced: a
fallback that matched on symbol and family alone reported `coverage 1.0` over 52 certificates that
between 105 and 437 candidates each could have produced.
"""
from __future__ import annotations

import json
import sqlite3
import sys
from pathlib import Path
from typing import Any

import pytest

ROOT = Path(__file__).resolve().parents[1]
DESK = ROOT / "desks" / "mt5"
for _p in (str(ROOT), str(DESK), str(DESK / "research")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

cp = pytest.importorskip("certificate_provenance")


SYM, FAM = "EURAUD", "overnight_gap_decay"
PARAMS: dict[str, Any] = {"rr": 2.0, "ttl_bars": 24}


def _cell() -> str:
    cid = cp._cell_id()
    assert cid is not None, "the desk's one cell identity must be importable"
    return str(cid({"sym": SYM, "family": FAM, "params": PARAMS}))


def _registry(tmp: Path, *, producer: str | None, n_decoys: int = 0) -> Path:
    """A registry holding one candidate for our cell, plus decoys sharing symbol and family."""
    db = tmp / "alpha_registry.sqlite"
    c = sqlite3.connect(db)
    c.execute("CREATE TABLE research_candidates (id TEXT, symbol TEXT, family TEXT, "
              "params_json TEXT, producer TEXT, region TEXT, created_at TEXT, status TEXT, "
              "donated_cell TEXT, judged_at TEXT)")
    c.execute("CREATE TABLE discoveries (discovery_id TEXT, producer TEXT, region TEXT)")
    if producer is not None:
        c.execute("INSERT INTO research_candidates VALUES (?,?,?,?,?,?,?,?,?,?)",
                  ("cand_1", SYM, FAM, json.dumps(PARAMS), producer, "Japan",
                   "2026-09-23T00:00:00+00:00", "judged", "cell_1", "2026-09-23T01:00:00+00:00"))
    for i in range(n_decoys):
        # SAME symbol and family, DIFFERENT params -- a different cell, a different producer.
        c.execute("INSERT INTO research_candidates VALUES (?,?,?,?,?,?,?,?,?,?)",
                  (f"cand_decoy_{i}", SYM, FAM, json.dumps({"rr": 3.0 + i}),
                   f"decoy_producer_{i}", "Europe", "2026-09-22T00:00:00+00:00", "judged",
                   f"cell_d{i}", "2026-09-22T01:00:00+00:00"))
    c.commit()
    c.close()
    return db


def _wire(monkeypatch: pytest.MonkeyPatch, tmp: Path, *, db: Path | None = None,
          docket: list[dict[str, Any]] | None = None, verdicts: list[dict[str, Any]] | None = None,
          graph: list[dict[str, Any]] | None = None) -> None:
    """Point every store the module reads at this test's own files, and nowhere else."""
    cell = _cell()
    canon = tmp / "canon.json"
    canon.write_text(json.dumps({"n": 1, "survivors": {
        f"external.{cell}": {"hunt": "external", "cell": cell, "sym": SYM,
                             "gated_at": "2026-09-24T00:00:00+00:00"}}}), encoding="utf-8")
    dpath, vpath, gpath = tmp / "docket.json", tmp / "verdicts.jsonl", tmp / "graph.jsonl"
    dpath.write_text(json.dumps(docket or []), encoding="utf-8")
    vpath.write_text("".join(json.dumps(r) + "\n" for r in (verdicts or [])), encoding="utf-8")
    gpath.write_text("".join(json.dumps(r) + "\n" for r in (graph or [])), encoding="utf-8")
    monkeypatch.setattr(cp, "CANON", canon)
    monkeypatch.setattr(cp, "SURVIVORS", tmp / "absent_survivors.json")
    monkeypatch.setattr(cp, "DOCKET", dpath)
    monkeypatch.setattr(cp, "VERDICTS", vpath)
    monkeypatch.setattr(cp, "GRAPH", gpath)
    monkeypatch.setattr(cp, "REGISTRY", db if db is not None else tmp / "absent.sqlite")
    monkeypatch.setattr(cp, "RECORD", tmp / "certificate_provenance.json")
    monkeypatch.setattr(cp, "TABLE", tmp / "PRODUCER_CONVERSION.json")


def _only(doc: dict[str, Any]) -> dict[str, Any]:
    recs = doc["records"]
    assert len(recs) == 1, recs
    return next(iter(recs.values()))


def _docket_row(producer: str | None) -> dict[str, Any]:
    """A docket row. `producer=None` strips BOTH provenance fields: `source` is a producer name
    too (`breadth_sweep/vol_transition`, `moat_registry`), so a test that meant to remove the
    link and left it behind would pass while the link was still there."""
    row: dict[str, Any] = {"symbol": SYM, "family": FAM, "params": PARAMS, "timeframe": "H1",
                           "candidate_id": "cand_1", "first_seen": "2026-09-23T00:00:00+00:00"}
    if producer is not None:
        row["producer"] = producer
        row["source"] = "external_discoveries"
    return row


# ------------------------------------------------------------------- the chain, link by link

def test_full_chain_names_one_producer(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Every link carries the same producer: the certificate is ATTRIBUTED, and named."""
    _wire(monkeypatch, tmp_path, db=_registry(tmp_path, producer="miner:deep_forest"),
          docket=[_docket_row("miner:deep_forest")])
    rec = _only(cp.refresh(budget_s=30.0))
    assert rec["verdict"] == cp.ATTRIBUTED
    assert rec["producer"] == "miner:deep_forest"
    assert set(rec["routes"]) >= {"registry_identity", "docket"}


def test_drop_registry_stamp_falls_back_to_the_docket(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """The birth stamp is gone from the registry; the judge's own docket still names it."""
    _wire(monkeypatch, tmp_path, db=_registry(tmp_path, producer=""),
          docket=[_docket_row("miner:deep_forest")])
    rec = _only(cp.refresh(budget_s=30.0))
    assert rec["verdict"] == cp.ATTRIBUTED
    assert rec["producer"] == "miner:deep_forest"
    assert rec["routes"] == ["docket"]


def test_drop_every_link_is_unmeasured_never_a_guess(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """THE CORE PROPERTY. No link names a producer -> UNMEASURED with a reason, and no name."""
    _wire(monkeypatch, tmp_path, db=_registry(tmp_path, producer="", n_decoys=40),
          docket=[_docket_row(None)])
    doc = cp.refresh(budget_s=30.0)
    rec = _only(doc)
    assert rec["verdict"] == cp.UNMEASURED
    assert rec["producer"] is None
    assert rec["why"], "an UNMEASURED verdict without a reason is silence, not a measurement"
    assert doc["coverage"]["named"] == 0
    assert doc["coverage"]["unnamed"] == 1


def test_symbol_family_is_never_an_attribution(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """THE BUG THIS MODULE REPLACED. Forty candidates share the symbol and family and NONE is the
    cell; the answer must be UNMEASURED, never one of the forty."""
    _wire(monkeypatch, tmp_path, db=_registry(tmp_path, producer=None, n_decoys=40))
    rec = _only(cp.refresh(budget_s=30.0))
    assert rec["verdict"] == cp.UNMEASURED
    assert rec["producer"] is None
    assert "decoy_producer_0" not in json.dumps(rec)


def test_verdict_graph_edge_carries_provenance_across_the_judge(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """The registry and the docket are both silent; the verdict's `graph_id` still reaches the
    node that names the source. This is the link that survives the sealed gauntlet."""
    cell = _cell()
    _wire(monkeypatch, tmp_path, db=_registry(tmp_path, producer=""),
          docket=[_docket_row(None)],
          verdicts=[{"cell": cell, "graph_id": "node_abc", "passed": True}],
          graph=[{"id": "node_abc", "source": "seat:kimi", "symbol": SYM, "family": FAM,
                  "params": PARAMS, "at": "2026-09-20T00:00:00+00:00"}])
    rec = _only(cp.refresh(budget_s=30.0))
    assert rec["producer"] == "seat:kimi"
    assert set(rec["routes"]) >= {"verdict_graph", "graph_identity"}


def test_co_discovery_is_first_claim_with_every_claimant_listed(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Two producers name the SAME cell. The earlier one is credited and both are recorded --
    a co-discovery is not a broken trail and must not be reported as one."""
    cell = _cell()
    _wire(monkeypatch, tmp_path, db=_registry(tmp_path, producer="miner:late"),
          docket=[_docket_row(None)],
          graph=[{"id": "n1", "source": "miner:early", "symbol": SYM, "family": FAM,
                  "params": PARAMS, "at": "2026-01-01T00:00:00+00:00"}])
    rec = _only(cp.refresh(budget_s=30.0))
    assert rec["verdict"] == cp.FIRST_CLAIM
    assert rec["producer"] == "miner:early"
    assert set(rec["claimants"]) == {"miner:early", "miner:late"}
    del cell


def test_a_tie_is_ambiguous_and_never_broken(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Two claimants, no recorded times at all: the tie is recorded, not resolved."""
    _wire(monkeypatch, tmp_path, db=_registry(tmp_path, producer=""),
          docket=[dict(_docket_row("miner:a"), first_seen=None, available_time=None)],
          graph=[{"id": "n1", "source": "miner:b", "symbol": SYM, "family": FAM,
                  "params": PARAMS}])
    rec = _only(cp.refresh(budget_s=30.0))
    assert rec["verdict"] == cp.AMBIGUOUS
    assert rec["producer"] is None
    assert set(rec["claimants"]) == {"miner:a", "miner:b"}


def test_record_and_table_are_written_together(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """One pass writes both artifacts, so the table can never describe a different record."""
    _wire(monkeypatch, tmp_path, db=_registry(tmp_path, producer="miner:deep_forest"),
          docket=[_docket_row("miner:deep_forest")],
          verdicts=[{"cell": _cell(), "passed": True, "terminal_gate": "PASSED"}])
    doc = cp.refresh(budget_s=30.0)
    table = cp.write(doc)
    assert cp.RECORD.exists() and cp.TABLE.exists()
    on_disk = json.loads(cp.RECORD.read_text(encoding="utf-8"))
    assert on_disk["coverage"]["named"] == 1
    rows = {r["producer"]: r for r in table["producers"]}
    assert rows["miner:deep_forest"]["certificates"] == 1
    assert rows["miner:deep_forest"]["candidates"] == 1
    assert rows["miner:deep_forest"]["judged"] == 1
    assert table["totals"]["certificates_named"] == 1


def test_judged_never_contradicts_certificates(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """THE COLUMN THAT LIED. `judged_at` gave `external` 1,246 judged cells and gave every
    producer holding a certificate ZERO -- a row saying a producer earned 68 certificates having
    never been judged. `judged` is now the verdict ledger joined by the SAME exact identity the
    certificates use, and `judged_at` is published beside it under its own name."""
    db = _registry(tmp_path, producer="miner:deep_forest")
    c = sqlite3.connect(db)
    # The contaminated stamp: a DIFFERENT producer's row carries judged_at for our cell's verdict.
    c.execute("INSERT INTO research_candidates VALUES (?,?,?,?,?,?,?,?,?,?)",
              ("cand_wrong", "XAUUSD", "carry", json.dumps({"rr": 9.0}), "external", "",
               "2026-09-01T00:00:00+00:00", "judged", "", "2026-09-02T00:00:00+00:00"))
    c.commit()
    c.close()
    _wire(monkeypatch, tmp_path, db=db, docket=[_docket_row("miner:deep_forest")],
          verdicts=[{"cell": _cell(), "passed": True}])
    table = cp.write(cp.refresh(budget_s=30.0))
    rows = {r["producer"]: r for r in table["producers"]}
    assert rows["miner:deep_forest"]["judged"] == 1
    assert rows["miner:deep_forest"]["certificates"] == 1
    # `external` was never judged on any cell the ledger names, whatever its judged_at says.
    assert rows["external"]["judged"] == 0
    assert rows["external"]["judged_stamped"] == 1
    for r in table["producers"]:
        if r["certificates"] and isinstance(r["judged"], int):
            assert r["judged"] >= 1, (
                f"{r['producer']} holds {r['certificates']} certificate(s) and reads "
                f"{r['judged']} judged -- a certificate cannot be earned unjudged")


def test_a_final_record_is_never_recomputed(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """A certificate is immutable once minted, so a second pass must not pay for the routes."""
    _wire(monkeypatch, tmp_path, db=_registry(tmp_path, producer="miner:deep_forest"),
          docket=[_docket_row("miner:deep_forest")])
    cp.write(cp.refresh(budget_s=30.0))
    again = cp.refresh(budget_s=30.0)
    assert again["pending"] == 0
    assert again["routes"] == {}
    assert _only(again)["producer"] == "miner:deep_forest"


# ------------------------------------------------------------------------------------ the fence

def test_the_fence_sees_a_certificate_with_no_birth_record(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """A certificate minted with nothing naming it must be visible IMMEDIATELY, not next sweep."""
    import importlib
    cb = importlib.import_module("scripts.check_birth_obligations")
    cell = _cell()
    (tmp_path / "desks" / "mt5" / "data").mkdir(parents=True)
    (tmp_path / "desks" / "mt5" / "data" / "UNIVERSAL_SURVIVORS.canon.json").write_text(
        json.dumps({"n": 1, "survivors": {f"external.{cell}": {"hunt": "external", "cell": cell}}}),
        encoding="utf-8")
    objects, ok, why = cb._certificate_birth(tmp_path)
    assert objects == {f"certificate:external.{cell}"}
    assert ok == set(), "a certificate with no record must NOT satisfy the obligation"
    assert "no birth record" in why

    rec = {"records": {cell: {"verdict": cp.UNMEASURED, "producer": None,
                              "why": "no exact identity route reaches this cell"}}}
    (tmp_path / "desks" / "mt5" / "data" / "certificate_provenance.json").write_text(
        json.dumps(rec), encoding="utf-8")
    objects, ok, why = cb._certificate_birth(tmp_path)
    assert ok == objects, "UNMEASURED WITH A REASON satisfies the obligation (L1.28a)"

    rec["records"][cell] = {"verdict": cp.UNMEASURED, "producer": None, "why": ""}
    (tmp_path / "desks" / "mt5" / "data" / "certificate_provenance.json").write_text(
        json.dumps(rec), encoding="utf-8")
    objects, ok, why = cb._certificate_birth(tmp_path)
    assert ok == set(), "a verdict with no reason is silence, and silence is the defect"


def test_the_fence_axis_is_registered() -> None:
    """The clause must be an AXIS, not a function nothing calls."""
    import importlib
    cb = importlib.import_module("scripts.check_birth_obligations")
    names = {a.name for a in cb.AXES}
    assert "certificate_birth" in names
    axis = next(a for a in cb.AXES if a.name == "certificate_birth")
    assert axis.source == "desks/mt5/data/certificate_provenance.json"


# ------------------------------------------------ the SOURCE lineage, and coverage of TODAY's store

def _cell_of(sym: str, params: dict[str, Any]) -> str:
    return str(cp._cell_id()({"sym": sym, "family": FAM, "params": params}))


def _wire_many(monkeypatch: pytest.MonkeyPatch, tmp: Path, certs: dict[str, dict[str, Any]],
               docket: list[dict[str, Any]], *, db: Path | None = None) -> None:
    """Several certificates at once; the graph and verdict ledger present but empty."""
    canon = tmp / "canon.json"
    canon.write_text(json.dumps({"n": len(certs), "survivors": certs}), encoding="utf-8")
    dpath, vpath, gpath = tmp / "docket.json", tmp / "verdicts.jsonl", tmp / "graph.jsonl"
    dpath.write_text(json.dumps(docket), encoding="utf-8")
    vpath.write_text("", encoding="utf-8")
    gpath.write_text("", encoding="utf-8")
    for name, val in (("CANON", canon), ("SURVIVORS", tmp / "absent_survivors.json"),
                      ("DOCKET", dpath), ("VERDICTS", vpath), ("GRAPH", gpath),
                      ("REGISTRY", db if db is not None else tmp / "absent.sqlite"),
                      ("RECORD", tmp / "certificate_provenance.json"),
                      ("TABLE", tmp / "PRODUCER_CONVERSION.json")):
        monkeypatch.setattr(cp, name, val)


def _three(tmp: Path) -> tuple[dict[str, dict[str, Any]], list[dict[str, Any]], list[str]]:
    """Three certificates: one whose docket row names its web source, one whose donation names
    no source, and one whose docket row is gone -- the three places a lineage can end."""
    p_url = {"rr": 2.0, "ttl_bars": 24}
    p_don = {"rr": 3.0, "ttl_bars": 9}
    p_gone = {"rr": 4.0, "ttl_bars": 5}
    cells = [_cell_of("EURAUD", p_url), _cell_of("GBPJPY", p_don), _cell_of("XAUUSD", p_gone)]
    certs = {f"external.{c}": {"hunt": "external", "cell": c, "sym": c.split(".")[0],
                               "gated_at": "2026-09-24T00:00:00+00:00"} for c in cells}
    docket = [
        {"symbol": "EURAUD", "family": FAM, "params": p_url, "producer": "miner:deep_forest",
         "source": "deep_forest_cn", "candidate_id": "cand_url",
         "first_seen": "2026-09-20T00:00:00+00:00",
         "source_url": "https://example.org/forum/thread/1"},
        {"symbol": "GBPJPY", "family": FAM, "params": p_don,
         "producer": "orthogonal_candidates.json",
         "source": "orthogonal_sweep:overnight_gap_decay", "candidate_id": "cand_don",
         "first_seen": "2026-09-21T00:00:00+00:00"},
    ]
    return certs, docket, cells


def test_every_current_certificate_gets_a_row_and_a_lineage(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """THE #104 DEFECT: 20 of 52 current certificates had a row. Coverage is today's store, all
    of it, and each lineage ends where the evidence ends -- never with a borrowed URL."""
    certs, docket, cells = _three(tmp_path)
    _wire_many(monkeypatch, tmp_path, certs, docket)
    doc = cp.refresh(budget_s=30.0)
    cp.write(doc)
    cov = doc["coverage"]
    assert cov["current_certificates"] == 3 and cov["recorded"] == 3
    assert cov["record_coverage"] == 1.0
    assert cov["source_lineage"]["walked"] == 3
    recs = doc["records"]
    url = recs[cells[0]]["source_lineage"]
    assert url["status"] == "MEASURED" and url["ends_at"] == "source"
    assert url["source_url"] == "https://example.org/forum/thread/1"
    assert url["retrieved_at"] and url["content_hash"]
    don = recs[cells[1]]["source_lineage"]
    assert don["status"] == cp.UNMEASURED and don["ends_at"] == "donation" and don["why"]
    assert don.get("source_url") is None, "an unlinked donation must never borrow a URL"
    assert don["steps"][2]["producer"] is None, "a FILE is a route, never the donor"
    gone = recs[cells[2]]["source_lineage"]
    assert gone["status"] == cp.UNMEASURED and gone["ends_at"] == "certificate" and gone["why"]
    rc, msg = cp.coverage_gate(cp._json(cp.RECORD), cp.certificates())
    assert rc == 0 and msg.startswith("OK: 3/3"), msg


def test_the_coverage_fence_fails_below_the_number_of_current_certificates(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """A record that saw TODAY's store and still left a certificate without a row fails; a record
    computed against an older store is STALE, which the hourly leg cures, and does not."""
    certs, docket, cells = _three(tmp_path)
    _wire_many(monkeypatch, tmp_path, certs, docket)
    cp.write(cp.refresh(budget_s=30.0))
    rec = cp._json(cp.RECORD)
    del rec["records"][cells[1]]
    rc, msg = cp.coverage_gate(rec, cp.certificates())
    assert rc == 1 and "2/3" in msg and cells[1] in msg
    rec2 = cp._json(cp.RECORD)
    rec2["records"][cells[0]].pop("source_lineage")
    assert cp.coverage_gate(rec2, cp.certificates())[0] == 1, "a row with no lineage is short"
    stale = dict(rec)
    stale["keys"] = {"external.OLD.cell": "OLD.cell"}
    rc, msg = cp.coverage_gate(stale, cp.certificates())
    assert rc == 0 and "STALE" in msg


def test_an_old_record_is_backfilled_without_being_reattributed(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """A final record written before the lineage existed keeps its producer and gains a lineage;
    a certificate the old record never saw gets a row of its own."""
    certs, docket, cells = _three(tmp_path)
    _wire_many(monkeypatch, tmp_path, certs, docket)
    old = {"records": {cells[0]: {"cell": cells[0], "verdict": cp.ATTRIBUTED,
                                  "producer": "legacy_producer", "final": True, "why": "x"}}}
    cp.RECORD.write_text(json.dumps(old), encoding="utf-8")
    doc = cp.refresh(budget_s=30.0)
    assert doc["pending"] == 2 and doc["lineage_pending"] == 3
    assert doc["records"][cells[0]]["producer"] == "legacy_producer"
    assert doc["records"][cells[0]]["source_lineage"]["status"] == "MEASURED"
    assert doc["coverage"]["recorded"] == 3


def test_the_spec_identity_reaches_a_docket_row_the_cell_name_does_not(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """The certificate's name and its shadow_spec can disagree (a selector, a renamed cell); the
    spec's own identity is a second exact key into the docket -- for the lineage only."""
    p = {"rr": 2.5, "ttl_bars": 7}
    spec_id = _cell_of("AUDNZD", p)
    certs = {"external.AUDNZD legacy name": {
        "hunt": "external", "cell": "AUDNZD legacy name", "sym": "AUDNZD",
        "shadow_spec": {"symbol": "AUDNZD", "family": FAM, "params": p}}}
    docket = [{"symbol": "AUDNZD", "family": FAM, "params": p, "producer": "miner:x",
               "source": "x", "candidate_id": "c1", "first_seen": "2026-09-01T00:00:00+00:00",
               "source_url": "https://example.org/a"}]
    _wire_many(monkeypatch, tmp_path, certs, docket)
    doc = cp.refresh(budget_s=30.0)
    lin = doc["records"]["AUDNZD legacy name"]["source_lineage"]
    assert lin["steps"][0]["spec_cell"] == spec_id
    assert lin["status"] == "MEASURED" and lin["steps"][1]["joined_by"] == "spec_frontier_id"
    assert doc["records"]["AUDNZD legacy name"]["verdict"] == cp.UNMEASURED, \
        "a spec-identity docket hit feeds the lineage, never a producer claim"


def test_a_route_that_could_not_run_leaves_the_verdict_open(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """No registry on this host is not a registry that looked and found nothing."""
    certs, docket, cells = _three(tmp_path)
    _wire_many(monkeypatch, tmp_path, certs, docket)          # REGISTRY absent
    doc = cp.refresh(budget_s=30.0)
    for c in cells:
        assert doc["records"][c]["final"] is False
        assert "registry_identity" in doc["records"][c]["why"]
