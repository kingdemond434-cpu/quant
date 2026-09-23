#!/usr/bin/env python3
"""THE CLOCK-LIVENESS FENCE -- no forward clock is FROZEN, and the frozen ratchet only falls.

A forward clock is the desk's only honest accelerator: it is how a certificate earns the right
to trade. A clock that quietly stops accruing is evidence the desk THINKS it has and does not,
and at day 14 the verdict rule fires on ancient trades. So this fence fails while:

  * any clock has been FROZEN longer than its OWN window (its instrument's and timeframe's
    venue-open bars, not a wall clock -- a weekend gap is not a freeze);
  * the frozen count has RISEN above the ratchet floor (the lowest count ever measured here);
  * the report itself is stale (older than two hourly cadences) or absent on a host that runs
    the leg.

IT IS A STATE FENCE. On a clean checkout, a build box or CI there is no CLOCK_LIVENESS.json and
no forward lane to read, so the verdict is UNMEASURED -- a real answer about the HOST (L1.28a),
never a pass and never a failure. `--require-state` turns that into a failure, which is what the
trading box passes.

    python scripts/check_clock_liveness.py                 # portable
    python scripts/check_clock_liveness.py --require-state # on the box: absence is a defect
    python scripts/check_clock_liveness.py --json
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
REPORT = ROOT / "desks" / "mt5" / "reports" / "CLOCK_LIVENESS.json"
RATCHET = ROOT / "desks" / "mt5" / "data" / "clock_liveness_ratchet.json"

#: The leg is hourly; two cadences is the desk's standing rule for "stopped rather than slow".
MAX_REPORT_AGE_S = 2 * 3600.0

OK, FAIL, UNMEASURED = "OK", "FAIL", "UNMEASURED"


def _read(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8", errors="replace"))
    except (OSError, ValueError):
        return None


def _age_s(stamp: Any, now: datetime) -> float | None:
    if not stamp:
        return None
    text = str(stamp).strip().replace("Z", "+00:00")
    if " " in text and "T" not in text:
        text = text.replace(" ", "T", 1)
    try:
        ts = datetime.fromisoformat(text)
    except ValueError:
        return None
    if not ts.tzinfo:
        ts = ts.replace(tzinfo=UTC)
    return (now - ts).total_seconds()


def judge(report: Any, ratchet: Any, *, require_state: bool,
          now: datetime | None = None) -> dict[str, Any]:
    now = now or datetime.now(UTC)
    findings: list[str] = []
    if not isinstance(report, dict):
        verdict = FAIL if require_state else UNMEASURED
        return {"verdict": verdict, "findings": [
            "desks/mt5/reports/CLOCK_LIVENESS.json is absent or unreadable"
            + (": on a host that runs the `clock_liveness` leg that is a DEFECT"
               if require_state
               else "; off the trading box that is UNMEASURED, which is a real answer")],
            "frozen": None, "ratchet": None, "report_age_s": None}

    age = _age_s(report.get("at"), now)
    if age is None:
        findings.append("the report carries no readable `at` stamp, so its freshness is "
                        "UNMEASURED and it cannot be trusted as current")
    elif age > MAX_REPORT_AGE_S:
        findings.append(f"the report is {age / 3600.0:.1f} h old against a "
                        f"{MAX_REPORT_AGE_S / 3600.0:.0f} h window: the `clock_liveness` leg has "
                        f"stopped, so every clock verdict in it is stale")

    raw_frozen = report.get("frozen")
    frozen_rows: list[Any] = raw_frozen if isinstance(raw_frozen, list) else []
    frozen_n = report.get("frozen_after")
    if not isinstance(frozen_n, int):
        frozen_n = len(frozen_rows)

    # 1. ANY clock frozen past its own window. The organ has already counted the venue's bars;
    #    this fence does not re-derive them, it refuses to let the count stand at zero cost.
    if frozen_rows:
        worst = sorted(frozen_rows, key=lambda r: -(r.get("lag_bars") or 0))[:5]
        for r in worst:
            findings.append(
                f"FROZEN {r.get('lane')}/{str(r.get('key'))[:60]} ({r.get('timeframe')}): "
                f"{r.get('lag_bars')} venue bar(s) with no advance past its own "
                f"{r.get('freeze_bars')}-bar window -- cause {r.get('cause')}")
        if len(frozen_rows) > 5:
            findings.append(f"... and {len(frozen_rows) - 5} more frozen clock(s); the full list "
                            f"is in CLOCK_LIVENESS.json `frozen`")

    # 2. THE RATCHET MAY ONLY FALL. A defect ceiling that can be raised is not a ceiling.
    floor = (ratchet or {}).get("lowest_frozen") if isinstance(ratchet, dict) else None
    if isinstance(floor, int) and isinstance(frozen_n, int) and frozen_n > floor:
        findings.append(f"the frozen count ROSE to {frozen_n} against a ratchet floor of {floor}: "
                        f"the enforced ceiling is the lowest count ever measured on this box and "
                        f"it may fall and never rise (L1.50)")

    # 3. A repair that did not prove itself is not a repair (LAWS 7: A REPORT IS NOT A REMEDY).
    for rep in report.get("repairs") or []:
        if str(rep.get("result")) in ("FAILED",):
            findings.append(f"the repair `{rep.get('actuator')}` FAILED over "
                            f"{rep.get('clocks')} clock(s): {rep.get('why')}")

    return {"verdict": FAIL if findings else OK, "findings": findings,
            "frozen": frozen_n, "ratchet": floor, "report_age_s": age,
            "clocks_total": report.get("clocks_total"), "counts": report.get("counts"),
            "frozen_before": report.get("frozen_before"), "hostname": report.get("hostname")}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=(__doc__ or "").split("\n")[0])
    ap.add_argument("--require-state", action="store_true",
                    help="an absent report is a DEFECT (the trading box passes this)")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--report", default=None)
    ap.add_argument("--ratchet", default=None)
    a = ap.parse_args(argv)
    doc = judge(_read(Path(a.report) if a.report else REPORT),
                _read(Path(a.ratchet) if a.ratchet else RATCHET),
                require_state=a.require_state)
    if a.json:
        print(json.dumps(doc, indent=1, default=str))
    else:
        print(f"clock liveness: {doc['verdict']} -- {doc.get('clocks_total')} clock(s), "
              f"frozen {doc.get('frozen_before')} -> {doc.get('frozen')}, "
              f"ratchet floor {doc.get('ratchet')}")
        for f in doc["findings"]:
            print(f"  - {f}")
    return 1 if doc["verdict"] == FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
