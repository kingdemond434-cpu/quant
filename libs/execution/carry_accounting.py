"""Self-healing spot-realized accounting for the delta-neutral cash-and-carry book.

The book banks each CLOSED spot leg's realized PnL in ``realized_spot_pnl`` -- the sell proceeds sit
in the spot wallet where open-position marks can't see them, while the matching perp leg's realized
stays inside the futures-equity delta. Historically this was a hand-maintained accumulator
(incremented at each close), which is FRAGILE: a stale/crashed executor, or duplicate close-logs
during a flatten, let it silently drift. Because the perp side IS captured, any drift fabricates a
one-sided loss on the dashboard (the 2026-07-10 phantom: a ~breakeven book showed -$865 on the 3x
levered lab).

Permanent fix -- derive it from EXCHANGE GROUND TRUTH every cycle instead of trusting the
accumulator. For a delta-neutral carry each closed leg satisfies ``price_pnl = spot_real +
perp_real`` and the venue's own ``REALIZED_PNL`` income equals ``sum(perp_real)``. Therefore::

    spot_realized = sum(price_pnl over closed carries) - venue_realized_pnl

The venue term is EXACT; the basis term (``sum(price_pnl)``, ~0 for a tight hedge) comes from the
trade log, deduped by ``(symbol, opened)`` so duplicate close-logs never double-count. Substituting
into ``net = spot_open + spot_realized + (fut_eq - start_eq)`` the venue-realized term cancels, so
``net = spot_open + basis + funding - fees`` -- the true economic PnL, which cannot be faked.
"""

from __future__ import annotations

import time
from collections.abc import Callable
from typing import Any

from pydantic import BaseModel, ConfigDict


def read_income(
    fetch: Callable[[], Any],
    *,
    attempts: int = 3,
    sleeper: Callable[[float], None] = time.sleep,
) -> dict[str, Any] | None:
    """Venue income summary, or ``None`` when it cannot be read -- NEVER a zero-filled dict.

    UNKNOWN IS NOT ZERO. This exists because on 2026-07-26 the venue's ``/fapi/v1/income``
    endpoint returned HTTP 502 for hours while the executor's ``_safe()`` context swallowed the
    error and left ``funding`` at its initialised ``0.0``. The primary book then published a
    $0.00 harvest -- against a ground truth of $101.96 that the molded book had recorded two
    hours earlier -- and the carry-leak alarm divided by that fabricated zero to declare an
    ``inf%`` total bleed. An outage was rendered as an economic verdict.

    That is the same failure SHAPE as the 2026-07-19 stranded-inventory incident (GAP row 34),
    where ``_safe()`` made a rejected order indistinguishable from a filled one. That incident
    was fixed on the ORDER path (``_filled``) and left standing on the MEASUREMENT path.

    Reads are idempotent, so a transient 5xx is retried. Orders are deliberately NOT retried
    this way (see ``libs/execution/retry``) -- a duplicate GET is free, a duplicate POST is a
    second position. Every failure class collapses to ``None`` on purpose: the caller's only
    honest question is "did this measure or not", and a partially-parsed dict is not a
    measurement.
    """
    for attempt in range(1, attempts + 1):
        try:
            out = fetch()
        except Exception:                              # any venue/transport failure = unmeasured
            if attempt < attempts:
                sleeper(1.0 * attempt)
                continue
            return None
        return out if isinstance(out, dict) else None
    return None


def dedup_basis(trades: list[dict[str, Any]]) -> float:
    """Sum ``price_pnl`` over closed carries, deduped by ``(symbol, opened)``.

    A single carry closes once; the executor can log the same close several times (reconcile retries
    or a flatten), so keep one record per ``(symbol, opened)`` to avoid double-counting basis.
    """
    seen: dict[tuple[Any, Any], float] = {}
    for t in trades:
        if t.get("event") == "close":
            try:
                seen[(t.get("symbol"), t.get("opened"))] = float(t.get("price_pnl", 0.0) or 0.0)
            except (TypeError, ValueError):
                continue
    return round(sum(seen.values()), 2)


def derive_spot_realized(venue_realized_pnl: float, trades: list[dict[str, Any]]) -> float:
    """Exchange-anchored spot realized PnL = deduped basis - venue futures REALIZED_PNL.

    ``venue_realized_pnl`` is the cumulative futures realized (``income_summary`` ``realized_pnl``)
    since the book's inception -- exact and un-fakeable. Robust to executor restarts/crashes and
    duplicate close-logs; degrades gracefully if the trade log is trimmed (basis is small).
    """
    try:
        vr = float(venue_realized_pnl)
    except (TypeError, ValueError):
        vr = 0.0
    return round(dedup_basis(trades) - vr, 2)


class FuturesLegReconciliation(BaseModel):
    """Two independent measurements of the SAME futures leg, and their disagreement.

    Measured 2026-08-05: the primary carry book published ``net_pnl +2938.01`` while the venue's
    own income ledger said the futures leg was ``-4791.09`` since inception. The gap was
    ``+4807.75``, the book's ONLY deployed sleeve read as profitable while it had lost $1,869.74,
    and the note on the artifact says it "builds the forward track record the gate sizes on".

    THE CAUSE IS A SHARED SOURCE, NOT A BROKEN HEDGE. ``fut_pnl = fut_eq - start_eq`` and
    ``start_eq`` is ``capital_events.effective_start_equity`` -- the RUIN RAIL's inception, which a
    principal-signed re-base legitimately moves. On 2026-08-01 a ``RESTART`` moved it 10,547.78 ->
    5,757.08 so the rail would measure the post-fix book instead of latching on an already-fixed
    churn-loop bug. That is correct FOR THE RAIL. It is not correct for P&L REPORTING, which must
    measure from the first inception forever -- and both read one number, so the re-base silently
    became $4,790.70 of reported profit. Same family as L1.51's ``_capital()``: a rail's reference
    point and a performance number may not share a source when a re-base can move one of them.

    THE INCOME LEDGER WINS, and the reason is structural rather than a preference: ``realized +
    funding - commission`` is venue-native and has no re-baseable input, so no desk-side accounting
    act can move it. The equity delta has exactly one, and that one moved.

    EXPLAINED IS NOT THE SAME AS FINE, and keeping them apart is the whole point (L1.55's
    ABSENT-vs-UNREADABLE discipline): a gap matching a ledgered re-base is a REPORTING defect with
    a known cause, while a gap that matches nothing is the phantom class that earns a page. The
    previous code collapsed both into one field named ``residual`` that no verdict ever cited.
    """

    model_config = ConfigDict(frozen=True)

    equity_delta: float | None       # fut_eq - start_eq (start_eq is RE-BASEABLE)
    income_ledger: float | None      # realized + funding - commission + unrealized (venue-native)
    gap: float | None                # equity_delta - income_ledger; 0 on an honest flat book
    rebase_usd: float                # ledgered re-base that would explain a gap of this size
    explained: bool                  # gap is attributable to the known re-base, within tolerance
    measured: bool                   # False = an income term was unreadable; NOT a zero gap
    reporting_pnl: float | None      # the number P&L reporting should publish
    verdict: str


def reconcile_futures_leg(
    *,
    equity_delta: float | None,
    venue_realized: float | None,
    funding: float | None,
    commission: float | None,
    unrealized: float = 0.0,
    rebase_usd: float = 0.0,
    tol: float = 25.0,
) -> FuturesLegReconciliation:
    """Cross-check the equity-delta futures PnL against the venue income ledger.

    ``tol`` absorbs the honest slack between the two paths -- open-position marks move between the
    equity read and the income read, and both are rounded. It is deliberately NOT scaled to the
    gap: a tolerance that grows with the discrepancy it is meant to catch explains everything.

    UNMEASURED IS NOT AGREEMENT. Any missing income term returns ``measured=False`` with no gap and
    no reporting number, because "the venue read failed" and "the two agree" are different claims
    and only one of them is evidence (the 2026-07-26 ``inf%`` verdict came from judging one as the
    other). ``reporting_pnl`` then stays ``None`` so a caller cannot quietly substitute a fabricated
    zero for a measurement that did not happen.
    """
    if equity_delta is None or venue_realized is None or funding is None or commission is None:
        missing = [n for n, v in (("equity_delta", equity_delta),
                                  ("venue_realized", venue_realized),
                                  ("funding", funding), ("commission", commission)) if v is None]
        return FuturesLegReconciliation(
            equity_delta=equity_delta, income_ledger=None, gap=None, rebase_usd=rebase_usd,
            explained=False, measured=False, reporting_pnl=None,
            verdict=(f"UNMEASURED: {', '.join(missing)} unreadable -- the futures leg has one "
                     f"measurement, not two, so the cross-check is UNDECIDABLE. A missing term is "
                     f"not an agreeing term."))
    income = round(float(venue_realized) + float(funding) - abs(float(commission))
                   + float(unrealized), 2)
    gap = round(float(equity_delta) - income, 2)
    explained = abs(gap - float(rebase_usd)) <= tol
    if abs(gap) <= tol:
        verdict = (f"AGREE: equity delta {equity_delta:+.2f} and income ledger {income:+.2f} match "
                   f"within {tol:.2f} -- the futures leg is measured twice and both agree.")
    elif explained:
        verdict = (
            f"REBASE-LEAK: equity delta {equity_delta:+.2f} exceeds the venue income ledger "
            f"{income:+.2f} by {gap:+.2f}, which matches the ledgered inception re-base of "
            f"{rebase_usd:+.2f}. The rail's re-based inception has leaked into P&L REPORTING; the "
            f"book has NOT earned this. Publishing {income:+.2f}.")
    else:
        verdict = (
            f"PHANTOM: equity delta {equity_delta:+.2f} vs income ledger {income:+.2f} differ by "
            f"{gap:+.2f}, and the ledgered re-base of {rebase_usd:+.2f} does NOT account for it. "
            f"Two measurements of one leg disagree for an unknown reason -- treat as unexplained "
            f"until a venue read proves otherwise (2026-07-10 phantom class).")
    return FuturesLegReconciliation(
        equity_delta=round(float(equity_delta), 2), income_ledger=income, gap=gap,
        rebase_usd=round(float(rebase_usd), 2), explained=explained, measured=True,
        reporting_pnl=income, verdict=verdict)


class CarryBleedReport(BaseModel):
    """The standing carry-leak alarm: how much of the funding harvest survives to the net."""

    model_config = ConfigDict(frozen=True)

    real_net: float  # spot_pnl + fut_pnl -- the real delta-neutral book (excludes paper legs)
    funding: float | None  # the harvest; None = UNMEASURED (venue read failed), never "zero"
    non_funding_pnl: float | None  # real_net - funding = basis + fees + drift (None if unmeasured)
    harvest_eaten_frac: float | None  # share of harvest lost to the leak (0 = clean, >=1 = all)
    alert: bool
    verdict: str
    measured: bool = True  # False = the funding read failed; the leak is UNDECIDABLE, not clean

    def __bool__(self) -> bool:
        # An UNMEASURED book is not a healthy one. Truthiness means "nothing to worry about",
        # and a blind alarm is something to worry about -- so it must not read as fine.
        return self.measured and not self.alert


def attribute_non_funding(
    non_funding_pnl: float, basis: float, fut_commission: float
) -> dict[str, float]:
    """Split the carry leak into ``basis``, ``fut_fees`` and an UNEXPLAINED ``residual``.

    The bleed alarm answers *how much* leaked; this answers *where it went*, which is the only
    form the desk can act on. From the book identity ``net = spot_open + basis + funding - fees``::

        non_funding = basis - fees + residual   ->   residual = non_funding - basis + fees

    ``basis`` is the deduped trade-log price_pnl (hedge convergence, ~0 for a tight hedge) and
    ``fut_commission`` is the venue's exact FUTURES fee bill. The residual is everything neither
    explains: SPOT commission (paid in the spot wallet, absent from the futures income ledger),
    slippage, and hedge-drift incidents. It is deliberately NOT called "fees" -- naming an
    unexplained quantity after a known one is how a phantom gets rationalised (2026-07-10).

    A large residual is the phantom/broken-hedge class and deserves a page; a large ``fut_fees``
    term is an EXECUTION problem with a known lever (maker share, churn, BNB burn). Before this
    split the two were indistinguishable on the dashboard, so the standing duty to "attribute
    basis/fees/incidents" could not actually be discharged.
    """
    fees = abs(fut_commission)
    return {"basis": round(basis, 2), "fut_fees": round(fees, 2),
            "residual": round(non_funding_pnl - basis + fees, 2)}


def carry_bleed_report(
    *, funding: float | None, spot_pnl: float, fut_pnl: float, alert_frac: float = 0.5,
    open_legs: int | None = None, recon: FuturesLegReconciliation | None = None,
) -> CarryBleedReport:
    """Attribute the delta-neutral book's non-funding PnL and raise an alarm if the leak is eating
    the funding harvest.

    A tight cash-and-carry earns ``funding`` and its price legs cancel, so the honest target is
    ``non_funding_pnl ~= 0`` (only small fees). ``non_funding_pnl = (spot_pnl + fut_pnl) - funding``
    captures everything else -- basis convergence, fees/slippage, and hedge-drift incidents. The
    alarm fires when that leak is a drain worth at least ``alert_frac`` of the harvest (or any drain
    at all when there is no harvest to offset it), so a hedge quietly losing more than it earns can
    never again slide by unnoticed on the dashboard. Diagnose the dominant cause only when it fires.

    TWO-SIDED (2026-07-26): the target is ~0 in BOTH directions, so a large POSITIVE non-funding
    PnL alarms just as loudly. On a delta-neutral book the price legs cancel by construction -- a
    windfall that size is not luck, it is a BROKEN HEDGE (a naked/untracked leg carrying real
    directional risk that will reverse). A one-sided alarm would have called that state "clean".

    UNMEASURED (2026-07-26): ``funding=None`` means the venue read failed, and the leak is then
    UNDECIDABLE -- every term of this alarm is denominated in a harvest we do not know. Passing a
    zero instead produced a division by that zero and an ``inf%`` "hedge losing more than it
    earns" verdict out of nothing but an HTTP 502. The report says so plainly and declines to
    judge; ``measured=False`` is what downstream must alarm on, and it is deliberately NOT folded
    into ``alert`` -- a venue outage and a leaking hedge need different responses, so collapsing
    them into one boolean would just move the ambiguity rather than remove it.
    """
    real_net = round(spot_pnl + fut_pnl, 2)
    if funding is None:
        return CarryBleedReport(
            real_net=real_net, funding=None, non_funding_pnl=None, harvest_eaten_frac=None,
            alert=False, measured=False,
            verdict=(f"UNMEASURED: funding harvest unavailable (venue income read failed) -- "
                     f"leak undecidable on real_net {real_net:+.2f}. A swallowed venue error is "
                     f"NOT a zero harvest; judging one as the other fabricates a total-bleed "
                     f"verdict out of an outage."),
        )
    non_funding = round(real_net - funding, 2)
    if funding > 0:
        eaten = round(max(0.0, -non_funding) / funding, 3)
    else:
        eaten = float("inf") if non_funding < 0 else 0.0
    alert = (abs(non_funding) >= alert_frac * funding) if funding > 0.0 else (non_funding < 0.0)
    if alert and non_funding > 0.0:
        # NAME THE CAUSE THE DATA SUPPORTS, NEVER THE ONE THE SHAPE SUGGESTS. This branch used to
        # assert "a NAKED/UNTRACKED leg -- reconcile spot vs perp qty" unconditionally. On
        # 2026-08-05 it fired for four days against a book holding ZERO positions, so the remedy it
        # ordered was not merely wrong, it was IMPOSSIBLE TO PERFORM: there were no legs to
        # reconcile, and an operator who checked found nothing and moved on. The real cause was an
        # inception re-base leaking into P&L reporting, which `reconcile_futures_leg` identifies
        # exactly. A confident wrong diagnosis is worse than an honest open question, because it
        # closes the search (2026-07-10 phantom lesson, applied to the alarm rather than the book).
        head = (f"BLEED(inverted): non-funding PnL {non_funding:+.2f} is "
                f"{non_funding / funding:.0%} of {funding:+.2f} funding harvest")
        if recon is not None and recon.measured and not recon.explained and recon.gap is not None \
                and abs(recon.gap) > 0.0:
            verdict = f"{head} -- {recon.verdict}"
        elif recon is not None and recon.explained and recon.gap is not None and recon.gap != 0.0:
            verdict = f"{head} -- ACCOUNTING, NOT EDGE. {recon.verdict}"
        elif open_legs == 0:
            # `open_legs` counts TRACKED carries, and untracked exposure is precisely what the
            # naked-leg hypothesis is about -- so zero tracked legs narrows the field to two
            # candidates rather than clearing the hedge. Saying "this cannot be a naked leg" here
            # would repeat, inverted, the very error this branch exists to fix: on 2026-08-05 the
            # same executor was logging 476 SPOT-EXCESS lines about wallet balances it did not
            # track. State both, and name which one to check first.
            verdict = (
                f"{head} -- and the book tracks ZERO open carries, so the gain is realized and "
                "cannot come from a tracked hedge. Two candidates remain, in this order: an "
                "ACCOUNTING artifact (check the inception the futures leg is differenced against "
                "against the venue income ledger), or UNTRACKED exposure the position map does "
                "not know about (check wallet balances against tracked carries).")
        else:
            verdict = (
                f"{head} -- delta-neutral price legs cancel, so a gain this size means a "
                f"NAKED/UNTRACKED leg, not edge; reconcile spot vs perp qty across the "
                f"{open_legs if open_legs is not None else 'open'} open leg(s) before trusting it")
    elif non_funding >= 0.0:
        verdict = f"clean: non-funding PnL {non_funding:+.2f} not a drain; harvest survives"
    elif not alert:
        verdict = f"ok: {eaten:.0%} of the {funding:+.2f} funding harvest lost to non-funding PnL"
    else:
        verdict = (
            f"BLEED: non-funding PnL {non_funding:+.2f} is {eaten:.0%} of {funding:+.2f} funding "
            "harvest -- hedge losing more than it earns; attribute basis/fees/incidents"
        )
    return CarryBleedReport(
        real_net=real_net,
        funding=funding,
        non_funding_pnl=non_funding,
        harvest_eaten_frac=eaten,
        alert=alert,
        verdict=verdict,
    )
