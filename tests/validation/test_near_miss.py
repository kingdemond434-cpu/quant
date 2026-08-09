"""The invariants that keep near-miss triage a RECORD rather than a second chance.

Four of these are load-bearing and the rest support them:

  test_a_structural_failure_is_never_a_near_miss_however_small_the_shortfall -- the ordering in
    `triage` that makes "structural beats arithmetic" an invariant instead of an accident.
  test_no_hint_ever_suggests_relaxing_anything -- a keyword sweep over EVERY string the module can
    emit. Relaxing a gate to manufacture survivors is the thing this desk forbids outright, and it
    would arrive disguised as helpful prose.
  test_nothing_exposed_can_turn_a_failed_candidate_into_a_passed_one -- the module changes no
    verdict; this is what that sentence means operationally.
  test_the_ledger_appends_and_survives_a_corrupt_existing_line -- the ledger's whole value is that
    it accumulates across campaigns, and it must not lose its history to one half-written row.
"""
from __future__ import annotations

import json
import math
from pathlib import Path

import pytest

from libs.validation.brain_calibration import BRAIN_NEAR_SUBMITTABLE_FRACTION
from libs.validation.near_miss import (
    CLASSIFICATIONS,
    DATA_REPAIRABLE_STRUCTURAL,
    FAR_MISS,
    GATE_HINTS,
    MAX_NEAR_MISS_SHORTFALL,
    NEAR_MISS,
    NEAR_MISS_FRACTION,
    NO_FAILURE_RECORDED,
    STRUCTURAL_DEAD,
    NearMissVerdict,
    Threshold,
    all_hints,
    improvement_hint,
    log_near_misses,
    read_near_miss_ledger,
    relative_shortfall,
    triage,
)
from libs.validation.screen_admission import STATISTICAL_GATES, STRUCTURAL_GATES

# A higher-is-better gate and a lower-is-better gate, so every arithmetic test runs both ways.
_THR: dict[str, Threshold] = {
    "dsr": Threshold(1.0, higher_is_better=True, label="deflated Sharpe"),
    "pbo": Threshold(0.20, higher_is_better=False, label="prob. of backtest overfitting"),
    "reality_check": Threshold(0.05, higher_is_better=False, label="reality-check p"),
    "walk_forward": Threshold(0.50, higher_is_better=True, label="WF efficiency"),
    "cpcv": Threshold(0.60, higher_is_better=True),
    "not_too_lucky": Threshold(0.10, higher_is_better=False),
    "beats_baselines": Threshold(1.0, higher_is_better=True),
    "economic_mechanism": Threshold(1.0, higher_is_better=True),
    "expected_value": Threshold(0.001, higher_is_better=True),
    "capacity": Threshold(1.0, higher_is_better=True),
    "fragility": Threshold(1.0, higher_is_better=True),
    "break_even_win_rate": Threshold(0.40, higher_is_better=True),
    "sample_adequacy": Threshold(500.0, higher_is_better=True),
}


def _all_pass() -> dict[str, bool]:
    return dict.fromkeys((*STRUCTURAL_GATES, *STATISTICAL_GATES), True)


def _failing(*gates: str) -> dict[str, bool]:
    g = _all_pass()
    for name in gates:
        g[name] = False
    return g


# ------------------------------------------------------------------ the constant and its source

def test_near_miss_fraction_cannot_drift_from_its_brain_provenance():
    """0.80 is restated here rather than imported, because brain_calibration forbids decision paths
    importing it. Drift is prevented by this assertion instead of by the import."""
    assert NEAR_MISS_FRACTION == BRAIN_NEAR_SUBMITTABLE_FRACTION == 0.80
    assert pytest.approx(0.20) == MAX_NEAR_MISS_SHORTFALL


def test_the_canonical_brain_example_is_a_near_miss():
    """"Sharpe 0.9 against a 1.0 bar" is the transcript's own worked near-submittable case. If this
    desk's boundary arithmetic did not classify it as a near-miss, the constant would be quoting a
    source it does not actually implement."""
    v = triage(_failing("dsr"), {"dsr": 0.9}, _THR, name="brain_example")
    assert v.classification == NEAR_MISS
    assert v.worst_shortfall == pytest.approx(0.10)


# ------------------------------------------------------------------ shortfall arithmetic

def test_shortfall_is_right_when_higher_is_better():
    """dsr needed >= 1.0 and measured 0.85 -> short by 15% OF THE BAR."""
    assert relative_shortfall(0.85, _THR["dsr"]) == pytest.approx(0.15)


def test_shortfall_is_right_when_lower_is_better():
    """pbo needed <= 0.20 and measured 0.23 -> over by 15% of the bar. Same scale, opposite
    direction; getting this sign wrong would score a badly overfit candidate as nearly passing."""
    assert relative_shortfall(0.23, _THR["pbo"]) == pytest.approx(0.15)


def test_the_two_directions_agree_on_an_equivalent_miss():
    """A 10%-of-bar miss reads as 0.10 whichever way the gate points -- that symmetry is what makes
    the ranking across mixed-direction gates meaningful."""
    assert relative_shortfall(0.9, _THR["dsr"]) == pytest.approx(
        relative_shortfall(0.055, _THR["reality_check"]))


def test_a_cleared_gate_scores_zero_not_negative():
    """A negative shortfall from a passing gate could drag a 'worst' downwards and manufacture a
    near-miss out of one bad gate and several good ones."""
    assert relative_shortfall(1.5, _THR["dsr"]) == 0.0
    assert relative_shortfall(0.01, _THR["pbo"]) == 0.0


def test_a_near_zero_threshold_is_unmeasurable_not_a_huge_miss():
    """Dividing by ~0 manufactures an arbitrarily large miss from an arbitrarily small gap -- the
    same defect class as the `> 0` variance guard that shipped a 1.4e31 premium here."""
    assert math.isnan(relative_shortfall(-1.0, Threshold(0.0, higher_is_better=True)))
    assert math.isnan(relative_shortfall(-1.0, Threshold(1e-9, higher_is_better=True)))


def test_non_finite_inputs_refuse_to_answer():
    assert math.isnan(relative_shortfall(float("nan"), _THR["dsr"]))
    assert math.isnan(relative_shortfall(float("inf"), _THR["dsr"]))


# ------------------------------------------------------------------ THE structural invariant

@pytest.mark.parametrize("gate", STRUCTURAL_GATES)
def test_a_structural_failure_is_never_a_near_miss_however_small_the_shortfall(gate: str):
    """THE load-bearing invariant. The candidate misses the structural gate by a hundredth of a
    percent and clears everything else -- and is still STRUCTURAL_DEAD, because a missing economic
    mechanism or absent capacity is not a measurement that came out slightly low."""
    thr = _THR[gate]
    metric = thr.value * (0.9999 if thr.higher_is_better else 1.0001)
    v = triage(_failing(gate), {gate: metric}, _THR, name="hairsbreadth")
    assert v.worst_shortfall < 1e-3  # the miss really is microscopic
    assert v.classification == STRUCTURAL_DEAD
    assert v.classification != NEAR_MISS


def test_a_structural_failure_dominates_even_alongside_a_perfect_statistical_near_miss():
    v = triage(_failing("capacity", "dsr"), {"capacity": 0.999, "dsr": 0.99}, _THR)
    assert v.classification == STRUCTURAL_DEAD
    assert v.structural_failures == ("capacity",)
    assert v.statistical_failures == ("dsr",)


def test_sample_adequacy_is_still_structural_dead_but_flagged_re_runnable():
    """The one structural gate that MORE DATA repairs. The module refuses to fork
    STRUCTURAL_GATES to special-case it, so the CLASSIFICATION is unchanged; only the ledger's
    re-run queue knows the difference."""
    assert "sample_adequacy" in STRUCTURAL_GATES
    assert "sample_adequacy" in DATA_REPAIRABLE_STRUCTURAL
    v = triage(_failing("sample_adequacy"), {"sample_adequacy": 120.0}, _THR)
    assert v.classification == STRUCTURAL_DEAD
    assert v.re_runnable is True
    assert triage(_failing("capacity"), {"capacity": 0.1}, _THR).re_runnable is False


def test_the_structural_list_is_imported_not_restated():
    """A second copy of the structural list would drift, and the copy that drifted loose would be
    the one quietly reclassifying a dead mechanism as fixable."""
    src = Path("libs/validation/near_miss.py").read_text("utf-8")
    assert "from libs.validation.screen_admission import" in src
    assert "STRUCTURAL_GATES" in src
    for gate in STRUCTURAL_GATES:
        # Gate names may appear as HINT KEYS, but never inside a literal tuple redefining the list.
        assert f'STRUCTURAL_GATES: tuple[str, ...] = ("{gate}"' not in src


# ------------------------------------------------------------------ near vs far

def test_the_worst_gate_decides_not_the_average():
    """One gate missed by 2% and another by 300% is 300% away, not 151%. Averaging would let a pile
    of nearly-passed gates hide a catastrophic one."""
    v = triage(_failing("dsr", "pbo"), {"dsr": 0.98, "pbo": 0.80}, _THR)
    assert v.classification == FAR_MISS
    assert v.worst_shortfall == pytest.approx(3.0)


def test_the_boundary_itself_classifies_as_near_miss():
    """Exactly 80% of the bar is the transcript's own figure; the 0.8/1.0 subtraction lands on
    0.19999999999999998 in binary floating point, so without the tolerance this would flip."""
    v = triage(_failing("dsr"), {"dsr": NEAR_MISS_FRACTION}, _THR)
    assert v.worst_shortfall == pytest.approx(MAX_NEAR_MISS_SHORTFALL)
    assert v.classification == NEAR_MISS


def test_just_outside_the_boundary_is_a_far_miss():
    v = triage(_failing("dsr"), {"dsr": 0.75}, _THR)
    assert v.classification == FAR_MISS


def test_the_ranking_puts_the_closest_gate_first():
    v = triage(_failing("dsr", "pbo", "cpcv"),
               {"dsr": 0.90, "pbo": 0.21, "cpcv": 0.30}, _THR)
    assert [s.gate for s in v.shortfalls] == ["pbo", "dsr", "cpcv"]
    assert v.closest_gate == "pbo"


# ------------------------------------------------------------------ unknown must not be favourable

def test_an_unscoreable_failure_cannot_be_a_near_miss():
    """UNMEASURED IS NOT NEAR. Treating a missing metric as a zero shortfall would classify the
    least-measured candidates as the closest to passing -- the beats_baselines defect exactly."""
    v = triage(_failing("dsr"), {}, _THR, name="no_metric")
    assert v.classification == FAR_MISS
    assert v.unmeasured_gates == ("dsr",)
    assert math.isnan(v.worst_shortfall)
    assert v.closest_gate is None


def test_a_missing_threshold_is_unmeasured_too():
    v = triage(_failing("dsr"), {"dsr": 0.99}, {}, name="no_threshold")
    assert v.classification == FAR_MISS
    assert v.unmeasured_gates == ("dsr",)


def test_an_unmeasured_gate_cannot_hide_behind_a_measured_near_miss():
    """A candidate one hair under on dsr and completely unmeasured on pbo is NOT near-submittable;
    it is partly unmeasured, and the label has to say so."""
    v = triage(_failing("dsr", "pbo"), {"dsr": 0.99}, _THR)
    assert v.classification == FAR_MISS
    assert v.unmeasured_gates == ("pbo",)
    assert [s.gate for s in v.shortfalls] == ["dsr", "pbo"]  # unmeasured sorts last


def test_an_unrecognised_gate_blocks_the_favourable_label():
    gates = _failing()
    gates["some_new_gate"] = False
    v = triage(gates, {"some_new_gate": 0.99}, {"some_new_gate": Threshold(1.0)})
    assert v.classification == FAR_MISS
    assert v.unknown_gates == ("some_new_gate",)
    # Deliberately NOT structural: declaring it dead on no evidence tells the desk to stop working
    # on it, and 53% of this desk's refutations are measurement failures.
    assert v.classification != STRUCTURAL_DEAD


def test_a_candidate_with_no_failures_gets_its_own_label_not_a_pass():
    v = triage(_all_pass(), {}, _THR, name="never_failed")
    assert v.classification == NO_FAILURE_RECORDED
    assert v.classification not in (NEAR_MISS,)
    assert bool(v) is False


# ------------------------------------------------------------------ THE no-relaxation invariant

#: The banned vocabulary lives in the TEST, not in the module, so a hint cannot be legalised by
#: editing the guard in the same commit as the violation. Bare verbs are banned outright: there is
#: no legitimate sentence in an improvement hint containing "relax" or "loosen".
_BANNED_WORDS = (
    "relax", "loosen", "weaken", "soften", "waive", "override", "exempt",
    "grandfather", "widen", "downgrade", "bypass", "skip the gate",
)
_BANNED_PHRASES = (
    "lower the", "lower bar", "lower threshold", "reduce the threshold", "reduce the bar",
    "drop the bar", "drop the threshold", "adjust the threshold", "adjust the bar",
    "ease the", "less strict", "lenient", "move the bar", "move the threshold",
    "change the threshold", "tweak the threshold", "smaller threshold", "looser",
)


def _assert_clean(text: str, where: str) -> None:
    low = text.lower()
    for word in _BANNED_WORDS:
        assert word not in low, f"{where} suggests relaxing something: {word!r} in {text!r}"
    for phrase in _BANNED_PHRASES:
        assert phrase not in low, f"{where} suggests moving a bar: {phrase!r} in {text!r}"


def test_no_hint_ever_suggests_relaxing_anything():
    """Swept over EVERY string the module can emit, not just the ones a few constructed verdicts
    happen to reach -- an unreachable-today hint saying 'consider a lower bar' would sit in the
    table waiting for the branch that emits it."""
    hints = all_hints()
    assert hints, "all_hints() must enumerate something or this test proves nothing"
    for h in hints:
        _assert_clean(h, "all_hints()")


def test_every_gate_has_a_hint_so_none_degrades_to_a_guess():
    for gate in (*STRUCTURAL_GATES, *STATISTICAL_GATES):
        assert gate in GATE_HINTS, f"{gate} has no registered improvement hint"


def test_emitted_hints_are_clean_across_every_branch():
    """The composed output, not just the fragments: prefixes and gate hints are concatenated, and
    the test has to see the finished sentence a reader would act on."""
    cases: list[NearMissVerdict] = [
        triage(_failing("dsr"), {"dsr": 0.95}, _THR),                     # NEAR_MISS
        triage(_failing("dsr"), {"dsr": 0.10}, _THR),                     # FAR_MISS
        triage(_failing("capacity"), {"capacity": 0.5}, _THR),            # STRUCTURAL_DEAD
        triage(_failing("sample_adequacy"), {"sample_adequacy": 9.0}, _THR),
        triage(_failing("dsr"), {}, _THR),                                # unmeasured
        triage(_failing("dsr", "pbo"), {"dsr": 0.95}, _THR),              # partly unmeasured
        triage(_all_pass(), {}, _THR),                                    # nothing failed
    ]
    gates = _failing()
    gates["mystery_gate"] = False
    cases.append(triage(gates, {}, {}))
    for gate in (*STRUCTURAL_GATES, *STATISTICAL_GATES):
        thr = _THR[gate]
        cases.append(triage(_failing(gate), {gate: thr.value * 0.5}, _THR, name=gate))
    for v in cases:
        hint = improvement_hint(v)
        assert hint.strip(), f"{v.classification} produced an empty hint"
        _assert_clean(hint, f"improvement_hint({v.classification})")


def test_hints_are_keyed_to_the_specific_gate_not_generic():
    near = triage(_failing("pbo"), {"pbo": 0.22}, _THR)
    assert "pbo" in improvement_hint(near)
    assert "purged" in improvement_hint(near)
    struct = triage(_failing("economic_mechanism"), {"economic_mechanism": 0.0}, _THR)
    assert "forced to trade against" in improvement_hint(struct)
    assert improvement_hint(near) != improvement_hint(struct)


def test_the_structural_hint_says_measurement_will_not_fix_it():
    v = triage(_failing("fragility"), {"fragility": 0.1}, _THR)
    hint = improvement_hint(v).lower()
    assert "no sample size" in hint


# ------------------------------------------------------------------ it cannot promote anything

def test_nothing_exposed_can_turn_a_failed_candidate_into_a_passed_one():
    """The module classifies and records; it has no pass verdict and no field a caller could read
    as one. Checked structurally so a future field named `admitted` or `survived` fails here."""
    v = triage(_failing("dsr"), {"dsr": 0.99}, _THR, name="closest_possible")
    assert v.classification == NEAR_MISS

    # 1. No verdict is ever truthy -- `if triage(...)` cannot read as approval.
    assert bool(v) is False

    # 2. No field is a pass, a slot, a size, or a promotion.
    banned_fields = ("passed", "pass", "admitted", "survived", "promote", "promoted", "approved",
                     "ok", "cleared", "weight", "size", "slot", "capital", "allocation")
    for field_name in vars(v):
        assert field_name.lower() not in banned_fields, f"{field_name} reads as a promotion"

    # 3. Every classification the module can emit is a label on a FAILED candidate.
    assert set(CLASSIFICATIONS) == {NEAR_MISS, FAR_MISS, STRUCTURAL_DEAD, NO_FAILURE_RECORDED}
    for label in CLASSIFICATIONS:
        assert "pass" not in label.lower()
        assert "admit" not in label.lower()

    # 4. The ledger row carries no promotion either.
    row = v.to_record(as_of="2026-08-01T00:00:00Z")
    for key in row:
        assert key.lower() not in banned_fields, f"ledger key {key} reads as a promotion"
    assert row["classification"] in CLASSIFICATIONS


def test_triage_does_not_mutate_its_inputs():
    """A classifier that edited the gate dict handed to it could flip a gate for a later caller --
    which WOULD be changing a verdict, by the back door."""
    gates = _failing("dsr", "pbo")
    metrics = {"dsr": 0.9, "pbo": 0.25}
    before_gates, before_metrics = dict(gates), dict(metrics)
    triage(gates, metrics, _THR)
    assert gates == before_gates
    assert metrics == before_metrics


def test_a_near_miss_and_a_far_miss_are_both_still_failed():
    """Same candidate, two shortfalls, one label each -- and neither label is an outcome the desk's
    admission path could consume as a pass."""
    near = triage(_failing("dsr"), {"dsr": 0.95}, _THR)
    far = triage(_failing("dsr"), {"dsr": 0.05}, _THR)
    assert near.classification == NEAR_MISS
    assert far.classification == FAR_MISS
    assert bool(near) is bool(far) is False
    assert near.failed_gates == far.failed_gates == ("dsr",)


# ------------------------------------------------------------------ the ledger

def test_the_ledger_appends_and_survives_a_corrupt_existing_line(tmp_path: Path):
    """The ledger's entire value is that it ACCUMULATES across campaigns. It must not overwrite the
    history, and it must not lose it to one half-written row from a killed process."""
    path = tmp_path / "near_misses.jsonl"

    first = triage(_failing("dsr"), {"dsr": 0.95}, _THR, name="march_candidate")
    assert log_near_misses([first], path, as_of="2026-03-01T00:00:00Z") == 1

    # A process killed mid-write: a truncated line with NO trailing newline.
    with path.open("a", encoding="utf-8") as fh:
        fh.write('{"name": "killed_mid_wr')

    second = triage(_failing("pbo"), {"pbo": 0.22}, _THR, name="september_candidate")
    assert log_near_misses([second], path, as_of="2026-09-01T00:00:00Z") == 1

    rows = read_near_miss_ledger(path)
    names = [r["name"] for r in rows]
    assert names == ["march_candidate", "september_candidate"], "history was lost or spliced"

    # The corrupt line is skipped, not repaired, not guessed at -- and it did not swallow the row
    # appended after it.
    raw_lines = [ln for ln in path.read_text("utf-8").splitlines() if ln.strip()]
    assert len(raw_lines) == 3
    assert len(rows) == 2


def test_repeated_runs_accumulate_rather_than_replace(tmp_path: Path):
    path = tmp_path / "ledger.jsonl"
    for i in range(4):
        v = triage(_failing("dsr"), {"dsr": 0.95}, _THR, name=f"c{i}")
        log_near_misses([v], path, as_of=f"2026-0{i + 1}-01T00:00:00Z")
    rows = read_near_miss_ledger(path)
    assert [r["name"] for r in rows] == ["c0", "c1", "c2", "c3"]
    assert len({r["as_of"] for r in rows}) == 4


def test_the_ledger_records_the_denominator_not_just_the_near_misses(tmp_path: Path):
    """Filtering at WRITE time is how the silent death happens. Far misses and structural deaths
    are written too, with their classification, so 'we had 8 near-misses' has a denominator."""
    path = tmp_path / "ledger.jsonl"
    verdicts = [
        triage(_failing("dsr"), {"dsr": 0.95}, _THR, name="near"),
        triage(_failing("dsr"), {"dsr": 0.05}, _THR, name="far"),
        triage(_failing("capacity"), {"capacity": 0.1}, _THR, name="dead"),
    ]
    assert log_near_misses(verdicts, path, as_of="2026-08-01T00:00:00Z") == 3
    rows = read_near_miss_ledger(path)
    assert [r["classification"] for r in rows] == [NEAR_MISS, FAR_MISS, STRUCTURAL_DEAD]
    assert [r["re_runnable"] for r in rows] == [True, True, False]


def test_ledger_rows_are_valid_json_with_nulls_where_numbers_are_unmeasurable(tmp_path: Path):
    """`json.dumps` writes a bare NaN happily and no conforming parser reads it back."""
    path = tmp_path / "ledger.jsonl"
    v = triage(_failing("dsr"), {}, _THR, name="unmeasured")
    log_near_misses([v], path, as_of="2026-08-01T00:00:00Z")
    text = path.read_text("utf-8")
    assert "NaN" not in text
    row = json.loads(text.strip())
    assert row["worst_shortfall"] is None
    assert row["shortfalls"][0]["shortfall"] is None
    assert row["closest_gate"] is None


def test_the_ledger_row_carries_the_hint_and_the_provenance(tmp_path: Path):
    path = tmp_path / "ledger.jsonl"
    v = triage(_failing("pbo"), {"pbo": 0.22}, _THR, name="rerun_me")
    log_near_misses([v], path, as_of="2026-08-01T00:00:00Z")
    row = read_near_miss_ledger(path)[0]
    assert row["near_miss_fraction"] == NEAR_MISS_FRACTION
    assert "pbo" in row["improvement_hint"]
    _assert_clean(row["improvement_hint"], "ledger row hint")


def test_an_empty_batch_writes_nothing_and_creates_no_file(tmp_path: Path):
    path = tmp_path / "nested" / "ledger.jsonl"
    assert log_near_misses([], path) == 0
    assert not path.exists()


def test_reading_a_missing_ledger_is_empty_not_an_error(tmp_path: Path):
    """The ledger not existing yet IS the desk's current state -- data/forward_slots.json has never
    existed either -- and that is a fact to report, not a crash."""
    assert read_near_miss_ledger(tmp_path / "never_written.jsonl") == ()


def test_a_ledger_of_bare_scalars_is_dropped_rather_than_returned(tmp_path: Path):
    path = tmp_path / "ledger.jsonl"
    path.write_text('42\n["a"]\n{"name": "real", "classification": "NEAR_MISS"}\n', "utf-8")
    rows = read_near_miss_ledger(path)
    assert [r["name"] for r in rows] == ["real"]


def test_log_writes_a_timestamp_when_none_is_supplied(tmp_path: Path):
    path = tmp_path / "ledger.jsonl"
    v = triage(_failing("dsr"), {"dsr": 0.95}, _THR, name="stamped")
    log_near_misses([v], path)
    row = read_near_miss_ledger(path)[0]
    assert row["as_of"].endswith("Z")
