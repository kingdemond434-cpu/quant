"""BRANCH PROTECTION FOR THE BOX'S OWN REPOSITORY -- the rules GitHub enforced, enforced here.

WHY (principal 2026-11-19: "all merges going live adoption everything not relying on GitHub").
On 11-19 GitHub suspended the account and every merge, CI run, CLEAR and adoption froze. The box
repository (C:\\ProgramData\\QuantBox\\origin.git) becomes the source of truth; this module is its
`pre-receive` hook, so the protection lives in the repository itself and not in a host that can
be switched off.

THE RULES, in order, first refusal wins. A push is a list of (old, new, ref) updates and is
refused WHOLE if any one update is refused (git's own pre-receive contract).

  1. NO DELETION of any ref. Branches and tags are evidence; a merged branch costs nothing.
  2. NO REWRITE, EVER, of a protected ref: LIVE, production, master, release tags and the merge
     gate's records. A non-fast-forward is refused even for the gate -- GitHub's "no force push"
     with no administrator bypass.
  3. PROTECTED REFS MOVE ONLY BY THEIR OWNER (LIVE: the gate; production, master: the release
     authority's promote). A push from the network (a Claude thread, role
     `thread`, set by the SSH forced command) may only create or fast-forward `claude/*` work
     branches that are NOT the LIVE branch (LIVE's own name starts with `claude/`). The box merge
     gate runs locally with role `gate` and is the only writer of LIVE and production, exactly as
     the audit gate was the only path onto LIVE on GitHub.
  4. RELEASE TAGS ARE WRITE-ONCE and only the release authority (role `authority`) creates them.
  5. ANY OTHER REF IS REFUSED. An unknown namespace is not a permission.

An unknown or missing role is `thread`: the least authority, never the most.
"""
from __future__ import annotations

import os
import subprocess
import sys
from collections.abc import Callable, Iterable
from dataclasses import dataclass

LIVE_BRANCH = "claude/llm-auto-upgrade-verify-gcjac3"
ZERO = "0" * 40

#: Protected branch -> the one role that may fast-forward it. LIVE moves by the merge gate (and
#: its seal commit); production and master move by the release authority's promote, exactly as
#: ci.yml's promote job moved them on GitHub.
PROTECTED_OWNER = {
    f"refs/heads/{LIVE_BRANCH}": "gate", "refs/heads/records": "gate",
    "refs/heads/production": "authority", "refs/heads/master": "authority",
}
PROTECTED_BRANCHES = frozenset(PROTECTED_OWNER)
RELEASE_TAG_PREFIX = "refs/tags/release/"
WORK_PREFIX = "refs/heads/claude/"
ROLES = frozenset({"thread", "gate", "authority"})
ROLE_ENV = "QUANT_BOX_GIT_ROLE"
#: The forge (Gitea) runs repository hooks with the AUTHENTICATED pusher's name in this variable,
#: set by the server, never by the client. The two box accounts below are the only roles above
#: `thread`; every other pusher, the `claude` account included, is a thread.
PUSHER_ENV = "GITEA_PUSHER_NAME"
FORGE_ROLES = {"merge-gate": "gate", "release-authority": "authority"}


@dataclass(frozen=True)
class Verdict:
    ok: bool
    ref: str
    why: str


def role_from_env(env: dict[str, str] | None = None) -> str:
    """The pusher's role. Through the forge: the server's own pusher name decides, and the
    role variable is ignored (a client must never name its own authority). Outside the forge (a
    local push on the box, by an administrator) the role variable is read."""
    e = env if env is not None else os.environ
    pusher = e.get(PUSHER_ENV)
    if pusher is not None:
        return FORGE_ROLES.get(pusher.strip().lower(), "thread")
    r = e.get(ROLE_ENV, "").strip().lower()
    return r if r in ROLES else "thread"


def decide(old: str, new: str, ref: str, role: str,
           is_ancestor: Callable[[str, str], bool]) -> Verdict:
    """One ref update. Pure over `is_ancestor(a, b)` (git merge-base --is-ancestor a b)."""
    role = role if role in ROLES else "thread"
    if new == ZERO:
        return Verdict(False, ref, "deleting a ref is refused: branches and tags are evidence")
    creating = old == ZERO
    if ref.startswith(RELEASE_TAG_PREFIX):
        if role != "authority":
            return Verdict(False, ref, "only the release authority creates release tags")
        if not creating:
            return Verdict(False, ref, "release tags are write-once")
        return Verdict(True, ref, "release tag created by the authority")
    if ref in PROTECTED_BRANCHES:
        owner = PROTECTED_OWNER[ref]
        if role != owner:
            who = "the box merge gate" if owner == "gate" else "the release authority"
            return Verdict(False, ref, f"{ref} is protected: only {who} moves it")
        if not creating and not is_ancestor(old, new):
            return Verdict(False, ref, f"{ref} may only fast-forward: no rewrite, no bypass")
        return Verdict(True, ref, f"{owner} fast-forward")
    if ref.startswith(WORK_PREFIX):
        if role not in ("thread", "gate"):
            return Verdict(False, ref, f"role {role} does not push work branches")
        if not creating and not is_ancestor(old, new):
            return Verdict(False, ref, "work branches may only fast-forward (no force push)")
        return Verdict(True, ref, "work branch")
    return Verdict(False, ref, f"{ref} is outside every allowed namespace")


def decide_push(updates: Iterable[tuple[str, str, str]], role: str,
                is_ancestor: Callable[[str, str], bool]) -> list[Verdict]:
    return [decide(o, n, r, role, is_ancestor) for o, n, r in updates]


def _git_is_ancestor(a: str, b: str) -> bool:
    try:
        return subprocess.run(["git", "merge-base", "--is-ancestor", a, b],
                              capture_output=True, timeout=60, check=False).returncode == 0
    except (OSError, subprocess.SubprocessError):
        return False  # unmeasured ancestry refuses: fail closed


def main(stdin: Iterable[str] | None = None, env: dict[str, str] | None = None) -> int:
    """git pre-receive: `<old> <new> <ref>` per line on stdin. Exit 0 accepts the whole push."""
    updates = []
    for line in stdin if stdin is not None else sys.stdin:
        parts = line.split()
        if len(parts) == 3:
            updates.append((parts[0], parts[1], parts[2]))
    role = role_from_env(env)
    verdicts = decide_push(updates, role, _git_is_ancestor)
    bad = [v for v in verdicts if not v.ok]
    for v in bad:
        print(f"box-git: REFUSED {v.ref}: {v.why}", file=sys.stderr)
    return 1 if bad or not updates else 0


if __name__ == "__main__":
    raise SystemExit(main())
