"""Dynamic weight optimization and capital reallocation (proposals only)."""

from __future__ import annotations

from libs.self_improvement.capital_reallocator import CapitalReallocator
from libs.self_improvement.weight_optimizer import DynamicWeightOptimizer, WeightCandidate


def test_weight_optimizer_favours_healthier() -> None:
    opt = DynamicWeightOptimizer(max_weight=1.0)
    proposal = opt.propose(
        [
            WeightCandidate(alpha_id="strong", health_score=90.0),
            WeightCandidate(alpha_id="weak", health_score=30.0),
        ]
    )
    assert proposal.weights["strong"] > proposal.weights["weak"]
    assert abs(sum(proposal.weights.values()) - 1.0) < 1e-9
    assert proposal.requires_portfolio_approval is True  # always


def test_weight_optimizer_respects_cap() -> None:
    opt = DynamicWeightOptimizer(max_weight=0.25)
    candidates = [WeightCandidate(alpha_id=f"a{i}", health_score=80.0) for i in range(4)]
    proposal = opt.propose(candidates)
    assert max(proposal.weights.values()) <= 0.25 + 1e-9
    assert abs(sum(proposal.weights.values()) - 1.0) < 1e-9


def test_weight_optimizer_zero_when_all_unhealthy() -> None:
    opt = DynamicWeightOptimizer()
    proposal = opt.propose(
        [
            WeightCandidate(alpha_id="a", health_score=0.0),
            WeightCandidate(alpha_id="b", health_score=0.0),
        ]
    )
    assert all(w == 0.0 for w in proposal.weights.values())
    assert "zero" in proposal.rationale
    assert proposal.requires_portfolio_approval is True


def test_weight_optimizer_decay_and_regime_penalize() -> None:
    opt = DynamicWeightOptimizer(max_weight=1.0)
    proposal = opt.propose(
        [
            WeightCandidate(alpha_id="aligned", health_score=80.0, regime_match=1.0),
            WeightCandidate(alpha_id="decaying", health_score=80.0, decay_multiplier=0.25),
            WeightCandidate(alpha_id="mismatch", health_score=80.0, regime_match=0.2),
        ]
    )
    assert proposal.weights["aligned"] > proposal.weights["decaying"]
    assert proposal.weights["aligned"] > proposal.weights["mismatch"]


def test_capital_reallocator_bounds_and_requires_approval() -> None:
    realloc = CapitalReallocator(max_move_frac=0.20)
    actions = realloc.propose(
        {"a": 0.5, "b": 0.5}, {"a": 0.9, "b": 0.1}, total_capital=100_000.0
    )
    by_id = {a.target_id: a for a in actions}
    assert set(by_id) == {"a", "b"}
    # +0.4 desired for a, clamped to +0.20 (bounded move)
    assert by_id["a"].detail["to_weight"] == 0.7
    assert by_id["a"].detail["capital_delta"] == 0.20 * 100_000.0
    assert by_id["b"].detail["to_weight"] == 0.3
    assert all(a.requires_portfolio_approval for a in actions)


def test_capital_reallocator_skips_unchanged() -> None:
    realloc = CapitalReallocator()
    actions = realloc.propose({"a": 0.5, "b": 0.5}, {"a": 0.5, "b": 0.5}, total_capital=1.0)
    assert actions == []
