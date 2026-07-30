"""LEAKAGE DETECTOR -- the deterministic half of red-teaming, and the missing measurement contract.

The principal's Measurement Integrity list named seven items. The gate shipped five. This is the
one with the strongest evidence behind it and the one an LLM red-team CANNOT do: leakage is
detected by arithmetic on the series, not by asking a model whether an idea smells wrong.

WHY IT MATTERS HERE SPECIFICALLY: H_OVERFIT is 24 refutations over 45 days, and the desk's whole
rail history -- SUSPECT-LOOKAHEAD (|IC|>0.35 or Sharpe>6), ic_exceeds_contemporaneous, the
gapped-window control, horizon-adjacency -- exists because leaked or confounded results kept
reaching serious testing. Those rails are scattered across individual screens. This makes them one
importable contract that any test can call, so a new script cannot silently omit them.

SEVEN CHECKS, each with a stated failure it catches:
  1 SUSPECT_MAGNITUDE     |IC| implausibly large for a real financial signal
  2 CONTEMPORANEOUS       same-period relationship dominates the forward one -> not a predictor
  3 ORTHOGONALITY         forward IC survives removing the same-period effect (the de-contamination
                          gate that turned four apparent findings into nulls on 2026-07-27)
  4 REVERSE_CAUSALITY     returns predict the feature better than the feature predicts returns
                          -> the "signal" is a CONSEQUENCE of the move, not a cause
  5 SHIFT_TEST            shifting the feature one period MORE into the past should WEAKEN it. If
                          it strengthens, the alignment is off by one and the test is reading the
                          future. This catches the single most common indexing bug in the repo.
  6 HORIZON_ADJACENCY     a real slow signal holds sign at neighbouring horizons; a leak spikes at
                          exactly one
  7 SURVIVORSHIP          the cross-section must not be selected using end-of-sample information

VALIDATED AGAINST KNOWN GROUND TRUTH, which the desk's commit-decision classifier was NOT. A
detector nobody has tested is itself an unverified measurement, and shipping one under a doctrine
that forbids exactly that would be indefensible. main() runs it on synthetic series whose answer
is known by construction -- a deliberately leaked feature, a pure-noise feature, and a genuine
weak signal -- and reports whether the detector got each right.

    from leakage_detector import audit
    verdict = audit(feature, fwd_ret, same_ret, name="depth5_replenish")

Read-only. No keys, no network. numpy only.
"""
from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "data/leakage_audit.json"

SUSPECT_IC = 0.35        # desk rail: financial signals do not honestly reach this
MIN_N = 40


def _spearman(a, b) -> tuple[float, float]:
    a, b = np.asarray(a, float), np.asarray(b, float)
    m = np.isfinite(a) & np.isfinite(b)
    a, b = a[m], b[m]
    if len(a) < 8:
        return 0.0, 0.0
    ra = np.argsort(np.argsort(a)).astype(float)
    rb = np.argsort(np.argsort(b)).astype(float)
    if ra.std() == 0 or rb.std() == 0:
        return 0.0, 0.0
    r = float(np.corrcoef(ra, rb)[0, 1])
    n = len(a)
    return r, float(r * np.sqrt((n - 2) / max(1e-12, 1 - r * r)))


def _resid(y, x):
    """y orthogonalised against x -- the de-contamination step."""
    y, x = np.asarray(y, float), np.asarray(x, float)
    m = np.isfinite(y) & np.isfinite(x)
    if m.sum() < 8:
        return None, None
    b = np.polyfit(x[m], y[m], 1)
    return y[m] - (b[0] * x[m] + b[1]), m


def audit(feature, fwd_ret, same_ret=None, name: str = "feature",
          horizons: dict | None = None, universe: list | None = None) -> dict:
    """Run every leakage contract. Returns a verdict dict; VERDICT=='CLEAN' is the only pass."""
    f = np.asarray(feature, float)
    r1 = np.asarray(fwd_ret, float)
    flags, notes = [], {}

    if len(f) != len(r1):
        return {"name": name, "verdict": "INVALID", "flags": ["length mismatch"], "notes": {}}
    if len(f) < MIN_N:
        return {"name": name, "verdict": "UNDERPOWERED",
                "flags": [f"n={len(f)} < {MIN_N}"], "notes": {}}

    ic, t_ic = _spearman(f, r1)
    notes["forward_ic"] = round(ic, 4)
    notes["forward_t"] = round(t_ic, 2)

    # 1 SUSPECT MAGNITUDE
    if abs(ic) > SUSPECT_IC:
        flags.append(f"SUSPECT_MAGNITUDE |IC|={abs(ic):.3f} > {SUSPECT_IC} -- financial signals "
                     f"do not honestly reach this; assume lookahead until proven otherwise")

    # 2/3 CONTEMPORANEOUS + ORTHOGONALITY
    if same_ret is not None:
        r0 = np.asarray(same_ret, float)
        ic0, _ = _spearman(f, r0)
        notes["same_period_ic"] = round(ic0, 4)
        if abs(ic0) > abs(ic) * 1.2:
            flags.append(f"CONTEMPORANEOUS same-period |IC|={abs(ic0):.3f} exceeds forward "
                         f"|IC|={abs(ic):.3f} -- this is not a predictor of the quantity, it IS "
                         f"the quantity")
        res, m = _resid(r1, r0)
        if res is not None:
            ric, rt = _spearman(f[m], res)
            notes["residual_ic"] = round(ric, 4)
            notes["residual_t"] = round(rt, 2)
            if abs(ic) > 0.05 and abs(ric) < abs(ic) * 0.4:
                flags.append(f"ORTHOGONALITY forward IC {ic:+.4f} collapses to {ric:+.4f} after "
                             f"removing the same-period effect -- the apparent lead was the "
                             f"confound, not the feature")

    # 4 REVERSE CAUSALITY -- does the past return predict the feature better than the reverse?
    if len(f) > 3:
        past_ret = np.roll(r1, 1)
        past_ret[0] = np.nan
        rc, _ = _spearman(past_ret, f)
        notes["reverse_ic"] = round(rc, 4)
        if abs(rc) > abs(ic) * 1.5 and abs(rc) > 0.1:
            flags.append(f"REVERSE_CAUSALITY past return -> feature |rho|={abs(rc):.3f} beats "
                         f"feature -> forward return |rho|={abs(ic):.3f}: the feature is a "
                         f"CONSEQUENCE of the move")

    # 5 SHIFT TEST -- pushing the feature further into the past must not IMPROVE it
    f_lag = np.roll(f, 1)
    f_lag[0] = np.nan
    ic_lag, _ = _spearman(f_lag, r1)
    notes["lagged_ic"] = round(ic_lag, 4)
    if abs(ic) > 0.03 and abs(ic_lag) > abs(ic) * 1.15:
        flags.append(f"SHIFT_TEST lagging the feature one period IMPROVES IC "
                     f"({ic:+.4f} -> {ic_lag:+.4f}) -- alignment is off by one and the live "
                     f"construction is reading information it would not have had")

    # 6 HORIZON ADJACENCY
    if horizons:
        signs = {h: np.sign(v) for h, v in horizons.items() if v is not None}
        notes["horizons"] = {h: round(float(v), 4) for h, v in horizons.items()}
        if len(signs) >= 3 and len(set(signs.values())) > 1:
            agree = max(list(signs.values()).count(s) for s in set(signs.values()))
            if agree < len(signs) - 1:
                flags.append(f"HORIZON_ADJACENCY sign flips across neighbouring horizons "
                             f"({agree}/{len(signs)} agree) -- a real slow signal holds sign")

    # 7 SURVIVORSHIP
    if universe is not None:
        sets = [frozenset(u) for u in universe]
        if len(set(sets)) == 1 and len(sets) > 1:
            flags.append("SURVIVORSHIP the cross-section is IDENTICAL at every date -- symbols "
                         "that delisted or were not yet listed cannot all be present; the "
                         "universe was almost certainly built from an end-of-sample snapshot")
        notes["universe_churn"] = len(set(sets))

    verdict = "CLEAN" if not flags else "LEAK_SUSPECTED"
    return {"name": name, "verdict": verdict, "n": len(f), "flags": flags, "notes": notes}


# ---------------------------------------------------------------- SELF-VALIDATION
def _validate() -> list[dict]:
    """Ground truth by construction. A detector nobody tested is an unverified measurement."""
    rng = np.random.default_rng(7)
    n = 400
    ret = rng.normal(0, 0.01, n)
    fwd = np.roll(ret, -1)
    fwd[-1] = np.nan
    cases = []

    # A: BLATANT LEAK -- feature literally contains the forward return
    leak = fwd + rng.normal(0, 0.002, n)
    cases.append(("A_blatant_leak", audit(leak, fwd, ret, name="A_blatant_leak"), True))

    # B: PURE NOISE -- must NOT be flagged (false-positive test)
    cases.append(("B_pure_noise", audit(rng.normal(0, 1, n), fwd, ret, name="B_pure_noise"), False))

    # C: CONFOUNDED -- feature tracks CURRENT volatility, which persists into next period.
    #    The exact structure that killed the microstructure test. Must be flagged.
    vol = np.abs(ret)
    vol_s = np.convolve(vol, np.ones(5) / 5, mode="same")
    fwd_vol = np.roll(vol_s, -1)
    fwd_vol[-1] = np.nan
    cases.append(("C_vol_confound",
                  audit(vol_s + rng.normal(0, 0.0005, n), fwd_vol, vol_s, name="C_vol_confound"),
                  True))

    # D: GENUINE WEAK SIGNAL -- small, honest, must NOT be flagged
    sig = rng.normal(0, 1, n)
    honest_fwd = 0.05 * sig + rng.normal(0, 1, n)
    cases.append(("D_genuine_weak", audit(sig, honest_fwd, rng.normal(0, 1, n),
                                          name="D_genuine_weak"), False))

    # E: OFF-BY-ONE -- feature accidentally aligned one period late
    good = rng.normal(0, 1, n)
    lag_fwd = 0.30 * np.roll(good, 1) + rng.normal(0, 1, n)
    cases.append(("E_off_by_one", audit(good, lag_fwd, rng.normal(0, 1, n),
                                        name="E_off_by_one"), True))

    out = []
    for label, res, should_flag in cases:
        flagged = res["verdict"] == "LEAK_SUSPECTED"
        out.append({"case": label, "expected_flag": should_flag, "flagged": flagged,
                    "correct": flagged == should_flag, "flags": res["flags"],
                    "notes": res["notes"]})
    return out


def main() -> None:
    print("=== LEAKAGE DETECTOR -- self-validated against known ground truth ===")
    print("    H_OVERFIT is 24 refutations over 45d. The desk's leakage rails were scattered")
    print("    across individual screens; this makes them one importable contract.\n")
    res = _validate()
    ok = sum(r["correct"] for r in res)
    print(f"  {'case':<20}{'expect':>8}{'got':>8}   result")
    for r in res:
        print(f"  {r['case']:<20}{r['expected_flag']!s:>8}{r['flagged']!s:>8}   "
              f"{'PASS' if r['correct'] else 'FAIL'}")
        for f in r["flags"][:2]:
            print(f"      caught: {f[:96]}")
    print(f"\n  SELF-VALIDATION {ok}/{len(res)} correct")
    if ok < len(res):
        print("  DETECTOR IS NOT TRUSTWORTHY -- it must pass every ground-truth case before any")
        print("  result it produces is quoted. Reporting this rather than hiding it.")
    else:
        print("  Catches blatant leakage, vol-confounding and off-by-one alignment; does NOT")
        print("  fire on pure noise or on a genuine weak signal (the false-positive cases).")
    OUT.write_text(json.dumps({"updated": datetime.now(tz=UTC).isoformat(),
                               "self_validation": res, "passed": ok, "total": len(res)}, indent=1),
                   "utf-8")
    print(f"\n  -> {OUT}")
    print("  USE: from leakage_detector import audit; audit(feature, fwd_ret, same_ret, name=...)")


if __name__ == "__main__":
    main()
