"""The harvester's prosecution: one spine, then every way the pass can be wrong about it.

Every path here is a `tmp_path`. Nothing touches the real chain
(`desks/mt5/data/research_artifacts.jsonl`), the real reports, or the ROOT alpha registry --
`_registry_conn` is monkeypatched in every test, because `libs.moat.registry.connect()` evolves
the schema it opens and a test that opened the live registry would WRITE to a tracked file.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from libs.research import artifact_chain as ac
from research import research_artifacts as ra

SYMBOL, FAMILY = "XAUUSD", "session_range_breakout"
PARAMS: dict[str, Any] = {"rr": 1.5, "wait_bars": 12}
CELL = f"{SYMBOL}.{FAMILY}.rr=1.5_wb=12"
CLAIM_TEXT = "gold breaks the Asia range and carries into London"


def _plant(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, *, inputs: bool = True) -> Path:
    """A whole synthetic desk: docket, verdict, certificate, review, bars, lead document."""
    chain = tmp_path / "research_artifacts.jsonl"
    for name, value in (
        ("CHAIN", chain),
        ("REPORT", tmp_path / "reports" / "RESEARCH_ARTIFACTS.json"),
        ("DIGESTS", tmp_path / "data" / "digests.json"),
        ("GATE_LEDGER", tmp_path / "gate_verdict_ledger.jsonl"),
        ("DOCKET", tmp_path / "external_survivors.json"),
        ("SURVIVORS", tmp_path / "UNIVERSAL_SURVIVORS.json"),
        ("BLIND_REPORT", tmp_path / "BLIND_REVIEW.json"),
        ("BLIND_LEDGER", tmp_path / "blind_review_ledger.jsonl"),
        ("SOURCE_REGISTRY", tmp_path / "source_registry.json"),
        ("UNIVERSE", tmp_path / "universe"),
        ("INTEL_DIRS", (tmp_path / "intelligence",)),
    ):
        monkeypatch.setattr(ra, name, value)
    # The registry is ABSENT in every test: opening the real one would migrate it.
    monkeypatch.setattr(ra, "_registry_conn", lambda: (
        None, {"status": "absent", "path": None, "n": 0, "why": "patched absent in tests"}))
    if not inputs:
        return chain

    (tmp_path / "universe").mkdir()
    (tmp_path / "universe" / f"{SYMBOL}_H1.parquet").write_bytes(b"bytes that hash to something")
    (tmp_path / "intelligence").mkdir()
    (tmp_path / "intelligence" / "lead.json").write_text('{"claim": "a lead"}', encoding="utf-8")
    ra.DOCKET.write_text(json.dumps([{
        "symbol": SYMBOL, "family": FAMILY, "params": PARAMS, "source": "ground:test:forum",
        "url": "https://example.invalid/thread", "mechanism": CLAIM_TEXT,
        "producer": "test", "first_seen": "2026-09-20T00:00:00+00:00"}]), encoding="utf-8")
    ra.GATE_LEDGER.write_text(json.dumps({
        "at": "2026-09-21T00:00:00+00:00", "cell": CELL, "sym": SYMBOL, "family": FAMILY,
        "passed": True, "terminal_gate": "expected_value", "n": 2117, "expectancy": 0.148,
        "t": 6.5, "downstream_status": "CERTIFIED"}) + "\n", encoding="utf-8")
    ra.SOURCE_REGISTRY.write_text(json.dumps({"sources": {"ground:test:forum": {
        "source_id": "ground:test:forum", "url": "https://example.invalid/thread", "kind": "web",
        "language": "zh", "region": "cn", "first_seen": "2026-09-01T00:00:00+00:00"}}}),
        encoding="utf-8")
    ra.BLIND_LEDGER.write_text(json.dumps({
        "at": "2026-09-21T02:00:00+00:00", "cell": CELL, "verdict": "PASS",
        "reviewer": "blind_reviewer", "reproduced": {"n": 2117, "expectancy": 0.148, "t": 6.5},
        "basis": "engine.run_backtest"}) + "\n", encoding="utf-8")
    return chain


def _build(chain: Path, **kw: Any) -> dict[str, Any]:
    report, _cache = ra.build(budget_s=60.0, max_spines=5, max_leads=5, chain=chain, **kw)
    return report


# --------------------------------------------------------------- (a) the spine, appended once

def test_a_full_spine_is_appended_once_and_a_second_pass_appends_nothing(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    chain = _plant(tmp_path, monkeypatch)

    first = _build(chain)
    assert first["status"] == "OK", first["why"]
    verification = ac.verify(chain)
    assert verification.ok, verification.reason
    by_kind = verification.by_kind
    assert all(by_kind.get(kind, 0) >= 1 for kind in ac.KINDS), (
        f"the eight-link spine is not complete: {by_kind}")

    # The links are really linked: the review's lineage walks back to the source.
    review = ac.latest("review", CELL, path=chain)
    assert review is not None
    kinds = [r.kind for r in ac.lineage(review.artifact_id, path=chain)]
    assert kinds == list(ac.KINDS), kinds
    claim = ac.latest("claim", ac.digest(CLAIM_TEXT), path=chain)
    assert claim is not None and claim.payload["verbatim"] is True, "the verbatim claim was lost"
    hypothesis = ac.latest("hypothesis", CELL, path=chain)
    assert hypothesis is not None and hypothesis.payload["cell_id"] == CELL
    data = ac.latest("data", SYMBOL, path=chain)
    assert data is not None and data.payload["bars_digest"][f"{SYMBOL}|H1"] is not None

    before = chain.read_bytes()
    second = _build(chain)
    assert second["chain"]["appended"] == 0, second["links"]
    assert all(v["appended_this_pass"] == 0 for v in second["links"].values())
    assert second["spines"]["already_recorded"] == 1
    assert second["reviews"]["already_recorded"] == 1
    assert chain.read_bytes() == before, "a second pass rewrote an append-only chain"


def test_a2_the_bars_digest_is_the_file_bytes_and_is_cached(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    chain = _plant(tmp_path, monkeypatch)
    bars = ra.UNIVERSE / f"{SYMBOL}_H1.parquet"
    _build(chain)
    data = ac.latest("data", SYMBOL, path=chain)          # KEY_FIELDS["data"] keys on the symbol
    assert data is not None and data.payload["cell"] == CELL
    import hashlib
    assert data.payload["bars_digest"][f"{SYMBOL}|H1"] == hashlib.sha256(
        bars.read_bytes()).hexdigest()

    cache: dict[str, dict[str, Any]] = {}
    assert ra._digest_for(bars, cache) is not None
    calls: list[Path] = []

    def _never(path: Path) -> str:
        calls.append(path)
        return "x" * 64

    monkeypatch.setattr(ac, "sha256_file", _never)
    ra._digest_for(bars, cache)
    assert calls == [], "an unchanged parquet was hashed twice"


# --------------------------------------------------------------- (b) a tampered payload

def test_b_a_tampered_payload_is_detected_and_never_repaired(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    chain = _plant(tmp_path, monkeypatch)
    _build(chain)

    lines = chain.read_text(encoding="utf-8").splitlines()
    target = next(i for i, line in enumerate(lines) if json.loads(line)["kind"] == "hypothesis")
    row = json.loads(lines[target])
    row["payload"]["family"] = "a_family_nobody_tested"      # the hashes are left alone
    lines[target] = json.dumps(row, sort_keys=True, separators=(",", ":"))
    chain.write_text("\n".join(lines) + "\n", encoding="utf-8")
    tampered = chain.read_bytes()

    report = _build(chain)
    assert report["status"] == "BROKEN"
    assert report["chain"]["verified_before"]["first_break"] == target + 1
    assert "payload was edited" in str(report["chain"]["verified_before"]["reason"])
    assert str(target + 1) in str(report["why"])
    assert report["chain"]["appended"] == 0
    assert chain.read_bytes() == tampered, "the harvester repaired a broken chain"
    assert all(v["appended_this_pass"] == 0 for v in report["links"].values())


def test_b2_a_broken_chain_exits_two_and_still_publishes_its_report(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    chain = _plant(tmp_path, monkeypatch)
    _build(chain)
    lines = chain.read_text(encoding="utf-8").splitlines()
    chain.write_text("\n".join(lines[:-2] + lines[-1:]) + "\n", encoding="utf-8")  # a line removed
    assert ra.main(["--once", "--budget-s", "20"]) == 2
    doc = json.loads(ra.REPORT.read_text(encoding="utf-8"))
    assert doc["status"] == "BROKEN" and doc["chain"]["appended"] == 0


# --------------------------------------------------------------- (c) absent inputs

def test_c_absent_inputs_are_unmeasured_rows_and_the_report_is_still_written(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _plant(tmp_path, monkeypatch, inputs=False)
    assert ra.main(["--once", "--budget-s", "20"]) == 0
    doc = json.loads(ra.REPORT.read_text(encoding="utf-8"))

    assert doc["status"] == "UNMEASURED"
    assert "every input is absent" in doc["why"]
    for name, row in doc["inputs"].items():
        assert row["status"] == "absent", name
        assert row["why"], f"{name} was absent with no reason given"
    for kind, link in doc["links"].items():
        assert link["status"] == "UNMEASURED", kind
        assert link["records"] == 0 and link["why"]
    assert not ra.CHAIN.exists(), "an empty pass created a chain file"


def test_c2_a_cell_with_no_bars_still_records_its_data_link_as_unmeasured(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    chain = _plant(tmp_path, monkeypatch)
    (ra.UNIVERSE / f"{SYMBOL}_H1.parquet").unlink()
    report = _build(chain)
    assert report["spines"]["no_data"] == 1
    data = ac.latest("data", SYMBOL, path=chain)
    assert data is not None
    assert data.payload["status"] == "UNMEASURED" and data.payload["why"]
    assert data.payload["bars_digest"] == {}, "a missing parquet must not hash to anything"
    assert ac.verify(chain).ok, "the spine must stay linked when an input is unmeasured"


def test_c3_the_record_cap_floors_when_the_memory_counter_cannot_be_read() -> None:
    assert ra.max_records_for(None) == ra.MIN_RECORDS
    assert ra.max_records_for(8_000.0) > ra.MIN_RECORDS
    assert ra.max_records_for(1e9) == ra.MAX_RECORDS_CEIL


# --------------------------------------------------------------- (d) --dry-run

def test_d_dry_run_writes_nothing_at_all(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _plant(tmp_path, monkeypatch)
    assert ra.main(["--once", "--budget-s", "20", "--dry-run"]) == 0
    assert not ra.CHAIN.exists(), "--dry-run appended to the chain"
    assert not ra.REPORT.exists(), "--dry-run wrote the report"
    assert not ra.DIGESTS.exists(), "--dry-run wrote the digest cache"
    assert not ac.lock_path(ra.CHAIN).exists(), "--dry-run took the chain's write lock"

    planned, _cache = ra.build(budget_s=60.0, max_spines=5, max_leads=5, chain=ra.CHAIN,
                               apply=False)
    assert planned["chain"]["appended"] > 0, "a dry run must still say what it would append"
    assert not ra.CHAIN.exists()


# --------------------------------------------------------------- the review's anchor

def test_a_review_of_a_parameterised_cell_attaches_to_its_certificate(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """The blind reviewer names `external.SYM.family.rr=..._wb=...`; the certificate is keyed
    `external.SYM.family`. A review hung on nothing is not provenance."""
    chain = _plant(tmp_path, monkeypatch)
    ra.GATE_LEDGER.unlink()
    key = f"external.{SYMBOL}.{FAMILY}"
    ra.SURVIVORS.write_text(json.dumps({"survivors": {key: {
        "hunt": "external_discoveries", "cell": f"{SYMBOL}.{FAMILY}", "sym": SYMBOL, "days": 2101,
        "gates": {"expected_value": {"passed": True, "ev": 0.187},
                  "lockbox": {"passed": True}},
        "shadow_spec": {"symbol": SYMBOL, "family": FAMILY, "selector": "asia"},
        "gated_at": "2026-08-25T22:00:42+00:00"}}}), encoding="utf-8")
    ra.BLIND_LEDGER.write_text(json.dumps({
        "at": "2026-09-21T02:00:00+00:00", "cell": f"{key}.rr=1.5_wb=12", "verdict": "PASS",
        "reviewer": "blind_reviewer", "reproduced": {"n": 2117}}) + "\n", encoding="utf-8")

    report = _build(chain)
    assert report["certificates"]["built"] == 1
    assert report["reviews"]["built"] == 1
    assert report["reviews"]["by_anchor_basis"] == {"prefix": 1}
    review = ac.latest("review", f"{key}.rr=1.5_wb=12", path=chain)
    assert review is not None
    assert [r.kind for r in ac.lineage(review.artifact_id, path=chain)][-3:] == [
        "config", "result", "review"]
    assert ac.verify(chain).ok


def test_an_unknown_review_verdict_is_unmeasured_and_never_a_pass(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    chain = _plant(tmp_path, monkeypatch)
    ra.BLIND_LEDGER.write_text(json.dumps({
        "at": "2026-09-21T03:00:00+00:00", "cell": CELL, "verdict": "looks fine to me",
        "reviewer": "someone"}) + "\n", encoding="utf-8")
    _build(chain)
    review = ac.latest("review", CELL, path=chain)
    assert review is not None and review.payload["verdict"] == "UNMEASURED"
