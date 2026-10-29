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


# --- MEASURED LINES (ARCH-28, 2026-10-07) ---------------------------------------------------
#
# A declared cost is the operator's word; a measured one is the desk's own ledger. Where the
# desk has a ledger the measurement wins over the YAML and the basis says which it was. Where
# it has none (the two hosts' invoices: no billing API key exists for either provider) the line
# stays what the YAML says, and a `null` there stays UNKNOWN -- never zero.

WINDOW_DAYS = 30.0


def _within(stamp: Any, now: Any, days: float) -> bool:
    from datetime import UTC, datetime
    try:
        if isinstance(stamp, (int, float)):
            t = datetime.fromtimestamp(float(stamp), tz=UTC)
        else:
            t = datetime.fromisoformat(str(stamp).replace("Z", "+00:00"))
            if t.tzinfo is None:
                t = t.replace(tzinfo=UTC)
    except (TypeError, ValueError, OSError):
        return False
    age = float((now - t).total_seconds()) / 86_400.0
    return bool(0.0 <= age <= days)


def _parse(stamp: Any) -> Any:
    from datetime import UTC, datetime
    try:
        t = datetime.fromisoformat(str(stamp).replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return None
    return t if t.tzinfo else t.replace(tzinfo=UTC)


def measure_llm(rows: list[dict[str, Any]], now: Any, is_free: Any,
                days: float = WINDOW_DAYS) -> dict[str, Any]:
    """Trailing-window model spend from the seat ledger, scaled to a 30-day month BY THE SPAN
    THE LEDGER ACTUALLY COVERS, never by the window it was asked for.

    THE `usd` ON A ROW IS AN ESTIMATE, not a bill: `llm_seat._record_spend` writes tokens times a
    flat, deliberately high per-1k rate. So a priced result is ESTIMATED, never MEASURED, and its
    basis says so. A paid row with no `usd` is UNPRICED: it is not $0, and while any exists the
    line is UNMEASURED, because a total that silently omits calls lowers the hurdle. Free-model
    rows cost zero by model id, the same rule `llm_seat.month_spend_usd` applies.
    """
    paid = 0.0
    calls = free_calls = tokens = unpriced = 0
    first = None
    for r in rows:
        if not _within(r.get("utc"), now, days):
            continue
        calls += 1
        tokens += int(r.get("tokens") or 0)
        t = _parse(r.get("utc"))
        if t is not None and (first is None or t < first):
            first = t
        if r.get("free") is True or is_free(str(r.get("model") or "")):
            free_calls += 1
            continue
        if r.get("usd") is None:
            unpriced += 1
            continue
        paid += float(r["usd"])
    if not calls or first is None:
        return {"status": "UNMEASURED", "why": f"no seat call in the last {days:g} days"}
    # The ledger covers from its first row in the window to now; a ledger that began yesterday
    # is one day of evidence, and scaling it as thirty would understate the month thirty-fold.
    span = max(1.0 / 24.0, min(days, (now - first).total_seconds() / 86_400.0))
    out = {"basis": "data/llm_spend.jsonl usd = tokens x flat per-1k rate (an over-estimate "
                    "by design, not a provider bill)",
           "window_days": days, "span_days": round(span, 3), "calls": calls,
           "free_calls": free_calls, "unpriced_calls": unpriced, "tokens": tokens,
           "window_usd": round(paid, 4)}
    if unpriced:
        return {**out, "status": "UNMEASURED",
                "why": f"{unpriced} paid call(s) carry no price; the total would omit them"}
    return {**out, "status": "ESTIMATED", "monthly_usd": round(paid * 30.0 / span, 2)}


def measure_broker(deals: list[dict[str, Any]], now: Any, currency: str | None,
                   days: float = WINDOW_DAYS) -> dict[str, Any]:
    """What the account PAID the broker in the window: commission, swap and fees per deal.

    Reported, never added to the burn: these are already inside realised P&L, so adding them to
    the hurdle would charge them twice. Swap can be income; it is signed so a cost is positive.
    """
    comm = swap = fee = 0.0
    n = 0
    for d in deals:
        if not _within(d.get("epoch", d.get("at")), now, days):
            continue
        n += 1
        comm += -float(d.get("comm") or 0.0)
        swap += -float(d.get("swap") or 0.0)
        fee += -float(d.get("fee") or 0.0)
    if not n:
        return {"status": "UNMEASURED", "why": f"no broker deal in the last {days:g} days"}
    return {"status": "MEASURED", "basis": "data/cost_truth_quotes.json deals "
            "(history_deals_get, account currency)", "currency": currency,
            "deals": n, "window_days": days,
            "commission": round(comm, 2), "swap": round(swap, 2), "fee": round(fee, 2),
            "total": round(comm + swap + fee, 2),
            "monthly": round((comm + swap + fee) * 30.0 / days, 2),
            "in_burn": False,
            "why_not_in_burn": "already inside realised P&L; the hurdle is what the desk must "
                               "earn ON TOP of trading costs"}


def alert_burden(summary: dict[str, int], escalations: list[dict[str, Any]],
                 events: dict[str, int]) -> dict[str, Any]:
    """How much of the operator's attention the desk asks for, and how much of it is meaningful.

    `needs_human` is the manual-repair load (only a person can close it); `escalate` is the subset
    worth a page (FAILED, REGRESSED, or NEEDS_HUMAN aged a day, `AlertLedger.escalations`); the
    rest is noise the desk is expected to absorb itself. The share that is meaningful is the
    number to push UP: a pager that cries about self-healing work gets muted.
    """
    open_n = sum(v for k, v in summary.items() if k != "FIXED")
    fixed = int(summary.get("FIXED", 0))
    esc = len(escalations)
    return {"open": open_n, "fixed": fixed, "needs_human": int(summary.get("NEEDS_HUMAN", 0)),
            "escalate": esc, "escalations": escalations[:20],
            "self_healed_share": round(fixed / (fixed + open_n), 3) if fixed + open_n else None,
            "meaningful_share": round(esc / open_n, 3) if open_n else None,
            "defect_events_window": events}


def merge_measured(cfg: dict[str, Any], measured: dict[str, dict[str, Any]]) -> dict[str, Any]:
    """The YAML with each MEASURED or ESTIMATED line written over its declared value; the basis
    per line says which. An UNMEASURED line leaves the declared value, and a null stays UNKNOWN.
    """
    out = dict(cfg)
    lines = dict(cfg.get("monthly_usd") or {})
    basis = {k: ("declared" if v is not None else "unknown") for k, v in lines.items()}
    for name, m in measured.items():
        st = m.get("status")
        if st in ("MEASURED", "ESTIMATED") and m.get("monthly_usd") is not None:
            lines[name] = float(m["monthly_usd"])
            basis[name] = f"{str(st).lower()}: {m.get('basis')}"
    out["monthly_usd"] = lines
    out["basis"] = basis
    return out
