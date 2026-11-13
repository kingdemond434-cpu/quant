#!/usr/bin/env python3
"""ADAPTER DATA -- the hourly leg that makes the federation's data-source adapters feed cells.

Audit 2026-11-13: the `openbb` adapter was an import probe and no OpenBB provider fed the desk.
This leg fetches the keyless OECD provider OpenBB wraps (composite leading indicators, CLI)
DIRECTLY from the OECD SDMX REST API and carries it through the same path every other exogenous
series takes to the judge:

  1. HONEST ACCESS. One User-Agent that names the desk, the host's robots.txt read with it (an
     unreadable policy is NOT a yes; a 404 is), no retries, and 401/403/429/451 is a HARD STOP
     written to state and never retried by this leg. At most one request per pass for the data,
     and only when the last good read is older than REFRESH_H (the series is monthly).
  2. POINT IN TIME. OECD revises the CLI and publishes no vintages, so the FIRST value the desk
     saw for each (economy, month) is kept for ever; a later different value is counted as a
     revision and never written over the first. A month present in the first-ever fetch is
     backfill and stamped period end + LAG_DAYS; a month first seen later is stamped
     max(period end + LAG_DAYS, first_seen). `revision_safe: false` rides in the report.
  3. SERIES. One lake file per economy, `data/lake/series/oecd_cli_<eco>.parquet`, in the frame
     `mt5desk.family_exogenous_conditioner` loads (available_time + level / change /
     acceleration / percentile columns, from `research.futures_state.dynamics`). DataHub
     contract `oecd.cli` (libs/data/datahub_adapters.py) serves the same files.
  4. CELLS. Every (column x transform x target x chart) on the MT5 instruments the economy
     informs becomes ONE `exogenous_conditioner` candidate through
     `libs.moat.registry.enqueue_candidate`, minted once in its life (state keeps the hash) so
     trials are charged when a rule is minted and never inflated by re-minting.

ARTIFACT `reports/ADAPTER_DATA.json`. Errors are published as exception TYPE NAMES only, never
free text or a path (a published report must not carry a URL with a token or a box path).

    python desks/mt5/research/adapter_data.py --once [--offline] [--dry-run]
"""
from __future__ import annotations

import argparse
import csv
import io
import json
import logging
import os
import sys
import time
import urllib.parse
import urllib.robotparser
from collections.abc import Callable, Mapping
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

DESK = Path(__file__).resolve().parents[1]
ROOT = DESK.parent.parent
for _p in (str(DESK), str(DESK / "research"), str(ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

_LOG = logging.getLogger(__name__)

STATE = DESK / "data" / "adapter_data" / "state.json"
SERIES = DESK / "data" / "lake" / "series"
UNIVERSE = DESK / "data" / "universe" / "universe.json"
OUT = DESK / "reports" / "ADAPTER_DATA.json"

UA = "quant-research/1.0 (+https://github.com/kingdemond434-cpu/quant; adapter_data)"
HARD_STOP = frozenset({401, 403, 429, 451})
REFRESH_H = 24.0
LAG_DAYS = 45
MIN_ROWS = 30
MAX_MINT_PER_PASS = 600
GENERATOR = "adapter_data"

#: OECD economy -> the MT5 instruments its leading indicator informs (filtered against the
#: universe registry at mint time; an unquoted target is reported, never minted).
ECONOMIES: dict[str, tuple[str, ...]] = {
    "USA": ("US500", "NAS100", "US30", "XAUUSD"),
    "JPN": ("JPN225", "USDJPY"),
    "DEU": ("GER40", "EURUSD"),
    "FRA": ("FRA40", "EURUSD"),
    "GBR": ("UK100", "GBPUSD"),
    "AUS": ("AUS200", "AUDUSD"),
    "CAN": ("CA60", "USDCAD"),
    "CHN": ("USDCNH", "XCUUSD", "AUDUSD", "HK50"),
}
#: OECD.SDD.STES DF_CLI, key REF_AREA.FREQ.MEASURE.UNIT.ACTIVITY.ADJUSTMENT.TRANSFORMATION.
#: TIME_HORIZ.METHODOLOGY -- monthly, LI (leading indicator), AA (amplitude adjusted), H
#: (the OECD's harmonised methodology). SDMX-CSV carries REF_AREA, TIME_PERIOD and OBS_VALUE.
CLI_URL = ("https://sdmx.oecd.org/public/rest/data/OECD.SDD.STES,DSD_STES@DF_CLI,/"
           "{areas}.M.LI...AA...H?startPeriod=2000-01&format=csvfile")


class HardStop(Exception):
    def __init__(self, code: int) -> None:
        super().__init__(f"HTTP {code}")
        self.code = code


class FetchError(Exception):
    def __init__(self, code: int | None) -> None:
        super().__init__(f"HTTP {code}")
        self.code = code


def _now() -> datetime:
    return datetime.now(UTC)


def _read(p: Path, default: Any) -> Any:
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return default


def _replace(tmp: Path, p: Path) -> None:
    """os.replace with the Windows fallback (a destination held open raises PermissionError)."""
    try:
        os.replace(tmp, p)
    except PermissionError:
        p.unlink(missing_ok=True)
        os.replace(tmp, p)


def _write(p: Path, doc: Any) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_suffix(p.suffix + ".tmp")
    tmp.write_text(json.dumps(doc, indent=1, default=str), encoding="utf-8")
    _replace(tmp, p)


def http_get(url: str, accept: str = "text/csv,*/*;q=0.5", timeout: float = 60.0) -> str:
    """One honest GET through the desk's polite fetcher; retries off, refusals are hard."""
    from libs.data import polite_fetch
    r = polite_fetch.get(url, headers={"User-Agent": UA, "Accept": accept}, timeout=timeout,
                         retries=0, leg=GENERATOR)
    if r.status in HARD_STOP:
        raise HardStop(int(r.status or 0))
    if not r.ok:
        raise FetchError(r.status)
    return str(r.text)


def robots_allow(url: str, get: Callable[[str], str]) -> bool:
    """robots.txt read with our own UA: a 404 allows, any other failure does NOT."""
    p = urllib.parse.urlsplit(url)
    rp = urllib.robotparser.RobotFileParser()
    try:
        rp.parse(get(f"{p.scheme}://{p.netloc}/robots.txt").splitlines())
    except FetchError as exc:
        return exc.code == 404
    except HardStop:
        return False
    return rp.can_fetch(UA, url)


def parse_sdmx_csv(text: str) -> dict[str, dict[str, float]]:
    """SDMX-CSV -> {economy: {YYYY-MM: value}}. Columns are found by name, case-insensitive."""
    rows = csv.DictReader(io.StringIO(text))
    out: dict[str, dict[str, float]] = {}
    for r in rows:
        k = {str(a).strip().upper(): b for a, b in r.items() if a is not None}
        area, period, val = k.get("REF_AREA"), k.get("TIME_PERIOD"), k.get("OBS_VALUE")
        if not area or not period or val in (None, ""):
            continue
        try:
            out.setdefault(str(area), {})[str(period)[:7]] = float(str(val))
        except ValueError:
            continue
    return out


def period_end(period: str) -> datetime:
    y, m = int(period[:4]), int(period[5:7])
    first_next = datetime(y + (m == 12), m % 12 + 1, 1, tzinfo=UTC)
    return first_next - timedelta(seconds=1)


def merge(state: dict[str, Any], fresh: Mapping[str, Mapping[str, float]],
          now: datetime) -> dict[str, int]:
    """Fold a fetch into the first-vintage store. Returns counts of new, kept and revised."""
    held = state.setdefault("obs", {})
    backfill = not held
    new = revised = 0
    for eco, series in fresh.items():
        if eco not in ECONOMIES:
            continue
        mine = held.setdefault(eco, {})
        for period, val in series.items():
            if period in mine:
                if abs(float(mine[period]["value"]) - val) > 1e-9:
                    revised += 1
                continue
            base = period_end(period) + timedelta(days=LAG_DAYS)
            avail = base if backfill else max(base, now)
            mine[period] = {"value": val, "first_seen": now.isoformat(timespec="seconds"),
                            "available_time": avail.isoformat(timespec="seconds")}
            new += 1
    return {"new": new, "revised_not_written": revised, "backfill": int(backfill)}


def frames(state: Mapping[str, Any]) -> dict[str, Any]:
    """One stamped feature frame per economy, from the first-vintage store."""
    import pandas as pd
    from research.futures_state import dynamics, stamped
    out: dict[str, Any] = {}
    for eco, series in (state.get("obs") or {}).items():
        if len(series) < MIN_ROWS:
            continue
        periods = sorted(series)
        df = pd.DataFrame({"cli": [float(series[p]["value"]) for p in periods]})
        f = dynamics(df, ["cli"])
        sid = f"oecd_cli_{eco.lower()}"
        out[sid] = stamped(f, pd.Series([series[p]["available_time"] for p in periods]), sid,
                           event_time=pd.Series([period_end(p).isoformat() for p in periods]))
    return out


def _universe() -> frozenset[str]:
    doc = _read(UNIVERSE, {})
    return frozenset(str(k) for k in doc) if isinstance(doc, dict) else frozenset()


def mint(frames_: Mapping[str, Any], universe: frozenset[str], state: dict[str, Any], *,
         enqueue: Callable[..., tuple[str, bool]] | None,
         limit: int = MAX_MINT_PER_PASS) -> dict[str, Any]:
    """The next `limit` unminted cells, each minted once in its life."""
    from research.futures_state import cell_hash, cell_plan
    built = {sid: {"targets": list(ECONOMIES[sid.rsplit("_", 1)[-1].upper()]),
                   "kind": "oecd_cli"} for sid in frames_}
    plan = cell_plan(built, frames_, universe)
    minted = set(state.get("minted") or [])
    new = 0
    errors: dict[str, int] = {}
    by_series: dict[str, int] = {}
    for sid, col, tf, sym, chart in plan:
        h = cell_hash(sid, col, tf, sym, chart)
        if h in minted or enqueue is None or new >= limit:
            continue
        eco = sid.rsplit("_", 1)[-1].upper()
        mech = (f"the OECD composite leading indicator for {eco} turns before activity; a turn "
                f"in it is information {sym}'s price has not yet absorbed when growth "
                f"expectations reprice slowly across the publication lag")
        try:
            enqueue(family="exogenous_conditioner", symbol=sym,
                    params={"source": sid, "signal": col, "transform": tf},
                    origin=GENERATOR, mechanism=mech, chart=chart, horizon=chart,
                    source_id=sid, generator=GENERATOR, department="information",
                    asset_class="", transformation="oecd_cli_feature",
                    required_data=[f"desks/mt5/data/lake/series/{sid}.parquet"],
                    pit_status="STAMPED", causal_rationale=mech,
                    falsifier=(f"the {tf} of {sid}.{col} has no measurable relation to {sym} "
                               f"at {chart} out of sample"))
        except Exception as exc:  # noqa: BLE001 -- counted by type, the pass continues
            errors[type(exc).__name__] = errors.get(type(exc).__name__, 0) + 1
            continue
        minted.add(h)
        new += 1
        by_series[sid] = by_series.get(sid, 0) + 1
    state["minted"] = sorted(minted)
    unquoted = sorted({t for sid in frames_ for t in built[sid]["targets"] if t not in universe})
    return {"cells_planned": len(plan), "cells_minted_this_pass": new,
            "cells_minted_total": len(minted),
            "cells_queued": len({cell_hash(*r) for r in plan} - minted),
            "minted_by_series": by_series, "unquoted_targets": unquoted, "errors": errors}


def due(state: Mapping[str, Any], now: datetime) -> bool:
    last = state.get("last_success_at")
    if not last:
        return True
    try:
        return now - datetime.fromisoformat(str(last)) >= timedelta(hours=REFRESH_H)
    except ValueError:
        return True


def build(*, offline: bool = False, dry_run: bool = False,
          get: Callable[[str], str] | None = None,
          enqueue: Callable[..., tuple[str, bool]] | None = None,
          state_path: Path = STATE, series_dir: Path = SERIES,
          universe: frozenset[str] | None = None) -> dict[str, Any]:
    t0 = time.monotonic()
    now = _now()
    state = _read(state_path, {}) or {}
    fetch = get or http_get
    url = CLI_URL.format(areas="+".join(ECONOMIES))
    access: dict[str, Any] = {"url_host": urllib.parse.urlsplit(url).netloc}
    if state.get("hard_stop"):
        access["status"] = "HARD_STOP"
        access["code"] = state["hard_stop"].get("code")
    elif offline:
        access["status"] = "OFFLINE"
    elif not due(state, now):
        access["status"] = "NOT_DUE"
    else:
        try:
            if not robots_allow(url, fetch):
                access["status"] = "ROBOTS_DISALLOW"
            else:
                fresh = parse_sdmx_csv(fetch(url))
                access["status"] = "FETCHED" if fresh else "EMPTY"
                access["economies"] = sorted(fresh)
                access.update(merge(state, fresh, now))
                if fresh:
                    state["last_success_at"] = now.isoformat(timespec="seconds")
        except HardStop as exc:
            state["hard_stop"] = {"code": exc.code, "at": now.isoformat(timespec="seconds")}
            access["status"] = "HARD_STOP"
            access["code"] = exc.code
        except Exception as exc:  # noqa: BLE001 -- the type name is the published reason
            _LOG.warning("adapter_data fetch failed: %s", exc)
            access["status"] = "UNMEASURED"
            access["error_type"] = type(exc).__name__
        state["last_attempt_at"] = now.isoformat(timespec="seconds")
    fr = frames(state)
    if not dry_run:
        for sid, f in fr.items():
            series_dir.mkdir(parents=True, exist_ok=True)
            p = series_dir / f"{sid}.parquet"
            tmp = p.with_suffix(".parquet.tmp")
            f.to_parquet(tmp, index=False)
            _replace(tmp, p)
    enq = enqueue
    registry_note = ""
    if enq is None and not dry_run:
        try:
            from libs.moat.registry import enqueue_candidate
            enq = enqueue_candidate
        except Exception as exc:  # noqa: BLE001
            registry_note = type(exc).__name__
    cells = mint(fr, universe if universe is not None else _universe(), state,
                 enqueue=None if dry_run else enq)
    held = state.get("obs") or {}
    doc = {
        "generated_utc": now.isoformat(timespec="seconds"),
        "adapter": "openbb", "contract": "oecd.cli", "clock": "hourly_cycle:adapter_data",
        "source": "OECD SDMX REST, DF_CLI (the keyless provider OpenBB's oecd extension wraps)",
        "licence": "OECD data: CC BY 4.0, attribute the OECD",
        "revision_safe": False,
        "pit_rule": (f"first vintage kept; backfill stamped period end + {LAG_DAYS}d, later "
                     f"months max(that, first seen)"),
        "access": access,
        "held": {eco: {"months": len(v), "last_period": max(v) if v else None}
                 for eco, v in held.items()},
        "series": sorted(fr),
        "cells": cells,
        "registry": registry_note or "ok",
        "seconds": round(time.monotonic() - t0, 2),
        "verdict_vocabulary": ("FETCHED | NOT_DUE | ROBOTS_DISALLOW | HARD_STOP | UNMEASURED | "
                               "OFFLINE | EMPTY"),
    }
    if not dry_run:
        _write(state_path, state)
    return doc


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    ap.add_argument("--once", action="store_true")
    ap.add_argument("--offline", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args(argv)
    doc = build(offline=a.offline, dry_run=a.dry_run)
    if not a.dry_run:
        _write(OUT, doc)
    print(json.dumps({"access": doc["access"].get("status"), "series": len(doc["series"]),
                      "minted": doc["cells"]["cells_minted_this_pass"]}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
