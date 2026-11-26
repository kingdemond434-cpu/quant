"""THE OFF-SITE COPY, with no credential anyone has to hand the box: a restic repository of the
critical tier, pushed as ciphertext to a branch of the private GitLab drop project with a write
deploy key the box generated for itself.

WHY THIS ROUTE (2026-11-25, rule E40). The box had never been backed up, and every off-site
target that needs a credential needs someone to put that credential on the box: the principal
declined to sign up for anything, and secrets work on the box is refused to remote sessions. A
key the box makes itself needs no transfer at all. The box generates an ed25519 key under
data/secrets (never printed, never shipped), publishes only the PUBLIC half to
desks/mt5/reports/BACKUP_DEPLOY_KEY.pub, and the project registers it once as a deploy key with
push on the drop project. From then on nothing depends on a person or a session.

WHY IT IS SAFE ON THE DROP PROJECT.
  * The drop's code branch (`main`) is protected for Maintainers only; a deploy key cannot push
    to it, so the box cannot write what it later pulls. The backup lives on BRANCH (below), which
    the forge never fetches (drop_pull fetches `refs/heads/<drop branch>` at depth 1).
  * Only restic ciphertext is pushed (AES-256, client-side). The repository password is generated
    on the box and stays in data/secrets/offsite_git.json.
  * GitLab free limits: a project holds 10 GiB and a push is at most 5 GiB. The off-site tier is
    capped at OFFSITE_CAP_BYTES (priority order below) and pushed in batches of PUSH_BATCH_BYTES.
    History is squashed (orphan commit, force push) when the branch's packs no longer match the
    tree, so pruned packs do not accumulate.

WHAT THE OFF-SITE TIER HOLDS. The critical tier's small files (each <= OFFSITE_MAX_FILE): ledgers,
certs, registries' small stores, state, config, evidence and the terminal's MQL5/config, in
SOURCE_PRIORITY order until the cap. Larger files stay in the box-local repository only and are
named in the report (`offsite_skipped_largest`), so the gap is visible, not silent.
"""
from __future__ import annotations

import contextlib
import json
import os
import secrets
import subprocess
from collections.abc import Callable, Iterable
from pathlib import Path
from typing import Any

DROP_URL = "git@gitlab.com:quant-group9361047/quant.git"
BRANCH = "box-backup"
OFFSITE_MAX_FILE = 64 * 1024 * 1024
OFFSITE_CAP_BYTES = 3 * 1024**3
#: The MEASURED restic repository (work dir minus .git) may not exceed this: a squash force-pushes
#: the whole repository in one push (GitLab: 5 GiB per push), and old + new objects plus the drop's
#: code must stay well under the project's 10 GiB before housekeeping (Audit M1, 48bf708e7).
REPO_CAP_BYTES = int(3.5 * 1024**3)
PUSH_BATCH_BYTES = 1024**3
PACK_SIZE_MB = "32"

Run = Callable[[list[str], dict[str, str] | None, str | None], subprocess.CompletedProcess[str]]


def _run(cmd: list[str], env: dict[str, str] | None = None,
         cwd: str | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(cmd, capture_output=True, text=True, timeout=3 * 3600, check=False,
                          env=env, cwd=cwd)


def select(files: Iterable[str], priority: Iterable[str], cap: int = OFFSITE_CAP_BYTES,
           max_file: int = OFFSITE_MAX_FILE,
           size: Callable[[str], int] = os.path.getsize) -> tuple[list[str], list[tuple[str, int]]]:
    """(files to ship off-site, skipped (path, bytes) largest first). Pure but for `size`."""
    pri = [os.path.normcase(os.path.normpath(p)) for p in priority]

    def rank(f: str) -> int:
        n = os.path.normcase(os.path.normpath(f))
        return next((i for i, p in enumerate(pri) if n.startswith(p)), len(pri))

    sized = []
    for f in files:
        with contextlib.suppress(OSError):
            sized.append((f, size(f)))
    keep, skipped, total = [], [], 0
    for f, b in sorted(sized, key=lambda x: (rank(x[0]), x[1], x[0])):
        if b > max_file or total + b > cap:
            skipped.append((f, b))
            continue
        keep.append(f)
        total += b
    skipped.sort(key=lambda x: -x[1])
    return sorted(keep), skipped


def ensure_key(key: Path, pub_out: Path, run: Run = _run) -> tuple[bool, str]:
    """Generate the box's own deploy key once; publish only its public half."""
    if not key.exists():
        key.parent.mkdir(parents=True, exist_ok=True)
        r = run(["ssh-keygen", "-q", "-t", "ed25519", "-N", "", "-C", "quant-box-backup",
                 "-f", str(key)], None, None)
        if r.returncode != 0 or not key.exists():
            return False, f"ssh-keygen failed (exit {r.returncode})"
    ok_acl, acl_why = tighten_acl(key, run)
    if not ok_acl:
        return False, f"could not restrict the private key: {acl_why}"
    pub = Path(str(key) + ".pub")
    if not pub.exists():
        return False, "public key missing next to the private key"
    pub_out.parent.mkdir(parents=True, exist_ok=True)
    text = pub.read_text(encoding="utf-8").strip()
    if "PRIVATE" in text:
        return False, "refused: the public key file holds a private key"
    pub_out.write_text(text + "\n", encoding="utf-8")
    return True, "ok"


def load_or_init(config: Path) -> dict[str, Any]:
    """{password} for the off-site repository; created once, never replaced, never printed."""
    with contextlib.suppress(OSError, ValueError):
        d = json.loads(config.read_text(encoding="utf-8"))
        if isinstance(d, dict) and d.get("password"):
            return d
    if config.exists():
        return {}
    config.parent.mkdir(parents=True, exist_ok=True)
    d = {"password": secrets.token_urlsafe(32), "key_escrowed_off_box": False}
    config.write_text(json.dumps(d, indent=1), encoding="utf-8")
    return d


def _git(work: Path, key: Path, known: Path, *args: str) -> list[str]:
    ssh = (f'ssh -i "{key}" -o IdentitiesOnly=yes -o StrictHostKeyChecking=accept-new '
           f'-o UserKnownHostsFile="{known}"')
    return ["git", "-c", f"core.sshCommand={ssh}", "-c", "safe.directory=*",
            "-c", "user.name=quant-box", "-c", "user.email=box@quant.invalid",
            "-C", str(work), *args]


def repo_bytes(work: Path) -> int:
    """Bytes of the restic repository in `work`, excluding git's own copy."""
    total = 0
    for dirpath, dirs, files in os.walk(work):
        dirs[:] = [d for d in dirs if d != ".git"]
        for f in files:
            with contextlib.suppress(OSError):
                total += os.path.getsize(os.path.join(dirpath, f))
    return total


def tighten_acl(key: Path, run: Run = _run) -> tuple[bool, str]:
    """Windows OpenSSH refuses a private key other accounts can read: SYSTEM and Administrators
    only, inheritance off (Audit S3). A no-op elsewhere (ssh-keygen already wrote it 0600)."""
    if os.name != "nt":
        return True, "posix: 0600 from ssh-keygen"
    r = run(["icacls", str(key), "/inheritance:r", "/grant:r", "SYSTEM:F",
             "/grant:r", "Administrators:F"], None, None)
    return r.returncode == 0, f"icacls exit {r.returncode}"


def push_repo(work: Path, key: Path, known: Path, url: str = DROP_URL, branch: str = BRANCH,
              run: Run = _run, batch: int = PUSH_BATCH_BYTES,
              cap: int = REPO_CAP_BYTES) -> dict[str, Any]:
    """Commit the restic repository in `work` and push it to `branch`, in batches.

    Restic writes packs once and never edits them; prune deletes some. When nothing was deleted
    since the last push, new files are added in batches (one commit + push per batch, each under
    GitLab's push limit). When files were deleted, the branch is SQUASHED to one orphan commit of
    the current tree and force-pushed, so dead packs never count against the project size."""
    def g(*a: str) -> subprocess.CompletedProcess[str]:
        return run(_git(work, key, known, *a), None, None)

    size = repo_bytes(work)
    if size > cap:
        return {"ok": False, "over_cap": True, "repo_bytes": size,
                "why": f"restic repository is {size / 1024**3:.2f} GiB > cap "
                       f"{cap / 1024**3:.2f} GiB; nothing pushed (would risk the drop project)"}
    if not (work / ".git").is_dir():
        r = g("init", "-q", "-b", branch)
        if r.returncode != 0:
            return {"ok": False, "why": f"git init failed: {r.stderr[-200:]}"}
        g("remote", "add", "origin", url)
    st = g("status", "--porcelain", "--untracked-files=all", "--", ".", ":!locks")
    if st.returncode != 0:
        return {"ok": False, "why": f"git status failed: {st.stderr[-200:]}"}
    lines = [ln for ln in st.stdout.splitlines() if ln.strip()]
    deleted = [ln for ln in lines if ln[:2].strip().startswith("D")]
    added = [ln[3:].strip().strip('"') for ln in lines if not ln[:2].strip().startswith("D")]
    if not lines:
        return {"ok": True, "pushed": 0, "mode": "unchanged"}
    if deleted:
        steps = [("checkout", "-q", "--orphan", f"{branch}-squash"), ("add", "-A", "--", ".",
                 ":!locks"), ("commit", "-q", "-m", "box backup (squashed after prune)"),
                 ("branch", "-M", branch), ("push", "-q", "--force", "origin",
                                            f"HEAD:refs/heads/{branch}")]
        for s in steps:
            r = g(*s)
            if r.returncode != 0:
                return {"ok": False, "why": f"git {s[0]} failed: {r.stderr[-300:]}",
                        "mode": "squash"}
        return {"ok": True, "pushed": len(added), "mode": "squash"}
    batches: list[list[str]] = [[]]
    acc = 0
    for f in sorted(added, key=lambda x: (not x.startswith("data/"), x)):
        b = 0
        with contextlib.suppress(OSError):
            b = (work / f).stat().st_size
        if batches[-1] and acc + b > batch:
            batches.append([])
            acc = 0
        batches[-1].append(f)
        acc += b
    for i, files in enumerate(batches):
        for s in (("add", "--", *files), ("commit", "-q", "-m", f"box backup batch {i + 1}"),
                  ("push", "-q", "origin", f"HEAD:refs/heads/{branch}")):
            r = g(*s)
            if r.returncode != 0:
                why = r.stderr[-300:]
                denied = "denied" in why.lower() or "not allowed" in why.lower()
                return {"ok": False, "why": f"git {s[0]} failed: {why}", "mode": "append",
                        "key_unregistered": denied and s[0] == "push"}
    return {"ok": True, "pushed": len(added), "mode": "append", "batches": len(batches)}
