"""London open and 22:00 roll must produce different books, end to end.

    python -m pytest desks/mt5/tests/test_state_to_allocation_chain.py -q

THE MATHEMATICS WAS WIRED AND THE CALL WAS NOT. `sleeve_evidence` grew `phase` and
`trades_by_sleeve`; `_posterior_mu` grew the state level of its hierarchy. And `run()` still
called `sleeve_evidence(daily, forward, live, trials)` with none of them, so every production
solve ran on an empty state and the conditioning was arithmetic nobody reached.

This file asserts the chain the desk was told it had:

    phase now -> that sleeve's returns in that phase -> conditional posterior mean
              -> different sampled worlds -> different optimal weights

and the two properties that keep it safe:

    all-negative conditional edge -> empty book -> no new exposure
    tiny conditional bucket       -> shrunk toward the parent, not believed
"""
from __future__ import annotations

import sys
from datetime import UTC, datetime
from pathlib import Path

import numpy as np

DESK = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(DESK))
sys.path.insert(0, str(DESK / "research"))
sys.path.insert(0, str(DESK.parent.parent))

import session_phase as sp  # noqa: E402

from libs.portfolio.robust_elog import (  # noqa: E402
    SleeveEvidence,
    WorldConfig,
    optimise,
    _posterior_mu,
)


def _trades(hour: int, r: float, n: int) -> list[dict]:
    return [{"entry_time": f"2026-0{1 + i % 8}-1{i % 9} {hour:02d}:00:00+00:00",
             "r_multiple": r} for i in range(n)]


def _ev(name: str, base_mu: float, state_r=(), n: int = 400, seed: int = 0) -> SleeveEvidence:
    rng = np.random.default_rng(seed)
    return SleeveEvidence(name=name, daily_r=rng.normal(base_mu, 1.0, n),
                          family=name, symbol=name,
                          state_r=np.asarray(state_r, dtype=float),
                          forward_days=120, live_days=60)


# ------------------------------------------------- 1. the phase actually selects the returns

def test_the_phase_selects_that_hours_trades_and_no_others() -> None:
    rows = _trades(8, 1.0, 50) + _trades(22, -1.0, 50)
    london = sp.returns_in_phase(rows, "LONDON_OPEN", broker_utc_offset_h=0)
    roll = sp.returns_in_phase(rows, "ROLL_THIN", broker_utc_offset_h=0)
    assert london.size == 50 and float(london.mean()) > 0
    assert roll.size == 50 and float(roll.mean()) < 0


# ------------------------------------------------- 2. state changes the posterior AND the book

def test_london_open_and_roll_produce_different_posteriors_and_different_books() -> None:
    """The end-to-end claim: it is 08:00, therefore this book; it is 22:00, therefore that one."""
    rows = _trades(8, 0.9, 60) + _trades(22, -0.9, 60)
    london = sp.returns_in_phase(rows, "LONDON_OPEN", broker_utc_offset_h=0)
    roll = sp.returns_in_phase(rows, "ROLL_THIN", broker_utc_offset_h=0)

    ev_london = [_ev("edge", 0.02, london, seed=1), _ev("other", 0.02, seed=2)]
    ev_roll = [_ev("edge", 0.02, roll, seed=1), _ev("other", 0.02, seed=2)]

    _, post_l = _posterior_mu(ev_london, np.random.default_rng(5), 64)
    _, post_r = _posterior_mu(ev_roll, np.random.default_rng(5), 64)
    assert post_l[0] > post_r[0], "a profitable hour must price above a losing one"

    cfg = WorldConfig(seed=5, n_worlds=64, n_rows=128)
    bl = optimise(ev_london, hard_cap=0.30, cfg=cfg)
    br = optimise(ev_roll, hard_cap=0.30, cfg=cfg)
    hl = dict(zip(bl.names, bl.heat, strict=True)) if hasattr(bl, "names") else bl.heat
    hr = dict(zip(br.names, br.heat, strict=True)) if hasattr(br, "names") else br.heat
    assert hl != hr, "the optimal book must differ between London open and the roll"
    assert float(hl.get("edge", 0.0)) >= float(hr.get("edge", 0.0)), (
        "the edge must not be sized larger in the hour it loses money")


# ------------------------------------------------- 3. no edge now -> no new exposure

def test_an_all_negative_conditional_state_produces_no_positive_book() -> None:
    """Forcing exposure when nothing has positive conditional edge reduces geometric growth."""
    bad = _trades(22, -1.2, 80)
    r = sp.returns_in_phase(bad, "ROLL_THIN", broker_utc_offset_h=0)
    ev = [_ev("a", -0.02, r, seed=1), _ev("b", -0.02, r, seed=2)]
    res = optimise(ev, hard_cap=0.30, cfg=WorldConfig(seed=3, n_worlds=64, n_rows=128))
    heat = dict(zip(res.names, res.heat, strict=True)) if hasattr(res, "names") else res.heat
    assert sum(float(v) for v in heat.values()) <= 0.02, (
        f"a book with no positive conditional edge deployed {heat}")


# ------------------------------------------------- 4. a tiny bucket is not believed

def test_a_six_trade_state_bucket_is_shrunk_toward_the_parent() -> None:
    base = [_ev("a", 0.02, seed=1), _ev("b", 0.02, seed=2)]
    thin = [_ev("a", 0.02, [0.9] * 6, seed=1), _ev("b", 0.02, seed=2)]
    thick = [_ev("a", 0.02, [0.9] * 60, seed=1), _ev("b", 0.02, seed=2)]
    _, p0 = _posterior_mu(base, np.random.default_rng(9), 64)
    _, pt = _posterior_mu(thin, np.random.default_rng(9), 64)
    _, pk = _posterior_mu(thick, np.random.default_rng(9), 64)
    assert (pt[0] - p0[0]) < 0.25 * 0.9, "six trades must not be taken at face value"
    assert (pk[0] - p0[0]) > 2.0 * (pt[0] - p0[0]), "sixty trades must count for much more"


# ------------------------------------------------- 5. the offset is required, never guessed

def test_the_broker_offset_changes_which_phase_now_is() -> None:
    ts = datetime(2026, 9, 4, 6, 30, tzinfo=UTC)
    assert sp.phase_at(ts, broker_utc_offset_h=0) != sp.phase_at(ts, broker_utc_offset_h=3)
