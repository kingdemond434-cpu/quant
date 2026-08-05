"""Per-gate accept/reject histogram for the real 420-candidate campaign (GATE-OPTIMALITY DUTY).

Answers the question three audits left open: is 420-tested/0-survivors a dead search space, or a
welded-shut gate? Runs the FULL validate() stack over the reconstructed campaign twice -- once via
the legacy campaign-constant path (what production ran until 2026-07-29) and once via the
per-candidate path (CSCV rank-consistency + Romano-Wolf stepdown) -- and tallies which gate
actually does the rejecting.

Thresholds are never touched here; this measures, it does not decide.
Input: _audit_prepared.pkl (reconstructed campaign, list of (family, subtype, symbol, rets)).
"""

from __future__ import annotations

import collections
import json
import pickle
import sys
import time

import numpy as np

from libs.autodiscovery.models import Family, Hypothesis
from libs.autodiscovery.validation import campaign_gate_stats, campaign_pbo_rc, validate
from libs.validation.dsr import sharpe_ratio
from libs.validation.economic_prior import MechanismType

_PKL = "_audit_prepared.pkl"
# The reconstructed campaign is the lab's own D1 crypto run (crypto_adapter defaults to D1 and
# perps trade 24/7), so 365 bars a year. The histogram this script writes was measured while
# validate() annualised the same series at 6240/yr -- the R0086 inflation. Gate verdicts are
# unaffected (no gate reads annual_sharpe); the reported metric is.
_PPY = 365.0


def _log(msg: str) -> None:
    print(msg, flush=True)


def _hyp(fam: str, sub: str, sym: str) -> Hypothesis:
    """Reconstruct a hypothesis shell. failure_modes is non-empty so the economic_mechanism gate
    reflects the REAL campaign (every generated hypothesis declares failure modes before testing);
    leaving it empty would make that gate a second constant veto and hide the statistical gates."""
    try:
        family = Family(fam)
    except ValueError:
        family = Family.CARRY
    return Hypothesis(
        family=family, subtype=sub, symbol=sym, params={},
        mechanism=MechanismType.RISK_PREMIUM,
        edge_source=f"{fam}/{sub}", failure_modes=["reconstructed-for-gate-measurement"],
    )


def main() -> int:
    t0 = time.time()
    with open(_PKL, "rb") as fh:
        prepared = pickle.load(fh)  # noqa: S301 -- pickle of a corpus this desk wrote itself; never an untrusted input
    _log(f"loaded {len(prepared)} candidates from {_PKL}")

    lens = np.array([len(e[-1]) for e in prepared])
    min_len = int(lens.min())
    matrix = np.column_stack([e[-1][-min_len:] for e in prepared])
    _log(f"matrix {matrix.shape}  (min_len={min_len}, median_len={int(np.median(lens))}, "
         f"max_len={int(lens.max())}, retained_obs={matrix.size} of {int(lens.sum())})")

    sharpe_estimates = np.array([sharpe_ratio(e[-1]) for e in prepared], dtype="float64")
    fam_counts = collections.Counter(e[0] for e in prepared)
    fam_sharpes = {
        f: np.array([sharpe_ratio(e[-1]) for e in prepared if e[0] == f], dtype="float64")
        for f in fam_counts
    }

    t = time.time()
    legacy_pbo, legacy_rc = campaign_pbo_rc(matrix)
    assert legacy_pbo is not None and legacy_rc is not None
    _log(f"LEGACY campaign constants [{time.time() - t:.1f}s]: "
         f"pbo={legacy_pbo.pbo:.4f} overfit={legacy_pbo.overfit} -> pbo_gate_passes="
         f"{not legacy_pbo.overfit} for ALL {matrix.shape[1]}; "
         f"rc_p={legacy_rc.p_value:.4f} sig={legacy_rc.significant_at_5pct} -> "
         f"reality_check_passes={legacy_rc.significant_at_5pct} for ALL {matrix.shape[1]}")

    t = time.time()
    gates = campaign_gate_stats(matrix)
    assert gates is not None
    cp = np.array(gates.cscv.candidate_pbo)
    rej = np.array(gates.stepdown.rejected)
    adj = np.array(gates.stepdown.adjusted_p)
    _log(f"PER-CANDIDATE stats [{time.time() - t:.1f}s]: "
         f"cscv pbo<=0.5 for {int((cp <= 0.5).sum())}/{len(cp)} "
         f"(min={cp.min():.3f} med={np.median(cp):.3f}); "
         f"romano-wolf rejected {int(rej.sum())}/{len(rej)} (min adj_p={adj.min():.4f}); "
         f"BOTH: {int(((cp <= 0.5) & rej).sum())}")

    report: dict[str, object] = {
        "generated_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "n_candidates": len(prepared),
        "matrix_shape": list(matrix.shape),
        "obs_retained": int(matrix.size),
        "obs_available": int(lens.sum()),
        "legacy": {
            "pbo": legacy_pbo.pbo, "pbo_gate_passes_all": not legacy_pbo.overfit,
            "rc_p": legacy_rc.p_value, "rc_gate_passes_all": legacy_rc.significant_at_5pct,
        },
        "per_candidate": {
            "cscv_pbo_ok": int((cp <= 0.5).sum()),
            "rw_rejected": int(rej.sum()),
            "both": int(((cp <= 0.5) & rej).sum()),
            "min_adj_p": float(adj.min()),
        },
    }

    for label, kwargs_fn in (
        ("legacy", lambda i: {"pbo": legacy_pbo, "rc": legacy_rc}),
        ("per_candidate", lambda i: {"campaign": gates, "column": i}),
    ):
        tally: collections.Counter[str] = collections.Counter()
        fail_tally: collections.Counter[str] = collections.Counter()
        seen: collections.Counter[str] = collections.Counter()
        survivors: list[str] = []
        n_fail_only: collections.Counter[str] = collections.Counter()
        t = time.time()
        for i, (fam, sub, sym, rets) in enumerate(prepared):
            _sh = fam_sharpes.get(fam)
            if _sh is None or len(_sh) < 2:
                _sh = sharpe_estimates
            v = validate(
                rets, hypothesis=_hyp(fam, sub, sym), periods_per_year=_PPY,
                n_trials=fam_counts[fam], sharpe_estimates=_sh,
                returns_matrix=matrix, **kwargs_fn(i),
            )
            # BOTH OUTCOMES ARE TALLIED. Counting only passes made a gate at 0/420 byte-for-byte
            # indistinguishable from a gate that is NOT IN THE CODE -- both simply absent from
            # pass_counts. That ambiguity is not cosmetic on the desk's only gate-optimality
            # artifact: it is exactly how `dsr` vetoing every single candidate and
            # `beats_baselines` not yet existing both read as "not there". A gate rejecting 100%
            # of candidates is the loudest possible finding and it was rendering as silence.
            for name, ok in v.gates.items():
                tally[name] += int(bool(ok))
                seen[name] += 1
                if not ok:
                    fail_tally[name] += 1
            failed = [n for n, ok in v.gates.items() if not ok]
            if not failed:
                survivors.append(f"{fam}/{sub}/{sym}")
            elif len(failed) == 1:
                n_fail_only[failed[0]] += 1
            if (i + 1) % 100 == 0:
                _log(f"  [{label}] {i + 1}/{len(prepared)} ({time.time() - t:.0f}s)")

        n = len(prepared)
        _log(f"--- {label.upper()} per-gate PASS counts (of {n}) [{time.time() - t:.0f}s] ---")
        for name, cnt in sorted(tally.items(), key=lambda kv: kv[1]):
            _log(f"    {name:20s} {cnt:4d}/{n}  ({100.0 * cnt / n:5.1f}%)")
        _log(f"    SURVIVORS: {len(survivors)}")
        if survivors:
            for s in survivors[:20]:
                _log(f"      + {s}")
        if n_fail_only:
            _log(f"    SOLE blocker (candidate failed exactly ONE gate): {dict(n_fail_only)}")
        report[f"histogram_{label}"] = {
            "pass_counts": dict(tally), "fail_counts": dict(fail_tally),
            "gates_evaluated": dict(seen),
            # A gate present in `gates_evaluated` with pass_counts 0 is a TOTAL VETO; a gate
            # missing from `gates_evaluated` entirely is not in the code. Recording both makes
            # those two states distinguishable, which they were not.
            "total_vetoes": sorted(g for g in seen if tally.get(g, 0) == 0),
            "survivors": survivors, "sole_blocker": dict(n_fail_only),
        }

    out = "reports/gate_histogram.json"
    with open(out, "w") as fh:
        json.dump(report, fh, indent=2)
    _log(f"wrote {out}  [total {time.time() - t0:.0f}s]")
    return 0


if __name__ == "__main__":
    sys.exit(main())
