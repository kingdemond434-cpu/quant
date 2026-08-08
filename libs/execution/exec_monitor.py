"""EXECUTION MONITORING -- and the only thing that separates a monitor from a daily complaint.

WHY THIS IS NOT `run_trade_forensics.py`. The forensics already work, and they are good: on
2026-08-07 they returned three specific, actionable defects from 27 real closes -- a >24h hold
class bleeding -37.54 bps, an entry gate not filtering, and a maker conversion that is
LEG-ASYMMETRIC (futures 100%, spot 41.7%). Nothing was missing from the diagnosis.

What was missing is MEMORY. A monitor that re-derives the same three flags every morning and
prints them again is a complaint, not a control: after a week nobody reads it, and the one morning
a NEW defect appears it looks exactly like the six mornings before. The forensics answer "what is
wrong today"; this answers "what is STILL wrong, what is NEW, and what came BACK after someone
believed it fixed".

**REGRESSION IS THE CATEGORY THAT MATTERS MOST, AND THE DESK ALREADY HAS ONE.** The live flag reads
"4 open(s) below the 0.00015 funding floor AFTER the gate shipped -- gate is not filtering". A
defect that returns after being marked fixed is strictly worse than one that was never fixed,
because a fix that did not hold has also spent the desk's belief: everything downstream was sized
and reasoned as though that leak were closed.

**A CLEAN DAY IS NOT A FIX.** `RESOLVED` requires `MIN_CLEAN_OBSERVATIONS` consecutive clean
readings AND a recorded code change. One quiet morning on a book that trades sporadically is an
absence of evidence -- and letting absence close a defect is WS-005 aimed at the money path, which
is the most expensive place this desk could aim it.

**ZERO CHURN IS NOT THE GOAL AND SAYING SO MATTERS.** Zero churn is achieved by not trading. The
objective is turnover that PAYS FOR ITSELF, so churn is always reported against net -- never as a
level to minimise. A monitor that rewarded low turnover would slowly steer the desk into holding
losers, which is exactly the >24h bleed already on the tape.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import UTC, datetime

__all__ = [
    "MIN_CLEAN_OBSERVATIONS",
    "DefectState",
    "ExecHealth",
    "churn_efficiency",
    "classify",
    "hold_class_report",
    "leg_asymmetry",
    "update",
]

#: Consecutive clean readings before a defect may be called RESOLVED -- and even then only
#: alongside a recorded change. Five, because a book that trades sporadically produces quiet days
#: for free, and a fix that is really a lull will re-fire the moment volume returns.
MIN_CLEAN_OBSERVATIONS: int = 5

#: Maker conversion below this on EITHER leg of a paired trade is a defect, not a preference. The
#: live tape shows futures 100% vs spot 41.7%: a one-shot passive quote with no re-peg, resting on
#: the side the entry regime does not lift. The blended rate hides it -- 71% average looks like a
#: tuning problem rather than one leg being structurally broken.
MAKER_FLOOR: float = 0.80


@dataclass(frozen=True)
class DefectState:
    """One execution defect, across time rather than on one morning."""

    key: str
    status: str                  # NEW | PERSISTING | REGRESSED | RESOLVED
    first_seen: str = ""
    last_seen: str = ""
    occurrences: int = 0
    clean_streak: int = 0
    times_regressed: int = 0
    detail: str = ""

    @property
    def is_open(self) -> bool:
        return self.status != "RESOLVED"


def classify(prev: dict[str, object] | None, present_today: bool, *,
             change_recorded: bool = False,
             min_clean: int = MIN_CLEAN_OBSERVATIONS) -> tuple[str, int, int]:
    """(status, clean_streak, times_regressed) for one defect.

    ORDER OF CHECKS IS THE WHOLE LOGIC. A defect seen today after a prior RESOLVED is a
    REGRESSION, and that is tested before PERSISTING so a returning defect can never be filed as
    the ordinary continuation of an old one -- which is how a fix that did not hold becomes
    invisible.
    """
    if prev is None:
        return ("NEW" if present_today else "RESOLVED"), 0, 0
    was = str(prev.get("status", ""))
    # `prev` rows come from a JSON artifact, so every field is `object` until proven otherwise.
    # Coercing through str() first keeps a malformed row from raising inside a money-path monitor.
    regressed = int(str(prev.get("times_regressed", 0) or 0))
    streak = int(str(prev.get("clean_streak", 0) or 0))

    if present_today:
        if was == "RESOLVED":
            return "REGRESSED", 0, regressed + 1
        return ("REGRESSED" if was == "REGRESSED" else "PERSISTING"), 0, regressed
    streak += 1
    # A CLEAN DAY IS NOT A FIX. Absence closes nothing on its own -- a sporadic book produces
    # quiet days for free, and a "fix" that is really a lull re-fires when volume returns.
    if streak >= min_clean and change_recorded:
        return "RESOLVED", streak, regressed
    return (was or "PERSISTING"), streak, regressed


def update(history: dict[str, dict[str, object]], flags: dict[str, str], *,
           changes: set[str] | None = None, now: str = "") -> list[DefectState]:
    """Fold today's flags into the running record. Returns every KNOWN defect, not just today's.

    Defects absent from `flags` are carried forward rather than dropped: a monitor that reported
    only today's flags would show an empty screen on a quiet day and read as health.
    """
    stamp = now or datetime.now(tz=UTC).isoformat()
    changed = changes or set()
    out: list[DefectState] = []
    for key in sorted(set(history) | set(flags)):
        prev = history.get(key)
        today = key in flags
        status, streak, regressed = classify(prev, today, change_recorded=key in changed)
        out.append(DefectState(
            key=key, status=status,
            first_seen=str((prev or {}).get("first_seen") or (stamp if today else "")),
            last_seen=stamp if today else str((prev or {}).get("last_seen", "")),
            occurrences=int(str((prev or {}).get("occurrences", 0) or 0)) + (1 if today else 0),
            clean_streak=streak, times_regressed=regressed,
            detail=flags.get(key, str((prev or {}).get("detail", ""))),
        ))
    return out


def churn_efficiency(net_bps: float, turnover: float) -> tuple[float, str]:
    """(net per unit turnover, verdict). CHURN IS JUDGED AGAINST NET, NEVER MINIMISED.

    Zero churn is achieved by not trading, so a monitor that rewarded low turnover would steer the
    desk toward holding losers -- which is the >24h bleed already on this tape. The question is
    never "is turnover high" but "does turnover pay for itself".
    """
    if turnover <= 0:
        return 0.0, ("NO TURNOVER -- nothing traded, which is not the same as nothing wasted and "
                     "must never read as efficiency")
    eff = net_bps / turnover
    if eff > 0:
        return eff, f"turnover pays: {eff:+.3f} bp of net per unit turned"
    return eff, (f"turnover COSTS: {eff:+.3f} bp of net per unit turned -- the churn is not buying "
                 "the edge it is spending. Look at holding period and leg conversion before "
                 "signal quality; a slower version of the same signal pays the round trip fewer "
                 "times")


def hold_class_report(buckets: dict[str, tuple[float, int]]) -> list[str]:
    """Net bps by holding-period bucket -- `{label: (net_bps, n_trades)}`.

    THE HOLDING PERIOD IS A FIRST-CLASS AXIS BECAUSE THE TAPE SAYS SO: the >24h class bled
    -37.54 bps over 23 trades while shorter classes did not. A blended P&L would have shown a
    modest loss and hidden which SHAPE of trade caused it -- and the shape is the fix.
    """
    out: list[str] = []
    for label, (net, n) in sorted(buckets.items()):
        if n <= 0:
            out.append(f"{label}: NO TRADES -- unmeasured, not clean")
            continue
        verdict = "bleeding" if net < 0 else "paying"
        out.append(f"{label}: {net:+.2f} bps over {n} trade(s) -- {verdict}")
    return out


def leg_asymmetry(rates: dict[str, float], *, floor: float = MAKER_FLOOR) -> tuple[bool, str]:
    """Is one leg of a paired trade structurally worse at getting maker fills?

    REPORTED PER LEG, NEVER BLENDED. The live tape is futures 100% / spot 41.7%; the blend is 71%,
    which reads as a tuning problem rather than as one leg being broken. The fix implied by the
    blend (nudge the quote) is not the fix implied by the split (re-peg the spot quote to the
    touch, because a one-shot passive order resting on the side the entry regime does not lift
    will simply never fill).
    """
    if len(rates) < 2:
        return False, "fewer than two legs -- asymmetry is not defined, not absent"
    worst = min(rates, key=lambda k: rates[k])
    best = max(rates, key=lambda k: rates[k])
    if rates[worst] >= floor:
        return False, f"both legs at or above {floor:.0%} (worst {worst} {rates[worst]:.1%})"
    gap = rates[best] - rates[worst]
    return True, (
        f"LEG-ASYMMETRIC: {best} {rates[best]:.1%} vs {worst} {rates[worst]:.1%} "
        f"(gap {gap:.1%}). Fix the {worst} quote -- re-peg to the touch. The blended rate is "
        f"{sum(rates.values()) / len(rates):.1%}, which would read as a tuning problem rather "
        "than one leg that structurally does not fill.")


@dataclass(frozen=True)
class ExecHealth:
    """The daily verdict. Ordered so a REGRESSION cannot be scrolled past."""

    defects: tuple[DefectState, ...] = field(default_factory=tuple)
    notes: tuple[str, ...] = field(default_factory=tuple)

    @property
    def regressions(self) -> tuple[DefectState, ...]:
        return tuple(d for d in self.defects if d.status == "REGRESSED")

    @property
    def open_defects(self) -> tuple[DefectState, ...]:
        return tuple(d for d in self.defects if d.is_open)

    @property
    def headline(self) -> str:
        if self.regressions:
            names = ", ".join(d.key for d in self.regressions)
            return (f"REGRESSION: {names} returned after being marked fixed. A fix that did not "
                    "hold has also spent the desk's belief -- everything downstream was sized as "
                    "though this leak were closed.")
        if self.open_defects:
            return f"{len(self.open_defects)} open execution defect(s)"
        return ("no open execution defects -- which is a statement about the flags that RAN, not "
                "a clean bill of health for paths nobody measured")


def render(health: ExecHealth) -> str:
    lines = [health.headline]
    for d in health.defects:
        if d.status == "RESOLVED":
            continue
        age = f"seen {d.occurrences}x" + (f", regressed {d.times_regressed}x"
                                          if d.times_regressed else "")
        lines.append(f"  [{d.status}] {d.key} ({age}) {d.detail}".rstrip())
    lines += [f"  {n}" for n in health.notes]
    return "\n".join(lines)


def sharpe_of_net(net_bps_per_trade: list[float]) -> float | None:
    """Sharpe of realised per-trade net. None when the sample cannot support it.

    None rather than 0.0 because a desk reading 0.0 concludes "no edge" and a desk reading None
    concludes "not measured yet" -- and on 27 closes the second is the true statement.
    """
    n = len(net_bps_per_trade)
    if n < 2:
        return None
    mean = sum(net_bps_per_trade) / n
    var = sum((x - mean) ** 2 for x in net_bps_per_trade) / (n - 1)
    return None if var <= 0 else mean / math.sqrt(var)
