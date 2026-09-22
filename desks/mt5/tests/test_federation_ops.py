"""Federation operations over a throwaway registry: a spawn signal admitted as new vs collapsed
as a duplicate with lineage, a surviving technique transferred to every other forest, a changed
upstream hash reopening the fingerprint, the dashboard naming the first broken invariant, and a
dry run that writes nothing."""
from __future__ import annotations

import json
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

DESK = Path(__file__).resolve().parents[1]
ROOT = DESK.parents[1]
for _p in (str(ROOT), str(DESK)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from libs.moat import registry as R  # noqa: E402
from libs.research import external_federation as fed  # noqa: E402
from libs.research import federation_registry as FR  # noqa: E402
from libs.research import forests as F  # noqa: E402
from research import external_federation as xfo  # noqa: E402
from research import federation_ops as fo  # noqa: E402

VOCAB = ("citation_cluster", "contributor_graph", "stars_forks", "conference_co_occurrence",
         "package_dependency", "competition_winner", "benchmark_leader",
         "unusual_public_performance", "high_source_roi_author", "recurring_mention")


@pytest.fixture
def desk(tmp_path, monkeypatch):
    """Every path the organ reads or writes lands in tmp_path; the moat registry is a
    throwaway file; the sandbox root is empty."""
    monkeypatch.setattr(R, "BACKUP", tmp_path / "no_backup")
    R.set_path(tmp_path / "alpha_registry.sqlite")
    for name in ("REGISTRY_PATH", "REPORT", "ROI_REPORT", "MINER_CANDIDATES", "SLEEVES",
                 "FORWARD", "CLAIMS_JSONL"):
        monkeypatch.setattr(fo, name, tmp_path / f"{name.lower()}.json")
    monkeypatch.setattr(fo, "DONATIONS", tmp_path / "intelligence" / "federation_ops")
    monkeypatch.setattr(fo, "DESK", tmp_path)
    monkeypatch.setattr(xfo, "STATE", tmp_path / "external_federation.json")
    monkeypatch.setattr(xfo, "PACKETS", tmp_path / "external_packets")
    monkeypatch.setattr(xfo, "PROCESSED", tmp_path / "external_packets" / "processed")
    from libs.ops.control_plane import fingerprints as fp
    from libs.research import sandbox
    monkeypatch.setattr(sandbox, "SANDBOX_ROOT", tmp_path / "sandbox")
    monkeypatch.setattr(fp, "LEDGER", tmp_path / "failure_fingerprints.jsonl")
    yield tmp_path
    R.set_path(None)


def _count(kind: str) -> int:
    conn = R.connect()
    try:
        got = conn.execute("SELECT COUNT(*) AS n FROM discoveries WHERE source_type=?",
                           (kind,)).fetchone()
        return int(dict(got)["n"])
    finally:
        conn.close()


def test_a_spawn_signal_is_admitted_as_new_or_collapsed_as_a_duplicate(desk) -> None:
    # A regional data stack over a known topology is the case the principal named: region +
    # language is a real axis, so a region no seed covers admits where a fork does not.
    fresh_region = next(r for r in ("br", "ng", "ke", "pl", "tr", "mx", "cl")
                        if not any(s.region == r for s in fed.SEEDS))
    parent = fed.SEED_BY_ID["tradingagents"]
    signals = [
        {"signal": "citation_cluster", "kind": "system", "name": "Novel Search",
         "url": "https://github.com/novel/search", "evidence": "cited by three roster papers",
         "capabilities": ["data_source"], "axes": ["data", "region_language"],
         "region": fresh_region, "languages": ["pt"]},
        {"signal": "stars_forks", "kind": "system", "name": "TradingAgents fork 42",
         "url": "https://github.com/someone/TradingAgents-42", "evidence": "a fork wave",
         "capabilities": list(parent.capabilities), "axes": list(parent.axes),
         "region": parent.region},
    ]
    reg = FR.Registry()
    at = fo.now()
    out = fo.spawn_step(reg, list(fed.SEEDS), signals, apply=True, conn=None, at=at,
                        vocabulary=VOCAB)
    assert len(out["admitted"]) == 1 and out["admitted"][0]["disposition"] in (
        fed.RUNNING_DISPOSITIONS)
    assert len(out["duplicates"]) == 1
    dup = out["duplicates"][0]
    assert dup["duplicate_of"] == "tradingagents"
    dup_row = reg.rows[dup["system_id"]]
    assert dup_row["disposition"] == "DUPLICATE"
    assert dup_row["duplicate_family_id"] == "tradingagents"
    assert dup_row["authors_lineage"] == ["tradingagents"]
    new_row = reg.rows[out["admitted"][0]["system_id"]]
    assert new_row["spawn_signal"] == "citation_cluster"
    assert new_row["duplicate_family_id"] == new_row["system_id"]
    # The new system is donated through the federation organ's own door, the duplicate is not.
    files = sorted(fo.DONATIONS.glob("discoveries_*.json"))
    assert len(files) == 1
    rows = json.loads(files[0].read_text(encoding="utf-8"))
    assert [r["url"] for r in rows] == ["https://github.com/novel/search"]
    assert rows[0]["capabilities"] == ["data_source"] and rows[0]["region"] == fresh_region
    # A second pass over the same signals adds nothing: the registry already holds both.
    again = fo.spawn_step(reg, list(fed.SEEDS), signals, apply=True, conn=None, at=at,
                          vocabulary=VOCAB)
    assert again["admitted"] == [] and again["duplicates"] == []


def test_a_surviving_technique_transfers_to_every_other_forest(desk) -> None:
    conn = R.connect()
    try:
        did, created = R.record_discovery(
            source_id="forest:japan", source_type="technique",
            mechanism="TECHNIQUE native_query_seeding: seed queries from pack terminology",
            origin="EXTERNAL", generator="forest_runner:japan:source_scouts",
            payload={"kind": "technique", "forest": "japan",
                     "method": {"technique": "native_query_seeding", "source_class": "forum",
                                "extraction_procedure": "seed from pack terms",
                                "representation": "query list", "region": "japan",
                                "languages": ["ja"]}}, conn=conn)
        assert created
        old = (datetime.now(tz=UTC) - timedelta(days=3)).isoformat(timespec="seconds")
        conn.execute("UPDATE discoveries SET created_at=? WHERE discovery_id=?", (old, did))
        conn.commit()
        # Delayed yield: a later discovery by the same role after the technique was recorded.
        R.record_discovery(source_id="src:jp_forum", source_type="forum",
                           mechanism="a claim found with the seeded queries", origin="EXTERNAL",
                           generator="forest_runner:japan:source_scouts", conn=conn)
        young, _ = R.record_discovery(
            source_id="forest:korea", source_type="technique", mechanism="TECHNIQUE too_young",
            origin="EXTERNAL", generator="forest_runner:korea:academic",
            payload={"kind": "technique", "forest": "korea",
                     "method": {"technique": "too_young", "source_class": "paper"}}, conn=conn)
        at = fo.now()
        out = fo.technique_exchange(conn, None, apply=True, at=at, deadline=float("inf"))
    finally:
        conn.close()
    assert out["techniques"] == 2
    judged = {j["discovery_id"]: j for j in out["judged"]}
    assert judged[did]["survives"] is True
    assert judged[did]["yield"]["later_discoveries_same_role"] == 1
    assert judged[young]["survives"] is None                 # too young: UNMEASURED, not dead
    assert out["survivors"] == [did]
    others = [fid for fid in F.FORESTS if fid != "japan"]
    assert out["transfers_created"] == len(others)
    conn = R.connect()
    try:
        rows = [dict(r) for r in conn.execute(
            "SELECT * FROM discoveries WHERE source_type='technique_transfer'").fetchall()]
        assert sorted(json.loads(r["payload_json"])["to_forest"] for r in rows) == sorted(others)
        for r in rows:
            payload = json.loads(r["payload_json"])
            assert payload["from_forest"] == "japan"
            assert payload["local_equivalent"]["source_class"] == "forum"
            assert payload["local_equivalent"]["forest"] == payload["to_forest"]
            assert "japan" not in payload["to_forest"]
            assert r["source_id"] == f"forest:{payload['to_forest']}"
            assert json.loads(r["parent_ids_json"]) == [did]
        again = fo.technique_exchange(conn, None, apply=True, at=fo.now(),
                                      deadline=float("inf"))
    finally:
        conn.close()
    assert again["transfers_created"] == 0 and again["transfers_existing"] == len(others)


def test_a_changed_upstream_hash_reopens_the_capability_fingerprint(desk) -> None:
    reg = FR.Registry()
    reg.upsert(FR.row_from_system(fed.ExternalSystem(
        "sys_x", "X", "https://github.com/x/y", "t", "WRAPPED", ("mcts",),
        ("search_algorithm",)), disposition="WRAPPED"), at=fo.now())
    bodies = {"v": "1"}

    def fake_fetch(url: str) -> tuple[str, int, str]:
        if "api.github.com" in url:
            return json.dumps({"pushed_at": bodies["v"], "updated_at": "noise-" + fo.now(),
                               "stargazers_count": 7, "fork": False}), 200, ""
        if url.endswith("README.md"):
            return "", 404, "HTTPError 404"
        return f"feed {bodies['v']} Grit::Commit/{'a' * 40}", 200, ""

    conn = R.connect()
    try:
        common = {"fetch": fake_fetch, "max_scan": 5, "deadline": float("inf"), "apply": True,
                  "conn": conn, "no_fetch": False}
        first = fo.delta_scan_step(reg, at=fo.now(), **common)
        assert first["scanned"] == ["sys_x"] and first["reopened"] == []
        assert reg.rows["sys_x"]["fingerprint_state"] == "MEASURED"
        assert first["refused"]["sys_x"] == {"docs": "HTTPError 404"}
        assert first["meta"]["sys_x"]["upstream_head"] == "a" * 40
        # Not due again until its next scan; then unchanged content is unchanged.
        assert fo.delta_scan_step(reg, at=fo.now(), **common)["scanned"] == []
        reg.upsert({"system_id": "sys_x", "next_upstream_delta_scan": "2020-01-01T00:00:00+00:00"})
        same = fo.delta_scan_step(reg, at=fo.now(), **common)
        assert same["unchanged"] == ["sys_x"] and same["reopened"] == []
        bodies["v"] = "2"
        reg.upsert({"system_id": "sys_x", "next_upstream_delta_scan": "2020-01-01T00:00:00+00:00"})
        moved = fo.delta_scan_step(reg, at=fo.now(), **common)
        assert moved["reopened"] == ["sys_x"]
        assert sorted(moved["changed"]["sys_x"]) == ["commits", "releases", "repos"]
        assert reg.rows["sys_x"]["fingerprint_state"] == "REOPENED"
    finally:
        conn.close()
    assert _count("delta_reopen") == 1
    # A host outside the allowlist is refused by name, never fetched.
    assert fo.desk_fetch("https://evil.example.com/repo")[2].startswith("host 'evil.example.com'")


def test_dashboard_names_the_first_broken_invariant(desk) -> None:
    doc = fo.run_pass(budget_s=30, dry_run=False, no_fetch=True)
    assert doc["FEDERATION_CLOSED_AND_HEALTHY"] is False
    first = doc["first_broken_invariant"]
    assert first["invariant"] == FR.INVARIANTS[0] == "registered"
    assert first["ok"] is None                                   # UNMEASURED is a verdict
    assert list(doc["invariants"]) == list(FR.INVARIANTS)
    assert doc["systems"] >= len(fed.SEEDS) and doc["running_rows"] == 0
    for sid in fed.SEED_BY_ID:
        row = doc["per_system"][sid]
        for key in ("runs", "compute_s", "unique_capabilities", "candidates",
                    "effective_trials", "duplicate_rate", "gauntlet_pass_rate",
                    "forward_enrolled", "forward_survivors", "live_descendants", "delta_elog",
                    "information_gain", "data_fields_discovered",
                    "representations_discovered", "failures_contributed", "freshness",
                    "health_state", "marginal_roi"):
            assert key in row, key
    assert doc["per_system"]["rd_agent"]["health_state"] == "UNDISPOSED"
    assert doc["steps"]["delta"]["unmeasured"]
    assert doc["steps"]["control_plane"]["rows"] == doc["invariants"]
    assert "debt" in doc["steps"]["control_plane"]
    assert fo.REPORT.exists() and fo.REGISTRY_PATH.exists()
    reg = FR.Registry.load(fo.REGISTRY_PATH)
    assert len(reg.rows) == doc["systems"] and reg.history and reg.history_valid()[0]
    assert reg.rows["rd_agent"]["canonical_consumers"] == list(fo.CANONICAL_CONSUMERS)
    # A second pass changes no row and appends nothing: the history is of CHANGES.
    n = len(reg.history)
    fo.run_pass(budget_s=30, dry_run=False, no_fetch=True)
    assert len(FR.Registry.load(fo.REGISTRY_PATH).history) == n


def test_dry_run_writes_nothing(desk) -> None:
    before = _count("spawn_signal") + _count("delta_reopen") + _count("technique_transfer")
    doc = fo.run_pass(budget_s=30, dry_run=True, no_fetch=True)
    assert doc["dry_run"] is True and doc["first_broken_invariant"]["invariant"] == "registered"
    assert not fo.REPORT.exists() and not fo.REGISTRY_PATH.exists()
    assert not fo.DONATIONS.exists()
    assert _count("spawn_signal") + _count("delta_reopen") + _count("technique_transfer") == before
