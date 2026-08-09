"""SIX MODULES THAT EXISTED, WORKED, AND WERE REACHED BY NOTHING.

I called wiring them "guesswork I'd rather not do". That was an excuse: reading a module tells you
what it is for, and every one of these had an obvious home. What they had in common is that each
answers a question the desk was otherwise not asking at all --

  baselines      does the candidate even beat buy-and-hold? The gauntlet never asked.
  edge_gate      is the gross target EARNED from forward evidence, or typed by hand?
  microstructure one definition of depth imbalance, or two that drift?
  stationarity   is the spread a mean-reverting series, or a random walk that came back?
  manufacture    what should we BUILD from data we already hold?
  emergence      have independent weak signals converged? (Charter §23's own promotion rule.)

These tests pin each wiring at the seam where it changes an outcome, not merely that an import
exists -- an import is satisfied by a module nobody calls, which is the defect being fixed.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

# ------------------------------------------------------------------- baselines

def test_a_candidate_that_loses_to_buy_and_hold_fails_the_gate() -> None:
    """A strategy can clear DSR, SPA and CPCV and still lose to holding BTC, in which case it is
    complexity with no reason to exist. On a directional crypto book that is the LIKELY outcome."""
    from libs.validation.baselines import baseline_scorecard
    rng = np.random.default_rng(0)
    bh = rng.normal(0.002, 0.01, 500)
    weak = rng.normal(0.0002, 0.01, 500)
    assert not baseline_scorecard(weak, buy_hold_returns=bh).beats_all


def test_the_baseline_gate_is_skipped_not_passed_when_no_benchmark_is_supplied() -> None:
    """A gate that defaults to True when nobody supplied its evidence is a gate that has been
    removed. The merged validate() goes one better than leaving it absent: the verdict RECORDS
    that nobody looked (`unmeasured`), so a green artifact cannot silently stand in for a
    measurement. Behavioural, not source-text -- the phrasing changed at the 2026-08-04 merge
    and a phrase probe would have pinned prose rather than conduct."""
    from types import SimpleNamespace

    import numpy as np

    from libs.autodiscovery.validation import validate
    rng = np.random.default_rng(0)
    m = rng.normal(0, 0.01, (400, 3))
    hyp = SimpleNamespace(failure_modes=["chop"])
    v = validate(m[:, 0], hypothesis=hyp, periods_per_year=365.0, n_trials=3,
                 sharpe_estimates=np.zeros(3), returns_matrix=m)
    assert "beats_baselines" in v.unmeasured


# ------------------------------------------------------------------- edge_gate

def test_gross_is_the_floor_until_forward_evidence_exists() -> None:
    """THE SEAM THAT MATTERS. Unwired, every allocation ran at a hand-picked gross regardless of
    whether anything had proven itself live."""
    from libs.portfolio.capacity_allocation import allocate_with_capacity
    rng = np.random.default_rng(1)
    d = pd.DataFrame({"a": rng.normal(0, 1, 400), "b": rng.normal(0, 1, 400)})
    cap = {"a": 1.0, "b": 1.0}
    sh = {"a": 1.0, "b": 1.0}
    unproven = allocate_with_capacity(d, sh, cap, fwd_sharpe=None, fwd_days=0).gross
    proven = allocate_with_capacity(d, sh, cap, fwd_sharpe=1.2, fwd_days=90).gross
    assert proven > unproven, "90 days of forward Sharpe 1.2 must buy more gross than nothing"


def test_an_explicit_gross_target_still_wins() -> None:
    """A caller stress-testing a book must be able to ask 'what if'."""
    from libs.portfolio.capacity_allocation import allocate_with_capacity
    d = pd.DataFrame({"a": np.random.default_rng(2).normal(0, 1, 300),
                      "b": np.random.default_rng(3).normal(0, 1, 300)})
    r = allocate_with_capacity(d, {"a": 1.0, "b": 1.0}, {"a": 1.0, "b": 1.0},
                               gross_target=0.5, fwd_sharpe=3.0, fwd_days=365)
    assert r.gross <= 0.5 + 1e-9


# -------------------------------------------------------------- microstructure

def test_depth_imbalance_has_exactly_one_definition() -> None:
    """Two definitions drift, and the one that gets traded is whichever the caller imported."""
    import inspect

    import scripts.calibrate_impact as C
    assert "book_imbalance" in inspect.getsource(C.main)
    from libs.research.microstructure import book_imbalance
    assert book_imbalance(np.array([2.0]), np.array([1.0]))[0] == pytest.approx(1 / 3)


def test_an_empty_book_imbalance_is_zero_not_nan() -> None:
    from libs.research.microstructure import book_imbalance
    assert book_imbalance(np.array([0.0]), np.array([0.0]))[0] == 0.0


# --------------------------------------------------------------- stationarity

def test_a_missing_stats_backend_skips_rather_than_passes(monkeypatch) -> None:
    """The backend is an OPTIONAL dependency. A gate that returns True when its backend is absent
    has been deleted by a packaging decision. Behavioural since the 2026-08-04 merge: the absent
    backend must land the gate in `unmeasured` -- never in `gates` as passed, never silent."""
    from types import SimpleNamespace

    import numpy as np

    import libs.research.stationarity as st
    from libs.autodiscovery.validation import validate

    def _raise(_arr):
        raise st.StatsBackendMissing("backend deliberately absent for this test")

    monkeypatch.setattr(st, "adf_pvalue", _raise)
    rng = np.random.default_rng(1)
    m = rng.normal(0, 0.01, (400, 3))
    hyp = SimpleNamespace(failure_modes=["chop"], requires_stationarity=True)
    v = validate(m[:, 0], hypothesis=hyp, periods_per_year=365.0, n_trials=3,
                 sharpe_estimates=np.zeros(3), returns_matrix=m)
    assert "stationary" not in v.gates
    assert "stationary" in v.unmeasured


# ---------------------------------------------------------------- manufacture

def test_the_manufacture_queue_ranks_by_moat_per_engineer_day() -> None:
    """AND THE KEY NAME WAS MINE TO GET WRONG. I read `score`, which score_spec does not return,
    so every entry ranked 0.00 -- a column of zeros presented as a ranking. Reading the API rather
    than guessing at it is the whole fix."""
    from libs.hypmax.manufacture import propose_from_owned, score_spec
    scored = [score_spec(sp) for sp in propose_from_owned()]
    assert scored, "propose_from_owned must offer something buildable from data already held"
    assert all("moat_per_day" in s for s in scored)
    assert all("score" not in s for s in scored), "the key I guessed at does not exist"
    assert max(float(s["moat_per_day"]) for s in scored) > 0


def test_time_accruing_specs_carry_their_urgency() -> None:
    """A series that only grows by waiting cannot be bought later at any price."""
    from libs.hypmax.manufacture import propose_from_owned, score_spec
    accruing = [score_spec(sp) for sp in propose_from_owned() if sp.time_accruing]
    assert accruing
    assert all("urgency" in s for s in accruing)


# ------------------------------------------------------------------ emergence

def test_the_weak_signal_registry_is_actually_read() -> None:
    """Its own docstring called being unread 'a genuine miss'. Charter §23's promotion rule was
    checked by whoever happened to remember, which is the same as not being checked."""
    import scripts.cluster_weak_signals as W
    obs = W.parse(W.REGISTRY)
    assert len(obs) >= 3, "the registry holds WS-001..WS-005; parsing must find them"
    assert all(o.tags for o in obs)


def test_clustering_does_not_fire_on_grammar() -> None:
    """THE FIRST RUN CLUSTERED ON 'when' AND 'desk' -- filler that appears in every entry and
    converges by construction. A convergence detector that fires on grammar produces exactly the
    confident-looking output nobody checks."""
    import scripts.cluster_weak_signals as W
    obs = W.parse(W.REGISTRY)
    tags = {t for o in obs for t in o.tags}
    for filler in ("when", "desk", "the", "with", "that"):
        assert filler not in tags, f"{filler!r} is filler and must not be a clustering tag"


def test_convergence_requires_independent_paths() -> None:
    """Charter §23's bar is TWO independent paths. One observer repeating themselves is not
    convergence, and cluster strength is super-additive precisely to encode that difference."""
    from libs.hypmax.emergence import Observation, cluster_weak_signals
    one = [Observation(text="x", tags=("liquidity",), source="s1")]
    two = [Observation(text="x", tags=("liquidity",), source="s1"),
           Observation(text="y", tags=("liquidity",), source="s2")]
    assert cluster_weak_signals(one, min_size=2) == []
    assert len(cluster_weak_signals(two, min_size=2)) == 1
