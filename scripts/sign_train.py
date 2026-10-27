"""THE WEEKLY SIGN TRAIN -- one principal command signs an audited head and re-pins QB-002 with it.

WHY. A sealed-file change needs two edits that must land together: the principal's file-only
re-sign of IMMUTABLE_MANIFEST.json, and the QB-002 seal rotation in research/quantbench.py
("to" = the new full sha256, signed_by "principal", "from" untouched). Done by hand they came
apart (#329 cleared without the re-pin, test_quantbench read REGRESSED after the merge), and each
re-sign cost the principal a laptop sitting of copied hashes. This script is that sitting.

WHAT IT IS NOT. It does not decide anything and cannot run unattended. It refuses unless HEAD is
the exact commit the principal names and every moved file's bytes are the ones the principal names. It signs with the existing `check_immutable_evaluator.py
--sign-files --by principal`, so the manifest format has one writer.

    python scripts/sign_train.py --target <audited commit> --expect <path>=<audited sha256> ...
    (add --push to push the signed commit as a branch)

It refuses without a terminal, and the principal types back the first 12 hex of each new hash:
the sign stays a real human act. Every moved sealed file must be named by --expect with the exact
audited sha256, so only the bytes the audit cleared can be signed.

On any failed check both files are restored to HEAD and the exit code is non-zero.
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
            problems.append(f"{rel} moved to {moved[rel]} but no --expect names it")
        elif rel not in moved:
            problems.append(f"{rel} is named in --expect but did not move")
        elif moved[rel] != expect[rel]:
            problems.append(f"{rel} is {moved[rel]}, not the audited {expect[rel]}")
    for rel, sha in moved.items():
        if any(sha.startswith(bad) for bad in DENIED):
            problems.append(f"{rel} is {sha[:16]}, which is never signed")
    return problems


def repin(src: str, name: str, new_to: str) -> str:
    """Rewrite one *_SEAL_ROTATION block: new "to", signed_by "principal", "from" kept."""
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
        f'    "to": "{new_to}",\n    "signed_by": "principal",\n}}\n'
    )
    return src[: m.start()] + new + src[m.end() :]


def _run(*cmd: str) -> int:
    return subprocess.run(cmd, cwd=ROOT, check=False).returncode


def _git(*args: str) -> str:
    return subprocess.run(
        ("git", *args), cwd=ROOT, capture_output=True, text=True, check=True
    ).stdout.strip()


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


def _commit_holds(head: str, moved: dict[str, str]) -> bool:
    """The new commit carries both files and every new QB-002 "to" (a hook may unstage one)."""
    files = set(_git("show", "--name-only", "--format=", "HEAD").splitlines())
    if _git("rev-parse", "HEAD~1") != head or not {MANIFEST, QUANTBENCH} <= files:
        return False
    bench = _git("show", f"HEAD:{QUANTBENCH}")
    return all(sha in bench for rel, sha in moved.items() if rel in ROTATIONS)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--target", required=True, help="the audited sha the principal is signing")
    ap.add_argument(
        "--expect",
        action="append",
        default=[],
        metavar="PATH=SHA256",
        help="the audited full sha256 of each moved sealed file (repeat per file)",
    )
    ap.add_argument("--push", action="store_true", help="push the signed commit as a branch")
    a = ap.parse_args(argv)

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
    problems = binding_problems(moved, expect)
    if problems:
        print("REFUSED:\n  " + "\n  ".join(problems))
        return 2
    if not _confirm(moved):
        return 2

    names = ", ".join(sorted(moved))
    done = False
    try:
        src = (ROOT / QUANTBENCH).read_text("utf-8")
        for rel, sha in moved.items():
            if rel in ROTATIONS:
                src = repin(src, ROTATIONS[rel], sha)
        (ROOT / QUANTBENCH).write_text(src, "utf-8")

        py = sys.executable
        if (
            _run(
                py,
                "scripts/check_immutable_evaluator.py",
                "--sign-files",
                "--by",
                "principal",
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
                f"Principal sign train at {head[:12]}: {names}\n\n"
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
