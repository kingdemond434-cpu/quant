"""THE EVIDENCE ROUTER on a tmp registry: the labels land, the quarantine keeps its rows, the
refusals keep their reasons, and a second pass writes nothing.

Nothing here touches the box's registry or its intelligence tree -- the fixture repoints both,
because a test that reads the real universe is a test about the box (test_gauntlet_backpressure's
own rule, for the same reason).

The two assertions that matter most:

  * IDEMPOTENCE. An hourly organ that re-writes every row every hour cannot be told apart from one
    that is looping, and it makes `routed_at` a lie about when the desk decided.
  * NOTHING IS DISCARDED. A quarantined source keeps its registry row and a refused one keeps its
    reason; the only thing either loses is a USE.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

_DESK = Path(__file__).resolve().parents[1]
_ROOT = _DESK.parent.parent
for _p in (str(_ROOT), str(_DESK), str(_DESK / "research")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from libs.moat import registry as R  # noqa: E402
from research import evidence_router as er  # noqa: E402


@pytest.fixture
def organ(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """A tmp registry, a tmp intelligence tree and tmp artifacts."""
    monkeypatch.setattr(R, "BACKUP", tmp_path / "no_backup")
    R.set_path(tmp_path / "alpha_registry.sqlite")
    intel = tmp_path / "intelligence"
    intel.mkdir()
    monkeypatch.setattr(er, "INTEL_ROOTS", (intel,))
    monkeypatch.setattr(er, "QUARANTINE", tmp_path / "evidence_quarantine.json")
    monkeypatch.setattr(er, "REPORT", tmp_path / "EVIDENCE_ROUTER.json")
    yield {"tmp": tmp_path, "intel": intel}
    R.set_path(None)


def _source(sid: str, **cols: object) -> None:
    conn = R.connect()
    try:
        meta = cols.pop("meta", None)
        conn.execute("INSERT INTO sources(source_id, url, kind, first_seen, status, meta_json) "
                     "VALUES(?,?,?,?,?,?)",
                     (sid, str(cols.get("url") or ""), str(cols.get("kind") or "web"),
                      "2026-09-17T00:00:00+00:00", "active",
                      json.dumps(meta) if meta is not None else None))
        conn.commit()
    finally:
        conn.close()


def _rows() -> dict[str, dict]:
    conn = R.connect()
    try:
        return {str(r["source_id"]): dict(r)
                for r in conn.execute("SELECT * FROM sources")}
    finally:
        conn.close()


# --------------------------------------------------------------- the columns exist and land --
def test_the_extension_columns_exist_on_the_sources_table(organ) -> None:
    conn = R.connect()
    try:
        cols = set(R._columns(conn, "sources"))
    finally:
        conn.close()
    assert {"access_label", "credibility", "predictive_state", "quarantine", "routed_at",
            "route_reason"} <= cols
    # CANON is untouched: the original columns are all still there.
    assert {"source_id", "url", "kind", "language", "country", "meta_json"} <= cols


def test_a_public_source_is_labelled_on_all_three_independent_axes(organ) -> None:
    _source("s_pub", url="https://www.boj.or.jp/statistics",
            meta={"source_class": "official"})
    doc = er.run(budget_s=30)
    row = _rows()["s_pub"]
    assert row["access_label"] == "PUBLIC"
    assert row["credibility"] == "AUTHORITATIVE"
    assert row["predictive_state"] == "UNTESTED"
    assert row["quarantine"] == 0 and row["routed_at"] and row["route_reason"]
    assert doc["by_label"]["PUBLIC"] == 1 and doc["n_routed"] == 1


def test_credibility_is_independent_of_the_access_label(organ) -> None:
    _source("s_forum", url="https://forum.example/t/1",
            meta={"source_class": "retail_ecology"})
    _source("s_gov", url="https://data.gov/x", meta={"source_class": "official"})
    er.run(budget_s=30)
    rows = _rows()
    assert rows["s_forum"]["access_label"] == "PUBLIC_SOCIAL"
    assert rows["s_forum"]["credibility"] == "UNRELIABLE"
    assert rows["s_gov"]["credibility"] == "AUTHORITATIVE"
    # Both are lawfully observable: an unreliable source is not an unlawful one.
    assert rows["s_forum"]["quarantine"] == 0 and rows["s_gov"]["quarantine"] == 0


# ------------------------------------------------------------------------------- quarantine --
def test_access_unclear_is_mined_and_never_quarantined(organ) -> None:
    """REWRITTEN 2026-09-23 (LAWS 5e). No url and a `kind` the desk has no class for: nothing
    says what this is or how it was reached. That used to QUARANTINE the row -- metadata kept,
    content never consumed, and nobody ever came back to resolve it. The label stays; the
    quarantine is deleted, and the ledger is empty by construction."""
    _source("s_unclear", url="", kind="mystery")
    doc = er.run(budget_s=30)
    row = _rows()["s_unclear"]
    assert row["access_label"] == "ACCESS_UNCLEAR"
    assert row["quarantine"] == 0, "the ACCESS_UNCLEAR quarantine was deleted on 2026-09-23"
    assert row["source_id"] == "s_unclear", "the metadata row survives, as it always did"
    ledger = json.loads(er.QUARANTINE.read_text(encoding="utf-8"))
    assert ledger["n_quarantined"] == 0 and ledger["quarantined"] == []
    assert "DELETED" in ledger["rule"]
    assert doc["n_quarantined"] == 0


# --------------------------------------------------------------------- refusal with a reason --
def test_the_three_prohibited_labels_are_refused_with_their_reason(organ) -> None:
    _source("s_priv", url="https://intranet.example.com/reports")
    _source("s_mnpi", url="https://x.example/a",
            meta={"terms": "board minutes, not yet public"})
    _source("s_dump", url="https://x.example/b", meta={"terms": "leaked database"})
    doc = er.run(budget_s=30)
    rows = _rows()
    assert rows["s_priv"]["access_label"] == "PRIVATE"
    assert rows["s_mnpi"]["access_label"] == "CONFIDENTIAL_MNPI"
    assert rows["s_dump"]["access_label"] == "STOLEN_UNAUTHORIZED"
    ledger = json.loads(er.QUARANTINE.read_text(encoding="utf-8"))
    assert ledger["n_refused"] == 3
    ids = {r["source_id"] for r in ledger["refused"]}
    assert ids == {"s_priv", "s_mnpi", "s_dump"}
    for r in ledger["refused"]:
        assert r["reason"].strip() and r["allowed_uses"] == []
        assert r["evidence_weight_cap"] == 0.0
    assert doc["n_refused"] == 3
    # THE ROWS STAY. A refusal nobody recorded gets re-proposed by the next miner.
    assert set(rows) == {"s_priv", "s_mnpi", "s_dump"}


def test_a_terms_restricted_source_is_mined_and_labelled_for_redistribution(organ) -> None:
    """REWRITTEN 2026-09-23 (LAWS 5e). `machine_use_allowed=false` was "registered, never
    scraped". It is a REDISTRIBUTION label now: the source is mined and tested in full and the
    census that names it is about what the desk may republish."""
    _source("s_terms", url="https://example.com/data",
            meta={"machine_use_allowed": False, "source_class": "media"})
    doc = er.run(budget_s=30)
    row = _rows()["s_terms"]
    assert row["access_label"] == "PUBLIC_WITH_TERMS"
    assert row["quarantine"] == 0, "restricted terms are not a quarantine"
    assert "s_terms" in doc["redistribution_restricted"], \
        "the terms fact is kept -- as a publication label, not as a refusal to mine"
    assert doc["by_label"]["PUBLIC_WITH_TERMS"] == 1


# ------------------------------------------------------------------------------ idempotence --
def test_a_second_pass_routes_nothing_and_leaves_routed_at_alone(organ) -> None:
    _source("s1", url="https://example.com/a", meta={"source_class": "academic"})
    first = er.run(budget_s=30)
    stamp = _rows()["s1"]["routed_at"]
    second = er.run(budget_s=30)
    assert first["n_routed"] == 1 and second["n_routed"] == 0
    assert second["n_skipped_already_labelled"] == 1
    assert _rows()["s1"]["routed_at"] == stamp
    # ...and the counts are still MEASURED: skipping a row does not make it vanish.
    assert second["n_sources_seen"] == 1 and second["by_label"]["PUBLIC"] == 1


def test_changed_metadata_reopens_a_settled_row(organ) -> None:
    _source("s1", url="https://example.com/a")
    er.run(budget_s=30)
    conn = R.connect()
    try:
        conn.execute("UPDATE sources SET meta_json=? WHERE source_id=?",
                     (json.dumps({"machine_use_allowed": False}), "s1"))
        conn.commit()
    finally:
        conn.close()
    again = er.run(budget_s=30)
    assert again["n_routed"] == 1
    assert _rows()["s1"]["access_label"] == "PUBLIC_WITH_TERMS"


def test_recheck_reroutes_everything(organ) -> None:
    _source("s1", url="https://example.com/a")
    er.run(budget_s=30)
    assert er.run(budget_s=30, recheck=True)["n_routed"] == 1


# ------------------------------------------------------------- intelligence rows join the graph --
def test_an_unseen_intelligence_source_is_registered_and_labelled(organ) -> None:
    seat = organ["intel"] / "forexfactory"
    seat.mkdir()
    (seat / "discoveries_20260917_0001.json").write_text(json.dumps([
        {"source": "forexfactory", "url": "https://www.forexfactory.com/calendar",
         "title": "GBP policy hearings"},
    ]), encoding="utf-8")
    doc = er.run(budget_s=30)
    assert doc["n_sources_created_from_intelligence"] == 1
    row = _rows()["forexfactory"]
    assert row["access_label"] == "PUBLIC" and row["credibility"] == "UNKNOWN"
    assert row["url"] == "https://www.forexfactory.com/calendar"
    assert doc["intelligence_scan"]["rows_read"] == 1


def test_an_intelligence_source_is_not_re_routed_on_the_next_pass(organ) -> None:
    """THE REGRESSION THAT WAS MEASURED ON THE BOX (2026-09-17). The first pass classified the raw
    intelligence metadata and stored a registry-shaped row, so the next pass hashed a different
    shape and re-routed 123 of 159 sources every hour. The row a source BECOMES is now what it is
    classified from, so the two hashes are the same hash."""
    seat = organ["intel"] / "china"
    seat.mkdir()
    (seat / "discoveries_20260917_0001.json").write_text(json.dumps([
        {"source": "ground:cn:7hcn", "url": "https://www.7hcn.com/article/list-1.html",
         "title": "futures trader interview"}]), encoding="utf-8")
    first = er.run(budget_s=30)
    assert first["n_routed"] == 1 and first["n_sources_created_from_intelligence"] == 1
    second = er.run(budget_s=30)
    assert second["n_sources_seen"] == 1
    assert second["n_routed"] == 0, "a stored source was re-routed: the hash shapes differ again"
    assert second["n_skipped_already_labelled"] == 1
    assert second["n_sources_created_from_intelligence"] == 0


def test_dry_run_writes_no_column_no_ledger_and_no_report(organ) -> None:
    _source("s1", url="https://example.com/a")
    doc = er.run(budget_s=30, dry_run=True)
    assert doc["n_routed"] == 1 and doc["by_label"]["PUBLIC"] == 1
    assert _rows()["s1"]["access_label"] is None
    assert not er.QUARANTINE.exists() and not er.REPORT.exists()
    assert doc["coverage_tensor"]["status"] == "UNMEASURED"


# --------------------------------------------------------------------- artifact and coverage --
def test_the_report_carries_the_principle_the_boundary_and_the_counts(organ) -> None:
    _source("s1", url="https://example.com/a")
    er.run(budget_s=30)
    doc = json.loads(er.REPORT.read_text(encoding="utf-8"))
    assert doc["principle"].startswith("The desk mines and tests everything")
    assert "no material non-public information" in doc["hard_boundary"]
    assert len(doc["hard_boundary"]) == 5, "the boundary is five ACTS and must not grow"
    assert doc["stages"] == ["DISCOVER", "CAPTURE_METADATA", "LEGAL_ACCESS", "EVIDENCE_CLASS",
                             "RESEARCH"]
    # EVERY label is a key, including the ones with no rows: a zero that is present is a
    # measurement, an absent key is a question nobody asked.
    assert len(doc["by_label"]) == 11
    assert doc["limitation"].strip() and doc["rule"].strip()


def test_counts_by_label_reach_the_coverage_tensor(organ) -> None:
    _source("s1", url="https://example.com/a")
    doc = er.run(budget_s=30)
    assert doc["coverage_tensor"]["status"] == "PUBLISHED"
    mem = R.memories(category="access_coverage")
    assert mem and json.loads(mem[0]["payload_json"])["by_label"]["PUBLIC"] == 1


def test_an_empty_desk_is_measured_not_a_crash(organ) -> None:
    doc = er.run(budget_s=30)
    assert doc["n_sources_seen"] == 0 and doc["n_routed"] == 0
    assert doc["by_label"]["PUBLIC"] == 0 and doc["n_quarantined"] == 0


def test_cli_once_dry_run_prints_and_writes_nothing(organ, capsys) -> None:
    _source("s1", url="https://example.com/a")
    assert er.main(["--once", "--budget-s", "30", "--dry-run"]) == 0
    out = capsys.readouterr().out
    assert "evidence router" in out and "--dry-run: nothing written" in out
    assert not er.REPORT.exists()
