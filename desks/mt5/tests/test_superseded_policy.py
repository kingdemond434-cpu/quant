"""A policy change that LOOSENED the bar must not invalidate certificates earned under it.

MEASURED 2026-09-02 and this was the whole reason the desk had no new forward clocks: 63
certificates passed all ten gates carrying a valid shadow_spec, and `authorized_specs` returned
ZERO. The single cause was byte-equality against ATTESTATION, and the artifact differed in
exactly one field -- `trial_count_basis` -- because the desk had improved how it counts trials.
"""
from __future__ import annotations

import sys
from pathlib import Path

_DESK = Path(__file__).resolve().parents[1]
for _p in (str(_DESK), str(_DESK / "research")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from research.gate_policy import (  # noqa: E402
    _SUPERSEDED_TRIAL_BASES,
    ATTESTATION,
    is_exact_policy,
)

OLD = {**ATTESTATION, "trial_count_basis": _SUPERSEDED_TRIAL_BASES[0]}


def test_the_current_attestation_is_accepted() -> None:
    assert is_exact_policy(ATTESTATION)


def test_a_superseded_trial_basis_is_accepted() -> None:
    """The old basis charged ~65,000 trials on a 9,333-cell sweep against today's fixed 597, and
    sr0 grows with sqrt(2 ln N) -- so these certificates cleared a HARDER hurdle than the current
    policy asks for. Refusing them is backwards."""
    assert is_exact_policy(OLD)


def test_a_tightened_threshold_is_still_refused() -> None:
    """The allowance is for a LOOSENED bar only. A certificate earned under an easier threshold
    is genuinely under-qualified and must be re-run."""
    for field, worse in (("dsr_threshold", 0.90), ("pbo_max", 0.6), ("spa_alpha", 0.10),
                         ("cost_multiplier", 1.0)):
        assert not is_exact_policy({**ATTESTATION, field: worse}), field


def test_an_unaudited_trial_basis_is_refused() -> None:
    """Only bases on the audited list pass -- an unknown one has not been shown to be harsher."""
    assert not is_exact_policy({**ATTESTATION, "trial_count_basis": "something new"})


def test_two_differing_fields_are_refused_even_if_one_is_the_basis() -> None:
    """The allowance is for the basis ALONE; anything riding alongside it fails closed."""
    assert not is_exact_policy({**OLD, "pbo_max": 0.6})


def test_missing_and_extra_keys_still_fail_closed() -> None:
    assert not is_exact_policy({**ATTESTATION, "unexpected": 1})
    trimmed = dict(ATTESTATION)
    trimmed.pop("pbo_max")
    assert not is_exact_policy(trimmed)


def test_non_dicts_are_refused() -> None:
    for junk in (None, [], "attestation", 0, True):
        assert not is_exact_policy(junk)


def test_the_gate_list_itself_can_never_be_edited_through_this_door() -> None:
    """The ten gates are fixed. A shortened or reordered list is a different policy."""
    assert not is_exact_policy({**ATTESTATION, "gates": ATTESTATION["gates"][:9]})
    assert not is_exact_policy({**ATTESTATION, "gates": list(reversed(ATTESTATION["gates"]))})


def test_the_live_survivor_ledger_is_admitted() -> None:
    """The end-to-end property: the desk's actual certificates reach the door."""
    import json

    path = _DESK / "reports" / "UNIVERSAL_SURVIVORS.json"
    if not path.exists():
        return
    doc = json.loads(path.read_text(encoding="utf-8"))
    policy = doc.get("gate_policy")
    if not isinstance(policy, dict):
        return
    assert is_exact_policy(policy), (
        "the live survivor ledger's attestation is refused; no certificate can enrol a clock")
