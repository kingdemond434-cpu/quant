"""BARS_STATE.json: how fresh the trading box's bars and ticks are, measured on the box.

WHY. Bar parquets never cross the wire on purpose (a parquet backlog once killed every push with
HTTP 408; see sync_shadow_to_git.ps1), so the repository's copies stop wherever they were last
committed -- XAUUSD's at 2026-09-11 -- and say nothing about the box. The tick tape's
`tape_state.json` is not published either. So no reader off the box could tell a live bar feed
from a dead one. This organ publishes the MEASUREMENT instead of the data: per bar file its last
bar time, row count and mtime, and per symbol the tape's newest tick and the partition it came
from. It is small JSON, carried by `$reportPaths`.

NON-MONEY-PATH. It reads parquet FOOTERS and two small JSON files and writes one report. It never
imports MetaTrader5, never reads an account, and carries no login or account field.

CHEAP BY CONSTRUCTION. Only the parquet footer is read (`pyarrow.parquet.ParquetFile.metadata`):
row counts and per-row-group min/max statistics of the time column. Only when a footer carries no
usable statistics is ONE column of the LAST row group read. No file is ever loaded whole. Peak RSS
is measured and written into the report rather than assumed (`resources`).

FAIL-SOFT, AND ABSENCE IS NEVER FRESH (L1.28a). Anything unreadable -- no pyarrow, a corrupt
footer, no time column, an empty file -- is `"status": "UNMEASURED"` with a `reason`, and has no
`last_bar_time`. A file not reached inside the time budget is UNMEASURED with reason
`time budget exhausted`; the pass then stops and writes what it has, so it never overruns the
hourly cycle that hosts it (core leg `bars_state`, just before `publish_state`).

Exit 0 whenever the report was written (an UNMEASURED row is a measurement, not a crash); 1 only
when the report itself could not be written.
"""
from __future__ import annotations

import argparse
import json
import socket
import sys
import time
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

DESK = Path(__file__).resolve().parents[1]
DATA = DESK / "data"
UNIVERSE = DATA / "universe"
TICKS = DATA / "tape" / "ticks"
TAPE_STATE = DATA / "tape" / "tape_state.json"
OUT = DATA / "BARS_STATE.json"

SCHEMA = "bars_state/1"
#: Default wall-clock budget for one pass. Measured on the research checkout (118 bar files,
#: footers only): well under a second. The cap is for a slow disk, not the expected case.
DEFAULT_BUDGET_S = 20.0
#: Column names tried, in order, for the bar / tick time. The universe writers use `time`
#: (H1/M15) and `timestamp` (M1); the tape uses `ts` and the integer `time_msc`, tried first
#: because a tick file also carries the second-resolution integer `time`.
TIME_COLUMNS = ("ts", "time_msc", "time", "timestamp", "datetime", "date")
TIMEFRAMES = ("M1", "M5", "M15", "M30", "H1", "H4", "D1", "W1", "MN1")
#: Field names never written, whatever an input carries (the publication login fence).
FORBIDDEN_KEYS = ("login", "account", "account_id", "password", "server")


def _iso(dt: datetime | None) -> str | None:
    return None if dt is None else dt.astimezone(UTC).isoformat(timespec="seconds")


def _mtime(path: Path) -> str | None:
    try:
        return _iso(datetime.fromtimestamp(path.stat().st_mtime, tz=UTC))
    except OSError:
        return None


def _to_utc(value: Any, unit_hint: str | None = None) -> datetime | None:
    """A footer statistic as a UTC datetime: datetimes, pandas Timestamps, or integer epochs."""
    if value is None:
        return None
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=UTC)
    to_py = getattr(value, "to_pydatetime", None)
    if callable(to_py):
        out = to_py()
        if not isinstance(out, datetime):
            return None
        return out if out.tzinfo else out.replace(tzinfo=UTC)
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        v = float(value)
        if unit_hint == "ms" or 1e11 < v < 1e14:
            v /= 1e3
        elif v >= 1e17:
            v /= 1e9
        elif v >= 1e14:
            v /= 1e6
        if v < 1e8:  # before 1973: not an epoch any writer here produces
            return None
        return datetime.fromtimestamp(v, tz=UTC)
    return None


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
    """Row count and newest time stamp of one parquet, from its footer. Never raises."""
    try:
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
            if st is None or not st.has_min_max:
                newest = None
                break
            t = _to_utc(st.max, unit)
            if t is None:
                newest = None
                break
            newest = t if newest is None or t > newest else newest
        source = "footer_statistics"
        if newest is None:
            # No usable statistics: read ONE column of the LAST row group, nothing else.
            tbl = pf.read_row_group(md.num_row_groups - 1, columns=[col])
            vals = [v for v in tbl.column(0).to_pylist() if v is not None]
            newest = max((t for t in (_to_utc(v, unit) for v in vals) if t is not None),
                         default=None)
            source = "last_row_group"
        if newest is None:
            return {"status": "UNMEASURED", "row_count": rows, "time_column": col,
                    "reason": "time column holds no readable time stamp"}
        return {"status": "MEASURED", "row_count": rows, "time_column": col,
                "last_time": _iso(newest), "source": source}
    except Exception as exc:
        return {"status": "UNMEASURED", "reason": f"{type(exc).__name__}: {str(exc)[:200]}"}


def split_bar_name(path: Path) -> tuple[str, str] | None:
    """`XAUUSD_M1.parquet` -> ("XAUUSD", "M1"); a name with no known timeframe -> None."""
    stem = path.stem
    sym, sep, tf = stem.rpartition("_")
    if not sep or not sym or tf not in TIMEFRAMES:
        return None
    return sym, tf


def _tick_partitions(sym_dir: Path) -> list[tuple[str, Path]]:
    """(ISO day, path) for both tape naming conventions, newest first (names only, no stat)."""
    out: list[tuple[str, Path]] = []
    for p in sym_dir.glob("*.parquet"):
        s = p.stem
        if len(s) == 10 and s[4] == "-" and s[7] == "-":
            out.append((s, p))
        elif len(s) == 8 and s.isdigit():
            out.append((f"{s[:4]}-{s[4:6]}-{s[6:]}", p))
    return sorted(out, reverse=True)


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


def _peak_rss_mb() -> float | None:
    try:
        import psutil  # type: ignore[import-untyped,unused-ignore]
        info = psutil.Process().memory_info()
        peak = getattr(info, "peak_wset", None) or info.rss  # peak_wset on Windows
        return round(float(peak) / 1024 ** 2, 1)
    except Exception:
        return None


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
    try:
        bar_files = sorted(universe.glob("*.parquet"))
    except OSError as exc:
        bar_files, bar_reason = [], f"universe directory unreadable: {type(exc).__name__}"
    if not universe.is_dir():
        bar_reason = f"universe directory absent: {universe.name}"
    for path in bar_files:
        named = split_bar_name(path)
        if named is None:
            continue
        sym, tf = named
        row: dict[str, Any] = {"symbol": sym, "timeframe": tf, "file": path.name}
        if exhausted or over():
            exhausted = True
            row.update(status="UNMEASURED", reason="time budget exhausted")
        else:
            m = last_time(path)
            row.update(status=m["status"], row_count=m.get("row_count"),
                       file_mtime=_mtime(path))
            if m["status"] == "MEASURED":
                row["last_bar_time"] = m["last_time"]
                row["source"] = m["source"]
            else:
                row["reason"] = m.get("reason")
        bars.append(row)

    state, state_reason = _read_tape_state(tape_state)
    symbols: set[str] = {k for k, v in state.items() if isinstance(v, dict)}
    try:
        if ticks.is_dir():
            symbols |= {d.name for d in ticks.iterdir() if d.is_dir()}
    except OSError:
        pass
    tape: list[dict[str, Any]] = []
    for sym in sorted(symbols):
        row = {"symbol": sym}
        entry = state.get(sym) if isinstance(state.get(sym), dict) else {}
        recorded = _to_utc(entry.get("last_tick_ms"), "ms") if entry else None
        row["tape_state_last_tick"] = _iso(recorded)
        row["tape_state_last_run"] = entry.get("last_run") if entry else None
        if exhausted or over():
            exhausted = True
            row.update(status="UNMEASURED", reason="time budget exhausted")
            tape.append(row)
            continue
        parts = _tick_partitions(ticks / sym)
        if not parts:
            row.update(status="UNMEASURED", reason="no tick partition on disk")
            tape.append(row)
            continue
        day, path = parts[0]
        row.update(partition=f"{sym}/{path.name}", partition_day=day,
                   partitions=len(parts), file_mtime=_mtime(path))
        m = last_time(path)
        if m["status"] == "MEASURED":
            row.update(status="MEASURED", last_tick=m["last_time"], row_count=m["row_count"],
                       source=m["source"])
        else:
            row.update(status="UNMEASURED", reason=m.get("reason"),
                       row_count=m.get("row_count"))
        tape.append(row)

    def newest(rows: list[dict[str, Any]], key: str) -> str | None:
        vals = [r[key] for r in rows if r.get("status") == "MEASURED" and r.get(key)]
        return max(vals) if vals else None

    nb, nt = newest(bars, "last_bar_time"), newest(tape, "last_tick")

    def age_h(iso: str | None) -> float | None:
        if iso is None:
            return None
        return round((at - datetime.fromisoformat(iso)).total_seconds() / 3600.0, 2)

    doc: dict[str, Any] = {
        "schema": SCHEMA,
        "generated_at": _iso(at),
        "host": socket.gethostname(),
        "budget_s": budget_s,
        "elapsed_s": round(clock() - t0, 3),
        "budget_exhausted": exhausted,
        "summary": {
            "bar_files": len(bars),
            "bar_files_measured": sum(r["status"] == "MEASURED" for r in bars),
            "newest_bar_time": nb, "newest_bar_age_h": age_h(nb),
            "tape_symbols": len(tape),
            "tape_symbols_measured": sum(r["status"] == "MEASURED" for r in tape),
            "newest_tick_time": nt, "newest_tick_age_h": age_h(nt),
            "verdict": "MEASURED" if (nb or nt) else "UNMEASURED",
        },
        "bars": bars,
        "tape": tape,
        "notes": {"bars_reason": bar_reason, "tape_state_reason": state_reason},
        "resources": {"peak_rss_mb": _peak_rss_mb()},
    }
    return doc


def _scrub(obj: Any) -> Any:
    """Drop any account-shaped key, recursively. Nothing here carries one; this is the fence."""
    if isinstance(obj, dict):
        return {k: _scrub(v) for k, v in obj.items() if str(k).lower() not in FORBIDDEN_KEYS}
    if isinstance(obj, list):
        return [_scrub(v) for v in obj]
    return obj


def write(doc: dict[str, Any], out: Path = OUT) -> None:
    text = json.dumps(_scrub(doc), indent=1, sort_keys=False) + "\n"
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
