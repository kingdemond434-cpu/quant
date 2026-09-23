#!/usr/bin/env python3
"""THE WRITE-OR-EXPLAIN FENCE -- no organ is allowed to be silent about producing nothing.

    python scripts/check_write_or_explain.py [--json] [--window-h 6] [--require-state]
    python scripts/check_write_or_explain.py --wiring-only        # portable: is it wired?
    python scripts/check_write_or_explain.py --probe coverage_tensor=research/coverage_tensor.py

THE CONTRACT IS IN `libs/ops/write_or_explain.py`; this is its gate and its publication. It reads
the append-only contract ledger every leg boundary writes, takes the LATEST row per leg, and
sentences the desk:

    BREACH       one or more legs kept exiting without writing and without saying why
                 (SILENT_NO_OP), or failed outright (LEG_FAILED / LEG_TIMEOUT).
    UNOBSERVED   a leg that DECLARES an artifact produced no contract row in the window at all.
                 That is not "it had nothing to do" -- it is the leg not firing, which is how
                 `ground_depth` and `independence_intake` sat at ZERO compute-ledger rows on the
                 trading box while both ran perfectly by hand.
    UNMEASURED   no ledger on this machine. FAILS under --require-state, because a fence that
                 passes on an absent input is the exact false GREEN L1.28a forbids.
    CONTRACT_KEPT every observed leg either wrote its artifact or named its reason.

IT SHIPS RED AND THE RED IS THE WORK (L1.43's inverse). The first run on the trading box was
never going to be green: `coverage_tensor` has exited 1 on 199 of its last 204 passes with
`COVERAGE_TENSOR.json` never once written. Lowering the bar to today's state would pin exactly
the backlog this fence exists to surface.

WHY THE SAME SCRIPT IS IN BOTH BATTERIES. `--wiring-only` is PORTABLE: it reads the cycle source
and asserts the contract is still called at the leg boundary, so a future edit that removes the
wiring reddens CI on a fresh clone with no desk state at all. The state battery runs it bare,
against the live ledger. A contract nothing calls is the same defect one layer up.

`--probe leg=script.py` runs ONE organ's real command through the identical `judge()` the cycle
uses and prints the verdict -- for a session that wants to know whether an organ keeps the
contract without waiting an hour for the cycle to say so.

Exit: 0 on CONTRACT_KEPT; 2 on BREACH/UNOBSERVED or a broken wiring; 2 on UNMEASURED only with
--require-state.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from libs.ops import write_or_explain as woe  # noqa: E402
from libs.ops.fence_exit import FAIL, fence_exit  # noqa: E402
from libs.ops.write_or_explain import WINDOW_H, build_report, publish  # noqa: E402

#: The one passing status (R0237: enumerate passes, never failures).
_PASSING = frozenset({"CONTRACT_KEPT"})
#: The cycle file the wiring check reads.
CYCLE = _ROOT / "desks" / "mt5" / "research" / "hourly_cycle.py"


# ------------------------------------------------------------------------ the portable half
#: The call sites the cycle MUST still contain for the contract to cover every leg.
_WIRING_NEEDLES: tuple[tuple[str, str], ...] = (
    ("write_or_explain", "the cycle must import the contract"),
    ("_woe_before", "the cycle must stat the declared artifact BEFORE the leg"),
    ("_woe_after", "the cycle must stat and judge it AFTER the leg"),
)


def wiring_report() -> dict[str, Any]:
    """Portable: is the contract still called at the leg boundary? Needs no desk state."""
    rep: dict[str, Any] = {"generated": datetime.now(UTC).isoformat(timespec="seconds"),
                           "cycle": str(CYCLE), "missing": [], "scanned": 0,
                           "status": "UNMEASURED", "detail": ""}
    try:
        text = CYCLE.read_text(encoding="utf-8", errors="replace")
    except OSError as exc:
        rep["detail"] = f"cannot read {CYCLE}: {exc}"
        return rep
    for needle, why in _WIRING_NEEDLES:
        if needle not in text:
            rep["missing"].append({"needle": needle, "why": why})
    # Both boundaries must sit inside `_costed`, which is the ONE place every leg passes through.
    body = text.split("def _costed(", 1)[-1].split("\ndef ", 1)[0] if "def _costed(" in text else ""
    if body and ("_woe_before" not in body or "_woe_after" not in body):
        rep["missing"].append({"needle": "_costed", "why": "the contract must be called inside "
                                                          "_costed, the one boundary every leg "
                                                          "passes through"})
    rep["scanned"] = len(_WIRING_NEEDLES) + 1
    rep["status"] = "WIRED" if not rep["missing"] else "UNWIRED"
    rep["detail"] = ("the write-or-explain contract is called at the cycle's leg boundary"
                     if not rep["missing"] else
                     f"{len(rep['missing'])} required call site(s) absent from {CYCLE.name}")
    return rep


# ----------------------------------------------------------------------------- the probe
def probe(spec: str) -> dict[str, Any]:
    """Run ONE organ's real command through the identical contract the cycle applies.

    `spec` is `leg=path/to/script.py [args...]`, resolved against the desk root then the repo
    root exactly as `hourly_cycle._producer_impl` resolves it, so the verdict is the verdict the
    cycle would reach. Nothing here knows which organs are suspected of anything.
    """
    leg, _, cmd = spec.partition("=")
    leg = leg.strip()
    parts = cmd.split()
    if not leg or not parts:
        return {"leg": leg, "verdict": woe.LEG_FAILED,
                "detail": f"probe spec {spec!r} is not leg=script.py [args]"}
    base = _ROOT / "desks" / "mt5"
    for root in (base, _ROOT):
        target = root / parts[0]
        if target.exists():
            break
    else:
        return woe.observe(leg, woe.before_leg(leg),
                           {"exit_code": None, "status": "MISSING",
                            "why": f"{parts[0]} exists under neither {base} nor {_ROOT}"},
                           record_row=False)
    before = woe.before_leg(leg)
    t0 = time.monotonic()
    try:
        r = subprocess.run([sys.executable, "-u", "-W", "ignore", str(target), *parts[1:]],
                           capture_output=True, text=True, cwd=str(root), timeout=900, check=False)
        result: dict[str, Any] = {"exit_code": r.returncode,
                                  "tail": (r.stdout or "")[-1200:],
                                  "stderr_tail": (r.stderr or "")[-1200:]}
    except subprocess.TimeoutExpired:
        result = {"exit_code": None, "timeout_s": 900}
    except OSError as exc:
        result = {"error": f"{type(exc).__name__}: {exc}"}
    return woe.observe(leg, before, result, wall_s=time.monotonic() - t0, record_row=False)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=(__doc__ or "").split("\n")[0])
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--window-h", type=float, default=WINDOW_H)
    ap.add_argument("--require-state", action="store_true",
                    help="an absent contract ledger is a failure (box gate)")
    ap.add_argument("--wiring-only", action="store_true",
                    help="portable: assert the contract is called at the cycle's leg boundary")
    ap.add_argument("--probe", action="append", default=[], metavar="LEG=SCRIPT",
                    help="run one organ's real command through the contract and report")
    ap.add_argument("--report-only", action="store_true",
                    help="print and exit 0; the law gate never passes this")
    a = ap.parse_args(argv)

    if a.wiring_only:
        rep = wiring_report()
        print(json.dumps(rep, indent=1) if a.json
              else f"write-or-explain wiring: {rep['status']} -- {rep['detail']}")
        for m in rep["missing"]:
            print(f"  UNWIRED   {m['needle']}: {m['why']}")
        return 0 if a.report_only else fence_exit(rep["status"], frozenset({"WIRED"}), fail=FAIL,
                                                  scanned=rep["scanned"], of="required call sites",
                                                  fence="check_write_or_explain.py --wiring-only")
    if a.probe:
        recs = [probe(spec) for spec in a.probe]
        if a.json:
            print(json.dumps(recs, indent=1, default=str))
        else:
            for rec in recs:
                print(f"  {rec['verdict']:<15} {rec.get('detail', '')}")
                for line in str(rec.get("stderr_tail") or "").strip().splitlines()[-6:]:
                    print(f"      stderr| {line[:160]}")
        bad = sum(int(woe.is_defect(r.get("verdict"))) for r in recs)
        return 0 if a.report_only else (FAIL if bad else 0)

    rep = build_report(window_h=float(a.window_h))
    try:
        out = publish(rep)
    except OSError as exc:
        out = None
        print(f"  (artifact not published: {type(exc).__name__}: {exc})")
    if a.json:
        print(json.dumps(rep, indent=1, default=str))
    else:
        print(f"write-or-explain: {rep['status']} -- {rep['detail']}")
        for row in rep["silent_no_ops"][:20]:
            print(f"  SILENT_NO_OP   {row['detail']}")
        for row in rep["failed"][:20]:
            print(f"  {row['verdict']:<14} {row['detail']}")
        for row in rep["never_observed"][:20]:
            print(f"  NEVER_OBSERVED {row['detail']}")
        if len(rep["never_observed"]) > 20:
            print(f"  ... and {len(rep['never_observed']) - 20} more never observed")
        if out:
            print(f"-> {out}")
    if a.report_only:
        return 0
    if rep["status"] == "UNMEASURED":
        return FAIL if a.require_state else 0
    return fence_exit(rep["status"], _PASSING, fail=FAIL, scanned=rep["scanned"],
                      of="legs observed at a boundary", fence="check_write_or_explain.py")


if __name__ == "__main__":
    raise SystemExit(main())
