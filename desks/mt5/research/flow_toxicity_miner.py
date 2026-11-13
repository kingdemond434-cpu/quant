"""Tick-tape flow, toxicity, impact and spread-regime SERIES, and the judge cells they condition.

WHAT WAS MISSING (desks/mt5/docs/CAPABILITY_AUDIT.md, "Microstructure features (OBI, book,
toxicity): MISSING -- queued (Fincept)"). The desk records a quote tape for ~243 instruments on the
box and reads it three ways: the cost side (`recorders/tape_features.py`, `mt5desk/microstructure`),
a sign-of-mid flow and a mean spread for two families (`orthogonal_sweep._tape_series`), and the
bar-level spread surfaces (`microstructure_miner`). Nothing measured TOXICITY (how informed the
pressing looks), IMPACT (what a unit of pressing buys) or the tick test's signed flow, and the two
tape families have a structural defect this organ also answers: their input is re-read from the
LAST 30 DAY FILES on every call, so a cell's conditioning variable never spans more than a month
and `JUDGE_COVERAGE.json` reads `orderflow_imbalance` 44,178 mined / 0 judged and
`liquidity_regime` 18,964 / 0 -- "never_fires" and "short_history" at the judge's history cut.

WHAT THIS ORGAN DOES, EVERY HOUR ON THE BOX THAT HOLDS THE TAPE (hourly_cycle leg `flow_toxicity`):

  1. ACCUMULATES. For every tape symbol it computes the additive per-bar aggregates of
     `mt5desk/flow_toxicity.py` for each day file it has not yet seen (or whose size changed),
     merges them into `data/lake/series/micro_<SYM>.parquet`, and re-derives the signal columns
     over the WHOLE accumulated history. The series therefore keeps growing after `archive_tape`
     ships the old day files off the box: it is a moat that compounds instead of a 30-day window.
  2. PUBLISHES THROUGH THE ONE DOOR THE JUDGE ALREADY READS. The file is the lake-series layout
     `family_exogenous_conditioner` and `family_alt_series_momentum` load by (source, signal),
     with `available_time` = bar close (UTC). So a cell needs no new family and no money-path edit:
     the sealed gauntlet rebuilds it from the same file this organ screened it on.
  3. PROPOSES CELLS. Per symbol, a small grid over the seven signals is screened with the shared
     proposer screen (`proposer_common.screen`: non-overlapping, net of the corrected round trip,
     artifact hours refused). A cell is proposed when it clears cost, reaches |t| >= 2 gross, AND
     its held-out last 30% of trades is net positive. That is a PROPOSAL filter, not a gate; the
     whole sweep's test count rides on the donation so the judge charges every trial.
  4. REFRESHES THE DEPTH PROBE. `data/tape/depth_probe.json` (2026-08-17, 22/22 NO_DEPTH) decides
     whether any book-based construction is buildable. It is re-probed weekly through
     `mt5desk/tape.py --probe` where a terminal is attached; elsewhere it is UNMEASURED, said so.

  5. MEASURES ITS OWN HOLES. Per symbol, `series_gaps` reports the start and end dates of the
     series, the gap count and the longest gap IN TRADING DAYS (a weekend on a Mon-Fri venue and
     a daily session break are not gaps), plus the trailing gap from the last bar to today; the
     report's `series_gaps` summary names the worst gap and every symbol over two trading days.
     The tape families forward-fill this input, so a stalled miner would otherwise read as a
     flat, plausible conditioner rather than a missing one. No series is UNMEASURED, never zero.

THE POINT-IN-TIME JOIN. The bar index is broker time under a UTC tzinfo (+2 winter, +3 summer);
the series is genuinely UTC. Every proposed cell carries `lag_hours = 3`, so a bar can only be
conditioned on a value whose bar had CLOSED before that bar opened, in both seasons.

LANES. Equity share CFDs are recorded and their series are written (the event lane may read them)
but `proposer_common.donate` refuses their hypothesis cells at the door, per the two-lane mandate.
The universe is the MT5/Fusion tape only; nothing here reads a crypto-exchange feed.

    python desks/mt5/research/flow_toxicity_miner.py                 # accumulate + propose
    python desks/mt5/research/flow_toxicity_miner.py --no-propose    # series only
    python desks/mt5/research/flow_toxicity_miner.py --symbol EURUSD --dry-run
"""
from __future__ import annotations

import argparse
import json
import logging
import math
import os
import subprocess
import sys
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

_DESK = Path(__file__).resolve().parents[1]
_ROOT = _DESK.parent.parent
for _p in (str(_DESK), str(_DESK / "research"), str(_ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from mt5desk import flow_toxicity as ft  # noqa: E402

#: Reports carry an exception's TYPE NAME only (Auditor MF1): free exception text can hold a URL,
#: a token or an absolute box path, and these reports are published. The full text goes to the
#: log, never into the payload.
_LOG = logging.getLogger(__name__)

SOURCE = "flow_toxicity"
#: The series prefix. `micro_<SYM>` in the lake-series directory; the DataHub contract
#: `micro.flow_bars` and the coverage audit key on it.
SERIES_PREFIX = "micro_"
TICKS = _DESK / "data" / "tape" / "ticks"
SERIES_DIR = _DESK / "data" / "lake" / "series"
STATE = SERIES_DIR / "micro_state.json"
REPORT = _DESK / "reports" / "FLOW_TOXICITY.json"
DEPTH_PROBE = _DESK / "data" / "tape" / "depth_probe.json"
DEPTH_PROBE_MAX_AGE_D = 7.0
RULE = "1h"
#: Day files whose aggregates are always recomputed (the newest is still being appended to).
REFRESH_TAIL_DAYS = 2
#: Measured bars a symbol needs before it is screened at all.
MIN_SERIES_BARS = 200
#: The lag every proposed cell carries; see the module docstring.
LAG_HOURS = 3
#: The z window a conditioner uses on these series. Shorter than the pack default (250) because
#: the tape is young; it grows with the series and is part of the cell's identity.
Z_WINDOW = 120
THRESHOLDS = (1.5, 2.0)
SIDES = (1, -1)
TTLS = (12, 24)
MOMENTUM_LOOKBACK = 4
PROPOSE_T_GROSS = 2.0
OOS_FRACTION = 0.30


# ------------------------------------------------------------------------------- helpers
def _published_path(path: Path) -> str:
    """A path as a published report may name it: relative to the repo root, else the bare file
    name. Never an absolute box path (Auditor MF1)."""
    try:
        return path.relative_to(_ROOT).as_posix() if path.is_relative_to(_ROOT) else path.name
    except ValueError:
        return path.name


def _now() -> datetime:
    return datetime.now(tz=UTC)


def _read_json(path: Path, default: Any) -> Any:
    try:
        return json.loads(path.read_text("utf-8"))
    except (OSError, ValueError):
        return default


def _write_atomic(path: Path, text: str, *, attempts: int = 5) -> None:
    """Write via a sibling temp file. Windows refuses a replace onto a file a reader holds open, so
    it is retried with backoff and finally written in place rather than lost."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(text, "utf-8")
    for i in range(attempts):
        try:
            os.replace(tmp, path)
            return
        except PermissionError:
            time.sleep(0.2 * (2 ** i))
    path.write_text(text, "utf-8")
    tmp.unlink(missing_ok=True)


def _write_parquet(df: pd.DataFrame, path: Path, *, attempts: int = 5) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp.parquet")
    df.to_parquet(tmp)
    for i in range(attempts):
        try:
            os.replace(tmp, path)
            return
        except PermissionError:
            time.sleep(0.2 * (2 ** i))
    df.to_parquet(path)
    tmp.unlink(missing_ok=True)


def point_of(symbol: str, meta: dict) -> float | None:
    row = meta.get(symbol)
    if not isinstance(row, dict):
        return None
    for key in ("tick_size", "point"):
        v = row.get(key)
        try:
            f = float(v)
        except (TypeError, ValueError):
            continue
        if math.isfinite(f) and f > 0:
            return f
    d = row.get("digits")
    try:
        return 10.0 ** -int(d)
    except (TypeError, ValueError):
        return None


def day_files(symbol: str, root: Path) -> dict[str, list[Path]]:
    """ISO day -> every file for it. Both naming conventions (`YYYY-MM-DD`, `YYYYMMDD`) are real
    and can hold the same day (see `mt5desk.tape.day_files`); both are read and de-duplicated."""
    d = root / symbol
    out: dict[str, list[Path]] = {}
    if not d.is_dir():
        return out
    for p in d.glob("*.parquet"):
        s = p.stem
        if len(s) == 10 and s[4] == "-" and s[7] == "-":
            day = s
        elif len(s) == 8 and s.isdigit():
            day = f"{s[:4]}-{s[4:6]}-{s[6:]}"
        else:
            continue
        out.setdefault(day, []).append(p)
    return dict(sorted(out.items()))


def _read_day(paths: list[Path]) -> pd.DataFrame | None:
    frames = []
    for p in paths:
        try:
            frames.append(pd.read_parquet(p, columns=["ts", "bid", "ask"]))
        except Exception:
            continue                                                # a torn file is not fatal
    if not frames:
        return None
    return pd.concat(frames, ignore_index=True)


def _signature(paths: list[Path]) -> str:
    parts = []
    for p in sorted(paths):
        try:
            parts.append(f"{p.name}:{p.stat().st_size}")
        except OSError:
            parts.append(f"{p.name}:?")
    return "|".join(parts)


# ------------------------------------------------------------------------------- accumulate
def accumulate(symbol: str, point: float, state: dict, *, tick_root: Path,
               series_root: Path, budget_end: float | None = None) -> dict[str, Any]:
    """Fold every new or changed day file into the symbol's series. Returns its reading."""
    files = day_files(symbol, tick_root)
    sym_state = state.setdefault(symbol, {"days": {}, "bucket_ticks": None})
    seen: dict[str, str] = sym_state.setdefault("days", {})
    tail = set(list(files)[-REFRESH_TAIL_DAYS:])
    todo = [d for d, ps in files.items() if d in tail or seen.get(d) != _signature(ps)]
    path = series_root / f"{SERIES_PREFIX}{symbol}.parquet"
    old = None
    if path.exists():
        try:
            prev = pd.read_parquet(path)
            old = prev[[c for c in (*ft.AGG_COLUMNS, "mid_open", "mid_close")
                        if c in prev.columns]]
        except Exception:
            old = None
            seen.clear()
            todo = list(files)
    agg = old
    done = 0
    for day in todo:
        if budget_end is not None and time.monotonic() > budget_end:
            break
        ticks = _read_day(files[day])
        if ticks is None or ticks.empty:
            seen[day] = _signature(files[day])
            continue
        if not sym_state.get("bucket_ticks"):
            # FIXED PER SYMBOL ON FIRST SIGHT, so a bucket means the same activity on every day
            # the series holds: ticks per ACTIVE hour of the first day folded.
            hours = pd.to_datetime(ticks["ts"], utc=True, errors="coerce").dt.floor(RULE)
            per_bar = len(ticks) / max(1, int(hours.nunique()))
            sym_state["bucket_ticks"] = ft.default_bucket_ticks(per_bar)
        new = ft.bar_aggregates(ticks, point, rule=RULE,
                                bucket_ticks=int(sym_state["bucket_ticks"]))
        agg = ft.merge_aggregates(agg, new)
        seen[day] = _signature(files[day])
        done += 1
    reading: dict[str, Any] = {"symbol": symbol, "day_files": len(files), "days_folded": done,
                               "days_pending": max(0, len(todo) - done),
                               "bucket_ticks": sym_state.get("bucket_ticks")}
    if agg is None or agg.empty:
        reading["status"] = "UNMEASURED"
        reading["why"] = "no readable tick day files"
        return reading
    if done:
        frame = ft.series_frame(agg, point, rule=RULE)
        _write_parquet(frame, path)
    else:
        frame = pd.read_parquet(path)
    measured = frame["tick_intensity"].notna()
    reading.update({
        "status": "MEASURED", "series": _published_path(path),
        "bars": len(frame), "bars_measured": int(measured.sum()),
        "first_bar": str(frame.index.min()), "last_bar": str(frame.index.max()),
        "quote_imbalance_basis": "sign_only",
        "latest": {c: (None if pd.isna(v) else round(float(v), 6))
                   for c, v in frame[list(ft.SIGNAL_COLUMNS)].dropna(how="all").iloc[-1].items()}
        if measured.any() else {},
    })
    return reading


# ------------------------------------------------------------------------------- gaps
#: A hole longer than this many trading days is named in the report's summary.
GAP_ALERT_TRADING_DAYS = 2
#: Asset classes whose venue quotes every calendar day (the same rule `libs.research.bar_span`
#: declares). Every other class is closed Saturday and Sunday (UTC), and a day it is closed on is
#: never a gap.
_WEEKEND_CLASSES = frozenset({"crypto"})
_WEEKDAYS = "1111100"
_ALL_DAYS = "1111111"


def _trades_weekends(symbol: str) -> bool:
    try:
        from libs.research.bar_span import WEEKEND_TRADING_CLASSES
    except Exception:
        classes: frozenset[str] = _WEEKEND_CLASSES
    else:
        classes = frozenset(WEEKEND_TRADING_CLASSES)
    try:
        from research.universe_policy import asset_class_of
        return str(asset_class_of(symbol) or "").lower() in classes
    except Exception:
        return False                      # unknown class: the stricter weekday calendar


def series_gaps(path: Path, *, trades_weekends: bool = False,
                today: datetime | None = None) -> dict[str, Any]:
    """Every hole in one `micro_<SYM>` series, counted in TRADING DAYS.

    A bar is present when it holds at least one tick. Counting is by whole UTC dates: the gap
    between two consecutive dates that hold bars is the number of trading days strictly between
    them, so a venue's daily break and its overnight hours (inside a date that still holds bars)
    and a weekend (no trading day) are never gaps, and a public holiday is one day. The trailing
    gap is the same count from the last date to today: a stalled miner shows there, where a
    family's forward-fill would otherwise hide it. An absent, unreadable or empty series is
    UNMEASURED, never zero gaps.
    """
    out: dict[str, Any] = {"series": _published_path(path),
                           "calendar": "every_day" if trades_weekends else "mon_fri_utc"}
    if not path.exists():
        return {**out, "status": "UNMEASURED", "why": "series file absent"}
    try:
        try:
            frame = pd.read_parquet(path, columns=["n_ticks"])
        except Exception:
            frame = pd.read_parquet(path)
    except Exception as exc:
        _LOG.warning("flow_toxicity gaps %s: %r", path.name, exc)
        return {**out, "status": "UNMEASURED", "why": type(exc).__name__}
    idx = frame.index
    if "n_ticks" in frame.columns:
        idx = idx[pd.to_numeric(frame["n_ticks"], errors="coerce").fillna(0).to_numpy() > 0]
    try:
        stamps = pd.DatetimeIndex(idx)
    except Exception as exc:
        return {**out, "status": "UNMEASURED", "why": type(exc).__name__}
    stamps = stamps.tz_localize("UTC") if stamps.tz is None else stamps.tz_convert("UTC")
    days = np.unique(stamps.dropna().normalize().tz_localize(None).to_numpy()
                     .astype("datetime64[D]"))
    if days.size == 0:
        return {**out, "status": "UNMEASURED", "why": "series holds no measured bar"}
    mask = _ALL_DAYS if trades_weekends else _WEEKDAYS
    missing = (np.busday_count(days[:-1] + np.timedelta64(1, "D"), days[1:], weekmask=mask)
               if days.size > 1 else np.zeros(0, dtype=np.int64))
    holes = np.flatnonzero(missing > 0)
    now_day = np.datetime64((today or _now()).astimezone(UTC).date(), "D")
    trailing = int(np.busday_count(days[-1] + np.timedelta64(1, "D"), now_day, weekmask=mask)
                   if now_day > days[-1] else 0)
    longest = None
    if holes.size:
        k = int(holes[np.argmax(missing[holes])])
        longest = {"trading_days": int(missing[k]), "after": str(days[k]),
                   "before": str(days[k + 1])}
    return {**out, "status": "MEASURED",
            "start": str(days[0]), "end": str(days[-1]),
            "dates_with_bars": int(days.size),
            "gap_count": int(holes.size),
            "longest_gap_trading_days": int(missing.max()) if missing.size else 0,
            "longest_gap": longest,
            "trailing_gap_trading_days": trailing}


def gap_report(symbols: list[str], series_root: Path, *,
               today: datetime | None = None) -> dict[str, Any]:
    """Per-symbol gaps over every series this organ owns, and the summary the Auditor reads."""
    by_symbol = {s: series_gaps(series_root / f"{SERIES_PREFIX}{s}.parquet",
                                trades_weekends=_trades_weekends(s), today=today)
                 for s in sorted(set(symbols))}
    measured = {s: g for s, g in by_symbol.items() if g.get("status") == "MEASURED"}
    worst = None
    if measured:
        s = max(measured, key=lambda k: (measured[k]["longest_gap_trading_days"], k))
        worst = {"symbol": s, "trading_days": measured[s]["longest_gap_trading_days"],
                 "gap": measured[s]["longest_gap"]}
    return {
        "status": "MEASURED" if measured else "UNMEASURED",
        "why": "" if measured else "no readable micro_<SYM> series on this host",
        "threshold_trading_days": GAP_ALERT_TRADING_DAYS,
        "symbols_measured": len(measured),
        "symbols_unmeasured": sorted(s for s in by_symbol if s not in measured),
        "worst_gap": worst,
        "symbols_gap_over_threshold": sorted(
            s for s, g in measured.items()
            if g["longest_gap_trading_days"] > GAP_ALERT_TRADING_DAYS),
        "symbols_stale_over_threshold": sorted(
            s for s, g in measured.items()
            if g["trailing_gap_trading_days"] > GAP_ALERT_TRADING_DAYS),
        "by_symbol": by_symbol,
    }


# ------------------------------------------------------------------------------- propose
def _grid(symbol: str) -> list[tuple[str, dict]]:
    src = f"{SERIES_PREFIX}{symbol}"
    out: list[tuple[str, dict]] = []
    for sig in ft.SIGNAL_COLUMNS:
        for thr in THRESHOLDS:
            for side in SIDES:
                for ttl in TTLS:
                    out.append(("exogenous_conditioner", {
                        "source": src, "signal": sig, "transform": "level_z",
                        "threshold": thr, "side_when_high": side, "lag_hours": LAG_HOURS,
                        "z_window": Z_WINDOW, "ttl_bars": ttl}))
                out.append(("alt_series_momentum", {
                    "source": src, "signal": sig, "lookback": MOMENTUM_LOOKBACK,
                    "threshold": thr, "side_when_up": side, "lag_hours": LAG_HOURS,
                    "z_window": Z_WINDOW, "ttl_bars": 12}))
    return out


def _family(name: str):
    if name == "exogenous_conditioner":
        from mt5desk.family_exogenous_conditioner import family_exogenous_conditioner
        return family_exogenous_conditioner
    from mt5desk.family_alt_series import family_alt_series_momentum
    return family_alt_series_momentum


def screen_symbol(symbol: str, bars: pd.DataFrame, cost: float, unfillable: dict,
                  series_root: Path, series_start: pd.Timestamp) -> list[dict]:
    """Every grid row for one symbol, screened exactly as the judge will rebuild it."""
    import research.proposer_common as pc
    d = bars.loc[bars.index >= series_start - pd.Timedelta(days=10)]
    if len(d) < 100:
        return []
    rows: list[dict] = []
    for fam, params in _grid(symbol):
        sig = _family(fam)(d, series_root=series_root, **params)
        sc = pc.screen(d, sig, cost, unfillable, detail=True)
        if sc is None:
            continue
        pnl = np.asarray(sc.pop("pnl"), dtype=float)
        sc.pop("entry_pos", None)
        k = max(1, round(len(pnl) * OOS_FRACTION))
        oos = pnl[-k:]
        sc["oos_trades"] = int(k)
        sc["oos_net_per_trade"] = round(float(oos.mean()) - cost, 8)
        sc["proposed_gross"] = bool(sc["clears_cost"] and abs(sc["t_gross"]) >= PROPOSE_T_GROSS
                                    and sc["t_gross"] > 0 and sc["oos_net_per_trade"] > 0)
        rows.append({"cell": f"{symbol}.{fam}.{params['signal']}", "symbol": symbol,
                     "family": fam, "params": params, **sc})
    return rows


def _may_hypothesise(symbol: str) -> bool:
    try:
        from research.universe_policy import may_hypothesise
    except Exception:
        return True              # no policy is not a refusal; the donor door re-checks anyway
    try:
        return bool(may_hypothesise(symbol, "exogenous_conditioner"))
    except Exception:
        return True


def propose(readings: list[dict], *, series_root: Path, budget_end: float | None,
            dry_run: bool) -> dict[str, Any]:
    import research.proposer_common as pc
    meta = pc.universe_meta()
    rows: list[dict] = []
    screened: list[str] = []
    skipped: dict[str, str] = {}
    for r in readings:
        sym = r["symbol"]
        if budget_end is not None and time.monotonic() > budget_end:
            skipped[sym] = "budget exhausted (series written; screened next pass)"
            continue
        if r.get("status") != "MEASURED" or int(r.get("bars_measured") or 0) < MIN_SERIES_BARS:
            skipped[sym] = f"under {MIN_SERIES_BARS} measured bars"
            continue
        if not _may_hypothesise(sym):
            # The series is still written (the event lane may read it); screening cells the
            # donor door would refuse by the two-lane mandate only spends the budget.
            skipped[sym] = "event lane (two-lane mandate): series kept, no hypothesis cells"
            continue
        d = pc.bars(sym)
        if d is None:
            skipped[sym] = "no H1 bars"
            continue
        cost = pc.cost_frac(sym, meta, d["close"])
        if cost is None:
            skipped[sym] = "no contract terms"
            continue
        start = pd.Timestamp(r["first_bar"])
        if start.tzinfo is None:
            start = start.tz_localize("UTC")
        rows.extend(screen_symbol(sym, d, cost, pc.artifact_hours(d), series_root, start))
        screened.append(sym)
    rows = pc.deflate(rows)
    best: dict[str, dict] = {}
    for r in sorted((x for x in rows if x.get("proposed_gross")), key=lambda x: -x["t_gross"]):
        best.setdefault(str(r["cell"]), r)
    proposals = sorted(best.values(), key=lambda x: -x["t_gross"])
    cands = [pc.candidate(
        SOURCE, r["symbol"], r["family"], dict(r["params"]),
        mechanism=(f"tick-tape {r['params']['signal']} on {r['symbol']}: "
                   + _MECHANISM.get(str(r["params"]["signal"]), "venue microstructure state")),
        title=f"{r['cell']} {r['params']}",
        evidence={k: r[k] for k in ("n_independent", "gross_per_trade", "net_per_trade",
                                    "cost_frac", "t_gross", "t_deflated_sweep",
                                    "n_tests_sweep", "oos_trades", "oos_net_per_trade")},
    ) for r in proposals]
    for c in cands:
        c["required_data"] = [f"desks/mt5/data/lake/series/{c['params']['source']}.parquet"]
        c["datahub_contract"] = "micro.flow_bars"
    donated = None
    counts: dict[str, Any] = {}
    if cands and not dry_run:
        donated = pc.donate(SOURCE, cands, len(rows))
        counts = pc.donation_counts()
    identities = [pc.identity(c["symbol"], c["family"], c["params"]) for c in cands]
    return {"tests_run": len(rows), "symbols_screened": len(screened),
            "cells_proposed": len(proposals),
            "donated_path": _published_path(Path(donated)) if donated else None,
            "donation": {k: counts.get(k) for k in ("donated", "refused_unstamped",
                                                    "refused_wrong_lane")} if counts else {},
            "identities": identities, "skipped": skipped,
            "proposals": [dict(r) for r in proposals[:200]]}


_MECHANISM = {
    "tick_rule_imbalance": "persistent one-sided tick-test flow is pressure the bar close hides",
    "quote_imbalance": "the sign asymmetry of quote revisions leads the mid (sign-only basis)",
    "vpin": "high bulk-classified toxicity marks informed flow; the next move is larger",
    "signed_vpin": "toxic flow in one direction carries information about the next move",
    "kyle_lambda": "price impact per unit of flow measures how thin and informed the book is",
    "spread_regime_rank": "the venue's own spread regime separates fee from warning",
    "tick_intensity": "quote-revision intensity says how hard the book worked for the bar",
}


# ------------------------------------------------------------------------------- depth probe
def refresh_depth_probe(*, max_age_d: float = DEPTH_PROBE_MAX_AGE_D,
                        probe: Path = DEPTH_PROBE, runner=None) -> dict[str, Any]:
    """Re-probe venue depth weekly where a terminal is attached. Never fabricates a verdict."""
    doc = _read_json(probe, {})
    at = doc.get("at") if isinstance(doc, dict) else None
    age_d = None
    try:
        age_d = (_now() - datetime.fromisoformat(str(at))).total_seconds() / 86400.0
    except (TypeError, ValueError):
        age_d = None
    out: dict[str, Any] = {
        "probe": _published_path(probe), "at": at,
        "age_d": None if age_d is None else round(age_d, 2),
        "symbols_with_real_depth": (doc or {}).get("symbols_with_real_depth"),
        "n_probed": len((doc or {}).get("symbols") or {})}
    if age_d is not None and age_d < max_age_d:
        out["status"] = "FRESH"
        return out
    if runner is None:
        try:
            import MetaTrader5  # noqa: F401
        except Exception:
            out["status"] = "UNMEASURED"
            out["why"] = ("probe is stale and no MetaTrader terminal is importable on this host; "
                          "only the trading box can call MarketBookGet")
            return out

        def runner() -> int:
            return subprocess.run([sys.executable, str(_DESK / "mt5desk" / "tape.py"), "--probe"],
                                  cwd=str(_DESK), timeout=600, capture_output=True).returncode
    try:
        rc = runner()
    except Exception as exc:
        out["status"] = "PROBE_FAILED"
        _LOG.warning("depth probe failed: %r", exc)
        out["why"] = type(exc).__name__
        return out
    fresh = _read_json(probe, {})
    out.update({"status": "REPROBED" if rc == 0 else "PROBE_FAILED", "returncode": rc,
                "at": (fresh or {}).get("at"),
                "symbols_with_real_depth": (fresh or {}).get("symbols_with_real_depth"),
                "n_probed": len((fresh or {}).get("symbols") or {})})
    return out


# ------------------------------------------------------------------------------- run
def _order(symbols: list[str], cursor: str | None) -> list[str]:
    if not cursor or cursor not in symbols:
        return symbols
    i = symbols.index(cursor)
    return symbols[i:] + symbols[:i]


def run(symbols: list[str] | None = None, *, budget_s: float = 900.0, propose_cells: bool = True,
        dry_run: bool = False, tick_root: Path = TICKS, series_root: Path = SERIES_DIR,
        state_path: Path | None = None, report_path: Path = REPORT,
        probe_depth: bool = True) -> dict[str, Any]:
    import research.proposer_common as pc
    started = time.monotonic()
    accumulate_end = started + budget_s * 0.6
    meta = pc.universe_meta()
    state_path = state_path or (series_root / "micro_state.json")
    state = _read_json(state_path, {})
    have = sorted(p.name for p in tick_root.iterdir() if p.is_dir()) if tick_root.is_dir() else []
    if symbols:
        want = {s.upper() for s in symbols}
        have = [s for s in have if s.upper() in want]
    order = _order(have, state.get("_cursor"))
    readings: list[dict] = []
    next_cursor = None
    for sym in order:
        if time.monotonic() > accumulate_end:
            next_cursor = next_cursor or sym
            readings.append({"symbol": sym, "status": "DEFERRED",
                             "why": "accumulation budget spent; resumes here next pass"})
            continue
        pt = point_of(sym, meta)
        if pt is None:
            readings.append({"symbol": sym, "status": "UNMEASURED",
                             "why": "no tick_size/digits in universe.json; the unit is never "
                                    "guessed"})
            continue
        try:
            readings.append(accumulate(sym, pt, state, tick_root=tick_root,
                                       series_root=series_root, budget_end=accumulate_end))
        except Exception as exc:
            _LOG.warning("flow_toxicity accumulate %s: %r", sym, exc)
            readings.append({"symbol": sym, "status": "ERROR", "why": type(exc).__name__})
    state["_cursor"] = next_cursor
    if not dry_run:
        _write_atomic(state_path, json.dumps(state, indent=0, sort_keys=True))
    prop: dict[str, Any] = {"status": "SKIPPED", "why": "--no-propose"}
    if propose_cells:
        prop = propose(readings, series_root=series_root,
                       budget_end=started + budget_s, dry_run=dry_run)
        prop["status"] = "RAN"
    depth = refresh_depth_probe() if (probe_depth and not dry_run) else {"status": "SKIPPED"}
    measured = [r for r in readings if r.get("status") == "MEASURED"]
    on_disk = ([p.stem[len(SERIES_PREFIX):] for p in series_root.glob(f"{SERIES_PREFIX}*.parquet")]
               if series_root.is_dir() else [])
    if symbols:
        on_disk = [s for s in on_disk if s.upper() in {x.upper() for x in symbols}]
    gaps = gap_report([*have, *on_disk], series_root)
    report = {
        "schema": "flow_toxicity/1", "generated_at": _now().isoformat(timespec="seconds"),
        "clock": "hourly_cycle:flow_toxicity",
        "status": ("MEASURED" if measured else "UNMEASURED"),
        "why": ("" if measured else
                "no tick tape on this host (the tape is recorded on the trading box)"),
        "tape_root": _published_path(tick_root), "series_dir": _published_path(series_root),
        "datahub_contract": "micro.flow_bars", "signals": list(ft.SIGNAL_COLUMNS),
        "quote_imbalance_basis": "sign_only",
        "symbols_on_tape": len(have), "symbols_measured": len(measured),
        "bars_measured_total": int(sum(int(r.get("bars_measured") or 0) for r in measured)),
        "deferred": sum(1 for r in readings if r.get("status") == "DEFERRED"),
        "next_cursor": next_cursor, "elapsed_s": round(time.monotonic() - started, 1),
        "cells": {k: v for k, v in prop.items() if k != "proposals"},
        "proposals": prop.get("proposals", [])[:50],
        "depth_probe": depth, "series_gaps": gaps, "readings": readings,
    }
    if not dry_run:
        _write_atomic(report_path, json.dumps(report, indent=1, default=str))
    return report


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--symbol", action="append", default=None)
    ap.add_argument("--budget-s", type=float, default=900.0)
    ap.add_argument("--no-propose", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args(argv)
    rep = run(a.symbol, budget_s=a.budget_s, propose_cells=not a.no_propose, dry_run=a.dry_run)
    c = rep["cells"]
    print(f"FLOW TOXICITY  {rep['status']}  {rep['symbols_measured']}/{rep['symbols_on_tape']} "
          f"symbols, {rep['bars_measured_total']} measured bars; tests={c.get('tests_run', 0)} "
          f"proposed={c.get('cells_proposed', 0)} depth={rep['depth_probe'].get('status')}")
    g = rep["series_gaps"]
    print(f"  gaps {g['status']}: worst={g['worst_gap']} "
          f"over_{g['threshold_trading_days']}d={g['symbols_gap_over_threshold']} "
          f"stale={g['symbols_stale_over_threshold']}")
    if rep["status"] != "MEASURED":
        print(f"  {rep['why']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
