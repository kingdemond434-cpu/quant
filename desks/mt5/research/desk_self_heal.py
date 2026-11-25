"""Is the MT5 desk's evidence pipeline actually running, and can it be fixed?

WHY THIS EXISTS

Aurum has self_heal.py: nineteen checks every fifteen minutes, fixing what is
mechanical and escalating what is not. This desk had nothing equivalent, and the
consequence showed up on 2026-08-28 -- `shadow_health.json` was THIRTY-THREE
HOURS stale while MT5-ShadowSync fired every fifteen minutes and returned exit
0, because its SKIP branch exited 0 when the sources were absent. Publishing
nothing and publishing successfully were byte-identical to every watchdog.

Nothing on this desk was looking. The stale artifact was found by the OTHER
desk's session hook, by accident, a day and a half late.

WHAT IT CHECKS, AND WHY EACH IS AN EVIDENCE QUESTION

Every check here is about whether the desk is still PRODUCING EVIDENCE. It is
deliberately not a correctness audit: the gates, the law fences and the
promotion protocol already do that, and they do it far better than a fifteen
minute poll could. This asks the question none of them ask, which is whether
they ran at all.

  shadow freshness   the desk's only forward-evidence record
  state publication  the four files the git sync carries to the other desk
  certification      QQUANT_GATES.json, the source of everything Aurum absorbs
  export             aurum_findings.jsonl, the channel out
  universe data      bars ending BEFORE shadow's start is exactly gap 119: every
                     replay refuses correctly, shadow starves, and nothing says
                     so because refusing correctly looks like working

WHAT IT WILL NOT DO

It runs research and it publishes; it never promotes, never arms, never edits a
gate or a threshold, and never touches the deadman rail. Those are the
principal's acts and a fifteen-minute poll has no business near them. The
prohibition is enforced by a test walking this module's AST, not by intent.
"""

from __future__ import annotations

import json
import re
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

DESK_SELF_HEAL_VERSION = "deskheal-2026-08-28-a"

#: Hours before an artifact published on a 15-minute cadence is stale. Three,
#: so a busy box or one slow run does not fire it.
SHADOW_STALE_H = 3.0

#: Days before the daily artifacts are stale. Two, so a single missed run is a
#: blip and two is a pattern.
DAILY_STALE_D = 2.0

#: Hours before QQUANT_GATES.json is stale. MT5-QQuantGatesCertify runs EVERY HOUR at :27
#: (box_tasks.manifest); the old two-day limit let certification sit stalled for 27 hours on
#: 2026-11-18 while this check read PASS. Six missed runs is a stall, not a blip.
CERT_STALE_H = 6.0

#: The files sync_shadow_to_git.ps1 carries. Absent, the other desk sees a
#: frozen snapshot and cannot tell it from a live one.
PUBLISHED = (
    "desks/mt5/reports/shadow/shadow_health.json",
    "desks/mt5/data/gateway_state.json",
    "desks/mt5/data/sleeves.json",
    "desks/mt5/data/regime_state.json",
)


@dataclass(frozen=True)
class Finding:
    check: str
    ok: bool
    detail: str
    fixable: bool = False
    task: str | None = None   # the producer task that cures it, when the check names one
    hung: bool = False        # output older than HUNG_FACTOR x its limit: a running copy is stuck

    @property
    def line(self) -> str:
        return f"  [{'PASS' if self.ok else 'BROKEN'}] {self.check:<20} {self.detail}"


def _is_producing_host(root: Path, rel_dir: str) -> bool:
    """Does this box actually produce these artifacts?

    GAP 111 IN ONE FUNCTION. reports/ and most of data/ are gitignored, so on
    any clone an artifact is ABSENT for a completely innocent reason. Reporting
    that as a fault would make this tool cry wolf on every checkout while saying
    nothing about the host that matters.

    FILESYSTEM HEURISTICS DO NOT WORK HERE and both obvious ones were tried:
    reports/ carries committed sweep JSONs and logs/ carries committed console
    captures, so "the directory has content" is true on a bare clone. A marker
    that is true everywhere discriminates nothing.

    MetaTrader5 is the honest marker. It is installed only where the desk
    actually runs, it is what every producer in this tree imports to do its job,
    and a box without it cannot have produced any of these files no matter what
    its directories contain. `rel_dir` is unused and kept in the signature so a
    future check with a different producer can override per-artifact.
    """
    try:
        import MetaTrader5  # noqa: F401
        return True
    except Exception:
        return False


def _absent(check: str, rel_dir: str, root: Path, detail: str,
            fixable: bool = True) -> Finding:
    """An artifact is missing. Whether that is a FAULT depends on the host."""
    if not _is_producing_host(root, rel_dir):
        return Finding(check, True,
                       f"UNMEASURED — MetaTrader5 is not installed here, so this "
                       f"box does not produce {rel_dir} and the file is "
                       f"gitignored rather than missing. Ask the host that runs "
                       f"the desk. NOT the same as healthy.")
    return Finding(check, False, detail, fixable=fixable)


def _age_h(p: Path, now: datetime) -> float | None:
    try:
        return (now.timestamp() - p.stat().st_mtime) / 3600.0
    except OSError:
        return None


def check_shadow_freshness(root: Path, now: datetime) -> Finding:
    """The desk's only forward-evidence record, and the one that went stale."""
    f = root / "desks/mt5/reports/shadow/shadow_health.json"
    if not f.exists():
        return _absent("shadow", "desks/mt5/reports", root,
                       "shadow_health.json does not exist. Either shadow has "
                       "never run on this box or it is writing elsewhere -- and "
                       "the sync publishes nothing either way.")
    age = _age_h(f, now)
    if age is not None and age > SHADOW_STALE_H:
        return Finding("shadow", False,
                       f"published {age:.1f}h ago on a 15-minute cadence. The "
                       f"numbers inside stay plausible while stale, which is "
                       f"why nothing else notices.",
                       fixable=True)
    try:
        d = json.loads(f.read_text(encoding="utf-8"))
    except Exception as e:
        return Finding("shadow", False, f"unreadable ({e})")
    return Finding("shadow", True,
                   f"{d.get('sleeves_with_forward_trades')} sleeve(s) accruing, "
                   f"{len(d.get('missing_sleeves') or [])} missing, "
                   f"{d.get('status')}")


def check_published_state(root: Path, now: datetime) -> Finding:
    """All four files the git sync carries, not just the one that is read most.

    A PARTIAL set is the dangerous case: the sync exits 0, the other desk reads
    three fresh files and one frozen one, and nothing distinguishes them.
    """
    missing = [rel for rel in PUBLISHED if not (root / rel).exists()]
    if missing and not _is_producing_host(root, "desks/mt5/reports"):
        return Finding("published state", True,
                       f"UNMEASURED — {len(missing)} absent on a box with no "
                       f"MetaTrader5, which produces none of them. Gitignored "
                       f"here, not missing.")
    if len(missing) == len(PUBLISHED):
        return Finding("published state", False,
                       f"NONE of the {len(PUBLISHED)} published files exist. The "
                       f"sync has nothing to carry and exits 0 doing it.")
    if missing:
        return Finding("published state", False,
                       f"{len(missing)} of {len(PUBLISHED)} absent: "
                       f"{', '.join(missing)}. Whatever reads these from git is "
                       f"STALE, not merely unchanged, and cannot tell.")
    return Finding("published state", True, f"all {len(PUBLISHED)} present")


def check_certification(root: Path, now: datetime) -> Finding:
    """QQUANT_GATES.json -- the source of every survivor Aurum can absorb."""
    f = root / "desks/mt5/reports/QQUANT_GATES.json"
    if not f.exists():
        return _absent("certification", "desks/mt5/reports", root,
                       "QQUANT_GATES.json absent. Nothing has been certified, so "
                       "the survivor channel to Aurum carries only negatives -- "
                       "which can cost that desk an edge but never give it one.")
    age = _age_h(f, now)
    if age is not None and age > CERT_STALE_H:
        return Finding("certification", False,
                       f"last written {age:.1f}h ago against an hourly task "
                       f"(limit {CERT_STALE_H:.0f}h)",
                       fixable=True)
    try:
        d = json.loads(f.read_text(encoding="utf-8"))
        passed = [v for v in d.get("verdicts", []) if v.get("passed") is True]
    except Exception as e:
        return Finding("certification", False, f"unreadable ({e})")
    return Finding("certification", True,
                   f"{len(passed)} of {len(d.get('verdicts', []))} cells cleared "
                   f"the battery")


def check_export(root: Path, now: datetime) -> Finding:
    """The channel out. Fresh here and stale in Aurum means the transport."""
    f = root / "desks/mt5/reports/aurum_findings.jsonl"
    if not f.exists():
        return _absent("export", "desks/mt5/reports", root,
                       "aurum_findings.jsonl absent -- the daily export has not "
                       "run, so Aurum's inbox cannot grow no matter how well its "
                       "own transport works.")
    age = _age_h(f, now)
    if age is not None and age > DAILY_STALE_D * 24:
        return Finding("export", False,
                       f"last written {age / 24:.1f}d ago against a daily export",
                       fixable=True)
    return Finding("export", True, f"written {(_age_h(f, now) or 0):.1f}h ago")


def check_lifted_rules(root: Path, now: datetime) -> Finding:
    """RULES THE PRINCIPAL REMOVED STAY REMOVED (zuck 2026-11-24 18:31Z: the E8 gold-only rule he
    had removed came back through a stale CERT_BOOK_LIVE.json). Fails, loudly and every pass,
    when a lifted name is zeroed again by a code pin or the live cert book. Not fixable by a
    task: the fix is code (decision_core.SUPERSEDED_CERT_ZEROS), so it pages."""
    try:
        from mt5desk.decision_core import lifted_rule_breaches
        breaches = lifted_rule_breaches()
    except Exception as exc:                      # the check itself must not go quiet
        return Finding("lifted_rules", False, f"check failed: {exc!r}", fixable=False)
    if breaches:
        return Finding("lifted_rules", False, "; ".join(breaches), fixable=False)
    # THE RAW FILE, NAMED (Audit should-fix 1 on 9dc6bbfe4): cert_book_zero filters lifted names
    # by design, so the box's own CERT_BOOK_LIVE.json zeros for them are read raw and reported --
    # harmless while the code lift holds, and the evidence if a reader ever bypasses it.
    raw: list[str] = []
    try:
        from mt5desk.decision_core import SUPERSEDED_CERT_ZEROS
        from mt5desk.kelly_sizing import CERT_BOOK_FILE, load_cert_book
        for venue, names in SUPERSEDED_CERT_ZEROS.items():
            book = load_cert_book(CERT_BOOK_FILE, venue) or {}
            raw += [f"{venue}:{n}" for n in sorted(names) if book.get(n) == 0.0]
    except Exception as exc:
        raw = [f"raw read failed ({type(exc).__name__})"]
    return Finding("lifted_rules", True,
                   "every principal-lifted rule stays lifted"
                   + (f"; the cert book file still writes {len(raw)} lifted zero(s), ignored in "
                      f"code: {', '.join(raw[:8])}" if raw else ""))


def check_universe_data(root: Path, now: datetime,
                        max_age_d: float = 3.0) -> Finding:
    """Do the bars reach the present?

    THIS IS GAP 119 IN ONE CHECK. Universe parquet ending before SHADOW_START
    meant every replay refused with "this period is NO DATA, not a quiet market"
    -- the correct call -- while shadow starved and five CORE sleeves waited on
    it. Nothing alerted, because refusing correctly is indistinguishable from
    working.
    """
    d = root / "desks/mt5/data/universe"
    if not d.exists():
        return Finding("universe data", True,
                       "no universe directory on this host — UNMEASURED, which "
                       "is not the same as healthy")
    pq = sorted(d.glob("*_H1.parquet"))
    if not pq:
        return Finding("universe data", False,
                       "universe directory exists and holds no H1 parquet. Every "
                       "replay will refuse, correctly, and shadow will starve.")
    newest = max((_age_h(p, now) or 1e9) for p in [max(pq, key=lambda p: p.stat().st_mtime)])
    if newest > max_age_d * 24:
        return Finding("universe data", False,
                       f"newest bars written {newest / 24:.1f}d ago. Shadow "
                       f"replays a period the data does not cover, refuses "
                       f"correctly, and starves -- which looks exactly like "
                       f"working.",
                       fixable=True)
    return Finding("universe data", True,
                   f"{len(pq)} instrument file(s), newest {newest:.1f}h old")


#: Free gigabytes below which the desk is one bad hour from losing every artifact write at once.
#: The same floor `stall_watch.ps1` prunes at; this check exists because the noon lane must see
#: the condition even on a pass where stall_watch itself did not run.
DISK_FLOOR_GB = 5.0

#: The organs whose cadence IS the desk, and the age past which each is not doing its job. The
#: gauntlet is the tightest because it is the conversion step: nothing becomes a certificate
#: without it, so a stalled gauntlet freezes the whole funnel while everything downstream keeps
#: reporting its last good number and looks healthy.
CADENCE_H = {
    "external_gauntlet": 6.0,
    "research_pipeline": 6.0,
    "universal_gate": 12.0,
    "allocation": 12.0,
    "research_loop": 12.0,
}


def check_disk_headroom(root: Path, now: datetime) -> Finding:
    """Free space on the volume the desk writes to.

    MEASURED 2026-09-08: C: fell to 0.5GB, `stall_watch` pruned its one reclaim pool, recovered
    nothing, wrote "needs a human decision" and stopped. The desk publisher died ten minutes
    later and every downstream organ went stale for twelve hours -- gauntlet 4.6 days, allocation
    5.1 days, markout 9 days -- while `audit()` had no check that could have named the cause.
    Five checks, all of them about artifacts, and none about the resource that produces them.

    A disk fault is NOT fixable by running a task, so it escalates rather than pretending a
    remedy exists. Naming it is the whole job: the noon lane's report is what a person reads.
    """
    try:
        import psutil  # type: ignore[import-untyped,unused-ignore]
        free_gb = psutil.disk_usage(str(root)).free / (1024 ** 3)
    except OSError as exc:
        return Finding("disk", True,
                       f"UNMEASURED — could not stat the volume at {root} ({exc}). "
                       "NOT the same as healthy.")
    if free_gb >= DISK_FLOOR_GB:
        return Finding("disk", True, f"{free_gb:.1f}GB free (floor {DISK_FLOOR_GB:.0f}GB)")
    return Finding(
        "disk", False,
        f"{free_gb:.1f}GB free, under the {DISK_FLOOR_GB:.0f}GB floor. stall_watch prunes the "
        "safe pools every 10 minutes; if this persists the growth is in protected data (tape, "
        "universe) or outside the desk tree, and no task can reclaim it.",
        fixable=False)


def check_research_cadence(root: Path, now: datetime) -> Finding:
    """Are the organs that convert research into certificates actually running?

    THE ONE THIS DESK KEEPS MISSING. Every other check asks whether an artifact EXISTS and is
    recent. This asks whether the pipeline that produces artifacts has run at all -- and on
    2026-09-08 that distinction was the whole failure: `shadow_health.json` was present and
    parseable and the gauntlet had not completed a run in 4.6 days. A stale organ keeps its last
    good output on disk, so "the file is there" stays true long after the desk stopped working.
    """
    f = root / "desks/mt5/reports/midnight_report.json"
    if not f.exists():
        return _absent("cadence", "desks/mt5/reports", root,
                       "midnight_report.json does not exist, so no organ's last-run time is "
                       "recorded anywhere this check can read.")
    try:
        fresh = (json.loads(f.read_text("utf-8")).get("freshness") or {})
    except (OSError, ValueError) as exc:
        return Finding("cadence", False, f"midnight_report.json is unreadable ({exc})",
                       fixable=False)
    stale: list[str] = []
    for organ, limit in CADENCE_H.items():
        raw = fresh.get(organ)
        if not raw:
            stale.append(f"{organ} UNRECORDED")
            continue
        try:
            ts = datetime.fromisoformat(str(raw).replace("Z", "+00:00"))
        except ValueError:
            stale.append(f"{organ} unparseable ({raw})")
            continue
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=UTC)
        age = (now - ts).total_seconds() / 3600.0
        if age > limit:
            stale.append(f"{organ} {age / 24:.1f}d (limit {limit / 24:.1f}d)")
    if not stale:
        return Finding("cadence", True, f"{len(CADENCE_H)} organs inside their cadence")
    # Re-running the hourly lane is exactly the work the scheduler already does, so it is a
    # legitimate remedy -- the same verb every other remedy in this module uses.
    return Finding("cadence", False, "; ".join(stale), fixable=True)


#: JUDGE_STALL.json incidents (scripts/judge_stall_pager.py, on MT5-BoxHeartbeat's 5-minute
#: clock) that RE-RUNNING THE GAUNTLET TASK can cure: the judge is dead, overdue or producing
#: nothing. MT5-Gauntlet is IgnoreNew, so a run while a sweep is alive is a no-op, never a stack.
#: `host_unreadable` and `inputs_unmeasured` are measurement faults no task run can cure.
JUDGE_RERUN_INCIDENTS = ("resident_dead", "sweep_dead", "sweep_overdue", "no_verdict",
                         "zero_judged_sweep")
#: The pager rewrites JUDGE_STALL.json every five minutes; older than this, it is not running.
JUDGE_STALL_REPORT_MAX_H = 1.0
#: The pager incidents that mean the judge is HUNG, not slow: its heartbeat is stale, its sweep
#: child is dead, or a sweep phase ran past its measured limit (judge_stall_pager.PHASE_LIMIT_H).
JUDGE_HUNG_INCIDENTS = frozenset({"resident_dead", "sweep_dead", "phase_overrun"})


def check_judge_stall(root: Path, now: datetime) -> Finding:
    """Is the judge -- the step every certificate passes through -- stalled right now?

    The pager already DETECTS this; nothing acted on it. A stall that a page names and nobody
    cures is the 2026-11-18 shape: certification stalled for a day with the alarm on the board.
    """
    f = root / "desks/mt5/reports/JUDGE_STALL.json"
    if not f.exists():
        return _absent("judge stall", "desks/mt5/reports", root,
                       "JUDGE_STALL.json absent: the judge stall pager has never run here",
                       fixable=False)
    age = _age_h(f, now)
    if age is not None and age > JUDGE_STALL_REPORT_MAX_H:
        return Finding("judge stall", False,
                       f"JUDGE_STALL.json is {age:.1f}h old against a 5-minute pager: the "
                       f"pager (MT5-BoxHeartbeat) is not running, so a stall is unseen",
                       fixable=False)
    try:
        doc = json.loads(f.read_text(encoding="utf-8"))
        inc = doc.get("incidents") or {}
    except (OSError, ValueError, AttributeError) as exc:
        return Finding("judge stall", False, f"JUDGE_STALL.json unreadable ({exc})")
    open_ = {k: v for k, v in inc.items() if isinstance(v, dict) and v.get("open") is True}
    if not open_:
        return Finding("judge stall", True, f"{len(inc)} incident(s) watched, none open")
    curable = [k for k in open_ if k in JUDGE_RERUN_INCIDENTS]
    detail = "; ".join(f"{k}: {str(v.get('why') or '')[:160]}" for k, v in open_.items())
    # HUNG only on the pager's own liveness signals, read from a reading whose `at` is fresh
    # (Audit HOLD 11-24): a verdict gap alone is never hung -- the ledger appends only when a
    # verdict changes -- and merge_and_publish inside its limit is never phase_overrun.
    at = _ts(doc.get("at"))
    fresh = at is not None and 0 <= (now - at).total_seconds() <= JUDGE_STALL_REPORT_MAX_H * 3600
    hung = fresh and any(k in open_ for k in JUDGE_HUNG_INCIDENTS)
    return Finding("judge stall", False, detail, fixable=bool(curable) or hung,
                   task=JUDGE_TASK if hung else None, hung=hung)


def check_tape(root: Path, now: datetime) -> Finding:
    """Is the tick recorder -- the feed under every tape feature and cost -- advancing?"""
    f = root / "desks/mt5/reports/TAPE_FRESHNESS.json"
    if not f.exists():
        return _absent("tape", "desks/mt5/reports", root,
                       "TAPE_FRESHNESS.json absent: tape freshness is not measured here",
                       fixable=False)
    try:
        d = json.loads(f.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        return Finding("tape", False, f"TAPE_FRESHNESS.json unreadable ({exc})")
    age = _age_h(f, now)
    if age is not None and age > SHADOW_STALE_H:
        return Finding("tape", False,
                       f"TAPE_FRESHNESS.json itself is {age:.1f}h old: the freshness check "
                       f"(MT5-TickIntegrity) is not running", fixable=False)
    if str(d.get("status") or "").upper() != "RED":
        return Finding("tape", True, f"tape {d.get('status')}")
    cause = str(d.get("cause") or "")
    # Only the recorder-not-advancing cause is a re-run's to cure. A terminal link that is down
    # or a recorder that reports itself PAUSED is a different fault; a re-run there is a guess.
    curable = "not running or not advancing" in cause
    return Finding("tape", False, f"{d.get('n_red')} tape(s) RED: {cause[:200]}",
                   fixable=curable)


# --------------------------------------------------------------------------
# THROUGHPUT, not just liveness (principal 2026-11-20 19:47Z: "They're supposed to do 24 hrs bro
# nonstop n the weak isn't supposed to be weak"). Measured that evening: every task read Running,
# yet the judge had made no verdict for 8.5h and ran 1.7k first verdicts a day against a 100k
# target, and the model seat made 237 completions against a 670/day baseline. A lane that is
# alive and weak passed every check above. These compare OUTPUT against a floor.
# --------------------------------------------------------------------------

#: Judge: first-time verdicts per day (the only number that drains the backlog) and the longest
#: tolerable gap between verdicts. A gap is curable by re-running the gauntlet task; a low rate
#: with fresh verdicts is a capacity fault and escalates with the numbers.
JUDGE_FIRST_PER_DAY_FLOOR = 100_000.0
JUDGE_VERDICT_GAP_H = 1.0
#: Model seat: completions per day at the 2026-11-07..09 baseline (676/696/657), pro-rated over
#: the UTC day so far. Below PACE_TOLERANCE of that pace is weak.
LLM_COMPLETIONS_PER_DAY_FLOOR = 670.0
PACE_TOLERANCE = 0.7
#: Lanes that must never sit idle: (name, report path, max age in hours, task that produces it or
#: None when no task re-run can cure it). Extended on the box without a code change by
#: desks/mt5/data/throughput_lanes.json: [{"lane", "path", "max_age_h", "task"}].
#: Measured from the box task inventory 2026-11-20 19:5xZ: each research lane, its report, and a
#: limit of a few cadences. Five forest regions were 5h+ stale that evening while their tasks read
#: Running; a lane whose report is older than this is idle whatever its task says.
LANES: tuple[tuple[str, str, float, str | None], ...] = (
    ("cn model ensemble", "desks/mt5/reports/CN_MODEL_ENSEMBLE.json", 1.5, "MT5-DeepSeek"),
    ("deepseek research", "desks/mt5/reports/DEEPSEEK_RESEARCH.json", 1.5, "MT5-DeepSeek"),
    ("llm budget census", "desks/mt5/reports/LLM_BUDGET_CENSUS.json", 1.5, None),
    ("judging throughput", "desks/mt5/reports/JUDGING_THROUGHPUT.json", 1.5, None),
    ("deepening queue", "desks/mt5/data/hypotheses/miner_deepening_queue.json",
     1.0, "MT5-Deepening"),
    ("forest frontier", "desks/mt5/data/deep_forest_frontier.json", 3.0, "MT5-Frontier"),
    ("forest africa", "desks/mt5/reports/FOREST_AFRICA.json", 2.0, "MT5-Forest-Africa"),
    ("forest asean", "desks/mt5/reports/FOREST_ASEAN.json", 2.0, "MT5-Forest-Asean"),
    ("forest china", "desks/mt5/reports/FOREST_CHINA.json", 2.0, "MT5-Forest-China"),
    ("forest europe", "desks/mt5/reports/FOREST_EUROPE.json", 2.0, "MT5-Forest-Europe"),
    ("forest korea", "desks/mt5/reports/FOREST_KOREA.json", 2.0, "MT5-Forest-Korea"),
    ("forest latam", "desks/mt5/reports/FOREST_LATAM.json", 2.0, "MT5-Forest-Latam"),
    ("forest mena", "desks/mt5/reports/FOREST_MENA.json", 2.0, "MT5-Forest-Mena"),
    ("forest oceania", "desks/mt5/reports/FOREST_OCEANIA.json", 2.0, "MT5-Forest-Oceania"),
    ("forest russia cis", "desks/mt5/reports/FOREST_RUSSIA_CIS.json", 2.0, "MT5-Forest-RussiaCis"),
    ("axis ingest", "desks/mt5/reports/AXIS_INGEST.json", 3.0, "MT5-AxisIngest"),
    ("ceo docket", "desks/mt5/reports/CEO_DOCKET.json", 3.0, "MT5-CEODocket"),
    ("moat swarms", "desks/mt5/reports/MOAT_SWARMS.json", 1.0, None),
    ("moat capture", "desks/mt5/reports/MOAT_CAPTURE.json", 2.0, "MT5-MoatCapture"),
    ("universal gate", "desks/mt5/reports/UNIVERSAL_GATE_CANDIDATES.json",
     3.0, "MT5-UniversalGate"),
    ("shadow discovery", "desks/mt5/reports/SHADOW_DISCOVERY.json", 3.0, "MT5-Shadow"),
    ("video cells", "desks/mt5/reports/VIDEO_CELLS.json", 3.0, "MT5-VideoCells"),
    ("independence intake", "desks/mt5/reports/INDEPENDENCE_INTAKE.json",
     1.0, "MT5-IndependenceIntake"),
    ("state vector", "desks/mt5/data/state_vector.json", 2.0, "MT5-StateVector"),
    ("scientist tournament", "desks/mt5/reports/SCIENTIST_TOURNAMENT.json",
     26.0, "MT5-ScientistTournament"),
    # Box 11-24: merge_hypotheses hung 22 h after its study-bank step holding the job lock, and
    # every 30-min trigger was refused (0x800710E0), so only direct appends reached the judge.
    ("merge docket", "desks/mt5/data/hypotheses/external_survivors.json", 3.0,
     "MT5-MergeDocket"),
)
#: A lane whose output is older than this multiple of its limit while its task still reads
#: Running is HUNG: the actuator may end that one research task and start it again (Audit 11-20).
HUNG_FACTOR = 2.0
LANES_FILE = "desks/mt5/data/throughput_lanes.json"
#: The ONLY tasks a lane may re-run: the research tasks named in LANES above. A lanes file can add
#: a lane to WATCH, but it can never point a re-run at anything else -- above all not a live
#: executor, the follower, the gateway or the release adopter, which may be stopped on purpose
#: (Audit MF-1 2026-11-20). A lane in the file naming any other task is kept as report-only.
#: The judge (MT5-Gauntlet) is research too: box 11-24 it read Running with no verdict for 7.5h
#: while every trigger was refused (0x800710E0), so a hung judge is ended and run like a lane.
JUDGE_TASK = "MT5-Gauntlet"
RESEARCH_TASKS: frozenset[str] = frozenset(t for *_, t in LANES if t) | {JUDGE_TASK}
RESEARCH_TASK_PREFIXES: tuple[str, ...] = ("MT5-Dept-", "MT5-Forest-", "MT5-Lab-", "MT5-Miner-")
_LIVE_TASK = re.compile(r"(?i)executor|follower|gateway|adopt|release|bridge|e8|ftmo|fusion|live")


def research_task(task: object) -> bool:
    """A task self-heal may re-run (and, when hung, end and re-run): research only, never live."""
    return (isinstance(task, str) and not _LIVE_TASK.search(task)
            and (task in RESEARCH_TASKS or task.startswith(RESEARCH_TASK_PREFIXES)))


def _ts(raw: Any) -> datetime | None:
    try:
        t = datetime.fromisoformat(str(raw).replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return None
    return t if t.tzinfo else t.replace(tzinfo=UTC)


def _num(raw: Any) -> float | None:
    return float(raw) if isinstance(raw, (int, float)) and not isinstance(raw, bool) else None


def check_judge_throughput(root: Path, now: datetime) -> Finding:
    """First verdicts per day against the floor, and the gap since the last verdict."""
    f = root / "desks/mt5/reports/JUDGING_THROUGHPUT.json"
    if not f.exists():
        return _absent("judge throughput", "desks/mt5/reports", root,
                       "JUDGING_THROUGHPUT.json absent: the judge's output is not measured",
                       fixable=False)
    try:
        doc = json.loads(f.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        return Finding("judge throughput", False,
                       f"JUDGING_THROUGHPUT.json unreadable ({type(exc).__name__}): the judge's "
                       f"output is UNMEASURED, not healthy")
    rate = doc.get("rate") if isinstance(doc.get("rate"), dict) else doc
    first = _num(rate.get("first_judged_per_day"))
    verdicts = rate.get("verdicts") if isinstance(rate.get("verdicts"), dict) else {}
    last = _ts(verdicts.get("last_verdict_at") or rate.get("last_verdict_at"))
    gap = (now - last).total_seconds() / 3600.0 if last else None
    parts = [f"first verdicts/day {first:,.0f}" if first is not None
             else "first verdicts/day UNMEASURED",
             f"last verdict {gap:.1f}h ago" if gap is not None else "last verdict UNMEASURED"]
    stalled = gap is None or gap > JUDGE_VERDICT_GAP_H
    weak = first is None or first < JUDGE_FIRST_PER_DAY_FLOOR
    if not stalled and not weak:
        return Finding("judge throughput", True, "; ".join(parts))
    if weak:
        parts.append(f"floor {JUDGE_FIRST_PER_DAY_FLOOR:,.0f}/day")
    # Only a stall is a re-run's to cure (MT5-Gauntlet is IgnoreNew: no stacking). A weak but
    # flowing judge is a capacity fault the report names for a person or a code change.
    return Finding("judge throughput", False, "; ".join(parts), fixable=stalled)


def check_llm_throughput(root: Path, now: datetime) -> Finding:
    """Model-seat completions today against the baseline, pro-rated over the UTC day."""
    f = root / "desks/mt5/reports/LLM_BUDGET_CENSUS.json"
    if not f.exists():
        return _absent("llm throughput", "desks/mt5/reports", root,
                       "LLM_BUDGET_CENSUS.json absent: the model seat's output is not measured",
                       fixable=False)
    try:
        doc = json.loads(f.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        return Finding("llm throughput", False,
                       f"LLM_BUDGET_CENSUS.json unreadable ({type(exc).__name__})")
    at = _ts(doc.get("at")) or now
    today = doc.get("today") if isinstance(doc.get("today"), dict) else {}
    done = _num(today.get("desk_completions"))
    if done is None:
        return Finding("llm throughput", False,
                       f"model seat {doc.get('status') or 'UNMEASURED'}: no completion count")
    hours = max(1.0, at.hour + at.minute / 60.0)
    pace = LLM_COMPLETIONS_PER_DAY_FLOOR * hours / 24.0
    waste = today.get("waste_rate")
    detail = (f"{done:.0f} completions by {at.strftime('%H:%M')}Z against a pace of {pace:.0f} "
              f"({LLM_COMPLETIONS_PER_DAY_FLOOR:.0f}/day)"
              + (f"; waste {waste}" if waste is not None else ""))
    if done >= PACE_TOLERANCE * pace:
        return Finding("llm throughput", True, detail)
    return Finding("llm throughput", False, detail, fixable=False)


# --------------------------------------------------------------------------
# MONEYPATH_CRASH (principal 2026-11-24 18:14Z, after the allocator crashed 440 times from 11-21
# to 11-24 and nothing said so): a money-path organ that keeps failing, or whose output is older
# than twice its cadence, is named with its ROOT CAUSE -- the exception it last died on -- so the
# alert carries the fix's starting point, not just "stale". These are code or terminal faults a
# re-run cannot cure, so they are never fixable here: the finding is the alert.
# --------------------------------------------------------------------------

ALLOCATION_CADENCE_H = 1.0
GATEWAY_STATE_MAX_MIN = 90.0
DAILY_CHAIN_STALL_H = 3.0
MONEYPATH_STALE_FACTOR = 2.0


def _step_names() -> list[str]:
    """daily_cycle.STEPS, imported (it imports the stdlib only at module scope). [] when the
    module cannot be imported: the chain is then UNMEASURED, never read as complete."""
    try:
        from daily_cycle import STEPS
    except Exception:
        try:
            from research.daily_cycle import STEPS
        except Exception:
            return []
    return [str(n) for n, _ in STEPS]


def _progress_at(v: Any) -> datetime | None:
    """A progress time in either shape: {"at": iso, ...} (the stamp) or a bare iso string."""
    return _ts(v.get("at")) if isinstance(v, dict) else _ts(v) if isinstance(v, str) else None


def _read_json(p: Path) -> Any:
    try:
        return json.loads(p.read_text(encoding="utf-8-sig"))
    except (OSError, ValueError):
        return None


def check_allocator_crash(root: Path, now: datetime) -> Finding:
    """The allocator's book must be younger than 2x its cadence; a FAILED pass is named."""
    rep = root / "desks/mt5/reports"
    alloc = rep / "pf_allocation.json"
    if not alloc.exists():
        return _absent("moneypath allocator", "desks/mt5/reports", root,
                       "pf_allocation.json absent: no book has ever been published here",
                       fixable=False)
    doc = _read_json(alloc)
    at = _ts((doc or {}).get("generated_utc")) if isinstance(doc, dict) else None
    age = (now - at).total_seconds() / 3600.0 if at else _age_h(alloc, now)
    sd = _read_json(rep / "ALLOCATOR_STANDDOWN.json")
    failed = isinstance(sd, dict) and str(sd.get("reason") or "").upper() == "FAILED" \
        and str(sd.get("status") or "").upper() == "STOOD_DOWN"
    limit = MONEYPATH_STALE_FACTOR * ALLOCATION_CADENCE_H
    if age is not None and age <= limit and not failed:
        return Finding("moneypath allocator", True, f"book {age:.1f}h old (limit {limit:.1f}h)")
    parts = [f"MONEYPATH_CRASH: allocator book is "
             f"{'UNMEASURED' if age is None else f'{age:.1f}h'} old (limit {limit:.1f}h)"]
    if failed:
        parts.append(f"last pass FAILED at {sd.get('at')}: {sd.get('why')} -- the previous book "
                     f"stands and every sleeve keeps its stale verdict until this is fixed")
    return Finding("moneypath allocator", False, "; ".join(parts), fixable=False)


def check_gateway_publication(root: Path, now: datetime) -> Finding:
    """The gateway's account reading (equity, book, reconcile) must be current: every rail and
    the Fusion deadman judge on it, and a frozen file reads exactly like a live account."""
    st = root / "desks/mt5/data/gateway_state.json"
    if not st.exists():
        return _absent("moneypath gateway", "desks/mt5/data", root,
                       "gateway_state.json absent: the gateway has never published here",
                       fixable=False)
    age_h = _age_h(st, now)
    age_min = None if age_h is None else age_h * 60.0
    if age_min is not None and age_min <= GATEWAY_STATE_MAX_MIN:
        return Finding("moneypath gateway", True, f"reading {age_min:.0f}min old")
    # A GATEWAY THE DEADMAN PAUSED IS NOT A CRASH (Audit should-fix on 45d647ac7; principal
    # 2026-11-24 18:02Z: Fusion is at 0 because he withdrew, so the halt is correct -- no alert
    # spam while equity is 0). Its reading is frozen by design until fusion-paused-reading
    # publishes while paused or a deposit re-arms it; the finding says so and does not page.
    paused = root / "desks/mt5/data/GATEWAY_PAUSED"
    if paused.exists():
        return Finding("moneypath gateway", True,
                       f"paused by the Fusion deadman (GATEWAY_PAUSED); reading "
                       f"{'UNMEASURED' if age_min is None else f'{age_min / 60.0:.1f}h'} old by "
                       f"design until a paused reading or a deposit re-arms it")
    doc = _read_json(st)
    last = doc.get("last_reconcile") if isinstance(doc, dict) else None
    eq = doc.get("equity") if isinstance(doc, dict) else None
    return Finding("moneypath gateway", False,
                   f"MONEYPATH_CRASH: gateway_state.json is "
                   f"{'UNMEASURED' if age_min is None else f'{age_min / 60.0:.1f}h'} old "
                   f"(limit {GATEWAY_STATE_MAX_MIN:.0f}min); last_reconcile {last}, equity {eq} -- "
                   f"every rail and the Fusion deadman are judging a frozen number",
                   fixable=False)


def check_daily_chain(root: Path, now: datetime) -> Finding:
    """The daily research chain must reach its steps: a chain that stamps the day and then stops
    (killed by its task limit, or hung on one step) starves every miner behind it."""
    stamp = _read_json(root / "desks/mt5/data/daily_cycle_state.json")
    names = _step_names()
    if not isinstance(stamp, dict):
        return _absent("moneypath daily chain", "desks/mt5/data", root,
                       "daily_cycle_state.json absent or unreadable", fixable=False)
    today = now.date().isoformat()
    steps = stamp.get("steps") if isinstance(stamp.get("steps"), dict) else {}
    ran = steps if stamp.get("last_run") == today else {}
    failed = {n: str((r or {}).get("error") or "")[:160] for n, r in ran.items()
              if isinstance(r, dict) and r.get("ok") is False}
    # PROGRESS, FROM EVERY PLACE THE CHAIN WRITES IT (Audit HOLD on 45d647ac7): the stamp's
    # `last_progress` {"at": iso} and the lock's owner sidecar `.job_locks/daily_cycle.owner.json`
    # (`last_progress` as a bare iso string, `at` when the holder took the lock). The box's
    # daily_cycle writes the sidecar on every heartbeat; the newest time wins.
    owner = _read_json(root / "desks/mt5/data/.job_locks/daily_cycle.owner.json")
    times = [_progress_at(stamp.get("last_progress"))]
    if isinstance(owner, dict):
        times += [_progress_at(owner.get("last_progress")), _progress_at(owner.get("at"))]
    live = [t for t in times if t is not None and t <= now + timedelta(minutes=5)]
    prog = max(live) if live else None
    quiet_h = (now - prog).total_seconds() / 3600.0 if prog else None
    hours_in = now.hour + now.minute / 60.0
    missing = [n for n in names if n not in ran]
    stalled = bool(missing) and hours_in >= DAILY_CHAIN_STALL_H and \
        (quiet_h is None or quiet_h > DAILY_CHAIN_STALL_H)
    if not stalled and not failed:
        return Finding("moneypath daily chain", True,
                       f"{len(ran)} of {len(names) or '?'} step(s) ran today")
    parts = []
    if stalled:
        parts.append(f"MONEYPATH_CRASH: daily chain stalled -- {len(ran)} of {len(names)} step(s) "
                     f"ran today, quiet {'UNMEASURED' if quiet_h is None else f'{quiet_h:.1f}h'}; "
                     f"next unrun: {', '.join(missing[:3])}")
    if failed:
        parts.append("failed: " + "; ".join(f"{n}: {e}" for n, e in list(failed.items())[:4]))
    return Finding("moneypath daily chain", False, " | ".join(parts), fixable=False)


def _lanes(root: Path) -> list[tuple[str, str, float, str | None]]:
    lanes = list(LANES)
    try:
        extra = json.loads((root / LANES_FILE).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        extra = []
    for row in extra if isinstance(extra, list) else []:
        if not isinstance(row, dict):
            continue
        name, path, age = row.get("lane"), row.get("path"), _num(row.get("max_age_h"))
        task = row.get("task")
        if isinstance(name, str) and isinstance(path, str) and age and age > 0 \
                and ".." not in path:
            safe = research_task(task)
            lanes.append((name, path, age, task if safe else None))
    return lanes


def check_lanes_idle(root: Path, now: datetime) -> list[Finding]:
    """Every lane's report must be newer than its limit; an idle lane is re-run when a task owns
    it. Missing on a host that does not produce it is not a fault (see _absent)."""
    out: list[Finding] = []
    for name, rel, limit, task in _lanes(root):
        p = root / rel
        if not p.exists():
            out.append(_absent(f"lane {name}", rel.rsplit("/", 1)[0], root,
                               f"{rel} absent: this lane has never written here",
                               fixable=False))
            continue
        age = _age_h(p, now)
        if age is not None and age <= limit:
            out.append(Finding(f"lane {name}", True, f"{age:.1f}h old (limit {limit:.1f}h)"))
        else:
            out.append(Finding(f"lane {name}", False,
                               f"idle: {rel} is {age if age is None else round(age, 1)}h old "
                               f"(limit {limit:.1f}h)", fixable=task is not None, task=task,
                               hung=age is not None and age > HUNG_FACTOR * limit))
    return out


# --------------------------------------------------------------------------
# THE PROCESS BOARD (principal 2026-11-25 01:47Z: know every broken component and fix it
# immediately, box-natively). ops/process_health.py already gives every scheduled task a verdict
# against its artifact contract; this reads that board and turns each fault into a Finding the
# actuator can act on, inside the same bounds as every other re-run here.
# --------------------------------------------------------------------------
BOARD_FILE = "desks/mt5/reports/process_health.json"
#: The board is written every 30 minutes (MT5-ProcessHealth). Older than this, its verdicts are
#: not today's and nothing is acted on from it.
BOARD_STALE_H = 2.0
BOARD_TASK = "MT5-ProcessHealth"
#: Verdicts that mean "this task is not producing": re-run when the task may be re-run.
BOARD_RERUN = frozenset({"FAILING", "STALE"})
#: Verdicts no re-run can cure (no task on the box, or a contract naming a file nothing writes):
#: alert only. Registering a task is an installer's act, which this actuator does not run.
BOARD_ALERT = frozenset({"NOT_SCHEDULED", "NO_ARTIFACT"})
#: NEVER re-run or ended from the board, whatever its verdict: the money path, the box's own
#: release/sign/forge chain and the bridge. A fault in one of these is PAGED, never touched.
#: Names are matched case-insensitively anywhere in the task name; the explicit list below is
#: the operator's never-stop list (memory 11-19 KEPT RULES), kept literal so a rename cannot
#: silently move a money task onto the re-run side.
_BOARD_NEVER = re.compile(
    r"(?i)executor|follower|follow|gateway|adopt|release|bridge|e8|ftmo|fusion|live|"
    r"allocator|account|clock|terminal|tick|memecoin|seal|sign|trust|forge|workflow|deadman|"
    r"window|order|quant-")
MONEY_PATH_TASKS: frozenset[str] = frozenset({
    "MT5-GatewayResident", "MT5-Gateway", "MT5-AccountState", "MT5-ClockFixer",
    "MT5-E8WindowGuard", "MT5-TerminalBoot", "MT5-TickRecorder", "MT5-LivePriority",
    "MT5-FusionDeadmanLive", "MT5-FusionDeadmanDryRun"})


GATEWAY_TASKS = frozenset({"MT5-GatewayResident", "MT5-Gateway"})
GATEWAY_PAUSED = "desks/mt5/data/GATEWAY_PAUSED"

#: THE DESIGN INVARIANTS (principal 2026-11-25 01:55Z, PERMANENT: the box always matches the
#: design). Each is checked here every guardian pass, box-natively, so it holds without Claude.
#: A violation pages; where a fixer exists the board's own re-run is that fixer (I3). I1 and I2
#: are measured by their owners' organs and only READ here (UNMEASURED until those artifacts
#: exist on the box): this module never computes a certification or a promotion itself.
INVARIANTS: tuple[tuple[str, str, str], ...] = (
    ("I1", "every certified survivor is on a fresh forward clock", "Research"),
    ("I2", "every fill-proven candidate is live on E8, FTMO and Fusion", "One pipe"),
    ("I3", "no task reports OK while its output is stale", "Autonomy"),
    ("I4", "cleared code reaches the box within 6h", "Autonomy"),
    ("I5", "every box alert reaches Claude", "Autonomy"),
    # principal 2026-11-25 02:49Z, PERMANENT: the box never fills up; caps without ever
    # reducing research or healing. Measured and reclaimed by box_headroom each guardian pass.
    ("I6", "the disk stays under its 75% line with 14+ days to the recorder pause", "Autonomy"),
    ("I7", "RAM, CPU, MT5 terminals and LLM relay quotas stay inside their lines", "Autonomy"),
)
HEADROOM_FILE = "desks/mt5/reports/BOX_HEADROOM.json"
HEADROOM_MAX_H = 1.0
RELEASE_FILE = "desks/mt5/data/release_identity.json"
ROUTING_FILE = "desks/mt5/reports/ALERT_ROUTING.json"
INVARIANT_FILES = {"I1": "desks/mt5/reports/INVARIANT_I1.json",
                   "I2": "desks/mt5/reports/INVARIANT_I2.json"}
RELEASE_MAX_H = 6.0


def check_invariants(root: Path, now: datetime,
                     board: Sequence[Finding] = ()) -> list[Finding]:
    """One Finding per invariant; violated -> not ok (paged), unmeasured -> ok with UNMEASURED."""
    out: list[Finding] = []
    for key, text, owner in INVARIANTS:
        label = f"invariant {key}"
        if key in INVARIANT_FILES:
            doc = _read_json(root / INVARIANT_FILES[key])
            if not isinstance(doc, dict) or "holds" not in doc:
                out.append(Finding(label, True, f"UNMEASURED: {text} -- {owner}'s organ has not "
                                   f"written {INVARIANT_FILES[key]} on this box"))
            else:
                out.append(Finding(label, bool(doc["holds"]),
                                   f"{text}: {str(doc.get('why') or '')[:240]}"))
        elif key == "I3":
            bad = [f.check.split("board ", 1)[1] for f in board
                   if not f.ok and f.detail.startswith("STALE_OUTPUT")]
            out.append(Finding(label, not bad, f"{text}: " + (
                f"VIOLATED by {', '.join(bad[:8])}" if bad else "holds")))
        elif key == "I4":
            doc = _read_json(root / RELEASE_FILE)
            if not isinstance(doc, dict) or not doc.get("measured"):
                out.append(Finding(label, True, f"UNMEASURED: {text} -- {RELEASE_FILE} absent "
                                   "or unmeasured"))
                continue
            age = _num(doc.get("age_h"))
            holds = bool(doc.get("ok")) and age is not None and age <= RELEASE_MAX_H
            out.append(Finding(label, holds, f"{text}: running "
                               f"{str(doc.get('running_sha'))[:9]}, seal {age}h old, "
                               f"ok={doc.get('ok')} ({str(doc.get('reason') or '')[:160]})"))
        elif key == "I5":
            doc = _read_json(root / ROUTING_FILE)
            if not isinstance(doc, dict) or "all_routed" not in doc:
                out.append(_absent(label, ROUTING_FILE.rsplit("/", 1)[0], root,
                                   f"{text}: VIOLATED -- {ROUTING_FILE} absent, so no box "
                                   "artifact proves an alert reached Claude", fixable=False))
            else:
                out.append(Finding(label, bool(doc["all_routed"]),
                                   f"{text}: {doc.get('routed_24h')}/{doc.get('alerts_24h')} "
                                   f"routed in 24h (last publish {doc.get('last_published_at')})"))
        elif key in ("I6", "I7"):
            doc = _read_json(root / HEADROOM_FILE)
            at = _ts(doc.get("at")) if isinstance(doc, dict) else None
            if at is None:
                out.append(_absent(label, HEADROOM_FILE.rsplit("/", 1)[0], root,
                                   f"{text}: VIOLATED -- {HEADROOM_FILE} absent, so nothing "
                                   "measures the box's headroom", fixable=False))
                continue
            age = (now - at).total_seconds() / 3600
            if age > HEADROOM_MAX_H:
                out.append(Finding(label, False, f"{text}: VIOLATED -- {HEADROOM_FILE} is "
                                   f"{age:.1f}h old (max {HEADROOM_MAX_H:.0f}h)", fixable=False))
                continue
            parts = ("disk",) if key == "I6" else ("ram", "cpu", "terminals", "quotas")
            bad = [f"{k}: {(doc.get(k) or {}).get('why')}" for k in parts
                   if not (doc.get(k) or {}).get("ok", True)]
            d = doc.get("disk") or {}
            detail = (f"{d.get('free_gb')}GB free of {d.get('total_gb')}GB, "
                      f"{d.get('days_to_pause')} days to pause" if key == "I6" else "holds")
            out.append(Finding(label, not bad, f"{text}: " + ("; ".join(bad)[:300] if bad
                                                              else detail)))
    return out


def board_rerunnable(task: object) -> bool:
    """A board task the actuator may re-run (and end when hung): a real scheduled task, not a
    component row, and nothing on the never list."""
    return (isinstance(task, str) and task.startswith("MT5-") and " " not in task
            and task not in MONEY_PATH_TASKS and not _BOARD_NEVER.search(task)
            and not task.startswith(("E8-", "Memecoin")))


#: 0x800710E0 ERROR_REQUEST_REFUSED as Task Scheduler reports it (unsigned, signed, or text).
_REFUSED_CODES = frozenset({0x800710E0, 0x800710E0 - (1 << 32)})


def _refused(code: object) -> bool:
    if isinstance(code, str):
        try:
            code = int(code, 16) if code.lower().startswith("0x") else int(code)
        except ValueError:
            return False
    return isinstance(code, int) and not isinstance(code, bool) and code in _REFUSED_CODES


def check_process_board(root: Path, now: datetime) -> tuple[list[Finding], dict[str, Any]]:
    """One Finding per faulted board row, plus the board's census (counts, uncontracted)."""
    p = root / BOARD_FILE
    doc = _read_json(p)
    if not isinstance(doc, dict) or not isinstance(doc.get("processes"), list):
        return ([_absent("board", BOARD_FILE.rsplit("/", 1)[0], root,
                         f"{BOARD_FILE} absent or unreadable: no task verdicts to act on",
                         fixable=False)], {"measured": False})
    at = _ts(doc.get("at"))
    age = None if at is None else (now - at).total_seconds() / 3600
    census = {"measured": True, "at": doc.get("at"), "counts": doc.get("counts") or {},
              "uncontracted": int((doc.get("counts") or {}).get("UNCONTRACTED") or 0)}
    if age is None or age > BOARD_STALE_H:
        census["measured"] = False
        return ([Finding("board", False,
                         f"{BOARD_FILE} is {'undated' if age is None else f'{age:.1f}h'} old "
                         f"(limit {BOARD_STALE_H:.0f}h): its verdicts are not acted on",
                         fixable=True, task=BOARD_TASK)], census)
    out: list[Finding] = []
    for row in doc["processes"]:
        if not isinstance(row, dict):
            continue
        name, verdict = str(row.get("name") or ""), str(row.get("verdict") or "")
        # A refused launch while an instance is RUNNING is the IgnoreNew overlap of a resident
        # (box RC 2026-11-25 03:45Z: all Dept-*, Forest-*, Moat-* -- event 322, never 332/329):
        # the work is being done, so it is not a refusal to page on.
        resident = str(row.get("state") or "").lower() == "running"
        if (name and _refused(row.get("last_result_code")) and verdict not in BOARD_RERUN
                and not resident):
            # TASK_REFUSED (red team 2026-11-25: 33 tasks read UNCONTRACTED while every run
            # returned 0x800710E0). The scheduler refused to start the run and nothing of the
            # task is running, so no re-run can cure it: the cause is the task's own settings
            # (a logon type with no session, a dead instance holding IgnoreNew). It pages
            # whatever its verdict says.
            census["refused"] = int(census.get("refused") or 0) + 1
            out.append(Finding(f"{'moneypath ' if name in MONEY_PATH_TASKS else ''}board {name}",
                               False, f"TASK_REFUSED: last run 0x800710E0 (the scheduler "
                               f"refused to start it); board verdict {verdict or 'none'}",
                               fixable=False))
            continue
        if verdict not in BOARD_RERUN | BOARD_ALERT or not name:
            continue
        if name in GATEWAY_TASKS and (root / GATEWAY_PAUSED).exists():
            # A gateway the Fusion deadman paused writes no state BY DESIGN (principal 11-24
            # 18:02Z: Fusion balance 0, auto-resume on deposit) -- the same reading as
            # check_gateway_publication. Paused is not stale output.
            out.append(Finding(f"board {name}", True, f"{verdict} while GATEWAY_PAUSED: "
                               "paused by the Fusion deadman, not stale"))
            continue
        why = str(row.get("why") or "")[:200]
        reports_ok = row.get("last_result_code") == 0 and str(row.get("state")) != "COMPONENT"
        # STALE_OUTPUT: the scheduler reads the task green while its artifact is older than the
        # contract -- the worst class, because nothing else on the box looks wrong.
        kind = "STALE_OUTPUT" if verdict == "STALE" and reports_ok else verdict
        money = name in MONEY_PATH_TASKS or not board_rerunnable(name)
        can_rerun = verdict in BOARD_RERUN and board_rerunnable(name)
        limit, age_min = _num(row.get("contract_max_age_min")), _num(row.get("artifact_age_min"))
        hung = bool(limit and age_min and age_min > HUNG_FACTOR * limit)
        label = f"{'moneypath ' if money and verdict in BOARD_RERUN else ''}board {name}"
        out.append(Finding(label, False, f"{kind}: {why}", fixable=can_rerun,
                           task=name if can_rerun else None, hung=hung and can_rerun))
    return out, census


def audit(root: Path, now: datetime | None = None) -> list[Finding]:
    now = now or datetime.now(UTC)
    return [check_lifted_rules(root, now),
            check_shadow_freshness(root, now),
            check_published_state(root, now),
            check_certification(root, now),
            check_export(root, now),
            check_universe_data(root, now),
            # ADDED 2026-09-08 after a disk-full took the desk down for twelve hours with every
            # existing check still reading PASS. Resource before artifact, cadence before
            # freshness: both name causes the other five can only show as symptoms.
            check_disk_headroom(root, now),
            check_research_cadence(root, now),
            # ADDED 2026-11-19 (principal: stall watchdog). The pager names a stalled judge and
            # the tape check names a stopped recorder; neither was ever cured by anything.
            check_judge_stall(root, now),
            check_tape(root, now),
            # ADDED 2026-11-20 (principal: 24/7 at full strength): output against floors.
            check_judge_throughput(root, now),
            check_llm_throughput(root, now),
            # ADDED 2026-11-24 (principal: MONEYPATH_CRASH -- the allocator died 440 times
            # unseen). Each names its root cause; none is a re-run's to cure.
            check_allocator_crash(root, now),
            check_gateway_publication(root, now),
            check_daily_chain(root, now),
            *check_lanes_idle(root, now),
            # ADDED 2026-11-25 (principal: every broken component found and fixed): the board.
            *(board := check_process_board(root, now)[0]),
            *check_invariants(root, now, board)]


# --------------------------------------------------------------------------
# Remediation. Same line as Aurum's: run RESEARCH, publish, never decide.
# --------------------------------------------------------------------------

@dataclass(frozen=True)
class Remedy:
    fault: str
    action: str
    why: str
    apply: Callable[[], bool]


def plan(findings: Sequence[Finding], *,
         run_task: Callable[[str], bool] | None = None
         ) -> tuple[list[Remedy], list[Finding]]:
    """Split into what a scheduled task can fix and what needs a person.

    Every remedy is "run the task that produces this artifact". That is the only
    verb this module has, and it is deliberately the only one: producing
    evidence is safe to retry, and everything else on this desk -- promoting,
    arming, editing a gate -- is the principal's act.
    """
    remedies: list[Remedy] = []
    escalate: list[Finding] = []
    task_for = {
        "shadow": "MT5-Shadow",
        "certification": "MT5-QQuantGatesCertify",
        "export": "MT5-Hourly",
        "universe data": "MT5-Universe",
        # A stalled conversion organ is fixed the same way as every other fault here: re-run the
        # task that already owns it. `disk` is deliberately absent -- no task can reclaim space,
        # so it escalates rather than pretending a remedy exists.
        "cadence": "MT5-Gauntlet",
        "judge stall": "MT5-Gauntlet",
        # The recorder's own keep-alive task: a running singleton makes the start a no-op.
        "tape": "MT5-TickRecorder",
        "judge throughput": "MT5-Gauntlet",
    }
    for f in findings:
        if f.ok:
            continue
        task = (f.task or task_for.get(f.check)) if f.fixable else None
        if task and run_task is not None:
            remedies.append(Remedy(
                f.check, f"run {task}",
                f"{task} produces this artifact; running it out of band is a "
                f"repeat of work the scheduler already does, not a new decision",
                lambda t=task: run_task(t)))
        else:
            escalate.append(f)
    return remedies, escalate


def render(findings: Sequence[Finding], outcomes: Sequence = (),
           escalations: Sequence[Finding] = ()) -> str:
    bad = [f for f in findings if not f.ok]
    # UNMEASURED IS NOT A PASS. A board of "we could not tell" rendered as
    # "evidence pipeline healthy" is absence read as a clean answer -- the
    # defect this desk has a law against, which shipped once in shadow_gap.py
    # and which I reproduced here after already fixing it in Aurum's
    # task_health. Caught by this module's own test, not by review.
    unknown = [f for f in findings if f.ok and "UNMEASURED" in f.detail]
    if bad:
        head = f"MT5 DESK SELF-HEAL ({DESK_SELF_HEAL_VERSION}) — {len(bad)} FAULT(S)"
    elif findings and len(unknown) == len(findings):
        head = (f"MT5 DESK SELF-HEAL ({DESK_SELF_HEAL_VERSION}) — NOTHING COULD "
                f"BE MEASURED on this box. Whether the pipeline is running is "
                f"UNKNOWN, which is not the same as healthy.")
    elif unknown:
        head = (f"MT5 DESK SELF-HEAL ({DESK_SELF_HEAL_VERSION}) — "
                f"{len(findings) - len(unknown)} healthy, {len(unknown)} UNMEASURED")
    else:
        head = f"MT5 DESK SELF-HEAL ({DESK_SELF_HEAL_VERSION}) — evidence pipeline healthy"
    out = [head] + [f.line for f in findings]
    for o in outcomes:
        out.append(f"  {'FIXED ' if o[1] else 'no-op '} {o[0]}")
    if escalations:
        out += ["", "  NEEDS A HUMAN:"]
        out += [f"    * {f.check}: {f.detail}" for f in escalations]
    return "\n".join(out)
