"""Execution algorithms as a registry of pure schedulers, competed on expected utility.

VeighNa's algo-trading registry translated to what an MT5 CFD venue can execute. An algorithm
here does not touch a socket: it turns a parent intent (symbol, side, lots, reference quote,
stop distance, edge) into a CHILD-ORDER PLAN -- a list of market / limit / wait children with
sizes, price offsets, time offsets and conditions -- and prices that plan with the desk's one
execution surface (`fill_surface`, duck-typed so a test or a challenger surface can stand in):

    market      one child, fill now at the quote, pay the modelled slip
    twap        even slices on a clock; smaller prints, edge decays while the clock runs
    iceberg     rest `display_lots` at the touch and replenish on each fill; size is hidden
    sniper      wait for the spread to come inside a threshold, market then or at the timeout
    pullback    rest a passive limit `offset_frac` better than the quote, market at the timeout

    utility = p_fill x edge_kept x edge_r - cost_r          (in R, by the intent's stop distance)

ONE COST CONVENTION, STATED. Every cost is a fraction of price RELATIVE TO THE REFERENCE QUOTE
the intent carries (ask for a buy, bid for a sell -- the `intended` the intent ledger records).
That is the convention `FillSurface.expected_slip` was fitted in and the one the markout
measures, so `record_outcome` can put expected and realised cost on the same axis without a
translation nobody will keep in step. A passive fill `d` better than the quote is a cost of
`-d`; a market print is the surface's slip, clamped at zero because a market order is never
assumed to improve. The spread itself is inside the quote and appears only when an algorithm
changes which quote it pays (sniper's narrowing, pullback's offset).

WAITING COSTS EDGE. A resting or delayed order fills into a market that has moved on; the desk
already pays for that in `execution_policy.fill_edge_decay`. Here the same idea is a clock:
`EDGE_DECAY_FRAC` of the edge is gone after `DECAY_HORIZON_S`, linearly, lots-weighted over the
children. It is a prior, and `scoreboard()` over recorded outcomes is how it gets replaced by a
measured number -- the learning loop for algorithm choice.

NO EDGE, NO ALGORITHM. Better execution of a trade not worth making is still a trade not worth
making: with `edge_r <= 0` every plan's utility is minus its cost, SKIP ranks first and
`compete` reports no positive algorithm. Nothing in this module sends an order.
"""
from __future__ import annotations

import json
import math
from collections.abc import Callable
from dataclasses import dataclass, field, replace
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

BASE = Path(__file__).resolve().parent.parent
#: Realised-against-expected rows per executed plan; `scoreboard` reads them per algorithm.
OUTCOMES = BASE / "data" / "execution_algo_outcomes.jsonl"

#: Fraction of the edge a plan loses by waiting DECAY_HORIZON_S (linear in the wait). Same
#: prior as `execution_policy.Context.fill_edge_decay`, expressed against a clock.
EDGE_DECAY_FRAC = 0.3
DECAY_HORIZON_S = 3600.0
#: Prior that a spread above its norm comes back inside the sniper's threshold before timeout.
P_SPREAD_NORMALISES = 0.6
#: Time between an iceberg fill and its replenished child, for the decay clock.
REPLENISH_S = 60.0
SKIP = "SKIP"


@dataclass(frozen=True)
class Intent:
    """A parent order as the sleeve wants it. `price` is the reference quote the intent ledger
    records as `intended`; `spread_frac_norm` is the trailing-normal spread when known, which
    is what the sniper waits for."""

    symbol: str
    side: str                       # "buy" | "sell"
    lots: float
    price: float
    stop_frac: float                # stop distance / price: the R denominator
    edge_r: float = 0.0
    spread_frac: float = 0.0
    atr_frac: float = 0.0
    hour: int = 0
    sleeve: str = ""
    spread_frac_norm: float | None = None


@dataclass(frozen=True)
class Plan:
    algo: str
    children: list[dict[str, Any]]
    lots: float
    p_fill: float                   # P(the parent is filled by the end of the plan)
    edge_kept: float                # fraction of edge_r left after the plan's waiting
    cost_frac: float                # expected cost per lot, fraction of price vs the quote
    cost_r: float                   # the same in R
    utility: float                  # p_fill * edge_kept * edge_r - cost_r
    detail: dict[str, Any] = field(default_factory=dict)
    intent: Intent | None = None

    def to_dict(self) -> dict[str, Any]:
        return {"algo": self.algo, "lots": self.lots, "p_fill": self.p_fill,
                "edge_kept": self.edge_kept, "cost_frac": self.cost_frac, "cost_r": self.cost_r,
                "utility": self.utility, "children": self.children, "detail": self.detail}


def _child(seq: int, kind: str, lots: float, *, offset: float = 0.0, at: float = 0.0,
           condition: str | None = None) -> dict[str, Any]:
    return {"seq": seq, "kind": kind, "lots": round(lots, 8),
            "price_offset_frac": round(offset, 8), "at_offset_s": round(at, 3),
            "condition": condition}


def _row(i: Intent, lots: float, distance_frac: float, order_type: str) -> dict[str, Any]:
    """The surface's feature row for one child, in the intent ledger's own vocabulary."""
    return {"spread_at_decision": i.spread_frac * i.price, "intended": i.price,
            "atr_frac": i.atr_frac, "time": f"2000-01-01T{int(i.hour) % 24:02d}:00:00+00:00",
            "lot": lots, "side": i.side, "distance_frac": distance_frac,
            "order_type": order_type}


def _surface(surface: Any | None) -> Any:
    if surface is not None:
        return surface
    from mt5desk.fill_surface import FillSurface
    return FillSurface()


def _decay(delay_s: float) -> float:
    return min(1.0, max(float(delay_s), 0.0) / DECAY_HORIZON_S) * EDGE_DECAY_FRAC


def _slip(fs: Any, i: Intent, lots: float) -> tuple[float, float]:
    mu, sd = fs.expected_slip(_row(i, lots, 0.0, "market"), i.spread_frac)
    return float(mu), float(sd)


def _finish(i: Intent, algo: str, children: list[dict[str, Any]], *, p_fill: float,
            edge_kept: float, cost_frac: float, **detail: Any) -> Plan:
    stop = max(float(i.stop_frac), 1e-9)
    cost_r = cost_frac / stop
    p = min(max(p_fill, 0.0), 1.0)
    kept = min(max(edge_kept, 0.0), 1.0)
    # NO EDGE, NO TRADE, WHATEVER THE EXECUTION (execution_policy's rule, kept identical).
    u = (p * kept * i.edge_r - cost_r) if i.edge_r > 0 else -abs(cost_r) - 1e-6
    return Plan(algo, children, round(i.lots, 8), round(p, 4), round(kept, 4),
                round(cost_frac, 8), round(cost_r, 6), round(u, 6), detail, i)


def _weights(lots: list[float], total: float) -> list[float]:
    if total > 0:
        return [x / total for x in lots]
    return [1.0 / len(lots)] * len(lots)


# --------------------------------------------------------------------------- the algorithms
def market(intent: Intent, *, surface: Any | None = None) -> Plan:
    """Fill now at the quote. The baseline every other algorithm has to beat."""
    fs = _surface(surface)
    mu, sd = _slip(fs, intent, intent.lots)
    return _finish(intent, "market", [_child(0, "market", intent.lots)], p_fill=1.0,
                   edge_kept=1.0, cost_frac=max(mu, 0.0), slip_mu=mu, slip_sd=sd)


def _split(total: float, n: int, lot_step: float | None) -> list[float]:
    """`n` even slices summing to `total` exactly. With a lot step the split is on the step
    grid and the leftover steps go one each to the first children, so the plan is sendable."""
    if lot_step is not None and lot_step > 0 and total > 0:
        steps = round(total / lot_step)
        base, extra = divmod(steps, n)
        return [round((base + (1 if k < extra else 0)) * lot_step, 8) for k in range(n)]
    per = round(total / n, 8)
    return [per] * (n - 1) + [round(total - per * (n - 1), 8)]


def twap(intent: Intent, *, slices: int = 4, horizon_s: float = 900.0,
         lot_step: float | None = None, surface: Any | None = None) -> Plan:
    """Even slices on a clock across `horizon_s`. Smaller prints pay less slip where the
    surface has learned size matters; every slice after the first pays the decay clock."""
    n = max(int(slices), 1)
    fs = _surface(surface)
    lots = _split(intent.lots, n, lot_step)
    step = float(horizon_s) / n
    children, cost, kept = [], 0.0, 0.0
    for k, (x, w) in enumerate(zip(lots, _weights(lots, intent.lots), strict=True)):
        at = k * step
        mu, _ = _slip(fs, intent, x)
        children.append(_child(k, "market", x, at=at, condition=None if k == 0 else "clock"))
        cost += w * max(mu, 0.0)
        kept += w * (1.0 - _decay(at))
    return _finish(intent, "twap", children, p_fill=1.0, edge_kept=kept, cost_frac=cost,
                   slices=n, horizon_s=float(horizon_s))


def iceberg(intent: Intent, *, display_lots: float | None = None, replenish: bool = True,
            surface: Any | None = None) -> Plan:
    """Show `display_lots` at the touch; on each fill show the next (`replenish`), or send the
    balance at market once the first displayed slice fills (`replenish=False`). Never displays
    more than `display_lots` at once -- that is the point of the algorithm."""
    fs = _surface(surface)
    total = float(intent.lots)
    disp = float(display_lots) if display_lots else (total / 3.0 if total > 0 else 0.0)
    if disp <= 0 or disp >= total:
        disp, n = total, 1
    else:
        n = math.ceil(total / disp - 1e-9)
    mu, _ = _slip(fs, intent, total)
    children, left = [], total
    sizes, kinds = [], []
    for k in range(n):
        if k > 0 and not replenish:
            sizes.append(round(left, 8))
            kinds.append("market")
            break
        x = round(min(disp, left), 8)
        left = round(left - x, 8)
        sizes.append(x)
        kinds.append("limit")
    cost = kept = p_fill = 0.0
    for k, (x, kind, w) in enumerate(zip(sizes, kinds, _weights(sizes, total), strict=True)):
        at = k * REPLENISH_S
        if kind == "limit":
            p = float(fs.p_fill(_row(intent, x, 0.0, "limit")))
            cond = None if k == 0 else f"after_fill:{k - 1}"
            children.append(_child(k, "limit", x, offset=0.0, at=at, condition=cond))
            cost += w * 0.0
        else:
            p = 1.0
            children.append(_child(k, "market", x, at=at, condition=f"after_fill:{k - 1}"))
            cost += w * max(mu, 0.0)
        p_fill += w * p
        kept += w * (1.0 - _decay(at))
    return _finish(intent, "iceberg", children, p_fill=p_fill, edge_kept=kept, cost_frac=cost,
                   display_lots=round(disp, 8), replenish=bool(replenish), slices=len(children))


def sniper(intent: Intent, *, max_spread_frac: float | None = None, timeout_s: float = 300.0,
           surface: Any | None = None) -> Plan:
    """Wait for the spread to come inside `max_spread_frac`, then market; market at the
    timeout regardless. When the spread is already inside, this IS market with a zero wait."""
    fs = _surface(surface)
    thr = (float(max_spread_frac) if max_spread_frac is not None
           else float(intent.spread_frac_norm if intent.spread_frac_norm is not None
                      else intent.spread_frac))
    mu, _ = _slip(fs, intent, intent.lots)
    ok_now = intent.spread_frac <= thr + 1e-12
    cond = f"spread_frac<={thr:.6g}"
    children = [_child(0, "wait", 0.0, condition=cond),
                _child(1, "market", intent.lots, at=(0.0 if ok_now else float(timeout_s)),
                       condition=f"{cond} or timeout:{float(timeout_s):g}")]
    if ok_now:
        p_ok, saving, wait = 1.0, 0.0, 0.0
    else:
        # Half the narrowing accrues to the entry side of the book; the rest of the wait is a
        # timeout market at the spread we already see.
        p_ok = P_SPREAD_NORMALISES
        saving = 0.5 * (intent.spread_frac - thr)
        wait = p_ok * float(timeout_s) / 2.0 + (1.0 - p_ok) * float(timeout_s)
    return _finish(intent, "sniper", children, p_fill=1.0, edge_kept=1.0 - _decay(wait),
                   cost_frac=max(mu, 0.0) - p_ok * saving, max_spread_frac=thr,
                   timeout_s=float(timeout_s), p_spread_ok=p_ok, expected_wait_s=round(wait, 1))


def pullback(intent: Intent, *, offset_frac: float | None = None, timeout_s: float = 600.0,
             surface: Any | None = None) -> Plan:
    """Rest a passive limit `offset_frac` better than the quote (default half an ATR, as
    execution_policy's PULLBACK); whatever is unfilled at the timeout goes market."""
    fs = _surface(surface)
    d = max(float(offset_frac) if offset_frac is not None else 0.5 * intent.atr_frac, 0.0)
    p = float(fs.p_fill(_row(intent, intent.lots, d, "limit")))
    mu, _ = _slip(fs, intent, intent.lots)
    children = [_child(0, "limit", intent.lots, offset=d,
                       condition=f"resting until timeout:{float(timeout_s):g}"),
                _child(1, "market", intent.lots, at=float(timeout_s),
                       condition="timeout: unfilled remainder")]
    kept = p * (1.0 - _decay(float(timeout_s) / 2.0)) + (1.0 - p) * (1.0 - _decay(timeout_s))
    return _finish(intent, "pullback", children, p_fill=1.0, edge_kept=kept,
                   cost_frac=p * (-d) + (1.0 - p) * max(mu, 0.0), offset_frac=round(d, 8),
                   p_limit=round(p, 4), timeout_s=float(timeout_s))


REGISTRY: dict[str, Callable[..., Plan]] = {
    "market": market, "twap": twap, "iceberg": iceberg, "sniper": sniper, "pullback": pullback,
}


# --------------------------------------------------------------------------- the competition
def compete(intent: Intent, surface: Any | None = None, *, spread_frac: float | None = None,
            edge_r: float | None = None, stop_frac: float | None = None,
            hour: int | None = None, params: dict[str, dict[str, Any]] | None = None
            ) -> dict[str, Any]:
    """Every registered algorithm's plan for `intent`, ranked by utility, SKIP included at
    zero. Keyword overrides replace the intent's own fields; `params` supplies per-algorithm
    keyword arguments (`{"twap": {"slices": 6}}`). An algorithm that raises is reported under
    `errors` and left out of the ranking rather than taking the competition down."""
    over = {k: v for k, v in {"spread_frac": spread_frac, "edge_r": edge_r,
                              "stop_frac": stop_frac, "hour": hour}.items() if v is not None}
    i = replace(intent, **over) if over else intent
    plans: dict[str, Plan] = {}
    errors: dict[str, str] = {}
    for name, fn in REGISTRY.items():
        try:
            plans[name] = fn(i, surface=surface, **((params or {}).get(name) or {}))
        except Exception as exc:
            # One misconfigured algorithm (a bad `params` entry, a surface that cannot price a
            # row) must not take the whole competition down: it is reported and out-ranked.
            errors[name] = f"{type(exc).__name__}: {exc}"
    plans[SKIP] = Plan(SKIP, [], round(i.lots, 8), 0.0, 0.0, 0.0, 0.0, 0.0,
                       {"why": "no algorithm has positive utility"}, i)
    ranked = sorted(plans.values(), key=lambda p: p.utility, reverse=True)
    best_plan = ranked[0]
    return {"symbol": i.symbol, "side": i.side, "lots": round(i.lots, 8), "edge_r": i.edge_r,
            "best": best_plan.algo, "utility": best_plan.utility,
            "would_trade": best_plan.algo != SKIP,
            "positive": [p.algo for p in ranked if p.utility > 0],
            "utilities": {p.algo: p.utility for p in ranked},
            "ranked": [p.algo for p in ranked], "plans": {p.algo: p for p in ranked},
            "errors": errors,
            "surface": str(getattr(surface, "note", "prior: spread model"))}


def best(intent: Intent, surface: Any | None = None, **kw: Any) -> Plan:
    comp = compete(intent, surface, **kw)
    return comp["plans"][comp["best"]]


def summary(comp: dict[str, Any]) -> dict[str, Any]:
    """The competition as a JSON-safe row for the intent ledger: the winner, every utility,
    and the winner's children -- enough to score the road not taken later."""
    bp = comp["plans"][comp["best"]]
    return {"best": comp["best"], "utility": comp["utility"],
            "would_trade": comp["would_trade"], "utilities": comp["utilities"],
            "positive": comp["positive"], "p_fill": bp.p_fill, "cost_frac": bp.cost_frac,
            "children": bp.children, "errors": comp["errors"], "surface": comp["surface"]}


# --------------------------------------------------------------------------- the learning loop
def record_outcome(plan: Plan, fills: list[Any], *, path: Path | str | None = None,
                   at: datetime | str | None = None) -> dict[str, Any]:
    """Append what the plan expected against what the venue did. `fills` are `(lots, price)`
    pairs or `{"lots", "price"}` rows, lots unsigned. Realised cost is the lots-weighted fill
    price against the intent's reference quote, signed so that worse-than-asked is positive --
    the markout's own sign -- and is null, never zero, when nothing filled."""
    p = Path(path) if path is not None else OUTCOMES
    pairs: list[tuple[float, float]] = []
    for f in fills or []:
        try:
            lots, price = (float(f["lots"]), float(f["price"])) if isinstance(f, dict) \
                else (float(f[0]), float(f[1]))
        except (KeyError, IndexError, TypeError, ValueError):
            continue
        if lots > 0 and price > 0:
            pairs.append((lots, price))
    tot = sum(x for x, _ in pairs)
    realised: float | None = None
    i = plan.intent
    if tot > 0 and i is not None and i.price > 0:
        d = 1.0 if i.side.startswith("buy") else -1.0
        realised = round(sum(x * (px - i.price) * d / i.price for x, px in pairs) / tot, 8)
    filled_frac = round(tot / plan.lots, 6) if plan.lots > 0 else (1.0 if tot > 0 else 0.0)
    row = {"at": _iso(at), "algo": plan.algo, "symbol": i.symbol if i else None,
           "side": i.side if i else None, "lots": plan.lots, "filled_lots": round(tot, 8),
           "expected_cost": plan.cost_frac, "realised_cost": realised,
           "filled_frac": filled_frac, "expected_p_fill": plan.p_fill,
           "utility": plan.utility, "n_fills": len(pairs)}
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("a", encoding="utf-8") as f:
        f.write(json.dumps(row) + "\n")
    return row


def _iso(at: datetime | str | None) -> str:
    if at is None:
        return datetime.now(tz=UTC).isoformat()
    return at.isoformat() if isinstance(at, datetime) else str(at)


def _rows(path: Path) -> list[dict[str, Any]]:
    try:
        return [json.loads(ln) for ln in path.read_text("utf-8").splitlines() if ln.strip()]
    except (OSError, ValueError):
        return []


def scoreboard(path: Path | str | None = None, rows: list[dict[str, Any]] | None = None
               ) -> dict[str, Any]:
    """Per algorithm: n, mean realised cost, mean expected cost, mean filled fraction and the
    mean surprise (realised - expected). Means over realised cost use only rows that filled;
    an algorithm that never filled shows null there, not a flattering zero."""
    xs = rows if rows is not None else _rows(Path(path) if path is not None else OUTCOMES)
    by: dict[str, list[dict[str, Any]]] = {}
    for r in xs:
        if isinstance(r, dict) and r.get("algo"):
            by.setdefault(str(r["algo"]), []).append(r)

    def mean(vals: list[float]) -> float | None:
        return round(sum(vals) / len(vals), 8) if vals else None

    algos: dict[str, dict[str, Any]] = {}
    for algo, rs in sorted(by.items()):
        real = [float(r["realised_cost"]) for r in rs if r.get("realised_cost") is not None]
        exp = [float(r["expected_cost"]) for r in rs if r.get("expected_cost") is not None]
        surprise = [float(r["realised_cost"]) - float(r["expected_cost"]) for r in rs
                    if r.get("realised_cost") is not None and r.get("expected_cost") is not None]
        algos[algo] = {"n": len(rs), "mean_realised_cost": mean(real),
                       "mean_expected_cost": mean(exp),
                       "mean_filled_frac": mean([float(r.get("filled_frac") or 0.0) for r in rs]),
                       "mean_surprise": mean(surprise), "n_filled": len(real)}
    return {"generated_utc": datetime.now(tz=UTC).isoformat(), "n": len(xs), "algos": algos,
            "path": str(path) if path is not None else (None if rows is not None
                                                        else str(OUTCOMES))}
