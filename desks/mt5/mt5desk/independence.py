"""How many INDEPENDENT bets the book is actually holding.

WHY THIS EXISTS

`heat_budget(k_eff)` scales the desk's total risk with the square root of effective breadth:
portfolio drawdown for N sleeves at total heat H scales roughly as H/sqrt(k_eff), so holding
drawdown fixed lets H grow with sqrt(k_eff). Five genuinely independent sleeves are SAFER at 6%
than three correlated ones at 4%, and that is the mechanism by which this desk is supposed to
widen as it earns breadth.

IT WAS NEVER CONNECTED. The gateway called `cap_by_heat(sleeves, equity)` with no k_eff, nothing
in the repository computed one, and so `heat_budget()` returned its base 3.81% on every call
forever. The entire correlation-aware ladder was dead code, and the book was pinned to a
three-leg budget no matter how many independent edges it went on to earn. A scaling term that
nothing supplies is a constant with extra steps -- and in this case a constant that permanently
caps compounding.

    k_eff = N / (1 + (N - 1) * rho_bar)

At rho_bar = 0 this is N (fully independent). At rho_bar = 1 it is 1 (one bet wearing N names).

THE TWO WAYS THIS NUMBER CAN LIE, AND WHAT IS DONE ABOUT EACH

1. ZERO-FILLING. A day a sleeve did not trade is not a day it returned zero. Writing 0.0 for
   absent days deflates every pairwise correlation and manufactures diversification that does not
   exist -- it inflated k_eff by 1.36x when it happened in `record_sleeve_returns`. Correlations
   here are computed on OVERLAPPING DAYS ONLY, pair by pair, and a pair without enough genuine
   overlap contributes nothing rather than contributing a convenient zero.

2. ESTIMATING FROM CALM. Correlations rise in exactly the regime where the risk budget would be
   spent, and a sample mean is a point estimate from whatever regime happened to be sampled. So
   the UPPER confidence bound on rho_bar is used, never the point estimate: the desk takes the
   growth its evidence supports at the PESSIMISTIC end of the correlation estimate. That is the
   difference between aggression and optimism.

Absence of a measurement returns None, which routes `heat_budget` to its base. Not-yet-measured
must never read as independent -- that is precisely how a correlated book comes to size like a
diversified one and discovers its real correlation during the drawdown instead of before it.
"""

from __future__ import annotations

import math
from collections import defaultdict
from typing import Any, Iterable

#: Overlapping observations a PAIR needs before its correlation is used at all. Below this the
#: estimate is dominated by noise, and a noisy correlation near zero is indistinguishable from
#: genuine independence -- which is the error that raises leverage.
MIN_PAIR_OVERLAP = 20

#: Pairs that must clear MIN_PAIR_OVERLAP before any k_eff is reported. One informative pair in a
#: six-sleeve book describes one relationship, not the book.
MIN_PAIRS = 1

#: Confidence level for the upper bound on mean correlation. 1.645 = 95% one-sided.
_Z = 1.645


def _pearson(xs: list[float], ys: list[float]) -> float | None:
    n = len(xs)
    if n < 3:
        return None
    mx, my = sum(xs) / n, sum(ys) / n
    sxx = sum((x - mx) ** 2 for x in xs)
    syy = sum((y - my) ** 2 for y in ys)
    if sxx <= 0 or syy <= 0:
        return None                      # a constant series has no correlation, not zero
    sxy = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
    return sxy / math.sqrt(sxx * syy)


def daily_returns(rows: Iterable[dict], sleeve_key: str = "sleeve",
                  value_key: str = "r_multiple",
                  time_key: str = "time") -> dict[str, dict[str, float]]:
    """Ledger rows -> {sleeve: {date: summed R}}.

    Same-day trades in one sleeve are SUMMED, because the sleeve's daily P&L is what correlates
    with another sleeve's daily P&L. Days absent from a sleeve's map are absent, not zero.
    """
    out: dict[str, dict[str, float]] = defaultdict(dict)
    for r in rows:
        name, ts = r.get(sleeve_key), r.get(time_key)
        if not name or not ts:
            continue
        day = str(ts)[:10]
        try:
            v = float(r.get(value_key))
        except (TypeError, ValueError):
            continue
        out[name][day] = out[name].get(day, 0.0) + v
    return dict(out)


def mean_pairwise_corr(series: dict[str, dict[str, float]],
                       min_overlap: int = MIN_PAIR_OVERLAP) -> tuple[float | None, int, int]:
    """Fisher-z mean of pairwise correlations, and its upper 95% bound.

    Returns ``(rho_upper, n_pairs_used, min_overlap_seen)``. Averaging is done in z space because
    correlation is not additive; the bound uses the SMALLEST overlap of any contributing pair,
    which is the conservative choice when pairs have unequal sample sizes.
    """
    names = sorted(series)
    zs: list[float] = []
    smallest = 0
    for i, a in enumerate(names):
        for b in names[i + 1:]:
            common = sorted(set(series[a]) & set(series[b]))
            if len(common) < min_overlap:
                continue                                  # absent overlap, not zero correlation
            r = _pearson([series[a][d] for d in common], [series[b][d] for d in common])
            if r is None:
                continue
            r = max(min(r, 0.999999), -0.999999)          # arctanh is undefined at +-1
            zs.append(math.atanh(r))
            smallest = len(common) if smallest == 0 else min(smallest, len(common))
    if len(zs) < MIN_PAIRS:
        return None, 0, 0
    z_bar = sum(zs) / len(zs)
    # Upper bound from the thinnest contributing pair. Deliberately not sqrt(n_pairs)-shrunk:
    # pairwise correlations within one book are themselves dependent, so treating them as
    # independent samples would narrow the interval on an assumption that is false in the
    # direction that raises leverage.
    se = 1.0 / math.sqrt(max(smallest - 3, 1))
    return math.tanh(z_bar + _Z * se), len(zs), smallest


def effective_bets(n: int, rho: float) -> float:
    """k_eff = N / (1 + (N-1) * rho), clamped to [1, N]."""
    if n <= 1:
        return 1.0
    rho = max(min(float(rho), 1.0), -1.0 / (n - 1) + 1e-9)
    return max(1.0, min(float(n), n / (1.0 + (n - 1) * rho)))


def measure_k_eff(rows: Iterable[dict],
                  min_overlap: int = MIN_PAIR_OVERLAP) -> tuple[float | None, str]:
    """Effective independent bets in the book, from realised daily returns. None if unmeasurable.

    The returned string is the reason, and it is always populated -- a budget that silently
    widened would be indistinguishable from one that was never measured.
    """
    series = daily_returns(rows)
    n = len(series)
    if n < 2:
        return None, (f"k_eff UNMEASURED: {n} sleeve(s) with returns; correlation needs two. "
                      f"Heat stays at the base budget.")
    rho_upper, pairs, overlap = mean_pairwise_corr(series, min_overlap)
    if rho_upper is None:
        return None, (f"k_eff UNMEASURED: no sleeve pair has {min_overlap} overlapping trading "
                      f"days yet ({n} sleeves). Heat stays at the base budget.")
    k = effective_bets(n, rho_upper)
    return k, (f"k_eff {k:.2f} from {n} sleeves, {pairs} pair(s), thinnest overlap {overlap}d, "
               f"rho<={rho_upper:.3f} (95% upper bound, not the point estimate)")


def factor_k_eff(exposures: "Mapping[str, float]") -> tuple[float | None, str]:
    """Effective bets from CURRENCY LEGS, not from realised return correlation.

    TWO SLEEVES CAN CORRELATE AT ZERO AND STILL BE ONE TRADE. `measure_k_eff` reads realised
    daily returns, which is the right measurement and an incomplete one: correlation is
    backward-looking and estimated on the quiet sample, so four sleeves each secretly SHORT USD
    measure as four bets for as long as the dollar does not move -- and then move together on the
    day it does. `libs/risk/fx_factors.py` decomposes the book into currency legs and was measured
    on the live survivor set reporting `n_effective 1.019 across 17 sleeves`: seventeen positions
    behaving as one bet, while an asset-class view put 28 of 45 certificates in a single FX bucket
    and said nothing at all.

    THAT MODULE HAD ZERO NON-TEST CALLERS. It described itself as "a MEASUREMENT, not a gate and
    not a sizer" -- true, and exactly why nothing ever changed because of it.

    It still sizes nothing. Sizing stays in the gateway, the only thing that knows Fusion tick
    value and contract size -- the knowledge whose absence produced the CADJPY incident (believed
    1.26% risk, actual 7.41%). What it now does is constrain BREADTH, which is what `heat_budget`
    scales total risk by. None is returned whenever the decomposition cannot be trusted, and None
    never widens a budget.
    """
    try:
        from libs.risk.fx_factors import effective_bets as fx_effective_bets
    except ImportError as exc:
        return None, f"factor k_eff UNMEASURED: {type(exc).__name__}: {exc}"
    if not exposures:
        return None, "factor k_eff UNMEASURED: no per-symbol exposures supplied"
    try:
        k = float(fx_effective_bets(exposures))
    except Exception as exc:                                        # noqa: BLE001
        return None, f"factor k_eff UNMEASURED: {type(exc).__name__}: {exc}"
    if not math.isfinite(k) or k < 1.0:
        return None, f"factor k_eff UNMEASURED: decomposition returned {k!r}"
    return k, f"factor k_eff {k:.2f} from {len(exposures)} symbol exposure(s), currency-leg net"


def _floor_by_factor(k: float | None, why: str,
                     exposures: "Mapping[str, float] | None") -> tuple[float | None, str]:
    """The smaller of return breadth and currency-factor breadth, and which bound bound it."""
    if exposures is None:
        return k, why
    k_fac, fac_why = factor_k_eff(exposures)
    if k_fac is None:
        return k, f"{why}; {fac_why} (return breadth unchanged)"
    if k is None:
        # Returns unmeasurable but the legs are known. The factor number is real evidence and can
        # only ever TIGHTEN against the base budget, so reporting it alone cannot widen anything.
        return k_fac, f"{why}; {fac_why} -- factor breadth is the only measured bound"
    if k_fac < k:
        return k_fac, f"{fac_why} BINDS below return breadth ({why})"
    return k, f"{why}; {fac_why} (return breadth binds)"


def measure_from_ledger(rows: Iterable[dict], acc: dict[str, Any] | None = None,
                        min_overlap: int = MIN_PAIR_OVERLAP,
                        exposures: "Mapping[str, float] | None" = None,
                        ) -> tuple[float | None, str]:
    """`measure_k_eff` over one account's rows only, floored by currency-factor breadth.

    Mixing demo and live fills would compute the book's independence from trades taken on two
    different books. See mt5desk.provenance.

    THE CAPITAL NUMBER IS THE MINIMUM OF THE TWO BREADTHS. Return correlation and currency
    exposure answer different questions, and a book is only as diversified as its worse answer:
    taking returns alone lets four expressions of one dollar view buy the heat of four
    independent bets. `exposures` is optional, and its ABSENCE never raises the budget -- an
    unmeasured factor breadth leaves the return-based number exactly as it was, the same
    fail-closed direction every other rail here takes.
    """
    rows = list(rows)
    if acc is not None:
        from mt5desk.provenance import same_account
        kept = [r for r in rows if same_account(r, acc)]
        if len(kept) != len(rows):
            k, why = measure_k_eff(kept, min_overlap)
            k, why = _floor_by_factor(k, why, exposures)
            return k, why + f" [{len(kept)}/{len(rows)} rows from the account in hand]"
        rows = kept
    k, why = measure_k_eff(rows, min_overlap)
    return _floor_by_factor(k, why, exposures)
