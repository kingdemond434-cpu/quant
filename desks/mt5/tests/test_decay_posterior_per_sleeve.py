"""The drift monitor's hazard is each sleeve's OWN decay probability, capped at the blanket.

`robust_elog` decayed every sleeve's edge in 30% of worlds -- one constant, whatever the drift
monitor had measured -- and the only per-sleeve decay input was a post-hoc shrink of the mean
(`apply_hazard_shrink`). `pf_allocator.apply_decay_posterior` now writes `hazard_by_sleeve` onto
each sleeve as `decay_prob_i = min(hazard, blanket)`, so a sleeve the monitor calls healthy stops
paying the blanket and earns MORE heat, and a sleeve it calls breaking is charged exactly the
blanket -- never more than every sleeve was charged before. The mean-shrink path stays available
behind `HAZARD_MODE = "mean_shrink"` and its own rail. These pin the cap, the default, the
single-charge rule, the missed-growth line, and the law: no sleeve sized below what it got.
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

from libs.portfolio import rails  # noqa: E402
from libs.portfolio.robust_elog import (  # noqa: E402
    SleeveEvidence,
    WorldConfig,
    optimise,
    sample_worlds,
)

pa = pytest.importorskip("research.pf_allocator", reason="the allocator ships with the desk")
mg = pytest.importorskip("research.missed_growth", reason="the ledger ships with the desk")

BLANKET = WorldConfig().decay_prob


def _sleeve(name: str, mu: float, seed: int, n: int = 700, act: float = 0.25) -> SleeveEvidence:
    rng = np.random.default_rng(seed)
    r = (rng.standard_normal(n) + mu / act) * (rng.random(n) < act)
    return SleeveEvidence(name=name, daily_r=r, symbol=name.split("_")[0], family="f",
                          forward_days=60)


# ---------------------------------------------------------------------- the default and the cap
def test_the_decay_posterior_is_the_default_and_the_mean_shrink_is_still_available() -> None:
    assert pa.HAZARD_MODE == "decay_posterior"
    assert callable(pa.apply_hazard_shrink), "the previous path must remain callable"
    src = inspect.getsource(pa.run)
    assert 'if HAZARD_MODE == "mean_shrink":' in src
    assert "hazard_meta = apply_hazard_shrink(ev, _haz)" in src
    assert "decay_meta = apply_decay_posterior(ev, _haz, _blanket)" in src
    assert '"decay_posterior": decay_meta' in src, "the artifact must carry the block"
    assert '"decay": {' in src, "both values belong on the evidence block"


def test_apply_decay_posterior_writes_the_hazard_capped_at_the_blanket() -> None:
    ev = [_sleeve("healthy_a", 0.05, 1), _sleeve("breaking_b", 0.05, 2), _sleeve("unknown_c",
                                                                                   0.05, 3)]
    meta = pa.apply_decay_posterior(ev, {"healthy_a": 0.05, "breaking_b": 0.90}, BLANKET)
    by = {e.name: e for e in ev}
    assert by["healthy_a"].decay_prob_i == pytest.approx(0.05)
    assert by["breaking_b"].decay_prob_i == pytest.approx(BLANKET), "never above the blanket"
    assert by["unknown_c"].decay_prob_i is None, "no hazard: the blanket, exactly as before"
    assert meta["mode"] == "decay_posterior" and meta["blanket"] == BLANKET
    assert meta["n_from_hazard"] == 2 and meta["n_blanket"] == 1
    assert meta["by_sleeve"]["healthy_a"] == {"hazard": 0.05, "decay_prob_i": 0.05,
                                              "relief_vs_blanket": pytest.approx(BLANKET - 0.05)}
    assert meta["by_sleeve"]["breaking_b"]["relief_vs_blanket"] == 0.0
    assert "charged above the blanket" in meta["rule"] and "only relieve" in meta["rule"]


def test_a_breaking_sleeve_is_drawn_exactly_as_the_blanket_draws_it() -> None:
    """The cap in arithmetic: a hazard of 0.9 produces the SAME world population the blanket
    does, so the change cannot deepen any sleeve's haircut."""
    base = [_sleeve("a", 0.05, 1), _sleeve("b", 0.05, 2)]
    tilted = [_sleeve("a", 0.05, 1), _sleeve("b", 0.05, 2)]
    pa.apply_decay_posterior(tilted, {"a": 0.9, "b": 0.75}, BLANKET)
    cfg = WorldConfig(n_worlds=48, n_rows=128, seed=3)
    np.testing.assert_array_equal(sample_worlds(base, cfg).r, sample_worlds(tilted, cfg).r)


# ---------------------------------------------------------------------------------- the law
def test_a_healthy_sleeve_earns_at_least_what_it_earned_and_the_book_no_less() -> None:
    base = [_sleeve("healthy", 0.06, 11), _sleeve("other", 0.05, 12)]
    relieved = [_sleeve("healthy", 0.06, 11), _sleeve("other", 0.05, 12)]
    pa.apply_decay_posterior(relieved, {"healthy": 0.02}, BLANKET)
    cfg = WorldConfig(n_worlds=64, n_rows=128, seed=3)
    before = optimise(base, hard_cap=0.45, target=None, cfg=cfg)
    after = optimise(relieved, hard_cap=0.45, target=None, cfg=cfg)
    assert before.total_heat > 0.01, "fixture: the book must want heat"
    assert after.heat["healthy"] >= before.heat["healthy"] - 1e-6
    assert after.total_heat >= before.total_heat - 1e-6
    # The floor and the bounds are untouched: a mandated 20% under 15% per-sleeve bounds is
    # still exactly 20%, and no sleeve is above its bound.
    mandated = optimise(relieved, hard_cap=0.45, target=0.20, cfg=cfg, max_per_sleeve=0.15)
    assert mandated.total_heat == pytest.approx(0.20, abs=1e-6)
    assert all(v <= 0.15 + 1e-9 for v in mandated.heat.values())


def test_the_mean_shrink_path_is_the_one_that_could_lower_heat_and_it_no_longer_runs() -> None:
    """Under the old path a hazard of 0.6 removed 60% of the sleeve's mean; under the default
    the same sleeve keeps its mean and pays the blanket decay. The default can only be the
    more generous of the two, which is the direction the standing order allows."""
    shrunk = [_sleeve("s", 0.06, 21), _sleeve("t", 0.05, 22)]
    pa.apply_hazard_shrink(shrunk, {"s": 0.6})
    posterior = [_sleeve("s", 0.06, 21), _sleeve("t", 0.05, 22)]
    pa.apply_decay_posterior(posterior, {"s": 0.6}, BLANKET)
    assert posterior[0].daily_r.mean() > shrunk[0].daily_r.mean()
    assert posterior[0].decay_prob_i == pytest.approx(BLANKET)
    cfg = WorldConfig(n_worlds=64, n_rows=128, seed=4)
    old = optimise(shrunk, hard_cap=0.45, target=None, cfg=cfg)
    new = optimise(posterior, hard_cap=0.45, target=None, cfg=cfg)
    assert new.heat["s"] >= old.heat["s"] - 1e-6


# ------------------------------------------------------------------------------ the billing
def test_the_rail_is_registered_measured_and_not_tunable() -> None:
    r = rails.rail("decay_posterior")
    assert r.kind == "shrink" and r.measure == "measure_decay_posterior"
    assert r.measure in mg.MEASURES
    assert r.tunable is False, "a relief-only term has no weaker direction to walk"
    assert rails.rail("hazard_shrink").measure == "measure_hazard_shrink", "the old rail stands"


def test_the_missed_growth_line_prices_the_pair_on_the_same_book() -> None:
    r = rails.rail("decay_posterior")
    doc = {"decay_posterior": {"mode": "decay_posterior", "n_from_hazard": 3, "blanket": BLANKET,
                               "growth_with": 0.0021, "growth_without": 0.0019}}
    m = mg.measure_decay_posterior(r, doc, {})
    assert m["verdict"] == "SAMPLE" and m["sample"] is True
    assert m["value_logw_per_day"] == pytest.approx(0.0002) and m["n_relieved"] == 3
    # No relieved sleeve is a real zero.
    m0 = mg.measure_decay_posterior(r, {"decay_posterior": {"mode": "decay_posterior",
                                                            "n_from_hazard": 0}}, {})
    assert m0["verdict"] == "NOT_BINDING" and m0["value_logw_per_day"] == 0.0
    # The mean-shrink mode does not bill this rail.
    m1 = mg.measure_decay_posterior(r, {"decay_posterior": {"mode": "mean_shrink",
                                                            "n_from_hazard": 0}}, {})
    assert m1["verdict"] == "NOT_BINDING"
    # A relieved pass without the pair is UNMEASURED, never free.
    m2 = mg.measure_decay_posterior(r, {"decay_posterior": {"mode": "decay_posterior",
                                                            "n_from_hazard": 2}}, {})
    assert m2["verdict"] == "UNMEASURED" and "with/without" in m2["why"]
    assert mg.measure_decay_posterior(r, {}, {})["verdict"] == "UNMEASURED"
    assert mg.measure_decay_posterior(r, {"heat": {}}, {})["verdict"] == "UNMEASURED"


def test_the_superseded_mean_shrink_rail_reads_not_binding() -> None:
    m = mg.measure_hazard_shrink(rails.rail("hazard_shrink"),
                                 {"hazard_shrink": {"applied": {}, "n_shrunk": 0,
                                                    "mode": "decay_posterior",
                                                    "superseded_by": "decay_posterior"}}, {})
    assert m["verdict"] == "NOT_BINDING" and m["value_logw_per_day"] == 0.0


def test_run_bills_the_pair_on_the_published_book_and_not_on_a_cached_population() -> None:
    src = inspect.getsource(pa.run)
    i_bind = src.index("book, funded = bind_verdict(nt, prev_book, held, book, funded)")
    i_bill = src.index('decay_meta["growth_with"]')
    assert i_bind < i_bill, "the pair must be scored on the PUBLISHED book"
    assert '"cached" in str(worlds.note)' in src
    assert "_ev_blanket = [_replace_ev(e, decay_prob_i=None) for e in ev]" in src
    assert "_w_blanket = sample_worlds(_ev_blanket, cfg)" in src, "same cfg, same seed"


def test_the_naive_kelly_reference_stays_decay_free_whatever_the_sleeves_carry() -> None:
    """`kelly_fraction` measures full Kelly with `decay_prob=0`; with per-sleeve decay on the
    evidence the reference must still be decay-free, or the fraction is measured against a
    reference that already shrank."""
    from libs.portfolio.robust_elog import decay_prob_of
    e = _sleeve("x", 0.05, 1)
    pa.apply_decay_posterior([e], {"x": 0.2}, BLANKET)
    assert decay_prob_of(e, WorldConfig(decay_prob=0.0)) == 0.0
    src = inspect.getsource(pa.kelly_fraction)
    assert "decay_prob=0.0" in src
