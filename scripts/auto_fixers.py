"""IMMEDIATE, DETERMINISTIC FIXERS -- one per breach class, invoked the moment a fence fires.

WHY (principal 2026-08-27: "watchdogs for everything possible and fixers as frequent and
immediate as possible"). The repair organ (gap-wirer) is an ANALYST: it reads a breach, thinks,
and patches -- on a 6-hour cooldown, and it was OOM-dead for half a day without anyone noticing.
Most breaches never needed analysis: a dead searcher needs its lock cleared and its task
triggered; an empty docket needs the merge re-run and shipped; a stale gauntlet needs
`schtasks /Run`. Those are FIRST-AID actions -- deterministic, idempotent, safe to repeat --
and waiting six hours to apply them is a human loop with extra steps.

DISCIPLINE. Every fixer is rate-limited per class (one attempt per FIX_COOLDOWN_MIN, journaled
to data/auto_fixer_state.json and the pulse), records outcome honestly (FIXED / ATTEMPTED /
FAILED), and never touches the money path: the gateway, the deadman and live orders have no
fixer here and never will. A fixer that fails leaves the breach standing and loud for the
gap-wirer and the dashboard; it never eats the breach.
"""
from __future__ import annotations

import json
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DESK = ROOT / "desks" / "mt5"
STATE = ROOT / "data" / "auto_fixer_state.json"
REMOTE = "contabo-mt5"
FIX_COOLDOWN_MIN = 40
SSH_TIMEOUT = 90


def _read_state() -> dict:
    try:
        return json.loads(STATE.read_text("utf-8"))
    except (OSError, ValueError):
        return {}


def _run(cmd: list[str], timeout: int = SSH_TIMEOUT) -> tuple[int, str]:
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, check=False)
        return r.returncode, (r.stdout + r.stderr)[-400:]
    except subprocess.TimeoutExpired:
        return 124, "timeout"
    except OSError as exc:
        return 1, str(exc)


def _ssh(command: str) -> tuple[int, str]:
    return _run(["ssh", "-o", "ConnectTimeout=20", REMOTE, command])


def _desk_task(name: str) -> tuple[bool, str]:
    """Enable + start a desk scheduled task. IgnoreNew on every research task makes this safe."""
    rc, out = _ssh(f"powershell -Command \"Enable-ScheduledTask -TaskName {name} "
                   f"-ErrorAction SilentlyContinue | Out-Null; schtasks /Run /TN {name}\"")
    return rc == 0, out.strip()[-160:]


def _clear_lock(job: str) -> None:
    _ssh(f"cmd /c del /q C:\\opt\\quant\\desks\\mt5\\data\\.job_locks\\{job}.json 2>nul")


# ----------------------------------------------------------------------------- fixers by class
def fix_search() -> tuple[bool, str]:
    """Dead family-free searcher: clear a possibly-orphaned lock, run the leg on the desk."""
    _clear_lock("edge_search")
    ok, out = _desk_task("MT5-Hourly")     # the desk hourly runs the search leg with its inputs
    rc, _out2 = _ssh("cmd /c \"cd /d C:\\opt\\quant\\desks\\mt5 && "
                    "start /b py -3 -W ignore research\\edge_search.py\"")
    return (ok or rc == 0), f"lock cleared; task={out} direct_rc={rc}"


def fix_sweep() -> tuple[bool, str]:
    _clear_lock("orthogonal_sweep")
    rc, out = _ssh("cmd /c \"cd /d C:\\opt\\quant\\desks\\mt5 && "
                   "start /b py -3 -W ignore research\\orthogonal_sweep.py\"")
    return rc == 0, f"lock cleared; direct_rc={rc} {out[-80:]}"


def fix_docket() -> tuple[bool, str]:
    """Empty/stale docket: re-run the merge from whatever sources are fresh, ship if non-empty."""
    rc, out = _run([sys.executable, str(DESK / "research" / "merge_hypotheses.py")], timeout=180)
    if rc != 0:
        return False, f"merge rc={rc}: {out[-160:]}"
    try:
        rows = json.loads((DESK / "data/hypotheses/external_survivors.json").read_text("utf-8"))
    except (OSError, ValueError):
        return False, "merge ran but docket unreadable"
    if not rows:
        return False, "merge ran; zero rows (sources dry -- upstream fixers own this)"
    rc2, _ = _run(["scp", "-q", str(DESK / "data/hypotheses/external_survivors.json"),
                   f"{REMOTE}:C:/opt/quant/desks/mt5/data/hypotheses/external_survivors.json"])
    return rc2 == 0, f"merged {len(rows)} rows, shipped rc={rc2}"


def fix_gauntlet() -> tuple[bool, str]:
    ok, out = _desk_task("MT5-Gauntlet")
    return ok, out


def fix_shadow() -> tuple[bool, str]:
    ok, out = _desk_task("MT5-Shadow")
    return ok, out


def fix_moat_builder() -> tuple[bool, str]:
    ok, out = _desk_task("MT5-DeskState")
    return ok, out


def fix_moat_tape() -> tuple[bool, str]:
    ok1, o1 = _desk_task("MT5-MoatRecorder")
    ok2, o2 = _desk_task("MT5-MoatSilver")
    return ok1 or ok2, f"recorder={o1[-60:]} silver={o2[-60:]}"


def fix_miners() -> tuple[bool, str]:
    rc, out = _run([sys.executable, str(DESK / "research" / "mined_ground.py")], timeout=180)
    return rc == 0, out[-160:]


def fix_stall_watch() -> tuple[bool, str]:
    ok, out = _desk_task("MT5-StallWatch")
    return ok, out


def fix_forward() -> tuple[bool, str]:
    """Clocks ACTIVE but no evidence accruing: run a shadow pass now and let its own guards
    (coverage refusal, terminal statuses) decide per sleeve. Never touches verdicts."""
    ok, out = _desk_task("MT5-Shadow")
    return ok, out


def fix_pull() -> tuple[bool, str]:
    """Desk->VPS artery down: restart the pull unit, re-trigger the desk-side builder."""
    rc, _out = _run(["systemctl", "--user", "restart", "quant-desk-pull.service"], timeout=120)
    ok2, o2 = _desk_task("MT5-DeskState")
    return rc == 0 or ok2, f"pull_restart_rc={rc} builder={o2[-60:]}"


def fix_data_macro() -> tuple[bool, str]:
    """Stale macro state: re-run the producer; free_data now routes FRED -> DBnomics mirror."""
    rc, out = _run([sys.executable, str(DESK / "research" / "macro_desk.py")], timeout=420)
    return rc == 0, out[-160:]


def fix_data_cot() -> tuple[bool, str]:
    """Refresh the MT5 desk's COT z-cache INCREMENTALLY from CFTC's fast API.

    Three defects lived on this one path. quant-cot-fetch writes data/cot/{btc,eth}.parquet --
    retired crypto ground -- while the FX/metal `cot_positioning` family reads
    data/cot_zcache.parquet, so the fence 'fixed' COT every pass while the watched file sat 67
    days stale (a fixer aimed at the wrong artifact is worse than none: the breach looks
    attended). run_cot_screen, the only other candidate, is READER-FIRST and re-screens the
    stale cache reporting success. And rebuilding from the 26 years of history zips takes long
    enough that every fixer attempt timed out and correctly restored the stale file -- endless
    motion, zero progress. refresh_cot_zcache appends only the missing weeks from Socrata:
    seconds, not minutes, and banked history can never be lost to a bad fetch.
    """
    rc, out = _run([sys.executable, str(ROOT / "scripts" / "refresh_cot_zcache.py")],
                   timeout=300)
    return rc == 0, out[-200:]


def fix_data_events() -> tuple[bool, str]:
    rc, out = _run(["systemctl", "--user", "start", "quant-seed-miners.service"], timeout=60)
    return rc == 0, out[-120:] or "calendar/miner seed unit started"


def fix_clocks() -> tuple[bool, str]:
    """Blocked sleeves: run the desk watchdog first (it restores a shrunken registry and other
    local causes), then a shadow pass so the healed inputs are actually used this cycle."""
    ok1, o1 = _desk_task("MT5-StallWatch")
    ok2, o2 = _desk_task("MT5-Shadow")
    return ok1 or ok2, f"stallwatch={o1[-50:]} shadow={o2[-50:]}"


def fix_breadth() -> tuple[bool, str]:
    """A class the docket never covers: re-run mined ground and the class-balanced searcher so
    the next rotation reaches it. Never narrows the hunt -- it widens the pass."""
    rc1, _o1 = _run([sys.executable, str(DESK / "research" / "mined_ground.py")], timeout=180)
    ok2, o2 = fix_search()
    return rc1 == 0 or ok2, f"mined_ground_rc={rc1} search={o2[-80:]}"


def fix_families() -> tuple[bool, str]:
    """A family unreachable from a door is a wiring defect: re-run the stage so its
    auto-discovery re-reads the registry, and page if it is still short."""
    rc, out = _run([sys.executable, str(DESK / "side_channels" / "run_external_backtest.py")],
                   timeout=600)
    return rc == 0, out[-160:]


FIXERS = {
    "FAMILIES": fix_families,
    "BREADTH": fix_breadth,
    "BACKLOG": fix_gauntlet,
    "QUEUES": None,          # bound below once the converter is defined
    "CLOCKS": fix_clocks,
    "DATA-MACRO": fix_data_macro,
    "DATA-COT": fix_data_cot,
    "DATA-EVENTS": fix_data_events,
    "PULL": fix_pull,
    "SEARCH": fix_search,
    "SWEEP": fix_sweep,
    "DOCKET": fix_docket,
    "GAUNTLET": fix_gauntlet,
    "SHADOW": fix_shadow,
    "FORWARD": fix_forward,
    "MOAT-BUILDER": fix_moat_builder,
    "MOAT": fix_moat_tape,
    "MINERS": fix_miners,
    "STALL-WATCH": fix_stall_watch,
}


def fix_queues() -> tuple[bool, str]:
    """Unconsumed question queues -> research-queue cards, so the brains actually meet them."""
    rc, out = _run([sys.executable, str(ROOT / "scripts" / "convert_question_queues.py")],
                   timeout=120)
    return rc == 0, out[-160:]


FIXERS["QUEUES"] = fix_queues


def apply(breaches: list[str]) -> list[dict]:
    """Run the fixer for each breached class, rate-limited; return the action journal rows."""
    now = datetime.now(tz=UTC)
    state = _read_state()
    last: dict = state.get("last_attempt", {})
    journal: list[dict] = state.get("journal", [])
    actions: list[dict] = []

    classes: list[str] = []
    for b in breaches:
        cls = b.split(":", 1)[0].strip()
        # MOAT summary-stale vs tape-dead are different fixes; disambiguate on the message.
        if cls == "MOAT" and "coverage summary" in b:
            cls = "MOAT-BUILDER"
        if cls in FIXERS and cls not in classes:
            classes.append(cls)

    for cls in classes:
        prev = last.get(cls)
        if prev:
            try:
                age_min = (now - datetime.fromisoformat(prev)).total_seconds() / 60
                if age_min < FIX_COOLDOWN_MIN:
                    actions.append({"class": cls, "outcome": "COOLDOWN",
                                    "detail": f"last attempt {age_min:.0f}m ago"})
                    continue
            except ValueError:
                pass
        ok, detail = FIXERS[cls]()
        last[cls] = now.isoformat(timespec="seconds")
        row = {"at": now.isoformat(timespec="seconds"), "class": cls,
               "outcome": "ATTEMPTED" if ok else "FAILED", "detail": detail}
        actions.append(row)
        journal.append(row)
        print(f"  FIXER {cls}: {'attempted' if ok else 'FAILED'} -- {detail[:140]}")

    STATE.parent.mkdir(parents=True, exist_ok=True)
    STATE.write_text(json.dumps({"last_attempt": last, "journal": journal[-400:]},
                                indent=1), "utf-8")
    return actions


if __name__ == "__main__":
    # manual invocation: fix the classes named on argv, e.g. `auto_fixers.py SEARCH DOCKET`
    named = [f"{c}: manual" for c in sys.argv[1:] if c in FIXERS]
    if not named:
        print("usage: auto_fixers.py CLASS [CLASS...]  --", ", ".join(sorted(FIXERS)))
        raise SystemExit(2)
    apply(named)
