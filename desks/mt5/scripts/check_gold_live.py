"""Is the gold book actually armed on the LIVE account, or does something still refuse it?

WHY A SCRIPT AND NOT AN EYEBALL. "The gold sleeves aren't placing limits" has at least seven
different causes on this desk, each in a different file, and six of them look identical from the
terminal: an empty XAUUSD order book. The registry says LIVE, the gateway says nothing, and the
reader concludes the gateway is broken. Measured 2026-09-07: four XAUUSD.asia sleeves were LIVE in
`sleeves.json` and refused by `GOLD_RETIRED.json`, and nothing on the desk said so in one place.

This walks the money path IN ORDER and stops describing the desk the moment a step refuses:

    1. data/GATEWAY_PAUSED          present -> gateway.main() trades NOTHING, whatever follows
    2. data/GOLD_RETIRED.json       names a window -> decision_core.roster skips it entirely
    3. data/sleeves.json            which XAUUSD rows are marked LIVE
    4. decision_core.roster(...)    what the money path ACTUALLY emits, not what a file describes
    5. MetaTrader5                  connected? which broker? is trading allowed on the terminal
                                    and on the account?
    6. live order book              XAUUSD pendings and positions right now
    7. the clock                    each window's signal hour against the broker's current hour

STEP 7 IS NOT DECORATION. The gold windows fire at 07:00, 13:00 and 17:00 broker time and place
nothing in between. An empty book at 09:40 is the schedule working, and without the clock printed
next to it that is indistinguishable from the failure this script exists to find.

    python desks/mt5/scripts/check_gold_live.py

Exit 0 when every step that can be checked is clear, 1 when something refuses the book.
"""
from __future__ import annotations

import json
import sys
from datetime import UTC, datetime
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
DATA = BASE / "data"
sys.path.insert(0, str(BASE))

OK, BAD, INFO = "OK  ", "STOP", "    "


def _read(path: Path):
    try:
        return json.loads(path.read_text("utf-8"))
    except (OSError, ValueError):
        return None


def main(argv: list[str] | None = None) -> int:
    lines: list[str] = []
    blocking: list[str] = []

    def say(tag: str, text: str) -> None:
        lines.append(f"{tag} {text}")

    # -- 1. the pause file -------------------------------------------------------------------
    # Checked FIRST because it is the only switch that makes every other answer irrelevant, and
    # it is the one most easily left behind by a broker migration.
    pause = DATA / "GATEWAY_PAUSED"
    if pause.exists():
        say(BAD, f"data/GATEWAY_PAUSED EXISTS -- the gateway trades nothing at all this pass.")
        say(INFO, f"     reason on file: {pause.read_text('utf-8', errors='replace').strip()[:120]}")
        say(INFO, "     remove it to re-arm; nothing below can place an order while it is there.")
        blocking.append("GATEWAY_PAUSED present")
    else:
        say(OK, "data/GATEWAY_PAUSED absent -- the gateway is not paused")

    # -- 2. the gold retirement file ---------------------------------------------------------
    retired_path = DATA / "GOLD_RETIRED.json"
    retired = _read(retired_path)
    if not isinstance(retired, dict):
        retired = {}
    if retired:
        say(BAD, f"data/GOLD_RETIRED.json names {sorted(retired)} -- roster() skips these windows")
        for k, v in sorted(retired.items()):
            why = (v or {}).get("reason", "no reason recorded") if isinstance(v, dict) else str(v)
            say(INFO, f"     {k}: {why}")
        blocking.append(f"GOLD_RETIRED.json holds {sorted(retired)}")
    elif retired_path.exists():
        say(OK, "data/GOLD_RETIRED.json is empty -- no window is retired")
    else:
        say(OK, "data/GOLD_RETIRED.json absent -- no window is retired")

    # -- 2b. the arming gates, PER LANE -------------------------------------------------------
    # These are not one switch and they do not gate the same sleeves, which is exactly how a
    # half-armed desk reads as a broken one.
    #
    # GOLD IS GATED BY THE RELEASE VERDICT TOO, and reading `place_bracket` alone says otherwise.
    # That function tests `st["armed"]` and nothing else, which is true and misleading: its
    # CALLER, the bracket loop, checks `if not NEW_RISK_OK` first and logs "[name] bracket NOT
    # placed: release identity refuses new risk" without ever reaching it (gateway.py:2116).
    # I read the callee and reported gold unaffected by the release gate. It is not. With
    # NEW_RISK_OK false -- which it had been since the gate was written, NON_CODE naming six of
    # the ten paths the box publishes -- gold placed nothing either, and `matched_fills: 0` on an
    # account that has never had a position is that fact.
    #
    # The promoted lanes need MORE than gold, not something different: `armed = st["armed"] and
    # GENERIC_EXEC_ENABLED.exists() and NEW_RISK_OK` (gateway.py:1453 and :1660). So
    # GENERIC_EXEC_ENABLED separates the lanes; the release verdict does not.
    kill = DATA / "CASHCARRY_KILL"
    if kill.exists():
        say(BAD, "data/CASHCARRY_KILL EXISTS -- the deadman ruin rail has fired and flattened")
        say(INFO, f"     {kill.read_text('utf-8', errors='replace').strip()[:120]}")
        blocking.append("deadman kill switch fired")

    state = _read(BASE / "gateway_state.json") or _read(DATA / "gateway_state.json") or {}
    if bool(state.get("armed")):
        say(OK, "gateway_state.json armed=true -- the GOLD lane places real orders")
    else:
        say(BAD, "gateway_state.json armed is NOT true -- every lane logs SHADOW and places "
                 "nothing, gold included")
        blocking.append("gateway_state armed is not true")

    generic = DATA / "GENERIC_EXEC_ENABLED"
    if generic.exists():
        say(OK, "data/GENERIC_EXEC_ENABLED present -- the family and scalp lanes are wired to "
                "place (this file is what separates them from gold; the release verdict is not)")
    else:
        say(INFO, "data/GENERIC_EXEC_ENABLED absent -- promoted family/scalp sleeves stay "
                  "LOG-ONLY. This does NOT affect the gold book.")

    # The third term of the promoted lanes' arm switch. Reported because promotion to live is
    # AUTOMATIC on this desk (principal 2026-09-07): a false verdict here means the promoter goes
    # on promoting and every promoted sleeve places nothing, with no human in the loop to notice.
    try:
        from mt5desk.release_identity import verdict
        ident = verdict(write=False)
        # BLOCKING, NOT INFORMATIONAL, and getting this wrong made the whole script lie. It was
        # written as INFO back when I believed the release verdict gated only the promoted lanes.
        # When I found it also gates gold (the bracket loop tests it at gateway.py:2116, before
        # `place_bracket` is reached) I corrected the TEXT and left the SEVERITY, so the script
        # printed "NOTHING places until this is true" and then concluded "nothing refuses the
        # gold book" in the same run. A check that explains the fault correctly and then reports
        # the opposite verdict is worse than no check: it is the one thing a person acts on.
        if not ident.ok:
            blocking.append("release identity refuses new risk (NEW_RISK_OK false)")
        say(OK if ident.ok else BAD,
            f"release identity: NEW_RISK_OK={bool(ident.ok)}"
            + ("" if ident.ok else
               f" -- {ident.reason}. NOTHING places until this is true: the bracket loop checks "
               f"it before it reaches place_bracket, so GOLD is refused by this too, not only "
               f"the promoted lanes (gateway.py:2116)."))
    except Exception as exc:                                   # noqa: BLE001
        # UNMEASURED IS NOT A PASS. The gateway's own default for NEW_RISK_OK is False, so a
        # host that cannot measure the verdict is a host where nothing places.
        blocking.append(f"release identity UNMEASURED ({type(exc).__name__})")
        say(BAD, f"release identity UNMEASURED on this host ({type(exc).__name__}) -- the "
                 f"gateway defaults it to False, and False refuses EVERY lane including gold")

    # -- 3. the registry ---------------------------------------------------------------------
    try:
        from research import sleeve_registry as reg
        snap = reg.snapshot()
        gold_live = [k for k in snap.get("live", []) if "XAUUSD" in k.upper()]
        blocked = sorted(reg.gateway_retired_keys())
        say(OK if gold_live else BAD,
            f"registry: {len(gold_live)} XAUUSD sleeve(s) LIVE and not gateway-blocked")
        for k in gold_live:
            say(INFO, f"     {k}")
        if blocked:
            say(BAD, f"registry: {len(blocked)} XAUUSD sleeve(s) marked LIVE but REFUSED by the "
                     f"gateway: {blocked}")
            blocking.append("registry and gateway disagree")
        if not gold_live:
            blocking.append("no XAUUSD sleeve is live in the registry")
    except Exception as exc:                                   # noqa: BLE001 - report, never raise
        say(INFO, f"registry unreadable on this host: {type(exc).__name__}: {exc}")

    # -- 4. what the money path emits --------------------------------------------------------
    # THE ONLY AUTHORITATIVE STEP. Everything above describes inputs; this calls the same
    # function the gateway calls, on the same two files, and reads what comes out.
    gold_rows: list[dict] = []
    try:
        # `decision_core.load_sleeves` rather than `gateway.load_sleeves`: identical function,
        # but reaching it through the gateway imports MetaTrader5, so this whole step went
        # UNMEASURED on any host without the terminal -- including every host where a person
        # would sit down to ask why gold is not trading.
        from mt5desk import decision_core as dc
        gold_rows_all, notes = dc.roster(retired, dc.load_sleeves(DATA / "sleeves.json"))
        gold_rows = [s for s in gold_rows_all
                     if str(s.get("symbol", "")).upper() == "XAUUSD"
                     or str(s.get("name", "")).startswith("gold_")]
        say(OK if gold_rows else BAD,
            f"roster(): {len(gold_rows)} gold row(s) reach the venue, out of "
            f"{len(gold_rows_all)} sleeve(s) total")
        # THE LOT IN LOTS, not the word "auto". The principal set a 0.02 floor per gold leg on
        # 2026-09-07; a report that prints the sizing MODE cannot show whether the floor bound,
        # which is the only thing anyone reading this line wants to know.
        eq = state.get("equity")
        try:
            sized = dc.gold_lot(float(eq)) if eq else None
        except (TypeError, ValueError):
            sized = None
        for s in gold_rows:
            lot = s.get("lot")
            shown = (f"{sized:.2f} (floor {dc.gold_min_lot():.2f}, policy "
                     f"{dc.auto_lot(float(eq), None, dc.GOLD_SYMBOL):.2f} at equity {eq})"
                     if sized and lot == "auto" else str(lot))
            say(INFO, f"     {s.get('name')}  window={s.get('window')}  "
                      f"sig_hour={s.get('sig_hour')}  lot={shown}")
        for n in notes:
            say(INFO, f"     note: {n}")
        if not gold_rows:
            blocking.append("roster() emits no gold row")
    except Exception as exc:                                   # noqa: BLE001
        say(INFO, f"roster() not callable on this host: {type(exc).__name__}: {exc}")

    # -- 5. the terminal ---------------------------------------------------------------------
    broker_hour = None
    try:
        import MetaTrader5 as mt5
        if not mt5.initialize():
            say(BAD, f"MetaTrader5 will not initialize: {mt5.last_error()}")
            blocking.append("MT5 not connected")
        else:
            t, a = mt5.terminal_info(), mt5.account_info()
            company = getattr(a, "company", None) or getattr(t, "company", "?")
            server = getattr(a, "server", "?") if a else "no-account"
            login = getattr(a, "login", "?") if a else "?"
            say(OK, f"MT5 connected: {company} / {server} / login {login} / "
                    f"equity {getattr(a, 'equity', '?')}")
            if "fusion" not in str(company).lower() and "fusion" not in str(server).lower():
                say(BAD, f"THIS IS NOT FUSION -- '{company}' on '{server}'. Orders placed here do "
                         f"not reach the live account this desk trades.")
                blocking.append(f"wrong broker: {company}")
            if not getattr(t, "trade_allowed", True):
                say(BAD, "terminal: algo trading is DISABLED (Tools > Options > Expert Advisors)")
                blocking.append("terminal trade_allowed false")
            if a is not None and not getattr(a, "trade_allowed", True):
                say(BAD, "account: trading is disabled on this login by the broker")
                blocking.append("account trade_allowed false")

            # -- 6. the live book ------------------------------------------------------------
            pend = [o for o in (mt5.orders_get() or [])
                    if str(getattr(o, "symbol", "")).upper().startswith("XAU")]
            pos = [p for p in (mt5.positions_get() or [])
                   if str(getattr(p, "symbol", "")).upper().startswith("XAU")]
            say(OK if (pend or pos) else INFO,
                f"live book: {len(pend)} XAU pending order(s), {len(pos)} open position(s)")
            for o in pend:
                say(INFO, f"     pending {o.symbol} vol {o.volume_current} @ {o.price_open} "
                          f"ticket {o.ticket} comment '{getattr(o, 'comment', '')}'")
            for p in pos:
                say(INFO, f"     open    {p.symbol} vol {p.volume} @ {p.price_open} "
                          f"P/L {p.profit} ticket {p.ticket}")

            tick = mt5.symbol_info_tick("XAUUSD")
            if tick is not None and getattr(tick, "time", 0):
                broker_hour = datetime.fromtimestamp(tick.time, UTC).hour
            mt5.shutdown()
    except ImportError:
        say(INFO, "MetaTrader5 not importable on this host -- steps 5 and 6 are UNMEASURED "
                  "(run this on the trading box for those)")
    except Exception as exc:                                   # noqa: BLE001
        say(INFO, f"terminal check failed: {type(exc).__name__}: {exc}")

    # -- 7. the clock ------------------------------------------------------------------------
    # An empty order book between signal hours is the schedule, not a fault, and saying so here is
    # the difference between this report and a person staring at MT5 concluding gold is broken.
    try:
        from mt5desk.decision_core import GOLD_WINDOWS
        now_h = broker_hour if broker_hour is not None else datetime.now(UTC).hour
        src = "broker tick" if broker_hour is not None else "this host's UTC clock"
        hours = sorted({h for _, h, _ in GOLD_WINDOWS})
        nxt = next((h for h in hours if h > now_h), hours[0])
        say(INFO, f"clock: hour {now_h:02d} by {src}; gold fires at "
                  f"{', '.join(f'{h:02d}:00' for h in hours)} -- next {nxt:02d}:00")
        if now_h not in hours and not blocking:
            say(INFO, "an empty XAU book right now is the SCHEDULE, not a fault: the next order "
                      f"is due at {nxt:02d}:00 broker time")
    except Exception:                                          # noqa: BLE001
        pass

    print("\n".join(lines))
    print()
    if blocking:
        print(f"VERDICT: the gold book is NOT fully armed -- {len(blocking)} thing(s) refuse it:")
        for b in blocking:
            print(f"  - {b}")
        return 1
    print("VERDICT: nothing on the money path refuses the gold book. It is armed and will place "
          "at its next signal hour.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
