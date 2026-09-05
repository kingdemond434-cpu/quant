"""MFE and MAE for every trade the desk has taken -- the dataset every exit decision needs.

WHAT WAS NOT RECORDED. A trade's ledger row says where it entered and where it left. It does not
say how far it went in its favour before it left, or how far against. Those two numbers -- the
maximum favourable and adverse excursion -- are what decide whether a target is too far, a stop
too tight, a hold too long. The desk has an `exit_sweep`; it had no excursion data to sweep on.

FROM THE BARS THE DESK ALREADY HOLDS. For each shadow (and, as they arrive, live) trade, the H1
bars between entry and exit are read and the path's extremes taken against the entry, in R --
the same unit the trade's result is in. Written append-only to `data/excursions.jsonl`, keyed on
(sleeve, entry_time), so a trade is measured once and re-runs cost nothing.

WHAT IT PROPOSES. Per sleeve, the distribution of MFE says what fraction of trades reached
k R before exiting worse. Where the median MFE is well above the realised result and the trade
count supports it, an EXIT hypothesis is written for the deepening queue naming the sleeve and
the excursion evidence -- not a re-parameterised certificate, which would be a second search on
a certified cell without a charge, but a research instruction with the numbers attached.
"""
from __future__ import annotations

import argparse
import contextlib
import json
import sys
from datetime import UTC, datetime
from pathlib import Path

import numpy as np
import pandas as pd

BASE = Path(__file__).resolve().parent.parent
ROOT = BASE.parent.parent
for p in (str(BASE), str(BASE / "research"), str(ROOT)):
    if p not in sys.path:
        sys.path.insert(0, p)

OUT = BASE / "data" / "excursions.jsonl"
REPORT = BASE / "reports" / "EXCURSIONS.json"
LEDGER_DIRS = (BASE / "reports" / "shadow", ROOT / "backups" / "moat" / "shadow_ledgers")
MIN_TRADES = 20


def _bars_cache():
    from research import proposer_common as pc
    cache: dict[str, pd.DataFrame | None] = {}

    def get(sym: str):
        if sym not in cache:
            cache[sym] = pc.bars(sym)
        return cache[sym]
    return get


def _symbol_of(sleeve: str) -> str:
    return str(sleeve).split("_")[0].upper()


def excursion(bars: pd.DataFrame, entry_time: str, exit_time: str, side: int,
              entry: float, risk: float) -> dict | None:
    """MFE/MAE in R over [entry, exit], from the bars' highs and lows."""
    try:
        t0 = pd.Timestamp(entry_time)
        t1 = pd.Timestamp(exit_time)
    except (TypeError, ValueError):
        return None
    if t0.tzinfo is None:
        t0 = t0.tz_localize("UTC")
    if t1.tzinfo is None:
        t1 = t1.tz_localize("UTC")
    seg = bars[(bars.index >= t0) & (bars.index <= t1)]
    if seg.empty or risk <= 0 or not np.isfinite(risk):
        return None
    hi, lo = float(seg["high"].max()), float(seg["low"].min())
    fav = (hi - entry) if side > 0 else (entry - lo)
    adv = (entry - lo) if side > 0 else (hi - entry)
    return {"mfe_r": round(fav / risk, 4), "mae_r": round(adv / risk, 4), "bars": len(seg)}


def _done() -> set[str]:
    keys = set()
    try:
        for ln in OUT.read_text("utf-8").splitlines():
            if ln.strip():
                r = json.loads(ln)
                keys.add(f"{r.get('sleeve')}|{r.get('entry_time')}")
    except (OSError, ValueError):
        pass
    return keys


def run() -> dict:
    get = _bars_cache()
    done = _done()
    new: list[dict] = []
    for d in LEDGER_DIRS:
        if not d.is_dir():
            continue
        for f in sorted(d.glob("ledger_*.json")):
            try:
                rows = json.loads(f.read_text("utf-8"))
            except (OSError, ValueError):
                continue
            if not isinstance(rows, list):
                continue
            sleeve = f.stem.removeprefix("ledger_")
            sym = _symbol_of(sleeve)
            bars = get(sym)
            if bars is None:
                continue
            for r in rows:
                if not isinstance(r, dict):
                    continue
                et, xt = r.get("entry_time"), r.get("exit_time")
                key = f"{sleeve}|{et}"
                if not et or not xt or key in done:
                    continue
                try:
                    side = 1 if str(r.get("side", "")).lower() in ("long", "buy", "1") else -1
                    entry = float(r.get("entry"))
                    rm = float(r.get("r_multiple"))
                    exit_ = float(r.get("exit"))
                except (TypeError, ValueError):
                    continue
                # Risk in price units from the realised R: |exit - entry| = |R| * risk.
                risk = abs(exit_ - entry) / abs(rm) if rm not in (0.0, None) and rm == rm else 0.0
                if risk <= 0:
                    continue
                ex = excursion(bars, str(et), str(xt), side, entry, risk)
                if ex is None:
                    continue
                new.append({"sleeve": sleeve, "symbol": sym, "entry_time": et, "exit_time": xt,
                            "side": side, "r_multiple": rm, **ex})
                done.add(key)
    if new:
        OUT.parent.mkdir(parents=True, exist_ok=True)
        with OUT.open("a", encoding="utf-8") as fh:
            for r in new:
                fh.write(json.dumps(r) + "\n")

    # The per-sleeve picture, from everything ever recorded.
    allrows = []
    with contextlib.suppress(OSError, ValueError):
        allrows = [json.loads(ln) for ln in OUT.read_text("utf-8").splitlines() if ln.strip()]
    per: dict[str, dict] = {}
    by = {}
    for r in allrows:
        by.setdefault(r["sleeve"], []).append(r)
    exit_tasks = []
    for sleeve, rs in by.items():
        mfe = np.array([r["mfe_r"] for r in rs])
        mae = np.array([r["mae_r"] for r in rs])
        res = np.array([r["r_multiple"] for r in rs])
        per[sleeve] = {"n": len(rs), "median_mfe_r": round(float(np.median(mfe)), 3),
                       "median_mae_r": round(float(np.median(mae)), 3),
                       "median_r": round(float(np.median(res)), 3),
                       "p_reached_1r": round(float((mfe >= 1.0).mean()), 3),
                       "p_reached_2r": round(float((mfe >= 2.0).mean()), 3),
                       "mfe_given_up": round(float(np.median(mfe - res)), 3)}
        if len(rs) >= MIN_TRADES and per[sleeve]["mfe_given_up"] >= 0.5:
            exit_tasks.append({
                "source": "excursions", "kind": "exit_hypothesis",
                "title": f"{sleeve}: trades reach {per[sleeve]['median_mfe_r']}R and exit at "
                         f"{per[sleeve]['median_r']}R",
                "description": (f"{len(rs)} trades; median MFE {per[sleeve]['median_mfe_r']}R, "
                                f"median MAE {per[sleeve]['median_mae_r']}R, median result "
                                f"{per[sleeve]['median_r']}R; P(reach 1R)={per[sleeve]['p_reached_1r']}, "
                                f"P(reach 2R)={per[sleeve]['p_reached_2r']}. The exit gives up "
                                f"{per[sleeve]['mfe_given_up']}R of excursion on the median trade. "
                                "Propose an exit rule (trail, partial, time stop) as a NEW cell "
                                "with its own multiplicity charge -- not a re-parameterisation of "
                                "the certified one."),
                "symbols": [_symbol_of(sleeve)], "sleeve": sleeve, "status": None,
                "consumer": "exit_sweep / research brains"})
    doc = {"generated_utc": datetime.now(tz=UTC).isoformat(), "new_measured": len(new),
           "total_measured": len(allrows), "sleeves": per, "exit_hypotheses": exit_tasks}
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text(json.dumps(doc, indent=1), "utf-8")
    if exit_tasks:
        try:
            from research.regime_coverage import _merge_into_queue
            _merge_into_queue(exit_tasks, source="excursions")
        except Exception as exc:
            doc["queue_error"] = f"{type(exc).__name__}: {exc}"
    return doc


def main() -> int:
    argparse.ArgumentParser().parse_args()
    d = run()
    print(f"EXCURSIONS  measured {d['new_measured']} new, {d['total_measured']} total; "
          f"{len(d['exit_hypotheses'])} exit hypotheses")
    for s, v in sorted(d["sleeves"].items(), key=lambda kv: -kv[1]["n"])[:12]:
        print(f"  {s[:38]:38s} n={v['n']:3d} MFE={v['median_mfe_r']:+.2f} "
              f"MAE={v['median_mae_r']:+.2f} R={v['median_r']:+.2f} "
              f"given_up={v['mfe_given_up']:+.2f}")
    print(f"written: {OUT}  report: {REPORT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
