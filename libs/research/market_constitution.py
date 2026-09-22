"""THE MARKET CONSTITUTION COMPILER -- exchange rules as point-in-time state variables.

WHY A RULE IS A VARIABLE AND NOT A FOOTNOTE. A tape does not know that at 15:26 Tokyo time on
a 2025 trading day the cash market is in a five-minute closing auction that did not exist a
year earlier, that a Korean stock quoted 3% away from its last trade is sitting in a two-minute
single-price call, that an A-share bought this morning cannot be sold until tomorrow, or that
the futures exchange trebled its intraday fee one Monday in 2015. Every one of those is a state
the price was formed under, and a mechanism whose edge depends on it is a mechanism that must
be conditioned on it. This module makes the rule book a column set: deterministic, dated,
cited, and honest about which rows have been checked against their primary document.

THE DSL. A `Venue` is a clock (an IANA zone), a weekly closure, a holiday set and a tuple of
`RuleRow`s. Every RuleRow is one clause of the venue's constitution -- a session timetable of
`Window`s, a price band, a short-sale state, a settlement convention, a fee regime, an HFT
reporting regime -- in force from `effective_from` (inclusive) to `effective_to` (exclusive),
with a `Source` citation and a `verified` flag. `state_at(venue, ts)` evaluates the clauses in
force on the LOCAL date of `ts` and returns one `VenueRuleState`; `stamp` does it for a whole
tape. Nothing in the evaluation reads a row dated after the instant being evaluated, so the
stamp is point-in-time by construction, and `rule_version` names the youngest clause in force
so two stamps from different regimes can never be pooled unnoticed.

VERIFICATION IS A FLAG, NEVER AN ASSUMPTION. Every row is `DECLARED_VERIFY` until the primary
document (the exchange's own rule text, notice or calendar) has been read; `VERIFIED` is used
only for rows whose citation is a document this repository holds and this module's author read
(`desks/mt5/mt5desk/engine.py`, `decision_core.py`). A state built from declared rows lists
them in `unverified`, so a consumer can refuse to size on them.

COUNTRY PACKS ARE CONSUMED, NEVER COPIED. `venue_from_pack_rows` takes a pack's own
`Exchange` / `SessionWindow` / `HolidayRule` / `SettlementRule` instances, duck-typed on their
fields so this module never imports the desk, and turns them into venues. The three Asian
constitutions this module carries in full (TSE/JPX, KRX, SSE/SZSE/CFFEX) and the broker's own
clock (Fusion) are here because no pack holds their intraday state machines.

RULE CHANGES ARE NATURAL EXPERIMENTS. `rule_change_calendar()` lists every dated change with
its mechanism, the instruments it touches and the venues it does not; `rule_change_effect()`
is the one study run on each: a difference in differences of a window statistic between the
affected instrument and an unaffected control venue, with the null drawn from PLACEBO dates on
the same two tapes. A change outside the tape is UNMEASURED with the tape's first date named;
a change in the future is PROSPECTIVE and pre-registered rather than measured.

Sources are public exchange rule books and notices only (JPX, KRX, SSE, SZSE, CFFEX, CSRC,
HKEX), the broker's published conditions, and this repository's own files. No licensed feed.
"""
from __future__ import annotations

import re
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import asdict, dataclass, field
from datetime import UTC, date, datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo

import numpy as np

RULES_VERSION = "2026-09-22.1"

DECLARED_VERIFY = "DECLARED_VERIFY"
VERIFIED = "VERIFIED"
VERIFY_STATES = (DECLARED_VERIFY, VERIFIED)

SESSION_STATES = ("CLOSED", "PRE_OPEN", "OPENING_CALL", "CONTINUOUS", "LUNCH", "PRE_CLOSING",
                  "CLOSING_CALL", "AFTER_HOURS", "NIGHT_SESSION", "ROLLOVER", "HOLIDAY",
                  "WEEKEND", "UNDECLARED")
AUCTION_STATES = ("NONE", "ITAYOSE", "ZARABA", "SINGLE_PRICE_CALL", "CLOSING_ITAYOSE",
                  "VI_CALL", "SPECIAL_QUOTE", "SEQUENTIAL_TRADE_QUOTE", "UNOBSERVED",
                  "UNDECLARED")
PRICE_BAND_STATES = ("NO_LIMIT", "WITHIN_LIMITS", "LIMIT_UP", "LIMIT_DOWN", "UNOBSERVED",
                     "UNDECLARED")
SHORT_STATES = ("PERMITTED", "UPTICK_RULE", "PARTIAL_BAN", "BANNED", "OVERHEATED_DESIGNATED",
                "NOT_APPLICABLE", "UNDECLARED")
SETTLEMENT_STATES = ("T+0", "T+1", "T+2", "T+1_LOCKED", "CFD_ROLLOVER", "UNDECLARED")
FEE_REGIMES = ("STANDARD", "CFFEX_2015_CURBS", "CFFEX_RELAXED", "CFFEX_HFT_DIFFERENTIATED",
               "UNDECLARED")
HFT_REGIMES = ("UNREGULATED", "REPORTING", "REPORTING_WITH_THRESHOLDS", "UNDECLARED")

WEEKDAYS: tuple[int, ...] = (0, 1, 2, 3, 4)
KRX_VI_SECONDS = 120            # a volatility interruption is a two-minute single-price call
MIN_PLACEBOS = 20               # below this a placebo null is POORLY_MEASURED, never a verdict
MIN_REGIME_DAYS = 20            # the shorter side of a pre/post comparison must hold this many

_HHMM = re.compile(r"^(\d{1,2}):(\d{2})$")


# --------------------------------------------------------------------------- the DSL
@dataclass(frozen=True)
class Source:
    """Where a rule came from and whether anyone has read it."""

    citation: str
    url: str = ""
    verified: str = DECLARED_VERIFY
    note: str = ""

    def __post_init__(self) -> None:
        if self.verified not in VERIFY_STATES:
            raise ValueError(f"verified must be one of {VERIFY_STATES}: {self.verified!r}")


@dataclass(frozen=True)
class Window:
    """One named window of the venue's LOCAL day, [start, end) as HH:MM wall clock. A window
    whose start is later than its end wraps midnight (a night session)."""

    name: str
    start: str
    end: str
    session_state: str
    auction_state: str = "NONE"
    weekdays: tuple[int, ...] = WEEKDAYS

    def contains(self, minute: int, weekday: int) -> bool:
        lo, hi = _hhmm(self.start), _hhmm(self.end)
        if lo is None or hi is None or weekday not in self.weekdays:
            return False
        if lo <= hi:
            return lo <= minute < hi
        return minute >= lo or minute < hi


@dataclass(frozen=True)
class RuleRow:
    """One clause of a venue's constitution, dated, cited and flagged."""

    rule_id: str
    venue: str
    instrument_class: str
    kind: str
    effective_from: str
    effective_to: str = ""
    spec: Mapping[str, Any] = field(default_factory=dict)
    mechanism: str = ""
    source: Source = field(default_factory=lambda: Source(citation="UNDECLARED"))

    def in_force(self, day: date) -> bool:
        iso = day.isoformat()
        return self.effective_from <= iso and (not self.effective_to or iso < self.effective_to)

    def applies_to(self, instrument_class: str) -> bool:
        return self.instrument_class in ("*", instrument_class) or not instrument_class


@dataclass(frozen=True)
class Venue:
    """A venue: its clock, its closures, its rules and the desk instruments it stamps."""

    venue_id: str
    name: str
    tz: str
    country: str
    instrument_classes: tuple[str, ...]
    rules: tuple[RuleRow, ...] = ()
    weekly_closed: tuple[int, ...] = (5, 6)
    holidays: frozenset[str] = frozenset()
    fixed_md: tuple[str, ...] = ()
    mt5_symbols: tuple[str, ...] = ()
    source: Source = field(default_factory=lambda: Source(citation="UNDECLARED"))

    def with_holidays(self, days: Iterable[str]) -> Venue:
        merged = frozenset(self.holidays) | frozenset(str(d)[:10] for d in days)
        return Venue(venue_id=self.venue_id, name=self.name, tz=self.tz, country=self.country,
                     instrument_classes=self.instrument_classes, rules=self.rules,
                     weekly_closed=self.weekly_closed, holidays=merged, fixed_md=self.fixed_md,
                     mt5_symbols=self.mt5_symbols, source=self.source)


@dataclass(frozen=True)
class VenueRuleState:
    """The rule state of one venue/instrument class at one instant. Every field is a value
    from the vocabularies above; `UNOBSERVED` means the state needs an input the caller did
    not supply (a price against its band), `UNDECLARED` means no rule row covers it."""

    exchange: str
    instrument_class: str
    timestamp: str
    rule_version: str
    session_state: str
    auction_state: str
    price_band: str
    short_state: str
    settlement_state: str
    fee_regime: str
    hft_regime: str
    window: str = ""
    local_time: str = ""
    rule_ids: tuple[str, ...] = ()
    unverified: tuple[str, ...] = ()

    def as_row(self) -> dict[str, Any]:
        row = asdict(self)
        row["rule_ids"] = "+".join(self.rule_ids)
        row["unverified"] = "+".join(self.unverified)
        return row


@dataclass(frozen=True)
class RuleChange:
    """A dated change of one clause: the natural experiment it offers, named in advance."""

    change_id: str
    venue: str
    date: str
    kind: str
    before: str
    after: str
    mechanism: str
    experiment: str
    affected_symbols: tuple[str, ...]
    control_venues: tuple[str, ...]
    source: Source
    window_utc: tuple[str, str] = ("", "")
    control_symbols: tuple[str, ...] = ()
    prospective: bool = False

    def as_row(self) -> dict[str, Any]:
        row = asdict(self)
        row["source"] = asdict(self.source)
        return row


# --------------------------------------------------------------------------- helpers
def _hhmm(text: str) -> int | None:
    m = _HHMM.match(str(text or "").strip())
    if m is None:
        return None
    h, mi = int(m.group(1)), int(m.group(2))
    if h > 24 or mi > 59:
        return None
    return h * 60 + mi


def _slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", str(text).lower()).strip("_")[:48]


_DAY_NAMES = {"mon": 0, "tue": 1, "wed": 2, "thu": 3, "fri": 4, "sat": 5, "sun": 6}


def _weekdays(value: Any, default: tuple[int, ...] = (5, 6)) -> tuple[int, ...]:
    """Weekday numbers from a pack's own spelling: ints, digit strings, or day names in one
    string ('Sat,Sun'). Anything unreadable is the default, never a silent empty closure."""
    if value is None:
        return default
    tokens: list[Any] = (re.split(r"[^A-Za-z0-9]+", value) if isinstance(value, str)
                         else list(value))
    out: list[int] = []
    for tok in tokens:
        if isinstance(tok, int | np.integer):
            out.append(int(tok))
        elif isinstance(tok, str) and tok.strip().isdigit():
            out.append(int(tok.strip()))
        elif isinstance(tok, str) and tok.strip()[:3].lower() in _DAY_NAMES:
            out.append(_DAY_NAMES[tok.strip()[:3].lower()])
    kept = tuple(sorted({d for d in out if 0 <= d <= 6}))
    return kept or default


def _ints(value: Any) -> tuple[int, ...]:
    if value is None or isinstance(value, str):
        return ()
    out: list[int] = []
    for x in value:
        try:
            out.append(int(x))
        except (TypeError, ValueError):
            continue
    return tuple(out)


def _pair(value: Any) -> tuple[str, str]:
    if isinstance(value, str):
        parts = value.split("-", 1)
        return (parts[0].strip(), parts[1].strip() if len(parts) > 1 else "")
    try:
        items = [str(x) for x in value]
    except TypeError:
        return ("", "")
    return (items[0] if items else "", items[1] if len(items) > 1 else "")


def _as_utc(ts: datetime) -> datetime:
    return ts.replace(tzinfo=UTC) if ts.tzinfo is None else ts.astimezone(UTC)


def local_time(ts: datetime, tz: str) -> datetime:
    """`ts` on the venue's wall clock; a naive `ts` is read as UTC."""
    return _as_utc(ts).astimezone(ZoneInfo(tz))


def closed_day_state(venue: Venue, day: date) -> str:
    """'' when the venue is open that day, else WEEKEND or HOLIDAY."""
    if day.weekday() in venue.weekly_closed:
        return "WEEKEND"
    if day.isoformat() in venue.holidays or f"{day.month:02d}-{day.day:02d}" in venue.fixed_md:
        return "HOLIDAY"
    return ""


def rules_in_force(venue: Venue, day: date, instrument_class: str = "") -> tuple[RuleRow, ...]:
    return tuple(r for r in venue.rules if r.in_force(day) and r.applies_to(instrument_class))


def _pick(rows: Sequence[RuleRow], kind: str) -> RuleRow | None:
    """The youngest row of `kind` in force -- a later clause supersedes an earlier one."""
    best: RuleRow | None = None
    for r in rows:
        if r.kind == kind and (best is None or r.effective_from >= best.effective_from):
            best = r
    return best


def _band_state(rule: RuleRow | None, observed: Mapping[str, Any] | None) -> str:
    if rule is None:
        return "UNDECLARED"
    spec = rule.spec
    if spec.get("no_limit"):
        return "NO_LIMIT"
    if not observed or "price" not in observed or "reference" not in observed:
        return "UNOBSERVED"
    try:
        price, ref = float(observed["price"]), float(observed["reference"])
    except (TypeError, ValueError):
        return "UNOBSERVED"
    if ref <= 0:
        return "UNOBSERVED"
    if spec.get("table") == "tse_daily_limit":
        width = tse_daily_price_limit(ref)
    else:
        pct = spec.get("limit_pct")
        if pct is None:
            return "UNOBSERVED"
        width = ref * float(pct) / 100.0
    if price >= ref + width:
        return "LIMIT_UP"
    if price <= ref - width:
        return "LIMIT_DOWN"
    return "WITHIN_LIMITS"


def _window_of(rows: Sequence[RuleRow], minute: int, weekday: int) -> tuple[str, str, str]:
    """(window name, session state, auction state) from the session clause in force."""
    srule = _pick(rows, "session")
    if srule is None:
        return "", "UNDECLARED", "UNDECLARED"
    for w in srule.spec.get("windows", ()):
        if isinstance(w, Window) and w.contains(minute, weekday):
            return w.name, w.session_state, w.auction_state
    return "", "CLOSED", "NONE"


def _fixed_states(rows: Sequence[RuleRow]) -> dict[str, str]:
    out: dict[str, str] = {}
    for kind in ("short", "settlement", "fee", "hft"):
        r = _pick(rows, kind)
        out[kind] = str(r.spec.get("state", "UNDECLARED")) if r is not None else "UNDECLARED"
    return out


def _version(venue: Venue, rows: Sequence[RuleRow]) -> str:
    youngest = max((r.effective_from for r in rows), default="")
    return f"{RULES_VERSION}:{venue.venue_id}@{youngest or 'no-rule'}"


def state_at(venue: Venue, ts: datetime, instrument_class: str = "",
             observed: Mapping[str, Any] | None = None) -> VenueRuleState:
    """The venue's rule state at `ts` (naive = UTC) for one instrument class.

    `observed` may carry what a clock cannot know: `price` and `reference` for the price band,
    `overheated=True` for a KRX overheated-short designation, `vi_until` (ISO UTC) for a
    volatility interruption in progress. Absent inputs read UNOBSERVED, never a guess.
    """
    cls = instrument_class or (venue.instrument_classes[0] if venue.instrument_classes else "")
    loc = local_time(ts, venue.tz)
    day = loc.date()
    rows = rules_in_force(venue, day, cls)
    closed = closed_day_state(venue, day)
    if closed:
        window_name, session, auction = "", closed, "NONE"
    else:
        window_name, session, auction = _window_of(rows, loc.hour * 60 + loc.minute,
                                                   day.weekday())
    obs = observed or {}
    if obs.get("vi_until") and session == "CONTINUOUS":
        try:
            until = datetime.fromisoformat(str(obs["vi_until"]))
            if _as_utc(ts) < _as_utc(until):
                auction = "VI_CALL"
        except ValueError:
            pass
    fixed = _fixed_states(rows)
    short = fixed["short"]
    if obs.get("overheated") and short not in ("BANNED", "NOT_APPLICABLE"):
        short = "OVERHEATED_DESIGNATED"
    return VenueRuleState(
        exchange=venue.venue_id, instrument_class=cls, timestamp=_as_utc(ts).isoformat(),
        rule_version=_version(venue, rows), session_state=session, auction_state=auction,
        price_band=_band_state(_pick(rows, "price_band"), observed),
        short_state=short, settlement_state=fixed["settlement"], fee_regime=fixed["fee"],
        hft_regime=fixed["hft"], window=window_name,
        local_time=loc.strftime("%Y-%m-%d %H:%M %Z"), rule_ids=tuple(r.rule_id for r in rows),
        unverified=tuple(r.rule_id for r in rows if r.source.verified != VERIFIED))


STAMP_COLUMNS: tuple[str, ...] = ("session_state", "auction_state", "price_band", "short_state",
                                  "settlement_state", "fee_regime", "hft_regime", "window",
                                  "rule_version", "n_unverified")


def stamp(venue: Venue, times: Sequence[datetime], instrument_class: str = "",
          observed: Mapping[str, Any] | None = None) -> dict[str, list[Any]]:
    """The PIT column set for a tape: one row per timestamp, columns `STAMP_COLUMNS`.

    Per-day rule resolution is cached, so a six-year hourly tape costs a few thousand rule
    lookups rather than fifty thousand; the per-minute window test is the only per-bar work.
    """
    cls = instrument_class or (venue.instrument_classes[0] if venue.instrument_classes else "")
    zone = ZoneInfo(venue.tz)
    cols: dict[str, list[Any]] = {c: [] for c in STAMP_COLUMNS}
    plans: dict[date, tuple[tuple[RuleRow, ...], str, dict[str, str], str, str, int]] = {}
    for ts in times:
        loc = _as_utc(ts).astimezone(zone)
        day = loc.date()
        plan = plans.get(day)
        if plan is None:
            rows = rules_in_force(venue, day, cls)
            plan = (rows, closed_day_state(venue, day), _fixed_states(rows),
                    _band_state(_pick(rows, "price_band"), observed), _version(venue, rows),
                    sum(1 for r in rows if r.source.verified != VERIFIED))
            plans[day] = plan
        rows, closed, fixed, band, version, n_unv = plan
        if closed:
            window_name, session, auction = "", closed, "NONE"
        else:
            window_name, session, auction = _window_of(rows, loc.hour * 60 + loc.minute,
                                                       day.weekday())
        cols["session_state"].append(session)
        cols["auction_state"].append(auction)
        cols["price_band"].append(band)
        cols["short_state"].append(fixed["short"])
        cols["settlement_state"].append(fixed["settlement"])
        cols["fee_regime"].append(fixed["fee"])
        cols["hft_regime"].append(fixed["hft"])
        cols["window"].append(window_name)
        cols["rule_version"].append(version)
        cols["n_unverified"].append(n_unv)
    return cols


# --------------------------------------------------------------------------- TSE / JPX
#: TSE daily price limits (値幅制限) by base price, yen. Thresholds are exclusive upper bounds.
TSE_LIMIT_TABLE: tuple[tuple[float, float], ...] = (
    (100, 30), (200, 50), (500, 80), (700, 100), (1_000, 150), (1_500, 300), (2_000, 400),
    (3_000, 500), (5_000, 700), (7_000, 1_000), (10_000, 1_500), (15_000, 3_000),
    (20_000, 4_000), (30_000, 5_000), (50_000, 7_000), (70_000, 10_000), (100_000, 15_000),
    (150_000, 30_000), (200_000, 40_000), (300_000, 50_000), (500_000, 70_000),
    (700_000, 100_000), (1_000_000, 150_000), (1_500_000, 300_000), (2_000_000, 400_000),
    (3_000_000, 500_000), (5_000_000, 700_000), (7_000_000, 1_000_000),
    (10_000_000, 1_500_000), (15_000_000, 3_000_000), (20_000_000, 4_000_000),
    (30_000_000, 5_000_000), (50_000_000, 7_000_000))


def tse_daily_price_limit(base_price: float) -> float:
    """The daily limit width (yen, each side) for a TSE base price, from the step table."""
    for upper, width in TSE_LIMIT_TABLE:
        if base_price < upper:
            return float(width)
    return 10_000_000.0


_JPX = Source(citation="JPX, 'Trading Rules of Domestic Stocks' and the 2024-11-05 trading "
                       "hours extension notice (arrowhead4.0: close moved 15:00 -> 15:30, "
                       "closing auction introduced)",
              url="https://www.jpx.co.jp/english/equities/trading/domestic/index.html")
_JPX_RANDOM = Source(citation="JPX announcement of a randomised closing-auction end, planned "
                              "for 2027-10-12 (date as declared to this desk 2026-09-22)",
                     note="prospective; the primary notice has not been read")
_JPX_LIMITS = Source(citation="JPX, daily price limit table (値幅制限) and special / "
                              "sequential-trade quote rules (特別気配, 連続約定気配)")
_OSE = Source(citation="OSE (JPX derivatives), Nikkei 225 futures trading hours; day session "
                       "close extended to 15:45 with the 2024-11-05 change, night session "
                       "17:00-06:00")


def _tse_cash_windows(close: str, closing_auction: bool) -> tuple[Window, ...]:
    """The TSE cash day: itayose open, zaraba, lunch, zaraba, then either a plain closing
    itayose (pre-2024-11-05) or a five-minute closing auction ending in the itayose."""
    tail: tuple[Window, ...]
    if closing_auction:
        tail = (Window("afternoon_zaraba", "12:30", "15:25", "CONTINUOUS", "ZARABA"),
                Window("closing_auction", "15:25", close, "PRE_CLOSING", "CLOSING_ITAYOSE"))
    else:
        tail = (Window("afternoon_zaraba", "12:30", close, "CONTINUOUS", "ZARABA"),)
    return (Window("pre_open_orders", "08:00", "09:00", "PRE_OPEN", "ITAYOSE"),
            Window("morning_zaraba", "09:00", "11:30", "CONTINUOUS", "ZARABA"),
            Window("lunch_orders", "11:30", "12:30", "LUNCH", "ITAYOSE"),
            *tail)


def venue_tse(holidays: Iterable[str] = ()) -> Venue:
    v = "TSE"
    rules = (
        RuleRow("tse.session.pre2024", v, "equity_cash", "session", "2010-01-04", "2024-11-05",
                {"windows": _tse_cash_windows("15:00", False)},
                "continuous zaraba to a 15:00 closing itayose; the last five minutes are "
                "continuous trading", _JPX),
        RuleRow("tse.session.2024_closing_auction", v, "equity_cash", "session", "2024-11-05",
                "", {"windows": _tse_cash_windows("15:30", True)},
                "the close moves to 15:30 and the last five minutes become an order-acceptance "
                "period with no continuous trading (the closing auction), matched by itayose at "
                "15:30 -- closing liquidity concentrates in one print instead of a tape", _JPX),
        RuleRow("tse.session.2027_random_close", v, "equity_cash", "session", "2027-10-12", "",
                {"windows": _tse_cash_windows("15:30", True), "random_end": True},
                "the closing itayose executes at a randomised instant after 15:30, so an order "
                "timed to the last second no longer sees the final imbalance", _JPX_RANDOM),
        RuleRow("tse.price_band.daily_limit", v, "equity_cash", "price_band", "2010-01-04", "",
                {"table": "tse_daily_limit", "special_quote_renewal_min": 3,
                 "sequential_trade_quote_min": 1},
                "a stock at its daily limit cannot print further in that direction; an order "
                "that would cross the renewal price interval posts a special quote renewed "
                "every three minutes, and a run of executions beyond it posts a sequential-"
                "trade quote", _JPX_LIMITS),
        RuleRow("tse.short.uptick", v, "equity_cash", "short", "2013-11-05", "",
                {"state": "UPTICK_RULE"},
                "the uptick rule applies only once a stock has fallen 10% from the previous "
                "close (trigger-type rule since 2013-11-05)", _JPX),
        RuleRow("tse.settlement.t2", v, "equity_cash", "settlement", "2019-07-16", "",
                {"state": "T+2"}, "T+2 settlement since 2019-07-16 (T+3 before)", _JPX),
        RuleRow("ose.session.pre2024", v, "index_futures", "session", "2010-01-04", "2024-11-05",
                {"windows": (Window("day_session", "08:45", "15:15", "CONTINUOUS"),
                             Window("night_session", "16:30", "06:00", "NIGHT_SESSION"))},
                "Nikkei 225 futures day session 08:45-15:15, night session 16:30-06:00", _OSE),
        RuleRow("ose.session.2024", v, "index_futures", "session", "2024-11-05", "",
                {"windows": (Window("day_session", "08:45", "15:45", "CONTINUOUS"),
                             Window("night_session", "17:00", "06:00", "NIGHT_SESSION"))},
                "the day session closes 15:45 after the cash close moved to 15:30", _OSE),
        RuleRow("ose.price_band.circuit", v, "index_futures", "price_band", "2010-01-04", "",
                {"limit_pct": 8.0},
                "a dynamic circuit breaker widens the futures band in steps (8%, 12%, 16%) with "
                "a ten-minute halt at each", _OSE),
        RuleRow("ose.settlement", v, "index_futures", "settlement", "2010-01-04", "",
                {"state": "T+1"}, "daily variation margin", _OSE),
        RuleRow("tse.hft.registration", v, "*", "hft", "2018-04-01", "", {"state": "REPORTING"},
                "high-speed traders register with the FSA under the 2018 FIEA amendment", _JPX),
        RuleRow("tse.hft.none", v, "*", "hft", "2010-01-04", "2018-04-01",
                {"state": "UNREGULATED"}, "no high-speed trading registration", _JPX),
        RuleRow("tse.fee.standard", v, "*", "fee", "2010-01-04", "", {"state": "STANDARD"},
                "no fee regime change in the window", _JPX),
    )
    return Venue(venue_id=v, name="Tokyo Stock Exchange / Osaka Exchange (JPX)", tz="Asia/Tokyo",
                 country="JP", instrument_classes=("equity_cash", "index_futures"), rules=rules,
                 holidays=frozenset(holidays), fixed_md=("01-01", "01-02", "01-03", "12-31"),
                 mt5_symbols=("JPN225", "USDJPY"), source=_JPX)


# --------------------------------------------------------------------------- KRX
_KRX = Source(citation="KRX, KOSPI Market Business Regulation: trading hours (15:30 close since "
                       "2016-08-01), the 15:20-15:30 closing call, dynamic VI (2014-09-01) and "
                       "static VI (2015-06-15), +/-30% daily limit (2015-06-15)")
_KRX_SHORT = Source(citation="FSC / KRX short-sale notices: bans 2008-10-01..2009-05-31, "
                             "2011-08-10..2011-11-09, 2020-03-16..2021-05-02 (partial "
                             "resumption 2021-05-03), 2023-11-06..2025-03-30; overheated-"
                             "stock designation")
_NXT = Source(citation="Nextrade (NXT) alternative trading system launch 2025-03-04: pre-market "
                       "08:00-08:50, after-market 15:30-20:00 KST")


@dataclass(frozen=True)
class VIState:
    """The KRX volatility-interruption machine's state: no call, or a two-minute single-price
    call that ends at `until` (UTC ISO) and was triggered by the named threshold."""

    state: str = "NONE"
    until: str = ""
    trigger: str = ""


def krx_vi_step(current: VIState, ts: datetime, price: float, dynamic_ref: float,
                static_ref: float, *, dynamic_pct: float = 3.0, static_pct: float = 10.0,
                seconds: int = KRX_VI_SECONDS) -> VIState:
    """One transition of the VI machine (deterministic, from the KRX rule).

    CONTINUOUS --(|price/dynamic_ref - 1| >= dynamic_pct or |price/static_ref - 1| >=
    static_pct)--> VI_CALL for `seconds`; VI_CALL --(ts >= until)--> CONTINUOUS, where the
    call's single price becomes the next dynamic reference. A call in progress is never
    re-triggered: the exchange extends nothing before the first one strikes.
    """
    now = _as_utc(ts)
    if current.state == "VI_CALL":
        until = datetime.fromisoformat(current.until) if current.until else now
        if now < _as_utc(until):
            return current
        return VIState()
    if dynamic_ref > 0 and abs(price / dynamic_ref - 1.0) * 100.0 >= dynamic_pct:
        return VIState("VI_CALL", (now + timedelta(seconds=seconds)).isoformat(), "dynamic")
    if static_ref > 0 and abs(price / static_ref - 1.0) * 100.0 >= static_pct:
        return VIState("VI_CALL", (now + timedelta(seconds=seconds)).isoformat(), "static")
    return VIState()


def _krx_windows(call_start: str, close: str) -> tuple[Window, ...]:
    """The KRX cash day: a ten-minute closing call ends the continuous session at `close`."""
    return (Window("pre_open_call", "08:30", "09:00", "PRE_OPEN", "SINGLE_PRICE_CALL"),
            Window("continuous", "09:00", call_start, "CONTINUOUS"),
            Window("closing_call", call_start, close, "CLOSING_CALL", "SINGLE_PRICE_CALL"),
            Window("after_hours_close_price", "15:40", "16:00", "AFTER_HOURS"),
            Window("after_hours_single_price", "16:00", "18:00", "AFTER_HOURS",
                   "SINGLE_PRICE_CALL"))


_KRX_SHORT_MECHANISM = {
    "BANNED": "no new short positions; borrowed-stock supply cannot express negative "
              "information",
    "PARTIAL_BAN": "shorting permitted only in KOSPI200 and KOSDAQ150 constituents",
    "UPTICK_RULE": "covered shorting on an uptick; naked shorting prohibited"}


def _krx_short_rows() -> tuple[RuleRow, ...]:
    spans = (("2008-01-01", "2008-10-01", "UPTICK_RULE"), ("2008-10-01", "2009-06-01", "BANNED"),
             ("2009-06-01", "2011-08-10", "UPTICK_RULE"), ("2011-08-10", "2011-11-10", "BANNED"),
             ("2011-11-10", "2020-03-16", "UPTICK_RULE"), ("2020-03-16", "2021-05-03", "BANNED"),
             ("2021-05-03", "2023-11-06", "PARTIAL_BAN"), ("2023-11-06", "2025-03-31", "BANNED"),
             ("2025-03-31", "", "UPTICK_RULE"))
    return tuple(RuleRow(f"krx.short.{a}", "KRX", "equity_cash", "short", a, b, {"state": s},
                         _KRX_SHORT_MECHANISM[s], _KRX_SHORT) for a, b, s in spans)


def venue_krx(holidays: Iterable[str] = ()) -> Venue:
    v = "KRX"
    rules = (
        RuleRow("krx.session.pre2016", v, "equity_cash", "session", "2008-01-01", "2016-08-01",
                {"windows": _krx_windows("14:50", "15:00")},
                "cash close at 15:00 with a ten-minute closing call from 14:50", _KRX),
        RuleRow("krx.session.2016_extension", v, "equity_cash", "session", "2016-08-01", "",
                {"windows": _krx_windows("15:20", "15:30")},
                "trading extended thirty minutes to a 15:30 close; the closing call is "
                "15:20-15:30 and KOSPI200 derivatives settle from it", _KRX),
        RuleRow("krx.price_band.15pct", v, "equity_cash", "price_band", "2008-01-01",
                "2015-06-15", {"limit_pct": 15.0}, "+/-15% daily limit", _KRX),
        RuleRow("krx.price_band.30pct_static_vi", v, "equity_cash", "price_band", "2015-06-15",
                "", {"limit_pct": 30.0, "static_vi_pct": 10.0, "dynamic_vi_pct": 3.0,
                     "vi_seconds": KRX_VI_SECONDS},
                "the daily limit widens to +/-30% and a static VI (10% from the reference "
                "price) joins the dynamic VI: a breach converts two minutes of continuous "
                "trading into one single-price call", _KRX),
        RuleRow("krx.auction.dynamic_vi", v, "equity_cash", "auction", "2014-09-01", "",
                {"dynamic_vi_pct": 3.0, "vi_seconds": KRX_VI_SECONDS},
                "an order that would execute 3% away from the last trade triggers a two-minute "
                "single-price call instead of a print", _KRX),
        *_krx_short_rows(),
        RuleRow("krx.settlement.t2", v, "equity_cash", "settlement", "2008-01-01", "",
                {"state": "T+2"}, "T+2 settlement", _KRX),
        RuleRow("krx.hft.none", v, "*", "hft", "2008-01-01", "", {"state": "UNREGULATED"},
                "no programmatic-trading reporting regime", _KRX),
        RuleRow("krx.fee.standard", v, "*", "fee", "2008-01-01", "", {"state": "STANDARD"},
                "securities transaction tax stepped down 2023-2025; no HFT differentiation",
                _KRX),
        RuleRow("nxt.session.2025", v, "ats_nxt", "session", "2025-03-04", "",
                {"windows": (Window("pre_market", "08:00", "08:50", "PRE_OPEN"),
                             Window("main", "09:00", "15:20", "CONTINUOUS"),
                             Window("after_market", "15:30", "20:00", "AFTER_HOURS"))},
                "a second venue extends the Korean cash day to twelve hours; the closing "
                "call keeps its monopoly on the settlement print", _NXT),
    )
    return Venue(venue_id=v, name="Korea Exchange (KRX)", tz="Asia/Seoul", country="KR",
                 instrument_classes=("equity_cash", "ats_nxt"), rules=rules,
                 holidays=frozenset(holidays), fixed_md=("01-01", "12-31"),
                 mt5_symbols=("USDKRW",), source=_KRX)


# --------------------------------------------------------------------------- SSE / SZSE / CFFEX
_SSE = Source(citation="SSE / SZSE Trading Rules: 09:15-09:25 opening call, continuous 09:30-"
                       "11:30 and 13:00-14:57, closing call 14:57-15:00 (SZSE since 2006, SSE "
                       "since 2018-08-20); +/-10% main boards, +/-20% ChiNext (2020-08-24) "
                       "and STAR (2019-07-22); T+1 for A shares")
_CSRC = Source(citation="CSRC Provisions on the Administration of Programmatic Trading in the "
                        "Securities Market (in force 2024-10-08); SSE/SZSE implementation rules "
                        "(in force 2025-07-07; HFT = >=300 orders/second or >=20,000 "
                        "orders/day); exchange reporting regime from 2023-10-09")
_CSRC_OCT25 = Source(citation="programmatic/HFT reporting and differentiated-fee regime from "
                              "October 2025, as declared to this desk (blueprint 2026-09-22)",
                     note="the exchange notice and its exact effective date have not been read")
_CFFEX = Source(citation="CFFEX notices: 2015-09-07 curbs (intraday round-trip fee 23bp, 40% "
                         "margin, 10-lot 'abnormal trading' threshold) and the relaxations of "
                         "2017-02-17, 2017-09-18, 2018-12-03 and 2019-04-22; 2026 "
                         "differentiated fees for high-frequency programmatic trading (date as "
                         "declared to this desk)")
_CONNECT = Source(citation="HKEX Stock Connect trading calendar: northbound trades only when "
                           "both markets are open and the money-settlement day is a Hong Kong "
                           "banking day")

_A_SHARE_WINDOWS: tuple[Window, ...] = (
    Window("opening_call", "09:15", "09:25", "OPENING_CALL", "SINGLE_PRICE_CALL"),
    Window("pre_open_gap", "09:25", "09:30", "PRE_OPEN"),
    Window("morning", "09:30", "11:30", "CONTINUOUS"),
    Window("lunch", "11:30", "13:00", "LUNCH"),
    Window("afternoon", "13:00", "14:57", "CONTINUOUS"),
    Window("closing_call", "14:57", "15:00", "CLOSING_CALL", "SINGLE_PRICE_CALL"))


def venue_sse_szse(holidays: Iterable[str] = ()) -> Venue:
    v = "SSE_SZSE"
    hft_thresholds = {"orders_per_second": 300, "orders_per_day": 20_000}
    rules = (
        RuleRow("sse.session.2018_closing_call", v, "a_share", "session", "2018-08-20", "",
                {"windows": _A_SHARE_WINDOWS},
                "the last three minutes of the SSE day become a single-price call (SZSE had "
                "one since 2006); the close is one print, and closing-price manipulation moves "
                "to the call", _SSE),
        RuleRow("sse.session.pre2018", v, "a_share", "session", "2010-01-04", "2018-08-20",
                {"windows": (*_A_SHARE_WINDOWS[:4],
                             Window("afternoon", "13:00", "15:00", "CONTINUOUS"))},
                "SSE closed on continuous trading", _SSE),
        RuleRow("sse.price_band.10pct", v, "a_share", "price_band", "2010-01-04", "",
                {"limit_pct": 10.0, "chinext_star_pct": 20.0, "st_pct": 5.0},
                "a +/-10% limit (20% on ChiNext since 2020-08-24 and STAR since 2019-07-22, "
                "5% on ST stocks) truncates the day's distribution and defers information to "
                "the next open", _SSE),
        RuleRow("sse.settlement.t1", v, "a_share", "settlement", "2010-01-04", "",
                {"state": "T+1_LOCKED"},
                "A shares bought today cannot be sold until tomorrow: intraday reversal is "
                "unavailable to the buyer, so the next open carries the unwind", _SSE),
        RuleRow("sse.short.designated", v, "a_share", "short", "2010-03-31", "",
                {"state": "PARTIAL_BAN"},
                "margin trading and securities lending only in designated securities; "
                "securities lending was curtailed from 2024-01-28 and suspended 2024-07-11",
                _SSE),
        RuleRow("sse.hft.unregulated", v, "*", "hft", "2010-01-04", "2023-10-09",
                {"state": "UNREGULATED"}, "no programmatic-trading reporting", _CSRC),
        RuleRow("sse.hft.reporting_2023", v, "*", "hft", "2023-10-09", "2025-07-07",
                {"state": "REPORTING"},
                "programmatic traders must file with the exchange before trading; the "
                "exchange can see who the machine is", _CSRC),
        RuleRow("sse.hft.thresholds_2025", v, "*", "hft", "2025-07-07", "2025-10-01",
                {"state": "REPORTING_WITH_THRESHOLDS", **hft_thresholds},
                "high-frequency trading is defined by order rate and put under differentiated "
                "supervision, fee and reporting duties", _CSRC),
        RuleRow("sse.hft.oct2025", v, "*", "hft", "2025-10-01", "",
                {"state": "REPORTING_WITH_THRESHOLDS", "differentiated_fees": True,
                 **hft_thresholds},
                "the October 2025 regime adds differentiated fees for high-frequency "
                "programmatic trading; the marginal cost of a cancelled order rises", _CSRC_OCT25),
        RuleRow("sse.fee.standard", v, "a_share", "fee", "2010-01-04", "", {"state": "STANDARD"},
                "stamp duty on sales halved to 0.05% on 2023-08-28", _SSE),
        RuleRow("connect.calendar", v, "a_share", "settlement_calendar", "2014-11-17", "",
                {"rule": "northbound open only when SSE/SZSE and SEHK are both open and T+1 "
                         "is a HK banking day"},
                "a mainland day the Connect is shut removes the northbound marginal buyer",
                _CONNECT),
    )
    return Venue(venue_id=v, name="Shanghai and Shenzhen Stock Exchanges", tz="Asia/Shanghai",
                 country="CN", instrument_classes=("a_share",), rules=rules,
                 holidays=frozenset(holidays), fixed_md=("01-01",),
                 mt5_symbols=("USDCNH", "CHINAH", "HK50"), source=_SSE)


_CFFEX_FEE_ERAS: tuple[tuple[str, str, str, str], ...] = (
    ("2010-04-16", "2015-09-07", "STANDARD", "intraday round-trip fee 0.23bp, margin 10-20%: "
     "an index-futures venue that clears a fifth of the cash turnover daily"),
    ("2015-09-07", "2017-02-17", "CFFEX_2015_CURBS", "intraday round-trip fee raised "
     "one-hundred-fold to 23bp, margin 40%, ten lots a day counted as abnormal: turnover fell "
     "~99% and the basis went to a persistent discount"),
    ("2017-02-17", "2019-04-22", "CFFEX_RELAXED", "stepwise relaxation: 20 lots, margin 20%, "
     "fee 9.2bp (2017-02-17); fee 6.9bp (2017-09-18); 50 lots, fee 4.6bp (2018-12-03)"),
    ("2019-04-22", "2026-01-01", "STANDARD", "500 lots, margin 10-12%, fee 3.45bp"),
    ("2026-01-01", "", "CFFEX_HFT_DIFFERENTIATED", "differentiated fees for high-frequency "
     "programmatic trading (2026, date as declared to this desk)"))


def venue_cffex(holidays: Iterable[str] = ()) -> Venue:
    v = "CFFEX"
    rules = (
        RuleRow("cffex.session.pre2016", v, "index_futures", "session", "2010-04-16",
                "2016-01-01", {"windows": (Window("morning", "09:15", "11:30", "CONTINUOUS"),
                                           Window("lunch", "11:30", "13:00", "LUNCH"),
                                           Window("afternoon", "13:00", "15:15", "CONTINUOUS"))},
                "futures opened fifteen minutes before the cash market and closed fifteen after",
                _CFFEX),
        RuleRow("cffex.session.2016", v, "index_futures", "session", "2016-01-01", "",
                {"windows": (Window("morning", "09:30", "11:30", "CONTINUOUS"),
                             Window("lunch", "11:30", "13:00", "LUNCH"),
                             Window("afternoon", "13:00", "15:00", "CONTINUOUS"))},
                "futures hours aligned to the cash market after the 2015 crash", _CFFEX),
        RuleRow("cffex.price_band.10pct", v, "index_futures", "price_band", "2010-04-16", "",
                {"limit_pct": 10.0}, "+/-10% daily limit", _CFFEX),
        RuleRow("cffex.settlement.t0", v, "index_futures", "settlement", "2010-04-16", "",
                {"state": "T+0"}, "daily mark-to-market", _CFFEX),
        RuleRow("cffex.short.na", v, "index_futures", "short", "2010-04-16", "",
                {"state": "NOT_APPLICABLE"}, "a future is sold, not shorted", _CFFEX),
        *(RuleRow(f"cffex.fee.{a}", v, "index_futures", "fee", a, b, {"state": s}, m, _CFFEX)
          for a, b, s, m in _CFFEX_FEE_ERAS),
        RuleRow("cffex.hft.follows_csrc", v, "index_futures", "hft", "2024-10-08", "",
                {"state": "REPORTING"}, "programmatic-trading reporting per the CSRC provisions",
                _CSRC),
    )
    return Venue(venue_id=v, name="China Financial Futures Exchange", tz="Asia/Shanghai",
                 country="CN", instrument_classes=("index_futures",), rules=rules,
                 holidays=frozenset(holidays), fixed_md=("01-01",),
                 mt5_symbols=("CHINAH", "HK50"), source=_CFFEX)


# --------------------------------------------------------------------------- Fusion (the broker)
_FUSION_ENGINE = Source(citation="desks/mt5/mt5desk/engine.py ROLLOVER_HOUR_UTC=21, "
                                 "TRIPLE_SWAP_WEEKDAY=2 (server UTC+2 winter / UTC+3 summer; "
                                 "the earlier hour is used deliberately)", verified=VERIFIED)
_FUSION_CLOSE = Source(citation="desks/mt5/mt5desk/decision_core.py CLOSE_HOUR=19.5 (the desk "
                                "force-closes the gold book at 19:30 UTC)", verified=VERIFIED)
_FUSION_EQUITY_HOURS = Source(citation="NYSE/Nasdaq core trading session 09:30-16:00 New York "
                                       "(public); Fusion share CFDs quote the underlying's "
                                       "cash session",
                              note="the broker's share-CFD specification page has not been "
                                   "read; the New York / Athens DST mismatch weeks are unread")
_FUSION_HOURS = Source(citation="Fusion Markets published trading hours (FX Sunday 22:05 - "
                                "Friday 21:55 UTC-equivalent; metals and index CFDs with a "
                                "daily break around server midnight)",
                       note="the broker's contract-specification page has not been read; the "
                            "server's DST switch dates (EU vs US) are unknown")


def venue_fusion() -> Venue:
    v = "FUSION"
    fx = (Window("fx_week", "00:05", "23:55", "CONTINUOUS"),
          Window("rollover", "23:55", "00:05", "ROLLOVER"))
    metals = (Window("metals_day", "01:00", "23:59", "CONTINUOUS"),
              Window("metals_break", "23:59", "01:00", "ROLLOVER"))
    # NYSE/Nasdaq core session 09:30-16:00 New York is 16:30-23:00 on the server's own clock
    # (Athens, seven hours ahead of New York in both seasons but for the two or three weeks the
    # two DST switches disagree, which the source note names as unread).
    equities = (Window("us_cash", "16:30", "23:00", "CONTINUOUS"),
                Window("us_closed", "23:00", "16:30", "CLOSED"))
    rules = (
        RuleRow("fusion.session.fx", v, "forex", "session", "2010-01-04", "", {"windows": fx},
                "24/5 with a rollover at server midnight; the desk counts it at 21:00 UTC "
                "and Wednesday's carries three days", _FUSION_HOURS),
        RuleRow("fusion.session.metals", v, "metals", "session", "2010-01-04", "",
                {"windows": metals}, "an hourly daily break around server midnight",
                _FUSION_HOURS),
        RuleRow("fusion.session.indices", v, "indices", "session", "2010-01-04", "",
                {"windows": metals},
                "index CFDs follow the underlying future's near-24h clock with a daily break",
                _FUSION_HOURS),
        RuleRow("fusion.session.equities", v, "equities", "session", "2010-01-04", "",
                {"windows": equities},
                "share CFDs trade the underlying's cash session only; an overnight gap is the "
                "whole of the close-to-open move", _FUSION_EQUITY_HOURS),
        RuleRow("fusion.rollover.swap", v, "*", "rollover", "2010-01-04", "",
                {"rollover_hour_utc": 21, "triple_swap_weekday": 2},
                "financing is charged at the rollover; a position held across it pays or "
                "earns the swap, three times on Wednesday", _FUSION_ENGINE),
        RuleRow("fusion.settlement.cfd", v, "*", "settlement", "2010-01-04", "",
                {"state": "CFD_ROLLOVER"}, "cash-settled CFD, financed nightly", _FUSION_ENGINE),
        RuleRow("fusion.desk_close.gold", v, "metals", "desk_close", "2025-01-01", "",
                {"close_utc": "19:30", "book": "gold"},
                "the desk's own rule: the gold book is flat by 19:30 UTC", _FUSION_CLOSE),
        RuleRow("fusion.short.cfd", v, "*", "short", "2010-01-04", "", {"state": "PERMITTED"},
                "a CFD is sold as freely as bought", _FUSION_HOURS),
        RuleRow("fusion.price_band.none", v, "*", "price_band", "2010-01-04", "",
                {"no_limit": True}, "no daily limit; the underlying venue's halts pass through",
                _FUSION_HOURS),
        RuleRow("fusion.fee.standard", v, "*", "fee", "2010-01-04", "", {"state": "STANDARD"},
                "commission per lot plus spread", _FUSION_HOURS),
        RuleRow("fusion.hft.none", v, "*", "hft", "2010-01-04", "", {"state": "UNREGULATED"},
                "no reporting regime", _FUSION_HOURS),
    )
    return Venue(venue_id=v, name="Fusion Markets (MT5 server clock)", tz="Europe/Athens",
                 country="AU", instrument_classes=("forex", "metals", "indices"), rules=rules,
                 mt5_symbols=("XAUUSD", "EURUSD", "USDJPY"), source=_FUSION_HOURS)


def builtin_venues(holidays: Mapping[str, Iterable[str]] | None = None) -> dict[str, Venue]:
    """The venues this module carries in full, with per-venue holiday sets injected by the
    caller (the desk reads them from the country packs and the Japan calendar; this module
    holds only the fixed-date closures every year shares)."""
    h = holidays or {}
    return {"TSE": venue_tse(h.get("TSE", ())), "KRX": venue_krx(h.get("KRX", ())),
            "SSE_SZSE": venue_sse_szse(h.get("SSE_SZSE", ())),
            "CFFEX": venue_cffex(h.get("CFFEX", ())), "FUSION": venue_fusion()}


# --------------------------------------------------------------------------- country packs
def venue_from_pack_rows(code: str, exchanges: Sequence[Any], session_windows: Sequence[Any],
                         holidays_rule: Any, settlement_rules: Sequence[Any],
                         mt5_symbols: Sequence[str] = ()) -> tuple[Venue, ...]:
    """Venues from a country pack's own rows (`libs.research.country_lab` types, duck-typed).

    One venue per `Exchange` row: its `open_utc`/`close_utc` become a CONTINUOUS window on a
    UTC clock (the pack already converted), every `SessionWindow` becomes a named window, the
    `HolidayRule` becomes the holiday set and weekly closure, every `SettlementRule` a
    settlement clause, and `expiry_dates` an expiry clause. Nothing is re-declared here: the
    citation is the pack file and the flag is DECLARED_VERIFY because the pack's rows carry
    their own VERIFY labels.
    """
    cc = str(code).lower()
    src = Source(citation=f"desks/mt5/research/countries/{cc}/pack.py",
                 note="consumed from the country pack's own rows")
    raw_dates = getattr(holidays_rule, "dates", ()) or ()
    hol_dates = frozenset(str(d)[:10] for d in ([raw_dates] if isinstance(raw_dates, str)
                                                else raw_dates))
    raw_md = getattr(holidays_rule, "fixed_md", ()) or ()
    fixed_md = tuple(str(x) for x in ([raw_md] if isinstance(raw_md, str) else raw_md))
    weekly = _weekdays(getattr(holidays_rule, "weekly_closed", None))
    named = tuple(Window(_slug(getattr(w, "name", "") or "window"),
                         str(getattr(w, "start_utc", "")), str(getattr(w, "end_utc", "")),
                         "CONTINUOUS")
                  for w in session_windows
                  if _hhmm(str(getattr(w, "start_utc", ""))) is not None
                  and _hhmm(str(getattr(w, "end_utc", ""))) is not None)
    out: list[Venue] = []
    for ex in exchanges:
        name = str(getattr(ex, "name", "") or "")
        if not name:
            continue
        vid = f"{cc.upper()}:{_slug(name)}"
        opn, cls = str(getattr(ex, "open_utc", "")), str(getattr(ex, "close_utc", ""))
        rules: list[RuleRow] = []
        if _hhmm(opn) is not None and _hhmm(cls) is not None:
            # the pack's NAMED windows are listed first: the first window that contains the
            # minute wins, and a closing call inside the cash day must outrank the cash day
            rules.append(RuleRow(f"{vid}.session", vid, "*", "session", "2000-01-01", "",
                                 {"windows": (*named, Window("cash", opn, cls, "CONTINUOUS"))},
                                 str(getattr(ex, "notes", "") or ""), src))
        elif named:
            rules.append(RuleRow(f"{vid}.session", vid, "*", "session", "2000-01-01", "",
                                 {"windows": named}, "pack session windows only", src))
        expiry = tuple(str(d) for d in (getattr(ex, "expiry_dates", ()) or ()))
        expiry_rule = str(getattr(ex, "expiry_rule", None) or "")
        if expiry or expiry_rule:
            rules.append(RuleRow(f"{vid}.expiry", vid, "*", "expiry", "2000-01-01", "",
                                 {"expiry_rule": expiry_rule, "expiry_dates": expiry},
                                 "index derivatives settle on these dates", src))
        for i, sr in enumerate(settlement_rules):
            rules.append(RuleRow(f"{vid}.settlement.{_slug(getattr(sr, 'name', '') or str(i))}",
                                 vid, "*", "settlement_convention", "2000-01-01", "",
                                 {"kind": str(getattr(sr, "kind", "")),
                                  "days": _ints(getattr(sr, "days", ())),
                                  "months": _ints(getattr(sr, "months", ())),
                                  "roll": str(getattr(sr, "roll", "")),
                                  "window_utc": _pair(getattr(sr, "window_utc", ("", ""))),
                                  "instruments": tuple(
                                      str(s) for s in (getattr(sr, "instruments", ()) or ())
                                      if not isinstance(s, str) or len(s) > 1)},
                                 str(getattr(sr, "notes", "") or ""), src))
        syms = (tuple(str(s) for s in (getattr(ex, "index_symbols", ()) or ()))
                or tuple(mt5_symbols))
        out.append(Venue(venue_id=vid, name=name, tz="UTC", country=cc.upper(),
                         instrument_classes=("*",), rules=tuple(rules), weekly_closed=weekly,
                         holidays=hol_dates, fixed_md=fixed_md, mt5_symbols=syms, source=src))
    return tuple(out)


# --------------------------------------------------------------------------- the calendar
_MAINLAND = ("01:30", "07:00")
_CN_SPILL = ("CHINAH", "HK50")


def rule_change_calendar() -> tuple[RuleChange, ...]:
    """Every dated rule change this module knows, with its mechanism and its experiment."""
    rows = (
        RuleChange("tse_closing_auction_2024", "TSE", "2024-11-05", "session",
                   "15:00 close, last five minutes continuous",
                   "15:30 close, 15:25-15:30 closing auction (no continuous trading)",
                   "closing liquidity concentrates in one itayose print thirty minutes later; "
                   "the cash close leaves the 14:00-15:00 JST hour and enters 15:00-16:00",
                   "share of JPN225's daily absolute move carried by the 06:00 UTC bar "
                   "(15:00-16:00 JST) before vs after, less the same on HK50 (no change), "
                   "null from placebo dates", ("JPN225",), ("HKEX",), _JPX,
                   ("06:00", "07:00"), ("HK50",)),
        RuleChange("tse_random_close_2027", "TSE", "2027-10-12", "session",
                   "closing itayose at exactly 15:30",
                   "closing itayose at a randomised instant after 15:30",
                   "the last-second order that reads the final imbalance loses its target; "
                   "pre-close positioning spreads over the auction window",
                   "PRE-REGISTERED (the statistic rule_change_effect runs, fixed now): share of "
                   "JPN225's daily absolute move carried by the 06:00 UTC bar, 120 trading days "
                   "each side, control HK50, placebo change dates every 10 trading days on the "
                   "same tapes; decision rule |DiD| beyond the 95th placebo percentile. The "
                   "15:25-15:30 JST return's autocorrelation with 15:30-16:00 is an EXTENSION "
                   "that needs M5 bars the desk does not yet hold for JPN225",
                   ("JPN225",), ("HKEX",),
                   _JPX_RANDOM, ("06:00", "07:00"), ("HK50",), prospective=True),
        RuleChange("krx_price_limit_30pct_2015", "KRX", "2015-06-15", "price_band",
                   "+/-15% daily limit", "+/-30% daily limit with static VI",
                   "a wider band lets a day's information print in a day; limit-hit "
                   "continuation moves to intraday VI calls", "USDKRW's KRX-hours share of "
                   "daily absolute move before vs after, control USDJPY", ("USDKRW",),
                   ("TSE",), _KRX, ("00:00", "06:30"), ("USDJPY",)),
        RuleChange("krx_hours_extension_2016", "KRX", "2016-08-01", "session",
                   "15:00 close", "15:30 close",
                   "thirty more minutes of Korean cash trading overlap the European pre-open",
                   "USDKRW's 06:00-07:00 UTC share before vs after, control USDJPY",
                   ("USDKRW",), ("TSE",), _KRX, ("06:00", "07:00"), ("USDJPY",)),
        RuleChange("krx_short_ban_2023", "KRX", "2023-11-06", "short",
                   "shorting in KOSPI200/KOSDAQ150 constituents", "full short-sale ban",
                   "negative information cannot be expressed through borrowed stock; foreign "
                   "hedged long-short books unwind and the currency leg goes with them",
                   "USDKRW's KRX-hours share of daily absolute move before vs after, control "
                   "USDJPY", ("USDKRW",), ("TSE",), _KRX_SHORT, ("00:00", "06:30"),
                   ("USDJPY",)),
        RuleChange("krx_nxt_launch_2025", "KRX", "2025-03-04", "session",
                   "one venue, 09:00-15:30", "NXT pre-market 08:00 and after-market to 20:00",
                   "Korean equity price discovery extends into the European morning; the "
                   "currency's after-hours window gains an equity print to react to",
                   "USDKRW's 06:30-11:00 UTC share before vs after, control USDJPY",
                   ("USDKRW",), ("TSE",), _NXT, ("06:30", "11:00"), ("USDJPY",)),
        RuleChange("krx_short_resumption_2025", "KRX", "2025-03-31", "short",
                   "full short-sale ban", "shorting resumed market-wide with an uptick rule",
                   "the reverse of 2023-11-06", "as krx_short_ban_2023, signs reversed",
                   ("USDKRW",), ("TSE",), _KRX_SHORT, ("00:00", "06:30"), ("USDJPY",)),
        RuleChange("krx_vi_activations", "KRX", "2014-09-01", "auction",
                   "continuous trading through a 3% jump",
                   "a two-minute single-price call on every 3% (dynamic) or 10% (static) jump",
                   "a VI converts a print into a call: the post-VI single price should carry "
                   "less short-horizon reversal than an uninterrupted jump",
                   "UNMEASURED by construction on this desk: per-stock VI activation records "
                   "(KRX market data) are not held; USDKRW cannot see a single stock's call",
                   (), ("TSE",), _KRX),
        RuleChange("sse_closing_call_2018", "SSE_SZSE", "2018-08-20", "session",
                   "SSE closed on continuous trading", "14:57-15:00 closing call on SSE",
                   "the Shanghai close becomes one print; closing-price manipulation and the "
                   "index-fund closing flow move into the call",
                   "CHINAH's 06:00-07:00 UTC share before vs after, control JPN225",
                   _CN_SPILL, ("TSE",), _SSE, ("06:00", "07:00"), ("JPN225",)),
        RuleChange("cffex_curbs_2015", "CFFEX", "2015-09-07", "fee",
                   "0.23bp intraday fee, 10-20% margin", "23bp intraday fee, 40% margin, "
                   "10-lot abnormal-trading threshold",
                   "index-futures turnover collapses ~99%; hedging demand moves to H shares "
                   "and offshore, the A/H basis and the CNH carry the unmet hedge",
                   "CHINAH's mainland-hours share before vs after, control JPN225",
                   ("CHINAH", "USDCNH"), ("TSE",), _CFFEX, _MAINLAND, ("JPN225",)),
        RuleChange("china_programmatic_2024", "SSE_SZSE", "2024-10-08", "hft",
                   "exchange reporting only", "CSRC programmatic-trading provisions in force",
                   "programmatic traders bear reporting, monitoring and differentiated "
                   "supervision; the marginal machine order costs more, spreads in the "
                   "mainland session widen and the H-share hedge absorbs the difference",
                   "CHINAH and HK50's mainland-hours (01:30-07:00 UTC) share before vs after, "
                   "control JPN225", _CN_SPILL, ("TSE",), _CSRC, _MAINLAND, ("JPN225",)),
        RuleChange("china_programmatic_impl_2025", "SSE_SZSE", "2025-07-07", "hft",
                   "provisions without thresholds", "HFT defined at 300 orders/s, 20,000/day",
                   "a named threshold caps the order rate of the fastest participants",
                   "as china_programmatic_2024", _CN_SPILL, ("TSE",), _CSRC, _MAINLAND,
                   ("JPN225",)),
        RuleChange("china_programmatic_oct_2025", "SSE_SZSE", "2025-10-01", "hft",
                   "thresholds", "differentiated fees for high-frequency programmatic trading",
                   "the cancelled order is charged; quote refresh rates fall and the mainland "
                   "book thins at the top", "as china_programmatic_2024",
                   _CN_SPILL, ("TSE",), _CSRC_OCT25, _MAINLAND, ("JPN225",)),
        RuleChange("cffex_hft_fee_2026", "CFFEX", "2026-01-01", "fee",
                   "one fee for all", "differentiated fees for high-frequency trading",
                   "index-futures liquidity provision by the fastest participants is taxed; "
                   "the futures basis widens intraday and the H-share hedge is used more",
                   "CHINAH and HK50's mainland-hours share before vs after, control JPN225",
                   _CN_SPILL, ("TSE",), _CFFEX, _MAINLAND, ("JPN225",)),
    )
    return tuple(sorted(rows, key=lambda r: (r.date, r.change_id)))


# --------------------------------------------------------------------------- the experiment
def window_share_by_day(times: np.ndarray, close: np.ndarray,
                        window_utc: tuple[str, str]) -> tuple[np.ndarray, np.ndarray]:
    """Per trading day: the share of the day's absolute log move carried by bars whose OPEN
    minute (UTC) falls in `window_utc`. Days with no move are dropped, never zero-filled."""
    lo, hi = _hhmm(window_utc[0]), _hhmm(window_utc[1])
    if lo is None or hi is None or close.size < 3:
        return np.zeros(0, dtype="datetime64[D]"), np.zeros(0)
    c = np.asarray(close, dtype="float64")
    t = np.asarray(times, dtype="datetime64[ns]")[1:]
    with np.errstate(divide="ignore", invalid="ignore"):
        r = np.abs(np.diff(np.log(c)))
    ok = np.isfinite(r)
    t, r = t[ok], r[ok]
    days = t.astype("datetime64[D]")
    mins = ((t - days).astype("timedelta64[m]").astype("int64")) % 1440
    in_w = ((mins >= lo) & (mins < hi)) if lo <= hi else ((mins >= lo) | (mins < hi))
    uniq, inv = np.unique(days, return_inverse=True)
    tot = np.bincount(inv, weights=r, minlength=uniq.size)
    win = np.bincount(inv, weights=r * in_w, minlength=uniq.size)
    keep = tot > 0
    return uniq[keep], win[keep] / tot[keep]


def placebo_dates(days: np.ndarray, change: np.datetime64, pre: int, post: int,
                  step: int = 10) -> np.ndarray:
    """Candidate placebo change dates on `days` (sorted datetime64[D]): every `step` trading
    days, with `pre` days of room before and `post` after, and no overlap with the true
    change's own pre/post windows. The true date is never a placebo of itself."""
    n = days.size
    if n < pre + post + 1:
        return np.zeros(0, dtype="datetime64[D]")
    true_idx = int(np.searchsorted(days, change))
    idx = np.arange(pre, n - post, max(1, int(step)))
    idx = idx[np.abs(idx - true_idx) >= (pre + post)]
    return days[idx]


def _did_at(days_a: np.ndarray, share_a: np.ndarray, days_c: np.ndarray, share_c: np.ndarray,
            at: np.datetime64, pre: int, post: int) -> tuple[float | None, dict[str, Any]]:
    ia, ic = int(np.searchsorted(days_a, at)), int(np.searchsorted(days_c, at))
    pa, qa = share_a[max(0, ia - pre):ia], share_a[ia:ia + post]
    pc, qc = share_c[max(0, ic - pre):ic], share_c[ic:ic + post]
    detail: dict[str, Any] = {"n_pre_affected": int(pa.size), "n_post_affected": int(qa.size),
                              "n_pre_control": int(pc.size), "n_post_control": int(qc.size)}
    if min(pa.size, qa.size, pc.size, qc.size) < MIN_REGIME_DAYS:
        return None, detail
    did = (float(qa.mean()) - float(pa.mean())) - (float(qc.mean()) - float(pc.mean()))
    detail.update({"pre_affected": round(float(pa.mean()), 6),
                   "post_affected": round(float(qa.mean()), 6),
                   "pre_control": round(float(pc.mean()), 6),
                   "post_control": round(float(qc.mean()), 6)})
    return did, detail


def rule_change_effect(times: np.ndarray, close: np.ndarray, ctrl_times: np.ndarray,
                       ctrl_close: np.ndarray, change_date: str, window_utc: tuple[str, str],
                       *, pre_days: int = 120, post_days: int = 120, step: int = 10,
                       today: date | None = None) -> dict[str, Any]:
    """The natural experiment: a difference in differences of the window share between the
    affected tape and an unaffected control tape across `change_date`, with the null drawn
    from placebo change dates on the same two tapes.

    Verdicts: PROSPECTIVE (the change is after today), UNMEASURED (the change is outside the
    tape, first/last dates named), POORLY_MEASURED (too few regime days or placebos, counts
    named), MEASURED (did, p_placebo, the placebo distribution's quantiles, and the four
    regime means so a reader can see which side moved).
    """
    out: dict[str, Any] = {"verdict": "UNMEASURED", "change_date": change_date,
                           "window_utc": list(window_utc), "pre_days": int(pre_days),
                           "post_days": int(post_days), "n_placebo": 0}
    try:
        change = np.datetime64(change_date[:10], "D")
    except ValueError:
        out["why"] = f"change_date {change_date!r} is not ISO"
        return out
    now = today or datetime.now(UTC).date()
    if change > np.datetime64(now.isoformat(), "D"):
        out["verdict"] = "PROSPECTIVE"
        out["why"] = f"{change_date} is after {now.isoformat()}: pre-registered, not measured"
        return out
    days_a, share_a = window_share_by_day(times, close, window_utc)
    days_c, share_c = window_share_by_day(ctrl_times, ctrl_close, window_utc)
    if days_a.size == 0 or days_c.size == 0:
        out["why"] = "a tape is empty or the window is malformed"
        return out
    first, last = str(days_a[0]), str(days_a[-1])
    out["tape"] = {"first": first, "last": last, "n_days": int(days_a.size),
                   "control_n_days": int(days_c.size)}
    if change < days_a[0] or change > days_a[-1]:
        out["why"] = f"{change_date} is outside the tape {first}..{last}"
        return out
    did, detail = _did_at(days_a, share_a, days_c, share_c, change, pre_days, post_days)
    out.update(detail)
    if did is None:
        out["verdict"] = "POORLY_MEASURED"
        out["why"] = f"a regime side holds fewer than {MIN_REGIME_DAYS} days"
        return out
    draws: list[float] = []
    for p in placebo_dates(days_a, change, pre_days, post_days, step):
        d, _ = _did_at(days_a, share_a, days_c, share_c, p, pre_days, post_days)
        if d is not None:
            draws.append(d)
    arr = np.asarray(draws, dtype="float64")
    out["did"] = round(did, 6)
    out["n_placebo"] = int(arr.size)
    if arr.size < MIN_PLACEBOS:
        out["verdict"] = "POORLY_MEASURED"
        out["why"] = f"{arr.size} placebo dates < {MIN_PLACEBOS}"
        return out
    p = float((1 + int((np.abs(arr) >= abs(did)).sum())) / (1 + arr.size))
    out.update({"verdict": "MEASURED", "p_placebo": round(p, 6),
                "placebo_abs_q50": round(float(np.quantile(np.abs(arr), 0.5)), 6),
                "placebo_abs_q95": round(float(np.quantile(np.abs(arr), 0.95)), 6),
                "significant_5pct": bool(p <= 0.05), "significant_10pct": bool(p <= 0.10),
                "controls": ["unaffected control venue (difference in differences)",
                             "placebo change dates on the same tapes"]})
    return out


def unverified_rules(venues: Iterable[Venue]) -> list[dict[str, str]]:
    """Every rule row still waiting for its document, by venue -- the reading list."""
    return [{"venue": v.venue_id, "rule_id": r.rule_id, "citation": r.source.citation}
            for v in venues for r in v.rules if r.source.verified != VERIFIED]


# --------------------------------------------------------------------------- constraints
#: THE REGISTRY COMPILED INTO CONSTRAINTS THE MACHINE CAN READ. `universe.json` is MetaTrader's
#: own answer about every symbol (tick size, digits, contract size, volume step, swaps) and the
#: venue rules above say when the symbol trades, when it halts and how it settles. Neither is a
#: constraint until the two are joined per symbol, and until that join is a FILE a placer and a
#: campaign runner can read without importing this module. `compile_constraints` is that join.
#: An axis the registry does not carry (margin: the terminal's `margin_initial` is never synced
#: into the registry; the stops/freeze distance: read live at the order) is UNMEASURED by name on
#: the row -- the gateway reads the terminal for those and the row says so.
MEASURED = "MEASURED"
UNMEASURED = "UNMEASURED"
PARTIAL = "PARTIAL"
#: The broker registry's `asset_class` vocabulary (MetaTrader's own path names, lower-cased) ->
#: the Fusion instrument class its rule rows are keyed by. A class absent here is UNCLASSIFIED:
#: its session clause reads UNDECLARED, never a neighbour's hours.
CLASS_OF_ASSET: dict[str, str] = {
    "forex": "forex", "forex exotics": "forex", "forex majors": "forex", "forex minors": "forex",
    # MetaTrader files the spot metals (XAUUSD, XAGUSD, XPTUSD, the base metals) under
    # "Commodities" on this broker (measured on the registry 2026-09-22: 12 symbols, all X??USD
    # metals); the softs carry their own class and no session clause yet.
    "metals": "metals", "commodities": "metals", "indices": "indices", "equities": "equities",
    "us share cfds": "equities", "share cfds": "equities",
    "soft commodity": "softs", "energy": "energy", "crypto": "crypto", "bonds": "bonds",
}
#: Registry fields a constraint row is compiled from, by axis.
TICK_FIELDS: tuple[str, ...] = ("tick_size", "digits", "tick_value", "contract_size",
                                "volume_min", "volume_step", "median_spread_pts",
                                "spread_pts_at_collection")
MARGIN_FIELDS: tuple[str, ...] = ("margin_initial", "margin_maintenance", "margin_rate",
                                  "margin_hedged", "margin_currency")
CONSTRAINT_AXES: tuple[str, ...] = ("sessions", "halts", "tick", "margin", "settlement")
CONSTRAINTS_RULE = ("one row per registry symbol: sessions, halts, tick, margin and settlement "
                    "joined from MetaTrader's registry row and the venue rules in force on the "
                    "broker's local date; an axis the registry does not carry is UNMEASURED by "
                    "name and the gateway reads the terminal for it; a row is an INPUT to the "
                    "placer and the campaign runner, never a cap, a veto or a filter")
STOPS_LEVEL_WHY = ("the registry does not carry trade_stops_level or trade_freeze_level; the "
                   "gateway reads both from the terminal's symbol_info at the order")
MARGIN_WHY = ("the registry carries no margin field (the terminal's margin_initial is not "
              "synced); the gateway reads it at the order")


def instrument_class_of(asset_class: Any) -> str:
    """The Fusion instrument class of a registry `asset_class`, '' when unclassified."""
    return CLASS_OF_ASSET.get(str(asset_class or "").strip().lower(), "")


def next_closed_day(venue: Venue, day: date, horizon_days: int = 14) -> tuple[str, str] | None:
    """(ISO date, WEEKEND | HOLIDAY) of the venue's next closed day at or after `day` inside the
    horizon; None when every day in the horizon is open."""
    for i in range(max(1, int(horizon_days))):
        d = day + timedelta(days=i)
        state = closed_day_state(venue, d)
        if state:
            return d.isoformat(), state
    return None


def symbol_venue_map(venues: Iterable[Venue]) -> dict[str, str]:
    """Upper-cased MT5 symbol -> the UNDERLYING venue that lists it. The broker's own venue is
    excluded because every symbol trades on it; the first listing venue wins."""
    out: dict[str, str] = {}
    for v in venues:
        if v.venue_id == "FUSION":
            continue
        for s in v.mt5_symbols:
            out.setdefault(str(s).upper(), v.venue_id)
    return out


def _num(v: Any) -> float | None:
    if isinstance(v, bool) or not isinstance(v, (int, float)):
        return None
    f = float(v)
    return f if np.isfinite(f) else None


def _windows_of(rows: Sequence[RuleRow]) -> list[dict[str, Any]]:
    srule = _pick(rows, "session")
    if srule is None:
        return []
    return [{"name": w.name, "start": w.start, "end": w.end, "state": w.session_state,
             "auction": w.auction_state, "weekdays": list(w.weekdays)}
            for w in srule.spec.get("windows", ()) if isinstance(w, Window)]


def compile_symbol(symbol: str, meta: Mapping[str, Any], broker: Venue, now: datetime,
                   underlying: Venue | None = None) -> dict[str, Any]:
    """One symbol's constraint row: the registry row joined to the broker's rules in force on
    its local date at `now`, and to the underlying venue's state where one lists the symbol."""
    cls = instrument_class_of(meta.get("asset_class"))
    ts = _as_utc(now)
    st = state_at(broker, ts, cls or "unclassified")
    loc_day = local_time(ts, broker.tz).date()
    rows = rules_in_force(broker, loc_day, cls or "unclassified")
    windows = _windows_of(rows)
    roll = _pick(rows, "rollover")
    close = _pick(rows, "desk_close")
    under_state = state_at(underlying, ts) if underlying is not None else None
    nxt = next_closed_day(broker, loc_day)
    unmeasured: list[str] = []
    tick = {k: _num(meta.get(k)) for k in TICK_FIELDS}
    tick_ok = tick["tick_size"] is not None and tick["digits"] is not None
    if not tick_ok:
        unmeasured.append("tick: the registry row carries no tick_size/digits")
    margin_vals = {k: meta.get(k) for k in MARGIN_FIELDS if meta.get(k) is not None}
    if not margin_vals:
        unmeasured.append("margin: " + MARGIN_WHY)
    sessions_ok = st.session_state != "UNDECLARED"
    if not sessions_ok:
        unmeasured.append(f"sessions: no session clause for instrument class "
                          f"{cls or 'unclassified'!r} on {broker.venue_id}")
    status = (MEASURED if tick_ok and sessions_ok and margin_vals
              else PARTIAL if tick_ok else UNMEASURED)
    margin: dict[str, Any] = {"status": MEASURED if margin_vals else UNMEASURED, **margin_vals}
    if not margin_vals:
        margin["why"] = MARGIN_WHY
    return {
        "symbol": symbol, "asset_class": meta.get("asset_class"),
        "instrument_class": cls or UNMEASURED, "venue": broker.venue_id, "venue_tz": broker.tz,
        "sessions": {"status": MEASURED if sessions_ok else UNMEASURED, "windows": windows,
                     "state_now": st.session_state, "auction_now": st.auction_state,
                     "window_now": st.window, "local_time": st.local_time,
                     "closed_today": closed_day_state(broker, loc_day) or "",
                     "next_closed_day": nxt[0] if nxt else None,
                     "next_closed_state": nxt[1] if nxt else None,
                     "underlying_state_now": (under_state.session_state if under_state
                                              else None)},
        "halts": {"price_band": st.price_band, "weekly_closed": list(broker.weekly_closed),
                  "n_holidays": len(broker.holidays),
                  "daily_break": next((w for w in windows if w["state"] == "ROLLOVER"), None),
                  "desk_close_utc": (close.spec.get("close_utc") if close is not None
                                     else None),
                  "desk_close_book": close.spec.get("book") if close is not None else None,
                  "underlying_venue": underlying.venue_id if underlying is not None else None,
                  "underlying_price_band": (under_state.price_band if under_state
                                            else None)},
        "tick": {**tick, "status": MEASURED if tick_ok else UNMEASURED,
                 "stops_level": None, "freeze_level": None, "stops_level_why": STOPS_LEVEL_WHY},
        "margin": margin,
        "settlement": {"state": st.settlement_state,
                       "rollover_hour_utc": (roll.spec.get("rollover_hour_utc")
                                             if roll is not None else None),
                       "triple_swap_weekday": (roll.spec.get("triple_swap_weekday")
                                               if roll is not None else None),
                       "swap_long": _num(meta.get("swap_long")),
                       "swap_short": _num(meta.get("swap_short")),
                       "currency_profit": meta.get("currency_profit"),
                       "underlying_settlement": (under_state.settlement_state if under_state
                                                 else None)},
        "short_state": st.short_state, "fee_regime": st.fee_regime,
        "rule_version": st.rule_version, "rule_ids": list(st.rule_ids),
        "unverified": list(st.unverified), "status": status, "unmeasured": unmeasured,
    }


def compile_constraints(universe: Mapping[str, Any], venues: Sequence[Venue],
                        now: datetime) -> dict[str, Any]:
    """The whole registry compiled into machine-readable constraints at `now`.

    Pure: the registry mapping and the venues are given, nothing is read. The broker's venue is
    the FUSION venue among `venues` (or the module's own when absent); a symbol listed by another
    venue's `mt5_symbols` carries that venue's state beside the broker's as its underlying.
    """
    by_id = {v.venue_id: v for v in venues}
    broker = by_id.get("FUSION") or venue_fusion()
    under_ids = symbol_venue_map(venues)
    rows: dict[str, dict[str, Any]] = {}
    by_status: dict[str, int] = {}
    by_class: dict[str, int] = {}
    unmeasured_axes: dict[str, int] = {}
    for sym in sorted(universe):
        meta = universe[sym]
        if not isinstance(meta, Mapping):
            continue
        under = by_id.get(under_ids.get(str(sym).upper(), ""))
        row = compile_symbol(str(sym), meta, broker, now, under)
        rows[str(sym)] = row
        by_status[row["status"]] = by_status.get(row["status"], 0) + 1
        by_class[row["instrument_class"]] = by_class.get(row["instrument_class"], 0) + 1
        for u in row["unmeasured"]:
            axis = u.split(":", 1)[0]
            unmeasured_axes[axis] = unmeasured_axes.get(axis, 0) + 1
    return {
        "generated_at": _as_utc(now).isoformat(timespec="seconds"),
        "rules_version": RULES_VERSION, "venue": broker.venue_id, "venue_tz": broker.tz,
        "n_symbols": len(rows), "by_status": by_status, "by_instrument_class": by_class,
        "axes": list(CONSTRAINT_AXES), "unmeasured_axes": unmeasured_axes,
        "n_unverified_rules": sum(1 for r in broker.rules if r.source.verified != VERIFIED),
        "symbols": rows, "rule": CONSTRAINTS_RULE,
    }
