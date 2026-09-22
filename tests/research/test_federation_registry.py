"""The persisted federation registry: round-trips, an append-only hash-chained history, a delta
hash set whose `changed_since` names only what moved, twins judged at equal compute, and the
twelve invariants whose first failure is named."""
from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta

import pytest

from libs.research import external_federation as fed
from libs.research import federation_registry as FR

NOW = datetime(2026, 9, 22, 12, 0, tzinfo=UTC)


def _system(sid: str = "sys_a", caps: tuple[str, ...] = ("mcts",),
            axes: tuple[str, ...] = ("search_algorithm",)) -> fed.ExternalSystem:
    return fed.ExternalSystem(sid, sid.upper(), f"https://github.com/x/{sid}", "test",
                              "WRAPPED", caps, axes)


def test_registry_round_trips_rows_history_delta_and_twins(tmp_path) -> None:
    reg = FR.Registry()
    reg.upsert(FR.row_from_system(_system()), at="2026-09-22T10:00:00+00:00")
    reg.upsert({"system_id": "sys_a", "commit_version": "abc123", "licence": "MIT"},
               at="2026-09-22T11:00:00+00:00")
    reg.delta.observe("sys_a", "commits", "feed v1", at="2026-09-22T11:00:00+00:00")
    reg.twins["sys_a"] = FR.twin_verdict("sys_a", None, None)
    path = tmp_path / "federation_registry.json"
    reg.save(path, at="2026-09-22T11:00:00+00:00")
    back = FR.Registry.load(path)
    assert back.rows == reg.rows
    assert back.history == reg.history
    assert back.delta.snapshot() == reg.delta.snapshot()
    assert back.twins["sys_a"]["verdict"] == FR.UNMEASURED
    assert back.history_valid() == (True, "ok")
    doc = json.loads(path.read_text(encoding="utf-8"))
    assert doc["content_hash"] == back.content_hash()
    assert set(FR.REGISTRY_FIELDS) <= set(back.rows["sys_a"])
    for name in ("upstream_repo", "commit_version", "licence", "authors_lineage",
                 "capability_fingerprint", "integration_mode", "security_profile",
                 "data_dependencies", "compute_requirements", "native_search_algorithm",
                 "native_representation_language", "native_validation_methods",
                 "supported_markets", "historical_claims", "known_weaknesses",
                 "duplicate_family_id", "sandbox_image_hash", "schedule", "progress_watermark",
                 "outputs", "canonical_consumers", "trials_donated", "descendants_created",
                 "forward_survivors", "live_portfolio_contribution", "compute_spent",
                 "next_upstream_delta_scan"):
        assert name in FR.REGISTRY_FIELDS, name
    assert back.rows["sys_a"]["compute_requirements"] == FR.UNMEASURED
    assert back.rows["sys_a"]["first_seen"] == "2026-09-22T10:00:00+00:00"


def test_history_is_append_only_and_hash_chained(tmp_path) -> None:
    path = tmp_path / "r.json"
    reg = FR.Registry()
    reg.upsert(FR.row_from_system(_system()), at="2026-09-22T10:00:00+00:00")
    n0 = len(reg.history)
    assert n0 >= 1 and all(e.get("hash") for e in reg.history)
    # An unchanged field is not a change; a volatile field never enters the history.
    assert reg.upsert({"system_id": "sys_a", "licence": "UNVERIFIED",
                       "updated_at": "later"}, at="t1") == []
    assert len(reg.history) == n0
    reg.upsert({"system_id": "sys_a", "licence": "MIT"}, at="t2")
    assert len(reg.history) == n0 + 1 and reg.history[-1]["field"] == "licence"
    reg.save(path)
    # Saving a registry whose history is not a superset of the one on disk is refused.
    shorter = FR.Registry.load(path)
    shorter.history = shorter.history[:-1]
    with pytest.raises(ValueError, match="append-only"):
        shorter.save(path)
    # A spliced entry breaks the chain and the document refuses to load.
    doc = json.loads(path.read_text(encoding="utf-8"))
    doc["history"][0]["after"] = "tampered"
    (tmp_path / "bad.json").write_text(json.dumps(doc), encoding="utf-8")
    with pytest.raises(ValueError, match="corrupt"):
        FR.Registry.load(tmp_path / "bad.json")
    # A closed schema: a typo is refused rather than becoming a second field.
    with pytest.raises(ValueError, match="not registry fields"):
        reg.upsert({"system_id": "sys_a", "licence_": "MIT"})


def test_delta_set_changed_since_names_only_what_moved() -> None:
    ds = FR.DeltaSet()
    assert ds.observe("a", "commits", "v1") is False          # first sight is not a change
    assert ds.observe("a", "commits", "v1") is False
    before = ds.snapshot()
    assert ds.observe("a", "commits", "v2") is True
    ds.observe("b", "releases", b"same")
    ds.observe("c", "docs", {"k": 1})
    moved = ds.changed_since(before)
    assert moved == {"a": ["commits"], "b": ["releases"], "c": ["docs"]}
    ds2 = FR.DeltaSet.from_doc(ds.to_doc())
    assert ds2.changed_since(ds) == {}
    with pytest.raises(ValueError):
        ds.observe("a", "not_a_surface", "x")
    row = {"next_upstream_delta_scan": (NOW + timedelta(hours=1)).isoformat()}
    assert FR.delta_due(row, now=NOW) is False
    assert FR.delta_due({}, now=NOW) is True
    assert FR.delta_stale({}, now=NOW) is None
    assert FR.delta_stale({"last_upstream_delta_scan": (NOW - timedelta(days=15)).isoformat()},
                          now=NOW) is True


def test_benchmark_twin_keeps_the_native_path_when_integration_is_worse() -> None:
    native = FR.TwinArm("native", "r1", 600.0, candidates=12, unique_candidates=10)
    worse = FR.TwinArm("integrated", "r2", 600.0, candidates=8, unique_candidates=6)
    better = FR.TwinArm("integrated", "r3", 620.0, candidates=20, unique_candidates=18)
    assert FR.twin_verdict("s", native, worse)["verdict"] == "NATIVE_STANDS"
    rec = FR.twin_verdict("s", native, better)
    assert rec["verdict"] == "INTEGRATED_BETTER" and rec["kept"] == "integrated"
    unequal = FR.TwinArm("integrated", "r4", 3000.0, candidates=50, unique_candidates=50)
    assert FR.twin_verdict("s", native, unequal)["verdict"] == FR.UNMEASURED
    assert FR.twin_verdict("s", native, None)["verdict"] == FR.UNMEASURED
    tie = FR.TwinArm("integrated", "r5", 600.0, candidates=10, unique_candidates=10)
    assert FR.twin_verdict("s", native, tie)["kept"] == "native"


def test_capability_inference_stays_inside_the_federation_vocabulary() -> None:
    caps, axes = FR.infer_capabilities("An MCTS alpha search with causal discovery and a "
                                       "walk-forward backtest harness")
    assert set(caps) <= set(fed.CAPABILITY_FAMILIES) and set(axes) <= set(fed.NEW_AXES)
    assert "mcts" in caps and "causal_discovery" in caps
    assert FR.infer_capabilities("") == ((), ())
    for cap in FR._CAPABILITY_AXIS:
        assert cap in fed.CAPABILITY_FAMILIES, cap
        assert FR._CAPABILITY_AXIS[cap] in fed.NEW_AXES, cap
    system = FR.system_from_signal(
        {"signal": "citation_cluster", "name": "KRX Miner", "url": "https://github.com/k/m",
         "evidence": "a Korean market data loader", "region": "kr", "languages": ["ko"]},
        system_id="disc_k_m", vocabulary=("citation_cluster",))
    assert "region_language" in system.axes and "data_source" in system.capabilities
    with pytest.raises(ValueError, match="not a spawn trigger"):
        FR.system_from_signal({"signal": "vibes", "name": "x"}, system_id="x",
                              vocabulary=("citation_cluster",))


def test_technique_survival_is_judged_on_delayed_yield() -> None:
    young = (NOW - timedelta(hours=2)).isoformat()
    old = (NOW - timedelta(days=3)).isoformat()
    assert FR.technique_survival(young, {"descendants": 5}, now=NOW)[0] is None
    assert FR.technique_survival(old, {"descendants": 0, "later": 2}, now=NOW)[0] is True
    assert FR.technique_survival(old, {"descendants": 0}, now=NOW)[0] is False
    assert FR.technique_survival(None, {"descendants": 9}, now=NOW)[0] is None


def _running_row(sid: str) -> dict:
    return FR.row_from_system(
        _system(sid), disposition="WRAPPED", commit_version="abc", licence="MIT",
        sandbox_image_hash="deadbeef", schedule=["hourly"], progress_watermark={"run_id": "r9"},
        canonical_consumers=["miner_candidate_compiler"], forward_survivors=0,
        last_upstream_delta_scan=NOW.isoformat(),
        next_upstream_delta_scan=(NOW + timedelta(days=7)).isoformat())


def test_invariants_name_the_first_broken_one_in_order() -> None:
    rows = {"sys_a": FR.row_from_system(_system())}          # UNDISPOSED: not running
    inv = FR.invariants(rows, {}, {}, now=NOW)
    assert list(inv) == list(FR.INVARIANTS)
    first = FR.first_broken(inv)
    assert first is not None and first["invariant"] == "registered" and first["ok"] is None
    good = {"sys_b": _running_row("sys_b")}
    stats = {"sys_b": {"runs": 2, "candidates": 4, "consumed": 3, "delta_elog": 0.0,
                       "last_run_at": NOW.isoformat()}}
    evidence = {"candidates_donated": 4, "candidates_recorded": 3, "candidates_collapsed": 1,
                "stranded": [], "verdict_fields_in_canonical": 0}
    inv = FR.invariants(good, stats, evidence, now=NOW)
    assert FR.first_broken(inv) is None, inv
    assert FR.health_state(good["sys_b"], stats["sys_b"], now=NOW) == "HEALTHY"
    evidence["candidates_recorded"] = 1
    assert FR.first_broken(FR.invariants(good, stats, evidence, now=NOW))["invariant"] == (
        "candidate_conservation")
    broke = {"sys_b": {**good["sys_b"], "sandbox_image_hash": FR.UNMEASURED}}
    assert FR.first_broken(FR.invariants(broke, stats, evidence, now=NOW))["invariant"] == (
        "sandboxed")
    assert FR.health_state(broke["sys_b"], stats["sys_b"], now=NOW) == "NOT_OPERATIONAL:sandboxed"
    stale = {"sys_b": {**good["sys_b"],
                       "last_upstream_delta_scan": (NOW - timedelta(days=30)).isoformat()}}
    evidence["candidates_recorded"] = 3
    assert FR.first_broken(FR.invariants(stale, stats, evidence, now=NOW))["invariant"] == (
        "delta_scans_fresh")
    assert FR.marginal_roi(good["sys_b"], {"delta_elog": 0.02, "information_gain": 3,
                                           "compute_s": 100.0}) == pytest.approx(3.02 / 100.0)
    assert FR.marginal_roi(good["sys_b"], {"compute_s": 100.0}) is None
