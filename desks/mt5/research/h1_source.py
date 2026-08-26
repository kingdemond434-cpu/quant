"""Where shadow gets its bars, and the stamp saying which.

SHADOW MUST NOT DEPEND ON A BROKER ACCEPTING ORDERS.

Shadow validation is a claim about what a strategy WOULD have done. It needs
bars and nothing else -- no terminal, no login, no funded account, no accepted
order. Yet `shadow_forward.fetch_h1` imported MetaTrader5 directly, so the whole
shadow record was hostage to a Windows box with a logged-in terminal. When the
Fusion switch paused that terminal, shadow stopped, and the daily cycle has been
failing on `ModuleNotFoundError: No module named 'MetaTrader5'` ever since.

That coupling was the bug. Forward evidence is the one thing that cannot be
recovered later -- a day of bars not evaluated is a day of evidence gone -- and
it was wired to the most fragile component in the system.

THE STAMP IS NOT BOOKKEEPING

A shadow record built on Yahoo bars is NOT the same evidence as one built on the
broker's own feed. The OHLC differ at the tick, the spread differs materially,
and session boundaries can shift by a broker's server offset. Silently mixing
them produces a ledger whose trades are not comparable to each other, and the
promotion gate would then be counting apples against oranges while reporting a
single expectancy.

So every source is recorded per fetch, and the caller writes it into the ledger.
Mixing is allowed -- half a record is better than none -- but it is VISIBLE, and
`SourceMix.homogeneous` tells the promoter whether it is looking at one
population or several.

ABSENCE OF BARS IS NOT ABSENCE OF SIGNALS

The failure that would quietly corrupt everything: a stale source returns bars
ending three days ago, the replay finds no entries in those three days, and the
state file records three days of "no trades". That is indistinguishable from a
strategy that legitimately stood aside, and it inflates the denominator of every
rate the promoter computes. `Bars.covers()` is how a caller asks whether it
actually has data for a period, and a gap is recorded as NO_DATA rather than as
a quiet market.
"""
from __future__ import annotations

import json
import os
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path

import pandas as pd

H1_SOURCE_VERSION = "h1src-2026-08-18-a"

BASE = Path(__file__).resolve().parent.parent
UNI = BASE / "data" / "universe"

#: A source whose freshest bar is older than this DURING TRADING HOURS is stale.
#: Generous, because a quiet Sunday is not a fault and gold trades ~23h a day;
#: anything past this on a weekday means the source is not keeping up.
STALE_AFTER_H = 6.0

_COLUMNS = ["open", "high", "low", "close", "tick_volume", "spread", "real_volume"]


def _market_open(ts: pd.Timestamp) -> bool:
    ts = pd.Timestamp(ts).tz_convert("UTC")
    wd, hour = ts.weekday(), ts.hour
    return not (wd == 5 or (wd == 4 and hour >= 22) or (wd == 6 and hour < 22))


def trading_lag_hours(last_bar: pd.Timestamp, end: datetime | pd.Timestamp) -> float:
    """Market-open hours missing after a bar; a closed weekend is not stale data."""
    cursor = pd.Timestamp(last_bar).ceil("h")
    finish = pd.Timestamp(end)
    cursor = cursor.tz_localize("UTC") if cursor.tzinfo is None else cursor.tz_convert("UTC")
    finish = finish.tz_localize("UTC") if finish.tzinfo is None else finish.tz_convert("UTC")
    hours = 0
    while cursor < finish:
        if _market_open(cursor):
            hours += 1
        cursor += pd.Timedelta(hours=1)
    return float(hours)


@dataclass
class Bars:
    """H1 bars plus the honest provenance of where they came from.

    `source` and `venue` are two DIFFERENT facts and conflating them welded the
    forward clocks shut. See `evidence_venue`.
    """
    df: pd.DataFrame
    source: str                     # ROUTE: MT5 | HTTP:<host> | CACHE:<file>
    fetched_utc: str
    why: str = ""
    promotion_authority: bool = False
    venue: str = ""                 # WHOSE PRINTS these are -- see evidence_venue

    @property
    def evidence_venue(self) -> str:
        """The venue whose prints this evidence IS, independent of how it was retrieved.

        THE DEFECT THIS FIXES (measured 2026-08-26). `shadow_forward` put `source` into the
        frozen sleeve identity. But `source` is a ROUTE -- "MT5:FusionMarkets-Live" when the
        Windows terminal answers, "CACHE:USDJPY_H1.parquet" when it does not -- and those are
        the SAME broker's bars arriving two different ways. `from_cache` already says so in
        code: it sets promotion_authority from broker_info.json precisely because cached Fusion
        bars "carry the same evidence quality as live broker bars for promotion". So every
        forward clock broke on identity drift on every run the terminal was down, which on this
        Linux box is every run: 195 IDENTITY BROKEN lines in reports, data_venue named in
        195/195. A break is terminal, so the 14-day window never survived a single day and
        nothing could ever reach promotion.

        The old field was ALSO blind to the change it existed to catch: a demo feed and a live
        feed reaching us by the same route both read "CACHE:<file>". broker_info.json currently
        records FusionMarkets-Demo while the frozen rows say FusionMarkets-Live -- a real venue
        change the transport string could not see. This property is therefore STRICTER, not
        looser: it ignores the route and reports the venue, so a genuine venue change breaks the
        clock and a terminal outage does not.

        Fails closed: an unrecoverable venue is "UNKNOWN-VENUE", which matches no frozen
        identity and so breaks the clock rather than quietly passing (L1.28a -- unmeasured is a
        real answer, never a clean verdict).
        """
        return self.venue or "UNKNOWN-VENUE"

    @property
    def n(self) -> int:
        return 0 if self.df is None else len(self.df)

    @property
    def freshest(self) -> pd.Timestamp | None:
        return None if self.df is None or self.df.empty else self.df.index.max()

    @property
    def age_hours(self) -> float | None:
        f = self.freshest
        if f is None:
            return None
        return (datetime.now(UTC) - f.to_pydatetime()).total_seconds() / 3600.0

    @property
    def trading_age_hours(self) -> float | None:
        f = self.freshest
        return None if f is None else trading_lag_hours(f, datetime.now(UTC))

    @property
    def stale(self) -> bool:
        a = self.trading_age_hours
        return a is not None and a > STALE_AFTER_H

    def covers(self, start: datetime, end: datetime | None = None) -> tuple:
        """Does this actually contain bars for the window? Returns (bool, why).

        THE CHECK THAT KEEPS A GAP FROM READING AS A QUIET MARKET. A caller that
        replays [start, end] without asking this records "no trades" for days it
        simply had no data for, and every rate the promoter computes is then
        divided by a denominator that includes them.
        """
        end = end or datetime.now(UTC)
        if self.df is None or self.df.empty:
            return False, f"{self.source} returned no bars at all"
        lo, hi = self.df.index.min(), self.df.index.max()
        if hi < pd.Timestamp(start):
            return False, (f"{self.source} ends {hi.isoformat()}, entirely before "
                           f"the window starting {start.isoformat()}: this period "
                           f"is NO DATA, not a quiet market")
        if lo > pd.Timestamp(start):
            return False, (f"{self.source} starts {lo.isoformat()}, after the "
                           f"window start {start.isoformat()}")
        gap_h = trading_lag_hours(hi, end)
        if gap_h > STALE_AFTER_H:
            return False, (f"{self.source} ends {hi.isoformat()}, {gap_h:.1f}h "
                           f"before the window end: the tail of this period is "
                           f"NO DATA, not an absence of signals")
        return True, f"{self.source} covers the window ({self.n} bars to {hi.isoformat()})"

    def stamp(self) -> dict:
        """What the caller writes into every ledger row built from these bars."""
        return {"bar_source": self.source, "evidence_venue": self.evidence_venue,
                "bars_fetched_utc": self.fetched_utc,
                "bars_freshest": None if self.freshest is None else self.freshest.isoformat(),
                "bars_stale": self.stale,
                "promotion_authority": self.promotion_authority,
                "h1_source_version": H1_SOURCE_VERSION}


def broker_utc_offset_hours(mt5_mod) -> float:
    """Measured offset between the broker's clock and true UTC, in hours.

    THE DEFECT THIS MEASURES. `copy_rates_*` returns the broker SERVER's wall time, not UTC.
    Stamping it `utc=True` -- as this file did -- labels every bar with a time it does not have.
    Measured 2026-08-26: a Fusion tick carried 04:29:03 while true UTC was 01:29:03, so every
    bar in the desk's history is labelled THREE HOURS LATE. Two things break silently:

      * any comparison between a bar timestamp and a real clock (a forward-window boundary, a
        staleness check, "is this bar fresh") is wrong by the offset;
      * session windows are hour-of-day filters. They still select coherent broker sessions --
        they were fitted and gauntleted on these labels, so the STRATEGIES are unaffected -- but
        the label "07:00 UTC" names an hour that is really 04:00 UTC.

    The fix is to record the offset rather than silently re-label history: the bars stay on the
    broker clock (which is what the sessions mean), and everything that must compare against a
    real clock converts explicitly through this number. Rounded to a quarter hour because broker
    offsets are whole or half hours; the residue is network latency, not a real offset.
    """
    from datetime import datetime as _dt
    from datetime import timezone as _tz
    try:
        tick = mt5_mod.symbol_info_tick("XAUUSD") or mt5_mod.symbol_info_tick("EURUSD")
        if tick is None or not getattr(tick, "time", 0):
            return 0.0
        broker = _dt.fromtimestamp(tick.time, _tz.utc)
        delta = (broker - _dt.now(_tz.utc)).total_seconds() / 3600.0
        return round(delta * 4) / 4
    except Exception:
        return 0.0


def _terminal_candidates() -> list[str]:
    """Configured terminal first, then explicitly configured/read-only fallbacks."""
    paths: list[str] = []
    try:
        from mt5desk.config import terminal_path
        paths.append(str(terminal_path()))
    except Exception:
        pass
    paths.extend(p for p in os.environ.get("MT5_SHADOW_TERMINALS", "").split(os.pathsep) if p)
    if os.name == "nt":
        paths.extend([
            r"C:\Program Files\Fusion Markets MetaTrader 5\terminal64.exe",
            r"C:\Program Files\VIG Group MT5 Terminal\terminal64.exe",
        ])
    return list(dict.fromkeys(paths))


def _normalise(df: pd.DataFrame) -> pd.DataFrame:
    """Every source lands in the same shape the engine expects.

    Missing columns are filled with 0.0 rather than dropped, because the engine
    indexes them by name; but `spread` filled with zero would make a free source
    look costless, so the CALLER's cost model is what charges spread -- see
    `per_symbol_costs`, which uses the account's measured spread and never the
    feed's column.
    """
    out = df.copy()
    out.columns = [str(c).lower() for c in out.columns]
    for col in _COLUMNS:
        if col not in out.columns:
            out[col] = 0.0
    if not isinstance(out.index, pd.DatetimeIndex):
        raise ValueError("bars must be indexed by a UTC DatetimeIndex")
    if out.index.tz is None:
        raise ValueError("bar index is timezone-naive; a naive index silently "
                         "shifts every session boundary by the server offset")
    return out[_COLUMNS].sort_index()


# ----------------------------------------------------------------- the sources

def from_mt5(sym: str, start: datetime) -> Bars | None:
    """The broker's own bars. Best evidence, least available."""
    try:
        import MetaTrader5 as mt5
    except ImportError:
        return None
    candidates: list[str | None] = [None] if mt5.terminal_info() is not None else []
    candidates.extend(_terminal_candidates())
    for terminal in candidates:
        try:
            if terminal is not None:
                mt5.shutdown()
                if not mt5.initialize(path=terminal, timeout=15_000):
                    continue
            account = mt5.account_info()
            server = str(getattr(account, "server", "unknown"))
            rates = mt5.copy_rates_range(sym, mt5.TIMEFRAME_H1, start,
                                         datetime.now(UTC))
            if rates is None or len(rates) < 100:
                continue
            df = pd.DataFrame(rates)
            # These are BROKER-CLOCK timestamps. `utc=True` here is a label, not a conversion --
            # kept because every session window and every gauntleted cell is defined on this
            # clock, and silently shifting history would change what the certified strategies do.
            # The honest part is publishing the offset so callers that compare against a real
            # clock can convert; see broker_utc_offset_hours().
            df["time"] = pd.to_datetime(df["time"], unit="s", utc=True)
            authority = "fusion" in server.casefold()
            offset = broker_utc_offset_hours(mt5)
            return Bars(
                _normalise(df.set_index("time")), f"MT5:{server}",
                datetime.now(UTC).isoformat(timespec="seconds"),
                f"broker-native bars on the BROKER clock (offset {offset:+.2f}h from UTC; "
                f"timestamps are labelled UTC but are not); capital authority only when the "
                f"server is the configured Fusion venue", authority,
                venue=f"MT5:{server}",
            )
        except Exception:
            continue
    return None


def from_cache(sym: str, start: datetime) -> Bars | None:
    """The parquet cached by `fetch_universe`. Works offline; goes stale.

    Kept as a real source rather than a fallback of last resort, because a
    strategy replayed on cached history up to the cache's end is valid evidence
    FOR THAT PERIOD. What it must not do is pretend to cover days it does not
    have, which is what `covers()` is for.

    Reads broker_info.json (written by refresh_tail.py on the Windows box)
    to determine promotion_authority: if the MT5 server is Fusion, the cached
    bars carry the same evidence quality as live broker bars for promotion.
    """
    p = UNI / f"{sym}_H1.parquet"
    if not p.exists():
        return None
    try:
        df = pd.read_parquet(p)
    except Exception:
        return None
    if df.empty:
        return None

    # Check broker_info.json for promotion_authority
    broker_info_path = UNI / "broker_info.json"
    is_fusion = False
    # THE VENUE TRAVELS WITH THE CACHE. broker_info.json already records which server the
    # parquet was refreshed from, so a cached bar can name its venue exactly as a live one
    # does. Without this the identity check saw only "CACHE:<file>" -- a route, not a venue.
    server = ""
    if broker_info_path.exists():
        try:
            broker_info = json.loads(broker_info_path.read_text(encoding="utf-8"))
            is_fusion = broker_info.get("is_fusion", False)
            server = str(broker_info.get("server") or "")
            # Per-symbol override if available
            sym_info = broker_info.get("symbols", {}).get(sym, {})
            if "is_fusion" in sym_info:
                is_fusion = sym_info["is_fusion"]
            if sym_info.get("server"):
                server = str(sym_info["server"])
        except Exception:
            pass

    b = Bars(_normalise(df), f"CACHE:{p.name}",
             datetime.now(UTC).isoformat(timespec="seconds"),
             "cached history \u2014 valid evidence up to its own end, and NO DATA "
             "after it. Re-run research/fetch_universe.py to extend.",
             promotion_authority=is_fusion,
             venue=f"MT5:{server}" if server else "UNKNOWN-VENUE")
    return b


#: Symbols as the free feeds spell them. A broker's XAUUSD, a futures front
#: month and a spot cross are NOT the same series -- they differ by carry, by
#: session and by roll -- so the mapping is written down rather than guessed, and
#: anything not listed is refused instead of being silently approximated.
_YF_SYMBOLS = {
    "XAUUSD": "XAUUSD=X", "XAGUSD": "XAGUSD=X",
    "EURUSD": "EURUSD=X", "GBPUSD": "GBPUSD=X", "USDJPY": "USDJPY=X",
    "AUDUSD": "AUDUSD=X", "USDCAD": "USDCAD=X", "USDCHF": "USDCHF=X",
    "NZDUSD": "NZDUSD=X", "EURJPY": "EURJPY=X", "GBPJPY": "GBPJPY=X",
    "CADJPY": "CADJPY=X", "CHFJPY": "CHFJPY=X", "AUDJPY": "AUDJPY=X",
    "NZDJPY": "NZDJPY=X", "EURGBP": "EURGBP=X", "EURCHF": "EURCHF=X",
    "AUDNZD": "AUDNZD=X", "NZDCAD": "NZDCAD=X", "AUDCAD": "AUDCAD=X",
}


def from_yfinance(sym: str, start: datetime) -> Bars | None:
    """H1 from Yahoo. No account, no key — the source that works on a VPS.

    NOT REGISTERED BY DEFAULT. Call `register_source(from_yfinance)` to enable
    it, because turning it on is a decision about evidence quality: these bars
    are a different series from the broker's, and a shadow ledger silently
    switching feeds mid-record would produce an expectancy averaged over two
    different games. Enabling it is deliberate; the stamp then makes it visible.

    Yahoo serves only ~730 days of hourly data, which is ample for a forward
    shadow record and useless for a backtest — do not reach for this to extend
    history, only to keep shadow alive.
    """
    try:
        import yfinance as yf
    except ImportError:
        return None
    tkr = _YF_SYMBOLS.get(sym.upper())
    if tkr is None:
        return None
    try:
        raw = yf.download(tkr, start=start.date().isoformat(), interval="1h",
                          progress=False, auto_adjust=False)
    except Exception:
        return None
    if raw is None or raw.empty:
        return None
    df = raw.copy()
    if isinstance(df.columns, pd.MultiIndex):        # yfinance >= 0.2.51
        df.columns = df.columns.get_level_values(0)
    df.columns = [str(c).lower() for c in df.columns]
    df = df.rename(columns={"volume": "tick_volume"})
    if df.index.tz is None:
        df.index = df.index.tz_localize("UTC")
    else:
        df.index = df.index.tz_convert("UTC")
    return Bars(_normalise(df), f"HTTP:yfinance/{tkr}",
                datetime.now(UTC).isoformat(timespec="seconds"),
                "free hourly bars — a DIFFERENT series from the broker's: no "
                "dealer spread, different session boundaries, and no guarantee "
                "the highs and lows match what the venue printed",
                venue="HTTP:yfinance")


#: Extra sources a deployment can register — an HTTP feed on the VPS, a vendor
#: API, whatever the operator has. Kept as a registry rather than hardcoded, so
#: this module needs no network dependency and no credentials of its own.
EXTRA_SOURCES: list = []


def register_source(fn: Callable[[str, datetime], Bars | None]) -> None:
    """Add a source. Tried after MT5 and before the cache."""
    EXTRA_SOURCES.append(fn)


def fetch_h1(sym: str, start: datetime,
             prefer: str | None = None,
             prefer_promotion_authority: bool = False) -> Bars | None:
    """First source that returns usable bars, in quality order.

    MT5 first because it is the venue actually traded; registered sources next
    because a live feed beats a stale file; cache last because it is always
    available and therefore would always win if it went first.

    Returns None only when NOTHING worked, which is a real condition the caller
    must handle as NO DATA rather than as an empty market.
    """
    chain = [("MT5", from_mt5)] + [(f"extra{i}", f) for i, f in enumerate(EXTRA_SOURCES)] \
            + [("CACHE", from_cache)]
    if prefer:
        chain.sort(key=lambda kv: 0 if kv[0].upper().startswith(prefer.upper()) else 1)
    best_proxy: Bars | None = None
    for _, fn in chain:
        try:
            b = fn(sym, start)
        except Exception:
            continue
        if b is not None and b.n > 0:
            if not prefer_promotion_authority or b.promotion_authority:
                return b
            if best_proxy is None:
                best_proxy = b
    return best_proxy


# --------------------------------------------------------------- the mix

@dataclass
class SourceMix:
    """Which sources a body of shadow evidence was built from."""
    counts: dict = field(default_factory=dict)

    def add(self, source: str, n: int = 1) -> None:
        self.counts[source] = self.counts.get(source, 0) + n

    @property
    def homogeneous(self) -> bool:
        return len(self.counts) <= 1

    def render(self) -> str:
        if not self.counts:
            return "no evidence recorded"
        if self.homogeneous:
            src, n = next(iter(self.counts.items()))
            return f"{n} row(s), all from {src}"
        parts = ", ".join(f"{k}={v}" for k, v in sorted(self.counts.items()))
        return (f"MIXED SOURCES ({parts}). These rows are not one population: "
                f"OHLC differ at the tick and spreads differ materially between "
                f"a broker feed and a free one, so an expectancy computed across "
                f"them is an average over two different games. Split before "
                f"promoting anything.")
