"""BAR-SPREAD Z -- the quoted spread the M1 bars already carry, scored against its own
minute-of-week history, as a pre-trigger dealer-protection signal (IDEA_QUEUE row 225).

INPUT. `desks/mt5/data/universe/<SYMBOL>_M1.parquet` (columns open, high, low, close, tick_volume,
spread, real_volume). `spread` is the bar's spread in POINTS as MT5 copy_rates reports it.

CLOCK. The bars are stamped on the BROKER clock (NY+7). The parquet index may carry a "UTC" tz
label; that label is the storage convention, not the clock, so the wall-clock values are read as
broker time and every timestamp in the report is labelled `broker (NY+7)`. Nothing here converts
to, or calls anything, UTC. Live-ledger `entry_time` rows with `timestamp_basis:
broker_deal_epoch` are on the same broker clock and join directly; a row on any other or no basis
is skipped with the reason counted.

SPREAD Z, POINT IN TIME. minute_of_week = weekday*1440 + hour*60 + minute on the broker clock. For
each bar, the baseline is that minute-of-week's STRICTLY EARLIER bars (at most `--lookback` of
them, ~2 years at 104): median m and scale s = max(IQR / 1.349, 1 point). The 1-point floor is the
field's resolution (spreads are integer points, and most minutes sit at the same value, so a raw
IQR of 0 would make every tick of widening an infinite z); the share of bars on the floor is
reported. z = (spread - m) / s. Fewer than `--min-history` earlier bars: no z (UNMEASURED, never 0).

WHAT IS JOINED.
  (a) gold_asia legs: for each historical gold_asia XAUUSD leg in the live ledger, the z of the 5
      M1 bars strictly before the trigger minute (max and mean), beside the leg's R
      (`r_multiple`). Spearman(z_pre_max, R) and mean R for z_pre_max >= 2 versus < 2 once at
      least `--min-legs` legs carry both; otherwise UNMEASURED with the count.
  (b) next-15-minute range on XAUUSD, EURUSD, USDJPY, GBPUSD: (max high - min low) over bars t+1..
      t+15 divided by close[t], in bps, only when those 15 bars are contiguous. Spearman(z, range)
      and mean range per z bucket.
  A symbol with no M1 chart, no spread column or no usable bars is UNMEASURED with the reason.

BUDGET. At most `--max-rows` bars per symbol are read (the newest), and the pass stops starting
new symbols past `--time-budget-s`; either is flagged in `budget`. Keys copied through from the
ledger are scrubbed with the repo's `login_fence.is_login_key`; only entry time, R and the z values
are copied, never deal, order or account fields.

No tape, no network, no sizing, no veto wired: REPORT ONLY.

    python desks/mt5/research/bar_spread_z.py
Writes `desks/mt5/reports/bar_spread_z.json`.

NO SCRIPT ENTRY GUARD (birth-obligation law, scripts/check_birth_obligations.py).
The hourly leg `bar_spread_z` (research/hourly_cycle.py) calls `main()`
in-process. By hand, from the repo root:
    python -c "import sys; sys.path[:0]=['desks/mt5'];
        from research import bar_spread_z as M; M.main()"
"""

from __future__ import annotations

import argparse
import json
import math
import re
import sys
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

DESK = Path(__file__).resolve().parents[1]
ROOT = DESK.parent.parent
for _p in (str(DESK), str(ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

UNIVERSE = DESK / "data" / "universe"
LEDGER = DESK / "data" / "live_ledger.jsonl"
OUT = DESK / "reports" / "bar_spread_z.json"

SCHEMA = "bar-spread-z/1"
UNMEASURED = "UNMEASURED"
CLOCK = "broker (NY+7)"
SYMBOLS = ("XAUUSD", "EURUSD", "USDJPY", "GBPUSD")
SLEEVE = "gold_asia"
SLEEVE_SYMBOL = "XAUUSD"
PRE_BARS = 5
FWD_BARS = 15
SCALE_FLOOR_POINTS = 1.0
Z_BUCKETS = ((-math.inf, 1.0, "z<1"), (1.0, 2.0, "1<=z<2"), (2.0, math.inf, "z>=2"))
HIGH_Z = 2.0
M1 = pd.Timedelta(minutes=1)
DEFAULT_MAX_ROWS = 1_200_000
DEFAULT_TIME_BUDGET_S = 180.0
MAX_LEDGER_BYTES = 50_000_000
MIN_BUCKET = 30


# ------------------------------------------------------------------------------- login scrub


def _fallback_is_login_key(key: str) -> bool:
    """Used only when `libs.ops.login_fence` is not on this tree; mirrors its key rule."""
    n = re.sub(r"[^a-z0-9]", "", str(key).lower())
    if not n or n.startswith(("requires", "require", "needs", "last", "failed", "allow", "auto",
                              "sso", "first", "prev", "next")):
        return False
    return n in {"account", "accountnumber", "accountno", "accountnum", "accountid",
                 "accountlogin", "login", "loginid", "loginno", "loginnumber"} or n.endswith(
        ("login", "loginid"))


try:  # the repo's fence, when this tree carries it
    from libs.ops.login_fence import is_login_key  # type: ignore[import-not-found]

    LOGIN_FENCE_SOURCE = "libs.ops.login_fence.is_login_key"
except ImportError:  # pragma: no cover - depends on the tree
    is_login_key = _fallback_is_login_key
    LOGIN_FENCE_SOURCE = "fallback (libs.ops.login_fence absent on this tree)"


def scrub(obj: Any) -> Any:
    if isinstance(obj, dict):
        return {k: scrub(v) for k, v in obj.items() if not is_login_key(str(k))}
    if isinstance(obj, list):
        return [scrub(v) for v in obj]
    return obj


def _ts(t: pd.Timestamp) -> str:
    """A broker-clock timestamp, with no zone suffix (it is not UTC)."""
    return t.strftime("%Y-%m-%dT%H:%M")


def _f(x: Any, nd: int = 4) -> Any:
    if x is None:
        return UNMEASURED
    try:
        v = float(x)
    except (TypeError, ValueError):
        return UNMEASURED
    return round(v, nd) if math.isfinite(v) else UNMEASURED


# ----------------------------------------------------------------------------------- loading


def load_bars(path: Path, max_rows: int) -> tuple[pd.DataFrame | None, str | None, bool]:
    """(bars on a naive broker-clock index, reason, truncated)."""
    if not path.exists():
        return None, f"{path.name} absent", False
    try:
        frame = pd.read_parquet(path)
    except Exception as exc:  # any unreadable parquet is UNMEASURED
        return None, f"{path.name} unreadable: {type(exc).__name__}", False
    for col in ("time", "timestamp"):
        if col in frame.columns:
            frame = frame.set_index(col)
    try:
        idx = pd.DatetimeIndex(frame.index)
    except (TypeError, ValueError):
        return None, f"{path.name} has no datetime index", False
    if idx.tz is not None:
        # the stored tz label is a storage convention; the wall-clock values are broker time
        idx = idx.tz_convert("UTC").tz_localize(None)
    frame.index = idx
    need = {"high", "low", "close", "spread"}
    missing = sorted(need - set(frame.columns))
    if missing:
        return None, f"{path.name} lacks column(s) {missing}", False
    frame = frame[sorted(need)]
    frame = frame[~frame.index.duplicated(keep="last")].sort_index()
    frame = frame[np.isfinite(frame["spread"].astype(float))]
    if frame.empty:
        return None, f"{path.name} has no usable bars", False
    truncated = len(frame) > max_rows
    if truncated:
        frame = frame.iloc[-max_rows:]
    return frame, None, truncated


# ------------------------------------------------------------------------------------ spread z


def minute_of_week(idx: pd.DatetimeIndex) -> np.ndarray:
    return (idx.dayofweek * 1440 + idx.hour * 60 + idx.minute).to_numpy()


def spread_z(bars: pd.DataFrame, lookback: int, min_history: int) -> pd.DataFrame:
    """Adds mow, base_median, base_scale, floored, z. Baseline = strictly earlier same-mow bars."""
    out = bars.copy()
    out["spread"] = out["spread"].astype(float)
    out["mow"] = minute_of_week(out.index)
    g = out.groupby("mow", sort=False)["spread"]
    prior = g.shift(1)
    pg = prior.groupby(out["mow"], sort=False)
    roll = {"min_periods": min_history}
    med = pg.transform(lambda s: s.rolling(lookback, **roll).median())
    q75 = pg.transform(lambda s: s.rolling(lookback, **roll).quantile(0.75))
    q25 = pg.transform(lambda s: s.rolling(lookback, **roll).quantile(0.25))
    raw = (q75 - q25) / 1.349
    out["base_median"] = med
    out["floored"] = raw < SCALE_FLOOR_POINTS
    out["base_scale"] = raw.clip(lower=SCALE_FLOOR_POINTS)
    out["z"] = (out["spread"] - med) / out["base_scale"]
    out.loc[med.isna(), ["base_scale", "z"]] = np.nan
    return out


def forward_range_bps(bars: pd.DataFrame, n: int = FWD_BARS) -> pd.Series:
    """(max high - min low) over bars t+1..t+n / close[t] in bps; NaN unless they are contiguous."""
    hi = bars["high"].astype(float).rolling(n).max().shift(-n)
    lo = bars["low"].astype(float).rolling(n).min().shift(-n)
    pos = pd.Series(np.arange(len(bars)), index=bars.index)
    ts = pd.Series(bars.index, index=bars.index)
    contiguous = (ts.shift(-n) - ts) == n * M1
    rng = (hi - lo) / bars["close"].astype(float) * 1e4
    rng[~contiguous | (pos + n >= len(bars))] = np.nan
    return rng


def spearman(x: pd.Series, y: pd.Series) -> float | None:
    ok = x.notna() & y.notna()
    if ok.sum() < 3:
        return None
    rx, ry = x[ok].rank(), y[ok].rank()
    if rx.std() == 0 or ry.std() == 0:
        return None
    return float(np.corrcoef(rx, ry)[0, 1])


# ------------------------------------------------------------------------------------ reports


def symbol_report(sym: str, bars: pd.DataFrame | None, reason: str | None, truncated: bool,
                  lookback: int, min_history: int) -> tuple[dict[str, Any], pd.DataFrame | None]:
    if bars is None:
        return {"symbol": sym, "status": UNMEASURED, "reason": reason}, None
    scored = spread_z(bars, lookback, min_history)
    scored["fwd_range_bps"] = forward_range_bps(bars)
    z = scored["z"]
    rep: dict[str, Any] = {
        "symbol": sym, "clock": CLOCK,
        "first_bar_broker": _ts(bars.index[0]), "last_bar_broker": _ts(bars.index[-1]),
        "n_bars": len(bars), "rows_truncated_to_budget": truncated,
        "n_z": int(z.notna().sum()),
        "scale_floor_share": _f(scored.loc[z.notna(), "floored"].mean()) if z.notna().any()
        else UNMEASURED,
        "spread_points_median": _f(bars["spread"].median(), 2),
    }
    if not z.notna().any():
        rep.update({"status": UNMEASURED,
                    "reason": f"no minute-of-week has {min_history} earlier bars yet",
                    "next15_range": {"status": UNMEASURED, "reason": "no z"}})
        return rep, scored
    rep["status"] = "MEASURED"
    both = z.notna() & scored["fwd_range_bps"].notna()
    rho = spearman(z[both], scored.loc[both, "fwd_range_bps"])
    buckets = {}
    for lo, hi, name in Z_BUCKETS:
        sel = both & (z >= lo) & (z < hi)
        n = int(sel.sum())
        buckets[name] = {"n": n, "mean_range_bps": _f(scored.loc[sel, "fwd_range_bps"].mean(), 3)
                         if n >= MIN_BUCKET else UNMEASURED}
    rep["next15_range"] = {
        "status": "MEASURED" if rho is not None else UNMEASURED,
        "n_pairs": int(both.sum()),
        "spearman_z_vs_range": _f(rho),
        "by_z_bucket": buckets,
        "min_bucket": MIN_BUCKET,
    }
    if rho is None:
        rep["next15_range"]["reason"] = "fewer than 3 (z, range) pairs or no rank variation"
    return rep, scored


def load_ledger_legs(path: Path) -> tuple[list[dict[str, Any]] | None, str | None,
                                          dict[str, int]]:
    """gold_asia XAUUSD legs as {entry_broker, r}; (None, reason) when the ledger is unusable."""
    skipped = {"no_entry_time": 0, "clock_not_broker_deal_epoch": 0, "r_unusable": 0,
               "unparseable": 0}
    if not path.exists():
        return None, "live ledger absent", skipped
    try:
        if path.stat().st_size > MAX_LEDGER_BYTES:
            return None, f"live ledger over the {MAX_LEDGER_BYTES} byte budget", skipped
        try:
            from libs.ops.live_ledger_view import ledger_path

            text = ledger_path(path).read_text(encoding="utf-8")
        except ImportError:
            text = path.read_text(encoding="utf-8")
    except Exception as exc:  # unreadable/uncorrectable: UNMEASURED
        return None, f"live ledger unreadable: {type(exc).__name__}", skipped
    legs: list[dict[str, Any]] = []
    for line in text.splitlines():
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            skipped["unparseable"] += 1
            continue
        if not isinstance(row, dict) or row.get("sleeve") != SLEEVE:
            continue
        if str(row.get("symbol") or "").upper() != SLEEVE_SYMBOL:
            continue
        et = row.get("entry_time")
        if not et:
            skipped["no_entry_time"] += 1
            continue
        if row.get("timestamp_basis") != "broker_deal_epoch":
            skipped["clock_not_broker_deal_epoch"] += 1
            continue
        r = row.get("r_multiple")
        if row.get("r_unreconstructible") or isinstance(r, bool) or not isinstance(
                r, int | float) or not math.isfinite(r):
            skipped["r_unusable"] += 1
            continue
        try:
            t = pd.Timestamp(str(et))
        except (ValueError, TypeError):
            skipped["unparseable"] += 1
            continue
        if t.tzinfo is not None:  # broker_deal_epoch: the wall clock is broker time
            t = t.tz_convert("UTC").tz_localize(None)
        legs.append({"entry_broker": t, "r": float(r)})
    return legs, None, skipped


def legs_report(legs: list[dict[str, Any]] | None, reason: str | None, skipped: dict[str, int],
                scored: pd.DataFrame | None, min_legs: int) -> dict[str, Any]:
    rep: dict[str, Any] = {"sleeve": SLEEVE, "symbol": SLEEVE_SYMBOL, "clock": CLOCK,
                           "pre_window_bars": PRE_BARS, "skipped": skipped}
    if legs is None:
        rep.update({"status": UNMEASURED, "reason": reason})
        return rep
    rep["n_legs"] = len(legs)
    if scored is None:
        rep.update({"status": UNMEASURED, "reason": f"no scored {SLEEVE_SYMBOL} M1 bars"})
        return rep
    z = scored["z"]
    rows = []
    for leg in sorted(legs, key=lambda d: d["entry_broker"]):
        trig = leg["entry_broker"].floor("min")
        win = z[(z.index >= trig - PRE_BARS * M1) & (z.index < trig)]
        zz = win.dropna()
        row = {"entry_broker": _ts(leg["entry_broker"]), "r": round(leg["r"], 4)}
        if zz.empty:
            why = ("trigger outside the held bars" if (trig < z.index[0] or trig > z.index[-1]
                                                      + M1) else "no z in the 5 bars before")
            row.update({"z_pre_max": UNMEASURED, "z_pre_mean": UNMEASURED, "reason": why})
        else:
            row.update({"z_pre_max": round(float(zz.max()), 4),
                        "z_pre_mean": round(float(zz.mean()), 4), "n_pre_bars": len(zz)})
        rows.append(row)
    rep["legs"] = rows
    joined = [r for r in rows if r["z_pre_max"] != UNMEASURED]
    rep["n_joined"] = len(joined)
    if len(joined) < min_legs:
        rep.update({"status": UNMEASURED,
                    "reason": f"{len(joined)} leg(s) joined to a pre-trigger z, need {min_legs}",
                    "spearman_zpre_vs_r": UNMEASURED})
        return rep
    zs = pd.Series([r["z_pre_max"] for r in joined], dtype=float)
    rs = pd.Series([r["r"] for r in joined], dtype=float)
    hi = rs[zs >= HIGH_Z]
    lo = rs[zs < HIGH_Z]
    rep.update({
        "status": "MEASURED",
        "spearman_zpre_vs_r": _f(spearman(zs, rs)),
        "mean_r_high_z": _f(hi.mean()) if len(hi) else UNMEASURED,
        "n_high_z": len(hi),
        "mean_r_low_z": _f(lo.mean()) if len(lo) else UNMEASURED,
        "n_low_z": len(lo),
        "high_z_threshold": HIGH_Z,
    })
    return rep


def build(universe: Path, ledger: Path, *, symbols: tuple[str, ...] = SYMBOLS,
          lookback: int = 104, min_history: int = 4, min_legs: int = 10,
          max_rows: int = DEFAULT_MAX_ROWS, time_budget_s: float = DEFAULT_TIME_BUDGET_S,
          now: datetime | None = None) -> dict[str, Any]:
    t0 = time.monotonic()
    doc: dict[str, Any] = {
        "schema": SCHEMA, "idea_row": 225, "report_only": True, "veto_wired": False,
        "generated_at_utc": (now or datetime.now(UTC)).isoformat(timespec="seconds"),
        "bar_clock": CLOCK,
        "bar_clock_note": "bar and leg timestamps are broker wall-clock (NY+7), not UTC",
        "login_fence": LOGIN_FENCE_SOURCE,
        "params": {"lookback_same_minute_bars": lookback, "min_history": min_history,
                   "scale_floor_points": SCALE_FLOOR_POINTS, "pre_bars": PRE_BARS,
                   "fwd_bars": FWD_BARS, "min_legs": min_legs},
        "budget": {"max_rows_per_symbol": max_rows, "time_budget_s": time_budget_s,
                   "exceeded": False, "rows_truncated": []},
    }
    symbols_out: dict[str, Any] = {}
    scored_gold: pd.DataFrame | None = None
    for sym in symbols:
        if time.monotonic() - t0 > time_budget_s:
            doc["budget"]["exceeded"] = True
            symbols_out[sym] = {"symbol": sym, "status": UNMEASURED,
                                "reason": "time budget spent before this symbol"}
            continue
        bars, reason, truncated = load_bars(universe / f"{sym}_M1.parquet", max_rows)
        if truncated:
            doc["budget"]["rows_truncated"].append(sym)
        rep, scored = symbol_report(sym, bars, reason, truncated, lookback, min_history)
        symbols_out[sym] = rep
        if sym == SLEEVE_SYMBOL:
            scored_gold = scored
    doc["symbols"] = symbols_out
    legs, lreason, skipped = load_ledger_legs(ledger)
    doc["gold_asia_pre_trigger"] = legs_report(legs, lreason, skipped, scored_gold, min_legs)
    doc["status"] = ("MEASURED" if all(s.get("status") == "MEASURED"
                                       for s in symbols_out.values())
                     and doc["gold_asia_pre_trigger"]["status"] == "MEASURED"
                     else "PARTIAL" if any(s.get("status") == "MEASURED"
                                           for s in symbols_out.values())
                     else UNMEASURED)
    doc["elapsed_s"] = round(time.monotonic() - t0, 3)
    return scrub(doc)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=(__doc__ or "").split("\n")[0])
    ap.add_argument("--universe", type=Path, default=UNIVERSE)
    ap.add_argument("--ledger", type=Path, default=LEDGER)
    ap.add_argument("--lookback", type=int, default=104)
    ap.add_argument("--min-history", type=int, default=4)
    ap.add_argument("--min-legs", type=int, default=10)
    ap.add_argument("--max-rows", type=int, default=DEFAULT_MAX_ROWS)
    ap.add_argument("--time-budget-s", type=float, default=DEFAULT_TIME_BUDGET_S)
    ap.add_argument("--out", type=Path, default=OUT)
    a = ap.parse_args(argv)
    if a.lookback < 1 or a.min_history < 1 or a.min_history > a.lookback or a.max_rows < 1:
        raise SystemExit("need 1 <= min-history <= lookback and max-rows >= 1")
    doc = build(a.universe, a.ledger, lookback=a.lookback, min_history=a.min_history,
                min_legs=a.min_legs, max_rows=a.max_rows, time_budget_s=a.time_budget_s)
    a.out.parent.mkdir(parents=True, exist_ok=True)
    tmp = a.out.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(doc, indent=1, default=str), encoding="utf-8")
    tmp.replace(a.out)
    print(f"bar_spread_z: {doc['status']} -> {a.out}")
    return 0

