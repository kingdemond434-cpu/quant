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
#: Promotion-critical files, as paths RELATIVE TO `desks/mt5`.
#:
#: THIS LIST WATCHED ONLY `research/`, AND THE CLOBBER IT EXISTS TO CATCH LANDED IN `mt5desk/`.
#:
#: On 2026-08-20 a Windows working copy was committed over the repo and reverted nine closed
#: defects -- gold priced at 3% of its spread in `engine.py`, the account filter in
#: `promoter.py`, the risk-budget import in `allocation.py`, the date join in `qquant_gates.py`,
#: the promotion chain's scheduler in `hourly_cycle.py`, the lookahead fix in `run_hunt12.py`.
#: Exactly ONE of those files was on this list. The verifier would have hashed its eight files,
#: found them identical, and written `ok=true` for the whole event.
#:
#: The engine and the gateway are THE money path: everything else on this desk produces a number
#: that one of those two acts on. A verifier that cannot see them is not verifying the desk.
#:
#: The rule for this list is not "files we edit often" -- that is what produced the gap. It is
#: every file whose contents can change what reaches capital, and it therefore fails safe by
#: being too long rather than too short.
KEY_FILES = [
    # --- the money path itself
    "mt5desk/engine.py",           # cost model + fill simulation; every R on this desk
    "mt5desk/gateway.py",          # the only code that sends an order
    "mt5desk/risk_units.py",       # EUR per price unit; sizes every stop
    "mt5desk/config.py",           # resolves every path, including the live terminal
    "mt5desk/families.py",         # signal definitions
    "mt5desk/gateway_config_fallback.py",   # the risk budget's single definition
    # --- the promotion chain
    "research/universal_gate.py",
    "research/signal_gate.py",
    "research/promoter.py",        # decides what is armed and what is retired
    "research/shadow_forward.py",  # the only source of forward evidence
    "research/hourly_cycle.py",    # runs the chain; deleted once already
    "research/qquant_gates.py",    # multiplicity: PBO/CSCV/SPA
    "research/run_hunt12.py",      # day_states -- lookahead fix reverted three times
    "research/allocation.py",
    "research/portfolio_projection.py",
    "research/research_loop.py",
    "research/research_supervisor.py",
    "research/run_hunt17.py",
    "research/macro_desk.py",
]
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


def git(*args: str, timeout: int = 60, binary: bool = False) -> tuple[int, object]:
    try:
        r = subprocess.run(["git", *args], cwd=str(git_tree()),
                           capture_output=True, timeout=timeout)
        out: object = r.stdout if binary else (r.stdout or b"") + (r.stderr or b"")
        return r.returncode, out
    except Exception as e:
        return -1, f"{e!r}"


def sha256(data: bytes) -> str:
    return hashlib.sha256(data.replace(b"\r\n", b"\n")).hexdigest()


def dec(data: object) -> str:
    return data.decode("utf-8", errors="replace") if isinstance(data, bytes) \
        else str(data)


def main() -> int:
    REPORTS.mkdir(exist_ok=True)
    tree = git_tree()
    out: dict = {"checked_at": datetime.now(timezone.utc).isoformat(),
                 "box": BOX, "git_tree": str(tree), "branch": BRANCH}
    rc, msg = git("rev-parse", "--short", "HEAD")
    out["local_head"] = dec(msg).strip() if rc == 0 else "?"
    rc, msg = git("fetch", "origin", BRANCH)
    out["fetch_ok"] = rc == 0
    if rc == 0:
        rc, msg = git("rev-parse", "--short", f"origin/{BRANCH}")
        out["remote_tip"] = dec(msg).strip() if rc == 0 else "?"
    else:
        out["remote_tip"] = "fetch-failed"

    pulls = []
    if rc == 0 and out.get("remote_tip") != out.get("local_head"):
        rc2, msg2 = git("merge", "--no-edit", "-X", "theirs",
                        f"origin/{BRANCH}", timeout=180)
        pulls.append({"action": "merge -X theirs", "ok": rc2 == 0,
                      "detail": (dec(msg2).strip().splitlines() or [""])[-1]})
        if rc2 == 0:
            # RE-READ THE HEAD, NEVER ASSUME IT. This assigned `remote_tip` to `local_head`,
            # which is only true when the merge fast-forwarded. A real merge creates a NEW
            # commit that is neither side, so the log line then printed head==remote and read
            # as "in sync" while the box sat on an unpushed merge commit ahead of the remote.
            rc3, msg3 = git("rev-parse", "--short", "HEAD")
            if rc3 == 0:
                out["local_head"] = dec(msg3).strip()
    out["pull"] = pulls

    # WHICH WAY THE TREES DIVERGED, because "not identical" is not an instruction. Ahead means
    # this box holds work the remote has never seen and must PUSH; behind means it must PULL.
    # The clobber came from a box that was both, and reported neither.
    rc4, msg4 = git("rev-list", "--left-right", "--count",
                    f"HEAD...origin/{BRANCH}")
    if rc4 == 0:
        parts = dec(msg4).split()
        if len(parts) >= 2 and parts[0].isdigit() and parts[1].isdigit():
            ahead, behind = int(parts[0]), int(parts[1])
            out["ahead"], out["behind"] = ahead, behind
            out["divergence"] = ("in-sync" if not ahead and not behind else
                                 "ahead (unpushed work on this box)" if ahead and not behind else
                                 "behind (remote work not pulled)" if behind and not ahead else
                                 "DIVERGED both ways -- resolve before any promotion")

    files = {}
    running = {}
    desk = tree / "desks" / "mt5"
    all_ok = bool(out.get("fetch_ok"))
    for f in KEY_FILES:
        fp = desk / f
        local_h = sha256(fp.read_bytes()) if fp.exists() else "missing"
        rc, blob = git("cat-file", "blob", f"origin/{BRANCH}:desks/mt5/{f}", binary=True)
        remote_h = sha256(bytes(blob)) if rc == 0 else "missing"
        match = local_h == remote_h
        # A file missing on BOTH sides hashes "missing" == "missing" and would score as a match.
        # That is absence read as agreement (WS-005): the two sides do agree, but about nothing,
        # and a promotion-critical file that exists nowhere is the loudest possible failure.
        present = local_h != "missing" and remote_h != "missing"
        ok = match and present
        files[f] = {"match": match, "present": present, "ok": ok,
                    "local": local_h[:12], "remote": remote_h[:12]}
        all_ok = all_ok and ok
        rfp = BASE / f
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
          f"head={out.get('local_head')} remote={out.get('remote_tip')} "
          f"[{out.get('divergence', 'divergence unknown')}]", flush=True)
    if not all_ok:
        # Name the files. `ok=false` alone sends whoever is on shift to open a JSON report, and
        # the whole point of running this hourly is that it is read in passing.
        for name, st in files.items():
            if not st["ok"]:
                why = "MISSING" if not st["present"] else "DIFFERS from remote"
                print(f"  {why}: desks/mt5/{name} "
                      f"(local {st['local']} / remote {st['remote']})", flush=True)
    return 0 if all_ok else 1


if __name__ == "__main__":
    sys.exit(main())