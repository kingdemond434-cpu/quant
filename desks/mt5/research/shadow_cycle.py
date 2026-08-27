"""Frequent, idempotent owner of every configured MT5 forward-shadow sleeve.

This is deliberately separate from daily research. Forward evidence follows data arrival, not a
calendar ceremony: each invocation replays the latest bars, refreshes all sleeve states, then runs
the deterministic promoter. Replays overwrite content-addressable ledgers, so cadence cannot
double-count trades.
"""
from __future__ import annotations

import json
import os
import traceback
from datetime import UTC, datetime
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
OUT = BASE / "reports" / "shadow" / "shadow_health.json"


def _refresh_scalp_bars() -> None:
    """Refresh broker M1/M5/M15 before replay; never place or modify an order.

    THIS USED TO ROUTE THROUGH fetch_gold_scalp.fetch(), which hard-refuses any
    account with account.trade_allowed set -- "refusing history job: account
    permits trading". That refusal is correct and stays completely untouched:
    fetch_gold_scalp.py is built for a heavier, occasional, manually-run pull
    (up to 90k bars, paged, 15 retries) and refusing to run that shape of job
    against a live-trading terminal is the right blast-radius guard for IT.

    But routing the routine 15-minute cycle through that same function meant
    every scheduled run refused outright the moment the desk went live on a
    real trading account -- these four scalp sleeves would stay
    WAITING_FOR_FORWARD_BARS forever on the one account this desk actually
    trades on, which is not a data problem, it is a wiring problem: this
    cycle's need is a small, bounded, ROUTINE refresh, the same shape of
    operation h1_source.from_mt5 already performs on this exact
    trade-allowed account every cycle, for the other 36 sleeves' H1 bars, with
    no incident. So this reuses that already-proven policy -- initialize,
    read, shutdown, no trade_allowed check -- and fetch_gold_scalp's own
    paging helper (_paged_rates, already exercised by the manual path), rather
    than fetch_gold_scalp.fetch()'s wrapper and its refusal. Writes the exact
    same file shapes fetch_gold_scalp.fetch() did -- XAUUSD_{tf}.parquet
    indexed by "timestamp", and XAUUSD_scalp_source.json with an honest (not
    refused) account_trade_allowed -- so scalp_shadow.py, which reads both,
    needs no changes.
    """
    if os.name != "nt":
        return
    import json as _json
    from datetime import UTC as _UTC
    from datetime import datetime as _datetime

    import h1_source
    import MetaTrader5 as mt5
    import pandas as pd
    from fetch_gold_scalp import _paged_rates

    out_dir = BASE / "data" / "universe"
    frames = {"M1": mt5.TIMEFRAME_M1, "M5": mt5.TIMEFRAME_M5, "M15": mt5.TIMEFRAME_M15}
    failures: list[str] = []
    for terminal in h1_source._terminal_candidates():
        if not Path(terminal).exists():
            continue
        if not mt5.initialize(path=terminal, timeout=15_000):
            failures.append(f"{terminal}: initialize failed: {mt5.last_error()}")
            continue
        try:
            account = mt5.account_info()
            if account is None:
                failures.append(f"{terminal}: account unavailable")
                continue
            if not mt5.symbol_select("XAUUSD", True):
                failures.append(f"{terminal}: cannot select XAUUSD: {mt5.last_error()}")
                continue
            result: dict[str, int] = {}
            out_dir.mkdir(parents=True, exist_ok=True)
            for label, timeframe in frames.items():
                rates = _paged_rates(mt5, "XAUUSD", timeframe, 20_000)
                if rates is None or len(rates) == 0:
                    result[label] = 0
                    continue
                frame = pd.DataFrame(rates)
                frame.index = pd.to_datetime(frame.pop("time"), unit="s", utc=True)
                frame.index.name = "timestamp"
                frame.to_parquet(out_dir / f"XAUUSD_{label}.parquet")
                result[label] = len(frame)
            terminal_info = mt5.terminal_info()
            server = str(account.server)
            (out_dir / "XAUUSD_scalp_source.json").write_text(_json.dumps({
                "fetched_at": _datetime.now(_UTC).isoformat(timespec="seconds"),
                "source_server": server,
                "source_company": str(terminal_info.company if terminal_info else ""),
                "account_trade_allowed": bool(account.trade_allowed),
                "symbol": "XAUUSD", "rows": result,
                "promotion_authority": "fusion" in server.casefold(),
            }, indent=2), "utf-8")
            if all(result.values()):
                return
            failures.append(f"{terminal}: incomplete {result}")
        except Exception as exc:
            failures.append(f"{terminal}: {type(exc).__name__}: {exc}")
        finally:
            mt5.shutdown()
    raise RuntimeError("no MT5 history source: " + " | ".join(failures))


def _read(path: Path) -> dict:
    try:
        row = json.loads(path.read_text("utf-8"))
        return row if isinstance(row, dict) else {}
    except (OSError, ValueError):
        return {}


def _terminal_status(value: object) -> bool:
    status = str(value or "").upper()
    return any(status == prefix or status.startswith(prefix + "_") for prefix in (
        "KILL", "PROMOTED", "DEAD", "REJECTED", "RETIRED", "QUARANTINED",
    ))


def run() -> tuple[dict, int]:
    import external_shadow
    import promoter
    import qquant_shadow
    import scalp_shadow
    import shadow_forward

    started = datetime.now(UTC)
    errors: dict[str, str] = {}
    for name, fn in (
        ("scalp_bar_refresh", _refresh_scalp_bars),
        # Compatibility migration only: retires the old private external ledger. External
        # certificates themselves run below in shadow_forward, so there is one evidence clock
        # per identity rather than two competing ledgers with different freshness.
        ("external_state_reconcile", external_shadow.main),
        ("legacy_shadow", shadow_forward.main),
        ("scalp_shadow", scalp_shadow.main),
        ("qquant_shadow", qquant_shadow.main),
        ("promoter", promoter.main),
    ):
        try:
            result = fn()
            if isinstance(result, int) and not isinstance(result, bool) and result != 0:
                raise RuntimeError(f"returned non-zero status {result}")
        except Exception as exc:
            errors[name] = f"{type(exc).__name__}: {exc}"
            traceback.print_exc()

    # PRE-REGISTRATION STAMP, CENTRALIZED (RESEARCH §6d). Every live forward row must carry
    # `forward_start` from the moment it exists; a clock counted from the first trade ever taken
    # was letting selection-era evidence pose as forward evidence (36 rows measured 2026-08-26).
    # The stamp is applied HERE -- by the orchestrator that owns these files -- so every engine,
    # present and future, is covered by one code path instead of each reimplementing it (the
    # one-pipeline law). First-seen-now is the only defensible stamp; backdating is fabrication.
    for _sf in ("shadow_state.json", "scalp_shadow_state.json", "qquant_shadow_state.json"):
        _p = BASE / "reports" / "shadow" / _sf
        _d = _read(_p)
        _stamped = 0
        for _row in list(_d.values()) + list((_d.get("sleeves") or {}).values()):
            if (isinstance(_row, dict) and ("status" in _row or "n" in _row)
                    and not _terminal_status(_row.get("status"))
                    and not _row.get("forward_start")):
                _row["forward_start"] = datetime.now(UTC).isoformat()
                _stamped += 1
        if _stamped:
            _p.write_text(json.dumps(_d, indent=2), "utf-8")
            print(f"stamped forward_start on {_stamped} row(s) in {_sf}")

    legacy = _read(BASE / "reports" / "shadow" / "shadow_state.json")
    scalp = _read(BASE / "reports" / "shadow" / "scalp_shadow_state.json")
    qquant = _read(BASE / "reports" / "shadow" / "qquant_shadow_state.json")
    represented_legacy = {
        key for key, row in legacy.items()
        if isinstance(row, dict) and row.get("gate_admission") == "ORIGINAL_UNIVERSAL_10_PASS"
    }
    represented_scalp = set((scalp.get("sleeves") or {}).keys())
    represented_qquant = {
        key for key, row in qquant.items()
        if key.startswith("qquant.") and isinstance(row, dict)
    }
    rows = [legacy[key] for key in represented_legacy]
    rows += [(scalp.get("sleeves") or {})[key] for key in represented_scalp]
    rows += [qquant[key] for key in represented_qquant]
    active_rows = [row for row in rows if not _terminal_status(row.get("status"))]
    terminal_rows = [row for row in rows if _terminal_status(row.get("status"))]
    certified = (int(legacy.get("configured_sleeves", 0) or 0)
                 + int(scalp.get("configured_sleeves", 0) or 0)
                 + int(qquant.get("certified_qquant_sleeves", 0) or 0))
    recorded = len(rows)
    missing = [] if recorded >= certified else [f"{certified - recorded} certified sleeve(s)"]
    blocked = sum(row.get("status") in {"NO_DATA", "WAITING_FOR_FORWARD_BARS", "STALE_SOURCE",
                                         "BLOCKED_UNIVERSAL_GATES"}
                  for row in active_rows)
    # LIVE-ARM STATE, SURFACED HERE ON PURPOSE. `armed` lives in data/gateway_state.json,
    # box-local and gitignored -- no other brain (Hetzner, a future session, anyone without
    # a shell on this exact machine) can see it any other way. This file is the one artifact
    # already pushed to Hetzner every 15 minutes by MT5-ShadowSync (sync_shadow_to_vps.ps1
    # tars up reports/shadow verbatim), so riding it costs no new sync plumbing. READ ONLY:
    # this never writes gateway_state.json or sleeves.json -- arming stays the human's act,
    # this only makes the CURRENT fact visible everywhere the health report already goes.
    gw = _read(BASE / "data" / "gateway_state.json")
    sleeves_doc = _read(BASE / "data" / "sleeves.json")
    live_sleeves = [s.get("name") for s in (sleeves_doc.get("sleeves") or [])
                    if isinstance(s, dict) and s.get("status") == "LIVE"]
    health = {
        "updated_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "configured_sleeves": len(active_rows),
        "represented_sleeves": len(active_rows),
        "certified_sleeves_total": certified,
        "retired_shadow_sleeves": len(terminal_rows),
        "quarantined_uncertified_candidates": (
            int(legacy.get("gate_blocked_sleeves", 0) or 0)
            + int(scalp.get("gate_blocked_sleeves", 0) or 0)
        ),
        "sleeves_with_forward_trades": sum(
            int(row.get("n", 0) or 0) > 0 for row in active_rows
        ),
        "evidence_blocked_sleeves": blocked,
        "missing_sleeves": missing,
        "errors": errors,
        "seconds": round((datetime.now(UTC) - started).total_seconds(), 3),
        "gateway_armed": bool(gw.get("armed", False)),
        "promoted_live_sleeves": live_sleeves,
    }
    if missing or errors:
        health["status"] = "FAILED"
    elif blocked:
        health["status"] = "EVIDENCE_BLOCKED"
    else:
        health["status"] = "OPERATING"
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(health, indent=2), "utf-8")
    print(json.dumps(health, indent=2))
    return health, {"OPERATING": 0, "EVIDENCE_BLOCKED": 2}.get(health["status"], 1)


def main() -> int:
    return run()[1]


if __name__ == "__main__":
    raise SystemExit(main())
