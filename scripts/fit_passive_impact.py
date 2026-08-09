#!/usr/bin/env python3
"""R0267: fit the passive-fill impact model on the desk's OWN recorded tape, and say plainly
which half of it is identifiable.

WHAT THIS PRODUCES. `data/passive_impact.json`: the exponential fill-probability decay length
(`lam_bps`), the linear order-flow-imbalance price response (`beta_bps`), the combined passive
impact curve, and -- separately and always -- the verdict on whether either could be fitted from
the desk's own FILLS rather than from the book it quoted into.

THE TWO BASES ARE NEVER MIXED, and the labelling is the point.

  basis="counterfactual"  Estimated from ~13M recorded L2 snapshots in data/moat by placing a
                          HYPOTHETICAL quote at each recorded level and counting the volume that
                          actually traded through it. A real measurement of the book, and an
                          UPPER BOUND on fill probability -- it cannot see our own order's queue
                          position or any reaction to our presence.

  basis="own_fills"       What L1.11(b) actually asks for: an Execution Reality Model from our
                          own fills. REFUSED today, and `identifiability()` re-derives the reason
                          from the tape on every run rather than trusting a comment.

WHY THE OWN-FILL HALF REFUSES. The executor quotes at the touch on every order, so the placement
offset is a CONSTANT -- and no tape field records it in any case. A regressor with no variance
identifies no slope, so this does not improve with more fills; it needs an OFFSET ARM in the
excitation design. L1.45 named this remedy in general terms ("at an operating point the desk
never visits, say UNIDENTIFIED and go buy the observation"); this is that instruction applied to
the quote-distance axis, which excitation does not currently vary.

REFUSAL PATHS. NO-DATA (no tape), UNDERPOWERED (too few usable observations), UNIDENTIFIED (a
regressor with no variance, or a decay fitted with the wrong sign). A coefficient published from
too few points would step execution decisions on noise, which is strictly worse than leaving them
where they are.
"""

from __future__ import annotations

import argparse
import gzip
import json
import sys
from collections import defaultdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from libs.execution.book_walk import (  # noqa: E402
    book_from_row,
    fill_probability,
    queue_ahead_at,
)
from libs.execution.execution_tape import read as read_tape  # noqa: E402
from libs.execution.passive_impact import (  # noqa: E402
    fit_fill_decay,
    fit_ofi_response,
    identifiability,
    passive_impact_curve,
    signed_flow,
    window_ofi,
)
from libs.ops.denominator import caller_name  # noqa: E402
from libs.ops.fence_exit import fence_exit  # noqa: E402
from libs.ops.lawful import guard as _law_guard  # noqa: E402

MOAT = _ROOT / "data/moat"
REPORT = _ROOT / "data/passive_impact.json"

#: Files per symbol. The tape is 10.9GB; a fit does not need all of it, and a run that cannot
#: finish is a run that gets removed from the cadence.
FILE_BUDGET = 6
#: Symbols per venue directory, most-recent-first. Breadth beats depth for a book-level constant.
SYMBOL_BUDGET = 8
#: Seconds a hypothetical quote is allowed to rest before we ask whether it filled. Matches the
#: excitation design's SHORTEST arm (brief=15s) so the counterfactual answers a question the desk
#: can actually act on, rather than an arbitrary window.
REST_S = 15.0
#: Distance-from-mid buckets, in bps. The touch sits near 0; beyond ~50bps a passive quote on a
#: liquid perp is not a quoting decision, it is a limit order left overnight.
_EDGES_BPS = (0.0, 1.0, 2.0, 3.0, 5.0, 8.0, 12.0, 18.0, 26.0, 40.0, 60.0)
#: Window for the OFI -> forward-return regression.
OFI_WINDOW_MS = 10_000.0

_PASSING = frozenset({"OK"})


def _files(root: Path, *, symbols: int, per_symbol: int) -> list[Path]:
    """Most recent `per_symbol` hourly files for the `symbols` most recently written symbols."""
    if not root.is_dir():
        return []
    syms = sorted((d for d in root.iterdir() if d.is_dir()),
                  key=lambda d: d.name)[:symbols]
    out: list[Path] = []
    for s in syms:
        out.extend(sorted(s.glob("*.jsonl.gz"))[-per_symbol:])
    return out


def _read(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    try:
        with gzip.open(path, "rt", encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    rows.append(json.loads(line))
                except ValueError:
                    continue          # one corrupt line must not discard the hour
    except (OSError, EOFError):
        return []
    return rows


def _mid(bids: Any, asks: Any) -> float:
    return (float(bids.price[0]) + float(asks.price[0])) / 2.0


def _decay_observations(rows: list[dict[str, Any]]) -> list[tuple[float, float]]:
    """(distance_bps, fill_probability) for a hypothetical BUY quote at each recorded bid level.

    THE COUNTERFACTUAL, stated exactly. A passive BUY resting at price p on the bid side fills
    when SELL-aggressor volume trades down through p. So for each depth snapshot we take the
    queue resting at or better than p, then count the sell-aggressor volume at prices <= p over
    the next REST_S seconds, and ask `fill_probability` -- the same queue model the backtester
    uses -- what fraction of our own order that would have cleared.
    """
    depth = [r for r in rows if r.get("k") in ("d", "depth")]
    if not depth:
        return []
    t_trade, q_trade = signed_flow(rows)
    if t_trade.size == 0:
        return []
    if not np.any(q_trade < 0):               # aggressor sold -> price walks DOWN into the bids
        return []                             # no sell-side aggression: nothing could have filled

    # Trade prices are needed to know WHICH bid levels a sell walked through. signed_flow drops
    # price (it is a flow primitive), so recover it here alongside the same filter.
    px: list[float] = []
    ts: list[float] = []
    vol: list[float] = []
    for r in rows:
        if r.get("k") == "t" and bool(r.get("m")) is True and r.get("p") is not None:
            try:
                px.append(float(r["p"]))
                ts.append(float(r.get("t", 0.0)))
                vol.append(float(r.get("q", 0.0)))
            except (TypeError, ValueError):
                continue
        elif r.get("k") == "trades":
            for tr in r.get("v") or []:
                if str(tr.get("side", "")).upper() != "SELL":
                    continue
                try:
                    px.append(float(tr["price"]))
                    ts.append(float(tr.get("time", r.get("t", 0))))
                    vol.append(float(tr.get("size", 0.0)))
                except (TypeError, ValueError, KeyError):
                    continue
    if not px:
        return []
    tp = np.asarray(ts, dtype=float)
    pp = np.asarray(px, dtype=float)
    vv = np.asarray(vol, dtype=float)
    order = np.argsort(tp, kind="stable")
    tp, pp, vv = tp[order], pp[order], vv[order]

    obs: list[tuple[float, float]] = []
    for row in depth:
        book = book_from_row(row)
        if book is None:
            continue
        bids, asks = book
        if len(bids) == 0 or len(asks) == 0:
            continue
        try:
            mid = _mid(bids, asks)
        except (IndexError, ValueError):
            continue
        if mid <= 0:
            continue
        t0 = float(row.get("t", 0.0))
        lo, hi = np.searchsorted(tp, [t0, t0 + REST_S * 1000.0])
        if hi <= lo:
            continue
        win_px, win_v = pp[lo:hi], vv[lo:hi]
        # A typical desk clip, so the fill fraction is the one we would actually have seen.
        own = float(np.median(bids.size)) if len(bids) else 0.0
        if own <= 0:
            continue
        for lvl in range(len(bids)):
            p_lvl = float(bids.price[lvl])
            if p_lvl <= 0:
                continue
            dist = (mid - p_lvl) / mid * 1e4
            if dist < 0 or dist > _EDGES_BPS[-1]:
                continue
            through = float(win_v[win_px <= p_lvl].sum())
            # ZERO THROUGH-VOLUME IS AN OBSERVATION, NOT A MISSING ROW, and dropping it was a real
            # bug caught by the first live run (fitted slope came back POSITIVE: fill probability
            # apparently RISING with distance). Skipping levels the price never reached conditions
            # the deep buckets on precisely the moves that fill them -- conditioning on the
            # outcome. A level that was never touched has fill probability zero, and it has to
            # count, or every deep bucket is measured only on its best days.
            try:
                ahead = queue_ahead_at(bids, p_lvl, is_bid=True)
                pf = fill_probability(ahead, through, own_size=own)
            except ValueError:
                continue
            obs.append((dist, pf))
    return obs


def _ofi_observations(rows: list[dict[str, Any]]) -> list[tuple[float, float]]:
    """(OFI, forward mid return in bps) over fixed windows."""
    depth = [r for r in rows if r.get("k") in ("d", "depth")]
    if len(depth) < 3:
        return []
    t_tr, q_tr = signed_flow(rows)
    if t_tr.size == 0:
        return []
    mids: list[tuple[float, float]] = []
    for row in depth:
        book = book_from_row(row)
        if book is None:
            continue
        bids, asks = book
        if len(bids) == 0 or len(asks) == 0:
            continue
        try:
            mids.append((float(row.get("t", 0.0)), _mid(bids, asks)))
        except (IndexError, ValueError):
            continue
    if len(mids) < 3:
        return []
    mt = np.asarray([m[0] for m in mids], dtype=float)
    mv = np.asarray([m[1] for m in mids], dtype=float)
    t0, t1 = float(mt[0]), float(mt[-1])
    if t1 - t0 < 2 * OFI_WINDOW_MS:
        return []
    edges = np.arange(t0, t1, OFI_WINDOW_MS)
    if edges.size < 3:
        return []
    ofi = window_ofi(t_tr, q_tr, edges)
    idx = np.searchsorted(mt, edges, side="left").clip(0, mv.size - 1)
    ref = mv[idx]
    out: list[tuple[float, float]] = []
    for i in range(ofi.size):
        p0, p1 = float(ref[i]), float(ref[i + 1]) if i + 1 < ref.size else None
        if p1 is None or p0 <= 0:
            continue
        out.append((float(ofi[i]), (p1 - p0) / p0 * 1e4))
    return out


def build_report(root: Path | None = None) -> dict[str, Any]:
    """Pure enough to test: reads the tape, returns the surface, writes nothing."""
    base = root or _ROOT
    moat = base / "data/moat"
    paths: list[Path] = []
    for venue in ("fut", "spot", "bybit"):
        paths.extend(_files(moat / venue, symbols=SYMBOL_BUDGET, per_symbol=FILE_BUDGET))

    decay_obs: list[tuple[float, float]] = []
    ofi_obs: list[tuple[float, float]] = []
    n_files = 0
    for p in paths:
        rows = _read(p)
        if not rows:
            continue
        n_files += 1
        decay_obs.extend(_decay_observations(rows))
        ofi_obs.extend(_ofi_observations(rows))

    # Bucket the decay observations: a per-level scatter is dominated by the touch, where
    # hundreds of thousands of points sit. Bucketing gives each DISTANCE equal weight, which is
    # what the decay length is a property of.
    buckets: dict[int, list[float]] = defaultdict(list)
    for dist_bps, prob in decay_obs:
        b = int(np.searchsorted(_EDGES_BPS, dist_bps, side="right")) - 1
        if 0 <= b < len(_EDGES_BPS) - 1:
            buckets[b].append(prob)
    xs = [float((_EDGES_BPS[b] + _EDGES_BPS[b + 1]) / 2.0) for b in sorted(buckets)]
    ys = [float(np.mean(buckets[b])) for b in sorted(buckets)]

    decay = fit_fill_decay(xs, ys)
    resp = fit_ofi_response([o[0] for o in ofi_obs], [o[1] for o in ofi_obs])
    grid = [0.0, 1.0, 2.0, 5.0, 10.0, 20.0, 40.0]
    combined = passive_impact_curve(decay, resp, distance_bps=grid)

    # `root` must reach EVERY read, not just the first one. An organ that honours a test root for
    # some inputs and silently falls back to the live tree for others produces a report that is
    # part fixture and part production, and the mixture is invisible in the output.
    own = identifiability(read_tape(path=base / "data/moat/execution_tape/cashcarry_trades.jsonl"))

    if not paths:
        status, why = "NO-DATA", f"no recorded tape under {moat}"
    elif decay.ok and resp.ok:
        status, why = "OK", ""
    else:
        status = decay.status if not decay.ok else resp.status
        why = decay.why if not decay.ok else resp.why

    return {
        "generated": datetime.now(tz=UTC).isoformat(),
        "law": "L1.11b / L1.45 -- Execution Reality Model, and the excitation it still needs",
        "row": "R0267",
        "status": status,
        "why": why,
        "n_files_read": n_files,
        "n_decay_observations": len(decay_obs),
        # Published so the selection fix stays auditable: these are the levels the price never
        # reached in the window. They are ZEROS, not missing rows, and dropping them is what made
        # the first run report a positive slope.
        "n_zero_fill_observations": int(sum(1 for _, pf in decay_obs if pf <= 0.0)),
        "n_distance_buckets": len(xs),
        "n_ofi_windows": len(ofi_obs),
        "rest_seconds": REST_S,
        "ofi_window_ms": OFI_WINDOW_MS,
        "counterfactual": {
            "decay": decay.as_dict(),
            "response": resp.as_dict(),
            "curve": combined.as_dict(),
            "caveat": "UPPER BOUND on fill probability -- measured on the book AS IT EXISTED "
                      "WITHOUT OUR ORDER IN IT, so queue position and any reaction to our own "
                      "presence are unobservable by construction.",
        },
        "own_fills": {
            **own.as_dict(),
            "note": "This is the basis L1.11b actually asks for. It is refused, and the reason "
                    "is structural rather than a shortage of rows: more fills do not fix a "
                    "regressor with no variance. The enabling change is an OFFSET ARM in "
                    "data/excitation_design.json -- excitation varies maker_wait_s only.",
        },
    }


def main() -> int:
    _law_guard()
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--report-only", action="store_true",
                    help="write the artifact but always exit 0")
    ap.add_argument("--json", action="store_true", help="print the report")
    args = ap.parse_args()

    rep = build_report()
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text(json.dumps(rep, indent=1) + "\n", "utf-8")

    if args.json:
        print(json.dumps(rep, indent=1))
    else:
        d, r = rep["counterfactual"]["decay"], rep["counterfactual"]["response"]
        print(f"passive-impact: {rep['status']} -- {rep['n_files_read']} files, "
              f"{rep['n_decay_observations']} decay obs in {rep['n_distance_buckets']} buckets, "
              f"{rep['n_ofi_windows']} OFI windows")
        print(f"  fill decay   : {d['status']} lam={d['lam_bps']} p0={d['p0']} r2={d['r2']}")
        print(f"  OFI response : {r['status']} beta={r['beta_bps']} r2={r['r2']}")
        print(f"  own fills    : {rep['own_fills']['status']} -- {rep['own_fills']['why'][:120]}")
        if rep["why"]:
            print(f"  why          : {rep['why']}")

    if args.report_only:
        return 0
    return fence_exit(rep["status"], _PASSING, scanned=rep["n_distance_buckets"],
                      of="distance-from-mid buckets with observations",
                      fence=caller_name("fit_passive_impact"))


if __name__ == "__main__":
    sys.exit(main())
