"""Tests for two-book sleeve allocation.

The load-bearing cases are the three that encode the principal's architecture:
  * an UNCORRELATED booster earns more than a correlated one at the SAME Sharpe (why a
    discretionary sleeve is fundable at all),
  * an UNPROVEN sleeve gets a learning stake rather than zero (else the evidence loop never
    closes and it can never earn size),
  * a DISPROVEN sleeve gets exactly zero (unproven and disproven are different states).
The rest check the guards hold.
"""
from __future__ import annotations

from libs.risk import sleeve_allocation as sa

fails: list[str] = []


def check(name: str, cond: bool, detail: str = "") -> None:
    print(f"  {'PASS' if cond else 'FAIL'}  {name}{(' -- ' + detail) if detail else ''}")
    if not cond:
        fails.append(name)


def plan(*sleeves, equity=100_000.0):
    return sa.allocate(list(sleeves), equity)


def by(p, name):
    return next(a for a in p.allocations if a.name == name)


BASE = sa.Sleeve("systematic", sharpe=1.20, n_closes=200, is_base=True)

# ---- the architecture ------------------------------------------------------------------------
p_unc = plan(BASE, sa.Sleeve("disc", sharpe=0.60, n_closes=50, rho_to_base=0.0))
p_cor = plan(BASE, sa.Sleeve("disc", sharpe=0.60, n_closes=50, rho_to_base=0.90))
a_unc, a_cor = by(p_unc, "disc"), by(p_cor, "disc")

check("uncorrelated booster earns MORE than correlated at equal Sharpe",
      a_unc.share > a_cor.share,
      f"rho=0 -> {a_unc.share:.3f} vs rho=0.9 -> {a_cor.share:.3f}")
check("correlated booster at rho=0.9 earns nothing (base already owns it)",
      a_cor.share == 0.0, f"IR {a_cor.marginal_ir:+.3f}")
check("a booster WEAKER than the base is still fundable when uncorrelated",
      a_unc.share > 0 and a_unc.marginal_ir > 0,
      f"Sharpe 0.60 vs base 1.20, IR {a_unc.marginal_ir:+.3f}")

# ---- unproven vs disproven -------------------------------------------------------------------
p_new = plan(BASE, sa.Sleeve("conviction", sharpe=0.0, n_closes=6, rho_to_base=0.0))
a_new = by(p_new, "conviction")
check("UNPROVEN sleeve gets a learning stake, not zero",
      a_new.state == "UNPROVEN-LEARNING-STAKE" and a_new.share == sa.LEARNING_STAKE,
      f"{a_new.share:.3f} on {a_new.n_closes} closes")

p_bad = plan(BASE, sa.Sleeve("conviction", sharpe=-0.40, n_closes=40, rho_to_base=0.0))
a_bad = by(p_bad, "conviction")
check("DISPROVEN sleeve gets exactly zero", a_bad.state == "DISPROVEN-ZERO" and a_bad.share == 0.0)
check("unproven and disproven are distinguished", a_new.state != a_bad.state)

# ---- the guard I nearly shipped broken -------------------------------------------------------
LOSING = sa.Sleeve("systematic", sharpe=-0.50, n_closes=200, is_base=True)
p_lose = plan(LOSING, sa.Sleeve("disc", sharpe=0.60, n_closes=50, rho_to_base=0.80))
a_lose = by(p_lose, "disc")
check("booster is NOT inflated by a LOSING base",
      a_lose.share <= sa.LEARNING_STAKE,
      f"{a_lose.share:.3f} ({a_lose.state}) -- naive IR would have rewarded resembling a loser")
check("losing base is labelled unproven", by(p_lose, "systematic").state == "BASE-UNPROVEN")

# ---- caps and conservation -------------------------------------------------------------------
p_greedy = plan(BASE, sa.Sleeve("disc", sharpe=8.0, n_closes=500, rho_to_base=0.0))
check("discretionary share is hard-capped regardless of measured brilliance",
      by(p_greedy, "disc").share <= sa.MAX_DISCRETIONARY,
      f"Sharpe 8.0 -> {by(p_greedy, 'disc').share:.3f}, cap {sa.MAX_DISCRETIONARY}")

p_many = plan(BASE, *[sa.Sleeve(f"d{i}", sharpe=3.0, n_closes=100, rho_to_base=0.0)
                      for i in range(6)])
tot = sum(a.share for a in p_many.allocations if a.name != "systematic")
check("aggregate booster share respects the cap across MANY sleeves",
      tot <= sa.MAX_DISCRETIONARY + 1e-9, f"{tot:.3f}")
check("shares always sum to 1.0",
      all(abs(sum(a.share for a in q.allocations) - 1.0) < 1e-9
          for q in (p_unc, p_cor, p_new, p_bad, p_lose, p_greedy, p_many)))
check("base receives the residual",
      abs(by(p_unc, "systematic").share - (1.0 - a_unc.share)) < 1e-9)
check("usd tracks share", abs(by(p_unc, "disc").usd - a_unc.share * 100_000.0) < 1e-6)

# ---- refusals --------------------------------------------------------------------------------
check("refuses with no base", not sa.allocate([sa.Sleeve("a", 1.0, 50)], 100.0).allocations)
check("refuses with two bases",
      not sa.allocate([sa.Sleeve("a", 1.0, 50, is_base=True),
                       sa.Sleeve("b", 1.0, 50, is_base=True)], 100.0).allocations)
check("refuses on non-positive equity", not sa.allocate([BASE], 0.0).allocations)

# ---- monotonicity ----------------------------------------------------------------------------
shares = [by(plan(BASE, sa.Sleeve("d", sharpe=0.6, n_closes=50, rho_to_base=r)), "d").share
          for r in (-0.5, 0.0, 0.3, 0.6, 0.9)]
check("share is non-increasing in correlation to the base",
      all(shares[i] >= shares[i + 1] - 1e-9 for i in range(len(shares) - 1)),
      " -> ".join(f"{s:.3f}" for s in shares))
check("NEGATIVE correlation earns the most", shares[0] == max(shares), f"{shares[0]:.3f}")

print("ALL PASS" if not fails else f"{len(fails)} FAILED: {fails}")
raise SystemExit(1 if fails else 0)
