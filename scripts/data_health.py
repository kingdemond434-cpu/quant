"""Data-pipeline health check + alerting feed.

Reports the freshness (age + distinct-day depth) of every archived dataset and the liveness of the
always-on heartbeats. Writes web/health.json for the dashboard (turns red when anything is stale)
and prints a one-line ALERT summary. A fragile pipeline thus gets caught early instead of
silently freezing (the mode that froze the OI archive at one snapshot).

    python scripts/data_health.py
"""

from __future__ import annotations

import json
import time
from datetime import UTC, datetime
from pathlib import Path

import pandas as pd

_OUT = Path("web/health.json")
# daily time-series dataset -> (path, timestamp-col, max age hours before STALE)
_DATASETS = {
    "oi_ls_taker": ("data/crypto_metrics.parquet", "ts", 36),
    "market_breadth": ("data/market_breadth.parquet", "ts", 36),
}
# JSON daily archives -> (path, date-key, max age hours before STALE)
_JSON_ARCHIVES = {
    "stablecoin_flows": ("data/stablecoin_flows_archive.json", "ts", 36),
    "fred_macro": ("data/fred_macro.json", "updated", 36),
}


# heartbeat alive but zero events this long -> the data pipe is almost certainly dead, not a quiet
# market (verified 2026-07-09: Binance mainnet WS handshakes OK but silently drops every data frame
# from this network -- 0 events/14 days on a stream that should fire continuously). Heartbeat
# liveness != data liveness.
_LIQ_STUCK_H = 24.0


def _liquidation_check() -> dict[str, object]:
    """Liquidations are a SPARSE event stream (not a daily dataset): report event count + the
    'listening since' clock + freshest event. LISTENING with 0 events is normal for the first
    _LIQ_STUCK_H hours (quiet market); past that with still-zero events, treat it as STUCK (alert)
    -- a broken data pipe looks identical to a quiet market on heartbeat alone."""
    liq, since_p, hb = (Path("data/liquidations.parquet"), Path("data/liquidation_since"),
                        Path("data/liquidation_heartbeat"))
    listening = hb.exists() and (time.time() - hb.stat().st_mtime) < 30 * 60
    events, latest = 0, None
    if liq.exists():
        ld = pd.read_parquet(liq)
        events = len(ld)
        if events:
            latest = pd.to_datetime(ld["ts"]).max().isoformat()
    since = since_p.read_text("utf-8").strip() if since_p.exists() else None
    since_h = None
    if since:
        since_dt = datetime.fromisoformat(since)
        since_h = (datetime.now(tz=UTC) - since_dt).total_seconds() / 3600
    if events > 0:
        status = "RECEIVING"
    elif listening and since_h is not None and since_h > _LIQ_STUCK_H:
        status = "STUCK"          # alive but structurally not receiving data -- treat as an alert
    elif listening:
        status = "LISTENING"
    else:
        status = "DOWN"
    return {"name": "liquidations", "status": status, "events": events,
            "since": since, "since_h": round(since_h, 1) if since_h is not None else None,
            "latest": latest}
# heartbeat -> (path, max minutes before DOWN)
_HEARTBEATS = {
    "cashcarry_executor": ("data/cashcarry_exec_heartbeat", 5),
    "liquidation_listener": ("data/liquidation_heartbeat", 30),
}


def main() -> None:
    now = datetime.now(tz=UTC)
    checks = []
    all_ok = True
    for name, (path, col, max_h) in _DATASETS.items():
        p = Path(path)
        if not p.exists():
            checks.append({"name": name, "status": "MISSING", "age_h": None, "days": 0})
            continue                                   # MISSING (not yet started) is not an alert
        df = pd.read_parquet(p)
        last = pd.to_datetime(df[col]).max()
        age_h = (now - last.to_pydatetime()).total_seconds() / 3600
        days = int(pd.to_datetime(df[col]).dt.date.nunique())
        status = "OK" if age_h <= max_h else "STALE"
        all_ok = all_ok and status == "OK"
        checks.append({"name": name, "status": status, "age_h": round(age_h, 1), "days": days})
    for name, (path, col, max_h) in _JSON_ARCHIVES.items():
        p = Path(path)
        if not p.exists():
            checks.append({"name": name, "status": "MISSING", "age_h": None, "days": 0})
            continue
        try:
            rows = json.loads(p.read_text("utf-8"))
            if not rows:
                checks.append({"name": name, "status": "EMPTY", "age_h": None, "days": 0})
                continue
            if isinstance(rows, dict):                    # dict-style archive (e.g. fred_macro):
                last = datetime.fromisoformat(str(rows[col]))   # timestamp at the top level;
                rows = rows.get("series", rows)                 # "days" = distinct sub-series
            else:
                last = datetime.fromisoformat(rows[-1][col])
            if last.tzinfo is None:
                last = last.replace(tzinfo=UTC)
            age_h = (now - last).total_seconds() / 3600
            days = len(rows)
            status = "OK" if age_h <= max_h else "STALE"
            all_ok = all_ok and status == "OK"
            checks.append({"name": name, "status": status, "age_h": round(age_h, 1), "days": days})
        except Exception as e:
            checks.append({"name": name, "status": "ERROR", "age_h": None, "days": 0,
                           "detail": repr(e)[:80]})
    liq = _liquidation_check()
    all_ok = all_ok and liq["status"] not in ("DOWN", "STUCK")
    checks.append(liq)
    hbs = []
    for name, (path, max_min) in _HEARTBEATS.items():
        p = Path(path)
        age_s = round(time.time() - p.stat().st_mtime) if p.exists() else None
        alive = age_s is not None and age_s < max_min * 60
        if name == "cashcarry_executor" and not alive:
            all_ok = False                             # executor down is the only hard alert
        hbs.append({"name": name, "alive": bool(alive), "age_s": age_s})
    # ORGANS visibility (2026-07-24 external-audit finding: health said all_ok while every AI
    # organ was dead -- this surface only ever covered datasets/heartbeats). organs_ok is shown
    # SEPARATELY, not folded into all_ok: the brain_noop pager already alarms on cycle death, so
    # folding would double-alert; blindness is ended by REPORTING, not re-alarming.
    organs = {}
    try:
        logs = sorted(Path("data/cro_ai_logs").glob("2026*_*.log"),
                      key=lambda q: q.stat().st_mtime)
        good = [q for q in logs if q.stat().st_size >= 2000]
        organs["last_cycle_success_h"] = (
            round((now.timestamp() - good[-1].stat().st_mtime) / 3600.0, 1) if good else None)
        organs["last_cycle_attempt_h"] = (
            round((now.timestamp() - logs[-1].stat().st_mtime) / 3600.0, 1) if logs else None)
    except Exception:
        pass
    organs_ok = bool(organs.get("last_cycle_success_h") is not None
                     and organs["last_cycle_success_h"] <= 26.0)
    out = {"updated": now.isoformat(), "all_ok": all_ok, "organs_ok": organs_ok,
           "organs": organs, "datasets": checks, "heartbeats": hbs}
    _OUT.parent.mkdir(parents=True, exist_ok=True)
    _OUT.write_text(json.dumps(out, indent=2), "utf-8")
    flag = "OK" if all_ok else "ALERT"

    def _amt(c: dict[str, object]) -> str:
        return f"{c['events']}ev" if "events" in c else f"{c.get('days', 0)}d"
    print(f"[{flag}] " + " | ".join(
        f"{c['name']}:{c['status']}({_amt(c)})" for c in checks) + " || " + " ".join(
        f"{h['name']}:{'up' if h['alive'] else 'DOWN'}" for h in hbs))


if __name__ == "__main__":
    main()
