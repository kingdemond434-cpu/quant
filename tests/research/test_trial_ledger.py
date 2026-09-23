"""The effective-trial ledger: clone families collapse, distinct mechanisms count in full, a
declared width is charged, identities are not parameters, and the libs gauntlet's deflated
Sharpe charge follows the family in both directions."""
from __future__ import annotations

import sys
from pathlib import Path

from migrations import MIGRATIONS
from tests.validation.conftest import complete_prior, edge_matrix, strong_returns

from libs.store.connection import Database
from libs.store.migrations import run_migrations
from libs.store.trials import TrialsLedger
from libs.validation.gauntlet import CandidateEvaluation, Gauntlet

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from libs.research import trial_ledger as T  # noqa: E402


def _ema(i: int, fast: int, slow: int, family: str = "ema_cross") -> T.Trial:
    return T.Trial(f"e{i}", family, {"mechanism": "trend", "symbol": "EURUSD", "chart": "H1"},
                   {"fast": fast, "slow": slow})


def test_parameter_neighbours_are_one_search_and_far_settings_are_not() -> None:
    clones = [_ema(i, f, s) for i, (f, s) in enumerate([(19, 57), (20, 58), (21, 59)])]
    c = T.census(clones)
    assert c.n_raw == 3 and 1.0 <= c.n_effective < 1.3, c.to_dict()
    assert c.families["ema_cross"].clone_pairs == 2      # (19,57)~(20,58), (20,58)~(21,59)
    far = [_ema(i, f, s) for i, (f, s) in enumerate([(5, 20), (50, 200), (200, 800)])]
    assert T.census(far).n_effective > 1.8
    assert T.similarity(clones[0], clones[1]) > T.similarity(far[0], far[2])
    assert T.similarity(clones[0], clones[0]) == 1.0


def test_distinct_mechanisms_count_in_full_and_a_declared_width_is_charged() -> None:
    mix = [T.Trial("a", "carry", {"mechanism": "carry"}), T.Trial("b", "breakout",
                                                                  {"mechanism": "breakout"}),
           T.Trial("c", "gap", {"mechanism": "gap"})]
    c = T.census(mix)
    assert c.n_raw == 3 and c.n_effective == 3.0 and c.inflation == 1.0
    lone = T.census([T.Trial("w", "sweep", {"mechanism": "x"}, {"k": 5},
                             declared_width=1_000_000)])
    assert lone.n_effective == 1_000_000.0            # one winner of a million is a million
    three = [T.Trial(f"w{i}", "sweep", {"mechanism": "x"}, {"k": 5 + i},
                     declared_width=1_000_000) for i in range(3)]
    f = T.census(three).families["sweep"]
    assert 1.0 <= f.n_effective_members < 1.5
    assert abs(f.n_effective - 1_000_000 * f.n_effective_members / 3) < 1e-6
    assert T.census([]).basis == T.UNMEASURED and T.census([]).n_effective == 0.0


def test_records_of_any_shape_are_priced_and_identities_are_not_parameters() -> None:
    rows = [{"id": f"cand_{i}", "family": "lead_lag", "symbol": "USDJPY", "chart": "H1",
             "params_json": f'{{"conditioner": "cross_asset", "lookback": {20 + i}}}',
             "mechanism": "cross_market_lead"} for i in range(4)]
    n = T.effective_count_of_records(rows)
    assert 1.0 <= n < 1.6
    ledgerish = [{"hypothesis_id": f"h{i}", "family": "session", "method": "gauntlet",
                  "params": {"candidate_id": f"c{i}"}} for i in range(3)]
    assert T.effective_count_of_records(ledgerish) == 1.0     # nothing distinguishes them
    genome_rows = [{"family": "session", "genome": {"mechanism": "m", "geography": g}}
                   for g in ("JP", "US", "EU")]
    assert T.effective_count_of_records(genome_rows) > 1.5
    t = T.trial_from_record({"family": "x", "declared_width": "12"})
    assert t.declared_width == 12 and t.trial_id == "trial_0"


def _candidate(i: int, family: str, **extra: object) -> CandidateEvaluation:
    return CandidateEvaluation(
        candidate_id=f"cand_{i}", hypothesis_id=f"hyp_{i}", family=family,
        returns=strong_returns(n=400, seed=1), strategy_matrix=edge_matrix(t=300, n=10, seed=0),
        gross_pnls=[10.0] * 20, base_costs=[1.0] * 20, economic_prior=complete_prior(),
        lockbox_returns=strong_returns(n=150, seed=9), n_trials_override=None,
        extra=dict(extra))


def test_the_gauntlet_charge_follows_the_family_in_both_directions(tmp_path: Path) -> None:
    db = Database(tmp_path / "sor.sqlite")
    run_migrations(db, MIGRATIONS)
    try:
        ledger = TrialsLedger(db)
        g = Gauntlet(ledger=ledger, trials_multiplier=7.0)
        for i in range(3):
            clone = g.run(_candidate(i, "ema_cross", genome={"mechanism": "trend"},
                                     params={"fast": 19 + i, "slow": 57 + i}))
        assert ledger.count() == 3 and clone.n_trials_raw == 3
        assert 1.0 <= clone.n_trials_effective < 1.6 and clone.n_trials < 21   # falls
        db2 = Database(tmp_path / "sor2.sqlite")
        run_migrations(db2, MIGRATIONS)
        try:
            g2 = Gauntlet(ledger=TrialsLedger(db2), trials_multiplier=7.0)
            for i, fam in enumerate(("carry", "breakout", "gap")):
                real = g2.run(_candidate(i, fam))
            assert real.n_trials_raw == 3 and real.n_trials_effective == 3.0
            assert real.n_trials == 21                                          # in full
            wide = g2.run(_candidate(9, "sweep", search_width=1000))
            assert wide.n_trials_effective >= 1000.0 and wide.n_trials >= 7000   # rises
            assert [s.name for s in wide.stages][:3] == ["economic_prior", "in_sample_screen",
                                                          "deflated_sharpe"]
        finally:
            db2.close()
    finally:
        db.close()
