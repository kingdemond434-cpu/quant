"""THE IMPLEMENTER -- the recommendation ledger's drain, on a clock, with no LLM in the path.

WHY THIS EXISTS (measured on the trading box 2026-09-23)

    docs/research/recommendation_ledger.json held 777 rows -- 333 implemented, 219 OPEN, 108
    rejected, 98 scheduled, 18 done, 1 screened -- and had not been written for 281.7 hours
    (11.7 days). The CEO side was alive the whole time: `frontier_ceo.py` writes CEO_DOCKET.json
    on its own task and proposed 18 undecided items into a ledger that could not receive them.

TWO CAUSES, BOTH REAL, BOTH FIXED RATHER THAN WORKED AROUND.

  1. THE LEDGER CLI COULD NOT RUN ON THE BOX THAT TRADES. `scripts/recommendations.py::_locked`
     did `import fcntl` -- POSIX-only. Every MUTATING subcommand (add / dispose / correct /
     repoint / claim) died with ModuleNotFoundError on Windows while `report` and `verify`, which
     skip the lock, worked perfectly. So the ledger looked healthy from the box and was physically
     unwritable there. Fixed in place: `_flock_exclusive` takes the same exclusive, non-blocking,
     closed-on-exit lock through msvcrt where fcntl is absent.

  2. THE ONLY DRAIN WAS AN LLM CRON ON THE OTHER MACHINE. `ops/run_recommendation_worker.sh`
     (VPS, */20) hands the open rows to `claude -p`. It needs brain auth, 900MB free, and the VPS
     -- which has published no commit since 2026-09-08. A queue whose only consumer lives on a
     machine that has stopped is a queue with no consumer at all, and nothing said so.

WHAT THIS ORGAN IS. A deterministic triage engine. It does not write speculative code and it does
not ask a model what to do. Every pass it takes the OPEN rows in priority order and drives each to
a recorded outcome:

    implemented  the row's deliverable is a FILE, it did not exist when the row was raised, and
                 git says it was added more than a grace window later -- cited by that add-commit
    scheduled    the row waits on an artifact a clocked organ regenerates; the row records WHICH
                 clock and when it next fires
    rejected     a substantive reason: duplicate of a NAMED terminal row, refused by the
                 standing order against reducing aggressiveness, or retired crypto ground
    blocked      an exactly named blocker with an owner and a next action

BLOCKED IS NOT A STATUS, AND THAT IS DELIBERATE. `scheduled` already carries the desk's scar --
"the place recommendations go to die" -- and a fifth status would be a better hiding place, because
no existing fence knows the word. `check_row_atomicity`, `libs/ops/ledger_reversion`, `owed()` and
`check_conversion` all count `open`. So a blocked row STAYS OPEN and visible to every one of them,
and gains three fields instead: `owner`, `next_action`, `blocker`. The defect this organ exists to
remove is not the word "open" -- it is an open row that names nobody and no next step.

WHERE A ROW ASKS FOR CODE, IT GETS A BUILD TASK, NEVER A GUESS. A deterministic BT-id per row,
published in the artifact and referenced from the row's `next_action`. Writing code to satisfy a
one-line prose recommendation is how a research loop spends its budget implementing its own
audit's bad ideas (`scripts/act_on_findings.py` says the same thing about the same ledger).

THE LOOP CLOSES BOTH WAYS. Intake pulls the CEO docket's undecided proposals and the frontier
audit's findings into THIS ledger rather than a second store, skipping anything a terminal row
already settled; and `already_settled()` is read by `frontier_ceo.py` so the docket cannot
re-propose what the desk has already implemented or reasoned its way out of.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import sys
import time
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

BASE = Path(__file__).resolve().parent.parent          # desks/mt5
ROOT = BASE.parent.parent                              # repo root
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(ROOT / "scripts"))

OUT = BASE / "reports" / "IMPLEMENTER.json"
DOC = ROOT / "docs" / "research" / "IMPLEMENTATION.md"
RATCHET = BASE / "data" / "recommendation_ratchet.json"
DOCKET = BASE / "reports" / "CEO_DOCKET.json"

#: The ledger's own cadence. This leg is hourly, and L1.48 wants every wall-clock constant to name
#: its exemption: this is the DUTY horizon, not an evidence clock -- how long the desk's owed-work
#: queue may go unwritten before that silence is itself the defect. Two cycles of headroom, so one
#: skipped hour is not an alarm and a dead organ is.
CADENCE_H = 3.0

#: Per-pass intake ceiling. Not a cap on what may be ledgered -- the remainder is counted and
#: named in the artifact and arrives on the next pass an hour later -- but a bound on how much one
#: pass rewrites a 1.3 MB tracked file.
INTAKE_PER_PASS = 60

#: Frontier-audit artifacts whose findings belong in THIS ledger (brief: "rather than a second
#: store"). An absent one is UNMEASURED and is NAMED in the artifact -- never silently skipped,
#: because a source that stopped producing and a source with nothing to say read identically.
FRONTIER_SOURCES: tuple[tuple[str, str], ...] = (
    ("desks/mt5/reports/UNKNOWN_UNKNOWNS.json", "findings"),
    ("desks/mt5/reports/NEGATIVE_KNOWLEDGE.json", "findings"),
    ("desks/mt5/reports/FRONTIER_MAP.json", "gaps"),
    ("desks/mt5/reports/PIT_AUDIT.json", "violations"),
    ("desks/mt5/reports/BOOK_FORENSICS.json", "findings"),
    ("desks/mt5/reports/QUANTBENCH.json", "defects"),
    ("desks/mt5/reports/FORMAL_INVARIANTS.json", "violations"),
    ("desks/mt5/reports/CERTIFICATE_HYGIENE.json", "unrunnable"),
    ("data/findings_docket.json", "docket"),
)

#: NEVER IMPLEMENTED, HOWEVER WELL ARGUED (principal, standing, given three times). Phrases, not
#: single words, because "cap" appears in "capacity" and "capital" and a word list would refuse
#: the growth items it exists to protect. A reduction is ADMITTED when what it shrinks is
#: correlation, lookahead, trial count, slippage or latency -- those buy growth.
_TIMID = (
    "reduce aggressiveness", "reduce the aggressiveness", "less aggressive",
    "lower the heat", "reduce the heat", "lower the heat floor", "cut the heat",
    "reduce risk per trade", "lower risk per trade", "reduce position size",
    "shrink the book", "cap the book", "de-risk", "derisk",
    "lower leverage", "reduce leverage", "cap the allocator", "shrink the allocator",
    "conditional on ruin", "drop the 0.02", "add a veto", "add a cap on",
)
_ADMITTED_SHRINK = ("correlation", "lookahead", "trial count", "trials", "slippage", "latency",
                    "drawdown of the estimator", "variance of the estimate")

#: The hunted-universe mandate (2026-08-18): crypto-EXCHANGE ground is never hunted again. Fusion
#: crypto CFDs are part of the MT5 universe, so a row naming one of these AND a CFD/Fusion context
#: is NOT refused -- the mandate is about the venue, not the asset.
_CRYPTO_VENUES = ("binance", "bybit", "okx", "hyperliquid", "deribit", "bitmex", "kucoin",
                  "coinbase", "kraken exchange", "perpetual funding")
_CRYPTO_OK = ("cfd", "fusion", "mt5", "reference data")

#: Files no session touches autonomously. A row that asks for one is BLOCKED on the principal --
#: never rejected (the ask may be right) and never scheduled (nobody here owns the date).
_SEALED = ("external_gauntlet.py", "promoter.py", "allocator_proof.py", "state_admission.py",
           "run_deadman_switch.py")

#: Subject -> the owner that carries it, for rows that cite no file at all. Ordered: first match
#: wins, so the more specific phrases come first.
_OWNERS: tuple[tuple[str, str], ...] = (
    ("gauntlet", "MT5-Gauntlet"),
    ("certificate", "MT5-Gauntlet"),
    ("forward clock", "hourly_cycle:shadow_forward"),
    ("shadow", "hourly_cycle:shadow_forward"),
    ("promot", "MT5-Hourly:promoter"),
    ("sleeve", "MT5-Hourly:promoter"),
    ("gateway", "MT5-Gateway"),
    ("execution", "MT5-Gateway"),
    ("allocator", "MT5-AllocatorFast"),
    ("heat", "MT5-AllocatorFast"),
    ("universe", "MT5-Hourly:refresh_bars"),
    ("bars", "MT5-Hourly:refresh_bars"),
    ("tape", "MT5-MoatRecorder"),
    ("miner", "hourly_cycle:mine"),
    ("hypothes", "hourly_cycle:queue_cycle"),
    ("docket", "MT5-CEODocket"),
    ("dashboard", "MT5-DashMirror"),
    ("fence", "hourly_cycle:fence_battery"),
    ("law", "hourly_cycle:fence_battery"),
)

_PATH_RE = re.compile(
    r"(?<![\w/])((?:[\w.-]+/)+[\w.-]+\.(?:py|ps1|sh|cmd|md|json|jsonl|manifest|sqlite|parquet))")
_WORD_RE = re.compile(r"[a-z0-9_]{4,}")
_STOP = frozenset((
    "that", "this", "with", "from", "into", "they", "them", "then", "than", "which", "what",
    "when", "where", "have", "been", "were", "will", "would", "could", "should", "must",
    "desk", "the", "and", "for", "not", "but", "its", "it's", "each", "every", "more", "less",
    "none", "only", "also", "over", "under", "rather", "never", "always", "still", "very"))


# --------------------------------------------------------------------------- small helpers
def _load_json(p: Path, default: Any = None) -> Any:
    try:
        return json.loads(p.read_text("utf-8"))
    except (OSError, ValueError):
        return default


def _age_h(iso: Any) -> float:
    """Hours since an ISO stamp, or 0.0 when it cannot be read.

    UNPARSEABLE READS AS 0.0 DELIBERATELY HERE and nowhere that would hide a row: this is only
    ever used for ORDERING (oldest first) and for the staleness verdict, where an unreadable stamp
    must not promote a row above rows whose age is known.
    """
    try:
        return (datetime.now(tz=UTC) - datetime.fromisoformat(str(iso))).total_seconds() / 3600.0
    except (TypeError, ValueError):
        return 0.0


def _tokens(text: str) -> frozenset[str]:
    return frozenset(w for w in _WORD_RE.findall(str(text).lower()) if w not in _STOP)


def _overlap(a: frozenset[str], b: frozenset[str]) -> float:
    """Jaccard-style containment: how much of the SHORTER row the longer one already says."""
    if not a or not b:
        return 0.0
    return len(a & b) / float(min(len(a), len(b)))


def _bt_id(rid: str, summary: str) -> str:
    return "BT-" + hashlib.blake2b(f"{rid}|{summary}".encode(), digest_size=5).hexdigest()


# --------------------------------------------------------------------------- the clock index
def _clock_index(root: Path | None = None) -> dict[str, str]:
    """script path (repo-relative, forward slashes) -> the clock that runs it.

    MEASURED FROM THE REPO, NEVER ASSERTED. Three sources, in the vocabulary each one uses:
    `_producer("<leg>", "<script>")` calls in the two cycles, and `TASK runs="..."` lines in the
    box manifest. A path absent from all three has NO clock, and that is the finding -- III.16's
    "unwired or idle is a defect" measured rather than believed.
    """
    r = root or ROOT
    index: dict[str, str] = {}
    for cycle in ("hourly_cycle", "daily_cycle"):
        src = r / "desks" / "mt5" / "research" / f"{cycle}.py"
        text = _read_text(src)
        for leg, script in re.findall(
                r'_producer\(\s*"([^"]+)"\s*,\s*"([^"]+)"', text):
            index.setdefault(f"desks/mt5/{script}", f"{cycle}:{leg}")
    manifest = r / "desks" / "mt5" / "ops" / "box_tasks.manifest"
    runner_task: dict[str, str] = {}
    for name, runs in re.findall(r'TASK name="([^"]+)"[^\n]*runs="([^"]+)"', _read_text(manifest)):
        rel = runs.replace("\\", "/")
        index.setdefault(rel, f"task:{name}")
        runner_task[rel] = f"task:{name}"
    # THE RUNNERS THEMSELVES RUN ORGANS, and reading only the two cycles said otherwise. One file
    # -- ops/run_frontier_audit.cmd -- invokes THIRTY organs that the `_producer` scan cannot see,
    # and every one of them would have been graded "exists and no clock runs it": fifty-two such
    # rows before this loop existed. A clock census that reads one scheduler's vocabulary and
    # calls the rest unwired reports its own blind spot as the desk's defect.
    # `run_*` ONLY. `ops/brain_env.sh` is SOURCED by the runners, not scheduled by anything, and
    # indexing it made every organ it mentions look clocked -- a clock census that counts a
    # library as a scheduler is worse than one that misses a scheduler, because it converts a real
    # III.16 defect into a green tick.
    for runner in sorted((r / "ops").glob("run_*.cmd")) + sorted((r / "ops").glob("run_*.sh")):
        rel = runner.relative_to(r).as_posix()
        label = runner_task.get(rel, f"runner:{runner.name}")
        text = _read_text(runner)
        for hit in re.findall(r'([\w./\\-]+\.py)', text):
            index.setdefault(hit.replace("\\", "/").lstrip("./"), label)
        for mod in re.findall(r'-m\s+([\w.]+)', text):
            index.setdefault(mod.replace(".", "/") + ".py", label)
    for line in _read_text(r / "ops" / "crontab.manifest").splitlines():
        if line.lstrip().startswith("#") or ".py" not in line:
            continue
        for hit in re.findall(r'([\w./-]+\.py)', line):
            index.setdefault(hit.lstrip("./"), "timer:crontab.manifest")
    # NORMALISE TO PATHS THAT EXIST. A runner may spell an organ from the desk root and a cycle
    # from the repo root; `_resolve_cited` hands back the real repo-relative path, so the index is
    # keyed the same way and a lookup cannot miss on spelling alone.
    out: dict[str, str] = {}
    for key, label in index.items():
        if (r / key).is_file():
            out[key] = label
        elif (r / "desks" / "mt5" / key).is_file():
            out[f"desks/mt5/{key}"] = label
    return out


def _read_text(p: Path) -> str:
    try:
        return p.read_text("utf-8", errors="ignore")
    except OSError:
        return ""


_SKIP_DIRS = frozenset((".git", "node_modules", ".venv", "__pycache__", "data", "logs",
                        "reports", "worktrees"))


def _basename_index(root: Path) -> dict[str, list[str]]:
    """basename -> every repo-relative code path with that name. Built once per pass.

    A ROW THAT CITES `research/moat_miner.py` IS NOT CITING A MISSING FILE. The desk writes paths
    in whichever root the writer was standing in -- `research/x.py` from desks/mt5, `desks/mt5/
    research/x.py` from the repo root -- and a literal `(root / p).exists()` calls the first one
    absent. Measured before this index: 60 open rows classified `needs_code` (build something
    that is not here) where the file was simply named from the other root. Grading a file that
    EXISTS as missing manufactures build tasks, which is the expensive direction to be wrong in.
    """
    index: dict[str, list[str]] = {}
    for p in root.rglob("*.py"):
        parts = set(p.relative_to(root).parts[:-1])
        if parts & _SKIP_DIRS:
            continue
        index.setdefault(p.name, []).append(p.relative_to(root).as_posix())
    return index


def _resolve_cited(root: Path, cited: str, index: dict[str, list[str]]) -> str | None:
    """The repo-relative path a citation means, or None when nothing in the tree answers to it.

    Three attempts, most literal first; a basename that matches SEVERAL files resolves to none of
    them, because guessing which one a row meant is how a fence starts inventing its own evidence.
    """
    if (root / cited).exists():
        return cited
    alt = f"desks/mt5/{cited}"
    if (root / alt).exists():
        return alt
    hits = index.get(Path(cited).name, [])
    return hits[0] if len(hits) == 1 else None


_JSON_RE = re.compile(r'"([A-Za-z0-9_./-]+\.json)"')


def _organ_artifacts(root: Path, rel: str) -> list[str]:
    """The report files an organ's own source says it writes, that exist on disk.

    THE PROOF AN IMPLEMENTATION NEEDS IS THE ARTIFACT, and most ledger rows name the organ rather
    than the file it publishes. Reading the organ's source for its own `.json` literals is how the
    proof is FOUND rather than assumed -- and a name that resolves to nothing on disk simply does
    not prove anything, which is the correct outcome, not an error.
    """
    out: list[str] = []
    for name in list(dict.fromkeys(_JSON_RE.findall(_read_text(root / rel))))[:16]:
        for cand in (f"desks/mt5/reports/{Path(name).name}", name, f"desks/mt5/{name}"):
            if (root / cand).is_file():
                out.append(cand)
                break
    return out


def _next_firing(clock: str) -> str:
    """When the named clock next fires, as a date. Hourly clocks land today; daily, tomorrow."""
    now = datetime.now(tz=UTC)
    if clock.startswith("hourly_cycle") or "Hourly" in clock or "Gauntlet" in clock:
        return (now + timedelta(hours=1)).date().isoformat()
    return (now + timedelta(days=1)).date().isoformat()


def _freshest_after(root: Path, paths: list[str], since_iso: str) -> str | None:
    """The first of `paths` whose mtime is after `since_iso`, or None -- artifact as proof."""
    for p in paths:
        try:
            mt = datetime.fromtimestamp((root / p).stat().st_mtime, tz=UTC)
        except OSError:
            continue
        if since_iso and mt.isoformat() > since_iso:
            return p
    return None


def _added_commit(root: Path, rel: str) -> tuple[str, str] | None:
    """(sha, committer-date) of the commit that ADDED `rel`, or None when git cannot answer.

    `--diff-filter=A` is the whole point: "last touched" is satisfied by a typo fix, while "added"
    is a claim about the file's existence that no later edit can manufacture. When git is
    unavailable the answer is None and the row is NOT disposed -- an unprovable implementation is
    not an implementation (R0478).
    """
    try:
        p = subprocess.run(
            ["git", "log", "--diff-filter=A", "--format=%H|%cI", "-1", "--", rel],
            capture_output=True, text=True, timeout=30, cwd=root)
    except (OSError, subprocess.SubprocessError):
        return None
    line = p.stdout.strip().splitlines()[0] if p.stdout.strip() else ""
    if p.returncode != 0 or "|" not in line:
        return None
    sha, _, when = line.partition("|")
    return (sha, when) if re.fullmatch(r"[0-9a-f]{40}", sha) else None


#: Git calls one pass may spend proving implementations. `git log --diff-filter=A` over a repo
#: this size costs ~0.4s on the box, and 219 open rows citing two paths each is 440 of them --
#: measured at over two minutes, which is a pass that spends its whole budget on the rung that
#: fires least. Cached per path (rows cite the same files repeatedly) and capped; a row whose
#: proof was not reached falls to a blocker and is re-offered next hour, which loses nothing.
GIT_CALLS_PER_PASS = 150

#: A file born INSIDE the ask's own grace window is the ask's EVIDENCE, not its fulfilment, and
#: this constant is the scar from the dry pass that proved it. Twenty rows disposed `implemented`
#: on "the cited file was added after the row was raised" -- and R0742, R0733 and six siblings
#: cite `data/brain_hunter_s*.json`, the measurement the hunter wrote WHILE raising the row, minutes
#: later. Same clause, same commit, and a proof that the desk had done the work. One grace window
#: (`recommendations.GRACE_H`) of separation is the cheapest rule that tells the two apart.
IMPL_MIN_LAG_H = 24.0


def _lag_h(raised: str, born: str) -> float:
    """Hours from the ask to the file's birth, or -inf when either stamp cannot be read.

    PARSED, NEVER STRING-COMPARED. `raised` carries +00:00 and `git --format=%cI` carries the
    committer's local offset, so `"2026-09-01T23:00+02:00" > "2026-09-01T22:00+00:00"` is True as
    TEXT and False as TIME. A lexical comparison of two ISO stamps with different offsets is the
    kind of bug that mints a false `implemented` twice a day and never on the day you look.
    """
    try:
        a = datetime.fromisoformat(raised)
        b = datetime.fromisoformat(born)
    except (TypeError, ValueError):
        return float("-inf")
    if a.tzinfo is None:
        a = a.replace(tzinfo=UTC)
    if b.tzinfo is None:
        b = b.replace(tzinfo=UTC)
    return (b - a).total_seconds() / 3600.0


def _born_cached(root: Path, rel: str, ctx: dict[str, Any]) -> tuple[str, str] | None:
    cache: dict[str, tuple[str, str] | None] = ctx.setdefault("born", {})
    if rel in cache:
        return cache[rel]
    if int(ctx.get("git_calls", 0)) >= GIT_CALLS_PER_PASS:
        ctx["git_budget_hit"] = True
        return None
    ctx["git_calls"] = int(ctx.get("git_calls", 0)) + 1
    cache[rel] = _added_commit(root, rel)
    return cache[rel]


def artifact_clock_index(root: Path, clocks: dict[str, str]) -> dict[str, str]:
    """artifact path -> the clock of the organ whose source declares it. Built once per pass.

    Read from each CLOCKED organ's own `.json` literals, so an artifact's clock is what the code
    says rather than what a naming convention suggests. Organs are not re-read per row: 500-odd
    small reads once a pass is cheap; once per open row is not.
    """
    out: dict[str, str] = {}
    for organ, clock in clocks.items():
        if not organ.endswith(".py"):
            continue
        for art in _organ_artifacts(root, organ):
            out.setdefault(art, clock)
    return out


def _last_commit(root: Path, rel: str) -> str | None:
    """The full sha of the commit that last touched `rel`, or None when git cannot answer.

    THE CITATION IS A PROOF OR IT IS NOTHING (R0478). An implemented row needs a hex sha that
    resolves in this clone; `git log -1` over the proving file gives exactly that, and when git is
    unavailable the row is NOT disposed implemented -- it falls through to the next rung. A
    disposition that cannot cite is not a disposition.
    """
    try:
        p = subprocess.run(["git", "log", "-1", "--format=%H", "--", rel],
                           capture_output=True, text=True, timeout=30, cwd=root)
    except (OSError, subprocess.SubprocessError):
        return None
    sha = p.stdout.strip()
    return sha if p.returncode == 0 and re.fullmatch(r"[0-9a-f]{40}", sha) else None


# --------------------------------------------------------------------------- the ledger view
def _ledger_path(root: Path) -> Path:
    return root / "docs" / "research" / "recommendation_ledger.json"


def load_ledger(root: Path | None = None) -> dict[str, Any]:
    r = root or ROOT
    d = _load_json(_ledger_path(r))
    if not isinstance(d, dict) or not isinstance(d.get("recommendations"), list):
        # A corrupt ledger must never read as empty-healthy: that is the mass deletion the ledger
        # law forbids, arriving through a consumer instead of a writer.
        raise SystemExit(f"REFUSING: {_ledger_path(r)} is missing or unreadable -- repair it from "
                         "git history; an unreadable ledger must never become an empty one")
    return d


def save_ledger(d: dict[str, Any], root: Path | None = None) -> None:
    """Write the ledger in the ONE canonical form (indent=1, ensure_ascii=False, no newline).

    tests/governance/test_ledger_format_canonical.py pins those bytes, and R0368 explains the
    ensure_ascii half: escaped CJK is ungreppable, so a term already mined returns a clean zero
    and reads as unexplored ground.
    """
    p = _ledger_path(root or ROOT)
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(d, indent=1, ensure_ascii=False), "utf-8")
    tmp.replace(p)


@contextmanager
def ledger_lock(root: Path, timeout_s: float = 10.0) -> Iterator[None]:
    """The SAME advisory lock `scripts/recommendations.py` takes, on the same file (R0623).

    A SECOND WRITER WITHOUT THE FIRST WRITER'S LOCK IS THE RACE, NOT A SMALLER VERSION OF IT. That
    lock exists because two sessions' interleaved add/dispose calls destroyed three rows and
    reverted two dispositions five separate times in one day: both processes read, both write,
    last writer wins. This organ rewrites the whole file every hour, so an unlocked pass would
    reopen exactly that with a machine holding one end of it. It contends on `data/.recommendation
    _ledger.lock` under the ROOT IT IS WRITING, so a pass against a tmp tree does not touch the
    repo's lock and a pass against the repo contends with the CLI as intended.

    A LOCK IT CANNOT TAKE REFUSES THE PASS. Ten seconds of contention on a millisecond write means
    a wedged holder; writing anyway is the corruption this guards, and skipping silently would
    leave the ledger unwritten while the leg reported success.
    """
    from recommendations import _flock_exclusive  # type: ignore[import-not-found]
    p = root / "data" / ".recommendation_ledger.lock"
    p.parent.mkdir(parents=True, exist_ok=True)
    fh = p.open("w")
    deadline = time.monotonic() + timeout_s
    try:
        while True:
            try:
                _flock_exclusive(fh)
                break
            except OSError:
                if time.monotonic() > deadline:
                    raise SystemExit(
                        f"REFUSING: could not lock {p} within {timeout_s:g}s -- another ledger "
                        "writer is wedged. Writing around the lock is the row loss R0623 "
                        "records; the next pass is an hour away and loses nothing.") from None
                time.sleep(0.2)
        yield
    finally:
        fh.close()


def priority(row: dict[str, Any]) -> tuple[float, float, float]:
    """Sort key, ascending. MEASURED ROI OUTRANKS AN OPINION, and age breaks every tie.

    A `roi_bps` is an estimate somebody computed; a `rank` is an ordinal somebody chose (R0477 is
    the scar: four-digit "bps" were ranks wearing a bps label). So measured rows go first, ranked
    rows next, unquantified rows last, and inside each tier the oldest row wins -- which is the
    only tie-break that cannot be gamed by whoever writes the next row.
    """
    roi, rank = row.get("roi_bps"), row.get("rank")
    try:
        if roi is not None:
            return (0.0, -float(roi), -_age_h(row.get("raised")))
        if rank is not None:
            return (1.0, float(rank), -_age_h(row.get("raised")))
    except (TypeError, ValueError):
        pass
    return (2.0, 0.0, -_age_h(row.get("raised")))


def already_settled(text: str, rows: list[dict[str, Any]] | None = None,
                    threshold: float = 0.72) -> str | None:
    """The id of a TERMINAL row that already says this, or None. The CEO docket's re-proposal gate.

    Containment, not equality: the docket phrases a proposal as an experiment and the ledger row
    phrases it as a deliverable, so identical strings never occur and an equality test would pass
    every duplicate through. `min(len)` in the denominator means a short proposal fully contained
    in a long implemented row scores 1.0, which is the case that matters.
    """
    rows = rows if rows is not None else load_ledger()["recommendations"]
    t = _tokens(text)
    if len(t) < 4:
        return None                # too short to match on; never guess a duplicate into existence
    best, best_id = threshold, None
    for r in rows:
        if r.get("status") not in ("implemented", "rejected", "done"):
            continue
        s = _overlap(t, _tokens(r.get("summary", "")))
        if s > best:
            best, best_id = s, str(r.get("id"))
    return best_id


# --------------------------------------------------------------------------- the decision ladder
def _dispose(row: dict[str, Any], status: str, reason: str,
             commit: str | None = None, due: str | None = None) -> None:
    """Write a CLI-LEGAL disposition. The CLI's own bars, enforced here rather than trusted.

    `scripts/recommendations.py::dispose` refuses a rejection under 25 chars, a schedule with no
    due date, an implementation with no commit, and stamps `disposed` -- and every one of those
    bars exists because a direct JSON write once skipped it (tests/governance/
    test_tracked_json_integrity.py counted 35 terminal rows with no stamp). An organ that writes
    the file directly inherits the whole class unless it re-imposes them, so it does.
    """
    if status == "rejected" and len(reason.strip()) < 25:
        raise ValueError(f"{row.get('id')}: a rejection needs a real reason (>=25 chars)")
    if status == "scheduled" and not due:
        raise ValueError(f"{row.get('id')}: a scheduled row needs a due date")
    if status == "implemented" and not commit:
        raise ValueError(f"{row.get('id')}: an implemented row needs a resolvable commit")
    row.update(status=status, reason=reason, commit=commit, due=due,
               disposed=datetime.now(tz=UTC).isoformat())
    row.pop("claimed_at", None)
    row.pop("claimed_by", None)


def _block(row: dict[str, Any], blocker: str, owner: str, next_action: str,
           cls: str) -> None:
    """Record a NAMED blocker on a row that stays OPEN and stays visible to every fence."""
    row["owner"] = owner
    row["next_action"] = next_action
    row["blocker"] = blocker
    row["blocker_class"] = cls
    row["triaged_at"] = datetime.now(tz=UTC).isoformat()


def _owner_for(text: str) -> str:
    low = text.lower()
    for key, owner in _OWNERS:
        if key in low:
            return owner
    return "hourly_cycle:implementer"


def _timid(text: str) -> bool:
    low = text.lower()
    if not any(p in low for p in _TIMID):
        return False
    return not any(k in low for k in _ADMITTED_SHRINK)


def _crypto_venue(text: str) -> str | None:
    low = text.lower()
    if any(k in low for k in _CRYPTO_OK):
        return None
    return next((v for v in _CRYPTO_VENUES if v in low), None)


def triage(row: dict[str, Any], ctx: dict[str, Any]) -> dict[str, Any]:
    """Decide ONE open row. Returns the outcome record; mutates the row in place.

    THE LADDER IS ORDERED BY WHAT IT COSTS TO BE WRONG. Refusals that are laws come first (a timid
    row must never be implemented by accident); duplicates next (cheapest true rejection); a proof
    of implementation only after that, and it is the conservative rung -- it demands an EXISTING
    file, a clock this repo can name, a fresh artifact AND a resolvable commit, because a false
    `implemented` removes the thing from view permanently, which is strictly worse than leaving
    it open (`ops/run_recommendation_worker.sh` says the same in its own prompt).
    """
    rid = str(row.get("id"))
    summary = str(row.get("summary") or "")
    root: Path = ctx["root"]
    clocks: dict[str, str] = ctx["clocks"]

    # 1. THE STANDING ORDER, BEFORE ANYTHING ELSE.
    if _timid(summary):
        _dispose(row, "rejected",
                 "REFUSED by the principal's standing order (2026-09-08, given three times): no "
                 "session lowers the desk's aggressiveness by fiat. The 20% heat floor, the "
                 "0.02-lot gold floor and the allocator's fractions stay as they are; a cap, "
                 "shrink or veto is admitted only with a proof that robust forward E[log W] "
                 "RISES (Growth Governance Rule 1), which this row does not carry.")
        return {"id": rid, "state": "rejected", "why": "standing order: aggressiveness"}

    venue = _crypto_venue(summary)
    if venue:
        _dispose(row, "rejected",
                 f"Out of universe: names {venue}, and the MT5 universe mandate (2026-08-18) is "
                 "that no crypto-EXCHANGE ground is ever hunted again -- no miner, query or "
                 "research mandate may target it. Fusion-executable crypto CFDs remain in scope "
                 "and this row does not name one.")
        return {"id": rid, "state": "rejected", "why": f"out of universe: {venue}"}

    # 2. A DUPLICATE OF A NAMED TERMINAL ROW. Named, because "duplicate" with no id is a claim.
    twin = already_settled(summary, ctx["rows"])
    if twin and twin != rid:
        _dispose(row, "rejected",
                 f"Duplicate of {twin}, which is already terminal and says the same thing; this "
                 "ledger's rule is one row per recommendation, and two rows for one ask split its "
                 "evidence and its owner across both.")
        return {"id": rid, "state": "rejected", "why": f"duplicate of {twin}"}

    # 3. PROVEN IMPLEMENTED -- and the bar is DELIBERATELY ALMOST UNREACHABLE.
    #
    # THE FIRST VERSION OF THIS RUNG WAS WRONG AND THE MEASUREMENT IS WHY IT IS NOW THIS SHAPE.
    # It accepted "the row cites an organ that has a clock, and some artifact that organ writes is
    # fresher than the row" and disposed 10 rows implemented on the first dry pass. Reading them:
    # R0748 asks for a fix to the test suite's restore guard and was proved by max_audit_report
    # .json being fresh, which says only that max_audit RAN. R0513 asks for archaeology on three
    # unresolvable citations and was proved by the ledger's own mtime. Both are false, and a false
    # `implemented` is strictly worse than an untouched row -- it removes the thing from view
    # permanently, which is the one outcome this whole ledger exists to prevent.
    #
    # WHAT SURVIVES IS THE ONE CLAIM PROSE CANNOT FAKE: the row names a file, that file did not
    # exist when the row was raised, and git says it was ADDED afterwards. The deliverable IS the
    # artifact, the add-commit is the citation, and no amount of an organ merely running satisfies
    # it. Everything else falls through to a blocker with an owner, which is honest.
    index: dict[str, list[str]] = ctx["basenames"]
    cited = list(dict.fromkeys(_PATH_RE.findall(summary)))
    resolved = {p: _resolve_cited(root, p, index) for p in cited}
    existing = [v for v in resolved.values() if v]
    sealed = next((s for s in _SEALED if s in summary), None)
    organs = [p for p in existing if p.endswith(".py") and p in clocks]
    raised = str(row.get("raised") or "")
    if existing and raised and not sealed:
        for p in existing:
            born = _born_cached(root, p, ctx)
            if born and _lag_h(raised, born[1]) > IMPL_MIN_LAG_H:
                _dispose(row, "implemented",
                         f"{p} did not exist when this row was raised ({raised[:10]}) and was "
                         f"ADDED in {born[0][:12]} on {born[1][:10]}, "
                         f"{_lag_h(raised, born[1]) / 24.0:.1f} days later; the deliverable is "
                         "the file itself, so the add-commit is the proof rather than a claim.",
                         commit=born[0])
                return {"id": rid, "state": "implemented", "why": f"{p} added after the ask",
                        "commit": born[0], "artifact": p}

    # 4. SEALED / PRINCIPAL-GATED -- blocked, never rejected and never scheduled.
    if sealed:
        bt = _bt_id(rid, summary)
        _block(row, f"{sealed} is sealed: no session edits it autonomously (LAWS: Tier-3 "
                    "never-touch and the four sealed judges)",
               "principal", f"{bt} -- write the change as a SPEC for the principal to approve; "
                            "do not edit the sealed file",
               "needs_principal")
        return {"id": rid, "state": "blocked", "why": f"sealed: {sealed}",
                "owner": "principal", "blocker_class": "needs_principal",
                "build_task": {"id": bt, "rec": rid, "target": sealed, "title": summary[:160],
                               "owner": "principal"}}

    # 5. THE ROW IS WAITING ON AN ARTIFACT A CLOCKED ORGAN REGENERATES -- schedule it, by clock.
    #
    # NARROW ON PURPOSE. Scheduling a row because SOMETHING it mentions has a clock is how
    # `scheduled` became "the place recommendations go to die" (scripts/recommendations.py says so
    # in its own docstring). This fires only when the row's deliverable IS an artifact that some
    # organ on a known clock writes, and that artifact is older than the ask: the work is
    # genuinely waiting for the next firing, and the due date is that firing.
    art_clock: dict[str, str] = ctx["artifact_clocks"]
    waiting = next((p for p in existing
                    if p in art_clock and not _freshest_after(root, [p], raised)), None)
    if waiting:
        clock = art_clock[waiting]
        due = _next_firing(clock)
        _dispose(row, "scheduled",
                 f"{waiting} is written by an organ on {clock} and has not been rewritten since "
                 f"this row was raised; the row is waiting on that clock, and its due date is "
                 f"that clock's next firing.", due=due)
        row["clock"] = clock
        return {"id": rid, "state": "scheduled", "why": f"{waiting} @ {clock}", "due": due}

    # 6. THE ORGAN EXISTS AND RUNS -- so the ask is a CHANGE to it, which no artifact can prove.
    if organs:
        bt = _bt_id(rid, summary)
        clock = clocks[organs[0]]
        _block(row, f"{organs[0]} already exists and runs on {clock}; this row asks for a CHANGE "
                    "to it, and an organ merely running proves nothing about the change",
               clock, f"{bt} -- make the change in {organs[0]} and dispose this row citing the "
                      "commit", "needs_change")
        return {"id": rid, "state": "blocked", "why": f"needs a change in {organs[0]}",
                "owner": clock, "blocker_class": "needs_change",
                "build_task": {"id": bt, "rec": rid, "target": organs[0],
                               "title": summary[:160], "owner": clock}}

    # 7. IT NAMES A FILE THAT IS NOT HERE -- a build task, never speculative code.
    absent = [p for p, v in resolved.items() if v is None]
    if absent:
        bt = _bt_id(rid, summary)
        _block(row, f"{absent[0]} does not exist in this tree",
               _owner_for(summary), f"{bt} -- build {absent[0]} and wire it to a clock",
               "needs_code")
        return {"id": rid, "state": "blocked", "why": f"absent: {absent[0]}",
                "owner": _owner_for(summary), "blocker_class": "needs_code",
                "build_task": {"id": bt, "rec": rid, "target": absent[0],
                               "title": summary[:160], "owner": _owner_for(summary)}}

    # 8. IT NAMES A FILE THAT EXISTS AND NOTHING RUNS IT (III.16, measured).
    unclocked = [p for p in existing if p.endswith(".py") and p not in clocks]
    if unclocked:
        bt = _bt_id(rid, summary)
        _block(row, f"{unclocked[0]} exists and no clock in this repo runs it (III.16: unwired "
                    "or idle is a defect)",
               _owner_for(summary), f"{bt} -- wire {unclocked[0]} as a leg or a box task",
               "needs_clock")
        return {"id": rid, "state": "blocked", "why": f"unclocked: {unclocked[0]}",
                "owner": _owner_for(summary), "blocker_class": "needs_clock",
                "build_task": {"id": bt, "rec": rid, "target": unclocked[0],
                               "title": summary[:160], "owner": _owner_for(summary)}}

    # 9. PROSE WITH NO CITED FILE. An exact blocker all the same: the ask has no target yet.
    bt = _bt_id(rid, summary)
    owner = _owner_for(summary)
    _block(row, "the row cites no file in this repo, so there is nothing to prove, schedule or "
                "build against -- it needs a target before it can be worked",
           owner, f"{bt} -- {owner} turns this into a cited spec (file + clock + artifact)",
           "needs_specification")
    return {"id": rid, "state": "blocked", "why": "no cited target", "owner": owner,
            "blocker_class": "needs_specification",
            "build_task": {"id": bt, "rec": rid, "target": None, "title": summary[:160],
                           "owner": owner}}


# --------------------------------------------------------------------------- intake
def _docket_rows(root: Path) -> list[dict[str, Any]]:
    doc = _load_json(root / "desks" / "mt5" / "reports" / "CEO_DOCKET.json", {}) or {}
    out: list[dict[str, Any]] = []
    for p in (doc.get("proposals") or []):
        if not isinstance(p, dict):
            continue
        adds = str(p.get("adds") or p.get("id") or "").strip()
        if not adds:
            continue
        exp = str(p.get("experiment") or "").strip()
        ref = str(p.get("refuted_if") or "").strip()
        out.append({"source": "ceo_docket",
                    "summary": f"{adds}. Experiment: {exp} Refuted if: {ref}".strip()[:600],
                    "rank": p.get("rank")})
    return out


def _frontier_rows(root: Path) -> tuple[list[dict[str, Any]], list[str]]:
    """(rows, unmeasured) -- the frontier audit's findings, and the sources that had nothing."""
    rows: list[dict[str, Any]] = []
    unmeasured: list[str] = []
    for rel, key in FRONTIER_SOURCES:
        blob = _load_json(root / rel)
        if blob is None:
            unmeasured.append(f"{rel}: ABSENT")
            continue
        items = blob.get(key) if isinstance(blob, dict) else None
        if not isinstance(items, list) or not items:
            unmeasured.append(f"{rel}: present, no `{key}` rows")
            continue
        for it in items[:20]:
            if isinstance(it, dict):
                text = " ".join(str(it.get(k)) for k in
                                ("subject", "title", "what", "finding", "why", "detail", "do",
                                 "gap", "name", "id")
                                if it.get(k))
            else:
                text = str(it)
            text = " ".join(text.split())[:600]
            if len(text) > 20:
                rows.append({"source": "frontier_audit", "summary": f"{text} [{rel}]"})
    return rows, unmeasured


def _next_id(rows: list[dict[str, Any]]) -> int:
    nums = [int(m.group(1)) for r in rows if (m := re.match(r"R(\d+)$", str(r.get("id", ""))))]
    return (max(nums) if nums else 0) + 1


def intake(d: dict[str, Any], root: Path, limit: int = INTAKE_PER_PASS) -> dict[str, Any]:
    """Pull the CEO docket and the frontier audit into THIS ledger. Never re-propose the settled.

    TWO GUARDS, AND THEY ANSWER DIFFERENT QUESTIONS. The exact (source, summary) dedupe is the
    CLI's own -- an organ re-reading the same report every hour must not grow a row per read. The
    `already_settled` containment check is the loop closing: a proposal the desk has already
    implemented or reasoned its way out of never comes back as new work, whatever words the docket
    chose for it this morning.
    """
    rows = d["recommendations"]
    seen = {(str(r.get("source")), str(r.get("summary")).strip()) for r in rows}
    open_tokens = [(_tokens(r.get("summary", "")), str(r.get("id")))
                   for r in rows if r.get("status") in ("open", "scheduled")]
    candidates = _docket_rows(root)
    fr, unmeasured = _frontier_rows(root)
    candidates += fr
    added: list[str] = []
    skipped_settled: list[dict[str, str]] = []
    skipped_dup = 0
    nxt = _next_id(rows)
    now = datetime.now(tz=UTC).isoformat()
    for c in candidates:
        if len(added) >= limit:
            break
        summary = c["summary"].strip()
        if (c["source"], summary) in seen:
            skipped_dup += 1
            continue
        twin = already_settled(summary, rows)
        if twin:
            skipped_settled.append({"id": twin, "summary": summary[:120]})
            continue
        t = _tokens(summary)
        if any(_overlap(t, ot) > 0.72 for ot, _ in open_tokens):
            skipped_dup += 1
            continue
        rid = f"R{nxt:04d}"
        nxt += 1
        row = {"id": rid, "source": c["source"], "summary": summary,
               "roi_bps": None, "rank": c.get("rank"),
               "roi_basis": "rank" if c.get("rank") is not None else None,
               "raised": now, "status": "open", "reason": None, "commit": None,
               "due": None, "disposed": None}
        rows.append(row)
        seen.add((c["source"], summary))
        open_tokens.append((t, rid))
        added.append(rid)
    return {"added": added, "n_added": len(added), "skipped_already_settled": skipped_settled,
            "skipped_duplicate": skipped_dup, "unmeasured_sources": unmeasured,
            "candidates_seen": len(candidates)}


# --------------------------------------------------------------------------- the ratchet
def read_ratchet(path: Path | None = None) -> dict[str, Any]:
    p = path or RATCHET
    d = _load_json(p)
    if not isinstance(d, dict):
        return {"floor": None, "at": None, "rises": []}
    d.setdefault("rises", [])
    return d


def update_ratchet(open_now: int, reason: str | None, path: Path | None = None) -> dict[str, Any]:
    """The OPEN backlog ratchets DOWN only; a rise must NAME what raised it.

    A LEVEL ALONE CANNOT TELL THE TWO CASES APART, and this desk has the measurement: the old
    level fence read RED for 226 of 226 informative hours, which is a gate carrying no
    information. So the floor is the best the desk has ever achieved and only moves down; a rise
    is legal exactly when this pass RECORDS its cause (intake from a named source), and that
    record is what the fence reads. An unexplained rise is the failure -- rows appearing with
    nobody noticing is how a queue stops being a queue.
    """
    p = path or RATCHET
    d = read_ratchet(p)
    now = datetime.now(tz=UTC).isoformat()
    floor = d.get("floor")
    if floor is None or open_now <= int(floor):
        d["floor"], d["at"] = open_now, now
    elif reason:
        d["rises"].append({"at": now, "from": int(floor), "to": open_now, "reason": reason})
        d["rises"] = d["rises"][-50:]
    d["open_now"], d["measured_at"] = open_now, now
    d["law"] = ("The OPEN backlog ratchets DOWN only. `floor` is the lowest open count ever "
                "measured; a pass may exceed it only by recording, here, what raised it.")
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(d, indent=1), "utf-8")
    return d


# --------------------------------------------------------------------------- the pass
def run(root: Path | None = None, budget_s: float = 600.0,
        do_intake: bool = True) -> dict[str, Any]:
    r = root or ROOT
    started = time.monotonic()
    # THE LOCK WRAPS THE WHOLE READ-MODIFY-WRITE, exactly as the CLI's does: acquiring it
    # after the read would serialize nothing, because the stale read IS the race (R0623).
    with ledger_lock(r):
        d = load_ledger(r)
        rows = d["recommendations"]
        open_before = sum(1 for x in rows if x.get("status") == "open")

        ink = intake(d, r, INTAKE_PER_PASS) if do_intake else {
            "added": [], "n_added": 0, "skipped_already_settled": [], "skipped_duplicate": 0,
            "unmeasured_sources": ["intake disabled for this pass"], "candidates_seen": 0}

        clocks = _clock_index(r)
        ctx = {"root": r, "clocks": clocks, "rows": rows, "basenames": _basename_index(r),
               "artifact_clocks": artifact_clock_index(r, clocks)}
        todo = sorted((x for x in rows if x.get("status") == "open"), key=priority)
        moved: list[dict[str, Any]] = []
        build_tasks: list[dict[str, Any]] = []
        deadline_hit = False
        for row in todo:
            elapsed = time.monotonic() - started
            # TWO PHASES, ONE BUDGET, AND EVERY ROW STILL GETS AN OWNER. Past half the budget
            # the git-backed proof rung is switched off rather than the pass being abandoned: a
            # row left untriaged has no owner and no next action, which is precisely the defect
            # this organ exists to remove, so a pass that runs out of time must degrade to CHEAP
            # triage and never to no triage. The proof rung is re-offered next hour.
            if elapsed > budget_s * 0.5:
                ctx["git_calls"] = GIT_CALLS_PER_PASS
                ctx["git_budget_hit"] = True
            if elapsed > budget_s * 0.97:
                deadline_hit = True
                break
            try:
                out = triage(row, ctx)
            except ValueError as exc:
                # A row this ladder cannot dispose LEGALLY is itself a finding, named rather than
                # swallowed: the alternative is an illegal row on disk or a silent skip.
                _block(row, f"triage produced an illegal disposition: {exc}",
                       "hourly_cycle:implementer",
                       "fix the ladder rung that produced it", "needs_code")
                out = {"id": str(row.get("id")), "state": "blocked", "why": str(exc),
                       "owner": "hourly_cycle:implementer", "blocker_class": "needs_code"}
            moved.append(out)
            if out.get("build_task"):
                build_tasks.append(out["build_task"])

        d["last_drain_at"] = datetime.now(tz=UTC).isoformat()
        d["last_drain_by"] = "desks/mt5/research/implementer.py"
        save_ledger(d, r)

    open_after = sum(1 for x in rows if x.get("status") == "open")
    orphans = [x for x in rows if x.get("status") == "open"
               and not (x.get("owner") and x.get("next_action"))]
    oldest = min((x for x in rows if x.get("status") == "open"),
                 key=lambda x: str(x.get("raised") or "9"), default=None)
    by_state: dict[str, int] = {}
    for m in moved:
        by_state[m["state"]] = by_state.get(m["state"], 0) + 1
    blockers: dict[str, int] = {}
    for x in rows:
        if x.get("status") == "open" and x.get("blocker_class"):
            blockers[str(x["blocker_class"])] = blockers.get(str(x["blocker_class"]), 0) + 1

    rise_reason = (f"intake: {ink['n_added']} row(s) from the CEO docket and the frontier audit"
                   if ink["n_added"] else None)
    ratchet = update_ratchet(open_after, rise_reason, r / RATCHET.relative_to(ROOT))

    doc = {
        "generated_utc": datetime.now(tz=UTC).isoformat(),
        "cadence_h": CADENCE_H,
        "open_before": open_before, "open_after": open_after,
        "moved": by_state, "n_moved": len(moved),
        "rows": moved[:200],
        "intake": ink,
        "build_tasks": build_tasks,
        "largest_blocker_class": max(blockers.items(), key=lambda kv: kv[1])[0] if blockers
        else None,
        "blocker_classes": dict(sorted(blockers.items(), key=lambda kv: -kv[1])),
        "oldest_open": ({"id": oldest.get("id"), "raised": oldest.get("raised"),
                         "age_h": round(_age_h(oldest.get("raised")), 1),
                         "owner": oldest.get("owner"), "next_action": oldest.get("next_action"),
                         "summary": str(oldest.get("summary"))[:160]} if oldest else None),
        "open_without_owner": [str(x.get("id")) for x in orphans][:50],
        "n_open_without_owner": len(orphans),
        "ratchet": {"floor": ratchet.get("floor"), "rises": len(ratchet.get("rises") or [])},
        "budget_s": budget_s, "elapsed_s": round(time.monotonic() - started, 1),
        "deadline_hit": deadline_hit,
        "law": ("No recommendation may sit OPEN with no owner and no next action. `blocked` is "
                "recorded as owner + next_action + blocker on a row that STAYS open, so every "
                "existing fence still counts it -- a fifth status would be a better hiding "
                "place than `scheduled` ever was."),
    }
    # THE DIRECTORY MUST BE MADE UNDER `r`, NOT UNDER THE MODULE'S OWN ROOT. `OUT` is absolute and
    # points at the real tree, so `OUT.parent.mkdir` created the repo's reports/ and left the
    # target root's missing -- a pass against any other root then wrote nowhere. Caught by the
    # organ's own tests, which is the reason they take a root at all.
    art_path = r / OUT.relative_to(ROOT)
    art_path.parent.mkdir(parents=True, exist_ok=True)
    art_path.write_text(json.dumps(doc, indent=1, default=str), "utf-8")
    _render(doc, r)
    try:
        from libs.ops.events import leg_events
        leg_events("implementer", "ok" if not orphans else "defect",
                   path=r / "desks" / "mt5" / "data" / "events.jsonl",
                   moved=len(moved), open_after=open_after, orphans=len(orphans))
    except Exception as exc:                                       # never fatal (L2.4)
        print(f"  WARNING: events not written: {type(exc).__name__}: {exc}")
    return doc


def _render(doc: dict[str, Any], root: Path) -> None:
    """One screen, derived from the artifact. Never hand-edited -- edit the organ or the ledger."""
    o = doc.get("oldest_open") or {}
    lines = [
        "# Implementation lane", "",
        "DERIVED FILE -- rendered from `desks/mt5/reports/IMPLEMENTER.json` by "
        "`desks/mt5/research/implementer.py`. Edit the organ or the ledger, never this page.", "",
        f"Measured {doc['generated_utc']} · leg `hourly_cycle:implementer` · cadence "
        f"{doc['cadence_h']:g}h", "",
        f"- OPEN before this pass: **{doc['open_before']}** -> after: **{doc['open_after']}**",
        f"- rows moved: **{doc['n_moved']}** "
        + (", ".join(f"{k} {v}" for k, v in sorted(doc["moved"].items())) or "none"),
        f"- intake: {doc['intake']['n_added']} new row(s); "
        f"{len(doc['intake']['skipped_already_settled'])} proposal(s) NOT re-proposed because the "
        f"desk already settled them",
        f"- open rows with no owner and no next action: **{doc['n_open_without_owner']}** "
        "(the defect this organ exists to remove; it must be 0)",
        f"- largest blocker class: **{doc['largest_blocker_class'] or 'none'}**",
        f"- OPEN ratchet floor: {doc['ratchet']['floor']} "
        f"({doc['ratchet']['rises']} recorded rise(s))",
        "",
    ]
    if o:
        lines += [f"Oldest OPEN row: **{o.get('id')}** raised {o.get('raised')} "
                  f"({o.get('age_h')}h) · owner `{o.get('owner')}`", "",
                  f"> {o.get('summary')}", "",
                  f"Next action: {o.get('next_action')}", ""]
    if doc["blocker_classes"]:
        lines += ["| blocker class | open rows |", "|---|---|"]
        lines += [f"| {k} | {v} |" for k, v in doc["blocker_classes"].items()]
        lines.append("")
    if doc["build_tasks"]:
        lines += ["## Build tasks opened this pass", "",
                  "A recommendation that asks for code gets a task, never speculative code.", "",
                  "| task | target | owner | recommendation |", "|---|---|---|---|"]
        lines += [f"| {b['id']} | `{b.get('target') or 'unspecified'}` | {b['owner']} | "
                  f"{b['rec']} |" for b in doc["build_tasks"][:25]]
        lines.append("")
    if doc["intake"]["unmeasured_sources"]:
        lines += ["## UNMEASURED sources", "",
                  "An absent source is a real answer (L1.28a) and is named rather than skipped:",
                  ""]
        lines += [f"- {s}" for s in doc["intake"]["unmeasured_sources"]]
        lines.append("")
    (root / DOC.relative_to(ROOT)).parent.mkdir(parents=True, exist_ok=True)
    (root / DOC.relative_to(ROOT)).write_text("\n".join(lines), "utf-8")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--once", action="store_true", help="one pass (the leg's mode)")
    ap.add_argument("--budget-s", type=float, default=600.0, help="wall-clock budget for the pass")
    ap.add_argument("--no-intake", action="store_true",
                    help="drain only; do not pull the docket or the frontier audit")
    a = ap.parse_args(argv)
    doc = run(budget_s=a.budget_s, do_intake=not a.no_intake)
    print(f"IMPLEMENTER  open {doc['open_before']} -> {doc['open_after']}  "
          f"moved {doc['n_moved']} {doc['moved']}")
    print(f"  intake +{doc['intake']['n_added']}  "
          f"already-settled {len(doc['intake']['skipped_already_settled'])}  "
          f"duplicates {doc['intake']['skipped_duplicate']}")
    print(f"  blockers {doc['blocker_classes']}  largest={doc['largest_blocker_class']}")
    if doc["oldest_open"]:
        o = doc["oldest_open"]
        print(f"  oldest OPEN {o['id']} {o['age_h']}h owner={o['owner']}")
    if doc["n_open_without_owner"]:
        print(f"  DEFECT: {doc['n_open_without_owner']} open row(s) with no owner/next action")
    print(f"  -> {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
