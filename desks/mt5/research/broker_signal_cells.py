#!/usr/bin/env python3
"""BROKER-SIDE SIGNAL CELLS (B3, approved 2026-10-13) -- the venue's own tape, swaps and the crowd.

    python desks/mt5/research/broker_signal_cells.py --once
    python desks/mt5/research/broker_signal_cells.py --once --dry-run   # build, mint nothing
    python desks/mt5/research/broker_signal_cells.py --once --offline   # no network (crowd held)

WHAT THE DESK ALREADY RECORDS, AND WHAT THIS ADDS. Nothing here is a new recorder:

  activity   every H1 bar the box stores (`data/universe/<SYM>_H1.parquet`, written by the bar
             refresh) carries Fusion's `tick_volume` and `spread`. `family_spread_state` TRADES a
             symbol's own spread; nothing used either column as a CONDITIONER on another
             mechanism. Two series per symbol: `tickvol_abn` (log tick volume against the
             trailing median of the SAME broker hour, so the session cycle is not read as news)
             and `spread_widen` (the bar's spread over the same-hour trailing median). A symbol
             whose bars carry a flat spread (raw accounts quote 0 on the majors) has no
             `spread_widen` column, and that is reported, never filled.
  swaps      `mt5desk.tape.publish_swap_panel` (MT5-ContractTerms, hourly) writes the box's own
             `symbol_info` swap panel to `data/intelligence/broker_swaps/`; `carry_state` reads it
             as a cost. Here its REPRICINGS are the event: `swap_diff` (long minus short) per
             observation, stamped at the capture that first saw the value.
  crowd      Myfxbook's community outlook through its OFFICIAL API (`get-community-outlook.json`,
             a session id, free tier 100 calls/day; this organ makes at most one per hour). The
             session is read from `MYFXBOOK_SESSION` -- the name `data/asia_sources.json` already
             declares -- or `data/secrets/myfxbook.json` `{"session": ...}`; it is never logged,
             printed or written, and this organ NEVER logs in (no password is ever sent). The
             host's robots.txt is asked first (the strict rule of 2026-11-10: unreadable robots
             are not permission), and 401/403/429/451, a Cloudflare challenge or an invalid
             session is a HARD STOP written to state. Collective2: its official API v4 has no
             sentiment or aggregated-positioning endpoint (read 2026-11-11: per-strategy
             `GetStrategyOpenPositions` only), and building one would mean bulk-reading third
             parties' strategy books under terms nobody has confirmed -- so C2 stays FAIL-CLOSED
             and is named UNMEASURED in the report with that reason.

THE CELLS, each a distinct claim, each through an EXISTING family and the one intake door
(`proposer_common.donate` -> `data/intelligence/broker_signal_cells/` -> the compiler -> the docket
the sealed gauntlet judges). No new family: the series land in `data/lake/series/` and the
families read them on their own point-in-time clock.

  alt_conditioned        tickvol_abn HIGH x session_range_breakout   volume confirms the break
                         tickvol_abn HIGH x trend_ma_cross            participation carries trend
                         tickvol_abn LOW  x mean_reversion_rsi        a thin tape's moves revert
                         spread_widen HIGH x mean_reversion_rsi       a move bought with a wide
                                                                      book was liquidity, it fades
                         spread_widen LOW x session_range_breakout    a deep book's break carries
  alt_series_momentum    swap_diff repricing (lookback 1), side +1    the broker passed a rate
                                                                      move on; carry follows it
  exogenous_conditioner  crowd long% extreme, side -1 (contrarian)    a crowd is a supply of stops
  alt_series_momentum    crowd long% piling in (lookback 4), side -1  the late crowd is the fuel

THE POINT-IN-TIME CONTRACT. Every series row carries `available_time` in TRUE UTC: a bar's value
at its close converted from the broker stamp by `libs.regime.session_clock.server_to_utc` (the
desk's one conversion, New York + 7 h), a swap at the capture that first saw it, a crowd reading
at its retrieval. The families compare that UTC stamp with BROKER-stamped bars, which run two to
three hours ahead of UTC, so every cell here sets `lag_hours=3`: a UTC stamp u reaches a bar only
at stamp u+3, i.e. true time u+0..1 h, never before it was known.

TRIALS ARE NEVER INFLATED. A cell is minted ONCE in its life (state keeps its hash) and only when
its series exists with enough rows to fire; a symbol whose swap never repriced, whose spread is
flat, or whose crowd series is still accruing is NAMED in the report, not minted to come back
UNKNOWN. Share CFDs are refused at the door by `universe_policy.may_hypothesise`.
"""
from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import os
import sys
import time
from collections.abc import Callable, Iterable, Mapping
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

DESK = Path(__file__).resolve().parents[1]
ROOT = DESK.parent.parent
for _p in (str(DESK), str(DESK / "research"), str(ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

SEAT = "broker_signal_cells"
SERIES = DESK / "data" / "lake" / "series"
UNIVERSE_DIR = DESK / "data" / "universe"
SWAP_PANEL = DESK / "data" / "intelligence" / "broker_swaps"
STATE_DIR = DESK / "data" / "broker_signals"
STATE = STATE_DIR / "state.json"
CROWD_RAW = STATE_DIR / "myfxbook_outlook.jsonl"
SECRETS = ROOT / "data" / "secrets" / "myfxbook.json"
OUT = DESK / "reports" / "BROKER_SIGNAL_CELLS.json"
UNMEASURED = "UNMEASURED"

UA = "quant-research/1.0 (+https://github.com/kingdemond434-cpu/quant; broker_signal_cells)"
MYFXBOOK_URL = "https://www.myfxbook.com/api/get-community-outlook.json"
#: The name `data/asia_sources.json` declares for this source; never a second spelling.
MYFXBOOK_KEY_ENV = "MYFXBOOK_SESSION"
C2_KEY_ENV = "C2_API_KEY"
#: One outlook call an hour at most: 24 a day against the free tier's 100.
CROWD_MIN_GAP_S = 55 * 60
CROWD_DAILY_CAP = 90
HARD_STOP = frozenset({401, 403, 429, 451})
#: Myfxbook's API terms have not been read verbatim from the source (2026-11-11): unread terms
#: fail CLOSED. Nothing is fetched until a box read records the terms (URL, status, sha256,
#: verbatim text) under reports/box_reads and a reviewed commit sets this to "OPEN".
MYFXBOOK_TERMS = "HELD"

#: Every cell here reads a UTC-stamped series against broker-stamped bars (UTC+2/+3).
LAG_H = 3
#: Below this many rows a series is ACCRUING and mints nothing (the families' own floor is 30).
MIN_ROWS = 30
#: Same-hour observations the activity baseline is measured over, strictly before the bar.
BASELINE_N = 20
#: H1 bars of activity history written per symbol: ~4 years, enough for the gauntlet's folds
#: without writing the whole 2018- store twice on a box whose disk is the binding constraint.
ACTIVITY_BARS = 26_000
#: Classes whose swap is a carry the broker reprices; crypto CFDs carry a fixed financing fee.
CARRY_CLASSES = ("forex", "forex exotics", "commodities", "energy", "indices")

#: (column, regime, base family, the claim) -- the activity conditioner cells.
ACTIVITY_CELLS: tuple[tuple[str, str, str, str], ...] = (
    ("tickvol_abn", "high", "session_range_breakout",
     "a range break on abnormal participation is information, not noise, and carries"),
    ("tickvol_abn", "high", "trend_ma_cross",
     "a trend turn made with abnormal participation persists"),
    ("tickvol_abn", "low", "mean_reversion_rsi",
     "an extreme printed on a thin tape had no participation behind it and reverts"),
    ("spread_widen", "high", "mean_reversion_rsi",
     "a move printed while the broker's spread was wide was paid for in liquidity and fades"),
    ("spread_widen", "low", "session_range_breakout",
     "a range break through a tight, competitive book carries"),
)


# ----------------------------------------------------------------------------- small helpers
def _now() -> datetime:
    return datetime.now(UTC)


def _read(p: Path, default: Any = None) -> Any:
    try:
        return json.loads(p.read_text("utf-8"))
    except (OSError, ValueError):
        return default


def _write(p: Path, doc: Any) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_suffix(p.suffix + ".tmp")
    tmp.write_text(json.dumps(doc, indent=1, default=str), encoding="utf-8")
    os.replace(tmp, p)


def write_series(sid: str, frame: pd.DataFrame, root: Path | None = None) -> Path:
    base = root or SERIES
    base.mkdir(parents=True, exist_ok=True)
    p = base / f"{sid}.parquet"
    tmp = p.with_suffix(".parquet.tmp")
    frame.to_parquet(tmp, index=False)
    os.replace(tmp, p)
    return p


def lane_symbols() -> list[str]:
    """Hypothesis-lane symbols from MetaTrader's own registry (share CFDs never)."""
    from research import universe_policy as up
    return sorted(s for s in up._registry() if up.may_hypothesise(s, "alt_conditioned"))


def asset_class(sym: str) -> str:
    from research import universe_policy as up
    return str(up.asset_class_of(sym) or "").strip().lower()


def cell_hash(*parts: Any) -> str:
    return hashlib.sha1("|".join(json.dumps(p, sort_keys=True) for p in parts).encode()
                        ).hexdigest()[:16]


# ------------------------------------------------------------------------- activity (bars)
def _bars(sym: str, root: Path | None = None) -> pd.DataFrame | None:
    p = (root or UNIVERSE_DIR) / f"{sym}_H1.parquet"
    if not p.exists():
        return None
    try:
        df = pd.read_parquet(p)
    except Exception:
        return None
    if df.empty:
        return None
    df.index = pd.DatetimeIndex(pd.to_datetime(df.index, utc=True, errors="coerce"))
    return df[~df.index.isna()].sort_index()


def _same_hour_baseline(s: pd.Series, n: int = BASELINE_N) -> pd.Series:
    """Trailing median of the same broker hour over the previous `n` days, strictly causal."""
    hours = pd.Index(s.index.hour)
    return s.groupby(hours).transform(
        lambda g: g.rolling(n, min_periods=max(5, n // 2)).median().shift(1))


def activity_frame(bars: pd.DataFrame, source_id: str,
                   max_bars: int = ACTIVITY_BARS) -> tuple[pd.DataFrame | None, dict[str, str]]:
    """(series frame, per-column reason a column is absent). None when nothing is measurable."""
    why: dict[str, str] = {}
    d = bars.tail(max_bars + 30 * 24)
    cols: dict[str, pd.Series] = {}
    if "tick_volume" in d.columns:
        tv = pd.to_numeric(d["tick_volume"], errors="coerce").astype(float)
        tv = tv.where(tv > 0)
        lt = np.log(tv)
        cols["tickvol_abn"] = lt - _same_hour_baseline(lt)
    else:
        why["tickvol_abn"] = "bars carry no tick_volume column"
    if "spread" in d.columns:
        sp = pd.to_numeric(d["spread"], errors="coerce").astype(float)
        if sp.dropna().nunique() < 4 or float(sp.max() or 0.0) <= 0:
            why["spread_widen"] = ("the bars' spread is flat or zero (a raw account quotes the "
                                   "majors at 0): no widening is measurable")
        else:
            base = _same_hour_baseline(sp).where(lambda b: b > 0)
            cols["spread_widen"] = sp / base
    else:
        why["spread_widen"] = "bars carry no spread column"
    if not cols:
        return None, why
    f = pd.DataFrame(cols).replace([np.inf, -np.inf], np.nan).dropna(how="all").tail(max_bars)
    for c in list(f.columns):
        if f[c].notna().sum() < MIN_ROWS:
            why[c] = f"{int(f[c].notna().sum())} measurable rows, below {MIN_ROWS}"
            f = f.drop(columns=c)
    if f.empty or not len(f.columns):
        return None, why
    from libs.regime.session_clock import server_to_utc
    # The bar's value is known at its CLOSE: the next stamp, converted to true UTC.
    closes = f.index + pd.Timedelta(hours=1)
    f = f.astype("float32").reset_index(drop=True)
    f["available_time"] = server_to_utc(closes)
    f["event_time"] = f["available_time"]
    f["source_id"] = source_id
    return f, why


# ---------------------------------------------------------------------------- swaps (panel)
def _panel_rows(panel_dir: Path) -> Iterable[dict[str, Any]]:
    """Every swap_table row the panel holds: hourly JSON files and the gzipped daily rollups."""
    if not panel_dir.exists():
        return
    for f in sorted(panel_dir.glob("*.json")):
        rows = _read(f, [])
        if isinstance(rows, list):
            yield from (r for r in rows if isinstance(r, dict))
    for f in sorted(panel_dir.glob("*.jsonl.gz")):
        try:
            with gzip.open(f, "rt", encoding="utf-8") as fh:
                for line in fh:
                    try:
                        r = json.loads(line)
                    except ValueError:
                        continue
                    if isinstance(r, dict):
                        yield r
        except OSError:
            continue


def swap_frames(panel_dir: Path | None = None) -> dict[str, pd.DataFrame]:
    """Per symbol: swap_long, swap_short, swap_diff, stamped at the capture that saw each value.

    `observed_at` (the box's capture, UTC) when the row carries it; the VPS-era rows carry only
    `found_at`, which was their capture time. Never a later stamp read earlier."""
    per: dict[str, list[tuple[str, float, float]]] = {}
    for r in _panel_rows(panel_dir or SWAP_PANEL):
        if r.get("kind") != "swap_table" or not r.get("symbols"):
            continue
        lo, sh = r.get("swap_long"), r.get("swap_short")
        at = r.get("observed_at") or r.get("found_at")
        if lo is None or sh is None or not at:
            continue
        per.setdefault(str(r["symbols"][0]), []).append((str(at), float(lo), float(sh)))
    out: dict[str, pd.DataFrame] = {}
    for sym, rows in per.items():
        f = pd.DataFrame(rows, columns=["available_time", "swap_long", "swap_short"])
        # One vectorised parse per symbol: a per-row parse cost 40 s on the 17 MB panel.
        f["available_time"] = pd.to_datetime(f["available_time"], utc=True, errors="coerce",
                                             format="ISO8601")
        f = f.dropna(subset=["available_time"])
        f = f.drop_duplicates("available_time", keep="last").sort_values("available_time")
        f["swap_diff"] = f["swap_long"] - f["swap_short"]
        f["event_time"] = f["available_time"]
        f["source_id"] = f"brk_swap_{sym}"
        out[sym] = f.reset_index(drop=True)
    return out


def repricings(frame: pd.DataFrame) -> int:
    """How many times the broker changed this symbol's swap_diff inside the panel."""
    v = frame["swap_diff"].round(6)
    return int((v != v.shift()).sum() - 1) if len(v) else 0


# ---------------------------------------------------------------------- crowd (official API)
def myfxbook_session(env: Mapping[str, str] | None = None,
                     secrets: Path | None = None) -> str | None:
    """The session id, or None. Read, never printed, never written anywhere."""
    val = (env if env is not None else os.environ).get(MYFXBOOK_KEY_ENV, "").strip()
    if val:
        return val
    doc = _read(secrets or SECRETS, {}) or {}
    s = str(doc.get("session") or "").strip() if isinstance(doc, dict) else ""
    return s or None


def _robots_refusal(url: str) -> str | None:
    """The desk's strict robots gate (index_discovery, ruling 2026-11-10)."""
    from research.index_discovery import robots_refusal
    return robots_refusal(url)


def _http_get(url: str) -> tuple[int | None, str, str]:
    """(status, body, error). One attempt; never raises; the URL is never echoed back."""
    from libs.data import polite_fetch
    r = polite_fetch.get(url, headers={"User-Agent": UA, "Accept": "application/json"},
                         timeout=30.0, retries=0, leg=SEAT)
    return r.status, r.text, ("" if r.ok else (f"HTTP {r.status}" if r.status else "network"))


def parse_outlook(body: str) -> tuple[list[dict[str, Any]], str | None]:
    """(rows, why-not). A challenge page or an API error is a reason, never an empty reading."""
    if "Just a moment" in body[:2000] or "cf-chl" in body[:4000]:
        return [], "ANTIBOT_CHALLENGE"
    try:
        doc = json.loads(body)
    except ValueError:
        return [], "ROUTE_CHANGED: body is not JSON"
    if not isinstance(doc, dict):
        return [], "ROUTE_CHANGED: body is not an object"
    if doc.get("error"):
        msg = str(doc.get("message") or "")
        return [], ("SESSION_INVALID" if "session" in msg.lower() else f"API_ERROR: {msg[:60]}")
    rows = []
    for s in doc.get("symbols") or []:
        if not isinstance(s, dict) or not s.get("name"):
            continue
        try:
            lp = float(s.get("longPercentage"))
            npos = float(s.get("longPositions") or 0) + float(s.get("shortPositions") or 0)
            lpos = 100.0 * float(s.get("longPositions") or 0) / npos if npos > 0 else np.nan
        except (TypeError, ValueError):
            continue
        rows.append({"symbol": str(s["name"]).upper(), "long_pct": lp, "long_pos_pct": lpos})
    return rows, (None if rows else "ROUTE_CHANGED: no symbols in the outlook")


def collect_crowd(state: dict[str, Any], *, now: datetime, offline: bool,
                  session: str | None,
                  get: Callable[[str], tuple[int | None, str, str]] | None = None,
                  robots: Callable[[str], str | None] | None = None,
                  raw: Path | None = None, terms: str | None = None) -> dict[str, Any]:
    """At most one outlook call per hour, appended to the raw jsonl with its retrieval time."""
    st = state.setdefault("myfxbook", {})
    if st.get("hard_stop"):
        return {"status": "HARD_STOP", "why": st["hard_stop"],
                "release": "delete myfxbook.hard_stop in data/broker_signals/state.json"}
    if session is None:
        return {"status": "UNCONFIGURED",
                "why": f"{MYFXBOOK_KEY_ENV} is not set and data/secrets/myfxbook.json holds no "
                       "session: a named state, never a dead endpoint"}
    if (terms or MYFXBOOK_TERMS) != "OPEN":
        return {"status": "TERMS_HELD",
                "why": "Myfxbook's API terms are unread at the source; fail-closed until a box "
                       "read records them and MYFXBOOK_TERMS is set OPEN in a reviewed commit"}
    if offline:
        return {"status": "OFFLINE", "why": "--offline: serving the held raw readings"}
    last = pd.to_datetime(st.get("last_fetch"), utc=True, errors="coerce")
    if pd.notna(last) and (pd.Timestamp(now) - last).total_seconds() < CROWD_MIN_GAP_S:
        return {"status": "NOT_DUE", "last_fetch": st.get("last_fetch")}
    day = now.date().isoformat()
    if st.get("day") != day:
        st["day"], st["calls"] = day, 0
    if int(st.get("calls") or 0) >= CROWD_DAILY_CAP:
        return {"status": "DAILY_CAP", "calls": st["calls"]}
    refused = (robots or _robots_refusal)(MYFXBOOK_URL)
    if refused:
        return {"status": "REFUSED_BY_ROBOTS", "why": refused}
    status, body, err = (get or _http_get)(f"{MYFXBOOK_URL}?session={session}")
    st["calls"] = int(st.get("calls") or 0) + 1
    st["last_fetch"] = now.isoformat(timespec="seconds")
    if status in HARD_STOP:
        st["hard_stop"] = f"HTTP {status} at {st['last_fetch']}"
        return {"status": "HARD_STOP", "why": st["hard_stop"]}
    if err:
        return {"status": "FETCH_ERROR", "why": err}
    rows, why = parse_outlook(body)
    if why in ("ANTIBOT_CHALLENGE", "SESSION_INVALID"):
        st["hard_stop"] = f"{why} at {st['last_fetch']}"
        return {"status": "HARD_STOP", "why": st["hard_stop"]}
    if why:
        return {"status": "ROUTE_CHANGED", "why": why}
    p = raw or CROWD_RAW
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("a", encoding="utf-8") as fh:
        for r in rows:
            fh.write(json.dumps({**r, "retrieval_time": st["last_fetch"]}) + "\n")
    return {"status": "COLLECTED", "symbols": len(rows)}


def crowd_frames(raw: Path | None = None) -> dict[str, pd.DataFrame]:
    p = raw or CROWD_RAW
    if not p.exists():
        return {}
    rows = []
    for line in p.read_text("utf-8").splitlines():
        try:
            rows.append(json.loads(line))
        except ValueError:
            continue
    if not rows:
        return {}
    f = pd.DataFrame(rows)
    f["available_time"] = pd.to_datetime(f["retrieval_time"], utc=True, errors="coerce")
    out = {}
    for sym, g in f.dropna(subset=["available_time"]).groupby("symbol"):
        g = g.drop_duplicates("available_time", keep="last").sort_values("available_time")
        g = g[["available_time", "long_pct", "long_pos_pct"]].copy()
        g["event_time"] = g["available_time"]
        g["source_id"] = f"crowd_mfx_{sym}"
        out[str(sym)] = g.reset_index(drop=True)
    return out


# ---------------------------------------------------------------------------------- cells
def _cell(sym: str, family: str, params: dict[str, Any], chart: str, sid: str, claim: str,
          arm: str, *, seat: str = SEAT,
          culture: tuple[str, str] = ("venue/broker", "retail_broker_flow")) -> dict[str, Any]:
    """One intake row: an exact (family, params, symbol, chart) the compiler admits as written.
    `timeframe` in params pins the chart, so the compiler's axis expansion never re-slices it
    into extra trials."""
    from research.proposer_common import candidate
    p = {**params, "lag_hours": LAG_H, "timeframe": chart}
    c = candidate(seat, sym, family, p, claim,
                  f"{family} on {sid} -> {sym} {chart} [{arm}]",
                  {"series": sid, "arm": arm, "lag_hours": LAG_H})
    c.update({"chart": chart,
              "required_data": [f"desks/mt5/data/lake/series/{sid}.parquet"],
              "source_culture": culture[0], "participant_structure": culture[1],
              "falsifier": f"{arm} on {sid} has no out-of-sample edge on {sym} at {chart} "
                           "after costs"})
    return c


def plan_cells(activity: Mapping[str, list[str]], swaps: Iterable[str],
               crowd: Iterable[str]) -> list[dict[str, Any]]:
    """Every cell whose series is present and measurable, in a stable order."""
    out: list[dict[str, Any]] = []
    for sym in sorted(activity):
        sid = f"brk_act_{sym}"
        for col, regime, base, claim in ACTIVITY_CELLS:
            if col not in activity[sym]:
                continue
            out.append(_cell(sym, "alt_conditioned",
                             {"source": sid, "signal": col, "transform": "level_z",
                              "regime": regime, "threshold": 1.0, "base_family": base,
                              "base_params": {}},
                             "H1", sid, f"{claim} ({col} {regime}, broker-own tape)",
                             f"activity:{col}|{regime}|{base}"))
    for sym in sorted(swaps):
        sid = f"brk_swap_{sym}"
        out.append(_cell(sym, "alt_series_momentum",
                         {"source": sid, "signal": "swap_diff", "lookback": 1,
                          "threshold": 1.0, "side_when_up": 1},
                         "H4", sid, "the broker repriced the financing leg toward one side: the "
                         "rate move it passed on is carry the market has not finished pricing",
                         "swap:repricing"))
    for sym in sorted(crowd):
        sid = f"crowd_mfx_{sym}"
        out.append(_cell(sym, "exogenous_conditioner",
                         {"source": sid, "signal": "long_pct", "transform": "level_z",
                          "threshold": 1.5, "side_when_high": -1},
                         "H4", sid, "retail crowding at an extreme is a supply of stops on "
                         "the crowded side: fade it", "crowd:level_contrarian"))
        out.append(_cell(sym, "alt_series_momentum",
                         {"source": sid, "signal": "long_pct", "lookback": 4,
                          "threshold": 1.5, "side_when_up": -1},
                         "H1", sid, "the crowd piling into one side late is the fuel for the "
                         "reversal, not the trend", "crowd:momentum_contrarian"))
    return out


def mint(cells: list[dict[str, Any]], state: dict[str, Any], *, dry_run: bool,
         seat: str = SEAT, donate: Callable[..., Path | None] | None = None,
         counts: Callable[[], dict[str, Any]] | None = None) -> dict[str, Any]:
    """Donate every cell not yet minted, ONCE in its life; a refused door mints nothing."""
    minted = set(state.get("minted") or [])
    fresh = [c for c in cells if cell_hash(c["symbol"], c["family"], c["params"]) not in minted]
    res: dict[str, Any] = {"cells_planned": len(cells), "cells_new": len(fresh),
                           "cells_minted_total": len(minted), "donated": 0, "path": None}
    if dry_run or not fresh:
        return res
    if donate is None:
        from research.proposer_common import donate as _door
        from research.proposer_common import donation_counts as _counts
        donate, counts = _door, _counts
    try:
        path = donate(seat, fresh, tests_run=len(fresh))
        got = (counts or (lambda: {}))()
    except Exception as exc:
        res["error"] = f"{type(exc).__name__}: {str(exc)[:120]}"
        return res
    if path is None:
        res["refused"] = {k: got.get(k) for k in ("refused_wrong_lane", "refused_unstamped")}
        return res
    # Wrong-lane rows never return, so they are recorded as minted and not re-offered; a row the
    # PIT stamp refused is left unminted so the next pass offers it again.
    unstamped = {str(r.get("title")) for r in got.get("refusals") or []}
    for c in fresh:
        if str(c.get("title")) not in unstamped:
            minted.add(cell_hash(c["symbol"], c["family"], c["params"]))
    state["minted"] = sorted(minted)
    res.update({"donated": int(got.get("donated") or len(fresh)), "path": str(path),
                "refused_wrong_lane": int(got.get("refused_wrong_lane") or 0),
                "refused_unstamped": int(got.get("refused_unstamped") or 0),
                "cells_minted_total": len(minted), "tests_run": len(fresh)})
    return res


# ---------------------------------------------------------------------------------- build
def build(*, dry_run: bool = False, offline: bool = False, now: datetime | None = None,
          symbols: list[str] | None = None, universe_dir: Path | None = None,
          panel_dir: Path | None = None, series_root: Path | None = None,
          state_path: Path | None = None, raw: Path | None = None,
          out: Path | None = None, get: Callable[[str], tuple[int | None, str, str]] | None = None,
          robots: Callable[[str], str | None] | None = None,
          env: Mapping[str, str] | None = None, secrets: Path | None = None,
          donate: Callable[..., Path | None] | None = None,
          counts: Callable[[], dict[str, Any]] | None = None) -> dict[str, Any]:
    t0 = time.monotonic()
    now = now or _now()
    state = _read(state_path or STATE, {}) or {}
    syms = symbols if symbols is not None else lane_symbols()
    lane = set(syms)

    # activity
    act_cols: dict[str, list[str]] = {}
    act_unmeasured: dict[str, Any] = {}
    for sym in syms:
        b = _bars(sym, universe_dir)
        if b is None:
            act_unmeasured[sym] = "no H1 bars on this host"
            continue
        f, why = activity_frame(b, f"brk_act_{sym}")
        if why:
            act_unmeasured[sym] = why
        if f is None:
            continue
        cols = [c for c in f.columns if c in ("tickvol_abn", "spread_widen")]
        act_cols[sym] = cols
        if not dry_run:
            write_series(f"brk_act_{sym}", f, series_root)

    # swaps
    swaps = swap_frames(panel_dir)
    swap_ok: list[str] = []
    swap_unmeasured: dict[str, str] = {}
    for sym in sorted(lane):
        if not any(k in asset_class(sym) for k in CARRY_CLASSES) or asset_class(sym) == "crypto":
            continue
        f = swaps.get(sym)
        if f is None:
            swap_unmeasured[sym] = "no row in the broker swap panel"
            continue
        n_re = repricings(f)
        if len(f) < MIN_ROWS or n_re < 2:
            swap_unmeasured[sym] = f"{len(f)} panel rows, {n_re} repricing(s): nothing to fire on"
            continue
        swap_ok.append(sym)
        if not dry_run:
            write_series(f"brk_swap_{sym}", f, series_root)

    # crowd
    crowd_fetch = collect_crowd(state, now=now, offline=offline or dry_run,
                                session=myfxbook_session(env, secrets), get=get,
                                robots=robots, raw=raw)
    crowd = crowd_frames(raw)
    crowd_ok: list[str] = []
    crowd_accruing: dict[str, int] = {}
    for sym, f in sorted(crowd.items()):
        if sym not in lane:
            continue
        if len(f) < MIN_ROWS:
            crowd_accruing[sym] = len(f)
            continue
        crowd_ok.append(sym)
        if not dry_run:
            write_series(f"crowd_mfx_{sym}", f, series_root)

    cells = plan_cells(act_cols, swap_ok, crowd_ok)
    cell_res = mint(cells, state, dry_run=dry_run, donate=donate, counts=counts)
    arms: dict[str, int] = {}
    for c in cells:
        a = str(c["evidence"]["arm"]).split(":")[0]
        arms[a] = arms.get(a, 0) + 1
    c2_key = bool(os.environ.get(C2_KEY_ENV)) if env is None else bool(env.get(C2_KEY_ENV))
    doc = {
        "generated_utc": now.isoformat(timespec="seconds"),
        "writer": "research/broker_signal_cells.py", "seat": SEAT,
        "rule": ("Broker-own tick volume, spread and swap repricings, and the retail crowd, as "
                 "point-in-time series and conditioner cells through existing families. A cell "
                 "is minted once in its life; an absent series is named, never filled."),
        "lag_hours": LAG_H,
        "activity": {"symbols_with_series": len(act_cols),
                     "columns": dict(sorted(act_cols.items())),
                     "unmeasured": act_unmeasured},
        "swaps": {"symbols_minted_on": swap_ok, "unmeasured": swap_unmeasured,
                  "panel_symbols": len(swaps)},
        "crowd": {
            "myfxbook": {"fetch": crowd_fetch, "symbols_live": crowd_ok,
                         "accruing": crowd_accruing, "terms": MYFXBOOK_TERMS,
                         "terms_note": (
                             "HELD until the terms are read verbatim on the box; the API page "
                             "reportedly asks that software built on it be free and caps the "
                             "free tier at 100 calls/day")},
            "collective2": {"status": UNMEASURED, "key_present": c2_key, "why": (
                "FAIL-CLOSED: the official API v4 exposes no sentiment or aggregated "
                "positioning endpoint, only per-strategy positions; a crowd series would mean "
                "bulk-reading third parties' strategy books under unconfirmed terms")}},
        "cells": {**cell_res, "by_arm": arms},
        "seconds": round(time.monotonic() - t0, 2),
    }
    if not dry_run:
        _write(state_path or STATE, state)
        _write(out or OUT, doc)
    return doc


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--once", action="store_true", help="one pass (the only mode)")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--offline", action="store_true")
    a = ap.parse_args(argv)
    doc = build(dry_run=a.dry_run, offline=a.offline)
    c = doc["cells"]
    print(f"broker_signal_cells: activity {doc['activity']['symbols_with_series']} sym, swaps "
          f"{len(doc['swaps']['symbols_minted_on'])} sym, crowd "
          f"{doc['crowd']['myfxbook']['fetch'].get('status')} "
          f"({len(doc['crowd']['myfxbook']['symbols_live'])} live); cells planned "
          f"{c['cells_planned']}, new {c['cells_new']}, donated {c['donated']} "
          f"({doc['seconds']}s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
