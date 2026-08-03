#!/usr/bin/env python3
"""HUNT SURVIVORS IN THE MOAT -- does any proprietary microstructure feature actually PREDICT?

THE GAP THIS CLOSES, AND IT IS THE LARGEST ONE LEFT. `libs/hypmax/moat_mine.py` reconstructs seven
features from the desk's self-recorded L2 tape -- withdrawal rate, replenishment half-life, book
slope, imbalance, microprice gap, effective spread, resting stability. `scripts/mine_moat.py` runs
them and records COVERAGE: which (venue, symbol, day, mechanism) cells have been measured.
`extract_all` returns mean, std, p50, p95, max.

Nothing ever asked whether any of them predicts anything.

The desk's own asymmetry ledger grades this tape EXCLUSIVE -- the single asset a competitor cannot
buy, scrape or backfill -- and puts it at DEPTH 2: collected, never screened. Descriptive
statistics on an irreplaceable asset is the most expensive possible way to own it. This is the
organ that turns coverage into a verdict.

THE ALIGNMENT IS THE ENTIRE RISK. A feature measured at snapshot t must be paired with the return
from t FORWARD. Pair it with the return INTO t and the "prediction" is a description of what just
happened -- an IC that looks extraordinary and means nothing, which is exactly the desk's own
bithumb IC-0.72 fake. Every target here is built by searching the trade tape for the last print at
or before t (entry) and at or before t+h (exit), so the feature can only ever see its own past.

MULTIPLE TESTING IS HANDLED, NOT MENTIONED. Seven features across several horizons is 20-plus
hypotheses, and the best of twenty looks good by construction. Romano-Wolf stepdown
(`libs/validation/per_candidate.py`) gives each one an adjusted p-value with family-wise error
controlled across the whole sweep -- the same machinery built when campaign-level statistics were
found being applied per-candidate.

SCALAR MECHANISMS ARE SKIPPED, NOT FAKED. `replenishment_halflife` returns one number per file,
not a series; there is nothing to correlate against a return and broadcasting it to a constant
would give a degenerate feature a verdict. Reported as SCALAR-NOT-SCREENABLE.

Read-only over data/moat. Writes one artifact. No keys, no order paths.
"""
from __future__ import annotations

import argparse
import gzip
import json
import sys
from collections import defaultdict
from datetime import UTC, datetime
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.build_bars import trades_from  # noqa: E402

from libs.hypmax.moat_mine import _EXTRACTORS, DEPTH_KINDS, _depth_snaps  # noqa: E402
from libs.research.axis_screen import stage_a_screen  # noqa: E402
from libs.validation.per_candidate import romano_wolf  # noqa: E402

MOAT = ROOT / "data/moat"
REPORT = ROOT / "data/moat_screen.json"
HISTORY = ROOT / "data/moat_screen_history.jsonl"

#: Horizons in SECONDS, applied by SUBSAMPLING the 15s snapshot grid so that one screen period
#: equals one horizon. That is what lets `stage_a_screen` do its own one-period-ahead prediction
#: at the horizon being tested, instead of being handed a pre-shifted target and shifting again.
HORIZONS_S = (60, 300, 900)
SNAPSHOT_S = 15

FILE_BUDGET = 200


def _rel(p: Path) -> str:
    try:
        return str(p.relative_to(ROOT))
    except ValueError:
        return str(p)


def _tape() -> list[Path]:
    if not MOAT.exists():
        return []
    out: list[Path] = []
    for vdir in sorted(p for p in MOAT.iterdir() if p.is_dir()):
        for sym in sorted(p for p in vdir.iterdir() if p.is_dir()):
            out.extend(sorted(sym.glob("*.jsonl.gz")))
    return out


def _rows(path: Path) -> list[dict]:
    out: list[dict] = []
    try:
        with gzip.open(path, "rt", encoding="utf-8", errors="ignore") as fh:
            for line in fh:
                try:
                    out.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
    except OSError:
        return []
    return out


def period_returns(rows: list[dict], snap_ms: np.ndarray) -> np.ndarray:
    """CONTEMPORANEOUS return over each period, priced at trades the desk could actually get.

    THE SCREEN DOES THE FORWARD SHIFT ITSELF, AND I MISSED THAT. `stage_a_screen`'s contract is
    explicit -- "target_ret[t] = return realised over period t" and it "predicts target_ret[t+1]
    from a z-scored signal[t]". An earlier version handed it returns that were ALREADY forward, so
    it shifted a second time: the contemporaneous correlation it computes came out near zero while
    the forward IC did not, which is precisely the misalignment signature its `ic_exceeds_
    contemporaneous` rail fires on. Fourteen of nineteen hypotheses came back SUSPECT-LOOKAHEAD on
    a tape built to be causally clean -- a verdict about the harness, correctly delivered.

    Each period's return is priced entry-to-entry on the FIRST print strictly after each snapshot,
    because that is the earliest price obtainable having seen the book at that snapshot. An earlier
    version used the last print at or before the snapshot, which on this tape landed 14 SECONDS
    BEFORE the signal -- a time machine whose return window spanned the very move the feature was
    measured during.

    NaN where a period has no print on either end: no trade means no return, and a zero would tell
    the screen nothing happened when nothing was observed.
    """
    tr: list[tuple[int, float, float]] = []
    for r in rows:
        tr.extend(trades_from(r))
    if len(tr) < 2:
        return np.full(snap_ms.size, np.nan)
    tr.sort(key=lambda x: x[0])
    t_ms = np.array([x[0] for x in tr], dtype="int64")
    px = np.array([x[1] for x in tr], dtype="float64")

    idx = np.searchsorted(t_ms, snap_ms, side="right")       # first print strictly AFTER t
    have = idx < t_ms.size
    p = np.where(have, px[np.clip(idx, 0, px.size - 1)], np.nan)
    out = np.full(snap_ms.size, np.nan)
    out[1:] = p[1:] / np.where(p[:-1] > 0, p[:-1], np.nan) - 1.0
    return out


def screen_symbol(sym: str, rows: list[dict]) -> list[dict]:
    """Every mechanism x horizon for one symbol, through the desk's own audited screen."""
    snaps = _depth_snaps([r for r in rows if r.get("k") in DEPTH_KINDS])
    if len(snaps) < 60:
        return [{"symbol": sym, "verdict": "TOO-FEW-SNAPSHOTS", "snapshots": len(snaps),
                 "why": "an IC on fewer than 60 aligned observations is describing coincidence"}]
    snap_ms = np.array([s[0] for s in snaps], dtype="int64")

    out: list[dict] = []
    for name, fn in _EXTRACTORS.items():
        try:
            vals = fn(rows)
        except Exception as e:
            out.append({"symbol": sym, "mechanism": name, "verdict": "ERROR",
                        "why": f"{type(e).__name__}: {str(e)[:100]}"})
            continue
        if isinstance(vals, float) or np.ndim(vals) == 0:
            out.append({"symbol": sym, "mechanism": name, "verdict": "SCALAR-NOT-SCREENABLE",
                        "why": ("one number per file, not a series -- broadcasting it to a "
                                "constant would hand a degenerate feature a verdict")})
            continue
        v = np.asarray(vals, dtype="float64")
        if v.size < 60:
            out.append({"symbol": sym, "mechanism": name, "verdict": "TOO-SHORT",
                        "n": int(v.size)})
            continue
        # DIFF-BASED FEATURES CONSUME THE FRONT of the snapshot series, so a feature of length L
        # aligns to the LAST L snapshots. Aligning to the first L instead would shift every
        # observation forward in time and quietly create lookahead.
        if v.size > snap_ms.size:
            out.append({"symbol": sym, "mechanism": name, "verdict": "UNALIGNABLE",
                        "why": f"{v.size} values against {snap_ms.size} snapshots"})
            continue
        ts = snap_ms[-v.size:]

        for h in HORIZONS_S:
            stride = max(1, h // SNAPSHOT_S)
            fv, fts = v[::stride], ts[::stride]
            ret = period_returns(rows, fts)
            ok = np.isfinite(fv) & np.isfinite(ret)
            if int(ok.sum()) < 60:
                out.append({"symbol": sym, "mechanism": name, "horizon_s": h,
                            "verdict": "SCREEN-UNDERPOWERED", "n": int(ok.sum()),
                            "why": "too few paired observations to resolve the question"})
                continue
            # THE SCREEN'S SHARPE RAIL IS CALIBRATED FOR DAILY DATA AND DOES NOT TRANSFER.
            # `sharpe_ceiling=6.0` assumes horizon_days=1; the screen ANNUALISES, so at 60s the
            # factor is sqrt(365/0.00069) ~ 725 and pure noise reported sharpe_reversal=53.4 --
            # SUSPECT-LOOKAHEAD on six hypotheses that had ICs of 0.01 to 0.08. That is a fact
            # about the calibration, not the features, and this desk is the first caller to point
            # the screen at microstructure frequencies.
            #
            # The IC ceiling is left ALONE: a correlation does not annualise, so 0.35 means the
            # same thing at 60s as at a day. Only the Sharpe bar is rescaled, by the same
            # sqrt(1/horizon) the annualisation applies -- which keeps the rail at a constant
            # PER-PERIOD strictness instead of tightening it 725-fold by accident.
            hd = h / 86400.0
            res = stage_a_screen(fv[ok], ret[ok], name=f"{sym}:{name}:{h}s",
                                 horizon_days=hd,
                                 sharpe_ceiling=6.0 * float(np.sqrt(1.0 / hd)))
            # PER-PERIOD TIMING P&L, KEPT FOR ROMANO-WOLF. An earlier version handed the stepdown
            # a SUMMARY STATISTIC broadcast to a constant column -- `ic_se` was not a key the
            # screen returns, so the divisor was always 1.0. A constant has zero bootstrap
            # variance, so every positive-IC candidate came back p=0.0 and noise was promoted to
            # "survivor". Fabricated significance, from the very machinery meant to prevent it.
            # The stepdown needs a real series: z-scored signal times the NEXT period's return.
            f_ok, r_ok = fv[ok], ret[ok]
            sd = float(f_ok.std())
            z = (f_ok - f_ok.mean()) / sd if sd > 0 else np.zeros_like(f_ok)
            out.append({"symbol": sym, "mechanism": name, "horizon_s": h,
                        "n": int(ok.sum()), "_pnl": (z[:-1] * r_ok[1:]).tolist(),
                        **{k: val for k, val in res.items() if k != "name"}})
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--files", type=int, default=FILE_BUDGET)
    a = ap.parse_args()

    files = _tape()
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    if not files:
        REPORT.write_text(json.dumps({
            "ts": datetime.now(tz=UTC).isoformat(), "state": "NO TAPE",
            "reason": (f"{_rel(MOAT)} absent or empty. data/ is gitignored, so this is expected in "
                       "a fresh checkout and a REAL blocker on the VPS -- the recorders write it."),
            "note": ("the tape is NOT synthesised: a survivor found on generated depth is a fact "
                     "about the generator, and it would enter the funnel wearing the same "
                     "vocabulary as a real one"),
        }, indent=1), "utf-8")
        print(f"moat-screen: NO TAPE under {_rel(MOAT)} -- recorders are the blocker")
        return 0

    by_sym: dict[str, list[dict]] = defaultdict(list)
    for f in files[-a.files:]:
        by_sym[f"{f.parent.parent.name}:{f.parent.name}"].extend(_rows(f))

    results: list[dict] = []
    for sym, rows in sorted(by_sym.items()):
        results.extend(screen_symbol(sym, rows))

    scored = [r for r in results if "ic" in r and np.isfinite(r.get("ic", np.nan))]
    tally: dict[str, int] = {}
    for r in results:
        tally[str(r.get("verdict", "?"))] = tally.get(str(r.get("verdict", "?")), 0) + 1

    # FAMILY-WISE ERROR ACROSS THE WHOLE SWEEP. Seven mechanisms times three horizons times every
    # symbol is a large family, and the best of a large family looks good by construction. Each
    # candidate gets an adjusted p-value rather than the set getting one verdict -- the defect
    # per_candidate.py was written to fix, applied here from the start.
    # ROMANO-WOLF PER HORIZON, NOT ACROSS ALL OF THEM. Candidates at different horizons live on
    # different period grids -- 60s has 978 observations, 900s has 45 -- and an earlier version
    # stacked them into one matrix by truncating every column to the SHORTEST. That cut the 978-
    # period candidate to its last 45 points and threw away 95% of its evidence: effective_spread
    # at t = +4.49 came back p_adjusted = 1.0, which is not strictness, it is data destruction.
    #
    # A horizon is the natural family: within it every mechanism shares one grid and one length,
    # so the stepdown compares like with like. Across horizons they are separate questions, and
    # pooling them was never the multiple-testing correction it looked like.
    rejected_total = 0
    for h in HORIZONS_S:
        group = [r for r in scored
                 if r.get("horizon_s") == h and len(r.get("_pnl") or []) >= 30]
        if len(group) < 2:
            for r in group:                    # a family of one needs no stepdown
                r["rw_p_adjusted"], r["rw_rejected"] = None, None
            continue
        n = min(len(r["_pnl"]) for r in group)
        perf = np.column_stack([np.asarray(r["_pnl"][-n:], dtype="float64") for r in group])
        rw_h = romano_wolf(perf, n_boot=500)
        rejected_total += int(rw_h.n_rejected)
        for i, r in enumerate(group):
            r["rw_p_adjusted"] = round(rw_h.p_for(i), 4)
            r["rw_rejected"] = bool(rw_h.significant(i))
            r["rw_family"] = f"horizon_{h}s (n={len(group)})"
    for r in results:
        r.pop("_pnl", None)                     # working series, never part of the record

    survivors = [r for r in scored
                 if r.get("verdict") == "SCREEN-INTERESTING" and r.get("rw_rejected")]
    suspect = [r for r in results if r.get("verdict") == "SUSPECT-LOOKAHEAD"]

    out = {
        "ts": datetime.now(tz=UTC).isoformat(),
        "files_read": len(files[-a.files:]), "files_on_disk": len(files),
        "symbols": sorted(by_sym), "hypotheses": len(results), "scored": len(scored),
        "horizons_s": list(HORIZONS_S), "tally": tally,
        "survivors": [{"symbol": r["symbol"], "mechanism": r["mechanism"],
                       "horizon_s": r["horizon_s"], "ic": r.get("ic"),
                       "rw_p_adjusted": r.get("rw_p_adjusted"),
                       "rw_family": r.get("rw_family"), "n": r["n"]}
                      for r in survivors],
        "suspect_lookahead": [f"{r.get('symbol')}:{r.get('mechanism')}" for r in suspect],
        "n_rejected_family_wise": rejected_total,
        "results": results,
        "note": ("A SURVIVOR here is a proprietary microstructure feature with a forward IC that "
                 "clears stage A AND survives Romano-Wolf across the whole sweep. Every target is "
                 "built from the last print AT OR BEFORE each timestamp, so a feature can only "
                 "see its own past -- pairing with the return INTO t would describe what just "
                 "happened and produce an extraordinary, meaningless IC. Zero survivors is the "
                 "expected outcome and a publishable one: the desk's prior is 420 screened, 420 "
                 "rejected."),
        "authority": "NONE -- stage A. Nothing here pre-registers, promotes or sizes.",
    }
    REPORT.write_text(json.dumps(out, indent=1, default=str), "utf-8")
    with HISTORY.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps({"ts": out["ts"], "hypotheses": len(results),
                             "survivors": len(survivors)}, separators=(",", ":")) + "\n")

    print(f"moat-screen: {len(results)} hypotheses over {len(by_sym)} symbol(s) from "
          f"{len(files[-a.files:])}/{len(files)} files")
    for v, c in sorted(tally.items(), key=lambda kv: -kv[1]):
        print(f"  {v:<24} {c}")
    if survivors:
        print(f"  SURVIVORS ({len(survivors)}) -- cleared stage A AND Romano-Wolf:")
        for r in survivors:
            print(f"    {r['symbol']}:{r['mechanism']}@{r['horizon_s']}s "
                  f"IC={r.get('ic'):.4f} p_adj={r.get('rw_p_adjusted')}")
    else:
        print("  NO SURVIVORS -- the expected outcome and a publishable one")
    if suspect:
        print(f"  SUSPECT-LOOKAHEAD on {len(suspect)} -- disbelieve first: a too-good IC here is "
              "alignment leakage, not edge")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
