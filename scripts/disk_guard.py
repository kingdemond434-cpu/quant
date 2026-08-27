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
import subprocess
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

ROOT = Path("/home/quant/quant-platform")
INTEL_DIRS = [ROOT / "desks/mt5/data/intelligence", ROOT / "data/intelligence"]
#: The reaper asks THIS repo which worktrees it registered; a checkout under /tmp that
#: this repo never registered is somebody else's and is left entirely alone.
REPO = ROOT
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

#: ---------------------------------------------------------------------------------------
#: THE MEMORY ARM (gap-fixer 2026-08-26). This file has called itself a "DISK + MEMORY GUARD"
#: since it was written, and it had no memory arm at all: every measurement it took was
#: `shutil.disk_usage("/")`. The box's actual killer is RAM, not disk -- 63% disk used and
#: ZERO swap on 3814MB. On 2026-08-20 root `cron.service` was OOM-killed and has been dead
#: ever since (161 manifest rows with it); on 2026-08-26 alone the same-day external pipeline
#: was OOM-killed three times, `memecoin-shadow` once, and the CI suite died sig9 with the
#: run's own note reading "MemAvailable 827MB, 495MB of RAM held by files under /tmp (tmpfs)".
#:
#: `/tmp` IS RAM ON THIS BOX. It is a tmpfs, so a scratch file a miner seat wrote last week is
#: not sitting on the disk -- it is holding resident memory against every organ that runs
#: afterwards, and it is invisible to a guard that only reads disk free space. That is the
#: whole defect: the instrument measured the wrong resource, so the resource that was actually
#: binding had no instrument at all (L1.46).
#:
#: SAFETY, and it is what makes deleting from /tmp legitimate rather than reckless:
#:   1. Only REGULAR FILES are ever removed -- never sockets, fifos, symlinks or directories.
#:   2. Never inside a live tool's own scratch (KEEP_PREFIXES): agent sessions, systemd private
#:      dirs, snap, X11, the pytest tmpdir tree, ssh control sockets, the node compile cache.
#:   3. Never a file ANY process holds open. Checked against /proc/*/fd, not assumed from age --
#:      a long-running miner streaming a 2GB download is exactly the file an age rule would eat.
#:   4. Only files untouched (max of mtime and atime) for TMP_RETAIN_HOURS.
#: A file surviving all four is derived scratch whose writer exited days ago.
#: S108 is suppressed deliberately: /tmp IS the subject here. This guard exists to reclaim
#: the RAM a tmpfs-mounted /tmp holds; parameterising the path away would parameterise away
#: the fix. The four safety clauses above are what make writing to it legitimate.
TMP_DIR = Path("/tmp")  # noqa: S108
TMP_RETAIN_HOURS = 24.0
#: Below this MemAvailable the box is in OOM-killer territory: the kernel starts choosing
#: victims, and it does not choose the offender -- on 08-20 it chose cron, which is why the
#: fleet lost its scheduler for six days. Naming the ruin path is what the survival rails
#: require of every clamp; this one reduces the probability that the OOM killer reaches
#: `quant-live-guard` or the gateway.
MEM_FLOOR_MB = 600.0
KEEP_PREFIXES = ("claude-", "systemd-private", ".X", "snap", "pytest-of-",
                 "node-compile-cache", ".font", "ssh-", ".ICE", "tmux-")
#: A REGISTERED GIT WORKTREE IS NOT SCRATCH, and unlinking its files one at a time is the worst
#: available outcome: the checkout is gutted while `.git/worktrees/<name>` still registers it, so
#: `git worktree list` keeps advertising a tree whose every tracked file now reads as deleted --
#: and this desk has repeatedly had stale checkouts launder mass deletions into a commit (R0423).
#: The file reaper therefore SKIPS anything inside a registered worktree, and a separate arm
#: removes the whole worktree through git, which refuses when the tree is dirty. Measured
#: 2026-08-27: /tmp/gw_base and /tmp/lawgate-head-w59v694v/t held 433MB of RAM between them on a
#: 3.8GB no-swap box that had OOM-killed its research organs 221 times in three days.
WORKTREE_STALE_HOURS = 12.0


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


def mem_available_mb() -> float:
    """MemAvailable in MB. Returns 0.0 when unreadable -- UNMEASURED is never a clean verdict
    (L1.28a), and a guard that cannot read the resource it guards must say so, not pass."""
    try:
        for line in Path("/proc/meminfo").read_text("utf-8").splitlines():
            if line.startswith("MemAvailable:"):
                return float(line.split()[1]) / 1024.0
    except (OSError, ValueError, IndexError):
        pass
    return 0.0


def _open_files() -> set[str]:
    """Every path any visible process currently holds open. Cheap (~one readlink per fd) and
    the difference between a janitor and an outage: age alone cannot tell a dead seat's
    leftovers from a live seat's in-progress download."""
    held: set[str] = set()
    for proc in Path("/proc").iterdir():
        if not proc.name.isdigit():
            continue
        try:
            for fd in (proc / "fd").iterdir():
                try:
                    held.add(str(fd.resolve()))
                except OSError:
                    continue
        except OSError:
            continue
    return held


def _git(args: list[str], cwd: Path | None = None) -> tuple[int, str]:
    try:
        proc = subprocess.run(["git", *args], cwd=str(cwd) if cwd else None,
                              capture_output=True, text=True, timeout=60, check=False)
    except (OSError, subprocess.SubprocessError) as exc:
        return 1, f"{type(exc).__name__}: {exc}"
    return proc.returncode, (proc.stdout + proc.stderr).strip()


def tmpfs_worktrees(repo: Path) -> list[Path]:
    """Registered worktrees whose checkout lives under the /tmp tmpfs."""
    rc, out = _git(["worktree", "list", "--porcelain"], repo)
    if rc != 0:
        return []
    found: list[Path] = []
    for line in out.splitlines():
        if line.startswith("worktree "):
            path = Path(line.split(" ", 1)[1].strip())
            if TMP_DIR in path.parents:
                found.append(path)
    return found


def _cwds() -> set[str]:
    """Every visible process's cwd -- a worktree someone is standing in is never reclaimed."""
    out: set[str] = set()
    for proc in Path("/proc").iterdir():
        if not proc.name.isdigit():
            continue
        try:
            out.add(str((proc / "cwd").resolve()))
        except OSError:
            continue
    return out


def reap_tmpfs_worktrees(now: datetime, repo: Path, actions: list[str]) -> tuple[int, int]:
    """Remove stale git worktrees checked out onto tmpfs. Returns (bytes_freed, n_removed).

    Every refusal is REPORTED rather than forced: a worktree that is dirty, holds untracked
    work, sits at a sha no branch contains, or has a live process inside it is left alone with
    its reason named. `git worktree remove` is the only removal path -- it refuses a dirty tree
    itself, which is the second half of the safety argument.
    """
    freed = 0
    removed = 0
    cwds = _cwds()
    for wt in tmpfs_worktrees(repo):
        if not wt.exists():
            continue
        try:
            size = sum(f.stat().st_size for f in wt.rglob("*")
                       if f.is_file() and not f.is_symlink())
            newest = max((max(f.stat().st_mtime, f.stat().st_atime) for f in wt.rglob("*")
                          if f.is_file() and not f.is_symlink()), default=0.0)
        except OSError:
            continue
        if now.timestamp() - newest < WORKTREE_STALE_HOURS * 3600.0:
            continue
        if any(c == str(wt) or c.startswith(f"{wt}/") for c in cwds):
            actions.append(f"tmpfs-worktree: {wt} HELD by a live process -- not reclaimed")
            continue
        rc, dirty = _git(["status", "--porcelain"], wt)
        if rc != 0 or dirty:
            actions.append(f"tmpfs-worktree: {wt} has uncommitted work "
                           f"({len(dirty.splitlines())} path(s)) -- not reclaimed, relocate it "
                           f"to real disk instead of deleting it")
            continue
        rc, head = _git(["rev-parse", "HEAD"], wt)
        if rc != 0:
            actions.append(f"tmpfs-worktree: {wt} HEAD unreadable -- not reclaimed")
            continue
        rc, contains = _git(["branch", "-a", "--contains", head], repo)
        if rc != 0 or not contains.strip():
            actions.append(f"tmpfs-worktree: {wt} sits at {head[:8]}, which NO branch contains "
                           f"-- not reclaimed; tag it before it can be freed")
            continue
        rc, out = _git(["worktree", "remove", str(wt)], repo)
        if rc != 0:
            actions.append(f"tmpfs-worktree: git refused to remove {wt} ({out[:120]})")
            continue
        freed += size
        removed += 1
        actions.append(f"tmpfs-worktree: reclaimed {size / 1e6:.0f}MB of RAM from {wt} "
                       f"(clean, HEAD {head[:8]} reachable)")
    if removed:
        _git(["worktree", "prune"], repo)
    return freed, removed


def reap_tmpfs(now: datetime, actions: list[str]) -> tuple[int, int]:
    """Free RAM held by stale scratch under the /tmp tmpfs. Returns (bytes_freed, n_files)."""
    if not TMP_DIR.is_dir():
        return 0, 0
    held = _open_files()
    # A registered worktree is a CHECKOUT, not scratch. Unlinking its files would leave git
    # advertising a tree of phantom deletions; `reap_tmpfs_worktrees` removes it wholesale or
    # not at all.
    worktrees = tmpfs_worktrees(REPO)
    cutoff = now.timestamp() - TMP_RETAIN_HOURS * 3600.0
    freed = 0
    removed = 0
    for entry in TMP_DIR.iterdir():
        if entry.name.startswith(KEEP_PREFIXES):
            continue
        if any(wt == entry or entry in wt.parents or wt in entry.parents for wt in worktrees):
            continue
        candidates = [entry] if entry.is_file() and not entry.is_symlink() else (
            [f for f in entry.rglob("*") if f.is_file() and not f.is_symlink()]
            if entry.is_dir() and not entry.is_symlink() else [])
        for f in candidates:
            try:
                st = f.stat()
            except OSError:
                continue
            if max(st.st_mtime, st.st_atime) >= cutoff:
                continue
            if str(f) in held:
                continue
            try:
                f.unlink()
            except OSError:
                continue
            freed += st.st_size
            removed += 1
    if removed:
        actions.append(f"tmpfs: reclaimed {freed / 1e6:.1f}MB of RAM from {removed} stale "
                       f"scratch file(s) older than {TMP_RETAIN_HOURS:.0f}h")
    return freed, removed


def main() -> int:
    now = datetime.now(tz=UTC)
    before = free_gb()
    mem_before = mem_available_mb()
    actions: list[str] = []
    big: list[str] = []
    wt_freed, wt_removed = reap_tmpfs_worktrees(now, REPO, actions)
    tmp_freed, tmp_files = reap_tmpfs(now, actions)
    tmp_freed += wt_freed
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
    mem_after = mem_available_mb()
    report: dict[str, Any] = {"checked_at": now.isoformat(timespec="seconds"),
              "free_gb_before": round(before, 2), "free_gb_after": round(after, 2),
              "freed_mb": round(freed / 1e6, 1), "actions": actions[-20:],
              "migration_candidates": big,
              "retain_days": RETAIN_DAYS,
              "mem_available_mb_before": round(mem_before, 1),
              "mem_available_mb_after": round(mem_after, 1),
              "tmpfs_reclaimed_mb": round(tmp_freed / 1e6, 1),
              "tmpfs_files_removed": tmp_files,
              "tmp_retain_hours": TMP_RETAIN_HOURS,
              "tmpfs_worktrees_removed": wt_removed,
              "tmpfs_worktrees_reclaimed_mb": round(wt_freed / 1e6, 1),
              "tmpfs_worktrees_remaining": [str(w) for w in tmpfs_worktrees(REPO)]}
    # The memory arm alerts on the SAME footing as the disk arm. `/tmp` is RAM here, so a
    # reclaim that still leaves the box under the floor is not a cleanup that worked -- it is
    # evidence the pressure is coming from resident processes, and the honest next move is the
    # console (swapfile) or moving heavy state to the Contabo node, not another sweep.
    if mem_after and mem_after < MEM_FLOOR_MB:
        report["MEM_ALERT"] = (
            f"MemAvailable {mem_after:.0f}MB below the {MEM_FLOOR_MB:.0f}MB floor after "
            f"reclaiming {tmp_freed / 1e6:.1f}MB of tmpfs -- the box is in OOM-killer "
            f"territory and the killer does not choose the offender (it took root cron on "
            f"2026-08-20 and the fleet lost its scheduler for six days). PRINCIPAL CONSOLE: "
            f"a swapfile needs root. Meanwhile heavy state belongs on the Contabo node.")
    elif not mem_after:
        report["MEM_ALERT"] = ("MemAvailable is UNREADABLE -- the memory arm is blind, which "
                               "is a defect, not a pass (L1.28a).")
    if after < FREE_FLOOR_GB:
        report["ALERT"] = (f"free space {after:.1f}GB below the {FREE_FLOOR_GB}GB floor even "
                           f"after rotation -- this is no longer a rotation problem: move heavy "
                           f"state to the Contabo node (the moat tape already lives there) or "
                           f"grow the disk.")
    LOG.write_text(json.dumps(report, indent=1), "utf-8")
    print(f"disk guard: {before:.1f}GB -> {after:.1f}GB free, "
          f"{report['freed_mb']}MB compacted, {len(actions)} action(s) | "
          f"mem {mem_before:.0f} -> {mem_after:.0f}MB avail "
          f"({report['tmpfs_reclaimed_mb']}MB tmpfs RAM reclaimed from "
          f"{tmp_files} file(s))"
          + (f" | ALERT: {report['ALERT'][:80]}" if "ALERT" in report else "")
          + (f" | MEM_ALERT: {report['MEM_ALERT'][:80]}" if "MEM_ALERT" in report else "")
          + (f" | large: {big}" if big else ""))
    return 1 if ("ALERT" in report or "MEM_ALERT" in report) else 0


if __name__ == "__main__":
    sys.exit(main())
