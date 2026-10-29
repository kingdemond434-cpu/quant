"""Two concurrent judge_coverage passes never lose each other's park or readmission line.

The defect (audit of the judge speed train a5847f82a, R9, MUST-FIX): inside a pass the bank,
the sidecar and the readmission log are STAGED under `_outstanding_lock` and only renamed at the
pass's commit point, which came AFTER the lock was released. A second pass in that window read
the pre-commit bank, staged its own, and committed last:

    A: reads bank {OLD}, parks PA, re-admits OLD, stages, RELEASES the lock
    B: takes the lock, reads bank {OLD} (A not committed), parks PB, re-admits OLD again
    A: commits  -> bank {PA},          log += A's line (readmitted 1)
    B: commits  -> bank {PB},          log  = B's copy of the OLD log + B's line

so A's park of PA and A's readmission line were lost, and OLD's readmission was counted twice.
The fix holds the lock from the bank's read until the pass's own commit (and lands the
readmission line at the commit, under the lock), so B reads the bank A committed.

The probe is two real processes, sequenced by files: A is held at its commit point; B is let
run up to the lock and then given ten seconds to reach ITS commit point. On the base it does
(it read the old bank); with the fix it cannot until A has committed and released.
"""
from __future__ import annotations

import json
import subprocess
import sys
import textwrap
import time
from datetime import UTC, datetime, timedelta
from pathlib import Path

DESK = Path(__file__).resolve().parents[1]
ROOT = DESK.parent.parent
for _p in (str(DESK), str(ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from research import judge_coverage as jc  # noqa: E402

NOW = datetime(2026, 10, 20, 20, 0, tzinfo=UTC)
FAMS = ("alpha", "beta", "gamma")
OLD_CELL = "OLD.alpha.p=1"


def _inputs(d: Path) -> None:
    """The shared state both passes read and write, plus one gauntlet report per pass, each
    parking a different cell (PA for A, PB for B)."""
    d.mkdir(parents=True, exist_ok=True)
    rows = [{"symbol": f"S{i}", "family": FAMS[i % 3], "params": {"rr": i},
             "first_seen": (NOW - timedelta(hours=5)).isoformat()} for i in range(30)]
    (d / "docket.json").write_text(json.dumps(rows), "utf-8")
    (d / "gate.jsonl").write_text("", "utf-8")
    for who in ("A", "B"):
        (d / f"gates_{who}.json").write_text(json.dumps({"verdicts": [
            {"cell": f"P{who}.alpha.p=1", "sym": f"P{who}", "family": "alpha",
             "unmeasured": True, "days": 5, "unknown_reason": "lockbox_consumed_history"}]}),
            "utf-8")
    old = (NOW - timedelta(days=120)).isoformat()
    # One bank row that is DUE for readmission: each pass that reads it re-admits it.
    (d / "unrunnable_specs.json").write_text(json.dumps({OLD_CELL: {
        "reason": "never_fires", "sym": "NOSUCH", "family": "alpha", "tf": "H1", "days": 0,
        "bar_bytes": 10, "parked_at": old, "not_testable_since": old}}), "utf-8")
    (d / "not_testable_readmissions.jsonl").write_text(
        json.dumps({"at": old, "readmitted": 0, "by_reason": {}}) + "\n", "utf-8")


def _child(d: Path, sig: Path, who: str) -> str:
    """`judge_coverage.main(["--once"])` on the shared state, held at its commit point until the
    parent says go. `at_lock` is touched when the pass first asks for the bank's lock."""
    return textwrap.dedent(f"""
        import sys, time
        from pathlib import Path
        sys.path[:0] = [{str(DESK)!r}, {str(ROOT)!r}]
        from libs.research import research_priors
        from research import docket_keff as dk
        from research import judge_coverage as jc
        d, sig, who = Path({str(d)!r}), Path({str(sig)!r}), {who!r}
        jc.UNRUNNABLE_BANK = d / "unrunnable_specs.json"
        jc.RATCHET = d / "judge_backlog_ratchet.json"
        jc.REPORT = d / "reports" / f"JUDGE_COVERAGE_{{who}}.json"
        jc.TIMEOUT_REPORT = d / "reports" / f"JUDGE_COVERAGE_TIMEOUT_{{who}}.json"
        jc.CONVERSION_HANDOFF = d / "conversion_handoff.json"
        jc.GATE_LEDGER = d / "gate.jsonl"
        jc.GATES_REPORT = d / f"gates_{{who}}.json"
        jc.DOCKET = d / "docket.json"
        dk.REPORT = d / "reports" / f"DOCKET_KEFF_ORDER_{{who}}.json"
        research_priors.STATE_DIR = d / f"research_priors_{{who}}"

        def _wait(name):
            t = time.monotonic() + 120
            while not (sig / name).exists():
                if time.monotonic() > t:
                    raise SystemExit(f"{{who}}: no {{name}}")
                time.sleep(0.05)

        _acquire = jc._SidecarLock.acquire
        def acquire(self, *a, **k):
            (sig / f"{{who}}_at_lock").touch()
            return _acquire(self, *a, **k)
        jc._SidecarLock.acquire = acquire

        _commit = jc._Txn.commit
        def commit(self):
            (sig / f"{{who}}_staged").touch()
            _wait(f"{{who}}_go")
            _commit(self)
            (sig / f"{{who}}_done").touch()
        jc._Txn.commit = commit
        rc = jc.main(["--once", "--budget-s", "600"])
        (sig / f"{{who}}_rc").write_text(str(rc))
    """)


def _wait_for(p: Path, timeout: float) -> bool:
    t = time.monotonic() + timeout
    while time.monotonic() < t:
        if p.exists():
            return True
        time.sleep(0.05)
    return p.exists()


def test_a_concurrent_pass_never_loses_the_holders_park_or_readmission_line(
        tmp_path: Path) -> None:
    d, sig = tmp_path / "state", tmp_path / "sig"
    _inputs(d)
    sig.mkdir()
    procs = []
    try:
        procs.append(subprocess.Popen([sys.executable, "-c", _child(d, sig, "A")],
                                      stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                      text=True))
        assert _wait_for(sig / "A_staged", 120), "A never reached its commit point"
        procs.append(subprocess.Popen([sys.executable, "-c", _child(d, sig, "B")],
                                      stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                      text=True))
        assert _wait_for(sig / "B_at_lock", 120), "B never asked for the bank's lock"
        # THE WINDOW: A has staged and is not committed. If B can reach its own commit point now
        # it read the bank A has not committed -- the lost update.
        b_raced = _wait_for(sig / "B_staged", 10)
        (sig / "A_go").touch()
        assert _wait_for(sig / "A_done", 120), "A never committed"
        (sig / "B_go").touch()
        outs = [p.communicate(timeout=180) for p in procs]
    finally:
        for p in procs:
            if p.poll() is None:
                p.kill()
    for who, (out, err) in zip("AB", outs, strict=True):
        assert (sig / f"{who}_rc").read_text() == "0", f"{who}: {out[-2000:]} {err[-2000:]}"

    bank = json.loads((d / "unrunnable_specs.json").read_text("utf-8"))
    lines = [json.loads(x) for x in
             (d / "not_testable_readmissions.jsonl").read_text("utf-8").splitlines()]
    assert "PA.alpha.p=1" in bank, "A's park was lost to B's commit"
    assert "PB.alpha.p=1" in bank
    assert OLD_CELL not in bank
    assert len(lines) == 3, f"the seed line, then one line per pass: {lines}"
    assert [ln.get("readmitted") for ln in lines] == [0, 1, 0], (
        "OLD is re-admitted once, by A; B read the bank A committed and re-admits nothing")
    assert not list(d.rglob("*.lock")), "both passes released the bank's lock"
    assert not b_raced, "B reached its commit point while A held an uncommitted bank"


def test_a_pass_holds_the_banks_lock_until_its_commit_and_releases_it_on_discard(
        tmp_path: Path, monkeypatch) -> None:
    """The lock taken for the bank's read-modify-write is the txn's until commit or discard."""
    bank = tmp_path / "unrunnable_specs.json"
    lock = tmp_path / (jc.NEEDS_DATA_OUTSTANDING.name + ".lock")
    at = NOW.isoformat(timespec="seconds")
    named = {"PA.alpha.p=1": {"reason": "never_fires", "sym": "PA", "family": "alpha",
                              "tf": "H1", "days": 0, "bar_bytes": 10}}
    for end in ("commit", "discard"):
        bank.write_text("{}", "utf-8")
        txn = jc._Txn(tmp_path)
        with jc._pass_memo() as memo:
            memo[("txn",)] = txn
            got = jc.update_unrunnable_bank(named, at=at, path=bank)
            memo.pop(("txn",), None)
        assert got["bank_write"] == "WRITTEN"
        assert lock.exists(), f"the lock outlives the bank update until the {end}"
        assert json.loads(bank.read_text("utf-8")) == {}, "nothing lands before the commit"
        getattr(txn, end)()
        assert not lock.exists(), f"{end} releases the lock"
        landed = json.loads(bank.read_text("utf-8"))
        assert ("PA.alpha.p=1" in landed) is (end == "commit")
        log = tmp_path / jc.READMISSION_LOG.name
        n_lines = len(log.read_text("utf-8").splitlines()) if log.exists() else 0
        assert n_lines == 1, "one line per committed pass, none from a discarded one"
