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

from typing import Any


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
