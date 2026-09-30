"""Gate rejection reasons must reach git as a small digest, never as the data lake.

`gate_verdict_ledger.jsonl` and `universal_gates_external.json` are gitignored, so the newest
committed REJECT with its gate named was 2026-09-12 while the box judged every hour. The digest is
the bounded committed answer; these pin its shape, its bounds and its honesty about absence.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

DESK = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(DESK / "research"))

import gate_verdict_digest as gvd  # noqa: E402


def _ledger(path: Path, n: int) -> None:
    rows = []
    for i in range(n):
        rows.append({"at": f"2026-09-30T{i % 24:02d}:00:00+00:00", "cell": f"EURUSD.f{i % 3}.p={i}",
                     "family": f"f{i % 3}", "sym": "EURUSD" if i % 2 else "XAUUSD",
                     "passed": i % 10 == 0,
                     "terminal_gate": "PASSED" if i % 10 == 0 else
                     ("deflated_sharpe" if i % 2 else "cpcv"),
                     "downstream_status": None})
    path.write_text("\n".join(json.dumps(r) for r in rows) + "\n{broken\n", "utf-8")


def _sweep(path: Path) -> None:
    path.write_text(json.dumps({"swept_at": "2026-09-30T12:00:00+00:00", "verdicts": [
        {"cell": "a", "family": "carry", "passed": False, "terminal_gate": "deflated_sharpe",
         "failed_gates": ["deflated_sharpe", "cpcv"],
         "stages": {"deflated_sharpe": {"passed": False, "message": "dsr 0.41 < 0.95"},
                    "cpcv": {"passed": False, "value": 0.2, "threshold": 0.5}}},
        {"cell": "b", "family": "carry", "passed": False, "terminal_gate": "economic_prior",
         "stages": {"economic_prior": {"passed": False, "reason": "no mechanism"}}},
        {"cell": "c", "family": "gap", "passed": True, "terminal_gate": "PASSED", "stages": {}},
    ]}), "utf-8")


def test_counts_reasons_and_latest(tmp_path: Path) -> None:
    led, swp = tmp_path / "ledger.jsonl", tmp_path / "sweep.json"
    _ledger(led, 200)
    _sweep(swp)
    doc = gvd.build(led, swp, latest_n=5)
    assert doc["status"] == "MEASURED"
    L = doc["ledger"]
    assert L["rows"] == 200 and L["malformed_rows"] == 1 and L["passed_rows"] == 20
    assert sum(L["rejections_by_terminal_gate"].values()) == 180
    assert set(L["rejections_by_family"]) == {"f0", "f1", "f2"}
    assert len(L["latest"]) == 5 and L["latest"][0]["cell"] == "EURUSD.f1.p=199", \
        "latest must be newest first"
    S = doc["latest_sweep"]
    assert S["terminal_gates"] == {"deflated_sharpe": 1, "economic_prior": 1}
    assert S["any_fail_by_gate"]["cpcv"] == 1
    assert S["reasons_by_gate"]["deflated_sharpe"] == ["dsr 0.41 < 0.95"]
    assert S["reasons_by_gate"]["cpcv"] == ["value=0.2, threshold=0.5"]
    assert S["terminal_gates_by_family"]["carry"] == {"deflated_sharpe": 1, "economic_prior": 1}


def test_absent_inputs_are_unmeasured_not_zero(tmp_path: Path) -> None:
    doc = gvd.build(tmp_path / "none.jsonl", tmp_path / "none.json")
    assert doc["status"] == "UNMEASURED"
    assert "rows" not in doc["ledger"], "an absent ledger was reported as a count"
    assert doc["ledger"]["source"]["status"] == "UNMEASURED"


def test_the_digest_stays_small(tmp_path: Path) -> None:
    led, swp = tmp_path / "ledger.jsonl", tmp_path / "sweep.json"
    rows = [{"at": "2026-09-30T00:00:00+00:00", "cell": f"c{i}", "family": f"fam{i % 500}",
             "sym": f"S{i % 900}", "passed": False, "terminal_gate": f"g{i % 12}"}
            for i in range(60_000)]
    led.write_text("\n".join(json.dumps(r) for r in rows), "utf-8")
    _sweep(swp)
    out = gvd.write(gvd.build(led, swp), tmp_path / "GATE_VERDICT_DIGEST.json")
    doc = json.loads(out.read_text("utf-8"))
    assert len(doc["ledger"]["rejections_by_family"]) == gvd.TOP_FAMILIES
    assert doc["ledger"]["families_omitted"] == 500 - gvd.TOP_FAMILIES
    assert out.stat().st_size < 256 * 1024, "the digest is turning into the data lake it replaces"


def test_it_is_published_and_allowlisted() -> None:
    root = DESK.parent.parent
    sync = (DESK / "scripts" / "sync_shadow_to_git.ps1").read_text("utf-8", errors="ignore")
    assert '"desks/mt5/reports/GATE_VERDICT_DIGEST.json"' in sync
    assert "!desks/mt5/reports/GATE_VERDICT_DIGEST.json" in (root / ".gitignore").read_text(
        "utf-8").splitlines()
