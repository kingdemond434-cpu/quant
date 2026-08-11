"""CADENCE ROI -- how often an organ should run is READ off its yield, never argued.

THE FAILURE THIS ENDS. Cadence on this desk has been set by intuition and then defended by
intuition, and intuition has one bias: more feels like effort. The miner was scheduled six times a
day against a corpus whose measured yield ratio fell 0.1135 -> 0.0292 in a single day; the CRO seat
was scheduled four times a day and produced 7 of 411 recommendation-ledger rows. Neither number was
consulted before the cadence was chosen, because nothing made the arithmetic automatic. R0088's own
lesson -- "should this run more often?" is an OPINION until somebody logs what a run returned --
was learned for the miner and never generalised to the other organs.

THE ARITHMETIC. An organ's cadence is worth raising only when the marginal run produces marginal
information. Three regimes, and they need different answers:

  * SATURATING -- the yield ratio falls run-over-run because the corpus is fixed and the
    seen-ledger already holds it. More frequency re-reads the same material; only NEW TERRITORY or
    MORE ELAPSED TIME moves the ratio. Cut the cadence, widen the queries.
  * PUBLICATION-RATE-LIMITED -- the upstream produces at its own pace (arXiv announces once a
    weekday, a research seat has one repo state to react to). Polling faster than the source
    publishes cannot mint information, it can only mint calls.
  * EVENT-DRIVEN -- the organ reacts to a state change (a commit, a fill, a breach). Its correct
    trigger is the event, and a timer is a poor approximation of one; the timer should be a
    fallback heartbeat, not the primary path.

Safety organs are DELIBERATELY EXCLUDED from this arithmetic and the exclusion is enforced in
`FLOOR_PROTECTED`: a watchdog, a live guard, a recorder or a ruin rail is not bought for its
information yield, it is bought for the tail it prevents, and "it found nothing today" is the
SUCCESS case. Applying yield logic to a safety floor is how a desk optimises its way into an
uninstrumented failure -- so those names cannot be cut by this module at all.

THIS MODULE RECOMMENDS. It does not edit the crontab: ops/crontab.manifest is the authoritative
schedule and a human (or the deploy path) installs it. A cadence advisor that could silently
rewrite the schedule would be able to turn off an organ nobody noticed was load-bearing.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

__all__ = [
    "FLOOR_PROTECTED",
    "REGIMES",
    "CadenceVerdict",
    "miner_yield_trend",
    "recommend",
    "recommend_all",
]

_ROOT = Path(__file__).resolve().parents[2]

#: Organs whose cadence this module may NEVER recommend cutting. Matched as substrings against the
#: cron line. A quiet safety organ is doing its job; its value is the tail it prevents, not the
#: findings it reports, so yield arithmetic simply does not apply to it.
FLOOR_PROTECTED: tuple[str, ...] = (
    "watchdog", "run_live_guard", "run_deadman", "ensure_recorder", "run_recorder",
    "organ_catchup", "run_alert_canary", "run_alerts", "pull_deploy", "run_law_gate",
    "resolve_paper_book", "run_cadence",
)

REGIMES: tuple[str, ...] = ("SATURATING", "PUBLICATION_RATE_LIMITED", "EVENT_DRIVEN", "UNMEASURED")


@dataclass(frozen=True)
class CadenceVerdict:
    organ: str
    regime: str
    runs_per_day_now: float
    runs_per_day_recommended: float
    why: str
    evidence: str
    protected: bool = False

    def as_dict(self) -> dict[str, Any]:
        return {
            "organ": self.organ, "regime": self.regime,
            "runs_per_day_now": self.runs_per_day_now,
            "runs_per_day_recommended": self.runs_per_day_recommended,
            "delta_runs_per_day": round(self.runs_per_day_now - self.runs_per_day_recommended, 2),
            "why": self.why, "evidence": self.evidence, "protected": self.protected,
        }


def miner_yield_trend(root: Path | None = None, *, source: str = "bilibili",
                      last_n: int = 8) -> dict[str, Any]:
    """Measured new/fetched ratio per run for one mined source, oldest to newest.

    This is the instrument R0088 asked for, read rather than argued. A FALLING ratio against a
    FLAT fetch count is saturation: the corpus is not producing, the ledger already holds it.
    """
    base = root or _ROOT
    ratios: list[float] = []
    fetched: list[int] = []
    try:
        text = (base / "data/miner_yield.jsonl").read_text("utf-8", errors="ignore")
    except OSError:
        return {"status": "UNMEASURED", "why": "data/miner_yield.jsonl absent -- cadence for "
                                               "this organ is an opinion until a run is logged"}
    for line in text.splitlines():
        if not line.strip():
            continue
        try:
            per = (json.loads(line).get("per_source") or {}).get(source)
        except ValueError:
            continue
        if isinstance(per, dict) and per.get("fetched"):
            ratios.append(float(per.get("yield", 0.0)))
            fetched.append(int(per["fetched"]))
    if len(ratios) < 3:
        return {"status": "UNMEASURED", "n_runs": len(ratios),
                "why": f"only {len(ratios)} logged run(s) for {source}; a trend needs at least 3"}
    head, tail = ratios[:max(1, len(ratios) // 3)], ratios[-max(1, len(ratios) // 3):]
    first, last = sum(head) / len(head), sum(tail) / len(tail)
    falling = last < first * 0.6
    flat_fetch = max(fetched[-last_n:]) <= min(fetched[-last_n:]) * 1.5
    return {
        "status": "MEASURED", "source": source, "n_runs": len(ratios),
        "ratios": [round(r, 4) for r in ratios[-last_n:]],
        "fetched": fetched[-last_n:],
        "early_mean_yield": round(first, 4), "recent_mean_yield": round(last, 4),
        "falling": falling, "fetch_flat": flat_fetch,
        "verdict": ("SATURATING -- yield fell while fetch volume stayed flat, so the runs are "
                    "re-reading a corpus the seen-ledger already holds"
                    if falling and flat_fetch else
                    "NOT SATURATING on this window"),
    }


def recommend(organ: str, *, runs_per_day: float, regime: str,
              evidence: str, upstream_publications_per_day: float | None = None,
              yield_ratio_trend: dict[str, Any] | None = None) -> CadenceVerdict:
    """One organ's cadence verdict. Never cuts a FLOOR_PROTECTED organ, whatever the arithmetic."""
    if any(p in organ for p in FLOOR_PROTECTED):
        return CadenceVerdict(
            organ=organ, regime="SAFETY_FLOOR", runs_per_day_now=runs_per_day,
            runs_per_day_recommended=runs_per_day, protected=True,
            why=("SAFETY FLOOR -- bought for the tail it prevents, not for information yield. "
                 "'Found nothing today' is the success case, so yield arithmetic does not apply "
                 "and this module cannot cut it"),
            evidence=evidence)
    if regime not in REGIMES:
        raise ValueError(f"unknown regime {regime!r}; valid: {REGIMES}")

    if regime == "SATURATING":
        rec = max(1.0, round(runs_per_day / 3.0))
        why = ("SATURATING: the marginal run re-reads a corpus the seen-ledger already holds. "
               "Only new TERRITORY or more ELAPSED TIME moves the ratio, and elapsed time is "
               "exactly what a lower cadence buys")
    elif regime == "PUBLICATION_RATE_LIMITED":
        pub = upstream_publications_per_day if upstream_publications_per_day else 1.0
        rec = max(1.0, min(runs_per_day, round(pub)))
        why = (f"PUBLICATION-RATE-LIMITED: upstream produces ~{pub:g}/day. Polling faster than "
               "the source publishes cannot mint information, only calls")
    elif regime == "EVENT_DRIVEN":
        rec = max(1.0, round(runs_per_day / 4.0))
        why = ("EVENT-DRIVEN: the correct trigger is the state change, not the clock. The timer "
               "should be a fallback heartbeat so a missed event still gets caught, not the "
               "primary path")
    else:
        rec = runs_per_day
        why = ("UNMEASURED: no yield instrument exists for this organ, so its cadence is an "
               "opinion. UNKNOWN is not a reason to cut and not a reason to raise -- instrument "
               "it first (L1.41)")

    if yield_ratio_trend and yield_ratio_trend.get("status") == "MEASURED":
        evidence = f"{evidence} | trend: {yield_ratio_trend['verdict']}"
    return CadenceVerdict(organ=organ, regime=regime, runs_per_day_now=runs_per_day,
                          runs_per_day_recommended=float(rec), why=why, evidence=evidence)


def recommend_all(root: Path | None = None) -> dict[str, Any]:
    """The desk's current cadence verdicts, each grounded in a measurement or declared UNMEASURED.

    The organ list and its regimes are DECLARED here rather than inferred from the crontab,
    because regime is an economic judgement about the upstream and cannot be read off a schedule
    string -- but every declaration carries the evidence that justifies it, and an organ with no
    evidence is UNMEASURED rather than quietly cut.
    """
    trend = miner_yield_trend(root)
    organs = [
        recommend("scripts/mine_research_queue.py", runs_per_day=6.0, regime="SATURATING",
                  evidence=("measured 2026-08-05/06: bilibili yield 0.1135 -> 0.0292 across one "
                            "day on FLAT fetch (~950/run); two runs 7 minutes apart collapsed to "
                            "0.0011 while a pair 6 hours apart recovered to 0.0292 -- yield is a "
                            "function of ELAPSED TIME, not of run count"),
                  yield_ratio_trend=trend),
        recommend("scripts/kimi_hunter.py", runs_per_day=8.0,
                  regime="PUBLICATION_RATE_LIMITED", upstream_publications_per_day=2.0,
                  evidence=("external research/source ecosystems publish on their own clock; the "
                            "deep variant already runs 2x/week for depth, so the 3-hourly shallow "
                            "pass is polling a slower upstream eight times a day")),
        recommend("scripts/run_cro.py", runs_per_day=4.0, regime="PUBLICATION_RATE_LIMITED",
                  upstream_publications_per_day=1.0,
                  evidence=("measured from docs/research/recommendation_ledger.json: source 'cro' "
                            "produced 7 of 411 rows (1.7%) while scheduled 4x/day. The seat's "
                            "input is the desk's own artifact state, which changes on commits and "
                            "daily measurements, not on a 6-hour clock")),
        recommend("scripts/run_wiring_agent.py", runs_per_day=4.0, regime="EVENT_DRIVEN",
                  evidence=("its input is repository state; repo state changes on COMMITS. Four "
                            "timed passes a day is a poor approximation of a commit hook and "
                            "spends an LLM call each time whether or not anything changed")),
        recommend("scripts/build_enforcement_matrix.py", runs_per_day=4.0, regime="EVENT_DRIVEN",
                  evidence=("derives the law<->check matrix from source files; changes only when "
                            "a check or law is added, which is a commit event")),
    ]
    cut = sum(v.runs_per_day_now - v.runs_per_day_recommended for v in organs if not v.protected)
    return {
        "generated_utc": datetime.now(tz=UTC).isoformat(timespec="seconds"),
        "miner_yield_trend": trend,
        "verdicts": [v.as_dict() for v in organs],
        "llm_runs_per_day_saved": round(
            sum(v.runs_per_day_now - v.runs_per_day_recommended
                for v in organs if not v.protected
                and any(k in v.organ for k in ("cro", "kimi", "wiring", "enforcement"))), 2),
        "total_runs_per_day_saved": round(cut, 2),
        "law": ("Cadence is READ off yield, never argued. Safety floors are exempt by "
                "construction: a quiet watchdog is a working watchdog."),
        "authority": ("RECOMMENDS ONLY. ops/crontab.manifest is the authoritative schedule and a "
                      "human installs it. An advisor that could rewrite the schedule could "
                      "silently disable an organ nobody knew was load-bearing."),
    }
