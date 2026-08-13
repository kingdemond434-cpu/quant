#!/usr/bin/env python3
"""UPBIT FULL-MARKET CANDLE SNAPSHOT (R0303) -- archive what the venue deletes.

Upbit PURGES a market's candle history at delisting: verified 6/6 delisted markets return
HTTP 404 on /v1/candles/days (OXT/NKN/LOOM/QTCON/PCI/MARO, 2026-08-01), ~11.4 KRW markets/yr
erased at source. The desk's kr_perasset panel filters to >=120 aligned days, which excludes
exactly the thin/new names that delist -- the venue's purge and the desk's own construction
filter STACK into survivorship bias. This collector closes the venue half: every market's
daily candles, full history on first contact, incremental after, so the day a market halts
the desk already holds what nobody can buy afterwards (L1.46: unrecoverable at any price).

THE LESSON ALREADY PAID: KRW-AQT and KRW-AERGO halted 2026-08-03, two days after the find was
carded, and their history is GONE -- this organ started nine days late. BTC-SPURS halts
2026-08-18. Scope is ALL quote currencies (KRW/BTC/USDT), not the row's KRW-only ask: the
purge is venue-wide and today's at-risk name is BTC-quoted.

WHAT IS STORED, and whose clock stamps it (L1.46):
  * daily/{market}.jsonl  -- the venue's candle rows VERBATIM plus one `_recv` field (our UTC
    receipt stamp). The candle label is the VENUE's clock (UTC-midnight boundary, proven in
    libs/research/upbit_data.py); `_recv` is OURS; both travel on every row.
  * minute/{market}.jsonl -- 1m rows for markets the venue has FLAGGED (market_event.warning,
    the designation that precedes delisting), trailing --minute-window-days: the
    delisting-unwind microstructure (s42 named ground) dies with the purge too.
  * manifest.json -- per-market row counts and last-candle keys, per-run failures, and the
    DELISTED ledger: a market that vanishes from /v1/market/all is recorded with its
    first_missing date and its files are PRESERVED -- that ledger is the treatment group every
    survivorship study needs and the venue erases.

ONLY COMPLETED candles are stored: today's daily candle and the current minute are in
progress at fetch time, and an in-progress row stored as final is a measurement claim the
data cannot cash. Incremental runs therefore re-see yesterday's boundary cleanly.

REFUSAL PATHS (L1.28a/L1.41):
  * market list unreachable -> REFUSED, exit 2, nothing written: an unreachable universe must
    never read as an empty universe, and a delist ledger built from a failed list would mark
    the whole venue delisted.
  * a market whose page walk dies mid-history -> recorded FAILED in the manifest (kept rows
    stand; `last` does NOT advance past what was actually stored), and >10% failed markets
    exits 1. UNMEASURED never collapses into "no new data".

CADENCE (L1.28c): daily -- the data-arrival ceiling; daily candles change once per UTC day
and the flagged-minute trailing window is far wider than one day. Scheduled in
ops/crontab.manifest; a delisting announced intra-day is covered as long as the halt is
>=1 day out (Upbit announces halts weeks ahead; the ledger row's own examples had 2-17 days).

    .venv/bin/python scripts/run_upbit_snapshot.py [--limit N] [--no-minute] [--json]
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_ROOT))

from libs.ops.lawful import guard  # noqa: E402
from libs.research import upbit_data as ud  # noqa: E402

SNAP_ROOT = _ROOT / "data/upbit_snapshot"
# Backstop against a runaway walk, NOT a coverage cap: ~3,400 daily candles (17 pages) is the
# venue's own history depth for its oldest 2017 markets; 400 pages = 80,000 candles = 219y of
# days or 5.5d of minutes. Hitting it is reported loudly by the walker (L1.57, no silent caps).
MAX_PAGES = 400
FAIL_FRACTION_EXIT = 0.10


def _load_manifest(root: Path) -> dict[str, Any]:
    p = root / "manifest.json"
    if not p.exists():
        return {"markets": {}, "minute": {}, "delisted": {}, "runs": 0}
    try:
        m = json.loads(p.read_text("utf-8"))
        if not isinstance(m, dict):
            raise ValueError("manifest not a dict")
        for k in ("markets", "minute", "delisted"):
            m.setdefault(k, {})
        return m
    except (json.JSONDecodeError, ValueError, OSError) as e:
        # A corrupt manifest must not silently restart history as if nothing was ever stored
        # (the candle files still exist); refuse and let a human look (L2.4, loud).
        raise SystemExit(f"REFUSED: manifest unreadable ({e!r}) -- fix or remove "
                         f"{p} explicitly; candle files are untouched") from e


def _append_rows(path: Path, rows: list[dict[str, Any]], recv: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps({**r, "_recv": recv}, ensure_ascii=False,
                               separators=(",", ":")) + "\n")


def _snap_series(mkt: str, *, path: str, entry: dict[str, Any], out_file: Path,
                 exclude_from_key: str, recv: str) -> tuple[int, bool]:
    """Walk one market's series incrementally; append; update `entry` in place."""
    last = str(entry.get("last") or "")
    if last and int(entry.get("rows") or 0) > 0 and not out_file.exists():
        # Manifest says rows exist but the file is gone (manual purge / partial restore):
        # resync from scratch rather than silently recording a hole as up-to-date.
        print(f"  {mkt} {path}: file missing with last={last!r} -- RESYNC from history start")
        last, entry["rows"] = "", 0
    rows, complete = ud.walk_candles_raw(mkt, path=path, stop_before_key=last,
                                         exclude_from_key=exclude_from_key,
                                         max_pages=MAX_PAGES)
    if rows:
        _append_rows(out_file, rows, recv)
        entry["rows"] = int(entry.get("rows") or 0) + len(rows)
        entry["last"] = ud.candle_key(rows[-1])
        entry.setdefault("first", ud.candle_key(rows[0]))
    return len(rows), complete


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--root", type=Path, default=SNAP_ROOT, help="snapshot root (tests)")
    ap.add_argument("--limit", type=int, default=0, help="first N markets only (smoke runs)")
    ap.add_argument("--no-minute", action="store_true", help="skip flagged-market 1m walk")
    ap.add_argument("--minute-window-days", type=int, default=30)
    ap.add_argument("--json", action="store_true", help="print the run summary as JSON")
    args = ap.parse_args(argv)
    guard()

    now = datetime.now(tz=UTC)
    recv = now.isoformat()
    today_daily_key = now.strftime("%Y-%m-%dT00:00:00")           # today's candle: in progress
    cur_minute_key = now.strftime("%Y-%m-%dT%H:%M:00")            # current minute: in progress

    try:
        live = ud.fetch_markets()
    except Exception as e:
        print(f"REFUSED: market list unreachable ({e!r}) -- an unreachable universe is not an "
              f"empty universe; nothing written")
        return 2

    root: Path = args.root
    man = _load_manifest(root)
    live_by_mkt = {str(m["market"]): m for m in live if m.get("market")}

    # DELIST LEDGER: previously-live markets that vanished from the venue's own list. Files
    # are preserved forever -- they are the point of this organ.
    for gone in sorted(set(man["markets"]) - set(live_by_mkt) - set(man["delisted"])):
        man["delisted"][gone] = {"first_missing": recv[:10],
                                 **{k: man["markets"][gone].get(k)
                                    for k in ("last", "rows", "first")}}
        print(f"  DELISTED: {gone} vanished from /v1/market/all -- "
              f"{man['markets'][gone].get('rows', 0)} rows preserved")

    targets = sorted(live_by_mkt)
    if args.limit:
        print(f"  --limit {args.limit}: scanning {min(args.limit, len(targets))} of "
              f"{len(targets)} live markets (smoke run, not coverage)")
        targets = targets[:args.limit]

    new_daily = new_minute = 0
    failures: list[str] = []
    flagged: list[str] = []
    for mkt in targets:
        entry = man["markets"].setdefault(mkt, {})
        entry["warning"] = bool((live_by_mkt[mkt].get("market_event") or {}).get("warning"))
        if entry["warning"]:
            flagged.append(mkt)
        try:
            n, complete = _snap_series(mkt, path="days", entry=entry,
                                       out_file=root / "daily" / f"{mkt}.jsonl",
                                       exclude_from_key=today_daily_key, recv=recv)
        except Exception as e:                        # loud per-market, never a silent skip
            failures.append(f"{mkt}:days:{e!r}")
            continue
        new_daily += n
        if not complete:
            failures.append(f"{mkt}:days:partial-walk")

    if not args.no_minute:
        min_floor = (now - timedelta(days=args.minute_window_days)).strftime("%Y-%m-%dT%H:%M:00")
        for mkt in flagged:
            entry = man["minute"].setdefault(mkt, {})
            if str(entry.get("last") or "") < min_floor:
                entry["last"] = min_floor              # trailing window, not full history
            try:
                n, complete = _snap_series(mkt, path="minutes/1", entry=entry,
                                           out_file=root / "minute" / f"{mkt}.jsonl",
                                           exclude_from_key=cur_minute_key, recv=recv)
            except Exception as e:
                failures.append(f"{mkt}:minutes:{e!r}")
                continue
            new_minute += n
            if not complete:
                failures.append(f"{mkt}:minutes:partial-walk")

    man["runs"] = int(man.get("runs") or 0) + 1
    man["last_run"] = recv
    man["clock"] = ("candle stamps are the VENUE's (UTC-midnight boundary daily candles, "
                    "libs/research/upbit_data.py); _recv per row is OUR receipt clock (L1.46)")
    man["last_run_summary"] = {"live_markets": len(live_by_mkt), "scanned": len(targets),
                               "new_daily_rows": new_daily, "new_minute_rows": new_minute,
                               "flagged": flagged, "failures": failures,
                               "delisted_total": len(man["delisted"])}
    root.mkdir(parents=True, exist_ok=True)
    (root / "manifest.json").write_text(json.dumps(man, indent=1, sort_keys=True) + "\n",
                                        "utf-8")

    summary = man["last_run_summary"]
    if args.json:
        print(json.dumps(summary, indent=1))
    else:
        print(f"upbit snapshot (R0303): scanned {len(targets)}/{len(live_by_mkt)} live markets, "
              f"+{new_daily} daily rows, +{new_minute} minute rows "
              f"({len(flagged)} venue-flagged), {len(man['delisted'])} delisted preserved, "
              f"{len(failures)} failure(s)")
        for f in failures[:20]:
            print(f"  FAILED {f}")
    if failures and len(failures) > FAIL_FRACTION_EXIT * max(1, len(targets)):
        print(f"UNMEASURED tail: {len(failures)} failures exceed "
              f"{FAIL_FRACTION_EXIT:.0%} of {len(targets)} scanned -- this run is NOT a "
              f"complete snapshot and must not be read as one")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
