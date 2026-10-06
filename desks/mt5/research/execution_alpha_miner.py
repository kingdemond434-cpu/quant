"""EXECUTION-TAPE ALPHA: the tape is a MINING SOURCE, not a cost model.

PRINCIPAL, 2026-09-17 (ledger M5). "The execution tape is a proprietary mining source that can
produce EXECUTION ALPHA, not merely lower costs." Every organ this desk has pointed at the tape so
far points the same way -- DOWNWARD. `execution_twin` calibrates the simulator's slippage against
the fills, `entry_timing` asks whether a certificate's gate ever reached the hours it trades,
`moat_series` prices the tape's depth. All three are cost accounting, and cost accounting can only
give money back. None of them asks the question that makes a tape an ASSET: is there a STATE of
this venue's quote stream in which WAITING TEN SECONDS IS WORTH BASIS POINTS? If there is, it is a
mechanism with an economic actor behind it -- a quote engine widening into a state it expects to
revert, a provider skewing a quote it means to pull -- it is unbuyable after the fact, and it
belongs in the gauntlet exactly like a range breakout does.

THE TWO SEARCHES, BOTH ON THIS DESK'S OWN FUSION TAPE.

  P(adverse move | spread, state, time)   A synthetic entry every ENTRY_STRIDE_S seconds, in every
      (spread tercile x quote-velocity tercile x session) cell: the fraction whose mid moves
      AGAINST the entry side by more than the half spread within 10 s / 60 s / 5 min. The side is
      the 30-second momentum sign, so "adverse" means the venue moved against the direction you
      were leaning -- adverse selection, which a quote engine can actually produce. The baseline is
      the same construction pooled over the instrument-day with NO conditioning, so a cell that
      beats it is a statement about the STATE and not about the proxy.

  E[return | signal, delayed 10 s] - E[return | immediate]   Same proxy, decided at t. The
      immediate arm enters at t; the delayed arms at t+10 s and t+30 s, each holding the same
      horizon from its own entry. The difference is PAIRED per entry and its interval comes from a
      MOVING-BLOCK BOOTSTRAP: a one-second mid path is autocorrelated to its eyebrows and an iid
      bootstrap would manufacture significance out of the sampling.

WHAT THIS BOX ACTUALLY HOLDS, measured before a line of this was written, because a miner that
assumes its inputs reports fiction:

  * TWO TAPE WRITERS, ONE TAPE. `data/tape/ticks/<SYM>/` carries both `20260916.parquet` (the
    recorder: recv_utc/recv_mono, no `ts`) and `2026-09-16.parquet` (`mt5desk/tape.py`: `ts`, no
    recv_*), across 245 instrument directories. `moat_series.tape_index` already normalises both
    and prefers the larger file; this organ reuses it rather than growing a third opinion about
    what a tape day is called, and reuses `_read_day` for the same reason.
  * `data/moat/` DOES NOT EXIST HERE, so `moat_series.series_frame` returns an EMPTY frame for
    every derived series -- and empty means UNMEASURED, never zero (L1.28a). The cells are built
    from the tape directly, the report says so in `moat_series_store`, and the store's day-level
    medians are read as context the day they exist.
  * THE FILL SIDE IS THIN AND MOSTLY UNMEASURED, BY NAME. `live_ledger.jsonl` holds 151 closed
    deals with a `fill_price` and NO quote and NO latency; of `fill_corpus.jsonl`'s 109 rows
    `latency_decision_to_send_ms` is present on 62, `spread_frac_at_decision` on 13, and
    `latency_send_to_ack_ms`, `latency_ack_to_fill_ms`, `spread_frac_at_fill` and all four markout
    columns on ZERO. Slippage and markout are therefore not read from a column -- they are JOINED
    to the tape at the deal's own second, which this desk can do because it owns both sides.
    `order_intents.jsonl` (92 rows) carries `retcode`, so rejection by state is real.

THE RECURRENCE RULE IS THE DIFFERENCE BETWEEN A MINER AND A MINE. One cell, one day, one bootstrap
that happens to exclude zero is a coincidence with an interval attached. A cell becomes a DISCOVERY
only when the same effect key clears its CI on >= MIN_DAYS_SIGNIFICANT instrument-days AND recurs
on >= MIN_INSTRUMENTS instruments. Everything else is published in the artifact and recorded
nowhere, which is the right disposition for a number that has not earned a trial.

WHAT IT REFUSES. It never tests a strategy: no P&L, no gate. It never donates a cell -- the
discovery lands in UNPROCESSED and the compiler decides what it owes (`conversion_debt`). It never
sizes or vetoes anything live: a `spread_gate` is a HYPOTHESIS about execution, and under GROWTH
GOVERNANCE Rule 1 a restriction that has not proven it raises robust forward E[log W] restricts
nothing. This organ has proven nothing; it has found something worth testing.

    python research/execution_alpha_miner.py --budget-s 240 --days 3
    python research/execution_alpha_miner.py --symbols XAUUSD,EURUSD --dry-run
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from collections import Counter, defaultdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np

BASE = Path(__file__).resolve().parents[1]
ROOT = BASE.parent.parent
for _p in (str(BASE), str(BASE / "research"), str(ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from libs.moat import registry  # noqa: E402
from research import moat_series as mos  # noqa: E402

#: The desk's own ledgers. Every one is written by an organ that already owns it; nothing here
#: writes to any of them.
LIVE_LEDGER = BASE / "data" / "live_ledger.jsonl"
FILL_CORPUS = BASE / "data" / "fill_corpus.jsonl"
ORDER_INTENTS = BASE / "data" / "order_intents.jsonl"
REPORTS = BASE / "reports"
REPORT = REPORTS / "EXECUTION_ALPHA.json"
#: Read, never recomputed: whatever the fill organs already published about this same ground.
FILL_ARTIFACT_GLOBS = ("MARKOUT*.json", "markout*.json", "FILL_ATTRIBUTION*.json")

GENERATOR = "execution_alpha_miner"
SOURCE_TYPE = "execution_tape"
RULE = ("the tape is a proprietary alpha source: a state where waiting ten seconds is worth basis "
        "points is a mechanism, and it goes to the gauntlet like any other")
NEXT_GATE = "gauntlet"
RECURRENCE_RULE = (
    "a cell becomes a discovery only when its bootstrap CI excludes zero on >= 2 instrument-days "
    "for the SAME effect key and the same key recurs on >= 2 instruments; one day on one "
    "instrument is a coincidence with a confidence interval attached")

#: Forward horizons in seconds. 10 s is inside a quote engine's own reaction, 60 s is a scalp's
#: first minute, 300 s is where a session mechanism starts to dominate the microstructure.
HORIZONS_S: tuple[int, ...] = (10, 60, 300)
#: The delays the timing search compares against an immediate entry.
DELAYS_S: tuple[int, ...] = (10, 30)
#: The horizons the timing search measures the delayed and immediate arms over.
DVI_HORIZONS_S: tuple[int, ...] = (10, 60)
#: The directional signal proxy: the sign of the mid move over the last MOMENTUM_S seconds. It is
#: deliberately a PROXY and deliberately trivial -- the question is whether the EXECUTION STATE
#: changes what a signal is worth, and a clever signal would confound the two.
MOMENTUM_S = 30
#: A synthetic entry every this many seconds of the one-second mid path.
ENTRY_STRIDE_S = 5
#: Moving-block bootstrap. The block is five minutes because the mid path's autocorrelation is the
#: thing being defended against; an iid draw would fabricate significance from the sampling.
BOOT_DRAWS, BOOT_BLOCK_S, BOOT_MAX_N = 200, 300, 6000
#: MEASURED IN THIS FILE'S FIRST RUN. With the block taken as `min(BOOT_BLOCK_S, n)` a 141-point
#: cell drew ONE block from a single legal start, every draw was the same series, and the interval
#: came back zero-width -- `[+0.6027, +0.6027]`, which "excludes zero" trivially and would have
#: sent a coincidence to the registry. The block is capped so MIN_BLOCKS distinct blocks exist;
#: a cell that cannot supply them is UNMEASURED rather than certain.
MIN_BLOCKS = 8
#: Below this many entries a cell is not measured at all -- an interval on forty points is theatre.
MIN_CELL_ENTRIES = 60
#: A SECOND IS ONLY A QUOTE IF A QUOTE ARRIVED NEAR IT. The grid forward-fills the last quote
#: across seconds the venue did not update -- right for a ten-second gap, a lie across a weekend:
#: the first live pass joined 143 deals and returned a MEDIAN 10-second markout of EXACTLY 0.0 bps
#: off frozen quotes. Every entry, forward read and fill join now needs its second -- and its
#: horizon's second -- within MAX_STALE_S of a real quote. A frozen mid is UNMEASURED.
MAX_STALE_S = 60
MIN_DAYS_SIGNIFICANT, MIN_INSTRUMENTS = 2, 2
#: Deterministic: the same tape re-mined gives the same intervals, so an hourly rerun is idempotent
#: in the registry rather than a fresh coincidence every pass.
SEED = 20260917
DEFAULT_SYMBOLS, DEFAULT_DAYS, DEFAULT_BUDGET_S = 8, 3, 240.0
#: The artifact is evidence, not a dump: the strongest rows by |effect| survive the cap.
MAX_REPORT_ROWS = 400
#: The fill join reads tape days the main loop did not; both are bounded.
MAX_FILL_TAPE_DAYS, FILL_CACHE_MAX = 12, 6

SPREAD_LABELS = ("tight", "mid", "wide")
VELOCITY_LABELS = ("slow", "normal", "fast")


def _now() -> str:
    return datetime.now(tz=UTC).isoformat(timespec="seconds")


def _jsonl(path: Path) -> list[dict[str, Any]]:
    """Every JSON object in an append-only ledger; a torn final line is skipped, never fatal."""
    try:
        text = path.read_text("utf-8")
    except OSError:
        return []
    out: list[dict[str, Any]] = []
    for line in text.splitlines():
        s = line.strip()
        if not s:
            continue
        try:
            row = json.loads(s)
        except ValueError:
            continue
        if isinstance(row, dict):
            out.append(row)
    return out


def _load_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text("utf-8"))
    except (OSError, ValueError):
        return None


def _f(x: Any) -> float | None:
    if x is None or isinstance(x, bool):
        return None
    try:
        v = float(x)
    except (TypeError, ValueError):
        return None
    return v if np.isfinite(v) else None


def _stats(values: list[float]) -> dict[str, Any]:
    a = np.asarray(values, dtype="float64")
    if a.size == 0:
        return {"n": 0, "mean": None, "p50": None, "p90": None, "max": None}
    return {"n": int(a.size), "mean": round(float(a.mean()), 4),
            "p50": round(float(np.percentile(a, 50)), 4),
            "p90": round(float(np.percentile(a, 90)), 4), "max": round(float(a.max()), 4)}


# --------------------------------------------------------------------- the one-second mid path --

def second_path(path: Path) -> dict[str, np.ndarray] | None:
    """One tape day as a DENSE one-second grid: mid, quoted spread in bps, UTC hour, quotes/min.

    The tick reader is `moat_series._read_day` ON PURPOSE. It already decides what an unusable
    quote is (bid>0, ask>=bid, finite stamp), it already handles both tape writers' column sets,
    and a second reader here would be a second opinion about the desk's own tape -- exactly the
    divergence `tape_index` exists to prevent. Each second carries its LAST observed quote,
    forward-filled across seconds the venue did not update, because that is the quote an order
    arriving in that second would have met.
    """
    d = mos._read_day(path)
    if d is None:
        return None
    ms, mid, spread_bps = d["ms"], d["mid"], d["spread_bps"]
    sec = (ms // 1000).astype("int64")
    uniq = np.unique(sec)
    if uniq.size < MOMENTUM_S + max(HORIZONS_S) + 2:
        return None
    last = np.searchsorted(sec, uniq, side="right") - 1
    grid = np.arange(int(uniq[0]), int(uniq[-1]) + 1, dtype="int64")
    pos = np.searchsorted(uniq, grid, side="right") - 1
    take = last[pos]
    minute = (ms // 60_000).astype("int64")
    m0 = int(minute[0])
    counts = np.bincount(minute - m0)
    qpm = counts[np.clip(grid // 60 - m0, 0, counts.size - 1)].astype("float64")
    return {"sec": grid, "mid": mid[take], "spread_bps": spread_bps[take],
            "hour": (grid // 3600) % 24, "qpm": qpm, "stale_s": grid - uniq[pos]}


def live_mask(sp: dict[str, np.ndarray]) -> np.ndarray:
    """Seconds whose quote is fresher than MAX_STALE_S -- the only seconds an order could meet."""
    return sp["stale_s"] <= MAX_STALE_S


def _tercile(x: np.ndarray) -> np.ndarray:
    """0/1/2 by the day's own terciles. `searchsorted` rather than `digitize` so a degenerate
    day (a constant spread, a dead instrument) collapses into one bucket instead of raising."""
    q = np.quantile(x, [1.0 / 3.0, 2.0 / 3.0])
    return np.searchsorted(q, x, side="right").astype("int64")


def cell_masks(sp: dict[str, np.ndarray]) -> dict[str, np.ndarray]:
    """(spread tercile x quote-velocity tercile x session) over the one-second grid.

    SESSIONS OVERLAP by the desk's own definition (london 8-16, ny 14-22) and the vocabulary is
    imported from `moat_series`, which imports it from `mt5desk.family_call` -- so a cell named
    `london` here is the window a certificate certified in `london` actually trades. A second
    inside two sessions is counted in both, and `all` is the unconditioned session.
    """
    live = live_mask(sp)
    sp_state, vel_state = _tercile(sp["spread_bps"]), _tercile(sp["qpm"])
    sessions = {"all": live}
    for name, (lo, hi) in mos.SESSIONS.items():
        sessions[name] = live & (sp["hour"] >= lo) & (sp["hour"] < hi)
    out: dict[str, np.ndarray] = {}
    for si, slabel in enumerate(SPREAD_LABELS):
        smask = sp_state == si
        for vi, vlabel in enumerate(VELOCITY_LABELS):
            vmask = smask & (vel_state == vi)
            if not vmask.any():
                continue
            for sess, sessmask in sessions.items():
                m = vmask & sessmask
                if int(m.sum()) >= MIN_CELL_ENTRIES * ENTRY_STRIDE_S:
                    out[f"spread={slabel}|vel={vlabel}|session={sess}"] = m
    return out


def entry_side(mid: np.ndarray) -> np.ndarray:
    """The signal proxy: the sign of the mid move over the last MOMENTUM_S seconds, 0 where the
    path is flat or the lookback is not yet available. 0 is NOT a side and never becomes one."""
    side = np.zeros(mid.shape, dtype="float64")
    side[MOMENTUM_S:] = np.sign(mid[MOMENTUM_S:] - mid[:-MOMENTUM_S])
    return side


# ------------------------------------------------------------------------ the block bootstrap --

def block_bootstrap_ci(x: np.ndarray, rng: np.random.Generator, *, draws: int = BOOT_DRAWS,
                       block: int = BOOT_BLOCK_S) -> tuple[float, float]:
    """A 95% CI for the mean of an autocorrelated series by the moving-block bootstrap.

    The series is thinned to BOOT_MAX_N by a deterministic stride before drawing: this box has
    8 GB and fourteen resident python processes (CLAUDE.md), and a 200 x 17,000 index matrix per
    cell is how an hourly leg starts standing down for memory instead of mining.
    """
    n = int(x.size)
    if n < MIN_CELL_ENTRIES:
        return float("nan"), float("nan")
    if n > BOOT_MAX_N:
        x = x[:: int(np.ceil(n / BOOT_MAX_N))]
        n = int(x.size)
    L = int(min(block, max(1, n // MIN_BLOCKS)))
    if L < 1 or n - L + 1 < MIN_BLOCKS:
        return float("nan"), float("nan")
    nb = int(np.ceil(n / L))
    starts = rng.integers(0, n - L + 1, size=(draws, nb))
    idx = (starts[:, :, None] + np.arange(L)[None, None, :]).reshape(draws, -1)[:, :n]
    means = np.asarray(x, dtype="float64")[idx].mean(axis=1)
    return float(np.percentile(means, 2.5)), float(np.percentile(means, 97.5))


def _excludes_zero(ci: tuple[float, float]) -> bool:
    lo, hi = ci
    return bool(np.isfinite(lo) and np.isfinite(hi) and (lo > 0.0 or hi < 0.0))


def _outside(ci: tuple[float, float], value: float) -> bool:
    """Is `value` outside the interval? A non-finite interval is UNMEASURED, never outside."""
    lo, hi = ci
    return bool(np.isfinite(lo) and np.isfinite(hi) and not lo <= value <= hi)


def _ci(ci: tuple[float, float]) -> list[float | None]:
    """A JSON-safe interval: a NaN bound is `null`, because `NaN` is not JSON and a reader who
    parses it leniently reads an unmeasured cell as a number."""
    return [None if not np.isfinite(b) else round(float(b), 6) for b in ci]


# --------------------------------------------------------------------------- the two searches --

def adverse_move_day(sp: dict[str, np.ndarray], masks: dict[str, np.ndarray],
                     rng: np.random.Generator
                     ) -> tuple[list[dict[str, Any]], dict[tuple, np.ndarray]]:
    """P(mid moves against the entry side by more than the half spread | cell, horizon).

    The baseline is the identical construction over EVERY valid entry in the day with no
    conditioning -- the random-entry rate. A cell is called significant when the baseline falls
    OUTSIDE the cell's own bootstrap interval, which is a statement that the STATE matters and not
    merely that adverse moves happen. Returns the per-day rows and the raw indicator series per
    key, so a symbol's days pool into one interval without re-reading the tape.
    """
    mid, half, live = sp["mid"], sp["spread_bps"] / 2.0, live_mask(sp)
    side = entry_side(mid)
    n = int(mid.size)
    entries = np.arange(MOMENTUM_S, n, ENTRY_STRIDE_S)
    entries = entries[(side[entries] != 0.0) & live[entries]]
    rows: list[dict[str, Any]] = []
    pooled: dict[tuple, np.ndarray] = {}
    for h in HORIZONS_S:
        e = entries[entries + h < n]
        e = e[live[e + h]]
        if e.size < MIN_CELL_ENTRIES:
            continue
        fwd_bps = (mid[e + h] - mid[e]) / mid[e] * 1e4
        adverse = ((-side[e] * fwd_bps) > half[e]).astype("float32")
        baseline = float(adverse.mean())
        for cell, mask in masks.items():
            ind = adverse[mask[e]]
            if ind.size < MIN_CELL_ENTRIES:
                continue
            ci = block_bootstrap_ci(ind, rng)
            rows.append({"cell": cell, "horizon_s": h, "p_adverse": float(ind.mean()),
                         "baseline": baseline, "n": int(ind.size), "ci": _ci(ci),
                         "significant": _outside(ci, baseline)})
            pooled[(cell, h)] = ind
    return rows, pooled


def delayed_vs_immediate_day(sp: dict[str, np.ndarray], masks: dict[str, np.ndarray],
                             rng: np.random.Generator
                             ) -> tuple[list[dict[str, Any]], dict[tuple, np.ndarray]]:
    """E[forward mid move | signal, entry delayed d] - E[... | entry immediate], PAIRED per entry.

    The signal is decided at t in both arms. The immediate arm enters at t and holds h seconds;
    the delayed arm enters at t+d and holds h seconds FROM ITS OWN ENTRY, so the two arms take the
    same risk for the same time and differ only in when they took it. Returns the per-day rows and
    the raw paired differences per key, so the caller can pool a symbol's days into one interval
    without re-reading the tape.
    """
    mid, live = sp["mid"], live_mask(sp)
    side = entry_side(mid)
    n = int(mid.size)
    rows: list[dict[str, Any]] = []
    pooled: dict[tuple, np.ndarray] = {}
    base = np.arange(MOMENTUM_S, n, ENTRY_STRIDE_S)
    base = base[(side[base] != 0.0) & live[base]]
    for delay in DELAYS_S:
        for h in DVI_HORIZONS_S:
            e = base[base + delay + h < n]
            e = e[live[e + h] & live[e + delay] & live[e + delay + h]]
            if e.size < MIN_CELL_ENTRIES:
                continue
            imm = side[e] * (mid[e + h] - mid[e]) / mid[e] * 1e4
            dly = side[e] * (mid[e + delay + h] - mid[e + delay]) / mid[e + delay] * 1e4
            diff = dly - imm
            for cell, mask in masks.items():
                d = diff[mask[e]]
                if d.size < MIN_CELL_ENTRIES:
                    continue
                ci = block_bootstrap_ci(d, rng)
                rows.append({"cell": cell, "delay_s": delay, "horizon_s": h,
                             "diff_bps": float(d.mean()), "ci": _ci(ci), "n": int(d.size),
                             "significant": _excludes_zero(ci)})
                pooled[(cell, delay, h)] = d.astype("float32")
    return rows, pooled


# -------------------------------------------------------------------------------- the fills --

def _session_of(hour: int) -> str:
    hit = [name for name, (lo, hi) in mos.SESSIONS.items() if lo <= hour < hi]
    return "+".join(sorted(hit)) if hit else "none"


def _fill_cache(sym: str, day: str, index: dict[str, dict[str, Path]],
                cache: dict[tuple[str, str], Any]) -> dict[str, np.ndarray] | None:
    key = (sym, day)
    if key not in cache:
        if len(cache) >= FILL_CACHE_MAX:
            cache.pop(next(iter(cache)))
        path = index.get(sym, {}).get(day)
        cache[key] = None if path is None else second_path(path)
    return cache[key]


def fills_block(index: dict[str, dict[str, Path]], *, deadline: float,
                unmeasured: list[str]) -> dict[str, Any] | str:
    """Realised slippage against the QUOTE, post-fill markout, latency and rejection by state.

    Slippage and markout are NOT read from a column: on this box `live_ledger.jsonl` carries a
    `fill_price` and no quote, and every markout column of `fill_corpus.jsonl` is null. They are
    JOINED to the tape at the second the deal is stamped -- the desk owns both sides, which is the
    entire reason this is a moat series and not a vendor feed. A deal whose second is outside the
    tape is UNMEASURED by name, never priced at the nearest quote it can reach.
    """
    ledger, corpus, intents = _jsonl(LIVE_LEDGER), _jsonl(FILL_CORPUS), _jsonl(ORDER_INTENTS)
    if not (ledger or corpus or intents):
        unmeasured.append("fills: no live_ledger.jsonl, fill_corpus.jsonl or order_intents.jsonl")
        return "UNMEASURED"

    by_day: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    stamped: list[tuple[str, int, dict[str, Any]]] = []
    for r in ledger:
        sym, price = str(r.get("symbol") or ""), _f(r.get("fill_price"))
        try:
            when = datetime.fromisoformat(str(r.get("time")))
        except (TypeError, ValueError):
            continue
        if sym and price is not None and when.tzinfo is not None:
            stamped.append((sym, int(when.timestamp()),
                            {"day": when.date().isoformat(), "sec": int(when.timestamp()),
                             "price": price, "hour": when.hour,
                             "side": 1.0 if int(r.get("side") or 0) == 0 else -1.0}))
    # THE LEDGER'S `time` IS NOT ALWAYS A FILL SECOND: 134 of this box's 151 deals share a
    # (symbol, second) stamp -- sixteen EURCHF at 2026-09-16T04:45:53, eleven XAUUSD at
    # 2026-09-07T17:04:15 with fill prices from 4351 to 4493. That is the gateway writing back
    # reconciled deals at one wall clock, and pricing them against the quote at that second gave a
    # -42 bps NY "slippage" that measured the WRITE. Seventeen stamps hold one deal each.
    seen = Counter((s, t) for s, t, _ in stamped)
    bulk = 0
    for sym, sec, fill in stamped:
        if seen[(sym, sec)] > 1:
            bulk += 1
            continue
        by_day[(sym, fill["day"])].append(fill)
    order = sorted(by_day, key=lambda k: (-len(by_day[k]), k))[:MAX_FILL_TAPE_DAYS]
    cache: dict[tuple[str, str], Any] = {}
    slip: dict[str, list[float]] = defaultdict(list)
    halfsp: dict[str, list[float]] = defaultdict(list)
    marks: dict[int, list[float]] = defaultdict(list)
    joined, days_read, stale = 0, 0, 0
    for sym, day in order:
        if time.monotonic() > deadline:
            unmeasured.append(f"fills: budget stopped before {sym} {day}")
            break
        sp = _fill_cache(sym, day, index, cache)
        if sp is None:
            continue
        days_read += 1
        mid, spb, grid, live = sp["mid"], sp["spread_bps"], sp["sec"], live_mask(sp)
        n, first = int(mid.size), int(grid[0])
        states = _tercile(spb)
        for fill in by_day[(sym, day)]:
            i = fill["sec"] - first
            if not (0 <= i < n) or not live[i]:
                stale += 1
                continue
            joined += 1
            bps = fill["side"] * (fill["price"] - mid[i]) / mid[i] * 1e4
            for key in (f"session={_session_of(fill['hour'])}",
                        f"spread={SPREAD_LABELS[min(int(states[i]), 2)]}"):
                slip[key].append(float(bps))
                halfsp[key].append(float(spb[i]) / 2.0)
            for h in HORIZONS_S:
                if i + h < n and live[i + h]:
                    marks[h].append(float(fill["side"] * (mid[i + h] - fill["price"])
                                          / fill["price"] * 1e4))
    if bulk:
        unmeasured.append(
            f"fills: {bulk} of {len(ledger)} ledger deals share a (symbol, second) stamp -- a bulk "
            f"reconciliation write, not a fill second; their slippage and markout are REFUSED")
    if joined == 0:
        unmeasured.append("fills: no ledger deal falls inside a live second of a tape day here")
    if stale:
        unmeasured.append(f"fills: {stale} deals sit outside the tape or on a quote older than "
                          f"{MAX_STALE_S}s -- slippage and markout are UNMEASURED for them")

    lat: dict[str, Any] = {}
    for col in ("latency_decision_to_send_ms", "latency_send_to_ack_ms", "latency_ack_to_fill_ms"):
        vals = [v for v in (_f(r.get(col)) for r in corpus) if v is not None]
        if vals:
            lat[col] = _stats(vals)
        else:
            lat[col] = f"UNMEASURED: 0 of {len(corpus)} fill_corpus rows carry it"
            unmeasured.append(f"fills.{col}: 0 of {len(corpus)} rows")

    rej: dict[str, Any] = {"n_intents": len(intents), "rejected": 0, "by_retcode": {},
                           "by_session": {}, "by_spread_state": {}}
    per_session: dict[str, list[float]] = defaultdict(list)
    per_state: dict[str, list[float]] = defaultdict(list)
    for r in intents:
        code = _f(r.get("retcode"))
        if code is None:
            continue
        bad = float(int(code) not in (10008, 10009))
        rej["rejected"] += int(bad)
        rej["by_retcode"][str(int(code))] = rej["by_retcode"].get(str(int(code)), 0) + 1
        try:
            when = datetime.fromisoformat(str(r.get("time")))
        except (TypeError, ValueError):
            continue
        per_session[_session_of(when.hour)].append(bad)
        sp = _fill_cache(str(r.get("symbol") or ""), when.date().isoformat(), index, cache)
        if sp is not None:
            i = int(when.timestamp()) - int(sp["sec"][0])
            if 0 <= i < int(sp["mid"].size) and live_mask(sp)[i]:
                st = SPREAD_LABELS[min(int(_tercile(sp["spread_bps"])[i]), 2)]
                per_state[st].append(bad)
    rej["rate"] = (round(rej["rejected"] / len(intents), 4) if intents else None)
    rej["by_session"] = {k: {"n": len(v), "rate": round(float(np.mean(v)), 4)}
                         for k, v in sorted(per_session.items())}
    rej["by_spread_state"] = {k: {"n": len(v), "rate": round(float(np.mean(v)), 4)}
                              for k, v in sorted(per_state.items())}
    if not per_state:
        unmeasured.append("fills.rejection_by_spread_state: no intent falls inside a tape day")

    arts: dict[str, Any] = {}
    for pattern in FILL_ARTIFACT_GLOBS:
        for p in sorted(REPORTS.glob(pattern)) if REPORTS.is_dir() else []:
            doc = _load_json(p)
            if isinstance(doc, dict):
                arts[p.name] = {k: doc[k] for k in ("at", "generated_utc", "usable", "n_matched",
                                                    "funnel", "rates") if k in doc}
    return {
        "measured": joined > 0,
        "n_ledger_deals": len(ledger), "n_corpus_rows": len(corpus), "n_intents": len(intents),
        "n_joined_to_tape": joined, "n_unjoinable_or_stale": stale,
        "n_bulk_stamped_refused": bulk, "tape_days_read": days_read,
        "slippage_vs_quote_bps": {
            k: {**_stats(v), "half_spread_bps_mean": _stats(halfsp[k])["mean"]}
            for k, v in sorted(slip.items())},
        "markout_bps": {str(h): _stats(marks[h]) for h in HORIZONS_S},
        "latency_ms": lat, "rejection": rej, "artifacts": arts,
        "note": ("slippage is fill_price against the tape mid at the deal's own second, positive = "
                 "worse than mid; markout is the mid move in the deal's favour after the fill"),
    }


# ------------------------------------------------------------------------ symbols and the run --

def select_symbols(index: dict[str, dict[str, Path]], n: int) -> list[str]:
    """The most-traded non-equity instruments this desk actually has a tape for, XAUUSD forced in.

    TRADED, not listed: the count comes from the desk's own closed deals. The equity lane is
    excluded by `universe_policy` -- ASSET CLASS from MetaTrader's registry, never a symbol list
    (the two-lane order, 2026-09-06): single names are traded on disclosure and hunted by nothing
    statistical, and every equity cell spends the same family-wise error budget FX and metals pay.
    """
    try:
        from research.universe_policy import may_hypothesise
    except ImportError:  # pragma: no cover -- the desk package is importable on both boxes
        def may_hypothesise(symbol: str) -> bool:
            return True
    counts: dict[str, int] = defaultdict(int)
    for r in _jsonl(LIVE_LEDGER):
        sym = str(r.get("symbol") or "")
        if sym in index:
            counts[sym] += 1
    ranked = sorted(index, key=lambda s: (-counts.get(s, 0), -len(index[s]), s))
    out = [s for s in ranked if may_hypothesise(s)] or ranked
    picked = [s for s in out if s == "XAUUSD"] + [s for s in out if s != "XAUUSD"]
    return picked[:n]


def _suggested(measure: str, effect: dict[str, Any], cell: str) -> str:
    """The hint the discovery carries into the compiler. It is a HINT: the gauntlet decides."""
    if measure == "delayed_vs_immediate":
        # A positive difference is the headline finding -- waiting pays. A negative one says the
        # signal decays inside ten seconds, so the entry has to exist at t: a resting limit placed
        # AT the signal is the only way to be in the market then without paying the cross.
        return "delayed_entry" if effect["diff_bps"] > 0 else "limit_entry"
    if effect["p_adverse"] <= effect["baseline"]:
        # The mid runs against you LESS than at a random entry: a resting order here is the cheap
        # way to be in the market, because the state itself is not the one that picks you off.
        return "limit_entry"
    if "spread=wide" in cell or "session=all" in cell:
        # A cell on `all` is not a session and cannot be avoided as one; every cell IS a spread
        # tercile, so the gate on that tercile is the expressible restriction. (The first live
        # artifact emitted `session_avoid` on a `session=all` cell -- an uncashable instruction.)
        return "spread_gate"
    return "session_avoid"


def _discovery_rows(adverse: list[dict[str, Any]], dvi: list[dict[str, Any]]
                    ) -> list[dict[str, Any]]:
    """Apply RECURRENCE_RULE to the pooled per-symbol rows and return what earned a trial."""
    keyed: dict[tuple, list[dict[str, Any]]] = defaultdict(list)
    for r in dvi:
        if r["days_significant"] >= MIN_DAYS_SIGNIFICANT:
            keyed[("delayed_vs_immediate", r["cell"], r["delay_s"], r["horizon_s"],
                   int(np.sign(r["diff_bps"])))].append(r)
    for r in adverse:
        if r["days_significant"] >= MIN_DAYS_SIGNIFICANT:
            keyed[("adverse_move", r["cell"], r["horizon_s"],
                   int(np.sign(r["p_adverse"] - r["baseline"])))].append(r)
    out: list[dict[str, Any]] = []
    for key, rows in sorted(keyed.items(), key=lambda kv: str(kv[0])):
        if len({r["symbol"] for r in rows}) < MIN_INSTRUMENTS:
            continue
        measure = str(key[0])
        for r in rows:
            effect = ({"measure": measure, "delay_s": r["delay_s"], "horizon_s": r["horizon_s"],
                       "diff_bps": round(r["diff_bps"], 4)} if measure == "delayed_vs_immediate"
                      else {"measure": measure, "horizon_s": r["horizon_s"],
                            "p_adverse": round(r["p_adverse"], 4),
                            "baseline": round(r["baseline"], 4)})
            out.append({"instrument": r["symbol"], "cell": r["cell"], "effect": effect,
                        "ci": list(r["ci"]), "n": r["n"],
                        "suggested": _suggested(measure, effect, r["cell"]),
                        "instrument_days_significant": r["days_significant"],
                        "recurring_instruments": sorted({x["symbol"] for x in rows})})
    return out


def _record(rows: list[dict[str, Any]], per_symbol: dict[str, dict[str, Any]],
            elapsed_s: float) -> dict[str, Any]:
    """Every finding gets a disposition: a DiscoveryObject in UNPROCESSED for the compiler, one
    research_memory row per instrument, and the generator's own yield line. Nothing is donated as
    a cell here -- which cells this discovery owes is `conversion_debt`'s answer, not a miner's."""
    conn = registry.connect()
    ids, created = [], 0
    try:
        for r in rows:
            did, is_new = registry.record_discovery(
                source_id=f"{SOURCE_TYPE}:{r['instrument']}:{r['cell']}", source_type=SOURCE_TYPE,
                origin="MOAT", generator=GENERATOR,
                mechanism=(f"{r['effect']['measure']} on the Fusion tape: {r['cell']} "
                           f"-> {r['suggested']}"),
                information="execution_microstructure", economic_rationale=RULE,
                assets=[r["instrument"]], horizons=[f"{r['effect']['horizon_s']}s"],
                sessions=[r["cell"].split("session=")[-1]],
                exact_rule_if_known=json.dumps({"cell": r["cell"], **r["effect"]}, sort_keys=True),
                required_data=["data/tape/ticks/<SYM>/<DAY>.parquet"], pit_requirements=["tape"],
                confidence=None, novelty=None,
                falsifier=("the same cell measured on later instrument-days no longer excludes "
                           "zero, or recurs on fewer than two instruments"),
                payload=r, conn=conn)
            registry.set_discovery_state(did, "UNPROCESSED", possible_cells=len(DVI_HORIZONS_S),
                                        conn=conn)
            ids.append(did)
            created += int(is_new)
        for sym, payload in sorted(per_symbol.items()):
            registry.remember(
                "execution_tape",
                (f"{sym}: {payload['cells']} tape cells over {payload['days']} instrument-days; "
                 f"{payload['n_significant_dvi']} timing cells and "
                 f"{payload['n_significant_adverse']} adverse-move cells excluded zero"),
                kind="execution_structure", memory_key=f"execution_structure:{sym}",
                # NEITHER OPTIONAL NOR FREE TEXT, whatever `CANON` says: the registry here was
                # RESTORED from the moat backup, whose real `research_memory` carries
                # `NOT NULL ... CHECK (result IN ('pending','success','failure'))`, and `_evolve`
                # only ADDS columns so the looser declaration never reached it. Two live runs died
                # here. `pending` is the honest word for cells that have not recurred.
                result="success" if payload["n_significant_dvi"] else "pending",
                metrics={k: payload[k] for k in ("days", "cells", "entries")},
                payload=payload, evidence={"source": SOURCE_TYPE, "rule": RECURRENCE_RULE},
                conn=conn)
        registry.generator_yield_update(GENERATOR, generated=created, compute_s=elapsed_s,
                                        conn=conn)
    finally:
        conn.close()
    return {"discovery_ids": ids, "new": created}


def run(*, budget_s: float = DEFAULT_BUDGET_S, days: int = DEFAULT_DAYS,
        symbols: list[str] | None = None, n_symbols: int = DEFAULT_SYMBOLS,
        dry_run: bool = False) -> dict[str, Any]:
    t0 = time.monotonic()
    deadline = t0 + budget_s
    index = mos.tape_index()
    wanted = symbols or select_symbols(index, n_symbols)
    unmeasured: list[str] = []
    store_seen, store_missing = 0, 0

    adverse_out: list[dict[str, Any]] = []
    dvi_out: list[dict[str, Any]] = []
    per_symbol: dict[str, dict[str, Any]] = {}
    days_used: set[str] = set()
    instrument_days, stopped = 0, False

    for sym in wanted:
        if sym not in index:
            unmeasured.append(f"{sym}: no tape directory")
            continue
        for series in ("realised_spread_session", "quote_intensity"):
            frame = mos.series_frame(series, sym)
            store_seen += int(not frame.empty)
            store_missing += int(frame.empty)
        rng = np.random.default_rng(SEED)
        sym_days = sorted(index[sym])[-days:]
        adv_acc: dict[tuple, dict[str, Any]] = {}
        dvi_acc: dict[tuple, dict[str, Any]] = {}
        entries_seen, cells_seen = 0, 0
        for day in sym_days:
            if time.monotonic() > deadline:
                stopped = True
                unmeasured.append(f"{sym} {day}: budget stopped before this instrument-day")
                break
            sp = second_path(index[sym][day])
            if sp is None:
                unmeasured.append(f"{sym} {day}: tape day too short or unreadable")
                continue
            masks = cell_masks(sp)
            if not masks:
                unmeasured.append(f"{sym} {day}: no cell reached {MIN_CELL_ENTRIES} entries")
                continue
            instrument_days += 1
            days_used.add(day)
            cells_seen = max(cells_seen, len(masks))
            entries_seen += int(sp["mid"].size // ENTRY_STRIDE_S)
            adv_rows, adv_pool = adverse_move_day(sp, masks, rng)
            for r in adv_rows:
                acc = adv_acc.setdefault((r["cell"], r["horizon_s"]),
                                         {"ind": [], "base_hits": 0.0, "base_n": 0,
                                          "days": 0, "days_significant": 0})
                acc["ind"].append(adv_pool[(r["cell"], r["horizon_s"])])
                acc["base_hits"] += r["baseline"] * r["n"]
                acc["base_n"] += r["n"]
                acc["days"] += 1
                acc["days_significant"] += int(r["significant"])
            dvi_rows, dvi_pool = delayed_vs_immediate_day(sp, masks, rng)
            for r in dvi_rows:
                acc = dvi_acc.setdefault((r["cell"], r["delay_s"], r["horizon_s"]),
                                         {"diffs": [], "days": 0, "days_significant": 0})
                acc["diffs"].append(dvi_pool[(r["cell"], r["delay_s"], r["horizon_s"])])
                acc["days"] += 1
                acc["days_significant"] += int(r["significant"])
            del sp, masks, adv_pool, dvi_pool

        sym_adverse = []
        for (c, h), a in adv_acc.items():
            x = np.concatenate(a["ind"])
            base = a["base_hits"] / a["base_n"]
            ci = block_bootstrap_ci(x, np.random.default_rng(SEED))
            sym_adverse.append({"symbol": sym, "cell": c, "horizon_s": h,
                                "p_adverse": float(x.mean()), "baseline": base, "n": int(x.size),
                                "ci": _ci(ci), "significant": _outside(ci, base),
                                "days": a["days"], "days_significant": a["days_significant"]})
        sym_dvi = []
        for (c, d, h), a in dvi_acc.items():
            x = np.concatenate(a["diffs"])
            ci = block_bootstrap_ci(x, np.random.default_rng(SEED))
            sym_dvi.append({"symbol": sym, "cell": c, "delay_s": d, "horizon_s": h,
                            "diff_bps": float(x.mean()), "ci": _ci(ci), "n": int(x.size),
                            "significant": _excludes_zero(ci),
                            "days": a["days"], "days_significant": a["days_significant"]})
        adverse_out.extend(sym_adverse)
        dvi_out.extend(sym_dvi)
        per_symbol[sym] = {
            "days": len(sym_days), "cells": cells_seen, "entries": entries_seen,
            "n_significant_dvi": sum(1 for r in sym_dvi
                                     if r["days_significant"] >= MIN_DAYS_SIGNIFICANT),
            "n_significant_adverse": sum(1 for r in sym_adverse
                                         if r["days_significant"] >= MIN_DAYS_SIGNIFICANT),
            "best_delay_bps": max((round(r["diff_bps"], 4) for r in sym_dvi), default=None),
        }
        if stopped:
            break

    if store_seen == 0 and store_missing:
        unmeasured.append("moat store data/moat/<series>/<SYM>.parquet is EMPTY -- the cells were "
                          "built from the tape directly, not from the derived series")

    discoveries = _discovery_rows(adverse_out, dvi_out)
    fills = fills_block(index, deadline=deadline, unmeasured=unmeasured)
    elapsed = time.monotonic() - t0
    recorded = ({"discovery_ids": [], "new": 0} if dry_run
                else _record(discoveries, per_symbol, elapsed))

    adverse_out.sort(key=lambda r: -abs(r["p_adverse"] - r["baseline"]))
    dvi_out.sort(key=lambda r: -abs(r["diff_bps"]))
    return {
        "at": _now(), "instruments": sorted(per_symbol), "days": sorted(days_used),
        "instrument_days": instrument_days,
        "grid": {"entry_stride_s": ENTRY_STRIDE_S, "horizons_s": list(HORIZONS_S),
                 "delays_s": list(DELAYS_S), "dvi_horizons_s": list(DVI_HORIZONS_S),
                 "signal_proxy": f"sign of the {MOMENTUM_S}s mid move",
                 "sessions": {k: list(v) for k, v in mos.SESSIONS.items()},
                 "bootstrap": {"draws": BOOT_DRAWS, "block_s": BOOT_BLOCK_S, "seed": SEED}},
        "adverse_move": [{k: (round(v, 6) if isinstance(v, float) else v) for k, v in r.items()}
                         for r in adverse_out[:MAX_REPORT_ROWS]],
        "adverse_move_rows_total": len(adverse_out),
        "delayed_vs_immediate": [{k: (round(v, 6) if isinstance(v, float) else v)
                                  for k, v in r.items()} for r in dvi_out[:MAX_REPORT_ROWS]],
        "delayed_vs_immediate_rows_total": len(dvi_out),
        "fills": fills,
        # TRIAL COUNT IS A SHARED COST (the two-lane order, 2026-09-06): the deflated-Sharpe charge
        # and the program SPA/PBO divide ONE family-wise budget, so a miner that does not declare
        # how wide it searched is spending someone else's error budget silently.
        "search_size": {"cells_tested": len(adverse_out) + len(dvi_out),
                        "effect_keys": len({(r["cell"], r["horizon_s"]) for r in adverse_out})
                        + len({(r["cell"], r["delay_s"], r["horizon_s"]) for r in dvi_out}),
                        "instrument_days": instrument_days,
                        "note": "the gauntlet charges these trials, not this artifact"},
        "discoveries": discoveries, "discoveries_recorded": len(recorded["discovery_ids"]),
        "discoveries_new": recorded["new"], "per_instrument": per_symbol,
        "moat_series_store": ("READ" if store_seen else "EMPTY -- fell back to the tape directly"),
        "unmeasured": unmeasured, "recurrence_rule": RECURRENCE_RULE,
        "budget_s": budget_s, "budget_stopped": stopped, "dry_run": dry_run,
        "elapsed_s": round(elapsed, 2), "next_gate": NEXT_GATE, "rule": RULE,
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="mine the execution tape for execution ALPHA")
    ap.add_argument("--budget-s", type=float, default=DEFAULT_BUDGET_S)
    ap.add_argument("--days", type=int, default=DEFAULT_DAYS)
    ap.add_argument("--symbols", type=str, default="")
    ap.add_argument("--n-symbols", type=int, default=DEFAULT_SYMBOLS)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--out", type=Path, default=None)
    a = ap.parse_args(argv)

    rep = run(budget_s=a.budget_s, days=a.days, n_symbols=a.n_symbols, dry_run=a.dry_run,
              symbols=[s.strip() for s in a.symbols.split(",") if s.strip()] or None)
    for r in rep["delayed_vs_immediate"][:8]:
        print(f"  {r['symbol']:<9}{r['cell']:<42} +{r['delay_s']:>3}s h={r['horizon_s']:>3}s "
              f"diff={r['diff_bps']:+8.4f}bps ci=[{r['ci'][0]:+.4f},{r['ci'][1]:+.4f}] n={r['n']}")
    print(f"\n{len(rep['instruments'])} instruments, {rep['instrument_days']} instrument-days, "
          f"{rep['adverse_move_rows_total']} adverse-move cells, "
          f"{rep['delayed_vs_immediate_rows_total']} timing cells, "
          f"{len(rep['discoveries'])} passed recurrence, {len(rep['unmeasured'])} unmeasured"
          + (" (BUDGET STOPPED)" if rep["budget_stopped"] else ""))
    if a.dry_run:
        print("--dry-run: nothing recorded in the registry, nothing written")
        return 0
    out = a.out or REPORT
    mos.write_report(rep, out)
    print(f"  -> {out}\nYIELD instrument_days={rep['instrument_days']} "
          f"discoveries={rep['discoveries_recorded']} new={rep['discoveries_new']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
