"""Q4 -- THE WORLD MODEL AS A LABORATORY: do(shock), then read the tape it implies.

THE PRINCIPAL, 2026-09-16: build a market world-model laboratory and use it as an INTERVENTION
lab -- do(shock) -> participants -> liquidity -> positioning -> prices -> residual -- to GENERATE
hypotheses that then go through the real gauntlet.

WHAT IT ADDS TO THE GRAPH IT READS. `world_causal_graph` measures what ALREADY HAPPENED: a
correlation between two series at a lag. It answers "did X lead Y" and cannot answer "what happens
to Y if X moves and the funds whose mandates force them to react, react" -- because that answer is
not one arc, it is that arc plus the second- and third-order paths the same shock opens plus the
participants who must transact once the move is large enough.

WHAT IT IS NOT, AND THIS IS THE WHOLE SAFETY ARGUMENT. Nothing simulated here is evidence. A
synthetic path cannot certify, size, promote, or be cited as a measurement. The lab's only output
with any authority is a QUESTION -- a structured hypothesis donated under the seat `world_lab`
with `source: "world_lab:<scenario>"`, which then takes the identical ten gates on REAL history
every other candidate takes.

THE MODEL is a linear-Gaussian structural simulator -- an SVAR impulse response over the graph:

    z[n, t] = persistence * z[n, t-1] + sum over arcs (s -> n at lag L) of beta * z[s, t-L]

Everything is in SIGMA UNITS of the node's own series, which is why the graph's `strength` is
usable as beta unconverted: a cross-correlation IS the standardised regression coefficient. An
instrument's move is its cumulative z times its measured H1 return sd, the only place a price
scale enters. `do(X)` CUTS THE ARCS INTO X: while the intervention is delivered the trigger is
SET, not computed, or the experiment would be a conditioning instead.

IDENTITIES ARE MERGED, NOT PROPAGATED. A lag-0 STRUCTURAL arc into an instrument
(`commodity:gold -> XAUUSD`, `currency:CAD -> USDCAD` opposite) does not say gold CAUSES XAUUSD --
it says the desk measures gold THROUGH XAUUSD. Kept as an arc it re-adds the node to itself every
bar, so the loader ALIASES it onto the instrument and composes the sign into every arc that
touched it. What survives at lag 0 is containment (`country:US -> cb:FED`), a real contemporaneous
arc, settled level by level.

PARTICIPANTS ARE RESPONSE OPERATORS, not arcs: a vol-control fund has no arc into gold, it has a
mandate that fires once realised vol crosses a level the structural path just crossed. Four act on
the path (`vol_control` deleveraging after a spike, `cta_trigger` continuation past a Donchian
break in sigma, `dealer_gamma` damping or amplifying a large bar, `systematic_rebalance` pushing
back against the accumulated move) and `market_maker` widens the round trip at handovers -- the
COST, not the path, which is the honest place for it. `market_ecology` supplies their PRESENCE and
SIGN when its report exists, and the MAGNITUDE for `vol_control` and `cta_trigger` only: a pinning
distance establishes that dealers are there, not how hard they push. Each coefficient says which.

THE NUMBER THIS ORGAN EXISTS TO PUBLISH is not the path. It is the DISAGREEMENT between the
simulated effect and what the trigger's direct arc alone predicts. Near zero, the graph was
already the whole answer. Large, and the chain or the participants carry the move -- and that gap
per instrument is the `residual`, the only quantity measured against cost and the one a hypothesis
is minted from.

UNMEASURED IS A REAL ANSWER (L1.28a). No graph, no lab. Where the graph has measured arcs but
ADMITTED none, the lab falls back to RECORDED_NOT_ADMITTED at beta x RECORDED_SHRINK and says so
in `edge_basis`, in `unmeasured` and in every donation's `why` -- it never quietly promotes a
rejected arc to a believed one. Arcs beyond the horizon, instruments with no bars, scenarios whose
trigger reaches nothing, and how far short a donation-less run fell (`best_residual_over_cost`)
are all counted, never rounded to zero.

    python desks/mt5/research/world_lab.py [--dry-run] [--seed N] [--max-donations 20]
"""
from __future__ import annotations

import argparse
import json
import math
import os
import sys
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np

DESK = Path(__file__).resolve().parents[1]
ROOT = DESK.parent.parent
for _p in (str(DESK), str(DESK / "research"), str(ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

GRAPH = DESK / "data" / "world_causal_graph.json"
CAUSAL_LAB = DESK / "reports" / "CAUSAL_LAB.json"
ECOLOGY = DESK / "reports" / "MARKET_ECOLOGY.json"
COST_SURFACE = DESK / "data" / "cost_surface.json"
UNI = DESK / "data" / "universe"
OUT = DESK / "reports" / "WORLD_LAB.json"

#: The seat donations land under. The SCENARIO rides on each row's own `source`
#: (`world_lab:cpi_surprise`), never on the directory: a colon is not a legal path character on
#: the box that trades, and six seats would fragment one organ's measured conversion into six.
SEAT = "world_lab"
SEED = 20260916
MT5 = "mt5_instrument"

#: An arc's lag is in its own clock; the lab's bar is H1, the timeframe donations declare.
CLOCK_BARS = {"H1": 1, "D1": 24, "W1": 120}
#: Ten trading days. NOT a style choice: this graph's arcs are mostly on the W1 clock, so a
#: 48-bar horizon saw 117 of 195 and four of six scenarios propagated NOTHING. Arcs past it are
#: counted in `unmeasured`, never silently dropped.
HORIZON = 240
DRAWS = 256
MAX_DONATIONS = 20
#: The AR(1) diagonal, ZERO ON PURPOSE. Every beta is a lagged cross-correlation of per-bar
#: RETURNS: 1 sigma in X implies beta sigma in Y at that lag, once. An AR term is a second claim
#: -- that returns are autocorrelated -- the graph never measured. The first build carried 0.6,
#: multiplying each node's cumulative response by 1/(1-0.6), which forced sum|beta| into a node
#: down to 0.30 for stability and crushed the multi-hop paths the lab exists to find.
PERSISTENCE = 0.0
#: No state may exceed Z_CLIP and sum|beta| into a node plus persistence is held under
#: STABILITY_MAX (scaled rows published): a measured graph is not guaranteed acyclic and a
#: resonant loop would mint hypotheses out of an arithmetic artefact.
Z_CLIP = 25.0
STABILITY_MAX = 0.90
#: A RECORDED_NOT_ADMITTED arc failed its admission bar. It is still a measurement, so the lab may
#: explore it when nothing is admitted -- at half weight, and never silently.
RECORDED_SHRINK = 0.5
MIN_SE = 0.02
SIGMA_BARS = 4000
#: Round trips at two spread crossings, as `mt5desk.engine.Costs.from_symbol(.., mult=2)`.
ROUND_TRIPS = 2.0

#: A shock is declared in DAILY sigma -- the clock a CPI print lives on -- and injected over the
#: event day's bars, cumulating to shock * sqrt(SHOCK_BARS) H1 sigma. Putting it all in ONE H1 bar
#: understated every macro shock by sqrt(24) and left the vol-calibrated participant thresholds
#: unreachable by anything downstream.
SHOCK_BARS = 24
VOL_WINDOW = 24
VOL_SPIKE_Z = 2.0
CTA_TRIGGER_Z = 1.5
GAMMA_SCALE = 2.0
PARTICIPANT_SE = 0.35
#: Bars before a path-side operator may fire again. THE OPERATORS ARE EDGE-TRIGGERED AND THIS IS
#: WHY: level-triggered, `vol_control` added its drift on EVERY bar the condition held -- over 240
#: bars, -28 sigma from one spike, and the first run duly reported USDCNH at -21.4 sigma off a
#: +2 sigma equity shock. A vol-target fund cuts once per episode.
FIRE_COOLDOWN = 48
#: vol_control: post-spike drift in sigma, NEGATIVE being the footprint (forced selling).
#: cta_trigger: continuation in sigma, signed by the move. dealer_gamma: >0 damps a large bar
#: (dealers long gamma), <0 amplifies it. systematic_rebalance: fraction of the accumulated move
#: pushed back at the month-end bar. market_maker: multiplier on the round trip at a handover.
DEFAULT_PARTICIPANTS: dict[str, float] = {"vol_control": -0.12, "cta_trigger": 0.08,
                                          "dealer_gamma": 0.25, "systematic_rebalance": 0.10,
                                          "market_maker": 0.15}
FALLBACK_FAMILY = "macro_conditional"

#: Each scenario names its transmission chain and a LADDER of trigger nodes: the first that
#: exists AND reaches a tradable instrument inside the horizon is used, substitution recorded.
#: Not a fudge -- `event:US_CPI` has no measured outgoing arc here and `country:US` has three that
#: dead-end in world nodes, and a scenario that reaches no price has not run.
SCENARIOS: dict[str, dict[str, Any]] = {
    "cpi_surprise": {
        "shock": 1.5, "month_end": False,
        "nodes": ["event:US_CPI", "yield:US2Y", "country:US", "currency:USD"],
        "chain": ("+1.5 sigma US CPI -> the front end reprices -> the dollar bids -> gold and "
                  "the dollar crosses take the mirror leg -> vol-control cuts into the spike"),
    },
    "usd_shock": {
        "shock": 1.5, "month_end": False,
        "nodes": ["currency:USD", "USDX"],
        "chain": ("+1.5 sigma broad dollar -> every USD-quoted cross by construction -> "
                  "dollar-priced commodities -> the exporters' indices a lag later"),
    },
    "oil_supply_shock": {
        "shock": 2.0, "month_end": False,
        "nodes": ["commodity:wti", "XTIUSD", "commodity:brent"],
        "chain": ("+2 sigma crude supply shock -> WTI and Brent -> the commodity currencies "
                  "(CAD, NOK) -> indices through the input-cost channel -> CTA continuation once "
                  "the move clears the trend trigger"),
    },
    "equity_vol_spike": {
        "shock": 2.0, "month_end": False,
        "nodes": ["vol:VIX", "index:SPX", "US500"],
        "chain": ("+2 sigma equity vol -> index beta -> the funding currencies (JPY, CHF) bid -> "
                  "vol-control deleverages the following day -> dealers hedging gamma damp or "
                  "amplify the bars while it happens"),
    },
    "gold_positioning_unwind": {
        "shock": -1.5, "month_end": False,
        "nodes": ["positioning:COT_gold", "commodity:gold", "XAUUSD"],
        "chain": ("-1.5 sigma unwind in speculative gold length -> gold spot -> silver and "
                  "platinum through the precious complex -> the dollar as the mirror leg"),
    },
    "central_bank_hawkish_surprise": {
        "shock": 1.5, "month_end": True,
        "nodes": ["cb:FED", "yield:US2Y", "country:US", "currency:USD"],
        "chain": ("+1.5 sigma hawkish Fed surprise -> the front end -> the dollar -> gold and the "
                  "rate-sensitive indices -> a month-end rebalance pushing back against whatever "
                  "the horizon accumulated"),
    },
}


# ------------------------------------------------------------------------------- network
@dataclass
class Edge:
    """One arc, already converted to H1 bars and a standardised beta."""

    src: str
    dst: str
    lag: int
    beta: float
    se: float
    basis: str


@dataclass
class Network:
    nodes: list[str]
    kinds: dict[str, str]
    edges: list[Edge]
    basis: str
    alias: dict[str, tuple[str, float]] = field(default_factory=dict)
    scaled_rows: int = 0
    notes: list[str] = field(default_factory=list)
    index: dict[str, int] = field(default_factory=dict)

    def __post_init__(self) -> None:
        self.index = {n: i for i, n in enumerate(self.nodes)}

    def instruments(self) -> list[str]:
        return [n for n in self.nodes if self.kinds.get(n) == MT5]

    def proxy_of(self, node: str) -> tuple[str, float] | None:
        """The instrument a node PRICES, with its sign -- itself when it is already one."""
        return (node, 1.0) if self.kinds.get(node) == MT5 else self.alias.get(node)


def _read_json(path: Path) -> dict[str, Any]:
    try:
        doc = json.loads(path.read_text("utf-8"))
    except (OSError, ValueError):
        return {}
    return doc if isinstance(doc, dict) else {}


def _edge_se(row: dict[str, Any]) -> float:
    best = ((row.get("evidence") or {}).get("xcorr") or {}).get("best") or {}
    sd = best.get("sd_boot")
    if isinstance(sd, (int, float)) and math.isfinite(float(sd)) and float(sd) > 0:
        return float(sd)
    n = row.get("n")
    return float(1.0 / math.sqrt(float(n))) if isinstance(n, (int, float)) and n > 4 else MIN_SE


def _lab_edges(doc: dict[str, Any], kinds: dict[str, str]) -> list[Edge]:
    """`CAUSAL_LAB.json`, read TOLERANTLY -- another seat owns its schema and it may not exist.

    Only `src`/`dst`/`lag`/`klass` are required, and only a klass NAMING a causal verdict is
    taken. A class this lab does not recognise is left alone rather than guessed at.
    """
    out: list[Edge] = []
    rows = doc.get("edges")
    if not isinstance(rows, list):
        return out
    for r in rows:
        if not isinstance(r, dict):
            continue
        src, dst = str(r.get("src") or ""), str(r.get("dst") or "")
        klass = str(r.get("klass") or r.get("class") or "").upper()
        beta = r.get("beta", r.get("strength"))
        if src not in kinds or dst not in kinds or src == dst:
            continue
        if not any(k in klass for k in ("CAUSAL", "CONFIRM", "ADMIT")):
            continue
        if not isinstance(beta, (int, float)) or not math.isfinite(float(beta)):
            continue
        out.append(Edge(src, dst, max(int(r.get("lag") or 1), 0), float(beta), MIN_SE,
                        "causal_lab"))
    return out


def _aliases(rows: list[dict[str, Any]], kinds: dict[str, str]) -> dict[str, tuple[str, float]]:
    """World node -> (instrument, sign) for every lag-0 STRUCTURAL arc into an instrument."""
    direct: dict[str, tuple[str, float]] = {}
    for r in rows:
        if str(r.get("status") or "") != "STRUCTURAL" or int(r.get("lag") or 0) != 0:
            continue
        src, dst = str(r.get("src") or ""), str(r.get("dst") or "")
        if kinds.get(dst) == MT5 and src in kinds and src not in direct:
            direct[src] = (dst, -1.0 if str(r.get("direction")) == "opposite" else 1.0)
    out: dict[str, tuple[str, float]] = {}
    for node in direct:
        cur, sign = node, 1.0
        for _ in range(8):
            step = direct.get(cur)
            if step is None:
                break
            cur, sign = step[0], sign * step[1]
        if cur != node:
            out[node] = (cur, sign)
    return out


def load_network(graph_path: Path = GRAPH, lab_path: Path = CAUSAL_LAB) -> Network | None:
    """The simulator's network, or None when there is no graph to intervene on."""
    doc = _read_json(graph_path)
    nodes, rows = doc.get("nodes"), doc.get("edges")
    if not isinstance(nodes, list) or not isinstance(rows, list) or not nodes:
        return None
    kinds = {str(n.get("id")): str(n.get("kind") or "") for n in nodes if isinstance(n, dict)}
    alias = _aliases([r for r in rows if isinstance(r, dict)], kinds)
    buckets: dict[str, list[Edge]] = {"structural": [], "admitted": [], "recorded": []}
    for r in rows:
        if not isinstance(r, dict):
            continue
        src, dst = str(r.get("src") or ""), str(r.get("dst") or "")
        if src not in kinds or dst not in kinds:
            continue
        (src, s_sign), (dst, d_sign) = alias.get(src, (src, 1.0)), alias.get(dst, (dst, 1.0))
        if src == dst:
            continue
        status = str(r.get("status") or "")
        sign = s_sign * d_sign * (-1.0 if str(r.get("direction") or "same") == "opposite" else 1.0)
        lag = int(r.get("lag") or 0) * CLOCK_BARS.get(str(r.get("clock") or "H1"), 1)
        if status == "STRUCTURAL":
            buckets["structural"].append(Edge(src, dst, 0, sign, 0.0, "structural"))
            continue
        strength = r.get("strength")
        if not isinstance(strength, (int, float)) or not math.isfinite(float(strength)):
            continue
        beta = abs(float(strength)) * sign
        if status == "ADMITTED":
            buckets["admitted"].append(Edge(src, dst, max(lag, 1), beta, _edge_se(r), "admitted"))
        elif status == "RECORDED_NOT_ADMITTED":
            buckets["recorded"].append(Edge(src, dst, max(lag, 1), beta * RECORDED_SHRINK,
                                            _edge_se(r), "recorded"))
    lab = _lab_edges(_read_json(lab_path), kinds)
    live, notes = [*buckets["admitted"], *lab], []
    if live:
        basis = "admitted" + ("+causal_lab" if lab else "")
    else:
        basis = "recorded_not_admitted (FALLBACK)"
        live = buckets["recorded"]
        notes.append(f"the graph ADMITS 0 arcs, so the lab propagates the {len(live)} "
                     f"RECORDED_NOT_ADMITTED ones at beta x {RECORDED_SHRINK}. Every donation "
                     "from this run names that basis; none of it is evidence either way.")
    net = Network(nodes=[n for n in sorted(kinds) if n not in alias], kinds=kinds,
                  edges=[*buckets["structural"], *live], basis=basis, alias=alias, notes=notes)
    _stabilise(net)
    return net


def _stabilise(net: Network) -> None:
    """Hold sum|beta| + persistence into each node under STABILITY_MAX.

    A loop whose gain exceeds one turns an impulse response into a divergent series. Scaling
    the offending row keeps that node's parents in proportion and caps only their total; the
    count is published, because a graph needing this everywhere is a graph with cycles.
    """
    incoming: dict[str, list[Edge]] = {}
    for e in net.edges:
        if e.basis != "structural":
            incoming.setdefault(e.dst, []).append(e)
    room = STABILITY_MAX - PERSISTENCE
    for group in incoming.values():
        total = sum(abs(e.beta) for e in group)
        if total > room > 0:
            for e in group:
                e.beta *= room / total
                e.se *= room / total
            net.scaled_rows += 1


# ------------------------------------------------------------------------- bars and cost
_BARS: dict[str, dict[str, float] | None] = {}


def bar_stats(symbol: str) -> dict[str, float] | None:
    """`{price, sigma_h1, median_abs_daily}` from the desk's lake, or None.

    The only place a price scale enters. A symbol with no parquet, or a box with no pandas,
    returns None and every number depending on it is published as null, never as a zero.
    """
    if symbol in _BARS:
        return _BARS[symbol]
    _BARS[symbol] = None
    path = UNI / f"{symbol}_H1.parquet"
    if not path.exists():
        return None
    try:
        import pandas as pd
        df = pd.read_parquet(path, columns=["close"])
    except (OSError, ValueError, ImportError, KeyError):
        return None
    close = np.asarray(df["close"], dtype=float)[-SIGMA_BARS:]
    close = close[np.isfinite(close) & (close > 0)]
    if close.size < 500:
        return None
    r = np.diff(np.log(close))
    daily = r[: (r.size // 24) * 24].reshape(-1, 24).sum(axis=1) if r.size >= 24 else r
    sd = float(np.std(r, ddof=1))
    if not math.isfinite(sd) or sd <= 0:
        return None
    _BARS[symbol] = {"price": float(close[-1]), "sigma_h1": sd,
                     "median_abs_daily": float(np.median(np.abs(daily)))}
    return _BARS[symbol]


def cost_fraction(symbol: str, surface: dict[str, Any]) -> tuple[float | None, str]:
    """(round trip as a fraction of price, how it was arrived at)."""
    stats = bar_stats(symbol)
    row = (surface.get("symbols") or {}).get(symbol)
    if stats and isinstance(row, dict):
        pts, tick = row.get("pooled_median_spread_pts"), row.get("tick_size")
        if isinstance(pts, (int, float)) and isinstance(tick, (int, float)) and pts > 0:
            c = ROUND_TRIPS * float(pts) * float(tick) / stats["price"]
            if math.isfinite(c) and c > 0:
                return c, "cost_surface pooled median spread x 2 crossings"
    if stats and stats["median_abs_daily"] > 0:
        return 1.5 * stats["median_abs_daily"] / 10.0, "proxy: 1.5 x median |daily return| / 10"
    return None, "UNMEASURED: no cost surface row and no bars on this box"


def participant_table(net: Network, doc: dict[str, Any]) -> tuple[dict[str, dict[str, Any]], str]:
    """Per-instrument response coefficients, each carrying where it came from.

    `market_ecology` measures a FOOTPRINT -- that a class is present and, for two of them, the
    return effect it leaves -- not a transmission coefficient. So it gives presence and sign for
    all five and MAGNITUDE for `vol_control` and `cta_trigger` only; the rest keep the stated
    prior and SAY `prior`, so nobody reads a guess as a measurement.
    """
    raw = doc.get("symbols")
    symbols: dict[str, Any] = raw if isinstance(raw, dict) else {}
    basis = "measured (reports/MARKET_ECOLOGY.json)" if symbols else (
        "STATED PRIORS: reports/MARKET_ECOLOGY.json is absent, so no participant coefficient "
        "here has been measured on this box")
    table: dict[str, dict[str, Any]] = {}
    for sym in net.instruments():
        row: dict[str, Any] = {k: {"value": v, "basis": "prior"}
                               for k, v in DEFAULT_PARTICIPANTS.items()}
        meas = symbols.get(sym)
        stats = bar_stats(sym)
        scale = stats["sigma_h1"] * math.sqrt(VOL_WINDOW) if stats else 0.0
        if isinstance(meas, dict) and scale > 0:
            effect = (meas.get("vol_control") or {}).get("effect")
            if isinstance(effect, (int, float)):
                row["vol_control"] = {"value": float(effect) / scale, "basis": "measured"}
            hits = [float(lv["continuation_24h"]) for lv in
                    ((meas.get("cta_trigger") or {}).get("levels") or [])
                    if isinstance(lv, dict)
                    and isinstance(lv.get("continuation_24h"), (int, float))]
            if hits:
                row["cta_trigger"] = {"value": max(hits, key=abs) / scale, "basis": "measured"}
            pin = (meas.get("dealer_gamma") or {}).get("effect")
            if isinstance(pin, (int, float)):
                # NEGATIVE distance-to-round = pinned = dealers long gamma = the bar is damped.
                row["dealer_gamma"] = {
                    "value": math.copysign(DEFAULT_PARTICIPANTS["dealer_gamma"], -float(pin)),
                    "basis": "sign measured, magnitude prior"}
        table[sym] = row
    return table, basis


# --------------------------------------------------------------------------------- lab
class Lab:
    """The seeded Monte Carlo intervention engine over one network."""

    def __init__(self, net: Network, table: dict[str, dict[str, Any]], *, draws: int = DRAWS,
                 horizon: int = HORIZON, seed: int = SEED) -> None:
        self.net = net
        self.draws = max(int(draws), 1)
        self.horizon = max(int(horizon), 2)
        self.seed = int(seed)
        self.table = table
        self.inst = net.instruments()
        self.inst_idx = np.array([net.index[s] for s in self.inst], dtype=int)

    def _coef(self, rng: np.random.Generator, name: str) -> np.ndarray:
        base = np.array([float(self.table.get(s, {}).get(name, {}).get(
            "value", DEFAULT_PARTICIPANTS[name])) for s in self.inst], dtype=float)
        return base[None, :] * (1.0 + rng.normal(0.0, PARTICIPANT_SE, size=(self.draws, 1)))

    def _groups(self, edges: list[Edge], rng: np.random.Generator) -> dict[int, list[Any]]:
        """Arcs bucketed by lag, one beta draw per Monte Carlo path.

        Structural arcs get no draw -- a standard error on an identity publishes uncertainty
        the desk does not have. Lag 0 is split into levels so one ordered pass settles a
        contemporaneous chain exactly, with no relaxation.
        """
        out: dict[int, list[Any]] = {}
        by_lag: dict[int, list[Edge]] = {}
        for e in edges:
            by_lag.setdefault(e.lag, []).append(e)
        for lag, rows in sorted(by_lag.items()):
            for level in (_levels(rows) if lag == 0 else [rows]):
                src = np.array([self.net.index[e.src] for e in level], dtype=int)
                dst = np.array([self.net.index[e.dst] for e in level], dtype=int)
                mu = np.array([e.beta for e in level], dtype=float)
                se = np.array([0.0 if e.basis == "structural" else e.se for e in level])
                beta = mu + rng.normal(0.0, 1.0, size=(self.draws, len(level))) * se
                out.setdefault(lag, []).append((src, dst, beta, len(set(dst.tolist())) == len(dst)))
        return out

    def simulate(self, trigger: str, shock: float, *, edges: list[Edge] | None = None,
                 participants: bool = True, month_end: bool = False
                 ) -> tuple[np.ndarray, dict[str, np.ndarray]]:
        """do(trigger = shock) and propagate. Returns (z paths, per-participant contributions)."""
        rng = np.random.default_rng(self.seed)
        net, ti = self.net, self.net.index[trigger]
        groups = self._groups(net.edges if edges is None else edges, rng)
        rows = np.arange(self.draws)[:, None]
        z = np.zeros((self.draws, len(net.nodes), self.horizon + 1), dtype=float)
        span = min(SHOCK_BARS, self.horizon)
        per_bar = float(shock) * math.sqrt(SHOCK_BARS) / span
        z[:, ti, 0:span] = per_bar
        _settle(z[:, :, 0], groups.get(0, []), rows)
        coef = {k: self._coef(rng, k) for k in DEFAULT_PARTICIPANTS} if participants else {}
        contrib = {k: np.zeros((self.draws, len(self.inst))) for k in DEFAULT_PARTICIPANTS}
        fired = {k: np.full((self.draws, len(self.inst)), -1e6) for k in
                 ("vol_control", "cta_trigger")}
        cum = z[:, self.inst_idx, 0].copy()
        rebalance_bar = self.horizon // 2 if month_end else -1
        for t in range(1, self.horizon + 1):
            cur = PERSISTENCE * z[:, :, t - 1]
            for lag, levels in groups.items():
                if lag == 0 or t - lag < 0:
                    continue
                for src, dst, beta, unique in levels:
                    _scatter(cur, rows, dst, beta * z[:, src, t - lag], unique)
            _settle(cur, groups.get(0, []), rows)
            z[:, :, t] = np.clip(cur, -Z_CLIP, Z_CLIP)
            if t < span:
                z[:, ti, t] = per_bar          # do(X) cuts the arcs INTO X while it is delivered
            if participants:
                self._respond(z, t, cum, coef, contrib, fired, rebalance_bar)
            cum = cum + z[:, self.inst_idx, t]
        return z, contrib

    def _respond(self, z: np.ndarray, t: int, cum: np.ndarray, coef: dict[str, np.ndarray],
                 contrib: dict[str, np.ndarray], fired: dict[str, np.ndarray],
                 rebalance_bar: int) -> None:
        """The four path-side operators, in the order a bar actually meets them."""
        idx = self.inst_idx
        cur = z[:, idx, t]
        damped = cur * (1.0 - coef["dealer_gamma"] * np.tanh(np.abs(cur) / GAMMA_SCALE))
        contrib["dealer_gamma"] += damped - cur
        cur = damped
        spike = np.abs(z[:, idx, max(0, t - VOL_WINDOW):t + 1]).sum(axis=2) >= VOL_SPIKE_Z
        delta = coef["vol_control"] * _fire(spike, fired["vol_control"], t)
        contrib["vol_control"] += delta
        cur = cur + delta
        trend = np.abs(cum) >= CTA_TRIGGER_Z
        delta = coef["cta_trigger"] * np.sign(cum) * _fire(trend, fired["cta_trigger"], t)
        contrib["cta_trigger"] += delta
        cur = cur + delta
        if t == rebalance_bar:
            delta = -coef["systematic_rebalance"] * cum
            contrib["systematic_rebalance"] += delta
            cur = cur + delta
        z[:, idx, t] = cur


def _levels(edges: list[Edge]) -> list[list[Edge]]:
    """Lag-0 arcs split so every arc's source is settled by an earlier level."""
    parents = {e.dst: e.src for e in edges}
    out: dict[int, list[Edge]] = {}
    for e in edges:
        node, depth = e.src, 0
        while node in parents and depth < 8:
            node, depth = parents[node], depth + 1
        out.setdefault(depth, []).append(e)
    return [out[k] for k in sorted(out)]


def _fire(condition: np.ndarray, last: np.ndarray, t: int) -> np.ndarray:
    """1.0 where `condition` holds and the operator has not fired inside FIRE_COOLDOWN bars.

    Mutates `last`: an operator is a DECISION, and a fund that cut at bar 40 has already cut at 41.
    """
    go = condition & ((t - last) >= FIRE_COOLDOWN)
    last[go] = float(t)
    return go.astype(float)


def _scatter(bar: np.ndarray, rows: np.ndarray, dst: np.ndarray, vals: np.ndarray,
             unique: bool) -> None:
    """`bar[:, dst] += vals`, taking the fast path when no destination repeats."""
    if unique:
        bar[:, dst] += vals
    else:
        np.add.at(bar, (rows, dst[None, :]), vals)


def _settle(bar: np.ndarray, levels: list[Any], rows: np.ndarray) -> None:
    for src, dst, beta, unique in levels:
        _scatter(bar, rows, dst, beta * bar[:, src], unique)


# ----------------------------------------------------------------------------- scenarios
def reaches_instrument(net: Network, node: str, horizon: int) -> bool:
    """Can a shock here touch a tradable instrument inside the horizon? BFS on cumulative lag."""
    out: dict[str, list[Edge]] = {}
    for e in net.edges:
        out.setdefault(e.src, []).append(e)
    seen, queue = {node: 0}, [(node, 0)]
    while queue:
        cur, spent = queue.pop()
        for e in out.get(cur, ()):
            cost = spent + e.lag
            if cost > horizon or seen.get(e.dst, horizon + 1) <= cost:
                continue
            if net.kinds.get(e.dst) == MT5 and e.dst != node:
                return True
            seen[e.dst] = cost
            queue.append((e.dst, cost))
    return False


def resolve_trigger(net: Network, nodes: list[str], horizon: int) -> tuple[str | None, str]:
    """(the node the shock is applied to, the one the SCENARIO asked for) -- both, always.

    The second is the ladder's head, not the rung that answered: "we shocked the dollar instead of
    the CPI print" is a fact about the run a reader must never have to infer.
    """
    wanted = nodes[0] if nodes else ""
    seen: list[str] = []
    for want in nodes:
        node = net.alias.get(want, (want, 1.0))[0]
        if node in net.index:
            seen.append(node)
            if reaches_instrument(net, node, horizon):
                return node, wanted
    return (seen[0] if seen else None), wanted


def run_scenario(lab: Lab, spec: dict[str, Any], surface: dict[str, Any]) -> dict[str, Any]:
    """One intervention: total path, direct-arc path, residual, bands, cost, actionability."""
    net = lab.net
    trigger, wanted = resolve_trigger(net, list(spec["nodes"]), lab.horizon)
    if trigger is None or not reaches_instrument(net, trigger, lab.horizon):
        return {"status": "UNMEASURED", "chain": spec["chain"], "effects": [],
                "why": (f"no node in {spec['nodes']} both exists in this graph and reaches a "
                        f"tradable instrument within {lab.horizon} bars, so the shock would "
                        "propagate nowhere")}
    shock = float(spec["shock"])
    total, contrib = lab.simulate(trigger, shock, month_end=bool(spec.get("month_end")))
    direct_edges = [e for e in net.edges if e.src == trigger]
    direct, _ = lab.simulate(trigger, shock, edges=direct_edges, participants=False)
    spoken_to = {e.dst for e in direct_edges}
    effects: list[dict[str, Any]] = []
    gaps: list[float] = []
    for j, sym in enumerate(lab.inst):
        if sym == trigger:
            continue
        i = net.index[sym]
        tot_z = total[:, i, :].sum(axis=1)
        res_z = tot_z - direct[:, i, :].sum(axis=1)
        if max(float(np.max(np.abs(tot_z))), float(np.max(np.abs(res_z)))) < 1e-9:
            continue
        stats = bar_stats(sym)
        sigma = stats["sigma_h1"] if stats else None
        cost, cost_basis = cost_fraction(sym, surface)
        mm = float(lab.table.get(sym, {}).get("market_maker", {}).get(
            "value", DEFAULT_PARTICIPANTS["market_maker"]))
        cost = None if cost is None else cost * (1.0 + mm)
        mean_tot, mean_res = float(np.mean(tot_z)), float(np.mean(res_z))
        gaps.append(abs(mean_res))
        resid = None if sigma is None else mean_res * sigma
        effects.append({
            "instrument": sym,
            "expected_move": None if sigma is None else round(mean_tot * sigma, 10),
            "residual": None if resid is None else round(resid, 10),
            "band": None if sigma is None else [
                round(float(np.percentile(tot_z, 5)) * sigma, 10),
                round(float(np.percentile(tot_z, 95)) * sigma, 10)],
            "cost": None if cost is None else round(cost, 10),
            "actionable": None if (resid is None or cost is None) else bool(abs(resid) > cost),
            "expected_move_sigma": round(mean_tot, 6), "residual_sigma": round(mean_res, 6),
            "peak_lag_bars": int(np.argmax(np.abs(np.mean(total[:, i, :], axis=0)))),
            "direction": "same" if mean_tot >= 0 else "opposite",
            "graph_speaks": sym in spoken_to, "cost_basis": cost_basis,
            "participants": {k: round(float(np.mean(v[:, j])), 6) for k, v in contrib.items()
                             if abs(float(np.mean(v[:, j]))) > 1e-9},
        })
    effects.sort(key=lambda r: -abs(float(r["residual_sigma"])))
    spoken = [abs(float(r["residual_sigma"])) for r in effects if r["graph_speaks"]]
    return {"status": "OK", "trigger_node": trigger, "trigger_requested": wanted,
            "shock_sigma": shock, "chain": spec["chain"], "effects": effects,
            "disagreement_with_observational": {
                "mean_abs_sigma": round(float(np.mean(gaps)), 6) if gaps else 0.0,
                "max_abs_sigma": round(float(np.max(gaps)), 6) if gaps else 0.0,
                "n_instruments": len(effects), "n_where_graph_speaks": len(spoken),
                "mean_abs_sigma_where_graph_speaks": (round(float(np.mean(spoken)), 6)
                                                      if spoken else None),
                "n_silent": len(effects) - len(spoken),
                "top": [{"instrument": r["instrument"], "residual_sigma": r["residual_sigma"],
                         "graph_speaks": r["graph_speaks"]} for r in effects[:5]],
                "reads": ("the simulated total minus what the trigger's DIRECT arc alone "
                          "predicts. Near zero the graph was already the whole answer; large, "
                          "and the chain or the participants carry the move. A gap on an "
                          "instrument the graph is SILENT about is a different claim from one "
                          "it disagrees with, so both are counted.")}}


# ---------------------------------------------------------------------------- hypotheses
def registered_families() -> set[str]:
    """Family names this tree actually implements. A hypothesis for anything else is refused."""
    try:
        from mt5desk import families as fam
        from mt5desk import families_orthogonal as fo
    except Exception:
        return set()
    return ({str(k) for k in getattr(fam, "FAMILY_REGISTRY", {})}
            | {str(k) for k in getattr(fo, "ORTHOGONAL_FAMILIES", {})})


def family_for(net: Network, trigger: str, symbol: str) -> tuple[str, str]:
    """(family, the driver symbol it should be run against) for a trigger and a target.

    A trigger that PRICES an instrument -- itself, or through a merged identity -- is a driver
    series the desk already holds, so the hypothesis is `lead_lag` against it. One that does not
    (a central bank, a positioning table, a yield) is a macro state, and the hypothesis is
    `macro_conditional` on that axis. An event node is an `event_reaction`.
    """
    if net.kinds.get(trigger, "") == "event":
        return "event_reaction", ""
    proxy = net.proxy_of(trigger)
    driver = proxy[0] if proxy else ""
    return ("lead_lag", driver) if driver and driver != symbol else (FALLBACK_FAMILY, "")


def family_params(family: str, wanted: dict[str, Any]) -> dict[str, Any]:
    """`wanted`, narrowed to the keys the family's constructor actually accepts.

    `family_call` splats `params` straight into the family as kwargs, so a provenance field left
    in there is a TypeError at backtest time, not a harmless annotation. The trigger node and the
    shock therefore ride on the row's `trigger` block and in `evidence`; what stays in `params` is
    exactly what the family reads -- and for `lead_lag` that INCLUDES the trigger, under the name
    the family knows it by (`driver_symbol`). A signature that cannot be read is passed through
    unchanged rather than emptied: an unreadable rule is not a licence to donate nothing.
    """
    import inspect
    try:
        from mt5desk import families as fam
        from mt5desk import families_orthogonal as fo
        entry: Any = getattr(fo, "ORTHOGONAL_FAMILIES", {}).get(family)
        if entry is None:
            entry = getattr(fam, "FAMILY_REGISTRY", {}).get(family)
            entry = entry.get("func") if isinstance(entry, dict) else entry
        if not callable(entry):
            return dict(wanted)
        names = set(inspect.signature(entry).parameters)
    except Exception:
        return dict(wanted)
    return {k: v for k, v in wanted.items() if k in names}


def hypotheses(net: Network, scenarios: dict[str, Any], families: set[str], limit: int
               ) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """(rows to donate, refusals), ranked by residual over cost across every scenario."""
    from research.proposer_common import candidate
    try:
        from research.universe_policy import may_hypothesise
    except Exception:
        def may_hypothesise(_s: str) -> bool:                             # type: ignore[misc]
            return True
    pool: list[tuple[float, str, dict[str, Any]]] = []
    refused: list[dict[str, Any]] = []
    for name, sc in scenarios.items():
        if sc.get("status") != "OK":
            continue
        trigger = str(sc["trigger_node"])
        for eff in sc["effects"]:
            if not eff.get("actionable"):
                continue
            sym = str(eff["instrument"])
            if not may_hypothesise(sym):
                refused.append({"symbol": sym, "scenario": name, "why": (
                    "the two-lane mandate (2026-09-06): this instrument is traded on news and "
                    "earnings reaction, never hunted for statistical hypotheses")})
                continue
            fam, driver = family_for(net, trigger, sym)
            if fam not in families:
                refused.append({"symbol": sym, "scenario": name, "family": fam,
                                "why": "no such family is registered on this tree"})
                continue
            lag = max(int(eff["peak_lag_bars"]), 1)
            side = 1 if eff["direction"] == "same" else -1
            params = family_params(fam, {
                "driver_symbol": driver, "lag": lag, "direction": eff["direction"],
                "hold_bars": max(lag, 6), "ttl_bars": max(lag, 6) * 2,
                "regime_high": 0.5, "side_in_high": side, "mode": "drift", "side": side})
            trig = {"node": trigger, "lag": lag, "direction": eff["direction"],
                    "shock_sigma": sc["shock_sigma"], "horizon_bars": HORIZON,
                    "driver_symbol": driver}
            row = candidate(
                SEAT, sym, fam, params,
                mechanism=f"world_lab intervention: {trigger} -> {sym}",
                title=f"{name}: {trigger} -> {sym} residual {eff['residual_sigma']:+.3f} sigma",
                evidence={"scenario": name, "chain": sc["chain"], "band": eff["band"],
                          "residual_sigma": eff["residual_sigma"], "cost": eff["cost"],
                          "expected_move_sigma": eff["expected_move_sigma"],
                          "edge_basis": net.basis, "graph_speaks": eff["graph_speaks"],
                          "participants": eff["participants"], "trigger": trig,
                          "authority": "ZERO -- synthetic"})
            row.update({"source": f"{SEAT}:{name}", "kind": "hypothesis", "timeframe": "H1",
                        "symbols": [sym], "trigger": trig,
                        "why": (f"{sc['chain']}. do({trigger} = {sc['shock_sigma']:+.2f} sigma) "
                                f"leaves {sym} a RESIDUAL of {eff['residual_sigma']:+.4f} sigma "
                                f"-- the part the trigger's direct arc does not explain -- "
                                f"against a {eff['cost']:.6f} round trip. SYNTHETIC: a question "
                                f"for the gauntlet on real history, never a measurement. Edge "
                                f"basis {net.basis}.")})
            score = abs(float(eff["residual"] or 0.0)) / max(float(eff["cost"] or 1e-9), 1e-9)
            pool.append((score, f"{name}:{sym}", row))
    pool.sort(key=lambda t: (-t[0], t[1]))
    # TRIAL COUNT IS A SHARED COST (universe_policy's own argument). Two scenarios whose ladders
    # land on one node produce one cell twice -- `cpi_surprise` and `central_bank_hawkish_surprise`
    # both substitute the dollar leg here -- charging the error budget twice for one question.
    kept: list[dict[str, Any]] = []
    seen: set[tuple[Any, ...]] = set()
    for _score, key, row in pool:
        t = row["trigger"]
        ident = (row["symbol"], row["family"], t["node"], t["lag"], t["direction"])
        if ident in seen:
            refused.append({"symbol": row["symbol"], "scenario": key.split(":")[0],
                            "why": "an identical cell was already donated by a scenario whose "
                                   "ladder landed on the same node; one question, one charge "
                                   "against the shared trial budget"})
            continue
        seen.add(ident)
        kept.append(row)
        if len(kept) >= max(limit, 0):
            break
    return kept, refused


# --------------------------------------------------------------------------------- build
def build(*, seed: int = SEED, draws: int = DRAWS, horizon: int = HORIZON,
          limit: int = MAX_DONATIONS, only: str | None = None) -> dict[str, Any]:
    head = {"at": datetime.now(tz=UTC).isoformat(timespec="seconds"),
            "authority": "ZERO -- synthetic; the gauntlet judges on real history",
            "rule": ("do(shock) on the observational graph, propagate along its arcs at their own "
                     "lags, apply the participants' response operators, and donate the "
                     "instruments whose RESIDUAL -- total minus the direct arc -- clears the "
                     "round trip. Nothing simulated certifies, sizes or promotes.")}
    # THE PATHS ARE PASSED, NOT DEFAULTED. `load_network`'s defaults bind at import, so a caller
    # pointing the lab at another tree -- or a test at a fixture -- would have been silently
    # answered by the box's own graph. Four tests passed against the real artifact before this.
    net = load_network(GRAPH, CAUSAL_LAB)
    if net is None:
        return {**head, "status": "UNMEASURED", "n_nodes": 0, "n_edges": 0, "scenarios": {},
                "donated": 0, "unmeasured": [{"what": "the whole lab", "why": (
                    f"no readable causal graph at {GRAPH.name}; there is nothing to intervene on "
                    "and a simulator with no arcs would invent its own answer")}]}
    table, p_basis = participant_table(net, _read_json(ECOLOGY))
    lab = Lab(net, table, draws=draws, horizon=horizon, seed=seed)
    unmeasured: list[dict[str, Any]] = []
    if "PRIOR" in p_basis.upper():
        unmeasured.append({"what": "participant coefficients", "why": p_basis})
    unmeasured += [{"what": "edge basis", "why": n} for n in net.notes]
    far = [e for e in net.edges if e.lag > lab.horizon]
    if far:
        unmeasured.append({"what": "arcs beyond the horizon", "n": len(far),
                           "why": f"{len(far)} of {len(net.edges)} arcs carry a lag longer than "
                                  f"the {lab.horizon}-bar horizon and cannot fire inside it"})
    surface = _read_json(COST_SURFACE)
    scenarios: dict[str, Any] = {}
    for name, spec in SCENARIOS.items():
        if only and name != only:
            continue
        scenarios[name] = run_scenario(lab, spec, surface)
        if scenarios[name]["status"] != "OK":
            unmeasured.append({"what": f"scenario {name}", "why": scenarios[name]["why"]})
    families = registered_families()
    if not families:
        unmeasured.append({"what": "family registry", "why": (
            "mt5desk.families is unimportable here, so nothing was donated: a family that cannot "
            "be verified is not a family")})
    rows, refused = hypotheses(net, scenarios, families, limit)
    # HOW FAR SHORT A RUN THAT DONATED NOTHING FELL. Zero hypotheses has two causes -- nothing
    # moved, or what moved could not pay the round trip -- one number and two different facts.
    ratios = [(abs(float(e["residual"])) / float(e["cost"]), n, str(e["instrument"]))
              for n, sc in scenarios.items() for e in sc.get("effects") or []
              if e.get("residual") is not None and e.get("cost")]
    best = max(ratios) if ratios else None
    no_bars = [s for s in lab.inst if bar_stats(s) is None]
    if no_bars:
        unmeasured.append({"what": "price scale", "n": len(no_bars), "symbols": no_bars[:12],
                           "why": "no H1 parquet on this box, so the move, the band and the cost "
                                  "are null and the instrument can never read actionable"})
    return {**head, "status": "OK", "n_nodes": len(net.nodes), "n_edges": len(net.edges),
            "edge_basis": net.basis, "stability_scaled_rows": net.scaled_rows,
            "identities_merged": len(net.alias), "seed": seed, "draws": draws,
            "horizon_bars": lab.horizon,
            "participants": {"basis": p_basis, "operators": sorted(DEFAULT_PARTICIPANTS)},
            "scenarios": scenarios, "hypotheses": rows, "donated": 0,
            "best_residual_over_cost": (None if best is None else
                                        {"ratio": round(best[0], 4), "scenario": best[1],
                                         "instrument": best[2],
                                         "reads": "above 1.0 the residual pays the round trip"}),
            "refused": refused[:20], "n_refused": len(refused), "unmeasured": unmeasured}


def _write(path: Path, doc: dict[str, Any]) -> None:
    """Atomic, and it survives the read-only destination that broke the frontier fix on Windows."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(doc, indent=1, default=str), "utf-8")
    try:
        os.replace(tmp, path)
    except PermissionError:
        os.chmod(path, 0o644)
        os.replace(tmp, path)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=(__doc__ or "").splitlines()[0])
    ap.add_argument("--dry-run", action="store_true", help="simulate and print; write nothing")
    ap.add_argument("--seed", type=int, default=SEED)
    ap.add_argument("--max-donations", type=int, default=MAX_DONATIONS)
    ap.add_argument("--draws", type=int, default=DRAWS)
    ap.add_argument("--horizon", type=int, default=HORIZON)
    ap.add_argument("--scenario", default=None, help="run one scenario by name")
    a = ap.parse_args(argv)
    doc = build(seed=a.seed, draws=a.draws, horizon=a.horizon, limit=a.max_donations,
                only=a.scenario)
    rows = doc.get("hypotheses") or []
    if not a.dry_run and rows:
        from research.proposer_common import donate, donation_counts
        donate(SEAT, [dict(r) for r in rows], tests_run=len(doc.get("scenarios") or {}))
        doc["donation"] = donation_counts()
        doc["donated"] = int(doc["donation"].get("donated") or 0)
    print(f"WORLD LAB  {doc['status']}  nodes={doc.get('n_nodes')} arcs={doc.get('n_edges')} "
          f"merged={doc.get('identities_merged')} basis={doc.get('edge_basis')} seed={a.seed}")
    for name, sc in list((doc.get("scenarios") or {}).items())[:6]:
        if sc.get("status") != "OK":
            print(f"  {name:<30} UNMEASURED -- {str(sc.get('why'))[:56]}")
            continue
        d, top = sc["disagreement_with_observational"], (sc["effects"] or [{}])[0]
        print(f"  {name:<30} do({sc['trigger_node']}={sc['shock_sigma']:+.1f}s) "
              f"disagree={d['mean_abs_sigma']:.4f}s over {d['n_instruments']} "
              f"top={top.get('instrument', '-')}/{top.get('residual_sigma', 0):+.3f}s "
              f"actionable={sum(1 for e in sc['effects'] if e.get('actionable'))}")
    print(f"  hypotheses={len(rows)} donated={doc.get('donated')} refused={doc.get('n_refused')} "
          f"best_residual/cost={(doc.get('best_residual_over_cost') or {}).get('ratio')} "
          f"unmeasured={len(doc.get('unmeasured') or [])}  {doc['authority']}")
    if a.dry_run:
        print("  --dry-run: nothing written, nothing donated")
        return 0
    _write(OUT, doc)
    print(f"-> {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
