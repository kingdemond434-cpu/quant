"""The graveyard novelty gate, where it is wired into live generation.

These assert the two things that decide whether the gate is worth anything:

  1. RENDERING PARITY. The corpus and the live generator must render a hypothesis identically or
     similarity decays to zero, every candidate reads as novel, and the gate reports a clean bill
     of health while catching nothing. The desk has already measured this gate at 0% recall once;
     a drifted renderer is how that happens silently.
  2. THE GATE MUST BITE, AND ONLY WHERE IT SHOULD. It has to catch the case the incumbent
     content-hash dedupe provably misses -- the same dead mechanism on a different symbol -- and
     it must not touch a genuinely new mechanism.
"""

from __future__ import annotations

import json

from tests.autodiscovery.conftest import noise_provider

from libs.alpha_factory.hypothesis_novelty import PriorIdea
from libs.alpha_factory.hypothesis_render import (
    candidate_features,
    candidate_statement,
    params_keys,
    params_text,
)
from libs.autodiscovery.memory import content_hash
from libs.autodiscovery.models import Family, Hypothesis
from libs.autodiscovery.novelty import NoveltyGate, render
from libs.autodiscovery.orchestrator import AutoDiscoveryLab
from libs.store.audit import AuditLog
from libs.store.connection import Database
from libs.validation.economic_prior import MechanismType


def _hyp(symbol: str = "EURUSD", **params: float) -> Hypothesis:
    return Hypothesis(
        family=Family.TREND, subtype="ma_cross", symbol=symbol,
        params=params or {"fast": 20.0, "slow": 50.0}, mechanism=MechanismType.BEHAVIORAL,
        edge_source="trend", failure_modes=["chop"],
    )


def _prior_from(hyp: Hypothesis, *, symbols: list[str] | None = None) -> PriorIdea:
    """A prior built the way scripts/build_graveyard_priors.py builds one, from sqlite strings."""
    params_json = json.dumps(dict(hyp.params))
    return PriorIdea(
        id="cand:trend/ma_cross",
        statement=candidate_statement(
            hyp.family.value, hyp.subtype, hyp.mechanism.value, params_json,
            symbols or [hyp.symbol],
        ),
        features=candidate_features(
            hyp.family.value, hyp.subtype, hyp.mechanism.value, params_json),
        lesson="rejected: dsr",
    )


# ---------------------------------------------------------------- rendering parity
def test_dict_and_json_params_render_identically() -> None:
    """The builder holds params_json from sqlite; the generator holds a dict. One renderer.

    If these ever diverge the gate does not fail loudly -- it just stops matching, which is
    indistinguishable from a clean cycle.
    """
    as_dict = {"fast": 20.0, "slow": 50.0}
    as_json = json.dumps(as_dict)
    assert params_keys(as_dict) == params_keys(as_json) == ("fast", "slow")
    assert params_text(as_dict) == params_text(as_json) == "fast=20 slow=50"
    assert candidate_features("trend", "ma_cross", "behavioral", as_dict) == candidate_features(
        "trend", "ma_cross", "behavioral", as_json)


def test_live_render_matches_the_corpus_render() -> None:
    """`.value` on both enums is load-bearing: the corpus was compiled from stored enum VALUES."""
    hyp = _hyp()
    statement, features = render(hyp)
    assert features == ("family:trend", "subtype:ma_cross", "mech:behavioral",
                        "param:fast", "param:slow")
    assert "Family.TREND" not in statement and "trend ma_cross rule" in statement


def test_unparseable_params_do_not_crash_the_renderer() -> None:
    assert params_keys("{not json") == () and params_text("{not json") == ""


# ---------------------------------------------------------------- the gate's discrimination
def test_same_mechanism_on_a_new_symbol_is_caught_where_the_hash_is_not() -> None:
    """The exact miss this gate exists for, asserted against the incumbent guard directly.

    `CandidateStore.exists` hashes (family, subtype, SYMBOL, params), so the same dead rule on the
    next instrument is a brand-new hash and gets paid for in full.
    """
    dead = _hyp(symbol="EURUSD")
    same_mechanism_elsewhere = _hyp(symbol="XAUUSD")
    assert content_hash(dead) != content_hash(same_mechanism_elsewhere)   # hash: sees nothing
    gate = NoveltyGate([_prior_from(dead)])
    assert gate.screen(same_mechanism_elsewhere).is_redundant             # gate: catches it


def test_a_nudged_parameter_value_is_still_re_tested_ground() -> None:
    gate = NoveltyGate([_prior_from(_hyp(fast=20.0, slow=50.0))])
    assert gate.screen(_hyp(fast=10.0, slow=30.0)).is_redundant


def test_a_genuinely_new_mechanism_is_not_suppressed() -> None:
    """The expensive failure mode: a gate that eats real edge is worse than no gate."""
    gate = NoveltyGate([_prior_from(_hyp())])
    novel = Hypothesis(
        family=Family.LIQUIDITY, subtype="funding_stress_reversal", symbol="BTCUSDT",
        params={"window": 20.0, "z_entry": 2.0}, mechanism=MechanismType.LIQUIDITY,
        edge_source="crowded perp leverage", failure_modes=["regime"],
    )
    verdict = gate.screen(novel)
    assert not verdict.is_redundant
    assert verdict.novelty_score > 0.5


def test_no_corpus_means_no_gate_rather_than_an_empty_one(tmp_path) -> None:
    """An empty gate is indistinguishable from a working one in a cycle summary."""
    assert NoveltyGate.from_corpus(tmp_path / "absent.json") is None
    corpus = tmp_path / "priors.json"
    corpus.write_text(json.dumps({"priors": [_prior_from(_hyp()).model_dump()]}), "utf-8")
    gate = NoveltyGate.from_corpus(corpus)
    assert gate is not None and len(gate.priors) == 1


# ---------------------------------------------------------------- wired into the cycle
def test_cycle_skips_redundant_hypotheses_before_spending_compute(db: Database) -> None:
    """The wiring itself: suppressed candidates are not tested, and they are COUNTED apart."""
    fetched: list[str] = []

    def counting_provider(symbol: str):
        fetched.append(symbol)
        return noise_provider()(symbol)

    # A prior covering every trend/ma_cross construction the planner will propose.
    gate = NoveltyGate([_prior_from(_hyp(), symbols=["EURUSD", "XAUUSD"])])
    lab = AutoDiscoveryLab(db, counting_provider, families=[Family.TREND], novelty=gate)
    result = lab.cycle(["EURUSD", "XAUUSD"])

    assert result.skipped_redundant > 0
    assert result.skipped_duplicate == 0          # nothing recorded yet -- these are NOT dupes
    # The saving is the point: a suppressed hypothesis must not even reach the data provider.
    ungated = AutoDiscoveryLab(db, noise_provider(), families=[Family.TREND])
    assert result.tested < ungated.cycle(["EURUSD", "XAUUSD"]).tested


def test_cycle_without_a_gate_is_unchanged(db: Database) -> None:
    """Default is off, so any caller that never opts in behaves exactly as it did before."""
    lab = AutoDiscoveryLab(db, noise_provider(), families=[Family.TREND])
    result = lab.cycle(["EURUSD"])
    assert result.skipped_redundant == 0
    assert result.tested > 0


def test_every_suppression_is_named_in_the_audit_log(db: Database) -> None:
    """A gate that drops candidates without a record cannot be audited for over-tightness."""
    gate = NoveltyGate([_prior_from(_hyp(), symbols=["EURUSD"])])
    lab = AutoDiscoveryLab(db, noise_provider(), families=[Family.TREND], novelty=gate)
    lab.cycle(["EURUSD"])
    rows = [e for e in AuditLog(db).all() if e.decision_type == "novelty_gate_suppressed"]
    assert rows, "suppressions must be recorded"
    payload = rows[0].inputs
    assert payload["n"] >= 1
    item = payload["items"][0]
    assert item["nearest_id"] == "cand:trend/ma_cross"
    assert item["similarity"] >= gate.threshold
