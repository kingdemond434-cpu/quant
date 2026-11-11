"""THE MEMECOIN REPO'S AUTO MERGE PATH, run by the box sweep beside audit_gate.py.

WHY (zuck 2026-11-03, via the coordinator: "zero taps everywhere"). Every kingdemond434-cpu/memecoin
PR still needed his manual merge. The bot trades paper only, so a reviewed, green change is a
low-risk change -- except one that can move it toward live money. That stays his.

THE RULE. The box (zuck's own gh login, `--box`) merges an open, non-draft memecoin PR into
`main` only when ALL of these hold, and does nothing on any doubt:

  1. LIVE FENCE: no changed path is a LIVE_PATHS pattern, and no added or removed diff line
     names a LIVE_WORDS token (the paper/live switch, the earned-stage ladder, the signer's
     acknowledgement, the execution venue). A fenced PR is zuck's: it is never merged here.
     A file list or patch the API truncates or omits reads as fenced (fail closed).
  2. AUDITOR CLEAR: the latest row for this PR in the box-local memecoin registry
     (MEMECOIN_REGISTRY_ENV, rows {"pr","sha","verdict","at"}, a file no PR can write) is CLEAR
     for the EXACT head. A HOLD row is a veto. The registry is separate from quant's, so PR
     numbers of the two repos never collide.
  3. VETO WINDOW: audit_gate's own registry window -- the gate sends the veto notice itself
     and the REGISTRY_HOLD_H window starts only when it was DELIVERED, by the gate's clock.
  4. GREEN: every REQUIRED_JOBS check run on the head concluded success, and no other check run
     on it failed or is still running.
  5. UP TO DATE with main (a behind PR is brought up with update-branch and waits for its
     fresh CI); the merge is pinned to the head sha.
  6. NOT DISABLED: no DISABLE_FILE beside the registry.

AUTO-REVERT: a registry merge whose `ci` on main fails while its first parent's passed is
reverted on main, using audit_gate.auto_revert in the memecoin clone.

    python memecoin_gate.py --box --clone C:\\ProgramData\\QuantBox\\memecoin-gate
"""

from __future__ import annotations

import argparse
import fnmatch
import os
import re
import sys
from collections.abc import Callable, Iterable, Mapping
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))
import audit_gate as ag

REPO = "kingdemond434-cpu/memecoin"
BASE = "main"
MEMECOIN_REGISTRY_ENV = "MEMECOIN_AUDIT_REGISTRY"
DISABLE_FILE = "memecoin.disabled"
#: The memecoin ci workflow's jobs (.github/workflows/ci.yml); all three must pass.
REQUIRED_JOBS = ("windows-native", "python", "rust")
#: Paths that can change how, whether or where the bot trades for real, or what CI checks.
LIVE_PATHS = (
    ".github/*", "deploy/*", "deploy.sh", "Dockerfile", "docker-compose*.yml", "*.service",
    "config/chains.yaml", "src/execution/*", "src/research/promotion_gate.py",
    "ops/autodeploy.py", "ops/bounded_release.py", "*.env", "*.env.*", "*secret*", "*wallet*",
    "*keypair*",
    # the Rust transaction builder and signer
    "native/solana_fastpath/src/transaction.rs", "native/solana_fastpath/src/bindings.rs",
    "native/solana_fastpath/src/message.rs", "native/solana_fastpath/build.rs",
    # dependency manifests: a supply-chain path to the key and the signer
    "pyproject.toml", "*/pyproject.toml", "requirements*.txt", "*/requirements*.txt",
    "Cargo.toml", "*/Cargo.toml", "Cargo.lock", "*/Cargo.lock", "*.lock", "package.json",
    "*/package.json", "package-lock.json", "*/package-lock.json", "setup.py", "setup.cfg",
)  # fmt: skip
#: A diff line naming one of these touches the paper/live switch or the live ladder.
LIVE_WORDS = re.compile(
    r"ALLOW_LIVE_TRADING|dry_run|live_submission|paper_equity|Stage\.(CANARY|LIVE)"
    r"|promotion_gate|signer|keypair|private_key|jito|send_transaction|sendTransaction"
    # the CLI switch, the signer acknowledgement and its halves, and ANY environment write
    r"|yes-i-understand|LIVE_TRADING|i-understand|dry_override|args\.live|--live|is_live"
    r"|os\.environ\s*\[|environ\.(setdefault|update)|putenv"
    # Rust signing
    r"|\.sign\(|SigningKey|Signature::new",
    re.IGNORECASE,
)
OK = ("success", "skipped", "neutral")
#: Only GitHub Actions' own check runs count for REQUIRED_JOBS; any installed App can post a name.
ACTIONS_APP = "github-actions"
MAX_FILES = 3000


def fenced(files: Iterable[Mapping[str, Any]]) -> str | None:
    """Why this PR is zuck's (the live fence), or None. Pure."""
    n = 0
    for f in files:
        n += 1
        name = str(f.get("filename") or "")
        prev = str(f.get("previous_filename") or "")
        for path in filter(None, (name, prev)):
            if any(fnmatch.fnmatch(path, p) for p in LIVE_PATHS):
                return f"{path} is on the live fence"
        patch = f.get("patch")
        pure_rename = f.get("status") == "renamed" and int(f.get("changes") or 0) == 0
        if patch is None and not pure_rename:
            # a binary file or an oversized diff has no patch: fail closed
            return f"{name}: the API returned no patch to read, so the fence cannot clear it"
        for line in str(patch or "").splitlines():
            if line[:1] in "+-" and not line.startswith(("+++", "---")) and LIVE_WORDS.search(line):
                return f"{name}: a changed line names the live switch ({line[:80].strip()!r})"
    if n == 0:
        return "the PR's file list is empty or unreadable"
    if n >= MAX_FILES:
        return f"the file list may be truncated at {n}"
    return None


def green(runs: Iterable[Mapping[str, Any]]) -> tuple[bool, str]:
    """(every required job passed and nothing failed or runs; why). Pure."""
    by: dict[str, list[Mapping[str, Any]]] = {}
    for r in runs:
        by.setdefault(str(r.get("name")), []).append(r)
    for name, rs in by.items():
        for r in rs:
            if r.get("status") != "completed":
                return False, f"{name} is still {r.get('status')}"
            if r.get("conclusion") not in OK:
                return False, f"{name} concluded {r.get('conclusion')}"
    missing = [
        j
        for j in REQUIRED_JOBS
        if not any(
            r.get("conclusion") == "success" and (r.get("app") or {}).get("slug") == ACTIONS_APP
            for r in by.get(j, [])
        )
    ]
    if missing:
        return False, f"no passing run of {missing}"
    return True, "every required job passed"


def decide(
    pr: Mapping[str, Any],
    files: list[Mapping[str, Any]],
    runs: list[Mapping[str, Any]],
    behind: int | None,
    rows: list[dict[str, Any]],
    window: Callable[[], tuple[datetime | None, str]],
    now: datetime,
) -> tuple[str, str]:
    """("merge" | "bring_up" | "wait" | "zuck", why) for one PR. Pure apart from `window`."""
    if pr.get("draft"):
        return "wait", "draft"
    if pr.get("base", {}).get("ref") != BASE:
        return "wait", f"base is {pr.get('base', {}).get('ref')}, not {BASE}"
    why = fenced(files)
    if why:
        return "zuck", why
    head = str(pr["head"]["sha"])
    ok, gwhy = green(runs)
    if not ok:
        return "wait", gwhy
    if behind is None:
        return "wait", "could not read how far behind main it is"
    if behind > 0:
        return "bring_up", f"{behind} commit(s) behind {BASE}"
    clear, cwhy = ag.registry_clear(rows, int(pr["number"]), head, window, now=now)
    if clear is None:
        return "wait", cwhy
    return "merge", cwhy


def sweep(registry: str, clone: str | None, now: datetime | None = None) -> int:
    now = now or datetime.now(UTC)
    reg = Path(registry)
    if (reg.parent / DISABLE_FILE).exists():
        ag._summary(f"memecoin auto-merge DISABLED ({DISABLE_FILE} present)")
        return 0
    rows, rwhy = ag.registry_rows(registry)
    if rwhy:
        ag._summary(f"memecoin registry: {rwhy}")
    seen = reg.with_suffix(reg.suffix + ".window.json")
    rc = 0
    try:
        prs = ag._gh(f"repos/{REPO}/pulls?state=open&base={BASE}&per_page=50") or []
    except RuntimeError as exc:
        ag._summary(f"memecoin: cannot list PRs: {exc}")
        return 1
    for pr in prs:
        n, head = int(pr["number"]), str(pr["head"]["sha"])
        try:
            files = ag._flat(
                ag._gh(f"repos/{REPO}/pulls/{n}/files?per_page=100", "--paginate", "--slurp")
            )
            pages = ag._flat_pages(
                ag._gh(
                    f"repos/{REPO}/commits/{head}/check-runs?per_page=100", "--paginate", "--slurp"
                )
            )
            runs = [r for pg in pages if isinstance(pg, dict) for r in pg.get("check_runs") or []]
            cmp = ag._gh(f"repos/{REPO}/compare/{BASE}...{head}") or {}
            behind = cmp.get("behind_by")
            verdict, why = decide(
                pr,
                files,
                runs,
                behind if isinstance(behind, int) else None,
                rows,
                lambda n=n, head=head: ag.registry_window(seen, n, head, now, ag.run_notify),
                now,
            )
            if verdict == "bring_up":
                ag._gh(
                    f"repos/{REPO}/pulls/{n}/update-branch",
                    "-X",
                    "PUT",
                    data={"expected_head_sha": head},
                )
            elif verdict == "merge":
                ag._gh(
                    f"repos/{REPO}/pulls/{n}/merge",
                    "-X",
                    "PUT",
                    data={
                        "sha": head,
                        "merge_method": "merge",
                        "commit_title": f"Merge #{n}: {ag.REGISTRY_TITLE} {head[:9]}",
                    },
                )
            ag._summary(f"memecoin #{n} {head[:9]}: {verdict.upper()} -- {why}")
        except (RuntimeError, KeyError, TypeError, ValueError) as exc:
            ag._summary(f"memecoin #{n}: skipped this sweep ({exc})")
            rc = 1
    if clone:
        here = os.getcwd()
        try:
            os.chdir(clone)
            rc = max(rc, ag.auto_revert(REPO, BASE))
        except OSError as exc:
            ag._summary(f"memecoin auto-revert: no clone at {clone} ({exc})")
            rc = 1
        finally:
            os.chdir(here)
    return rc


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--box", action="store_true", help="required: only the box merges")
    p.add_argument("--clone", help="a memecoin checkout for auto-revert")
    a = p.parse_args(argv)
    registry = os.environ.get(MEMECOIN_REGISTRY_ENV)
    if not a.box or not registry:
        print("memecoin_gate: runs only on the box with MEMECOIN_AUDIT_REGISTRY set; nothing done")
        return 0
    return sweep(registry, a.clone)


if __name__ == "__main__":
    raise SystemExit(main())
