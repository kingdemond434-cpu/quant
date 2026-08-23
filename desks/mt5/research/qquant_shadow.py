"""Forward-clock exact QQUANT certificates on venue-native bars, with zero order authority."""
from __future__ import annotations

import json
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pandas as pd

BASE = Path(__file__).resolve().parent.parent
for value in (BASE, BASE / "research"):
    if str(value) not in sys.path:
        sys.path.insert(0, str(value))

from gate_policy import all_ten_pass, is_exact_policy  # noqa: E402
from mt5desk.engine import Costs, run_backtest  # noqa: E402
from research.h1_source import fetch_h1  # noqa: E402
from run_hunt12 import day_states  # noqa: E402
from run_hunt16 import FAMILIES, WINDOWS  # noqa: E402

REPORTS = BASE / "reports"
SHADOW = REPORTS / "shadow"
STATE = SHADOW / "qquant_shadow_state.json"
MIN_TRADES = 20
FULL_TRADES = 50
MIN_DAYS = 14


def _read(path: Path) -> dict:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
        return value if isinstance(value, dict) else {}
    except (OSError, json.JSONDecodeError):
        return {}


def _max_drawdown(values: list[float]) -> float:
    running = peak = 0.0
    worst = 0.0
    for value in values:
        running += value
        peak = max(peak, running)
        worst = min(worst, running - peak)
    return worst


def main() -> int:
    certs = _read(REPORTS / "UNIVERSAL_SURVIVORS.json")
    state = _read(STATE)
    now = datetime.now(UTC)
    rows = certs.get("survivors", {}) if is_exact_policy(certs.get("gate_policy")) else {}
    certified = 0
    processed = 0
    for key, cert in rows.items():
        if not str(key).startswith("qquant.") or not isinstance(cert, dict):
            continue
        if not all_ten_pass(cert.get("gates")):
            continue
        spec = cert.get("shadow_spec")
        if not isinstance(spec, dict) or spec.get("hunt") != "hunt16.json":
            continue
        certified += 1
        family = str(spec.get("family"))
        selector = str(spec.get("selector"))
        if family not in FAMILIES or selector not in WINDOWS:
            state[key] = {"status": "WIRING_ERROR", "promotion_authority": False,
                          "why": "certified family/selector has no exact executable"}
            continue
        frozen_at = pd.Timestamp(cert.get("gated_at"))
        if frozen_at.tzinfo is None:
            frozen_at = frozen_at.tz_localize("UTC")
        else:
            frozen_at = frozen_at.tz_convert("UTC")
        start = frozen_at.to_pydatetime() - timedelta(days=45)
        bars = fetch_h1(str(spec["symbol"]), start, prefer="MT5")
        row = state.get(key, {}) if isinstance(state.get(key), dict) else {}
        row.update({
            "certificate": key,
            "cell": cert.get("cell"),
            "forward_start": frozen_at.isoformat(),
            "last_attempt_at": now.isoformat(),
            "promotion_authority": False,
            "order_authority": False,
        })
        if bars is None:
            row.update(status="NO_DATA", why="no H1 source returned bars")
            state[key] = row
            continue
        covered, why = bars.covers(frozen_at.to_pydatetime())
        row.update(bar_source=bars.source, bars_freshest=(None if bars.freshest is None
                                                         else bars.freshest.isoformat()), why=why)
        if not covered:
            row["status"] = "NO_DATA"
            state[key] = row
            continue
        h1 = bars.df
        side = 1 if str(spec.get("side")).upper() == "LONG" else -1
        signal_hour = WINDOWS[selector].get("signal_at") or WINDOWS[selector]["range_start"]
        signals = [s for s in FAMILIES[family](h1, side) if s.time.hour == signal_hour]
        condition = spec.get("condition")
        if condition:
            states = day_states(h1)
            signals = [s for s in signals
                       if states.get(pd.Timestamp(s.time).date()) == condition]
        meta = _read(BASE / "data" / "universe" / "universe.json")
        costs = Costs.from_symbol(meta.get(str(spec["symbol"]), {}), mult=2.0)
        result = run_backtest(h1, signals, costs)
        trades = [trade for trade in result.trades
                  if pd.Timestamp(trade.entry_time).tz_convert("UTC") > frozen_at]
        values = [float(trade.r_multiple) for trade in trades]
        ledger = SHADOW / f"ledger_{key.replace(' ', '_').replace('/', '_')}.json"
        ledger.parent.mkdir(parents=True, exist_ok=True)
        stamp = bars.stamp()
        ledger.write_text(json.dumps([
            {"entry_time": str(t.entry_time), "exit_time": str(t.exit_time),
             "side": t.side, "entry": t.entry, "exit": t.exit,
             "r_multiple": t.r_multiple, "reason": t.reason, **stamp}
            for t in trades
        ], indent=2), encoding="utf-8")
        days = max(0, (now - frozen_at.to_pydatetime()).days)
        expectancy = sum(values) / len(values) if values else 0.0
        row.update({
            "n": len(values), "cum_r": sum(values), "exp_r": expectancy,
            "max_dd_r": _max_drawdown(values), "days_active": days,
            "ledger": str(ledger.relative_to(BASE)),
            "promotion_authority": bars.promotion_authority,
        })
        ready = len(values) >= FULL_TRADES or (days >= MIN_DAYS and len(values) >= MIN_TRADES)
        if not bars.promotion_authority:
            row["status"] = "PROXY_SHADOW"
            row["why"] = "forward rows are not Fusion-native and cannot promote"
        elif not ready:
            row["status"] = "ACTIVE"
            row["why"] = f"accruing: {len(values)}/{FULL_TRADES} trades; {days}/{MIN_DAYS} days"
        elif expectancy > 0 and row["max_dd_r"] > -25.0:
            row["status"] = "PROMOTION_CANDIDATE"
            row["why"] = (
                "Fusion-native forward evidence met the fixed clock and remained net positive"
            )
        else:
            row["status"] = "KILL"
            row["why"] = "Fusion-native forward evidence completed without positive net expectancy"
        state[key] = row
        processed += 1
    state["updated_at"] = now.isoformat()
    state["certified_qquant_sleeves"] = certified
    state["processed_qquant_sleeves"] = processed
    SHADOW.mkdir(parents=True, exist_ok=True)
    STATE.write_text(json.dumps(state, indent=2), encoding="utf-8")
    print(f"qquant shadow: {processed}/{certified} exact certificate(s) processed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
