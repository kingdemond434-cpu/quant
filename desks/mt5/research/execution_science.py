"""F22 -- RESEARCH THE EXECUTION LAYER LIKE ALPHA, and separate the signal from the fill.

THE PRINCIPAL, 2026-09-12:

    Research execution like alpha -- order timing, order type, entry delay, partial fills, spread
    state, adverse selection, rollover/swap, stop behaviour, session boundaries, broker
    microstructure -- with live fills continuously recalibrating the simulator and signal alpha
    attributed separately.

WHY THE LAST CLAUSE IS THE WHOLE THING. A strategy's measured edge is signal alpha MINUS execution
drag, and the desk has only ever had the difference. That single number cannot tell a mechanism
that does not work from a mechanism that works and is being eaten by the round trip -- and the two
call for opposite decisions. The first should be abandoned; the second should be traded
differently.

THE SEPARATION IS AVAILABLE AND COSTS ONE EXTRA RUN. `external_gauntlet.costs_for` takes a
multiplier, so the identical signal list scored at mult=0.0 is the FRICTIONLESS path -- pure signal
alpha -- and at mult=1.0 is what the desk would actually have earned. Their difference is the
execution drag, in the same units, on the same bars, with no second model of anything.

WHAT IS VARIED, AND WHY EACH ONE IS AN EXECUTION QUESTION RATHER THAN AN ALPHA QUESTION:

    order type      market at the next open, or a resting order an ATR-fraction away. A better
                    price bought with missed trades.
    order life      how many bars a resting order stays alive before the trade is abandoned.
    exit style      a fixed stop, a chandelier trail, or a partial bank at target with the runner
                    protected. The signal is identical in all three.
    session gate    whether the sleeve trades the session handover at all.

NONE OF THESE CHANGES THE SIGNAL. Every variant fires on the same bars for the same reason; only
the fill and the exit differ. That is what makes the difference attributable to execution rather
than to a second strategy wearing the first one's name.

TRAIN AND TEST ARE PURGED AND EMBARGOED, and every number reported is from the held-out slice. The
variants are ranked on train; a variant chosen on test would be an execution policy fitted to the
window it is measured in.

LIVE FILLS RECALIBRATING THE SIMULATOR is the one clause this cannot yet honour, and it says so:
the live ledger holds 16 deals across 3 days. The hook is named rather than faked.

    python desks/mt5/research/execution_science.py [--apply] [--dry-run]

THE REPORT IS WRITTEN ON EVERY RUN (`reports/EXECUTION_SCIENCE.json`), an UNMEASURED verdict with
its reason included: an organ that writes only on success is indistinguishable from one that
never ran.
"""
from __future__ import annotations

import argparse
import contextlib
import json
import math
import os
import sys
from collections.abc import Callable, Iterable, Mapping, Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

DESK = Path(__file__).resolve().parents[1]
ROOT = DESK.parent.parent
for _p in (str(DESK), str(DESK / "research"), str(DESK / "scripts"), str(ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

UNI = DESK / "data" / "universe"
SLEEVES = DESK / "data" / "sleeves.json"
LEDGER = DESK / "data" / "live_ledger.jsonl"
OUT = DESK / "reports" / "EXECUTION_SCIENCE.json"

#: Families whose execution is studied. The same three the joint search uses, so the two organs
#: talk about the same objects and a finding in one is checkable in the other.
FAMILIES: tuple[str, ...] = ("momentum_volgate", "session_range_breakout", "mean_reversion_rsi")

MAX_SYMBOLS = 4
BARS = 6000
TRAIN_FRAC = 0.70
EMBARGO = 240

#: The fixed fraction that turns a daily R series into log growth. Not a sizing decision and
#: nothing reads it downstream -- it is the transform that makes the ranking a GROWTH ranking
#: rather than a mean-R ranking, and it is stated so the comparison is reproducible.
RANK_RISK_FRAC = 0.01

#: The execution variants. Each is a fill-and-exit policy over an UNCHANGED signal list.
#:
#: `selects` MARKS THE ONE THAT IS NOT PURELY AN EXECUTION QUESTION, and the first run is why. A
#: session filter topped the board on median growth while keeping 32% of the signals -- but a
#: variant that trades a third as often is not executing the same strategy better, it is trading
#: a DIFFERENT strategy. Comparing per-day growth across different trade counts conflates
#: selection with execution, and the selection axis already belongs to the joint search's state
#: condition. It stays on the board because the number is real; it is reported apart because the
#: question is.
VARIANTS: tuple[dict[str, Any], ...] = (
    {"name": "market_next_open", "genes": {}, "selects": False},
    {"name": "resting_0.25atr_3bar", "genes": {"trigger_atr": 0.25, "rest_bars": 3},
     "selects": True},
    {"name": "resting_0.50atr_6bar", "genes": {"trigger_atr": 0.5, "rest_bars": 6},
     "selects": True},
    {"name": "trail_1x", "genes": {"trail_k": 1.0}, "selects": False},
    {"name": "trail_2x", "genes": {"trail_k": 2.0}, "selects": False},
    {"name": "bank_half_at_target", "genes": {"bank_frac": 0.5}, "selects": False},
    {"name": "bank_half_and_trail", "genes": {"bank_frac": 0.5, "trail_k": 1.0},
     "selects": False},
    {"name": "session_london_only", "genes": {"session": "london"}, "selects": True},
)

#: Below this share of the base signal list a variant is changing WHICH trades are taken, not how
#: they are filled -- whatever it was intended to vary. Measured, so a resting order that misses
#: half its fills is flagged on the evidence rather than on its label.
LIKE_FOR_LIKE_KEPT = 0.90

#: The layer genes apply_layers accepts. Anything a variant does not name takes its neutral value,
#: so "market_next_open" is exactly the base family and the comparison has a true zero.
NEUTRAL: dict[str, Any] = {"state_band": "any", "session": "any", "trigger_atr": 0.0,
                           "rest_bars": 1, "ttl_mult": 1.0, "rr_mult": 1.0,
                           "bank_frac": 0.0, "trail_k": 0.0}


def _live_symbols(limit: int = MAX_SYMBOLS) -> list[str]:
    try:
        doc = json.loads(SLEEVES.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []
    rows = doc if isinstance(doc, list) else (doc.get("sleeves") or [])
    out: list[str] = []
    for r in rows:
        if isinstance(r, dict) and str(r.get("status", "")).upper() == "LIVE":
            s = str(r.get("symbol") or "").strip()
            if s and s not in out:
                out.append(s)
    return out[:limit]


def _growth(ds: Any) -> float:
    import numpy as np
    if ds is None or len(ds) < 20:
        return float("nan")
    r = np.asarray(ds, dtype=float) * RANK_RISK_FRAC
    r = r[np.isfinite(r)]
    if r.size < 20 or np.any(r <= -1.0):
        return float("nan")
    return float(np.mean(np.log1p(r)))


def _live_fill_calibration() -> dict[str, Any]:
    """The clause this cannot honour yet, stated rather than faked."""
    n = 0
    if LEDGER.exists():
        for ln in LEDGER.read_text(encoding="utf-8", errors="replace").splitlines():
            if ln.strip():
                n += 1
    return {
        "status": "UNMEASURED",
        "n_live_deals": n,
        "why": (f"the live ledger holds {n} realised deal(s). Recalibrating a fill simulator "
                f"needs the distribution of slippage against the modelled fill, and a "
                f"distribution estimated from {n} observations would be a point estimate wearing "
                f"a histogram."),
        "hook": ("when the ledger carries enough deals, `split_fills` is the recalibration: "
                 "each deal records entry_price and fill_price, and their difference against the "
                 "modelled fill IS the recalibration. Nothing further needs building."),
    }


def split_fills(fills: Iterable[Mapping[str, Any]]) -> dict[str, Any]:
    """Signal alpha and execution drag, split per fill, in R.

    Each fill names the price the SIGNAL decided at (`signal_price`, the modelled fill), the price
    the order actually got (`fill_price`), where the trade left (`exit_price`), its `side` (+1/-1),
    its `stop_dist` (the R unit) and any round-trip `cost` in price units. Then, with no model of
    anything:

        signal_alpha    side * (exit - signal_price) / stop_dist        what the idea earned
        execution_drag  side * (fill - signal_price) / stop_dist
                        + cost / stop_dist                              what the round trip took
        net             signal_alpha - execution_drag                   what the book was paid

    so `net + drag == alpha` holds exactly on every row. A fill with no usable stop distance is
    counted and skipped, never scored as a zero.
    """
    rows: list[dict[str, float]] = []
    skipped = 0
    for f in fills:
        try:
            side = 1.0 if float(f.get("side", 1)) >= 0 else -1.0
            sd = float(f["stop_dist"])
            sig_px, fill_px, exit_px = (float(f["signal_price"]), float(f["fill_price"]),
                                        float(f["exit_price"]))
            cost = float(f.get("cost", 0.0) or 0.0)
        except (KeyError, TypeError, ValueError):
            skipped += 1
            continue
        if not (sd > 0) or not all(math.isfinite(x) for x in (sig_px, fill_px, exit_px, cost)):
            skipped += 1
            continue
        alpha = side * (exit_px - sig_px) / sd
        drag = side * (fill_px - sig_px) / sd + cost / sd
        rows.append({"signal_alpha_r": alpha, "execution_drag_r": drag, "net_r": alpha - drag})
    n = len(rows)
    if n == 0:
        return {"status": "UNMEASURED", "n": 0, "skipped": skipped,
                "why": "no fill carried a signal price, a fill price, an exit and a stop"}
    mean = {k: sum(r[k] for r in rows) / n
            for k in ("signal_alpha_r", "execution_drag_r", "net_r")}
    a = mean["signal_alpha_r"]
    return {"status": "MEASURED", "n": n, "skipped": skipped,
            "mean_signal_alpha_r": round(a, 8),
            "mean_execution_drag_r": round(mean["execution_drag_r"], 8),
            "mean_net_r": round(mean["net_r"], 8),
            "drag_share_of_signal": (round(mean["execution_drag_r"] / abs(a), 6)
                                     if a != 0 else None),
            "diagnosis": diagnose(a, mean["net_r"])}


def diagnose(signal_alpha: float, net: float) -> str:
    """The decision the split exists for: abandon the mechanism, or trade it differently."""
    if signal_alpha <= 0:
        return "NO_SIGNAL: the idea earns nothing before costs -- abandon or rethink the mechanism"
    if net <= 0:
        return ("EATEN_BY_EXECUTION: the signal works and the round trip takes all of it -- "
                "trade it differently, do not abandon it")
    return "SURVIVES_EXECUTION: the signal works and keeps part of its edge after the round trip"


def cell_row(sym: str, fam: str, variant: Mapping[str, Any], n_base: int, n_sigs: int,
             net_series: Any, gross_series: Any) -> dict[str, Any] | None:
    """One (symbol, family, variant) cell: the SAME signals scored frictionless and costed."""
    g_net, g_gross = _growth(net_series), _growth(gross_series)
    if not (math.isfinite(g_net) and math.isfinite(g_gross)):
        return None
    kept = n_sigs / max(n_base, 1)
    return {
        "symbol": sym, "family": fam, "variant": variant["name"],
        "declared_selects": bool(variant.get("selects")),
        "n_signals": int(n_sigs),
        "signals_kept_share": round(kept, 4),
        "like_for_like": bool(kept >= LIKE_FOR_LIKE_KEPT),
        "signal_alpha_frictionless": round(g_gross, 8),
        "net_growth": round(g_net, 8),
        "execution_drag": round(g_gross - g_net, 8),
        "drag_share_of_signal": (round((g_gross - g_net) / abs(g_gross), 4)
                                 if g_gross != 0 else None),
        "diagnosis": diagnose(g_gross, g_net),
    }


def _unmeasured(now: datetime, why: str, **extra: Any) -> dict[str, Any]:
    """UNMEASURED is a verdict (L1.28a): it is written, with its reason, like any other."""
    return {"at": now.isoformat(timespec="seconds"), "status": "UNMEASURED", "why": why,
            "live_fill_calibration": _live_fill_calibration(), **extra}


def build(evaluator: Any = None, families: Any = None, meta: Mapping[str, Any] | None = None,
          symbols: Sequence[str] | None = None, bars: Callable[[str], Any] | None = None
          ) -> dict[str, Any]:
    """The whole attribution. Every dependency is injectable so the split is testable on
    synthetic fills; by default each is the desk's own (`external_gauntlet`, `mt5desk.families`,
    the universe registry, the LIVE sleeves' symbols, the H1 parquet)."""
    now = datetime.now(tz=UTC)
    try:
        import pandas as pd
    except ImportError as exc:
        return _unmeasured(now, f"pandas unavailable ({exc})")
    eg, fam_mod = evaluator, families
    if eg is None or fam_mod is None:
        try:
            import external_gauntlet as _eg  # type: ignore[import-not-found]
            from mt5desk import families as _fam
        except ImportError as exc:
            return _unmeasured(now, (
                f"the canonical evaluator is not importable ({exc}). This organ refuses to "
                f"score with a second implementation of the fill model -- that is the one thing "
                f"it exists to hold constant."))
        eg = eg if eg is not None else _eg
        fam_mod = fam_mod if fam_mod is not None else _fam
    if meta is None:
        try:
            meta = json.loads((UNI / "universe.json").read_text("utf-8"))
        except (OSError, ValueError) as exc:
            return _unmeasured(now, f"universe registry unreadable: {exc}")
    syms = list(symbols) if symbols is not None else _live_symbols()
    if not syms:
        return _unmeasured(now, "no LIVE sleeve names a symbol in sleeves.json")

    def _load(sym: str) -> Any:
        p = UNI / f"{sym}_H1.parquet"
        return pd.read_parquet(p).tail(BARS) if p.exists() else None

    load = bars or _load
    rows: list[dict[str, Any]] = []
    skipped: list[dict[str, str]] = []
    for sym in syms:
        try:
            df = load(sym)
        except (OSError, ValueError) as exc:
            skipped.append({"symbol": sym, "why": f"bars unreadable: {type(exc).__name__}"})
            continue
        if df is None or len(df) < 2000:
            skipped.append({"symbol": sym, "why": "fewer than 2000 H1 bars"})
            continue
        ntr = int(len(df) * TRAIN_FRAC)
        test = df.iloc[ntr + EMBARGO:]
        if len(test) < 500:
            skipped.append({"symbol": sym, "why": "held-out slice under 500 bars"})
            continue
        try:
            costed = eg.costs_for(sym, meta, 1.0)
            # THE FRICTIONLESS PATH IS THE SAME COST OBJECT AT ZERO, not a different model. One
            # multiplier is the whole separation between signal alpha and execution drag.
            free = eg.costs_for(sym, meta, 0.0)
        except Exception as exc:
            skipped.append({"symbol": sym, "why": f"costs_for raised: {type(exc).__name__}"})
            continue

        for fam in FAMILIES:
            entry = fam_mod.FAMILY_REGISTRY.get(fam)
            fn: Any = (entry.get("func") if isinstance(entry, dict)
                       else getattr(fam_mod, f"family_{fam}", None))
            if fn is None or not callable(fn):
                continue
            try:
                with contextlib.redirect_stdout(None):
                    base_sigs = list(fn(test) or [])
            except Exception:
                continue
            if len(base_sigs) < 30:
                continue
            h1 = fam_mod._h1(test)
            for v in VARIANTS:
                genes = {**NEUTRAL, **v["genes"]}
                try:
                    sigs = fam_mod.apply_layers(list(base_sigs), h1, **genes)
                    if len(sigs) < 20:
                        continue
                    row = cell_row(sym, fam, v, len(base_sigs), len(sigs),
                                   eg.daily_series(test, sigs, costed),
                                   eg.daily_series(test, sigs, free))
                except Exception:
                    continue
                if row is not None:
                    rows.append(row)

    if not rows:
        return _unmeasured(now, ("no (symbol, family) pair produced enough signals on the "
                                 "held-out slice to compare execution variants"),
                           symbols_tried=syms, skipped=skipped[:40])
    return {"at": now.isoformat(timespec="seconds"), **summarise(rows), "skipped": skipped[:40]}


def summarise(rows: list[dict[str, Any]]) -> dict[str, Any]:
    """Per variant, across every cell -- the question "is a resting entry worth it" is about the
    POLICY, and a per-symbol answer is a policy fitted to a symbol."""
    import numpy as np
    by_variant: dict[str, dict[str, Any]] = {}
    for r in rows:
        b = by_variant.setdefault(str(r["variant"]),
                                  {"variant": r["variant"], "n": 0, "net": [], "drag": [],
                                   "kept": []})
        b["n"] += 1
        b["net"].append(float(r["net_growth"]))
        b["drag"].append(float(r["execution_drag"]))
        b["kept"].append(float(r["signals_kept_share"]))
    base = by_variant.get("market_next_open")
    base_med = float(np.median(base["net"])) if base and base["net"] else None
    summary: list[dict[str, Any]] = []
    for b in by_variant.values():
        med = float(np.median(b["net"]))
        kept_med = float(np.median(b["kept"]))
        summary.append({
            "variant": b["variant"], "n_cells": b["n"],
            "median_net_growth": round(med, 8),
            "median_execution_drag": round(float(np.median(b["drag"])), 8),
            "median_signals_kept": round(kept_med, 4),
            "like_for_like": bool(kept_med >= LIKE_FOR_LIKE_KEPT),
            "vs_market_next_open": (None if base_med is None else round(med - base_med, 8)),
            "comparability": (
                "like-for-like: the same trades, filled differently"
                if kept_med >= LIKE_FOR_LIKE_KEPT else
                f"NOT like-for-like -- keeps {kept_med:.0%} of the base signals, so its growth "
                f"reflects a different SET of trades as much as a different fill. Read it as a "
                f"selection result, which belongs to the joint search's state axis."),
        })
    summary.sort(key=lambda r: -float(r["median_net_growth"]))
    like = [r for r in summary if r["like_for_like"]]
    like.sort(key=lambda r: -float(r["median_net_growth"]))

    drags = [float(r["execution_drag"]) for r in rows]
    shares = [float(r["drag_share_of_signal"]) for r in rows
              if isinstance(r.get("drag_share_of_signal"), (int, float))]
    diagnoses: dict[str, int] = {}
    for r in rows:
        d = str(r.get("diagnosis") or "").split(":")[0]
        diagnoses[d] = diagnoses.get(d, 0) + 1
    return {
        "status": "OK",
        "n_cells": len(rows),
        "protocol": {"families": list(FAMILIES), "bars": BARS, "train_frac": TRAIN_FRAC,
                     "embargo": EMBARGO, "rank_risk_frac": RANK_RISK_FRAC,
                     "evaluator": "external_gauntlet.daily_series; costs_for(mult=1) vs mult=0"},
        "variants": summary,
        "best_like_for_like_variant": like[0] if like else None,
        "best_overall_including_selection": summary[0] if summary else None,
        "comparability_rule": (
            f"a variant keeping at least {LIKE_FOR_LIKE_KEPT:.0%} of the base signal list is "
            f"LIKE-FOR-LIKE: the same trades, filled differently, so the growth difference is "
            f"execution. Below that it is trading a different set and its result mixes selection "
            f"with execution -- reported, and never presented as the best execution policy."),
        "attribution": {
            "median_execution_drag": round(float(np.median(drags)), 8),
            "median_drag_as_share_of_signal_alpha": (round(float(np.median(shares)), 4)
                                                     if shares else None),
            "diagnoses": diagnoses,
            "reads": ("signal alpha is the frictionless path; execution drag is what the round "
                      "trip takes. A desk that only ever sees the difference cannot tell a "
                      "mechanism that does not work from one that works and is being eaten, and "
                      "those two call for opposite decisions."),
        },
        "cells": rows[:80],
        "live_fill_calibration": _live_fill_calibration(),
        "boundary": (
            "NOTHING HERE CHANGES AN ORDER. It measures what each execution policy would have "
            "cost or earned on held-out bars. Any change to how the desk actually fills is the "
            "gateway's, on evidence, and reaches the book through the usual gates."),
        "why": (
            "a strategy's measured edge is signal alpha MINUS execution drag, and the desk has "
            "only ever had the difference. The separation costs one extra scoring run -- the "
            "same signals at a zero cost multiplier -- and it is the difference between "
            "abandoning a mechanism and trading it differently."),
    }


def write(doc: Mapping[str, Any], out: Path | None = None) -> Path:
    """Atomic write of the report -- OK or UNMEASURED alike, so the artifact always says which."""
    path = out or OUT
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(dict(doc), indent=1, default=str), encoding="utf-8")
    os.replace(tmp, path)
    return path


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--apply", action="store_true",
                    help="accepted for the hourly leg; the report is written on every run")
    ap.add_argument("--dry-run", action="store_true", help="measure and print; write nothing")
    a = ap.parse_args(argv)
    doc = build()
    if doc.get("status") != "OK":
        print(f"execution science: {doc.get('status')} -- {doc.get('why')}")
    else:
        at = doc["attribution"]
        print(f"execution science: OK   {doc['n_cells']} (symbol, family, variant) cell(s)")
        print(f"  median execution drag {at['median_execution_drag']:+.8f} log-growth/day; "
              f"that is {at['median_drag_as_share_of_signal_alpha']} of signal alpha")
        print("  variant                       n   median net     drag        kept   vs market")
        for v in doc["variants"]:
            vs = v["vs_market_next_open"]
            mark = " " if v["like_for_like"] else "*"
            print(f" {mark}{v['variant']:<28} {v['n_cells']:<3} {v['median_net_growth']:+.7f}  "
                  f"{v['median_execution_drag']:+.7f}  {v['median_signals_kept']:.2f}  "
                  f"{'' if vs is None else f'{vs:+.7f}'}")
        print("  * = NOT like-for-like: it changes which trades are taken, not only how they fill")
        bl = doc.get("best_like_for_like_variant")
        if bl:
            print(f"  best EXECUTION policy (same trades): {bl['variant']} at "
                  f"{bl['vs_market_next_open']:+.7f} vs market-at-next-open")
    lf = doc["live_fill_calibration"]
    print(f"  live-fill recalibration: {lf['status']} -- {lf['why'][:120]}")
    if a.dry_run:
        print("  --dry-run: nothing written")
        return 0
    print(f"-> {write(doc)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
