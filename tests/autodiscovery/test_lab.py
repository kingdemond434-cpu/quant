"""Validation, memory/dedup, lifecycle, orchestrator cycle, reports, dashboard — on noise."""

from __future__ import annotations

import numpy as np
from tests.autodiscovery.conftest import noise_provider, noise_series

from app.dashboard import build_dashboard
from libs.autodiscovery.lifecycle import promote, segment_pass
from libs.autodiscovery.memory import CandidateStore, content_hash
from libs.autodiscovery.models import CandidateStatus, Family, Hypothesis
from libs.autodiscovery.orchestrator import AutoDiscoveryLab
from libs.autodiscovery.reports import (
    discovery_efficiency_report,
    pipeline_health_report,
    research_report,
)
from libs.autodiscovery.validation import validate
from libs.store.audit import verify_audit_chain
from libs.store.connection import Database
from libs.validation.economic_prior import MechanismType


def _hyp(symbol: str = "EURUSD", **params: float) -> Hypothesis:
    return Hypothesis(
        family=Family.TREND, subtype="ma_cross", symbol=symbol,
        params=params or {"fast": 20.0, "slow": 50.0}, mechanism=MechanismType.BEHAVIORAL,
        edge_source="trend", failure_modes=["chop"],
    )


def test_validate_rejects_pure_noise() -> None:
    rng = np.random.default_rng(1)
    rets = rng.normal(0.0, 0.01, size=1500)
    matrix = np.column_stack([rets, rng.normal(0.0, 0.01, size=1500)])
    verdict = validate(rets, hypothesis=_hyp(), n_trials=2, sharpe_estimates=np.array([0.0, 0.0]),
                       returns_matrix=matrix)
    assert verdict.survived is False
    assert verdict.rejection_reason  # names the failed gates
    assert set(verdict.gates) >= {"cpcv", "dsr", "pbo", "reality_check", "walk_forward",
                                  "capacity", "fragility", "economic_mechanism"}


def test_lifecycle_states() -> None:
    up = np.full(100, 0.001)        # consistently positive tail -> registry
    down = np.full(100, -0.001)     # negative tail -> shadow stage fails
    assert promote(up, validation_survived=False) is CandidateStatus.REJECTED
    assert promote(down, validation_survived=True) is CandidateStatus.SHADOW
    assert promote(up, validation_survived=True) is CandidateStatus.REGISTRY
    assert segment_pass(up, tail=0.1) is True


def test_memory_dedup_and_checkpoint(db: Database) -> None:
    store = CandidateStore(db)
    hyp = _hyp()
    assert not store.exists(hyp)
    from libs.autodiscovery.models import ValidationMetrics
    store.record(campaign_id="c1", hyp=hyp, status=CandidateStatus.REJECTED,
                 metrics=ValidationMetrics(), survived=False, rejection_reason="failed: dsr")
    assert store.exists(hyp)  # same content hash -> duplicate
    assert content_hash(hyp) == content_hash(_hyp())
    store.set_checkpoint("last_campaign", "c1")
    assert store.get_checkpoint("last_campaign") == "c1"


def test_orchestrator_cycle_archives_and_is_idempotent(db: Database) -> None:
    lab = AutoDiscoveryLab(db, noise_provider())
    first = lab.cycle(["EURUSD", "XAUUSD"])
    assert first.tested > 0
    assert first.survivors == 0          # pure noise -> zero survivors (honest)
    assert lab.store.total() == first.tested
    assert verify_audit_chain(db).ok

    second = lab.cycle(["EURUSD", "XAUUSD"])  # re-run: everything already tested
    assert second.tested == 0
    assert second.skipped_duplicate > 0
    assert lab.store.total() == first.tested  # no duplicate rows added


def test_reports_and_dashboard_section(db: Database) -> None:
    lab = AutoDiscoveryLab(db, noise_provider())
    lab.cycle(["EURUSD"])
    assert research_report(lab.store)["total_candidates"] > 0
    assert discovery_efficiency_report(lab.store)["survivors"] == 0
    assert "funnel" in pipeline_health_report(lab.store)
    section = build_dashboard(db).research_lab
    assert section["candidates_tested"] > 0
    assert section["survivors"] == 0
    assert "validation_funnel" in section


def test_append_only_candidates(db: Database) -> None:
    import pytest
    lab = AutoDiscoveryLab(db, noise_provider())
    lab.cycle(["EURUSD"])
    rec = lab.store.all()[0]
    with pytest.raises(Exception, match="append-only"), db.transaction() as conn:
        conn.execute("DELETE FROM research_candidates WHERE id = ?", (rec.id,))


def test_noise_series_helper_shape() -> None:
    assert len(noise_series(n=300)) == 300
