"""Fusion MT5 ruin rail -- WIRED 2026-08-26 by principal order (dry-run first, then --live).

Read this file, change the numbers you disagree with, then decide whether it runs. Nothing here
executes until a human schedules it, and it can NEVER open, resize or reverse a position -- it
only flattens and halts. `scripts/run_deadman_switch.py` (Tier-3, crypto-testnet, inert) is
untouched; if this proposal is accepted it REPLACES that rail's role rather than editing it.

WHY IT EXISTS: the account is ARMED and live (measured 2026-08-25: equity EUR 500, armed=true,
gold book trading) while the only existing rail watches retired Binance testnet endpoints. Live
MT5 risk currently has no automated backstop at all.

SETTINGS AS OF THIS DRAFT -- principal-set 2026-08-26 ("crank to maximum for safe-aggressive
growth"), with two DELIBERATE DEPARTURES argued inline. The rails split into two kinds and the
distinction is the whole design:

  RAILS THAT ONLY COST YOU WHEN THEY FALSE-TRIP  (position count, margin, size guard, weekly
  loss): widen these freely -- a rail that halts a healthy desk is pure lost compounding, and
  the REAL risk control is the heat budget, which already prices every leg by its own stop.

  RAILS THAT STAND BETWEEN YOU AND RUIN  (equity floor, daily loss): these are not widened for
  aggression. log(0) = -inf; one ruin ends all compounding. But note the direction of the
  correction below -- the naive "tight floor" is ALSO wrong, and for a growth reason.
"""
from __future__ import annotations

import json
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent          # desks/mt5
#: The repo root on sys.path so `libs.ops.provenance` (the ledger's account_key) imports.
if str(BASE.parent.parent) not in sys.path:
    sys.path.insert(0, str(BASE.parent.parent))
STATE = BASE / "data" / "gateway_state.json"
LEDGER = BASE / "data" / "live_ledger.jsonl"
#: The intent ledger: the lot the desk's own sizer sent, per order ticket. For a pending stop the
#: position id IS that ticket (gateway `_position_entry`'s key chain), so the size guard reads a
#: position's expected lot straight off it. Read-only here.
INTENTS = BASE / "data" / "order_intents.jsonl"
PAUSED = BASE / "data" / "GATEWAY_PAUSED"              # the gateway ALREADY honours this file
BREACH_LOG = BASE / "logs" / "fusion_deadman.log"
STAMP = BASE / "data" / "fusion_deadman_state.json"
#: THE PRINCIPAL'S ARMING MARKER (audit r5 must-fix 4). `--live` acts ONLY while this file exists
#: and reads {"armed_by": "zuck", ...}; it is gitignored, so no adoption, restore or session can
#: create it -- the principal writes it on the box. Without it a `--live` pass runs as DRY-RUN and
#: says so on the stamp; with it the dry-run task steps aside, so one stamp has one writer.
ARMED_MARKER = BASE / "data" / "FUSION_DEADMAN_ARMED.json"

#: THE BROKER DAY (r6, coordinator must-fix 2026-10-20). The daily-loss rail measured "today" from
#: UTC midnight, so between the server's midnight (17:00 New York = 21:00Z in summer) and 24:00Z a
#: new broker day was still judged on the previous one's losses -- the box's stamp at 22:20Z read
#: halt_codes [DAILY_LOSS] that way. The day is the SERVER's, by the convention this desk already
#: uses: `prop/e8_guard.server_day` (server midnight == 17:00 America/New_York) and the gateway's
#: tick-clock `day_key`, which is what `gateway_state.json`'s `day_start_equity.date` carries.
SERVER_ANCHOR_TZ = "America/New_York"
SERVER_MIDNIGHT_ET_HOUR = 17


def broker_day(now: datetime | None = None) -> str:
    """The broker (server) trading day at `now`, as YYYY-MM-DD."""
    from zoneinfo import ZoneInfo
    et = (now or datetime.now(tz=UTC)).astimezone(ZoneInfo(SERVER_ANCHOR_TZ))
    return (et + timedelta(hours=24 - SERVER_MIDNIGHT_ET_HOUR)).strftime("%Y-%m-%d")


def broker_day_start(now: datetime | None = None) -> datetime:
    """The UTC instant the current broker day began (the server's midnight)."""
    from zoneinfo import ZoneInfo
    tz = ZoneInfo(SERVER_ANCHOR_TZ)
    from datetime import date
    day = date.fromisoformat(broker_day(now))
    start_et = datetime.combine(day - timedelta(days=1), datetime.min.time(), tzinfo=tz) \
        .replace(hour=SERVER_MIDNIGHT_ET_HOUR)
    return start_et.astimezone(UTC)

# ---------------------------------------------------------------- RAILS
#: PRINCIPAL-SET. ~8 full-risk losers at the account's realised q -- a legitimately bad day stays
#: under it, a broken day trips it. The 5% first draft was measured against the desk's own
#: drawdown ladder and rejected: it would halt the desk on days the strategy is designed to lose.
DAILY_LOSS_PCT = 0.10

#: DEPARTURE 1 -- LOWER than the 30% first draft, and lower FOR GROWTH, not against it.
#: The book's worst measured 3-leg drawdown is -33.7R; at the realised risk this account runs,
#: that is a ~40%+ equity drawdown INSIDE NORMAL BEHAVIOUR. A 30% floor would therefore halt the
#: desk permanently during a drawdown it was built to survive -- guaranteeing it never compounds
#: back out. The floor is instead placed where the account stops being able to trade its own
#: policy: PROMOTED_MIN_EQUITY (EUR 300), the desk's own "cannot size properly below this" line.
#: Below that the venue's 0.01 lot minimum dictates risk and the policy is fiction.
EQUITY_FLOOR_EUR = 300.0

#: Must exceed the daily cap or it is decoration: ~2 maximum bad days.
WEEKLY_LOSS_PCT = 0.20

#: A LOOP DETECTOR, NOT A RISK CONTROL -- and the distinction is why this number is high.
#: Concurrent RISK is capped by heat_budget() (Q_OPT x legs, scaled by sqrt(k_eff) to the 15%
#: ceiling), which prices every leg by its own stop; a position COUNT cap on top of that caps
#: BREADTH, and breadth is the growth lever (five orthogonal sleeves at 3% beat one at 10%).
#: Raised 12 -> 24 (principal 2026-08-26, max-growth): 3 gold legs + up to 12 forward slots +
#: promoted family sleeves can legitimately reach the high teens, so 24 fires only when
#: something has genuinely looped. If this ever binds on a healthy book, RAISE IT -- the heat
#: budget is what must say no, not an arbitrary integer.
MAX_OPEN_POSITIONS = 24

#: Free margin as a fraction of equity. Widened from 40% -> 25%: this exists to trip BEFORE the
#: broker's stop-out, not to cap breadth, and 25% still leaves a wide gap to any stop-out level.
MIN_FREE_MARGIN_FRAC = 0.25

#: Bug-catcher for the sizing engine, widened 2x -> 3x so honest volatility never trips it.
#: A position more than 3x what mt5desk.sizing would have returned is a defect, not a decision.
MAX_SIZE_MULTIPLE = 3.0

#: DEPARTURE 2 -- TIGHTER than the 90 min first draft. "Crank to maximum" on a pure-safety rail
#: means tighter, because staleness has NO growth cost: a gateway that has not reconciled while
#: positions are open is unmanaged risk, and 45 minutes is already 3 missed 15-minute passes.
STALE_HEARTBEAT_MIN = 45

#: Consecutive breach observations before acting. One bad read (a stale file mid-write, a
#: momentary broker disconnect) must not flatten a healthy book; two consecutive reads of the
#: same breach is evidence, not noise.
CONFIRM_READS = 2

# ------------------------------------------------------- AUTO RE-ARM (fully automatic, always)
#: PRINCIPAL 2026-08-26: re-arming is AUTOMATIC, ALWAYS. No breach ever waits on a person.
#: The earlier "human-only" tier was conservatism standing where an OBJECTIVE MEASUREMENT
#: already exists: every rail below has a condition that is observably true or false, so "is it
#: fixed?" is a READING, never an opinion. A desk halted because nobody was awake is lost
#: compounding wearing a safety costume (LAWS S2a), and a rail that needs a human is a rail that
#: fails precisely when the human is asleep.
#:
#: THE SAFETY IS NOT THE HUMAN -- IT IS THE CLEAR CONDITION. Nothing resumes while its own
#: breach is still true, and each entry names what "cleared" means for it:
AUTO_REARM = {
    "STALE_GATEWAY": "gateway is reconciling again",
    "MARGIN": "free margin recovered above the floor",
    "POSITION_COUNT": "open positions fell back within the loop-detector",
    "DAILY_LOSS": "a new trading day began",
    "WEEKLY_LOSS": "a new trailing week began",
    "EQUITY_FLOOR": "equity recovered above the floor (with hysteresis)",
    "SIZE_GUARD": "no open position exceeds the sizing multiple",
}

#: HYSTERESIS ON THE RUIN RAIL. Equity must recover to floor x this, not merely touch it:
#: re-arming at EUR 300.01 would oscillate the account across its own floor all day. The CLEAR
#: condition is deliberately harder than the BREACH condition, which is what kills a boundary
#: flap without anyone watching it.
EQUITY_REARM_HYSTERESIS = 1.05

#: Base cooldown after the condition clears. One clean read is not a recovery.
REARM_COOLDOWN_MIN = 30

#: EXPONENTIAL BACKOFF REPLACES HUMAN ESCALATION -- this is the load-bearing part. Re-arm #1
#: waits 30min, #2 60, #3 120, #4 240 ... capped below, counted per breach code over a rolling
#: 24h. A rail that re-arms into the same breach forever is switched off with extra steps, but
#: the answer to that is a LONGER WAIT, not a person: a genuine repeat failure costs
#: progressively more while a one-off recovers fast -- and it works at 04:00 on a Sunday.
REARM_COOLDOWN_CAP_MIN = 12 * 60


def log(msg: str) -> None:
    line = f"{datetime.now(tz=UTC).isoformat(timespec='seconds')} {msg}"
    BREACH_LOG.parent.mkdir(parents=True, exist_ok=True)
    with BREACH_LOG.open("a", encoding="utf-8") as f:
        f.write(line + "\n")
    print(line)


def _read(p: Path, default):
    try:
        return json.loads(p.read_text("utf-8"))
    except (OSError, ValueError):
        return default


def ledger_rows() -> list[dict]:
    if not LEDGER.exists():
        return []
    out = []
    for line in LEDGER.read_text("utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            r = json.loads(line)
        except ValueError:
            continue
        if isinstance(r, dict):
            out.append(r)
    return out


#: The box's declared Fusion live login (gitignored; decision_core.FUSION_ACCOUNT_FILE) and its
#: server: the ledger rows this rail judges are THAT account's live rows and nothing else.
FUSION_ACCOUNT = BASE / "data" / "FUSION_LIVE_ACCOUNT.json"
FUSION_LIVE_SERVER = "FusionMarkets-Live"


def ledger_checked(path: Path | None = None,
                   account_path: Path | None = None) -> tuple[list[dict] | None, str]:
    """(the declared Fusion LIVE account's ledger rows, why) -- or (None, why) when that cannot be
    MEASURED (audit r6: an absent ledger read as zero loss). None when the ledger is absent or
    unreadable, a line other than a torn LAST line does not parse, or the box declares no Fusion
    login. Rows are filtered to `account == login`, `server == FUSION_LIVE_SERVER` and
    `account_kind == "live"`; an empty filtered list IS a measurement (no trade yet)."""
    p = path or LEDGER
    ap = account_path or FUSION_ACCOUNT
    try:
        decl = json.loads(ap.read_text(encoding="utf-8-sig"))
        login = decl.get("login") if isinstance(decl, dict) else None
        if isinstance(login, bool) or not isinstance(login, int) or login <= 0 \
                or decl.get("server") != FUSION_LIVE_SERVER:
            return None, f"{ap.name} declares no integer login on {FUSION_LIVE_SERVER}"
    except (OSError, ValueError) as exc:
        return None, f"{ap.name} absent or unreadable ({type(exc).__name__})"
    try:
        lines = p.read_text("utf-8").splitlines()
    except (OSError, ValueError) as exc:
        return None, f"{p.name} absent or unreadable ({type(exc).__name__}); loss UNMEASURED"
    rows: list[dict] = []
    key = _declared_key(login)
    body = [ln.strip() for ln in lines if ln.strip()]
    for i, line in enumerate(body):
        try:
            r = json.loads(line)
        except ValueError:
            if i == len(body) - 1:
                continue                          # a torn last line is a write in progress
            return None, f"{p.name} line {i + 1} does not parse; loss UNMEASURED"
        if key is None and isinstance(r, dict) and r.get("server") == FUSION_LIVE_SERVER \
                and "account" not in r and r.get("account_key"):
            return None, ("account_key rows present but the declared key is underivable; "
                          "loss UNMEASURED")
        if isinstance(r, dict) and r.get("account_kind") == "live" \
                and r.get("server") == FUSION_LIVE_SERVER and (
                    r.get("account") == login
                    or (key is not None and "account" not in r
                        and r.get("account_key") == key)):
            rows.append(r)
    return rows, f"{len(rows)} live row(s) of the declared Fusion account in {p.name}"


def _declared_key(login: int) -> str | None:
    """The HMAC `account_key` the ledger writer stamps since publish_sync v5, for the declared
    login -- or None when it cannot be derived (no provenance, no box key). MEASURED 2026-10-29:
    every live row from 2026-10-23 on carries `account_key` and no raw `account`, so a filter on
    `account == login` alone read the whole trailing week as zero realised loss."""
    try:
        from libs.ops import provenance
        key = provenance.account_key(login, FUSION_LIVE_SERVER, create=False)
    except Exception:
        return None
    return key if isinstance(key, str) and key.startswith("sha256:") else None


def realised_pl_since(rows: list[dict], since: datetime) -> float:
    total = 0.0
    for r in rows:
        try:
            ts = datetime.fromisoformat(str(r.get("time", "")).replace("Z", "+00:00"))
        except ValueError:
            continue
        if ts >= since:
            total += float(r.get("pl_quote", 0.0) or 0.0)
    return total


def intent_rows(path: Path | None = None) -> list[dict]:
    p = INTENTS if path is None else path
    if not p.exists():
        return []
    out = []
    for line in p.read_text("utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            r = json.loads(line)
        except ValueError:
            continue
        if isinstance(r, dict):
            out.append(r)
    return out


def expected_lots(intents: list[dict]) -> dict[int, float]:
    """Order ticket -> the lot the desk's own sizer sent, from the intent ledger. A ticket with
    no lot, or no ticket at all, is not a reading and is left out."""
    out: dict[int, float] = {}
    for r in intents:
        try:
            ticket = int(r.get("ticket"))
            lot = float(r.get("lot"))
        except (TypeError, ValueError):
            continue
        if ticket and lot > 0:
            out[ticket] = lot
    return out


def size_guard(positions: list[dict], expected: dict[int, float] | None
               ) -> tuple[list[tuple[str, str]], dict[str, int]]:
    """THE SIZING BUG-CATCHER, measured against what the sizer actually sent.

    A position more than MAX_SIZE_MULTIPLE x the lot on its own intent is a defect, not a
    decision. A position whose ticket has no intent row cannot be judged and is counted as
    UNMEASURED rather than assumed right or wrong -- an absent ledger is never a clean bill.
    """
    breaches: list[tuple[str, str]] = []
    judged = unmeasured = 0
    for p in positions:
        try:
            ticket = int(p.get("ticket"))
            vol = float(p.get("volume") or 0.0)
        except (TypeError, ValueError):
            unmeasured += 1
            continue
        exp = (expected or {}).get(ticket)
        if exp is None or exp <= 0:
            unmeasured += 1
            continue
        judged += 1
        if vol > MAX_SIZE_MULTIPLE * exp:
            breaches.append(("SIZE_GUARD",
                             f"SIZE GUARD: position {ticket} holds {vol:g} lots, over "
                             f"{MAX_SIZE_MULTIPLE:g}x the {exp:g} its intent sized -- a defect, "
                             f"not a decision"))
    return breaches, {"judged": judged, "unmeasured": unmeasured}


def evaluate(account: dict, positions: list[dict], rows: list[dict],
             peak_equity: float, halt_codes: tuple = (),
             expected: dict[int, float] | None = None, *,
             now: datetime | None = None) -> list[tuple[str, str]]:
    """Pure function: state in, breach reasons out. Testable without MT5 attached.

    `expected` (order ticket -> the lot the sizer sent, see `expected_lots`) arms the size guard;
    without it no position is judged on size and none is assumed right.
    """
    breaches: list[tuple[str, str]] = []
    equity = float(account.get("equity", 0.0) or 0.0)
    now = now or datetime.now(tz=UTC)

    # HYSTERESIS: once halted on the floor, the account must climb back to floor x 1.05 before
    # this stops reporting a breach -- so the CLEAR condition is strictly harder than the BREACH
    # condition and the ruin rail cannot oscillate across its own boundary unattended.
    floor = (EQUITY_FLOOR_EUR * EQUITY_REARM_HYSTERESIS
             if "EQUITY_FLOOR" in (halt_codes or ()) else EQUITY_FLOOR_EUR)
    if equity > 0 and equity < floor:
        breaches.append(("EQUITY_FLOOR",
                         f"EQUITY FLOOR: {equity:.2f} < {floor:.2f} -- the account "
                         f"can no longer size its own policy"))

    # THE CURRENT BROKER DAY ONLY (r6): realised P/L since the server's midnight, and the
    # equity against THAT day's opening balance (the gateway's `day_start_equity` anchor, used
    # only when it is dated to this broker day -- a stale anchor is no opening balance).
    day = broker_day(now)
    day_start = broker_day_start(now)
    day_pl = realised_pl_since(rows, day_start)
    day_ref = max(peak_equity, equity)
    anchor = account.get("day_start_equity")
    opening = None
    if isinstance(anchor, dict) and anchor.get("date") == day:
        try:
            opening = float(anchor.get("equity"))
        except (TypeError, ValueError):
            opening = None
    if day_ref > 0 and day_pl < -DAILY_LOSS_PCT * day_ref:
        breaches.append(("DAILY_LOSS",
                         f"DAILY LOSS: {day_pl:.2f} beyond {DAILY_LOSS_PCT:.0%} of {day_ref:.2f} "
                         f"(broker day {day})"))
    elif opening and opening > 0 and equity > 0 \
            and equity <= opening * (1.0 - DAILY_LOSS_PCT):
        breaches.append(("DAILY_LOSS",
                         f"DAILY LOSS: equity {equity:.2f} is {DAILY_LOSS_PCT:.0%}+ below broker "
                         f"day {day}'s opening {opening:.2f}"))

    week_pl = realised_pl_since(rows, now - timedelta(days=7))
    if day_ref > 0 and week_pl < -WEEKLY_LOSS_PCT * day_ref:
        breaches.append(("WEEKLY_LOSS",
                         f"WEEKLY LOSS: {week_pl:.2f} beyond {WEEKLY_LOSS_PCT:.0%} of "
                         f"{day_ref:.2f}"))

    if len(positions) > MAX_OPEN_POSITIONS:
        breaches.append(("POSITION_COUNT",
                         f"POSITION COUNT: {len(positions)} > {MAX_OPEN_POSITIONS} -- runaway"))

    free_margin = float(account.get("margin_free", 0.0) or 0.0)
    if equity > 0 and free_margin > 0 and free_margin < MIN_FREE_MARGIN_FRAC * equity:
        breaches.append(("MARGIN",
                         f"MARGIN: free {free_margin:.2f} < {MIN_FREE_MARGIN_FRAC:.0%} of equity"))

    last = account.get("last_reconcile")
    # RESTING PENDINGS ARE RISK TOO (audit r5 should-fix): a stop entry that fills while the
    # gateway is not reconciling is unmanaged exactly like an open position.
    pendings = list(account.get("pending") or [])
    exposed = len(positions) + len(pendings)
    if exposed and not last:
        breaches.append(("STALE_GATEWAY",
                         f"STALE GATEWAY: no last_reconcile with {len(positions)} position(s) "
                         f"and {len(pendings)} pending order(s) -- treated as stale"))
    if exposed and last:
        try:
            age_min = (now - datetime.fromisoformat(str(last))).total_seconds() / 60
            if age_min > STALE_HEARTBEAT_MIN:
                breaches.append(("STALE_GATEWAY",
                                 f"STALE GATEWAY: {age_min:.0f}min since reconcile with "
                                 f"{len(positions)} position(s) open and {len(pendings)} "
                                 f"pending order(s) -- unmanaged risk"))
        except ValueError:
            breaches.append(("STALE_GATEWAY",
                             "STALE GATEWAY: last_reconcile unparseable -- treated as stale"))

    breaches += size_guard(positions, expected)[0]
    return breaches


def loss_rail_headroom(rows: list[dict] | None, peak_equity: float, equity: float,
                       peak_ts: str | None, *, now: datetime | None = None,
                       opening: dict | None = None) -> dict:
    """What the two realised-loss rails are measured against, and how far each is from tripping.

    Mirrors `evaluate` EXACTLY and changes nothing it decides: the anchor of both rails is
    `max(peak_equity, equity)` (the stamp's high-water mark of EQUITY, floating included), the
    weekly window is the ROLLING 7x24h before `now` (no week start: there is no Monday reset),
    the daily window starts at the broker day's server midnight, and a rail trips when realised
    P/L in its window is STRICTLY below -PCT x anchor. `rows is None` (ledger UNMEASURED) gives
    `measured: False` and no headroom -- absence is never a full tank."""
    now = now or datetime.now(tz=UTC)
    anchor = max(float(peak_equity or 0.0), float(equity or 0.0))
    out: dict = {}
    for code, pct, start in (("WEEKLY_LOSS", WEEKLY_LOSS_PCT, now - timedelta(days=7)),
                             ("DAILY_LOSS", DAILY_LOSS_PCT, broker_day_start(now))):
        blk: dict = {"rule": "trip when realised P/L since window_start < -pct x anchor; "
                             "anchor = max(stamp peak_equity, equity incl. floating)",
                     "pct": pct, "anchor": round(anchor, 2), "anchor_ts": peak_ts,
                     "window_start": start.isoformat(timespec="seconds"),
                     "measured": rows is not None and anchor > 0}
        if blk["measured"]:
            pl = realised_pl_since(rows or [], start)
            trip = pct * anchor
            blk.update({"realised_pl": round(pl, 2), "loss_frac": round(max(-pl, 0.0) / anchor, 4),
                        "trip_at_ccy": round(trip, 2), "headroom_ccy": round(trip + pl, 2),
                        "headroom_frac": round((trip + pl) / anchor, 4)})
        else:
            blk.update({"realised_pl": None, "loss_frac": None, "trip_at_ccy": None,
                        "headroom_ccy": None, "headroom_frac": None})
        out[code] = blk
    w = out["WEEKLY_LOSS"]
    w["weekly_anchor"], w["week_start"] = w["anchor"], w["window_start"]
    # THE DAILY RAIL'S SECOND LEG (evaluate's elif): equity <= the broker day's opening x 0.9,
    # only when `day_start_equity` is dated to this broker day.
    d = out["DAILY_LOSS"]
    op = None
    if isinstance(opening, dict) and opening.get("date") == broker_day(now):
        try:
            op = float(opening.get("equity"))
        except (TypeError, ValueError):
            op = None
    d["opening_equity"] = op
    d["equity_trip_at"] = round(op * (1.0 - DAILY_LOSS_PCT), 2) if op else None
    d["equity_headroom_ccy"] = (round(float(equity) - op * (1.0 - DAILY_LOSS_PCT), 2)
                                if op and equity else None)
    return out


def flatten_and_halt(reasons: list[str], dry_run: bool = True) -> None:
    """Write the halt file FIRST (stops new brackets within one gateway pass), then flatten.

    Order matters: pausing before flattening means the gateway cannot re-open behind us. The
    halt lifts AUTOMATICALLY once the breach condition is measurably gone (see try_rearm) --
    the rail does not hold an opinion about when the emergency ended, it holds a MEASUREMENT.
    """
    body = (f"AUTO-HALTED {datetime.now(tz=UTC).isoformat(timespec='seconds')} by the Fusion "
            f"ruin rail.\n\n" + "\n".join(f"  - {r}" for r in reasons) +
            "\n\nAll positions flattened. Trading resumes AUTOMATICALLY once every breach "
            "condition above is measurably clear, after a cooldown that lengthens with each "
            "repeat. Delete this file by hand only if you want to resume sooner.\n")
    if dry_run:
        log(f"DRY-RUN would halt: {reasons}")
        return
    PAUSED.parent.mkdir(parents=True, exist_ok=True)
    PAUSED.write_text(body, "utf-8")
    log(f"HALT FILE WRITTEN: {PAUSED}")
    import MetaTrader5 as mt5
    for p in mt5.positions_get() or []:
        tick = mt5.symbol_info_tick(p.symbol)
        if tick is None:
            log(f"FLATTEN {p.ticket}: no tick, retry next pass")
            continue
        res = mt5.order_send({
            "action": mt5.TRADE_ACTION_DEAL, "symbol": p.symbol, "volume": p.volume,
            "type": (mt5.ORDER_TYPE_SELL if p.type == mt5.POSITION_TYPE_BUY
                     else mt5.ORDER_TYPE_BUY),
            "position": p.ticket,
            "price": (tick.bid if p.type == mt5.POSITION_TYPE_BUY else tick.ask),
            "deviation": 50, "comment": "DEADMAN",
        })
        log(f"FLATTEN {p.ticket} {p.symbol} {p.volume} -> "
            f"retcode={getattr(res, 'retcode', None)}")
    for o in mt5.orders_get() or []:
        mt5.order_delete(o.ticket)
        log(f"CANCELLED pending {o.ticket}")


def halted_by_us() -> dict | None:
    """The halt record we wrote, if the pause is OURS. A pause a HUMAN wrote (or the gateway's
    own placement-failure auto-pause) is never auto-cleared -- we only ever undo our own act."""
    if not PAUSED.exists():
        return None
    try:
        body = PAUSED.read_text("utf-8")
    except OSError:
        return None
    return {"body": body} if "Fusion ruin rail" in body else None


def try_rearm(stamp: dict, dry_run: bool) -> bool:
    """Clear OUR halt once every breach that caused it has objectively cleared.

    Returns True if trading was resumed. FULLY AUTOMATIC -- no path here requires a person.
    Auto re-arm requires ALL of:
      1. the halt is ours (a human's own pause is respected, never overwritten),
      2. no breach is currently observed -- including the ruin rail's hysteresis band,
      3. the backoff window has elapsed since the condition last cleared, where the window
         DOUBLES per re-arm of the same code in the last 24h (30/60/120/240... to the cap).
    """
    # Every exit names its verdict on the stamp, so a dry-run pass can STATE what it would do
    # rather than only log it.
    if not halted_by_us():
        stamp["rearm_verdict"] = "no halt of ours to lift"
        return False
    codes = list(stamp.get("halt_codes") or [])
    if not codes:
        stamp["rearm_verdict"] = "halt is ours but names no codes; held"
        return False
    unknown = [c for c in codes if c not in AUTO_REARM]
    if unknown:
        # A code with no declared clear condition cannot be measured as fixed, so it holds --
        # this is the fail-closed direction, not a request for a human.
        log(f"re-arm HELD -- no declared clear condition for {unknown}")
        stamp["rearm_verdict"] = f"HELD: no declared clear condition for {unknown}"
        return False

    now = datetime.now(tz=UTC)
    # BACKOFF, not escalation: prune to the rolling 24h, then double the wait per prior re-arm.
    hist = {c: [t for t in stamp.get("rearm_history", {}).get(c, [])
                if datetime.fromisoformat(t) > now - timedelta(days=1)]
            for c in codes}
    repeats = max((len(v) for v in hist.values()), default=0)
    wait_min = min(REARM_COOLDOWN_MIN * (2 ** repeats), REARM_COOLDOWN_CAP_MIN)

    cleared_at = stamp.get("cleared_at")
    if not cleared_at:
        stamp["cleared_at"] = now.isoformat(timespec="seconds")
        log(f"breach cleared; backoff {wait_min:.0f}min before re-arm "
            f"(repeat #{repeats + 1} in 24h)")
        stamp["rearm_verdict"] = (f"cleared; backoff {wait_min:.0f}min before re-arm "
                                  f"(repeat #{repeats + 1} in 24h)")
        return False
    waited = (now - datetime.fromisoformat(cleared_at)).total_seconds() / 60
    if waited < wait_min:
        log(f"backoff {waited:.0f}/{wait_min:.0f}min (repeat #{repeats + 1})")
        stamp["rearm_verdict"] = f"backoff {waited:.0f}/{wait_min:.0f}min (repeat #{repeats + 1})"
        return False

    why = "; ".join(AUTO_REARM[c] for c in codes)
    if dry_run:
        log(f"DRY-RUN would AUTO RE-ARM ({codes}): {why}")
        stamp["rearm_verdict"] = f"WOULD RE-ARM ({codes}): {why}"
        return False
    stamp["rearm_verdict"] = f"RE-ARMED ({codes}): {why}"
    PAUSED.unlink(missing_ok=True)
    for c in codes:
        hist.setdefault(c, []).append(now.isoformat(timespec="seconds"))
    stamp["rearm_history"] = {**stamp.get("rearm_history", {}), **hist}
    stamp["halt_codes"] = []
    stamp["cleared_at"] = None
    log(f"AUTO RE-ARMED after {codes}: {why} (auto re-arms today: "
        f"{ {c: len(hist[c]) for c in codes} })")
    return True


#: The rails as this pass measured against them, written onto every stamp so a reading can be
#: checked against the number it was judged by rather than against whatever the file says later.
def rails() -> dict:
    return {"DAILY_LOSS_PCT": DAILY_LOSS_PCT, "EQUITY_FLOOR_EUR": EQUITY_FLOOR_EUR,
            "WEEKLY_LOSS_PCT": WEEKLY_LOSS_PCT, "MAX_OPEN_POSITIONS": MAX_OPEN_POSITIONS,
            "MIN_FREE_MARGIN_FRAC": MIN_FREE_MARGIN_FRAC, "MAX_SIZE_MULTIPLE": MAX_SIZE_MULTIPLE,
            "STALE_HEARTBEAT_MIN": STALE_HEARTBEAT_MIN, "CONFIRM_READS": CONFIRM_READS}


def clear_stale_daily_loss(stamp: dict, day: str, *, ours: bool = False) -> str | None:
    """Drop a DAILY_LOSS latch measured on another broker day than `day`. Returns what it cleared
    (None when nothing was stale). When the pause is OURS the code stays for `try_rearm`, whose
    declared clear condition for it is exactly a new trading day; only the day it holds is
    refreshed so it no longer reads as today's halt. Pure over `stamp`."""
    codes = list(stamp.get("halt_codes") or [])
    if "DAILY_LOSS" not in codes or stamp.get("daily_loss_day") == day:
        return None
    was = stamp.get("daily_loss_day")
    if not ours:
        stamp["halt_codes"] = [c for c in codes if c != "DAILY_LOSS"]
    stamp["daily_loss_day"] = None
    why = f"stale DAILY_LOSS from broker day {was or 'unknown'} cleared on {day}"
    log(why)
    return why


def principal_armed(path: Path | None = None) -> tuple[bool, str]:
    """Whether the principal has armed the rail: `ARMED_MARKER` exists and reads
    {"armed_by": "zuck", ...}. Anything else is NOT armed (fail closed to dry-run)."""
    p = path or ARMED_MARKER
    try:
        doc = json.loads(p.read_text("utf-8"))
    except (OSError, ValueError):
        return False, f"{p.name} absent or unreadable"
    if not isinstance(doc, dict) or doc.get("armed_by") != "zuck":
        return False, f"{p.name} does not carry armed_by \"zuck\""
    return True, f"armed by the principal ({p.name})"


def main(dry_run: bool = True) -> int:
    """Default DRY-RUN. A rail that arms itself on first execution is not reviewable.

    EVERY PASS WRITES THE STAMP AND THE STAMP SAYS WHAT THIS PASS WOULD DO (`would.action`):
    HALT_AND_FLATTEN, WAIT_FOR_CONFIRMATION, RE-ARM, HOLD_HALT or NOTHING -- with the readings
    it judged and the rails it judged them by. In dry-run `would.executed` is false and no file
    but the stamp and the log is touched; arming (`--live`) is the principal's decision.
    """
    armed, armed_why = principal_armed()
    if dry_run and armed:
        # The LIVE task owns the stamp once the principal has armed the rail.
        log(f"dry-run pass stands aside: {armed_why}; MT5-FusionDeadmanLive owns the stamp")
        return 0
    demoted = (not dry_run) and not armed
    if demoted:
        dry_run = True
        log(f"--live requested but NOT armed ({armed_why}); this pass runs as DRY-RUN")
    st = _read(STATE, {})
    account = {"equity": st.get("equity", 0.0), "margin_free": st.get("margin_free", 0.0),
               "last_reconcile": st.get("last_reconcile"), "pending": st.get("pending") or [],
               "day_start_equity": st.get("day_start_equity")}
    positions = st.get("position") or []
    stamp = _read(STAMP, {"peak_equity": 0.0, "consecutive": 0, "halt_codes": [],
                          "rearm_history": {}, "escalated": [], "cleared_at": None})
    peak = max(float(stamp.get("peak_equity", 0.0)), float(account["equity"] or 0.0))
    expected = expected_lots(intent_rows())
    day = broker_day()
    # A STALE DAILY_LOSS IS CLEARED BEFORE ANY FLATTEN DECISION (r6): the latch is for the broker
    # day it was measured on, never carried into the next. Our own pause keeps the code so
    # try_rearm lifts it by its declared clear condition ("a new trading day began").
    stale_cleared = clear_stale_daily_loss(stamp, day, ours=halted_by_us() is not None)
    if stamp.get("consecutive_day") != day:
        stamp["consecutive"] = 0                  # a confirm count never spans broker days

    # THE LEDGER IS A PRECONDITION (audit r6): absent or unreadable is UNMEASURED, never a zero
    # loss. The realised rule is skipped (nothing is assumed), arming refuses, and a LIVE stamp
    # carrying ledger.ok == False makes the gateway's gate refuse new Fusion risk.
    led_rows, led_why = ledger_checked()
    breaches = evaluate(account, positions, led_rows or [], peak,
                        tuple(stamp.get('halt_codes') or ()), expected=expected)
    codes = [c for c, _ in breaches]
    messages = [m for _, m in breaches]
    if peak > float(stamp.get("peak_equity", 0.0) or 0.0) or not stamp.get("peak_equity_ts"):
        # A peak set before this field existed has no known instant: it is stamped when first
        # recorded and says so, rather than inventing when the high-water mark was made.
        stamp["peak_equity_ts_basis"] = ("new high this pass"
                                         if peak > float(stamp.get("peak_equity", 0.0) or 0.0)
                                         else "inherited; first recorded at this instant")
        stamp["peak_equity_ts"] = datetime.now(tz=UTC).isoformat(timespec="seconds")
    stamp["peak_equity"] = peak
    stamp.pop("rearm_verdict", None)

    # ARMING NEVER FLATTENS (r6). The first LIVE pass after DRY-RUN refuses to arm while the
    # current broker day's DAILY_LOSS halt is set (latched today or observed now) and says why;
    # it stays DRY-RUN, so the gateway's gate (decision_core.fusion_deadman_armed) keeps new
    # Fusion risk off. Otherwise it arms with a fresh confirm count: a dry-run count is not a
    # live read.
    refused = None
    if not dry_run and stamp.get("mode") != "LIVE":
        today_halt = ("DAILY_LOSS" in (stamp.get("halt_codes") or [])
                      and stamp.get("daily_loss_day") == day) or "DAILY_LOSS" in codes
        if led_rows is None:
            refused = (f"arming refused: the live ledger is UNMEASURED ({led_why}); the rail "
                       f"stays DRY-RUN until it reads the declared account's ledger")
            log(refused)
            dry_run = True
        elif today_halt:
            refused = (f"arming refused: a DAILY_LOSS halt is set for broker day {day}; the rail "
                       f"stays DRY-RUN (no flatten) and arms on the next broker day")
            log(refused)
            dry_run = True
        else:
            stamp["consecutive"] = 0

    if breaches:
        stamp["consecutive"] = int(stamp.get("consecutive", 0)) + 1
        stamp["consecutive_day"] = day
        stamp["cleared_at"] = None
        log(f"BREACH ({stamp['consecutive']}/{CONFIRM_READS}) {codes}: {messages}")
        if stamp["consecutive"] >= CONFIRM_READS:
            flatten_and_halt(messages, dry_run=dry_run)
            stamp["halt_codes"] = sorted(set(stamp.get("halt_codes", [])) | set(codes))
            if "DAILY_LOSS" in codes:
                stamp["daily_loss_day"] = day
            action = "HALT_AND_FLATTEN"
        else:
            action = "WAIT_FOR_CONFIRMATION"
    else:
        stamp["consecutive"] = 0
        rearmed = try_rearm(stamp, dry_run=dry_run)
        verdict = str(stamp.get("rearm_verdict") or "")
        if rearmed or verdict.startswith("WOULD RE-ARM"):
            action = "RE-ARM"
        elif halted_by_us():
            action = "HOLD_HALT"
        else:
            action = "NOTHING"

    stamp["mode"] = "DRY-RUN" if dry_run else "LIVE"
    stamp["armed"] = {"principal": armed, "why": armed_why,
                      "live_requested_but_unarmed": demoted, "refused": refused}
    stamp["broker_day"] = day
    stamp["ledger"] = {"ok": led_rows is not None, "why": led_why,
                       "rows": len(led_rows) if led_rows is not None else None}
    stamp["stale_daily_loss_cleared"] = stale_cleared
    stamp["checked_at"] = datetime.now(tz=UTC).isoformat(timespec="seconds")
    stamp["readings"] = {"equity": account["equity"], "margin_free": account["margin_free"],
                         "last_reconcile": account["last_reconcile"],
                         "open_positions": len(positions), "peak_equity": peak,
                         "size_guard": size_guard(positions, expected)[1]}
    stamp["rails"] = rails()
    stamp["loss_rails"] = loss_rail_headroom(led_rows, peak, float(account["equity"] or 0.0),
                                             stamp.get("peak_equity_ts"),
                                             opening=account.get("day_start_equity"))
    stamp["breaches"] = codes
    stamp["would"] = {"action": action, "executed": not dry_run, "reasons": messages,
                      "confirm": f"{stamp['consecutive']}/{CONFIRM_READS}",
                      "rearm": stamp.get("rearm_verdict")}
    STAMP.parent.mkdir(parents=True, exist_ok=True)
    STAMP.write_text(json.dumps(stamp, indent=1), "utf-8")
    return 1 if breaches else 0


if __name__ == "__main__":
    import sys
    main(dry_run="--live" not in sys.argv)
