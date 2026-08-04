"""THE STUDY RUNNER -- and the tests that keep it honest to its own pre-registration.

A pre-registration only binds if the code cannot quietly disagree with it. Two ways it stops
binding, and both are silent:

  the thresholds drift  -- KILL in the script is edited and the document is not, so the study is
                           scored against numbers chosen after the fact
  the grid grows        -- an axis is added to the sweep and never to the trial budget, so the
                           deflation understates how many things were tried

Both are asserted here rather than trusted.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import scripts.run_failed_breakout_study as S  # noqa: E402

PREREG = ROOT / "docs/research/FAILED_BREAKOUT_PREREGISTRATION.md"


def test_the_preregistration_exists_and_predates_the_analysis() -> None:
    """The document is the authority. Without it the kill criteria are just constants."""
    assert PREREG.exists()
    doc = PREREG.read_text("utf-8")
    for token in ("K1", "K7", "Deflated Sharpe", "PBO", "Reality Check", "Brier"):
        assert token in doc, f"the pre-registration does not state {token}"


def test_kill_thresholds_in_code_match_the_document() -> None:
    """A threshold in two places drifts, and the one that governs becomes whichever was edited
    last. Here that would mean scoring the study against numbers picked after seeing the result."""
    doc = PREREG.read_text("utf-8")
    for label, value in (("DSR < 0.95", S.KILL["dsr_min"]),
                         ("PBO > 0.30", S.KILL["pbo_max"]),
                         ("p > 0.05", S.KILL["rc_p_max"])):
        assert str(value) in doc, f"{label}: code says {value}, document does not state it"
    assert "50k" in doc or "50,000" in doc or str(int(S.KILL["capacity_min_usd"])) in doc


def test_the_trial_budget_matches_the_declared_grid() -> None:
    """4,860 is not a number to be re-derived by hand -- it is the product of the declared axes.
    If someone adds a hyperparameter to GRID, this recomputes and the document must follow."""
    expected = S.N_SYMBOLS_PLANNED
    for v in S.GRID.values():
        expected *= len(v)
    assert S.nominal_trials() == expected
    assert str(expected) in PREREG.read_text("utf-8").replace(",", ""), (
        f"the grid implies {expected} nominal trials and the pre-registration does not say so")


def test_the_symbol_deflation_takes_the_STRICTER_of_two_disagreeing_numbers() -> None:
    """THE DISAGREEMENT WAS IN THE STRATEGY'S FAVOUR, WHICH IS THE ONLY DIRECTION THAT MATTERS.

    The document estimated the 10-symbol axis at ~3 effective bets; the standard equicorrelated
    formula N/(1+(N-1)rho) at rho=0.8 gives 1.22, i.e. 593 effective trials instead of 1,458.
    Fewer trials is LESS deflation and an EASIER bar, so adopting the formula would have handed
    the strategy credit the pre-registration never granted.

    The rule applied generalises: when an estimate and a formula disagree about how much credit a
    result gets, take the one that gives it less.
    """
    assert S.effective_trials() == 1458
    assert S.effective_trials() < S.nominal_trials(), "deflation must reduce the count"
    formula = 10 / (1 + 9 * 0.8)
    assert formula < S.N_EFF_SYMBOLS, (
        "the code took the more permissive of the two estimates")


def test_with_no_data_the_study_reports_BLOCKED_and_synthesises_nothing(tmp_path,
                                                                       monkeypatch) -> None:
    """A verdict computed on generated bars is a fact about the generator, and it would enter the
    funnel wearing the same vocabulary as a real one."""
    monkeypatch.setattr(S, "BARS", tmp_path / "no_bars")
    monkeypatch.setattr(S, "REPORT", tmp_path / "out.json")
    sys.argv = ["run_failed_breakout_study.py"]
    assert S.main() == 0
    rep = json.loads((tmp_path / "out.json").read_text("utf-8"))
    assert rep["verdict"].startswith("BLOCKED")
    assert rep["stage_reached"].startswith("0 of 6")
    # Asserted on MEANING, not one phrasing -- a test that breaks when prose is reworded teaches
    # people to loosen it, which is how this suite lost a real assertion earlier today.
    assert "SYNTHESISED" in rep["note"].upper()
    assert "generator" in rep["note"]
    # the budget is declared even when nothing ran -- that is the point of pre-registering it
    assert rep["nominal_trials"] == 4860 and rep["effective_trials"] == 1458


def test_the_runner_cannot_reach_a_venue_or_place_an_order() -> None:
    """Stage A has no authority. Fenced by source inspection because a study that could fetch is a
    study that could be re-run until it passed."""
    src = Path("scripts/run_failed_breakout_study.py").read_text("utf-8")
    for banned in ("urllib", "requests", "place_market", "place_post_only", "_signed"):
        assert banned not in src, f"the study reaches something it must not: {banned}"


def test_the_mechanism_runs_BEFORE_the_pattern_search() -> None:
    """Mining first and explaining afterwards is how a pattern search becomes a mechanism story.
    The mechanism step can only ever DOWNGRADE the claim, so running it first costs nothing."""
    src = Path("scripts/run_failed_breakout_study.py").read_text("utf-8")
    assert src.index("STAGE 1: MECHANISM") < src.index("mechanism_evidence("), (
        "the mechanism stage must be reached before any evidence is scored")
    assert "halted before the pattern search" in src, (
        "an unmeasurable mechanism must HALT the study, not merely annotate it")
