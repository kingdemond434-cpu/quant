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
   data/max_audit_acks.json -- no permanent burial, ever
 - defects persisting >48h un-acked ESCALATE to the principal page (PRINCIPAL_ACTION.md):
   nothing can sit below max for more than two days without either being fixed or him knowing
 - one broken check must never kill the sweep (every check is fenced)
"""
from __future__ import annotations

import contextlib
import json
import re
import subprocess
import sys
import time
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# THE AUDITOR WAS THE ONE SCRIPT THAT FORGOT ITS OWN PATH. Ten of the 55 checks import `libs.*`
# lazily inside their bodies -- the whole findings family, both mining checks, data-utilization,
# depth-parity, source-backlog, carryover. Run as `python3 scripts/max_audit.py`, sys.path[0] is
# scripts/, so every one of them raised ModuleNotFoundError, got caught by _fenced, and was
# reported as ONE defect line among two dozen. A blind checker does not merely miss defects: it
# makes the audit's coverage claim false while the report still looks healthy. 18% of the desk's
# own auditor was dark, and the fence is what made that survivable enough to go unnoticed.
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

LOGS = ROOT / "data/cro_ai_logs"
REPORT = ROOT / "data/max_audit_report.json"
ACKS = ROOT / "data/max_audit_acks.json"
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
    "dataaxis-dig":     ("dataaxis_*.log",           1500, 96.0),
    "litminer-dig":     ("litminer_*.log",           1500, 216.0),
    "prospector-dig":   ("prospector_*.log",         1500, 216.0),
    "blindrediscovery": ("blindrediscovery_*.log",   1500, 840.0),
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
    "brain-cycle": ("data/decision_ledger.json", "docs/research/cadence_duties.md"),
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
}


def _artifact_age_h(organ: str) -> float:
    """Hours since this organ's freshest declared artifact advanced (inf if none)."""
    best = 0.0
    for rel in ORGAN_ARTIFACTS.get(organ, ()):
        try:
            best = max(best, (ROOT / rel).stat().st_mtime)
        except OSError:
            continue
    return (NOW - best) / 3600 if best else float("inf")


def check_organs(defects) -> None:
    for organ, (pat, min_b, max_h) in ORGANS.items():
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
            defects.append((f"organ-stale-{organ}",
                            f"{organ}: last SUCCESSFUL run {age_h:.0f}h ago "
                            f"(cadence expects <= {max_h:.0f}h) -- silently degraded"))


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
    if not pat:
        return False
    try:
        return subprocess.run(["pgrep", "-f", pat], capture_output=True,
                              timeout=10, check=False).returncode == 0
    except (OSError, subprocess.SubprocessError):
        return False               # cannot prove it is alive -> fall through and report


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


#: Long-lived daemons whose code is loaded ONCE at process start. Add any new always-on service.
_DAEMONS = {
    "quant-cashcarry": "scripts/run_cashcarry_executor.py",
    "quant-deadman": "scripts/run_deadman_switch.py",
    "quant-liquidations": "scripts/liquidation_listener.py",
    "quant-dashboard": "scripts/serve_dashboard.py",
}


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
        if m.split(".")[0] not in {"libs", "app", "scripts"}:
            continue
        for cand in (ROOT / (m.replace(".", "/") + ".py"),
                     ROOT / m.replace(".", "/") / "__init__.py"):
            if cand.exists():
                _import_closure(cand, seen)
    return seen


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
    import subprocess
    for svc, rel in _DAEMONS.items():
        entry = ROOT / rel
        if not entry.exists():
            continue
        sd_pid, state = "", ""
        with contextlib.suppress(OSError, subprocess.SubprocessError):
            sd_pid = subprocess.run(["systemctl", "show", "-p", "MainPID", "--value", svc],
                                    capture_output=True, text=True, timeout=10).stdout.strip()
            state = subprocess.run(["systemctl", "show", "-p", "ActiveState", "--value", svc],
                                   capture_output=True, text=True, timeout=10).stdout.strip()
        workers = _worker_pids(rel)
        if not workers:
            continue                                  # not running -- check_organs owns that
        # OWNERSHIP first: a fix cannot ship into a process the supervisor does not control.
        if sd_pid not in {str(p) for p in workers}:
            oldest = min(workers, key=lambda p: Path(f"/proc/{p}").stat().st_mtime)
            age = (NOW - Path(f"/proc/{oldest}").stat().st_mtime) / 3600.0
            storm = (" and the unit is stuck in auto-restart, respawning against it"
                     if state == "activating" else "")
            defects.append((f"daemon-unsupervised-{svc}",
                            f"{svc} work is being done by pid {oldest} (up {age:.1f}h) which "
                            f"systemd does NOT own (MainPID={sd_pid or 'unknown'}, "
                            f"state={state or 'unknown'}){storm}. `systemctl restart` cannot "
                            "replace this process, so fixes do not ship and crash-recovery is "
                            "an illusion. Stop the unit, kill the orphan, start the unit, and "
                            "verify MainPID matches the worker."))
        for pid in sorted(workers, key=lambda p: Path(f"/proc/{p}").stat().st_mtime)[:1]:
            try:
                started = Path(f"/proc/{pid}").stat().st_mtime
            except OSError:
                continue
            stale = sorted(p for p in _import_closure(entry) if p.stat().st_mtime > started)
            if stale:
                age = (NOW - started) / 3600.0
                names = ", ".join(p.relative_to(ROOT).as_posix() for p in stale[:4])
                defects.append((f"daemon-stale-code-{svc}",
                                f"{svc} (pid {pid}, up {age:.1f}h) imports {len(stale)} file(s) "
                                f"MODIFIED SINCE IT STARTED: {names} -- python loaded the old "
                                "module at start, so every fix in those files is INERT in the "
                                "running process. Restart the unit and verify the new behaviour "
                                "appears in its output; a committed fix is not a shipped fix."))


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
    for seat, n in (m.get("seat_blanks") or {}).items():
        if int(n) >= 3:
            defects.append((f"seat-chronic-{seat.split('/')[-1]}",
                            f"panel seat {seat} blanked {n}x -- chronic capacity failure, "
                            "swap-candidate with evidence"))


def check_findings(defects) -> None:
    d = _j(ROOT / "data/findings_ledger.json", {})
    old = [f for f in d.get("findings", [])
           if f.get("ruling") == "accepted" and not f.get("fixed")
           and (datetime.now(tz=UTC) - datetime.fromisoformat(f["raised"])).days > 14]
    if old:
        ids = ", ".join(f["id"] for f in old[:5])
        defects.append(("findings-rotting",
                        f"{len(old)} ACCEPTED panel findings unfixed >14d ({ids}) -- the loop "
                        "the audit system exists for is open"))


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
    state = _j(ROOT / "data/cadence_state.json", {})
    last = state.get("last_blind_rediscovery")
    seen = _j(ROOT / "data/blind_trigger_baseline.json", {})

    umap = _j(ROOT / "data/data_universe_map.json", {})
    srcs = umap.get("sources", {})
    n_sources = len(srcs) if isinstance(srcs, (dict, list)) else 0
    gy = ROOT / "docs/graveyard.md"
    n_grave = (sum(1 for ln in gy.read_text("utf-8").splitlines() if ln.startswith("| "))
               if gy.exists() else 0)

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
            defects.append(("recorder-scope-shrank",
                            f"recorder futures tape has {live} symbols written in the last "
                            "30min (expansion floor is 20) -- forward-tape breadth regressed "
                            "or the recorder stalled"))
    # bybit second-venue recorder must still exist
    if not (ROOT / "scripts/run_recorder_bybit.py").exists():
        defects.append(("bybit-recorder-gone", "second-venue (bybit) recorder script removed -- "
                        "cross-venue tape breadth lost"))
    # CI GATE must be GREEN -- a red desk-wide gate is the safety net down for everyone and
    # sat UNDETECTED for 81h (2026-07-22..23: a stale deadman test failed at HEAD while the
    # brain cycle that runs run_ci was quota-dead, so nothing surfaced the red). run_ci writes
    # data/.ci_last_run.json on every run; surface a red result mechanically so it enters the
    # 48h escalation path instead of hiding until a human notices.
    ci_marker = ROOT / "data/.ci_last_run.json"
    if ci_marker.exists():
        with contextlib.suppress(OSError, json.JSONDecodeError):
            ci = json.loads(ci_marker.read_text("utf-8"))
            if ci.get("ok") is False:
                defects.append(("ci-gate-red",
                                f"last CI run ({ci.get('ts')}) was RED -> {ci.get('failed')}; "
                                "the desk-wide safety gate is down. Run scripts/run_ci.py + fix"))


def check_dig_depth(defects) -> None:
    """Depth guard: a substantial dig log that shows NO depth markers (never mined a reply
    chain, followed a fork, or chased a citation) is breadth-theater -- flag it. Depth quality
    ultimately shows in output and is judged by red-team/maximization; this catches the gross
    wide-and-shallow case mechanically."""
    markers = ("repl", "comment", "thread", "fork", "citation", "issue", "discussion",
               ">=2", "deep", "exhaust", "debunk")
    for pat in ("frontier_*.log", "dataaxis_*.log", "prospector_*.log", "litminer_*.log"):
        logs = sorted(LOGS.glob(pat), key=lambda p: p.stat().st_mtime, reverse=True)
        if not logs:
            continue
        newest = logs[0]
        _mand = ROOT / "data/depth_mandate_baseline"
        if not _mand.exists():
            _mand.write_text(str(NOW))
        try:
            _base = float(_mand.read_text().strip())
        except Exception:
            _base = NOW
        if newest.stat().st_mtime < _base:
            continue                                  # pre-mandate dig -- not judged
        if (NOW - newest.stat().st_mtime) > 4 * 86400:
            continue                                  # stale digs handled by check_organs
        if newest.stat().st_size < 1500:
            continue                                  # stub/quota-death handled elsewhere
        txt = newest.read_text("utf-8", errors="ignore").lower()
        hits = sum(1 for m in markers if m in txt)
        if hits < 2:
            defects.append((f"dig-shallow-{newest.stem}",
                            f"{newest.name}: substantial dig with <2 depth markers "
                            f"({hits}) -- breadth-theater, no reply/fork/citation mining "
                            "evident. Depth mandate not honored."))


def check_interrogation(defects) -> None:
    """The last successful brain cycle must show evidence it ran the self-interrogation battery.
    A cycle that did not probe is a cycle that trusted itself -- the exact failure this catches.
    Only judged on cycles that ran AFTER the protocol existed."""
    base_f = ROOT / "data/interrogation_baseline"
    if not base_f.exists():
        base_f.write_text(str(NOW))
        return
    try:
        base = float(base_f.read_text().strip())
    except Exception:
        return
    cyc = [p for p in LOGS.glob("2026*_*.log")
           if p.stat().st_mtime >= base and p.stat().st_size >= 2000]
    if not cyc:
        return                                        # no post-protocol successful cycle yet
    newest = max(cyc, key=lambda p: p.stat().st_mtime)
    txt = newest.read_text("utf-8", errors="ignore").lower()
    if not any(k in txt for k in ("interrogat", "probe", "verified with a fresh read",
                                  "self-interrog", "angle")):
        defects.append(("cycle-skipped-interrogation",
                        f"{newest.name}: last successful cycle shows no self-interrogation "
                        "evidence -- it trusted itself instead of probing. Protocol not honored."))


def check_generation(defects) -> None:
    """Hypothesis testing is the primary output. If SUCCESSFUL brain cycles have run since a
    baseline but last_live_generate has not advanced, generation is being skipped -- escalate.
    Also flags the simple case: generation owed and long-stale."""
    cs = _j(ROOT / "data/cadence_state.json", {})
    last_gen = cs.get("last_live_generate") or cs.get("gen_done_fred_macro")
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
                        f"a successful brain cycle ran but last_live_generate has not advanced "
                        f"(last gen {last_gen}) -- hypothesis testing, the desk's PRIMARY output, "
                        "is being crowded out by meta-duties. Generation-first duty not honored."))


def check_self_sufficiency(defects) -> None:
    """The meta-check: is the desk finding its own gaps, or is the principal still doing it?
    Reads the blind-spot ledger; if over the recent window the principal is the primary finder,
    the whole maximization apparatus is not yet working -- the top-level defect."""
    lg = ROOT / "data/blind_spot_ledger.jsonl"
    if not lg.exists():
        return
    rows = []
    for line in lg.read_text("utf-8").splitlines():
        with contextlib.suppress(Exception):
            rows.append(json.loads(line))
    live = [r for r in rows if not r.get("baseline")]  # judge post-baseline gaps only
    if len(live) < 8:
        return                                          # not enough signal yet
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
    READS (file-path citations proving it actually looked), not bare 'verified' prose."""
    flag = ROOT / "data/ANTIRUBBERSTAMP_ACTIVE"
    if not flag.exists():
        return
    cyc = [p for p in LOGS.glob("2026*_*.log")
           if p.stat().st_size >= 2000 and (NOW - p.stat().st_mtime) < 2 * 86400]
    if not cyc:
        return
    newest = max(cyc, key=lambda p: p.stat().st_mtime)
    t = newest.read_text("utf-8", errors="ignore")
    cites = len(set(re.findall(r"[\w/]+\.(?:py|json|md|sh|txt)", t)))
    if cites < 5:
        defects.append(("rubberstamp-enforced",
                        f"{newest.name}: anti-rubber-stamp ACTIVE but the cycle cites only {cites} "
                        "named reads -- interrogation lacks verified-read evidence. Cite the "
                        "specific file+value per probe angle, do not rubber-stamp."))


def check_clock_saturation(defects) -> None:
    """OBJECTIVE #2 CLOCK-SATURATION DUTY (principal 2026-07-23), made mechanical.

    Every VERIFIED data axis must have a pre-registered hypothesis ACCRUING within 7 days. An
    empty forward-validation slot is idle capital's research twin: the axis was ingested (real
    cost paid) but is generating zero evidence, so the discovery objective is silently stalled.

    This duty shipped as prompt text only -- and prompt-only duties are aspirations. The desk's
    recursion rule is that every manual probe becomes a standing automatic check, so it is fenced
    here. Axes are read from the Bronze lake (what was actually ingested, not what a doc claims);
    clocks are read from cadence_state gen_done_* (what actually ran)."""
    bronze = ROOT / "data/lake/bronze"
    cad_p = ROOT / "data/cadence_state.json"
    if not bronze.exists() or not cad_p.exists():
        return
    try:
        cad = json.loads(cad_p.read_text("utf-8"))
    except Exception:
        return
    # INPUT STORES are not axes: raw price/metrics lakes feed constructions but cannot carry
    # a hypothesis themselves (the constructions built FROM them do). Excluding them keeps this
    # check pointed at genuinely idle research axes instead of manufacturing false defects.
    _input_stores = {"futclose_daily", "oi_ls_daily", "fx", "index", "crypto", "binance_metrics"}
    axes = sorted(d.name for d in bronze.iterdir() if d.is_dir() and d.name not in _input_stores)
    if not axes:
        return
    stale = []
    for ax in axes:
        ts = cad.get(f"gen_done_{ax}") or cad.get(f"gen_done_{ax}_family")
        if not ts:
            stale.append(f"{ax}(never)")
            continue
        try:
            age_d = (NOW - datetime.fromisoformat(ts).timestamp()) / 86400.0
            if age_d > 7:
                stale.append(f"{ax}({age_d:.0f}d)")
        except Exception:
            stale.append(f"{ax}(unparsable)")
    if stale:
        defects.append((
            "clock-saturation",
            f"OBJECTIVE #2 breach: {len(stale)}/{len(axes)} verified axes have NO hypothesis "
            f"accruing within 7d -- {', '.join(stale[:8])}"
            f"{' ...' if len(stale) > 8 else ''}. An empty forward clock is idle research "
            "capital: pre-register a hypothesis on each, or ledger why the axis is not yet "
            "testable (e.g. forward history under the gauntlet minimum)."))


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
    bleed detection -- the exact silent-leak failure mode the integrity watch exists to kill."""
    fj = ROOT / "web/trade_forensics.json"
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


def check_bnb_funded(defects) -> None:
    """BNB fee-burn is enabled (feeBurn:True) but only DISCOUNTS when BNB is held. Audit 2026-07-24:
    balance 0 -> the whole commission line was paid at rack rate while the desk believed the ~25%
    discount was active. feeBurn:True is STATE; a funded BNB balance is the OUTCOME that matters."""
    try:
        from libs.execution import binance_testnet as _fut
        bal = 0.0
        for b in _fut._signed("/fapi/v2/balance", {}):
            if b.get("asset") == "BNB":
                bal = float(b.get("balance", 0.0))
        if bal <= 0.0:
            defects.append(("bnb-burn-unfunded",
                            "fee-burn is ON (feeBurn:True) but BNB balance is 0 -- the ~25% "
                            "discount is INERT and commissions are paid at rack rate. Fund a small "
                            "BNB balance (or accept it as a testnet limitation and ledger why)."))
    except Exception:
        pass


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
        ("prospector-product", "docs/research/prospector_watchlist.md", 30, 100),
        ("litminer-product", "docs/research/*iterature*coverage*.md", 30, 50),
        ("frontier-product", "docs/research/prospector_coverage.md", 30, 100),
        ("crypto-factory", "web/autodiscovery_crypto.json", 30, 100),
        ("forensics", "web/trade_forensics.json", 30, 50),
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


#: Every doc where a finding can be WRITTEN. The register is where findings are WORKED; anything
#: written here and absent there is invisible to the daily cycle.
_FINDING_DOCS = (
    "docs/SYSTEM_REVIEW.md",
    "docs/BLIND_SPOT_AUDIT.md",
    "docs/research/micro_audit_inbox.md",
    "docs/research/improvement_inbox.md",
    "docs/research/panel_rulings.md",
)
#: Finding-bearing docs deliberately out of scope, with the reason -- so the scope check can tell
#: "consciously excluded" from "quietly unmonitored".
_FINDING_DOCS_EXCLUDED = {
    "docs/research/panel_inbox.md": "raw panel transcript -- rulings are the distilled output",
    "docs/research/feed_inbox.md": "literature feed, not desk findings",
    "docs/research/data_axis_watchlist.md": "source cards -- governed by §33 dispositions",
    "docs/research/discovery_hypotheses.md": "hypotheses -- governed by §33 / the trial ledger",
    "docs/research/literature_coverage.md": "coverage log -- governed by §33",
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
    "docs/DIGGING_CHARTER.md": "the law itself",
    "docs/OPERATOR_COMPACT.md": "operator agreement, not findings",
    "docs/GO_LIVE_CHECKLIST.md": "checklist -- gated by GAP #2",
    "docs/EVIDENCE_GATED_PROGRESSIONS.md": "progression definitions, not findings",
    "docs/KILL_THESIS.md": "kill criteria, not findings",
    "docs/REPO_EXTRACTION.md": "adoption record, not findings",
    "docs/RD_AGENT_AUDIT.md": "historical audit -- superseded by SYSTEM_REVIEW",
    "docs/institutional_knowledge.md": "knowledge base, not an obligation list",
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
        "weekly deep-cold-audit output -- CADENCED PRODUCER (§36); findings flow to\n"
        "improvement_inbox and GAP_REGISTER rows (§35). Each dated report is one\n"
        "sweep's snapshot, superseded by the next, never converted in place.",
    "docs/EXTERNAL_PANEL_DOSSIER.md":
        "GENERATED dossier -- its numbered block is a copy of the register table; original panel "
        "findings enter via panel_inbox -> panel_rulings, which are in scope",
    # SURFACED 2026-07-29, the moment check_findings_scope stopped being blind. These three
    # carried 106 numbered items outside the §35 scan. They are NOT findings owing register rows:
    "docs/research/MEASUREMENT_DOCTRINE.md":
        "DOCTRINE (per ARTIFACT_GOVERNANCE) -- its 5 numbered lines are the measurement CLASSES "
        "the law binds (timestamp integrity, data correctness, feature validity, cost realism, "
        "attribution), not defects anyone owes a row for",
    "docs/research/SUBSYSTEM_TRIAGE.md":
        "SELF-DISPOSING triage register -- every numbered item sits under an explicit "
        "BUILT/BUILD/QUEUE/REJECT verdict IN THE DOC. check_triage_disposition proves that "
        "still holds and keeps the open (BUILD/QUEUE) items visible",
    "docs/research/TRIAGE_ADDENDUM.md":
        "SELF-DISPOSING triage register (items 82-101), same instrument as SUBSYSTEM_TRIAGE "
        "and proven by the same check",
}

#: Triage registers excluded from §35 because they disposition their own items inline. The
#: exclusion is only honest while that stays TRUE, so it is checked rather than trusted.
_TRIAGE_DOCS = ("docs/research/SUBSYSTEM_TRIAGE.md", "docs/research/TRIAGE_ADDENDUM.md")
_TRIAGE_VERDICTS = ("BUILT", "BUILD", "QUEUE", "REJECT")
#: BUILD/QUEUE are OPEN work. An exclusion that let them vanish would be the bypass the scope
#: check exists to prevent, so they are counted back out loud.
_TRIAGE_OPEN = ("BUILD", "QUEUE")


#: §36 PRODUCERS: artifacts that accumulate inventory under a cadence STATED IN THEIR OWN PROSE
#: and, until now, enforced by nothing. Each maps to the max age its own text promises. This is
#: the miner failure in its purest form -- a conversion rule written down, with no clock behind it.
_PRODUCER_CADENCE = {
    "docs/research/weak_signal_registry.md": (
        3.0, "§23: >=2 weak signals from INDEPENDENT paths auto-promote to hypothesis generation, "
             "'checked each cycle during inbox triage' -- convention, never verified"),
    "docs/research/canary_searches.md": (
        4.0, "re-run each digging session; an unexpected shift triggers targeted rediscovery "
             "BEFORE the normal cadence -- nothing confirmed the canaries were re-run"),
    "docs/research/generation_due.md": (
        8.0, "the cadence engine flags scoped generate runs and the brain executes then marks "
             "them -- nothing checked a flagged run was ever executed"),
    "docs/research/adoption_queue.md": (
        35.0, "trigger-gated methods (fracdiff, dollar bars, ...) -- nothing notices when a "
              "precondition ARRIVES, so a due adoption waits forever"),
    # The register is a producer too -- the one every other law routes into. Its own header
    # promises a re-rank every daily cycle; check_gap_register_health reads the self-declared
    # stamp, and this is the file-level backstop if the stamp itself stops being written.
    "docs/GAP_REGISTER.md": (
        3.0, "re-ranked at the START of every daily AI cycle by its own rule -- the organ §35 and "
             "§36 both depend on, and it was checked by nothing"),
}
#: Artifacts that are terminal by nature: templates, forensic write-ups, protocol libraries. They
#: accumulate no inventory, so they owe no cadence -- recorded here so "no law" is a DECISION.
_TERMINAL_ARTIFACTS = {
    "docs/research/FRONTIER_MINER_TEMPLATE.md": "template spec -- instantiated, not converted",
    "docs/research/GAP34_FORENSIC.md": "forensic write-up for a closed gap",
    "docs/research/self_interrogation_patterns.md": "protocol library -- applied, not converted",
    "docs/playbooks/carry.md": "runbook -- followed, not converted",
    "docs/playbooks/go_live.md": "runbook -- followed; the gate is GAP #2",
    "docs/playbooks/ops_checklist.md": "runbook -- followed, not converted",
    "docs/EXTERNAL_PANEL_DOSSIER.md":
        "derived snapshot -- REGENERATED from live state on every panel run by "
        "generate_external_review_doc.py, never an inventory. Its findings flow panel responses "
        "-> panel_inbox -> panel_rulings -> GAP_REGISTER rows (§35), so converting the dossier "
        "itself is meaningless: the next run overwrites it. Terminal by construction.",
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
    """
    r = subprocess.run([sys.executable, "-m", "pytest", "tests/", "--collect-only", "-q"],
                       cwd=str(ROOT), capture_output=True, text=True, timeout=300, check=False)
    out = (r.stdout or "") + (r.stderr or "")
    if r.returncode != 0 or "error" in out.lower().split("short test summary")[0]:
        why = [ln for ln in out.splitlines() if "ERROR" in ln or "ModuleNotFound" in ln][:4]
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
    # docs/research/ARTIFACT_GOVERNANCE.md is the standing classification register: any artifact
    # named in its decision table is claimed BY THAT DECISION. Without this the register was a
    # document nobody's check consulted -- so classifying eight artifacts cleared nothing, and
    # writing the register itself made the count WORSE by adding an unclaimed file. A governance
    # doc that does not feed the governance check is the exact prose-only-duty failure the desk
    # keeps re-learning.
    _reg = ROOT / "docs/research/ARTIFACT_GOVERNANCE.md"
    with contextlib.suppress(OSError):
        _txt = _reg.read_text("utf-8")
        claimed |= set(re.findall(r"`(docs/[A-Za-z0-9_./-]+\.md)`", _txt))
        claimed |= {f"docs/research/{m}" for m in re.findall(r"`([A-Z][A-Z0-9_]+\.md)`", _txt)}
        claimed.add("docs/research/ARTIFACT_GOVERNANCE.md")   # the register governs itself
    # A trailing-slash claim governs a whole DIRECTORY CLASS. Generators (the weekly deep sweep)
    # emit dated instances forever, so exact-path claims could never keep up and the check would
    # fire permanently on correctly-governed output. Claim the class once; instances inherit it.
    claimed_prefixes = tuple(c for c in claimed if c.endswith("/"))
    audit_src = ""
    with contextlib.suppress(OSError):
        audit_src = Path(__file__).read_text("utf-8")
    unclaimed = []
    for p in sorted((ROOT / "docs").rglob("*.md")):
        rel = p.relative_to(ROOT).as_posix()
        if (rel in claimed or rel.startswith(claimed_prefixes)
                or rel.endswith("GAP_REGISTER.md")):
            continue
        if p.name in audit_src:      # named by some other check -- already governed
            continue
        unclaimed.append(p.name)
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


def check_orphan_code(defects) -> None:
    """MAP-vs-TERRITORY (audit 2.x): the desk flags idle DATA/capital/clocks but not idle CODE.
    Flags library packages that are almost entirely unreachable from any scripts/ entry point --
    e.g. libs/backtest (the independent cross-check engine) applied to zero strategies. Bounded:
    reports only near-fully-orphaned packages to stay cheap and low-noise."""
    libs = ROOT / "libs"
    scripts = ROOT / "scripts"
    if not (libs.exists() and scripts.exists()):
        return
    # TRANSITIVE reachability (corrected 2026-07-29). This was a one-hop grep -- "is the package
    # named under scripts/" -- and it reported libs/discovery and libs/backtest as orphaned when
    # both are BASE LAYERS reached through other libs packages that say so in their own
    # docstrings ("Reuses the discovery capacity model") and import them explicitly. Acting on
    # that would have deleted working code ten call sites depend on. meta_research_review's
    # complexity_audit was fixed the same way; this check kept the bug, so the two disagreed
    # about the same repo -- and a checker that contradicts another checker teaches everyone to
    # ignore both.
    _pkgs = [d.name for d in libs.iterdir() if d.is_dir() and (d / "__init__.py").exists()]

    def _refs(text: str) -> set[str]:
        return {x for x in _pkgs if f"libs.{x}" in text}

    _edges = {}
    for _p in _pkgs:
        _body = ""
        for _m in (libs / _p).glob("*.py"):
            with contextlib.suppress(OSError):
                _body += _m.read_text("utf-8", errors="ignore")
        _edges[_p] = _refs(_body) - {_p}
    entry_text = "\n".join(f.read_text("utf-8", errors="ignore")
                            for f in scripts.glob("*.py"))
    _reached, _frontier = _refs(entry_text), _refs(entry_text)
    for _ in range(12):
        _nxt = {q for pp in _frontier for q in _edges.get(pp, ()) if q not in _reached}
        if not _nxt:
            break
        _reached |= _nxt
        _frontier = _nxt
    suspicious = []
    for pkg in sorted(d for d in libs.iterdir() if d.is_dir() and (d / "__init__.py").exists()):
        name = pkg.name
        mods = [m.stem for m in pkg.glob("*.py") if m.stem != "__init__"]
        if len(mods) < 3:
            continue
        # reachable by ANY import path, direct or through another libs package
        if name in _reached:
            continue
        suspicious.append(f"{name}({len(mods)} modules)")
    if suspicious:
        defects.append(("orphan-code",
                        "library package(s) unreachable from ANY entry point, directly or "
                        "transitively (idle code -- "
                        f"the class never monitored): {', '.join(suspicious[:6])}. Wire the "
                        "safeguard (e.g. libs/backtest cross_engine) or retire on the record -- "
                        "verify against dynamic imports before deleting."))


#: Docs where mined finds ACCUMULATE UN-DISPOSITIONED -- the only place §33 inventory can rot.
#: Deliberately excluded, each for a reason (the check must flag rot, not paperwork):
#:   graveyard.md              -- a graveyard entry IS a disposition; terminal by construction
#:   negative_knowledge.md     -- own terminal schema (``[priority: ...] review-due: <date>``)
#:   search_operator_library.md-- own terminal schema (``[status: active|watch|archived]``)
#:   prospector_watchlist.md   -- prose STEP headers, not carded finds
_DIG_DOCS = (
    "docs/research/data_axis_watchlist.md",
    "docs/research/feed_inbox.md",
    "docs/research/discovery_hypotheses.md",
    "docs/research/literature_coverage.md",
)
#: Card-bearing docs deliberately OUT of §33 scope, each with its reason. Kept explicit so the
#: scope check below can tell "consciously excluded" from "quietly unmonitored".
_DIG_DOCS_EXCLUDED = {
    "docs/research/micro_audit_inbox.md":
        "audit findings, not mined finds -- own rotting-findings check",
    "docs/research/panel_inbox.md": "external panel output -- own rulings/scoring loop",
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


def _mine_thresholds() -> dict:
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


def _mine_backing() -> dict:
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
        tier_calibration,
        update_ratchet,
    )

    ledger = load_ledger(MINE_LEDGER)
    if len(ledger) < 2:
        return  # a single snapshot cannot measure flow -- not a defect, just no history yet
    thr = _mine_thresholds()
    flow = flow_stats(ledger)
    n_names = len({str(i.get("n", "")) for r in ledger for i in r["items"]})
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
    try:
        out = subprocess.run(["git", "status", "--porcelain", "--", *_DIG_TRACKED],
                             cwd=ROOT, capture_output=True, text=True, timeout=20)
    except (OSError, subprocess.SubprocessError):
        return  # no git available -- the check simply does not apply here
    if out.returncode != 0:
        return
    stale = []
    for line in out.stdout.splitlines():
        if len(line) > 3:
            code, path = line[:2].strip() or "??", line[3:].strip()
            stale.append(f"{Path(path).name}[{code}]")
    if stale:
        defects.append((
            "dig-output-uncommitted",
            f"§33: dig output UNCOMMITTED -- {', '.join(stale[:8])}. Output not "
            "committed and pushed by end of cycle DID NOT HAPPEN and earns zero credit: git is "
            "the institutional memory, VPS disk is not. Commit, push, and VERIFY the push."))


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
CHECKS = [("carryover-skipped", check_carryover_skipped),
          ("organs", check_organs), ("stubs", check_stub_deaths),
                      ("stale-daemons", check_stale_daemons),
                      ("panel", check_panel), ("coverage", check_coverage),
                      ("model-freshness", check_model_freshness),
                      ("meta-research", check_meta_research),
                      ("findings", check_findings), ("idle", check_idle_capability),
                      ("directives", check_directives), ("verify", check_verify_lag),
                      ("blind", check_blind_trigger),
                      ("self-application", check_self_application),
                      ("dig-depth", check_dig_depth),
                      ("interrogation", check_interrogation),
                      ("generation", check_generation),
                      ("clock-saturation", check_clock_saturation),
                      ("vendor-replacement", check_vendor_replacement),
                      ("forensics-fresh", check_forensics_fresh),
                      ("carry-funding-measured", check_carry_funding_measured),
                      ("memory-hygiene", check_memory_hygiene),
                      ("prompt-layer", check_prompt_layer),
                      ("gate-optimality", check_gate_optimality),
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
                      ("test-suite", check_test_suite_collectable),
                      ("triage-disposition", check_triage_disposition),
                      ("artifact-governance", check_artifact_governance),
                      ("orphan-code", check_orphan_code),
                      ("mine-conversion", check_mine_conversion),
                      ("mine-flow", check_mine_flow),
                      ("mine-gate", check_mine_gate),
                      ("mine-scope", check_mine_scope),
                      ("dig-uncommitted", check_dig_uncommitted),
                      ("depth-parity", check_depth_parity),
                      ("source-backlog", check_source_backlog),
                      ("rejection-shadow", check_rejection_shadow),
                      ("post-gate0-activation", check_post_gate0_activation),
                      ("production", check_production),
                      ("bnb-funded", check_bnb_funded),
                      ("self-sufficiency", check_self_sufficiency),
                      ("rs-detect", check_rubberstamp_detector),
                      ("rs-enforce", check_rubberstamp_enforcement)]


PAID_TARGETS = ROOT / "docs/research/paid_dataset_targets.md"
HOLDINGS_RECORD = ROOT / "docs/research/holdings_record.json"   # git-tracked, ratchets UP only
#: Data-surface high-water mark. Machine-local BY NECESSITY: it counts gitignored `data/` holdings,
#: so a committed figure makes every clone look like it lost the VPS's entire lake.
HOLDINGS_LOCAL = ROOT / "data/holdings_surface_local.json"


def check_paid_target_registry(defects) -> None:
    """§39: the paid-dataset target registry must exist, be hunted, and GROW.

    §38 hunts a replacement when a source fails -- reactive. §39 keeps a standing list of every
    valuable paid dataset with a live free-replacement status, so the desk already knows what it
    would do if a vendor vanished. A FIXED list is the same blind spot in a different shape, so
    the list growing is itself the deliverable.
    """
    if not PAID_TARGETS.exists():
        defects.append(("paid-registry-missing",
                        "§39: docs/research/paid_dataset_targets.md is missing -- the desk has no "
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
        rec.setdefault("note", "§39 ratchet: registry size and holdings only grow; a fall is a "
                               "regression defect, never a new normal")
        HOLDINGS_RECORD.write_text(json.dumps(rec, indent=1), "utf-8")
    elif n < best:
        defects.append(("paid-registry-shrank",
                        f"§39: paid-dataset registry fell to {n} entries from a record of {best} "
                        "-- the hunt list may only GROW. Restore the removed targets or record "
                        "why each is genuinely no longer a dataset worth replacing."))
    # a registry nobody advances is a document, not a hunt
    age_d = (NOW - PAID_TARGETS.stat().st_mtime) / 86400.0
    if age_d > 14 and open_items:
        defects.append(("paid-registry-stagnant",
                        f"§39: {open_items} OPEN replacement hunts and the registry has not been "
                        f"touched in {age_d:.0f}d. Every dig must advance the top OPEN item it "
                        "can and ADD any paid dataset it encountered -- a list that never grows "
                        "is the same blind spot in a different shape."))


def check_holdings_never_shrink(defects) -> None:
    """§39(4): non-noise information holdings grow monotonically -- quantity AND quality.

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
                        f"§39(4): information surface fell to {surface} (axes+series) from a "
                        f"record of {best}. Holdings may NEVER shrink -- a dropped source, a "
                        "rotted series or discarded history is a regression by attrition. Restore "
                        "it or record the replacement that supersedes it."))


FEE_RECORD = ROOT / "docs/research/fee_ratio_record.json"   # git-tracked; ratchets DOWN only


def check_fee_carry_ratio(defects) -> None:
    """§40: fees must always shrink RELATIVE to the carry they consume.

    Absolute fees say nothing -- a bigger book pays more and earns more. The viability number is
    what fraction of the harvest the fees eat. This desk went from fees at 2.4x funding to
    commission -133 -> -30 over 7 days once patient-maker opens and the single-book invariant
    landed; that gain becomes the floor, and any material worsening is a defect rather than a new
    normal.
    """
    try:
        import time as _t

        from libs.execution import binance_testnet as _fut
        # PAGINATE (2026-07-26). This called `_signed(/fapi/v1/income, limit=1000)` directly and
        # got back exactly 1000 rows -- the cap. Binance serves <=1000 rows/call, and this book
        # books >1000 income rows in 7 days, so the window silently truncated to its most recent
        # slice: funding read 2.80 against a true 13.57, commission 29.14 against a true 129.18.
        # The understated funding then tripped this function's own flat-book guard, so §40 never
        # fired even once it was registered. Worse, the truncated 2.80 was mistaken for a real
        # flat book and written into the guard's comment as the 07-25 dead-man fire -- the bug
        # manufactured its own justification. `income_summary` is the audited paginated+deduped
        # helper and is the ONLY sanctioned way to read this endpoint (institutional_knowledge:
        # "paginate every venue history endpoint... truncation never throws an error").
        inc = _fut.income_summary(int((_t.time() - 7 * 86400) * 1000))
    except Exception:
        return                                    # venue unreachable is not a fee defect
    funding = float(inc.get("funding", 0.0))
    commission = abs(float(inc.get("commission", 0.0)))
    if funding < 5.0:
        # FLAT-BOOK GUARD: with almost no harvest the ratio explodes for reasons unrelated to
        # execution quality. Firing here would be a false defect, and false defects train the
        # desk to ignore the check.
        return
    ratio = commission / funding
    try:
        rec = json.loads(FEE_RECORD.read_text("utf-8")) if FEE_RECORD.exists() else {}
    except Exception:
        rec = {}
    best = float(rec.get("best_ratio", 9e9))
    if ratio < best:
        FEE_RECORD.write_text(json.dumps(
            {"best_ratio": round(ratio, 4), "commission_7d": round(commission, 2),
             "funding_7d": round(funding, 2),
             "updated": datetime.now(tz=UTC).isoformat(),
             "note": "§40 ratchet: fees as a fraction of funding earned. Ratchets DOWN only -- a "
                     "material worsening is a defect, never a new normal."}, indent=1), "utf-8")
        # NO EARLY RETURN (2026-07-26): banking a new best must never suppress the ABSOLUTE alarm
        # below. The first run on this book would otherwise record fees at 9.5x the harvest as
        # "best ever" and report nothing at all -- a ratchet is a relative test, and a sleeve
        # whose fees exceed its entire harvest is broken in absolute terms however it trends.
    if ratio > best * 1.3 and best < 9e8:
        defects.append((
            "fee-ratio-regression",
            f"§40: fees are eating {ratio:.2f}x the funding harvest (7d: commission "
            f"{commission:.2f} vs funding {funding:.2f}) against a best-ever of {best:.2f}x. "
            "Fees must always fall RELATIVE to carry. Check maker fill-rate (patient opens should "
            "keep it climbing), churn (24h min-hold), BNB burn funding at live, and whether "
            "turnover rose without a matching rise in harvest."))
    if ratio > 1.0:
        defects.append((
            "fee-ratio-above-one",
            f"§40: fees ({commission:.2f}) EXCEED the funding earned ({funding:.2f}) over 7d "
            f"-- ratio {ratio:.2f}x. The sleeve cannot be net-positive while this holds, "
            "regardless of how good the signal is. This is the single most direct drag on CAGR."))


DOCTRINE = ROOT / "ops/principal_doctrine.txt"

# Duties that must reach EVERY organ, not just the brain. The list is explicit rather than
# inferred: a heuristic would either miss a renamed duty or nag about the many duties that are
# CORRECTLY brain-only (audit coverage, red-team panels, risk-path depth, the independence gate).
_UNIVERSAL = ("PROACTIVE BATTERY DUTY", "NO-ORPHANED-RECOMMENDATION LAW", "NOVELTY GATE",
              "TARGET/HORIZON SWEEP DUTY", "RESEARCH-MEMORY DUTY", "FREE-FIRST DATA PROTOCOL",
              "BLIND-SPOT ORIGIN DUTY", "FINDING LIFECYCLE DUTY", "SELF-INTERROGATION DUTY",
              "TWO-STAGE DISCOVERY LAW", "SCREEN-ON-DISCOVERY DUTY", "MINING-NEVER-REGRESSES LAW",
              "NO-CEILING AXIOM", "FREE-FRONTIER AXIOM", "DATA-UTILIZATION")


def check_universal_doctrine(defects) -> None:
    """Every universal duty must live in the SHARED doctrine, and every organ must inject it.

    ORIGIN (2026-07-26): the doctrine ordered every digger to screen new axes (SCREEN-ON-DISCOVERY)
    while the rules that keep screening honest -- novelty gate, target/horizon trial accounting,
    research-memory -- lived only in the brain's own prompt. Diggers were commanded to do the
    dangerous half of the job without the discipline that makes it safe. A universal law parked in
    one organ's prompt is not a law, it is a local habit.
    """
    if not DOCTRINE.exists():
        defects.append(("doctrine-missing",
                        "ops/principal_doctrine.txt is gone -- every organ injects it as its "
                        "system prompt, so the desk is running with no standing law at all"))
        return
    txt = DOCTRINE.read_text("utf-8", errors="ignore")
    missing = [d for d in _UNIVERSAL if d not in txt]
    if missing:
        defects.append(("doctrine-universal-missing",
                        f"universal duties absent from the shared doctrine: {', '.join(missing)}. "
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
CHECKS += [("fee-carry-ratio", check_fee_carry_ratio),
           ("paid-target-registry", check_paid_target_registry),
           ("holdings-ratchet", check_holdings_never_shrink),
           ("universal-doctrine", check_universal_doctrine)]


#: Every reasoning organ. An organ that does not carry the constitution is optimising for
#: something -- it just is not the desk's objective, and nothing in its output will say so.
_CONSTITUTION_ORGANS = ("run_external_panel", "hypothesis_generator", "breadth_expander",
                        "llm_code_auditor", "meta_architect", "llm_blind_researcher",
                        "collector_author", "deep_review", "run_micro_audit")


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
            if "OBJECTIVE_PREAMBLE" not in p.read_text("utf-8", errors="ignore"):
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
    _CALLER_EXEMPT = {"scripts/run_autodiscovery.py": "imports MetaTrader5 -- Windows-only"}

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
            "alignment, horizon calibration or target construction. Four such bugs were found and "
            "fixed on 2026-08-03; a fifth would look exactly like this."))

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
    if orphans:
        defects.append((
            "check-unregistered",
            f"{len(orphans)} check(s) authored but NEVER RUN -- the law they enforce is inert "
            f"while the desk believes it is enforced: {', '.join(orphans)}. Add each to CHECKS "
            "(register BELOW its definition) or justify it in _CHECKS_EXEMPT."))


CHECKS += [("check-registry", check_registry_complete)]


def main() -> None:
    defects: list[tuple] = []
    for label, fn in CHECKS:
        _fenced(fn, defects, label)

    acks = _j(ACKS, {})
    live, acked = [], []
    for did, msg, scope, tr, un in defects:
        a = acks.get(did)
        if a and a.get("until", "") > datetime.now(tz=UTC).isoformat():
            acked.append((did, a.get("reason", "")))
        else:
            live.append((did, msg, scope, tr, un))

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
         "acked": [d for d, _ in acked], "first_seen": first_seen,
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
    _MARK = "MAX-AUDIT ESCALATION"
    existing = PA.read_text("utf-8") if PA.exists() else ""
    # strip any prior escalation block so it never stacks / goes stale
    body = existing.split("\n" + _MARK)[0].split(_MARK)[0].rstrip()
    if overdue:
        head = (f"{_MARK}: {len(overdue)} REPO-scope below-max state(s) >48h unfixed/unacked -- "
                + "; ".join(f"{d}" for d, _ in overdue[:6])
                + (" ..." if len(overdue) > 6 else "") + "\n"
                + "".join(f"  - {d}: {m}\n" for d, m in overdue[:8])
                + (f"  ({runtime_overdue} further RUNTIME-scope defect(s) rest only on untracked "
                   "artifacts and cannot be confirmed or closed from a checkout -- see "
                   "data/max_audit_report.json)\n" if runtime_overdue else ""))
        PA.write_text(head + "\n" + body, "utf-8")   # escalation OWNS line 1
        print(f"ESCALATED to principal page (line 1): {len(overdue)} REPO defect(s) >48h"
              + (f" (+{runtime_overdue} RUNTIME, not paged)" if runtime_overdue else ""))
    elif existing != body + ("\n" if body else ""):
        PA.write_text(body + ("\n" if body else ""), "utf-8")  # cleared: drop stale escalation
        print("escalation cleared: no overdue defects")


if __name__ == "__main__":
    main()
