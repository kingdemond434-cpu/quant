#!/usr/bin/env python3
"""THE BOX'S STATE, BY PULL REQUEST (Governance + Architecture, 2026-11-14).

    python ops/box/box_state_pr.py --repo C:\\opt\\quant --pending <sha> [--dry-run]

WHY. The box published its state by pushing straight to LIVE every 15 minutes, so any agent on
the box holding that credential could push CODE the same way, and at 13:12Z on 2026-11-14 a CRO
pass did: five commits, no PR. A GitHub rule that refuses every direct push to LIVE closes that,
once the state has another way in. The gate (`audit_gate.merge_box_state`, #1218) merges at once
a PR from a `box-state/` branch opened by the box's own App (`quant-merger[bot]`) whose every
commit that App authored through the API (GitHub-verified) and whose every file is ungoverned
data-shaped box state. This program builds exactly that PR from the commit
`sync_shadow_to_git.ps1` already fences every pass (`refs/publish/pending`: allowlisted state
blobs, login fence and sanitiser applied, one parent = origin's tip).

WHAT IT DOES.
  1. Splits the pending commit's changed paths (pending^..pending) into `pr_ok` paths and the
     rest. The rest -- governed state, rows that grant authority (ADOPT/SEAL clears, RELEASE.json,
     *_ARMED*, HOLD_*, sleeve policy/registry, anything named *approv* / *authority*), switches,
     and any non-data extension -- keep their current route: it makes a local commit of ONLY
     those paths over the same parent and prints its sha as `direct_commit`, which the caller
     pushes as before. Governance designs their gated variant; Evaluate mode lists them.
  2. Mints the quant-merger App token (C:\\opt\\merger\\config.json, the same minting as
     ops/release/merger/merger_env.ps1) for this process only; it is never printed or written.
  3. Through the API, as the App: one blob per path, one tree over LIVE's tip tree, one commit
     (author = the App, signed by GitHub), a `box-state/box-<UTC>` ref, a non-draft PR to LIVE.
  4. Closes the older open box-state PRs carrying the same tag and deletes their refs: each
     snapshot supersedes the last, and two open snapshots of the same files would only conflict.

Exit 0 with one JSON line on stdout: {"pr", "pr_paths", "direct", "direct_commit", "mode"}.
`mode` is "pr", "nothing" (no change against LIVE), or one of three stand-asides, on which
nothing is done and the caller keeps its direct push:
  - "no-gate": the box's adopted gate has no box-state path yet (#1218), so a PR never merges;
  - "no-ci-skip": the adopted ci.yml and release-gates.yml do not yet skip box-state/ heads, so
    each snapshot would cost a full suite run (Governance, 2026-11-14);
  - "no-app": no merger config on this machine.
The PR route therefore switches itself on once both are adopted, with no flag and no tap. Exit 1
on any failure -- the caller logs it and keeps its current route for that pass.
"""

from __future__ import annotations

import argparse
import ast
import base64
import fnmatch
import importlib.util
import json
import os
import re
import subprocess
import sys
import tempfile
import urllib.error
import urllib.request
from collections.abc import Callable, Mapping
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

LIVE = "claude/llm-auto-upgrade-verify-gcjac3"
BRANCH_PREFIX = "box-state/"
#: A FIXED tag, never the machine's name: the repository is public, and the branch name, the
#: commit message and the PR title would publish the host name every 15 minutes (#1219 audit).
BOX_TAG = "box"
MERGER_HOME = Path(r"C:\opt\merger")

#: The gate accepts these extensions only (#1218 after audit). Extensionless files never.
DATA_EXTS = (".json", ".jsonl", ".ndjson", ".csv", ".tsv", ".log", ".txt", ".gz", ".parquet")
#: Never box state on this path, whatever release.py says.
NEVER_PREFIXES = ("docs/", "web/", "context/", ".github/")
#: Files that grant authority or switch behaviour keep their own route (Governance, 2026-11-14),
#: matched case-insensitively against the file NAME.
AUTHORITY_GLOBS = (
    "adopt_clears*", "seal_clears*", "release.json", "*_armed*", "hold_*",
    "*live_sleeve_policy*", "*sleeve_registry*", "*approv*", "*authority*",
    "*_enabled*", "*_disabled*", "*_enforce*", "*_off", "*_off.*", "deactivate*",
    "principal_*", "*kill*", "*_halt*", "*_stop", "*_stop.*", "*override*", "*clears.jsonl",
    "armed_*", "*armed_*", "release_identity*", "gateway_loaded*", "*adopt_*",
)  # fmt: skip
GATE = ".github/scripts/audit_gate.py"
#: The workflows that must skip a box-state/ head before snapshots are opened (Governance,
#: 2026-11-14): without the skip every 15-minute snapshot costs a full suite run.
CI_WORKFLOWS = (".github/workflows/ci.yml", ".github/workflows/release-gates.yml")


def ci_skips_box_state(repo: Path) -> bool:
    """True when every workflow in CI_WORKFLOWS, as the box adopted it, names the box-state/
    prefix (its skip condition). Unreadable is False: the route keeps standing aside."""
    try:
        return all(BRANCH_PREFIX in (repo / w).read_text(encoding="utf-8") for w in CI_WORKFLOWS)
    except OSError:
        return False


def gate_refusals(repo: Path) -> tuple[str, ...] | None:
    """The gate's own BOX_STATE_REFUSED patterns (full lower-case paths), read from the box's
    adopted tree; None while that tree's gate has no box-state path (#1218 not merged and
    adopted), in which case nothing is done and the caller keeps its direct push. Read with ast,
    never imported: the gate is not this program's to execute."""
    try:
        tree = ast.parse((repo / GATE).read_text(encoding="utf-8"))
    except (OSError, SyntaxError, ValueError):
        return None
    names = {n.name for n in tree.body if isinstance(n, ast.FunctionDef)}
    if "merge_box_state" not in names:
        return None
    for node in tree.body:
        if isinstance(node, ast.Assign | ast.AnnAssign):
            targets = node.targets if isinstance(node, ast.Assign) else [node.target]
            if any(isinstance(t, ast.Name) and t.id == "BOX_STATE_REFUSED" for t in targets):
                try:
                    val = ast.literal_eval(node.value) if node.value is not None else None
                except ValueError:
                    return None
                if isinstance(val, tuple) and all(isinstance(v, str) for v in val):
                    return tuple(v.lower() for v in val)
    return None


Api = Callable[[str, str, Mapping[str, Any] | None], Any]


def _release(repo: Path) -> Any:
    """libs/ops/release.py from the box's own checkout (adopted, sealed code), loaded by path."""
    spec = importlib.util.spec_from_file_location("_box_release", repo / "libs/ops/release.py")
    if spec is None or spec.loader is None:
        raise RuntimeError("libs/ops/release.py cannot be loaded")
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


def pr_ok(rel: str, release: Any, refused: tuple[str, ...] = ()) -> bool:
    """True when `rel` may travel on a box-state PR: ungoverned box state, data-shaped, granting
    no authority, refused by none of the gate's own patterns (`refused`). Anything unsure is
    False and keeps its current route."""
    p = str(rel).replace("\\", "/")
    low = p.lower()
    if not p or p.startswith(("/", "./")) or ".." in p.split("/") or "/secrets/" in f"/{low}":
        return False
    if low.startswith(NEVER_PREFIXES) or not low.endswith(DATA_EXTS):
        return False
    name = low.rsplit("/", 1)[-1]
    if any(fnmatch.fnmatchcase(name, g) for g in AUTHORITY_GLOBS):
        return False
    if any(fnmatch.fnmatchcase(low, g) for g in refused):
        return False
    return bool(release.is_state_path(p)) and not bool(release.is_governed_state(p))


def git(
    repo: Path, *args: str, env: Mapping[str, str] | None = None, data: bytes | None = None
) -> bytes:
    p = subprocess.run(["git", "-c", "safe.directory=*", "-C", str(repo), *args], input=data,
                       capture_output=True, env=dict(env) if env is not None else None,
                       check=False, timeout=120)  # fmt: skip
    if p.returncode != 0:
        raise RuntimeError(f"git {' '.join(args[:2])}: {p.stderr.decode(errors='replace')[:300]}")
    return p.stdout


def changed(repo: Path, pending: str) -> tuple[str, list[tuple[str, str]]]:
    """(parent, [(status, path)]) of the pending commit against its one parent."""
    parents = git(repo, "rev-list", "--parents", "-n", "1", pending).decode().split()
    if len(parents) != 2:
        raise RuntimeError(f"pending {pending[:12]} must have exactly one parent")
    rows = (
        git(repo, "diff-tree", "--no-renames", "--name-status", "-r", "-z", parents[1], pending)
        .decode()
        .split("\0")
    )
    out = [(rows[i], rows[i + 1]) for i in range(0, len(rows) - 1, 2) if rows[i]]
    return parents[1], out


def direct_commit(repo: Path, parent: str, pending: str, paths: list[str]) -> str:
    """A local commit of ONLY `paths` (as the pending commit has them) over `parent`; the
    caller pushes it by its current route. A private index: the shared one is never touched."""
    fd, idx = tempfile.mkstemp(prefix="box-state-direct-")
    os.close(fd)
    env = {**os.environ, "GIT_INDEX_FILE": idx}
    try:
        git(repo, "read-tree", parent, env=env)
        lines = []
        for path in paths:
            ent = git(repo, "ls-tree", pending, "--", path).decode().strip()
            if ent:
                lines.append(ent)  # "<mode> blob <sha>\t<path>"
            else:
                lines.append(f"0 {'0' * 40}\t{path}")  # deleted in pending
        git(repo, "update-index", "--index-info", env=env, data=("\n".join(lines) + "\n").encode())
        tree = git(repo, "write-tree", env=env).decode().strip()
    finally:
        Path(idx).unlink(missing_ok=True)
    msg = "mt5 box state (governed/authority paths; their own route until the gated variant)"
    return git(repo, "commit-tree", tree, "-p", parent, "-m", msg).decode().strip()


def mint_token(repo: Path, home: Path = MERGER_HOME) -> str | None:
    """The quant-merger App token, or None when this machine has no merger config."""
    cfg_path = home / "config.json"
    if not cfg_path.is_file():
        return None
    cfg = json.loads(cfg_path.read_text(encoding="utf-8-sig"))
    p = subprocess.run([str(cfg["python"]), "-I",
                        str(repo / "ops/release/authority/mint_app_token.py"),
                        "--app-id", str(cfg["app_id"]),
                        "--installation-id", str(cfg["installation_id"]),
                        "--key", str(home / "key" / "app.pem")],
                       capture_output=True, text=True, check=False, timeout=60)  # fmt: skip
    tok = p.stdout.strip()
    if p.returncode != 0 or not tok:
        raise RuntimeError("the quant-merger App token could not be minted")
    return tok


def _keyed_sources(repo: Path) -> Any:
    """libs/data/keyed_sources.py from the box's own checkout, loaded by path (stdlib only)."""
    spec = importlib.util.spec_from_file_location(
        "_box_keyed_sources", repo / "libs/data/keyed_sources.py"
    )
    if spec is None or spec.loader is None:
        raise RuntimeError("libs/data/keyed_sources.py cannot be loaded")
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


def github_api(token: str, repo: Path) -> Api:
    """API calls as the App. Every request goes through keyed_urlopen, so the token never follows
    a redirect to another host (the desk's keyed-fetch fence)."""
    ks = _keyed_sources(repo)

    def call(method: str, path: str, body: Mapping[str, Any] | None = None) -> Any:
        req = urllib.request.Request(
            f"https://api.github.com/{path}",
            method=method,
            data=None if body is None else json.dumps(body).encode(),
            headers={
                "Authorization": f"Bearer {token}",
                "Accept": "application/vnd.github+json",
                "X-GitHub-Api-Version": "2022-11-28",
                "User-Agent": "quant-box-state",
            },
        )
        try:
            with ks.keyed_urlopen(req, timeout=60, secrets=[token]) as r:
                raw = r.read()
        except urllib.error.HTTPError as exc:
            raise RuntimeError(f"{method} {path}: HTTP {exc.code}") from exc
        return json.loads(raw) if raw.strip() else None

    return call


def slug(repo: Path) -> str:
    url = git(repo, "remote", "get-url", "origin").decode().strip()
    m = re.search(r"github\.com[:/]+([^/]+/[^/]+?)(?:\.git)?/?$", url)
    if not m:
        raise RuntimeError("origin is not a github.com repository")
    return m.group(1)


def publish(
    repo: Path,
    pending: str,
    api: Api,
    gh_repo: str,
    *,
    tag: str = BOX_TAG,
    now: datetime | None = None,
    base: str = LIVE,
    release: Any = None,
    refused: tuple[str, ...] = (),
) -> dict[str, Any]:
    """Open the box-state PR for the pending commit's pr_ok paths (see the module docstring)."""
    release = release if release is not None else _release(repo)
    parent, rows = changed(repo, pending)
    pr_paths = sorted(p for _, p in rows if pr_ok(p, release, refused))
    direct = sorted(p for _, p in rows if p not in pr_paths)
    out: dict[str, Any] = {
        "pr": None,
        "pr_paths": pr_paths,
        "direct": direct,
        "direct_commit": None,
        "mode": "nothing",
    }
    if direct:
        out["direct_commit"] = direct_commit(repo, parent, pending, direct)
    if not pr_paths:
        return out
    tip = api("GET", f"repos/{gh_repo}/git/ref/heads/{base}", None)["object"]["sha"]
    tip_tree = api("GET", f"repos/{gh_repo}/git/commits/{tip}", None)["tree"]["sha"]
    status = {p: s for s, p in rows}
    entries: list[dict[str, Any]] = []
    for path in pr_paths:
        if status.get(path) == "D":
            entries.append({"path": path, "mode": "100644", "type": "blob", "sha": None})
            continue
        data = git(repo, "cat-file", "blob", f"{pending}:{path}")
        blob = api(
            "POST",
            f"repos/{gh_repo}/git/blobs",
            {"content": base64.b64encode(data).decode(), "encoding": "base64"},
        )
        entries.append({"path": path, "mode": "100644", "type": "blob", "sha": blob["sha"]})
    tree = api("POST", f"repos/{gh_repo}/git/trees", {"base_tree": tip_tree, "tree": entries})
    if tree["sha"] == tip_tree:
        return out  # LIVE already carries it
    stamp = (now or datetime.now(tz=UTC)).strftime("%Y%m%dT%H%M%SZ")
    if not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", tag):
        raise ValueError("the box-state tag must be lower-case letters, digits and dashes")
    host_tag = tag
    msg = f"mt5 box state {stamp} ({len(pr_paths)} path(s), {host_tag})"
    commit = api(
        "POST",
        f"repos/{gh_repo}/git/commits",
        {"message": msg, "tree": tree["sha"], "parents": [tip]},
    )
    ref = f"{BRANCH_PREFIX}{host_tag}-{stamp}"
    api("POST", f"repos/{gh_repo}/git/refs", {"ref": f"refs/heads/{ref}", "sha": commit["sha"]})
    pr = api(
        "POST",
        f"repos/{gh_repo}/pulls",
        {
            "title": msg,
            "head": ref,
            "base": base,
            "draft": False,
            "body": (
                "The box's ungoverned state, made by the box's App through the API "
                "(ops/box/box_state_pr.py). The gate merges it on the box-state path; "
                f"{len(direct)} governed/authority path(s) kept their own route."
            ),
        },
    )
    out.update(pr=pr["number"], mode="pr")
    mine = f"{BRANCH_PREFIX}{host_tag}-"
    for old in api("GET", f"repos/{gh_repo}/pulls?state=open&base={base}&per_page=100", None):
        head = str((old.get("head") or {}).get("ref") or "")
        if head.startswith(mine) and old.get("number") != pr["number"]:
            api("PATCH", f"repos/{gh_repo}/pulls/{old['number']}", {"state": "closed"})
            api("DELETE", f"repos/{gh_repo}/git/refs/heads/{head}", None)
    return out


def _stand_aside(mode: str) -> dict[str, Any]:
    return {"mode": mode, "pr": None, "pr_paths": [], "direct": [], "direct_commit": None}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--repo", type=Path, required=True)
    ap.add_argument("--pending", required=True)
    ap.add_argument("--base", default=LIVE)
    ap.add_argument(
        "--dry-run", action="store_true", help="split and print the plan; mint nothing, call no API"
    )
    a = ap.parse_args(argv)
    try:
        refused = gate_refusals(a.repo)
        if refused is None:  # this tree's gate cannot merge a box-state PR yet
            print(json.dumps(_stand_aside("no-gate")))
            return 0
        if not ci_skips_box_state(a.repo):  # each snapshot would cost a full CI run
            print(json.dumps(_stand_aside("no-ci-skip")))
            return 0
        if a.dry_run:
            rel = _release(a.repo)
            _, rows = changed(a.repo, a.pending)
            ok = sorted(p for _, p in rows if pr_ok(p, rel, refused))
            plan = {
                "mode": "dry-run",
                "pr_paths": ok,
                "direct": [p for _, p in rows if p not in ok],
            }
            print(json.dumps(plan))
            return 0
        tok = mint_token(a.repo)
        if tok is None:
            print(json.dumps(_stand_aside("no-app")))
            return 0
        res = publish(
            a.repo,
            a.pending,
            github_api(tok, a.repo),
            slug(a.repo),
            base=a.base,
            refused=refused,
        )
    except Exception as exc:  # the caller keeps its current route for this pass
        print(json.dumps({"mode": "failed", "error": f"{type(exc).__name__}: {exc}"[:400]}))
        return 1
    print(json.dumps(res))
    return 0


if __name__ == "__main__":
    sys.exit(main())
