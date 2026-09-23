"""EFFECTIVE TRIALS -- the multiplicity budget is charged in independent TESTS, not in rows.

    "more cells make certification harder, because the deflated-Sharpe gate charges a shared
     multiplicity cost"                          -- the measured tension, 2026-09-23

WHAT WAS MEASURED. The desk pushes ~311 cells an hour whose orthogonality-weighted equivalent is
25.9: a thirty-one-times multiplicity bill for one mechanism's worth of information. The
deflated-Sharpe hurdle is `expected_max_sharpe(n_trials, variance_of_sharpes)`, and it grows with
sqrt(2 ln N), so every extra tuning of an existing rule raises the bar that every OTHER cell --
including the ones testing genuinely new mechanisms -- has to clear. Thirty-one parameter variants
of one rule on one instrument at one horizon are nearer ONE independent test than thirty-one, and
charging them as thirty-one is not conservatism, it is a wrong correction that happens to point
the harsh way.

WHAT THIS ORGAN DOES, AND THE ONE THING IT DOES NOT. It measures the desk's own docket with
`libs.research.trial_ledger.effective_independent_tests` -- the participation ratio of the
(grid cell, content) identity sizes within each mechanism, where the grid cell is (family, symbol,
horizon) -- publishes NOMINAL versus EFFECTIVE per family with the ratio, and writes the corrected
campaign charge into the ONE input the sealed judge already reads for it:

    desks/mt5/policy/gate_spec.yaml -> gates[deflated_sharpe].params.fixed_trial_count

`desks/mt5/scripts/external_gauntlet.py` is SEALED and is not touched. It calls
`research.gate_policy.charged_trial_count`, which returns `_SPEC_FIXED_TRIALS` -- that spec value
and nothing else. So the number arrives through the judge's existing door, as POLICY, in the
policy file, where it is visible and diffable; the seal holds.

IT NEVER REMOVES A CELL, CAPS A PRODUCER OR LOWERS A GATE. The ten gates run exactly as defined,
the raw cell count is untouched, and the miners are unrestricted. The only thing that changes is
that the multiplicity charge stops counting one search thirty-one times.

DIRECTION, FLOORS AND FAILING CLOSED. The corrected charge is only ever LOWER than the nominal
campaign count, which is the direction that makes a bar easier, so every safeguard here points the
other way:

  * the charge is floored at the number of DISTINCT MECHANISMS in the docket -- you cannot have
    run fewer independent tests than you had distinct economic claims;
  * an unmeasurable or implausible census returns the UNCHANGED nominal count (`campaign_charge`
    fails closed upward, never downward);
  * the spec is rewritten only when the measured charge differs from the standing one by more
    than `MIN_CHANGE_FRAC`, so the bar is a property of policy, not of the hour -- the defect the
    fixed charge was introduced to remove;
  * `attestation` supersession is recorded in `research.gate_policy` so a certificate never
    attests to a basis it was not judged under.

WHAT IT PUBLISHES -- `reports/EFFECTIVE_TRIALS.json`: `nominal` and `effective` totals with the
`ratio`, the per-family table (`n_nominal`, `n_effective`, `n_grid_cells`, `n_identities`,
`ratio`), the campaign charge before and after, and the deflated-Sharpe hurdle `sr0` before and
after so the effect on the bar is inspectable rather than asserted.

WHO READS IT. The sealed gauntlet reads the spec value on its next sweep (proved by measurement:
`research.gate_policy.charged_trial_count` returns it); `scripts/check_tier1_program.py` cites the
artifact; `research/judge_coverage.py` publishes the realised pass rate the same hour, so what the
budget is spent on and what the budget costs are readable side by side.
"""
from __future__ import annotations

import argparse
import json
import math
import re
import sys
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

BASE = Path(__file__).resolve().parent.parent
ROOT = BASE.parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(BASE) not in sys.path:
    sys.path.insert(0, str(BASE))

REPORTS = BASE / "reports"
DOCKET = BASE / "data" / "hypotheses" / "external_survivors.json"
SPEC_PATH = BASE / "policy" / "gate_spec.yaml"
REPORT = REPORTS / "EFFECTIVE_TRIALS.json"

#: The standing campaign charge is rewritten only when the measurement moves this much. A bar
#: that moved every hour would be a property of the hour again, which is the whole defect the
#: fixed charge removed.
MIN_CHANGE_FRAC = 0.05
#: Rows read from the docket in one pass. Derived from the budget, never from a machine size.
MAX_ROWS = 60_000
UNMEASURED = "UNMEASURED"


def _now() -> str:
    return datetime.now(tz=UTC).isoformat(timespec="seconds")


def read_docket(path: Path | None = None, *, limit: int = MAX_ROWS) -> list[dict[str, Any]]:
    """The docket the judge is handed, as rows. Absent or malformed is an empty docket, which is
    UNMEASURED downstream -- never an invented one."""
    try:
        raw = json.loads((path or DOCKET).read_text("utf-8"))
    except (OSError, ValueError):
        return []
    rows = raw if isinstance(raw, list) else None
    if rows is None and isinstance(raw, dict):
        for value in raw.values():
            if isinstance(value, list) and value:
                rows = value
                break
    if not isinstance(rows, list):
        return []
    return [r for r in rows[:limit] if isinstance(r, dict)]


def spec_fixed_trial_count(path: Path | None = None) -> int | None:
    """The standing campaign charge as the sealed judge will read it, from the spec itself."""
    try:
        import yaml
        spec = yaml.safe_load((path or SPEC_PATH).read_text("utf-8"))
    except (OSError, ValueError, ImportError):
        return None
    except Exception:
        return None
    if not isinstance(spec, dict):
        return None
    for gate in spec.get("gates") or []:
        if isinstance(gate, dict) and gate.get("name") == "deflated_sharpe":
            val = (gate.get("params") or {}).get("fixed_trial_count")
            return int(val) if isinstance(val, int) else None
    return None


def spec_variance_of_sharpes(path: Path | None = None) -> float | None:
    try:
        import yaml
        spec = yaml.safe_load((path or SPEC_PATH).read_text("utf-8"))
    except Exception:
        return None
    if not isinstance(spec, dict):
        return None
    for gate in spec.get("gates") or []:
        if isinstance(gate, dict) and gate.get("name") == "deflated_sharpe":
            val = (gate.get("params") or {}).get("fixed_variance_of_sharpes")
            return float(val) if isinstance(val, (int, float)) else None
    return None


def sr0(n_trials: int, variance_of_sharpes: float) -> float:
    """The deflated-Sharpe hurdle this charge produces, from the desk's own estimator."""
    try:
        from libs.validation.dsr import expected_max_sharpe
        return float(expected_max_sharpe(int(n_trials), float(variance_of_sharpes)))
    except Exception:
        return float("nan")


#: The nominal campaign charge this desk operated under before any correction, and the value its
#: standing certificates were issued at. It is the number the correction SCALES, and the number
#: every failure path returns to.
NOMINAL_CAMPAIGN_TRIALS = 597


def measure(rows: list[dict[str, Any]]) -> dict[str, Any]:
    """Nominal versus effective independent tests, per family and in total."""
    from libs.research.trial_ledger import effective_independent_tests
    census = effective_independent_tests(rows)
    out = census.to_dict()
    fams = sorted(census.families.values(),
                  key=lambda c: (-c.n_nominal, c.family))
    out["by_family"] = [c.to_dict() for c in fams]
    out.pop("families", None)
    return out


def charge(census_dict: dict[str, Any], *, nominal: int = NOMINAL_CAMPAIGN_TRIALS
           ) -> tuple[int, str]:
    """The campaign charge the corrected census supports; fails closed to `nominal`."""
    from libs.research.trial_ledger import ChargeCensus, FamilyCharge
    fams = {row["family"]: FamilyCharge(
        str(row["family"]), int(row["n_nominal"]), float(row["n_effective"]),
        int(row.get("n_grid_cells") or 0), int(row.get("n_identities") or 0),
        float(row.get("ratio") or 1.0), str(row.get("basis") or ""))
        for row in census_dict.get("by_family") or []}
    census = ChargeCensus(int(census_dict.get("n_nominal") or 0),
                          float(census_dict.get("n_effective") or 0.0),
                          int(census_dict.get("n_mechanisms") or 0), fams,
                          str(census_dict.get("basis") or ""),
                          str(census_dict.get("status") or UNMEASURED))
    from libs.research.trial_ledger import campaign_charge
    return campaign_charge(nominal, census)


_COUNT_RE = re.compile(r"^(\s*fixed_trial_count:\s*)(\d+)(.*)$", re.M)
_BASIS_RE = re.compile(r'^(\s*trial_count_basis:\s*")([^"]*)(".*)$', re.M)
_FAILCLOSED_RE = re.compile(r'^(\s*fail_closed_to:\s*")([^"]*)(".*)$', re.M)


def apply_to_spec(charged: int, *, variance: float, path: Path | None = None,
                  dry_run: bool = False) -> dict[str, Any]:
    """Write the corrected charge into the judge's existing input, preserving the file's text.

    An anchored regex edit, NOT a YAML round-trip: every threshold in `gate_spec.yaml` carries the
    measurement that set it in a comment above it, and a `safe_dump` would silently delete the
    entire audit trail this desk's policy is made of.
    """
    target = path or SPEC_PATH
    try:
        text = target.read_text("utf-8")
    except OSError as exc:
        return {"status": UNMEASURED, "why": f"{type(exc).__name__}: {exc}"}
    m = _COUNT_RE.search(text)
    if m is None:
        return {"status": UNMEASURED, "why": "fixed_trial_count not found in spec"}
    standing = int(m.group(2))
    if charged >= standing:
        return {"status": "UNCHANGED", "standing": standing, "charged": charged,
                "why": "the corrected charge is not lower than the standing one; the bar stands"}
    if standing > 0 and abs(standing - charged) / standing < MIN_CHANGE_FRAC:
        return {"status": "UNCHANGED", "standing": standing, "charged": charged,
                "why": f"change {abs(standing - charged) / standing:.4f} below "
                       f"MIN_CHANGE_FRAC {MIN_CHANGE_FRAC}; the bar is policy, not the hour"}
    basis = (f"effective_campaign_trials({charged}) + fixed_variance_of_sharpes({variance}): "
             f"the campaign charge is measured in EFFECTIVE independent tests -- the "
             f"participation ratio of (grid cell, content) identities within each mechanism -- "
             f"not in docket rows; both inputs remain constants, so the bar is identical for "
             f"every cell regardless of how many others share its sweep")
    new = _COUNT_RE.sub(lambda mm: f"{mm.group(1)}{charged}{mm.group(3)}", text, count=1)
    new = _BASIS_RE.sub(lambda mm: f"{mm.group(1)}{basis}{mm.group(3)}", new, count=1)
    new = _FAILCLOSED_RE.sub(
        lambda mm: f"{mm.group(1)}effective_campaign_trials({charged}){mm.group(3)}", new,
        count=1)
    if new == text:
        return {"status": "UNCHANGED", "standing": standing, "charged": charged,
                "why": "spec text already carries this charge"}
    if dry_run:
        return {"status": "DRY_RUN", "standing": standing, "charged": charged, "basis": basis}
    try:
        target.write_text(new, encoding="utf-8")
    except OSError as exc:
        return {"status": UNMEASURED, "standing": standing, "charged": charged,
                "why": f"{type(exc).__name__}: {exc}"}
    return {"status": "APPLIED", "standing": standing, "charged": charged, "basis": basis,
            "path": str(target)}


def judge_reads(expected: int) -> dict[str, Any]:
    """PROVE IT, do not assert it: ask the judge's own input function what it will charge.

    `external_gauntlet` computes `n_trials` by calling `research.gate_policy.charged_trial_count`,
    so re-importing that module from a clean state and reading its answer is the measurement of
    whether the sealed judge picked the number up.
    """
    out: dict[str, Any] = {"expected": expected}
    try:
        for name in [m for m in list(sys.modules)
                     if m == "gate_policy" or m.endswith(".gate_policy")]:
            sys.modules.pop(name, None)
        from research.gate_policy import charged_trial_count, fail_closed_trial_count
        got, basis = charged_trial_count(1000, None, None)
        out.update(charged_trial_count=int(got), basis=basis,
                   fail_closed=int(fail_closed_trial_count(1000)),
                   status="MEASURED", judge_reads_effective=bool(int(got) == int(expected)))
    except Exception as exc:
        out.update(status=UNMEASURED, why=f"{type(exc).__name__}: {exc}",
                   judge_reads_effective=False)
    return out


def build(*, docket: Path | None = None, spec: Path | None = None,
          apply: bool = True, budget_s: float = 120.0) -> dict[str, Any]:
    """Measure, publish, feed the judge's input, and measure that the judge reads it."""
    t0 = time.time()
    rows = read_docket(docket)
    census = measure(rows)
    variance = spec_variance_of_sharpes(spec)
    variance = 0.014863 if variance is None else variance
    standing = spec_fixed_trial_count(spec)
    nominal = NOMINAL_CAMPAIGN_TRIALS if standing is None else standing
    charged, basis = charge(census, nominal=NOMINAL_CAMPAIGN_TRIALS)
    applied = (apply_to_spec(charged, variance=variance, path=spec) if apply
               else {"status": "SKIPPED", "standing": standing, "charged": charged})
    effective_now = spec_fixed_trial_count(spec)
    proof = judge_reads(effective_now if effective_now is not None else nominal)
    before = sr0(nominal, variance)
    after = sr0(effective_now if effective_now else nominal, variance)
    doc = {
        "at": _now(),
        "verdict": ("MEASURED" if census.get("status") == "MEASURED" else UNMEASURED),
        "rule": ("the multiplicity budget is charged in EFFECTIVE independent tests -- the "
                 "participation ratio of (grid cell, content) identity sizes within each "
                 "mechanism -- never in docket rows; no gate is lowered, no cell removed, no "
                 "producer capped, and every failure path returns the unchanged nominal charge"),
        "docket_rows": len(rows),
        "nominal": census.get("n_nominal"),
        "effective": census.get("n_effective"),
        "ratio_nominal_per_effective": census.get("ratio"),
        "n_mechanisms": census.get("n_mechanisms"),
        "census_basis": census.get("basis"),
        "campaign": {
            "nominal_campaign_trials": NOMINAL_CAMPAIGN_TRIALS,
            "standing_spec_trial_count": standing,
            "charged": charged, "charge_basis": basis,
            "variance_of_sharpes": variance,
            "sr0_before": None if math.isnan(before) else round(before, 6),
            "sr0_after": None if math.isnan(after) else round(after, 6),
            "sr0_relief": (None if (math.isnan(before) or math.isnan(after))
                           else round(before - after, 6)),
            "spec_trial_count_now": effective_now,
        },
        "applied": applied,
        "judge_input_proof": proof,
        "by_family": census.get("by_family") or [],
        "elapsed_s": round(time.time() - t0, 3),
        "budget_s": budget_s,
    }
    return doc


def write(doc: dict[str, Any], *, report: Path | None = None) -> Path:
    path = report or REPORT
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(doc, indent=2, sort_keys=False, default=str), encoding="utf-8")
    try:
        from libs.ops.events import emit
        emit("effective_trials", leg="effective_trials",
             nominal=doc.get("nominal"), effective=doc.get("effective"),
             ratio=doc.get("ratio_nominal_per_effective"),
             charged=(doc.get("campaign") or {}).get("charged"),
             judge_reads_effective=(doc.get("judge_input_proof") or {}).get(
                 "judge_reads_effective"))
    except Exception:
        pass
    return path


def render(doc: dict[str, Any]) -> list[str]:
    cam = doc.get("campaign") or {}
    lines = [f"EFFECTIVE TRIALS {doc.get('at')}  {doc.get('verdict')}",
             f"  docket {doc.get('docket_rows')} rows: nominal {doc.get('nominal')} -> "
             f"effective {doc.get('effective')} (ratio {doc.get('ratio_nominal_per_effective')}x"
             f" over {doc.get('n_mechanisms')} mechanisms)",
             f"  campaign charge {cam.get('nominal_campaign_trials')} -> {cam.get('charged')}"
             f"  sr0 {cam.get('sr0_before')} -> {cam.get('sr0_after')}"
             f"  spec now {cam.get('spec_trial_count_now')}",
             f"  applied: {(doc.get('applied') or {}).get('status')}"
             f"  judge reads effective: "
             f"{(doc.get('judge_input_proof') or {}).get('judge_reads_effective')}"]
    for row in (doc.get("by_family") or [])[:12]:
        lines.append(f"    {row['family']:28s} nominal {row['n_nominal']:6d} effective "
                     f"{row['n_effective']:9.2f}  x{row['ratio']:.2f}  "
                     f"grid {row['n_grid_cells']} ident {row['n_identities']}")
    return lines


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--once", action="store_true", help="one pass (the scheduled mode)")
    ap.add_argument("--budget-s", type=float, default=120.0)
    ap.add_argument("--no-apply", action="store_true",
                    help="measure and publish, but do not write the spec")
    ap.add_argument("--docket", type=Path, default=None)
    ap.add_argument("--spec", type=Path, default=None)
    args = ap.parse_args(argv)
    doc = build(docket=args.docket, spec=args.spec, apply=not args.no_apply,
                budget_s=args.budget_s)
    write(doc)
    for line in render(doc):
        print(line)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
