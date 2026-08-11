#!/usr/bin/env python3
"""LEDGER R0003 -- put the desk's own L2 tape through the AUDITED Stage-A screen.

WHAT WAS ACTUALLY MISSING, WHICH IS NOT WHAT THE ROW SAID. The row claimed
`libs/research/moat_microstructure.py` had zero callers and the moat had zero research artifacts.
Both are false as written: `scripts/run_moat_campaign.py` imports the module and is cron-scheduled
(ops/crontab.manifest, 04:10 daily), and `scripts/screen_moat.py` already screens a DIFFERENT
feature set (libs/hypmax/moat_mine.py) through `stage_a_screen`. What genuinely did not exist is
the intersection: moat_microstructure's DEPTH-IMBALANCE bars have never once been through the
audited de-contamination harness. Everything they have ever been scored by is
`run_moat_campaign.py`, which uses the autodiscovery gauntlet and has NO angle-20 gate at all --
and which reported an annualised Sharpe of 97.27 on 2026-08-02.

That number is the reason this file exists, and the leak probe below is why.

THE ALIGNMENT, DECLARED IN FULL, BECAUSE IT IS THE ENTIRE RISK.
`resample()` labels a bar with the START of its window and fills every book field with the MEAN
over that window. So for bar j covering W_j = [T_j, T_j + bar_ms):

    feature[j]  is an average over W_j        -> first fully observable at T_j + bar_ms
    mid[j]      is an average over W_j        -> a TWAP achievable by trading THROUGHOUT W_j

Those two facts together are a trap. A position decided from feature[j] cannot be filled at
mid[j], because mid[j] is the average price of the very window the feature was still being
measured in. Half of W_j's own move is inside that entry price.

This screen therefore LAGS THE SIGNAL BY ONE BAR and hands `stage_a_screen` contemporaneous
returns, which is the contract the harness documents and which `scripts/screen_moat.py` learned
the hard way (its bug #2: pre-forwarded returns get shifted twice):

    signal[i]     = feature over W_{i-1}          known at T_i
    target_ret[i] = mid[i] / mid[i-1] - 1         the return realised OVER period i
    -> harness predicts target_ret[i+1] = mid[i+1]/mid[i] - 1
    -> ENTRY is mid[i], a TWAP over W_i = [T_i, T_i + bar_ms), begun the instant the signal
       completes. Every price in the target window is at or after the signal's observation time.

Rows where bars i-1 and i are not adjacent on the bar_ms grid are DROPPED: the recorder stops and
restarts, and a 3-hour gap priced as a 1-minute return is not a horizon. Masking compacts the
series, so after a drop signal[t] is paired with a return from a LATER window -- that attenuates
an IC toward zero and can never leak, because the return still begins after the signal. The count
of breaks is reported per cell rather than buried.

THE LEAK PROBE. `moat_microstructure.bar_returns()` pays position p[i] the return
mid[i+1]/mid[i] - 1, i.e. it enters at mid[i] using a signal that is not complete until W_i ends.
Under the paragraph above that is a half-bar time machine, and it is the P&L path
`run_moat_campaign.py` scores. Rather than assert it, every symbol is run BOTH WAYS -- as the
module does it, and with the same positions lagged one bar -- and both Sharpes are reported.

EVERY CONSTRUCTION IS COUNTED, INCLUDING THE ONES THAT DIED. Five constructions x two bar sizes
are pre-registered below and all ten appear in the artifact whatever they print. Symbols are not a
hypothesis dimension: the whole recorded universe is screened (no symbol selection) and the
cross-symbol spread is what builds the standard error, so the family size is 10 and the Holm bar
is computed at m=10.

Stage A only. A pass earns a forward clock and NEVER capital.

    .venv/bin/python scripts/screen_moat_microstructure.py [--venue fut] [--max-symbols N]
"""
from __future__ import annotations

import argparse
import json
import math
import sys
import time
from pathlib import Path
from typing import Any

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

import numpy as np  # noqa: E402

from libs.research.axis_screen import stage_a_screen  # noqa: E402
from libs.research.moat_microstructure import (  # noqa: E402
    CANDIDATES,
    MOAT,
    Bar,
    bar_returns,
    partitions,
    read_partition,
    resample,
)
from libs.validation.forward_stats import holm_bar  # noqa: E402

OUT = Path("reports/moat_microstructure_screen.json")

BASE_MS = 60_000
#: Coarser grids are built by EXACT re-aggregation of the 60s bars (see `coarsen`), not by a
#: second pass over 1.2GB of gzip. Every Bar field is either an n_books-weighted mean or a sum, so
#: the coarsened bar is identical to what `resample(records, ms=coarse)` would have produced.
COARSEN = {60_000: 1, 300_000: 5}

#: zwin the harness uses internally. Mirrored here ONLY for the cost diagnostic, and the mirror is
#: checked against the harness's own `current_z` on every cell (`z_mirror_ok`).
ZWIN = 20

#: A screen needs enough paired rows for an IC to mean anything. 250 mirrors run_moat_campaign's
#: _MIN_BARS; below it the honest output is "no result", not "a weak result".
MIN_ROWS = 250


# -------------------------------------------------------------------------- tape -> bars

def _merge(group: list[Bar]) -> Bar:
    """Fold bars sharing a slot into one, EXACTLY as `resample` would have.

    Book fields are means over snapshots, so re-averaging them needs n_books weights; tfi is
    flow/volume, so flow must be reconstituted as tfi*volume before summing. Weighting these by
    anything else (or not at all) silently re-weights every coarse bar toward its quietest minute.
    """
    if len(group) == 1:
        return group[0]
    w = np.array([float(b.n_books) for b in group])
    tot = float(w.sum())
    if tot <= 0:
        return group[0]

    def _wm(vals: list[float]) -> float:
        return float(np.dot(w, np.array(vals, dtype="float64")) / tot)

    vol = float(sum(b.volume for b in group))
    flow = float(sum(b.tfi * b.volume for b in group))
    return Bar(t_ms=min(b.t_ms for b in group), mid=_wm([b.mid for b in group]),
               obi=_wm([b.obi for b in group]), obi_deep=_wm([b.obi_deep for b in group]),
               spread_bps=_wm([b.spread_bps for b in group]),
               slope=_wm([b.slope for b in group]),
               tfi=(flow / vol if vol > 0 else 0.0), volume=vol,
               depth_total=_wm([b.depth_total for b in group]), n_books=int(tot))


def coarsen(bars: list[Bar], *, base_ms: int, factor: int) -> list[Bar]:
    """Exact re-aggregation of base_ms bars onto a factor*base_ms grid."""
    if factor <= 1:
        return list(bars)
    step = base_ms * factor
    groups: dict[int, list[Bar]] = {}
    for b in bars:
        groups.setdefault((b.t_ms // step) * step, []).append(b)
    out = []
    for slot in sorted(groups):
        m = _merge(groups[slot])
        out.append(m._replace(t_ms=slot))
    return out


def load_bars(symbol: str, venue: str, *, bar_ms: int = BASE_MS) -> list[Bar]:
    """Every recorded partition for one symbol, folded into bars ONE PARTITION AT A TIME.

    `run_moat_campaign.load_bars` chains all 427 partitions into a single `resample`, which holds
    every snapshot of every minute of the whole archive in bucket lists at once -- several hundred
    MB for BTCUSDT on a 3GB box. Partitions are hourly and 60s slots nest inside an hour exactly,
    so resampling per partition and merging by slot is identical output at bounded memory. Slots
    are merged rather than concatenated because a recorder flush can put one minute in two files.
    """
    acc: dict[int, list[Bar]] = {}
    for p in partitions(symbol, venue):
        for b in resample(read_partition(p), ms=bar_ms):
            acc.setdefault(b.t_ms, []).append(b)
    return [_merge(acc[k]) for k in sorted(acc)]


# -------------------------------------------------------------------------- panel

def _pos_signal(name: str) -> Any:
    fn = CANDIDATES[name]
    return lambda bars: np.asarray(fn(bars), dtype="float64")


#: PRE-REGISTERED. Four depth-imbalance constructions plus one declared non-depth comparator.
#: `obi_deep` / `obi_touch` are the raw continuous imbalances (the harness z-scores them itself);
#: `obi_pressure` and `microprice_reversion` are the module's own ternary rules over the same
#: quantity, kept separate because a threshold rule is a different hypothesis from the level.
#: `flow_momentum` is NOT depth imbalance -- it is here because it is the construction
#: run_moat_campaign ranked top, so it is the benchmark this screen has to speak to.
CONSTRUCTIONS: dict[str, Any] = {
    "obi_deep": lambda bars: np.array([b.obi_deep for b in bars], dtype="float64"),
    "obi_touch": lambda bars: np.array([b.obi for b in bars], dtype="float64"),
    "obi_pressure": _pos_signal("obi_pressure"),
    "microprice_reversion": _pos_signal("microprice_reversion"),
    "flow_momentum": _pos_signal("flow_momentum"),
}

#: EXCLUDED BEFORE ANY NUMBER WAS SEEN, and recorded so the exclusion cannot be mistaken for a
#: silent failure. `liquidity_withdrawal` returns a 0/1 TRADE-OR-DON'T filter, not a direction.
#: `stage_a_screen` z-scores its input and asks which way it points; there is no reading of
#: "IC of a risk-off flag" that means anything. It is still exercised in the leak probe, where
#: P&L is the right question for it.
EXCLUDED = {"liquidity_withdrawal": ("risk filter (0/1 flat-or-trade), not a directional signal -- "
                                     "an IC on it has no interpretation; probed on P&L instead")}


def build_panel(bars: list[Bar], *, bar_ms: int) -> dict[str, Any]:
    """Signal panel + contemporaneous target + validity mask, on the declared alignment.

    Returns arrays of equal length N (= len(bars)) plus an `ok` mask. See the module docstring:
    signal[i] is the feature over bar i-1, target[i] is the return realised over period i, and the
    harness supplies the forward shift itself.
    """
    n = len(bars)
    t = np.array([b.t_ms for b in bars], dtype="int64")
    mid = np.array([b.mid for b in bars], dtype="float64")

    target = np.full(n, np.nan)
    if n >= 2:
        with np.errstate(divide="ignore", invalid="ignore"):
            target[1:] = np.where(mid[:-1] > 0, mid[1:] / mid[:-1] - 1.0, np.nan)

    # ADJACENCY IS PART OF THE TARGET'S DEFINITION, not a hygiene step. target[i] is only a
    # bar_ms return if bars i-1 and i are consecutive slots; the recorder gaps constantly.
    adjacent = np.zeros(n, dtype=bool)
    if n >= 2:
        adjacent[1:] = (t[1:] - t[:-1]) == bar_ms

    signals: dict[str, np.ndarray] = {}
    for name, fn in CONSTRUCTIONS.items():
        raw = np.asarray(fn(bars), dtype="float64")
        s = np.full(n, np.nan)
        if raw.size == n and n >= 2:
            s[1:] = raw[:-1]              # LAG ONE BAR: feature over W_{i-1}, known at T_i
        signals[name] = s

    base_ok = adjacent & np.isfinite(target)
    return {"t_ms": t, "mid": mid, "target": target, "adjacent": adjacent,
            "signals": signals, "base_ok": base_ok, "bar_ms": bar_ms}


def _screen_z(s: np.ndarray, zwin: int = ZWIN) -> np.ndarray:
    """Mirror of the trailing z-score inside `stage_a_screen`, for the cost diagnostic only.

    Checked against the harness's own `current_z` on every cell, so a future divergence in the
    harness shows up as `z_mirror_ok: false` instead of a quietly wrong turnover number.
    """
    z = np.zeros(len(s))
    for i in range(zwin, len(s)):
        w = s[i - zwin:i]
        sd = w.std()
        z[i] = (s[i] - w.mean()) / sd if sd > 0 else 0.0
    return z


def _cost_diagnostic(sig: np.ndarray, target: np.ndarray, spread_bps: np.ndarray) -> dict[str, Any]:
    """Is the gross edge bigger than the spread it has to cross to collect it?

    `stage_a_screen` reports IC and an annualised Sharpe on RAW returns; it has no cost model, and
    at 60s bars a sign-flipping rule pays the touch several hundred times a day. A cell that clears
    every floor gross and dies at half a spread is not an edge, so the comparison is made here
    rather than left to whoever reads the IC.
    """
    z = _screen_z(sig)
    pos = np.sign(z)[ZWIN:-1]
    fwd = np.roll(target, -1)[ZWIN:-1]
    if pos.size < 2:
        return {"gross_bps_per_bar": 0.0, "cost_bps_per_bar": 0.0, "net_positive": False}
    gross = float(np.mean(pos * fwd) * 1e4)
    turn = float(np.mean(np.abs(np.diff(np.concatenate([[0.0], pos])))))
    # Round trip crosses the half-spread on each side, so one unit of |position change| costs one
    # full spread. Using the cell's OWN measured spread, not a guess.
    cost = turn * float(np.nanmean(spread_bps)) * 0.5
    return {"gross_bps_per_bar": round(gross, 5), "turnover_per_bar": round(turn, 4),
            "mean_spread_bps": round(float(np.nanmean(spread_bps)), 4),
            "cost_bps_per_bar": round(cost, 5), "net_bps_per_bar": round(gross - cost, 5),
            "net_positive": bool(gross > cost), "current_z_mirror": round(float(z[-1]), 3)}


def screen_symbol(sym: str, bars: list[Bar], *, bar_ms: int) -> list[dict[str, Any]]:
    """Every pre-registered construction on one symbol at one bar size. All cells returned."""
    panel = build_panel(bars, bar_ms=bar_ms)
    hd = bar_ms / 86_400_000.0
    spread = np.array([b.spread_bps for b in bars], dtype="float64")
    cells: list[dict[str, Any]] = []
    for name, sig in panel["signals"].items():
        ok = panel["base_ok"] & np.isfinite(sig)
        n_ok = int(ok.sum())
        cell: dict[str, Any] = {"symbol": sym, "construction": name, "bar_ms": bar_ms,
                                "n": n_ok, "n_bars": len(bars),
                                "gap_breaks": int((~panel["adjacent"][1:]).sum())}
        if n_ok < MIN_ROWS:
            cell.update(verdict="NO-RESULT-TOO-SHORT",
                        why=f"{n_ok} paired rows < {MIN_ROWS}; not a weak result, no result")
            cells.append(cell)
            continue
        s_ok, r_ok = sig[ok], panel["target"][ok]
        if float(s_ok.std()) == 0.0:
            cell.update(verdict="DEGENERATE-CONSTANT",
                        why="the construction never varied on this cell")
            cells.append(cell)
            continue
        # THE SHARPE RAIL'S SUB-DAILY RESCALE LIVES IN THE HARNESS (stage_a_screen applies
        # sqrt(1/hd) itself whenever horizon_days<1). Passing a pre-rescaled ceiling here would
        # DOUBLE-rescale -- ~38x too loose at 60s, which kills the lookahead rail on exactly the
        # cells it exists for. The IC ceiling is left alone: a correlation does not annualise.
        res = stage_a_screen(s_ok, r_ok, name=f"{sym}:{name}:{bar_ms}ms", horizon_days=hd)
        cost = _cost_diagnostic(s_ok, r_ok, spread[ok])
        # HONEST POWER. The harness computes n_eff = n / horizon_days, which assumes overlapping
        # daily-sampled returns; at 60s bars horizon_days is 6.9e-4 so it MULTIPLIES n by 1440 and
        # `powered` comes back true for free. These bars are non-overlapping, so n_eff is n.
        mdi = 1.96 / math.sqrt(max(n_ok, 1))
        cell.update({k: v for k, v in res.items() if k != "name"})
        cell.update(cost)
        cell.update(n_eff_honest=n_ok, min_detectable_ic_honest=round(mdi, 5),
                    powered_honest=bool(mdi <= 0.03),
                    harness_n_eff_inflation=round(float(res.get("n_eff", n_ok)) / max(n_ok, 1), 1),
                    z_mirror_ok=bool(abs(cost["current_z_mirror"]
                                         - float(res.get("current_z", 0.0))) < 1e-3))
        cells.append(cell)
    return cells


# -------------------------------------------------------------------------- leak probe

def leak_probe(sym: str, bars: list[Bar], *, bar_ms: int) -> list[dict[str, Any]]:
    """Score every module candidate through `bar_returns` AS THE MODULE DOES IT, and lagged.

    `bar_returns` pays p[i] the move mid[i+1]/mid[i]-1, entering at mid[i] -- the MEAN mid of the
    window the signal is measured over. The lagged arm shifts positions one bar so entry is the
    first window that starts after the signal is complete. If the module's number survives the
    lag, the entry convention was harmless; if it collapses, `run_moat_campaign.py` has been
    scoring a time machine on cron since it was scheduled.
    """
    if len(bars) < MIN_ROWS:
        return []
    ppy = 365.0 * 24.0 * 3600_000.0 / bar_ms
    out = []
    for name, fn in CANDIDATES.items():
        pos = np.asarray(fn(bars), dtype="float64")
        lagged = np.concatenate([[0.0], pos[:-1]])

        def _sh(p: np.ndarray) -> float:
            r = bar_returns(p, bars)
            sd = float(np.std(r))
            return round(float(np.mean(r) / sd * math.sqrt(ppy)), 3) if sd > 0 else 0.0
        out.append({"symbol": sym, "candidate": name, "bar_ms": bar_ms,
                    "ann_sharpe_module_convention": _sh(pos),
                    "ann_sharpe_one_bar_lagged": _sh(lagged)})
    return out


# -------------------------------------------------------------------------- aggregation

def aggregate(cells: list[dict[str, Any]], m_hyp: int) -> list[dict[str, Any]]:
    """Cross-symbol panel read: symbols are replications, so they build the standard error.

    Screening 45 symbols is not 45 hypotheses -- it is one hypothesis measured 45 times. The
    family is (construction x bar size) = m_hyp, and the Holm bar is set at that m.
    """
    keys = sorted({(c["construction"], c["bar_ms"]) for c in cells})
    rows = []
    for name, bms in keys:
        ics = [float(c["ic"]) for c in cells
               if c["construction"] == name and c["bar_ms"] == bms and "ic" in c]
        nets = [float(c["net_bps_per_bar"]) for c in cells
                if c["construction"] == name and c["bar_ms"] == bms and "net_bps_per_bar" in c]
        if len(ics) < 2:
            rows.append({"construction": name, "bar_ms": bms, "n_symbols": len(ics),
                         "verdict": "NO-PANEL"})
            continue
        a = np.array(ics)
        se = float(a.std(ddof=1)) / math.sqrt(len(a))
        t = float(a.mean() / se) if se > 0 else 0.0
        rows.append({"construction": name, "bar_ms": bms, "n_symbols": len(a),
                     "mean_ic": round(float(a.mean()), 5), "std_ic": round(float(a.std(ddof=1)), 5),
                     "t_cross_symbol": round(t, 3),
                     "mean_net_bps_per_bar": round(float(np.mean(nets)), 5) if nets else None,
                     "n_symbols_net_positive": int(sum(x > 0 for x in nets))})
    ranked = sorted([r for r in rows if "t_cross_symbol" in r],
                    key=lambda r: -abs(float(r["t_cross_symbol"])))
    for i, r in enumerate(ranked, start=1):
        # Two-sided at alpha=0.05 => the one-sided helper is asked for 0.025.
        r["holm_bar_t"] = holm_bar(m_hyp, i, alpha=0.025)
        r["clears_holm"] = bool(abs(float(r["t_cross_symbol"])) >= float(r["holm_bar_t"]))
    return rows


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--venue", default="fut", help="fut | spot | bybit")
    ap.add_argument("--max-symbols", type=int, default=0, help="0 = every recorded symbol")
    ap.add_argument("--out", default=str(OUT))
    args = ap.parse_args()

    root = MOAT / args.venue
    symbols = sorted(d.name for d in root.iterdir() if d.is_dir()) if root.is_dir() else []
    if args.max_symbols > 0:
        symbols = symbols[:args.max_symbols]
    stamp = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    header: dict[str, Any] = {
        "generated": stamp, "ledger_row": "R0003", "venue": args.venue,
        "script": "scripts/screen_moat_microstructure.py",
        "stage": "A (zero promotion authority -- a pass earns a forward clock, never capital)",
        "alignment": {
            "bar_label": "resample() labels a bar with the START of its window",
            "bar_fields": "every book field is the MEAN over the window, not a close",
            "signal": "signal[i] = feature averaged over W_{i-1}; observable at T_i",
            "target": "target_ret[i] = mid[i]/mid[i-1] - 1 (CONTEMPORANEOUS, backward-labelled)",
            "forward_shift": "supplied by stage_a_screen itself (fwd = target_ret[i+1])",
            "entry_price": "mid[i] = TWAP over W_i, begun at T_i -- the instant signal[i] "
                           "completes. No price in the target window precedes the signal.",
            "gap_rule": "rows whose bar and its predecessor are not adjacent on the bar_ms grid "
                        "are dropped; masking attenuates IC and cannot leak",
        },
        "preregistration": {
            "constructions": sorted(CONSTRUCTIONS),
            "bar_ms": sorted(COARSEN),
            "excluded_before_seeing_numbers": EXCLUDED,
            "n_hypotheses": len(CONSTRUCTIONS) * len(COARSEN),
            "symbol_policy": "every recorded symbol on the venue; symbols are replications used "
                             "to build a standard error, NOT separate hypotheses",
        },
    }

    if not symbols:
        header.update(status="BLOCKED", blocker=f"no recorded symbols under {root}", cells=[])
        out_path.write_text(json.dumps(header, indent=2), "utf-8")
        print(f"BLOCKED: no recorded symbols under {root}")
        return 1

    cells: list[dict[str, Any]] = []
    probes: list[dict[str, Any]] = []
    tape: dict[str, Any] = {}
    t0 = time.time()
    for i, sym in enumerate(symbols, start=1):
        parts = partitions(sym, args.venue)
        base = load_bars(sym, args.venue, bar_ms=BASE_MS)
        tape[sym] = {"partitions": len(parts), "bars_60s": len(base),
                     "first": parts[0].name if parts else None,
                     "last": parts[-1].name if parts else None}
        for bms, factor in sorted(COARSEN.items()):
            bars = coarsen(base, base_ms=BASE_MS, factor=factor)
            cells.extend(screen_symbol(sym, bars, bar_ms=bms))
            probes.extend(leak_probe(sym, bars, bar_ms=bms))
        print(f"[{i}/{len(symbols)}] {sym}: {len(parts)} parts, {len(base)} 60s bars "
              f"({time.time() - t0:.0f}s)", flush=True)

    hist: dict[str, int] = {}
    for c in cells:
        hist[str(c.get("verdict"))] = hist.get(str(c.get("verdict")), 0) + 1
    panel = aggregate(cells, len(CONSTRUCTIONS) * len(COARSEN))

    leaked = [p for p in probes
              if abs(p["ann_sharpe_module_convention"]) > 3.0
              and abs(p["ann_sharpe_one_bar_lagged"]) < 0.5 * abs(p["ann_sharpe_module_convention"])]
    interesting = [c for c in cells if c.get("verdict") == "SCREEN-INTERESTING"]

    header.update({
        "status": "COMPLETE", "runtime_s": round(time.time() - t0, 1),
        "n_symbols": len(symbols), "n_cells": len(cells),
        "tape": tape, "verdict_histogram": hist,
        "panel": panel,
        "cells": cells,
        "leak_probe": {
            "what": "bar_returns() enters at mid[i], the MEAN mid of the window the signal is "
                    "measured over. The lagged arm enters one bar later, the first window that "
                    "starts after the signal completes.",
            "n_probes": len(probes),
            "n_collapsing_on_lag": len(leaked),
            "rows": probes,
        },
        "harness_power_note": (
            "stage_a_screen computes n_eff = n / (horizon_days * panel_width). That models "
            "OVERLAPPING daily-sampled returns; at sub-daily bars horizon_days < 1 so it "
            "MULTIPLIES n (1440x at 60s, 288x at 300s) and `powered` comes back true for free. "
            "These bars are non-overlapping, so n_eff is n. Every cell carries "
            "powered_honest/min_detectable_ic_honest computed from n directly."),
        "headline": (
            f"{len(interesting)} of {len(cells)} cells SCREEN-INTERESTING; "
            f"{len(leaked)}/{len(probes)} leak probes collapse under a one-bar lag"),
    })
    out_path.write_text(json.dumps(header, indent=2), "utf-8")

    print(f"\nverdicts: {hist}")
    print(f"{'construction':<24}{'bar_ms':>8}{'nsym':>6}{'mean_ic':>10}{'t':>8}"
          f"{'holm_t':>8}{'net+':>6}")
    for r in panel:
        if "mean_ic" not in r:
            continue
        print(f"{r['construction']!s:<24}{r['bar_ms']:>8}{r['n_symbols']:>6}"
              f"{float(r['mean_ic']):>10.4f}{float(r['t_cross_symbol']):>8.2f}"
              f"{float(r.get('holm_bar_t', 0)):>8.2f}{r['n_symbols_net_positive']:>6}")
    print(f"\nleak probe: {len(leaked)}/{len(probes)} collapse under one-bar lag")
    print(f"SCREEN-INTERESTING: {len(interesting)} of {len(cells)} cells")
    print(f"wrote {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
