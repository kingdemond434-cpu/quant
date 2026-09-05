"""Forward-only shadow clock for the four stable anti-crowd gold scalp candidates.

Discovery bars end before ``SHADOW_START`` and are never counted as forward trades. The engine
replays only newly acquired M5/M15 broker bars, overwrites deterministic ledgers idempotently, and
cannot grant promotion authority while the feed is a non-Fusion proxy. Fifty trades can mature a
sleeve immediately; after fourteen calendar days at least twenty trades are still required.
"""
from __future__ import annotations

import json
import sys
from datetime import UTC, datetime
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

from desks.mt5.research import forward_verdict  # noqa: E402
from desks.mt5.research import scalp_family_expansion as families  # noqa: E402
from desks.mt5.research import scalp_reverse_engineering as core  # noqa: E402

DESK = Path(__file__).resolve().parents[1]
DATA = DESK / "data" / "universe"
SHADOW = DESK / "reports" / "shadow"
STATE = SHADOW / "scalp_shadow_state.json"
SHADOW_START = pd.Timestamp("2026-08-22T18:00:00Z")

CANDIDATES = {
    "xau_m5_anti_breakout_overlap": (
        "M5", families.Choice("anti_donchian_breakout", "overlap", 1.0, 1.5, 9)
    ),
    "xau_m5_anti_momentum_ny": (
        "M5", families.Choice("anti_three_bar_momentum", "new_york", 1.0, 1.5, 9)
    ),
    "xau_m15_anti_breakout": (
        "M15", families.Choice("anti_donchian_breakout", "all", 1.0, 1.5, 6)
    ),
    "xau_m15_anti_momentum": (
        "M15", families.Choice("anti_three_bar_momentum", "all", 1.0, 1.5, 6)
    ),
}


def _market_open(ts: pd.Timestamp) -> bool:
    """Approximate the broker's 24/5 gold/FX session for freshness accounting."""
    ts = pd.Timestamp(ts).tz_convert("UTC")
    wd, hour = ts.weekday(), ts.hour
    return not (wd == 5 or (wd == 4 and hour >= 22) or (wd == 6 and hour < 22))


def _trading_lag_hours(last_bar: pd.Timestamp, now: datetime) -> float:
    """Elapsed market-open hours; weekends must not manufacture stale evidence alarms."""
    cursor = pd.Timestamp(last_bar).ceil("h")
    end = pd.Timestamp(now)
    cursor = cursor.tz_localize("UTC") if cursor.tzinfo is None else cursor.tz_convert("UTC")
    end = end.tz_localize("UTC") if end.tzinfo is None else end.tz_convert("UTC")
    hours = 0
    while cursor < end:
        if _market_open(cursor):
            hours += 1
        cursor += pd.Timedelta(hours=1)
    return float(hours)


def _source() -> dict:
    path = DATA / "XAUUSD_scalp_source.json"
    if not path.exists():
        return {"promotion_authority": False, "reason": "missing source manifest"}
    try:
        return json.loads(path.read_text("utf-8"))
    except (OSError, ValueError) as exc:
        return {"promotion_authority": False, "reason": f"invalid source manifest: {exc}"}



def _broker_offset_h() -> float:
    """Measured broker-vs-UTC offset, so the forward boundary converts instead of guessing."""
    try:
        import MetaTrader5 as _mt5
        from h1_source import broker_utc_offset_hours
        return float(broker_utc_offset_hours(_mt5))
    except Exception:
        return 0.0


def _drawdown(rs: list[float]) -> float:
    if not rs:
        return 0.0
    curve = np.r_[0.0, np.cumsum(rs)]
    return float(np.min(curve - np.maximum.accumulate(curve)))


def _previous_sleeves() -> dict[str, dict]:
    """Return the writer's prior clock state, or no state when it is unreadable.

    A replay rebuilds summary statistics but it must not rebuild a pre-registration
    boundary.  Treating an unreadable prior state as a new clock is unsafe: the
    caller will emit an unstamped row, which the central fail-closed fence reports.
    """
    try:
        prior = json.loads(STATE.read_text("utf-8"))
    except (OSError, ValueError):
        return {}
    rows = prior.get("sleeves") if isinstance(prior, dict) else None
    return {str(k): v for k, v in (rows or {}).items() if isinstance(v, dict)}


def _first_forward_trade(records: list[dict]) -> str | None:
    """Return an auditable UTC first-trade stamp for the clock watchdog."""
    stamps: list[pd.Timestamp] = []
    for record in records:
        raw = record.get("entry_time") or record.get("time") or record.get("open_time")
        if raw is None:
            continue
        try:
            stamps.append(pd.Timestamp(raw))
        except (TypeError, ValueError):
            continue
    if not stamps:
        return None
    first = min(stamps)
    if first.tzinfo is None:
        first = first.tz_localize("UTC")
    else:
        first = first.tz_convert("UTC")
    return first.isoformat()


def run(now: datetime | None = None) -> dict:
    now = now or datetime.now(UTC)
    prior_sleeves = _previous_sleeves()
    source = _source()
    authority = bool(source.get("promotion_authority"))
    # EVERY DECLARED CANDIDATE GETS A REAL FORWARD CLOCK (principal decision 2026-08-23, carried
    # from the branch the box runs; reaffirmed 2026-09-04). The ten-gate gauntlet has no path
    # that certifies an M5/M15 scalp spec -- no `gold_scalp` certificate can exist -- so gating
    # SHADOW admission on one quarantined the whole lane and produced no evidence at all. The
    # lane's certificate is its own forward clock: Fusion-native bars, the canon maturity bar
    # (50 trades, or 14 days with 20), positive expectancy and the drawdown bound, judged only
    # after the frozen pre-registration boundary. Promotion (research/promoter.py) reads that.
    admitted = dict(CANDIDATES)
    blocked_names: list[str] = []
    state: dict = {
        "updated_at": now.isoformat(timespec="seconds"),
        "shadow_start": SHADOW_START.isoformat(), "source": source,
        "declared_sleeves": len(CANDIDATES), "configured_sleeves": len(admitted),
        "gate_blocked_sleeves": len(blocked_names), "sleeves": {},
        "quarantined_candidates": {
            name: {"status": "QUARANTINED_UNCERTIFIED", "n": 0,
                   "promotion_authority": False,
                   "gate_reason": "missing exact original universal ten-gate pass"}
            for name in blocked_names
        },
    }
    SHADOW.mkdir(parents=True, exist_ok=True)
    cache: dict[str, tuple[pd.DataFrame, dict[str, np.ndarray]]] = {}
    for name, (tf, choice) in admitted.items():
        path = DATA / f"XAUUSD_{tf}.parquet"
        if not path.exists():
            state["sleeves"][name] = {"status": "NO_DATA", "n": 0}
            continue
        if tf not in cache:
            df = pd.read_parquet(path).sort_index()
            cache[tf] = (df, families._base_signals(df))
        df, all_signals = cache[tf]
        signal = all_signals[choice.family].copy()
        signal[~families._session_mask(df.index, choice.session)] = 0
        signal[df.index < SHADOW_START] = 0
        records = core.simulate(
            df, families._cfg(choice, "bounded_structural"), signal_override=signal,
            detailed=True,
        )
        assert isinstance(records, list)
        ledger = SHADOW / f"ledger_{name}.json"

        # FORWARD EVIDENCE STARTS AT THIS SLEEVE'S OWN FROZEN CLOCK, not at the engine-wide
        # SHADOW_START. `forward_start` is stamped per row when the row is created; observations
        # before it were available while the cell was being selected. Measured 2026-08-26: these
        # four scalp rows froze at 01:19 and reported 4/8/17/28 observations dating back four
        # days -- 57 selection-era observations presented as forward evidence. History is kept
        # and tagged; only post-boundary rows feed n / exp / maturity.
        #
        # The boundary is CONVERTED: bar stamps are on the broker clock (Fusion runs +3h) while
        # `forward_start` is true UTC. Comparing them raw moves the boundary three hours.
        _prior = prior_sleeves.get(name) or {}
        _fs = _prior.get("forward_start")
        _bound = None
        if _fs:
            try:
                _bound = pd.Timestamp(_fs) + pd.Timedelta(hours=_broker_offset_h())
            except (ValueError, TypeError):
                _bound = None
        _all = list(records)
        if _bound is not None:
            records = [r for r in _all
                       if pd.Timestamp(str(r.get("entry_time") or r.get("time") or
                                           r.get("open_time") or SHADOW_START)) >= _bound]
        else:
            records = []
        n_historical = len(_all) - len(records)
        ledger = SHADOW / f"ledger_{name}.json"
        ledger.write_text(json.dumps(
            [{**r, "phase": ("forward" if r in records else "historical")} for r in _all],
            indent=2), "utf-8")
        rs = [float(row["r"]) for row in records]
        n = len(rs)
        last_bar = pd.Timestamp(df.index[-1])
        lag_hours = _trading_lag_hours(last_bar, now)
        stale_source = lag_hours > (1.0 if tf == "M5" else 2.0)
        _clock_from = (_bound - pd.Timedelta(hours=_broker_offset_h())
                       if _bound is not None else SHADOW_START)
        days = max(0, (last_bar.date() - _clock_from.date()).days)
        exp = float(np.mean(rs)) if rs else None
        max_dd = _drawdown(rs)
        matured = n >= 50 or (days >= 14 and n >= 20)
        # THE UNIFIED VERDICT'S DIAGNOSTICS ride on the row -- effective n, the always-valid
        # lower bound, significance -- so the allocator and a reader can see how much of the
        # forward record is independent evidence. They inform; the canon bar above decides.
        try:
            fv = forward_verdict.verdict(rs, days)
            diagnostics = {k: fv.get(k) for k in ("n_eff", "n_eff_basis", "seq_lower_bound",
                                                  "significant", "independent", "reason")}
        except Exception as exc:                                  # a diagnostic never fails a clock
            diagnostics = {"error": f"{type(exc).__name__}: {exc}"}
        if last_bar < SHADOW_START:
            status = "WAITING_FOR_FORWARD_BARS"
        elif stale_source:
            status = "STALE_SOURCE"
        elif not authority:
            status = "PROXY_SHADOW"
        elif not matured:
            status = "ACCUMULATING"
        elif exp is not None and exp > 0.05 and max_dd > -25.0:
            status = "PROMOTION_CANDIDATE"
        else:
            status = "KILL"
        state["sleeves"][name] = {
            # THE CLOCK IS THE PREREGISTRATION, NEVER "NOW". These cells were declared when the
            # lane's SHADOW_START was committed; a row-level stamp of the current wall clock on
            # an already-declared cell DISCARDS every legitimate forward day since declaration
            # (measured 2026-08-27: rows with 6 true forward days re-stamped to day 0). A row
            # keeps an existing freeze; a row without one gets the lane preregistration.
            "forward_start": _fs or SHADOW_START.isoformat(),
            "first_trade_at": _first_forward_trade(records) or _prior.get("first_trade_at"),
            "status": status, "timeframe": tf, "choice": choice.__dict__,
            "n": n, "n_historical": n_historical, "days": days,
            "expectancy_r": exp, "max_drawdown_r": max_dd, "forward_verdict": diagnostics,
            "certificate": "forward_clock (no backtest gauntlet exists for M5/M15 scalps)",
            "last_source_bar": last_bar.isoformat(), "matured": matured,
            "source_trading_lag_hours": lag_hours, "source_stale": stale_source,
            "promotion_authority": authority,
            "note": ("Proxy bars may accrue diagnostic evidence but cannot authorize capital."
            if not authority else "Fusion-native forward shadow."),
        }
    state["represented_sleeves"] = len(state["sleeves"])
    STATE.write_text(json.dumps(state, indent=2), "utf-8")
    return state


def main() -> int:
    state = run()
    for name, sleeve in state["sleeves"].items():
        print(name, sleeve["status"], f"n={sleeve['n']}",
              f"E={sleeve.get('expectancy_r')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
