"""TWO MORE ENGINES FOR THE INDEPENDENT REPLICA: LEAN's gap-aware fills and Nautilus's bar path.

`libs/validation/independent_replica.py` rebuilds a certificate's signals and fills from its
frozen spec and the engine CONTRACT, and agrees or disagrees with the desk's implementation.
Both implement the SAME contract, so neither can say whether the contract itself flatters a
cell. This module extends the replica with two published fill semantics that differ from the
contract in exactly the places a bar backtest is least sure of, and replays the replica's own
signals through them (audit 2026-11-13: the `lean` and `nautilus` adapters were import probes;
this is the work they now do):

    lean_gap        LEAN's bar fill model. A stop the bar OPENS through fills at the OPEN, not at
                    the stop (the contract fills it at the stop: a gap's extra loss is never
                    charged). A take-profit the bar opens through fills at the OPEN too (better).
                    Otherwise the contract's intrabar rule: stop first when both are touched.
    nautilus_path   Nautilus's adaptive bar ordering. A bar is replayed as four prices -- open,
                    the NEARER of high and low, the other, close -- so a bar touching both stop
                    and target resolves by path instead of "stop always wins". Gaps fill at the
                    open as in lean_gap (a resting stop is triggered by the open price).

Both reuse the replica's bars, signals, cost arithmetic, rollover count and `compare`, and
change ONLY the exit resolution, so a difference is attributable to that one semantic. What the
report says per certificate: the contract's sum R, each engine's sum R, the difference, and the
trades whose exit moved -- e.g. "this cell's R owes 0.8 to filling gapped stops at the stop".

Nothing here imports `mt5desk`, `research` or `scripts` (the replica's rule, tested by AST), and
nothing here withdraws, vetoes or sizes anything. It is evidence for the family's owner.
"""
from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from typing import Any

import pandas as pd

from libs.validation import independent_replica as rep

ENGINES: tuple[str, ...] = ("lean_gap", "nautilus_path")


def _exit(semantics: str, side: int, j: int, fill_i: int, limit: bool, o: float, h: float,
          lo: float, stop: float, target: float) -> tuple[float, str] | None:
    """The exit on bar j under `semantics`, or None when the position survives the bar."""
    if j > fill_i:   # the fill bar's open is the entry, so no gap can occur on it
        gap_stop = o <= stop if side > 0 else o >= stop
        if gap_stop:
            return o, "stop_gap"
        gap_target = o >= target if side > 0 else o <= target
        if gap_target and not (limit and j == fill_i):
            return o, "target_gap"
    stopped = lo <= stop if side > 0 else h >= stop
    reached = (h >= target if side > 0 else lo <= target) and not (limit and j == fill_i)
    if not (stopped or reached):
        return None
    if stopped and reached and semantics == "nautilus_path":
        # open -> nearer extreme -> farther extreme -> close
        high_first = abs(h - o) <= abs(o - lo)
        stop_on_high = side < 0
        if high_first == stop_on_high:
            return stop, "stop"
        return target, "target"
    if stopped:
        return stop, "stop"
    return target, "target"


def simulate(df: pd.DataFrame, sigs: Sequence[rep.Sig], meta: Mapping[str, Any],
             semantics: str) -> list[rep.Fill]:
    """`independent_replica.simulate` with the exit resolution replaced by `semantics`.
    Entry, trigger, one-position-at-a-time, ttl and cost arithmetic are the replica's."""
    if semantics not in ENGINES:
        raise ValueError(f"unknown semantics {semantics!r}: {ENGINES}")
    o = df["open"].to_numpy(float)
    h = df["high"].to_numpy(float)
    lo = df["low"].to_numpy(float)
    ix = df.index
    pos = {t: i for i, t in enumerate(ix)}
    rt = rep.round_trip_price(meta)
    swap = rep.swap_price_per_night(meta)
    busy = -1
    out: list[rep.Fill] = []
    order = sorted(range(len(sigs)), key=lambda k: (pd.Timestamp(sigs[k].time), k))
    for k in order:
        s = sigs[k]
        i0 = pos.get(pd.Timestamp(s.time))
        if i0 is None:
            continue
        i = i0 + 1
        if i >= len(ix) - 1 or i <= busy:
            continue
        ref = o[i]
        if not (ref > 0):
            continue
        fill_i, entry, limit = i, ref, False
        if s.trigger is not None:
            limit = (s.side > 0 and s.trigger < ref) or (s.side < 0 and s.trigger > ref)
            hit = next((j for j in range(i, min(i + s.wait, len(ix)))
                        if lo[j] <= s.trigger <= h[j]), None)
            if hit is None:
                continue
            fill_i, entry = hit, float(s.trigger)
        levels = (entry, float(s.stop), float(s.target))
        if s.side not in (-1, 1) or not all(math.isfinite(x) for x in levels):
            continue
        precision = 8 * math.ulp(max(abs(x) for x in levels))
        unit = s.side * (entry - s.stop)
        if unit <= precision or s.side * (s.target - entry) <= precision:
            continue
        exit_px: float | None = None
        exit_i = -1
        why = "ttl"
        for j in range(fill_i, min(len(ix), fill_i + s.ttl)):
            got = _exit(semantics, s.side, j, fill_i, limit, float(o[j]), float(h[j]),
                        float(lo[j]), float(s.stop), float(s.target))
            if got is not None:
                exit_px, why = got
                exit_i = j
                break
        if exit_px is None:
            exit_i = min(fill_i + s.ttl, len(ix) - 1)
            exit_px = float(o[exit_i])
        busy = exit_i
        gross = s.side * (exit_px - entry) / unit
        nights = rep.rollovers(ix[fill_i], ix[exit_i]) if swap else 0.0
        cost = (rt + swap * nights) / unit
        out.append(rep.Fill(ix[fill_i], ix[exit_i], s.side, entry, float(exit_px), s.stop,
                            float(gross), float(cost), float(gross - cost), why))
    return out


def replay(df: pd.DataFrame, sigs: Sequence[rep.Sig], meta: Mapping[str, Any]
           ) -> dict[str, Any]:
    """The contract replica and both engines on the same signals; per engine the comparison
    against the contract and the R it moves."""
    import dataclasses
    base = [dataclasses.asdict(f) for f in rep.simulate(df, sigs, meta)]
    sum_base = sum(float(f["r"]) for f in base)
    out: dict[str, Any] = {"n_trades_contract": len(base), "sum_r_contract": round(sum_base, 6)}
    for eng in ENGINES:
        fills = [dataclasses.asdict(f) for f in simulate(df, sigs, meta, eng)]
        cmp = rep.compare(base, fills, tol_r=1e-6)
        s = sum(float(f["r"]) for f in fills)
        out[eng] = {"n_trades": len(fills), "sum_r": round(s, 6),
                    "delta_sum_r": round(s - sum_base, 6),
                    "mean_r": round(s / len(fills), 6) if fills else None,
                    "exits_moved": cmp["n_r_disagree"],
                    "gap_exits": sum(1 for f in fills if str(f["reason"]).endswith("_gap")),
                    "agree_with_contract": bool(cmp["agree"]),
                    "n_only_contract": cmp["n_only_original"],
                    "n_only_engine": cmp["n_only_replica"]}
    return out
