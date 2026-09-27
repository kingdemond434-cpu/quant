"""Single immutable authority for MT5 shadow admission.

Discovery screens and batteries may rank or diagnose candidates, but only an
exact pass of this original ten-gate policy can admit a sleeve to shadow.

GATE DEFINITIONS ARE LOADED FROM desks/mt5/policy/gate_spec.yaml
This file is the single source of truth for gate definitions, thresholds, and classifications.
"""
from __future__ import annotations

import math
import re
from pathlib import Path
from typing import Any

import yaml

BASE = Path(__file__).resolve().parent.parent
SPEC_PATH = BASE / "policy" / "gate_spec.yaml"


def _load_spec() -> dict:
    """Load gate specification from YAML."""
    with open(SPEC_PATH, encoding="utf-8") as f:
        return yaml.safe_load(f)


_SPEC = _load_spec()

VERSION = _SPEC["version"]
#: Fixed multiple-testing charge, read from the spec so the number lives in policy, not code.
_SPEC_FIXED_TRIALS = next(
    (g.get("params", {}).get("fixed_trial_count")
     for g in _SPEC.get("gates", []) if g.get("name") == "deflated_sharpe"), None)
#: The OTHER input to the deflated-Sharpe hurdle. Pinned for the same reason as the trial count:
#: a candidate must not face a higher bar for having been scheduled into a wider sweep.
FIXED_VARIANCE_OF_SHARPES = next(
    (g.get("params", {}).get("fixed_variance_of_sharpes")
     for g in _SPEC.get("gates", []) if g.get("name") == "deflated_sharpe"), None)
DONE_MARKER = "DONE_qquant_gates_original10_v2"
GATES = tuple(g["name"] for g in _SPEC["gates"])

# Extract thresholds from spec
_PARAMS = {g["name"]: g.get("params", {}) for g in _SPEC["gates"]}
THRESHOLDS = {g["name"]: g.get("threshold", "") for g in _SPEC["gates"]}

TRIALS_MULTIPLIER = _SPEC["gates"][2]["params"].get("trials_multiplier", 7.0)  # deflated_sharpe
DSR_THRESHOLD = 0.95
PBO_THRESHOLD = 0.5
SPA_ALPHA = 0.05
WF_SPLITS = 4
WF_MIN_STABILITY = 0.5
COST_SCENARIO = 3.0

REGIME_ADMISSION_UNIT = (
    "strategy x instrument x side x horizon/session x preregistered point-in-time regime"
)
REGIME_CONTROL = (
    "regime frozen before OOS; unconditional arm is a separately counted control; "
    "unknown or incompatible live regime is OFF"
)
# THE BAR IS FIXED. It never raises, and it never gets harsher (principal, standing instruction,
# stated three times). A candidate is judged against a constant campaign charge, not against the
# accident of how many other cells shared its sweep: sr0 was 0.3786 at 597 charged trials and
# 1.3593 at 5,963, same gate, same policy, same cell, purely because the docket grew that hour.
#
# The attestation MUST describe what was actually applied. Leaving the old formula here while the
# charge became constant would keep every existing certificate matching -- and make each one
# attest to a basis it was not judged under, which is the one thing this field exists to prevent.
# Re-stamping costs a window: certificates carry the OLD attestation until a sweep rewrites them,
# and is_exact_policy is an exact dict match, so admission sees nothing until then. The gauntlet
# republishes with the current attestation every sweep, and sweeps now finish in ~20 minutes.
#
# AND IT IS READ FROM THE SPEC, NOT RETYPED HERE (2026-09-23). `research/effective_trials.py`
# corrects the campaign charge for MEASURED redundancy -- thirty-one tunings of one rule on one
# instrument at one horizon are one independent test, not thirty-one -- and it does so by writing
# `fixed_trial_count` and `trial_count_basis` into `policy/gate_spec.yaml`, the one input the
# SEALED gauntlet reads for this number. If the description stayed a literal here it would go on
# saying 597 while the judge charged something else, and every certificate would attest to a basis
# it was not judged under: exactly the failure the comment above says this field exists to
# prevent. So the string follows the spec, and the literal it used to be is carried in the
# superseded list below -- admissible there only because the correction lowers the charge, which
# makes the old bar the HARDER one.
_LEGACY_TRIAL_COUNT_BASIS = (
    "fixed_campaign_trials(597) + fixed_variance_of_sharpes(0.014863): BOTH inputs to the "
    "deflated-Sharpe hurdle are constants, so the bar is identical for every cell regardless of "
    "how many others share its sweep or how dispersed their Sharpes are"
)
_SPEC_TRIAL_COUNT_BASIS = next(
    (g.get("params", {}).get("trial_count_basis")
     for g in _SPEC.get("gates", []) if g.get("name") == "deflated_sharpe"), None)
TRIAL_COUNT_BASIS = (_SPEC_TRIAL_COUNT_BASIS
                     if isinstance(_SPEC_TRIAL_COUNT_BASIS, str) and _SPEC_TRIAL_COUNT_BASIS
                     else _LEGACY_TRIAL_COUNT_BASIS)

ATTESTATION = {
    "version": VERSION,
    "gates": list(GATES),
    "trials_multiplier": TRIALS_MULTIPLIER,
    "trial_count_basis": TRIAL_COUNT_BASIS,
    "dsr_threshold": DSR_THRESHOLD,
    "pbo_max": PBO_THRESHOLD,
    "spa_alpha": SPA_ALPHA,
    "wf_splits": WF_SPLITS,
    "wf_test_size": "max(20,len//6)",
    "wf_min_oos_sharpe": 0.0,
    "wf_min_stability": WF_MIN_STABILITY,
    "cost_multiplier": COST_SCENARIO,
    "regime_admission_unit": REGIME_ADMISSION_UNIT,
    "regime_control": REGIME_CONTROL,
    "cpcv_mean_oos_sharpe_min_exclusive": 0.0,
    "lockbox_oos_sharpe_min": 0.0,
    "expected_value_min_exclusive": 0.0,
}


#: Trial-count bases this desk has certified under, superseded by the move to a fixed campaign
#: count. THE ONLY REASON THIS LIST MAY EXIST is that the change made the bar strictly LOOSER:
#: `ceil(effective_cells * 7)` charged ~65,000 trials on a 9,333-cell sweep, against today's
#: fixed 597. sr0 grows with sqrt(2 ln N), so a certificate minted under the old basis cleared a
#: deflated-Sharpe hurdle far ABOVE the one the current policy asks for.
#:
#: NOTHING WEAKER MAY BE ADDED HERE. An entry is admissible only when the superseded basis can be
#: shown to have charged at least as many trials as the current one, for every cell it certified.
#: If a future policy change TIGHTENS the bar, the old certificates are genuinely under-qualified
#: and must be re-run -- that is a re-certification, not a list entry.
_SUPERSEDED_TRIAL_BASES: tuple[str, ...] = (
    "ceil(null_calibrated_participation_ratio_effective_cells * 7); fail closed to "
    "ceil(raw_cells * 7) when dependence is unmeasurable",
)
# THE FIXED-597 BASIS JOINS THAT LIST ONLY WHILE THE SPEC CHARGES 597 OR FEWER. The admissibility
# rule above is not a formality: an entry may exist only when the superseded basis charged AT
# LEAST as many trials as the current one, so a certificate minted under it cleared a hurdle at
# least as high. `sr0` grows with sqrt(2 ln N), so 597 >= the current charge is exactly that
# condition, and it is evaluated against the spec rather than assumed. If a future policy ever
# raises the charge ABOVE 597, this entry disappears by itself and those certificates are
# correctly treated as under-qualified -- a re-certification, not a list entry.
if isinstance(_SPEC_FIXED_TRIALS, int) and 2 <= _SPEC_FIXED_TRIALS <= 597:
    _SUPERSEDED_TRIAL_BASES = (*_SUPERSEDED_TRIAL_BASES, _LEGACY_TRIAL_COUNT_BASIS,
                               "fixed_campaign_trials(597)")


def is_exact_policy(value: Any) -> bool:
    """The complete attestation, or one this desk superseded by LOOSENING the bar.

    MEASURED 2026-09-02 and this is the whole reason the desk had no new forward clocks. Sixty-
    three certificates passed all ten gates and carried a valid shadow_spec, and
    `authorized_specs` returned ZERO -- so not one of them could enrol. The single cause was
    this predicate: byte-equality against ATTESTATION, and the artifact's attestation differed
    in exactly one field, `trial_count_basis`, because the desk had improved how it counts
    trials. Every other bar -- dsr_threshold, pbo_max, spa_alpha, the gate list, the cost
    multiplier -- was identical.

    Equality is right for a THRESHOLD. It is wrong for a description of how a threshold was
    reached, when the change made that threshold easier: refusing evidence earned under a
    HARDER bar is backwards, and it silently froze the desk's entire path to live capital. This
    is the same failure as the cost-hash identity break (`sleeve_registry.rebase_cost`): the desk
    corrected itself and the correction invalidated every certificate it already held.

    STILL FAILS CLOSED ON EVERYTHING ELSE. Any difference outside `trial_count_basis`, or a basis
    not on the audited list above, is refused exactly as before.
    """
    if not isinstance(value, dict):
        return False
    if value == ATTESTATION:
        return True
    if set(value) != set(ATTESTATION):
        return False
    differing = [k for k in ATTESTATION if value[k] != ATTESTATION[k]]
    return (differing == ["trial_count_basis"]
            and is_admissible_trial_count_basis(value["trial_count_basis"]))


_BASIS_COUNT_RE = re.compile(
    r"^(?:fixed|effective)_campaign_trials\((\d+)\)"
    r"(?:\s*\+\s*fixed_variance_of_sharpes\(([0-9.eE+-]+)\))?")


def basis_charge(value: Any) -> tuple[int, float | None] | None:
    """(trials, variance-or-None) a fixed-charge basis string declares, or None if it is not one.

    Reads both the long attestation form (`effective_campaign_trials(N) + fixed_variance_of_
    sharpes(V): ...`) and the short form the gauntlet stamps on its gate output
    (`fixed_campaign_trials(N)`, from `charged_trial_count`).
    """
    if not isinstance(value, str):
        return None
    m = _BASIS_COUNT_RE.match(value.strip())
    if m is None:
        return None
    try:
        var = float(m.group(2)) if m.group(2) else None
    except ValueError:
        return None
    return int(m.group(1)), var


def is_admissible_trial_count_basis(value: Any, n_trials: Any = None) -> bool:
    """Whether a recorded trial charge is the current one or one PROVABLY at least as hard.

    This is deliberately narrower than a general migration.  It exists so publication and
    forward enrolment use the same audited exception as certificate attestation: a result that
    cleared a harder multiplicity charge is not invalidated merely because the desk later made
    the charge more accurate.

    THE SHORT FORM OF THE CURRENT CHARGE WAS ITSELF REFUSED (2026-09-25). The gauntlet stamps its
    gate output with the basis `charged_trial_count` returns -- `fixed_campaign_trials(N)` -- while
    this predicate knew only the long attestation string and the audited legacy list. So a sweep
    judged at EXACTLY the charge in force was recovered as `superseded_charge`. A fixed-charge
    basis is now read for its number: admissible iff it charged at least the current trials, at
    the current dispersion when it names one (sr0 rises with both, so N >= current at the same
    variance is a hurdle at least as high). A charge BELOW the current one stays refused -- that
    certificate cleared a lower bar and must be re-judged.

    `n_trials` (the gate output's own `n_trials`) admits the fail-closed stamp
    (`raw_cells_x7_fail_closed (...)`), whose string carries no number, when the count it
    actually charged is at least the current one.
    """
    if value == TRIAL_COUNT_BASIS or value in _SUPERSEDED_TRIAL_BASES:
        return True
    current = _SPEC_FIXED_TRIALS
    if not (isinstance(current, int) and current >= 2):
        return False
    parsed = basis_charge(value)
    if parsed is not None:
        trials, var = parsed
        if var is not None and (not isinstance(FIXED_VARIANCE_OF_SHARPES, (int, float))
                                or abs(var - float(FIXED_VARIANCE_OF_SHARPES)) > 1e-12):
            return False
        return trials >= current
    if (isinstance(value, str) and value.startswith("raw_cells_x7_fail_closed")
            and isinstance(n_trials, int) and not isinstance(n_trials, bool)):
        return n_trials >= current
    return False


#: SUPPLEMENTARY STAGES THE JUDGE MAY STAMP BESIDE THE TEN, AND THE ONLY ONES (audited list).
#:
#: `external_gauntlet` added an eleventh stage, `swap_cost`, on 2026-09-14. `all_ten_pass` then
#: demanded `tuple(stages) == GATES`, so every verdict the judge reached after that day was
#: refused as `extra_gate_not_in_policy` -- the canon could not admit a single new certificate.
#: The fix is NOT "any extra name that says passed": an unknown stage is a judge this policy has
#: never read, and admitting it by name would let any writer attach a self-passing gate. So an
#: extra stage is admissible only when it is on this list. Adding a name here is a policy change
#: and belongs in a re-signed commit, exactly like the ten.
SUPPLEMENTARY_GATES: frozenset[str] = frozenset({"swap_cost"})


def supplementary_stage_ok(stage: Any) -> bool:
    """An audited extra stage clears when it PASSED, or was honestly UNMEASURED without failing.

    `swap_cost` needs a live terminal to price a swap. Where there is none the judge records
    `{"passed": True, "measured": False}` -- a reading, not a verdict -- and refusing that would
    halt certification on every host without MT5 rather than charge a cost. So:

      * `passed is True`                        -> clears (measured or not);
      * `measured is False` and no `passed: False` -> clears (UNMEASURED is not a failure);
      * anything that says `passed: False`       -> REFUSES, measured or not -- a measured
        swap cost that eats the edge is exactly what this stage exists to catch.
    """
    if not isinstance(stage, dict):
        return False
    if stage.get("passed") is True:
        return True
    return stage.get("measured") is False and stage.get("passed") is not False


def all_ten_pass(stages: Any) -> bool:
    """All ten canonical gates present and passed; any EXTRA stage audited and not failed.

    The original ten are mandatory and each must carry `passed is True`. A stage outside the ten
    is admissible only when it is named in `SUPPLEMENTARY_GATES` and `supplementary_stage_ok`
    holds on it. An unknown extra stage still refuses: the policy cannot vouch for a judge it has
    never read.
    """
    if not isinstance(stages, dict):
        return False
    if not all(name in stages for name in GATES):
        return False
    if not all(isinstance(stages[name], dict) and stages[name].get("passed") is True
               for name in GATES):
        return False
    return all(name in SUPPLEMENTARY_GATES and supplementary_stage_ok(stages[name])
               for name in stages if name not in GATES)


def charged_trial_count(raw_cells: int, effective_cells: Any,
                        method: Any) -> tuple[int, str]:
    """Charge measured independent cells plus the unchanged 7x campaign history.

    Dependence relief is available only from the fixed participation-ratio instrument and only
    when its result is finite and bounded by the cells actually run. Every missing or malformed
    measurement fails closed to the raw-cell burden.
    """
    # THE SAME CHARGE FOR EVERY CELL, WHATEVER ELSE IS IN THE SWEEP. Both former branches scaled
    # with how many cells that hour happened to carry, so a candidate's bar moved with the batch
    # it was scheduled into rather than with anything about the candidate: sr0 0.3786 at 597
    # charged trials, 1.3593 at 5,963, same gate, same policy, same cell.
    # The deflated Sharpe still corrects for multiple testing -- it now corrects against a
    # standing campaign size, which is what the correction was always meant to represent.
    # `raw_cells`, `effective_cells` and `method` are still accepted and still REPORTED by the
    # caller: the census is how anyone checks this number was not quietly chosen to suit a
    # result, and hiding the inputs would be exactly that.
    fixed = _SPEC_FIXED_TRIALS
    if isinstance(fixed, int) and fixed >= 2:
        return fixed, f"fixed_campaign_trials({fixed})"
    # No fixed count in the spec: fail closed to the old raw burden rather than guess.
    return (max(2, math.ceil(max(0, raw_cells) * TRIALS_MULTIPLIER)),
            "raw_cells_x_campaign_multiplier_fail_closed")


def fail_closed_trial_count(raw_cells: int) -> int:
    """The charge to use when the CENSUS could not be computed. Policy's number, not the batch's.

    `charged_trial_count` is wrapped in a try/except at three call sites, because the effective-
    cell census it takes as input can throw. Every one of those except-branches fell back to
    `ceil(raw_cells * TRIALS_MULTIPLIER)` -- the batch-width tax the fixed wall exists to remove,
    reintroduced on the failure path. So a census error did not merely lose the dependence
    relief, it silently made a candidate's bar a property of how many cells were scheduled
    alongside it, which is the defect in full.

    `gate_spec.yaml` already says what should happen here in as many words:

        fail_closed_to: "fixed_campaign_trials(597)"

    and the code did something else. Failing closed means falling back to a HARSHER-OR-EQUAL bar
    that is still POLICY -- not to a different policy that happens to be harsher on average. When
    the spec carries no fixed count at all there is nothing to fall back to and the raw burden is
    the honest answer, which is the one case `charged_trial_count` still handles that way.
    """
    fixed = _SPEC_FIXED_TRIALS
    if isinstance(fixed, int) and fixed >= 2:
        return fixed
    return max(2, math.ceil(max(0, raw_cells) * TRIALS_MULTIPLIER))


def get_gate_classification() -> dict[str, str]:
    """Return gate -> classification mapping from spec."""
    return {
        g["name"]: g["classification"]
        for g in _SPEC["gates"]
    }


def get_validity_gates() -> frozenset[str]:
    """Return set of VALIDITY gate names."""
    return frozenset(
        g["name"] for g in _SPEC["gates"] if g["classification"] == "validity"
    )


def get_power_gates() -> frozenset[str]:
    """Return set of POWER gate names."""
    return frozenset(
        g["name"] for g in _SPEC["gates"] if g["classification"] == "power"
    )


def get_promotion_thresholds() -> dict:
    """Return promotion protocol thresholds from spec."""
    return _SPEC.get("promotion", {})
