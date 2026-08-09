"""THE STAGE THAT MADE `PORTFOLIO_CONTRIBUTING: null` PERMANENT.

Every sweep reported `INDEPENDENT MECHANISM 2 | PORTFOLIO-CONTRIBUTING unmeasured`. The null read
as "the harness builds no portfolio", which was true and not the whole truth: the sweep computed
each survivor's return series for clustering and DISCARDED it, so nothing downstream could have
measured contribution even if it had tried. Unmeasured and unmeasurable look identical in a report.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import scripts.run_portfolio_admission as PA


def _pnl(tmp_path: Path, **series) -> Path:
    p = tmp_path / "pnl.npz"
    np.savez_compressed(p, **series)
    return p


def test_AN_ABSENT_SIDECAR_IS_BLOCKED_AND_NAMES_THE_CAUSE(tmp_path, monkeypatch, capsys) -> None:
    monkeypatch.setattr(sys, "argv", ["run_portfolio_admission.py",
                                      "--pnl", str(tmp_path / "nope.npz"),
                                      "--out", str(tmp_path / "o.json")])
    assert PA.main() == 0
    out = capsys.readouterr().out
    assert "BLOCKED" in out
    assert "permanently null" in out


def test_AN_ABSENT_COHORT_IS_AN_EMPTY_BOOK_NOT_AN_ERROR(tmp_path) -> None:
    """Empty is the desk's ACTUAL state and must produce a stated weak verdict rather than a
    crash or a silent skip -- a skip is how the count stayed null."""
    mat, names = PA.load_incumbents(tmp_path / "absent.npz")
    assert mat.size == 0 and names == []


def test_THE_EMPTY_BOOK_VERDICT_REFUSES_TO_CLAIM_INCREMENTAL_VALUE(
        tmp_path, monkeypatch, capsys) -> None:
    """With no incumbents there is nothing to be incremental TO, so this answers a strictly easier
    question and must never be banked as if it had answered the hard one."""
    rng = np.random.default_rng(3)
    pnl = _pnl(tmp_path, m1=rng.normal(2.0, 5.0, 400))
    out = tmp_path / "o.json"
    monkeypatch.setattr(sys, "argv", ["run_portfolio_admission.py", "--pnl", str(pnl),
                                      "--incumbents", str(tmp_path / "none.npz"),
                                      "--out", str(out)])
    PA.main()
    rep = json.loads(out.read_text())
    assert rep["empty_book"] is True
    assert "EMPTY BOOK" in rep["verdict"]
    assert "NOT evidence of incremental value" in rep["rows"][0]["why"]
    printed = capsys.readouterr().out
    assert "weak result by construction" in printed


def test_THE_COUNT_IS_EMITTED_SO_THE_FIELD_CAN_STOP_BEING_NULL(tmp_path, monkeypatch) -> None:
    rng = np.random.default_rng(11)
    pnl = _pnl(tmp_path, up=rng.normal(3.0, 4.0, 500), down=rng.normal(-3.0, 4.0, 500))
    out = tmp_path / "o.json"
    monkeypatch.setattr(sys, "argv", ["run_portfolio_admission.py", "--pnl", str(pnl),
                                      "--incumbents", str(tmp_path / "none.npz"),
                                      "--out", str(out)])
    PA.main()
    rep = json.loads(out.read_text())
    assert rep["PORTFOLIO_CONTRIBUTING"] == 1
    assert rep["survivors_tested"] == 2


def test_A_REAL_COHORT_IS_JUDGED_ON_INCREMENTAL_VALUE(tmp_path, monkeypatch) -> None:
    """A DISTINCT mechanism is not an ADDITIVE one: independence is measured against the other
    survivors, admission against what the desk already holds."""
    rng = np.random.default_rng(5)
    base = rng.normal(1.0, 6.0, 800)
    pnl = _pnl(tmp_path, clone=base.copy())
    inc = tmp_path / "inc.npz"
    np.savez_compressed(inc, sleeve=base)
    out = tmp_path / "o.json"
    monkeypatch.setattr(sys, "argv", ["run_portfolio_admission.py", "--pnl", str(pnl),
                                      "--incumbents", str(inc), "--out", str(out)])
    PA.main()
    rep = json.loads(out.read_text())
    assert rep["empty_book"] is False
    assert rep["incumbents"] == ["sleeve"]
    assert rep["rows"][0]["admitted"] is False, "a perfect clone of the book cannot be additive"


def test_IT_PROMOTES_NOTHING() -> None:
    src = Path("scripts/run_portfolio_admission.py").read_text("utf-8").lower()
    for token in ("place_order", "place_market", "size_position", "api_key"):
        assert token not in src
    assert "promotes nothing, sizes nothing, places nothing" in src


def test_THE_SWEEP_ACTUALLY_EMITS_THE_SIDECAR() -> None:
    """Without this line the whole stage is unreachable, which was the original defect."""
    sweep = Path("scripts/run_full_sweep.py").read_text("utf-8")
    assert "full_sweep_survivor_pnl.npz" in sweep
    assert "savez_compressed" in sweep


def test_THE_CYCLE_RUNS_IT() -> None:
    """A completed sweep is a TRIGGER, not an endpoint -- survivor forwarding runs in the same
    cycle that produced the survivors."""
    cyc = Path("ops/run_research_cycle.sh").read_text("utf-8")
    assert "run_portfolio_admission.py" in cyc
    assert "run_intelligence_cycle.py" in cyc and "run_max_push.py" in cyc


def test_NAN_ROWS_ARE_MISSING_EVIDENCE_NOT_A_ZERO_SHARPE(
        tmp_path, monkeypatch) -> None:
    """The live sidecar is sparse by construction. np.mean over it is NaN, and the old code
    converted that to a false rejection with printed Sharpe +0.000 for every real candidate."""
    pnl = _pnl(
        tmp_path,
        edge=np.array([np.nan, 0.01, np.nan, 0.02, -0.001, np.nan]),
        __timestamp_ns=np.arange(6),
        __symbol=np.array(["", "BTC", "", "ETH", "BTC", ""]),
    )
    out = tmp_path / "o.json"
    monkeypatch.setattr(sys, "argv", [
        "run_portfolio_admission.py", "--pnl", str(pnl),
        "--incumbents", str(tmp_path / "none.npz"), "--out", str(out),
    ])
    PA.main()
    rep = json.loads(out.read_text())
    assert rep["survivors_tested"] == 1, "provenance arrays are not candidate streams"
    assert rep["PORTFOLIO_CONTRIBUTING"] == 1
    assert rep["rows"][0]["finite_observations"] == 3
    assert rep["rows"][0]["missing_fraction"] == 0.5
    assert "+0.000" not in rep["rows"][0]["why"]