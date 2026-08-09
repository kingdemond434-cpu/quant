"""BEHAVIORAL tests for the wealth report — the economic scoreboard and the daily board question.

THE PROPERTY THIS FILE PROTECTS ABOVE ALL OTHERS. A scoreboard with no inputs must say UNMEASURED,
by name, and must name the artifact whose absence caused it. A version that filled the gaps with
plausible defaults would be the single most dangerous file in the repository: it would look
exactly like a working desk and would be describing a simulation of one.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import scripts.run_wealth_report as W  # noqa: E402


def _write(monkeypatch, tmp_path: Path, **files: object) -> None:
    """Point the report's inputs at a tmp dir and write the ones this test cares about."""
    for attr, name in (("NAV_PATH", "nav_path.json"), ("ENGINE_PNL", "engine_pnl.json"),
                       ("CONVERSION", "conversion_records.json"),
                       ("DECISIONS", "decision_ledger.jsonl"),
                       ("BENCHMARK", "external_benchmark_claims.json"),
                       ("MODELS", "model_records.json"),
                       ("CONDITIONAL", "state_conditional_candidates.json"),
                       ("LADDER", "live_ladder.json")):
        monkeypatch.setattr(W, attr, tmp_path / name)
    for key, value in files.items():
        p = tmp_path / key
        p.write_text(value if isinstance(value, str) else json.dumps(value), "utf-8")


# ------------------------------------------------------------------ absence is not a verdict

def test_with_no_inputs_every_section_reports_unmeasured_by_name(monkeypatch, tmp_path) -> None:
    _write(monkeypatch, tmp_path)
    rep = W.build()
    unmeasured = rep["unmeasured_sections"]
    assert isinstance(unmeasured, list)
    assert len(unmeasured) >= 6, f"a section quietly produced a verdict with no input: {rep}"
    for name in unmeasured:
        s = rep["sections"][name]           # type: ignore[index]
        assert "UNMEASURED" in str(s["headline"])
        assert s["missing_artifact"], f"{name} reported UNMEASURED without naming its input"


def test_the_board_question_is_answered_from_artifacts_not_opinion(monkeypatch, tmp_path) -> None:
    _write(monkeypatch, tmp_path)
    rep = W.build()
    assert rep["ANSWER"] == "NO REALISED P&L EXISTS TO RETAIN"
    assert "first real fill" in str(rep["why"])


def test_no_section_invents_a_number_when_its_input_is_malformed(monkeypatch, tmp_path) -> None:
    _write(monkeypatch, tmp_path, **{"nav_path.json": {"nav": "not a list"},
                                     "engine_pnl.json": {"engines": [{"engine": "NONSENSE"}]}})
    rep = W.build()
    # A NONSENSE engine is skipped rather than bucketed, so the section has zero rows.
    assert "UNMEASURED" in str(rep["sections"]["return_engines"]["headline"])  # type: ignore[index]


# --------------------------------------------------------- the answer changes with the evidence

def test_process_bound_survivors_outrank_everything_below_them(monkeypatch, tmp_path) -> None:
    """Once a euro exists, the next-highest constraint is alpha not reaching live."""
    _write(monkeypatch, tmp_path,
           **{"nav_path.json": {"nav": [1000.0 * 1.001 ** i for i in range(40)],
                                "elapsed_days": 200.0, "deployed_capital": 500.0,
                                "total_capital": 1000.0, "real_fills": 50,
                                "realised_pnl": 40.0},
              "engine_pnl.json": {"engines": [{"engine": "INDEPENDENT_ALPHA", "pnl": 40.0}],
                                  "gross_pnl": 40.0},
              "conversion_records.json": {"records": [
                  {"candidate_id": "X1", "stage_days": {"discovered": 0.0, "survivor": 1.0},
                   "effective_n": 400, "required_effective_n": 60, "age_days": 20.0,
                   "half_life_days": 10.0, "expected_bps_per_day": 3.0}]}})
    rep = W.build()
    assert rep["ANSWER"] == "ALPHA IS NOT REACHING LIVE"
    assert "conversion deficit" in str(rep["why"])


def test_hidden_beta_is_escalated_above_a_thin_pipeline(monkeypatch, tmp_path) -> None:
    _write(monkeypatch, tmp_path,
           **{"nav_path.json": {"nav": [1000.0 * 1.001 ** i for i in range(40)],
                                "elapsed_days": 200.0, "deployed_capital": 500.0,
                                "total_capital": 1000.0, "real_fills": 50, "realised_pnl": 40.0},
              "engine_pnl.json": {"engines": [
                  {"engine": "INDEPENDENT_ALPHA", "pnl": 40.0, "r2_market": 0.88,
                   "market_beta": 0.95}], "gross_pnl": 40.0},
              "conversion_records.json": {"records": [
                  {"candidate_id": "X1", "stage_days": {"discovered": 0.0, "survivor": 1.0},
                   "effective_n": 5, "required_effective_n": 60, "age_days": 3.0}]}})
    rep = W.build()
    assert rep["ANSWER"] == "BETA IS BEING REPORTED AS ALPHA"


def test_a_round_trip_is_escalated_over_a_benchmark_gap(monkeypatch, tmp_path) -> None:
    up = [1000.0 * 1.06 ** i for i in range(25)]
    down = [up[-1] * 0.94 ** i for i in range(1, 25)]
    _write(monkeypatch, tmp_path,
           **{"nav_path.json": {"nav": up + down, "elapsed_days": 200.0,
                                "deployed_capital": 500.0, "total_capital": 1000.0,
                                "real_fills": 50, "realised_pnl": 40.0},
              "engine_pnl.json": {"engines": [{"engine": "INDEPENDENT_ALPHA", "pnl": 40.0}],
                                  "gross_pnl": 40.0},
              "conversion_records.json": {"records": [
                  {"candidate_id": "X1", "stage_days": {"discovered": 0.0, "survivor": 1.0},
                   "effective_n": 5, "required_effective_n": 60, "age_days": 3.0}]}})
    rep = W.build()
    assert rep["ANSWER"] == "WEALTH IS ROUND-TRIPPING"
    assert "retention" in str(rep["why"])


def test_conversion_records_fall_back_to_the_live_ladder(monkeypatch, tmp_path) -> None:
    """A capability wired only when its dedicated artifact exists is a capability wired late."""
    _write(monkeypatch, tmp_path,
           **{"live_ladder.json": {"rows": [
               {"alpha": "L1", "effective_n": 500, "required_effective_n": 60, "age_days": 14.0}]}})
    sec = W.velocity_section()
    assert sec.get("measured") is not False
    assert sec["process_bound"] == 1


# ----------------------------------------------------------------------------- the script runs

def test_the_script_runs_and_writes_its_artifact(tmp_path) -> None:
    out = tmp_path / "wealth_report.json"
    r = subprocess.run([sys.executable, str(ROOT / "scripts/run_wealth_report.py"),
                        "--out", str(out)], cwd=ROOT, capture_output=True, text=True,
                       timeout=300, check=False)
    assert r.returncode == 0, r.stderr
    assert out.exists()
    doc = json.loads(out.read_text("utf-8"))
    assert doc["DAILY_BOARD_QUESTION"].startswith("What is currently preventing")
    assert "sections" in doc
    assert "BOARD QUESTION" in r.stdout


def test_the_report_promotes_nothing_and_sizes_nothing() -> None:
    """The scoreboard reads artifacts. If it ever gains an allocation path, this fails."""
    src = (ROOT / "scripts/run_wealth_report.py").read_text("utf-8")
    tree = __import__("ast").parse(src)
    called = {n.func.attr for n in __import__("ast").walk(tree)
              if isinstance(n, __import__("ast").Call)
              and isinstance(n.func, __import__("ast").Attribute)}
    for banned in ("allocate", "promote", "place_order", "submit", "advance"):
        assert banned not in called, f"the wealth report called {banned}() -- it may only measure"


def test_architecture_counts_are_absent_from_the_scoreboard() -> None:
    """§59: architecture counts belong below economic outcomes, and this report has none of them."""
    rep = W.build()
    for banned in ("modules", "capabilities", "lines_of_code", "agents", "n_tests"):
        assert banned not in rep, (
            f"an architecture count appeared on the economic scoreboard: {banned}")


@pytest.mark.parametrize("section", ["wealth_retention", "return_engines", "conversion",
                                     "decisions", "external_benchmark", "payoff_selection",
                                     "state_conditional"])
def test_every_declared_section_is_present(section, monkeypatch, tmp_path) -> None:
    _write(monkeypatch, tmp_path)
    assert section in W.build()["sections"]        # type: ignore[operator]
