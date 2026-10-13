"""WHICH MINUTE INSIDE A SLEEVE'S OWN WINDOW IS CHEAPEST TO CROSS, AND WHETHER WAITING FOR IT PAYS.

`entry_timing.py` prices a certificate's entry window by the HOUR from `cost_surface.json`. This
organ extends it one level down: inside the hour a fill is ALLOWED to happen in, which MINUTE
has the lowest measured spread, and what does waiting for that minute cost in forgone move?

    cost(m)   half the median spread stamped on sub-hour bars at minute-offset m (points ->
              price via the registry's tick_size), in R. One side of the round trip per leg.
    drift(m)  the mean signed move (sleeve direction) from offset 0 to offset m, in R, across the
              same days. Entering late FORGOES it; exiting late EARNS it.
    lift(m)   cost(0) - cost(m) - max(0, adverse drift(m) + 2 SE), adverse = forgone on entry,
              given back on exit. Favourable drift is credited at zero.

A minute is RECOMMENDED only when that conservative lift is positive; otherwise KEEP_CURRENT.
A cheaper but later fill that gives the edge back is reported as net worse, which is the
point of measuring the drift at all.

WHAT IT WILL NOT DO:
  * It never moves a trade out of its window and never changes a signal. Candidates are the
    offsets inside the first hour after the signal bar closes, which is the hour the gateway
    already places in.
  * It never touches the gateway. Report only: `desks/mt5/reports/EXECUTION_TIMING.json`.
  * It never invents a minute surface. Only sub-hour bars on disk (M1 > M5 > M15) are read; a
    symbol with H1 bars alone is UNMEASURED, because an H1 bar carries one spread stamp an hour.
  * A resting stop entry (session_range_breakout) fires where PRICE reaches the level, so its
    entry minute is NOT_SELECTABLE; its exit is still priced.

R BASIS: the identity carries no stop distance, so 1R := the median 14-bar H1 true range of the
symbol. That basis is written into every row. Slippage beyond the quoted spread has no
per-minute measurement on disk and is reported UNMEASURED rather than zero (L1.28a).

    python desks/mt5/research/execution_timing.py
"""
from __future__ import annotations

import argparse
import json
import math
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

BASE = Path(__file__).resolve().parent.parent
ROOT = BASE.parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from desks.mt5.research.entry_timing import WINDOWS  # noqa: E402

REGISTRY_REL = "desks/mt5/data/sleeve_registry.json"
UNIVERSE_REL = "desks/mt5/data/universe/universe.json"
BARS_REL = "desks/mt5/data/universe"
OUT_REL = "desks/mt5/reports/EXECUTION_TIMING.json"

#: Finest first. H1 is deliberately absent: one stamp an hour is not a minute surface.
SUBHOUR = (("M1", 1), ("M5", 5), ("M15", 15))
#: Days an offset must be observed on before its median or drift is read.
MIN_DAYS = 20
#: Families whose entry is a resting stop: the fill minute is price's choice, not ours.
RESTING_STOP_FAMILIES = frozenset({"session_range_breakout"})
UNMEASURED = "UNMEASURED"
RECOMMEND = "MOVE_TO_BEST_MINUTE"
KEEP = "KEEP_CURRENT"
NOT_SELECTABLE = "NOT_SELECTABLE"


def _read(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return value if isinstance(value, dict) else {}


def direction_sign(identity: dict[str, Any]) -> int:
    """+1 long, -1 short, 0 when the identity does not say (drift is then UNMEASURED)."""
    # A family's own `side` parameter outranks the identity's direction, which some families
    # leave at its LONG default while the cell trades short.
    side = (identity.get("params") or {}).get("side")
    raw = str(side if side is not None else identity.get("direction") or "")
    raw = raw.strip().upper()
    if raw in ("LONG", "BUY", "1", "+1"):
        return 1
    if raw in ("SHORT", "SELL", "-1"):
        return -1
    return 0


def signal_hour(selector: str) -> int | None:
    """The UTC hour a windowed selector places in; None for continuous (every hour)."""
    win = WINDOWS.get(str(selector or "").strip().lower())
    return None if win is None else win[0]


def load_bars(root: Path, symbol: str) -> list[tuple[str, int, Any]]:
    """Every sub-hour bar file on disk for the symbol, finest first."""
    import pandas as pd
    found: list[tuple[str, int, Any]] = []
    for tf, step in SUBHOUR:
        path = root / BARS_REL / f"{symbol}_{tf}.parquet"
        if path.exists():
            try:
                frame = pd.read_parquet(path)
            except Exception:
                continue
            if {"open", "spread"} <= set(frame.columns) and len(frame):
                found.append((tf, step, frame))
    return found


def r_unit(root: Path, symbol: str) -> float | None:
    """Median 14-bar H1 true range, in price."""
    import pandas as pd
    path = root / BARS_REL / f"{symbol}_H1.parquet"
    try:
        h = pd.read_parquet(path, columns=["high", "low", "close"])
    except Exception:
        return None
    if len(h) < 50:
        return None
    prev = h["close"].shift(1)
    tr = pd.concat([h["high"] - h["low"], (h["high"] - prev).abs(), (h["low"] - prev).abs()],
                   axis=1).max(axis=1)
    atr = tr.rolling(14).mean().dropna()
    med = float(atr.tail(2000).median()) if len(atr) else float("nan")
    return med if math.isfinite(med) and med > 0 else None


def minute_profile(frame: Any, step: int, hour: int | None, sign: int,
                   tick: float, r: float) -> dict[str, Any]:
    """Per offset inside the placing hour: half-spread cost and signed drift from offset 0, in R."""
    import pandas as pd
    idx = pd.DatetimeIndex(frame.index)
    df = pd.DataFrame({"open": frame["open"].to_numpy(float),
                       "spread": frame["spread"].to_numpy(float),
                       "anchor": idx.floor("h"), "offset": idx.minute}, index=idx)
    if hour is not None:
        df = df[idx.hour == hour]
    if df.empty:
        return {"offsets": [], "why": "no sub-hour bars in the placing hour"}
    base = df[df["offset"] == 0].set_index("anchor")["open"]
    rows = []
    for off in range(0, 60, step):
        cell = df[df["offset"] == off]
        n = len(cell)
        if n < MIN_DAYS:
            rows.append({"offset_min": off, "n": n, "status": UNMEASURED})
            continue
        # EXPECTED cost is the mean: a minute whose median ties its neighbours can still carry
        # a fatter tail, and the tail is paid on the trades that land in it.
        cost = 0.5 * float(cell["spread"].mean()) * tick / r
        row: dict[str, Any] = {"offset_min": off, "n": n, "status": "MEASURED",
                               "spread_mean_pts": round(float(cell["spread"].mean()), 4),
                               "spread_p50_pts": float(cell["spread"].median()),
                               "spread_p90_pts": float(cell["spread"].quantile(0.9)),
                               "half_spread_R": round(cost, 6)}
        if sign:
            joined = cell.set_index("anchor")["open"].to_frame("p").join(base.rename("p0"),
                                                                          how="inner")
            mv = sign * (joined["p"] - joined["p0"]) / r
            if len(mv) >= MIN_DAYS:
                row["drift_R"] = round(float(mv.mean()), 6)
                row["drift_se_R"] = round(float(mv.std(ddof=1) / math.sqrt(len(mv))), 6)
        rows.append(row)
    return {"offsets": rows}


def choose(rows: list[dict[str, Any]], leg: str) -> dict[str, Any]:
    """Current fill (offset 0) against the best net minute in the window."""
    measured = [r for r in rows if r.get("status") == "MEASURED"]
    cur = next((r for r in measured if r["offset_min"] == 0), None)
    if cur is None:
        return {"verdict": UNMEASURED, "why": f"offset 0 has fewer than {MIN_DAYS} days"}
    cheapest = min(measured, key=lambda r: r["half_spread_R"])
    out: dict[str, Any] = {
        "current_minute": 0, "current_cost_R": cur["half_spread_R"],
        "cheapest_minute": cheapest["offset_min"], "cheapest_cost_R": cheapest["half_spread_R"],
        "gross_saving_R": round(cur["half_spread_R"] - cheapest["half_spread_R"], 6)}
    if not all("drift_R" in r for r in measured):
        out.update(verdict=UNMEASURED, why="drift not measurable (direction unknown or thin)")
        return out
    sgn = -1.0 if leg == "entry" else 1.0
    best, best_lift = cur, 0.0
    for r in measured:
        saving = cur["half_spread_R"] - r["half_spread_R"]
        # Only a COST saving earns a minute. Drift is charged at its upper 2-SE bound when it is
        # adverse and credited at ZERO when it is favourable: harvesting an unconditional drift
        # is a new directional bet, not cheaper execution of this signal.
        adverse = max(0.0, -sgn * r["drift_R"] + 2.0 * r["drift_se_R"])
        lift = saving - adverse
        if saving > 0 and lift > best_lift:
            best, best_lift = r, lift
    out.update(best_minute=best["offset_min"], best_cost_R=best["half_spread_R"],
               drift_at_best_R=best["drift_R"], lift_R_per_trade=round(best_lift, 6),
               edge_decay_R_at_cheapest=cheapest["drift_R"],
               verdict=RECOMMEND if best is not cur else KEEP)
    return out


def assess(root: Path | None = None) -> dict[str, Any]:
    root = root or ROOT
    sleeves = (_read(root / REGISTRY_REL).get("sleeves") or {})
    meta = _read(root / UNIVERSE_REL)
    cache: dict[tuple[Any, ...], dict[str, Any]] = {}
    bars: dict[str, Any] = {}
    rows: list[dict[str, Any]] = []
    for name, entry in sorted(sleeves.items()):
        if not isinstance(entry, dict) or entry.get("status") != "LIVE":
            continue
        ident = entry.get("identity") or {}
        sym = str(ident.get("symbol") or "")
        family = str(ident.get("family") or "")
        hour = signal_hour(str(ident.get("selector") or ""))
        sign = direction_sign(ident)
        row: dict[str, Any] = {"sleeve": name, "symbol": sym, "family": family,
                               "selector": ident.get("selector"), "placing_hour_utc": hour,
                               "slippage": UNMEASURED}
        if sym not in bars:
            bars[sym] = load_bars(root, sym)
        loaded = bars[sym]
        tick = float((meta.get(sym) or {}).get("tick_size") or 0.0)
        r = r_unit(root, sym) if loaded and tick > 0 else None
        if not loaded or r is None:
            row.update(verdict=UNMEASURED,
                       why=("only H1 bars on disk: one spread stamp an hour is no minute surface"
                            if not loaded else "no tick_size or H1 range for an R unit"))
            rows.append(row)
            continue
        def profile(h: int | None, _l: Any = loaded, _t: float = tick, _r: float = r,
                    _s: int = sign, _y: str = sym) -> tuple[str, dict[str, Any]]:
            key = (_y, h, _s)
            if key not in cache:
                # Finest timeframe whose offset 0 holds MIN_DAYS; else the finest (reads thin).
                profs = [(tf, minute_profile(fr, st, h, _s, _t, _r)) for tf, st, fr in _l]
                cache[key] = next(((tf, p) for tf, p in profs if any(
                    o["offset_min"] == 0 and o.get("status") == "MEASURED"
                    for o in p["offsets"])), profs[0])
            return cache[key]
        tf, prof = profile(hour)
        # The exit hour is not in the identity, so the exit is priced on the all-hours profile.
        etf, eprof = profile(None)
        row.update(bars_tf=tf, exit_bars_tf=etf, R_basis="median H1 ATR14", R_price=round(r, 8),
                   drift_basis="unconditional on the placing hour; signal times not replayed",
                   exit_basis="all hours (exit hour not declared in the identity)",
                   minute_profile=prof["offsets"])
        exit_leg = choose(eprof["offsets"], "exit")
        entry_leg = ({"verdict": NOT_SELECTABLE, "why": "resting stop: price picks the minute"}
                     if family in RESTING_STOP_FAMILIES else choose(prof["offsets"], "entry"))
        row.update(entry=entry_leg, exit=exit_leg)
        lifts = [leg.get("lift_R_per_trade") for leg in (entry_leg, exit_leg)
                 if isinstance(leg.get("lift_R_per_trade"), (int, float))]
        row["verdict"] = (RECOMMEND if RECOMMEND in (entry_leg["verdict"], exit_leg["verdict"])
                          else KEEP if lifts else UNMEASURED)
        row["total_lift_R_per_trade"] = round(sum(lifts), 6) if lifts else None
        rows.append(row)
    counts: dict[str, int] = {}
    for row in rows:
        counts[row["verdict"]] = counts.get(row["verdict"], 0) + 1
    return {"schema": "execution-timing-1",
            "built_at": datetime.now(UTC).isoformat(timespec="seconds"),
            "report_only": True, "min_days": MIN_DAYS,
            "n_sleeves": len(rows), "verdicts": counts,
            "measured_lift": [{"sleeve": r["sleeve"], "lift_R": r["total_lift_R_per_trade"],
                               "verdict": r["verdict"]}
                              for r in rows if r.get("total_lift_R_per_trade") is not None],
            "sleeves": rows}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--out", default=str(ROOT / OUT_REL))
    args = ap.parse_args(argv)
    report = assess()
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=1, sort_keys=True), encoding="utf-8")
    print(json.dumps({"n_sleeves": report["n_sleeves"], "verdicts": report["verdicts"]}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
