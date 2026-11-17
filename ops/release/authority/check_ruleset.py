#!/usr/bin/env python3
"""Refuse to apply ruleset_live.json until it is safe to (ops/release/authority/LEVEL2.md step 5).

    python ops/release/authority/check_ruleset.py --repo OWNER/NAME [live.json] [--master m.json]

Safe means:
- the required check is pinned to the authority App;
- no person may bypass, not even the admin in pull_request mode (#650 audit MF1): only the state
  App, bounded by the ROOT publisher's path filter;
- no bypass actor is a placeholder (actor_id 0);
- no bypass actor is GitHub Actions or any other identity whose credential a PR's own workflow
  can use (#650 audit MF: a same-repo pull_request run gets a write-scoped GITHUB_TOKEN, so an
  Actions bypass lets any branch push LIVE past the authority);
- every LIVE writer is converted, OBSERVED on GitHub (writer_problems; bootstrap_level2.ps1 step
  7 promised this, and until 2026-11-17 nothing checked it). Applying the ruleset while a writer
  still pushes as a person would silently cut that writer off, and adoption with it.

    ... --state-login quant-state-publisher[bot] --merger-login quant-merger[bot]
        --converted-at 2026-11-20T10:00:00Z
"""

from __future__ import annotations

import importlib.util
import json
import sys
from collections.abc import Callable, Iterable
from datetime import UTC, datetime, timedelta
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
        kind, ident = b.get("actor_type"), b.get("actor_id")
        if not ident:
            out.append(f"bypass actor {kind} has a placeholder id: fill in the state App's id")
        if kind == "Integration" and ident in (GITHUB_ACTIONS_APP_ID, AUTHORITY_APP_ID):
            out.append(f"Integration {ident} may not bypass (a PR's workflow or the signer)")
        if kind != "Integration":
            # #650 audit MF1: no person bypasses LIVE, not even the admin in pull_request mode.
            # A ROOT change lands through root_merge.ps1, which opens that bypass for one merge.
            out.append(f"bypass actor type {kind} is not allowed (Apps only)")
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


LIVE = "claude/llm-auto-upgrade-verify-gcjac3"
#: How far back every person-made push to LIVE must be one the state App now carries.
WRITERS_LOOKBACK_H = 72
#: How long LIVE must be watched after the writers converted, with no person-made write at all.
WRITERS_QUIET_MIN = 60
PUSH_TYPES = frozenset({"push", "force_push", "branch_creation", "branch_deletion"})
WRITE_TYPES = PUSH_TYPES | {"pr_merge"}


def _when(x: Any) -> datetime | None:
    try:
        t = datetime.fromisoformat(str(x).replace("Z", "+00:00"))
    except ValueError:
        return None
    return t if t.tzinfo else None


def writer_problems(events: Iterable[dict[str, Any]],
                    changed: Callable[[str, str], list[str] | None],
                    apps: set[str], converted_at: datetime | None, now: datetime,
                    carried: Callable[[str], bool]) -> tuple[list[str], dict[str, int]]:
    """(problems, counts) for LIVE's writers (pure over its two callables).

    (a) Every push to LIVE in the last WRITERS_LOOKBACK_H hours by a login that is not one of
        `apps` changed only paths the state App now carries (`carried`, the publisher's own
        filter). Anything else is a writer the bootstrap did not convert.
    (b) Since `converted_at`, nobody but `apps` wrote LIVE at all: no push, and no PR merge
        (the gate's merges included). At least WRITERS_QUIET_MIN minutes are observed, and the
        state App pushed at least once in them, so a silent publisher cannot pass for a quiet one.
    Anything unreadable is a problem: this fails closed."""
    out: list[str] = []
    n = {"events": 0, "person_pushes_72h": 0, "uncarried_pushes_72h": 0,
         "person_writes_since": 0, "app_pushes_since": 0}
    if converted_at is None:
        out.append("no --converted-at: the time the box writers converted must be given")
    since = now - timedelta(hours=WRITERS_LOOKBACK_H)
    for e in events:
        n["events"] += 1
        kind, who = e.get("activity_type"), str((e.get("actor") or {}).get("login") or "")
        at = _when(e.get("timestamp"))
        if at is None or kind is None:
            out.append(f"an activity row cannot be read: {json.dumps(e)[:120]}")
            continue
        if at < since or kind not in WRITE_TYPES:
            continue
        sha = str(e.get("after") or "")[:9]
        after = converted_at is not None and at >= converted_at
        if who in apps:
            if after and kind in PUSH_TYPES:
                n["app_pushes_since"] += 1
            continue
        if after:
            n["person_writes_since"] += 1
            out.append(f"{who} wrote LIVE after the conversion ({kind} {sha} at {e['timestamp']})")
            continue
        if kind not in PUSH_TYPES:
            continue        # a merge before the conversion: the ruleset governs those from now
        n["person_pushes_72h"] += 1
        files = changed(str(e.get("before") or ""), str(e.get("after") or ""))
        if files is None:
            out.append(f"the paths of {who}'s push {sha} at {e['timestamp']} cannot be read")
            continue
        bad = [f for f in files if not carried(f)]
        if bad:
            n["uncarried_pushes_72h"] += 1
            out.append(f"{who} pushed {sha} at {e['timestamp']} with {len(bad)} path(s) no App "
                       f"carries, e.g. {bad[0]}: that writer is not converted")
    if converted_at is not None:
        watched = (now - converted_at).total_seconds() / 60.0
        if watched < WRITERS_QUIET_MIN:
            out.append(f"only {watched:.0f} min watched since the conversion; "
                       f"{WRITERS_QUIET_MIN} needed")
        if not n["app_pushes_since"]:
            out.append("the state App has not pushed LIVE since the conversion")
    return out, n


def _carried() -> Callable[[str], bool]:
    """The publisher's own path filter, so this check and the App can never disagree."""
    path = Path(__file__).resolve().parents[1] / "publisher" / "publish.py"
    spec = importlib.util.spec_from_file_location("_cr_publish", path)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.publishable  # type: ignore[no-any-return]


def _gh_rows(path: str) -> list[dict[str, Any]]:
    import subprocess

    p = subprocess.run(["gh", "api", "--paginate", path, "--jq", ".[]"], capture_output=True,
                       text=True, check=False)  # fmt: skip
    if p.returncode != 0:
        raise RuntimeError(f"gh api {path}: {p.stderr.strip()[:200]}")
    return [json.loads(line) for line in p.stdout.splitlines() if line.strip()]


def _changed(repo: str) -> Callable[[str, str], list[str] | None]:
    def changed(before: str, after: str) -> list[str] | None:
        if not (before and after) or set(before) == {"0"}:
            return None
        try:
            got = _gh(f"repos/{repo}/compare/{before}...{after}")
        except (RuntimeError, ValueError):
            return None
        files = got.get("files") if isinstance(got, dict) else None
        if not isinstance(files, list) or len(files) >= 300:   # the API caps the list at 300
            return None
        return [str(f.get("filename")) for f in files] + \
            [str(f.get("previous_filename")) for f in files if f.get("previous_filename")]
    return changed


def _opt(args: list[str], flag: str) -> tuple[str | None, list[str]]:
    if flag not in args:
        return None, args
    i = args.index(flag)
    return args[i + 1], args[:i] + args[i + 2:]


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
    state_login, args = _opt(args, "--state-login")
    merger_login, args = _opt(args, "--merger-login")
    conv, args = _opt(args, "--converted-at")
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
        apps = {x for x in (state_login, merger_login) if x}
        if len(apps) != 2 or not all(x.endswith("[bot]") for x in apps):
            got.append("name both Apps' bot logins (--state-login, --merger-login)")
        try:
            rows = _gh_rows(f"repos/{repo}/activity?ref=refs/heads/{LIVE}"
                            "&time_period=week&per_page=100")
            bad, counts = writer_problems(rows, _changed(repo), apps,
                                          _when(conv) if conv else None,
                                          datetime.now(UTC), _carried())
            got += bad
            print("LIVE writers judged: " + ", ".join(f"{k}={v}" for k, v in counts.items()))
        except (RuntimeError, ValueError) as exc:
            got.append(f"could not read LIVE's activity: {exc}")
    for p in got:
        print(f"NOT SAFE: {p}")
    if not got:
        print("SAFE to import")
    return 1 if got else 0


if __name__ == "__main__":
    sys.exit(main())
