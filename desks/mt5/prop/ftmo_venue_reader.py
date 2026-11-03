"""FTMO VENUE READER -- the account's phase and position, the terminal's symbol list, and FTMO's own
spread at every hour, for research/prop_challenge_allocator.py. READ-ONLY: it sends no order.

WHY A READER OF ITS OWN. MetaTrader5 attaches to the FTMO terminal only from the interactive
desktop session that runs it (prop/ftmo_follower.py's `interactive_session`), while the allocator
runs inside the hourly cycle. So this script, on its own interactive task every five minutes,
publishes what the allocator needs and the allocator reads files:

  reports/FTMO_ACCOUNT_STATE.json   phase, balance, equity, today's starting balance (00:00 CE(S)T),
                                    trading days this phase, open positions; the account is named
                                    only by its keyed HMAC (gold_oco.oco_account_key)
  data/ftmo_registry.json           every symbol the terminal lists: point, contract, live spread,
                                    swap; plus commission per lot per side MEASURED off the deals
  data/cost_surface_ftmo.json       FTMO's spread per symbol x hour, built by research/
                                    cost_surface.build from the FTMO terminal's own H1 bars
                                    (refreshed once a day; bars land in data/universe_ftmo/)

THE PHASE IS READ OFF THE ACCOUNT, AND ONLY A POSITIVELY ESTABLISHED PHASE IS PUBLISHED AS ONE.
A 2-Step account runs phase1 -> phase2 -> funded, and each step is a NEW account (a new login) that
starts at the initial balance. The chain is kept in data/ftmo_phase_state.json:
  * a new account key right after a phase this reader SAW pass (balance at its target, flat, with
    the minimum trading days done) is the next phase -- ESTABLISHED;
  * the declaration's "phase" (data/FTMO_LIVE_ACCOUNT.json) establishes it outright;
  * anything else -- a first-seen account, a new key after a phase that was not seen to pass (a
    retry, or a pass this reader missed), an unknown next phase -- is published with status
    UNMEASURED, so the allocator solves it but never deploys from it (fail closed);
  * a balance deal after the account was first seen is a RESET: same phase, still established.
The terminal must be on the DECLARED account (login and server, as the follower checks), and the
initial balance is the declaration's, never a default: otherwise the state is UNMEASURED.
Every inference is published with its reason (`phase_why`).

    python prop/ftmo_venue_reader.py            one pass (interactive session only)
"""
from __future__ import annotations

import contextlib
import json
import os
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

DESK = Path(__file__).resolve().parents[1]
ROOT = DESK.parent.parent
for _p in (str(DESK), str(DESK / "research"), str(ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

STATE_OUT = DESK / "reports" / "FTMO_ACCOUNT_STATE.json"
REGISTRY_OUT = DESK / "data" / "ftmo_registry.json"
SURFACE_OUT = DESK / "data" / "cost_surface_ftmo.json"
BARS_DIR = DESK / "data" / "universe_ftmo"
PHASES = DESK / "data" / "ftmo_phase_state.json"
LOG = DESK / "logs" / "ftmo_venue_reader.log"
#: H1 bars per symbol for the cost surface: ~2 years, past the surface's MIN_OBS per hour.
BARS = 12_000
SURFACE_MAX_AGE_S = 24 * 3600
#: The symbols worth a surface: FX crosses and metals (the certified families' ground).
DEAL_TYPES_TRADE = (0, 1)        # DEAL_TYPE_BUY / DEAL_TYPE_SELL
DEAL_TYPE_BALANCE = 2
DEAL_ENTRY_IN = 0


def log(msg: str) -> None:
    line = f"{datetime.now(tz=UTC).isoformat(timespec='seconds')} {msg}"
    print(line)
    with contextlib.suppress(OSError):
        LOG.parent.mkdir(parents=True, exist_ok=True)
        with LOG.open("a", encoding="utf-8") as fh:
            fh.write(line + "\n")


def _atomic(path: Path, doc: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(doc, indent=1, default=str), encoding="utf-8")
    os.replace(tmp, path)


def _read(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, ValueError):
        return None


def wanted_symbol(name: str) -> bool:
    return (len(name) == 6 and name.isalpha() and name.isupper()) or name.startswith("XA")


# ------------------------------------------------------------------ the phase chain (pure)

def infer_phase(chain: dict[str, Any], key: str, *, balance: float, initial: float,
                declared: str | None, first_balance_at: str | None,
                rules: Any) -> tuple[str, str, dict[str, Any]]:
    """(phase, why, updated chain). Pure: the tests drive it with no terminal."""
    accounts = dict(chain.get("accounts") or {})
    cur = accounts.get(key)
    if cur is None:
        prev_key = chain.get("current")
        prev = accounts.get(prev_key) if prev_key else None
        established = False
        if prev is None:
            phase, why = "phase1", "first account seen: phase NOT established"
        elif prev.get("passed") and prev.get("established") \
                and prev["phase"] in rules.next_phase:
            phase = rules.next_phase[prev["phase"]]
            why, established = f"new account after {prev['phase']} was seen to PASS", True
        else:
            phase = prev["phase"]
            why = (f"new account after {prev['phase']} was not seen to pass (a retry, or a missed "
                   f"pass): phase NOT established")
        cur = {"phase": phase, "first_seen_balance_at": first_balance_at, "passed": False,
               "established": established}
    else:
        phase, why = cur["phase"], "same account"
        if first_balance_at and cur.get("first_seen_balance_at") \
                and first_balance_at > cur["first_seen_balance_at"]:
            why = "balance reset on the same account: a new attempt at the same phase"
            cur = {**cur, "first_seen_balance_at": first_balance_at, "passed": False}
    if declared:
        phase, why = declared, f"declared in FTMO_LIVE_ACCOUNT.json (inferred: {why})"
        cur = {**cur, "phase": declared, "established": True}
    target = rules.targets.get(phase)
    cur["last_balance_x"] = round(balance / initial, 5)
    accounts[key] = cur
    return phase, why, {"accounts": accounts, "current": key, "target": target}


def mark_passed(chain: dict[str, Any], key: str, *, balance: float, initial: float,
                days_traded: int, flat: bool, rules: Any) -> dict[str, Any]:
    cur = (chain.get("accounts") or {}).get(key)
    if cur is None:
        return chain
    target = rules.targets.get(cur["phase"])
    if target is not None and flat and balance >= initial * (1 + target) \
            and days_traded >= rules.min_days:
        cur["passed"] = True
    return chain


def trading_days(deals: list[Any], since_epoch: float | None) -> int:
    """Distinct CE(S)T dates with a position OPENED (FTMO's definition of a trading day)."""
    from zoneinfo import ZoneInfo
    tz = ZoneInfo("Europe/Prague")
    days = set()
    for d in deals:
        if int(getattr(d, "type", -1)) in DEAL_TYPES_TRADE \
                and int(getattr(d, "entry", -1)) == DEAL_ENTRY_IN \
                and (since_epoch is None or float(d.time) >= since_epoch):
            days.add(datetime.fromtimestamp(float(d.time), tz=UTC).astimezone(tz).date())
    return len(days)


# ------------------------------------------------------------------ the pass (needs the terminal)

def run(mt5: Any, now: datetime | None = None) -> dict[str, Any]:
    from mt5desk import gold_oco as _oco
    from prop_challenge_allocator import FTMO_2STEP as rules

    from prop import ftmo_follower as ff
    now = now or datetime.now(tz=UTC)
    decl = _read(ff.ACCOUNT_FILE) or {}
    acc = mt5.account_info()
    if acc is None:
        doc = {"status": "UNMEASURED", "why": "account_info unanswered",
               "generated_at": now.isoformat()}
        _atomic(STATE_OUT, doc)
        return doc
    key = _oco.oco_account_key(getattr(acc, "login", None), getattr(acc, "server", None))
    try:
        initial = float(decl["initial_balance"])
    except (KeyError, TypeError, ValueError):
        initial = None
    declared_ok = (initial is not None and initial > 0
                   and ff._canon(getattr(acc, "login", None)) == ff._canon(decl.get("login"))
                   and str(getattr(acc, "server", "")).strip()
                   == str(decl.get("server") or "").strip())
    if initial is None or not initial > 0:
        doc = {"status": "UNMEASURED", "generated_at": now.isoformat(),
               "why": "FTMO_LIVE_ACCOUNT.json carries no initial_balance: the limits cannot be "
                      "placed"}
        _atomic(STATE_OUT, doc)
        return doc
    deals = list(mt5.history_deals_get(now - timedelta(days=400), now + timedelta(minutes=5))
                 or [])
    bal_deals = sorted(float(d.time) for d in deals
                       if int(getattr(d, "type", -1)) == DEAL_TYPE_BALANCE)
    first_bal = (datetime.fromtimestamp(bal_deals[-1], tz=UTC).isoformat() if bal_deals
                 else None)
    chain = _read(PHASES) or {}
    phase, why, chain = infer_phase(chain, key, balance=float(acc.balance), initial=initial,
                                    declared=decl.get("phase"), first_balance_at=first_bal,
                                    rules=rules)
    since = bal_deals[-1] if bal_deals else None
    days = trading_days(deals, since)
    positions = list(mt5.positions_get() or [])
    chain = mark_passed(chain, key, balance=float(acc.balance), initial=initial,
                        days_traded=days, flat=not positions, rules=rules)
    _atomic(PHASES, chain)
    _, midnight = ff.cet_day(now)
    try:
        start = ff.day_start_balance(mt5, float(acc.balance), midnight, now)
    except ValueError as exc:
        doc = {"status": "UNMEASURED", "why": f"day start balance: {exc}",
               "generated_at": now.isoformat()}
        _atomic(STATE_OUT, doc)
        return doc
    established = bool(((chain.get("accounts") or {}).get(key) or {}).get("established"))
    status = "OK" if established and declared_ok else "UNMEASURED"
    if not declared_ok:
        why = f"{why}; the terminal is not on the declared account"
    doc = {"status": status, "generated_at": now.isoformat(timespec="seconds"),
           "account_key": key, "phase": phase, "phase_why": why,
           "initial_balance": initial, "balance": float(acc.balance),
           "equity": float(acc.equity), "day_start_balance": start, "days_traded": days,
           "phase_started_at": first_bal,
           "open_positions": [{"symbol": p.symbol, "side": "long" if int(p.type) == 0 else "short",
                               "volume": float(p.volume), "profit": float(p.profit)}
                              for p in positions]}
    _atomic(STATE_OUT, doc)
    # The registry: every listed symbol, and commission per lot per side off the deals.
    syms: dict[str, Any] = {}
    for s in mt5.symbols_get() or []:
        syms[s.name] = {"point": s.point, "digits": s.digits,
                        "trade_contract_size": s.trade_contract_size, "spread": s.spread,
                        "live_spread_pts": s.spread, "swap_long": s.swap_long,
                        "swap_short": s.swap_short, "volume_min": s.volume_min,
                        "volume_step": s.volume_step, "trade_mode": s.trade_mode}
    reg = {"generated_at": now.isoformat(timespec="seconds"),
           "terminal": {"name": "FTMO Global Markets MT5 Terminal"}, "symbols": syms,
           "deals": [{"sym": d.symbol, "vol": float(d.volume), "comm": float(d.commission)}
                     for d in deals if int(getattr(d, "type", -1)) in DEAL_TYPES_TRADE
                     and float(d.volume) > 0]}
    _atomic(REGISTRY_OUT, reg)
    # FTMO's own hour surface, once a day.
    surf = _read(SURFACE_OUT) or {}
    try:
        age = (now - datetime.fromisoformat(str(surf.get("built_at")))).total_seconds()
    except (TypeError, ValueError):
        age = float("inf")
    if age > SURFACE_MAX_AGE_S:
        build_surface(mt5, [n for n in syms if wanted_symbol(n)])
    return doc


def build_surface(mt5: Any, symbols: list[str]) -> None:
    import pandas as pd
    from cost_surface import build
    BARS_DIR.mkdir(parents=True, exist_ok=True)
    for s in symbols:
        rates = mt5.copy_rates_from_pos(s, mt5.TIMEFRAME_H1, 0, BARS)
        if rates is None or len(rates) == 0:
            continue
        df = pd.DataFrame(rates)
        df["time"] = pd.to_datetime(df["time"], unit="s", utc=True)
        df.set_index("time").to_parquet(BARS_DIR / f"{s}_H1.parquet")
    doc = build(BARS_DIR)
    doc["source"] = "FTMO terminal H1 bars (prop/ftmo_venue_reader.py)"
    _atomic(SURFACE_OUT, doc)
    log(f"FTMO cost surface: {doc.get('n_symbols')} symbols")


def main(argv: list[str] | None = None) -> int:
    del argv
    from prop import ftmo_follower as ff
    ok, why = ff.interactive_session()
    if not ok:
        log(f"not run: {why}")
        return 1
    try:
        import MetaTrader5 as mt5
        if not mt5.initialize(path=os.environ.get(ff.TERMINAL_ENV) or ff.TERMINAL_PATH,
                              timeout=15000):
            log(f"FTMO terminal unavailable: {mt5.last_error()}")
            return 1
    except Exception as exc:
        log(f"MetaTrader5 unavailable ({type(exc).__name__}: {exc})")
        return 1
    try:
        doc = run(mt5)
    finally:
        mt5.shutdown()
    log(f"ftmo venue reader: {doc.get('status')} phase={doc.get('phase')} ({doc.get('phase_why')})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
