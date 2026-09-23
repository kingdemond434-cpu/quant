"""The claim compiler: a false source may still produce a true hypothesis, and never capital.

The organ exists because `ontology.map_to_capabilities` is deliberately literal -- it matches only
text that already NAMES a capability group -- and almost nothing in the wild does. A forum post
saying "they run thousands of small models and average them" mapped to the empty tuple, so the
claim was admitted to the queue and then went nowhere: the same outcome as refusing it, wearing
the costume of the opposite.

What is pinned here is the epistemics, not the vocabulary. The table will grow; these properties
must not move.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

BASE = Path(__file__).resolve().parent.parent
if str(BASE) not in sys.path:
    sys.path.insert(0, str(BASE))

from frontier_intel import claims, ontology, registry  # noqa: E402


def _c(text: str, **kw: object) -> claims.Claim:
    return claims.Claim(text=text, **kw)  # type: ignore[arg-type]


# --------------------------------------------------------------- mythology is not the mechanism
def test_a_rumour_and_a_paper_yield_the_same_mechanism() -> None:
    """THE POINT OF THE WHOLE FILE.

    Whether the poster worked there is a question about the poster; whether the technique helps is
    a question about the technique, and only the second has an experiment attached. If attribution
    language changed the extracted mechanism, the desk would be testing reputations.
    """
    rumour = "allegedly some ex-employee says they run thousands of small models and average them"
    paper = "we train large ensembles of weak predictors"
    assert [m.capability for m in claims.to_mechanisms(rumour)] == ["ENSEMBLES"]
    assert [m.capability for m in claims.to_mechanisms(paper)] == ["ENSEMBLES"]


def test_stripping_removes_attribution_and_keeps_the_technical_content() -> None:
    out = claims.strip_mythology(
        "reportedly a former employee said they use graph neural networks")
    assert "former employee" not in out
    assert "reportedly" not in out
    assert "graph neural networks" in out


def test_every_mechanism_carries_a_falsifier() -> None:
    """A proposition nothing could refute is not a hypothesis, it is a slogan."""
    for _, mech in claims.MECHANISMS:
        assert mech.falsifier.strip(), f"{mech.capability} has no falsifier"
        assert mech.proposition.strip()
        assert mech.falsifier != mech.proposition


def test_every_capability_the_compiler_emits_exists_in_the_ontology() -> None:
    """Otherwise the literal mapper still fails downstream and nothing has been fixed.

    The compiler's entire job is to do the NAMING that `map_to_capabilities` refuses to guess. A
    capability name that is not an ontology group is a name that maps to nothing -- the original
    defect, reintroduced one layer further along where it is harder to see.
    """
    known = set(ontology.NAMES)
    for _, mech in claims.MECHANISMS:
        assert mech.capability in known, f"{mech.capability} is not an ontology group"


def test_compiled_mechanism_text_survives_the_literal_mapper() -> None:
    """End to end: the compiler's output is what the literal mapper was waiting for."""
    rec = claims.compile_claim(_c("they run thousands of small models and average them"))
    assert rec["capabilities"] == ["ENSEMBLES"]
    assert ontology.map_to_capabilities(rec["mechanism_text"]) == ("ENSEMBLES",)


# ------------------------------------------------------------------------------ plural regression
@pytest.mark.parametrize("text", [
    "they use graph neural networks across futures",
    "they train embeddings over the whole market",
    "massive gpu clusters and distributed training",
    "their slippage models are very good",
    "feature stores everywhere",
    "aum constraints push them out of small trades",
])
def test_the_plural_is_how_people_actually_write_these_phrases(text: str) -> None:
    """Regression for the `_v` suffix rule.

    Written the obvious way each pattern ends in a word boundary, so `graph neural network`
    matched and `graph neural networkS` did not -- invisible in review, fatal in use, and a miss
    is a claim that reaches the queue as unreadable prose.
    """
    assert claims.to_mechanisms(text), f"no mechanism recovered from {text!r}"


# ----------------------------------------------------------------------------------- genealogy
def test_ten_reposts_are_one_origin() -> None:
    """A machine that counts reposts as corroboration believes whatever propagates fastest.

    Worst in exactly the multilingual ecosystems the desk was asked to mine, where one sentence is
    repeated across many platforms within hours.
    """
    origin = "they run thousands of small models and average them together for the forecast"
    batch = [
        _c(origin, source="forum-a", retrieved_at="2026-09-01T00:00:00+00:00"),
        _c("Quoting: " + origin, source="forum-a", retrieved_at="2026-09-01T01:00:00+00:00"),
        _c(origin + " (via forum-a)", source="forum-a",
           retrieved_at="2026-09-01T02:00:00+00:00"),
        _c("they run thousands of small models and average them together for the forecasts",
           source="forum-a", retrieved_at="2026-09-01T03:00:00+00:00"),
    ]
    assert len(claims.genealogy(batch)) == 1
    assert claims.independent_sources(batch) == 1


def test_genuinely_different_statements_stay_separate() -> None:
    batch = [
        _c("they run thousands of small models and average them", source="forum-a"),
        _c("their execution desk models market impact with a square-root law", source="paper-b"),
    ]
    assert len(claims.genealogy(batch)) == 2
    assert claims.independent_sources(batch) == 2


def test_one_site_repeating_itself_is_not_a_second_witness() -> None:
    batch = [
        _c("they run thousands of small models and average them", source="forum-a"),
        _c("their execution desk models market impact with a square-root law", source="forum-a"),
    ]
    assert len(claims.genealogy(batch)) == 2      # two distinct statements
    assert claims.independent_sources(batch) == 1  # but one origin


# ------------------------------------------------------------------------------------ authority
def test_no_claim_at_any_grade_receives_capital_authority() -> None:
    """The ladder to capital is the same one every candidate walks.

    An official technical page from the most respected firm on the registry is still a claim, and
    a claim is still a hypothesis. Replication, the ten gates, a forward clock and measured rent
    decide -- and this field records only that no shortcut was granted.
    """
    for grade in registry.GRADES:
        rec = claims.compile_claim(
            _c("we train large ensembles of weak predictors", grade=grade, source="official"))
        assert rec["capital_authority"] in {"ZERO", "BLOCKED"}
        assert rec["research_authority"] == "ALLOWED"


def test_confidential_sounding_claims_are_blocked_from_capital_but_not_from_research() -> None:
    """The general principle is public regardless of who said it first.

    What must never happen is a position sized from something whose only support is material
    somebody should not have published.
    """
    rec = claims.compile_claim(
        _c("internal only, not public: they run thousands of small models", source="forum"))
    assert rec["capital_authority"] == "BLOCKED"
    assert rec["research_authority"] == "ALLOWED"
    assert "confidential" in rec["capital_authority_why"]
    assert rec["capabilities"] == ["ENSEMBLES"]     # the mechanism still stands on its own


def test_an_unrecognised_claim_is_flagged_not_discarded() -> None:
    """The genuinely new technique arrives looking exactly like an unmatched claim.

    Dropping it is how a taxonomy becomes a ceiling: the miner would then only ever find the
    things it already had words for.
    """
    rec = claims.compile_claim(_c("they use a hyperdimensional simplectic resonator"))
    assert rec["unrecognised"] is True
    assert rec["capabilities"] == []
    assert rec["research_authority"] == "ALLOWED"


# --------------------------------------------------------------------------- two-score sources
def test_truth_and_idea_yield_are_learned_from_different_ledgers(tmp_path: Path) -> None:
    """A source may be unreliable about facts and an excellent generator of ideas.

    Collapsing the two into one number silences exactly the weak sources the principal asked to
    mine: truth 0.2 with yield 0.8 means crawl it often and believe it rarely, which a single
    score cannot say.
    """
    import json
    truth = tmp_path / "truth.jsonl"
    yields = tmp_path / "yield.jsonl"
    truth.write_text("\n".join(
        json.dumps({"source": "forum-a", "hit": i < 2}) for i in range(10)))
    yields.write_text("\n".join(
        json.dumps({"source": "forum-a", "hit": i < 8}) for i in range(10)))

    t, t_why = claims.truth_score("forum-a", ledger=truth)
    y, y_why = claims.idea_yield("forum-a", ledger=yields)
    assert t == pytest.approx(0.2)
    assert y == pytest.approx(0.8)
    assert "corroborated" in t_why
    assert "tested hypothesis" in y_why


def test_a_thin_ledger_returns_none_rather_than_a_confident_zero(tmp_path: Path) -> None:
    """Four observations is not a rate. `None` says 'prior stands'; 0.0 would say 'never right'."""
    import json
    thin = tmp_path / "truth.jsonl"
    thin.write_text("\n".join(
        json.dumps({"source": "new-source", "hit": False}) for _ in range(4)))
    score, why = claims.truth_score("new-source", ledger=thin)
    assert score is None
    assert "prior stands" in why


# -------------------------------------------------------------------------------- the mandate
def test_the_vocabulary_hunts_no_crypto_exchange_universe() -> None:
    """MT5 UNIVERSE MANDATE (principal 2026-08-18), which binds every miner on this desk.

    No miner, hunter, query, channel list or scoring vocabulary may target crypto-exchange-native
    opportunities. A frontier miner is a plausible place for that to creep back in, because the
    firms it watches are widely written about in those ecosystems -- so the table is fenced.
    """
    banned = ("binance", "bybit", "okx", "hyperliquid", "perpetual swap", "funding rate",
              "defi", "on-chain", "dex ")
    for pattern, mech in claims.MECHANISMS:
        blob = f"{pattern.pattern} {mech.proposition} {mech.falsifier}".lower()
        for word in banned:
            assert word not in blob, f"{mech.capability} names {word!r}"


def test_compile_all_counts_convergence_by_origin() -> None:
    """Cross-firm convergence is a prior about where to look, and only if the sources differ."""
    same = "they run thousands of small models and average them for the final forecast"
    out = claims.compile_all([
        _c(same, source="forum-a", firm="A", retrieved_at="2026-09-01T00:00:00+00:00"),
        _c(same, source="forum-a", firm="A", retrieved_at="2026-09-01T01:00:00+00:00"),
    ])
    assert out["convergence"]["ENSEMBLES"] == 1
    assert out["claims"] == 2
    assert out["origins"] == 1
