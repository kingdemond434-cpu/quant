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
import sys
import time
from pathlib import Path
from typing import Any

_ROOT = Path("/home/quant/quant-platform")
if not _ROOT.exists():
    _ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    # WITHOUT THIS the script dies on `ModuleNotFoundError: No module named 'libs'` when invoked
    # as `python scripts/certify_gauntlet.py` -- which is exactly how its manifest line calls it.
    # It only ever ran under `python -m`, so the daily organ produced a bare traceback and the
    # BLOCKED artifact it was carefully written to emit never got written either. Every other
    # organ on the desk carries this preamble; this one was missing it.
    sys.path.insert(0, str(_ROOT))

import numpy as np  # noqa: E402
from scipy.stats import norm as _norm  # noqa: E402

from libs.autodiscovery.models import Family, Hypothesis  # noqa: E402
from libs.autodiscovery.validation import (  # noqa: E402
    _DSR_THRESHOLD,
    campaign_gate_stats,
    validate,
)
from libs.validation.dsr import expected_max_sharpe, sharpe_ratio  # noqa: E402
from libs.validation.economic_prior import MechanismType  # noqa: E402
from libs.validation.positive_control import PPY, exact_sharpe_series, null_cohort  # noqa: E402

_PREPARED = Path("_audit_prepared.pkl")
#: The campaign SHAPE, committed, so a synthetic cohort can stand in at the right dimensions.
_HIST = Path("reports/gate_histogram.json")
#: Fixed seed for the SYNTHETIC peer cohort -- the peers must be identical across runs or the
#: certification moves for reasons that have nothing to do with the gate. The INJECTED controls
#: still vary their seed per row (--seeds/--seed0): R0017 closed on exactly that defect, a
#: reused seed=7 across all 13 sweep rows reading as signal when it was one draw repeated.
_SYNTH_SEED = 20260731
_OUT = Path("reports/gauntlet_certification.json")
_FAMILY_TRIAL_BUDGET = 120
_HYP = Hypothesis(
    family=Family.LIQUIDITY, subtype="control", symbol="BTCUSDT", params={},
    mechanism=MechanismType.LIQUIDITY, edge_source="synthetic control",
    failure_modes=["synthetic control -- never tradeable"],
)


class CampaignUnavailable(RuntimeError):
    """The campaign pickle is absent. Raised so the caller can record a BLOCKER, not a traceback."""


def _load_campaign() -> tuple[np.ndarray, np.ndarray, int, str]:
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
    if _PREPARED.exists():
        prepared = pickle.loads(_PREPARED.read_bytes())
        min_len = min(len(r) for *_x, r in prepared)
        matrix = np.column_stack([r[-min_len:] for *_x, r in prepared])
        sharpes = np.array([sharpe_ratio(r) for *_x, r in prepared])
        return matrix, sharpes, min_len, "CAMPAIGN"

    # FALLBACK: a SYNTHETIC null cohort at the campaign's RECORDED shape -- the resolution this
    # script named for itself, now taken. It splits the question the certifier was asked into the
    # half that is answerable without the pickle and the half that is not, and the split is the
    # whole point of doing it this way rather than waiting:
    #
    #   ANSWERABLE ON SYNTHETIC PEERS -- "can this gate stack EVER pass a genuinely good
    #   candidate?" That is a property of the GATE MACHINERY, not of the desk's price space. If
    #   an injected true Sharpe of 10 cannot survive against 420 zero-edge peers, the gate is
    #   welded shut and no amount of real data would have shown it more clearly.
    #
    #   NOT ANSWERABLE -- "is the desk's real 420-candidate campaign's 0-survivor result
    #   informative, or an artifact of its peers?" That needs the REAL peers, because PBO and the
    #   reality check are both computed AGAINST the cohort. A synthetic cohort answers a
    #   different question and must never be reported as if it answered this one.
    #
    # So the run is labelled SYNTHETIC end to end and the artifact says which question it settled.
    shape = json.loads(_HIST.read_text("utf-8"))["matrix_shape"] if _HIST.exists() else None
    if not shape:
        raise CampaignUnavailable(
            f"{_PREPARED} is absent (3 readers, 0 writers) AND {_HIST} carries no matrix_shape, "
            "so not even a synthetic cohort can be built at the campaign's dimensions. Commit a "
            "builder for the pickle, or restore the histogram.")
    n_obs, n_cand = int(shape[0]), int(shape[1])
    rng = np.random.default_rng(_SYNTH_SEED)
    matrix = null_cohort(n_cand, n_obs, rng=rng)
    sharpes = np.array([sharpe_ratio(matrix[:, i]) for i in range(n_cand)])
    return matrix, sharpes, n_obs, "SYNTHETIC"


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


#: Campaign shapes to price. Rows are observation counts, columns candidate counts -- the two
#: knobs the desk actually controls when it designs a sweep.
_DESIGN_T = (310, 620, 1250, 2500)
_DESIGN_N = (420, 100, 30, 10, 5)
#: True annualised Sharpes worth asking about. A world-class systematic book runs 2-3; anything
#: at 5+ is a once-a-decade find, so a gate that only resolves above 5 resolves nothing real.
_TRUE_SR_GRID = (1.0, 1.5, 2.0, 2.5, 3.0, 4.0, 5.0, 6.0)


def dsr_hurdle_annual(n_trials: int, n_obs: int, *, var_sharpes: float | None = None) -> float:
    """The observed ANNUALISED Sharpe a candidate must post to clear the DSR gate.

    Derived from the desk's OWN primitives rather than restated, so the number moves if the gate
    moves: ``expected_max_sharpe`` supplies the multiplicity deflator and ``_DSR_THRESHOLD`` the
    tolerance. Inlining either as a literal would let the table drift silently away from the gate
    it claims to describe, which is the whole failure mode this script exists to catch.

    ``var_sharpes`` defaults to the NULL dispersion 1/T -- the variance of sample Sharpes across
    zero-edge candidates. That makes the result a FLOOR: a real cohort disperses more than noise,
    ``expected_max_sharpe`` scales linearly in that dispersion, so the live hurdle is higher than
    this, never lower. Reporting the floor keeps the verdict conservative in the safe direction.
    """
    sr0 = expected_max_sharpe(n_trials, (1.0 / n_obs) if var_sharpes is None else var_sharpes)
    # dsr >= threshold  <=>  z >= Phi^-1(threshold), and z = (sr - sr0)*sqrt(T-1)/sqrt(denom)
    # with denom -> 1 for near-normal returns. Solve for sr, then annualise.
    z = float(_norm.ppf(_DSR_THRESHOLD))
    return float((sr0 + z / np.sqrt(max(1, n_obs - 1))) * np.sqrt(PPY))


def design_power(n_trials: int, n_obs: int) -> dict[str, Any]:
    """Why 0-of-420 is uninformative, priced instead of argued.

    The certification above answers "can a true edge pass"; the honest follow-up is "how big must
    it be", and that is arithmetic on the campaign's SHAPE, not on its thresholds. Two knobs set
    it: N widens the multiplicity deflator (E[max of N nulls]) and T shrinks the standard error
    (SE = sqrt(PPY/T)). Their product IS the hurdle.

    This matters because the two available responses to "nothing survived" are not equally
    legitimate. Lowering a threshold manufactures survivors and is forbidden. Re-shaping the
    experiment -- fewer, mechanism-motivated candidates over longer history -- buys the same
    resolution while every threshold stays exactly where it is. The table prices that trade so
    the choice is made on numbers.
    """
    se = float(np.sqrt(PPY / n_obs))
    hurdle = dsr_hurdle_annual(n_trials, n_obs)
    power = {f"{s:g}": float(1.0 - _norm.cdf((hurdle - s) / se)) for s in _TRUE_SR_GRID}
    # The largest true Sharpe the campaign still cannot find half the time. If this sits above
    # what real strategies achieve, a null result carries no information about the price space.
    blind_to = [s for s in _TRUE_SR_GRID if power[f"{s:g}"] < 0.5]
    return {
        "dsr_threshold": _DSR_THRESHOLD,
        "n_trials": n_trials,
        "n_obs": n_obs,
        "se_annual_sharpe": se,
        "hurdle_annual_sharpe": hurdle,
        "hurdle_is_a_floor": "null dispersion assumed; a real cohort disperses more, so the live "
                             "hurdle is >= this, never below it",
        "power_by_true_annual_sharpe": power,
        "underpowered_below_annual_sharpe": (max(blind_to) if blind_to else None),
        # N enters DIRECTLY here, with no floor, because that is what a redesigned campaign would
        # actually face: production callers pass the real candidate count (run_discovery
        # n_trials=len(lib), run_crypto_portfolio matrix.shape[1], orchestrator per-family counts).
        # The first draft of this table applied THIS SCRIPT's _FAMILY_TRIAL_BUDGET floor of 120 to
        # every cell, which collapsed N=100/30/10/5 to one number and said -- falsely -- that
        # narrowing a campaign below 120 buys nothing. The floor is the certifier's scoring
        # assumption, not the gate's; conflating the two would have argued the desk out of the one
        # lever that works.
        "alternative_shapes": {
            f"T={t}": {f"N={n}": dsr_hurdle_annual(n, t) for n in _DESIGN_N} for t in _DESIGN_T
        },
        "certifier_trial_floor": _FAMILY_TRIAL_BUDGET,
        "reading": ("Hurdle is set by campaign SHAPE, not by the 0.95 tolerance. Cutting N and "
                    "raising T lowers it without relaxing a single gate; lowering the tolerance "
                    "would manufacture survivors and is not on the table."),
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--seeds", type=int, default=3)
    ap.add_argument("--targets", default="2,3,5,7,10,15")
    ap.add_argument("--seed0", type=int, default=1000)
    args = ap.parse_args()
    targets = [float(t) for t in args.targets.split(",")]

    try:
        matrix, peer_sharpes, n_obs, provenance = _load_campaign()
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
    print(f"campaign: T={n_obs} N={matrix.shape[1]}  SE(annual Sharpe)={se:.3f}  "
          f"peers={provenance}")
    if provenance == "SYNTHETIC":
        print("PEERS ARE SYNTHETIC -- this run certifies the GATE MACHINERY (can a true edge "
              "pass?), NOT whether the desk's real 0/420 result is informative. Different "
              "questions; only the first is answerable without _audit_prepared.pkl.")
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
                "campaign": {"T": n_obs, "N": matrix.shape[1], "se_annual_sharpe": se,
                             "peers": provenance},
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
        # COMPLETE-SYNTHETIC is deliberately a DIFFERENT status, not a footnote on COMPLETE. A
        # reader scanning for "COMPLETE" must not pick up a run whose peers were manufactured and
        # conclude the desk's real 0/420 campaign has been vindicated -- it answers the gate
        # question, not the price-space question, and the two get confused precisely because the
        # numbers look identical.
        "status": "COMPLETE" if provenance == "CAMPAIGN" else "COMPLETE-SYNTHETIC",
        "peers": provenance,
        "answers": ("both: can the gate pass a true edge, AND is the real 0/420 informative"
                    if provenance == "CAMPAIGN" else
                    "ONLY: can the gate stack pass a genuinely good candidate at all. The peers "
                    "here are manufactured zero-edge draws at the campaign's recorded shape, so "
                    "PBO and the reality check -- both computed AGAINST the cohort -- say nothing "
                    "about whether the desk's real price space is picked clean. That half stays "
                    "blocked on a builder for _audit_prepared.pkl (3 readers, 0 writers)."),
        "campaign": {"T": n_obs, "N": matrix.shape[1], "se_annual_sharpe": se,
                     "peers": provenance},
        "controls": {"targets": targets, "seeds": args.seeds,
                     "construction": "exact sample Sharpe (libs.validation.positive_control)"},
        # The other half of "can a true edge pass": HOW BIG must it be. Purely analytic, so it is
        # correct even on the rows this run did not sweep -- and it is what turns "0 of 420" from
        # a claim about the price space into a claim about the campaign's resolution.
        "design": design_power(max(_FAMILY_TRIAL_BUDGET, matrix.shape[1] + 1), n_obs),
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
