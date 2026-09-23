"""THE FEED / CLOCK / INFORMATION-PROPAGATION OBSERVATORY -- market data as a sensor network.

WHY. Every organ on this desk reads a price as if it were the market. It is not: it is the last
message a chain of clocks let through, and the chain has five clocks that are never the same
instant -- the SOURCE event (the instant the world changed), the EXCHANGE stamp (the venue's own
`time_msc`), the VENDOR receipt (the terminal's), the LOCAL receipt (this box's `recv_utc`) and,
for anything reconstructed across venues, an IMPLIED time that is only as fresh as its stalest
leg. `latency_lab` measures what the desk's OWN order takes to travel; this module measures what
the desk's PICTURE of the market is worth at the instant it decides -- and which instrument's
move can be said to precede which, given that the clocks cannot resolve every lag.

WHAT IS MEASURED, and from what:

    latency_distribution     local - exchange, per feed; negatives KEPT and counted (a broker
                             clock ahead of this box is a fact about the clocks, not noise)
    sequence_continuity      inversions / duplicates / dropped numbers where a sequence exists;
                             MT5 ticks carry none, so drops there are a PROXY and say so
    staleness_probability    P(the quote is older than its age) from the feed's own in-session
                             inter-arrival gaps -- a survival function, never a threshold
    reference_consistency    two views of one instrument (tape mid vs bar close) at every
                             candidate lag: the best lag IS the clock offset, the residual is
                             the disagreement in bps
    feed_health              P(observed market is trustworthy | all feeds): per feed a PRODUCT
                             of component probabilities, across feeds a geometric mean over the
                             feeds that are in session -- a closed market is EXCLUDED, never 0
    propagation_graph        which instrument's move can precede which at what lag: an edge at
                             lag L is causally ADMISSIBLE only when L exceeds what the two
                             clocks can jointly resolve (|offset_a - offset_b| + jitter_a +
                             jitter_b); below that the ordering is not identifiable and the
                             graph REFUSES the edge rather than ranking it
    timing_fragility         a signal re-measured under realistic timing corruption (jitter,
                             dropped messages, stale quotes, sequence inversions) at the
                             MEASURED noise level and at 10x and 100x; a candidate whose edge
                             halves at the measured level is TIMING_FRAGILE

EVERYTHING HERE IS PURE. No file, no clock, no desk path: the organ (`desks/mt5/research/
feed_clock_lab.py`) reads the tape and the bars and hands arrays in, so every function can be
tested on a planted feed. UNMEASURED is a value in every return (L1.28a): a feed with too few
ticks to establish a gap distribution has no staleness probability, and saying so is the
measurement.

IT ROUTES AND INFORMS; IT NEVER SIZES. Feed health is an INPUT to entry timing and to research
routing (GROWTH_GOVERNANCE Rule 1: nothing here is a cap, a veto or a shrink).
"""
from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any

import numpy as np
from numpy.typing import NDArray

FloatArray = NDArray[np.float64]

UNMEASURED = "UNMEASURED"
MEASURED = "MEASURED"
#: The five clocks, in the order a message travels. `implied` is not on the path: it is a
#: reconstruction and is carried apart so it can never be mistaken for a receipt.
CLOCKS: tuple[str, ...] = ("source_event", "exchange", "vendor_receipt", "local_receipt",
                           "implied")
#: Below this many observations a distribution is a sample, and a probability is not one.
MIN_OBS = 30
#: A feed whose age exceeds this multiple of its own p99 in-session gap is not stale, it is
#: CLOSED (or the recorder is down) -- excluded from health by name rather than scored 0.
CLOSED_GAP_MULTIPLE = 3.0
#: Floor on the closed threshold so a thin feed is not declared closed by one quiet minute.
CLOSED_FLOOR_MS = 300_000.0
#: A silence burst this many times the median gap is the drop PROXY on a feed without sequence
#: numbers: it is where dropped messages would hide, and it is named a proxy in every output.
BURST_MULTIPLE = 10.0
#: An edge keeps this share of its clean value or it is fragile.
SURVIVAL_FRACTION = 0.5
#: The corruption ladder: measured noise, then an order of magnitude and two above it.
MULTIPLIERS: tuple[float, ...] = (1.0, 10.0, 100.0)
HEALTH_RULE = ("per feed: product of component probabilities (freshness, continuity, "
               "completeness, latency, reference); across feeds: geometric mean over the feeds "
               "in session; a closed feed is EXCLUDED, an unmeasured one is COUNTED and named")
GRAPH_RULE = ("an edge a->b at lag L is admissible only when L >= |offset_a - offset_b| + "
              "jitter_a + jitter_b, and both feeds are in session; below the clocks' joint "
              "resolution the ordering is not identifiable and the edge is REFUSED")


# ------------------------------------------------------------------------------------- stamps
@dataclass(frozen=True)
class FeedStamp:
    """One message's five clocks, in epoch milliseconds; None is UNMEASURED, never zero."""

    exchange_ms: float | None = None
    local_ms: float | None = None
    source_ms: float | None = None
    vendor_ms: float | None = None
    implied_ms: float | None = None
    seq: int | None = None


def stamp_coverage(stamps: Sequence[FeedStamp]) -> dict[str, dict[str, Any]]:
    """Which clocks a feed actually carries. A clock no message carries is UNMEASURED by name."""
    fields = {"source_event": "source_ms", "exchange": "exchange_ms",
              "vendor_receipt": "vendor_ms", "local_receipt": "local_ms", "implied": "implied_ms"}
    total = len(stamps)
    out: dict[str, dict[str, Any]] = {}
    for clock, attr in fields.items():
        n = sum(1 for s in stamps if getattr(s, attr) is not None)
        out[clock] = {"n": n, "of": total, "status": MEASURED if n else UNMEASURED}
    return out


def implied_time(leg_times: Sequence[float | None]) -> float | None:
    """A cross-venue reconstruction is as fresh as its STALEST leg; any missing leg makes it
    UNMEASURED. It is returned for the `implied` clock and must never be merged into a receipt."""
    if not leg_times or any(t is None for t in leg_times):
        return None
    return float(max(float(t) for t in leg_times if t is not None))


def _finite(values: Sequence[float] | FloatArray) -> FloatArray:
    arr = np.asarray(values, dtype=float).ravel()
    out: FloatArray = arr[np.isfinite(arr)]
    return out


def quantiles(values: Sequence[float] | FloatArray) -> dict[str, Any]:
    arr = _finite(values)
    if arr.size == 0:
        return {"status": UNMEASURED, "n": 0}
    p50, p90, p99 = (float(np.percentile(arr, q)) for q in (50, 90, 99))
    return {"status": MEASURED if arr.size >= 3 else "SAMPLE", "n": int(arr.size),
            "p50": round(p50, 3), "p90": round(p90, 3), "p99": round(p99, 3),
            "mean": round(float(arr.mean()), 3), "max": round(float(arr.max()), 3)}


# ------------------------------------------------------------------------------ measurements
def latency_distribution(exchange_ms: Sequence[float] | FloatArray,
                         local_ms: Sequence[float] | FloatArray) -> dict[str, Any]:
    """local - exchange per message. Negatives are kept and counted: dropping them would turn a
    clock offset into a flattering delay made of the positive tail."""
    a, b = np.asarray(exchange_ms, dtype=float), np.asarray(local_ms, dtype=float)
    if a.shape != b.shape or a.size == 0:
        return {"status": UNMEASURED, "n": 0, "why": "no paired stamps"}
    delta = b - a
    delta = delta[np.isfinite(delta)]
    if delta.size == 0:
        return {"status": UNMEASURED, "n": 0, "why": "no finite pair"}
    q = quantiles(delta)
    q.update({"n_negative": int((delta < 0).sum()),
              "offset_ms": round(float(np.median(delta)), 3),
              "jitter_ms": round(float(np.percentile(delta, 90) - np.median(delta)), 3)})
    return q


def sequence_continuity(seq: Sequence[float] | FloatArray, *,
                        integer_sequence: bool = False) -> dict[str, Any]:
    """Inversions and duplicates in arrival order; dropped numbers only where a true integer
    sequence exists. Time stamps are NOT sequence numbers: two ticks in one millisecond are a
    duplicate stamp, not a duplicate message, and a feed without numbers cannot count drops."""
    arr = np.asarray(seq, dtype=float).ravel()
    arr = arr[np.isfinite(arr)]
    n = int(arr.size)
    if n < 2:
        return {"status": UNMEASURED, "n": n, "why": "fewer than two messages"}
    d = np.diff(arr)
    inversions, duplicates = int((d < 0).sum()), int((d == 0).sum())
    out: dict[str, Any] = {"status": MEASURED, "n": n, "inversions": inversions,
                           "duplicates": duplicates,
                           "inversion_rate": round(inversions / (n - 1), 6)}
    if integer_sequence:
        dropped = int(np.clip(d - 1, 0, None).sum())
        out.update({"dropped": dropped, "drop_rate": round(dropped / (dropped + n), 6)})
    else:
        out.update({"dropped": None, "drop_rate": None,
                    "drop_basis": "no sequence numbers on this feed: drops are UNMEASURED here"
                                  " and proxied by silence bursts (see burst_rate)"})
    return out


def burst_rate(gaps_ms: Sequence[float] | FloatArray, *, multiple: float = BURST_MULTIPLE
               ) -> dict[str, Any]:
    """Share of inter-arrival gaps above `multiple` x the median gap: the drop PROXY."""
    g = _finite(gaps_ms)
    g = g[g >= 0]
    if g.size < MIN_OBS:
        return {"status": UNMEASURED, "n": int(g.size), "why": f"fewer than {MIN_OBS} gaps"}
    med = float(np.median(g))
    if med <= 0:
        return {"status": UNMEASURED, "n": int(g.size), "why": "median gap is zero"}
    bursts = int((g > multiple * med).sum())
    return {"status": MEASURED, "n": int(g.size), "median_gap_ms": round(med, 3),
            "bursts": bursts, "rate": round(bursts / g.size, 6), "multiple": multiple,
            "basis": "PROXY for dropped messages on a feed without sequence numbers"}


def staleness_probability(gaps_ms: Sequence[float] | FloatArray, age_ms: float
                          ) -> float | None:
    """P(a fresher quote was DUE by now) = P(in-session gap <= age), the empirical CDF of the
    feed's own inter-arrival gaps at the quote's current age. A one-second-old quote on a feed
    that ticks every two seconds is not stale (0.0); a five-second-old one is (1.0). None
    below MIN_OBS."""
    g = _finite(gaps_ms)
    g = g[g >= 0]
    if g.size < MIN_OBS or not math.isfinite(age_ms) or age_ms < 0:
        return None
    return float(np.mean(g <= age_ms))


def closed_threshold_ms(gaps_ms: Sequence[float] | FloatArray) -> float | None:
    """The silence beyond which a feed is CLOSED rather than stale: a multiple of its own p99 gap,
    floored. None when the gaps cannot establish it."""
    g = _finite(gaps_ms)
    g = g[g >= 0]
    if g.size < MIN_OBS:
        return None
    return max(CLOSED_FLOOR_MS, CLOSED_GAP_MULTIPLE * float(np.percentile(g, 99)))


def reference_consistency(a_times: Sequence[float] | FloatArray,
                          a_values: Sequence[float] | FloatArray,
                          b_times: Sequence[float] | FloatArray,
                          b_values: Sequence[float] | FloatArray, *,
                          lags_ms: Sequence[float] = (0.0,), min_pairs: int = 10
                          ) -> dict[str, Any]:
    """Two views of one instrument. For each candidate lag, every `a` observation is matched to
    the LAST `b` observation at or before `t_a + lag`; the lag with the smallest median |bps|
    is the measured clock offset between the views and its residual is their disagreement."""
    at, av = np.asarray(a_times, dtype=float), np.asarray(a_values, dtype=float)
    bt, bv = np.asarray(b_times, dtype=float), np.asarray(b_values, dtype=float)
    if at.size == 0 or bt.size == 0 or at.shape != av.shape or bt.shape != bv.shape:
        return {"status": UNMEASURED, "n": 0, "why": "one view is empty"}
    order = np.argsort(bt, kind="stable")
    bt, bv = bt[order], bv[order]
    rows: list[dict[str, Any]] = []
    for lag in lags_ms:
        shifted = at + float(lag)
        idx = np.searchsorted(bt, shifted, side="right") - 1
        # ONLY INSIDE THE REFERENCE'S OWN SPAN. A shifted time past the last `b` observation
        # would silently match that last (stale) value, and a lag that moved more `a` points
        # into the window would win on COUNT rather than agreement -- measured on the box
        # 2026-09-22, where +3 h "won" against a truncated tape day with 16.8 bps residual.
        keep = (idx >= 0) & (shifted <= bt[-1])
        if int(keep.sum()) < min_pairs:
            rows.append({"lag_ms": float(lag), "status": UNMEASURED, "n": int(keep.sum())})
            continue
        ref = bv[idx[keep]]
        own = av[keep]
        ok = np.isfinite(ref) & np.isfinite(own) & (ref != 0)
        if int(ok.sum()) < min_pairs:
            rows.append({"lag_ms": float(lag), "status": UNMEASURED, "n": int(ok.sum())})
            continue
        bps = (own[ok] - ref[ok]) / ref[ok] * 1e4
        rows.append({"lag_ms": float(lag), "status": MEASURED, "n": int(ok.sum()),
                     "median_abs_bps": round(float(np.median(np.abs(bps))), 4),
                     "p90_abs_bps": round(float(np.percentile(np.abs(bps), 90)), 4),
                     "median_bps": round(float(np.median(bps)), 4)})
    measured = [r for r in rows if r["status"] == MEASURED]
    if not measured:
        return {"status": UNMEASURED, "n": 0, "lags": rows, "why": "no lag pairs enough rows"}
    best = min(measured, key=lambda r: float(r["median_abs_bps"]))
    at0 = next((r for r in measured if r["lag_ms"] == 0.0), None)
    return {"status": MEASURED, "n": int(best["n"]), "best_lag_ms": float(best["lag_ms"]),
            "median_abs_bps_at_best": float(best["median_abs_bps"]),
            "median_abs_bps_at_zero": None if at0 is None else float(at0["median_abs_bps"]),
            "lags": rows}


# ---------------------------------------------------------------------------------- health
@dataclass(frozen=True)
class FeedClock:
    """One feed's measured clock. Every probability is in [0, 1]; None is UNMEASURED."""

    instrument: str
    n: int
    offset_ms: float | None = None        # median(local - exchange)
    jitter_ms: float | None = None        # p90 - p50 of that delay
    inversion_rate: float | None = None
    drop_prob: float | None = None        # burst proxy on MT5; true drops where a sequence exists
    stale_prob: float | None = None       # P(a fresher quote was due by now)
    repeat_rate: float | None = None      # share of messages repeating the previous value
    p_latency_ok: float | None = None     # P(delay <= the caller's tolerance)
    reference_ok: float | None = None     # 1 - clipped(median |bps| / tolerance)
    in_session: bool = True
    status: str = MEASURED
    why: str = ""


def _p(value: float | None) -> float | None:
    if value is None or not math.isfinite(value):
        return None
    return float(min(1.0, max(0.0, value)))


def feed_component_health(clock: FeedClock) -> dict[str, float | None]:
    """The five components of one feed's trustworthiness, each a probability or None."""
    return {"freshness": None if clock.stale_prob is None else _p(1.0 - clock.stale_prob),
            "continuity": (None if clock.inversion_rate is None
                           else _p(1.0 - clock.inversion_rate)),
            "completeness": None if clock.drop_prob is None else _p(1.0 - clock.drop_prob),
            "latency": _p(clock.p_latency_ok),
            "reference": _p(clock.reference_ok)}


def feed_trust(clock: FeedClock) -> dict[str, Any]:
    """P(this feed is trustworthy) = product of its MEASURED components; the unmeasured ones are
    listed rather than imputed as 1. A feed with no measured component is UNMEASURED."""
    comps = feed_component_health(clock)
    have = {k: v for k, v in comps.items() if v is not None}
    missing = sorted(k for k, v in comps.items() if v is None)
    if not clock.in_session:
        return {"status": "CLOSED", "p_trustworthy": None, "components": comps,
                "unmeasured_components": missing, "why": clock.why or "feed is out of session"}
    if not have:
        return {"status": UNMEASURED, "p_trustworthy": None, "components": comps,
                "unmeasured_components": missing, "why": clock.why or "no measured component"}
    p = 1.0
    for v in have.values():
        p *= v
    return {"status": MEASURED if not missing else "PARTIAL", "p_trustworthy": round(p, 6),
            "components": comps, "unmeasured_components": missing,
            "why": clock.why or ("every component measured" if not missing
                                 else f"unmeasured: {', '.join(missing)} (not imputed)")}


def feed_health(now_ms: float, clocks: Mapping[str, FeedClock]) -> dict[str, Any]:
    """P(observed market is trustworthy | all feeds), with the rule that produced it.

    The market-level number is the GEOMETRIC MEAN over feeds in session with a measured or
    partial trust -- a product would punish breadth (200 good feeds multiply to nothing) and an
    arithmetic mean would hide one dead feed among them. The minimum is published beside it so
    the worst feed is never averaged away.
    """
    per: dict[str, dict[str, Any]] = {}
    logs: list[float] = []
    for name in sorted(clocks):
        row = feed_trust(clocks[name])
        per[name] = row
        p = row.get("p_trustworthy")
        if p is not None and p > 0:
            logs.append(math.log(p))
    measured = {k: v for k, v in per.items() if v.get("p_trustworthy") is not None}
    zeros = sum(1 for v in per.values() if v.get("p_trustworthy") == 0.0)
    market: float | None = None
    if measured:
        market = 0.0 if zeros else float(math.exp(sum(logs) / len(logs)))
    worst = min(((v["p_trustworthy"], k) for k, v in measured.items()), default=None)
    return {"at_ms": float(now_ms), "rule": HEALTH_RULE,
            "status": MEASURED if measured else UNMEASURED,
            "p_market_trustworthy": None if market is None else round(market, 6),
            "worst_feed": None if worst is None else {"instrument": worst[1],
                                                     "p_trustworthy": worst[0]},
            "n_feeds": len(per), "n_in_session": sum(1 for v in per.values()
                                                     if v["status"] != "CLOSED"),
            "n_closed": sum(1 for v in per.values() if v["status"] == "CLOSED"),
            "n_unmeasured": sum(1 for v in per.values() if v["status"] == UNMEASURED),
            "feeds": per}


# ----------------------------------------------------------------------------- propagation
def min_admissible_lag_ms(a: FeedClock, b: FeedClock) -> float | None:
    """The smallest lag at which a->b ordering is identifiable from these two clocks. None when
    either clock's offset or jitter is unmeasured: an unknown clock admits no lag, which is the
    conservative reading and is named as such by `admissible`."""
    if None in (a.offset_ms, a.jitter_ms, b.offset_ms, b.jitter_ms):
        return None
    assert a.offset_ms is not None and b.offset_ms is not None
    assert a.jitter_ms is not None and b.jitter_ms is not None
    return abs(a.offset_ms - b.offset_ms) + abs(a.jitter_ms) + abs(b.jitter_ms)


def admissible(a: FeedClock, b: FeedClock, lag_ms: float) -> tuple[bool, str]:
    """Is 'a moved, then b moved `lag_ms` later' a causally admissible statement?"""
    if not a.in_session or not b.in_session:
        closed = a.instrument if not a.in_session else b.instrument
        return False, f"{closed} is out of session: nothing it did not quote can lead or lag"
    floor = min_admissible_lag_ms(a, b)
    if floor is None:
        return False, ("a clock is UNMEASURED (offset or jitter): an unknown clock admits no"
                       " ordering, which is a verdict and not a permission")
    if lag_ms < floor:
        return False, (f"lag {lag_ms:.0f} ms is below the clocks' joint resolution of"
                       f" {floor:.0f} ms: the ordering is not identifiable, REFUSED")
    return True, f"lag {lag_ms:.0f} ms >= resolution {floor:.0f} ms"


def propagation_graph(clocks: Mapping[str, FeedClock], lags_ms: Sequence[float]
                      ) -> dict[str, Any]:
    """Every ordered pair at every candidate lag, with its admissibility and the reason.

    The graph is a STATEMENT ABOUT THE CLOCKS, not about the instruments: it says which lead-lag
    claims the desk's feeds could even support, so a lead-lag miner reads it BEFORE it fits
    anything. A pair whose smallest admissible lag exceeds every candidate is listed under
    `unresolvable_pairs` -- a finding, not an absence.
    """
    names = sorted(clocks)
    edges: list[dict[str, Any]] = []
    refused = 0
    unresolvable: list[dict[str, Any]] = []
    for src in names:
        for dst in names:
            if src == dst:
                continue
            a, b = clocks[src], clocks[dst]
            floor = min_admissible_lag_ms(a, b)
            any_ok = False
            for lag in lags_ms:
                ok, why = admissible(a, b, float(lag))
                any_ok = any_ok or ok
                refused += int(not ok)
                # The clock-only verdict rides beside the full one, so a closed market (every
                # edge refused for session) still shows which lags the clocks COULD resolve.
                by_clock = floor is not None and float(lag) >= floor
                edges.append({"from": src, "to": dst, "lag_ms": float(lag), "admissible": ok,
                              "resolution_admissible": by_clock,
                              "min_admissible_lag_ms": None if floor is None
                              else round(floor, 3), "why": why})
            if not any_ok:
                unresolvable.append({"from": src, "to": dst,
                                     "min_admissible_lag_ms": None if floor is None
                                     else round(floor, 3)})
    return {"rule": GRAPH_RULE, "n_nodes": len(names), "lags_ms": [float(x) for x in lags_ms],
            "n_edges": len(edges), "n_admissible": sum(1 for e in edges if e["admissible"]),
            "n_resolution_admissible": sum(1 for e in edges if e["resolution_admissible"]),
            "n_refused": refused, "unresolvable_pairs": unresolvable, "edges": edges}


# ------------------------------------------------------------------------ timing fragility
@dataclass(frozen=True)
class TimingNoise:
    """A realistic timing-corruption model, in the units the feed was measured in."""

    jitter_ms: float = 0.0
    drop_prob: float = 0.0
    stale_prob: float = 0.0
    inversion_prob: float = 0.0

    def scaled(self, k: float) -> TimingNoise:
        return TimingNoise(jitter_ms=self.jitter_ms * k,
                           drop_prob=min(0.95, self.drop_prob * k),
                           stale_prob=min(0.95, self.stale_prob * k),
                           inversion_prob=min(0.95, self.inversion_prob * k))

    def row(self) -> dict[str, float]:
        return {"jitter_ms": round(self.jitter_ms, 3), "drop_prob": round(self.drop_prob, 6),
                "stale_prob": round(self.stale_prob, 6),
                "inversion_prob": round(self.inversion_prob, 6)}


def noise_from_clock(clock: FeedClock, *, age_ms: float | None = None) -> TimingNoise:
    """The corruption model a MEASURED clock implies; an unmeasured term contributes nothing and
    the caller is expected to say so (the verdict then carries `noise_basis`)."""
    # The per-message stale term is the REPEAT rate (a message carrying the previous value),
    # not `stale_prob`, which is the feed's freshness NOW and belongs to health.
    return TimingNoise(jitter_ms=float(clock.jitter_ms or 0.0),
                       drop_prob=float(clock.drop_prob or 0.0),
                       stale_prob=float(clock.repeat_rate or 0.0),
                       inversion_prob=float(clock.inversion_rate or 0.0))


def corrupt_timing(times: FloatArray, values: FloatArray, noise: TimingNoise,
                   rng: np.random.Generator) -> tuple[FloatArray, FloatArray]:
    """Apply the four corruptions a real feed inflicts, in the order they happen on the wire.

    jitter     each message arrives LATE by |N(0, jitter)| -- receipt is never early
    drop       a message is lost with probability drop_prob
    stale      a message repeats the previous VALUE with probability stale_prob (the frozen
               quote that looks exactly like a calm market)
    inversion  adjacent messages swap order with probability inversion_prob
    """
    t = np.asarray(times, dtype=float).copy()
    v = np.asarray(values, dtype=float).copy()
    n = t.size
    if n == 0:
        return t, v
    if noise.jitter_ms > 0:
        t = t + np.abs(rng.normal(0.0, noise.jitter_ms, size=n))
    if noise.stale_prob > 0 and n > 1:
        stale = rng.random(n) < noise.stale_prob
        stale[0] = False
        idx = np.where(stale, np.arange(n) - 1, np.arange(n))
        v = v[idx]
    if noise.inversion_prob > 0 and n > 1:
        swap = np.where(rng.random(n - 1) < noise.inversion_prob)[0]
        for i in swap:
            t[i], t[i + 1] = t[i + 1], t[i]
    if noise.drop_prob > 0:
        keep = rng.random(n) >= noise.drop_prob
        if int(keep.sum()) == 0:
            keep[rng.integers(0, n)] = True
        t, v = t[keep], v[keep]
    return t, v


def edge(signal: FloatArray, returns: FloatArray, *, min_pairs: int = MIN_OBS) -> float:
    """Mean return in the signal's direction per unit of return sd. NaN below `min_pairs`."""
    s, r = np.asarray(signal, dtype=float), np.asarray(returns, dtype=float)
    keep = np.isfinite(s) & np.isfinite(r) & (s != 0)
    if int(keep.sum()) < min_pairs:
        return float("nan")
    sd = float(np.std(r[keep]))
    if sd <= 0:
        return float("nan")
    return float(np.mean(np.sign(s[keep]) * r[keep]) / sd)


def matched_edge(sig_t: FloatArray, sig_v: FloatArray, tgt_t: FloatArray, tgt_v: FloatArray,
                 *, min_pairs: int = MIN_OBS) -> float:
    """The edge when each signal is matched to the target interval CONTAINING its (corrupted)
    time: a target stamped at t_k covers [t_k, t_k+1), so a message that arrives late inside
    the same interval still acts on that interval's return, and one that arrives after the
    interval closed acts on the next -- exactly what a late message costs at the target's own
    resolution (a bar-level target cannot express a 30 s delay; a tick-level one can)."""
    idx = np.searchsorted(tgt_t, sig_t, side="right") - 1
    keep = idx >= 0
    if int(keep.sum()) < min_pairs:
        return float("nan")
    return edge(sig_v[keep], tgt_v[idx[keep]], min_pairs=min_pairs)


def timing_fragility(signal: Sequence[tuple[float, float]],
                     target: Sequence[tuple[float, float]], noise: TimingNoise, *,
                     draws: int = 64, multipliers: Sequence[float] = MULTIPLIERS,
                     survival_fraction: float = SURVIVAL_FRACTION, min_pairs: int = MIN_OBS,
                     rng_seed: int = 20260922) -> dict[str, Any]:
    """Does the edge survive the timing uncertainty the desk's feeds actually carry?

    The clean edge is the signal matched to the first target at or after its stamp. Each draw
    corrupts the signal stream (jitter, drops, stale values, inversions) at `noise` scaled by a
    multiplier and re-measures. The verdict is taken at multiplier 1 -- the MEASURED noise --
    and the ladder above it is the margin: the largest multiplier at which the edge still keeps
    `survival_fraction` of its clean value. UNMEASURED below `min_pairs`, never a verdict.
    """
    sig = sorted((float(t), float(v)) for t, v in signal if math.isfinite(float(v)))
    tgt = sorted((float(t), float(v)) for t, v in target if math.isfinite(float(v)))
    if len(sig) < min_pairs or len(tgt) < min_pairs:
        return {"verdict": UNMEASURED, "n_signal": len(sig), "n_target": len(tgt),
                "why": f"fewer than {min_pairs} usable pair(s): a fragility curve needs a sample"}
    st, sv = (np.asarray([t for t, _ in sig]), np.asarray([v for _, v in sig]))
    tt, tv = (np.asarray([t for t, _ in tgt]), np.asarray([v for _, v in tgt]))
    base = matched_edge(st, sv, tt, tv, min_pairs=min_pairs)
    if not math.isfinite(base) or base == 0.0:
        return {"verdict": UNMEASURED, "n_signal": len(sig), "n_target": len(tgt),
                "base_edge": None if not math.isfinite(base) else 0.0,
                "why": "the clean edge is zero or unmeasurable, so nothing can decay"}
    rng = np.random.default_rng(rng_seed)
    ladder: list[dict[str, Any]] = []
    for k in multipliers:
        scaled = noise.scaled(float(k))
        got = np.asarray([matched_edge(*corrupt_timing(st, sv, scaled, rng), tt, tv,
                                       min_pairs=min_pairs) for _ in range(max(1, draws))])
        got = got[np.isfinite(got)]
        if got.size == 0:
            ladder.append({"multiplier": float(k), "status": UNMEASURED, "noise": scaled.row()})
            continue
        med = float(np.median(got))
        ladder.append({"multiplier": float(k), "status": MEASURED, "noise": scaled.row(),
                       "edge_median": round(med, 6), "edge_p10": round(float(np.percentile(
                           got, 10)), 6), "retained": round(med / base, 4),
                       "draws": int(got.size)})
    at1 = next((r for r in ladder if r["multiplier"] == 1.0 and r["status"] == MEASURED), None)
    if at1 is None:
        return {"verdict": UNMEASURED, "n_signal": len(sig), "n_target": len(tgt),
                "base_edge": round(base, 6), "ladder": ladder,
                "why": "no draw at the measured noise level produced a measurable edge"}
    fragile = float(at1["retained"]) < survival_fraction
    alive = [float(r["multiplier"]) for r in ladder
             if r["status"] == MEASURED and float(r["retained"]) >= survival_fraction]
    return {"verdict": "TIMING_FRAGILE" if fragile else "TIMING_ROBUST",
            "n_signal": len(sig), "n_target": len(tgt), "base_edge": round(base, 6),
            "retained_at_measured_noise": float(at1["retained"]),
            "survival_fraction": survival_fraction,
            "margin_multiplier": max(alive, default=0.0), "noise": noise.row(),
            "ladder": ladder,
            "reason": (f"the edge keeps only {float(at1['retained']):.0%} of its clean value"
                       " under the desk's own MEASURED timing noise: TIMING_FRAGILE, set aside"
                       " for research (never a size)") if fragile else
                      (f"the edge keeps {float(at1['retained']):.0%} under measured noise and"
                       f" survives to {max(alive, default=0.0):g}x of it")}
