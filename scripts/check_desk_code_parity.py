#!/usr/bin/env python3
"""IS THE TRADING BOX RUNNING THIS REPO'S MONEY-PATH CODE? Hash it there and find out.

WHY THIS EXISTS (measured 2026-08-27). `forward_reconcile.py` carried a fatal unpack bug for a
full day. The fix was written, tested and committed here -- and would have changed NOTHING,
because the only code-sync path on this desk (`ops/run_external_pipeline.sh` stage 0) ships a
HARDCODED FOUR-FILE list, and the entire forward/promotion chain the box actually executes is
outside it. A hardcoded list that silently caps what can be deployed is the WS-005 class: the
absence of a sync read exactly like a successful one.

This desk has been burned by every cheaper check:
  * `scp` exits 0 in cases that did not land, the same way `git push` exits 0 on a reject
  * a committed fix is INERT until the process actually restarts -- and doubly inert if it never
    reached the box at all
  * the box is on a branch diverged 348/233 from this one, so no `git pull` there delivers
    anything; scp is the route, and scp needs verifying

So parity is measured the only way that cannot lie: `git hash-object` run ON the box, compared to
`git hash-object` run here. Not mtime, not size, not exit code.

THE REGISTRY IS THE MONEY-PATH FENCE ITSELF. There is no second list to drift: whatever the desk
has declared money-path-critical is what gets checked. A file the fence protects but the box has
never heard of is reported MISSING, not skipped -- absence is never a clean verdict.

Read-only. This never ships anything; it reports what diverged so a human or the pipeline can.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
REMOTE = "contabo-mt5"
REMOTE_ROOT = r"C:\opt\quant"
OUT = ROOT / "data" / "desk_code_parity.json"


def protected_files() -> list[str]:
    """The money-path registry, read from the fence so the two can never disagree."""
    spec = importlib.util.spec_from_file_location(
        "_mpf", ROOT / "scripts" / "check_moneypath_fence.py")
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot load the money-path fence to read its registry")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return sorted(str(k) for k in mod.PROTECTED)


def local_hashes(files: list[str]) -> dict[str, str]:
    """SHA256 of the RAW BYTES -- never `git hash-object`.

    `git hash-object` applies the repository's own clean filters, and the desk box's git
    normalises line endings while this one does not: `run_hunt17.py` was byte-for-byte identical
    on both boxes (cmp confirmed it) and still hashed differently. A fence that cries wolf on one
    file in twenty-five every run is a fence nobody reads, which is how the real divergence next
    to it survives. Bytes are what the interpreter executes, so bytes are what this compares.
    """
    out: dict[str, str] = {}
    for f in files:
        path = ROOT / f
        if path.exists():
            out[f] = hashlib.sha256(path.read_bytes()).hexdigest()
    return out


def remote_hashes(files: list[str], timeout: int) -> dict[str, str] | None:
    """None means UNREACHABLE -- never an empty dict, which would read as 'everything missing'."""
    # Per-file so one absent path cannot abort the batch and blank every other verdict.
    script = " ; ".join(
        f'if (Test-Path "{f}") {{ (Get-FileHash -Algorithm SHA256 "{f}").Hash.ToLower() }} '
        f'else {{ "MISSING" }}' for f in files)
    try:
        res = subprocess.run(
            ["ssh", "-o", "ConnectTimeout=20", REMOTE,
             f'powershell -Command "cd {REMOTE_ROOT} ; {script}"'],
            capture_output=True, text=True, timeout=timeout)
    except (subprocess.TimeoutExpired, OSError):
        return None
    lines = [ln.strip() for ln in res.stdout.replace("\r", "").splitlines() if ln.strip()]
    lines = [ln for ln in lines if ln == "MISSING" or len(ln) == 64]
    if len(lines) != len(files):
        return None
    return dict(zip(files, lines, strict=False))


def heal(diverged: list[dict[str, str]], missing: list[str], timeout: int) -> list[str]:
    """Ship the money-path files the desk is missing or has drifted on, verified by re-hash.

    DETECTION WITHOUT REPAIR IS A HUMAN LOOP (principal 2026-08-27: "everything should always be
    automated without me or you"). This check ran every 30 minutes for weeks, correctly reported
    DIVERGED, and waited for a person -- so the desk box traded on stale engines for hours at a
    time while a green-looking report accumulated.

    THE ORDER MATTERS AND IS NOT NEGOTIABLE. A replayer reverts this tree to ancient copies on
    roughly an hourly cadence, so shipping "local" blindly would push a trample straight onto the
    box that trades. The money-path fence runs FIRST: it restores any protected file that has
    lost its canon marker, and only a tree that then passes may be shipped. If the fence cannot
    heal the tree, nothing is shipped and the divergence is left standing and loud.
    """
    fence = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "check_moneypath_fence.py")],
        cwd=ROOT, capture_output=True, text=True, timeout=timeout, check=False)
    if fence.returncode != 0:
        print("  HEAL REFUSED: the money-path fence cannot bring this tree to canon; "
              "shipping unverified code to the trading box is never the safer option")
        return []
    shipped: list[str] = []
    for rel in [d["file"] for d in diverged] + list(missing):
        src = ROOT / rel
        if not src.is_file():
            continue
        res = subprocess.run(["scp", "-q", str(src), f"{REMOTE}:C:/opt/quant/{rel}"],
                             capture_output=True, text=True, timeout=timeout, check=False)
        if res.returncode == 0:
            shipped.append(rel)
            print(f"  HEALED {rel} -> {REMOTE}")
        else:
            print(f"  HEAL FAILED {rel}: {(res.stderr or '').strip()[:120]}")
    return shipped


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--timeout", type=int, default=300)
    ap.add_argument("--quiet", action="store_true")
    ap.add_argument("--heal", action="store_true",
                    help="ship diverged/missing money-path files to the desk after the "
                         "money-path fence verifies this tree")
    args = ap.parse_args()

    files = protected_files()
    local = local_hashes(files)
    remote = remote_hashes(files, args.timeout)
    now = datetime.now(tz=UTC).isoformat(timespec="seconds")

    if remote is None:
        # UNREACHABLE is its own verdict. A box this check cannot see is not a box in parity, and
        # it is not a box out of parity either -- saying either would be fabricating a reading.
        unreachable: dict[str, object] = {
            "checked_at": now, "status": "UNREACHABLE", "remote": REMOTE,
            "why": "the desk box did not answer; parity is UNMEASURED, not clean"}
        OUT.write_text(json.dumps(unreachable, indent=1), "utf-8")
        print(f"desk code parity: UNREACHABLE ({REMOTE}) -- parity UNMEASURED, not clean")
        return 2

    diverged: list[dict[str, str]] = []
    missing: list[str] = []
    matched: list[str] = []
    for f in files:
        want, have = local.get(f), remote.get(f)
        if want is None:
            continue          # not in this checkout; nothing to compare against
        if have == "MISSING":
            missing.append(f)
        elif have == want:
            matched.append(f)
        else:
            diverged.append({"file": f, "local": want, "remote": have or "UNREADABLE"})

    doc: dict[str, object] = {
        "checked_at": now, "remote": REMOTE,
        "status": "OK" if not diverged else "DIVERGED",
        "n_checked": len(local), "n_matched": len(matched),
        "diverged": diverged, "missing_on_desk": missing}
    OUT.write_text(json.dumps(doc, indent=1), "utf-8")

    if (diverged or missing) and args.heal:
        shipped = heal(diverged, missing, args.timeout)
        if shipped:
            # RE-VERIFY: scp exits 0 in cases that did not land, which is this module's own
            # founding lesson. The stored verdict reflects the box as it is AFTER healing.
            remote2 = remote_hashes(files, args.timeout) or {}
            diverged = [d for d in diverged if remote2.get(d["file"]) != local.get(d["file"])]
            missing = [f for f in missing if remote2.get(f) == "MISSING"]
            doc["healed"] = shipped
            doc["status"] = "OK" if not diverged else "DIVERGED"
            doc["diverged"], doc["missing_on_desk"] = diverged, missing
            doc["checked_at"] = datetime.now(tz=UTC).isoformat(timespec="seconds")
            OUT.write_text(json.dumps(doc, indent=1), "utf-8")

    if not args.quiet:
        for d in diverged:
            print(f"  DIVERGED {d['file']}\n    here {d['local']}\n    box  {d['remote']}")
        for f in missing:
            print(f"  MISSING-ON-DESK {f}")
    print(f"desk code parity: {len(matched)}/{len(local)} money-path module(s) byte-identical "
          f"on {REMOTE}; {len(diverged)} diverged, {len(missing)} missing")
    return 1 if diverged else 0


if __name__ == "__main__":
    sys.exit(main())
