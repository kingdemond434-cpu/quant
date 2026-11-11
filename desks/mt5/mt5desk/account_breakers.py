"""THE ACCOUNT BREAKERS: one daily-loss latch and one disconnect breaker, for every live account.

WHY (backlog 2026-10-13, "account daily-loss circuit breaker + disconnect breaker"). Measured on
LIVE 2026-11-11, lane by lane:

    account  lane                  daily-loss latch before this file      disconnect breaker before
    fusion   mt5desk/gateway.py    decision_core.fusion_daily_loss (5%)   a 30-minute idle gate only;
                                                                          terminal_info() read and
                                                                          discarded
    e8       prop/e8_gold.py       e8_guard.assess STAND_DOWN (0.75%)     none: the terminal tick
                                                                          that dates every window
                                                                          was never aged
    e8       prop/e8_executor.py   e8_guard.assess STAND_DOWN (0.75%)     (TradeLocker REST; no
                                                                          terminal, no quote stamp)
    ftmo     prop/ftmo_follower.py none: loss_guard refuses a trade that  none
                                   would CROSS the hard 5%, never latches
    ftmo     prop/ftmo_executor.py none (the same per-trade loss_guard)   the clock check refuses a
                                                                          tick >300s off the hour

ALL ACCOUNTS RUN IDENTICAL MECHANISMS (zuck 2026-11-03, tests/test_mechanism_parity.py), so this
is the Fusion latch GENERALISED, not a second copy of it: `daily_loss_latch` is the function the
Fusion rail already ran (`decision_core.fusion_daily_loss` now calls it, byte-for-byte the same
answers), and every prop lane calls `account_latch`, the same function over an account-keyed state
file. Only the THRESHOLD is per venue, read from `account_profile`:

    fusion  fusion-live has no venue limit       -> decision_core.FUSION_DAILY_LOSS_FRAC (5%)
    e8      e8-pro-v2 daily_circuit_breaker      -> 1.5% (2.5% daily x 60% utilisation)
    ftmo    ftmo-2step daily_circuit_breaker     -> 3.0% (5% daily x 60%); a declared tighter
                                                    daily limit (1-Step, 3%) tightens it to 1.8%

WHAT THE BREAKERS DO, AND WHAT THEY NEVER DO. They answer one question -- may this pass take NEW
risk? -- and the lane obeys by not sending a new order. They never close, modify or cancel an
open position or a resting order: the Fusion rail's one cancel of its resting gold brackets is
the Fusion rail's own and is unchanged; nothing here adds another. Management of what is open
runs before them and is untouched.

FAIL CLOSED, NEVER SILENT (L1.28a). An equity that cannot be read, a state file that cannot be
read, a tick that cannot be dated, or a terminal that did not answer refuses new risk as
UNMEASURED, with the reason named. An attribute the terminal object does not carry is not read as
False (a real `TerminalInfo`/`AccountInfo` always carries it); an explicit False is refused.

THE LEDGER. Every trip and every refusal is a line on the rails ledger
(`mt5desk.fusion_rails`, rails `account_daily_loss` and `account_disconnect`), with the account,
the lane, the state and the reason; `line_once` bills a refusal re-checked every pass once (per
lane, day and state; per hour for a disconnect). `research/missed_growth` publishes both.

PURE OVER ITS INPUTS EXCEPT FOR ITS OWN STATE FILE. No MetaTrader call is made here: each lane
hands in what it already read (equity, the terminal and account objects, the tick's stamp).

State: desks/mt5/data/account_breakers_state.json (box state, gitignored like its siblings).
"""
from __future__ import annotations

import contextlib
import json
import math
import os
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

_DESK = Path(__file__).resolve().parent.parent
STATE = _DESK / "data" / "account_breakers_state.json"

RAIL_DAILY_LOSS = "account_daily_loss"
RAIL_DISCONNECT = "account_disconnect"

#: A last quote older than this is no evidence the terminal is live, so no new order is sent on
#: it. Every lane reads a liquid symbol (XAUUSD, or the freshest of the FTMO clock symbols), which
#: ticks several times a second while its market is open; the Fusion gateway's own 30-minute idle
#: gate still decides "market closed" above this.
QUOTE_MAX_AGE_S = 120.0
#: A tick stamped this far AHEAD of the wall clock cannot be dated (box clock or broker clock
#: wrong); refused as UNMEASURED rather than read as fresh.
QUOTE_MAX_LEAD_S = 120.0

#: account -> the `account_profile` envelope whose daily limit sets its threshold.
ACCOUNT_PROFILE = {"fusion": "fusion-live", "e8": "e8-pro-v2", "ftmo": "ftmo-2step"}


class _NotRead:
    """The lane does not read this input at all (TradeLocker has no terminal) -- distinct from
    None, which is a read that returned nothing and refuses as UNMEASURED."""

    def __repr__(self) -> str:
        return "NOT_READ"


NOT_READ: Any = _NotRead()


@dataclass(frozen=True)
class Breaker:
    """One breaker's answer. `refuse` is the only field a lane obeys."""

    refuse: bool
    #: OK | TRIPPED (latched on this call) | STOOD_DOWN (latched earlier today) | UNMEASURED
    #: | DISCONNECTED | TRADE_DISABLED | STALE_QUOTE
    state: str
    why: str

    def as_dict(self) -> dict[str, Any]:
        return {"refuse": self.refuse, "state": self.state, "why": self.why}


# ------------------------------------------------------------------ the daily-loss latch
def trip_frac(account: str, declared_daily_limit: object = None) -> tuple[float, str]:
    """The fraction of the day's starting equity at which `account` stops taking new risk.

    The venue's own `daily_circuit_breaker` (deliberately inside its hard limit), else its
    `daily_loss_limit x LIMIT_UTILISATION`; a venue with neither (fusion-live) keeps the Fusion
    book's FUSION_DAILY_LOSS_FRAC. A declared daily limit TIGHTER than the profile's (an FTMO
    1-Step account declares 3%) tightens it in the same proportion; a looser one never loosens.
    """
    from mt5desk import account_profile as _ap
    prof = _ap.PROFILES.get(ACCOUNT_PROFILE.get(account, ""))
    if prof is None:
        # An account this file does not know is sized like an unknown prop account: tightest.
        prof = _ap.E8_PRO
    frac = prof.daily_circuit_breaker
    if frac is None and prof.daily_loss_limit is not None:
        frac = prof.daily_loss_limit * _ap.LIMIT_UTILISATION
    if frac is None:
        from mt5desk.decision_core import FUSION_DAILY_LOSS_FRAC
        return float(FUSION_DAILY_LOSS_FRAC), (f"{prof.name} has no venue daily limit; the "
                                               f"Fusion book's own {FUSION_DAILY_LOSS_FRAC:.1%}")
    why = f"{prof.name} daily circuit breaker {frac:.2%}"
    try:
        dec = float(declared_daily_limit)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        dec = float("nan")
    if (math.isfinite(dec) and 0.0 < dec and prof.daily_loss_limit is not None
            and dec < prof.daily_loss_limit):
        frac = frac * dec / prof.daily_loss_limit
        why += f", tightened to {frac:.2%} by the declared {dec:.0%} daily limit"
    return float(frac), why


def daily_loss_latch(st: dict[str, Any], equity: object, day_key: str, frac: float, *,
                     label: str) -> Breaker:
    """(stand down for the rest of the day?) Updates `st` in place. THE ONE LATCH.

    The day's starting equity is the first readable equity seen on `day_key` (anchored once and
    kept); a latch, once set for `day_key`, holds until the day changes. An unreadable equity
    stands the pass down (fail closed) without anchoring on it. Equity is balance plus floating,
    so an open loss counts the moment it is open.
    """
    try:
        eq = float(equity)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        eq = float("nan")
    if not (math.isfinite(eq) and eq > 0.0):
        return Breaker(True, "UNMEASURED", f"{label}: equity unreadable; no new risk this pass")
    anchor = st.get("day_start_equity")
    if not (isinstance(anchor, dict) and anchor.get("date") == day_key
            and isinstance(anchor.get("equity"), (int, float))
            and not isinstance(anchor.get("equity"), bool) and float(anchor["equity"]) > 0.0):
        anchor = {"date": day_key, "equity": round(eq, 2)}
        st["day_start_equity"] = anchor
    start = float(anchor["equity"])
    floor = start * (1.0 - frac)
    if st.get("daily_loss_stood_down") == day_key:
        return Breaker(True, "STOOD_DOWN", (f"{label}: stood down for {day_key} (start "
                                            f"{start:.2f}, floor {floor:.2f}, equity {eq:.2f})"))
    if eq <= floor:
        st["daily_loss_stood_down"] = day_key
        return Breaker(True, "TRIPPED", (f"{label}: equity {eq:.2f} reached {floor:.2f} "
                                         f"(-{round(frac * 100, 4):g}% of the day's start "
                                         f"{start:.2f}); no new "
                                         f"risk for the rest of {day_key}"))
    return Breaker(False, "OK", (f"{label}: equity {eq:.2f} above the {floor:.2f} floor "
                                 f"(start {start:.2f})"))


def _load(path: Path) -> tuple[dict[str, Any] | None, str]:
    if not path.exists():
        return {}, ""
    try:
        doc = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        return None, f"{path.name} unreadable ({type(exc).__name__})"
    if not isinstance(doc, dict):
        return None, f"{path.name} is not an object"
    return doc, ""


def _save(doc: dict[str, Any], path: Path) -> bool:
    """Whole-file write through a sibling, so a reader never sees half a file. Never raises."""
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_name(f"{path.name}.{os.getpid()}.tmp")
        tmp.write_text(json.dumps(doc, indent=1, sort_keys=True), encoding="utf-8")
        try:
            os.replace(tmp, path)
        except OSError:
            # Windows refuses a replace onto a file another lane holds open (WinError 5).
            with contextlib.suppress(OSError):
                tmp.unlink()
            path.write_text(json.dumps(doc, indent=1, sort_keys=True), encoding="utf-8")
        return True
    except OSError:
        return False


def account_latch(account: str, equity: object, day_key: str, *,
                  declared_daily_limit: object = None, path: Path | None = None) -> Breaker:
    """`daily_loss_latch` for a prop account, on this file's account-keyed state.

    The lanes of one account (E8 gold and the E8 executor) share one anchor and one latch: the
    venue's daily limit is the account's, not a lane's. A state file that cannot be read refuses
    this pass as UNMEASURED and is rewritten from this pass's equity (the next pass reads it).
    """
    p = path or STATE
    frac, fwhy = trip_frac(account, declared_daily_limit)
    label = f"{account} account daily-loss breaker ({fwhy})"
    doc, bad = _load(p)
    if doc is None:
        sub: dict[str, Any] = {}
        b = daily_loss_latch(sub, equity, day_key, frac, label=label)
        if b.state != "UNMEASURED":
            _save({account: sub}, p)
        return Breaker(True, "UNMEASURED", f"{label}: {bad}; no new risk this pass")
    sub = doc.get(account) if isinstance(doc.get(account), dict) else {}
    before = json.dumps(sub, sort_keys=True)
    b = daily_loss_latch(sub, equity, day_key, frac, label=label)
    if json.dumps(sub, sort_keys=True) != before:
        doc[account] = sub
        if not _save(doc, p) and b.state == "TRIPPED":
            # The latch lives in this pass only; the next pass re-measures the same equity.
            return Breaker(True, "TRIPPED", b.why + f" (latch NOT persisted to {p.name})")
    return b


# ------------------------------------------------------------------ the disconnect breaker
def tick_age_s(broker_epoch: object, now: datetime) -> float | None:
    """Seconds since a tick stamped on the broker clock (NY+7: Fusion's and E8's terminal, and
    FTMO's, which `ftmo_executor.clock_ok` holds to it), or None when it cannot be dated."""
    try:
        from mt5desk.broker_clock import broker_epoch_to_utc
        at = broker_epoch_to_utc(broker_epoch)
    except Exception:
        return None
    if at is None:
        return None
    ref = now if now.tzinfo is not None else now.replace(tzinfo=UTC)
    return float((ref - at.to_pydatetime()).total_seconds())


def _flag(obj: Any, name: str) -> bool | None:
    """True/False as the object states it; None when it carries no such boolean."""
    v = getattr(obj, name, None)
    return v if isinstance(v, bool) else None


def connection_breaker(*, tick_age: float | None, terminal: Any = NOT_READ,
                       account: Any = NOT_READ, max_age_s: float | None = None) -> Breaker:
    """May a NEW order go to this venue now? Refuses on a terminal that did not answer, says it
    is disconnected, or has trading switched off; on an account with trading switched off; and
    on a last quote older than `max_age_s` (QUOTE_MAX_AGE_S) or one that cannot be dated."""
    limit = QUOTE_MAX_AGE_S if max_age_s is None else float(max_age_s)
    if terminal is None:
        return Breaker(True, "UNMEASURED", "disconnect breaker: the terminal did not answer "
                                           "terminal_info; no new orders this pass")
    if not isinstance(terminal, _NotRead):
        if _flag(terminal, "connected") is False:
            return Breaker(True, "DISCONNECTED", "disconnect breaker: terminal_info().connected "
                                                 "is False (no broker connection); no new orders "
                                                 "this pass")
        if _flag(terminal, "trade_allowed") is False:
            return Breaker(True, "TRADE_DISABLED", "disconnect breaker: terminal_info()."
                                                   "trade_allowed is False (algo trading off); "
                                                   "no new orders this pass")
    if account is None:
        return Breaker(True, "UNMEASURED", "disconnect breaker: the account did not answer; no "
                                           "new orders this pass")
    if not isinstance(account, _NotRead) and _flag(account, "trade_allowed") is False:
        return Breaker(True, "TRADE_DISABLED", "disconnect breaker: account_info().trade_allowed "
                                               "is False; no new orders this pass")
    if tick_age is None or not math.isfinite(float(tick_age)):
        return Breaker(True, "UNMEASURED", "disconnect breaker: the last quote cannot be dated; "
                                           "no new orders this pass")
    if float(tick_age) < -QUOTE_MAX_LEAD_S:
        return Breaker(True, "UNMEASURED", (f"disconnect breaker: the last quote is stamped "
                                            f"{-float(tick_age):.0f}s in the future (a clock is "
                                            f"wrong); no new orders this pass"))
    if float(tick_age) > limit:
        return Breaker(True, "STALE_QUOTE", (f"disconnect breaker: the last quote is "
                                             f"{float(tick_age):.0f}s old (limit {limit:.0f}s); "
                                             f"no new orders this pass"))
    return Breaker(False, "OK", f"disconnect breaker: connected, last quote {float(tick_age):.0f}s "
                                f"old")


# ------------------------------------------------------------------ the ledger line
def bill(rail: str, b: Breaker, *, account: str, lane: str, day: str,
         now: datetime | None = None, **fields: Any) -> bool:
    """One rails-ledger line for a trip or a refusal, never for an OK. A trip is billed once per
    account and day (whichever lane saw it); a refusal once per lane, day and state -- and per
    UTC hour for a disconnect, so a second outage later in the day is its own line. Never
    raises (the ledger's own contract)."""
    if not b.refuse:
        return False
    from mt5desk import fusion_rails as _rails
    if b.state == "TRIPPED":
        key = f"{account}/{day}/TRIPPED"
    elif rail == RAIL_DISCONNECT:
        hour = (now or datetime.now(tz=UTC)).astimezone(UTC).strftime("%H")
        key = f"{account}/{lane}/{day}/{b.state}/{hour}"
    else:
        key = f"{account}/{lane}/{day}/{b.state}"
    return _rails.line_once(rail, key, account=account, lane=lane, state=b.state, why=b.why,
                            **fields)
