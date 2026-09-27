"""F8 -- FEED THE SEARCH WHAT THE DESK CANNOT EXPLAIN.

THE PRINCIPAL, 2026-09-12:

    Don't only ask the AI to invent strategies. Feed it everything the existing models cannot
    explain: large forecast residuals, ensemble disagreement, unexplained drawdowns, cross-market
    decouplings, unusual execution deterioration, state transitions and new latent clusters. Then
    generate hypotheses whose purpose is to explain those errors. This is how the system searches
    outside its current ontology.

THE ASYMMETRY THIS EXPLOITS. Every generator on this desk proposes from INSIDE its own ontology:
the grammar composes known primitives, the seats are prompted with the desk's own vocabulary, the
miners read claims written in the language of things people already trade. A search that can only
recombine what it already represents cannot find what it has no word for -- and the places where
the desk's models are WRONG are the only observations that carry information about the missing
word. An anomaly is not a nuisance, it is the single highest-information row the desk owns.

WHAT IT COLLECTS, all from artifacts that already exist:

    unexplained_move    a bar in the top percentile of absolute return with no macro event within
                        the window -- the desk's event ontology has no entry for whatever moved it
    decoupling          a pair whose recent correlation has flipped sign against its own history,
                        so a relationship the book is implicitly sizing on has stopped holding
    dispersion_break    a symbol whose realised volatility has broken its own regime band, which
                        is a state transition the regime labels did not name
    cost_shock          an hour whose measured spread is a multiple of its own median, which is
                        execution deterioration nothing currently reacts to
    latent_state        the latest joint return/volatility/skew/autocorrelation state lies beyond
                        the historical feature cloud -- a state no single regime label describes
    directed_emergence  A's lagged return has newly begun to lead B, a possible information path
                        absent from the desk's current directed market graph

EACH ROW IS A QUESTION, NEVER AN ANSWER. The output is not a hypothesis -- it is the EVIDENCE a
hypothesis would have to explain, phrased so a seat can be asked "what mechanism would produce
this?" rather than "invent something". That difference is the whole of F8: the desk already has
generators, and what it lacks is a supply of anomalies pointed at them.

NOTHING HERE TRADES, SIZES OR PROMOTES. It writes a queue of unexplained observations. Whatever a
seat proposes from them faces the identical ten gates as every other candidate.

    python desks/mt5/research/unknown_unknowns.py [--apply]
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

DESK = Path(__file__).resolve().parents[1]
ROOT = DESK.parent.parent
for _p in (str(DESK), str(DESK / "research"), str(ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

UNI = DESK / "data" / "universe"
UNIVERSE_CANON = UNI / "universe.canon.json"
SLEEVES = DESK / "data" / "sleeves.json"
EVENTS = DESK / "data" / "macro" / "event_ledger.jsonl"
OUT = DESK / "reports" / "UNKNOWN_UNKNOWNS.json"
QUEUE = DESK / "data" / "unknown_unknowns_queue.jsonl"
STATE = DESK / "data" / "unknown_unknowns_state.json"

# Every live sleeve x available timeframe is inspected on every pass.  This many additional
# non-equity universe cells are then visited through a durable round-robin cursor.  It is a
# throughput knob, not a coverage cap: every available cell is eventually visited even when the
# universe is larger than one safe hourly memory budget.
ROTATION_CELLS = max(1, int(os.environ.get("MT5_UNKNOWN_FRONTIER_CELLS", "120")))

#: Bars examined. ~1,500 H1 is about nine months -- long enough that "unprecedented" means
#: something and short enough that the desk's current ontology is the one being tested.
BARS = 1500

#: A move is UNEXPLAINED when it is this extreme. The 99.5th percentile of |return| keeps the
#: list to roughly the top 7 bars per symbol per nine months, which is a reading list rather than
#: a firehose -- an anomaly queue nobody can read is an anomaly queue nobody reads.
MOVE_Q = 0.995

#: Hours either side of a macro event within which a move is considered explained. Three hours
#: covers the release, the revision headlines and the first liquidity recovery; beyond that,
#: attributing a move to the event is storytelling.
EVENT_WINDOW_H = 3

#: A correlation has DECOUPLED when recent and historical disagree by this much. 0.6 is roughly
#: the gap between "a relationship weakened" and "a relationship inverted".
DECOUPLE_DELTA = 0.6

#: Realised vol outside this multiple of its own trailing band is a regime the labels did not name.
VOL_BREAK_MULT = 2.5

# A spread observation this far above its own recent median is an execution-state anomaly.
COST_SHOCK_MULT = 3.0

# Unknown-state thresholds are deliberately extreme because these observations seed research.
# They do not pass a gate, but flooding the converter with ordinary states still wastes compute.
LATENT_Q = 0.995
LATENT_WINDOW = 60
LEAD_MIN = 0.35
LEAD_DELTA = 0.35
PAIR_BUDGET = max(1, int(os.environ.get("MT5_UNKNOWN_PAIR_BUDGET", "2000")))

TIMEFRAMES = ("M1", "M5", "M15", "M30", "H1", "H4", "D1")


def _json(path: Path, default: Any) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, ValueError, TypeError):
        return default


def _sleeve_symbols() -> list[str]:
    doc = _json(SLEEVES, {})
    rows = doc if isinstance(doc, list) else (doc.get("sleeves") or [])
    return sorted({str(r.get("symbol") or "").strip() for r in rows
                   if isinstance(r, dict)
                   and str(r.get("status", "")).upper() in {"LIVE", "FORWARD", "SHADOW"}
                   and str(r.get("symbol") or "").strip()})


def _available_cells() -> list[tuple[str, str, str]]:
    """All executable bar cells on disk; single-name equities remain in their event lane."""
    canon = _json(UNIVERSE_CANON, {})
    out: list[tuple[str, str, str]] = []
    for p in UNI.glob("*.parquet"):
        stem = p.stem
        tf = next((x for x in TIMEFRAMES if stem.endswith(f"_{x}")), "")
        if not tf:
            continue
        sym = stem[:-(len(tf) + 1)]
        meta = canon.get(sym, {}) if isinstance(canon, dict) else {}
        asset = str(meta.get("asset_class") or "UNKNOWN")
        if asset.lower() in {"equities", "equity", "stocks", "stock"}:
            continue
        out.append((sym, tf, asset))
    return sorted(set(out), key=lambda x: (TIMEFRAMES.index(x[1]), x[2], x[0]))


def _selected_cells() -> tuple[list[tuple[str, str, str]], dict[str, Any]]:
    """All sleeve cells plus a resumable slice of every other executable bar cell."""
    all_cells = _available_cells()
    sleeve_symbols = set(_sleeve_symbols())
    sleeve_cells = [c for c in all_cells if c[0] in sleeve_symbols]
    frontier = [c for c in all_cells if c[0] not in sleeve_symbols]
    old = _json(STATE, {})
    cursor = int(old.get("cursor", 0) or 0)
    chosen: list[tuple[str, str, str]] = []
    if frontier:
        n = min(ROTATION_CELLS, len(frontier))
        chosen = [frontier[(cursor + i) % len(frontier)] for i in range(n)]
        cursor = (cursor + n) % len(frontier)
    cells = list(dict.fromkeys(sleeve_cells + chosen))
    return cells, {
        "cursor": cursor,
        "available_cells": len(all_cells),
        "sleeve_cells": len(sleeve_cells),
        "rotating_cells": len(chosen),
        "frontier_cells": len(frontier),
        "pair_cursors": dict(old.get("pair_cursors") or {}),
        "bar_watermarks": dict(old.get("bar_watermarks") or {}),
        "seen": list(old.get("seen") or []),
    }


def _latent_features(r: Any, np: Any, pd: Any) -> Any:
    """Rolling state vector; no market ontology or hand-labelled regime enters this transform."""
    mean = r.rolling(LATENT_WINDOW).mean()
    vol = r.rolling(LATENT_WINDOW).std()
    skew = r.rolling(LATENT_WINDOW).skew()
    auto = r.rolling(LATENT_WINDOW).corr(r.shift(1))
    downside = (r < 0).astype(float).rolling(LATENT_WINDOW).mean()
    frame = pd.concat({"mean": mean, "vol": vol, "skew": skew,
                       "auto": auto, "downside": downside}, axis=1).dropna()
    if len(frame) < 8 * LATENT_WINDOW:
        return None
    hist = frame.iloc[:-1]
    med = hist.median()
    scale = (hist - med).abs().median().replace(0, np.nan)
    z = ((frame - med) / scale).replace([np.inf, -np.inf], np.nan).dropna()
    if len(z) < 6 * LATENT_WINDOW:
        return None
    return np.sqrt((z * z).sum(axis=1))


def _pair_slice(frame: Any, state: dict[str, Any], timeframe: str) -> list[tuple[str, str]]:
    cols = sorted(frame.columns)
    pairs = [(a, b) for a in cols for b in cols if a != b]
    if not pairs:
        return []
    cursors = state.setdefault("pair_cursors", {})
    cursor = int(cursors.get(timeframe, 0) or 0) % len(pairs)
    n = min(PAIR_BUDGET, len(pairs))
    chosen = [pairs[(cursor + i) % len(pairs)] for i in range(n)]
    cursors[timeframe] = (cursor + n) % len(pairs)
    state.setdefault("directed_pairs_available", {})[timeframe] = len(pairs)
    state.setdefault("directed_pairs_scanned", {})[timeframe] = n
    return chosen


def _live_symbols(limit: int = 20) -> list[str]:
    try:
        doc = json.loads(SLEEVES.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []
    rows = doc if isinstance(doc, list) else (doc.get("sleeves") or [])
    out: list[str] = []
    for r in rows:
        if isinstance(r, dict) and str(r.get("status", "")).upper() == "LIVE":
            s = str(r.get("symbol") or "").strip()
            if s and s not in out:
                out.append(s)
    # AIMED AT WHAT THE DESK CANNOT EXPLAIN (Tier-1 B8, 2026-09-23). `residual_map` measures
    # unexplained P&L, calibration holes and execution anomalies per instrument and publishes a
    # weight per symbol. The scan is BOUNDED by `limit`, so its order IS its allocation: the
    # instruments the desk's own models got most wrong are visited first.
    #
    # ORDER ONLY, NEVER EXCLUSION. Every live symbol stays in the list and the prior's floor is
    # 0.25, because a symbol the models explain today is exactly where an unknown unknown is
    # least visible -- dropping it would be a cap on discovery wearing the word "focus".
    try:
        from research.residual_map import load_prior
        weights, _why = load_prior()
        if weights:
            out.sort(key=lambda s: (-float(weights.get(s, 0.0)), s))
    except Exception:
        pass
    return out[:limit]


def _event_times() -> list[Any]:
    """Macro event instants, if the desk holds a ledger. Absent is UNMEASURED, not 'no events'."""
    out: list[Any] = []
    if not EVENTS.exists():
        return out
    try:
        import pandas as pd
    except ImportError:
        return out
    for ln in EVENTS.read_text(encoding="utf-8", errors="replace").splitlines()[:20000]:
        ln = ln.strip()
        if not ln:
            continue
        try:
            row = json.loads(ln)
        except ValueError:
            continue
        t = row.get("time") or row.get("timestamp") or row.get("at") or row.get("date")
        if t:
            try:
                out.append(pd.to_datetime(t, utc=True, errors="coerce"))
            except Exception:
                continue
    return [t for t in out if t is not None]


def build() -> dict[str, Any]:
    now = datetime.now(tz=UTC)
    try:
        import numpy as np
        import pandas as pd
    except ImportError as exc:
        return {"at": now.isoformat(timespec="seconds"), "status": "UNMEASURED",
                "why": f"numpy/pandas unavailable ({exc})"}

    cells, state = _selected_cells()
    series: dict[tuple[str, str], Any] = {}
    spreads: dict[tuple[str, str], Any] = {}
    for s, tf, _asset in cells:
        p = UNI / f"{s}_{tf}.parquet"
        if not p.exists():
            continue
        try:
            df = pd.read_parquet(p)
        except (OSError, ValueError):
            continue
        col = next((c for c in ("close", "Close", "c") if c in df.columns), None)
        if col is None:
            continue
        px = pd.to_numeric(df[col], errors="coerce")
        px = px[px > 0].tail(BARS)
        if len(px) < 400:
            continue
        series[(s, tf)] = np.log(px).diff().dropna()
        state["bar_watermarks"][f"{s}|{tf}"] = str(px.index[-1])
        spread_col = next((c for c in ("spread", "Spread", "spread_points", "spread_pts")
                           if c in df.columns), None)
        if spread_col is not None:
            spreads[(s, tf)] = pd.to_numeric(df[spread_col], errors="coerce").dropna().tail(BARS)

    if len(series) < 2:
        return {"at": now.isoformat(timespec="seconds"), "status": "UNMEASURED",
                "n_symbols": len({s for s, _tf in series}), "n_cells": len(series),
                "why": "fewer than two live symbols have usable history"}

    events = _event_times()
    anomalies: list[dict[str, Any]] = []

    # 1. UNEXPLAINED MOVES -- extreme bars with no event the desk knows about nearby.
    for (sym, tf), r in series.items():
        if r.empty:
            continue
        thresh = r.abs().quantile(MOVE_Q)
        extreme = r[r.abs() >= thresh]
        for ts, val in extreme.items():
            explained = False
            if events:
                try:
                    t = pd.Timestamp(ts)
                    t = t.tz_localize("UTC") if t.tzinfo is None else t.tz_convert("UTC")
                    explained = any(abs((t - e).total_seconds()) <= EVENT_WINDOW_H * 3600
                                    for e in events)
                except Exception:
                    explained = False
            if not explained:
                anomalies.append({
                    "kind": "unexplained_move", "symbol": sym, "timeframe": tf,
                    "at": str(ts),
                    "return": round(float(val), 6),
                    "sigma": round(float(val / r.std()), 2) if r.std() else None,
                    "question": (
                        f"what mechanism moved {sym} {float(val):+.2%} on {tf} with no "
                        f"macro event within {EVENT_WINDOW_H}h that this desk records?"),
                })

    # 2. DECOUPLINGS -- a relationship the book implicitly sizes on that has stopped holding.
    for tf in TIMEFRAMES:
        tf_series = {s: r for (s, chart), r in series.items() if chart == tf}
        frame = pd.DataFrame(tf_series).dropna()
        if len(frame) <= 600:
            continue
        cols = list(frame.columns)
        recent, hist = frame.tail(300), frame.head(len(frame) - 300)
        for i, a in enumerate(cols):
            for b in cols[i + 1:]:
                try:
                    rc = float(np.corrcoef(recent[a], recent[b])[0, 1])
                    hc = float(np.corrcoef(hist[a], hist[b])[0, 1])
                except Exception:
                    continue
                if abs(rc - hc) >= DECOUPLE_DELTA:
                    anomalies.append({
                        "kind": "decoupling", "symbol": f"{a}|{b}", "timeframe": tf,
                        "recent_corr": round(rc, 3), "historical_corr": round(hc, 3),
                        "delta": round(rc - hc, 3),
                        "question": (f"{a} and {b} on {tf} ran at {hc:+.2f} and now run at "
                                     f"{rc:+.2f}. "
                                     f"What changed -- a participant, a policy, a venue -- and "
                                     f"does the book still hold the bet it thought it held?"),
                    })

    # 3. DISPERSION BREAKS -- a state transition the regime labels did not name.
    for (sym, tf), r in series.items():
        roll = r.rolling(120).std().dropna()
        if len(roll) < 200:
            continue
        band = roll.iloc[:-60].median()
        latest = roll.iloc[-1]
        if band and latest >= band * VOL_BREAK_MULT:
            anomalies.append({
                "kind": "dispersion_break", "symbol": sym, "timeframe": tf,
                "recent_vol": round(float(latest), 6), "band_vol": round(float(band), 6),
                "multiple": round(float(latest / band), 2),
                "question": (f"{sym} {tf} realised vol is "
                             f"{float(latest / band):.1f}x its own band. "
                             f"Which regime is this, and does any label the desk holds name it?"),
            })

    # 4. COST SHOCKS -- the docstring promised this detector, but the old implementation never
    # emitted one.  Use the bar-native spread series only; absent spread data is unmeasured.
    for (sym, tf), spread in spreads.items():
        positive = spread[spread > 0]
        if len(positive) < 100:
            continue
        baseline = float(positive.iloc[:-1].tail(400).median())
        latest = float(positive.iloc[-1])
        if baseline > 0 and latest >= baseline * COST_SHOCK_MULT:
            anomalies.append({
                "kind": "cost_shock", "symbol": sym, "timeframe": tf,
                "at": str(positive.index[-1]), "spread": latest,
                "median_spread": baseline, "multiple": round(latest / baseline, 2),
                "question": (f"{sym} {tf} spread is {latest / baseline:.1f}x its recent median. "
                             "Which liquidity withdrawal or participant constraint caused it, "
                             "and is the execution model conditioned on that state?"),
            })

    # 5. LATENT-STATE NOVELTY -- find joint states outside the historical feature cloud without
    # pre-naming a bull, bear, trend or volatility regime.  This is explicitly a question source;
    # descendants must still supply an economic mechanism before gate one.
    for (sym, tf), r in series.items():
        distance = _latent_features(r, np, pd)
        if distance is None or len(distance) < 100:
            continue
        threshold = float(distance.iloc[:-1].quantile(LATENT_Q))
        latest = float(distance.iloc[-1])
        if threshold > 0 and latest > threshold:
            anomalies.append({
                "kind": "latent_state", "symbol": sym, "timeframe": tf,
                "at": str(distance.index[-1]), "distance": round(latest, 3),
                "historical_q995": round(threshold, 3),
                "question": (f"{sym} {tf} entered a joint return/vol/skew/autocorrelation state "
                             f"{latest / threshold:.1f}x beyond its historical 99.5% boundary. "
                             "What participant constraint or information arrival created a state "
                             "the installed regime labels do not express?"),
            })

    # 6. DIRECTED LEAD-LAG EMERGENCE -- scan a resumable pair slice.  A new predictive ordering
    # is not called causal; it becomes a prompt for causal/event/participant reconstruction.
    for tf in TIMEFRAMES:
        tf_series = {s: r for (s, chart), r in series.items() if chart == tf}
        frame = pd.DataFrame(tf_series).dropna()
        if len(frame) < 700 or len(frame.columns) < 2:
            continue
        recent = frame.tail(250)
        hist = frame.iloc[:-250]
        for leader, follower in _pair_slice(frame, state, tf):
            rc = float(recent[leader].shift(1).corr(recent[follower]))
            hc = float(hist[leader].shift(1).corr(hist[follower]))
            if not np.isfinite(rc) or not np.isfinite(hc):
                continue
            if abs(rc) >= LEAD_MIN and abs(rc - hc) >= LEAD_DELTA:
                anomalies.append({
                    "kind": "directed_emergence", "symbol": f"{leader}->{follower}",
                    "timeframe": tf, "recent_lag1_corr": round(rc, 3),
                    "historical_lag1_corr": round(hc, 3), "delta": round(rc - hc, 3),
                    "question": (f"{leader} has newly begun to lead {follower} on {tf} "
                                 f"({hc:+.2f} -> {rc:+.2f}). Which information, hedge, fixing, "
                                 "inventory or forced-flow path could create that ordering, and "
                                 "does it survive event-time and reverse-direction placebos?"),
                })

    by_kind: dict[str, int] = {}
    for a in anomalies:
        by_kind[a["kind"]] = by_kind.get(a["kind"], 0) + 1
    return {
        "at": now.isoformat(timespec="seconds"),
        "n_symbols": len({s for s, _tf in series}), "n_cells": len(series), "bars": BARS,
        "timeframes_scanned": sorted({tf for _s, tf in series}, key=TIMEFRAMES.index),
        "coverage": {k: state[k] for k in ("available_cells", "sleeve_cells",
                                             "rotating_cells", "frontier_cells", "cursor",
                                             "pair_cursors")},
        "bar_watermarks": dict(state.get("bar_watermarks") or {}),
        "events_known": len(events),
        "n_anomalies": len(anomalies), "by_kind": by_kind,
        "anomalies": anomalies[:150],
        # WITHOUT AN EVENT LEDGER, "UNEXPLAINED" IS NOT A FINDING. Every extreme move is
        # unexplained when the desk knows of no events at all, so the count becomes a measure of
        # volatility rather than of ignorance -- and 128 rows that all say "we have no calendar"
        # is the cry-wolf shape this desk keeps paying for. The verdict says so explicitly and
        # the anomaly kind is downgraded rather than dropped: the moves are real, the INFERENCE
        # that nothing explains them is what is unsupported.
        "events_caveat": (None if events else
                          "NO macro events were parseable, so every extreme move is reported as "
                          "unexplained by construction. `unexplained_move` rows are UNMEASURED "
                          "as anomalies until the event ledger is readable -- fix that first, or "
                          "this queue measures volatility and calls it ignorance."),
        "status": ("UNMEASURED" if (anomalies and not events
                                    and set(by_kind) <= {"unexplained_move"})
                   else "OK" if anomalies else "QUIET"),
        "how_to_use": ("each row is a QUESTION, never an answer. Hand it to a seat as 'what "
                       "mechanism would produce this?' rather than 'invent something' -- the "
                       "desk has no shortage of generators and every one of them proposes from "
                       "inside the ontology it already has."),
        "search_routes": [
            "participant/constraint reconstruction",
            "event-time and revision-aware causal search",
            "cross-asset directed graph and reverse-direction placebo",
            "distant-domain representation transfer",
            "new public sensor/data-source discovery",
            "independent blind rediscovery",
            "search-method mutation and tournament",
        ],
        "why": ("a search that can only recombine what it already represents cannot find what it "
                "has no word for. The observations where the desk's models are WRONG are the only "
                "ones carrying information about the missing word."),
        "boundary": ("nothing here trades, sizes or promotes. Anything a seat proposes from these "
                     "rows faces the identical ten gates as every other candidate."),
        "_state": state,
    }


def _fingerprint(row: dict[str, Any]) -> str:
    identity = {k: row.get(k) for k in
                ("kind", "symbol", "timeframe", "at", "recent_corr", "historical_corr")}
    return hashlib.sha256(json.dumps(identity, sort_keys=True, default=str).encode()).hexdigest()


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--apply", action="store_true")
    a = ap.parse_args(argv)
    doc = build()
    print(f"unknown-unknowns: {doc.get('status')}  {doc.get('n_anomalies', 0)} anomaly(ies) "
          f"across {doc.get('n_symbols', 0)} symbol(s); events known {doc.get('events_known', 0)}")
    for k, v in (doc.get("by_kind") or {}).items():
        print(f"   {k:<20} {v}")
    for row in (doc.get("anomalies") or [])[:5]:
        print(f"   {row['kind']:<18} {row['question'][:110]}")
    if not a.apply:
        print("  --apply not given; nothing written")
        return 0
    state = dict(doc.pop("_state", {}) or {})
    seen = set(state.get("seen") or [])
    fresh = [row for row in (doc.get("anomalies") or []) if _fingerprint(row) not in seen]
    seen.update(_fingerprint(row) for row in fresh)
    state["seen"] = sorted(seen)[-50000:]
    state["updated_at"] = doc["at"]
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps({**doc, "new_anomalies": len(fresh)}, indent=1, default=str),
                   encoding="utf-8")
    STATE.write_text(json.dumps(state, indent=1, default=str), encoding="utf-8")
    QUEUE.parent.mkdir(parents=True, exist_ok=True)
    with QUEUE.open("a", encoding="utf-8") as fh:
        for row in fresh:
            fh.write(json.dumps({"queued_at": doc["at"], **row}, default=str) + "\n")
    print(f"-> {OUT}  (+{len(fresh)} new row(s) -> {QUEUE.name})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
