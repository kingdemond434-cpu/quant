"""SEAT STAMPER: a name-stamped reading for every intelligence seat whose files carry no time.

THE GAP (measured 2026-09-30, the D18 fence). Five enrolled seats were UNFED with "no snapshot file
carries a time in its name": `brain` (peer_group_maps.json), `cohorts` (cohort_registry.json),
`fxmerge` (fxmerge_archived_records.json), `mql5_reputation` (reputation_history.jsonl) and, until
dataset_series learnt YAML, `hypotheses`. Each is a STATE FILE rewritten in place. `dataset_series`
reads a seat only through file names that say when the desk knew their contents, and refuses an
mtime (an mtime is when git checked the file out, not when the desk learnt it) -- correctly. So a
seat whose writer overwrites one file can never hold a series, however long it runs.

THE FIX, without inventing a single timestamp. Two honest clocks say when the desk knew a state
file's contents:

    git       every committed version of the file, at its COMMIT time (the box commits its state
              hourly; the content existed at or before the commit, so the stamp is conservative);
    this      every content change this organ sees, at the moment it sees it.

Each is written as a DIGEST -- `{"records": <rows in the file>, "bytes": <size>}` -- under
`data/dataset_stamps/<seat>/stamp_<YYYYMMDD_HHMMSS>_<file>.json`, which `dataset_series` reads as a
third intelligence root. A digest is a READING (how much the seat held when the desk knew it), not a
claim: it sits outside `data/intelligence/**` on purpose, so the compiler never reads it twice.

Runs inside the hourly `dataset_exploitation` leg, before discovery. Idempotent: a ledger per seat
records the versions already stamped. Never raises; an unreadable version is skipped and named.

THE QUIET-WRITER GAP (measured 2026-09-30, D18 after #168). Thirteen seats held fewer than 30
stamped readings. Three causes, each closed here or by its writer:

    a quiet run wrote NOTHING     `factor_residual_engine`, `plumbing_miner` (via
                                  `proposer_common.donate`) and `global_survivor_frontier` wrote a
                                  dated file only when they found something, so an hour that ran
                                  and found nothing left no reading at all -- the seat looked dead
                                  when its writer was alive. `record_run` writes that hour's
                                  reading (zero rows, organ named) under data/dataset_stamps/, so
                                  a run is ALWAYS a reading and the compiler never sees it.
    rewrites git already holds    `hypotheses` and `recombinants` rewrite day-stamped files in
                                  place; git holds every rewrite at its commit time.
                                  `stamp_git_activity` reads each MODIFYING commit as one reading
                                  (the files the seat rewrote then), for any seat under 30.
    the writer's host never       `SEAT_WRITERS` names, per seat, the writer, where it runs and
    pushes                        why git stopped hearing from it. A writer that only went quiet
                                  in git because its host stopped pushing is a BOX STEP, and the
                                  census below says so rather than inventing readings.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
DESK = ROOT / "desks" / "mt5"
STAMPS = DESK / "data" / "dataset_stamps"
#: Git versions stamped per file per pass (the backfill is incremental across passes).
BACKFILL_PER_PASS = 200
#: Files larger than this are digested by size and line count only (never parsed whole).
PARSE_MAX_BYTES = 64 * 1024 * 1024
_SUFFIXES = (".json", ".jsonl", ".yaml", ".yml")


#: Readings a seat needs before its series is conditionable (dataset_census.MIN_OBSERVATIONS).
MIN_READINGS = 30
#: Modifying commits stamped per seat per pass (incremental, like the backfill).
ACTIVITY_PER_PASS = 400

#: WHO WRITES EACH SEAT THAT WENT QUIET, WHERE, AND WHY GIT STOPPED HEARING FROM IT (2026-09-30,
#: read from the committed code and the seat directories' own git history). `closure` is what
#: now makes it write stamped readings: `record_run` (code, this commit), `git_activity`
#: (history already in git, stamped here), or `box_step` (its host must push its state; the
#: step is named). A seat absent from this table is still stamped by every mechanism above.
SEAT_WRITERS: dict[str, dict[str, str]] = {
    "factor_residual": {
        "writer": "desks/mt5/research/factor_residual_engine.py", "host": "box",
        "clock": "hourly_cycle leg residual_factors + daily_cycle",
        "cause": "wrote discoveries_*.json only when a proposal survived; a run with none left "
                 "no reading (last file 2026-09-12)",
        "closure": "record_run"},
    "plumbing": {
        "writer": "desks/mt5/research/plumbing_miner.py", "host": "box",
        "clock": "daily_cycle._proposers",
        "cause": "donated only when a cell beat its placebo; 1,198 tests with no proposal left "
                 "no reading (last file 2026-09-04)",
        "closure": "record_run"},
    "frontier": {
        "writer": "desks/mt5/side_channels/global_survivor_frontier.py", "host": "vps",
        "clock": "seed_miners (quant-seed-miners.service, hourly)",
        "cause": "wrote only when a NEW population was found; its query rings exhaust, so most "
                 "runs found none; and the VPS commits to the orphaned desk-sync-clean, which "
                 "never reaches the live branch",
        "closure": "record_run + box_step"},
    "hypotheses": {
        "writer": "desks/mt5/side_channels/hourly_controller.py", "host": "vps",
        "clock": "hourly-controller.service",
        "cause": "rewrites H-<day>-NNN.yaml in place; the VPS stopped reaching live git "
                 "2026-09-12",
        "closure": "git_activity + box_step"},
    "recombinants": {
        "writer": "desks/mt5/side_channels/alpha_recombination.py (via hourly_controller)",
        "host": "vps", "clock": "hourly-controller.service",
        "cause": "rewrites REC-<day>-<hash>.json in place; the VPS stopped reaching live git "
                 "2026-09-12",
        "closure": "git_activity + box_step"},
    "brain": {
        "writer": "ops/run_brain_hunter.sh (BRAIN hunter dig, s10)", "host": "vps",
        "clock": "VPS timer", "cause": "one state file from dig s10 (2026-08-29); the dig's "
        "later output stays on the VPS's orphaned branch",
        "closure": "box_step"},
    "fxmerge": {
        "writer": "Codex video seat (fxmerge track-record recovery)", "host": "vps",
        "clock": "Codex hourly sync", "cause": "one state file (2026-08-27); Codex's sync "
        "commits to desk-sync-clean, orphaned since 2026-09-11",
        "closure": "box_step"},
    "literature": {
        "writer": "box session (READING_LIST.md -> structured hypotheses)", "host": "box",
        "clock": "none: a one-shot donation (2026-09-16)",
        "cause": "a curated corpus with one dated file; the box has pushed no state since "
                 "2026-09-25",
        "closure": "box_step"},
    "firm_mining": {
        "writer": "Claude firm-mining session (docs/research/firm_mining)", "host": "cloud",
        "clock": "none: a one-shot donation (2026-09-27)",
        "cause": "five files written once, all stamped the same day",
        "closure": "box_step"},
    "mql5_catalog": {
        "writer": "Codex MQL5 prospector", "host": "vps", "clock": "Codex prospector runs",
        "cause": "last pushed 2026-08-28; its host commits to the orphaned desk-sync-clean",
        "closure": "box_step"},
    "mql5_prospector": {
        "writer": "Codex MQL5 prospector", "host": "vps", "clock": "Codex prospector runs",
        "cause": "last pushed 2026-08-26; its host commits to the orphaned desk-sync-clean",
        "closure": "box_step"},
    "scheduled_chatgpt": {
        "writer": "scheduled ChatGPT seat (external)", "host": "external",
        "clock": "the seat's own schedule", "cause": "last donation 2026-08-28; the seat "
        "writes through a session that pushes, and none has since",
        "closure": "box_step"},
    "mql5_reputation": {
        "writer": "desks/mt5/side_channels/sources/strategy/mql5_reputation.py",
        "host": "vps", "clock": "seed_miners (quant-seed-miners.service, hourly)",
        "cause": "MQL5ReputationTracker had NO caller: its only rows are four `test_author` "
                 "rows from 2026-08-24; seed_miners now records every MQL5 miner's output "
                 "through it",
        "closure": "wired (seed_miners.record_mql5_reputation) + box_step"},
}

#: The box step every `box_step` closure shares (the VPS and session hosts reach git only by a
#: push to the LIVE branch, which the orphaned desk-sync-clean cannot give them).
BOX_STEP = ("on the box (and the VPS): commit and push the seat directories under "
            "data/intelligence/ and desks/mt5/data/intelligence/ plus desks/mt5/data/"
            "dataset_stamps/ to claude/llm-auto-upgrade-verify-gcjac3 (the box's hourly state "
            "commit; the VPS's seed_miners/hourly-controller output needs "
            "ops/pull_desk_state.sh run the other way or the VPS repointed at the live branch)")


def record_run(seat: str, donated: int, *, organ: str, tests_run: int | None = None,
               now: datetime | None = None, stamps: Path | None = None) -> Path | None:
    """A seat writer's reading for a run that DONATED NOTHING: zero rows at this instant, the
    organ named. A run that donated writes its own dated file, which is that run's reading, so
    this writes nothing then. Outside data/intelligence/ on purpose (the compiler never reads
    it). Never raises: a writer must not fail for its reading."""
    if donated:
        return None
    try:
        now = now or datetime.now(UTC)
        sd = (stamps or STAMPS) / seat
        sd.mkdir(parents=True, exist_ok=True)
        out = sd / f"run_{now:%Y%m%d_%H%M%S}.json"
        doc = {"seat": seat, "organ": organ, "donated": 0, "tests_run": tests_run,
               "basis": "the writer ran at this time and donated no row: a zero reading",
               "rows": []}
        tmp = sd / (out.name + ".tmp")
        tmp.write_text(json.dumps(doc), "utf-8")
        os.replace(tmp, out)
        return out
    except Exception:
        return None


def _readings(seat: str, roots: tuple[Path, ...] | None = None) -> int:
    """Distinct stamps a seat holds across every intelligence root (stamps included)."""
    from mt5desk import dataset_series as DS
    dirs = DS.intel_dirs(seat, roots)
    return len({t for t, _p in DS.snapshot_files(dirs, 0)})


def stamp_git_activity(now: datetime | None = None, *, stamps: Path | None = None,
                       roots: tuple[Path, ...] | None = None,
                       min_readings: int = MIN_READINGS) -> dict[str, Any]:
    """For every seat under `min_readings`, one reading per commit that MODIFIED a file already in
    the seat (a rewrite in place): `[{"file": <name>}, ...]` at the commit time, so `_rows` is how
    many records the seat rewrote then. An ADDED file is already its own reading (its name's
    stamp) and is never counted twice. Incremental and idempotent through the seat's ledger."""
    from mt5desk import dataset_series as DS
    now = now or datetime.now(UTC)
    base = stamps or STAMPS
    live_roots = roots or tuple(r for r in DS.INTEL_ROOTS if r != DS.STAMPS_ROOT)
    seats = sorted({d.name for r in live_roots if r.is_dir() for d in r.iterdir()
                    if d.is_dir() and not d.name.startswith((".", "_"))})
    out: dict[str, Any] = {}
    for seat in seats:
        # A seat with no name-stamped file of its own is `run()`'s: every git version of its
        # state files is already a digest there, so its rewrites are never read twice.
        if not DS.snapshot_files([r / seat for r in live_roots if (r / seat).is_dir()], 0):
            continue
        have_n = _readings(seat, (*live_roots, base))
        if have_n >= min_readings:
            continue
        rels = []
        for r in live_roots:
            d = r / seat
            if d.is_dir():
                try:
                    rels.append(str(d.resolve().relative_to(ROOT)).replace("\\", "/"))
                except ValueError:
                    continue
        if not rels:
            continue
        try:
            log = subprocess.run(["git", "-C", str(ROOT), "log", "--diff-filter=M",
                                  "--format=\x1f%H %cI", "--name-only", "--", *rels],
                                 capture_output=True, text=True, timeout=120,
                                 check=False).stdout
        except (OSError, subprocess.SubprocessError):
            out[seat] = {"status": "UNMEASURED: git unavailable"}
            continue
        commits: list[tuple[str, datetime, list[str]]] = []
        for block in log.split("\x1f"):
            lines = [ln.strip() for ln in block.splitlines() if ln.strip()]
            if not lines:
                continue
            sha, _, when = lines[0].partition(" ")
            try:
                t = datetime.fromisoformat(when.strip()).astimezone(UTC)
            except ValueError:
                continue
            commits.append((sha, t, [Path(x).name for x in lines[1:]]))
        sd = base / seat
        led_p = sd / "_activity_ledger.json"
        try:
            seen = set(json.loads(led_p.read_text("utf-8")).get("commits") or [])
        except (OSError, ValueError):
            seen = set()
        wrote = 0
        for sha, t, files in sorted(commits, key=lambda c: c[1]):
            if sha in seen or wrote >= ACTIVITY_PER_PASS or not files:
                continue
            sd.mkdir(parents=True, exist_ok=True)
            name = f"stamp_{t:%Y%m%d_%H%M%S}_git-activity.json"
            doc = [{"file": f, "basis": f"git commit {sha[:10]} rewrote it in place"}
                   for f in sorted(set(files))]
            tmp = sd / (name + ".tmp")
            tmp.write_text(json.dumps(doc), "utf-8")
            os.replace(tmp, sd / name)
            seen.add(sha)
            wrote += 1
        if wrote:
            led_p.write_text(json.dumps({"seat": seat, "commits": sorted(seen),
                                         "rule": "modifying commits already stamped"},
                                        indent=1), "utf-8")
        out[seat] = {"readings_before": have_n, "modifying_commits": len(commits),
                     "stamped_now": wrote}
    return out


def writer_census(roots: tuple[Path, ...] | None = None,
                  min_readings: int = MIN_READINGS) -> dict[str, Any]:
    """Every seat under `min_readings` with its writer, host, cause and closure (SEAT_WRITERS),
    and the box step where the closure needs one. A quiet seat with no row names itself
    UNMAPPED: the census never hides one."""
    from mt5desk import dataset_series as DS
    rts = roots or DS.INTEL_ROOTS
    seats = sorted({d.name for r in rts if r.is_dir() for d in r.iterdir()
                    if d.is_dir() and not d.name.startswith((".", "_"))})
    rows: dict[str, Any] = {}
    for seat in seats:
        n = _readings(seat, rts)
        if n >= min_readings:
            continue
        w = SEAT_WRITERS.get(seat)
        rows[seat] = ({"readings": n, **w,
                       **({"box_step": BOX_STEP} if "box_step" in w["closure"] else {})}
                      if w else {"readings": n, "writer": "UNMAPPED",
                                 "closure": "name its writer in seat_stamper.SEAT_WRITERS"})
    return {"min_readings": min_readings, "n_quiet": len(rows), "seats": rows}


def _slug(name: str) -> str:
    return re.sub(r"[^A-Za-z0-9]+", "-", name.rsplit(".", 1)[0]).strip("-")[:40] or "file"


def records_in(blob: bytes, name: str) -> int:
    """How many records a state file holds: a JSONL's lines, a list's items, a mapping's largest
    list (a document's payload, e.g. `rows` or `maps`) or else its keys. 0 when unreadable."""
    if name.endswith(".jsonl"):
        return sum(1 for ln in blob.splitlines() if ln.strip())
    if len(blob) > PARSE_MAX_BYTES:
        return 0
    try:
        if name.endswith((".yaml", ".yml")):
            import yaml
            doc = yaml.safe_load(blob.decode("utf-8", "replace"))
        else:
            doc = json.loads(blob.decode("utf-8", "replace"))
    except Exception:
        return 0
    if isinstance(doc, list):
        return len(doc)
    if isinstance(doc, dict):
        payload = [len(v) for k, v in doc.items() if isinstance(v, (list, dict))
                   and not str(k).startswith("_")]
        # A mapping of records keyed by id (cohort_registry) is its own payload.
        if payload and max(payload) > 1:
            return max(payload) if len(doc) < 64 else len(doc)
        return len(doc)
    return 1


def unstamped_seats(roots: tuple[Path, ...] | None = None) -> dict[str, list[Path]]:
    """{seat: its non-empty state files} for every seat none of whose files is name-stamped."""
    from mt5desk import dataset_series as DS
    roots = roots or tuple(r for r in DS.INTEL_ROOTS if r != DS.STAMPS_ROOT)
    seats = sorted({d.name for r in roots if r.is_dir() for d in r.iterdir()
                    if d.is_dir() and not d.name.startswith((".", "_"))})
    out: dict[str, list[Path]] = {}
    for seat in seats:
        dirs = [r / seat for r in roots if (r / seat).is_dir()]
        if DS.snapshot_files(dirs, 0):
            continue
        files = [p for d in dirs for p in sorted(d.iterdir()) if p.is_file()
                 and p.name.endswith(_SUFFIXES) and p.stat().st_size > 2]
        if files:
            out[seat] = files
    return out


def _git_versions(path: Path) -> list[tuple[str, datetime]]:
    try:
        rel = str(path.resolve().relative_to(ROOT)).replace("\\", "/")
        out = subprocess.run(["git", "-C", str(ROOT), "log", "--format=%H %cI", "--", rel],
                             capture_output=True, text=True, timeout=120, check=False).stdout
    except (OSError, subprocess.SubprocessError, ValueError):
        return []
    got: list[tuple[str, datetime]] = []
    for ln in out.splitlines():
        sha, _, when = ln.partition(" ")
        try:
            got.append((sha, datetime.fromisoformat(when.strip()).astimezone(UTC)))
        except ValueError:
            continue
    return sorted(got, key=lambda t: t[1])


def _git_blob(sha: str, path: Path) -> bytes | None:
    try:
        rel = str(path.resolve().relative_to(ROOT)).replace("\\", "/")
        r = subprocess.run(["git", "-C", str(ROOT), "show", f"{sha}:{rel}"],
                           capture_output=True, timeout=120, check=False)
    except (OSError, subprocess.SubprocessError, ValueError):
        return None
    return r.stdout if r.returncode == 0 else None


def _write_stamp(seat_dir: Path, when: datetime, f: Path, blob: bytes, basis: str) -> str:
    seat_dir.mkdir(parents=True, exist_ok=True)
    name = f"stamp_{when:%Y%m%d_%H%M%S}_{_slug(f.name)}.json"
    doc = [{"file": f.name, "records": records_in(blob, f.name), "bytes": len(blob),
            "basis": basis}]
    tmp = seat_dir / (name + ".tmp")
    tmp.write_text(json.dumps(doc), "utf-8")
    os.replace(tmp, seat_dir / name)
    return name


def run(now: datetime | None = None, *, stamps: Path | None = None,
        roots: tuple[Path, ...] | None = None, git: bool = True) -> dict[str, Any]:
    """Stamp every unstamped seat: its git versions (backfill, incremental) and its current
    content when this organ has not seen it. Returns the census of what was written."""
    now = now or datetime.now(UTC)
    base = stamps or STAMPS
    report: dict[str, Any] = {"generated_at": now.isoformat(timespec="seconds"), "seats": {}}
    for seat, files in unstamped_seats(roots).items():
        sd = base / seat
        led_p = sd / "_ledger.json"
        try:
            led = json.loads(led_p.read_text("utf-8"))
        except (OSError, ValueError):
            led = {}
        seen: dict[str, list[str]] = dict(led.get("seen") or {})
        wrote: list[str] = []
        for f in files:
            key = f.name
            have = set(seen.get(key) or [])
            if git:
                n = 0
                for sha, when in _git_versions(f):
                    if f"git:{sha}" in have or n >= BACKFILL_PER_PASS:
                        continue
                    blob = _git_blob(sha, f)
                    have.add(f"git:{sha}")
                    if blob is None:
                        continue
                    have.add(hashlib.sha256(blob).hexdigest())
                    wrote.append(_write_stamp(sd, when, f, blob,
                                              f"git commit {sha[:10]}: the desk held this "
                                              "version at or before its commit time"))
                    n += 1
            try:
                blob = f.read_bytes()
            except OSError:
                continue
            h = hashlib.sha256(blob).hexdigest()
            if h not in have:
                have.add(h)
                wrote.append(_write_stamp(sd, now, f, blob,
                                          "content first seen by seat_stamper at this time"))
            seen[key] = sorted(have)
        if wrote or not led_p.exists():
            sd.mkdir(parents=True, exist_ok=True)
            led_p.write_text(json.dumps({"seat": seat, "seen": seen,
                                         "rule": "versions already stamped; never rewritten"},
                                        indent=1), "utf-8")
        report["seats"][seat] = {"files": [f.name for f in files], "stamped_now": len(wrote)}
    report["n_seats"] = len(report["seats"])
    if git:
        try:
            report["git_activity"] = stamp_git_activity(now, stamps=base, roots=roots)
        except Exception as exc:
            report["git_activity"] = {"status": f"UNMEASURED: {type(exc).__name__}"}
    try:
        from mt5desk import dataset_series as DS
        live = roots or tuple(r for r in DS.INTEL_ROOTS if r != DS.STAMPS_ROOT)
        report["quiet_writers"] = writer_census((*live, base))
    except Exception as exc:
        report["quiet_writers"] = {"status": f"UNMEASURED: {type(exc).__name__}"}
    return report


if __name__ == "__main__":
    print(json.dumps(run(), indent=1))
