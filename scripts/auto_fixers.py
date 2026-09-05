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


#: Lines OpenSSH writes to stderr that say nothing about the command that was run. They were
#: being concatenated into every fixer's report, so a breach summary read
#: "FIXER BREADTH: attempted -- backfill_rc=75 ypt later\" attacks." -- the client's
#: post-quantum advisory sliced mid-word by the 400-character tail. A report a human cannot parse
#: is a report a human stops reading, and these fixer lines are the desk's account of what it did
#: about a breach.
_SSH_NOISE = ("post-quantum", "store now, decrypt later", "openssh.com/pq.html",
              "may need to be upgraded", "This session may be vulnerable")


def _ssh(command: str) -> tuple[int, str]:
    rc, out = _run(["ssh", "-o", "ConnectTimeout=20", REMOTE, command])
    kept = [ln for ln in out.splitlines()
            if ln.strip() and not any(n in ln for n in _SSH_NOISE)]
    return rc, "\n".join(kept)


def _desk_task(name: str) -> tuple[bool, str]:
    """Enable + start a desk scheduled task, and REPORT WHAT IT LAST RETURNED.

    RE-TRIGGERING A FAILING TASK IS NOT HEALING, and the desk has been doing exactly that.
    `schtasks /Run` succeeds whenever the scheduler ACCEPTS the request, so rc==0 says the task
    was started -- never that it worked. Measured on the live dashboard 2026-09-05: the desk's own
    healer journalled `healed: FAILING MT5-Gauntlet: last result 1 twice in a row -- re-run` while
    the canon went 58.3 hours without a sweep. The task was failing, the fixer's answer was to
    start it again, and the answer to a task that returns 1 is never another trigger.

    So the task's OWN last result is read back after the run and carried into the journal. A task
    that returns non-zero is reported as a FAILED fix with the code, not as an attempt that might
    have worked -- which is the same distinction the WITNESS map draws one level up, applied to
    the one repair type where the box can simply be asked.

    LastTaskResult is read AFTER a short settle: `schtasks /Run` is asynchronous, so reading it
    immediately returns the PREVIOUS run's code. Five seconds is not enough for the gauntlet to
    finish -- nothing here waits for that -- but it is enough for a task that dies on startup
    (a missing interpreter, a bad working directory, an unreadable script) to have already
    recorded its code, and startup death is the failure this is trying to surface.
    """
    rc, out = _ssh(f"powershell -Command \"Enable-ScheduledTask -TaskName {name} "
                   f"-ErrorAction SilentlyContinue | Out-Null; schtasks /Run /TN {name}; "
                   f"Start-Sleep -Seconds 5; "
                   f"(Get-ScheduledTaskInfo -TaskName {name}).LastTaskResult\"")
    text = out.strip()
    last = None
    for line in reversed(text.splitlines()):
        token = line.strip()
        if token.lstrip("-").isdigit():
            last = int(token)
            break
    if rc != 0:
        return False, f"trigger failed rc={rc}: {text[-140:]}"
    if last is None:
        # UNMEASURED, not success: the trigger was accepted but the box did not report a code.
        return True, f"started; LastTaskResult UNREADABLE -- {text[-120:]}"
    if last not in (0, 267009):        # 267009 = currently running, which is healthy
        return False, (f"started but the task's LAST RESULT is {last} -- it is FAILING, not "
                       f"unstarted, and another trigger will not fix it: {text[-100:]}")
    return True, f"started; LastTaskResult={last} {text[-100:]}"


def _clear_lock(job: str) -> None:
    _ssh(f"cmd /c del /q C:\\opt\\quant\\desks\\mt5\\data\\.job_locks\\{job}.json 2>nul")


#: A desk-box research process older than this is an orphan, not a long run. edge_search and the
#: gauntlet are bounded by a 25-minute remote-stage timeout, so anything past an hour is a
#: process whose supervisor is already gone.
_ORPHAN_AGE_MIN = 60


def _reap_desk(script: str, older_than_min: int = _ORPHAN_AGE_MIN) -> str:
    """Kill desk-box pythons running `script` that outlived their supervisor. Returns what died.

    WHY EVERY RELAUNCHING FIXER MUST DO THIS FIRST. `timeout ... ssh` kills the SSH CLIENT, not
    the remote process, so a timed-out stage keeps running on the desk box after the pipeline has
    reported it dead. MEASURED 2026-09-02: a gauntlet orphan from 10:44 was still resident at
    11:41 holding 1.3 GB beside a sweep orphan from 10:12; six pythons held 3.1 GB of the box's
    8.4 GB, and edge_search -- which needs ~2000 MB -- found 891 MB and stood down.

    THE FIXERS MADE IT WORSE. `fix_search` cleared the lock and started a SECOND edge_search
    while the first was still resident, so every repair attempt added a process to a box that
    was already starved and the artifact went 9.1 hours stale anyway. Clearing a lock is not
    reclaiming a slot: the lock is a flag, the memory is the constraint.

    MATCHED ON THE SCRIPT NAME and bounded by age, never a blanket python kill -- the same box
    runs the MT5 gateway and the forward engine.
    """
    rc, out = _ssh(
        "powershell -NoProfile -Command \""
        f"$cut = (Get-Date).AddMinutes(-{int(older_than_min)}); "
        "Get-CimInstance Win32_Process -Filter \\\"Name='python.exe'\\\" | "
        f"Where-Object {{ $_.CommandLine -like '*{script}*' -and $_.CreationDate -lt $cut }} | "
        "ForEach-Object { Write-Output ('reaped ' + $_.ProcessId + ' ' + "
        "[math]::Round($_.WorkingSetSize/1MB) + 'MB'); Stop-Process -Id $_.ProcessId -Force }\"")
    return out.strip()[-160:] if rc == 0 else f"reap failed rc={rc}"


# ----------------------------------------------------------------------------- fixers by class
def fix_search() -> tuple[bool, str]:
    """Dead family-free searcher: clear a possibly-orphaned lock, run the leg on the desk."""
    reaped = _reap_desk("edge_search.py")
    _clear_lock("edge_search")
    ok, out = _desk_task("MT5-Hourly")     # the desk hourly runs the search leg with its inputs
    rc, _out2 = _ssh("cmd /c \"cd /d C:\\opt\\quant\\desks\\mt5 && "
                    "start /b py -3 -W ignore research\\edge_search.py\"")
    return (ok or rc == 0), f"{reaped}; lock cleared; task={out} direct_rc={rc}"


def fix_sweep() -> tuple[bool, str]:
    reaped = _reap_desk("orthogonal_sweep.py")
    _clear_lock("orthogonal_sweep")
    rc, out = _ssh("cmd /c \"cd /d C:\\opt\\quant\\desks\\mt5 && "
                   "start /b py -3 -W ignore research\\orthogonal_sweep.py\"")
    return rc == 0, f"{reaped}; lock cleared; direct_rc={rc} {out[-80:]}"


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
    # REAP BEFORE RELAUNCH. The gauntlet is the biggest and longest of the desk-box jobs and the
    # one the pipeline times out at 25 minutes, so it is the most frequent orphan: the 10:44 run
    # was reported TIMED OUT at 11:09 and still held 1.3 GB at 11:41. Starting a second one on
    # top is how the box reaches six resident pythons and stops fitting anything.
    reaped = _reap_desk("external_gauntlet.py")
    ok, out = _desk_task("MT5-Gauntlet")
    return ok, f"{reaped}; task={out}"


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
    """A class the docket never covers: hunt THAT CLASS directly, then widen the general pass.

    Re-running the searcher was not enough and could not have been. The rotation is exactly what
    failed: bonds are 3 symbols out of 299, mined ground fills the head of every run's budget,
    and the cursor can leave a thin class unvisited for days -- so asking the same rotation to go
    again is asking the mechanism that produced the gap to close it. Measured 2026-08-28: the
    docket held 6,024 candidates and zero bonds, while probing those bonds directly returned 67,
    84 and 74 hypotheses. The candidates were always there; nothing had gone to fetch them.

    backfill_coverage runs ON THE DESK BOX because that is where the bars are -- 299 H1 files
    against 203 here -- and it asks which classes are starved rather than being told, so it
    behaves the same way the day equities or softs fall out of the rotation.

    The general widening still runs afterwards: this targets the gap, it does not narrow the hunt.
    """
    rc0, o0 = _ssh("cmd /c \"cd /d C:\\opt\\quant\\desks\\mt5 && "
                   "py -3 -W ignore research\\backfill_coverage.py\"")
    rc1, _o1 = _run([sys.executable, str(DESK / "research" / "mined_ground.py")], timeout=180)
    ok2, o2 = fix_search()
    return (rc0 == 0 or rc1 == 0 or ok2,
            f"backfill_rc={rc0} {o0.strip()[-90:]} | mined_ground_rc={rc1} search={o2[-60:]}")


def fix_families() -> tuple[bool, str]:
    """A family unreachable from a door is a wiring defect: re-run the stage so its
    auto-discovery re-reads the registry, and page if it is still short."""
    rc, out = _run([sys.executable, str(DESK / "side_channels" / "run_external_backtest.py")],
                   timeout=600)
    return rc == 0, out[-160:]


def fix_seats() -> tuple[bool, str]:
    """Re-measure seat yield, then re-fire any owed organ work.

    Never launches a seat blindly: `organ_catchup` is the resume path that knows WHICH organ
    owes WHAT and picks up from the same spot after a quota wall lifts, so the fixer refreshes
    the scorecard and asks catchup to act on it. A seat that is dead for a structural reason
    (no auth of its own, a missing regional key) stays a paged breach -- retrying it forever
    would burn launches and hide the cause.
    """
    rc1, o1 = _run([sys.executable, str(ROOT / "scripts" / "check_seat_launch_yield.py")],
                   timeout=180)
    rc2, o2 = _run(["systemctl", "--user", "start", "quant-organ-catchup.service"], timeout=90)
    return rc1 == 0 or rc2 == 0, f"yield_rc={rc1} catchup_rc={rc2} {(o1 or o2)[-100:]}"


def fix_roi() -> tuple[bool, str]:
    """Falling ROI is a hunting problem: re-measure, then widen (mined ground + searcher)."""
    _run([sys.executable, str(ROOT / "scripts" / "check_dig_roi.py")], timeout=120)
    return fix_breadth()


FIXERS = {
    "ROI": fix_roi,
    "SEATS": fix_seats,
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

#: class -> the artifact that must ADVANCE for the fix to have actually worked.
#:
#: WHY THIS EXISTS (gap-fixer 2026-08-29). `fix_sweep` runs
#: `ssh ... 'cmd /c "... start /b py -3 orthogonal_sweep.py"'` and returns `rc == 0`. `start /b`
#: returns the moment the LAUNCH is accepted, so that rc reports that cmd.exe parsed a command
#: line -- not that python was found, not that the script ran, not that anything was written. It
#: is a launch acknowledgement being recorded as a repair, and it is this desk's most expensive
#: standing lesson: an exit code proves a process ended, never that it produced.
#:
#: MEASURED: `orthogonal_candidates.json` last advanced 2026-08-28T20:05. SWEEP was fixed at
#: 01:33, 02:33 and 03:13 on 08-29, each journaled `ATTEMPTED  lock cleared; direct_rc=0`, and
#: the artifact never moved. The outcome vocabulary was ATTEMPTED / FAILED / COOLDOWN, so a
#: fixer that repairs nothing is indistinguishable -- in the journal AND on the dashboard -- from
#: one that works, and `check_research_health` kept printing the breach beside its own successful
#: first aid every five minutes.
#:
#: A class with NO witness is reported UNWITNESSED, never as success: not knowing whether a
#: repair landed is a different fact from knowing it did (L1.28a), and folding them together is
#: the whole defect one level up.
#: EXTENDED FROM ONE CLASS TO EIGHT, 2026-09-05, and the gap was costing exactly what the note
#: above predicted it would. Twenty-two classes had fixers and ONE had a witness, so twenty-one
#: repairs could report ATTEMPTED forever without anyone able to tell a fixer that works from one
#: that does nothing. Measured on the live dashboard the same day: SEARCH 35.2h stale and GAUNTLET
#: 58.3h stale, both with a fixer wired, both running on the 30-minute health timer, neither
#: repairing anything, and nothing in the desk able to say so -- the SWEEP lesson repeating in the
#: two classes beside it because only SWEEP had been given the instrument.
#:
#: Each entry is the artifact whose staleness IS the breach `check_research_health` prints, so the
#: witness and the complaint cannot drift apart: if the fix worked, the file the breach named has
#: moved. A class stays out of this map only when its repair has no single observable artifact
#: (SEATS, MEMORY, STALL-WATCH), and those keep reporting UNWITNESSED, which is the honest answer
#: rather than a silent pass.
WITNESS: dict[str, Path] = {
    "SWEEP": DESK / "data" / "hypotheses" / "orthogonal_candidates.json",
    "SEARCH": DESK / "data" / "hypotheses" / "edge_search_results.json",
    # GAUNTLET and BACKLOG share `fix_gauntlet`, so they share its witness: the canon's own file,
    # whose `swept_at` is what the breach reads.
    "GAUNTLET": DESK / "reports" / "UNIVERSAL_SURVIVORS.json",
    "BACKLOG": DESK / "reports" / "UNIVERSAL_SURVIVORS.json",
    "DOCKET": DESK / "data" / "hypotheses" / "external_survivors.json",
    "MINERS": DESK / "data" / "hypotheses" / "mined_targets.json",
    "MOAT": DESK / "data" / "moat_coverage.json",
    # SHADOW and PULL both breach on the off-box view being stale, and both fixers exist to make
    # the builder run again; the file it writes is the only thing that proves either did.
    "SHADOW": ROOT / "web" / "desk_state.json",
    "PULL": ROOT / "web" / "desk_state.json",
    # MOAT-BUILDER's fixer runs the MT5-DeskState task, and the state file is the only thing that
    # proves the task did more than start.
    "MOAT-BUILDER": ROOT / "web" / "desk_state.json",
    # CLOCKS: the breach counts BLOCKED rows read out of the off-box desk_state view, NOT out of
    # the registry -- so desk_state is what must advance for the repair to be provable. Caught by
    # `test_every_witness_is_the_artifact_its_own_breach_names` after I first wired this to
    # sleeve_registry.json, which check_research_health never opens: the fix would have been
    # "proved" by a file unrelated to the breach it answered, which is the same class of defect as
    # judging a fixer by its launch.
    "CLOCKS": ROOT / "web" / "desk_state.json",
    # QUEUES is deliberately absent: `check_research_health` raises no QUEUES breach at all, so
    # there is no complaint for a witness to correspond to. Adding one would assert coverage of a
    # thing this organ never reports.
    # The three data feeds each name the artifact their own breach reads, so a re-run that fetched
    # nothing is visible instead of being reported as a repair. ff_calendar_vintage is a
    # DIRECTORY on purpose: its mtime moves when a new vintage lands, which is precisely the
    # event "the feed produced" means here.
    "DATA-MACRO": DESK / "data" / "macro_state.json",
    "DATA-COT": ROOT / "data" / "cot_zcache.parquet",
    "DATA-EVENTS": DESK / "data" / "intelligence" / "ff_calendar_vintage",
}


def _witness_stamp(cls: str) -> float | None:
    """mtime of the class's witness artifact, or None when there is no witness / no file."""
    path = WITNESS.get(cls)
    if path is None:
        return None
    try:
        return path.stat().st_mtime
    except OSError:
        return 0.0     # absent is a real reading: it can still ADVANCE into existence


def apply(breaches: list[str]) -> list[dict]:
    """Run the fixer for each breached class, rate-limited; return the action journal rows."""
    now = datetime.now(tz=UTC)
    state = _read_state()
    last: dict = state.get("last_attempt", {})
    journal: list[dict] = state.get("journal", [])
    witness: dict = state.get("witness", {})
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
        # Did the PREVIOUS attempt on this class actually move anything? Asked now, because the
        # remote job is asynchronous -- `start /b` returns immediately, so the only honest place
        # to judge a launch is the next tick, against the artifact it was supposed to advance.
        before = _witness_stamp(cls)
        prior = witness.get(cls)
        ineffective = 0
        if prior is not None and before is not None and before <= float(prior.get("stamp", 0)):
            ineffective = int(prior.get("ineffective", 0)) + 1

        ok, detail = FIXERS[cls]()
        last[cls] = now.isoformat(timespec="seconds")
        if before is None:
            outcome = "ATTEMPTED" if ok else "FAILED"
            note = " [UNWITNESSED: no artifact declared for this class, so whether it repaired "
            note += "anything is UNMEASURED, not confirmed]"
        elif not ok:
            outcome, note = "FAILED", ""
        elif ineffective:
            outcome = "INEFFECTIVE"
            note = (f" [artifact {WITNESS[cls].name} has not advanced across {ineffective} "
                    f"consecutive attempt(s) -- first aid is NOT working on this class; it needs "
                    f"deep repair, not another launch]")
        else:
            outcome, note = "ATTEMPTED", ""
        witness[cls] = {"stamp": before or 0.0, "ineffective": ineffective}
        row = {"at": now.isoformat(timespec="seconds"), "class": cls,
               "outcome": outcome, "detail": detail + note}
        actions.append(row)
        journal.append(row)
        print(f"  FIXER {cls}: {outcome.lower()} -- {(detail + note)[:200]}")

    STATE.parent.mkdir(parents=True, exist_ok=True)
    STATE.write_text(json.dumps({"last_attempt": last, "journal": journal[-400:],
                                 "witness": witness}, indent=1), "utf-8")
    return actions


if __name__ == "__main__":
    # manual invocation: fix the classes named on argv, e.g. `auto_fixers.py SEARCH DOCKET`
    named = [f"{c}: manual" for c in sys.argv[1:] if c in FIXERS]
    if not named:
        print("usage: auto_fixers.py CLASS [CLASS...]  --", ", ".join(sorted(FIXERS)))
        raise SystemExit(2)
    apply(named)
