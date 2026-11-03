#!/usr/bin/env python3
"""Refuse to apply ruleset_live.json until it is safe to (ops/release/authority/LEVEL2.md step 5).

    python ops/release/authority/check_ruleset.py --repo OWNER/NAME [live.json] [--master m.json]

Safe means:
- the required check is pinned to the authority App;
- the admin bypass is pull-request-only;
- no bypass actor is a placeholder (actor_id 0);
- no bypass actor is GitHub Actions or any other identity whose credential a PR's own workflow
  can use (#650 audit MF: a same-repo pull_request run gets a write-scoped GITHUB_TOKEN, so an
  Actions bypass lets any branch push LIVE past the authority).
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

AUTHORITY_APP_ID = 5601819
GITHUB_ACTIONS_APP_ID = 15368


def problems(rs: dict[str, Any]) -> list[str]:
    out: list[str] = []
    rules = {r.get("type"): r for r in rs.get("rules") or []}
    need = ((rules.get("required_status_checks") or {}).get("parameters") or {}).get(
        "required_status_checks"
    ) or []
    if need != [{"context": "release-authority", "integration_id": AUTHORITY_APP_ID}]:
        out.append("the required check must be exactly release-authority from the authority App")
    if rs.get("enforcement") != "active":
        out.append("enforcement must be active")
    for b in rs.get("bypass_actors") or []:
        kind, ident, mode = b.get("actor_type"), b.get("actor_id"), b.get("bypass_mode")
        if not ident:
            out.append(f"bypass actor {kind} has a placeholder id: fill in the state App's id")
        if kind == "Integration" and ident in (GITHUB_ACTIONS_APP_ID, AUTHORITY_APP_ID):
            out.append(f"Integration {ident} may not bypass (a PR's workflow or the signer)")
        if kind == "RepositoryRole" and mode != "pull_request":
            out.append("the admin bypass must be pull_request mode only (never direct pushes)")
        if kind not in ("Integration", "RepositoryRole"):
            out.append(f"bypass actor type {kind} is not allowed")
    integ = [b for b in rs.get("bypass_actors") or [] if b.get("actor_type") == "Integration"]
    if len(integ) != 1:
        out.append("exactly one App (the state publisher) may bypass")
    return out


#: master's trusted-eval.yml is what pull_request_target runs (the default branch's file), and
#: the box adopts `production`: whoever can move either can fake the base-run evaluation or roll
#: the box back. Only CI's promote job (LIVE's own ci.yml, in the LIVE-only seal environment,
#: holding the state App's token) may update them.
PROMOTED_REFS = ["refs/heads/master", "refs/heads/production"]


def master_problems(rs: dict[str, Any], state_app: Any) -> list[str]:
    out: list[str] = []
    if rs.get("enforcement") != "active":
        out.append("master ruleset: enforcement must be active")
    inc = sorted(((rs.get("conditions") or {}).get("ref_name") or {}).get("include") or [])
    if inc != sorted(PROMOTED_REFS):
        out.append(f"master ruleset must cover exactly {PROMOTED_REFS}, got {inc}")
    types = {r.get("type"): r for r in rs.get("rules") or []}
    upd = (types.get("update") or {}).get("parameters") or {}
    if "update" not in types or upd.get("update_allows_fetch_and_merge") is not False:
        out.append("master ruleset must restrict updates to its bypass actor")
    if not {"deletion", "non_fast_forward"} <= set(types):
        out.append("master ruleset must refuse deletion and force pushes")
    bys = rs.get("bypass_actors") or []
    if [(b.get("actor_type"), b.get("actor_id")) for b in bys] != [("Integration", state_app)] \
            or not state_app:
        out.append("master ruleset: the state App alone may update master and production")
    return out


SEAL_ENV = "live-seal"
#: LIVE ALONE. desk-sync-clean is pushed directly by the VPS with no review, so a ci.yml edited
#: there would run in this environment and could read the state App's key -- and that App
#: bypasses the LIVE ruleset. The desk-sync-clean seal pushes its own unprotected branch with
#: GITHUB_TOKEN and needs no environment (ci.yml).
SEAL_BRANCHES = frozenset({"claude/llm-auto-upgrade-verify-gcjac3"})


def env_problems(env: dict[str, Any], branch_policies: list[dict[str, Any]]) -> list[str]:
    """The seal environment holds the state App's key: it must admit only LIVE, or a
    push-triggered run of a modified ci.yml on any other branch could read it (#650 audit)."""
    pol = env.get("deployment_branch_policy") or {}
    if not pol.get("custom_branch_policies") or pol.get("protected_branches"):
        return [f"environment {SEAL_ENV} must use custom branch policies (selected branches)"]
    names = {str(b.get("name")) for b in branch_policies if b.get("type", "branch") == "branch"}
    tags = [b for b in branch_policies if b.get("type") == "tag"]
    out = []
    if names != SEAL_BRANCHES or any(ch in n for n in names for ch in "*?[") or tags:
        out.append(f"environment {SEAL_ENV} must admit exactly {sorted(SEAL_BRANCHES)}, got "
                   f"{sorted(names)}{' and tags' if tags else ''}")  # fmt: skip
    return out


def _gh(path: str) -> Any:
    import subprocess

    p = subprocess.run(["gh", "api", path], capture_output=True, text=True, check=False)
    if p.returncode != 0:
        raise RuntimeError(f"gh api {path}: {p.stderr.strip()[:200]}")
    return json.loads(p.stdout)


def main(argv: list[str] | None = None) -> int:
    args = sys.argv[1:] if argv is None else argv
    repo = None
    if "--repo" in args:
        i = args.index("--repo")
        repo = args[i + 1]
        args = args[:i] + args[i + 2:]
    mpath = Path(__file__).with_name("ruleset_master.json")
    if "--master" in args:
        i = args.index("--master")
        mpath = Path(args[i + 1])
        args = args[:i] + args[i + 2:]
    path = Path(args[0]) if args else Path(__file__).with_name("ruleset_live.json")
    live = json.loads(path.read_text(encoding="utf-8"))
    got = problems(live)
    state = [b.get("actor_id") for b in live.get("bypass_actors") or []
             if b.get("actor_type") == "Integration"]  # fmt: skip
    got += master_problems(json.loads(mpath.read_text(encoding="utf-8")),
                           state[0] if len(state) == 1 else None)  # fmt: skip
    if repo is None:
        got.append("run with --repo OWNER/NAME so the live-seal environment is checked too")
    else:
        try:
            env = _gh(f"repos/{repo}/environments/{SEAL_ENV}")
            pols = _gh(f"repos/{repo}/environments/{SEAL_ENV}/deployment-branch-policies")
            got += env_problems(env, list(pols.get("branch_policies") or []))
        except (RuntimeError, ValueError) as exc:
            got.append(f"could not read environment {SEAL_ENV}: {exc}")
    for p in got:
        print(f"NOT SAFE: {p}")
    if not got:
        print("SAFE to import")
    return 1 if got else 0


if __name__ == "__main__":
    sys.exit(main())
