"""OPTIONS AND IMPLIED VOL -- the lawful route to the vol-surface class the desk lacks, and the
PROXY family it can build today from data it owns.

    python desks/mt5/research/options_implied.py --once
    python desks/mt5/research/options_implied.py --once --dry-run   # compute, write nothing

WHY THIS EXISTS (data_class_gap #2, `options_implied_vol`, score 6.26 with nothing ingested). Every
macro/FX desk reads 25-delta risk reversals and the ATM vol term structure daily. The gap module
names this file as the class's producer. It does two things, and labels each for what it is.

1. THE IMPLIED SOURCES, ON THE ONE TERMS REGISTER. Every free publisher of option-implied measures
   for the MT5 universe was read on 2026-10-29 (libs/data/terms_fence.SOURCE_POLICY): the
   Minneapolis Fed's market-based probabilities (option-implied mean, sd, skew and tails for corn,
   soybeans, wheat, gold, crude, the euro, the yen and the S&P 500 -- the best fit by far) permit
   "research and informational purposes only" and name no automated access; Eurex bars copying
   without written permission; Cboe's and CME's terms are held routes already; JPX's terms page
   was unreadable. NONE permits live input, so every one is IDEAS_ONLY (or held) and this module
   fetches none of them. The Minneapolis Fed file's parser (`mpd_frame`) is built and tested on a
   fixture so the day a permitting clause is quoted into its row the door is one spec away; until
   then each source's missed-growth line is in the artifact, delta E[log W] UNMEASURED.

2. THE PROXY FAMILY, FROM THE BROKER'S OWN BARS. Realized volatility term structure and realized
   skew per hypothesis-lane symbol, from its MT5 H1 bars: rv over 5/21/63 days, the 5/63 and
   21/63 log term slopes, the 63-day skew of daily returns and the 21-day downside share of
   intraday variance (a realized stand-in for the risk reversal). THIS IS NOT IMPLIED VOL and is
   never called so: provider `MT5_PROXY`, every series name begins "PROXY realized". The series
   land in the world dataset hunter's store (`world_dataset_hunter.ingest_series`), mapped to the
   symbol whose bars made them, so `world_macro_proposer` mints `world_macro_state` cells on them
   -- the form the desk's cells already consume; no second lane. A day's value is knowable once
   its last bar closes: available at the next 00:00 UTC (H1 bars are UTC-indexed), never sooner.

3. THE CBOE OPTIONS AND VOLATILITY STATE (2026-11-03, the empty `options_implied` cluster). Cboe's
   public daily files on cdn.cboe.com -- the VIX, VIX9D, VIX3M, VVIX, SKEW, OVX and GVZ index
   histories and the total / index / equity put-call ratios -- are fetched politely
   (`polite_fetch`, DESK_UA, robots and holds checked per request, a 401/403/429/WAF page a hard
   stop for the site) and MINED AND TESTED under LAWS 5e. Their row `cboe_cdn_index_history` is
   PUBLIC_WITH_TERMS, research-only, redistribution withheld: Cboe's terms (read 2026-11-03)
   grant one personal non-commercial copy and say the Materials "are not intended for trading
   purposes", so no clause permits live use; MACRO_VIEW's VIX risk lean stays cut and nothing
   here touches sizing. From them and the desk's own bars the organ derives the STATE: the
   variance risk premium VIX^2 - RV^2 of US500 (rv_21d of the proxy family above, the
   `macro_desk.RV_PROXY` pattern), the term-structure slopes VIX9D/VIX and VIX/VIX3M, VVIX/VIX,
   and the GVZ and OVX premiums over the realised vol of XAUUSD and XTIUSD (XBRUSD when XTIUSD
   has no bars). Every value is stamped at its AVAILABILITY: a Cboe close of day D at D+1 12:00 UTC
   (`CBOE_RELEASE_H`), never the period date. All of it lands as RESEARCH-ONLY lake packs
   (`data/lake/series/cboe_*.csv` + `.pit.json`, registry rows in `data/asia_sources.json` with
   role `landed`). Their rows carry the cdn.cboe.com URL, so the live-input fence
   (`terms_fence.input_source`, read by pack_cells) holds them from cells: minting a cell feeds
   automatic live promotion, which is trading use, and s.4 forbids it (principal's coordinator,
   2026-11-03: keep the fence). The hold carries a missed-growth line that names the substitute.

4. THE LICENSED SUBSTITUTE, WHICH DOES MINT CELLS. From the desk's own MT5 bars, per US500,
   NAS100, XAUUSD, XTIUSD and XBRUSD (`mt5vol_<sym>` packs): the realised-vol term structure
   (5/21/63d and the 5/21, 21/63 slopes), vol-of-vol, realised skew and downside share, range
   vol (Parkinson, Garman-Klass) and its jump; plus the gold/oil realised-vol ratio
   (`mt5vol_gold_oil_ratio`). Stamped at D+1 00:00 UTC. `pack_cells` mints them as
   `exogenous_conditioner` cells on each pack's registered targets (US500, NAS100, the JPY
   crosses, XAUUSD, the oil CFDs). The report carries counts, dates and liveness, never Cboe's
   values. LIVENESS: a Cboe door that lands nothing on more than `CBOE_EMPTY_RED_RUNS`
   consecutive attempts puts RED in the report's `status`.

Terms of the proxy: the desk's own broker bars; no third-party input.
Clock: `hourly_cycle:options_implied` (department `data`, layer `information`); a symbol is
recomputed once its dataset is older than `REFRESH_H`.
Artifact: desks/mt5/reports/OPTIONS_IMPLIED.json
"""
from __future__ import annotations

import argparse
import io
import json
import math
import os
import re
import sys
import time
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

DESK = Path(__file__).resolve().parents[1]
ROOT = DESK.parents[1]
for _p in (str(ROOT), str(DESK), str(DESK / "research")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

REPORT = DESK / "reports" / "OPTIONS_IMPLIED.json"
BARS = DESK / "data" / "universe"
UNMEASURED = "UNMEASURED"
PROVIDER = "MT5_PROXY"
REFRESH_H = 20.0
#: The pass stops starting symbols after this many seconds (the leg's cap sits above it); the
#: freshness skip means the next pass resumes with the symbols this one did not reach.
DEFAULT_BUDGET_S = 240.0
#: Daily bars a symbol needs before its 63-day window says anything.
MIN_DAYS = 90
#: A UTC day counts only with this many H1 bars (a holiday stub is not a day of variance).
MIN_BARS_PER_DAY = 4
WINDOWS = (5, 21, 63)
ANNUAL = 252.0

#: The implied-vol sources read for this class, each a row key of terms_fence.SOURCE_POLICY (or
#: a host with no row: TERMS_UNMEASURED, never OK). What each would give the desk.
IMPLIED_SOURCES: tuple[tuple[str, str, str], ...] = (
    ("minneapolis_fed_mpd", "minneapolisfed.org",
     ("option-implied distributions for CORN, SOYBEAN, WHEAT, XAUUSD, XTIUSD, EURUSD, USDJPY, "
      "US500")),
    ("eurex_web", "eurex.com", "index-option settlements for GER40 and EU50"),
    ("cboe_delayed_index_values", "cboe.com", "VIX-family indices for US500 and NAS100"),
    ("cboe_cdn_index_history", "cdn.cboe.com",
     ("VIX-family, OVX, GVZ histories and put/call ratios: MINED AS RESEARCH INPUT (part 3), "
      "refused only as live input")),
    ("cme_margin_changes", "cmegroup.com", "CME option bulletins (FX, metals, grains)"),
    ("", "jpx.co.jp", "Nikkei 225 option statistics for JP225 (terms page unreadable)"),
)


def _now() -> datetime:
    return datetime.now(UTC)


def _iso(t: datetime) -> str:
    return t.isoformat(timespec="seconds")


# ---------------------------------------------------------------- IDEAS_ONLY parser (MPD) ----
_MPD_MEASURES = ("mu", "sd", "skew", "kurt", "p10", "p50", "p90", "prdec", "princ")


def mpd_frame(raw: bytes) -> Any:
    """Minneapolis Fed `mpd_stats.csv` -> a long frame [series_code, period, value]: one series
    per market x measure (mean, sd, skew, kurtosis, 10/50/90th percentiles, the probability of a
    large decrease / increase). IDEAS_ONLY (row `minneapolis_fed_mpd`): tested on fixtures and
    never fetched as live input by this module."""
    import pandas as pd

    text = raw.decode("utf-8-sig", "replace")
    if text.lstrip()[:1] == "<":
        raise ValueError("served_html")
    df = pd.read_csv(io.StringIO(text), low_memory=False)
    cols = {re.sub(r"[^a-z0-9]", "", str(c).lower()): c for c in df.columns}
    mcol = cols.get("market")
    dcol = next((cols[k] for k in ("idt", "date", "asof") if k in cols), None)
    if mcol is None or dcol is None:
        raise ValueError(f"mpd columns {sorted(cols)[:12]}")
    days = pd.to_datetime(df[dcol].astype(str), errors="coerce", format="mixed")
    frames = []
    for meas in _MPD_MEASURES:
        if meas not in cols:
            continue
        vals = pd.to_numeric(df[cols[meas]], errors="coerce")
        code = df[mcol].astype(str).str.strip().str.lower().str.replace(r"[^a-z0-9]+", "_",
                                                                        regex=True)
        frames.append(pd.DataFrame({"series_code": code + "_" + meas,
                                    "period": days.dt.strftime("%Y-%m-%d"), "value": vals}))
    if not frames:
        raise ValueError("mpd: no measure columns")
    out = pd.concat(frames, ignore_index=True).dropna(subset=["period", "value"])
    return out.drop_duplicates(["series_code", "period"], keep="last")


def implied_sources() -> list[dict[str, Any]]:
    """Each implied-vol source with its register row, live-input verdict and missed-growth line."""
    from libs.data import terms_fence as tf

    out = []
    for key, host, gives in IMPLIED_SOURCES:
        row = tf.SOURCE_POLICY.get(key) if key else None
        if row is None:
            out.append({"source": key or host, "host": host, "gives": gives,
                        "live_input": "TERMS_UNMEASURED",
                        "missed_growth": {"source": key or host, "kind": "terms_unmeasured",
                                          "delta_elogw": UNMEASURED,
                                          "cause": ("no SOURCE_POLICY row: the publisher's own "
                                                    "terms page was unreadable on 2026-10-29, so "
                                                    "the growth at stake is UNMEASURED")}})
            continue
        refused = bool(row.get("held_route")) or tf.live_input_status(key) in (
            tf.IDEAS_ONLY, tf.METHOD_BLOCKED)
        line = tf.held_missed_growth(key, live_input_refusal=not tf.held_on_terms(key))
        out.append({"source": key, "host": host, "gives": gives,
                    "status": tf.live_input_status(key), "terms_state": tf.terms_state(key),
                    "live_input": "REFUSED" if refused else "PERMITTED",
                    "parser": "mpd_frame" if key == "minneapolis_fed_mpd" else None,
                    "missed_growth": line if refused else None})
    return out


# -------------------------------------------------------------------- the PROXY family ----
def daily_returns(bars: Any) -> tuple[Any, Any]:
    """(daily close-to-close log returns, per-day intraday H1 log returns frame) on UTC days
    holding at least MIN_BARS_PER_DAY bars."""
    import numpy as np
    import pandas as pd

    close = bars["close"].astype("float64")
    close = close[np.isfinite(close) & (close > 0)]
    idx = close.index
    if idx.tz is None:
        idx = idx.tz_localize("UTC")
    close = pd.Series(close.to_numpy(), index=idx.tz_convert("UTC"))
    day = close.index.normalize()
    counts = close.groupby(day).size()
    good = counts[counts >= MIN_BARS_PER_DAY].index
    last = close.groupby(day).last().reindex(good)
    rd = np.log(last).diff().dropna()
    rh = np.log(close).diff()
    rh = rh[day.isin(good)].dropna()
    return rd, rh


def proxy_features(bars: Any) -> Any:
    """Per UTC day: rv_5d, rv_21d, rv_63d (annualised), the log term slopes rv5/rv63 and
    rv21/rv63, the 63-day skew of daily returns, the 21-day intraday rv and the 21-day downside
    share of intraday variance. Each value uses only days up to and including its own."""
    import numpy as np
    import pandas as pd

    rd, rh = daily_returns(bars)
    if len(rd) < MIN_DAYS:
        return pd.DataFrame()
    out = pd.DataFrame(index=rd.index)
    for n in WINDOWS:
        out[f"rv_{n}d"] = np.sqrt(ANNUAL * (rd ** 2).rolling(n, min_periods=n).mean())
    with np.errstate(divide="ignore", invalid="ignore"):
        out["rv_term_5_63"] = np.log(out["rv_5d"] / out["rv_63d"])
        out["rv_term_21_63"] = np.log(out["rv_21d"] / out["rv_63d"])
    out["rskew_63d"] = rd.rolling(63, min_periods=63).skew()
    day = rh.index.normalize()
    sq = (rh ** 2).groupby(day).sum().reindex(out.index).fillna(0.0)
    dn = ((rh.clip(upper=0.0)) ** 2).groupby(day).sum().reindex(out.index).fillna(0.0)
    tot21 = sq.rolling(21, min_periods=21).sum()
    out["rv_intraday_21d"] = np.sqrt(ANNUAL * tot21 / 21.0)
    with np.errstate(divide="ignore", invalid="ignore"):
        out["downside_share_21d"] = dn.rolling(21, min_periods=21).sum() / tot21
    return out.replace([np.inf, -np.inf], np.nan)


def proxy_series(sym: str, feats: Any) -> list[dict[str, Any]]:
    """Feature frame -> the hunter's series dicts, every name labelled PROXY realized."""
    out = []
    for col in feats.columns:
        s = feats[col].dropna()
        if s.empty:
            continue
        pts = [(d.strftime("%Y-%m-%d"), float(v)) for d, v in s.items()
               if math.isfinite(float(v))]
        out.append({"code": col, "freq": "daily", "dims": {}, "stems": [sym],
                    "name": (f"PROXY realized {col} of {sym} from MT5 broker bars (realized, "
                             "not implied vol)"),
                    "points": pts})
    return out


def _load_bars(sym: str, base: Path = BARS) -> Any:
    import pandas as pd

    p = base / f"{sym}_H1.parquet"
    if not p.exists():
        return None
    try:
        df = pd.read_parquet(p)
    except Exception:
        return None
    if "close" not in df.columns or not isinstance(df.index, pd.DatetimeIndex):
        return None
    return df.sort_index()


# ------------------------------------------------- the Cboe options and volatility state ----
CBOE_ROW = "cboe_cdn_index_history"
CBOE_INDEX_URL = "https://cdn.cboe.com/api/global/us_indices/daily_prices/{}_History.csv"
CBOE_PC_URL = "https://cdn.cboe.com/resources/options/volume_and_call_put_ratios/{}.csv"
CBOE_INDICES: tuple[str, ...] = ("VIX", "VIX9D", "VIX3M", "VVIX", "SKEW", "OVX", "GVZ")
CBOE_PC: tuple[tuple[str, str], ...] = (("total", "totalpc"), ("index", "indexpc"),
                                        ("equity", "equitypc"))
#: A Cboe close of day D is stamped knowable at D 00:00 UTC + this many hours (D+1 12:00 UTC):
#: the index settles 16:15 ET and the history file is refreshed after it. Late only costs edge;
#: early would invent it.
CBOE_RELEASE_H = 36
#: A day of the desk's own bars is knowable once its last bar closes: D+1 00:00 UTC.
OWN_BARS_RELEASE_H = 24
CBOE_REFRESH_H = 20.0
#: More than this many consecutive empty attempts on one door is RED.
CBOE_EMPTY_RED_RUNS = 2
#: Seconds the Cboe pass may spend fetching (the proxy family gets the rest of the budget).
CBOE_BUDGET_S = 90.0
#: Fetch answers that HOLD the whole site for a person (polite_fetch records the hold itself).
_HARD_STOP = ("http_401", "http_403", "http_429", "challenge", "METHOD_BLOCKED", "NEEDS_KEY",
              "held")
LAKE = DESK / "data" / "lake" / "series"
LIVENESS = DESK / "data" / "lake" / "options_vol_doors.json"
REGISTRY = DESK / "data" / "asia_sources.json"
ORGAN = "desks/mt5/research/options_implied.py"
#: The registry `role` of a pack this organ writes into the lake itself: the collector has
#: nothing to fetch for it, and `source_drain` counts the landed frame as collected.
LANDED_ROLE = "landed"

#: The instruments each pack conditions (pack_cells reads at most eight per pack).
_EQUITY = ("US500", "NAS100", "XAUUSD", "USDJPY", "EURJPY", "GBPJPY", "AUDJPY", "CADJPY")
_OIL = ("XTIUSD", "XBRUSD")
#: THE SUBSTITUTE PACKS (licensed: the desk's own MT5 bars). These are what mint cells while the
#: Cboe packs are fenced as research-only. symbol -> targets.
SUBSTITUTE_SYMBOLS: dict[str, tuple[str, ...]] = {
    "US500": ("US500", "NAS100", "USDJPY", "EURJPY", "GBPJPY", "AUDJPY", "CADJPY", "XAUUSD"),
    "NAS100": ("NAS100", "US500", "USDJPY", "EURJPY", "AUDJPY"),
    "XAUUSD": ("XAUUSD",),
    "XTIUSD": _OIL,
    "XBRUSD": ("XBRUSD", "XTIUSD"),
}
GOLD_OIL_PACK = "mt5vol_gold_oil_ratio"


def substitute_pack_id(sym: str) -> str:
    return f"mt5vol_{sym.lower()}"


def cboe_doors() -> list[dict[str, Any]]:
    """One door per Cboe file, each landing one research-only lake pack."""
    tgt = {"OVX": _OIL, "GVZ": ("XAUUSD",)}
    out = [{"pack": f"cboe_{sym.lower()}", "kind": "index", "symbol": sym, "code": sym.lower(),
            "url": CBOE_INDEX_URL.format(sym), "targets": tgt.get(sym, _EQUITY),
            "name": f"Cboe {sym} index daily close (research-only, PUBLIC_WITH_TERMS)"}
           for sym in CBOE_INDICES]
    out += [{"pack": f"cboe_pc_{kind}", "kind": "pc", "symbol": f"pc_{kind}",
             "code": f"pc_{kind}", "url": CBOE_PC_URL.format(f), "targets": _EQUITY,
             "name": f"Cboe {kind} put/call volume ratio (research-only, PUBLIC_WITH_TERMS)"}
            for kind, f in CBOE_PC]
    return out


#: The Cboe-derived state packs: pack -> (targets, the Cboe file its inputs come from).
CBOE_STATE_PACKS: dict[str, tuple[tuple[str, ...], str]] = {
    "cboe_vol_state": (_EQUITY, CBOE_INDEX_URL.format("VIX")),
    "cboe_gold_vol_premium": (("XAUUSD",), CBOE_INDEX_URL.format("GVZ")),
    "cboe_oil_vol_premium": (_OIL, CBOE_INDEX_URL.format("OVX")),
}


def _csv_from_header(raw: bytes, want: Any) -> Any:
    import pandas as pd

    text = raw.decode("utf-8-sig", "replace")
    if text.lstrip()[:1] == "<":
        raise ValueError("served_html")
    lines = text.splitlines()
    head = next((i for i, ln in enumerate(lines) if want(ln)), None)
    if head is None:
        raise ValueError("no header row")
    return pd.read_csv(io.StringIO("\n".join(lines[head:])), skip_blank_lines=True)


def _dated(df: Any, col: Any) -> Any:
    import pandas as pd

    dcol = next(c for c in df.columns if str(c).strip().upper() == "DATE")
    days = pd.to_datetime(df[dcol].astype(str).str.strip(), format="%m/%d/%Y", errors="coerce")
    vals = pd.to_numeric(df[col], errors="coerce")
    s = pd.Series(vals.to_numpy(dtype="float64"), index=pd.DatetimeIndex(days))
    s = s[s.index.notna() & s.notna() & (s > 0)]
    s = s[~s.index.duplicated(keep="last")].sort_index()
    if s.empty:
        raise ValueError("no observations")
    return s


def cboe_index_frame(raw: bytes, sym: str) -> Any:
    """`<SYM>_History.csv` -> daily closes by US trading date. OHLC files use CLOSE; single-value
    files (VVIX, SKEW) use the column named for the index, else the last numeric column."""
    df = _csv_from_header(raw, lambda ln: ln.strip().upper().startswith("DATE"))
    cols = {str(c).strip().upper(): c for c in df.columns}
    col = cols.get("CLOSE") or cols.get(sym.upper())
    if col is None:
        num = [c for c in df.columns if str(c).strip().upper() != "DATE"]
        if not num:
            raise ValueError("no value column")
        col = num[-1]
    return _dated(df, col)


def cboe_pc_frame(raw: bytes) -> Any:
    """Cboe put/call archive (a disclaimer block, then DATE,CALLS,PUTS,TOTAL,P/C Ratio) -> the
    ratio by trading date; PUTS/CALLS when the ratio column is absent."""
    import pandas as pd

    df = _csv_from_header(raw, lambda ln: ln.strip().upper().startswith("DATE")
                          and "P" in ln.upper())
    cols = {re.sub(r"[^A-Z]", "", str(c).upper()): c for c in df.columns}
    col = cols.get("PCRATIO")
    if col is None:
        calls, puts = cols.get("CALLS") or cols.get("CALL"), cols.get("PUTS") or cols.get("PUT")
        if calls is None or puts is None:
            raise ValueError("no put/call columns")
        df["_ratio"] = (pd.to_numeric(df[puts], errors="coerce")
                        / pd.to_numeric(df[calls], errors="coerce"))
        col = "_ratio"
    return _dated(df, col)


def cboe_terms() -> dict[str, Any]:
    """The row's labels, its research/live verdict and the missed-growth line of the live hold."""
    from libs.data import terms_fence as tf
    from libs.research import access_classifier as ac

    row = tf.SOURCE_POLICY[CBOE_ROW]
    v = ac.classify(dict(row.get("access_meta") or {}))
    live = (tf.terms_verdict(CBOE_ROW) == "confirmed" and tf.input_source(CBOE_INDEX_URL) is None
            and row.get("live_sizing_input") is not False)
    line = tf.held_missed_growth(CBOE_ROW, live_input_refusal=True)
    line.update({"cause": row["missed_growth"]["cause"],
                 "substitute": row["missed_growth"]["substitute"]})
    return {"policy_row": CBOE_ROW, "status": tf.live_input_status(CBOE_ROW),
            "terms_state": tf.terms_state(CBOE_ROW), "terms_url": row["terms"]["url"],
            "checked_at": row["terms"]["checked_at"], "basis": row["terms"]["clauses"]["4"],
            "access_label": v.access_label, "row_access_label": row.get("access_label"),
            "redistribute": bool(v.redistribute_allowed and row.get("redistribute")),
            "research": bool(v.may("alpha_input")), "live_sizing_input": bool(live),
            "mints_cells": bool(live), "robots": row.get("robots"),
            "missed_growth": None if live else line,
            "macro_view_vix_lean": {
                "state": "RESTORABLE" if live else "NOT_RESTORED",
                "why": ("a verbatim clause permits live use" if live else
                        "no Cboe clause permits live use (s.4: 'not intended for trading "
                        "purposes'); the lean stays cut and is billed once under "
                        "missed_growth.vix_risk_lean_cut")}}


def _get(url: str, deadline: float) -> tuple[bytes | None, str]:
    from libs.data import polite_fetch as pf

    r = pf.get(url, leg="options_implied", timeout=25.0, deadline=deadline, live_input=False)
    if r.ok and r.body:
        return r.body, ""
    if r.verdict:
        return None, str(r.verdict)
    if r.fenced:
        return None, "held"
    if r.status:
        return None, f"http_{r.status}"
    return None, (r.error or "error")[:80]


# ------------------------------------------------------------------ the lake door ----
_ENVELOPE = ("event_time", "published_time", "available_time", "retrieval_time",
             "revision_time", "source_id", "vintage_id")


def write_lake_pack(pack: str, frame: Any, *, release_h: int, now: datetime,
                    lake: Path = LAKE) -> dict[str, Any]:
    """Land one pack in the lake in the envelope `exogenous_conditioner` reads, plus its
    `.pit.json` sidecar. `frame` is indexed by the day the value describes; each value is stamped
    available at that day 00:00 UTC + `release_h`, never the period date. APPEND-ONLY: a day
    already held keeps its first value; a changed value is a NEW row stamped available no earlier
    than now (a revision is never back-dated)."""
    import pandas as pd

    lake.mkdir(parents=True, exist_ok=True)
    path = lake / f"{pack}.csv"
    cols = [str(c) for c in frame.columns]
    f = frame.dropna(how="all")
    f = f.replace([float("inf"), float("-inf")], float("nan"))
    days = pd.DatetimeIndex(f.index).tz_localize(None) if getattr(f.index, "tz", None) else \
        pd.DatetimeIndex(f.index)
    avail = days.tz_localize("UTC") + pd.Timedelta(hours=release_h)
    new = pd.DataFrame({"event_time": days.strftime("%Y-%m-%d"),
                        "published_time": avail.strftime("%Y-%m-%dT%H:%M:%S+00:00"),
                        "available_time": avail.strftime("%Y-%m-%dT%H:%M:%S+00:00"),
                        "retrieval_time": _iso(now), "revision_time": "",
                        "source_id": pack, "vintage_id": 1})
    for c in cols:
        new[c] = f[c].to_numpy(dtype="float64")
    old = None
    if path.exists():
        try:
            old = pd.read_csv(path)
        except Exception:
            old = None
    added = len(new)
    if old is not None and len(old) and set(cols) <= set(old.columns):
        last = old.drop_duplicates("event_time", keep="last").set_index("event_time")
        keep = []
        for i, row in new.iterrows():
            ev = row["event_time"]
            if ev not in last.index:
                keep.append(i)
                continue
            prev = last.loc[ev]
            changed = any(not _same(row[c], prev[c]) for c in cols)
            if changed:
                at = max(pd.Timestamp(row["available_time"]), pd.Timestamp(now))
                new.loc[i, ["available_time", "revision_time"]] = [
                    at.strftime("%Y-%m-%dT%H:%M:%S+00:00"), _iso(now)]
                new.loc[i, "vintage_id"] = int(prev.get("vintage_id") or 1) + 1
                keep.append(i)
        new = new.loc[keep]
        added = len(new)
        out = pd.concat([old, new], ignore_index=True)
    else:
        out = new
    tmp = path.with_suffix(f".tmp{os.getpid()}")
    out.to_csv(tmp, index=False)
    os.replace(tmp, path)
    at = pd.to_datetime(out["available_time"], utc=True)
    known = at[at <= pd.Timestamp(now)]
    side = {"source_id": pack, "organ": ORGAN, "lag_hours": release_h,
            "lag_basis": ("Cboe close at D+1 12:00 UTC" if release_h == CBOE_RELEASE_H
                          else "own MT5 bars: the day's last bar closes by D+1 00:00 UTC"),
            "frames": [{"file": path.name, "status": "STAMPED",
                        "available_time": (known.max().isoformat() if len(known) else None)}],
            "n_rows": len(out), "canonical_file": path.name, "written_at": _iso(now)}
    (lake / f"{pack}.pit.json").write_text(json.dumps(side, indent=1), encoding="utf-8")
    return {"pack": pack, "rows_added": int(added), "rows": len(out),
            "columns": cols, "last_day": str(days.max().date()) if len(days) else None}


def _same(a: Any, b: Any) -> bool:
    try:
        x, y = float(a), float(b)
    except (TypeError, ValueError):
        return str(a) == str(b)
    if x != x and y != y:
        return True
    return abs(x - y) <= 1e-9 * (1.0 + abs(y))


def lake_series(pack: str, col: str, lake: Path = LAKE) -> Any:
    """The first-vintage value of each day of one landed column (the state reads its inputs
    back through the same door it wrote them)."""
    import pandas as pd

    p = lake / f"{pack}.csv"
    if not p.exists():
        return None
    try:
        df = pd.read_csv(p)
    except Exception:
        return None
    if col not in df.columns:
        return None
    df = df.drop_duplicates("event_time", keep="first")
    s = pd.Series(pd.to_numeric(df[col], errors="coerce").to_numpy(dtype="float64"),
                  index=pd.DatetimeIndex(pd.to_datetime(df["event_time"]))).dropna()
    return s.sort_index() if len(s) else None


# ----------------------------------------------- the substitute features (own bars) ----
def daily_ohlc(bars: Any) -> Any:
    """UTC-day OHLC from H1 bars, days with at least MIN_BARS_PER_DAY bars only."""
    import numpy as np
    import pandas as pd

    d = bars[["open", "high", "low", "close"]].astype("float64")
    d = d[np.isfinite(d).all(axis=1) & (d > 0).all(axis=1)]
    idx = d.index if d.index.tz is not None else d.index.tz_localize("UTC")
    d = pd.DataFrame(d.to_numpy(), index=idx.tz_convert("UTC"), columns=d.columns)
    day = d.index.normalize()
    g = d.groupby(day)
    out = pd.DataFrame({"open": g["open"].first(), "high": g["high"].max(),
                        "low": g["low"].min(), "close": g["close"].last(), "n": g.size()})
    return out[out["n"] >= MIN_BARS_PER_DAY].drop(columns="n")


def substitute_features(bars: Any) -> Any:
    """THE LICENSED SUBSTITUTE for the fenced Cboe state, per UTC day, from the desk's own bars:
    the realised-vol term structure (5/21/63d and the 5/21, 21/63 log slopes), vol-of-vol (the
    63-day dispersion of log rv_5d), realised skew (63d) and downside share (21d), range-based
    vol (Parkinson and Garman-Klass, 21d) and its jump (log of today's Garman-Klass variance over
    its trailing 21-day mean, the day itself excluded). Every value uses only its own day and
    earlier."""
    import numpy as np
    import pandas as pd

    base = proxy_features(bars)
    if base.empty:
        return pd.DataFrame()
    out = base[["rv_5d", "rv_21d", "rv_63d", "rv_term_21_63", "rskew_63d",
                "downside_share_21d"]].copy()
    with np.errstate(divide="ignore", invalid="ignore"):
        out["rv_term_5_21"] = np.log(out["rv_5d"] / out["rv_21d"])
        out["vol_of_vol_63d"] = np.log(out["rv_5d"]).rolling(63, min_periods=63).std()
    o = daily_ohlc(bars).reindex(out.index)
    with np.errstate(divide="ignore", invalid="ignore"):
        hl = np.log(o["high"] / o["low"])
        co = np.log(o["close"] / o["open"])
        park = hl ** 2 / (4.0 * math.log(2.0))
        gk = 0.5 * hl ** 2 - (2.0 * math.log(2.0) - 1.0) * co ** 2
        out["parkinson_21d"] = np.sqrt(ANNUAL * park.rolling(21, min_periods=21).mean())
        out["garman_klass_21d"] = np.sqrt(ANNUAL * gk.clip(lower=0).rolling(
            21, min_periods=21).mean())
        prior = gk.clip(lower=0).shift(1).rolling(21, min_periods=21).mean()
        out["gk_jump"] = np.log(gk.clip(lower=1e-12) / prior)
    return out.replace([np.inf, -np.inf], np.nan)


def vol_state(idx: dict[str, Any], rv: dict[str, Any]) -> dict[str, dict[str, Any]]:
    """Cboe-derived pack -> {column: daily series}: the variance risk premium VIX^2 - RV^2 of
    US500 (rv_21d of the desk's own bars, the macro_desk.RV_PROXY pattern), the term slopes
    VIX9D/VIX and VIX/VIX3M, VVIX/VIX, and the GVZ and OVX premiums over XAUUSD and oil RV."""
    import numpy as np

    out: dict[str, dict[str, Any]] = {p: {} for p in CBOE_STATE_PACKS}
    eq = out["cboe_vol_state"]
    for code, (a, b) in {"vix9d_vix": ("VIX9D", "VIX"), "vix_vix3m": ("VIX", "VIX3M"),
                         "vvix_vix": ("VVIX", "VIX")}.items():
        x, y = idx.get(a), idx.get(b)
        if x is not None and y is not None:
            r = (x / y.reindex(x.index)).dropna()
            if len(r):
                eq[code] = r

    def premium(iv_sym: str, rv_s: Any) -> tuple[Any, Any] | None:
        iv = idx.get(iv_sym)
        if iv is None or rv_s is None:
            return None
        j = (iv / 100.0).to_frame("iv").join(rv_s.rename("rv"), how="inner").dropna()
        if j.empty:
            return None
        with np.errstate(divide="ignore", invalid="ignore"):
            return j["iv"] ** 2 - j["rv"] ** 2, np.log(j["iv"] / j["rv"])

    for pack, code, iv_sym, rv_s in (("cboe_vol_state", "vrp", "VIX", rv.get("US500")),
                                     ("cboe_gold_vol_premium", "gvz_vrp", "GVZ",
                                      rv.get("XAUUSD")),
                                     ("cboe_oil_vol_premium", "ovx_vrp", "OVX", rv.get("OIL"))):
        got = premium(iv_sym, rv_s)
        if got is not None:
            out[pack][code] = got[0]
            out[pack][f"{code}_log_ratio"] = got[1]
    return {k: v for k, v in out.items() if v}


def _rv21(feats: dict[str, Any], sym: str) -> Any:
    f = feats.get(sym)
    if f is None or f.empty:
        return None
    rv = f["rv_21d"].dropna()
    rv.index = rv.index.tz_localize(None)
    return rv[rv > 0]


# ---------------------------------------------------------------- the registry rows ----
def pack_rows() -> list[dict[str, Any]]:
    """The registry rows (data/asia_sources.json) of every pack this organ lands: the Cboe packs
    carry their cdn.cboe.com URL, so the live-input fence holds them as research-only; the
    substitute packs carry no URL (the desk's own bars) and mint exogenous_conditioner cells."""
    note = ("landed by desks/mt5/research/options_implied.py; role landed: nothing for the "
            "collector to fetch")
    rows: list[dict[str, Any]] = []
    for d in cboe_doors():
        rows.append({"id": d["pack"], "plane": "options_vol", "country": "us",
                     "name": d["name"], "url": d["url"], "expect": "csv",
                     "access": "public", "cadence": "daily", "role": LANDED_ROLE,
                     "pit": {"event_time": "US trading date", "publication_lag_hours":
                             CBOE_RELEASE_H},
                     "targets": list(d["targets"]),
                     "mechanism": ("options-implied state (dealer gamma, the implied-realised "
                                   "premium) leans on the targets; RESEARCH-ONLY: Cboe's terms "
                                   "permit no live use, so the fence holds it from cells"),
                     "why": note})
    for pack, (tgt, url) in CBOE_STATE_PACKS.items():
        rows.append({"id": pack, "plane": "options_vol", "country": "us",
                     "name": f"Cboe-derived {pack} (research-only, PUBLIC_WITH_TERMS)",
                     "url": url, "expect": "csv", "access": "public", "cadence": "daily",
                     "role": LANDED_ROLE,
                     "pit": {"event_time": "US trading date", "publication_lag_hours":
                             CBOE_RELEASE_H},
                     "targets": list(tgt),
                     "mechanism": ("variance risk premium and vol term structure; "
                                   "RESEARCH-ONLY (Cboe inputs), fenced from cells"),
                     "why": note})
    subs = [(substitute_pack_id(s), t, f"realised vol state of {s} from the desk's own MT5 bars")
            for s, t in SUBSTITUTE_SYMBOLS.items()]
    subs.append((GOLD_OIL_PACK, ("XAUUSD", "XTIUSD", "XBRUSD"),
                 "gold/oil realised-vol ratio from the desk's own MT5 bars"))
    for pack, tgt, what in subs:
        rows.append({"id": pack, "plane": "options_vol", "country": "global",
                     "name": what, "url": "", "expect": "csv", "access": "own_bars",
                     "cadence": "daily", "role": LANDED_ROLE,
                     "pit": {"event_time": "UTC day", "publication_lag_hours":
                             OWN_BARS_RELEASE_H},
                     "targets": list(tgt),
                     "mechanism": ("the licensed SUBSTITUTE for the fenced Cboe implied state: "
                                   "realised-vol term structure, vol-of-vol, realised skew and "
                                   "range-vol jumps lean on the instrument's next move the way "
                                   "the implied surface would"),
                     "why": note})
    return rows


# ---------------------------------------------------------------------- the pass ----
def cboe_pass(*, now: datetime, bars: Path, dry_run: bool = False, fetch: Any = None,
              budget_s: float = CBOE_BUDGET_S, lake: Path = LAKE,
              liveness: Path = LIVENESS) -> dict[str, Any]:
    """Fetch the Cboe doors that are due and land them as research-only lake packs, derive the
    Cboe state, land the own-bar substitute packs, and keep each door's liveness.
    `fetch(url) -> (bytes | None, reason)` is the transport (polite_fetch on the box; a fixture
    in tests)."""
    t0 = time.monotonic()
    try:
        live = json.loads(liveness.read_text("utf-8"))
    except (OSError, ValueError):
        live = {}
    stats: Counter[str] = Counter()
    held = ""
    landed: dict[str, Any] = {}
    for d in cboe_doors():
        key = d["pack"]
        st = live.setdefault(key, {"empty_streak": 0})
        at = _parse_at(st.get("fetched_at"))
        if at and (now - at).total_seconds() < CBOE_REFRESH_H * 3600:
            stats["fresh_skipped"] += 1
            continue
        if held:
            stats["skipped_site_held"] += 1
            continue
        if time.monotonic() - t0 > budget_s:
            stats["deferred_budget"] += 1
            continue
        st["attempted_at"] = _iso(now)
        if fetch is not None:
            raw, why = fetch(d["url"])
        else:
            raw, why = _get(d["url"], time.monotonic() + max(1.0, budget_s))
        s = None
        if raw is not None:
            try:
                s = (cboe_index_frame(raw, d["symbol"]) if d["kind"] == "index"
                     else cboe_pc_frame(raw))
            except Exception as exc:
                why = f"parse:{type(exc).__name__}:{str(exc)[:40]}"
        if s is None or not len(s):
            st["empty_streak"] = int(st.get("empty_streak") or 0) + 1
            st["fail_reason"] = why or "empty"
            stats["empty"] += 1
            if any(h in str(why) for h in _HARD_STOP):
                held = str(why)                       # a person-held stop for the whole site
            continue
        st.update({"empty_streak": 0, "fail_reason": None, "fetched_at": _iso(now),
                   "last_day": str(s.index.max().date()), "n": len(s)})
        if not dry_run:
            landed[key] = write_lake_pack(key, s.to_frame(d["code"]),
                                          release_h=CBOE_RELEASE_H, now=now, lake=lake)
        stats["fetched"] += 1
    if not dry_run:
        liveness.parent.mkdir(parents=True, exist_ok=True)
        liveness.write_text(json.dumps(live, indent=1), encoding="utf-8")
    # THE SUBSTITUTE PACKS (own bars) and the realised vol the Cboe premiums need
    feats: dict[str, Any] = {}
    for sym in SUBSTITUTE_SYMBOLS:
        df = _load_bars(sym, bars)
        feats[sym] = substitute_features(df) if df is not None else None
    subs: dict[str, Any] = {}
    for sym, f in feats.items():
        pid = substitute_pack_id(sym)
        if f is None or f.empty:
            subs[pid] = {"status": "UNMEASURED", "why": f"no or too few {sym} H1 bars"}
            continue
        f = f.copy()
        f.index = f.index.tz_localize(None)
        subs[pid] = (write_lake_pack(pid, f, release_h=OWN_BARS_RELEASE_H, now=now, lake=lake)
                     if not dry_run else {"columns": list(f.columns)})
    oil_sym = "XTIUSD" if feats.get("XTIUSD") is not None and not feats["XTIUSD"].empty \
        else "XBRUSD"
    g, o = _rv21(feats, "XAUUSD"), _rv21(feats, oil_sym)
    if g is not None and o is not None:
        import numpy as np
        j = g.to_frame("g").join(o.rename("o"), how="inner")
        ratio = j.assign(gold_oil_rv_ratio=j["g"] / j["o"],
                         gold_oil_rv_log_ratio=np.log(j["g"] / j["o"]))[
            ["gold_oil_rv_ratio", "gold_oil_rv_log_ratio"]]
        subs[GOLD_OIL_PACK] = (write_lake_pack(GOLD_OIL_PACK, ratio,
                                               release_h=OWN_BARS_RELEASE_H, now=now, lake=lake)
                               if not dry_run else {"columns": list(ratio.columns)})
    else:
        subs[GOLD_OIL_PACK] = {"status": "UNMEASURED", "why": "XAUUSD or oil bars missing"}
    # THE CBOE STATE, read back from the lake (every landed first vintage)
    idx: dict[str, Any] = {}
    for d in cboe_doors():
        s = lake_series(d["pack"], d["code"], lake)
        if s is not None:
            idx[d["symbol"]] = s
    rv = {"US500": _rv21(feats, "US500"), "XAUUSD": _rv21(feats, "XAUUSD"),
          "OIL": _rv21(feats, oil_sym)}
    state: dict[str, Any] = {}
    for pack, cols in vol_state(idx, rv).items():
        import pandas as pd
        frame = pd.DataFrame(cols)
        state[pack] = (write_lake_pack(pack, frame, release_h=CBOE_RELEASE_H, now=now, lake=lake)
                       if not dry_run else {"columns": sorted(cols)})
    doors = {d["pack"]: {f: (live.get(d["pack"]) or {}).get(f)
                         for f in ("empty_streak", "fail_reason", "fetched_at", "last_day", "n")}
             for d in cboe_doors()}
    red = sorted(k for k, v in doors.items() if int(v.get("empty_streak") or 0)
                 > CBOE_EMPTY_RED_RUNS)
    terms = cboe_terms()
    mg = terms["missed_growth"]
    if held:
        mg = {**(mg or {}), "delta_elogw": UNMEASURED,
              "cause": (f"cdn.cboe.com held for a person ({held}): the research state is not "
                        "refreshed; delta E[log W] UNMEASURED")}
    return {
        "policy_row": CBOE_ROW, "terms": terms, "access_label": terms["access_label"],
        "redistribute": terms["redistribute"], "live_sizing_input": terms["live_sizing_input"],
        "mints_cells": terms["mints_cells"],
        "fetched": stats["fetched"], "empty": stats["empty"],
        "fresh_skipped": stats["fresh_skipped"], "deferred_budget": stats["deferred_budget"],
        "skipped_site_held": stats["skipped_site_held"], "held": held or None,
        "rows_appended": (sum(int(v.get("rows_added") or 0) for v in landed.values())
                          if not dry_run else UNMEASURED),
        "doors": doors, "cboe_state": state, "substitutes": subs,
        "red_doors": red, "red_after_empty_runs": CBOE_EMPTY_RED_RUNS,
        "available": {"cboe": f"a close of day D at D 00:00 UTC + {CBOE_RELEASE_H}h",
                      "own_bars": f"day D at D 00:00 UTC + {OWN_BARS_RELEASE_H}h"},
        "registry_rows": len(pack_rows()),
        "cells": ("pack_cells mints exogenous_conditioner cells from the substitute packs; the "
                  "Cboe packs are held by the live-input fence (research-only)"),
        "missed_growth": mg,
        "status": ("RED: Cboe doors empty > "
                   f"{CBOE_EMPTY_RED_RUNS} runs: {', '.join(red)}") if red else "OK",
    }


def _parse_at(v: Any) -> datetime | None:
    try:
        t = datetime.fromisoformat(str(v))
    except (TypeError, ValueError):
        return None
    return t if t.tzinfo else t.replace(tzinfo=UTC)


def _fresh(sym: str, now: datetime, wdh: Any) -> bool:
    meta = wdh._read_json(wdh.meta_path(PROVIDER, f"RVOL_{sym}"), {}) or {}
    at = wdh._parse_iso(meta.get("updated_at"))
    return bool(at and (now - at).total_seconds() < REFRESH_H * 3600)


def run(*, now: datetime | None = None, dry_run: bool = False, bars: Path = BARS,
        symbols: list[str] | None = None, budget_s: float = DEFAULT_BUDGET_S,
        fetch: Any = None, lake: Path = LAKE, liveness: Path = LIVENESS) -> dict[str, Any]:
    from research import world_dataset_hunter as wdh

    now = now or _now()
    t0 = time.monotonic()
    cboe = cboe_pass(now=now, bars=bars, dry_run=dry_run, fetch=fetch, lake=lake,
                     liveness=liveness,
                     budget_s=min(CBOE_BUDGET_S, budget_s / 2.0))
    uni = [s for s, _, _ in wdh.hypothesis_universe()] if symbols is None else list(symbols)
    stats: Counter[str] = Counter()
    qstats: Counter[str] = Counter()
    per: dict[str, Any] = {}
    for sym in uni:
        if time.monotonic() - t0 > budget_s:
            stats["deferred_budget"] += 1
            continue
        if not dry_run and _fresh(sym, now, wdh):
            stats["fresh_skipped"] += 1
            continue
        df = _load_bars(sym, bars)
        if df is None:
            stats["no_h1_bars"] += 1
            continue
        feats = proxy_features(df)
        if feats.empty:
            stats["too_short"] += 1
            per[sym] = {"status": "too_short", "min_days": MIN_DAYS}
            continue
        series = proxy_series(sym, feats)
        last = feats.dropna(how="all").index.max()
        row: dict[str, Any] = {"series": len(series), "last_day": str(last.date()),
                               "latest": {c: (round(float(v), 6) if v == v else None)
                                          for c, v in feats.loc[last].items()}}
        if not dry_run:
            res = wdh.ingest_series(PROVIDER, f"RVOL_{sym}",
                                    f"PROXY realized vol term structure and skew {sym}", series,
                                    now=now, base_score=wdh.dataset_score(PROVIDER, "volatility"),
                                    declared_lag=1, qstats=qstats)
            row.update({"rows_added": res["rows_added"], "passed": res["passed"]})
            stats["rows_appended"] += int(res["rows_added"])
        stats["symbols_computed"] += 1
        per[sym] = row
    measured = bool(uni)
    return {
        "generated_at": _iso(now),
        "organ": "desks/mt5/research/options_implied.py",
        "leg": "hourly_cycle:options_implied",
        "dry_run": dry_run,
        "label": ("PROXY: realized volatility term structure and realized skew from MT5 broker "
                  "bars -- NOT implied volatility"),
        "proxy": {
            "provider": PROVIDER, "store": "desks/mt5/data/world_datasets/obs/mt5_proxy/",
            "symbols_in_lane": len(uni) if measured else UNMEASURED,
            "symbols_computed": stats["symbols_computed"],
            "fresh_skipped": stats["fresh_skipped"], "no_h1_bars": stats["no_h1_bars"],
            "too_short": stats["too_short"], "deferred_budget": stats["deferred_budget"],
            "rows_appended": stats["rows_appended"] if not dry_run else UNMEASURED,
            "quality_by_reason": dict(qstats),
            "available": "next 00:00 UTC after the day's last bar (declared_lag 1 day)",
            "per_symbol": per},
        "implied_sources": implied_sources(),
        "cboe": cboe,
        "status": cboe["status"],
        "rule": ("no implied-vol source is used as LIVE input until its own terms quote a "
                 "permitting clause into its SOURCE_POLICY row; research-only sources are mined "
                 "and tested with their label (LAWS 5e) and never redistributed; the proxy is "
                 "labelled PROXY and never called implied vol; absence is UNMEASURED, never 0"),
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    ap.add_argument("--once", action="store_true", help="one pass (the default)")
    ap.add_argument("--budget-s", type=float, default=DEFAULT_BUDGET_S)
    ap.add_argument("--dry-run", action="store_true",
                    help="compute the proxy and read the register; write only the report")
    args = ap.parse_args(argv)
    rep = run(dry_run=args.dry_run, budget_s=args.budget_s)
    from research.world_dataset_hunter import write_json
    write_json(REPORT, json.loads(json.dumps(rep, default=str)))
    p = rep["proxy"]
    refused = sum(1 for s in rep["implied_sources"] if s["live_input"] != "PERMITTED")
    print(f"options_implied: proxy symbols={p['symbols_computed']} rows={p['rows_appended']} "
          f"fresh={p['fresh_skipped']} no_bars={p['no_h1_bars']} short={p['too_short']}; "
          f"implied sources {len(rep['implied_sources'])}, not live {refused}; cboe "
          f"fetched={rep['cboe']['fetched']} empty={rep['cboe']['empty']} "
          f"held={rep['cboe']['held']} status={rep['status']}", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
