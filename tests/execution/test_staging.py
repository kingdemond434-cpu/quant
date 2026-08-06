"""Stage machine -- promotion never skips a stage, demotion is unlimited and instant, every
transition is logged. Property-tested per the connector spec's verification bar (section 7):
size/stage guards must never violate their invariants under any input."""

from __future__ import annotations

from hypothesis import given
from hypothesis import strategies as st

import libs.execution.staging as staging

_STAGES = ("S0", "S1", "S2")


def _isolate(tmp_path, monkeypatch):  # type: ignore[no-untyped-def]
    monkeypatch.setattr(staging, "_STATE", tmp_path / "stage_state.json")


def test_starts_at_s0_by_default(tmp_path, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    _isolate(tmp_path, monkeypatch)
    assert staging.current_stage() == "S0"


def test_promotion_never_skips_a_stage(tmp_path, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    _isolate(tmp_path, monkeypatch)
    full_evidence = {
        "principal_signoff": True, "capital_fraction": 0.05, "symbol_count": 5,
        "keys_present": True, "connector_verified": True,
        "live_weeks": 10.0, "calibration_rows": 12, "critical_drill_failures": 0,
        "cost_ratio": 1.1,
    }
    assert staging.current_stage() == "S0"
    ok, _why = staging.promote(full_evidence)
    assert ok is True
    assert staging.current_stage() == "S1"                 # S0 -> S1 only, never straight to S2
    ok2, _why2 = staging.promote(full_evidence)
    assert ok2 is True
    assert staging.current_stage() == "S2"
    ok3, _why3 = staging.promote(full_evidence)
    assert ok3 is False                                    # S2 is terminal
    assert staging.current_stage() == "S2"


def test_s1_gate_blocks_on_any_missing_precondition(tmp_path, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    _isolate(tmp_path, monkeypatch)
    base = {"principal_signoff": True, "capital_fraction": 0.05, "symbol_count": 5,
            "keys_present": True, "connector_verified": True}
    bad_values = {"principal_signoff": False, "capital_fraction": 1.0, "symbol_count": 0,
                  "keys_present": False, "connector_verified": False}
    for key, bad_val in bad_values.items():
        bad = dict(base)
        bad[key] = bad_val
        assert staging.s1_entry_met(bad)[0] is False, f"S1 gate should block on {key}"
    assert staging.s1_entry_met(base)[0] is True


def test_s1_gate_rejects_symbol_count_outside_4_to_5(tmp_path, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    _isolate(tmp_path, monkeypatch)
    base = {"principal_signoff": True, "capital_fraction": 0.05, "keys_present": True,
            "connector_verified": True}
    for n in (0, 1, 2, 3, 6, 10):
        assert staging.s1_entry_met({**base, "symbol_count": n})[0] is False
    for n in (4, 5):
        assert staging.s1_entry_met({**base, "symbol_count": n})[0] is True


def test_s2_gate_blocks_on_any_missing_precondition(tmp_path, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    _isolate(tmp_path, monkeypatch)
    base = {"live_weeks": 10.0, "calibration_rows": 12, "critical_drill_failures": 0,
            "cost_ratio": 1.1}
    assert staging.s2_entry_met(base)[0] is True
    assert staging.s2_entry_met({**base, "live_weeks": 7.9})[0] is False
    assert staging.s2_entry_met({**base, "calibration_rows": 9})[0] is False
    assert staging.s2_entry_met({**base, "critical_drill_failures": 1})[0] is False
    assert staging.s2_entry_met({**base, "cost_ratio": 1.26})[0] is False


def test_demotion_is_unlimited_and_instant(tmp_path, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    _isolate(tmp_path, monkeypatch)
    full_evidence = {
        "principal_signoff": True, "capital_fraction": 0.05, "symbol_count": 5,
        "keys_present": True, "connector_verified": True,
        "live_weeks": 10.0, "calibration_rows": 12, "critical_drill_failures": 0,
        "cost_ratio": 1.1,
    }
    staging.promote(full_evidence)
    staging.promote(full_evidence)
    assert staging.current_stage() == "S2"
    ok, target = staging.demote("cost breach")
    assert ok is True and target == "S1"
    ok2, target2 = staging.demote("second tripwire same day -- unlimited")
    assert ok2 is True and target2 == "S0"
    ok3, _target3 = staging.demote("already at floor")
    assert ok3 is False                                    # S0 is the floor, demotion is a no-op


def test_every_transition_is_logged(tmp_path, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    _isolate(tmp_path, monkeypatch)
    full_evidence = {
        "principal_signoff": True, "capital_fraction": 0.05, "symbol_count": 5,
        "keys_present": True, "connector_verified": True,
    }
    staging.promote(full_evidence)
    staging.demote("test")
    hist = staging._load()["history"]
    assert len(hist) == 2
    assert hist[0]["action"] == "promote" and hist[0]["from"] == "S0" and hist[0]["to"] == "S1"
    assert hist[1]["action"] == "demote" and hist[1]["from"] == "S1" and hist[1]["to"] == "S0"


@given(
    signoff=st.booleans(), cap_frac=st.floats(0.0, 1.0), n_sym=st.integers(0, 10),
    keys=st.booleans(), verified=st.booleans(),
)
def test_s1_gate_property_matches_conjunction(  # type: ignore[no-untyped-def]
    signoff: bool, cap_frac: float, n_sym: int, keys: bool, verified: bool,
) -> None:
    """The gate is exactly the AND of its five named checks -- no hidden leniency."""
    evidence = {"principal_signoff": signoff, "capital_fraction": cap_frac,
                "symbol_count": n_sym, "keys_present": keys, "connector_verified": verified}
    expected = signoff and cap_frac <= 0.10 and 4 <= n_sym <= 5 and keys and verified
    assert staging.s1_entry_met(evidence)[0] == expected


@given(
    weeks=st.floats(0.0, 20.0), rows=st.integers(0, 30), fails=st.integers(0, 5),
    cost=st.floats(0.5, 3.0),
)
def test_s2_gate_property_matches_conjunction(  # type: ignore[no-untyped-def]
    weeks: float, rows: int, fails: int, cost: float,
) -> None:
    evidence = {"live_weeks": weeks, "calibration_rows": rows,
                "critical_drill_failures": fails, "cost_ratio": cost}
    expected = weeks >= 8.0 and rows >= 10 and fails == 0 and cost <= 1.25
    assert staging.s2_entry_met(evidence)[0] == expected


@given(actions=st.lists(st.booleans(), min_size=1, max_size=12))
def test_stage_always_in_valid_range_under_any_sequence(  # type: ignore[no-untyped-def]
    tmp_path_factory, actions: list[bool],
) -> None:
    """No sequence of promote/demote calls can ever push the stage outside {S0,S1,S2} or skip
    a stage in one hop -- the core safety property of the whole machine."""
    import importlib

    tmp = tmp_path_factory.mktemp("stage")
    importlib.reload(staging)
    staging._STATE = tmp / "stage_state.json"
    full_evidence = {
        "principal_signoff": True, "capital_fraction": 0.05, "symbol_count": 5,
        "keys_present": True, "connector_verified": True,
        "live_weeks": 10.0, "calibration_rows": 12, "critical_drill_failures": 0,
        "cost_ratio": 1.1,
    }
    prev_idx = _STAGES.index(staging.current_stage())
    for do_promote in actions:
        if do_promote:
            staging.promote(full_evidence)
        else:
            staging.demote("fuzz")
        idx = _STAGES.index(staging.current_stage())
        assert idx in (0, 1, 2)
        assert abs(idx - prev_idx) <= 1                     # never a 2-stage jump
        prev_idx = idx


# ------------------------------------------------ what the machine believes when the record is bad

def test_A_CORRUPT_STATE_FILE_FALLS_BACK_TO_S0_NOT_TO_THE_LAST_STAGE(  # type: ignore[no-untyped-def]
    tmp_path, monkeypatch
) -> None:
    """THE DIRECTION OF THE FALLBACK IS THE WHOLE SAFETY PROPERTY, and it is one `return` away
    from being inverted.

    A half-written stage_state.json is not exotic -- `_save` is a plain write with no temp-and-
    rename, so any kill between truncate and flush leaves exactly this. Falling back to S0 means a
    damaged record demotes the desk to paper until a human looks. Any other choice -- raising,
    or preserving a remembered stage -- means an unreadable file leaves live automation running on
    a record nothing can verify. Pinned because "don't lose the operator's progress on a parse
    error" is a natural-sounding change that silently converts a fail-safe into a fail-open.
    """
    _isolate(tmp_path, monkeypatch)
    staging._STATE.write_text('{"stage": "S2", "history": [] ', "utf-8")   # truncated mid-write
    assert staging.current_stage() == "S0"


def test_AN_UNRECOGNISED_STAGE_IS_NOT_TRUSTED(tmp_path, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    """Valid JSON carrying a stage this module has never heard of -- a hand-edit, a rolled-back
    deploy that knew about an "S3". `_STAGES.index()` in `demote` would raise ValueError on it,
    so an unrecognised stage does not merely mis-report: it makes the DEMOTION PATH throw, and
    demotion is the one operation the spec says is unlimited and never gated."""
    _isolate(tmp_path, monkeypatch)
    staging._STATE.write_text('{"stage": "S3", "history": []}', "utf-8")
    assert staging.current_stage() == "S0"
    ok, _why = staging.demote("tripwire")
    assert ok is False, "demote must not raise on a stage it does not recognise"


def test_A_JSON_LIST_WHERE_THE_STATE_SHOULD_BE(tmp_path, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    """Parses fine, has no `.get`. Without the isinstance check this is an AttributeError inside
    every caller of current_stage(), including the live guard's reporting pass."""
    _isolate(tmp_path, monkeypatch)
    staging._STATE.write_text('[{"stage": "S2"}]', "utf-8")
    assert staging.current_stage() == "S0"


def test_A_MISSING_FILE_IS_S0_AND_DEMOTE_SAYS_SO(tmp_path, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    """The floor is a floor: demoting from S0 reports failure rather than walking off the list."""
    _isolate(tmp_path, monkeypatch)
    ok, why = staging.demote("tripwire")
    assert ok is False and "S0" in why


def test_PROMOTION_STOPS_AT_S2(tmp_path, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    """S2 is terminal. A fourth stage reached by index arithmetic would be a stage with no gate
    defined for it at all."""
    _isolate(tmp_path, monkeypatch)
    staging._STATE.write_text('{"stage": "S2", "history": []}', "utf-8")
    ok, why = staging.promote({})
    assert ok is False and "terminal" in why


def test_A_STATE_FILE_WITH_NO_HISTORY_KEY_STILL_LOGS(tmp_path, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    """Every transition is logged "for auditability" -- but the log lives in the same dict the
    file supplies, so a record written by an older version without the key would KeyError on the
    append. The transition that fails is the DEMOTION, i.e. the one that runs when a tripwire has
    already fired."""
    _isolate(tmp_path, monkeypatch)
    staging._STATE.write_text('{"stage": "S1"}', "utf-8")
    ok, _target = staging.demote("tripwire")
    assert ok is True
    assert staging.current_stage() == "S0"
