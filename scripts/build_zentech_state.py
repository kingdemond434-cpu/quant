"""Build the read-only ZENTECH operator view from canonical MT5 artifacts."""
from __future__ import annotations

import json
import math
import os
import tempfile
from contextlib import suppress
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DESK = ROOT / "desks" / "mt5"
OUT = ROOT / "web" / "zentech_state.json"


def _read(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
        return value if isinstance(value, dict) else {}
    except (OSError, json.JSONDecodeError):
        return {}


def _number(*values: Any) -> float | None:
    for value in values:
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            value = float(value)
            if math.isfinite(value):
                return value
    return None


def _find(data: dict[str, Any], *names: str) -> Any:
    wanted = {name.casefold() for name in names}
    stack: list[Any] = [data]
    while stack:
        current = stack.pop()
        if isinstance(current, dict):
            for key, value in current.items():
                if str(key).casefold() in wanted:
                    return value
                if isinstance(value, (dict, list)):
                    stack.append(value)
        elif isinstance(current, list):
            stack.extend(current)
    return None


def _timestamp(value: Any) -> datetime | None:
    if not isinstance(value, str):
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        return parsed.replace(tzinfo=UTC) if parsed.tzinfo is None else parsed.astimezone(UTC)
    except ValueError:
        return None


def _ledger() -> list[dict[str, Any]]:
    path = DESK / "data" / "live_ledger.jsonl"
    try:
        return [json.loads(line) for line in path.read_text("utf-8").splitlines()
                if line.strip()]
    except (OSError, json.JSONDecodeError):
        return []


def _series(rows: list[dict[str, Any]], starting: float | None) -> list[float]:
    if starting is None:
        return []
    values = [starting]
    for row in rows:
        pnl = _number(row.get("profit"), row.get("net_pnl"), row.get("pnl"))
        if pnl is not None:
            values.append(values[-1] + pnl)
    return values[-180:]


def _shadow_rows() -> list[dict[str, Any]]:
    combined: list[tuple[str, dict[str, Any]]] = []
    for path in (DESK / "reports" / "shadow" / "shadow_state.json",
                 DESK / "reports" / "shadow" / "qquant_shadow_state.json"):
        for key, row in _read(path).items():
            if isinstance(row, dict) and "status" in row:
                combined.append((key, row))
    output = []
    for key, row in combined:
        n = int(_number(row.get("n")) or 0)
        exp = _number(row.get("exp_r"))
        cum_r = _number(row.get("cum_r"))
        # User-facing profitable list is literal: unknown and non-positive rows are excluded.
        if exp is None or exp <= 0:
            continue
        roll = _number(row.get("roll20_exp"))
        decay = None if roll is None or exp == 0 else roll / exp
        output.append({
            "name": key, "status": row.get("status"), "trades": n,
            "expectancy_r": exp, "cum_r": cum_r, "max_dd_r": _number(row.get("max_dd_r")),
            "days": int(_number(row.get("days_active")) or 0), "source": row.get("bar_source"),
            "decay_ratio": decay, "promotion_authority": row.get("promotion_authority") is True,
        })
    return sorted(output, key=lambda row: row["expectancy_r"], reverse=True)


def build() -> dict[str, Any]:
    gateway = _read(DESK / "data" / "gateway_state.json")
    account = _read(DESK / "data" / "account_state.json") or gateway
    qquant = _read(DESK / "reports" / "QQUANT_GATES.json")
    universal = _read(DESK / "reports" / "UNIVERSAL_SURVIVORS.json")
    markout = _read(DESK / "reports" / "markout.json")
    midnight = _read(ROOT / "data" / "intelligence" / "mt5_midnight_state.json")
    daily = _read(DESK / "data" / "daily_cycle_state.json")
    rows = _ledger()
    balance = _number(_find(account, "balance", "account_balance"))
    equity = _number(_find(account, "equity", "account_equity"))
    start = _number(_find(account, "starting_capital", "initial_balance"), balance)
    profitable = _shadow_rows()
    passes = [row for row in qquant.get("verdicts", [])
              if isinstance(row, dict) and row.get("passed") is True]
    candidates = []
    for row in passes:
        stages = row.get("stages", {})
        candidates.append({
            "name": row.get("id"), "hunt": row.get("hunt"), "days": row.get("days"),
            "dsr": _number(stages.get("deflated_sharpe", {}).get("dsr")),
            "wf_sharpe": _number(stages.get("walk_forward", {}).get("oos_sharpe")),
            "pbo": _number(stages.get("pbo", {}).get("pbo")),
            "spa_p": _number(stages.get("reality_check_spa", {}).get("p_value")),
        })
    freshest = []
    for path in (DESK / "data" / "universe").glob("*_H1.parquet"):
        freshest.append(path.stat().st_mtime)
    newest_bar_file = (datetime.fromtimestamp(max(freshest), UTC).isoformat()
                       if freshest else None)
    now = datetime.now(UTC)
    account_at = _timestamp(_find(account, "updated_at", "timestamp", "at", "fetched_at"))
    account_age = None if account_at is None else (now - account_at).total_seconds()
    live_state = "LIVE" if equity is not None and account_age is not None and account_age <= 120 else (
        "STALE" if equity is not None else "UNMEASURED"
    )
    payload = {
        "generated_at": now.isoformat(),
        "identity": {"name": "ZENTECH", "caption": "MULTI-ASSET MT5 INSTITUTIONAL QUANT FUND",
                     "operator": "ZAID HUSSAIN", "moniker": "THE WOLF OF WALL STREET"},
        "account": {
            "venue": _find(account, "server", "broker") or "UNMEASURED",
            "currency": _find(account, "currency") or "UNMEASURED",
            "balance": balance, "equity": equity, "starting_capital": start,
            "today_pnl": _number(_find(account, "today_pnl", "daily_pnl")),
            "open_pnl": _number(_find(account, "profit", "floating_pnl", "open_pnl")),
            "margin": _number(_find(account, "margin")),
            "free_margin": _number(_find(account, "margin_free", "free_margin")),
            "growth_pct": None if start in (None, 0) or equity is None else 100 * (equity / start - 1),
            "source_updated_at": None if account_at is None else account_at.isoformat(),
            "source_age_seconds": account_age,
        },
        "research": {
            "candidates_tested": qquant.get("survivors_total"),
            "historical_survivors": qquant.get("survivors_passing_all"),
            "canonical_survivors": universal.get("n"),
            "gate_failures": qquant.get("gate_fails", {}),
            "survivors": candidates,
        },
        "shadow": {"profitable": profitable, "profitable_count": len(profitable)},
        "execution": {
            "markout_usable": markout.get("usable") is True,
            "matched_fills": markout.get("n_matched"), "why": markout.get("why"),
            "open_trades": _find(gateway, "open_positions", "positions") or [],
        },
        "health": {
            "newest_h1_file": newest_bar_file, "midnight": midnight,
            "daily_cycle": daily, "status": live_state,
        },
        "equity_curve": _series(rows, start),
        "disclaimer": "Research and operator telemetry only. Missing values are UNMEASURED; shadow has zero order authority.",
    }
    return payload


def main() -> int:
    payload = build()
    OUT.parent.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(prefix=".zentech_state.", dir=OUT.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, indent=2, default=str)
        os.replace(name, OUT)
    finally:
        with suppress(FileNotFoundError):
            os.unlink(name)
    print(f"ZENTECH state: {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
