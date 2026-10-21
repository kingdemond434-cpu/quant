"""BARS_STATE.json: how fresh the trading box's bars and ticks are, measured on the box.

WHY. Bar parquets never cross the wire on purpose (a parquet backlog once killed every push with
HTTP 408; see sync_shadow_to_git.ps1), so the repository's copies stop wherever they were last
committed -- XAUUSD's at 2026-09-11 -- and say nothing about the box. The tick tape's
`tape_state.json` is not published either. So no reader off the box could tell a live bar feed
from a dead one. This organ publishes the MEASUREMENT instead of the data: per bar file its last
bar time, row count and mtime, and per symbol the tape's newest tick and the partition it came
from. It is small JSON, carried by `$reportPaths`, and read by `check_desk_health.py`.

NON-MONEY-PATH. It reads parquet FOOTERS and two small JSON files and writes one report. It never
imports MetaTrader5, never reads an account, and carries no login or account field.

THE BAR AND TICK STAMPS ARE ON THE BROKER'S CLOCK, NOT UTC (audit of f8167d3e, 2026-10-21).
`copy_rates_*` / `copy_ticks_*` return the server's wall time, and the desk's writers store it
labelled UTC (`h1_source.broker_utc_offset_hours` documents the defect): EURUSD_H1's last Friday
bar reads 23:00 and the next Monday's 00:00. Subtracting such a stamp from UTC now reads every
feed two to three hours FRESHER than it is. So every bar/tick time here is published as a naive
broker wall time with `"time_clock": "broker"`, and EVERY AGE comes from a true UTC source:

  * `*_utc` / `age_h`: the broker time converted through the published server anchor
    (`prop.e8_guard`: server midnight is 17:00 America/New_York, i.e. the server is New York + 7h,
    UTC+2 in winter and UTC+3 in summer, DST handled by the zone database);
  * `file_mtime` / `mtime_age_h`: the file system's UTC mtime;
  * `tape_state_last_run` / `tape_state_last_run_age_h`: the recorder's own `datetime.now(UTC)`.

If the anchor cannot be imported, the converted fields and their ages are null with a reason --
never a broker stamp read as UTC.

CHEAP AND BOUNDED. Only the parquet footer is read (row counts and per-row-group min/max of the
time column). When a footer has no usable statistics, ONE column of the LAST row group is reduced
with `pyarrow.compute.max` -- and only if that row group is under FALLBACK_MAX_ROWS rows and
FALLBACK_MAX_BYTES uncompressed; a larger one is UNMEASURED, never read. Peak RSS is written into
the report (`resources`), not assumed.

FAIL-SOFT, AND ABSENCE IS NEVER FRESH (L1.28a). Anything unreadable -- no pyarrow, a corrupt
footer, no time column, an empty file, a bad tape_state entry, a stamp before 2000 (epoch 0) or
in the future -- is `"status": "UNMEASURED"` with a `reason`, and carries no time. A file not
reached inside the time budget is UNMEASURED `time budget exhausted`; the pass then writes what it
has, so it never overruns the hourly cycle that hosts it (core, always-run leg `bars_state`).

THE SUMMARY VERDICT IS A SHARE, NOT AN EXISTENCE PROOF. `bars_verdict` / `tape_verdict` read
MEASURED only when at least MEASURED_SHARE (80%) of their rows measured, PARTIAL when some did,
UNMEASURED when none did; `verdict` is the worse of the two.

NAMES THAT LOOK LIKE ACCOUNT NUMBERS ARE NOT PUBLISHED. A symbol folder or bar file whose name is
all digits and at least ACCOUNT_LIKE_DIGITS long is reported as `<redacted-numeric>` (UNMEASURED),
and every account-shaped KEY is dropped before writing. `libs.ops.login_fence.is_login_key` is
used when the base carries it; this base does not, so the local rule below applies. Value-level
login detection belongs to the publication fence, not here.

Exit 0 whenever the report was written (an UNMEASURED row is a measurement, not a crash); 1 only
when the report itself could not be written.
"""
from __future__ import annotations

import argparse
import json
import math
import re
import socket
import sys
import time
from collections.abc import Callable
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any

DESK = Path(__file__).resolve().parents[1]
DATA = DESK / "data"
UNIVERSE = DATA / "universe"
TICKS = DATA / "tape" / "ticks"
TAPE_STATE = DATA / "tape" / "tape_state.json"
OUT = DATA / "BARS_STATE.json"

SCHEMA = "bars_state/2"
#: Default wall-clock budget for one pass. Measured on the research checkout (107 bar files,
#: 245 tape symbols, footers only): 0.4 s. The cap is for a slow disk, not the expected case.
DEFAULT_BUDGET_S = 20.0
#: Column names tried, in order, for the bar / tick time. The universe writers use `time`
#: (H1/M15) and `timestamp` (M1); the tape uses `ts` and the integer `time_msc`, tried first
#: because a tick file also carries the second-resolution integer `time`.
TIME_COLUMNS = ("ts", "time_msc", "time", "timestamp", "datetime", "date")
TIMEFRAMES = ("M1", "M5", "M15", "M30", "H1", "H4", "D1", "W1", "MN1")
#: The no-statistics fallback reads one column of the last row group only below BOTH bounds.
#: The audit's 20M-row partition took 78.5 s and 1.6 GB through the unbounded read.
FALLBACK_MAX_ROWS = 2_000_000
FALLBACK_MAX_BYTES = 64 * 1024 * 1024
#: A stamp before this year is not one any writer here produced (epoch 0 is the usual culprit).
MIN_PLAUSIBLE_YEAR = 2000
#: Converted UTC stamps more than this far past now are future-dated, hence UNMEASURED.
FUTURE_SKEW = timedelta(minutes=10)
#: Without the anchor, a broker wall time may lead UTC by at most +3h (summer) before it is
#: future-dated on any reading of the server clock.
BROKER_MAX_LEAD = timedelta(hours=3)
#: A summary verdict reads MEASURED only when at least this share of its rows measured.
MEASURED_SHARE = 0.8
#: A name of this many digits or more, and nothing else, is treated as an account number.
ACCOUNT_LIKE_DIGITS = 5
REDACTED = "<redacted-numeric>"
_LOGIN_TOKENS = ("login", "acct", "account", "passw", "secret", "token", "apikey")


def _anchor() -> tuple[Any, int] | None:
    """The published server anchor (zone, server-midnight hour there), or None."""
    try:
        from zoneinfo import ZoneInfo
        if str(DESK) not in sys.path:
            sys.path.insert(0, str(DESK))
        from prop.e8_guard import SERVER_ANCHOR_TZ, SERVER_MIDNIGHT_ET_HOUR
        return ZoneInfo(str(SERVER_ANCHOR_TZ)), int(SERVER_MIDNIGHT_ET_HOUR)
    except Exception:
        return None


ANCHOR = _anchor()
ANCHOR_NAME = ("prop.e8_guard: server = America/New_York + 7h (UTC+2 winter / UTC+3 summer)"
               if ANCHOR else None)


def broker_to_utc(wall: datetime, anchor: tuple[Any, int] | None = None) -> datetime | None:
    """A naive broker wall time as true UTC, through the server anchor. None when unavailable."""
    a = anchor if anchor is not None else ANCHOR
    if a is None:
        return None
    zone, midnight_hour = a
    try:
        local = (wall.replace(tzinfo=None) - timedelta(hours=24 - midnight_hour))
        return local.replace(tzinfo=zone).astimezone(UTC)
    except Exception:
        return None


def _iso(dt: datetime | None) -> str | None:
    return None if dt is None else dt.astimezone(UTC).isoformat(timespec="seconds")


def _wall_iso(dt: datetime | None) -> str | None:
    """A broker wall time, written WITHOUT an offset so no reader can mistake it for UTC."""
    return None if dt is None else dt.replace(tzinfo=None).isoformat(timespec="seconds")


def _mtime(path: Path) -> datetime | None:
    try:
        return datetime.fromtimestamp(path.stat().st_mtime, tz=UTC)
    except (OSError, ValueError, OverflowError):
        return None


def _age_h(now: datetime, then: datetime | None) -> float | None:
    return None if then is None else round((now - then).total_seconds() / 3600.0, 2)


def to_wall(value: Any, unit_hint: str | None = None) -> datetime | None:
    """A footer statistic or tape_state value as a naive broker wall time. Never raises.

    The stores label broker wall time as UTC, so the label is dropped, never honoured.
    """
    try:
        if value is None or isinstance(value, bool):
            return None
        if isinstance(value, datetime):
            return value.replace(tzinfo=None)
        to_py = getattr(value, "to_pydatetime", None)
        if callable(to_py):
            out = to_py()
            return out.replace(tzinfo=None) if isinstance(out, datetime) else None
        if isinstance(value, (int, float)):
            v = float(value)
            if not math.isfinite(v):
                return None
            if unit_hint == "ms" or 1e11 < v < 1e14:
                v /= 1e3
            elif v >= 1e17:
                v /= 1e9
            elif v >= 1e14:
                v /= 1e6
            return datetime.fromtimestamp(v, tz=UTC).replace(tzinfo=None)
    except (ValueError, OverflowError, OSError, TypeError):
        return None
    return None


def sanity(wall: datetime, now: datetime, anchor: tuple[Any, int] | None = None
           ) -> tuple[datetime | None, str | None]:
    """(true UTC or None, reason it is UNMEASURED or None)."""
    if wall.year < MIN_PLAUSIBLE_YEAR:
        return None, f"implausible stamp {wall.isoformat()} (before {MIN_PLAUSIBLE_YEAR})"
    utc = broker_to_utc(wall, anchor)
    if utc is not None:
        if utc > now + FUTURE_SKEW:
            return None, f"future-dated stamp {utc.isoformat()} (now {now.isoformat()})"
    elif wall > (now + BROKER_MAX_LEAD + FUTURE_SKEW).replace(tzinfo=None):
        return None, f"future-dated broker stamp {wall.isoformat()}"
    return utc, None


def _time_column(pf: Any) -> str | None:
    names = list(pf.schema_arrow.names)
    for c in TIME_COLUMNS:
        if c in names:
            return c
    meta = pf.schema_arrow.pandas_metadata or {}
    for idx in meta.get("index_columns") or []:
        if isinstance(idx, str) and idx in names:
            return idx
    return None


def last_time(path: Path) -> dict[str, Any]:
    """Row count and newest broker wall time of one parquet, from its footer. Never raises."""
    try:
        import pyarrow.compute as pc
        import pyarrow.parquet as pq
    except Exception as exc:  # pragma: no cover - pyarrow is a desk dependency
        return {"status": "UNMEASURED", "reason": f"pyarrow unavailable: {type(exc).__name__}"}
    try:
        pf = pq.ParquetFile(str(path))
        md = pf.metadata
        rows = int(md.num_rows)
        col = _time_column(pf)
        if col is None:
            return {"status": "UNMEASURED", "row_count": rows,
                    "reason": "no time column in the footer schema"}
        if rows == 0 or md.num_row_groups == 0:
            return {"status": "UNMEASURED", "row_count": rows, "reason": "file holds no rows"}
        ci = pf.schema_arrow.names.index(col)
        unit = "ms" if col == "time_msc" else None
        newest: datetime | None = None
        for g in range(md.num_row_groups):
            st = md.row_group(g).column(ci).statistics
            t = to_wall(st.max, unit) if st is not None and st.has_min_max else None
            if t is None:
                newest = None
                break
            newest = t if newest is None or t > newest else newest
        source = "footer_statistics"
        if newest is None:
            last = md.num_row_groups - 1
            rg = md.row_group(last)
            nbytes = int(rg.column(ci).total_uncompressed_size)
            if rg.num_rows > FALLBACK_MAX_ROWS or nbytes > FALLBACK_MAX_BYTES:
                return {"status": "UNMEASURED", "row_count": rows, "time_column": col,
                        "reason": (f"no footer statistics and the last row group is too large "
                                   f"to read ({rg.num_rows:,} rows, {nbytes:,} bytes; caps "
                                   f"{FALLBACK_MAX_ROWS:,} / {FALLBACK_MAX_BYTES:,})")}
            arr = pf.read_row_group(last, columns=[col]).column(0)
            newest = to_wall(pc.max(arr).as_py(), unit)
            source = "last_row_group"
        if newest is None:
            return {"status": "UNMEASURED", "row_count": rows, "time_column": col,
                    "reason": "time column holds no readable time stamp"}
        return {"status": "MEASURED", "row_count": rows, "time_column": col,
                "wall": newest, "source": source}
    except Exception as exc:
        return {"status": "UNMEASURED", "reason": f"{type(exc).__name__}: {str(exc)[:200]}"}


def account_like(name: str) -> bool:
    return name.isdigit() and len(name) >= ACCOUNT_LIKE_DIGITS


def split_bar_name(path: Path) -> tuple[str, str] | None:
    """`XAUUSD_M1.parquet` -> ("XAUUSD", "M1"); a name with no known timeframe -> None."""
    sym, sep, tf = path.stem.rpartition("_")
    if not sep or not sym or tf not in TIMEFRAMES:
        return None
    return sym, tf


def partition_day(stem: str) -> str | None:
    """The ISO day a tick partition names, for both conventions, validated as a real date."""
    if len(stem) == 10 and stem[4] == "-" and stem[7] == "-":
        iso = stem
    elif len(stem) == 8 and stem.isdigit():
        iso = f"{stem[:4]}-{stem[4:6]}-{stem[6:]}"
    else:
        return None
    try:
        return date.fromisoformat(iso).isoformat()
    except ValueError:
        return None


def _tick_partitions(sym_dir: Path) -> tuple[list[tuple[str, Path]], int]:
    """((ISO day, path) newest first, count of names that are not a real date)."""
    out: list[tuple[str, Path]] = []
    bad = 0
    for p in sym_dir.glob("*.parquet"):
        day = partition_day(p.stem)
        if day is None:
            bad += 1
        else:
            out.append((day, p))
    return sorted(out, reverse=True), bad


def _read_tape_state(path: Path) -> tuple[dict[str, Any], str | None]:
    try:
        doc = json.loads(path.read_text("utf-8"))
    except FileNotFoundError:
        return {}, "tape_state.json absent"
    except Exception as exc:
        return {}, f"tape_state.json unreadable: {type(exc).__name__}"
    if not isinstance(doc, dict):
        return {}, "tape_state.json is not an object"
    return doc, None


def _utc_iso_or_none(value: Any) -> datetime | None:
    """`last_run` as a true UTC datetime: an ISO string or nothing. Its raw value never passes."""
    if not isinstance(value, str) or len(value) > 40:
        return None
    try:
        dt = datetime.fromisoformat(value)
    except ValueError:
        return None
    return dt if dt.tzinfo else None


def _peak_rss_mb() -> float | None:
    try:
        import psutil  # type: ignore[import-untyped,unused-ignore]
        info = psutil.Process().memory_info()
        peak = getattr(info, "peak_wset", None) or info.rss  # peak_wset on Windows
        return round(float(peak) / 1024 ** 2, 1)
    except Exception:
        return None


def _verdict(rows: list[dict[str, Any]]) -> tuple[str, float | None]:
    if not rows:
        return "UNMEASURED", None
    share = sum(r.get("status") == "MEASURED" for r in rows) / len(rows)
    if share >= MEASURED_SHARE:
        return "MEASURED", round(share, 3)
    return ("PARTIAL" if share > 0 else "UNMEASURED"), round(share, 3)


_RANK = {"MEASURED": 0, "PARTIAL": 1, "UNMEASURED": 2}


def _bar_row(path: Path, sym: str, tf: str, now: datetime) -> dict[str, Any]:
    row: dict[str, Any] = {"symbol": sym, "timeframe": tf, "file": path.name,
                           "time_clock": "broker"}
    m = last_time(path)
    mt = _mtime(path)
    row.update(row_count=m.get("row_count"), file_mtime=_iso(mt),
               mtime_age_h=_age_h(now, mt))
    if m["status"] != "MEASURED":
        row.update(status="UNMEASURED", reason=m.get("reason"))
        return row
    utc, why = sanity(m["wall"], now)
    if why:
        row.update(status="UNMEASURED", reason=why)
        return row
    row.update(status="MEASURED", last_bar_time=_wall_iso(m["wall"]), source=m["source"],
               last_bar_time_utc=_iso(utc), age_h=_age_h(now, utc))
    if utc is None:
        row["age_reason"] = "server anchor unavailable; broker time is never read as UTC"
    return row


def _tape_row(sym: str, entry: Any, ticks: Path, now: datetime) -> dict[str, Any]:
    row: dict[str, Any] = {"symbol": sym, "time_clock": "broker"}
    entry = entry if isinstance(entry, dict) else {}
    wall = to_wall(entry.get("last_tick_ms"), "ms") if entry else None
    if wall is not None:
        utc, why = sanity(wall, now)
        if why:
            row["tape_state_reason"] = why
        else:
            row.update(tape_state_last_tick=_wall_iso(wall),
                       tape_state_last_tick_utc=_iso(utc))
    elif entry.get("last_tick_ms") is not None:
        row["tape_state_reason"] = "last_tick_ms is not a readable time stamp"
    run = _utc_iso_or_none(entry.get("last_run")) if entry else None
    row.update(tape_state_last_run=_iso(run), tape_state_last_run_age_h=_age_h(now, run))
    parts, bad = _tick_partitions(ticks / sym)
    if bad:
        row["invalid_partition_names"] = bad
    if not parts:
        row.update(status="UNMEASURED", reason="no tick partition on disk")
        return row
    day, path = parts[0]
    mt = _mtime(path)
    row.update(partition=f"{sym}/{path.name}", partition_day=day, partitions=len(parts),
               file_mtime=_iso(mt), mtime_age_h=_age_h(now, mt))
    m = last_time(path)
    row["row_count"] = m.get("row_count")
    if m["status"] != "MEASURED":
        row.update(status="UNMEASURED", reason=m.get("reason"))
        return row
    utc, why = sanity(m["wall"], now)
    if why:
        row.update(status="UNMEASURED", reason=why)
        return row
    row.update(status="MEASURED", last_tick=_wall_iso(m["wall"]), source=m["source"],
               last_tick_utc=_iso(utc), age_h=_age_h(now, utc))
    return row


def measure(*, universe: Path = UNIVERSE, ticks: Path = TICKS, tape_state: Path = TAPE_STATE,
            budget_s: float = DEFAULT_BUDGET_S,
            clock: Callable[[], float] = time.monotonic,
            now: datetime | None = None) -> dict[str, Any]:
    """The whole report. Stops at `budget_s` and marks what it did not reach UNMEASURED."""
    t0 = clock()
    at = now or datetime.now(UTC)
    exhausted = False

    def over() -> bool:
        return clock() - t0 > budget_s

    bars: list[dict[str, Any]] = []
    bar_reason = None
    if not universe.is_dir():
        bar_reason = f"universe directory absent: {universe.name}"
    try:
        bar_files = sorted(universe.glob("*.parquet"))
    except OSError as exc:
        bar_files, bar_reason = [], f"universe directory unreadable: {type(exc).__name__}"
    for path in bar_files:
        named = split_bar_name(path)
        if named is None:
            continue
        sym, tf = named
        if account_like(sym):
            bars.append({"symbol": REDACTED, "timeframe": tf, "file": REDACTED,
                         "status": "UNMEASURED", "reason": "name looks like an account number"})
            continue
        if exhausted or over():
            exhausted = True
            bars.append({"symbol": sym, "timeframe": tf, "file": path.name,
                         "status": "UNMEASURED", "reason": "time budget exhausted"})
            continue
        try:
            bars.append(_bar_row(path, sym, tf, at))
        except Exception as exc:
            bars.append({"symbol": sym, "timeframe": tf, "file": path.name,
                         "status": "UNMEASURED", "reason": f"{type(exc).__name__}"})

    state, state_reason = _read_tape_state(tape_state)
    symbols: set[str] = {str(k) for k in state}
    try:
        if ticks.is_dir():
            symbols |= {d.name for d in ticks.iterdir() if d.is_dir()}
    except OSError:
        pass
    tape: list[dict[str, Any]] = []
    redacted_tape = 0
    for sym in sorted(symbols):
        if account_like(sym):
            redacted_tape += 1
            tape.append({"symbol": REDACTED, "status": "UNMEASURED",
                         "reason": "name looks like an account number"})
            continue
        if exhausted or over():
            exhausted = True
            tape.append({"symbol": sym, "status": "UNMEASURED",
                         "reason": "time budget exhausted"})
            continue
        try:
            tape.append(_tape_row(sym, state.get(sym), ticks, at))
        except Exception as exc:
            # ONE BAD ENTRY COSTS ITS OWN ROW, NEVER THE REPORT (audit: NaN / 1e20 at :249).
            tape.append({"symbol": sym, "status": "UNMEASURED",
                         "reason": f"bad tape entry: {type(exc).__name__}"})

    def newest(rows: list[dict[str, Any]], key: str) -> dict[str, Any] | None:
        best = None
        for r in rows:
            if r.get("status") == "MEASURED" and r.get(key) and (
                    best is None or r[key] > best[key]):
                best = r
        return best

    def youngest(rows: list[dict[str, Any]], key: str) -> float | None:
        vals = [r[key] for r in rows if isinstance(r.get(key), (int, float))]
        return min(vals) if vals else None

    nb, nt = newest(bars, "last_bar_time"), newest(tape, "last_tick")
    bv, bshare = _verdict(bars)
    tv, tshare = _verdict(tape)
    doc: dict[str, Any] = {
        "schema": SCHEMA,
        "generated_at": _iso(at),
        "host": socket.gethostname(),
        "time_clock": "broker",
        "utc_conversion": ANCHOR_NAME,
        "budget_s": budget_s,
        "elapsed_s": round(clock() - t0, 3),
        "budget_exhausted": exhausted,
        "summary": {
            "bar_files": len(bars),
            "bar_files_measured": sum(r["status"] == "MEASURED" for r in bars),
            "bars_measured_share": bshare, "bars_verdict": bv,
            "newest_bar_time": nb["last_bar_time"] if nb else None,
            "newest_bar_time_utc": nb.get("last_bar_time_utc") if nb else None,
            "newest_bar_age_h": nb.get("age_h") if nb else None,
            "newest_bar_file_mtime_age_h": youngest(
                [r for r in bars if r.get("status") == "MEASURED"], "mtime_age_h"),
            "tape_symbols": len(tape),
            "tape_symbols_measured": sum(r["status"] == "MEASURED" for r in tape),
            "tape_measured_share": tshare, "tape_verdict": tv,
            "newest_tick_time": nt["last_tick"] if nt else None,
            "newest_tick_time_utc": nt.get("last_tick_utc") if nt else None,
            "newest_tick_age_h": nt.get("age_h") if nt else None,
            "newest_tick_file_mtime_age_h": youngest(
                [r for r in tape if r.get("status") == "MEASURED"], "mtime_age_h"),
            "newest_tape_run_age_h": youngest(tape, "tape_state_last_run_age_h"),
            "measured_share_threshold": MEASURED_SHARE,
            "verdict": max((bv, tv), key=lambda v: _RANK[v]),
        },
        "bars": bars,
        "tape": tape,
        "notes": {"bars_reason": bar_reason, "tape_state_reason": state_reason,
                  "redacted_names": redacted_tape + sum(r["symbol"] == REDACTED for r in bars),
                  "ages": ("every age is from a true UTC source: the server anchor, the file "
                           "mtime, or tape_state.last_run; never a broker stamp read as UTC")},
        "resources": {"peak_rss_mb": _peak_rss_mb()},
    }
    return doc


def _local_is_login_key(key: str) -> bool:
    k = re.sub(r"[^a-z]", "", key.lower())
    return any(tok in k for tok in _LOGIN_TOKENS)


def _login_key_rule() -> Callable[[str], bool]:
    try:
        from libs.ops.login_fence import (  # type: ignore[import-not-found,unused-ignore]
            is_login_key,  # absent on the 2026-10-21 base
        )
        return lambda k: bool(is_login_key(k))
    except Exception:
        return _local_is_login_key


def _scrub(obj: Any, rule: Callable[[str], bool] | None = None) -> Any:
    """Drop every account-shaped key, recursively. Nothing here emits one; this is the fence."""
    rule = rule or _login_key_rule()
    if isinstance(obj, dict):
        return {k: _scrub(v, rule) for k, v in obj.items() if not rule(str(k))}
    if isinstance(obj, list):
        return [_scrub(v, rule) for v in obj]
    return obj


def write(doc: dict[str, Any], out: Path = OUT) -> None:
    text = json.dumps(_scrub(doc), indent=1, sort_keys=False, allow_nan=False) + "\n"
    out.parent.mkdir(parents=True, exist_ok=True)
    try:
        from libs.ops.win_write import write_text_resilient
    except Exception:
        repo = DESK.parents[1]
        if str(repo) not in sys.path:
            sys.path.insert(0, str(repo))
        from libs.ops.win_write import write_text_resilient
    write_text_resilient(out, text)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--budget-s", type=float, default=DEFAULT_BUDGET_S)
    ap.add_argument("--out", type=Path, default=OUT)
    ap.add_argument("--universe", type=Path, default=UNIVERSE)
    ap.add_argument("--ticks", type=Path, default=TICKS)
    ap.add_argument("--tape-state", type=Path, default=TAPE_STATE)
    a = ap.parse_args(argv)
    doc = measure(universe=a.universe, ticks=a.ticks, tape_state=a.tape_state,
                  budget_s=a.budget_s)
    try:
        write(doc, a.out)
    except Exception as exc:
        print(f"bars_state: could not write {a.out}: {type(exc).__name__}: {exc}",
              file=sys.stderr)
        return 1
    s = doc["summary"]
    print(json.dumps({"out": str(a.out), "elapsed_s": doc["elapsed_s"],
                      "budget_exhausted": doc["budget_exhausted"], **s}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
