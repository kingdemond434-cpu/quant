"""§3 host-death survivorship: every live position carries a venue-side reduce-only stop.

The rail that matters when the host dies is the one the VENUE holds. A stop enforced by our own
process is not a stop -- it is an intention that evaporates with the process. So the invariant is
stated against what Binance can see: for every open position there must be a RESTING reduce-only
STOP_MARKET, on the closing side, covering the WHOLE quantity, at no worse than ruin-line distance.

Partial cover is the subtle failure and the reason `naked_positions` compares quantities rather
than merely asking "is there a stop?": a 1.0-BTC position with a 0.2-BTC stop passes every
presence check ever written and leaves 80% of the book naked through the outage.

Pure logic only -- no exchange calls, no clock reads beyond what the caller passes in. The
impure half (reading positions/orders, paging, freezing) lives in scripts/run_live_guard.py so
this file stays property-testable, which is the §7 verification bar for risk-path code.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

# §3: naked for longer than this and the desk freezes new entries + pages. Not a tunable knob --
# it is the spec's number, and lengthening it lengthens exactly the window the rail exists for.
NAKED_GRACE_S = 60.0

# fraction of equity a single position may lose before its stop fires. Mirrors the dead-man's
# 35% ruin rail (_RUIN_FACTOR = 0.65 in scripts/run_deadman_switch.py) so the per-position stop
# sits AT the ruin line rather than somewhere unrelated to it.
RUIN_FRACTION = 0.35

# tolerated shortfall in stop coverage: venues round quantity to the lot step, so a stop placed
# for the exact position size can come back a hair light. 0.5% is far below any size that
# matters and far above any rounding step.
_COVER_TOLERANCE = 0.995

_WATCH = Path("data/naked_position_watch.json")


def closing_side(position_qty: float) -> str:
    """The order side that REDUCES this position. Long (+) closes by SELL, short (-) by BUY."""
    return "SELL" if position_qty > 0 else "BUY"


def ruin_stop_price(mark: float, position_qty: float, equity: float,
                    ruin_fraction: float = RUIN_FRACTION) -> float | None:
    """Stop price at ruin-line distance: the adverse move that costs exactly ``ruin_fraction``
    of equity on this position.

    Returns None when the inputs cannot produce a meaningful stop (non-positive mark, equity or
    size). None means "cannot compute" and callers must treat it as "do not open", never as
    "no stop needed" -- fail-closed is the whole point of this file.

    A long's stop is clamped to a positive price: when the ruin budget exceeds the position's
    entire notional, price zero is reached before the budget is spent, and a stop at or below 0
    is not placeable. In that case the position is already sized past ruin and the honest answer
    is the smallest positive tick-ish price, not a negative number the venue would reject.
    """
    if mark <= 0 or equity <= 0 or position_qty == 0 or ruin_fraction <= 0:
        return None
    budget = equity * ruin_fraction
    adverse_per_unit = budget / abs(position_qty)
    if position_qty > 0:
        return max(mark * 1e-6, mark - adverse_per_unit)
    return mark + adverse_per_unit


def stop_qty(order: dict[str, Any]) -> float:
    """Quantity on a resting order, 0.0 when unreadable (unreadable => contributes no cover)."""
    try:
        return abs(float(order.get("origQty", order.get("quantity", 0.0)) or 0.0))
    except (TypeError, ValueError):
        return 0.0


def is_protective_stop(order: dict[str, Any], position_qty: float) -> bool:
    """Is this order the RIGHT KIND of order to protect ``position_qty``? (Quantity aside.)

    Three things must hold together and each one has been a real bug somewhere: it must be a
    STOP_MARKET (a LIMIT stop can go unfilled through the very gap it exists for), it must be
    reduce-only (or it opens a new position on the far side), and it must be on the CLOSING side.
    """
    if str(order.get("type", "")).upper() not in {"STOP_MARKET", "STOP"}:
        return False
    ro = order.get("reduceOnly", order.get("reduce_only", False))
    if not (ro is True or str(ro).lower() == "true"):
        return False
    return str(order.get("side", "")).upper() == closing_side(position_qty)


def stop_is_adequate(order: dict[str, Any], position_qty: float) -> bool:
    """Does this SINGLE order fully protect ``position_qty``? Kind, side, and full coverage."""
    return (is_protective_stop(order, position_qty)
            and stop_qty(order) >= abs(position_qty) * _COVER_TOLERANCE)


def naked_positions(positions: dict[str, float],
                    open_orders: list[dict[str, Any]]) -> dict[str, float]:
    """Symbols holding a position with NO adequate venue-side stop. {symbol: position_qty}.

    Multiple partial stops on one symbol are summed before the coverage test: two 0.5-BTC stops
    do protect a 1.0-BTC position, and calling that naked would be a false alarm that gets the
    rail switched off.
    """
    naked: dict[str, float] = {}
    for sym, qty in positions.items():
        if qty == 0:
            continue
        # sum the quantities of every order that is a valid protective stop for this position,
        # then test the TOTAL (testing per-order would call split stops naked).
        covered = sum(stop_qty(o) for o in open_orders
                      if str(o.get("symbol", "")) == sym and is_protective_stop(o, qty))
        if covered < abs(qty) * _COVER_TOLERANCE:
            naked[sym] = qty
    return naked


@dataclass
class NakedWatch:
    """First-seen timestamps for naked symbols, persisted across process death.

    The 60s clock has to survive a restart or the invariant is trivially defeatable: a process
    that dies and respawns every 45s would reset the timer forever and never breach, which is
    precisely the crash-loop scenario the rail is for.
    """

    first_seen: dict[str, float] = field(default_factory=dict)
    path: Path = _WATCH

    @classmethod
    def load(cls, path: Path = _WATCH) -> NakedWatch:
        try:
            d = json.loads(path.read_text("utf-8"))
            seen = {str(k): float(v) for k, v in d.get("first_seen", {}).items()}
        except (OSError, json.JSONDecodeError, TypeError, ValueError):
            seen = {}
        return cls(first_seen=seen, path=path)

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix(".json.tmp")
        tmp.write_text(json.dumps({"first_seen": self.first_seen}, indent=2), "utf-8")
        tmp.replace(self.path)

    def observe(self, naked: dict[str, float], now: float) -> None:
        """Record this tick. Symbols that got covered are dropped so the clock restarts clean."""
        for sym in naked:
            self.first_seen.setdefault(sym, now)
        for sym in list(self.first_seen):
            if sym not in naked:
                del self.first_seen[sym]

    def breaches(self, now: float, grace_s: float = NAKED_GRACE_S) -> dict[str, float]:
        """Symbols naked for longer than the grace period. {symbol: seconds_naked}."""
        return {s: now - t for s, t in self.first_seen.items() if now - t > grace_s}


@dataclass(frozen=True)
class ReconcileReport:
    naked: dict[str, float]
    breaches: dict[str, float]
    n_positions: int

    @property
    def freeze_entries(self) -> bool:
        """§3: any position naked >60s freezes NEW entries. Existing positions are not touched --
        flattening into an unknown book state is its own risk, and the ladder owns that decision."""
        return bool(self.breaches)

    @property
    def summary(self) -> str:
        if not self.naked:
            return f"all {self.n_positions} position(s) carry an adequate venue-side stop"
        worst = max(self.breaches.values(), default=0.0)
        return (f"{len(self.naked)} naked position(s) of {self.n_positions}: "
                f"{', '.join(sorted(self.naked))}"
                + (f" -- oldest naked {worst:.0f}s (>{NAKED_GRACE_S:.0f}s grace)"
                   if self.breaches else " -- within grace"))


def reconcile(positions: dict[str, float], open_orders: list[dict[str, Any]], now: float,
              watch: NakedWatch | None = None) -> ReconcileReport:
    """Full §3 invariant evaluation for one tick. Persists the watch as a side effect."""
    w = watch if watch is not None else NakedWatch.load()
    naked = naked_positions(positions, open_orders)
    w.observe(naked, now)
    w.save()
    return ReconcileReport(naked=naked, breaches=w.breaches(now), n_positions=len(positions))
