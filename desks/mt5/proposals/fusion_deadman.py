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
from datetime import UTC, datetime, timedelta
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent          # desks/mt5
STATE = BASE / "data" / "gateway_state.json"
LEDGER = BASE / "data" / "live_ledger.jsonl"
PAUSED = BASE / "data" / "GATEWAY_PAUSED"              # the gateway ALREADY honours this file
BREACH_LOG = BASE / "logs" / "fusion_deadman.log"
STAMP = BASE / "data" / "fusion_deadman_state.json"

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


def evaluate(account: dict, positions: list[dict], rows: list[dict],
             peak_equity: float, halt_codes: tuple = ()) -> list[tuple[str, str]]:
    """Pure function: state in, breach reasons out. Testable without MT5 attached."""
    breaches: list[tuple[str, str]] = []
    equity = float(account.get("equity", 0.0) or 0.0)
    now = datetime.now(tz=UTC)

    # HYSTERESIS: once halted on the floor, the account must climb back to floor x 1.05 before
    # this stops reporting a breach -- so the CLEAR condition is strictly harder than the BREACH
    # condition and the ruin rail cannot oscillate across its own boundary unattended.
    floor = (EQUITY_FLOOR_EUR * EQUITY_REARM_HYSTERESIS
             if "EQUITY_FLOOR" in (halt_codes or ()) else EQUITY_FLOOR_EUR)
    if equity > 0 and equity < floor:
        breaches.append(("EQUITY_FLOOR",
                         f"EQUITY FLOOR: {equity:.2f} < {floor:.2f} -- the account "
                         f"can no longer size its own policy"))

    day_start = datetime.combine(now.date(), datetime.min.time(), tzinfo=UTC)
    day_pl = realised_pl_since(rows, day_start)
    day_ref = max(peak_equity, equity)
    if day_ref > 0 and day_pl < -DAILY_LOSS_PCT * day_ref:
        breaches.append(("DAILY_LOSS",
                         f"DAILY LOSS: {day_pl:.2f} beyond {DAILY_LOSS_PCT:.0%} of {day_ref:.2f}"))

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
    if positions and last:
        try:
            age_min = (now - datetime.fromisoformat(str(last))).total_seconds() / 60
            if age_min > STALE_HEARTBEAT_MIN:
                breaches.append(("STALE_GATEWAY",
                                 f"STALE GATEWAY: {age_min:.0f}min since reconcile with "
                                 f"{len(positions)} position(s) open -- unmanaged risk"))
        except ValueError:
            breaches.append(("STALE_GATEWAY",
                             "STALE GATEWAY: last_reconcile unparseable -- treated as stale"))
    return breaches


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
    if not halted_by_us():
        return False
    codes = list(stamp.get("halt_codes") or [])
    if not codes:
        return False
    unknown = [c for c in codes if c not in AUTO_REARM]
    if unknown:
        # A code with no declared clear condition cannot be measured as fixed, so it holds --
        # this is the fail-closed direction, not a request for a human.
        log(f"re-arm HELD -- no declared clear condition for {unknown}")
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
        return False
    waited = (now - datetime.fromisoformat(cleared_at)).total_seconds() / 60
    if waited < wait_min:
        log(f"backoff {waited:.0f}/{wait_min:.0f}min (repeat #{repeats + 1})")
        return False

    why = "; ".join(AUTO_REARM[c] for c in codes)
    if dry_run:
        log(f"DRY-RUN would AUTO RE-ARM ({codes}): {why}")
        return False
    PAUSED.unlink(missing_ok=True)
    for c in codes:
        hist.setdefault(c, []).append(now.isoformat(timespec="seconds"))
    stamp["rearm_history"] = {**stamp.get("rearm_history", {}), **hist}
    stamp["halt_codes"] = []
    stamp["cleared_at"] = None
    log(f"AUTO RE-ARMED after {codes}: {why} (auto re-arms today: "
        f"{ {c: len(hist[c]) for c in codes} })")
    return True


def main(dry_run: bool = True) -> int:
    """Default DRY-RUN. A rail that arms itself on first execution is not reviewable."""
    st = _read(STATE, {})
    account = {"equity": st.get("equity", 0.0), "margin_free": st.get("margin_free", 0.0),
               "last_reconcile": st.get("last_reconcile")}
    positions = st.get("position") or []
    stamp = _read(STAMP, {"peak_equity": 0.0, "consecutive": 0, "halt_codes": [],
                          "rearm_history": {}, "escalated": [], "cleared_at": None})
    peak = max(float(stamp.get("peak_equity", 0.0)), float(account["equity"] or 0.0))

    breaches = evaluate(account, positions, ledger_rows(), peak,
                        tuple(stamp.get('halt_codes') or ()))
    codes = [c for c, _ in breaches]
    messages = [m for _, m in breaches]
    stamp["peak_equity"] = peak

    if breaches:
        stamp["consecutive"] = int(stamp.get("consecutive", 0)) + 1
        stamp["cleared_at"] = None
        log(f"BREACH ({stamp['consecutive']}/{CONFIRM_READS}) {codes}: {messages}")
        if stamp["consecutive"] >= CONFIRM_READS:
            flatten_and_halt(messages, dry_run=dry_run)
            stamp["halt_codes"] = sorted(set(stamp.get("halt_codes", [])) | set(codes))
    else:
        stamp["consecutive"] = 0
        try_rearm(stamp, dry_run=dry_run)

    stamp["checked_at"] = datetime.now(tz=UTC).isoformat(timespec="seconds")
    STAMP.write_text(json.dumps(stamp, indent=1), "utf-8")
    return 1 if breaches else 0


if __name__ == "__main__":
    import sys
    main(dry_run="--live" not in sys.argv)
