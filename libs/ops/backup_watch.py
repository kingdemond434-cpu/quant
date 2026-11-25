"""The guardian's backup watch: a backup that has gone stale pages, and the guardian restarts it.

WHY (rule E40, 2026-11-25). The 6h pass's unknowns probe found the box had never been backed up:
MT5-OffsiteBackup existed in code since 2026-09-30, waited for an operator switch nobody pressed,
and recorded NOT_ARMED into a report nobody read. Nothing paged. This leg reads
desks/mt5/reports/OFFSITE_BACKUP.json every 15 minutes and judges it:

    NO_REPORT       the backup job has never written its report
    NOT_ARMED / NO_RESTIC / FAIL   the job's own status
    STALE           no successful snapshot for 12h (the job runs every 6h)
    CHECK_STALE     no passing `restic check` read-back in 8 days
    DRILL_STALE     no passing restore drill in 8 days
    LOCAL_ONLY      snapshots exist only on this box (repaged daily, not every 6h)
    KEY_NOT_ESCROWED the repository password is not attested as held off the box
    OFFSITE_KEY_UNREGISTERED  GitLab refused the box's own deploy key (register
                    desks/mt5/reports/BACKUP_DEPLOY_KEY.pub on the drop project, push allowed)

Repair (bounded, at most every 2h): `schtasks /Run MT5-OffsiteBackup`; if the task does not exist,
the installer (desks/mt5/scripts/install_offsite_backup_task.ps1, no switches: the job arms
itself) re-registers it. A backup never touches the money path, so starting it is always safe.
Pages "BACKUP WATCH:" on a change of shape, every 6h while broken, daily while only LOCAL_ONLY or
KEY_NOT_ESCROWED. Writes desks/mt5/reports/BACKUP_WATCH.json. No Claude dependency.
"""
from __future__ import annotations

import json
import subprocess
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

SCHEMA = "backup_watch/1"
REPORT_REL = "desks/mt5/reports/OFFSITE_BACKUP.json"
OUT_REL = "desks/mt5/reports/BACKUP_WATCH.json"
STATE_REL = "desks/mt5/data/BACKUP_WATCH_STATE.json"
TASK = "MT5-OffsiteBackup"
INSTALLER_REL = "desks/mt5/scripts/install_offsite_backup_task.ps1"
SNAPSHOT_MAX = timedelta(hours=12)
VERIFY_MAX = timedelta(days=8)
REPAIR_EVERY = timedelta(hours=2)
REPAGE_BROKEN = timedelta(hours=6)
REPAGE_SOFT = timedelta(hours=24)
#: Flags that mean "a copy exists and reads back, but it is not yet safe from losing the box".
SOFT = frozenset({"LOCAL_ONLY", "KEY_NOT_ESCROWED"})
#: Flags the guardian repairs by starting the job.
REPAIRABLE = frozenset({"NO_REPORT", "NOT_ARMED", "NO_RESTIC", "FAIL", "STALE"})


def _ts(v: Any) -> datetime | None:
    if not v:
        return None
    try:
        t = datetime.fromisoformat(str(v).replace("Z", "+00:00"))
    except ValueError:
        return None
    return t if t.tzinfo else t.replace(tzinfo=UTC)


def _read(p: Path) -> dict[str, Any]:
    try:
        d = json.loads(p.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return d if isinstance(d, dict) else {}


def judge(doc: dict[str, Any], now: datetime) -> list[str]:
    """Every flag that holds for this OFFSITE_BACKUP.json. Empty = PASS. Pure."""
    if not doc:
        return ["NO_REPORT"]
    flags: list[str] = []
    st = str(doc.get("status") or "")
    if st in ("NOT_ARMED", "NO_RESTIC", "FAIL"):
        flags.append(st)
    last = _ts(doc.get("last_success_at"))
    if last is None or now - last > SNAPSHOT_MAX:
        flags.append("STALE")
    chk = _ts(doc.get("last_check_at"))
    if chk is None or now - chk > VERIFY_MAX or not doc.get("last_check_ok"):
        flags.append("CHECK_STALE")
    raw = doc.get("restore_drill")
    rd: dict[str, Any] = raw if isinstance(raw, dict) else {}
    rd_at = _ts(rd.get("at"))
    if rd_at is None or now - rd_at > VERIFY_MAX or rd.get("verdict") != "PASS":
        flags.append("DRILL_STALE")
    if doc.get("offsite") is not True:
        flags.append("LOCAL_ONLY")
    raw_og = doc.get("offsite_git")
    og: dict[str, Any] = raw_og if isinstance(raw_og, dict) else {}
    if og.get("key_unregistered"):
        # the box made its deploy key and published BACKUP_DEPLOY_KEY.pub; GitLab refuses it
        # until it is registered on the drop project with push
        flags.append("OFFSITE_KEY_UNREGISTERED")
    if not doc.get("key_escrowed_off_box"):
        flags.append("KEY_NOT_ESCROWED")
    return flags


def _run(cmd: list[str]) -> bool:
    try:
        p = subprocess.run(cmd, capture_output=True, text=True, timeout=300, check=False)
    except (OSError, subprocess.TimeoutExpired):
        return False
    return p.returncode == 0


def repair(root: Path, runner: Callable[[list[str]], bool] = _run) -> str:
    """Start the backup job; if that fails, re-register it, then start it."""
    if runner(["schtasks.exe", "/Run", "/TN", TASK]):
        return "started"
    inst = root / INSTALLER_REL
    if inst.exists() and runner(["powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass",
                                 "-File", str(inst)]):
        return "registered+started" if runner(["schtasks.exe", "/Run", "/TN", TASK]) \
            else "registered"
    return "failed"


def run_once(root: Path, *, now: datetime | None = None,
             runner: Callable[[list[str]], bool] = _run,
             page: Callable[[str], None] | None = None) -> dict[str, Any]:
    now = now or datetime.now(UTC)
    doc = _read(root / REPORT_REL)
    flags = judge(doc, now)
    st_path = root / STATE_REL
    state = _read(st_path)
    repaired = None
    last_rep = _ts(state.get("repaired_at"))
    if set(flags) & REPAIRABLE and (last_rep is None or now - last_rep >= REPAIR_EVERY):
        repaired = repair(root, runner)
        state["repaired_at"], state["repair"] = now.isoformat(), repaired
    hard = [f for f in flags if f not in SOFT]
    verdict = "PASS" if not flags else ("BROKEN" if hard else "SOFT")
    out = {"schema": SCHEMA, "at": now.isoformat(), "verdict": verdict, "flags": flags,
           "status": doc.get("status"), "last_success_at": doc.get("last_success_at"),
           "last_check_at": doc.get("last_check_at"),
           "restore_drill": (doc.get("restore_drill") or {}).get("verdict")
           if isinstance(doc.get("restore_drill"), dict) else None,
           "offsite": doc.get("offsite"), "scheme": doc.get("scheme"),
           "included_n": len(doc.get("included") or []), "missing": doc.get("missing") or [],
           "repair": repaired, "last_repair": state.get("repair")}
    key = "|".join(flags)
    paged_at = _ts(state.get("paged_at"))
    every = REPAGE_BROKEN if hard else REPAGE_SOFT
    if flags and page is not None and (key != state.get("paged_key") or paged_at is None
                                       or now - paged_at > every):
        page(f"BACKUP WATCH: box backup {verdict}: {', '.join(flags)}. Last snapshot "
             f"{doc.get('last_success_at') or 'never'}; restore drill "
             f"{out['restore_drill'] or 'never'}. "
             f"Repair: {repaired or state.get('repair') or 'none'}. Detail: {OUT_REL}")
        state["paged_at"], state["paged_key"] = now.isoformat(), key
    elif not flags:
        state.pop("paged_key", None)
    for p, d in ((root / OUT_REL, out), (st_path, state)):
        p.parent.mkdir(parents=True, exist_ok=True)
        tmp = p.with_suffix(p.suffix + ".tmp")
        tmp.write_text(json.dumps(d, indent=1, sort_keys=True, default=str), encoding="utf-8")
        tmp.replace(p)
    return out
