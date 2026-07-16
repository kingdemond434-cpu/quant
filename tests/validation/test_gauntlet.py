"""Tests for the validation gauntlet, ledger integration, and report generation."""

from __future__ import annotations

import json
from collections.abc import Iterator
from pathlib import Path

import pytest
from migrations import MIGRATIONS
from tests.validation.conftest import complete_prior, edge_matrix, strong_returns

from libs.store.connection import Database
from libs.store.migrations import run_migrations
from libs.store.trials import TrialsLedger
from libs.validation.gauntlet import CandidateEvaluation, Gauntlet
from libs.validation.report import generate_validation_report


def _candidate(**overrides: object) -> CandidateEvaluation:
    defaults: dict[str, object] = {
        "candidate_id": "cand_1",
        "hypothesis_id": "hyp_1",
        "family": "session",
        "returns": strong_returns(n=400, seed=1),
        "strategy_matrix": edge_matrix(t=300, n=10, seed=0),
        "gross_pnls": [10.0] * 20,
        "base_costs": [1.0] * 20,
        "economic_prior": complete_prior(),
        "lockbox_returns": strong_returns(n=150, seed=9),
        "n_trials_override": 5,
    }
    defaults.update(overrides)
    return CandidateEvaluation(**defaults)  # type: ignore[arg-type]


@pytest.fixture
def ledger(tmp_path: Path) -> Iterator[TrialsLedger]:
    db = Database(tmp_path / "sor.sqlite")
    run_migrations(db, MIGRATIONS)
    yield TrialsLedger(db)
    db.close()


def test_strong_candidate_passes() -> None:
    result = Gauntlet().run(_candidate())
    assert result.passed
    assert result.verdict == "PASS"
    names = [s.name for s in result.stages]
    assert names == [
        "economic_prior", "in_sample_screen", "deflated_sharpe", "pbo",
        "reality_check_spa", "stress_costs", "lockbox",
    ]
    assert all(s.passed for s in result.stages)


def test_incomplete_prior_short_circuits() -> None:
    prior = complete_prior()
    del prior["why_decay"]
    result = Gauntlet().run(_candidate(economic_prior=prior))
    assert not result.passed
    assert result.verdict == "FAIL"
    assert len(result.stages) == 1
    assert result.stages[0].name == "economic_prior"


def test_fails_at_stress_costs() -> None:
    result = Gauntlet().run(_candidate(gross_pnls=[10.0] * 10, base_costs=[20.0] * 10))
    assert not result.passed
    assert result.stages[-1].name == "stress_costs"
    assert not result.stages[-1].passed


def test_ledger_integration_inflates_trial_count(ledger: TrialsLedger) -> None:
    gauntlet = Gauntlet(ledger=ledger, trials_multiplier=7.0)
    result = gauntlet.run(_candidate(n_trials_override=None))
    assert ledger.count() == 1
    assert result.n_trials == 7  # ceil(1 * 7)


def test_report_generation(tmp_path: Path) -> None:
    result = Gauntlet().run(_candidate())
    paths = generate_validation_report(result, tmp_path / "report")
    assert paths["json"].is_file()
    assert paths["html"].is_file()
    payload = json.loads(paths["json"].read_text(encoding="utf-8"))
    assert payload["verdict"] == "PASS"
    assert "PASS" in paths["html"].read_text(encoding="utf-8")
