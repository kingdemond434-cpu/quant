"""R0429 -- the ruin cap's drop-vs-level inversion, pinned directionally.

`dynamic_leverage._ruin_cap(drawdown_ruin=0.35)` documents "equity drop treated as ruin";
`growth_leverage.risk_of_ruin(threshold=...)` is P(equity < LEVEL). Passing the drop raw asked
for P(equity < 0.35) -- a 65% crash -- so the survival ceiling was derived against roughly twice
the documented disaster and could only ever be LOOSER than designed. These tests pin the
translation and its direction so a refactor cannot silently re-invert it.
"""

from __future__ import annotations

import numpy as np

import libs.risk.dynamic_leverage as dl


def test_ruin_cap_translates_the_drop_into_an_equity_level(monkeypatch):
    seen: list[float] = []

    def _spy(returns, lev, *, threshold, **kw):
        seen.append(threshold)
        return 0.0                                    # every leverage passes; we only watch args

    monkeypatch.setattr(dl, "risk_of_ruin", _spy)
    dl._ruin_cap(np.full(64, 0.001), ruin_tol=0.02, drawdown_ruin=0.35)
    assert seen, "risk_of_ruin was never consulted"
    assert all(abs(t - 0.65) < 1e-12 for t in seen), (
        "a 35% drawdown-ruin must probe P(equity < 0.65), not P(equity < 0.35)")


def test_the_documented_drop_is_stricter_than_the_inverted_one():
    """Directional: judging ruin at the 35% drawdown must cap leverage at or below the cap the
    old inverted call produced -- the fix may only ever TIGHTEN the ceiling."""
    rng = np.random.default_rng(7)
    r = rng.normal(0.0008, 0.02, 400)                # volatile enough for the grid to bind
    fixed = dl._ruin_cap(r, ruin_tol=0.02, drawdown_ruin=0.35)
    from libs.risk.growth_leverage import risk_of_ruin

    inverted = 0.0
    for lev in dl._GRID:
        ror = risk_of_ruin(r, float(lev), threshold=0.35)   # the old, inverted call
        if not np.isfinite(ror):
            break
        if ror <= 0.02:
            inverted = float(lev)
        else:
            break
    assert fixed <= inverted
