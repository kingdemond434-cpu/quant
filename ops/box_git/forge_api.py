"""THE AUDIT GATE, POINTED AT THE BOX FORGE: GitHub REST calls answered by the box's Gitea.

WHY (principal 2026-11-19: "nothing should rely on GitHub at all"). The merge rules live in
.github/scripts/audit_gate.py and have been audited for weeks: CLEAR at the exact head, HOLD
beats green, gating jobs, ROOT needs zuck's own line, standing approval, registry/authority paths,
pinned merges. Rewriting them for a new host would be a new, unaudited gate. Instead the gate's
one transport, `_gh(path, ...)`, is answered here when QUANT_FORGE_URL is set: each GitHub path the
gate uses is translated to the forge's API and the answer is reshaped to GitHub's fields. The RULES
are untouched; only where the facts come from changes.

TRUST, WHICH IS THE WHOLE POINT, IS RE-ANCHORED EXPLICITLY:
  * CI. A GitHub check run counted only if GitHub Actions posted it from the right workflow. Here a
    commit status counts only if the forge says its CREATOR is the box CI account (BOX_CI_USER),
    whose token never leaves the box. Statuses from anyone else -- the `claude` account included --
    are dropped before the gate sees them, so a thread can never post its own green.
  * zuck's own words. GitHub told the gate a comment came through an App (a Claude session). Here
    every comment by a non-owner account is marked as App-posted, and only the forge OWNER
    accounts (OWNER_USERS) read as OWNER. The `claude` account is a COLLABORATOR, never the owner.
  * Anything the shim cannot answer truthfully RAISES (RuntimeError), which the gate already
    treats as "not this sweep" for that PR: it fails closed, never open.
"""
from __future__ import annotations

import json
import os
import re
import ssl
import subprocess
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Callable, Mapping
from typing import Any

FORGE_URL_ENV = "QUANT_FORGE_URL"          # https://127.0.0.1:3443
FORGE_TOKEN_FILE_ENV = "QUANT_FORGE_TOKEN_FILE"  # noqa: S105 (a variable name, not a secret)
FORGE_CA_ENV = "QUANT_FORGE_CA"            # the forge's own certificate (pinned)
FORGE_BARE_ENV = "QUANT_FORGE_BARE"        # the forge repo's bare path, for compare/ancestry
FORGE_REPO = "quant/quant"
BOX_CI_USER = "box-ci"
OWNER_USERS = frozenset({"quant-admin"})
CI_APP = "github-actions"

Transport = Callable[[str, str, Any], Any]


def enabled(env: Mapping[str, str] | None = None) -> bool:
    return bool((env if env is not None else os.environ).get(FORGE_URL_ENV))


def _status_state(state: str) -> tuple[str, str | None]:
    s = (state or "").lower()
    if s in ("pending", "running", "waiting", "queued"):
        return "in_progress", None
    return "completed", {"success": "success", "failure": "failure", "error": "failure",
                         "warning": "failure", "skipped": "skipped"}.get(s, "failure")


def _comment(c: Mapping[str, Any]) -> dict[str, Any]:
    login = str((c.get("user") or {}).get("login") or "")
    owner = login in OWNER_USERS
    return {**c, "author_association": "OWNER" if owner else "COLLABORATOR",
            "performed_via_github_app": None if owner else {"slug": f"forge:{login}"}}


class Forge:
    def __init__(self, transport: Transport, *, workflow_of: Mapping[str, str],
                 bare: str | None = None, approvals_issue: int | None = None,
                 git: Callable[..., str] | None = None) -> None:
        self.t = transport
        self.workflow_of = dict(workflow_of)
        self.bare = bare
        self.approvals_issue = approvals_issue
        self._git = git or self._run_git
        self._statuses: dict[str, list[dict[str, Any]]] = {}

    # ------------------------------------------------------------------ plumbing
    def _run_git(self, *args: str) -> str:
        if not self.bare:
            raise RuntimeError("forge: no bare repository configured for git questions")
        p = subprocess.run(["git", "-C", self.bare, *args], capture_output=True, text=True,
                           timeout=60, check=False)
        if p.returncode != 0:
            raise RuntimeError(f"forge git {' '.join(args)}: {p.stderr.strip()[:200]}")
        return p.stdout.strip()

    def _all(self, path: str) -> list[Any]:
        out: list[Any] = []
        page = 1
        while True:
            sep = "&" if "?" in path else "?"
            got = self.t("GET", f"{path}{sep}limit=50&page={page}", None) or []
            if not isinstance(got, list):
                raise RuntimeError(f"forge: {path} did not answer a list")
            out += got
            if len(got) < 50 or page >= 60:
                return out
            page += 1

    def _box_ci_statuses(self, sha: str) -> list[dict[str, Any]]:
        if sha not in self._statuses:
            rows = self._all(f"/repos/{FORGE_REPO}/commits/{sha}/statuses")
            self._statuses[sha] = [
                r for r in rows if str((r.get("creator") or {}).get("login") or "") == BOX_CI_USER]
        return self._statuses[sha]

    def _check_runs(self, sha: str) -> dict[str, Any]:
        runs = []
        for s in self._box_ci_statuses(sha):
            status, conclusion = _status_state(str(s.get("status") or s.get("state") or ""))
            rid = int(s.get("id") or 0)
            runs.append({"id": rid, "name": s.get("context"), "status": status,
                         "conclusion": conclusion, "head_sha": sha,
                         "started_at": s.get("created_at") or s.get("updated_at"),
                         "app": {"slug": CI_APP}, "check_suite": {"id": rid},
                         "output": {"summary": s.get("description") or ""}})
        return {"total_count": len(runs), "check_runs": runs}

    # ------------------------------------------------------------------ the GitHub surface
    def gh(self, *args: str, data: Mapping[str, Any] | None = None) -> Any:
        path, method, slurp = args[0], "GET", "--slurp" in args
        if "-X" in args:
            method = args[list(args).index("-X") + 1]
        url = urllib.parse.urlsplit(path)
        q = dict(urllib.parse.parse_qsl(url.query))
        p = url.path
        m = re.fullmatch(r"repos/[^/]+/[^/]+/(.*)", p)
        if not m:
            raise RuntimeError(f"forge: no translation for {path}")
        rest = m.group(1)
        out = self._route(method, rest, q, data)
        return [out] if slurp else out

    def _route(self, method: str, rest: str, q: Mapping[str, str],
               data: Mapping[str, Any] | None) -> Any:
        R = f"/repos/{FORGE_REPO}"
        if method == "GET" and rest == "pulls":
            rows = self._all(f"{R}/pulls?state={q.get('state', 'open')}")
            base = q.get("base")
            return [r for r in rows if not base or (r.get("base") or {}).get("ref") == base]
        if mm := re.fullmatch(r"pulls/(\d+)", rest):
            return self.t("GET", f"{R}/pulls/{mm.group(1)}", None)
        if mm := re.fullmatch(r"pulls/(\d+)/files", rest):
            return self._all(f"{R}/pulls/{mm.group(1)}/files")
        if mm := re.fullmatch(r"issues/(\d+)/comments", rest):
            n = int(mm.group(1))
            if n == 453 and self.approvals_issue:
                n = self.approvals_issue
            return [_comment(c) for c in self._all(f"{R}/issues/{n}/comments")]
        if mm := re.fullmatch(r"commits/([0-9a-f]{40})/check-runs", rest):
            return self._check_runs(mm.group(1))
        if method == "GET" and rest == "actions/runs" and "check_suite_id" in q:
            return self._suite_runs(int(q["check_suite_id"]))
        if mm := re.fullmatch(r"actions/runs/(\d+)/jobs", rest):
            return {"jobs": [{"id": int(mm.group(1))}]}
        if mm := re.fullmatch(r"compare/([^.]+)\.\.\.(.+)", rest):
            return self._compare(mm.group(1), mm.group(2))
        if mm := re.fullmatch(r"pulls/(\d+)/merge", rest):
            d = dict(data or {})
            body = {"Do": d.get("merge_method") or "merge", "head_commit_id": d.get("sha"),
                    "MergeTitleField": d.get("commit_title") or "",
                    "MergeMessageField": d.get("commit_message") or ""}
            if not body["head_commit_id"]:
                raise RuntimeError("forge: a merge must be pinned to the head sha")
            return self.t("POST", f"{R}/pulls/{mm.group(1)}/merge", body)
        if mm := re.fullmatch(r"pulls/(\d+)/update-branch", rest):
            return self.t("POST", f"{R}/pulls/{mm.group(1)}/update", {})
        if mm := re.fullmatch(r"statuses/([0-9a-f]{40})", rest):
            return self.t("POST", f"{R}/statuses/{mm.group(1)}", dict(data or {}))
        if method == "GET" and rest == "commits":
            sha = q.get("sha", "")
            rows = self.t("GET", f"{R}/commits?sha={urllib.parse.quote(sha)}&limit="
                                 f"{q.get('per_page', '30')}", None) or []
            return rows
        if rest.startswith("issues/") and "/labels" in rest:
            return self._labels(method, rest, data)
        if rest == "actions/workflows/ci.yml/dispatches":
            return None  # box CI starts its own full run on every LIVE move; nothing to dispatch
        raise RuntimeError(f"forge: {method} {rest} has no truthful translation; failing closed")

    def _suite_runs(self, sid: int) -> dict[str, Any]:
        for sha, rows in self._statuses.items():
            for s in rows:
                if int(s.get("id") or 0) == sid:
                    return {"workflow_runs": [{
                        "id": sid, "path": self.workflow_of.get(str(s.get("context") or ""), ""),
                        "head_sha": sha, "event": "push", "pull_requests": []}]}
        return {"workflow_runs": []}

    def _compare(self, a: str, b: str) -> dict[str, Any]:
        ahead = int(self._git("rev-list", "--count", f"{a}..{b}") or 0)
        behind = int(self._git("rev-list", "--count", f"{b}..{a}") or 0)
        status = ("identical" if not ahead and not behind else "ahead" if not behind
                  else "behind" if not ahead else "diverged")
        return {"status": status, "ahead_by": ahead, "behind_by": behind}

    def _labels(self, method: str, rest: str, data: Mapping[str, Any] | None) -> Any:
        R = f"/repos/{FORGE_REPO}"
        mm = re.fullmatch(r"issues/(\d+)/labels(?:/(.+))?", rest)
        if not mm:
            raise RuntimeError(f"forge: label path {rest}")
        n, name = mm.group(1), mm.group(2)
        ids = {str(lab.get("name")): lab.get("id") for lab in self._all(f"{R}/labels")}
        if method == "DELETE" and name:
            lid = ids.get(urllib.parse.unquote(name))
            return None if lid is None else self.t("DELETE", f"{R}/issues/{n}/labels/{lid}", None)
        want = [ids[x] for x in (data or {}).get("labels", []) if x in ids]
        return self.t("POST", f"{R}/issues/{n}/labels", {"labels": want})


def http_transport(env: Mapping[str, str] | None = None) -> Transport:
    """The real transport: HTTPS to the forge with its own pinned certificate and a box token."""
    e = env if env is not None else os.environ
    base = e[FORGE_URL_ENV].rstrip("/") + "/api/v1"
    with open(e[FORGE_TOKEN_FILE_ENV], encoding="utf-8") as fh:
        token = fh.read().strip()
    ctx = ssl.create_default_context(cafile=e.get(FORGE_CA_ENV) or None)
    ctx.check_hostname = False  # the pinned self-signed certificate is the identity (no CA chain)

    def call(method: str, path: str, body: Any) -> Any:
        req = urllib.request.Request(base + path, method=method,
                                     data=None if body is None else json.dumps(body).encode(),
                                     headers={"Authorization": f"token {token}",
                                              "Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=60, context=ctx) as r:
                raw = r.read()
        except urllib.error.HTTPError as exc:
            raise RuntimeError(f"forge {method} {path}: HTTP {exc.code}") from exc
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            raise RuntimeError(f"forge {method} {path}: {exc}") from exc
        return json.loads(raw) if raw.strip() else None

    return call
