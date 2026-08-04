#!/usr/bin/env python3
"""Read reports/gate_power_audit.json and print the tables the audit was run to produce.

Separate from the measurement on purpose: re-reading an artifact must never re-run a two-hour
Monte Carlo, and a reporting bug must never be able to change a measured number.

    python -u scripts/report_gate_audit.py [--json path]
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

_ROOT = Path("/home/quant/quant-platform")
if not _ROOT.exists():
    _ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

_DEFAULT = Path("reports/gate_power_audit.json")


def _pct(x: float | None, nd: int = 1) -> str:
    return "  n/a" if x is None else f"{100 * x:>{4 + nd}.{nd}f}%"


def _ci(d: dict[str, Any]) -> str:
    lo, hi = d.get("ci95", [None, None])
    return "n/a" if lo is None else f"[{100 * lo:.1f},{100 * hi:.1f}]"


def power_curve(conds: list[dict[str, Any]]) -> None:
    print("\nPOWER CURVE -- probability a candidate survives EVERY gate")
    print(f"{'true SR':>8} {'power':>8} {'95% CI':>14} {'n_true':>7} | "
          f"{'Type I':>8} {'95% CI':>14} {'n_null':>7}")
    for c in conds:
        t, p = c["condition"]["true_sr"], c["power_joint"]
        f = c["type_i_joint"]
        print(f"{t:>8.1f} {_pct(p['rate']):>8} {_ci(p):>14} {p['n']:>7} | "
              f"{_pct(f['rate'], 2):>8} {_ci(f):>14} {f['n']:>7}")


def marginal_table(c: dict[str, Any]) -> None:
    """The question every gate must answer: what does it BUY and what does it COST?"""
    cond = c["condition"]
    print(f"\nMARGINAL CONTRIBUTION OF EACH GATE  (true SR={cond['true_sr']}, "
          f"N={cond['n']}, T={cond['t']})")
    print("  'blocks true' = share of GENUINE alphas this gate rejects   (its Type II cost)")
    print("  'passes null' = share of NOISE this gate lets through       (its Type I leak)")
    print("  LOO = drop this gate, keep the rest: change in power and in false-positive rate")
    print(f"\n{'gate':>20} {'blocks true':>12} {'passes null':>12} | "
          f"{'LOO d power':>12} {'LOO d FPR':>11} {'sole blocker':>13}")
    sole = c["sole_blocker_of_true_alpha"]
    rows = []
    for g, d in c["per_gate"].items():
        loo = c["leave_one_out"][g]
        rows.append((loo["delta_power"] or 0.0, g, d, loo))
    for _, g, d, loo in sorted(rows, reverse=True):
        print(f"{g:>20} {_pct(d['blocks_true']['rate']):>12} "
              f"{_pct(d['passes_null']['rate']):>12} | "
              f"{_pct(loo['delta_power']):>12} {_pct(loo['delta_fpr'], 2):>11} "
              f"{sole.get(g, 0):>13}")
    print(f"{'':>20} {'':>12} {'':>12} | joint power {_pct(c['power_joint']['rate'])}"
          f"  joint FPR {_pct(c['type_i_joint']['rate'], 2)}")


def subset_table(c: dict[str, Any]) -> None:
    """Leave-one-out is blind to redundancy: two gates that block the same candidates each look
    free when removed alone. Removing them as a pair is the only way to see it."""
    cond = c["condition"]
    subs = c.get("gate_subsets")
    if not subs:
        return
    print(f"\nGATE SUBSETS -- redundancy between the multiplicity corrections "
          f"(true SR={cond['true_sr']}, N={cond['n']}, T={cond['t']})")
    print(f"{'gates kept':>34} {'power':>8} {'95% CI':>14} {'FPR':>8} {'95% CI':>14}")
    for name, s in subs.items():
        lo, hi = s["power_ci95"]
        flo, fhi = s["fpr_ci95"]
        print(f"{name:>34} {_pct(s['power']):>8} [{100 * lo:>5.1f},{100 * hi:>5.1f}]  "
              f"{_pct(s['fpr'], 2):>8} [{100 * flo:>5.2f},{100 * fhi:>5.2f}]")


def calibration_table(conds: list[dict[str, Any]]) -> None:
    print("\nCALIBRATION UNDER THE NULL -- is each correction the size it claims to be?")
    print(f"{'condition':>26} {'DSR>=.95':>10} {'RC p<=.05':>10} {'mean RC p':>10} "
          f"{'PBO<=.5':>9}")
    print(f"{'nominal':>26} {'5.0%':>10} {'5.0%':>10} {'0.500':>10} {'50.0%':>9}")
    for c in conds:
        cal = c.get("calibration") or {}
        if not cal:
            continue
        cond = c["condition"]
        lbl = f"SR={cond['true_sr']} N={cond['n']} T={cond['t']}"
        print(f"{lbl:>26} {_pct(cal['dsr_realised_fpr'], 2):>10} "
              f"{_pct(cal['reality_p_realised_fpr'], 2):>10} "
              f"{cal['reality_p_mean_should_be_0.5_if_uniform']:>10.3f} "
              f"{_pct(cal['pbo_realised_fpr_at_0.5']):>9}")


def auc_table(conds: list[dict[str, Any]]) -> None:
    print("\nDISCRIMINATION (AUC) -- can the statistic tell a true alpha from noise AT ALL?")
    print("  0.50 = uninformative at every threshold (re-tuning cannot help)")
    print(f"{'true SR':>8} {'DSR':>8} {'reality p':>10} {'PBO':>8} {'OOS Sharpe':>11}")
    for c in conds:
        if c["condition"]["true_sr"] <= 0:
            continue
        a = c["auc"]
        def f(x: float | None) -> str:
            return " n/a" if x is None else f"{x:>.3f}"
        print(f"{c['condition']['true_sr']:>8.1f} {f(a['dsr']):>8} {f(a['reality_p']):>10} "
              f"{f(a['pbo']):>8} {f(a['oos_sharpe']):>11}")


def bottleneck_table(studies: dict[str, list[dict[str, Any]]]) -> None:
    print("\nBOTTLENECK -- which knob actually moves power?")
    for name, key, fmt in (("history_length", "t", "T={}"),
                           ("campaign_size", "n", "N={}"),
                           ("correlation", "rho", "rho={}"),
                           ("realism", None, "{}")):
        conds = studies.get(name) or []
        if not conds:
            continue
        print(f"\n  {name}:")
        for c in conds:
            cond = c["condition"]
            if key is None:
                lbl = (f"ar1={cond['ar1']}" if cond.get("ar1") else
                       f"t-dist df={cond['df']}" if cond.get("df") else
                       f"regime={cond['regime']}")
            else:
                lbl = fmt.format(cond[key])
            neff = c.get("effective_n_tests_ratio_vs_baseline", {}).get("participation")
            extra = f"   N_eff/baseline {neff:.2f}" if neff is not None else ""
            print(f"    {lbl:>18}  power {_pct(c['power_joint']['rate']):>7} "
                  f"{_ci(c['power_joint']):>13}   FPR {_pct(c['type_i_joint']['rate'], 2):>7}"
                  f"{extra}")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", default=str(_DEFAULT))
    args = ap.parse_args()
    d = json.loads(Path(args.json).read_text("utf-8"))
    studies = d["studies"]
    pc = studies.get("power_curve") or []
    if pc:
        power_curve(pc)
        auc_table(pc)
        calibration_table(pc)
        # the marginal table at the effect size where the decision actually bites
        for c in pc:
            if c["condition"]["true_sr"] in (2.0, 3.0, 5.0):
                marginal_table(c)
                subset_table(c)
    bottleneck_table(studies)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
