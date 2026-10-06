"""Every funded seat generates hypotheses -- not three of thirteen.

THE GAP. `hypothesis_generator` passed `n=len(SEATS)` with a hardcoded 3-model list, so
generation asked exactly three models no matter how many the desk paid for. Ten funded seats --
google, qwen, z-ai, moonshotai (Kimi), nvidia and the lab siblings -- never produced a single
hypothesis, on the desk's own #2 supreme objective. Cognitive diversity is the entire reason the
roster is 13 distinct labs rather than 3 copies of one, and generation is exactly the task where
uncorrelated training data pays.

Worse, it was a THIRD model-pinning surface. The panel roster auto-upgrades, the Claude chain
auto-upgrades, and this literal did not gate anything -- but `n=len(SEATS)` silently made the
list's LENGTH a cap on the roster. Same shape as the inline `${_BRAIN_MODEL_CHAIN:-...}` pin and
the `_LABS` literal that capped roster breadth: a constant quietly bounding something that was
supposed to grow.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest
from scripts.seats import resolve_ids

ROOT = Path(__file__).resolve().parents[2]


def _gen():
    spec = importlib.util.spec_from_file_location("hg", ROOT / "scripts/hypothesis_generator.py")
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


HG = _gen()

#: The funded 13-seat shape, including the lab siblings.
ROSTER = [
    "openai/gpt-5.6-terra-pro", "openai/o5-pro", "x-ai/grok-4.3", "google/gemini-3.5-pro",
    "deepseek/deepseek-v4-pro", "qwen/qwen4-max", "z-ai/glm-6", "moonshotai/kimi-k3",
    "nvidia/nemotron-3-ultra", "google/gemma-4", "deepseek/deepseek-r2", "qwen/qwq-2",
    "moonshotai/kimi-linear",
]


def _seated(roster: list[str]) -> list[str]:
    pref = HG.SEAT_PRIORITY + [m for m in roster if m not in HG.SEAT_PRIORITY]
    chosen, _ = resolve_ids(pref, roster, HG.GEN_SEATS, distinct_labs=True)
    return chosen


def test_generation_is_not_capped_at_three() -> None:
    """The regression this file exists for."""
    assert len(_seated(ROSTER)) > 3


def test_every_lab_on_the_roster_generates() -> None:
    """Each distinct lab must contribute -- that is what the roster is bought for."""
    labs = {m.split("/")[0] for m in ROSTER}
    seated_labs = {m.split("/")[0] for m in _seated(ROSTER)}
    assert seated_labs == labs, f"labs never asked to generate: {labs - seated_labs}"


def test_gpt_leads_the_priority_order() -> None:
    """The principal's stated observation: GPT is strong at idea generation. It goes first --
    but leading the order is not the same as being the only seat asked."""
    assert _seated(ROSTER)[0].startswith("openai/")
    assert HG.SEAT_PRIORITY[0].startswith("openai/")


def test_lab_siblings_are_declined_deliberately() -> None:
    """distinct_labs is ON by choice: a second model from one lab adds correlated ideas, which
    is the mode collapse batch_diversity() exists to detect. Volume without information."""
    seated = _seated(ROSTER)
    labs = [m.split("/")[0] for m in seated]
    assert len(labs) == len(set(labs)), "one seat per lab"
    assert len(seated) < len(ROSTER), "siblings are intentionally not seated"


def test_growing_the_roster_grows_generation() -> None:
    """The cap was the defect: a 24-seat roster must generate with more seats than a 13-seat one."""
    bigger = [*ROSTER, "newlab-a/model", "newlab-b/model", "newlab-c/model"]
    assert len(_seated(bigger)) == len(_seated(ROSTER)) + 3


def test_a_shrunken_roster_degrades_without_crashing() -> None:
    small = ["openai/gpt-5.6-terra-pro", "qwen/qwen4-max"]
    assert len(_seated(small)) == 2


def test_seat_count_is_not_derived_from_the_priority_list_length() -> None:
    """`n=len(SEATS)` was the exact bug -- the literal's LENGTH became the roster cap."""
    src = (ROOT / "scripts/hypothesis_generator.py").read_text("utf-8")
    assert "n=len(SEATS)" not in src
    assert "n=GEN_SEATS" in src
    assert HG.GEN_SEATS is None, "None means every seat; an int here is a deliberate budget cap"


def test_full_lens_sweep_is_preserved() -> None:
    """Seats multiply lenses: capping either one throttles the desk's primary output."""
    assert len(HG.LENSES) >= 5
    jobs = len(HG.LENSES) * len(_seated(ROSTER))
    assert jobs >= 40, f"only {jobs} generation jobs/run"


@pytest.mark.parametrize("lab", ["google", "qwen", "z-ai", "moonshotai", "nvidia"])
def test_the_previously_silent_labs_now_generate(lab: str) -> None:
    """Named individually: these five paid for a seat and were never asked to generate."""
    assert any(m.startswith(f"{lab}/") for m in _seated(ROSTER))
