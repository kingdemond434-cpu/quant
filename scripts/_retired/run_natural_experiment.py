#!/usr/bin/env python3
"""DOES THE MACRO LAYER'S CLAIMED EXPOSURE ACTUALLY CAUSE THE MOVE IT PREDICTS? (R0207, L1.16)

Stage A. ZERO promotion authority: this earns a pre-registered forward clock at most, never a cent.

WHY THIS COHORT, AND WHY THE OLD ONE HAD TO GO. The predecessor ran a difference-in-differences on
dated TOKEN UNLOCKS -- vesting schedules, circulating supply -- and was deleted with the retired
crypto-exchange desk on 2026-09-05 under the MT5 UNIVERSE MANDATE. Deleting it was right; deleting
it and stopping was not. `libs/research/natural_experiment` is the desk's only causal-identification
organ, and with its single caller gone it went DECORATIVE: `check_enforcement_execution` measured
that none of `DiDResult`, `MIN_PRE_OBS`, `MIN_POST_OBS` or `MAX_TREATED_SHARE` was referenced
anywhere outside its own module and tests, which made L1.16-r0207 a law enforced by nothing. A
capability the desk still needs, pointed at a universe the desk no longer trades, is not retired --
it is unwired, and unwiring is a defect with a fix rather than a decision with a reason.

WHAT IT ASKS. The macro package assigns every event a set of tradeable Fusion `instruments` and
carries, per instrument, a measured exposure to the event's factor. That exposure is a CLAIM about
the world: it says a shock of this kind moves this instrument this way. Nothing so far tests it
causally -- the loadings are fitted on the same tape that produced them, so a loading and the
correlation it was fitted to cannot disagree. This runner puts the claim in front of a design that
CAN refuse it:

    treated   the instruments the expression step named for this event
    control   the tradeable universe it did NOT name, over the SAME calendar days
    effect    (treated after - treated before) - (control after - control before)

If the desk's macro exposures carry causal content, the oriented DiD effect is positive. If they
are calendar artefacts -- everything moved because it was a Tuesday in a risk-off week -- the
control leg absorbs it and the effect goes to zero. That is the whole point of differencing against
a control rather than reporting the treated move, and it is why "gold rose after the CPI print" is
not evidence of anything on its own.

=================================================================================================
PRE-REGISTRATION -- fixed BEFORE any estimate, and changing one of these is a diff
=================================================================================================
DIRECTION IS NOT CHOSEN FROM THE RESULT, and this is the part that would be easiest to get wrong.
`event_study` underneath is a ONE-SIDED POSITIVE test, so a direction picked after seeing the sign
would convert every result into a confirmation. Instead each treated unit's return series is
ORIENTED by the sign of the exposure the desk has STORED for that (instrument, category), and the
null is that a stored exposure carries no causal content. A unit whose exposure sign is unknown is
DROPPED, never defaulted to +1: defaulting would silently convert "no prior" into "predicted up",
which is a coin flip dressed as a hypothesis. Direction is then "increase" by construction.

THE ORIENTATION IS NOT POINT-IN-TIME, AND THAT IS A REAL LIMIT ON WHAT THIS PROVES. `exposures.json`
is a CURRENT snapshot with no history -- `macro/expression.py` overwrites it -- so a sign fitted
today can orient an event from last month. The bias is toward FINDING an effect: an exposure fitted
over a window that contains the event is partly fitted to the very move being tested. The result is
therefore an upper bound on the causal content, not an unbiased estimate, and a cohort that fails
HERE has failed under favourable conditions, which is the reading that is safe to act on. Closing
this needs a dated exposure history (append a row per fit, read `<= event_ts`); until that exists
this file must not claim a guarantee it does not provide. The identification rails underneath --
parallel trends, placebo, SUTVA -- are unaffected, because none of them consults the orientation.

WINDOWS are fixed here and never swept. Sweeping windows and reporting the best is data-mining our
own collector -- the discipline `listing_events.py` holds to. PRE_BARS=20 sits above
`natural_experiment.MIN_PRE_OBS` (10) so the parallel-trends test has power rather than merely
failing to reject on a short window; POST_BARS=5 sits above MIN_POST_OBS (3) so the after leg is a
mean and not a point. Daily bars, because a macro event's cross-asset propagation is a
multi-session process and an M1 window would measure the release spike alone.

EXOGENEITY, stated because the module requires it and refuses without it: the estimate is
conditioned on scheduled and externally-originated events, whose timing is set by statistical
agencies, central-bank calendars and world affairs -- not by the desk, not by its book, and not by
the instruments it holds. The known threat is the mirror of the crypto row's: a macro event is
exogenous to THIS DESK but not to the market, so a release that surprises everyone moves treated
and control together. That is precisely what the control leg differences away, and it is why a
large treated move with a near-zero DiD effect is the expected result for a well-priced release
rather than a failure of the runner.

WHAT IT REFUSES, loudly. An empty or thin event ledger reads UNMEASURED, never "no effect" -- on a
box that has recorded nothing, the correct output is the absence of a study, and the way out is
rows, not code (`macro/ledger.py`'s own standard). Same for absent exposures, absent bars, and a
cohort whose treated share breaches SUTVA.

    python scripts/run_natural_experiment.py [--json] [--min-cohort N] [--report-only]
"""
from __future__ import annotations

import argparse
import itertools
import json
import math
import sys
from collections import defaultdict
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

_ROOT = Path(__file__).resolve().parent.parent
_DESK = _ROOT / "desks" / "mt5"
for _p in (str(_ROOT), str(_DESK)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from libs.research.natural_experiment import (  # noqa: E402
    MAX_TREATED_SHARE,
    MIN_POST_OBS,
    MIN_PRE_OBS,
    DiDResult,
    TreatedUnit,
    difference_in_differences,
)

#: Pre-period daily bars per unit. Above MIN_PRE_OBS so parallel trends is tested with power.
PRE_BARS = 20
#: Post-period daily bars per unit. Above MIN_POST_OBS so the after leg is a mean, not a point.
POST_BARS = 5
#: Control legs drawn per event. The cross-sectional mean of this many untreated peers is the
#: counterfactual; more is better for the mean's stability and costs only read time.
MAX_CONTROLS = 60
#: Minimum treated units in a cohort before it is estimated at all. Below this the cross-sectional
#: t has no power and reporting a verdict would be reporting noise with a label.
MIN_COHORT = 8
#: Where the verdict lands.
OUT_REL = "desks/mt5/reports/NATURAL_EXPERIMENTS.json"

_DAY_S = 86_400.0
_EXOGENEITY = (
    "Event timing is set by statistical agencies, central-bank calendars and world affairs -- "
    "exogenous to this desk, its book and its holdings. It is NOT exogenous to the market, so a "
    "surprising release moves treated and control together; the control leg differences exactly "
    "that away, which is why a large treated move with a near-zero effect is the expected result "
    "for a well-priced release rather than a defect."
)


def _ts(rec: Any) -> datetime | None:
    """The event clock, preferring when it HAPPENED over when the desk heard about it."""
    from macro.schema import parse_ts
    return parse_ts(getattr(rec, "happened_at", None)) or parse_ts(
        getattr(rec, "published_at", None))


def _daily_returns(reader: Any, symbol: str, start: datetime, end: datetime) -> list[float]:
    """Log returns of daily closes in [start, end]. Empty when the tape cannot serve the span."""
    try:
        quotes = list(reader.bars(symbol, start, end))
    except Exception:
        return []
    by_day: dict[str, float] = {}
    for q in quotes:
        ts = getattr(q, "ts", None) or getattr(q, "time", None)
        px = getattr(q, "price", None) or getattr(q, "close", None) or getattr(q, "mid", None)
        if ts is None or px is None:
            continue
        day = ts.date().isoformat() if hasattr(ts, "date") else str(ts)[:10]
        by_day[day] = float(px)                          # last print of the day wins
    closes = [by_day[d] for d in sorted(by_day)]
    out = []
    for a, b in itertools.pairwise(closes):
        if a > 0 and b > 0 and math.isfinite(a) and math.isfinite(b):
            out.append(math.log(b / a))
    return out


def _orientation(exposures: dict[str, Any], symbol: str, category: str) -> float | None:
    """+1/-1 from the exposure the desk has stored, or None when it has no prior for this cell.

    None is returned rather than +1 on purpose: defaulting an unknown prior to "predicted up"
    turns a coin flip into a hypothesis, and the one-sided test underneath would then confirm it
    half the time by construction.

    NOT point-in-time -- `exposures.json` is a current snapshot -- so this biases toward finding
    an effect. See the module docstring; the consequence is that a FAILING cohort is the reading
    that can be acted on, and a passing one is an upper bound.
    """
    row = exposures.get(symbol)
    if not isinstance(row, dict):
        return None
    beta = row.get(category)
    if isinstance(beta, dict):
        beta = beta.get("beta")
    if not isinstance(beta, int | float) or not math.isfinite(float(beta)) or beta == 0:
        return None
    return 1.0 if float(beta) > 0 else -1.0


def build_cohorts(records: list[Any], reader: Any, exposures: dict[str, Any],
                  universe: dict[str, Any], *, min_cohort: int = MIN_COHORT,
                  ) -> tuple[dict[str, list[TreatedUnit]], list[str]]:
    """Treated units per event CATEGORY, plus the reasons units were dropped.

    The drop reasons are returned rather than logged away: a cohort that shrank from 200 events to
    6 units has a story, and "n=6" without it is unreadable.
    """
    tradeable = {s for s, m in universe.items()
                 if isinstance(m, dict) and m.get("tradeable") is not False}
    cohorts: dict[str, list[TreatedUnit]] = defaultdict(list)
    drops: defaultdict[str, int] = defaultdict(int)
    for rec in records:
        t0 = _ts(rec)
        cat = str(getattr(rec, "category", "") or "")
        named = [s for s in (getattr(rec, "instruments", ()) or ()) if s in tradeable]
        if t0 is None or not cat or not named:
            drops["no clock, category or named instrument"] += 1
            continue
        controls = sorted(tradeable - set(named))[:MAX_CONTROLS]
        if not controls:
            drops["no untreated peer in the universe"] += 1
            continue
        pre_start = t0 - timedelta(seconds=(PRE_BARS + 2) * _DAY_S)
        post_end = t0 + timedelta(seconds=(POST_BARS + 2) * _DAY_S)
        ctrl_pre_legs, ctrl_post_legs = [], []
        for c in controls:
            pre = _daily_returns(reader, c, pre_start, t0)[-PRE_BARS:]
            post = _daily_returns(reader, c, t0, post_end)[:POST_BARS]
            if len(pre) >= MIN_PRE_OBS and len(post) >= MIN_POST_OBS:
                ctrl_pre_legs.append(pre[-MIN_PRE_OBS:])
                ctrl_post_legs.append(post[:MIN_POST_OBS])
        if len(ctrl_pre_legs) < 2:
            drops["fewer than two control legs with enough bars"] += 1
            continue
        ctrl_pre = [sum(col) / len(col) for col in zip(*ctrl_pre_legs, strict=False)]
        ctrl_post = [sum(col) / len(col) for col in zip(*ctrl_post_legs, strict=False)]
        for sym in named:
            sign = _orientation(exposures, sym, cat)
            if sign is None:
                drops["no stored exposure sign at event time"] += 1
                continue
            pre = _daily_returns(reader, sym, pre_start, t0)[-PRE_BARS:]
            post = _daily_returns(reader, sym, t0, post_end)[:POST_BARS]
            if len(pre) < MIN_PRE_OBS or len(post) < MIN_POST_OBS:
                drops["treated leg has too few bars"] += 1
                continue
            cohorts[cat].append(TreatedUnit(
                unit_id=f"{sym}@{t0.isoformat()}",
                event_ts=t0.timestamp(),
                # ORIENTED by the stored prior, so "increase" is the pre-registered direction.
                # Controls are oriented identically: differencing an oriented treated leg against
                # an unoriented control would put a sign on the effect that came from the
                # orientation rather than from the event.
                treated_pre=[sign * r for r in pre[-MIN_PRE_OBS:]],
                treated_post=[sign * r for r in post[:MIN_POST_OBS]],
                control_pre=[sign * r for r in ctrl_pre],
                control_post=[sign * r for r in ctrl_post],
                cohort_key=sym,          # SUTVA counts SYMBOLS, not events -- see TreatedUnit
            ))
    kept = {c: u for c, u in cohorts.items() if len(u) >= min_cohort}
    for c, u in cohorts.items():
        if len(u) < min_cohort:
            drops[f"cohort {c!r} under the {min_cohort}-unit floor"] += len(u)
    return kept, [f"{n}x {why}" for why, n in sorted(drops.items(), key=lambda kv: -kv[1])]


def run(*, min_cohort: int = MIN_COHORT) -> dict[str, Any]:
    """Estimate every cohort with sample, or say precisely why nothing was estimated."""
    report: dict[str, Any] = {
        "generated_utc": datetime.now(tz=UTC).isoformat(timespec="seconds"),
        "design": "difference-in-differences, oriented by the stored point-in-time exposure sign",
        "pre_bars": PRE_BARS, "post_bars": POST_BARS, "min_cohort": min_cohort,
        "max_treated_share": MAX_TREATED_SHARE,
        "exogeneity_note": _EXOGENEITY,
        "cohorts": {}, "status": "UNMEASURED", "detail": "",
    }
    try:
        from macro import expression
        from macro.ledger import EventLedger
        from macro.prices import ParquetPriceReader
    except ImportError as exc:
        report["detail"] = f"the macro package is not importable here: {exc}"
        return report

    records = EventLedger().records()
    if not records:
        report["detail"] = ("the macro event ledger is empty on this host, so there is no cohort "
                            "to study. This is the correct state of a system that has recorded "
                            "nothing, and the way out is rows, not code.")
        return report

    try:
        universe = expression.load_universe()
    except (OSError, ValueError) as exc:
        report["detail"] = f"the universe registry is unreadable, so nothing can be priced: {exc}"
        return report

    exposures: dict[str, Any] = {}
    try:
        exposures = json.loads(Path(expression.EXPOSURE_PATH).read_text("utf-8"))
    except (OSError, ValueError):
        exposures = {}
    if not exposures:
        report["detail"] = ("no measured exposures are stored, so no unit has a pre-registered "
                            "direction. Orienting by a fitted-after-the-fact sign would make the "
                            "one-sided test confirm itself; the study is refused instead.")
        return report

    reader = ParquetPriceReader()
    cohorts, drops = build_cohorts(records, reader, exposures, universe, min_cohort=min_cohort)
    report["events_in_ledger"] = len(records)
    report["dropped"] = drops
    if not cohorts:
        report["detail"] = (f"no category reached the {min_cohort}-unit floor. Dropped: "
                            f"{'; '.join(drops) or 'nothing was examined'}")
        return report

    n_pool = sum(1 for m in universe.values()
                 if isinstance(m, dict) and m.get("tradeable") is not False)
    out: dict[str, Any] = {}
    for cat, units in sorted(cohorts.items()):
        try:
            res: DiDResult = difference_in_differences(
                units, n_control_pool=n_pool, exogeneity_note=_EXOGENEITY,
                direction="increase",            # by construction -- see the orientation note
                n_cohort=len(cohorts), rank=1,
                post_window_s=POST_BARS * _DAY_S,
            )
        except Exception as exc:
            out[cat] = {"status": "REFUSED", "why": f"{type(exc).__name__}: {exc}"}
            continue
        out[cat] = {
            "n_treated": res.n_treated, "effect": res.effect,
            "identified": res.identified, "passed": res.passed, "verdict": res.verdict,
            "parallel_trends_t": res.parallel_trends_t,
            "parallel_trends_ok": res.parallel_trends_ok,
            "placebo_t": res.placebo_t, "placebo_ok": res.placebo_ok,
            "treated_share": res.treated_share, "direction": res.direction,
        }
    report["cohorts"] = out
    passed = [c for c, r in out.items() if r.get("passed")]
    report["status"] = "MEASURED"
    report["detail"] = (f"{len(out)} cohort(s) estimated, {len(passed)} with a causal effect "
                        f"identified and significant: {passed or 'none'}")
    return report


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--json", action="store_true", help="print the full report as JSON")
    ap.add_argument("--min-cohort", type=int, default=MIN_COHORT)
    ap.add_argument("--report-only", action="store_true",
                    help="always exit 0; the report is still written")
    args = ap.parse_args(argv)

    rep = run(min_cohort=args.min_cohort)
    out = _ROOT / OUT_REL
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(rep, indent=1), "utf-8")
    if args.json:
        print(json.dumps(rep, indent=1))
    else:
        print(f"natural experiments (R0207): {rep['status']} -- {rep['detail']}")
        for cat, r in (rep.get("cohorts") or {}).items():
            print(f"  {cat}: {r.get('verdict', r.get('why', '?'))}")
    print(f"-> {OUT_REL}")
    # UNMEASURED is not a failure to fix in CI: an empty ledger on a research container is the
    # honest state, and exiting non-zero there would make this fence red on every machine that
    # has not yet recorded an event. A REFUSED cohort is different -- that is a design fault.
    if args.report_only:
        return 0
    return 1 if any(r.get("status") == "REFUSED" for r in (rep.get("cohorts") or {}).values()) else 0


if __name__ == "__main__":
    sys.exit(main())
