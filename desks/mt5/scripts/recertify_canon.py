"""RE-JUDGE EVERY STANDING CERTIFICATE UNDER THE CURRENT COST MODEL, and report.

WHY THIS EXISTS (2026-08-27). `external_gauntlet.costs_for` carried three defects, all in the
survivor-manufacturing direction: gold's spread written per-OUNCE into a per-LOT field (2.43x
undercharged), no account-currency conversion on commission (USDJPY 184x, CADJPY 8.2x, EURJPY
6.2x on this EUR account), and a contractual commission scaled by market stress. They were fixed
in bc4b03ed -- but every certificate ALREADY in canon was graded before the fix, against costs
that flattered it. A ten-gate pass is a claim about net-of-cost economics; if the costs were
wrong, the claim was never tested, and forward clocks are now accruing evidence for strategies
whose economics were mis-stated.

WHAT THIS DOES AND DELIBERATELY DOES NOT DO. It rebuilds each certified cell from its own
`shadow_spec` -- the exact parameterization that passed -- charges it the CURRENT cost model, and
re-runs the identical ten gates. It writes a report. It does NOT delete, revoke, or shrink canon:
the never-shrink seal stands, past verdicts are not revoked by a later run, and which
certificates to retire is the principal's call on measured evidence rather than a script's.
Re-grading with a CORRECTED measurement is not a harsher bar -- the thresholds are untouched.

A certificate that no longer passes is reported as COST_REGRADE_FAIL with the gates that now
fail and the old-vs-new cost per lot, so the size of the error is visible per symbol.
"""
from __future__ import annotations

import json
import sys
from datetime import UTC, datetime
from pathlib import Path

BASE = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(BASE))
sys.path.insert(0, str(BASE / "desks" / "mt5"))
sys.path.insert(0, str(BASE / "desks" / "mt5" / "scripts"))

DESK = BASE / "desks" / "mt5"
OUT = DESK / "reports" / "recertification_audit.json"


def main() -> int:
    import external_gauntlet as eg

    uni = json.loads((DESK / "reports" / "UNIVERSAL_SURVIVORS.json").read_text("utf-8"))
    meta = json.loads((DESK / "data" / "universe" / "universe.json").read_text("utf-8"))
    survivors = uni.get("survivors") or {}

    # THE PARAMETERIZATION THAT ACTUALLY RUNS, not the one the certificate displays.
    # `shadow_spec` often carries no params at all, and rebuilding on family DEFAULTS judges a
    # strategy nobody runs: measured 2026-08-27, XAUUSD.session_range_breakout rebuilt from an
    # empty spec produced 4,344 signals and ZERO trades, so all 20 breakout certificates read as
    # "under 60 days" and the audit measured nothing. `authorized_runs` is the same door the
    # forward engine enrols through -- window hours merged with the certified params -- so it is
    # the only honest basis for re-grading. A certificate with no runnable parameterization is
    # reported as such rather than judged on a guess.
    sys.path.insert(0, str(DESK / "research"))
    runs_by_cert: dict[str, dict] = {}
    try:
        from shadow_admission import authorized_runs
        # H1 lane only: scalp certificates are re-judged daily by scalp_gauntlet itself.
        for r in authorized_runs(DESK, lanes=("h1",)):
            runs_by_cert[str(r.get("certificate"))] = r
    except Exception as exc:
        print(f"recertify: authorized_runs unavailable ({type(exc).__name__}: {exc})")

    cells, keys, skipped = [], [], []
    for name, row in survivors.items():
        spec = row.get("shadow_spec")
        if not isinstance(spec, dict) or not spec.get("symbol"):
            skipped.append({"certificate": name, "why": "no shadow_spec to rebuild from"})
            continue
        run = runs_by_cert.get(name)
        if run is None:
            skipped.append({"certificate": name,
                            "why": ("no runnable parameterization (authorized_runs excludes it), "
                                    "so there is nothing exact to re-grade -- this certificate "
                                    "cannot be run forward either")})
            continue
        cell = eg.build_cell(str(run["symbol"]), str(run.get("family") or ""),
                             dict(run.get("params") or {}), meta)
        if cell is None:
            skipped.append({"certificate": name, "why": "cell could not be rebuilt"})
            continue
        cells.append(cell)
        keys.append(name)

    if not cells:
        print("recertify: no certificate could be rebuilt -- nothing measured, nothing claimed")
        return 1

    res = eg.run_gauntlet(cells, "recertification_audit", meta)
    verdicts = {v.get("cell"): v for v in (res.get("verdicts") or [])}

    rows = []
    for name, cell in zip(keys, cells, strict=False):
        cid = eg.cell_id({"sym": cell["sym"], "family": cell["family"],
                          "params": cell.get("params") or {}})
        v = verdicts.get(cid)
        if v is None:
            rows.append({"certificate": name, "status": "UNMEASURED",
                         "why": "no verdict written for this cell in the re-judge"})
            continue
        fails = [g for g, s in (v.get("stages") or {}).items() if not s.get("passed")]
        rows.append({
            "certificate": name, "cell": cid,
            "status": "STILL_PASSES" if v.get("passed") else "COST_REGRADE_FAIL",
            "gates_failing_now": fails,
            "cost_per_lot_now": round(float(cell["costs"].spread_per_lot)
                                      + float(cell["costs"].commission_per_lot), 4),
        })

    still = sum(1 for r in rows if r["status"] == "STILL_PASSES")
    failed = sum(1 for r in rows if r["status"] == "COST_REGRADE_FAIL")
    doc = {
        "audited_at": datetime.now(tz=UTC).isoformat(timespec="seconds"),
        "certificates_in_canon": len(survivors),
        "rebuilt_and_judged": len(rows),
        "still_passes": still, "cost_regrade_fail": failed,
        "skipped": skipped, "rows": rows,
        "note": ("Re-judged under the CURRENT cost model after bc4b03ed corrected three "
                 "undercharges. Thresholds are untouched -- this is a corrected measurement, "
                 "not a harsher bar. Nothing is revoked here: canon never shrinks from a script, "
                 "and retirement is the principal's call on this evidence."),
    }
    OUT.write_text(json.dumps(doc, indent=1, default=str), "utf-8")
    print(f"\nRECERTIFICATION: {still} still pass, {failed} FAIL under corrected costs "
          f"({len(skipped)} unrebuildable) -> {OUT}")
    for r in rows:
        if r["status"] == "COST_REGRADE_FAIL":
            print(f"   FAIL {r['certificate']}: now fails {', '.join(r['gates_failing_now'])}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
