"""THE CONSUMER FOR FOUR MODULES THAT HAD NONE.

Measured 2026-08-08: convergence, evidence_tier, funnel and near_survivor each had ZERO importers.
Tested, documented, committed, and nothing called any of them -- the same shape as a generator with
no executor. A module is not a capability until the cycle runs it and something reads its output.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import pytest
import scripts.run_research_review as RR

_BOX = {
    "verdict": "NO SURVIVORS", "declared_universe": 898_560,
    "counts": {"declared": 898_560, "measurable": 172_890,
               "net_positive_before_deflation": 83_731, "cleared_screen_F1_F2": 2,
               "FORMULA": 0, "FAMILY": 0, "INDEPENDENT_MECHANISM": 0,
               "PORTFOLIO_CONTRIBUTING": None},
    "kill_criteria_fired": {"F5 SAMPLE FLOOR": 2},
    "survivors": [],
}


def test_THE_FUNNEL_IS_FED_FROM_THE_SWEEPS_OWN_COUNTS() -> None:
    """A hand-typed number is an opinion. These come from the run that just happened, which is the
    only reason the diagnosis can be trusted to say 'blocked at execution' not 'generate more'."""
    f = RR.funnel_from_sweep(_BOX)
    assert f.get("tested") == 172_890 and f.get("deflated") == 2


def test_STAGES_THE_SWEEP_CANNOT_SEE_ARE_NONE_NOT_ZERO() -> None:
    """`mined` and `novel_families` belong to the miners. Reporting them as 0 would make the
    funnel diagnose an INFORMATION blockage on every run -- blaming the one stage this artifact
    has no visibility into."""
    f = RR.funnel_from_sweep(_BOX)
    assert f.get("mined") is None and f.get("novel_families") is None


def test_THE_DOMINANT_KILL_OVERRIDES_A_MISLEADING_STAGE_DIAGNOSIS() -> None:
    """CAUGHT BY RUNNING IT. The funnel saw out_of_sample=0 and said OVERFITTING -- 'the harness is
    selecting on noise'. The sweep said F5 SAMPLE FLOOR: both cells died for want of observations.
    Tighten-the-harness and get-more-tape are opposite spends."""
    dominant, caveat = RR.kill_caveat(_BOX, "out_of_sample")
    assert dominant == "F5 SAMPLE FLOOR"
    assert "THE STAGE IS NOT THE CAUSE" in caveat
    assert "more span, NOT a tighter harness" in caveat


def test_A_CONSISTENT_KILL_DOES_NOT_RAISE_A_FALSE_CAVEAT() -> None:
    doc = {**_BOX, "kill_criteria_fired": {"F2 NET OF COST": 9}}
    _d, caveat = RR.kill_caveat(doc, "net_positive")
    assert "THE STAGE IS NOT THE CAUSE" not in caveat and "dominant kill" in caveat


def test_NO_KILLS_YIELDS_NO_CAVEAT() -> None:
    assert RR.kill_caveat({"kill_criteria_fired": {}}, "tested") == ("", "")


def test_KILLED_CELLS_BECOME_NEAR_SURVIVORS_CARRYING_THE_ANCESTRY() -> None:
    """A descendant is a test on the SAME data chosen BECAUSE the desk saw this result, so it
    inherits the whole search that produced it -- otherwise the bank becomes the most efficient
    survivor-manufacturing device on the desk."""
    bank = RR.bank_near_survivors(_BOX)
    assert len(bank) == 1
    row = bank[0]
    assert row["failure_mode"] == "sample"
    assert row["descendant_hurdle"] == pytest.approx(5.236, abs=1e-3)
    assert "898560" in row["note"]


def test_A_SAMPLE_FAILURE_LICENSES_NO_DESCENDANTS() -> None:
    """UNMEASURED is not a weak result. Searching the neighbourhood of a number never measured is
    searching noise with extra steps."""
    assert RR.bank_near_survivors(_BOX)[0]["next_experiments"] == []


def test_A_COST_FAILURE_DOES_LICENSE_DESCENDANTS() -> None:
    doc = {**_BOX, "kill_criteria_fired": {"F2 NET OF COST": 40}}
    plays = RR.bank_near_survivors(doc)[0]["next_experiments"]
    assert plays and any("WS-006" in p for p in plays), "the liquidity check is not offered first"


def test_AN_UNKNOWN_KILL_KEY_IS_SKIPPED_RATHER_THAN_GUESSED() -> None:
    doc = {**_BOX, "kill_criteria_fired": {"F99 SOMETHING NEW": 1}}
    assert RR.bank_near_survivors(doc) == []
    assert RR.failure_mode("F99 SOMETHING NEW") == ""


def test_SURVIVORS_ARE_TIERED_AS_EXECUTABLE() -> None:
    """A sweep survivor is executable by construction -- the desk holds the expression and the
    data, so it can be re-run rather than argued about."""
    doc = {**_BOX, "survivors": [{"key": ["c", "ratio", "1h", "all", "a", "b"], "t": 6.0,
                                  "net_bps": 1.2}]}
    tiers = RR.tier_survivors(doc)
    assert tiers and tiers[0]["tier"] == "EXECUTABLE"


def test_AN_ABSENT_SWEEP_IS_BLOCKED_NOT_AN_EMPTY_FUNNEL(tmp_path, monkeypatch, capsys) -> None:
    monkeypatch.setattr(sys, "argv", [
        "run_research_review.py",
        "--sweep", str(tmp_path / "nope.json"),
        "--out", str(tmp_path / "o.json"),
    ])
    assert RR.main() == 0
    assert "UNMEASURED" in capsys.readouterr().out


def test_CONVERGENCE_REPORTS_UNMEASURED_RATHER_THAN_CLEAN(tmp_path, monkeypatch) -> None:
    """No miner records a derivation chain yet, so cross-ecosystem agreement cannot be told apart
    from three regions echoing one paper."""
    sweep = tmp_path / "s.json"
    sweep.write_text(json.dumps(_BOX), "utf-8")
    out = tmp_path / "o.json"
    monkeypatch.setattr(sys, "argv", ["run_research_review.py", "--sweep", str(sweep),
                                      "--out", str(out)])
    RR.main()
    rep = json.loads(out.read_text())
    assert rep["convergence"]["verdict"] == "UNMEASURED"
    assert rep["funnel"]["dominant_kill"] == "F5 SAMPLE FLOOR"


def test_THE_REVIEW_PROMOTES_NOTHING() -> None:
    """THE CHECK IS FOR CALLS, NOT FOR THE WORD.

    A plain substring scan failed on the module's own disclaimer -- "promotes nothing, sizes
    nothing, trades nothing" -- which is the sentence that STATES the property being tested. A
    guard that fires on the documentation of the invariant it protects trains the next session to
    delete the documentation, so the scan is call-shaped: `promote(`, `place_order(`, an attribute
    read of `api_key`. Prose is allowed to say the word; the code is not allowed to do the thing.
    """
    src = Path("scripts/run_research_review.py").read_text("utf-8")
    for token in ("place_market", "place_order", "promote", "size_position", "api_key"):
        hit = re.search(rf"\b{token}\w*\s*[(=]", src.lower())
        assert hit is None, f"the review reached beyond reading: {hit.group(0)!r}"


def test_CONVERGENCE_IS_CALLED_NOT_DESCRIBED(tmp_path) -> None:
    """The module had ZERO importers and the first draft of this script kept it that way.

    It wrote a hand-typed `"verdict": "UNMEASURED"` that merely ASSERTED what `elevate()` would
    have concluded -- a consumer that discusses a capability instead of exercising it, which is
    the same defect one level up. The verdict must come out of the module on every run.
    """
    p = tmp_path / "f.jsonl"
    p.write_text("\n".join([
        json.dumps({"region": "kr", "mechanism": "funding_flip_squeeze",
                    "source": "https://blog.kr/a", "origins": ["https://arxiv.org/abs/1"],
                    "origins_recorded": True}),
        json.dumps({"region": "br", "mechanism": "funding_flip_squeeze",
                    "source": "https://blog.br/b", "origins": ["https://arxiv.org/abs/1"],
                    "origins_recorded": True}),
    ]), "utf-8")
    rep = RR.convergence_report(p)
    # Two regions, one shared arXiv origin -> ONE observation reported twice, never two.
    assert rep["observations"] == 2
    assert rep["tally"] == {"SHARED_SOURCE_ECHO": 1}
    assert rep["verdict"] == "NONE ELEVATED"


def test_AN_ABSENT_CORPUS_IS_UNMEASURED_NOT_ZERO_CONVERGENCE(tmp_path) -> None:
    rep = RR.convergence_report(tmp_path / "absent.jsonl")
    assert rep["verdict"] == "UNMEASURED" and rep["observations"] == 0
    assert "prose" in rep["reason"]


def test_ORIGINS_RECORDED_DEFAULTS_FALSE_SO_UNCHECKED_IS_NOT_INDEPENDENT(tmp_path) -> None:
    """A row that does not SAY it checked has not checked.

    Defaulting the flag True would turn every unexamined finding into an independent
    confirmation on the first run -- the exact inflation the module exists to refuse.
    """
    p = tmp_path / "f.jsonl"
    p.write_text("\n".join([
        json.dumps({"region": "kr", "mechanism": "m", "source": "https://a.kr/x"}),
        json.dumps({"region": "jp", "mechanism": "m", "source": "https://b.jp/y"}),
    ]), "utf-8")
    rep = RR.convergence_report(p)
    assert rep["tally"] == {"UNVERIFIABLE_PROVENANCE": 1}


def test_MALFORMED_ROWS_ARE_SKIPPED_NOT_GUESSED_AT(tmp_path) -> None:
    p = tmp_path / "f.jsonl"
    p.write_text('not json\n{"region":"kr"}\n\n{"region":"kr","mechanism":"m"}\n', "utf-8")
    assert len(RR.load_observations(p)) == 1
