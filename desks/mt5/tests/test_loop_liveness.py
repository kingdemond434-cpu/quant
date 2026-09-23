"""THE LOOP LIVENESS PROVER, held to its own claims.

Every fixture is planted in `tmp_path`: a fake registry, a fake gate ledger, fake shadow states.
Nothing here reads or writes a tracked file, and nothing depends on what this box's clocks did
last night -- a liveness prover whose tests pass only on a healthy desk proves nothing.
"""
from __future__ import annotations

import json
import sqlite3
import sys
from collections.abc import Sequence
from pathlib import Path
from typing import Any

import pytest

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from desks.mt5.research import loop_liveness as LL  # noqa: E402

NOW = 1_780_000_000.0


def iso(now: float, hours_ago: float) -> str:
    from datetime import UTC, datetime
    return datetime.fromtimestamp(now - hours_ago * 3600.0, tz=UTC).isoformat(timespec="seconds")


def plant_registry(root: Path, *, discoveries: list[float], candidates: list[float],
                   sources: Sequence[tuple[float, bool]] = ()) -> Path:
    """A minimal alpha_registry with the three tables the prover reads."""
    (root / "data").mkdir(parents=True, exist_ok=True)
    p = root / "data" / "alpha_registry.sqlite"
    conn = sqlite3.connect(p)
    conn.executescript(
        "CREATE TABLE sources (source_id TEXT, first_seen TEXT, last_crawled TEXT);"
        "CREATE TABLE discoveries (discovery_id TEXT, created_at TEXT);"
        "CREATE TABLE research_candidates (id TEXT, created_at TEXT, status TEXT,"
        " discovery_id TEXT, judged_at TEXT);")
    for i, (h, crawled) in enumerate(sources):
        conn.execute("INSERT INTO sources VALUES (?,?,?)",
                     (f"s{i}", iso(NOW, h), iso(NOW, h) if crawled else None))
    for i, h in enumerate(discoveries):
        conn.execute("INSERT INTO discoveries VALUES (?,?)", (f"d{i}", iso(NOW, h)))
    for i, h in enumerate(candidates):
        conn.execute("INSERT INTO research_candidates VALUES (?,?,?,?,?)",
                     (f"c{i}", iso(NOW, h), "queued", f"d{i}", None))
    conn.commit()
    conn.close()
    return p


# ------------------------------------------------------------------------------- the verdict
def _stage(name: str = "s", host: str = "any") -> LL.Stage:
    return LL.Stage(name, "an_organ", "in", "out", lambda _r, _n: LL.Measure(), host=host)


def test_alive_when_output_is_inside_the_window() -> None:
    m = LL.Measure(True, 4, 40, 600.0, 0, None, "src")
    verdict, why = LL.judge(_stage(), m, here="build_box")
    assert verdict == LL.ALIVE
    assert "last hour" in why


def test_stalled_when_input_waits_and_no_output() -> None:
    """THE CENTRAL CLAIM: input waiting + no output inside the window is a DEFECT."""
    m = LL.Measure(True, 0, 0, 40 * 3600.0, 4_082, 143 * 3600.0, "src")
    verdict, why = LL.judge(_stage(), m, here="build_box")
    assert verdict == LL.STALLED
    assert "4082 input row(s) waiting on `an_organ`" in why
    assert "DEFECT" in why


def test_stalled_when_input_waits_and_output_never_happened() -> None:
    m = LL.Measure(True, 0, 0, None, 7, None, "src")
    verdict, why = LL.judge(_stage(), m, here="build_box")
    assert verdict == LL.STALLED
    assert "no output ever" in why


def test_slow_is_not_stalled_when_nothing_is_waiting() -> None:
    """Idle for want of input is not a stall: the defect is upstream and named there."""
    m = LL.Measure(True, 0, 0, 40 * 3600.0, 0, None, "src")
    verdict, _ = LL.judge(_stage(), m, here="build_box")
    assert verdict == LL.SLOW


def test_absent_source_is_unmeasured_not_zero() -> None:
    m = LL.Measure(source_present=False, source="reports/NOPE.json (absent)")
    verdict, why = LL.judge(_stage(), m, here="build_box")
    assert verdict == LL.UNMEASURED
    assert "not zero" in why


def test_box_only_stage_is_unmeasured_off_the_box_never_stalled() -> None:
    """A build box's idle forward clock is not a stall, and must never be published as one."""
    m = LL.Measure(True, 0, 0, 200 * 3600.0, 651, None, "src")
    verdict, why = LL.judge(_stage(host="trading_box"), m, here="box_clocks_off")
    assert verdict == LL.UNMEASURED
    assert "not a stall" in why
    # ...and the SAME numbers on the real box are the defect they describe.
    verdict2, _ = LL.judge(_stage(host="trading_box"), m, here="trading_box")
    assert verdict2 == LL.STALLED


def test_every_stage_declares_an_organ_and_the_ten_arrows_are_present() -> None:
    names = [s.name for s in LL.STAGES]
    assert names == ["sources_ingested", "discoveries_mined", "conversion",
                     "candidates_compiled", "ten_gates_judged", "survivors_certified",
                     "clocks_enrolled", "clocks_accruing", "promoter_reading",
                     "allocator_sizing"]
    assert all(s.organ for s in LL.STAGES)
    assert all(s.stall_window_s == s.cadence_s * LL.STALL_CADENCES for s in LL.STAGES)


# ----------------------------------------------------------------------------- the measures
def test_conversion_debt_is_measured_from_the_registry(tmp_path: Path) -> None:
    plant_registry(tmp_path, sources=[(1.0, True)], discoveries=[0.5, 0.6, 100.0],
                   candidates=[0.4])           # d0 converted; d1 and d2 are debt
    m = LL.m_conversion(tmp_path, NOW)
    assert m.source_present
    assert m.pending == 2
    assert m.detail["discoveries_converted"] == 1
    assert m.oldest_pending_age_s is not None and m.oldest_pending_age_s > 3600.0


def test_missing_registry_is_unmeasured_and_creates_nothing(tmp_path: Path) -> None:
    m = LL.m_discoveries(tmp_path, NOW)
    assert not m.source_present
    assert m.count_24h is None
    assert not (tmp_path / "data" / "alpha_registry.sqlite").exists()


def test_ten_gates_reads_the_sealed_judges_gate_names_and_verdict_rows(tmp_path: Path) -> None:
    from desks.mt5.research.gate_policy import GATES
    d = tmp_path / "desks" / "mt5" / "data" / "hypotheses"
    d.mkdir(parents=True)
    (d / "gate_verdict_ledger.jsonl").write_text(
        "\n".join(json.dumps({"at": iso(NOW, h), "cell": f"X{i}", "passed": h < 1.0,
                              "terminal_gate": "pbo"})
                  for i, h in enumerate([0.2, 0.5, 30.0])), encoding="utf-8")
    m = LL.m_gauntlet(tmp_path, NOW)
    assert m.source_present
    assert m.count_1h == 2
    assert m.count_24h == 2
    assert m.detail["n_gates"] == 10
    assert tuple(m.detail["gates"]) == GATES
    assert m.detail["ten_gate_passes_24h"] == 2


def test_gauntlet_with_no_ledger_is_unmeasured_but_still_reports_the_gate_names(
        tmp_path: Path) -> None:
    m = LL.m_gauntlet(tmp_path, NOW)
    assert not m.source_present
    assert m.detail["n_gates"] == 10


def test_clocks_accruing_counts_silent_clocks(tmp_path: Path) -> None:
    d = tmp_path / "desks" / "mt5" / "reports" / "shadow"
    d.mkdir(parents=True)
    (d / "shadow_state.json").write_text(json.dumps({
        "XAUUSD.asia": {"n": 40, "status": "live", "last_attempt_at": iso(NOW, 0.4)},
        "EURUSD.asia": {"n": 3, "status": "live", "last_attempt_at": iso(NOW, 300.0)},
        "GBPJPY.asia": {"n": 9, "status": "retired", "last_attempt_at": iso(NOW, 900.0)},
    }), encoding="utf-8")
    m = LL.m_accrual(tmp_path, NOW)
    assert m.detail["active_clocks"] == 2
    assert m.detail["clocks_silent_24h"] == 1
    assert m.detail["forward_observations"] == 52
    assert m.count_1h == 1


# --------------------------------------------------------------------------------- the host
def test_host_reads_disabled_tasks_as_clocks_off(tmp_path: Path) -> None:
    """MEASURED ON THE REAL BOX: the package is installed and every MT5 task is Disabled."""
    tasks = tmp_path / "Tasks"
    tasks.mkdir()
    for n in ("MT5-Gateway", "MT5-Hourly"):
        (tasks / n).write_text("<Task><Settings><Enabled>false</Enabled></Settings></Task>",
                               encoding="utf-16")
    assert LL._enabled_box_clocks(tasks) == 0
    (tasks / "MT5-Live").write_text("<Task><Settings><Enabled>true</Enabled></Settings></Task>",
                                    encoding="utf-16")
    assert LL._enabled_box_clocks(tasks) == 1


def test_host_with_no_task_directory_is_unmeasured_not_zero(tmp_path: Path) -> None:
    assert LL._enabled_box_clocks(tmp_path / "nope") is None


# ------------------------------------------------------------------------ build and publish
def test_build_publishes_every_stage_with_its_host_and_verdict(tmp_path: Path) -> None:
    plant_registry(tmp_path, sources=[(1.0, True)], discoveries=[0.2], candidates=[0.1])
    doc = LL.build(tmp_path, now=NOW, here="build_box", budget_s=60.0)
    assert len(doc["stages"]) == len(LL.STAGES)
    assert doc["host"] == "build_box"
    assert set(doc["stage_counts"]) == set(LL.VERDICTS)
    for s in doc["stages"]:
        assert s["verdict"] in LL.VERDICTS
        assert s["measured_on"] == "build_box"
        assert s["organ"]
        assert "organ_last_run" in s
    # box-only stages can never be STALLED off the box
    box_only = [s for s in doc["stages"] if s["host"] == "trading_box"]
    assert box_only and all(s["verdict"] == LL.UNMEASURED for s in box_only)


def test_build_respects_its_budget(tmp_path: Path) -> None:
    doc = LL.build(tmp_path, now=NOW, here="build_box", budget_s=-1.0)
    assert all(s["verdict"] == LL.UNMEASURED for s in doc["stages"])
    assert "budget" in doc["stages"][0]["why"]


def test_publish_writes_both_artifacts_and_the_doc_names_the_defect(tmp_path: Path) -> None:
    doc = LL.build(tmp_path, now=NOW, here="build_box", budget_s=60.0)
    doc["defects"] = [{"stage": "ten_gates_judged", "organ": "external_gauntlet",
                       "why": "4082 waiting -- DEFECT", "organ_last_run": {"at": "2026-09-16"}}]
    doc["first_stalled_stage"] = "ten_gates_judged"
    r, m = LL.publish(doc, report=tmp_path / "R.json", markdown=tmp_path / "R.md")
    assert json.loads(r.read_text(encoding="utf-8"))["host"] == "build_box"
    text = m.read_text(encoding="utf-8")
    assert "external_gauntlet" in text
    assert "ten_gates_judged" in text
    assert "DERIVED" in text


def test_timestamp_parser_never_returns_the_epoch_for_junk() -> None:
    junk: list[Any] = ["", None, "not a date", 0, False, [], {}]
    for j in junk:
        assert LL._parse(j) is None
    assert LL._parse("2026-09-16T15:07:09+00:00") is not None
    assert LL._parse("2026-09-08 01:00:00+00:00") is not None


@pytest.mark.parametrize("cli", [["--once", "--budget-s", "5"]])
def test_main_runs_and_returns_zero(tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
                                    cli: list[str]) -> None:
    monkeypatch.setattr(LL, "REPORT", tmp_path / "LOOP_LIVENESS.json")
    monkeypatch.setattr(LL, "DOC", tmp_path / "LOOP_LIVENESS.md")
    monkeypatch.setattr(LL, "ROOT", tmp_path)
    assert LL.main(cli) == 0
    assert (tmp_path / "LOOP_LIVENESS.json").exists()
    assert (tmp_path / "LOOP_LIVENESS.md").exists()


def test_the_leg_is_on_a_clock_and_in_a_layer() -> None:
    """UNWIRED OR IDLE IS A DEFECT (LAWS III.16): the organ is done only when it is scheduled."""
    from libs.research.layers import LEG_LAYER
    assert LEG_LAYER["loop_liveness"] == "meta"
    src = (ROOT / "desks" / "mt5" / "research" / "hourly_cycle.py").read_text(encoding="utf-8")
    assert '_costed("loop_liveness"' in src
    assert '"research/loop_liveness.py", "--once", "--budget-s", "240"' in src
    assert '"loop_liveness": llv' in src
    assert '"loop_liveness"' in src.split("LEG_BUDGET_SEC")[1][:40000]


def test_elapsed_and_rule_are_published(tmp_path: Path) -> None:
    doc = LL.build(tmp_path, now=NOW, here="build_box", budget_s=60.0)
    assert isinstance(doc["elapsed_s"], float)
    assert "STALLED" in doc["rule"]
    assert doc["sources"]["judge"].startswith("desks/mt5/scripts/external_gauntlet.py")
