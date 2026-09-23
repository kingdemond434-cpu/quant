"""The funnel ledger names the binding stage, and cannot flatter itself into naming the wrong one.

    python -m pytest desks/mt5/tests/test_conversion_ledger.py -q

WHAT THIS LEDGER IS FOR. Every stage transition in this desk's funnel is a conversion, and the
rates are the desk's real output. Counting the stages was already done twice
(`reports/RESEARCH_PRODUCTIVITY.json`, `data/intelligence/survivor_funnel.json`); neither carried
a RATE with a CAUSE beside it, and a count without a cause produces no work.

THE FOUR PROPERTIES THAT DECIDE WHETHER THE LEDGER IS HONEST, each pinned below:

  1. The BINDING stage is the lowest measured rate ON THE CRITICAL PATH. A tributary can read 0%
     and still not be the constraint, because unblocking it adds nothing downstream.
  2. An UNMEASURED stage names the artifact it could not read. "No certificates are blocked" and
     "I could not read the certificates" are opposite facts.
  3. A loss with no derivable cause says UNKNOWN. "REJECTED" is a verdict, not a cause -- that
     confusion is why thirty thousand buried rows produced no research.
  4. The reason is READ FROM THE DATA. Change the data and the named reason changes with it; a
     constant would go stale exactly the way `UNREACHABLE_NO_SHORT_LEG` did.

The scalp-session rows below pin a fifth thing the funnel itself cannot see: a generator that
cannot express a state has a conversion rate of zero on it, and no measurement starting at
"candidate" will ever notice.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

DESK = Path(__file__).resolve().parent.parent
RESEARCH = DESK / "research"
if str(RESEARCH) not in sys.path:
    sys.path.insert(0, str(RESEARCH))
if str(DESK.parent.parent) not in sys.path:
    sys.path.insert(0, str(DESK.parent.parent))

import conversion_ledger as cl  # noqa: E402
import scalp_family_expansion as sfe  # noqa: E402

S = cl.Stage


# --------------------------------------------------- 1. the binding stage

def test_the_binding_stage_is_the_lowest_measured_rate_on_the_critical_path() -> None:
    stages = [S("wide", 100, 90, critical=True),
              S("narrow", 1000, 1, critical=True),
              S("middling", 100, 50, critical=True)]
    assert cl.binding_stage(stages).name == "narrow"


def test_a_tributary_is_never_named_binding_however_bad_its_rate() -> None:
    """The deepening queue converts at 0.0%. Unblocking it would not add one certificate this
    week, because the family sweeps reach the gauntlet without passing through it. Naming it
    binding would send the next hour at a stage nothing downstream is waiting on."""
    stages = [S("tributary_at_zero", 888, 0, critical=False),
              S("the_real_constraint", 46835, 49, critical=True)]
    assert cl.binding_stage(stages).name == "the_real_constraint"


def test_an_unmeasured_stage_can_never_be_binding_even_at_a_zero_count() -> None:
    """A stage nobody could read is not a stage that lost everything."""
    stages = [S("unreadable", 100, 0, critical=True, measured=False),
              S("measured", 100, 5, critical=True)]
    assert cl.binding_stage(stages).name == "measured"


def test_ties_are_broken_by_the_work_destroyed() -> None:
    """Two stages at the same rate are not the same problem; the expensive one is."""
    stages = [S("cheap", 100, 1, critical=True), S("expensive", 100000, 1000, critical=True)]
    assert cl.binding_stage(stages).name == "expensive"


# --------------------------------------------------- 2. unmeasured is a finding

def test_an_unmeasured_stage_names_the_artifact_it_could_not_read(tmp_path: Path) -> None:
    (tmp_path / "data").mkdir()
    (tmp_path / "reports").mkdir()
    stage = cl.stage_certificate_to_enrollable(tmp_path)
    assert stage.measured is False
    assert stage.rate is None, "an unreadable stage must not report a rate of zero"
    assert "canon" in stage.loss_reason


def test_the_live_box_stages_say_where_to_read_them_instead_of_reporting_zero(
        tmp_path: Path) -> None:
    """`reports/` is git-ignored, so a host with only the repository cannot see the shadow state.
    That is a fact about the HOST and must never read as a fact about the desk."""
    stage = cl.stage_clock_to_sleeve(tmp_path)
    assert stage.measured is False
    assert "git-ignored" in stage.loss_reason
    assert stage.count_out is None


# --------------------------------------------------- 3 & 4. causes come from the data

def _queue(rows: list[dict]) -> list[dict]:
    return rows


def test_a_stage_with_no_derivable_cause_says_unknown_rather_than_guessing() -> None:
    stage = cl.stage_card_to_verdict(_queue([{"canonical_verdict": "PASSED"}]))
    assert stage.loss_reason.startswith("NONE"), "nothing was lost, so nothing may be blamed"
    empty = cl.stage_verdict_to_certificate([], [])
    assert empty.loss_reason == cl.UNKNOWN


def test_the_unjudged_card_is_counted_out_of_both_numerator_and_denominator() -> None:
    """An unjudged card is work not yet done. Counting it as a failure makes a queue read as a
    wall, which is the confusion the whole ledger exists to remove."""
    rows = _queue([{"canonical_verdict": "PASSED"},
                   {"canonical_verdict": "REJECTED"},
                   {"status": "PENDING", "blocked_on": "the docket has not reached it"}])
    assert cl.stage_card_to_verdict(rows).count_out == 2
    gate = cl.stage_verdict_to_certificate(rows, [])
    assert gate.count_in == 2 and gate.count_out == 1


def test_the_binding_reason_is_read_from_the_data_and_changes_with_it() -> None:
    """A constant reason goes stale silently -- exactly how the enrolment ceiling came to blame a
    defect that had already been fixed."""
    import trial_allocator as ta

    rows = _queue([{"canonical_verdict": "REJECTED"}] * 10)
    good = ta.CellYield("overnight_gap_decay", "fx_exotic", 122, 18)
    bad = ta.CellYield("discovered", "equity", 25876, 8)
    reason = cl.stage_verdict_to_certificate(rows, [good, bad]).loss_reason
    assert "discovered x equity" in reason and "overnight_gap_decay x fx_exotic" in reason
    flipped = cl.stage_verdict_to_certificate(
        rows, [ta.CellYield("discovered", "equity", 25876, 8000),
               ta.CellYield("overnight_gap_decay", "fx_exotic", 122, 0)]).loss_reason
    assert "overnight_gap_decay x fx_exotic certifies at 14" not in flipped


def test_a_card_with_no_canonical_cell_is_in_neither_count() -> None:
    """A region with no instrument is not a region, and guessing the symbol out of the prose is
    how a denominator quietly acquires rows nothing judged."""
    import trial_allocator as ta

    assert ta._symbol_of({"canonical_cell": "EURUSD.discovered.p=abc"}) == "EURUSD"
    assert ta._symbol_of({"hypothesis": "EURUSD looks good"}) is None


# --------------------------------------------------- the crypto fence, asserted

def test_the_crypto_fence_is_asserted_rather_than_assumed() -> None:
    """The crypto-EXCHANGE universe is retired and may never be hunted (2026-08-18). Fusion crypto
    CFDs are part of the MT5 universe, so the fence is a REGISTRY question, not a name question:
    a crypto symbol that is not a Fusion instrument would be an exchange-native leak."""
    out = cl.crypto_fence([{"canonical_cell": "BTCUSD.discovered.p=1"},
                           {"canonical_cell": "EURUSD.discovered.p=2"}])
    if out.get("measured"):
        assert out["crypto_cfd_symbols"] == 1
        assert "not_in_fusion_registry" in out


# --------------------------------------------------- the state the generator cannot express

def test_every_swept_session_has_a_mask_the_overlap_fallthrough_cannot_be_mistaken_for() -> None:
    """THE GUARD THAT MAKES ADDING A SESSION SAFE.

    `_session_mask` returns the London/NY overlap for ANY name it does not recognise, and the
    live executor calls this same function. So a session added to a roster without a branch in
    the mask would be certified, promoted and TRADED as the overlap while every report called it
    something else -- the mask/replay disagreement that put the scalp lane in quarantine.
    """
    import numpy as np
    import pandas as pd

    idx = pd.date_range("2026-01-05", periods=48, freq="h", tz="UTC")
    unknown = sfe._session_mask(idx, "a name no branch implements")
    for name in (*sfe.SESSIONS, *sfe.PROPOSED_SESSIONS):
        mask = sfe._session_mask(idx, name)
        if name == "overlap":
            assert np.array_equal(mask, unknown), "overlap IS the documented fall-through"
            continue
        assert not np.array_equal(mask, unknown), (
            f"session {name!r} has no branch in _session_mask and would trade as the overlap")


def test_the_two_session_rosters_move_together_or_multiplicity_falls_behind_the_search() -> None:
    """THE COUPLING THAT KEEPS A WIDER SWEEP FROM BEING A LOOSER GATE.

    `mt5desk.scalp_families.swept_grid()` charges the deflated-Sharpe hurdle
    `families x len(SWEPT_SESSIONS) x geometry` trials. Adding a session to the research roster
    without raising the census would charge a five-arm search at four arms -- a quieter version
    of moving the bar, and the one repair this desk forbids outright.
    """
    from mt5desk.scalp_families import SWEPT_SESSIONS

    assert tuple(SWEPT_SESSIONS) == tuple(sfe.SESSIONS), (
        "the sweep and the multiplicity census disagree about how wide the search is")
    assert not (set(sfe.PROPOSED_SESSIONS) & set(sfe.SESSIONS)), (
        "a proposed session that is already swept is not proposed, it is swept")


def test_the_asia_session_is_implemented_and_covers_the_hours_the_lane_cannot_target() -> None:
    """The lane's best forward sleeve earns in ASIA_MID (hours 02-05) and reaches those hours
    only because its session happens to be `all`. The mask exists so landing it is one word."""
    covered = cl._covered_utc_hours(sfe, ["asia"])
    assert covered is not None
    assert {0, 1, 2, 3, 4, 5, 6} <= covered
    assert 13 not in covered, "the asia branch must not be the overlap fall-through"
    swept = cl._covered_utc_hours(sfe, [s for s in sfe.SESSIONS if s != "all"])
    assert covered - swept, "if the swept sessions already covered Asia there would be no finding"


def test_a_phase_span_is_parsed_and_never_guessed() -> None:
    assert cl._phase_hours("02-05") == {2, 3, 4}
    assert cl._phase_hours("not a span") == set()


# --------------------------------------------------- the ledger is wired and reads only

def test_the_ledger_and_the_allocator_are_on_the_hourly_roster() -> None:
    """A measurement nothing runs is indistinguishable from one that does not exist."""
    import hourly_discovery as hd

    assert "conversion_ledger" in hd.ORGANS
    assert "trial_allocator" in hd.ORGANS
    assert "stages_measured" in hd.YIELD_KEYS and "cell_types" in hd.YIELD_KEYS, (
        "a measurement organ with no yield key reads as an organ that produced nothing")


def test_the_ledger_writes_under_the_base_it_measured(tmp_path: Path) -> None:
    """A test measuring a synthetic tree must not overwrite the desk's real ledger."""
    (tmp_path / "data").mkdir()
    (tmp_path / "reports").mkdir()
    (tmp_path / "data" / "research_queue.json").write_text(json.dumps([]), encoding="utf-8")
    doc = cl.run(tmp_path)
    assert (tmp_path / "data" / "conversion_ledger.json").exists()
    assert doc["binding_rule"] and doc["law"]


def test_both_new_components_declare_a_capability_node_beside_their_code() -> None:
    """A new component is admissible only with a capability-graph node. The graph's registry is
    outside this tree, so the declaration lives beside the code and is checked against it --
    the same discipline the UNDECLARED check enforces upstream."""
    import trial_allocator as ta

    src = (RESEARCH / "conversion_ledger.py").read_text(encoding="utf-8")
    for path in (*cl.CAPABILITY_NODE["writes"], *cl.CAPABILITY_NODE["reads"]):
        assert path.rsplit("/", 1)[-1] in src, f"declared path {path} is never touched"
    assert cl.CAPABILITY_NODE["authority"] == () == ta.CAPABILITY_NODE["authority"], (
        "neither component may hold authority: one measures, the other orders work")
    assert "desks/mt5/data/conversion_ledger.json" in ta.CAPABILITY_NODE["reads"], (
        "an artifact nothing reads is a DEAD_PRODUCER in the capability graph, and a component "
        "that spends the desk's compute must name the measurement it is aimed at")


def test_the_allocator_names_the_stage_it_is_aimed_at_and_notices_when_it_moves(
        tmp_path: Path) -> None:
    """A component that keeps producing weights after its constraint has moved is a component
    nobody will notice has stopped being the answer."""
    import trial_allocator as ta

    (tmp_path / "data").mkdir()
    (tmp_path / "data" / "conversion_ledger.json").write_text(json.dumps(
        {"binding_stage": ta.GATE_STAGE, "binding_rate": 0.001046,
         "generated_utc": "2026-09-05T00:00:00+00:00"}), encoding="utf-8")
    aimed = ta.target_stage(tmp_path / "data" / "conversion_ledger.json")
    assert aimed["aimed_correctly"] is True

    (tmp_path / "data" / "conversion_ledger.json").write_text(json.dumps(
        {"binding_stage": "forward_clock -> live_sleeve", "binding_rate": 0.02}),
        encoding="utf-8")
    moved = ta.target_stage(tmp_path / "data" / "conversion_ledger.json")
    assert moved["aimed_correctly"] is False

    missing = ta.target_stage(tmp_path / "data" / "nope.json")
    assert missing["binding_stage"] is None and "absent" in missing["why"]


def test_the_ledger_carries_the_rent_line_of_the_component_it_recommends() -> None:
    """A new component is admissible only with the ledger line that measures its rent."""
    import trial_allocator as ta

    r = ta.rent([ta.CellYield("good", "fx_exotic", 122, 18),
                 ta.CellYield("bad", "equity", 25876, 8)])
    assert r["module"] == "trial_allocator"
    assert r["ledger"] == "desks/mt5/data/conversion_ledger.json"
    assert r["unit"] and r["forward_basis"]


def test_the_gate_note_reports_a_loose_gate_and_takes_no_action(tmp_path: Path) -> None:
    """A gate that is too LOOSE is named and left alone. Tightening it would LOWER the
    certificate count, so it can never be confused with a conversion fix -- which is exactly why
    it is safe to name and unsafe to leave unnamed."""
    (tmp_path / "data").mkdir()
    (tmp_path / "data" / "UNIVERSAL_SURVIVORS.canon.json").write_text(json.dumps(
        {"survivors": {}, "gate_policy": {"trial_count_basis": "fixed_campaign_trials(597)"}}),
        encoding="utf-8")
    notes = cl.gate_notes(tmp_path)
    assert notes and notes[0]["gate"] == "deflated_sharpe"
    assert notes[0]["direction"].startswith("TOO LOOSE")
    assert notes[0]["action"].startswith("NONE TAKEN")
