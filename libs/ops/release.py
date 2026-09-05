"""One canonical live release: every decision on the desk names the SHA it was made under.

    CODE_SHA (= LIVE_SHA)    the commit the release was sealed from -- HEAD at seal time
    TREE_SHA / PARENT_SHA    that commit's tree and parent, for the record
    CONFIG_HASH              sizing constants + heat law
    SURVIVOR_REGISTRY_HASH   the canonical survivor file (and CANON_SHA256, the full digest)
    ALLOCATOR_HASH           the allocator, the proof, the heat policy
    MONEY_PATH_HASH          every module that places, sizes or vetoes an order (+ per file)
    IMMUTABLE_MANIFEST       the signed judge manifest's digest, signer and signing time
    ALLOCATOR_CERTIFICATE    the proof certificate present at seal time, if any
    DEPENDENCY_HASH          pyproject's dependency tables
    DATA_SCHEMA_VERSION      the PIT stamp fields and the feature-store code version

THE CHICKEN AND THE EGG. A manifest cannot contain the SHA of the commit that contains it: a
commit's SHA hashes its tree, and the tree includes the manifest. Until 2026-09-05 RELEASE.json
was generated from a tree and then committed together with the next batch of code, so
`live_sha` always named the commit BEFORE the one that shipped -- the audit found
`live_sha = 38688f5...` against an integrated head of `f9fd6a26`, and nothing the desk stamped on
a fill could be traced to the code that produced it.

The way out is to make the seal a commit of its own. `seal()` records `code_sha = HEAD` and hashes
the tracked files AT THAT COMMIT -- read from git's objects, never from the working tree, so a
dirty checkout cannot leak into the record -- and the commit that carries the manifest must touch
nothing else. `accepts()` then admits a running SHA S in exactly two cases: S == code_sha, or the
diff code_sha..S touches only paths in `NON_CODE` -- the manifest itself (the pure seal commit)
and the state files the Windows box commits on top of it every fifteen minutes. Any other path in
that diff is code the release never named, and the gateway refuses new risk until a fresh seal
lands. That is the invariant the principal asked for, stated so a machine can check it:

    running box SHA == RELEASE.code_sha == signed money-path SHA == tested SHA == merged SHA

`release_id()` is the short hash the gateway stamps on every intent and every decision;
`verify()` says whether the working tree the process runs in still matches the sealed release --
the state fence with no ambiguity about which SHA is live.
"""
from __future__ import annotations

import hashlib
import json
import os
import subprocess
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
DESK = ROOT / "desks" / "mt5"
RELEASE = DESK / "data" / "RELEASE.json"
RELEASE_REL = "desks/mt5/data/RELEASE.json"

#: Every module that places, sizes, vetoes or promotes. Widened 2026-09-05 to the modules the
#: box-side smoke test imports: the scalp executor, netting, the execution policy and registry,
#: the family compiler and the shadow/forward chain all decide what reaches the broker.
MONEY_PATH: tuple[str, ...] = (
    "desks/mt5/mt5desk/gateway.py", "desks/mt5/mt5desk/decision_core.py",
    "desks/mt5/mt5desk/sizing.py",
    "desks/mt5/mt5desk/gateway_config_fallback.py", "desks/mt5/mt5desk/engine.py",
    "desks/mt5/mt5desk/independence.py", "desks/mt5/mt5desk/scalp_exec.py",
    "desks/mt5/mt5desk/netting.py", "desks/mt5/mt5desk/execution_policy.py",
    "desks/mt5/mt5desk/execution_registry.py", "desks/mt5/mt5desk/families.py",
    "desks/mt5/research/pf_allocator.py", "desks/mt5/research/heat_policy.py",
    "desks/mt5/research/promoter.py", "desks/mt5/research/shadow_forward.py",
    "desks/mt5/research/scalp_shadow.py", "desks/mt5/research/forward_verdict.py",
    "desks/mt5/research/sleeve_registry.py",
    "libs/portfolio/robust_elog.py", "libs/portfolio/allocator_proof.py",
    "libs/portfolio/rails.py", "libs/portfolio/capital_modifiers.py",
)
CONFIG_FILES: tuple[str, ...] = ("desks/mt5/mt5desk/gateway_config_fallback.py",
                                 "desks/mt5/research/heat_policy.py")
ALLOCATOR_FILES: tuple[str, ...] = ("desks/mt5/research/pf_allocator.py",
                                    "libs/portfolio/robust_elog.py",
                                    "libs/portfolio/allocator_proof.py",
                                    "desks/mt5/research/heat_policy.py")
SURVIVORS = "desks/mt5/data/UNIVERSAL_SURVIVORS.canon.json"
IMMUTABLE_MANIFEST = "desks/mt5/data/IMMUTABLE_MANIFEST.json"
ALLOCATOR_PROOF = "desks/mt5/reports/ALLOCATOR_PROOF.json"
PYPROJECT = "pyproject.toml"
DATA_SCHEMA_VERSION = "pit-1;features-2026-09-04.1"

#: Paths a commit may touch and still be "the same code" as the sealed commit. The manifest
#: itself (the pure seal commit) and the files the Windows box WRITES and commits through
#: sync_shadow_to_git.ps1 every fifteen minutes: outputs of the running code, never inputs that
#: change what it does. Anything else in `git diff code_sha..HEAD` is unreleased code.
NON_CODE: frozenset[str] = frozenset({
    RELEASE_REL,
    "desks/mt5/data/release_identity.json",
    "desks/mt5/reports/shadow/shadow_health.json",
    "desks/mt5/data/gateway_state.json",
    "desks/mt5/data/sleeves.json",
    "desks/mt5/data/regime_state.json",
})

SEAL_RULE = ("a running SHA is accepted iff it equals code_sha, or `git diff --name-only "
             "code_sha HEAD` touches only NON_CODE paths (the pure seal commit and the box's "
             "own state-sync commits); anything else is unreleased code and refuses new risk")


# --------------------------------------------------------------------------------- git / files
def _git(args: list[str], root: Path, timeout: float = 10.0) -> str | None:
    """stdout of a git command, or None when git is absent, times out, or exits non-zero."""
    try:
        r = subprocess.run(["git", "-c", "core.quotepath=off", *args], cwd=root,
                           capture_output=True, text=True, timeout=timeout)
    except (OSError, subprocess.SubprocessError):
        return None
    return r.stdout if r.returncode == 0 else None


def _root(root: Path | None) -> Path:
    return ROOT if root is None else root


def _release_path(root: Path | None) -> Path:
    # The module-level RELEASE is what tests monkeypatch; an explicit root names its own file.
    return RELEASE if root is None else root / Path(*RELEASE_REL.split("/"))


def git_head(root: Path | None = None) -> str:
    out = _git(["rev-parse", "HEAD"], _root(root))
    return (out or "").strip() or "unknown"


def _rev(spec: str, root: Path) -> str | None:
    out = _git(["rev-parse", "--verify", "--quiet", spec], root)
    return (out or "").strip() or None


def _norm(b: bytes) -> bytes:
    """CRLF-insensitive. The Windows box checks out with autocrlf, so a byte-exact digest of a
    working file would differ from the LF blob the seal hashed and refuse every release."""
    return b.replace(b"\r\n", b"\n")


def _read(rel: str, root: Path, commit: str | None) -> bytes | None:
    """File bytes from the working tree (commit None) or from git's objects at `commit`."""
    if commit is None:
        try:
            return (root / Path(*rel.split("/"))).read_bytes()
        except OSError:
            return None
    try:
        r = subprocess.run(["git", "show", f"{commit}:{rel}"], cwd=root, capture_output=True,
                           timeout=10)
    except (OSError, subprocess.SubprocessError):
        return None
    return r.stdout if r.returncode == 0 else None


def hash_paths(paths: tuple[str, ...] | list[str], root: Path | None = None,
               commit: str | None = None) -> str:
    """The keyed digest of a file set. Mirrored byte-for-byte in mt5desk/release_identity.py,
    which must not import this package; a test pins the two together."""
    r = _root(root)
    h = hashlib.sha256()
    for rel in sorted(paths):
        h.update(rel.encode())
        b = _read(rel, r, commit)
        h.update(_norm(b) if b is not None else b"<absent>")
    return h.hexdigest()[:16]


def _file_sha256(rel: str, root: Path, commit: str | None) -> str | None:
    b = _read(rel, root, commit)
    return hashlib.sha256(_norm(b)).hexdigest() if b is not None else None


def _dependency_hash(root: Path, commit: str | None) -> str | None:
    """pyproject's dependency tables only, so a docstring edit in pyproject does not read as a
    dependency change; the raw bytes when the file will not parse."""
    b = _read(PYPROJECT, root, commit)
    if b is None:
        return None
    try:
        import tomllib
        proj = tomllib.loads(b.decode("utf-8")).get("project", {})
        body = {"requires-python": proj.get("requires-python"),
                "dependencies": proj.get("dependencies"),
                "optional-dependencies": proj.get("optional-dependencies")}
        return hashlib.sha256(json.dumps(body, sort_keys=True).encode()).hexdigest()[:16]
    except (ValueError, UnicodeDecodeError):
        return hashlib.sha256(_norm(b)).hexdigest()[:16]


def _immutable_manifest(root: Path, commit: str | None) -> dict[str, Any] | None:
    b = _read(IMMUTABLE_MANIFEST, root, commit)
    if b is None:
        return None
    out: dict[str, Any] = {"sha256_16": hashlib.sha256(_norm(b)).hexdigest()[:16]}
    try:
        doc = json.loads(b.decode("utf-8"))
        out.update(signed_utc=doc.get("signed_utc"), signed_by=doc.get("signed_by"),
                   n_files=len(doc.get("files") or {}))
    except (ValueError, UnicodeDecodeError):
        out["note"] = "manifest present but unparseable"
    return out


def _allocator_certificate(root: Path) -> dict[str, Any] | None:
    """Working tree only: reports/ is untracked, so there is no blob to read at a commit."""
    b = _read(ALLOCATOR_PROOF, root, None)
    if b is None:
        return None
    out: dict[str, Any] = {"sha256_16": hashlib.sha256(_norm(b)).hexdigest()[:16]}
    try:
        doc = json.loads(b.decode("utf-8"))
        out.update(passed=bool(doc.get("passed")), at=doc.get("at"))
    except (ValueError, UnicodeDecodeError):
        out["note"] = "certificate present but unparseable"
    return out


def dirty_paths(root: Path | None = None) -> list[str]:
    """Tracked files that differ from HEAD, the manifest excluded. Untracked files are not
    listed: the box writes hundreds of artifacts and none of them is code."""
    out = _git(["status", "--porcelain", "--untracked-files=no"], _root(root))
    if not out:
        return []
    paths = []
    for ln in out.splitlines():
        if len(ln) < 4:
            continue
        p = ln[3:].split(" -> ")[-1].strip().strip('"')
        if p and p != RELEASE_REL:
            paths.append(p)
    return sorted(paths)


# ------------------------------------------------------------------------------------ build
def _describe(root: Path, commit: str | None) -> dict[str, Any]:
    """The release record for the working tree (commit None) or for one commit's blobs."""
    sha = commit or git_head(root)
    doc: dict[str, Any] = {
        "generated_utc": datetime.now(tz=UTC).isoformat(), "live_sha": sha, "code_sha": sha,
        "parent_sha": _rev(f"{sha}^", root) if sha != "unknown" else None,
        "tree_sha": _rev(f"{sha}^{{tree}}", root) if sha != "unknown" else None,
        "config_hash": hash_paths(CONFIG_FILES, root, commit),
        "survivor_registry_hash": hash_paths((SURVIVORS,), root, commit),
        "allocator_hash": hash_paths(ALLOCATOR_FILES, root, commit),
        "money_path_hash": hash_paths(MONEY_PATH, root, commit),
        "data_schema_version": DATA_SCHEMA_VERSION, "money_path": list(MONEY_PATH),
        "money_path_files": {rel: hash_paths((rel,), root, commit) for rel in MONEY_PATH},
        "canon_sha256": _file_sha256(SURVIVORS, root, commit),
        "immutable_manifest": _immutable_manifest(root, commit),
        "allocator_certificate": _allocator_certificate(root),
        "dependency_hash": _dependency_hash(root, commit),
        "seal_rule": SEAL_RULE, "non_code": sorted(NON_CODE),
    }
    # The stamped id keeps its 2026-09-04 formula so an unchanged tree keeps its release_id.
    doc["release_id"] = hashlib.sha256(json.dumps(
        {k: doc[k] for k in ("live_sha", "config_hash", "survivor_registry_hash",
                             "allocator_hash", "money_path_hash", "data_schema_version")},
        sort_keys=True).encode()).hexdigest()[:12]
    return doc


def _write(doc: dict[str, Any], root: Path | None) -> None:
    p = _release_path(root)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(doc, indent=1), "utf-8")


def build(write: bool = True, *, root: Path | None = None) -> dict[str, Any]:
    """Describe the WORKING TREE under HEAD. Not a seal: the hashes are of whatever is on disk,
    which is what `verify()` needs to compare against. Kept for the callers that predate
    sealing; a release that is meant to be run comes from `seal()`."""
    r = _root(root)
    doc = _describe(r, None)
    doc["sealed"] = False
    if write:
        _write(doc, root)
    return doc


def seal(*, root: Path | None = None, tested: bool = False, by: str | None = None,
         allow_dirty: bool = False, write: bool = True) -> dict[str, Any]:
    """Seal HEAD: every hash is taken from the commit's own blobs, so the record names exactly
    the code the commit carries whatever the checkout looks like. The caller then commits
    RELEASE.json ALONE -- that commit is the pure seal `accepts()` recognises.

    `tested` attests that the suite ran green on this SHA before sealing (CI passes it after the
    test jobs; an operator sealing by hand does not get to claim it by default). A dirty tree is
    refused unless `allow_dirty`, in which case the dirty paths are recorded rather than hidden:
    the seal is still exact, but the operator should know their screen is not what they sealed.
    """
    r = _root(root)
    head = git_head(r)
    if head == "unknown":
        raise RuntimeError("cannot seal: git HEAD is unknown here (no git, or not a repository)")
    dirty = dirty_paths(r)
    if dirty and not allow_dirty:
        raise RuntimeError(f"cannot seal a dirty tree ({len(dirty)} tracked path(s) differ from "
                           f"HEAD: {dirty[:5]}); commit them or pass allow_dirty")
    doc = _describe(r, head)
    doc.update(sealed=True, sealed_at=doc["generated_utc"],
               sealed_by=by or os.environ.get("GITHUB_ACTOR") or "operator",
               ci_run_id=os.environ.get("GITHUB_RUN_ID"),
               tested_sha=head if tested else None, worktree_dirty=dirty)
    if write:
        _write(doc, root)
    return doc


def load(root: Path | None = None) -> dict[str, Any] | None:
    try:
        doc = json.loads(_release_path(root).read_text("utf-8"))
    except (OSError, ValueError):
        return None
    return doc if isinstance(doc, dict) else None


_CACHE: dict[str, Any] = {"mtime": None, "id": None}


def release_id() -> str:
    """The stamped id, cached on the release file's mtime; 'unreleased' when none exists."""
    try:
        m = RELEASE.stat().st_mtime
        if _CACHE["mtime"] != m:
            _CACHE["id"] = str(json.loads(RELEASE.read_text("utf-8")).get("release_id"))
            _CACHE["mtime"] = m
        return str(_CACHE["id"])
    except (OSError, ValueError):
        return "unreleased"


# --------------------------------------------------------------------------------- identity
def accepts(running_sha: str | None, rec: dict[str, Any], *, root: Path | None = None
            ) -> tuple[bool, str, list[str]]:
    """Is `running_sha` the sealed code? (ok, why, the code paths that say otherwise).

    Needs git for anything but the trivial equality: the pure-seal and state-only cases are a
    diff between two commits, and without git that diff cannot be taken -- so the answer is no,
    with the reason, rather than a guess.
    """
    code_sha = str(rec.get("code_sha") or rec.get("live_sha") or "")
    if not code_sha or code_sha == "unknown":
        return False, "the release names no code_sha", []
    if not running_sha or running_sha == "unknown":
        return False, "the running SHA is unmeasured", []
    if running_sha == code_sha:
        return True, f"running the sealed commit {code_sha[:12]}", []
    out = _git(["diff", "--name-only", code_sha, running_sha], _root(root))
    if out is None:
        return False, (f"cannot diff sealed {code_sha[:12]} against running {running_sha[:12]} "
                       f"(git unavailable, or the sealed commit is not in this clone)"), []
    changed = sorted({ln.strip() for ln in out.splitlines() if ln.strip()})
    allow = set(rec.get("non_code") or NON_CODE)
    code = [p for p in changed if p not in allow]
    if not code:
        return True, (f"running {running_sha[:12]} differs from sealed {code_sha[:12]} only by "
                      f"seal/state paths {changed}"), []
    return False, (f"running {running_sha[:12]} carries {len(code)} path(s) the sealed release "
                   f"{code_sha[:12]} never named: {code[:6]}"), code


def verify(root: Path | None = None) -> dict[str, Any]:
    """Does the running tree match the written release? The one-live-SHA fence.

    The SHA component uses `accepts()` (a seal commit or a state-sync commit on top of the
    sealed code is the same release); every hash component is the working tree against the
    record, so a file edited on the box after the seal is a drift even when git agrees.
    """
    rec = load(root)
    if rec is None:
        return {"ok": False, "why": "no RELEASE.json"}
    now = build(write=False, root=root)
    keys = ["config_hash", "survivor_registry_hash", "allocator_hash", "money_path_hash",
            "data_schema_version"]
    keys += [k for k in ("canon_sha256", "dependency_hash") if k in rec]
    diffs: dict[str, tuple[Any, Any]] = {k: (rec.get(k), now[k]) for k in keys
                                         if rec.get(k) != now[k]}
    imm_rec = (rec.get("immutable_manifest") or {}).get("sha256_16")
    imm_now = (now.get("immutable_manifest") or {}).get("sha256_16")
    if "immutable_manifest" in rec and imm_rec != imm_now:
        diffs["immutable_manifest"] = (imm_rec, imm_now)
    ok_sha, why_sha, _code = accepts(now["live_sha"], rec, root=root)
    if not ok_sha:
        diffs["live_sha"] = (rec.get("code_sha") or rec.get("live_sha"), now["live_sha"])
    return {"ok": not diffs, "release_id": rec.get("release_id"), "diffs": diffs,
            "identity": why_sha, "sealed": bool(rec.get("sealed")),
            "why": ("tree matches the written release" if not diffs else
                    f"{len(diffs)} component(s) differ from the written release")}
