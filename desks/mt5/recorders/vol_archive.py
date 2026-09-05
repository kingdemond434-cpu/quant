"""The implied-vol and term-structure archive, on ground this desk can actually trade.

    py -3 -m recorders.vol_archive              # one observation cycle, appended
    py -3 -m recorders.vol_archive --dry-run    # observe and print, append nothing

WHAT THIS REPLACES AND WHAT IT KEEPS. A retired organ pulled a full option chain from a
crypto-exchange public API, built an IV surface, compared it to realised vol from the desk's own
parquets and appended each observation to an archive it described as "the proprietary dataset
being built from NOW (no paid history)". The archive idea was right and the ground was wrong: a
crypto-exchange options venue is a universe this desk may not hunt (2026-08-18 mandate). Two
things are carried over deliberately rather than reinvented:

  ITS HONESTY DISCIPLINE. It said plainly that a forward-only dataset has no backtest, and gave
  its candidates no promotion authority until enough vintages existed. That is kept, and
  sharpened -- see THE MOAT CLAIM below, which is more restrictive than the retired organ's.

  ITS ACCUMULATION SHAPE. Append-only, one observation per instrument per cycle, archived as its
  own artifact rather than recomputed on demand. That is what turns a query into an asset.

THE MOAT CLAIM, STATED HONESTLY, BECAUSE OVERCLAIMING IT WOULD BREAK THE FIRST RULE ABOVE.

This archive is a THINNER asset than the tick tape and the difference must not be blurred. The
tick tape is unbuyable at any price by anyone: no vendor sells one retail CFD broker's past quote
stream. The implied-vol series here are PUBLIC -- CBOE indices, keyless, with years of history
anyone can download this afternoon. So the honest inventory is:

  NOT PROPRIETARY, and never claimed as such: the level of ^VIX, ^GVZ, ^OVX, ^VXN on any past
  date. Anyone can have it. It is used here as REFERENCE HISTORY -- context, never a moat.

  PROPRIETARY, and genuinely unbuyable later, in two specific ways:
    1. THE VINTAGE. These series are restated. A reader in 2028 can get today's value of ^VIX as
       it stands THEN; nobody publishes an as-of view of what it read at 14:00 on the day, and
       the desk's own dated snapshot is the only record of what it could have acted on. That is
       the same point-in-time argument `libs/research/information_decay.py` makes for COT and
       macro prints, applied to vol.
    2. THE JOIN. Implied vol against THIS BROKER's realised vol, on THIS broker's bars, for the
       instrument this desk can actually trade. The variance risk premium a Fusion account faces
       on XAUUSD is not the premium GLD options imply, because the bars, the hours, the spread
       and the financing are all this desk's. That join exists nowhere else and accrues only
       forward.

  NO BACKTEST EXISTS FOR THE JOIN. The reference history can be replayed; the desk's own vintage
  series cannot, because it starts today. Every row this module writes carries `forward_only:
  true` and the report carries `desk_vintages` and refuses `backtestable` until MIN_VINTAGES of
  the desk's OWN observations exist. Nothing here promotes, sizes or conditions capital, ever.

THE GROUND IS MT5-TRADEABLE, AND THE MAPPING IS CHECKED AGAINST THE UNIVERSE, NOT ASSUMED.
Instrument ids come from `data/universe/universe.json` and nowhere else -- the same rule
`libs/research/causal_graph.py` follows, and for the same reason: a foreign alias that becomes a
node is a node the desk cannot trade. A vol series whose MT5 instrument is not on this account is
recorded as NOT_TRADEABLE_HERE with the candidate names that were tried, rather than dropped.

    ^GVZ   gold vol            -> XAUUSD
    ^OVX   crude vol           -> USOIL / WTI / UKOIL, whichever this broker lists
    ^VIX   S&P 500 30-day vol  -> US500 / SPX500 / USA500, with the 9D/30D/3M/6M term curve
    ^VXN   Nasdaq-100 vol      -> USTEC / NAS100 / NDX
    ^VXD   Dow vol             -> US30 / DJ30
    ^EVZ   EURUSD vol          -> EURUSD
    ^SKEW  S&P tail-risk skew  -> US500 (a skew PROXY, and named one: it is not a smile)

MEASURED 2026-09-05 FROM THIS CONTAINER, against the live endpoints. All six grounds answered and
the first cycle is worth reading, because it is already saying something:

    ^GVZ -> XAUUSD    iv 26.63   this broker's own 21d realised 28.51   VRP -1.89
    ^EVZ -> EURUSD    iv  7.51   this broker's own 21d realised  4.45   VRP +3.06
    ^VIX -> US500     iv 14.53   term 9D/30D/3M/6M in CONTANGO          rv UNMEASURED here
    ^OVX              iv 44.96   NOT_TRADEABLE_HERE: none of USOIL/WTI/UKOIL/BRENT is listed

Gold implied vol below this broker's realised, and euro implied well above it, is exactly the
kind of statement the join produces and the public series alone cannot. ^RVX (Russell) returns
HTTP 404 and is therefore not in GROUND at all rather than sitting in it as a permanent failure.
Absences are recorded as absences with the reason -- an unavailable series is a fact about the
world, and a module that quietly drops it teaches its reader the series was never wanted.

NOTHING HERE IS A SIGNAL. Every row is an observation. The gauntlet decides, this measures, and
the archive has no promotion authority in any lane.
"""
from __future__ import annotations

import argparse
import json
import math
import sys
import urllib.parse
import urllib.request
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Protocol

import numpy as np
import pandas as pd

_HERE = Path(__file__).resolve().parent
_DESK = _HERE.parent
for _p in (str(_DESK), str(_DESK.parent.parent)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from recorders.tape_store import _append_line  # noqa: E402

SCHEMA = "vol-archive-1"
ARCHIVE = _DESK / "data" / "vol_archive" / "observations.jsonl"
STATE = _DESK / "data" / "vol_archive" / "state.json"
REPORT = _DESK / "reports" / "VOL_ARCHIVE.json"
UNIVERSE = _DESK / "data" / "universe" / "universe.json"

#: The desk's OWN dated observations needed before anything derived from this archive may be
#: called backtestable. Sixty is roughly a quarter of trading days: enough to see one regime
#: change, nowhere near enough to certify anything, and it is a floor on ADMISSIBILITY rather
#: than a claim that sixty is sufficient. The gauntlet's own gates still apply on top.
MIN_VINTAGES = 60

#: Realised-vol window in trading days, matched to the 30-day horizon the CBOE indices quote so
#: the IV/RV comparison is like-for-like. A 21-day realised window against a 30-day implied one
#: is the standard variance-risk-premium construction; the mismatch is stated rather than hidden.
RV_WINDOW_D = 21
ANNUALISE = math.sqrt(252.0)

UA = "Mozilla/5.0 (MT5 research desk; point-in-time vol collector)"


@dataclass(frozen=True)
class Ground:
    """One implied-vol series and the MT5 instrument it is about."""

    vol_ticker: str
    #: Candidate MT5 symbols, in preference order. The FIRST one this account lists wins; if none
    #: are listed the row is NOT_TRADEABLE_HERE and says which names were tried.
    mt5_candidates: tuple[str, ...]
    what: str
    #: Extra tickers forming a term curve, shortest tenor first. Empty for a single-point series.
    term: tuple[str, ...] = ()
    #: A skew PROXY, where one exists keylessly. Never called a smile: the CBOE SKEW index is a
    #: single number summarising the tail of one surface, not the surface.
    skew_ticker: str = ""


GROUND: tuple[Ground, ...] = (
    Ground("^GVZ", ("XAUUSD", "GOLD", "XAUUSD.", "XAUUSDx"), "gold 30-day implied vol"),
    Ground("^OVX", ("USOIL", "WTI", "UKOIL", "BRENT", "CRUDE", "OIL"),
           "crude oil 30-day implied vol"),
    Ground("^VIX", ("US500", "SPX500", "USA500", "SP500", "US500.cash"),
           "S&P 500 30-day implied vol",
           term=("^VIX9D", "^VIX", "^VIX3M", "^VIX6M"), skew_ticker="^SKEW"),
    Ground("^VXN", ("USTEC", "NAS100", "NDX", "USTEC.cash", "NASDAQ"),
           "Nasdaq-100 30-day implied vol"),
    Ground("^VXD", ("US30", "DJ30", "DOW", "US30.cash"), "Dow Jones 30-day implied vol"),
    Ground("^EVZ", ("EURUSD",), "EURUSD 30-day implied vol"),
)

#: Tenors in days, for the term slope. Named here rather than parsed out of the ticker so a
#: renamed index cannot silently change what a slope means.
TENOR_DAYS: dict[str, int] = {"^VIX9D": 9, "^VIX": 30, "^VIX3M": 91, "^VIX6M": 182,
                              "^GVZ": 30, "^OVX": 30, "^VXN": 30, "^VXD": 30, "^EVZ": 30}


class VolSource(Protocol):
    """Where a daily implied-vol series comes from. One method, so a fake is trivial."""

    def series(self, ticker: str) -> dict[str, float] | None:
        """{iso_date: close} or None when the source will not answer. None is NOT an empty dict:
        an unreachable endpoint and an index with no history are different facts."""


class YahooVolSource:
    """Keyless CBOE volatility indices through the public chart API.

    TWO RANGES ARE FETCHED AND MERGED, AND THE REASON IS A MEASURED DEFECT IN THE SOURCE, not
    caution. Measured 2026-09-05 against the live endpoint:

        ^VIX     range=10y -> 2,515 points ending 2026-09-04   (current)
        ^VIX9D   range=10y -> 2,479 points ending 2026-07-17   (SEVEN WEEKS STALE)
        ^VIX9D   range=1mo ->     1 point  ending 2026-09-04   (current, no history)
        ^VIX3M, ^VIX6M: identical split

    The long-range endpoint carries the history and is stale for the term indices; the short-range
    endpoint is current and carries nothing behind it. A collector using either one alone gets a
    term curve that is either seven weeks out of date or one point long -- and the first failure
    is the dangerous one, because a stale 9-day tenor beside a fresh 30-day one manufactures a
    term slope out of a publication lag, and a term-structure signal would fire on exactly that.

    This also sharpens the archive's own justification. A public endpoint that cannot reproduce
    its own recent history means a desk that snapshots daily ends up holding a series the source
    itself will not serve -- which is the accumulation argument in its strongest form.

    Order of preference: the merged Yahoo pair, then `research/free_data.yahoo_daily` (the desk's
    declared keyless collector, with its own cache), then FRED. FRED is last because it was
    measured UNREACHABLE from this desk's research container on 2026-09-05 while Yahoo answered;
    on the trading box the order may well be worth reversing, and the fallback chain is the point
    rather than any one member of it.
    """

    def __init__(self, timeout: int = 20, range_: str = "10y", fresh_range: str = "1mo") -> None:
        self.timeout = timeout
        self.range = range_
        self.fresh_range = fresh_range
        self._fred_ok = True

    def series(self, ticker: str) -> dict[str, float] | None:
        history = self._chart(ticker, self.range)
        if history is None:
            try:
                from research import free_data as fd
                got = fd.yahoo_daily(ticker)
                history = {str(k): float(v) for k, v in got.items()} if got else None
            except Exception:
                history = None
        fresh = self._chart(ticker, self.fresh_range)
        if history is None and fresh is None:
            return self._fred(ticker)
        merged: dict[str, float] = dict(history or {})
        # THE FRESH TAIL WINS ON OVERLAP. It is the endpoint that is current, and where the two
        # disagree on a shared date the disagreement is the source restating itself -- which is
        # the very thing this archive's vintage claim is about.
        merged.update(fresh or {})
        return merged or None

    def _chart(self, ticker: str, range_: str) -> dict[str, float] | None:
        url = ("https://query1.finance.yahoo.com/v8/finance/chart/"
               + urllib.parse.quote(ticker) + f"?range={range_}&interval=1d")
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA})
            with urllib.request.urlopen(req, timeout=self.timeout) as r:
                doc = json.loads(r.read())
        except Exception:
            return None
        res = (doc.get("chart") or {}).get("result")
        if not res:
            return None
        node = res[0]
        stamps = node.get("timestamp") or []
        try:
            closes = node["indicators"]["quote"][0]["close"]
        except (KeyError, IndexError, TypeError):
            # A REAL AND MEANINGFUL ABSENCE. ^EVZ answers with a result block carrying no close
            # series, which is not the same as a 404 and not the same as a zero. Returning None
            # here makes the caller record it as an unavailable series rather than a flat one.
            return None
        out: dict[str, float] = {}
        for t, c in zip(stamps, closes, strict=False):
            if c is None:
                continue
            out[datetime.fromtimestamp(int(t), tz=UTC).date().isoformat()] = float(c)
        return out or None

    def _fred(self, ticker: str) -> dict[str, float] | None:
        sid = {"^VIX": "VIXCLS", "^GVZ": "GVZCLS", "^OVX": "OVXCLS", "^VXN": "VXNCLS",
               "^VXD": "VXDCLS", "^EVZ": "EVZCLS", "^VIX3M": "VXVCLS"}.get(ticker)
        if not sid or not self._fred_ok:
            return None
        try:
            from research import free_data as fd
            got = fd.fred_series(sid, start="2015-01-01")
        except Exception:
            self._fred_ok = False
            return None
        return {str(k): float(v) for k, v in got.items()} if got else None


class FakeVolSource:
    """A deterministic vol source for tests. Holds whatever the test puts in it."""

    def __init__(self, data: dict[str, dict[str, float]] | None = None,
                 missing: set[str] | None = None) -> None:
        self.data = data or {}
        self.missing = missing or set()
        self.asked: list[str] = []

    def series(self, ticker: str) -> dict[str, float] | None:
        self.asked.append(ticker)
        if ticker in self.missing:
            return None
        return self.data.get(ticker)


@dataclass
class Observation:
    """One instrument, one cycle. Append-only; this row is never edited."""

    schema: str
    observed_at: str
    #: The date the IV value is FOR, which is not the date it was observed. A close published
    #: today describes today, but a stale index republishing yesterday describes yesterday, and
    #: the two must never collapse -- that collapse is the point-in-time violation
    #: `libs/research/information_decay.py` refuses for every other input class.
    value_date: str
    vol_ticker: str
    mt5_symbol: str | None
    tradeable: bool
    what: str
    implied_vol: float | None = None
    #: Days of staleness between `value_date` and `observed_at`. Zero on a live trading day.
    value_age_days: int = 0
    term: dict[str, float] = field(default_factory=dict)
    term_slope_short: float | None = None
    term_slope_long: float | None = None
    term_shape: str = ""
    #: WHY the curve is short, when it is. An empty `term` with no reason is an absence rendered
    #: as "no term structure exists", which is a different and false claim.
    term_reason: str = ""
    skew_proxy: float | None = None
    realised_vol_cc: float | None = None
    realised_vol_parkinson: float | None = None
    realised_window_d: int = RV_WINDOW_D
    realised_last_bar: str = ""
    variance_risk_premium: float | None = None
    iv_over_rv: float | None = None
    status: str = "OBSERVED"
    reason: str = ""
    #: BINDING AND ALWAYS TRUE HERE. The desk's own series starts the day this first ran; the
    #: reference history behind it is public and is not this desk's vintage.
    forward_only: bool = True


def resolve_symbol(candidates: tuple[str, ...], registry: dict[str, Any]) -> str | None:
    """The first candidate this ACCOUNT lists, or None. Never invents an instrument id."""
    for c in candidates:
        if c in registry:
            return c
    lower = {k.casefold(): k for k in registry}
    for c in candidates:
        hit = lower.get(c.casefold())
        if hit:
            return hit
    return None


def realised_vol(symbol: str, universe_dir: Path, window_d: int = RV_WINDOW_D
                 ) -> tuple[float | None, float | None, str]:
    """(close-to-close, Parkinson, last bar) annualised realised vol in PERCENT, from the desk's
    own bars.

    TWO ESTIMATORS, ON PURPOSE. Close-to-close is what the variance-risk-premium literature uses
    and is comparable to an implied number; Parkinson uses the bar's own high-low range and is
    roughly five times more efficient per observation. They disagree when the day trends inside
    its range versus chops within it, and a premium that only exists under one of them is a
    property of the estimator rather than of the market. Reporting both is what makes that
    visible; picking one and calling it realised vol is what hides it.

    Percent, to match the CBOE indices' own units. A ratio-versus-percent mix here would be the
    same class of unit bug `mt5desk/universe.py` records costing this desk a whole asset class.
    """
    path = universe_dir / f"{symbol}_H1.parquet"
    if not path.exists():
        return None, None, ""
    try:
        df = pd.read_parquet(path, columns=["high", "low", "close"])
    except (OSError, ValueError, KeyError):
        return None, None, ""
    if df.empty:
        return None, None, ""
    idx = pd.DatetimeIndex(df.index)
    daily = df.groupby(idx.date).agg(high=("high", "max"), low=("low", "min"),
                                     close=("close", "last"))
    daily = daily.tail(window_d + 1)
    if len(daily) < max(5, window_d // 2):
        return None, None, str(idx.max())
    close = daily["close"].to_numpy(dtype=float)
    ret = np.diff(np.log(close[close > 0])) if (close > 0).all() else np.array([])
    cc = (float(np.std(ret, ddof=1) * ANNUALISE * 100.0)
          if ret.size >= 4 and np.isfinite(ret).all() else None)
    hi = daily["high"].to_numpy(dtype=float)
    lo = daily["low"].to_numpy(dtype=float)
    ok = (hi > 0) & (lo > 0) & (hi >= lo)
    park = None
    if int(np.count_nonzero(ok)) >= 5:
        rng = np.log(hi[ok] / lo[ok]) ** 2
        park = float(math.sqrt(rng.mean() / (4.0 * math.log(2.0))) * ANNUALISE * 100.0)
    return cc, park, str(idx.max())


def term_metrics(term: dict[str, float]) -> tuple[float | None, float | None, str]:
    """(short slope, long slope, shape) from a tenor curve, in vol points per log-tenor.

    Slope in VOL POINTS PER LOG-TENOR rather than raw difference, because tenors are
    multiplicative (9d, 30d, 91d, 182d) and a raw difference makes the 3M-to-6M step look four
    times more informative than the 9D-to-30D one purely because the calendar gap is longer.
    """
    pts = sorted(((TENOR_DAYS.get(k, 0), v) for k, v in term.items() if TENOR_DAYS.get(k)),
                 key=lambda kv: kv[0])
    if len(pts) < 2:
        return None, None, ""

    def slope(a: tuple[int, float], b: tuple[int, float]) -> float:
        return round((b[1] - a[1]) / (math.log(b[0]) - math.log(a[0])), 4)

    short = slope(pts[0], pts[1])
    long_ = slope(pts[-2], pts[-1]) if len(pts) >= 3 else None
    rising = all(pts[i][1] <= pts[i + 1][1] for i in range(len(pts) - 1))
    falling = all(pts[i][1] >= pts[i + 1][1] for i in range(len(pts) - 1))
    shape = "contango" if rising else ("backwardation" if falling else "mixed")
    return short, long_, shape


def observe(source: VolSource, registry: dict[str, Any], universe_dir: Path,
            now: datetime | None = None) -> list[Observation]:
    """One cycle: every ground, whether it answered, and the join to this desk's own bars."""
    now = now or datetime.now(tz=UTC)
    at = now.isoformat(timespec="seconds")
    out: list[Observation] = []
    for g in GROUND:
        sym = resolve_symbol(g.mt5_candidates, registry)
        base = {"schema": SCHEMA, "observed_at": at, "vol_ticker": g.vol_ticker,
                "mt5_symbol": sym, "tradeable": sym is not None, "what": g.what}
        s = source.series(g.vol_ticker)
        if not s:
            out.append(Observation(**base, value_date="", status="UNAVAILABLE",
                                   reason=(f"{g.vol_ticker} returned no series -- recorded as an "
                                           f"absence, not as a flat or missing value")))
            continue
        vdate = max(s)
        iv = float(s[vdate])
        obs = Observation(**base, value_date=vdate, implied_vol=round(iv, 4))
        obs.value_age_days = max(0, (now.date() - datetime.fromisoformat(vdate).date()).days)

        term: dict[str, float] = {}
        stale: list[str] = []
        for t in (g.term or (g.vol_ticker,)):
            ts = s if t == g.vol_ticker else source.series(t)
            if not ts:
                stale.append(f"{t}=unavailable")
                continue
            # THE SAME AS-OF DATE FOR EVERY TENOR, or the curve is not a curve. Mixing a fresh
            # 30-day quote with a stale 6-month one manufactures a slope out of a publication
            # lag, which is exactly the shape a term-structure signal would fire on. A tenor with
            # no value on THIS date is omitted, and the omission is REPORTED -- an empty curve
            # with no reason reads as "this instrument has no term structure", which is false.
            v = ts.get(vdate)
            if v is None:
                stale.append(f"{t}=last {max(ts)}")
                continue
            term[t] = round(float(v), 4)
        obs.term = term
        obs.term_slope_short, obs.term_slope_long, obs.term_shape = term_metrics(term)
        if stale and len(term) < 2:
            obs.term_reason = (f"no contemporaneous curve on {vdate}: " + ", ".join(stale)
                               + " -- refusing to build a slope across as-of dates")
        elif stale:
            obs.term_reason = "partial curve; missing on this date: " + ", ".join(stale)

        if g.skew_ticker:
            sk = source.series(g.skew_ticker)
            if sk and sk.get(vdate) is not None:
                obs.skew_proxy = round(float(sk[vdate]), 4)

        if sym:
            cc, park, last = realised_vol(sym, universe_dir)
            obs.realised_vol_cc = round(cc, 4) if cc is not None else None
            obs.realised_vol_parkinson = round(park, 4) if park is not None else None
            obs.realised_last_bar = last
            if cc is not None:
                obs.variance_risk_premium = round(iv - cc, 4)
                obs.iv_over_rv = round(iv / cc, 4) if cc > 0 else None
        else:
            obs.status = "NOT_TRADEABLE_HERE"
            obs.reason = (f"none of {', '.join(g.mt5_candidates)} is listed on this account, so "
                          f"the IV is recorded without a join rather than joined to an "
                          f"instrument the desk cannot trade")
        out.append(obs)
    return out


def append(observations: list[Observation], path: Path = ARCHIVE) -> int:
    """Append one cycle to the archive. APPEND-ONLY: a row is never edited or removed.

    An observation with no implied vol is still written. "We asked and the source was down" is
    a fact about the archive's own coverage, and an archive that only records its successes
    cannot tell a quiet week from a broken collector -- the same reason the tick tape records
    its gaps.
    """
    n = 0
    for o in observations:
        _append_line(path, json.dumps(asdict(o), separators=(",", ":")))
        n += 1
    return n


def read_archive(path: Path = ARCHIVE) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    try:
        for line in path.read_text("utf-8").splitlines():
            if line.strip():
                try:
                    rows.append(json.loads(line))
                except ValueError:
                    continue
    except OSError:
        return []
    return rows


def report(rows: list[dict[str, Any]], cycle: list[Observation]) -> dict[str, Any]:
    """What the archive holds, and what it is and is not yet entitled to claim."""
    vintages: dict[str, set[str]] = {}
    for r in rows:
        if r.get("implied_vol") is not None and r.get("value_date"):
            vintages.setdefault(str(r.get("vol_ticker")), set()).add(str(r["value_date"]))
    per_ticker = {k: len(v) for k, v in sorted(vintages.items())}
    least = min(per_ticker.values()) if per_ticker else 0
    return {
        "schema": SCHEMA,
        "generated_utc": datetime.now(tz=UTC).isoformat(timespec="seconds"),
        "archive": str(ARCHIVE),
        "rows_total": len(rows),
        "rows_this_cycle": len(cycle),
        "desk_vintages_per_ticker": per_ticker,
        "desk_vintages_min": least,
        "min_vintages_for_backtestable": MIN_VINTAGES,
        # THE HONESTY LINE, CARRIED OVER FROM THE RETIRED ORGAN AND MADE STRICTER. Nothing
        # derived from this archive may claim a backtest until the DESK'S OWN vintage series is
        # long enough; the public reference history behind it does not count, because it is not
        # what a decision would have seen.
        "backtestable": bool(least >= MIN_VINTAGES),
        "promotion_authority": False,
        "forward_only": True,
        "moat_claim": {
            "not_proprietary": ("the level of any CBOE volatility index on any past date -- "
                                "public, keyless, downloadable this afternoon. Used as reference "
                                "context and never claimed as an asset."),
            "proprietary_vintage": ("the desk's own dated snapshot of what each series READ at "
                                    "the moment it was observed. These series are restated and "
                                    "nobody publishes an as-of view, so this record cannot be "
                                    "reconstructed later."),
            "proprietary_join": ("implied vol against THIS broker's realised vol on THIS "
                                 "broker's bars for the instrument this desk can actually trade. "
                                 "The variance risk premium a Fusion account faces on XAUUSD is "
                                 "not the premium GLD options imply."),
            "loss_rate_vs_tick_tape": ("far lower. A missed day of vol observations costs one "
                                       "daily vintage; a missed hour of ticks costs every quote "
                                       "in it. This archive is second priority to the tape and "
                                       "is scheduled accordingly."),
        },
        "cycle": [asdict(o) for o in cycle],
        "unavailable": [o.vol_ticker for o in cycle if o.status == "UNAVAILABLE"],
        "not_tradeable_here": [o.vol_ticker for o in cycle if o.status == "NOT_TRADEABLE_HERE"],
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Accumulate the MT5-ground implied-vol archive")
    ap.add_argument("--dry-run", action="store_true", help="observe and print; append nothing")
    ap.add_argument("--out", type=Path, default=REPORT)
    ap.add_argument("--archive", type=Path, default=ARCHIVE)
    ap.add_argument("--universe", type=Path, default=_DESK / "data" / "universe")
    args = ap.parse_args(argv)

    try:
        registry = json.loads(UNIVERSE.read_text("utf-8"))
    except (OSError, ValueError):
        registry = {}
    if not registry:
        print("vol_archive: universe.json is unreadable -- refusing to map a vol series to an "
              "instrument id this desk cannot confirm it trades (that is how a foreign alias "
              "becomes a node). Observing WITHOUT the join.")

    cycle = observe(YahooVolSource(), registry, args.universe)
    rows = read_archive(args.archive)
    if not args.dry_run:
        append(cycle, args.archive)
        rows = rows + [asdict(o) for o in cycle]
    rep = report(rows, cycle)
    if not args.dry_run:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json.dumps(rep, indent=1, sort_keys=True) + "\n", "utf-8")

    got = [o for o in cycle if o.implied_vol is not None]
    print(f"vol_archive: {len(got)}/{len(cycle)} series observed, "
          f"{rep['rows_total']} archive rows, min desk vintages {rep['desk_vintages_min']} "
          f"(backtestable at {MIN_VINTAGES}: {rep['backtestable']})")
    for o in cycle:
        if o.implied_vol is None:
            print(f"  {o.vol_ticker:<7} {o.status}: {o.reason[:80]}")
            continue
        rv = (f"rv_cc={o.realised_vol_cc}" if o.realised_vol_cc is not None else "rv=UNMEASURED")
        print(f"  {o.vol_ticker:<7} -> {o.mt5_symbol!s:<8} iv={o.implied_vol:<7} {rv:<18} "
              f"vrp={o.variance_risk_premium} term={o.term_shape or '-'}")
    print(f"YIELD observed={len(got)} rows={rep['rows_total']} "
          f"vintages={rep['desk_vintages_min']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
