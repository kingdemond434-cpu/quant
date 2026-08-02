"""The adaptive data acquisition agent (triage #93).

WHAT "ADAPTIVE" HAS TO MEAN HERE, and the reason the obvious build was refused. `research_cio.py`
already carries an INFORMATION ADVANTAGE SCORE: a hardcoded table of uniqueness, predictive power,
persistence and replication difficulty, all hand-assigned. Ranking acquisitions by that table
produces a confident order built out of one author's priors wearing the vocabulary of measurement
-- the failure `libs/doctrine/contribution.py` rejects at construction.

So the load-bearing claim under test is that the ranking MOVES WHEN THE DESK LEARNS: the same
source, in the same universe, must fall once the ontology records that its regions were worked and
produced nothing. A static table cannot do that, and a test that only checked "it emits an order"
would pass for one.

The second claim is the refusal: an unchecked source must never outrank a checked-and-rejected one,
or the ranking rewards not looking.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import scripts.acquire_data as A

from libs.hypmax.ontology import SEED_QUESTIONS, map_dataset


def _regions_for(name: str, desc: str = "") -> list[str]:
    return map_dataset(name, desc, SEED_QUESTIONS)


@pytest.fixture
def desk(tmp_path, monkeypatch):
    monkeypatch.setattr(A, "UNIVERSE", tmp_path / "universe.json")
    monkeypatch.setattr(A, "ONTOLOGY_STATE", tmp_path / "ontology.json")
    monkeypatch.setattr(A, "MOAT", tmp_path / "moat.json")
    monkeypatch.setattr(A, "REPORT", tmp_path / "plan.json")
    monkeypatch.setattr(A, "HISTORY", tmp_path / "hist.jsonl")
    return tmp_path


# ------------------------------------------------------------------ the adaptive claim


def test_a_source_falls_once_its_regions_are_worked_and_produce_nothing() -> None:
    """THE LOAD-BEARING TEST, and the one a hardcoded table cannot pass. Identical source, identical
    grade, identical access class -- only the desk's recorded experience differs. If the score does
    not move, the agent is a static ranking with extra steps."""
    entry = {"grade": "verified-clean", "description": "order book depth liquidity withdrawal"}
    regions = _regions_for("orderbook depth", entry["description"])
    assert regions, "fixture must map to at least one frontier region or it proves nothing"

    virgin = A.score_candidate("orderbook depth", entry, state={})
    barren = A.score_candidate("orderbook depth", entry,
                               state={r: {"attempts": 400, "survivors": 0} for r in regions})
    assert barren["score"] < virgin["score"], (virgin["score"], barren["score"])


def test_a_region_that_HAS_produced_survivors_is_not_penalised_for_being_worked() -> None:
    """Coverage and exhaustion are different questions. Thirty attempts with two survivors is a
    RICH region worth mining harder; only zero survivors is evidence of barrenness, and conflating
    them would drive the desk away from exactly the ground it has proved fertile."""
    entry = {"grade": "verified-clean", "description": "order book depth liquidity withdrawal"}
    regions = _regions_for("orderbook depth", entry["description"])
    rich = A.score_candidate("orderbook depth", entry,
                             state={r: {"attempts": 400, "survivors": 3} for r in regions})
    barren = A.score_candidate("orderbook depth", entry,
                               state={r: {"attempts": 400, "survivors": 0} for r in regions})
    assert rich["score"] > barren["score"]


# ------------------------------------------------------------------ the refusals


def test_an_ungraded_source_ranks_below_every_graded_one_including_rejects() -> None:
    """A ranking that rewards not looking is worse than no ranking. An unchecked source is LESS
    known than one somebody opened and rejected, so it must not sit above `unverified`."""
    assert min(p for p, _ in A.GRADE_P.values()) > A.UNGRADED_P
    p_none, why = A._grade_p("")
    assert p_none == A.UNGRADED_P
    assert "rewards not looking" in why


def test_a_source_mapping_to_no_frontier_region_scores_zero_not_a_default() -> None:
    """A source nobody can say what it would ANSWER is a wish, not an acquisition. Giving it a
    middling default would let unfalsifiable candidates accumulate at mid-table forever."""
    r = A.score_candidate("qwertyuiop zxcvbnm", {"grade": "verified-clean"}, state={})
    assert r["regions"] == []
    assert r["score"] == 0.0
    assert r["unmeasured"] is True
    assert "is not an acquisition, it is a wish" in r["why"]


def test_public_data_is_discounted_however_good_the_grade() -> None:
    """Edge found in data anyone can pull in an afternoon is already priced. Replication
    difficulty MULTIPLIES for the same reason it does in EVIG -- no other term rescues it."""
    desc = "order book depth liquidity withdrawal"
    pub = A.score_candidate("x", {"grade": "verified-clean", "description": desc,
                                  "access": "public"}, state={})
    own = A.score_candidate("x", {"grade": "verified-clean", "description": desc,
                                  "access": "self-recorded tape"}, state={})
    assert own["score"] > pub["score"]
    assert own["access_class"] == "self-recorded"
    assert pub["access_class"] == "public"


def test_the_access_class_is_read_from_the_entry_never_guessed_from_the_name() -> None:
    """Inferring "this sounds proprietary" from a source's NAME is how an opinion re-enters a
    ranking that was built to exclude opinions."""
    assert A._access_class({"notes": "keyless community API, rate-limited"}) == "gated-free"
    # Prose, not an enum -- "rebuilt from the public methodology" is a reconstruction however it
    # is spelled, and matching only "reconstruct" demoted real ones to the most-discounted class.
    assert A._access_class({"why": "rebuilt from the public methodology"}) == "reconstructed"
    assert A._access_class({"why": "self-computed from mint/burn events"}) == "reconstructed"
    assert A._access_class({}) == "public", "unknown must fall to the LEAST advantaged class"


# ------------------------------------------------------------------ end to end


def test_an_absent_universe_refuses_to_rank_rather_than_printing_an_empty_plan(desk) -> None:
    """An empty ranking reads as 'nothing worth acquiring', which is the opposite of 'the digger
    has not published yet'. data/ is gitignored, so this is the FRESH-CHECKOUT state and it must
    not be mistaken for a finding."""
    assert A.main() == 0
    rep = json.loads((desk / "plan.json").read_text("utf-8"))
    assert rep["state"] == "NO SOURCE UNIVERSE"
    assert rep["candidates"] == 0
    assert "expected in a fresh checkout" in rep["reason"]


def test_a_real_universe_produces_a_ranked_explained_plan(desk) -> None:
    (desk / "universe.json").write_text(json.dumps({
        "own recorder": {"grade": "verified-clean", "access": "self-recorded tape",
                         "description": "order book depth liquidity withdrawal microstructure"},
        "dune dashboard": {"grade": "unverified", "access": "public",
                           "description": "on-chain flows"},
        "mystery feed": {"description": "unknown"},
    }), "utf-8")
    assert A.main() == 0
    rep = json.loads((desk / "plan.json").read_text("utf-8"))
    assert rep["candidates"] == 3
    assert rep["plan"][0]["rank"] == 1
    assert all(r["why"] for r in rep["plan"]), "every row must be auditable six weeks later"
    # the ungraded, unmappable one must be last
    assert rep["plan"][-1]["source"] == "mystery feed"


def test_the_agent_claims_no_acquisition_authority(desk) -> None:
    """It ranks and explains. Anything that could spend money or start a collector belongs behind
    a human decision, not behind a score."""
    (desk / "universe.json").write_text('{"a": {"grade": "verified-clean"}}', "utf-8")
    A.main()
    rep = json.loads((desk / "plan.json").read_text("utf-8"))
    assert "NONE" in rep["authority"]
    assert "spends nothing" in rep["authority"]


def test_history_is_append_only(desk) -> None:
    (desk / "universe.json").write_text('{"a": {"grade": "verified-clean"}}', "utf-8")
    A.main()
    A.main()
    assert len((desk / "hist.jsonl").read_text("utf-8").strip().splitlines()) == 2
