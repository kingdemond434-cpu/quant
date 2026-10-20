"""EVERY RANK OF A STEP-UP / STEP-DOWN FAMILY IS CHARGED min(ITS OWN CHARGE, BAR_N).

Principal's rule: the trial bar is N=5. Trials never inflate a bar, AND never deflate one below
N=5; no bar ever rises against LIVE.

Audit of 6de7b1a99 (2026-10-20): pinning the family size m to min(m, 5) charged rank 1 correctly
and every rank past the fifth NOTHING -- they reached raw alpha (t=1.64). On 50,000 pure-noise
p-values that BH passed 2,505, against 509 for Bonferroni at 5 (and 0 for LIVE BH over m).

The fix charges each rank min(its own LIVE charge, BAR_N):
    BH / BY : level_i = alpha * max(i / (m * c_m), 1 / BAR_N)
    Holm    : level_r = alpha / min(m - r + 1, BAR_N)
    e-BH    : crit_k  = min(m / (alpha * k), BAR_N / alpha)

So, for every site, two things are pinned here:
  1. NEVER BELOW N=5: on pure noise the pass count never exceeds Bonferroni at N=5.
  2. NEVER ABOVE LIVE: no threshold is stricter than LIVE's (written out below as LIVE had it).
"""
from __future__ import annotations

import math

import numpy as np
import pytest
from desks.mt5.research import causal_lab
from desks.mt5.research.macro_region import miners as macro_miners

from libs.research.trial_count_guard import BAR_N
from libs.validation import family_multiplicity as fm
from libs.validation import fdr
from libs.validation import forward_stats as fs

ALPHA = 0.05
NOISE = [(50_000, s) for s in range(3)] + [(5_000, s) for s in range(3)] + \
        [(400, s) for s in range(5)] + [(40, s) for s in range(5)]


def _noise(m: int, seed: int) -> np.ndarray:
    return np.random.default_rng(seed).uniform(size=m)


def _bonferroni_at_bar(p: np.ndarray, alpha: float = ALPHA) -> int:
    return int((np.asarray(p) <= alpha / BAR_N).sum())


# ----------------------------------------------------------------------------------------------
# LIVE (claude/llm-auto-upgrade-verify-gcjac3) written out: the bars no fix may tighten.
# ----------------------------------------------------------------------------------------------
def _live_step_up(p: np.ndarray, alpha: float, *, dependent: bool = False) -> np.ndarray:
    p = np.asarray(p, dtype="float64")
    m = p.size
    ranks = np.arange(1, m + 1)
    c_m = float(np.sum(1.0 / ranks)) if dependent else 1.0
    order = np.argsort(p, kind="stable")
    below = p[order] <= ranks / (m * c_m) * alpha
    k = int(np.nonzero(below)[0][-1]) + 1 if below.any() else 0
    rej = np.zeros(m, dtype=bool)
    rej[order[:k]] = True
    return rej


def _live_qvalues(p: np.ndarray) -> np.ndarray:
    m = p.size
    order = np.argsort(p, kind="stable")
    ranked = p[order]
    qs = np.minimum.accumulate((m / np.arange(m, 0, -1, dtype="float64")) * ranked[::-1])[::-1]
    out = np.empty(m)
    out[order] = np.clip(qs, 0.0, 1.0)
    return out


def _live_holm_alpha(m: int, rank: int, alpha: float = ALPHA) -> float:
    m, rank = max(1, int(m)), max(1, int(rank))
    return alpha / max(1, m - min(rank, m) + 1)


def _live_e_bh(e: np.ndarray, alpha: float) -> np.ndarray:
    e = np.maximum(np.where(np.isnan(e), 0.0, e), 0.0)
    m = e.size
    order = np.argsort(-e)
    meets = e[order] >= m / (alpha * np.arange(1, m + 1))
    k = int(np.max(np.where(meets)[0])) + 1 if meets.any() else 0
    rej = np.zeros(m, dtype=bool)
    rej[order[:k]] = True
    return rej


def _pinned_6de7b1a99_bh(p: np.ndarray, alpha: float) -> int:
    """The held head's form: family size min(m, BAR_N), rank capped at it -- ranks > 5 at alpha."""
    o = np.sort(p)
    m_bar = min(o.size, BAR_N)
    crit = alpha * np.minimum(np.arange(1, o.size + 1), m_bar) / m_bar
    b = o <= crit
    return int(np.nonzero(b)[0][-1]) + 1 if b.any() else 0


# ----------------------------------------------------------------------------------------------
# The sites, each as "rejections on p" so one battery covers them all.
# ----------------------------------------------------------------------------------------------
def _fdr_bh(p: np.ndarray, alpha: float) -> np.ndarray:
    return np.asarray(fdr.benjamini_hochberg(p, alpha=alpha).rejected)


def _fdr_by(p: np.ndarray, alpha: float) -> np.ndarray:
    return np.asarray(fdr.benjamini_yekutieli(p, alpha=alpha).rejected)


def _causal_lab(p: np.ndarray, alpha: float) -> np.ndarray:
    return np.asarray(causal_lab.bh_fdr(np.asarray(p), alpha)[0])


def _macro(p: np.ndarray, alpha: float) -> np.ndarray:
    return np.asarray(macro_miners.bh_fdr(list(map(float, p)), alpha))


def _step_up_by_level(level) -> object:
    def run(p: np.ndarray, alpha: float) -> np.ndarray:
        m = p.size
        order = np.argsort(p, kind="stable")
        lv = np.array([level(m, r, alpha) for r in range(1, m + 1)])
        below = p[order] <= lv
        k = int(np.nonzero(below)[0][-1]) + 1 if below.any() else 0
        rej = np.zeros(m, dtype=bool)
        rej[order[:k]] = True
        return rej
    return run


def _holm_step_down(p: np.ndarray, alpha: float) -> np.ndarray:
    m = p.size
    order = np.argsort(p, kind="stable")
    rej = np.zeros(m, dtype=bool)
    for r, idx in enumerate(order, 1):
        if p[idx] <= fs.holm_alpha(m, r, alpha=alpha):
            rej[idx] = True
        else:
            break
    return rej


_fm_bh = _step_up_by_level(lambda m, r, a: fm.bh_alpha(m, r, alpha=a))

SITES = {
    "fdr.benjamini_hochberg": (_fdr_bh, False),
    "fdr.benjamini_yekutieli": (_fdr_by, True),
    "causal_lab.bh_fdr": (_causal_lab, False),
    "macro_region.miners.bh_fdr": (_macro, False),
    "family_multiplicity.bh_alpha": (_fm_bh, False),
}


# ----------------------------------------------------------------------------------------------
# 1. NEVER BELOW N=5: pure noise never passes more than Bonferroni at the fixed N.
# ----------------------------------------------------------------------------------------------
@pytest.mark.parametrize("name", [*SITES, "forward_stats.holm_alpha"])
@pytest.mark.parametrize(("m", "seed"), NOISE)
def test_pure_noise_never_passes_more_than_bonferroni_at_bar_n(name: str, m: int,
                                                               seed: int) -> None:
    p = _noise(m, seed)
    run = _holm_step_down if name == "forward_stats.holm_alpha" else SITES[name][0]
    passed = int(run(p, ALPHA).sum())
    assert passed <= _bonferroni_at_bar(p), (name, m, seed, passed, _bonferroni_at_bar(p))


def test_the_auditors_50k_noise_probe_reproduces() -> None:
    """Seed 0, 50,000 uniform p-values, alpha 0.05: the held head passed 2,505; Bonferroni at 5
    passes 509; every fixed site passes no more than that; LIVE BH passes 0."""
    p = _noise(50_000, 0)
    bonf = _bonferroni_at_bar(p)
    assert bonf == 509
    assert _pinned_6de7b1a99_bh(p, ALPHA) == 2505
    assert int(_live_step_up(p, ALPHA).sum()) == 0
    for run, _dep in SITES.values():
        assert int(run(p, ALPHA).sum()) <= bonf
    assert int(_holm_step_down(p, ALPHA).sum()) <= bonf
    e = _null_evalues(50_000, 0)
    assert fdr.e_benjamini_hochberg(e, alpha=ALPHA).n_rejected <= int((e >= BAR_N / ALPHA).sum())


# ----------------------------------------------------------------------------------------------
# 2. NEVER ABOVE LIVE: no threshold is stricter than LIVE's, on noise and on real signal.
# ----------------------------------------------------------------------------------------------
def _mixtures() -> list[np.ndarray]:
    out = []
    for seed in range(12):
        rng = np.random.default_rng(100 + seed)
        m = int(rng.choice([1, 2, 3, 4, 5, 6, 12, 40, 400, 3000]))
        n_sig = int(rng.integers(0, m + 1))
        sig = rng.uniform(0, rng.choice([1e-5, 1e-3, 0.02]), size=n_sig)
        out.append(rng.permutation(np.concatenate([sig, rng.uniform(size=m - n_sig)])))
    return out


@pytest.mark.parametrize("name", list(SITES))
def test_no_site_rejects_less_than_live(name: str) -> None:
    run, dependent = SITES[name]
    for p in _mixtures():
        for a in (0.001, 0.05, 0.1):
            live = _live_step_up(p, a, dependent=dependent)
            fixed = run(p, a)
            assert not np.any(live & ~fixed), (name, p.size, a)


@pytest.mark.parametrize("m", [1, 2, 3, 4, 5, 6, 12, 50, 1000])
def test_bh_level_is_max_of_live_and_bonferroni_at_bar_n(m: int) -> None:
    for r in range(1, m + 1):
        want = max(ALPHA * r / m, ALPHA / BAR_N)
        assert math.isclose(fm.bh_alpha(m, r, alpha=ALPHA), want, rel_tol=1e-12)
        assert fm.bh_alpha(m, r, alpha=ALPHA) >= ALPHA * r / m       # never above LIVE's bar
    assert math.isclose(fm.bh_alpha(m, 1, alpha=ALPHA), ALPHA / min(m, BAR_N), rel_tol=1e-12)


@pytest.mark.parametrize("m", [1, 2, 3, 4, 5, 6, 12, 50, 1000])
def test_holm_level_is_charged_min_of_its_divisor_and_bar_n(m: int) -> None:
    for r in range(1, m + 1):
        got = fs.holm_alpha(m, r, alpha=ALPHA)
        assert math.isclose(got, ALPHA / min(m - r + 1, BAR_N), rel_tol=1e-12)
        assert got >= _live_holm_alpha(m, r)                          # never stricter than LIVE
        assert got <= max(_live_holm_alpha(m, r), ALPHA / BAR_N)      # never below N=5
    # the auditor's 12-cohort: rank 1 at alpha/5 (t 2.33), ranks 5..12 NOT at raw alpha (t 1.64)
    if m == 12:
        assert fs.holm_bar(12, 1) == 2.33
        assert all(fs.holm_bar(12, r) == 2.33 for r in range(1, 9))
        assert fs.holm_bar(12, 12) == 1.64


def test_causal_lab_qvalues_are_never_above_live_and_agree_with_rejections() -> None:
    for p in _mixtures():
        if p.size == 0:
            continue
        rej, q = causal_lab.bh_fdr(p, 0.05)
        assert np.all(q <= _live_qvalues(p) + 1e-12)
        assert np.all(q >= np.minimum(1.0, p))  # a q-value is at least the p it adjusts
        np.testing.assert_array_equal(rej, q <= 0.05)


def test_macro_region_matches_causal_lab() -> None:
    for p in _mixtures():
        np.testing.assert_array_equal(_macro(p, 0.05), _causal_lab(p, 0.05))


# ----------------------------------------------------------------------------------------------
# e-BH: crit_k = min(m / (alpha k), BAR_N / alpha).
# ----------------------------------------------------------------------------------------------
def _null_evalues(m: int, seed: int) -> np.ndarray:
    """Likelihood-ratio e-values under the null: E[e] = 1 exactly."""
    z = np.random.default_rng(seed).standard_normal(m)
    lam = 2.0
    return np.exp(lam * z - lam * lam / 2.0)


@pytest.mark.parametrize(("m", "seed"), NOISE)
def test_e_bh_on_null_evalues_never_passes_more_than_bonferroni_at_bar_n(m: int,
                                                                         seed: int) -> None:
    e = _null_evalues(m, seed)
    got = fdr.e_benjamini_hochberg(e, alpha=ALPHA).n_rejected
    assert got <= int((e >= BAR_N / ALPHA).sum())


def test_e_bh_never_rejects_less_than_live() -> None:
    for seed in range(12):
        rng = np.random.default_rng(300 + seed)
        m = int(rng.choice([1, 3, 5, 6, 12, 200, 2000]))
        e = np.exp(rng.normal(rng.choice([0.0, 2.0, 5.0]), 2.0, size=m))
        for a in (0.01, 0.05, 0.1):
            live = _live_e_bh(e, a)
            fixed = np.asarray(fdr.e_benjamini_hochberg(e, alpha=a).rejected)
            assert not np.any(live & ~fixed)


def test_e_bh_deep_ranks_are_charged_bar_n_not_one() -> None:
    """m=1000 with 900 e-values of 30: LIVE needs 1000/(0.05*900)=22.2, which 30 clears, so LIVE
    rejects all 900. The held head's crit at k>=5 was 1/alpha=20 -- it would have rejected ten
    e-values of 21 out of 1000. The fix charges BAR_N: crit_k = min(m/(alpha k), 100)."""
    e = np.concatenate([np.full(900, 30.0), np.ones(100)])
    assert fdr.e_benjamini_hochberg(e, alpha=ALPHA).n_rejected == 900       # LIVE's verdict kept
    weak = np.concatenate([np.full(10, 21.0), np.ones(990)])
    assert fdr.e_benjamini_hochberg(weak, alpha=ALPHA).n_rejected == 0      # below BAR_N/alpha
    strong = np.concatenate([np.full(10, 101.0), np.ones(990)])
    assert fdr.e_benjamini_hochberg(strong, alpha=ALPHA).n_rejected == 10   # LIVE: needs 2000
