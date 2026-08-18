"""What latency is actually worth, per sleeve. CONSTITUTION 221.

221.4 is unambiguous: eBPF and DPDK are in the challenger inventory and are NOT
SCHEDULED FOR CONSTRUCTION. So this is not a low-latency stack. It is the thing
221.3 names as the only admission criterion for one:

    delta E[log W] from the latency improvement
        >
    engineering cost + infrastructure cost + operational risk

estimated from the LATENCY VALUE CURVE — replay the strategy at 0ms, 10ms, 50ms,
100ms, 250ms, 1s and 5s and measure NET_EDGE(latency). THE CURVE DECIDES, PER
SLEEVE, and not a general preference for speed.

WHY THIS IS THE HONEST DELIVERABLE AND A FAST PATH WOULD NOT BE

221.1 settles the physics: an order does not go from this desk's NIC to a
matching engine. It traverses a broker gateway, an MT5 server, broker risk
controls and LP routing. Kernel bypass cannot remove layers that are not in the
kernel, and shaving 300 microseconds off the first hop of a path whose dominant
term is a broker's risk check is buying nothing at real cost.

For an M15 session-range book the curve is very likely flat out to a full
second, which would make every rung of 221.2's ladder a pure loss. But "very
likely" is not a measurement, and the section exists precisely so the answer
comes from a replay rather than from taste. If a sleeve turns out to be
latency-sensitive at 100ms, that is worth knowing before it is deployed, not
after it underperforms its backtest for a reason nobody looked for.

THE ASYMMETRY THAT MAKES THIS WORTH RUNNING EVEN WHEN THE ANSWER IS NO

A flat curve is not a null result. It is a licence to run the desk on cheap
infrastructure — a shared VPS, a Python loop, a poll interval measured in
seconds — and to stop treating latency as a thing to worry about at all. That
conclusion is worth more than a fast path, because it removes an entire category
of engineering from the roadmap permanently.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Callable, Optional, Sequence

LATENCY_VERSION = "latency-2026-08-18-a"

#: The grid 221.3 names, in milliseconds. Fixed here rather than passed, so a
#: sleeve cannot be evaluated on a grid chosen after seeing its curve.
GRID_MS = (0, 10, 50, 100, 250, 1_000, 5_000)

#: Fractional edge loss below which a sleeve is called latency-INSENSITIVE. Not
#: zero: any replay has sampling noise, and demanding an exactly flat curve
#: would make every sleeve look sensitive.
FLAT_TOLERANCE = 0.05


@dataclass(frozen=True)
class Point:
    latency_ms: int
    net_edge_r: float
    n_trades: int
    fills_missed: int = 0

    def render(self) -> str:
        miss = f"  {self.fills_missed} fill(s) missed" if self.fills_missed else ""
        return (f"  {self.latency_ms:>6}ms   net edge {self.net_edge_r:+8.4f}R   "
                f"n={self.n_trades}{miss}")


@dataclass
class Curve:
    """NET_EDGE(latency) for one sleeve."""
    sleeve: str
    points: tuple = ()
    why: str = ""

    @property
    def baseline(self) -> Optional[Point]:
        return next((p for p in self.points if p.latency_ms == 0), None)

    def edge_at(self, ms: int) -> Optional[float]:
        p = next((p for p in self.points if p.latency_ms == ms), None)
        return None if p is None else p.net_edge_r

    def decay(self, ms: int) -> Optional[float]:
        """Fraction of the zero-latency edge lost by `ms`. None if unmeasurable."""
        b = self.baseline
        if b is None or abs(b.net_edge_r) < 1e-12:
            return None
        e = self.edge_at(ms)
        return None if e is None else (b.net_edge_r - e) / abs(b.net_edge_r)

    @property
    def flat(self) -> bool:
        """Insensitive across the whole grid. The likely and valuable answer."""
        ds = [self.decay(p.latency_ms) for p in self.points]
        ds = [d for d in ds if d is not None]
        return bool(ds) and max(ds) <= FLAT_TOLERANCE

    def knee(self) -> Optional[int]:
        """First grid point where more than FLAT_TOLERANCE of the edge is gone."""
        for p in sorted(self.points, key=lambda x: x.latency_ms):
            d = self.decay(p.latency_ms)
            if d is not None and d > FLAT_TOLERANCE:
                return p.latency_ms
        return None

    def verdict(self) -> dict:
        b = self.baseline
        if b is None:
            return {"accelerate": False, "why": "no zero-latency baseline was "
                                                "replayed; there is nothing to "
                                                "measure decay against."}
        if b.net_edge_r <= 0:
            return {"accelerate": False,
                    "why": (f"the sleeve has no edge at ZERO latency "
                            f"({b.net_edge_r:+.4f}R). Latency cannot be the "
                            f"problem with a strategy that does not work when "
                            f"it is infinitely fast.")}
        if self.flat:
            return {"accelerate": False, "knee": None,
                    "why": ("the curve is FLAT across the whole grid, out to five "
                            "seconds. Every rung of the 221.2 ladder is a pure "
                            "loss for this sleeve — and that is a licence to run "
                            "on cheap infrastructure and stop treating latency as "
                            "a concern at all, which is worth more than a fast "
                            "path would have been.")}
        k = self.knee()
        return {"accelerate": True, "knee": k,
                "why": (f"more than {FLAT_TOLERANCE:.0%} of the edge is gone by "
                        f"{k}ms. 221.3 still requires the value of the recovered "
                        f"edge to exceed engineering plus infrastructure plus "
                        f"operational risk — this says the curve is not flat, "
                        f"not that a fast path is justified.")}

    def render(self) -> str:
        lines = [f"LATENCY VALUE CURVE — {self.sleeve}  ({LATENCY_VERSION})"]
        lines += [p.render() for p in sorted(self.points, key=lambda x: x.latency_ms)]
        v = self.verdict()
        lines += ["", f"  {v['why']}"]
        if self.why:
            lines.append(f"  {self.why}")
        return "\n".join(lines)


def build_curve(sleeve: str, replay: Callable[[int], tuple],
                grid: Sequence[int] = GRID_MS) -> Curve:
    """Replay a sleeve across the latency grid.

    `replay(latency_ms)` returns `(net_edge_r, n_trades, fills_missed)`. The
    caller owns the simulator, because a latency model living in this module
    would be a second execution assumption competing with the engine's.

    A grid point whose replay raises is DROPPED with its reason rather than
    scored as zero — a failed replay is not a strategy that made no money.
    """
    pts, notes = [], []
    for ms in grid:
        try:
            edge, n, missed = replay(int(ms))
        except Exception as e:                       # noqa: BLE001
            notes.append(f"{ms}ms: replay failed ({type(e).__name__}: {e})")
            continue
        if not math.isfinite(edge):
            notes.append(f"{ms}ms: non-finite edge")
            continue
        pts.append(Point(int(ms), float(edge), int(n), int(missed)))
    return Curve(sleeve, tuple(pts), "; ".join(notes))


def admission(curve: Curve, r_value: float, trades_per_year: float,
              engineering_cost: float, annual_infra_cost: float,
              target_ms: int = 0) -> dict:
    """221.3 in arithmetic. Does the recovered edge beat what it costs?

    Deliberately requires the costs as arguments and has no defaults: an
    admission test with a guessed engineering cost is a test that admits
    whatever the guesser wanted. Operational risk is NOT monetised here, because
    pretending to price it would be worse than naming it — it is returned as a
    line the reader must weigh.
    """
    v = curve.verdict()
    if not v.get("accelerate"):
        return {"admit": False, "why": v["why"], "recovered_per_year": 0.0}
    b = curve.baseline
    at_target = curve.edge_at(target_ms)
    if b is None or at_target is None:
        return {"admit": False, "why": f"no replay at the {target_ms}ms target"}
    # Current operating latency is the WORST measured point unless the caller
    # says otherwise: assuming the desk already runs near zero would credit the
    # improvement with an edge it never lost.
    worst = min(curve.points, key=lambda p: p.net_edge_r)
    recovered_r = (at_target - worst.net_edge_r) * trades_per_year
    recovered = recovered_r * r_value
    first_year = engineering_cost + annual_infra_cost
    return {
        "admit": recovered > first_year,
        "recovered_per_year": recovered,
        "first_year_cost": first_year,
        "measured_from": f"{worst.latency_ms}ms",
        "why": (f"recovering {at_target - worst.net_edge_r:+.4f}R per trade over "
                f"{trades_per_year:.0f} trades at {r_value:,.0f} per R is "
                f"{recovered:,.0f}/yr against {first_year:,.0f} of first-year "
                f"cost."),
        "unpriced": ("OPERATIONAL RISK IS NOT IN THIS NUMBER. A kernel-bypass "
                     "path is a new failure mode on the money path, and pricing "
                     "it would be worse than naming it. 221.3 requires it in the "
                     "comparison; this arithmetic cannot supply it."),
    }
