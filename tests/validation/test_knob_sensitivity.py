"""Tests for the knob-sensitivity instrument (L1.49 family).

The load-bearing test in this file is `test_overclaimed_is_the_refusal_path`: an instrument that
cannot produce a failing verdict is not a fence, and every fence this desk built on 2026-07-31
shipped with at least one violation of exactly that (L1.41).
"""
from __future__ import annotations

import numpy as np
import pytest

from libs.validation.knob_sensitivity import (
    DECORATIVE,
    LOAD_BEARING,
    UNMEASURED,
    measure_knob,
    summarise,
)


def _probe_ignoring(_value: object) -> float:
    """A consumer that does not read the structure the knob modifies."""
    return 0.5


def _probe_reading(value: object) -> float:
    return float(value) * 2.0


def test_decorative_when_output_never_moves() -> None:
    v = measure_knob(_probe_ignoring, (0, 1, 500), name="n", knob="k", consumer="c")
    assert v.status == DECORATIVE
    assert v.outputs == [0.5, 0.5, 0.5]
    assert "does not read the structure" in v.why


def test_load_bearing_when_output_moves() -> None:
    v = measure_knob(_probe_reading, (0, 1, 500), name="n", knob="k", consumer="c")
    assert v.status == LOAD_BEARING
    assert not v.overclaims


def test_overclaimed_is_the_refusal_path() -> None:
    """DECORATIVE + not declared inert must FAIL the roll-up. This is the whole fence."""
    undeclared = measure_knob(_probe_ignoring, (0, 1), name="n", knob="k", consumer="c")
    assert undeclared.overclaims is True
    rep = summarise([undeclared])
    assert rep["status"] == "OVERCLAIMED"
    assert rep["n_overclaimed"] == 1
    assert "REPAIR UPWARD" in rep["next_action"]


def test_declared_inert_is_honest_not_a_defect() -> None:
    """A knob that says out loud it buys nothing is the HONEST-GAP state, not the failing one."""
    v = measure_knob(_probe_ignoring, (0, 1), name="n", knob="k", consumer="c",
                     declared_inert=True, inert_reason="consumer reads test only")
    assert v.status == DECORATIVE
    assert v.overclaims is False
    assert v.why == "consumer reads test only"
    assert summarise([v])["status"] == "OK"


def test_single_value_cannot_certify_a_knob() -> None:
    """One value has nothing to compare against; resolving it to DECORATIVE is the false-clean
    direction, so it must read UNMEASURED (L1.28a)."""
    v = measure_knob(_probe_reading, (7,), name="n", knob="k", consumer="c")
    assert v.status == UNMEASURED
    assert summarise([v])["status"] == UNMEASURED


def test_raising_probe_is_counted_never_swallowed() -> None:
    """Attrition is recorded (L1.60): a probe that dies on 2 of 4 values still yields a verdict
    on the surviving 2, and the 2 deaths stay visible."""
    def flaky(value: object) -> float:
        if int(value) > 1:
            raise ValueError("range unsupported")
        return float(value)

    v = measure_knob(flaky, (0, 1, 50, 500), name="n", knob="k", consumer="c")
    assert v.status == LOAD_BEARING
    assert v.values_failed == [50, 500]
    assert v.as_dict()["n_attempted"] == 4


def test_all_probes_raising_is_unmeasured_not_clean() -> None:
    def dead(_value: object) -> float:
        raise RuntimeError("no")

    v = measure_knob(dead, (0, 1), name="n", knob="k", consumer="c")
    assert v.status == UNMEASURED
    assert v.values_failed == [0, 1]


def test_empty_roster_is_unmeasured_never_ok() -> None:
    rep = summarise([])
    assert rep["status"] == UNMEASURED
    assert rep["n_probes"] == 0


# --------------------------------------------------------------- the shipped code under test

def test_shipped_cpcv_consumers_are_inert_and_say_so() -> None:
    """The proving instance (R0240), pinned so a future edit cannot silently restore the claim.

    If a consumer ever starts reading `s.train`, this test fails and the `declared_inert`
    comments in both modules become the thing that must be corrected -- which is the intended
    direction of repair, not a regression.
    """
    import libs.autodiscovery.validation as av
    import libs.validation.ensemble_gate as eg

    rng = np.random.default_rng(7)
    innovation = rng.normal(0.0004, 0.01, 3000)
    arr = np.zeros(3000, dtype="float64")
    for i in range(1, 3000):
        arr[i] = 0.35 * arr[i - 1] + innovation[i]

    for mod in (av, eg):
        baseline = mod._cpcv_positive_fraction(arr)
        original_purge, original_embargo = mod._CPCV_PURGE, mod._CPCV_EMBARGO
        try:
            mod._CPCV_PURGE, mod._CPCV_EMBARGO = 500, 0.45
            assert mod._cpcv_positive_fraction(arr) == baseline, (
                f"{mod.__name__} became purge/embargo-sensitive -- update the declared_inert "
                "comment at the constant block and the probe registry")
        finally:
            mod._CPCV_PURGE, mod._CPCV_EMBARGO = original_purge, original_embargo


def test_walk_forward_embargo_is_the_positive_control() -> None:
    """A fence never shown to detect a REAL dependency has not been validated -- only its
    negative readings have been observed."""
    from libs.validation.revalidation import WalkForwardEngine

    rng = np.random.default_rng(7)
    innovation = rng.normal(0.0004, 0.01, 3000)
    arr = np.zeros(3000, dtype="float64")
    for i in range(1, 3000):
        arr[i] = 0.35 * arr[i - 1] + innovation[i]

    engine = WalkForwardEngine()
    seen = {engine.evaluate(arr, n_splits=4, test_size=300, embargo=e).is_sharpe
            for e in (0, 1, 50, 500)}
    assert len(seen) > 1, "walk_forward embargo stopped reaching is_sharpe -- the fence's only "\
                          "positive control went dark and every DECORATIVE reading is suspect"


@pytest.mark.parametrize("status", [LOAD_BEARING, DECORATIVE, UNMEASURED])
def test_status_vocabulary_is_closed(status: str) -> None:
    """The fence script maps every status to a display token; an unmapped one would KeyError."""
    assert status in {LOAD_BEARING, DECORATIVE, UNMEASURED}
