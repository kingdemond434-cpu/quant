#!/usr/bin/env python3
"""THE SENSITIVITY FLOOR UNDER RANKED ADMISSION -- measured the same way the wall was measured.

THE QUESTION. libs/validation/screen_admission.py split the gauntlet: STRUCTURAL gates still
block, STATISTICAL gates only rank, and MIN_ADMISSION_OOS_SHARPE = 0.25 is a relevance floor. The
all-gates-must-pass rule it replaced was certified at TRUE SHARPE 5.0 and measured at 12.08% power
there (reports/gate_power_audit.json). Nobody has measured what the NEW path resolves, and until
that number exists "admission is not a relaxation" is an argument rather than a finding.

METHOD, AND WHY IT REUSES THE OLD ONE VERBATIM. The cohorts come from
scripts/audit_gate_power.simulate_cohort and are scored by its score_cohort -- i.e. through the
REAL validate() with the REAL campaign statistics, at the campaign's own shape (N=420, T=310,
20 true alphas per cohort). Writing a fresh generator would have produced numbers that could not
be laid beside the recorded audit, and the whole point is the comparison: same draws, same
scorer, one difference -- the decision rule at the end.

TWO DIFFERENT POWERS ARE REPORTED AND THEY MUST NOT BE CONFLATED:

  ADMISSIBLE   the candidate clears the structural gates and the relevance floor. This is the
               GATE's power, independent of how many slots happen to be free, and it is the
               number comparable to the recorded audit's `power_joint`.
  ADMITTED     the candidate actually receives one of the 12 idle forward clocks, after ranking
               against every other candidate in its own cohort. This is the number the desk
               experiences, and it can only be lower.

The gap between them is slot scarcity, which is a resource fact rather than a statistical one,
and reporting only the second would blame the gate for the shortage of clocks.

WHAT IS DELIBERATELY NOT DONE. No threshold is tuned, and MIN_ADMISSION_OOS_SHARPE is read from
the module rather than restated, so if the floor moves this measurement moves with it. A higher
admission rate is not a result -- it is the cost side of the trade being priced.

    python3 scripts/measure_admission_power.py --reps 12
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path
from typing import Any

import numpy as np

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))
if str(_ROOT / "scripts") not in sys.path:
    # audit_gate_power is a SCRIPT, not a package module. Importing it rather than copying its
    # generator is the only way these numbers stay comparable to reports/gate_power_audit.json.
    sys.path.insert(0, str(_ROOT / "scripts"))

from audit_gate_power import _wilson, score_cohort, simulate_cohort  # noqa: E402

from libs.research.slot_registry import MAX_FORWARD_SLOTS  # noqa: E402
from libs.validation.admission_power import (  # noqa: E402
    BRAIN_TARGET_SHARPE,
    OLD_CERTIFIED_FLOOR,
    POWER_TARGET,
    power_crossing,
    slot_occupancy_cost,
)
from libs.validation.positive_control import PPY  # noqa: E402
from libs.validation.screen_admission import (  # noqa: E402
    MIN_ADMISSION_OOS_SHARPE,
    STRUCTURAL_GATES,
    admit,
)

_OUT = _ROOT / "reports" / "admission_power.json"

#: The campaign shape the 0-of-420 record was measured on. Anchored to the recorded audit's
#: `base_shape` so the two artifacts describe the same experiment.
_BASE_N, _BASE_T = 420, 310
_N_TRUE = 20

#: True ANNUALISED Sharpes to price. The task's grid (0.5 .. 5.0) plus the bracketing levels the
#: recorded audit already showed are needed: at 5.0 the old rule had 12% power, so a grid that
#: stops at 5.0 can only report "no crossing" and would leave the new floor unlocated.
_GRID: tuple[float, ...] = (0.0, 0.5, 1.0, 1.5, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 10.0)


def _rows_to_candidates(rows: list[dict[str, Any]]) -> list[dict[str, object]]:
    """Shape scored candidates for `admit()`.

    Turnover is NOT supplied, and that is a measurement decision rather than an omission: these
    are simulated return streams with no position path, so their turnover is genuinely unknown.
    `admit` then applies no turnover penalty but still records the UNMEASURED cost basis, which is
    the honest state -- inventing a turnover would put a number the generator chose into a rank.
    """
    return [{"name": f"c{i}", "gates": r["gates"], "oos_sharpe": r["oos_sharpe"],
             "dsr": r["dsr"], "reality_p": r["reality_p"]} for i, r in enumerate(rows)]


def _rate(k: int, n: int) -> dict[str, Any]:
    lo, hi = _wilson(k, n)
    return {"k": k, "n": n, "rate": (k / n) if n else None, "ci95": [lo, hi]}


def run_level(true_sr: float, *, reps: int, seed0: int, n: int = _BASE_N, n_obs: int = _BASE_T,
              n_true: int = _N_TRUE, slots: int = MAX_FORWARD_SLOTS,
              verbose: bool = True) -> dict[str, Any]:
    """One true-Sharpe level: admissibility, ranked admission into `slots`, and the attribution.

    Each replication is ONE CAMPAIGN. The slot competition is therefore run per replication and
    never on the pooled rows -- pooling 12 campaigns and offering them 12 slots would model a desk
    that screens 5,040 candidates against one slot table, which is not the experiment being run
    and would understate the true alphas' chance of winning a clock by twelve-fold.
    """
    n_t = 0 if true_sr <= 0.0 else n_true
    adm_true = adm_null = elig_true = elig_null = 0
    tot_true = tot_null = 0
    struct_true = struct_null = floor_true = floor_null = 0
    slot_true = slot_null = slot_used = 0
    oos_true: list[float] = []
    oos_null: list[float] = []
    supplied: set[str] = set()
    struct_seen: dict[str, dict[str, int]] = {}

    for i in range(reps):
        rng = np.random.default_rng(seed0 + 7919 * i)
        m, flags = simulate_cohort(n, n_obs, rng, n_true=n_t, true_ann_sharpe=true_sr)
        t0 = time.time()
        rows = score_cohort(m, flags)
        cands = _rows_to_candidates(rows)
        for c in cands:
            g = c["gates"]
            if isinstance(g, dict):
                supplied |= {k for k in g if k in STRUCTURAL_GATES}

        # UNBOUNDED slots: the GATE's verdict, free of the resource question.
        unbounded = admit(cands, idle_slots=len(cands))
        admissible = {a.name for a in unbounded.admitted}
        # The real campaign: 12 idle clocks, everything competing on rank.
        bounded = admit(cands, idle_slots=slots)
        won = {a.name for a in bounded.admitted}
        slot_used += len(won)

        for c, r in zip(cands, rows, strict=True):
            is_true = bool(r["is_true"])
            gates = r["gates"]
            # R0419: this was `all(gates.get(g, True) ...)`, which counts a gate NOBODY SUPPLIED
            # as a PASS -- so the harness that produced the "structural gates pass 73-100% of
            # true alphas" figure reproduced, in its own arithmetic, the very defect it would
            # have caught. Measured: break_even_win_rate and sample_adequacy were absent for 100%
            # of rows, so the published rate was computed over 4 of 6 declared gates while
            # reading as though it covered all six.
            #
            # AND ONE OF THOSE FOUR IS STILL FABRICATED, one file upstream: `audit_gate_power`
            # builds each row as `{g: bool(v.gates.get(g, True)) for g in GATES}`, so `capacity`
            # -- which validate() only emits when an ADV input exists, and records as UNMEASURED
            # otherwise -- arrives here as a constant True. Measured on this harness: capacity
            # 80/80 pass, 0 fail. The histogram below shows it as a CONSTANT-PASS gate rather
            # than hiding it, but the fix belongs upstream and is rowed separately (R0569): it
            # moves audit_gate_power's own published power numbers and needs its own re-run.
            #
            # The evaluated gates still decide struct_ok -- an absent gate must not FAIL a
            # candidate either (that is the beats_baselines defect pointed the other way). What
            # changes is that the denominator is now honest about what it measured.
            evaluated = [g for g in STRUCTURAL_GATES if g in gates]
            struct_ok = all(gates[g] for g in evaluated)
            for g in STRUCTURAL_GATES:
                cell = struct_seen.setdefault(g, {"pass": 0, "fail": 0, "unmeasured": 0})
                cell["unmeasured" if g not in gates else
                     ("pass" if gates[g] else "fail")] += 1
            floor_ok = float(r["oos_sharpe"]) >= MIN_ADMISSION_OOS_SHARPE
            name = str(c["name"])
            if is_true:
                tot_true += 1
                elig_true += int(name in admissible)
                struct_true += int(struct_ok)
                floor_true += int(floor_ok)
                slot_true += int(name in won)
                oos_true.append(float(r["oos_sharpe"]))
            else:
                tot_null += 1
                elig_null += int(name in admissible)
                struct_null += int(struct_ok)
                floor_null += int(floor_ok)
                slot_null += int(name in won)
                oos_null.append(float(r["oos_sharpe"]))
        adm_true, adm_null = elig_true, elig_null
        if verbose:
            print(f"    SR={true_sr:4.1f} rep {i + 1}/{reps} [{time.time() - t0:5.1f}s] "
                  f"admissible true {elig_true}/{tot_true} null {elig_null}/{tot_null}", flush=True)

    def _stats(x: list[float]) -> dict[str, float | None]:
        if not x:
            return {"mean": None, "sd": None, "p95": None, "max": None}
        a = np.asarray(x, dtype="float64")
        return {"mean": float(a.mean()), "sd": float(a.std(ddof=1)) if a.size > 1 else 0.0,
                "p95": float(np.quantile(a, 0.95)), "max": float(a.max())}

    return {
        "true_ann_sharpe": true_sr,
        "reps": reps,
        "n_true": tot_true,
        "n_null": tot_null,
        "admissible_power": _rate(adm_true, tot_true),
        "false_admissible_rate": _rate(adm_null, tot_null),
        "structural_only_pass": {"true": _rate(struct_true, tot_true),
                                 "null": _rate(struct_null, tot_null)},
        "relevance_floor_only_pass": {"true": _rate(floor_true, tot_true),
                                      "null": _rate(floor_null, tot_null)},
        "ranked_admission_into_slots": {
            "slots_per_campaign": slots,
            "slots_filled_per_campaign": slot_used / reps,
            "true_alphas_given_a_clock_per_campaign": slot_true / reps,
            "nulls_given_a_clock_per_campaign": slot_null / reps,
            "power_after_ranking": _rate(slot_true, tot_true),
        },
        "oos_sharpe_true": _stats(oos_true),
        "oos_sharpe_null": _stats(oos_null),
        "structural_gates_supplied_by_validate": sorted(supplied),
        "structural_gates_never_supplied": sorted(set(STRUCTURAL_GATES) - supplied),
        # THE PER-GATE HISTOGRAM THE GATE-OPTIMALITY DUTY DEMANDS (R0419). The two summary lists
        # above say WHICH gates were supplied; this says what each one actually DID. `unmeasured`
        # is a first-class column: absence from a rejection tally is ambiguous between "never
        # evaluated" and "evaluated and always passed", and only one of those is a wiring defect.
        "structural_gate_histogram": struct_seen,
        "structural_pass_rate_is_measured_over": sorted(
            g for g, h in struct_seen.items() if h["pass"] + h["fail"]),
    }


def build_report(levels: list[dict[str, Any]], *, reps: int, slots: int) -> dict[str, Any]:
    """Assemble the artifact, including the crossing and the slot-cost arithmetic."""
    grid = [x["true_ann_sharpe"] for x in levels if x["n_true"] > 0]
    pw_gate = [x["admissible_power"]["rate"] for x in levels if x["n_true"] > 0]
    pw_slot = [x["ranked_admission_into_slots"]["power_after_ranking"]["rate"]
               for x in levels if x["n_true"] > 0]
    cross_gate = power_crossing(grid, pw_gate)
    cross_slot = power_crossing(grid, pw_slot)

    # The worst-case slot cost is priced on the PURE-NULL level (true_sr = 0): a campaign in which
    # nothing real was submitted, which is the campaign this desk has actually been running.
    pure = next((x for x in levels if x["n_true"] == 0), None)
    null_rate = float(pure["false_admissible_rate"]["rate"]) if pure else float("nan")
    null_n = int(pure["n_null"] // max(1, reps)) if pure else 0
    cost = slot_occupancy_cost(null_rate, n_screened_nulls=null_n, n_slots=slots)
    realised = (pure["ranked_admission_into_slots"]["nulls_given_a_clock_per_campaign"]
                if pure else float("nan"))

    def _ratios(c: Any) -> dict[str, Any]:
        f = c.sensitivity_floor
        ok = bool(np.isfinite(f)) and f > 0.0
        return {"sensitivity_floor_true_ann_sharpe": (f if ok else None),
                "bracketed": c.bracketed,
                "ratio_to_old_certified_floor_5.0": (f / OLD_CERTIFIED_FLOOR) if ok else None,
                "ratio_to_brain_target_1.25": (f / BRAIN_TARGET_SHARPE) if ok else None,
                "summary": c.summary(), "note": c.note}

    return {
        "generated_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "status": "MEASURED",
        "question": "what does the gauntlet resolve once STRUCTURAL gates block and STATISTICAL "
                    "gates only rank",
        "method": "libs.validation.screen_admission.admit applied to cohorts from "
                  "scripts/audit_gate_power.simulate_cohort scored by the REAL validate(); same "
                  "generator and scorer as reports/gate_power_audit.json",
        "shape": {"n": _BASE_N, "t": _BASE_T, "n_true_per_cohort": _N_TRUE, "reps": reps,
                  "slots": slots},
        "power_target": POWER_TARGET,
        "relevance_floor": {
            "MIN_ADMISSION_OOS_SHARPE": MIN_ADMISSION_OOS_SHARPE,
            "units_of_oos_sharpe": "PER-BAR (libs/validation/revalidation.WalkForwardEngine "
                                   "averages sharpe_ratio() over folds and never annualises)",
            "floor_in_annualised_sharpe": MIN_ADMISSION_OOS_SHARPE * float(np.sqrt(PPY)),
            "ppy": PPY,
        },
        "crossing_gate_only": _ratios(cross_gate),
        "crossing_after_slot_competition": _ratios(cross_slot),
        "false_admission_cost": {
            "measured_on": "pure-null cohorts (true Sharpe 0.0)",
            "rate": null_rate,
            "nulls_screened_per_campaign": null_n,
            "worst_case_slots_wasted_per_campaign": cost.slots_wasted_per_campaign,
            "expected_admissible_nulls_per_campaign": cost.expected_false_admissions,
            "realised_nulls_given_a_clock_per_campaign": realised,
            "saturated": cost.saturated,
            "verdict": cost.verdict,
            "summary": cost.summary(),
        },
        "recorded_all_gates_audit_for_comparison": {
            "source": "reports/gate_power_audit.json (power_curve study)",
            "power_at_true_sharpe_5.0": 0.1208333333,
            "type_i_at_every_level": 0.0,
            "nulls_per_level": 4800,
        },
        "levels": levels,
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--reps", type=int, default=12)
    ap.add_argument("--seed0", type=int, default=90210)
    ap.add_argument("--slots", type=int, default=MAX_FORWARD_SLOTS)
    ap.add_argument("--grid", default=",".join(f"{g:g}" for g in _GRID))
    ap.add_argument("--out", default=str(_OUT))
    args = ap.parse_args(argv)

    grid = [float(x) for x in str(args.grid).split(",") if x.strip()]
    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    levels: list[dict[str, Any]] = []
    for sr in grid:
        print(f"== true annualised Sharpe {sr:g} ==", flush=True)
        levels.append(run_level(sr, reps=args.reps, seed0=args.seed0, slots=args.slots))
        # CHECKPOINT per level: each level is ~1 minute of real validate() calls, and a sweep that
        # dies at 90% must not discard the 90%. An exit code proves a process ended, never that it
        # produced -- so the artifact is written as it goes and carries its own status.
        partial = build_report(levels, reps=args.reps, slots=args.slots)
        partial["status"] = "RUNNING" if len(levels) < len(grid) else "MEASURED"
        partial["levels_done"] = len(levels)
        partial["levels_planned"] = len(grid)
        out_path.write_text(json.dumps(partial, indent=2), "utf-8")

    rep = build_report(levels, reps=args.reps, slots=args.slots)
    rep["levels_done"] = len(levels)
    rep["levels_planned"] = len(grid)
    out_path.write_text(json.dumps(rep, indent=2), "utf-8")
    print("\n" + "=" * 78)
    print(rep["crossing_gate_only"]["summary"])
    print(rep["crossing_after_slot_competition"]["summary"])
    print(rep["false_admission_cost"]["summary"])
    print(f"wrote {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
