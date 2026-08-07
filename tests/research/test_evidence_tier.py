"""CLAIMED IS NOT VERIFIED, and the tests exist to keep the two columns apart.

The cheapest way for a research programme to manufacture survivors is to let a number that arrived
in a sentence sit in the field reserved for a number the desk computed. Every mined artifact is
ore. So most of this file is about refusing to promote, and about the ordering NOT being a
credibility ranking -- because "executable ranks first" is one careless sentence away from
"executable is more trustworthy", which is false and in the dangerous direction.
"""

from __future__ import annotations

from libs.research.evidence_tier import (
    BACKTEST_MARKERS,
    CRYPTO_MECHANISMS,
    SOURCE_CLASS_YIELD,
    TIERS,
    Finding,
    MiningRecord,
    Reproduction,
    classify,
    rank,
    translate_to_crypto,
)

# --------------------------------------------------------------- claimed vs verified


def test_A_CLAIM_IS_NEVER_EVIDENCE_HOWEVER_SPECIFIC() -> None:
    """The principal's rule as code: a post saying 'my BTC bot made 40% last month' is ore. A
    precise claim is still a claim, and precision is the property fabrications have most."""
    r = Reproduction("sharpe", claimed=2.17)
    assert not r.is_evidence
    assert "ore, not" in r.summary() and "may not be cited as a result" in r.summary()


def test_NOTHING_IN_THE_MODULE_CAN_MOVE_A_NUMBER_INTO_THE_VERIFIED_COLUMN() -> None:
    """Structural. There is no promote(), no accept(), and no default that copies `claimed` across
    on the grounds that it is probably fine -- populating `verified` requires a run."""
    import libs.research.evidence_tier as ET

    forbidden = [n for n in dir(ET) if n.lower() in {"promote", "accept", "verify", "confirm"}]
    assert forbidden == [], f"a promotion path appeared in the ore layer: {forbidden}"
    assert Reproduction("cagr", claimed=0.4).verified is None


def test_A_FAILED_REPRODUCTION_IS_A_FINDING_NOT_A_MISSING_MEASUREMENT() -> None:
    """The distinction that keeps a refuted claim from being quietly re-queued as untested."""
    r = Reproduction("cagr", claimed=0.4, status="IRREPRODUCIBLE")
    assert not r.is_evidence
    assert "ATTEMPTED AND FAILED" in r.summary()


def test_ONLY_A_COMPLETED_REPRODUCTION_COUNTS_EITHER_WAY() -> None:
    """A reproduction that REFUTES is as much evidence as one that confirms -- and is the more
    common outcome, so treating only confirmations as results would bias the whole ledger."""
    assert Reproduction("sharpe", 2.17, 0.3, "REFUTES").is_evidence
    assert Reproduction("sharpe", 2.17, 2.0, "CONFIRMS").is_evidence
    assert not Reproduction("sharpe", 2.17, None, "NOT_ATTEMPTED").is_evidence


def test_NOTHING_MINED_IS_EVER_A_SURVIVOR() -> None:
    """Present as an explicit always-False property rather than an absent attribute, because an
    attribute that does not exist invites a caller to invent one."""
    assert MiningRecord(mechanism="funding", tier="EXECUTABLE").is_survivor is False


# ------------------------------------------------------------------------ tiering


def test_CODE_PLUS_DATA_IS_EXECUTABLE_AND_THE_REASON_IS_COST_NOT_CREDIBILITY() -> None:
    """The sentence that must stay in the codebase: published bot code is if anything MORE overfit
    than an anecdote, having been tuned until the curve looked good. It ranks first because the
    desk can settle it, not because it is more likely true."""
    tier, why = classify(Finding(has_code=True, has_data=True))
    assert tier == "EXECUTABLE"
    assert "REFUTE" in why and "overfit" in why


def test_THE_TIERS_DESCEND_BY_COST_OF_REFUTATION() -> None:
    assert classify(Finding(has_code=True))[0] == "REPRODUCIBLE_SPEC"
    assert classify(Finding(has_params=True, mechanism_stated=True))[0] == "REPRODUCIBLE_SPEC"
    assert classify(Finding(mechanism_stated=True))[0] == "MECHANISM_ONLY"
    assert classify(Finding(text="made 40% last month"))[0] == "BARE_CLAIM"
    assert TIERS[0] == "EXECUTABLE" and TIERS[-1] == "BARE_CLAIM"


def test_A_BARE_CLAIM_IS_NOT_A_REJECTION() -> None:
    """The mechanism inside a fabricated track record is usually real and the author neither
    invented nor understood it. Discarding the page loses the only part worth having."""
    _tier, why = classify(Finding(text="10x in a week"))
    assert "Mine it for the mechanism" in why


def test_MECHANISM_ONLY_IS_THE_FORM_THAT_TRANSFERS() -> None:
    """A parameter does not survive translation across venues and regimes; a mechanism does."""
    _t, why = classify(Finding(mechanism_stated=True))
    assert "TRANSFERS" in why


# ------------------------------------------------------------------------ ranking


def test_EXECUTABLE_OUTRANKS_A_LOUDER_CLAIM_FROM_A_BETTER_SOURCE_CLASS() -> None:
    """Tier dominates source class, because the queue is ordered by what can be SETTLED."""
    code = Finding(title="repo", source_class="general_forum", has_code=True, has_data=True)
    talk = Finding(title="post", source_class="bot_framework", text="sharpe 3.0")
    order = [f.title for f, _t, _s in rank([talk, code])]
    assert order[0] == "repo"


def test_A_COSTED_BACKTEST_RANKS_ABOVE_AN_UNCOSTED_ONE() -> None:
    """A backtest with no fees, funding or slippage is not a weaker result -- it is a DIFFERENT
    QUANTITY from the one the desk would compute. On a perp book funding alone routinely exceeds
    the edge (WS-006: a Holm-cleared signal netting -0.656 bp/bar)."""
    bare = Finding(title="bare", text="backtest sharpe 2.0")
    costed = Finding(title="costed", text="backtest sharpe 2.0 after fees, funding and slippage")
    ranked = {f.title: s for f, _t, s in rank([bare, costed])}
    assert ranked["costed"] > ranked["bare"]


def test_THE_SCORE_ORDERS_A_QUEUE_AND_CONFERS_NOTHING() -> None:
    """A high score on a claim that fails claim_screen means the desk should read a bad claim
    sooner, not believe it. Encoded as: rank() returns no verdict field at all."""
    (_f, tier, score), = rank([Finding(has_code=True, has_data=True)])
    assert isinstance(score, float) and tier in TIERS


def test_SOURCE_CLASS_PRIORS_ARE_ORDERED_SENSIBLY_AND_ARE_ONLY_PRIORS() -> None:
    """Stated priors calibrated on nothing, recorded as data so a miner measuring its own hit rate
    per class can overwrite them."""
    assert SOURCE_CLASS_YIELD["bot_framework"] > SOURCE_CLASS_YIELD["regional_community"]
    assert SOURCE_CLASS_YIELD["code_repository"] > SOURCE_CLASS_YIELD["general_forum"]
    assert all(0.0 <= v <= 1.0 for v in SOURCE_CLASS_YIELD.values())


# ------------------------------------------------------------- crypto translation


def test_TRADITIONAL_CONSTRUCTS_MAP_ONTO_THINGS_THE_DESK_ACTUALLY_RECORDS() -> None:
    """Where the international and academic miners earn their keep. A futures-basis paper is not a
    Binance strategy; its mechanism maps onto perpetual funding, which the desk records every 8h."""
    got = dict(translate_to_crypto("we study the futures basis and its roll yield"))
    assert "perpetual funding rate + spot-perp basis" in got["futures basis"]
    assert "funding carry" in got["roll yield"]


def test_TRANSLATION_IS_SILENT_WHEN_THERE_IS_NOTHING_TO_TRANSLATE() -> None:
    assert translate_to_crypto("an ordinary sentence about nothing") == []
    assert translate_to_crypto("") == []


def test_THE_BACKTEST_AND_MECHANISM_VOCABULARIES_ARE_PRESENT_AND_WHOLE_WORD() -> None:
    """Substring matching would fire 'oos' inside 'choose' and route half the corpus to the
    backtest category."""
    assert {"sharpe", "walk-forward", "out-of-sample"} <= BACKTEST_MARKERS
    assert not Finding(text="we had to choose between them").mentions_backtest
    assert Finding(text="the OOS window was short").mentions_backtest
    for m in ("funding", "liquidation", "basis", "order_flow", "mev", "options_skew"):
        assert m in CRYPTO_MECHANISMS
