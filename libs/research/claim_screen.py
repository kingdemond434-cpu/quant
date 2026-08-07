"""EXTERNAL CLAIM SCREEN -- mechanise the checks that killed three Reddit posts by hand.

The desk ingests claims constantly: kimi_hunter, the prospector, the literature miner, forum
sweeps, and the principal forwarding a screenshot. Every one arrives as a headline number with an
implied "should we build this?", and until now the answer came from someone eyeballing it. That
does not scale, and worse, it is not REPRODUCIBLE -- the same claim can pass on a tired Tuesday and
fail on a sharp Wednesday.

These five checks are exactly the ones that resolved three real claims on 2026-08-07, written down
so the next claim meets the same bar rather than the same mood.

WHAT THIS IS NOT. It does not decide whether an edge is real -- only the gauntlet does that, on
data. This is a CHEAP PRE-FILTER that answers "is this claim even worth spending a backtest on?",
and its verdicts are about the CLAIM, never about the market. A claim that passes every check here
has earned a queue place, nothing more.

**AND IT MUST NEVER BE USED TO ADMIT.** A clean screen is the ABSENCE of a detected defect, which
is not evidence of quality (L1.28a). The asymmetry is deliberate: REJECT is informative, PASS is
merely "no cheap tell found".
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field


@dataclass(frozen=True)
class Finding:
    """One detected defect in a claim."""

    code: str
    severity: str          # "FATAL" | "SEVERE" | "NOTE"
    detail: str


@dataclass(frozen=True)
class ClaimVerdict:
    """The screen's answer. `findings` carries the reasoning, never just a boolean."""

    verdict: str           # "REJECT" | "SUSPECT" | "NO-CHEAP-TELL"
    findings: tuple[Finding, ...] = field(default_factory=tuple)

    @property
    def fatal(self) -> tuple[Finding, ...]:
        return tuple(f for f in self.findings if f.severity == "FATAL")


def round_ratio_tell(counts: list[tuple[int, int]], *, places: int = 4) -> Finding | None:
    """FABRICATION TELL: reported ratios that are EXACTLY round across several sample sizes.

    THE CASE THIS CAME FROM. A "WR TARGET DASH" claiming 5-minute BTC prediction reported
    6264/8640 = 72.500000%, 1512/2016 = 75.000000%, 27/36 = 75.000000%. Hitting a round percentage
    to six places on three different denominators does not happen to a real system -- those are
    percentages BACKED INTO counts, written before they were measured.

    Real measurement produces untidy numbers. The check is therefore not "is the rate high" (a high
    rate can be real) but "is the rate too CLEAN for its sample size", which is a much harder thing
    to fake accidentally and a much easier thing to detect.
    """
    exact = []
    for w, n in counts:
        if n <= 0 or w < 0 or w > n:
            continue
        pct = 100.0 * w / n
        if n >= 20 and abs(pct - round(pct, 2)) < 10.0 ** (-places):
            exact.append(f"{w}/{n}={pct:.6f}%")
    if len(exact) >= 2:
        return Finding(
            "round-ratio-fabrication", "FATAL",
            f"{len(exact)} reported ratios are EXACTLY round across different denominators "
            f"({', '.join(exact)}). Real measurement is untidy; these are percentages backed into "
            "counts. Treat every other number from this source as written rather than measured.")
    return None


def denominator_is_theoretical_max(counts: list[tuple[int, int]], per_day: int) -> Finding | None:
    """A denominator equal to the THEORETICAL MAXIMUM means zero gaps, ever.

    8640 = 288 x 30, 2016 = 288 x 7, 288 = 24h x 12. A live system has outages, missed bars,
    maintenance windows and restarts; a denominator that is exactly `per_day x whole days` is a
    calendar, not a log. Separate from the round-ratio tell because a claim can fail this while
    reporting untidy percentages -- and it is the cheaper of the two to check.
    """
    if per_day <= 0:
        return None
    hits = [n for _w, n in counts if n > 0 and n % per_day == 0 and n // per_day >= 1]
    if len(hits) >= 2:
        return Finding(
            "denominator-is-calendar", "SEVERE",
            f"{len(hits)} denominators are exact multiples of {per_day}/day ({hits}). That is the "
            "theoretical maximum sample -- no missed bars, no downtime, no restarts, ever. A real "
            "log does not look like a calendar.")
    return None


def oos_beats_is(is_metric: float, oos_metric: float, *, margin: float = 0.05) -> Finding | None:
    """OUT-OF-SAMPLE BEATING IN-SAMPLE MEANS THE SPLIT WAS EASIER, NOT THE STRATEGY BETTER.

    THE CASE: a claim of 39.2% annually on "unseen" 2020-2026 against 26.7% on 2015-2019 training
    data. Out-of-sample is where a strategy DEGRADES -- that is what the split is for. When it
    improves, the ordinary explanations are that the held-out period was simply kinder, that the
    split leaked, or that the strategy was iterated against the "unseen" data.

    2020-2026 contained a historic bull run and 2015-2019 did not, so that claim measured the
    regime and reported it as validation. The number that looked like the strongest evidence in the
    post is the one that voids it.
    """
    if is_metric <= 0 or oos_metric <= is_metric * (1.0 + margin):
        return None
    return Finding(
        "oos-exceeds-is", "FATAL",
        f"out-of-sample ({oos_metric:g}) exceeds in-sample ({is_metric:g}) by "
        f"{(oos_metric / is_metric - 1) * 100:.0f}%. Out-of-sample is where a real strategy "
        "DEGRADES. An improvement means the held-out window was easier, the split leaked, or the "
        "strategy was tuned against it -- so the validation validated nothing.")


def missing_benchmark(claimed_cagr: float, benchmark_cagr: float | None) -> Finding | None:
    """A return with no benchmark is not a result.

    THE CASE: 17.9% and 19.1% annually from 2015, over a window in which simply holding a broad
    index compounded strongly on its own. This is the desk's own K7, and it is the criterion
    nobody applies to their own work -- a strategy that does not beat holding the asset is not an
    edge, it is a costlier way to be long.
    """
    if benchmark_cagr is None:
        return Finding(
            "no-benchmark", "SEVERE",
            f"{claimed_cagr:.1%} annually is reported against NOTHING. Over any window the "
            "comparison is buy-and-hold, and it is missing here -- which is the desk's own K7, "
            "and the criterion authors skip most reliably on their own results.")
    if claimed_cagr <= benchmark_cagr:
        return Finding(
            "loses-to-benchmark", "FATAL",
            f"{claimed_cagr:.1%} does not beat holding ({benchmark_cagr:.1%}). Not an edge -- a "
            "costlier way to be long.")
    return None


def cost_infeasible(trades_per_day: float, round_trip_bp: float,
                    typical_move_bp: float) -> Finding | None:
    """Does the strategy's own turnover eat the move it is trying to capture?

    THE CASE: predicting every 5-minute BTC candle is 288 round trips a day. At a 10bp round trip
    that is 28.8% OF NOTIONAL PER DAY in fees, against a 5-minute candle whose typical range is
    single-digit basis points. The claimed win rate never gets a chance to matter -- the strategy
    is arithmetically dead before the signal is evaluated, and that is worth computing FIRST
    because it is the cheapest possible refutation.
    """
    if trades_per_day <= 0 or round_trip_bp <= 0:
        return None
    daily_cost_bp = trades_per_day * round_trip_bp
    if typical_move_bp > 0 and round_trip_bp >= typical_move_bp:
        return Finding(
            "cost-exceeds-move", "FATAL",
            f"{round_trip_bp:g}bp round trip against a typical move of {typical_move_bp:g}bp: the "
            f"fee is larger than the thing being predicted. At {trades_per_day:g} trades/day that "
            f"is {daily_cost_bp / 100:.1f}% of notional PER DAY in cost.")
    if daily_cost_bp >= 500:                      # >5%/day is not survivable by any edge
        return Finding(
            "turnover-infeasible", "SEVERE",
            f"{trades_per_day:g} trades/day x {round_trip_bp:g}bp = {daily_cost_bp / 100:.1f}% of "
            "notional per day in cost. No win rate survives that.")
    return None


def undeflated_sharpe(sharpe: float, years: float, *, assumed_configs: int = 10) -> Finding | None:
    """Is the claimed Sharpe distinguishable from noise once the search is priced in?

    Lo (2002): SE(SR) ~ sqrt((1 + SR^2/2)/T). A Sharpe of 2.17 over 2.8 years gives t = 1.98 and a
    95% interval of roughly [0.02, 4.32] -- an interval that effectively touches zero on ONE trial.

    `assumed_configs` defaults to 10 rather than 1 deliberately. Nobody arrives at an "ML entry +
    regime filter + crash filter" construction on the first attempt, and assuming a single trial
    would hand every claim the most flattering possible bar. Ten is conservative in the direction
    that costs the desk nothing.
    """
    if sharpe <= 0 or years <= 0:
        return None
    se = math.sqrt((1.0 + sharpe * sharpe / 2.0) / years)
    t = sharpe / se
    bar = math.sqrt(2.0 * math.log(assumed_configs)) if assumed_configs > 1 else 1.96
    if t < bar:
        return Finding(
            "undeflated-sharpe", "FATAL",
            f"Sharpe {sharpe:g} over {years:g}y gives t={t:.2f}; the hurdle at {assumed_configs} "
            f"configurations is {bar:.2f}. 95% interval on the Sharpe is "
            f"[{sharpe - 1.96 * se:.2f}, {sharpe + 1.96 * se:.2f}] -- it includes values at which "
            "there is no edge, so nothing can be sized on it.")
    return None


def screen(findings: list[Finding | None]) -> ClaimVerdict:
    """Collect findings into a verdict.

    THREE STATES, AND THE THIRD IS NAMED CAREFULLY. "NO-CHEAP-TELL" is not "PASS": it says the
    cheap screens found nothing, which is the absence of a detected defect and not evidence of
    quality. Calling it PASS would let a claim that merely avoided these five tells enter the
    funnel wearing a verdict it did not earn (L1.28a).
    """
    found = tuple(f for f in findings if f is not None)
    if any(f.severity == "FATAL" for f in found):
        return ClaimVerdict("REJECT", found)
    if found:
        return ClaimVerdict("SUSPECT", found)
    return ClaimVerdict("NO-CHEAP-TELL", found)


def render(v: ClaimVerdict) -> str:
    """One block a human or an organ can read."""
    head = {
        "REJECT": "REJECT -- a fatal tell was found; do not spend a backtest on this",
        "SUSPECT": "SUSPECT -- no fatal tell, but defects worth resolving before any work",
        "NO-CHEAP-TELL": ("NO CHEAP TELL -- the five screens found nothing. This is the ABSENCE of "
                          "a detected defect, NOT evidence the claim is good."),
    }[v.verdict]
    return "\n".join([head, *(f"  [{f.severity}] {f.code}: {f.detail}" for f in v.findings)])
