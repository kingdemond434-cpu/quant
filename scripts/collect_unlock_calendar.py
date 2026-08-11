#!/usr/bin/env python3
"""UNLOCK-CALENDAR COLLECTOR -- the recoverable half of the unlock screen's inputs (R0288).

Fetches defillama.com/unlocks (the s13-passed source the 2026-07-24 snapshot came from -- the
public page's __NEXT_DATA__, not the pro-gated api.llama.fi/emissions, which answers 402) and
appends first-seen events to data/unlock_calendar.jsonl with the supply OBSERVED AT COLLECTION.

WHY RECURRING: the snapshot's forward calendar expires 2026-08-23 and its `pct_circ_now` is a
look-ahead for every historical event. A future event captured HERE, before it happens, carries a
genuine point-in-time pct-of-float -- the conditioning variable the forced-supply mechanism needs
and the one thing a later re-scrape can never reconstruct. Pairs with
collect_circulating_supply.py, which accrues the denominator series daily.

Refusal path: a page-shape change, HTTP failure or empty parse exits non-zero with the error in
the status artifact -- zero new events from a healthy parse and a broken parse are different
claims and the status file says which happened (L1.57).

    python scripts/collect_unlock_calendar.py [--json]
"""
from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.request
from datetime import UTC, datetime
from pathlib import Path

_ROOT = Path("/home/quant/quant-platform")
if not _ROOT.exists():
    _ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from libs.ops.lawful import guard  # noqa: E402
from libs.research.unlock_calendar import append_new, extract_events, parse_next_data  # noqa: E402

URL = "https://defillama.com/unlocks"
STATUS = "data/unlock_calendar_status.json"


def _fetch(url: str) -> tuple[int, str]:
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (X11; Linux x86_64)"})
    with urllib.request.urlopen(req, timeout=60) as resp:
        return resp.status, resp.read().decode("utf-8", errors="replace")


def main() -> int:
    guard()
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    now = datetime.now(tz=UTC)
    status: dict[str, object] = {"run_utc": now.isoformat(), "url": URL}
    rc = 0
    try:
        code, html = _fetch(URL)
        status["http_status"] = code
        parsed = parse_next_data(html)
        events = extract_events(parsed["protocols"], now)
        n_new = append_new(events, _ROOT)
        future = [e for e in events if not e["retrospective"] and e["tokens"] is not None]
        status.update({
            "generated_at_sec": parsed["generated_at_sec"],
            "n_protocols": len(parsed["protocols"]),
            "n_events_seen": len(events),
            "n_new_appended": n_new,
            "n_forward_cliffs": len(future),
            "forward_horizon_utc": (
                datetime.fromtimestamp(max(e["ts"] for e in future), tz=UTC).isoformat()
                if future else None),
            "status": "OK",
            "measured": True,
        })
    except (urllib.error.URLError, urllib.error.HTTPError, ValueError, OSError) as exc:
        # 402/403 would mean the free page joined the paid API behind the paywall -- record the
        # encounter so the free-replacement hunt gets a target instead of a silent gap.
        code = getattr(exc, "code", None)
        if code in (402, 403):
            from libs.data.paywall import record
            record(URL, status=code, unlocks="forward unlock calendar with point-in-time "
                   "pct-of-float (forced-supply conditioning variable)", body=str(exc))
        status.update({"status": "UNMEASURED", "measured": False,
                       "error": f"{type(exc).__name__}: {exc}"})
        rc = 1

    out = _ROOT / STATUS
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(status, indent=1) + "\n", "utf-8")
    print(json.dumps(status, indent=1) if args.json else
          f"unlock-calendar: {status.get('n_new_appended', 0)} new event(s), "
          f"{status.get('n_forward_cliffs', 0)} forward cliff(s)"
          + (f" -- ERROR {status['error']}" if "error" in status else ""))
    return rc


if __name__ == "__main__":
    sys.exit(main())
