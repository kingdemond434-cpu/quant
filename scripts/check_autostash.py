#!/usr/bin/env python
"""NO IMPLICIT STASH, IN ANY SCOPE (R0423) -- the fence for the ban nothing could grep.

R0423 bans `git stash` in this tree, and every session reads that as a ban on TYPING it. It is
not. `merge.autoStash` and `rebase.autoStash` make git run a stash IMPLICITLY, before the merge
or rebase body, with no script naming the command anywhere -- so a grep for "stash" over ops/,
scripts/ and desks/ returns clean on a box where every single `git pull` stashes first. The ban
was enforced by reading habits and by nothing else.

WHY IT MATTERS HERE SPECIFICALLY, and it is not a style point. The trading box's working tree
carries ~21,884 modified and untracked paths: the price bars, the intelligence corpora and every
live ledger the desk writes. An autostash over that tree either takes minutes while holding the
index lock that `Adopt-Release.ps1` already fights for, or fails halfway and parks the entire
live research state in a stash entry no organ knows to pop. The first costs an adoption window;
the second loses the desk's state with no error anyone reads.

WHAT THIS PROVES, and why each half is needed.

1. NO SCOPE SETS IT TRUE. Not the effective value alone -- EVERY scope git reports (system,
   global, local, worktree, command, and the GIT_CONFIG_* environment). A `true` in a wide scope
   that a narrow scope currently overrides is not safe: it is one `git -C` somewhere else, one
   fresh clone, or one deleted local line away from being the effective value. The fence names
   the scope and the origin file, because "autostash is on" is unactionable until you know which
   file to edit.

2. NO STASH ENTRY EXISTS. A stash in this tree is always one of exactly two things: a banned
   operation somebody ran, or the wreckage of an autostash that failed halfway. Neither is a
   state to leave sitting, and both are invisible in `git status`. The entries are listed, never
   dropped -- this fence reports, and dropping a stash is precisely the "acting on an absence"
   that LAWS 7 refuses.

UNSET IS A PASS, AND IS SAID OUT LOUD. git's own default for both keys is false, so an unset key
is already safe and failing on it would paint every clean clone and every CI run red -- which is
how a gate gets switched off (L1.43). It is reported as UNPINNED in the artifact and in the
notes, because the measured history of this defect class is that config drifts back, and
`--pin` is the one-command repair that closes it.

PORTABLE. It reads git's own configuration and ref state on whatever host it runs on, so it
means the same in CI, in a fresh clone, on the VPS and on the trading box. Registered in
`scripts/run_law_gate.py` (`_LAW_FENCES`): the boundary that matters is the COMMIT and the PUSH,
because a config that has drifted true is already dangerous before any hourly clock comes round.

Artifact: `desks/mt5/reports/AUTOSTASH_FENCE.json`.

    python scripts/check_autostash.py
    python scripts/check_autostash.py --json
    python scripts/check_autostash.py --pin     # set both to false at local scope, then re-check
"""
from __future__ import annotations

import argparse
import json
import subprocess
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "desks" / "mt5" / "reports" / "AUTOSTASH_FENCE.json"

#: The two keys that make git stash without being asked. Lower-cased because `git config --list`
#: normalises key case on output while `--get` accepts the camelCase spelling documented by git.
KEYS: tuple[str, ...] = ("merge.autostash", "rebase.autostash")

#: How the keys are spelled when SET, so the repair writes what a human reading .git/config
#: recognises from the git documentation.
CANONICAL: dict[str, str] = {"merge.autostash": "merge.autoStash",
                             "rebase.autostash": "rebase.autoStash"}

UNMEASURED = "UNMEASURED"

#: git renders booleans in several spellings; these are the ones it accepts as TRUE.
_TRUE = {"true", "yes", "on", "1", ""}


def _git(root: Path, *args: str, timeout: float = 60.0) -> tuple[int, str]:
    """(returncode, stdout). A failure to run is (-1, "") and is never read as a clean answer."""
    try:
        r = subprocess.run(["git", *args], cwd=root, capture_output=True, text=True,
                           errors="replace", timeout=timeout)
    except (OSError, subprocess.SubprocessError):
        return -1, ""
    return r.returncode, r.stdout


def _is_true(value: str) -> bool:
    return value.strip().lower() in _TRUE


def scan(root: Path | None = None) -> dict[str, Any]:
    """Every scope that mentions either key, the effective value, and the stash list."""
    base = Path(root or ROOT)
    doc: dict[str, Any] = {
        "generated": datetime.now(tz=UTC).isoformat(timespec="seconds"),
        "root": str(base), "keys": list(KEYS),
        "effective": {}, "scopes": [], "stash": {}, "problems": [], "notes": [], "ok": True,
    }

    rc, ver = _git(base, "--version")
    if rc != 0:
        doc["ok"] = False
        doc["measured"] = False
        doc["problems"].append(
            "git is not runnable here, so neither key can be read: UNMEASURED. A fence that "
            "cannot prove the law holds must not claim it does (L1.28a)")
        return doc
    doc["measured"] = True
    doc["git_version"] = ver.strip()

    # ---- 1. EVERY SCOPE, not just the winner.  `--show-scope` names system/global/local/
    # worktree/command; `--show-origin` names the exact file, which is the only actionable half.
    rc, listing = _git(base, "config", "--list", "--show-scope", "--show-origin")
    if rc != 0:
        doc["ok"] = False
        doc["measured"] = False
        doc["problems"].append(
            "`git config --list --show-scope` failed, so the scopes cannot be enumerated: "
            "UNMEASURED, which is a real answer and never a pass")
        return doc
    for line in listing.splitlines():
        # scope \t origin \t key=value -- the origin itself may contain no tab, and a value may.
        parts = line.split("\t")
        if len(parts) < 3:
            continue
        scope, origin, kv = parts[0], parts[1], "\t".join(parts[2:])
        key, _, value = kv.partition("=")
        if key.strip().lower() not in KEYS:
            continue
        row = {"scope": scope.strip(), "origin": origin.strip(), "key": key.strip(),
               "value": value, "true": _is_true(value)}
        doc["scopes"].append(row)

    # ---- 2. THE EFFECTIVE VALUE, which is what git will actually do on the next merge.
    for key in KEYS:
        rc, val = _git(base, "config", "--bool", "--get", CANONICAL[key])
        doc["effective"][CANONICAL[key]] = val.strip() if rc == 0 else None

    # ---- 3. THE STASH ITSELF. Repo-wide and shared by every linked worktree, so this answers
    # for the whole checkout no matter which worktree the gate is judging from.
    rc, stash = _git(base, "stash", "list")
    entries = [ln for ln in stash.splitlines() if ln.strip()]
    doc["stash"] = {"measured": rc == 0, "n": len(entries) if rc == 0 else UNMEASURED,
                    "entries": entries[:40]}

    # ---- the verdict
    for row in doc["scopes"]:
        if row["true"]:
            doc["problems"].append(
                f"{row['key']} is TRUE at {row['scope']} scope ({row['origin']}): git will stash "
                f"implicitly before a merge or rebase. On the trading box that stashes ~21,884 "
                f"live paths -- the bars, the corpora and every ledger -- under the index lock "
                f"Adopt-Release already contends for. Repair: "
                f"git config --{row['scope']} {CANONICAL[row['key'].lower()]} false")
    for key in KEYS:
        eff = doc["effective"].get(CANONICAL[key])
        if eff is None:
            doc["notes"].append(
                f"{CANONICAL[key]} is UNPINNED in every scope. git's own default is false, so "
                f"this is safe today and is not a breach -- but it is the state this defect "
                f"class drifts back from. Pin it: python scripts/check_autostash.py --pin")
        elif _is_true(eff):
            doc["problems"].append(
                f"{CANONICAL[key]} resolves to {eff!r}: an implicit stash is armed right now")
    if doc["stash"]["measured"] and entries:
        doc["problems"].append(
            f"{len(entries)} stash entry(ies) exist. In this tree a stash is always either a "
            f"banned operation (R0423) or the wreckage of an autostash that failed halfway; "
            f"either way it is live desk state parked where no organ will pop it. Inspect with "
            f"`git stash list` and `git stash show -p stash@{{0}}` -- this fence never drops one")
    elif not doc["stash"]["measured"]:
        doc["problems"].append(
            "`git stash list` failed: whether state is parked in a stash is UNMEASURED, which is "
            "a real answer and not a pass")
    doc["ok"] = not doc["problems"]
    return doc


def pin(root: Path | None = None) -> list[str]:
    """Set both keys to false at LOCAL scope. Never touches global or system.

    Local only, on purpose: this repository is what the ban is about, the trading box and the
    build box each own their own checkout, and a fence that rewrote a developer's global git
    configuration would be reaching outside its subject.
    """
    base = Path(root or ROOT)
    done: list[str] = []
    for key in KEYS:
        rc, _ = _git(base, "config", "--local", CANONICAL[key], "false")
        done.append(f"{CANONICAL[key]}=false ({'set' if rc == 0 else 'FAILED'})")
    return done


def write_artifact(doc: dict[str, Any], target: Path | None = None) -> Path:
    path = Path(target or OUT)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(doc, indent=2, default=str) + "\n", encoding="utf-8")
    return path


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=(__doc__ or "").splitlines()[0])
    ap.add_argument("--json", action="store_true", help="print the artifact as JSON")
    ap.add_argument("--no-write", action="store_true", help="do not write the artifact")
    ap.add_argument("--pin", action="store_true",
                    help="set both keys to false at local scope, then re-measure")
    args = ap.parse_args(argv)

    if args.pin:
        for line in pin():
            print(f"  pinned: {line}")

    doc = scan()
    if not args.no_write:
        write_artifact(doc)
    if args.json:
        print(json.dumps(doc, indent=2, default=str))
        return 0 if doc["ok"] else 1

    eff = ", ".join(f"{k}={v if v is not None else 'UNSET'}"
                    for k, v in doc["effective"].items()) or UNMEASURED
    print(f"autostash: effective {eff}; "
          f"{len(doc['scopes'])} scope(s) mention it; "
          f"stash entries {doc['stash'].get('n', UNMEASURED)}")
    for row in doc["scopes"]:
        print(f"  {row['scope']:<8} {row['key']}={row['value']}  [{row['origin']}]")
    for note in doc["notes"]:
        print(f"  note: {note}")
    for problem in doc["problems"]:
        print(f"  FAIL: {problem}")
    if doc["ok"]:
        print("check_autostash: OK -- no implicit stash is reachable and no stash entry exists")
        return 0
    print("check_autostash: FAILED")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
