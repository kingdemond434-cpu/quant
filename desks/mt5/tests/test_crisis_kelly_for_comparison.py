"""The crisis-conditional Kelly, beside the blended one, for COMPARISON -- and it binds nothing.

`kelly_surface.surface` gave growth quantiles on a fixed heat grid over the whole mixture; the
crisis worlds sat inside it and "what would Kelly be if the crisis world is the one we are in"
had no number. `surface(..., subset=worlds.crisis)` runs the same arithmetic on the crisis worlds
alone and `crisis_block` puts f_opt / f_robust next to the blended surface's. These pin that the
subset is the same draws and fewer of them, that a thin crisis population is UNMEASURED with its
count, that the comparison names its sign, and -- the law -- that nothing sizes from it.
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pytest

_DESK = Path(__file__).resolve().parents[1]
_ROOT = _DESK.parent.parent
for _p in (str(_DESK), str(_DESK / "research"), str(_ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from libs.portfolio import kelly_surface as ks  # noqa: E402
from libs.portfolio.robust_elog import SleeveEvidence, WorldConfig, sample_worlds  # noqa: E402


def _evidence(n: int = 4, seed: int = 0) -> list[SleeveEvidence]:
    rng = np.random.default_rng(seed)
    return [SleeveEvidence(name=f"s{i}", daily_r=rng.normal(0.02, 0.3, 400), family=f"f{i}",
                           forward_days=100, live_days=20) for i in range(n)]


BOOK = {"s0": 0.06, "s1": 0.05, "s2": 0.05, "s3": 0.04}


def _worlds(crisis_prob: float, n_worlds: int = 64, seed: int = 2):
    ev = _evidence(seed=seed)
    return ev, sample_worlds(ev, WorldConfig(n_worlds=n_worlds, n_rows=64, seed=seed,
                                             crisis_prob=crisis_prob))


# ------------------------------------------------------------------------------------- subset
def test_a_subset_surface_is_the_same_draws_and_fewer_of_them() -> None:
    _, w = _worlds(0.5)
    whole = ks.surface(w, BOOK, tolerance=0.35, alpha=0.2)
    crisis = ks.surface(w, BOOK, tolerance=0.35, alpha=0.2, subset=w.crisis)
    idx = ks.surface(w, BOOK, tolerance=0.35, alpha=0.2, subset=np.flatnonzero(w.crisis))
    assert whole["n_worlds"] == w.n_worlds
    assert crisis["n_worlds"] == int(w.crisis.sum()) == idx["n_worlds"]
    assert [r["heat"] for r in crisis["rows"]] == [r["heat"] for r in whole["rows"]]
    assert crisis["rows"][3]["mean_growth"] == pytest.approx(idx["rows"][3]["mean_growth"])
    # Crisis worlds are worse by construction, so the crisis surface grows slower at the book.
    assert crisis["at_book"]["mean_growth"] < whole["at_book"]["mean_growth"]
    assert crisis["at_book"]["dd_p90"] >= whole["at_book"]["dd_median"]


def test_no_subset_is_exactly_the_old_surface() -> None:
    _, w = _worlds(0.3)
    a = ks.surface(w, BOOK, tolerance=0.35, alpha=0.2)
    b = ks.surface(w, BOOK, tolerance=0.35, alpha=0.2, subset=None)
    assert a["f_opt"] == b["f_opt"] and a["rows"] == b["rows"]


def test_an_empty_subset_says_so_rather_than_a_number() -> None:
    _, w = _worlds(0.0)
    s = ks.surface(w, BOOK, tolerance=0.35, alpha=0.2, subset=w.crisis)
    assert s["rows"] == [] and s["n_worlds"] == 0 and "empty world subset" in s["note"]


# ------------------------------------------------------------------------------ crisis block
def test_the_crisis_block_is_measured_beside_the_blended_surface_and_binds_nothing() -> None:
    _, w = _worlds(0.5)
    blended = ks.surface(w, BOOK, tolerance=0.35, alpha=0.2)
    c = ks.crisis_block(w, BOOK, blended, tolerance=0.35, alpha=0.2)
    assert c["status"] == ks.MEASURED and c["n_worlds"] == int(w.crisis.sum())
    assert c["binds"] is False
    for key in ("f_opt", "f_robust", "f_tail", "heat_opt", "heat_robust", "heat_tail_max"):
        assert key in c, key
    vs = c["vs_blended"]
    assert vs["f_opt_blended"] == blended["f_opt"]
    assert vs["f_opt_crisis_minus_blended"] == pytest.approx(c["f_opt"] - blended["f_opt"],
                                                             abs=1e-4)
    assert vs["crisis_kelly_higher_than_blended"] is (c["f_opt"] > blended["f_opt"] + 1e-9)
    assert vs["reading"]
    assert c["rows"] and len(c["rows"]) <= len(blended["rows"])


def test_a_thin_crisis_population_is_unmeasured_with_its_count() -> None:
    _, w = _worlds(0.05, n_worlds=40)
    n = int(w.crisis.sum())
    assert n < ks.MIN_SUBSET_WORLDS, "fixture: must be thin"
    c = ks.crisis_block(w, BOOK, None, tolerance=0.35, alpha=0.2)
    assert c["status"] == ks.UNMEASURED and c["n_worlds"] == n and c["binds"] is False
    assert str(ks.MIN_SUBSET_WORLDS) in c["why"]
    assert "f_opt" not in c


def test_no_blended_surface_still_measures_and_says_the_comparison_is_missing() -> None:
    _, w = _worlds(0.5)
    c = ks.crisis_block(w, BOOK, None, tolerance=0.35, alpha=0.2)
    assert c["status"] == ks.MEASURED
    assert c["vs_blended"]["status"] == ks.UNMEASURED


def test_a_population_without_a_crisis_mask_is_unmeasured() -> None:
    class Bare:
        names = tuple(BOOK)
        r = np.zeros((4, 8, 4), dtype=np.float32)

    c = ks.crisis_block(Bare(), BOOK, None, tolerance=0.35, alpha=0.2)
    assert c["status"] == ks.UNMEASURED and c["binds"] is False


# ------------------------------------------------------------------------------------ the law
def test_the_crisis_kelly_reaches_no_sizing_path() -> None:
    """A comparison is not a bar. The allocator publishes the block and nothing reads it for a
    size: `heat_policy.resolve` and the survival envelope take no argument from it, and the
    money path (`decision_core`) never opens it."""
    import inspect

    from mt5desk import decision_core

    from research import heat_policy, pf_allocator

    assert "crisis_block" not in inspect.getsource(heat_policy)
    assert "kelly_surface_crisis" not in inspect.getsource(decision_core)
    src = inspect.getsource(pf_allocator.run)
    assert '"kelly_surface_crisis"' in src, "the block must be published beside kelly_surface"
    # It is computed AFTER the heat is resolved and the book solved, so it cannot feed either.
    assert src.index("verdict = resolve(free.total_heat") < src.index("_crisis_block(")
    assert src.index("funded = {k: round(v, 6)") < src.index("_crisis_block(")
