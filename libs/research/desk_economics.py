"""What return the desk needs just to stand still.

Every real fund knows its hurdle; this one had never computed one. `config/costs.yaml` models
what a TRADE costs. Nothing modelled what the DESK costs -- the VPS, the model access, the data
-- so "is this book big enough to be worth running?" had no numeric answer.

The arithmetic is trivial and the discipline is not: unknown costs are reported as UNKNOWN and
propagate to "cannot compute", never to zero. A burn rate that silently omits the largest line
item is worse than no burn rate at all, because it yields a hurdle someone would actually plan
against. Every function here refuses to guess.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

MONTHS_PER_YEAR = 12.0


@dataclass(frozen=True)
class CostBase:
    """Declared monthly costs, with the unknowns kept visible rather than folded into the total."""

    known: dict[str, float]
    unknown: tuple[str, ...]

    @property
    def monthly_usd(self) -> float:
        """Sum of what is KNOWN. Read alongside `is_complete` -- this is a floor, not the total."""
        return round(sum(self.known.values()), 2)

    @property
    def annual_usd(self) -> float:
        return round(self.monthly_usd * MONTHS_PER_YEAR, 2)

    @property
    def is_complete(self) -> bool:
        return not self.unknown

    @property
    def largest(self) -> tuple[str, float] | None:
        return max(self.known.items(), key=lambda kv: kv[1]) if self.known else None


def parse_costs(cfg: dict[str, Any]) -> CostBase:
    """Split declared costs into known amounts and unknown line items."""
    _raw = cfg.get("monthly_usd")
    raw: dict[str, Any] = _raw if isinstance(_raw, dict) else {}
    known: dict[str, float] = {}
    unknown: list[str] = []
    for name, value in raw.items():
        if value is None:
            unknown.append(str(name))
            continue
        try:
            known[str(name)] = float(value)
        except (TypeError, ValueError):
            unknown.append(str(name))
    return CostBase(known=known, unknown=tuple(sorted(unknown)))


@dataclass(frozen=True)
class Hurdle:
    """The return the book must earn to cover the desk's own costs."""

    equity_usd: float
    monthly_cost_usd: float
    complete: bool

    @property
    def monthly_pct(self) -> float | None:
        if self.equity_usd <= 0:
            return None
        return round(100.0 * self.monthly_cost_usd / self.equity_usd, 4)

    @property
    def annual_pct(self) -> float | None:
        """Compounded, not multiplied by 12 -- the desk's own doctrine is geometric growth, and
        a hurdle stated arithmetically understates what compounding actually has to deliver."""
        m = self.monthly_pct
        if m is None:
            return None
        return float(round(100.0 * ((1.0 + m / 100.0) ** MONTHS_PER_YEAR - 1.0), 3))

    @property
    def verdict(self) -> str:
        a = self.annual_pct
        if a is None:
            return "no equity deployed -- hurdle undefined (any cost is infinite % of zero)"
        floor = "at least " if not self.complete else ""
        return (f"the book must return {floor}{a:.2f}%/yr "
                f"(${self.monthly_cost_usd:,.2f}/mo on ${self.equity_usd:,.0f}) "
                f"before a single dollar is profit")


def hurdle(equity_usd: float, costs: CostBase) -> Hurdle:
    return Hurdle(equity_usd=max(0.0, float(equity_usd)),
                  monthly_cost_usd=costs.monthly_usd,
                  complete=costs.is_complete)


def capital_for_hurdle(costs: CostBase, target_annual_pct: float) -> float | None:
    """Equity at which the cost base falls to an acceptable hurdle. None when uncomputable.

    The inverse question, and the more useful one for a small desk: not "what must I earn" but
    "how much capital makes these costs tolerable". Below this figure the desk is a research
    project being funded, which is a legitimate choice but should be a KNOWN one.
    """
    if target_annual_pct <= 0 or costs.monthly_usd <= 0:
        return None
    monthly_target = (1.0 + target_annual_pct / 100.0) ** (1.0 / MONTHS_PER_YEAR) - 1.0
    if monthly_target <= 0:
        return None
    return float(round(costs.monthly_usd / monthly_target, 2))


def runway_months(cash_usd: float, costs: CostBase) -> float | None:
    """Months of costs the cash covers. None when costs are zero or unknown-dominated."""
    if costs.monthly_usd <= 0:
        return None
    return round(max(0.0, float(cash_usd)) / costs.monthly_usd, 1)


def assess(equity_usd: float, cfg: dict[str, Any]) -> dict[str, Any]:
    """Full economic picture for the report artifact."""
    costs = parse_costs(cfg)
    h = hurdle(equity_usd, costs)
    _pol = cfg.get("policy")
    policy: dict[str, Any] = _pol if isinstance(_pol, dict) else {}
    try:
        target = float(policy.get("max_acceptable_annual_hurdle_pct", 10.0))
    except (TypeError, ValueError):
        target = 10.0
    needed = capital_for_hurdle(costs, target)
    a = h.annual_pct
    return {
        "equity_usd": h.equity_usd,
        "monthly_cost_usd": costs.monthly_usd,
        "annual_cost_usd": costs.annual_usd,
        "cost_base_complete": costs.is_complete,
        "undeclared_line_items": list(costs.unknown),
        "largest_known_cost": costs.largest,
        "hurdle_monthly_pct": h.monthly_pct,
        "hurdle_annual_pct": a,
        "max_acceptable_annual_hurdle_pct": target,
        "hurdle_acceptable": (None if a is None else a <= target),
        "capital_needed_for_acceptable_hurdle_usd": needed,
        "verdict": h.verdict,
        "note": ("Unknown costs are EXCLUDED from the total and listed under "
                 "undeclared_line_items; every figure here is therefore a FLOOR until "
                 "cost_base_complete is true. Declare the real numbers in "
                 "config/desk_costs.yaml -- a hurdle computed from a partial cost base is the "
                 "one output of this module that could do harm."),
    }
