"""THE WEEKLY SIGN TRAIN -- one principal command signs an audited head and re-pins QB-002 with it.

WHY. A sealed-file change needs two edits that must land together: the principal's file-only
re-sign of IMMUTABLE_MANIFEST.json, and the QB-002 seal rotation in research/quantbench.py
("to" = the new full sha256, signed_by "principal", "from" untouched). Done by hand they came
apart (#329 cleared without the re-pin, test_quantbench read REGRESSED after the merge), and each
re-sign cost the principal a laptop sitting of copied hashes. This script is that sitting.

WHAT IT IS NOT. It does not decide anything. It refuses unless HEAD is the exact sha the principal
names, and the principal runs it. It signs with the existing `check_immutable_evaluator.py
--sign-files --by principal`, so the manifest format has one writer.

    python scripts/sign_train.py --target <audited sha>            # sign, re-pin, verify, commit
    python scripts/sign_train.py --target <audited sha> --push     # ... and push a branch

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


def full_sha(rel: str, root: Path = ROOT) -> str:
    # Same normalisation as check_immutable_evaluator._hashes and quantbench._sha.
    return hashlib.sha256((root / rel).read_bytes().replace(b"\r\n", b"\n")).hexdigest()


def moved_files(manifest: dict, root: Path = ROOT) -> dict[str, str]:
    """Signed files whose bytes no longer match the manifest: {path: new full sha256}."""
    out = {}
    for rel, digest in (manifest.get("files") or {}).items():
        p = root / rel
        if p.exists():
            now = full_sha(rel, root)
            if now[:16] != digest:
                out[rel] = now
    return out


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
    new = (f'{name} = {{\n    "path": "{path.group(1)}",\n    "from": "{frm.group(1)}",\n'
           f'    "to": "{new_to}",\n    "signed_by": "principal",\n}}\n')
    return src[:m.start()] + new + src[m.end():]


def _run(*cmd: str) -> int:
    return subprocess.run(cmd, cwd=ROOT, check=False).returncode


def _git(*args: str) -> str:
    return subprocess.run(("git", *args), cwd=ROOT, capture_output=True, text=True,
                          check=True).stdout.strip()


def _restore() -> None:
    _git("checkout", "HEAD", "--", MANIFEST, QUANTBENCH)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--target", required=True, help="the audited sha the principal is signing")
    ap.add_argument("--push", action="store_true", help="push the signed commit as a branch")
    a = ap.parse_args(argv)

    head = _git("rev-parse", "HEAD")
    if not head.startswith(a.target.lower()) or len(a.target) < 7:
        print(f"REFUSED: HEAD {head[:12]} is not the named target {a.target}")
        return 2
    if _git("status", "--porcelain", "--", MANIFEST, QUANTBENCH):
        print(f"REFUSED: {MANIFEST} or {QUANTBENCH} already has local edits")
        return 2

    manifest = json.loads((ROOT / MANIFEST).read_text("utf-8"))
    moved = moved_files(manifest)
    if not moved:
        print("nothing to sign: every sealed file matches the manifest")
        return 0
    blocked = [p for p in moved if p in NO_ROTATION]
    if blocked:
        print(f"REFUSED: {blocked} moved but has no QB-002 rotation constant; that needs an "
              "audited quantbench.py change first")
        return 2

    src = (ROOT / QUANTBENCH).read_text("utf-8")
    for rel, sha in moved.items():
        if rel in ROTATIONS:
            src = repin(src, ROTATIONS[rel], sha)
    (ROOT / QUANTBENCH).write_text(src, "utf-8")

    py = sys.executable
    ok = (_run(py, "scripts/check_immutable_evaluator.py", "--sign-files", "--by", "principal")
          == 0
          and _run(py, "scripts/check_immutable_evaluator.py") == 0
          and _run(py, "-m", "pytest", "desks/mt5/tests/test_quantbench.py", "-q") == 0)
    if not ok:
        _restore()
        print("FAILED: checks red; manifest and quantbench.py restored to HEAD")
        return 1

    names = ", ".join(sorted(moved))
    _git("add", MANIFEST, QUANTBENCH)
    # Hooks run: this commit goes through the same law gate as any other.
    if _run("git", "commit", "-m", f"Principal sign train at {head[:12]}: {names}\n\n"
            "File-only re-sign of IMMUTABLE_MANIFEST plus QB-002 re-pin, same commit.") != 0:
        _restore()
        print("FAILED: commit refused; manifest and quantbench.py restored to HEAD")
        return 1
    print(f"signed {len(moved)} file(s): {names}")
    if a.push:
        branch = f"claude/sign-train-{head[:12]}"
        return _run("git", "push", "-u", "origin", f"HEAD:refs/heads/{branch}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
