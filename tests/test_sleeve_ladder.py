"""Tests for the evidence-dependent ceiling ladder.

WHY THIS FILE EXISTS SEPARATELY. Installing the ladder left test_sleeve_allocation.py fully green
while quietly gutting it: with default evidence fields every sleeve now sits at UNPROVEN, so
assertions that once compared 0.150 against 0.000 now compare 0.020 against 0.000. They still pass,
and they no longer test what their names claim. A suite that goes green for a weaker reason than it
did yesterday is the "test that cannot fail" defect arriving by drift rather than by design.
"""
from __future__ import annotations

from libs.risk import sleeve_allocation as sa

fails: list[str] = []


def check(name: str, cond: bool, detail: str = "") -> None:
    print(f"  {'PASS' if cond else 'FAIL'}  {name}{(' -- ' + detail) if detail else ''}")
    if not cond:
        fails.append(name)


def sleeve(**kw):
    base = dict(name="disc", sharpe=1.0, n_closes=500, rho_to_base=0.0, max_drawdown=0.10,
                regimes_positive=4, t_stat=5.0, persistence=0.75)
    base.update(kw)
    return sa.Sleeve(**base)


BASE = sa.Sleeve("systematic", sharpe=1.20, n_closes=200, is_base=True)


def share_of(s):
    p = sa.allocate([BASE, s], 100_000.0)
    return next(a for a in p.allocations if a.name == s.name)


# ---- the ladder climbs -----------------------------------------------------------------------
rungs = {
    "UNPROVEN": sleeve(n_closes=5),
    "INITIAL": sleeve(n_closes=25, t_stat=1.6, regimes_positive=1, persistence=0.0),
    "STRONG": sleeve(n_closes=70, t_stat=2.6, regimes_positive=2, persistence=0.0),
    "DURABLE": sleeve(),
}
for want, s in rungs.items():
    t, cap, blocker = sa.evidence_tier(s)
    check(f"reaches {want}", t == want, f"cap {cap:.2f}; next -- {blocker}")

check("ceiling rises monotonically with evidence",
      [sa.evidence_tier(rungs[k])[1] for k in ("UNPROVEN", "INITIAL", "STRONG", "DURABLE")]
      == [0.02, 0.10, 0.25, 0.60])
# The tier ceiling only BINDS when the edge asks for more than it. At Sharpe 1.0 against a
# Sharpe-1.2 base, fractional Kelly wants exactly 0.25, so DURABLE status is irrelevant -- the
# sleeve is Kelly-limited, not tier-limited, and that is correct. A first draft asserted every
# DURABLE sleeve exceeds the old constant, which confused the CEILING with the ALLOCATION.
check("tier ceiling is not binding when Kelly asks for less",
      abs(share_of(sleeve()).share - 0.25) < 1e-9, f"{share_of(sleeve()).share:.3f}")
check("a DURABLE sleeve WITH the edge to justify it exceeds the old 25% constant",
      share_of(sleeve(sharpe=2.4)).share > 0.25, f"{share_of(sleeve(sharpe=2.4)).share:.3f}")

# ---- conjunctive: one great number cannot buy a rung -----------------------------------------
check("spectacular Sharpe cannot buy a rung on a short record",
      sa.evidence_tier(sleeve(sharpe=25.0, n_closes=5, t_stat=0.9))[0] == "UNPROVEN")
for field, bad in (("max_drawdown", 0.90), ("regimes_positive", 0), ("t_stat", 1.6),
                   ("persistence", 0.0), ("rho_to_base", 0.95)):
    t, cap, _ = sa.evidence_tier(sleeve(**{field: bad}))
    check(f"failing {field} alone blocks DURABLE", t != "DURABLE", f"-> {t} ({cap:.2f})")

# ---- demotion is immediate, not latched ------------------------------------------------------
hot = sleeve()
check("decayed sleeve is demoted at once, no ratchet",
      sa.evidence_tier(sa.Sleeve(**{**hot.__dict__, "t_stat": 0.4}))[0] == "UNPROVEN",
      "t-stat collapse -> straight back to the learning stake")
check("rising correlation to the base demotes",
      sa.evidence_tier(sleeve(rho_to_base=0.85))[1] < 0.60)

# ---- defaults must fail upward, never promote by omission ------------------------------------
bare = sa.Sleeve("d", sharpe=5.0, n_closes=10_000)
check("omitted evidence fields cannot promote a sleeve",
      sa.evidence_tier(bare)[0] == "UNPROVEN",
      "no drawdown/regime/track supplied -> lowest rung")

# ---- the blocker names the thing to fix ------------------------------------------------------
_, _, why = sa.evidence_tier(sleeve(t_stat=2.6))
check("blocker names the specific failing condition and how to fix it",
      "t>=" in why and "faster" in why, why)

# Calendar time must NOT gate: two sleeves with identical statistics but wildly different track
# lengths must reach the same rung. Gating on days punishes a fast book for being fast.
check("calendar span does not gate a rung",
      sa.evidence_tier(sleeve(track_days=14))[0] == sa.evidence_tier(sleeve(track_days=900))[0]
      == "DURABLE", "14 days and 900 days both reach DURABLE on identical statistics")
check("t-stat, not Sharpe, separates a hot streak from an edge",
      sa.evidence_tier(sleeve(sharpe=3.0, n_closes=25, t_stat=1.0))[0] == "UNPROVEN",
      "Sharpe 3.0 on 25 closes at t=1.0 stays at the learning stake")

# ---- base_candidate surfaces the structural decision -----------------------------------------
huge = share_of(sleeve(sharpe=12.0))
check("a sleeve outgrowing the top rung is flagged as a BASE candidate",
      huge.base_candidate and huge.share <= 0.60,
      f"share {huge.share:.3f}, tier {huge.tier}, base_candidate={huge.base_candidate}")

# ---- aggregate budget still holds across many strong sleeves ---------------------------------
many = sa.allocate([BASE] + [sa.Sleeve(**{**sleeve().__dict__, "name": f"d{i}"}) for i in range(5)],
                   100_000.0)
tot = sum(a.share for a in many.allocations if a.name != "systematic")
check("aggregate booster share cannot exceed the top rung", tot <= 0.60 + 1e-9, f"{tot:.3f}")
check("shares still sum to 1.0", abs(sum(a.share for a in many.allocations) - 1.0) < 1e-9)

print("ALL PASS" if not fails else f"{len(fails)} FAILED: {fails}")
raise SystemExit(1 if fails else 0)
