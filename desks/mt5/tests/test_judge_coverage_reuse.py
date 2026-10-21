"""The hourly leg REUSES the coverage table merge_hypotheses published this cycle, and fails
closed -- exit 4, a named verdict, the table untouched -- whenever that table is not this cycle's.

Contingent change (b) of patches/judge_coverage_fast: the leg's own build + write was a second
full computation of the table `catch_up_intake` -> merge_hypotheses -> order_docket already
wrote in the same cycle. Nothing here may ever make an old table read as new.
"""
from __future__ import annotations

import json
import os
import sys
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

START = datetime(2026, 10, 20, 20, 0, 3, 517000, tzinfo=UTC)   # the cycle's own stamp
NOW = START + timedelta(minutes=9)


@pytest.fixture
def desk(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> dict[str, Path]:
    p = {"report": tmp_path / "reports" / "JUDGE_COVERAGE.json",
         "ratchet": tmp_path / "judge_backlog_ratchet.json",
         "merge": tmp_path / "hypotheses" / "merge_report.json",
         "docket": tmp_path / "hypotheses" / "external_survivors.json",
         "reuse": tmp_path / "reports" / "JUDGE_COVERAGE_REUSE.json"}
    for f in p.values():
        f.parent.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(jc, "REPORT", p["report"])
    monkeypatch.setattr(jc, "RATCHET", p["ratchet"])
    monkeypatch.setattr(jc, "MERGE_REPORT", p["merge"])
    monkeypatch.setattr(jc, "DOCKET", p["docket"])
    monkeypatch.setattr(jc, "REUSE_REPORT", p["reuse"])
    monkeypatch.setattr(jc, "UNRUNNABLE_BANK", tmp_path / "unrunnable_specs.json")
    monkeypatch.setattr(jc, "CONVERSION_HANDOFF", tmp_path / "conversion_handoff.json")
    monkeypatch.setattr(jc, "GATE_LEDGER", tmp_path / "gate.jsonl")
    monkeypatch.setattr(jc, "GATES_REPORT", tmp_path / "gates.json")
    monkeypatch.setattr(jc, "STUDY_BANK", tmp_path / "study_bank.json")
    monkeypatch.setattr(dk, "REPORT", tmp_path / "reports" / "DOCKET_KEFF_ORDER.json")
    monkeypatch.setattr(research_priors, "STATE_DIR", tmp_path / "research_priors")
    monkeypatch.setenv("QUANT_PIPELINE_STARTED_AT", START.isoformat())
    return p


def _merge_cycle(p: dict[str, Path], *, at: datetime = START + timedelta(minutes=2),
                 cycle: datetime = START, ship: bool = True) -> None:
    """What a merge of `cycle` leaves: the table and ratchet, then the docket, then its report."""
    stamp = at.isoformat(timespec="seconds")
    p["report"].write_text(json.dumps({"at": stamp, "families": {"alpha": {"unjudged": 3}},
                                       "variant_demotion": {"slots_freed": 0}}), "utf-8")
    p["ratchet"].write_text(json.dumps({"at": stamp, "families": {}}), "utf-8")
    t = p["report"].stat().st_mtime
    os.utime(p["ratchet"], (t, t))
    if ship:
        p["docket"].write_text("[]", "utf-8")
        p["merge"].write_text(json.dumps({
            "merged_at": (at - timedelta(seconds=40)).isoformat(timespec="seconds"),
            "pipeline_started_at": cycle.isoformat(timespec="seconds")}), "utf-8")
        for f in (p["docket"], p["merge"]):
            os.utime(f, (t + 5, t + 5))


def _bytes(p: dict[str, Path]) -> dict[str, bytes | None]:
    return {k: (p[k].read_bytes() if p[k].exists() else None) for k in ("report", "ratchet")}


def test_this_cycles_merge_table_is_reused_and_never_rewritten(desk: dict[str, Path]) -> None:
    _merge_cycle(desk)
    before = _bytes(desk)
    fresh, v = jc.reuse_fresh(now=NOW)
    assert fresh and v["verdict"] == "REUSED" and "why" not in v
    assert v["report_at"] == (START + timedelta(minutes=2)).isoformat(timespec="seconds")
    assert _bytes(desk) == before, "reuse publishes nothing: the table keeps its own `at`"
    assert json.loads(desk["reuse"].read_text("utf-8"))["verdict"] == "REUSED"


@pytest.mark.parametrize("case, expect", [
    ("missing", "missing or unreadable"),
    ("last_cycle", "predates this cycle"),
    ("other_cycle_merge", "is not this cycle's"),
    ("ratchet_behind", "ratchet does not carry"),
    ("not_shipped", "did not ship"),
    ("hand_run", "not written by order_docket"),
    ("future", "in the future"),
    ("garbage_at", "not a timestamp"),
    ("no_cycle", "no cycle start"),
])
def test_anything_but_this_cycles_table_fails_closed(desk: dict[str, Path],
                                                     monkeypatch: pytest.MonkeyPatch,
                                                     case: str, expect: str) -> None:
    if case == "missing":
        _merge_cycle(desk)
        desk["report"].unlink()
    elif case == "last_cycle":
        # The previous cycle's end-of-hour merge: complete and consistent, and an hour old.
        prev = START - timedelta(hours=1)
        _merge_cycle(desk, at=START - timedelta(minutes=5), cycle=prev)
    elif case == "other_cycle_merge":
        _merge_cycle(desk, cycle=START - timedelta(hours=1))
    elif case == "ratchet_behind":
        _merge_cycle(desk)
        desk["ratchet"].write_text(json.dumps({"at": START.isoformat(timespec="seconds")}),
                                   "utf-8")
    elif case == "not_shipped":
        # The merge died after order_docket wrote the table and before the docket shipped:
        # the docket and merge report on disk are the previous cycle's, older than the table.
        desk["docket"].write_text("[]", "utf-8")
        desk["merge"].write_text(json.dumps({"merged_at": START.isoformat(),
                                             "pipeline_started_at": START.isoformat()}), "utf-8")
        _merge_cycle(desk, ship=False)
        t = desk["report"].stat().st_mtime
        for f in (desk["docket"], desk["merge"]):
            os.utime(f, (t - 60, t - 60))
    elif case == "hand_run":
        _merge_cycle(desk)
        doc = json.loads(desk["report"].read_text("utf-8"))
        doc.pop("variant_demotion")
        desk["report"].write_text(json.dumps(doc), "utf-8")
        t = desk["report"].stat().st_mtime
        for f in (desk["docket"], desk["merge"]):
            os.utime(f, (t + 5, t + 5))
    elif case == "future":
        _merge_cycle(desk, at=NOW + timedelta(hours=3))
    elif case == "garbage_at":
        _merge_cycle(desk)
        doc = json.loads(desk["report"].read_text("utf-8"))
        doc["at"] = "garbage"
        desk["report"].write_text(json.dumps(doc), "utf-8")
        t = desk["report"].stat().st_mtime
        for f in (desk["docket"], desk["merge"]):
            os.utime(f, (t + 5, t + 5))
    elif case == "no_cycle":
        _merge_cycle(desk)
        monkeypatch.delenv("QUANT_PIPELINE_STARTED_AT")
    before = _bytes(desk)
    fresh, v = jc.reuse_fresh(now=NOW)
    assert not fresh and v["verdict"] == "STALE" and v["fresh"] is False
    assert any(expect in w for w in v["why"]), v["why"]
    assert _bytes(desk) == before, "a stale table is left exactly as it was, never restamped"
    assert json.loads(desk["reuse"].read_text("utf-8"))["verdict"] == "STALE"


def test_the_leg_exits_four_on_stale_and_zero_on_fresh(desk: dict[str, Path],
                                                       capsys: pytest.CaptureFixture[str]) -> None:
    _merge_cycle(desk, at=START - timedelta(minutes=5), cycle=START - timedelta(hours=1))
    before = _bytes(desk)
    assert jc.main(["--once", "--reuse-fresh", "--budget-s", "120"]) == jc.REUSE_STALE_EXIT
    assert "STALE" in capsys.readouterr().out
    assert _bytes(desk) == before
    _merge_cycle(desk, at=datetime.now(tz=UTC) - timedelta(seconds=30), cycle=START)
    # The real clock is past START, so a table stamped 30 s ago is inside this cycle.
    assert jc.main(["--once", "--reuse-fresh"]) == 0
    assert "REUSED" in capsys.readouterr().out


def test_a_real_order_docket_write_is_what_reuse_accepts(desk: dict[str, Path],
                                                         monkeypatch: pytest.MonkeyPatch) -> None:
    """End to end on the real writer: what order_docket(publish=True) leaves, followed by the
    merge shipping its docket and report, passes; the same table one cycle later does not."""
    started = datetime.now(tz=UTC).replace(microsecond=0) - timedelta(seconds=5)
    monkeypatch.setenv("QUANT_PIPELINE_STARTED_AT", started.isoformat())
    seen = (started - timedelta(hours=5)).isoformat()
    rows = [{"symbol": f"S{i}", "family": ("alpha", "beta")[i % 2], "params": {"rr": i},
             "first_seen": seen} for i in range(40)]
    _ordered, doc = jc.order_docket(rows, publish=True)
    assert doc.get("families") and "variant_demotion" in doc
    desk["docket"].write_text("[]", "utf-8")
    desk["merge"].write_text(json.dumps({"merged_at": started.isoformat(),
                                         "pipeline_started_at": started.isoformat()}), "utf-8")
    t = desk["report"].stat().st_mtime
    for f in (desk["docket"], desk["merge"]):
        os.utime(f, (t + 1, t + 1))
    fresh, v = jc.reuse_fresh()
    assert fresh, v.get("why")
    later = started + timedelta(hours=1)
    fresh2, v2 = jc.reuse_fresh(started_at=later, now=later + timedelta(minutes=9))
    assert not fresh2 and any("predates this cycle" in w for w in v2["why"])


def test_the_hourly_leg_reuses_and_keeps_its_cap() -> None:
    src = (DESK / "research" / "hourly_cycle.py").read_text("utf-8")
    assert '"--once", "--reuse-fresh",' in src
    sys.path.insert(0, str(DESK / "research"))
    import hourly_cycle as hc
    assert hc.LEG_BUDGET_SEC["judge_coverage"] == 300, "the cap is not this change's to move"


def test_a_stale_reuse_is_a_named_failure_in_the_cycle() -> None:
    sys.path.insert(0, str(DESK / "research"))
    import hourly_cycle as hc
    assert hc._exit_outcome("judge_coverage", jc.REUSE_STALE_EXIT) == "exit_code=4:REUSE_STALE"
    assert jc.REUSE_STALE_EXIT not in hc.VERDICT_EXITS.get("judge_coverage", ())
