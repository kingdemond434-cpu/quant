#!/usr/bin/env python3
"""PRE-FLIGHT: will the credit-blocked organs actually FIRE when credits arrive?

WHY THIS EXISTS. Eleven of the desk's defects reduce to "this organ has not run", and the stated
blocker is LLM credits. That framing is only honest if the organs are otherwise sound -- otherwise
the credits get spent discovering that a prompt file moved, the doctrine read empty, or the
conversion gate silently returned nothing, and the money buys a log file saying so.

It is not hypothetical. All six dig scripts computed `_MINE_PRIORITY` from `scripts/mine_gate.py`
under fourteen lines of comment explaining that the result is prepended to the organ's brief, and
then invoked `claude -p "$(cat <brief>)"` -- never referencing the variable. The conversion duty
had been dead in every organ. Firing them with credits in that state would have grown the
conversion backlog that `mine-conversion-unbacked` and `mine-law-unjudgeable` are complaining
about, at maximum effort, seven regions a day.

WHAT IT CHECKS, and every one of these has a failure mode that costs credits to discover:
  the runner exists and PARSES (`bash -n`)
  the brief exists and is substantial -- a truncated prompt still runs, and still bills
  the runner wires `dig_prompt`, not a bare `cat` -- the regression guard for the bug above
  the doctrine file is present and non-empty -- an empty `--append-system-prompt` runs undirected
  `mine_gate.py` executes and its output leads the assembled prompt
  the log directory is writable -- a dig that cannot write its log produces nothing auditable

EXIT CODE IS NON-ZERO WHEN ANY ORGAN IS NOT READY, unlike most report scripts here. This one is a
gate meant to run before spending, so "everything is fine" and "something is broken" must be
distinguishable without reading the output.

Read-only apart from its own report. No network, no keys, no `claude` invocation -- checking
readiness must not itself cost credits, which is why it never calls `brain_auth_check`.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
REPORT = ROOT / "data/organ_readiness.json"
DOCTRINE = ROOT / "ops/principal_doctrine.txt"
LOGDIR = ROOT / "data/cro_ai_logs"

#: organ label -> (runner script, prompt brief). The frontier regions share one runner.
ORGANS: dict[str, tuple[str, str]] = {
    "prospector": ("ops/run_prospector_dig.sh", "ops/prospector_dig_prompt.txt"),
    "litminer": ("ops/run_litminer_dig.sh", "ops/litminer_dig_prompt.txt"),
    "dataaxis": ("ops/run_dataaxis_dig.sh", "ops/dataaxis_dig_prompt.txt"),
    "blindrediscovery": ("ops/run_blindrediscovery_dig.sh",
                         "ops/blindrediscovery_dig_prompt.txt"),
    **{f"frontier-{r}": ("ops/run_frontier_miner.sh", f"ops/frontier_{r}_prompt.txt")
       for r in ("en", "cn", "ru", "kr", "jp", "ar", "br")},
}

#: A brief shorter than this is a stub. blindrediscovery's is the smallest real one at ~2.4KB.
MIN_BRIEF_BYTES = 1500


def _sh(script: str, *args: str, dry: bool = True) -> subprocess.CompletedProcess:
    env = dict(os.environ, _BRAIN_ROOT=str(ROOT))
    if dry:
        env["BRAIN_DRY_RUN"] = "1"
    return subprocess.run(["bash", script, *args], cwd=ROOT, env=env,
                          capture_output=True, text=True, timeout=180, check=False)


def check(label: str, runner: str, brief: str) -> dict:
    fails: list[str] = []
    rp, bp = ROOT / runner, ROOT / brief

    if not rp.exists():
        fails.append(f"runner {runner} is missing")
    elif subprocess.run(["bash", "-n", str(rp)], capture_output=True,
                        text=True, check=False).returncode != 0:
        fails.append(f"runner {runner} does not parse")

    if not bp.exists():
        fails.append(f"brief {brief} is missing")
    elif bp.stat().st_size < MIN_BRIEF_BYTES:
        fails.append(f"brief {brief} is {bp.stat().st_size}b (<{MIN_BRIEF_BYTES}b) -- a stub "
                     "prompt still runs and still bills")

    if rp.exists():
        src = rp.read_text("utf-8", errors="ignore")
        # THE REGRESSION GUARD. A bare `cat` here is the exact shape of the bug that left the
        # conversion duty dead in all six organs.
        if "dig_prompt" not in src:
            fails.append("runner does not call dig_prompt -- the conversion duty would be "
                         "computed and discarded, as it was until 2026-08-03")
        if "$(cat ops/" in src and "prompt" in src.split("$(cat ops/")[1][:60]:
            fails.append("runner still passes a bare `cat <brief>` as the prompt")

    return {"organ": label, "runner": runner, "brief": brief, "failures": fails}


def main() -> int:
    rows = [check(label, r, b) for label, (r, b) in ORGANS.items()]

    if not DOCTRINE.exists() or DOCTRINE.stat().st_size == 0:
        for r in rows:
            r["failures"].append(f"{DOCTRINE.name} missing/empty -- every organ would run with an "
                                 "empty --append-system-prompt, undirected")

    # The conversion gate is shared, so it is exercised once rather than eleven times.
    gate = subprocess.run([sys.executable, str(ROOT / "scripts/mine_gate.py")],
                          cwd=ROOT, capture_output=True, text=True, timeout=300, check=False)
    gate_ok = gate.returncode == 0 and gate.stdout.strip().startswith("[§33]")
    if not gate_ok:
        for r in rows:
            r["failures"].append("scripts/mine_gate.py did not produce a conversion duty "
                                 f"(rc={gate.returncode}) -- digs would mine without converting")

    try:
        LOGDIR.mkdir(parents=True, exist_ok=True)
        probe = LOGDIR / ".readiness_probe"
        probe.write_text("", "utf-8")
        probe.unlink()
        log_ok = True
    except OSError as e:
        log_ok = False
        for r in rows:
            r["failures"].append(f"{LOGDIR} not writable ({e}) -- a dig that cannot write its log "
                                 "produces nothing auditable")

    # END TO END, FOR FREE. Each runner is invoked in dry-run, which assembles the real prompt and
    # exits before brain_auth_check -- that check itself burns a `claude -p PING` per model.
    for r in rows:
        args = ([r["organ"].split("-", 1)[1]] if r["organ"].startswith("frontier-") else [])
        proc = _sh(r["runner"], *args)
        out = proc.stdout + proc.stderr
        r["dry_run"] = out.strip().splitlines()[-3:] if out.strip() else []
        if "READY" not in out:
            r["failures"].append(
                f"dry run did not report READY: {out.strip()[:160] or 'no output'}")

    ready = [r for r in rows if not r["failures"]]
    blocked = [r for r in rows if r["failures"]]
    out = {
        "ts": datetime.now(tz=UTC).isoformat(),
        "organs": len(rows), "ready": len(ready), "not_ready": len(blocked),
        "gate_ok": gate_ok, "doctrine_bytes": DOCTRINE.stat().st_size if DOCTRINE.exists() else 0,
        "log_dir_writable": log_ok,
        "results": rows,
        "note": ("READY means the organ assembles its full prompt, carries the doctrine and leads "
                 "with the §33 conversion duty -- verified WITHOUT calling claude, because a "
                 "pre-flight that costs credits is not a pre-flight. It does NOT mean auth works: "
                 "that needs a live credential and is checked by brain_auth_check at run time."),
    }
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text(json.dumps(out, indent=1), "utf-8")

    print(f"organ-readiness: {len(ready)}/{len(rows)} READY | gate={'ok' if gate_ok else 'BROKEN'}"
          f" | doctrine={out['doctrine_bytes']}b | logs={'w' if log_ok else 'RO'}")
    for r in blocked:
        print(f"  NOT READY {r['organ']}")
        for f in r["failures"]:
            print(f"      - {f}")
    if not blocked:
        print("  every credit-blocked organ assembles cleanly; auth is the only untested step "
              "and it needs a live credential by definition")
    return 1 if blocked else 0


if __name__ == "__main__":
    raise SystemExit(main())
