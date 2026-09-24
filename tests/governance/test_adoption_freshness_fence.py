"""THE ADOPTION FENCE MUST FIRE ON A FAILURE AND PASS ON A SUCCESS.

`scripts/check_adoption_freshness.py` shipped 2026-09-24 with no test. A fence nobody has
watched fail is a claim the desk cannot cash (L1.49): it is registered in `run_law_gate.py`, it
had been green all morning, and the box it guards was three commits behind at the time. These
cases drive `judge()` directly, because `judge` is the whole verdict and it is pure -- every
input it reads is already in the doc that `read_evidence` builds.

The case that matters most is BREACH (c). It used to read `behind > 0 and age > grace`, so it
could only fire when breach (a) had already failed the check, and the failure it was written for
-- adoption reporting success every hour while never landing origin's code -- was unreachable.
The `merge_base_age_s` case below is that failure, and it is the shape the trading box was
actually in.
"""
from __future__ import annotations

import importlib.util
from pathlib import Path
from typing import Any

import pytest

ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location(
    "check_adoption_freshness", ROOT / "scripts" / "check_adoption_freshness.py")
assert SPEC and SPEC.loader
FENCE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(FENCE)

HOUR = 3600.0


def _doc(**over: Any) -> dict[str, Any]:
    """An adopting host that has just adopted cleanly: the shape every case below perturbs."""
    doc: dict[str, Any] = {
        "problems": [], "notes": [], "ok": True,
        "task": {"present": True, "cadence_s": 3600, "limit_s": 7200, "lastresult": "0"},
        "heartbeat": {"present": True, "unfinished": False, "started_age_s": 60.0},
        "adoption_state": {"present": True, "ok": True},
        "log": {"present": True},
        "last_success_age_s": 0.5 * HOUR,
        "lag": {"branch": "b", "behind": 0, "merge_base": "aaa",
                "merge_base_since": "2026-09-24T10:00:00+00:00", "merge_base_age_s": 0.5 * HOUR},
    }
    doc.update(over)
    return doc


def test_a_clean_adoption_passes() -> None:
    doc = _doc()
    FENCE.judge(doc)
    assert doc["ok"] is True
    assert doc["verdict"] == "FRESH"
    assert doc["problems"] == []


def test_a_host_that_never_adopts_is_not_applicable_and_not_unmeasured() -> None:
    doc = _doc(task={"present": False}, heartbeat={"present": False},
               adoption_state={"present": False}, log={"present": False},
               last_success_age_s=None)
    FENCE.judge(doc)
    assert doc["verdict"] == "NOT_APPLICABLE"
    assert doc["ok"] is True, "a gate red on every non-adopting box gets switched off (L1.43)"


def test_an_adopting_host_with_no_witness_at_all_fails_as_unmeasured() -> None:
    doc = _doc(last_success_age_s=None)
    FENCE.judge(doc)
    assert doc["verdict"] == FENCE.UNMEASURED
    assert doc["ok"] is False, "an absent artifact is what the outage looks like (L1.28a)"


def test_breach_a_no_success_within_the_grace_fires() -> None:
    doc = _doc(last_success_age_s=4 * HOUR)          # grace is 3 x the 1h cadence
    FENCE.judge(doc)
    assert doc["ok"] is False
    assert doc["verdict"] == "STALE"
    assert any("past the" in p for p in doc["problems"])


def test_breach_a_does_not_fire_one_minute_inside_the_grace() -> None:
    doc = _doc(last_success_age_s=3 * HOUR - 60.0)
    FENCE.judge(doc)
    assert doc["ok"] is True
    assert doc["verdict"] == "FRESH"


def test_breach_b_a_run_that_started_and_never_finished_fires() -> None:
    doc = _doc(heartbeat={"present": True, "unfinished": True,
                          "started_age_s": 3 * HOUR, "stage": "started"})
    FENCE.judge(doc)
    assert doc["ok"] is False, "the scheduler's kill lands between statements and logs nothing"
    assert any("never recorded finishing" in p for p in doc["problems"])


def test_breach_b_tolerates_a_run_still_inside_its_execution_limit() -> None:
    doc = _doc(heartbeat={"present": True, "unfinished": True,
                          "started_age_s": HOUR, "stage": "started"})
    FENCE.judge(doc)
    assert doc["ok"] is True, "an adoption in flight is not an outage"


def test_breach_c_fires_when_the_merge_base_is_frozen_though_every_hour_succeeded() -> None:
    """THE TRADING BOX, 2026-09-24, with its own numbers.

    Merge records that actually landed came 1.4 h, 2.4 h and 2.3 h apart overnight and then
    stopped for 7.4 h. Through that gap `adopt_and_seal.log` kept saying "nothing to seal",
    which IS a success line and is counted as one, so at 09:55:39Z the fence read
    last_success_age_s = 2295 s against a 3 h grace and published FRESH -- while the last merge
    to land was 6.2 h old, the merge base had been pinned since 11:17, and the box drifted from
    1 to 9 commits behind. The old clause could not reach this case.
    """
    doc = _doc(last_success_age_s=0.6 * HOUR,
               lag={"branch": "b", "behind": 9, "merge_base": "b8ab5342",
                    "merge_base_age_s": 6.2 * HOUR})
    FENCE.judge(doc)
    assert doc["ok"] is False, (
        "a success that never moves the merge base is a refusal with a green light; this is "
        "the case the old `behind > 0 and age > grace` clause could never reach")
    assert any("merge base has not advanced" in p for p in doc["problems"])


def test_breach_c_stays_quiet_while_origin_merely_moves_ahead() -> None:
    """A healthy box reads behind>0 almost always, because origin gains commits all night. That
    must stay a note, or the fence reds on every busy evening and gets switched off."""
    doc = _doc(lag={"branch": "b", "behind": 4, "merge_base": "ccc",
                    "merge_base_age_s": 0.2 * HOUR})
    FENCE.judge(doc)
    assert doc["ok"] is True
    assert any("inside the grace" in n for n in doc["notes"])
    assert doc["problems"] == []


def test_uncountable_lag_is_named_unmeasured_and_never_silently_passed() -> None:
    doc = _doc(lag={"branch": "b", "behind": None})
    FENCE.judge(doc)
    assert any("UNMEASURED" in n for n in doc["notes"])


@pytest.mark.parametrize("code", ["2147946720", "267014"])
def test_scheduler_kill_codes_are_explained_rather_than_hunted(code: str) -> None:
    doc = _doc(task={"present": True, "cadence_s": 3600, "limit_s": 7200, "lastresult": code})
    FENCE.judge(doc)
    assert any("SCHEDULER stopped the run" in n for n in doc["notes"])


def test_the_fence_reduces_nothing() -> None:
    """It caps no risk and gates no capital: it reports whether the box runs the shipped code."""
    text = (ROOT / "scripts" / "check_adoption_freshness.py").read_text(encoding="utf-8")
    assert "NEVER REDUCES ANYTHING" in text
    for banned in ("lot", "heat", "risk_fraction", "max_position"):
        assert f"{banned} =" not in text
