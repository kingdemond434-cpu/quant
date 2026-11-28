"""THE ACCOUNT BREAKERS: a daily-loss circuit breaker for a prop account, and a disconnect breaker.

WHY (BACKLOG 2026-10-13, the control room's two diagrams; spec in the project files at
patches/recovery_drills/account_circuit_breaker.md). A prop account is a BARRIER problem: touch the
venue's daily-loss line once and the account is gone, with no recovery to compound back from. The
desk had the venue's numbers (`account_profile.daily_loss_limit`) feeding a PRE-TRADE heat bar
only, so nothing watched the account's equity during the day and nothing flattened before the line.
This module is that watcher, for any account the gateway trades that is declared a prop account.

THE DAILY-LOSS BREAKER, step by step.

  1. THE RULE IS THE VENUE'S, NEVER A FIAT CUT. `rule_for_connected` reads the box's declaration
     (`account_profile.read_declarations`, the same file the heat bar reads) and returns the
     venue's own daily-loss fraction: E8 from `AccountProfile.daily_loss_limit` (2.5% Pro v2, 5.3%
     One 8%), FTMO from its published rules (5% 2-Step, 3% 1-Step, 10% maximum loss; the same
     numbers `prop/ftmo_follower.ACCOUNT_TYPES` enforces). `fusion-live` has no daily-loss rule, so
     the account half is NOT_APPLICABLE there and the main book is untouched: the 20% heat floor,
     the allocator's fractions and the Fusion rails are not read or changed by this file.
  2. THE LINE. floor = anchor - frac x base, where the anchor is the account at the VENUE's day
     boundary (E8: the higher of balance and equity at 17:00 New York, i.e. broker midnight on the
     New York + 7 clock; FTMO: the balance at midnight Prague) and the base is the anchor (E8) or
     the initial balance (FTMO): the first deposit in the account's deal history
     (`initial_balance`), or the declared one, which overrides it. With neither, the base is the
     day's anchor and the reading says UNMEASURED; orders are NOT held for it. A static
     maximum-loss floor, initial x (1 - max), binds too wherever the initial balance is known.
     The anchor is the MAX of every reading that can stand for it (the first reading of the
     day, the last reading of the previous day, and the day-start balance re-derived from the
     deal history), so a late first pass can only make the line stricter, never looser.
  3. THE BUFFER IS MEASURED, NEVER A FIXED CUT. The breaker can only act on its next reading, so
     the line it trips at must sit inside the venue's by the most the open book can lose in ONE
     BLIND INTERVAL plus the cost of closing it. Two measurements, and the smaller one binds
     (a cold-start fallback below covers the case where neither exists):
       * VOLATILITY OF OPEN RISK: every pass records |d equity| / open notional / sqrt(gap). The
         worst of those over the last trading week, scaled by the current open notional and the
         square root of the longest interval the gateway tolerates (step 5), is the move the book
         has actually shown it can make between two readings. Measured only once a venue day of
         readings exists (`MIN_READINGS`); until then it is UNMEASURED and not used.
       * THE STOP BOUND: when every open position and resting order carries a stop, the book
         cannot lose more than the distance to those stops before they fire.
     Both add the live spread to close the whole book. With no open risk the buffer is 0 and the
     breaker trips exactly at the venue's line, because nothing can move it further.
       * COLD START (audit HOLD on 94a6d4e7, should-fix 2): before a day of readings exists AND
         with a leg that has no stop, each such leg is priced at `FALLBACK_ATR_MULT` x its
         instrument's measured M1 ATR (`ATR_BARS` bars from the terminal), scaled to the blind
         interval, and stopped legs at their stops. The source reads "fallback". New orders are
         not refused for it; only a leg whose bars cannot be read leaves the buffer UNMEASURED.
  4. TRIP, CONFIRMED. equity <= floor + buffer, read twice (`CONFIRM_READS`, the deadman's rule:
     one torn read must not flatten a healthy book). Then, for the rest of the VENUE day: every new
     order is refused, resting orders are cancelled and every position is closed (the diagram's
     flatten), re-done on each pass while anything remains. It resets itself at the venue's next
     day boundary; no person is needed to re-arm it.
  5. NEW ORDERS THAT WOULD ENTER THE TRIP ZONE are refused at the order door (`open_gate`): an
     order whose own notional and stop would push the buffer past the room left. Without it an
     order could be sent and flattened on the next pass, paying the spread twice for nothing.

THE DISCONNECT BREAKER. Nothing is sent while the terminal reports no broker connection or the
account cannot be read (checked again at the door, on every new order). A gap between two gateway
readings longer than the gateway's own measured cadence allows (`gap_threshold`: Tukey's far-out
fence, Q3 + 3 IQR, over the last venue day of measured gaps; one missed pass, 2 x the resident
cadence, until a day is measured) means the heartbeat was lost. After it, or after any reading the
terminal could not give, NEW orders wait until `order_door.restart_reconcile` has read the venue
and answered OK on a pass. It never closes, opens or resizes anything: it cannot widen risk.

GROWTH GOVERNANCE (docs/GROWTH_GOVERNANCE.md). Both are survival rails, not growth caps. Rule 1: on
a barrier account a breach is a terminal loss (log W of the account goes to its fee), so a trip
that keeps the account alive raises robust forward E[log W]; the buffer is the measured one-interval
loss, so the breaker gives up only the part of a day the venue would otherwise be entitled to end.
Rule 2 / two-sided: the buffer shrinks as open risk and its measured volatility shrink (to zero
with a flat book), so the breaker never sits further inside the venue's line than the book needs.
Every refusal and every trip is a missed-growth line on the rails ledger (rails
`account_daily_breaker` and `disconnect_breaker`, `mt5desk.fusion_rails`), carried into
MISSED_GROWTH.json by `research/missed_growth.published_fusion_book_lines`.

State (the box's, gitignored): desks/mt5/data/account_breaker_state.json -- written every pass.
"""
from __future__ import annotations

import contextlib
import itertools
import json
import math
import os
import statistics
from collections.abc import Callable, Iterable, Mapping
from dataclasses import asdict, dataclass, field
from datetime import UTC, date, datetime, time, timedelta
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from mt5desk import account_profile as _acct

_DESK = Path(__file__).resolve().parent.parent
_ROOT = _DESK.parent.parent
STATE = _DESK / "data" / "account_breaker_state.json"

# ------------------------------------------------------------------ the venues' own rules
#: The broker clock is New York + 7 h (libs/regime/session_clock), so the broker's midnight is
#: 17:00 New York. E8 and Fusion roll their day there.
NY_TZ, NY_ROLL_HOUR = "America/New_York", 17
#: FTMO resets its daily loss at midnight CE(S)T (ftmo.com trading objectives; the same anchor
#: `prop/ftmo_follower` measures from).
PRAGUE_TZ, PRAGUE_ROLL_HOUR = "Europe/Prague", 0
#: FTMO's published rules: daily loss by account type, of the INITIAL balance, and the 10%
#: maximum loss. Pinned equal to `prop/ftmo_follower.ACCOUNT_TYPES` / `MAX_LOSS_FRAC` by a test.
FTMO_DAILY = {"ftmo-2step": 0.05, "ftmo-1step": 0.03}
FTMO_MAX_LOSS = 0.10


@dataclass(frozen=True)
class VenueRule:
    """One venue's daily-loss rule, as the venue measures it."""

    name: str
    daily_loss_frac: float
    max_loss_frac: float | None
    #: "anchor": the limit is a fraction of the day's anchor; "initial": of the initial balance.
    base: str
    #: "max_balance_equity" or "balance": what the anchor reads at the day boundary.
    anchor_on: str
    day_tz: str
    day_roll_hour: int


def _derive_rules() -> dict[str, VenueRule]:
    rules: dict[str, VenueRule] = {}
    for prof in _acct.PROFILES.values():
        if prof.daily_loss_limit is None:
            continue
        # E8 measures its daily drawdown from the day's starting balance or equity; the anchor
        # reads the HIGHER of the two, which is the line under either reading.
        rules[prof.name] = VenueRule(prof.name, float(prof.daily_loss_limit),
                                     prof.max_drawdown_limit, "anchor", "max_balance_equity",
                                     NY_TZ, NY_ROLL_HOUR)
    for name, frac in FTMO_DAILY.items():
        rules[name] = VenueRule(name, frac, FTMO_MAX_LOSS, "initial", "balance",
                                PRAGUE_TZ, PRAGUE_ROLL_HOUR)
    return rules


#: Every venue rule the breaker knows, derived from the profiles (never restated).
RULES: dict[str, VenueRule] = _derive_rules()

# ------------------------------------------------------------------ the measured parts
#: The resident gateway's cadence contract (research/gateway_resident.INTERVAL_S, pinned by a
#: test). Used only before the real cadence is measured.
CADENCE_S = 60.0
#: One venue day of readings at that cadence: the least history the breaker calls MEASURED, so the
#: worst move in it is at least the worst single-interval move of one whole day.
DAY_S = 86_400.0
MIN_READINGS = int(DAY_S / CADENCE_S)
#: The disconnect threshold before a day of gaps is measured: one whole missed pass.
FALLBACK_GAP_S = 2.0 * CADENCE_S
#: Tukey's far-out fence: a gap beyond Q3 + 3 x IQR of the measured gaps is not the gateway's
#: ordinary rhythm. A statistical convention, not a desk-chosen risk number.
TUKEY_FAR_OUT = 3.0
#: The volatility window: the last trading week of per-day maxima, so a weekly event (payrolls,
#: the Friday close) is always inside it.
Z_DAYS = 5
#: THE COLD-START FALLBACK (should-fix 2): a stopless leg, before volatility is measured, is priced
#: at this many of its instrument's M1 ATRs per sqrt(minute) of blind interval -- the same far-out
#: multiple as the gap fence, so "a move the bars call an outlier" is the one convention used.
FALLBACK_ATR_MULT = TUKEY_FAR_OUT
#: M1 bars behind that ATR (Wilder's 14).
ATR_BARS = 14
#: MetaTrader's DEAL_TYPE_BALANCE: a deposit or withdrawal, the first of which is the initial
#: balance a prop firm measures its limits from.
DEAL_TYPE_BALANCE = 2
#: Two consecutive reads of the same breach before acting (proposals/fusion_deadman.CONFIRM_READS).
CONFIRM_READS = 2

UNMEASURED = "UNMEASURED"

# MetaTrader's documented constants, used when the module in hand (a fake, an old build) lacks one.
_POSITION_BUY = 0
_BUY_ORDER_TYPES = frozenset({2, 4, 6})      # BUY_LIMIT, BUY_STOP, BUY_STOP_LIMIT
_SELL_ORDER_TYPES = frozenset({3, 5, 7})     # SELL_LIMIT, SELL_STOP, SELL_STOP_LIMIT


def _num(x: object) -> float | None:
    if isinstance(x, bool) or not isinstance(x, (int, float)):
        return None
    v = float(x)
    return v if math.isfinite(v) else None


# ------------------------------------------------------------------ the venue day
def venue_day(now: datetime, tz: str = NY_TZ, roll_hour: int = NY_ROLL_HOUR) -> str:
    """The venue's trading day at `now` (YYYY-MM-DD): it rolls at `roll_hour` local to `tz`."""
    local = now.astimezone(ZoneInfo(tz))
    if roll_hour:
        local = local + timedelta(hours=24 - roll_hour)
    return local.strftime("%Y-%m-%d")


def venue_day_start(day: str, tz: str = NY_TZ, roll_hour: int = NY_ROLL_HOUR) -> datetime:
    """The UTC instant venue day `day` began."""
    d = date.fromisoformat(day)
    if roll_hour:
        d = d - timedelta(days=1)
    return datetime.combine(d, time(roll_hour), tzinfo=ZoneInfo(tz)).astimezone(UTC)


def broker_epoch(at: datetime) -> float:
    """`at` as MetaTrader stamps it: New York + 7 h wall time read as if it were UTC."""
    ny = at.astimezone(ZoneInfo(NY_TZ))
    off = ny.utcoffset() or timedelta(0)
    return at.timestamp() + (off + timedelta(hours=7)).total_seconds()


# ------------------------------------------------------------------ which rule binds
def _declarations_raw(root: Path) -> dict[str, Any]:
    p = root / Path(*_acct.DECLARATIONS_REL.split("/"))
    try:
        raw = json.loads(p.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return raw if isinstance(raw, dict) else {}


def rule_for_connected(acc: Mapping[str, Any] | None, root: Path = _ROOT
                       ) -> tuple[VenueRule | None, float | None, str]:
    """(the rule binding the connected account or None, its declared initial balance, why).

    No declaration file: the desk runs no declared prop account, nothing binds (the main book
    is untouched). A declared profile without a daily rule (`fusion-live`): nothing binds. An
    account the file does not name, or names with no known venue rule: nothing binds either --
    only a DECLARED prop account is held to a prop line (the disconnect breaker covers every
    account). The declared initial balance is the file's optional "initial_balances" object
    ({"<login>@<server>": number}), an OVERRIDE of the one `initial_balance` measures from the
    deal history; the login never leaves this function."""
    declared, why = _acct.read_declarations(root)
    if declared is None:
        return None, None, f"{why}; no prop account is declared, no daily-loss rule binds"
    key = _acct.declaration_key(dict(acc) if acc else None)
    # ONLY A DECLARED PROP ACCOUNT BINDS (audit HOLD on 94a6d4e7, should-fix 1). An account the
    # file does not name -- the Fusion main book on a box that also declares a prop account --
    # is not held to any prop line: failing it closed to E8 Pro would stop the growth book at
    # -2.5% on an ordinary day. The disconnect breaker still covers it.
    initial: float | None = None
    if key is not None:
        ib = _declarations_raw(root).get("initial_balances")
        if isinstance(ib, dict):
            v = _num(ib.get(key))
            initial = v if v is not None and v > 0 else None
    name = declared.get(key) if key is not None else None
    if name is None:
        return None, None, (f"the connected account is not declared a prop account ({why}); "
                            f"no daily-loss rule binds")
    if name in RULES:
        return RULES[name], initial, f"declared {name} ({why})"
    prof = _acct.PROFILES.get(name)
    if prof is not None and prof.daily_loss_limit is None:
        return None, initial, f"declared {name}, which has no daily-loss rule"
    return None, initial, (f"declared {name!r}, which names no known venue rule "
                           f"({', '.join(sorted(RULES))}); NO daily-loss rule binds -- fix the "
                           f"declaration")


# ------------------------------------------------------------------ one reading of the account
@dataclass
class Reading:
    """The account, read once. Amounts are in the account's currency."""

    t: float
    connected: bool
    equity: float | None = None
    balance: float | None = None
    #: Open notional: positions, plus the larger side of each symbol's resting orders.
    notional: float = 0.0
    #: What the book loses if every stop fires; inf when any leg has no stop or is unreadable.
    stop_bound: float = 0.0
    #: The spread to close every position (and the larger resting side).
    close_cost: float = 0.0
    #: The cold-start fallback's two parts: the stop risk of the legs that HAVE a stop, and
    #: sum(volume x value-per-price x M1 ATR) of the legs that do not (inf if a bar is unreadable).
    stopped_risk: float = 0.0
    atr_unit: float = 0.0
    n_positions: int = 0
    n_orders: int = 0
    symbols: list[str] = field(default_factory=list)
    why: str = ""

    @property
    def ok(self) -> bool:
        return self.connected and self.equity is not None and self.balance is not None


def _value_per_price(mt5: Any, symbol: str, cache: dict[str, tuple[float, float] | None]
                     ) -> tuple[float, float] | None:
    """(account currency per 1.0 of price per lot, live spread), or None if unreadable."""
    if symbol in cache:
        return cache[symbol]
    out: tuple[float, float] | None = None
    with contextlib.suppress(Exception):
        info = mt5.symbol_info(symbol)
        tick = mt5.symbol_info_tick(symbol)
        tv = _num(getattr(info, "trade_tick_value", None))
        ts = _num(getattr(info, "trade_tick_size", None))
        bid = _num(getattr(tick, "bid", None))
        ask = _num(getattr(tick, "ask", None))
        if tv and ts and tv > 0 and ts > 0 and bid and ask and ask >= bid:
            out = (tv / ts, ask - bid)
    cache[symbol] = out
    return out


def atr_m1(mt5: Any, symbol: str, cache: dict[str, float | None] | None = None
           ) -> float | None:
    """The instrument's mean true range over the last `ATR_BARS` closed M1 bars, from the
    terminal's own bars. None when they cannot be read."""
    if cache is not None and symbol in cache:
        return cache[symbol]
    out: float | None = None
    with contextlib.suppress(Exception):
        tf = getattr(mt5, "TIMEFRAME_M1", 1)
        rates = mt5.copy_rates_from_pos(symbol, tf, 1, ATR_BARS + 1)
        rows = list(rates) if rates is not None else []
        trs: list[float] = []
        for prev, cur in itertools.pairwise(rows):
            hi, lo, pc = _num(cur["high"]), _num(cur["low"]), _num(prev["close"])
            if hi is None or lo is None or pc is None:
                continue
            trs.append(max(hi - lo, abs(hi - pc), abs(lo - pc)))
        if len(trs) >= ATR_BARS // 2:
            out = sum(trs) / len(trs)
    if cache is not None:
        cache[symbol] = out
    return out


def _leg(volume: object, price: object, sl: object, buy: bool,
         vps: tuple[float, float] | None, atr: float | None = None
         ) -> tuple[float, float, float, float, float]:
    """(notional, stop risk, close cost, stopped risk, atr unit) of one leg; inf where it cannot
    be priced. A leg with a stop has atr unit 0; one without has stopped risk 0."""
    vol, px = _num(volume), _num(price)
    if vps is None or vol is None or px is None or vol <= 0 or px <= 0:
        return math.inf, math.inf, math.inf, math.inf, math.inf
    vpp, spread = vps
    stop = _num(sl)
    if stop is not None and stop > 0:
        risk = vol * vpp * max(0.0, (px - stop) if buy else (stop - px))
        return vol * vpp * px, risk, vol * vpp * spread, risk, 0.0
    unit = vol * vpp * atr if atr is not None else math.inf
    return vol * vpp * px, math.inf, vol * vpp * spread, 0.0, unit


def read_account(mt5: Any, now: datetime | None = None) -> Reading:
    """Read the account once. Never raises: what cannot be read is named in `why`."""
    at = (now or datetime.now(tz=UTC)).timestamp()
    try:
        ti = mt5.terminal_info()
    except Exception as exc:
        return Reading(at, False, why=f"terminal_info raised {type(exc).__name__}")
    if ti is None or getattr(ti, "connected", True) is False:
        return Reading(at, False, why=("the terminal is not running" if ti is None
                                       else "the terminal has no broker connection"))
    try:
        ai = mt5.account_info()
    except Exception as exc:
        return Reading(at, False, why=f"account_info raised {type(exc).__name__}")
    eq, bal = _num(getattr(ai, "equity", None)), _num(getattr(ai, "balance", None))
    if ai is None or eq is None or bal is None:
        return Reading(at, False, why="the account could not be read")
    r = Reading(at, True, equity=eq, balance=bal)
    cache: dict[str, tuple[float, float] | None] = {}
    atrs: dict[str, float | None] = {}

    def _atr_if_stopless(sym: str, sl: object) -> float | None:
        stop = _num(sl)
        return None if stop is not None and stop > 0 else atr_m1(mt5, sym, atrs)

    syms: set[str] = set()
    try:
        positions = list(mt5.positions_get() or ())
        orders = list(mt5.orders_get() or ())
    except Exception as exc:
        r.notional = r.stop_bound = r.close_cost = r.stopped_risk = r.atr_unit = math.inf
        r.why = f"positions/orders unreadable ({type(exc).__name__}); open risk unbounded"
        return r
    pos_buy = int(getattr(mt5, "POSITION_TYPE_BUY", _POSITION_BUY))
    for p in positions:
        sym = str(getattr(p, "symbol", "") or "")
        syms.add(sym)
        sl = getattr(p, "sl", None)
        n, s, c, sr, au = _leg(getattr(p, "volume", None), getattr(p, "price_current", None),
                               sl, int(getattr(p, "type", -1)) == pos_buy,
                               _value_per_price(mt5, sym, cache), _atr_if_stopless(sym, sl))
        r.notional += n
        r.stop_bound += s
        r.close_cost += c
        r.stopped_risk += sr
        r.atr_unit += au
    # A RESTING ORDER IS RISK THAT CAN ARRIVE BETWEEN TWO READINGS. Per symbol, the larger side
    # is counted: a bracket's two legs are one trade, and its sibling is cancelled on the fill.
    sides: dict[tuple[str, bool], list[float]] = {}
    zero = [0.0] * 5
    for o in orders:
        typ = int(getattr(o, "type", -1))
        if typ not in _BUY_ORDER_TYPES and typ not in _SELL_ORDER_TYPES:
            continue
        sym = str(getattr(o, "symbol", "") or "")
        syms.add(sym)
        buy = typ in _BUY_ORDER_TYPES
        vol = getattr(o, "volume_current", None)
        if _num(vol) is None:
            vol = getattr(o, "volume_initial", None)
        osl = getattr(o, "sl", None)
        legs = _leg(vol, getattr(o, "price_open", None), osl, buy,
                    _value_per_price(mt5, sym, cache), _atr_if_stopless(sym, osl))
        acc = sides.setdefault((sym, buy), list(zero))
        for i in range(5):
            acc[i] += legs[i]
    for sym in {k[0] for k in sides}:
        b, s_ = sides.get((sym, True), zero), sides.get((sym, False), zero)
        worse = b if b[0] >= s_[0] else s_
        r.notional += worse[0]
        r.stop_bound += max(b[1], s_[1])
        r.close_cost += worse[2]
        r.stopped_risk += max(b[3], s_[3])
        r.atr_unit += max(b[4], s_[4])
    r.n_positions, r.n_orders = len(positions), len(orders)
    r.symbols = sorted(x for x in syms if x)
    return r


def day_start_balance(mt5: Any, balance: float, day: str, rule_tz: str = NY_TZ,
                      roll_hour: int = NY_ROLL_HOUR, now: datetime | None = None
                      ) -> float | None:
    """The balance at the venue day's start: today's balance less every deal since. None when the
    history cannot be read or a deal carries no readable time (never guessed)."""
    start = venue_day_start(day, rule_tz, roll_hour)
    end = now or datetime.now(tz=UTC)
    try:
        deals = mt5.history_deals_get(start - timedelta(days=1), end + timedelta(days=1))
    except Exception:
        return None
    if deals is None:
        return None
    since = broker_epoch(start)
    moved = 0.0
    for d in deals:
        ts = _num(getattr(d, "time", None))
        if ts is None or ts <= 0:
            return None
        if ts < since:
            continue
        for k in ("profit", "commission", "swap", "fee"):
            moved += _num(getattr(d, k, 0.0)) or 0.0
    return balance - moved


def initial_balance(mt5: Any, now: datetime | None = None) -> float | None:
    """The account's initial balance, MEASURED: the first deposit (a DEAL_TYPE_BALANCE deal with a
    positive amount) in its whole deal history. None when the history is unreadable or holds no
    deposit. A prop account's history is short, so the wide query is cheap; the gateway caches
    the answer in the breaker state once found."""
    end = (now or datetime.now(tz=UTC)) + timedelta(days=1)
    try:
        deals = mt5.history_deals_get(datetime(2000, 1, 1, tzinfo=UTC), end)
    except Exception:
        return None
    if not deals:
        return None
    first: tuple[float, float] | None = None
    for d in deals:
        if int(_num(getattr(d, "type", -1)) or -1) != DEAL_TYPE_BALANCE:
            continue
        amt, ts = _num(getattr(d, "profit", None)), _num(getattr(d, "time", None))
        if amt is None or amt <= 0 or ts is None:
            continue
        if first is None or ts < first[0]:
            first = (ts, amt)
    return None if first is None else first[1]


# ------------------------------------------------------------------ the measured quantities
def gap_threshold(gaps: Iterable[float]) -> tuple[float, str]:
    """The longest gap between two readings the gateway's own rhythm explains, and its basis."""
    g = sorted(x for x in gaps if x > 0 and math.isfinite(x))
    if len(g) < MIN_READINGS:
        return FALLBACK_GAP_S, (f"{UNMEASURED}: {len(g)} of {MIN_READINGS} gaps; one missed "
                                f"pass ({FALLBACK_GAP_S:.0f}s)")
    q1, _, q3 = statistics.quantiles(g, n=4)
    fence = q3 + TUKEY_FAR_OUT * (q3 - q1)
    return max(fence, g[len(g) // 2]), (f"measured: Q3 {q3:.0f}s + {TUKEY_FAR_OUT:g} IQR over "
                                        f"{len(g)} gaps")


def z_max(z_days: Mapping[str, Any]) -> tuple[float | None, int]:
    """(the worst normalised move in the window, readings behind it); None until MEASURED."""
    worst, n = 0.0, 0
    for v in z_days.values():
        if isinstance(v, list) and len(v) == 2:
            m, k = _num(v[0]), _num(v[1])
            if m is not None and k is not None:
                worst, n = max(worst, m), n + int(k)
    return (worst if n >= MIN_READINGS else None), n


def buffer_for(notional: float, stop_bound: float, close_cost: float,
               zmax: float | None, horizon_s: float, *, stopped_risk: float = math.inf,
               atr_unit: float = math.inf) -> tuple[float | None, str]:
    """The measured buffer: the smaller of the volatility and stop bounds, plus the close cost.
    When neither exists (cold start with a stopless leg), the ATR fallback: stopped legs at their
    stops, stopless legs at FALLBACK_ATR_MULT M1 ATRs per sqrt(minute) of `horizon_s`. None only
    when even that cannot be priced (the caller then holds new risk)."""
    if notional <= 0 and stop_bound <= 0:
        cc = close_cost if math.isfinite(close_cost) else 0.0
        return cc, "no open risk: the line is the venue's own"
    cands: list[tuple[float, str]] = []
    if zmax is not None and math.isfinite(notional):
        cands.append((notional * zmax * math.sqrt(horizon_s),
                      f"volatility: notional {notional:,.2f} x worst move {zmax:.3g}/sqrt(s) x "
                      f"sqrt({horizon_s:.0f}s)"))
    if math.isfinite(stop_bound):
        cands.append((stop_bound, f"stops: {stop_bound:,.2f} to every stop"))
    if not cands and math.isfinite(stopped_risk) and math.isfinite(atr_unit) \
            and math.isfinite(close_cost):
        fb = stopped_risk + atr_unit * FALLBACK_ATR_MULT * math.sqrt(horizon_s / 60.0)
        return fb + close_cost, (f"fallback (cold start): stops {stopped_risk:,.2f} + "
                                 f"{FALLBACK_ATR_MULT:g} M1 ATR x {atr_unit:,.2f} x "
                                 f"sqrt({horizon_s:.0f}s/60) + close {close_cost:,.2f}")
    if not cands or not math.isfinite(close_cost):
        return None, (f"{UNMEASURED}: volatility "
                      f"{'unmeasured' if zmax is None else 'measured'}, "
                      f"{'a leg has no stop' if not math.isfinite(stop_bound) else 'stops priced'}"
                      f"{', close cost unpriced' if not math.isfinite(close_cost) else ''}")
    best = min(cands)
    return best[0] + close_cost, f"{best[1]} + close {close_cost:,.2f}"


# ------------------------------------------------------------------ the verdict
@dataclass
class Verdict:
    day: str
    applicable: bool
    rule: str | None
    rule_why: str
    connected: bool
    equity: float | None = None
    floor: float | None = None
    buffer: float | None = None
    buffer_why: str = ""
    trip_line: float | None = None
    tripped: bool = False
    newly_tripped: bool = False
    flatten_symbols: list[str] = field(default_factory=list)
    reconcile_required: bool = False
    gap_s: float | None = None
    gap_threshold_s: float = FALLBACK_GAP_S
    gap_basis: str = ""
    #: The worst measured normalised move behind the buffer (None while UNMEASURED).
    zmax: float | None = None
    #: The initial balance the max-loss floor (and an "initial"-based limit) used, and its source.
    initial: float | None = None
    initial_source: str = ""
    account_ok: bool = True
    why: str = ""

    @property
    def new_risk_ok(self) -> bool:
        return (self.connected and not self.reconcile_required and not self.tripped
                and self.account_ok)

    def as_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["new_risk_ok"] = self.new_risk_ok
        return {k: (None if isinstance(v, float) and not math.isfinite(v) else v)
                for k, v in d.items()}


def load_state(path: Path | None = None) -> dict[str, Any]:
    """The breakers' state, or {} when absent or unreadable (the anchor is then re-derived)."""
    path = path or STATE
    try:
        doc = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return doc if isinstance(doc, dict) else {}


def save_state(state: Mapping[str, Any], path: Path | None = None) -> None:
    """Whole-file write through a sibling; Windows' WinError 5 on os.replace falls back in place."""
    path = path or STATE
    path.parent.mkdir(parents=True, exist_ok=True)
    body = json.dumps(state, indent=1, default=str)
    tmp = path.with_name(f"{path.name}.{os.getpid()}.tmp")
    try:
        tmp.write_text(body, encoding="utf-8")
        os.replace(tmp, path)
    except OSError:
        with contextlib.suppress(OSError):
            tmp.unlink()
        path.write_text(body, encoding="utf-8")


def _sub(state: Mapping[str, Any], key: str) -> dict[str, Any]:
    """`state[key]` when it is a JSON object, else a fresh empty one (never None)."""
    v = state.get(key)
    return dict(v) if isinstance(v, dict) else {}


def _anchor_value(rule: VenueRule, balance: float | None, equity: float | None) -> float | None:
    if balance is None:
        return None
    if rule.anchor_on == "balance" or equity is None:
        return balance
    return max(balance, equity)


def _record(state: dict[str, Any], r: Reading, day: str) -> float | None:
    """Fold one good reading into the measured gap and volatility windows; returns the gap."""
    last = state.get("last") if isinstance(state.get("last"), dict) else None
    gap = None
    if last is not None:
        lt, le, ln = _num(last.get("t")), _num(last.get("equity")), _num(last.get("notional"))
        if lt is not None and r.t > lt:
            gap = r.t - lt
            gaps = [x for x in (state.get("gaps") or []) if _num(x) is not None]
            gaps.append(round(gap, 1))
            state["gaps"] = gaps[-MIN_READINGS:]
            if le is not None and ln is not None and ln > 0 and r.equity is not None:
                z = abs(r.equity - le) / ln / math.sqrt(gap)
                zd = _sub(state, "z_days")
                raw = zd.get(day)
                cur: list[Any] = raw if isinstance(raw, list) and len(raw) == 2 else [0.0, 0]
                zd[day] = [max(float(cur[0]), z), int(cur[1]) + 1]
                state["z_days"] = {k: zd[k] for k in sorted(zd)[-Z_DAYS:]}
    state["last"] = {"t": r.t, "day": day, "equity": r.equity, "balance": r.balance,
                     "notional": r.notional if math.isfinite(r.notional) else None}
    return gap


def evaluate(state: dict[str, Any], reading: Reading, rule: VenueRule | None,
             initial: float | None, rule_why: str, *,
             derived_start_balance: float | None = None,
             measured_initial: float | None = None,
             confirm: Callable[[], Reading] | None = None) -> Verdict:
    """One pass of both breakers. Mutates `state`; the caller persists it and acts on the
    verdict (flatten `flatten_symbols`, and refuse new risk unless `new_risk_ok`)."""
    now = datetime.fromtimestamp(reading.t, tz=UTC)
    tz, hour = (rule.day_tz, rule.day_roll_hour) if rule else (NY_TZ, NY_ROLL_HOUR)
    day = venue_day(now, tz, hour)
    thr, basis = gap_threshold(state.get("gaps") or [])
    v = Verdict(day=day, applicable=rule is not None, rule=rule.name if rule else None,
                rule_why=rule_why, connected=reading.ok, equity=reading.equity,
                gap_threshold_s=thr, gap_basis=basis)
    disc = _sub(state, "disconnect")
    # ---- the disconnect breaker
    if not reading.ok:
        disc.setdefault("since", now.isoformat(timespec="seconds"))
        disc["reconcile_required"] = True
        disc["why"] = reading.why
        state["disconnect"] = disc
        v.reconcile_required = True
        v.why = f"disconnected: {reading.why}; no new orders"
        tr = state.get("tripped")
        v.tripped = isinstance(tr, dict) and tr.get("day") == day
        return v
    last_day = (state.get("last") or {}).get("day") if isinstance(state.get("last"), dict) \
        else None
    prev_last = dict(state["last"]) if isinstance(state.get("last"), dict) else None
    gap = _record(state, reading, day)
    v.gap_s = gap
    if prev_last is None:
        disc["reconcile_required"] = True
        disc["why"] = "no earlier reading: the venue is reconciled before the first new order"
    elif gap is not None and gap > thr:
        disc["reconcile_required"] = True
        disc["why"] = f"heartbeat lost for {gap:.0f}s (> {thr:.0f}s, {basis})"
        disc.setdefault("since", datetime.fromtimestamp(reading.t - gap, tz=UTC)
                        .isoformat(timespec="seconds"))
    state["disconnect"] = disc
    v.reconcile_required = bool(disc.get("reconcile_required"))
    # ---- the daily-loss breaker
    if rule is None:
        state.pop("tripped", None)
        v.why = rule_why
        return v
    anchor = _sub(state, "anchor")
    if anchor.get("day") != day:
        cands = [_anchor_value(rule, reading.balance, reading.equity)]
        # The previous day's LAST reading stands for this day's anchor only when it was taken
        # within one tolerated gap of the boundary; an older one (a weekend, a dead gateway)
        # describes some other moment and is not used.
        boundary = venue_day_start(day, tz, hour).timestamp()
        prev_t = _num(prev_last.get("t")) if prev_last is not None else None
        if (prev_last is not None and last_day is not None and last_day < day
                and prev_t is not None and boundary - thr <= prev_t <= boundary):
            cands.append(_anchor_value(rule, _num(prev_last.get("balance")),
                                       _num(prev_last.get("equity"))))
        anchor = {"day": day, "value": max(c for c in cands if c is not None),
                  "fresh": prev_last is None or last_day != day}
    if derived_start_balance is not None:
        anchor["value"] = max(float(anchor["value"]), derived_start_balance)
        anchor.pop("unmeasured", None)
    elif anchor.get("fresh") and last_day != day and prev_last is None:
        # First reading ever, mid-day, with no deal history: the loss before it is unknown.
        anchor["unmeasured"] = True
    state["anchor"] = anchor
    tr = state.get("tripped") if isinstance(state.get("tripped"), dict) else None
    if tr is not None and tr.get("day") != day:
        state.pop("tripped", None)          # the venue day rolled: the breaker re-arms itself
        tr = None
    av = float(anchor["value"])
    # THE INITIAL BALANCE (audit HOLD on 94a6d4e7, must-fix): the declared figure overrides the
    # one measured from the deal history's first deposit; with neither, the day's anchor stands
    # in as the base and the reading says UNMEASURED -- orders are NOT held for it (holding them
    # took a declared FTMO account dark on the day it was due to trade).
    if initial is not None:
        v.initial, v.initial_source = initial, "declared"
    elif measured_initial is not None:
        initial = measured_initial
        v.initial, v.initial_source = initial, "deal history: first deposit"
    else:
        v.initial_source = (f"{UNMEASURED}: no declared initial balance and no deposit in the "
                            f"deal history; the day's anchor stands in"
                            + ("" if rule.base != "initial" else
                               f" as {rule.name}'s base, the max-loss floor is not applied"))
    if anchor.get("unmeasured"):
        v.account_ok = False
        v.why = ("the day's anchor is unmeasured (no earlier reading and no deal history); "
                 "no new orders until the venue day rolls or the history reads")
        return v
    base = initial if rule.base == "initial" and initial is not None else av
    floor = av - rule.daily_loss_frac * base
    if rule.max_loss_frac is not None and initial is not None:
        floor = max(floor, initial * (1.0 - rule.max_loss_frac))
    zm, _n = z_max(state.get("z_days") or {})
    buf, bwhy = buffer_for(reading.notional, reading.stop_bound, reading.close_cost, zm, thr,
                           stopped_risk=reading.stopped_risk, atr_unit=reading.atr_unit)
    v.floor, v.buffer, v.buffer_why, v.zmax = floor, buf, bwhy, zm
    eq = float(reading.equity or 0.0)
    line = floor + (buf if buf is not None else 0.0)
    v.trip_line = line
    if tr is not None:
        v.tripped = True
        v.flatten_symbols = reading.symbols
        v.why = f"tripped for {day} at {tr.get('at')}: {tr.get('why')}"
        return v
    if buf is None:
        v.account_ok = False
        v.why = f"buffer {bwhy}; no new orders"
    if eq > line:
        if v.account_ok:
            v.why = (f"equity {eq:,.2f} above the trip line {line:,.2f} (venue floor "
                     f"{floor:,.2f}, buffer {bwhy})")
        return v
    # CONFIRMED BEFORE ACTING: a second, independent read of the account.
    reads = [reading]
    while confirm is not None and len(reads) < CONFIRM_READS:
        again = confirm()
        if not again.ok or (again.equity or 0.0) > line:
            v.why = (f"equity {eq:,.2f} reached the trip line {line:,.2f} once; the confirming "
                     f"read did not ({again.why or again.equity}); not tripped")
            return v
        reads.append(again)
    if len(reads) < CONFIRM_READS:
        v.why = f"equity {eq:,.2f} at the trip line {line:,.2f}; awaiting a confirming read"
        return v
    why = (f"equity {eq:,.2f} <= trip line {line:,.2f} = venue floor {floor:,.2f} "
           f"({rule.daily_loss_frac:.2%} {rule.name}) + buffer {bwhy}")
    state["tripped"] = {"day": day, "at": now.isoformat(timespec="seconds"),
                        "equity": round(eq, 2), "floor": round(floor, 2),
                        "buffer": None if buf is None else round(buf, 2), "why": why}
    v.tripped = v.newly_tripped = True
    v.flatten_symbols = reading.symbols
    v.why = why
    return v


def note_reconcile(state: dict[str, Any], verdict: object) -> bool:
    """The gateway's restart reconcile answered `verdict` this pass. An OK clears a pending
    reconcile requirement (orders resume); anything else keeps it. Returns whether it cleared."""
    disc = state.get("disconnect") if isinstance(state.get("disconnect"), dict) else None
    if disc is None or not disc.get("reconcile_required"):
        return False
    if verdict != "OK":
        disc["last_reconcile"] = str(verdict)
        return False
    disc.update({"reconcile_required": False, "since": None, "last_reconcile": "OK",
                 "reconciled_at": datetime.now(tz=UTC).isoformat(timespec="seconds")})
    return True


def order_legs(mt5: Any, req: Mapping[str, Any]) -> Reading:
    """One opening request as a Reading of its own legs (notional, stop risk, close cost)."""
    sym = str(req.get("symbol") or "")
    typ = int(_num(req.get("type")) or 0)
    buy = typ == 0 or typ in _BUY_ORDER_TYPES
    sl = req.get("sl")
    stop = _num(sl)
    atr = None if stop is not None and stop > 0 else atr_m1(mt5, sym)
    n, s, c, sr, au = _leg(req.get("volume"), req.get("price"), sl, buy,
                           _value_per_price(mt5, sym, {}), atr)
    return Reading(0.0, True, notional=n, stop_bound=s, close_cost=c, stopped_risk=sr,
                   atr_unit=au, symbols=[sym])


def projected_refusal(v: Verdict, reading: Reading, order: Reading) -> str | None:
    """Would adding `order`'s legs to `reading` put the account inside its trip zone? None when
    it would not, or when no daily-loss rule binds this account."""
    if not v.applicable or v.floor is None:
        return None
    if reading.equity is None:
        return "the account could not be read"
    buf, why = buffer_for(reading.notional + order.notional,
                          reading.stop_bound + order.stop_bound,
                          reading.close_cost + order.close_cost, v.zmax, v.gap_threshold_s,
                          stopped_risk=reading.stopped_risk + order.stopped_risk,
                          atr_unit=reading.atr_unit + order.atr_unit)
    if buf is None:
        return f"with this order the buffer is {why}"
    if reading.equity <= v.floor + buf:
        return (f"the order would put the account inside its trip zone: equity "
                f"{reading.equity:,.2f} <= floor {v.floor:,.2f} + buffer {buf:,.2f} ({why})")
    return None
