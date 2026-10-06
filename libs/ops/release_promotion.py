"""Development -> green immutable release -> production, and a master equal to what is deployed.

THE CHAIN, ONE HOP PER STAGE

    live branch (development)   every commit, tested by ci.yml's `quality` + `mt5-money-path`
        |  both green, `seal` committed RELEASE.json
        v
    release/<UTC>-<sha12>       an ANNOTATED tag on that commit carrying the evidence: the CI
                                run, the law gate's verdict, both suites' counts. Immutable: a tag
                                that exists is never moved or re-pointed by this module.
        |
        v
    production                  a pointer branch, only ever FAST-FORWARDED (never force-pushed)
                                to the newest release. This is what the trading box adopts.
        |
        v
    master                      a tree-take merge commit: parents (master, release), tree = the
                                release's tree. Pushed without force. The mechanism is the one
                                99704ba1 (PR #66) used by hand; this makes it the CI's job, so
                                master stops drifting 20 commits behind between hand syncs.

WHY THE BOX NEEDS THIS (the other half lives in `adoption_decision`). Until now the box adopted
the branch TIP every hour. A tip that CI had not finished judging -- or had judged red -- was
live code on the machine that trades within the hour (7379cbf7, 2026-09-30: an edit to the sealed
gauntlet reached the branch while CI reported the law gate red). Adopting the production pointer
means the tip lands only once CI is green.

WHY THE BOX STILL ADOPTS THE TIP, MOST OF THE TIME. The box pushes its own state commits to the
live branch every quarter hour, so the tip is almost always "the release plus box state". The
rule that decides "same code" is the one the gateway already trusts, `libs.ops.release`'s
NON_CODE + `is_state_path`: when the diff release..tip touches no CODE path, the tip IS the
release and is adopted whole, which keeps the box's pushes fast-forwarding. Only a tip carrying
code that no green run has judged is held back, and then the box adopts the release itself.

FAIL CLOSED. No production pointer/tag or an unverifiable diff -> HOLD, not an untested tip.
An explicit
override (`ADOPT_UNRELEASED` flag file, `QUANT_ADOPT_UNRELEASED=1`, `--allow-unreleased`) adopts
the tip regardless -- a deliberate act with a name, for the day CI is down and a fix must land.

Stdlib only, like `libs.ops.release`: the box runs this under the Windows launcher with no venv.
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import xml.etree.ElementTree as ET
from collections.abc import Iterable, Sequence
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from libs.ops import release

LIVE_BRANCH = "claude/llm-auto-upgrade-verify-gcjac3"
PRODUCTION_BRANCH = "production"
MASTER_BRANCH = "master"
TAG_PREFIX = "release/"
#: `release/20260930T101736Z-6c8a71a40d7d` -- sortable by name because the stamp leads.
TAG_RE = re.compile(r"^release/(\d{8}T\d{6}Z)-([0-9a-f]{12})$")

#: The box's escape hatch. Untracked by construction (the state sync publishes an allowlist).
OVERRIDE_FLAG_REL = "desks/mt5/data/ADOPT_UNRELEASED"
OVERRIDE_ENV = "QUANT_ADOPT_UNRELEASED"

#: Private ref namespace the box fetches into, so no other fetcher's tracking ref is raced.
GATE_REF_TIP = "refs/quant/release-gate/tip"
GATE_REF_PRODUCTION = "refs/quant/release-gate/production"

CI_IDENTITY = ("quant-ci", "ci@users.noreply.github.com")


# ------------------------------------------------------------------------------------ git
class GitError(RuntimeError):
    """A git command exited non-zero. Carries git's own words."""


@dataclass
class Git:
    root: Path
    timeout: float = 300.0

    def run(self, *args: str, check: bool = True, env: dict[str, str] | None = None
            ) -> subprocess.CompletedProcess[str]:
        # Scheduled adoption is noninteractive. A timed-out HTTPS fetch must
        # also stop its remote helper, which otherwise outlives the writer lease.
        from libs.ops.proctree import run as run_process

        full_env = dict(os.environ)
        full_env.setdefault("GIT_TERMINAL_PROMPT", "0")
        full_env.setdefault("GCM_INTERACTIVE", "never")
        if env:
            full_env.update(env)
        r = run_process([release._git_exe(), "-c", "core.quotepath=off", *args],
                           cwd=self.root, capture_output=True, text=True,
                           timeout=self.timeout, env=full_env)
        if check and r.returncode != 0:
            raise GitError(f"git {' '.join(args)} exited {r.returncode}: "
                           f"{(r.stderr or r.stdout).strip()[-600:]}")
        return r

    def out(self, *args: str) -> str:
        return self.run(*args).stdout.strip()

    def rev(self, spec: str) -> str | None:
        r = self.run("rev-parse", "--verify", "--quiet", f"{spec}^{{commit}}", check=False)
        if r.returncode != 0:
            return None
        return r.stdout.strip() or None

    def is_ancestor(self, a: str, b: str) -> bool:
        return self.run("merge-base", "--is-ancestor", a, b, check=False).returncode == 0

    def tree(self, spec: str) -> str:
        return self.out("rev-parse", f"{spec}^{{tree}}")

    def changed(self, a: str, b: str) -> list[str]:
        out = self.out("diff", "--name-only", "--no-renames", a, b)
        return sorted({ln.strip() for ln in out.splitlines() if ln.strip()})


# ------------------------------------------------------------------------------ pure rules
def is_code_path(rel: str) -> bool:
    """The gateway's own rule (`release.accepts`): anything not NON_CODE and not state."""
    p = str(rel).replace("\\", "/").lstrip("./")
    return p not in release.NON_CODE and not release.is_state_path(p)


def code_paths(paths: Iterable[str]) -> list[str]:
    return sorted({p for p in paths if is_code_path(p)})


def tag_name(sha: str, when: datetime) -> str:
    if len(sha) < 12 or not re.fullmatch(r"[0-9a-f]+", sha):
        raise ValueError(f"not a commit sha: {sha!r}")
    return f"{TAG_PREFIX}{when.astimezone(UTC):%Y%m%dT%H%M%SZ}-{sha[:12]}"


def parse_tag(name: str) -> tuple[datetime, str] | None:
    m = TAG_RE.match(str(name).strip())
    if not m:
        return None
    return datetime.strptime(m.group(1), "%Y%m%dT%H%M%SZ").replace(tzinfo=UTC), m.group(2)


def newest_release_tag(names: Iterable[str]) -> str | None:
    """The newest well-formed `release/*` tag by its own timestamp; malformed names ignored."""
    best: tuple[datetime, str] | None = None
    for n in names:
        parsed = parse_tag(n)
        if parsed is not None and (best is None or parsed[0] > best[0]
                                   or (parsed[0] == best[0] and n > best[1])):
            best = (parsed[0], n)
    return best[1] if best else None


def junit_counts(path: Path) -> dict[str, int]:
    """Totals from a pytest JUnit XML (one or many <testsuite>). Absent file -> ValueError."""
    root = ET.parse(path).getroot()
    suites = [root] if root.tag == "testsuite" else list(root.iter("testsuite"))
    tot = {"tests": 0, "failures": 0, "errors": 0, "skipped": 0}
    for s in suites:
        for k in tot:
            tot[k] += int(s.get(k) or 0)
    tot["passed"] = tot["tests"] - tot["failures"] - tot["errors"] - tot["skipped"]
    return tot


def summarize_counts(c: dict[str, int]) -> str:
    return (f"{c['passed']} passed, {c['failures']} failed, {c['errors']} errors, "
            f"{c['skipped']} skipped ({c['tests']} collected)")


def law_gate_line(text: str) -> str:
    """The verdict line `run_law_gate.py` prints (`LAW GATE -- 38 fences: PASS`)."""
    for ln in text.splitlines():
        if ln.strip().startswith("LAW GATE"):
            return ln.strip()
    return "LAW GATE -- verdict line not found in the captured output (UNMEASURED)"


@dataclass(frozen=True)
class Evidence:
    tested_sha: str
    run_id: str = ""
    run_attempt: str = ""
    run_url: str = ""
    law_gate: str = ""
    quality_suite: str = ""
    mt5_suite: str = ""

    def lines(self) -> list[str]:
        return [f"tested_sha: {self.tested_sha}",
                f"ci_run: {self.run_id or 'UNMEASURED'}"
                + (f" attempt {self.run_attempt}" if self.run_attempt else "")
                + (f" {self.run_url}" if self.run_url else ""),
                f"law_gate: {self.law_gate or 'UNMEASURED'}",
                f"quality_suite: {self.quality_suite or 'UNMEASURED'}",
                f"mt5_money_path_suite: {self.mt5_suite or 'UNMEASURED'}"]


def tag_message(tag: str, target: str, ev: Evidence, *, previous: str | None,
                code_changed: Sequence[str] | None) -> str:
    head = [f"{tag}", "", f"commit: {target}", *ev.lines()]
    if previous is None:
        head.append("previous_production: none (first release)")
    else:
        n = "UNMEASURED" if code_changed is None else str(len(code_changed))
        head.append(f"previous_production: {previous} ({n} code path(s) changed since)")
    head += ["", "Green on quality + mt5-money-path; sealed by the seal job. Immutable: never "
                 "moved, never re-pointed. `production` fast-forwards to it; master carries its "
                 "tree."]
    return "\n".join(head) + "\n"


def master_sync_message(target: str, tag: str | None) -> str:
    return (f"Make master carry the tree the desk deploys ({target[:12]})\n\n"
            f"Tree-take merge: parents (master, {target[:12]}), tree = {target[:12]}'s tree"
            + (f", release {tag}" if tag else "") + ".\n"
            "Written by ci.yml's promote job; nothing on master is lost because every commit\n"
            "master carried is still its first parent.\n")


# --------------------------------------------------------------------------- CI promotion
@dataclass
class PromotionResult:
    target: str
    tag: str | None = None
    tag_created: bool = False
    production_before: str | None = None
    production_after: str | None = None
    master_before: str | None = None
    master_after: str | None = None
    notes: list[str] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def _fetch(git: Git, remote: str, branch: str, ref: str) -> str | None:
    """Fetch `branch` into the private `ref`; None when the remote has no such branch."""
    r = git.run("fetch", "--no-auto-maintenance", "--no-tags", remote,
                f"+refs/heads/{branch}:{ref}", check=False)
    if r.returncode != 0:
        msg = (r.stderr or r.stdout)
        if "couldn't find remote ref" in msg or "could not find remote ref" in msg:
            return None
        raise GitError(f"fetch {remote} {branch}: {msg.strip()[-600:]}")
    return git.rev(ref)


def promote(root: Path, target: str, ev: Evidence, *, remote: str = "origin",
            live_branch: str = LIVE_BRANCH, production: str = PRODUCTION_BRANCH,
            master: str = MASTER_BRANCH, now: datetime | None = None,
            dry_run: bool = False) -> PromotionResult:
    """Tag `target`, fast-forward `production` to it, tree-take-merge it into `master`.

    Refuses (GitError / ValueError) rather than guessing when: the target is not on the live
    branch, the target carries code the tested commit did not, or production has moved to a
    history the target does not contain -- the three ways a wiring mistake would otherwise
    publish something no green run judged.
    """
    git = Git(root)
    now = now or datetime.now(UTC)
    tgt = git.rev(target)
    tested = git.rev(ev.tested_sha)
    if tgt is None or tested is None:
        raise ValueError(f"target {target!r} or tested {ev.tested_sha!r} is not a commit here")
    res = PromotionResult(target=tgt)

    # 1. the target must be the tested code, on the live branch.
    untested = code_paths(git.changed(tested, tgt)) if tested != tgt else []
    if untested:
        raise ValueError(f"target {tgt[:12]} carries {len(untested)} code path(s) the tested "
                         f"commit {tested[:12]} did not: {untested[:6]}")
    live = _fetch(git, remote, live_branch, "refs/quant/promote/live")
    if live is None or not git.is_ancestor(tgt, live):
        raise ValueError(f"target {tgt[:12]} is not on {remote}/{live_branch}")

    # 2. production: fast-forward only.
    prod = _fetch(git, remote, production, "refs/quant/promote/production")
    res.production_before = prod
    advance = True
    if prod is not None and prod != tgt:
        if git.is_ancestor(tgt, prod):
            advance = False
            res.notes.append(f"production {prod[:12]} already contains {tgt[:12]} (a newer "
                             "run promoted first); not moving it backwards")
        elif not git.is_ancestor(prod, tgt):
            raise ValueError(f"production {prod[:12]} is not an ancestor of {tgt[:12]}: it was "
                             "moved off the live history by hand; refusing to force it")
    elif prod == tgt:
        advance = False
        res.notes.append("production already points at the target")

    # 3. the tag: one per promoted commit, never moved.
    existing = [t for t in git.out("tag", "--points-at", tgt, "--list", f"{TAG_PREFIX}*")
                .splitlines() if parse_tag(t)]
    if existing:
        res.tag = sorted(existing)[-1]
        res.notes.append(f"{tgt[:12]} is already released as {res.tag}")
    elif advance or prod is None or prod == tgt:
        changed = None if prod is None else code_paths(git.changed(prod, tgt))
        res.tag = tag_name(tgt, now)
        msg = tag_message(res.tag, tgt, ev, previous=prod, code_changed=changed)
        env = {"GIT_COMMITTER_NAME": CI_IDENTITY[0], "GIT_COMMITTER_EMAIL": CI_IDENTITY[1],
               "GIT_AUTHOR_NAME": CI_IDENTITY[0], "GIT_AUTHOR_EMAIL": CI_IDENTITY[1]}
        if not dry_run:
            git.run("tag", "-a", res.tag, tgt, "-m", msg, env=env)
            git.run("push", remote, f"refs/tags/{res.tag}")
        res.tag_created = True

    if advance:
        if not dry_run:
            git.run("push", remote, f"{tgt}:refs/heads/{production}")
        res.production_after = tgt
    else:
        res.production_after = prod

    # 4. master: tree-take merge, no force, retried when master moves under us.
    deployed = res.production_after or tgt
    for attempt in range(1, 4):
        mst = _fetch(git, remote, master, "refs/quant/promote/master")
        if attempt == 1:
            res.master_before = mst
        if mst is None:
            res.notes.append(f"{remote}/{master} does not exist; not creating it")
            break
        if git.tree(mst) == git.tree(deployed):
            res.master_after = mst
            res.notes.append("master already carries the deployed tree")
            break
        env = {"GIT_COMMITTER_NAME": CI_IDENTITY[0], "GIT_COMMITTER_EMAIL": CI_IDENTITY[1],
               "GIT_AUTHOR_NAME": CI_IDENTITY[0], "GIT_AUTHOR_EMAIL": CI_IDENTITY[1]}
        merged = git.run("commit-tree", git.tree(deployed), "-p", mst, "-p", deployed,
                         "-m", master_sync_message(deployed, res.tag), env=env).stdout.strip()
        if dry_run:
            res.master_after = merged
            break
        if git.run("push", remote, f"{merged}:refs/heads/{master}", check=False).returncode == 0:
            res.master_after = merged
            break
        res.notes.append(f"master push rejected (attempt {attempt}); master moved, rebuilding")
    else:
        raise GitError("could not push the master tree-take merge after 3 attempts")
    return res


# ------------------------------------------------------------------------- box adoption
@dataclass
class AdoptionDecision:
    decision: str            # ADOPT_TIP | ADOPT_RELEASE | HOLD | LEGACY_TIP | OVERRIDE_TIP
    target: str | None
    reason: str
    tip: str | None = None
    release_ref: str | None = None
    release_sha: str | None = None
    head: str | None = None
    unreleased_code: list[str] = field(default_factory=list)

    @property
    def adopts(self) -> bool:
        return self.target is not None

    def as_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["adopts"] = self.adopts
        return d


def override_requested(root: Path, flag: bool = False) -> str | None:
    """Why the box adopts the tip regardless of release, or None when nobody asked."""
    if flag:
        return "--allow-unreleased was passed"
    if os.environ.get(OVERRIDE_ENV, "").strip() in {"1", "true", "yes"}:
        return f"{OVERRIDE_ENV} is set"
    if (root / Path(*OVERRIDE_FLAG_REL.split("/"))).exists():
        return f"{OVERRIDE_FLAG_REL} exists"
    return None


def adoption_decision(git: Git, *, tip: str, release_sha: str | None, release_ref: str | None,
                      head: str | None, override: str | None = None) -> AdoptionDecision:
    """Which commit may this box adopt? Pure over git's answers; never fetches."""
    def mk(decision: str, target: str | None, reason: str,
           unreleased: list[str] | None = None) -> AdoptionDecision:
        return AdoptionDecision(decision, target, reason, tip=tip, release_ref=release_ref,
                                release_sha=release_sha, head=head,
                                unreleased_code=list(unreleased or []))

    if override:
        return mk("OVERRIDE_TIP", tip, f"override: {override}; adopting the branch tip whether "
                  "or not CI has released it")
    if release_sha is None:
        return mk("HOLD", None, "no production pointer and no release/* tag exists yet; "
                  "holding until a tested release is published")
    try:
        unreleased = code_paths(git.changed(release_sha, tip))
    except GitError as exc:
        return mk("HOLD", None, f"cannot diff release {release_sha[:12]} against tip "
                  f"{tip[:12]} ({exc}); holding because release equivalence is unverified")
    if not unreleased:
        return mk("ADOPT_TIP", tip, f"tip {tip[:12]} is release {release_sha[:12]} plus "
                  "seal/state paths only")
    if not git.is_ancestor(release_sha, tip):
        return mk("HOLD", None, f"release {release_sha[:12]} is not on the branch history of tip "
                  f"{tip[:12]}; holding (override: create {OVERRIDE_FLAG_REL})", unreleased)
    if head is not None and git.is_ancestor(release_sha, head):
        return mk("HOLD", None, f"tip {tip[:12]} carries {len(unreleased)} code path(s) no green "
                  f"run has released, and this box already runs release {release_sha[:12]}; "
                  "waiting for CI", unreleased)
    return mk("ADOPT_RELEASE", release_sha, f"tip {tip[:12]} carries {len(unreleased)} unreleased "
              f"code path(s); adopting the newest green release {release_sha[:12]} instead",
              unreleased)


def gate(root: Path, *, branch: str = LIVE_BRANCH, remote: str = "origin",
         allow_unreleased: bool = False, fetch: bool = True) -> AdoptionDecision:
    """Fetch the tip and the release pointer into private refs, then decide."""
    git = Git(root)
    if fetch:
        tip = None
        last: Exception | None = None
        for _ in range(3):
            try:
                tip = _fetch(git, remote, branch, GATE_REF_TIP)
                break
            except (GitError, subprocess.SubprocessError) as exc:
                last = exc
        if tip is None:
            raise GitError(f"could not fetch {remote}/{branch}: {last}")
        prod = _fetch(git, remote, PRODUCTION_BRANCH, GATE_REF_PRODUCTION)
    else:
        tip = git.rev(GATE_REF_TIP) or git.rev(f"{remote}/{branch}")
        if tip is None:
            raise GitError(f"no fetched tip for {branch}")
        prod = git.rev(GATE_REF_PRODUCTION)
    ref: str | None = PRODUCTION_BRANCH if prod else None
    if prod is None:
        if fetch:
            git.run("fetch", "--no-auto-maintenance", "--no-tags", remote,
                    f"+refs/tags/{TAG_PREFIX}*:refs/tags/"
                    f"{TAG_PREFIX}*", check=False)
        newest = newest_release_tag(git.out("tag", "--list", f"{TAG_PREFIX}*").splitlines())
        if newest:
            prod, ref = git.rev(newest), newest
    head = git.rev("HEAD")
    return adoption_decision(git, tip=tip, release_sha=prod, release_ref=ref, head=head,
                             override=override_requested(root, allow_unreleased))


def dumps(d: dict[str, Any]) -> str:
    return json.dumps(d, sort_keys=True)
