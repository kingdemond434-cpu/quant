"""PRICED VERSUS UNPRICED -- the estimate that separates an intelligence layer from a news bot.

THE QUESTION. Not "is this bullish for gold". The question is: of the information this item
carries, how much is still in front of the market rather than behind it? If gold already moved
forty dollars before the feed arrived, the unpriced fraction is near zero and there is nothing
to trade, however important, credible and well-understood the event is. `assess.py` multiplies
importance by this number, so an event with maximum credibility and zero unpriced fraction
produces no allocation change by arithmetic rather than by anyone remembering the rule.

THE MEASUREMENT.

    pre_move_sigma   the move that ALREADY HAPPENED between the source publishing and this desk
                     receiving, measured in trailing per-bar sigma, taken as the MAXIMUM across
                     the candidate instruments. The maximum, not the mean, because the leading
                     instrument is the one carrying the information -- averaging it against four
                     instruments that had not reacted yet would systematically understate how
                     late the desk is, which is the error that costs money.

    unpriced         1 - pre_move_sigma / total_move_sigma, clipped to [0, 1], where
                     total_move_sigma is the MEDIAN absolute full-window response of this
                     category's past instances from the desk's own ledger. Median rather than
                     mean because event responses are fat-tailed and one 2015-franc afternoon
                     would otherwise set the denominator for every subsequent event.

WHEN THE DENOMINATOR DOES NOT EXIST, WHICH IS TODAY. A category with fewer than
`MIN_CATEGORY_N` measured reactions has no total_move_sigma, and the honest output is
UNMEASURED -- not a default of 1.0, which would say "all of it is still tradeable" and would be
the single most expensive default in this package. UNMEASURED costs capital authority, which is
correct: the desk should not size an event class it has never measured.

UNCERTAINTY MAY ONLY REDUCE AUTHORITY, NEVER GRANT IT. There is one asymmetry here and it is
deliberate. When the category denominator is missing but the observed pre-arrival move is already
enormous (`LARGE_MOVE_SIGMA`), the estimate is still UNMEASURED but carries
`already_moved=True`, and `assess.py` treats that as a hard zero. In other words: not knowing
whether we are late can never make us bold, but seeing that we are late can make us abstain. A
symmetric treatment would let ignorance authorise trades.

WHAT THIS CANNOT DO ON THIS BOX. `prices.py` documents the granularity floor. With H1 as the
fastest series for most instruments, any event whose publish-to-receive lag is under an hour
returns UNMEASURABLE for those instruments, and the layer says so on every such row rather than
substituting an hourly move for a three-minute one.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime

from .ledger import CategoryStats
from .prices import PriceReader, move_sigma
from .schema import PricedEstimate, Status, parse_ts

#: A pre-arrival move this large means the story is out, whatever the ledger does or does not
#: know about the category. Three trailing sigma on the fastest instrument the desk can see is
#: not a threshold for acting -- it is a threshold for ABSTAINING, which is why it is allowed to
#: bind without category sample.
LARGE_MOVE_SIGMA = 3.0

#: Below this the desk is not meaningfully late and the pre-move carries no information about
#: how much is priced; reported, but not used to reduce the estimate.
NOISE_SIGMA = 0.5

__all__ = ["LARGE_MOVE_SIGMA", "NOISE_SIGMA", "already_priced", "estimate", "realised_unpriced"]


def estimate(reader: PriceReader, *, symbols: Sequence[str], published_at: str | None,
             received_at: str, stats: CategoryStats | None) -> PricedEstimate:
    """How much of this item is still unpriced. Every refusal names its reason.

    `symbols` are the candidate instruments -- the ones `expression.py` says could carry this
    event. Handing in the whole universe would make the maximum a maximum over noise.
    """
    t_pub = parse_ts(published_at)
    t_rec = parse_ts(received_at)
    if t_rec is None:
        return PricedEstimate(None, None, None, "no-receive-clock", 0, Status.UNMEASURED,
                              note="received_at is missing or unparseable")
    if t_pub is None:
        # Not a failure of the estimator: a source that does not stamp its own publication time
        # makes the question unanswerable, and that is a property of the SOURCE worth recording
        # against it rather than a gap to fill with an assumption.
        return PricedEstimate(None, None, None, "no-publish-clock", 0, Status.UNMEASURED,
                              note="source did not stamp publication time; lateness unknowable")
    lag_s = (t_rec - t_pub).total_seconds()
    if lag_s < 0:
        return PricedEstimate(None, None, lag_s, "clock-inversion", 0, Status.UNMEASURED,
                              note=("received before published -- source clock disagrees with "
                                    "ours; recorded, not corrected"))

    per_symbol: dict[str, float] = {}
    reasons: list[str] = []
    for sym in symbols:
        val, why = move_sigma(reader, sym, t_pub, t_rec)
        if val is None:
            if why:
                reasons.append(why)
            continue
        per_symbol[sym] = round(val, 4)

    if not per_symbol:
        note = "; ".join(reasons[:4]) or "no candidate instruments"
        status = (Status.UNMEASURABLE
                  if any("UNMEASURABLE at this granularity" in r for r in reasons)
                  else Status.UNMEASURED)
        return PricedEstimate(None, None, lag_s, "no-usable-series", 0, status, note=note)

    pre = max(abs(v) for v in per_symbol.values())
    already_moved = pre >= LARGE_MOVE_SIGMA

    if stats is None or not stats.has_sample or not stats.total_move_sigma:
        note = ("category denominator UNMEASURED "
                f"(n_measured={0 if stats is None else stats.n_measured}); "
                "unpriced fraction is NOT defaulted to 1.0")
        if already_moved:
            note += (f"; pre-arrival move {pre:.2f} sigma >= {LARGE_MOVE_SIGMA} -- treat as "
                     "already priced, abstain")
        return PricedEstimate(
            None, round(pre, 4), lag_s, "pre-move-only", 0, Status.UNMEASURED,
            per_symbol=per_symbol, note=note)

    denom = float(stats.total_move_sigma)
    effective_pre = 0.0 if pre < NOISE_SIGMA else pre
    frac = 1.0 - effective_pre / denom
    frac = 0.0 if frac < 0.0 else (1.0 if frac > 1.0 else frac)
    return PricedEstimate(
        unpriced_fraction=round(frac, 4), pre_move_sigma=round(pre, 4), lag_s=lag_s,
        method="pre_move_over_category_median", n=stats.n_measured, status=Status.MEASURED,
        per_symbol=per_symbol,
        note=(f"pre-arrival {pre:.2f} sigma against category median full response "
              f"{denom:.2f} sigma over n={stats.n_measured}"
              + ("; already priced" if frac <= 0.0 else "")))


def already_priced(est: PricedEstimate) -> bool:
    """True when the desk should not act, INCLUDING the uncertain case.

    Both a measured zero and an unmeasured-but-obviously-late reading return True. That
    asymmetry is the module's whole safety property: uncertainty abstains.
    """
    if est.status == Status.MEASURED:
        return (est.unpriced_fraction or 0.0) <= 0.0
    return est.pre_move_sigma is not None and est.pre_move_sigma >= LARGE_MOVE_SIGMA


def realised_unpriced(reader: PriceReader, *, symbols: Sequence[str], published_at: str,
                      received_at: str, horizon_end: datetime) -> float | None:
    """AFTER the fact: what fraction of the full response was still available when we arrived.

    This is the label the estimator is scored against in `attribution.py` -- the calibration
    loop. Without it the unpriced estimate is an opinion that never gets marked, which is
    exactly the failure mode the principal's "intelligence grows" sentence rules out.
    """
    t_pub, t_rec = parse_ts(published_at), parse_ts(received_at)
    if t_pub is None or t_rec is None:
        return None
    # Scored on the LEADING instrument -- the one that moved most in total over the whole event
    # window -- to match `estimate`, which takes the maximum pre-move across candidates. Scoring
    # the estimate against a different instrument than it was formed on would make the
    # calibration loop measure the disagreement between two instruments rather than the error.
    best_total = 0.0
    best_share: float | None = None
    for sym in symbols:
        pre, _ = move_sigma(reader, sym, t_pub, t_rec)
        post, _ = move_sigma(reader, sym, t_rec, horizon_end)
        if pre is None or post is None:
            continue
        total = abs(pre) + abs(post)
        if total > best_total:
            best_total, best_share = total, abs(post) / total
    return None if best_share is None else round(best_share, 4)
