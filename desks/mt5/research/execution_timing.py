"""WHICH MINUTE INSIDE A SLEEVE'S OWN WINDOW IS CHEAPEST TO CROSS, AND WHETHER WAITING FOR IT PAYS.

`entry_timing.py` prices a certificate's entry window by the HOUR from `cost_surface.json`. This
organ extends it one level down: inside the hour a fill is ALLOWED to happen in, which MINUTE
has the lowest measured spread, and what does waiting for that minute cost in forgone move?

    cost(m)   half the median spread stamped on sub-hour bars at minute-offset m (points ->
              price via the registry's tick_size), in R. One side of the round trip per leg.
    drift(m)  the mean signed move (sleeve direction) from offset 0 to offset m, in R, across the
              same days. Entering late FORGOES it; exiting late EARNS it.
    lift(m)   saving(m) - max(0, adverse drift(m)), per paired day; adverse = forgone on entry,
              given back on exit. Favourable drift is credited at zero.

A minute is RECOMMENDED only when the LOWER confidence bound of the paired saving, minus the
UPPER bound of adverse drift, is positive, both at a Bonferroni z over every candidate minute
(the minute is an argmin over up to 59 offsets; its in-sample saving is otherwise optimistic).
A leg whose fill hour is not fixed (continuous selector, undeclared exit hour) is UNMEASURED:
pricing it on an all-hours pooled spread credits other hours' costs to this fill.
A cheaper but later fill that gives the edge back is reported as net worse, which is the
point of measuring the drift at all.

WHAT IT WILL NOT DO:
  * It never moves a trade out of its window and never changes a signal. Candidates are the
    offsets inside the first hour after the signal bar closes, which is the hour the gateway
    already places in.
  * It never touches the gateway. Report only: `desks/mt5/reports/EXECUTION_TIMING.json`.
  * It never invents a minute surface. Only sub-hour bars on disk (M1 > M5 > M15 > M30) are read; a
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
SUBHOUR = (("M1", 1), ("M5", 5), ("M15", 15), ("M30", 30))
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


def _z_one_sided(alpha: float) -> float:
    """Upper-tail standard normal quantile by bisection on erfc (stdlib only)."""
    lo, hi = 0.0, 10.0
    for _ in range(80):
        mid = 0.5 * (lo + hi)
        if 0.5 * math.erfc(mid / math.sqrt(2.0)) > alpha:
            lo = mid
        else:
            hi = mid
    return 0.5 * (lo + hi)


def _mean_se(values: list[float]) -> tuple[float, float]:
    n = len(values)
    mean = sum(values) / n
    var = sum((v - mean) ** 2 for v in values) / (n - 1) if n > 1 else 0.0
    return mean, math.sqrt(var / n)


def minute_profile(frame: Any, step: int, hour: int, sign: int,
                   tick: float, r: float) -> dict[str, Any]:
    """Per offset inside the placing hour: PAIRED per-day half-spread saving against offset 0
    and signed drift from offset 0, both in R. One row per day is one trade opportunity: a
    windowed sleeve places at most once a day in its hour, so `n_trades` counts paired days in
    THAT hour, never bars pooled over other hours."""
    import pandas as pd
    idx = pd.DatetimeIndex(frame.index)
    df = pd.DataFrame({"open": frame["open"].to_numpy(float),
                       "spread": frame["spread"].to_numpy(float),
                       "anchor": idx.floor("h"), "offset": idx.minute}, index=idx)
    df = df[idx.hour == hour]
    if df.empty:
        return {"offsets": [], "why": "no sub-hour bars in the placing hour"}
    base = df[df["offset"] == 0].drop_duplicates("anchor").set_index("anchor")
    rows: list[dict[str, Any]] = []
    for off in range(0, 60, step):
        cell = df[df["offset"] == off].drop_duplicates("anchor").set_index("anchor")
        j = cell[["open", "spread"]].join(base[["open", "spread"]], rsuffix="0", how="inner")
        n = len(j)
        if n < MIN_DAYS:
            rows.append({"offset_min": off, "n_trades": n, "status": UNMEASURED})
            continue
        saving = (0.5 * (j["spread0"] - j["spread"]) * tick / r).tolist()
        row: dict[str, Any] = {"offset_min": off, "n_trades": n, "status": "MEASURED",
                               "spread_mean_pts": round(float(j["spread"].mean()), 4),
                               "spread_p50_pts": float(j["spread"].median()),
                               "spread_p90_pts": float(j["spread"].quantile(0.9)),
                               "half_spread_R": round(0.5 * float(j["spread"].mean()) * tick / r,
                                                      6),
                               "_saving": saving}
        if sign:
            row["_drift"] = (sign * (j["open"] - j["open0"]) / r).tolist()
            m, se = _mean_se(row["_drift"])
            row["drift_R"], row["drift_se_R"] = round(m, 6), round(se, 6)
        rows.append(row)
    return {"offsets": rows}


def choose(rows: list[dict[str, Any]], leg: str, alpha: float = 0.05) -> dict[str, Any]:
    """Current fill (offset 0) against the best net minute, with the selection over every
    candidate minute paid for: each minute's bound uses a Bonferroni z at alpha / k.

        lift      = mean(saving) - max(0, mean(adverse drift))
        lift_lcb  = LCB(saving)  - max(0, UCB(adverse drift))
        lift_ucb  = UCB(saving)  - max(0, LCB(adverse drift))

    RECOMMEND only when lift_lcb > 0. Favourable drift is credited at zero: harvesting an
    unconditional drift is a new directional bet, not cheaper execution of this signal."""
    measured = [r for r in rows if r.get("status") == "MEASURED"]
    cur = next((r for r in measured if r["offset_min"] == 0), None)
    if cur is None:
        return {"verdict": UNMEASURED, "why": f"offset 0 has fewer than {MIN_DAYS} days"}
    cands = [r for r in measured if r is not cur]
    cheapest = min(measured, key=lambda r: r["half_spread_R"])
    out: dict[str, Any] = {
        "current_minute": 0, "current_cost_R": cur["half_spread_R"],
        "cheapest_minute": cheapest["offset_min"], "cheapest_cost_R": cheapest["half_spread_R"],
        "gross_saving_R": round(cur["half_spread_R"] - cheapest["half_spread_R"], 6),
        "n_candidates": len(cands), "alpha_one_sided": alpha,
        "selection_correction": "bonferroni"}
    if not cands:
        out.update(verdict=KEEP, best_minute=0, lift_R_per_trade=0.0,
                   lift_ci_R=[0.0, 0.0], n_trades=cur["n_trades"])
        return out
    if not all("_drift" in r for r in measured):
        out.update(verdict=UNMEASURED, why="drift not measurable (direction unknown or thin)")
        return out
    z = _z_one_sided(alpha / len(cands))
    sgn = -1.0 if leg == "entry" else 1.0
    best: dict[str, Any] | None = None
    for r in cands:
        s_m, s_se = _mean_se(r["_saving"])
        d_m, d_se = _mean_se([-sgn * d for d in r["_drift"]])   # adverse drift, signed
        lift = s_m - max(0.0, d_m)
        lcb = (s_m - z * s_se) - max(0.0, d_m + z * d_se)
        ucb = (s_m + z * s_se) - max(0.0, d_m - z * d_se)
        rec = {"minute": r["offset_min"], "cost_R": r["half_spread_R"], "drift_R": r["drift_R"],
               "lift": round(lift, 6), "ci": [round(lcb, 6), round(ucb, 6)],
               "n": r["n_trades"]}
        if best is None or lcb > best["ci"][0]:
            best = rec
    assert best is not None
    out.update(best_minute=best["minute"], best_cost_R=best["cost_R"],
               drift_at_best_R=best["drift_R"], lift_R_per_trade=best["lift"],
               lift_ci_R=best["ci"], n_trades=best["n"], z_bonferroni=round(z, 4),
               edge_decay_R_at_cheapest=cheapest.get("drift_R"),
               verdict=RECOMMEND if best["ci"][0] > 0 else KEEP)
    return out


def _public(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [{k: v for k, v in r.items() if not k.startswith("_")} for r in rows]


def exit_hour(identity: dict[str, Any]) -> int | None:
    """The UTC hour the exit fills in, ONLY when the identity declares it. None otherwise."""
    raw = (identity.get("params") or {}).get("exit_hour_utc", identity.get("exit_hour_utc"))
    if not isinstance(raw, (int, str)) or isinstance(raw, bool):
        return None
    try:
        h = int(raw)
    except ValueError:
        return None
    return h if 0 <= h < 24 else None


def _profile(loaded: list[tuple[str, int, Any]], hour: int, sign: int, tick: float,
             r: float) -> tuple[str, dict[str, Any]]:
    """Finest timeframe whose offset 0 holds MIN_DAYS paired days; else the finest (thin)."""
    profs = [(tf, minute_profile(fr, st, hour, sign, tick, r)) for tf, st, fr in loaded]
    return next(((tf, p) for tf, p in profs if any(
        o["offset_min"] == 0 and o.get("status") == "MEASURED" for o in p["offsets"])),
        profs[0])


NO_INTRADAY_WHY = ("no sub-hour bars on disk (M1/M5/M15/M30): one H1 spread stamp an hour is no "
                   "minute surface. Collector: fetch_universe.INTRADAY_TIMEFRAMES (its per-symbol "
                   "coverage names the reason a timeframe was not written)")
CONTINUOUS_WHY = ("continuous selector: the placing hour is not fixed, and pricing it on an "
                  "all-hours pooled spread would credit other hours' costs to this fill")
EXIT_WHY = ("exit hour not declared in the identity (params.exit_hour_utc): the exit is not "
            "priced on an all-hours pooled spread")


def assess(root: Path | None = None) -> dict[str, Any]:
    root = root or ROOT
    sleeves = (_read(root / REGISTRY_REL).get("sleeves") or {})
    meta = _read(root / UNIVERSE_REL)
    rows: list[dict[str, Any]] = []
    by_symbol: dict[str, list[tuple[str, dict[str, Any]]]] = {}
    for name, entry in sorted(sleeves.items()):
        if isinstance(entry, dict) and entry.get("status") == "LIVE":
            ident = entry.get("identity") or {}
            by_symbol.setdefault(str(ident.get("symbol") or ""), []).append((name, ident))
    # Symbol by symbol: one symbol's frames are resident at a time and freed before the next.
    for sym in sorted(by_symbol):
        loaded = load_bars(root, sym) if sym else []
        tick = float((meta.get(sym) or {}).get("tick_size") or 0.0)
        r = r_unit(root, sym) if loaded and tick > 0 else None
        for name, ident in by_symbol[sym]:
            rows.append(_assess_sleeve(name, ident, sym, loaded, tick, r))
        del loaded
    rows.sort(key=lambda row: row["sleeve"])
    counts: dict[str, int] = {}
    for row in rows:
        counts[row["verdict"]] = counts.get(row["verdict"], 0) + 1
    return {"schema": "execution-timing-2",
            "built_at": datetime.now(UTC).isoformat(timespec="seconds"),
            "report_only": True, "min_days": MIN_DAYS,
            "n_sleeves": len(rows), "verdicts": counts,
            "measured_lift": [{"sleeve": r["sleeve"], "lift_R": r["total_lift_R_per_trade"],
                               "verdict": r["verdict"]}
                              for r in rows if r.get("total_lift_R_per_trade") is not None],
            "sleeves": rows}


def _assess_sleeve(name: str, ident: dict[str, Any], sym: str,
                   loaded: list[tuple[str, int, Any]], tick: float,
                   r: float | None) -> dict[str, Any]:
    family = str(ident.get("family") or "")
    hour = signal_hour(str(ident.get("selector") or ""))
    xhour = exit_hour(ident)
    sign = direction_sign(ident)
    row: dict[str, Any] = {"sleeve": name, "symbol": sym, "family": family,
                           "selector": ident.get("selector"), "placing_hour_utc": hour,
                           "exit_hour_utc": xhour, "slippage": UNMEASURED}
    if not loaded or r is None:
        row.update(verdict=UNMEASURED,
                   why=NO_INTRADAY_WHY if not loaded else "no tick_size or H1 range for an R unit")
        return row
    row.update(R_basis="median H1 ATR14", R_price=round(r, 8),
               cost_basis="per-hour: spreads stamped on sub-hour bars inside the fill hour only",
               drift_basis="unconditional on the placing hour; signal times not replayed")
    entry_leg: dict[str, Any]
    if family in RESTING_STOP_FAMILIES:
        entry_leg = {"verdict": NOT_SELECTABLE, "why": "resting stop: price picks the minute"}
    elif hour is None:
        entry_leg = {"verdict": UNMEASURED, "why": CONTINUOUS_WHY}
    else:
        tf, prof = _profile(loaded, hour, sign, tick, r)
        row.update(bars_tf=tf, minute_profile=_public(prof["offsets"]))
        entry_leg = choose(prof["offsets"], "entry")
    exit_leg: dict[str, Any]
    if xhour is None:
        exit_leg = {"verdict": UNMEASURED, "why": EXIT_WHY}
    else:
        etf, eprof = _profile(loaded, xhour, sign, tick, r)
        row["exit_bars_tf"] = etf
        exit_leg = choose(eprof["offsets"], "exit")
    row.update(entry=entry_leg, exit=exit_leg)
    lifts = [float(leg["lift_R_per_trade"]) for leg in (entry_leg, exit_leg)
             if leg.get("verdict") in (RECOMMEND, KEEP)
             and isinstance(leg.get("lift_R_per_trade"), (int, float))]
    row["verdict"] = (RECOMMEND if RECOMMEND in (entry_leg["verdict"], exit_leg["verdict"])
                      else KEEP if lifts else UNMEASURED)
    row["total_lift_R_per_trade"] = round(sum(lifts), 6) if lifts else None
    return row


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
