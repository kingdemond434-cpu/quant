#!/usr/bin/env python3
"""DISK + MEMORY GUARD for the 4GB research box (principal 2026-08-26: "never let the VPS get
clogged; processes should not clog it and should be independent from it").

WHY THIS EXISTS AND NOT A CRON `rm`. 53 hourly miners write a discovery file per source per
sweep -- ~1,300 files/day at steady state. Each is small, none is the problem, and the sum is:
that is exactly the shape of growth nobody notices until a 38GB disk is full and every organ
fails at once for an unrelated-looking reason. The box already lost four days to memory
starvation this month, so the fix is a standing guard, not a cleanup someone remembers.

WHAT IT PROTECTS, in priority order:
  1. IRREPLACEABLE things are NEVER touched -- the moat tape (which lives on the Contabo node
     anyway), git history, ledgers, registries, cohort archives. Anything time cannot rebuild.
  2. REBUILDABLE artifacts are ROTATED, not deleted wholesale: discovery files older than the
     retention window are compacted per source into one gz-per-day roll-up, so the corpus
     survives and the inode count collapses.
  3. The guard REPORTS before it acts and records what it did -- a silent janitor is how a
     desk discovers its evidence is gone.

INDEPENDENCE FROM THIS BOX: heavy state belongs on the Contabo node (the moat tape already
does). This guard also flags any local directory growing faster than the retention can absorb,
so migration happens on evidence rather than after an outage.
"""
from __future__ import annotations

import gzip
import json
import shutil
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

ROOT = Path("/home/quant/quant-platform")
INTEL_DIRS = [ROOT / "desks/mt5/data/intelligence", ROOT / "data/intelligence"]
LOG = ROOT / "data" / "disk_guard.json"

#: Keep this many days of individual discovery files; older ones roll up per source per day.
#:
#: PAYLOADS ARE ROTATED; MEMORY IS NEVER TOUCHED -- and the distinction is the whole safety of
#: this file. A miner has two kinds of state and they have opposite value:
#:
#:   MEMORY (tiny, irreplaceable): the cursors and dedup keys that make a miner INCREMENTAL --
#:   regional_hunters_state.json, frontier_state.json, tick_cursors.json, queued_external.json,
#:   cohort_registry.json, the seen-sets. Delete these and every miner re-mines ground it
#:   already covered, re-submits candidates the novelty gate has already judged, and burns DSR
#:   multiplicity budget twice on the same hypothesis. That is not a cleanup, it is amnesia
#:   with a cost.
#:
#:   PAYLOADS (bulky, disposable once extracted): the discoveries_*.json rows themselves. By
#:   the time they age out they have already been converted to hypotheses, enrolled in the
#:   cohort time machine with their frozen t0, and folded into the identity graph -- all of
#:   which live in MEMORY, not in the payload. Rolling them into one gz per source per day
#:   preserves every row for search while collapsing the inode count.
#:
#: So this guard globs ONLY `discoveries_*.json`. Every `*_state.json`, registry, ledger and
#: archive is invisible to it by construction -- not by a rule someone must remember.
RETAIN_DAYS = 3
#: Act when free space falls below this. Well above the recorder's own floor so the guard moves
#: first and the recorder never has to pause.
FREE_FLOOR_GB = 4.0
#: A single source directory larger than this is a migration candidate, not a rotation problem.
DIR_ALERT_MB = 400


def free_gb() -> float:
    return shutil.disk_usage("/").free / 1e9


def rollup(src_dir: Path, cutoff: str, actions: list[str]) -> int:
    """Compact one source's aged discovery files into a single gz per day. Content preserved."""
    by_day: dict[str, list[Path]] = {}
    for f in src_dir.glob("discoveries_*.json"):
        stamp = f.stem.replace("discoveries_", "")[:8]
        if stamp and stamp < cutoff:
            by_day.setdefault(stamp, []).append(f)
    freed = 0
    for day, files in by_day.items():
        if len(files) < 2:
            continue
        roll = src_dir / f"rollup_{day}.jsonl.gz"
        try:
            with gzip.open(roll, "at", encoding="utf-8") as out:
                for f in files:
                    try:
                        rows = json.loads(f.read_text("utf-8"))
                    except (OSError, ValueError):
                        continue
                    for r in (rows if isinstance(rows, list) else [rows]):
                        out.write(json.dumps(r, separators=(",", ":"), default=str) + "\n")
                    freed += f.stat().st_size
                    f.unlink()
            actions.append(f"rolled {len(files)} files -> {roll.name}")
        except OSError as exc:
            actions.append(f"rollup failed {src_dir.name}/{day}: {exc}")
    return freed


def main() -> int:
    now = datetime.now(tz=UTC)
    before = free_gb()
    actions: list[str] = []
    big: list[str] = []
    cutoff = (now - timedelta(days=RETAIN_DAYS)).strftime("%Y%m%d")
    freed = 0

    for base in INTEL_DIRS:
        if not base.exists():
            continue
        for src in [d for d in base.iterdir() if d.is_dir()]:
            size_mb = sum(f.stat().st_size for f in src.rglob("*") if f.is_file()) / 1e6
            if size_mb > DIR_ALERT_MB:
                big.append(f"{src.name} {size_mb:.0f}MB")
            freed += rollup(src, cutoff, actions)

    after = free_gb()
    report = {"checked_at": now.isoformat(timespec="seconds"),
              "free_gb_before": round(before, 2), "free_gb_after": round(after, 2),
              "freed_mb": round(freed / 1e6, 1), "actions": actions[-20:],
              "migration_candidates": big,
              "retain_days": RETAIN_DAYS}
    if after < FREE_FLOOR_GB:
        report["ALERT"] = (f"free space {after:.1f}GB below the {FREE_FLOOR_GB}GB floor even "
                           f"after rotation -- this is no longer a rotation problem: move heavy "
                           f"state to the Contabo node (the moat tape already lives there) or "
                           f"grow the disk.")
    LOG.write_text(json.dumps(report, indent=1), "utf-8")
    print(f"disk guard: {before:.1f}GB -> {after:.1f}GB free, "
          f"{report['freed_mb']}MB compacted, {len(actions)} action(s)"
          + (f" | ALERT: {report['ALERT'][:80]}" if "ALERT" in report else "")
          + (f" | large: {big}" if big else ""))
    return 1 if "ALERT" in report else 0


if __name__ == "__main__":
    sys.exit(main())
