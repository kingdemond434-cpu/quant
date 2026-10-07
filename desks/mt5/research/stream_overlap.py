"""BEHAVIOURAL OVERLAP between two return streams, from their realised daily P&L (breadth law §4,
§12, §15, §16; producer law 15, 16).

Return correlation is one reading of dependence. Two sleeves can carry a modest rho and still lose
on the same days, crash together, trade the same sessions, earn in the same regime or one lead the
other. Each of those is a way the book holds ONE bet while counting two. This module measures six
of them from the daily P&L series the desk already keeps (`alpha_breadth.daily_sleeve_returns`):

    signal     association of the days each stream is ACTIVE (non-zero P&L)
    drawdown   association of the days each stream sits below its running P&L peak
    co_crash   association of each stream's worst-decile loss days
    event      |rho| of the two streams on scheduled-EVENT days (calendar required)
    regime     the largest |rho| inside one lagged-volatility regime (no look-ahead)
    lead_lag   the largest |rho| between a(t) and b(t+k), k in +-1..LEAD_LAG_MAX

EVERY TERM IS A LOWER 95% BOUND and is zero in expectation for independent streams. Indicator
terms use the phi association on an n discounted by the mean run length, because a drawdown that
lasts a month is one observation; a raw Jaccard would score two always-active or two random-walk
streams near 1 by construction.

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


def _runs(x: np.ndarray) -> float:
    """Mean run length of a boolean series (>= 1): the autocorrelation discount on its n."""
    if x.size == 0:
        return 1.0
    changes = int((x[1:] != x[:-1]).sum()) + 1
    return max(1.0, x.size / changes)


def _assoc_lo(a: np.ndarray, b: np.ndarray, min_true: int) -> float | None:
    """Lower 95% bound of the phi association of two day-indicators, on an n discounted by the
    longer mean run (a drawdown lasting weeks is one observation, not twenty). Zero in
    expectation for independent streams, unlike a raw Jaccard, which a pair of always-active or
    always-underwater streams would max out by construction. None below the floors."""
    if int(a.sum()) < min_true or int(b.sum()) < min_true \
            or int((~a).sum()) < min_true or int((~b).sum()) < min_true:
        return None
    x, y = a.astype(float), b.astype(float)
    if x.std() <= 0 or y.std() <= 0:
        return None
    phi = float(np.corrcoef(x, y)[0, 1])
    if not math.isfinite(phi) or phi <= 0:
        return 0.0
    n_eff = int(a.size / max(_runs(a), _runs(b)))
    return _fisher_lo(phi, n_eff)


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


#: THE BEHAVIOURAL PROFILE (breadth law, BREADTH-0420/0421/0426/0434/0435/0437/0438). These are
#: DISTANCES between what two streams look like, not dependence: two independent daily holders
#: share a holding-time distribution by construction, so none of these may enter
#: `overlap_score` (which links pairs as one bet). They feed the novelty/behavioural vector only.
PROFILE = ("holding_time_ks", "turnover_gap", "spectral_distance", "factor_residual_distance",
           "information_source_distance", "mechanism_distance")
#: spectral bands in days per cycle: short (2-5), medium (5-20), long (>20)
SPECTRAL_BANDS = ((2.0, 5.0), (5.0, 20.0), (20.0, float("inf")))
MIN_RUNS = 5


def _active_runs(x: np.ndarray) -> np.ndarray:
    """Lengths of consecutive active (non-zero) day runs: the holding-time distribution."""
    out, n = [], 0
    for v in x != 0:
        if v:
            n += 1
        elif n:
            out.append(n)
            n = 0
    if n:
        out.append(n)
    return np.asarray(out, dtype=float)


def _ks(a: np.ndarray, b: np.ndarray) -> float:
    grid = np.union1d(a, b)
    fa = np.searchsorted(np.sort(a), grid, side="right") / a.size
    fb = np.searchsorted(np.sort(b), grid, side="right") / b.size
    return float(np.max(np.abs(fa - fb)))


def _band_shares(x: np.ndarray) -> np.ndarray | None:
    if x.size < 2 * MIN_DAYS // 2 or x.std() <= 0:
        return None
    f = np.fft.rfftfreq(x.size, d=1.0)[1:]
    pw = (np.abs(np.fft.rfft(x - x.mean())) ** 2)[1:]
    period = 1.0 / f
    sh = np.array([pw[(period >= lo) & (period < hi)].sum() for lo, hi in SPECTRAL_BANDS])
    tot = sh.sum()
    return sh / tot if tot > 0 else None


def profile_distance(x: np.ndarray, y: np.ndarray, common: np.ndarray | None = None
                     ) -> dict[str, Any]:
    """Holding-time KS, turnover gap, spectral distance and factor-residual distance of two
    aligned daily series; each None with its reason below its floor."""
    out: dict[str, Any] = {}
    why: dict[str, str] = {}
    ra, rb = _active_runs(x), _active_runs(y)
    if ra.size >= MIN_RUNS and rb.size >= MIN_RUNS:
        out["holding_time_ks"] = round(_ks(ra, rb), 4)
    else:
        out["holding_time_ks"] = None
        why["holding_time_ks"] = f"fewer than {MIN_RUNS} holding runs on a side"
    # turnover: entries per active day (a new run starts) -- how often the stream re-trades
    ta = ra.size / max(1, int((x != 0).sum())) if ra.size else None
    tb = rb.size / max(1, int((y != 0).sum())) if rb.size else None
    out["turnover_gap"] = round(abs(ta - tb), 4) if ta is not None and tb is not None else None
    if out["turnover_gap"] is None:
        why["turnover_gap"] = "a stream with no active day"
    sa, sb = _band_shares(x), _band_shares(y)
    out["spectral_distance"] = (round(0.5 * float(np.abs(sa - sb).sum()), 4)
                                if sa is not None and sb is not None else None)
    if out["spectral_distance"] is None:
        why["spectral_distance"] = "a constant or too-short stream"
    if common is not None and common.std() > 0 and x.std() > 0 and y.std() > 0:
        ex = x - np.polyval(np.polyfit(common, x, 1), common)
        ey = y - np.polyval(np.polyfit(common, y, 1), common)
        if ex.std() > 0 and ey.std() > 0:
            lo = _fisher_lo(float(np.corrcoef(ex, ey)[0, 1]), x.size)
            out["factor_residual_distance"] = round(1.0 - lo, 4)
    if out.get("factor_residual_distance") is None:
        out["factor_residual_distance"] = None
        why["factor_residual_distance"] = "no common book factor or a constant residual"
    if why:
        out["why"] = why
    return out


def pair_overlap(a: Mapping[str, float], b: Mapping[str, float], *,
                 events: set[str] | None = None,
                 regimes: Mapping[str, str] | None = None,
                 common: Mapping[str, float] | None = None) -> dict[str, Any]:
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
    out["signal"] = _assoc_lo(ax, ay, MIN_ACTIVE)
    if out["signal"] is None:
        why["signal"] = (f"fewer than {MIN_ACTIVE} active AND {MIN_ACTIVE} idle days on a side "
                         "(an always-active stream carries no timing information)")
    cx, cy = np.cumsum(x), np.cumsum(y)
    ddx, ddy = cx < np.maximum.accumulate(cx), cy < np.maximum.accumulate(cy)
    out["drawdown"] = _assoc_lo(ddx, ddy, MIN_ACTIVE)
    if out["drawdown"] is None:
        why["drawdown"] = f"fewer than {MIN_ACTIVE} days in and out of drawdown on a side"
    tx = (x <= np.quantile(x, 0.1)) & (x < 0)
    ty = (y <= np.quantile(y, 0.1)) & (y < 0)
    out["co_crash"] = _assoc_lo(tx, ty, MIN_TAIL)
    if out["co_crash"] is None:
        why["co_crash"] = f"fewer than {MIN_TAIL} loss days in a worst decile"
    if events is None:
        out["event"] = None
        why["event"] = "no event calendar on this host"
    else:
        ev = np.array([d in events for d in days])
        if ev.sum() >= MIN_EVENT_DAYS:
            xe, ye = x[ev], y[ev]
            if len(xe) > 3 and xe.std() > 0 and ye.std() > 0:
                out["event"] = round(_fisher_lo(float(np.corrcoef(xe, ye)[0, 1]), len(xe)), 4)
            else:
                out["event"] = None
                why["event"] = "a constant stream on event days"
        else:
            out["event"] = None
            why["event"] = f"{int(ev.sum())} event days in the overlap < {MIN_EVENT_DAYS}"
    if regimes:
        lab = [regimes.get(d) for d in days]
        best_r: float | None = None
        for k in ("low", "mid", "high"):
            m = np.array([v == k for v in lab])
            if m.sum() >= MIN_DAYS // 2 and x[m].std() > 0 and y[m].std() > 0:
                lo = _fisher_lo(float(np.corrcoef(x[m], y[m])[0, 1]), int(m.sum()))
                best_r = lo if best_r is None else max(best_r, lo)
        out["regime"] = round(best_r, 4) if best_r is not None else None
        if best_r is None:
            why["regime"] = f"no regime with {MIN_DAYS // 2} overlapping days"
    else:
        out["regime"] = None
        why["regime"] = "no regime labels"
    for t in ("signal", "drawdown", "co_crash"):
        if out[t] is not None:
            out[t] = round(float(out[t]), 4)
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
    cm = (np.array([float(common.get(d, 0.0)) for d in days])
          if common is not None and all(d in common for d in days) else None)
    out["profile"] = profile_distance(x, y, cm)
    vals = [float(out[t]) for t in TERMS if out.get(t) is not None]
    out["overlap_score"] = round(max(vals), 4) if vals else None
    out["binding_term"] = (max((t for t in TERMS if out.get(t) is not None),
                               key=lambda t: float(out[t])) if vals else None)
    out["status"] = MEASURED if vals else UNMEASURED
    if why:
        out["why"] = why
    return out


def _identity(label: str) -> tuple[str, str] | None:
    """(mechanism, information source) of a sleeve label, from the family registry; None when
    the family is not registered."""
    try:
        try:
            from research import axis_registry as ar
            from research import certificate_saturation as cs
        except ImportError:                                              # pragma: no cover
            import axis_registry as ar  # type: ignore[import-not-found,no-redef]
            import certificate_saturation as cs  # type: ignore[import-not-found,no-redef]
        _sym, fam, _sess = cs.sleeve_identity(str(label))
        mech, info, _ = ar.classify_family(fam)
    except Exception:
        return None
    return None if mech == ar.UNKNOWN else (str(mech), str(info))


def book_overlap(daily: Mapping[str, Mapping[str, float]], *,
                 events: set[str] | None = None) -> dict[str, Any]:
    """Every pair's overlap, and each stream's WORST overlap with the rest of the book."""
    names = sorted(k for k, v in daily.items() if v)
    if events is None:
        events = event_days()
    regimes = regime_labels(daily[n] for n in names)
    pooled: dict[str, list[float]] = {}
    for n in names:
        for d, v in daily[n].items():
            pooled.setdefault(d, []).append(float(v))
    common = {d: float(np.mean(v)) for d, v in pooled.items()}
    ident = {n: _identity(n) for n in names}
    pairs: dict[tuple[str, str], dict[str, Any]] = {}
    worst: dict[str, dict[str, Any]] = {}
    for i, a in enumerate(names):
        for b in names[i + 1:]:
            o = pair_overlap(daily[a], daily[b], events=events, regimes=regimes, common=common)
            if "profile" in o:
                for key, axis in (("information_source_distance", 1),
                                  ("mechanism_distance", 0)):
                    ia, ib = ident[a], ident[b]
                    o["profile"][key] = (None if ia is None or ib is None
                                         else float(ia[axis] != ib[axis]))
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


__all__ = ["MEASURED", "OVERLAP_INDEPENDENT", "OVERLAP_LINK", "PROFILE", "TERMS", "UNMEASURED",
           "book_overlap", "event_days", "pair_overlap", "profile_distance", "regime_labels"]
