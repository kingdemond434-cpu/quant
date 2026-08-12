"""DESK STATE THAT SURVIVES A FRESH CLONE — and never lies about how old it is.

THE PROBLEM, asked by the principal directly: why can a container session not measure the desk?

Because `data/` is gitignored (`.gitignore:11`), nothing under it travels with a clone. But the
measured answer is sharper than "the files are missing", and the sharper version is the one that
matters -- MEASURED on this container 2026-08-12:

    26 of 27 measurement artifacts ARE present. 23 of them are OLDER THAN 48 HOURS.
    promotion_queue.json is 12.5 DAYS old. gate0_readiness.json is 12.2 days.

They survive because a container reset reverts TRACKED files and leaves untracked ones on disk,
so `data/` accumulates a fossil layer: real files, real shapes, real numbers, all long dead. The
capability ratchet then reads them without asking their age and reports 21 aspects FELL. The
problem was never absence. It was AGE READ AS CURRENCY -- the same failure recorded on 2026-08-05
when a four-day-stale conversion file scored 0.276 against a live 0.431, and far more dangerous
than a missing file because a missing file at least announces itself.

THE FIX IS THE PATTERN THE DESK ALREADY USES. Nineteen files are force-added under `data/`
despite the ignore rule — CAPABILITY_RATCHET.json, decision_ledger.json, gate0_signoff.json and
others. They are kilobyte JSON reports and they travel with the clone. `scripts/sync_desk_state.py`
extends that set to the measurement artifacts, so a fresh container inherits the desk's last known
state instead of an empty directory.

WHAT MAKES THIS SAFE RATHER THAN A NEW WAY TO LIE. A committed snapshot is POINT-IN-TIME by
construction, and scoring a three-day-old snapshot as current fact is the exact failure above,
merely relocated. So `read()` never returns a bare payload:

    LIVE      the file is in data/ on this box. This is PROVENANCE, NOT FRESHNESS -- it means
              something produced it here once, and says nothing about when.
    SNAPSHOT  the file came from the committed mirror. Carries source_age_h from the VPS mtime,
              NOT from the git checkout time -- a clone is seconds old and the data inside it may
              be days old, and conflating those is the whole trap.
    ABSENT    neither exists. UNMEASURED, never zero.

A consumer that wants to score MUST pass `max_age_h` and handle STALE. There is deliberately no
way to read a snapshot without learning its age.

WHAT IS NEVER SYNCED: the ~10GB moat tape, anything under data/secrets, and any file above the
size cap. The snapshot is a MEASUREMENT MIRROR, not a backup, and a repo is not a place to put
credentials or a depth tape.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

__all__ = ["MANIFEST", "SNAPSHOT_DIR", "State", "manifest", "read", "syncable"]

_ROOT = Path(__file__).resolve().parents[2]
SNAPSHOT_DIR = "docs/state"
MANIFEST = "docs/state/MANIFEST.json"

#: Per-file cap. These are measurement REPORTS; anything larger is a data store and does not
#: belong in git. 2 MB is generous for JSON and small enough that a clone stays fast.
MAX_BYTES = 2_000_000

#: The artifacts the capability ratchet, gate board and audit actually read. Extending this list
#: is how a future organ's output becomes measurable from a container.
SYNC_SET: tuple[str, ...] = (
    "max_audit_report.json", "organ_liveness.json", "organ_er.json", "miner_runway.json",
    "mechanism_census.json", "mutation_score.json", "conversion_status.json",
    "calibration_status.json", "promotion_queue.json", "replacement_rate.json",
    "backup_status.json", "utilisation.json", "gate0_readiness.json", "exploration_status.json",
    "data_assets.json", "wiring_agent.json", "fence_yield.json", "execution_economics.json",
    "cost_hunt.json", "clock_provenance_status.json", "trading_playbook.json",
    "scheduler_manifest_report.json", "instrumentation_chase.json", "source_health.jsonl",
    "alert_delivery.jsonl", "miner_yield.jsonl", "instrumentation_coverage.jsonl",
)

#: Never synced, whatever else changes. Credentials and the moat tape are not measurement.
NEVER_SYNC: tuple[str, ...] = ("secrets", "moat", "lake", "inbox", ".sqlite", ".parquet", ".db")


@dataclass(frozen=True)
class State:
    """One artifact, with its provenance attached so it cannot be mistaken for something else."""

    name: str
    source: str                    # LIVE | SNAPSHOT | ABSENT
    payload: Any = None
    source_age_h: float | None = None
    why: str = ""

    @property
    def usable(self) -> bool:
        return self.source in ("LIVE", "SNAPSHOT")

    def fresh_enough(self, max_age_h: float) -> bool:
        """Age-checked for BOTH sources. UNKNOWN age is never fresh.

        LIVE IS NOT A SYNONYM FOR FRESH, and the first version of this method said it was -- it
        returned True for any LIVE file regardless of age. That is the precise bug this module
        exists to prevent, written into the module itself. Measured immediately afterwards on this
        very box: 23 of 27 artifacts are LIVE and older than 48h, with promotion_queue.json at
        12.5 DAYS. Under the original logic every one of them would have been scored as current.

        A file sitting in data/ only means SOMETHING PRODUCED IT HERE ONCE. Whether that was an
        hour ago or a fortnight ago is the entire question, and provenance never answers it.
        """
        if self.source_age_h is None:
            return False
        return self.source_age_h <= float(max_age_h)


def syncable(name: str) -> bool:
    return name in SYNC_SET and not any(bad in name for bad in NEVER_SYNC)


def manifest(root: Path | None = None) -> dict[str, Any]:
    """The snapshot's own record: what was mirrored, and how old each file was AT SYNC TIME."""
    try:
        return json.loads(((root or _ROOT) / MANIFEST).read_text("utf-8"))
    except (OSError, ValueError):
        return {}


def read(name: str, *, root: Path | None = None) -> State:
    """Resolve an artifact LIVE-first, then snapshot, and always say which and how old.

    The age reported for a SNAPSHOT is the source mtime recorded on the VPS at sync time, never
    the checkout time. A fresh clone is seconds old and the numbers inside it may be days old;
    reporting the clone's age would make every stale snapshot look current, which is precisely
    the failure this module exists to prevent.
    """
    base = root or _ROOT
    live = base / "data" / name
    if live.exists() and live.stat().st_size > 0:
        age = (datetime.now(tz=UTC).timestamp() - live.stat().st_mtime) / 3600.0
        return State(name, "LIVE", _load(live), round(age, 2),
                     f"produced on this box {age / 24:.1f} days ago -- provenance, not freshness. "
                     "Score it only against an explicit max_age_h")

    snap = base / SNAPSHOT_DIR / name
    if snap.exists():
        m = manifest(base).get("files", {}).get(name, {})
        age = m.get("source_age_h_at_sync")
        synced = m.get("synced_utc", "")
        extra = 0.0
        try:
            extra = (datetime.now(tz=UTC)
                     - datetime.fromisoformat(str(synced))).total_seconds() / 3600.0
        except ValueError:
            extra = 0.0
        total = round(float(age) + max(0.0, extra), 2) if age is not None else None
        return State(name, "SNAPSHOT", _load(snap), total,
                     f"committed mirror synced {synced or 'at an unrecorded time'}; the age is the "
                     "VPS source age, NOT the clone age -- score it only against an explicit "
                     "max_age_h and treat UNKNOWN age as stale")
    return State(name, "ABSENT", None, None,
                 f"neither data/{name} nor {SNAPSHOT_DIR}/{name} exists -- UNMEASURED, never zero")


def _load(p: Path) -> Any:
    try:
        text = p.read_text("utf-8", errors="ignore")
    except OSError:
        return None
    if p.suffix == ".jsonl":
        out = []
        for line in text.splitlines():
            if line.strip():
                try:
                    out.append(json.loads(line))
                except ValueError:
                    continue
        return out
    try:
        return json.loads(text)
    except ValueError:
        return None


def coverage(root: Path | None = None) -> dict[str, Any]:
    """How much of the desk this box can actually see -- the honest denominator for any claim
    that 'the desk measures X'."""
    rows = [read(n, root=root) for n in SYNC_SET]
    by = {}
    for r in rows:
        by.setdefault(r.source, []).append(r.name)
    live, snap, absent = (len(by.get(k, [])) for k in ("LIVE", "SNAPSHOT", "ABSENT"))
    return {
        "n_artifacts": len(SYNC_SET),
        "live": live, "snapshot": snap, "absent": absent,
        "readable": live + snap,
        "coverage": round((live + snap) / len(SYNC_SET), 3),
        "absent_names": sorted(by.get("ABSENT", []))[:30],
        "why": "an aspect scored off an ABSENT artifact describes this box, not the desk -- which "
               "is why a ratchet run on a fresh container reported 21 aspects FELL",
    }
