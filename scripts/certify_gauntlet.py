"""Certify the real gauntlet with known-GOOD / known-NULL controls (R0017).

Answers the question 434-tested/0-promoted cannot answer on its own: **can this funnel admit a
genuinely good candidate at all, and does it still reject noise?** Until that is answered, "0
survivors" is uninterpretable -- it is equally consistent with picked-clean price space and with a
gate welded shut, and the desk has been reasoning from the first reading without evidence for it.

Controls come from ``libs.validation.positive_control``, which pins a control's SAMPLE Sharpe by
construction. That matters more than it sounds: at T=310 the standard error of an annualised Sharpe
is 1.085, so the previous probe's fixed-seed "true SR +0.5" candidate actually realised -2.32 and
every gate rejected it correctly. See that module's docstring.

CONTROLLED A/B, and it is controlled on purpose. ``campaign_gate_stats`` returns the legacy campaign
constants (``legacy_pbo``/``legacy_rc``) alongside the per-candidate statistics, so ONE pass over the
injected matrix scores both the welded path and the per-candidate path for the SAME candidate on the
SAME window. The 2026-07-30 migration attempt was reverted partly because its before/after windows
differed and the deltas could not be attributed; this design removes that objection.

Writes reports/gauntlet_certification.json. Read-only with respect to every DB, ledger, and gate:
this script measures, it never promotes.

    .venv/bin/python scripts/certify_gauntlet.py [--seeds 3] [--targets 2,3,5,7,10,15]
"""

from __future__ import annotations

import argparse
import json
import pickle
import time
from pathlib import Path
from typing import Any

import numpy as np

from libs.autodiscovery.models import Family, Hypothesis
from libs.autodiscovery.validation import campaign_gate_stats, validate
from libs.validation.dsr import sharpe_ratio
from libs.validation.economic_prior import MechanismType
from libs.validation.positive_control import PPY, exact_sharpe_series

_PREPARED = Path("_audit_prepared.pkl")
_OUT = Path("reports/gauntlet_certification.json")
_FAMILY_TRIAL_BUDGET = 120
_HYP = Hypothesis(
    family=Family.LIQUIDITY, subtype="control", symbol="BTCUSDT", params={},
    mechanism=MechanismType.LIQUIDITY, edge_source="synthetic control",
    failure_modes=["synthetic control -- never tradeable"],
)


class CampaignUnavailable(RuntimeError):
    """The campaign pickle is absent. Raised so the caller can record a BLOCKER, not a traceback."""


def _load_campaign() -> tuple[np.ndarray, np.ndarray, int]:
    """The reconstructed 420-candidate campaign the 0-survivor result was measured on.

    `_audit_prepared.pkl` is a gitignored 6MB scratch artifact with THREE READERS (this script,
    measure_gate_histogram.py, measure_matrix_window.py) and NO WRITER anywhere in the repo -- it
    was produced once by hand during the 2026-07-29 audit and never committed or regenerated.

    So this script, scheduled daily, has been dying on a bare FileNotFoundError every run, and
    reports/gauntlet_certification.json has never existed. The consequence is not cosmetic:
    libs/validation/positive_control.py is the instrument that distinguishes "price space is
    genuinely picked clean" from "the gate is welded shut", and until it produces an artifact the
    desk cannot tell those apart -- which is the single question the 420-tested/0-survivors record
    turns on. It is also why GAP_REGISTER R0040 and R0041 are both still gated.

    Raising a NAMED exception rather than crashing means the daily run leaves EVIDENCE of why it
    could not certify, in the artifact the max-push queue reads, instead of a stack trace at the
    bottom of a log nobody opens.
    """
    if not _PREPARED.exists():
        raise CampaignUnavailable(
            f"{_PREPARED} is absent and NOTHING in this repo generates it (3 readers, 0 writers). "
            "It was reconstructed by hand for the 2026-07-29 audit and never committed. Until it "
            "is regenerated or _load_campaign() is given a fallback, the positive control cannot "
            "run and 'welded gate' vs 'empty space' stays undecidable.")
    prepared = pickle.loads(_PREPARED.read_bytes())
    min_len = min(len(r) for *_x, r in prepared)
    matrix = np.column_stack([r[-min_len:] for *_x, r in prepared])
    sharpes = np.array([sharpe_ratio(r) for *_x, r in prepared])
    return matrix, sharpes, min_len


def _score(rets: np.ndarray, matrix: np.ndarray,
           peer_sharpes: np.ndarray) -> dict[str, Any]:
    """Inject ``rets`` as a new campaign column and score it on BOTH gate paths."""
    m = np.column_stack([matrix, rets])
    gates = campaign_gate_stats(m)
    if gates is None:
        raise RuntimeError("campaign_gate_stats returned None on a >=2-column matrix")
    col = m.shape[1] - 1
    sh = np.append(peer_sharpes, sharpe_ratio(rets))
    n_trials = max(_FAMILY_TRIAL_BUDGET, m.shape[1])

    common = {
        "hypothesis": _HYP, "n_trials": n_trials, "sharpe_estimates": sh, "returns_matrix": m,
    }
    legacy = validate(rets, pbo=gates.legacy_pbo, rc=gates.legacy_rc, **common)
    percand = validate(rets, campaign=gates, column=col, **common)

    def _v(res: Any) -> dict[str, Any]:
        return {
            "survived": bool(res.survived),
            "failed": [g for g, ok in res.gates.items() if not ok],
            "dsr": float(res.metrics.dsr), "pbo": float(res.metrics.pbo),
            "reality_p": float(res.metrics.reality_p),
            "oos_sharpe": float(res.metrics.oos_sharpe),
        }

    return {"legacy": _v(legacy), "per_candidate": _v(percand)}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--seeds", type=int, default=3)
    ap.add_argument("--targets", default="2,3,5,7,10,15")
    ap.add_argument("--seed0", type=int, default=1000)
    args = ap.parse_args()
    targets = [float(t) for t in args.targets.split(",")]

    try:
        matrix, peer_sharpes, n_obs = _load_campaign()
    except CampaignUnavailable as exc:
        # RECORD THE BLOCKER, do not crash. A daily organ that dies on a traceback produces
        # nothing an audit can read, so the gap stays invisible for as long as nobody opens the
        # log -- which for this script was every day since it was scheduled. Writing the artifact
        # with status BLOCKED means check_organs sees a fresh file, run_max_push sees a named
        # blocker, and the reason is one grep away instead of one archaeology session away.
        _OUT.parent.mkdir(parents=True, exist_ok=True)
        _OUT.write_text(json.dumps({
            "generated_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "status": "BLOCKED",
            "blocker": str(exc),
            "consequence": "The positive control has never run, so the desk cannot distinguish a "
                           "genuinely picked-clean price space from a welded-shut gate. "
                           "GAP_REGISTER R0040 and R0041 both depend on this answer.",
            "resolution": "Commit a builder for _audit_prepared.pkl, or give _load_campaign() a "
                          "fallback to positive_control.null_cohort at the shape recorded in "
                          "reports/gate_histogram.json.",
            "rows": [],
        }, indent=2), "utf-8")
        print(f"BLOCKED: {exc}")
        print(f"-> {_OUT} (status BLOCKED -- the blocker is now an artifact, not a traceback)")
        return 1
    se = float(np.sqrt(PPY / n_obs))
    print(f"campaign: T={n_obs} N={matrix.shape[1]}  SE(annual Sharpe)={se:.3f}")
    print("controls have their target SAMPLE Sharpe by construction (sampling error removed)\n")

    rows: list[dict[str, Any]] = []
    # target 0.0 is the NULL control -- the other half of certification.
    for target in [*targets, 0.0]:
        for k in range(args.seeds):
            rng = np.random.default_rng(args.seed0 + (500_000 if target == 0.0 else 0) + k)
            rets = exact_sharpe_series(target, n_obs, rng=rng)
            realised = float(sharpe_ratio(rets) * np.sqrt(PPY))
            t0 = time.time()
            scored = _score(rets, matrix, peer_sharpes)
            rows.append({"target": target, "seed": k, "realised_ann_sharpe": realised, **scored})
            # CHECKPOINT EVERY ROW (R0052): each row is ~50s of Romano-Wolf bootstrap on a
            # 2-core box, and the full run does not comfortably fit one wall-clock window --
            # a timeout or kill used to discard the WHOLE run (R0017 was disposed
            # 'implemented' against an artifact of 0 bytes). Every row is independently
            # meaningful, so a partial file with status RUNNING beats a perfect file that
            # never exists.
            _OUT.parent.mkdir(parents=True, exist_ok=True)
            _OUT.write_text(json.dumps({
                "generated": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                "status": "RUNNING",
                "rows_done": len(rows),
                "rows_planned": (len(targets) + 1) * args.seeds,
                "campaign": {"T": n_obs, "N": matrix.shape[1], "se_annual_sharpe": se},
                "rows": rows,
            }, indent=2), "utf-8")
            lg, pc = scored["legacy"], scored["per_candidate"]
            print(
                f"SR_true={target:5.1f} seed={k} realised={realised:6.2f} "
                f"[{time.time() - t0:5.1f}s]  "
                f"legacy={'PASS' if lg['survived'] else 'FAIL:' + ','.join(lg['failed'])}  "
                f"percand={'PASS' if pc['survived'] else 'FAIL:' + ','.join(pc['failed'])}"
            )

    def _summary(path: str) -> dict[str, Any]:
        good = [r for r in rows if r["target"] > 0.0]
        nulls = [r for r in rows if r["target"] == 0.0]
        by_t = {
            f"{t:g}": float(np.mean([r[path]["survived"] for r in good if r["target"] == t]))
            for t in targets
        }
        passing = [t for t in targets if by_t[f"{t:g}"] > 0.0]
        sole: dict[str, int] = {}
        for r in good:
            failed = r[path]["failed"]
            if not r[path]["survived"] and len(failed) == 1:
                sole[failed[0]] = sole.get(failed[0], 0) + 1
        blocked_all: dict[str, int] = {}
        for r in good:
            for g in r[path]["failed"]:
                blocked_all[g] = blocked_all.get(g, 0) + 1
        return {
            "pass_rate_by_true_sharpe": by_t,
            "min_passing_true_sharpe": (min(passing) if passing else None),
            "null_false_pass_rate": (
                float(np.mean([r[path]["survived"] for r in nulls])) if nulls else 0.0
            ),
            "sole_blocking_gate_counts": sole,
            "all_blocking_gate_counts": blocked_all,
            "certified_admits_good": bool(passing),
        }

    out: dict[str, Any] = {
        "generated": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "status": "COMPLETE",          # RUNNING checkpoints carry partial rows; only this is final
        "campaign": {"T": n_obs, "N": matrix.shape[1], "se_annual_sharpe": se},
        "controls": {"targets": targets, "seeds": args.seeds,
                     "construction": "exact sample Sharpe (libs.validation.positive_control)"},
        "legacy_welded_path": _summary("legacy"),
        "per_candidate_path": _summary("per_candidate"),
        "rows": rows,
    }
    _OUT.parent.mkdir(parents=True, exist_ok=True)
    _OUT.write_text(json.dumps(out, indent=2))

    print("\n" + "=" * 78)
    for name in ("legacy_welded_path", "per_candidate_path"):
        s = out[name]
        print(f"{name}: min passing true SR = {s['min_passing_true_sharpe']}  "
              f"null FPR = {s['null_false_pass_rate']:.0%}  "
              f"sole blockers = {s['sole_blocking_gate_counts']}")
    print(f"wrote {_OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
