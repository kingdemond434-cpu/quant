# CANON COPY of the trading box's C:\opt\quant-ops\e8_window_guard.py (2026-10-21), ported
# verbatim: below this comment block the file is byte-identical to the box original once its CRLF
# line endings are normalised to LF (box sha256 c72dcb88...f6e8, CRLF). Every path is absolute and
# the script puts C:\opt\quant\desks\mt5 and C:\opt\quant on sys.path itself, so it runs unchanged
# from desks\mt5\scripts\watchers\ (task MT5-E8WindowGuard, cwd C:\opt\quant;
# installer desks\mt5\scripts\install_box_watchers_canon.ps1).
# KNOWN AND DELIBERATELY NOT FIXED IN THE PORT (behaviour kept identical):
#   - `since` is hard-coded to the guard's arming time "2026-10-20T23:30" (a string compared with
#     each log line's first 16 chars); it never advances.
#   - the docstring is stale: argv[1] is never read; handled ids persist in
#     desks\mt5\data\e8_window_guard_state.json, seeded with two ids when that file is unreadable.
"""Interim fail-open guard (coordinator item, approved by zuck's Allow): E8 gold london_am and
afternoon are pinned to 0 in CERT_BOOK_LIVE. If either window PLACES anyway, cancel those exact
resting entry order ids. Never an asia order, never a position. Read-only unless such a line appears.
argv[1] = comma-separated ids already handled (so a re-run never re-acts)."""
import json
import re
import sys
import time
from datetime import datetime, timezone

LOG = r"C:\opt\quant\desks\mt5\logs\e8_gold.log"
since = "2026-10-20T23:30"   # the guard's arming time: only placements after the windows were pinned to 0
STATE = r"C:\opt\quant\desks\mt5\data\e8_window_guard_state.json"
try:
    done = set(json.load(open(STATE, encoding="utf-8")).get("handled", []))
except Exception:
    done = {360287970214366177, 360287970214366181}


def save():
    json.dump({"handled": sorted(done)}, open(STATE, "w", encoding="utf-8"))
pat = re.compile(r"^(\S+) \[(london_am|afternoon)\] PLACED (buy|sell)_stop ([\d.]+) XAUUSD @ ([\d.]+) sl ([\d.]+).*-> order (\d+)")
hits = []
for line in open(LOG, encoding="utf-8", errors="replace"):
    if line[:16] < since:
        continue
    m = pat.match(line)
    if m and int(m.group(7)) not in done:
        hits.append({"at": m.group(1), "window": m.group(2), "side": m.group(3), "lot": m.group(4), "id": int(m.group(7))})
if not hits:
    print("OK", datetime.now(timezone.utc).isoformat(timespec="seconds"), "no london_am/afternoon PLACED since", since)
    sys.exit(0)

print("ALERT", datetime.now(timezone.utc).isoformat(timespec="seconds"), "pinned-0 window PLACED:", hits)
sys.path[:0] = [r"C:\opt\quant\desks\mt5", r"C:\opt\quant"]
import logging
logging.disable(logging.ERROR)
try:
    from libs.ops.alert_channels import send_all
    r = send_all("E8 FAIL-OPEN: pinned window placed",
                 f"E8 placed {len(hits)} order(s) in london_am/afternoon although the cert book has them at 0. "
                 "The guard is cancelling the resting ones now.")
    print("  PAGE ->", {k: r.get(k) for k in ("armed", "delivered")})
except Exception as e:
    print("  PAGE failed:", type(e).__name__)
from mt5desk.kelly_sizing import load_cert_book
from pathlib import Path
print("  cert book e8 now:", load_cert_book(Path(r"C:\opt\quant\desks\mt5\data\CERT_BOOK_LIVE.json"), "e8"))
try:
    g = json.load(open(r"C:\opt\quant\desks\mt5\reports\E8_GOLD.json", encoding="utf-8"))
    print("  E8_GOLD:", g.get("at"), "cert_book_windows", g.get("cert_book_windows"), "sizing_source", g.get("sizing_source"))
except Exception as e:
    print("  E8_GOLD unreadable:", e)
from prop.tradelocker_venue import TradeLockerVenue
from mt5desk import order_door
raw = TradeLockerVenue().connect()
venue = order_door.guard_venue(raw, caller="window_guard_failopen", log=print)


def resting() -> set[int]:
    out = set()
    for o in raw.orders("XAUUSD"):
        for k in ("id", "orderId", "order_id"):
            if o.get(k) is not None:
                out.add(int(o[k]))
                break
    return out


for h in hits:
    oid = h["id"]
    if oid not in resting():
        print(f"  SKIP {h['window']} {h['side']}_stop {oid}: not resting (filled or gone) -- position NOT touched; REPORT")
        print("HANDLED", oid)
        done.add(oid); save()
        continue
    for attempt in range(1, 4):
        ok = venue.cancel(oid)
        time.sleep(2)
        still = oid in resting()
        print(f"  CANCEL {h['window']} {h['side']}_stop {oid} attempt {attempt}: api={ok} still_resting={still}")
        if not still:
            break
    else:
        print(f"  FAILED to cancel {oid} after 3 attempts")
    print("HANDLED", oid)
    done.add(oid); save()
try:
    from libs.ops.alert_channels import send_all
    send_all("E8 fail-open guard: done", f"Handled {len(hits)} pinned-window order(s); see MT5-E8WindowGuard.log.")
except Exception:
    pass
