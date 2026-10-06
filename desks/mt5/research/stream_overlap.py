"""BEHAVIOURAL OVERLAP between two return streams, from their realised daily P&L (breadth law §4,
§12, §15, §16; producer law 15, 16).

Return correlation is one reading of dependence. Two sleeves can carry a modest rho and still lose
on the same days, crash together, trade the same sessions, earn in the same regime or one lead the
other. Each of those is a way the book holds ONE bet while counting two. This module measures six
of them from the daily P&L series the desk already keeps (`alpha_breadth.daily_sleeve_returns`):

    signal     Jaccard of the days each stream is ACTIVE (non-zero P&L): do they trade together
    drawdown   Jaccard of the days each stream sits below its running P&L peak
    co_crash   P(b in its worst decile | a in its worst decile), averaged both ways
    event      Jaccard of the scheduled-EVENT days on which both are active (calendar required)
    regime     cosine of the two streams' mean P&L per volatility regime (lagged, no look-ahead)
    lead_lag   the largest lower-95% |rho| between a(t) and b(t+k), k in +-1..LEAD_LAG_MAX

Every term has a sample floor. Below it the term is UNMEASURED -- never zero, never "independent"
(L1.28a, breadth law §25). `overlap_score` is the LARGEST measured term: one shared failure is
enough to make two streams one bet, and averaging would let an unshared term dilute a shared one.

FACTS ONLY. The certificate-saturation map uses `overlap_score` to revoke structural credit
(a pair at or above OVERLAP_LINK is linked like a dependent pair) and to deny exception F
(measured independence) to a pair that overlaps; the docket stamp caps a matching row's novelty
credit at 1 - score. Ordering and breadth counting only: no gate, trial, verdict, capital or size.
"""
from __future__ import annotations

import json
import math
from collections.abc import Iterable, Mapping
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np

DESK = Path(__file__).resolve().parents[1]
ROOT = DESK.parents[1]
#: The macro event calendar residual_hunt reads (`events[].utc`); absent -> event term UNMEASURED.
EVENT_CALENDAR = ROOT / "data" / "event_calendar.json"
UNMEASURED = "UNMEASURED"
MEASURED = "MEASURED"
TERMS = ("signal", "drawdown", "co_crash", "event", "regime", "lead_lag")

#: PREREGISTERED 2026-10-06, never tuned on which pairs were linked.
MIN_DAYS = 40            # overlapping days a pair needs before any term is read
MIN_ACTIVE = 10          # active days each stream needs for signal / drawdown
MIN_TAIL = 4             # worst-decile days each stream needs for co_crash
MIN_EVENT_DAYS = 5       # calendar event days inside the overlap for the event term
REGIME_LAG = 20          # trailing window of the lagged volatility regime
LEAD_LAG_MAX = 3
#: A pair whose overlap score reaches this is ONE bet for breadth counting.
OVERLAP_LINK = 0.5
#: Exception F (measured independence) is denied to a pair whose overlap score exceeds this.
OVERLAP_INDEPENDENT = 0.3


def _jaccard(a: np.ndarray, b: np.ndarray) -> float | None:
    u = int((a | b).sum())
    return float((a & b).sum()) / u if u else None


def _fisher_lo(rho: float, n: int) -> float:
    if n <= 3 or not math.isfinite(rho):
        return 0.0
    z = math.atanh(max(-0.999999, min(0.999999, abs(rho))))
    return max(0.0, math.tanh(z - 1.96 / math.sqrt(n - 3)))


def event_days(path: Path | None = None) -> set[str] | None:
    """YYYY-MM-DD of every calendar event, or None when no calendar exists (UNMEASURED)."""
    try:
        doc = json.loads((path or EVENT_CALENDAR).read_text("utf-8-sig"))
    except (OSError, ValueError):
        return None
    rows = doc.get("events") if isinstance(doc, dict) else None
    out = {str(r.get("utc") or r.get("ts") or "")[:10] for r in rows or [] if isinstance(r, dict)}
    out.discard("")
    return out or None


def regime_labels(series: Iterable[Mapping[str, float]], lag: int = REGIME_LAG
                  ) -> dict[str, str]:
    """A day's regime = the tercile of the trailing `lag`-day volatility of the equal-weight book,
    measured up to the PREVIOUS day (no look-ahead). Days without a full window are unlabelled."""
    pooled: dict[str, list[float]] = {}
    for s in series:
        for d, v in s.items():
            pooled.setdefault(d, []).append(float(v))
    days = sorted(pooled)
    if len(days) <= lag + 3:
        return {}
    r = np.array([float(np.mean(pooled[d])) for d in days])
    vol = np.full(len(days), np.nan)
    for i in range(lag, len(days)):
        vol[i] = float(np.std(r[i - lag:i]))
    ok = ~np.isnan(vol)
    if ok.sum() < 3:
        return {}
    lo, hi = np.quantile(vol[ok], [1 / 3, 2 / 3])
    return {days[i]: ("low" if vol[i] <= lo else "high" if vol[i] > hi else "mid")
            for i in range(len(days)) if ok[i]}


def pair_overlap(a: Mapping[str, float], b: Mapping[str, float], *,
                 events: set[str] | None = None,
                 regimes: Mapping[str, str] | None = None) -> dict[str, Any]:
    """The six overlap terms for one pair, each MEASURED with its n or UNMEASURED with why."""
    days = sorted(set(a) & set(b))
    out: dict[str, Any] = {"n": len(days)}
    if len(days) < MIN_DAYS:
        out.update(dict.fromkeys(TERMS))
        out["status"] = UNMEASURED
        out["why"] = f"{len(days)} overlapping days < {MIN_DAYS}"
        out["overlap_score"] = None
        return out
    x = np.array([float(a[d]) for d in days])
    y = np.array([float(b[d]) for d in days])
    why: dict[str, str] = {}
    ax, ay = x != 0, y != 0
    out["signal"] = (round(j, 4) if (j := _jaccard(ax, ay)) is not None
                     and ax.sum() >= MIN_ACTIVE and ay.sum() >= MIN_ACTIVE else None)
    if out["signal"] is None:
        why["signal"] = f"fewer than {MIN_ACTIVE} active days"
    cx, cy = np.cumsum(x), np.cumsum(y)
    ddx, ddy = cx < np.maximum.accumulate(cx), cy < np.maximum.accumulate(cy)
    out["drawdown"] = (round(j, 4) if (j := _jaccard(ddx, ddy)) is not None
                       and ddx.sum() >= MIN_ACTIVE and ddy.sum() >= MIN_ACTIVE else None)
    if out["drawdown"] is None:
        why["drawdown"] = f"fewer than {MIN_ACTIVE} drawdown days"
    tx, ty = x <= np.quantile(x, 0.1), y <= np.quantile(y, 0.1)
    tx &= x < 0
    ty &= y < 0
    if tx.sum() >= MIN_TAIL and ty.sum() >= MIN_TAIL:
        out["co_crash"] = round(0.5 * (float((tx & ty).sum()) / tx.sum()
                                       + float((tx & ty).sum()) / ty.sum()), 4)
    else:
        out["co_crash"] = None
        why["co_crash"] = f"fewer than {MIN_TAIL} loss days in a worst decile"
    if events is None:
        out["event"] = None
        why["event"] = "no event calendar on this host"
    else:
        ev = np.array([d in events for d in days])
        if ev.sum() >= MIN_EVENT_DAYS:
            j = _jaccard(ax & ev, ay & ev)
            out["event"] = round(j, 4) if j is not None else 0.0
        else:
            out["event"] = None
            why["event"] = f"{int(ev.sum())} event days in the overlap < {MIN_EVENT_DAYS}"
    if regimes:
        lab = [regimes.get(d) for d in days]
        va, vb = [], []
        for k in ("low", "mid", "high"):
            m = np.array([v == k for v in lab])
            if m.sum() >= MIN_ACTIVE:
                va.append(float(x[m].mean()))
                vb.append(float(y[m].mean()))
        na, nb = math.sqrt(sum(v * v for v in va)), math.sqrt(sum(v * v for v in vb))
        if len(va) >= 2 and na > 0 and nb > 0:
            out["regime"] = round(max(0.0, sum(p * q for p, q in zip(va, vb, strict=True))
                                      / (na * nb)), 4)
        else:
            out["regime"] = None
            why["regime"] = "fewer than two populated regimes"
    else:
        out["regime"] = None
        why["regime"] = "no regime labels"
    best, lag_at = 0.0, None
    for k in range(1, LEAD_LAG_MAX + 1):
        for p, q, sign in ((x[:-k], y[k:], k), (y[:-k], x[k:], -k)):
            if len(p) < MIN_DAYS or p.std() <= 0 or q.std() <= 0:
                continue
            rho = float(np.corrcoef(p, q)[0, 1])
            lo = _fisher_lo(rho, len(p))
            if lo > best:
                best, lag_at = lo, sign
    if x.std() > 0 and y.std() > 0:
        out["lead_lag"] = round(best, 4)
        out["lead_lag_k"] = lag_at
    else:
        out["lead_lag"] = None
        why["lead_lag"] = "a constant stream"
    vals = [float(out[t]) for t in TERMS if out.get(t) is not None]
    out["overlap_score"] = round(max(vals), 4) if vals else None
    out["binding_term"] = (max((t for t in TERMS if out.get(t) is not None),
                               key=lambda t: float(out[t])) if vals else None)
    out["status"] = MEASURED if vals else UNMEASURED
    if why:
        out["why"] = why
    return out


def book_overlap(daily: Mapping[str, Mapping[str, float]], *,
                 events: set[str] | None = None) -> dict[str, Any]:
    """Every pair's overlap, and each stream's WORST overlap with the rest of the book."""
    names = sorted(k for k, v in daily.items() if v)
    if events is None:
        events = event_days()
    regimes = regime_labels(daily[n] for n in names)
    pairs: dict[tuple[str, str], dict[str, Any]] = {}
    worst: dict[str, dict[str, Any]] = {}
    for i, a in enumerate(names):
        for b in names[i + 1:]:
            o = pair_overlap(daily[a], daily[b], events=events, regimes=regimes)
            pairs[(a, b)] = o
            s = o.get("overlap_score")
            if s is None:
                continue
            for me, other in ((a, b), (b, a)):
                if s > float((worst.get(me) or {}).get("overlap_score") or -1.0):
                    worst[me] = {"overlap_score": s, "with": other,
                                 "binding_term": o.get("binding_term"), "n": o["n"]}
    measured = sum(1 for o in pairs.values() if o.get("status") == MEASURED)
    by_term = {t: sum(1 for o in pairs.values() if o.get(t) is not None) for t in TERMS}
    return {"status": MEASURED if measured else UNMEASURED,
            "at": datetime.now(tz=UTC).isoformat(timespec="seconds"),
            "n_streams": len(names), "n_pairs": len(pairs), "n_pairs_measured": measured,
            "terms_measured": by_term, "event_calendar": events is not None,
            "n_linked": sum(1 for o in pairs.values()
                            if (o.get("overlap_score") or 0.0) >= OVERLAP_LINK),
            "stream_worst": worst, "pairs": pairs,
            "rule": (f"overlap_score = max measured term; >= {OVERLAP_LINK} links a pair as one "
                     f"bet; > {OVERLAP_INDEPENDENT} denies exception F. Floors: {MIN_DAYS} days, "
                     f"{MIN_ACTIVE} active, {MIN_TAIL} tail, {MIN_EVENT_DAYS} event days")}


__all__ = ["MEASURED", "OVERLAP_INDEPENDENT", "OVERLAP_LINK", "TERMS", "UNMEASURED",
           "book_overlap", "event_days", "pair_overlap", "regime_labels"]
