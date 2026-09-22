"""THE EVENT-GRAPH LAB (LAWS 5m): the cross-market event graph built from the desk's own stores,
its edges measured on the desk's own bars and series, and the causal adjudicator run on the
newest queued candidates and on every LIVE / STANDBY sleeve's declared mechanism.

    python research/event_graph_lab.py --once --budget-s 900 [--dry-run]

WHAT ONE PASS DOES, in order and inside its budget:

  1. BUILD the graph (`libs.research.event_graph`) from what already exists: the event ontology's
     kinds and transmission edges, the country packs' transmission seeds through
     `transmission_engine.seed_edges`, the world causal graph's measured edges, and the observed
     event instances in the desk's event logs. Nothing is redeclared here.
  2. MEASURE a rotating slice of edges whose two ends are series this box holds (a symbol's daily
     return, a macro series stamped by `knowable_at`), with the ANTI-LOOKAHEAD RULE inside the
     alignment: x_t against y_{t+lag}, lag >= 1 day, controls read at t. A SUPPORTED edge
     becomes DESK_MEASURED with its strength; a refuted one keeps its evidence state and carries
     the refutation, because "measured and found nothing" is negative knowledge worth an edge.
  3. ADJUDICATE the newest queued candidates and every LIVE / STANDBY sleeve. A candidate's
     declared mechanism is turned into (cause, effect) arrays on its own bars by a MECHANISM
     TEMPLATE for the family (a gap in ATR units against the return that follows it; a breakout
     distance against the hold that follows; ...), with y's own persistence and the symbol's
     trailing momentum as the simpler and common-factor explanations, a stale and a permuted
     cause as placebos, and the halves of the sample as subsets. A family with no template is
     UNMEASURED by name -- a value, never a pass.
  4. RECORD `causal_verdict` on the candidate rows (registry EXTENSIONS; status untouched --
     L1.60: the ten gates decide), the sleeves' verdicts in research memory, and every verdict
     as a gate reading on the hypothesis graph.
  5. DONATE edge-derived candidate seeds to the compiler, rotating through the graph so every
     edge is eventually offered: `data/intelligence/event_graph/discoveries_<ts>.json`, the seat
     shape `miner_candidate_compiler` reads (`kind: hypothesis`, a registered family, explicit
     params, the falsifier and the competing explanations on the row).

Artifact: `reports/EVENT_GRAPH.json`. State: `data/event_graph/graph.json` (the graph, so
community change is measured against the previous pass) and `data/event_graph/cursor.json`.
`--dry-run` builds, measures, adjudicates and prints, and writes nothing anywhere.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from collections.abc import Callable, Mapping, Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np

DESK = Path(__file__).resolve().parents[1]
ROOT = DESK.parent.parent
for _p in (str(DESK), str(DESK / "research"), str(ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from libs.research import causal_adjudicator as ca  # noqa: E402
from libs.research import event_graph as eg  # noqa: E402
from libs.research import event_ontology as eo  # noqa: E402

SOURCE = "event_graph"
UNIVERSE_DIR = DESK / "data" / "universe"
UNIVERSE_JSON = UNIVERSE_DIR / "universe.json"
STORE_DIR = DESK / "data" / "event_graph"
STORE = STORE_DIR / "graph.json"
CURSOR = STORE_DIR / "cursor.json"
REPORT = DESK / "reports" / "EVENT_GRAPH.json"
INTEL = DESK / "data" / "intelligence" / "event_graph"
WORLD_GRAPH = DESK / "data" / "world_causal_graph.json"
TRANSMISSION_GRAPH = DESK / "data" / "transmission_graph.json"
SLEEVES = DESK / "data" / "sleeves.json"
EVENT_LOGS: tuple[Path, ...] = (DESK / "data" / "events" / "events.jsonl",
                                ROOT / "data" / "events.jsonl")

BUDGET_S = 900.0
#: Breadth-per-run bounds, and only so a pass finishes inside its budget (LAWS 2: NO QUOTA).
#: Each is a ROTATION slice: the cursor carries on where the last pass stopped, so every edge,
#: candidate and sleeve is reached across passes and nothing is capped forever.
MAX_EDGES_PER_PASS = 40
MAX_CANDIDATES_PER_PASS = 24
MAX_DONATIONS_PER_PASS = 40
MAX_EVENT_ROWS = 500
N_PERM = 200
UNMEASURED = "UNMEASURED"

#: Bootstrap session windows in broker hours (UTC on this desk's parquet), read when a sleeve
#: or candidate names a session. A SEED: `mt5desk.family_call.SESSIONS` is the traded table and
#: is read first when importable; this only fills what it does not name.
SESSION_SEED: dict[str, tuple[int, int] | None] = {
    "asia": (0, 8), "london": (8, 16), "ny": (14, 22), "new_york": (14, 22),
    "overlap": (13, 17), "all": None, "continuous": None,
}
#: Breakout selector -> the window the certificate was hunted on. A seed of the same table
#: `shadow_forward.WINDOWS` keeps; it is read first when importable.
WINDOW_SEED: dict[str, dict[str, Any]] = {
    "asia": {"range_start": 7, "wait_bars": 12, "rr": 2.0, "ttl_bars": 12},
    "london_am": {"range_start": 10, "range_end": 13, "signal_at": 13, "wait_bars": 8,
                  "rr": 2.0, "ttl_bars": 12},
    "ny_open": {"range_start": 13, "range_end": 14, "signal_at": 14, "wait_bars": 12,
                "rr": 2.0, "ttl_bars": 12},
    "afternoon": {"range_start": 14, "range_end": 17, "signal_at": 17, "wait_bars": 8,
                  "rr": 2.0, "ttl_bars": 12},
}

RULE = ("the graph is built from what the desk already declared, every edge is a hypothesis with "
        "a falsifier, every mechanism is adjudicated on the desk's own series with x_t against "
        "y_(t+lag), and a verdict is recorded, never used as a gate")


# ----------------------------------------------------------------------------------- helpers
def _now() -> str:
    return datetime.now(tz=UTC).isoformat(timespec="seconds")


def _read_json(path: Path, default: Any = None) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, ValueError):
        return default


def _write_atomic(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + f".tmp{os.getpid()}")
    tmp.write_text(json.dumps(payload, indent=1, ensure_ascii=False, default=str),
                   encoding="utf-8")
    os.replace(tmp, path)


def _read_jsonl(path: Path, limit: int) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    try:
        with path.open(encoding="utf-8", errors="replace") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    row = json.loads(line)
                except ValueError:
                    continue
                if isinstance(row, dict):
                    rows.append(row)
    except OSError:
        return []
    return rows[-limit:]


def load_universe() -> dict[str, str]:
    doc = _read_json(UNIVERSE_JSON, {}) or {}
    out: dict[str, str] = {}
    for sym, row in doc.items():
        if str(sym).startswith("_") or not isinstance(row, dict):
            continue
        out[str(sym).upper()] = str(row.get("asset_class") or "")
    return out


def _sessions() -> dict[str, tuple[int, int] | None]:
    table = dict(SESSION_SEED)
    try:
        from mt5desk.family_call import SESSIONS
        table.update({str(k): v for k, v in dict(SESSIONS).items()})
    except Exception:
        pass
    return table


def _windows() -> dict[str, dict[str, Any]]:
    table = {k: dict(v) for k, v in WINDOW_SEED.items()}
    try:
        import shadow_forward as sf
        for k, v in dict(getattr(sf, "WINDOWS", {}) or {}).items():
            table[str(k)] = dict(v)
    except Exception:
        pass
    return table


# ------------------------------------------------------------------------------- bars / series
def load_bars(symbol: str, timeframe: str = "H1") -> Any:
    """`<SYM>_<TF>.parquet` as a UTC-indexed OHLC frame, or None."""
    path = UNIVERSE_DIR / f"{symbol.upper()}_{str(timeframe).upper()}.parquet"
    if not path.exists():
        return None
    try:
        import pandas as pd
        frame = pd.read_parquet(path)
        if "time" in frame.columns:
            frame = frame.set_index("time")
        frame.index = pd.DatetimeIndex(pd.to_datetime(frame.index, utc=True, errors="coerce"))
        frame = frame[~frame.index.isna()].sort_index()
        need = {"open", "high", "low", "close"}
        return frame if need <= set(frame.columns) and len(frame) else None
    except Exception:
        return None


def _leg_series(selector: str) -> tuple[np.ndarray, np.ndarray] | None:
    """(days, values) for `sym:X` (daily log return) or `series:name`, through the
    transmission engine's own loaders so a series means the same thing in both organs."""
    try:
        import transmission_engine as te
        return te._leg_series(selector)
    except Exception:
        return None


def _align_days(a: tuple[np.ndarray, np.ndarray], b: tuple[np.ndarray, np.ndarray],
                *more: tuple[np.ndarray, np.ndarray]) -> tuple[np.ndarray, list[np.ndarray]]:
    common = np.asarray(a[0], dtype="datetime64[D]")
    for other in (b, *more):
        common = np.intersect1d(common, np.asarray(other[0], dtype="datetime64[D]"))
    out: list[np.ndarray] = []
    for series in (a, b, *more):
        days = np.asarray(series[0], dtype="datetime64[D]")
        pos = np.searchsorted(days, common)
        out.append(np.asarray(series[1], dtype="float64")[pos])
    return common, out


# ------------------------------------------------------------------------------ the graph
def build_graph(*, universe: Mapping[str, str], previous: Mapping[str, Any] | None = None,
                seed_rows: Sequence[Mapping[str, Any]] | None = None,
                causal_rows: Sequence[Mapping[str, Any]] | None = None,
                event_rows: Sequence[Mapping[str, Any]] | None = None,
                notes: list[str] | None = None) -> eg.EventGraph:
    """The graph from the desk's stores (or the rows a caller hands in), on top of the previous
    pass's graph so measurements survive a re-seed."""
    notes = notes if notes is not None else []
    graph = eg.EventGraph.from_doc(previous)
    n_onto = eg.seed_from_ontology(graph, universe=universe)
    if seed_rows is None:
        seed_rows = []
        try:
            import transmission_engine as te
            packs, pack_notes = te.load_packs()
            notes.extend(f"packs: {n}" for n in pack_notes[:5])
            seed_rows = list(te.seed_edges(packs))
            stored = _read_json(TRANSMISSION_GRAPH, {}) or {}
            measured = {str(e.get("id")): e for e in (stored.get("edges") or [])
                        if isinstance(e, dict) and e.get("measured")}
            seed_rows = [dict(r, **measured.get(str(r.get("id")), {})) for r in seed_rows]
        except Exception as exc:
            notes.append(f"transmission seeds UNMEASURED: {type(exc).__name__}: {exc}")
    n_tx = eg.seed_from_transmission(graph, seed_rows, universe=universe)
    if causal_rows is None:
        doc = _read_json(WORLD_GRAPH, {}) or {}
        causal_rows = [e for e in (doc.get("edges") or []) if isinstance(e, dict)]
    n_ca = eg.seed_from_causal_edges(graph, causal_rows, universe=universe)
    if event_rows is None:
        event_rows = []
        for log in EVENT_LOGS:
            event_rows.extend(r for r in _read_jsonl(log, MAX_EVENT_ROWS)
                              if str(r.get("kind") or "").lower() in eo.ONTOLOGY)
    n_ev = eg.seed_from_events(graph, event_rows, limit=MAX_EVENT_ROWS)
    notes.append(f"seeded edges: ontology {n_onto}, transmission {n_tx}, causal {n_ca}, "
                 f"events {n_ev}")
    return graph


def measurable_edges(graph: eg.EventGraph) -> list[eg.Edge]:
    """Edges whose both ends carry a `sym:` / `series:` selector, oldest measurement first."""
    out: list[eg.Edge] = []
    for e in graph.edges.values():
        s, d = graph.nodes[e.src], graph.nodes[e.dst]
        if str(s.attrs.get("selector") or "").startswith(("sym:", "series:")) and \
                str(d.attrs.get("selector") or "").startswith("sym:"):
            out.append(e)
    out.sort(key=lambda e: (e.measured_at or "", e.id))
    return out


def _controls_for(days: np.ndarray, loader: Callable[[str], Any]) -> dict[str, np.ndarray]:
    """The common factors every macro edge must beat: global risk (US500) and the dollar leg."""
    out: dict[str, np.ndarray] = {}
    for name, sel in (("us500", "sym:US500"), ("usd", "sym:USDX")):
        got = loader(sel)
        if got is None:
            continue
        d = np.asarray(got[0], dtype="datetime64[D]")
        v = np.asarray(got[1], dtype="float64")
        pos = np.searchsorted(d, days)
        ok = (pos < len(d)) & (d[np.minimum(pos, len(d) - 1)] == days)
        arr = np.full(len(days), np.nan)
        arr[ok] = v[pos[ok]]
        if np.isfinite(arr).sum() >= ca.MIN_N:
            out[name] = arr
    return out


def measure_edge(edge: eg.Edge, graph: eg.EventGraph, *, loader: Callable[[str], Any],
                 seed: int = 0) -> dict[str, Any]:
    """One edge on the desk's own daily series. Anti-lookahead: x_t against y_{t+lag}, lag >= 1
    day; every control read at t; a series is dated by `knowable_at` in the loader."""
    src, dst = graph.nodes[edge.src], graph.nodes[edge.dst]
    xs, ys = loader(str(src.attrs["selector"])), loader(str(dst.attrs["selector"]))
    if xs is None or ys is None:
        missing = [n.label for n, got in ((src, xs), (dst, ys)) if got is None]
        return {"edge_id": edge.id, "verdict": UNMEASURED, "failing_test": "data",
                "why": f"series absent on this box: {missing}"}
    days, (x, y) = _align_days(xs, ys)
    if len(days) < ca.MIN_N:
        return {"edge_id": edge.id, "verdict": UNMEASURED, "failing_test": "data",
                "why": f"{len(days)} common day(s) < {ca.MIN_N}"}
    lag = max(1, int(round(float(edge.lag or 1.0))))
    own = np.concatenate([[np.nan], y[:-1]])
    controls = _controls_for(days, loader)
    hyp = eg.edge_hypothesis(edge, graph)
    half = np.arange(len(days)) < len(days) // 2
    rng = np.random.default_rng(seed)
    m = ca.Mechanism(
        name=f"{src.label} -> {dst.label}", cause=x, effect=y, lag=lag,
        claimed_sign={"+": 1, "-": -1}.get(edge.sign, 0), controls=controls,
        placebo_predictors={"stale_cause": np.concatenate([np.full(lag * 5, np.nan),
                                                            x[:-lag * 5]]) if len(x) > lag * 5
                            else x, "permuted_cause": rng.permutation(x)},
        subsets={"first_half": half.astype(float), "second_half": (~half).astype(float)},
        simpler={"own_persistence": own}, competing=tuple(hyp["competing"]),
        falsifier=str(hyp["falsifier"]))
    adj = ca.adjudicate(m, seed=seed, n_perm=N_PERM)
    beta = adj.estimate.get("beta")
    row = {"edge_id": edge.id, "signature": f"{src.label} -> {dst.label}", "lag_days": lag,
           "n": adj.n, "verdict": adj.verdict, "failing_test": adj.failing_test,
           "effect": beta, "p": adj.estimate.get("p"), "controls": sorted(controls),
           "why": adj.eligibility_why}
    detail = {"verdict": adj.verdict, "failing_test": adj.failing_test, "p": row["p"],
              "n": adj.n, "at": _now()}
    if adj.verdict == ca.SUPPORTED and isinstance(beta, (int, float)):
        graph.set_measurement(edge.id, strength=float(beta), sign="+" if beta > 0 else "-",
                              detail=detail)
    else:
        edge.measured_at = _now()
        edge.detail.update({"last_adjudication": detail})
    return row


# ------------------------------------------------------------------ mechanism templates
def _atr(h: np.ndarray, low: np.ndarray, c: np.ndarray, n: int) -> np.ndarray:
    prev = np.concatenate([[c[0]], c[:-1]])
    tr = np.maximum(h - low, np.maximum(np.abs(h - prev), np.abs(low - prev)))
    out = np.empty(len(tr))
    csum = np.cumsum(np.nan_to_num(tr))
    for i in range(len(tr)):
        lo = max(0, i - n + 1)
        out[i] = (csum[i] - (csum[lo - 1] if lo > 0 else 0.0)) / (i - lo + 1)
    return out


def _rsi(c: np.ndarray, n: int) -> np.ndarray:
    d = np.diff(c, prepend=c[0])
    gain, loss = np.where(d > 0, d, 0.0), np.where(d < 0, -d, 0.0)
    cg, cl = np.cumsum(gain), np.cumsum(loss)
    out = np.full(len(c), np.nan)
    for i in range(len(c)):
        lo = max(0, i - n + 1)
        g = (cg[i] - (cg[lo - 1] if lo > 0 else 0.0)) / (i - lo + 1)
        ls = (cl[i] - (cl[lo - 1] if lo > 0 else 0.0)) / (i - lo + 1)
        out[i] = 100.0 - 100.0 / (1.0 + g / ls) if ls > 0 else np.nan
    return out


def _forward(o: np.ndarray, hold: int, atr: np.ndarray) -> np.ndarray:
    """y_t: the move from bar t's open to bar t+hold's open, in ATR units at t-1 (known at t)."""
    n = len(o)
    y = np.full(n, np.nan)
    a = np.concatenate([[atr[0]], atr[:-1]])
    if n > hold:
        y[:n - hold] = (o[hold:] - o[:n - hold]) / np.where(a[:n - hold] > 0, a[:n - hold],
                                                             np.nan)
    return y


def mechanism_arrays(family: str, frame: Any, params: Mapping[str, Any], *,
                     session: str | None = None, selector: str | None = None,
                     side: int = 0) -> dict[str, Any] | None:
    """(cause, effect, lag, claimed_sign) for a family's declared mechanism on OHLC bars, or
    None when the family has no template here (the caller records UNMEASURED by name).

    Every cause is a function of bars <= t; every effect starts at bar t+1's open (the
    adjudicator's lag of 1 bar). A session restricts WHERE the cause is defined; the complement
    is returned so the lab can ask whether the mechanism disappears outside it.
    """
    import pandas as pd
    if frame is None or len(frame) < 300:
        return None
    o = frame["open"].to_numpy(dtype="float64")
    h = frame["high"].to_numpy(dtype="float64")
    low = frame["low"].to_numpy(dtype="float64")
    c = frame["close"].to_numpy(dtype="float64")
    idx = pd.DatetimeIndex(frame.index)
    hour = np.asarray(idx.hour)
    dow = np.asarray(idx.dayofweek)
    day = np.asarray(idx.normalize().asi8)
    first_bar = np.concatenate([[True], day[1:] != day[:-1]])
    p = dict(params or {})
    atr_n = int(p.get("atr_n") or 20)
    atr = _atr(h, low, c, atr_n)
    safe_atr = np.where(atr > 0, atr, np.nan)
    n = len(o)
    x = np.full(n, np.nan)
    sign = 0
    hold = int(p.get("ttl_bars") or p.get("max_hold") or 8)
    fam = str(family or "").lower()
    if fam == "overnight_gap_decay":
        gap = np.full(n, np.nan)
        gap[1:] = o[1:] - c[:-1]
        x = np.where(first_bar, gap / safe_atr, np.nan)
        x[np.abs(np.nan_to_num(x)) < float(p.get("gap_atr") or 0.75)] = np.nan
        sign, hold = -1, int(p.get("ttl_bars") or 8)
    elif fam == "session_range_breakout":
        win = dict(_windows().get(str(selector or "asia"), {}))
        win.update({k: v for k, v in p.items() if k in ("range_start", "range_end", "signal_at",
                                                        "ttl_bars")})
        rs, re_ = int(win.get("range_start") or 7), win.get("range_end")
        sig_h = int(win.get("signal_at") or (re_ if re_ is not None else rs))
        in_range = (hour < rs) if re_ is None else ((hour >= rs) & (hour < int(re_)))
        hi_d: dict[int, float] = {}
        lo_d: dict[int, float] = {}
        for i in np.nonzero(in_range)[0]:
            d = int(day[i])
            hi_d[d] = max(hi_d.get(d, -np.inf), h[i])
            lo_d[d] = min(lo_d.get(d, np.inf), low[i])
        for i in np.nonzero(hour == sig_h)[0]:
            d = int(day[i])
            if d in hi_d and hi_d[d] > lo_d[d]:
                mid = 0.5 * (hi_d[d] + lo_d[d])
                x[i] = (c[i] - mid) / safe_atr[i]
        sign, hold = 1, int(win.get("ttl_bars") or 12)
    elif fam == "anti_donchian_breakout":
        look = int(p.get("lookback") or p.get("channel") or 20)
        for i in range(look, n):
            top, bot = np.max(h[i - look:i]), np.min(low[i - look:i])
            if c[i] > top:
                x[i] = (c[i] - top) / safe_atr[i]
            elif c[i] < bot:
                x[i] = (c[i] - bot) / safe_atr[i]
        sign = -1
    elif fam == "anti_three_bar_momentum":
        d1 = np.diff(c, prepend=c[0])
        for i in range(3, n):
            if (d1[i] > 0 and d1[i - 1] > 0 and d1[i - 2] > 0) or \
                    (d1[i] < 0 and d1[i - 1] < 0 and d1[i - 2] < 0):
                x[i] = (c[i] - c[i - 3]) / safe_atr[i]
        sign = -1
    elif fam == "dow_effect":
        dl, ds = int(p.get("dow_long", 0)), int(p.get("dow_short", 3))
        x = np.where((hour == 0) & (dow == dl), 1.0, np.where((hour == 0) & (dow == ds), -1.0,
                                                               np.nan))
        sign, hold = 1, int(p.get("ttl_bars") or 12)
    elif fam == "monday_gap":
        last_fri = np.nan
        for i in range(n):
            if dow[i] == 4:
                last_fri = c[i]
            if dow[i] == 0 and hour[i] == 0 and last_fri == last_fri:
                g = (o[i] - last_fri) / safe_atr[i]
                x[i] = g if abs(g) >= float(p.get("min_gap_atr") or 0.2) else np.nan
        sign = -1 if str(p.get("mode") or "momentum") == "fade" else 1
        hold = int(p.get("ttl_bars") or 12)
    elif fam == "mean_reversion_rsi":
        x = (_rsi(c, int(p.get("rsi_n") or 14)) - 50.0) / 50.0
        sign, hold = -1, int(p.get("ttl_bars") or 12)
    elif fam == "overnight_drift":
        hb, anchor = int(p.get("hold_bars") or 8), int(p.get("anchor_hour", 0))
        for i in range(hb, n):
            if hour[i] == anchor:
                drift = (c[i] - c[i - hb]) / safe_atr[i]
                x[i] = drift if abs(drift) >= 0.3 else np.nan
        sign, hold = -1, int(p.get("ttl_bars") or 12)
    else:
        return None
    if side:
        # A one-sided cell claims only its own side of the mechanism: the other side's
        # observations are not evidence for or against it.
        keep = (x * sign * side) > 0 if sign else np.full(n, True)
        x = np.where(keep, x, np.nan)
    y = _forward(o, max(1, hold), atr)
    complement: np.ndarray | None = None
    win_s = _sessions().get(str(session or "all").lower(), None) if session else None
    if win_s is not None:
        lo_h, hi_h = win_s
        inside = (hour >= lo_h) & (hour < hi_h)
        complement = np.where(inside, np.nan, x)
        x = np.where(inside, x, np.nan)
    if np.isfinite(x).sum() < ca.MIN_N:
        return {"cause": x, "effect": y, "lag": 1, "claimed_sign": sign, "hold": hold,
                "complement": complement, "n_cause": int(np.isfinite(x).sum()),
                "too_few": True}
    trail = np.full(n, np.nan)
    trail[24:] = (c[24:] - c[:-24]) / safe_atr[24:]
    own = np.full(n, np.nan)
    own[hold:] = (o[hold:] - o[:-hold]) / safe_atr[hold:]
    rng = np.random.default_rng(7)
    stale = np.concatenate([np.full(hold + 3, np.nan), x[:-(hold + 3)]])
    half = (np.arange(n) < n // 2).astype(float)
    return {"cause": x, "effect": y, "lag": 1, "claimed_sign": sign, "hold": hold,
            "controls": {"trailing_momentum_24": trail},
            "simpler": {"own_persistence": own},
            "placebo_predictors": {"stale_cause": stale, "permuted_cause": rng.permutation(x)},
            "subsets": {"first_half": half, "second_half": 1.0 - half},
            "complement": complement, "n_cause": int(np.isfinite(x).sum()), "too_few": False}


def adjudicate_mechanism(label: str, family: str, symbol: str, timeframe: str,
                         params: Mapping[str, Any], *, session: str | None = None,
                         selector: str | None = None, side: int = 0,
                         falsifier: str = "", competing: Sequence[str] = (),
                         bars_loader: Callable[[str, str], Any] = load_bars,
                         seed: int = 0) -> dict[str, Any]:
    """One declared mechanism through the whole ladder, on its own bars."""
    row: dict[str, Any] = {"label": label, "family": family, "symbol": symbol,
                           "timeframe": timeframe, "session": session, "selector": selector,
                           "verdict": UNMEASURED, "failing_test": "", "effect": None, "p": None,
                           "n": 0, "eligible": False, "why": ""}
    frame = bars_loader(symbol, timeframe)
    if frame is None:
        row.update(failing_test="data", why=f"no {timeframe} bars for {symbol} on this box")
        return row
    arrays = mechanism_arrays(family, frame, params, session=session, selector=selector,
                              side=side)
    if arrays is None:
        row.update(failing_test="template",
                   why=f"no mechanism template for family {family!r}: its declared mechanism "
                       f"is not price-only or has not been written down here")
        return row
    if arrays.get("too_few"):
        row.update(failing_test="data",
                   why=f"{arrays['n_cause']} mechanism observation(s) < {ca.MIN_N}")
        return row
    complement = arrays.pop("complement", None)
    spec = {k: v for k, v in arrays.items() if k not in ("n_cause", "too_few", "hold")}
    spec.update({"name": label, "falsifier": falsifier, "competing": list(competing)})
    adj = ca.adjudicate(ca.mechanism_from_spec(spec), seed=seed, n_perm=N_PERM)
    row.update(verdict=adj.verdict, failing_test=adj.failing_test,
               effect=adj.estimate.get("beta"), p=adj.estimate.get("p"), n=adj.n,
               eligible=adj.eligible, why=adj.eligibility_why, hold_bars=arrays["hold"],
               counterfactual=adj.counterfactual,
               refutations=[r.to_dict() for r in adj.refutations])
    if complement is not None and adj.verdict == ca.SUPPORTED:
        # DISAPPEARANCE: a session-specific mechanism must be absent outside its session.
        comp = dict(spec, cause=complement, name=f"{label} [outside session]")
        comp.pop("subsets", None)
        out = ca.adjudicate(ca.mechanism_from_spec(comp), seed=seed, n_perm=N_PERM)
        same_sign = np.sign(out.estimate.get("beta") or 0.0) == np.sign(adj.estimate.get("beta")
                                                                          or 0.0)
        row["outside_session"] = {"verdict": out.verdict, "effect": out.estimate.get("beta"),
                                  "p": out.estimate.get("p"), "n": out.n}
        if out.verdict == ca.SUPPORTED and same_sign:
            row.update(verdict=ca.REFUTED, failing_test="disappearance", eligible=False,
                       why="the mechanism is as strong outside its declared session: the "
                           "session is not the mechanism")
    return row


# ------------------------------------------------------------------- candidates and sleeves
def newest_queued(conn: Any, limit: int, *, before: str | None = None) -> list[dict[str, Any]]:
    """The newest queued candidates not yet adjudicated (or adjudicated before `before`)."""
    q = ("SELECT * FROM research_candidates WHERE status='queued' AND "
         "(causal_judged_at IS NULL OR causal_judged_at < ?) ORDER BY created_at DESC LIMIT ?")
    stamp = before or "9999"
    try:
        return [dict(r) for r in conn.execute(q, (stamp, int(limit)))]
    except Exception:
        return []


def _params_of(row: Mapping[str, Any]) -> dict[str, Any]:
    raw = row.get("params") if isinstance(row.get("params"), Mapping) else None
    if raw is None:
        try:
            raw = json.loads(str(row.get("params_json") or "{}"))
        except ValueError:
            raw = {}
    return dict(raw) if isinstance(raw, Mapping) else {}


def _competing_of(row: Mapping[str, Any]) -> list[str]:
    for key in ("competing", "competing_explanations", "alternatives"):
        v = row.get(key)
        if isinstance(v, (list, tuple)) and v:
            return [str(x) for x in v]
        if isinstance(v, str) and v.strip():
            return [s.strip() for s in v.split(";") if s.strip()]
    text = str(row.get("causal_rationale") or "")
    return [s.strip() for s in text.split("|")[1:] if s.strip()]


def adjudicate_candidate(row: Mapping[str, Any], *, bars_loader: Callable[[str, str], Any],
                         seed: int = 0) -> dict[str, Any]:
    params = _params_of(row)
    tf = str(params.get("timeframe") or row.get("chart") or "H1").upper()
    side_txt = str(params.get("side") or row.get("side") or "").upper()
    side = 1 if side_txt in ("LONG", "1", "+1") else -1 if side_txt in ("SHORT", "-1") else 0
    out = adjudicate_mechanism(
        f"candidate {row.get('id')}", str(row.get("family") or ""), str(row.get("symbol") or ""),
        tf, params, session=(str(row.get("session")) if row.get("session") else None),
        selector=(str(params.get("selector")) if params.get("selector") else None), side=side,
        falsifier=str(row.get("falsifier") or ""), competing=_competing_of(row),
        bars_loader=bars_loader, seed=seed)
    out.update(kind="candidate", candidate_id=str(row.get("id") or ""), params=params,
               status=str(row.get("status") or ""))
    return out


def adjudicate_sleeve(row: Mapping[str, Any], *, bars_loader: Callable[[str, str], Any],
                      seed: int = 0) -> dict[str, Any]:
    fam = str(row.get("family") or "")
    params = {k: row[k] for k in ("stop_atr", "target_atr", "max_hold", "lookback") if k in row}
    params.update(_params_of(row))
    out = adjudicate_mechanism(
        f"sleeve {row.get('name')}", fam, str(row.get("symbol") or ""),
        str(row.get("timeframe") or "H1").upper(), params,
        session=(str(row.get("session")) if row.get("session") else None),
        selector=(str(row.get("selector")) if row.get("selector") else None),
        falsifier=str(row.get("falsifier") or f"the {fam} mechanism on {row.get('symbol')} "
                                              f"stops paying on its forward clock"),
        competing=_competing_of(row) or ["the symbol's own persistence",
                                         "a common factor moves the session"],
        bars_loader=bars_loader, seed=seed)
    out.update(kind="sleeve", sleeve=str(row.get("name") or ""),
               status=str(row.get("status") or ""))
    if not fam:
        out.update(failing_test="mechanism", why="the sleeve declares no family, so it declares "
                                                  "no mechanism to adjudicate")
    return out


def live_sleeves(path: Path = SLEEVES) -> list[dict[str, Any]]:
    doc = _read_json(path, {}) or {}
    rows = doc.get("sleeves") if isinstance(doc, dict) else doc
    return [r for r in (rows or []) if isinstance(r, dict)
            and str(r.get("status") or "").upper() in ("LIVE", "STANDBY")]


def record_verdicts(rows: Sequence[Mapping[str, Any]], *, conn: Any, dry_run: bool
                    ) -> dict[str, int]:
    """Candidate rows get the EXTENSIONS columns (status untouched); sleeves go to research
    memory; every row is a gate reading on the hypothesis graph."""
    out = {"candidates": 0, "sleeves": 0, "graph": 0}
    if dry_run:
        return out
    try:
        from libs.moat import registry as R
    except Exception:
        return out
    for row in rows:
        try:
            if row.get("kind") == "candidate" and row.get("candidate_id"):
                if R.mark_candidate(str(row["candidate_id"]), str(row.get("status") or "queued"),
                                    conn=conn, causal_verdict=str(row["verdict"]),
                                    causal_failing_test=str(row.get("failing_test") or ""),
                                    causal_effect=row.get("effect"), causal_judged_at=_now(),
                                    causal_eligible=int(bool(row.get("eligible")))):
                    out["candidates"] += 1
            elif row.get("kind") == "sleeve":
                R.remember("causal", f"{row['label']}: {row['verdict']}"
                           + (f" ({row.get('failing_test')})" if row.get("failing_test") else "")
                           + f" -- {row.get('why')}", kind="causal_verdict",
                           memory_key=f"causal:{row.get('sleeve')}", result=str(row["verdict"]),
                           payload={k: row.get(k) for k in ("effect", "p", "n", "refutations",
                                                            "counterfactual", "outside_session")},
                           evidence={"rule": RULE, "at": _now()}, conn=conn)
                out["sleeves"] += 1
        except Exception:
            continue
    try:
        from libs.research import hypothesis_graph as hg
        out["graph"] = hg.record_causal_verdicts(
            [{"symbol": r.get("symbol"), "family": r.get("family"),
              "params": r.get("params") or {}, "verdict": r.get("verdict"),
              "failing_test": r.get("failing_test"), "effect": r.get("effect"),
              "eligible": r.get("eligible"), "source": SOURCE} for r in rows
             if r.get("symbol") and r.get("family")])
    except Exception:
        pass
    return out


# ----------------------------------------------------------------------------- donations
#: What a graph edge becomes for the compiler: a registered family with EXPLICIT params, so the
#: row compiles as an exact recipe rather than prose. Symbol-to-symbol edges ride
#: `relative_value` (the pair's spread reverts) and, once DESK_MEASURED, `correlation_regime`;
#: a macro series into a symbol rides `macro_conditional`.
def donation_rows(graph: eg.EventGraph, hypotheses: Sequence[Mapping[str, Any]],
                  universe: Mapping[str, str]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for hyp in hypotheses:
        if not hyp.get("testable"):
            continue
        dst = str(hyp["symbol"]).upper()
        if dst not in universe:
            continue
        src_sel = str(hyp.get("source_selector") or "")
        base = {"kind": "hypothesis", "source": SOURCE, "symbol": dst, "symbols": [dst],
                "mechanism": hyp["claim"], "claim": hyp["claim"], "falsifier": hyp["falsifier"],
                "competing": list(hyp["competing"]), "evidence_state": hyp["evidence"],
                "edge_id": hyp["edge_id"], "horizon": hyp["horizon"], "sign": hyp["sign"],
                "strength": hyp["strength"], "seen_at": _now(),
                "why": "an edge of the cross-market event graph, offered to the ten gates"}
        if src_sel.startswith("sym:"):
            peer = src_sel.split(":", 1)[1].upper()
            if peer == dst or peer not in universe:
                continue
            out.append({**base, "family": "relative_value", "params": {"peer_symbol": peer}})
            if hyp["evidence"] == eg.DESK_MEASURED:
                out.append({**base, "family": "correlation_regime",
                            "params": {"peer_symbol": peer}})
        elif src_sel.startswith("series:"):
            out.append({**base, "family": "macro_conditional",
                        "params": {"input_source": src_sel.split(":", 1)[1]}})
    return out


def donate(rows: Sequence[Mapping[str, Any]], *, out_dir: Path, dry_run: bool) -> str | None:
    if dry_run or not rows:
        return None
    stamp = datetime.now(tz=UTC).strftime("%Y%m%d_%H%M%S")
    path = out_dir / f"discoveries_{stamp}.json"
    _write_atomic(path, {"source": SOURCE, "at": _now(), "rule": RULE,
                         "n": len(rows), "discoveries": list(rows)})
    return str(path)


# ------------------------------------------------------------------------------- the pass
def build(*, budget_s: float = BUDGET_S, dry_run: bool = False, conn: Any = None,
          universe: Mapping[str, str] | None = None,
          seed_rows: Sequence[Mapping[str, Any]] | None = None,
          causal_rows: Sequence[Mapping[str, Any]] | None = None,
          event_rows: Sequence[Mapping[str, Any]] | None = None,
          candidate_rows: Sequence[Mapping[str, Any]] | None = None,
          sleeve_rows: Sequence[Mapping[str, Any]] | None = None,
          bars_loader: Callable[[str, str], Any] = load_bars,
          series_loader: Callable[[str], Any] = _leg_series,
          store: Path = STORE, cursor_path: Path = CURSOR, report: Path = REPORT,
          intel_dir: Path = INTEL, max_edges: int = MAX_EDGES_PER_PASS,
          max_candidates: int = MAX_CANDIDATES_PER_PASS,
          max_donations: int = MAX_DONATIONS_PER_PASS) -> dict[str, Any]:
    t0 = time.monotonic()
    deadline = t0 + max(1.0, float(budget_s))
    notes: list[str] = []
    uni = dict(universe) if universe is not None else load_universe()
    previous = _read_json(store, None)
    cursor = _read_json(cursor_path, {}) or {}
    graph = build_graph(universe=uni, previous=previous, seed_rows=seed_rows,
                        causal_rows=causal_rows, event_rows=event_rows, notes=notes)

    # 2. measure a rotating slice of edges
    measured: list[dict[str, Any]] = []
    pool = measurable_edges(graph)
    start = int(cursor.get("edge_cursor") or 0) % max(1, len(pool)) if pool else 0
    order = pool[start:] + pool[:start]
    for i, edge in enumerate(order[:max(0, int(max_edges))]):
        if time.monotonic() > deadline:
            notes.append(f"budget: {len(order) - i} measurable edge(s) left for the next pass")
            break
        measured.append(measure_edge(edge, graph, loader=series_loader, seed=i))
        cursor["edge_cursor"] = (start + i + 1) % max(1, len(pool))

    # 3. adjudicate the newest queued candidates and every LIVE / STANDBY sleeve
    adjudications: list[dict[str, Any]] = []
    c = conn
    opened = False
    if (candidate_rows is None and not dry_run) or candidate_rows is None:
        try:
            from libs.moat import registry as R
            c = conn or R.connect()
            opened = conn is None
            candidate_rows = newest_queued(c, max_candidates)
        except Exception as exc:
            notes.append(f"registry UNMEASURED: {type(exc).__name__}: {exc}")
            candidate_rows = []
    try:
        for i, row in enumerate(list(candidate_rows)[:max(0, int(max_candidates))]):
            if time.monotonic() > deadline:
                notes.append("budget: candidates left for the next pass")
                break
            adjudications.append(adjudicate_candidate(row, bars_loader=bars_loader, seed=i))
        sleeves = list(sleeve_rows) if sleeve_rows is not None else live_sleeves()
        for i, row in enumerate(sleeves):
            if time.monotonic() > deadline:
                notes.append("budget: sleeves left for the next pass")
                break
            adjudications.append(adjudicate_sleeve(row, bars_loader=bars_loader, seed=i))
        recorded = record_verdicts(adjudications, conn=c, dry_run=dry_run)
    finally:
        if opened and c is not None:
            try:
                c.close()
            except Exception:
                pass

    # 4. readings and hypotheses; 5. donations, rotating through the graph's hypotheses
    readings = graph.readings()
    labels = graph.communities()
    prev_labels = (previous or {}).get("communities") if isinstance(previous, dict) else None
    change = graph.community_change(prev_labels if isinstance(prev_labels, dict) else None,
                                    labels)
    instances = [n for n in graph.nodes_of_kind("event") if n.attrs.get("instance")]
    instances.sort(key=lambda n: str(n.attrs.get("at") or ""), reverse=True)
    seeds = {n.id: 1.0 for n in instances[:10]} or {
        n.id: 0.5 for n in graph.nodes_of_kind("event")[:10]}
    contagion = dict(list(graph.contagion(seeds).items())[:40])
    paths: list[dict[str, Any]] = []
    for n in (instances[:5] or graph.nodes_of_kind("event")[:5]):
        for p in graph.propagation_paths(n.id, limit=4):
            paths.append(eg.summarise_path(p, graph))
    hyps = graph.hypotheses()
    testable = [h for h in hyps if h.get("testable")]
    hstart = int(cursor.get("hypothesis_cursor") or 0) % max(1, len(testable)) if testable else 0
    rows = donation_rows(graph, testable[hstart:] + testable[:hstart], uni)[:max(0, max_donations)]
    cursor["hypothesis_cursor"] = (hstart + len(rows)) % max(1, len(testable))
    donated = donate(rows, out_dir=intel_dir, dry_run=dry_run)

    unmeasured = ([{"what": m["edge_id"], "why": m["why"]} for m in measured
                   if m["verdict"] == UNMEASURED]
                  + [{"what": a["label"], "why": a["why"]} for a in adjudications
                     if a["verdict"] == UNMEASURED])
    counts = {v: sum(1 for a in adjudications if a["verdict"] == v) for v in ca.VERDICTS}
    doc = {
        "at": _now(), "rule": RULE, "dry_run": bool(dry_run),
        "readings": readings, "community_change": change, "contagion": contagion,
        "propagation_paths": paths[:20],
        "measured_edges": {"n": len(measured), "pool": len(pool),
                           "supported": sum(1 for m in measured if m["verdict"] == ca.SUPPORTED),
                           "refuted": sum(1 for m in measured if m["verdict"] == ca.REFUTED),
                           "rows": measured},
        "adjudications": {"n": len(adjudications), "counts": counts,
                          "eligible": sum(1 for a in adjudications if a.get("eligible")),
                          "rows": [{k: v for k, v in a.items() if k != "refutations"}
                                   for a in adjudications],
                          "recorded": recorded},
        "hypotheses": {"n": len(hyps), "testable": len(testable), "donated": len(rows),
                       "file": donated},
        "unmeasured": unmeasured, "notes": notes, "cursor": cursor,
        "seconds": round(time.monotonic() - t0, 2),
    }
    if not dry_run:
        stored = graph.to_doc()
        stored["communities"] = labels
        _write_atomic(store, stored)
        _write_atomic(cursor_path, {**cursor, "at": _now()})
        _write_atomic(report, doc)
    return doc


def render(doc: Mapping[str, Any]) -> list[str]:
    r, m, a = doc.get("readings") or {}, doc.get("measured_edges") or {}, \
        doc.get("adjudications") or {}
    lines = [f"EVENT GRAPH  {r.get('n_nodes')} nodes / {r.get('n_edges')} edges "
             f"{r.get('edges_by_evidence')}; measured {m.get('n')}/{m.get('pool')} "
             f"(supported {m.get('supported')}, refuted {m.get('refuted')}); adjudicated "
             f"{a.get('n')} {a.get('counts')}; donated {(doc.get('hypotheses') or {}).get('donated')}"]
    for row in (a.get("rows") or [])[:12]:
        lines.append(f"  {row['verdict']:<14} {str(row['label'])[:48]:<48} "
                     f"{row.get('failing_test') or '-':<18} effect={row.get('effect')} "
                     f"n={row.get('n')}")
    for note in doc.get("notes") or []:
        lines.append(f"  note: {note}")
    return lines


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="the cross-market event graph and its adjudicator")
    ap.add_argument("--once", action="store_true", help="one pass (the hourly leg)")
    ap.add_argument("--budget-s", type=float, default=BUDGET_S)
    ap.add_argument("--dry-run", action="store_true", help="build, measure, adjudicate, print; "
                                                            "write nothing")
    ap.add_argument("--max-candidates", type=int, default=MAX_CANDIDATES_PER_PASS)
    a = ap.parse_args(argv)
    doc = build(budget_s=a.budget_s, dry_run=a.dry_run, max_candidates=a.max_candidates)
    for line in render(doc):
        print(line)
    if a.dry_run:
        print("  --dry-run: no graph, cursor, report, registry row or donation written")
    else:
        print(f"  -> {REPORT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
