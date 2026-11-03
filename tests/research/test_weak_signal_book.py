"""The weak-signal book: pools many weak members, refuses noise, never peeks, never over-sizes."""
from __future__ import annotations

import numpy as np
import pandas as pd

from libs.research import weak_signal_book as wsb

DAYS = pd.bdate_range("2019-01-01", periods=1500)


def _series(rng, mu, sd=1.0, p_trade=0.4, start=0):
    v = rng.normal(mu, sd, len(DAYS)) * (rng.random(len(DAYS)) < p_trade)
    s = pd.Series(v, index=DAYS)
    s = s[s != 0]
    return s[s.index >= DAYS[start]]


def _pool(n_weak=40, n_noise=60, mu=0.04, seed=1):
    rng = np.random.default_rng(seed)
    series = {}
    for i in range(n_weak):
        s = _series(rng, mu)
        series[f"weak{i}"] = (s, s - 0.01)
    for i in range(n_noise):
        s = _series(rng, 0.0)
        series[f"noise{i}"] = (s, s - 0.01)
    return wsb.build_pool(series)


def test_many_weak_members_make_a_book_that_passes():
    # 80 members at a daily Sharpe near 0.05 each: none clears the bar alone, the book does.
    pool = _pool(n_weak=80, mu=0.05)
    out = wsb.judge(pool, wsb.BookConfig(), n_trials=1000)
    assert out["passed"], out["gates"]
    # The book is worth more than its best single leg out of sample.
    g = out["gates"]["beats_best_single"]
    assert g["book_sr_daily"] > g["best_single_sr_daily"]
    # Weight concentrates on the real members.
    weak_w = sum(m["weight"] for m in out["members"] if m["cell"].startswith("weak"))
    assert weak_w > 0.7


def test_pure_noise_does_not_pass_and_arms_nothing():
    pool = _pool(n_weak=0, n_noise=120, seed=7)
    out = wsb.judge(pool, wsb.BookConfig(), n_trials=1000)
    assert not out["passed"]
    assert out["sizing"]["lambda_armed"] == 0.0
    assert all(m["risk_per_trade_frac"] == 0.0 for m in out["members"])


def test_unmeasured_trial_count_fails_closed():
    out = wsb.judge(_pool(), wsb.BookConfig(), n_trials=None)
    assert not out["gates"]["deflated_sharpe"]["passed"]
    assert not out["passed"]


def test_more_trials_raise_the_bar():
    pool = _pool(n_weak=12, mu=0.03, seed=3)
    lo = wsb.judge(pool, wsb.BookConfig(), n_trials=10)["gates"]["deflated_sharpe"]["dsr"]
    hi = wsb.judge(pool, wsb.BookConfig(), n_trials=10_000_000)["gates"]["deflated_sharpe"]["dsr"]
    assert hi < lo


def test_fold_weights_never_see_the_test_block():
    pool = _pool(seed=5)
    cfg = wsb.BookConfig()
    a = wsb.walk_forward(pool, cfg)
    # Scramble everything after the first test block starts; the first fold must not move.
    t = len(pool.dates)
    first_test = wsb._blocks(t, cfg.n_blocks)[1][0]
    rng = np.random.default_rng(0)
    pool.r1[first_test:] = rng.normal(0, 5, pool.r1[first_test:].shape)
    b = wsb.walk_forward(pool, cfg)
    assert a["folds"][0]["active"] == b["folds"][0]["active"]
    assert a["folds"][0]["best_single"] == b["folds"][0]["best_single"]


def test_sizing_stays_inside_half_the_firm_rails():
    pool = _pool(n_weak=80, mu=0.05)
    cfg = wsb.BookConfig()
    out = wsb.judge(pool, cfg, n_trials=1000)
    s = out["sizing"]
    assert s["lambda"] > 0
    assert s["oos_worst_day"] >= -cfg.daily_loss_cap - 1e-9
    assert s["oos_max_drawdown"] <= cfg.drawdown_cap + 1e-9
    assert s["lambda"] <= s["lambda_growth_opt"] + 1e-12


def test_three_x_cost_can_kill_a_book_that_lives_at_one_x():
    rng = np.random.default_rng(11)
    series = {}
    for i in range(40):
        s = _series(rng, 0.04)
        series[f"w{i}"] = (s, s - 0.2)   # costs eat it at 3x
    out = wsb.judge(wsb.build_pool(series), wsb.BookConfig(), n_trials=1000)
    assert not out["gates"]["cost_3x"]["passed"]
    assert not out["passed"]


def test_member_without_history_is_not_padded_with_zeros():
    rng = np.random.default_rng(2)
    late = _series(rng, 0.05, start=1200)
    early = _series(rng, 0.0)
    pool = wsb.build_pool({"late": (late, None), "early": (early, None)})
    j = pool.ids.index("late")
    before = pool.dates < late.index[0]
    assert before.any() and not pool.avail[before, j].any()
    assert pool.avail[~before, j].all()
    assert pool.has_3x.sum() == 0


def test_coverage_is_red_on_any_gap_and_counts_refusals_separately():
    c = wsb.Coverage(eligible=3, ingested=2)
    c.refuse("symbol_untradeable")
    assert c.as_dict()["status"] == "GREEN"
    c.gap("not_yet_built", "X.f.p=1")
    d = c.as_dict()
    assert d["status"] == "RED" and d["missing"] == 1
    assert d["refused_by_rule"] == {"symbol_untradeable": 1}


def test_every_recipe_is_a_charged_trial():
    a = wsb.BookConfig().digest()
    b = wsb.BookConfig(n_blocks=7).digest()
    assert a != b
    assert wsb.recipe_trials([{"recipe": a}, {"recipe": a}, {"recipe": b}]) == 2


def test_cost_gate_is_never_vacuous_on_members_without_a_3x_arm():
    rng = np.random.default_rng(4)
    series = {f"w{i}": (_series(rng, 0.05), None) for i in range(80)}
    out = wsb.judge(wsb.build_pool(series), wsb.BookConfig(), n_trials=1000)
    g = out["gates"]["cost_3x"]
    assert g["real_3x_weight_share_min_fold"] == 0.0
    assert not g["passed"] and not out["passed"]


def test_lambda_is_scored_on_a_fold_it_was_not_chosen_on():
    out = wsb.judge(_pool(n_weak=80, mu=0.05), wsb.BookConfig(), n_trials=1000)
    h = out["sizing"]["holdout"]
    assert h["last_fold_days"] > 0 and h["lambda_from_earlier_folds"] > 0


def test_recipe_dispersion_can_only_raise_the_bar():
    pool = _pool(n_weak=80, mu=0.05)
    base = wsb.judge(pool, wsb.BookConfig(), n_trials=1000)["gates"]["deflated_sharpe"]
    wide = wsb.judge(pool, wsb.BookConfig(), n_trials=1000,
                     recipe_sharpes=[-0.5, 0.0, 0.5])["gates"]["deflated_sharpe"]
    assert wide["sr0"] >= base["sr0"]


def test_armed_lambda_never_exceeds_what_the_holdout_supports():
    out = wsb.judge(_pool(n_weak=80, mu=0.05), wsb.BookConfig(), n_trials=1000)
    s = out["sizing"]
    assert out["passed"]
    assert s["lambda_armed"] <= min(s["lambda"], s["holdout"]["lambda_from_earlier_folds"])
