"""The composition re-optimised INSIDE the current state, published beside the global book.

`state_growth_curves` scores the global composition proportionally scaled on each state's own
worlds (`basis: scaled_candidate`): the evaluation is conditional, the composition is not.
`pf_allocator.state_book` re-solves the composition on the current state bucket alone -- one
extra solve, same bounds, same family cap, same resolved total heat -- and puts the global
book's score on those worlds beside it. These pin that it is measured, that it is a real book
inside the law (total exactly the resolved heat, every sleeve under its bound), that a thin or
missing state is UNMEASURED with the reason, and that NOTHING consumes it: the gateway still
sizes from `book`.
"""
from __future__ import annotations

import inspect
import sys
from pathlib import Path

import numpy as np
import pytest

_DESK = Path(__file__).resolve().parents[1]
_ROOT = _DESK.parent.parent
for _p in (str(_DESK), str(_DESK / "research"), str(_ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from libs.portfolio.allocator_proof import MIN_STATE_WORLDS, state_id  # noqa: E402
from libs.portfolio.robust_elog import (  # noqa: E402
    SleeveEvidence,
    WorldConfig,
    optimise,
    sample_worlds,
    score_book,
)

pa = pytest.importorskip("research.pf_allocator", reason="the allocator ships with the desk")


def _evidence(n: int = 6, days: int = 900, seed: int = 0) -> list[SleeveEvidence]:
    """Sleeves whose edge depends on the regime: half work in `bull` days, half in `bear`."""
    rng = np.random.default_rng(seed)
    labels = np.array(["bull" if x > 0 else "bear" for x in rng.standard_normal(days)])
    ev = []
    for i in range(n):
        edge = np.where(labels == ("bull" if i % 2 == 0 else "bear"), 0.10, -0.02)
        r = (rng.standard_normal(days) + edge) * (rng.random(days) < 0.3)
        ev.append(SleeveEvidence(name=f"s{i}", daily_r=r, family=f"f{i}", forward_days=60))
    return ev, tuple(labels)


def _worlds(seed: int = 3):
    ev, labels = _evidence()
    cfg = WorldConfig(n_worlds=96, n_rows=160, seed=seed, regime_labels=labels,
                      regime_probs=(("bull", 0.5), ("bear", 0.5)), regime_min_days=50)
    return ev, cfg, sample_worlds(ev, cfg)


BOUNDS = dict.fromkeys((f"s{i}" for i in range(6)), 0.06)
FAMILY = {f"s{i}": f"f{i}" for i in range(6)}


def test_the_current_state_gets_its_own_composition_beside_the_global_one() -> None:
    ev, cfg, w = _worlds()
    assert set(w.regimes) == {"bull", "bear"}, "fixture: regime conditioning must engage"
    glob = optimise(ev, hard_cap=0.45, target=0.20, cfg=cfg, worlds=w, max_per_sleeve=BOUNDS)
    state = state_id({}, "bull")
    sb = pa.state_book(ev, w, cfg, state=state, now_buckets={}, total_heat=0.20, bounds=BOUNDS,
                       family_of=FAMILY, warm_start=glob.heat, global_book=glob.heat)
    assert sb["status"] == "MEASURED" and sb["state"] == state
    assert sb["n_worlds"] >= MIN_STATE_WORLDS
    assert sb["consumed"] is False and "not consumed" in sb["note"]
    assert "reoptimised_in_state" in sb["basis"]
    # A real book inside the law: exactly the resolved heat, every sleeve under its bound.
    assert sb["total_heat"] == pytest.approx(0.20, abs=1e-6)
    assert sum(sb["book"].values()) == pytest.approx(0.20, abs=1e-5)
    assert all(v <= BOUNDS[k] + 1e-9 for k, v in sb["book"].items())
    # The state's own solve, warm-started from the global book, cannot score below it on the
    # state's own worlds: the ascent only accepts improving steps (distinct families, so the
    # family cap does not re-solve).
    assert sb["family_cap_bound"] is False
    assert sb["delta_robust"] >= -1e-9
    assert "delta_elogw_per_day" in sb and "global_book_on_state" in sb
    assert sb["reading"].endswith("reported, not sized")


def test_two_states_solve_to_different_compositions_each_better_on_its_own_worlds() -> None:
    """The point of the extra solve: w_i is state-dependent, and the scaled global composition
    cannot express that. Measured here -- bull and bear disagree about the book, and each
    state's own solve beats the global composition ON THAT STATE'S WORLDS."""
    ev, cfg, w = _worlds()
    glob = optimise(ev, hard_cap=0.45, target=0.20, cfg=cfg, worlds=w, max_per_sleeve=BOUNDS)
    books = {}
    for regime in ("bull", "bear"):
        sb = pa.state_book(ev, w, cfg, state=state_id({}, regime), now_buckets={},
                           total_heat=0.20, bounds=BOUNDS, family_of=FAMILY,
                           warm_start=glob.heat, global_book=glob.heat)
        assert sb["status"] == "MEASURED"
        assert sb["delta_elogw_per_day"] > 0.0, f"{regime}: the state solve bought nothing"
        assert sb["total_heat"] == pytest.approx(0.20, abs=1e-6)
        books[regime] = sb["book"]
    assert books["bull"] != books["bear"], (
        "both states solved to the same book -- the composition is not state-dependent and the "
        "extra solve is measuring nothing")


def test_the_global_score_on_the_state_matches_a_direct_scoring() -> None:
    from libs.portfolio.allocator_proof import _subworlds, buckets_from_worlds
    ev, cfg, w = _worlds()
    glob = optimise(ev, hard_cap=0.45, target=0.20, cfg=cfg, worlds=w, max_per_sleeve=BOUNDS)
    state = state_id({}, "bear")
    sb = pa.state_book(ev, w, cfg, state=state, now_buckets={}, total_heat=0.20, bounds=BOUNDS,
                       family_of=FAMILY, warm_start=glob.heat, global_book=glob.heat)
    idx = buckets_from_worlds(w, {}, min_worlds=MIN_STATE_WORLDS)[state]
    direct = score_book(ev, glob.heat, cfg=cfg, worlds=_subworlds(w, idx))
    assert sb["global_book_on_state"]["mean_log_growth"] == pytest.approx(
        direct["mean_log_growth"], abs=1e-9)
    assert sb["n_worlds"] == len(idx)


def test_a_state_without_a_bucket_or_without_worlds_is_unmeasured_with_the_reason() -> None:
    ev, cfg, w = _worlds()
    missing = pa.state_book(ev, w, cfg, state=state_id({"session": "asia"}, "bull"),
                            now_buckets={}, total_heat=0.20, bounds=BOUNDS, family_of=FAMILY,
                            warm_start=None, global_book=None)
    assert missing["status"] == "UNMEASURED" and "no bucket" in missing["why"]
    assert "book" not in missing and missing["consumed"] is False
    plain = sample_worlds(ev, WorldConfig(n_worlds=32, n_rows=64, seed=1))
    none = pa.state_book(ev, plain, cfg, state="regime=bull", now_buckets={}, total_heat=0.20,
                         bounds=BOUNDS, family_of=FAMILY, warm_start=None, global_book=None)
    assert none["status"] == "UNMEASURED" and "no regime-labelled worlds" in none["why"]
    empty = pa.state_book(ev, w, cfg, state="", now_buckets={}, total_heat=0.20, bounds=BOUNDS,
                          family_of=FAMILY, warm_start=None, global_book=None)
    assert empty["status"] == "UNMEASURED" and "no current state" in empty["why"]
    guard = pa.state_book(ev, w, cfg, state=state_id({}, "bull"), now_buckets={},
                          total_heat=0.0, bounds=BOUNDS, family_of=FAMILY, warm_start=None,
                          global_book=None)
    assert guard["status"] == "UNMEASURED" and "catastrophe" in guard["why"]


def test_bounds_that_cannot_fund_the_heat_refuse_rather_than_shrink_it() -> None:
    ev, cfg, w = _worlds()
    tiny = dict.fromkeys(BOUNDS, 0.01)                      # 6 x 1% cannot hold 20%
    sb = pa.state_book(ev, w, cfg, state=state_id({}, "bull"), now_buckets={}, total_heat=0.20,
                       bounds=tiny, family_of=FAMILY, warm_start=None, global_book=None)
    assert sb["status"] == "UNMEASURED" and "cannot fund" in sb["why"]
    assert "book" not in sb, "a book below the resolved heat is never published from here"


# --------------------------------------------------------------------------------- the law
def test_run_publishes_the_state_book_and_nothing_sizes_from_it() -> None:
    src = inspect.getsource(pa.run)
    i_funded = src.index("funded = {k: round(v, 6) for k, v in book.heat.items() if v > 1e-5}")
    i_state = src.index("sbook = state_book(ev, worlds, cfg, state=current_state")
    assert i_funded < i_state, "solved after the published book, from it"
    assert "total_heat=float(verdict.total_heat), bounds=ub, family_of=family_of" in src, (
        "the resolved heat and the book's own bounds, never a different law")
    assert '"state_book": sbook' in src
    assert "book = sbook" not in src and 'sbook["book"]' not in src, (
        "the state book must not replace the published book")
    assert 'funded = sbook' not in src

    from mt5desk import decision_core, gateway_config_fallback  # noqa: F401
    assert "state_book" not in inspect.getsource(decision_core), (
        "the money path does not read it; it reads heat.state and the certificate")
    assert "state_curves_basis" in src, "the scaled-candidate curves keep their stated basis"
