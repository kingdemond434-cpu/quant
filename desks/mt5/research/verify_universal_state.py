"""verify_universal_state.py - daily/hourly universal-state verification.

Every brain runs this (wired into the supervisor loop on every box). It:
  1. fetches the shared GitHub remote
  2. pulls the main desk branch (merge -X theirs; failures logged, never forced)
  3. hashes the promotion-critical research files in the local desk tree and
     compares them with the remote blobs (universal = identical everywhere)
  4. records HOLD flags and local authority mode
Writes reports/UNIVERSAL_STATE_VERIFY.json + appends to reports/universal_state_verify.log.
Fail-closed: ok=false on ANY discrepancy. Every brain MUST read the verify file
at session start (bound in CLAUDE.md / AGENTS.md / docs/UNIVERSAL_PROMOTION_PROTOCOL.md).
"""
from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
REPORTS = BASE / "reports"
BRANCH = os.environ.get("QUANT_BRANCH", "claude/llm-auto-upgrade-verify-gcjac3")
KEY_FILES = ["universal_gate.py", "signal_gate.py", "research_loop.py",
             "allocation.py", "portfolio_projection.py", "run_hunt17.py",
             "macro_desk.py", "research_supervisor.py"]
BOX = "vps" if os.name != "nt" else "local"


def git_tree() -> Path:
    env = os.environ.get("QUANT_GIT_TREE")
    if env and Path(env).exists():
        return Path(env)
    p = BASE
    for _ in range(5):
        if (p / ".git").exists():
            return p
        p = p.parent
    sibling = BASE.parent / "quant-platform"
    return sibling if sibling.exists() else BASE


def git(*args: str, timeout: int = 60) -> tuple[int, str]:
    try:
        r = subprocess.run(["git", *args], cwd=str(git_tree()),
                           capture_output=True, text=True, timeout=timeout)
        return r.returncode, (r.stdout or "") + (r.stderr or "")
    except Exception as e:
        return -1, f"{e!r}"


def sha256(data: bytes) -> str:
    return hashlib.sha256(data.replace(b"\r\n", b"\n")).hexdigest()


def main() -> int:
    REPORTS.mkdir(exist_ok=True)
    tree = git_tree()
    out: dict = {"checked_at": datetime.now(timezone.utc).isoformat(),
                 "box": BOX, "git_tree": str(tree), "branch": BRANCH}
    rc, msg = git("rev-parse", "--short", "HEAD")
    out["local_head"] = msg.strip() if rc == 0 else "?"
    rc, msg = git("fetch", "origin", BRANCH)
    out["fetch_ok"] = rc == 0
    if rc == 0:
        rc, msg = git("rev-parse", "--short", f"origin/{BRANCH}")
        out["remote_tip"] = msg.strip() if rc == 0 else "?"
    else:
        out["remote_tip"] = "fetch-failed"

    pulls = []
    if rc == 0 and out.get("remote_tip") != out.get("local_head"):
        rc2, msg2 = git("merge", "--no-edit", "-X", "theirs",
                        f"origin/{BRANCH}", timeout=180)
        pulls.append({"action": "merge -X theirs", "ok": rc2 == 0,
                      "detail": (msg2.strip().splitlines() or [""])[-1]})
        if rc2 == 0:
            out["local_head"] = out.get("remote_tip")
    out["pull"] = pulls

    files = {}
    running = {}
    desk = tree / "desks" / "mt5"
    all_ok = bool(out.get("fetch_ok"))
    for f in KEY_FILES:
        fp = desk / "research" / f
        local_h = sha256(fp.read_bytes()) if fp.exists() else "missing"
        rc, blob = git("cat-file", "blob", f"origin/{BRANCH}:desks/mt5/research/{f}")
        remote_h = sha256(blob.encode()) if rc == 0 else "missing"
        match = local_h == remote_h
        files[f] = {"match": match, "local": local_h[:12], "remote": remote_h[:12]}
        all_ok = all_ok and match
        rfp = BASE / "research" / f
        if rfp.resolve() != fp.resolve() and rfp.exists():
            rh = sha256(rfp.read_bytes())
            running[f] = {"synced_to_tree": rh == local_h,
                          "matches_remote": rh == remote_h}

    holds = sorted(p.name for p in (BASE / "data").glob("HOLD_*"))
    vps_authority = (BASE / "data" / "VPS_AUTHORITY").exists()
    out["holds"] = holds
    out["vps_authority"] = vps_authority
    out["files"] = files
    out["running"] = running
    out["ok"] = all_ok
    REPORTS.joinpath("UNIVERSAL_STATE_VERIFY.json").write_text(
        json.dumps(out, indent=2), encoding="utf-8")
    with open(REPORTS / "universal_state_verify.log", "a", encoding="utf-8") as lf:
        lf.write(f"{out['checked_at']} {BOX} ok={all_ok} head={out.get('local_head')} "
                 f"remote={out.get('remote_tip')} holds={holds}\n")
    print(f"UNIVERSAL STATE VERIFY: ok={all_ok} "
          f"head={out.get('local_head')} remote={out.get('remote_tip')}", flush=True)
    return 0 if all_ok else 1


if __name__ == "__main__":
    sys.exit(main())