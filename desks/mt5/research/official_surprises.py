"""OFFICIAL-DATA SURPRISES -- scheduled public releases as point-in-time event states for MT5 cells.

WHAT WAS MISSING (wired ledger 2026-11-13, all state D, zero code hits on LIVE):

  N4  BoJ rinban surprise       each JGB purchase operation's offer size against the plan the BoJ
                                pre-announced for that maturity bucket, plus how much the market
                                tried to sell into it (bids / offer). Same-day state for USDJPY,
                                EURJPY, JP225.
  N6  TIC foreign-flow surprise monthly net foreign purchases of US long-term securities against
                                their own trailing 12-month median. State for USDJPY, EURUSD,
                                US500 over release day + 1 week.
  N7  USDA export-sales surprise Thursday 08:30 ET net export sales for corn, wheat and soybeans
                                against their own trailing 4-week mean. Event state for the desk's
                                CORN, WHEAT, SOYBEAN CFDs.
  N8  EIA gas-storage surprise  Thursday 10:30 ET working-gas change against the 5-year average
                                change for the same week of the year. Event state for XNGUSD.
  GAP_MAP 68  Fed net liquidity  WALCL - TGA - RRP, weekly delta, published with the H.4.1 on
                                Thursday 16:30 ET. Distinct from macro_desk's liquidity z (which
                                omits the Treasury General Account and is a daily blend, not the
                                weekly H.4.1 event).
  GAP_MAP 64  USD funding stress  SOFR - IORB (reserve scarcity), 90-day AA financial CP - 3m bill
                                (bank term funding), and a CIP-basis proxy: the broker's own
                                overnight swap-implied rate differential against the FRED 3-month
                                differential for the same pair. Distinct from row 52 (swap drift
                                is the change of the swap; this is its gap to the cash market).

HOW, end to end -- each stage leaves an artifact:

  1. ROWS, NEVER CODE. `research/official_surprises_sources.json` holds one row per release with
     its adapter, terms state, URLs, key env names, release clock and targets. A row whose terms
     are not OPEN is never fetched and is counted as a named gap with its reason.

  2. HONEST ACCESS. Every URL is checked against the host's robots.txt with our own User-Agent
     before any data request (an unreadable robots.txt is a NO); every request goes through
     `libs.data.polite_fetch` with retries off; 401/403/429/451 is a HARD STOP recorded in the
     futures-state `hard_stops` and never retried until released. A key is read from the
     environment by NAME and never written, printed or logged; a missing key is NEEDS_KEY.

  3. CATALOGUE BEFORE IDS. A series id or commodity code is used only after the source's own
     catalogue returned it (EIA route metadata, the FAS commodity list, the TIC file index). The
     catalogue read is saved under raw/ as the evidence; an id the catalogue does not carry makes
     the row UNMEASURED with the ids it did carry, never a guessed fetch.

  4. POINT IN TIME. Every frame carries `available_time` = the release instant in its own time
     zone plus a short grace, converted to UTC. Holiday weeks move a release LATER, never earlier
     (late stamping is safe; early is lookahead). Rows can carry an exact `calendar.releases`
     map and `calendar.windows` not-before dates (government shutdowns), like the CFTC calendar.
     The TIC release day is not in its file, so it is stamped at a conservative upper bound until
     the release-calendar leg supplies exact dates; that basis is written on every row.

  5. FEATURES. Few columns on purpose: every column mints cells and every cell is charged to the
     program's family-wise budget. Each event series carries `surprise` (actual minus its stated
     baseline) and `surprise_z` (against strictly EARLIER surprises only); state series add one
     level column. Event rows also land in `data/calendar_backfill/` so the event-reaction lane
     sees each release instant.

  6. CELLS. `collect()` returns (oid, frame, meta) to `futures_state.build_market_series`, which
     writes `data/lake/series/<oid>.parquet` and mints each (column x transform x target x chart)
     ONCE as an `exogenous_conditioner` candidate. The hourly `futures_state` leg is the clock.

    python desks/mt5/research/futures_state.py --once --dry-run   # this module runs inside it
    python desks/mt5/research/futures_state.py --once --offline   # features from held raw only
"""
from __future__ import annotations

import gzip
import io
import json
import os
import re
import sys
import time
import urllib.parse
from collections.abc import Callable, Mapping, Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

_DESK = Path(__file__).resolve().parents[1]
if str(_DESK) not in sys.path:
    sys.path.insert(0, str(_DESK))

from research import futures_state as fs  # noqa: E402

REGISTRY = _DESK / "research" / "official_surprises_sources.json"
RAW = fs.RAW / "official"
REPORT = _DESK / "reports" / "OFFICIAL_SURPRISES.json"
UA = "quant-research/1.0 (+https://github.com/kingdemond434-cpu/quant; official_surprises)"
LEG = "official_surprises"
MIN_EVENTS = 30
GRACE = pd.Timedelta(minutes=5)

Text = Callable[[str], str]


# ------------------------------------------------------------------------------ honest access

class Access:
    """One pass's network door: robots first, then a polite GET with our own UA, no retry.

    `text` is injected so tests (and `--offline`) never touch the network. Robots verdicts are
    cached per host for the pass; a refused host is never asked again this pass."""

    def __init__(self, text: Callable[[str, Mapping[str, str]], str] | None,
                 state: dict[str, Any], notes: list[dict[str, Any]],
                 deadline: float | None = None):
        self._text = text
        self.state = state
        self.notes = notes
        self.deadline = deadline
        self._robots: dict[str, Any] = {}

    @property
    def online(self) -> bool:
        return self._text is not None

    def _stopped(self, sid: str) -> bool:
        return sid in (self.state.get("hard_stops") or {})

    def allowed(self, url: str) -> bool:
        import urllib.robotparser
        p = urllib.parse.urlsplit(url)
        host = f"{p.scheme}://{p.netloc}"
        if host not in self._robots:
            rp = urllib.robotparser.RobotFileParser()
            try:
                assert self._text is not None
                rp.parse(self._text(f"{host}/robots.txt", {}).splitlines())
                self._robots[host] = rp
            except fs.FetchError as exc:
                # RFC 9309: a 4xx robots.txt (other than the hard stops) means no rules
                self._robots[host] = (exc.code is not None and 400 <= int(exc.code) < 500)
            except fs.HardStop:
                self._robots[host] = False
            except Exception:
                self._robots[host] = False
        v = self._robots[host]
        return v.can_fetch(UA, url) if hasattr(v, "can_fetch") else bool(v)

    def get(self, sid: str, url: str, headers: Mapping[str, str] | None = None) -> str | None:
        """The body, or None with the reason in notes. Never raises for a refusal."""
        if self._text is None or self._stopped(sid):
            return None
        if self.deadline is not None and time.monotonic() > self.deadline:
            self.notes.append({"source": sid, "status": "DEFERRED", "why": "fetch budget spent"})
            return None
        if not self.allowed(url):
            self.notes.append({"source": sid, "status": "UNMEASURED", "why": "robots disallows",
                               "url": _redact(url)})
            return None
        try:
            return self._text(url, headers or {})
        except fs.HardStop as hs:
            self.state.setdefault("hard_stops", {})[sid] = {"code": hs.code, "at": fs._now()}
            self.notes.append({"source": sid, "status": "HARD_STOP", "code": hs.code})
        except Exception as exc:
            self.notes.append({"source": sid, "error": type(exc).__name__,
                               "url": _redact(url)})
        return None

    def json(self, sid: str, url: str, headers: Mapping[str, str] | None = None) -> Any:
        body = self.get(sid, url, headers)
        if body is None:
            return None
        try:
            return json.loads(body)
        except ValueError:
            self.notes.append({"source": sid, "error": "not JSON", "url": _redact(url)})
            return None


def _redact(url: str) -> str:
    """A URL with every key-like query value replaced, so no note ever carries a key."""
    p = urllib.parse.urlsplit(url)
    q = [(k, "***" if re.search(r"key|token", k, re.I) else v)
         for k, v in urllib.parse.parse_qsl(p.query, keep_blank_values=True)]
    return urllib.parse.urlunsplit((p.scheme, p.netloc, p.path, urllib.parse.urlencode(q), ""))


def polite_text(url: str, headers: Mapping[str, str]) -> str:
    from libs.data import polite_fetch
    r = polite_fetch.get(url, headers={"User-Agent": UA, "Accept": "*/*", **headers},
                         timeout=40.0, retries=0, leg=LEG)
    if r.status in fs.HARD_STOP:
        raise fs.HardStop(int(r.status or 0), url)
    if not r.ok:
        raise fs.FetchError(r.status, url, r.error or f"HTTP {r.status}")
    return r.text


def key_for(row: Mapping[str, Any]) -> str:
    """The first set env var named by the row. The VALUE never leaves this function's caller."""
    return next((os.environ[k] for k in row.get("key_env") or [] if os.environ.get(k)), "")


# ------------------------------------------------------------------------------ release clocks

def _holidays() -> frozenset[pd.Timestamp]:
    return fs._us_holidays()


def release_instant(days: pd.Series, at: str, tz: str,
                    calendar: Mapping[str, Any] | None = None,
                    holiday_shift: bool = True) -> pd.Series:
    """Scheduled release DAYS -> UTC instants at the local clock time plus grace.

    A release scheduled on a US federal holiday, or in a week where a holiday fell earlier the
    same week, moves one business day LATER (EIA, USDA and the H.4.1 all slip that way; when the
    agency actually published earlier the stamp is merely late, which is safe). Exact dates in
    `calendar.releases` (scheduled day ISO -> real day ISO) win; `calendar.windows` raise a
    not-before date for every scheduled day inside a shutdown window."""
    cal = calendar or {}
    hol = _holidays()
    hh, mm = (int(x) for x in str(at).split(":"))
    out: list[pd.Timestamp] = []
    for d in pd.to_datetime(days, errors="coerce"):
        if pd.isna(d):
            out.append(pd.NaT)
            continue
        day = pd.Timestamp(d).tz_localize(None).normalize()
        exact = (cal.get("releases") or {}).get(day.date().isoformat())
        if exact:
            day = pd.Timestamp(exact).normalize()
        elif holiday_shift:
            week0 = day - pd.Timedelta(days=day.weekday())
            if any(week0 <= h <= day for h in hol):
                day = day + pd.Timedelta(days=1)
                while day.weekday() >= 5 or day in hol:
                    day += pd.Timedelta(days=1)
        for w in cal.get("windows") or []:
            if pd.Timestamp(w["from"]) <= day <= pd.Timestamp(w["to"]):
                day = max(day, pd.Timestamp(w["not_before"]).normalize())
        local = (day + pd.Timedelta(hours=hh, minutes=mm)).tz_localize(
            tz, nonexistent="shift_forward", ambiguous=False)
        out.append(local.tz_convert("UTC") + GRACE)
    return pd.Series(pd.to_datetime(out, utc=True), index=getattr(days, "index", None))


# ------------------------------------------------------------------------------ features (pure)

def surprise_frame(actual: pd.Series, baseline: pd.Series, window: int = 52) -> pd.DataFrame:
    """[surprise, surprise_z] per event. z uses strictly EARLIER surprises (shifted), so an event
    never scores against itself; under MIN_EVENTS // 2 prior events z is NaN, never a guess."""
    a = pd.to_numeric(actual, errors="coerce").reset_index(drop=True)
    b = pd.to_numeric(baseline, errors="coerce").reset_index(drop=True)
    s = a - b
    past = s.shift(1)
    mu = past.rolling(window, min_periods=MIN_EVENTS // 2).mean()
    sd = past.rolling(window, min_periods=MIN_EVENTS // 2).std(ddof=0)
    return pd.DataFrame({"surprise": s, "surprise_z": (s - mu) / sd.replace(0.0, np.nan)})


def trailing_mean(x: pd.Series, n: int) -> pd.Series:
    """Mean of the n PRIOR values (the release's own value excluded)."""
    return pd.to_numeric(x, errors="coerce").shift(1).rolling(n, min_periods=n).mean()


def trailing_median(x: pd.Series, n: int) -> pd.Series:
    return pd.to_numeric(x, errors="coerce").shift(1).rolling(n, min_periods=n).median()


def same_week_5y_mean(week_end: pd.Series, change: pd.Series, years: int = 5,
                      tol_days: int = 3) -> pd.Series:
    """EIA's own construction: for each report week, the mean change over the same calendar week
    of the PRIOR `years` years (the week whose end is within `tol_days` of the same day-of-year).
    Needs all `years` years present, else NaN -- a partial average is a different baseline."""
    we = pd.to_datetime(week_end).reset_index(drop=True)
    ch = pd.to_numeric(change, errors="coerce").reset_index(drop=True)
    by_day = dict(zip(we, ch, strict=False))
    keys = np.array(list(by_day.keys()), dtype="datetime64[ns]")
    out = []
    for d in we:
        vals = []
        for k in range(1, years + 1):
            try:
                tgt = d.replace(year=d.year - k)
            except ValueError:          # 29 Feb
                tgt = d.replace(year=d.year - k, day=28)
            gap = np.abs((keys - np.datetime64(tgt)).astype("timedelta64[D]").astype(int))
            j = int(gap.argmin()) if len(gap) else -1
            if j >= 0 and gap[j] <= tol_days:
                v = by_day[pd.Timestamp(keys[j])]
                if pd.notna(v):
                    vals.append(float(v))
        out.append(float(np.mean(vals)) if len(vals) == years else np.nan)
    return pd.Series(out)


def windowed_state(feat: pd.DataFrame, avail: pd.Series, event: pd.Series, col: str,
                   days: int) -> tuple[pd.DataFrame, pd.Series, pd.Series]:
    """Add `<col>_wk`: the event's value from its release for `days` days, then 0.

    The conditioner carries a value forward until the next row, so a state that should hold for
    "release day + 1 week" needs an explicit end: a row at release + days whose `_wk` value is
    0 (below any threshold) and whose other columns are NaN (dropped by the conditioner, so they
    keep carrying the release's value). Ends that would land after the next release are skipped.
    """
    f = feat.reset_index(drop=True).copy()
    a = pd.to_datetime(avail, utc=True).reset_index(drop=True)
    e = pd.to_datetime(event).reset_index(drop=True)
    f[f"{col}_wk"] = f[col]
    ends = a + pd.Timedelta(days=days)
    nxt = a.shift(-1)
    keep = nxt.isna() | (ends < nxt)
    tail = pd.DataFrame({c: np.nan for c in f.columns}, index=range(int(keep.sum())))
    tail[f"{col}_wk"] = 0.0
    f2 = pd.concat([f, tail], ignore_index=True)
    a2 = pd.concat([a, ends[keep]], ignore_index=True)
    e2 = pd.concat([e, e[keep]], ignore_index=True)
    order = np.argsort(a2.to_numpy(), kind="stable")
    return (f2.iloc[order].reset_index(drop=True), a2.iloc[order].reset_index(drop=True),
            e2.iloc[order].reset_index(drop=True))


# ------------------------------------------------------------------------------ calendar rows

def write_calendar(oid: str, row: Mapping[str, Any], instants: pd.Series, basis: str
                   ) -> Path | None:
    """Release instants for the event-reaction lane (outside data/intelligence on purpose: the
    candidate compiler would mint a cell per historical row there)."""
    t = pd.to_datetime(instants, utc=True).dropna()
    if t.empty:
        return None
    lines = [json.dumps({"event_date": (x - GRACE).isoformat(),
                         "currency": str(row.get("currency") or "USD"),
                         "country": str(row.get("country") or "USD"),
                         "title": str(row.get("title") or oid), "impact": "High",
                         "series": oid, "source": "official_surprises",
                         "instant_basis": basis, "backfill": True}, sort_keys=True)
             for x in t]
    fs.CALENDAR_BACKFILL.mkdir(parents=True, exist_ok=True)
    p = fs.CALENDAR_BACKFILL / f"backfill_{oid}.jsonl.gz"
    tmp = p.with_suffix(p.suffix + ".tmp")
    with gzip.open(tmp, "wt", encoding="utf-8") as fh:
        fh.write("\n".join(lines) + "\n")
    fs._replace(tmp, p)
    return p


def _hold(raw: Path, df: pd.DataFrame | None) -> pd.DataFrame:
    """Persist a fresh read; otherwise serve the last held read (the offline path)."""
    if df is not None and not df.empty:
        RAW.mkdir(parents=True, exist_ok=True)
        fs._atomic_parquet(raw, df, index=False)
        return df
    if raw.exists():
        return pd.read_parquet(raw)
    return pd.DataFrame()


def _evidence(name: str, doc: Any) -> None:
    RAW.mkdir(parents=True, exist_ok=True)
    fs._write(RAW / f"catalogue_{name}.json", {"read_utc": fs._now(), "doc": doc})


Out = tuple[str, pd.DataFrame, dict[str, Any]]


def _emit(oid: str, row: Mapping[str, Any], feat: pd.DataFrame, avail: pd.Series,
          event: pd.Series, kind: str, basis: str, extra: Mapping[str, Any] | None = None
          ) -> Out | None:
    ok = avail.notna().to_numpy() & feat.notna().any(axis=1).to_numpy()
    feat, avail, event = (feat[ok].reset_index(drop=True), avail[ok].reset_index(drop=True),
                          event[ok].reset_index(drop=True))
    if len(feat) < MIN_EVENTS:
        return None
    frame = fs.stamped(feat, avail, oid, event)
    if row.get("event_lane", True):
        try:
            first = ~pd.Series(pd.to_datetime(event)).duplicated(keep="first").to_numpy()
            write_calendar(oid, row, avail[first], basis)
        except OSError:
            pass
    meta = {"targets": list(row.get("targets") or []), "kind": kind, "rows": len(frame),
            "last_event": str(pd.to_datetime(event).max()), "why": str(row.get("why") or ""),
            "idea": row.get("idea"), "instant_basis": basis, **(extra or {})}
    return oid, frame, meta


# ------------------------------------------------------------------------------ FRED (N/L, funding)

def fred_series(acc: Access, row: Mapping[str, Any], sid: str, key: str) -> pd.Series:
    q = urllib.parse.urlencode({"series_id": sid, "api_key": key, "file_type": "json"})
    doc = acc.json(str(row["id"]), f"https://api.stlouisfed.org/fred/series/observations?{q}")
    rows = (doc or {}).get("observations") or []
    if not rows:
        return pd.Series(dtype=float)
    d = pd.DataFrame(rows)
    return pd.Series(pd.to_numeric(d["value"], errors="coerce").to_numpy(),
                     index=pd.to_datetime(d["date"])).dropna()


def _fred_frame(acc: Access, row: Mapping[str, Any]) -> pd.DataFrame:
    """All of the row's FRED series as columns (held raw if offline / refused)."""
    raw = RAW / f"{row['id']}.parquet"
    key = key_for(row)
    fresh = None
    if acc.online and key:
        cols = {s: fred_series(acc, row, s, key) for s in row["series"]}
        if all(len(v) for v in cols.values()):
            fresh = pd.DataFrame(cols).sort_index().rename_axis("date").reset_index()
    elif acc.online and not key:
        acc.notes.append({"source": row["id"], "status": "NEEDS_KEY",
                          "key_env": row.get("key_env")})
    return _hold(raw, fresh)


def net_liquidity(df: pd.DataFrame, units: Mapping[str, float]) -> pd.DataFrame:
    """Weekly Wednesday frame: net = WALCL - TGA - RRP in $bn, with its 1w and 4w changes.

    WALCL and WTREGEN are Wednesday levels; RRP (daily) is taken AS OF that Wednesday. Units come
    from the row (WALCL is published in $mn, WTREGEN and RRPONTSYD in $bn) so no constant here
    decides them."""
    d = df.set_index(pd.to_datetime(df["date"])).drop(columns=["date"]).sort_index()
    weds = d.index[d.index.weekday == 2]
    w = d.loc[weds, ["WALCL", "WTREGEN"]].dropna()
    rrp = d["RRPONTSYD"].dropna()
    # RRP before its daily series began is genuinely zero-usage history only if FRED says so;
    # otherwise the week is dropped rather than imputed.
    w["RRPONTSYD"] = rrp.reindex(w.index, method="ffill", tolerance=pd.Timedelta(days=6))
    w = w.dropna()
    net = (w["WALCL"] * units.get("WALCL", 1.0) - w["WTREGEN"] * units.get("WTREGEN", 1.0)
           - w["RRPONTSYD"] * units.get("RRPONTSYD", 1.0))
    out = pd.DataFrame({"week": w.index, "net_liq_bn": net.to_numpy()})
    out["d1w"] = out["net_liq_bn"].diff()
    out["d4w"] = out["net_liq_bn"].diff(4)
    return out


def collect_net_liquidity(acc: Access, row: Mapping[str, Any]) -> list[Out]:
    df = _fred_frame(acc, row)
    if df.empty or not set(row["series"]) <= set(df.columns):
        return []
    w = net_liquidity(df, row.get("units") or {})
    # weekly gaps (a skipped Wednesday) make d1w a 2-week change: NaN it
    gap = pd.to_datetime(w["week"]).diff()
    w.loc[gap > pd.Timedelta(days=8), "d1w"] = np.nan
    sz = surprise_frame(w["d1w"], pd.Series(0.0, index=w.index), int(row.get("window", 52)))
    feat = pd.DataFrame({"net_liq_bn": w["net_liq_bn"], "d1w": w["d1w"], "d4w": w["d4w"],
                         "d1w_z": sz["surprise_z"]})
    rel_day = pd.to_datetime(w["week"]) + pd.Timedelta(days=1)          # H.4.1: Thursday
    avail = release_instant(rel_day, str(row.get("at") or "16:30"), str(row["tz"]),
                            row.get("calendar"))
    out = _emit(f"os_{row['id']}", row, feat, avail, pd.Series(pd.to_datetime(w["week"])),
                "fed_net_liquidity", "h41_thursday_1630_et_holiday_late")
    return [out] if out else []


def collect_funding(acc: Access, row: Mapping[str, Any]) -> list[Out]:
    """Daily funding spreads, each stamped the next business day 23:00 UTC (FRED's daily rule)."""
    df = _fred_frame(acc, row)
    if df.empty:
        return []
    d = df.set_index(pd.to_datetime(df["date"])).drop(columns=["date"]).sort_index()
    outs: list[Out] = []
    for sp in row.get("spreads") or []:
        a, b = str(sp["a"]), sp["b"]
        bs = [b] if isinstance(b, str) else list(b)       # first available of a chain (IORB->IOER)
        if a not in d.columns or not any(x in d.columns for x in bs):
            continue
        base = d[[x for x in bs if x in d.columns]].bfill(axis=1).iloc[:, 0]
        both = pd.DataFrame({"a": d[a], "b": base}).dropna()
        if len(both) < fs.MIN_ROWS:
            continue
        s = (both["a"] - both["b"]) * 100.0                   # basis points
        feat = fs.dynamics(pd.DataFrame({"bp": s.to_numpy()}), ["bp"],
                           window=int(row.get("window", 252)))
        feat = feat[["bp", "bp_chg", "bp_pct"]]
        avail = fs.daily_available(pd.Series(both.index))
        out = _emit(f"os_{row['id']}_{sp['id']}", {**row, "event_lane": False,
                                                  "targets": sp.get("targets") or row["targets"]},
                    feat, avail, pd.Series(both.index), "usd_funding_spread",
                    "fred_daily_next_bday_2300utc")
        if out:
            outs.append(out)
    return outs


# ------------------------------------------------------------------------------ CIP basis proxy

def swap_implied_diff(swap_points: float, price: float, digits: int, side: str) -> float:
    """Annualised % rate differential implied by an MT5 swap in POINTS per lot per night.

    A points swap is (forward - spot) per night in the quote's smallest unit, so the implied
    base-minus-quote differential is points * 10**-digits / price * 365 * 100, sign by side
    (long earns base, pays quote). A broker's markup sits inside the swap on both sides, so the
    MID of long and short (computed by the caller) is the differential and half their spread is
    the broker's take."""
    v = swap_points * (10.0 ** -digits) / price * 365.0 * 100.0
    return v if side == "long" else -v


def collect_cip(acc: Access, row: Mapping[str, Any], frames: Mapping[str, pd.DataFrame],
                swaps: pd.DataFrame | None) -> list[Out]:
    """broker swap-implied differential minus the FRED 3m cash differential, per pair.

    `swaps` is the hourly broker swap panel (columns: time, symbol, swap_long, swap_short,
    swap_mode, price, digits); only swap_mode == points rows are used, since other modes need
    contract units the panel does not carry. The cash leg is futures_state's `fred_rdiff3m_<pair>`
    frame, joined AS OF the swap observation's day."""
    if swaps is None or swaps.empty:
        acc.notes.append({"source": row["id"], "status": "UNMEASURED",
                          "why": "no broker swap panel held"})
        return []
    outs: list[Out] = []
    for pr in row.get("pairs") or []:
        sym = str(pr["symbol"])
        cash = frames.get(str(pr.get("cash") or f"fred_rdiff3m_{sym.lower()}"))
        sw = swaps[(swaps["symbol"] == sym)]
        if "swap_mode" in sw.columns:
            sw = sw[sw["swap_mode"].astype(str).str.lower().isin(("points", "1", "by_points"))]
        if cash is None or sw.empty or "diff" not in cash.columns:
            acc.notes.append({"source": f"{row['id']}_{sym}", "status": "UNMEASURED",
                              "why": "cash differential or points-mode swaps missing"})
            continue
        sw = sw.dropna(subset=["swap_long", "swap_short", "price", "digits"]).copy()
        sw["t"] = pd.to_datetime(sw["time"], utc=True)
        sw = sw.set_index("t").sort_index()
        day = sw.resample("1D").last().dropna(subset=["price"])
        lng = [swap_implied_diff(r.swap_long, r.price, int(r.digits), "long")
               for r in day.itertuples()]
        sht = [swap_implied_diff(r.swap_short, r.price, int(r.digits), "short")
               for r in day.itertuples()]
        implied = pd.Series((np.array(lng) + np.array(sht)) / 2.0, index=day.index)
        take = pd.Series((np.array(sht) - np.array(lng)) / 2.0, index=day.index)
        c = pd.Series(pd.to_numeric(cash["diff"], errors="coerce").to_numpy(),
                      index=pd.to_datetime(cash["available_time"], utc=True)).sort_index()
        c = c[~c.index.duplicated(keep="last")]
        cash_asof = c.reindex(implied.index.union(c.index)).ffill().reindex(implied.index)
        basis = (implied - cash_asof).dropna()
        if len(basis) < fs.MIN_ROWS:
            acc.notes.append({"source": f"{row['id']}_{sym}", "status": "ACCRUING",
                              "rows": int(len(basis)), "need": fs.MIN_ROWS})
            continue
        feat = pd.DataFrame({"basis_pct": basis.to_numpy(),
                             "broker_take_pct": take.reindex(basis.index).to_numpy()})
        feat["basis_chg"] = feat["basis_pct"].diff()
        # the swap is observed at the panel's hour; usable the next hour, stamped end of day
        avail = pd.Series(basis.index + pd.Timedelta(hours=23, minutes=59))
        out = _emit(f"os_{row['id']}_{sym.lower()}",
                    {**row, "event_lane": False, "targets": pr.get("targets") or [sym]},
                    feat, avail, pd.Series(basis.index), "cip_basis_proxy",
                    "broker_swap_panel_day_end")
        if out:
            outs.append(out)
    return outs


def load_swap_panel(panel_dir: Path | None = None, terms_dir: Path | None = None,
                    bars_dir: Path | None = None) -> pd.DataFrame:
    """The broker's hourly swap panel joined with its UNITS and a price, one row per capture.

    Swaps come from carry_state's own store (data/intelligence/broker_swaps/: hourly JSON lists
    and the daily jsonl.gz roll-ups), swap_mode and digits from the tape's contract terms, price
    from the symbol's own H1 close on the capture day. A symbol with no contract terms has no
    swap_mode and is left out: the unit of its swap is unknown (carry_state's rule)."""
    from research import carry_state as cs
    pdir = panel_dir or cs._PANEL
    terms = cs._load_terms(terms_dir or cs._TERMS)
    rows: list[dict[str, Any]] = []

    def _take(r: Any) -> None:
        if not isinstance(r, dict) or r.get("kind") != "swap_table" or not r.get("symbols"):
            return
        if r.get("swap_long") is None or r.get("swap_short") is None:
            return
        rows.append({"time": r.get("found_at"), "symbol": str(r["symbols"][0]),
                     "swap_long": float(r["swap_long"]), "swap_short": float(r["swap_short"])})

    for f in sorted(pdir.glob("*.json")) if pdir.exists() else []:
        try:
            doc = json.loads(f.read_text("utf-8"))
        except (OSError, ValueError):
            continue
        for r in doc if isinstance(doc, list) else []:
            _take(r)
    for f in sorted(pdir.glob("*.jsonl.gz")) if pdir.exists() else []:
        try:
            with gzip.open(f, "rt", encoding="utf-8") as fh:
                for ln in fh:
                    try:
                        _take(json.loads(ln))
                    except ValueError:
                        continue
        except OSError:
            continue
    if not rows:
        return pd.DataFrame()
    df = pd.DataFrame(rows)
    df["swap_mode"] = df["symbol"].map(lambda s: (terms.get(s) or {}).get("swap_mode"))
    df["digits"] = df["symbol"].map(lambda s: (terms.get(s) or {}).get("digits"))
    df = df.dropna(subset=["swap_mode", "digits"])
    df["swap_mode"] = df["swap_mode"].map(
        lambda m: "points" if int(m) == cs.SWAP_MODE_POINTS else str(int(m)))
    bdir = bars_dir or cs._UNIVERSE
    px: list[float] = []
    closes: dict[str, pd.Series] = {}
    for r in df.itertuples():
        if r.symbol not in closes:
            closes[r.symbol] = _daily_close(bdir / f"{r.symbol}_H1.parquet")
        c = closes[r.symbol]
        t = pd.Timestamp(r.time).tz_convert("UTC") if pd.Timestamp(r.time).tzinfo else \
            pd.Timestamp(r.time).tz_localize("UTC")
        v = c[c.index <= t].iloc[-1] if len(c) and (c.index <= t).any() else np.nan
        px.append(float(v))
    df["price"] = px
    return df


def _daily_close(p: Path) -> pd.Series:
    try:
        b = pd.read_parquet(p)
    except Exception:
        return pd.Series(dtype=float)
    if "time" in b.columns:
        b = b.set_index(pd.to_datetime(b["time"], utc=True))
    idx = pd.to_datetime(b.index, utc=True)
    return pd.Series(pd.to_numeric(b["close"], errors="coerce").to_numpy(), index=idx).dropna()


# ------------------------------------------------------------------------------ EIA storage (N8)

def eia_storage_frame(rows: Sequence[Mapping[str, Any]]) -> pd.DataFrame:
    d = pd.DataFrame(list(rows))
    if d.empty or "period" not in d.columns:
        return pd.DataFrame()
    return (pd.DataFrame({"week_end": pd.to_datetime(d["period"]),
                          "stock_bcf": pd.to_numeric(d["value"], errors="coerce")})
            .dropna().sort_values("week_end").drop_duplicates("week_end", keep="last")
            .reset_index(drop=True))


def collect_eia_storage(acc: Access, row: Mapping[str, Any]) -> list[Out]:
    """Working gas in storage, Lower 48. The route's own metadata is read first and the series id
    must appear in it; the weekly change is then compared with the 5-year same-week mean."""
    raw = RAW / f"{row['id']}.parquet"
    key = key_for(row)
    fresh = None
    if acc.online and key:
        meta = acc.json(row["id"], f"https://api.eia.gov/v2/{row['route']}/facet/series?"
                        + urllib.parse.urlencode({"api_key": key}))
        facets = [str(f.get("id")) for f in ((meta or {}).get("response") or {})
                  .get("facets") or []]
        if meta is not None:
            _evidence(str(row["id"]), {"route": row["route"], "series_ids": facets[:500]})
        if facets and row["series"] not in facets:
            acc.notes.append({"source": row["id"], "status": "UNMEASURED",
                              "why": "series id not in the route's catalogue",
                              "catalogue_sample": facets[:20]})
        elif facets:
            q = urllib.parse.urlencode({"api_key": key, "frequency": "weekly",
                                        "data[0]": "value", "facets[series][]": row["series"],
                                        "sort[0][column]": "period",
                                        "sort[0][direction]": "asc", "length": "5000"})
            doc = acc.json(row["id"], f"https://api.eia.gov/v2/{row['route']}/data/?{q}")
            fresh = eia_storage_frame(((doc or {}).get("response") or {}).get("data") or [])
    elif acc.online:
        acc.notes.append({"source": row["id"], "status": "NEEDS_KEY",
                          "key_env": row.get("key_env")})
    df = _hold(raw, fresh)
    if df.empty:
        return []
    df["week_end"] = pd.to_datetime(df["week_end"])
    df["chg_bcf"] = df["stock_bcf"].diff()
    df.loc[df["week_end"].diff() > pd.Timedelta(days=8), "chg_bcf"] = np.nan
    base = same_week_5y_mean(df["week_end"], df["chg_bcf"])
    sz = surprise_frame(df["chg_bcf"], base, int(row.get("window", 52)))
    feat = pd.DataFrame({"surprise": sz["surprise"], "surprise_z": sz["surprise_z"]})
    rel_day = df["week_end"] + pd.Timedelta(days=6)                    # Fri week end -> Thursday
    avail = release_instant(rel_day, str(row.get("at") or "10:30"), str(row["tz"]),
                            row.get("calendar"))
    out = _emit(f"os_{row['id']}", row, feat, avail, df["week_end"], "eia_storage_surprise",
                "wngsr_thursday_1030_et_holiday_late")
    return [out] if out else []


# ------------------------------------------------------------------------------ USDA export sales (N7)

def fas_week_totals(rows: Sequence[Mapping[str, Any]], field: str) -> pd.DataFrame:
    """Country rows -> one total per week ending (net sales summed over destinations)."""
    d = pd.DataFrame(list(rows))
    if d.empty or "weekEndingDate" not in d.columns or field not in d.columns:
        return pd.DataFrame(columns=["week_end", "net_sales"])
    d["week_end"] = pd.to_datetime(d["weekEndingDate"], errors="coerce").dt.tz_localize(None)
    d["v"] = pd.to_numeric(d[field], errors="coerce")
    g = d.dropna(subset=["week_end"]).groupby("week_end", as_index=False)["v"].sum(min_count=1)
    return g.rename(columns={"v": "net_sales"}).sort_values("week_end").reset_index(drop=True)


def collect_usda_esr(acc: Access, row: Mapping[str, Any], now: datetime) -> list[Out]:
    """FAS Export Sales Reporting API. The commodity CODE comes from the API's own commodity list,
    matched by the row's name pattern, never typed in; the API needs a data.gov key in the
    `API_KEY` header (named by the row's key_env)."""
    key = key_for(row)
    outs: list[Out] = []
    if acc.online and not key:
        acc.notes.append({"source": row["id"], "status": "NEEDS_KEY",
                          "key_env": row.get("key_env")})
    hdr = {"API_KEY": key} if key else {}
    base = str(row["api_base"]).rstrip("/")
    codes: dict[str, str] = {}
    if acc.online and key:
        cat = acc.json(row["id"], f"{base}/esr/commodities", hdr) or []
        if cat:
            _evidence(str(row["id"]), cat)
        for c in row.get("commodities") or []:
            pat = re.compile(str(c["name_pattern"]), re.I)
            hit = [x for x in cat if pat.search(str(x.get("commodityName") or ""))]
            if len(hit) == 1:
                codes[str(c["id"])] = str(hit[0].get("commodityCode"))
            elif cat:
                acc.notes.append({"source": f"{row['id']}_{c['id']}", "status": "UNMEASURED",
                                  "why": f"commodity list matched {len(hit)} names",
                                  "names": [x.get("commodityName") for x in hit][:8]})
    for c in row.get("commodities") or []:
        cid = str(c["id"])
        raw = RAW / f"{row['id']}_{cid}.parquet"
        fresh = None
        if cid in codes:
            held = pd.read_parquet(raw) if raw.exists() else pd.DataFrame()
            first = int(row.get("first_market_year", 2010))
            have = set()
            if not held.empty and "market_year" in held.columns:
                have = set(held["market_year"].astype(int))
            parts = [held] if not held.empty else []
            # market years already held are immutable except the two most recent
            for my in range(first, now.year + 2):
                if my in have and my < now.year:
                    continue
                url = f"{base}/esr/exports/commodityCode/{codes[cid]}/allCountries/marketYear/{my}"
                rows = acc.json(f"{row['id']}_{cid}", url, hdr)
                if rows is None:
                    break
                t = fas_week_totals(rows, str(row.get("field") or "currentMYNetSales"))
                t["market_year"] = my
                parts = [p[p["market_year"] != my] if "market_year" in p.columns else p
                         for p in parts] + [t]
            if parts:
                fresh = pd.concat(parts, ignore_index=True)
        df = _hold(raw, fresh)
        if df.empty:
            continue
        # one row per week: across a market-year boundary the old and new year both report the
        # same week; the total of both is the week's net sales
        w = (df.groupby("week_end", as_index=False)["net_sales"].sum(min_count=1)
             .sort_values("week_end").reset_index(drop=True))
        w["week_end"] = pd.to_datetime(w["week_end"])
        base_m = trailing_mean(w["net_sales"], int(row.get("baseline_weeks", 4)))
        sz = surprise_frame(w["net_sales"], base_m, int(row.get("window", 52)))
        rel_day = w["week_end"] + pd.Timedelta(days=7)               # Thu week end -> next Thu
        avail = release_instant(rel_day, str(row.get("at") or "08:30"), str(row["tz"]),
                                row.get("calendar"))
        out = _emit(f"os_{row['id']}_{cid}", {**row, "targets": c.get("targets") or [],
                                              "title": f"USDA export sales {cid}"},
                    sz, avail, w["week_end"], "usda_export_sales_surprise",
                    "fas_esr_thursday_0830_et_holiday_late")
        if out:
            outs.append(out)
    return outs


# ------------------------------------------------------------------------------ TIC (N6)

_MONTH = r"(?P<y>(?:19|20)\d\d)[-/ ]?(?P<m>0?[1-9]|1[0-2])\b"


def tic_parse(text: str, column_pattern: str) -> pd.DataFrame:
    """A TIC monthly table -> [month, value]. The column is found by its HEADER text (the row's
    pattern), never by position, and a file whose header lacks it yields nothing."""
    lines = [ln for ln in text.splitlines() if ln.strip()]
    sep = "," if sum(ln.count(",") for ln in lines[:40]) > sum(ln.count("\t") for ln in lines[:40]) \
        else "\t"
    pat = re.compile(column_pattern, re.I)
    col = None
    hdr_i = None
    for i, ln in enumerate(lines[:80]):
        cells = [c.strip().strip('"') for c in ln.split(sep)]
        hits = [j for j, c in enumerate(cells) if pat.search(c)]
        if hits:
            col, hdr_i = hits[0], i
            break
    if col is None or hdr_i is None:
        return pd.DataFrame(columns=["month", "value"])
    out = []
    for ln in lines[hdr_i + 1:]:
        cells = [c.strip().strip('"') for c in ln.split(sep)]
        m = re.match(_MONTH, cells[0]) if cells else None
        if not m or len(cells) <= col:
            continue
        v = pd.to_numeric(cells[col].replace(",", ""), errors="coerce")
        out.append((pd.Timestamp(int(m["y"]), int(m["m"]), 1), v))
    d = pd.DataFrame(out, columns=["month", "value"]).dropna()
    return d.drop_duplicates("month", keep="first").sort_values("month").reset_index(drop=True)


def tic_find_file(index_html: str, link_pattern: str, base_url: str) -> str | None:
    """The data file's URL from the TIC index page, matched by its LINK TEXT or href."""
    pat = re.compile(link_pattern, re.I)
    for href, label in re.findall(r'<a[^>]+href="([^"]+)"[^>]*>(.*?)</a>', index_html,
                                  re.I | re.S):
        lab = re.sub(r"<[^>]+>", " ", label)
        if pat.search(lab) or pat.search(href):
            return urllib.parse.urljoin(base_url, href)
    return None


def collect_tic(acc: Access, row: Mapping[str, Any]) -> list[Out]:
    raw = RAW / f"{row['id']}.parquet"
    fresh = None
    if acc.online:
        idx = acc.get(row["id"], str(row["index_url"]))
        url = tic_find_file(idx or "", str(row["link_pattern"]), str(row["index_url"]))
        if idx is not None:
            _evidence(str(row["id"]), {"index_url": row["index_url"], "found": url})
        if idx is not None and url is None:
            acc.notes.append({"source": row["id"], "status": "UNMEASURED",
                              "why": "TIC index carries no link matching the row's pattern"})
        if url:
            body = acc.get(row["id"], url)
            if body:
                fresh = tic_parse(body, str(row["column_pattern"]))
                if fresh.empty:
                    acc.notes.append({"source": row["id"], "status": "UNMEASURED",
                                      "why": "file header lacks the row's column"})
    df = _hold(raw, fresh)
    if df.empty:
        return []
    df["month"] = pd.to_datetime(df["month"])
    med = trailing_median(df["value"], int(row.get("baseline_months", 12)))
    sz = surprise_frame(df["value"], med, int(row.get("window", 60)))
    # The release day is not in the file. Upper bound: month end + lag_days at 16:00 ET (TIC
    # has published month M between ~M+44 and ~M+50 days); exact dates win via calendar.
    month_end = df["month"] + pd.offsets.MonthEnd(0)
    rel_day = month_end + pd.Timedelta(days=int(row.get("lag_days", 52)))
    avail = release_instant(rel_day, str(row.get("at") or "16:00"), str(row["tz"]),
                            row.get("calendar"), holiday_shift=False)
    hold_days = int(row.get("state_days", 7))
    feat, avail, event = windowed_state(sz, avail, month_end, "surprise_z", hold_days)
    out = _emit(f"os_{row['id']}", row, feat, avail, event, "tic_flow_surprise",
                "conservative_upper_bound_month_end_plus_lag",
                {"state_days": hold_days})
    return [out] if out else []


# ------------------------------------------------------------------------------ BoJ rinban (N4)

def rinban_parse(rows: Sequence[Mapping[str, Any]]) -> pd.DataFrame:
    """Operation results -> per operation: offer vs plan for its bucket, and bid cover.

    Each input row: date, bucket, offered (amount the BoJ offered to buy), planned (the bucket's
    per-operation amount from the BoJ's pre-announced monthly schedule), bids (amount the market
    offered to sell). Planned may be absent when the schedule was not read; such an operation
    keeps its cover but has no size surprise."""
    d = pd.DataFrame(list(rows))
    if d.empty:
        return pd.DataFrame()
    d["date"] = pd.to_datetime(d["date"], errors="coerce")
    for c in ("offered", "planned", "bids"):
        d[c] = pd.to_numeric(d.get(c), errors="coerce")
    d = d.dropna(subset=["date", "offered"])
    d["size_vs_plan"] = d["offered"] / d["planned"] - 1.0
    d["cover"] = d["bids"] / d["offered"]
    g = d.groupby("date", as_index=False).agg(
        size_vs_plan=("size_vs_plan", "mean"), cover=("cover", "mean"),
        offered=("offered", "sum"))
    return g.sort_values("date").reset_index(drop=True)


def collect_rinban(acc: Access, row: Mapping[str, Any]) -> list[Out]:
    """Held until the terms read is OPEN and the box has read one results page and one schedule
    page (the parser's field map is in the row). Offline it serves held rows."""
    raw = RAW / f"{row['id']}.parquet"
    df = _hold(raw, None)
    if df.empty:
        return []
    ops = rinban_parse(df.to_dict("records"))
    if ops.empty:
        return []
    cover_base = trailing_median(ops["cover"], int(row.get("baseline_ops", 20)))
    sz = surprise_frame(ops["cover"], cover_base, int(row.get("window", 60)))
    feat = pd.DataFrame({"size_vs_plan": ops["size_vs_plan"], "cover_surprise": sz["surprise"],
                         "cover_z": sz["surprise_z"]})
    avail = release_instant(ops["date"], str(row.get("at") or "12:10"), str(row["tz"]),
                            row.get("calendar"), holiday_shift=False)
    out = _emit(f"os_{row['id']}", row, feat, avail, ops["date"], "boj_rinban_surprise",
                "boj_result_release_same_day_jst")
    return [out] if out else []


# ------------------------------------------------------------------------------ the pass

ADAPTERS = ("fred_net_liquidity", "fred_funding", "cip_basis", "eia_storage", "usda_esr", "tic",
            "boj_rinban")


def collect(*, text: Callable[[str, Mapping[str, str]], str] | None, state: dict[str, Any],
            notes: list[dict[str, Any]], frames: Mapping[str, pd.DataFrame] | None = None,
            now: datetime | None = None, deadline: float | None = None,
            registry: Mapping[str, Any] | None = None,
            swaps: pd.DataFrame | None = None) -> list[Out]:
    """Every row -> outputs. `text=None` is offline (held raw only). Never raises per row."""
    reg = registry if registry is not None else (fs._read(REGISTRY, {}) or {})
    now = now or datetime.now(UTC)
    acc = Access(text, state, notes, deadline)
    out: list[Out] = []
    for row in reg.get("rows") or []:
        sid, ad = str(row.get("id")), str(row.get("adapter"))
        if ad not in ADAPTERS:
            notes.append({"source": sid, "status": "UNMEASURED", "why": f"no adapter {ad}"})
            continue
        if row.get("terms") != "OPEN":
            notes.append({"source": sid, "status": "UNMEASURED",
                          "why": f"terms {row.get('terms')}", "note": row.get("terms_note", "")})
            # a held row still serves what an earlier OPEN pass or a box read already holds
            live = Access(None, state, notes, deadline)
        else:
            live = acc
        try:
            if ad == "fred_net_liquidity":
                out += collect_net_liquidity(live, row)
            elif ad == "fred_funding":
                out += collect_funding(live, row)
            elif ad == "cip_basis":
                out += collect_cip(live, row, frames or {},
                                   swaps if swaps is not None else load_swap_panel())
            elif ad == "eia_storage":
                out += collect_eia_storage(live, row)
            elif ad == "usda_esr":
                out += collect_usda_esr(live, row, now)
            elif ad == "tic":
                out += collect_tic(live, row)
            elif ad == "boj_rinban":
                out += collect_rinban(live, row)
        except (fs.HardStop, KeyboardInterrupt):
            raise
        except Exception as exc:
            notes.append({"source": sid, "error": f"{type(exc).__name__}: {str(exc)[:80]}"})
    return out


def report(outs: Sequence[Out], notes: Sequence[Mapping[str, Any]],
           registry: Mapping[str, Any]) -> dict[str, Any]:
    built = {oid: meta for oid, _f, meta in outs}
    rows = registry.get("rows") or []
    by_row = {}
    for r in rows:
        mine = [o for o in built if o == f"os_{r['id']}" or o.startswith(f"os_{r['id']}_")]
        why = [n for n in notes if str(n.get("source", "")).startswith(str(r["id"]))]
        by_row[r["id"]] = {"idea": r.get("idea"), "adapter": r.get("adapter"),
                           "terms": r.get("terms"), "series": mine,
                           "state": "PRODUCING" if mine else "UNMEASURED",
                           "why_not": why[:4] if not mine else []}
    return {"generated_utc": fs._now(),
            "rule": ("Every official release row reaches cells or is named here with its "
                     "reason. Robots first; 401/403/429/451 hard stop; ids only from the "
                     "source's own catalogue; release instants late, never early."),
            "rows": by_row, "series": built,
            "producing": sum(1 for v in by_row.values() if v["state"] == "PRODUCING"),
            "of": len(rows), "notes": list(notes)}


def write_report(outs: Sequence[Out], notes: Sequence[Mapping[str, Any]],
                 registry: Mapping[str, Any] | None = None) -> dict[str, Any]:
    """reports/OFFICIAL_SURPRISES.json: per row PRODUCING or why not. Written by the futures_state
    leg after every pass (this module has no clock of its own; that leg is its clock)."""
    reg = registry if registry is not None else (fs._read(REGISTRY, {}) or {})
    doc = report(outs, notes, reg)
    fs._write(REPORT, doc)
    return doc
