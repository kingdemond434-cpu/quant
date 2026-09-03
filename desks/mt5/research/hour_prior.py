"""Turn the measured hour-of-day surface into an allocation prior the desk actually reads.

WHY THIS EXISTS. `hour_surface.py` has been measuring expected R by hour of day and writing
hour_surface.json, and NOTHING has ever read it -- the only importer is its own producer. A
measurement organ whose output no fence consumes is a log line (III.16), and this one was sitting
on the largest unclaimed allocation signal the desk has.

WHAT THE SURFACE ACTUALLY SAYS, once significance is applied rather than eyeballed:

    08Z  +0.166R  n=6143  t=+13.0   heat 7.55%   robustly positive, well funded
    14Z  +0.164R  n=6154  t=+12.9   heat 0.04%   robustly positive, STARVED
    18Z  -0.032R  n=3779  t= -2.0   heat 8.53%   marginal, heavily funded
    16Z  -0.115R  n=3178  t= -6.5   heat 0.06%   solidly negative, already tiny
    17Z  -0.130R  n=2310  t= -6.2   heat 0.04%   solidly negative, already tiny

The headline is NOT "move heat off the losing hours". 18Z carries most of the negative-hour heat
and is only a 2-sigma effect -- moving 8.53% of the book on that would be a real bet dressed as
housekeeping. The genuinely free finding is 14Z: an hour as strongly positive as the desk's best
(t=+12.9 over 6,154 trades) holding 0.04% of the book. The desk is not over-allocated to losers
so much as blind to a winner.

HOW THIS IS USED, AND HOW IT IS NOT. It emits a per-hour PRIOR -- a multiplicative shade on
expected return, bounded and significance-weighted -- for the allocator to fold into sleeve
evidence. It does not gate orders, does not block an hour, and does not size anything. An hour
whose evidence is thin gets a prior of exactly 1.0, which is the same as having no opinion: a
noisy hour must not move money, and UNMEASURED is a real answer (L1.28a).

BOUNDED ON PURPOSE. The shade is clamped so no hour can be zeroed or doubled by this alone. The
surface is one cut of history over a book that has changed composition repeatedly; letting it
dominate the posterior would be fitting the allocator to a summary statistic.
"""
from __future__ import annotations

import json
import math
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

DESK = Path(__file__).resolve().parents[1]
SURFACE = DESK / "reports" / "hour_surface.json"
OUT = DESK / "reports" / "hour_prior.json"

#: |t| below which an hour has no opinion. 3.0 is the same reporting floor the anomaly miner uses,
#: so one standard of evidence applies to both discovery and allocation.
MIN_T = 3.0

#: How far the prior may shade expected return, either way. The surface is one cut of history
#: over a book whose composition has changed; a bound is what stops a summary statistic from
#: becoming the posterior.
MAX_SHADE = 0.25


def _t_stat(expected_r: float, trades: int) -> float:
    """t-like statistic for an hour's mean R. Unit sigma assumed -- deliberately conservative.

    The surface carries no dispersion, so sigma=1 is used, which UNDERSTATES t when trade-level R
    is tighter than 1 and overstates it when wider. Understating is the safe direction for a
    statistic that moves money, and the alternative -- inventing a dispersion the artifact does
    not carry -- would be worse than being conservative.
    """
    if trades <= 1:
        return 0.0
    return float(expected_r) * math.sqrt(trades)


def build() -> dict[str, Any]:
    """Read the surface, apply significance, emit a bounded per-hour prior."""
    if not SURFACE.exists():
        return {"error": "hour_surface.json absent -- no prior, not a neutral prior",
                "hours": {}}
    doc = json.loads(SURFACE.read_text("utf-8"))
    rows = doc.get("hours") or []

    priors: dict[str, float] = {}
    detail: list[dict[str, Any]] = []
    for r in rows:
        hour = int(r.get("hour_utc") or 0)
        exp_r = float(r.get("expected_r") or 0.0)
        trades = int(r.get("trades") or 0)
        t = _t_stat(exp_r, trades)
        if abs(t) < MIN_T or trades < 200:
            shade = 1.0
            why = ("no opinion: " + ("too few trades" if trades < 200 else f"|t|={abs(t):.1f}"
                                     f" below {MIN_T}"))
        else:
            # Scale by significance, not by effect size: a large effect on thin evidence must not
            # outrank a moderate one on thick evidence, which is the mistake raw exp_R invites.
            strength = min(1.0, (abs(t) - MIN_T) / 10.0)
            shade = 1.0 + math.copysign(MAX_SHADE * strength, exp_r)
            why = f"t={t:+.1f} over {trades} trades"
        priors[str(hour)] = round(shade, 4)
        detail.append({"hour_utc": hour, "expected_r": exp_r, "trades": trades,
                       "t": round(t, 2), "prior": round(shade, 4),
                       "funded_heat_pct": round(float(r.get("funded_heat") or 0.0) * 100, 3),
                       "why": why})

    detail.sort(key=lambda d: -d["t"])
    acted = [d for d in detail if d["prior"] != 1.0]
    starved = [d for d in detail if d["t"] >= MIN_T and d["funded_heat_pct"] < 1.0]
    overfunded = [d for d in detail if d["t"] <= -MIN_T and d["funded_heat_pct"] > 1.0]

    report = {
        "built_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "source": str(SURFACE),
        "min_t": MIN_T, "max_shade": MAX_SHADE,
        "priors": priors,
        "hours": detail,
        "acted_on": len(acted),
        "starved_positive_hours": [d["hour_utc"] for d in starved],
        "overfunded_negative_hours": [d["hour_utc"] for d in overfunded],
        "finding": ("The unclaimed signal is a STARVED WINNER, not an over-funded loser. "
                    "Hours with significant positive expectancy and under 1% of the book are "
                    "listed in starved_positive_hours; they are where reallocation is free."),
        "not_a_gate": ("This shades expected return for the allocator. It blocks no hour, sizes "
                       "nothing, and gives an hour with thin evidence a prior of exactly 1.0 -- "
                       "the same as having no opinion."),
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(report, indent=1, default=str), encoding="utf-8")
    return report


def prior_for(hour_utc: int) -> float:
    """The bounded shade for one hour, or 1.0 when unmeasured.

    Safe for a caller with no artifact: a missing prior is no opinion, never a zero.
    """
    try:
        d = json.loads(OUT.read_text("utf-8"))
        return float((d.get("priors") or {}).get(str(int(hour_utc)), 1.0))
    except (OSError, ValueError, TypeError):
        return 1.0


if __name__ == "__main__":
    rep = build()
    print(f"hour prior: acted on {rep.get('acted_on')} of 24 hours")
    print(f"  starved positive hours (free reallocation): {rep.get('starved_positive_hours')}")
    print(f"  over-funded negative hours:                 {rep.get('overfunded_negative_hours')}")
    for d in (rep.get("hours") or [])[:6]:
        print(f"   {d['hour_utc']:2d}Z  expR {d['expected_r']:+.3f}  t {d['t']:+6.1f}  "
              f"heat {d['funded_heat_pct']:5.2f}%  prior {d['prior']:.3f}  {d['why']}")
