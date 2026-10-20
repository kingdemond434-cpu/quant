"""Every verdict row names the gate that stopped it, and why; an unnamed one is a DEFECT.

    python -m pytest desks/mt5/tests/test_terminal_gate_stamp.py -q

GATE_VERDICT_DIGEST 2026-10-20 19:40Z: 587,075 of 963,604 ledger rejections and 885,556 of the
newest sweep's 900,500 verdicts read terminal gate UNKNOWN, because `terminal_gate` is written
only when the gates RULED. `patches/judge_funnel_shards/A_terminal_stamp.patch` adds
`terminal_stamp` to the sealed judge: `terminal_kind`, `terminal_gate_id` and `terminal_reason`
on every row, beside a `terminal_gate` whose meaning (UNKNOWN = unmeasured, never a rejection)
does not change. These tests SKIP until that sealed patch is applied.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

DESK = Path(__file__).resolve().parent.parent
for p in (DESK, DESK / "research", DESK / "scripts", DESK.parent.parent):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))


@pytest.fixture(scope="module")
def eg():
    import external_gauntlet
    if not hasattr(external_gauntlet, "terminal_stamp"):
        pytest.skip("A_terminal_stamp.patch is not applied to the sealed judge")
    return external_gauntlet


ROWS = {
    "passed": ({"cell": "p", "passed": True, "terminal_gate": "PASSED", "stages": {}},
               ("PASSED", "PASSED")),
    "deferred": ({"cell": "d", "passed": None, "stages": {},
                  "downstream_status": "NOT_RUN_BUILD_BUDGET_DEFERRED", "why": "budget out"},
                 ("NOT_RUN", "NOT_RUN_BUILD_BUDGET_DEFERRED")),
    "unmeasured": ({"cell": "u", "passed": False, "unmeasured": True,
                    "unknown_reason": "lockbox_consumed_history",
                    "failed_gates": ["observations"],
                    "stages": {"observations": {"passed": False, "days": 12}}},
                   ("UNMEASURED", "observations")),
    "unmeasured_unnamed": ({"cell": "u2", "passed": False, "unmeasured": True, "stages": {}},
                           ("UNMEASURED", "observations")),
    "gate0": ({"cell": "g", "passed": False, "terminal_gate": "symbol_eligibility",
               "downstream_status": "NOT_RUN_UNTRADEABLE_SYMBOL",
               "stages": {"symbol_eligibility": {"passed": False, "message": "no parquet"}}},
              ("RULED", "symbol_eligibility")),
    "ruled": ({"cell": "r", "passed": False, "terminal_gate": "deflated_sharpe",
               "stages": {"economic_prior": {"passed": True},
                          "deflated_sharpe": {"passed": False, "dsr": 0.41, "sr0": 0.2},
                          "cpcv": {"passed": False}}},
              ("RULED", "deflated_sharpe")),
    "failed_stage_no_gate": ({"cell": "f", "passed": False,
                              "stages": {"cpcv": {"passed": True},
                                         "walk_forward": {"passed": False, "why": "unstable"}}},
                             ("RULED", "walk_forward")),
    "nothing": ({"cell": "x", "passed": False, "stages": {}}, ("DEFECT", None)),
    "null_without_status": ({"cell": "y", "passed": None, "stages": {}}, ("DEFECT", None)),
}


@pytest.mark.parametrize("name", sorted(ROWS))
def test_every_shape_is_named_and_never_empty(eg, name: str) -> None:
    row, (kind, gid) = ROWS[name]
    st = eg.terminal_stamp(dict(row))
    assert st["terminal_kind"] == kind
    assert st["terminal_gate_id"] == (gid or eg.TERMINAL_DEFECT)
    assert st["terminal_reason"] and len(st["terminal_reason"]) <= eg.TERMINAL_REASON_CHARS
    assert st["terminal_kind"] in eg.TERMINAL_KINDS


def test_the_reason_is_the_gates_own_words(eg) -> None:
    assert eg.terminal_stamp(ROWS["unmeasured"][0])["terminal_reason"] == \
        "lockbox_consumed_history"
    assert eg.terminal_stamp(ROWS["gate0"][0])["terminal_reason"] == "no parquet"
    assert eg.terminal_stamp(ROWS["ruled"][0])["terminal_reason"] == \
        "deflated_sharpe: dsr=0.41, sr0=0.2"
    assert eg.terminal_stamp(ROWS["failed_stage_no_gate"][0])["terminal_reason"] == "unstable"
    assert eg.terminal_stamp(ROWS["deferred"][0])["terminal_reason"] == "budget out"


def test_terminal_gate_keeps_its_meaning(eg) -> None:
    """The stamp rides BESIDE `terminal_gate`: UNKNOWN stays unmeasured for every reader."""
    rows = [dict(r) for r, _ in ROWS.values()]
    before = [r.get("terminal_gate") for r in rows]
    out = eg.stamp_terminal([*rows, "not-a-row"])
    assert [r.get("terminal_gate") for r in rows] == before
    assert out["n"] == 2 and out["sample"] == ["x", "y"]


def test_a_stamp_is_deterministic(eg) -> None:
    for row, _ in ROWS.values():
        assert eg.terminal_stamp(dict(row)) == eg.terminal_stamp(dict(row))


def test_the_ledger_carries_the_stamp_and_its_key_is_unchanged(eg, tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(eg, "GATE_LEDGER", tmp_path / "ledger.jsonl")
    monkeypatch.setattr(eg, "GATE_INDEX", tmp_path / "index.json")
    rows = [dict(r) for r, _ in ROWS.values()]
    got = eg._append_gate_ledger(rows)
    assert got["appended"] == len(rows) and got["terminal_defects"] == 2
    written = [json.loads(x) for x in (tmp_path / "ledger.jsonl").read_text().splitlines()]
    for w in written:
        assert w["terminal_kind"] in eg.TERMINAL_KINDS and w["terminal_gate_id"]
        assert w["terminal_reason"]
    by = {w["cell"]: w for w in written}
    assert by["u"]["terminal_gate"] == "UNKNOWN" and by["u"]["terminal_gate_id"] == "observations"
    # The index key is gate|passed as before: the same verdicts, now stamped, append nothing.
    eg.stamp_terminal(rows)
    assert eg._append_gate_ledger(rows)["appended"] == 0
