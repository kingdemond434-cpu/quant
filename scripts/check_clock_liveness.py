#!/usr/bin/env python3
"""THE CLOCK-LIVENESS FENCE -- no forward clock is FROZEN, and the frozen ratchet only falls.

A forward clock is the desk's only honest accelerator: it is how a certificate earns the right
to trade. A clock that quietly stops accruing is evidence the desk THINKS it has and does not,
and at day 14 the verdict rule fires on ancient trades. So this fence fails while:

  * any clock has been FROZEN longer than its OWN window (its instrument's and timeframe's
    venue-open bars, not a wall clock -- a weekend gap is not a freeze);
  * the frozen count has RISEN above the ratchet floor (the lowest count ever measured here);
  * the report itself is stale (older than two hourly cadences) or absent on a host that runs
    the leg;
  * CLOCK IMPLIES CERTIFICATE (principal 2026-09-23) is breached and has been for longer than
    ONE JUDGING CYCLE -- a clock running with no certificate is a breach, and the remedy is to
    JUDGE its cell, not to switch the clock off, so the fence measures how long the breach has
    waited at the front of the judge's queue rather than how many breaches exist;
  * the breach count has RISEN above its own ratchet floor.

WHAT IT DELIBERATELY DOES NOT DO. It never fails merely because breached clocks exist: on a desk
that has just been told every clock must be certified, the breach count starts at almost the
whole book, and a fence that went red on the count would pressure a future session into
retiring clocks to get green -- destroying the evidence the law exists to gather. It fails on
AGE, which only judging can cure, and on the ratchet, which only judging can lower.

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
    ratchet_floor = (ratchet or {}).get("lowest_frozen") if isinstance(ratchet, dict) else None
    if isinstance(ratchet_floor, int) and isinstance(frozen_n, int) and frozen_n > ratchet_floor:
        findings.append(f"the frozen count ROSE to {frozen_n} against a ratchet floor of "
                        f"{ratchet_floor}: "
                        f"the enforced ceiling is the lowest count ever measured on this box and "
                        f"it may fall and never rise (L1.50)")

    # 3. CLOCK IMPLIES CERTIFICATE. Age, never count -- see the docstring.
    cert = report.get("certificate") if isinstance(report.get("certificate"), dict) else {}
    if cert:
        cycle = float(cert.get("judging_cycle_s") or 3600.0)
        overdue = cert.get("overdue_beyond_one_judging_cycle")
        oldest = cert.get("oldest_breach_age_s")
        if isinstance(overdue, int) and overdue > 0:
            eldest = (f"; oldest breach {float(oldest) / 3600.0:.1f} h"
                      if isinstance(oldest, (int, float)) else "")
            findings.append(
                f"{overdue} clock(s) have been running UNCERTIFIED for longer than one judging "
                f"cycle ({cycle / 3600.0:.1f} h){eldest}")
            findings.append(
                "the remedy is the judge, not the clock: their cells are queued FIRST as "
                "`recertify` tasks and the throughput organ must be reaching them")
        floor = (cert.get("ratchet") or {}).get("lowest_breached")
        n_breach = cert.get("breached")
        if isinstance(floor, int) and isinstance(n_breach, int) and n_breach > floor:
            findings.append(f"the breach count ROSE to {n_breach} against a ratchet floor of "
                            f"{floor}: it may fall and never rise, and it falls by JUDGING "
                            f"cells, never by switching clocks off")
        queue = cert.get("queue") or {}
        if isinstance(queue, dict) and queue.get("submitted") == 0                 and queue.get("already_queued") == 0 and (n_breach or 0) > 0:
            findings.append(f"{n_breach} breached clock(s) and NOTHING was queued for judgement: "
                            f"{queue.get('why')} -- a breach that reaches no queue is a report, "
                            f"not a remedy")

    # 4. A repair that did not prove itself is not a repair (LAWS 7: A REPORT IS NOT A REMEDY).
    for rep in report.get("repairs") or []:
        if str(rep.get("result")) in ("FAILED",):
            findings.append(f"the repair `{rep.get('actuator')}` FAILED over "
                            f"{rep.get('clocks')} clock(s): {rep.get('why')}")

    return {"verdict": FAIL if findings else OK, "findings": findings,
            "certificate": {k: cert.get(k) for k in
                            ("breached", "awaiting", "backed", "retired",
                             "overdue_beyond_one_judging_cycle")} if cert else None,
            "frozen": frozen_n, "ratchet": ratchet_floor, "report_age_s": age,
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
        c = doc.get("certificate") or {}
        print(f"clock liveness: {doc['verdict']} -- {doc.get('clocks_total')} clock(s), "
              f"frozen {doc.get('frozen_before')} -> {doc.get('frozen')}, "
              f"ratchet floor {doc.get('ratchet')}; certificate: "
              f"breached {c.get('breached')} (awaiting {c.get('awaiting')}), "
              f"backed {c.get('backed')}, retired {c.get('retired')}")
        for f in doc["findings"]:
            print(f"  - {f}")
    return 1 if doc["verdict"] == FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
