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
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

DESK_SELF_HEAL_VERSION = "deskheal-2026-08-28-a"

#: Hours before an artifact published on a 15-minute cadence is stale. Three,
#: so a busy box or one slow run does not fire it.
SHADOW_STALE_H = 3.0

#: Days before the daily artifacts are stale. Two, so a single missed run is a
#: blip and two is a pattern.
DAILY_STALE_D = 2.0

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
    if age is not None and age > DAILY_STALE_D * 24:
        return Finding("certification", False,
                       f"last written {age / 24:.1f}d ago against a daily task",
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


def audit(root: Path, now: datetime | None = None) -> list[Finding]:
    now = now or datetime.now(UTC)
    return [check_shadow_freshness(root, now),
            check_published_state(root, now),
            check_certification(root, now),
            check_export(root, now),
            check_universe_data(root, now)]


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
    }
    for f in findings:
        if f.ok:
            continue
        task = task_for.get(f.check) if f.fixable else None
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
