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
    *, funding: float | None, spot_pnl: float, fut_pnl: float, alert_frac: float = 0.5
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
        verdict = (
            f"BLEED(inverted): non-funding PnL {non_funding:+.2f} is "
            f"{non_funding / funding:.0%} of {funding:+.2f} funding harvest -- delta-neutral price "
            "legs cancel, so a gain this size means a NAKED/UNTRACKED leg, not edge; reconcile "
            "spot vs perp qty before trusting the number"
        )
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
