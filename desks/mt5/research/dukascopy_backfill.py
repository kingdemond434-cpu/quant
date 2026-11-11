"""Bounded, resumable Dukascopy tick-history acquisition for the MT5 research desk.

This is a depth source, never execution-cost authority.  Fusion-native quotes and fills remain
the only source allowed to price the live venue.  Each invocation downloads a small number of
complete UTC symbol-days, writes them atomically, and advances a durable per-symbol cursor.
The hourly data department can therefore compound history without a multi-hour monolith or a
restart that begins again at the newest date.
"""

from __future__ import annotations

import argparse
import contextlib
import json
import os
from collections import defaultdict
from datetime import UTC, date, datetime, time, timedelta
from pathlib import Path
from typing import Any

try:  # package import in tests; direct import when invoked as a script by the supervisor
    from .fetch_dukascopy import (
        POINT,
        USER_AGENT,
        FeedSaysStop,
        check_scale,
        fetch_hour,
        instrument_map,
        robots_gate,
        unmapped_reasons,
        vendor_code,
    )
except ImportError:  # pragma: no cover - exercised by the real script entry point
    from fetch_dukascopy import (
        POINT,
        USER_AGENT,
        FeedSaysStop,
        check_scale,
        fetch_hour,
        instrument_map,
        robots_gate,
        unmapped_reasons,
        vendor_code,
    )


BASE = Path(__file__).resolve().parents[1]
DATA = BASE / "data" / "dukascopy"
REPORT = BASE / "reports" / "DUKASCOPY_BACKFILL.json"
STATE = DATA / "backfill_state.json"
LOCK = DATA / ".backfill.lock"
UNIVERSE_DIR = BASE / "data" / "universe"
UNIVERSE_JSON = UNIVERSE_DIR / "universe.json"

# Rotate across unlike exposures first.  The remainder of the supported vendor universe follows,
# so the source never collapses into another gold/FX-only dataset.
PRIORITY = (
    "XAUUSD", "XTIUSD", "USDJPY", "EURUSD", "XAGUSD", "XBRUSD", "AUDNZD", "GBPUSD",
    "XNGUSD", "EURCHF", "XPTUSD", "USDCAD", "XPDUSD",
)

# After PRIORITY, the asset classes POINT never reached go first, one symbol per class per turn,
# so an index, a soft, a bond, a crypto CFD and an exotic each land within the first rotation
# rather than after a hundred share CFDs.
CLASS_ORDER = (
    "Indices", "Soft Commodity", "Bonds", "Crypto", "Forex Exotics", "Commodities", "Energy",
    "Forex", "Equities",
)


def _class_of(symbol: str, rows: dict[str, dict[str, Any]]) -> str:
    row = rows.get(symbol) or {}
    return str(row.get("asset_class") or "UNCLASSIFIED")


def rotation(mapped: dict[str, dict[str, Any]] | None = None,
             point: dict[str, float] | None = None) -> tuple[str, ...]:
    """PRIORITY first, then every other supported symbol interleaved across asset classes."""
    rows = instrument_map() if mapped is None else mapped
    supported = set(rows) | set(POINT if point is None else point)
    head = tuple(s for s in PRIORITY if s in supported)
    by_class: dict[str, list[str]] = defaultdict(list)
    for sym in sorted(supported - set(head)):
        by_class[_class_of(sym, rows)].append(sym)
    order = [c for c in CLASS_ORDER if c in by_class] + sorted(set(by_class) - set(CLASS_ORDER))
    tail: list[str] = []
    while any(by_class[c] for c in order):
        for c in order:
            if by_class[c]:
                tail.append(by_class[c].pop(0))
    return head + tuple(tail)


SYMBOLS = rotation()


def _atomic_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".partial")
    tmp.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    os.replace(tmp, path)


def _load_state(path: Path, *, newest: date) -> dict[str, Any]:
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        raw = {}
    cursors = raw.get("next_date") if isinstance(raw.get("next_date"), dict) else {}
    codes = raw.get("vendor_code") if isinstance(raw.get("vendor_code"), dict) else {}
    requeue = raw.get("requeue_empty_after") if isinstance(
        raw.get("requeue_empty_after"), dict) else {}
    refused = raw.get("refused") if isinstance(raw.get("refused"), dict) else {}
    clean: dict[str, str] = {}
    clean_codes: dict[str, str] = {}
    clean_requeue: dict[str, str] = {}
    for symbol in SYMBOLS:
        value = str(cursors.get(symbol, newest.isoformat()))
        try:
            clean[symbol] = date.fromisoformat(value).isoformat()
        except ValueError:
            clean[symbol] = newest.isoformat()
        code = vendor_code(symbol)
        # A state written before the vendor map recorded no code, and fetched under the Fusion
        # name. Where that name was never a vendor id (XTIUSD -> LIGHTCMDUSD and four more) every
        # hour 404'd and the day was published EMPTY. Rewind that symbol to the newest day and
        # re-fetch the empty partitions the old code wrote, down to where its cursor had reached.
        old = str(codes.get(symbol) or symbol.upper())
        if symbol in cursors and old != code:
            clean_requeue[symbol] = clean[symbol]
            clean[symbol] = newest.isoformat()
        elif symbol in requeue:
            with contextlib.suppress(ValueError):
                clean_requeue[symbol] = date.fromisoformat(str(requeue[symbol])).isoformat()
        clean_codes[symbol] = code
    # A refusal holds only while the vendor code it was measured on is still the one in use.
    clean_refused = {s: dict(v) for s, v in refused.items()
                     if isinstance(v, dict) and s in clean_codes
                     and v.get("vendor_code") == clean_codes[s]}
    return {"schema_version": 2, "next_date": clean, "vendor_code": clean_codes,
            "requeue_empty_after": clean_requeue, "refused": clean_refused,
            "rotation": int(raw.get("rotation", 0) or 0)}


def _day_path(root: Path, symbol: str, day: date) -> Path:
    return root / symbol / f"{day:%Y}" / f"{day:%m}" / f"{symbol}_ticks_{day:%Y%m%d}.parquet"


def _rows_in(path: Path) -> int | None:
    try:
        import pyarrow.parquet as pq
        return int(pq.read_metadata(path).num_rows)  # type: ignore[no-untyped-call]
    except Exception:
        return None


def broker_reference(symbol: str, day: date, universe_dir: Path = UNIVERSE_DIR) -> float | None:
    """The broker's median H1 close within three days of `day`, or None when it has none."""
    import pandas as pd

    path = universe_dir / f"{symbol}_H1.parquet"
    if not path.exists():
        return None
    try:
        close = pd.read_parquet(path, columns=["close"])["close"]
    except Exception:
        return None
    if not isinstance(close.index, pd.DatetimeIndex) or close.empty:
        return None
    idx = close.index if close.index.tz is not None else close.index.tz_localize("UTC")
    centre = pd.Timestamp(day, tz="UTC")
    near = close[(idx >= centre - pd.Timedelta(days=3)) & (idx <= centre + pd.Timedelta(days=4))]
    near = near[near > 0]
    return float(near.median()) if len(near) else None


def fetch_day(symbol: str, day: date, root: Path, *, pause: float = 0.25,
              refetch_empty: bool = False,
              universe_dir: Path = UNIVERSE_DIR) -> dict[str, Any]:
    """Fetch one complete UTC day.  A partial download is never published as complete."""
    import pandas as pd

    target = _day_path(root, symbol, day)
    if target.exists() and not (refetch_empty and _rows_in(target) == 0):
        return {"symbol": symbol, "day": day.isoformat(), "status": "EXISTS",
                "ticks": None, "file": str(target)}
    rows: list[tuple[Any, ...]] = []
    failures: list[str] = []
    missing = 0
    start = datetime.combine(day, time.min, tzinfo=UTC)
    for hour in range(24):
        values, status = fetch_hour(symbol, start + timedelta(hours=hour), pause=pause)
        if status == "ok":
            rows.extend(values)
        elif status in {"missing", "empty"}:
            missing += 1
        else:
            failures.append(f"{hour:02d}:{status}")
    if failures:
        return {"symbol": symbol, "day": day.isoformat(), "status": "RETRY",
                "ticks": len(rows), "missing_hours": missing, "failures": failures}

    # THE SCALE CHECK: the decoded day against the broker's own level for the same dates. A
    # mismatch is never published -- it is the 10x error POINT's comment describes.
    scale = "UNMEASURED"
    reference: float | None = None
    mid: float | None = None
    if rows:
        mids = sorted((r[1] + r[2]) / 2.0 for r in rows)
        mid = mids[len(mids) // 2]
        reference = broker_reference(symbol, day, universe_dir)
        scale = check_scale(mid, reference)
    if scale == "SCALE_MISMATCH":
        return {"symbol": symbol, "day": day.isoformat(), "status": "SCALE_MISMATCH",
                "ticks": len(rows), "vendor_code": vendor_code(symbol),
                "vendor_mid": mid, "broker_reference": reference}

    target.parent.mkdir(parents=True, exist_ok=True)
    frame = pd.DataFrame(rows, columns=["ms", "bid", "ask", "bidvol", "askvol"])
    if not frame.empty:
        frame["utc"] = pd.to_datetime(frame.pop("ms"), unit="ms", utc=True)
        frame = frame.set_index("utc").sort_index()
    else:
        frame.index = pd.DatetimeIndex([], name="utc", tz="UTC")
    partial = target.with_suffix(target.suffix + ".partial")
    frame.to_parquet(partial)
    os.replace(partial, target)
    return {"symbol": symbol, "day": day.isoformat(), "status": "WRITTEN",
            "ticks": len(frame), "missing_hours": missing, "file": str(target),
            "vendor_code": vendor_code(symbol), "scale_check": scale}


def _fetched_days(root: Path, symbol: str) -> int:
    base = root / symbol
    if not base.is_dir():
        return 0
    return sum(1 for _ in base.glob(f"*/*/{symbol}_ticks_*.parquet"))


def coverage(root: Path, state: dict[str, Any], *,
             universe_json: Path = UNIVERSE_JSON) -> dict[str, Any]:
    """Per universe symbol: MAPPED / UNMAPPED / REFUSED, the vendor code and the days on disk."""
    try:
        universe = json.loads(universe_json.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        universe = {}
    mapped = instrument_map()
    named = unmapped_reasons()
    symbols = sorted({k for k, v in universe.items() if isinstance(v, dict)} | set(SYMBOLS))
    per: dict[str, dict[str, Any]] = {}
    by_class: dict[str, dict[str, int]] = defaultdict(
        lambda: {"symbols": 0, "mapped": 0, "unmapped": 0, "with_days": 0})
    for sym in symbols:
        u = universe.get(sym) if isinstance(universe.get(sym), dict) else {}
        cls = str(u.get("asset_class") or (mapped.get(sym) or {}).get("asset_class")
                  or "UNCLASSIFIED")
        days = _fetched_days(root, sym)
        if sym in state.get("refused", {}):
            row = {"status": "REFUSED", **state["refused"][sym]}
        elif sym in SYMBOLS:
            row = {"status": "MAPPED", "vendor_code": vendor_code(sym),
                   "source": "vendor_map" if sym in mapped else "POINT"}
        else:
            reason = (named.get(sym) or {}).get("reason") or (
                "not in dukascopy_instruments.json (added to the registry after the map was "
                "built); rebuild the map")
            row = {"status": "UNMAPPED", "reason": reason}
        row.update({"asset_class": cls, "fetched_days": days,
                    "in_universe": sym in universe})
        per[sym] = row
        agg = by_class[cls]
        agg["symbols"] += 1
        agg["mapped" if row["status"] == "MAPPED" else "unmapped"] += 1
        agg["with_days"] += int(days > 0)
    in_uni = [s for s in per if per[s]["in_universe"]]
    return {
        "universe_symbols": len(in_uni),
        "mapped": sum(per[s]["status"] == "MAPPED" for s in in_uni),
        "unmapped": sum(per[s]["status"] == "UNMAPPED" for s in in_uni),
        "refused": sum(per[s]["status"] == "REFUSED" for s in in_uni),
        "universe_symbols_with_days": sum(per[s]["fetched_days"] > 0 for s in in_uni),
        "by_asset_class": dict(sorted(by_class.items())),
        "symbols": per,
    }


def run(*, root: Path = DATA, state_path: Path = STATE, report_path: Path = REPORT,
        symbol_days: int = 8, pause: float = 0.25, now: datetime | None = None,
        robots: dict[str, Any] | None = None) -> dict[str, Any]:
    now = now or datetime.now(UTC)
    newest = now.date() - timedelta(days=1)  # never publish the still-forming UTC day
    state = _load_state(state_path, newest=newest)
    # The host's own rules are read before any history request, every pass. Anything but
    # ALLOWED fetches nothing and says why in the artifact.
    robots = robots if robots is not None else robots_gate()
    stopped: str | None = None
    if robots.get("verdict") != "ALLOWED":
        symbol_days = 0
    start_rotation = state["rotation"] % len(SYMBOLS)
    live = [s for s in SYMBOLS if s not in state["refused"]] or list(SYMBOLS)
    results: list[dict[str, Any]] = []
    position = start_rotation
    for _ in range(max(0, symbol_days)):
        # Refused symbols are stepped over, not fetched: 24 requests a turn for a day that can
        # never be published would be rude to a free feed.
        for _ in range(len(SYMBOLS)):
            symbol = SYMBOLS[position % len(SYMBOLS)]
            position += 1
            if symbol in live:
                break
        day = date.fromisoformat(state["next_date"][symbol])
        floor = state["requeue_empty_after"].get(symbol)
        requeue = bool(floor) and day > date.fromisoformat(floor)
        try:
            result = fetch_day(symbol, day, root, pause=pause, refetch_empty=requeue)
        except FeedSaysStop as e:
            # The vendor asked us to slow down: stop the pass, keep the cursor, say so.
            stopped = str(e)
            break
        results.append(result)
        if floor and not requeue:
            state["requeue_empty_after"].pop(symbol, None)
        if result["status"] == "SCALE_MISMATCH":
            state["refused"][symbol] = {
                "vendor_code": result.get("vendor_code"), "day": result["day"],
                "reason": (f"SCALE_MISMATCH: vendor mid {result.get('vendor_mid')} vs broker "
                           f"{result.get('broker_reference')} -- outside 3x; nothing published"),
                "at": now.isoformat()}
        # Only a complete artifact (new or pre-existing) advances the cursor. Transient failures
        # remain on the same day and are retried on the next rotation.
        if result["status"] in {"WRITTEN", "EXISTS"}:
            state["next_date"][symbol] = (day - timedelta(days=1)).isoformat()
    state["rotation"] = position % len(SYMBOLS)
    state["updated_at"] = now.isoformat()
    _atomic_json(state_path, state)
    report = {
        "schema_version": 2,
        "generated_at": now.isoformat(),
        "authority": "RESEARCH_DEPTH_ONLY",
        "venue_cost_authority": "Fusion-native quotes and fills",
        "client": {"user_agent": USER_AGENT, "min_interval_s": max(0.25, pause),
                   "robots": robots, "stopped_by_vendor": stopped},
        "supported_symbols": len(SYMBOLS),
        "attempted_symbol_days": len(results),
        "written": sum(r["status"] == "WRITTEN" for r in results),
        "retry": sum(r["status"] == "RETRY" for r in results),
        "scale_mismatch": sum(r["status"] == "SCALE_MISMATCH" for r in results),
        "results": results,
        "next_date": state["next_date"],
        "coverage": coverage(root, state),
    }
    _atomic_json(report_path, report)
    return report


def _claim(lock: Path, *, now: datetime) -> bool:
    lock.parent.mkdir(parents=True, exist_ok=True)
    try:
        fd = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    except FileExistsError:
        try:
            age = now.timestamp() - lock.stat().st_mtime
        except OSError:
            return False
        if age <= 2 * 3600:
            return False
        lock.unlink(missing_ok=True)
        fd = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    with os.fdopen(fd, "w", encoding="utf-8") as handle:
        handle.write(f"pid={os.getpid()} at={now.isoformat()}\n")
    return True


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--symbol-days", type=int, default=8)
    parser.add_argument("--pause", type=float, default=0.25)
    parser.add_argument("--out", type=Path, default=DATA)
    parser.add_argument("--state", type=Path, default=STATE)
    parser.add_argument("--report", type=Path, default=REPORT)
    args = parser.parse_args()
    now = datetime.now(UTC)
    if not _claim(LOCK, now=now):
        print("Dukascopy backfill already running; this pass is a measured no-op")
        return 0
    try:
        report = run(root=args.out, state_path=args.state, report_path=args.report,
                     symbol_days=args.symbol_days, pause=max(0.0, args.pause), now=now)
    finally:
        LOCK.unlink(missing_ok=True)
    print(f"Dukascopy: {report['written']}/{report['attempted_symbol_days']} symbol-days written; "
          f"{report['retry']} held for retry")
    return 1 if report["retry"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
