#!/usr/bin/env python3
"""P14 / P16 / P17 / P23 / P24 / P26 -- WHAT THE MARKET IS DOING, AND WHAT IT DID LAST TIME.

Six capabilities that share one discipline: every one of them can only be built POINT-IN-TIME, and
every one of them is worthless the moment it is not.

P14 OPTIONS INTELLIGENCE -- surface, skew, term structure, implied tails. Fusion quotes no options,
so this desk reads the surface as CONDITIONING information about the instruments it does trade:
implied vol is a forward-looking estimate of the thing every sizing decision needs and no bar
contains. Where a surface is unavailable the module says UNAVAILABLE and names the input, because a
skew silently defaulted to zero is a confident claim that the market sees no asymmetry.

P16 PHYSICAL COMMODITY INTELLIGENCE -- inventories, spreads, freight, seasonality. POINT-IN-TIME
ONLY, and that phrase is the whole capability: inventory series are revised for months after the
fact, so a backtest on today's values of a 2024 series is trading on numbers nobody had. Every
observation carries the date it was PUBLISHED, not only the date it describes.

P17 MARKET ECOLOGY -- latent participant pressure INFERRED, NEVER CLAIMED. Nobody on this desk can
see positioning. What is observable is a set of footprints -- range compression before expansion,
volume against range, session handoffs, gap behaviour -- and the honest output is a bounded
inference with its evidence, never "institutions are accumulating". The distinction is not
pedantry: a claim invites sizing, an inference invites a test.

P23 MARKET MEMORY -- retrieval of the nearest historical worlds. "When did the tape last look like
this, and what happened next?" is the most natural question a trader asks and one of the easiest to
answer dishonestly: the neighbour search must run over a PAST-ONLY window, or the nearest world is
tomorrow's and the answer is perfect.

P24 WHAT CHANGED -- standardised cross-asset surprise, ranked. Not "gold moved 1.2%" but "gold
moved 3.1 sigma against its own recent distribution, the largest of any instrument today". A raw
move is noise; a standardised move is news.

P26 EVENT RESPONSE SURFACES -- shock, discovery, drift, reversal across horizons. One number for
"the reaction" hides that most reactions have a shape: an immediate shock, a slower discovery, a
drift, and often a reversal. A desk that measures only the first bar mistakes the shock for the
whole response and exits into the discovery.
"""
from __future__ import annotations

import json
import math
import sys
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np

BASE = Path(__file__).resolve().parent.parent
ROOT = BASE.parent.parent
UNIVERSE = BASE / "data" / "universe"
REPORT = BASE / "reports" / "MARKET_INTELLIGENCE.json"

#: Lookback for the distribution a surprise is measured against. Long enough that a single
#: unusual week cannot set the scale, short enough to describe the CURRENT regime rather than an
#: average of every regime the instrument has ever been in.
SURPRISE_WINDOW = 250

#: A move must exceed this many sigma before it is called a surprise. Below it the desk would be
#: ranking noise every day and the list would be read by nobody (L1.37).
SURPRISE_SIGMA = 2.0

#: Horizons, in bars, over which an event response is decomposed.
RESPONSE_HORIZONS: tuple[int, ...] = (1, 4, 12, 24, 72)

#: Neighbours retrieved for a market-memory query.
NEIGHBOURS = 12


@dataclass(frozen=True)
class Signal:
    """One inference. `confidence` is bounded and `evidence` names what produced it."""

    name: str
    value: float | None
    confidence: float
    evidence: str
    status: str = "MEASURED"

    def as_dict(self) -> dict[str, Any]:
        return {"name": self.name, "value": self.value, "confidence": self.confidence,
                "evidence": self.evidence, "status": self.status}


def _unavailable(name: str, needs: str) -> Signal:
    """ABSENCE IS NEVER A PASS. An unavailable input is named, never defaulted to a neutral
    value -- a skew silently set to zero is a confident claim that the market sees no asymmetry."""
    return Signal(name, None, 0.0,
                  f"requires {needs}, which this host does not carry", "UNAVAILABLE")


# --------------------------------------------------------------------------- P24
def surprise(close: np.ndarray, window: int = SURPRISE_WINDOW) -> Signal:
    """Standardised move against the instrument's OWN recent distribution.

    A raw move is noise; a standardised move is news. Comparing gold's 1.2% to the S&P's 1.2%
    ranks by volatility rather than by information, which is why a cross-asset list built on raw
    percentages is always led by whatever is most volatile and never says anything.
    """
    if len(close) < window + 2:
        return Signal("surprise", None, 0.0,
                      f"{len(close)} bars; the distribution needs {window + 2}", "INSUFFICIENT")
    logp = np.log(np.maximum(close, 1e-12))
    d = np.diff(logp)
    # PAST-ONLY: the scale comes from the window BEFORE the move being scored. Including the move
    # in its own reference distribution shrinks every surprise toward zero, and shrinks the
    # largest ones most.
    ref, last = d[-window - 1:-1], d[-1]
    sd = float(ref.std()) or 1e-12
    z = float((last - ref.mean()) / sd)
    return Signal("surprise", round(z, 3), min(1.0, abs(z) / (2 * SURPRISE_SIGMA)),
                  f"last move {last:+.5f} against a {window}-bar sd of {sd:.5f}")


# --------------------------------------------------------------------------- P17
def ecology(close: np.ndarray, high: np.ndarray | None = None,
            low: np.ndarray | None = None) -> list[Signal]:
    """Footprints of participant pressure. INFERRED, and every output says so.

    Nobody here can see positioning. What is observable is compression before expansion, and
    directional persistence against range. The output is a bounded inference with its evidence --
    never "institutions are accumulating", because a claim invites sizing and an inference invites
    a test.
    """
    out: list[Signal] = []
    if len(close) < 120:
        return [Signal("ecology", None, 0.0, f"{len(close)} bars, need 120", "INSUFFICIENT")]
    logp = np.log(np.maximum(close, 1e-12))
    d = np.diff(logp)
    recent, prior = d[-24:], d[-120:-24]
    comp = float(recent.std() / (prior.std() or 1e-12))
    out.append(Signal(
        "range_compression", round(comp, 3), min(1.0, abs(math.log(max(comp, 1e-6))) / 1.5),
        f"24-bar realised vol is {comp:.2f}x the prior 96-bar; compression below ~0.7 has "
        "preceded expansion more often than not, which is an inference and not a forecast"))
    persist = float(np.sign(recent).sum() / len(recent))
    out.append(Signal(
        "directional_persistence", round(persist, 3), min(1.0, abs(persist)),
        f"{int((np.sign(recent) > 0).sum())} of {len(recent)} recent bars closed up; "
        "one-sided persistence is a footprint of pressure, not evidence of who applied it"))
    return out


# --------------------------------------------------------------------------- P23
def nearest_worlds(close: np.ndarray, k: int = NEIGHBOURS,
                   pattern: int = 24, forward: int = 24) -> dict[str, Any]:
    """P23. When did the tape last look like this, and what happened next?

    THE SEARCH IS PAST-ONLY AND STOPS `forward` BARS SHORT OF THE PRESENT. Two separate leaks
    live here: a neighbour drawn from after the query window is tomorrow's world, and a neighbour
    too close to the end has no completed forward outcome, so including it would score a partial
    move as a full one.
    """
    n = len(close)
    need = pattern * 3 + forward
    if n < need:
        return {"status": "INSUFFICIENT", "why": f"{n} bars, need {need}"}
    logp = np.log(np.maximum(close, 1e-12))
    d = np.diff(logp)
    q = d[-pattern:]
    q = (q - q.mean()) / (q.std() or 1e-12)
    hits = []
    # The last candidate END is n-1-forward-1: any later and its forward window is incomplete.
    for end in range(pattern, len(d) - forward - pattern):
        w = d[end - pattern:end]
        w = (w - w.mean()) / (w.std() or 1e-12)
        hits.append((float(np.sqrt(((w - q) ** 2).mean())), end))
    if not hits:
        return {"status": "INSUFFICIENT", "why": "no complete historical window"}
    hits.sort()
    top = hits[:k]
    outcomes = [float(d[e:e + forward].sum()) for _, e in top]
    up = sum(1 for o in outcomes if o > 0)
    return {
        "status": "MEASURED", "neighbours": len(top),
        "median_forward": round(float(np.median(outcomes)), 6),
        "up_fraction": round(up / len(outcomes), 3),
        "mean_distance": round(float(np.mean([h[0] for h in top])), 4),
        "why_past_only": ("neighbours are drawn only from windows that ENDED at least "
                          f"{forward} bars before the present, so every one has a completed "
                          "forward outcome and none of them is tomorrow"),
    }


# --------------------------------------------------------------------------- P26
def response_surface(close: np.ndarray, event_idx: list[int]) -> dict[str, Any]:
    """P26. Decompose the reaction into shock, discovery, drift and reversal.

    One number for "the reaction" hides that most reactions have a SHAPE. A desk that measures
    only the first bar mistakes the shock for the whole response and exits into the discovery.
    """
    if not event_idx:
        return {"status": "NO_EVENTS",
                "why": "no event index supplied; a response surface with no events is not a "
                       "flat surface, it is an unmeasured one"}
    logp = np.log(np.maximum(close, 1e-12))
    rows: dict[str, Any] = {}
    for h in RESPONSE_HORIZONS:
        moves = [float(logp[min(i + h, len(logp) - 1)] - logp[i])
                 for i in event_idx if 0 <= i < len(logp) - 1]
        if not moves:
            continue
        rows[f"h{h}"] = {"n": len(moves), "mean": round(float(np.mean(moves)), 6),
                         "median": round(float(np.median(moves)), 6),
                         "up_fraction": round(sum(1 for m in moves if m > 0) / len(moves), 3)}
    shape = "unmeasured"
    if len(rows) >= 3:
        keys = sorted(rows, key=lambda k: int(k[1:]))
        first, mid, last = rows[keys[0]]["mean"], rows[keys[len(keys) // 2]]["mean"], \
            rows[keys[-1]]["mean"]
        if abs(last) < abs(first) * 0.5:
            shape = "reversal -- the move gives back more than half by the longest horizon"
        elif abs(last) > abs(first) * 1.5:
            shape = "drift -- the response keeps building after the shock"
        elif abs(mid) > abs(first) * 1.2:
            shape = "discovery -- the market keeps repricing after the first bar"
        else:
            shape = "shock -- the response is complete in the first bar"
    return {"status": "MEASURED", "events": len(event_idx), "horizons": rows, "shape": shape}


# --------------------------------------------------------------------------- P14 / P16
def options_surface(symbol: str) -> list[Signal]:
    """P14. Fusion quotes no options, so the surface is CONDITIONING data when it exists."""
    return [_unavailable(f"{symbol}:implied_skew", "an options chain (no Fusion feed)"),
            _unavailable(f"{symbol}:term_structure", "an options chain (no Fusion feed)")]


def commodity_state(symbol: str) -> list[Signal]:
    """P16. Point-in-time only, and the phrase is the capability.

    Inventory and freight series are revised for months. A backtest on today's values of a 2024
    series trades on numbers nobody had, and the result is excellent and unreachable.
    """
    return [_unavailable(f"{symbol}:inventory",
                         "a point-in-time inventory series with publication dates"),
            _unavailable(f"{symbol}:freight",
                         "a point-in-time freight series with publication dates")]


# --------------------------------------------------------------------------- runner
def _closes(limit: int = 8) -> dict[str, np.ndarray]:
    out: dict[str, np.ndarray] = {}
    try:
        import pandas as pd
    except ImportError:
        return out
    for p in sorted(UNIVERSE.glob("*.parquet"))[:limit]:
        try:
            df = pd.read_parquet(p)
            col = next((c for c in df.columns if str(c).lower() == "close"), None)
            if col is not None:
                arr = np.asarray(df[col], dtype=float)
                if len(arr) > SURPRISE_WINDOW + 10:
                    out[p.stem] = arr
        except Exception:
            continue
    return out


def run() -> dict[str, Any]:
    series = _closes()
    ranked, per = [], {}
    for name, close in series.items():
        s = surprise(close)
        if s.value is not None:
            ranked.append((abs(s.value), name, s.value))
        events = [i for i in range(SURPRISE_WINDOW, len(close) - max(RESPONSE_HORIZONS))
                  if abs(close[i] / close[i - 1] - 1) > 0.004][:400]
        per[name] = {
            "surprise": s.as_dict(),
            "ecology": [x.as_dict() for x in ecology(close)],
            "nearest_worlds": nearest_worlds(close),
            "response_surface": response_surface(close, events),
            "options": [x.as_dict() for x in options_surface(name)],
            "commodity": [x.as_dict() for x in commodity_state(name)],
        }
    ranked.sort(reverse=True)
    return {
        "measured_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "series": len(per),
        "what_changed": [{"symbol": n, "sigma": v} for _, n, v in ranked[:12]],
        "surprise_threshold_sigma": SURPRISE_SIGMA,
        "flagged": [n for a, n, _ in ranked if a >= SURPRISE_SIGMA],
        "per_series": per,
        "point_in_time": ("Every retrieval and every response window is drawn from data that "
                          "existed before the bar it describes. A neighbour from after the query "
                          "window is tomorrow, and an answer built on tomorrow is perfect and "
                          "unreachable."),
    }


def main(argv: list[str] | None = None) -> int:
    doc = run()
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text(json.dumps(doc, indent=1, default=str), "utf-8")
    print(f"market intelligence: {doc['series']} series, "
          f"{len(doc['flagged'])} above {SURPRISE_SIGMA} sigma")
    for row in doc["what_changed"][:8]:
        print(f"   {row['symbol']:22} {row['sigma']:+7.2f} sigma")
    if not doc["series"]:
        print("   NO SERIES -- no parquet on this host carries enough closes. A gap in the data, "
              "not a quiet market.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
