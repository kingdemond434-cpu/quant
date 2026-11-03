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
        rows.append(
            {
                "at": f"2026-09-30T{i % 24:02d}:00:00+00:00",
                "cell": f"EURUSD.f{i % 3}.p={i}",
                "family": f"f{i % 3}",
                "sym": "EURUSD" if i % 2 else "XAUUSD",
                "passed": i % 10 == 0,
                "terminal_gate": "PASSED"
                if i % 10 == 0
                else ("deflated_sharpe" if i % 2 else "cpcv"),
                "downstream_status": None,
            }
        )
    path.write_text("\n".join(json.dumps(r) for r in rows) + "\n{broken\n", "utf-8")


def _sweep(path: Path) -> None:
    path.write_text(
        json.dumps(
            {
                "swept_at": "2026-09-30T12:00:00+00:00",
                "verdicts": [
                    {
                        "cell": "a",
                        "family": "carry",
                        "passed": False,
                        "terminal_gate": "deflated_sharpe",
                        "failed_gates": ["deflated_sharpe", "cpcv"],
                        "stages": {
                            "deflated_sharpe": {"passed": False, "message": "dsr 0.41 < 0.95"},
                            "cpcv": {"passed": False, "value": 0.2, "threshold": 0.5},
                        },
                    },
                    {
                        "cell": "b",
                        "family": "carry",
                        "passed": False,
                        "terminal_gate": "economic_prior",
                        "stages": {"economic_prior": {"passed": False, "reason": "no mechanism"}},
                    },
                    {
                        "cell": "c",
                        "family": "gap",
                        "passed": True,
                        "terminal_gate": "PASSED",
                        "stages": {},
                    },
                ],
            }
        ),
        "utf-8",
    )


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
    assert len(L["latest"]) == 5 and L["latest"][0]["cell"] == "EURUSD.f1.p=199", (
        "latest must be newest first"
    )
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
    rows = [
        {
            "at": "2026-09-30T00:00:00+00:00",
            "cell": f"c{i}",
            "family": f"fam{i % 500}",
            "sym": f"S{i % 900}",
            "passed": False,
            "terminal_gate": f"g{i % 12}",
        }
        for i in range(60_000)
    ]
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
    assert (
        "!desks/mt5/reports/GATE_VERDICT_DIGEST.json"
        in (root / ".gitignore").read_text("utf-8").splitlines()
    )


# ------------------------------------------------------------------ the terminal stamp (2026-10-20)
def _rows_mixed() -> list[dict]:
    """Every shape the ledger holds: stamped rows, and the unstamped rows written before them."""
    return [
        # unstamped, as written 2026-09-30..10-20: UNKNOWN with its reason beside it
        {
            "cell": "u1",
            "family": "f",
            "passed": False,
            "terminal_gate": "UNKNOWN",
            "unknown_reason": "no_signals",
            "failed_gates": ["no_signals"],
        },
        # unstamped, as written 2026-09-12..30: UNKNOWN and nothing else -- a legacy DEFECT
        {"cell": "u2", "family": "f", "passed": False, "terminal_gate": "UNKNOWN"},
        {"cell": "r1", "family": "f", "passed": False, "terminal_gate": "in_sample_screen"},
        {"cell": "p1", "family": "f", "passed": True, "terminal_gate": "PASSED"},
        # stamped by the judge
        {
            "cell": "s1",
            "family": "g",
            "passed": False,
            "terminal_gate": "UNKNOWN",
            "terminal_kind": "UNMEASURED",
            "terminal_gate_id": "observations",
            "terminal_reason": "lockbox_consumed_history",
        },
        {
            "cell": "s2",
            "family": "g",
            "passed": False,
            "terminal_gate": "deflated_sharpe",
            "terminal_kind": "RULED",
            "terminal_gate_id": "deflated_sharpe",
            "terminal_reason": "deflated_sharpe: dsr=0.41",
        },
    ]


def test_every_unknown_is_split_by_the_gate_that_stopped_it(tmp_path: Path) -> None:
    led, swp = tmp_path / "ledger.jsonl", tmp_path / "sweep.json"
    led.write_text("\n".join(json.dumps(r) for r in _rows_mixed()) + "\n", "utf-8")
    _sweep(swp)
    L = gvd.build(led, swp)["ledger"]
    # The legacy keys are unchanged: three rows still read UNKNOWN there.
    assert L["rejections_by_terminal_gate"]["UNKNOWN"] == 3
    assert L["by_terminal_kind"] == {"UNMEASURED": 2, "RULED": 2, "PASSED": 1, "DEFECT": 1}
    assert L["rejections_by_terminal_gate_id"] == {"in_sample_screen": 1, "deflated_sharpe": 1}
    assert L["unmeasured_by_reason"] == {"no_signals": 1, "lockbox_consumed_history": 1}
    td = L["terminal_defects"]
    assert td["n"] == 1 and td["sample"][0]["cell"] == "u2"
    assert td["stamped_by_the_judge"] == 0 and td["derived_from_unstamped_rows"] == 1
    assert L["rows_carrying_the_stamp"] == 2


def test_a_legacy_defect_is_named_but_only_a_stamped_one_raises_the_status(tmp_path: Path) -> None:
    led, swp = tmp_path / "ledger.jsonl", tmp_path / "sweep.json"
    led.write_text("\n".join(json.dumps(r) for r in _rows_mixed()) + "\n", "utf-8")
    _sweep(swp)
    head = gvd.build(led, swp)["terminal_defects"]
    assert head == {
        "ledger": 1,
        "ledger_stamped": 0,
        "ledger_legacy": 1,
        "latest_sweep": 0,
        "latest_sweep_stamped": False,
        "status": "CLEAN",
    }
    with led.open("a", encoding="utf-8") as fh:
        fh.write(
            json.dumps(
                {
                    "cell": "s3",
                    "passed": False,
                    "terminal_kind": "DEFECT",
                    "terminal_gate_id": gvd.TERMINAL_DEFECT,
                    "terminal_reason": "x",
                }
            )
            + "\n"
        )
    assert gvd.build(led, swp)["terminal_defects"]["status"] == "DEFECT"


def test_the_sweep_digest_reads_the_stamp_and_never_folds_not_run_into_rejections(
    tmp_path: Path,
) -> None:
    swp = tmp_path / "sweep.json"
    swp.write_text(
        json.dumps(
            {
                "verdicts": [
                    {
                        "cell": "d",
                        "passed": None,
                        "stages": {},
                        "downstream_status": "NOT_RUN_BUILD_BUDGET_DEFERRED",
                        "why": "budget",
                    },
                    {
                        "cell": "o",
                        "passed": False,
                        "unmeasured": True,
                        "unknown_reason": "too_rare",
                        "stages": {"observations": {"passed": False}},
                    },
                    {"cell": "x", "passed": False, "stages": {}},  # names nothing: a DEFECT
                ]
            }
        ),
        "utf-8",
    )
    S = gvd.digest_sweep(swp)
    assert S["by_terminal_kind"] == {"NOT_RUN": 1, "UNMEASURED": 1, "DEFECT": 1}
    assert S["not_run_by_status"] == {"NOT_RUN_BUILD_BUDGET_DEFERRED": 1}
    assert S["unmeasured_by_reason"] == {"too_rare": 1}
    assert S["rejections_by_terminal_gate_id"] == {}
    assert S["terminal_defects"]["n"] == 1


def test_the_vocabulary_is_the_judges() -> None:
    """The kinds and the defect name are the sealed judge's own, once the stamp has landed."""
    import re

    src = (DESK / "scripts" / "external_gauntlet.py").read_text("utf-8")
    kinds = re.search(r"^TERMINAL_KINDS = (\(.*?\))$", src, re.M)
    defect = re.search(r'^TERMINAL_DEFECT = "(.*?)"$', src, re.M)
    if kinds is None or defect is None:
        import pytest

        pytest.skip("the sealed terminal-stamp patch is not applied on this tree")
    import ast

    assert tuple(ast.literal_eval(kinds.group(1))) == gvd.TERMINAL_KINDS
    assert defect.group(1) == gvd.TERMINAL_DEFECT
