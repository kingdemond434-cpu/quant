#!/usr/bin/env python3
"""DAILY MAXIMIZATION SWEEP (principal standing order 2026-07-21).

The principal kept discovering -- only by personally pressuring the system -- that organs were
quietly below potential: audits seeing 1% of the code, prompts carrying 40x-stale budget
figures, quotas behaving as ceilings, credits sitting idle, miners dying silently on quota.
This script institutionalizes that pressure as a DAILY MECHANICAL SWEEP: pure filesystem
reads, no LLM cost, run by cron and at every brain-cycle start.

Layers above it: every 3-day panel carries a full-system recommendations sweep, and the
zero-based MAXIMIZATION panel mission re-derives each organ's ceiling from scratch on rotation.

Rules of the sweep:
 - a below-max state is a DEFECT unless acknowledged with a reason AND an expiry (max 30d) in

#  EXHAUSTION: there is no acceptable number of un-acked below-max states. Sweep every
#  organ every run; a check skipped for time is a defect hidden for time.
   data/max_audit_acks.json -- no permanent burial, ever
 - defects persisting >48h un-acked ESCALATE to the principal page (PRINCIPAL_ACTION.md):
   nothing can sit below max for more than two days without either being fixed or him knowing
 - one broken check must never kill the sweep (every check is fenced)
"""
from __future__ import annotations

import collections
import contextlib
import importlib.util
import json
import os
import re
import subprocess
import sys
import time
from collections.abc import Sequence
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import TYPE_CHECKING, Any

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:          # fences import libs; a blind checker is a defect
    sys.path.insert(0, str(ROOT))

from libs.research import path_refs  # noqa: E402  (needs the sys.path line above)

if TYPE_CHECKING:                      # the libs import below needs the sys.path line above
    from libs.ops.cycle_evidence import CycleEvidence
LOGS = ROOT / "data/cro_ai_logs"
REPORT = ROOT / "data/max_audit_report.json"
#: PER-BOX acks: the defect's truth genuinely differs by machine, so its disposition should too.
#: Untracked by design (`data/*` is gitignored) -- a RUNTIME defect acked here is acked exactly
#: where it fires and nowhere else, which is correct.
ACKS = ROOT / "data/max_audit_acks.json"
#: TRACKED acks, and the distinction is R0393. A REPO-scope defect is a property of a COMMITTED
#: file, so it is identically true in every checkout -- but its ack lived only in the untracked
#: file, so acking it here left it firing on the VPS, where the doctrine's own escalation rule
#: ("defects persisting >48h un-acked ESCALATE to the principal page") pages the principal for a
#: defect that HAS a full reasoned disposition sitting in another checkout. That is the exact
#: failure the ack mechanism exists to prevent, and it fires hardest on the most carefully
#: dispositioned items. The scope needed to route this was already computed per defect
#: (`scope_of`) and simply never applied to ack STORAGE.
ACKS_REPO = ROOT / "data/max_audit_acks_repo.json"
PA = ROOT / "data/PRINCIPAL_ACTION.md"

ESCALATE_H = 48.0
NOW = time.time()

# organ -> (glob, min_bytes_for_success, max_age_hours)
ORGANS = {
    "brain-cycle":      ("2026*_*.log",              2000, 8.0),
    "frontier-en":      ("frontier_en_*.log",        1500, 36.0),
    "frontier-cn":      ("frontier_cn_*.log",        1500, 36.0),
    "frontier-ru":      ("frontier_ru_*.log",        1500, 36.0),
    "frontier-kr":      ("frontier_kr_*.log",        1500, 36.0),
    "frontier-jp":      ("frontier_jp_*.log",        1500, 36.0),
    "frontier-ar":      ("frontier_ar_*.log",        1500, 36.0),
    "frontier-br":      ("frontier_br_*.log",        1500, 36.0),
    # THE ORGAN THAT REPLACED THE SEVEN ABOVE, AND NOTHING WAS WATCHING IT (2026-08-26).
    # 53c55b8e deleted `REGIONS=(en cn ru kr jp ar br)` from ops/run_frontier_rotation.sh on
    # 08-25 and put one EV-triaged unified dig in its place. The seven regional entries here
    # kept firing `organ-stale-*` about seats nothing invokes any more, while the dig that
    # actually runs -- the desk's primary discovery organ -- appeared in no liveness table at
    # all. `grep frontier_unified` over scripts/ and libs/ops/ found exactly one hit, in
    # check_quota_resume, which is itself unscheduled. So the desk was monitoring seven ghosts
    # and zero real organs on its highest-value hunting path: if the unified dig had died, the
    # only signal would have been the arrival rate months later.
    "frontier-unified": ("frontier_unified_*.log",   1500, 36.0),
    "dataaxis-dig":     ("dataaxis_*.log",           1500, 96.0),
    "litminer-dig":     ("litminer_*.log",           1500, 216.0),
    "prospector-dig":   ("prospector_*.log",         1500, 216.0),
    "blindrediscovery": ("blindrediscovery_*.log",   1500, 840.0),
}


#: organ -> the organ that now does its work. Lives HERE, beside ORGANS, because this file is
#: already the shared home of the organ tables and check_miner_runway imports from it; a second
#: copy in the other direction would be circular and would drift the day either moved.
#:
#: NOT A DELETION. Dropping these seven rows would shrink the denominator until both fences went
#: green on seven dead hunting grounds, which is the trick LAWS §2a forbids by name. Keeping them
#: as permanent daily reds is the other failure: a fence that is always red gets ignored, and
#: this desk lost six days to a cron outage nobody escalated for exactly that reason. So the
#: ghosts stop firing HERE -- `frontier-unified` is in ORGANS and fires once, naming the one
#: repair -- while check_miner_runway keeps a row per ground and flips every one of them bad the
#: moment the superseder is.
#:
#: MEASURED 2026-08-26: 53c55b8e deleted `REGIONS=(en cn ru kr jp ar br)` from
#: ops/run_frontier_rotation.sh on 08-25, so nothing has invoked a per-region dig since. These
#: five had been firing `organ-stale-*` for 101h about seats no scheduler names.
SUPERSEDED_BY: dict[str, str] = {
    "frontier-en": "frontier-unified", "frontier-cn": "frontier-unified",
    "frontier-ru": "frontier-unified", "frontier-kr": "frontier-unified",
    "frontier-jp": "frontier-unified", "frontier-ar": "frontier-unified",
    "frontier-br": "frontier-unified",
}


def _j(path: Path, default):
    try:
        return json.loads(path.read_text("utf-8"))
    except Exception:
        return default


def _acquired_axes() -> list[str]:
    """The ingested-data surface as NAMES (not a count): bronze lake stores + forward clocks."""
    names: list[str] = []
    lake = ROOT / "data/lake/bronze"
    if lake.exists():
        names += [p.name for p in lake.iterdir() if p.is_dir()]
    for pat in ("data/*_premium.jsonl", "data/*_supply.jsonl", "data/*_activity.jsonl"):
        names += [p.stem for p in ROOT.glob(pat)]
    return list(dict.fromkeys(names))  # de-dup, preserve order


def _converted_axes() -> list[str]:
    """Every axis the desk has actually CONVERTED, from the real conversion artifacts.

    An axis is 'converted' (covered) if a tested-hypothesis artifact exists for it -- regardless of
    outcome (tested-and-rejected is still converted; the graveyard is coverage). Three sources, all
    the desk's real conversion record, so the coverage metric credits work that genuinely happened
    instead of only the new --axis tag: (1) forward-clock shadows (web/axis_shadows.json), (2)
    reconstructed held-out OOS reports (reports/reconstructed_oos/*.json), (3) research_memory
    hypotheses tagged with --axis. Lowercased for tolerant matching against acquired-axis names.
    """
    tags: set[str] = set()
    # (1) forward-clock shadow registry -- each axis under a live forward clock
    shadows = _j(ROOT / "web/axis_shadows.json", {})
    for rec in (shadows.get("axes", []) if isinstance(shadows, dict) else []):
        ax = rec.get("axis") if isinstance(rec, dict) else None
        if isinstance(ax, str) and ax.strip():
            tags.add(ax.strip().lower())
    # (2) reconstructed held-out OOS reports -- each backfilled + diff-verified axis
    oos_dir = ROOT / "reports/reconstructed_oos"
    if oos_dir.exists():
        for rep in oos_dir.glob("*.json"):
            tags.add(rep.stem.lower())
            d = _j(rep, {})
            for r in (d.get("results", []) if isinstance(d, dict) else []):
                s = r.get("sleeve") if isinstance(r, dict) else None
                if isinstance(s, str) and s.strip():
                    tags.add(s.strip().lower())
    # (3) research_memory hypotheses tagged with the axis they screen (the --axis flag)
    try:
        import sqlite3
        con = sqlite3.connect(str(ROOT / "data/sor_research.sqlite"))
        for (mj,) in con.execute(
            "SELECT metrics_json FROM research_memory WHERE category != 'method' "
            "AND metrics_json IS NOT NULL"
        ):
            try:
                axis = (json.loads(mj) or {}).get("axis")
            except Exception:
                axis = None
            if isinstance(axis, str) and axis.strip():
                tags.add(axis.strip().lower())
        con.close()
    except Exception:
        pass
    return sorted(tags)


def _trial_mechanisms() -> list[str]:
    """The trials-ledger ``family`` column (the mechanism key) across candidate runtime DBs.

    Feeds the effective (independence-clustered) trial count. Robust to the ledger living in any of
    the sor databases; returns [] if unreachable so the monitor degrades to its prior behavior.
    """
    import sqlite3
    for name in ("sor_research.sqlite", "sor.sqlite", "sor_demo.sqlite", "sor_live.sqlite"):
        db = ROOT / "data" / name
        if not db.exists():
            continue
        try:
            con = sqlite3.connect(str(db))
            rows = con.execute("SELECT family FROM trials_ledger").fetchall()
            con.close()
            if rows:
                return [str(r[0]) for r in rows if r[0] is not None]
        except Exception:
            continue
    return []


# --------------------------------------------------------------- evidence scope
#
# THE AUDITOR COULD NOT TELL "THIS ORGAN IS BROKEN" FROM "THIS CHECKOUT NEVER RAN IT", and that
# ambiguity has now produced a wrong report to the principal at least once: five defects were
# relayed as real when three of them rested on `data/` artifacts that are gitignored and therefore
# absent in every fresh clone by construction. The auditor was not wrong to fire -- on the machine
# that owns the history, an absent artifact IS the defect -- it was wrong to present both readings
# in identical language, leaving the reader to guess which machine the sentence was about.
#
# The scope is derived from WHAT EACH CHECK ACTUALLY READ, not from parsing its prose. Path reads
# are recorded while the check runs, then split against `git ls-files`:
#
#   REPO     the check consulted at least one TRACKED file. The evidence is in git, so the defect
#            is verifiable and closable from any checkout -- it is mine.
#   RUNTIME  the check consulted ONLY untracked paths. The evidence exists solely on the machine
#            that runs the organ; a clone cannot confirm or close it. Still a real defect there.
#   UNSCOPED the check read no files at all -- pure in-memory or subprocess logic. Treated as REPO
#            for escalation, because unknown provenance must never become an excuse.
#
# THE ASYMMETRY IS DELIBERATE AND POINTS AT ME. A check that touches both a tracked doc and a
# runtime artifact is scored REPO, not RUNTIME. Misfiling a runtime defect as mine costs an
# investigation; misfiling my defect as the machine's lets it live forever behind "needs the VPS".
# Only the second failure is self-serving, so the tie breaks against me.

_RECORDING: list[str] | None = None
_PATH_METHODS = ("exists", "stat", "glob", "rglob", "iterdir", "open",
                 "read_text", "read_bytes", "is_file", "is_dir")


def _git_head() -> str | None:
    """The repo's current HEAD sha, or None when it cannot be resolved.

    None is the honest answer for a detached/absent/broken git dir, and every caller must treat
    it as "cannot tell" rather than "unchanged" -- a comparison against an unknown must never
    soften a safety verdict.
    """
    try:
        r = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True,
                           text=True, timeout=30, check=False)
    except (OSError, subprocess.SubprocessError):
        return None
    return ((r.stdout or "").strip() or None) if r.returncode == 0 else None


def _rel_root(p: Path) -> str:
    """Repo-relative when inside the repo, absolute otherwise. `relative_to` RAISES outside ROOT,
    and this session has now fixed that same crash in four separate scripts."""
    try:
        return str(p.relative_to(ROOT))
    except ValueError:
        return str(p)


def _install_read_probe() -> None:
    """Record every filesystem path a check consults. Idempotent."""
    if getattr(Path, "_maxaudit_probed", False):
        return
    for name in _PATH_METHODS:
        orig = getattr(Path, name)

        def wrap(self, *a, _orig=orig, **kw):
            if _RECORDING is not None:
                _RECORDING.append(str(self))
            return _orig(self, *a, **kw)

        setattr(Path, name, wrap)
    Path._maxaudit_probed = True


def _tracked_set() -> set[str]:
    """Every path git tracks, repo-relative. One subprocess, cached by the caller."""
    try:
        out = subprocess.run(["git", "ls-files"], cwd=ROOT, capture_output=True,
                             text=True, timeout=60, check=False)
        return set(out.stdout.split("\n")) - {""}
    except (OSError, subprocess.SubprocessError):
        return set()


_TRACKED: set[str] | None = None


def _committed_only(rels: list[str]) -> list[str]:
    """Keep only paths git TRACKS -- governance applies to what is COMMITTED (2026-08-12).

    check_artifact_governance already refuses to judge GITIGNORED files, for a reason it wrote
    down: a gate whose verdict depends on which machine ran it cannot be trusted in either
    direction. Untracked-but-not-ignored files are the same class and were never filtered, which
    matters because this repo is a SHARED, CONTENDED checkout -- sibling sessions and organs hold
    work-in-progress in the tree constantly. Measured while installing the birth-property fence:
    a sibling's uncommitted `scripts/check_denominator_attrition.py` turned both this check and
    the CI test that asserts on it RED, in a session that had never touched that file. A gate any
    other worker's scratch can trip is a gate that gets bypassed, and one bypassed on a false
    alarm is bypassed on the true one too.

    NOTHING REAL IS HIDDEN. A file that is not tracked is not in the repository: it cannot be an
    orphan in it, and it cannot be an ungoverned artifact of it. The instant it is committed --
    the moment the property actually has to hold -- it is in scope again, which is precisely the
    boundary this filter exists to sharpen.

    AN EMPTY ANSWER IS NOT AN ANSWER (L1.28a). If git cannot be reached (no repo, tmp_path test
    tree, subprocess failure) `_tracked_set` returns an empty set, and filtering against it would
    remove EVERY candidate and render a clean verdict over nothing -- the vacuous pass L1.57
    exists to refuse. So the filter applies only when git actually answered; otherwise the caller
    judges the filesystem exactly as before.
    """
    tracked = _tracked_set()
    return [r for r in rels if r in tracked] if tracked else rels


def _split_evidence(paths: list[str]) -> tuple[list[str], list[str]]:
    """(tracked, untracked) repo-relative evidence paths, deduped and ordered."""
    global _TRACKED
    if _TRACKED is None:
        _TRACKED = _tracked_set()
    tracked, untracked = [], []
    for p in dict.fromkeys(paths):
        try:
            rel = str(Path(p).resolve().relative_to(ROOT))
        except (ValueError, OSError):
            continue                              # outside the repo: not evidence about the repo
        if rel.startswith((".git/", "__pycache__")) or "/__pycache__/" in rel:
            continue
        (tracked if rel in _TRACKED else untracked).append(rel)
    return tracked, untracked


def scope_of(tracked: list[str], untracked: list[str]) -> str:
    """REPO / RUNTIME / UNSCOPED -- and the EVIDENCE outranks the REMEDY.

    THE REFINEMENT, AND IT WAS INFLATING THE PRINCIPAL PAGE. Defect prose names two kinds of path
    and they mean opposite things:

        "data/moat_screen.json absent -- ... Run scripts/screen_moat.py."
         ^ the EVIDENCE: untracked, and NOT THERE     ^ the REMEDY: tracked, and present

    Counting the tracked one first returned REPO, so a defect that is true on every fresh checkout
    BY CONSTRUCTION -- data/ is gitignored -- was paged as a repository fault the desk had left
    unfixed. At least three of the eleven REPO defects on the page were this, and a page padded
    with things no commit could ever fix is how a page stops being read.

    The discriminator is EXISTENCE, not vocabulary: an absent untracked artifact is what the
    defect is ABOUT, while a path that is present is what the sentence is POINTING AT. Only when
    nothing cited is missing does the tracked/untracked split decide, which keeps a genuine repo
    defect ("A is not called from B", both present and tracked) firmly REPO.
    """
    if any(not (ROOT / p).exists() for p in untracked):
        return "RUNTIME"
    if tracked:
        return "REPO"
    return "RUNTIME" if untracked else "UNSCOPED"


#: A path-ish token: either something containing a slash, or a bare filename with a known suffix.
#: Glob metacharacters are kept so the directory part survives (`data/cro_ai_logs/2026*.log`).
_TOKEN_RE = re.compile(r"[\w./*?<>-]*[\w*?](?:\.(?:md|json|jsonl|log|csv|parquet|py|sh|sqlite))\b"
                       r"|(?:data|web|docs|libs|scripts|ops|tests)/[\w./*?-]+")

_BASENAMES: dict[str, str] | None = None


def _basename_index() -> dict[str, str]:
    """basename -> repo-relative path, for tracked files with an unambiguous basename.

    Defect prose names artifacts the way a human would (`prospector_coverage.md`), not by full
    path. Ambiguous basenames are dropped rather than guessed: two files with one name cannot
    settle which the sentence meant, and picking either would fabricate the evidence.
    """
    global _BASENAMES, _TRACKED
    if _BASENAMES is None:
        if _TRACKED is None:
            _TRACKED = _tracked_set()
        counts: dict[str, list[str]] = {}
        for rel in _TRACKED:
            counts.setdefault(rel.rsplit("/", 1)[-1], []).append(rel)
        _BASENAMES = {b: v[0] for b, v in counts.items() if len(v) == 1}
    return _BASENAMES


def cited_evidence(msg: str) -> tuple[list[str], list[str]]:
    """(tracked, untracked) paths the DEFECT ITSELF names -- its own claim about its evidence.

    WHY THIS OUTRANKS WHAT THE CHECK READ. Scope was first derived purely from the files a check
    touched while running, which is mechanically true and too coarse: `check_organs` stats the
    tracked ORGAN_ARTIFACTS docs on its way to concluding that an untracked LOG is missing, so
    every organ-never defect came out REPO. One check emits many defects and they do not share
    evidence. What a defect asserts is missing is stated in its own sentence, so that is read
    first; the check's read-set is the fallback for defects that name nothing.
    """
    global _TRACKED
    if _TRACKED is None:
        _TRACKED = _tracked_set()
    idx = _basename_index()
    tracked, untracked = [], []
    for raw in _TOKEN_RE.findall(msg):
        tok = raw.strip("./").replace(str(ROOT) + "/", "")
        if not tok:
            continue
        if tok in _TRACKED:
            tracked.append(tok)
            continue
        if tok in idx:
            tracked.append(idx[tok])
            continue
        # A glob names a directory even when no file matches -- that directory is the evidence.
        head = tok.split("*")[0].split("?")[0].rsplit("/", 1)[0] if ("*" in tok or "?" in tok) \
            else tok
        if head.startswith(("data/", "web/")) or tok.startswith(("data/", "web/")):
            untracked.append(tok)
    return list(dict.fromkeys(tracked)), list(dict.fromkeys(untracked))


def _fenced(fn, defects, label):
    """Run one check, recording the evidence each defect it raises actually rests on."""
    global _RECORDING
    _install_read_probe()
    before = len(defects)
    _RECORDING = []
    try:
        fn(defects)
    except Exception as e:
        defects.append((f"sweep-broken-{label}", f"max_audit check '{label}' itself failed: "
                        f"{e!r} -- a blind checker is a defect"))
    finally:
        seen, _RECORDING = _RECORDING or [], None
    read_tr, read_un = _split_evidence(seen)
    for i in range(before, len(defects)):
        did, msg = defects[i][0], defects[i][1]
        tr, un = cited_evidence(msg)
        if not (tr or un):                       # names nothing: fall back to what the check read
            tr, un = read_tr, read_un
        defects[i] = (did, msg, scope_of(tr, un), tr[:6], un[:6])


# ARTIFACT PARITY (2026-07-25): claude writes deliverables via FILE TOOLS, so a SUCCESSFUL organ
# run can leave only the shell's ~58-byte start/exit header in its log. Judging production by log
# size alone made this sweep report 'organ never fired' on demonstrably working organs (the 07-25
# frontier dig wrote prospector_coverage.md at 13:37 while its log stayed 58b). An organ counts as
# having produced when its log is substantial OR a declared artifact advanced. Keep in sync with
# libs/ops/organ_catchup.py ORGANS.
ORGAN_ARTIFACTS: dict[str, tuple[str, ...]] = {
    # EXCLUSIVITY, and this drifted from its own sibling for weeks. libs/ops/organ_catchup.py
    # dropped BOTH of these for the brain on 2026-07-26 with the reason spelled out -- the ledger
    # is written by every commit and several organs, cadence_duties by run_cadence -- so each made
    # a DEAD cycle read as produced. This table kept them, and because the reported age is
    # min(log_age, artifact_age) the shared artifact made the number OPTIMISTIC: on 2026-08-12 the
    # brain had been dead 17.9h through four consecutive failures and this reported 13h. A
    # liveness signal a dozen other writers can emit is not evidence THIS organ ran. No exclusive
    # artifact exists, so fall back to log size: weaker, but honest (L1.28a).
    "brain-cycle": (),
    "dataaxis-dig": ("docs/research/data_axis_watchlist.md", "data/data_universe_map.json"),
    "prospector-dig": ("docs/research/prospector_watchlist.md",
                       "docs/research/prospector_coverage.md"),
    "litminer-dig": ("docs/research/improvement_inbox.md",),
    "frontier-en": ("docs/research/prospector_coverage.md",
                    "docs/research/search_operator_library.md"),
    "frontier-cn": ("docs/research/prospector_coverage.md",),
    "frontier-ru": ("docs/research/prospector_coverage.md",),
    "frontier-kr": ("docs/research/prospector_coverage.md",),
    "frontier-jp": ("docs/research/prospector_coverage.md",),
    "frontier-ar": ("docs/research/prospector_coverage.md",),
    "frontier-br": ("docs/research/prospector_coverage.md",),
    # Its shell log is ~always a stub (auth deferrals) or reaped; the deliverable is the
    # committed log doc -- run 2 (8278e31) wrote 234 lines there while every .log stayed
    # under 200b, and this check read that as "organ has never fired" (2026-08-12).
    "blindrediscovery": ("docs/research/blind_rediscovery_log.md",),
    # DECLARED EMPTY ON PURPOSE, same reasoning as brain-cycle above. The unified dig writes
    # prospector_coverage.md and search_operator_library.md, both of which several organs write,
    # and a liveness signal a dozen writers can emit is not evidence THIS organ ran. Log size is
    # weaker and honest; a shared artifact here would make a dead unified cycle read as produced.
    "frontier-unified": (),
}


def _exclusive_artifacts(organ: str) -> tuple[str, ...]:
    """Declared artifacts only THIS organ writes.

    R0418. The brain-cycle note above states the principle -- "a liveness signal a dozen other
    writers can emit is not evidence THIS organ ran" -- and it was applied by hand, to one organ,
    once. Eight organs still shared `docs/research/prospector_coverage.md` (measured 2026-08-13:
    prospector-dig + frontier-en/cn/ru/kr/jp/ar/br), so any ONE frontier seat writing it made the
    other seven read as having produced. That is the same false GREEN the brain fix removed,
    multiplied by eight and left in place because exclusivity was a comment rather than a rule.

    Computed from the table instead of curated, so a future organ that declares a shared artifact
    cannot silently re-open the hole -- the drift this docstring's own sibling suffered for weeks.
    An organ left with no exclusive artifact falls back to log size: weaker, but honest (L1.28a).
    """
    shared = {a for a, n in collections.Counter(
        a for arts in ORGAN_ARTIFACTS.values() for a in arts).items() if n > 1}
    return tuple(a for a in ORGAN_ARTIFACTS.get(organ, ()) if a not in shared)


def _artifact_age_h(organ: str) -> float:
    """Hours since this organ's freshest EXCLUSIVE declared artifact advanced (inf if none)."""
    best = 0.0
    for rel in _exclusive_artifacts(organ):
        try:
            best = max(best, (ROOT / rel).stat().st_mtime)
        except OSError:
            continue
    return (NOW - best) / 3600 if best else float("inf")


def check_organs(defects) -> None:
    for organ, (pat, min_b, max_h) in ORGANS.items():
        sup = SUPERSEDED_BY.get(organ)
        if sup:
            # Its work moved. The superseder has its own row in this table and fires ONCE if it
            # dies, which is the report the desk wants -- seven identical defects naming one
            # repair is noise, and noise is how a real one gets skimmed past. A map pointing at
            # an organ that is not in ORGANS is the dangerous case and is caught below, not here.
            if sup in ORGANS:
                continue
            defects.append((f"organ-supersession-broken-{organ}",
                            f"{organ} is recorded as superseded by {sup!r}, which is not in "
                            "ORGANS -- so this ground is watched by nothing at all. A "
                            "retirement pointing at an absent organ is strictly worse than no "
                            "retirement, because it reads as covered."))
            continue
        ok = [p for p in LOGS.glob(pat) if p.stat().st_size >= min_b]
        art_h = _artifact_age_h(organ)
        if not ok and art_h > max_h:
            # THE LOG PATH IS NAMED, not just the glob. The evidence for "never fired" is an
            # absent log under data/cro_ai_logs, which is gitignored -- so the sentence must say
            # so, or the scoper reads this as a repo defect and pages the principal about a
            # directory that cannot exist in a checkout.
            defects.append((f"organ-never-{organ}",
                            f"{organ}: no substantial log ({_rel_root(LOGS)}/{pat}, >= {min_b}b) "
                            f"AND no declared artifact written in {max_h}h -- organ has never "
                            "fired or always dies"))
            continue
        if not ok:
            continue                      # artifacts prove production; stub log is expected
        age_h = min((NOW - max(p.stat().st_mtime for p in ok)) / 3600, art_h)
        if age_h > max_h:
            # IN-FLIGHT IS NOT SILENTLY DEGRADED. `_producer_running` already encodes this for
            # products ("a monitor that cries wolf on healthy work is how a desk learns to ignore
            # its own pager") and this check never consulted it: on 2026-08-12 it paged
            # `organ-stale-brain-cycle ... silently degraded` at 14:54 about a cycle that was
            # running at that moment and exited 0 at 15:26. A claude organ's log stays tiny until
            # exit, so a healthy long run looks exactly like a dead one to a size-and-mtime rule.
            #
            # BOUNDED, because forgiving an in-flight run forever would hide a HUNG organ -- the
            # failure this check exists to catch. Past 2x the cadence window a still-running
            # producer IS the defect, and the message says which of the two it is.
            running = _organ_running(organ)
            if running and age_h <= 2 * max_h:
                continue
            hung = (" -- and its producer is STILL RUNNING, so this is a HUNG run, not a missed "
                    "one") if running else ""
            defects.append((f"organ-stale-{organ}",
                            f"{organ}: last SUCCESSFUL run {age_h:.0f}h ago "
                            f"(cadence expects <= {max_h:.0f}h) -- silently degraded{hung}"))


# A real death SAYS so. A ~58b log is the normal signature of a SUCCESSFUL claude organ (it writes
# deliverables via file tools, so only the shell's start/exit header reaches the log) -- the old
# size-only rule reported 22 'deaths' in 48h while those organs were writing real artifacts.
_DEATH_MARKERS = ("out of usage credits", "session limit", "hit your limit",
                  "issue with the selected model", "auth", "not found", "traceback",
                  "permission denied", "refusing to send")


#: label -> pgrep pattern of the organ that WRITES that product, in BRACKET-TRICK form
#: (`run_cro_ai[.]sh`). The bracket is not decoration: the decision ledger records a monitor
#: that self-matched its own pgrep and reported a dead cycle as RUNNING for 80 minutes, so
#: every pattern this desk greps for a liveness answer is written so it cannot match the
#: checker's own argv.
_PRODUCER_PGREP = {
    "cron-cycle":         "run_cro_ai[.]sh",
    "prospector-product": "run_prospector_dig[.]sh",
    "dataaxis-product":   "run_dataaxis_dig[.]sh",
    "litminer-product":   "run_litminer_dig[.]sh",
    "frontier-product":   "run_frontie[r]",
}


def _producer_running(label: str) -> bool:
    """True while the organ that writes this product is still running.

    IN-FLIGHT IS NOT A STUB (2026-07-26). check_production compared a product's size against a
    success threshold with no liveness test, so an organ that was running CORRECTLY was reported
    as a defect: the 15:00 brain cycle was 20 seconds old, its log held only the shell's start
    header (53b), and the sweep filed it as `production-stub ... ran but produced a stub, not
    real output (the quota-stub / refuse class)`. A claude organ writes deliverables via file
    tools and its log stays tiny until exit, so EVERY healthy cycle trips that rule for its whole
    runtime. organ_catchup already guards exactly this way (is_running + RETRY_COOLDOWN_S); the
    audit did not, and a monitor that cries wolf on healthy work is how a desk learns to ignore
    its own pager -- the same blindness the stub-death check exists to prevent.
    """
    pat = _PRODUCER_PGREP.get(label)
    return bool(pat) and _pgrep(pat)


def _pgrep(pat: str) -> bool:
    try:
        return subprocess.run(["pgrep", "-f", pat], capture_output=True,
                              timeout=10, check=False).returncode == 0
    except (OSError, subprocess.SubprocessError):
        return False               # cannot prove it is alive -> fall through and report


#: organ -> pgrep pattern for the shell entrypoint that writes its log. Mirrors the `pgrep` field
#: of libs/ops/organ_catchup.ORGANS, which has guarded exactly this way since 2026-07-26.
_ORGAN_PGREP = {
    "brain-cycle":      "run_cro_ai[.]sh",
    "dataaxis-dig":     "run_dataaxis_dig[.]sh",
    "litminer-dig":     "run_litminer_dig[.]sh",
    "prospector-dig":   "run_prospector_dig[.]sh",
    "blindrediscovery": "run_blind_rediscovery",
}


def _organ_running(organ: str) -> bool:
    """True while THIS organ is mid-run, so a healthy long cycle is not filed as a dead one.

    FAILS TOWARD REPORTING. An organ with no known pattern, or a pgrep that cannot run, returns
    False and the staleness defect fires as before -- an unprovable liveness claim must never
    silence a fence (L1.28a: unmeasured is not OK).
    """
    pat = _ORGAN_PGREP.get(organ) or ("run_frontie[r]" if organ.startswith("frontier-") else "")
    return bool(pat) and _pgrep(pat)


def check_stub_deaths(defects) -> None:
    dead = []
    for p in LOGS.glob("*.log"):
        try:
            if p.stat().st_size >= 600 or (NOW - p.stat().st_mtime) >= 48 * 3600:
                continue
            txt = p.read_text("utf-8", errors="ignore").lower()
        except OSError:
            continue
        if any(m in txt for m in _DEATH_MARKERS):
            dead.append(p)
    if len(dead) >= 3:
        defects.append(("stub-deaths",
                        f"{len(dead)} organ runs died at birth in 48h (log CONTENT names a quota/"
                        f"auth/model failure): {', '.join(p.name for p in dead[:6])}"))


_DEATH_DROPIN = Path.home() / ".config/systemd/user/service.d/10-death-visibility.conf"


def check_unit_deaths(defects) -> None:
    """Fleet-wide abnormal unit stops (2026-08-26). A global user-scope drop-in
    (ops/service.d/10-death-visibility.conf) logs every non-success service stop to
    unit_deaths.jsonl -- oom-kill, timeout, crash. Before it, three gap-wirer seats were
    OOM-killed in one night leaving 58-byte logs identical to auth failures. Two arms:
    the drop-in going missing is itself a defect (absence must never read as clean),
    and any death in 24h is named. stub-deaths reads log CONTENT; this reads the KILL."""
    dropin = _DEATH_DROPIN
    if not dropin.exists():
        defects.append(("unit-deaths-fence-missing",
                        "the death-visibility drop-in is NOT installed at "
                        f"{dropin} -- every abnormal user-unit stop (oom-kill, timeout, crash) "
                        "is silent again. Reinstall from ops/service.d/ + daemon-reload."))
        return
    log = LOGS / "unit_deaths.jsonl"
    if not log.exists():
        return  # fence installed, no deaths ever logged -- genuinely clean
    # WINDOW BY TIME, NOT BY ROW COUNT (gap-fixer 2026-08-28). This read `[-200:]` and then
    # filtered to 24h -- a row cap standing in for a time window. Measured the day it was fixed:
    # 241 abnormal stops in 24h, so the cap silently dropped 41 of them and, worse, the count it
    # printed would have STOPPED RISING at 200 exactly as the fleet got sicker. A cap that
    # saturates during the incident it exists to size is the "no silent caps" defect (LAWS): the
    # number reads like a measurement and is really the cap. 5000 lines is a memory bound, not a
    # window, and if it ever binds the check says so instead of quietly under-reporting.
    _SCAN_LINES = 5000
    lines = log.read_text("utf-8", errors="ignore").splitlines()
    scanned = lines[-_SCAN_LINES:]
    recent: list[str] = []
    counts: dict[str, int] = {}
    oldest_in_window = False
    for line in scanned:
        try:
            row = json.loads(line)
            ts = time.mktime(time.strptime(row["ts"], "%Y-%m-%dT%H:%M:%SZ"))
        except (ValueError, KeyError):
            continue
        if NOW - ts <= 24 * 3600 and "test-death-visibility" not in row.get("unit", ""):
            label = f"{row.get('unit')}({row.get('result')}/{row.get('exit_status')})"
            recent.append(label)
            counts[label] = counts.get(label, 0) + 1
            if line is scanned[0]:
                oldest_in_window = True
    if recent:
        # Rank by frequency so the report names the CAUSE, not the first eight rows
        # chronologically: on the day this was fixed one crash-looping unit produced 106 of the
        # 241 stops, and a chronological head buried it among the units it was killing. The
        # label keeps result/exit_status -- an oom-kill and an exit-1 need different repairs.
        top = ", ".join(f"{lab}x{n}" if n > 1 else lab
                        for lab, n in sorted(counts.items(), key=lambda kv: -kv[1])[:8])
        truncated = (" SCAN WINDOW BOUND HIT: the oldest scanned line is still inside 24h, so "
                     f"this count is a FLOOR -- raise _SCAN_LINES above {_SCAN_LINES}."
                     if oldest_in_window and len(scanned) == _SCAN_LINES else "")
        defects.append(("unit-deaths",
                        f"{len(recent)} abnormal user-unit stop(s) in 24h, by unit: {top}."
                        f"{truncated} An oom-kill here is the 4GB/no-swap box "
                        "eating a seat mid-cycle (console item: swapfile); a timeout/crash is "
                        "that unit's own defect. Read the unit journal, fix the cause -- the "
                        "retry loop hides the death but pays for it in quota."))


def check_launcher_seal(defects) -> None:
    """Long-running shell launchers must be sealed against mid-run rewrite (2026-08-26).

    bash reads a script INCREMENTALLY, by byte offset. This desk commits ~200x/day into the tree
    these launchers execute from, and a dig holds its slot for up to three hours, so any commit
    that changes a launcher's LENGTH mid-run makes bash resume from the middle of a line.

    IT HAPPENED. 63680c05 grew a comment in ops/run_frontier_rotation.sh by ~120 bytes at 11:22
    while a dig was running, and data/cro_ai_logs/seat_frontier.log recorded comment text being
    executed as a command, then output from the STALE version, then `syntax error near
    unexpected token 'fi'`. The dig died mid-way and the failure looked like an ordinary
    non-zero exit.

    REPRODUCED, AND THE FIX MEASURED RATHER THAN ASSUMED: an unguarded script rewritten mid-run
    executed garbage AND THEN RE-RAN ITSELF FROM THE TOP. A bare `{ ... }` protected the body
    but bash still read past the closing brace and re-ran. Only `{ ... exit N }` -- the exit
    INSIDE the group, so the process is gone before bash reads another byte -- ran exactly once,
    cleanly, with the right status.

    So the seal is three properties, and this check tests all three because two of them alone
    still leave the script re-running: a `{` on its own line, an `exit` as the last statement
    INSIDE the group, and a `}` that is the final line of the file.
    """
    root = ROOT / "ops"
    if not root.is_dir():
        return
    unsealed = []
    for f in sorted(root.glob("run_*.sh")):
        try:
            lines = f.read_text("utf-8", errors="ignore").rstrip("\n").split("\n")
        except OSError:
            continue
        # Only launchers a scheduler actually starts and that run long enough to be caught.
        # A script nothing invokes cannot be corrupted mid-run by definition.
        if not _launcher_is_scheduled(f.name):
            continue
        body = [ln for ln in lines if ln.strip()]
        sealed = (bool(body) and body[-1].strip() == "}"
                  and body[-2].strip().startswith("exit")
                  and any(ln.strip() == "{" for ln in lines))
        if not sealed:
            unsealed.append(f.name)
    if unsealed:
        defects.append(("launcher-unsealed",
                        f"{len(unsealed)} scheduled shell launcher(s) can be corrupted by a "
                        f"commit landing mid-run: {', '.join(unsealed[:8])}"
                        f"{' ...' if len(unsealed) > 8 else ''}. bash reads by byte offset, so a "
                        "length change mid-run resumes execution inside a line -- measured on "
                        "63680c05, which killed a frontier dig and left a `syntax error near "
                        "unexpected token` in seat_frontier.log. Fix: wrap the body in `{` ... "
                        "`exit $?` `}` with the closing brace as the file's last line."))


def _launcher_is_scheduled(name: str) -> bool:
    """True when a user unit or the crontab manifest names this launcher."""
    units = Path.home() / ".config" / "systemd" / "user"
    if units.is_dir():
        for u in units.glob("*.service"):
            try:
                if name in u.read_text("utf-8", errors="ignore"):
                    return True
            except OSError:
                continue
    man = ROOT / "ops" / "crontab.manifest"
    try:
        return name in man.read_text("utf-8", errors="ignore")
    except OSError:
        return False


def check_manifest_backlog(defects) -> None:
    """The scheduler's own backlog (2026-08-26). Root `cron.service` OOM-died on 08-20 and
    every ops/crontab.manifest row without a user-timer twin died with it -- 201 organs,
    including the hourly law gate, the daily ratchet raiser (the L1.50 floor stall's direct
    cause) and `check_organ_liveness` itself, which is precisely why six days passed with no
    escalation: the dead-organ detector was one of the dead organs.

    `run_manifest_dispatch.py` resurrects the allowlisted rows and has always WRITTEN the
    remaining backlog to its state file -- but nothing ever READ it (grep, 2026-08-26: zero
    consumers). A measurement no organ consumes is an opinion, so "216 uncovered" sat in a
    JSON file and escalated to nobody. This is the consumer. Two arms, because the failure has
    two shapes: the dispatcher itself going silent (the outage recursing one level up), and the
    backlog sitting un-drained. Both are the same defect class -- a schedule nobody is checking.
    """
    state = ROOT / "data" / "manifest_dispatch_state.json"
    if not state.is_file():
        defects.append(("manifest-dispatch-missing",
                        f"{state} does not exist -- the manifest dispatcher has never run, so "
                        "every ops/crontab.manifest row without a user-timer twin is dead and "
                        "unmeasured. Root cron has been down since 2026-08-20."))
        return
    try:
        data = json.loads(state.read_text("utf-8"))
    except (OSError, ValueError) as exc:
        defects.append(("manifest-dispatch-unreadable", f"{state} is unreadable ({exc})"))
        return
    try:
        age_h = (NOW - time.mktime(time.strptime(
            str(data.get("last_check", ""))[:19], "%Y-%m-%dT%H:%M:%S"))) / 3600.0
    except ValueError:
        age_h = None
    # The timer fires every 5 minutes; an hour of silence is the dispatcher itself dead.
    if age_h is None or age_h > 1.0:
        defects.append(("manifest-dispatch-stale",
                        f"manifest dispatcher last ran {age_h if age_h is None else round(age_h, 1)}h "
                        "ago (timer is every 5min) -- the organ that resurrects cron rows is "
                        "itself down. `systemctl --user status quant-manifest-dispatch`."))
    uncovered = int(data.get("uncovered_unallowed", 0) or 0)
    if uncovered:
        toks = [str(t) for t in (data.get("uncovered_tokens") or [])][:6]
        defects.append(("manifest-backlog",
                        f"{uncovered} manifest row(s) still have no scheduler since the 08-20 "
                        f"cron death: {', '.join(toks) or 'see uncovered_tokens'}"
                        f"{' ...' if uncovered > len(toks) else ''}. Each is an organ that "
                        "leaves no artifact. Triage: allowlist the venue-agnostic positive-EV "
                        "ones in run_manifest_dispatch.py, or retire the crypto-era rows OUT "
                        "of ops/crontab.manifest so the backlog is honest rather than ignored."))
    pending = data.get("pending") or {}
    if len(pending) >= 8:
        defects.append(("manifest-dispatch-throttled",
                        f"{len(pending)} allowlisted row(s) are deferred by the memory governor "
                        f"(avail {data.get('avail_mb')}MB < {MIN_AVAIL_MB_HINT}MB floor) -- the "
                        "box is too tight to run the fleet it is scheduled to run. This is a "
                        "capacity fact, not a missing executor (L1.53): the console item is a "
                        "swapfile or a bigger box."))


#: Mirrors run_manifest_dispatch.MIN_AVAIL_MB for the message above; imported lazily would
#: couple the audit to a script, so it is restated and kept in sync by the test.
MIN_AVAIL_MB_HINT = 420


#: Long-lived daemons whose code is loaded ONCE at process start. Add any new always-on service.
_DAEMONS = {
    "quant-cashcarry": "scripts/run_cashcarry_executor.py",
    "quant-deadman": "scripts/run_deadman_switch.py",
    "quant-liquidations": "scripts/liquidation_listener.py",
    "quant-dashboard": "scripts/serve_dashboard.py",
}



# ---------------------------------------------------------------------------------------------
# RESTORED 2026-08-13, second pass. The first sweep compared PUBLIC names only and found five;
# these are private helpers the same merge dropped, surfaced by their tests rather than by the
# sweep. Recorded because it corrects the earlier claim that the casualty list was complete: it
# was complete for public names and not for the module's internals.
# ---------------------------------------------------------------------------------------------

_ORGAN_MIN_UP_H = 1.0                         # below this it is a one-shot CLI run, not an organ
# THE SLOP WAS SIZED AGAINST THE SMALLER OF TWO QUANTISATIONS. `_proc_start` is
# `btime + starttime/HZ`, and the note here accounted only for the second term -- clock ticks,
# 10ms, rounding down. But `btime` in /proc/stat is printed in WHOLE SECONDS, so `_BOOT_TS` is
# truncated by up to 1s and every derived start time inherits that error in the direction that
# makes a process look OLDER than it is. Measured on this box: a probe written and immediately
# exec'd reported its own source as 0.72s NEWER than its start -- physically impossible, and it
# fired `daemon-stale-code` on a process 1.2 seconds old.
#
# Which direction that matters in: the error only ever manufactures FALSE staleness, never hides
# real staleness, so nothing was missed -- but a fence that cries wolf is one nobody reads, and
# this desk has already retired two for exactly that. 2.0s covers btime truncation (<=1s), tick
# rounding (10ms) and the write-then-exec ordering of an ordinary deploy, and still sits orders of
# magnitude below any genuine deploy-then-restart gap, which is minutes at its very shortest.
_START_SLOP_S = 2.0


def _live_organs() -> dict[str, list[int]]:
    """{repo-relative script -> pids} for every python process running a script from this repo.

    WHY NOT `_DAEMONS`: that map holds four systemd units, and a census of the box found EIGHT
    long-lived organ processes. ops_server.py (up 122h), run_recorder{,_bybit,_spot}.py and
    mine_moat.py have no unit, so no amount of fixing the clock would have made the old loop look
    at them -- the coverage hole is independent of the clock bug and had to be closed too.

    Discovery is from the process table for the same reason `_worker_pids` is: systemd only knows
    the children it started, and an orphan that outlived a unit restart is exactly the process
    most likely to be running code nobody can replace.

    THE SELF-MATCH TRAP: brain/subagent processes carry the whole doctrine through
    `--append-system-prompt`, and the doctrine QUOTES script paths. Matching a path as a substring
    of any argv element therefore returns claude processes as desk organs and measures a brain's
    uptime as a daemon's. So the script must be an argv element IN ITS OWN RIGHT and must resolve
    to a file in this repo.
    """
    out: dict[str, list[int]] = {}
    with contextlib.suppress(OSError):
        for d in Path("/proc").iterdir():
            if not d.name.isdigit():
                continue
            try:
                argv = [a for a in (d / "cmdline").read_bytes()
                        .decode("utf-8", "replace").split("\0") if a]
            except OSError:
                continue                      # exited while we were walking
            if not argv or "python" not in Path(argv[0]).name:
                continue
            if any(a.startswith("--append-system-prompt") for a in argv):
                continue
            for a in argv[1:]:
                if not a.endswith(".py") or len(a) > 200:
                    continue
                cand = (ROOT / a) if not a.startswith("/") else Path(a)
                with contextlib.suppress(OSError, ValueError):
                    if cand.is_file() and cand.resolve().is_relative_to(ROOT):
                        rel = cand.resolve().relative_to(ROOT).as_posix()
                        if rel.startswith("tests/"):
                            break             # a pytest invocation is not an organ
                        out.setdefault(rel, []).append(int(d.name))
                        break
    return out

def _last_commit_ts(rels: list[str]) -> float:
    """Commit time of the most recent commit touching any of these paths (0 when unknown)."""
    import subprocess
    with contextlib.suppress(OSError, subprocess.SubprocessError, ValueError):
        out = subprocess.run(["git", "log", "-1", "--format=%ct", "--", *rels[:300]],
                             cwd=str(ROOT), capture_output=True, text=True,
                             timeout=20, check=False).stdout.strip()
        if out:
            return float(out)
    return 0.0

def _import_closure(entry: Path, seen: set[Path] | None = None) -> set[Path]:
    """Repo-local modules an entry point actually imports, followed transitively.

    Resolves `from libs.x.y import z` and `import libs.x.y` to files under the repo. Anything
    unresolvable is stdlib/third-party and is skipped -- those ship with the interpreter and do
    not change under a running process.
    """
    import ast
    seen = seen if seen is not None else set()
    if entry in seen or not entry.exists():
        return seen
    seen.add(entry)
    try:
        tree = ast.parse(entry.read_text("utf-8", errors="ignore"))
    except (OSError, SyntaxError):
        return seen
    mods: set[str] = set()
    for n in ast.walk(tree):
        if isinstance(n, ast.Import):
            mods |= {a.name for a in n.names}
        elif isinstance(n, ast.ImportFrom) and n.module and not n.level:
            mods.add(n.module)
    for m in mods:
        # `api` BELONGS HERE AND ITS ABSENCE WAS SILENT. `scripts/ops_server.py`'s only repo
        # import is `from api import adapters`, so with api/ missing from this set the server's
        # entire closure was ITSELF ALONE -- every change under api/ was invisible to the
        # stale-code detector, and a long-running ops_server executing superseded adapter code
        # would never be flagged. The detector reported healthy because it was looking at one
        # file. Pinned by tests/ops/test_stale_code_daemons.py, which survived a merge that
        # dropped this line.
        if m.split(".")[0] not in {"libs", "app", "scripts", "api"}:
            continue
        for cand in (ROOT / (m.replace(".", "/") + ".py"),
                     ROOT / m.replace(".", "/") / "__init__.py"):
            if cand.exists():
                _import_closure(cand, seen)
    return seen


def _proc_start(pid: int) -> float | None:
    """Wall-clock epoch a process actually started. THE ONLY CORRECT SOURCE ON LINUX.

    `Path("/proc/<pid>").stat().st_mtime` LOOKS like a process start time and is not one. It is
    the procfs DIRECTORY inode's mtime, which the kernel refreshes as the directory is walked --
    so it reads ~now for any process something is polling, and only coincides with the true start
    for a process nobody looks at. Measured on this box: pid 1, which nothing polls, matched its
    real start (595.08h vs 595.1h), while EVERY supervised daemon read 0.0167h against true ages
    of 6.9h, 139.8h and 180.1h. The population it is wrong about is exactly the population this
    check exists to audit: monitored daemons.

    That is what welded `check_stale_daemons` shut. `stale = files newer than started` with
    `started ~= now` can only ever match a file edited in the last minute, so the detector for
    "a committed fix did not ship" could not fire -- and the `up {age}h` it printed into every
    unsupervised-daemon defect was ~0.0h always, a fabricated number handed to a human.

    Field 22 of /proc/<pid>/stat is starttime in clock ticks since boot; /proc/stat's `btime` is
    the boot epoch. comm (field 2) can contain spaces and parens, so the split starts after the
    LAST ')' -- the standard parse, and the reason this is a helper rather than four inline
    copies.

    RETURNS None ON AN EXITED PID RATHER THAN RAISING. A scan walks a pid list assembled a moment
    earlier, so a process exiting between the listing and the read is ORDINARY, not exceptional --
    and the previous contract ("raises OSError/ValueError, which every caller already handles")
    made the routine case an exception that any caller forgetting to wrap would turn into a crashed
    sweep. A fence that dies partway through reports nothing about the organs it never reached, and
    the desk reads a missing defect as no defect. None says "this process is gone" in a value the
    type system carries to every caller.
    """
    try:
        st = Path(f"/proc/{pid}/stat").read_text("utf-8")
        starttime = int(st[st.rindex(")") + 2:].split()[19])
        btime = next(int(ln.split()[1]) for ln in Path("/proc/stat").read_text("utf-8").splitlines()
                     if ln.startswith("btime "))
    except (OSError, ValueError, StopIteration, IndexError):
        return None
    return btime + starttime / os.sysconf("SC_CLK_TCK")


def _mtime_is_content_change(p: Path, floor: float) -> bool:
    """Whether a post-start mtime reflects a CONTENT change, not a bulk git rewrite.

    The union's mtime half exists to catch a pull/restore/rollback swapping bytes under a
    running process -- the case commit dates miss when the swapped-in code is OLDER than the
    process. But checkout/rebase/merge rewrite the mtime of byte-identical files too, and on
    mtime alone the Tier-3 RUIN RAIL read as running stale code for 19 days (measured
    2026-08-18: run_deadman_switch.py mtime 2026-08-09 from one bulk git op, content identical
    to its 2026-07-30 commit, process started 63s AFTER that commit -- a false page telling a
    human to restart the deadman for nothing, the cry-wolf that gets a fence switched off,
    L1.43/L1.37). So: compare the file's bytes against the last commit touching it BEFORE the
    process started. Identical -> the rewrite provably changed nothing, stay quiet. Different,
    no pre-start commit, outside the repo, or git unavailable -> the alarm stands; over-reporting
    remains the safe direction and dirty working-tree edits still fire (they differ by
    definition).
    """
    if not p.is_relative_to(ROOT):
        return True
    rel = p.relative_to(ROOT).as_posix()
    try:
        base = subprocess.run(
            ["git", "rev-list", "-1", f"--before=@{int(floor)}", "HEAD", "--", rel],
            cwd=ROOT, capture_output=True, text=True, timeout=30, check=False,
        ).stdout.strip()
        if not base:
            return True                    # born after the process started -> genuinely new
        diff = subprocess.run(
            ["git", "diff", "--quiet", base, "--", rel],
            cwd=ROOT, capture_output=True, timeout=30, check=False,
        )
        return diff.returncode != 0
    except (OSError, subprocess.SubprocessError):
        return True


def _sources_changed_since(paths: set[Path], since: float) -> list[Path]:
    """Files whose CONTENT changed since `since` -- a committed change or an uncommitted edit.

    NOT mtime, which is the second half of what welded this check. `git checkout`, `merge`,
    `rebase` and worktree operations rewrite the mtime of every file they touch WITHOUT changing
    a byte. Measured 2026-08-05 on this box: scripts/run_deadman_switch.py and
    scripts/serve_dashboard.py both carried mtime 02:53:48 from ONE bulk git operation while
    their last real commits were 6 and 11 days earlier and both were byte-identical to HEAD. On
    mtime alone the Tier-3 RUIN RAIL reads as running stale code after every git operation --
    and this check's own docstring already knows the ending: "a check that always fires is a
    check nobody reads". Fixing the clock without fixing the signal would have swapped a
    detector that never fires for one that always does, which is not an improvement.

    So: committed files are judged by COMMIT DATE (one `git log` for the whole set), and only
    files with real uncommitted edits fall back to mtime -- where mtime IS the evidence, because
    an uncommitted edit is a content change by definition. A file git does not know about is
    treated the same way: unknown provenance, mtime is all there is.
    """
    if not paths:
        return []
    rels = {p.relative_to(ROOT).as_posix() for p in paths if p.is_relative_to(ROOT)}
    clean_tracked: set[str] = set()
    committed: set[str] = set()
    try:
        tracked = {ln.strip() for ln in subprocess.run(
            ["git", "ls-files", "--", *sorted(rels)], cwd=ROOT, capture_output=True,
            text=True, timeout=30, check=False).stdout.splitlines() if ln.strip()}
        dirty = {ln[3:].strip().split(" -> ")[-1] for ln in subprocess.run(
            ["git", "status", "--porcelain", "--", *sorted(rels)], cwd=ROOT,
            capture_output=True, text=True, timeout=30, check=False).stdout.splitlines()
            if len(ln) > 3}
        clean_tracked = tracked - dirty
        committed = {ln.strip() for ln in subprocess.run(
            ["git", "log", f"--since=@{int(since)}", "--name-only", "--format=", "--",
             *sorted(rels)], cwd=ROOT, capture_output=True, text=True, timeout=30,
            check=False).stdout.splitlines() if ln.strip()}
    except (OSError, subprocess.SubprocessError):
        # git unavailable -> we cannot tell a checkout from an edit. Everything falls to mtime:
        # over-reporting is the safe direction for "did my fix ship", and the alternative is
        # reporting nothing at all.
        clean_tracked = set()
    out = []
    for p in sorted(paths):
        rel = p.relative_to(ROOT).as_posix() if p.is_relative_to(ROOT) else str(p)
        try:
            # TRACKED AND CLEAN -> the commit date is the truth and mtime is noise.
            # ANYTHING ELSE (locally edited, untracked, gitignored, outside the repo) -> git has
            # no committed version to compare against, so mtime IS the evidence. Defaulting the
            # unknown case to "unchanged" would be the silent-swallow this whole fix exists to
            # remove, one layer down.
            changed = rel in committed if rel in clean_tracked else p.stat().st_mtime > since
            if changed:
                out.append(p)
        except OSError:
            continue
    return out


def _worker_pids(rel: str) -> list[int]:
    """PIDs actually running an entry script, discovered WITHOUT asking systemd.

    Independence is the point: systemd only knows about the children it started, so an orphan
    that outlived a unit restart is invisible in `systemctl show`. pgrep sees the process table.

    ARGV-EXACT, never a substring (caught on this check's first live run): `pgrep -f` matches the
    whole command line, and every brain/subagent process carries the full doctrine via
    `--append-system-prompt` -- which quotes `scripts/run_cashcarry_executor.py` and
    `scripts/run_deadman_switch.py` in the risk-path duty. A bare `pgrep -f <rel>` therefore
    returned claude processes as executor and dead-man workers, which would have invented
    ownership defects and measured a brain's start time as a daemon's uptime. A monitor that
    reports the wrong process is worse than no monitor. So: argv[0] must be a python, and the
    script must be an argv element in its own right, not text buried inside one.
    """
    import subprocess
    try:
        out = subprocess.run(["pgrep", "-f", rel], capture_output=True, text=True,
                             timeout=10, check=False).stdout.split()
    except (OSError, subprocess.SubprocessError):
        return []
    pids = []
    for p in out:
        if not p.isdigit():
            continue
        try:
            argv = Path(f"/proc/{p}/cmdline").read_bytes().decode("utf-8", "replace").split("\0")
        except OSError:
            continue                                  # exited between pgrep and here
        argv = [a for a in argv if a]
        if not argv or "python" not in Path(argv[0]).name:
            continue
        if any(a == rel or a.endswith("/" + rel) for a in argv[1:]):
            pids.append(int(p))
    return pids


def _owner_unit(pid: int) -> str:
    """The systemd unit that actually owns this pid, from its cgroup. "" when nothing does.

    WHY THIS EXISTS (2026-08-26). `_live_organs()` maps a script to EVERY pid running it, and
    this check then collapsed them into ONE verdict keyed on the OLDEST -- so three
    `serve_dashboard.py` processes with three different owners produced a single reading, taken
    from whichever had been alive longest.

    Measured: `quant-dashboard.service` (pid 861460, /system.slice), the token-gated desk-web
    unit (pid 2582648, --port 8788), and an ORPHAN (pid 2484799, --port 8799) left behind in
    `/user.slice/.../session-91168.scope` by an ssh session that had since closed. The orphan was
    the oldest, so `daemon-stale-code-quant-dashboard` reported ITS staleness against the UNIT's
    label -- and `run_stale_daemon_repair` dutifully restarted the unit, every run, forever. The
    restart worked (the unit's pid did change) and the verdict came back STILL-STALE because the
    stale process was never part of that unit. The defect had stood 53.9h that way.

    The orphan was also invisible to the `daemon-unsupervised` arm below, because that arm asks
    whether MainPID is anywhere in the pid SET -- and it was, via a legitimate sibling. An orphan
    hiding inside a supervised script's pid set is exactly the case that check exists to catch.
    """
    try:
        line = Path(f"/proc/{pid}/cgroup").read_text("utf-8", errors="ignore").strip()
    except OSError:
        return ""
    tail = line.rsplit("/", 1)[-1] if line else ""
    return tail if tail.endswith(".service") else ""


def check_stale_daemons(defects) -> None:
    """A daemon running code older than its own source is a fix that DID NOT SHIP.

    Origin (2026-07-26): the carry-leak alarm was committed 02:29Z and the executor had been up
    since 00:38Z, so python had already loaded the pre-fix module. The alarm sat inert for 8.7
    hours over a book bleeding 510% of its funding harvest -- the dashboard read "clean" because
    the field was simply absent. Same class as 2026-07-10, when a churn fix was inert for two
    days. Both were caught by hand; nothing mechanical looked.

    Compared against the IMPORT CLOSURE, not any-file-newer: a repo-wide mtime test fires on
    every unrelated commit, and a check that always fires is a check nobody reads.

    OWNERSHIP (2026-07-26, second instance the same day): the first version asked systemd for
    MainPID and skipped on `0`. But `0` is exactly what systemd reports while a unit sits in
    `activating (auto-restart)` -- which is the state an ORPHANED worker causes, because the
    orphan holds the singleton lock and every supervised spawn exits on it. So the detector was
    blind to the single most common way code goes inert: work being done by a process systemd
    does NOT own, surviving every `systemctl restart`. Verified live: quant-cashcarry MainPID=0
    while orphan pid 817906 (up 8.0h, pre-fix code) held the book and the unit respawned ~190
    processes/hour against it. The worker is now discovered INDEPENDENTLY of systemd, and the
    ownership mismatch is itself a defect -- an unsupervised worker means restarts do not ship
    fixes and crash-recovery is an illusion.
    """
    # DISCOVERY COMES FROM THE PROCESS TABLE, NOT FROM A HARDCODED SERVICE MAP. Iterating
    # `_DAEMONS` can only ever see organs somebody remembered to register, and the commonest way
    # code goes inert is work being done by a process systemd does not own -- exactly the
    # population a roster cannot enumerate. `_live_organs()` reads what is actually RUNNING.
    by_script = {rel: svc for svc, rel in _DAEMONS.items()}
    # Live clock, not the module-level NOW: that is snapshotted at import, so a process started
    # after the sweep began measures as NEGATIVE uptime and gets skipped as "too young".
    now = time.time()
    for rel, pids in sorted(_live_organs().items()):
        entry = ROOT / rel
        if not entry.exists():
            continue
        svc = by_script.get(rel)
        # ATTRIBUTE BEFORE JUDGING. A pid that no systemd unit owns cannot be repaired by
        # restarting one, so it must not be folded into a unit's staleness verdict -- that is
        # what made this defect self-perpetuating. Orphans get their OWN defect naming their own
        # repair (a kill), and the unit is judged only on the processes it actually owns.
        owned, orphans = [], []
        for _p in pids:
            (owned if (_owner_unit(_p) or not svc) else orphans).append(_p)
        for _p in orphans:
            _oage = (now - (_proc_start(_p) or now)) / 3600.0
            if _oage < _ORGAN_MIN_UP_H:
                continue
            defects.append((f"daemon-orphan-{rel.rsplit('/', 1)[-1].removesuffix('.py')}-{_p}",
                            f"{rel} pid {_p} (up {_oage:.1f}h) belongs to NO systemd unit -- it "
                            "was started by hand in a login session that has since closed, and "
                            "nothing supervises, restarts or ships fixes into it. It is running "
                            "whatever code existed when that session ran. `systemctl restart` "
                            f"cannot touch it: the repair is `kill {_p}` after confirming the "
                            "managed unit serves the same thing."))
        pids = owned
        if not pids:
            continue
        starts = [s for s in (_proc_start(p) for p in pids) if s is not None]
        if not starts:
            continue                       # every pid exited mid-audit; next run sees them
        started = min(starts)
        pid = min(pids, key=lambda p: _proc_start(p) or now)
        age = (now - started) / 3600.0
        if age < _ORGAN_MIN_UP_H:
            continue        # a one-shot CLI run or a just-restarted organ -- it loaded fresh code
        # LABEL FROM THE PID'S ACTUAL OWNER, not from the script->unit map. Two DIFFERENT units
        # run serve_dashboard.py here (quant-dashboard on :8080, quant-desk-web on :8788), and
        # `by_script` collapses a script to ONE unit name -- so a stale pid owned by desk-web was
        # reported under quant-dashboard's label, and the actuator restarted quant-dashboard. Same
        # class as the orphan above, one level down: a verdict is only actionable if it names the
        # thing whose restart would change it.
        #
        # RESIDUAL, STATED RATHER THAN HIDDEN: still ONE verdict per script, taken from the oldest
        # owned pid. If two units are stale at once, the older is reported, repaired, and the
        # other surfaces on the next run -- it converges rather than reporting both at once.
        label = _owner_unit(pid).removesuffix(".service") or svc or \
            rel.rsplit("/", 1)[-1].removesuffix(".py")
        # OWNERSHIP: a fix cannot ship into a process the supervisor does not control. Only
        # meaningful for scripts that HAVE a unit -- the rest are cron/loop organs by design.
        if svc:
            sd_pid, state = "", ""
            with contextlib.suppress(OSError, subprocess.SubprocessError):
                sd_pid = subprocess.run(["systemctl", "show", "-p", "MainPID", "--value", svc],
                                        capture_output=True, text=True, timeout=10).stdout.strip()
                state = subprocess.run(["systemctl", "show", "-p", "ActiveState", "--value", svc],
                                       capture_output=True, text=True, timeout=10).stdout.strip()
            if sd_pid not in {str(p) for p in pids}:
                storm = (" and the unit is stuck in auto-restart, respawning against it"
                         if state == "activating" else "")
                defects.append((f"daemon-unsupervised-{svc}",
                                f"{svc} work is being done by pid {pid} (up {age:.1f}h) which "
                                f"systemd does NOT own (MainPID={sd_pid or 'unknown'}, "
                                f"state={state or 'unknown'}){storm}. `systemctl restart` cannot "
                                "replace this process, so fixes do not ship and crash-recovery is "
                                "an illusion. Stop the unit, kill the orphan, start the unit, and "
                                "verify MainPID matches the worker."))
        closure = _import_closure(entry)
        # THE UNION OF BOTH SIGNALS, DELIBERATELY, BECAUSE THE TWO MISS IN OPPOSITE DIRECTIONS
        # AND ONLY ONE OF THOSE DIRECTIONS IS SAFE. Content-vs-commit-date (`_sources_changed_
        # since`) ignores an mtime a checkout rewrote without changing a byte -- fewer false
        # alarms, but it MISSES a pull/restore that genuinely swapped the file under a running
        # process. Raw mtime catches that and cries wolf after ordinary git operations. A
        # staleness detector guarding processes near live capital must never miss; an extra alarm
        # costs a restart, a missed one runs superseded code against money. So: flag if EITHER
        # says changed.
        # THE SLOP APPLIES TO BOTH SIGNALS OR THE UNION CRIES WOLF ON EVERY FRESH START.
        # `_proc_start` is `btime + starttime/HZ`: btime truncates to the second and starttime
        # quantises to clock ticks, so a process launched microseconds after its own file was
        # written can measure as having started BEFORE it. `_sources_changed_since` carried no
        # slop of its own, so folding it in raw flagged a freshly started organ as running stale
        # code -- the cry-wolf failure that gets a fence switched off, taking the real signal with
        # it (L1.43). 2.0s covers both quantisations and sits orders of magnitude below any
        # genuine deploy-then-restart gap, which is minutes at its shortest.
        floor = started + _START_SLOP_S
        by_mtime = {p for p in closure if p.exists() and p.stat().st_mtime > floor
                    and _mtime_is_content_change(p, floor)}
        stale = sorted(by_mtime | set(_sources_changed_since(closure, floor)))
        if not stale:
            continue
        names = ", ".join(p.relative_to(ROOT).as_posix() for p in stale[:4])
        cts = _last_commit_ts([p.relative_to(ROOT).as_posix() for p in stale])
        when = (f", last committed {datetime.fromtimestamp(cts, tz=UTC):%Y-%m-%d %H:%M}Z"
                if cts else "")
        defects.append((f"daemon-stale-code-{label}",
                        f"{rel} (pid {pid}, up {age:.1f}h) imports {len(stale)} file(s) CHANGED "
                        f"SINCE IT STARTED: {names}{when} -- python loaded the old module at "
                        "start, so every fix in those files is INERT in the running process. "
                        "Restart it and verify the new behaviour appears in its output; a "
                        "committed fix is not a shipped fix."))


def check_panel(defects) -> None:
    log = ROOT / "data/external_panel_log.jsonl"
    if not log.exists():
        defects.append(("panel-never", "external panel has never logged a run"))
        return
    last = ""
    with log.open() as f:
        for line in f:
            last = line
    ts = json.loads(last).get("ts", "")
    age_h = (datetime.now(tz=UTC) - datetime.fromisoformat(ts)).total_seconds() / 3600
    if age_h > 96:
        defects.append(("panel-stale",
                        f"external panel last ran {age_h:.0f}h ago (3d cadence + slack = 96h) "
                        "-- review capability is down (credits? crash?)"))


_MODEL_CHECK_FLOOR_D = 35      # monthly cadence + slack; a missed month is a defect, not drift


def check_model_freshness(defects) -> None:
    """The upgrade loop must RUN, and a verified upgrade must not sit unadopted.

    Origin: the desk had NO upward path at all -- panel seats and the Claude organ chain were
    both hand-pinned, so "are we on the best available model?" was answered only when a human
    remembered to ask. Automating the upgrade is not enough on its own: an automation nobody
    watches decays into the same silence. These two checks make the loop's own health visible.
    """
    for surface, path in (("panel", ROOT / "data/model_upgrade.json"),
                          ("brain", ROOT / "data/brain_model_upgrade.json")):
        st = _j(path, {})
        checked = st.get("checked")
        if not checked:
            defects.append((f"model-upgrade-never-{surface}",
                            f"{surface} model-upgrade check has never run -- the desk cannot "
                            "know whether a better flagship shipped"))
            continue
        try:
            age_d = (datetime.now(tz=UTC) - datetime.fromisoformat(checked)).days
        except (TypeError, ValueError):
            continue
        if age_d > _MODEL_CHECK_FLOOR_D:
            defects.append((f"model-upgrade-stale-{surface}",
                            f"{surface} model-upgrade check last ran {age_d}d ago (floor "
                            f"{_MODEL_CHECK_FLOOR_D}d) -- seats age silently past this point"))

    # A candidate that PASSED the live gauntlet but was never applied is a measured, verified
    # improvement left on the table -- exactly the class the maximization duty calls a defect.
    log = ROOT / "data/model_upgrade_log.jsonl"
    if log.exists():
        passed: dict[str, str] = {}
        for line in log.read_text("utf-8").splitlines():
            try:
                r = json.loads(line)
            except json.JSONDecodeError:
                continue
            if r.get("action") in ("gauntlet", "probe") and r.get("passed"):
                passed[str(r.get("incumbent"))] = str(r.get("candidate"))
            elif r.get("action") == "apply":
                for old in (r.get("promotions") or {}):
                    passed.pop(str(old), None)
            elif r.get("action") == "rollback":
                passed.clear()          # a rollback is a deliberate NO on that promotion
        if passed:
            names = ", ".join(f"{k}->{v}" for k, v in list(passed.items())[:3])
            defects.append(("model-upgrade-unadopted",
                            f"{len(passed)} model upgrade(s) passed the live gauntlet but were "
                            f"never applied ({names}) -- verified improvement left unbuilt"))


def check_coverage(defects) -> None:
    m = _j(ROOT / "data/audit_coverage.json", {})
    if not m:
        defects.append(("coverage-missing", "audit_coverage.json absent -- coverage untracked"))
        return
    files = m.get("files", {})
    stale_risk = 0
    for rec in files.values():
        if rec.get("review_class") == 1:
            la = rec.get("last_audited")
            if not la or (datetime.now(tz=UTC) - datetime.fromisoformat(la)).days > 14:
                stale_risk += 1
    if stale_risk:
        defects.append(("coverage-risk-stale",
                        f"{stale_risk} RISK-class (money path) files past their 14d review "
                        "floor -- the exact class that must never go stale"))
    if int(m.get("code_budget_chars", 999999)) <= 40000:
        defects.append(("coverage-budget-floor",
                        "adaptive review payload pinned at its 40k floor -- seats are blanking "
                        "repeatedly; coverage is crawling"))
    _check_chronic_seats(defects, m)


#: A blank inside this window is evidence about the seat NOW. Wide enough that a genuinely dying
#: seat cannot hide between panel runs, short enough that a seat which has since recovered clears.
SEAT_BLANK_WINDOW_DAYS = 7

#: Calls needed inside the window before a rate is allowed to mean anything. Below this the fence
#: says UNMEASURED rather than grading: on 2 calls a single blank reads as a 50% failure rate and
#: would prescribe swapping a healthy seat, which is the wrong direction to be confident in
#: (L1.62 -- an underpowered sample earns no verdict, and refusing to grade is a real answer).
SEAT_MIN_ATTEMPTS = 5


def _check_chronic_seats(defects, m: dict) -> None:
    """A SEAT IS SWAPPED ON WHAT IT IS DOING NOW, NOT ON WHAT IT HAS EVER DONE.

    This fence read `seat_blanks`, a LIFETIME counter that nothing anywhere resets or decays. So
    once a seat crossed 3 it fired on every run forever, whatever the seat was currently doing --
    a gate that cannot clear carries zero information, and this one's recommendation is to SWAP,
    which costs a live seat. Measured 2026-08-13: nemotron-3-super-120b-a12b sat at a lifetime 4
    while the free-roster canary reported it ALIVE and answering with all 4 seats up, and the
    session banner reported panel depth already under-driven at 403/406 seats. Acting on the
    fence would have removed a working seat to fix a failure that had stopped happening.

    THE COUNTER IS ALSO DENOMINATOR-FREE, and that half is not repaired here: "blanked 4x" out of
    four calls is a dead seat, out of four hundred it is a 1% flake rate on a free tier, and
    nothing records the attempts. Recency is the half that is measurable from what the panel
    already writes; the rate needs a success counter at the call site and is rowed separately.

    UNMEASURED RECENCY IS REPORTED, NEVER TREATED AS QUIET. Until the event log has entries, a
    seat with a lifetime tally has no recency evidence, and silently clearing the fence there
    would be absence resolving to a clean verdict on the exact history that raised it.
    """
    from scripts.build_audit_coverage import blank_rate

    lifetime = {k: int(v) for k, v in (m.get("seat_blanks") or {}).items()}
    rate = blank_rate(m, window_days=SEAT_BLANK_WINDOW_DAYS) or {}
    for seat, n in lifetime.items():
        if n < 3:
            continue
        tag = f"seat-chronic-{seat.split('/')[-1]}"
        blanks, attempts = rate.get(seat, (0, 0))
        if attempts < SEAT_MIN_ATTEMPTS:
            defects.append((
                f"{tag}-unmeasured",
                f"panel seat {seat} carries a LIFETIME blank tally of {n} and only {attempts} "
                f"recorded call(s) in {SEAT_BLANK_WINDOW_DAYS}d, below the {SEAT_MIN_ATTEMPTS} "
                f"needed to tell a dead seat from a flake, so whether it is failing NOW is "
                f"UNMEASURED. Do not swap on this: the tally never resets, so it says only that "
                f"the seat failed at some point in its history. Clears on its own once the panel "
                f"has run {SEAT_MIN_ATTEMPTS}x -- from SUCCESS, not only from a new blank."))
        elif blanks >= 3:
            defects.append((
                tag,
                f"panel seat {seat} blanked {blanks}x of {attempts} calls "
                f"({blanks / attempts:.0%}) in the last {SEAT_BLANK_WINDOW_DAYS}d (lifetime {n}) "
                f"-- chronic capacity failure that is still happening, swap-candidate with "
                f"evidence"))


def check_findings(defects) -> None:
    d = _j(ROOT / "data/findings_ledger.json", {})
    # A SUPERSEDED FINDING IS CLOSED, NOT OWED. Its mechanism was refuted by a later finding that
    # carries the live version of the concern, so the work this row asks for is work nobody should
    # do -- and it had no legal exit before, leaving `fix` (a false claim that also credits the
    # seat with a hit it did not earn) as the only way to stop it firing. It stays listed in
    # `track_findings report`, so closing it is visible rather than a disappearance.
    # ONE THRESHOLD, ONE ROUNDING. `timedelta.days` TRUNCATES, so this fence used to disagree with
    # `track_findings report` -- which measures the same ledger against the same bar in float days
    # -- by up to 24h. Measured 2026-08-13: the report printed "3 ACCEPTED FINDINGS UNFIXED >14d
    # -- these are DEFECTS" (F0005/F0006/F0008 at 14.0d) while this fence returned NONE on the same
    # file in the same second. A human reading one and a gate reading the other is the shared-
    # constant divergence L1.61 exists for, and it errs toward silence, which is the direction
    # nobody notices. The constant is now imported rather than re-typed, so they cannot drift.
    # AN ESCALATED FINDING IS OWED BY A NAMED PERSON, ON A CLOCK -- and the two ends of that
    # clock are DIFFERENT defects, never one. While the hold is live the row is silent here: the
    # repair is legally reserved to a human (F0025 asks for a change to the Tier-3 ruin rail,
    # which every worker prompt forbids editing), so firing `findings-rotting` at it demands work
    # nobody is permitted to do -- the exact cry-wolf that gets a fence switched off. Once the
    # hold LAPSES it fires its own louder defect NAMING the person, because "a seat has not got
    # round to it" and "the principal has not ruled in two weeks" want different responses and
    # folding them together loses the only actionable half.
    from scripts.track_findings import UNFIXED_DEFECT_D, escalation_lapsed

    now = datetime.now(tz=UTC)
    open_rows = [f for f in d.get("findings", [])
                 if f.get("ruling") == "accepted" and not f.get("fixed")
                 and not f.get("superseded_by")]
    lapsed = [f for f in open_rows if f.get("escalated") and escalation_lapsed(f)]
    old = [f for f in open_rows
           if not f.get("escalated")
           and (now - datetime.fromisoformat(f["raised"])).total_seconds() / 86400.0
           > UNFIXED_DEFECT_D]
    if old:
        ids = ", ".join(f["id"] for f in old[:5])
        defects.append(("findings-rotting",
                        f"{len(old)} ACCEPTED panel findings unfixed >{UNFIXED_DEFECT_D:.0f}d "
                        f"({ids}) -- the loop "
                        "the audit system exists for is open"))
    if lapsed:
        who = ", ".join(sorted({str(f.get("escalated_to") or "(unnamed)") for f in lapsed}))
        ids = ", ".join(f["id"] for f in lapsed[:5])
        defects.append(("findings-escalation-lapsed",
                        f"{len(lapsed)} escalated finding(s) ({ids}) outlived their hold with no "
                        f"decision from {who} -- an escalation silences this fence, so an expired "
                        "one is an amnesty until it is renewed, ruled on, or withdrawn"))


def check_idle_capability(defects) -> None:
    if (ROOT / "data/secrets/databento.json").exists():
        cme = ROOT / "data/lake/bronze/cme"
        pulled = list(cme.glob("*.csv")) if cme.exists() else []
        if not pulled:
            defects.append(("idle-databento",
                            "Databento key verified but ZERO CME data pulled to Bronze -- "
                            "one-time credits idling"))
    vl = ROOT / "docs/research/video_locked_log.md"
    if vl.exists():
        stale_rows = 0
        for line in vl.read_text("utf-8").splitlines():
            if line.startswith("| 2026"):
                try:
                    d = datetime.fromisoformat(line.split("|")[1].strip())
                    if (datetime.now(tz=UTC) - d.replace(tzinfo=UTC)).days > 7:
                        stale_rows += 1
                except Exception:
                    pass
        if stale_rows:
            defects.append(("video-locked-unactioned",
                            f"{stale_rows} video-locked mechanisms logged >7d with no unlock "
                            "decision -- evidence gate met but purchase page never made?"))


def check_directives(defects) -> None:
    """Time-boxed work orders: registered with a due date; past-due = defect. This is how
    'the brain will do it next cycle' gets teeth instead of drifting forever."""
    for d in _j(ROOT / "data/max_audit_directives.json", []):
        if d.get("due", "9999") < datetime.now(tz=UTC).isoformat():
            defects.append((f"directive-overdue-{d['id']}",
                            f"work order '{d['id']}' past due {d['due'][:10]}: {d['msg']}"))


def check_verify_lag(defects) -> None:
    """The verify pass audits the CRO's own triage -- and the CRO fires it. If triage-bearing
    panels keep running without a verify run following, the auditee is skipping his auditor."""
    log = ROOT / "data/external_panel_log.jsonl"
    if not log.exists():
        return
    last_triage, last_verify = None, None
    with log.open() as f:
        for line in f:
            try:
                r = json.loads(line)
            except Exception:
                continue
            if r.get("mission") == "verify":
                last_verify = r.get("ts")
            elif r.get("mission") in ("audit", "tier1", "premortem", "maximization"):
                last_triage = r.get("ts")
    if last_triage and (not last_verify or last_verify < last_triage):
        age_h = (datetime.now(tz=UTC) - datetime.fromisoformat(last_triage)
                 ).total_seconds() / 3600
        if age_h > 48:
            defects.append(("verify-pass-skipped",
                            f"last triage-bearing panel ({last_triage[:16]}) has had NO verify "
                            "pass after it for >48h -- the auditee is skipping his auditor"))


def check_blind_trigger(defects) -> None:
    """Blind Rediscovery is state-driven, not clock-driven: fire it early when the desk has
    materially new internal raw material (data axes / graveyard entries) since its last run."""
    from libs.ops.blind_trigger import counts as _blind_counts

    state = _j(ROOT / "data/cadence_state.json", {})
    last = state.get("last_blind_rediscovery")
    seen = _j(ROOT / "data/blind_trigger_baseline.json", {})

    # ONE counting rule, shared with the actuator that clears this trigger
    # (libs/ops/blind_trigger.stamp, called by the dig on verified production) --
    # two copies of the count is how the detector and the clearer drift apart.
    n_sources, n_grave = _blind_counts(ROOT)

    base_src = int(seen.get("sources", 0))
    base_grave = int(seen.get("graveyard", 0))
    d_src, d_grave = n_sources - base_src, n_grave - base_grave

    # thresholds: enough NEW material that first-principles invention has fresh ground
    if d_src >= 5 or d_grave >= 10:
        defects.append(("blind-rediscovery-due-by-state",
                        f"internal state changed materially since last blind-rediscovery "
                        f"({last or 'never'}): +{d_src} data sources, +{d_grave} graveyard "
                        "entries. Fire ops/run_blindrediscovery_dig.sh -- fresh-eyes invention "
                        "has new raw material; do not wait for the monthly floor."))


def _recorder_pause_reason() -> str:
    """Why the tape recorders are not writing, READ from what they publish. '' == they are writing.

    Returns "SWITCHED-OFF" | "DISK-PAUSED" | "".

    TWO STATES THAT ARE NOT DEFECTS, AND ONE THAT WELDED A GATE SHUT. `data/RECORDERS_OFF` is the
    desk's own non-root kill switch (scripts/recorder_switch.py) -- the exact file
    data/PRINCIPAL_ACTION.md tells the principal to touch to ACCEPT the crypto-tape retirement
    (Constitution 224 / commit 6b8b61a9 / R0717). Nothing in this file had ever heard of it:
    `grep -c RECORDERS_OFF scripts/max_audit.py` was 0. So accepting the retirement would have
    left `recorder-scope-shrank` and `tape-recording-stopped` firing forever, identically and
    unclearably, on a decision the desk had deliberately made -- the ACCEPT path welded shut by
    the fence that was supposed to watch it. A gate that cannot be satisfied by doing the right
    thing is a §33 Tier-1 defect-closer, and this desk has shipped that exact shape before (a
    file-presence gate holding the sterile cockpit shut over a retired executor's flat book).

    DISK-PAUSED is self-protection, not a stall: run_recorder.py:281-287 stops writing above
    _DISK_MAX_FRAC=0.80 and keeps the heartbeat fresh, stamping the marker so a reader can tell.
    Reading it is what separates "the recorder broke" from "the disk filled up".

    This LOOSENS NOTHING: a genuinely stalled recorder publishes neither marker and still fires
    the original defect with the original message.
    """
    if (ROOT / "data" / "RECORDERS_OFF").exists():
        return "SWITCHED-OFF"
    for hb in ("recorder_heartbeat", "recorder_spot_heartbeat", "recorder_bybit_heartbeat"):
        try:
            if "DISK-PAUSED" in (ROOT / "data" / hb).read_text("utf-8"):
                return "DISK-PAUSED"
        except OSError:
            continue      # a heartbeat we cannot read is not evidence of a pause
    return ""


def check_self_application(defects) -> None:
    """Each of these encodes a max-fix the principal forced this session, as a REGRESSION guard.
    His pressure, made permanent: a future edit that undoes any becomes a same-day defect."""
    orgs = ["run_cro_ai.sh", "run_frontier_miner.sh", "run_prospector_dig.sh",
            "run_litminer_dig.sh", "run_dataaxis_dig.sh", "run_blindrediscovery_dig.sh"]
    for name in orgs:
        fp = ROOT / "ops" / name
        if not fp.exists():
            defects.append((f"organ-missing-{name}", f"organ script {name} vanished"))
            continue
        txt = fp.read_text("utf-8", errors="ignore")
        if "claude" in txt and "-p " in txt:
            if "--effort" not in txt:
                defects.append((f"effort-dropped-{name}",
                                f"{name}: claude call lost its --effort flag (max-reasoning "
                                "regressed to CLI default) -- re-add xhigh"))
            if "--append-system-prompt" not in txt and "_DOCTRINE" not in txt:
                defects.append((f"doctrine-dropped-{name}",
                                f"{name}: lost the principal-doctrine injection "
                                "(--append-system-prompt \"$_DOCTRINE\") -- the max-push stance "
                                "is no longer in this organ"))
    # cost-censorship must never creep back into the advisory layer
    for mp in (ROOT / "prompts/panel_missions").glob("*.txt"):
        if mp.stem == "maximization":
            continue  # legitimately quotes fossils as the anti-patterns it hunts
        t = mp.read_text("utf-8", errors="ignore").lower()
        for fossil in ("worthless", "$1/mo", "at most rare one-off cheap"):
            if fossil in t and "not worthless" not in t:
                # 'worthless' is allowed only in the sanctioned "a recommendation ignoring
                # STRUCTURAL constraints is worthless" phrasing; flag other reappearances
                if fossil == "worthless" and "structural" in t:
                    continue
                defects.append((f"cost-censorship-{mp.stem}",
                                f"panel mission {mp.name}: cost-self-censorship language "
                                f"'{fossil}' reappeared -- money-recs must stay proposable"))
    # recorder scope + liveness -- measure the GROUND-TRUTH tape, not the source code.
    # Until 2026-07-23 this regex-scanned run_recorder.py for a literal `_SYMBOLS = (...)`
    # tuple; gap #39 (2026-07-22) made _SYMBOLS a dynamic expression, so the regex matched
    # nothing, read 0, and FALSE-fired "dropped to 0" while 30 symbols were actively
    # recording. Counting the symbol directories that received a fresh write is the true
    # breadth measure AND catches a silent write-stall the source regex could never see --
    # the desk's own "heartbeat liveness != data liveness" lesson applied to the breadth
    # check (a stalled recorder keeps a fresh heartbeat but stops writing files).
    fut_root = ROOT / "data/moat/fut"
    if fut_root.exists():
        cutoff = time.time() - 1800.0   # a symbol counts only if written in the last 30 min
        live = sum(1 for d in fut_root.iterdir()
                   if d.is_dir() and any(f.stat().st_mtime > cutoff
                                         for f in d.glob("*.jsonl.gz")))
        if live < 20:
            # RESTORED 2026-08-26 (lost half of 3da91a1d, which never merged: the CHECKS landed
            # and their un-welder did not). Three causes, three different actions, and only one
            # of them is this defect -- without this, a recorder that is alive, healthy and
            # DELIBERATELY paused reported as "breadth regressed or the recorder stalled".
            reason = _recorder_pause_reason()
            if reason == "SWITCHED-OFF":
                pass          # a recorded decision via the desk's own kill switch
            elif reason == "DISK-PAUSED":
                defects.append((
                    "recorder-disk-paused",
                    f"recorder futures tape has {live} symbols written in the last 30min, "
                    "because the recorders PAUSED THEMSELVES on disk pressure (heartbeat marker "
                    "DISK-PAUSED, run_recorder.py _DISK_MAX_FRAC=0.80) -- the recorders are "
                    "healthy and the DISK is the defect. Reclaim space or buy it; do not chase "
                    "the recorder."))
            else:
                defects.append(("recorder-scope-shrank",
                                f"recorder futures tape has {live} symbols written in the last "
                                "30min (expansion floor is 20) -- forward-tape breadth regressed "
                                "or the recorder stalled"))
    # bybit second-venue recorder must still exist
    if not (ROOT / "scripts/run_recorder_bybit.py").exists():
        defects.append(("bybit-recorder-gone", "second-venue (bybit) recorder script removed -- "
                        "cross-venue tape breadth lost"))

#: Staleness bound for the CI marker. daily_research_cycle runs the gate once a day, so 48h is
#: two consecutive missed cycles -- comfortably past "the box was busy", squarely at "it stopped".
_CI_STALE_H = 48.0


def check_ci_gate(defects) -> None:
    """The desk-wide gate must be GREEN, and must be PROVABLY RUNNING.

    Extracted from check_self_application (2026-08-05) so the fail-closed behaviour below can be
    exercised directly by a test. A safety check whose only coverage is a source grep is a check
    whose logic nobody has ever run.

    CI GATE must be GREEN -- a red desk-wide gate is the safety net down for everyone and
    sat UNDETECTED for 81h (2026-07-22..23: a stale deadman test failed at HEAD while the
    brain cycle that runs run_ci was quota-dead, so nothing surfaced the red). run_ci writes
    data/.ci_last_run.json on every run; surface a red result mechanically so it enters the
    48h escalation path instead of hiding until a human notices.
    """
    # AND A STALE MARKER IS A DEFECT TOO -- fail-closed (2026-08-05). Reading `ok is False` alone
    # catches a gate that RAN and failed, and is blind to the more dangerous case: a gate that
    # stopped running. run_ci holds a flock for its whole run, so any step that wedges leaves the
    # lock held; every later run then takes the "another run holds the lock -- skipping (marker
    # left untouched)" path and returns 0 by design. The marker freezes at its last value, and a
    # frozen marker is never False. The desk would report its safety gate green, with nothing
    # behind it, for as long as the wedge lasted -- which is the same blindness as the 81h above,
    # only quieter, because this version never produces a red anything to notice.
    #
    # The timestamp was already being written and already being read; only its AGE went unchecked.
    # An unreadable, absent or unparseable marker is treated the same way as an old one: on a
    # safety gate the honest reading of "unknown" is "not proven green", never "fine".
    ci_marker = ROOT / "data/.ci_last_run.json"
    if not ci_marker.exists():
        defects.append(("ci-gate-unproven",
                        "data/.ci_last_run.json absent -- the desk-wide gate has no recorded "
                        "result at all. Unknown is NOT green. Run scripts/run_ci.py"))
    else:
        try:
            ci = json.loads(ci_marker.read_text("utf-8"))
            # READ THE TRACKED VERDICT (2026-08-05). This box runs several agent sessions against
            # ONE working tree, so the whole-tree `ok` also goes False when a concurrent session
            # has a half-written untracked file -- breakage that belongs to no commit and that
            # the observer cannot fix. Escalating that made ci-gate-red recur 8x in 10.7d and,
            # worse, BURIED a real one: on 2026-08-05 all 5 lint errors were scratch files while
            # two genuine mypy errors sat in committed code inside the same red verdict.
            # `tracked_ok` is absent on markers written before that fix -- fall back to `ok`, so
            # an old marker still escalates rather than silently reading as green. Staleness is
            # NOT softened by this: ci-gate-stale below is unchanged and still fail-closed.
            if ci.get("tracked_ok", ci.get("ok")) is False:
                # A RESOURCE KILL IS NOT A CODE FAILURE, AND THE PRODUCER ALREADY KNOWS THE
                # DIFFERENCE (2026-08-26). run_ci.py writes a separate `killed` list and its
                # entries carry their own diagnosis -- the 08-26 marker reads verbatim "KILLED
                # sig9, MemAvailable 827MB, 495MB of RAM held by files under /tmp (tmpfs) -- box
                # ran out of resources mid-step, NOT a code failure". This consumer never read
                # that field, so the desk-wide safety gate reported "RED on COMMITTED code" about
                # a run whose own record says the code was never the problem.
                #
                # The two demand OPPOSITE repairs: one sends someone to find a bug that does not
                # exist, the other says reclaim memory and re-run when quiet. Merging them is the
                # same defect the tracked_ok fix above was written for -- a red nobody can act on
                # recurs, gets skimmed, and BURIES a real one. Still a defect either way: unknown
                # is never green, and the gate has not proven anything.
                failed = list(ci.get("failed_tracked") or ci.get("failed") or [])
                killed = set(ci.get("killed") or [])
                if failed and all(f in killed for f in failed):
                    defects.append(("ci-gate-resource-killed",
                                    f"last CI run ({ci.get('ts')}) did not finish -- every "
                                    f"tracked failure is a RESOURCE KILL, not a code failure: "
                                    f"{failed}. The gate has proven NOTHING (unknown is not "
                                    "green), but the repair is capacity, not a code fix: reclaim "
                                    "memory (scripts/disk_guard.py has a tmpfs arm) and re-run "
                                    "scripts/run_ci.py when the box is quiet."))
                else:
                    # A RED IS A STATEMENT ABOUT A TREE, AND THE TREE MOVES (2026-08-28).
                    # run_ci now stamps the commit it measured. On 2026-08-28 the 08:54 marker
                    # named 25 committed-code failures; every one was fixed by 09:39, and this
                    # check went on reporting "RED on COMMITTED code" -- sending a reader to hunt
                    # a bug that no longer existed. Same burying as the tracked_ok and
                    # resource-killed splits above: an un-actionable red recurs, gets skimmed, and
                    # hides the next real one. The two demand OPPOSITE work -- one is "find the
                    # bug", the other is "re-run the gate" -- so they get separate names.
                    # STILL A DEFECT either way: a verdict about a superseded tree has proven
                    # NOTHING about this one, and unknown is never green. An absent `head`
                    # (markers written before this fix) or an unresolvable HEAD keeps the old
                    # escalation, so the fail-closed direction is unchanged.
                    marker_head = ci.get("head")
                    live_head = _git_head()
                    if marker_head and live_head and marker_head != live_head:
                        defects.append(("ci-gate-red-superseded",
                                        f"last CI run ({ci.get('ts')}) was red -> {failed}, but "
                                        f"it measured commit {marker_head[:8]} and HEAD is now "
                                        f"{live_head[:8]}. Do NOT hunt those failures until they "
                                        "are re-observed -- they may already be fixed. The gate "
                                        "has proven nothing about the current tree (unknown is "
                                        "not green): re-run scripts/run_ci.py, then fix whatever "
                                        "survives."))
                    else:
                        defects.append(("ci-gate-red",
                                        f"last CI run ({ci.get('ts')}) was RED on COMMITTED code "
                                        f"-> {failed}; the desk-wide safety gate is down. "
                                        "Run scripts/run_ci.py + fix"))
            # NOW is epoch seconds (time.time()), not a datetime -- compare in epoch space.
            age_h = (NOW - datetime.fromisoformat(str(ci.get("ts"))).timestamp()) / 3600.0
            if age_h > _CI_STALE_H:
                defects.append(("ci-gate-stale",
                                f"last CI run was {age_h:.0f}h ago (>{_CI_STALE_H:.0f}h) -- the "
                                "gate has STOPPED RUNNING, which a green marker cannot show. "
                                "Usual cause: a wedged run_ci still holding data/.ci_run.lock, "
                                "so every later run exits 0 'skipping'. Check for a stuck "
                                "process, then run scripts/run_ci.py"))
        except (OSError, json.JSONDecodeError, TypeError, ValueError):
            defects.append(("ci-gate-unproven",
                            "data/.ci_last_run.json unreadable or has no parseable timestamp -- "
                            "cannot prove the desk-wide gate ran. Unknown is NOT green."))


def check_dig_depth(defects) -> None:
    """Depth guard: a substantial dig log that shows NO depth markers (never mined a reply
    chain, followed a fork, or chased a citation) is breadth-theater -- flag it. Depth quality
    ultimately shows in output and is judged by red-team/maximization; this catches the gross
    wide-and-shallow case mechanically."""
    # TWO CLASSES OF DEPTH, because the original list encoded only one and misgraded the other.
    # CORPUS depth is following a source down: reply chains, forks, citations, threads. The list
    # below it is VERIFICATION depth -- re-deriving a claim rather than repeating it -- which
    # costs at least as much and looks nothing like the first in prose.
    #
    # WIDENED ON A MEASURED FALSE POSITIVE (2026-08-12), the same remedy check_timidity_language
    # records for its own vocabulary. frontier_br_20260812T0827 scored 1/11 and was flagged
    # breadth-theater. What it actually did: reimplemented a repo's "MCPT validation" to show it
    # permutes order-invariant statistics (max-min across 500 permutations = 1.1e-15, so the
    # p-value is a floating-point rounding hash), censused 23 archive vintages to RETRACT its own
    # predecessor's inferred decay rate, ran the native-key control that exposed a structural
    # zero, and recorded a falsifier instead of picking the exciting hypothesis. Grading that as
    # theatre is not a harmless miss: a lexical fence teaches seats to WRITE the words it counts,
    # so a list blind to verification depth actively pushes digs toward comment-tree breadth --
    # the fence causing the failure it detects.
    #
    # THE BAR IS UNCHANGED at <2 hits. This adds sight, not slack, and it stays a GROSS detector
    # by its own docstring -- lexical markers are fakeable by construction and real depth quality
    # is judged downstream by red-team/maximization. FALSIFIER: if a dig ever clears this bar on
    # verification words alone while its output shows no re-derivation, the class is noise and
    # comes back out.
    # THE VOCABULARY ENCODED ONE DIG MODALITY AND SCORED EVERY OTHER ONE AS THEATRE. Every marker
    # above the second line is community/text mining (reply, comment, thread, fork, citation) or
    # code replication (permut, reimplement, census). A dig into a BULK ARCHIVE or an API does its
    # depth with a different vocabulary entirely, so it was structurally incapable of clearing this
    # bar however deep it went -- a gate that rejects ~100% of a category carries zero information
    # about that category, which is the welded-gate class this desk hunts (L1.43/L1.49).
    #
    # MEASURED, 2026-08-12: dataaxis_20260812T1530 scored 1. That dig verified a published sha256
    # sidecar, ran archive-vs-live to 0 mismatches over 31 bars x 7 fields, and found that the S3
    # lister truncates at 1000 keys and never errors -- a 3.7-YEAR silent understatement of the
    # archive's depth, now a recorded desk lesson. That is the depth mandate honoured exactly, and
    # the fence called it breadth-theater.
    #
    # THIS IS NOT THE BAR BEING LOWERED TO FIT THE VIOLATION IT CAUGHT, and the distinction is the
    # whole point: the threshold stays at >=2, and every added marker names a VERIFICATION ACT
    # PERFORMED rather than an adjective or an intention. `backfill` was tried and REJECTED for
    # exactly that reason -- its only occurrence in the corpus is "still needs a pi backfill",
    # which names work NOT done, and a marker that passes on intent is how this becomes theatre.
    # Measured over all 9 substantial digs on disk: exactly ONE flips, and the shallow log still
    # fires. FALSIFIER, inherited from the rule above and unchanged: if a dig ever clears the bar
    # on verification words alone while its output shows no re-derivation, the class comes out.
    markers = ("repl", "comment", "thread", "fork", "citation", "issue", "discussion",
               ">=2", "deep", "exhaust", "debunk",
               "permut", "reimplement", "replicat", "census", "falsifier",
               "positive control", "graveyard", "wayback", "retract",
               # archive / API verification: the act, never the adjective
               "paginat", "sha256", "checksum", "mismatch", "sidecar", "cross-check",
               "byte-for-byte", "truncat")
    for pat in ("frontier_*.log", "dataaxis_*.log", "prospector_*.log", "litminer_*.log"):
        logs = sorted(LOGS.glob(pat), key=lambda p: p.stat().st_mtime, reverse=True)
        if not logs:
            continue
        _mand = ROOT / "data/depth_mandate_baseline"
        if not _mand.exists():
            _mand.write_text(str(NOW))
        try:
            _base = float(_mand.read_text().strip())
        except Exception:
            _base = NOW
        # JUDGE THE NEWEST *JUDGEABLE* DIG, NOT THE NEWEST FILE. This took `logs[0]` and then
        # `continue`d if it was a stub -- so one 171-byte "DEFERRED -- brain mutex held by cro_ai"
        # notice, written seconds ago, silently exempted the ENTIRE frontier family from depth
        # judgement while four substantial digs from that morning sat unread. The fence reported
        # no defect over a set it never opened: a passing verdict on an empty scan, which is the
        # vacuous-denominator class (L1.57) rather than a threshold being too loose. Stubs are
        # still not judged for depth -- check_organs owns quota-deaths -- they just no longer
        # blind the family behind them.
        newest = next((p for p in logs
                       if p.stat().st_size >= 1500                      # substantial dig
                       and p.stat().st_mtime >= _base                   # post-mandate
                       and (NOW - p.stat().st_mtime) <= 4 * 86400), None)  # not stale
        if newest is None:
            continue
        txt = newest.read_text("utf-8", errors="ignore").lower()
        hits = sum(1 for m in markers if m in txt)
        if hits < 2:
            defects.append((f"dig-shallow-{newest.stem}",
                            f"{newest.name}: substantial dig with <2 depth markers "
                            f"({hits}) -- breadth-theater, no reply/fork/citation mining "
                            "evident. Depth mandate not honored."))


def _cycle_evidence() -> CycleEvidence:
    """The ONE evidence reading both cycle-quality fences judge, on the ONE log they both select.

    Computed here rather than twice, because the fences below previously chose their own log by
    their own window AND scored it by their own proxy, so they could -- and on 2026-08-01 did --
    return contradictory verdicts about the same cycle. Sharing the selection and the scoring is
    what makes that contradiction structurally impossible; see libs/ops/cycle_evidence.py.

    A missing baseline is still bootstrapped (first run stamps it and declines to judge cycles
    that predate the protocol), but "no judgeable log" is now UNMEASURED rather than a silent
    clean return -- L1.28a, and the vacuous pass L1.57 exists to refuse."""
    from libs.ops import cycle_evidence

    base_f = ROOT / "data/interrogation_baseline"
    if not base_f.exists():
        base_f.write_text(str(NOW))
        return cycle_evidence.unmeasured("interrogation baseline just stamped -- no post-protocol "
                                         "cycle exists to judge yet")
    try:
        base = float(base_f.read_text().strip())
    except Exception as e:
        return cycle_evidence.unmeasured(f"interrogation baseline unreadable ({e!r}) -- cannot "
                                         "tell a pre-protocol cycle from a post-protocol one")
    cyc = [p for p in LOGS.glob("2026*_*.log")
           if p.stat().st_mtime >= base and p.stat().st_size >= 2000]
    if not cyc:
        return cycle_evidence.unmeasured(
            f"no cycle log in {LOGS.name} is both post-protocol and >=2000 bytes -- the desk "
            "cannot show that its last cycle interrogated anything")
    newest = max(cyc, key=lambda p: p.stat().st_mtime)
    return cycle_evidence.score(newest.read_text("utf-8", errors="ignore"), log_name=newest.name)


def check_interrogation(defects) -> None:
    """The last successful brain cycle must show evidence it ran the self-interrogation battery.
    A cycle that did not probe is a cycle that trusted itself -- the exact failure this catches.

    FIRES ON TOTAL ABSENCE OF EVIDENCE, not on the absence of five magic words. The keyword grep
    this replaces ('interrogat', 'probe', 'verified with a fresh read', 'self-interrog', 'angle')
    fired on a cycle that had verified its headline finding from the journal with timestamps and
    values and disproved a CI-red by isolation -- it had simply never typed one of the words.
    Whether the interrogation was CITED is a different question and belongs to the fence below;
    this one asks only whether it happened at all."""
    ev = _cycle_evidence()
    if not ev.measured:
        defects.append(("cycle-evidence-unmeasured",
                        f"cannot judge cycle interrogation: {ev.why_unmeasured}. UNMEASURED is "
                        "not a pass -- absence of evidence was reading as evidence of health."))
        return
    if ev.substance == 0:
        defects.append(("cycle-skipped-interrogation",
                        f"{ev.log}: last successful cycle shows no self-interrogation evidence -- "
                        "no artifact cited with a value, no self-correction, no finding disproved. "
                        "It trusted itself instead of probing. Protocol not honored."))


def check_generation(defects) -> None:
    """Hypothesis testing is the primary output. If SUCCESSFUL brain cycles have run since a
    baseline but last_live_generate has not advanced, generation is being skipped -- escalate.
    Also flags the simple case: generation owed and long-stale.

    ARTIFACT OVER FLAG (2026-07-28). This read ONLY cadence_state.last_live_generate -- a key a
    cycle sets by hand -- and so reported generation "skipped" on a day the Stage-A executor had
    already screened and written real verdicts, while it would equally have reported generation
    DONE for a cycle that touched nothing but the timestamp. Both errors have the same root: the
    check trusted a flag instead of demanding the product, which is the exact failure the desk's
    own check_production exists to catch (`scheduled but not PRODUCING`). The verdict ledger is
    the artifact -- newest of {flag, last real verdict row} wins, and a run that screens without
    updating the key is now correctly credited.
    """
    cs = _j(ROOT / "data/cadence_state.json", {})
    last_gen = cs.get("last_live_generate") or cs.get("gen_done_fred_macro")
    verdicts = ROOT / "data/stage_a_verdicts.jsonl"
    last_verdict = None
    if verdicts.exists():
        with contextlib.suppress(Exception):
            for ln in reversed(verdicts.read_text("utf-8").splitlines()):
                if ln.strip() and (ts := json.loads(ln).get("ts")):
                    last_verdict = ts                 # newest row carrying a real timestamp
                    break
    if last_verdict and (not last_gen or last_verdict > last_gen):
        last_gen = last_verdict
    # THIRD STORE (2026-08-01). The 07-28 fix established the right principle -- credit the
    # PRODUCT, not the flag -- but wired only two of the three places a screen actually lands. A
    # screen run through libs.research.axis_screen directly (rather than via stage_a_executor)
    # writes reports/axis_screens/<axis>.json and NOTHING else, so this check called generation
    # "skipped" on days real screens ran. Measured: it had been firing for 5.8d and was walked
    # past by 10 awake cycles -- while R0069's decisive 38-asset / 84,891-asset-day panel screen
    # was written to reports/axis_screens/ that very afternoon. Same shape as the §37 ack bug
    # fixed in this commit: an organ judging the desk from a partial view of the evidence, then
    # escalating. Newest of {flag, verdict row, screen report} wins.
    # L1.44: content `updated` OUTRANKS mtime -- a deploy or checkout rewrites files and mtime
    # then lies FRESH, which is the dangerous direction here (it would credit generation that
    # never happened). Fall back to mtime only for the reports whose schema carries no stamp.
    screens = ROOT / "reports/axis_screens"
    if screens.is_dir():
        for p in screens.glob("*.json"):
            with contextlib.suppress(Exception):
                stamp = None
                blob = json.loads(p.read_text("utf-8"))
                if isinstance(blob, dict):
                    stamp = blob.get("updated") or blob.get("generated")
                iso = str(stamp) if stamp else datetime.fromtimestamp(
                    p.stat().st_mtime, tz=UTC).isoformat()
                if not last_gen or iso > last_gen:
                    last_gen = iso
    # successful cycles since a fixed watch baseline
    base_f = ROOT / "data/generation_watch_baseline"
    if not base_f.exists():
        base_f.write_text(str(NOW))
    try:
        base = float(base_f.read_text().strip())
    except Exception:
        base = NOW
    good_cycles = [p for p in LOGS.glob("2026*_*.log")
                   if p.stat().st_mtime >= base and p.stat().st_size >= 2000]
    if not good_cycles:
        return                                        # no successful cycle yet -- quota, not skip
    newest_cycle = max(p.stat().st_mtime for p in good_cycles)
    gen_ts = 0.0
    if last_gen:
        with contextlib.suppress(Exception):
            gen_ts = datetime.fromisoformat(last_gen).timestamp()
    # a successful cycle ran AFTER the last generation -> generation was skipped
    if newest_cycle > gen_ts + 3600:
        defects.append(("generation-skipped",
                        f"a successful brain cycle ran with no generation after it "
                        f"(last screened verdict / gen flag: {last_gen}) -- hypothesis testing, "
                        "the desk's PRIMARY output, "
                        "is being crowded out by meta-duties. Generation-first duty not honored."))


#: How long the origin ledger may go unwritten before silence becomes a finding. The desk finds
#: gaps continuously -- every cycle, every sweep -- so a week of no rows does not mean a week
#: without gaps; it means a week without logging them.
_BLINDSPOT_STALE_D = 7.0


def _parse_iso(raw: object) -> float | None:
    """An ISO stamp as epoch seconds, or None. None is a real answer: a row that cannot date
    itself cannot bound the ledger's freshness, and must never be counted as recent."""
    if not isinstance(raw, str) or not raw:
        return None
    try:
        ts = datetime.fromisoformat(raw)
    except ValueError:
        return None
    return (ts if ts.tzinfo is not None else ts.replace(tzinfo=UTC)).timestamp()


def check_self_sufficiency(defects) -> None:
    """The meta-check: is the desk finding its own gaps, or is the principal still doing it?
    Reads the blind-spot ledger; if over the recent window the principal is the primary finder,
    the whole maximization apparatus is not yet working -- the top-level defect."""
    # THE CHECK USED TO BE DISABLED BY THE ABSENCE OF ITS OWN INPUT (fixed 2026-08-05).
    #
    # Both early returns below were silent, and together they made this -- the desk's ONLY measure
    # of whether it or the principal is finding the gaps -- reward non-compliance exactly:
    #
    #     skip the logging duty  ->  no ledger  ->  no defect  ->  the desk looks self-sufficient
    #
    # An organ that stops performing a duty thereby switched off the check on that duty. The
    # cheapest way to a clean self-sufficiency reading was to never log anything, and on this box
    # that is precisely the state found: data/blind_spot_ledger.jsonl DOES NOT EXIST, while L2.5
    # has mandated origin-tagging every gap since 2026-07-21.
    #
    # It is the same fail-open as the CI marker and the source-health verdicts -- unknown reading
    # as fine -- but it is the most expensive instance of it, because this is the meta-check. It
    # is the one that would have told the desk that its whole maximisation apparatus was not
    # working, and it could not fire while the apparatus was not working.
    #
    # So absence, emptiness and thinness are each a NAMED defect now. Note the direction: none of
    # them claims the desk is failing to find gaps. They claim the desk CANNOT SHOW that it is,
    # which is a different and honest statement, and the only one the evidence supports.
    lg = ROOT / "data/blind_spot_ledger.jsonl"
    if not lg.exists():
        defects.append(("self-sufficiency-unlogged",
                        "data/blind_spot_ledger.jsonl does not exist -- L2.5 mandates an "
                        "origin-tagged row for EVERY gap found, and not one has been written. "
                        "The desk cannot show whether it or the principal is finding its gaps, "
                        "and skipping the duty is what silenced the check. "
                        "Log via scripts/blind_spot.py log --origin self|guard|principal"))
        return
    rows = []
    for line in lg.read_text("utf-8").splitlines():
        with contextlib.suppress(Exception):
            rows.append(json.loads(line))
    live = [r for r in rows if not r.get("baseline")]  # judge post-baseline gaps only
    # STALENESS, same reasoning as the CI marker: a ledger that stopped being written is a duty
    # that stopped being performed, and its last rows keep describing a desk that no longer
    # exists. Measured on the ledger's own newest stamp, never the file mtime -- any organ that
    # touches the file would otherwise reset the clock without a gap having been logged.
    newest = max((_parse_iso(r.get("ts")) for r in rows if r.get("ts")), default=None)
    if newest is not None and (NOW - newest) / 86400.0 > _BLINDSPOT_STALE_D:
        defects.append(("self-sufficiency-stale",
                        f"blind-spot ledger last written {(NOW - newest) / 86400.0:.1f}d ago "
                        f"(>{_BLINDSPOT_STALE_D:.0f}d) -- gaps are still being found (this sweep "
                        "found some) and none are being logged, so the origin accounting has "
                        "quietly stopped. A frozen ledger reads as a settled one."))
    if len(live) < 8:
        defects.append(("self-sufficiency-unproven",
                        f"blind-spot ledger holds {len(live)} post-baseline row(s); 8 are needed "
                        "before the self/guard/principal split means anything. This is NOT a "
                        "clean bill of health -- it is too little evidence to give one, and it "
                        "used to be reported as silence, which reads identically to passing."))
        return
    by = {"self": 0, "guard": 0, "principal": 0}
    for r in live:
        by[r.get("origin", "principal")] = by.get(r.get("origin", "principal"), 0) + 1
    if by["principal"] > by["self"] + by["guard"]:
        defects.append(("system-not-self-sufficient",
                        f"blind-spot ledger: principal still the primary gap-finder "
                        f"({by['principal']} vs self {by['self']} + guard {by['guard']}) -- the "
                        "maximization system is not yet doing its job. TOP defect."))


def _blind_rows_window(days=7):
    lg = ROOT / "data/blind_spot_ledger.jsonl"
    if not lg.exists():
        return []
    cut = NOW - days * 86400
    out = []
    for line in lg.read_text("utf-8").splitlines():
        try:
            r = json.loads(line)
        except Exception:
            continue
        if r.get("baseline"):
            continue
        try:
            if datetime.fromisoformat(r["ts"]).timestamp() >= cut:
                out.append(r)
        except Exception:
            pass
    return out


def check_rubberstamp_detector(defects) -> None:
    """Signature: >=3 successful cycles CLAIMED interrogation, found ZERO gaps themselves, yet
    the principal found >=2 in the same window. That is probing theater. Auto-activate the
    enforcement, page, and log -- the desk deciding for itself that it needs the higher bar."""
    flag = ROOT / "data/ANTIRUBBERSTAMP_ACTIVE"
    if flag.exists():
        return                                        # already active
    cyc = [p for p in LOGS.glob("2026*_*.log") if p.stat().st_size >= 2000
           and (NOW - p.stat().st_mtime) < 7 * 86400]
    interrogated = 0
    for p in cyc:
        t = p.read_text("utf-8", errors="ignore").lower()
        if any(k in t for k in ("interrogat", "probe", "self-interrog")):
            interrogated += 1
    rows = _blind_rows_window(7)
    self_ct = sum(1 for r in rows if r.get("origin") == "self")
    princ_ct = sum(1 for r in rows if r.get("origin") == "principal")
    if interrogated >= 3 and self_ct == 0 and princ_ct >= 2:
        flag.write_text(f"auto-activated {datetime.now(tz=UTC).isoformat()}: {interrogated} "
                        f"cycles claimed interrogation, 0 self-gaps, {princ_ct} principal-gaps "
                        "-- rubber-stamp signature")
        defects.append(("rubberstamp-detected-ACTIVATED",
                        f"RUBBER-STAMP SIGNATURE: {interrogated} cycles claimed to interrogate but "
                        f"found 0 gaps while the principal found {princ_ct}. Anti-rubber-stamp "
                        "enforcement AUTO-ACTIVATED -- cycles must cite named reads per angle."))
        try:
            import subprocess
            subprocess.run(["python", "scripts/blind_spot.py", "log", "--origin", "guard",
                            "--summary", "auto-activated anti-rubber-stamp: interrogation was "
                            "probing theater (claimed, found nothing, principal found real gaps)"],
                           cwd=str(ROOT), timeout=20)
        except Exception:
            pass


def check_rubberstamp_enforcement(defects) -> None:
    """Active only when the flag exists: the newest successful cycle must show NAMED VERIFIED
    READS, not bare 'verified' prose.

    A NAMED VERIFIED READ IS A PATH AND A VALUE, which is what the cycle prompt has always asked
    for ("file path + the value/line you saw"). The count this replaces matched path-shaped
    tokens only, so five filenames nobody opened passed it while a cycle that read carefully and
    reported its numbers against bare module names failed. Same floor, better measurement: the
    bar did not move, the instrument did.

    It judges THE SAME LOG as check_interrogation above, by construction. Two fences that pick
    their own log cannot be prevented from disagreeing about the cycle."""
    flag = ROOT / "data/ANTIRUBBERSTAMP_ACTIVE"
    if not flag.exists():
        return
    ev = _cycle_evidence()
    if not ev.measured:
        return                      # check_interrogation already raised cycle-evidence-unmeasured
    if not ev.cited:
        from libs.ops.cycle_evidence import CITED_FLOOR
        defects.append(("rubberstamp-enforced",
                        f"{ev.log}: anti-rubber-stamp ACTIVE but the cycle cites only "
                        f"{ev.cited_claims} artifact(s) with a value (floor {CITED_FLOOR}; it "
                        f"names {ev.artifacts} artifact(s) in total) -- interrogation lacks "
                        "verified-read evidence. Cite the specific file+value per probe angle "
                        "(web/growth_audit.json, capital_util=1.005), not a bare module name."))


def check_clock_saturation(defects) -> None:
    """OBJECTIVE #2 CLOCK-SATURATION DUTY (principal 2026-07-23), made mechanical.

    Every VERIFIED data axis must have a pre-registered hypothesis ACCRUING within 7 days. An
    empty forward-validation slot is idle capital's research twin: the axis was ingested (real
    cost paid) but is generating zero evidence, so the discovery objective is silently stalled.

    This duty shipped as prompt text only -- and prompt-only duties are aspirations. The desk's
    recursion rule is that every manual probe becomes a standing automatic check, so it is fenced
    here. Axes are read from the Bronze lake (what was actually ingested, not what a doc claims).

    WHAT IT READS, AND WHY THAT CHANGED (2026-08-12). The first cut graded `gen_done_<axis>` in
    cadence_state as a RECENCY clock. That key is a one-way PRESENCE latch, and its own producer
    refuses to re-stamp it when a run pre-registers nothing new -- run_axis_generate.py:196: "
    writing 'done at <now>' for work not done this run is the same lie in a quieter file". So 7
    days after the last NEW axis this fired on every axis forever, and the only way to clear it
    was the re-stamp its producer calls a lie. It also misread the QUANTITY: on 2026-08-12 it
    reported `crossasset` as having NO hypothesis accruing while data/forward_slots.json carried
    a standing crossasset clock ACCRUING since 2026-06-21 -- 52 days. All 9 flagged axes in fact
    held dated EV-gate cards in two pre-registration docs (2026-07-22 and 2026-08-05), which is
    the duty's own second branch ("or ledger why the axis is not yet testable") already satisfied.
    A gate that rejects 100% on a quantity it does not measure carries zero information
    (GATE-OPTIMALITY DUTY, L1.43), and its only available remedy was fabrication.

    So it now reads the two stores that actually hold the answer -- the Holm cohort
    (data/forward_slots.json) for ACCRUING, and the `axis=` trail run_axis_generate stamps into
    research_agenda.json for LEDGERED -- and it stays able to FIRE, on two genuine breaches:
    an ingested axis with NEITHER (nobody ever authored a hypothesis for paid-for data), and a
    ledgered-but-unclocked axis while the cohort has IDLE SLOTS, which is the literal L1.28a
    idleness this duty exists to catch -- a free slot next to an authored hypothesis. At 12/12
    with zero idle slots the clocks ARE saturated (the metric this check is named for) and no
    axis can start one without displacing another: the Holm cap binds, not researcher idleness,
    and MAX_FORWARD_SLOTS is a validation bar that is never widened to clear a defect. The
    cohort file's own freshness is L1.44's job, not a second uncoordinated rule here."""
    bronze = ROOT / "data/lake/bronze"
    if not bronze.exists():
        return
    # INPUT STORES are not axes: raw price/metrics lakes feed constructions but cannot carry
    # a hypothesis themselves (the constructions built FROM them do). Excluding them keeps this
    # check pointed at genuinely idle research axes instead of manufacturing false defects.
    _input_stores = {"futclose_daily", "oi_ls_daily", "fx", "index", "crypto", "binance_metrics"}
    axes = sorted(d.name for d in bronze.iterdir() if d.is_dir() and d.name not in _input_stores)
    if not axes:
        return
    # UNMEASURED is a real answer (L1.28a): an absent accrual store is not an empty one, and
    # treating it as empty would manufacture a breach on every axis -- the exact failure above.
    try:
        fs = json.loads((ROOT / "data/forward_slots.json").read_text("utf-8"))
        slots = [s for s in fs.get("slots") or [] if isinstance(s, dict)]
        idle = int(fs.get("idle_slots") or 0)
    except Exception:
        defects.append((
            "clock-saturation",
            f"UNMEASURED: data/forward_slots.json is absent or unreadable, so the accrual state "
            f"of {len(axes)} verified axes cannot be read at all. Absence is not health and is "
            "not idleness either -- repair the cohort producer before grading this duty."))
        return
    accruing = {str(s.get("name", "")) for s in slots}
    # The ledger branch the duty explicitly allows. run_axis_generate stamps `axis=<name>` into
    # every pre-registration it routes -- QUEUED or EV-rejected-with-a-revisit-condition alike --
    # so this is the machine-readable trail of "a hypothesis was actually authored for this axis".
    try:
        ledgered = set(re.findall(
            r"axis=([a-z_]+)", (ROOT / "research_agenda.json").read_text("utf-8")))
    except Exception:
        ledgered = set()
    ungenerated = [a for a in axes if a not in accruing and a not in ledgered]
    unclocked = [a for a in axes if a not in accruing and a in ledgered]
    if ungenerated:
        defects.append((
            "clock-saturation",
            f"OBJECTIVE #2 breach: {len(ungenerated)}/{len(axes)} verified axes have NEITHER a "
            f"forward clock NOR a pre-registered hypothesis -- {', '.join(ungenerated[:8])}"
            f"{' ...' if len(ungenerated) > 8 else ''}. Ingest cost was paid and nothing was ever "
            "authored against it: pre-register a hypothesis on each, or ledger why the axis is "
            "not yet testable (e.g. forward history under the gauntlet minimum)."))
    if unclocked and idle > 0:
        defects.append((
            "clock-saturation",
            f"OBJECTIVE #2 breach: {idle} forward slot(s) sit IDLE while {len(unclocked)}/"
            f"{len(axes)} axes hold an authored-but-unclocked hypothesis -- "
            f"{', '.join(unclocked[:8])}{' ...' if len(unclocked) > 8 else ''}. An empty forward "
            "clock beside a ready hypothesis is idle research capital (L1.28a): start the clock. "
            "Slots are the scarce input, so spend them shortest-capacity-runway first."))


def check_vendor_replacement(defects) -> None:
    """FREE-ALTERNATIVES-TO-PAID enforcement (principal 2026-07-24). The dataaxis dig's pillar 6
    mandates decomposing every paid vendor into a free reconstruction with a ground-truth diff;
    this check makes that output rot-proof: entries must be complete, UNVERIFIED grades must not
    sit while a daily dig runs, and the free-hunt itself must keep landing updates."""
    ump = ROOT / "data/data_universe_map.json"
    if not ump.exists():
        defects.append(("vendor-replacement", "data_universe_map.json MISSING"))
        return
    try:
        d = json.loads(ump.read_text("utf-8"))
    except Exception as e:
        defects.append(("vendor-replacement", f"universe map unreadable: {e!r}"))
        return
    vr = (d.get("sources") or {}).get("vendor_replacement") or []
    if not isinstance(vr, list) or not vr:
        defects.append(("vendor-replacement",
                        "no vendor_replacement entries -- the free-alternatives hunt has "
                        "recorded zero paid-vendor decompositions"))
        return
    for e in vr:
        v = str(e.get("vendor", "?"))[:40]
        if not e.get("free_path"):
            defects.append(("vendor-replacement",
                            f"{v}: NO free_path -- a paid product with no owned reconstruction"))
        if not e.get("ground_truth_for_diff"):
            defects.append(("vendor-replacement",
                            f"{v}: NO ground_truth_for_diff -- verify-don't-trust is impossible; "
                            "find a free sample/reference to diff the reconstruction against"))
        g = str(e.get("grade", "")).lower()
        if "unverified" in g:
            defects.append(("vendor-replacement",
                            f"{v}: grade UNVERIFIED while the free-data dig runs DAILY -- "
                            "verify the free path this cycle or ledger why it cannot be"))
    # the hunt itself must keep landing: daily dig -> map bookkeeping must move
    try:
        lfd = datetime.fromisoformat(str(d.get("last_free_dig")))
        age_d = (NOW - lfd.timestamp()) / 86400.0
        if age_d > 3:
            defects.append(("vendor-replacement",
                            f"last_free_dig {age_d:.1f}d old while the data-axis dig is DAILY -- "
                            "the free-alternatives hunt is not landing updates to the map"))
    except Exception:
        defects.append(("vendor-replacement", "last_free_dig missing/unparsable in universe map"))


def check_forensics_fresh(defects) -> None:
    """DAILY PnL/churn/loss analysis is GUARANTEED, not assumed (principal 2026-07-24): the
    trade-forensics probe (the mechanical version of the probes that found gaps #42/#43/#34)
    must have produced a fresh verdict within 26h, or the desk is flying without its daily
    bleed detection -- the exact silent-leak failure mode the integrity watch exists to kill.

    THE DUTY SURVIVES THE MANDATE; ITS ARTIFACT DID NOT (2026-08-27). `web/trade_forensics.json`
    is the funding/maker-fill/hold-bucket forensics of the crypto cashcarry book, retired by
    principal order, and the MT5 desk holds no live capital yet (readiness rung 0). So there are
    no fills to analyse, and reporting that as "not landing; check daily_research_cycle" blamed a
    healthy organ for the absence of a book -- the same misattribution `live_readiness` made when
    it called a desk defect a fact about the market.

    UNMEASURABLE IS ITS OWN VERDICT (L1.28a), so it is reported rather than quietly skipped, and
    the duty RE-ARMS BY ITSELF: the moment the desk reaches a rung above 0 the staleness bar
    applies again with no edit here. Absence of a book is never permission to stop watching for
    bleed; it is only the honest reason there is none to see."""
    fj = ROOT / "web/trade_forensics.json"
    try:
        rung = int(json.loads((ROOT / "data/live_readiness.json").read_text("utf-8"))["rung"])
    except (OSError, ValueError, KeyError, TypeError):
        rung = -1               # unreadable readiness is NOT "no book"; fall through and gauge
    if rung == 0:
        defects.append(("forensics-unmeasurable",
                        "trade-class bleed forensics UNMEASURABLE, not stale: readiness is rung 0 "
                        "(no live capital) and the only forensics artifact on disk belongs to the "
                        "retired crypto cashcarry book, which the MT5 mandate bans re-running. "
                        "The duty stands and re-arms automatically at rung > 0; nothing here is "
                        "evidence the desk is bleeding unwatched"))
        return
    if not fj.exists():
        defects.append(("forensics-stale", "web/trade_forensics.json MISSING -- daily "
                        "trade-class bleed analysis has never produced output"))
        return
    age_h = (NOW - fj.stat().st_mtime) / 3600.0
    if age_h > 26:
        defects.append(("forensics-stale",
                        f"trade_forensics.json {age_h:.0f}h old (>26h) -- the daily churn/"
                        "bleed/PnL analysis is not landing; check daily_research_cycle"))


def check_carry_funding_measured(defects) -> None:
    """The carry-leak alarm must be able to SEE (2026-07-26 incident).

    The alarm is denominated in the funding harvest, so a failed venue read blinds it entirely.
    Before this check the executor filled that gap with `0.0` and the alarm dutifully published an
    `inf%` total-bleed verdict against a book that had really earned $101.96 -- an HTTP 502
    rendered as an economic judgement. The fix makes the harvest honestly None, which means the
    alarm now goes QUIET during an outage instead of loud-and-wrong; that trade is only safe if
    the silence itself is a tracked defect, which is this function. A blind alarm and a clean book
    look identical on a dashboard and must never look identical here.
    """
    cj = ROOT / "web/cashcarry_live.json"
    if not cj.exists():
        return                                        # book not running is a different check
    try:
        cc = json.loads(cj.read_text("utf-8"))
    except Exception:
        defects.append(("carry-funding-unmeasured", "web/cashcarry_live.json unparsable -- the "
                        "carry-leak alarm cannot be read at all"))
        return
    # Absent key = an executor predating the fix, which is exactly the silent-zero state.
    if cc.get("funding_measured", False) is not True:
        age_h = (NOW - cj.stat().st_mtime) / 3600.0
        defects.append((
            "carry-funding-unmeasured",
            f"carry funding harvest UNMEASURED (venue income read failing, book {age_h:.0f}h old) "
            f"-- the leak alarm is BLIND: it cannot tell a clean hedge from a bleeding one, and "
            f"the forward track record the sizing gate reads is accruing without its edge term. "
            f"Verdict: {str(cc.get('bleed_verdict', ''))[:120]}"))
        return
    # THE ALARM ACTUALLY FIRING must fail something too. Until 2026-07-31 this branch did not
    # exist: bleed_alert was computed, written to JSON, rendered on the dashboard -- and gated
    # nothing, so a book whose non-funding P&L was 3146% of its harvest could read as a SURVIVOR.
    # A fence firing into a field nobody reads is not a fence.
    if cc.get("bleed_alert") is True:
        # AN ABSORBING ALARM CARRIES ZERO INFORMATION (R0352, L1.43 welded gate). `bleed_alert` is
        # computed from CUMULATIVE-LIFETIME totals, and a book holding no positions cannot accrue
        # new funding or new non-funding P&L -- so with exposure at zero BOTH terms of the ratio
        # are frozen by construction and the alarm is arithmetically incapable of ever clearing.
        # Measured: it fired every cycle for 7+ days against `funding_harvested` pinned at the
        # same 113.06 while `n_carries` was 0. That is not a leak, it is a stuck needle.
        #
        # THE THRESHOLD IS NOT TOUCHED, and that direction is forbidden -- the bar in
        # carry_bleed_report is unchanged and a book with ANY exposure alarms exactly as before.
        # What changes is only WHICH CLAIM is made about a book that cannot move the number.
        #
        # ABSENCE IS NOT ZERO. `n_carries`/`deployed_notional` must both be PRESENT and zero to
        # earn the flat reading; an executor predating those keys falls through to the live alarm,
        # because "no exposure" and "we cannot see the exposure" are opposite states and only one
        # of them is safe to quieten (WS-005, the desk's most-repeated defect class).
        legs, notl = cc.get("n_carries"), cc.get("deployed_notional")
        flat = (isinstance(legs, int) and legs == 0
                and isinstance(notl, int | float) and float(notl) == 0.0)
        recon = cc.get("fut_leg_reconciliation") or {}
        attributed = recon.get("explained") is True and recon.get("measured") is True
        verdict = str(cc.get("bleed_verdict", ""))[:200]
        if not flat:
            defects.append((
                "carry-bleed-alarm",
                f"carry leak alarm FIRING and unactioned -- {verdict}"))
        elif not attributed:
            # STILL A DEFECT, AND DELIBERATELY A DIFFERENT ONE. The leak is historical rather than
            # live, but nobody has said where it went -- and unlike the cumulative ratio this IS
            # satisfiable: attributing the gap clears it. A quiet fence here would be the muting
            # this repair exists to avoid.
            defects.append((
                "carry-bleed-unattributed",
                f"carry book is FLAT (0 carries, 0 notional) but a lifetime bleed is UNATTRIBUTED "
                f"-- the futures-leg reconciliation does not explain it "
                f"(explained={recon.get('explained')!r} measured={recon.get('measured')!r}). "
                f"Closed episode, open question: {verdict}"))


def check_memory_hygiene(defects) -> None:
    """MEMORY layer fences (principal 2026-07-24): institutional memory must be written, fresh,
    and retrievable -- a memory system nobody writes to or that outgrows retrieval is theater.
    Found at audit time: research_memory had 0 rows ever while mission directives claim to write
    it; the brain memory index was a week stale and used the principal old name."""
    # (a) the brain's own memory index must stay fresh (it is the first thing cycles read)
    mi = ROOT / "ops/memory/MEMORY.md"
    if mi.exists():
        age_d = (NOW - mi.stat().st_mtime) / 86400.0
        if age_d > 7:
            defects.append(("memory-index-stale",
                            f"ops/memory/MEMORY.md {age_d:.0f}d old -- the brain memory index "
                            "must be refreshed weekly with current desk state (cycle duty)"))
    # (b) research_memory must actually be written by the analyst missions that cite it
    try:
        import sqlite3
        n = sqlite3.connect(str(ROOT / "data/sor_research.sqlite")).execute(
            "SELECT COUNT(*) FROM research_memory").fetchone()[0]
        if n == 0:
            defects.append(("research-memory-unused",
                            "research_memory has 0 rows EVER while mission directives claim "
                            "every analyst pass writes to it -- either write it (hypothesis ID + "
                            "economic logic + EV score per mission) or remove the claim"))
    except Exception:
        pass
    # (c) ledger bloat: append-only is sacred, but retrieval must survive growth
    lp = ROOT / "data/decision_ledger.json"
    if lp.exists() and lp.stat().st_size > 1_500_000:
        defects.append(("ledger-bloat",
                        f"decision_ledger.json {lp.stat().st_size/1e6:.1f}MB -- run the memory-"
                        "consolidation duty (archive-never-delete, index the archive) before "
                        "tail-reads go lossy"))


#: Characters of doctrine per COMMITMENT above which the file is carrying prose that does no
#: work. The live doctrine sits near 140; a padded one runs into four figures. Anchored to the
#: measured density rather than to a round number, and it can go red the moment somebody adds
#: waffle rather than law.
_DOCTRINE_CHARS_PER_COMMITMENT = 400.0

#: Absolute ceiling, so density cannot license unbounded growth: a doctrine that doubles in size
#: while staying dense is still a doubled context bill on every organ call.
_DOCTRINE_HARD_CEILING = 60_000


def _check_doctrine_density(doc, defects) -> None:
    """Is the doctrine LONG, or is it BLOATED? They are not the same defect and the old check
    could not tell them apart.

    WHAT THIS REPLACES, AND WHY THE OLD VERSION WAS ACTIVELY DANGEROUS. The previous rule fired on
    file size past 16k and prescribed: "consolidate the stacked axiom blocks into tighter prose
    (preserve every commitment, cut the repetition)". Measured against the actual file, that
    advice is false in its premise and harmful if followed:

      * repetition:  ONE near-duplicate sentence pair out of 17,955 pairs across 190 sentences.
                     There is essentially nothing to consolidate.
      * commitments: 247 distinct obligations -- section marks, defect names, artifact paths,
                     thresholds, tier weights, named laws -- at ~140 chars each.

    So the file is long because it contains a great deal of distinct law, not because it says
    anything twice, and "cut the repetition" resolves in practice to "cut law". A shorter doctrine
    that dropped an obligation is strictly worse than a long one that kept it: the context tax is
    paid per call and is small, while a missing law is paid once, at an unknown later date, in
    full. An audit that prescribes a harmful remedy is worse than one that stays silent, because
    the remedy carries the audit's authority.

    Scoping the injection per organ was the other candidate and is refused for a different reason:
    the principal's standing instruction is that every law binds every interaction at full
    coverage. Sending each organ only the sections that "apply to it" is a coverage reduction
    wearing an efficiency costume, and which laws apply is exactly what an organ cannot be trusted
    to have decided for it.

    What remains is the real question: does the doctrine contain prose that carries no commitment?
    That is measurable, it is the actual definition of bloat, and it still goes red -- padding the
    file with exhortation raises chars-per-commitment immediately.
    """
    if not doc.exists():
        return
    try:
        text = doc.read_text("utf-8")
    except OSError:
        return
    from libs.doctrine.commitments import extract
    n = sum(len(v) for v in extract(text).values())
    size = len(text)
    if n <= 0:
        defects.append((
            "prompt-doctrine-empty",
            f"principal_doctrine.txt is {size/1000:.1f}k chars and states NO checkable "
            "commitment -- no section mark, artifact path, threshold or named law. Every organ "
            "injects this; a doctrine of pure exhortation is context with no instruction in it."))
        return
    density = size / n
    if density > _DOCTRINE_CHARS_PER_COMMITMENT:
        defects.append((
            "prompt-doctrine-bloat",
            f"principal_doctrine.txt carries {density:.0f} chars per commitment "
            f"({size/1000:.1f}k chars, {n} commitments) against a bar of "
            f"{_DOCTRINE_CHARS_PER_COMMITMENT:.0f}. The file is padded with prose that binds "
            "nothing -- cut the exhortation, keep every obligation. Verify with "
            "libs.doctrine.commitments.diff(before, after), which fails on any lost commitment."))
    if size > _DOCTRINE_HARD_CEILING:
        defects.append((
            "prompt-doctrine-oversized",
            f"principal_doctrine.txt is {size/1000:.1f}k chars, past the "
            f"{_DOCTRINE_HARD_CEILING/1000:.0f}k ceiling, at {density:.0f} chars/commitment. "
            "Density alone cannot license unbounded growth: this is a context bill every organ "
            "pays on every call. Splitting law out to a referenced document is the move, never "
            "deleting it."))


def check_prompt_layer(defects) -> None:
    """PROMPT-LAYER hygiene (principal 2026-07-24 prompt audit): the prompts are organs too.
    (a) Doctrine bloat: the doctrine is prepended to EVERY organ call; past ~16k chars the
    stacked supreme-blocks start diluting mission instructions -- consolidate, never just stack.
    (b) State-triggered prompt review: the 28d review cadence is calendar-based, but when the
    contract/doctrine change materially the review is due by STATE (the blind-rediscovery
    precedent) -- a week of unreviewed prompt mutations is how contradictions accrete."""
    doc = ROOT / "ops/principal_doctrine.txt"
    _check_doctrine_density(doc, defects)
    # (c) DESK MEMORY OVERFLOW. The lesson corpus is hard-budgeted so that new lessons DISPLACE
    # weaker ones instead of growing every organ's context -- that budget is the whole reason it
    # cannot become a second 95k doctrine file. But overflow still means the desk paid for a
    # lesson it is no longer telling anyone, so it must be visible rather than quietly ranked out.
    # The fix is to retire a lesson whose falsifier arrived, NOT to raise the budget.
    # A GRADUATED LESSON IS NOT AN UNREACHED ONE. Counting the whole overflow reported 31 lessons
    # "reaching NO organ" when 20 were enforced by a verified test and demoted on purpose -- 2.8x
    # overstated, which buries the 11 real losses in noise and teaches the reader to skip the line.
    try:
        from libs.research.desk_memory import BUDGET_CHARS, unreached
        lost, demoted = unreached()
        if lost:
            tail = (f" [{len(demoted)} further lesson(s) ranked out but enforced by a verified "
                    "test -- demoted by design, not lost]" if demoted else "")
            defects.append(("desk-memory-overflow",
                            f"{len(lost)} paid-for lesson(s) exceed the {BUDGET_CHARS}-char "
                            f"memory budget and reach NO organ: "
                            f"{', '.join(o.id for o in lost)} -- retire a lesson whose falsifier "
                            f"arrived, or graduate one to a test (scripts/learn.py audit).{tail}"))
    except Exception as exc:  # never silently OK on absent input (L1.41)
        defects.append(("desk-memory-unmeasured",
                        f"the lesson corpus could not be read ({type(exc).__name__}: {exc}) -- "
                        "what reaches an organ is UNKNOWN, which is not the same as healthy"))
    try:
        cad = json.loads((ROOT / "data/cadence_state.json").read_text("utf-8"))
        last_rev = datetime.fromisoformat(cad["last_prompt_review"]).timestamp()
        contract = (ROOT / "ops/run_cro_ai.sh").stat().st_mtime
        doc_m = doc.stat().st_mtime if doc.exists() else 0
        newest_change = max(contract, doc_m)
        if newest_change > last_rev and (NOW - newest_change) / 86400.0 > 7:
            defects.append(("prompt-review-due-by-state",
                            "contract/doctrine changed materially since the last prompt review "
                            f"({cad['last_prompt_review'][:10]}) and the newest change is >7d "
                            "old -- run the prompt-review duty NOW (check for duty collisions, "
                            "stale numbers, contradictions), do not wait for the 28d floor"))
    except Exception:
        pass


# RETIRED 2026-09-05 (universe mandate): `check_bnb_funded`. It signed a GET against the Binance
# futures testnet balance endpoint to confirm the ~25% BNB fee-burn discount was actually funded.
# BNB is a crypto-exchange asset and the burn is a Binance account setting; neither has any
# meaning on an MT5/Fusion book, where the cost line is spread + commission + swap and the desk
# reads it from the broker, not from a token balance. Nothing replaces it because there is nothing
# to replace: the equivalent MT5 question ("is the cost model the one the broker actually
# charges?") is already asked by desks/mt5/research/cost_surface.py.
#
# Its law row went with it -- see the `bnb-funded` entry removed from CHECKS below.


def _git_age_h(rel: str) -> float:
    """Hours since this path's last COMMIT, or inf if git does not know it."""
    try:
        out = subprocess.run(["git", "log", "-1", "--format=%ct", "--", rel],
                             cwd=ROOT, capture_output=True, text=True, timeout=20, check=False)
        ts = out.stdout.strip()
        return (NOW - float(ts)) / 3600.0 if ts else float("inf")
    except (OSError, ValueError, subprocess.SubprocessError):
        return float("inf")


def _production_age_h(p: Path) -> float:
    """Age of a product artifact, in hours -- mtime for untracked, WORSE-OF for tracked.

    MTIME LIES ABOUT TRACKED FILES, ALWAYS IN THE FLATTERING DIRECTION. `git clone` stamps every
    checked-out file with the CLONE time, so a doc last authored a week ago reports as hours old
    on a fresh machine. Measured here: four `docs/research/*` products reported 131h stale while
    their last commit was 168h back -- the staleness gate was reading the age of the checkout, not
    the age of the work, and understating it by a day and a half. A freshness check that gets
    younger every time you clone the repo is not measuring production.

    Untracked products keep mtime: they are written in place and git knows nothing about them.
    Tracked products take the WORSE of mtime-age and last-commit-age, which is strict in the one
    direction the desk already demands -- §33 credits output only once it is committed and pushed,
    so an artifact freshly written but never committed is correctly still counted as not produced.
    """
    rel = _rel_root(p)
    age_mtime = (NOW - p.stat().st_mtime) / 3600.0
    global _TRACKED
    if _TRACKED is None:
        _TRACKED = _tracked_set()
    if rel not in _TRACKED:
        return age_mtime
    g = _git_age_h(rel)
    return age_mtime if g == float("inf") else max(age_mtime, g)


def check_production(defects) -> None:
    """OUTCOME-LEVEL fence (principal 2026-07-24): does each scheduled organ actually PRODUCE its
    output artifact within cadence? State-freshness checks miss the class where a scheduler fires
    but nothing is produced (cron self-match), an organ runs but refuses to emit (panel
    sanitizer), or a duty is claimed but writes nothing (research_memory). Product artifacts, not
    state files -- state can be touched without producing."""
    import glob as _glob
    # (label, product glob, max_age_h, min_bytes). Products, not state files.
    manifest = [
        ("cron-cycle", "data/cro_ai_logs/2026*_????.log", 26, 2000),
        ("panel-verdicts", "data/panel_verdicts.jsonl", 96, 100),
        ("dataaxis-product", "docs/research/data_axis_watchlist.md", 30, 100),
        # THE PRODUCT IS THE RUN, NOT A MUTATED FILE (corrected 2026-08-27). Both rows below were
        # red against organs that were behaving CORRECTLY, and in the prospector's case the fence
        # was punishing the exact behaviour the desk most wants.
        #
        # PROSPECTOR: its 2026-08-27 06:00 run took 24 minutes, raised R0673/R0674/R0675, and
        # wrote NO watchlist card -- "the public MQL5 alpha layer was picked clean again... I did
        # not fabricate survivors to cover it." Gauging `prospector_watchlist.md` by MTIME makes a
        # run that honestly found nothing indistinguishable from a run that never happened, and
        # the only way to clear the alarm is to write a card -- a fence that pays for padding, in
        # a desk whose L1.21 forbids it. So the RUN is gauged (its dated log, whose size separates
        # a real dig from a 172-byte stub) and the product keeps a weekly bar, which still catches
        # a genuinely silent organ without demanding output that does not exist.
        ("prospector-run", "data/cro_ai_logs/prospector_2026*.log", 30, 1000),
        ("prospector-product", "docs/research/prospector_watchlist.md", 168, 100),
        # LITMINER: it stands down behind its own MONTHLY gate ("last real dig is younger than
        # 28 days"), so a 30h bar was red for 28 days out of every 29 by construction -- the fence
        # asserting a cadence the organ does not have and never claimed. Gauged at its real one.
        ("litminer-product", "docs/research/*iterature*coverage*.md", 720, 50),
        ("frontier-product", "docs/research/prospector_coverage.md", 30, 100),
        # RETIRED 2026-08-27 BY THE MT5 MANDATE, not by neglect -- and retired rather than left
        # red, because a cadence row nothing may legally satisfy is a permanent alarm, and a
        # detector that is always red is one everybody learns to scroll past (L1.37 rule 1). Both
        # products belong to the crypto-exchange universe the standing principal order of
        # 2026-08-18 bans permanently (LAWS s1): `web/autodiscovery_crypto.json` is written only
        # by ops/run_crypto_factory.sh, whose twelve `quant-autodiscovery*` timers are all
        # disabled -- VERIFIED, none appears in `systemctl --user list-timers --all` and none has
        # started this boot; `web/trade_forensics.json` is the funding/maker-fill/hold-bucket
        # forensics of the retired cashcarry book (its last content is 4 closes on $25.85
        # notional). Neither can be produced again without breaching the mandate.
        #   ("crypto-factory", "web/autodiscovery_crypto.json", 30, 100),
        #   ("forensics", "web/trade_forensics.json", 30, 50),
        # THE DUTY TRANSFERS, THE ARTIFACT DOES NOT. Execution-quality forensics on MT5 ground is
        # `desks/mt5/reports/execution_quality.json`, already age-gauged at 36h in
        # check_job_manifest, so retiring the crypto row drops no coverage. If a crypto row is
        # ever wanted back, the mandate must be lifted first -- restoring the cadence is not the
        # act that lifts it.
    ]
    for label, pat, max_h, min_b in manifest:
        hits = [Path(q) for q in _glob.glob(str(ROOT / pat))]
        if not hits:
            defects.append(("production-missing",
                            f"{label}: NO product artifact exists ({pat}) -- the organ has never "
                            "produced output, only (maybe) been scheduled"))
            continue
        newest = max(hits, key=lambda q: q.stat().st_mtime)
        age_h = _production_age_h(newest)
        sz = newest.stat().st_size
        if age_h > max_h:
            defects.append(("production-stale",
                            f"{label}: {newest.name} {age_h:.0f}h old (cad {max_h}h) "
                            "-- scheduled but not PRODUCING; verify the organ actually runs end-to-"
                            "end, not just that its timer/cron fires (the cron-self-match class)"))
        elif sz < min_b and not _producer_running(label):
            defects.append(("production-stub",
                            f"{label}: product {newest.name} is {sz}b (<{min_b}b) -- ran but "
                            "produced a stub, not real output (the quota-stub / refuse class)"))
    # THE FINANCING TAPE IS UNBUYABLE ONCE THE DAY PASSES, AND IT DIED IN SILENCE. On 2026-08-29
    # `desks/mt5/data/tape/contract_terms` held exactly one file -- 2026-08-27, 9 hourly
    # observations -- while the H1 bar sync from the same Windows terminal was fresh THAT DAY, so
    # the terminal was up and only this recorder had stopped. Nothing said so, because no fence
    # gauged it: the crypto recorders had `ensure_recorder` and a staleness pager, and the
    # obligation that "TRANSFERS to mt5desk.tape" (ops/crontab.manifest:814) transferred without
    # its instrument. `mt5desk.tape --terms-only` exists precisely so the cheap perishable leg can
    # run at its own cadence; what it lacked was anything that noticed when it did not.
    #
    # GAUGED ON TRADING DAYS, NOT ON AGE. A plain mtime bar cannot distinguish a dead recorder
    # from a weekend: loose enough to survive Fri-close..Mon-open (~51h) it also sleeps through a
    # missed Friday, which is the exact miss here. So the test is the honest one -- the most
    # recent WEEKDAY that has fully passed must have a file. It cannot fire on a Saturday for
    # being a Saturday, and it fires the morning after any missed trading day.
    _terms = ROOT / "desks/mt5/data/tape/contract_terms"
    _have = {q.stem for q in _terms.glob("*.parquet")} if _terms.exists() else set()
    _day = datetime.now(UTC).date() - timedelta(days=1)
    while _day.weekday() >= 5:                      # Sat/Sun are not trading days
        _day -= timedelta(days=1)
    if not _terms.exists():
        defects.append(("production-missing",
                        "mt5-contract-terms: NO tape at desks/mt5/data/tape/contract_terms -- the "
                        "point-in-time swap/margin history has never been recorded"))
    elif _day.isoformat() not in _have:
        defects.append(("production-stale",
                        f"mt5-contract-terms: no rows for {_day.isoformat()} (the last completed "
                        f"trading day); newest on disk is {max(_have) if _have else 'nothing'}. "
                        "Point-in-time broker financing is UNBUYABLE once the day passes -- a "
                        "swap or margin reprice inside the gap is permanently gone. The recorder "
                        "runs on the Windows terminal box (`python -m mt5desk.tape --terms-only`, "
                        "seconds of work); install/repair its scheduled task via "
                        "desks/mt5/scripts/install_contract_terms_task.ps1"))

    # research_memory must GROW, not just be non-zero (the null-pipe class)
    try:
        import sqlite3
        n = sqlite3.connect(str(ROOT / "data/sor_research.sqlite")).execute(
            "SELECT COUNT(*) FROM research_memory WHERE created_at >= datetime('now','-7 days') "
            "AND category != 'method'"   # exclude meta/seed rows -- a self-referential seed must
            "").fetchone()[0]             # not green the guard (2026-07-24 audit: 1 seed did)
        if n == 0:
            defects.append(("production-research-memory-flat",
                            "research_memory added 0 rows in 7d -- the conversion loop is not "
                            "recording experiments (writable via scripts/research_memory.py; the "
                            "duty exists, verify missions actually call it)"))
    except Exception:
        pass


def check_gate_optimality(defects) -> None:
    """GATE-OPTIMALITY MONITOR (principal 2026-07-24): the DSR/gauntlet bar must stay OPTIMAL --
    a gate that rejects ~100pct or accepts ~100pct of candidates carries ZERO information and is
    a defect (good alphas lost to an accidentally-too-high bar cost as much as false ones
    admitted). Reads the per-gate rejection histogram; flags any gate at >=98pct reject over a
    non-trivial sample as suspect (mis-applied campaign-level veto, mis-calibration, or a bar
    that has silently become unclearable)."""
    wf = ROOT / "web/autodiscovery_crypto.json"
    if not wf.exists():
        return
    try:
        d = json.loads(wf.read_text("utf-8"))
    except Exception:
        return
    tested = int(d.get("cumulative_tested", 0) or 0)
    hist = d.get("rejection_by_gate", {}) or {}
    if tested < 30 or not hist:
        return
    pegged = [g for g, n in hist.items() if tested and (int(n) / tested) >= 0.98]
    if pegged:
        # Reconciliation rule 3: COMPUTE effective-vs-raw n_trials instead of only asking a human
        # to "audit" it. A raw tally that inflates far past the independent-mechanism count sets
        # the DSR bar unclearable -- the concrete way a pegged gate becomes a survivor-killer.
        from libs.autodiscovery.extraction_parity import effective_trial_count
        eff = effective_trial_count(_trial_mechanisms())
        infl = (f" Effective-vs-raw n_trials: raw {eff.raw} vs {eff.effective} independent "
                f"mechanisms ({eff.inflation:.1f}x inflation) -- "
                + ("deflate DSR by the EFFECTIVE count." if eff.inflation > 1.5
                   else "count is not the cause here.")) if eff.raw else ""
        defects.append((
            "gate-optimality",
            f"gate(s) rejecting >=98pct of {tested} candidates: {', '.join(sorted(pegged))} -- "
            "a ~100pct-constant gate carries zero information. Verify it is genuinely "
            "discriminating, not a campaign-level statistic mis-applied per-candidate or a bar "
            f"risen unclearable; real alphas may be dying at it.{infl}"))
    if int(d.get("cumulative_survivors", 0) or 0) == 0 and tested >= 200:
        defects.append((
            "gate-optimality-zero-survivors",
            f"0 survivors across {tested} tested -- expected on picked-clean price space, but "
            "confirm the funnel can EVER promote: is any single gate the 100pct bottleneck, and "
            "is the walk-forward/per-candidate path able to pass a genuinely-good synthetic?"))


def check_welded_gates(defects) -> None:
    """WELDED-GATE SCAN (RECURSION RULE, 2026-07-30): a per-candidate gate fed a CAMPAIGN CONSTANT.

    Origin, measured this cycle on the real 420-candidate campaign: PBO and White's Reality Check
    take ONLY the returns matrix -- the candidate's own returns are never an input -- so used as
    per-candidate gates they are campaign constants. At PBO 0.6159 / RC p 0.4220 that forced
    420/420 rejections regardless of merit, and 420-tested/0-survivors measured the instrument
    rather than the market. The orchestrator was repaired (pbo 0/420 -> 209/420) and 21 OTHER
    gauntlet scripts were still welded at the time of writing.

    Mechanical so it can never rot back: flags any call site that computes campaign_pbo_rc() and
    feeds the result to validate() as pbo=/rc=. Legitimate non-gate uses are exempt -- the
    deprecated shim itself, the measurement harness that deliberately runs BOTH arms to compare,
    and tests that assert the legacy path still behaves exactly as before.
    """
    exempt = {
        "libs/autodiscovery/validation.py",      # defines the deprecated shim
        "scripts/measure_gate_histogram.py",     # runs both arms on purpose, to compare them
        "scripts/max_audit.py",                  # this scanner DESCRIBES the pattern in prose;
                                                 # scanning itself is the cron-self-match class
    }
    welded: list[str] = []
    for base in ("scripts", "libs"):
        for p in sorted((ROOT / base).rglob("*.py")):
            rel = p.relative_to(ROOT).as_posix()
            if rel in exempt or "/tests/" in f"/{rel}" or rel.startswith("tests/"):
                continue
            try:
                src = p.read_text("utf-8", errors="replace")
            except Exception:
                continue
            # The weld signature: the campaign constant is computed AND handed to validate() as a
            # per-candidate gate input. Either half alone is not the defect.
            if "campaign_pbo_rc(" in src and re.search(r"\bpbo\s*=\s*pbo\b|\brc\s*=\s*rc\b"
                                                       r"|pbo=pbo_once|rc=rc_once", src):
                welded.append(rel)
    if welded:
        shown = ", ".join(welded[:6]) + (f" ... +{len(welded) - 6} more" if len(welded) > 6 else "")
        defects.append((
            "welded-gate-campaign-constant",
            f"{len(welded)} validation path(s) still feed a CAMPAIGN CONSTANT to a per-candidate "
            f"gate: {shown}. PBO/RC do not read the candidate's own returns, so every candidate in "
            "a batch gets one verdict whatever its merit -- measured at 420/420 rejected. Migrate "
            "to campaign_gate_stats() + validate(campaign=..., column=...). PHANTOM-EDGE CRITICAL: "
            "verify the column index maps to the matrix column_stack order per file -- a mis-mapped "
            "index hands one candidate's passing verdict to another, which is worse than the weld."))


def check_data_utilization(defects) -> None:
    """DATA-UTILIZATION LAW, reconciled with the GATE-OPTIMALITY MONITOR (principal 2026-07-24).

    The naive law ("idle data is paralysis; scale extraction") conflicts with gate-optimality:
    mass combinatorial/genetic generation to clear the flag explodes the trial count and deflates
    the DSR bar unclearable (the 420->0 dynamic). Binding reconciliation (extraction_parity.py):
    paralysis is a COVERAGE gap, NOT a volume gap. It clears when every ingested axis carries >=1
    screened, economically-motivated hypothesis (~one mechanism-first trial per axis, ~20 trials),
    never on hypothesis count. So this check measures COVERAGE of the acquired surface, and its
    remedy is mechanism-first coverage of the idle axes -- explicitly NOT volume."""
    from libs.autodiscovery.extraction_parity import axis_coverage

    acquired = _acquired_axes()
    if len(acquired) < 8:
        return  # too small a surface to judge parity
    tags = _converted_axes()
    # tolerant match: an acquired axis is 'covered' if any converted-axis name shares its normalized
    # name (handles collector-store vs axis-name drift, e.g. cny_premium.jsonl <-> cny_premium)
    def _covered(axis: str) -> bool:
        a = axis.lower()
        return any(t == a or t in a or a in t for t in tags)
    covered = [a for a in acquired if _covered(a)]
    rep = axis_coverage(axes=acquired, screened_axes=covered)
    if not rep.cleared:
        shown = ", ".join(rep.idle[:8]) + (" ..." if len(rep.idle) > 8 else "")
        defects.append((
            "data-utilization-paralysis",
            f"{len(rep.idle)}/{rep.n_axes} ingested axes have 0 screened hypothesis "
            f"({rep.coverage_frac:.0%} coverage): {shown} -- DATA PARALYSIS is a COVERAGE gap. "
            "Convert each idle axis MECHANISM-FIRST: one screened, economically-motivated "
            "hypothesis per axis (tag it via research_memory.py --axis). Do NOT clear this by "
            "generating volume -- combinatorial/genetic expansion is EARNED per axis only after "
            "its single-axis screen shows signal (else it is pure DSR deflation)."))


def check_post_gate0_activation(defects) -> None:
    """POST-GATE-0 ACTIVATION INTERLOCK (enforces 'nothing deferred may be skipped').

    The freeze-exit is auto-detected by run_cadence and the POST_GATE0 manifest is flagged for
    activation -- but activation itself was a DIRECTIVE the brain cycle had to obey, with no check
    that it actually happened. This closes that: the moment Gate 0 is complete
    (``data/gate0_complete``) but the cadence state has not set ``post_gate0_activated``, the entire
    deferred queue (docs/POST_GATE0_MANIFEST.md) is sitting un-built -- a defect that escalates to
    the principal at 48h. So the automatic build is VERIFIED to fire, never silently missed."""
    if not (ROOT / "data/gate0_complete").exists():
        return  # pre-Gate-0: the freeze correctly holds, the manifest is not due yet
    state = _j(ROOT / "data/cadence_state.json", {})
    if not (isinstance(state, dict) and state.get("post_gate0_activated")):
        defects.append((
            "post-gate0-activation",
            "Gate 0 is COMPLETE (data/gate0_complete) but post_gate0_activated is NOT set -- the "
            "POST_GATE0 manifest has not activated, so every deferred item (data collectors, "
            "growth ramp, live organs, runtime-gated research completions) is sitting un-built. "
            "Activate docs/POST_GATE0_MANIFEST.md top-to-bottom in EV order THIS cycle; nothing "
            "deferred may be skipped."))


def check_rejection_shadow(defects) -> None:
    """REJECTION-SHADOW standing duty (gate-calibration, MAX_SURVIVORS Part 1.2): the gauntlet
    rejects most candidates -- correct on picked-clean price space -- but a gate that drifted
    over-strict silently LEAKS real edges. run_rejection_shadow.py shadow-tracks a sample of rejects
    forward and writes web/reject_shadow.json. This check surfaces its verdict every cycle: (a) an
    OVER-STRICT gate is a defect (recover the leaked edges); (b) rejects piling up with the audit
    never run / stale is itself a defect (the recovery loop is off). Pure recovery, no new data."""
    rf = ROOT / "web/reject_shadow.json"
    d = _j(rf, None)
    if not isinstance(d, dict):
        return  # runner has never produced output yet -- surfaced by production/organ checks
    audit = d.get("audit", {}) if isinstance(d.get("audit"), dict) else {}
    if audit.get("over_strict"):
        leak = audit.get("leak_frac", 0.0)
        n = audit.get("n_rejects", 0)
        defects.append((
            "rejection-shadow-overstrict",
            f"gate OVER-STRICT: {audit.get('n_would_have_paid', 0)}/{n} shadowed rejects "
            f"({float(leak):.0%}) would have paid out-of-sample -- the gate is leaking survivors. "
            "Re-calibrate (effective-trial count, per-gate bar) and re-examine the leaked ids; "
            "this is pure recovery, no new data."))
    n_elig = int(d.get("n_eligible", 0) or 0)
    n_pending = int(d.get("n_pending_rescore", 0) or 0)
    if n_elig >= 5 and n_pending == n_elig:
        defects.append((
            "rejection-shadow-unscored",
            f"{n_elig} rejects are old enough to judge but NONE are forward-scored -- the reject "
            "forward-evaluator is not feeding data/reject_forward_scores.json, so the gate-leak "
            "audit cannot run. Wire the re-score so wrongly-rejected edges can be recovered."))


def check_source_backlog(defects) -> None:
    """SOURCE-VERIFICATION BACKLOG DUTY: the catalogue (data_axis_watchlist.md) already grows
    faster than it gets verified -- prospector/litminer run daily and add candidate source cards;
    verifying one (real docs read, real endpoint test) is the actual bottleneck, not discovery.
    Flags a STALE backlog: pending cards exist but the watchlist file hasn't been touched (a card
    resolved/added) in a long time -- the verification loop has stopped, silently, while discovery
    keeps running. This is the coverage-not-volume discipline applied to sourcing: the fix is
    working scripts/source_backlog_next.py's queue, never cataloguing more."""
    from libs.research.source_backlog import backlog_from_file

    wf = ROOT / "docs/research/data_axis_watchlist.md"
    if not wf.exists():
        return
    rep = backlog_from_file(wf, limit=1)
    pending = rep.n_verification_pending + rep.n_legitimacy_pending
    if pending == 0:
        return
    stale_days = 14.0
    age_h = (NOW - wf.stat().st_mtime) / 3600.0
    if age_h / 24.0 > stale_days:
        defects.append((
            "source-backlog-stale",
            f"{pending} catalogued source(s) still pending (verification or legitimacy decision) "
            f"and the watchlist has not been touched in {age_h / 24.0:.0f}d -- discovery is "
            "outrunning verification. Run scripts/source_backlog_next.py and clear the next item, "
            "do not catalogue more."))


def check_depth_parity(defects) -> None:
    """DEPTH-BREADTH PARITY LAW enforcement (charter §32): depth must keep pace with breadth,
    never lag it. A forward-clock axis that sits SHALLOW (< DEEP_DAYS of history) while the desk
    keeps widening breadth is a defect -- a shallow axis waits weeks on the forward clock and
    cannot validate, so breadth without depth is unconverted potential (the utilisation-without-
    conversion trap). Flags shallow clock axes as backfill targets (reconstruct to archive depth,
    MAX_SURVIVORS Part 1 #1). An axis already backfilled (has a reconstructed_oos report) is deep;
    an archive-thin axis that has logged its measured depth ceiling is exempt -- depth is never
    faked to clear this flag."""
    # deep_days is evidence-adjustable within hard bounds (self-tuning, not a free knob)
    from libs.self_improvement.adaptive_thresholds import ThresholdBook
    deep_days = ThresholdBook(ROOT / "data/adaptive_thresholds.json").get("depth_deep_days")
    clocks: list[Path] = []
    for pat in ("data/*_premium.jsonl", "data/*_supply.jsonl", "data/*_activity.jsonl"):
        clocks += list(ROOT.glob(pat))
    if len(clocks) < 3:
        return  # too few series to judge depth-vs-breadth
    deep_names: set[str] = set()
    oos = ROOT / "reports/reconstructed_oos"
    if oos.exists():
        for r in oos.glob("*.json"):
            deep_names.add(r.stem.lower())
    # archive-relative exemption: an axis whose archive genuinely maxes out below deep_days logs its
    # measured ceiling here (axis -> max available days); at/above it, the axis is as deep as its
    # archive allows and is NOT flagged (§32: 'as deep as the archive legitimately allows').
    ceilings = _j(ROOT / "data/depth_ceilings.json", {})
    shallow: list[tuple[str, int]] = []
    for c in clocks:
        stem = c.stem.lower()
        if any(stem in d or d in stem for d in deep_names):
            continue  # already backfilled to archive depth
        try:
            with c.open("r", encoding="utf-8") as fh:
                n = sum(1 for _ in fh)
        except Exception:
            continue
        ceiling = ceilings.get(c.stem) if isinstance(ceilings, dict) else None
        if isinstance(ceiling, (int, float)) and n >= int(ceiling):
            continue  # as deep as its own archive allows -- exempt, never faked
        if n < deep_days:
            shallow.append((c.stem, n))
    if shallow:
        shown = ", ".join(f"{s}({n}d)" for s, n in sorted(shallow, key=lambda x: x[1])[:8])
        defects.append((
            "depth-parity",
            f"{len(shallow)} axis(es) shallow (<{int(deep_days)}d) while breadth widens: {shown} "
            "-- DEPTH LAGGING BREADTH (§32). A shallow axis waits weeks on the forward clock and "
            "cannot validate; breadth without depth is unconverted potential. Backfill each to its "
            "archive-depth ceiling and diff-verify (MAX_SURVIVORS Part 1 #1) -- never fake depth; "
            "an archive-thin axis logs its measured ceiling and is exempt."))


def check_ci_scope(defects) -> None:
    """MAP-vs-TERRITORY (audit 3.1): the CI gate must run the whole test tree, not a hardcoded
    subset. GAP #31's stated blocker (duplicate basenames) expired -- pyproject sets
    import-mode=importlib and the tree collects cleanly. A gate that runs a handful of named
    files certifies almost nothing: the ruin path (tests/risk) and the anti-false-positive path
    (tests/validation) are the largest ungated directories, and freshly-shipped tests land in
    ungated dirs by default. Parses the pytest ARGUMENT TOKENS (a comment mentioning the tree
    must not satisfy the check)."""
    ci = ROOT / "scripts/run_ci.py"
    tests_dir = ROOT / "tests"
    if not (ci.exists() and tests_dir.exists()):
        return
    body = ci.read_text("utf-8")
    named = re.findall(r'"(tests/[A-Za-z0-9_./-]*)"', body)
    if not named:
        return
    whole_tree = any(t.rstrip("/") == "tests" for t in named)
    if whole_tree:
        return
    total = sum(1 for _ in tests_dir.rglob("test_*.py"))
    gated_files = sum(1 for t in named if t.endswith(".py"))
    gated_dirs = [t for t in named if not t.endswith(".py")]
    defects.append((
        "ci-scope-partial",
        f"run_ci.py gates a HARDCODED subset -- {gated_files} named test files + "
        f"{len(gated_dirs)} dir(s) {gated_dirs} -- out of ~{total} test files in the tree. The "
        "ruin path (tests/risk) and anti-false-positive path (tests/validation) are ungated, and "
        "new tests land ungated by default. Replace the named paths with the tests/ tree: the "
        "importlib collection blocker (GAP #31) has expired. Freeze-legal, highest-ROI."))


def check_review_risks_tracked(defects) -> None:
    """MAP-vs-TERRITORY (audit 4.1): every risk NAMED in a review doc must inherit the
    GAP_REGISTER escalation loop (weekly re-rank, 7-day staleness). Nothing reconciles the two,
    so the desk's two largest structural risks (counterparty concentration, key-person) sit in a
    doc that is read but never re-ranked."""
    sr = ROOT / "docs/SYSTEM_REVIEW.md"
    gr = ROOT / "docs/GAP_REGISTER.md"
    if not (sr.exists() and gr.exists()):
        return
    reg = gr.read_text("utf-8").lower()
    # the named structural risks the audit flagged as untracked
    for key, label in (("counterparty", "counterparty/single-venue concentration"),
                       ("key-person", "principal key-person risk"),
                       ("per-venue", "per-venue exposure cap")):
        named_in_review = key in sr.read_text("utf-8").lower()
        tracked = key.replace("-", " ") in reg or key in reg
        if named_in_review and not tracked:
            defects.append(("review-risk-untracked",
                            f"'{label}' named in SYSTEM_REVIEW, NO GAP_REGISTER row -- "
                            "it never enters the weekly re-rank/staleness/escalation loop. Add a "
                            "tracked row so a named risk cannot silently escape the discipline."))


#: DELETED 2026-08-01 (R0079): `DESK_BOOK_USD = 50_000.0`. It was the audit's private copy of the
#: desk's book size, and its last reader now calls `capacity_policy.live_book_usd()` like every
#: other scorer. Left as a comment rather than silently removed because the constant is exactly
#: the shape L1.28a warns about -- a plausible literal standing in for a measured quantity, which
#: reads as prudent determinism and behaves as a permanent 2.7x mis-statement of the denominator
#: every capacity band divides by. If a fallback is ever wanted again, it belongs in
#: capacity_policy (which already has one, DEFAULT_BOOK_USD), never re-inlined here.


#: Neither band may fall below this share of the screened funnel. SYMMETRIC on purpose: a funnel
#: that is 100% niche is as defective as one that is 100% fund-shaped, because both mean a whole
#: class of alpha is going unhunted and the objective is the MAXIMUM NUMBER of them.
_BAND_MIN_SHARE = 0.25

#: THE LAB CANDIDATE STORE. Both capacity checks below read it, and until 2026-08-01 (R0079) both
#: named `data/research_memory.db` -- a path nothing in this repo has EVER written. One constant
#: now, because two copies of a path is how one of them gets repointed and the other does not.
_CANDIDATE_DB = ROOT / "data/sor_research.sqlite"


def _rel(p: Path) -> str:
    """Repo-relative display that never raises.

    `Path.relative_to` throws ValueError for anything outside ROOT, which would have made the
    REFUSAL PATH ITSELF the thing that crashed -- the failure handler failing on exactly the
    unusual input it exists to describe. Found by the test written for it, not by reading it.
    """
    try:
        return p.relative_to(ROOT).as_posix()
    except ValueError:
        return str(p)


def _scored_capacities() -> tuple[list[float], list[str], str]:
    """Every scored candidate's capacity, plus the reason the read produced nothing.

    REFUSAL IS AN OUTCOME WITH ITS OWN VOCABULARY (L1.41 condition 1). Both callers previously
    wrapped this read in a bare `contextlib.suppress(Exception)` and then returned early on
    `len(caps) < 5`, so THREE different situations were indistinguishable and all three read as a
    passing check: (a) the desk genuinely has few scored candidates, (b) the db is absent because
    this is not the research box, and (c) the read RAISED -- which it did, on every run since the
    checks were written, because `CandidateStore(Path)` is a type error (`CandidateStore` takes a
    `Database`, and a `PosixPath` has no `.execute`). Two §42 audits therefore reported OK for
    their entire existence without ever having read a single candidate, and the exception that
    would have said so was swallowed one line above.

    Returns (capacities, subtype-names, error) -- `error` empty when the read succeeded.
    """
    if not _CANDIDATE_DB.exists():
        return [], [], f"{_rel(_CANDIDATE_DB)} absent (not the research box)"
    try:
        from libs.autodiscovery.memory import CandidateStore
        from libs.store.connection import Database
        store = CandidateStore(Database(_CANDIDATE_DB, read_only=True))
        caps, names = [], []
        for c in store.all():
            cap = float(getattr(c.metrics, "capacity_usd", 0.0) or 0.0)
            if cap > 0:
                caps.append(cap)
                names.append(str(getattr(getattr(c, "hypothesis", None), "subtype", "") or ""))
    except Exception as exc:                                    # reported, never hidden
        return [], [], f"{type(exc).__name__}: {exc}"
    return caps, names, ""


def _capacity_unreadable(defects, where: str, err: str) -> None:
    """A capacity audit that cannot READ its input has not passed -- it has not run."""
    defects.append((
        "capacity-store-unreadable",
        f"§42/L1.28a: {where} could not read {_rel(_CANDIDATE_DB)} -- {err}. This "
        "check is NOT green; it is UNMEASURED, which is the state that looked identical to green "
        "for as long as the reader was broken. Repair the store or the reader before trusting any "
        "capacity-band verdict."))


def check_capacity_hunt(defects) -> None:
    """§42: BOTH capacity bands must be hunted -- the funnel may not collapse onto either one.

    PROSPECTOR_SPEC names capacity-bound edges -- the ones a fund abandoned for being too small --
    as "this desk's ONE structural advantage". Until 2026-07-26 the survival gate contradicted
    that outright with a flat $100k capacity floor, so the niche was unreachable by construction.
    Removing the block is necessary and NOT sufficient: a desk merely permitted to hunt small will
    still default to fund-shaped ideas, because that is what the literature is written about.

    SYMMETRIC, BY PRINCIPAL DIRECTION (2026-07-26). The first version of this check enforced a
    NICHE FLOOR, which is the same bias pointed the other way: it would have sat silent while the
    desk hunted nothing but tiny edges, and a funnel with no large edges in it has no successor
    inventory for the day the book outgrows the small ones. The objective is the maximum number of
    simultaneous uncorrelated alphas, so BOTH bands are measured and EITHER one collapsing is the
    defect. Small edges expire first -- that is arithmetic, and it is handled by
    `check_capacity_runway`, not by preferring them here.
    """
    caps, names, err = _scored_capacities()
    if err:
        _capacity_unreadable(defects, "check_capacity_hunt", err)
        return
    if len(caps) < 5:
        return  # too few scored candidates to judge where the hunt is pointed
    from libs.research.capacity_policy import (
        capacity_band,
        declared_allocation,
        live_book_usd,
        live_sleeves,
    )
    # Whole-book figure -> must be divided by the sleeve count: no single edge is filled with the
    # entire desk. Judging candidates against the whole book would inflate the requirement 8x and
    # mark perfectly tradeable small edges "unfillable" -- the flat-floor bug wearing a new hat.
    #
    # A DECLARED sleeve is banded at its declaration, because that is how every scorer judges it.
    # Banding at equal weight here would have the audit call an edge UNFILLABLE while the scorer
    # calls the same edge NICHE -- two answers to one question, and the audit is meant to be the
    # thing that catches that class of disagreement, not a source of it.
    #
    # THE LIVE BOOK, NOT A LITERAL (2026-08-01, R0079). This banded against the module constant
    # DESK_BOOK_USD = $50,000 while its sibling `check_capacity_runway` banded the SAME candidates
    # against `live_book_usd()` = $18,811 -- two answers to the one number every capacity band is a
    # ratio to, in adjacent functions, which is the precise defect L1.28a's first run found in the
    # opposite direction. It is also self-inflicted in the expensive direction: a book pinned 2.7x
    # too large inflates `capacity_required` and marks small edges UNFILLABLE, which is §42's named
    # structural advantage being audited away by a constant. Doctrine is explicit -- "a ratio
    # measured against a hardcoded number is the flat-floor bug one step removed" -- and
    # live_book_usd() already falls back to the constant when the NAV chain is missing or stale,
    # so this is strictly better-founded than the literal it replaces, never looser.
    book, sleeves = live_book_usd(), live_sleeves()
    bands = [capacity_band(c, book, sleeves, allocation_usd=declared_allocation(name))
             for c, name in zip(caps, names, strict=True)]
    in_niche = sum(1 for b in bands if b == "NICHE")
    larger = sum(1 for b in bands if b in ("SCALABLE", "FUND-SCALE"))
    unfillable = sum(1 for b in bands if b == "UNFILLABLE")
    fillable = in_niche + larger
    if unfillable:
        defects.append((
            "capacity-hunt-unfillable",
            f"§42: {unfillable}/{len(caps)} scored candidates cannot absorb the required headroom "
            f"on a ${book:,.0f} book at all -- the desk would BE the edge. Small is the "
            "advantage; too small to fill is not. These should be screened out before scoring, "
            "not carried as candidates."))
    if fillable < 5:
        return  # too few FILLABLE candidates to judge how the hunt is split between bands
    if in_niche / fillable < _BAND_MIN_SHARE:
        defects.append((
            "capacity-hunt-fund-shaped",
            f"§42: only {in_niche}/{fillable} fillable candidates ({in_niche / fillable:.0%}) sit "
            f"in the NICHE band -- below the {_BAND_MIN_SHARE:.0%} both bands must hold. The "
            "prospector has drifted onto fund-scale ground, where a book this size has NO "
            "advantage and could not fill the trade if it found one. Point it back at the niche "
            "its own spec names: listing-event dislocations, thin-pair cross-venue funding, "
            "low-OI tails -- edges that pay BECAUSE they are too small to interest anyone with "
            "money. These are ADDITIONAL sleeves, not replacements for the large ones."))
    if larger / fillable < _BAND_MIN_SHARE:
        defects.append((
            "capacity-hunt-niche-only",
            f"§42: only {larger}/{fillable} fillable candidates ({larger / fillable:.0%}) can "
            f"absorb size -- below the {_BAND_MIN_SHARE:.0%} both bands must hold. Hunting ONLY "
            "small is the same bias pointed the other way, and it costs twice: alphas that would "
            "have run alongside the small ones are never found, and there is no successor "
            "inventory for the day the book outgrows the ones being run. Every small edge has a "
            "known expiry (`capacity-runway`); the replacement must be in the pipeline BEFORE it "
            "arrives, which means hunting large concurrently, not afterwards."))


#: Knobs on the capacity policy that exist ONLY to be passed by a caller. Each must have at least
#: one PRODUCTION caller -- a test does not count, because a test proves the mechanism works and
#: says nothing about whether anything runs it.
_CAPACITY_KNOBS = ("allocation_usd", "sleeve", "edge_capacity_usd")


def check_capacity_knobs_are_wired(defects) -> None:
    """§42: every capacity knob must have a PRODUCTION caller, not just a passing test.

    This exists because the same mistake was made three times in one day: the crowding floor, the
    sizer governor and `allocation_usd` were each built, unit-tested green, and never passed by any
    real caller. A parameter nothing passes is an orphaned artifact (§36) with camouflage -- the
    tests genuinely prove the mechanism, so the gap is invisible in exactly the way review is worst
    at catching. Reviewing harder does not fix a class of error; a check does.

    The rule is deliberately blunt: for each knob, at least one call site under libs/ or scripts/
    that is NOT the definition and NOT a test must pass it by keyword.
    """
    import re
    prod: list[tuple[str, str]] = []
    for base in ("libs", "scripts"):
        for path in sorted((ROOT / base).rglob("*.py")):
            rel = str(path.relative_to(ROOT))
            if "test" in rel:
                continue
            with contextlib.suppress(OSError):
                prod.append((rel, path.read_text("utf-8", errors="ignore")))
    for knob in _CAPACITY_KNOBS:
        # a CALL passes `knob=`; a DEFINITION writes `knob: type` or `knob=default` in a signature
        callers = [rel for rel, text in prod
                   if re.search(rf"\b{knob}\s*=\s*(?!None\s*[,)])[\w.\[\]()\"']", text)
                   and "capacity_policy.py" not in rel and "/sizing.py" not in rel]
        if not callers:
            defects.append((
                "capacity-knob-orphaned",
                f"§42: `{knob}` is a capacity knob that NO production code passes -- it is wired "
                "to nothing and clamps nothing, while its unit tests pass and make it look "
                "finished. That is the orphaned-artifact failure (§36) in its most deceptive "
                "form. Either thread it from a real caller or delete it; a knob that only tests "
                "use is a false assurance, which is worse than no knob at all."))


def check_capacity_governor_reachable(defects) -> None:
    """§42: the capacity clamp must be THREADED to the gate, not merely defined in the sizer.

    A governor no caller passes is an orphaned artifact (§36) that tests green forever while
    clamping nothing -- and it is the most dangerous kind, because the tests prove the mechanism
    works and say nothing about whether it runs. This checks the join: `OrderIntent` must carry
    `edge_capacity_usd`, and `risk_gate` must hand it to `calculate_position_size`. Structural, so
    it survives the numbers being re-tuned and fails the moment the wire is cut.
    """
    gate = ROOT / "libs/risk/gate.py"
    sizing = ROOT / "libs/risk/sizing.py"
    if not gate.exists() or not sizing.exists():
        return
    g, s = gate.read_text("utf-8", errors="ignore"), sizing.read_text("utf-8", errors="ignore")
    if "edge_capacity_usd" not in s:
        defects.append((
            "capacity-governor-missing",
            "§42: libs/risk/sizing.py has no edge_capacity_usd governor. Nothing stops a sleeve "
            "being sized past what its edge can hold, which does not lose money slowly -- it "
            "DESTROYS the edge, because the desk's own flow becomes the counterparty."))
        return
    if "edge_capacity_usd" not in g:
        defects.append((
            "capacity-governor-orphaned",
            "§42: the sizer HAS a capacity governor and libs/risk/gate.py never passes it, so it "
            "clamps nothing on any real order while its tests stay green. That is exactly the "
            "orphaned-artifact failure §36 exists to catch, in the one place it can cost capital: "
            "thread intent.edge_capacity_usd into calculate_position_size."))


def _funded_by_sleeve() -> dict[str, float]:
    """Live notional per sleeve, from whatever the desk actually publishes. Empty pre-Gate-0."""
    out: dict[str, float] = {}
    with contextlib.suppress(Exception):
        raw = json.loads((ROOT / "web/portfolio.json").read_text("utf-8"))
        for name, row in (raw.get("sleeves") or {}).items():
            with contextlib.suppress(Exception):
                out[str(name)] = float(row["notional_usd"])
    return out


def check_capacity_allocation_honesty(defects) -> None:
    """§42: a DECLARED allocation is a commitment, and this is what makes it one.

    Allowing a candidate to be judged against the equity it will actually be funded with is
    strictly correct and unblocks the small edges the desk exists to trade. It is also the easiest
    bypass in the whole capacity policy: declare $1, pass every gate forever. So the declaration is
    checked from both ends -- it must be possible under its own edge's capacity, and it must match
    what the sleeve is really funded with.

    "No live funding data" is reported as UNVERIFIED, never as a pass. Pre-Gate-0 that is the
    normal state, and the distinction is the entire point: a check that prints the same thing when
    it verified something and when it verified nothing is not a check.
    """
    from libs.research.sleeve_allocations import inconsistent, load, overfunded, unverified
    allocs = load(ROOT / "data/sleeve_allocations.json")
    if not allocs:
        return   # nothing declared -> equal weight applies, and equal weight is STRICTER
    funded = _funded_by_sleeve()
    for a in inconsistent(allocs):
        defects.append((
            "capacity-declaration-impossible",
            f"§42: sleeve '{a.sleeve}' declares ${a.declared_usd:,.0f} against a "
            f"${a.capacity_usd:,.0f} edge, whose ceiling is ${a.ceiling_usd:,.0f}. The declaration "
            "does not qualify under its own numbers -- it is asking the capacity gate for a pass "
            "it cannot have. Fix the declaration or re-measure the capacity."))
    for a, got in overfunded(allocs, funded):
        defects.append((
            "capacity-declaration-breached",
            f"§42: sleeve '{a.sleeve}' declared ${a.declared_usd:,.0f} -- the number its capacity "
            f"gate was PASSED on -- and is funded with ${got:,.0f}. The gate was cleared on a "
            "commitment that is not being kept, so the edge is being traded past the size it was "
            "ever approved for. Cut the sleeve to its declaration or re-run the gate at the real "
            "size."))
    n_unver = len(unverified(allocs, funded))
    if n_unver and n_unver == len(allocs):
        defects.append((
            "capacity-declaration-unverified",
            f"§42: all {n_unver} declared allocation(s) have NO live funding figure to reconcile "
            "against, so every allocation-aware capacity pass on this desk is currently taken on "
            "trust. Expected pre-Gate-0 and not a fault -- but it must not read as verified, "
            "because the declaration is only a commitment while something checks it."))


def check_capacity_runway(defects) -> None:
    """§42(3): the desk must SEE itself outgrowing an edge, not discover it mid-trade.

    The sequence §42 commits to is edge -> size -> next edge, and the decay of a small edge as the
    book grows into it is DEFINITIONAL rather than a risk to be mitigated. That only compounds if
    the expiry is visible in advance. Every edge has a book size at which it stops being fillable;
    this reports how much growth the current shortlist survives, so the replacement pipeline can
    start BEFORE the edge dies rather than after. Two failures are worth a defect:

      - already outgrown: an edge still being scored that today's book can no longer fill;
      - no runway: nothing on the shortlist survives a doubling, so the desk is one good quarter
        from having no deployable inventory and no notice that it is coming.
    """
    from libs.research.capacity_policy import growth_runway, live_book_usd, live_sleeves
    caps, _names, err = _scored_capacities()
    if err:
        _capacity_unreadable(defects, "check_capacity_runway", err)
        return
    if len(caps) < 5:
        return
    book, sleeves = live_book_usd(), live_sleeves()
    runways = sorted(growth_runway(c, book, sleeves) for c in caps)
    outgrown = [r for r in runways if r < 1.0]
    if outgrown:
        defects.append((
            "capacity-already-outgrown",
            f"§42(3): {len(outgrown)}/{len(caps)} scored candidates can no longer be filled by "
            f"today's ${book:,.0f} book across {sleeves} sleeves. They are inventory the desk has "
            "already grown past -- retire them and bank the mechanism, do not keep ranking them."))
    survives_2x = sum(1 for r in runways if r >= 2.0)
    if survives_2x == 0:
        defects.append((
            "capacity-no-runway",
            f"§42(3): NOTHING on the shortlist survives a doubling of the ${book:,.0f} book "
            f"(best runway {runways[-1]:.1f}x). Outgrowing an edge is the plan, but the NEXT edge "
            "has to already be in the pipeline when it happens. Hunt one tier larger NOW, while "
            "the current sleeves still pay -- both bands at once, which is the point."))


#: Every scorer that has ever had to answer "is this capacity enough?". Each one used to carry its
#: own dollar constant; they disagreed, and fixing the survival gate alone on 2026-07-26 left four
#: of them still penalising the niche. They are enumerated so a NEW one cannot quietly appear.
_CAPACITY_CONSUMERS = (
    "libs/risk/sizing.py",
    "libs/discovery/objective.py",
    "libs/research/alpha_economics.py",
    "libs/alpha_factory/capacity_intelligence.py",
    "libs/autodiscovery/validation.py",
)
#: Dollar magnitudes that mean "a fund's book" when they appear next to capacity. Finding one of
#: these in a consumer is the fingerprint of a re-inlined threshold.
_FUND_SHAPED_CONSTANTS = ("1e5", "1e6", "1e7", "100_000", "1_000_000", "100000.0", "1000000.0")


def check_deploy_path(defects) -> None:
    """INBOUND DEPLOY must be alive, and its OWED states must not rest (EXECUTION_QUEUE.md RANK 7).

    A deploy path is only worth having if its silence is detectable. Before deploy/pull_deploy.sh
    existed, git_snapshot pushed VPS->GitHub and nothing came back, so master could be arbitrarily
    far ahead of the code the desk was actually running and nothing said so. Restoring that blind
    spot by letting the puller die quietly would be the same gap wearing a newer name.

    THREE FAILURES, and the last two are the ones a naive freshness check would miss:
      * NEVER RAN / STALE -- the box stopped pulling; master is deploying nothing again.
      * CI-RED -- the puller correctly reverted a red commit, which means the box is deliberately
        parked on older code. Right call, but it is a HOLD, not a steady state: master and the box
        have diverged in what they claim to be running until someone fixes the red.
      * ACTION OWED -- the pull landed but a supervised process could not be restarted (this box
        denies systemctl to the quant user) or the ruin rail was invalidated. New code is on disk
        while the OLD code still owns the book: precisely the 2026-07-26 incident, where a
        committed funding fix sat inert in an orphaned executor for 8h.
    """
    sj = ROOT / "data/pull_deploy_state.json"
    if not sj.exists():
        # Absent is only a defect on the box that actually INSTALLED the puller. Gating on the
        # manifest instead would fire on every dev checkout and sandbox, and a fence that cries on
        # every clone is a fence people learn to ignore -- so the discriminator is a LIVE crontab
        # that references it, the same sandbox-vs-box signal check_scheduler_manifest.py uses.
        try:
            live = subprocess.run(["crontab", "-l"], capture_output=True, text=True,
                                  timeout=10, check=False).stdout
        except (OSError, subprocess.SubprocessError):
            return
        if "pull_deploy.sh" in live:
            defects.append(("deploy-never-ran",
                            "the live crontab installs deploy/pull_deploy.sh but "
                            "data/pull_deploy_state.json is MISSING -- the inbound deploy path has "
                            "never produced evidence, so 'merge is deploy' is a claim, not a "
                            "mechanism. Check the cron log for a startup failure"))
        return
    try:
        st = json.loads(sj.read_text("utf-8"))
    except (OSError, ValueError):
        defects.append(("deploy-state-unreadable",
                        "data/pull_deploy_state.json is unparseable -- the deploy path's only "
                        "evidence artifact is corrupt; treat the running code as unverified"))
        return
    age_h = (NOW - sj.stat().st_mtime) / 3600.0
    status = str(st.get("status", "?"))
    if age_h > 26:
        defects.append(("deploy-stale",
                        f"pull_deploy last ran {age_h:.0f}h ago (>26h, status {status!r}) -- the "
                        "box may be running code arbitrarily far behind master, which is the exact "
                        "blind spot the inbound path was built to close"))
    if status == "ci-red":
        defects.append(("deploy-blocked-ci-red",
                        f"pull_deploy did NOT merge {st.get('to', '?')} because the CI gate was "
                        f"red; the box is still on {st.get('from', '?')}. Correct refusal, but it "
                        "is a HOLD: master and the desk disagree about what is running until the "
                        "red is fixed. Fix the gate, do not bypass the puller"))
    # Since R0246 the gate runs in a detached worktree and the live tree is merged only on green,
    # so there is no revert and no window in which the box sits on red code. The wording above was
    # updated with it: an alarm that describes an action the script can no longer take sends the
    # reader looking for a rollback that never happened.
    if status == "refused-merge-tree-moved":
        defects.append(("deploy-blocked-tree-moved",
                        f"pull_deploy gated {st.get('to', '?')} GREEN but refused to merge it: the "
                        "tree moved mid-gate, so a session is committing here. Nothing was lost "
                        "and the next tick re-gates -- but if this repeats the box is being held "
                        "behind master by continuous local commits, which no tick will resolve"))
    if status == "deployed-action-owed":
        defects.append(("deploy-action-owed",
                        f"pull_deploy landed {st.get('to', '?')} but a supervised process was NOT "
                        f"restarted ({st.get('note', '')}). New code on disk, OLD code owning the "
                        "book -- the 2026-07-26 orphaned-executor class. Run the owed systemctl "
                        "command printed in data/cro_ai_logs/pull_deploy.log"))
    if status in ("refused-dirty", "refused-diverged"):
        defects.append(("deploy-refused",
                        f"pull_deploy is REFUSING to deploy (status {status!r}): the box has "
                        "modified tracked files or local commits. Every merge to master is a no-op "
                        "until an operator reconciles the box"))


def check_capacity_single_source(defects) -> None:
    """§42: ONE capacity policy, imported -- never a constant re-inlined next to a scorer.

    The original defect was not that the number was wrong; it was that the number existed in five
    places. Fixing the survival gate did nothing to the other four, and the exclusion simply moved
    to where nobody was looking. So the invariant is structural, not numeric: every scorer that
    judges capacity must IMPORT `libs.research.capacity_policy`, and none may carry a fund-shaped
    dollar constant on a line that mentions capacity. Checking the shape of the dependency rather
    than the value of the threshold is what makes this survive somebody re-tuning the threshold.
    """
    for rel in _CAPACITY_CONSUMERS:
        path = ROOT / rel
        if not path.exists():
            defects.append(("capacity-consumer-missing",
                            f"§42: {rel} is enumerated as a capacity consumer but does not exist. "
                            "Either it moved (update the list) or the parity guard is now blind "
                            "to wherever its logic went."))
            continue
        text = path.read_text("utf-8", errors="ignore")
        if "capacity_policy" not in text:
            defects.append(("capacity-policy-not-imported",
                            f"§42: {rel} judges capacity but does not import capacity_policy -- "
                            "it is carrying its own definition again. That is exactly how the "
                            "flat $100k floor survived being 'fixed': five copies, one patched."))
        for i, line in enumerate(text.splitlines(), start=1):
            low = line.lstrip()
            if low.startswith("#") or "capacity" not in low.lower():
                continue
            hit = next((c for c in _FUND_SHAPED_CONSTANTS if c in line), None)
            if hit is not None:
                defects.append(("capacity-constant-reinlined",
                                f"§42: {rel}:{i} puts a fund-shaped constant ({hit}) on a capacity "
                                "line. Capacity is a RATIO to deployed equity; a six/seven-figure "
                                "literal here is the excluded-by-default bug growing back."))

#: Every doc where a finding can be WRITTEN. The register is where findings are WORKED; anything
#: written here and absent there is invisible to the daily cycle.
_FINDING_DOCS = (
    "docs/SYSTEM_REVIEW.md",
    "docs/BLIND_SPOT_AUDIT.md",
    "docs/research/micro_audit_inbox.md",
    "docs/research/improvement_inbox.md",
    "docs/research/panel_rulings.md",
    # 2026-07-28: the 101-item triage. Its own header is a disposition mandate -- "don't skip any
    # -- build now, queue, or reject completely" -- which is precisely what §35 drives. Adding
    # these RAISES the open-finding count rather than lowering it; that is the honest direction.
    # Leaving them out kept ~101 items invisible to the only organ that works a backlog, and
    # coverage that rises because findings stopped being counted is the denominator trick §35
    # exists to forbid.
    "docs/research/SUBSYSTEM_TRIAGE.md",
    "docs/research/TRIAGE_ADDENDUM.md",
    "docs/GATE0_QUEUE.md",
    # 2026-08-05: the preserved dated copy of the FIRST premortem run. Classified IN SCOPE after
    # checking rather than by analogy: the sibling artifact panel_inbox.md is excluded because the
    # panel's own triage loop governs it, but that loop has NOT run for this mission -- grep
    # 'premortem' over data/panel_verdicts.jsonl returns 0 and its newest rows are 07-31/tier1.
    # Excluding it on the panel-loop precedent while the panel loop holds none of its findings is
    # exactly the denominator trick 35 forbids, so it is scanned until those verdicts exist.
    "docs/research/PREMORTEM_20260805.md",
    # 2026-08-11 (findings-scope-unmonitored): the halted failed-breakout study's write-up
    # carries 5 numbered findings ("MECHANISM UNMEASURABLE -- study halted before the pattern
    # search"). A HALTED study is not a closed one: its findings name work still owed (the
    # measurability defect itself), so they owe register rows -- the INTRADAY_ROTATION exclusion
    # precedent (a COMPLETED study is a record) explicitly does not apply to a halt.
    "docs/research/FAILED_BREAKOUT_PREREGISTRATION.md",
)
#: Finding-bearing docs deliberately out of scope, with the reason -- so the scope check can tell
#: "consciously excluded" from "quietly unmonitored".
_FINDING_DOCS_EXCLUDED = {
    "docs/RESEARCH.md":
        "OPERATIVE GOVERNING DOCUMENT (the 2026-08-25 consolidation's research constitution, "
        "CLAUDE.md table row 2; supersedes ELITE_QUANT_INTELLIGENCE_MANDATE, which is excluded "
        "on the same class). Its numbered matches are the canonical ten-gate table (§6a rows "
        "1-10) and the discovery->live pipeline steps -- LAW that stays open by design, never "
        "findings owing dispositions. It binds through ops/brain_env.sh injection into every "
        "organ prompt, not through the findings register; rowing its clauses would inflate the "
        "open-finding count with items that can never close.",
    "docs/research/MOAT_NODE_SPEC.md":
        "BUILD SPECIFICATION for the Contabo moat recorder node: its numbered items are spec "
        "requirements (symbols-recorded/uptime/gap-count floors, heartbeat contract) whose "
        "delivery is driven by GAP register row 127 (moat coverage ratchet), not by findings "
        "rows -- one obligation, one law, the COINM_CONVEXITY precedent. The spec stays open "
        "until the node ships its fence; double-rowing each requirement would charge the same "
        "work to two registers.",
    "docs/research/recent_changes.md":
        "GENERATED 24h change digest (scripts/, regenerated on a rolling window): every line is "
        "a QUOTED commit patch, so any numbered finding matched inside it is a copy of text that "
        "lives in -- and is scanned at -- its source doc, or a ledger row already driving the "
        "work. Scanning the digest would double-count each finding for exactly 24h and then drop "
        "it as the window rolls, an unstable denominator §35 forbids. Already governed for §36 "
        "as a terminal artifact ('append-only change record'); this entry extends the same "
        "verdict to the findings scan, which reads a different registry.",
    "docs/UNIVERSAL_PROMOTION_PROTOCOL.md":
        "BINDING PROMOTION PROTOCOL (CLAUDE.md read-before-acting table: 'binding on every "
        "brain', one door to capital). Its numbered sections are the NINE-SHIPPED-DEFECTS "
        "doctrine exemplars (Part I) and the ladder/shadow/monitoring clauses (Parts II-V) -- "
        "teaching material and law that stay open by design, the ELITE_QUANT_INTELLIGENCE_"
        "MANDATE precedent. Rowing them would inflate the open-finding count with items that "
        "can never close; the protocol binds through the promotion path itself (qquant_gates, "
        "shadow, auto_promotion), not through the findings register. Also satisfies §36(2) "
        "artifact governance, which fired on it as claimed-by-no-law.",
    "docs/research/COINM_CONVEXITY_PREREGISTRATION.md":
        "PRE-REGISTRATION record (2026-08-13) governed by its own ledger row R0462: its numbered "
        "blocks are kill criteria and promotion triggers written down BEFORE any screen, so "
        "rowing them as findings would double-charge one obligation to two laws (the "
        "THREE_MECHANISM_PREREGISTRATION precedent). The work it names is driven by R0462 and "
        "watchlist card 31; the doc becomes TERMINAL when its trigger resolves, per its header",
    "docs/research/ELITE_QUANT_INTELLIGENCE_MANDATE.md":
        "PERMANENT STANDING POLICY (principal directive 2026-08-13, all three builder seats): "
        "its numbered items are mandate clauses and standing hunting grounds whose whole design "
        "is to stay open -- the DATA_UNIVERSE_TAXONOMY precedent. Rowing them would inflate the "
        "open-finding count with policy that can never close; the mandate binds through the "
        "doctrine and CLAUDE.md read-before-acting table, not through the findings register",
    "docs/MANDATE_NET_COMPOUNDING.md":
        "BINDING HUMAN MANDATE (principal, 2026-08-16, every desk and brain): sizing law for "
        "high-drawdown books -- policy clauses, not findings owing dispositions. Same class as "
        "ELITE_QUANT_INTELLIGENCE_MANDATE; also satisfies §36(2) artifact governance, which was "
        "firing on it as claimed-by-no-law",
    "docs/research/SURVIVOR_YIELD_AUDIT.md": (
        "terminal repo audit -- its numbered rows classify EXISTING modules against a mandate, "
        "so they are evidence for work NOT done rather than defects owing a register row. The "
        "residuals it does name (right-tail auditor, capital-occupancy) are carried as GAP rows"),
    "docs/research/DATA_UNIVERSE_TAXONOMY.md":
        "the STANDING HUNTING MAP (principal 2026-08-04), not a findings backlog: its 30 "
        "numbered blocks are domain rows of the universe every breadth organ diffs against "
        "daily, each a permanent hunting ground that can never 'close'. Rowing them would "
        "inflate the open-finding count with items whose whole design is to stay open. The "
        "file is governed twice already: _PRODUCER_CADENCE holds it to its own weekly re-sweep "
        "promise, and the daily coverage DIFF runs inside breadth_expander/run_cro",
    "docs/research/INTRADAY_ROTATION_RESULT.md":
        "dated MEASURED-RESULT record (2026-08-04, pre-registered NO-GO at 5m; DSR-priced over "
        "540 configs). Its numbered blocks are the study's conclusions, converted at write "
        "time: the verdict is cited by the ledger's resolution-diagnostic row (commit bc28e2a) "
        "and the 15m/1h ladder re-test completed same day. A closed study's write-up is the "
        "record, not a backlog -- same precedent as CYCLE_20260729_CLOSURE.md",
    "docs/CYCLE_20260729_CLOSURE.md": "dated closure snapshot -- every numbered item was rowed "
                                      "via track_findings/recommendations at write time; the "
                                      "register drives them, the snapshot is the record",
    "docs/WEEKLY_MAX_CYCLE.md": "process runbook -- its numbered steps are procedure, not "
                                "findings owing dispositions",
    "docs/research/TRIAGE_20260729_PRINCIPAL_BATCH.md": "dated triage record -- verdicts were "
                                                        "rowed into the ledger 07-29; "
                                                        "historical artifact",
    "docs/research/cn_oss_extraction_20260731.md": "dig extraction card -- its 5 finds are "
                                                   "rowed as R0100 (ingest+screen) by the "
                                                   "authoring session; §33 governs the cards",
    "docs/research/search_operator_library.md": "versioned REFERENCE library, not a findings "
                                                "backlog: its 'numbered items' are OP-nnn search "
                                                "OPERATORS (charter 15/16), each a reusable "
                                                "technique with its own status lifecycle "
                                                "(active/watch/archived) and its own retirement "
                                                "rule -- 'retired entries move to the ARCHIVE "
                                                "section, never deleted'. An operator is a tool a "
                                                "digger DRAWS from, not a defect owing a "
                                                "disposition, and rowing 25 of them would inflate "
                                                "the open-finding count with items that can never "
                                                "close. The doc is still governed: 36 covers it "
                                                "via _PRODUCER_CADENCE, so a library that stops "
                                                "being contributed to fires",
    "docs/research/blind_rediscovery_log.md": "monthly blind-rediscovery run log -- each run's "
                                              "cards are rowed into the RECOMMENDATION ledger by "
                                              "the authoring session (run 1 2026-07-31 -> "
                                              "R0202-R0210), the organ that drives conversion and "
                                              "enforces dispositions. Same precedent as "
                                              "cn_oss_extraction_20260731.md. Scope-excluded here "
                                              "so the SAME cards are not double-counted against "
                                              "two backlogs; §36 still governs the file via "
                                              "_PRODUCER_CADENCE, so a run that stops happening "
                                              "fires. If a future run's cards are ever NOT "
                                              "ledgered, move this into _FINDING_DOCS",
    "docs/research/panel_inbox.md": "raw panel transcript -- rulings are the distilled output",
    "docs/research/deep_review_inbox.md": "RAW ADVERSARIAL-MODEL TRANSCRIPT, verbatim and "
                                          "UNVERIFIED AT WRITE TIME -- deep_review.py appends "
                                          "each seat's unedited response, hallucinated items "
                                          "included (one block reads '35% further drawdown "
                                          "required' against nothing). Its numbered items are "
                                          "model CLAIMS awaiting triage, not desk findings, and "
                                          "the file's own auto-written header states the "
                                          "protocol: verify each claim against the code, then "
                                          "record accepted ones via scripts/track_findings.py. "
                                          "That loop demonstrably ran for this content -- F0024 "
                                          "(staging.py bool(str) consent gate) and F0025 "
                                          "(dead-man blind-feed guard) were raised minutes after "
                                          "the reviews and accepted, F0025 -> R0401 -- and "
                                          "track_findings carries its own 14-day "
                                          "accepted-but-unfixed clock, so dispositions ARE "
                                          "enforced, one layer down. Rowing the raw transcript "
                                          "too would charge the same claim to two backlogs and "
                                          "seed the register with unverified model output: same "
                                          "precedent as panel_inbox.md and "
                                          "blind_rediscovery_log.md. MEASURED at exclusion time: "
                                          "in-scope would read 213 findings / coverage 0.991 "
                                          "against a 1.000 ratchet floor, i.e. trading three "
                                          "defects for two. If a future run's accepted claims "
                                          "are ever NOT routed to track_findings, move this into "
                                          "_FINDING_DOCS. ALSO THE §36 CLAIM (merged 2026-08-05, "
                                          "ruff F601): a second entry for this same key was "
                                          "added lower in this dict, and Python kept only the "
                                          "later one -- silently deleting everything above. It "
                                          "said: CADENCED PRODUCER, deep_review.py appends one "
                                          "panel pass per risk-path module (LIVE_CONNECTOR_SPEC "
                                          "s7 bar); unclaimed it read as an orphan, which is the "
                                          "inventory-accumulates failure §36 exists to catch, so "
                                          "the claim names the conversion path rather than "
                                          "exempting the file from having one. Both reasons are "
                                          "true and neither replaces the other -- one answers "
                                          "'why is this out of FINDINGS scope', the other 'which "
                                          "law claims this artifact'",
    "docs/CONSTITUTION.md": "LAW TEXT, and the 10 matches are false positives: _PROSE_RE keys on "
                            "'N. **Bold**', which is how the constitution numbers the sub-clauses "
                            "of L1.49 (3), L1.53 (1) and L1.54 (6). A law clause binds organs "
                            "permanently and can never CLOSE, so rowing one would inflate the "
                            "open-finding denominator with items designed to stay open forever. "
                            "Same argument already accepted for MEASUREMENT_DOCTRINE.md and "
                            "TWO_STAGE_DISCOVERY_LAW.md. Excluding here touches max_audit only -- "
                            "the L1.x hash seal is not engaged",
    "docs/research/feed_inbox.md": "literature feed, not desk findings",
    "docs/research/data_axis_watchlist.md": "source cards -- governed by §33 dispositions",
    "docs/research/crypto_source_seeds.md": "living source-seed map -- governed by L1.52 miners",
    "docs/research/discovery_hypotheses.md": "hypotheses -- governed by §33 / the trial ledger",
    "docs/research/literature_coverage.md": "coverage log -- governed by §33",
    "docs/research/prospector_coverage.md": "coverage log -- governed by §33, same as its "
                                            "literature_coverage sibling",
    "docs/research/MEASUREMENT_DOCTRINE.md": "standing doctrine -- its numbered items are "
                                             "principles that bind organs, not findings owing "
                                             "a disposition",
    "docs/POST_GATE0_MANIFEST.md": "deferred builds -- driven by check_post_gate0_activation",
    "docs/research/DAILY_INTEGRITY_WATCH.md": "standing checklist, not findings",
    "docs/research/FREE_DATA_ADDENDA_BCD.md": "source catalogue -- source cards, not findings",
    "docs/research/FREE_DATA_ALTERNATIVES_SPEC.md": "spec document, not findings",
    "docs/research/GAP14_ROOTCAUSE.md": "forensic writeup for a gap row that already exists",
    "docs/research/GAP32_RESIZE_UP_SPEC.md": "spec for GAP #32 -- the row is the tracked item",
    "docs/research/GAP19_RECONCILE_GUARD_SPEC.md": "spec for GAP #19 -- the row is tracked",
    "docs/research/CRISIS_AUTOPSY_SPEC.md": "spec document, not findings",
    "docs/research/MAX_SURVIVORS_PROGRAM.md": "programme design, not findings",
    "docs/research/HYPOTHESIS_MAX_SPEC.md": "spec document, not findings",
    "docs/research/SPECIALIZED_SEATS_SPEC.md": "spec document, not findings",
    "docs/research/BYBIT_SECOND_VENUE_SPEC.md": "spec document, not findings",
    "docs/research/DISCOVERY_TELEMETRY_SPEC.md": "spec document, not findings",
    "docs/research/NLP_NORMALIZATION_SPEC.md": "spec document, not findings",
    "docs/research/PROSPECTOR_SPEC.md": "spec document, not findings",
    "docs/research/LITERATURE_SPEC.md": "spec document, not findings",
    "docs/research/GROWTH_UNLOCK_LADDER.md": "ladder definition, not findings",
    "docs/research/TWO_STAGE_DISCOVERY_LAW.md": "law text, not findings",
    "docs/research/DIGGER_TARGET_ROADMAP.md": "target list -- §33 governs what it yields",
    "docs/research/STRUCTURAL_EDGE_IDEAS.md": "idea list -- §33 / trial ledger governs",
    "docs/research/AXIS_PREREGISTRATIONS.md": "pre-registrations -- the trial ledger governs",
    # Batch 2 of the same artifact (scripts/run_axis_generate_20260805.py:53), same class, same
    # governing organ. Classified as a DECISION rather than left to default: each card in it is a
    # frozen, DSR-counted trial, so the trial ledger governs it exactly as it governs batch 1, and
    # the one QUEUE verdict is carried in research_agenda.json. Named per-file (not by prefix)
    # because the producer is a dated one-shot debt-clearer with no cron line -- a prefix claim
    # would silently pre-govern docs nobody has written or reviewed.
    "docs/research/axis_generation_20260805.md": "pre-registrations batch 2 -- trial ledger governs",
    "docs/DIGGING_CHARTER.md": "the law itself",
    "docs/OPERATOR_COMPACT.md": "operator agreement, not findings",
    "docs/GO_LIVE_CHECKLIST.md": "checklist -- gated by GAP #2",
    "docs/EVIDENCE_GATED_PROGRESSIONS.md": "progression definitions, not findings",
    "docs/KILL_THESIS.md": "kill criteria, not findings",
    "docs/REPO_EXTRACTION.md": "adoption record, not findings",
    "docs/RD_AGENT_AUDIT.md": "historical audit -- superseded by SYSTEM_REVIEW",
    "docs/institutional_knowledge.md": "knowledge base, not an obligation list",
    "docs/desk_lessons.jsonl": "the injected lesson corpus -- each row IS a closed lesson, and "
                               "scripts/learn.py audit is what governs it",
    "docs/desk_digest.md": "generated digest",
    "docs/graveyard.md": "terminal by construction",
    "docs/PROJECT_HANDOFF.md": "handoff doc, not findings",
    "docs/HOME.md": "index",
    "docs/DASHBOARD.md": "generated status",
    "docs/LIVE_CONNECTOR_SPEC.md": "spec for GAP #2 -- the row is the tracked item",
    "docs/research/oss_benchmark.md": "external benchmark log -- adoption_queue governs uptake",
    "docs/research/prospector_watchlist.md": "prospector cards -- governed by §33 dispositions",
    # VERIFIED 2026-07-26 before excluding: the file is WRITTEN by
    # scripts/generate_external_review_doc.py on every panel run, and its numbered block is a
    # verbatim copy of the GAP_REGISTER table ("## Current gap register (self-assessed, ranked)").
    # So every "finding" it carries is, by construction, already a register row -- demanding rows
    # for them would double-count the register against itself, and the next regeneration
    # overwrites anything written here. It is a DERIVED surface, never an original one: genuinely
    # new findings arrive as panel RESPONSES, which flow panel_inbox -> panel_rulings (in scope,
    # above) -> register rows. If the generator ever starts emitting desk-authored findings that
    # do not exist upstream, move it into _FINDING_DOCS.
    # trailing slash = the whole CLASS is claimed (a generator emits dated instances)
    "docs/research/deep_sweep/":
        "TWO producers' output under one directory (R0015): the weekly deep cold audit AND the\n"
        "literature deep-miner's LIT_* files -- both CADENCED PRODUCERS (§36) whose findings\n"
        "flow to improvement_inbox / the recommendation ledger / GAP_REGISTER rows (§35; e.g.\n"
        "LIT #72 -> GAP #79, litminer run 7 -> R0514-R0519). Each dated report is one run's\n"
        "snapshot, superseded by the next, never converted in place. The exclusion covers each\n"
        "producer on its own routing argument, not by directory accident.",
    "docs/EXTERNAL_PANEL_DOSSIER.md":
        "GENERATED dossier -- its numbered block is a copy of the register table; original panel "
        "findings enter via panel_inbox -> panel_rulings, which are in scope",
    # trailing slash = class entry, same design as deep_sweep/ above
    "docs/research/ARTIFACT_GOVERNANCE.md":
        "THE LAW ITSELF (§36). The register that says which law claims which artifact cannot be claimed by another register without circularity -- it is the root of that tree.",
    "docs/research/META_RESEARCH_DIRECTIVE.md":
        "L1.22 self-improvement. States how the desk researches its own research; enforced by the cycle's meta duty, not by an artifact-freshness clock.",
    "docs/research/UNREACHABLE_LAYER_TRIAGE.md":
        "§36 orphan-code triage. The standing record of which modules are unreachable and why, with each carrying an explicit wire/defer/retire verdict -- self-disposing, like the other triage registers.",
    # deep_review_inbox.md's §36 claim was HERE and has been merged into its single entry above
    # (ruff F601, 2026-08-05). A repeated dict-key literal is not a style nit: Python keeps the
    # LAST binding, so this block was silently deleting the measured findings-scope exclusion --
    # coverage numbers, the F0024/F0025 -> R0401 evidence and the "move this into _FINDING_DOCS"
    # escape hatch -- and leaving the exclusion justified by the wrong argument entirely.
    "docs/research/capability_hunt/":
        "daily L1.31 hunt records -- dated per-slot snapshots whose findings are ROWED IN THE\n"
        "SAME RUN by the hunt's own duty (L1.31/L1.39; 2026-07-31 proof: s5 -> R0153-R0173,\n"
        "every one disposed). The ledger drives them; the snapshot is the record. A hunt that\n"
        "fails to row is caught by the conversion fences on the rows' absence, and that failure\n"
        "belongs to the hunt run, not to scope.",
}


#: §36 PRODUCERS: artifacts that accumulate inventory under a cadence STATED IN THEIR OWN PROSE
#: and, until now, enforced by nothing. Each maps to the max age its own text promises. This is
#: the miner failure in its purest form -- a conversion rule written down, with no clock behind it.
_PRODUCER_CADENCE = {
    "docs/research/DATA_UNIVERSE_TAXONOMY.md": (
        7.0, "the standing hunting map (principal 2026-08-04): 30 domains + the bulk name-list "
             "every breadth organ diffs against daily. Its own text promises a weekly re-sweep of "
             "the coverage column; a taxonomy nobody re-verifies decays into the checklist it "
             "forbids itself to be. The daily half (the diff) is enforced through the organs "
             "whose dossiers carry the file whole, not through this stamp."),
    "docs/research/CRO_BRIEFING.md": (
        1.5, "the Chief Research Officer's cycle briefing, regenerated by scripts/run_cro.py on "
             "every firing. It is a PRODUCT, not inventory: the file is overwritten each cycle "
             "and the durable output is docs/research/cro_recommendations.jsonl, where each row "
             "owes a disposition. It goes stale in exactly one way -- the organ stopped firing -- "
             "and that is what this cadence catches. While the seat is dark the briefing is also "
             "the MANUAL path: it carries the identical prompt the seat would receive, so a "
             "hand-run review is comparable to an automated one."),
    "docs/research/weak_signal_registry.md": (
        3.0, "§23: >=2 weak signals from INDEPENDENT paths auto-promote to hypothesis generation, "
             "'checked each cycle during inbox triage' -- convention, never verified"),
    # REPOINTED 2026-08-19 (was docs/research/canary_searches.md at the same 4d bar): the run
    # duty moved from prose to an organ on 2026-08-02 (scripts/run_canaries.py appends a row per
    # run), and this fence must measure the artifact the duty actually produces. The history was
    # GITIGNORED EVIDENCE until today, so the .md's commit age stood in for a run record it never
    # was -- measured 16d "stale" while the organ had run 19h earlier. Same bar, truer subject:
    # nothing loosened. The .md keeps the canary SET + shift investigations (event-driven).
    "data/canary_history.jsonl": (
        4.0, "canary run-record (Charter §21): scripts/run_canaries.py appends a row per run, "
             "miner sessions fire it per digging session and desk snapshots commit it -- a stale "
             "COMMIT here means either the canaries stopped running or their evidence stopped "
             "being committed, and both are the outage this fence exists to catch"),
    # THE LIVE QUEUE, and this table pointed at the WRONG FILE for weeks (fixed 2026-08-12).
    # `generation_due.md` sat here at an 8d bar while having ZERO writers anywhere in the repo
    # (content frozen since 2026-07-29, header stamped 2026-07-16); it is now recorded terminal
    # below. The file run_cadence ACTUALLY writes is this one -- scripts/run_cadence.py:46 sets
    # _DUE_NOTE to it and :881 write_text's it on every hourly firing that has due items. So the
    # producer-cadence-stale defect fired four times in a single sweep against a document nothing
    # produces, and each ack reasoned about it as the live queue ("stale for exactly one reason --
    # the generate run it is waiting on"), concluding it would clear with an OpenRouter top-up. A
    # file with no writer cannot be freshened by unblocking its reader: that ack could never have
    # come true. Read-without-writer (L1.40 lens 1) applied to a governance table.
    # THE BAR'S ONE HONEST CAVEAT, stated rather than discovered later: run_cadence writes this
    # file only under `if due:`, so a fully-drained queue stops refreshing it and would read as
    # stale. That is the L1.51 "what does absence look like?" trap, and it is not live today --
    # PROSPECTOR (7d) and the DATA-AXIS dig (7d) are standing recurring duties, so the queue has
    # never been empty. If it ever drains, the right repair is to make run_cadence stamp an
    # explicit empty queue, NOT to widen this bar until it cannot fire.
    "docs/research/cadence_duties.md": (
        3.0, "the LIVE generation-duty queue, rewritten by scripts/run_cadence.py:881 on each "
             "hourly firing with due items. It goes stale in exactly one way that matters -- "
             "run_cadence stopped firing -- and that is what this catches. The brain drains it "
             "by executing the scoped generate runs and setting gen_done_<name> / "
             "last_live_generate in data/cadence_state.json."),
    "docs/research/adoption_queue.md": (
        35.0, "trigger-gated methods (fracdiff, dollar bars, ...) -- nothing notices when a "
              "precondition ARRIVES, so a due adoption waits forever"),
    # (A duplicate blind_rediscovery_log.md entry lived here from 2026-07-31 until a concurrent
    # session classified the SAME file below at 31.0d. Removed rather than merged: Python keeps
    # the LAST duplicate key silently, so two entries meant one of the two stated reasons was
    # decorative and nobody could tell which. The surviving entry is the better-founded one --
    # it READS the cadence from the document's own header, which is what §36 asks for, instead of
    # inventing one here. The dropped entry's only distinct argument was a 35d-vs-31d margin so an
    # on-time monthly run cannot fire the check on its own due date; if that ever fires
    # spuriously, widen the surviving entry rather than re-adding a second key.)
    # The register is a producer too -- the one every other law routes into. Its own header
    # promises a re-rank every daily cycle; check_gap_register_health reads the self-declared
    # stamp, and this is the file-level backstop if the stamp itself stops being written.
    "docs/GAP_REGISTER.md": (
        3.0, "re-ranked at the START of every daily AI cycle by its own rule -- the organ §35 and "
             "§36 both depend on, and it was checked by nothing"),
    # THE TIER-1 BENCHMARK is a PRODUCER: sub-T1 rows are queued into the max-push hunt every
    # refresh, and the deep sweep re-grades it weekly from auditor evidence. A stale benchmark
    # silently stops queueing gaps -- the exact inventory-accumulates failure §36 catches.
    "docs/research/TIER1_BENCHMARK.md": (
        8.0, "L1.36/L1.31: re-graded weekly by the deep-sweep synthesis from auditor evidence, "
             "and parsed by run_max_push every refresh so every sub-T1 row enters the daily "
             "hunt -- if it goes stale, gaps stop being queued and nothing would say so"),
    # THE DISCRETIONARY DESK is a PRODUCER: it states the sleeve's measured constants (noise
    # floors, costs, the cost-adjusted breakeven hit rate) and every one is a MEASUREMENT that
    # drifts. A stale page means the desk is reasoning from last month's volatility regime and
    # last month's fee tier while believing they are current -- and the numbers in it are what the
    # principal reads before a capital decision, which is the most expensive place for a quietly
    # outdated figure to sit.
    # CLASSIFIED 2026-07-31 on arrival from the VPS lineage -- the §36(2) fence fired the moment
    # it landed, which is the law working. The file states its own governance in its header
    # ("Governed by §36 ... max age = one month + the early-fire rule"), so the cadence is READ
    # from its prose rather than invented here, exactly as §36 intends.
    "docs/research/blind_rediscovery_log.md": (
        31.0, "L1.9/§36: the blind-rediscovery seat runs once per cycle and logs every invention "
              "for a 12-month literature comparison -- the desk's only direct measurement of "
              "whether it is genuinely creative or an excellent summariser. Its cadence is stated "
              "in its own header (one month); going stale means the seat stopped running and the "
              "12-month comparison silently loses its baseline."),
    "docs/DISCRETIONARY_DESK.md": (
        14.0, "L1.6/L1.41: re-stated from the resolver's measured output (noise floors, realised "
              "costs, conditional hit rates, cost-adjusted breakeven) -- if it goes "
              "stale the section claims measurements that are no longer true"),
}
#: Artifacts that are terminal by nature: templates, forensic write-ups, protocol libraries. They
#: accumulate no inventory, so they owe no cadence -- recorded here so "no law" is a DECISION.
_TERMINAL_ARTIFACTS = {
    "docs/CANONICAL_RELEASE_RECONCILIATION.md":
        "A DATED MEASUREMENT, taken 2026-09-05T00:02Z and stamped as such in its own first "
        "paragraph ('this file is the measurement... nothing here is an estimate'). It records the "
        "three code-line SHAs and the backup refs cut before the merge work, so its content is "
        "true of that instant and of no other -- a re-work clock on it would schedule rewrites of "
        "history, the alpha_hunt_20260731 and EXECUTION_QUEUE precedent verbatim. The LIVE version "
        "of the question it answers ('is it really live?') is carried by running machinery, not by "
        "this file: release_identity.verdict() answers it every gateway pass and writes "
        "data/release_identity.json, and the CI seal job keeps RELEASE.json naming the tested SHA.",
    "docs/research/archive_crypto_era/":
        "THE RETIRED DESK'S FROZEN RECORD, claimed as a DIRECTORY CLASS because the archive takes "
        "further files as more of the crypto era is retired into it and an exact-path claim could "
        "never keep up (the generator precedent above it). Its own README states the terms: "
        "everything inside is history, not a mandate, and no miner may draw a ground from it. "
        "These are measured negatives with pre-registered protocols -- the most expensive "
        "knowledge the desk owns and the cheapest to lose -- so they are kept rather than deleted, "
        "and nothing inside owes a disposition because nothing inside is live work. The MT5 "
        "UNIVERSE MANDATE (2026-08-18) is what makes the whole directory terminal.",
    "docs/research/alpha_hunt_20260731.md":
        "FULLY CONVERTED HUNT RECORD (verified by fresh read 2026-08-19). Every rowed candidate "
        "reached a ledger disposition: R0115/R0118/R0119/R0120/R0121 implemented (screens built "
        "and scheduled -- funding_spread, event_density, crowding residual, collateral_allocation, "
        "funding_interval_mismatch), R0116 screened NEGATIVE (first-class deliverable), R0117 "
        "rejected on measurement; the un-rowed candidates were routed to the axis watchlist for "
        "screen-on-discovery, whose own fences hold them. The L1.39 concern this cadence encoded "
        "-- candidates accumulating un-screened -- is structurally empty for a drained record: "
        "the EXECUTION_QUEUE precedent, a completed pass's write-up is the record, not a backlog, "
        "and a re-work clock on a dated snapshot schedules rewrites of history. Reclassified "
        "from _PRODUCER_CADENCE with the verification stamp appended in-doc.",
    "docs/EXECUTION_QUEUE.md":
        "COMPLETED BATCH RECORD (verified by fresh read 2026-08-18). Ranks 2-7 ALL BUILT AND "
        "WIRED 07-30 (the doc's own status table, artifacts on disk); rank 1 dispositioned the "
        "same day (14 retired / 32 evidenced-blocked / 7 activate-pending). The live residue is "
        "carried by RUNNING machinery, not by this file: dormancy/unwired is measured daily "
        "(check_unwired_capability, 241 at reclassification), strategic-director activation is "
        "OpenRouter-402-blocked and tracked in PRINCIPAL_ACTION, and every item-exit obligation "
        "lands in the recommendation ledger per its own SS41 rule. A completed batch's write-up "
        "is the record, not a backlog -- the INTRADAY_ROTATION precedent; a 7d re-work clock on "
        "a dated snapshot schedules rewrites of history. Reclassified from _PRODUCER_CADENCE "
        "with the verification stamp appended in-doc.",
    "docs/research/MASTER_APPENDIX_A_PENDING_RESEAL.md":
        "PARKED CONSTITUTIONAL TEXT AWAITING THE PRINCIPAL (2026-08-18). Sections appended to "
        "the sealed master on 08-17 by 98d63ce3+6b8b61a9 WITHOUT the principal-only --reseal; "
        "786e98d9 restored the sealed 218-section master and parked the appendix here verbatim "
        "so the seal check passes while the text stays reviewable. It is an immutable exhibit, "
        "not inventory: the one action it owes is the principal's accept-or-reject, tracked by "
        "ledger row R0615 and the 2026-08-18 PRINCIPAL_ACTION block (which carries the recorder-"
        "polarity arithmetic). On accept it merges into the master under --reseal and this file "
        "dies; on reject it dies too. A producer cadence or findings scan here would schedule "
        "rewrites of a text whose whole point is that only the principal may touch it.",
    "docs/research/ELITE_QUANT_INTELLIGENCE_MANDATE.md":
        "STANDING PRINCIPAL DOCTRINE (2026-08-13), terminal by nature rather than by exhaustion. "
        "It accumulates no inventory and has no producer: it is the principal's directive on "
        "elite-firm capability recovery, extreme-outlier forensics, future-frontier search and "
        "(PART III, 2026-08-14) external intelligence mining across the English and Chinese "
        "research ecosystem, binding on every brain, miner and LLM seat rather than on the "
        "three builder seats alone. It changes only by principal decision. A "
        "producer cadence here would be actively wrong -- it would imply the law goes stale and "
        "invite a scheduled rewrite of something no schedule owns. Classified DOCTRINE in "
        "ARTIFACT_GOVERNANCE.md and indexed in CLAUDE.md so a fresh session can find it, which is "
        "the only freshness property a standing law has.",
    "docs/research/generation_due.md":
        "SUPERSEDED SNAPSHOT WITH NO PRODUCER (recorded 2026-08-12). Header stamped "
        "2026-07-16T23:23Z, last content change 2026-07-29, and a repo-wide search for a writer "
        "returns NOTHING -- no write_text, no append, no shell redirect. The live queue with the "
        "same header template is docs/research/cadence_duties.md, which run_cadence.py:46/:881 "
        "actually writes; this table governed THIS file on an 8d producer cadence instead, so "
        "producer-cadence-stale fired against a document nothing produces and was acked four "
        "times in one sweep on the theory it would clear when a generate run unblocked. It could "
        "not: an unread reader cannot freshen an unwritten file. TERMINAL, NOT DELETED, because "
        "it still has live READERS -- scripts/screen_fred_macro_axis.py:1/:325 cites its line 5 "
        "as the provenance of the fred_macro scoped run, and scripts/build_audit_coverage.py:54 "
        "lists it. Deleting it would break the audit trail of a duty that was actually executed. "
        "It is an immutable record of what was owed on 2026-07-16, superseded by the live queue, "
        "never edited.",
    "docs/research/PREMORTEM_20260805.md":
        "DATED PRE-MORTEM RECORD (run 1, 2026-08-05, R0105) -- the first time that mission has "
        "ever fired. Terminal because it is an immutable transcript of ONE dated adversarial "
        "pass, not an inventory: it accumulates nothing, and the work it implies is tracked "
        "OUTSIDE it by a gate rather than by a disposition on the file. The funded re-run it "
        "still owes is enforced by check_gate0_ready's premortem_completed criterion, which "
        "reads 1/8 NOT-READY and blocks the deposit until 8 distinct seats answer -- so the "
        "obligation cannot be lost by nobody re-reading this doc. It exists as a file only "
        "because run_external_panel write_text's docs/research/panel_inbox.md on EVERY run, so "
        "the next mission of any kind destroys the readable copy; the raw response survives in "
        "the append-only panel log but unread. Superseded by the funded re-run, never edited.",
    "docs/research/axis_generation_20260805.md":
        "DATED GENERATE-RUN RECORD (batch 2, the 9 stale Bronze axes, 2026-08-05). Terminal "
        "because every outcome was ROUTED BY THE GATE IN THE SAME RUN that wrote the file, so "
        "it holds no un-converted inventory: 1 candidate queued to the research agenda "
        "(etf_flow_price_divergence_absorption, ev=0.0091), 8 rejected below the EV threshold "
        "and written to dnr, and 9 research_memory rows logged including every negative -- the "
        "forgetting-factory guard. The honesty guard is why the rejects dominate and why that "
        "is the CORRECT result, not a thin run: most SHOULD fail on base rates, and a "
        "manufactured survivor is negative discovery. Nothing in this file awaits a "
        "disposition; re-running it re-registers nothing (agenda dedupe) and a NO-CANDIDATES "
        "pass leaves doc, memory and cadence state alone. Superseded by the next dated batch, "
        "never edited to look better.",
    "docs/research/VPS_STATE_20260805.md":
        "dated runtime-truth record read live off the VPS (recorders up, 10GB moat tape, the "
        "two moat screen survivors' OOS collapse to the 0.10 ceiling, the carry fast-track's "
        "regime-evidence blocker). It accumulates no inventory: each finding is either a "
        "correction already applied to this repo's claims or an operator action named in the "
        "text. Superseded by the next live read, never edited to look better.",
    "docs/research/NEW_FAMILY_GENERATORS_PREREGISTRATION.md":
        "PRE-REGISTRATION (2026-08-04) of the seven new generator families + the 15m/1h "
        "intraday re-test, committed before any of them ran. Immutable by design; conversions "
        "land in reports/real_campaign.json and reports/intraday_rotation_{15m,1h}.json, and "
        "the two deferred rows (H9 conditional on the 15m result, H4/H5 on the moat tape) "
        "carry their blockers in the text.",
    "docs/research/DISCRETIONARY_PLAYBOOK_PREREGISTRATION.md":
        "PRE-REGISTRATION of the principal's playbook + tier list as hypotheses H1-H11 "
        "(2026-08-04), sizing module rejected under R0143 in the text itself. Immutable by "
        "design; each hypothesis converts through the standard campaign (H3 ict-screen already "
        "cadenced, H6-H10 queued in the generator roadmap), and outcomes land in reports/ and "
        "the ledger, never back in this file.",
    "docs/research/INTRADAY_ROTATION_PREREGISTRATION.md":
        "PRE-REGISTRATION (2026-08-04, committed before data), same immutability rationale as "
        "the other preregistrations: thresholds fixed before the backtest are the only kind "
        "that constrain one. Its conversion happened same-day: the walk-forward ran and the "
        "verdict is recorded in INTRADAY_ROTATION_RESULT.md. Editing it now would destroy the "
        "instrument.",
    "docs/research/INTRADAY_ROTATION_RESULT.md":
        "dated measurement record (25,036 + 565 OOS trades, NO-GO both strategies, cost-in-R "
        "1.1 at 5m scale, half-Kelly zero). Regenerable from scripts/run_intraday_rotation.py "
        "into reports/intraday_rotation.json; the one follow-up it names (15m/1h re-test, new "
        "trial count) is carried as a hypothesis in the campaign pipeline, not as inventory "
        "here. NOTHING in it licenses moving a threshold.",
    "docs/RECORDER_DEPLOY.md":
        "deploy runbook (recorder systemd units + debug reference), not inventory. Consumed by "
        "being EXECUTED on the VPS -- ops/deploy_vps.sh supersedes its manual steps and the "
        "scheduler manifest owns the units it describes. It queues nothing; the action it names "
        "is tracked as the operator's recorder-bringup blocker, not as rows here.",
    "docs/VPS_BRINGUP.md":
        "deploy runbook (whole-desk bringup: cadence engine, pager, supervisor, ruin rail), same "
        "instrument as RECORDER_DEPLOY.md. Executed, not converted; the desk-not-running gap it "
        "closes is the operator-side blocker the ceiling report names. Grows only when bringup "
        "itself changes, which is a repair event with its own commit.",
    "docs/research/FAILED_BREAKOUT_PREREGISTRATION.md":
        "PRE-REGISTRATION, dated 2026-08-04 and written before data or analysis code existed -- "
        "immutability is the entire point: thresholds chosen before any backtest are the only "
        "kind that constrain one. It never accumulates inventory; the hypothesis it pins either "
        "gets tested through the standard gauntlet (its outcome ledgered like any candidate) or "
        "dies untested. Editing it after data arrives would destroy the instrument.",
    "docs/research/COINM_CONVEXITY_PREREGISTRATION.md":
        "PRE-REGISTRATION (2026-08-13, R0462) of the COIN-M-vs-USDT-M convexity-differential "
        "measurement + the two screen constructions, written BEFORE the backfill was read. Same "
        "instrument and same immutability rationale as FAILED_BREAKOUT_PREREGISTRATION.md: "
        "thresholds fixed before data are the only kind that constrain anything. It records one "
        "additional thing the others do not -- a STRUCTURAL kill measured before the run (Binance "
        "has never listed a USDT-M quarterly for BNB/SOL/XRP, so the standing trigger's '>=3 of 5 "
        "underlyings' clause can never fire; ceiling 2 of 5). Its conversion is "
        "COINM_CONVEXITY_RESULT.md; nothing learned goes back into this file. Superseded BY A "
        "NAMED CONDITION, not a date: if Binance ever lists a USDT-M quarterly for BNB, SOL or "
        "XRP, a new pre-registration must supersede it by name.",
    "docs/research/COINM_CONVEXITY_RESULT.md":
        "DATED MEASUREMENT RECORD (2026-08-13, R0462) of the screen the file above pre-registered "
        "-- same pairing as INTRADAY_ROTATION_PREREGISTRATION.md / INTRADAY_ROTATION_RESULT.md. "
        "It exists as a TRACKED artifact because its regenerable twin "
        "(reports/axis_screens/coinm_convexity_20260813.json) sits under a gitignored path, and a "
        "gitignored evidence path is a dangling citation on every box but the one that ran it. "
        "Regenerable from scripts/screen_coinm_convexity.py. NOTHING in it licenses moving a "
        "threshold or re-scoring the standing EV REJECT.",
    "docs/research/THREE_MECHANISM_PREREGISTRATION.md":
        "PRE-REGISTRATION of the desk's named mechanism set (trial count declared in advance), "
        "same instrument and same immutability rationale as FAILED_BREAKOUT_PREREGISTRATION.md. "
        "Its conversion is the campaign run that tests exactly the pre-declared list; anything "
        "learned lands in reports/ and the ledger, never back in this file.",
    "docs/research/ADVERSARIAL_REVIEW_RUBRIC.md":
        "standing review checklist, not inventory. Its ten defect classes are each derived from a "
        "defect actually shipped on this desk and each carries its own test, so the document is "
        "consumed by being APPLIED to a diff rather than by being converted into rows. Nothing "
        "queues here: a finding produced by running it is ledgered like any other finding. Grows "
        "only when a NEW class is found in production, which is a repair event with its own row.",
    "docs/research/gate_power_audit.md":
        "dated measurement record (Type I / Type II of every gauntlet gate, 2026-08-01). It "
        "accumulates no inventory because its conclusions were CONVERTED the same day: the "
        "duplicated multiplicity correction became a code change in libs/autodiscovery/"
        "validation.py, its evidence was rowed as R0224, and its claims are pinned by "
        "tests/validation/test_dsr_single_correction.py. The numbers themselves are regenerable "
        "from scripts/audit_gate_power.py into reports/gate_power_audit.json, which is where a "
        "cadence would belong if one is ever wanted -- the doc is the write-up, not a queue. The "
        "two findings it does NOT convert (min-length truncation, top-K screen) are carried as "
        "ledger rows, not as unread inventory here.",
    "docs/research/cn_oss_extraction_20260731.md":
        "dated verification record (10 CN OSS projects: 8 real, 1 hallucinated, 1 proprietary). "
        "It accumulates no inventory: its 5 extracted axes were rowed as R0100 and appended to "
        "data_axis_watchlist.md, and its verdicts were folded into ops/frontier_cn_prompt.txt so "
        "the CN seat never re-spends the verification. The doc is the evidence, not a queue.",
    "docs/research/REALITY_CHECK_POWER.md":
        "dated power measurement (Type II of the reality_check gate on the real cohort's shape, "
        "2026-08-01), same class as gate_power_audit.md. It accumulates no inventory: the numbers "
        "regenerate from scripts/audit_reality_check.py into reports/reality_check_audit.json, "
        "and its conclusion is a single named build -- a pooled-by-mechanism path in "
        "run_real_campaign -- not a queue of items. The measurement it records is terminal: the "
        "gate's false-positive rate is clean (0/3,900 at N=196) and its power inside the desk's "
        "real-edge band is not, which is a fact about the campaign's design rather than an "
        "inventory to work off. NOTHING here licenses moving a threshold, and the doc says so.",
    "docs/research/PERMUTATION_NULL_RESULT.md":
        "dated measurement record (permutation null + monkey test + overlays on OKX daily perps, "
        "2026-08-01), same shape as gate_power_audit.md and governed the same way. It accumulates "
        "no inventory because every conclusion it reaches was CONVERTED the day it was written: "
        "the biased two-shuffle construction became the coupled permutation in libs/validation/"
        "bar_permutation.py, the float-dust p-value became its tie tolerance, the per-bar/"
        "annualised units error became MIN_ADMISSION_ANN_SHARPE in screen_admission, and the "
        "vol-targeting and conditional trade-dependence results became libs/research/overlays. "
        "The numbers regenerate from scripts/measure_permutation_null.py into reports/"
        "permutation_null.json, which is where a cadence would attach if one is ever wanted -- "
        "the doc is the write-up, not a queue. The one thing it does NOT convert is the live "
        "candidate (time_series_mom[40], p=0.008, stable across three assets); that is carried by "
        "scripts/run_real_campaign.py, which runs the full gauntlet on it, not as unread "
        "inventory here.",
    "docs/research/BITMEX_DECADE_INGEST_SPEC.md":
        "build spec (directive bitmex-ingest-spec, closed 2026-07-31) -- executed via its phase "
        "artifacts: phase 1 landed same-day (data/bitmex_funding.jsonl, 11,148 rows 2016->now); "
        "phase 2 is the tranche cron line the spec defines. Conversion is tracked on those "
        "artifacts, not on this doc.",
    "docs/research/FRONTIER_MINER_TEMPLATE.md": "template spec -- instantiated, not converted",
    "docs/research/GAP34_FORENSIC.md": "forensic write-up for a closed gap",
    "docs/research/self_interrogation_patterns.md": "protocol library -- applied, not converted",
    "docs/playbooks/carry.md": "runbook -- followed, not converted",
    "docs/playbooks/go_live.md": "runbook -- followed; the gate is GAP #2",
    "docs/playbooks/ops_checklist.md": "runbook -- followed, not converted",
    # STANDING DOCTRINE (2026-07-28). These bind organs; they are not inventory awaiting
    # conversion, and "convert the doctrine" is not a coherent action. Terminal is the DECISION
    # the law demands, not a default -- each governs behaviour and is superseded by amendment,
    # never worked off a queue.
    "docs/MASTER_QUANT_CONSTITUTION.md":
        "principal-supplied sealed top-level doctrine -- injected at controller "
        "entry, never an inventory",
    "docs/audit_shards/":
        "generated audit-shard class -- disposable working views, never a findings backlog",
    "docs/research/ETHBTC_ROTATION_PREREGISTRATION.md":
        "immutable preregistration -- superseded by its result, never refreshed in place",
    "docs/research/FULL_SWEEP_PREREGISTRATION.md":
        "immutable preregistration -- superseded by its result, never refreshed in place",
    "docs/research/TRAIL_WIDTH_PREREGISTRATION.md":
        "immutable preregistration (R0479, 2026-08-18) -- evaluated hourly by "
        "resolve_paper_book's trail_forward block; superseded by its verdict, never refreshed "
        "in place",
    "docs/research/MANAGEMENT_SWEEP_PREREGISTRATION.md":
        "immutable preregistration -- superseded by its result, never refreshed in place",
    "docs/research/recent_changes.md":
        "append-only change record -- each row is terminal evidence, not inventory",
    "docs/research/TIER1_CONTROLLER_MANDATE.md":
        "standing subordinate implementation doctrine under the sealed master",
    "docs/RESEARCH_DATA_TRANSPORT.md":
        "deployment runbook -- superseded by a new transport design, never cadence-refreshed",
    # 2026-08-26 consolidation docs (gap-wirer): the two operative governing documents, their
    # disposition map, and two standing specs -- classified in ARTIFACT_GOVERNANCE.md same cycle.
    "docs/LAWS.md": "operative constitution of the 2026-08-25 consolidation -- amendment is a principal act, never a cadence",
    # CLASSIFIED 2026-09-05 at the birth-property boundary: three docs landed unclaimed between
    # 2026-08-27 and 2026-09-04 and the law gate was red on every push until each got a decision.
    "docs/GROWTH_GOVERNANCE.md":
        "standing principal order (2026-09-04): both growth rules verbatim, enforced by "
        "check_growth_governance.py at every law-gate boundary and by check_heat_floor_wiring.py "
        "on the box -- binds organs, amended by principal decision, never a cadence",
    "docs/research/offbook_source_seeds.md":
        "RETIRED GROUND. A Binance/crypto-native source-seed map (its own header says so), "
        "re-landed by a free-tier seat on 2026-08-30 -- twelve days after the MT5 universe "
        "mandate forbade every crypto-exchange hunt. No miner may draw a ground from it, so it "
        "is a record of what was once mapped, never a queue; whether it should exist at all is "
        "the principal's call, not a cadence's",
    "docs/research/prospector_harvesters.md":
        "seat handoff record: the resumable MQL5 slippage harvester a research-frozen prospector "
        "seat could not land in scripts/ (2026-08-27). The obligation it carries -- wiring the "
        "collector -- is the ledger row the doc names, not a re-read of the doc",
    "docs/RESEARCH.md": "operative research mandate -- every organ's first standing order, amended by decision only",
    "docs/MANDATE_COVERAGE.md": "terminal disposition map of the consolidation -- a re-consolidation writes a NEW map",
    "docs/policy/DEEPSEEK_SECOND_FLYWHEEL_MANDATE.md": "standing principal mandate -- donation-only flywheel authority limits",
    "docs/research/MOAT_NODE_SPEC.md": "standing spec -- implementations change by code, the spec by decision",
    "docs/research/EXPLORATION_DOCTRINE.md": "standing doctrine -- binds organs, not an inventory",
    "docs/research/MEASUREMENT_DOCTRINE.md": "standing doctrine -- binds organs, not an inventory",
    "docs/research/OPERATING_DOCTRINE.md": "standing doctrine -- governs what to build",
    "docs/research/RESEARCH_EXCELLENCE.md": "standing doctrine -- governs how research is run",
    "docs/DESK_BRIEF.md":
        "derived snapshot -- machine-generated from measured state by research_exchange.py and "
        "overwritten on each run, so converting it is meaningless. Terminal by construction, the "
        "same reasoning already applied to EXTERNAL_PANEL_DOSSIER.md.",
    "docs/research/MECHANISM_GRAPH.md":
        "reference structure CONSUMED by hypothesis_generator.py + llm_blind_researcher.py to "
        "choose what gets asked -- applied, not converted (cf. self_interrogation_patterns.md). "
        "It declares no cadence, and inventing one would build a gate that fires forever.",
    "docs/EXTERNAL_PANEL_DOSSIER.md":
        "derived snapshot -- REGENERATED from live state on every panel run by "
        "generate_external_review_doc.py, never an inventory. Its findings flow panel responses "
        "-> panel_inbox -> panel_rulings -> GAP_REGISTER rows (§35), so converting the dossier "
        "itself is meaningless: the next run overwrites it. Terminal by construction.",
    # CLASSIFIED 2026-07-29 (closure cycle). This check FIRED on the four documents that cycle
    # created, which is the law working: each is classified below as a DECISION, never a default.
    "docs/CYCLE_20260729_CLOSURE.md":
        "CYCLE REPORT -- a dated record of one cycle's measured results with every proving command, "
        "same class as a forensic write-up (GAP34_FORENSIC.md). Its open items are carried by "
        "GAP_REGISTER rows and the ratchet fence, not by converting the report.",
    "docs/WEEKLY_MAX_CYCLE.md":
        "standing contract for the weekly gap-max sweep (constitution L4) -- it BINDS the sweep's "
        "conduct and effort floor and is superseded by amendment, never worked off a queue. Same "
        "class as the standing doctrines above.",
    "docs/research/MUTATION_BASELINE.md":
        "MEASUREMENT RECORD with a live artifact behind it (data/mutation_score.json) and a "
        "ratchet fence that keeps it honest (check_ratchets: test_strength_min_kill_rate, floor "
        "only rises). Its 'owed next' targets are tracked by that fence and by GAP #53's row, not "
        "by converting the write-up -- the write-up is the evidence, the fence is the queue.",
    "docs/research/COT_SCREEN_RESULT.md":
        "SCREEN RESULT, terminal by construction: a Stage-A screen has zero promotion authority, "
        "so there is nothing to convert. Its two dispositions are already routed -- the "
        "positioning-axis REJECT is recorded against register #77 (and cancels the queued crypto "
        "positioning acquisition), and the un-measurable decay leaves the borrowed -58% prior "
        "labelled borrowed under register #71. Re-entry needs a named enabling change (L1.16a).",
    "docs/research/TRIAGE_20260729_PRINCIPAL_BATCH.md":
        "TRIAGE LEDGER in the same class as SUBSYSTEM_TRIAGE.md / TRIAGE_ADDENDUM.md: every row "
        "already carries its disposition (BUILT / UPGRADED / BUILD / QUEUE / REJECT with reason), "
        "so the document IS the conversion record rather than inventory awaiting one. Rows that "
        "became work carry register rows; rows that were rejected carry their reason.",
}


def check_gap_register_health(defects) -> None:
    """§36(3): the register is held to the rules it states about ITSELF.

    §35 and §36 route every finding INTO the register, which makes it the load-bearing organ for
    both -- and it was checked by nothing. Its own header declares 're-ranked at the START of every
    daily AI cycle', 'items stale >7 days MUST be escalated (implement / defer with deadline /
    retire with reason)' and 'never empty without written justification'. All three were rules
    written INSIDE the document they govern: exactly the shape §36 names as a rule with no clock.
    Routing findings into a bucket nobody empties is not an improvement, it is a tidier backlog.

    The re-rank age comes from the SELF-DECLARED stamp, never from mtime or commit time -- editing
    the file must not be able to fake a re-rank that never happened.
    """
    from libs.research.finding_registry import register_health

    gr = ROOT / "docs/GAP_REGISTER.md"
    if not gr.exists():
        return
    h = register_health(gr.read_text("utf-8"), today=datetime.now(UTC).date())
    if h.n_rows == 0:
        defects.append(("gap-register-unparseable", f"§36(3): {h.verdict}"))
        return
    if h.stale_rows:
        shown = ", ".join(h.stale_rows[:5])
        more = f" (+{len(h.stale_rows) - 5} more)" if len(h.stale_rows) > 5 else ""
        defects.append((
            "gap-register-rows-stale",
            f"§36(3): {len(h.stale_rows)} OPEN row(s) past the register's own 7-day escalation "
            f"bar, oldest {h.oldest_open_days:.0f}d: {shown}{more}. Each owes one of the three "
            "exits the register names -- implement, defer WITH a deadline, or retire with a "
            "reason. Re-ranking the header is not one of them: the rule is about ITEMS, and "
            "measuring the re-rank stamp instead let a daily stamp make every row immortal."))
    # THE MECHANICAL HALF, REPORTED SEPARATELY. scripts/rerank_gaps.py computes every part of the
    # re-rank that needs no opinion, every cycle. It cannot discharge the judgment duty and does
    # not try -- but "the countable work is current and the judgment call is owed" is a materially
    # different state from "nobody has touched this", and collapsing them costs the reader the
    # only distinction that changes what to do next.
    _mech = ""
    with contextlib.suppress(OSError, json.JSONDecodeError):
        _m = json.loads((ROOT / "data/gap_rerank.json").read_text("utf-8"))
        _age = (NOW - datetime.fromisoformat(_m["ts"]).timestamp()) / 3600.0
        _hot = [f"#{r['id']}" for r in _m["rows"]
                if r["verdict"] not in ("ON-CLOCK", "TRACKED")][:6]
        _mech = (f" MECHANICAL PASS {_age:.0f}h old: {_m['need_decision']} of "
                 f"{_m['open_rows']} open rows need a decision"
                 + (f" ({', '.join(_hot)})" if _hot else "")
                 + " -- the judgment call is what remains, and it arrives pre-computed.")
    if h.rerank_breach:
        defects.append((
            "gap-register-rerank-breach",
            f"§36(3): {h.verdict} Re-rank now and escalate anything genuinely stuck -- this is the "
            "organ every other law depends on; when it stops moving, everything routed into it "
            f"stops with it, silently.{_mech}"))
    elif h.rerank_stale:
        defects.append((
            "gap-register-rerank-stale",
            f"§36(3): {h.verdict} Caught as DRIFT, before the 7-day escalation bar it sets for "
            f"itself.{_mech}"))
    if h.undated_open:
        defects.append((
            "gap-register-parked-rows",
            f"§36(3): {len(h.undated_open)} open row(s) carry NO date in their plan -- "
            f"{', '.join(h.undated_open)}. The register's own three exits are implement / defer "
            "WITH A DEADLINE / retire with reason; a row with no date took none of them and is "
            "parked, which is the state the rule exists to forbid."))
    if h.ownerless:
        defects.append((
            "gap-register-ownerless",
            f"§36(3): open row(s) with no owner -- {', '.join(h.ownerless)}. Unowned work is "
            "nobody's, and the escalation has no addressee."))


def check_producer_cadence(defects) -> None:
    """§36: an artifact that accumulates inventory declares a cadence and is HELD to it.

    The miner failure, in its purest form: four artifacts state a conversion rule in their own
    prose -- 'auto-promote on convergence', 're-run each digging session', 'the brain executes and
    marks them', 'monthly trigger re-check' -- and NOTHING checked any of it. A rule written in a
    document it governs is a rule with no clock; it is obeyed exactly as long as somebody
    remembers, which is the failure §33 and §35 each closed for their own surface.

    Age is measured from the last COMMIT, not mtime: a fresh clone stamps every file at checkout,
    and this check must mean the same thing on the VPS and in a sandbox.
    """
    import subprocess

    stale = []
    for rel, (max_days, why) in _PRODUCER_CADENCE.items():
        p = ROOT / rel
        if not p.exists():
            continue
        try:
            out = subprocess.run(["git", "log", "-1", "--format=%ct", "--", rel],
                                 cwd=ROOT, capture_output=True, text=True, timeout=15)
        except (OSError, subprocess.SubprocessError):
            return  # no git -- the check does not apply here
        if out.returncode != 0 or not out.stdout.strip():
            continue
        with contextlib.suppress(ValueError):
            age_d = (NOW - float(out.stdout.strip())) / 86400.0
            if age_d > max_days:
                stale.append(f"{Path(rel).name} {age_d:.0f}d (bar {max_days:.0f}d) -- {why}")
    for s in stale:
        defects.append((
            "producer-cadence-stale",
            f"§36: {s}. The artifact's own text promises this cadence; nothing enforced it until "
            "now. Work it and commit, or amend the stated cadence to one the desk actually keeps "
            "-- a promise nobody checks is how inventory rots in plain sight."))


#: Organs that ask an LLM for IDEAS. Each must (a) push until the seat is exhausted and (b) ask
#: every funded seat. collector_author is deliberately absent: it writes ONE working fetch(), not
#: an enumeration, so the analysis ladder is the wrong instrument there and extract_code() on a
#: ten-round concatenation would pick a block from the wrong round.
_IDEA_ORGANS = ("run_external_panel", "hypothesis_generator", "breadth_expander",
                "llm_code_auditor", "meta_architect", "llm_blind_researcher")


def check_llm_exhaustion(defects) -> None:
    """STANDING POLICY: never accept a seat's first answer, and never ask only some of the seats.

    TWO DEFECTS, ONE ROOT. Both were found 2026-07-31 and both were systemic rather than local.

    1. ONE-SHOT HARVESTING. Every organ took a single completion per seat and discarded the rest
       of what that seat knew. The expensive half of an LLM call is the INPUT -- a ~40k-char
       mission plus dossier, graveyard and rulings -- and it was being paid for once and thrown
       away. Pushing reuses that whole context (same conversation, nothing re-sent), so additional
       rounds cost only output tokens. The ladder stops on measured EXHAUSTION, not a fixed count:
       novelty per round against everything already said, so "it gave up" is a number.

    2. SEAT CAPS BY LITERAL LENGTH. `seats.resolve(SEATS, n=len(SEATS))` appeared in FIVE organs.
       The hardcoded list's LENGTH became the cap on how many funded seats were ever asked -- 3 of
       13 in four of them. The desk paid for thirteen lineages of training data and consulted
       three. This is the same shape as the inline `${_BRAIN_MODEL_CHAIN:-...}` pin and the
       `_LABS` literal that capped roster breadth: a constant quietly bounding something that was
       supposed to grow with the roster.

    Checked structurally rather than by convention, because a convention that only lives in a
    commit message decays the first time someone adds an organ.
    """
    missing_push, capped = [], []
    for name in _IDEA_ORGANS:
        p = ROOT / "scripts" / f"{name}.py"
        if not p.exists():
            continue
        with contextlib.suppress(OSError):
            src = p.read_text("utf-8", errors="ignore")
            if "push_rounds(" not in src:
                missing_push.append(name)
            if re.search(r"seats\.resolve\([A-Z_]+,\s*n=len\(", src):
                capped.append(name)
    if missing_push:
        defects.append((
            "llm-not-exhausted",
            f"{len(missing_push)} idea-generating organ(s) accept a seat's FIRST answer and stop "
            f"-- {', '.join(missing_push)}. The input context is the expensive half and is "
            "already paid for; a push ladder reuses it and harvests the rest of the seat's "
            "inventory for output tokens only. Use libs.llm.push.push_rounds, which stops on "
            "measured exhaustion rather than a fixed count."))
    if capped:
        defects.append((
            "llm-seats-capped-by-literal",
            f"{len(capped)} organ(s) cap seats at a hardcoded list's LENGTH via "
            f"`n=len(...)` -- {', '.join(capped)}. The desk pays for the whole roster and asks a "
            "fraction of it, and growing the roster does not grow the organ. Build the preferred "
            "list from seats.load_roster() and pass n=None; the literal is a PRIORITY ORDER, not "
            "a membership list."))


VPS_PINS = ROOT / "requirements-vps.txt"


def _pinned() -> dict[str, str]:
    out: dict[str, str] = {}
    with contextlib.suppress(OSError):
        for ln in VPS_PINS.read_text("utf-8").splitlines():
            ln = ln.strip()
            if "==" in ln and not ln.startswith("#"):
                name, _, ver = ln.partition("==")
                out[name.strip().lower()] = ver.strip()
    return out


def check_dependency_drift(defects) -> None:
    """GAP #51: GREEN TESTS HERE ARE NOT EVIDENCE ABOUT PRODUCTION UNLESS THE DEPS MATCH.

    pyproject declares floors (`>=`) while the VPS runs 22 exact pins, so CI resolves whatever is
    newest and production runs something else. The register records this biting once already:
    `ruff>=0.5` resolved to 0.15.8 and produced 36 errors that production never saw.

    Measured 2026-07-29 in the dev container: 18 of 22 packages differ from the pin set, and one
    of them is a MAJOR version -- pandas 2.3.3 in production versus 3.0.5 here. A major version
    is where behaviour changes rather than drifts, so a suite that is green against 3.0.5 says
    very little about a desk running 2.3.3. That is not a hypothetical: `Timestamp.utcnow()`
    raises a removal warning on 3.x and is perfectly quiet on 2.3.3, so the same code produces
    different signals in the two environments.

    MAJOR drift is a defect; minor/patch drift is reported as one line and not escalated, because
    the point is to see divergence, not to forbid a patch bump. Absent packages are listed
    separately -- a dependency production has and the test environment lacks means the tests
    covering it never ran at all.
    """
    import importlib.metadata as md
    pins = _pinned()
    if not pins:
        defects.append(("dependency-pins-missing",
                        f"{VPS_PINS.name} has no exact pins -- production's dependency set is "
                        "unrecorded, so no test run anywhere can be tied to what actually runs."))
        return
    major, minor, absent = [], [], []
    for name, want in sorted(pins.items()):
        try:
            have = md.version(name)
        except Exception:
            absent.append(name)
            continue
        if have == want:
            continue
        if want.split(".")[0] != have.split(".")[0]:
            major.append(f"{name} prod={want} here={have}")
        else:
            minor.append(f"{name} {want}->{have}")
    if major:
        defects.append((
            "dependency-major-drift",
            f"{len(major)} package(s) differ from production by a MAJOR version -- "
            f"{'; '.join(major)}. A major version changes behaviour rather than drifting, so a "
            "green suite in this environment is not evidence about the desk that runs "
            f"{VPS_PINS.name}. Align the environment, or state explicitly which results are "
            "known to be environment-specific."))
    if absent:
        defects.append((
            "dependency-absent",
            f"{len(absent)} pinned package(s) are NOT INSTALLED here -- {', '.join(absent[:8])}. "
            "Any test that needs them did not run, and pytest reports a skipped or uncollected "
            "module far more quietly than a failing one."))
    if minor and not major:
        print(f"  note: {len(minor)} minor/patch dependency drift(s) vs {VPS_PINS.name}")

    # AND THE FLOORS MUST NEVER SIT BELOW PRODUCTION. A `>=` floor lower than the deployed pin
    # lets CI legally resolve a version production has already moved past, so a green run can be
    # testing code paths the desk retired. Raising the floor costs nothing and makes "CI resolved
    # something older than prod" impossible rather than merely unlikely.
    low: list[str] = []
    with contextlib.suppress(OSError):
        pyproj = (ROOT / "pyproject.toml").read_text("utf-8")
        for name, floor in re.findall(r'"([A-Za-z0-9_.-]+)>=([0-9][^"]*)"', pyproj):
            want = pins.get(name.lower())
            if not want:
                continue
            fl = [int(x) for x in re.findall(r"\d+", floor)[:3]]
            wt = [int(x) for x in re.findall(r"\d+", want)[:3]]
            if fl < wt:
                low.append(f"{name} floor>={floor} < prod pin {want}")
    if low:
        defects.append((
            "dependency-floor-below-prod",
            f"{len(low)} pyproject floor(s) sit BELOW the deployed pin -- {'; '.join(low[:6])}. "
            "CI may legally resolve a version production has already moved past, so a green run "
            "can be exercising retired code paths. Raise the floor to the pin."))


def check_naive_datetime(defects) -> None:
    """GAP #50, CORRECTED. Ban the calls that are genuinely naive or scheduled for removal --
    and do NOT count the desk's own correct helper as a defect.

    The register claimed "52 utcnow() calls (deprecated, naive/aware corruption risk)". Verified
    2026-07-29 and the premise is wrong: 30 of the 31 files call `libs.core.time.utcnow`, which
    is `datetime.now(UTC)` -- timezone-aware and correct. The finding came from grepping the
    STRING `utcnow(`, which matches the desk's own fix as readily as the bug it replaced. Acting
    on it would have meant "fixing" 53 correct call sites.

    One instance was real but a different defect: `pd.Timestamp.utcnow()` in compute_performance
    is tz-aware (so never a corruption risk) yet is removed in pandas 4. A scheduled breakage,
    not a correctness bug -- fixed, and pinned here.

    This checks for what actually bites: bare `datetime.utcnow()`, which returns a NAIVE datetime
    that silently compares wrong against every aware timestamp on the desk, and the deprecated
    pandas form. The desk's own helper is explicitly not matched.
    """
    # AST, NOT GREP -- and the reason is this check's own first run: a text scan matched the
    # patterns inside this very docstring and reported 4 defects in the auditor describing the
    # defect. Same shape as the one-hop grep that produced the false orphan-module finding
    # earlier in the same session. Parse the code, do not read the prose.
    import ast
    bad: list[str] = []
    for base in ("libs", "scripts", "app"):
        for p in sorted((ROOT / base).rglob("*.py")):
            rel = p.relative_to(ROOT).as_posix()
            try:
                tree = ast.parse(p.read_text("utf-8", errors="ignore"))
            except (OSError, SyntaxError):
                continue
            for node in ast.walk(tree):
                if not (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)):
                    continue
                if node.func.attr != "utcnow":
                    continue
                owner = getattr(node.func.value, "id", None) or getattr(
                    node.func.value, "attr", None)
                if owner == "datetime":
                    bad.append(f"{rel}:{node.lineno} datetime.utcnow() -> NAIVE")
                elif owner == "Timestamp":
                    bad.append(f"{rel}:{node.lineno} Timestamp.utcnow() -> removed in pandas 4")
    if bad:
        defects.append((
            "naive-datetime",
            f"{len(bad)} call(s) return a naive or soon-removed timestamp -- {'; '.join(bad[:6])}."
            " A naive datetime compares silently wrong against every aware timestamp here, "
            "corrupting forward-clock day counts, 8h funding boundaries and §33 deferral expiry. "
            "Use libs.core.time.utcnow (already correct, already used in 30 files) or "
            "datetime.now(UTC)."))


TEST_RECORD = ROOT / "docs/research/test_suite_record.json"


#: MemAvailable below this is a real risk of the next probe being OOM-killed rather than run. A
#: full pytest collection peaked at 326MB here (R0407b), so a floor at 400MB is "one more probe
#: fits"; 189MB was the reading on the day two consecutive runs were killed.
MEM_FLOOR_MB = 400

#: tmpfs is RAM owned by NO PROCESS, so it appears in no RSS check and is never reclaimed under
#: pressure -- the whole reason this class was invisible. 1021MB (26% of a 3.8GB box) was the
#: orphan pile that closed R0407's loop; 600MB is well below that and well above steady state.
TMPFS_CEILING_MB = 600


def check_host_memory_headroom(defects) -> None:
    """THE MEMORY THAT BELONGS TO NO PROCESS (R0407a). Every other memory check watches RSS.

    `libs/ops/host_resources` was built for R0407 and wired only REACTIVELY -- run_ci and
    max_audit's collection probe call `pressure_note()` to annotate a death that has already
    happened. That makes the instrument a coroner. Nothing on this desk asks the question BEFORE
    the kill, so the closed loop R0407 documented (an OOM-killed run never reaches its own
    cleanup -> its scratch is orphaned -> free RAM falls -> the next run is likelier to be killed)
    still had no detector, only a better autopsy.

    MEASURED WHEN THIS WAS WIRED (2026-08-13): MemAvailable 205MB, 798MB held under /tmp. The
    R0407 prevention (`tmp_path_retention_policy=failed`, 513ba24) worked on the population it
    targeted -- pytest orphans are no longer the bulk -- and the occupancy came back anyway from
    a DIFFERENT population: agent-session scratch and stray research artifacts (a 178MB mentions
    dump, a 63MB CSV, a 63MB probe file). So the fence must watch TOTAL tmpfs occupancy, not
    pytest directories; fixing the one producer that was caught is not the same as watching the
    resource, which is exactly why R0407 left this half open.

    IT REPORTS AND DOES NOT DELETE, deliberately. `/tmp` on this box is shared with the live
    executor, three recorders and several concurrent agent sessions; an automatic reaper here
    would race a sibling's scratch mid-run, and destroying another process's working state to
    reclaim memory is a larger failure than the one it fixes. The actionable half is carried in
    the message: the exact command, the two numbers, and which threshold was crossed.

    UNMEASURED IS A DEFECT, NOT SILENCE (L1.28a). A box whose /proc cannot be read is not a box
    with plenty of memory. `None` from `tmpfs_used_mb` is kept distinct from `0`: it means /tmp
    is not a tmpfs here, so there is no hidden RAM to report -- a different fact, not a low
    reading, and folding them together would invent pressure on a normal disk-backed host.
    """
    from libs.ops.host_resources import mem_available_mb, tmpfs_used_mb

    avail = mem_available_mb()
    tmp_mb = tmpfs_used_mb()
    where = "check tmpfs occupancy with `du -sm /tmp/* | sort -rn | head`"

    if avail is None:
        defects.append((
            "host-memory-unmeasured",
            "MemAvailable could not be read from /proc/meminfo, so host memory headroom is "
            "UNMEASURED this cycle. That is not a clean bill: the OOM class this check exists "
            "for (R0407) is invisible by construction to every RSS-based check on the desk, so "
            "an unreadable /proc leaves it invisible again. Confirm /proc is mounted."))
        return

    # S108 guards against WRITING predictable paths into a world-writable dir; these are message
    # strings about a mount this check only reads, same exemption as libs/ops/host_resources.
    tmp_note = (
        "/tmp is not a tmpfs on this host (no RAM hidden there)"  # noqa: S108
        if tmp_mb is None else f"{tmp_mb}MB of RAM held by files under /tmp (tmpfs)")

    if avail < MEM_FLOOR_MB:
        defects.append((
            "host-memory-low",
            f"MemAvailable is {avail}MB, below the {MEM_FLOOR_MB}MB floor -- {tmp_note}. A full "
            f"pytest collection peaks near 326MB here, so the next probe is a coin-flip against "
            f"the OOM killer, and a killed probe reports as a broken test suite (R0407b). This "
            f"is memory no RSS check can see. First move: {where}; free the largest entries that "
            f"no live process owns, NEVER by deleting another session's scratch blind."))

    if tmp_mb is not None and tmp_mb > TMPFS_CEILING_MB:
        defects.append((
            "host-tmpfs-bloated",
            f"{tmp_mb}MB of RAM is held by files under /tmp, above the {TMPFS_CEILING_MB}MB "
            f"ceiling (MemAvailable {avail}MB). tmpfs pages are resident memory owned by no "
            f"process: they are never reclaimed under pressure and never appear in a process "
            f"memory check. R0407's prevention fixed pytest's orphans specifically; occupancy "
            f"returning from other producers is the same resource going unwatched. "
            f"{_tmpfs_holders_note()} {where}."))


def _desk_owned_worktrees() -> dict[str, str]:
    """Realpath -> registered path, for THIS repo's own git worktrees living outside the repo.

    THE ONE PRODUCER THE NOTE ASKS FOR AND NEVER SUPPLIED. `_tmpfs_holders_note` closes by
    telling the reader that "age plus a known producer is the evidence to act on" -- and then
    names no producer, so the reader has to establish ownership by hand at the exact moment the
    box is short of memory. Measured 2026-08-13: /tmp held 838MB against a 600MB ceiling, and
    150MB of it was a detached checkout at /tmp/wt-head that THIS REPO had registered 6.5h
    earlier and abandoned. Establishing that took `git worktree list`, a read of the entry's
    `.git` pointer, a diff of its one dirty artifact against the main tree, and a holder scan.
    The fence had already computed the size, the age and the holder, and stopped one fact short
    of the one that actually decides the deletion.

    A REGISTERED WORKTREE IS OWNERSHIP EVIDENCE, which is precisely what a bare directory under
    a shared /tmp does not carry. It is a checkout of a COMMITTED sha of this repo, so reclaiming
    it destroys no unique work unless the tree is dirty -- and `git worktree remove` refuses a
    dirty tree by itself, which is why the command named below is the plain one and never
    `--force`. The reader who needs `--force` is then making that call knowingly.

    THE FENCE STILL DELETES NOTHING. Naming a reclaimable entry and reaping it are different
    acts, and only the second can race a live sibling: an agent session's `git worktree add`
    (which CLAUDE.md itself instructs, in preference to `git stash`) holds no descriptor while
    the model is thinking, so "no holder" cannot distinguish an abandoned checkout from one
    between commands. Age plus ownership is evidence for a HUMAN decision, not a licence to
    automate one -- the same reason `libs/ops/host_resources` reports and does not reap.

    Best-effort: a repo without git, or a git that errors, yields no attribution and the note
    degrades to exactly what it printed before.
    """
    try:
        r = subprocess.run(["git", "worktree", "list", "--porcelain"], cwd=ROOT,
                           capture_output=True, text=True, timeout=30, check=False)
    except (OSError, subprocess.SubprocessError):
        return {}
    if r.returncode != 0:
        return {}
    main = os.path.realpath(str(ROOT))
    owned: dict[str, str] = {}
    for line in r.stdout.splitlines():
        if not line.startswith("worktree "):
            continue
        p = line.split(" ", 1)[1].strip()
        rp = os.path.realpath(p)
        if rp != main:                      # the main checkout is the desk, not its scratch
            owned[rp] = p
    return owned


def _tmpfs_holders_note() -> str:
    """The largest /tmp entries with the one fact that makes freeing them a safe decision.

    THE FENCE STAYS A REPORTER AND THE REPORT BECOMES ACTIONABLE. It still deletes nothing --
    `/tmp` is shared with the live executor, three recorders and several agent sessions, and an
    automatic reaper racing a sibling's scratch is a worse failure than the one it fixes. What
    changes is that the reader no longer has to redo the investigation by hand under memory
    pressure: the entries, their ages and whether anything live holds them are IN the defect.

    HELD-BY-NOTHING IS NEVER ASSERTED FROM A PARTIAL SCAN. Most pids on this box are unreadable,
    so an unheld-looking entry is reported as "holder unknown", never as safe. The coverage
    fraction is printed so the reader can price the verdict instead of trusting it.
    """
    from libs.ops.host_resources import fd_scan_coverage, tmpfs_top_holders

    rows = tmpfs_top_holders()
    if not rows:
        return ""
    readable, total = fd_scan_coverage()
    seen = f"{readable}/{total} pids' descriptors readable" if total else "no pid table readable"
    owned = _desk_owned_worktrees()
    parts = []
    n_owned = 0
    for r in rows:
        holder = ("HELD by a live process" if r.held
                  else "held by nothing" if r.held is False else "holder UNKNOWN")
        # A lawgate checkout registers at <entry>/t while the entry itself is what holds the RAM,
        # so ownership is matched by CONTAINMENT, not equality: the reclaim command has to name
        # the registered path and the size next to it is the whole subtree's.
        target = os.path.realpath(r.path).rstrip("/")
        mine = [reg for rp, reg in sorted(owned.items())
                if rp == target or rp.startswith(target + "/")]
        own = ""
        if mine:
            n_owned += 1
            own = f" DESK-OWNED git worktree -- reclaim: git worktree remove {mine[0]}"
        parts.append(f"{r.path} {r.mb}MB {r.age_h:.0f}h {holder}{own}")
    # THE ATTRIBUTION SENTENCE IS CONDITIONAL, and that is not cosmetic. Printed unconditionally
    # it appears on every firing including the ones where nothing is reclaimable, so the reader
    # cannot tell from the message whether the desk owns any of the pile -- which is the single
    # question it was added to answer. Its presence IS the signal.
    tail = ("" if not n_owned else
            f" {n_owned} of these are DESK-OWNED: this repo registered them, each is a checkout "
            f"of a committed sha, and `git worktree remove` refuses one whose tree is dirty -- "
            f"the one class the reader can free without first reconstructing where it came from.")
    return (f"Largest entries: {'; '.join(parts)}. Holder scan saw {seen}, so 'holder UNKNOWN' "
            f"means NOT CHECKABLE from here, never 'safe to delete' -- age plus a known producer "
            f"is the evidence to act on.{tail}")


def check_test_suite_collectable(defects) -> None:
    """THE SUITE MUST ACTUALLY RUN, AND MUST NOT SHRINK. Coverage theater in its purest form.

    FOUND 2026-07-29, THE HARD WAY. `tests/risk/*` imports `hypothesis` and `tests/regime`
    imports `sklearn`, neither installed here. pytest does not skip a module it cannot import --
    it raises a COLLECTION ERROR and aborts the ENTIRE session with "Interrupted: 5 errors during
    collection". So `pytest tests/` ran ZERO tests. Not five files' worth: zero. And hiding
    behind that were two genuinely failing tests on the LIVE EXECUTION path -- the fill-
    verification regression bar for the 2026-07-19 dead-man incident that stranded ~$2,150.

    A suite that has silently stopped running is worse than no suite, because it is still cited
    as evidence. This desk's own doctrine is PRODUCTION, NOT EXIT CODE; a test suite is subject
    to exactly the same rule, and nothing was applying it to the tests themselves.

    Two teeth: collection must SUCCEED, and the collected count is RATCHETED. The ratchet is the
    important half -- a suite can rot one deleted file at a time without ever failing, and
    "tests pass" stays true the whole way down.

    A THIRD STATE, ADDED 2026-08-05 (R0407b). `rc != 0` folded a probe the KERNEL KILLED into a
    collection error, and the two have nothing in common. A negative returncode means this child
    never finished collecting anything, so the message below -- "install the missing dependency"
    -- named a dependency that does not exist and sent the reader hunting a test failure that was
    never there. Measured twice on 2026-08-05: rc=-9 raised `test-suite-uncollectable` with an
    EMPTY `why` list, while a full collection seconds later returned rc=0 in 19s at 326MB peak.
    The box is a 3.8GB swapless VPS shared with the live daemons and several agent sessions, and
    `/tmp` is a tmpfs, so the scratch of a previous run is itself resident RAM (513ba24).

    NOTHING IS LOOSENED BY THE SPLIT. A killed probe still raises a defect -- on a safety gate
    "unknown" reads as NOT-PROVEN-GREEN, never as fine -- and it is never re-run, because
    re-running a memory-killed probe under the same pressure doubles the shortage it is reporting
    (the same rule run_ci.py's HUNG and KILLED branches already follow). What changes is only what
    the alarm SAYS, and that the ratchet's silence is now stated out loud instead of being an
    invisible early return: a partial count from a truncated run would fire a FALSE
    `test-suite-shrank`, so the honest report is that the count is UNMEASURED this cycle.
    """
    from libs.ops.host_resources import pressure_note

    r = subprocess.run([sys.executable, "-m", "pytest", "tests/", "--collect-only", "-q"],
                       cwd=str(ROOT), capture_output=True, text=True, timeout=300, check=False)
    out = (r.stdout or "") + (r.stderr or "")
    if r.returncode < 0:
        defects.append((
            "test-suite-probe-killed",
            f"the collection probe was KILLED by signal {-r.returncode} before it could report "
            f"({pressure_note()}). This is a verdict on the BOX, not on the tests: nothing here "
            "says a single test is broken, and re-running it under the same pressure would only "
            "double the shortage. It still counts as a defect because an unmeasured suite is "
            "NOT a green one. Two consequences to act on: the collected-module ratchet could not "
            "be evaluated this cycle, so a genuine suite shrink would be invisible right now; and "
            "the first move is to free host memory (check tmpfs occupancy under /tmp -- it is RAM "
            "no process owns) and re-run when the box is quiet, NOT to hunt a failing test."))
        return
    # LINE-ANCHORED, not substring (2026-08-18). `"error" in out.lower()` was welded ON the day
    # tests/execution/test_spot_live_error_detail.py was added (172d6ea7): the FILENAME contains
    # "error", so a perfectly green rc=0 collection raised test-suite-uncollectable every cycle --
    # the substring-fence-satisfied-by-a-name failure, on the fence guarding the suite itself.
    # Real pytest collection errors are line-anchored ("ERROR tests/...", "==== ERRORS ====") or
    # the phrase "N error(s) during collection"; a path component can satisfy neither.
    collect_err = re.search(r"(?m)^(?:=+ )?ERRORS?\b|errors? during collection",
                            out.split("short test summary")[0])
    if r.returncode != 0 or collect_err:
        why = [ln for ln in out.splitlines()
               if re.match(r"^(?:=+ )?ERRORS?\b", ln) or "ModuleNotFound" in ln][:4]
        defects.append((
            "test-suite-uncollectable",
            f"pytest cannot COLLECT the suite (rc={r.returncode}) -- "
            f"{' | '.join(why) or out[-300:]}"
            ". A collection error aborts the WHOLE session, so this is not 'some tests skipped', "
            "it is ZERO TESTS RUN while the desk still cites the suite as evidence. Install the "
            "missing dependency or guard the import with pytest.importorskip, which is what "
            "tests/research/test_stationarity.py already does correctly."))
        return

    n = sum(1 for ln in out.splitlines() if ln.strip().startswith("tests/") and ":" in ln)
    try:
        rec = json.loads(TEST_RECORD.read_text("utf-8"))
    except (OSError, json.JSONDecodeError):
        rec = {}
    best = int(rec.get("max_collected", 0))
    if n > best:
        TEST_RECORD.parent.mkdir(parents=True, exist_ok=True)
        TEST_RECORD.write_text(json.dumps({
            "max_collected": n, "at": datetime.now(tz=UTC).isoformat(),
            "note": "high-water mark of COLLECTABLE test modules; ratchets UP only. A suite may "
                    "never quietly shrink -- deleting a test is a decision, not a side effect.",
        }, indent=1), "utf-8")
    elif n < best:
        defects.append((
            "test-suite-shrank",
            f"collectable test modules fell to {n} from a high-water {best}. Tests are the only "
            "thing standing between a refactor and a silent regression, and a suite shrinks one "
            "deleted file at a time while 'tests pass' stays true the entire way down. Restore "
            f"them, or record in {TEST_RECORD.relative_to(ROOT)} why the coverage is legitimately "
            "gone."))


#: Triage registers excluded from §35 because they disposition their own items inline. The
#: exclusion is only honest while that stays TRUE, so it is checked rather than trusted.
_TRIAGE_DOCS = ("docs/research/SUBSYSTEM_TRIAGE.md", "docs/research/TRIAGE_ADDENDUM.md")
_TRIAGE_VERDICTS = ("BUILT", "BUILD", "QUEUE", "REJECT")
#: BUILD/QUEUE are OPEN work. An exclusion that let them vanish would be the bypass the scope
#: check exists to prevent, so they are counted back out loud.
_TRIAGE_OPEN = ("BUILD", "QUEUE")

#: Miner session logs excluded from §35 on the SAME premise as _TRIAGE_DOCS -- they disposition
#: their own items inline, with a `[§33: ...]` tag rather than a verdict heading. The premise is
#: what the exclusion rests on, so it is checked (check_dig_log_disposition) rather than trusted.
_SELF_DISPOSING_DIG_LOGS = ("docs/research/prospector_coverage.md",)
#: PRESENCE probe for the §33 inline tag. Deliberately only the OPENER: the parser of record is
#: ``libs.research.mine_conversion._DISP_RE`` and duplicating its full grammar here would be a
#: second parser to keep in sync (the desk has been bitten by exactly that). Tolerant of
#: "S33"/"section 33" for the same reason the real parser is -- an ASCII-only writer still counts.
_DIG_TAG_RE = re.compile(r"\[(?:§|S|section\s*)33:", re.IGNORECASE)


def check_triage_disposition(defects) -> None:
    """§35(8): the triage registers are excluded from the findings scan ONLY while they still
    disposition their own items -- and their OPEN items stay counted, not hidden.

    WHY THIS EXISTS AT ALL. Excluding a doc from §35 is the cheapest possible way to make 101
    obligations disappear, and it leaves no diff anyone reviews. So the exclusion reason
    ("every numbered item carries a BUILT/BUILD/QUEUE/REJECT verdict in the doc") is written as a
    TESTABLE CLAIM rather than a comment. Add item #102 with no verdict and this fires; the
    exclusion cannot quietly decay into a bypass.

    THE SECOND HALF IS THE POINT. BUILT and REJECT are terminal, but BUILD and QUEUE are open
    work. An exclusion that let those vanish would defeat the scope check it is registered
    against, so they are surfaced with their counts and their blockers. Excluded from §35 is a
    statement about WHICH instrument governs them -- never a statement that nothing does.
    """
    # ONE NUMBERING SPACE, TWO FILES. The addendum continues the register at #82, and its
    # blockers cite items verdicted in the other file. Reading each doc in isolation made the
    # stale-blocker scan miss #93-waits-on-17 on its first run, because 17 is BUILT "elsewhere".
    # Parse everything first, judge second.
    parsed: dict[str, tuple[str, dict[str, list[str]], list[str]]] = {}
    for rel in _TRIAGE_DOCS:
        p = ROOT / rel
        if not p.exists():
            defects.append((
                "triage-doc-missing",
                f"§35(8): {rel} is excluded from the findings scan on the grounds that it "
                "dispositions its own items -- and it is GONE. Deleting the register deletes "
                "the audit trail of every verdict in it. Restore it or supersede it by name."))
            continue
        parsed[rel] = (p.read_text("utf-8"), {}, [])

    built_global: set[str] = set()
    for text, seen_out, undisposed_out in parsed.values():
        current: str | None = None
        seen_out.update({v: [] for v in _TRIAGE_VERDICTS})
        for line in text.splitlines():
            if line.startswith("#"):
                head = line.lstrip("# ").strip().upper()
                current = next((v for v in _TRIAGE_VERDICTS if head.startswith(v)), None)
                continue
            m = re.match(r"\|\s*(\d+)\s*\|", line)
            if not m:
                continue
            if current is None:
                undisposed_out.append(m.group(1))
            else:
                seen_out[current].append(m.group(1))
        built_global |= set(seen_out["BUILT"])

    for rel, (text, seen, undisposed) in parsed.items():

        if undisposed:
            defects.append((
                "triage-item-undisposed",
                f"§35(8): {Path(rel).name} carries {len(undisposed)} numbered item(s) under NO "
                f"verdict heading -- #{', #'.join(undisposed[:10])}. The doc is excluded from the "
                "§35 findings scan PRECISELY because it dispositions its own items; an item with "
                "no verdict is governed by nothing at all. Give it a BUILT/BUILD/QUEUE/REJECT "
                "verdict, or move the doc into _FINDING_DOCS so §35 takes it."))

        # STALE BLOCKERS. A QUEUE verdict is a claim that something else must land first, and that
        # claim expires silently the moment the dependency ships -- nobody revisits a blocked item
        # to ask whether it is still blocked. Found on its first run: #93 was queued behind
        # "Information Advantage Score (BUILD item 17) existing first", and 17 is now BUILT.
        stale: list[str] = []
        if built_global:
            current = None
            for line in text.splitlines():
                if line.startswith("#"):
                    head = line.lstrip("# ").strip().upper()
                    current = next((v for v in _TRIAGE_VERDICTS if head.startswith(v)), None)
                    continue
                m = re.match(r"\|\s*(\d+)\s*\|", line)
                if current != "QUEUE" or not m:
                    continue
                dep = {d for d in re.findall(r"item\s+(\d+)", line, re.I) if d in built_global}
                if dep:
                    stale.append(f"#{m.group(1)} (waits on now-BUILT #{', #'.join(sorted(dep))})")
        if stale:
            defects.append((
                "triage-blocker-stale",
                f"§35(8): {Path(rel).name} has {len(stale)} QUEUE item(s) whose named blocker has "
                f"SHIPPED -- {'; '.join(stale[:6])}. A blocker is a claim with an expiry date and "
                "nobody re-reads a blocked row to check it. Re-verdict them BUILD (unblocked) or "
                "restate the real blocker; leaving them queued is how finished dependencies keep "
                "work frozen indefinitely."))

        openwork = {v: seen[v] for v in _TRIAGE_OPEN if seen[v]}
        if openwork:
            parts = ", ".join(f"{v}={len(ids)} (#{', #'.join(ids[:6])})"
                              for v, ids in openwork.items())
            defects.append((
                "triage-open-items",
                f"§35(8): {Path(rel).name} still carries OPEN triage items -- {parts}. These are "
                "excluded from §35 (the doc dispositions them) but they are not DONE: BUILD is "
                "unblocked work nobody has done, QUEUE is blocked work whose blocker must still "
                "be true. Ship them, or re-verdict them with the reason. Visible-and-open beats "
                "invisible-and-forgotten -- that asymmetry is why this reports rather than "
                "stays quiet."))


def check_artifact_governance(defects) -> None:
    """§36(2): EVERY artifact is claimed by a law -- so the miner problem cannot reappear anywhere.

    §33 governs mined cards, §35 governs findings, §36 governs cadenced producers. Each closed the
    same failure on its own surface, one surface at a time -- which is a losing game, because the
    NEXT artifact arrives ungoverned by default and nobody notices until it has rotted. This
    inverts it: every docs/ markdown must be claimed by some law, or explicitly recorded as
    terminal WITH A REASON. An unclaimed artifact is the miner problem waiting to happen, and it
    now fires on the day it appears rather than months later.
    """
    claimed = (set(_DIG_DOCS) | set(_DIG_DOCS_EXCLUDED) | set(_FINDING_DOCS)
               | set(_FINDING_DOCS_EXCLUDED) | set(_PRODUCER_CADENCE) | set(_TERMINAL_ARTIFACTS))
    # A trailing-slash claim governs a whole DIRECTORY CLASS. Generators (the weekly deep sweep)
    # emit dated instances forever, so exact-path claims could never keep up and the check would
    # fire permanently on correctly-governed output. Claim the class once; instances inherit it.
    claimed_prefixes = tuple(c for c in claimed if c.endswith("/"))
    audit_src = ""
    with contextlib.suppress(OSError):
        audit_src = Path(__file__).read_text("utf-8")
    cands = [p.relative_to(ROOT).as_posix() for p in sorted((ROOT / "docs").rglob("*.md"))]
    # GITIGNORED PATHS ARE NOT ARTIFACTS (2026-07-28). This walked docs/ raw, so locally-generated
    # scratch that git is explicitly told to ignore (docs/audit_shards/shard_*.md) was demanded to
    # carry a governance claim. Those files do not exist on a clean checkout, which made this check
    # -- and the CI test that asserts on it -- ENVIRONMENT-DEPENDENT: red on the box that generated
    # the scratch, green on a runner that never did. A gate whose verdict depends on which machine
    # ran it cannot be trusted in either direction. Governance applies to what is COMMITTED.
    with contextlib.suppress(OSError, subprocess.SubprocessError):
        ig = subprocess.run(["git", "check-ignore", "--stdin"], cwd=ROOT, input="\n".join(cands),
                            capture_output=True, text=True, timeout=20)
        if ig.returncode in (0, 1):        # 0 = some ignored, 1 = none ignored; 128 = no git
            skip = {ln.strip() for ln in ig.stdout.splitlines() if ln.strip()}
            cands = [c for c in cands if c not in skip]
    cands = _committed_only(cands)      # untracked WIP is not yet an artifact OF this repo
    unclaimed = []
    for rel in cands:
        if (rel in claimed or rel.startswith(claimed_prefixes)
                or rel.endswith("GAP_REGISTER.md")):
            continue
        if Path(rel).name in audit_src:      # named by some other check -- already governed
            continue
        unclaimed.append(Path(rel).name)
    if unclaimed:
        defects.append((
            "artifact-ungoverned",
            f"§36(2): {len(unclaimed)} docs artifact(s) claimed by NO law -- "
            f"{', '.join(unclaimed[:8])}. Every artifact is governed by §33 (mined cards), §35 "
            "(findings), §36 (cadenced producers), or recorded terminal with a reason. Ungoverned "
            "is how the miner problem reappears: inventory accumulates and nothing ever converts "
            "it. Classify each -- 'no law' must be a DECISION, never a default."))


def check_findings_tracked(defects) -> None:
    """EVERY FINDING MUST REACH THE LOOP THAT DRIVES IT (§35).

    The register is the desk's only organ that DRIVES work: weekly re-rank, 7-day staleness,
    escalation. Every other doc is a place findings are WRITTEN. The daily cycle acts on the
    register, so a finding absent from it is not merely slow -- it is invisible, and however
    carefully it was found it will never be worked.

    Generalises check_review_risks_tracked, which enforced this for THREE HARDCODED KEYS and so
    could only ever catch risks somebody remembered to hardcode -- the same brittleness one level
    up. Matching is deliberately generous (one distinctive token is enough): a false accept is
    cheap, a false alarm trains the reader to ignore the check, and an ignored check is worse than
    no check because it looks like coverage.
    """
    from libs.research.finding_registry import coverage_report, parse_findings

    gr = ROOT / "docs/GAP_REGISTER.md"
    if not gr.exists():
        return
    register = gr.read_text("utf-8")
    findings = []
    for rel in _FINDING_DOCS:
        p = ROOT / rel
        if p.exists():
            with contextlib.suppress(OSError):
                findings += parse_findings(p.read_text("utf-8"), source=rel)
    if not findings:
        return
    rep = coverage_report(findings, register)
    if rep.n_untracked:
        defects.append((
            "findings-untracked",
            f"§35: {rep.n_untracked}/{rep.n_open} open finding(s) have NO GAP_REGISTER trace "
            f"({rep.coverage:.0%} coverage) -- {'; '.join(rep.untracked_names)}. The daily cycle "
            "works the register; a finding that never lands there is invisible to it forever. "
            "Add a row (mechanism, trigger, owner) or record it as closed -- being written down "
            "somewhere is not the same as being driven."))


#: TRACKED (docs/, not gitignored data/) -- a coverage floor stored where `rm` resets it is not a
#: floor. In git, a reset shows in `git status`, in the diff, and in check_dig_uncommitted.
FINDINGS_RECORD = ROOT / "docs/research/findings_coverage_record.json"


def check_findings_ratchet(defects) -> None:
    """§35(7): coverage holds at 100% and the FLOOR ONLY RISES -- over a scope that cannot shrink.

    A one-off 100% is a snapshot. The law needs a floor, and the floor needs an honest denominator:
    the cheapest way to reach 100% is not to row the findings but to SHRINK THE DENOMINATOR --
    exclude a doc from scope, or delete the finding. Same loophole §34 closed for mining (fake a
    conversion rate by mining less), closed the same way: coverage, open-finding count and
    docs-scanned all ratchet UP together, and a worse cycle produces a defect rather than a
    relaxed bar.
    """
    from libs.research.finding_registry import (
        CoverageRatchet,
        coverage_report,
        parse_findings,
        update_coverage_ratchet,
    )

    gr = ROOT / "docs/GAP_REGISTER.md"
    if not gr.exists():
        return
    findings, n_docs = [], 0
    for rel in _FINDING_DOCS:
        p = ROOT / rel
        if p.exists():
            n_docs += 1
            with contextlib.suppress(OSError):
                findings += parse_findings(p.read_text("utf-8"), source=rel)
    if not findings:
        return
    rep = coverage_report(findings, gr.read_text("utf-8"))

    prior = CoverageRatchet()
    with contextlib.suppress(Exception):
        prior = CoverageRatchet.model_validate_json(FINDINGS_RECORD.read_text("utf-8"))
    new, verdict = update_coverage_ratchet(
        prior, rep, n_docs=n_docs, at=datetime.now(UTC).isoformat())
    with contextlib.suppress(OSError):
        FINDINGS_RECORD.parent.mkdir(parents=True, exist_ok=True)
        FINDINGS_RECORD.write_text(new.model_dump_json(indent=2), "utf-8")

    if verdict.scope_shrank:
        defects.append(("findings-scope-shrank", f"§35(7): {verdict.verdict}"))
    if verdict.coverage_regressed:
        defects.append(("findings-coverage-regressed", f"§35(7): {verdict.verdict}"))
    if rep.coverage < 1.0 and not verdict.coverage_regressed:
        defects.append((
            "findings-coverage-below-100",
            f"§35(7): {verdict.verdict} The standing target is 100% -- every finding the desk has "
            "made reaches the loop that drives it, or is recorded closed. Anything less means the "
            "cycle is provably blind to work it already knows about."))


def check_findings_scope(defects) -> None:
    """The finding-scan's own scope is audited -- a new findings doc must not appear unmonitored.

    Same shape as check_mine_scope: a fixed doc list is the check's blast radius, and a finding
    written outside it evades §35 with no code change and no diff. Every docs/ markdown carrying
    numbered findings must be in scope or excluded WITH A REASON; never decided by omission.
    """
    from libs.research.finding_registry import parse_findings

    # TRAILING-SLASH CLASS CLAIMS (2026-07-26). check_artifact_ungoverned already honours these,
    # with a comment stating exactly why: generators emit dated instances forever, so exact-path
    # claims "could never keep up and the check would fire permanently on correctly-governed
    # output". This sibling check never got the same treatment, so `docs/research/deep_sweep/` --
    # excluded WITH a stated reason since it was written -- was never actually excluded here, and
    # every weekly sweep report re-fired findings-scope-unmonitored. The defect was therefore
    # UNCLOSABLE by construction: the only way to satisfy it was to list files that do not exist
    # yet. A convention honoured by one check and ignored by its sibling in the same file is the
    # generalise-the-rule blind spot; the two now read the claims the same way.
    _excluded_prefixes = tuple(c for c in _FINDING_DOCS_EXCLUDED if c.endswith("/"))
    rogue = []
    for p in sorted((ROOT / "docs").rglob("*.md")):
        rel = p.relative_to(ROOT).as_posix()
        if (rel in _FINDING_DOCS or rel in _FINDING_DOCS_EXCLUDED
                or rel.startswith(_excluded_prefixes) or rel.endswith("GAP_REGISTER.md")):
            continue
        with contextlib.suppress(OSError):
            n = len(parse_findings(p.read_text("utf-8"), source=rel))
            if n >= 5:  # a handful of numbered lines is prose; a pile of them is a findings doc
                rogue.append(f"{p.name}({n})")
    if rogue:
        defects.append((
            "findings-scope-unmonitored",
            "§35 scope: doc(s) carrying numbered findings outside the scan -- "
            f"{', '.join(rogue[:6])}. Findings written there owe no register row and are "
            "invisible to §35 -- a bypass needing no code change and leaving no diff. Add to "
            "_FINDING_DOCS or _FINDING_DOCS_EXCLUDED with a stated reason."))


#: Day-over-day collapse thresholds for the live book. Deliberately loose: this catches a book
#: LOSING ITSELF, not ordinary rebalancing. A tight bar here would fire on every rotation and be
#: acknowledged into silence, which is worse than no check.
_BOOK_EQUITY_DROP = 0.10       # 10% marked equity in one day
_BOOK_CARRY_DROP = 0.50        # half the positions gone in one day


def check_book_collapse(defects) -> None:
    """The book losing most of itself overnight must be LOUD. Nothing watched this.

    On 2026-07-26 concurrent carries went 10 -> 2 and deployed notional fell 30% in a single day,
    and no organ said a word: the desk had checks for idle code, mining regression and stale
    findings, and none for its own positions vanishing. Either the executor unwound eight carries
    or a state file was truncated -- both are things you want to hear about the same morning, and
    the second one silently corrupts every downstream number that reads the book.

    Reads the attestation chain only, so it works from the record rather than from live venue
    access, and stays quiet on a single row (no prior day = nothing to compare).
    """
    rows = []
    with contextlib.suppress(Exception):
        for line in (ROOT / "data/nav_attestation.jsonl").read_text("utf-8").splitlines():
            if line.strip():
                rows.append(json.loads(line))
    if len(rows) < 2:
        return
    prev, cur = rows[-2], rows[-1]

    def _f(row, key):
        try:
            return float(row.get(key) or 0.0)
        except (TypeError, ValueError):
            return 0.0

    p_eq, c_eq = _f(prev, "equity_marked"), _f(cur, "equity_marked")
    if p_eq > 0 and (p_eq - c_eq) / p_eq > _BOOK_EQUITY_DROP:
        defects.append((
            "book-equity-collapse",
            f"marked equity fell {(p_eq - c_eq) / p_eq:.0%} in one day "
            f"(${p_eq:,.0f} -> ${c_eq:,.0f}) on {cur.get('date')}. Past the "
            f"{_BOOK_EQUITY_DROP:.0%} bar -- establish whether this is P&L or a bad read BEFORE "
            "any number derived from the book is trusted again."))

    p_n, c_n = int(_f(prev, "n_carries")), int(_f(cur, "n_carries"))
    if p_n >= 4 and c_n < p_n * (1.0 - _BOOK_CARRY_DROP):
        defects.append((
            "book-carries-collapse",
            f"concurrent carries fell {p_n} -> {c_n} on {cur.get('date')} (deployed "
            f"${_f(prev, 'deployed_notional'):,.0f} -> ${_f(cur, 'deployed_notional'):,.0f}). "
            "Either the executor unwound most of the book or the position state was truncated. "
            "The second is silent and corrupts every downstream figure -- confirm which."))

    p_r, c_r = _f(prev, "realized_spot_pnl"), _f(cur, "realized_spot_pnl")
    if p_r > 0 and c_r < p_r:
        defects.append((
            "book-realized-pnl-fell",
            f"REALIZED spot P&L fell ${p_r:,.2f} -> ${c_r:,.2f} on {cur.get('date')}. Realized "
            "P&L is banked and should only ratchet up; a fall means the accounting is being "
            "restated, which is a data-integrity problem rather than a trading loss."))



#: §33's ratchets bind on the desk's own history. Below this many records that history is noise,
#: and a ratchet calibrated on noise blocks real work for no reason.
_MINE_RATCHET_MIN_RECORDS = 10


def check_mine_evidence_base(defects) -> None:
    """A ratchet calibrated on two observations is superstition with a JSON file.

    §33's conversion ratchet, latency-regression bound and tier weights all bind against
    best-ever values. Those are meaningful once there is a distribution and meaningless before:
    with n=2, a single fast conversion sets a "best median latency" that every future cycle is
    then held to. The machinery is orders of magnitude heavier than the evidence under it.

    This does not weaken the ratchet -- it reports when the ratchet is running ahead of its own
    evidence base, so a bar that starts biting can be read as "too few observations" rather than
    "the desk got worse".
    """
    n = 0
    with contextlib.suppress(Exception):
        n = int(json.loads(
            (ROOT / "docs/research/conversion_record.json").read_text("utf-8"))["n_records"])
    if 0 < n < _MINE_RATCHET_MIN_RECORDS:
        defects.append((
            "mine-ratchet-thin-evidence",
            f"§33 ratchets are binding on {n} record(s), under the {_MINE_RATCHET_MIN_RECORDS} "
            "needed for a distribution. Best-ever latency and conversion rate set from a handful "
            "of observations are noise the desk then holds itself to forever. Treat §33 bars as "
            "ADVISORY until the base is real -- and do not tighten them on this evidence."))


#: One-shot scripts that legitimately ran once and are kept for provenance. Anything NOT listed
#: here must be reachable, so the exemption is a written decision rather than a silent default.
_ONESHOT_SCRIPTS = frozenset({
    # classified 2026-08-27: R0574's decisive study -- does the Kelly estimation shrink already
    # absorb the best-of-12 PROMOTION winner's curse? It answers ONE question about the sizer's
    # bias on a fixed body of evidence; re-running it on unchanged history re-derives the same
    # verdict, so a cadence would buy nothing and would make a settled question look perpetually
    # open. Its answer belongs in the ledger, not in a timer.
    "study_promotion_selection_bias.py",
    "backfill_onchain_oos.py", "batch_onchain.py", "batch_premium.py", "build_dev_factor.py",
    "dl_metrics_history.py", "pull_cme.py",
    # classified 2026-07-31 (orphan-scripts sweep):
    "collect_bitmex_funding.py",   # phase-1 decade ingest, ran 07-31 -> data/bitmex_funding.jsonl
                                   # (11,148 rows); forward funding comes from the live collectors,
                                   # phase-2 tranche runner is rowed separately
    "flatten_cookie.py",           # principal-approved COOKIEUSDT incident tool, ran once 07-28
    "hl_filter_test.py",           # elite-trader premise experiment (kernel of the 26-layer spec
    "screen_smart_dumb.py",        # decision) -- both ran once, verdicts recorded in data/hl_*.log
    "verify_fixes.py",             # dated live-code verification of the a1bcd86 fixes, ran once
    # classified 2026-08-01: R0069's named DECISIVE EXPERIMENT -- a one-shot full-depth panel
    # backfill whose whole purpose is to settle one axis permanently. It ran and produced
    # reports/axis_screens/kr_perasset_premium_depth.json (38 assets, 84,891 asset-days). A
    # decisive experiment is by definition not a cadence: re-running it on unchanged history
    # would re-test dead ground and burn multiplicity budget for nothing.
    "screen_kr_perasset_depth.py",
    # classified 2026-08-06: R0266's named STUDY, whose whole purpose was to answer one sizing
    # question before any wiring -- and it answered DO NOT WIRE (boundary shrink <=10% at the
    # desk's real barrier, an order of magnitude under the estimation shrink already applied).
    # Verdict banked in docs/research/absorbing_kelly_study.json (committed 92cb529); no sizer,
    # rail or bar changed, which is exactly why nothing imports it. It is a SIMULATION over a
    # parameter grid, not a reader of desk state, so a cadence would re-derive a settled number
    # from unchanged inputs. NOT a hidden orphan: R0431 rows the one follow-up that would re-run
    # it (multi-year horizons, to confirm the 1y framing is what inverted the sign), and that is
    # a re-run of the same decisive experiment rather than a schedule.
    "study_absorbing_kelly.py",
    # classified 2026-08-12 ON THE DAY IT WAS WRITTEN (4c578e58), which is the point: R0345
    # PRE-REGISTERED this falsifier in its own text ("measure disposition latency for compound
    # versus atomic rows -- if compound rows do NOT age longer, this hypothesis is wrong"), and
    # this script ran it BEFORE the admission-control build R0345 proposed. It refuted the
    # hypothesis (p=0.93; compound rows are 6% of the ledger and cannot explain a 200-row backlog
    # at any effect size), so the build was correctly NOT made and the backlog was re-diagnosed as
    # a burst STOCK rather than a flow imbalance. A pre-registered falsifier is a decisive
    # experiment, not a cadence: re-running it on the same ledger re-derives a settled number, and
    # re-running it on a CHANGED ledger would answer a different question than the one registered.
    # Its verdict is the durable artifact; the script is the transcript of how it was reached.
    "check_row_atomicity.py",
    # classified 2026-08-12 (orphan-scripts defect): the OI/LS universe metrics BACKFILL half of
    # work order oi-ls-universe-metrics-backfill. Ran to completion 2026-08-12T01:35Z ->
    # data/oi_ls_universe.jsonl (365 symbols, 256,625 rows, every symbol current to the archive
    # edge 2026-08-10) + data/oi_ls_universe_coverage.json. The FORWARD feed is
    # collect_oi_ls_live.py's cadence, so a schedule here would re-download a static public
    # archive daily. Idempotent and resumable by design: a future listing-gap fill is a manual
    # re-invocation of the same script, not a cadence.
    "dl_metrics_universe.py",
    # classified 2026-09-05 (birth-property boundary, the orphan-scripts sweep of the 08-28..09-04
    # seat builds). Both are ANALYSES whose only input that can move -- completed forward
    # evidence -- does not exist yet: optimise_prop_settings' own docstring records ZERO
    # completed forward windows and recommends waiting for the first cohort rather than picking
    # a row; compare_book_growth measured 1-4 forward days per sleeve on 2026-09-01 and labels
    # its ranking a backtest PRIOR. A cadence would re-derive the same conditional tables from
    # unchanged evidence and make a settled "not yet" look perpetually open. Each is re-run by
    # hand when the first forward cohort completes, with its result banked in the ledger.
    "optimise_prop_settings.py",
    "compare_book_growth.py",
})


#: Path literals that are legitimately absent -- each with the reason, so "known gap" is
#: distinguishable from "nobody noticed". Anything not here and not on disk is a phantom.
_PHANTOM_ALLOWED = {
    "data/principal_replies.jsonl": "the principal's reply channel -- absent because he has not "
                                    "replied yet, not because nothing writes it. Its emptiness is "
                                    "itself the signal several organs read.",
    "data/mining_suspended": "a FLAG file: present only while §33 backlog is owed. Absence is the "
                             "healthy state, and creating it would suspend mining.",
    "data/LIVE_ENABLE": "arming flag -- absence is the safe state by design.",
    "data/kill_switch": "rail flag -- absence is the healthy state.",
    # OPERATOR-SUPPLIED CREDENTIALS. These are never written by desk code by design -- a repo that
    # can WRITE its own secrets is a repo that can leak them. They are placed by hand (or by the
    # deploy) and are gitignored, so "no writer in the tree" is the correct and intended state.
    # Their absence is a FUNDING/PROVISIONING fact, already surfaced by the organs that need them
    # (alert_channels degrades to log-only; the KR collector reports its key as missing).
    "data/secrets/alert_channels.json": "operator-provisioned credential; desk code must never "
                                        "write a secret, and its absence is reported by the "
                                        "alert channel itself as degraded delivery.",
    "data/secrets/binance_live_spot.json": "operator-provisioned live spot credential -- absence "
                                           "is the SAFE state and is what keeps the spot leg "
                                           "un-armed until a human provisions it.",
    "data/secrets/naver.json": "operator-provisioned free NAVER API key (GAP #69, unclaimed). "
                               "The KR collector reports the missing key rather than failing.",
}

#: Extensions worth auditing: durable stores a reader can be wrong about. Logs are excluded --
#: they are written by redirection from cron, not by python, so they would all read as phantoms.
_PHANTOM_EXTS = (".json", ".jsonl", ".db", ".sqlite", ".csv", ".pkl", ".parquet")

def check_phantom_paths(defects) -> None:
    """READ-WITHOUT-WRITER: a path some organ reads that NOTHING on this desk ever writes.

    THE DESK'S MOST PROLIFIC DEFECT CLASS, and it had no detector. A reader pointed at a path no
    producer creates does not crash -- it takes the empty/missing branch and returns a plausible
    zero, so the organ reports HEALTHY on data that does not exist. Live instances found by hand
    rather than by any fence: data/research_memory.db had FOUR readers and no writer and sat in
    the moat backup's store list, where it recorded ABSENT on every run and padded the denominator
    so 4/4 coverage read as 4/6; cost_ratio, slippage_ks_p and calibration_mae_falling_months were
    ramp step-up conditions with zero producers anywhere while the ramp sat pinned at its floor.

    THE TEST IS DELIBERATELY NARROW so it does not cry wolf. A path is a phantom only if it is
    referenced in code, does NOT exist on disk, AND no line anywhere pairs it with a write verb.
    A path that exists is fine (something made it, whatever that was). A path with a writer is
    fine (it will exist when the producer runs). Logs are out of scope entirely -- cron writes
    them by shell redirection, so every one would read as a phantom and the check would be
    switched off within a week.
    """
    # RESOLVED FROM THE SYNTAX TREE (R0356). This was a line-text scan, and a path in Python is an
    # EXPRESSION -- `_ROOT / "data" / "x.json"` is invisible to any regex needing `data/` inside one
    # string, in the READ position as much as the write position. Measured on this tree: swapping
    # the textual scan for libs/research/path_refs resolved 12 reported paths (7 by finding the
    # writer, 5 by recognising a provenance LABEL that opens nothing) and surfaced 12 genuine
    # read-without-writers it had never been able to see. One of those was
    # `data/trade_forensics.json`, read by run_exec_monitor while the producer writes
    # `web/trade_forensics.json` -- the desk's most prolific defect class, sitting unreported
    # inside its own detector because the read was a split literal.
    root = ROOT
    found = path_refs.scan(root)
    refs = found.reads
    phantoms = found.phantoms(root, allowed=set(_PHANTOM_ALLOWED))
    if phantoms:
        shown = "; ".join(f"{p} (read by {', '.join(sorted(refs[p])[:2])})" for p in phantoms[:5])
        defects.append((
            "phantom-paths",
            f"READ-WITHOUT-WRITER: {len(phantoms)} path(s) are read by code, do NOT exist on "
            f"disk, and NOTHING writes them: {shown}{'...' if len(phantoms) > 5 else ''}. A "
            "reader on a phantom path does not crash -- it takes the empty branch and reports a "
            "plausible zero, so the organ reads HEALTHY on data that was never produced. Point "
            "the reader at the real store, build the producer, or record the path in "
            "_PHANTOM_ALLOWED with the reason it is legitimately absent."))


def check_orphan_scripts(defects) -> None:
    """§36: a SCRIPT nothing runs is an orphan too -- and the orphan check could not see it.

    `check_orphan_code` walks the import graph from `scripts/` as its ROOTS, so "is this script
    itself reached by anything?" was unaskable by construction. The blind spot was exactly the
    shape of scripts/: on 2026-07-26 eight scripts were written and wired to nothing, including
    `page_digest.py`, which describes itself as a daily job and was absent from the daily cycle.

    Reachability is generous on purpose -- the cycle, any other script, any lib, CI config, or a
    documented runbook all count. What is left is genuinely unreferenced, and a one-shot that
    honestly ran once belongs in `_ONESHOT_SCRIPTS` with that stated, not in silence.
    """
    import re
    sdir, corpus = ROOT / "scripts", []
    if not sdir.exists():
        return
    for pat in ("scripts/*.py", "libs/**/*.py", "*.md", "docs/**/*.md", "ops/*",
                "*.toml", "*.yml", "*.yaml", "*.sh", ".github/**/*"):
        for f in ROOT.glob(pat):
            # THIS FILE IS EXCLUDED. Naming a script in the checker's own prose must not exempt
            # it -- the first version described `page_digest.py` in this very docstring and
            # thereby marked it reachable. A checker that launders its examples into passes is
            # the same false-negative class as the one-hop orphan check it replaced.
            #
            # AUDIT REPORTS ARE EXCLUDED FOR THE SAME REASON, one file wider (found 2026-07-30 by
            # this check's own test going red). A deep-sweep report DESCRIBES orphans; it does not
            # wire them. 20260730_research-engine.md:786 reads "scripts/page_digest.py: grep -> no
            # hits" -- the report correctly IDENTIFIED the orphan, and writing that sentence down
            # made this detector count it as referenced and fall silent. Diagnosing a problem must
            # never be what silences its detection, or the desk's own audits become the thing that
            # hides the findings.
            # docs/audit_shards/ excluded 2026-07-31, third instance of the same class: the
            # sharded audit dossiers QUOTE orphan findings verbatim ("scripts/page_digest.py:
            # no hits"), and that quotation silenced this very detector for a day.
            if (f.is_file()
                    and f.name not in ("daily_research_cycle.py", "max_audit.py")
                    and "deep_sweep" not in f.as_posix()
                    and "audit_shards" not in f.as_posix()):
                with contextlib.suppress(OSError):
                    corpus.append(f.read_text("utf-8", errors="ignore"))
    cycle = set(re.findall(r'"scripts/([a-z_0-9]+\.py)"',
                           (sdir / "daily_research_cycle.py").read_text("utf-8", errors="ignore")))
    # ONE PASS OVER THE CORPUS, NOT ONE PER SCRIPT (2026-08-12). This ran
    # `re.search(rf"scripts/{name}|scripts\.{stem}\b|\b{stem}\b", blob)` for EVERY script, i.e.
    # ~500 full scans of a multi-megabyte blob: 91.6s of check_orphan_scripts' 91.7s, and the
    # dominant term in max_audit's whole runtime. That cost is why this check could only ever
    # live on a daily cron -- at 90s it cannot be a push gate, and a law with no boundary is a
    # law enforced periodically (L1.37).
    #
    # THE REWRITE IS AN IDENTITY, NOT AN APPROXIMATION, and the argument is the only reason it is
    # safe to touch a detector this load-bearing: `\b` is defined against exactly [A-Za-z0-9_],
    # so `\bSTEM\b` matches iff STEM appears as a MAXIMAL run of those characters -- which is
    # precisely membership in the token set below. The two other alternatives are strict
    # subcases: `scripts/foo.py` and `scripts.foo` both contain `foo` as a maximal token (`/` and
    # `.` are not word characters), so neither can match where the third does not. Verified
    # empirically against the old implementation over the real repo before landing: identical
    # verdicts on all 496 scripts.
    #
    # A stem that is not a pure identifier (a dash, a dot) would break that equivalence, because
    # `\b` could then match across a boundary the tokenizer split. Those keep the original regex
    # -- correctness first, and they are rare enough that the speed is unaffected.
    # MEMORY IS THE OTHER HALF OF "AFFORDABLE AT A BOUNDARY", and it nearly deleted this fence on
    # its first wiring: `re.findall` over the joined corpus materialises a LIST of every token in
    # the repo -- ~6M short strings at ~50B of object overhead each -- which peaked at 621MB RSS
    # on a 3.8GB box with 616MB free. The law gate's subprocess came back rc=-9: the OOM killer,
    # reported as "no output". Streaming per file with `finditer` keeps only the UNIQUE tokens
    # (a few hundred thousand), and the 45MB joined blob is never built unless something actually
    # needs it. A fence that dies under memory pressure is indistinguishable from a fence that
    # passed, which is the worst of the available failure modes (L1.28a).
    tokens: set[str] = set()
    for _text in corpus:
        tokens.update(mm.group() for mm in re.finditer(r"[A-Za-z0-9_]+", _text))
    # A sibling session's uncommitted script is not an orphan of this repo -- see _committed_only.
    committed = set(_committed_only([f"scripts/{f.name}" for f in sdir.glob("*.py")]))
    cands = [f for f in sorted(sdir.glob("*.py"))
             if f.name not in cycle and f.name not in _ONESHOT_SCRIPTS
             and f.name != "daily_research_cycle.py" and f"scripts/{f.name}" in committed]
    # The joined blob exists ONLY for the non-identifier fallback, which is empty in practice.
    blob = ("\n".join(corpus)
            if any(not re.fullmatch(r"[A-Za-z0-9_]+", f.stem) for f in cands) else "")
    dead = []
    for f in cands:
        if re.fullmatch(r"[A-Za-z0-9_]+", f.stem):
            referenced = f.stem in tokens
        else:
            stem = re.escape(f.stem)
            referenced = bool(
                re.search(rf"scripts/{re.escape(f.name)}|scripts\.{stem}\b|\b{stem}\b", blob))
        if not referenced:
            dead.append(f.name)
    if dead:
        defects.append((
            "orphan-scripts",
            f"§36: {len(dead)} script(s) referenced by NOTHING -- not the daily cycle, not another "
            f"script, not a lib, not CI, not a runbook: {', '.join(dead[:8])}"
            f"{'...' if len(dead) > 8 else ''}. check_orphan_code treats scripts/ as its ROOTS, so "
            "it cannot see these. Wire each into a cadence, add it to _ONESHOT_SCRIPTS with the "
            "reason it ran once, or delete it -- built-and-forgotten must not look like finished."))
    if (sdir / "test_review_fixes.py").exists():
        defects.append((
            "test-outside-test-tree",
            "scripts/test_review_fixes.py is a test file living outside tests/, so pytest never "
            "collects it. Move it to tests/ or rename it -- a test that never runs is worse than "
            "no test, because it reads as coverage."))


#: Every doc that can carry a numbered law. A number must identify ONE law across all of them.
_LAW_DOCS = ("docs/DIGGING_CHARTER.md", "ops/principal_doctrine.txt")


def check_law_numbers_unique(defects) -> None:
    """A law number must name exactly one law. Nothing enforced that, and it collided.

    On 2026-07-26 two accounts independently wrote a §38 and a §39 for DIFFERENT laws, hours
    apart on separate branches; it surfaced only because the merge conflicted. A citation to
    "§39" then resolves to whichever copy the reader happens to open, which is §36's
    no-ungoverned-artifact rule failing at the citation layer -- the law numbers themselves were
    the ungoverned artifact.

    Reports the next free number too, so allocating one is a lookup rather than a guess.
    """
    import re
    from collections import defaultdict
    titles: dict[int, set[str]] = defaultdict(set)
    for rel in _LAW_DOCS:
        path = ROOT / rel
        if not path.exists():
            continue
        text = path.read_text("utf-8", errors="ignore")
        for num, title in re.findall(r"^##\s*(\d+)\.\s*([^\n(]{4,60})", text, re.M):
            titles[int(num)].add(title.strip().rstrip("—-").strip().upper()[:40])
    clashes = {n: ts for n, ts in titles.items() if len(ts) > 1}
    if clashes:
        detail = "; ".join(f"§{n} claimed by {len(ts)}: {' | '.join(sorted(ts))}"
                           for n, ts in sorted(clashes.items()))
        defects.append((
            "law-number-collision",
            f"§36: {detail}. A citation to one of these resolves to whichever copy the reader "
            "opens. Renumber the later law -- the trunk keeps the number it landed with."))
    if titles:
        nxt = max(titles) + 1
        marker = ROOT / "docs/research/next_law_number.txt"
        # THIS NUMBER IS A HIGH-WATER MARK AND WAS BEING RECOMPUTED AS A CURRENT READING (GAP 113).
        # Measured 2026-08-13: a full pytest run drove it 60 -> 43, because `_LAW_DOCS` entries
        # that are absent or unreadable on a given host are SKIPPED above -- so the max falls with
        # them and the file confidently hands the next two laws a number already in use, which is
        # the exact collision it exists to prevent.
        #
        # A RATCHET, NOT A HOST GUARD, deliberately: allocation must never go backwards on ANY
        # host, including this one after a doc is renamed or temporarily unreadable. Reading the
        # existing value costs one open and makes the write correct everywhere rather than correct
        # only where a marker happens to be stamped.
        try:
            prev_txt = marker.read_text("utf-8").strip().split("\n", 1)[0]
            nxt = max(nxt, int(prev_txt) if prev_txt.lstrip("-").isdigit() else nxt)
        except (OSError, ValueError):
            pass                                   # no prior mark: this reading is the first one
        with contextlib.suppress(OSError):
            marker.parent.mkdir(parents=True, exist_ok=True)
            marker.write_text(
                f"{nxt}\n\nNext free law number, recomputed every sweep by "
                f"max_audit.check_law_numbers_unique. Two accounts collided on 38/39 on "
                f"2026-07-26 because allocation was a guess; read this file instead of guessing.\n",
                "utf-8")


def check_orphan_code(defects) -> None:
    """MAP-vs-TERRITORY (audit 2.x): the desk flags idle DATA/capital/clocks but not idle CODE.
    Flags library packages that are almost entirely unreachable from any scripts/ entry point --
    e.g. libs/backtest (the independent cross-check engine) applied to zero strategies. Bounded:
    reports only near-fully-orphaned packages to stay cheap and low-noise."""
    libs = ROOT / "libs"
    scripts = ROOT / "scripts"
    if not (libs.exists() and scripts.exists()):
        return
    # TRANSITIVE reachability. The old proxy checked only DIRECT imports in scripts/, so a package
    # reached through one hop -- scripts -> libs.research.listing_events -> libs.features.labels --
    # was reported as idle while being genuinely run. A check that cries wolf gets acknowledged
    # into silence, which costs more than the check ever earned, and it under-reported too: a
    # package imported ONLY by another orphan is still an orphan and used to look reachable.
    import re

    def _pkgs_in(text: str) -> set[str]:
        return set(re.findall(r"\blibs\.([a-z_][a-z0-9_]*)", text))

    pkg_text: dict[str, str] = {}
    for d in libs.iterdir():
        if d.is_dir() and (d / "__init__.py").exists():
            with contextlib.suppress(OSError):
                pkg_text[d.name] = "\n".join(
                    f.read_text("utf-8", errors="ignore") for f in d.rglob("*.py"))

    reached: set[str] = set()
    # ENTRY POINTS ARE scripts/ + app/ + api/, and the walk is RECURSIVE. Two bugs lived here:
    # a non-recursive glob (a package reached only from scripts/sub/x.py read as orphaned) and a
    # root set one directory too narrow -- _module_reachability() 70 lines below already declares
    # the production frontier as ("scripts", "app", "api"), so ONE file held two reachability
    # walkers that disagreed. That disagreement produced a live false positive: stage14(13
    # modules) is reached by scripts/check_readiness.py -> app/readiness.py -> libs.stage14.engine
    # (which calls PortfolioConstructionEngine().construct), and nothing under scripts/ mentions
    # libs.stage14 textually. Widening the roots REMOVES a false accusation; it cannot hide a real
    # orphan, because adding entry points can only ever grow `reached`.
    entry_text: list[str] = []
    for entry in ("scripts", "app", "api"):
        d = ROOT / entry
        if not d.is_dir():
            continue
        entry_text.extend(f.read_text("utf-8", errors="ignore") for f in d.rglob("*.py"))
    frontier = _pkgs_in("\n".join(entry_text))
    while frontier:                       # BFS from the entry points, not a single hop
        nxt = frontier.pop()
        if nxt in reached or nxt not in pkg_text:
            continue
        reached.add(nxt)
        frontier |= _pkgs_in(pkg_text[nxt]) - reached

    suspicious = []
    for pkg in sorted(d for d in libs.iterdir() if d.is_dir() and (d / "__init__.py").exists()):
        name = pkg.name
        mods = [m.stem for m in pkg.glob("*.py") if m.stem != "__init__"]
        if len(mods) < 3 or name in reached:
            continue
        suspicious.append(f"{name}({len(mods)} modules)")
    if suspicious:
        defects.append(("orphan-code",
                        "library package(s) unreachable from ANY scripts/ entry point, "
                        "directly or transitively (idle code -- "
                        f"the class never monitored): {', '.join(suspicious[:6])}. Wire the "
                        "safeguard (e.g. libs/backtest cross_engine) or retire on the record -- "
                        "verify against dynamic imports before deleting."))


#: Modules on the MONEY PATH: the ones where "built, tested green, called by nobody" stops being
#: untidy and becomes a safety defect. Every one of these must be reachable from a production
#: entry point, because an S1 desk whose rails have never executed outside pytest has no rails.
#: This list is deliberately short. `check_orphan_code` is package-granular and could not see any
#: of it: libs/execution is reachable via ea_bridge, so staging.py sat orphaned inside a "live"
#: package for 8 days -- imported by its own test and nothing else -- while the register carried
#: the connector as PARTIAL and the audit reported clean.
_MONEY_PATH_MODULES = (
    "libs.execution.staging",
    "libs.execution.binance_live",
    "libs.execution.binance_spot_live",
    "libs.execution.protective_stops",
    "libs.execution.canary",
    "libs.execution.ramp_gate",
    "libs.ops.derisk_ladder",
    "libs.risk.gate",
    "libs.risk.sizing",
)


def _module_reachability() -> tuple[set[str], dict[str, str]]:
    """Transitive MODULE-level reachability from production entry points (scripts/, app/, api/).

    Package granularity is the blind spot this replaces: asking "is libs.execution used?" answers
    yes forever while any one module in it is imported, which is why a dead stage machine inside
    a live package was invisible. Tests are NOT entry points -- being imported by your own test
    is exactly the condition under audit.
    """
    import re

    mods: dict[str, str] = {}
    for f in (ROOT / "libs").rglob("*.py"):
        if f.stem == "__init__":
            continue
        with contextlib.suppress(OSError):
            mods[".".join(f.relative_to(ROOT).with_suffix("").parts)] = \
                f.read_text("utf-8", errors="ignore")

    def _refs(text: str) -> set[str]:
        out = {"libs." + m.group(1) for m in re.finditer(r"\blibs\.([a-z0-9_.]+)", text)}
        # `from libs.execution import staging` names the module in the IMPORT list, not the path
        for m in re.finditer(r"from\s+(libs[a-z0-9_.]*)\s+import\s+([^\n(]+)", text):
            for n in m.group(2).split(","):
                token = n.strip().split(" ")[0]
                if token:
                    out.add(f"{m.group(1)}.{token}")
        return out

    frontier: set[str] = set()
    for entry in ("scripts", "app", "api"):
        d = ROOT / entry
        if d.exists():
            for f in d.rglob("*.py"):
                with contextlib.suppress(OSError):
                    frontier |= _refs(f.read_text("utf-8", errors="ignore"))

    reached: set[str] = set()
    init_memo: dict[str, set[str]] = {}

    def _init_refs(pkg: str) -> set[str]:
        if pkg not in init_memo:
            out: set[str] = set()
            init = ROOT / Path(pkg.replace(".", "/")) / "__init__.py"
            if init.exists():
                with contextlib.suppress(OSError):
                    out = _refs(init.read_text("utf-8", errors="ignore"))
            init_memo[pkg] = out
        return init_memo[pkg]

    while frontier:
        n = frontier.pop()
        if n in reached:
            continue
        reached.add(n)
        if n in mods:
            frontier |= _refs(mods[n]) - reached
        # Python executes EVERY ancestor package __init__ on submodule import
        # (`from libs.pkg.sub import X` runs libs/__init__.py AND libs/pkg/__init__.py), so a
        # re-export sitting in an ancestor init is EXECUTED code, not a token import. The old
        # walk read only n's OWN init, so every module loaded solely via a package re-export
        # was flagged orphan -- measured 2026-08-19: 20 of 50 census rows were this class.
        # The blind spot this walker was built for is preserved: a dead module merely INSIDE
        # a live package (the execution.staging case) is still orphan unless some executed
        # init or module names it.
        parts = n.split(".")
        for k in range(1, len(parts) + 1):
            frontier |= _init_refs(".".join(parts[:k])) - reached
    return reached, mods


def check_decision_ledger_matures(defects) -> None:
    """The self-improvement loop must have a QUEUE, not just a cadence.

    The ledger's policy promises "the monthly governance review scores each matured entry so
    decision QUALITY compounds". Measured 2026-07-26: 189 decisions, 2 scored, and 175 with no
    review date at all -- nothing could mature, so the monthly review ran against an empty queue
    and correctly reported no work. A cadence pointed at an empty queue looks identical to a
    cadence with nothing to do, which is why this went unnoticed for the ledger's whole life.
    """
    try:
        from datetime import date as _date

        from libs.research.decision_review import health as _health
        doc = json.loads((ROOT / "data" / "decision_ledger.json").read_text("utf-8"))
    except (OSError, json.JSONDecodeError, ImportError):
        return
    rows = doc.get("decisions", []) if isinstance(doc, dict) else doc
    rows = [r for r in rows if isinstance(r, dict)]
    if not rows:
        return
    h = _health(rows, _date.today())  # noqa: DTZ011 -- calendar date for a filename/stamp, never compared to an instant
    if h.no_review_date:
        defects.append((
            "decision-ledger-undated",
            f"{h.no_review_date} of {h.total} logged decisions carry NO review date -- they can "
            "never come due, so the scoring cadence has nothing to pull and reports clean "
            "forever. Run scripts/run_decision_review.py to derive them."))
    elif h.due:
        defects.append((
            "decision-ledger-unscored",
            f"{h.due} decision(s) matured and unscored, oldest {h.oldest_overdue_d}d past due "
            f"({h.scored}/{h.total} = {h.scored_pct}% ever scored). Scoring is a JUDGEMENT and is "
            "never automated -- see data/decision_review.json for the worklist."))


def check_money_path_wired(defects) -> None:
    """Every money-path module must have a PRODUCTION caller, not just a test.

    This is the §36 orphaned-artifact failure in the one place it can cost the whole book, and
    it is checked structurally -- "is there a path from an entry point to this module" -- rather
    than by naming a caller, so it survives the callers being renamed or moved.
    """
    reached, mods = _module_reachability()
    missing = [m for m in _MONEY_PATH_MODULES if m in mods and m not in reached]
    absent = [m for m in _MONEY_PATH_MODULES if m not in mods]
    if missing:
        defects.append((
            "money-path-orphaned",
            f"money-path module(s) with NO production caller -- reachable only from their own "
            f"tests: {', '.join(missing)}. A rail that has never executed outside pytest is not "
            "a rail; wire it into an entry point (see scripts/run_live_guard.py) or delete it "
            "and stop counting it as built."))
    if absent:
        defects.append((
            "money-path-module-missing",
            f"money-path module(s) named by the guard but absent from the tree: "
            f"{', '.join(absent)}. A moved or deleted file must not silently make this check "
            "blind to wherever the logic went."))


def check_orphan_modules(defects) -> None:
    """Census of individually-unreachable libs MODULES (informational, not a wall of noise).

    Reported as a single number rather than 60-odd names on purpose: the package-level check
    stays the blocking one for whole idle subsystems, this tracks the long tail so it cannot
    grow unnoticed, and `check_money_path_wired` is what actually blocks. A check that prints a
    list nobody can action gets acknowledged into silence and takes the useful ones with it.
    """
    reached, mods = _module_reachability()
    orphans = sorted(m for m in mods if m not in reached)
    if len(orphans) > _ORPHAN_MODULE_BUDGET:
        defects.append((
            "orphan-modules",
            f"{len(orphans)} of {len(mods)} libs modules are unreachable from any production "
            f"entry point (budget {_ORPHAN_MODULE_BUDGET}). Newest offenders: "
            f"{', '.join(orphans[:5])}. Wire or retire -- the budget ratchets DOWN as the "
            "backlog is worked off, never up."))


#: Ratchet for the module-orphan census. 67 -> 66 when run_live_guard.py wired the stage machine
#: and connectors back in; 66 -> 49 when run_alpha_factory.py gave the seventeen research engines
#: a production caller; 49 -> 45 when lockbox/fdr/cpcv/baselines were wired into the promotion
#: path; 45 -> 29 when the walker learned Python's real import semantics (ancestor package
#: __init__ files EXECUTE on submodule import -- 20 census rows were re-exports the walk could
#: not see), market_impact_forecaster + stage15.errors were retired dead, and drawdown_metrics
#: was wired into compute_performance. Lower this as the backlog clears; raising it to make the
#: check pass is the one edit that defeats its purpose.
_ORPHAN_MODULE_BUDGET = 29


#: Docs where mined finds ACCUMULATE UN-DISPOSITIONED -- the only place §33 inventory can rot.
#: Deliberately excluded, each for a reason (the check must flag rot, not paperwork):
#:   graveyard.md              -- a graveyard entry IS a disposition; terminal by construction
#:   negative_knowledge.md     -- own terminal schema (``[priority: ...] review-due: <date>``)
#:   search_operator_library.md-- own terminal schema (``[status: active|watch|archived]``)
#:   prospector_watchlist.md   -- prose STEP headers, not carded finds
#: RE-DERIVED 2026-08-06 (R0269) BY MEASUREMENT, not by intent. Three of the four paths that used
#: to sit here parsed to ZERO items -- `_ITEM_RE` wants `### N. <name>` and none of them writes
#: that shape -- so §33 was measuring ONE doc and reporting it as the desk's whole mining surface.
#: Listing a path is not counting it. They are moved to _DIG_DOCS_EXCLUDED with their real
#: lifecycles below, and `check_mine_scope_vacuous` now fails if this list ever again contains a
#: path whose content the parser cannot see.
_DIG_DOCS = (
    "docs/research/data_axis_watchlist.md",
)
#: Card-bearing docs deliberately OUT of §33 scope, each with its reason. Kept explicit so the
#: scope check below can tell "consciously excluded" from "quietly unmonitored".
_DIG_DOCS_EXCLUDED = {
    "docs/research/mt5_source_seeds.md":
        "A SEED MAP, not a card-bearing find doc, and the distinction is the point: the catalogue "
        "(data_axis_watchlist.md, which IS in _DIG_DOCS) carries graded cards that owe "
        "verification decisions, and the desk's measured bottleneck is verification, not "
        "cataloguing. A seed map carries no verification debt, so it can hold hundreds of grounds "
        "without making that bottleneck worse -- a source only becomes a card by producing "
        "something, and the card is where the §33 disposition then lives. Tagging seeds as well "
        "would be a second bookkeeping system over the same item (the feed_inbox precedent). "
        "Claimed by L1.52 (information mining is permanently active) per its ARTIFACT_GOVERNANCE "
        "row. It REPLACED crypto_source_seeds.md / offbook_source_seeds.md, deleted under the "
        "MT5 universe mandate; the structure carried over, the grounds did not, and the rename is "
        "why this claim was briefly missing.",
    "docs/research/COINM_CONVEXITY_PREREGISTRATION.md":
        "PRE-REGISTRATION record: its card-shaped blocks CITE data_axis_watchlist cards 98/99 "
        "(card 31's split), which live -- and owe their dispositions -- in the watchlist, which "
        "IS in _DIG_DOCS. A §33 tag here would be a second bookkeeping system over the same "
        "cards; the THREE_MECHANISM_PREREGISTRATION precedent verbatim",
    "docs/research/ELITE_QUANT_INTELLIGENCE_MANDATE.md":
        "PERMANENT STANDING POLICY: its card-shaped blocks are mandate specifications of WHAT to "
        "mine (source classes, seat duties), not mined finds. A find produced UNDER this mandate "
        "is carded where the miner writes (the watchlist / session docs), which are in scope; "
        "the mandate itself can never be 'disposed'",
    "docs/research/feed_inbox.md":
        "A QUEUE with a process-then-DELETE protocol stated in its own header, not a card-bearing "
        "find doc. The collector appends '## <title>' entries; the CRO triages them, routes what "
        "survives to a watchlist card / graveyard row / ledger row, and DELETES the entry. So an "
        "entry's disposition is its ABSENCE, and a §33 tag on it would be a second bookkeeping "
        "system over the same item -- the improvement_inbox precedent. It sat in _DIG_DOCS from "
        "2026-07 to 2026-08-06 and contributed exactly ZERO items the whole time (27 entries, 0 "
        "parsed), so the 'now a measured, fenced number' claim in R0269 was true in scope and "
        "false in effect. The count is now genuinely measured by check_feed_inbox_backlog below",
    "docs/research/discovery_hypotheses.md":
        "Charter §22 hypothesis register with its OWN lifecycle and its own disposition field: "
        "'### DH-<nnn> <hypothesis> [status: open|validated|falsified]'. A DH entry is a "
        "hypothesis about WHERE information lives, resolved by evidence rather than by a dig "
        "disposition, and it is permanent once falsified. Demanding a §33 tag as well would "
        "double-charge one backlog to two laws",
    "docs/research/literature_coverage.md":
        "A COVERAGE MAP -- a rotation table of literature families with last-visited dates and "
        "yield, plus dated session notes. Its headings are sessions, not finds; the finds those "
        "sessions produced were carded to the watchlist or graveyarded at the time. Nothing here "
        "owes a disposition because nothing here IS a find",
    "docs/research/THREE_MECHANISM_PREREGISTRATION.md":
        "PRE-REGISTRATION document (2026-08-04), not mined finds: its three cards are study "
        "designs named IN ADVANCE precisely so the trial count is honest, and each lives the "
        "pre-registration -> run -> verdict lifecycle, not the dig -> disposition one. Card 1 "
        "(funding carry) is the deployed sleeve; the cascade/basis studies are ledgered "
        "BLOCKED-OPERATOR on the VPS transport gap the doc itself documents (:9-31). Rowing "
        "the cards against §33 would double-charge one backlog to two laws -- the "
        "improvement_inbox precedent",
    "docs/research/micro_audit_inbox.md":
        "audit findings, not mined finds -- own rotting-findings check",
    "docs/research/deep_review_inbox.md":
        "RAW ADVERSARIAL-MODEL REVIEW TRANSCRIPT, not mined finds. deep_review.py appends each "
        "seat's verbatim response over the money-path files; its numbered items are unverified "
        "model CLAIMS about code that already exists, never SOURCES or data axes, so they have "
        "no dig -> disposition lifecycle to owe. The claim -> verify -> accept path is "
        "scripts/track_findings.py, named in the file's own header and demonstrably used for "
        "this content (F0024, F0025 -> R0401). Same class as panel_inbox.md directly below",
    "docs/research/panel_inbox.md": "external panel output -- own rulings/scoring loop",
    "docs/research/PREMORTEM_20260805.md":
        "already in _FINDING_DOCS as of 2026-08-05, so 35 drives every item in it. Counting the "
        "same panel findings against 33 as well would double-charge one backlog to two laws and "
        "depress both conversion rates -- the improvement_inbox precedent directly below",
    "docs/research/ADVERSARIAL_REVIEW_RUBRIC.md":
        "a rubric of DEFECT CLASSES, not mined finds. Each 'card' defines a recurring failure "
        "shape with the real instance that produced it -- reference material a reviewer reads "
        "BEFORE looking at code. A class is permanent and cannot be 'disposed'; the instances it "
        "cites were rowed when they were found. Governed by 36 via _PRODUCER_CADENCE",
    "docs/research/improvement_inbox.md":
        "already in _FINDING_DOCS, so 35 drives every item in it. Counting the same cards against "
        "33 as well would double-charge one backlog to two laws and make both conversion rates "
        "wrong -- the same precedent as blind_rediscovery_log.md. Its items are improvements "
        "owing a RECOMMENDATION row, not dig finds owing a screen",
}
#: Committed-state is checked over the whole research surface, including the excluded docs above:
#: a graveyard entry is self-dispositioning but still has to reach git to exist.
_DIG_TRACKED = ("docs/research", "docs/graveyard.md")
#: Written when the backlog is non-empty; every ops/run_*_dig.sh refuses to start while it exists.
MINING_SUSPENDED = ROOT / "data/mining_suspended"


def _conversion_artifacts() -> list[str]:
    """Names the desk can CORROBORATE on disk -- the artifact-only credit set for §33.

    Mirrors ``_converted_axes``: a conversion is credited from things that exist (a collector's
    output, a reconstructed-OOS report, a screened axis in research memory), never from a claim in
    a document. An organ does not grade its own homework.
    """
    names: set[str] = set()
    with contextlib.suppress(Exception):
        names.update(_converted_axes())
    for pat in ("data/*.jsonl", "data/batch_*.json", "reports/reconstructed_oos/*.json"):
        with contextlib.suppress(Exception):
            names.update(p.stem.lower() for p in ROOT.glob(pat))
    for pat in ("scripts/collect_*.py", "scripts/backfill_*.py"):
        with contextlib.suppress(Exception):
            names.update(p.stem.replace("collect_", "").replace("backfill_", "").lower()
                         for p in ROOT.glob(pat))
    return sorted(n for n in names if n)


MINE_LEDGER = ROOT / "data/mine_conversion_log.jsonl"
#: TRACKED on purpose (docs/, not gitignored data/). The ratchet's whole guarantee is that the
#: bar never loosens -- stored under data/* it was one `rm` from a fresh record, so the monotonic
#: standard was erasable by an organ that wanted an easier bar. In docs/ a reset shows up in
#: `git status`, in the diff, and in check_dig_uncommitted. Tampering becomes visible, not silent.
MINE_RATCHET = ROOT / "docs/research/conversion_record.json"
#: Machine-local snapshot count. Deliberately under data/ (gitignored): how many times THIS
#: machine ran the sweep is not an institutional fact, and committing it dirtied the tree on
#: every run while making the truncation test compare a clone against the VPS's count.
MINE_RATCHET_LOCAL = ROOT / "data/mine_ratchet_local.json"
MINE_PRIORS = ROOT / "data/mine_generation_priors.json"


def _mine_thresholds() -> dict[str, Any]:
    """§33 bars, evidence-adjustable within hard tighten-only bounds (the desk's ThresholdBook)."""
    out = {"kill": 0.60, "stale": 14.0, "regress": 1.5}
    try:
        from libs.self_improvement.adaptive_thresholds import ThresholdBook
        b = ThresholdBook(ROOT / "data/adaptive_thresholds.json")
        out = {"kill": b.get("mine_kill_share_bar"),
               "stale": b.get("mine_stale_owing_days"),
               "regress": b.get("mine_latency_regress_mult")}
    except Exception:
        pass
    return out


def _mine_items():
    """Parse every owing carded find, tiered against the axes the desk has ALREADY ingested."""
    from libs.research.mine_conversion import parse_dispositions
    from libs.research.source_backlog import parse_watchlist
    axes = []
    with contextlib.suppress(Exception):
        axes = _acquired_axes()
    items = []
    for rel in _DIG_DOCS:
        p = ROOT / rel
        if not p.exists():
            continue
        with contextlib.suppress(Exception):
            text = p.read_text("utf-8")
            found = parse_dispositions(text, source=rel, ingested_axes=axes)
            # A source card's OWN grade is already a disposition -- 'verified-clean' and
            # 'destroyed-at-source' are terminal in the existing taxonomy, so demanding a second
            # §33 tag would be paperwork, not conversion. Reuse the graded classifier the desk
            # already has rather than duplicating the grade rules here.
            with contextlib.suppress(Exception):
                resolved = {c.name.lower() for c in parse_watchlist(text)
                            if c.category == "resolved"}
                if resolved:
                    found = [i for i in found
                             if not any(r in i.name.lower() for r in resolved)]
            items += found
    return items


def _mine_backing() -> dict[str, Any]:
    """Artifact-only credit, per disposition. `killed` is backed by the GRAVEYARD -- which is what
    makes mass-killing the backlog cost more than converting it, rather than less."""
    arte = _conversion_artifacts()
    grave = []
    gp = ROOT / "docs/graveyard.md"
    if gp.exists():
        with contextlib.suppress(Exception):
            grave = [ln.strip(" #-*").lower() for ln in gp.read_text("utf-8").splitlines()
                     if ln.strip()]
    return {"wired": arte, "screened": arte, "killed": grave}


def check_mine_conversion(defects) -> None:
    """§33 MINED-TO-WIRED (stock + quality + value): no carded find sleeps twice, a backlog
    SUSPENDS mining, and the backlog is PRICED so it cannot be cleared by doing only easy work.

    Mined intelligence is inventory, and un-converted inventory depreciates. Mining is not the
    product; conversion is. This writes the gate file the digger shells refuse to start against,
    so an organ producing faster than the desk converts pays the cost itself -- flow control, not
    punishment. Three teeth beyond mere reporting: `killed` is corroborated against the graveyard
    (closing the mass-kill escape hatch), the backlog is TIER-WEIGHTED, and a priority inversion
    (cheap work finished while a Tier-1 defect-closer still owes) is its own defect.
    """
    from libs.research.mine_conversion import (
        append_snapshot,
        conversion_report,
        first_seen_map,
        load_ledger,
        vanished,
    )

    items = _mine_items()
    if not items:
        return  # nothing carded -- nothing owed (a fresh clone, not a defect)
    thr = _mine_thresholds()
    today = datetime.now(UTC).date()
    ledger = load_ledger(MINE_LEDGER)
    rep = conversion_report(items, as_of=today, backing=_mine_backing(), root=ROOT,
                            first_seen=first_seen_map(ledger))
    gone = vanished(items, ledger, as_of=today)
    if gone:
        defects.append((
            "mine-item-vanished",
            f"§33: {len(gone)} find(s) owed a disposition in the last snapshot and have "
            f"DISAPPEARED from the docs -- {', '.join(gone[:8])}. Deleting the card does not "
            "delete the obligation: the ledger remembers. Restore the item and dispose of it "
            "properly, or record the deletion as a `killed` with its graveyard mechanism."))
    with contextlib.suppress(OSError):
        append_snapshot(MINE_LEDGER, items)

    # the gate file IS the enforcement -- a reported backlog that stops nothing is a wish
    try:
        if rep.suspend_mining:
            MINING_SUSPENDED.parent.mkdir(parents=True, exist_ok=True)
            MINING_SUSPENDED.write_text(rep.verdict + "\n", "utf-8")
        elif MINING_SUSPENDED.exists():
            MINING_SUSPENDED.unlink()
    except OSError:
        pass  # a read-only checkout still reports; it just cannot gate

    if rep.n_backlog:
        defects.append((
            "mine-conversion-backlog",
            f"§33: {rep.n_backlog}/{rep.n_items} carded find(s) owe a disposition (weighted "
            f"{rep.weighted_backlog}, highest tier owing T{rep.top_tier_owing}) -- "
            f"{', '.join(rep.backlog_names)}. MINING IS SUSPENDED (data/mining_suspended): the "
            "whole dig slot reassigns to conversion, HIGHEST TIER FIRST, catalogue nothing new "
            "until it clears. Every item takes exactly one of wired / screened / killed / "
            "deferred(DATE) -- silence is the defect."))
    if rep.n_illegal:
        defects.append((
            "mine-conversion-illegal",
            f"§33: {rep.n_illegal} disposition(s) are not legal -- {', '.join(rep.illegal_names)}."
            " An UNDATED deferral is the hiding place every rotting backlog uses: name the blocker"
            " and give a date, or pick a terminal disposition."))
    if rep.n_unbacked:
        defects.append((
            "mine-conversion-unbacked",
            f"§33: {rep.n_unbacked} item(s) CLAIM a terminal disposition with no corroborating "
            f"artifact -- {', '.join(rep.unbacked_names)}. Conversion is credited from artifacts "
            "on disk, never from a report; a 'killed' needs its GRAVEYARD entry with the mechanism "
            "of death. Produce the artifact or downgrade the claim."))
    if rep.kill_share > thr["kill"] and (rep.n_killed + rep.n_wired + rep.n_screened) >= 4:
        defects.append((
            "mine-conversion-killspike",
            f"§33 quality: {rep.kill_share:.0%} of terminal dispositions are 'killed' (bar "
            f"{thr['kill']:.0%}) -- the backlog is being cleared by GRAVEYARD rather than by "
            "conversion. A disposition is not automatically a conversion; a bad batch is real but "
            "so is the cheap exit, and this is its signature. Justify each kill's mechanism."))
    if rep.n_fuzzy_credited and not rep.n_unbacked:
        defects.append((
            "mine-conversion-fuzzy",
            f"§33 evidence standard: {rep.n_fuzzy_credited} terminal claim(s) are credited by "
            "NAME MATCHING, not by a named artifact. Fuzzy credit breaks silently on a rename and "
            "grants silently on a coincidence. Use the exact form -- "
            "`[§33: wired -> data/upbit_1m.jsonl]` -- which must exist and be non-empty. Not a "
            "backlog defect; a standard the desk should be ratcheting up."))
    if rep.priority_inversion:
        defects.append((
            "mine-conversion-inversion",
            f"§33.6 priority inversion: a T{rep.top_tier_owing} item still owes while cheaper-tier "
            "work was completed. Defect-closers (a permanently-firing gate made satisfiable) "
            "outrank mechanism priors, which outrank new surfaces, which outrank operators. Work "
            "the expensive tier FIRST -- clearing the easy tail is how a backlog looks like "
            "progress while the valuable item rots."))


def check_mine_flow(defects) -> None:
    """§33 FLOW + FEEDBACK + RATCHET: is conversion getting FASTER, and does it steer generation?

    A stock check says whether inventory exists; only a flow check says whether the desk is
    improving. And conversion outcomes that dead-end in an audit report are a fence -- fed back as
    per-class priors they become a control system, which is what maximum utilisation actually
    means. The bar is the desk's OWN BEST-EVER performance: every record tightens it permanently
    and it never loosens, so there is no "good enough", only better-than-our-best or a regression.
    """
    from libs.research.mine_conversion import (
        MIN_ITEMS_PER_WINDOW,
        class_priors,
        feedback_applied,
        flow_stats,
        law_effectiveness,
        ledger_regressed,
        load_ledger,
        load_ratchet,
        priors_payload,
        stable_key,
        tier_calibration,
        update_ratchet,
    )

    ledger = load_ledger(MINE_LEDGER)
    if len(ledger) < 2:
        return  # a single snapshot cannot measure flow -- not a defect, just no history yet
    thr = _mine_thresholds()
    flow = flow_stats(ledger)
    # Stable identities, matching flow_stats: raw names count every re-grade as a fresh find,
    # which inflates the denominator and understates the conversion rate.
    n_names = len({stable_key(str(i.get("n", ""))) for r in ledger for i in r["items"]})
    rate = (flow.n_converted / n_names) if n_names else 0.0

    priors = class_priors(ledger)
    if priors:
        with contextlib.suppress(OSError):
            MINE_PRIORS.parent.mkdir(parents=True, exist_ok=True)
            MINE_PRIORS.write_text(json.dumps(priors_payload(priors), indent=2), "utf-8")

    prior = load_ratchet(MINE_RATCHET)
    local_prior = _j(MINE_RATCHET_LOCAL, {}).get("n_snapshots")
    truncated, why_trunc = ledger_regressed(
        prior, ledger, local_n_prior=int(local_prior) if local_prior is not None else None)
    if truncated:
        defects.append((
            "mine-ledger-truncated",
            f"§33: {why_trunc}. The ledger is the evidence base for latency, the per-class priors "
            "and the ratchet itself -- erasing it resets all three and hands back an easier bar. "
            "The high-water marks in docs/research/conversion_record.json are what caught this."))
    new_ratchet, verdict = update_ratchet(
        prior, flow, conversion_rate=rate, regress_mult=thr["regress"], ledger=ledger)

    # THE AUDITOR WAS MANUFACTURING ITS OWN DEFECT, ONCE PER RUN, FOREVER. `append_snapshot` adds
    # one ledger row per invocation, so `n_snapshots` advanced on every sweep; writing the whole
    # ratchet unconditionally then dirtied a GIT-TRACKED file every run, and the next check duly
    # reported `dig-output-uncommitted`. The only way to keep that green was to commit after every
    # single audit -- a defect that can only be cleared by ceremony is noise, and it was crowding
    # out the defects that matter.
    #
    # The committed ratchet now carries only the HIGH-WATER MARKS, which change rarely and are
    # genuinely institutional. The per-run count is machine-local state and lives in data/ beside
    # the ledger it counts -- which also makes the truncation test compare like with like, instead
    # of measuring a fresh clone against the count the VPS reached.
    body_changed = (new_ratchet.model_dump(exclude={"n_snapshots"})
                    != prior.model_dump(exclude={"n_snapshots"}))
    if body_changed or not MINE_RATCHET.exists():
        with contextlib.suppress(OSError):
            MINE_RATCHET.write_text(new_ratchet.model_dump_json(indent=2), "utf-8")
    with contextlib.suppress(OSError):
        MINE_RATCHET_LOCAL.parent.mkdir(parents=True, exist_ok=True)
        MINE_RATCHET_LOCAL.write_text(
            json.dumps({"n_snapshots": len(ledger), "note": (
                "machine-local snapshot count. data/ is gitignored on purpose: this counts how "
                "many times THIS machine ran the sweep, which is not an institutional fact and "
                "must never be compared against another machine's.")}, indent=1), "utf-8")

    if flow.oldest_owing_days > thr["stale"]:
        defects.append((
            "mine-flow-rotting",
            f"§33: '{flow.oldest_owing_name}' has owed a disposition for "
            f"{flow.oldest_owing_days:.0f}d (bar {thr['stale']:.0f}d). Age IS the damage -- a "
            "finding depreciates while it waits, and the desk has been faster than this."))
    if verdict.regressed:
        defects.append((
            "mine-flow-regression",
            f"§33 RATCHET: {verdict.verdict} Next-cycle bar {verdict.next_bar_days:.1f}d. The "
            "standard is the desk's own record and it only moves down -- recover the pace or "
            "log the measured reason it is no longer achievable."))
    if flow.latency_worsening and not verdict.regressed:
        defects.append((
            "mine-flow-slowing",
            f"§33: conversion latency is TRENDING worse (median {flow.median_latency_days:.1f}d, "
            "recent half >1.5x the earlier half). Catch it as a trend, before it becomes a "
            "regression against the record."))
    # THE LAW HELD TO ITS OWN STANDARD -- everything else here pressures the desk; these two ask
    # whether §33's own machinery earns its place, which the no-ceiling axiom demands of anything
    # claiming to be at max.
    cal = tier_calibration(ledger)
    if cal.inverted:
        defects.append((
            "mine-tier-miscalibrated",
            f"§33 self-audit: {cal.verdict} The T1=8..T4=1 weighting is an ASSERTION, and measured "
            "outcomes contradict it -- priority enforcement is currently steering effort toward "
            "work that does not finish. Re-tier the affected finds (explicit `tier:N`) or fix the "
            "inference keywords; do not leave a weighting in force that the evidence rejects."))
    eff = law_effectiveness(ledger)
    if eff.conclusive and not eff.improving:
        defects.append((
            "mine-law-ineffective",
            f"§33 self-audit: {eff.verdict} A law is not exempt from the evidence standard it "
            "enforces. Trend, not counterfactual (no pre-§33 baseline exists) -- but flat is flat. "
            "Either the gate is not biting or conversion is bottlenecked elsewhere; establish "
            "which before adding more enforcement on top."))
    elif not eff.conclusive and eff.n_snapshots >= 12:
        # UNJUDGEABLE IS NOT EXONERATED, and silence would read as the latter. The ledger has been
        # written often enough to look like evidence while holding too few distinct items to be
        # any -- so the desk must keep knowing it cannot yet judge its own law, and know exactly
        # what would make it judgeable. Dropping the report here is how a law stops being asked
        # about: the defect disappears, nobody notices the question went with it.
        defects.append((
            "mine-law-unjudgeable",
            f"§33 self-audit: {eff.verdict} The law is neither working nor convicted -- it is "
            f"UNMEASURED. {MIN_ITEMS_PER_WINDOW} distinct items per window is the bar; the ledger "
            f"holds {eff.n_early_items}/{eff.n_late_items}. Converting more finds is what closes "
            "this, so the fix for 'we cannot tell whether §33 works' is the same work §33 exists "
            "to demand."))
    ok, why = feedback_applied(ledger, priors)
    if not ok:
        defects.append((
            "mine-feedback-ignored",
            f"§33.4 closed loop: {why} data/mine_generation_priors.json is published every "
            "sweep -- generation MUST read it and reweight. A prior nothing acts on is the same "
            "failure as a law with no monitor."))


def check_mine_scope(defects) -> None:
    """A find written somewhere unscanned is a find outside the law -- with no code change needed.

    §33 reads a FIXED list of docs. That list is the law's blast radius, and a digger that writes
    its cards to any other file evades every check in the family without touching tracked code --
    the one bypass that does not show up in a diff. So the scope itself is audited: any
    docs/research markdown carrying numbered cards must be either IN the scanned set or in the
    explicit exclusion list with a stated reason. Consciously excluded is fine; quietly unmonitored
    is not. Same shape as check_review_risks_tracked -- a thing named in one place must inherit the
    discipline of the other, and nothing may fall between them by omission.
    """
    research = ROOT / "docs/research"
    if not research.is_dir():
        return
    card = re.compile(r"^### \d+\.", re.MULTILINE)
    rogue = []
    for p in sorted(research.glob("*.md")):
        rel = p.relative_to(ROOT).as_posix()
        if rel in _DIG_DOCS or rel in _DIG_DOCS_EXCLUDED:
            continue
        with contextlib.suppress(OSError):
            n = len(card.findall(p.read_text("utf-8", errors="ignore")))
            if n:
                rogue.append(f"{p.name}({n} cards)")
    if rogue:
        defects.append((
            "mine-scope-unmonitored",
            f"§33 scope: card-bearing research doc(s) outside the law -- {', '.join(rogue[:8])}. "
            "Findings written here owe no disposition and are invisible to every §33 check, which "
            "is the one bypass that needs no code change. Add each to _DIG_DOCS (in scope) or to "
            "_DIG_DOCS_EXCLUDED with a stated reason -- never leave it decided by omission."))


def check_mine_scope_vacuous(defects) -> None:
    """L1.57 applied to §33's own scope: a doc IN the law that the parser cannot see.

    `check_mine_scope` above hunts the outward leak -- a card-bearing doc outside `_DIG_DOCS`. The
    INWARD one had no detector at all, and it is the quieter of the two: a path listed in scope
    that contributes ZERO items reads exactly like a path that was checked and found clean. The
    backlog count comes back low, the ratchet looks healthy, and `data/mining_suspended` never
    fires -- all honestly computed, all over an empty set.

    MEASURED 2026-08-06, and this is why the check exists rather than the docstring: THREE of the
    four `_DIG_DOCS` parsed zero cards. `feed_inbox.md` (27 `##` entries), `discovery_hypotheses.md`
    (4) and `literature_coverage.md` (10) all contribute nothing, because `_ITEM_RE` requires
    `### N. <name>` and none of them writes that shape. §33 was measuring one doc and reporting it
    as the desk's whole mining surface. A ledger row had already recorded feed_inbox as "now a
    measured, fenced number" -- true in SCOPE, false in EFFECT, which is precisely the gap between
    listing a denominator and counting one.

    THE DISTINCTION THAT KEEPS THIS FROM FALSE-FIRING, and it is the whole design: an EMPTY doc is
    healthy. A queue drained to zero should read clean, and a fence that punished that would push
    the desk to keep entries around. So vacuity is content-the-parser-cannot-see -- headings
    present, cards parsed zero -- never merely "no cards".
    """
    from libs.research.mine_conversion import parse_dispositions

    head = re.compile(r"^#{2,3} ", re.MULTILINE)
    absent, vacuous = [], []
    for rel in _DIG_DOCS:
        p = ROOT / rel
        if not p.exists():
            absent.append(rel)
            continue
        try:
            text = p.read_text("utf-8", errors="ignore")
        except OSError:
            absent.append(f"{rel}(unreadable)")
            continue
        n_head = len(head.findall(text))
        try:
            n_card = len(parse_dispositions(text, source=rel))
        except Exception:
            # A parser that raises yields zero items, which is the very thing this check exists
            # to refuse to read as "clean". Caught broadly on purpose: the failure mode matters,
            # the exception type does not.
            vacuous.append(f"{Path(rel).name}(parser raised)")
            continue
        if n_card == 0 and n_head > 0:
            vacuous.append(f"{Path(rel).name}({n_head} headings -> 0 cards)")
    if absent:
        defects.append((
            "mine-scope-phantom",
            f"§33 scope: {len(absent)} path(s) in _DIG_DOCS do not exist -- {', '.join(absent)}. "
            "They are skipped silently, so the law reads as covering more ground than it does. "
            "Create the doc, or remove the path and record why the surface went away."))
    if vacuous:
        defects.append((
            "mine-scope-vacuous",
            f"§33 scope: {len(vacuous)} doc(s) IN the law parse to ZERO items while carrying "
            f"content -- {', '.join(vacuous[:8])}. A listed path that yields nothing reads exactly "
            "like a path checked and found clean (L1.57: a passing verdict over an empty set is "
            "vacuous, not OK). Either card the findings as '### N. <name>' so they owe a "
            "disposition, or move the doc to _DIG_DOCS_EXCLUDED with a stated reason and its own "
            "fence. An empty doc is fine -- this fires only on content the parser cannot see."))


#: A feed entry may sit one cycle. Past this it is not a queue, it is an archive nobody reads.
_FEED_INBOX_STALE_DAYS = 3.0
#: Depth beyond which the queue is not being drained at the rate it fills, whatever its age.
_FEED_INBOX_MAX_OPEN = 20


def check_feed_inbox_backlog(defects) -> None:
    """R0269: the research feed inbox is a QUEUE, so its depth and age are measured numbers.

    THE DUTY THAT WAS SILENTLY NOT RUNNING. `docs/research/feed_inbox.md` is specified as a queue
    processed and CLEARED every cycle. On 2026-08-01 it held 27 entries all predating 07-28, and
    nothing anywhere reported that -- the per-cycle duty had not run for days while emitting no
    signal at all. It was nominally inside §33's scope, which is what made the silence convincing;
    in fact it parsed to zero items, so §33 was reporting a clean backlog off an empty set.

    A QUEUE NOBODY COUNTS BECOMES AN ARCHIVE. This counts it: entries live (the collector writes
    '## <title>' and triage DELETES), and the age of the oldest, read from the '- <YYYY-MM-DD> ...'
    line each entry carries. Zero entries is the HEALTHY state and reads clean -- draining is what
    this fence exists to reward.
    """
    p = ROOT / "docs/research/feed_inbox.md"
    if not p.exists():
        return
    try:
        text = p.read_text("utf-8", errors="ignore")
    except OSError:
        return
    # Entries only: the file also carries HTML-comment triage blocks, which are the RECORD of
    # draining and must never be counted as backlog.
    entries = re.findall(r"^## (?!Record schema)(.+)$", text, re.MULTILINE)
    if not entries:
        return
    dates = sorted(re.findall(r"^- (\d{4}-\d{2}-\d{2}) ", text, re.MULTILINE))
    oldest_days = None
    if dates:
        with contextlib.suppress(ValueError):
            oldest = datetime.strptime(dates[0], "%Y-%m-%d").replace(tzinfo=UTC)
            oldest_days = (datetime.now(tz=UTC) - oldest).total_seconds() / 86400.0
    n = len(entries)
    stale = oldest_days is not None and oldest_days > _FEED_INBOX_STALE_DAYS
    if stale or n > _FEED_INBOX_MAX_OPEN:
        age = f"{oldest_days:.1f}d" if oldest_days is not None else "unknown age"
        defects.append((
            "feed-inbox-backlog",
            f"§33/R0269: research feed inbox holds {n} live entr(ies), oldest {age} "
            f"(bars: {_FEED_INBOX_MAX_OPEN} open / {_FEED_INBOX_STALE_DAYS:.0f}d). The inbox is "
            "specified as a queue processed and CLEARED every cycle, so a standing backlog means "
            "the per-cycle triage duty is not running -- and it reports nothing on its own, which "
            "is how it went unnoticed for days. Triage each entry to a watchlist card, a graveyard "
            "row with its mechanism, or a ledger row, then DELETE it and record the batch."))


def check_mine_gate(defects) -> None:
    """The gate must be DERIVED, not a deletable flag -- and it must actually run.

    `data/mining_suspended` was a file, and a file is something `rm` defeats: deleting it would
    have restored mining without converting anything, making the law advisory again. The shells
    now RUN scripts/mine_gate.py, which recomputes the backlog from the docs. Two failure modes
    are checked here because the gate fails OPEN by design (a bug must never freeze the desk's
    entire research intake for a week): the script must exist, and it must execute cleanly.
    """
    import subprocess

    gate = ROOT / "scripts/mine_gate.py"
    if not gate.exists():
        defects.append(("mine-gate-missing",
                        "§33: scripts/mine_gate.py is absent -- the digger shells call it to "
                        "recompute the backlog, and without it the gate degrades to whatever the "
                        "shells do on a missing command. Restore it."))
        return
    # THE GATE IS REACHED THROUGH A HELPER NOW, AND GREPPING FOR THE FILENAME MISSED IT.
    # Each shell used to run `scripts/mine_gate.py` inline, into a `_MINE_PRIORITY` variable that
    # was then never referenced -- the gate ran and its verdict went nowhere in all six. The fix
    # moved the call into `mine_priority()`/`dig_prompt()` in ops/brain_env.sh, which DOES reach
    # the prompt. This check kept looking for the literal filename and reported all six as
    # bypassing the law they had just started obeying.
    #
    # Following exactly ONE level of indirection is deliberate. A shell counts as gated if it
    # names the gate itself, or if it calls a helper that does -- and the helper must genuinely
    # invoke the gate, which is re-derived here rather than assumed. Merely SOURCING brain_env.sh
    # is not enough: sourcing a file that could call the gate is not calling it.
    _GATE_HELPERS = ("mine_priority", "dig_prompt")
    env = (ROOT / "ops/brain_env.sh")
    env_txt = env.read_text("utf-8", errors="ignore") if env.exists() else ""
    live_helpers = tuple(h for h in _GATE_HELPERS if "mine_gate.py" in env_txt and h in env_txt)

    def _code_only(text: str) -> str:
        """Shell source with comments removed. A COMMENT NAMING THE GATE IS NOT CALLING IT, and
        every one of these shells carries a comment explaining what `dig_prompt` does -- so
        matching raw text passed a shell whose actual invocation had been deleted."""
        out = []
        for line in text.splitlines():
            q = None
            for i, ch in enumerate(line):
                if q:
                    q = None if ch == q else q
                elif ch in "\"'":
                    q = ch
                elif ch == "#" and (i == 0 or line[i - 1] in " \t"):
                    line = line[:i]
                    break
            out.append(line)
        return "\n".join(out)

    def _gated(text: str) -> bool:
        # THE HELPER MUST APPEAR AS A COMMAND, NOT AS A SUBSTRING. `dig_prompt` is also inside
        # every one of these shells' PROMPT FILENAMES (ops/prospector_dig_prompt.txt), so a plain
        # `in` test passed a shell whose invocation had been replaced by `cat`. Requiring a
        # non-word character before and a word boundary after distinguishes `$(dig_prompt f)`
        # from `..._dig_prompt.txt`.
        code = _code_only(text)
        if "mine_gate.py" in code:
            return True
        return any(re.search(r"(?<![\w./-])" + re.escape(h) + r"(?=[\s)]|$)", code, re.M)
                   for h in live_helpers)

    shells = [*sorted(ROOT.glob("ops/run_*dig*.sh")), ROOT / "ops/run_frontier_miner.sh"]
    untrusting = [s.name for s in shells
                  if s.exists() and not _gated(s.read_text("utf-8", errors="ignore"))]
    if untrusting:
        defects.append(("mine-gate-bypassed",
                        f"§33: digger shell(s) do NOT invoke the derived gate -- "
                        f"{', '.join(untrusting)}. A shell that skips mine_gate.py mines "
                        "regardless of the backlog; that is the law switched off for that organ."))
    try:
        r = subprocess.run([sys.executable, str(gate), "--explain"], cwd=ROOT,
                           capture_output=True, text=True, timeout=120)
    except (OSError, subprocess.SubprocessError) as exc:
        defects.append(("mine-gate-broken",
                        f"§33: the gate script could not be executed ({type(exc).__name__}). It "
                        "fails OPEN by design, so a broken gate silently authorises mining -- "
                        "this defect is the only thing that surfaces it. Fix before the next dig."))
        return
    if "GATE-ERROR" in (r.stdout + r.stderr):
        defects.append(("mine-gate-broken",
                        f"§33: the gate script raised and failed OPEN -- {r.stdout.strip()[:220]}. "
                        "Mining is currently UNGATED. Fix before the next dig."))


def check_dig_uncommitted(defects) -> None:
    """A dig finding not in git DID NOT HAPPEN -- VPS disk is not institutional memory.

    The best output of a cycle is one disk failure from never having existed, and an audit that
    reads only the repo cannot see it at all (the map-vs-territory failure, applied to the desk's
    own research). Compares each dig doc's mtime against the last commit that touched it.
    """
    import subprocess

    # Asked exactly, via git's own index -- NOT file mtimes. A fresh clone stamps every file with
    # the checkout time, so an mtime-vs-commit-time comparison reports the entire research surface
    # as uncommitted on any re-clone. `git status --porcelain` answers the real question.
    #
    # `-b` COSTS NOTHING AND NAMES THE TREE. This box runs a dozen registered worktrees at once
    # (cron starts several), and this check reports whichever one it happened to run in -- ROOT is
    # relative to max_audit.py's own location. A bare basename is therefore unactionable from
    # anywhere else, and the way it fails is expensive rather than merely unhelpful: a reader who
    # resolves `absorbing_kelly_study.json[M]` in their OWN checkout finds it clean, goes looking,
    # finds it dirty in a sibling's tree, and commits another live session's in-progress work.
    # That is R0423, which this desk has recorded four times. Measured 2026-08-13: the handed
    # defect named absorbing_kelly_study.json, clean in the canonical checkout and dirty in two
    # sibling worktrees mid-study.
    try:
        out = subprocess.run(["git", "status", "--porcelain", "-b", "--", *_DIG_TRACKED],
                             cwd=ROOT, capture_output=True, text=True, timeout=20)
    except (OSError, subprocess.SubprocessError):
        return  # no git available -- the check simply does not apply here
    if out.returncode != 0:
        return
    stale = []
    branch = ""
    for line in out.stdout.splitlines():
        # `## <branch>...<upstream>` from -b. Skipping it explicitly matters: the parse below
        # would otherwise read it as a file with status code "##".
        if line.startswith("##"):
            branch = line[2:].strip().split("...")[0].strip()
            continue
        if len(line) > 3:
            code, path = line[:2].strip() or "??", line[3:].strip()
            # RATCHET GRACE (R0147): conversion/holdings records are re-ticked by cron every
            # ~15min, so the working tree is dirty on them within seconds of ANY commit -- as
            # written, this gate could never stay satisfied (measured: re-fired 60s after a
            # commit, aged 141.8h across a day with 4 snapshot commits). "By end of cycle"
            # means a snapshot commit exists within the cycle window, not a perpetually clean
            # tree: a file whose last COMMIT is <6h old was snapshotted this cycle and is not
            # debt. New/untracked files (??) get no grace -- they have never been committed.
            if code != "??":
                try:
                    last = subprocess.run(["git", "log", "-1", "--format=%ct", "--", path],
                                          cwd=ROOT, capture_output=True, text=True, timeout=20)
                    import time
                    if last.returncode == 0 and last.stdout.strip() and \
                            time.time() - int(last.stdout.strip()) < 6 * 3600:
                        continue
                except (OSError, ValueError, subprocess.SubprocessError):
                    pass                     # grace unreadable -> file stays counted (fail firm)
            stale.append(f"{Path(path).name}[{code}]")
    if stale:
        where = f"{ROOT}{f' ({branch})' if branch else ''}"
        defects.append((
            "dig-output-uncommitted",
            f"§33: dig output UNCOMMITTED in {where} -- {', '.join(stale[:8])}. Output not "
            "committed and pushed by end of cycle DID NOT HAPPEN and earns zero credit: git is "
            "the institutional memory, VPS disk is not. Commit, push, and VERIFY the push -- IN "
            "THAT TREE. Several worktrees are live on this box and the same path is a different "
            "session's work in each, so resolving the basename in your own checkout commits "
            "someone else's (R0423)."))


MINING_RECORD = ROOT / "docs/research/mining_record.json"   # tracked in git, like the §33 record


def check_mining_nonregression(defects) -> None:
    """MINING MAY NEVER REGRESS (principal 2026-07-25, strict). Conversion ratchets UP; mining
    volume ratchets up too and is never allowed to fall. Without this, the cheapest way to raise a
    conversion RATE is to shrink the denominator -- mine less. That is a regression in the desk's
    single irreplaceable input (unprocessed data is unrealized option value; living-web sources
    decay and cannot be re-mined later), so it is a defect, never an optimisation."""
    led = ROOT / "data/mine_conversion_log.jsonl"
    if not led.exists():
        return
    rows = []
    for line in led.read_text("utf-8", errors="ignore").splitlines():
        try:
            rows.append(json.loads(line))
        except Exception:
            continue
    if len(rows) < 3:
        return                                    # not enough history to call a trend
    counts = [len(r.get("items", [])) for r in rows if isinstance(r.get("items"), list)]
    if len(counts) < 3:
        return
    best = max(counts)
    recent = counts[-1]
    try:
        rec = json.loads(MINING_RECORD.read_text("utf-8")) if MINING_RECORD.exists() else {}
    except Exception:
        rec = {}
    record = max(int(rec.get("best_finds", 0)), best)
    if record > int(rec.get("best_finds", 0)):
        MINING_RECORD.write_text(json.dumps(
            {"best_finds": record, "updated": datetime.now(tz=UTC).isoformat(),
             "note": "desk's best-ever carded-find count in one snapshot; ratchets UP only -- "
                     "mining volume may never regress (principal 2026-07-25)"}, indent=1), "utf-8")
    # a genuine regression: latest materially below the all-time record
    if record >= 5 and recent < record * 0.6:
        defects.append((
            "mining-regression",
            f"MINING REGRESSED: latest snapshot carries {recent} carded finds vs the desk's "
            f"record of {record}. Mining volume must NEVER fall -- conversion pressure is never "
            "allowed to shrink acquisition (the cheapest way to fake a conversion rate is to mine "
            "less). Raise mining back above the record; scale extraction to meet it, never the "
            "reverse."))


def check_no_mining_throttle(defects) -> None:
    """STRUCTURAL anti-throttle guard (principal 2026-07-25). Re-verifies every surface a mining
    throttle could return through, so a future edit cannot quietly shrink the desk's intake."""
    gate = ROOT / "scripts/mine_gate.py"
    if gate.exists():
        g = gate.read_text("utf-8", errors="ignore")
        if "return 1" in g.split("def main")[-1]:
            defects.append(("mining-throttle-returned",
                            "scripts/mine_gate.py can exit non-zero again -- that BLOCKS diggers. "
                            "The gate must always exit 0; the backlog steers PRIORITY, never "
                            "whether a dig runs."))
        v = ROOT / "libs/research/mine_conversion.py"
        if v.exists() and "catalogue nothing new" in v.read_text("utf-8", errors="ignore"):
            defects.append(("mining-throttle-language",
                            "the §33 verdict text tells a dig to 'catalogue nothing new' -- that "
                            "string is injected into the dig prompt and throttles mining through "
                            "LANGUAGE. Conversion preempts priority, never acquisition."))
    for sh in [*sorted((ROOT / "ops").glob("run_*dig*.sh")), ROOT / "ops/run_frontier_miner.sh"]:
        try:
            txt = sh.read_text("utf-8", errors="ignore")
        except OSError:
            continue
        if "mine_gate.py" in txt and ("if ! " in txt and "exit 0" in txt):
            defects.append(("mining-throttle-shell",
                            f"{sh.name} carries a blocking early-exit on the mining gate -- a dig "
                            "must never be skipped for a conversion backlog."))


CARRYOVER_LEDGER = ROOT / "data/carryover_sweeps.jsonl"


def check_carryover_skipped(defects) -> None:
    """§37: work the brain was SHOWN and did not do -- distinct from work it never saw.

    The brain is a metered session; it dies on quota, and the cycle's owed work used to die with
    it. §37 records every sweep and hands the backlog back on return. This check closes the other
    half: an item that survived sweeps the brain was AWAKE for was not missed, it was SKIPPED --
    and a plain queue cannot tell the two apart, because a long queue looks identical whether
    nobody was home or everybody walked past it. Only the second is a defect: blaming the desk for
    an outage is unfair, and excusing avoidance is expensive.
    """
    from libs.ops.carryover import carryover_state, load_sweeps

    sweeps = load_sweeps(CARRYOVER_LEDGER)
    if len(sweeps) < 3:
        return  # too little history to distinguish a skip from a fresh item
    st = carryover_state(sweeps, now=NOW)
    skipped = st.skipped_items
    if not skipped:
        return
    worst = ", ".join(f"{i.defect_id}({i.seen_by_live_brain}x awake, {i.age_days:.0f}d)"
                      for i in skipped[:6])
    defects.append((
        "carryover-skipped",
        f"§37: {len(skipped)} item(s) survived sweeps the brain was AWAKE for -- {worst}. "
        f"{st.n_dead_sweeps} cycle(s) were lost to quota and are NOT the excuse for these: the "
        "brain ran, was handed the item, and carried it anyway. Do them, or record in the ledger "
        "why not -- silently carrying an item a third time is what this exists to stop."))


#: Every check the sweep runs. Module-level so other organs (§37 carry-over) can
#: enumerate the same set instead of keeping a second copy that silently drifts.
def check_recommendation_rows(defects) -> None:
    """§42 X1 wire (2026-07-31): the recommendation ledger joins the carry-over pressure loop.

    Measured before this check existed (meta audit 2026-07-31): NO row older than 3.67 days had
    ever been implemented -- λ≈14 rows/day arrived, terminal disposals ran ≈3.2/day and almost
    entirely same-session, so the undone stock grew +10/day and old rows were simply never seen
    again. Directives, findings and gap-register rows all had max_audit gates; the §42 ledger --
    the one organ whose law says nothing recommended is ever forgotten -- had none, so the §37
    brief (built FROM these checks) could not carry its rows across sessions.

    Per-row stable IDs (`rec-owed-R0031`) let the sweep ledger track each row's survival count
    individually, which is the §37 pressure that actually moves work. The per-row list is capped
    to the OLDEST offenders so the pager stays readable; the summary defect carries the TRUE
    totals so the cap hides nothing (no-silent-caps). Grace/due semantics mirror
    scripts/recommendations.py (GRACE_H=24, terminal={implemented,rejected}); a parity test in
    tests/test_desk_integrity_checks.py locks the two against drifting apart.
    """
    _PER_ROW_CAP = 12
    d = _j(ROOT / "docs/research/recommendation_ledger.json", {})
    rows = d.get("recommendations", []) if isinstance(d, dict) else []
    if not rows:
        return
    now = datetime.now(UTC)

    def _age_h(iso):
        try:
            return (now - datetime.fromisoformat(iso)).total_seconds() / 3600.0
        except (TypeError, ValueError):
            return 0.0

    overdue = []
    for r in rows:
        st = r.get("status")
        if st == "open" and _age_h(r.get("raised", "")) > 24.0:
            overdue.append((_age_h(r.get("raised", "")), r, "undisposed"))
        elif st == "scheduled":
            due = str(r.get("due") or "")
            if due and due < now.date().isoformat():
                overdue.append((_age_h(r.get("raised", "")), r, f"scheduled-past-due({due})"))
    if not overdue:
        return
    overdue.sort(key=lambda t: -t[0])
    for age_h, r, why in overdue[:_PER_ROW_CAP]:
        defects.append((f"rec-owed-{r.get('id', '?')}",
                        f"§42: {r.get('id')} {why} {age_h / 24.0:.1f}d "
                        f"[{r.get('source', '?')}]: {str(r.get('summary', ''))[:120]}"))
    defects.append(("rec-ledger-backlog",
                    f"§42: {len(overdue)} recommendation row(s) owe a disposition "
                    f"({sum(1 for *_, w in overdue if w == 'undisposed')} undisposed past 24h "
                    f"grace, {sum(1 for *_, w in overdue if w != 'undisposed')} scheduled past "
                    f"due; oldest {overdue[0][0] / 24.0:.1f}d, {_PER_ROW_CAP} oldest shown "
                    f"per-row). Dispose via scripts/recommendations.py dispose -- implemented "
                    f"with --commit, rejected with a real --reason, or scheduled with an "
                    f"enforced --due. Deleting rows is the denominator trick and is detected."))





# ---------------------------------------------------------------------------------------------
# RESTORED 2026-08-13. These four checks were dropped by the 8b981a5 merge -- DEFINITION AND
# DISPATCH ENTRY BOTH -- because that resolution took the other branch's max_audit.py wholesale
# and these existed only on this one. No import broke and no test named three of them, so four
# audits simply stopped running and the auditor kept reporting green. An audit that vanishes is
# strictly worse than one that fails: a failure is a signal, an absence is a silence that reads
# exactly like a pass.
# ---------------------------------------------------------------------------------------------

def check_meta_research(defects) -> None:
    """The CIO review must RUN. §12 of META_RESEARCH_DIRECTIVE, made mechanical.

    A directive that lives only in prose is skipped on a busy cycle and the skip is invisible --
    this desk's own recursion rule says every manual probe becomes a standing automatic check.
    """
    st = _j(ROOT / "data/meta_research_review.json", {})
    ran = st.get("ran")
    if not ran:
        defects.append(("meta-research-never",
                        "META_RESEARCH_DIRECTIVE review has never run -- research capital is "
                        "being allocated without the CIO layer that prices it"))
        return
    try:
        age_d = (datetime.now(tz=UTC) - datetime.fromisoformat(ran)).days
    except (TypeError, ValueError):
        return
    if age_d > 3:
        defects.append(("meta-research-stale",
                        f"meta-research review last ran {age_d}d ago (floor 3d) -- the desk is "
                        "allocating engineering hours without a current ERV ranking"))


def check_principal_page_unanswerable(defects) -> None:
    """RETURN-PATH CHECK (self-interrogation angle 11, mechanised 2026-08-05).

    A page is half a channel. This desk verified DELIVERY for weeks and never once verified that
    the principal could ANSWER -- so when the branch fork deleted `_poll_replies` from
    run_alerts.py, the pager went strictly one-way on 2026-08-02 and nothing noticed. Four
    decisions, two of them gating the entire book and the entire promotion funnel, sat "awaiting
    principal" across 33 sweeps; the `gate-optimality` ack read *"lifts on his reply"* while he
    had no way to send one.

    Fires when there is an open ask AND the reply poller has not run recently. Deliberately keyed
    on the POLL STATE rather than on the presence of replies: silence is the expected state of a
    healthy reply channel, so "no replies" can never be the trigger. What must never happen is the
    desk waiting on an answer down a pipe that nobody is reading.
    """
    ask = ROOT / "data/PRINCIPAL_ACTION.md"
    if not ask.exists() or not ask.read_text("utf-8", errors="ignore").strip():
        return                                    # nothing is blocked on him
    state = ROOT / "data/.reply_poll_state.json"
    if not state.exists():
        defects.append((
            "principal-page-unanswerable",
            "data/PRINCIPAL_ACTION.md carries an open ask but data/.reply_poll_state.json does "
            "NOT EXIST -- nothing on this box is reading the reply channel, so the page cannot be "
            "answered by any means. Restore _poll_replies in scripts/run_alerts.py."))
        return
    try:
        polled = json.loads(state.read_text("utf-8")).get("polled")
        age_h = (NOW - datetime.fromisoformat(str(polled)).timestamp()) / 3600.0
    except Exception:
        age_h = None
    if age_h is None or age_h > 6:
        shown = "unparsable" if age_h is None else f"{age_h:.1f}h"
        defects.append((
            "principal-page-unanswerable",
            f"data/PRINCIPAL_ACTION.md carries an open ask but the reply poll last ran {shown} "
            "ago (watchdog fires run_alerts every 3 min, so anything over ~6h means the poller is "
            "dead). The desk is waiting on an answer down a pipe nobody is reading -- verify "
            "_poll_replies still runs in scripts/run_alerts.py main()."))


def check_dig_log_disposition(defects) -> None:
    """§35(9): a miner session log stays out of §35 only while it DISPOSES ITS OWN ITEMS.

    `prospector_coverage.md` is excluded from the §35 scan because every numbered item in a
    session note closes in place with an inline `[§33: ...]` tag. That is a CLAIM ABOUT THE
    DOCUMENT, and a claim nobody checks is exactly the shape the scope law exists to forbid --
    the next session writes one more item, forgets the tag, and the item is now governed by
    nothing at all while the exclusion comment still says otherwise. The same reasoning already
    stands behind _TRIAGE_DOCS ("the exclusion is only honest while that stays TRUE, so it is
    checked rather than trusted"); this is that instrument applied to the other self-disposing
    surface, so the two exclusions cost the same to hold.

    A FLOOR, NOT A MATCHER, and said out loud: counting tags per session cannot prove tag #2
    belongs to item #2 (the seats write the tag on the item's own line, on a later `#### ITEM n`
    header, or at the end of the item's block, and all three are legal). What it CANNOT be
    satisfied by is a session that adds an item and no disposition -- which is the entire failure
    mode the exclusion must not be allowed to hide. Item parsing reuses ``parse_findings`` on each
    section, so the set counted here is exactly the set §35 would have scanned; a second item
    parser that drifted from the first would reintroduce the blind spot one level down.
    """
    from libs.research.finding_registry import parse_findings

    short = []
    for rel in _SELF_DISPOSING_DIG_LOGS:
        p = ROOT / rel
        if not p.exists():
            continue
        try:
            text = p.read_text("utf-8")
        except OSError:
            continue
        # Sections are the `### ` session notes. `#### ITEM n` sub-headers stay INSIDE their
        # session on purpose: that is where two of the five seats write their dispositions.
        heads = [(m.start(), m.group(1).strip())
                 for m in re.finditer(r"^###\s+(.+?)\s*$", text, re.MULTILINE)]
        bounds = [h[0] for h in heads] + [len(text)]
        for i, (pos, title) in enumerate(heads):
            block = text[pos:bounds[i + 1]]
            n_items = len(parse_findings(block, source=rel))
            n_tags = len(_DIG_TAG_RE.findall(block))
            if n_items and n_tags < n_items:
                short.append(f"{Path(rel).name} '{title[:60]}' "
                             f"({n_items} item(s), {n_tags} §33 tag(s))")
    if short:
        defects.append((
            "dig-log-undisposed",
            f"§35(9): {len(short)} miner session(s) carry numbered items with FEWER §33 "
            f"dispositions than items -- {'; '.join(short[:6])}. The doc is excluded from the §35 "
            "findings scan PRECISELY because it dispositions its own items inline; an item with "
            "no tag is governed by neither law. Write the item's "
            "`[§33: wired|screened|killed|deferred(DATE)|n/a -> artifact]` tag, or move the doc "
            "into _FINDING_DOCS so §35 takes it and every item owes a GAP_REGISTER row instead."))


def check_scheduled_scripts(defects) -> None:
    """Every scheduled command must NAME A FILE THAT EXISTS in this checkout.

    Found live 2026-08-04: the working tree sat on a branch forked from master at 3bf89cd, and
    75 of the 125 scripts the crontab invokes existed only on master -- 60% of the desk's
    scheduled organs, run_live_guard.py among them, had been dying instantly on ENOENT. Nothing
    reported it, because each organ still APPENDED TO ITS LOG on every fire: the log's mtime was
    minutes old and its contents were 'can't open file'. Every freshness-shaped check the desk
    owns read that mtime and passed. deploy/pull_deploy.sh was itself missing, so the mechanism
    that would have re-synced the tree was part of the outage.

    This is the config-vs-outcome class: a schedule proves intent, never execution. The check is
    deliberately the cheapest possible statement of the real requirement -- resolve what is
    scheduled, then stat it -- because that is the assertion no freshness signal can fake.
    """
    import re
    import subprocess as _sp

    # The pattern must consume the WHOLE path token, not the tail that happens to start at a
    # `scripts/`|`ops/`|`deploy/` segment. The unanchored form shipped until 2026-09-03 and was
    # wrong in BOTH directions on any organ living under a sub-desk: it reported
    # `desks/mt5/scripts/fxblue_track_record_miner.py` as the non-existent
    # `scripts/fxblue_track_record_miner.py` (a false positive, which trains the desk to ignore
    # this fence -- L1.43), and, worse, it would have resolved a genuinely MISSING
    # `desks/<x>/scripts/foo.py` against a same-named `scripts/foo.py` that does exist and
    # reported the dead organ HEALTHY. That silent direction is the exact failure this check was
    # written for. The leading greedy class backtracks to the longest prefix, so absolute paths
    # match whole too and are normalised against ROOT below.
    _SCHED_PATH_RE = re.compile(
        r"[A-Za-z0-9_./-]*(?:scripts|ops|deploy)/[A-Za-z0-9_./-]+\.(?:py|sh)")

    def _resolve(tok: str) -> Path:
        """A scheduled token -> the path to stat. Absolute stays absolute unless it is inside
        this checkout, in which case it is made repo-relative so the answer does not depend on
        which worktree ran the audit."""
        q = Path(tok)
        if q.is_absolute():
            try:
                return ROOT / q.relative_to(ROOT)
            except ValueError:
                return q
        return ROOT / q

    refs: dict[str, str] = {}                     # script path -> where it was scheduled
    try:
        _cr = _sp.run(["crontab", "-l"], capture_output=True, text=True, timeout=20, check=False)
        for ln in (_cr.stdout or "").splitlines():
            if ln.strip().startswith("#"):
                continue
            for m in _SCHED_PATH_RE.findall(ln):
                refs.setdefault(m, "crontab")
    except (OSError, _sp.SubprocessError):
        pass                                       # no crontab on this box: unit files still count
    for unit in sorted(Path("ops").glob("*.service")):
        try:
            for ln in unit.read_text("utf-8").splitlines():
                if ln.strip().startswith("ExecStart"):
                    for m in _SCHED_PATH_RE.findall(ln):
                        refs.setdefault(m, unit.name)
        except OSError:
            continue

    missing = sorted(p for p in refs if not _resolve(p).exists())
    if missing:
        shown = ", ".join(missing[:6]) + ("..." if len(missing) > 6 else "")
        defects.append((
            "scheduled-script-missing",
            f"{len(missing)}/{len(refs)} scheduled script(s) DO NOT EXIST in this checkout: "
            f"{shown}. Every one of these fires on schedule, dies on ENOENT, and still touches "
            f"its log -- so freshness checks read minutes-old logs and report the organ healthy. "
            f"A schedule is intent, not execution. Restore the files (usually a branch/deploy "
            f"divergence: compare against the mainline) or remove the schedule."))


CHECKS = [("carryover-skipped", check_carryover_skipped),
          ("recommendation-rows", check_recommendation_rows),
          ("organs", check_organs), ("stubs", check_stub_deaths),
          ("unit-deaths", check_unit_deaths),
          ("manifest-backlog", check_manifest_backlog),
          ("launcher-unsealed", check_launcher_seal),
                      ("stale-daemons", check_stale_daemons),
                      ("panel", check_panel), ("model-freshness", check_model_freshness),
                      ("coverage", check_coverage),
                      ("findings", check_findings), ("idle", check_idle_capability),
                      ("directives", check_directives), ("verify", check_verify_lag),
                      ("blind", check_blind_trigger),
                      ("self-application", check_self_application),
                      # First-class rather than a line inside self-application (2026-08-05): the
                      # desk-wide gate being green AND provably still running deserves its own
                      # named entry, not a sentence buried among thirty organ probes. Registered
                      # here and removed from check_self_application's body -- one caller, so it
                      # reports once.
                      ("ci-gate", check_ci_gate),
                      ("dig-depth", check_dig_depth),
                      ("meta-research", check_meta_research),
                      ("principal-page", check_principal_page_unanswerable),
                      ("dig-log-disposition", check_dig_log_disposition),
                      ("scheduled-scripts", check_scheduled_scripts),
                      ("interrogation", check_interrogation),
                      ("generation", check_generation),
                      ("clock-saturation", check_clock_saturation),
                      ("vendor-replacement", check_vendor_replacement),
                      ("forensics-fresh", check_forensics_fresh),
                      ("carry-funding-measured", check_carry_funding_measured),
                      ("memory-hygiene", check_memory_hygiene),
                      ("prompt-layer", check_prompt_layer),
                      ("gate-optimality", check_gate_optimality),
                      ("welded-gates", check_welded_gates),
                      ("data-utilization", check_data_utilization),
                      ("mining-nonregression", check_mining_nonregression),
                      ("no-mining-throttle", check_no_mining_throttle),
                      ("ci-scope", check_ci_scope),
                      ("review-risks", check_review_risks_tracked),
                      ("findings-tracked", check_findings_tracked),
                      ("findings-scope", check_findings_scope),
                      ("findings-ratchet", check_findings_ratchet),
                      ("gap-register-health", check_gap_register_health),
                      ("producer-cadence", check_producer_cadence),
                      ("llm-exhaustion", check_llm_exhaustion),
                      ("dependency-drift", check_dependency_drift),
                      ("naive-datetime", check_naive_datetime),
                      ("host-memory", check_host_memory_headroom),
                      ("test-suite", check_test_suite_collectable),
                      ("triage-disposition", check_triage_disposition),
                      ("artifact-governance", check_artifact_governance),
                      ("orphan-code", check_orphan_code),
                      ("money-path-wired", check_money_path_wired),
                      ("decision-maturity", check_decision_ledger_matures),
                      ("orphan-modules", check_orphan_modules),
                      ("capacity-hunt", check_capacity_hunt),
                      ("deploy-path", check_deploy_path),
                      ("capacity-single-source", check_capacity_single_source),
                      ("capacity-runway", check_capacity_runway),
                      ("capacity-allocation-honesty", check_capacity_allocation_honesty),
                      ("capacity-governor-reachable", check_capacity_governor_reachable),
                      ("capacity-knobs-wired", check_capacity_knobs_are_wired),
                      ("book-collapse", check_book_collapse),
                      ("mine-evidence-base", check_mine_evidence_base),
                      ("orphan-scripts", check_orphan_scripts),
                      ("phantom-paths", check_phantom_paths),
                      ("law-numbers", check_law_numbers_unique),
                      ("mine-conversion", check_mine_conversion),
                      ("mine-flow", check_mine_flow),
                      ("mine-gate", check_mine_gate),
                      ("mine-scope", check_mine_scope),
                      ("mine-scope-vacuous", check_mine_scope_vacuous),
                      ("feed-inbox-backlog", check_feed_inbox_backlog),
                      ("dig-uncommitted", check_dig_uncommitted),
                      ("depth-parity", check_depth_parity),
                      ("source-backlog", check_source_backlog),
                      ("rejection-shadow", check_rejection_shadow),
                      ("post-gate0-activation", check_post_gate0_activation),
                      ("production", check_production),
                      ("self-sufficiency", check_self_sufficiency),
                      ("rs-detect", check_rubberstamp_detector),
                      ("rs-enforce", check_rubberstamp_enforcement)]


PAID_TARGETS = ROOT / "docs/research/paid_dataset_targets.md"
HOLDINGS_RECORD = ROOT / "docs/research/holdings_record.json"   # git-tracked, ratchets UP only
#: Data-surface high-water mark. Machine-local BY NECESSITY: it counts gitignored `data/` holdings,
#: so a committed figure makes every clone look like it lost the VPS's entire lake.
HOLDINGS_LOCAL = ROOT / "data/holdings_surface_local.json"


def check_paid_target_registry(defects) -> None:
    """§42: the paid-dataset target registry must exist, be hunted, and GROW.

    §38 hunts a replacement when a source fails -- reactive. §42 keeps a standing list of every
    valuable paid dataset with a live free-replacement status, so the desk already knows what it
    would do if a vendor vanished. A FIXED list is the same blind spot in a different shape, so
    the list growing is itself the deliverable.
    """
    if not PAID_TARGETS.exists():
        defects.append(("paid-registry-missing",
                        "§42: docs/research/paid_dataset_targets.md is missing -- the desk has no "
                        "standing list of paid datasets to hunt free replacements for, so it can "
                        "only react to failures instead of anticipating them"))
        return
    txt = PAID_TARGETS.read_text("utf-8", errors="ignore")
    rows = [ln for ln in txt.splitlines() if ln.startswith("| ") and "---" not in ln]
    n = max(0, len(rows) - 1)                      # minus the header row
    open_items = sum(1 for ln in rows if "OPEN" in ln)
    try:
        rec = json.loads(HOLDINGS_RECORD.read_text("utf-8")) if HOLDINGS_RECORD.exists() else {}
    except Exception:
        rec = {}
    best = int(rec.get("best_paid_targets", 0))
    if n > best:
        rec["best_paid_targets"] = n
        rec["updated"] = datetime.now(tz=UTC).isoformat()
        rec.setdefault("note", "§42 ratchet: registry size and holdings only grow; a fall is a "
                               "regression defect, never a new normal")
        # Trailing newline, because this file is GIT-TRACKED. Without it every write produces a
        # "\ No newline at end of file" diff that touches the last line whether or not the last
        # line changed, so a one-field ratchet bump reads as a two-line edit and a reviewer
        # scanning for real changes learns to skip this file. Same family as R0272 (tracked-JSON
        # format), one file over.
        HOLDINGS_RECORD.write_text(json.dumps(rec, indent=1) + "\n", "utf-8")
    elif n < best:
        defects.append(("paid-registry-shrank",
                        f"§42: paid-dataset registry fell to {n} entries from a record of {best} "
                        "-- the hunt list may only GROW. Restore the removed targets or record "
                        "why each is genuinely no longer a dataset worth replacing."))
    # a registry nobody advances is a document, not a hunt
    age_d = (NOW - PAID_TARGETS.stat().st_mtime) / 86400.0
    if age_d > 14 and open_items:
        defects.append(("paid-registry-stagnant",
                        f"§42: {open_items} OPEN replacement hunts and the registry has not been "
                        f"touched in {age_d:.0f}d. Every dig must advance the top OPEN item it "
                        "can and ADD any paid dataset it encountered -- a list that never grows "
                        "is the same blind spot in a different shape."))


def check_holdings_never_shrink(defects) -> None:
    """§42(4): non-noise information holdings grow monotonically -- quantity AND quality.

    Counts the desk's live data surface (lake axis dirs + forward-clock/series jsonl files) and
    ratchets it against the best-ever. A source removed without replacement, a series left to rot,
    or history quietly dropped is a §34 regression arriving by attrition rather than by mining
    less. Today's holdings are the FLOOR, never the target.
    """
    lake = ROOT / "data/lake/bronze"
    axes = sum(1 for _ in lake.iterdir()) if lake.exists() else 0
    series = len(list(ROOT.glob("data/*.jsonl")))
    surface = axes + series
    if surface == 0:
        return
    # THE HIGH-WATER MARK MUST LIVE WHERE THE THING IT MEASURES LIVES. `best_surface` counted
    # `data/lake/bronze` directories and `data/*.jsonl` files -- both gitignored -- while the
    # record sat in a git-TRACKED file. So every clone measured a near-empty data/ against the
    # VPS's 37 and reported catastrophic attrition: this checkout read 9 against 37 and filed
    # `holdings-shrank`, having dropped nothing. Identical in shape to the `n_snapshots` ratchet
    # fixed the same day, and the same fix applies -- a machine-local measurement needs a
    # machine-local record.
    #
    # ONE-TIME COST, STATED: the local record seeds from the CURRENT surface on first run, so a
    # drop occurring between this change landing and that first run is not caught. On the machine
    # that owns the data the seed is taken at its true (high) value and the ratchet proceeds
    # normally from there. Missing one transition once beats reporting a false regression forever.
    try:
        loc = json.loads(HOLDINGS_LOCAL.read_text("utf-8")) if HOLDINGS_LOCAL.exists() else {}
    except (OSError, json.JSONDecodeError):
        loc = {}
    best = int(loc.get("best_surface", 0))
    if surface > best:
        loc["best_surface"] = surface
        loc["updated"] = datetime.now(tz=UTC).isoformat()
        loc["note"] = ("machine-local: counts gitignored data/ holdings, so this record must not "
                       "be committed -- a clone would inherit another machine's floor")
        with contextlib.suppress(OSError):
            HOLDINGS_LOCAL.parent.mkdir(parents=True, exist_ok=True)
            HOLDINGS_LOCAL.write_text(json.dumps(loc, indent=1), "utf-8")
    elif best >= 8 and surface < best * 0.9:
        defects.append(("holdings-shrank",
                        f"§42(4): information surface fell to {surface} (axes+series) from a "
                        f"record of {best}. Holdings may NEVER shrink -- a dropped source, a "
                        "rotted series or discarded history is a regression by attrition. Restore "
                        "it or record the replacement that supersedes it."))


# RETIRED 2026-09-05 (universe mandate): `check_fee_carry_ratio`, the §40 fee/carry ratchet. It
# paginated Binance `/fapi/v1/income` and graded commission as a fraction of PERP FUNDING
# harvested. Both halves are crypto-exchange-native: the income ledger is a venue endpoint this
# desk may no longer call, and "funding harvested" is the cash-and-carry sleeve's revenue line,
# deleted the same day with the sleeve.
#
# THE PRINCIPLE IS NOT RETIRED, ONLY THIS INSTRUMENT. "Fees must shrink relative to what they
# consume" survives on the MT5 side as the cost surface and execution-quality decomposition under
# desks/mt5/, which grade spread + commission + swap against realised R. What is deliberately NOT
# done here is a fake repoint: re-pointing a funding-denominated ratchet at a book with no funding
# line would publish a ratio computed from a zero denominator and call it a floor.
#
# The `FEE_RECORD` constant (docs/research/fee_ratio_record.json) was this check's ratchet store
# and is removed with it -- a ratchet file with no writer reads as a floor the desk is still
# holding. The §40 row is removed from CHECKS below rather than left pointing at a function that
# cannot run. The historical record itself stays on disk under docs/, which is memory, not a
# live mandate (see scripts/check_mt5_purity.py).


def check_close_retry_loop(defects) -> None:
    """A carry that keeps failing to close is a CHURN ENGINE, not a stuck position.

    ORIGIN (2026-07-28 incident, and the reason this is mechanical rather than a lesson): every
    futures hedge had been force-closed out from under the book, so the close path's reduceOnly
    cover had nothing to reduce. The venue rejects that order, `_filled` returns False, and the
    pair stayed tracked for a retry -- every tick, forever -- while `_reconcile` rebuilt BOTH legs
    in front of each attempt. The book round-tripped its entire notional through market orders
    every 600s: 11,136 venue commission events against 251 logged round-trips, $1,456 of fees in
    48h against $113 of LIFETIME funding harvest.

    §40 (`check_fee_carry_ratio`) DID fire on this, ~27h before it was diagnosed -- but it reports
    a SYMPTOM ("fees are 63x the harvest"), which is consistent with a dozen causes and cost a
    full diagnosis to localise. This check reports the FINGERPRINT: the same symbol failing to
    close on repeat. Detection was never the gap; NAMING THE CAUSE was.

    Deliberately reads the published feed rather than re-deriving state: CLOSE-FAIL is exactly
    what the executor itself says it did, so the check cannot disagree with the book about
    reality (institutional_knowledge: a monitor that sources ground truth from the failing
    component cannot see the failure -- here the feed is the executor's own testimony, and a
    stale feed is caught by the separate liveness checks).
    """
    feed = ROOT / "web/cashcarry_live.json"
    if not feed.exists():
        return
    try:
        acts = json.loads(feed.read_text("utf-8")).get("last_actions") or []
    except Exception:
        return
    failing = sorted({a.split()[1].rstrip(":") for a in acts
                      if isinstance(a, str) and a.startswith("CLOSE-FAIL")})
    if not failing:
        return
    rebuilding = sorted({a.split()[1] for a in acts if isinstance(a, str)
                         and (a.startswith("re-hedge") or a.startswith("spot-rehedge"))})
    both = [s for s in failing if s in rebuilding]
    if both:
        defects.append(("carry-churn-loop",
                        f"CHURN LOOP: {', '.join(both)} are failing to CLOSE while the reconciler "
                        f"REBUILDS the same legs in the same tick -- the book is round-tripping "
                        f"its notional every interval and paying fees both ways for zero harvest. "
                        f"This is unbounded: it does not self-heal and it has no position limit. "
                        f"Stop the executor or clear the cause NOW, do not wait for the fee ratio "
                        f"to report it."))
    else:
        defects.append(("carry-close-failing",
                        f"close failing on {', '.join(failing)} -- each retry pays fees for a "
                        f"position that never retires. Verify the leg is not ALREADY flat (a "
                        f"reduceOnly cover against a flat position is rejected, which reads as "
                        f"'unfilled' forever) before treating this as a transient venue error."))


def check_book_absorbing_state(defects) -> None:
    """A book whose risk rail can never release it is DEAD, not safe -- and reads as healthy.

    ORIGIN (2026-07-29, found by hand during the STEP-0 integrity watch; encoded here under the
    recursion rule so it is never a hand-probe again). The carry book sat at n_carries=0 /
    deployed_notional=0 with a fresh heartbeat and NO alarm anywhere in the sweep, because every
    existing check reads a flat book as a healthy one: the bleed alarm needs non-funding PnL, §40
    needs >$5 of funding to divide by, and `check_close_retry_loop` needs CLOSE-FAIL actions. A
    book doing NOTHING trips none of them.

    What was actually happening: the 07-25→07-28 churn loop billed $1,750.65 of commission against
    $113.04 of lifetime funding, driving combined equity to -37.2% from inception. `risk_controls`
    flattens at -35% measured against a FIXED `start_equity`, and its response -- flatten -- removes
    the only mechanism (carrying) by which equity could ever climb back. So the verdict is
    self-sustaining: flat forever, evidence clock stopped, and the forward track record the live
    gate sizes on silently stopped accruing.

    That absorbing property is CORRECT for real capital: a book that lost a third of its equity
    must stop and get human review, never auto-resume. The defect is not the rail, it is that
    NOTHING SAID SO -- the rail's design assumes a human re-baselines it, and no organ ever
    escalated that a human decision was owed. This check is that escalation.

    Deliberately recomputes the verdict through the SAME pure function the executor calls, from
    the same state file, rather than re-deriving a threshold here: a monitor that keeps its own
    copy of the rule eventually disagrees with the book about the book's own state. Reads that
    fail leave the check SILENT -- an unmeasurable equity must never manufacture a defect (the
    07-26 "no measurement beats a confident wrong one" lesson).

    NOT a rail change and must never become one: re-baselining a ruin rail after it fired is
    Tier-3 (principal-only). This check reports; the principal decides.
    """
    feed = ROOT / "web/cashcarry_live.json"
    st_p = ROOT / "data/cashcarry_positions.json"
    if not (feed.exists() and st_p.exists()):
        return
    try:
        from libs.risk import capital_events, risk_controls
        fd = json.loads(feed.read_text("utf-8"))
        st = json.loads(st_p.read_text("utf-8"))
    except Exception:
        return
    fut_leg = fd.get("fut_leg_net")
    if fut_leg is None:                       # futures equity unmeasured this tick -> stay silent
        return
    try:
        # THE THIRD SITE OF THE TWO-SITES/ONE-TRUTH BUG (R0364). The docstring above promises this
        # monitor recomputes through the SAME pure function the executor calls; it did, and then
        # fed it a DIFFERENT inception. `start_futures_equity` is the raw inception, written once
        # and never re-based, while `fut_leg_net` is published as `fut_eq - effective_start_equity`
        # (run_cashcarry_executor.py:1833) -- so `raw + fut_leg_net` adds a delta measured against
        # one baseline to another baseline and over-states equity by exactly the ledgered re-base.
        # Measured 2026-08-12: this monitor believed $13,472.67 while the book's own published
        # equity was $8,682.22, a $4,790.70 gap equal to the recorded capital event to the cent.
        #
        # The direction is the dangerous one. `flatten` comes ONLY from the ruin rail
        # (risk_controls.evaluate:319, dd_start = eq/start - 1), so over-stating equity means this
        # check goes SILENT while the real rail is firing: at a true -36% the raw arithmetic reads
        # -19.7% and reports a healthy book. An absorbing-state monitor that cannot see the
        # absorbing state is worse than absent, because its silence is read as an all-clear.
        #
        # `flow_adjusted_equity` and `venue_equity` are deliberately still omitted: both feed only
        # the pause/breach branches, and this check returns early on anything but `flatten`.
        start = capital_events.effective_start_equity(float(st["start_futures_equity"]))
        fut_eq = start + float(fut_leg)
        # Flat book: unrealised spot is 0, so the spot side is exactly the banked realised PnL.
        eq_c = fut_eq + float(st.get("realized_spot_pnl", 0.0))
        peak = float(st.get("peak_combined_equity", start))
        gross = float(fd.get("deployed_notional") or 0.0)
        n_carries = int(fd.get("n_carries") or 0)
    except (KeyError, TypeError, ValueError):
        return
    verdict = risk_controls.evaluate(eq_c, start, peak, gross, ruin_cap_lev=8.0)
    # BOTH HOLDING ACTIONS ARE ABSORBING ON A FLAT BOOK, and narrowing this to `flatten` made the
    # monitor blind to the commoner half. `pause_opens` bars NEW opens; on a book already holding
    # nothing that is the same trap by a gentler name -- no carries, so no funding, so equity
    # cannot rise, so the drawdown never shrinks and the pause never lifts. The measured 2026-08-05
    # instance was exactly this: pause_opens at -17.65% with zero positions, and it is the state
    # this check was originally written for.
    if verdict.action not in ("flatten", "pause_opens"):
        return
    if n_carries > 0 or gross > 0:
        # Holding inventory is the rail doing its job mid-unwind -- transient, not absorbing, and
        # a book with carries still earns funding, so its equity genuinely can move.
        return
    # The bar is IMPORTED, never re-stated. This docstring promises the monitor recomputes through
    # the same rule the executor uses, and a second copy of 0.35/0.15 here is precisely how the
    # monitor and the book end up disagreeing about the book's own state.
    ruin = verdict.action == "flatten"
    bar = risk_controls.DRAWDOWN_RUIN if ruin else risk_controls.DD_PAUSE
    # Distance to clear, measured against the denominator each rail actually uses: the ruin rail
    # is equity/START - 1 (risk_controls.evaluate:319), the pause rail is off PEAK.
    base = start if ruin else peak
    gap = (1.0 - bar) * base - eq_c
    defects.append((
        "book-absorbing-state",
        f"BOOK DEAD, NOT IDLE: the carry book is flat (n_carries=0) while risk_controls still "
        f"returns {verdict.action.upper()} -- {'; '.join(verdict.reasons)}. A flat book earns no "
        f"funding, so equity cannot rise the ${gap:,.2f} needed to clear the {bar:.0%} bar, so "
        f"the verdict never clears: this state is ABSORBING and the forward track record the live "
        f"gate sizes on has STOPPED ACCRUING (combined equity ${eq_c:,.2f} vs ${start:,.2f} "
        f"inception, peak ${peak:,.2f}). Every other check reads this as a healthy flat book. "
        f"Re-baselining a fired rail is TIER-3 (principal-only) -- a re-arm does NOT touch it and "
        f"this is NOT a licence to move one; a prior re-baseline dissolved a live DD rail, because "
        f"the rail is a ratio. Page the principal with the attribution of what caused the "
        f"drawdown, or ledger the decision to sit flat. What is forbidden is neither."))


#: How far the recomputed ruin-channel drawdown may sit from the published one before the
#: published block is treated as describing DIFFERENT INPUTS. Both sides are `equity/start - 1`
#: off the same snapshot, so agreement is exact up to one tick of equity drift; the failure this
#: catches was 68 percentage points wide. A NUMERIC tolerance on a ratio, not a clock.
_RAIL_DD_TOL_PCT = 1.0


def check_rail_verdict_published(defects) -> None:
    """THE RAIL VERDICT EVERY CONSUMER READS MUST BE ONE SOMETHING ACTUALLY EVALUATED (R0364).

    `web/cashcarry_live.json["risk"]` is the desk's published rail state: the dashboard renders it,
    `check_idle_cost` prices the clamp from it, and a human reads `action` to decide whether the
    book is stopped. It is published by `_emit` as `rb.get("risk")` -- a key set ONLY by
    `_rebalance`. Two ways that lies, and NOTHING could tell either from a healthy verdict:

      ABSENT   On any tick that did not rebalance, `rb` is `_book_snapshot()`, which has no "risk"
               key at all, so `_emit` publishes `"risk": null`. At `--interval 600` against a 60s
               heartbeat that is ~9 ticks in 10. `check_idle_cost` reads `live.get("risk") or {}`
               -> action "" -> the rail clamp is recorded INACTIVE and priced at zero, so a live
               pause is invisible to the one fence built to price it.
      STALE    When `_rebalance` stops completing, the last block it set is copied forward every
               tick onto a file whose mtime keeps advancing. Measured 2026-08-05: the feed was
               fresh at 08:52Z carrying `dd_from_start_pct -17.64 / pause_opens`, which reproduces
               ONLY against the RAW inception, while the running code computes +50.90 against the
               ledgered one -- and `last_combined_equity_at` sat 11 hours behind a process that
               republishes every 600s. A frozen pause verdict was steering the dashboard, the
               pager and the Gate-0 clock.

    This is the desk's oldest lesson pointed at a rail: A HEARTBEAT PROVES THE LOOP IS ALIVE, NEVER
    THAT THE PIPE IS. The feed's own freshness is the heartbeat and it stayed green through both.

    So the check does what R0364 asked for and compares the RECOMPUTED decision against the
    published one, rather than asking either how old it is -- an age bound would need a threshold
    and would still pass a verdict that was fresh and wrong. Only the RUIN channel is compared:
    `dd_start = equity/start - 1` depends on nothing this monitor omits, while the pause and
    breach channels take `flow_adjusted_equity` and `venue_equity` that only the executor holds,
    so comparing `action` outright would fire on a venue breach that is entirely correct.

    Reports; changes nothing. Reads that fail leave it SILENT -- an unmeasurable feed must never
    manufacture a rail defect (the 07-26 "no measurement beats a confident wrong one" lesson).
    """
    feed = ROOT / "web/cashcarry_live.json"
    st_p = ROOT / "data/cashcarry_positions.json"
    if not (feed.exists() and st_p.exists()):
        return
    try:
        from libs.risk import capital_events
        fd = json.loads(feed.read_text("utf-8"))
        st = json.loads(st_p.read_text("utf-8"))
    except Exception:
        return
    fut_leg = fd.get("fut_leg_net")
    if fut_leg is None:                       # futures equity unmeasured this tick -> stay silent
        return
    try:
        start = capital_events.effective_start_equity(float(st["start_futures_equity"]))
        eq_c = start + float(fut_leg) + float(st.get("realized_spot_pnl", 0.0))
        dd_start_pct = (eq_c / max(1e-9, start) - 1.0) * 100.0
    except (KeyError, TypeError, ValueError):
        return
    risk = fd.get("risk")
    if not isinstance(risk, dict):
        defects.append((
            "rail-verdict-absent",
            f"NO RAIL VERDICT IS PUBLISHED: web/cashcarry_live.json carries `risk: {risk!r}` on a "
            f"feed that is otherwise current (n_carries={fd.get('n_carries')}, equity "
            f"${eq_c:,.2f}). `_emit` publishes `rb.get('risk')` and only `_rebalance` sets that "
            f"key, so every non-rebalance tick republishes the whole book with the rail state "
            f"blanked. Downstream cannot tell this from 'no breach': check_idle_cost reads "
            f"`live.get('risk') or {{}}` and prices the clamp at zero. UNMEASURED IS NOT OK "
            f"(L1.28a) -- the executor must publish the last EVALUATED decision with the time it "
            f"was evaluated, or publish an explicit UNEVALUATED marker."))
        return
    pub = risk.get("dd_from_start_pct")
    if pub is None:
        return
    try:
        gap = abs(float(pub) - dd_start_pct)
    except (TypeError, ValueError):
        return
    if gap > _RAIL_DD_TOL_PCT:
        defects.append((
            "rail-verdict-stale",
            f"THE PUBLISHED RAIL VERDICT DISAGREES WITH ITS OWN INPUTS by {gap:.2f} points: the "
            f"feed says dd_from_start {float(pub):+.2f}% / action {risk.get('action')!r}, and "
            f"recomputing it from the SAME snapshot against the ledgered inception "
            f"(${start:,.2f}) gives {dd_start_pct:+.2f}%. `_emit` copies `rb['risk']` forward "
            f"every tick, so a `_rebalance` that stops completing publishes a FROZEN verdict onto "
            f"a file whose mtime keeps advancing -- state last stamped "
            f"{st.get('last_combined_equity_at')!r}. The dashboard, the pager and the idle-cost "
            f"clamp price are all reading a rail nothing is recomputing. Do NOT re-baseline "
            f"anything: find why _rebalance stopped writing."))


DOCTRINE = ROOT / "ops/principal_doctrine.txt"

# Duties that must reach EVERY organ, not just the brain. The list is explicit rather than
# inferred: a heuristic would either miss a renamed duty or nag about the many duties that are
# CORRECTLY brain-only (audit coverage, red-team panels, risk-path depth, the independence gate).
# REPOINTED 2026-08-26 (gap-fixer): the 08-25 consolidation moved every one of these into
# LAWS.md/RESEARCH.md under the canon's own phrasing, and this check kept demanding the OLD
# all-caps names from the OLD single file -- accusing the correct post-consolidation doctrine
# (the same failure the constitution-not-injected detector had, fixed the same way). The shared
# surface is now the UNION of what organs inject/read (LAWS §7: brain_env injects the sealed
# doctrine AND LAWS.md; research organs open RESEARCH.md as their first standing order), and
# each token below is the consolidated canon's own distinctive name, matched case-insensitively.
_UNIVERSAL = (
    ("PROACTIVE BATTERY DUTY", "adversarial battery"),          # RESEARCH §8, masters 187-207
    ("NO-ORPHANED-RECOMMENDATION LAW", "no orphaned recommendation"),
    ("NOVELTY GATE", "novelty gate"),
    ("TARGET/HORIZON SWEEP DUTY", "target-horizon cell is a dsr-counted trial"),
    ("RESEARCH-MEMORY DUTY", "research memory"),
    ("FREE-FIRST DATA PROTOCOL", "free-first"),
    ("BLIND-SPOT ORIGIN DUTY", "blind-spot origin"),
    ("FINDING LIFECYCLE DUTY", "findings lifecycle"),
    ("SELF-INTERROGATION DUTY", "self-interrogation"),
    ("TWO-STAGE DISCOVERY LAW", "two-stage discovery law"),
    ("SCREEN-ON-DISCOVERY DUTY", "screen-on-discovery"),
    ("MINING-NEVER-REGRESSES LAW", "mining-never-regresses"),
    ("NO-CEILING AXIOM", "no-ceiling"),
    ("FREE-FRONTIER AXIOM", "free-frontier"),
    ("DATA-UTILIZATION", "data-utilization"),
)
#: The injected/read shared surface (LAWS §7). ALL of these must exist and together carry
#: every universal duty; principal_doctrine.txt alone is the sealed core, not the whole law.
_SHARED_SURFACE = ("ops/principal_doctrine.txt", "docs/LAWS.md", "docs/RESEARCH.md")


def check_universal_doctrine(defects) -> None:
    """Every universal duty must live in the SHARED doctrine, and every organ must inject it.

    ORIGIN (2026-07-26): the doctrine ordered every digger to screen new axes (SCREEN-ON-DISCOVERY)
    while the rules that keep screening honest -- novelty gate, target/horizon trial accounting,
    research-memory -- lived only in the brain's own prompt. Diggers were commanded to do the
    dangerous half of the job without the discipline that makes it safe. A universal law parked in
    one organ's prompt is not a law, it is a local habit.
    """
    absent = [p for p in _SHARED_SURFACE if not (ROOT / p).exists()]
    if absent:
        defects.append(("doctrine-missing",
                        f"shared-surface document(s) gone: {', '.join(absent)} -- every organ "
                        "injects/reads these as standing law (LAWS §7), so the desk is running "
                        "with a hole in its constitution"))
        return
    txt = "".join((ROOT / p).read_text("utf-8", errors="ignore")
                  for p in _SHARED_SURFACE).lower()
    missing = [label for label, token in _UNIVERSAL if token not in txt]
    if missing:
        defects.append(("doctrine-universal-missing",
                        f"universal duties absent from the shared doctrine surface "
                        f"({' + '.join(_SHARED_SURFACE)}): {', '.join(missing)}. "
                        "These bind every organ; if one lives only in a single organ's prompt, "
                        "every other organ operates without it -- which is how diggers came to be "
                        "ordered to screen axes with no novelty gate or trial accounting."))
    # A duty is only universal if every reasoning organ actually injects the doctrine.
    naked = []
    for sh in sorted(ROOT.glob("ops/run_*.sh")):
        body = sh.read_text("utf-8", errors="ignore")
        if re.search(r"claude .*(-p|--append-system-prompt)", body) and "_DOCTRINE" not in body:
            naked.append(sh.name)
    if naked:
        defects.append(("doctrine-not-injected",
                        f"reasoning organs invoking claude WITHOUT the doctrine: {naked}. "
                        "An organ that does not inject it is exempt from every standing law the "
                        "desk has, silently."))


# Checks DEFINED BELOW the CHECKS literal must be registered here -- appending them up there is a
# NameError, which is exactly how four of them ended up dead. Keep the order explicit (the list is
# the run order); `check_registry_complete` below is what makes a future omission impossible.
def check_route_shaped_identity(defects) -> None:
    """A frozen IDENTITY field that names a FILE, HOST or PATH describes the pipe, not the water.

    Origin (2026-08-26, self-found): `shadow_forward` froze `data_venue = str(bars.source)` -- the
    ROUTE the bars arrived by -- into every sleeve identity. On the Linux VPS `MetaTrader5` is not
    importable, so every run read the parquet cache, every run "drifted", and an identity break is
    TERMINAL. 195 IDENTITY BROKEN lines with data_venue named in 195/195: the 14-day forward
    window never survived one day and nothing could ever reach promotion. Each break looked like
    the gate correctly doing its job, which is why nothing surfaced it.

    The check is the angle in the patterns file, mechanised: read the frozen identities and flag
    any value that contains a path separator, a file extension or a cache/route verb. Those are
    transport facts. A venue, a model, a dataset or a venue-server name is not one.
    """
    reg = ROOT / "desks/mt5/data/sleeve_registry.json"
    if not reg.exists():
        return
    try:
        rows = (json.loads(reg.read_text("utf-8")).get("sleeves") or {})
    except (OSError, ValueError):
        return
    bad: list[str] = []
    for key, row in rows.items():
        ident = row.get("identity") or {}
        for field, value in ident.items():
            if field == "sleeve_id" or not isinstance(value, str):
                continue
            low = value.lower()
            if (low.startswith(("cache:", "file:", "path:"))
                    or "/" in value or "\\" in value
                    or low.endswith((".parquet", ".json", ".csv"))):
                bad.append(f"{key}.{field}={value!r}")
    if not bad:
        return
    defects.append(("route-shaped-identity",
            f"{len(bad)} frozen identity field(s) name a RETRIEVAL ROUTE "
            f"rather than the thing itself -- {', '.join(sorted(bad)[:4])}. A route in an identity "
            f"field fires on every outage AND is blind to a real change arriving by the same "
            f"route; it is not a stricter gate, it is the wrong quantity. Split the subject from "
            f"the transport (h1_source.Bars.evidence_venue is the worked example), fail the "
            f"subject CLOSED, and version the schema so rows frozen under the old meaning are "
            f"archived and re-windowed rather than silently re-blessed."))


def check_worktree_on_tmpfs(defects) -> None:
    """A git worktree under /tmp is tmpfs -- it is spending RAM, not disk.

    tmpfs mounts are DERIVED from /proc/mounts, not listed -- any mount can be memory.

    Origin (2026-08-26, self-found): CI was RED on committed code with 'KILLED sig9, MemAvailable
    827MB, 495MB of RAM held by files under /tmp (tmpfs)'. The holder was /tmp/lit10-wt, an
    abandoned detached worktree costing 322MB of a 4GB no-swap box -- so the desk-wide safety gate
    was down for a reason no code change could fix and no code review could see. Removing it took
    MemAvailable 1131MB -> 1348MB and CI came back.

    The second hazard is worse than the first and is why this reports rather than stays quiet: the
    same worktree held commit 16a68718 (a full litminer run) reachable from NO branch. tmpfs does
    not survive a reboot, so that work was one power cycle -- or one `worktree remove` -- from
    being gone. TAG THE HEAD BEFORE RECLAIMING, always; verify the tag makes it reachable, then
    remove. Never delete a sibling's worktree that still has uncommitted work; relocate it to real
    disk instead, which fixes the RAM cost with zero data loss.
    """
    try:
        out = subprocess.run(["git", "worktree", "list", "--porcelain"], cwd=ROOT,
                             capture_output=True, text=True, timeout=30)
    except (OSError, subprocess.SubprocessError):
        return
    if out.returncode != 0:
        return
    paths = [ln.split(" ", 1)[1].strip() for ln in out.stdout.splitlines()
             if ln.startswith("worktree ")]
    # Derived, never hardcoded: /tmp and /dev/shm are the usual tmpfs mounts on this box, but the
    # property that matters is "this filesystem IS memory", and any mount can be one. A literal
    # list here would be a boundary silently capping the sweep (the anti-hardcode law).
    ram_mounts: list[str] = []
    try:
        for line in Path("/proc/mounts").read_text("utf-8").splitlines():
            parts = line.split()
            if len(parts) >= 3 and parts[2] in ("tmpfs", "ramfs"):
                ram_mounts.append(parts[1].rstrip("/") + "/")
    except OSError:                              # pragma: no cover -- non-Linux
        return
    if not ram_mounts:
        return
    offenders: list[str] = []
    for raw in paths:
        wt = Path(raw)
        if not str(wt).startswith(tuple(ram_mounts)) or not wt.exists():
            continue
        try:
            head = subprocess.run(["git", "rev-parse", "HEAD"], cwd=wt,
                                  capture_output=True, text=True, timeout=30).stdout.strip()
            reach = subprocess.run(["git", "branch", "-a", "--contains", head], cwd=ROOT,
                                   capture_output=True, text=True, timeout=60).stdout
            size = subprocess.run(["du", "-sm", str(wt)], capture_output=True, text=True,
                                  timeout=120).stdout.split("\t")[0].strip()
        except (OSError, subprocess.SubprocessError, IndexError):
            continue
        named = [b for b in reach.splitlines() if b.strip() and "(no branch)" not in b]
        orphan = "" if named else " and its HEAD is reachable from NO BRANCH -- TAG IT FIRST"
        offenders.append(f"{wt} (~{size}MB of RAM, HEAD {head[:8]}{orphan})")
    if offenders:
        defects.append((
            "worktree-on-tmpfs",
            f"{len(offenders)} git worktree(s) live on tmpfs, so they cost RAM on a 4GB no-swap "
            f"box and do NOT survive a reboot: {'; '.join(offenders)}. This is how CI died on "
            "2026-08-26 -- a resource failure no code review could see and no code change could "
            "fix. Reclaim it, but TAG the HEAD and verify reachability BEFORE removing; if it "
            "holds uncommitted work, relocate it to real disk rather than deleting it."))


def check_sync_launder(defects) -> None:
    """Code a one-way sync reverted and nobody put back -- DERIVED, so no file falls through.

    The Dell's hourly sync scp's its copy over desks/mt5 and commits it here over ssh. Two
    defences exist and both are LIST-shaped: the pre-commit guard is future-tense (it works --
    no mt5 sync commit has carried a .py change since 2026-08-26 02:02), and the content fence
    restores only files somebody already added to its hand-maintained PROTECTED map.

    MEASURED 2026-08-28: desks/mt5/research/regime_monitor.py lost 122 of 149 lines -- the GAP 130
    shadow-replay wake -- to a sync two hours after it shipped, and sat dead in HEAD for two days
    with its 5 tests inside a 25-test CI red nobody traced. It was invisible for one reason: it
    was in no list. A registry of files already damaged cannot name the file about to be, and
    every entry in it was bought with the loss it was meant to prevent.

    Reads the artifact rather than re-deriving it (the walk is a few hundred `git show` calls);
    the producer is scripts/check_sync_launder.py, wired to run before this. Only CLEAN-REVERT
    rows are defects: a REVIEW row cannot be closed mechanically -- it needs two versions of a
    rewritten file read by a mind -- and a red nobody can act on gets skimmed and buries a real
    one, which is the lesson check_ci_gate already carries in its own body.
    """
    # PRODUCER AND CONSUMER ON ONE SCHEDULE, so they cannot rot apart. The manifest has 120 rows
    # with no scheduler since the 08-20 cron death; adding a 121st would be wiring an organ to a
    # dead clock and calling it done. The walk is a few hundred `git show` calls -- refreshed at
    # most once a day, bounded, and a failure leaves the previous artifact rather than a lie.
    art = ROOT / "data" / "sync_launder.json"
    stale = (not art.exists()) or (NOW - art.stat().st_mtime) > 20 * 3600
    if stale:
        with contextlib.suppress(OSError, subprocess.SubprocessError):
            subprocess.run([sys.executable, str(ROOT / "scripts" / "check_sync_launder.py")],
                           cwd=ROOT, capture_output=True, text=True, timeout=600, check=False)
    if not art.exists():
        return
    try:
        rows = json.loads(art.read_text("utf-8")).get("residue") or []
    except (OSError, json.JSONDecodeError, TypeError):
        return
    clean = [r for r in rows if r.get("verdict") == "CLEAN-REVERT"]
    if clean:
        named = ", ".join(f"{r['file']} ({r['lines_lost']} lines, {r['sync_commit']})"
                          for r in clean[:4])
        defects.append(("sync-launder",
                        f"{len(clean)} file(s) still carry authored code a SYNC commit reverted "
                        f"and nothing restored: {named}. Each is desk work that reached HEAD, was "
                        "overwritten by a one-way push, and is being run in its stale form right "
                        "now. Heal with scripts/check_sync_launder.py --heal (previous bytes are "
                        "quarantined), then commit."))
    review = [r for r in rows if r.get("verdict") == "REVIEW"]
    if len(review) > 12:
        defects.append(("sync-launder-review-backlog",
                        f"{len(review)} file(s) carry sync-removed lines that a later rewrite may "
                        "or may not have superseded -- nothing mechanical can tell those apart. "
                        "The backlog is only worth reporting when it grows: read the samples in "
                        "data/sync_launder.json and close each one with a judgement."))


CHECKS += [
           ("close-retry-loop", check_close_retry_loop),
           ("paid-target-registry", check_paid_target_registry),
           ("holdings-ratchet", check_holdings_never_shrink),
           ("book-absorbing-state", check_book_absorbing_state),
           ("rail-verdict-published", check_rail_verdict_published),
           ("universal-doctrine", check_universal_doctrine),
           ("route-shaped-identity", check_route_shaped_identity),
           ("worktree-on-tmpfs", check_worktree_on_tmpfs),
           ("sync-launder", check_sync_launder)]


#: Every reasoning organ. An organ that does not carry the constitution is optimising for
#: something -- it just is not the desk's objective, and nothing in its output will say so.
_CONSTITUTION_ORGANS = ("run_external_panel", "hypothesis_generator", "breadth_expander",
                        "llm_code_auditor", "meta_architect", "llm_blind_researcher",
                        "collector_author", "deep_review", "run_micro_audit",
                        # added at the 2026-08-04 merge: this branch's organs, caught by the
                        # sibling's coverage net (they held the panel keys with no objective)
                        "kimi_hunter", "run_strategic_director",
                        # caught by the panel-keys net 2026-08-11: both send reasoning prompts
                        "gpt_hunter", "run_survivor_panel")


def _carries_objective(script: Path) -> bool:
    """Does this organ's prompt carry the objective -- in the script, or one hop into `libs/`?

    A FLAT GREP ON scripts/ WAS WRONG IN BOTH DIRECTIONS, and the second direction is the one that
    matters. `run_strategic_director` builds its prompt in `libs.research.strategic_director.
    build_prompt`, so the preamble is correctly injected and the grep would have called it NAKED
    forever. A fence that reports a defect which cannot be cleared is a fence that gets ignored --
    this desk has already retired two for exactly that ("Two fences that cried wolf").

    ONE HOP, NOT A FULL IMPORT GRAPH. The prompt of an organ lives either where the organ is or in
    the module it delegates prompt-building to; chasing transitively would start finding the string
    in unrelated dependencies and turn a specific check into one that can never go red.
    """
    src = script.read_text("utf-8", errors="ignore")
    if "OBJECTIVE_PREAMBLE" in src:
        return True
    for mod in re.findall(r"^from (libs[.\w]+) import", src, re.M):
        p = ROOT / (mod.replace(".", "/") + ".py")
        if p.exists():
            with contextlib.suppress(OSError):
                if "OBJECTIVE_PREAMBLE" in p.read_text("utf-8", errors="ignore"):
                    return True
    return False


def check_constitution(defects) -> None:
    """THE OBJECTIVE, ITS RATCHET, AND ITS REACH (principal 2026-08-01).

    max_pi E[log W_T] is the desk's sole objective; validated information gain, validated alpha
    and realized CAGR are subordinate measures. Three failure modes, all checked here:

      REACH. An organ that does not inject the constitution is optimising for SOMETHING -- the
      shape of a good-looking answer, the reviewer's instinct for caution, whatever its training
      leans toward -- and nothing in its output will announce which. Same class as
      `doctrine-not-injected`: a law parked in one organ's prompt is a local habit.

      THE RATCHET. Every principle carries an aggression rank with a high-water mark on disk that
      code only ever RAISES. A rank that fell means the constitution was weakened, and weakening
      is meant to cost a hand-edit of a file named CONSTITUTION_RATCHET -- deliberate, dated and
      visible -- because institutions do not vote to become timid, they drift there one
      reasonable-sounding amendment at a time.

      VOCABULARY. Weakening phrases used rather than named. This catches the accidental kind and
      cannot catch a determined one; the ratchet is what covers the rest.
    """
    try:
        from libs.doctrine import ratchet as _ratchet
        from libs.doctrine.constitution import OBJECTIVE, weakening_language
        from libs.doctrine.constitution import governance_balance as _governance_balance
    except ImportError as e:                      # pragma: no cover - the desk has no objective
        defects.append(("constitution-unimportable",
                        f"libs.doctrine will not import ({e}) -- the desk's sole objective is "
                        "unavailable to every organ that injects it, and to this check"))
        return

    naked = []
    for name in _CONSTITUTION_ORGANS:
        p = ROOT / "scripts" / f"{name}.py"
        if not p.exists():
            continue
        with contextlib.suppress(OSError):
            if not _carries_objective(p):
                naked.append(name)
    if naked:
        defects.append((
            "constitution-not-injected",
            f"{len(naked)} reasoning organ(s) run WITHOUT the constitution: {', '.join(naked)}. "
            "Each is still optimising something -- the objective just is not stated, so nothing "
            "it proposes can be scored against dE[log W_T]. Prepend "
            "libs.doctrine.constitution.OBJECTIVE_PREAMBLE to its system prompt."))

    doc = ROOT / "ops/principal_doctrine.txt"
    if doc.exists() and OBJECTIVE not in doc.read_text("utf-8", errors="ignore"):
        defects.append((
            "constitution-absent-from-doctrine",
            "ops/principal_doctrine.txt no longer states max_pi E[log W_T]. Every local organ "
            "injects that file as its system prompt, so the desk would be running with an "
            "aggression stance and no objective for it to serve."))
    elif doc.exists() and _ratchet.preamble_in_sync(doc) is False:
        # A prompt cannot import Python, so the doctrine necessarily holds a COPY of the
        # constitution. Copies drift: the module gets edited, the file does not, and every local
        # organ then runs on last month's constitution while this audit enforces this month's.
        # Both look correct in isolation, which is why drift has to be checked rather than noticed.
        defects.append((
            "constitution-doctrine-stale",
            "ops/principal_doctrine.txt carries an OUT-OF-DATE copy of the constitution. Every "
            "local organ injects it, so they are governed by a superseded objective while this "
            "audit enforces the current one. Run libs.doctrine.ratchet.sync_preamble()."))

    rep = _ratchet.check()
    if not rep.ok:
        defects.append((
            "constitution-ratchet-broken",
            "AGGRESSION RATCHET VIOLATED -- " + " | ".join(rep.violations)))
    if not _ratchet.BASELINE_PATH.exists():
        defects.append((
            "constitution-ratchet-missing",
            f"{_ratchet.BASELINE_PATH} is gone. With no high-water mark there is no floor under "
            "any principle, and the next weakening passes silently. Regenerate with "
            "libs.doctrine.ratchet.update_high_water() and commit it."))

    balance = _governance_balance()
    if not balance["balanced"]:
        # THE DRIFT THAT PROMPTED THIS CHECK (principal, 2026-08-01). A constitution can state an
        # aggressive philosophy and encode the opposite one in its mechanics, one defensible
        # amendment at a time. The mechanism is arithmetic rather than intent: a body of law
        # follows its majority, so once restraints outnumber enablers, governance becomes the
        # dominant optimiser however the preamble reads -- and the desk quietly switches from
        # "find as many good things as possible while preventing catastrophe" to "never deploy
        # something bad". Counting is the only way that is visible before it has happened.
        defects.append((
            "governance-asymmetry",
            f"{balance['enablers']} enabling principles vs {balance['guards']} restraining ones. "
            + balance["note"]))

    weak = weakening_language()
    if weak:
        defects.append((
            "constitution-weakening-language",
            "constitutional statements USE weakening language rather than naming it: "
            + ", ".join(f"{pid}:'{ph}'" for pid, ph in weak)))


CHECKS += [("constitution", check_constitution)]


#: Organs that report a coverage/completeness figure. Each must name the NEXT ceiling, because a
#: percentage with no successor reads as a finish line -- and P20 does not recognise one.
_COVERAGE_ORGANS = ("run_allocator", "mine_moat", "calibrate_gauntlet", "run_ancestors")

#: Completion claims. P20: "done", "sufficient", "fully built" and "complete" are status claims
#: this constitution does not recognise for any component -- they are unexamined ceilings.
_COMPLETION_CLAIMS = ("fully built", "nothing left to", "no further work",
                      "feature complete", "work is finished", "nothing more to do")


def check_no_ceiling(defects) -> None:
    """P20 AND P13, ENFORCED EVERYWHERE RATHER THAN WHERE SOMEBODY REMEMBERED (principal
    2026-08-02: "these constitutional laws must apply everywhere anyway regardless").

    A constitutional law that holds only in the module that happens to import it is not a law, it
    is a local habit -- the same finding as universal duties parked in the brain's own prompt and
    the doctrine that six organs injected and three did not. So the two clauses most easily lost
    are checked structurally across every organ that reports progress:

      NO DECLARED COMPLETION. "done", "fully built", "nothing left to do" are unexamined ceilings.
      An organ that says one is not merely optimistic; it has stopped looking, and nothing
      downstream can tell that from having genuinely arrived.

      EVERY COVERAGE FIGURE NAMES ITS SUCCESSOR. A percentage with no next ceiling reads as a
      finish line, and the day it turns green the organ goes quiet -- which is precisely when the
      next constraint becomes binding and precisely when nobody is looking for it.

    Quoted and negated occurrences are exempt, because an organ that FORBIDS a completion claim
    necessarily contains the words -- and a detector that fires on the rule against the thing gets
    switched off within a week, which is strictly worse than no detector.
    """
    claimed, unceilinged = [], []
    for name in _COVERAGE_ORGANS:
        f = ROOT / "scripts" / f"{name}.py"
        if not f.exists():
            continue
        with contextlib.suppress(OSError):
            src = f.read_text("utf-8", errors="ignore")
            # UNCONDITIONAL. An earlier version only asked organs whose source contained the
            # word "coverage", so two progress-reporting organs escaped on a keyword technicality
            # -- which is the same "applies only where somebody remembered" failure the whole
            # check exists to close. Membership of this list IS the trigger.
            if "next_ceiling" not in src:
                unceilinged.append(name)
            for sentence in re.split(r"(?<=[.;])\s+", src):
                low = sentence.lower()
                if any(n in low for n in ("not ", "never", "no ", "does not", "forbid",
                                          "reject", "must not", "cannot")):
                    continue
                quoted = " ".join(re.findall(r"'([^']*)'", low) + re.findall(r'"([^"]*)"', low))
                for claim in _COMPLETION_CLAIMS:
                    if claim in low and claim not in quoted:
                        claimed.append(f"{name}: '{claim}'")
    if claimed:
        defects.append((
            "no-ceiling-violated",
            f"organ(s) declare completion: {', '.join(sorted(set(claimed)))}. P20 does not "
            "recognise 'done' for any component -- a completion claim is an unexamined ceiling, "
            "and an organ that has stopped looking is indistinguishable downstream from one that "
            "genuinely arrived."))
    if unceilinged:
        defects.append((
            "coverage-without-next-ceiling",
            f"organ(s) report a coverage figure and name no successor: {', '.join(unceilinged)}. "
            "A percentage with no next ceiling reads as a finish line, so the organ goes quiet "
            "exactly when it turns green -- which is exactly when the next constraint binds and "
            "nobody is looking for it."))


CHECKS += [("no-ceiling", check_no_ceiling)]


ALLOCATOR_ARTIFACT = ROOT / "data/allocator.json"

#: field in data/allocator.json -> (principle it evidences, what its absence means).
#: PRODUCTION, NOT EXISTENCE. Checking that libs/doctrine imports would prove only that files are
#: on disk; these fields exist only if the allocator actually RAN the corresponding code path, so
#: their absence means the law is unenforced no matter how good the library is.
_GOVERNING_FIELDS: dict[str, tuple[str, str]] = {
    "bottleneck": ("P4", "the binding constraint is not being re-identified each cycle"),
    "why_no_ranking": ("P10", "estimates are not being treated as estimates"),
    "allocation": ("P12", "the global-first allocation never ran"),
    "starved": ("P13", "nothing is watching for permanently-neglected subsystems"),
    "closure_rate": ("P18", "the desk is not measuring the RATE at which it improves"),
    "next_ceiling": ("P20", "the organ has no declared successor and will go quiet when green"),
}


def check_governing_layer_live(defects) -> None:
    """THE GOVERNING LAYER MUST RUN, NOT MERELY EXIST (principal 2026-08-02: every law enforced
    desk-wide, in every interaction, at full coverage -- now and always).

    libs/doctrine/{estimate,allocate,portfolio_law}.py shipped with full test suites and no caller
    for a while, which is the failure this desk keeps finding in itself: a governing layer nothing
    calls governs nothing, and its unit tests stay green the entire time it is inert. So this
    checks the ARTIFACT the allocator produces, field by field, because those fields exist only if
    the corresponding code path actually executed this cycle.

    A missing artifact is the loudest version of the same defect and is reported as such rather
    than skipped -- "the allocator did not run" and "the allocator ran and found nothing" are
    different facts, and only one of them is acceptable.
    """
    if not ALLOCATOR_ARTIFACT.exists():
        defects.append((
            "governing-layer-inert",
            f"{ALLOCATOR_ARTIFACT.name} absent -- the governing layer did not run this cycle, so "
            "P4, P10, P11, P12, P13 and P18 are unenforced. A layer nothing calls governs "
            "nothing, and its unit tests stay green the whole time it is inert."))
        return
    try:
        art = json.loads(ALLOCATOR_ARTIFACT.read_text("utf-8"))
    except (OSError, json.JSONDecodeError) as e:
        defects.append(("governing-layer-unreadable",
                        f"{ALLOCATOR_ARTIFACT.name} will not parse ({e}) -- treated as inert"))
        return
    missing = [(f, pid, why) for f, (pid, why) in _GOVERNING_FIELDS.items() if f not in art]
    if missing:
        defects.append((
            "governing-layer-partial",
            "allocator artifact is missing field(s) that prove a law ran: "
            + "; ".join(f"{f} ({pid}: {why})" for f, pid, why in missing)))
    # P11: the three-verdict rule. Collapsing INSUFFICIENT-EVIDENCE into KEEP or RETIRE loses the
    # one fact that should drive the next action -- go and measure it.
    if "made entirely of guesses" not in str(art.get("why_no_ranking", "")) and not art.get(
            "allocation", {}).get("funded"):
        defects.append((
            "governing-layer-ranked-on-nothing",
            "the allocator produced no funded actions but does not state WHY it refused to rank. "
            "Silence there is indistinguishable from a ranking that happened to be empty, and a "
            "ranking gets acted on."))


CHECKS += [("governing-layer", check_governing_layer_live)]


LAW_COVERAGE_MARK = ROOT / "docs/research/LAW_COVERAGE.json"


def check_law_coverage(defects) -> None:
    """EVERY LAW ENFORCED, MEASURED, AND RATCHETED -- including laws added tomorrow.

    A one-time audit of the principles is a snapshot. The next principle lands with no enforcement
    and nothing notices, because nothing was watching for it. So coverage is a measured fraction
    with a HIGH-WATER MARK, exactly like the aggression ratchet: it may rise freely and a fall
    fails the audit. A new principle defaults to unenforced and therefore DROPS the percentage,
    which is the mechanism that makes "and upcoming always" true of code rather than of intent.

    Two modes are counted separately and are not interchangeable. Mechanical cover is a registered
    check that can go red -- it constrains what gets DONE. Interactional cover is presence in the
    preamble every organ injects -- it constrains what gets PROPOSED. A law with only the second
    is not fully enforced, because a model that ignores the preamble produces a bad recommendation
    and nothing catches it.
    """
    try:
        from libs.doctrine.enforcement import coverage as _law_coverage
        from libs.doctrine.enforcement import unenforced as _law_gaps
    except ImportError as e:                       # pragma: no cover
        defects.append(("law-coverage-unimportable", f"libs.doctrine.enforcement: {e}"))
        return

    registered = {name for name, _ in CHECKS}
    cov = _law_coverage(registered)
    gaps = _law_gaps(registered)

    if cov["phantom"]:
        defects.append((
            "law-enforced-by-phantom-check",
            f"principle(s) claim enforcement by unregistered check(s): {cov['phantom']}. An "
            "unregistered check is a law the desk BELIEVES it is enforcing -- four consecutive "
            "charters shipped exactly that way."))

    dark = [r for r in cov["rows"] if r["mode"] == "NONE"]
    if dark:
        defects.append((
            "law-unenforced",
            f"{len(dark)} principle(s) have NO enforcement of either kind: "
            + ", ".join(f"{r['id']} ({r['name']})" for r in dark)
            + ". A law nothing can detect a violation of is not a law."))

    prev = {}
    with contextlib.suppress(OSError, json.JSONDecodeError):
        prev = json.loads(LAW_COVERAGE_MARK.read_text("utf-8")).get("high_water", {})
    regressed = [k for k in ("mechanical_pct", "interactional_pct", "full_pct")
                 if float(prev.get(k, 0.0)) > float(cov[k])]
    if regressed:
        defects.append((
            "law-coverage-regressed",
            "law enforcement coverage FELL: "
            + "; ".join(f"{k} {prev[k]} -> {cov[k]}" for k in regressed)
            + ". Coverage ratchets like aggression does: it may rise freely, and a fall is either "
            "a law that lost its check or a new law nobody enforced -- both are defects."))

    # High-water mark only ever rises, by the same asymmetry the aggression ratchet uses.
    #
    # WRITTEN ONLY WHEN SOMETHING ACTUALLY CHANGED. This previously rewrote the file on every
    # invocation, moving `updated` while every mark stayed identical -- so any audit run dirtied a
    # tracked file with no information in the diff. That is not cosmetic: a repository where
    # running the auditor always produces a change trains whoever commits to `git add -A` without
    # reading, and the one time the diff DOES carry a regression it goes through with the noise.
    # A ratchet's timestamp should mean "this is when the mark moved", not "this is when somebody
    # looked" -- the same distinction that made min_snapshots an unsound gate two commits ago.
    _new_hw = {k: max(float(prev.get(k, 0.0)), float(cov[k]))
               for k in ("mechanical_pct", "interactional_pct", "full_pct")}
    _live_now = {k: cov[k] for k in ("principles", "both", "mechanical_only",
                                     "interactional_only", "unenforced",
                                     "mechanical_pct", "interactional_pct", "full_pct")}
    _prev_live = {}
    with contextlib.suppress(OSError, json.JSONDecodeError):
        _prev_live = json.loads(LAW_COVERAGE_MARK.read_text("utf-8")).get("live", {})
    if _new_hw == prev and _live_now == _prev_live and LAW_COVERAGE_MARK.exists():
        return
    with contextlib.suppress(OSError):
        LAW_COVERAGE_MARK.parent.mkdir(parents=True, exist_ok=True)
        LAW_COVERAGE_MARK.write_text(json.dumps({
            "_": ("HIGH-WATER MARK for constitutional enforcement coverage. Raised automatically, "
                  "never lowered by code. A NEW principle defaults to unenforced and therefore "
                  "drops the live percentage below this mark -- which is the mechanism that makes "
                  "'every law, now and upcoming' true of code rather than of intention."),
            "updated": datetime.now(tz=UTC).isoformat(),
            "high_water": {k: max(float(prev.get(k, 0.0)), float(cov[k]))
                           for k in ("mechanical_pct", "interactional_pct", "full_pct")},
            "live": {k: cov[k] for k in ("principles", "both", "mechanical_only",
                                         "interactional_only", "unenforced",
                                         "mechanical_pct", "interactional_pct", "full_pct")},
            "gaps_worst_first": [{"id": g["id"], "name": g["name"], "aggression": g["aggression"],
                                  "mode": g["mode"]} for g in gaps],
            "next_ceiling": ("every law mechanically enforced AND in every interaction. Reaching "
                             "that is not completion -- the next ceiling is enforcement that "
                             "catches SUBTLE violations, not only absent ones."),
        }, indent=1), "utf-8")


def check_evig_ranking(defects) -> None:
    """P1: the funnel must ORDER by expected shift in E[log W], not by generator emission order.

    Before 2026-08-02 the screen emitted candidates in whatever order the generator produced them,
    so L4 compute -- the scarcest resource on this desk -- was allocated by accident of ordering.
    EVIG existed as a fully-tested library that nothing called for weeks, which is the same
    "built but never runs" class as the governing layer.

    Checked on the ARTIFACT, because that is the only thing that proves the path ran. The floor is
    also audited for BITE: with the desk's true base rate every candidate can fall below the
    absolute compute floor, and a ranking that marks everything not-worth-compute is a FILTER
    wearing a ranking's clothes -- which EVIG has no authority to be.
    """
    art = ROOT / "data/gauntlet_candidates.json"
    src = ROOT / "scripts/hypothesis_screen.py"
    if src.exists() and "rank_by_evig" not in src.read_text("utf-8", errors="ignore"):
        defects.append((
            "evig-not-wired",
            "hypothesis_screen does not rank by EVIG -- L4 compute is allocated by the order the "
            "generator happened to emit candidates in, which is P1 unenforced."))
        return
    if not art.exists():
        return                       # no run yet; the funnel's own producer check owns that gap
    with contextlib.suppress(OSError, json.JSONDecodeError):
        cands = json.loads(art.read_text("utf-8")).get("candidates", [])
        scored = [c for c in cands if c.get("evig_scored")]
        if cands and not scored:
            defects.append((
                "evig-scored-nothing",
                f"{len(cands)} candidate(s) survived the screen and NONE carries an EVIG score. "
                "Ranking by nothing is ranking by the generator's emission order."))
        elif scored and not any(c.get("floor_not_discriminating") for c in scored) and not any(
                c.get("worth_compute") for c in scored):
            defects.append((
                "evig-floor-silently-buried-everything",
                "every scored candidate is below the compute floor and the artifact does not say "
                "the floor stopped discriminating. A ranking that buries everything IS a filter, "
                "and a blanket 'not worth compute' would read as a considered per-candidate "
                "verdict when it is a statement about the desk's base rate."))


#: Organs that DETECT defects and must therefore carry a fix path (P25). The pager is the one
#: legitimate pure notifier on the desk -- its whole job is to reach a human -- and it is exempt
#: by name rather than by keyword, so nothing else can claim the exemption by resembling it.
_DETECTOR_ORGANS = ("watch_pnl", "run_allocator", "mine_moat")
_PURE_NOTIFIER_EXEMPT = ("run_alerts", "seats")

#: A finding must resolve into one of these. "investigate", "monitor" and "escalated" are not
#: outcomes -- a defect parked in one is an excuse with a ticket number.
_FIX_TIERS = ("AUTOFIX", "PATCH_READY", "BLOCKED")


def check_fixers_not_watchers(defects) -> None:
    """P25: EVERY DETECTOR CARRIES A FIX PATH (principal 2026-08-02: everything here is a fixer,
    not a notifier -- only the pager may merely notify).

    A monitor that finds a defect and leaves it open is worse than no monitor. The desk then has
    the defect AND the false comfort of watching it, and the attention the alarm consumes every
    cycle is a real recurring cost bought against nothing. So a detector must resolve each finding
    into AUTOFIX, PATCH_READY or BLOCKED -- applied now, the exact patch named and chased, or the
    exact measurement that determines the fix, also chased.

    Checked structurally, because a convention that lives only in a commit message decays the
    first time somebody adds an organ -- this desk has watched exactly that happen with seat caps,
    with the doctrine injection, and with the coverage keyword escape hatch three commits ago.
    """
    watchers, stale_blind = [], []
    for name in _DETECTOR_ORGANS:
        f = ROOT / "scripts" / f"{name}.py"
        if not f.exists():
            continue
        with contextlib.suppress(OSError):
            src = f.read_text("utf-8", errors="ignore")
            if not any(t in src for t in _FIX_TIERS):
                watchers.append(name)
            if "cycles_open" not in src and "cycles_owed" not in src:
                stale_blind.append(name)
    if watchers:
        defects.append((
            "detector-without-fix-path",
            f"organ(s) DETECT defects and carry no fix path: {', '.join(watchers)}. A monitor "
            "that finds a defect and leaves it open is worse than no monitor -- the desk gets the "
            "defect AND the false comfort of watching it. Resolve each finding into AUTOFIX, "
            "PATCH_READY or BLOCKED; only the pager may notify without repairing."))
    if stale_blind:
        defects.append((
            "detector-cannot-age-its-findings",
            f"organ(s) cannot tell a three-week-old defect from this morning's: "
            f"{', '.join(stale_blind)}. Without a per-finding age counter that only CLOSING "
            "clears, a standing leak looks like a fresh finding every cycle, which is precisely "
            "how a monitor becomes wallpaper."))


#: artifact -> (label, the dedicated organ that closes it). Every owned dataset the desk can
#: measure coverage of. Adding a dataset here without a closing organ is itself the breach P26
#: describes: a measure with nothing driving it is a number that watches itself stand still.
_EXPLORATION_SURFACES: dict[str, tuple[str, str]] = {
    "data/moat_mine.json": ("moat (self-recorded order books)", "ops/run_moat_miner.sh"),
}

def check_under_exploration(defects) -> None:
    """P26: an owned dataset below 100% explored is a BREACH, and the breach is the gap NOT
    CLOSING (principal 2026-08-02: "underexploration of anything is violation of law").

    THE DISTINCTION IS THE WHOLE CHECK. A gap that is closing is work in progress and firing on
    it would train everyone to ignore the alarm. A gap that is STANDING STILL is the desk
    declining edge it has already paid for -- and those look identical in any single snapshot,
    which is why coverage has to be trended rather than read.

    That distinction used to be a docstring. This check fired on every reading below 100% and the
    constant that was supposed to implement the trend was never referenced anywhere -- so the desk
    got the same red line whether the miner was converging in hours or had been dead for a week,
    which is precisely the alarm everyone learns to ignore. The decision now reads the miner's own
    `closure` field, computed over recorded history with a standard error, and every branch below
    is a DIFFERENT defect with a different fix:

      CLOSING               -- not a defect. Work in progress.
      STANDING-STILL        -- the P26 breach in its pure form: mine it.
      OUTPACED-BY-RECORDING -- cells rising, percentage not. The miner works and the archive grows
                               faster than it mines; the fix is more miner, and calling this
                               neglect would send the desk chasing a motivation problem it has not
                               got.
      UNKNOWN               -- fewer than three recorded runs. Reported as unmeasured rather than
                               guessed, because a slope through two points is not evidence.

    Zero coverage with a named blocker is reported distinctly from zero coverage with none: "the
    recorders have written nothing" is an actionable fact about a different organ, while "we have
    data and are not mining it" is this breach in its pure form.
    """
    for artifact, (label, organ) in _EXPLORATION_SURFACES.items():
        p = ROOT / artifact
        if not p.exists():
            defects.append((
                "exploration-unmeasured",
                f"{label}: {artifact} absent -- coverage is not even MEASURED, so the desk cannot "
                f"tell 'mined and empty' from 'never looked'. Run {organ}."))
            continue
        try:
            d = json.loads(p.read_text("utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        cov = d.get("cumulative_coverage", {}).get("coverage_pct", d.get("coverage_pct"))
        if cov is None or float(cov) >= 100.0:
            continue
        # A dedicated continuous miner must EXIST, or nothing is driving the number at all.
        if not (ROOT / organ).exists():
            defects.append((
                "exploration-has-no-dedicated-organ",
                f"{label} sits at {cov}% and {organ} does not exist. A cadence step is the FLOOR; "
                "continuous mining is the ceiling, and without it coverage converges in as many "
                "days as there are cycles instead of in hours."))
        if d.get("state") == "NO MINE ON DISK":
            defects.append((
                "exploration-blocked-upstream",
                f"{label}: 0% and the blocker is UPSTREAM -- {d.get('reason', '')[:150]} This is "
                "distinct from declining to mine: no mining action closes it, and the named "
                "producer is the only thing that can."))
            continue
        closing = d.get("closure") or {}
        state = str(closing.get("state", "UNRECORDED"))
        why = str(closing.get("why", ""))
        # THE ARCHIVE'S DEADLINE, CHECKED BEFORE THE COVERAGE VERDICT. Disk exhaustion is the one
        # failure that makes a GOOD number appear: the recorders pause, the grid stops growing,
        # and the miner closes the last holes in a frozen denominator all the way to 100%. Read
        # as a finish line, that retires the chase at the moment the asset stops accumulating.
        disk = closing.get("disk") or {}
        if disk.get("state") in ("URGENT", "PAUSED"):
            defects.append((
                "tape-disk-deadline",
                f"{label}: {disk.get('note', '')} Deleting mined tape does NOT close this -- the "
                "seven reconstructions are the first seven, not the last, so raw tape must stay "
                "re-readable. Buy storage; every hour past the pause is permanently unbuyable."))
        if state == "RECORDING-STOPPED":
            # A tape that stopped because the desk SWITCHED IT OFF is a recorded decision, not a
            # stall (see _recorder_pause_reason). Without this, the principal's own ACCEPT path in
            # data/PRINCIPAL_ACTION.md fires an unclearable defect for as long as the retirement
            # holds -- and under the MT5 mandate that retirement is PERMANENT, so this defect
            # would have fired forever on a decision the desk deliberately made. Restored
            # 2026-08-26 from 3da91a1d, whose checks landed here while this half never did.
            # The frozen-denominator warning still stands and is still said.
            if _recorder_pause_reason() == "SWITCHED-OFF":
                defects.append((
                    "tape-retired-coverage-frozen",
                    f"{label}: recording is OFF by decision (data/RECORDERS_OFF present). That is "
                    "not a stall -- but coverage is filled/total over a FROZEN grid, so any "
                    "coverage number from this surface is now meaningless and must not be read "
                    "as progress (L1.65: a gauge denominated in what survives cannot see a loss)."))
                continue
            defects.append((
                "tape-recording-stopped",
                f"{label}: {why} This outranks every coverage finding: coverage is filled/total "
                "and a frozen total makes the ratio rise on its own."))
            continue
        if state in ("CLOSING", "COMPLETE-FOR-THIS-GRID"):
            continue
        if state == "OUTPACED-BY-RECORDING":
            defects.append((
                "exploration-outpaced-by-recording",
                f"{label} at {cov}%: {why} Raise miner throughput -- run {organ} with a shorter "
                "--interval or a larger per-run file budget. This is NOT a neglect finding and "
                "must not be closed by asserting the miner is running; it already is."))
            continue
        if state == "UNRECORDED":
            defects.append((
                "exploration-rate-unmeasured",
                f"{label} at {cov}% and the artifact carries no `closure` field -- the desk can "
                "read the LEVEL but cannot tell a gap converging in hours from one that has stood "
                f"still for a week. Re-run {organ} on a build that records coverage history."))
            continue
        if state == "UNKNOWN":
            defects.append((
                "exploration-rate-unmeasured",
                f"{label} at {cov}%: {why} Run {organ} continuously so the rate becomes "
                "measurable; until then the level is a status line, not a verdict."))
            continue
        defects.append((
            "under-exploration",
            f"{label} explored {cov}% and the gap is NOT CLOSING -- P26 breach. {why} Verify "
            f"{organ} is running continuously; a standing coverage number is edge the desk has "
            "already paid for and is declining to collect."))


def check_coexistence(defects) -> None:
    """P16: no sleeve, family or engine may cost another its growth (principal 2026-08-02).

    Two rules, and conflating them loses the harder one. NOBODY SUBTRACTS: a family is judged by
    its marginal contribution to the portfolio, never its standalone record, because ranking on
    standalone Sharpe builds a book of correlated winners -- one bet wearing five names. EVERYBODY
    MAXES: after the global optimum, each family expands to its own maximum feasible point, so a
    family that could grow and does not is an optimisation failure rather than a tidy book.

    Checked on the ARTIFACT. A DORMANT verdict is acceptable and expected -- MC_i is undefined
    with one family -- but the organ must have RUN, and it must still carry the separation ladder
    while dormant, because the ORDER (orthogonality before retirement) binds immediately and needs
    no data to be in force.
    """
    art = ROOT / "data/coexistence.json"
    if not art.exists():
        defects.append((
            "coexistence-never-measured",
            "data/coexistence.json absent -- nothing checks whether one family is costing another "
            "its growth. Run scripts/run_coexistence.py."))
        return
    try:
        d = json.loads(art.read_text("utf-8"))
    except (OSError, json.JSONDecodeError):
        return
    if "separation_ladder" not in d:
        defects.append((
            "coexistence-no-separation-ladder",
            "the coexistence artifact carries no separation ladder. Orthogonality before "
            "retirement is an ORDER that binds immediately and needs no data -- without it, the "
            "first harmful interaction gets answered by retiring a strategy, which recovers the "
            "interaction loss AND gives up the opportunity."))
    if d.get("state") == "ACTIVE" and d.get("retirement_permitted"):
        defects.append((
            "coexistence-retires-too-early",
            "the coexistence organ claims authority to retire. It must never: retirement recovers "
            "the interaction loss and gives up the strategy, which is strictly worse whenever an "
            "earlier rung of the separation ladder was available and untried."))


CHECKS += [("coexistence", check_coexistence)]


CHECKS += [("under-exploration", check_under_exploration)]


CHECKS += [("fixers-not-watchers", check_fixers_not_watchers)]


CHECKS += [("evig-ranking", check_evig_ranking)]


CHECKS += [("law-coverage", check_law_coverage)]

#: Module-level `check_*` functions that are deliberately NOT swept. Empty by design: an exemption
#: must be argued in writing here, never assumed by silence.
_CHECKS_EXEMPT: set[str] = set()


ASYM_RECORD = ROOT / "docs/research/asymmetry_record.json"   # git-tracked; ratchets UP only


def check_asymmetry_ratchet(defects) -> None:
    """REALISED asymmetry may never fall -- the promised ratchet, and it was missing.

    `scripts/asymmetry_ledger.py` grades every source on two axes and computes REALISED asymmetry
    as weight x depth. Nothing audited it, so the ledger was a report rather than a ratchet: depth
    could regress, a claim could go stale, and the only consequence was a number changing in a
    file nobody re-read. `daily_max` even carried a remediation keyed on "asymmetry" that could
    never fire, because no check produced a defect with that id -- dead config guarding nothing.

    Two conditions, and the second is the one that matters. Realised asymmetry falling is a
    regression by attrition -- §39(4) applied to the axis that actually decides edge. And a STALE
    claim is worse than a low one: it means the desk is holding an advantage it has not
    re-verified, which is 'not measured = fine' pointed at its own moat.
    """
    art = ROOT / "data/asymmetry_ledger.json"
    if not art.exists():
        defects.append((
            "asymmetry-never-measured",
            "data/asymmetry_ledger.json absent -- nothing has graded which of the desk's sources "
            "a competitor could also have. Run scripts/asymmetry_ledger.py."))
        return
    try:
        d = json.loads(art.read_text("utf-8"))
    except (OSError, json.JSONDecodeError):
        return
    realised = float(d.get("realised_asymmetry_total", 0.0))
    stale = list(d.get("stale_claims") or [])
    if stale:
        defects.append((
            "asymmetry-claim-stale",
            f"{len(stale)} asymmetry claim(s) past their half-life without re-verification: "
            f"{', '.join(stale[:6])}. A RECONSTRUCTIBLE advantage lasts only until somebody "
            "productises it -- the graveyard already carries vendor-replacement entries that are "
            "exactly that transition. An unchecked claim is 'not measured' being read as "
            "'measured and fine', applied to the one asset that justifies the enterprise."))
    try:
        rec = json.loads(ASYM_RECORD.read_text("utf-8")) if ASYM_RECORD.exists() else {}
    except (OSError, json.JSONDecodeError):
        rec = {}
    best = float(rec.get("best_realised", 0.0))
    if realised > best + 1e-9:
        rec["best_realised"] = realised
        rec["updated"] = datetime.now(tz=UTC).isoformat()
        rec["note"] = ("§39 ratchet on the asymmetry axis: realised = weight x depth, and it only "
                       "grows. Depth is what has been BUILT, never what is planned.")
        with contextlib.suppress(OSError):
            ASYM_RECORD.write_text(json.dumps(rec, indent=1), "utf-8")
    elif best > 0 and realised < best * 0.9:
        defects.append((
            "asymmetry-realised-fell",
            f"§39(4) on the asymmetry axis: realised asymmetry fell to {realised:.2f} from a "
            f"record of {best:.2f}. Weight x depth only grows -- a source demoted, a depth "
            "regressed or a claim expired. Restore it or record what supersedes it."))


CHECKS += [("asymmetry-ratchet", check_asymmetry_ratchet)]


def check_data_decay(defects) -> None:
    """A source going dark or going useless must raise a defect, not sit in a report.

    `libs/data/decay.py` separates availability decay from usefulness decay and refuses to call
    either one on a thin sample. Nothing consumed its verdicts, so a DECAYING source produced a
    JSON file and no consequence -- and `daily_max` carried a "decay" remediation that could never
    fire for want of a defect to match.
    """
    art = ROOT / "data/data_decay.json"
    if not art.exists():
        return                    # the monitor has never run here; production checks cover that
    try:
        d = json.loads(art.read_text("utf-8"))
    except (OSError, json.JSONDecodeError):
        return
    act = d.get("actionable") or []
    if act:
        names = ", ".join(f"{r.get('source')}({r.get('verdict')})" for r in act[:6])
        defects.append((
            "data-decay-actionable",
            f"{len(act)} source(s) DECAYING or DEAD: {names}. Availability decay needs a new "
            "endpoint and usefulness decay needs the source retired -- different remedies, which "
            "is why they are never summed. NEVER-WORKED is excluded here on purpose: it is an "
            "acquisition failure, not a decline."))


CHECKS += [("data-decay", check_data_decay)]


def check_dormancy_disarm(defects) -> None:
    """A guard fed by a ROLLING WINDOW of our OWN activity disarms itself during a pause.

    Probe angle 15 (self_interrogation_patterns.md), coined 2026-08-05 after it found a live
    money-path no-op. `_structurally_bleeding` -- the gate blocking new opens in proven-loser
    symbols -- read only `worst_symbols`, a 14-day rolling window over the carry book's own
    closes. The book paused 2026-08-01 on a -17.6% drawdown, the window emptied, and the gate
    returned False for COOKIEUSDT and 1000CATUSDT, the two incident-#6 symbols the executor's own
    comment calls "currently-blocked", while a `REARM` that auto-executes sat on the principal's
    page. Self-reinforcing: a pause is CAUSED by losses, so the guard is guaranteed to be disarmed
    exactly when it matters.

    OUTCOME, NOT CONFIG. This calls the real gate on the real recorded denials rather than
    grepping for a wiring marker: "the branch is present" and "the symbol is actually blocked" are
    different claims, and only the second is the one the money depends on. An empty list with a
    young mtime is indistinguishable from health to every staleness fence on this desk.
    """
    ledger = ROOT / "data/execution_reentry.json"
    if not ledger.exists():
        return
    try:
        rows = json.loads(ledger.read_text("utf-8"))
    except (OSError, json.JSONDecodeError):
        return
    denied = [k for k, v in rows.items() if not k.startswith("_") and isinstance(v, dict)]
    if not denied:
        return                     # nothing was ever denylisted, so nothing can be forgotten
    try:
        spec = importlib.util.spec_from_file_location(
            "_dormancy_probe", ROOT / "scripts/run_cashcarry_executor.py")
        if spec is None or spec.loader is None:
            return
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        gate = mod._structurally_bleeding
    except Exception:              # unimportable executor is other checks' job
        return
    leaked = []
    for sym in denied:
        try:
            if gate(sym) is False and not mod.excitation.reentry_allowed(
                    sym, rows, mod.execution_tape.read())[0]:
                leaked.append(sym)
        except Exception:          # a probe that cannot run is not a pass
            continue
    if leaked:
        defects.append((
            "dormancy-disarm",
            f"{len(leaked)} recorded execution denial(s) are NOT being enforced: "
            f"{', '.join(leaked[:6])}. Each has a row in data/execution_reentry.json whose "
            "re-entry conditions are NOT met, yet `_structurally_bleeding` allows the symbol -- "
            "so the denylist has forgotten a denial it still records. The usual cause is the "
            "14-day rolling `worst_symbols` window emptying while the book is paused, which is "
            "exactly when the guard is most needed. Repair UPWARD (persist the denial), never by "
            "deleting the row: a denial that forgets itself is not a denial."))


CHECKS += [("dormancy-disarm", check_dormancy_disarm)]


#: Library modules that legitimately have no importer. Each exemption is ARGUED here, never
#: assumed by silence -- the same rule CHECKS uses.
_UNWIRED_EXEMPT: set[str] = {
    "libs.__init__",
    # LIVE CONNECTORS, DORMANT UNTIL GATE-0 BY DESIGN. Wiring them now would mean an order path
    # reachable from a desk with zero validated alphas, which is strictly worse than an unreachable
    # one. They activate when the principal supplies keys; until then unreachable IS the safe state
    # and pretending otherwise would be the one exemption that could lose money.
    "libs.execution.binance_live",
    "libs.execution.binance_spot_live",
    "libs.execution.staging",
}


def check_unwired_modules(defects) -> None:
    """A library module nothing imports is the desk's own "built but never runs" class.

    THIS CHECK EXISTS BECAUSE A ONE-OFF GREP FOUND THREE OF THEM AT ONCE (2026-08-03):
    `libs/data/wallet_graph.py`, `libs/portfolio/capacity_allocation.py` and -- earlier in the same
    session -- the whole ICT detector family, which shipped with full test suites and no caller.
    Tests passing is not the same as being reachable: a module with 20 green tests and no importer
    produces exactly as much E[log W] as not having been written, and takes longer.

    The sweep that caught them was a shell loop run by hand. A defect class found by hand once gets
    found by hand never again, so it is mechanical from here.

    TESTS DO NOT COUNT AS WIRING, deliberately. A test importing a module proves it works, not that
    anything uses it -- and counting them would make every orphan look connected, which is the
    precise failure being detected.
    """
    import ast

    lib_root = ROOT / "libs"
    if not lib_root.exists():
        return
    modules: set[str] = set()
    for p in lib_root.rglob("*.py"):
        if "__pycache__" in p.parts:
            continue
        rel = p.relative_to(ROOT).with_suffix("")
        name = ".".join(rel.parts)
        if name.endswith(".__init__"):
            name = name[: -len(".__init__")]
        modules.add(name)

    imported: set[str] = set()
    # A `python -m libs.x.y` IN A SHELL IS A CALLER, and an AST scan of .py files cannot see one.
    # Measured false positive: libs.ops.deploy_plan is invoked by deploy/pull_deploy.sh every 10
    # minutes (`"$PY" -m libs.ops.deploy_plan --directives`) and this fence called it unwired --
    # "retire on the record" would have deleted the module that computes which systemd units a
    # pulled commit invalidates. Scanning the shell/cron surface for -m targets closes that hole.
    # This can only ADD real callers, never hide a genuine orphan.
    for area in ("scripts", "ops", "deploy"):
        base = ROOT / area
        if not base.is_dir():
            continue
        for sh in (*base.rglob("*.sh"), *base.rglob("*.manifest")):
            with contextlib.suppress(OSError):
                for hit in re.findall(r"-m\s+(libs\.[A-Za-z0-9_.]+)",
                                      sh.read_text("utf-8", errors="ignore")):
                    parts = hit.split(".")
                    # register the module AND its parent packages, matching the AST roll-up
                    for i in range(2, len(parts) + 1):
                        imported.add(".".join(parts[:i]))
    for area in ("scripts", "libs", "ops"):
        base = ROOT / area
        if not base.exists():
            continue
        for p in base.rglob("*.py"):
            if "__pycache__" in p.parts:
                continue
            try:
                tree = ast.parse(p.read_text("utf-8", errors="ignore"))
            except (OSError, SyntaxError):
                continue
            parts = p.relative_to(ROOT).with_suffix("").parts
            self_name = ".".join(parts)
            pkg = ".".join(parts[:-1])          # the package a relative import resolves against
            here: set[str] = set()
            for node in ast.walk(tree):
                if isinstance(node, ast.ImportFrom):
                    # RELATIVE IMPORTS ARE THE MAJORITY INSIDE A PACKAGE, and resolving them is
                    # what separates a useful check from a useless one. The first version recorded
                    # `from .card import X` as the module "card", which matches nothing, and
                    # reported 241 orphans out of 244 modules -- a check that loud is ignored
                    # immediately, which is the crying-wolf failure this codebase names elsewhere.
                    base = node.module or ""
                    if node.level:
                        up = pkg.split(".")
                        up = up[: len(up) - (node.level - 1)] if node.level > 1 else up
                        base = ".".join([*up, base]) if base else ".".join(up)
                    if base:
                        here.add(base)
                        for alias in node.names:      # `from libs.ict import crypto`
                            here.add(f"{base}.{alias.name}")
                elif isinstance(node, ast.Import):
                    for alias in node.names:
                        here.add(alias.name)
            # SELF-DISCARD IS PER FILE, AND GETTING THAT WRONG INVERTED THE WHOLE CHECK. The first
            # version discarded `self_name` from the GLOBAL set, so processing libs/alpha/card.py
            # erased the record that libs/self_improvement/controller.py had imported it -- every
            # module deleted its own inbound edges and 241 of 244 modules reported as orphans. A
            # check that loud is ignored on sight, which is the crying-wolf failure named
            # elsewhere in this file.
            here.discard(self_name)                   # a module importing itself is not a caller
            imported |= here

    # A PACKAGE IS REACHABLE IF ANY SUBMODULE IS: importing libs.alpha.card loads libs.alpha on
    # the way. Counting package roots as orphans put 20 phantom entries in the list and buried the
    # real ones, which is the same crying-wolf failure in a quieter register.
    reachable = set(imported)
    for name in imported:
        parts = name.split(".")
        for i in range(1, len(parts)):
            reachable.add(".".join(parts[:i]))

    orphans = sorted(
        m for m in modules
        if m not in reachable and m not in _UNWIRED_EXEMPT
        and not m.endswith((".errors", ".models"))    # type/exception modules are imported by name
    )
    if orphans:
        defects.append((
            "unwired-modules",
            f"{len(orphans)} library module(s) that NOTHING imports -- built, tested, and "
            f"unreachable: {', '.join(orphans[:8])}"
            + (f" (+{len(orphans) - 8} more)" if len(orphans) > 8 else "")
            + ". Tests do not count as wiring: a module with green tests and no importer produces "
              "as much E[log W] as not having been written. Give each a caller or argue it into "
              "_UNWIRED_EXEMPT."))

    # THE HOLE IN THE CHECK ABOVE, AND IT IS THE ONE I FELL INTO. A libs module counts as wired
    # the moment ANY file imports it -- including a scripts/ entrypoint that nothing ever runs. So
    # the honest fix for an orphan ("write it a caller") can be satisfied by a file that is itself
    # an orphan, the check goes green, and the module is exactly as unreachable as before. It
    # happened three times in one session: cluster_weak_signals.py, resolve_wallets.py and
    # run_ict_cross_sectional.py were each written to wire a library module, and nothing ran any
    # of them. A wiring fix one link short still reports success, which is worse than no fix.
    #
    # This closes the chain rather than auditing all 277 scripts: only scripts that are LOAD-
    # BEARING for the check above -- the sole importer of some libs module -- must themselves be
    # invoked by something that runs (a shell in ops/, a systemd unit, the cadence, or another
    # script). Research one-shots stay unaudited on purpose: not every script needs a caller, and
    # a check that said otherwise would produce 69 defects nobody could act on.
    sole_importer: dict[str, str] = {}
    for mod in modules:
        importers = [
            str(f.relative_to(ROOT))
            for f in ROOT.joinpath("scripts").glob("*.py")
            if mod in _imports_of(f)
        ]
        others = [
            f for f in (ROOT / "libs").rglob("*.py")
            if "__pycache__" not in f.parts and mod in _imports_of(f)
            and ".".join(f.relative_to(ROOT).with_suffix("").parts) != mod
        ]
        if len(importers) == 1 and not others:
            sole_importer[mod] = importers[0]

    # A SCRIPT MUST NOT VOUCH FOR ITSELF. Every script names itself in its own usage line, so
    # searching a blob that includes the file being judged makes every script look invoked. The
    # candidate's own text is excluded from its own haystack -- the same self-discard bug that
    # inverted the orphan check above, in a different costume.
    invoker_files = [
        f for pat in ("ops/*", "scripts/*.py", ".github/workflows/*", "docs/*.md")
        for f in ROOT.glob(pat) if f.is_file()
    ]
    # Scripts that cannot run on this platform at all. `run_autodiscovery.py` imports MetaTrader5,
    # a Windows-only broker bridge already carried in the optional-dependency allowlist -- wiring
    # it into a Linux cadence would schedule a guaranteed ImportError every cycle, which is noise
    # dressed as coverage. The module it keeps alive (libs.costs.mt5_calibration) is reachable the
    # day the desk runs an MT5 leg, and not before.
    _CALLER_EXEMPT = {
        "scripts/run_autodiscovery.py": "imports MetaTrader5 -- Windows-only",
        # The funding-interval/venue-risk-parameter axis is crypto-exchange-NATIVE ground, which
        # the 2026-08-18 universe mandate bans from ever being hunted again -- wiring this screen
        # to a schedule would manufacture usage of a retired axis (the III.16 inverse). Retained
        # for provenance; re-entry only via a named enabling change under L1.16a.
        "scripts/screen_venue_risk_params.py":
            "crypto-exchange-native axis -- banned universe (MT5 mandate 2026-08-18)",
    }

    dead_links = []
    for mod, script in sorted(sole_importer.items()):
        if script in _CALLER_EXEMPT:
            continue
        base = script.rsplit("/", 1)[-1]
        invoked = any(
            base in f.read_text("utf-8", errors="ignore")
            for f in invoker_files
            if str(f.relative_to(ROOT)) != script
        )
        if not invoked:
            dead_links.append(f"{script} (sole importer of {mod})")
    dead_links = sorted(set(dead_links))
    if dead_links:
        defects.append((
            "unwired-caller",
            f"{len(dead_links)} script(s) are the ONLY importer of a library module and nothing "
            f"invokes them -- so the module is unreachable and the orphan check above is green "
            f"anyway: {'; '.join(dead_links[:6])}"
            + (f" (+{len(dead_links) - 6} more)" if len(dead_links) > 6 else "")
            + ". A wiring fix that is one link short still reports success. Put each in the "
              "cadence, a shell or a unit."))


def _imports_of(path: Path) -> set[str]:
    """Dotted module names a file imports, relative imports resolved. Cached: the orphan check
    walks every file twice and parsing 400 files twice per run is the difference between a check
    that runs every cycle and one that gets switched off."""
    import ast as _ast

    key = str(path)
    if key in _IMPORTS_CACHE:
        return _IMPORTS_CACHE[key]
    out: set[str] = set()
    try:
        tree = _ast.parse(path.read_text("utf-8", errors="ignore"))
    except (OSError, SyntaxError):
        _IMPORTS_CACHE[key] = out
        return out
    for node in _ast.walk(tree):
        if isinstance(node, _ast.ImportFrom) and node.module and not node.level:
            out.add(node.module)
            for alias in node.names:
                out.add(f"{node.module}.{alias.name}")
        elif isinstance(node, _ast.Import):
            for alias in node.names:
                out.add(alias.name)
    _IMPORTS_CACHE[key] = out
    return out


_IMPORTS_CACHE: dict[str, set[str]] = {}


def check_silent_swallows_on_the_rails(defects) -> None:
    """A BROAD `except Exception: pass` ON A RAIL MUST SAY WHY IT IS THERE.

    Swept 2026-08-04: 39 of them across libs/ and scripts/, 32 with no explanatory comment. Most
    are in research scripts where a swallowed error costs a wasted cycle and nothing else, so a
    check demanding a comment on all 39 would be noise -- the crying-wolf failure this file names
    in four other places.

    On the RAILS it is different, and the two outcomes are opposite:

      CORRECT   the recorder must not stop taping twenty-nine symbols because one fetch failed
                (`fromId` resumes, so the gap is deferred and not dropped); the executor's
                post-only fallback must return "no order rested" rather than crash; the pager
                must not withhold pages it has already computed because a liveness ping failed
      A DEFECT  the same construct hiding a failure on the primary path, where the caller then
                proceeds believing the thing happened -- which is how `_market_max_qty` silently
                cached its own failure and disabled the market-order cap for a whole process
                lifetime, found the same day

    The two look identical in a diff. The comment is the only thing that distinguishes a decision
    from an oversight, so on these files it is required rather than encouraged.

    scripts/run_deadman_switch.py is DELIBERATELY ABSENT. It is Tier-3 -- "may not be modified
    autonomously, explicit principal sign-off only" -- and adding a comment is a modification. Its
    two swallows were READ and are correct (a paging failure after the book is already flattened
    must not crash the rail), but annotating them is the principal's call, not this file's.
    """
    import ast as _ast

    rails = (
        "libs/execution/binance_live.py", "libs/execution/binance_spot_live.py",
        "libs/execution/binance_testnet.py", "libs/execution/binance_spot_testnet.py",
        "libs/execution/staging.py",
        "scripts/run_cashcarry_executor.py", "scripts/run_alerts.py",
        "scripts/run_recorder.py", "scripts/run_recorder_spot.py",
        "scripts/run_recorder_bybit.py",
    )
    bare: list[str] = []
    for rel in rails:
        p = ROOT / rel
        if not p.exists():
            continue
        text = p.read_text("utf-8", errors="ignore")
        lines = text.splitlines()
        try:
            tree = _ast.parse(text)
        except SyntaxError:
            continue
        for n in _ast.walk(tree):
            if not (isinstance(n, _ast.ExceptHandler) and len(n.body) == 1
                    and isinstance(n.body[0], _ast.Pass)):
                continue
            if not (isinstance(n.type, _ast.Name) and n.type.id in ("Exception", "BaseException")):
                continue
            # A comment anywhere between the `except` line and the `pass` counts as the reason.
            window = " ".join(lines[n.lineno - 1: n.body[0].lineno])
            if "#" not in window:
                bare.append(f"{rel}:{n.lineno}")
    if bare:
        defects.append((
            "rail-silent-swallow",
            f"{len(bare)} broad `except Exception: pass` on a RAIL with no stated reason -- "
            f"{', '.join(bare[:6])}"
            + (f" (+{len(bare) - 6} more)" if len(bare) > 6 else "")
            + ". On these files a swallow is either load-bearing or a hidden failure on the "
              "primary path, and the two are indistinguishable in a diff. Say which."))


CHECKS += [("rail-silent-swallow", check_silent_swallows_on_the_rails)]

CHECKS += [("unwired-modules", check_unwired_modules)]


def check_moat_screened(defects) -> None:
    """The EXCLUSIVE asset must be screened for survivors, not merely counted.

    `mine_moat` records COVERAGE -- which (venue, symbol, day, mechanism) cells have been measured
    -- and `extract_all` returns mean, std, p50, p95, max. For weeks that was the whole
    relationship the desk had with the one asset a competitor cannot buy, scrape or backfill:
    descriptive statistics and no verdict, at asymmetry depth 2 of 5.

    Coverage without a verdict is the most expensive possible way to own an irreplaceable asset.
    """
    art = ROOT / "data/moat_screen.json"
    if not art.exists():
        defects.append((
            "moat-never-screened",
            "data/moat_screen.json absent -- the self-recorded L2 tape has never been screened "
            "for predictive power. mine_moat measures COVERAGE; nothing asks whether any "
            "proprietary mechanism predicts anything. Run scripts/screen_moat.py."))
        return
    try:
        d = json.loads(art.read_text("utf-8"))
    except (OSError, json.JSONDecodeError):
        return
    if d.get("state") == "NO TAPE":
        return                      # the recorders are the blocker; other checks own that
    suspect = d.get("suspect_lookahead") or []
    if len(suspect) > 0.5 * max(int(d.get("scored", 0)), 1):
        defects.append((
            "moat-screen-mostly-suspect",
            f"{len(suspect)} of {d.get('scored')} scored hypotheses came back SUSPECT-LOOKAHEAD. "
            "On a causally clean tape that is a statement about the HARNESS, not the features -- "
            "alignment, horizon calibration or target construction. Five such bugs were found and "
            "fixed on 2026-08-03 (1595bd4), the sub-daily ceiling rescale was re-welded 2026-08-11 "
            "(9e11c7d) after a merge deleted it from BOTH sides, and the warmup-blind screen floor "
            "fell 2026-08-12; the next one would look exactly like this."))

    # THE RATE, NOT THE LEVEL (P18) -- APPLIED TO THE HUNT, NOT ONLY TO THE MINE. The miner has
    # carried a closure check since it was built; the screen shipped with a coverage frontier and
    # no equivalent, which means "we screen it continuously" could stay true while the frontier
    # stood still. Those are opposite diagnoses: a rising number is exploration, a frozen one is a
    # scheduler that keeps re-screening the same convenient cells, and a SNAPSHOT cannot tell them
    # apart -- 41% is a triumph the run after 27% and a scandal after a week at 41%.
    hist = ROOT / "data/moat_screen_history.jsonl"
    rows = []
    if hist.exists():
        for ln in hist.read_text("utf-8", errors="ignore").splitlines()[-40:]:
            with contextlib.suppress(json.JSONDecodeError):
                rows.append(json.loads(ln))
    pcts = [float(r["coverage_pct"]) for r in rows if r.get("coverage_pct") is not None]
    if len(pcts) >= 6 and pcts[-1] < 99.0 and pcts[-1] <= pcts[0]:
        defects.append((
            "moat-screen-not-converging",
            f"screen coverage has not risen over the last {len(pcts)} runs "
            f"({pcts[0]:.1f}% -> {pcts[-1]:.1f}%) and is not complete. The frontier is supposed to "
            "spend every run on the cells owing the most mechanisms, so a flat series means the "
            "scheduler is re-screening ground it has already covered while holes stand open -- "
            "the exact failure hole-first ordering was built to prevent. Check the coverage "
            "record is being persisted and that the file budget is not smaller than one cell."))

    # A HUNT WHOSE FINDINGS NOTHING READS IS A DIARY. The registry accumulates survivors with
    # their misses; `promote_moat_survivors.py` is the only thing that converts persistence into a
    # forward clock. If survivors exist and no promotion artifact does, the desk is finding edges
    # on its irreplaceable asset and dropping them on the floor.
    reg = ROOT / "data/moat_survivors.json"
    promo = ROOT / "data/moat_promotion.json"
    if reg.exists() and not promo.exists():
        with contextlib.suppress(OSError, json.JSONDecodeError):
            entries = json.loads(reg.read_text("utf-8"))
            if isinstance(entries, dict) and any(
                    int(e.get("times_survived", 0)) > 0 for e in entries.values()):
                defects.append((
                    "moat-survivors-unexploited",
                    f"{sum(1 for e in entries.values() if int(e.get('times_survived', 0)) > 0)} "
                    "triple(s) have survived a screening pass and data/moat_promotion.json does "
                    "not exist -- nothing has adjudicated whether any of them beats the sweep's "
                    "own false-positive rate. A survivor nobody reads is worth what a survivor "
                    "nobody found is worth. Run scripts/promote_moat_survivors.py."))

    # A CLOCK NOBODY READS IS A WAITING ROOM WITH NO DOOR. Promotion buys forward days; the only
    # out-of-sample question in the whole pipeline is whether the candidate still predicts on tape
    # recorded AFTER it was named. Everything upstream -- including the persistence test -- is
    # answered on tape that already existed when the candidate was chosen.
    prereg = ROOT / "data/moat_preregistered.json"
    review = ROOT / "data/moat_clock_review.json"
    if prereg.exists() and not review.exists():
        with contextlib.suppress(OSError, json.JSONDecodeError):
            pending = json.loads(prereg.read_text("utf-8"))
            if isinstance(pending, dict) and pending:
                defects.append((
                    "moat-clocks-unread",
                    f"{len(pending)} candidate(s) are pre-registered with forward clocks and "
                    "data/moat_clock_review.json does not exist -- nothing has asked whether any "
                    "of them still predicts on tape recorded AFTER it was named. That is the only "
                    "out-of-sample evidence this pipeline can produce, and the days are being "
                    "paid whether or not anyone reads them. Run scripts/review_moat_clocks.py."))


CHECKS += [("moat-screened", check_moat_screened)]


def check_registry_complete(defects) -> None:
    """A written check that is never registered is a law the desk believes it is enforcing.

    Origin (2026-07-26): `check_fee_carry_ratio` (§40 fee ratchet), `check_paid_target_registry`
    and `check_holdings_never_shrink` (§39) and `check_universal_doctrine` were all authored,
    committed, and NEVER added to CHECKS -- four consecutive charters shipped with zero
    enforcement. The cause is structural, not careless: CHECKS is a literal defined ABOVE most of
    the checks, so the natural "append next to the others" edit raises NameError at import and the
    registration quietly gets dropped. Nothing mechanical looked, because the checker that would
    have looked was itself one of the unregistered ones.

    This closes the class: every module-level `check_*` callable must be in CHECKS or argued into
    `_CHECKS_EXEMPT`. Silence is no longer a way to ship a dead law.
    """
    registered = {fn.__name__ for _, fn in CHECKS}
    orphans = sorted(
        name for name, obj in globals().items()
        if name.startswith("check_") and callable(obj)
        and name not in registered and name not in _CHECKS_EXEMPT)

    # 2026-08-26, self-found and PAID FOR THE SAME DAY: `check_route_shaped_identity` was written
    # `() -> list[str]` (returning its verdicts) while the runner calls `fn(defects)`. It was
    # correctly REGISTERED, so this guard was green -- and it raised TypeError on every single
    # sweep, so a real 195-break defect produced zero verdicts and the dimension read clean.
    # Registration is not enforcement: a check the runner cannot CALL is as inert as one it never
    # reaches, and _fenced's sweep-broken-* rescue reports the crash without ever naming the law
    # that went dark. Shape is checked here, at registration, where it is cheap and unmissable.
    import inspect
    misshapen: list[str] = []
    for label, fn in CHECKS:
        try:
            sig = inspect.signature(fn)
        except (TypeError, ValueError):          # pragma: no cover -- builtins/C callables
            continue
        positional = [pm for pm in sig.parameters.values()
                      if pm.kind in (pm.POSITIONAL_ONLY, pm.POSITIONAL_OR_KEYWORD)
                      and pm.default is pm.empty]
        varargs = any(pm.kind is pm.VAR_POSITIONAL for pm in sig.parameters.values())
        if len(positional) != 1 and not varargs:
            misshapen.append(f"{label}({fn.__name__}{sig})")
    if misshapen:
        defects.append((
            "check-wrong-signature",
            f"{len(misshapen)} registered check(s) cannot be CALLED by the runner, which passes "
            f"exactly one positional `defects` list: {', '.join(misshapen)}. Each raises on every "
            "sweep and its law reads clean while going unenforced -- registration is not "
            "enforcement. Every check is `def check_x(defects) -> None` and APPENDS "
            "`(id, message)` tuples; returning verdicts discards them silently."))
    if orphans:
        defects.append((
            "check-unregistered",
            f"{len(orphans)} check(s) authored but NEVER RUN -- the law they enforce is inert "
            f"while the desk believes it is enforced: {', '.join(orphans)}. Add each to CHECKS "
            "(register BELOW its definition) or justify it in _CHECKS_EXEMPT."))


CHECKS += [("check-registry", check_registry_complete)]


CONSTITUTION = ROOT / "docs/CONSTITUTION.md"
CONST_REVIEW = ROOT / "docs/research/constitution_review.md"


def check_constitution_review(defects) -> None:
    """The constitution governs (installed 2026-07-29): present, injected, and reviewed.

    RENAMED at the 2026-08-04 merge: the sibling branch's check_constitution (above) owns REACH
    -- organ injection, the ratchet, the doctrine copy -- while this one owns PRESENCE and the
    quarterly REVIEW age. Same name would shadow; both must run.

    L2.8 makes stability the default review outcome -- but an UNREVIEWED constitution is not
    stable, it is unexamined. The quarterly cadence is enforced as an age fence rather than a new
    scheduler: the defect fires, the brain runs the review (default verdict: unchanged, stated
    explicitly), writes the artifact, the fence goes green. No second orchestrator.
    """
    if not CONSTITUTION.exists() or CONSTITUTION.stat().st_size < 8000:
        defects.append(("constitution-missing",
                        "docs/CONSTITUTION.md is missing or gutted -- the desk's governing "
                        "operating system is not installed; every organ is running on doctrine "
                        "fragments with no Level-1 objective hierarchy"))
        return
    try:
        doct = (ROOT / "ops/principal_doctrine.txt").read_text("utf-8", errors="ignore")
    except OSError:
        doct = ""   # ABSENT doctrine injects nothing: same defect as de-cored, reported not crashed
    # CONSOLIDATION 2026-08-25: docs/LAWS.md is the operative constitution and the doctrine
    # writes the objective as E[log W_T]; the old strings (CONSTITUTION.md, parenthesised W_T)
    # made this detector fire on the CORRECT consolidated doctrine -- a stale detector accusing
    # a healthy artifact. Either generation of either token satisfies the same property: the
    # doctrine names its governing document and states the objective.
    _governs = ("docs/LAWS.md" in doct) or ("docs/CONSTITUTION.md" in doct)
    _objective = ("E[log W_T]" in doct) or ("E[log(W_T)]" in doct)
    if not _governs or not _objective:
        defects.append(("constitution-not-injected",
                        "the doctrine no longer declares docs/LAWS.md (or the legacy "
                        "CONSTITUTION.md) governing, or lost the E[log W_T] objective -- organs "
                        "are being briefed without the constitutional core, which voids "
                        "universal enforcement"))
    if CONST_REVIEW.exists():
        age_d = (NOW - CONST_REVIEW.stat().st_mtime) / 86400.0
        if age_d > 92:
            defects.append(("constitution-review-overdue",
                            f"L4 quarterly constitutional review is {age_d:.0f}d old (>92d). Run "
                            "it per L2.8: rank candidate changes by ERV, default outcome "
                            "STABILITY stated explicitly, write the verdict to "
                            "docs/research/constitution_review.md."))
    elif (NOW - CONSTITUTION.stat().st_mtime) / 86400.0 > 92:
        defects.append(("constitution-review-overdue",
                        "no constitutional review artifact exists and the constitution is >92d "
                        "old -- L4 requires the quarterly review; write "
                        "docs/research/constitution_review.md with the ERV-ranked verdict."))


CHECKS += [("constitution-review", check_constitution_review)]   # registered BELOW its definition


def _read_one(path: Path) -> tuple[dict, str]:
    """One ack registry -> (acks, state). An ABSENT registry is known-empty; an UNPARSEABLE one is
    "unknown", never silently empty -- guessing "nothing is acked" writes a permanent false
    accusation and guessing "all acked" buries real work."""
    if not path.exists():
        return {}, "known"
    try:
        acks = json.loads(path.read_text("utf-8"))
    except Exception:
        return {}, "unknown"
    return (acks, "known") if isinstance(acks, dict) else ({}, "unknown")


def _read_acks() -> tuple[dict, str]:
    """Both registries as one view. TRACKED WINS on a duplicate id: it is the copy every checkout
    can see and a reviewer can read in the diff, so a local entry must not be able to quietly
    shorten or extend a disposition the repo has already recorded. Either registry failing to
    parse degrades the WHOLE view to "unknown" -- a half-read ack table is not a known one."""
    repo, s1 = _read_one(ACKS_REPO)
    local, s2 = _read_one(ACKS)
    merged = {**local, **repo}
    return merged, ("known" if s1 == "known" and s2 == "known" else "unknown")


def misfiled_acks(defects: Sequence[tuple], *, now_iso: str | None = None) -> list[tuple[str, str]]:
    """REPO-scope defects acked ONLY in the per-box registry -- acks that do not travel (R0393).

    Reported rather than fixed silently, because moving an ack between files is a disposition and
    disposition is not this function's to make. Each entry is (defect id, scope).

    DEDUPED BY ID, because an ack is keyed by id and one check emits many defects under the same
    one: `producer-cadence-stale` fires five times in a normal run, and a list that repeated it
    five times would report 17 misfilings where 12 acks need moving -- inflating a queue is the
    same class of error as hiding one.
    """
    now_iso = now_iso or datetime.now(tz=UTC).isoformat()
    repo, _ = _read_one(ACKS_REPO)
    local, _ = _read_one(ACKS)
    out: list[tuple[str, str]] = []
    seen: set[str] = set()
    for d in defects:
        did = d[0]
        if did in seen:
            continue
        seen.add(did)
        scope = d[2] if len(d) > 2 else "UNSCOPED"
        if scope == "RUNTIME":
            continue                                    # per-box defect, per-box ack: correct
        a = local.get(did)
        if not (isinstance(a, dict) and a.get("until", "") > now_iso):
            continue                                    # not acked locally; nothing to misfile
        b = repo.get(did)
        if isinstance(b, dict) and b.get("until", "") > now_iso:
            continue                                    # already carried by the tracked registry
        out.append((did, scope))
    return out


def split_acked(
    defects: Sequence[tuple], *, now_iso: str | None = None
) -> tuple[list[tuple], list[tuple[str, str]], str]:
    """Split raw defects into LIVE and ACKED against the one ack registry.

    THE ONE DEFINITION (2026-08-01). ``CHECKS`` is module-level precisely so other organs can
    enumerate the same defects "instead of keeping a second copy that silently drifts" -- but the
    ack filter that runs immediately after it lived inside ``main()``, so §37's carry-over brief
    enumerated CHECKS and never saw the acks. It therefore filed all 26 dated, reasoned, expiring
    acks under "shown the work and not done", and the 12 items it put in front of the brain FIRST
    were 12/12 acked -- several of them blocked on principal-only actions the brain cannot take.
    A brief whose top of queue is 100% false gets walked past, which the brief then counted as
    avoidance and escalated. Sharing this function is what stops that drift for good.

    TWO REGISTRIES, ONE VIEW (R0393). Acks are split by the scope max_audit already computes:
    REPO-scope dispositions live in the TRACKED registry so they travel with the commit that
    reasons about them, RUNTIME ones stay per-box where their truth actually differs. An id acked
    in EITHER is acked here -- the split governs where a disposition is WRITTEN, never whether it
    counts, so no existing ack was invalidated by the split landing.

    Returns ``(live, acked, ack_state)``. ``ack_state`` is the REFUSAL PATH (L1.41): "known" when
    the registry was genuinely read, "unknown" when it exists but could not be parsed. An ABSENT
    registry is known-empty -- "nothing has been acked" is a fact, not an unknown. Callers that
    write history must record "unknown" rather than guessing, because guessing "nothing is acked"
    writes a permanent false accusation and guessing "all acked" buries real work.
    """
    now_iso = now_iso or datetime.now(tz=UTC).isoformat()
    acks, state = _read_acks()

    # WIDTH-PRESERVING (merge 2026-08-04): defects arrive as (did, msg) from bare callers and as
    # (did, msg, scope, tracked, untracked) after _fenced's evidence recording. The ack rule reads
    # only the id; everything else passes through untouched so scope-aware consumers downstream
    # (RUNTIME vs REPO escalation) keep their evidence.
    live: list[tuple] = []
    acked: list[tuple[str, str]] = []
    for d in defects:
        a = acks.get(d[0])
        if isinstance(a, dict) and a.get("until", "") > now_iso:
            acked.append((d[0], a.get("reason", "")))
        else:
            live.append(tuple(d))
    return live, acked, state


def main() -> None:
    defects: list[tuple] = []
    for label, fn in CHECKS:
        _fenced(fn, defects, label)

    live, acked, _ack_state = split_acked(defects)
    misfiled = misfiled_acks(defects)

    prev = _j(REPORT, {})
    first_seen = prev.get("first_seen", {})
    now_iso = datetime.now(tz=UTC).isoformat()
    first_seen = {d: t for d, t in first_seen.items() if d in {x[0] for x in live}}
    for did, *_ in live:
        first_seen.setdefault(did, now_iso)
    by_scope: dict[str, int] = {}
    for _, _, s, _, _ in live:
        by_scope[s] = by_scope.get(s, 0) + 1
    REPORT.write_text(json.dumps(
        {"ran": now_iso,
         "live": [{"id": d, "msg": m, "scope": s, "evidence_tracked": tr,
                   "evidence_untracked": un} for d, m, s, tr, un in live],
         "by_scope": by_scope,
         "acked": [d for d, _ in acked],
         #: Acks that do not travel: REPO-scope defects disposed of only in the untracked
         #: per-box registry, so they keep firing (and escalating) on every other checkout.
         "acked_misfiled": [{"id": d, "scope": s} for d, s in misfiled],
         "first_seen": first_seen,
         "scope_note": (
             "REPO: the check consulted a git-tracked file, so the defect is verifiable and "
             "closable from any checkout. RUNTIME: it consulted only untracked paths (data/, "
             "web/ are gitignored), so a clone can neither confirm nor close it -- real on the "
             "machine that runs the organ, unresolvable here. UNSCOPED: read no files; escalated "
             "as REPO so unknown provenance never becomes an excuse. Scope is derived from the "
             "paths each check ACTUALLY READ, not from its wording, and a check touching both "
             "kinds is scored REPO -- misfiling a runtime defect as mine costs an investigation, "
             "misfiling mine as the machine's lets it live forever behind 'needs the VPS'."),
         }, indent=1), "utf-8")

    print(f"MAX-AUDIT {now_iso[:16]}  live defects: {len(live)}  acked: {len(acked)}"
          f"  | by scope: {by_scope}")
    for did, msg, scope, _, _ in live:
        age_h = (datetime.now(tz=UTC) - datetime.fromisoformat(first_seen[did])
                 ).total_seconds() / 3600
        print(f"  [{age_h:>5.1f}h] [{scope:<8}] {did}: {msg}")
    for did, reason in acked:
        print(f"  [ acked] {did}: {reason}")

    # ESCALATION IS SCOPED. Paging the principal about an artifact that is absent because data/ is
    # gitignored is crying wolf in the same way the stale RESOLVED line was, and it buries the
    # defects he can actually act on. RUNTIME defects are still reported above, in full, every run.
    overdue = [(d, m) for d, m, s, _, _ in live
               if s != "RUNTIME"
               and (datetime.now(tz=UTC) - datetime.fromisoformat(first_seen[d])
                    ).total_seconds() / 3600 > ESCALATE_H]
    runtime_overdue = sum(
        1 for d, _, s, _, _ in live
        if s == "RUNTIME" and (datetime.now(tz=UTC) - datetime.fromisoformat(first_seen[d])
                               ).total_seconds() / 3600 > ESCALATE_H)
    # DELIVERY FIX (2026-07-24 external audit): the pager reads only PRINCIPAL_ACTION line 1.
    # The old code appended the escalation BELOW existing content (a stale RESOLVED line stayed
    # at line 1) AND only wrote once ever (one-shot latch), so 24 live defects never paged. Now
    # the escalation OWNS line 1 whenever defects are overdue, and is CLEARED when none are --
    # so the pager surfaces the truth and stops crying resolved-wolf.
    # URGENT CARVE-OUT (2026-07-28). Owning line 1 unconditionally fixed the stale-RESOLVED bug by
    # creating the opposite one: with defects essentially always overdue, the ROUTINE 48h sweep
    # permanently outranked every EVENT-DRIVEN page, so a Tier-3 ask the CRO cannot act on alone
    # (a dead-man reset) was delivered as "20 below-max states". A standing sweep is never more
    # urgent than a blocker only the principal can clear. A page marked `URGENT <ISO-date>:` keeps
    # line 1 while it is FRESH -- the date is mandatory precisely so this cannot rot back into the
    # stale line 1 the 07-24 fix removed; past _URGENT_TTL_D it is demoted automatically.
    _MARK = "MAX-AUDIT ESCALATION"
    _URGENT_TTL_D = 7.0
    existing = PA.read_text("utf-8") if PA.exists() else ""
    # DATA LOSS FIX (2026-07-28). This was `existing.split(_MARK)[0]`, which keeps only the text
    # BEFORE the marker. Once the escalation owned line 1 -- i.e. every run after the first -- that
    # expression returned "" and SILENTLY DELETED the entire human-written page below it. Every
    # PRINCIPAL_ACTION page the CRO wrote was destroyed by the next sweep, on the desk's only
    # human-escalation channel, from 2026-07-24 until this fix. Found by re-reading the file after
    # writing it rather than trusting the write. Strip the escalation BLOCK ONLY: its header line
    # plus the indented bullets that belong to it; every other line is somebody's message and is
    # preserved.
    kept, skipping = [], False
    for ln in existing.splitlines():
        if ln.startswith(_MARK):
            skipping = True
            continue
        if skipping and (ln.startswith("  - ") or not ln.strip()):
            continue                       # bullets + the blank line that trails the block
        skipping = False
        kept.append(ln)
    body = "\n".join(kept).strip()
    # POSITION FIX (2026-07-30). This checked only `body.startswith("URGENT ")`, so the carve-out
    # required the URGENT block to be the FIRST paragraph. On 07-30 an unrelated PURCHASE DECISION
    # notice was prepended above it, which silently disabled the carve-out: the routine 48h sweep
    # retook line 1 and the principal was paged "24 below-max state(s)" while TWO Tier-3 rulings the
    # whole discovery pipeline is blocked on (dead carry book, pbo/rc gate flip) sat below the fold.
    # Third recurrence of one family -- 07-24 stale line 1, 07-28 silent deletion, now demotion by a
    # neighbour's insert -- because the carve-out was POSITIONAL and no writer owns a position. Find
    # a fresh URGENT block ANYWHERE in the body and hoist it; reordering only, nothing dropped.
    # FORMAT-FRAGILITY FIX (2026-07-31, FOURTH recurrence of the family: 07-24 stale line 1,
    # 07-28 silent deletion, 07-30 demotion-by-neighbour, now demotion-by-ANNOTATION). The stamp
    # parse was `split("URGENT ",1)[1].split(":",1)[0]` -> fromisoformat, so the moment a human
    # annotated the header ("URGENT 2026-07-29 (updated 07-31): ...") recognition threw, was
    # suppressed, and the routine sweep silently retook line 1 from two Tier-3 asks -- caught
    # live by test_max_audit_run_preserves_a_written_page. Recognition now keys on the first
    # ISO-DATE TOKEN anywhere in the paragraph head, so annotations cannot disarm it. And hoist
    # the RUN of all fresh URGENT paragraphs, not just the first -- with two pending Tier-3
    # asks, "one above the fold, one buried" is the same failure at half size.
    urgents: list[tuple[str, str]] = []       # (iso_date, para)
    paras = body.split("\n\n")
    remaining: list[str] = []
    for para in paras:
        hoisted = False
        if para.startswith("URGENT"):
            m_date = re.search(r"(\d{4}-\d{2}-\d{2})", para[:80])
            if m_date:
                with contextlib.suppress(Exception):
                    age_d = (NOW - datetime.fromisoformat(m_date.group(1))
                             .replace(tzinfo=UTC).timestamp()) / 86400.0
                    if age_d <= _URGENT_TTL_D:
                        urgents.append((m_date.group(1), para))
                        hoisted = True
        if not hoisted:
            remaining.append(para)
    body = "\n\n".join(remaining).strip()
    # NEWEST URGENT OWNS LINE 1 (2026-07-31, fifth member of the demotion family: a fresh
    # book-frozen ask landed BELOW two older URGENTs because hoisting preserved body order).
    # Sort is by stamp desc and stable, so same-day blocks keep their written order.
    urgents.sort(key=lambda t: t[0], reverse=True)
    urgent = "\n\n".join(p for _, p in urgents)
    if overdue:
        head = (f"{_MARK}: {len(overdue)} REPO-scope below-max state(s) >48h unfixed/unacked -- "
                + "; ".join(f"{d}" for d, _ in overdue[:6])
                + (" ..." if len(overdue) > 6 else "") + "\n"
                + "".join(f"  - {d}: {m}\n" for d, m in overdue[:8])
                + (f"  ({runtime_overdue} further RUNTIME-scope defect(s) rest only on untracked "
                   "artifacts and cannot be confirmed or closed from a checkout -- see "
                   "data/max_audit_report.json)\n" if runtime_overdue else ""))
        # BOTH BRANCHES' FIXES COMPOSE: the RUNTIME tail keeps unactionable defects off the page
        # without hiding their count, and a fresh URGENT page still outranks the routine sweep --
        # a standing escalation is never more urgent than a blocker only the principal can clear.
        PA.write_text((urgent + "\n\n" if urgent else "") + head + "\n" + body, "utf-8")
        print(f"ESCALATED to principal page (line {'2' if urgent else '1'}): "
              f"{len(overdue)} REPO defect(s) >48h"
              + (f" (+{runtime_overdue} RUNTIME, not paged)" if runtime_overdue else "")
              + (" -- behind a fresh URGENT page" if urgent else ""))
    elif existing != body + ("\n" if body else ""):
        PA.write_text(body + ("\n" if body else ""), "utf-8")  # cleared: drop stale escalation
        print("escalation cleared: no overdue defects")


if __name__ == "__main__":
    main()


#: A paper sleeve's accrual artifact older than this is a FOSSIL, not evidence. Sources regenerate
#: daily, so two missed runs is already a runner that stopped.
_FORWARD_STALE_H = 60.0


def check_survivor_pipeline(defects) -> None:
    """THE CHAIN BETWEEN MINING AND A SURVIVOR, checked link by link.

    WHY THIS EXISTS. On 2026-08-05 the desk had 120 scored screen cells on disk, twelve forward
    slots, and ZERO forward clocks ever started -- and every organ in the chain reported success.
    The break was structural and completely silent: a converter did not exist, so 114 of 120 cells
    were unreadable by the correction layer; admission gated on a Stage-A significance verdict the
    two-stage law says Stage A cannot issue; the slot registry read ABSENT state files as UNKNOWN,
    which forced free slots to zero forever; and the evidence map was eight hardcoded names, so a
    spawned sleeve could never publish a day count. Each link failed CLOSED and reported nothing,
    and the desk read the resulting silence as "no edges exist". It was reading its own closed door.

    Every check here is about PLUMBING, never about strength. Nothing in this function reads an
    effect size, and a desk with zero real edges must be able to pass it completely -- the failure
    it detects is a pipeline that cannot deliver a survivor even if one is standing in it.
    """
    import json as _json

    conv = ROOT / "reports/axis_screens"
    corrected = 0
    if conv.is_dir():
        for p in conv.glob("*.json"):
            try:
                doc = _json.loads(p.read_text("utf-8"))
            except (OSError, ValueError):
                continue
            trials = doc.get("trials")
            if isinstance(trials, list):
                corrected += sum(1 for t in trials
                                 if isinstance(t, dict) and t.get("verdict_adjusted"))

    # LINK 1 -- conversion. Scored cells exist on disk that the correction layer cannot read.
    try:
        sys.path.insert(0, str(ROOT))
        from libs.research.screen_conversion import convert_all
        result = convert_all(ROOT)
        on_disk = int(result["n_cells"])
    except Exception as exc:
        defects.append(("survivor-conversion-broken",
                        f"screen_conversion could not run ({type(exc).__name__}: {exc}). Every "
                        "screen that writes its own schema is then invisible to the correction "
                        "layer, and its cells can never reach a forward slot."))
        on_disk = 0
    if on_disk and corrected < on_disk:
        defects.append(("survivor-cells-unconverted",
                        f"{on_disk} scored cell(s) convertible but only {corrected} carry "
                        "verdict_adjusted -- run scripts/finalize_axis_screens.py. Cells nobody "
                        "can read are not refuted, they are UNREAD, and reporting the silence as "
                        "'no survivors' is the conversion defect (L1.50/L1.53)."))

    # LINK 2 -- slots. Idle capacity while candidates are queued is unspent forward time, and
    # forward time is the only thing that ever produces a survivor.
    try:
        from libs.research.slot_registry import derive_slots
        cohort = derive_slots()
    except Exception as exc:
        defects.append(("survivor-registry-broken",
                        f"slot_registry.derive_slots failed ({type(exc).__name__}: {exc}) -- the "
                        "cohort size m is then unknown, and every Holm bar downstream is computed "
                        "from a number nobody could derive."))
        cohort = {}
    queue = _j(ROOT / "data/paper_sleeve_queue.json", {}) or {}
    n_queued = len(queue.get("queued") or [])
    idle = int(cohort.get("idle_slots") or 0)
    if idle > 0 and n_queued > 0:
        defects.append(("survivor-slots-idle-with-queue",
                        f"{idle} forward slot(s) idle while {n_queued} candidate(s) wait in the "
                        "queue. A slot costs nothing to fill and every idle day is forward "
                        "evidence not accruing -- the two-stage law's own clock-saturation "
                        "failure, and it is what ten idle slots looked like for the desk's "
                        "entire life."))

    # LINK 3 -- accrual. A clock that is standing but not running is worse than no clock: it pays
    # the cohort's multiplicity (tightening every other candidate's bar) and returns nothing.
    fwd = _j(ROOT / "web/paper_sleeve_forward.json", None)
    live = [n for n in (_j(ROOT / "data/shadow_sleeves.json", []) or [])
            if (ROOT / "data" / f"{n}_shadow_state.json").exists()]
    if live and not isinstance(fwd, dict):
        defects.append(("survivor-clocks-unrun",
                        f"{len(live)} paper sleeve(s) standing and web/paper_sleeve_forward.json "
                        "is absent -- nothing has ever run them. A spawned clock nobody runs can "
                        "never accrue and never resolve, while still charging the cohort its "
                        "multiplicity: born, registered, and structurally unable to finish."))
    elif isinstance(fwd, dict):
        # _parse_iso returns EPOCH SECONDS, and NOW is time.time(). Both are floats; treating
        # either as a datetime raises inside the check and the whole audit dies silently on it.
        ts = _parse_iso(fwd.get("updated"))
        if ts is not None and (NOW - ts) / 3600.0 > _FORWARD_STALE_H:
            age = round((NOW - ts) / 3600.0, 1)
            defects.append(("survivor-accrual-stale",
                            f"web/paper_sleeve_forward.json is {age}h old (> {_FORWARD_STALE_H}h). "
                            "The forward runner has stopped; every standing clock is a fossil "
                            "reporting its last reading, and a fossil that still says ACCRUING is "
                            "how a dead pipeline reads as a healthy one."))
        unrunnable = [n for n, s in (fwd.get("sleeves") or {}).items()
                      if isinstance(s, dict) and s.get("evidence") in ("UNRUNNABLE", "SOURCE-GONE")]
        if unrunnable:
            defects.append(("survivor-clocks-unrunnable",
                            f"{len(unrunnable)} standing clock(s) cannot be run at all "
                            f"({', '.join(sorted(unrunnable)[:3])}...): their state file names no "
                            "origin artifact, or the source no longer carries their cell. Each is "
                            "charging the cohort multiplicity while unable to produce evidence -- "
                            "retire by a ledgered decision or re-spawn, never leave standing."))


def check_clock_retirement_mechanism(defects) -> None:
    """Every clock that LEFT the Holm cohort must carry a classifiable mechanism (F0011/R0049).

    The distinction that licenses leaving at all: REFUTED-AS-INVALID-MEASUREMENT (the trial was
    void) may go; FAILED-ON-ITS-MERITS keeps counting via the high-water floor. Both halves rest
    on the ledger row saying WHICH -- a row whose verdict is a bare timestamp ("since <ts>", the
    writer bug three derivative rows shipped with) is a retirement decision no audit can
    classify, which is the exact uncitable-decision defect the tracked ledger was built to end.
    """
    rows = _j(ROOT / "docs/research/CLOCK_RETIREMENTS.json", {}).get("retirements", [])
    bad = [str(r.get("clock", "?")) for r in rows
           if not str(r.get("why", "")).strip()
           or not str(r.get("verdict", "")).strip()
           or str(r.get("verdict", "")).startswith("since ")]
    if bad:
        defects.append(("clock-retirement-mechanism-missing",
                        f"{len(bad)} retirement row(s) in docs/research/CLOCK_RETIREMENTS.json "
                        f"carry no classifiable mechanism ({', '.join(sorted(bad)[:3])}...): a "
                        "timestamp is a date, not a verdict. Without the mechanism, "
                        "REFUTED-AS-INVALID-MEASUREMENT and FAILED-ON-ITS-MERITS are "
                        "indistinguishable, and the attrition-never-lowers-the-bar law cannot be "
                        "audited. Repair the row from its own why; fix the writer."))


CHECKS += [("survivor-pipeline", check_survivor_pipeline),
           ("clock-retirement-mechanism", check_clock_retirement_mechanism)]


def check_paywalls_registered(defects) -> None:
    """§42: every paid dataset the desk WALKED INTO must reach the registry, not just a log.

    The registry's standing rule already says every digger ADDS any paid dataset it encounters.
    The rule was right and nothing mechanical enforced it, so it depended on whoever wrote the
    collector remembering -- the by-hand step that runs at zero when nobody is looking. Measured
    2026-08-05: a collector hit DefiLlama's emissions endpoint, got HTTP 402 Payment Required,
    wrote it into its own status artifact and a cron comment, and DefiLlama never reached
    docs/research/paid_dataset_targets.md.

    Only confirmed PAYWALLs are demanded. A bare 403 is far more often a WAF than a price, and
    requiring a registry row for every one would fill the list with bot blocks and bury the
    vendors somebody actually sells -- a registry nobody trusts is a registry nobody consults.
    """
    try:
        sys.path.insert(0, str(ROOT))
        from libs.data.paywall import vendors_encountered
    except Exception as exc:
        defects.append(("paywall-ledger-unreadable",
                        f"libs.data.paywall could not be imported ({exc}) -- paid datasets the "
                        "desk walks into can no longer be recorded, so the registry silently "
                        "stops growing while collectors keep hitting paywalls"))
        return

    seen = vendors_encountered(ROOT)
    if not seen:
        return                                                # nothing encountered is not a defect
    try:
        registry = PAID_TARGETS.read_text("utf-8", errors="ignore").lower()
    except OSError:
        registry = ""
    if not registry:
        defects.append(("paywall-registry-missing",
                        f"{len(seen)} confirmed paywall(s) encountered and "
                        "docs/research/paid_dataset_targets.md is absent -- every one is a paid "
                        "dataset with no recorded free-replacement hunt"))
        return
    missing = sorted(v for v in seen if v.split(".")[0] not in registry)
    if missing:
        rows = "; ".join(f"{v} ({seen[v].get('unlocks', '')[:60]})" for v in missing[:4])
        defects.append(("paywall-unregistered",
                        f"§42: {len(missing)} paid dataset(s) encountered but NOT in the registry: "
                        f"{rows}. Every paywall the desk walks into is a valuable dataset somebody "
                        "sells -- it must be listed WITH a free-replacement hunt (primary-source "
                        "reconstruction first; facts are not copyrightable), or the desk keeps "
                        "hitting the same wall and never routes around it."))
    unhunted = sorted(v for v, r in seen.items()
                      if str(r.get("free_replacement_status", "")).upper() == "UNHUNTED"
                      and v.split(".")[0] in registry)
    if unhunted:
        defects.append(("paywall-unhunted",
                        f"{len(unhunted)} registered paywall(s) still carry no free-replacement "
                        f"verdict in the encounter ledger: {', '.join(unhunted[:5])}. Listed is "
                        "not hunted -- §42's deliverable is the REPLACEMENT, not the row."))


CHECKS += [("paywalls-registered", check_paywalls_registered)]


def check_verified_alternatives_promoted(defects) -> None:
    """A verified better alternative that never REPLACES the incumbent is cataloguing, not hunting.

    The desk had two thirds of a loop: `source_alternatives` holds candidates, `paywall` records
    paid datasets and demands a hunt. Neither could SWAP anything, so a genuinely better free route
    could be found, verified, written into a registry row -- and the desk would keep calling the
    old one forever. This fence closes the loop from the other end: it fails when the evidence for
    a replacement exists and the replacement has not happened.

    It never demands a swap on unmeasured evidence. INSUFFICIENT is a legitimate resting state and
    is reported as owed WORK (go and measure the missing field), never as an owed decision.
    """
    import json as _json

    try:
        sys.path.insert(0, str(ROOT))
        from libs.data.paywall import vendors_encountered
        from libs.data.source_promotion import ACTIVE_ROUTES
    except Exception as exc:
        defects.append(("promotion-unimportable",
                        f"libs.data.source_promotion / paywall could not be imported ({exc}) -- a "
                        "verified alternative can no longer replace anything, so hunting silently "
                        "degrades to cataloguing"))
        return

    routes_path = ROOT / ACTIVE_ROUTES
    try:
        routes = _json.loads(routes_path.read_text("utf-8"))
    except (OSError, ValueError):
        routes = {}

    # A PAID ROUTE MUST NEVER BE THE LIVE ONE. Buying is the principal's decision; if a paid vendor
    # is what the desk actually calls, that decision was made by drift rather than by a person.
    paid_live = sorted(k for k, v in routes.items()
                       if isinstance(v, dict) and v.get("is_paid") is True)
    if paid_live:
        defects.append(("promotion-paid-route-live",
                        f"{len(paid_live)} information class(es) are served by a PAID route: "
                        f"{', '.join(paid_live)}. Buying is the principal's decision -- a paid "
                        "vendor becoming the live route without one is a purchase made by drift."))

    # EVERY CONFIRMED PAYWALL SHOULD EVENTUALLY HAVE A FREE ROUTE, or an honest record that the
    # hunt ran and failed. Silence is neither.
    seen = vendors_encountered(ROOT)
    unresolved = sorted(v for v, r in seen.items()
                        if str(r.get("free_replacement_status", "")).upper()
                        in ("UNHUNTED", "HUNTED-OPEN"))
    if unresolved and not routes:
        defects.append(("promotion-no-routes-registered",
                        f"{len(unresolved)} paywall(s) hunted and data/active_routes.json holds NO "
                        "route at all -- nothing records what the desk actually calls for anything, "
                        "so no replacement can ever be evaluated against an incumbent."))


CHECKS += [("alternatives-promoted", check_verified_alternatives_promoted)]


def check_blocked_routes_hunted(defects) -> None:
    """A blocked route the desk stopped chasing is an accepted loss. L1.54 forbids accepting it.

    The 402/403 split keeps a WAF out of the PAID-VENDOR registry, which is right -- a registry
    full of bot blocks buries the vendors somebody actually sells. But the first version then let
    those rows SIT, and parking is accepting in a quieter form. A bare 403 is a source the desk
    WANTED, could not reach, and has no verdict on, with named routes available (render path,
    mirrors, regional hosts, archives, primary-source reconstruction).

    So the two verdicts go to different registries with the SAME urgency. UNREACHABLE is a legal
    resting state and stops this fence -- but only once recorded WITH what was tried, which is the
    enumerated exhaustion L1.54 demands rather than silence.
    """
    try:
        sys.path.insert(0, str(ROOT))
        from libs.data.paywall import BLOCK_STALE_H, unresolved_blocks
    except Exception as exc:
        defects.append(("blocked-routes-unreadable",
                        f"libs.data.paywall could not be imported ({exc}) -- blocked routes can no "
                        "longer be tracked, so a source the desk cannot reach silently becomes a "
                        "source the desk stopped trying to reach"))
        return

    owed = unresolved_blocks(ROOT)
    if not owed:
        return
    idle = [b for b in owed if b.get("idle")]
    names = ", ".join(f"{b['vendor']}({b.get('age_h')}h)" for b in owed[:5])
    if idle:
        defects.append(("blocked-routes-idle",
                        f"{len(idle)} blocked route(s) have gone unhunted for more than "
                        f"{BLOCK_STALE_H}h: {names}. A block is a verdict about the ROUTE the desk "
                        "tried, never about the source -- and one that outlives a full miner cycle "
                        "has been accepted rather than solved. Hunt a render path, mirror, regional "
                        "host, archive or primary-source reconstruction, or record UNREACHABLE "
                        "WITH what was tried (L1.54: exhaustion must be enumerated, never assumed)."))
    else:
        defects.append(("blocked-routes-unhunted",
                        f"{len(owed)} blocked route(s) awaiting a route hunt: {names}. Recorded "
                        "while fresh -- this is owed work, not yet a failure."))


CHECKS += [("blocked-routes", check_blocked_routes_hunted)]


# ---------------------------------------------------------------------------------------------
# SESSION-DERIVED FENCES (2026-08-26). The recursion rule, applied: every defect this desk finds
# becomes a standing automatic check, so the same class can never run unnoticed again. Each of
# the four below is a REAL failure measured on this box, not a hypothetical.
# ---------------------------------------------------------------------------------------------

def check_verifier_reads_injection(defects) -> None:
    """A law verifier must read the SAME text the organ receives.

    MEASURED 2026-08-26: the governance consolidation made the injected prompt doctrine +
    docs/LAWS.md, but libs/ops/lawful.py kept reading the doctrine alone, declared all six law
    families missing, and paged on every guard() call -- 292 OOM kills in two hours. A verifier
    that reads LESS than the organ does reports on a prompt nobody is running.
    """
    inj = ROOT / "ops/brain_env.sh"
    if not inj.exists():
        return
    try:
        env = inj.read_text("utf-8", errors="ignore")
    except OSError:
        return
    # what brain_env actually concatenates into _DOCTRINE
    m = re.search(r'_DOCTRINE="\$\(cat ([^)]+)\)"', env)
    if not m:
        return
    sources = {p.strip().strip('"').split("/")[-1] for p in m.group(1).split()
               if ("/" in p or p.strip().startswith("$")) and ">" not in p}
    sources = {s for s in sources if "." in s and not s.startswith("dev")}
    for verifier in ("libs/ops/lawful.py", "scripts/run_law_gate.py"):
        p = ROOT / verifier
        if not p.exists():
            continue
        try:
            body = p.read_text("utf-8", errors="ignore")
        except OSError:
            continue
        if "check_law_families" not in body and "FAMILIES" not in body:
            continue
        missing = [s for s in sources if s and s not in body]
        if missing:
            defects.append(("verifier-reads-less-than-injection",
                            f"{verifier} verifies law families but does not read {missing} -- "
                            f"ops/brain_env.sh injects them into every organ. A verifier reading "
                            f"less than the organ receives reports on a prompt nobody runs, and "
                            f"its false gaps page in a loop (measured: 292 OOM kills, 2026-08-26)."))


def check_authority_writers_scheduled(defects) -> None:
    """Every script that writes an AUTHORITY artifact must be on a clock.

    MEASURED 2026-08-26: universal_gate.py is the sole writer of UNIVERSAL_SURVIVORS.json -- the
    file shadow_admission and the promoter treat as certificate authority -- and it had no task
    on any box. Candidates could never obtain a certificate, so nothing could ever promote, and
    the nightly job everyone assumed was the certifier writes diagnostics only. III.16 sitting on
    the certification door.
    """
    authority = {"UNIVERSAL_SURVIVORS.json": "certificate authority",
                 "constitution_core.lock": "the sealed core"}
    for artifact, role in authority.items():
        writers = []
        for py in (ROOT / "desks/mt5/research").glob("*.py"):
            try:
                body = py.read_text("utf-8", errors="ignore")
            except OSError:
                continue
            # PROXIMITY, not co-occurrence: promoter.py READS this artifact and WRITES a
            # different one, and a naive `name in body and write_text in body` calls that a
            # writer. Require the artifact name to sit within 200 chars of the write call.
            # SAME LINE, not merely nearby: the real writer reads
            # `(REPORTS / "ARTIFACT").write_text(` -- one statement. Readers like
            # qquant_shadow.py mention the artifact on a DIFFERENT line from their own
            # (unrelated) write, and a proximity window still called them writers.
            is_writer = any(artifact in ln and ".write_text" in ln
                            for ln in body.splitlines())
            if is_writer:
                writers.append(py.name)
        for w in writers:
            stem = w[:-3]
            scheduled = any(stem in f.read_text("utf-8", errors="ignore")
                            for f in list((ROOT / "ops").glob("*.sh"))
                            if f.is_file())
            marker = ROOT / "data" / f".sched_{stem}"
            if not scheduled and not marker.exists():
                defects.append(("authority-writer-unscheduled",
                                f"{w} writes {artifact} ({role}) but no ops/ runner references "
                                f"it. An authority artifact nothing refreshes is a gate that "
                                f"cannot mint -- candidates accrue forward evidence they can "
                                f"never cash (measured 2026-08-26)."))


def check_one_way_flags(defects) -> None:
    """A flag an organ can SET must have a path that CLEARS it.

    MEASURED 2026-08-26 (GAP 130): regime_monitor.py writes flag="hibernate" and the gateway
    drops flagged sleeves, but nothing anywhere clears the flag when the regime returns. Under
    the Regime Specialization Law a specialist is SUPPOSED to sleep out of regime and wake in
    it, so every hibernation was a permanent loss of a deliberately-admitted sleeve.
    """
    pairs = [("hibernate", "desks/mt5/research/regime_monitor.py",
              "regime hibernation (specialists must WAKE, RESEARCH 6c)")]
    for token, path, why in pairs:
        p = ROOT / path
        if not p.exists():
            continue
        try:
            body = p.read_text("utf-8", errors="ignore")
        except OSError:
            continue
        sets = f'"{token}"' in body or f"'{token}'" in body
        if not sets:
            continue
        clears = any(k in body for k in ("wake", '"ok"', "clear", "unhibernate", "resume"))
        if not clears:
            defects.append(("one-way-flag",
                            f"{path} SETS '{token}' with no clear/wake path -- {why}. A flag that "
                            f"only ever goes one way is a slow retirement engine wearing a "
                            f"reversible name."))
            continue
        # THE SUBTLER TRAP, measured 2026-08-26: a wake path can EXIST and still be unreachable
        # if its evidence comes from a source the flag itself switches off. regime_monitor
        # recomputes the flag every run (a real wake path) from LIVE LEDGER rows -- but a
        # hibernated sleeve stops trading, stops producing rows, and its trailing window freezes
        # at the values that hibernated it. Starved recovery evidence is a one-way door wearing
        # a two-way name, and it is invisible to a grep for "wake".
        if "live_ledger" in body or "ledger" in body.lower():
            defects.append(("clear-evidence-starved",
                            f"{path} can clear '{token}', but its clear condition reads the LIVE "
                            f"ledger -- which the flag itself stops filling. A hibernated sleeve "
                            f"produces no trades, so its window never recovers and the wake path "
                            f"can never fire. Drive the wake from ZERO-CAPITAL SHADOW replay, "
                            f"which keeps running while the sleeve is dark ({why})."))


def check_page_before_spawn(defects) -> None:
    """No paging path may spawn a heavyweight process before its dedupe check.

    MEASURED 2026-08-26: lawful._page() ran `bash -c source ops/brain_env.sh`, which spawns
    libs.ops.repair_mode at source time -- so a page SUPPRESSED by the 6h dedupe still bought a
    ~73MB python interpreter, every call. The alert was correctly silent while the cost ran
    unbounded, which is exactly why it went unnoticed for hours.
    """
    for rel in ("libs/ops/lawful.py",):
        p = ROOT / rel
        if not p.exists():
            continue
        try:
            body = p.read_text("utf-8", errors="ignore")
        except OSError:
            continue
        if "brain_env.sh" not in body:
            continue
        # the CODE site, not a docstring mention: the subprocess line that sources it
        m_spawn = re.search(r"subprocess\.run\([^)]*brain_env\.sh", body, re.DOTALL)
        if not m_spawn:
            continue
        pre = body[:m_spawn.start()]
        if "brain_page_stamps" not in pre and "_PAGE_DEDUPE" not in pre:
            defects.append(("page-spawns-before-dedupe",
                            f"{rel} spawns brain_env.sh (which starts repair_mode at source "
                            f"time) BEFORE any dedupe check -- a suppressed page still costs a "
                            f"python interpreter. Dedupe first, spawn second."))


def check_recursion_rule_applied(defects) -> None:
    """THE RULE THAT AUTOMATES THIS FILE'S OWN GROWTH.

    Every FIXED gap-register row should leave behind a standing check, or the desk relearns the
    same lesson. This compares recent FIXED rows against the CHECKS registry and names the ones
    that closed without a fence -- so 'turn defects into checks' stops depending on whoever
    happens to remember it (the recursion rule, made mechanical).
    """
    reg = ROOT / "docs/GAP_REGISTER.md"
    if not reg.exists():
        return
    try:
        rows = reg.read_text("utf-8", errors="ignore").splitlines()
    except OSError:
        return
    fixed = [ln for ln in rows if ln.startswith("| 1") and "FIXED" in ln.upper()]
    if not fixed:
        return
    slugs = {name for name, _fn in CHECKS}
    unfenced = 0
    for ln in fixed[-15:]:                       # the recent tail, not all history
        cells = [c.strip() for c in ln.split("|")]
        title = cells[2].lower() if len(cells) > 2 else ""
        words = {w.strip("*`,.:;()") for w in title.split() if len(w) > 5}
        if not any(any(w in s for w in words) for s in slugs):
            unfenced += 1
    if unfenced >= 5:
        defects.append(("recursion-rule-unapplied",
                        f"{unfenced} of the last 15 FIXED gap rows have no matching check in "
                        f"max_audit's registry ({len(slugs)} checks). A defect fixed without a "
                        f"fence is a lesson the desk will pay for twice -- the recursion rule "
                        f"exists precisely so remembering is not the mechanism."))


CHECKS += [("verifier-reads-injection", check_verifier_reads_injection),
           ("authority-writer-scheduled", check_authority_writers_scheduled),
           ("one-way-flag", check_one_way_flags),
           ("page-before-spawn", check_page_before_spawn),
           ("recursion-rule", check_recursion_rule_applied)]
