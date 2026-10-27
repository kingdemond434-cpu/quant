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

`--principal` keeps the human path: it refuses without a terminal and the principal types back
the first 12 hex of each new hash. It signs with the existing `check_immutable_evaluator.py
--sign-files --by <signer>`, so the manifest format has one writer.

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


REPORT = re.compile(r"(/mnt/project-files/)?reports/audit/\S+\.md")
HEX64 = re.compile(r"[0-9a-f]{64}")


def parse_clears(text: str) -> dict[str, set[str]]:
    """{path: {sha256 the audit cleared}} from SEAL_CLEARS.jsonl text, failing closed.

    Every non-blank line must be a well-formed row, or the whole record is refused (ValueError):
    a garbled line is not a quiet "no". Any HOLD for a path's sha256 outranks every CLEAR for it,
    whichever came first.
    """
    cleared: dict[str, set[str]] = {}
    held: dict[str, set[str]] = {}
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
        if not isinstance(report, str) or not REPORT.fullmatch(report):
            raise ValueError(f"{SEAL_CLEARS}:{n} report must be a reports/audit/...md path")
        if report_sha is not None and (
            not isinstance(report_sha, str) or not HEX64.fullmatch(report_sha)
        ):
            raise ValueError(f"{SEAL_CLEARS}:{n} report_sha256 is not 64 lower-case hex")
        (cleared if verdict == "CLEAR" else held).setdefault(path, set()).add(sha)
    out = {p: shas - held.get(p, set()) for p, shas in cleared.items()}
    return {p: shas for p, shas in out.items() if shas}


def append_only_problems(versions: list[bytes]) -> list[str]:
    """Each committed version of the CLEAR record, oldest first, must be a prefix of the next."""
    return [
        f"version {i + 1} of {SEAL_CLEARS} rewrites an earlier row"
        for i in range(1, len(versions))
        if not versions[i].startswith(versions[i - 1])
    ]


def _committed_clears(head: str) -> str:
    """The CLEAR record at the target, after proving its history only ever appended."""
    if _git("rev-parse", "--is-shallow-repository") == "true":
        raise ValueError("shallow clone: the CLEAR record's history cannot be proven append-only")
    shas = _git("log", "--format=%H", "--reverse", head, "--", SEAL_CLEARS).splitlines()
    versions = []
    for sha in shas:
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
