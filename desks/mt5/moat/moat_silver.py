"""BRONZE -> SILVER: turn the append-only tick tape into the parquet the desk actually reads.

THE TAPE HAD NO CONVERTER (found 2026-08-27). The recorder writes gzip-jsonl bronze at
C:\\moat\\bronze\\mt5_ticks\\<SYM>\\<day>.jsonl.gz continuously -- verified live to the second --
but data/tape/ticks/<SYM>/<day>.parquet, which the tape-input families (liquidity_regime,
orderflow_imbalance) and the moat coverage summary read, last updated 16:00Z the day before:
whatever once produced it is gone, and the moat looked dead while recording perfectly. This is
that producer, reborn as ONE explicit script: incremental (only days whose bronze is newer than
their parquet), append-safe (bronze grows within a day; the parquet is rewritten from the full
day file), and refusing to guess (a row that does not parse is counted and reported, not
silently dropped).

Runs hourly on the desk box (MT5-MoatSilver). The health fence watches the OUTPUT
(newest_tape_write via moat_coverage.json), so this converter dying is a paged breach, not a
silent one, ever again.
"""
from __future__ import annotations

import gzip
import json
import os
from datetime import UTC, datetime, timedelta
from pathlib import Path

BRONZE = Path(os.environ.get("MOAT_BRONZE", r"C:\moat\bronze")) / "mt5_ticks"
BASE = Path(__file__).resolve().parent.parent
SILVER = BASE / "data" / "tape" / "ticks"
#: Only convert recent days: older days are immutable once their bronze stops growing, and the
#: consumers (spread/flow series for the gauntlet, 7-day coverage) never look further back.
DAYS_BACK = 9


def convert_day(src: Path, dst: Path) -> tuple[int, int]:
    rows, bad = [], 0
    with gzip.open(src, "rt", encoding="utf-8") as f:
        for line in f:
            try:
                rows.append(json.loads(line))
            except ValueError:
                bad += 1
    if not rows:
        return 0, bad
    import pandas as pd
    df = pd.DataFrame(rows)
    dst.parent.mkdir(parents=True, exist_ok=True)
    tmp = dst.with_suffix(f".{os.getpid()}.tmp")
    df.to_parquet(tmp, index=False)
    os.replace(tmp, dst)
    return len(rows), bad


def main() -> int:
    if not BRONZE.exists():
        print(f"moat silver: no bronze at {BRONZE} -- recorder has never run here")
        return 1
    cutoff = (datetime.now(tz=UTC) - timedelta(days=DAYS_BACK)).strftime("%Y%m%d")
    done = skipped = failed = 0
    for sym_dir in sorted(d for d in BRONZE.iterdir() if d.is_dir()):
        for gz in sym_dir.glob("*.jsonl.gz"):
            day = gz.name.split(".")[0]
            if day < cutoff:
                continue
            dst = SILVER / sym_dir.name / f"{day}.parquet"
            try:
                if dst.exists() and dst.stat().st_mtime >= gz.stat().st_mtime:
                    skipped += 1
                    continue
                n, bad = convert_day(gz, dst)
                done += 1
                if bad:
                    print(f"  {sym_dir.name}/{day}: {n} rows, {bad} UNPARSEABLE (kept counted)")
            except Exception as exc:  # one bad day must not kill the tape for every symbol
                failed += 1
                print(f"  FAIL {sym_dir.name}/{day}: {type(exc).__name__}: {exc}")
    print(f"moat silver: {done} day-file(s) converted, {skipped} current, {failed} failed")
    return 1 if failed and not done else 0


if __name__ == "__main__":
    raise SystemExit(main())
