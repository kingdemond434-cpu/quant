# CANON COPY of the trading box's C:\opt\quant-ops\ftmo_follow.py (2026-10-21), ported verbatim:
# below this comment block the file is byte-identical to the box original once its CRLF line
# endings are normalised to LF (box sha256 b657dfac..., CRLF). Every path is absolute and the
# script puts C:\opt\quant\desks\mt5 and C:\opt\quant on sys.path itself, so it runs unchanged from
# desks\mt5\scripts\watchers\ (task MT5-FTMOFollow, cwd C:\opt\quant;
# installer desks\mt5\scripts\install_box_watchers_canon.ps1).
# KNOWN AND DELIBERATELY NOT FIXED IN THE PORT (behaviour kept identical):
#   - the docstring is stale: it names the 2026-10-21 bracket, but DAY is today's UTC date; the
#     open phase is stored as "open:<side>:<pid>", not "open:<side>"; and besides the four listed
#     STATUS values the script also prints STATUS DONE / STATUS OPEN, and none for "test".
"""FTMO manual-follow pager for the 2026-10-21 E8 gold_asia bracket. NOTIFY ONLY: no order calls.

argv[1]: phase -- "test" (send the armed page), "watch" (no fill paged yet), "open:<side>" (fill paged,
waiting for the close). Prints exactly one STATUS line: WAIT | FILLED <side> | CLOSED | NOTRADE <why>.
"""
import json
import math
import re
import sys
import logging

logging.disable(logging.ERROR)
sys.path[:0] = [r"C:\opt\quant\desks\mt5", r"C:\opt\quant"]
from datetime import datetime, timezone
DAY = datetime.now(timezone.utc).strftime("%Y-%m-%d")
RISK_USD = 900.0
OZ = 100.0
LOG = r"C:\opt\quant\desks\mt5\logs\e8_gold.log"
STATE = r"C:\opt\quant\desks\mt5\data\ftmo_follow_state.json"
try:
    _st = json.load(open(STATE, encoding="utf-8"))
except Exception:
    _st = {}
if _st.get("day") != DAY:
    _st = {"day": DAY, "phase": "watch"}
phase = sys.argv[1] if len(sys.argv) > 1 else _st["phase"]
if phase == "done":
    print("STATUS DONE"); sys.exit(0)


def setphase(p):
    _st["phase"] = p
    json.dump(_st, open(STATE, "w", encoding="utf-8"))


def page(title: str, body: str) -> None:
    from libs.ops.alert_channels import send_all
    r = send_all(title, body)
    print("PAGE", title, "->", {k: r.get(k) for k in ("armed", "delivered")})


if phase == "test":
    page("FTMO follow alert armed", "FTMO manual-follow alert is armed for today's E8 gold asia bracket. "
         "You will get one page if a leg fills, and one when it closes. Notify only.")
    sys.exit(0)

placed, filled, cancelled = {}, [], []
pat = re.compile(r"^(\S+) \[asia\] PLACED (buy|sell)_stop ([\d.]+) XAUUSD @ ([\d.]+) sl ([\d.]+) tp ([\d.]+) -> order (\d+)")
for line in open(LOG, encoding="utf-8", errors="replace"):
    if not line.startswith(DAY):
        continue
    m = pat.match(line)
    if m:
        placed[m.group(2)] = {"entry": float(m.group(4)), "sl": float(m.group(5)), "tp": float(m.group(6))}
    m = re.match(r"^\S+ \[asia\] (buy|sell)_stop filled -> position (\d+)", line)
    if m:
        filled.append((m.group(1), int(m.group(2))))
    if re.match(r"^\S+ \[asia\] (ttl_cancel|eod_cancel)", line):
        cancelled.append(line[:40])

if phase == "watch":
    if len({s for s, _ in filled}) > 1:
        page("FTMO: NO TRADE TODAY", "E8 state unclear (both asia legs show fills). Do not follow.")
        setphase("done"); print("STATUS NOTRADE both_filled"); sys.exit(0)
    if not filled:
        if cancelled and len(cancelled) >= len(placed) > 0:
            page("FTMO: NO TRADE TODAY", "E8 asia bracket expired without a fill.")
            setphase("done"); print("STATUS NOTRADE expired"); sys.exit(0)
        print("STATUS WAIT"); sys.exit(0)
    side, pid = filled[0]
    p = placed.get(side)
    from prop.tradelocker_venue import TradeLockerVenue
    pos = [x for x in TradeLockerVenue().connect().positions() if int(x.get("id") or x.get("positionId") or 0) == pid]
    fill = float(pos[0].get("avgPrice") or pos[0].get("openPrice") or 0) if pos else 0.0
    if not p or not fill:
        page("FTMO: NO TRADE TODAY", "E8 state unclear (fill price or bracket unreadable). Do not follow.")
        setphase("done"); print("STATUS NOTRADE unreadable"); sys.exit(0)
    stop_pts = abs(fill - p["sl"]); tp_pts = abs(p["tp"] - fill)
    lot = math.floor(RISK_USD / (stop_pts * OZ) / 0.01) * 0.01
    d = "BUY" if side == "buy" else "SELL"
    body = (f"FTMO GOLD: {d} XAUUSD {lot:.2f} lots now at market. SL {stop_pts:.2f} pts from your fill "
            f"(about {p['sl']:.2f}), TP {tp_pts:.2f} pts (about {p['tp']:.2f}). E8 filled {fill:.2f}. "
            f"Risk about $900 at 100 oz/lot. Close if E8 closes (you will get a page).")
    page(f"FTMO GOLD {d} {lot:.2f}", body)
    setphase(f"open:{side}:{pid}"); print("STATUS FILLED", side, pid); sys.exit(0)

if phase.startswith("open:"):
    side, pid = phase.split(":")[1], int(phase.split(":")[2])
    from prop.tradelocker_venue import TradeLockerVenue
    still = [x for x in TradeLockerVenue().connect().positions() if int(x.get("id") or x.get("positionId") or 0) == pid]
    if still:
        print("STATUS OPEN"); sys.exit(0)
    page("FTMO: CLOSE YOUR GOLD TRADE", f"The E8 gold {side.upper()} position has closed. Close the FTMO trade now if it is still open.")
    setphase("done"); print("STATUS CLOSED"); sys.exit(0)
