#!/usr/bin/env python3
"""Page the principal when the live MT5 desk stops trading or loses money fast.

WHY THIS EXISTS (audit 2026-09-25). Nothing on the trading box could tell the principal that
the gateway had stopped, that equity was falling, or that a pause/refusal had silently switched
new risk off: `scripts/run_alerts.py` checks crypto-era signals only and no box task runs it,
`MT5-FusionDeadmanDryRun` sends nothing, and the deadman switch still polls Binance testnet.
The live state files then stopped reaching GitHub for nine days, and nobody was told.

WHAT IT CHECKS, each from a file the gateway itself writes every pass:
  * GATEWAY SILENT  -- `desks/mt5/data/gateway_state.json` not rewritten for SILENT_MIN minutes
                       while gold is trading (Sun 22:00 -> Fri 21:00 UTC, less the daily break);
  * EQUITY DROP     -- equity down DAY_DROP of the day's first reading, or PEAK_DROP from the
                       running peak this script has seen;
  * PAUSED          -- `desks/mt5/data/GATEWAY_PAUSED` present (new risk refused);
  * NO NEW RISK     -- `desks/mt5/data/release_identity.json` says `ok: false` (every new order
                       refused until the release is re-sealed).
Each condition pages at most once per REPEAT_H hours. Delivery is `libs.ops.alert_channels`
(every armed channel, delivery ledger); with no channel armed the verdict is still written and
says UNARMED -- an unarmed pager is a recorded state, never silence.

It never trades, closes, pauses or edits anything but its own two files.
Artifact: desks/mt5/reports/live_alive.json. State: desks/mt5/data/live_alive_state.json.
"""
from __future__ import annotations

import json
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DESK = ROOT / "desks" / "mt5"
GW_STATE = DESK / "data" / "gateway_state.json"
PAUSED = DESK / "data" / "GATEWAY_PAUSED"
RELEASE_ID = DESK / "data" / "release_identity.json"
STATE = DESK / "data" / "live_alive_state.json"
ARTIFACT = DESK / "reports" / "live_alive.json"

SILENT_MIN = 30.0
DAY_DROP = 0.05
PEAK_DROP = 0.10
REPEAT_H = 6.0


def gold_is_trading(now: datetime) -> bool:
    """XAUUSD trades Sunday 22:00 to Friday 21:00 UTC with a daily 21:00-22:00 break.

    Deliberately generous at the edges (it only decides whether SILENCE is suspicious): the
    venue's own session shifts an hour with US daylight time, so the break is treated as the
    whole 21:00-22:59 UTC span and Sunday opens at 23:00.
    """
    wd, h = now.weekday(), now.hour
    if wd == 5:
        return False
    if wd == 6:
        return h >= 23
    if wd == 4 and h >= 21:
        return False
    return not (21 <= h < 23)


def _read_json(p: Path) -> dict[str, Any] | None:
    try:
        v = json.loads(p.read_text(encoding="utf-8"))
        return v if isinstance(v, dict) else None
    except (OSError, ValueError):
        return None


def evaluate(now: datetime, state: dict[str, Any], *, gw_state: dict[str, Any] | None,
             gw_mtime: float | None, paused: bool,
             release: dict[str, Any] | None) -> tuple[list[tuple[str, str]], dict[str, Any]]:
    """Pure: (conditions [(key, message)], new state). No I/O, so every branch is testable."""
    st = dict(state)
    conds: list[tuple[str, str]] = []
    if gold_is_trading(now):
        if gw_mtime is None:
            conds.append(("silent", "gateway_state.json is missing: the gateway has never "
                                    "written its state on this box, or it was deleted"))
        else:
            age_min = (now.timestamp() - gw_mtime) / 60.0
            if age_min > SILENT_MIN:
                conds.append(("silent", f"gateway silent {age_min:.0f} min while gold is "
                                        f"trading (last state write "
                                        f"{datetime.fromtimestamp(gw_mtime, UTC):%Y-%m-%d %H:%M}"
                                        f" UTC)"))
    eq = None
    if gw_state is not None:
        try:
            eq = float(gw_state.get("equity") or 0.0)
        except (TypeError, ValueError):
            eq = None
    if eq is not None and eq > 0:
        day = now.date().isoformat()
        if st.get("day") != day:
            st["day"], st["day_start_equity"] = day, eq
        st["peak_equity"] = max(float(st.get("peak_equity") or 0.0), eq)
        start = float(st.get("day_start_equity") or eq)
        peak = float(st["peak_equity"])
        if start > 0 and eq <= start * (1.0 - DAY_DROP):
            conds.append(("day_drop", f"equity {eq:.2f} is {1 - eq / start:.1%} below today's "
                                      f"first reading {start:.2f}"))
        if peak > 0 and eq <= peak * (1.0 - PEAK_DROP):
            conds.append(("peak_drop", f"equity {eq:.2f} is {1 - eq / peak:.1%} below its peak "
                                       f"{peak:.2f}"))
        st["last_equity"] = eq
    if paused:
        conds.append(("paused", "GATEWAY_PAUSED is present: every new order is refused "
                                "(open positions are still managed)"))
    if release is not None and release.get("ok") is False:
        conds.append(("release_refused", "release identity refuses NEW risk: "
                                         + str(release.get("reason") or "")[:240]))
    return conds, st


def due(key: str, now: datetime, st: dict[str, Any]) -> bool:
    last = (st.get("paged") or {}).get(key)
    if not last:
        return True
    try:
        return now - datetime.fromisoformat(last) >= timedelta(hours=REPEAT_H)
    except ValueError:
        return True


def main(argv: list[str] | None = None) -> int:
    now = datetime.now(tz=UTC)
    state = _read_json(STATE) or {}
    gw_mtime = GW_STATE.stat().st_mtime if GW_STATE.exists() else None
    conds, st = evaluate(now, state, gw_state=_read_json(GW_STATE), gw_mtime=gw_mtime,
                         paused=PAUSED.exists(), release=_read_json(RELEASE_ID))
    delivery: dict[str, Any] = {"armed": None, "delivered": 0}
    to_page = [(k, m) for k, m in conds if due(k, now, st)]
    if to_page:
        sys.path.insert(0, str(ROOT))
        try:
            from libs.ops import alert_channels as ac
            body = "\n".join(f"- {m}" for _, m in to_page)
            delivery = ac.send_all("MT5 desk: " + ", ".join(k for k, _ in to_page), body,
                                   config=ROOT / "data" / "secrets" / "alert_channels.json",
                                   ledger=ROOT / "data" / "alert_delivery.jsonl")
        except Exception as exc:                         # the verdict is still written below
            delivery = {"armed": None, "delivered": 0, "error": f"{type(exc).__name__}: {exc}"}
        if delivery.get("delivered"):
            paged = dict(st.get("paged") or {})
            for k, _ in to_page:
                paged[k] = now.isoformat()
            st["paged"] = paged
    verdict = ("OK" if not conds else
               "UNARMED" if delivery.get("armed") == 0 else
               "PAGED" if delivery.get("delivered") else
               "ALERTING" if not to_page else "DELIVERY_FAILED")
    out = {"checked_at": now.isoformat(), "verdict": verdict,
           "conditions": [{"key": k, "message": m} for k, m in conds],
           "paged_now": [k for k, _ in to_page] if delivery.get("delivered") else [],
           "delivery": {k: v for k, v in delivery.items() if k != "results"},
           "gold_trading": gold_is_trading(now)}
    for path, doc in ((STATE, st), (ARTIFACT, out)):
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(doc, indent=1, default=str), encoding="utf-8")
        except OSError as exc:
            print(f"live_alive: could not write {path.name}: {exc}", file=sys.stderr)
    print(f"live_alive: {verdict} {[k for k, _ in conds]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
