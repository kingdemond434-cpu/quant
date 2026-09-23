"""The chain's own prosecution: a full lineage, then every way it can be lied to.

Every test writes to `tmp_path`. Nothing here touches
`desks/mt5/data/research_artifacts.jsonl` -- a test that appended to the real chain would put
fixture rows into an append-only record that is never edited, so they could never be removed.
"""
from __future__ import annotations

import dataclasses
import json
from pathlib import Path
from typing import Any

import pytest

from libs.research import artifact_chain as ac
from libs.research.artifacts import new_artifact

SYMBOL, FAMILY = "XAUUSD", "overnight_gap_decay"
PARAMS: dict[str, Any] = {"rr": 2.0, "wait_bars": 3}


def _chain(tmp_path: Path) -> Path:
    return tmp_path / "research_artifacts.jsonl"


def _full_lineage(path: Path) -> dict[str, ac.Record]:
    """source -> claim -> hypothesis -> code -> data -> config -> result -> review."""
    source = ac.append("source", ac.source_payload(
        "qihuo-ribao-2026", "https://example.invalid/大赛", "2026-09-16T00:00:00+00:00",
        source_hash="a" * 64), path=path)
    claim = ac.append("claim", ac.claim_payload(
        "gold gaps down into the Asia open and fills", "overnight gap decay",
        actor="七禾网 interview", language="zh"), prev=source.artifact_id, path=path)
    hypothesis = ac.append("hypothesis", ac.hypothesis_payload(
        SYMBOL, FAMILY, PARAMS, "expectancy <= 0 over 60 forward trades"),
        prev=claim.artifact_id, path=path)
    code = ac.append("code", ac.code_payload(_full_lineage, FAMILY),
                     prev=hypothesis.artifact_id, path=path)
    bars = path.parent / "XAUUSD_H1.parquet"
    bars.write_bytes(b"not really a parquet, but it is bytes and they hash")
    data = ac.append("data", ac.data_payload({(SYMBOL, "H1"): bars}),
                     prev=code.artifact_id, path=path)
    config = ac.append("config", ac.config_payload({"gates": 10, "min_trades": 30}, cell="c"),
                       prev=data.artifact_id, path=path)
    result = ac.append("result", ac.result_payload(
        {"in_sample_screen": True, "deflated_sharpe": True}, passed=True, n=71,
        expectancy=0.11, t=2.4, output_hash="b" * 64, cell=ac.cell_id_for(SYMBOL, FAMILY, PARAMS)),
        prev=config.artifact_id, path=path)
    review = ac.append("review", ac.review_payload(
        "PASS", "blind_reviewer", {"n": 69, "expectancy": 0.10, "t": 2.2},
        cell=ac.cell_id_for(SYMBOL, FAMILY, PARAMS)), prev=result.artifact_id, path=path)
    return {"source": source, "claim": claim, "hypothesis": hypothesis, "code": code,
            "data": data, "config": config, "result": result, "review": review}


# --------------------------------------------------------------------------- the happy path

def test_full_lineage_verifies(tmp_path: Path) -> None:
    path = _chain(tmp_path)
    recs = _full_lineage(path)

    report = ac.verify(path)
    assert report.ok, report.reason
    assert report.n == 8
    assert report.first_break is None
    assert report.by_kind == dict.fromkeys(ac.KINDS, 1)
    assert report.lineages == 1
    assert report.orphan_lineages == []

    # One lineage, headed by the source, and every record carries its id.
    assert all(r.lineage_id == recs["source"].artifact_id for r in recs.values())
    assert recs["source"].prev is None
    assert recs["review"].prev == recs["result"].artifact_id


def test_empty_and_missing_chain_verify_ok(tmp_path: Path) -> None:
    missing = _chain(tmp_path)
    report = ac.verify(missing)
    assert (report.ok, report.n, report.by_kind) == (True, 0, {})

    missing.write_text("\n\n", encoding="utf-8")
    assert ac.verify(missing).ok


def test_chain_hash_links_each_line_to_the_one_before(tmp_path: Path) -> None:
    path = _chain(tmp_path)
    recs = _full_lineage(path)
    rows = [json.loads(ln) for ln in path.read_text("utf-8").splitlines() if ln.strip()]
    tail = None
    for row in rows:
        assert row["chain_hash"] == ac._chain_hash(tail, row["payload_hash"])
        tail = row["chain_hash"]
    assert rows[-1]["artifact_id"] == recs["review"].artifact_id


def test_the_same_payload_appended_twice_is_two_artifacts(tmp_path: Path) -> None:
    """A new experiment is a new artifact -- even when it is the same experiment run again."""
    path = _chain(tmp_path)
    body = ac.source_payload("s1", "ground", "2026-09-16T00:00:00+00:00")
    first = ac.append("source", body, path=path)
    second = ac.append("source", body, path=path)
    assert first.payload_hash == second.payload_hash
    assert first.artifact_id != second.artifact_id
    assert first.chain_hash != second.chain_hash
    assert ac.verify(path).ok


# ------------------------------------------------------------------------------- tampering

def test_tampering_with_a_middle_line_breaks_verify_at_it(tmp_path: Path) -> None:
    path = _chain(tmp_path)
    _full_lineage(path)
    lines = path.read_text("utf-8").splitlines()
    assert len(lines) == 8

    row = json.loads(lines[5])                       # the config, line 6 of 8
    row["payload"]["settings_digest"] = "0" * 64
    lines[5] = json.dumps(row, sort_keys=True, separators=(",", ":"))
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    report = ac.verify(path)
    assert not report.ok
    assert report.first_break == 6
    assert report.reason is not None
    assert "payload_hash" in report.reason
    # Records before the break still counted; the walk stops where the lie is.
    assert report.by_kind == {"source": 1, "claim": 1, "hypothesis": 1, "code": 1, "data": 1}


def test_tampering_with_payload_and_its_hash_breaks_the_chain_hash(tmp_path: Path) -> None:
    path = _chain(tmp_path)
    _full_lineage(path)
    lines = path.read_text("utf-8").splitlines()
    row = json.loads(lines[6])                       # the result
    row["payload"]["passed"] = False
    row["payload_hash"] = ac.digest(row["payload"])  # a careful forger updates this too
    lines[6] = json.dumps(row, sort_keys=True, separators=(",", ":"))
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    report = ac.verify(path)
    assert not report.ok and report.first_break == 7
    assert report.reason is not None and "chain_hash" in report.reason


def test_deleting_a_line_breaks_the_chain(tmp_path: Path) -> None:
    path = _chain(tmp_path)
    _full_lineage(path)
    lines = path.read_text("utf-8").splitlines()
    del lines[4]                                     # drop the data record
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    report = ac.verify(path)
    assert not report.ok and report.first_break == 5


def test_unparseable_line_is_named_not_swallowed(tmp_path: Path) -> None:
    path = _chain(tmp_path)
    _full_lineage(path)
    with path.open("a", encoding="utf-8") as fh:
        fh.write("{not json at all\n")

    report = ac.verify(path)
    assert not report.ok and report.first_break == 9
    assert report.reason is not None and "not JSON" in report.reason

    # And nothing may be appended on top of a chain that does not parse.
    with pytest.raises(ac.ChainError, match="refusing to append"):
        ac.append("source", ac.source_payload("s", "g", "2026-09-16T00:00:00+00:00"), path=path)


# --------------------------------------------------------------------------------- refusals

def test_wrong_order_is_refused(tmp_path: Path) -> None:
    path = _chain(tmp_path)
    source = ac.append("source", ac.source_payload("s", "g", "2026-09-16T00:00:00+00:00"),
                       path=path)
    with pytest.raises(ac.ChainOrderError, match="cannot follow"):
        ac.append("result", ac.result_payload({}, passed=True), prev=source.artifact_id,
                  path=path)
    # And a review may not skip the result it is supposed to reproduce.
    claim = ac.append("claim", ac.claim_payload("t", "m", "a"), prev=source.artifact_id,
                      path=path)
    with pytest.raises(ac.ChainOrderError, match="cannot follow"):
        ac.append("review", ac.review_payload("PASS", "r", {}), prev=claim.artifact_id,
                  path=path)
    assert ac.verify(path).ok


def test_unknown_prev_is_refused(tmp_path: Path) -> None:
    path = _chain(tmp_path)
    ac.append("source", ac.source_payload("s", "g", "2026-09-16T00:00:00+00:00"), path=path)
    with pytest.raises(ac.UnknownPrev, match="not in"):
        ac.append("claim", ac.claim_payload("t", "m", "a"), prev="f" * 32, path=path)
    assert ac.verify(path).n == 1


def test_only_source_and_hypothesis_may_start_a_lineage(tmp_path: Path) -> None:
    path = _chain(tmp_path)
    with pytest.raises(ac.ChainOrderError, match="cannot start a lineage"):
        ac.append("claim", ac.claim_payload("t", "m", "a"), path=path)
    with pytest.raises(ac.ChainOrderError, match="cannot start a lineage"):
        ac.append("result", ac.result_payload({}, passed=False), path=path)


def test_missing_payload_field_is_refused(tmp_path: Path) -> None:
    path = _chain(tmp_path)
    with pytest.raises(ac.PayloadError, match="missing"):
        ac.append("source", {"source_id": "s"}, path=path)
    # A value of None is legal -- unknown is a real answer; an absent KEY is not.
    rec = ac.append("source", {"source_id": "s", "url_or_ground": "g", "retrieved_at": None,
                               "source_hash": None}, path=path)
    assert rec.payload["source_hash"] is None


def test_unknown_review_verdict_is_refused(tmp_path: Path) -> None:
    path = _chain(tmp_path)
    with pytest.raises(ac.PayloadError, match="verdict"):
        ac.append("hypothesis", ac.hypothesis_payload(SYMBOL, FAMILY, PARAMS, "f"), path=path)\
            if False else None
        ac.append("review", {"verdict": "probably", "reviewer": "r", "reproduced_digest": "d"},
                  path=path)


def test_unknown_kind_is_refused(tmp_path: Path) -> None:
    with pytest.raises(ac.ChainOrderError, match="is not one of"):
        ac.append("certificate", {}, path=_chain(tmp_path))


def test_lineage_id_that_disagrees_with_prev_is_refused(tmp_path: Path) -> None:
    path = _chain(tmp_path)
    source = ac.append("source", ac.source_payload("s", "g", "2026-09-16T00:00:00+00:00"),
                       path=path)
    with pytest.raises(ac.ChainOrderError, match="disagrees"):
        ac.append("claim", ac.claim_payload("t", "m", "a"), prev=source.artifact_id,
                  lineage_id="d" * 32, path=path)


def test_records_are_frozen(tmp_path: Path) -> None:
    rec = ac.append("source", ac.source_payload("s", "g", "2026-09-16T00:00:00+00:00"),
                    path=_chain(tmp_path))
    with pytest.raises(dataclasses.FrozenInstanceError):
        rec.payload_hash = "0" * 64                                   # type: ignore[misc]


# -------------------------------------------------------------------------- orphan lineage

def test_orphan_hypothesis_starts_and_is_flagged(tmp_path: Path) -> None:
    path = _chain(tmp_path)
    hypothesis = ac.append("hypothesis", ac.hypothesis_payload(
        "EURUSD", "carry", {"rr": 1.5}, "expectancy <= 0"), path=path)
    assert hypothesis.orphan_lineage is True
    assert hypothesis.lineage_id == hypothesis.artifact_id
    assert hypothesis.prev is None

    code = ac.append("code", ac.code_payload(_full_lineage, "carry"),
                     prev=hypothesis.artifact_id, path=path)
    assert code.lineage_id == hypothesis.artifact_id
    assert code.orphan_lineage is False              # only the head carries the flag

    report = ac.verify(path)
    assert report.ok
    assert report.orphan_lineages == [hypothesis.artifact_id]


def test_a_sourced_hypothesis_is_not_an_orphan(tmp_path: Path) -> None:
    path = _chain(tmp_path)
    _full_lineage(path)
    assert ac.verify(path).orphan_lineages == []


# --------------------------------------------------------------------------------- lookups

def test_lineage_latest_and_from_cell(tmp_path: Path) -> None:
    path = _chain(tmp_path)
    recs = _full_lineage(path)
    # A second, unrelated lineage must not bleed into the first.
    other = ac.append("hypothesis", ac.hypothesis_payload("EURUSD", "carry", {"rr": 1.0}, None),
                      path=path)

    whole = ac.lineage(recs["result"].artifact_id, path=path)
    assert [r.kind for r in whole] == list(ac.KINDS)
    assert ac.lineage(recs["source"].artifact_id, path=path) == whole      # id or lineage id
    assert [r.artifact_id for r in ac.lineage(other.artifact_id, path=path)] == [
        other.artifact_id]

    cid = ac.cell_id_for(SYMBOL, FAMILY, PARAMS)
    found = ac.from_cell(SYMBOL, FAMILY, PARAMS, path=path)
    assert found is not None and found.artifact_id == recs["hypothesis"].artifact_id
    assert found.payload["cell_id"] == cid

    assert ac.latest("hypothesis", cid, path=path) == recs["hypothesis"]
    assert ac.latest("source", "qihuo-ribao-2026", path=path) == recs["source"]
    assert ac.latest("code", FAMILY, path=path) == recs["code"]
    assert ac.latest("review", "blind_reviewer", path=path) == recs["review"]
    assert ac.latest("result", "b" * 64, path=path) == recs["result"]
    # An artifact id always resolves, whatever the kind's own key field is.
    assert ac.latest("data", recs["data"].artifact_id, path=path) == recs["data"]

    assert ac.from_cell("GBPUSD", FAMILY, PARAMS, path=path) is None
    assert ac.latest("source", "never-collected", path=path) is None


def test_latest_returns_the_newest_of_several(tmp_path: Path) -> None:
    path = _chain(tmp_path)
    first = ac.append("hypothesis", ac.hypothesis_payload(SYMBOL, FAMILY, PARAMS, "f1"),
                      path=path)
    second = ac.append("hypothesis", ac.hypothesis_payload(SYMBOL, FAMILY, PARAMS, "f2"),
                       path=path)
    cid = ac.cell_id_for(SYMBOL, FAMILY, PARAMS)
    assert first.payload["cell_id"] == second.payload["cell_id"] == cid
    found = ac.latest("hypothesis", cid, path=path)
    assert found is not None and found.artifact_id == second.artifact_id


def test_cell_id_is_the_desks_own(tmp_path: Path) -> None:
    from desks.mt5.research.frontier_identity import cell_id
    assert ac.cell_id_for(SYMBOL, FAMILY, PARAMS) == cell_id(
        {"sym": SYMBOL, "family": FAMILY, "params": PARAMS})
    # The chart is part of the name, exactly as the desk spells it.
    assert "@M5" in ac.cell_id_for(SYMBOL, FAMILY, {"rr": 2, "timeframe": "M5"})


# -------------------------------------------------------------------------------- payloads

def test_code_payload_carries_both_desk_hashes(tmp_path: Path) -> None:
    from desks.mt5.research.sleeve_registry import behaviour_hash, code_hash
    body = ac.code_payload(_full_lineage, FAMILY)
    assert body["code_hash"] == code_hash(_full_lineage)
    assert body["behaviour_hash"] == behaviour_hash(_full_lineage)
    assert body["code_hash"] != body["behaviour_hash"]


def test_data_payload_hashes_bytes_and_names_what_it_could_not_read(tmp_path: Path) -> None:
    good = tmp_path / "AUDUSD_H1.parquet"
    good.write_bytes(b"bars")
    missing = tmp_path / "NOPE_M15.parquet"
    body = ac.data_payload({("AUDUSD", "H1"): good, ("NOPE", "M15"): missing})
    assert body["bars_digest"]["AUDUSD|H1"] == ac.sha256_file(good)
    assert body["bars_digest"]["NOPE|M15"] is None
    assert body["unreadable"] == ["NOPE|M15"]
    assert body["vintage_basis"] == "derived_from_mtime"
    assert len(body["vintage_ids"]) == 1              # only the file that could be stat'd

    declared = ac.data_payload({("AUDUSD", "H1"): good}, vintage_ids=["v1"])
    assert declared["vintage_ids"] == ["v1"] and declared["vintage_basis"] == "declared"
    assert declared["digest"] != body["digest"]


def test_claim_payload_keeps_the_prose_out(tmp_path: Path) -> None:
    body = ac.claim_payload("gold fills its Asia gap", "overnight gap decay", "七禾网")
    assert "gold" not in json.dumps(body, ensure_ascii=False)
    assert body["text_hash"] == ac.digest("gold fills its Asia gap")
    assert body["chars"] == len("gold fills its Asia gap")


def test_hypothesis_payload_joins_the_mutable_candidate(tmp_path: Path) -> None:
    candidate = new_artifact("H-20260916-001", semantic_coordinate="gold.asia.gap",
                             mechanism="overnight gap decay")
    body = ac.hypothesis_payload(SYMBOL, FAMILY, PARAMS, "f", artifact=candidate)
    assert body["candidate_id"] == candidate.artifact_id
    assert body["candidate_fingerprint"] == candidate.fingerprint()


def test_result_payload_keeps_unmeasured_as_none(tmp_path: Path) -> None:
    body = ac.result_payload({"a": 1}, passed=None)
    assert body["passed"] is None and body["n"] is None
    assert body["expectancy"] is None and body["t"] is None
    assert body["stages_digest"] == ac.digest({"a": 1})


# -------------------------------------------------------------------------------- adapters

def test_from_gate_verdict_on_a_synthetic_row(tmp_path: Path) -> None:
    path = _chain(tmp_path)
    recs = _full_lineage(path)
    cid = recs["hypothesis"].payload["cell_id"]
    row = {"at": "2026-09-15T04:37:37+00:00", "cell": cid, "sym": SYMBOL, "family": FAMILY,
           "passed": False, "terminal_gate": "deflated_sharpe", "downstream_status": None,
           "n": 41, "expectancy": "-0.03", "t_stat": -0.8}

    result = ac.from_gate_verdict(row, path=path)
    assert result.kind == "result"
    assert result.payload["passed"] is False
    assert result.payload["n"] == 41
    assert result.payload["expectancy"] == pytest.approx(-0.03)
    assert result.payload["t"] == pytest.approx(-0.8)
    assert result.payload["cell"] == cid
    assert result.payload["output_hash"] == ac.digest(row)

    config = ac.latest("config", cid, path=path)
    assert config is not None and result.prev == config.artifact_id
    assert config.prev == recs["data"].artifact_id       # attached to the bars it ran on
    assert config.lineage_id == recs["source"].artifact_id

    report = ac.verify(path)
    assert report.ok and report.n == 10
    assert report.by_kind["result"] == 2                 # a re-run is a NEW artifact


def test_from_gate_verdict_refuses_a_cell_with_no_provenance(tmp_path: Path) -> None:
    path = _chain(tmp_path)
    row = {"cell": "NOTHING.carry.rr=1_wb=1", "sym": "NOTHING", "family": "carry",
           "passed": True, "terminal_gate": None}
    with pytest.raises(ac.ChainOrderError, match="no hypothesis record"):
        ac.from_gate_verdict(row, path=path)

    # A hypothesis with no data record cannot carry a config either.
    hypothesis = ac.append("hypothesis", ac.hypothesis_payload(
        "NOTHING", "carry", {"rr": 1, "wait_bars": 1}, None), path=path)
    assert hypothesis.payload["cell_id"] == row["cell"]
    with pytest.raises(ac.ChainOrderError, match="holds no data record"):
        ac.from_gate_verdict(row, path=path)
    assert ac.verify(path).ok


def test_from_blind_review_is_tolerant_of_its_ledgers_shape(tmp_path: Path) -> None:
    path = _chain(tmp_path)
    recs = _full_lineage(path)
    cid = recs["hypothesis"].payload["cell_id"]

    row = {"at": "2026-09-16T01:00:00+00:00", "cell": cid, "verdict": "VETO",
           "why": ["reproduced expectancy disagrees in sign"],
           "certified": {"expectancy": 0.11}, "reproduced": {"expectancy": -0.02, "t": -0.4},
           "hostile": {"status": "UNMEASURED", "why": "not reached"}, "basis": "replay2",
           "seconds": 4.1}
    review = ac.from_blind_review(row, path=path)
    assert review.kind == "review"
    assert review.payload["verdict"] == "VETO"
    assert review.payload["reviewer"] == "blind_reviewer"
    assert review.payload["reproduced_digest"] == ac.digest(row["reproduced"])
    assert review.payload["hostile"] == "UNMEASURED"
    assert review.prev == recs["result"].artifact_id

    # A verdict this cannot read never becomes PASS and never becomes VETO.
    unknown = ac.from_blind_review({"cell": cid, "verdict": "looks fine to me"}, path=path)
    assert unknown.payload["verdict"] == "UNMEASURED"
    assert ac.from_blind_review({"cell": cid}, path=path).payload["verdict"] == "UNMEASURED"
    assert ac.verify(path).ok


# ------------------------------------------------------------------------ locking / writing

def test_sequential_appends_leave_a_consistent_chain(tmp_path: Path) -> None:
    """Two writers in sequence: the second reads the first's tail, so nothing is lost."""
    path = _chain(tmp_path)
    first = ac.append("hypothesis", ac.hypothesis_payload(SYMBOL, FAMILY, PARAMS, "f"),
                      path=path)
    second = ac.append("hypothesis", ac.hypothesis_payload("EURUSD", "carry", {"rr": 1}, "f"),
                       path=path)
    third = ac.append("code", ac.code_payload(_full_lineage, FAMILY),
                      prev=first.artifact_id, path=path)

    assert second.chain_hash == ac._chain_hash(first.chain_hash, second.payload_hash)
    assert third.chain_hash == ac._chain_hash(second.chain_hash, third.payload_hash)
    assert third.lineage_id == first.artifact_id         # lineage follows prev, not file order

    report = ac.verify(path)
    assert report.ok and report.n == 3 and report.lineages == 2


def test_the_lock_releases(tmp_path: Path) -> None:
    path = _chain(tmp_path)
    ac.append("source", ac.source_payload("s", "g", "2026-09-16T00:00:00+00:00"), path=path)
    assert ac.lock_path(path).exists()

    # Re-entering must not block: an append that left the lock held would hang every writer.
    for _ in range(3):
        with ac._locked(path, timeout_s=2.0) as held:
            assert held is True

    # And the chain is still appendable afterwards.
    ac.append("source", ac.source_payload("s2", "g", "2026-09-16T00:00:00+00:00"), path=path)
    assert ac.verify(path).n == 2


def test_lock_sidecar_is_never_the_chain_itself(tmp_path: Path) -> None:
    path = _chain(tmp_path)
    assert ac.lock_path(path) != path
    assert ac.lock_path(path).name.endswith(".lock")


def test_the_module_points_at_the_desks_chain() -> None:
    assert ac.CHAIN.name == "research_artifacts.jsonl"
    assert ac.CHAIN.parent.as_posix().endswith("desks/mt5/data")
