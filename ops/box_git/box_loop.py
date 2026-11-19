"""THE BOX'S RELEASE LOOP: gate sweep, PR checks, full suite, seal and promote -- no GitHub.

One pass every few minutes (scheduled task QuantForge-Loop, IgnoreNew, installed by
install_box_forge.ps1). Each stage is the GitHub-era stage it replaces, run on the box:

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
import subprocess
import sys
import tempfile
from collections.abc import Iterator, Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
if str(HERE.parents[1]) not in sys.path:
    sys.path.insert(0, str(HERE.parents[1]))

from ops.box_git import box_ci, forge_api, impacted  # noqa: E402

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
    d = Path(tempfile.mkdtemp(prefix="wt_", dir=cfg.work))
    git(cfg, "worktree", "add", "-q", "--detach", str(d), sha)
    try:
        yield d
    finally:
        _run(["git", "-C", str(cfg.bare), "worktree", "remove", "--force", str(d)], timeout=300)
        box_ci.prune(d)
        _run(["git", "-C", str(cfg.bare), "worktree", "prune"], timeout=120)


def _forge(cfg: Config, account: str) -> forge_api.Forge:
    env = {forge_api.FORGE_URL_ENV: cfg.forge_url, forge_api.FORGE_CA_ENV: str(cfg.ca),
           forge_api.FORGE_TOKEN_FILE_ENV: str(cfg.tokens / f"{account}.token")}
    return forge_api.Forge(forge_api.http_transport(env), workflow_of={}, bare=str(cfg.bare))


def post(cfg: Config, sha: str, state: str, desc: str) -> None:
    f = _forge(cfg, forge_api.BOX_CI_USER)
    for ctx in GATING:
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


def run_tests(cfg: Config, root: Path, tests: Sequence[str] | str,
              workers: int) -> tuple[bool, str]:
    junit = root / "box-junit.xml"
    rc, out = _run(box_ci.pytest_argv(cfg.python, tests, workers, junit), cwd=root,
                   timeout=6 * 3600, idle=True)
    tail = out.strip().splitlines()[-1:] or [""]
    return rc == 0, f"pytest rc={rc}: {tail[0][:180]}"


# ------------------------------------------------------------------------------ the stages
def gate_tick(cfg: Config, live: str) -> str:
    with worktree(cfg, live) as root:
        env = {**os.environ, forge_api.FORGE_URL_ENV: cfg.forge_url,
               forge_api.FORGE_CA_ENV: str(cfg.ca), forge_api.FORGE_BARE_ENV: str(cfg.bare),
               forge_api.FORGE_TOKEN_FILE_ENV: str(cfg.tokens / "merge-gate.token")}
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


def pr_tick(cfg: Config) -> str:
    f = _forge(cfg, forge_api.BOX_CI_USER)
    prs = f.gh(f"repos/{forge_api.FORGE_REPO}/pulls?state=open&base={LIVE}")
    for p in prs or []:
        head = str((p.get("head") or {}).get("sha") or "")
        if not head or checked(f.gh(f"repos/x/y/commits/{head}/check-runs")["check_runs"]):
            continue
        base = git(cfg, "merge-base", f"refs/heads/{LIVE}", head)
        changed = [c for c in git(cfg, "diff", "--name-only", base, head).splitlines() if c]
        with worktree(cfg, head) as root:
            sel = impacted.select(root, changed)
            if sel == []:
                post(cfg, head, "success", "box CI: no change any test can observe (fast lane)")
                return f"PR #{p.get('number')}: fast lane"
            ok, n, why = _resources(cfg)
            if not ok:
                return f"PR #{p.get('number')} waits: {why}"
            post(cfg, head, "pending", f"box CI running on {n} idle cores")
            passed, what = run_tests(cfg, root, sel, n)
        scope = "full suite" if sel == impacted.ALL else f"{len(sel)} impacted test file(s)"
        post(cfg, head, "success" if passed else "failure",
             f"box CI, {scope}: {what}. Full suite runs after merge; release needs it green.")
        return f"PR #{p.get('number')}: {'pass' if passed else 'FAIL'} ({scope})"
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


def tick(cfg: Config) -> dict[str, Any]:
    out: dict[str, Any] = {"at": datetime.now(UTC).isoformat(timespec="seconds")}
    for name, fn in (("gate", lambda: gate_tick(cfg, live_head(cfg))),
                     ("pr", lambda: pr_tick(cfg)),
                     ("full", lambda: full_tick(cfg, live_head(cfg))),
                     ("promote", lambda: promote_tick(cfg))):
        try:
            out[name] = fn()
        except Exception as exc:  # one stage failing never stops the others
            out[name] = f"ERROR {type(exc).__name__}: {str(exc)[:300]}"
    return out


def live_head(cfg: Config) -> str:
    return git(cfg, "rev-parse", f"refs/heads/{LIVE}")


def main(argv: list[str] | None = None) -> int:
    import argparse
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--config", required=True, help="JSON with the Config fields")
    a = ap.parse_args(argv)
    raw = json.loads(Path(a.config).read_text(encoding="utf-8"))
    cfg = Config(forge_url=raw["forge_url"], bare=Path(raw["bare"]), work=Path(raw["work"]),
                 tokens=Path(raw["tokens"]), ca=Path(raw["ca"]), state=Path(raw["state"]),
                 python=raw.get("python") or sys.executable)
    doc = tick(cfg)
    report = cfg.state.with_name("LOOP_LAST.json")
    box_ci.save_state(report, doc)
    print(json.dumps(doc))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
