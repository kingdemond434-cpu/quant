"""A pass persists as ONE transaction: a killed pass changes nothing or everything, never half.

The defect (gap 2 of the 2026-10-21 timeout audit): `learn_priors` saved the posterior and
`update_unrunnable_bank` wrote the bank and the readmission log mid-pass, while the cursor that
says which verdicts the posterior already holds (`priors_cursor`) and the re-admissions the next
cohort is measured against (`readmitted_to_next`) only reached disk with the ratchet in `write`.
A pass killed in between taught the same verdicts twice on the next run, and left the bank ahead
of the ratchet. Also pinned: the producer stops itself at its budget, uncommitted, with a named
TIMEOUT artifact, and never earlier than the cap the cycle grants.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import textwrap
import time
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

DESK = Path(__file__).resolve().parents[1]
ROOT = DESK.parent.parent
for _p in (str(DESK), str(ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from libs.research import research_priors  # noqa: E402
from research import docket_keff as dk  # noqa: E402
from research import judge_coverage as jc  # noqa: E402

NOW = datetime(2026, 10, 20, 20, 0, tzinfo=UTC)
FAMS = ("alpha", "beta", "gamma")


class _Frozen(datetime):
    @classmethod
    def now(cls, tz=None):  # type: ignore[override]
        return NOW if tz is None else NOW.astimezone(tz)


def _point(monkeypatch: pytest.MonkeyPatch, d: Path) -> dict[str, Path]:
    """Every path a pass reads or writes, under `d`."""
    paths = {"bank": d / "unrunnable_specs.json", "ratchet": d / "judge_backlog_ratchet.json",
             "report": d / "reports" / "JUDGE_COVERAGE.json",
             "timeout": d / "reports" / "JUDGE_COVERAGE_TIMEOUT.json",
             "handoff": d / "conversion_handoff.json", "ledger": d / "gate.jsonl",
             "gates": d / "gates.json", "docket": d / "docket.json",
             "keff": d / "reports" / "DOCKET_KEFF_ORDER.json", "priors": d / "research_priors",
             "log": d / "not_testable_readmissions.jsonl"}
    monkeypatch.setattr(jc, "UNRUNNABLE_BANK", paths["bank"])
    monkeypatch.setattr(jc, "RATCHET", paths["ratchet"])
    monkeypatch.setattr(jc, "REPORT", paths["report"])
    monkeypatch.setattr(jc, "TIMEOUT_REPORT", paths["timeout"])
    monkeypatch.setattr(jc, "CONVERSION_HANDOFF", paths["handoff"])
    monkeypatch.setattr(jc, "GATE_LEDGER", paths["ledger"])
    monkeypatch.setattr(jc, "GATES_REPORT", paths["gates"])
    monkeypatch.setattr(jc, "DOCKET", paths["docket"])
    monkeypatch.setattr(dk, "REPORT", paths["keff"])
    monkeypatch.setattr(research_priors, "STATE_DIR", paths["priors"])
    # Freeze the two clocks a pass stamps into what it persists, so a re-run is comparable
    # byte for byte with the run it must reproduce.
    monkeypatch.setattr(research_priors, "datetime", _Frozen)
    monkeypatch.setattr(dk, "datetime", _Frozen)
    return paths


def _inputs(d: Path) -> list[dict]:
    """A docket, a ledger the priors learn from, a gauntlet report that parks cells, an old bank
    row the pass re-admits, and a prior reading -- so every one of the six writes happens."""
    d.mkdir(parents=True, exist_ok=True)
    rows = [{"symbol": f"S{i}", "family": FAMS[i % 3], "params": {"rr": i},
             "first_seen": (NOW - timedelta(hours=5)).isoformat()} for i in range(60)]
    (d / "docket.json").write_text(json.dumps(rows), "utf-8")
    ledger = []
    for i in range(90):
        ledger.append({"at": (NOW - timedelta(hours=1 + i % 30)).isoformat(),
                       "cell": f"X{i}.{FAMS[i % 3]}.p={i}", "family": FAMS[i % 3],
                       "passed": i % 17 == 0,
                       "terminal_gate": "PASSED" if i % 17 == 0 else "in_sample_screen"})
    (d / "gate.jsonl").write_text("".join(json.dumps(r) + "\n" for r in ledger), "utf-8")
    verdicts = [{"cell": f"P{i}.alpha.p={i}", "sym": f"P{i}", "family": "alpha",
                 "unmeasured": True, "days": 5, "unknown_reason": "lockbox_consumed_history"}
                for i in range(4)]
    (d / "gates.json").write_text(json.dumps({"verdicts": verdicts}), "utf-8")
    old = (NOW - timedelta(days=120)).isoformat()
    (d / "unrunnable_specs.json").write_text(json.dumps({"OLD.alpha.p=1": {
        "reason": "never_fires", "sym": "NOSUCH", "family": "alpha", "tf": "H1", "days": 0,
        "bar_bytes": 10, "parked_at": old, "not_testable_since": old}}), "utf-8")
    (d / "judge_backlog_ratchet.json").write_text(json.dumps({
        "at": (NOW - timedelta(hours=1)).isoformat(), "backlog_basis": jc.BACKLOG_BASIS,
        "families": {f: {"unjudged": 20, "queued": 5} for f in FAMS},
        "priors_cursor": ""}), "utf-8")
    (d / "not_testable_readmissions.jsonl").write_text(
        json.dumps({"at": old, "readmitted": 0, "by_reason": {}}) + "\n", "utf-8")
    return rows


def _state(p: dict[str, Path]) -> dict[str, object]:
    """What a pass leaves on disk. The priors are compared without their wall-clock stamps."""
    def strip(x: object) -> object:
        if isinstance(x, dict):
            return {k: strip(v) for k, v in x.items() if k not in ("last_at", "updated_at")}
        return x
    out: dict[str, object] = {}
    root = str(p["bank"].parent)                 # the report names its own paths; mask the dir
    for k in ("bank", "ratchet", "report", "handoff", "log", "timeout"):
        out[k] = (p[k].read_text("utf-8").replace(json.dumps(root)[1:-1], "<D>")
                  .replace(root, "<D>") if p[k].exists() else None)
    for name in ("beta.json", "dirichlet.json"):
        f = p["priors"] / name
        out[name] = strip(json.loads(f.read_text("utf-8"))) if f.exists() else None
    return out


def _leftovers(d: Path) -> list[str]:
    return sorted(str(x.relative_to(d)) for x in d.rglob("*")
                  if jc.TXN_TAG in x.name or x.name.startswith(jc.TXN_MANIFEST_PREFIX))


def _pass(rows: list[dict]) -> None:
    doc = jc.build([dict(r) for r in rows], now=NOW, defer=True)
    jc.write(doc)


def _family_n(p: dict[str, Path]) -> dict[str, int]:
    beta = json.loads((p["priors"] / "beta.json").read_text("utf-8"))
    return {f: int(r["n"]) for f, r in (beta["dimensions"].get("family") or {}).items()}


def test_a_pass_killed_before_write_changes_nothing_and_never_double_counts(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    # THE REFERENCE: one clean pass.
    ref = _point(monkeypatch, tmp_path / "ref")
    rows = _inputs(tmp_path / "ref")
    _pass(rows)
    reference = _state(ref)
    assert _family_n(ref) == {"alpha": 30, "beta": 30, "gamma": 30}, "each verdict once"

    # THE KILL: build has taught the priors and moved the bank, then the process dies before
    # `write` (the cycle's timeout). Staged files stay behind exactly as a kill leaves them.
    p = _point(monkeypatch, tmp_path / "run")
    rows = _inputs(tmp_path / "run")
    before = _state(p)
    doc = jc.build([dict(r) for r in rows], now=NOW, defer=True)
    assert doc["priors_learned"]["recorded"] == 90 and doc["unrunnable"]["readmitted_not_testable"]
    del doc                                              # dies here: no write, no discard
    jc._PASS = None
    assert _state(p) == before, "a pass killed before its commit point changes nothing"
    assert _leftovers(tmp_path / "run"), "the kill leaves its staged writes as orphans"

    # THE NEXT PASS teaches each verdict ONCE and lands exactly where a clean pass lands.
    _pass(rows)
    assert _family_n(p) == {"alpha": 30, "beta": 30, "gamma": 30}
    assert _state(p) == reference


def test_a_kill_after_the_commit_point_is_rolled_forward(tmp_path: Path,
                                                        monkeypatch: pytest.MonkeyPatch) -> None:
    ref = _point(monkeypatch, tmp_path / "ref")
    rows = _inputs(tmp_path / "ref")
    _pass(rows)
    reference = _state(ref)

    p = _point(monkeypatch, tmp_path / "run")
    rows = _inputs(tmp_path / "run")
    doc = jc.build([dict(r) for r in rows], now=NOW, defer=True)
    txn = doc.pop("_txn")
    jc._write_staged(doc, txn, report=None, ratchet=None)
    txn.write_manifest()                                 # committed ...
    ops = list(txn.ops.values())
    jc._apply_ops(ops[:2])                               # ... and killed two renames in
    half = _state(p)
    assert half != reference, "the kill really did leave a half-moved state"
    assert jc.recover_transactions() == 1
    assert _state(p) == reference
    assert not [x for x in _leftovers(tmp_path / "run") if x.startswith(jc.TXN_MANIFEST_PREFIX)]
    # A further pass starts from the consistent state: priors charged once, not twice.
    assert _family_n(p) == {"alpha": 30, "beta": 30, "gamma": 30}


def test_orphans_of_a_killed_pass_are_swept_once_old(tmp_path: Path,
                                                    monkeypatch: pytest.MonkeyPatch) -> None:
    p = _point(monkeypatch, tmp_path / "run")
    rows = _inputs(tmp_path / "run")
    jc.build([dict(r) for r in rows], now=NOW, defer=True)
    jc._PASS = None
    left = [x for x in (tmp_path / "run").rglob("*") if jc.TXN_TAG in x.name]
    assert left
    jc.recover_transactions()
    assert all(x.exists() for x in left), "a young staged file may be a live pass's"
    old = time.time() - jc.TXN_ORPHAN_AGE_S - 60
    for x in left:
        os.utime(x, (old, old))
    jc.recover_transactions()
    assert not _leftovers(tmp_path / "run")
    assert p["bank"].exists()


def test_a_killed_subprocess_leaves_every_target_untouched(tmp_path: Path,
                                                          monkeypatch: pytest.MonkeyPatch) -> None:
    """The real thing: `main` in a child, killed by the parent's timeout while `write` is
    staging, as `hourly_cycle._producer_impl` kills an overrunning leg."""
    d = tmp_path / "run"
    p = _point(monkeypatch, d)
    _inputs(d)
    before = _state(p)
    child = textwrap.dedent(f"""
        import sys, time
        from pathlib import Path
        sys.path[:0] = [{str(DESK)!r}, {str(ROOT)!r}]
        from libs.research import research_priors
        from research import docket_keff as dk
        from research import judge_coverage as jc
        d = Path({str(d)!r})
        jc.UNRUNNABLE_BANK = d / "unrunnable_specs.json"
        jc.RATCHET = d / "judge_backlog_ratchet.json"
        jc.REPORT = d / "reports" / "JUDGE_COVERAGE.json"
        jc.TIMEOUT_REPORT = d / "reports" / "JUDGE_COVERAGE_TIMEOUT.json"
        jc.CONVERSION_HANDOFF = d / "conversion_handoff.json"
        jc.GATE_LEDGER = d / "gate.jsonl"
        jc.GATES_REPORT = d / "gates.json"
        jc.DOCKET = d / "docket.json"
        dk.REPORT = d / "reports" / "DOCKET_KEFF_ORDER.json"
        research_priors.STATE_DIR = d / "research_priors"
        _stage = jc._write_staged
        def stalled(*a, **k):
            _stage(*a, **k)
            print("staged", flush=True)
            time.sleep(60)
        jc._write_staged = stalled
        jc.main(["--once"])
    """)
    with pytest.raises(subprocess.TimeoutExpired):
        subprocess.run([sys.executable, "-c", child], capture_output=True, text=True,
                       timeout=20, check=False)
    assert _state(p) == before


def test_the_budget_stops_the_pass_uncommitted_with_a_named_timeout(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    d = tmp_path / "run"
    p = _point(monkeypatch, d)
    _inputs(d)
    monkeypatch.delenv("QUANT_LEG_BUDGET_S", raising=False)
    before = _state(p)
    assert jc.main(["--once", "--budget-s", "0"]) == jc.TIMEOUT_EXIT
    after = _state(p)
    timeout = json.loads(p["timeout"].read_text("utf-8"))
    assert timeout["verdict"] == "TIMEOUT" and timeout["committed"] is False
    after["timeout"] = None
    assert after == before, "a pass stopped at its budget writes nothing but the TIMEOUT"
    # The next completed pass commits and clears the TIMEOUT in the same transaction.
    assert jc.main(["--once", "--budget-s", "600"]) == 0
    assert not p["timeout"].exists() and p["report"].exists()
    assert not _leftovers(d)


def test_the_stop_never_falls_below_the_cap_the_cycle_grants(
        monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("QUANT_LEG_BUDGET_S", raising=False)
    assert jc.stop_after_s(120.0) == (120.0, None)
    monkeypatch.setenv("QUANT_LEG_BUDGET_S", "300")
    assert jc.stop_after_s(120.0) == (300.0 - jc.COMMIT_MARGIN_S, 300.0)
    monkeypatch.setenv("QUANT_LEG_BUDGET_S", "100")      # a cap below the budget: budget wins
    assert jc.stop_after_s(120.0) == (120.0, 100.0)
