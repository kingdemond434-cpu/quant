"""The implementer removes the human courier and keeps the money-path fence.

The loop used to end at a plan: the supervisor scored a gap, wrote a queue row, and a person
carried the idea to a builder by hand. That courier step is what the mandate objects to -- "no
known gap is allowed to remain merely because nobody manually remembered to tell the builder."

What it must NOT remove is the boundary the supervisor documented: an organ that can both propose
and merge into the tree that sizes real positions is one bad extraction away from a live defect.
So every test here is about containment and authority, not about code quality -- the ten gates
judge the code, and nothing this file writes has any authority at all.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

BASE = Path(__file__).resolve().parent.parent
for _p in (str(BASE), str(BASE.parent.parent)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from frontier_intel import implementer  # noqa: E402


def _card(**over: object) -> dict:
    card = {
        "candidate_id": "cand_test01",
        "capability": "ENSEMBLES",
        "mechanism": "large ensembles of weak predictors may beat one concentrated model",
        "falsifier": "an ensemble of N weak learners does not beat the best single learner OOS",
        "firm": "Lingjun", "source": "forum-a", "grade": "D", "url": "u1",
    }
    card.update(over)
    return card


# ------------------------------------------------------------------ the fence
@pytest.mark.parametrize("escape", [
    "../../mt5desk/gateway.py",
    "../../mt5desk/decision_core.py",
    "../../../libs/ops/release.py",
    "../../scripts/run_deadman_switch.py",
    "../../data/secrets/llm_panel.json",
    "/etc/passwd",
])
def test_it_cannot_write_outside_the_challenger_directory(escape: str) -> None:
    """Checked on the RESOLVED path, which is what makes it a containment guarantee.

    A denylist of names alone would not stop `..` walking out of the challenger directory into
    the live tree, and a generated module name plausibly could contain one.
    """
    with pytest.raises(PermissionError):
        implementer._refuse_money_path(implementer.CHALLENGERS / escape)


def test_an_ordinary_challenger_path_is_allowed() -> None:
    implementer._refuse_money_path(implementer.CHALLENGERS / "cand_x" / "ensembles.py")


def test_the_money_path_list_names_the_files_that_move_money() -> None:
    """Pinned so a future edit cannot quietly shorten it."""
    for required in ("mt5desk/gateway.py", "mt5desk/decision_core.py",
                     "scripts/run_deadman_switch.py", "data/secrets"):
        assert required in implementer.MONEY_PATH


# ------------------------------------------------------------------ authority
def test_every_challenger_is_written_with_zero_authority(tmp_path: Path,
                                                         monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(implementer, "CHALLENGERS", tmp_path / "challengers")
    out = implementer.build(_card(), apply=True)
    assert out["status"] == "BUILT"

    manifest = json.loads((Path(out["dir"]) / "MANIFEST.json").read_text("utf-8"))
    assert manifest["authority"] == "ZERO"
    assert "never because it was written" in manifest["authority_why"]
    # provenance survives to the artifact: which claim, from whom, at what grade
    assert manifest["provenance"]["firm"] == "Lingjun"
    assert manifest["provenance"]["grade"] == "D"


def test_a_card_with_no_falsifier_is_refused(tmp_path: Path,
                                             monkeypatch: pytest.MonkeyPatch) -> None:
    """A challenger that cannot fail is a module with opinions.

    Refusing here rather than building something unfalsifiable is the difference between a
    research organ and the implementation theatre the mandate names.
    """
    monkeypatch.setattr(implementer, "CHALLENGERS", tmp_path / "challengers")
    out = implementer.build(_card(falsifier=""), apply=True)
    assert out["status"] == "REFUSED"
    assert "falsifier" in out["why"]
    assert not (tmp_path / "challengers").exists()


def test_the_falsifier_reaches_the_generated_test(tmp_path: Path,
                                                  monkeypatch: pytest.MonkeyPatch) -> None:
    """Written from the card, not invented -- `claims.Mechanism` already recovered it."""
    monkeypatch.setattr(implementer, "CHALLENGERS", tmp_path / "challengers")
    out = implementer.build(_card(), apply=True)
    tests = list(Path(out["dir"]).glob("test_*.py"))
    assert len(tests) == 1
    assert "does not beat the best single learner OOS" in tests[0].read_text("utf-8")


# ------------------------------------------------------------------ unseated
def test_no_seat_produces_a_specification_and_says_so(tmp_path: Path,
                                                      monkeypatch: pytest.MonkeyPatch) -> None:
    """UNSEATED is a verdict, not a crash, and never an empty module reported as success.

    Measured on the box 2026-09-07: world_crawler rejected 910 tasks with "no seat: export
    OPENROUTER_API_KEY". An organ that reported BUILT on that would be lying in exactly the way
    this desk keeps getting burned by.
    """
    monkeypatch.setattr(implementer, "CHALLENGERS", tmp_path / "challengers")
    monkeypatch.setattr(implementer, "_generate",
                        lambda card: ("", "UNSEATED: no seat"))
    out = implementer.build(_card(), apply=True)
    assert out["status"] == "BUILT"
    assert out["generation"].startswith("UNSEATED")

    module = next(p for p in Path(out["dir"]).glob("*.py") if not p.name.startswith("test_"))
    body = module.read_text("utf-8")
    assert "UNSEATED" in body
    assert "OPENROUTER_API_KEY" in body
    # the specification is the deliverable, so it must actually be there
    assert "FALSIFIER" in body and "AUTHORITY: ZERO" in body


def test_dry_run_writes_nothing(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(implementer, "CHALLENGERS", tmp_path / "challengers")
    out = implementer.build(_card(), apply=False)
    assert out["status"] == "DRY"
    assert not (tmp_path / "challengers").exists()


def test_the_specification_states_what_wired_means() -> None:
    """A module nothing calls is the failure this desk has already paid for repeatedly.

    Naming the consumer BEFORE any code is written is what stops it recurring.
    """
    spec = implementer.specification(_card())
    assert "producer -> storage -> consumer -> decision path -> telemetry" in spec
    assert "AUTHORITY    ZERO" in spec
    assert "ENSEMBLES" in spec
