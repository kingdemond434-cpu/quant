"""The anytime-valid science controller: an autonomous all-null stream that peeks, stops early
and launches follow-ups keeps its false-discovery rate inside the budget under LORD++ wealth,
while the same stream under a fixed level does not; the e-process and the confidence sequence
survive optional stopping; a verdict is the same whenever it is read; a lineage that has spent
its wealth is refused and told why, and a refused launch spends nothing."""
from __future__ import annotations

import math
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from libs.research import anytime_science as A  # noqa: E402


def test_all_null_autonomous_stream_holds_fdr_and_the_naive_rule_does_not() -> None:
    r = A.simulate_all_null_stream(lineages=5, launches=30, obs=80, reps=120, follow_ups=2,
                                   seed=20260922)
    assert r["fdr_lord"] <= A.ALPHA + 2.5 * r["se"], r
    assert r["fdr_naive"] >= 0.5, r          # same peeking, no accounting: the winners' curse


def test_all_null_stream_holds_fdr_under_heavy_tails() -> None:
    r = A.simulate_all_null_stream(lineages=5, launches=30, obs=80, reps=60, follow_ups=2,
                                   heavy_tails=True, seed=7)
    assert r["fdr_lord"] <= A.ALPHA + 2.5 * math.sqrt(A.ALPHA * (1 - A.ALPHA) / 60), r


def test_ville_bound_and_confidence_sequence_survive_a_cheating_stop() -> None:
    rng = np.random.default_rng(1)
    alpha, n_paths, cross, miss = 0.05, 1500, 0, 0
    for _ in range(n_paths):
        x = rng.standard_normal(200)
        if A.eprocess_path(x).max() >= 1.0 / alpha:
            cross += 1
        s, n = np.cumsum(x), np.arange(1, 201)
        k = int(np.argmax(s / n)) + 1          # stop where the sample mean looks best
        lo, hi = A.confidence_sequence(float(s[k - 1]), float(np.sum(x[:k] ** 2)), k,
                                       alpha=alpha, rho=10.0)
        if not lo <= 0.0 <= hi:
            miss += 1
    se = math.sqrt(alpha * (1 - alpha) / n_paths)
    assert cross / n_paths <= alpha + 3 * se
    assert miss / n_paths <= alpha + 3 * se
    ep = A.EProcess()
    ep.extend(x)
    assert abs(ep.e - A.eprocess_path(x)[-1]) < 1e-9        # incremental == vectorised


def test_verdict_is_the_same_whenever_it_is_read() -> None:
    rng = np.random.default_rng(3)
    x = rng.standard_normal(3000) + 0.15
    full = A.verdict_at_any_time(x)
    assert full.verdict == A.DISCOVERY and full.decided_at is not None
    k = full.decided_at
    early = A.verdict_at_any_time(x[:k - 1])
    assert early.verdict == A.UNDECIDED and early.decided_at is None
    at = A.verdict_at_any_time(x[:k])
    later = A.verdict_at_any_time(x[:k + 700])
    assert at.verdict == later.verdict == A.DISCOVERY
    assert at.decided_at == later.decided_at == k
    assert later.p_value <= A.ALPHA
    neg = A.verdict_at_any_time(rng.standard_normal(3000) - 0.2)
    assert neg.verdict == A.REFUTED and neg.interval[1] < 0.0
    assert A.verdict_at_any_time([]).verdict == A.UNMEASURED


def test_wealth_spends_replenishes_refuses_and_a_refusal_costs_nothing() -> None:
    lw = A.LineageWealth("fam")
    w0 = lw.wealth
    assert abs(w0 - A.ALPHA / 2) < 1e-12
    first = lw.launch()
    assert first.granted and first.slots == 1
    assert abs(first.alpha_granted - A.ALPHA / 2 * A.gamma_sequence()[0]) < 1e-12
    assert lw.wealth < w0
    assert lw.record(first, 0.5) is False
    second = lw.launch()
    assert lw.record(second, second.alpha_granted / 2) is True     # a discovery replenishes
    assert lw.earned > 0 and lw.next_alpha() > lw.alpha_at(2)
    slots, total = lw.grant_for(2.4)
    assert slots == 3 and total > lw.next_alpha()
    over = lw.launch(level=A.ALPHA)                                # the sealed gate's level
    assert over.state == A.BLOCKED and over.reason.startswith("OVERDRAW")
    t_before, spent_before = lw.t, lw.spent
    n = 0
    while True:
        launch = lw.launch()
        if not launch.granted:
            break
        lw.record(launch, 0.9)
        n += 1
        assert n < 500
    assert launch.reason.startswith("EXHAUSTED") and lw.t == t_before + n
    assert lw.spent >= spent_before and lw.wealth >= -1e-12       # never overdrawn by the rule
    assert lw.to_dict()["state"] == "EXHAUSTED" and lw.refused == 2
    ctrl = A.ScienceController()
    ctrl.launch("a")
    ctrl.launch("b", level=1.0)
    s = ctrl.summary()
    assert s["lineages"] == 2 and s["launches"] == 1 and s["blocked"] == 1


def test_indicator_e_values_bonferroni_and_gamma_sum_to_at_most_one() -> None:
    assert A.indicator_e_value([], 0.05) == 1.0
    assert A.indicator_e_value([True, False, False, False], 0.05) == 5.0
    assert A.indicator_e_value([False] * 10, 0.05) == 0.0
    assert A.bonferroni(0.001, 8.7) == 0.0087
    assert A.bonferroni(0.5, 1e6) == 1.0
    g = A.gamma_sequence(500)
    assert abs(g.sum() - 1.0) < 1e-12 and (g >= 0).all() and g[0] > g[1] > g[10]
