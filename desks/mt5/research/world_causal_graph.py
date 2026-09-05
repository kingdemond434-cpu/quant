"""The hourly organ that grows the world causal graph and hands the state builder its hints.

WHAT IT DOES, once an hour on the discovery pass. It seeds `libs.research.causal_graph`'s prior
chains (so every chain the principal named exists before any data proves it), collects the
CANDIDATE edges this box can actually measure -- the seeded chains whose ends resolve to a
series here, the pairs `cross_asset_graph` already screened, the instrument pairs and the
positioning claims the deep-forest miner extracted -- and measures as many as the budget allows,
OLDEST-MEASURED FIRST so an edge nobody has looked at is looked at before one measured an hour
ago is measured again. Every (pair, lag) cell it tests is charged to the graph's multiplicity
ledger before the measurement, and the ledger never shrinks. The merged graph is written to
`data/world_causal_graph.json`; the report, with the admitted edges, the top second- and
third-order paths into each MT5 instrument and the CONDITIONING HINTS, to
`reports/WORLD_CAUSAL_GRAPH.json`.

WHAT A SERIES IS HERE. An MT5 instrument is its H1 log returns from the desk's parquet lake. A
positioning node (`positioning:COT_gold`) is the weekly net-speculative z-score from the CFTC
tables, indexed by the time each report became AVAILABLE (report date + the feature store's
`COT_RELEASE_LAG`), paired with the instrument's return over the following week: the same
point-in-time convention `feature_store.cot_z` uses. A world node that has a structural proxy
(`commodity:gold -> XAUUSD`) is measured through the proxy's series, sign-flipped when the proxy
is the inverse quote, and the edge's evidence names what it was measured through. A node with
no series on this box stays PLAUSIBLE_UNMEASURED, which the report shows -- it is a data
acquisition target, not a gap to paper over.

THE DEEP-FOREST CLAIMS ARE READ DEFENSIVELY. Their schema is being finalised by the miner's
owner; this reads only `instruments.analogues` (Fusion symbols), `mechanism_class`, `channel`,
`horizon`, `claim_hash`, `evidence_grade` and `available_time`, skips any line that is not a
JSON object, and counts what it could not map by mechanism class so the report says what the
miner produced that the graph cannot yet place.

NOTHING HERE DECIDES ANYTHING. The organ writes hints; `state_vector_build` may read them as
information; the allocator still owns every decision. No network.

WHAT AN HOUR OF THIS IS WORTH. The report carries `discovered` -- one of `hourly_discovery`'s
YIELD_KEYS -- and it counts only what is NEW: edges admitted that were not admitted in the
previous report, plus second- and third-order chains that were not there before. Re-measuring
the same sixty priors is not a yield, and a pass that learned nothing reads as zero.

    python3 research/world_causal_graph.py [--budget-s 600] [--symbol XAUUSD ...]
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

_DESK = Path(__file__).resolve().parents[1]
_ROOT = _DESK.parent.parent
for _p in (str(_DESK), str(_DESK / "research"), str(_ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from libs.data.feature_store import COT_RELEASE_LAG, COT_SOURCES, cot_legs  # noqa: E402
from libs.research import causal_graph as cg  # noqa: E402
from libs.research.information_decay import REGISTRY, decay  # noqa: E402

SOURCE = "world_causal_graph"
UNI = _DESK / "data" / "universe"
UNIVERSE_JSON = UNI / "universe.json"
GRAPH = _DESK / "data" / "world_causal_graph.json"
REPORT = _DESK / "reports" / "WORLD_CAUSAL_GRAPH.json"
CLAIMS = _DESK / "data" / "deep_forest_claims.jsonl"
CROSS = _DESK / "reports" / "CROSS_ASSET_GRAPH.json"

DEFAULT_BUDGET_S = 600.0
#: Candidates measured per pass at most, whatever the budget: the pass is hourly and a cell
#: re-measured every hour buys nothing the ledger does not already charge.
MAX_PER_RUN = 60
#: Aligned H1 bars a pair needs. The estimator's own floor; repeated here for the skip reason.
MIN_BARS = cg.MIN_N
#: COT reports a positioning edge needs -- a year of weeks, the feature store's z window.
MIN_REPORTS = 52
#: Plausibility given to candidates from each external source. Below any seeded prior on
#: purpose: a screened pair is a statistical finding, a hand-written chain is a mechanism.
PLAUSIBILITY_CROSS_ASSET = {"CAUSAL_ROLE": 0.5, "STATISTICAL": 0.2}
PLAUSIBILITY_CLAIM = 0.3
#: Horizon words in the claims -> the clock the edge is measured on.
HORIZON_CLOCK: tuple[tuple[tuple[str, ...], str], ...] = (
    (("week", "weekly", "周", "週", "month", "monthly", "月", "quarter", "季"), "W1"),
    (("day", "daily", "days", "日线", "日線", "overnight", "隔夜", "swing", "波段"), "D1"),
)
#: mechanism_class of a single-instrument claim -> the world node kind that carries it.
CLAIM_CLASS_NODE = {"positioning": "positioning", "policy": "central_bank"}
#: Quote currency -> the central bank node that sets it, for `policy` claims.
CB_OF_CCY = {"USD": "cb:FED", "EUR": "cb:ECB", "JPY": "cb:BOJ", "GBP": "cb:BOE",
             "AUD": "cb:RBA", "CAD": "cb:BOC", "CNH": "cb:PBOC"}


# ------------------------------------------------------------------------------- series
class Series:
    """Per-run cache of the series a node resolves to, so a node in ten candidates is read once."""

    def __init__(self, universe: dict[str, cg.Node]) -> None:
        self.universe = universe
        self._h1: dict[str, pd.Series | None] = {}
        self._cot: dict[str, pd.Series | None] = {}
        self._close: dict[str, pd.Series | None] = {}

    def close(self, sym: str) -> pd.Series | None:
        if sym not in self._close:
            self._close[sym] = _h1_close(sym)
        return self._close[sym]

    def h1(self, sym: str) -> pd.Series | None:
        if sym not in self._h1:
            c = self.close(sym)
            self._h1[sym] = (np.log(c).diff().dropna() if c is not None and c.size > 1
                             else None)
        return self._h1[sym]

    def cot(self, stem: str) -> pd.Series | None:
        if stem not in self._cot:
            self._cot[stem] = _cot_z(stem)
        return self._cot[stem]

    def resolve(self, node_id: str, graph: cg.CausalGraph
                ) -> tuple[str, str, float] | None:
        """(kind, symbol-or-stem, sign) for a node this box can measure, else None.

        kind is "h1" (an instrument's returns, possibly through a proxy) or "cot" (a weekly
        positioning table). The sign is -1 when the proxy is the inverse quote.
        """
        node = graph.nodes.get(node_id)
        if node is None:
            return None
        if node.kind == cg.MT5:
            return ("h1", node_id, 1.0) if self.h1(node_id) is not None else None
        if node.kind == "positioning" and node_id.startswith("positioning:COT_"):
            stem = node_id[len("positioning:COT_"):]
            return ("cot", stem, 1.0) if self.cot(stem) is not None else None
        for e in graph.edges_from(node_id):
            if e.status == cg.STRUCTURAL and e.lag == 0 and e.dst in self.universe \
                    and self.h1(e.dst) is not None:
                return ("h1", e.dst, -1.0 if e.direction == "opposite" else 1.0)
        return None


def _h1_close(sym: str) -> pd.Series | None:
    path = UNI / f"{sym}_H1.parquet"
    if not path.exists():
        return None
    try:
        df = pd.read_parquet(path, columns=["close"])
    except (OSError, ValueError, ImportError, KeyError):
        return None
    if df.empty:
        return None
    idx = pd.DatetimeIndex(pd.to_datetime(df.index, utc=True, errors="coerce"))
    s = pd.Series(df["close"].to_numpy(dtype=float), index=idx)
    s = s[~s.index.isna()]
    s = s[~s.index.duplicated(keep="last")].sort_index()
    s = s[np.isfinite(s.to_numpy()) & (s.to_numpy() > 0)]
    return s if s.size else None


def _cot_z(stem: str, w: int = 52) -> pd.Series | None:
    """Weekly net-speculative z over `w` reports, indexed by the UTC time each report became
    available -- the feature store's convention (report_date + COT_RELEASE_LAG unless the row
    carries its own available_time/published_at)."""
    found = None
    for d, long_col, short_col in COT_SOURCES:
        p = d / f"{stem}.parquet"
        if p.exists():
            found = (p, long_col, short_col)
            break
    if found is None:
        return None
    p, long_col, short_col = found
    try:
        raw = pd.read_parquet(p)
    except (OSError, ValueError, ImportError):
        return None
    if "report_date" not in raw.columns or long_col not in raw.columns \
            or short_col not in raw.columns:
        return None
    col = "market" if "market" in raw.columns else "contract_market_name"
    if col in raw.columns:
        names = raw[col].astype(str)
        raw = raw[~names.str.contains("XRATE|DIVIDEND|TOTAL RETURN|ADJUSTED", case=False,
                                      regex=True)]
        cons = raw[raw[col].astype(str).str.contains("Consolidated", case=False, regex=False)]
        raw = cons if len(cons) else raw
    dates = pd.to_datetime(raw["report_date"], utc=True, errors="coerce")
    avail = dates + COT_RELEASE_LAG
    for c in ("available_time", "published_at"):
        if c in raw.columns:
            own = pd.to_datetime(raw[c], utc=True, errors="coerce")
            avail = own.where(own.notna(), avail)
            break
    net = pd.Series(raw[long_col].to_numpy(dtype=float) - raw[short_col].to_numpy(dtype=float),
                    index=pd.DatetimeIndex(avail))
    net = net[~net.index.isna()].sort_index()
    net = net[~net.index.duplicated(keep="last")]
    if net.size < MIN_REPORTS:
        return None
    r = net.rolling(w, min_periods=w)
    with np.errstate(all="ignore"):
        z = (net - r.mean()) / r.std()
    z = z.replace([np.inf, -np.inf], np.nan).dropna()
    return z if z.size else None


def _aligned_h1(a: pd.Series, b: pd.Series, sa: float, sb: float, clock: str
                ) -> tuple[np.ndarray, np.ndarray]:
    j = pd.concat([a.rename("x") * sa, b.rename("y") * sb], axis=1, join="inner").dropna()
    if clock == "D1" and not j.empty:
        j = j.groupby(j.index.floor("D")).sum()
    elif clock == "W1" and not j.empty:
        day = j.index.floor("D")
        j = j.groupby(day - pd.to_timedelta(day.dayofweek, unit="D")).sum()
    return j["x"].to_numpy(dtype=float), j["y"].to_numpy(dtype=float)


def _weekly_cot_pairs(z: pd.Series, close: pd.Series, sign: float
                      ) -> tuple[np.ndarray, np.ndarray]:
    """x_i = the positioning z knowable at availability time a_i; y_i = the instrument's log
    return over the week ENDING at a_i, so X_i -> Y_{i+1} is the week after the report."""
    pos = close.index.searchsorted(z.index, side="right") - 1
    ok = pos >= 0
    logp = np.full(z.size, np.nan)
    logp[ok] = np.log(close.to_numpy(dtype=float)[pos[ok]])
    y = np.diff(logp) * sign
    x = z.to_numpy(dtype=float)[1:]
    fin = np.isfinite(x) & np.isfinite(y)
    return x[fin], y[fin]


# --------------------------------------------------------------------------- candidates
def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    try:
        text = path.read_text("utf-8")
    except OSError:
        return rows
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            d = json.loads(line)
        except ValueError:
            continue
        if isinstance(d, dict):
            rows.append(d)
    return rows


def _horizon_clock(horizon: Any) -> str:
    words = " ".join(str(h) for h in (horizon if isinstance(horizon, list) else [horizon]))
    low = words.lower()
    for keys, clock in HORIZON_CLOCK:
        if any(k in low for k in keys):
            return clock
    return "H1"


def _decay_for(clock: str) -> str:
    return {"H1": "bar_H1", "D1": "bar_D1", "W1": "bar_W1"}.get(clock, "bar_H1")


def claim_candidates(rows: list[dict[str, Any]], universe: set[str],
                     graph: cg.CausalGraph) -> tuple[list[cg.Edge], dict[str, int]]:
    """Candidate edges from the deep-forest claims. Two analogues -> both orderings of the pair
    (the row does not say which leads); a single analogue with a `positioning` class -> the
    CFTC leg(s) of that instrument; `policy` -> the central bank of its quote currency. The
    rest is counted by class so the report says what could not be placed."""
    out: list[cg.Edge] = []
    unmapped: dict[str, int] = {}
    seen: set[tuple[str, str, int]] = set()
    for r in rows:
        inst = r.get("instruments") if isinstance(r.get("instruments"), dict) else {}
        syms = [str(s) for s in (inst.get("analogues") or []) if str(s) in universe]
        cls = str(r.get("mechanism_class") or "other")
        clock = _horizon_clock(r.get("horizon"))
        ev = {"prior_source": "deep_forest_claims", "prior_claim_hash": r.get("claim_hash"),
              "prior_mechanism_class": cls, "prior_channel": r.get("channel"),
              "prior_evidence_grade": r.get("evidence_grade"),
              "prior_available_time": r.get("available_time")}
        plaus = PLAUSIBILITY_CLAIM + (0.1 if str(r.get("evidence_grade") or "").upper()
                                      in ("A", "HIGH") else 0.0)
        if len(syms) >= 2:
            for a in syms[:3]:
                for b in syms[:3]:
                    if a != b and (a, b, 1) not in seen:
                        seen.add((a, b, 1))
                        out.append(cg.Edge(src=a, dst=b, lag=1, plausibility=plaus,
                                           decay_cls=_decay_for(clock), clock=clock,
                                           evidence=dict(ev)))
            continue
        if len(syms) == 1 and cls == "positioning":
            for stem, _sign in cot_legs(syms[0]):
                src = f"positioning:COT_{stem}"
                if src in graph.nodes and (src, syms[0], 1) not in seen:
                    seen.add((src, syms[0], 1))
                    out.append(cg.Edge(src=src, dst=syms[0], lag=1, plausibility=plaus,
                                       decay_cls="cot", clock="W1", evidence=dict(ev)))
            continue
        if len(syms) == 1 and cls == "policy":
            sym = syms[0]
            ccys = [sym[:3], sym[3:]] if len(sym) == 6 else [sym]
            for c in ccys:
                src = CB_OF_CCY.get(c.upper())
                if src and src in graph.nodes and (src, sym, 1) not in seen:
                    seen.add((src, sym, 1))
                    out.append(cg.Edge(src=src, dst=sym, lag=1, plausibility=plaus,
                                       decay_cls="cb_decision", clock=clock,
                                       evidence=dict(ev)))
            continue
        unmapped[cls] = unmapped.get(cls, 0) + 1
    return out, unmapped


def cross_asset_candidates(doc: dict[str, Any], universe: set[str]) -> list[cg.Edge]:
    """The pairs `cross_asset_graph` screened, as candidates carrying its verdict as evidence."""
    out: list[cg.Edge] = []
    for e in doc.get("edges") or []:
        if not isinstance(e, dict):
            continue
        d, t = str(e.get("driver") or ""), str(e.get("target") or "")
        if d not in universe or t not in universe or d == t:
            continue
        plaus = PLAUSIBILITY_CROSS_ASSET.get(str(e.get("plausibility") or ""), 0.2)
        out.append(cg.Edge(src=d, dst=t, lag=int(e.get("lag") or 1), plausibility=plaus,
                           decay_cls="bar_H1", clock="H1",
                           evidence={"prior_source": "cross_asset_graph",
                                     "prior_lead_lag": {k: e.get(k) for k in
                                                        ("verdict", "t", "lag", "role",
                                                         "direction", "stability")}}))
    return out


def _measured_at(graph: cg.CausalGraph, e: cg.Edge) -> str:
    have = graph.measured_edge(e.src, e.dst)
    return have.measured_at if have is not None else ""


def _scope_names(node_id: str, graph: cg.CausalGraph) -> set[str]:
    """The names a node answers to under `--symbol`: its own id and every instrument that PRICES
    it. `--symbol XAUUSD` means the gold chain, so it must reach `commodity:gold` -- matching
    only the endpoints that happen to be spelled as Fusion symbols would scope out every edge
    the graph exists to measure."""
    names = {node_id.upper()}
    names.update(e.dst.upper() for e in graph.edges_from(node_id)
                 if e.status == cg.STRUCTURAL and e.lag == 0)
    return names


def plan(graph: cg.CausalGraph, candidates: list[cg.Edge], series: Series,
         symbols: set[str] | None) -> tuple[list[tuple[cg.Edge, tuple[str, str, float],
                                                        tuple[str, str, float]]], dict[str, str]]:
    """Measurable candidates in run order (never measured first, then oldest measured, then
    the more plausible), and the reason each unmeasurable one was skipped."""
    todo = []
    skipped: dict[str, str] = {}
    for e in candidates:
        key = f"{e.src}->{e.dst}@{e.lag}"
        if symbols and not (_scope_names(e.src, graph) | _scope_names(e.dst, graph)) & symbols:
            skipped[key] = "outside --symbol scope"
            continue
        a = series.resolve(e.src, graph)
        b = series.resolve(e.dst, graph)
        if a is None or b is None:
            missing = e.src if a is None else e.dst
            skipped[key] = f"no series on this box for {missing}"
            continue
        if b[0] == "cot":
            skipped[key] = "positioning is a source here, not a target"
            continue
        todo.append((e, a, b))
    todo.sort(key=lambda t: (_measured_at(graph, t[0]) != "", _measured_at(graph, t[0]),
                             -t[0].plausibility, t[0].src, t[0].dst))
    return todo, skipped


def lags_for(e: cg.Edge, a: tuple[str, str, float]) -> list[int]:
    """The cells a candidate will be charged: one weekly lag for positioning, 1..MAX_LAG bars
    of the edge's clock otherwise."""
    return [1] if a[0] == "cot" else list(range(1, cg.MAX_LAG + 1))


def measure(graph: cg.CausalGraph, e: cg.Edge, a: tuple[str, str, float],
            b: tuple[str, str, float], series: Series, *, n_tests: int | None = None
            ) -> cg.Edge | str:
    """Align and measure one candidate. Returns the measured Edge or a skip reason.

    `n_tests` is the ledger the edge is judged against. The pass charges EVERY planned cell
    before measuring any, so every edge in the pass faces the same bar; a caller measuring one
    edge on its own passes nothing and the cells are charged here.
    """
    via = [f"{a[1]}{'(-)' if a[2] < 0 else ''}", f"{b[1]}{'(-)' if b[2] < 0 else ''}"]
    ev = dict(e.evidence)
    ev["measured_via"] = via
    lags = lags_for(e, a)
    bar = graph.charge(e.src, e.dst, lags) if n_tests is None else max(int(n_tests), 1)
    if a[0] == "cot":
        z = series.cot(a[1])
        close = series.close(b[1])
        if z is None or close is None:
            return "positioning series vanished between plan and measure"
        x, y = _weekly_cot_pairs(z, close, b[2])
        if x.size < MIN_REPORTS:
            return f"{x.size} weekly pairs below MIN_REPORTS={MIN_REPORTS}"
        return cg.measure_edge(x, y, src=e.src, dst=e.dst, clock="W1", decay_cls="cot",
                               n_tests=bar, lags=lags, plausibility=e.plausibility,
                               min_n=MIN_REPORTS, evidence=ev)
    xa, yb = series.h1(a[1]), series.h1(b[1])
    if xa is None or yb is None:
        return "bar series vanished between plan and measure"
    clock = e.clock or "H1"
    x, y = _aligned_h1(xa, yb, a[2], b[2], clock)
    floor = MIN_BARS if clock == "H1" else MIN_REPORTS
    if x.size < floor:
        return f"{x.size} aligned {clock} bars below {floor}"
    return cg.measure_edge(x, y, src=e.src, dst=e.dst, clock=clock,
                           decay_cls=e.decay_cls or _decay_for(clock), n_tests=bar,
                           lags=lags, plausibility=e.plausibility, min_n=floor, evidence=ev)


# --------------------------------------------------------------------------------- run
def _read_json(path: Path) -> dict[str, Any]:
    try:
        d = json.loads(path.read_text("utf-8"))
        return d if isinstance(d, dict) else {}
    except (OSError, ValueError):
        return {}


def _rel(path: Path) -> str:
    """The path as the desk names it, or absolute when it lives elsewhere (tests)."""
    try:
        return str(path.relative_to(_DESK))
    except ValueError:
        return str(path)


def conditioning_hints(graph: cg.CausalGraph) -> dict[str, list[dict[str, Any]]]:
    """Per MT5 instrument: every ADMITTED upstream node with its lag, clock, decay class and
    the weight that class carries at one cadence of age -- the row `state_vector_build` reads.
    Direct edges first, then chains, strongest first within an order."""
    out: dict[str, list[dict[str, Any]]] = {}
    for node in graph.instrument_nodes():
        rows = []
        for p in graph.upstream(node.id, max_order=3, admitted_only=True):
            cls = str(p.get("decay_cls") or "")
            reg = REGISTRY.get(cls)
            rows.append({
                "src": p["src"], "nodes": p["nodes"], "order": p["order"],
                "lag": p["lag_total"], "lags": p["lags"], "clock": p["clock"],
                "direction": "same" if float(p["strength"]) >= 0 else "opposite",
                "strength": p["strength"], "decay_cls": cls,
                "half_life_s": reg.half_life_s if reg else None,
                "cadence_s": reg.cadence_s if reg else None,
                "weight_at_one_cadence": (round(decay(cls, reg.cadence_s), 4)
                                          if reg else None),
                "min_plausibility": p["min_plausibility"],
            })
        if rows:
            out[node.id] = rows
    return out


def top_paths(graph: cg.CausalGraph, per_instrument: int = 8
              ) -> dict[str, list[dict[str, Any]]]:
    """Second- and third-order chains into each instrument, measured chains first."""
    out: dict[str, list[dict[str, Any]]] = {}
    for node in graph.instrument_nodes():
        rows = [p for p in graph.upstream(node.id, max_order=3, admitted_only=False)
                if p["order"] >= 2]
        rows.sort(key=lambda p: (not p["admitted"], not p["measured"], p["order"],
                                 -abs(float(p["strength"])), -float(p["min_plausibility"])))
        if rows:
            out[node.id] = rows[:per_instrument]
    return out


def _path_keys(hints: dict[str, list[dict[str, Any]]]) -> set[str]:
    return {f"{dst}<-{'<-'.join(r['nodes'])}@{r['lags']}" for dst, rows in hints.items()
            for r in rows if int(r.get("order") or 0) >= 2}


def run(symbols: list[str] | None = None, budget_s: float = DEFAULT_BUDGET_S) -> dict[str, Any]:
    started = time.monotonic()
    now = datetime.now(tz=UTC)
    universe = cg.instrument_nodes(UNIVERSE_JSON)
    graph = cg.CausalGraph(instrument_ids=universe or None)
    if GRAPH.exists():
        try:
            graph.merge(cg.CausalGraph.load(GRAPH, instrument_ids=universe or None))
        except (OSError, ValueError, KeyError) as exc:
            graph.seed_notes.append(f"previous graph unreadable, starting from the priors: "
                                    f"{type(exc).__name__}: {exc}")
    cg.seed_priors(graph, universe)

    series = Series(universe)
    universe_ids = set(universe)
    claim_rows = _read_jsonl(CLAIMS)
    claim_edges, unmapped = claim_candidates(claim_rows, universe_ids, graph)
    cross_edges = cross_asset_candidates(_read_json(CROSS), universe_ids)
    # A candidate is a PAIR: the lag on it is a hint and the measurement lands at the lag the
    # data chooses, so two rows for one pair would be the same hypothesis measured twice.
    seeded = [e for e in graph.edges.values() if e.status != cg.STRUCTURAL]
    candidates: list[cg.Edge] = []
    seen: set[tuple[str, str]] = set()
    for e in [*seeded, *cross_edges, *claim_edges]:
        if (e.src, e.dst) in seen:
            continue
        seen.add((e.src, e.dst))
        candidates.append(e)
    # every candidate is in the graph, measured or not, so the report shows what is waiting
    for e in [*cross_edges, *claim_edges]:
        for nid in (e.src, e.dst):
            if nid not in graph.nodes and nid in universe:
                graph.add_node(universe[nid])
        if e.src in graph.nodes and e.dst in graph.nodes:
            graph.add_edge(e)

    scope = {s.upper() for s in symbols} if symbols else None
    todo, skipped = plan(graph, candidates, series, scope)
    have_data = any(UNI.glob("*_H1.parquet")) or any(
        (d / f"{stem}.parquet").exists() for d, _, _ in COT_SOURCES
        for stem in ("gold", "eur", "jpy", "aud", "gbp", "cad", "chf", "nzd", "dxy"))

    previous = _read_json(REPORT)
    prev_keys = set(previous.get("admitted_path_keys") or [])
    prev_admitted = {_edge_key(r) for r in (previous.get("admitted_edges") or [])
                     if isinstance(r, dict)}
    # CHARGE FIRST, MEASURE SECOND. Every cell this pass intends to test is on the ledger
    # before the first estimate, so the edge measured first faces the same bar as the last --
    # and a pass killed at its budget has still paid for what it planned.
    batch = todo[:MAX_PER_RUN]
    for e, a, _b in batch:
        graph.charge(e.src, e.dst, lags_for(e, a))
    bar = graph.multiplicity
    measured: list[cg.Edge] = []
    for e, a, b in batch:
        if time.monotonic() - started > budget_s:
            skipped[f"{e.src}->{e.dst}@{e.lag}"] = "budget exhausted"
            continue
        got = measure(graph, e, a, b, series, n_tests=bar)
        if isinstance(got, str):
            skipped[f"{e.src}->{e.dst}@{e.lag}"] = got
            continue
        graph.add_edge(got)
        measured.append(got)

    hints = conditioning_hints(graph)
    keys = _path_keys(hints)
    chains = graph.chain_status()
    counts = graph.counts()
    status = "OK" if have_data and todo else "UNMEASURED"
    why = ""
    if not have_data:
        why = (f"no *_H1.parquet under {_rel(UNI)} and no COT tables under "
               f"{', '.join(d.name for d, _, _ in COT_SOURCES)} -- the seeded graph is written "
               "so the chains are visible; nothing was measured")
    elif not todo:
        why = ("no candidate edge has a series at both ends within the requested scope"
               if scope else
               "bars exist but no candidate edge has a series at both ends on this box")

    admitted = [e for e in graph.edges.values() if e.status == cg.ADMITTED]
    not_adm = [e for e in graph.edges.values() if e.status == cg.RECORDED_NOT_ADMITTED]
    new_edges = {f"{e.src}->{e.dst}@{e.lag}" for e in admitted} - prev_admitted
    report: dict[str, Any] = {
        "generated_at": now.isoformat(), "source": SOURCE, "status": status, "why": why,
        "budget_s": budget_s, "spent_s": round(time.monotonic() - started, 1),
        "counts": counts,
        "chains_seeded": sum(1 for c in chains.values() if c["seeded"]),
        "chains_measured": sum(1 for c in chains.values() if c["measured"]),
        "chains_admitted": sum(1 for c in chains.values() if c["admitted"]),
        "chains": chains,
        "candidate_edges": len(candidates), "measurable": len(todo),
        "edges_measured": len(measured),
        "edges_admitted": sum(1 for e in measured if e.status == cg.ADMITTED),
        "edges_admitted_new": len(new_edges),
        "paths_new": len(keys - prev_keys),
        # THE HOURLY PASS'S YIELD COUNTER for this organ (`hourly_discovery.YIELD_KEYS` reads
        # `discovered` straight off this dict): admitted edges and admitted chains that are NEW
        # since the last report. The candidate count is deliberately NOT the yield -- it is the
        # same prior table every hour (51 candidate edges on this box), and an organ that
        # re-measures them and learns nothing must read as zero rather than as fifty-one.
        "discovered": len(new_edges) + len(keys - prev_keys),
        "admitted_path_keys": sorted(keys),
        "admitted_edges": [_edge_row(e) for e in sorted(admitted, key=lambda e: -abs(e.strength))],
        "recorded_not_admitted": [_edge_row(e) for e in
                                  sorted(not_adm, key=lambda e: -abs(e.strength))[:80]],
        "paths": top_paths(graph),
        "conditioning_hints": hints,
        "claims": {"rows_read": len(claim_rows), "edges_from_claims": len(claim_edges),
                   "unmapped_by_class": unmapped,
                   "fields_consumed": ["instruments.analogues", "mechanism_class", "channel",
                                       "horizon", "claim_hash", "evidence_grade",
                                       "available_time"]},
        "cross_asset_graph_edges": len(cross_edges),
        "skipped": skipped, "seed_notes": graph.seed_notes,
        "consumer": "research/state_vector_build.py reads conditioning_hints; the allocator "
                    "reads the state vector; nothing here sizes or trades",
    }
    graph.save(GRAPH)
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text(json.dumps(report, indent=1, default=str), "utf-8")
    return report


def _edge_key(row: dict[str, Any]) -> str:
    """The identity of an admitted edge across passes, as the previous report wrote it."""
    return f"{row.get('src')}->{row.get('dst')}@{row.get('lag')}"


def _edge_row(e: cg.Edge) -> dict[str, Any]:
    inc = e.evidence.get("incremental") or {}
    xc = (e.evidence.get("xcorr") or {}).get("best") or {}
    return {"src": e.src, "dst": e.dst, "lag": e.lag, "clock": e.clock,
            "direction": e.direction, "strength": e.strength, "n": e.n,
            "ci_deflated": xc.get("ci_deflated"), "n_tests": (e.evidence.get("xcorr") or {}
                                                              ).get("n_tests"),
            "stability": e.stability, "state_dependence": e.state_dependence,
            "nonlinearity": e.nonlinearity, "incremental_info": e.incremental_info,
            "p_perm": inc.get("p_value"), "plausibility": e.plausibility,
            "prior_direction": e.evidence.get("prior_direction"),
            "prior_source": e.evidence.get("prior_source"), "decay_cls": e.decay_cls,
            "measured_via": e.evidence.get("measured_via"), "status": e.status,
            "reason": e.reason, "measured_at": e.measured_at}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--symbol", action="append", default=None)
    ap.add_argument("--budget-s", type=float, default=DEFAULT_BUDGET_S)
    a = ap.parse_args()
    rep = run(symbols=a.symbol, budget_s=a.budget_s)
    c = rep["counts"]
    print(f"WORLD CAUSAL GRAPH  {rep['status']}  nodes={c['nodes']} edges={c['edges']} "
          f"admitted={c['admitted']} recorded_not_admitted={c['recorded_not_admitted']} "
          f"unmeasured={c['plausible_unmeasured']} multiplicity={c['multiplicity_charged']} "
          f"chains seeded/measured/admitted={rep['chains_seeded']}/{rep['chains_measured']}/"
          f"{rep['chains_admitted']}  spent={rep['spent_s']}s")
    if rep["why"]:
        print(f"  why: {rep['why']}")
    for e in rep["admitted_edges"][:10]:
        print(f"  ADMITTED {e['src']} -> {e['dst']} lag={e['lag']}{e['clock']} "
              f"r={e['strength']:+.4f} n={e['n']} via {e['measured_via']}")
    for sym, rows in list(rep["conditioning_hints"].items())[:8]:
        print(f"  HINT {sym}: " + ", ".join(f"{r['src']}@{r['lag']}{r['clock']}/{r['decay_cls']}"
                                            for r in rows[:4]))
    print(f"written: {GRAPH}\nwritten: {REPORT}")
    print("YIELD " + json.dumps({"edges_measured": rep["edges_measured"],
                                 "edges_admitted": rep["edges_admitted"],
                                 "paths_new": rep["paths_new"],
                                 "discovered": rep["discovered"]}), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
