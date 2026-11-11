#!/usr/bin/env python3
"""CFD-VS-REFERENCE BASIS CELLS (B10, approved 2026-10-13) -- the gap between the broker's CFD and
the public reference it is meant to track, as a dislocation that mean-reverts.

    python desks/mt5/research/basis_cells.py --once
    python desks/mt5/research/basis_cells.py --once --dry-run    # build, mint nothing
    python desks/mt5/research/basis_cells.py --once --offline    # held reference only

THE CLAIM. A Fusion CFD is quoted by the broker off its own hedge (a front future, a cash index,
a spot book). The difference between that quote and the public reference -- the CFD's log price
at the reference's own fixing minute, minus the log reference -- is roll yield, financing and the
broker's skew plus a DISLOCATION. The cell bets the dislocation closes: when the basis is at an
extreme of its own history the CFD is rich (or cheap) and is faded (`exogenous_conditioner`,
`side_when_high=-1`), on its LEVEL and, separately, on a sudden CHANGE of it (two claims: a slow
drift of the basis is carry, a jump is a dislocation).

WHAT THE DESK HOLDS, AND WHY MOST PAIRS ARE UNMEASURED. Measured against the repo 2026-11-11:
`futures_state_sources.json` marks every public futures-price venue it knows as unusable for a
live input -- CME settlements HELD (terms restrict automated access), Yahoo futures IDEAS_ONLY,
EIA's NYMEX table DISCONTINUED 2024-04-05. There is therefore NO free, terms-clean daily FUTURES
reference, and no CFD-vs-future pair is minted. What does exist is the public SPOT reference on
FRED, with an official API and stated terms, so the basis here is CFD-vs-SPOT where the spot is
public-domain or citation-only (`PAIRS`), and every other pair is named with its reason in
`NOT_MINTED`: gold and silver (FRED's LBMA series were withdrawn in 2022; LBMA prices are
licensed), the European indices (no open-terms daily reference), the S&P 500 and Dow (S&P Dow
Jones Indices forbids reproduction without permission), the Treasury CFDs (they quote a note
FUTURE's price and H.15 publishes a yield: converting one into the other needs a CTD/duration
model, which would be a proxy, so it is not built).

THE CLOCK. The reference is a value at a wall-clock minute in its own market (`at`, `tz`). The
CFD is read from the H1 bar the broker stamped at that minute: broker stamps are New York + 7 h
(`libs.regime.session_clock`), so the bar label is the reference minute converted to New York and
shifted seven hours, floored to the hour, and the bar's OPEN is the price at that hour (at most
30 minutes before the WTI / gas settle anchor; exact for the Nasdaq-100 16:00 close). A day the
broker has no bar for is dropped, never interpolated. Each row is AVAILABLE when FRED publishes
the reference -- the next business day 23:00 UTC (`futures_state.daily_available`) -- and every
cell adds `lag_hours=3` for the broker clock on top of that.

THE DOOR AND THE TRIAL COUNT are `broker_signal_cells.mint`'s: one intake row per cell through
`proposer_common.donate`, each minted once in its life; a pair whose reference is stale, unfetched
or short is named in the report and mints nothing.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
import urllib.parse
from collections.abc import Callable, Mapping
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

from research import broker_signal_cells as BSC  # noqa: E402

SEAT = "basis_cells"
RAW = DESK / "data" / "broker_signals" / "basis_raw"
STATE = DESK / "data" / "broker_signals" / "basis_state.json"
OUT = DESK / "reports" / "BASIS_CELLS.json"
UNMEASURED = "UNMEASURED"
FRED_URL = "https://api.stlouisfed.org/fred/series/observations"
FRED_KEY_ENV = ("FRED_API_KEY", "FRED_KEY")
#: The reference is daily; re-read it at most this often.
REFETCH_S = 20 * 3600
#: A reference silent for longer than this is STALE and mints nothing.
STALE_DAYS = 10
HISTORY_START = "2018-01-01"
CHARTS: tuple[str, ...] = ("H1", "H4")
TRANSFORMS: tuple[str, ...] = ("level_z", "delta_z")

#: CFD -> its public spot reference on FRED, at the reference's own fixing minute.
PAIRS: tuple[dict[str, str], ...] = (
    {"symbol": "XTIUSD", "ref": "DCOILWTICO", "tz": "America/New_York", "at": "14:30",
     "terms": "PUBLIC_DOMAIN", "note": "EIA WTI Cushing spot; anchor the NYMEX settle window"},
    {"symbol": "XBRUSD", "ref": "DCOILBRENTEU", "tz": "Europe/London", "at": "16:30",
     "terms": "PUBLIC_DOMAIN", "note": "EIA Europe Brent spot FOB; anchor the London close"},
    {"symbol": "XNGUSD", "ref": "DHHNGSP", "tz": "America/New_York", "at": "14:30",
     "terms": "PUBLIC_DOMAIN",
     "note": "EIA Henry Hub spot is a day-ahead index; the NYMEX close anchor adds timing noise"},
    {"symbol": "NAS100", "ref": "NASDAQ100", "tz": "America/New_York", "at": "16:00",
     "terms": "CITATION_REQUIRED", "note": "Nasdaq-100 cash close; FRED asks for citation"},
)

#: Pairs named and NOT minted, each with its reason (L1.28a: absence is a verdict, not a zero).
NOT_MINTED: dict[str, str] = {
    "XAUUSD": "no free terms-clean daily gold reference: FRED's LBMA fix withdrawn 2022, LBMA "
              "prices licensed, COMEX settlements HELD",
    "XAGUSD": "no free terms-clean daily silver reference (as XAUUSD)",
    "XAUEUR": "no free terms-clean daily gold reference", "XAUAUD": "as XAUEUR",
    "XAGEUR": "as XAGUSD",
    "US500": "HELD: FRED SP500 is S&P Dow Jones Indices data, reproduction prohibited without "
             "permission", "US30": "HELD: FRED DJIA, same S&P Dow Jones Indices terms",
    "GER40": "no open-terms daily DAX reference", "UK100": "no open-terms daily FTSE reference",
    "EUSTX50": "no open-terms daily Euro Stoxx 50 reference",
    "UST10Y": "the CFD quotes a note future's price, H.15 a yield: converting needs a CTD model "
              "(a proxy), not built", "UST05Y": "as UST10Y",
    "*futures*": "no CFD-vs-FUTURE pair: CME HELD, Yahoo IDEAS_ONLY, EIA NYMEX DISCONTINUED "
                 "(futures_state_sources.json)",
}


def fred_key(env: Mapping[str, str] | None = None) -> str | None:
    e = env if env is not None else os.environ
    for k in FRED_KEY_ENV:
        if str(e.get(k) or "").strip():
            return str(e[k]).strip()
    if env is not None:
        return None
    try:
        from research.fetch_alfred import api_key
        return api_key()
    except Exception:
        return None


def fetch_reference(series: str, key: str, *,
                    get: Callable[[str], tuple[int | None, str, str]] | None = None,
                    robots: Callable[[str], str | None] | None = None
                    ) -> tuple[pd.DataFrame | None, str]:
    """(date,value) observations, or (None, reason). Robots first; one attempt; key never shown."""
    refused = (robots or BSC._robots_refusal)(FRED_URL)
    if refused:
        return None, f"REFUSED_BY_ROBOTS: {refused}"
    q = urllib.parse.urlencode({"series_id": series, "api_key": key, "file_type": "json",
                                "observation_start": HISTORY_START})
    status, body, err = (get or BSC._http_get)(f"{FRED_URL}?{q}")
    if status in BSC.HARD_STOP:
        return None, f"HARD_STOP: HTTP {status}"
    if err:
        return None, f"FETCH_ERROR: {err}"
    try:
        rows = (json.loads(body) or {}).get("observations") or []
    except (ValueError, AttributeError):
        return None, "ROUTE_CHANGED: body is not FRED JSON"
    f = pd.DataFrame(rows)
    if f.empty or "date" not in f.columns:
        return None, "ROUTE_CHANGED: no observations"
    f = pd.DataFrame({"date": f["date"].astype(str),
                      "value": pd.to_numeric(f["value"], errors="coerce")})
    return f.dropna().reset_index(drop=True), "ok"


def cfd_at_reference(bars: pd.DataFrame, dates: pd.Series, at: str, tz: str) -> pd.Series:
    """The CFD's price at the reference minute of each date: the OPEN of the broker H1 bar that
    contains it (New York + 7 h, floored). NaN where the broker has no such bar."""
    from libs.regime.session_clock import SERVER_SHIFT_H, SERVER_TZ
    hh, mm = (int(x) for x in at.split(":"))
    local = (pd.to_datetime(dates) + pd.Timedelta(hours=hh, minutes=mm)).dt.tz_localize(
        tz, ambiguous="NaT", nonexistent="NaT")
    stamp = (local.dt.tz_convert(SERVER_TZ).dt.tz_localize(None)
             + pd.Timedelta(hours=SERVER_SHIFT_H)).dt.floor("h").dt.tz_localize("UTC")
    opens = pd.to_numeric(bars["open"], errors="coerce")
    opens = opens[~opens.index.duplicated(keep="last")]
    return pd.Series(opens.reindex(pd.DatetimeIndex(stamp)).to_numpy(), index=dates.index)


def basis_frame(sym: str, ref: pd.DataFrame, bars: pd.DataFrame, pair: Mapping[str, str]
                ) -> pd.DataFrame:
    """basis_log = ln CFD - ln reference, per reference date the broker quoted, stamped PIT."""
    from research.futures_state import daily_available
    r = ref[ref["value"] > 0].copy()
    cfd = cfd_at_reference(bars, r["date"], pair["at"], pair["tz"])
    r["cfd"] = cfd.to_numpy()
    r = r[r["cfd"] > 0]
    out = pd.DataFrame({"basis_log": np.log(r["cfd"].to_numpy()) - np.log(r["value"].to_numpy())})
    out["event_time"] = pd.to_datetime(r["date"].to_numpy(), utc=True)
    out["available_time"] = daily_available(r["date"]).to_numpy()
    out["source_id"] = f"basis_{sym}"
    return out.dropna(subset=["basis_log", "available_time"]).reset_index(drop=True)


def plan_cells(live: list[str]) -> list[dict[str, Any]]:
    out = []
    for sym in sorted(live):
        sid = f"basis_{sym}"
        for tf in TRANSFORMS:
            what = ("the CFD sits at an extreme of its own basis to the public reference: the "
                    "dislocation closes" if tf == "level_z" else
                    "the basis to the public reference jumped: a dislocation, not carry, and it "
                    "reverts")
            for chart in CHARTS:
                out.append(BSC._cell(sym, "exogenous_conditioner",
                                     {"source": sid, "signal": "basis_log", "transform": tf,
                                      "threshold": 1.5, "side_when_high": -1},
                                     chart, sid, what, f"basis:{tf}", seat=SEAT,
                                     culture=("venue/broker", "dealer_hedged_cfd")))
    return out


def build(*, dry_run: bool = False, offline: bool = False, now: datetime | None = None,
          universe_dir: Path | None = None, series_root: Path | None = None,
          raw_dir: Path | None = None, state_path: Path | None = None, out: Path | None = None,
          get: Callable[[str], tuple[int | None, str, str]] | None = None,
          robots: Callable[[str], str | None] | None = None,
          env: Mapping[str, str] | None = None,
          universe: set[str] | None = None,
          donate: Callable[..., Path | None] | None = None,
          counts: Callable[[], dict[str, Any]] | None = None) -> dict[str, Any]:
    t0 = time.monotonic()
    now = now or datetime.now(UTC)
    state = BSC._read(state_path or STATE, {}) or {}
    raw = raw_dir or RAW
    uni = universe if universe is not None else set(BSC.lane_symbols())
    key = None if (offline or dry_run) else fred_key(env)
    pairs: dict[str, Any] = {}
    live: list[str] = []
    for pair in PAIRS:
        sym, ref_id = pair["symbol"], pair["ref"]
        row: dict[str, Any] = {"reference": f"FRED {ref_id}", "terms": pair["terms"],
                               "fix": f"{pair['at']} {pair['tz']}", "note": pair["note"]}
        pairs[sym] = row
        if sym not in uni:
            row["status"] = "NOT_QUOTED"
            continue
        held = raw / f"{ref_id}.json"
        stops = state.setdefault("hard_stops", {})
        last = pd.to_datetime((state.get("fetched") or {}).get(ref_id), utc=True, errors="coerce")
        due = pd.isna(last) or (pd.Timestamp(now) - last).total_seconds() >= REFETCH_S
        if ref_id in stops:
            row["fetch"] = f"HARD_STOP held: {stops[ref_id]}"
        elif key and due:
            ref, why = fetch_reference(ref_id, key, get=get, robots=robots)
            row["fetch"] = why
            if why.startswith("HARD_STOP"):
                stops[ref_id] = why
            if ref is not None and not dry_run:
                raw.mkdir(parents=True, exist_ok=True)
                held.write_text(ref.to_json(orient="records"), encoding="utf-8")
                state.setdefault("fetched", {})[ref_id] = now.isoformat(timespec="seconds")
        else:
            row["fetch"] = ("NEEDS_KEY: no FRED key on this host" if not key and not offline
                            and not dry_run else "held reference served")
        try:
            ref = pd.read_json(held, orient="records", dtype={"date": str}) \
                if held.exists() else None
        except ValueError:
            ref = None
        if ref is None or ref.empty:
            row["status"] = UNMEASURED
            row["why"] = "no reference observations held on this host"
            continue
        ref["date"] = ref["date"].astype(str).str[:10]
        newest = pd.Timestamp(ref["date"].max(), tz="UTC")
        if (pd.Timestamp(now) - newest).days > STALE_DAYS:
            row["status"] = "STALE"
            row["why"] = f"reference last dated {newest.date()}"
            continue
        bars = BSC._bars(sym, universe_dir)
        if bars is None or "open" not in bars.columns:
            row["status"] = UNMEASURED
            row["why"] = "no H1 bars for the CFD on this host"
            continue
        f = basis_frame(sym, ref, bars, pair)
        row["rows"] = len(f)
        if len(f) < BSC.MIN_ROWS:
            row["status"] = "ACCRUING"
            row["why"] = f"{len(f)} dated basis rows, below {BSC.MIN_ROWS}"
            continue
        last_b = float(f["basis_log"].iloc[-1])
        hist = f["basis_log"].tail(250)
        row.update({"status": "LIVE", "basis_log_last": round(last_b, 6),
                    "basis_z_last": (round(float((last_b - hist.mean()) / hist.std(ddof=0)), 3)
                                     if float(hist.std(ddof=0) or 0) > 0 else None),
                    "as_of": str(f["event_time"].iloc[-1].date())})
        live.append(sym)
        if not dry_run:
            BSC.write_series(f"basis_{sym}", f, series_root)
    cells = plan_cells(live)
    res = BSC.mint(cells, state, dry_run=dry_run, seat=SEAT, donate=donate, counts=counts)
    doc = {
        "generated_utc": now.isoformat(timespec="seconds"),
        "writer": "research/basis_cells.py", "seat": SEAT,
        "rule": ("CFD-vs-public-reference basis as a mean-reverting dislocation, through "
                 "exogenous_conditioner. Only public, terms-clean references; every other pair is "
                 "named with its reason, never proxied."),
        "pairs": pairs, "live": live, "not_minted": NOT_MINTED, "cells": res,
        "seconds": round(time.monotonic() - t0, 2),
    }
    if not dry_run:
        BSC._write(state_path or STATE, state)
        BSC._write(out or OUT, doc)
    return doc


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--once", action="store_true", help="one pass (the only mode)")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--offline", action="store_true")
    a = ap.parse_args(argv)
    doc = build(dry_run=a.dry_run, offline=a.offline)
    st = {s: r.get("status") for s, r in doc["pairs"].items()}
    c = doc["cells"]
    print(f"basis_cells: {st}; cells planned {c['cells_planned']}, new {c['cells_new']}, "
          f"donated {c['donated']} ({doc['seconds']}s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
