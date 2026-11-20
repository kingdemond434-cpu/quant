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
  3. FULL    LIVE's head, coalesced (box_ci.plan_full_run): law gate + the whole suite.
  4. SEAL + PROMOTE  at the newest fully green head only (box_ci.promotable): RELEASE.json sealed
             and pushed to LIVE exactly as ci.yml's seal job did, then scripts/release_promotion.py
             promote (tag, production fast-forward, master) as the release-authority account.
             MT5-AdoptRelease then adopts production as it always has.

Disk floor and idle cores (box_ci) bind every test stage. Nothing here writes C:\\opt\\quant.
"""
from __future__ import annotations

import contextlib
import json
import os
import re
import shutil
import subprocess
import sys
from collections.abc import Iterator, Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
if str(HERE.parents[1]) not in sys.path:
    sys.path.insert(0, str(HERE.parents[1]))

from ops.box_git import box_ci, drop_pull, forge_api, impacted, inbox  # noqa: E402

LIVE = "claude/llm-auto-upgrade-verify-gcjac3"
GATING = ("quality", "mt5-money-path", "coverage-floor")
RELEASE_JSON = "desks/mt5/data/RELEASE.json"


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


def _run(argv: Sequence[str], *, cwd: Path | None = None, env: Mapping[str, str] | None = None,
         timeout: float = 3600, idle: bool = False) -> tuple[int, str]:
    kw: dict[str, Any] = box_ci.idle_priority_kwargs() if idle else {}
    try:
        p = subprocess.run(list(argv), cwd=cwd, env=dict(env) if env else None,
                           capture_output=True, text=True, encoding="utf-8", errors="replace",
                           timeout=timeout, check=False, **kw)
    except subprocess.TimeoutExpired:
        return 124, f"timed out after {timeout:.0f}s"
    except OSError as exc:
        return 127, f"{type(exc).__name__}: {exc}"
    return p.returncode, (p.stdout + p.stderr)[-4000:]


def git(cfg: Config, *args: str) -> str:
    rc, out = _run(["git", "-C", str(cfg.bare), *args], timeout=300)
    if rc != 0:
        raise RuntimeError(f"git {' '.join(args)}: {out.strip()[-300:]}")
    return out.strip()


@contextlib.contextmanager
def worktree(cfg: Config, sha: str) -> Iterator[Path]:
    cfg.work.mkdir(parents=True, exist_ok=True)
    # A checkout is a full tree: never make one below the disk floor (box 2026-11-20: CI
    # checkouts helped push the desk volume under its own 5 GB floor).
    ok, why = box_ci.disk_ok(shutil.disk_usage(cfg.work).free / 1024 ** 3)
    if not ok:
        raise RuntimeError(f"no checkout: {why}")
    d = box_ci.shared_dir(cfg.work, "wt_")
    git(cfg, "worktree", "add", "-q", "--detach", str(d), sha)
    try:
        yield d
    finally:
        _run(["git", "-C", str(cfg.bare), "worktree", "remove", "--force", str(d)], timeout=300)
        box_ci.prune(d)
        _run(["git", "-C", str(cfg.bare), "worktree", "prune"], timeout=120)


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


def _resources(cfg: Config) -> tuple[bool, int, str]:
    try:
        import psutil  # type: ignore[import-untyped,unused-ignore]
        free = psutil.disk_usage(str(cfg.work.anchor or cfg.work)).free / 1024 ** 3
        cores = psutil.cpu_percent(interval=2.0, percpu=True)
    except Exception as exc:  # unmeasured resources start nothing
        return False, 0, f"resources UNMEASURED ({type(exc).__name__})"
    ok, why = box_ci.disk_ok(free)
    n = box_ci.idle_workers(cores)
    if ok and n == 0:
        return False, 0, "no idle cores right now: CI waits"
    return ok, n, why


# ------------------------------------------------------------------ untrusted code (Audit MF-2)
#: A PR's own code (its tests, conftest, strategies under replay) never runs as SYSTEM. The loop
#: hands each such command to the CI WORKER: a scheduled task running as the local non-admin
#: account `quantci`, denied the token folder, the trust folder, data\secrets and C:\opt\quant.
#: The loop reads back only the exit code and the output tail, and posts statuses itself.
JOB_ENV_KEEP = ("PATH", "SYSTEMROOT", "PATHEXT", "COMSPEC", "NUMBER_OF_PROCESSORS", "PYTHONUTF8")
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
        time.sleep(JOB_POLL_S)
    (pending / f"{jid}.json").unlink(missing_ok=True)
    return 124, "the CI worker did not answer in time"


def worker_pass(jobs: Path) -> int:
    """One pass of the unprivileged CI worker: run every pending job, write its result."""
    pending, done = jobs / "pending", jobs / "done"
    n = 0
    for f in sorted(pending.glob("*.json")) if pending.is_dir() else []:
        try:
            job = json.loads(f.read_text(encoding="utf-8"))
            f.unlink()
        except (OSError, ValueError):
            continue
        rc, out = _run([str(a) for a in job.get("argv") or []], cwd=Path(job["cwd"]),
                       env={str(k): str(v) for k, v in (job.get("env") or {}).items()},
                       timeout=float(job.get("timeout") or 3600), idle=True)
        tmp = done / f"{job['id']}.tmp"
        done.mkdir(parents=True, exist_ok=True)
        tmp.write_text(json.dumps({"rc": rc, "out": out}), encoding="utf-8")
        os.replace(tmp, done / f"{job['id']}.json")
        n += 1
    return n


def run_tests(cfg: Config, root: Path, tests: Sequence[str] | str,
              workers: int) -> tuple[bool, str]:
    junit = root / "box-junit.xml"
    rc, out = _run_untrusted(cfg, box_ci.pytest_argv(cfg.python, tests, workers, junit),
                             cwd=root, timeout=6 * 3600)
    tail = out.strip().splitlines()[-1:] or [""]
    return rc == 0, f"pytest rc={rc}: {tail[0][:180]}"


def risk_job(cfg: Config, root: Path, base: str, head: str) -> tuple[bool, str]:
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
    if rc != 0:
        return False, f"risk-invariants static rc={rc}: {out.strip()[-160:]}"
    if suites:
        rc, out = _run_untrusted(cfg, [cfg.python, "-m", "pytest", "-q", "-p", "no:randomly",
                                       "-p", "no:cacheprovider", "--timeout=600", *suites],
                                 cwd=root, timeout=3600)
        if rc != 0:
            return False, f"risk suites rc={rc}: {out.strip()[-160:]}"
    return True, f"risk-invariants passed ({len(suites)} suite file(s))"


def replay_job(cfg: Config, base: str, head: str, changed: Sequence[str]) -> tuple[bool, str]:
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
                                 cwd=cfg.work, extra_env=extra, timeout=3600)
        lst.unlink(missing_ok=True)
        report.unlink(missing_ok=True)
    return rc == 0, f"replay-shadow rc={rc}: {out.strip()[-160:]}"


# ------------------------------------------------------------------------------ the stages
def gate_code(cfg: Config, live: str) -> str:
    """The commit whose gate runs. LIVE, once LIVE contains the forge-aware gate. Until the box-git
    change itself has merged, LIVE's gate only knows GitHub (and fails closed there), so the gate
    runs from the Audit-CLEARed head the installer ran from: the same rules plus the forge
    transport, never a PR's own code."""
    if not cfg.boot or cfg.boot == live:
        return live
    rc, _ = _run(["git", "-C", str(cfg.bare), "merge-base", "--is-ancestor", cfg.boot, live],
                 timeout=120)
    return live if rc == 0 else cfg.boot


def gate_tick(cfg: Config, live: str) -> str:
    with worktree(cfg, gate_code(cfg, live)) as root:
        env = {**os.environ, forge_api.FORGE_URL_ENV: cfg.forge_url,
               forge_api.FORGE_CA_ENV: str(cfg.ca), forge_api.FORGE_BARE_ENV: str(cfg.bare),
               forge_api.FORGE_TOKEN_FILE_ENV: str(cfg.tokens / "merge-gate.token"),
               "QUANT_TRUST_CHECKER": str(cfg.trust_checker or ""),
               "QUANT_TRUST_PIN": str(cfg.trust_pin or "")}
        rc, out = _run([cfg.python, ".github/scripts/audit_gate.py", "--repo",
                        forge_api.FORGE_REPO, "--sweep", "--box"], cwd=root, env=env, timeout=1800)
    return f"gate rc={rc}: {out.strip().splitlines()[-1][:200] if out.strip() else ''}"


#: A pending box CI status older than this is a run that died (reboot, kill): it is run again.
STALE_PENDING_S = 6 * 3600


def checked(runs: Sequence[Mapping[str, Any]], now: datetime | None = None) -> bool:
    """Has box CI already answered (or is it plausibly still answering) for this head?"""
    t = now or datetime.now(UTC)
    for r in runs:
        if r.get("status") == "completed":
            return True
        try:
            at = datetime.fromisoformat(str(r.get("started_at") or "").replace("Z", "+00:00"))
        except ValueError:
            continue
        if (t - at).total_seconds() < STALE_PENDING_S:
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


def pr_tick(cfg: Config) -> str:
    f = _forge(cfg, forge_api.BOX_CI_USER)
    prs = f.gh(f"repos/{forge_api.FORGE_REPO}/pulls?state=open&base={LIVE}")
    for p in prs or []:
        head = str((p.get("head") or {}).get("sha") or "")
        if not head or checked(f.gh(f"repos/x/y/commits/{head}/check-runs")["check_runs"]):
            continue
        if not audited_clear(f.gh(f"repos/x/y/issues/{p.get('number')}/comments"), head):
            continue  # Audit MF-2: unreviewed code never runs on the trading box
        base = git(cfg, "merge-base", f"refs/heads/{LIVE}", head)
        changed = [c for c in git(cfg, "diff", "--name-only", base, head).splitlines() if c]
        with worktree(cfg, head) as root:
            sel = impacted.select(root, changed)
            if sel == [] and all(c.endswith(impacted.INERT_SUFFIXES) for c in changed):
                why = "box CI: documents and images only (fast lane)"
                post(cfg, head, "success", why, (*GATING, "risk-invariants", "replay-shadow"))
                return f"PR #{p.get('number')}: fast lane"
            if sel == []:
                post(cfg, head, "success", "box CI: no change any test can observe")
            ok, n, why = _resources(cfg)
            if not ok:
                return f"PR #{p.get('number')} waits: {why}"
            passed, scope = True, "no observable test"
            if sel != []:
                post(cfg, head, "pending", f"box CI running on {n} idle cores")
                passed, what = run_tests(cfg, root, sel, n)
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
    return "no PR waiting for checks"


def full_tick(cfg: Config, live: str) -> str:
    state = box_ci.load_state(cfg.state)
    plan = box_ci.plan_full_run(state, live)
    if plan.pending:
        state["full_pending"] = plan.pending
    if not plan.start:
        box_ci.save_state(cfg.state, state)
        return plan.why
    ok, n, why = _resources(cfg)
    if not ok:
        return f"full run waits: {why}"
    state["full_running"] = plan.start
    box_ci.save_state(cfg.state, state)
    passed, why = False, "the run did not finish"
    try:
        with worktree(cfg, plan.start) as root:
            law_rc, _law = _run([cfg.python, "scripts/run_law_gate.py", "--laws-only"], cwd=root,
                                timeout=3600, idle=True)
            passed, what = run_tests(cfg, root, impacted.ALL, n)
            passed = passed and law_rc == 0
            why = f"law gate rc={law_rc}; {what}"
    finally:
        state = box_ci.load_state(cfg.state)
        state["full_running"] = None
        if state.get("full_pending") == plan.start:
            state["full_pending"] = None
        box_ci.record(state, head=plan.start, kind=box_ci.FULL, ok=passed, why=why)
        box_ci.save_state(cfg.state, state)
    return f"full {plan.start[:9]}: {'GREEN' if passed else 'RED'} ({why})"


def promote_tick(cfg: Config) -> str:
    state = box_ci.load_state(cfg.state)

    def anc(a: str, b: str) -> bool:
        return _run(["git", "-C", str(cfg.bare), "merge-base", "--is-ancestor", a, b])[0] == 0

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
    return f"promote {head[:9]}: rc={rc} {last}"


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


def drop_tick(cfg: Config) -> str:
    """Pull new packets from the drop repository into the inbox (ops/box_git/drop_pull.py)."""
    if cfg.drop is None or cfg.inbox is None:
        return "no drop configured"
    return drop_pull.pull(cfg.drop, cfg.inbox, cfg.state.parent)


def tick(cfg: Config) -> dict[str, Any]:
    out: dict[str, Any] = {"at": datetime.now(UTC).isoformat(timespec="seconds")}
    try:
        out["swept"] = sweep_stale(cfg)
    except Exception as exc:
        out["swept"] = f"ERROR {type(exc).__name__}: {str(exc)[:200]}"
    for name, fn in (("drop", lambda: drop_tick(cfg)),
                     ("inbox", lambda: inbox_tick(cfg)),
                     ("gate", lambda: gate_tick(cfg, live_head(cfg))),
                     ("pr", lambda: pr_tick(cfg)),
                     ("full", lambda: full_tick(cfg, live_head(cfg))),
                     ("promote", lambda: promote_tick(cfg))):
        try:
            out[name] = fn()
        except Exception as exc:  # one stage failing never stops the others
            out[name] = f"ERROR {type(exc).__name__}: {str(exc)[:300]}"
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
                 if raw.get("drop") else None)
    doc = tick(cfg)
    doc["trust"] = trust_status(cfg)
    report = cfg.state.with_name("LOOP_LAST.json")
    box_ci.save_state(report, doc)
    print(json.dumps(doc))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
