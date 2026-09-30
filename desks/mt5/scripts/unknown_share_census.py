"""THE UNKNOWN-SHARE CENSUS: what fraction of the cells the judge builds come back UNKNOWN, and why.

WHY THIS EXISTS (2026-09-30). The gate ledger read 43% UNKNOWN over seven days on the box, the
desktop report 9.55%, and a hand-run 1,200-row census 34.8% -- three numbers over three
denominators, none of them reproducible by the next session. This is the reproducible one:

* a FIXED-SEED sample of docket cells (the hash of seed + cell key ranks every cell, so the same
  seed draws the same cells whatever the docket's row order, in O(n) memory), grouped exactly as
  `external_gauntlet.main` groups them;
* run through the JUDGE'S OWN PATH, read-only -- gate 0 (`partition_at_economic_prior`), the
  modifier preflight, `build_cell`, `daily_series`, `_series_trim_partial` at the chart's last
  complete day, the campaign lockbox carve (`gate_policy.lockbox_cut` / `carve_lockbox`, at the
  constitution's fraction when the sealed judge carries one) and, when the sealed judge carries
  it, the per-cell tail carve (`cell_lockbox_cut`) -- far enough to know whether each cell reaches
  the 60 development days CPCV needs;
* THE DENOMINATOR IS JUDGED (BUILT) CELLS, the basis `judge_coverage.unknown_share` and the gate
  ledger use. Gate-0 rejects, modifier refusals and build failures never reach the judge and are
  reported beside it, by name, never folded in;
* every UNKNOWN is named: the judge's own classification (`classify_unknown` when the sealed
  judge carries it, the identical rule here when it does not, so a before/after reading compares
  like with like) plus a finer cause -- the peer/driver/factor input the cell never named, the
  session window that excludes the hour the family fires, the session that thins a firing cell
  below 60, the external input that is absent on this host.

THE INPUT-COMPLETION SIBLINGS. `discovery_compiler.complete_inputs` does not rewrite a peerless
row; it mints a sibling with the input named, and the original stays in the docket. With
`--complete-inputs` every sampled peerless row is put through `complete_inputs` exactly as the
compiler does on the box, the sibling is built and judged like any other cell, and the report
gives the share over the sampled cells alone AND over cells + siblings.

`--overlay DIR` loads the modules found under DIR (paths relative to `desks/mt5`, e.g.
`research/discovery_compiler.py`) IN PLACE OF the tree's own, so a BEFORE reading can run the
pre-fix versions (`git show <rev>:<path>`) without touching the checkout.

BOUNDED: the sample is sized from measured free memory (psutil) unless `--n` is given, the build
stops at `--budget-s` or at an RSS cap derived from free memory, and the frames go through the
judge's own row-bounded LRU. Nothing is written unless `--out` is given.
"""
from __future__ import annotations

import argparse
import hashlib
import heapq
import importlib.util
import json
import math
import sys
import time
from collections import Counter
from pathlib import Path
from typing import Any

DESK = Path(__file__).resolve().parents[1]
BASE = DESK.parents[1]
for _p in (str(BASE), str(DESK), str(DESK / "scripts")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

#: CPCV's floor -- the `< 60` in `run_gauntlet`.
NEED_DAYS = 60
#: Families whose identity names another instrument, and the key that names it. Mirrors
#: `judge_coverage.REQUIRED_INPUT_KEY` (= the compiler's PEER_KEY_BY_FAMILY + FACTOR_FAMILIES +
#: LEG_FAMILIES); the test pins them together.
INPUT_KEY: dict[str, str] = {"relative_value": "peer_symbol",
                             "correlation_regime": "peer_symbol",
                             "lead_lag": "driver_symbol",
                             "cross_asset_residual": "factor_symbols",
                             "pca_residual": "factor_symbols",
                             "triangle": "leg_b_symbol"}
#: Families conditioned on an external series `build_cell` loads for them.
EXTERNAL_INPUT_FAMILIES = frozenset({"cot_positioning", "macro_conditional", "liquidity_regime",
                                     "orderflow_imbalance", "event_reaction"})
#: Per sampled cell (its daily series and record; signals are released as it is built).
#: Measured 2026-09-30: 1,662 cells peaked at 735 MB RSS including the frame cache -- ~0.2 MB a
#: cell -- so 0.5 is generous and a 16 GB container fits a few thousand.
PER_CELL_MB = 0.5
#: The judge's own row-bounded frame cache, at its worst (1.3M rows x ~6 float columns).
FRAME_CACHE_MB = 400.0


def wilson(k: int, n: int, z: float = 1.96) -> tuple[float, float] | None:
    """95% Wilson score interval for k of n, or None for n == 0 (an empty sample is UNMEASURED)."""
    if n <= 0:
        return None
    p = k / n
    den = 1.0 + z * z / n
    mid = (p + z * z / (2 * n)) / den
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / den
    return (round(max(0.0, mid - half), 4), round(min(1.0, mid + half), 4))


def classify(dev: Any, pre_carve_days: int | None, n_signals: int | None, *,
             errored: bool = False, need: int = NEED_DAYS) -> str:
    """The judge's UNKNOWN classification (`external_gauntlet.classify_unknown`, sealed patch
    `unknown_verdict_named`), restated so an UNPATCHED judge is read on the same scale."""
    if dev is None:
        return "series_exception" if errored else "no_series"
    if (pre_carve_days or 0) >= need:
        return "lockbox_consumed_history"
    if len(dev) == 0:
        return ("no_trades" if n_signals is None else
                "no_signals" if n_signals == 0 else "signals_no_trades")
    return "too_rare"


def build_failure_kind(why: str) -> str:
    """A build failure's class, with the symbol stripped so the table aggregates."""
    w = str(why or "")
    if w.startswith("NOT_RUN_MODIFIER"):
        return "modifier_refused"
    if " raised " in w:
        return "family_raised:" + w.split(" raised ", 1)[1].split(":", 1)[0]
    if w.startswith("factor basket incomplete"):
        return "factor_basket_incomplete"
    if "no peer_symbol" in w:
        return "no_peer_symbol_named"
    if "no driver_symbol" in w:
        return "no_driver_symbol_named"
    if "driver missing" in w:
        return "no_bars_for_driver"
    if "no microstructure surface" in w:
        return "no_microstructure_surface"
    if "no event calendar" in w:
        return "no_event_calendar"
    if w.startswith("no ") and " bars for peer " in w:
        return "no_bars_for_peer"
    if w.startswith("no ") and " bars for " in w:
        return "no_bars:" + w.split()[1]
    if w.startswith("no implementation of family"):
        return "no_family_implementation"
    if w.startswith("input load failed"):
        return "input_load_failed:" + w.split(":", 2)[1].strip()
    return w[:60] or "unnamed"


def sample_key(seed: int, key: str) -> int:
    return int.from_bytes(hashlib.sha256(f"{seed}:{key}".encode()).digest()[:8], "big")


def docket_sample(path: Path, n: int, seed: int, iter_rows: Any,
                  timeframe_of: Any) -> tuple[list[dict[str, Any]], int]:
    """The `n` cells with the smallest seeded hash, grouped the way `external_gauntlet.main` does
    (row chart folded into params, key `sym.family.params`). Returns (cells, unique cells seen)."""
    heap: list[tuple[int, str, dict[str, Any]]] = []
    seen: set[str] = set()
    for h in iter_rows(path):
        if not isinstance(h, dict):
            continue
        sym, fam = h.get("symbol"), h.get("family")
        if not sym or not fam:
            continue
        params = dict(h.get("params") or {})
        row_tf = str(h.get("timeframe") or "").upper()
        if row_tf and row_tf != "H1" and "timeframe" not in params:
            params["timeframe"] = row_tf
        key = f"{sym}.{fam}.{json.dumps(params, sort_keys=True, default=str)}"
        if key in seen:
            continue
        seen.add(key)
        rank = sample_key(seed, key)
        spec = {"sym": sym, "family": fam, "params": params, "key": key,
                "timeframe": timeframe_of(params, str(fam)), "row": h}
        item = (-rank, key, spec)
        if len(heap) < n:
            heapq.heappush(heap, item)
        elif -rank > heap[0][0]:
            heapq.heapreplace(heap, item)
    cells = [s for _r, _k, s in sorted(heap, key=lambda t: (-t[0], t[1]))]
    return cells, len(seen)


def load_overlay(overlay: Path) -> list[str]:
    """Pre-load every module under `overlay` (paths relative to `desks/mt5`) under its package
    name, so later imports resolve to the overlay's version. Returns the module names loaded.

    A file under `scripts/` loads as a top-level module (that directory is on the path), so a
    patched `scripts/external_gauntlet.py` replaces the judge. Each module's `__file__` is set to
    the TREE's path before it executes: the desk derives its data roots from `__file__`
    (`BASE = Path(__file__).parents[3]`), and a module that believed it lived in the overlay
    would read an empty universe and measure nothing."""
    loaded: list[str] = []
    for f in sorted(overlay.rglob("*.py")):
        rel = f.relative_to(overlay).with_suffix("")
        if "__pycache__" in rel.parts:
            continue
        name = rel.name if rel.parts[0] == "scripts" else ".".join(rel.parts)
        spec = importlib.util.spec_from_file_location(name, f)
        if spec is None or spec.loader is None:
            continue
        mod = importlib.util.module_from_spec(spec)
        mod.__file__ = str(DESK / f.relative_to(overlay))
        sys.modules[name] = mod
        spec.loader.exec_module(mod)
        parent, _, child = name.rpartition(".")
        if parent and parent in sys.modules:
            setattr(sys.modules[parent], child, mod)
        loaded.append(name)
    return loaded


def coarse_proxy(eg: Any) -> None:
    """OPT-IN: serve an H4/D1 chart this host does not hold by resampling its H1 parquet, so the
    census can reach the coarse cells the box builds from its own bars. Reported as a proxy."""
    import pandas as pd
    orig = eg._live_frame
    rule = {"H4": "4h", "D1": "1D"}

    def _proxy(sym: str, timeframe: str = "H1"):
        tf = str(timeframe).upper()
        pq = eg.UNI / f"{sym}_H1.parquet"
        if tf not in rule or not pq.exists():
            return orig(sym, timeframe)
        h1 = eg.families._h1(pd.read_parquet(pq))
        agg = {c: f for c, f in (("open", "first"), ("high", "max"), ("low", "min"),
                                  ("close", "last"), ("volume", "sum"),
                                  ("tick_volume", "sum"), ("spread", "mean"))
               if c in h1.columns}
        out = h1.resample(rule[tf]).agg(agg).dropna(subset=["close"])
        return out if len(out) else None

    eg._live_frame = _proxy


def _input_absent(eg: Any, fam: str, sym: str, frame: Any, tf: str) -> str | None:
    """Name the external input a no-signal cell's family was handed empty, or None."""
    try:
        from research import orthogonal_sweep as inputs
        if fam == "cot_positioning":
            x = inputs._cot_frame(sym)
        elif fam == "macro_conditional":
            x = inputs._macro_series(frame.index)
        elif fam in ("liquidity_regime", "orderflow_imbalance"):
            spread, flow = inputs._tape_series(sym, frame.index, tf)
            x = spread if fam == "liquidity_regime" else flow
        elif fam == "event_reaction":
            x = inputs._event_index()
        else:
            return None
    except Exception as exc:
        return f"input_absent:{fam}:{type(exc).__name__}"
    if x is None:
        return f"input_absent:{fam}"
    try:
        if len(x) == 0:
            return f"input_absent:{fam}"
    except TypeError:
        pass
    return None


def measure(cells: list[dict[str, Any]], *, meta: dict[str, Any], eg: Any, budget_s: float,
            rss_cap_mb: float, lockbox_cut_override: str | None = None) -> dict[str, Any]:
    """Run each spec down the judge's path; return per-cell records and the sweep's lockbox cut."""
    import pandas as pd
    import psutil
    from research.gate_policy import LOCKBOX_FRAC, carve_lockbox, lockbox_cut
    proc = psutil.Process()
    records: list[dict[str, Any]] = []
    specs = [{"sym": c["sym"], "family": c["family"], "params": dict(c["params"]),
              "timeframe": c["timeframe"], "_src": c} for c in cells]
    eligible, rejected = eg.partition_at_economic_prior(specs, meta)
    # `partition_at_economic_prior` builds fresh reject dicts, so the sibling flag is matched back
    # by position: it walks `specs` in order and every spec lands on exactly one side.
    kept = {id(s) for s in eligible}
    for spec, r in zip([s for s in specs if id(s) not in kept], rejected, strict=True):
        records.append({"stage": "gate0", "reason": r.get("terminal_gate"),
                        "sym": r.get("sym"), "family": r.get("family"),
                        "sibling": bool(spec["_src"].get("sibling"))})
    t0 = time.monotonic()
    series: list[Any] = []
    built: list[dict[str, Any]] = []
    for spec in eligible:
        fam, sym, params = str(spec["family"]), str(spec["sym"]), spec["params"]
        rec: dict[str, Any] = {"sym": sym, "family": fam, "tf": spec["timeframe"],
                               "sibling": bool(spec["_src"].get("sibling")),
                               "key": spec["_src"]["key"], "session": params.get("session")}
        why = eg.modifier_preflight(spec)
        if why:
            rec.update(stage="preflight_refused", reason="modifier_refused", why=why[:160])
            records.append(rec)
            continue
        if time.monotonic() - t0 > budget_s or proc.memory_info().rss / 2**20 > rss_cap_mb:
            rec.update(stage="deferred", reason="census_budget")
            records.append(rec)
            continue
        frame = eg._bars_for(sym, spec["timeframe"])
        if frame is None or len(frame) == 0:
            rec.update(stage="build_failed", reason=f"no_bars:{spec['timeframe']}")
            records.append(rec)
            continue
        last_day = frame.index[-1].normalize()
        tb = time.monotonic()
        try:
            obj = eg.build_cell(sym, fam, params, meta)
        except Exception as exc:          # the judge's build raising is itself a finding
            obj = None
            eg.LAST_BUILD_FAILURE = f"{fam} raised {type(exc).__name__}: {str(exc)[:160]}"
        if not obj:
            fail = str(eg.LAST_BUILD_FAILURE or "parquet missing or build failed")
            rec.update(stage="build_failed", reason=build_failure_kind(fail), why=fail[:160],
                       build_s=round(time.monotonic() - tb, 2))
            records.append(rec)
            continue
        rec["n_signals"] = len(obj.get("sigs") or [])
        try:
            ds = eg._series_trim_partial(eg.daily_series(obj["df"], obj["sigs"], obj["costs"]),
                                         last_day)
            rec["errored"] = False
        except Exception as exc:
            ds = None
            rec["errored"] = True
            rec["series_error"] = f"{type(exc).__name__}: {str(exc)[:160]}"
        obj.clear()
        rec.update(stage="built", build_s=round(time.monotonic() - tb, 2),
                   pre_carve_days=None if ds is None else len(ds))
        rec["_spec"] = spec
        series.append(ds)
        built.append(rec)
        records.append(rec)

    # THE CAMPAIGN CARVE, as `run_gauntlet` takes it: one calendar cut from the union of every
    # built cell's days, at the constitution's lockbox fraction when the sealed judge has one.
    frac = LOCKBOX_FRAC
    if hasattr(eg, "constitution_thresholds"):
        try:
            frac = float(eg.constitution_thresholds(LOCKBOX_FRAC)["lockbox_min_fraction"])
        except Exception:
            frac = LOCKBOX_FRAC
    cut = (pd.Timestamp(lockbox_cut_override).date() if lockbox_cut_override
           else lockbox_cut(series, frac=frac))
    dev, _held = carve_lockbox(series, cut)
    # THE PER-CELL CARVE, by the judge's own rule when it has one: `cell_dev_cut` (the re-chained
    # sealed patch, shared by the sharded and unsharded sweep), else `cell_lockbox_cut` (its first
    # form), else none -- an unpatched judge carves every cell at the campaign cut.
    dev_cut = getattr(eg, "cell_dev_cut", None)
    own_cut = getattr(eg, "cell_lockbox_cut", None)
    carved_own = 0
    for i, rec in enumerate(built):
        d = dev[i]
        if cut is not None and series[i] is not None and d is not None and \
                len(d) < NEED_DAYS and (dev_cut is not None or own_cut is not None):
            own = (dev_cut(series[i], cut, frac=frac) if dev_cut is not None
                   else own_cut(series[i]))
            if own is not None and own > cut:
                s = series[i]
                d = s[s.index < own]
                rec["cut_basis"] = "cell_own_tail"
                carved_own += 1
        rec["dev_days"] = None if d is None else len(d)
        if d is not None and len(d) >= NEED_DAYS:
            rec["verdict"] = "judgeable"
            continue
        rec["verdict"] = "UNKNOWN"
        judge_classify = getattr(eg, "classify_unknown", None)
        args = (d, rec.get("pre_carve_days"), rec.get("n_signals"))
        rec["unknown_reason"] = (judge_classify(*args, errored=rec["errored"])
                                 if judge_classify is not None
                                 else classify(*args, errored=rec["errored"]))
        rec["cause"] = _cause(rec, eg=eg, meta=meta, cut=cut)
    for rec in built:
        rec.pop("_spec", None)
    return {"records": records, "lockbox_cut": None if cut is None else str(cut),
            "lockbox_frac": frac, "cells_carved_at_own_tail": carved_own}


def _cause(rec: dict[str, Any], *, eg: Any, meta: dict[str, Any], cut: Any) -> str:
    """The finer cause of one UNKNOWN: the missing identity input, the session, the absent
    external input -- else the judge's own classification."""
    spec = rec["_spec"]
    fam, params = rec["family"], spec["params"]
    reason = str(rec["unknown_reason"])
    need = INPUT_KEY.get(fam)
    if need and not params.get(need):
        return "missing_identity_input:" + need
    if reason in ("no_signals", "too_rare", "signals_no_trades") and params.get("session") and \
            str(params.get("session")).lower() != "all":
        free = {k: v for k, v in params.items() if k != "session"}
        try:
            obj = eg.build_cell(rec["sym"], fam, free, meta)
        except Exception:
            obj = None
        if obj:
            n_free = len(obj.get("sigs") or [])
            try:
                ds = eg.daily_series(obj["df"], obj["sigs"], obj["costs"])
                d_free = len(ds if cut is None else ds[ds.index < cut])
            except Exception:
                d_free = 0
            obj.clear()
            if rec.get("n_signals") == 0 and n_free > 0:
                return "session_excludes_fire_hour"
            if d_free >= NEED_DAYS:
                return "session_thins_below_60"
    if reason == "signals_no_trades" and (rec.get("pre_carve_days") or 0) > 0:
        # The judge's scale reads "signals, no trades" whenever the development window is empty;
        # a cell that DID trade, on fewer than 60 days all after the campaign cut, is a short
        # history, not a fill problem.
        return "short_history_after_cut"
    if reason == "no_signals" and need:
        named = params.get(need)
        names = named if isinstance(named, list) else [named]
        if fam == "triangle":
            names = [params.get("leg_b_symbol"), params.get("leg_c_symbol")]
        if any(n and eg._bars_for(str(n), rec["tf"]) is None for n in names):
            return "named_input_has_no_bars"
    if reason == "no_signals" and fam in EXTERNAL_INPUT_FAMILIES:
        frame = eg._bars_for(rec["sym"], rec["tf"])
        absent = None if frame is None else _input_absent(eg, fam, rec["sym"], frame, rec["tf"])
        if absent:
            return absent
    if reason == "no_signals":
        return "never_fires"
    return reason


def siblings(cells: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """`discovery_compiler.complete_inputs` on every sampled peerless row, as the compiler runs
    it on the box: the sibling carries the input named; the original is kept."""
    try:
        from research import discovery_compiler as dc
    except Exception as exc:
        return [], {"status": "UNMEASURED", "why": f"discovery_compiler: {exc}"}
    fn = getattr(dc, "complete_inputs", None)
    peerless = [c for c in cells if INPUT_KEY.get(str(c["family"]))
                and not c["params"].get(INPUT_KEY[str(c["family"])])]
    if fn is None:
        return [], {"status": "ABSENT", "why": "this tree's compiler has no complete_inputs",
                    "peerless_rows": len(peerless)}
    ctx = dc.build_context()
    meta = dc._universe_meta()
    out: list[dict[str, Any]] = []
    unfilled: Counter[str] = Counter()
    for c in peerless:
        row = dict(c["row"])
        row["params"] = dict(c["params"])
        child = fn(row, ctx, meta)
        if not child.get("input_completed"):
            unfilled[str(c["family"])] += 1
            continue
        params = dict(child.get("params") or {})
        key = (f"{c['sym']}.{c['family']}."
               f"{json.dumps(params, sort_keys=True, default=str)}")
        out.append({**c, "params": params, "key": key, "sibling": True, "row": child})
    return out, {"status": "MEASURED", "peerless_rows": len(peerless), "siblings": len(out),
                 "unfilled_by_family": dict(unfilled)}


def summarise(records: list[dict[str, Any]], *, siblings_too: bool) -> dict[str, Any]:
    rows = [r for r in records if siblings_too or not r.get("sibling")]
    built = [r for r in rows if r.get("stage") == "built"]
    unk = [r for r in built if r.get("verdict") == "UNKNOWN"]
    share = (len(unk) / len(built)) if built else None
    return {
        "cells": len(rows),
        "gate0_rejected": dict(Counter(str(r.get("reason")) for r in rows
                                       if r.get("stage") == "gate0")),
        "preflight_refused": len([r for r in rows if r.get("stage") == "preflight_refused"]),
        "build_failed": len([r for r in rows if r.get("stage") == "build_failed"]),
        "build_failed_by_reason": dict(Counter(str(r.get("reason")) for r in rows
                                               if r.get("stage") == "build_failed")
                                       .most_common()),
        "deferred": len([r for r in rows if r.get("stage") == "deferred"]),
        "judged_built": len(built),
        "unknown": len(unk),
        "unknown_share_of_judged": None if share is None else round(share, 4),
        "wilson95": wilson(len(unk), len(built)),
        "unknown_by_reason": dict(Counter(str(r.get("unknown_reason")) for r in unk)
                                  .most_common()),
        "unknown_by_cause": dict(Counter(str(r.get("cause")) for r in unk).most_common()),
        "unknown_by_family": dict(Counter(str(r.get("family")) for r in unk).most_common(15)),
        "unknown_by_chart": dict(Counter(str(r.get("tf")) for r in unk).most_common()),
        "judged_by_chart": dict(Counter(str(r.get("tf")) for r in built).most_common()),
    }


def sized_sample(avail_mb: float, requested: int | None) -> tuple[int, float]:
    """(sample size, RSS cap MB) from measured free memory: a quarter of it for this census."""
    cap = max(512.0, 0.25 * avail_mb)
    fit = int(max(100.0, (cap - FRAME_CACHE_MB) / PER_CELL_MB))
    n = fit if requested is None else min(int(requested), fit)
    return n, cap


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--n", type=int, default=None, help="cells to sample (default: sized)")
    ap.add_argument("--seed", type=int, default=20260930)
    ap.add_argument("--docket", type=Path, default=None)
    ap.add_argument("--budget-s", type=float, default=1800.0)
    ap.add_argument("--complete-inputs", action="store_true",
                    help="mint and judge complete_inputs siblings of sampled peerless rows")
    ap.add_argument("--coarse-proxy", action="store_true",
                    help="serve H4/D1 bars resampled from H1 where this host holds none")
    ap.add_argument("--overlay", type=Path, default=None,
                    help="dir of desks/mt5-relative modules loaded in place of the tree's")
    ap.add_argument("--lockbox-cut", default=None, help="campaign cut to use (YYYY-MM-DD)")
    ap.add_argument("--label", default="")
    ap.add_argument("--out", type=Path, default=None)
    ap.add_argument("--records", type=Path, default=None,
                    help="also write one JSON line per sampled cell (for diagnosis)")
    a = ap.parse_args(argv)

    import psutil
    overlaid = load_overlay(a.overlay) if a.overlay else []
    import external_gauntlet as eg
    if a.coarse_proxy:
        coarse_proxy(eg)
    avail_mb = psutil.virtual_memory().available / 2**20
    n, rss_cap = sized_sample(avail_mb, a.n)
    meta = json.loads((eg.UNI / "universe.json").read_text("utf-8"))
    docket = a.docket or (eg.HYP / "external_survivors.json")
    t0 = time.monotonic()
    cells, unique = docket_sample(docket, n, a.seed, eg.iter_json_array, eg.timeframe_of)
    sib_report: dict[str, Any] = {"status": "NOT_REQUESTED"}
    if a.complete_inputs:
        sibs, sib_report = siblings(cells)
        cells = cells + sibs
    out = measure(cells, meta=meta, eg=eg, budget_s=a.budget_s, rss_cap_mb=rss_cap,
                  lockbox_cut_override=a.lockbox_cut)
    recs = out["records"]
    doc = {
        "label": a.label, "seed": a.seed, "docket": str(docket), "docket_unique_cells": unique,
        "sample": n, "overlay": overlaid,
        "judge": {"named_unknowns": hasattr(eg, "classify_unknown"),
                  "cell_lockbox_cut": hasattr(eg, "cell_lockbox_cut"),
                  "cell_dev_cut": hasattr(eg, "cell_dev_cut"),
                  "constitution": hasattr(eg, "constitution_thresholds")},
        "coarse_proxy": bool(a.coarse_proxy),
        "memory": {"available_mb": round(avail_mb), "rss_cap_mb": round(rss_cap),
                   "peak_rss_mb": round(psutil.Process().memory_info().rss / 2**20)},
        "lockbox_cut": out["lockbox_cut"], "lockbox_frac": out["lockbox_frac"],
        "cells_carved_at_own_tail": out["cells_carved_at_own_tail"],
        "elapsed_s": round(time.monotonic() - t0, 1),
        "siblings": sib_report,
        "sampled_cells": summarise(recs, siblings_too=False),
    }
    if a.complete_inputs:
        doc["sampled_plus_siblings"] = summarise(recs, siblings_too=True)
        sib = [r for r in recs if r.get("sibling")]
        doc["siblings_only"] = summarise(sib, siblings_too=True)
    text = json.dumps(doc, indent=2, default=str)
    if a.out:
        a.out.write_text(text, "utf-8")
    if a.records:
        with a.records.open("w", encoding="utf-8") as fh:
            for r in recs:
                fh.write(json.dumps(r, default=str) + "\n")
    print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
