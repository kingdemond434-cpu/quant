"""Zero-order forward clock for every exact external/orthogonal universal certificate."""
from __future__ import annotations

import json
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pandas as pd

BASE = Path(__file__).resolve().parent.parent
ROOT = BASE.parents[1]
for value in (ROOT, BASE, BASE / "research", BASE / "scripts"):
    if str(value) not in sys.path:
        sys.path.insert(0, str(value))

from gate_policy import all_ten_pass, is_exact_policy  # noqa: E402
from scripts.external_gauntlet import build_cell  # noqa: E402

from research.h1_source import fetch_h1  # noqa: E402

REPORTS = BASE / "reports"
SHADOW = REPORTS / "shadow"
STATE = SHADOW / "external_shadow_state.json"
MIN_TRADES = 20
FULL_TRADES = 50
MIN_DAYS = 14


def _read(path: Path) -> dict:
    try:
        value = json.loads(path.read_text("utf-8"))
        return value if isinstance(value, dict) else {}
    except (OSError, ValueError):
        return {}


def _max_drawdown(values: list[float]) -> float:
    total = peak = worst = 0.0
    for value in values:
        total += value
        peak = max(peak, total)
        worst = min(worst, total - peak)
    return worst


def main() -> int:
    certs = _read(REPORTS / "UNIVERSAL_SURVIVORS.json")
    state = _read(STATE)
    now = datetime.now(UTC)
    if not is_exact_policy(certs.get("gate_policy")):
        state.update(updated_at=now.isoformat(), source_gate_policy_valid=False,
                     source_error="universal certificate policy attestation invalid")
        SHADOW.mkdir(parents=True, exist_ok=True)
        STATE.write_text(json.dumps(state, indent=2), "utf-8")
        return 1
    meta = _read(BASE / "data" / "universe" / "universe.json")
    certified = processed = 0
    for key, cert in (certs.get("survivors") or {}).items():
        if not str(key).startswith("external.") or not isinstance(cert, dict):
            continue
        if not all_ten_pass(cert.get("gates")):
            continue
        spec = cert.get("shadow_spec")
        if not isinstance(spec, dict) or spec.get("hunt") != "external_discoveries":
            continue
        certified += 1
        row = state.get(key, {}) if isinstance(state.get(key), dict) else {}
        frozen = pd.Timestamp(cert.get("gated_at"))
        frozen = frozen.tz_localize("UTC") if frozen.tzinfo is None else frozen.tz_convert("UTC")
        row.update(certificate=key, cell=cert.get("cell"), forward_start=frozen.isoformat(),
                   last_attempt_at=now.isoformat(), order_authority=False,
                   promotion_authority=False)
        bars = fetch_h1(str(spec["symbol"]), frozen.to_pydatetime() - timedelta(days=45),
                        prefer="MT5", prefer_promotion_authority=True)
        if bars is None:
            row.update(status="NO_DATA", why="no H1 source returned bars")
            state[key] = row
            continue
        covered, why = bars.covers(frozen.to_pydatetime())
        row.update(bar_source=bars.source,
                   bars_freshest=None if bars.freshest is None else bars.freshest.isoformat(),
                   why=why)
        if not covered:
            row["status"] = "NO_DATA"
            state[key] = row
            continue
        cell = build_cell(str(spec["symbol"]), str(spec["family"]),
                          dict(spec.get("params") or {}), meta, h1_override=bars.df)
        if cell is None:
            row.update(status="WIRING_ERROR", why="exact certified executable could not rebuild")
            state[key] = row
            continue
        try:
            result = __import__("mt5desk.engine", fromlist=["run_backtest"]).run_backtest(
                cell["df"], cell["sigs"], cell["costs"]
            )
        except Exception as exc:
            row.update(status="WIRING_ERROR", why=f"{type(exc).__name__}: {exc}")
            state[key] = row
            continue
        trades = [t for t in result.trades if pd.Timestamp(t.entry_time).tz_convert("UTC") > frozen]
        values = [float(t.r_multiple) for t in trades]
        ledger = SHADOW / f"ledger_{key.replace('/', '_')}.json"
        ledger.parent.mkdir(parents=True, exist_ok=True)
        stamp = bars.stamp()
        ledger.write_text(json.dumps([
            {"entry_time": str(t.entry_time), "exit_time": str(t.exit_time), "side": t.side,
             "entry": t.entry, "exit": t.exit, "r_multiple": t.r_multiple,
             "reason": t.reason, **stamp} for t in trades
        ], indent=2), "utf-8")
        days = max(0, (now - frozen.to_pydatetime()).days)
        exp = sum(values) / len(values) if values else 0.0
        row.update(n=len(values), cum_r=sum(values), exp_r=exp, max_dd_r=_max_drawdown(values),
                   days_active=days, forward_bars_evaluated=int((cell["df"].index > frozen).sum()),
                   forward_eligible_signals=sum(
                       pd.Timestamp(s.time) > frozen for s in cell["sigs"]
                   ),
                   last_evaluated_bar=(None if cell["df"].empty else
                                       pd.Timestamp(cell["df"].index.max()).isoformat()),
                   ledger=str(ledger.relative_to(BASE)),
                   promotion_authority=bars.promotion_authority)
        ready = len(values) >= FULL_TRADES or (days >= MIN_DAYS and len(values) >= MIN_TRADES)
        if not bars.promotion_authority:
            row.update(status="PROXY_SHADOW", why="non-Fusion bars cannot promote")
        elif not ready:
            row.update(status="ACTIVE", why=f"accruing {len(values)}/{FULL_TRADES} trades; "
                       f"{days}/{MIN_DAYS} days")
        elif exp > 0 and row["max_dd_r"] > -25.0:
            row.update(status="PROMOTION_CANDIDATE",
                       why="Fusion-native fixed forward clock completed net positive")
        else:
            row.update(status="KILL", why="fixed forward evidence completed without net edge")
        state[key] = row
        processed += 1
    state.update(updated_at=now.isoformat(), source_gate_policy_valid=True,
                 certified_external_sleeves=certified, processed_external_sleeves=processed)
    SHADOW.mkdir(parents=True, exist_ok=True)
    STATE.write_text(json.dumps(state, indent=2), "utf-8")
    print(f"external shadow: {processed}/{certified} exact certificate(s) processed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
