"""POINT-IN-TIME, PER-SYMBOL SERIES BEHIND FOUR INTERACTION CONDITIONERS.

WHAT WAS REFUSED. `transformation_miners.mine_interaction` crosses a mechanism with a second
information axis ("is it stronger when that second participant is also pressed?"). On a 1,000-
discovery sample of the live intake 177 such children were refused `modifier_unavailable` for
`conditioner=positioning|event|carry|cross_asset`, because nothing told `cell_modifiers` what
"pressed" means for THAT symbol on THAT date. Every input already exists on the desk:

  positioning  `data/axes/cot.json` (axis_ingest, CFTC legacy, 22 MT5 symbols, publication lag
               applied). Pressed = net non-commercial share of open interest in the outer tails
               of its trailing 156-week window -- `family_cot_positioning`'s own `lookback_weeks`
               and `extreme_pct`, read off its signature so the two can never drift apart.
  carry        `data/axes/bis.json` (axis_ingest, BIS policy rates -> the pair's differential;
               the rate HISTORY, never the `carry_state.json` snapshot). Pressed = the absolute
               differential at or above `family_carry`'s own `min_edge_bp_per_day`, annualised.
  event        `data/event_calendar.json` (scripts/build_event_calendar.py, FOMC decision days
               from federalreserve.gov). Pressed = the decision day or the day after. The file
               covers what it covers: outside its span there are NO rows, so a bar there keeps
               nothing (an unrecorded year is not an event-free year, WS-005), and a symbol with
               no USD exposure has no series at all -- UNMEASURED, refused by name.
  cross_asset  the desk's own H1 bars for the three residual factors (`RESIDUAL_FACTOR_SYMBOLS`:
               USDX, XAUUSD, US500). USDX falls back to an equal-weight basket of the dollar
               majors when its bars are absent (named in the report). Pressed = the factor's
               20-day log move at |z| >= 1 against its own trailing year.

THE PIT RULE. Every row carries `knowable_at` (when the desk could have had it) and `stale_after`
(`knowable_at` + the series' cadence + `cell_modifiers.STATE_MAX_AGE`, the same four days the
free-state conditioners use). A signal reads the last row known at its bar and keeps nothing once
that row is stale -- the forward clock never trades on a series that stopped arriving.

    python desks/mt5/research/pit_conditioners.py          # build + publish
"""
from __future__ import annotations

import inspect
import json
import math
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

DESK = Path(__file__).resolve().parents[1]
ROOT = DESK.parents[1]
for _p in (str(DESK), str(DESK / "research"), str(ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

from mt5desk import cell_modifiers as cm  # noqa: E402

AXES_DIR = DESK / "data" / "axes"
UNIVERSE_DIR = DESK / "data" / "universe"
EVENT_CALENDAR = ROOT / "data" / "event_calendar.json"
REPORT = DESK / "reports" / "PIT_CONDITIONERS.json"

#: Rows before this date are not needed by any replay the desk runs (bars start 2018) and would
#: only bloat the file: the BIS history goes back to 1954.
SINCE = pd.Timestamp("2015-01-01", tz="UTC")
CROSS_MOVE_DAYS = 20
CROSS_Z_WINDOW = 252
CROSS_Z = 1.0
#: The dollar basket used when USDX bars are absent: (symbol, +1 when the price IS dollars per
#: unit of the other currency, so a dollar rally lowers it).
USD_BASKET = (("EURUSD", -1), ("GBPUSD", -1), ("AUDUSD", -1), ("NZDUSD", -1),
              ("USDJPY", 1), ("USDCAD", 1), ("USDCHF", 1))
MIN_BASKET = 4


def _default(fn: Any, name: str) -> float:
    return float(inspect.signature(fn).parameters[name].default)


def _rows(axis: str, key: str, frame: pd.DataFrame, cadence_days: float) -> pd.DataFrame:
    """Normalise one key's frame (index knowable_at, columns value/pressed) into output rows."""
    out = frame.copy()
    out.index = pd.DatetimeIndex(out.index)
    out = out[out.index >= SINCE]
    return pd.DataFrame({
        "axis": axis, "key": key, "knowable_at": out.index,
        "stale_after": out.index + pd.Timedelta(days=cadence_days) + cm.STATE_MAX_AGE,
        "value": out["value"].astype(float).to_numpy(),
        "pressed": out["pressed"].astype(bool).to_numpy()})


def _axis_rows(name: str) -> list[dict[str, Any]]:
    try:
        doc = json.loads((AXES_DIR / f"{name}.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []
    return [r for r in doc.get("rows") or [] if isinstance(r, dict)]


def positioning() -> tuple[list[pd.DataFrame], dict[str, Any]]:
    from mt5desk.families_orthogonal import family_cot_positioning

    weeks = int(_default(family_cot_positioning, "lookback_weeks"))
    ext = _default(family_cot_positioning, "extreme_pct")
    rows = _axis_rows("cot")
    if not rows:
        return [], {"state": "UNMEASURED", "why": "data/axes/cot.json absent or empty"}
    df = pd.DataFrame(rows)
    out = []
    for sym, g in df.groupby("symbol"):
        s = (g.assign(t=pd.to_datetime(g["knowable_at"], utc=True))
             .drop_duplicates("t").set_index("t")["net_pct_oi"].astype(float).sort_index())
        # Rank of today's reading inside its own trailing window, today included: PIT.
        pct = s.rolling(weeks, min_periods=52).apply(
            lambda w: float((w <= w[-1]).mean()), raw=True)
        frame = pd.DataFrame({"value": pct, "pressed": (pct >= ext) | (pct <= 1.0 - ext)})
        frame = frame[pct.notna()]
        if len(frame):
            out.append(_rows("positioning", str(sym).upper(), frame, 7.0)
                       .assign(source="cftc_cot_legacy"))
    return out, {"state": "OK" if out else "EMPTY", "source": "data/axes/cot.json",
                 "rule": f"trailing {weeks}w percentile >= {ext} or <= {1 - ext:.2f}",
                 "cadence_days": 7}


#: The broker's own published overnight financing, one vintage per capture: the `broker_swaps`
#: seat writes `swap_table` rows (`swap_long`, `swap_short`, `found_at`) read straight off the
#: venue terminal. That is the carry the desk actually PAYS, and it exists for every symbol the
#: venue lists -- metals and indices included, which no policy-rate pair can speak for.
SWAP_DIR = DESK / "data" / "intelligence" / "broker_swaps"
#: Unit metadata for those numerals: `swap_mode` per symbol (`carry_state.json`, read from the
#: contract-terms tape) and `tick_size` (`universe.json`). A contract property, not a market
#: observation, so its own vintage does not gate the swap rows' knowledge time.
CARRY_STATE = DESK / "data" / "carry_state.json"
UNIVERSE_JSON = UNIVERSE_DIR / "universe.json"
SWAP_MODE_POINTS = 1
SWAP_MODE_INTEREST_CURRENT = 5


def _swap_rows() -> list[dict[str, Any]]:
    import gzip

    out: list[dict[str, Any]] = []
    if not SWAP_DIR.exists():
        return out
    for f in sorted(SWAP_DIR.iterdir()):
        try:
            if f.name.endswith(".jsonl.gz"):
                with gzip.open(f, "rt", encoding="utf-8") as fh:
                    got = [json.loads(line) for line in fh if line.strip()]
            elif f.suffix == ".json":
                doc = json.loads(f.read_text(encoding="utf-8"))
                got = doc if isinstance(doc, list) else list(doc.get("discoveries") or [])
            else:
                continue
        except (OSError, ValueError, EOFError):
            continue
        out += [r for r in got if isinstance(r, dict) and r.get("kind") == "swap_table"]
    return out


def _json(path: Path) -> dict[str, Any]:
    try:
        doc = json.loads(path.read_text(encoding="utf-8"))
        return doc if isinstance(doc, dict) else {}
    except (OSError, ValueError):
        return {}


def swap_carry(missing: set[str] | None = None) -> tuple[list[pd.DataFrame], dict[str, Any]]:
    """The broker-swap-implied carry, % p.a. of notional, (long - short) -- the same differential
    `family_carry` trades on -- for every symbol in `missing` (None = all). Each row's
    `knowable_at` is the capture's own `found_at`. A symbol whose unit cannot be established, or
    whose POINTS swap has no price to scale against, is named in `unmeasured`, never guessed."""
    modes = {k.upper(): v.get("swap_mode") for k, v in
             (_json(CARRY_STATE).get("symbols") or {}).items() if isinstance(v, dict)}
    uni = _json(UNIVERSE_JSON)
    by_sym: dict[str, list[tuple[pd.Timestamp, float, float]]] = {}
    for r in _swap_rows():
        syms = r.get("symbols") or []
        if len(syms) != 1:
            continue
        sym = str(syms[0]).upper()
        if missing is not None and sym not in missing:
            continue
        try:
            t = pd.Timestamp(str(r["found_at"]))
            lo, sh = float(r["swap_long"]), float(r["swap_short"])
        except (KeyError, TypeError, ValueError):
            continue
        t = t.tz_localize("UTC") if t.tzinfo is None else t.tz_convert("UTC")
        by_sym.setdefault(sym, []).append((t, lo, sh))
    out: list[pd.DataFrame] = []
    unmeasured: dict[str, str] = {}
    for sym, obs in sorted(by_sym.items()):
        frame = (pd.DataFrame(obs, columns=["t", "long", "short"])
                 .drop_duplicates("t", keep="last").set_index("t").sort_index())
        mode = modes.get(sym)
        diff = frame["long"] - frame["short"]
        if mode == SWAP_MODE_INTEREST_CURRENT:
            value = diff                                     # already annual percent
        elif mode == SWAP_MODE_POINTS:
            tick = float((uni.get(sym) or {}).get("tick_size") or 0.0)
            close = _daily_close(sym)
            if tick <= 0 or close is None or close.empty:
                unmeasured[sym] = ("POINTS swap with no tick_size or no bars to price the "
                                   "notional")
                continue
            # The last close KNOWN at the capture: a day's close is stamped at the day's end.
            px = close.reindex(close.index.union(frame.index)).ffill().reindex(frame.index)
            value = diff * tick / px * 365.0 * 100.0
        else:
            unmeasured[sym] = f"swap_mode {mode!r}: unit not established"
            continue
        value = value.dropna()
        if value.empty:
            unmeasured[sym] = "no capture after the first priced close"
            continue
        out.append(pd.DataFrame({"value": value}))
        out[-1].attrs["key"] = sym
    return out, {"unmeasured": unmeasured}


def carry() -> tuple[list[pd.DataFrame], dict[str, Any]]:
    from mt5desk.families_orthogonal import family_carry

    floor = _default(family_carry, "min_edge_bp_per_day") * 365.0 / 100.0   # bp/day -> % p.a.
    out = []
    rows = [r for r in _axis_rows("bis") if len(str(r.get("knowable_at") or "")) == 10]
    if rows:
        df = pd.DataFrame(rows)
        for sym, g in df.groupby("symbol"):
            s = (g.assign(t=pd.to_datetime(g["knowable_at"], utc=True))
                 .drop_duplicates("t").set_index("t")["carry_differential"].astype(float)
                 .sort_index())
            frame = pd.DataFrame({"value": s, "pressed": s.abs() >= floor})
            if len(frame):
                out.append(_rows("carry", str(sym).upper(), frame, 1.0)
                           .assign(source="bis_policy_rates"))
    have = {str(f["key"].iloc[0]) for f in out}
    # EVERY SYMBOL THE RATE DIFFERENTIAL CANNOT SPEAK FOR -- gold, silver, indices, energy --
    # reads the broker's own swap: the financing the desk is actually charged or paid.
    swaps, smeta = swap_carry(None)
    n_swap = 0
    for f in swaps:
        key = f.attrs["key"]
        if key in have:
            continue
        frame = pd.DataFrame({"value": f["value"], "pressed": f["value"].abs() >= floor})
        out.append(_rows("carry", key, frame, 1.0).assign(source="broker_swap"))
        n_swap += 1
    if not out:
        return [], {"state": "UNMEASURED", "unmeasured": smeta["unmeasured"],
                    "why": "no BIS pair and no priceable broker swap capture is on disk"}
    return out, {"state": "OK",
                 "source": "data/axes/bis.json, then data/intelligence/broker_swaps",
                 "rule": f"|carry| >= {floor:.3f}% p.a. (family_carry.min_edge_bp_per_day, "
                         "annualised): the policy-rate differential where BIS has the pair, "
                         "else the broker's (swap_long - swap_short) as % p.a. of notional",
                 "n_keys_bis": len(have), "n_keys_broker_swap": n_swap,
                 "unmeasured": {**smeta["unmeasured"],
                                "_fallback": ("no public gold lease / forward series is on the "
                                              "desk, so a symbol with neither a BIS pair nor a "
                                              "swap capture stays UNMEASURED")},
                 "cadence_days": 1}


def event() -> tuple[list[pd.DataFrame], dict[str, Any]]:
    try:
        doc = json.loads(EVENT_CALENDAR.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return [], {"state": "UNMEASURED", "why": "data/event_calendar.json absent"}
    days = sorted({pd.Timestamp(e["utc"]).tz_convert("UTC").normalize()
                   for e in doc.get("events") or []
                   if isinstance(e, dict) and e.get("utc") and e.get("impact") == "high"})
    if not days:
        return [], {"state": "UNMEASURED", "why": "the calendar lists no high-impact event"}
    end = pd.Timestamp(str(doc.get("valid_through") or days[-1].date()), tz="UTC")
    span = pd.date_range(days[0], max(end, days[-1]), freq="D", tz="UTC")
    hot = set(days) | {d + pd.Timedelta(days=1) for d in days}
    frame = pd.DataFrame({"value": [1.0 if d in hot else 0.0 for d in span],
                          "pressed": [d in hot for d in span]}, index=span)
    rows = _rows("event", "USD", frame, 1.0).assign(source="fomc_calendar")
    # The calendar is a schedule, not a publication: past its declared end nothing is known.
    rows["stale_after"] = rows["stale_after"].clip(upper=span[-1] + pd.Timedelta(days=1))
    return [rows], {"state": "OK", "source": "data/event_calendar.json",
                    "rule": "FOMC decision day or the day after",
                    "covered": [str(span[0].date()), str(span[-1].date())],
                    "keys": ["USD"],
                    "unmeasured": ("every non-USD key: no calendar of another central bank or "
                                   "release is on the desk (CPI/NFP are pending_sources there)")}


def _daily_close(symbol: str) -> pd.Series | None:
    p = UNIVERSE_DIR / f"{symbol}_H1.parquet"
    if not p.exists():
        return None
    try:
        bars = pd.read_parquet(p, columns=["close"])
    except Exception:
        return None
    idx = pd.DatetimeIndex(bars.index)
    bars.index = idx.tz_localize("UTC") if idx.tz is None else idx.tz_convert("UTC")
    close = bars["close"].astype(float).sort_index().resample("1D").last().dropna()
    # A day's last close is known when the day ends.
    close.index = close.index + pd.Timedelta(days=1)
    return close


def _factor_log_level(factor: str) -> tuple[pd.Series | None, str]:
    sym = cm.RESIDUAL_FACTOR_SYMBOLS.get(factor, "")
    close = _daily_close(sym) if sym else None
    if close is not None and len(close) > CROSS_Z_WINDOW:
        return np.log(close), f"{sym}_H1"
    if factor != "usd":
        return None, f"{sym}_H1 absent"
    legs = []
    for s, sign in USD_BASKET:
        c = _daily_close(s)
        if c is not None:
            legs.append(sign * np.log(c).diff())
    if len(legs) < MIN_BASKET:
        return None, f"{sym}_H1 absent and only {len(legs)} basket legs on disk"
    ret = pd.concat(legs, axis=1, sort=True).mean(axis=1, skipna=False).dropna()
    return ret.cumsum(), f"equal-weight dollar basket of {len(legs)} majors ({sym}_H1 absent)"


def cross_asset() -> tuple[list[pd.DataFrame], dict[str, Any]]:
    out, sources = [], {}
    for factor in sorted(cm.RESIDUAL_FACTOR_SYMBOLS):
        lvl, src = _factor_log_level(factor)
        sources[factor] = src
        if lvl is None:
            continue
        move = lvl.diff(CROSS_MOVE_DAYS)
        mu = move.rolling(CROSS_Z_WINDOW, min_periods=CROSS_Z_WINDOW // 2).mean()
        sd = move.rolling(CROSS_Z_WINDOW, min_periods=CROSS_Z_WINDOW // 2).std()
        z = ((move - mu) / sd.replace(0.0, np.nan)).dropna()
        frame = pd.DataFrame({"value": z, "pressed": z.abs() >= CROSS_Z})
        if len(frame):
            out.append(_rows("cross_asset", factor, frame, 1.0).assign(source=src))
    return out, {"state": "OK" if out else "UNMEASURED", "sources": sources,
                 "rule": f"factor {CROSS_MOVE_DAYS}d log move |z| >= {CROSS_Z} vs trailing "
                         f"{CROSS_Z_WINDOW}d", "cadence_days": 1}


BUILDERS = {"positioning": positioning, "carry": carry, "event": event,
            "cross_asset": cross_asset}


def build() -> tuple[pd.DataFrame, dict[str, Any]]:
    frames, axes = [], {}
    for axis, fn in BUILDERS.items():
        try:
            got, meta = fn()
        except Exception as exc:     # one source's failure is that axis's UNMEASURED, not ours
            got, meta = [], {"state": "UNMEASURED", "why": f"{type(exc).__name__}: {exc}"}
        frames += got
        keys = sorted({str(f["key"].iloc[0]) for f in got if len(f)})
        last = max((f["knowable_at"].max() for f in got if len(f)), default=None)
        axes[axis] = {**meta, "keys": keys, "n_keys": len(keys),
                      "n_rows": int(sum(len(f) for f in got)),
                      "last_knowable_at": None if last is None else str(last)}
    cols = ["axis", "key", "knowable_at", "stale_after", "value", "pressed", "source"]
    frame = (pd.concat(frames, ignore_index=True) if frames else pd.DataFrame(columns=cols))
    return frame, axes


def main(argv: list[str] | None = None) -> int:
    frame, axes = build()
    path = cm.PIT_FILE
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    frame.to_parquet(tmp, index=False)
    tmp.replace(path)
    doc = {"at": datetime.now(tz=UTC).isoformat(timespec="seconds"),
           "file": str(path.relative_to(DESK)), "n_rows": int(len(frame)), "axes": axes,
           "max_age_days": cm.STATE_MAX_AGE / pd.Timedelta(days=1),
           "rule": ("a row is used from knowable_at until stale_after (cadence + the state "
                    "freshness window); a key absent here is refused UNMEASURED by name")}
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text(json.dumps(doc, indent=1, default=str), encoding="utf-8")
    for axis, meta in axes.items():
        print(f"{axis:<12} {meta['state']:<10} keys={meta['n_keys']:<3} rows={meta['n_rows']:<7} "
              f"last={meta['last_knowable_at']}")
    return 0 if len(frame) and not math.isnan(float(len(frame))) else 1


if __name__ == "__main__":
    sys.exit(main())
