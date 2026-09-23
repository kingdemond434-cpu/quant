"""F23 -- COUNTERFACTUALS AT THE RESOLUTION THE SLEEVE TRADES, and the cost of not doing it.

THE PRINCIPAL, 2026-09-12:

    M1/M5/M15/tick-level replay, and enough entry/stop/exit metadata on every live decision to
    make it replayable.

THE GAP, AS THE LEDGER STATES IT, AND THE CODE SAYS IT OUT LOUD: `action_counterfactuals` already
measures alternative sizes, exits and the opposite side in dE[log W] and turns findings into
research tasks -- and it SKIPS sub-H1 sleeves, because H1 bars cannot reconstruct them. Three LIVE
sleeves are sub-H1 today: xau_m5_anti_breakout_overlap, xau_m5_anti_momentum_ny and
xau_m15_anti_breakout. Every counterfactual the desk has ever run has been silent about them.

THE DATA IS ALREADY ON THE BOX. XAUUSD_M1 and XAUUSD_M5 parquets, four M15 symbols, and 7.09 GB of
tick tape across 6,877 files. The skip was never a data problem; nothing had been pointed at it.

WHAT THIS ADDS BEYOND "RUN IT AT M5". It runs the IDENTICAL counterfactual at both resolutions and
reports the disagreement, so the desk learns what the H1 approximation was actually costing rather
than being told it was wrong. An M5 sleeve's stop can be hit and recovered inside one H1 bar: on
H1 that trade survives and on M5 it is stopped out, and the two answers differ by a full R. The
size of that gap IS the value of this organ, and until it is measured "H1 cannot reconstruct them"
is a reasonable belief rather than a number.

ONE VALIDATOR, NOT A SECOND ONE. The counterfactual itself is
`action_counterfactuals.counterfactual_path` -- the same function, the same horizons, the same
1R-stop rule -- called with a different bar frame. A re-implementation here would prove that two
programs agree, which is precisely what this repo forbids.

    python desks/mt5/research/subhour_counterfactuals.py [--apply]
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

DESK = Path(__file__).resolve().parents[1]
ROOT = DESK.parent.parent
for _p in (str(DESK), str(DESK / "research"), str(ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

UNI = DESK / "data" / "universe"
SLEEVES = DESK / "data" / "sleeves.json"
LEDGER = DESK / "data" / "live_ledger.jsonl"
OUT = DESK / "reports" / "SUBHOUR_COUNTERFACTUALS.json"

#: Timeframes this organ can replay at, finest first. A sleeve is replayed on the FINEST frame the
#: box holds for its symbol that is no coarser than the sleeve's own -- replaying an M5 sleeve on
#: M15 would repeat the original error one step smaller.
FRAMES: tuple[str, ...] = ("M1", "M5", "M15")

#: Minutes per frame, for deciding which frames are fine enough for a given sleeve.
MINUTES: dict[str, int] = {"M1": 1, "M5": 5, "M15": 15, "H1": 60, "H4": 240, "D1": 1440}


def _as_ts(v: Any) -> Any:
    import pandas as pd
    t = pd.Timestamp(str(v))
    return t.tz_localize("UTC") if t.tzinfo is None else t


def _read_json(p: Path) -> Any:
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def _bars(symbol: str, frame: str) -> Any:
    try:
        import pandas as pd
    except ImportError:
        return None
    p = UNI / f"{symbol}_{frame}.parquet"
    if not p.exists():
        return None
    try:
        df = pd.read_parquet(p)
    except (OSError, ValueError):
        return None
    if not {"high", "low", "close"} <= set(df.columns):
        return None
    idx = df.index
    if getattr(idx, "tz", None) is None:
        try:
            df.index = idx.tz_localize("UTC")
        except (TypeError, ValueError):
            return None
    return df


def _subhour_sleeves() -> list[dict[str, Any]]:
    """LIVE sleeves whose own timeframe is finer than H1 -- exactly the ones H1 cannot replay."""
    doc = _read_json(SLEEVES)
    rows = doc if isinstance(doc, list) else ((doc or {}).get("sleeves") or [])
    out: list[dict[str, Any]] = []
    for r in rows:
        if not isinstance(r, dict) or str(r.get("status", "")).upper() != "LIVE":
            continue
        tf = str(r.get("timeframe") or "").upper()
        if tf and MINUTES.get(tf, 10 ** 6) < 60:
            out.append({"sleeve": r.get("name") or r.get("sleeve"),
                        "symbol": r.get("symbol"), "timeframe": tf})
    return out


def _trades_for(sleeve: str) -> list[dict[str, Any]]:
    """Realised deals for one sleeve, from the live ledger. Its own record, nothing inferred."""
    if not LEDGER.exists():
        return []
    out: list[dict[str, Any]] = []
    for ln in LEDGER.read_text(encoding="utf-8", errors="replace").splitlines():
        ln = ln.strip()
        if not ln:
            continue
        try:
            d = json.loads(ln)
        except ValueError:
            continue
        if str(d.get("sleeve") or "") != sleeve:
            continue
        entry = d.get("entry_price") or d.get("fill_price")
        sl = d.get("sl")
        if not isinstance(entry, (int, float)) or not isinstance(sl, (int, float)):
            continue
        risk = abs(float(entry) - float(sl))
        if risk <= 0:
            continue
        out.append({"time": d.get("time"), "side": int(d.get("side") or 0),
                    "entry": float(entry), "risk": risk,
                    "deal": d.get("deal"), "r_multiple": d.get("r_multiple")})
    return out


def build() -> dict[str, Any]:
    now = datetime.now(tz=UTC)
    try:
        import numpy as np
        import pandas as pd  # noqa: F401
    except ImportError as exc:
        return {"at": now.isoformat(timespec="seconds"), "status": "UNMEASURED",
                "why": f"numpy/pandas unavailable ({exc})"}
    try:
        from research.action_counterfactuals import counterfactual_path
    except ImportError as exc:
        return {"at": now.isoformat(timespec="seconds"), "status": "UNMEASURED",
                "why": (f"the canonical counterfactual is not importable ({exc}). This organ "
                        f"refuses to re-implement it -- a second implementation would prove only "
                        f"that two programs agree.")}

    sleeves = _subhour_sleeves()
    if not sleeves:
        return {"at": now.isoformat(timespec="seconds"), "status": "UNMEASURED",
                "why": ("no LIVE sleeve declares a sub-H1 timeframe. That is the honest reading "
                        "of sleeves.json and not a claim that none exists.")}

    rows: list[dict[str, Any]] = []
    coverage: list[dict[str, Any]] = []
    for sl in sleeves:
        sym, tf = str(sl["symbol"]), str(sl["timeframe"])
        want = [f for f in FRAMES if MINUTES[f] <= MINUTES.get(tf, 60)]
        native = None
        native_frame = None
        for f in want:
            b = _bars(sym, f)
            if b is not None and len(b) > 200:
                native, native_frame = b, f
                break
        h1 = _bars(sym, "H1")
        trades = _trades_for(str(sl["sleeve"]))
        coverage.append({**sl, "native_frame": native_frame,
                         "native_bars": None if native is None else len(native),
                         "h1_bars": None if h1 is None else len(h1),
                         "n_trades": len(trades),
                         "replayable": bool(native is not None and h1 is not None and trades)})
        if native is None or h1 is None or not trades:
            continue
        for t in trades:
            nat = counterfactual_path(native, str(t["time"]), str(t["time"]),
                                      int(t["side"]), float(t["entry"]), float(t["risk"]))
            if not nat:
                # The NATIVE replay is the product; without it there is nothing to report for
                # this trade, and the reason is always the same -- too few bars after entry.
                continue
            # THE H1 COMPARISON IS A SEPARATE QUESTION AND FAILS SEPARATELY. Measured on the
            # first run: the one replayable trade is 2026-09-11 21:51 and the H1 frame ends at
            # 23:00, so the coarse side had two bars where it needs a full horizon. Reporting
            # the whole trade as unmeasured because the COMPARISON was unavailable would have
            # thrown away the native replay, which is the thing this organ exists to produce.
            coarse = counterfactual_path(h1, str(t["time"]), str(t["time"]),
                                         int(t["side"]), float(t["entry"]), float(t["risk"]))
            gaps: dict[str, float] = {}
            if coarse:
                for k, v in (nat.get("hold") or {}).items():
                    cv = (coarse.get("hold") or {}).get(k)
                    if isinstance(cv, (int, float)) and isinstance(v, (int, float)):
                        gaps[k] = round(float(v) - float(cv), 4)
            after_h1 = int((h1.index > _as_ts(t["time"])).sum())
            rows.append({
                "sleeve": sl["sleeve"], "symbol": sym, "sleeve_timeframe": tf,
                "native_frame": native_frame, "deal": t.get("deal"), "at": t.get("time"),
                "realised_r": t.get("r_multiple"),
                "native_hold": nat.get("hold"),
                "native_stop_hit_bar": nat.get("stop_hit_bar"),
                "h1_comparison": ("OK" if coarse else "UNAVAILABLE"),
                "h1_comparison_why": (None if coarse else
                                      f"the H1 frame holds {after_h1} bar(s) after this entry, "
                                      f"fewer than the counterfactual horizon needs. The trade "
                                      f"is too recent for a coarse comparison; the native "
                                      f"replay above is unaffected."),
                "h1_hold": (coarse or {}).get("hold"),
                "h1_stop_hit_bar": (coarse or {}).get("stop_hit_bar"),
                "hold_gap_native_minus_h1": gaps or None,
                "stop_verdict_differs": (None if not coarse else bool(
                    (nat.get("stop_hit_bar") is None) != (coarse.get("stop_hit_bar") is None))),
            })

    replayable = [c for c in coverage if c["replayable"]]
    if not rows:
        return {
            "at": now.isoformat(timespec="seconds"),
            "status": "UNMEASURED",
            "n_subhour_sleeves": len(sleeves),
            "coverage": coverage,
            "why": (
                "no sub-H1 sleeve has BOTH a native bar frame on this box and a realised deal in "
                "the live ledger with a usable entry and stop. The machinery is wired and the "
                "ledger is the constraint -- the coverage block names exactly which half is "
                "missing per sleeve, so this becomes measurable on its own as the book trades."),
            "boundary": ("nothing here trades, sizes or promotes; it replays decisions already "
                         "taken"),
        }

    import numpy as np
    compared = [r for r in rows if r["h1_comparison"] == "OK"]
    diffs = [abs(v) for r in compared for v in (r["hold_gap_native_minus_h1"] or {}).values()]
    n_stop_flip = sum(1 for r in compared if r["stop_verdict_differs"])
    return {
        "at": now.isoformat(timespec="seconds"),
        "status": "OK",
        "n_subhour_sleeves": len(sleeves),
        "n_replayable": len(replayable),
        "n_trades_replayed": len(rows),
        "coverage": coverage,
        "n_h1_comparisons": len(compared),
        "approximation_error": {
            "status": "OK" if compared else "UNMEASURED",
            "why": (None if compared else
                    "every replayed trade is too recent for the H1 frame to supply a full "
                    "counterfactual horizon after entry, so the approximation error cannot be "
                    "computed yet. The NATIVE replays are unaffected and are reported above; "
                    "this measurement arrives on its own as the trades age."),
            "mean_abs_hold_gap_R": round(float(np.mean(diffs)), 4) if diffs else None,
            "max_abs_hold_gap_R": round(float(np.max(diffs)), 4) if diffs else None,
            "n_stop_verdict_flips": n_stop_flip,
            "share_stop_verdict_flips": (round(n_stop_flip / len(compared), 4)
                                         if compared else None),
            "reads": ("the gap between the SAME counterfactual computed on native bars and on H1. "
                      "A stop-verdict flip is the expensive one: an M5 stop can be hit and "
                      "recovered inside a single H1 bar, so H1 says the trade survived and M5 "
                      "says it was stopped -- a full R of disagreement about what happened."),
        },
        "trades": rows[:60],
        "validator": ("action_counterfactuals.counterfactual_path, unmodified, called with a "
                      "different bar frame. Same horizons, same 1R-stop rule."),
        "boundary": (
            "NOTHING HERE TRADES, SIZES OR PROMOTES. It replays decisions already taken, at the "
            "resolution they were actually taken at."),
        "why": (
            "action_counterfactuals says in its own code that it skips sub-H1 sleeves because H1 "
            "bars cannot reconstruct them. Three LIVE sleeves are sub-H1, the M1/M5/M15 parquets "
            "and 7 GB of tick tape are already on the box, and every counterfactual the desk has "
            "run has been silent about them."),
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--apply", action="store_true")
    a = ap.parse_args(argv)
    doc = build()
    print(f"sub-hour counterfactuals: {doc.get('status')}   "
          f"{doc.get('n_subhour_sleeves', 0)} sub-H1 LIVE sleeve(s)")
    for c in doc.get("coverage") or []:
        print(f"  {str(c['sleeve'])[:34]:<34} {c['symbol']:<8} {c['timeframe']:<4} "
              f"native={c['native_frame'] or '-':<4} "
              f"bars={c['native_bars'] or 0:<7} trades={c['n_trades']:<4} "
              f"{'REPLAYABLE' if c['replayable'] else 'not yet'}")
    if doc.get("status") != "OK":
        print(f"  {str(doc.get('why'))[:200]}")
    else:
        ae = doc["approximation_error"]
        print(f"  {doc['n_trades_replayed']} trade(s) replayed at native resolution, "
              f"{doc['n_h1_comparisons']} with an H1 comparison")
        if ae["status"] == "OK":
            print(f"  H1 approximation error: mean |gap| {ae['mean_abs_hold_gap_R']} R, "
                  f"max {ae['max_abs_hold_gap_R']} R, "
                  f"{ae['n_stop_verdict_flips']} stop-verdict flip(s) "
                  f"({ae['share_stop_verdict_flips']})")
        else:
            print(f"  H1 approximation error: UNMEASURED -- {ae['why'][:140]}")
        for r in doc["trades"][:4]:
            print(f"    {str(r['sleeve'])[:28]:<28} {str(r['at'])[:16]} "
                  f"native {r['native_frame']} hold={r['native_hold']} "
                  f"stop_bar={r['native_stop_hit_bar']}  h1={r['h1_comparison']}")
    if not a.apply:
        print("  --apply not given; nothing written")
        return 0
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(doc, indent=1, default=str), encoding="utf-8")
    print(f"-> {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
