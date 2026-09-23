"""The posterior E[log W] optimiser: the ceiling when the evidence is strong, the flat floor when
it is weak, below the floor only for the ruin guard, turnover priced, contests paired, evidence
believed in proportion to its size.

What is pinned:

  * strong, independent, positive sleeves run at the 30% ceiling with a positive robust (p10)
    growth, and the certificate carries every field the governance reads plus both rules verbatim;
  * weak sleeves sit EXACTLY at the flat 20% floor with `binding == "floor"`, and the fill goes to
    the sleeves with the highest marginal growth, none to the duds;
  * a sleeve with ruinous tails takes the book BELOW the floor and names itself: `ruin_guard`;
  * the turnover price makes the first-step book move less from the held book than the
    frictionless solution on the same paths;
  * `compare` on identical books is exactly zero with an interval containing zero, a strictly
    better book wins with an interval excluding zero, and the loser does not `beat`;
  * more evidence (a longer history) is deflated and shrunk less, and the certificate says so;
  * `plan_posterior` returns `plan`'s book format plus the certificate and respects the band.

Every series is built with its sample mean and sd EXACT, so an assertion about which sleeve is
better is about the mechanism and never about which seed got lucky.
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pytest

_DESK = Path(__file__).resolve().parents[1]
_ROOT = _DESK.parent.parent
for p in (str(_DESK), str(_DESK / "research"), str(_ROOT)):
    if p not in sys.path:
        sys.path.insert(0, p)

from libs.portfolio import multiperiod_worlds  # noqa: E402
from libs.portfolio import posterior_growth as pg  # noqa: E402
from libs.portfolio.robust_elog import SleeveEvidence, WorldConfig, sample_worlds  # noqa: E402

FLOOR, CEILING = 0.20, 0.30


def _series(rng: np.random.Generator, n: int, mu: float, sd: float) -> np.ndarray:
    """n days with sample mean exactly `mu` and sample sd exactly `sd`."""
    x = rng.normal(0.0, 1.0, n)
    x = (x - x.mean()) / x.std(ddof=1)
    out: np.ndarray = mu + sd * x
    return out


def _strong(seed: int = 0, n: int = 6, mu: float = 0.15, obs: int = 500,
            cost: float = 0.0) -> list[SleeveEvidence]:
    rng = np.random.default_rng(seed)
    return [SleeveEvidence(name=f"s{i}", daily_r=_series(rng, obs, mu, 0.3), forward_days=100,
                           live_days=20, cost_r=cost) for i in range(n)]


# ------------------------------------------------------------------ 1. strong -> the ceiling
def test_strong_independent_sleeves_run_at_the_ceiling_with_positive_robust_growth() -> None:
    book = pg.solve(_strong(), floor=FLOOR, ceiling=CEILING, seed=1)
    assert book.binding == "ceiling"
    assert book.total_heat == pytest.approx(CEILING, abs=1e-6)
    assert book.free_total_heat >= CEILING - 1e-6            # growth wanted at least this much
    assert book.elogw_p10 > 0.0 and book.elogw_per_day > book.elogw_p10
    assert book.p_ruin == 0.0 and book.p_stopout < pg.EPS_STOP
    assert all(v >= 0.0 for v in book.h.values())
    cert = book.certificate()
    assert {"h", "elogw_per_day", "elogw_p10", "p_ruin", "p_stopout", "turnover_cost",
            "binding", "n_worlds", "T", "shrinkage", "governance"} <= set(cert)
    assert cert["n_worlds"] == pg.DEFAULT_N_PATHS and cert["T"] == pg.DEFAULT_HORIZON
    assert cert["binding"] == "ceiling" and cert["shrinkage"]["sleeves"]["s0"]["lam"] > 0.9
    # The two governance rules, verbatim, in the certificate AND in the module docstring.
    assert cert["governance"] == list(pg.RULES)
    assert pg.__doc__ is not None
    for rule in pg.RULES:
        assert rule in cert["governance"]
    assert ("Every risk reduction mechanism must prove that it increases robust forward "
            "E[log W].") in pg.__doc__
    assert "Every strong opportunity must be allowed to increase capital above normal" in pg.__doc__


# ------------------------------------------------------------------ 2. weak -> the flat floor
def test_weak_sleeves_sit_exactly_at_the_floor_and_the_fill_goes_to_the_best() -> None:
    rng = np.random.default_rng(2)
    ev = [SleeveEvidence(name="good0", daily_r=_series(rng, 120, 0.01, 0.3)),
          SleeveEvidence(name="good1", daily_r=_series(rng, 120, 0.01, 0.3)),
          SleeveEvidence(name="dud0", daily_r=_series(rng, 120, 0.0, 0.3)),
          SleeveEvidence(name="dud1", daily_r=_series(rng, 120, 0.0, 0.3))]
    book = pg.solve(ev, floor=FLOOR, ceiling=CEILING, seed=2)
    assert book.binding == "floor"
    assert book.total_heat == pytest.approx(FLOOR, abs=1e-6)     # exactly, never scaled
    assert 0.0 <= book.free_total_heat < FLOOR                   # growth wanted less
    # The fill is by marginal growth: both good sleeves ahead of both duds, and the duds get
    # nothing while a better sleeve can still take the heat.
    assert min(book.h["good0"], book.h["good1"]) > max(book.h["dud0"], book.h["dud1"])
    assert book.h["good0"] + book.h["good1"] > 0.9 * FLOOR
    assert list(book.marginal)[:2] == sorted(["good0", "good1"],
                                             key=lambda k: -book.marginal[k])
    assert book.p_ruin == 0.0 and book.certificate()["binding"] == "floor"


# ------------------------------------------------------------------ 3. ruinous tails -> guard
def test_ruinous_tails_take_the_book_below_the_floor_and_the_guard_names_itself() -> None:
    rng = np.random.default_rng(3)
    ev = []
    for i in range(3):
        r = _series(rng, 300, 0.02, 0.3)
        r[[20 + 90 * i, 40 + 90 * i, 70 + 90 * i]] = -30.0       # three -30R days each
        ev.append(SleeveEvidence(name=f"t{i}", daily_r=r))
    book = pg.solve(ev, floor=FLOOR, ceiling=CEILING, seed=3)
    assert book.binding == "ruin_guard"
    assert 0.0 < book.total_heat < FLOOR - 1e-3
    assert book.p_ruin < pg.EPS_RUIN and book.guard_scale < 1.0
    assert "RUIN GUARD" in book.note
    # The floor was breached on the stop-out bound too; that is REPORTED, not quietly fixed.
    assert book.stopout_breached_at_floor
    cert = book.certificate()
    assert cert["binding"] == "ruin_guard" and cert["total_heat"] < FLOOR
    # Without the tails the same shape of evidence would have been mandated to the floor.
    clean = [SleeveEvidence(name=e.name, daily_r=np.where(e.daily_r < -5.0, 0.0, e.daily_r))
             for e in ev]
    assert pg.solve(clean, floor=FLOOR, ceiling=CEILING, seed=3).binding in ("floor", "growth",
                                                                              "ceiling")


# ------------------------------------------------------------------ 4. turnover is priced
def test_turnover_cost_moves_the_first_step_less_than_the_frictionless_solution() -> None:
    ev = _strong(seed=4, n=4, mu=0.03, obs=400, cost=0.0)
    paths = pg.sample_paths(ev, seed=4)
    prev = {"s0": 0.20}
    priced = pg.solve(ev, h_prev=prev, paths=paths, floor=FLOOR, ceiling=CEILING,
                      turnover_cost=0.06)
    free = pg.solve(ev, h_prev=prev, paths=paths, floor=FLOOR, ceiling=CEILING,
                    turnover_cost=0.0)
    assert free.turnover_cost == 0.0 and priced.turnover_cost > 0.0
    assert priced.turnover_l1 < 0.5 * free.turnover_l1
    # The held sleeve is kept where the price says moving is not worth it.
    assert priced.h["s0"] > free.h["s0"]
    assert priced.turnover_cost == pytest.approx(0.06 * priced.turnover_l1)
    assert priced.h_prev == {"s0": 0.20}


# ------------------------------------------------------------------ 5. the paired contest
def test_compare_is_zero_on_identical_books_and_decisive_on_a_better_one() -> None:
    ev = _strong(seed=5)
    paths = pg.sample_paths(ev, seed=5)
    book = pg.solve(ev, paths=paths, floor=FLOOR, ceiling=CEILING)
    same = pg.compare(book, book, paths)
    assert same["delta_elogw_per_day"] == 0.0
    assert same["ci_lo"] <= 0.0 <= same["ci_hi"] and not same["beats"]
    assert same["n_paths"] == paths.n_paths
    better = pg.compare(book, {}, paths)                     # the solved book against flat
    assert better["delta_elogw_per_day"] > 0.0 and better["ci_lo"] > 0.0 and better["beats"]
    assert better["elogw_a"] == pytest.approx(book.elogw_per_day)
    assert better["total_heat_b"] == 0.0
    worse = pg.compare({}, book, paths)
    assert worse["delta_elogw_per_day"] == pytest.approx(-better["delta_elogw_per_day"])
    assert worse["ci_hi"] < 0.0 and not worse["beats"]


# ------------------------------------------------------------------ 6. evidence earns belief
def test_more_evidence_is_deflated_and_shrunk_less() -> None:
    rng = np.random.default_rng(6)
    small = [SleeveEvidence(name="a", daily_r=_series(rng, 60, 0.03, 0.3), n_trials=20)]
    big = [SleeveEvidence(name="a", daily_r=_series(rng, 600, 0.03, 0.3), n_trials=20)]
    ps, pb = pg.posterior_moments(small), pg.posterior_moments(big)
    assert ps.sample_mean[0] == pytest.approx(pb.sample_mean[0])   # same measured edge
    assert pb.lam[0] > ps.lam[0]                                   # precision limb
    assert pb.deflation[0] < ps.deflation[0]                       # bias limb
    assert pb.post_mean[0] > ps.post_mean[0]
    assert ps.lam[0] == pytest.approx(60.0 / (60.0 + pg.K_SLEEVE))
    cs = pg.solve(small, floor=0.0, ceiling=CEILING, seed=6).certificate()["shrinkage"]
    cb = pg.solve(big, floor=0.0, ceiling=CEILING, seed=6).certificate()["shrinkage"]
    assert cb["mean_shrink"] > cs["mean_shrink"] and cb["sleeves"]["a"]["n_obs"] == 600
    assert cs["k_sleeve"] == pg.K_SLEEVE and cs["source"] == "niw"
    # Live days earn belief faster than backtest days, exactly as robust_elog weighs them.
    live = [SleeveEvidence(name="a", daily_r=small[0].daily_r, n_trials=20, live_days=30)]
    assert pg.posterior_moments(live).lam[0] > ps.lam[0]


# ------------------------------------------------------------------ 7. the thin planner
def test_plan_posterior_returns_plans_format_plus_the_certificate_inside_the_band() -> None:
    rng = np.random.default_rng(7)
    ev = [SleeveEvidence(name=f"s{i}", daily_r=_series(rng, 500, 0.02, 0.3), family=f"f{i}",
                         forward_days=100) for i in range(5)]
    cfg = WorldConfig(n_worlds=16, n_rows=96, seed=7)
    worlds = sample_worlds(ev, cfg)
    ref = multiperiod_worlds.plan(worlds, {}, horizon=3, target=FLOOR, cap=CEILING, cost_r=0.06)
    mp = multiperiod_worlds.plan_posterior(worlds, {}, horizon=3, target=FLOOR, cap=CEILING,
                                           cost_r=0.06, n_paths=200, seed=7)
    assert set(ref) <= set(mp) and {"certificate", "binding"} <= set(mp)
    assert mp["horizon"] == 3 and len(mp["path_total_heat"]) == 3
    assert all(FLOOR - 1e-6 <= h <= CEILING + 1e-9 for h in mp["path_total_heat"])
    assert sum(mp["h_now"].values()) == pytest.approx(mp["path_total_heat"][0], abs=1e-5)
    assert mp["turnover_per_block"][0] == pytest.approx(sum(mp["h_now"].values()), abs=1e-5)
    assert mp["turnover_per_block"][1:] == [0.0, 0.0]            # hold h_1: receding horizon
    assert all(g is not None for g in mp["growth_per_block"])
    cert = mp["certificate"]
    assert cert["binding"] == mp["binding"] in pg.BINDINGS
    assert cert["governance"] == list(pg.RULES) and cert["n_worlds"] == 200 and cert["T"] == 3
    assert cert["shrinkage"]["source"] == "worlds"
    # With the evidence supplied the certificate carries the per-sleeve shrinkage as well.
    with_ev = multiperiod_worlds.plan_posterior(worlds, {}, horizon=3, target=FLOOR, cap=CEILING,
                                                ev=ev, n_paths=200, seed=7)
    assert set(with_ev["certificate"]["shrinkage"]["sleeves"]) == {e.name for e in ev}
    assert with_ev["certificate"]["shrinkage"]["source"].startswith("worlds")
    # A floor above the ceiling is refused rather than silently reordered.
    with pytest.raises(ValueError):
        multiperiod_worlds.plan_posterior(worlds, {}, target=0.31, cap=CEILING, n_paths=50)
