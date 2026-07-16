"""End-to-end SignalEngine: the exclusive BUY/SELL/FLAT gate, audit, and monitoring."""

from __future__ import annotations

from tests.signal_engine.conftest import (
    full_governance,
    make_alpha,
    make_state,
    strong_obs,
)

from libs.signal_engine.audit import SignalAudit
from libs.signal_engine.engine import SignalEngine, SymbolObservation
from libs.signal_engine.governance import GovernanceVerdict
from libs.signal_engine.models import Direction
from libs.signal_engine.monitoring import build_monitoring_snapshot
from libs.store.audit import verify_audit_chain
from libs.store.connection import Database


def test_engine_approves_strong_signal() -> None:
    result = SignalEngine().evaluate([strong_obs()])
    assert len(result.approved) == 1
    pkg = result.approved[0]
    assert pkg.direction is Direction.BUY
    assert pkg.symbol == "EURUSD"
    assert pkg.quality_score > 80.0
    assert pkg.confidence > 0.75
    assert pkg.expected_value > 0.0
    assert result.rejected == {}


def test_engine_flat_on_no_governed_alpha() -> None:
    obs = SymbolObservation(
        signals=[make_alpha(governance_passed=False)], state=make_state()
    )
    result = SignalEngine().evaluate([obs])
    assert result.approved == []
    assert "governed" in result.rejected["EURUSD"]


def test_engine_flat_on_governance_verdict_failure() -> None:
    obs = strong_obs(governance_verdict=GovernanceVerdict())  # all gates fail
    result = SignalEngine().evaluate([obs])
    assert result.approved == []
    assert result.rejected["EURUSD"] == "governance gate failed"


def test_engine_passes_with_full_governance_verdict() -> None:
    obs = strong_obs(governance_verdict=full_governance())
    result = SignalEngine().evaluate([obs])
    assert len(result.approved) == 1


def test_engine_flat_on_direction_cancellation() -> None:
    buy = make_alpha("b", direction=Direction.BUY, strength=0.8, health_score=90.0)
    sell = make_alpha("s", direction=Direction.SELL, strength=0.8, health_score=90.0)
    obs = SymbolObservation(signals=[buy, sell], state=make_state())
    result = SignalEngine().evaluate([obs])
    assert result.rejected["EURUSD"] == "no net direction"


def test_engine_flat_on_weak_signal() -> None:
    weak = make_alpha(
        "weak", strength=0.2, sharpe=0.2, profit_factor=1.05, health_score=55.0,
        regime_affinity={}, win_rate=0.5, avg_win=0.005, avg_loss=0.005,
    )
    result = SignalEngine().evaluate([SymbolObservation(signals=[weak], state=make_state())])
    assert result.approved == []
    assert "EURUSD" in result.rejected


def test_engine_ranks_multiple_symbols() -> None:
    strong = strong_obs()
    weaker = strong_obs(
        signals=[make_alpha("t2", sharpe=1.55, profit_factor=1.55)],
        state=make_state(symbol="GBPUSD"),
    )
    result = SignalEngine().evaluate([weaker, strong])
    # both may approve; the engine evaluates each symbol independently
    assert {p.symbol for p in result.approved} <= {"EURUSD", "GBPUSD"}
    assert len(result.approved) >= 1


def test_engine_audits_decisions_immutably(db: Database) -> None:
    engine = SignalEngine(audit=SignalAudit(db))
    flat = SymbolObservation(signals=[make_alpha(governance_passed=False)], state=make_state())
    result = engine.evaluate([strong_obs(), flat])
    chain = verify_audit_chain(db)
    assert chain.ok
    assert chain.length == len(result.approved) + len(result.rejected)


def test_regime_confidence_zero_when_no_weight() -> None:
    # Defensive zero branch: no weighted alphas -> zero regime confidence.
    assert SignalEngine()._regime_confidence([], {}, make_state()) == 0.0


def test_monitoring_snapshot_aggregates() -> None:
    engine = SignalEngine()
    obs = strong_obs()
    candidate = engine._build_candidate(obs)
    result = engine.evaluate([obs])
    from libs.signal_engine.models import TradeCandidate

    assert isinstance(candidate, TradeCandidate)
    snap = build_monitoring_snapshot([candidate], result)
    assert snap.metrics["n_candidates"] == 1
    assert snap.metrics["n_approved"] == 1
    assert snap.metrics["avg_quality"] > 80.0
    assert "EURUSD" in snap.metrics["alpha_contributions"]
