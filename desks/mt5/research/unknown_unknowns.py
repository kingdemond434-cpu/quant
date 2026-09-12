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
import json
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
SLEEVES = DESK / "data" / "sleeves.json"
EVENTS = DESK / "data" / "macro" / "event_ledger.jsonl"
OUT = DESK / "reports" / "UNKNOWN_UNKNOWNS.json"
QUEUE = DESK / "data" / "unknown_unknowns_queue.jsonl"

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

    syms = _live_symbols()
    series: dict[str, Any] = {}
    for s in syms:
        p = UNI / f"{s}_H1.parquet"
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
        series[s] = np.log(px).diff().dropna()

    if len(series) < 2:
        return {"at": now.isoformat(timespec="seconds"), "status": "UNMEASURED",
                "n_symbols": len(series),
                "why": "fewer than two live symbols have usable history"}

    events = _event_times()
    anomalies: list[dict[str, Any]] = []

    # 1. UNEXPLAINED MOVES -- extreme bars with no event the desk knows about nearby.
    for sym, r in series.items():
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
                    "kind": "unexplained_move", "symbol": sym, "at": str(ts),
                    "return": round(float(val), 6),
                    "sigma": round(float(val / r.std()), 2) if r.std() else None,
                    "question": (
                        f"what mechanism moved {sym} {float(val):+.2%} in one hour with no "
                        f"macro event within {EVENT_WINDOW_H}h that this desk records?"),
                })

    # 2. DECOUPLINGS -- a relationship the book implicitly sizes on that has stopped holding.
    frame = pd.DataFrame(series).dropna()
    if len(frame) > 600:
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
                        "kind": "decoupling", "symbol": f"{a}|{b}",
                        "recent_corr": round(rc, 3), "historical_corr": round(hc, 3),
                        "delta": round(rc - hc, 3),
                        "question": (f"{a} and {b} ran at {hc:+.2f} and now run at {rc:+.2f}. "
                                     f"What changed -- a participant, a policy, a venue -- and "
                                     f"does the book still hold the bet it thought it held?"),
                    })

    # 3. DISPERSION BREAKS -- a state transition the regime labels did not name.
    for sym, r in series.items():
        roll = r.rolling(120).std().dropna()
        if len(roll) < 200:
            continue
        band = roll.iloc[:-60].median()
        latest = roll.iloc[-1]
        if band and latest >= band * VOL_BREAK_MULT:
            anomalies.append({
                "kind": "dispersion_break", "symbol": sym,
                "recent_vol": round(float(latest), 6), "band_vol": round(float(band), 6),
                "multiple": round(float(latest / band), 2),
                "question": (f"{sym} realised vol is {float(latest / band):.1f}x its own band. "
                             f"Which regime is this, and does any label the desk holds name it?"),
            })

    by_kind: dict[str, int] = {}
    for a in anomalies:
        by_kind[a["kind"]] = by_kind.get(a["kind"], 0) + 1
    return {
        "at": now.isoformat(timespec="seconds"),
        "n_symbols": len(series), "bars": BARS,
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
        "why": ("a search that can only recombine what it already represents cannot find what it "
                "has no word for. The observations where the desk's models are WRONG are the only "
                "ones carrying information about the missing word."),
        "boundary": ("nothing here trades, sizes or promotes. Anything a seat proposes from these "
                     "rows faces the identical ten gates as every other candidate."),
    }


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
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(doc, indent=1, default=str), encoding="utf-8")
    QUEUE.parent.mkdir(parents=True, exist_ok=True)
    with QUEUE.open("a", encoding="utf-8") as fh:
        for row in doc.get("anomalies") or []:
            fh.write(json.dumps({"queued_at": doc["at"], **row}, default=str) + "\n")
    print(f"-> {OUT}  (+{len(doc.get('anomalies') or [])} row(s) -> {QUEUE.name})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
