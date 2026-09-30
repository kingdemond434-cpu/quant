"""POINT-IN-TIME FUNDAMENTALS FOR THE SHARE CFDs: built from SEC XBRL, stamped when KNOWABLE.

WHAT THIS IS. The pure half of the quantamental dataset: it turns one SEC `companyfacts` document
(plus the accession -> acceptance map from the SEC `submissions` document) into a table of
SNAPSHOTS, one per moment the market could first know something new about the company, and it
reads that table back as-of any decision stamp. The fetch, the refresh clock and the coverage
artifact are `research/sec_fundamentals.py`; the families that rank on it are
`mt5desk/families_quantamental.py`.

THE ONE RULE: EVERY VALUE CARRIES ITS AVAILABILITY, NEVER ITS PERIOD END. A 10-Q for the quarter
ending 30 June is accepted in late July; a backtest that reads the June EPS on 30 June has read a
number that did not exist yet, and because reported numbers correlate with the returns that
preceded them, the error looks exactly like skill. So:

  * a fact's `available` is the ACCEPTANCE time of the filing that carried it, from the
    `submissions` document, read CONSERVATIVELY: the SEC stamps `acceptanceDateTime` with a `Z`
    but the clock is Eastern, so it is read as Eastern at the winter offset (+5h), which is never
    earlier than the truth in either season;
  * a fact whose accession is not in the submissions map (older than the recent list) is
    available at its `filed` DATE + 1 day, 06:00 UTC -- after the latest possible acceptance on
    that date (EDGAR accepts to 22:00 ET = 03:00 UTC next day);
  * a period restated in a later filing keeps BOTH values: before the restatement's acceptance
    the original is what was known, after it the restatement. Snapshots are recomputed at every
    availability instant from exactly the facts visible then.

FIELDS PER SNAPSHOT: trailing-twelve-month revenue, gross profit, operating income, net income and
diluted EPS; gross, operating and net margin; book value (stockholders' equity), shares
outstanding, debt, cash, and ROE. The price-derived ratios (P/E, P/B, EV/Sales, earnings yield)
are computed against the bar store's close AT THE DECISION BAR by `valuation`, never stored,
because a stored ratio would freeze the price of the day it was built.

TTM, WITHOUT LOOKAHEAD. At a snapshot, E is the latest period end visible. When a ~1-year fact
ends at E, TTM is that fact. Otherwise TTM = FY_last + YTD(E) - YTD_prior_year, the standard
identity, using only facts visible at the snapshot; failing that, the four latest contiguous
quarters. Anything else is NaN -- never a stale annual carried as if it were current.

USD ONLY. A figure in another currency (a 20-F filer reporting in TWD, CNY, JPY or EUR) is not
comparable with a USD CFD price without an FX leg and an ADR ratio this module does not have, so
those companies are reported as UNCOVERED with the reason, never converted by a guess.
"""
from __future__ import annotations

import math
from collections.abc import Iterable
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from libs.regime import session_clock

BASE = Path(__file__).resolve().parent.parent
#: The lake file the refresh leg writes and every family reads. Module-level for tests.
PIT_PATH = BASE / "data" / "lake" / "fundamentals" / "sec_pit.parquet"

#: Concept preference per field (first present wins, per period). us-gaap then ifrs-full.
FLOW_CONCEPTS: dict[str, tuple[str, ...]] = {
    "revenue": ("Revenues", "RevenueFromContractWithCustomerExcludingAssessedTax",
                "RevenueFromContractWithCustomerIncludingAssessedTax", "SalesRevenueNet",
                "Revenue"),
    "gross_profit": ("GrossProfit",),
    "operating_income": ("OperatingIncomeLoss", "ProfitLossFromOperatingActivities"),
    "net_income": ("NetIncomeLoss", "ProfitLossAttributableToOwnersOfParent", "ProfitLoss"),
    "eps": ("EarningsPerShareDiluted", "EarningsPerShareBasic",
            "DilutedEarningsLossPerShare", "BasicEarningsLossPerShare"),
}
INSTANT_CONCEPTS: dict[str, tuple[str, ...]] = {
    "book_value": ("StockholdersEquity",
                   "StockholdersEquityIncludingPortionAttributableToNoncontrollingInterest",
                   "EquityAttributableToOwnersOfParent", "Equity"),
    "shares": ("EntityCommonStockSharesOutstanding", "CommonStockSharesOutstanding"),
    "debt": ("LongTermDebt", "LongTermDebtNoncurrent", "LongTermBorrowings"),
    "cash": ("CashAndCashEquivalentsAtCarryingValue",
             "CashCashEquivalentsRestrictedCashAndRestrictedCashEquivalents",
             "CashAndCashEquivalents"),
}
TAXONOMIES = ("us-gaap", "ifrs-full", "dei")
#: The unit each field must carry; anything else (a foreign currency) is not read.
UNIT = {"eps": "USD/shares", "shares": "shares"}

#: The columns a snapshot row carries, in order.
FIELDS = ("revenue_ttm", "gross_profit_ttm", "operating_income_ttm", "net_income_ttm",
          "eps_ttm", "gross_margin", "operating_margin", "net_margin", "book_value", "shares",
          "debt", "cash", "roe")

_DAY = timedelta(days=1)


# ---------------------------------------------------------------------------- availability ---
def acceptance_map(submissions: dict | None) -> dict[str, datetime]:
    """accession -> conservative UTC availability, from an SEC submissions document."""
    out: dict[str, datetime] = {}
    if not isinstance(submissions, dict):
        return out
    blocks = [((submissions.get("filings") or {}).get("recent") or {})]
    for block in blocks:
        accns = block.get("accessionNumber") or []
        accepted = block.get("acceptanceDateTime") or []
        for a, t in zip(accns, accepted, strict=False):
            try:
                naive = datetime.fromisoformat(str(t).replace("Z", "").split(".")[0])
            except ValueError:
                continue
            # Eastern clock labelled Z: read at the winter offset, never earlier than the truth.
            out[str(a)] = naive.replace(tzinfo=UTC) + timedelta(hours=5)
    return out


def _available(fact: dict, accepted: dict[str, datetime]) -> datetime | None:
    hit = accepted.get(str(fact.get("accn") or ""))
    if hit is not None:
        return hit
    try:
        filed = datetime.fromisoformat(str(fact.get("filed"))).replace(tzinfo=UTC)
    except ValueError:
        return None
    return filed + _DAY + timedelta(hours=6)


def _date(v: Any) -> datetime | None:
    try:
        return datetime.fromisoformat(str(v)).replace(tzinfo=UTC)
    except (TypeError, ValueError):
        return None


# ------------------------------------------------------------------------------- the facts ---
def _records(facts: dict, concepts: tuple[str, ...], unit: str,
             accepted: dict[str, datetime], flow: bool) -> list[tuple]:
    """(concept_rank, start, end, available, value, accn) for every USD fact of the concepts."""
    out: list[tuple] = []
    body = (facts or {}).get("facts") or {}
    for rank, concept in enumerate(concepts):
        for tax in TAXONOMIES:
            node = (body.get(tax) or {}).get(concept)
            if not isinstance(node, dict):
                continue
            for fact in (node.get("units") or {}).get(unit) or []:
                end = _date(fact.get("end"))
                start = _date(fact.get("start")) if flow else None
                if end is None or (flow and start is None):
                    continue
                av = _available(fact, accepted)
                try:
                    val = float(fact.get("val"))
                except (TypeError, ValueError):
                    continue
                if av is None or not math.isfinite(val):
                    continue
                out.append((rank, start, end, av, val, str(fact.get("accn") or "")))
    return out


def _asof(records: list[tuple], t: datetime, flow: bool) -> dict:
    """{(start, end): value} as known at `t`: per period the best-ranked concept, and within it
    the LATEST filing accepted at or before `t` (a restatement replaces, never precedes)."""
    best: dict[tuple, tuple] = {}
    for rank, start, end, av, val, accn in records:
        if av > t:
            continue
        key = (start, end) if flow else (end,)
        cur = best.get(key)
        cand = (rank, -av.timestamp(), val, accn)
        if cur is None or (cand[0], cand[1]) < (cur[0], cur[1]):
            best[key] = cand
    return {k: v[2] for k, v in best.items()}


def _instant_asof(records: list[tuple], t: datetime, sum_classes: bool) -> float:
    """The latest period-end value visible at `t` (classes summed for the share count)."""
    visible = [r for r in records if r[3] <= t]
    if not visible:
        return float("nan")
    end = max(r[2] for r in visible)
    at_end = [r for r in visible if r[2] == end]
    rank = min(r[0] for r in at_end)
    at_end = [r for r in at_end if r[0] == rank]
    latest = max(r[3] for r in at_end)
    rows = [r for r in at_end if r[3] == latest]
    if sum_classes:
        return float(sum(r[4] for r in rows))
    return float(rows[0][4])


def _days(a: datetime, b: datetime) -> float:
    return (b - a).total_seconds() / 86400.0


def ttm(periods: dict) -> tuple[float, datetime | None]:
    """(trailing-twelve-month value, period end) from {(start, end): value} visible now."""
    if not periods:
        return float("nan"), None
    end = max(e for _s, e in periods)
    at_end = {(s, e): v for (s, e), v in periods.items() if e == end}
    for (s, e), v in at_end.items():
        if 350 <= _days(s, e) <= 380:
            return float(v), end
    # YTD identity: FY_last + YTD(E) - YTD_prior
    ytd = [(s, e, v) for (s, e), v in at_end.items() if 80 <= _days(s, e) < 350]
    ytd.sort(key=lambda r: _days(r[0], r[1]), reverse=True)
    for s, e, v in ytd:
        span = _days(s, e)
        fy = [val for (fs, fe), val in periods.items()
              if 350 <= _days(fs, fe) <= 380 and abs(_days(fe, s - _DAY)) <= 10]
        prior = [val for (ps, pe), val in periods.items()
                 if abs(_days(pe, e - timedelta(days=365))) <= 10
                 and abs(_days(ps, pe) - span) <= 10]
        if fy and prior:
            return float(fy[0] + v - prior[0]), end
    # four contiguous quarters
    quarters = sorted(((s, e, v) for (s, e), v in periods.items() if 80 <= _days(s, e) <= 100),
                      key=lambda r: r[1], reverse=True)
    chain = []
    for s, e, v in quarters:
        if not chain:
            if e != end:
                break
            chain.append((s, e, v))
        elif abs(_days(e, chain[-1][0] - _DAY)) <= 10:
            chain.append((s, e, v))
        if len(chain) == 4:
            return float(sum(c[2] for c in chain)), end
    return float("nan"), end


def build_snapshots(companyfacts: dict, submissions: dict | None = None) -> pd.DataFrame:
    """One row per availability instant: the TTM and balance-sheet fields as known then.

    Columns: available (UTC, tz-aware), period_end, and FIELDS. Empty frame when the document
    carries no USD fact at all (a foreign-currency filer), which the caller reports as UNCOVERED.
    """
    accepted = acceptance_map(submissions)
    flows = {f: _records(companyfacts, c, UNIT.get(f, "USD"), accepted, True)
             for f, c in FLOW_CONCEPTS.items()}
    insts = {f: _records(companyfacts, c, UNIT.get(f, "USD"), accepted, False)
             for f, c in INSTANT_CONCEPTS.items()}
    instants = sorted({r[3] for recs in (*flows.values(), *insts.values()) for r in recs})
    rows = []
    for t in instants:
        vals: dict[str, float] = {}
        period_end = None
        for f, recs in flows.items():
            v, e = ttm(_asof(recs, t, True))
            vals[f"{f}_ttm"] = v
            if (f == "revenue" and e is not None) or (period_end is None and e is not None):
                period_end = e
        for f, recs in insts.items():
            vals[f] = _instant_asof(recs, t, sum_classes=(f == "shares"))
        rev = vals["revenue_ttm"]
        with np.errstate(divide="ignore", invalid="ignore"):
            for name, num in (("gross_margin", "gross_profit_ttm"),
                              ("operating_margin", "operating_income_ttm"),
                              ("net_margin", "net_income_ttm")):
                vals[name] = (vals[num] / rev if math.isfinite(rev) and rev > 0
                              else float("nan"))
            bv = vals["book_value"]
            vals["roe"] = (vals["net_income_ttm"] / bv if math.isfinite(bv) and bv > 0
                           else float("nan"))
        rows.append({"available": t, "period_end": period_end,
                     **{k: vals.get(k, float("nan")) for k in FIELDS}})
    if not rows:
        return pd.DataFrame(columns=["available", "period_end", *FIELDS])
    frame = pd.DataFrame(rows)
    # consecutive identical snapshots add nothing a reader can see
    keep = frame[list(FIELDS)].round(10).ne(frame[list(FIELDS)].round(10).shift()).any(axis=1)
    return frame[keep].reset_index(drop=True)


# ------------------------------------------------------------------------------- the reader ---
_CACHE: dict[str, Any] = {"key": None, "by_symbol": {}}
_NAT = np.iinfo("int64").min


def _ns(values: Any) -> np.ndarray:
    """Nanoseconds since the epoch, whatever unit the parquet stored (a pandas 2 frame round-
    trips datetimes as MICROseconds, and a bare astype('int64') would read them 1000x small)."""
    idx = pd.DatetimeIndex(pd.to_datetime(values, utc=True, errors="coerce"))
    return idx.as_unit("ns").asi8.astype("int64")


def _panel_by_symbol() -> dict[str, tuple[np.ndarray, dict[str, np.ndarray]]]:
    """{symbol: (available ns sorted, {field: values})} from PIT_PATH, cached on (path, mtime)."""
    try:
        key = (str(PIT_PATH), PIT_PATH.stat().st_mtime_ns)
    except OSError:
        return {}
    if _CACHE["key"] == key:
        return _CACHE["by_symbol"]
    try:
        frame = pd.read_parquet(PIT_PATH)
    except Exception:
        return {}
    out: dict[str, tuple[np.ndarray, dict[str, np.ndarray]]] = {}
    if len(frame) and {"symbol", "available"} <= set(frame.columns):
        frame = frame.assign(_ns=_ns(frame["available"]))
        frame = frame[frame["_ns"] != _NAT]
        for sym, g in frame.groupby("symbol", sort=False):
            g = g.sort_values("_ns", kind="stable")
            cols = {f: pd.to_numeric(g[f], errors="coerce").to_numpy("float64")
                    for f in FIELDS if f in g.columns}
            if "period_end" in g.columns:
                pe = _ns(g["period_end"])
                cols["period_end_ns"] = np.where(pe == _NAT, np.nan, pe.astype("float64"))
            out[str(sym).upper()] = (g["_ns"].to_numpy("int64"), cols)
    _CACHE["key"], _CACHE["by_symbol"] = key, out
    return out


def covered_symbols() -> list[str]:
    return sorted(_panel_by_symbol())


def bar_stamps_to_utc_ns(stamps_ns: np.ndarray) -> np.ndarray:
    """BAR stamps (the venue's New York + 7 h wall clock under a UTC label) -> true UTC ns.

    THE TWO CLOCKS MEET HERE. `available` is a TRUE UTC instant (an SEC acceptance time), while
    every stamp a family hands this module is a bar stamp from the store, three hours ahead of
    UTC while New York is on daylight time and two otherwise (US DST dates, not the EU's). Compared raw, a 10-Q accepted after the US close (16:05 ET
    = 20:05 UTC in summer) read as "known" at the 22:00 bar -- which is 19:00 UTC, an hour
    BEFORE the filing existed: an earnings reaction read with lookahead. The conversion is
    `libs.regime.session_clock.server_to_utc`, the desk's one broker-clock helper (PR #134).
    """
    arr = np.asarray(stamps_ns, dtype="int64")
    if arr.size == 0:
        return arr
    flat = arr.reshape(-1)
    got = session_clock.server_to_utc(pd.DatetimeIndex(flat, tz="UTC"))
    return np.asarray(got.as_unit("ns").asi8, dtype="int64").reshape(arr.shape)


def asof(symbol: str, stamps_ns: np.ndarray, field: str) -> np.ndarray:
    """`field` for `symbol` as known at each BAR stamp (NaN before the first availability).

    `stamps_ns` are bar stamps on the broker clock; they are converted to true UTC before they
    are compared with the true-UTC `available` column (`bar_stamps_to_utc_ns`)."""
    got = _panel_by_symbol().get(str(symbol).upper())
    out = np.full(np.asarray(stamps_ns).shape, np.nan, dtype="float64")
    if got is None or field not in got[1]:
        return out
    t, vals = got[0], got[1][field]
    j = np.searchsorted(t, bar_stamps_to_utc_ns(stamps_ns), side="right") - 1
    ok = j >= 0
    out[ok] = vals[j[ok]]
    return out


def fresh(symbol: str, stamps_ns: np.ndarray, max_age_d: float) -> np.ndarray:
    """True where the snapshot known at the stamp describes a period ending within `max_age_d`
    days of it. A company that stopped filing is ABSENT from the cross-section, never ranked on
    a year-old number carried forward."""
    pe = asof(symbol, stamps_ns, "period_end_ns")
    utc = bar_stamps_to_utc_ns(stamps_ns).astype("float64")
    with np.errstate(invalid="ignore"):
        return np.isfinite(pe) & ((utc - pe)
                                  <= float(max_age_d) * 86_400e9)


def valuation(symbol: str, stamps_ns: np.ndarray, price: np.ndarray) -> dict[str, np.ndarray]:
    """The price-derived ratios at each stamp, against `price` (the bar store's close there).

    earnings_yield = EPS_ttm / P; pe = P / EPS_ttm (NaN when EPS <= 0); book_to_price =
    book / (P x shares); pb its inverse; sales_to_ev = revenue_ttm / (P x shares + debt - cash),
    with missing debt or cash read as zero; ev_sales its inverse."""
    price = np.asarray(price, dtype="float64")
    g = {f: asof(symbol, stamps_ns, f) for f in ("eps_ttm", "book_value", "shares", "debt",
                                                 "cash", "revenue_ttm")}
    with np.errstate(divide="ignore", invalid="ignore"):
        mcap = price * g["shares"]
        ev = mcap + np.nan_to_num(g["debt"]) - np.nan_to_num(g["cash"])
        ey = np.where(price > 0, g["eps_ttm"] / price, np.nan)
        bp = np.where(mcap > 0, g["book_value"] / mcap, np.nan)
        sev = np.where(ev > 0, g["revenue_ttm"] / ev, np.nan)
        return {"earnings_yield": ey, "pe": np.where(g["eps_ttm"] > 0, price / g["eps_ttm"],
                                                     np.nan),
                "book_to_price": bp, "pb": np.where(bp > 0, 1.0 / bp, np.nan),
                "sales_to_ev": sev, "ev_sales": np.where(sev > 0, 1.0 / sev, np.nan)}


def write_table(frames: Iterable[tuple[str, pd.DataFrame]], path: Path | None = None) -> Path:
    """Write {symbol: snapshots} as one long parquet, atomically."""
    target = path or PIT_PATH
    parts = [f.assign(symbol=s) for s, f in frames if f is not None and len(f)]
    table = (pd.concat(parts, ignore_index=True) if parts
             else pd.DataFrame(columns=["symbol", "available", "period_end", *FIELDS]))
    target.parent.mkdir(parents=True, exist_ok=True)
    tmp = target.with_suffix(".tmp.parquet")
    table.to_parquet(tmp, index=False)
    tmp.replace(target)
    return target


def read_table(path: Path | None = None) -> pd.DataFrame:
    try:
        return pd.read_parquet(path or PIT_PATH)
    except Exception:
        return pd.DataFrame(columns=["symbol", "available", "period_end", *FIELDS])
