#!/usr/bin/env python3
"""GLOBAL FLOW -- who is forced, crowded or paid to trade, read from free public files.

Retail, institutional, dealer, central-bank, sovereign and cross-border flow, every region, as
point-in-time series that become exogenous_conditioner cells for the judge. Nothing here sizes
a trade: a series is a QUESTION the gauntlet answers, never an edge.

WHERE IT RUNS. `futures_state.build` calls `collect` once per hourly pass and mints these
series through its own once-in-a-lifetime cell door, so this module adds no hourly leg, no
registry path and no second minting clock. Rows live in `global_flow_sources.json` beside the
code: add a source there; a row whose adapter is `none` is a NAMED GAP with its reason.

SOURCES: snb_sight, gld_holdings, nse_part_oi, mof_weekly (see the rows).

HONEST ACCESS. Robots is read as a routing label (LAWS 5e: PUBLIC / PUBLIC_WITH_TERMS /
ACCESS_UNCLEAR, carried on each series); 401/403/429/451 is a hard stop recorded in state and
never retried; no login, key, captcha or paywall is touched. The cloud build cannot reach any
of these hosts, so every parser is written to the publisher's documented layout, tested on a
fixture, and its live yield is UNMEASURED until the box runs it. A parser that reads zero rows
says so in `notes` with the first bytes it saw, so the next pass can fix it rather than guess.
"""
from __future__ import annotations

import csv
import io
import json
import math
import re
import sys
import time
from collections.abc import Callable, Mapping
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

DESK = Path(__file__).resolve().parents[1]
ROOT = DESK.parent.parent
for _p in (str(DESK), str(DESK / "research"), str(ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

REGISTRY = DESK / "research" / "global_flow_sources.json"
RAW = DESK / "data" / "futures_state" / "raw" / "global_flow"
UA = "quant-research/1.0 (+https://github.com/kingdemond434-cpu/quant; global_flow)"
HARD_STOP = frozenset({401, 403, 429, 451})
MIN_ROWS = 30
NSE_DAYS_PER_PASS = 25
NSE_BACKFILL_DAYS = 520          # calendar days (~1.4 years of sessions)
FETCH_BUDGET_S = 300.0           # on top of futures_state's own budget


class HardStop(Exception):
    def __init__(self, code: int, url: str):
        super().__init__(f"HTTP {code}")
        self.code, self.url = code, url


class Missing(Exception):
    """404 / 410: the file does not exist (a holiday, an unpublished day). Not a refusal."""


def http_get(url: str, *, timeout: float = 40.0, max_bytes: int = 4_000_000) -> str:
    from libs.data import polite_fetch
    r = polite_fetch.get(url, headers={"User-Agent": UA}, timeout=timeout, retries=0,
                         max_bytes=max_bytes, leg="global_flow")
    if r.status in HARD_STOP:
        raise HardStop(int(r.status or 0), url)
    if r.status in (404, 410):
        raise Missing(url)
    if not r.ok:
        raise ConnectionError(r.error or f"HTTP {r.status}")
    return r.text


# ------------------------------------------------------------------------------ parsers (pure)

def _num(x: Any) -> float:
    try:
        s = str(x).strip().replace(",", "").replace('"', "")
        return float(s) if s not in ("", "-", "HOLIDAY", "NA", "N/A") else math.nan
    except ValueError:
        return math.nan


def parse_snb_cube(text: str) -> pd.DataFrame:
    """SNB data-portal CSV: metadata lines, then `Date;D0;Value` rows (semicolon, quoted).
    Returns one column per D0 member, indexed by the observation date."""
    rows = []
    started = False
    for line in text.splitlines():
        cells = [c.strip().strip('"') for c in line.split(";")]
        if not started:
            started = len(cells) >= 3 and cells[0].lower() == "date"
            continue
        if len(cells) >= 3 and re.match(r"\d{4}-\d{2}(-\d{2})?$", cells[0]):
            rows.append((cells[0], cells[1], _num(cells[-1])))
    if not rows:
        return pd.DataFrame()
    df = pd.DataFrame(rows, columns=["date", "dim", "v"])
    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    out = df.dropna(subset=["date"]).pivot_table(index="date", columns="dim", values="v",
                                                 aggfunc="last").sort_index()
    out.columns = [f"sight_{str(c).lower()}" for c in out.columns]
    return out


def parse_gld_archive(text: str) -> pd.DataFrame:
    """SPDR GLD archive CSV: a header row naming `Date` and `... Tonnes in the Trust`; dates
    like 18-Nov-2004; holiday rows say HOLIDAY. Returns tonnes and daily share volume."""
    lines = text.splitlines()
    hdr = next((i for i, ln in enumerate(lines) if "date" in ln.lower()
                and "tonnes" in ln.lower()), None)
    if hdr is None:
        return pd.DataFrame()
    df = pd.read_csv(io.StringIO("\n".join(lines[hdr:])), dtype=str, skipinitialspace=True)
    df.columns = [str(c).strip() for c in df.columns]
    dcol = next(c for c in df.columns if c.lower() == "date")
    tcol = next(c for c in df.columns if "tonnes" in c.lower())
    vcol = next((c for c in df.columns if "volume" in c.lower()), None)
    out = pd.DataFrame({"date": pd.to_datetime(df[dcol].str.strip(), format="%d-%b-%Y",
                                               errors="coerce"),
                        "tonnes": df[tcol].map(_num)})
    if vcol:
        out["share_volume"] = df[vcol].map(_num)
    out = out.dropna(subset=["date", "tonnes"]).set_index("date").sort_index()
    return out[~out.index.duplicated(keep="last")]


_NSE_COLS = {"future index long": "fi_l", "future index short": "fi_s",
             "future stock long": "fs_l", "future stock short": "fs_s",
             "option index call long": "oic_l", "option index put long": "oip_l",
             "option index call short": "oic_s", "option index put short": "oip_s"}


def parse_nse_participant_oi(text: str) -> dict[str, float]:
    """One day's participant-wise OI file -> per-class positioning ratios.

    For each of client (retail), fii, dii, pro:
        <cls>_fi_net   (index futures long - short) / (long + short)
        <cls>_fs_net   the same for stock futures
        <cls>_opt_tilt (index call long + put short - put long - call short) / their sum:
                       the class's directional options book, +1 all bullish
    and client_minus_fii_fi: retail against foreign index-futures positioning.
    """
    lines = [ln for ln in text.splitlines() if ln.strip()]
    hdr = next((i for i, ln in enumerate(lines) if ln.lower().lstrip('"').startswith(
        "client type")), None)
    if hdr is None:
        return {}
    head = [c.strip().strip('"').strip().lower() for c in lines[hdr].split(",")]
    idx = {key: head.index(name) for name, key in _NSE_COLS.items() if name in head}
    if len(idx) < len(_NSE_COLS):
        return {}
    out: dict[str, float] = {}
    for ln in lines[hdr + 1:]:
        cells = [c.strip().strip('"').strip() for c in ln.split(",")]
        cls = cells[0].lower()
        if cls not in ("client", "fii", "dii", "pro"):
            continue
        v = {k: _num(cells[i]) if i < len(cells) else math.nan for k, i in idx.items()}

        def ratio(a: float, b: float) -> float:
            return (a - b) / (a + b) if (a + b) > 0 else math.nan
        out[f"{cls}_fi_net"] = ratio(v["fi_l"], v["fi_s"])
        out[f"{cls}_fs_net"] = ratio(v["fs_l"], v["fs_s"])
        bull = v["oic_l"] + v["oip_s"]
        bear = v["oip_l"] + v["oic_s"]
        out[f"{cls}_opt_tilt"] = ratio(bull, bear)
    if "client_fi_net" in out and "fii_fi_net" in out:
        out["client_minus_fii_fi"] = out["client_fi_net"] - out["fii_fi_net"]
    return out


_WEEK_END = re.compile(r"(\d{4})[./-](\d{1,2})[./-](\d{1,2})\s*[~\uFF5E\-\u2013]\s*"
                       r"(?:(\d{4})[./-])?(\d{1,2})[./-](\d{1,2})")


def parse_mof_weekly(text: str) -> pd.DataFrame:
    """MoF weekly international transactions in securities (week.csv).

    Rows carry a week label `YYYY.M.D~M.D` (the year of the end date may be omitted) followed
    by net figures in 100 million yen. The FIRST SIX numeric cells of a row are read in the
    publisher's documented order: Japanese investors' net purchases of foreign equity, long-term
    debt, short-term debt; then foreign investors' net purchases of Japanese equity, long-term
    debt, short-term debt. Gross columns, when present, follow and are ignored. Index = week end.
    """
    names = ["jp_out_equity", "jp_out_ltdebt", "jp_out_stdebt",
             "fx_in_equity", "fx_in_ltdebt", "fx_in_stdebt"]
    recs = []
    for ln in text.splitlines():
        m = _WEEK_END.search(ln)
        if not m:
            continue
        y1, mo1, _d1, y2, mo2, d2 = m.groups()
        year = int(y2) if y2 else int(y1) + (1 if int(mo2) < int(mo1) else 0)
        try:
            end = pd.Timestamp(year=year, month=int(mo2), day=int(d2))
        except ValueError:
            continue
        cells = next(csv.reader([ln.replace("\t", ",")]))
        at = next((i for i, c in enumerate(cells) if _WEEK_END.search(c)), len(cells))
        nums = [_num(c) for c in cells[at + 1:] if c.strip() != ""]
        nums = [x for x in nums if np.isfinite(x)]
        if len(nums) >= 6:
            recs.append({"date": end, **dict(zip(names, nums[:6], strict=True))})
    if not recs:
        return pd.DataFrame()
    df = pd.DataFrame(recs).drop_duplicates("date", keep="last").set_index("date").sort_index()
    df["jp_out_total"] = df[["jp_out_equity", "jp_out_ltdebt"]].sum(axis=1)
    df["fx_in_total"] = df[["fx_in_equity", "fx_in_ltdebt"]].sum(axis=1)
    # Net yen pressure: foreign money in minus Japanese money out (+ = yen demand).
    df["net_yen_flow"] = df["fx_in_total"] - df["jp_out_total"]
    return df


def intervention_hazard(close: pd.Series, weak_side: float) -> pd.DataFrame:
    """Central-bank intervention hazard state for one pair, from its own daily closes.

    Interventions arrive after FAST, LARGE moves to EXTREME levels in the defended currency's
    weak direction (MoF 2022/2024 at USDJPY 145-162, SNB, CBRT, RBI, BoK). `weak_side` is +1
    when the pair RISING weakens the defended currency (USDJPY, USDKRW), -1 when falling does
    (EURCHF for the SNB's floor era). Every column is causal (trailing windows only):

        speed5 / speed20   signed 5- and 20-day log move over its trailing 1y daily vol * sqrt(n)
        ext252             signed position in the trailing 252-day range (+1 = weakest extreme)
        dd_from_ext        signed distance from the weak-side 252-day extreme, in vol units
        hazard             logistic(speed20 + 2 * ext252 - 1): one smooth score, a QUESTION for
                           the gauntlet (does price mean-revert / vol spike when it is high?)
    """
    c = pd.to_numeric(close, errors="coerce").dropna()
    r = np.log(c).diff()
    vol = r.rolling(252, min_periods=60).std()
    out = pd.DataFrame(index=c.index)
    for n in (5, 20):
        out[f"speed{n}"] = weak_side * np.log(c).diff(n) / (vol * np.sqrt(n))
    hi, lo = c.rolling(252, min_periods=60).max(), c.rolling(252, min_periods=60).min()
    pos = (2 * (c - lo) / (hi - lo).replace(0, np.nan)) - 1
    out["ext252"] = weak_side * pos
    edge = hi if weak_side > 0 else lo
    out["dd_from_ext"] = weak_side * np.log(c / edge) / vol
    out["hazard"] = 1 / (1 + np.exp(-(out["speed20"] + 2 * out["ext252"] - 1)))
    return out


# ------------------------------------------------------------------------------ collectors

def _raw(name: str) -> Path:
    return RAW / f"{name}.parquet"


def _load_raw(name: str) -> pd.DataFrame:
    p = _raw(name)
    return pd.read_parquet(p) if p.exists() else pd.DataFrame()


def _save_raw(name: str, df: pd.DataFrame) -> None:
    from research.futures_state import _atomic_parquet
    RAW.mkdir(parents=True, exist_ok=True)
    _atomic_parquet(_raw(name), df)


def _whole_file(src: Mapping[str, Any], get: Callable[..., str], parse: Callable[[str], Any],
                notes: list[dict[str, Any]]) -> pd.DataFrame:
    text = get(src["url"], max_bytes=int(src.get("max_bytes", 4_000_000)))
    df = parse(text)
    if df is None or len(df) == 0:
        notes.append({"source": src["id"], "status": "UNMEASURED",
                      "why": "parser read zero rows", "head": text[:300]})
        return pd.DataFrame()
    _save_raw(src["id"], df)
    return df


def _nse_days(src: Mapping[str, Any], get: Callable[..., str], state: dict[str, Any],
              notes: list[dict[str, Any]], today: date, deadline: float) -> pd.DataFrame:
    """Walk back from today, a bounded number of new trading days per pass; a 404 is a
    holiday or an unpublished day and is remembered so it is never asked again."""
    held = _load_raw(src["id"])
    seen = set(state.setdefault("global_flow_nse_seen", []))
    have = {d.strftime("%Y-%m-%d") for d in pd.to_datetime(held.index)} if len(held) else set()
    recs, asked = [], 0
    for back in range(1, NSE_BACKFILL_DAYS):
        d = today - timedelta(days=back)
        key = d.isoformat()
        if d.weekday() >= 5 or key in have or key in seen:
            continue
        if asked >= NSE_DAYS_PER_PASS or time.monotonic() > deadline:
            break
        asked += 1
        try:
            row = parse_nse_participant_oi(get(src["url"].format(ddmmyyyy=d.strftime("%d%m%Y"))))
        except Missing:
            seen.add(key)
            continue
        if row:
            recs.append({"date": pd.Timestamp(d), **row})
        else:
            seen.add(key)
            notes.append({"source": src["id"], "day": key, "status": "UNPARSED"})
    state["global_flow_nse_seen"] = sorted(seen)[-2000:]
    if recs:
        new = pd.DataFrame(recs).set_index("date")
        held = pd.concat([held, new]) if len(held) else new
        held = held[~held.index.duplicated(keep="last")].sort_index()
        _save_raw(src["id"], held)
    return held


PARSERS: dict[str, Callable[[str], pd.DataFrame]] = {
    "snb_cube": parse_snb_cube, "gld_archive": parse_gld_archive, "mof_weekly": parse_mof_weekly}


def _hazard(src: Mapping[str, Any], bars: Callable[[str], Any] | None,
            notes: list[dict[str, Any]]) -> pd.DataFrame:
    """Desk-bar derived: no network, so it runs offline too. One column block per pair."""
    if bars is None:
        return pd.DataFrame()
    cols = []
    for pr in src.get("pairs") or []:
        b = bars(str(pr["symbol"]))
        if b is None or len(b) == 0:
            notes.append({"source": src["id"], "symbol": pr["symbol"], "status": "NO_BARS"})
            continue
        idx = pd.DatetimeIndex(pd.to_datetime(b.index, utc=True)).tz_convert(None)
        daily = pd.Series(pd.to_numeric(b["close"], errors="coerce").to_numpy(),
                          index=idx).resample("1D").last().dropna()
        h = intervention_hazard(daily, float(pr.get("weak_side", 1)))
        cols.append(h.add_prefix(f"{str(pr['symbol']).lower()}_"))
    return pd.concat(cols, axis=1).sort_index() if cols else pd.DataFrame()


def collect(*, get: Callable[..., str] | None, state: dict[str, Any], notes: list[dict[str, Any]],
            get_text: Callable[[str], str] | None = None, now: datetime | None = None,
            budget: float | None = None, registry: Mapping[str, Any] | None = None,
            bars: Callable[[str], Any] | None = None
            ) -> tuple[dict[str, dict[str, Any]], dict[str, pd.DataFrame]]:
    """Every live row -> (built, frames) in futures_state's shape. `get=None` reads only what
    is already held (offline / dry passes)."""
    from research.futures_state import dynamics, robots_allow, stamped
    reg = registry if registry is not None else json.loads(REGISTRY.read_text(encoding="utf-8"))
    now = now or datetime.now(UTC)
    deadline = budget if budget is not None else time.monotonic() + 300.0
    stops = state.setdefault("hard_stops", {})
    built: dict[str, dict[str, Any]] = {}
    frames: dict[str, pd.DataFrame] = {}
    access: dict[str, str] = {}
    for src in reg.get("sources") or []:
        sid, adapter = str(src["id"]), str(src.get("adapter") or "none")
        if adapter == "none":
            continue
        df = pd.DataFrame()
        live = get is not None and f"gf_{sid}" not in stops and time.monotonic() < deadline
        if live and get_text is not None and src.get("url"):
            probe = src.get("robots_url") or src["url"].format(
                ddmmyyyy="01012024")
            # LAWS 5e: robots is a ROUTING LABEL, never a refusal (the #651 access_label
            # pattern). Only 401/403/429/451 or a WAF page stop a source (HardStop below).
            try:
                label = "PUBLIC" if robots_allow(probe, get_text) else "PUBLIC_WITH_TERMS"
            except Exception:
                label = "ACCESS_UNCLEAR"
            access[sid] = label
            if label != "PUBLIC":
                notes.append({"source": sid, "access_label": label,
                              "terms_note": "robots.txt disallows or is unreadable; read under"
                                            " LAWS 5e, nothing redistributed"})
        try:
            if live and adapter in PARSERS:
                df = _whole_file(src, get, PARSERS[adapter], notes)
            elif live and adapter == "nse_daily":
                df = _nse_days(src, get, state, notes, now.date(), deadline)
            elif adapter == "cb_hazard":
                df = _hazard(src, bars, notes)
        except HardStop as hs:
            stops[f"gf_{sid}"] = {"code": hs.code, "at": now.isoformat(timespec="seconds")}
        except Exception as exc:
            notes.append({"source": sid, "error": f"{type(exc).__name__}: {str(exc)[:80]}"})
        if df.empty:
            df = _load_raw(sid)
        if df.empty or len(df) < MIN_ROWS:
            notes.append({"source": sid, "status": "ACCRUING" if len(df) else "UNMEASURED",
                          "rows": len(df), "need": MIN_ROWS})
            continue
        df = df.sort_index()
        cols = [c for c in df.columns if c not in src.get("drop_cols", [])]
        feat = dynamics(df[cols], cols, window=int(src.get("window", 156)))
        for c in src.get("log_change_cols") or []:
            if c in df.columns:
                v = pd.to_numeric(df[c], errors="coerce")
                feat[f"{c}_logchg"] = np.log(v.where(v > 0)).diff()
        idx = pd.Series(pd.to_datetime(df.index))
        at = (idx.dt.tz_localize("UTC") if idx.dt.tz is None else idx).dt.normalize() + \
            pd.Timedelta(days=float(src.get("avail_lag_days", 1)),
                         hours=float(src.get("avail_hour_utc", 23)))
        at = declared_floor(src, idx, at)
        at = first_seen_floor(sid, idx, at, state, now)
        fid = f"flow_{sid}"
        frames[fid] = stamped(feat.reset_index(drop=True), at, fid, idx)
        built[fid] = {"targets": list(src.get("targets") or []), "kind": f"flow_{src['class']}",
                      "region": src.get("region"), "rows": len(df),
                      "access_label": access.get(sid, "UNREAD_THIS_PASS"),
                      "last_event": str(idx.max()), "why": src.get("why", "")}
    return built, frames


def declared_floor(src: Mapping[str, Any], idx: pd.Series, at: pd.Series) -> pd.Series:
    """A source the desk's PIT registry already declares (`pit_source` on the row, e.g. GLD as
    spdr_gld_holdings) is never stamped earlier than valid time + its data_os.declared_lag: one
    registry owns each source's publication lag, and this module can only be later than it."""
    name = src.get("pit_source")
    if not name:
        return at
    from libs.tiers import data_os
    lag = data_os.declared_lag(str(name))
    if lag is None:
        return at
    valid = idx.dt.tz_localize("UTC") if idx.dt.tz is None else idx
    floor = valid + pd.Timedelta(seconds=float(lag["lag_s"]))
    return pd.Series(np.maximum(at.to_numpy(), floor.to_numpy()), index=at.index)


FIRST_SEEN_DAYS = 14


def first_seen_floor(sid: str, idx: pd.Series, at: pd.Series, state: dict[str, Any],
                     now: datetime) -> pd.Series:
    """A rule-derived publication time is a GUESS; the pass that first held the row is a FACT.
    For any row whose rule time is within FIRST_SEEN_DAYS of the pass that first saw it, the
    availability is max(rule, first seen): a late release (a Japanese holiday week) or a snapshot
    fetched before its own rule hour can never be stamped earlier than it was observed. Older
    rows (the back-fill) keep the rule time. First-seen stamps persist in state, so a row's
    stamp never moves on a later pass."""
    seen = state.setdefault("global_flow_first_seen", {}).setdefault(sid, {})
    now_ts = pd.Timestamp(now).tz_convert("UTC") if pd.Timestamp(now).tzinfo else \
        pd.Timestamp(now).tz_localize("UTC")
    out = []
    for d, a in zip(idx, at, strict=True):
        key = pd.Timestamp(d).strftime("%Y-%m-%d")
        if key not in seen:
            seen[key] = now_ts.isoformat() if now_ts - a < pd.Timedelta(days=FIRST_SEEN_DAYS) \
                else None
        fs = seen[key]
        out.append(max(a, pd.Timestamp(fs)) if fs else a)
    return pd.Series(out, index=at.index)


def coverage(registry: Mapping[str, Any] | None = None) -> dict[str, Any]:
    """The flow map: every (class, region) cell, what feeds it, and what is still a gap."""
    reg = registry if registry is not None else json.loads(REGISTRY.read_text(encoding="utf-8"))
    rows = [*(reg.get("sources") or []), *(reg.get("already_live") or [])]
    by: dict[str, dict[str, list[str]]] = {}
    for r in rows:
        status = "gap" if r.get("adapter") == "none" else "live"
        by.setdefault(r["class"], {}).setdefault(r.get("region", "global"), []).append(
            f"{r['id']}:{status}")
    gaps = [{"id": r["id"], "class": r["class"], "region": r.get("region"),
             "blocked_by": r.get("blocked_by", "")} for r in reg.get("sources") or []
            if r.get("adapter") == "none"]
    unsearched = [f"{c}|{g}" for c in reg.get("player_classes") or []
                  for g in reg.get("regions") or [] if g not in by.get(c, {})]
    n_cells = len(reg.get("player_classes") or []) * len(reg.get("regions") or [])
    return {"by_class_region": by, "gaps": gaps, "unsearched": unsearched,
            "n_live": sum(1 for r in rows if r.get("adapter") != "none"), "n_gaps": len(gaps),
            "grid_cells": n_cells, "grid_covered": n_cells - len(unsearched)}


if __name__ == "__main__":
    print(json.dumps(coverage(), indent=1))
