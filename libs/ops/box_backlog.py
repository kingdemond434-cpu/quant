"""Drain the box's unpushed backlog without ever pushing the box's branch.

MEASURED 2026-10-06 (read-only census, vmi3571445 15:43Z): the box's branch is 823 commits ahead
of origin. Pushing that branch is exactly what died on `RPC failed; HTTP 408` on 2026-09-24 (506
commits of parquet then), so the publisher no longer does it: the box's STATE now travels as one
commit on origin's tip (`Publish-StateOnto`). What that leaves stranded is anything else the box
committed -- a hand fix made on the box, a box-side session's code -- which no one off the box can
see, review or keep.

WHAT THIS DOES, every run:

1. Lists the backlog (`<upstream>..HEAD`, merges counted apart -- a merge of origin into the box
   carries origin's own code, not the box's).
2. Classifies each non-merge commit: STATE-ONLY when every path it touches is state
   (`libs.ops.release.is_state_path` -- the one classification the adopter and the seal use), else
   CODE-TOUCHING. State-only commits are superseded by the fresh state publish and are dropped
   from consideration; nothing is deleted on the box.
3. For the code paths those commits touched, keeps the ones whose blob at the box's HEAD differs
   from origin's tip (a path the box changed and origin has since caught up with is not news), and
   skips any blob over MAX_BLOB_BYTES (that is how 408s start).
4. With --push: lays those blobs over origin's tip in a PRIVATE index and pushes ONE commit to
   `box/backlog-<YYYYMMDD-HHMM>` -- a review branch, never the live branch, never the production or
   release refs (refused in code, not by convention). A human or a thread reviews and lands it.
5. Writes desks/mt5/reports/BOX_BACKLOG.json: counts, the code paths, the branch and the push
   result. An unreadable backlog is UNMEASURED, never zero.

HEAD, the real index and the working tree are never touched. git runs with `git_env` (the box's
ownership setting) and inherits the caller's credential header when the publisher launches it.
"""
from __future__ import annotations

import argparse
import base64
import binascii
import contextlib
import fnmatch
import gzip
import hashlib
import json
import os
import re
import subprocess
import sys
import tempfile
import zlib
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from libs.ops.box_git_env import git_env  # noqa: E402
from libs.ops.release import is_state_path as is_state  # noqa: E402

OUT_REL = "desks/mt5/reports/BOX_BACKLOG.json"
REVIEW_PREFIX = "box/backlog-"
MAX_BLOB_BYTES = 2_000_000
#: THE REPOSITORY IS PUBLIC (audit D2, 2026-10-06). Box-local files that hold credentials or keys
#: never leave the box: these names are denied outright (matched on the basename and the path,
#: case-insensitive), and a path origin's .gitignore covers is denied too.
DENY_GLOBS: tuple[str, ...] = ("*.ini", "*.env", ".env*", "*secret*", "*credential*", "*token*",
                               "*.pem", "*.key", "*.pfx", "*.p12", "data/secrets/*")
#: Content that looks like a credential, in two strengths, and only path names are ever recorded.
#:
#: STRONG -- a real credential FORMAT (a GitHub/OpenAI/AWS token shape, a private key block). One
#: hit refuses the WHOLE push: a tree that holds a credential is not drained in part. These are
#: anchored shapes, so ordinary prose does not trip them (`\bsk-` needs a word boundary, so
#: "task-" and "desk-" never match; the token bodies need 16-36+ characters of the right alphabet).
#:
#: WEAK -- a credential-ish assignment (`password=`, `token:`) or a bare PEM header. Code reads
#: tokens from the environment all the time (`token = os.environ[...]`), so a weak hit WITHHOLDS
#: THAT FILE (listed in `withheld_paths` for a human) and the rest still drains: a false positive
#: costs one named file, never the whole drain forever (audit D2, third condition).
#:
#: AUDIT HOLD (2026-10-06) widened both lists after a bypass list: JSON keys, prefixed env names
#: (MT5_PASSWORD=, FRED_API_KEY=), URL-encoded separators, header values, longer GitHub tokens,
#: Slack/Google/Telegram shapes, credentials inside a URL, a PEM header split across a string
#: concatenation, and encoded payloads (see `screen_bytes`).
STRONG_SECRET_PATTERNS: tuple[re.Pattern[str], ...] = tuple(re.compile(p) for p in (
    r"\bgh[pousr]_[A-Za-z0-9]{36,}", r"\bgithub_pat_[A-Za-z0-9_]{60,}",
    r"\bsk-(?:proj-|ant-)?[A-Za-z0-9_-]{20,}", r"\b(?:AKIA|ASIA)[0-9A-Z]{16}\b",
    r"\bxox[abposr]-[A-Za-z0-9-]{10,}", r"\bAIza[0-9A-Za-z_-]{35}",
    r"\b[0-9]{8,10}:AA[0-9A-Za-z_-]{33}",                      # Telegram bot token
    r"-----BEGIN[A-Z ]{0,40}PRIVATE KEY", r"PRIVATE KEY-----",   # whole or split PEM header
))
WEAK_SECRET_PATTERNS: tuple[re.Pattern[str], ...] = (*(re.compile(p, re.IGNORECASE) for p in (
    # No leading \b: MT5_PASSWORD, $mt5Password and aws_secret_access_key must all match.
    r"(?:pass(?:word|wd)?|pwd|token|secret|api[_-]?key|access[_-]?key|auth(?:orization)?|bearer)"
    r"[\w-]*[\"']?\s*(?:[=:]|%3[ad])",
    # An Authorization header value; the digit lookahead keeps "basic functionality" prose out.
    r"\b(?:bearer|basic)\s+(?=[A-Za-z0-9._~+/=-]*[0-9])[A-Za-z0-9._~+/=-]{12,}",
    r"x-api-key",
    r"\b[a-z][a-z0-9+.-]*://[^\s/:@'\"]+:[^\s/@'\"]+@",          # scheme://user:password@host
    r"-----BEGIN",
)),
    # Upper-case env names ending in KEY (EIA_KEY=, MY_KEY:), case-SENSITIVE so Python's `key=`
    # keyword and JSON "key": do not withhold half the tree.
    re.compile(r"\b[A-Z][A-Z0-9_]*_KEY\b[\"']?\s*(?:[=:]|%3[ADad])"),
)
#: An encoded run worth decoding and re-screening (base64 and its url-safe form).
_B64_RUN = re.compile(r"[A-Za-z0-9+/_-]{20,}={0,2}")
#: Bytes that make a blob unscreenable as text: a NUL (utf-16, any binary), gzip, zip.
_BINARY_MAGIC = (b"\x1f\x8b", b"PK\x03\x04")
_MAX_INFLATE = 8_000_000


class Unmeasured(RuntimeError):
    """A git read the screen depends on failed: the drain is UNMEASURED and pushes nothing."""


#: Refs this module may never write, whatever it is asked.
FORBIDDEN_REFS = ("claude/llm-auto-upgrade-verify-gcjac3", "production", "master", "main",
                  "desk-sync-clean")


def _git(root: Path, *args: str, env: dict[str, str] | None = None,
         timeout: float = 300.0, stdin: str | None = None) -> tuple[int, str, str]:
    try:
        r = subprocess.run(["git", "-C", str(root), *args], capture_output=True, text=True,
                           encoding="utf-8", errors="replace", timeout=timeout, check=False,
                           env=env or git_env(root), input=stdin)
    except (OSError, subprocess.SubprocessError) as exc:
        return 127, "", f"{type(exc).__name__}: {exc}"
    return r.returncode, r.stdout, r.stderr


def _git_bytes(root: Path, *args: str, timeout: float = 300.0) -> tuple[int, bytes]:
    try:
        r = subprocess.run(["git", "-C", str(root), *args], capture_output=True, timeout=timeout,
                           check=False, env=git_env(root))
    except (OSError, subprocess.SubprocessError):
        return 127, b""
    return r.returncode, r.stdout


def review_branch(now: datetime) -> str:
    return f"{REVIEW_PREFIX}{now.strftime('%Y%m%d-%H%M')}"


def _assert_review_ref(branch: str) -> None:
    name = branch.removeprefix("refs/heads/")
    if not name.startswith(REVIEW_PREFIX) or name in FORBIDDEN_REFS or name.startswith("release/"):
        raise ValueError(f"refusing to write {branch!r}: the backlog goes to {REVIEW_PREFIX}* only")


def classify(root: Path, upstream: str) -> dict[str, Any]:
    doc: dict[str, Any] = {"upstream": upstream}
    rc, out, err = _git(root, "rev-list", "--count", f"{upstream}..HEAD")
    if rc != 0:
        doc.update(verdict="UNMEASURED", why=f"cannot list the backlog: {err.strip()[:300]}")
        return doc
    doc["ahead"] = int(out.strip() or 0)
    rc, out, _ = _git(root, "rev-list", "--count", "--merges", f"{upstream}..HEAD")
    doc["merges"] = int(out.strip() or 0) if rc == 0 else None
    # One pass: "@@<sha>" header per non-merge commit, then the paths it touched.
    rc, out, err = _git(root, "log", "--no-merges", "--format=@@%H", "--name-only",
                        f"{upstream}..HEAD")
    if rc != 0:
        doc.update(verdict="UNMEASURED", why=f"cannot read the backlog: {err.strip()[:300]}")
        return doc
    commits: dict[str, list[str]] = {}
    cur = None
    for line in out.splitlines():
        if line.startswith("@@"):
            cur = line[2:].strip()
            commits[cur] = []
        elif line.strip() and cur:
            commits[cur].append(line.strip())
    code_commits = [c for c, paths in commits.items() if any(not is_state(p) for p in paths)]
    code_paths = sorted({p for c in code_commits for p in commits[c] if not is_state(p)})
    doc.update(non_merge=len(commits), state_only=len(commits) - len(code_commits),
               code_touching=len(code_commits), code_commits=code_commits[:200],
               code_paths_touched=len(code_paths), verdict="MEASURED")
    doc["_code_paths"] = code_paths
    return doc


Blob = tuple[str, str, str]


def differing_blobs(root: Path, upstream: str,
                    paths: list[str]) -> tuple[list[Blob], list[dict[str, Any]]]:
    """(mode, sha, path) for paths whose HEAD blob differs from upstream's, and the skipped."""
    keep: list[tuple[str, str, str]] = []
    skipped: list[dict[str, Any]] = []
    for i in range(0, len(paths), 200):
        chunk = paths[i:i + 200]
        rc_h, head_out, err_h = _git(root, "ls-tree", "-l", "HEAD", "--", *chunk)
        rc_u, up_out, err_u = _git(root, "ls-tree", upstream, "--", *chunk)
        if rc_h != 0 or rc_u != 0:
            raise Unmeasured(f"ls-tree failed: {(err_h or err_u).strip()[:300]}")
        up = {}
        for line in up_out.splitlines():
            meta, _, rel = line.partition("\t")
            f = meta.split()
            if len(f) >= 3:
                up[rel] = f[2]
        for line in head_out.splitlines():
            meta, _, rel = line.partition("\t")
            f = meta.split()
            if len(f) < 4 or f[1] != "blob":
                continue
            mode, sha, size = f[0], f[2], f[3]
            if up.get(rel) == sha:
                continue
            if size.isdigit() and int(size) > MAX_BLOB_BYTES:
                skipped.append({"path": rel, "bytes": int(size), "why": "over MAX_BLOB_BYTES"})
                continue
            keep.append((mode, sha, rel))
    keep, adopted = _drop_origin_history(root, upstream, keep)
    for rel in adopted:
        skipped.append({"path": rel,
                        "why": "blob is in origin's history (an adoption, not box code)"})
    return keep, skipped


def _drop_origin_history(root: Path, upstream: str,
                         blobs: list[Blob]) -> tuple[list[Blob], list[str]]:
    """AUDIT D1 (2026-10-06): Adopt-Release records each adoption as a NON-merge commit of origin's
    code, so the box's HEAD blob for a path can be an OLDER origin version (box adopted v1, origin
    moved on to v2). That is not box code, and draining it would revert origin. A (path, blob)
    whose blob appears anywhere in origin's history of that path is dropped.

    AUDIT HOLD (2026-10-06): `--full-history -m`. Without them git's history simplification hides
    a side branch whose merge kept the other parent's version of the path, so an adopted blob that
    only ever lived on that side branch read as box code. A failed log is UNMEASURED (raise), never
    "nothing in origin's history" -- that reading fails open and drains origin's own code."""
    if not blobs:
        return blobs, []
    seen: set[tuple[str, str]] = set()
    paths = [b[2] for b in blobs]
    for i in range(0, len(paths), 200):
        chunk = paths[i:i + 200]
        rc, out, err = _git(root, "log", "--full-history", "-m", "--format=", "--raw",
                            "--no-abbrev", "--no-renames", upstream, "--", *chunk)
        if rc != 0:
            raise Unmeasured(f"origin history unreadable: {err.strip()[:300]}")
        for line in out.splitlines():
            if not line.startswith(":"):
                continue
            meta, _, rel = line.partition("\t")
            f = meta.split()
            if len(f) >= 4:
                seen.add((rel, f[2]))
                seen.add((rel, f[3]))
    keep = [b for b in blobs if (b[2], b[1]) not in seen]
    return keep, [b[2] for b in blobs if (b[2], b[1]) in seen]


def _denied_name(rel: str) -> bool:
    low = rel.lower()
    base = low.rsplit("/", 1)[-1]
    return any(fnmatch.fnmatch(base, g) or fnmatch.fnmatch(low, g) for g in DENY_GLOBS)


def _plain_strength(text: str) -> str | None:
    if any(p.search(text) for p in STRONG_SECRET_PATTERNS):
        return "strong"
    if any(p.search(text) for p in WEAK_SECRET_PATTERNS):
        return "weak"
    return None


def _worse(a: str | None, b: str | None) -> str | None:
    order = {None: 0, "weak": 1, "strong": 2}
    return a if order[a] >= order[b] else b


def _b64_decoded(text: str) -> list[str]:
    """Printable decodings of every base64-looking run (standard and url-safe alphabets)."""
    found: list[str] = []
    for m in _B64_RUN.finditer(text):
        run = m.group(0)
        for dec in (base64.b64decode, base64.urlsafe_b64decode):
            try:
                raw = dec(run + "=" * (-len(run) % 4))
            except (binascii.Error, ValueError):
                continue
            try:
                s = raw.decode("utf-8")
            except UnicodeDecodeError:
                continue
            if s and sum(c.isprintable() or c in "\r\n\t" for c in s) >= 0.9 * len(s):
                found.append(s)
                break
    return found


def secret_strength(text: str, _depth: int = 0) -> str | None:
    """'strong', 'weak' or None for a blob's text (or a commit message), base64 runs included."""
    level = _plain_strength(text)
    if level == "strong" or _depth >= 2:
        return level
    for decoded in _b64_decoded(text):
        level = _worse(level, secret_strength(decoded, _depth + 1))
        if level == "strong":
            break
    return level


def _inflate(data: bytes) -> bytes | None:
    try:
        d = zlib.decompressobj(16 + zlib.MAX_WBITS)
        return d.decompress(data, _MAX_INFLATE)
    except (zlib.error, gzip.BadGzipFile, EOFError):
        return None


def screen_bytes(data: bytes) -> str | None:
    """A blob's raw bytes. Anything that is not plain text (a NUL anywhere -- which is also every
    utf-16 file -- or gzip/zip magic) cannot be screened as text, so it is WITHHELD at least; the
    decodings we can read cheaply (utf-16, gzip) are also scanned so a credential inside them
    escalates to strong and refuses the push."""
    binary = b"\x00" in data or data.startswith(_BINARY_MAGIC)
    texts = [data.decode("utf-8", errors="replace")]
    if binary:
        for enc in ("utf-16", "utf-16-le", "utf-16-be"):
            with contextlib.suppress(UnicodeDecodeError):
                texts.append(data.decode(enc))
        inflated = _inflate(data) if data.startswith(b"\x1f\x8b") else None
        if inflated is not None:
            texts.append(inflated.decode("utf-8", errors="replace"))
    level: str | None = "weak" if binary else None
    for t in texts:
        level = _worse(level, secret_strength(t))
        if level == "strong":
            break
    return level


def screen_secrets(root: Path, upstream: str,
                   blobs: list[Blob]) -> tuple[list[Blob], list[str], list[str], list[str]]:
    """AUDIT D2: (kept, denied-by-name-or-ignore, strong hits, weak-withheld). Path names only.

    WHAT IS SCANNED IS EVERYTHING THAT IS PUSHED. The review branch is ONE commit whose parent is
    origin's own tip (already public) and whose tree is origin's tree plus exactly these blobs; no
    box commit, box history or box commit message is ever in the pushed range. So scanning each
    kept blob (and the one commit message, in push_review) covers every byte the push adds."""
    denied = [b[2] for b in blobs if _denied_name(b[2])]
    rest = [b for b in blobs if b[2] not in denied]
    if rest:
        # Ignored by the rules origin carries: check-ignore --no-index reads .gitignore from the
        # tree, so a box-local file under an ignored path is refused even if the box tracked it.
        # --stdin, not argv: Windows caps a command line near 32K characters (audit should-fix).
        # rc 1 means "none ignored"; anything else but 0 is a failed read, hence UNMEASURED.
        rc, out, err = _git(root, "check-ignore", "--no-index", "--stdin",
                            stdin="".join(b[2] + "\n" for b in rest))
        if rc not in (0, 1):
            raise Unmeasured(f"check-ignore failed: {err.strip()[:300]}")
        ignored = {ln.strip() for ln in out.splitlines() if ln.strip()}
        denied += [b[2] for b in rest if b[2] in ignored]
        rest = [b for b in rest if b[2] not in ignored]
    strong: list[str] = []
    weak: list[str] = []
    for _mode, sha, rel in rest:
        rc, data = _git_bytes(root, "cat-file", "blob", sha)
        level = "strong" if rc != 0 else screen_bytes(data)   # unreadable is not clean
        if level == "strong":
            strong.append(rel)
        elif level == "weak":
            weak.append(rel)
    kept = [b for b in rest if b[2] not in weak]
    return kept, denied, strong, weak


def push_review(root: Path, upstream: str, blobs: list[tuple[str, str, str]], branch: str,
                remote: str = "origin") -> dict[str, Any]:
    _assert_review_ref(branch)
    rc, base, err = _git(root, "rev-parse", f"{upstream}^{{commit}}")
    if rc != 0:
        return {"pushed": False, "why": f"upstream unreadable: {err.strip()[:300]}"}
    base = base.strip()
    fd, idx = tempfile.mkstemp(prefix="box-backlog-index-")
    os.close(fd)
    os.unlink(idx)
    env = {**git_env(root), "GIT_INDEX_FILE": idx}
    try:
        rc, _, err = _git(root, "read-tree", base, env=env)
        if rc != 0:
            return {"pushed": False, "why": f"read-tree failed: {err.strip()[:300]}"}
        for mode, sha, rel in blobs:
            rc, _, err = _git(root, "update-index", "--add", "--cacheinfo", f"{mode},{sha},{rel}",
                              env=env)
            if rc != 0:
                return {"pushed": False, "why": f"update-index failed: {err.strip()[:300]}"}
        rc, tree, err = _git(root, "write-tree", env=env)
    finally:
        if os.path.exists(idx):
            os.unlink(idx)
    if rc != 0:
        return {"pushed": False, "why": f"write-tree failed: {err.strip()[:300]}"}
    msg = (f"box backlog for review: {len(blobs)} code path(s) the box changed and origin lacks\n\n"
           f"Built by libs/ops/box_backlog.py on origin's tip {base[:12]}. Review branch only; "
           "it never lands on the live branch by itself.")
    if secret_strength(msg):
        return {"pushed": False, "why": "REFUSED: the commit message failed the secret screen"}
    rc, commit, err = _git(root, "commit-tree", tree.strip(), "-p", base, "-m", msg)
    if rc != 0:
        return {"pushed": False, "why": f"commit-tree failed: {err.strip()[:300]}"}
    commit = commit.strip()
    # A NEW ref every run (minute-stamped), so the push never needs force over anything.
    rc, _, err = _git(root, "push", "--porcelain", remote, f"{commit}:refs/heads/{branch}")
    if rc != 0:
        return {"pushed": False, "commit": commit, "why": err.strip()[-600:]}
    return {"pushed": True, "commit": commit, "branch": branch}


def _digest(blobs: list[tuple[str, str, str]]) -> str:
    return hashlib.sha256("\n".join(f"{m} {s} {p}" for m, s, p in sorted(blobs, key=lambda b: b[2]))
                          .encode("utf-8")).hexdigest()[:16]


def _previous(out: Path) -> dict[str, Any]:
    try:
        data = json.loads(out.read_text("utf-8"))
    except (OSError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def run(root: Path, *, upstream: str, push: bool, now: datetime | None = None,
        remote: str = "origin", out: Path | None = None) -> dict[str, Any]:
    now = now or datetime.now(UTC)
    doc = classify(root, upstream)
    doc["measured_at"] = now.isoformat(timespec="seconds")
    code_paths = doc.pop("_code_paths", [])
    if doc.get("verdict") != "MEASURED":
        return doc
    try:
        blobs, skipped = differing_blobs(root, upstream, code_paths)
        blobs, denied, hits, withheld = screen_secrets(root, upstream, blobs)
    except Unmeasured as exc:
        # A read the drain depends on failed: no partial answer, and nothing is pushed.
        doc.update(verdict="UNMEASURED", why=str(exc),
                   push={"pushed": False, "why": "UNMEASURED: nothing pushed"})
        return doc
    doc.update(code_paths_differing=len(blobs), code_paths=[b[2] for b in blobs][:500],
               skipped=skipped, denied_paths=denied, secret_screen_hits=hits,
               withheld_paths=withheld, blob_digest=_digest(blobs))
    prev = _previous(out) if out else {}
    raw_push = prev.get("push")
    prev_push: dict[str, Any] = raw_push if isinstance(raw_push, dict) else {}
    if hits:
        # One suspicious blob refuses the whole push: a partial drain of a tree that holds a
        # credential is still a tree that holds one. Path names only are recorded.
        doc["push"] = {"pushed": False, "why": f"REFUSED: secret screen matched {len(hits)} "
                                              "path(s); nothing pushed (see secret_screen_hits)"}
    elif not blobs:
        doc["push"] = {"pushed": False, "why": "nothing to drain: no box-only code differs"}
    elif prev.get("blob_digest") == doc["blob_digest"] and prev_push.get("pushed"):
        # The same box-only code is already on a review branch; a new branch every slot is noise.
        doc["push"] = {**prev_push, "repeated": True}
    elif push:
        doc["push"] = push_review(root, upstream, blobs, review_branch(now), remote=remote)
    else:
        doc["push"] = {"pushed": False, "why": "dry run (no --push)"}
    return doc


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--upstream", default="@{u}")
    ap.add_argument("--push", action="store_true")
    ap.add_argument("--out", type=Path, default=ROOT / OUT_REL)
    args = ap.parse_args(argv)
    doc = run(ROOT, upstream=args.upstream, push=args.push, out=args.out)
    try:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json.dumps(doc, indent=2), "utf-8")
    except OSError as exc:
        print(f"box backlog: report not written ({exc})", file=sys.stderr)
    push = doc.get("push") or {}
    print(f"box backlog: {doc.get('verdict')} ahead={doc.get('ahead')} merges={doc.get('merges')} "
          f"state_only={doc.get('state_only')} code_touching={doc.get('code_touching')} "
          f"code_paths_differing={doc.get('code_paths_differing')} "
          f"pushed={push.get('pushed')} {push.get('branch') or push.get('why', '')}")
    return 0 if doc.get("verdict") == "MEASURED" else 1


if __name__ == "__main__":
    raise SystemExit(main())
