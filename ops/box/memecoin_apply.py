"""Apply Auditor-CLEARed memecoin packets from the GitLab drop to the box's spot checkout.

Runs as a stage of the box's SYSTEM loop, after drop_pull, so nothing depends on a Claude
session. PAPER ONLY: it merges code the Auditor cleared and restarts one scheduled task. It never
touches CPU budgets, keys, or the trading mode.

Rules it enforces (Autonomy + Audit, 2026-11-24):
  * A packet is applied only if memecoin/verdicts/<id>.json reads exactly "AUDIT CLEAR <head>",
    the manifest names that head, and the bundle's branch tip IS that head.
  * A manifest with "fenced": true is never applied (zuck merges those).
  * Order comes from memecoin/APPLY_ORDER.json; the first refusal stops the run, so a later
    packet never lands ahead of one it depends on.
  * The spot checkout must be clean before any merge. Nothing under it is ever checked out to
    another branch, cleaned, or reset: changes are merges, and an undo is a `git revert`.
  * After merging, a smoke check (byte-compile src/, import src.main) runs with the spot's own
    Python. If it fails, every merge of this run is reverted, newest first.
  * If anything landed, the spot task is restarted with schtasks /End then /Run, nothing else.

The result is written to --out (default C:\\ProgramData\\QuantBox\\memecoin_apply.json): HEAD before
and after, what was applied, skipped and refused and why, the smoke output, and the revert
command for each merge.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import time
from collections.abc import Sequence
from pathlib import Path
from typing import Any

DEFAULT_REPO = r"C:\Users\Administrator\memecoin-codex-stage-20261020\repo"
DEFAULT_TASK = "MemecoinShadowCodex"
DEFAULT_OUT = r"C:\ProgramData\QuantBox\memecoin_apply.json"
SHA = re.compile(r"^[0-9a-f]{40}$")
REF_NS = "refs/memecoin-drop"


class Refused(Exception):
    pass


def git(repo: Path, *args: str, check: bool = True, timeout: float = 900) -> str:
    proc = subprocess.run(
        ["git", "-C", str(repo), *args], capture_output=True, text=True, timeout=timeout
    )
    if check and proc.returncode != 0:
        raise Refused(
            f"git {' '.join(args[:3])} failed: {(proc.stderr or proc.stdout).strip()[:400]}"
        )
    return proc.stdout.strip()


def is_ancestor(repo: Path, a: str, b: str) -> bool:
    return (
        subprocess.run(
            ["git", "-C", str(repo), "merge-base", "--is-ancestor", a, b], capture_output=True
        ).returncode
        == 0
    )


def has_commit(repo: Path, sha: str) -> bool:
    return (
        subprocess.run(
            ["git", "-C", str(repo), "cat-file", "-e", f"{sha}^{{commit}}"], capture_output=True
        ).returncode
        == 0
    )


def read_json(path: Path) -> dict[str, Any]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise Refused(f"{path.name}: unreadable ({type(exc).__name__})") from exc


def bundle_heads(repo: Path, bundle: Path) -> dict[str, str]:
    out = git(repo, "bundle", "list-heads", str(bundle))
    heads = {}
    for line in out.splitlines():
        sha, _, ref = line.partition(" ")
        heads[ref.strip()] = sha.strip()
    return heads


def ensure_clean(repo: Path) -> None:
    if (repo / ".git" / "MERGE_HEAD").exists():
        raise Refused("a merge is already in progress in the spot checkout")
    dirty = git(repo, "status", "--porcelain", "--untracked-files=no")
    if dirty:
        raise Refused("spot checkout has uncommitted changes: " + "; ".join(dirty.splitlines()[:5]))


def verify_packet(drop: Path, packet: str, repo: Path) -> dict[str, Any]:
    manifest = read_json(drop / f"{packet}.json")
    head = str(manifest.get("head") or "")
    branch = str(manifest.get("branch") or "")
    if not SHA.match(head) or not branch:
        raise Refused(f"{packet}: manifest has no exact head/branch")
    verdict = read_json(drop / "verdicts" / f"{packet}.json")
    line = str(verdict.get("line") or "").strip()
    if line != f"AUDIT CLEAR {head}":
        raise Refused(f"{packet}: verdict is {line!r}, not AUDIT CLEAR {head[:9]}")
    bundle = drop / f"{packet}.bundle"
    if not bundle.exists():
        raise Refused(f"{packet}: bundle missing")
    tip = bundle_heads(repo, bundle).get(f"refs/heads/{branch}")
    if tip != head:
        raise Refused(f"{packet}: bundle tip {str(tip)[:9]} is not the CLEARed head {head[:9]}")
    return {
        "packet": packet,
        "head": head,
        "branch": branch,
        "bundle": bundle,
        "fenced": bool(manifest.get("fenced")),
    }


def bring_to_base(repo: Path, drop: Path, base: str, record: dict[str, Any]) -> None:
    """Fast-forward the checkout to the packets' base when it is behind; refuse if diverged."""
    if not SHA.match(base):
        raise Refused("APPLY_ORDER.json has no exact base sha")
    if not has_commit(repo, base):
        main = drop / "main.bundle"
        if not main.exists():
            raise Refused("base commit absent and main.bundle missing")
        git(repo, "fetch", "--no-tags", str(main), f"refs/heads/main:{REF_NS}/main")
    if not has_commit(repo, base):
        raise Refused(f"main.bundle does not contain base {base[:9]}")
    if is_ancestor(repo, base, "HEAD"):
        return
    if not is_ancestor(repo, "HEAD", base):
        raise Refused(f"spot checkout has diverged from base {base[:9]}: needs a person")
    git(repo, "merge", "--ff-only", base)
    record["fast_forward"] = base


def smoke(repo: Path, python: str, timeout: float) -> dict[str, Any]:
    code = (
        "import compileall,sys; ok=compileall.compile_dir('src',quiet=1); "
        "import src.main; sys.exit(0 if ok else 3)"
    )
    try:
        proc = subprocess.run(
            [python, "-c", code], cwd=str(repo), capture_output=True, text=True, timeout=timeout
        )
        return {
            "ok": proc.returncode == 0,
            "rc": proc.returncode,
            "tail": (proc.stderr or proc.stdout)[-1500:],
        }
    except (OSError, subprocess.TimeoutExpired) as exc:
        return {"ok": False, "rc": None, "tail": f"{type(exc).__name__}: {exc}"[:1500]}


def restart(task: str, schtasks: Sequence[str]) -> dict[str, Any]:
    result = {}
    for verb in ("/End", "/Run"):
        proc = subprocess.run(
            [*schtasks, verb, "/TN", task], capture_output=True, text=True, timeout=120
        )
        result[verb.strip("/").lower()] = {
            "rc": proc.returncode,
            "out": (proc.stdout or proc.stderr).strip()[:300],
        }
        if verb == "/End":
            time.sleep(5)
    result["ok"] = result.get("run", {}).get("rc") == 0
    return result


def apply(
    drop_root: Path,
    repo: Path,
    *,
    task: str = DEFAULT_TASK,
    python: str | None = None,
    schtasks: Sequence[str] = ("schtasks",),
    dry_run: bool = False,
    smoke_timeout: float = 600,
) -> dict[str, Any]:
    drop = drop_root / "memecoin"
    record: dict[str, Any] = {
        "schema": "memecoin_apply/1",
        "at": time.time(),
        "repo": str(repo),
        "dry_run": dry_run,
        "applied": [],
        "skipped": {},
        "refused": None,
        "reverted": [],
        "smoke": None,
        "restart": None,
    }
    try:
        if not (repo / ".git").exists():
            raise Refused(f"no git checkout at {repo}")
        record["before"] = git(repo, "rev-parse", "HEAD")
        order = read_json(drop / "APPLY_ORDER.json")
        packets: list[str] = [str(p) for p in order.get("order") or []]
        ensure_clean(repo)
        if dry_run:
            record["plan"] = []
            for name in packets:
                record["plan"].append(verify_packet(drop, name, repo)["packet"])
            return record
        bring_to_base(repo, drop, str(order.get("base") or ""), record)
        for name in packets:
            p = verify_packet(drop, name, repo)  # first refusal stops the run, in order
            if p["fenced"]:
                record["skipped"][p["packet"]] = "fenced: zuck merges it"
                continue
            if is_ancestor(repo, p["head"], "HEAD"):
                record["skipped"][p["packet"]] = "already in"
                continue
            ref = f"{REF_NS}/{p['packet']}"
            git(repo, "fetch", "--no-tags", str(p["bundle"]), f"refs/heads/{p['branch']}:{ref}")
            if git(repo, "rev-parse", ref) != p["head"]:
                raise Refused(f"{p['packet']}: fetched tip differs from the CLEARed head")
            ensure_clean(repo)
            merged = subprocess.run(
                [
                    "git",
                    "-C",
                    str(repo),
                    "-c",
                    "user.name=memecoin_apply",
                    "-c",
                    "user.email=memecoin-apply@box.local",
                    "merge",
                    "--no-ff",
                    "--no-edit",
                    "-m",
                    f"memecoin_apply: {p['packet']} AUDIT CLEAR {p['head']}",
                    p["head"],
                ],
                capture_output=True,
                text=True,
                timeout=900,
            )
            if merged.returncode != 0:
                if (repo / ".git" / "MERGE_HEAD").exists():
                    git(repo, "merge", "--abort", check=False)
                raise Refused(
                    f"{p['packet']}: merge conflict, aborted: "
                    f"{(merged.stdout + merged.stderr).strip()[-300:]}"
                )
            sha = git(repo, "rev-parse", "HEAD")
            record["applied"].append(
                {
                    "packet": p["packet"],
                    "head": p["head"],
                    "merge": sha,
                    "undo": f'git -C "{repo}" revert -m 1 --no-edit {sha}',
                }
            )
    except Refused as exc:
        record["refused"] = str(exc)
    if record["applied"] and not dry_run:
        record["smoke"] = smoke(repo, python or sys.executable, smoke_timeout)
        if not record["smoke"]["ok"]:
            for item in reversed(record["applied"]):
                proc = subprocess.run(
                    [
                        "git",
                        "-C",
                        str(repo),
                        "-c",
                        "user.name=memecoin_apply",
                        "-c",
                        "user.email=memecoin-apply@box.local",
                        "revert",
                        "-m",
                        "1",
                        "--no-edit",
                        item["merge"],
                    ],
                    capture_output=True,
                    text=True,
                    timeout=900,
                )
                record["reverted"].append({"merge": item["merge"], "rc": proc.returncode})
        record["restart"] = restart(task, schtasks)
    try:
        record["after"] = git(repo, "rev-parse", "HEAD")
    except Refused:
        record["after"] = None
    return record


def write_out(path: Path, record: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(json.dumps(record, indent=1, sort_keys=True), encoding="utf-8")
    os.replace(tmp, path)


def main(argv: Sequence[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--drop", required=True, help="checkout of the drop repo (holds memecoin/)")
    ap.add_argument("--repo", default=DEFAULT_REPO, help="the spot checkout")
    ap.add_argument("--task", default=DEFAULT_TASK)
    ap.add_argument("--python", default=None, help="the spot's python for the smoke check")
    ap.add_argument("--out", default=DEFAULT_OUT)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args(argv)
    record = apply(
        Path(args.drop), Path(args.repo), task=args.task, python=args.python, dry_run=args.dry_run
    )
    write_out(Path(args.out), record)
    print(
        json.dumps(
            {k: record.get(k) for k in ("before", "after", "refused")}
            | {"applied": [a["packet"] for a in record["applied"]]}
        )
    )
    failed = record["refused"] or (record["smoke"] and not record["smoke"]["ok"])
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
