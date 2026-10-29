"""ALERT CANARY -- proves the pager is alive BEFORE an incident needs it (gap #38).

The pager has died silently twice: quota exhaustion 2026-07-11 -> 07-16 (five days invisible) and
a latin-1 header encode 07-19 (39/39 pushes failed for 29h, across a live dead-man fire). Both
times the desk learned about it afterwards. The reason is structural: alerts only fire on
incidents, so an alert path that is broken between incidents looks exactly like a quiet desk.

This sends a low-priority synthetic page on a throttled cadence and then AUDITS THE LEDGER: if no
channel has recorded a delivery inside the lookback, it writes `data/ALERT_CHANNELS_SILENT` and
exits nonzero, so cron/systemd surfaces it. The flag is cleared automatically on the next
successful delivery -- a stale flag would be its own silent failure.

THE OFF-BOX HALF IS NOT THIS SCRIPT, and the distinction matters: this proves the desk can SEND.
Only an external watcher noticing the canary stopped ARRIVING proves delivery end to end -- that
is the healthchecks.io check of gap #17 (box liveness), which is configured separately. Neither
substitutes for the other and this script does not claim to.

    python scripts/run_alert_canary.py [--interval-h 6] [--lookback-h 24] [--force]
"""

from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from libs.ops.alert_channels import (
    all_silent_since,
    clear_desk_alert,
    personal_channel_health,
    record_desk_alert,
    send_all,
    status,
)

_STATE = Path("data/alert_canary_state.json")
_SILENT_FLAG = Path("data/ALERT_CHANNELS_SILENT")
_NTFY_SECRET = Path("data/secrets/ntfy.json")
#: desk alert key for a personal channel that is no longer proven to deliver
PERSONAL_STALE_KEY = "personal_channel_stale:ntfy"


def sent_count(res: dict[str, Any] | None) -> int | str:
    """Real deliveries only. A ROUTED row (a personal channel the desk canary is kept off) is
    counted in send_all's `delivered` for dedupe, but it delivered nothing, so it is not 'sent'."""
    if not res:
        return "throttled"
    return int(res.get("delivered", 0)) - int(res.get("routed", 0))


def check_personal_channel(*, ntfy_known: bool | None = None) -> dict[str, Any]:
    """THE PHONE'S OWN LIVENESS, WITHOUT TOUCHING THE PHONE. ntfy now carries principal pages
    only, so between incidents nothing exercises it; a dead topic would surface on the one page
    that mattered. When its last real success is older than PERSONAL_STALE_DAYS (or a real attempt
    failed after it) this writes a DESK alert row -- a RED in DESK_ALERTS.json that
    check_desk_health surfaces -- and clears it once a real success lands. Never a page."""
    known = ntfy_known
    if known is None:
        known = _NTFY_SECRET.exists() or "ntfy" in status()["armed_kinds"]
    h = personal_channel_health("ntfy")
    if not known:
        return {**h, "stale": False, "why": "no ntfy topic configured on this box"}
    if h["stale"]:
        record_desk_alert(
            PERSONAL_STALE_KEY, "personal channel ntfy unproven",
            f"ntfy last real success {h['last_success'] or 'NEVER'}"
            f"{'; a real attempt failed after it' if h['failed_since'] else ''} -- older than "
            f"{h['days']:.0f}d. Desk pages never exercise it, so a principal page may not arrive: "
            "check data/alert_delivery.jsonl, the topic in data/secrets/ntfy.json, and ntfy.sh "
            "rate limits.", source="run_alert_canary")
    else:
        clear_desk_alert(PERSONAL_STALE_KEY)
    return h


def _due(interval_h: float, *, state: Path = _STATE) -> bool:
    try:
        last = datetime.fromisoformat(json.loads(state.read_text("utf-8"))["last_canary"])
    except (OSError, json.JSONDecodeError, KeyError, ValueError):
        return True
    return datetime.now(tz=UTC) - last >= timedelta(hours=interval_h)


def _stamp(state: Path = _STATE) -> None:
    state.parent.mkdir(parents=True, exist_ok=True)
    state.write_text(json.dumps({"last_canary": datetime.now(tz=UTC).isoformat()}), "utf-8")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--interval-h", type=float, default=6.0,
                    help="minimum hours between canaries (throttle; default 6)")
    ap.add_argument("--lookback-h", type=float, default=24.0,
                    help="silence window: no delivery on ANY channel in this many hours = silent")
    ap.add_argument("--force", action="store_true", help="ignore the throttle")
    args = ap.parse_args()

    sent = None
    if args.force or _due(args.interval_h):
        # canary=True: channels with a non-notifying probe endpoint use it. Proving the route is
        # alive must not cost a page every 6h -- a canary that pages is a canary that gets muted,
        # and then it is protecting nothing.
        sent = send_all("quant canary",
                        f"synthetic canary {datetime.now(tz=UTC).isoformat()} -- "
                        "no action needed; this proves the alert path can deliver",
                        canary=True,
                        # DESK: a canary must never reach the phone. It still exercises the
                        # route through hc /log; the personal channels get a routed row.
                        audience="desk")
        _stamp()

    silent = all_silent_since(args.lookback_h)
    st = status()
    if silent:
        _SILENT_FLAG.parent.mkdir(parents=True, exist_ok=True)
        _SILENT_FLAG.write_text(
            f"{datetime.now(tz=UTC).isoformat()} no alert delivery on ANY channel in "
            f"{args.lookback_h:.0f}h (armed: {st['armed_kinds'] or 'NONE -- arming owed'})\n",
            "utf-8")
    elif _SILENT_FLAG.exists():
        _SILENT_FLAG.unlink()      # cleared on recovery; a stale flag is its own silent failure

    personal = check_personal_channel()
    print(f"alert canary: armed={st['armed']} {st['armed_kinds']} "
          f"sent={sent_count(sent)} silent_{args.lookback_h:.0f}h={silent} "
          f"ntfy_stale={personal['stale']}")
    if st["arming_owed"]:
        print("  NOT-ARMED (human step owed): drop credentials at "
              "data/secrets/alert_channels.json -- until then ntfy is the only path, which is "
              "the single point of failure gap #38 exists to remove")
    return 1 if silent else 0


if __name__ == "__main__":
    raise SystemExit(main())
