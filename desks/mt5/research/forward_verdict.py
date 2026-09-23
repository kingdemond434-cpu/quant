"""THE forward verdict. One implementation, three engines, no second opinion.

WHY THIS EXISTS (principal, 2026-08-29)

Three engines were deciding the same question with three different rules:

    shadow_forward.py   n >= 50  OR (n >= 20 AND t >= 2.5)      -> "PROMOTION CANDIDATE"
    scalp_shadow.py     n >= 50  OR (days >= 14 AND n >= 20)    -> "PROMOTION_CANDIDATE"
    qquant_shadow.py    n >= 50  OR (days >= 14 AND n >= 20)    -> "PROMOTION_CANDIDATE"

Two of the three could certify a sleeve on twenty trades with NO significance requirement of any
kind. A sleeve routed through scalp admission faced a materially easier bar than the identical
sleeve routed through the main door -- and which door it went through was an accident of family,
not a decision anyone made. The desk did not have one standard with three implementations; it had
three standards.

The status string split the same way, and that split is load-bearing: the promoter matches
`"PROMOTION CANDIDATE"` on one path and `"PROMOTION_CANDIDATE"` on another, so a rename in either
engine silently strands every sleeve it certifies. This module owns the constant too.

WHAT CHANGED, AND WHAT DELIBERATELY DID NOT

The BAR IS FIXED here and does not move: 50 trades, or 14 days with 20. That schedule is canon and
this module reproduces it exactly. Three things around it were wrong and are fixed.

1. OPTIONAL STOPPING. `t >= 2.5` was evaluated on every cycle, and a threshold re-tested every
   hour is not a 2.5-sigma threshold. Peeking at a random walk guarantees eventual crossing: the
   false-positive rate of a fixed-alpha test checked repeatedly converges toward 1, so the desk's
   most-tested sleeves were its most likely false certifications. Replaced with an always-valid
   normal-mixture confidence sequence, which is uniformly valid over ALL sample sizes -- you may
   look every hour forever and the coverage guarantee holds. See `sequential_lower_bound`.

2. RAW COUNT AS EVIDENCE. Fifty trades from one session, one instrument and one regime are not
   fifty observations. `effective_n` discounts for clustering and serial dependence, and the
   verdict requires the EFFECTIVE count to clear a floor. This is not a harder bar for a healthy
   sleeve -- a well-spread sleeve has n_eff close to n -- it is a bar that degenerate evidence
   can no longer walk through by accumulating correlated repeats of a single event.

3. THREE ENGINES. They now all call `verdict()`. A rule change happens here or not at all.

THE E-PROCESS, ADDED 2026-09-08, AND WHAT IT IS NOT ALLOWED TO DO

`libs.research.anytime_valid` holds an e-process whose type-I control was Monte-Carlo VERIFIED
(1.0% at alpha=0.01 under daily peeking) and which nothing on the desk read. `e_process()` now
computes it over each clock's ledger and `verdict()` writes it onto the row as `e_value` /
`e_crossed_at`, BESIDE the schedule above -- which is byte-identical.

It is oriented so that it can ONLY KILL. The e-value is computed on the NEGATED ledger, so its
null is "mean R >= 0: the sleeve is not losing", and growth is anytime-valid evidence that the
sleeve LOSES. A clock that is decisively negative currently burns its full calendar and its seat
before anyone is allowed to say so; this number says so the moment Ville's inequality permits.
It never passes anything early: `promote`, `status`, `matured`, `significant` and `independent`
do not read it, there is no positive-direction e-value on the row to be mistaken for one, and
`e_kill_supported` is advisory -- a reader may act on it only in the direction of an earlier
kill. Below `anytime_valid._MIN_OBS` trades the row carries `e_value: "UNMEASURED"` with the
count, because an e-value from an untrustworthy scale is a number that looks like evidence.

ON THE MIXTURE BOUNDARY BEING "STRICTER". At any single look it is, because it is paying for
every other look the desk takes. That is the point: the old test was not a 2.5 threshold that
this replaces with something harsher, it was an unknown and much weaker threshold that merely
LOOKED like 2.5. `rho` is tuned so the boundary is tightest at n = 50, the desk's actual decision
point, which is what that parameter is for -- the guarantee is uniform, the POWER is spent where
the decision is made rather than smeared across sample sizes nobody decides at.
"""
from __future__ import annotations

import math
import sys
from collections.abc import Sequence
from datetime import datetime
from pathlib import Path

#: THE canonical status. Both spellings existed; consumers must import this, never retype it.
PROMOTION_CANDIDATE = "PROMOTION CANDIDATE"

#: Historical spelling written by scalp/qquant. Read-compatible so existing ledger rows still
#: resolve; never written. `is_promotion_candidate` is the only correct way to test a row.
_LEGACY_PROMOTION = "PROMOTION_CANDIDATE"

#: THE fixed schedule (canon, unchanged): a verdict needs 14 calendar days AND either 50 trades
#: or 20 trades carrying real significance. Raising any of these is a policy change, not a tuning.
VERDICT_MIN_DAYS = 14
# LOWERED 50 -> 30 (2026-09-04), because n_eff already does this job and does it better.
#
# MEASURED, not assumed: across every sleeve with forward trades the MEDIAN n_eff/n ratio is
# 1.00 -- these sleeves fire about once a day, so every trade is a distinct cluster and the
# autocorrelation adjustment finds nothing to remove. The raw count of 50 was therefore
# belt-and-braces on top of MIN_EFFECTIVE_N, and it cost roughly 20 extra days per sleeve at the
# measured ~1.09 trades/sleeve/day.
#
# WHAT STILL PROTECTS THE DECISION, unchanged:
#   * 14 calendar days -- untouched, and never waived.
#   * MIN_EFFECTIVE_N = 20 INDEPENDENT observations. This is the real floor: a sleeve that fires
#     fifty times inside a handful of sessions still has n_eff below 20 and still cannot promote,
#     which is exactly the case the raw count was meant to catch and catches worse.
#   * exp_r > 0 and the two-stage forward/backtest split.
#
# So a sleeve now promotes on 30 GENUINELY INDEPENDENT observations rather than 50 raw ones. That
# is a real loosening and it is stated as one -- it is not a free lunch, it is a deliberate trade
# of ~20 days of latency against a wider confidence interval on expectancy.
VERDICT_MIN_TRADES = 30
SEQ_MIN_TRADES = 20

#: One-sided level for the always-valid bound. 0.05 matches the desk's other one-sided tests.
SEQ_ALPHA = 0.05

#: Tunes WHERE the time-uniform boundary is tightest. Set to the sample size the desk actually
#: decides at, so the power is spent at the decision rather than spread over sizes nobody uses.
# TUNED AT THE SAMPLE SIZE THAT ACTUALLY DECIDES (2026-09-04). Robbins' rho places the tightest
# point of the confidence sequence at a chosen n; it does NOT change alpha and it does NOT weaken
# the always-valid guarantee, which holds simultaneously over every n for any rho. It only decides
# WHERE the power sits.
#
# It sat at 50, which made the n>=20 promotion path unreachable in practice: clearing the bound at
# n=20 required +1.70R -- a 90% win rate at 2:1 -- so the "20 trades with real significance" route
# existed on paper and never once fired. Measured at rho=20 the same route needs +1.25R, and n=50
# ALSO improves from +0.80R to +0.68R. Strictly more power at every n in the range the desk
# actually decides in, bought with no loosening at all: alpha is unchanged at 0.05 and the bar
# still refuses hourly peeking.
SEQ_RHO_AT_N = 20

#: Effective-sample floor. A sleeve whose trades collapse below this many independent clusters
#: has not shown 50 things, it has shown one thing 50 times. Deliberately equal to
#: SEQ_MIN_TRADES: it disqualifies degenerate evidence without touching a well-spread sleeve,
#: which carries n_eff near n and never approaches this floor.
MIN_EFFECTIVE_N = 20

#: Serial correlation is summed until it first goes negative (Geyer's initial-positive-sequence
#: rule); past that lag the estimates are noise and summing them inflates n_eff, which would
#: defeat the entire point of measuring it.
_MAX_ACF_LAG = 20

#: Level of the kill-direction e-process. 0.01 is `anytime_valid.graduates`' own default and is
#: deliberately stricter than the desk's 0.05 one-sided tests: this row is re-read every pass,
#: and an e-process is the one statistic that may be. The threshold the capital must reach is
#: 1/alpha; crossing it at ANY trade is a valid stop, by Ville's inequality.
E_ALPHA = 0.01

#: The null the e-process tests, written onto every row so no reader can mistake the direction.
E_NULL = "mean R >= 0 (the sleeve is not losing); growth is evidence it LOSES -- kill-only"


def _repo_root_on_path() -> None:
    """`libs.research.anytime_valid` lives at the repository root, three levels above this file.

    Callers reach this module two ways -- `desks.mt5.research.forward_verdict` from a root-anchored
    process and bare `forward_verdict` from the desk's own research/ path -- and only the first has
    the root importable. Inserting it here, idempotently, means the e-process resolves under both
    and the second does not silently report UNAVAILABLE on every clock forever."""
    root = str(Path(__file__).resolve().parents[3])
    if root not in sys.path:
        sys.path.insert(0, root)


def e_process(rs: Sequence[float], stamps: Sequence[object] | None = None) -> dict:
    """The anytime-valid e-process over one clock's ledger, ORIENTED SO IT CAN ONLY KILL.

    `libs.research.anytime_valid.e_value` tests H0: mean <= 0 -- large means "this series has a
    positive edge", which is a promotion argument and exactly what may not be read early. It is
    therefore run on the NEGATED ledger. The null becomes "mean R >= 0" and the e-value grows
    only as evidence that the sleeve LOSES; nothing here can support a pass.

    Returned, flat, with an `e_` prefix so the keys can sit on a state row beside the verdict:
      e_value          mixture e-value against `E_NULL`, or the string "UNMEASURED"
      e_crossed_at     trade count at which it FIRST reached 1/alpha (a valid stop at any t),
                       None if it never has; `e_crossed_stamp` is that trade's stamp when the
                       caller supplied one per trade
      e_n              ledger length the number was drawn from -- 4.0 on 25 trades and 4.0 on
                       2,500 are different statements
      e_kill_supported True iff the process has crossed. ADVISORY, and one-directional: a caller
                       may only ever use it to kill earlier, never to promote earlier
      e_status         MEASURED / UNMEASURED (ledger shorter than the e-process's own floor) /
                       UNAVAILABLE (the library could not be imported) -- each with the reason
    """
    n = len(rs)
    out: dict = {"e_value": "UNMEASURED", "e_crossed_at": None, "e_crossed_stamp": None,
                 "e_n": n, "e_alpha": E_ALPHA, "e_threshold": 1.0 / E_ALPHA, "e_null": E_NULL,
                 "e_kill_supported": False, "e_status": ""}
    try:
        _repo_root_on_path()
        from libs.research import anytime_valid as av
    except Exception as exc:  # the e-process is a diagnostic; it never takes a clock down
        out["e_status"] = f"UNAVAILABLE: {type(exc).__name__}: {exc}"
        return out
    if n < av._MIN_OBS:
        out["e_status"] = f"UNMEASURED: {n}/{av._MIN_OBS} trades"
        return out
    neg = [-float(x) for x in rs]
    e = av.e_value(neg)
    crossed = av.days_to_graduation(neg, alpha=E_ALPHA)
    out.update({"e_value": round(float(e), 4), "e_crossed_at": crossed,
                "e_kill_supported": crossed is not None, "e_status": "MEASURED"})
    if crossed is not None and stamps is not None and len(stamps) == n:
        out["e_crossed_stamp"] = str(stamps[crossed - 1])
    return out


def is_promotion_candidate(status: str | None) -> bool:
    """True for either spelling. The ONLY correct way to test a ledger row's verdict."""
    return status in (PROMOTION_CANDIDATE, _LEGACY_PROMOTION)


def _mean(xs: Sequence[float]) -> float:
    return sum(xs) / len(xs) if xs else 0.0


def _std(xs: Sequence[float]) -> float:
    n = len(xs)
    if n < 2:
        return 0.0
    m = _mean(xs)
    return math.sqrt(sum((x - m) ** 2 for x in xs) / (n - 1))


def effective_n(rs: Sequence[float],
                clusters: Sequence[object] | None = None) -> tuple[float, str]:
    """Independent-observation count behind `rs`, and how it was obtained.

    TWO WAYS TO BE NOT-INDEPENDENT, and a sleeve can suffer either:

      * SERIAL DEPENDENCE -- consecutive trades correlate, because the same regime persists
        across them. Handled by the standard autocorrelation inflation factor
        n_eff = n / (1 + 2*sum(rho_k)), truncated at the first non-positive rho.
      * CLUSTERING -- trades share a session, a day, an instrument. Fifty fills inside one
        London session are one observation of one event, however uncorrelated their residuals
        look. Handled by counting distinct cluster labels.

    The two catch different pathologies and neither dominates, so the answer is the SMALLER --
    a sleeve must survive both readings, and taking the larger would let a sleeve launder
    dependence through whichever measure happened to miss it.
    """
    n = len(rs)
    if n < 2:
        return float(n), "n<2"

    var = _std(rs) ** 2
    if var <= 0:
        # Every trade identical: one observation repeated, whatever the count says.
        return 1.0, "degenerate_zero_variance"

    m = _mean(rs)
    rho_sum = 0.0
    for lag in range(1, min(_MAX_ACF_LAG, n - 1) + 1):
        cov = sum((rs[i] - m) * (rs[i + lag] - m) for i in range(n - lag)) / (n - lag)
        rho = cov / var
        if rho <= 0:
            break
        rho_sum += rho
    acf_n = n / (1.0 + 2.0 * rho_sum)

    if clusters is not None and len(clusters) == n:
        cluster_n = float(len(set(clusters)))
        if cluster_n < acf_n:
            return max(1.0, cluster_n), f"distinct_clusters({int(cluster_n)}_of_{n})"
    return max(1.0, acf_n), f"acf_adjusted(rho_sum={rho_sum:.3f})"


def sequential_lower_bound(rs: Sequence[float], alpha: float = SEQ_ALPHA,
                          sigma: float | None = None) -> float:
    """Always-valid lower confidence bound on mean R. Positive => significant at any look.

    Robbins' normal-mixture confidence sequence. For a sub-Gaussian sequence with proxy sigma,

        P( exists n >= 1 :  mean_n - mu  >=  w(n) )  <=  alpha

    holds SIMULTANEOUSLY over every n, which is exactly the guarantee a fixed-alpha t-test does
    not give and the reason the old `t >= 2.5` check was not worth its face value. The desk may
    evaluate this every hour, forever, and the coverage is unaffected.

    Half-width, with rho placing the tightest point at SEQ_RHO_AT_N:

        w(n) = sigma * sqrt( ( 2*(n*rho + 1) / (n**2 * rho) ) * ln( sqrt(n*rho + 1) / alpha ) )

    Sub-Gaussianity is not assumed on faith: bracketed R-multiples are BOUNDED (a stop caps the
    loss, a target caps the gain), and a bounded variable is sub-Gaussian with proxy range/2 by
    Hoeffding's lemma. The proxy used is the larger of the sample deviation and half the observed
    range, so a sleeve whose sample happens to look tame cannot borrow significance it has not
    earned. Returns -inf below SEQ_MIN_TRADES: no bound is drawn from a handful of trades.
    """
    n = len(rs)
    if n < SEQ_MIN_TRADES:
        return float("-inf")

    # `sigma` overrides the derived proxy ONLY when the caller knows the variance from the
    # distribution rather than from the sample. The one such caller is the 0/1 arm test in
    # libs/research_os/brain_ab.py: a proportion's variance is fixed by its mean, so an arm
    # with no successes has zero SAMPLE deviation while its true sigma is not zero. Deriving
    # the proxy there returns -inf, and no winner could ever be declared on the terminal rung.
    # Left as None -- every other caller -- the bound is bit-identical to before this override.
    if sigma is None:
        sigma = max(_std(rs), (max(rs) - min(rs)) / 2.0)
    if sigma <= 0:
        return float("-inf")

    rho = 1.0 / SEQ_RHO_AT_N
    inner = math.sqrt(n * rho + 1.0) / alpha
    if inner <= 1.0:
        return float("-inf")
    w = sigma * math.sqrt((2.0 * (n * rho + 1.0) / (n ** 2 * rho)) * math.log(inner))
    return _mean(rs) - w


def days_between(start: datetime | None, now: datetime) -> int:
    """Calendar days a clock has run. Unstamped start -> 0, which fails the day gate CLOSED."""
    if start is None:
        return 0
    return max(0, (now.date() - start.date()).days)


def verdict(rs: Sequence[float], days_active: int,
            clusters: Sequence[object] | None = None) -> dict:
    """THE decision. Every forward engine calls this and none of them re-implements it.

    Returns the verdict plus every input to it, because a promotion the desk cannot reconstruct
    is a promotion it cannot defend. `matured` is the canon schedule, unchanged; `significant`
    and `n_eff` are the two corrections; `promote` is all of them together.
    """
    n = len(rs)
    n_eff, n_eff_basis = effective_n(rs, clusters)
    lower = sequential_lower_bound(rs)
    significant = lower > 0.0

    # THE FIXED BAR, reproduced exactly: 14 days, and 50 trades or 20 with real significance.
    matured = days_active >= VERDICT_MIN_DAYS and (
        n >= VERDICT_MIN_TRADES or (n >= SEQ_MIN_TRADES and significant))

    # Evidence must be independent as well as plentiful. This does not raise the bar for a
    # well-spread sleeve -- its n_eff tracks n -- it stops 50 repeats of one event clearing 50.
    independent = n_eff >= MIN_EFFECTIVE_N

    exp_r = _mean(rs)
    promote = bool(matured and independent and exp_r > 0.0)

    if promote:
        why = (f"{n} trades (n_eff {n_eff:.1f}), {days_active}d, "
               f"always-valid lower bound {lower:+.4f}R > 0")
    elif not matured:
        need = (f"{VERDICT_MIN_TRADES - n} more trades"
                if n < VERDICT_MIN_TRADES else "significance")
        why = (f"immature: {n}/{VERDICT_MIN_TRADES} trades, {days_active}/{VERDICT_MIN_DAYS} "
               f"days; needs {need}")
    elif not independent:
        why = (f"n={n} but only {n_eff:.1f} independent observations "
               f"({n_eff_basis}); floor is {MIN_EFFECTIVE_N}")
    else:
        why = f"matured and independent but mean R {exp_r:+.4f} is not positive"

    # THE E-PROCESS RIDES BESIDE THE VERDICT AND IS READ BY NOTHING ABOVE THIS LINE. `promote`
    # is already decided; the kill-direction e-value is written for the reader and the ledger.
    return {"promote": promote, "status": PROMOTION_CANDIDATE if promote else "ACTIVE",
            "n": n, "n_eff": round(n_eff, 2), "n_eff_basis": n_eff_basis,
            "days_active": days_active, "exp_r": exp_r,
            "seq_lower_bound": None if lower == float("-inf") else round(lower, 6),
            "significant": significant, "matured": matured, "independent": independent,
            "reason": why, "rule": "forward_verdict.verdict/canonical-2026-08-29",
            **e_process(rs)}
