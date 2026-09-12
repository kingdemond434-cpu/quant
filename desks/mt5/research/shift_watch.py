"""HAS THE MEASURING STICK MOVED? -- the distribution-shift detector, finally wired.

`libs/research/dist_shift.py` was built 2026-07-29 against constitution L2.10 and, measured by
`check_enforcement_execution` on 2026-09-12, NOTHING outside its own module and its tests has ever
called it: DECORATIVE. Its own docstring says it is "a library the existing revalidation path and
axis screens call" -- and no revalidation path or axis screen ever did. A detector that runs
nowhere has detected nothing, however correct it is (III.16).

THE QUESTION IT ANSWERS, and why it is worth capital. Regime labels say WHICH state the market is
in. This asks whether the distribution the signal was SCREENED IN still holds -- because every
threshold the desk calibrated (stop distances in ATR units, z-score windows, cost floors, spread
guards) was fitted in the old distribution. A relationship can survive while the ground beneath it
moves, and then the sleeve is still trading, still passing its gates on old evidence, and sized by
constants that no longer describe the market. That failure is silent by construction: nothing
errors, the equity curve just stops meaning what it meant.

WHAT IT READS. Per-trade returns are not available -- `shadow_state` keeps aggregates only (n,
cum_r) -- so this runs on the thing that actually defines the calibration: the H1 return
distribution of each symbol the live book trades. Reference window against recent window, the
library's own `split_and_check`, and the verdict attributed back to every LIVE sleeve on that
symbol.

DIRECTION IS ONE-WAY, exactly as the library insists. A detected shift NEVER promotes and never
auto-demotes: it flags the sleeve for RE-VALIDATION and recommends a downward confidence haircut.
A monitor that could raise confidence would be an alpha claim wearing a diagnostic's clothes, and
a monitor that could demote would be a growth cut with no missed-growth ledger line behind it.
This publishes; the promoter and the allocator decide.

    python desks/mt5/research/shift_watch.py [--apply]
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
OUT = DESK / "reports" / "DIST_SHIFT.json"

#: Bars of H1 history to judge on. 1,500 H1 bars is roughly nine months of a 24h market, which is
#: long enough that the reference window spans more than one regime and a single quiet fortnight
#: cannot masquerade as a shift. `split_and_check` takes the most recent 25% as the recent window
#: by default, so this gives a ~375-bar recent window against a ~1,125-bar reference.
BARS = 1500


def _live_symbols() -> dict[str, list[str]]:
    """Symbol -> the LIVE sleeves riding on it. Only funded rows: a shift under a sleeve nobody
    trades is a research curiosity, and this exists to protect capital."""
    try:
        doc = json.loads(SLEEVES.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    rows = doc if isinstance(doc, list) else (doc.get("sleeves") or [])
    out: dict[str, list[str]] = {}
    for r in rows:
        if not isinstance(r, dict) or str(r.get("status", "")).upper() != "LIVE":
            continue
        sym = str(r.get("symbol") or "").strip()
        if sym:
            out.setdefault(sym, []).append(str(r.get("name") or r.get("family") or "?"))
    return out


def _returns(symbol: str) -> Any:
    """H1 log returns for a symbol, or None when the desk holds no bars for it.

    UNMEASURED IS A VERDICT. A symbol with no parquet is reported as such rather than skipped
    silently -- a live sleeve whose own price history the desk cannot load is itself a finding.
    """
    try:
        import numpy as np
        import pandas as pd
    except ImportError:
        return None
    p = UNI / f"{symbol}_H1.parquet"
    if not p.exists():
        return None
    try:
        df = pd.read_parquet(p)
    except (OSError, ValueError):
        return None
    col = next((c for c in ("close", "Close", "c") if c in df.columns), None)
    if col is None or len(df) < 200:
        return None
    close = pd.to_numeric(df[col], errors="coerce").to_numpy(dtype="float64")
    close = close[np.isfinite(close) & (close > 0)][-BARS:]
    if close.size < 200:
        return None
    return np.diff(np.log(close))


def build() -> dict[str, Any]:
    now = datetime.now(tz=UTC)
    try:
        from libs.research.dist_shift import split_and_check
    except ImportError as exc:
        return {"at": now.isoformat(timespec="seconds"), "status": "UNMEASURED",
                "why": f"dist_shift not importable ({exc}) -- UNMEASURED, never 'no shift'"}

    by_symbol = _live_symbols()
    rows: list[dict[str, Any]] = []
    shifted: list[dict[str, Any]] = []
    unmeasured: list[str] = []

    for sym, sleeves in sorted(by_symbol.items()):
        r = _returns(sym)
        if r is None:
            unmeasured.append(sym)
            rows.append({"symbol": sym, "sleeves": sleeves, "verdict": "UNMEASURED",
                         "why": "no usable H1 history on this box -- a LIVE sleeve whose own "
                                "price series cannot be loaded is itself a finding"})
            continue
        try:
            v = split_and_check(r)
        except Exception as exc:
            rows.append({"symbol": sym, "sleeves": sleeves, "verdict": "UNMEASURED",
                         "why": f"{type(exc).__name__}: {exc}"})
            unmeasured.append(sym)
            continue
        verdict = str(v.get("verdict") or v.get("agreed") or "?")
        row = {"symbol": sym, "sleeves": sleeves, "verdict": verdict,
               "n_sleeves": len(sleeves), "detail": v}
        rows.append(row)
        if verdict.upper() not in ("STABLE", "NO_SHIFT", "OK", "?"):
            shifted.append({"symbol": sym, "verdict": verdict, "sleeves": sleeves})

    return {
        "at": now.isoformat(timespec="seconds"),
        "bars": BARS,
        "n_symbols": len(rows),
        "n_shifted": len(shifted),
        "n_unmeasured": len(unmeasured),
        "shifted": shifted,
        "symbols": rows,
        "status": ("UNMEASURED" if not rows else ("ATTENTION" if shifted else "OK")),
        "action": ("A shift FLAGS the sleeve for re-validation and recommends a DOWNWARD "
                   "confidence haircut. It never promotes and never auto-demotes: this organ "
                   "publishes, the promoter and the allocator decide."),
        "why": ("every calibrated constant -- stop distance in ATR units, z-score window, cost "
                "floor, spread guard -- was fitted in a distribution. If that distribution moved, "
                "the sleeve is sized by numbers that no longer describe the market, and nothing "
                "errors to say so."),
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--apply", action="store_true", help="write the report")
    a = ap.parse_args(argv)
    doc = build()
    print(f"distribution shift: {doc.get('status')}  "
          f"{doc.get('n_symbols', 0)} symbol(s), {doc.get('n_shifted', 0)} shifted, "
          f"{doc.get('n_unmeasured', 0)} unmeasured")
    for s in (doc.get("shifted") or [])[:15]:
        print(f"  SHIFTED  {s['symbol']:<12} {s['verdict']:<18} "
              f"{len(s['sleeves'])} live sleeve(s)")
    if not a.apply:
        print("  --apply not given; nothing written")
        return 0
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(doc, indent=1, default=str), encoding="utf-8")
    print(f"-> {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
