"""Conviction scaling, in SHADOW: what the allocator's book would be with it, and what it earned.

Build C row 143. `libs.portfolio.capital_modifiers.conviction_factors` multiplies each sleeve's
evidence weight by its evidence STRENGTH (deflated Sharpe probability, shrunk by n) and by how
many INDEPENDENT signals agree with it. `pf_allocator` applies it only when the switch
`desks/mt5/data/CONVICTION_SCALING.json` reads LIVE; absent, it is SHADOW and the live fractions
are byte-identical. This leg is how the switch earns its flip:

  1. read what the allocator already read this pass -- the pre-conviction evidence it
     snapshots (`data/pf_allocator_cache/conviction_inputs.npz`) and the book it published;
  2. solve the same robust E[log W] objective twice at the book's own total heat, once on that
     evidence and once on the conviction-tilted evidence, on the same seed;
  3. write both books and the ex-ante dE[log W] (scored on the UNTILTED worlds, where the base
     book is optimal by construction, so ex-ante can only read <= 0: it is reported, never
     used to promote);
  4. once per UTC day, ledger the two books; score every earlier day's pair on the FIRST
     realised day after it (forward ledgers first, then the allocator's own daily-R matrix):
     dlogW = log(1 + h_conv.r) - log(1 + h_base.r);
  5. `capital_modifiers.conviction_promotion` over the last N matured days flips the switch
     LIVE when mean - se > 0 and back to SHADOW when mean + se < 0. No human gate.

The downward half (sleeves the modifier cut) is priced per matured day as
sum_{f<1} (h_conv - h_base) x r and read by `missed_growth.measure_conviction`.

    python desks/mt5/research/conviction_shadow.py --once --budget-s 240 [--json]
"""
from __future__ import annotations

import argparse
import json
import math
import sys
import time
from collections.abc import Mapping, Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np

DESK = Path(__file__).resolve().parents[1]
ROOT = DESK.parent.parent
for _p in (str(DESK), str(DESK / "research"), str(ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from libs.portfolio import capital_modifiers as cm  # noqa: E402

REPORTS = DESK / "reports"
DATA = DESK / "data"
OUT = REPORTS / "CONVICTION_SHADOW.json"
LEDGER = DATA / "conviction_shadow_ledger.jsonl"
INPUTS = ROOT / "data" / "pf_allocator_cache" / "conviction_inputs.npz"
MATRIX = DATA / "pf_allocator_cache" / "daily_r.parquet"
#: Sleeves beyond the funded book the shadow solve may fund: the strongest-conviction
#: positive-mean ones, so the modifier can BUY a sleeve the base book left out (Rule 2).
EXTRA = 40
#: Per-sleeve heat bound for both solves: the larger of the book's own largest sleeve and this
#: share of the total. The same bound on both sides, so the difference is the modifier.
SLEEVE_SHARE = 0.25


def _now() -> str:
    return datetime.now(tz=UTC).isoformat()


def load_inputs(path: Path = INPUTS) -> tuple[list[Any], dict[str, float], str]:
    """The allocator's pre-conviction evidence and its published book."""
    from libs.portfolio.robust_elog import SleeveEvidence
    z = np.load(path, allow_pickle=False)
    lens = z["lens"]
    flat = z["flat"].astype(float)
    offs = np.concatenate([[0], np.cumsum(lens)])
    ev = []
    for i, name in enumerate(z["names"]):
        ev.append(SleeveEvidence(
            name=str(name), daily_r=flat[offs[i]:offs[i + 1]].copy(),
            family=str(z["family"][i]), symbol=str(z["symbol"][i]),
            forward_days=int(z["forward_days"][i]), live_days=int(z["live_days"][i]),
            cost_r=float(z["cost_r"][i]), n_trials=int(z["n_trials"][i])))
    book = {str(k): float(v) for k, v in zip(z["book_names"], z["book_heat"], strict=True)}
    return ev, book, str(z["generated_utc"])


def universe(ev: Sequence[Any], book: Mapping[str, float],
             factors: Mapping[str, Mapping[str, Any]], extra: int = EXTRA) -> list[Any]:
    """The funded book plus the `extra` strongest-conviction positive-mean sleeves."""
    def _mean(e: Any) -> float:
        x = np.asarray(e.daily_r, dtype=float)
        x = x[np.isfinite(x)]
        return float(x.mean()) if x.size else 0.0
    funded = [e for e in ev if float(book.get(e.name, 0.0)) > 0]
    rest = sorted((e for e in ev if e.name not in book and _mean(e) > 0
                   and float(factors.get(e.name, {}).get("factor", 1.0)) > 1.0),
                  key=lambda e: -float(factors[e.name]["factor"]))
    return funded + rest[:extra]


def shadow_books(ev: Sequence[Any], book: Mapping[str, float],
                 factors: Mapping[str, Mapping[str, Any]], *, seed: int = 0,
                 n_worlds: int = 128, n_rows: int = 256,
                 deadline: float | None = None) -> dict[str, Any]:
    """Both books at the published book's total heat, and the ex-ante comparison."""
    from libs.portfolio.robust_elog import WorldConfig, optimise, sample_worlds, score_book
    total = float(sum(v for v in book.values() if v > 0))
    sub = universe(ev, book, factors)
    if total <= 0 or len(sub) < 2:
        return {"status": "UNMEASURED",
                "why": f"book total heat {total:.4f}, {len(sub)} sleeve(s) in the universe"}
    cap = max(max(book.values()), SLEEVE_SHARE * total)
    cfg = WorldConfig(seed=seed, n_worlds=n_worlds, n_rows=n_rows)
    conv_sub = cm.apply_conviction(sub, factors)
    wb = sample_worlds(sub, cfg)
    wc = sample_worlds(conv_sub, cfg)
    base = optimise(sub, hard_cap=total, target=total, cfg=cfg, worlds=wb,
                    max_per_sleeve=cap, deadline=deadline)
    conv = optimise(conv_sub, hard_cap=total, target=total, cfg=cfg, worlds=wc,
                    max_per_sleeve=cap, deadline=deadline)
    sb = score_book(sub, base.heat, cfg=cfg, worlds=wb)
    sc = score_book(sub, conv.heat, cfg=cfg, worlds=wb)

    def _r(h: Mapping[str, float]) -> dict[str, float]:
        return {k: round(float(v), 6) for k, v in h.items() if v > 1e-5}
    return {"status": "MEASURED", "total_heat": round(total, 6), "per_sleeve_cap": round(cap, 6),
            "n_universe": len(sub), "base_book": _r(base.heat), "conviction_book": _r(conv.heat),
            "ex_ante": {
                "base_mean_log_per_day": sb["mean_log_growth"],
                "conviction_mean_log_per_day": sc["mean_log_growth"],
                "delta_mean_log_per_day": sc["mean_log_growth"] - sb["mean_log_growth"],
                "conviction_on_its_own_worlds": conv.mean_log_growth,
                "basis": ("both books scored on the UNTILTED worlds, where the base book is the "
                          "optimum by construction: ex-ante reads <= 0 and never promotes; the "
                          "forward realised delta below is the evidence")},
            "converged": bool(base.converged and conv.converged)}


def realised_by_day() -> dict[str, dict[str, float]]:
    """{sleeve: {YYYY-MM-DD: R}}: the allocator's daily-R matrix, overridden by forward ledgers."""
    out: dict[str, dict[str, float]] = {}
    try:
        import pandas as pd
        m = pd.read_parquet(MATRIX)
        for col in m.columns:
            s = m[col].dropna()
            out[str(col)] = {str(k)[:10]: float(v) for k, v in s.items()}
    except Exception:
        pass
    try:
        from research.portfolio_evidence import daily_series
        for k, days in daily_series().items():
            out.setdefault(str(k), {}).update({str(d)[:10]: float(r) for d, r in days.items()})
    except Exception:
        pass
    return out


def _log1p(x: float) -> float:
    return math.log(max(1.0 + x, 1e-9))


def score_record(rec: Mapping[str, Any], realised: Mapping[str, Mapping[str, float]]
                 ) -> dict[str, Any] | None:
    """The record's pair on the first realised day strictly after the record's day."""
    base = {str(k): float(v) for k, v in (rec.get("base_book") or {}).items()}
    conv = {str(k): float(v) for k, v in (rec.get("conviction_book") or {}).items()}
    names = set(base) | set(conv)
    after = sorted({d for n in names for d in (realised.get(n) or {}) if d > str(rec["day"])})
    if not after:
        return None
    d = after[0]
    r = {n: float((realised.get(n) or {}).get(d, 0.0)) for n in names}
    pb = sum(base.get(n, 0.0) * r[n] for n in names)
    pc = sum(conv.get(n, 0.0) * r[n] for n in names)
    facs = rec.get("factors") or {}
    down = sum((conv.get(n, 0.0) - base.get(n, 0.0)) * r[n] for n in names
               if float(facs.get(n, 1.0)) < 1.0)
    return {"day": rec["day"], "realised_day": d, "delta_logw": _log1p(pc) - _log1p(pb),
            "base_logw": _log1p(pb), "conviction_logw": _log1p(pc),
            "down_half_logw": down}


def _ledger(path: Path = LEDGER) -> list[dict[str, Any]]:
    try:
        return [json.loads(ln) for ln in path.read_text("utf-8").splitlines() if ln.strip()]
    except (OSError, ValueError):
        return []


def run(budget_s: float = 240.0, write: bool = True) -> dict[str, Any]:
    t0 = time.time()
    mode = cm.conviction_mode()
    doc: dict[str, Any] = {"generated_utc": _now(), "mode": mode,
                           "switch": "desks/mt5/data/" + cm.CONVICTION_SWITCH.name,
                           "rule": ("conviction = clip(strength x agreement, 0.5, 2.0); strength "
                                    "= 1 + n/(n+120) x (2 DSR - 1) x 0.5; agreement = "
                                    "clip(sqrt((1+k)/(1+k_ref)), 0.75, 1.5), k = same-instrument "
                                    "other-mechanism positive-mean sleeves at |corr| < 0.3")}
    try:
        ev, book, alloc_at = load_inputs()
    except Exception as exc:
        doc.update(status="UNMEASURED",
                   why=f"allocator inputs unreadable ({type(exc).__name__}: {exc}); "
                       "pf_allocator writes them every pass")
        ev, book, alloc_at = [], {}, ""
    rows = _ledger()
    if ev:
        factors = cm.conviction_factors(ev)
        doc["allocator_pass_utc"] = alloc_at
        doc["factors_summary"] = {
            "n": len(factors),
            "n_up": sum(1 for v in factors.values() if v["factor"] > 1.0 + 1e-9),
            "n_down": sum(1 for v in factors.values() if v["factor"] < 1.0 - 1e-9),
            "largest": dict(sorted(factors.items(),
                                   key=lambda kv: -abs(kv[1]["factor"] - 1.0))[:15])}
        sh = shadow_books(ev, book, factors, deadline=t0 + max(30.0, budget_s - 30.0))
        doc["shadow"] = sh
        day = _now()[:10]
        if sh.get("status") == "MEASURED" and not any(r.get("day") == day for r in rows):
            rec = {"day": day, "t": _now(), "allocator_pass_utc": alloc_at, "mode": mode,
                   "base_book": sh["base_book"], "conviction_book": sh["conviction_book"],
                   "factors": {k: v["factor"] for k, v in factors.items()
                               if k in sh["base_book"] or k in sh["conviction_book"]},
                   "ex_ante_delta": sh["ex_ante"]["delta_mean_log_per_day"]}
            rows.append(rec)
            if write:
                LEDGER.parent.mkdir(parents=True, exist_ok=True)
                with LEDGER.open("a", encoding="utf-8") as fh:
                    fh.write(json.dumps(rec) + "\n")
    realised = realised_by_day() if rows else {}
    scored = [s for s in (score_record(r, realised) for r in rows) if s is not None]
    deltas = [float(s["delta_logw"]) for s in scored]
    promo = cm.conviction_promotion(deltas, mode)
    doc["forward"] = {"ledger_days": len(rows), "matured": len(scored),
                      "recent": scored[-10:], "promotion": promo,
                      "need": cm.CONV_PROMOTE_N}
    # THE MISSED-GROWTH LINE: what the DOWNWARD half did on the latest matured day.
    doc["down_half"] = ({"day": scored[-1]["day"], "realised_day": scored[-1]["realised_day"],
                         "value_logw_per_day": scored[-1]["down_half_logw"],
                         "mean_value_logw_per_day": float(np.mean(
                             [s["down_half_logw"] for s in scored])), "n": len(scored)}
                        if scored else {"verdict": "UNMEASURED", "n": 0})
    if promo["changed"] and write:
        cm.CONVICTION_SWITCH.parent.mkdir(parents=True, exist_ok=True)
        cm.CONVICTION_SWITCH.write_text(json.dumps({
            "mode": promo["mode"], "changed_utc": _now(), "by": "research/conviction_shadow.py",
            "evidence": promo}, indent=1), "utf-8")
        doc["switch_flipped_to"] = promo["mode"]
    doc.setdefault("status", "MEASURED" if ev else doc.get("status", "UNMEASURED"))
    doc["elapsed_s"] = round(time.time() - t0, 2)
    if write:
        OUT.parent.mkdir(parents=True, exist_ok=True)
        OUT.write_text(json.dumps(doc, indent=1, default=str), "utf-8")
    return doc


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--once", action="store_true")
    ap.add_argument("--budget-s", type=float, default=240.0)
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args(argv)
    doc = run(budget_s=a.budget_s)
    if a.json:
        print(json.dumps(doc, indent=1, default=str))
    else:
        f = doc.get("forward") or {}
        print(f"conviction_shadow: mode={doc['mode']} status={doc.get('status')} "
              f"matured={f.get('matured')} promotion={(f.get('promotion') or {}).get('verdict')} "
              f"-> {OUT.name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
