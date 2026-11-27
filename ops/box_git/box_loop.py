"""THE BOX'S RELEASE LOOP: gate sweep, PR checks, full suite, seal and promote -- no GitHub.

One pass every few minutes (scheduled task QuantForge-Loop, IgnoreNew, installed by
install_box_forge.ps1). Each stage is the GitHub-era stage it replaces, run on the box:

  0. INBOX  packets from cloud threads (ops/box_git/inbox.py), pushed as the `claude` account so
             the repository hook judges them exactly as a thread's push.
  1. GATE    .github/scripts/audit_gate.py --sweep --box, from a clean checkout of LIVE (trusted
             code, never a PR's), answered by the forge (ops/box_git/forge_api.py), pushing as
             the merge-gate account. Same rules: CLEAR at the exact head, HOLD beats green, gating
             jobs green, pinned merges.
  2. PR CHECK  one open PR per pass whose head has no box CI status: impacted tests
             (ops/box_git/impacted.py) on idle cores, statuses posted as the box-ci account under
             the gating names (quality, mt5-money-path, coverage-floor), each saying exactly what
             ran. Fast lane: a change no test can see posts green with that reason.
  2b. SIGN   scripts/sign_train.py at LIVE's head when a CLEAR row or sealed file moved
             (sign_tick): the audit-signed re-sign of a sealed judge file, fast-forwarded.
  3. FULL    LIVE's head, coalesced (box_ci.plan_full_run): law gate + the whole suite.
  4. SEAL + PROMOTE  at the newest fully green head only (box_ci.promotable): RELEASE.json sealed
             and pushed to LIVE exactly as ci.yml's seal job did, then scripts/release_promotion.py
             promote (tag, production fast-forward, master) as the release-authority account.
             MT5-AdoptRelease then adopts production as it always has.

Disk floor and idle cores (box_ci) bind every test stage. Nothing here writes C:\\opt\\quant.
"""
from __future__ import annotations

import contextlib
import difflib
import json
import os
import re
import shutil
import subprocess
import sys
import threading
import time
from collections.abc import Callable, Iterator, Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
if str(HERE.parents[1]) not in sys.path:
    sys.path.insert(0, str(HERE.parents[1]))

from ops.box_git import (  # noqa: E402
    box_ci,
    delivery_leadtime,
    drop_pull,
    forge_api,
    guard,
    impacted,
    inbox,
    state_publish,
)

LIVE = "claude/llm-auto-upgrade-verify-gcjac3"
GATING = ("quality", "mt5-money-path", "coverage-floor")
#: (boot r21) DIRECT LIVE. zuck 2026-11-27 11:40Z "no more tests no releases no merges js built n
#: direct live", 11:42Z (on keeping only the automatic safety check on code that places real
#: trades) "ok only that nth else". The one delivery gate is now the Auditor's CLEAR at the exact
#: head plus, ONLY when the diff touches the money path (ops/release/replay_shadow.is_money, read
#: from LIVE's own tree), the risk invariants: the ceilings, the prop-firm rules and the survival
#: suites. No replay-shadow, no impacted tests, no full suite, no all-green release: LIVE's newest
#: head is promoted on the next light round (90 s) and the box's adoption task is started at once.
#: The trust boundary at the door (protect.py) and the runtime rails are unchanged. False is r20.
DIRECT_LIVE = True
DIRECT_ENV = "QUANT_FORGE_DIRECT"
ADOPT_TASK = "MT5-AdoptRelease"
RELEASE_JSON = "desks/mt5/data/RELEASE.json"
#: (boot r23) THE GUARD HOLDS THE PEN. zuck 2026-11-27 13:13Z: an independent, protected,
#: automated checker validates AI-written code and it deploys automatically; he intervenes only
#: for authority and protected safeguards. Every PR into LIVE is checked by ops/box_git/guard.py
#: (its code runs under quantci, the verdict is written by this loop) and merged on a PASS with no
#: seat's CLEAR. A TRUST-class PR takes the legacy owner path. False is r21/r22 exactly.
GUARD_LIVE = True
#: (boot r23, Audit D1, measured on the box 2026-11-27 13:20Z) The pen is only independent while
#: the code it lets through cannot write the pen. Today it can: MT5-Gateway and MT5-HourlyCore run
#: the live tree as Administrator (Highest), MT5-Hourly, MT5-AdoptRelease and the forward clocks
#: as SYSTEM, and both may write C:\ProgramData\QuantBox\guard and \trust. So until every task
#: that runs C:\opt\quant runs as a non-admin account denied those folders (boot r24), a PASS
#: also needs the Auditor's CLEAR of the exact head. The checks run at once and in parallel with
#: the review (quantci is already isolated), so the CLEAR adds no wait beyond the review itself.
REQUIRE_SEAT_CLEAR = True
RUN_AS_PROOF = "runas/RUN_AS.json"  # (r24) the pinned SYSTEM migrator writes it; quantgate reads


def seat_required(cfg: Any, now: datetime | None = None) -> tuple[bool, str]:
    r"""(r24, Audit MF-B) Re-read every cycle. While REQUIRE_SEAT_CLEAR is on (until the owner's
    flip packet) the seat is required. After the flip, it is required again by itself the moment
    guard\RUN_AS.json is missing, stale or shows an elevated live-tree task."""
    if REQUIRE_SEAT_CLEAR:
        return True, "REQUIRE_SEAT_CLEAR"
    from ops.box_git import runas_plan
    try:
        doc = json.loads((guard_dir(cfg) / RUN_AS_PROOF).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        doc = None
    ok, why = runas_plan.proof_holds(doc, now or datetime.now(UTC))
    return (not ok), why


@dataclass(frozen=True)
class Config:
    forge_url: str            # https://127.0.0.1:443
    bare: Path                # the forge repo's bare path
    work: Path                # scratch for worktrees (pruned)
    tokens: Path              # Administrators/SYSTEM-only folder: <account>.token
    ca: Path                  # the forge's certificate
    state: Path               # box CI state JSON
    python: str = sys.executable
    inbox: Path | None = None # packets from cloud threads (ops/box_git/inbox.py)
    boot: str | None = None   # the Audit-CLEARed head the installer ran from (see gate_code)
    ci_jobs: Path | None = None  # hand-off folder to the unprivileged CI worker (Audit MF-2)
    trust_checker: Path | None = None  # box-local pinned trust checker (D-20261119-TRUSTSET)
    trust_pin: Path | None = None
    drop: drop_pull.Drop | None = None  # private drop repo the box pulls by itself
    state_outbox: Path | None = None    # MT5-ShadowSync's bundle outbox (ops/box_git/state_publish)

    def token(self, account: str) -> str:
        return (self.tokens / f"{account}.token").read_text(encoding="utf-8").strip()

    def git_env(self, account: str) -> dict[str, str]:
        """git over HTTPS to the forge as `account`, through command-scope config only."""
        return {**os.environ, "GIT_TERMINAL_PROMPT": "0", "GIT_CONFIG_COUNT": "3",
                "GIT_CONFIG_KEY_0": "safe.directory", "GIT_CONFIG_VALUE_0": "*",
                "GIT_CONFIG_KEY_1": "http.sslCAInfo", "GIT_CONFIG_VALUE_1": str(self.ca),
                "GIT_CONFIG_KEY_2": "http.extraHeader",
                "GIT_CONFIG_VALUE_2": f"Authorization: token {self.token(account)}"}

    def remote(self) -> str:
        return f"{self.forge_url.rstrip('/')}/quant/quant.git"


class StallGuard:
    """THE PASS NEVER HANGS SILENTLY (box 2026-11-26: the 04:39Z pass sat at 0 CPU with no child
    and no socket from ~06:03Z, inside Python cleanup of a half-removed checkout, and only the
    task's 8 h limit would have ended it -- adoption stalled all night behind one stuck call).

    Every stage start and every job poll is a beat; a child process is alive until its own
    timeout. When neither has moved for `stall_s`, the guard writes LOOP_STALL.json and ends the
    process, so the next 5-minute trigger starts a clean pass (sweep_stale then removes the
    half-made checkout). It never touches a child that is still inside its timeout."""

    def __init__(self, stall_s: float = 2700.0, *, clock: Callable[[], float] = time.monotonic,
                 on_stall: Callable[[dict[str, Any]], None] | None = None) -> None:
        self.stall_s, self.clock, self.on_stall = stall_s, clock, on_stall
        self.stage, self.last, self.until = "start", clock(), 0.0
        self._lock = threading.Lock()

    def beat(self, stage: str | None = None) -> None:
        with self._lock:
            if stage:
                self.stage = stage
            self.last = self.clock()

    def child(self, timeout: float) -> None:
        with self._lock:
            self.until = max(self.until, self.clock() + timeout + 60.0)

    def child_done(self) -> None:
        with self._lock:
            self.until, self.last = 0.0, self.clock()

    def stalled(self) -> dict[str, Any] | None:
        with self._lock:
            now = self.clock()
            if now <= max(self.last + self.stall_s, self.until):
                return None
            return {"stage": self.stage, "silent_s": round(now - self.last),
                    "stall_s": self.stall_s}

    def watch(self, every_s: float = 30.0) -> threading.Thread:
        def loop() -> None:
            while True:
                time.sleep(every_s)
                why = self.stalled()
                if why is not None and self.on_stall is not None:
                    self.on_stall(why)
                    return
        t = threading.Thread(target=loop, name="stall-guard", daemon=True)
        t.start()
        return t


GUARD: StallGuard | None = None


def _run(argv: Sequence[str], *, cwd: Path | None = None, env: Mapping[str, str] | None = None,
         timeout: float = 3600, idle: bool = False) -> tuple[int, str]:
    kw: dict[str, Any] = box_ci.idle_priority_kwargs() if idle else {}
    if GUARD is not None:
        GUARD.child(timeout)
    try:
        p = subprocess.run(list(argv), cwd=cwd, env=dict(env) if env else None,
                           capture_output=True, text=True, encoding="utf-8", errors="replace",
                           timeout=timeout, check=False, **kw)
    except subprocess.TimeoutExpired:
        return 124, f"timed out after {timeout:.0f}s"
    except OSError as exc:
        return 127, f"{type(exc).__name__}: {exc}"
    finally:
        if GUARD is not None:
            GUARD.child_done()
    return p.returncode, (p.stdout + p.stderr)[-4000:]


#: A full checkout of this tree is ~50k files; on the box (Windows, real-time scanning on) one
#: took over 300 s while the disk was busy (11-20 19:55Z: gate and pr both "worktree add timed
#: out after 300s", so CI never started on any PR). Checkouts get their own, longer limit and
#: git's parallel checkout; every other bare-repo command keeps the 300 s limit.
WORKTREE_ADD_TIMEOUT = 1800
_FAST_CHECKOUT = ("-c", "checkout.workers=0", "-c", "core.fscache=true",
                  "-c", "core.preloadindex=true")


def git(cfg: Config, *args: str, timeout: float = 300) -> str:
    rc, out = _run(["git", "-C", str(cfg.bare), *args], timeout=timeout)
    if rc != 0:
        raise RuntimeError(f"git {' '.join(args)}: {out.strip()[-300:]}")
    return out.strip()


#: (boot r20) Stages run concurrently (parallel PR checks, the light loop beside the heavy
#: stages): git's worktree bookkeeping in the one bare repo is serialised here, and every
#: read-modify-write of the CI state file holds STATE_LOCK.
_WT_LOCK = threading.Lock()
STATE_LOCK = threading.RLock()


def _drop_worktree(cfg: Config, d: Path) -> None:
    with _WT_LOCK:
        _run(["git", "-C", str(cfg.bare), "worktree", "remove", "--force", str(d)], timeout=300)
    box_ci.prune(d)  # a plain delete of what git left: outside the lock, it can take minutes
    with _WT_LOCK:
        _run(["git", "-C", str(cfg.bare), "worktree", "prune"], timeout=120)


@contextlib.contextmanager
def worktree(cfg: Config, sha: str) -> Iterator[Path]:
    cfg.work.mkdir(parents=True, exist_ok=True)
    # A checkout is a full tree: never make one below the disk floor (box 2026-11-20: CI
    # checkouts helped push the desk volume under its own 5 GB floor).
    ok, why = box_ci.disk_ok(shutil.disk_usage(cfg.work).free / 1024 ** 3)
    if not ok:
        raise RuntimeError(f"no checkout: {why}")
    d = box_ci.shared_dir(cfg.work, "wt_")
    try:
        with _WT_LOCK:
            git(cfg, *_FAST_CHECKOUT, "worktree", "add", "-q", "--detach", str(d), sha,
                timeout=WORKTREE_ADD_TIMEOUT)
    except RuntimeError:
        # a half-made checkout must not wait for the next pass's sweep to give its disk back
        _drop_worktree(cfg, d)
        raise
    try:
        yield d
    finally:
        _drop_worktree(cfg, d)


def sweep_stale(cfg: Config) -> int:
    """Remove checkouts a pass that died left behind. Called ONCE at the start of a pass, before
    any checkout exists (Audit MF-1: worktree() nests, so sweeping inside it would delete the
    outer checkout). Passes never overlap (the task does not start a second instance)."""
    if not cfg.work.is_dir():
        return 0
    n = 0
    for stale in cfg.work.glob("wt_*"):
        _run(["git", "-C", str(cfg.bare), "worktree", "remove", "--force", str(stale)],
             timeout=300)
        box_ci.prune(stale)
        n += 1
    if n:
        _run(["git", "-C", str(cfg.bare), "worktree", "prune"], timeout=120)
    return n


def _forge(cfg: Config, account: str) -> forge_api.Forge:
    env = {forge_api.FORGE_URL_ENV: cfg.forge_url, forge_api.FORGE_CA_ENV: str(cfg.ca),
           forge_api.FORGE_TOKEN_FILE_ENV: str(cfg.tokens / f"{account}.token")}
    return forge_api.Forge(forge_api.http_transport(env), workflow_of={}, bare=str(cfg.bare))


def post(cfg: Config, sha: str, state: str, desc: str,
         contexts: Sequence[str] = GATING) -> None:
    f = _forge(cfg, forge_api.BOX_CI_USER)
    for ctx in contexts:
        f.t("POST", f"/repos/{forge_api.FORGE_REPO}/statuses/{sha}",
            {"state": state, "context": ctx, "description": desc[:250]})


@dataclass
class Hold:
    workers: int
    worktrees: int


class Reservations:
    """(boot r20, Audit HOLD MF1) ONE locked budget for every concurrent CI job on the box.

    The sum of workers held never exceeds box_ci.idle_workers() of the cores measured now (at
    most MAX_WORKERS, RESERVE_CORES kept back); free disk minus every held and requested checkout
    (WORKTREE_GB each) stays at or above DISK_FLOOR_GB; available RAM minus RAM_PER_CHECK_GB for
    every held and requested job stays at or above RAM_FLOOR_GB. Anything unmeasured grants
    nothing: the job waits."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self.workers = 0
        self.worktrees = 0
        self.jobs = 0

    def _measure(self, cfg: Config) -> tuple[float, list[float], float]:
        import psutil  # type: ignore[import-untyped,unused-ignore]
        free = psutil.disk_usage(str(cfg.work.anchor or cfg.work)).free / 1024 ** 3
        cores = psutil.cpu_percent(interval=1.0, percpu=True)
        ram = psutil.virtual_memory().available / 1024 ** 3
        return free, cores, ram

    def take(self, cfg: Config, want: int | None, worktrees: int) -> tuple[Hold | None, str]:
        with self._lock:
            try:
                free, cores, ram = self._measure(cfg)
            except Exception as exc:  # unmeasured resources start nothing
                return None, f"resources UNMEASURED ({type(exc).__name__})"
            total = box_ci.idle_workers(cores)
            spare = total - self.workers
            if spare < 1:
                return None, f"no worker slot: {self.workers} of {total} held"
            left = free - (self.worktrees + worktrees) * box_ci.WORKTREE_GB
            ok, why = box_ci.disk_ok(left)
            if not ok:
                return None, f"disk after checkouts: {why}"
            if ram - (self.jobs + 1) * box_ci.RAM_PER_CHECK_GB < box_ci.RAM_FLOOR_GB:
                return None, (f"RAM {ram:.1f} GB available, {self.jobs} job(s) running: under the "
                              f"{box_ci.RAM_FLOOR_GB:.0f} GB floor")
            n = spare if want is None else max(1, min(want, spare))
            self.workers += n
            self.worktrees += worktrees
            self.jobs += 1
            return Hold(n, worktrees), why

    def release(self, hold: Hold) -> None:
        with self._lock:
            self.workers -= hold.workers
            self.worktrees -= hold.worktrees
            self.jobs -= 1


RES = Reservations()
#: A fast-path check holds one worker and three checkouts (the head's, and replay's base + head).
FAST_CHECK_WORKTREES = 3


# ------------------------------------------------------------------ untrusted code (Audit MF-2)
#: A PR's own code (its tests, conftest, strategies under replay) never runs as SYSTEM. The loop
#: hands each such command to the CI WORKER: a scheduled task running as the local non-admin
#: account `quantci`, denied the token folder, the trust folder, data\secrets and C:\opt\quant.
#: The loop reads back only the exit code and the output tail, and posts statuses itself.
JOB_ENV_KEEP = ("PATH", "SYSTEMROOT", "PATHEXT", "COMSPEC", "NUMBER_OF_PROCESSORS", "PYTHONUTF8")
#: The CI WORKER's own profile, never the loop's: Path.home() needs these on Windows, and 38-48
#: test modules failed collection ("Could not determine home directory") while the job carried
#: none of them (box 2026-11-24). The worker adds its own values; whatever a job file says about
#: them is ignored, so the loop can never point a job at another account's profile.
WORKER_OWN_ENV = ("USERPROFILE", "HOMEDRIVE", "HOMEPATH", "APPDATA", "LOCALAPPDATA", "TEMP",
                  "TMP")
JOB_POLL_S = 5.0


def _run_untrusted(cfg: Config, argv: Sequence[str], *, cwd: Path,
                   extra_env: Mapping[str, str] | None = None,
                   timeout: float = 3600) -> tuple[int, str]:
    if cfg.ci_jobs is None:  # development and tests only: the installer always sets ci_jobs
        return _run(argv, cwd=cwd, env={**os.environ, **(extra_env or {})}, timeout=timeout,
                    idle=True)
    import time
    import uuid
    jid = uuid.uuid4().hex
    pending, done = cfg.ci_jobs / "pending", cfg.ci_jobs / "done"
    pending.mkdir(parents=True, exist_ok=True)
    done.mkdir(parents=True, exist_ok=True)
    env = {k: os.environ[k] for k in JOB_ENV_KEEP if k in os.environ}
    # the worktrees belong to SYSTEM; the worker's git must read them (no token, no remote)
    env.update({"GIT_CONFIG_COUNT": "1", "GIT_CONFIG_KEY_0": "safe.directory",
                "GIT_CONFIG_VALUE_0": "*", "GIT_TERMINAL_PROMPT": "0"})
    job = {"id": jid, "argv": list(argv), "cwd": str(cwd), "env": {**env, **(extra_env or {})},
           "timeout": timeout}
    tmp = pending / f"{jid}.tmp"
    tmp.write_text(json.dumps(job), encoding="utf-8")
    os.replace(tmp, pending / f"{jid}.json")
    deadline = time.monotonic() + timeout + 900
    result = done / f"{jid}.json"
    while time.monotonic() < deadline:
        if result.exists():
            try:
                doc = json.loads(result.read_text(encoding="utf-8"))
                result.unlink(missing_ok=True)
                return int(doc.get("rc", 1)), str(doc.get("out", ""))[-4000:]
            except (OSError, ValueError):
                pass  # the worker is still writing it
        if GUARD is not None:
            GUARD.child(JOB_POLL_S)  # waiting on the worker inside the job's own deadline
        time.sleep(JOB_POLL_S)
    (pending / f"{jid}.json").unlink(missing_ok=True)
    return 124, "the CI worker did not answer in time"


#: (boot r20) The worker runs jobs CONCURRENTLY and keeps taking new ones while any run: with
#: parallel PR checks a serial worker would have been the queue again. Bounded like the checks.
WORKER_PARALLEL_MAX = 6
WORKER_IDLE_EXIT_S = 240.0  # stays up between back-to-back checks: the task is periodic


def _run_job(f: Path, done: Path) -> bool:
    try:
        job = json.loads(f.read_text(encoding="utf-8"))
        f.unlink()
    except (OSError, ValueError):
        return False
    env = {str(k): str(v) for k, v in (job.get("env") or {}).items()
           if str(k).upper() not in WORKER_OWN_ENV}
    env.update({k: os.environ[k] for k in WORKER_OWN_ENV if k in os.environ})
    rc, out = _run([str(a) for a in job.get("argv") or []], cwd=Path(job["cwd"]),
                   env=env, timeout=float(job.get("timeout") or 3600), idle=True)
    tmp = done / f"{job['id']}.tmp"
    done.mkdir(parents=True, exist_ok=True)
    tmp.write_text(json.dumps({"rc": rc, "out": out}), encoding="utf-8")
    os.replace(tmp, done / f"{job['id']}.json")
    return True


def worker_pass(jobs: Path, *, parallel: int | None = None,
                idle_exit_s: float = WORKER_IDLE_EXIT_S, poll_s: float = 2.0) -> int:
    """One pass of the unprivileged CI worker: run pending jobs concurrently, taking new ones as
    they arrive, until nothing is running and nothing has arrived for `idle_exit_s`."""
    import concurrent.futures as cf
    pending, done = jobs / "pending", jobs / "done"
    k = parallel or max(1, min(WORKER_PARALLEL_MAX, (os.cpu_count() or 1) // 3))
    n = 0
    taken: set[str] = set()
    running: set[cf.Future[bool]] = set()
    quiet_since = time.monotonic()
    with cf.ThreadPoolExecutor(max_workers=k, thread_name_prefix="ci-job") as pool:
        while True:
            for f in sorted(pending.glob("*.json")) if pending.is_dir() else []:
                if len(running) >= k:
                    break
                if f.name in taken:
                    continue
                taken.add(f.name)
                running.add(pool.submit(_run_job, f, done))
            if running:
                fin, _ = cf.wait(running, timeout=poll_s, return_when=cf.FIRST_COMPLETED)
                for fu in fin:
                    running.discard(fu)
                    with contextlib.suppress(Exception):
                        n += 1 if fu.result() else 0
                quiet_since = time.monotonic()
                continue
            if time.monotonic() - quiet_since >= idle_exit_s:
                break
            time.sleep(poll_s)
    return n


CI_LOGS = "ci_logs"
KEEP_CI_LOGS = 200


def keep_log(cfg: Config, name: str, out: str) -> Path | None:
    """The run's output tail, kept next to the CI state: the forge status holds one line, and
    a red with no log cannot be diagnosed (box 11-20: PR #17 red on '+++ Timeout +++', no test
    named). Oldest logs beyond KEEP_CI_LOGS are dropped. Never raises."""
    try:
        d = cfg.state.parent / CI_LOGS
        d.mkdir(parents=True, exist_ok=True)
        f = d / f"{name}.log"
        f.write_text(out, encoding="utf-8")
        for old in sorted(d.glob("*.log"), key=lambda p: p.stat().st_mtime)[:-KEEP_CI_LOGS]:
            old.unlink(missing_ok=True)
        return f
    except OSError:
        return None


def run_tests(cfg: Config, root: Path, tests: Sequence[str] | str,
              workers: int, name: str = "") -> tuple[bool, str]:
    junit = root / "box-junit.xml"
    rc, out = _run_untrusted(cfg, box_ci.pytest_argv(cfg.python, tests, workers, junit),
                             cwd=root, timeout=6 * 3600)
    if name:
        keep_log(cfg, name, out)
    lines = out.strip().splitlines()
    failed = [ln for ln in lines if ln.startswith(("FAILED ", "ERROR "))][:3]
    tail = lines[-1:] or [""]
    named = ("; " + "; ".join(f[:90] for f in failed)) if failed else ""
    return rc == 0, f"pytest rc={rc}: {tail[0][:180]}{named}"[:240]


def risk_job(cfg: Config, root: Path, base: str, head: str,
             suite_timeout_s: int = 3600) -> tuple[bool, str]:
    """release-gates.yml `risk-invariants`, on the box: the ceilings, suites and their tests
    from the BASE, the PR's code, the static invariants then the risk suites."""
    if _run(["git", "checkout", base, "--", "ops/release"], cwd=root)[0] != 0:
        return False, "risk-invariants: could not take ops/release from the base"
    suites_file = root / "ops" / "release" / "risk_suites.txt"
    try:
        suites = [ln.strip() for ln in suites_file.read_text(encoding="utf-8").splitlines()
                  if ln.strip() and not ln.startswith("#")]
    except OSError:
        return False, "risk-invariants: risk_suites.txt unreadable"
    if suites and _run(["git", "checkout", base, "--", *suites], cwd=root)[0] != 0:
        return False, "risk-invariants: could not take the risk suites from the base"
    rc, out = _run_untrusted(cfg, [cfg.python, "-I", "ops/release/risk_invariants.py",
                                   "--head", head, "--base", base], cwd=root, timeout=1800)
    keep_log(cfg, f"risk-static-{head[:12]}", out)   # (r19) a red keeps its whole output
    if rc != 0:
        return False, f"risk-invariants static rc={rc}: {out.strip()[-160:]}"
    if suites:
        rc, out = _run_untrusted(cfg, [cfg.python, "-m", "pytest", "-q", "-p", "no:randomly",
                                       "-p", "no:cacheprovider", "--timeout=600", *suites],
                                 cwd=root, timeout=suite_timeout_s)
        keep_log(cfg, f"risk-suites-{head[:12]}", out)
        if rc != 0:
            return False, f"risk suites rc={rc}: {out.strip()[-160:]}"
    return True, f"risk-invariants passed ({len(suites)} suite file(s))"


def replay_job(cfg: Config, base: str, head: str, changed: Sequence[str],
               timeout_s: int = 3600) -> tuple[bool, str]:
    """release-gates.yml `replay-shadow`, on the box: the BASE's harness replays the live E8
    book on the base and on the PR head; any divergence not declared fails."""
    with worktree(cfg, base) as b, worktree(cfg, head) as h:
        lst = cfg.work / f"changed_{head[:12]}.txt"
        lst.write_text("\n".join(sorted(set(changed))) + "\n", encoding="utf-8")
        report = cfg.work / f"replay_{head[:12]}.json"
        extra = {"QUANT_EXPECTED_DIVERGENCE":
                 str(b / "ops" / "release" / "expected_divergence.json")}
        rc, out = _run_untrusted(cfg, [cfg.python, "-I",
                                       str(b / "ops" / "release" / "replay_shadow.py"),
                                       "--base", str(b), "--head", str(h), "--changed", str(lst),
                                       "--report", str(report)],
                                 cwd=cfg.work, extra_env=extra, timeout=timeout_s)
        try:
            rep = report.read_text(encoding="utf-8")
        except OSError:
            rep = ""
        # (r19) the whole run is kept: PR #127 went red at 21:35Z on a 160-char tail cut mid-JSON
        # and its report was deleted, so the reason was unrecoverable on the box.
        kept = keep_log(cfg, f"replay-{head[:12]}", f"{out}\n--- report ---\n{rep}\n")
        lst.unlink(missing_ok=True)
        report.unlink(missing_ok=True)
    where = f" [log ci_logs/{kept.name}]" if kept else ""
    return rc == 0, f"replay-shadow rc={rc}: {out.strip()[-140:]}{where}"


# ------------------------------------------------------------------------------ the stages
#: The checkout this loop runs from (the installer's loop source). It always holds the boot
#: commit, because the installer ran from it.
LOOP_SRC = Path(__file__).resolve().parents[2]


def ensure_boot(cfg: Config, src: Path = LOOP_SRC) -> str:
    """Make sure the forge repo holds the boot commit's objects. A boot move lands the commit in
    the loop source but not in the forge repo, and every gate then failed on "invalid reference"
    (2026-11-26). Objects only: no ref is created or moved, so the forge's branches are untouched;
    the check runs every pass, so a later gc that drops the objects is healed the same way."""
    if not cfg.boot:
        return "no boot"
    have = ["git", "-C", str(cfg.bare), "cat-file", "-e", f"{cfg.boot}^{{commit}}"]
    if _run(have, timeout=60)[0] == 0:
        return "present"
    rc, out = _run(["git", "-c", "safe.directory=*", "-C", str(cfg.bare), "fetch", "-q",
                    "--no-tags", str(src), cfg.boot], timeout=600)
    if rc == 0 and _run(have, timeout=60)[0] == 0:
        return f"fetched {cfg.boot[:12]} from {src}"
    return f"boot {cfg.boot[:12]} MISSING from the forge repo and not fetchable: {out[-200:]}"


def gate_code(cfg: Config, live: str) -> str:
    """The commit whose gate runs. LIVE, once LIVE contains the forge-aware gate. Until the box-git
    change itself has merged, LIVE's gate only knows GitHub (and fails closed there), so the gate
    runs from the Audit-CLEARed head the installer ran from: the same rules plus the forge
    transport, never a PR's own code."""
    if not cfg.boot or cfg.boot == live:
        return live
    ensure_boot(cfg)
    rc, _ = _run(["git", "-C", str(cfg.bare), "merge-base", "--is-ancestor", cfg.boot, live],
                 timeout=120)
    return live if rc == 0 else cfg.boot


def gate_tick(cfg: Config, live: str) -> str:
    if GUARD_LIVE:
        merged = guard_merge_tick(cfg)
        return f"guard: {merged}; {legacy_gate(cfg, live)}"
    return legacy_gate(cfg, live)


def legacy_gate(cfg: Config, live: str) -> str:
    """The audit gate (r22 and before). Under r23 it is the OWNER path: it can still merge only
    what the pinned checker or the owner's AUTHORIZE TRUST allows, at the door too."""
    with worktree(cfg, gate_code(cfg, live)) as root:
        env = {**os.environ, forge_api.FORGE_URL_ENV: cfg.forge_url,
               forge_api.FORGE_CA_ENV: str(cfg.ca), forge_api.FORGE_BARE_ENV: str(cfg.bare),
               forge_api.FORGE_TOKEN_FILE_ENV: str(cfg.tokens / "merge-gate.token"),
               "QUANT_TRUST_CHECKER": str(cfg.trust_checker or ""),
               "QUANT_TRUST_PIN": str(cfg.trust_pin or ""),
               DIRECT_ENV: "1" if DIRECT_LIVE else ""}
        rc, out = _run([cfg.python, ".github/scripts/audit_gate.py", "--repo",
                        forge_api.FORGE_REPO, "--sweep", "--box"], cwd=root, env=env, timeout=1800)
    return f"gate rc={rc}: {out.strip().splitlines()[-1][:200] if out.strip() else ''}"


#: A pending box CI status older than this is a run that died (reboot, kill): it is run again.
STALE_PENDING_S = 21600  # 6 h (a literal: it is a knob, boot r17)


#: A red caused by the BOX, not the code: git unable to read the repo (exit 128), a run that
#: outlived its limit, a worker that never answered. Box 11-20: PR #17's first CI went 5/5 red
#: on exactly these, and a completed red was final, so the head could never be re-run after the
#: cause was fixed. Such a red is re-run, at most ENV_RERUNS times, each ENV_RERUN_AFTER_S apart.
#: A red that names anything else (a failing test, a refused invariant) stays final.
_ENV_RED = re.compile(r"exit status 128|\+\+\+ Timeout \+\+\+|did not answer in time"
                      r"|timed out after|resources UNMEASURED|No space left")
ENV_RERUNS = 2
ENV_RERUN_AFTER_S = 3600


def _at(r: Mapping[str, Any]) -> datetime | None:
    try:
        return datetime.fromisoformat(str(r.get("started_at") or "").replace("Z", "+00:00"))
    except ValueError:
        return None


#: (boot r15) "timed out after N s" with N below the cap that job has NOW measured the old
#: budget, not the code. It does not count toward ENV_RERUNS and is re-run at once (it stays a
#: red until a run at the current cap passes), unless another context holds a real code red.
#: Anchored to the box's OWN framing as the WHOLE status text ("box: replay-shadow rc=124: timed
#: out after 600s", written by _run's timeout branch), never a phrase inside the child's output
#: tail, so head code that prints it cannot buy itself endless re-runs (Audit should-fix a, r15).
_TIMED_OUT = re.compile(r"\Abox: (?:replay-shadow|risk suites) rc=124: timed out after (\d+)s\Z")
#: A hard bound all the same: past this many old-cap reds in one context the reds count as usual
#: (a head that forges the box's exact framing buys at most this many extra runs). Today's PRs
#: carry 3 (the first run plus two env re-runs at 600 s).
UNDERCAP_REDS_MAX = 6


def _cap_now(name: str) -> int:
    return FAST_REPLAY_TIMEOUT_S if name == REPLAY_CONTEXT else FAST_RISK_TIMEOUT_S


def _undercap(r: Mapping[str, Any]) -> bool:
    out = r.get("output")
    m = _TIMED_OUT.search(str(out.get("summary") or "") if isinstance(out, Mapping) else "")
    return (r.get("status") == "completed" and r.get("conclusion") == "failure" and m is not None
            and int(m.group(1)) < _cap_now(str(r.get("name") or "")))


#: (boot r20) The box's OWN framing of a status: "box: <job> rc=<N>: <child output tail>". The
#: exit code is the box's measurement; the tail is the child's text. 11-26: PR #127/#128's
#: replay-shadow went red with rc=1 (a real FUSION-ROSTER divergence), but the tail of that output
#: matched _ENV_RED, so the red was read as a box defect and re-run every pass, alternating
#: with #128 at the head of the queue while 18 newer CLEARed PRs never got a check.
_BOX_FRAME = re.compile(r"\Abox: [^:\n]{0,80}?rc=(\d+)(?::|\Z)")
#: Exit codes that are the box's own (a run outliving its limit, git unable to read the repo).
#: Any other framed code -- 1 above all -- is the code's answer and decides the head.
ENV_RCS = frozenset({"124", "128"})


def _env_red(r: Mapping[str, Any]) -> bool:
    raw = r.get("output")
    out: Mapping[str, Any] = raw if isinstance(raw, Mapping) else {}
    text = str(out.get("summary") or "")
    if not (r.get("status") == "completed" and r.get("conclusion") == "failure"):
        return False
    framed = _BOX_FRAME.search(text)
    if framed:
        return framed.group(1) in ENV_RCS
    return bool(_ENV_RED.search(text))


def checked(runs: Sequence[Mapping[str, Any]], now: datetime | None = None) -> bool:
    """Has box CI already answered (or is it plausibly still answering) for this head?"""
    t = now or datetime.now(UTC)
    done = [r for r in runs if r.get("status") == "completed"]
    if done:
        latest: dict[str, Mapping[str, Any]] = {}
        for r in sorted(done, key=lambda r: (_at(r) or datetime.min.replace(tzinfo=UTC),
                                             int(r.get("id") or 0))):
            latest[str(r.get("name") or "")] = r
        spent = {n for n in latest
                 if sum(1 for x in done if x.get("name") == n and _undercap(x)) > UNDERCAP_REDS_MAX}

        def old_cap(r: Mapping[str, Any]) -> bool:
            return _undercap(r) and str(r.get("name") or "") not in spent

        if any(old_cap(r) for r in latest.values()):
            # (r15) a red at an old, smaller cap: run it again now -- unless another context
            # already holds a real code red, which decides the head on its own
            return any(r.get("conclusion") == "failure" and not _env_red(r)
                       for r in latest.values())
        reds = [r for r in latest.values() if _env_red(r)]
        rounds = max((sum(1 for r in done if r.get("name") == n and _env_red(r)
                           and not old_cap(r)) for n in latest), default=0)
        newest = max((a for r in reds if (a := _at(r)) is not None), default=None)
        code_red = any(r.get("conclusion") == "failure" and not _env_red(r)
                       for r in latest.values())
        if code_red or not reds or rounds > ENV_RERUNS or newest is None:
            return True
        rerun = [r for r in runs if r.get("status") != "completed"
                 and (a := _at(r)) is not None and a > newest]
        if not rerun:
            return (t - newest).total_seconds() < ENV_RERUN_AFTER_S
        runs = rerun                           # a re-run in flight: judged like any pending
    for r in runs:
        at = _at(r)
        if at is not None and (t - at).total_seconds() < STALE_PENDING_S:
            return True
    return False


_VERDICT = re.compile(r"^AUDIT (CLEAR|HOLD) ([0-9a-f]{40})(?: (merge|squash))?[ \t]*$", re.M)


def audited_clear(comments: Sequence[Mapping[str, Any]], head: str) -> bool:
    """The latest verdict line (as the forge adapter shows it: only the auditor's or the owner's
    CLEAR survives) is a CLEAR of exactly `head`. No reviewed CLEAR, no PR code on the box."""
    last = None
    for c in comments:
        for m in _VERDICT.finditer(str(c.get("body") or "")):
            last = (m.group(1), m.group(2))
    return last == ("CLEAR", head)


#: THE FAST PATH (zuck 2026-11-25 18:53Z; Audit design check 18:53Z, HOLD H1/H2 19:08Z). A CLEARed
#: PR runs only the two KEPT money gates before merge -- the risk suites and replay-shadow -- each
#: capped at ten minutes. Impacted tests and coverage no longer gate (the full suite still runs
#: after merge, informational). A failure counts as a box defect that does not block ONLY when it
#: is env-classed (delivery_leadtime.cause), produced no pytest result line, did not exit 1 and
#: was not a pytest-timeout hang ("+++ Timeout +++" always blocks: a hang in money code is red).
#: QUANT_FORGE_FULL_GATING=1 restores the old pre-merge checks, here and in audit_gate.
FULL_GATING_ENV = "QUANT_FORGE_FULL_GATING"
RISK_CONTEXT = "risk-invariants"
REPLAY_CONTEXT = "replay-shadow"
FAST_TIMEOUT_S = 600
FAST_RISK_TIMEOUT_S = 600  # = FAST_TIMEOUT_S (a literal: it is a knob, boot r17)
#: (boot r15, 2026-11-26) replay-shadow is 90 scenarios x 2 trees = 180 fresh child processes.
#: Measured 172 s on a Linux build box with its research legs failing fast; on the trading box
#: every fast-path replay today (#4, #9, #13, #126, #127, #128) hit the 600 s cap, so no CLEARed
#: PR could go green and 0 of 148 merged. The cap is replay_job's own pre-fast-path default.
#: The gate is unchanged: a replay that times out still blocks; only its budget is realistic.
FAST_REPLAY_TIMEOUT_S = 3600
_RESULT_LINE = re.compile(r"\b\d+ (passed|failed|errors?)\b")
_RC = re.compile(r"rc=(\d+)")


def fast_path() -> bool:
    return os.environ.get(FULL_GATING_ENV, "").strip().lower() not in {"1", "true", "yes"}


def env_only(why: str) -> bool:
    """A red that is a box defect, not the code: env-classed, no test result, not rc 1, no hang."""
    rc = _RC.search(why or "")
    return (delivery_leadtime.cause(why) == "env" and not _RESULT_LINE.search(why or "")
            and "+++ Timeout +++" not in (why or "") and not (rc and rc.group(1) == "1"))


def _fast(ok: bool, why: str) -> tuple[bool, str]:
    if not ok and env_only(why):
        return True, f"a box defect, not the code (env, does not block): {why}"
    return ok, why


def fast_risk(cfg: Config, root: Path, base: str, head: str) -> tuple[bool, str]:
    return _fast(*risk_job(cfg, root, base, head, suite_timeout_s=FAST_TIMEOUT_S))


def fast_replay(cfg: Config, base: str, head: str, changed: Sequence[str]) -> tuple[bool, str]:
    return _fast(*replay_job(cfg, base, head, changed, timeout_s=FAST_REPLAY_TIMEOUT_S))


def pr_order(prs: Sequence[Mapping[str, Any]]) -> list[Mapping[str, Any]]:
    """Release trains first (they gate adoption), then OLDEST FIRST: the forge lists newest
    first, so a steady inflow of new packets would keep the first-queued fix (11-20: the drop
    pull, PR #1) waiting behind every later one."""
    def key(p: Mapping[str, Any]) -> tuple[int, int]:
        ref = str((p.get("head") or {}).get("ref") or "")
        return (0 if _TRAIN.search(ref) else 1, int(p.get("number") or 0))
    return sorted(prs, key=key)


#: ONE PR per pass (11-20..11-26) at 1-2 h a pass left 86 open PRs days from their checks.
#: (boot r20) PRs are now checked IN PARALLEL and CONTINUOUSLY: every CLEARed head without an
#: answer is started as soon as a slot is free, and the stage re-lists the forge as slots free,
#: so a PR imported mid-pass starts within PR_RELIST_S instead of waiting a whole pass. Each
#: check is its own worktree and its own CI-worker jobs (the worker runs them concurrently).
#: The stage stops STARTING checks after PR_TICK_BUDGET_S; checks in hand always finish.
PR_TICK_BUDGET_S = 10800
PR_RELIST_S = 60
#: Concurrent PR checks: a third of the cores, at most 6, at least 1 (each replay is one
#: below-normal process tree; the trading terminal and gateway run at normal priority).
PR_PARALLEL_MAX = 6
_TRAIN = re.compile(r"(^|/)(release[-_])?train[-_]?\d", re.I)


def pr_parallel(cores: int | None = None) -> int:
    n = cores if cores is not None else (os.cpu_count() or 1)
    return max(1, min(PR_PARALLEL_MAX, n // 3))


def _eligible(f: forge_api.Forge, prs: Sequence[Mapping[str, Any]],
              skip: set[str]) -> list[Mapping[str, Any]]:
    """`prs` arrive in pr_order already (pr_tick sorts: pr_order's one named caller)."""
    out = []
    for p in prs:
        head = str((p.get("head") or {}).get("sha") or "")
        if not head or head in skip:
            continue
        if checked(f.gh(f"repos/x/y/commits/{head}/check-runs")["check_runs"]):
            continue
        if not GUARD_LIVE and not audited_clear(
                f.gh(f"repos/x/y/issues/{p.get('number')}/comments"), head):
            continue  # Audit MF-2 (r23: head code runs only as quantci, Audit D1)
        out.append(p)
    return out


def check_pr(cfg: Config, p: Mapping[str, Any], hold: Hold | None = None) -> str:
    """One PR's box checks, posted as statuses, inside a reservation `hold` from RES (pr_tick
    takes it before the check starts and releases it after)."""
    if hold is None:
        hold, why = RES.take(cfg, 1 if fast_path() else None, FAST_CHECK_WORKTREES)
        if hold is None:
            return f"PR #{p.get('number')} waits: {why}"
        try:
            return check_pr(cfg, p, hold)
        finally:
            RES.release(hold)
    head = str((p.get("head") or {}).get("sha") or "")
    base = git(cfg, "merge-base", f"refs/heads/{LIVE}", head)
    changed = [c for c in git(cfg, "diff", "--name-only", base, head).splitlines() if c]
    if GUARD_LIVE:
        return guard_check(cfg, p, base, head, changed)
    if DIRECT_LIVE:
        return direct_check(cfg, p, base, head, changed)
    with worktree(cfg, head) as root:
        if fast_path():
            rok, rwhy = fast_risk(cfg, root, base, head)
            post(cfg, head, "success" if rok else "failure", f"box: {rwhy}", (RISK_CONTEXT,))
            sok, swhy = fast_replay(cfg, base, head, changed)
            post(cfg, head, "success" if sok else "failure", f"box: {swhy}", (REPLAY_CONTEXT,))
            return (f"PR #{p.get('number')}: fast path, risk {'ok' if rok else 'FAIL'}; "
                    f"replay {'ok' if sok else 'FAIL'}")
        sel = impacted.select(root, changed)
        if sel == [] and all(c.endswith(impacted.INERT_SUFFIXES) for c in changed):
            post(cfg, head, "success", "box CI: documents and images only (fast lane)",
                 (*GATING, "risk-invariants", "replay-shadow"))
            return f"PR #{p.get('number')}: fast lane"
        if sel == []:
            post(cfg, head, "success", "box CI: no change any test can observe")
        n = hold.workers   # the shared reservation's grant (Audit MF1), never a fresh sample
        passed, scope = True, "no observable test"
        if sel != []:
            post(cfg, head, "pending", f"box CI running on {n} idle cores")
            passed, what = run_tests(cfg, root, sel, n, f"pr{p.get('number')}_{head[:12]}")
            scope = ("full suite" if sel == impacted.ALL
                     else f"{len(sel)} impacted test file(s)")
            post(cfg, head, "success" if passed else "failure",
                 f"box CI, {scope}: {what}. Full suite runs after merge; release needs it "
                 "green.")
        rok, rwhy = risk_job(cfg, root, base, head)
        post(cfg, head, "success" if rok else "failure", f"box: {rwhy}", ("risk-invariants",))
        sok, swhy = replay_job(cfg, base, head, changed)
        post(cfg, head, "success" if sok else "failure", f"box: {swhy}", ("replay-shadow",))
    return (f"PR #{p.get('number')}: {'pass' if passed else 'FAIL'} ({scope}); "
            f"risk {'ok' if rok else 'FAIL'}; replay {'ok' if sok else 'FAIL'}")


#: Run in LIVE's (the merge base's) own checkout by the CI worker: which changed files are money
#: path, by the same classifier replay-shadow uses (MONEY_PATH directories, the entry points'
#: import closure, every script unless a reviewed exception). Prints one JSON list.
_MONEY_PROBE = (
    "import json, sys; from pathlib import Path; sys.path.insert(0, 'ops/release');"
    "import replay_shadow as r; b, h = Path('.'), Path(sys.argv[2]);"
    "c = r.import_closure(b) | r.import_closure(h); ex = r.exempt_scripts((b, h), c);"
    "ch = Path(sys.argv[1]).read_text(encoding='utf-8').split();"
    "print('MONEY=' + json.dumps(sorted(f for f in ch if r.is_money(f, c, exempt=ex))))")


def money_changes(cfg: Config, base_root: Path, head_root: Path,
                  changed: Sequence[str]) -> tuple[list[str] | None, str]:
    """The changed files that are money path, or None when that could not be measured (which the
    caller treats as money: an unmeasured diff never skips the risk check)."""
    lst = cfg.work / f"money_{uuid_hex()}.txt"
    try:
        lst.write_text("\n".join(sorted(set(changed))) + "\n", encoding="utf-8")
        rc, out = _run_untrusted(cfg, [cfg.python, "-I", "-c", _MONEY_PROBE, str(lst),
                                       str(head_root)], cwd=base_root, timeout=900)
    finally:
        lst.unlink(missing_ok=True)
    m = re.search(r"^MONEY=(\[.*\])\s*$", out or "", re.M)
    if rc != 0 or not m:
        return None, f"money path UNMEASURED (rc={rc}): {(out or '').strip()[-120:]}"
    try:
        got = json.loads(m.group(1))
    except ValueError:
        return None, "money path UNMEASURED: unreadable classifier answer"
    if not isinstance(got, list):
        return None, "money path UNMEASURED: unreadable classifier answer"
    return [str(f) for f in got], f"{len(got)} money-path file(s) of {len(set(changed))}"


def uuid_hex() -> str:
    import uuid
    return uuid.uuid4().hex[:12]


def direct_check(cfg: Config, p: Mapping[str, Any], base: str, head: str,
                 changed: Sequence[str]) -> str:
    """(boot r21) The ONE box check of direct live: the risk invariants, run only when the diff
    touches the money path. A diff that does not gets a success that says so, with the count."""
    n = p.get("number")
    with worktree(cfg, base) as b, worktree(cfg, head) as root:
        money, mwhy = money_changes(cfg, b, root, changed)
        if money == []:
            post(cfg, head, "success",
                 f"box: direct live, no money-path file changed ({mwhy}): no check applies",
                 (RISK_CONTEXT,))
            return f"PR #{n}: direct live, not money path"
        rok, rwhy = risk_job(cfg, root, base, head, suite_timeout_s=FAST_RISK_TIMEOUT_S)
        rok, rwhy = _fast(rok, rwhy)
        post(cfg, head, "success" if rok else "failure", f"box: {rwhy} [{mwhy}]",
             (RISK_CONTEXT,))
    return f"PR #{n}: direct live, money path ({mwhy}), risk {'ok' if rok else 'FAIL'}"


# ------------------------------------------------------------------------------ boot r23
GUARD_FILES = ("guard.py", "trust_check.py", "TRUST_SET.json")


def guard_dir(cfg: Any) -> Path:
    return Path(getattr(cfg, "guard_dir", None) or guard.GUARD_DIR)


def guard_id(cfg: Any) -> str:
    """The hash a verdict must carry: this loop's own guard and the PINNED checker and policy."""
    tc = getattr(cfg, "trust_checker", None)
    files = [HERE / "guard.py"]
    if tc:
        files += [Path(tc), Path(tc).parent / "TRUST_SET.json"]
    return guard.guard_hash(files)


def pinned_trust(cfg: Any, base: str, head: str) -> tuple[bool, str, str]:
    """(allowed, class, why) from the PINNED checker, the one the door also runs. Fails closed."""
    try:
        import importlib.util
        spec = importlib.util.spec_from_file_location("_guard_trust", cfg.trust_checker)
        assert spec is not None and spec.loader is not None
        tc = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(tc)
        pin = json.loads(Path(cfg.trust_pin).read_text(encoding="utf-8"))
        pol = tc.load_policy((Path(cfg.trust_checker).parent / "TRUST_SET.json")
                             .read_text(encoding="utf-8"))
        ok, cls, why, _t = tc.verdict(tc.strict_git("git", "-C", str(cfg.bare)), base, head,
                                      pin, pol)
        return bool(ok), str(cls), str(why)
    except Exception as exc:
        return False, "TRUST", f"trust UNMEASURED ({type(exc).__name__}: {str(exc)[:120]})"


def _show(cfg: Any, sha: str, path: str) -> str | None:
    try:
        return git(cfg, "show", f"{sha}:{path}")
    except Exception:
        return None


_SMOKE_PROBE = ("import sys; from pathlib import Path; sys.path.insert(0, '.');"
                "from libs.ops import adopt_guard as g; rc, d = g.smoke(Path('.'));"
                "print('SMOKE=' + str(d.get('decision')) + ' ' + str(d.get('reason') or ''));"
                "raise SystemExit(rc)")


def smoke_job(cfg: Config, root: Path) -> tuple[bool, str]:
    rc, out = _run_untrusted(cfg, [cfg.python, "-I", "-c", _SMOKE_PROBE], cwd=root, timeout=600)
    m = re.search(r"^SMOKE=(.*)$", out or "", re.M)
    said = m.group(1) if m else ""
    return (rc == 0 and said.startswith("SMOKE_OK"),
            f"smoke rc={rc}: {(said or (out or '').strip()[-120:])[:160]}")


def _held_by_audit(cfg: Config, n: Any, head: str) -> bool:
    """An Auditor's or the owner's latest verdict line names this head as HOLD."""
    try:
        comments = _forge(cfg, forge_api.BOX_CI_USER).gh(f"repos/x/y/issues/{n}/comments")
    except Exception:
        return True  # unreadable: a HOLD may be there
    last = None
    for c in comments or []:
        for m in _VERDICT.finditer(str(c.get("body") or "")):
            last = (m.group(1), m.group(2))
    return last == ("HOLD", head)


def guard_check(cfg: Config, p: Mapping[str, Any], base: str, head: str,
                changed: Sequence[str]) -> str:
    """(boot r23) The guard's checks for one PR head; the verdict file is the pen."""
    n = p.get("number")
    gid = guard_id(cfg)
    trust = pinned_trust(cfg, base, head)
    with worktree(cfg, base) as b, worktree(cfg, head) as root:
        money, mwhy = money_changes(cfg, b, root, changed)
        scan = changed if money is None else money
        static = guard.static_problems(
            (c, _show(cfg, base, c), _show(cfg, head, c)) for c in scan
            if c.endswith(".py") and not c.startswith("tests/"))
        raises = guard.ceiling_raises(_show(cfg, base, guard.CEILINGS),
                                      _show(cfg, head, guard.CEILINGS))
        risk = smoke = None
        if money != [] and trust[1] != "REFUSE":
            risk = risk_job(cfg, root, base, head, suite_timeout_s=FAST_RISK_TIMEOUT_S)
            if risk[0]:
                smoke = smoke_job(cfg, root)
    gd = guard_dir(cfg)
    v = guard.decide(head, base, trust=trust, static=static, raises=raises, money=money,
                     risk=risk, smoke=smoke, merges_today=guard.money_merges_today(gd),
                     rolled_back=guard.rolled_back_heads(gd), held=_held_by_audit(cfg, n, head),
                     guard=gid)
    guard.write_verdict(gd, v)
    post(cfg, head, "success" if v.ok else "failure", f"box guard {v.cls}: {v.why} [{mwhy}]",
         (guard.CONTEXT,))
    # the legacy (owner) path reads risk-invariants: green only for a PASS, or for a TRUST-class
    # head whose risk run passed (or was not needed), so the owner's AUTHORIZE TRUST can merge it
    owner_ok = v.cls == "TRUST" and (risk is None or risk[0]) and (smoke is None or smoke[0])
    post(cfg, head, "success" if v.ok or owner_ok else "failure",
         f"box guard {v.cls}: {v.why}"[:250], (RISK_CONTEXT,))
    return f"PR #{n}: guard {v.cls} ({mwhy})"


def guard_merge_tick(cfg: Config) -> str:
    """(boot r23) Merge every open PR whose head holds this guard's PASS. Pinned to the head sha;
    a money PR behind LIVE is brought up first (its new head is checked again)."""
    f = _forge(cfg, "merge-gate")
    gd, gid = guard_dir(cfg), guard_id(cfg)
    live = live_head(cfg)
    out = []
    for p in f.gh(f"repos/{forge_api.FORGE_REPO}/pulls?state=open&base={LIVE}") or []:
        n, head = p.get("number"), str((p.get("head") or {}).get("sha") or "")
        if not str((p.get("head") or {}).get("ref") or "").startswith("claude/"):
            continue
        v = guard.read_verdict(gd, head, gid)
        if v is None:
            continue
        comments = f.gh(f"repos/x/y/issues/{n}/comments") or []
        if _held_by_audit(cfg, n, head):
            out.append(f"#{n} HOLD")
            continue
        need, nwhy = seat_required(cfg)
        if need and not audited_clear(comments, head):
            out.append(f"#{n} guard PASS, waits for the Auditor's CLEAR ({nwhy})")
            continue
        behind = _run(["git", "-C", str(cfg.bare), "merge-base", "--is-ancestor", live, head],
                      timeout=120)[0] != 0
        if behind and v.money:
            f.gh(f"repos/x/y/pulls/{n}/update-branch", "-X", "PUT", data={})
            out.append(f"#{n} brought up to LIVE; checked again")
            continue
        f.gh(f"repos/x/y/pulls/{n}/merge", "-X", "PUT",
             data={"sha": head, "merge_method": "merge",
                   "commit_title": f"Merge #{n} (box guard PASS {head[:9]})"})
        merged = live_head(cfg)
        guard.record_merge(gd, n, head, merged, v.money)
        live = merged
        out.append(f"#{n} merged ({'money' if v.money else 'not money'})")
    return "; ".join(out) or "nothing to merge"


def _held(hold: Hold, fn: Callable[..., str], cfg: Config, p: Mapping[str, Any]) -> str:
    try:
        return fn(cfg, p, hold)
    finally:
        RES.release(hold)


def pr_tick(cfg: Config, budget_s: float = PR_TICK_BUDGET_S, *,
            parallel: int | None = None, relist_s: float = PR_RELIST_S) -> str:
    import concurrent.futures as cf
    f = _forge(cfg, forge_api.BOX_CI_USER)
    k = parallel or pr_parallel()
    done: list[str] = []
    started: set[str] = set()
    until = time.monotonic() + budget_s
    running: dict[cf.Future[str], str] = {}
    with cf.ThreadPoolExecutor(max_workers=k, thread_name_prefix="pr-check") as pool:
        while True:
            # the stage stops STARTING after its budget, but one check always runs
            waited = ""
            if (time.monotonic() < until or not started) and len(running) < k:
                prs = pr_order(f.gh(f"repos/{forge_api.FORGE_REPO}/pulls?state=open&base={LIVE}")
                               or [])
                for p in _eligible(f, prs, started)[:k - len(running)]:
                    hold, why = RES.take(cfg, 1 if fast_path() else None, FAST_CHECK_WORKTREES)
                    if hold is None:
                        waited = f"PR #{p.get('number')} waits: {why}"
                        break  # the box is full: no further check starts until one finishes
                    head = str((p.get("head") or {}).get("sha") or "")
                    started.add(head)
                    running[pool.submit(_held, hold, check_pr, cfg, p)] = f"PR #{p.get('number')}"
            if not running:
                if waited:
                    done.append(waited)
                break
            fin, _ = cf.wait(list(running), timeout=relist_s, return_when=cf.FIRST_COMPLETED)
            if GUARD is not None:
                GUARD.beat("pr")
            for fu in fin:
                name = running.pop(fu)
                try:
                    done.append(fu.result())
                except Exception as exc:  # one PR failing never stops the others
                    done.append(f"{name}: ERROR {type(exc).__name__}: {str(exc)[:200]}")
    if time.monotonic() >= until and done:
        done.append("budget spent; the rest wait for the next pass")
    return "; ".join(done)[:2000] if done else "no PR waiting for checks"


def full_tick(cfg: Config, live: str) -> str:
    with STATE_LOCK:
        state = box_ci.load_state(cfg.state)
        plan = box_ci.plan_full_run(state, live)
        if plan.pending:
            state["full_pending"] = plan.pending
        if not plan.start:
            box_ci.save_state(cfg.state, state)
            return plan.why
    hold, why = RES.take(cfg, None, 1)   # every spare worker, from the shared reservation
    if hold is None:
        return f"full run waits: {why}"
    n = hold.workers
    with STATE_LOCK:
        state = box_ci.load_state(cfg.state)
        state["full_running"] = plan.start
        box_ci.save_state(cfg.state, state)
    passed, why, counts = False, "the run did not finish", ""
    try:
        with worktree(cfg, plan.start) as root:
            law_rc, _law = _run([cfg.python, "scripts/run_law_gate.py", "--laws-only"], cwd=root,
                                timeout=3600, idle=True)
            passed, what = run_tests(cfg, root, impacted.ALL, n, f"full_{plan.start[:12]}")
            passed = passed and law_rc == 0
            why = f"law gate rc={law_rc}; {what}"
            # (r20) the per-test outcomes, before the checkout (and its junit file) goes
            nodes = box_ci.junit_outcomes(root / "box-junit.xml")
            nodes["law_gate_rc"] = law_rc
            box_ci.save_full_nodes(cfg.state, plan.start, nodes)
            if "collected" in nodes:
                counts = (f" [{nodes['collected']} collected, {nodes['failed']} failed, "
                          f"{nodes['error']} error, {nodes['skipped']} skipped]")
    finally:
        with STATE_LOCK:
            state = box_ci.load_state(cfg.state)
            state["full_running"] = None
            if state.get("full_pending") == plan.start:
                state["full_pending"] = None
            box_ci.record(state, head=plan.start, kind=box_ci.FULL, ok=passed, why=why + counts)
            box_ci.save_state(cfg.state, state)
        RES.release(hold)
    return f"full {plan.start[:9]}: {'GREEN' if passed else 'RED'} ({why}){counts}"


def promote_tick(cfg: Config) -> str:
    state = box_ci.load_state(cfg.state)

    def anc(a: str, b: str) -> bool:
        return _run(["git", "-C", str(cfg.bare), "merge-base", "--is-ancestor", a, b])[0] == 0

    if DIRECT_LIVE:
        head = box_ci.direct_promotable(state, git(cfg, "rev-parse", f"refs/heads/{LIVE}"), anc,
                                        lambda a, b: git(cfg, "diff", "--name-only", a, b, "--",
                                                         ".", f":(exclude){RELEASE_JSON}"))
    else:
        head = box_ci.promotable(state, anc)
    if not head:
        return "nothing new to promote"
    seal = seal_and_push(cfg, head)
    if not seal:
        return f"seal of {head[:9]} did not land; promote waits"
    with worktree(cfg, seal) as root:
        rc, out = _run([cfg.python, "scripts/release_promotion.py", "promote", "--target", seal,
                        "--tested", head, "--run-id", f"box-{datetime.now(UTC):%Y%m%dT%H%M%SZ}",
                        "--remote", cfg.remote(), "--root", str(root)],
                       cwd=root, env=cfg.git_env("release-authority"), timeout=900)
    if rc == 0:
        state = box_ci.load_state(cfg.state)
        state["promoted"] = head
        box_ci.save_state(cfg.state, state)
    last = out.strip().splitlines()[-1][:160] if out.strip() else ""
    adopt = start_adoption() if rc == 0 and DIRECT_LIVE else ""
    return f"promote {head[:9]}: rc={rc} {last}{adopt}"


def start_adoption() -> str:
    """(r21) Start the box's own adoption task now instead of waiting for its hourly slot. The
    task (Adopt-And-Seal.ps1) keeps every one of its own checks; this only moves its start."""
    if os.name != "nt":
        return ""
    rc, out = _run(["schtasks.exe", "/Run", "/TN", ADOPT_TASK], timeout=60)
    return f"; adoption {ADOPT_TASK} started" if rc == 0 else (
        f"; adoption start refused rc={rc}: {out.strip()[-120:]} (its hourly slot still runs)")


def seal_and_push(cfg: Config, tested: str) -> str | None:
    """ci.yml's seal job, on the box: RELEASE.json alone, committed on the tested head and landed
    on LIVE (merged into a moved tip as history only). Returns the seal commit or None."""
    env = cfg.git_env("merge-gate")
    with worktree(cfg, tested) as root:
        rc, _ = _run([cfg.python, "scripts/release_manifest.py", "--seal", "--tested",
                      "--if-needed", "--by", "box-ci"], cwd=root, timeout=600)
        if rc != 0:
            return None
        if _run(["git", "diff", "--quiet", "--", RELEASE_JSON], cwd=root)[0] == 0:
            return tested  # already the sealed code
        for a in (["add", RELEASE_JSON],
                  ["-c", "user.name=box-ci", "-c", "user.email=box-ci@box.invalid", "commit",
                   "-q", "-m", f"seal release {tested[:12]}"]):
            if _run(["git", *a], cwd=root)[0] != 0:
                return None
        seal = _run(["git", "rev-parse", "HEAD"], cwd=root)[1].strip()
        for _attempt in range(5):
            if _run(["git", "fetch", "-q", cfg.remote(), f"refs/heads/{LIVE}"], cwd=root,
                    env=env)[0] != 0:
                return None
            tip = _run(["git", "rev-parse", "FETCH_HEAD"], cwd=root)[1].strip()
            if _run(["git", "merge-base", "--is-ancestor", seal, tip], cwd=root)[0] == 0:
                return seal
            push = seal
            if tip != tested:
                _run(["git", "checkout", "-q", "--detach", tip], cwd=root)
                _run(["git", "merge", "-q", "--no-ff", "--no-commit", seal], cwd=root)
                _run(["git", "checkout", seal, "--", RELEASE_JSON], cwd=root)
                _run(["git", "add", RELEASE_JSON], cwd=root)
                if _run(["git", "diff", "--name-only", "--diff-filter=U"], cwd=root)[1].strip():
                    return None
                if _run(["git", "-c", "user.name=box-ci", "-c", "user.email=box-ci@box.invalid",
                         "commit", "-q", "--no-edit", "-m",
                         f"Merge seal release {tested[:12]} into {LIVE} (history only)"],
                        cwd=root)[0] != 0:
                    return None
                extra = _run(["git", "diff", "--name-only", tip, "HEAD", "--", ".",
                              f":(exclude){RELEASE_JSON}"], cwd=root)[1].strip()
                if extra:
                    return None
                push = _run(["git", "rev-parse", "HEAD"], cwd=root)[1].strip()
            if _run(["git", "push", "-q", cfg.remote(), f"{push}:refs/heads/{LIVE}"], cwd=root,
                    env=env)[0] == 0:
                return seal
    return None


#: THE SIGN TRAIN ON THE BOX (guardian gap 7, 2026-11-24). A sealed judge file (the gauntlet,
#: the promoter, the rails) may move only with a re-signed IMMUTABLE_MANIFEST and a QB-002
#: re-pin, and since D-20261027-003 the AUDIT signs: scripts/sign_train.py signs a moved file
#: only when a CLEAR row for its exact sha256 is committed in SEAL_CLEARS.jsonl. Its only clock
#: was ops/box/sign_train_leg.ps1, which pushes to GitHub -- gone with the suspension -- and a
#: cloud clone is shallow, which the train refuses. So no sealed change could ever be signed,
#: and a merged one would hold every release red. This stage runs the SAME train at LIVE's head,
#: in a clean checkout of the forge's full history, and fast-forwards LIVE by the train's one
#: commit. It adds no signing rule of its own: every refusal of the train stands, and the stage
#: pushes only a commit that sits directly on LIVE and touches only the two files the train
#: writes. Checked once per LIVE head; a checkout is made only when SEAL_CLEARS.jsonl or a
#: sealed file moved since the last head it checked.
SIGN_TRAIN = "scripts/sign_train.py"
SIGNED_PATHS = ("desks/mt5/data/IMMUTABLE_MANIFEST.json", "desks/mt5/research/quantbench.py")
SIGN_TRIGGERS = ("desks/mt5/data/SEAL_CLEARS.jsonl", "desks/mt5/scripts/external_gauntlet.py",
                 "desks/mt5/research/promoter.py", "libs/portfolio/allocator_proof.py",
                 "libs/portfolio/rails.py")


_SIGN_LINE = re.compile(r'^\s*"(to|signed_by)": "[^"]*",$')
_SIGN_TOP = frozenset({"files", "signed_utc", "signed_by"})
_HASH16 = re.compile(r"[0-9a-f]{16}")


def sign_diff_problems(old_manifest: str, new_manifest: str, old_qb: str, new_qb: str,
                       clears: str) -> list[str]:
    """What the train's commit may change, checked by the box itself before it pushes (Audit
    should-fix on 389704797): the manifest's file hashes ONLY for paths whose new hash has a CLEAR
    row in SEAL_CLEARS.jsonl at LIVE, its signer stamp, and nothing else -- the record wall, the
    rules and the rotation signers byte-identical -- and in quantbench.py only rotation "to" and
    "signed_by" lines. [] when the commit is exactly a sign."""
    out: list[str] = []
    try:
        old, new = json.loads(old_manifest), json.loads(new_manifest)
    except ValueError as exc:
        return [f"manifest unreadable: {exc}"]
    if not (isinstance(old, dict) and isinstance(new, dict)):
        return ["manifest is not an object"]
    for k in sorted((set(old) | set(new)) - _SIGN_TOP):
        if json.dumps(old.get(k), sort_keys=True) != json.dumps(new.get(k), sort_keys=True):
            out.append(f"manifest key {k!r} changed (record wall, rules and signers are fixed)")
    of, nf = old.get("files") or {}, new.get("files") or {}
    if set(of) != set(nf):
        out.append(f"sealed file set changed: {sorted(set(of) ^ set(nf))}")
    cleared: dict[str, set[str]] = {}
    for line in clears.splitlines():
        try:
            row = json.loads(line)
        except ValueError:
            continue
        if isinstance(row, dict) and row.get("verdict") == "CLEAR":
            cleared.setdefault(str(row.get("path")), set()).add(str(row.get("sha256")))
    for path in sorted(p for p in set(of) & set(nf) if of[p] != nf[p]):
        h = str(nf[path])
        if not _HASH16.fullmatch(h):
            out.append(f"{path} re-signed to {h!r}, not 16 lower-case hex")
        elif not any(str(s).startswith(h) for s in cleared.get(path, ())):
            out.append(f"{path} re-signed to {h} with no CLEAR row for it")
    # Only REPLACEMENTS of existing rotation lines, pairwise: each changed old line is a
    # to/signed_by line and is replaced by a line of the same key; nothing added or removed.
    sm = difflib.SequenceMatcher(a=old_qb.splitlines(), b=new_qb.splitlines(), autojunk=False)
    for op, i1, i2, j1, j2 in sm.get_opcodes():
        if op == "equal":
            continue
        olds, news = sm.a[i1:i2], sm.b[j1:j2]
        if op != "replace" or len(olds) != len(news):
            out.append(f"quantbench.py {op} of {i2 - i1} line(s) for {j2 - j1}: only paired "
                       f"to/signed_by replacements are a sign")
            continue
        for o, n in zip(olds, news, strict=True):
            mo, mn = _SIGN_LINE.match(o), _SIGN_LINE.match(n)
            if not (mo and mn and mo.group(1) == mn.group(1)):
                out.append(f"quantbench.py line outside a rotation's to/signed_by: {n[:120]}")
    return out


def sign_tick(cfg: Config, live: str) -> str:
    state = box_ci.load_state(cfg.state)
    last = str(state.get("sign_checked") or "")
    if last == live:
        return f"LIVE {live[:12]} already checked for a sign"
    if last:
        rc, moved = _run(["git", "-C", str(cfg.bare), "diff", "--name-only", last, live, "--",
                          *SIGN_TRIGGERS], timeout=300)
        if rc == 0 and not moved.strip():
            state["sign_checked"] = live
            box_ci.save_state(cfg.state, state)
            return f"LIVE {live[:12]}: no CLEAR row or sealed file moved; nothing to sign"
    who = {"GIT_AUTHOR_NAME": "box-sign", "GIT_AUTHOR_EMAIL": "box-sign@box.invalid",
           "GIT_COMMITTER_NAME": "box-sign", "GIT_COMMITTER_EMAIL": "box-sign@box.invalid"}
    env = {**cfg.git_env("merge-gate"), **who}
    with worktree(cfg, live) as root:
        if not (root / SIGN_TRAIN).exists():
            state["sign_checked"] = live
            box_ci.save_state(cfg.state, state)
            return f"LIVE {live[:12]} has no {SIGN_TRAIN}"
        rc, out = _run([cfg.python, SIGN_TRAIN, "--target", live], cwd=root,
                       env={**os.environ, **who}, timeout=1800)
        said = (out.strip().splitlines() or [""])[-1][:200]
        head = _run(["git", "rev-parse", "HEAD"], cwd=root)[1].strip()
        if rc != 0 or head == live:
            state["sign_checked"] = live
            box_ci.save_state(cfg.state, state)
            return f"sign train at {live[:12]}: rc {rc}: {said}"
        parent = _run(["git", "rev-parse", "HEAD~1"], cwd=root)[1].strip()
        files = set(_run(["git", "diff", "--name-only", live, "HEAD"], cwd=root)[1].split())
        if parent != live or not files or files - set(SIGNED_PATHS):
            return (f"REFUSED to push the sign at {head[:12]}: parent {parent[:12]}, "
                    f"files {sorted(files)}")

        def show(rev: str, path: str) -> str:
            # Whole file (_run keeps only the tail); an unreadable blob reads "" and fails the
            # check closed rather than passing it.
            p = subprocess.run(["git", "show", f"{rev}:{path}"], cwd=root, capture_output=True,
                               text=True, encoding="utf-8", errors="replace", check=False,
                               timeout=300)
            return p.stdout if p.returncode == 0 else ""
        man, qb = SIGNED_PATHS
        bad = sign_diff_problems(show(live, man), show("HEAD", man), show(live, qb),
                                 show("HEAD", qb), show(live, SIGN_TRIGGERS[0]))
        if bad:
            return f"REFUSED to push the sign at {head[:12]}: " + "; ".join(bad[:4])
        if _run(["git", "push", "-q", cfg.remote(), f"{head}:refs/heads/{LIVE}"], cwd=root,
                env=env)[0] != 0:
            return f"signed {head[:12]} on {live[:12]} but the push was refused; next pass retries"
    state["sign_checked"] = head
    box_ci.save_state(cfg.state, state)
    return f"SIGNED: {said} -> {head[:12]} on {LIVE}"


def inbox_tick(cfg: Config) -> str:
    if cfg.inbox is None:
        return "no inbox configured"

    def run_git(*args: str, push_as: str | None = None) -> tuple[int, str]:
        if push_as:
            _push, head, ref = args
            return _run(["git", "-C", str(cfg.bare), "push", "-q", cfg.remote(), f"{head}:{ref}"],
                        env=cfg.git_env(push_as), timeout=600)
        return _run(["git", "-C", str(cfg.bare), *args], timeout=600)

    rows = inbox.drain(cfg.inbox, git=run_git, api=_forge(cfg, "claude").t)
    rows += inbox.drain_verdicts(cfg.inbox / "verdicts", api=_forge(cfg, "auditor").t)
    return "; ".join(rows) or "inbox empty"


def state_tick(cfg: Config) -> str:
    """Box state from ShadowSync's outbox onto claude/box-state (ops/box_git/state_publish.py)."""
    if cfg.state_outbox is None:
        return "no state outbox configured"
    who = {"NAME": "box-state", "EMAIL": "box-state@box.invalid"}
    ident = {**os.environ, **{f"GIT_{r}_{k}": v for r in ("AUTHOR", "COMMITTER")
                              for k, v in who.items()}}

    def git(args: Sequence[str]) -> tuple[int, str]:
        return _run(["git", "-c", "safe.directory=*", "-C", str(cfg.bare), *args], env=ident,
                    timeout=600)

    def push(sha: str, ref: str) -> tuple[int, str]:
        return _run(["git", "-C", str(cfg.bare), "push", "-q", cfg.remote(), f"{sha}:{ref}"],
                    env=cfg.git_env("claude"), timeout=600)

    def remote_tip(ref: str) -> str | None:
        """The branch tip on the forge, its objects fetched here (FETCH_HEAD only, no ref)."""
        rc, out = _run(["git", "-C", str(cfg.bare), "ls-remote", cfg.remote(), ref],
                       env=cfg.git_env("claude"), timeout=120)
        sha = out.split()[0] if rc == 0 and out.split() else ""
        if len(sha) != 40:
            return None
        _run(["git", "-C", str(cfg.bare), "fetch", "-q", cfg.remote(), ref],
             env=cfg.git_env("claude"), timeout=600)
        return sha

    return state_publish.publish(cfg.state_outbox, cfg.state.parent / state_publish.STATUS,
                                 git=git, push=push, remote_tip=remote_tip, live=LIVE)


def drop_tick(cfg: Config) -> str:
    """Pull new packets from the drop repository into the inbox (ops/box_git/drop_pull.py)."""
    if cfg.drop is None or cfg.inbox is None:
        return "no drop configured"
    return drop_pull.pull(cfg.drop, cfg.inbox, cfg.state.parent)


#: Lead time is re-measured at most this often (it reads every PR's comments and statuses).
LEADTIME_EVERY_S = 300  # (r20) the SLA alarm reads it: 5 min, not 30
LOOP_ALARM = "LOOP_ALARM.json"


def _production_commits(cfg: Config) -> list[tuple[datetime, str]]:
    rc, out = _run(["git", "-C", str(cfg.bare), "log", "--first-parent", "--format=%cI %H",
                    "refs/heads/production"])
    rows = []
    for line in out.splitlines() if rc == 0 else []:
        stamp, _, sha = line.strip().partition(" ")
        with contextlib.suppress(ValueError):
            rows.append((datetime.fromisoformat(stamp).astimezone(UTC), sha))
    return rows


def leadtime_tick(cfg: Config, now: datetime | None = None) -> str:
    """DELIVERY_LEADTIME.json beside LOOP_LAST.json (L16). Read only: forge GETs, git ancestry."""
    t = now or datetime.now(UTC)
    out = cfg.state.with_name(delivery_leadtime.REPORT)
    with contextlib.suppress(OSError, ValueError):
        last = json.loads(out.read_text(encoding="utf-8")).get("at")
        if last and (t - datetime.fromisoformat(last)).total_seconds() < LEADTIME_EVERY_S:
            return f"lead time fresh ({last})"
    f = _forge(cfg, forge_api.BOX_CI_USER)
    repo = f"/repos/{forge_api.FORGE_REPO}"
    prs = [p for p in f._all(f"{repo}/pulls?state=all")
           if (p.get("base") or {}).get("ref") == LIVE]
    comments = {int(p["number"]): f._all(f"{repo}/issues/{p['number']}/comments") for p in prs}
    statuses = {}
    for p in prs:
        sha = str((p.get("head") or {}).get("sha") or "")
        if re.fullmatch(r"[0-9a-f]{40}", sha):
            statuses[sha] = f._all(f"{repo}/commits/{sha}/statuses")

    def anc(a: str, b: str) -> bool:
        return _run(["git", "-C", str(cfg.bare), "merge-base", "--is-ancestor", a, b])[0] == 0

    doc = delivery_leadtime.build(
        prs, comments, statuses,
        full_results=box_ci.load_state(cfg.state).get("full_results") or [],
        production=_production_commits(cfg), adopted=None, is_ancestor=anc, now=t,
        direct=DIRECT_LIVE)
    box_ci.save_state(out, doc)
    s = doc["summary"]
    sl = s.get("sla") or {}
    alarm = cfg.state.with_name(LOOP_ALARM)
    with contextlib.suppress(OSError):
        if sl.get("ok", True):
            alarm.unlink(missing_ok=True)
        else:
            box_ci.save_state(alarm, {"at": doc.get("at"), "alarms": sl.get("alarms"),
                                      "breaches": sl.get("breaches")})
    flag = ("SLA ok" if sl.get("ok", True) else
            "SLA BREACH " + ",".join([a["alarm"] for a in sl.get("alarms") or []]
                                     + [f"{k}:{v['n']}" for k, v in
                                        (sl.get("breaches") or {}).items()]))
    return (f"lead time: {len(prs)} PR(s), backlog {s['built_not_live']['n']}, "
            f"p90 {s['lead_time_h']['p90']}h, bottleneck {s['bottleneck']}; {flag}")


#: (boot r20) THE LIGHT LOOP. Pickup, import, merge, sign and promote no longer wait for a whole
#: pass: the heavy stages (PR checks, the full suite) run in their own threads, and the light
#: stages repeat every LIGHT_EVERY_S while they run (11-26: a packet dropped at 01:10Z could not
#: be picked up before the ~02:35Z pass, because each 2 h pass ran drop and inbox once, at its
#: start). The pass ends when the heavy stages are done, after one last light round, so the
#: mover still sees one pass at a time and nothing outlives it.
LIGHT_EVERY_S = 90.0
LIGHT = ("drop", "inbox", "state", "gate", "sign", "promote", "leadtime")
HEAVY = ("pr", "full")


def heavy_stages() -> tuple[str, ...]:
    """(r21) direct live runs no full suite: the pr stage is the only heavy one."""
    return tuple(n for n in HEAVY if not (DIRECT_LIVE and n == "full"))


def _locked(fn: Callable[[], str]) -> str:
    with STATE_LOCK:
        return fn()


def _stages(cfg: Config) -> dict[str, Callable[[], str]]:
    return {"drop": lambda: drop_tick(cfg),
            "inbox": lambda: inbox_tick(cfg),
            "state": lambda: state_tick(cfg),
            "gate": lambda: gate_tick(cfg, live_head(cfg)),
            # sign and promote read-modify-write the CI state the full thread also writes
            "sign": lambda: _locked(lambda: sign_tick(cfg, live_head(cfg))),
            "pr": lambda: pr_tick(cfg),
            "full": lambda: full_tick(cfg, live_head(cfg)),
            "promote": lambda: _locked(lambda: promote_tick(cfg)),
            "leadtime": lambda: leadtime_tick(cfg)}


def _call(name: str, fn: Callable[[], str]) -> str:
    if GUARD is not None:
        GUARD.beat(name)
    try:
        return fn()
    except Exception as exc:  # one stage failing never stops the others
        return f"ERROR {type(exc).__name__}: {str(exc)[:300]}"


def tick(cfg: Config, *, light_every_s: float = LIGHT_EVERY_S,
         stages: Mapping[str, Callable[[], str]] | None = None,
         progress: Callable[[dict[str, Any]], None] | None = None) -> dict[str, Any]:
    out: dict[str, Any] = {"at": datetime.now(UTC).isoformat(timespec="seconds")}
    try:
        out["swept"] = sweep_stale(cfg)
    except Exception as exc:
        out["swept"] = f"ERROR {type(exc).__name__}: {str(exc)[:200]}"
    fns = dict(stages or _stages(cfg))
    timing: dict[str, Any] = {}

    def run(name: str) -> None:
        t0 = time.monotonic()
        res = _call(name, fns[name])
        t1 = time.monotonic()
        with STATE_LOCK:
            out[name] = res
            row = timing.setdefault(name, {"runs": 0, "s_total": 0.0, "s_max": 0.0})
            row["runs"] += 1
            row["s_total"] = round(row["s_total"] + t1 - t0, 1)
            row["s_max"] = round(max(row["s_max"], t1 - t0), 1)
            row["last_end"] = datetime.now(UTC).isoformat(timespec="seconds")

    # one light round first: a packet already in the drop is imported before any check starts
    for name in LIGHT:
        if name in fns:
            run(name)
    heavy = [threading.Thread(target=run, args=(n,), name=f"stage-{n}", daemon=True)
             for n in heavy_stages() if n in fns]
    for t in heavy:
        t.start()
    rounds = 1
    while any(t.is_alive() for t in heavy):
        for t in heavy:
            t.join(timeout=light_every_s / max(1, len(heavy)))
        if not any(t.is_alive() for t in heavy):
            break
        for name in LIGHT:
            if name in fns:
                run(name)
        rounds += 1
        if progress is not None:
            with STATE_LOCK, contextlib.suppress(Exception):
                progress({**out, "in_progress": True, "light_rounds": rounds,
                          "stage_timing": timing})
    for name in LIGHT:  # the heavy stages' answers are merged and promoted in this pass
        if name in fns:
            run(name)
    out["light_rounds"] = rounds + 1
    out["stage_timing"] = timing
    return out


def trust_status(cfg: Config) -> str:
    """LIVE's trust hash against the pin (Audit follow-up 3): a mismatch makes every merge wait,
    so it is reported every pass, never a silent stall. Read only."""
    if not cfg.trust_checker or not cfg.trust_pin:
        return "no trust boundary configured"
    try:
        import importlib.util
        spec = importlib.util.spec_from_file_location("_loop_trust", cfg.trust_checker)
        assert spec is not None and spec.loader is not None
        tc = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(tc)
        pin = json.loads(cfg.trust_pin.read_text(encoding="utf-8"))
        live = live_head(cfg)
        t = tc.t_hash(tc.strict_git("git", "-C", str(cfg.bare)), live)
        return (f"LIVE {live[:12]} trust {t[:12]} == pin" if t == pin.get("t_hash") else
                f"MISMATCH: LIVE {live[:12]} trust {t[:12]} != pin {str(pin.get('t_hash'))[:12]}"
                ": every merge waits")
    except Exception as exc:
        return f"trust status unmeasured ({type(exc).__name__}: {str(exc)[:120]})"


def live_head(cfg: Config) -> str:
    return git(cfg, "rev-parse", f"refs/heads/{LIVE}")


def main(argv: list[str] | None = None) -> int:
    import argparse
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--config", help="JSON with the Config fields")
    ap.add_argument("--ci-worker", metavar="JOBS", help="run as the unprivileged CI worker")
    a = ap.parse_args(argv)
    if a.ci_worker:
        print(f"ci worker ran {worker_pass(Path(a.ci_worker))} job(s)")
        return 0
    if not a.config:
        ap.error("--config is required")
    raw = json.loads(Path(a.config).read_text(encoding="utf-8"))
    cfg = Config(forge_url=raw["forge_url"], bare=Path(raw["bare"]), work=Path(raw["work"]),
                 tokens=Path(raw["tokens"]), ca=Path(raw["ca"]), state=Path(raw["state"]),
                 python=raw.get("python") or sys.executable,
                 inbox=Path(raw["inbox"]) if raw.get("inbox") else None,
                 boot=raw.get("boot") or None,
                 ci_jobs=Path(raw["ci_jobs"]) if raw.get("ci_jobs") else None,
                 trust_checker=Path(raw["trust_checker"]) if raw.get("trust_checker") else None,
                 trust_pin=Path(raw["trust_pin"]) if raw.get("trust_pin") else None,
                 drop=drop_pull.Drop(url=raw["drop"]["url"], key=Path(raw["drop"]["key"]),
                                     checkout=Path(raw["drop"]["checkout"]),
                                     branch=raw["drop"].get("branch") or "main")
                 if raw.get("drop") else None,
                 state_outbox=Path(raw["state_outbox"]) if raw.get("state_outbox") else None)
    global GUARD
    stall_file = cfg.state.with_name("LOOP_STALL.json")

    def _stalled(why: dict[str, Any]) -> None:
        why["at"] = datetime.now(UTC).isoformat(timespec="seconds")
        with contextlib.suppress(OSError):
            box_ci.save_state(stall_file, why)
        print(f"STALL: {json.dumps(why)}; ending this pass so the next trigger starts clean",
              file=sys.stderr, flush=True)
        os._exit(75)

    GUARD = StallGuard(float(raw.get("stall_s") or 2700.0), on_stall=_stalled)
    GUARD.watch()
    report = cfg.state.with_name("LOOP_LAST.json")
    doc = tick(cfg, progress=lambda d: box_ci.save_state(report, d))
    doc["trust"] = trust_status(cfg)
    box_ci.save_state(report, doc)
    print(json.dumps(doc))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
