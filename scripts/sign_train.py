"""THE SIGN TRAIN -- re-sign an audited head and re-pin QB-002 with it, in one commit.

WHY. A sealed-file change needs two edits that must land together: the file-only re-sign of
IMMUTABLE_MANIFEST.json and the QB-002 seal rotation in research/quantbench.py ("to" = the new
full sha256, "from" untouched). Done by hand they came apart (#329 cleared without the re-pin,
test_quantbench read REGRESSED after the merge).

WHO SIGNS (D-20261027-003). zuck, the owner, ordered the principal sign removed on 2026-10-27:
"no remove judge sign it should auto sign" / "remove sign" / "i am trlling u to do it". So the
default signer is the AUDIT, not a person: a moved sealed file is signed only when a CLEAR row for
its exact sha256 is already COMMITTED in data/SEAL_CLEARS.jsonl at the target. No CLEAR row, no
sign. Everything else holds: the manifest still pins every judge file's bytes, QB-002 still reads
REGRESSED on any unsigned byte, 1aa4b33f is never signed, and the train refuses any HEAD that is
not the named target.

    python scripts/sign_train.py --target <audited commit>                 # auditor-clear sign
    python scripts/sign_train.py --target <commit> --principal --expect <path>=<sha256> ...
    (add --push to push the signed commit as a branch)

THE CLEAR RECORD only ever grows. Every committed version must be a byte prefix of the version at
the target, across every branch: append CLEAR rows by rebasing, never by merging two branches that
both appended (that is refused). A malformed line, once committed, refuses every later auditor
sign; recover with `--principal`, or by rotating to a new record file in a principal-signed change.
The check needs full history: run `git fetch --unshallow` once in a shallow clone.

`--principal` keeps the human path: it refuses without a terminal and the principal types back
the first 12 hex of each new hash. It signs with the existing `check_immutable_evaluator.py
--sign-files --by <signer>`, so the manifest format has one writer.

On any failed check both files are restored to HEAD and the exit code is non-zero.

A PR HEAD, NOT LIVE (2026-11-11, Desk health's read reports/box_reads/sign_train_pr_head_read).
CI's law gate refuses any unsigned sealed byte, so a sealed change never reaches LIVE unsigned
and a train that signs only LIVE's head never has anything to sign. `--root <checkout>` signs a
PR head instead, with every guard of that read:

    python scripts/sign_train.py --list-heads                       # heads LIVE's rows name
    python scripts/sign_train.py --root <pr checkout> --target <40-hex PR head>

  G1  This file and check_immutable_evaluator.py run from LIVE's checkout (this file's own
      tree). The PR checkout is DATA: read and hashed, never imported, never executed. A PR
      that changes the train's own files (the manifest, quantbench.py, this file, the
      evaluator) is refused: those are a change for audit, not a re-sign.
  G2  No pytest at the PR head. QB-002 is checked statically by LIVE's code: quantbench.py is
      parsed (ast, never imported), every *_SEAL_ROTATION "from" is kept, a moved file's "to"
      is its new full sha256 with this signer, and the manifest pins exactly those bytes.
  G3  The head is chosen by LIVE: a CLEAR row in SEAL_CLEARS.jsonl AS COMMITTED ON LIVE (proven
      append-only there) whose `head` field is the exact 40-hex PR head. The PR's own copy of
      the record is never read.
  G4  The moved files at the head are EXACTLY the paths of that head's rows, byte for byte.
      DENIED, NO_ROTATION, no --expect and no --principal all still hold.
  G6  The train's own files at the head are byte-identical to LIVE's current ones, so the sign
      starts from LIVE's manifest and can never drop a newer manifest row. (Not "the head
      contains LIVE": the CLEAR row naming the head lands on LIVE AFTER the head, so no cleared
      head could ever contain it -- the same deadlock again. The gate merges LIVE into the sign
      PR as for any other, and a clean merge-in keeps its CLEAR by patch-id.)
  G7  One single-parent commit on the head, touching exactly the manifest and quantbench.py,
      made with hooks off (core.hooksPath -> an empty folder, so no PR file runs as a hook).
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = "desks/mt5/data/IMMUTABLE_MANIFEST.json"
QUANTBENCH = "desks/mt5/research/quantbench.py"
# Append-only CLEAR record: {"path", "sha256", "verdict": "CLEAR", "report", "cleared_utc"}.
SEAL_CLEARS = "desks/mt5/data/SEAL_CLEARS.jsonl"
AUDITOR = "auditor-clear"

# QB-002 rotation constant for each sealed file that has one (research/quantbench.py SEALED).
ROTATIONS = {
    "desks/mt5/research/promoter.py": "PROMOTER_SEAL_ROTATION",
    "libs/portfolio/allocator_proof.py": "ALLOCATOR_PROOF_SEAL_ROTATION",
    "desks/mt5/scripts/external_gauntlet.py": "GAUNTLET_SEAL_ROTATION",
}
# Sealed in QB-002 but with no rotation constant yet: a change here needs a new constant and a
# probe entry, which is a code change for audit, not a re-pin.
NO_ROTATION = ("libs/regime/state_admission.py",)
# Bytes the principal has ruled are never signed, whatever the audit says.
DENIED = ("1aa4b33f",)


def full_sha(rel: str, root: Path = ROOT) -> str:
    # Same normalisation as check_immutable_evaluator._hashes and quantbench._sha.
    return hashlib.sha256((root / rel).read_bytes().replace(b"\r\n", b"\n")).hexdigest()


def moved_files(manifest: dict[str, Any], root: Path = ROOT) -> dict[str, str]:
    """Signed files whose bytes no longer match the manifest: {path: new full sha256}."""
    out = {}
    for rel, digest in (manifest.get("files") or {}).items():
        p = root / rel
        now = full_sha(rel, root) if p.exists() else "<absent>"
        if now[:16] != digest:
            out[rel] = now
    return out


def parse_expect(items: list[str]) -> dict[str, str]:
    """--expect path=sha256 pairs; each sha must be a full 64-hex digest."""
    out = {}
    for item in items:
        rel, _, sha = item.partition("=")
        if not re.fullmatch(r"[0-9a-f]{64}", sha.lower()):
            raise ValueError(f"--expect {item!r}: want path=<64-hex sha256>")
        out[rel] = sha.lower()
    return out


def binding_problems(moved: dict[str, str], expect: dict[str, str]) -> list[str]:
    """Why these bytes are not the audited bytes the principal named; empty when they are."""
    problems = []
    for rel in sorted(set(moved) | set(expect)):
        if rel not in expect:
            problems.append(f"{rel} moved to {moved[rel]} but no --expect or CLEAR row names it")
        elif rel not in moved:
            problems.append(f"{rel} is named in --expect but did not move")
        elif moved[rel] != expect[rel]:
            problems.append(f"{rel} is {moved[rel]}, not the audited {expect[rel]}")
    for rel, sha in moved.items():
        if any(sha.startswith(bad) for bad in DENIED):
            problems.append(f"{rel} is {sha[:16]}, which is never signed")
    return problems


def repin(src: str, name: str, new_to: str, signer: str = "principal") -> str:
    """Rewrite one *_SEAL_ROTATION block: new "to", signed_by = signer, "from" kept."""
    block = re.compile(rf"^{name} = \{{\n(.*?)^\}}\n", re.DOTALL | re.MULTILINE)
    m = block.search(src)
    if not m:
        raise ValueError(f"{name} not found in quantbench.py")
    body = m.group(1)
    path = re.search(r'"path": "([^"]+)"', body)
    frm = re.search(r'"from": "([0-9a-f]{64})"', body)
    if not (path and frm):
        raise ValueError(f"{name} has no path/from to keep")
    new = (
        f'{name} = {{\n    "path": "{path.group(1)}",\n    "from": "{frm.group(1)}",\n'
        f'    "to": "{new_to}",\n    "signed_by": "{signer}",\n}}\n'
    )
    return src[: m.start()] + new + src[m.end() :]


def _run(*cmd: str) -> int:
    return subprocess.run(cmd, cwd=ROOT, check=False).returncode


def _git(*args: str) -> str:
    return subprocess.run(
        ("git", *args), cwd=ROOT, capture_output=True, text=True, check=True
    ).stdout.strip()


def _git_in(cwd: Path, *args: str) -> str:
    return subprocess.run(
        ("git", *args), cwd=cwd, capture_output=True, text=True, check=True
    ).stdout.strip()


REPORT = re.compile(r"(/mnt/project-files/)?reports/audit/\S+\.md")
HEX64 = re.compile(r"[0-9a-f]{64}")


HEX40 = re.compile(r"[0-9a-f]{40}")


def _rows(text: str) -> list[dict[str, Any]]:
    """Every row of SEAL_CLEARS.jsonl text, validated, failing closed (ValueError)."""
    rows = []
    for n, line in enumerate(text.splitlines(), 1):
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except ValueError as exc:
            raise ValueError(f"{SEAL_CLEARS}:{n} is not JSON") from exc
        if not isinstance(row, dict):
            raise ValueError(f"{SEAL_CLEARS}:{n} is not an object")
        path, sha, verdict = row.get("path"), row.get("sha256"), row.get("verdict")
        report, report_sha = row.get("report"), row.get("report_sha256")
        if not isinstance(path, str) or not path:
            raise ValueError(f"{SEAL_CLEARS}:{n} has no path")
        if not isinstance(sha, str) or not HEX64.fullmatch(sha):
            raise ValueError(f"{SEAL_CLEARS}:{n} sha256 is not 64 lower-case hex")
        if verdict not in ("CLEAR", "HOLD"):
            raise ValueError(f"{SEAL_CLEARS}:{n} verdict must be CLEAR or HOLD")
        if not isinstance(report, str) or not REPORT.fullmatch(report) or ".." in report:
            raise ValueError(f"{SEAL_CLEARS}:{n} report must be a reports/audit/...md path")
        if report_sha is not None and (
            not isinstance(report_sha, str) or not HEX64.fullmatch(report_sha)
        ):
            raise ValueError(f"{SEAL_CLEARS}:{n} report_sha256 is not 64 lower-case hex")
        # `head` (2026-11-11, G3): the exact PR head the audit cleared these bytes AT. Optional,
        # but when present it must be a full 40-hex commit, or the whole record is refused.
        if "head" in row and (not isinstance(row["head"], str) or not HEX40.fullmatch(row["head"])):
            raise ValueError(f"{SEAL_CLEARS}:{n} head is not a 40-hex lower-case commit")
        rows.append(row)
    return rows


def parse_clears(text: str) -> dict[str, set[str]]:
    """{path: {sha256 the audit cleared}} from SEAL_CLEARS.jsonl text, failing closed.

    Every non-blank line must be a well-formed row, or the whole record is refused (ValueError):
    a garbled line is not a quiet "no". Any HOLD for a path's sha256 outranks every CLEAR for it,
    whichever came first.
    """
    cleared: dict[str, set[str]] = {}
    held: dict[str, set[str]] = {}
    for row in _rows(text):
        (cleared if row["verdict"] == "CLEAR" else held).setdefault(row["path"], set()).add(
            row["sha256"]
        )
    out = {p: shas - held.get(p, set()) for p, shas in cleared.items()}
    return {p: shas for p, shas in out.items() if shas}


def heads_named(text: str) -> list[str]:
    """The PR heads LIVE's record names in a CLEAR row, oldest first, each once (G3)."""
    out: list[str] = []
    for row in _rows(text):
        h = row.get("head")
        if row["verdict"] == "CLEAR" and h and h not in out:
            out.append(h)
    return out


def head_clears(text: str, head: str) -> dict[str, str]:
    """{path: sha256} the audit cleared AT `head` (G3), failing closed.

    Only rows whose `head` is exactly this head count. A HOLD outranks: a HOLD row for this
    head and path, or any HOLD for that path's exact bytes (with or without a head), drops the
    path. Two CLEAR rows for one head and path naming different bytes are refused (ValueError):
    the train never guesses which bytes the audit meant.
    """
    rows = _rows(text)
    held_bytes = {(r["path"], r["sha256"]) for r in rows if r["verdict"] == "HOLD"}
    held_here = {r["path"] for r in rows if r["verdict"] == "HOLD" and r.get("head") == head}
    out: dict[str, str] = {}
    for r in rows:
        if r["verdict"] != "CLEAR" or r.get("head") != head:
            continue
        if r["path"] in out and out[r["path"]] != r["sha256"]:
            raise ValueError(f"two CLEAR rows for {r['path']} at {head[:12]} name different bytes")
        out[r["path"]] = r["sha256"]
    return {p: sha for p, sha in out.items() if p not in held_here and (p, sha) not in held_bytes}


def append_only_problems(versions: list[bytes]) -> list[str]:
    """Every committed version of the CLEAR record must be a byte prefix of the target's version.

    Compared with the TARGET, not just the next version walked: a merge that takes one branch's
    record would otherwise drop the other branch's HOLD row without any single step rewriting.
    """
    if not versions:
        return []
    target = versions[-1]
    return [
        f"an earlier committed {SEAL_CLEARS} (version {i + 1}) is not kept at the target"
        for i, v in enumerate(versions[:-1])
        if not target.startswith(v)
    ]


def _committed_clears(head: str) -> str:
    """The CLEAR record at the target, after proving its history only ever appended."""
    if _git("rev-parse", "--is-shallow-repository") == "true":
        raise ValueError(
            "shallow clone: the CLEAR record's history cannot be proven append-only; "
            "run `git fetch --unshallow` once in this clone"
        )
    # --full-history: default simplification follows one side of a merge and never reads a
    # version (and its HOLD rows) that only the other side carried.
    shas = _git(
        "log", "--full-history", "--format=%H", "--reverse", head, "--", SEAL_CLEARS
    ).splitlines()
    versions = []
    for sha in [*shas, head]:
        r = subprocess.run(
            ("git", "show", f"{sha}:{SEAL_CLEARS}"), cwd=ROOT, capture_output=True, check=False
        )
        versions.append(r.stdout if r.returncode == 0 else b"")
    problems = append_only_problems(versions)
    if problems:
        raise ValueError("; ".join(problems))
    return versions[-1].decode("utf-8") if versions else ""


def cleared_expect(moved: dict[str, str], clears: dict[str, set[str]]) -> dict[str, str]:
    """The --expect the audit implies: every moved file whose exact bytes carry a CLEAR row."""
    return {rel: sha for rel, sha in moved.items() if sha in clears.get(rel, set())}


def _restore() -> None:
    _git("checkout", "HEAD", "--", MANIFEST, QUANTBENCH)


def _qb002_green() -> bool:
    return _run(sys.executable, "-m", "pytest", "desks/mt5/tests/test_quantbench.py", "-q") == 0


def _confirm(moved: dict[str, str]) -> bool:
    """The real human act: a person at a terminal reads each new hash and types it back."""
    if not sys.stdin.isatty():
        print("REFUSED: no terminal. The principal signs by typing, never a task or a pipe.")
        return False
    print("You are signing these bytes as principal:")
    for rel, sha in sorted(moved.items()):
        print(f"  {rel}\n    {sha}")
    for rel, sha in sorted(moved.items()):
        typed = input(f"type the first 12 hex of {rel}: ").strip().lower()
        if typed != sha[:12]:
            print("REFUSED: typed hash does not match")
            return False
    return True


def _commit_holds(head: str, moved: dict[str, str], commit: str = "HEAD") -> bool:
    """The new commit carries both files and every new QB-002 "to" (a hook may unstage one)."""
    files = set(_git("show", "--name-only", "--format=", commit).splitlines())
    if _git("rev-parse", f"{commit}~1") != head or not {MANIFEST, QUANTBENCH} <= files:
        return False
    bench = _git("show", f"{commit}:{QUANTBENCH}")
    return all(sha in bench for rel, sha in moved.items() if rel in ROTATIONS)


# ------------------------------------------------------------------ a PR head (--root)
#: The train's own files: a PR that changes one is a change for audit, never a re-sign (G1).
TRAIN_OWNED = (
    MANIFEST,
    QUANTBENCH,
    "scripts/sign_train.py",
    "scripts/check_immutable_evaluator.py",
)
SEALED_NAME = "SEALED"


def _constants(src: str) -> dict[str, Any]:
    """quantbench.py's SEALED tuple and *_SEAL_ROTATION dicts, read by ast (never imported)."""
    import ast

    out: dict[str, Any] = {}
    for node in ast.parse(src).body:
        if not (isinstance(node, ast.Assign) and len(node.targets) == 1):
            continue
        name = getattr(node.targets[0], "id", None)
        if isinstance(name, str) and (name == SEALED_NAME or name in ROTATIONS.values()):
            out[name] = ast.literal_eval(node.value)
    return out


def static_qb002(
    before_src: str, after_src: str, moved: dict[str, str], signer: str, manifest: dict[str, Any]
) -> list[str]:
    """Why QB-002 would not read green after the sign; empty when it would (G2).

    The same rule as quantbench.probe_sealed_files, read statically from LIVE's code: each
    rotation keeps its "from"; a moved file's rotation names its new full sha256 and this
    signer, and the manifest pins those bytes under that signer; nothing else changes.
    """
    try:
        b, a = _constants(before_src), _constants(after_src)
    except (SyntaxError, ValueError) as exc:
        return [f"quantbench.py constants unreadable: {exc}"]
    problems = []
    if b.get(SEALED_NAME) != a.get(SEALED_NAME):
        problems.append("the SEALED tuple changed")
    files = manifest.get("files") or {}
    for rel, name in ROTATIONS.items():
        rb, ra = b.get(name), a.get(name)
        if not (isinstance(rb, dict) and isinstance(ra, dict)):
            problems.append(f"{name} is missing")
            continue
        if ra.get("from") != rb.get("from") or ra.get("path") != rel or rb.get("path") != rel:
            problems.append(f'{name} lost its path or its "from"')
        if rel in moved:
            if ra.get("to") != moved[rel] or ra.get("signed_by") != signer:
                problems.append(f"{name} does not name {moved[rel][:16]} by {signer}")
            if manifest.get("signed_by") != signer or files.get(rel) != moved[rel][:16]:
                problems.append(f"the manifest does not pin {rel} at {moved[rel][:16]} by {signer}")
        elif ra != rb:
            problems.append(f"{name} changed though {rel} did not move")
    for rel in b.get(SEALED_NAME) or ():
        if rel in moved and rel not in ROTATIONS:
            problems.append(f"{rel} is in QB-002's SEALED but has no rotation constant")
    return problems


def _evaluator() -> Any:
    """LIVE's check_immutable_evaluator, loaded from this file's own tree (G1)."""
    import importlib.util

    spec = importlib.util.spec_from_file_location(
        "_live_evaluator", ROOT / "scripts" / "check_immutable_evaluator.py"
    )
    if not (spec and spec.loader):
        raise ValueError("LIVE's check_immutable_evaluator.py cannot be loaded")
    mod = importlib.util.module_from_spec(spec)
    sys.dont_write_bytecode = True  # LIVE's checkout stays exactly as fetched
    spec.loader.exec_module(mod)
    return mod


def _sign_files_at(root: Path, signer: str) -> int:
    """LIVE's own `--sign-files`, pointed at the PR checkout: the manifest keeps one writer."""
    mod = _evaluator()
    mod.ROOT = root
    mod.MANIFEST = root / MANIFEST
    saved = sys.argv
    sys.argv = ["check_immutable_evaluator.py", "--sign-files", "--by", signer]
    try:
        return int(mod.main())
    finally:
        sys.argv = saved


def _hashes_at(root: Path) -> dict[str, str]:
    mod = _evaluator()
    mod.ROOT = root
    return dict(mod._hashes())


def _is_ancestor(cwd: Path, a: str, b: str) -> bool:
    r = subprocess.run(("git", "merge-base", "--is-ancestor", a, b), cwd=cwd, check=False)
    return r.returncode == 0


def train_commit_problems(cwd: Path, head: str, commit: str) -> list[str]:
    """Why `commit` is not exactly a train commit on `head`; empty when it is (G7, G8).

    One single-parent commit whose parent is `head`, touching exactly the manifest and
    quantbench.py. A gate can call this to carry a CLEAR of `head` to `commit`.
    """
    problems = []
    parents = _git_in(cwd, "rev-list", "--parents", "-n", "1", commit).split()
    if parents[1:] != [head]:
        problems.append(f"{commit[:12]} is not one single-parent commit on {head[:12]}")
    touched = sorted(_git_in(cwd, "diff", "--name-only", head, commit).splitlines())
    if touched != sorted((MANIFEST, QUANTBENCH)):
        problems.append(f"{commit[:12]} touches {touched}, not exactly the two seal files")
    return problems


def sign_root(root: Path, target: str, live_head: str) -> int:
    """Sign the PR head checked out at `root` from LIVE's record and LIVE's code (G1-G7)."""
    root = root.resolve()
    if root == ROOT or ROOT in root.parents or root in ROOT.parents:
        print("REFUSED: --root must be a checkout separate from LIVE's")
        return 2
    if not HEX40.fullmatch(target):
        print("REFUSED: --root needs the full 40-hex --target")
        return 2
    head = _git_in(root, "rev-parse", "HEAD")
    if head != target:
        print(f"REFUSED: {root} is at {head[:12]}, not the named target {target[:12]}")
        return 2
    if _git_in(root, "status", "--porcelain", "--untracked-files=no"):
        print(f"REFUSED: {root} has local edits")
        return 2
    owned = _git_in(root, "diff", "--name-only", live_head, head, "--", *TRAIN_OWNED)
    if owned:
        print(f"REFUSED: the PR changes the train's own files: {owned.split()}")
        return 2
    try:
        rows = head_clears(_committed_clears(live_head), head)
    except ValueError as exc:
        print(f"REFUSED: {exc}")
        return 2
    before = json.loads((root / MANIFEST).read_text("utf-8"))
    moved = moved_files(before, root)
    if not moved:
        print("nothing to sign: every sealed file at the head matches the manifest")
        return 0
    blocked = [p for p in moved if p in NO_ROTATION]
    if blocked:
        print(f"REFUSED: {blocked} moved but has no QB-002 rotation constant")
        return 2
    problems = binding_problems(moved, rows)
    if problems:
        print("REFUSED:\n  " + "\n  ".join(problems))
        return 2

    signer = AUDITOR
    names = ", ".join(sorted(moved))
    bench_before = (root / QUANTBENCH).read_text("utf-8")
    done = False
    try:
        src = bench_before
        for rel, sha in moved.items():
            if rel in ROTATIONS:
                src = repin(src, ROTATIONS[rel], sha, signer)
        (root / QUANTBENCH).write_text(src, "utf-8")
        if _sign_files_at(root, signer) != 0:
            print("FAILED: --sign-files refused")
            return 1
        after = json.loads((root / MANIFEST).read_text("utf-8"))
        resigned = {
            p
            for p, d in (after.get("files") or {}).items()
            if (before.get("files") or {}).get(p) != d
        }
        if resigned != set(moved):
            print(f"FAILED: the sign touched {sorted(resigned)}, not the bound {sorted(moved)}")
            return 1
        if (after.get("files") or {}) != _hashes_at(root):
            print("FAILED: the manifest does not pin the bytes at the head")
            return 1
        bad = static_qb002(bench_before, src, moved, signer, after)
        if bad:
            print("FAILED: QB-002 would not read green:\n  " + "\n  ".join(bad))
            return 1
        hooks = root.parent / f"{root.name}.nohooks"
        hooks.mkdir(exist_ok=True)
        for leftover in hooks.iterdir():
            print(f"FAILED: the empty hooks folder holds {leftover.name}")
            return 1
        r = subprocess.run(
            (
                "git", "-c", f"core.hooksPath={hooks.as_posix()}", "commit", "-q", "-m",
                f"Sign train at {head[:12]} by {signer}: {names}\n\n"
                "File-only re-sign of IMMUTABLE_MANIFEST plus QB-002 re-pin, same commit, made "
                "by LIVE's sign_train.py from LIVE's SEAL_CLEARS rows for this exact head.",
                "--", MANIFEST, QUANTBENCH,
            ),
            cwd=root,
            check=False,
        )  # fmt: skip
        if r.returncode != 0:
            print("FAILED: commit refused")
            return 1
        mine = _git_in(root, "rev-parse", "HEAD")
        bad = train_commit_problems(root, head, mine)
        if bad:
            print("FAILED: " + "; ".join(bad))
            _git_in(root, "reset", "-q", "--hard", head)
            done = True
            return 1
        done = True
    finally:
        if not done:
            _git_in(root, "checkout", "HEAD", "--", MANIFEST, QUANTBENCH)
            print("manifest and quantbench.py restored at the head")
    print(f"signed {len(moved)} file(s) at {head[:12]}: {names}")
    return 0


def list_heads(live_head: str) -> list[str]:
    """PR heads LIVE's record clears that LIVE does not already contain (G3)."""
    text = _committed_clears(live_head)
    out = []
    for h in heads_named(text):
        if head_clears(text, h) and not _is_ancestor(ROOT, h, live_head):
            out.append(h)
    return out


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--target", required=True, help="the audited commit being signed")
    ap.add_argument(
        "--expect",
        action="append",
        default=[],
        metavar="PATH=SHA256",
        help="the audited full sha256 of each moved sealed file (repeat per file)",
    )
    ap.add_argument(
        "--principal",
        action="store_true",
        help="sign as the principal at a terminal (--expect + type-back) instead of the audit",
    )
    ap.add_argument("--push", action="store_true", help="push the signed commit as a branch")
    ap.add_argument(
        "--root",
        type=Path,
        help="sign the PR head checked out here (data only) from LIVE's rows and LIVE's code",
    )
    ap.add_argument(
        "--list-heads",
        action="store_true",
        help="print the PR heads LIVE's SEAL_CLEARS rows clear, one per line",
    )
    if argv is None:
        argv = sys.argv[1:]
    if "--list-heads" in argv:
        live = _git("rev-parse", "HEAD")
        try:
            heads = list_heads(live)
        except ValueError as exc:
            print(f"REFUSED: {exc}")
            return 2
        for h in heads:
            print(h)
        return 0
    a = ap.parse_args(argv)
    if a.root is not None:
        if a.principal or a.expect or a.push:
            print("REFUSED: --root signs by the audit alone: no --principal, --expect or --push")
            return 2
        if _git("status", "--porcelain", "--untracked-files=no"):
            print("REFUSED: LIVE's checkout has local edits")
            return 2
        return sign_root(a.root, a.target.lower(), _git("rev-parse", "HEAD"))

    head = _git("rev-parse", "HEAD")
    if not head.startswith(a.target.lower()) or len(a.target) < 7:
        print(f"REFUSED: HEAD {head[:12]} is not the named target {a.target}")
        return 2
    if _git("status", "--porcelain", "--", MANIFEST, QUANTBENCH):
        print(f"REFUSED: {MANIFEST} or {QUANTBENCH} already has local edits")
        return 2
    try:
        expect = parse_expect(a.expect)
    except ValueError as exc:
        print(f"REFUSED: {exc}")
        return 2

    before = json.loads((ROOT / MANIFEST).read_text("utf-8"))
    sealed = list(before.get("files") or {})
    dirty = _git("status", "--porcelain", "--", *sealed) if sealed else ""
    if dirty:
        print(f"REFUSED: sealed files differ from the committed target:\n{dirty}")
        return 2
    moved = moved_files(before)
    if not moved:
        if not _qb002_green():
            print("FAILED: nothing moved, yet QB-002 is not green")
            return 1
        print("nothing to sign: every sealed file matches the manifest")
        return 0
    blocked = [p for p in moved if p in NO_ROTATION]
    if blocked:
        print(
            f"REFUSED: {blocked} moved but has no QB-002 rotation constant; that needs an "
            "audited quantbench.py change first"
        )
        return 2
    if a.principal:
        signer = "principal"
    else:
        # The audit signs: only bytes with a CLEAR row committed at the target, never --expect.
        signer = AUDITOR
        if expect:
            print("REFUSED: --expect is for --principal; the audit signs from SEAL_CLEARS.jsonl")
            return 2
        try:
            clears = parse_clears(_committed_clears(head))
        except ValueError as exc:
            print(f"REFUSED: {exc}")
            return 2
        expect = cleared_expect(moved, clears)
    problems = binding_problems(moved, expect)
    if problems:
        print("REFUSED:\n  " + "\n  ".join(problems))
        return 2
    if a.principal and not _confirm(moved):
        return 2

    names = ", ".join(sorted(moved))
    done = False
    try:
        src = (ROOT / QUANTBENCH).read_text("utf-8")
        for rel, sha in moved.items():
            if rel in ROTATIONS:
                src = repin(src, ROTATIONS[rel], sha, signer)
        (ROOT / QUANTBENCH).write_text(src, "utf-8")

        py = sys.executable
        if (
            _run(
                py,
                "scripts/check_immutable_evaluator.py",
                "--sign-files",
                "--by",
                signer,
            )
            != 0
        ):
            print("FAILED: --sign-files refused")
            return 1
        after = json.loads((ROOT / MANIFEST).read_text("utf-8"))
        resigned = {
            p
            for p, d in (after.get("files") or {}).items()
            if (before.get("files") or {}).get(p) != d
        }
        if resigned != set(moved):
            print(f"FAILED: the sign touched {sorted(resigned)}, not the bound {sorted(moved)}")
            return 1
        if _run(py, "scripts/check_immutable_evaluator.py") != 0 or not _qb002_green():
            print("FAILED: evaluator or QB-002 red after the sign")
            return 1

        # Only these two paths go into the commit; hooks run as for any other commit.
        if (
            _run(
                "git",
                "commit",
                "-m",
                f"Sign train at {head[:12]} by {signer}: {names}\n\n"
                "File-only re-sign of IMMUTABLE_MANIFEST plus QB-002 re-pin, same commit.",
                "--",
                MANIFEST,
                QUANTBENCH,
            )
            != 0
        ):
            print("FAILED: commit refused")
            return 1
        mine = _git("rev-parse", "HEAD")
        if mine == head:
            print("FAILED: no commit was made")
            return 1
        if _git("rev-parse", "HEAD~1") != head:
            # Something stacked a commit after ours (a hook, another session). Undoing it would
            # drop work that is not the train's, so touch nothing and hand it to a human.
            done = True
            print(
                f"FAILED: HEAD {mine} does not sit directly on the target {head}; "
                "nothing undone, sort it out by hand"
            )
            # First-parent walk: the train's commit is the oldest first-parent commit above the
            # target. Name it only when its parent and subject prove it is the train's own.
            chain = _git("rev-list", "--first-parent", f"{head}..{mine}").splitlines()
            train = chain[-1] if chain else ""
            subject = _git("log", "-1", "--format=%s", train) if train else ""
            is_ours = (
                bool(train)
                and _git("rev-parse", f"{train}~1") == head
                and subject.startswith(f"Sign train at {head[:12]} by {signer}")
            )
            if is_ours and not _commit_holds(head, moved, train):
                print(f"HALF-SIGN at {train}: it does not carry both files and every re-pin.")
                left = _git("status", "--porcelain", "--", MANIFEST, QUANTBENCH)
                if left:
                    print(f"  left staged or modified, not committed: {left}")
                print("  undo it with:")
                print(f"    git checkout HEAD -- {MANIFEST} {QUANTBENCH}")
                print(f"    git revert --no-edit {train}")
            elif not is_ours:
                print("  could not identify the train's own commit; no undo command offered")
            return 1
        if not _commit_holds(head, moved):
            # HEAD is the train's own commit, alone above the target: safe to take back.
            _git("reset", "-q", "--soft", head)
            print("FAILED: the commit did not carry both files and every re-pin; undone")
            return 1
        done = True
    finally:
        if not done:
            _restore()
            print("manifest and quantbench.py restored to HEAD")

    print(f"signed {len(moved)} file(s): {names}")
    if a.push:
        branch = f"claude/sign-train-{head[:12]}"
        return _run("git", "push", "-u", "origin", f"HEAD:refs/heads/{branch}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
