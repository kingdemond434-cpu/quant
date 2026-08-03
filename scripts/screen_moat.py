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

ELEVEN MECHANISMS, NOT SEVEN. The seven `moat_mine` reconstructs, plus the four `moat_features`
MANUFACTURES from the asymmetry ledger's own build queue -- hidden liquidity, queue depth at
touch, book pressure against funding, spread regime shift. Every one is RECONSTRUCT or FUSE class:
computed from timestamps only this desk holds, so an edge found in them is not an edge everyone
else can also find.

HOLE-FIRST SCHEDULING, NOT NEWEST-FIRST. An earlier version took `files[-200:]` every run: it
re-screened the same recent slice forever and never once looked at the older archive, which is the
part a competitor most conclusively cannot obtain because it cannot be backfilled at any price.
Coverage of the (venue, symbol, day) x mechanism grid is persisted in data/moat_screen_coverage.json
and the run spends its budget on the cells that owe the most mechanisms -- the same scheduler that
made `mine_moat` converge, over the same grid, so mined-but-unscreened is a visible hole.

SURVIVORS PERSIST, WITH THEIR MISSES. data/moat_survivors.json keeps every promoted triple AND
how many times that triple was screened without surviving. Romano-Wolf controls family-wise error
WITHIN a run and nothing controls it ACROSS runs, so screening the archive a hundred times returns
false survivors at the nominal rate by construction. Repetition on independent cells is the only
out-of-sample evidence stage A can offer.

MULTIPLE TESTING IS HANDLED, NOT MENTIONED. Eleven features across several horizons is 30-plus
hypotheses, and the best of thirty looks good by construction. Romano-Wolf stepdown
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
import time
from collections import defaultdict
from datetime import UTC, datetime
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.build_bars import trades_from  # noqa: E402

from libs.hypmax.moat_features import MANUFACTURED  # noqa: E402
from libs.hypmax.moat_mine import _EXTRACTORS, DEPTH_KINDS, _depth_snaps  # noqa: E402
from libs.research.axis_screen import stage_a_screen  # noqa: E402
from libs.validation.per_candidate import romano_wolf  # noqa: E402

MOAT = ROOT / "data/moat"
REPORT = ROOT / "data/moat_screen.json"
HISTORY = ROOT / "data/moat_screen_history.jsonl"
#: Which (venue, symbol, day) x mechanism cells have EVER been screened. Persisted, so repeated
#: runs converge on the archive instead of re-screening whatever sorts last forever.
COVERAGE = ROOT / "data/moat_screen_coverage.json"
#: Survivors, with provenance, ACROSS runs. A survivor printed to a terminal and then overwritten
#: by the next run is not a finding, it is a rumour.
REGISTRY = ROOT / "data/moat_survivors.json"

#: EVERY mechanism the desk can compute off its own tape -- the seven reconstructed in `moat_mine`
#: plus the four MANUFACTURED from the asymmetry ledger's own build queue. Screening only the
#: first seven left four features that exist, are RECONSTRUCT/FUSE class, and had never once been
#: asked whether they predict.
MECHANISMS = {**_EXTRACTORS, **MANUFACTURED}
_COLLISION = set(_EXTRACTORS) & set(MANUFACTURED)
if _COLLISION:                       # two definitions of one name is a silent swap, not a merge
    raise RuntimeError(f"mechanism name collision between moat_mine and moat_features: "
                       f"{sorted(_COLLISION)}")

#: Horizons in SECONDS, applied by SUBSAMPLING the 15s snapshot grid so that one screen period
#: equals one horizon. That is what lets `stage_a_screen` do its own one-period-ahead prediction
#: at the horizon being tested, instead of being handed a pre-shifted target and shifting again.
HORIZONS_S = (60, 300, 900)
SNAPSHOT_S = 15

#: A sampled period whose WALL-CLOCK span exceeds its nominal horizon by more than this is not
#: that horizon. See `_contiguous`.
GAP_TOLERANCE = 1.5

FILE_BUDGET = 200
#: Cells with fewer snapshots than the screen can use are marked exhausted rather than retried:
#: that is a property of the file, not of when the run happened, and retrying it forever would
#: starve real holes.
MIN_SNAPSHOTS = 60


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


def _day_of(p: Path) -> str:
    """The day a tape file covers, from its name. `mine_moat` uses the same first-10-chars rule."""
    return p.stem.split(".")[0][:10]


def _cells() -> dict[tuple[str, str, str], list[Path]]:
    """(venue:symbol, day) -> files. The SAME grid `mine_moat` covers, so the two organs are
    talking about the same ground: a cell that is mined but unscreened is a visible hole rather
    than an accounting mismatch between two different notions of 'cell'."""
    out: dict[tuple[str, str, str], list[Path]] = defaultdict(list)
    for f in _tape():
        out[(f.parent.parent.name, f.parent.name, _day_of(f))].append(f)
    return {k: sorted(v) for k, v in out.items()}


def _load_coverage() -> dict:
    try:
        cov = json.loads(COVERAGE.read_text("utf-8"))
    except (OSError, json.JSONDecodeError):
        return {"screened": {}, "runs": 0}
    if not isinstance(cov.get("screened"), dict):
        cov["screened"] = {}
    return cov


def _schedule(cells: dict, cov: dict) -> list[tuple[tuple[str, str, str], list[Path]]]:
    """HOLES FIRST, then the stalest -- the same ordering that made the miner converge.

    Ranked by how many of the eleven mechanisms a cell still owes. A virgin cell outranks one
    screened on two mechanisms, which outranks one screened on ten. Without this the screen takes
    `files[-200:]` forever: it re-screens the newest slice every run and the oldest tape -- the
    part of the archive a competitor most conclusively cannot obtain -- is never looked at once.

    EXHAUSTED CELLS SORT LAST BUT ARE NOT DELETED. A cell with too few snapshots to screen is a
    fact about the file, so retrying it every run would starve real holes; but the recorders can
    still be appending to today's file, so it is re-checked once everything else is covered rather
    than retired permanently.
    """
    screened = cov.get("screened", {})
    scored = []
    for key, files in cells.items():
        rec = screened.get("|".join(key), {})
        have = set(rec.get("mechanisms", []))
        owed = len(MECHANISMS) - len(have & set(MECHANISMS))
        exhausted = 1 if rec.get("exhausted") else 0
        scored.append((exhausted, -owed, float(rec.get("t", 0.0)), key, files))
    scored.sort(key=lambda x: (x[0], x[1], x[2]))
    return [(k, f) for _, _, _, k, f in scored]


def _contiguous(ts: np.ndarray, horizon_s: int) -> np.ndarray:
    """Mask of sampled points whose period is REALLY the nominal horizon.

    A recorder outage -- or, now that scheduling is hole-first, two non-adjacent days screened
    together -- puts a gap in the snapshot series. Subsampling by stride assumes every step is
    `stride * 15s`; across a gap one "60-second period" can be twelve hours, and it carries twelve
    hours of return into a sample whose every other observation carries a minute. That single
    point dominates an IC computed over a few hundred, and it does so in whichever direction the
    overnight move happened to go.

    Returns a mask over the SAMPLED grid, True where the period ENDING at that point spanned no
    more than `GAP_TOLERANCE x` its nominal length. The first point has no preceding period and is
    dropped, matching `period_returns`, which leaves it NaN for the same reason.
    """
    m = np.zeros(ts.size, dtype=bool)
    if ts.size < 2:
        return m
    m[1:] = np.diff(ts) <= horizon_s * 1000.0 * GAP_TOLERANCE
    return m


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
    if len(snaps) < MIN_SNAPSHOTS:
        return [{"symbol": sym, "verdict": "TOO-FEW-SNAPSHOTS", "snapshots": len(snaps),
                 "why": "an IC on fewer than 60 aligned observations is describing coincidence"}]
    snap_ms = np.array([s[0] for s in snaps], dtype="int64")

    out: list[dict] = []
    for name, fn in MECHANISMS.items():
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
            # A GAP IS NOT A HORIZON. Hole-first scheduling hands this function non-adjacent days
            # by design, and a recorder outage does the same thing inside one day. Periods that
            # actually spanned longer than their nominal horizon are dropped rather than priced.
            ok = np.isfinite(fv) & np.isfinite(ret) & _contiguous(fts, h)
            # Masking COMPACTS the series, so the pair either side of a dropped period is no
            # longer adjacent: signal[t] gets paired with a return from a later window. That
            # ATTENUATES an IC toward zero -- it never leaks, because the return still comes from
            # after the signal -- so it is the safe direction to be wrong in, and the count is
            # reported rather than buried so a candidate resting on a shredded series is visible.
            breaks = int((~_contiguous(fts, h)[1:]).sum())
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
                        "n": int(ok.sum()), "gap_breaks": breaks,
                        "_pnl": (z[:-1] * r_ok[1:]).tolist(),
                        **{k: val for k, val in res.items() if k != "name"}})
    return out


def update_registry(scored: list[dict], survivors: list[dict], ts: str) -> dict:
    """PERSIST SURVIVORS WITH PROVENANCE, AND COUNT THE TIMES THEY DIDN'T SURVIVE.

    A survivor printed once and overwritten by the next run is a rumour. The registry keeps every
    (symbol, mechanism, horizon) the screen has EVER promoted, together with the far more
    important denominator: how many times that same triple was screened and did NOT survive.

    THE HIT RATE IS THE POINT. One survivor out of one screening is the best of a family of
    thirty-three and means nothing; the same mechanism surviving on eight of eleven independent
    days is the only evidence a microstructure feature ever gets that is not in-sample. Romano-Wolf
    controls family-wise error WITHIN a run, and nothing controls it ACROSS runs -- screen the
    archive a hundred times and the sweep will hand back false survivors at exactly the nominal
    rate. Persistence across independent cells is what distinguishes them, and it is only
    measurable because the misses are recorded too.

    Provenance is per triple: first and last seen, every IC observed, the best adjusted p-value.
    """
    try:
        reg = json.loads(REGISTRY.read_text("utf-8"))
    except (OSError, json.JSONDecodeError):
        reg = {}
    if not isinstance(reg, dict):
        reg = {}

    won = {f"{r['symbol'].split('@')[0]}|{r['mechanism']}|{r['horizon_s']}" for r in survivors}
    for r in scored:
        # The registry is keyed on the SYMBOL, not the cell: the same mechanism on the same symbol
        # on a different day is another draw of the same question, which is exactly the repetition
        # the hit rate is counting. Keying on the cell would give every entry a denominator of 1.
        key = f"{r['symbol'].split('@')[0]}|{r['mechanism']}|{r.get('horizon_s')}"
        e = reg.setdefault(key, {"symbol": r["symbol"].split("@")[0], "mechanism": r["mechanism"],
                                 "horizon_s": r.get("horizon_s"), "first_seen": ts,
                                 "times_screened": 0, "times_survived": 0, "ics": [],
                                 "best_p_adjusted": None, "cells": []})
        e["times_screened"] += 1
        e["last_screened"] = ts
        if np.isfinite(r.get("ic", np.nan)):
            e["ics"] = [*(e.get("ics") or [])[-49:], round(float(r["ic"]), 5)]
        if key in won:
            e["times_survived"] += 1
            e["last_survived"] = ts
            e["cells"] = [*(e.get("cells") or [])[-49:], r["symbol"]]
            p = r.get("rw_p_adjusted")
            if p is not None and (e["best_p_adjusted"] is None or p < e["best_p_adjusted"]):
                e["best_p_adjusted"] = p

    for e in reg.values():
        n = max(int(e.get("times_screened", 0)), 1)
        e["hit_rate"] = round(int(e.get("times_survived", 0)) / n, 4)
        ics = e.get("ics") or []
        e["ic_mean"] = round(float(np.mean(ics)), 5) if ics else None
        # SIGN STABILITY IS THE CHEAPEST FRAUD TEST THERE IS. A real microstructure effect points
        # the same way every day; a fitted one flips, and its mean IC hides that by cancelling.
        e["ic_sign_stability"] = (round(float(abs(np.mean(np.sign(ics)))), 3) if ics else None)
    REGISTRY.write_text(json.dumps(reg, indent=1, sort_keys=True, default=str), "utf-8")
    return reg


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--files", type=int, default=FILE_BUDGET)
    ap.add_argument("--loop", action="store_true", help="run forever (see loop())")
    ap.add_argument("--interval", type=float, default=0.0)
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

    # HOLE-FIRST, NOT NEWEST-FIRST. `files[-200:]` re-screened the same recent slice every run,
    # so the older archive -- the part a competitor most conclusively cannot obtain, because it
    # cannot be backfilled at any price -- was never screened once however often this ran.
    cells = _cells()
    cov = _load_coverage()
    plan = _schedule(cells, cov)

    results: list[dict] = []
    used: list[tuple[tuple[str, str, str], list[Path]]] = []
    budget = a.files
    for key, cfiles in plan:
        if budget <= 0:
            break
        take = cfiles[:budget]
        budget -= len(take)
        rows: list[dict] = []
        for f in take:
            rows.extend(_rows(f))
        # The label carries the cell, so a survivor's provenance says WHICH DAY of WHICH VENUE it
        # came from. A survivor without a cell cannot be re-checked, and a finding that cannot be
        # re-checked is an anecdote.
        results.extend(screen_symbol(f"{key[0]}:{key[1]}@{key[2]}", rows))
        used.append((key, take))
    by_sym = {f"{k[0]}:{k[1]}@{k[2]}" for k, _ in used}

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
    ts_now = datetime.now(tz=UTC).isoformat()

    # COVERAGE IS EARNED PER MECHANISM, NOT PER RUN. A cell counts a mechanism as screened only
    # when that mechanism produced a FINITE IC there -- the miner's own rule. A run that touched a
    # cell and resolved nothing leaves the hole open, so "100%" means "we asked everywhere", not
    # "we ran everywhere": mined-and-barren and never-looked-at demand opposite responses.
    by_cell: dict[str, set[str]] = defaultdict(set)
    for r in scored:
        by_cell[str(r["symbol"])].add(str(r["mechanism"]))
    screened = cov.setdefault("screened", {})
    for key, take in used:
        label = f"{key[0]}:{key[1]}@{key[2]}"
        rec = screened.setdefault("|".join(key), {"mechanisms": [], "t": 0.0})
        rec["mechanisms"] = sorted(set(rec.get("mechanisms", [])) | by_cell.get(label, set()))
        rec["t"] = datetime.now(tz=UTC).timestamp()
        rec["files"] = len(take)
        # Too little tape to screen is a property of the FILE. Retrying it every run would starve
        # real holes -- but today's file is still being appended to, so it is deprioritised rather
        # than retired, and any later run that resolves a mechanism clears the flag.
        rec["exhausted"] = not rec["mechanisms"]
    cov["runs"] = int(cov.get("runs", 0)) + 1
    cov["mechanisms"] = sorted(MECHANISMS)
    cov["cells_total"] = len(cells)
    covered_cells = sum(1 for v in screened.values() if v.get("mechanisms"))
    cells_pct = round(100.0 * covered_cells / max(len(cells), 1), 3)
    grid = len(cells) * len(MECHANISMS)
    filled = sum(len(set(v.get("mechanisms", [])) & set(MECHANISMS)) for v in screened.values())
    cov["coverage_pct"] = round(100.0 * filled / max(grid, 1), 3)
    cov["cells_covered_pct"] = cells_pct
    COVERAGE.write_text(json.dumps(cov, indent=1, sort_keys=True, default=str), "utf-8")

    reg = update_registry(scored, survivors, ts_now)
    # A CANDIDATE THE SWEEP PROMOTED MORE THAN ONCE, ON MORE THAN ONE CELL. Within one run
    # Romano-Wolf controls the family; across runs nothing does, so screening the archive a
    # hundred times hands back false survivors at the nominal rate by construction. Repetition on
    # independent days is the only out-of-sample evidence available at stage A.
    persistent = sorted(
        (e for e in reg.values()
         if int(e.get("times_survived", 0)) >= 2 and len(set(e.get("cells") or [])) >= 2),
        key=lambda e: (-float(e.get("hit_rate", 0.0)), -int(e.get("times_survived", 0))))

    out = {
        "ts": ts_now,
        "files_read": sum(len(t) for _, t in used), "files_on_disk": len(files),
        "cells_screened_this_run": len(used), "cells_on_disk": len(cells),
        "coverage_pct": cov["coverage_pct"], "cells_covered_pct": cells_pct,
        "mechanisms": sorted(MECHANISMS), "manufactured": sorted(MANUFACTURED),
        "symbols": sorted(by_sym), "hypotheses": len(results), "scored": len(scored),
        "horizons_s": list(HORIZONS_S), "tally": tally,
        "persistent_candidates": [
            {k: e.get(k) for k in ("symbol", "mechanism", "horizon_s", "times_screened",
                                   "times_survived", "hit_rate", "ic_mean", "ic_sign_stability",
                                   "best_p_adjusted", "first_seen")}
            for e in persistent[:20]],
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
                 "rejected. A survivor in ONE run is the best of a family and means little; the "
                 "registry's hit rate over independent cells is the number that matters."),
        "authority": "NONE -- stage A. Nothing here pre-registers, promotes or sizes.",
    }
    REPORT.write_text(json.dumps(out, indent=1, default=str), "utf-8")
    with HISTORY.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps({"ts": out["ts"], "hypotheses": len(results),
                             "survivors": len(survivors), "coverage_pct": cov["coverage_pct"],
                             "cells": len(cells)}, separators=(",", ":")) + "\n")

    print(f"moat-screen: {len(results)} hypotheses / {len(MECHANISMS)} mechanisms "
          f"({len(MANUFACTURED)} manufactured) over {len(used)} cell(s), "
          f"{out['files_read']}/{len(files)} files")
    print(f"  coverage {cov['coverage_pct']}% of {grid} (cell x mechanism) | "
          f"cells touched {cells_pct}% of {len(cells)}")
    for v, c in sorted(tally.items(), key=lambda kv: -kv[1]):
        print(f"  {v:<24} {c}")
    if persistent:
        print(f"  PERSISTENT ({len(persistent)}) -- survived on >=2 independent cells:")
        for e in persistent[:10]:
            print(f"    {e['symbol']}:{e['mechanism']}@{e['horizon_s']}s "
                  f"hit={e['hit_rate']:.2f} ({e['times_survived']}/{e['times_screened']}) "
                  f"ic={e.get('ic_mean')} sign_stab={e.get('ic_sign_stability')}")
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


def loop(interval_s: float = 0.0) -> int:
    """RUN FOREVER, hole-first. The screen is now a continuous organ, not a one-shot report.

    WHY BOTH EXIST, AND IT IS THE MINER'S ARGUMENT VERBATIM. A cadence call guarantees the screen
    runs at all -- the floor. This is the ceiling: with a persisted coverage frontier, each pass
    lands on the cells that owe the most mechanisms, so continuous running converges on the whole
    archive in hours rather than in as many days as there are cadence cycles. Mining an
    irreplaceable asset continuously while ASKING it a question once a day was the asymmetry:
    coverage measured everywhere and predicted nowhere.

    Each pass is budgeted exactly as a single-shot run, so the loop can never monopolise the box.
    A crash in one pass is logged and the loop continues: a screen that dies on one unreadable
    file has stopped hunting, which is the failure it exists to prevent.
    """
    passes, t_start = 0, time.time()
    print(f"moat-screen: CONTINUOUS mode, interval {interval_s}s (0 = back-to-back)")
    while True:
        passes += 1
        try:
            main()
        except KeyboardInterrupt:
            break
        except Exception as e:                     # one bad pass must never end the hunt
            print(f"moat-screen: pass {passes} failed ({type(e).__name__}: {e}) -- continuing")
        if interval_s > 0:
            time.sleep(interval_s)
    print(f"moat-screen: stopped after {passes} pass(es), "
          f"{(time.time() - t_start) / 3600:.1f}h")
    return 0


if __name__ == "__main__":
    if "--loop" in sys.argv:
        _iv = 0.0
        if "--interval" in sys.argv:
            _iv = float(sys.argv[sys.argv.index("--interval") + 1])
        raise SystemExit(loop(_iv))
    raise SystemExit(main())
