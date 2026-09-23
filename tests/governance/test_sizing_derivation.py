"""R0135 sizing-derivation fence -- no number that moves money may be chosen by feel.

Four money-path constants were found defective in one session, all round numbers picked by
analogy. These tests pin that the fence actually distinguishes a cited derivation from a
comfortable number, and that it says so rather than passing quietly.
"""
from __future__ import annotations

from scripts.check_sizing_derivation import _EXEMPT, audit_module, build_report


def _mod(tmp_path, body: str, name: str = "scripts/x.py"):
    p = tmp_path / name
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(body, "utf-8")
    return audit_module(tmp_path, name)


def test_a_bare_number_is_flagged(tmp_path):
    r = _mod(tmp_path, "MAX_RISK = 0.20  # aggressive but not crazy\n")
    assert r["state"] == "UNJUSTIFIED-CONSTANTS"
    assert r["undocumented"][0]["name"] == "MAX_RISK"
    assert "no derivation cited" in r["undocumented"][0]["why"]


def test_a_cited_derivation_passes(tmp_path):
    r = _mod(tmp_path, "#: simulated over 250 days: 20% risk gives P(-90% drawdown) = 96%\n"
                       "MAX_RISK = 0.06\n")
    assert r["state"] == "OK" and r["n_bad"] == 0


def test_hand_waving_without_numbers_is_not_a_derivation(tmp_path):
    # "measured" with nothing measured is the failure this fence is most likely to face.
    r = _mod(tmp_path, "#: measured and derived, definitely\nMAX_RISK = 0.20\n")
    assert r["state"] == "UNJUSTIFIED-CONSTANTS"
    assert "no numbers" in r["undocumented"][0]["why"]


def test_a_trailing_comment_counts_as_the_justification(tmp_path):
    r = _mod(tmp_path, "MAX_LEV = 20.0  # derived: 0.50 stress / ((0.5+2)/100) = 20.0x\n")
    assert r["state"] == "OK"


def test_exemptions_must_be_declared_not_inferred(tmp_path):
    # "It's obviously plumbing" has to be written down to count -- same rule as the build
    # standard's schedule exemptions.
    r = _mod(tmp_path, "MAX_PAGES = 12\n")
    assert r["state"] == "OK"
    assert any(c["state"] == "EXEMPT" for c in r["constants"])
    assert all(_EXEMPT[k] for k in _EXEMPT)              # every exemption carries a reason
    r = _mod(tmp_path, "SOME_UNDECLARED_KNOB = 12\n")
    assert r["state"] == "UNJUSTIFIED-CONSTANTS"


def test_non_numeric_and_lowercase_names_are_ignored(tmp_path):
    r = _mod(tmp_path, "MODE = 'fast'\nthreshold = 0.5\n")
    assert r["n_constants"] == 0 and r["state"] == "OK"


def test_an_unreadable_module_is_stated_never_passed(tmp_path):
    r = audit_module(tmp_path, "scripts/does_not_exist.py")
    assert r["state"] == "UNREADABLE"                    # not OK -- absence is not compliance


def test_a_syntax_error_is_stated_never_passed(tmp_path):
    r = _mod(tmp_path, "MAX_RISK = (((\n")
    assert r["state"] == "UNPARSEABLE"


def test_the_live_money_path_is_fully_derived():
    # The fence holds the real modules, not just fixtures.
    rep = build_report()
    assert rep["status"] == "OK", rep["detail"]
    assert rep["n_unjustified"] == 0


def test_a_schedule_derived_threshold_is_not_flagged(tmp_path):
    """FOURTH FALSE-POSITIVE CLASS (2026-08-05). A staleness threshold set from a producer's known
    firing rate is derived from a fact you can look up in the manifest, exactly as a published fee
    schedule is: CHART_STALE_H=2.0 because the chart builder's cron cadence is 20 minutes, so 2h
    is five consecutive missed builds -- the organ has STOPPED, not hiccuped. Widening the
    vocabulary is this list's own documented response to a false positive; rewording
    run_conviction_trader to hit the words would be gaming the fence."""
    src = ("#: Age beyond which chart structure is stale. The builder's cron cadence is 20\n"
           "#: minutes, so 2h means five consecutive missed builds -- the organ has STOPPED.\n"
           "CHART_STALE_H: float = 2.0\n")
    (tmp_path / "mod.py").write_text(src, "utf-8")
    rep = audit_module(tmp_path, "mod.py")
    assert rep["state"] == "OK", rep["undocumented"]


def test_a_bare_number_with_no_reason_is_still_flagged(tmp_path):
    """The widening must not weld the gate open: a constant with a comment carrying neither a
    derivation word nor a number is exactly what this fence exists to catch."""
    (tmp_path / "mod.py").write_text("#: Seems about right.\nSOME_LIMIT: float = 3.0\n", "utf-8")
    assert audit_module(tmp_path, "mod.py")["state"] == "UNJUSTIFIED-CONSTANTS"


# =============================================================================================
# ONE `#:` BLOCK DOCUMENTS ITS WHOLE GROUP -- and stops at the group's edge (gap-fixer 08-29).
#
# The walk used to halt at the first non-comment line, so a block covering several related
# constants was credited to whichever one sat directly beneath it and its siblings were reported
# `no derivation cited`. MEASURED: `scripts/resolve_paper_book.py` carries ONE preregistration
# block deriving TRAIL_FWD_DECIDE_N=25, TRAIL_FWD_HARD_N=50 and TRAIL_FWD_T=1.7 together, and
# this fence reported three of them plus TRAIL_FWD_CHALLENGER. Those four false breaches held
# `run_law_gate --laws-only` RED -- and a gate red on correct code is exactly how a gate red on
# a REAL breach stops being read (L1.43).
#
# THE NEGATIVE TESTS MATTER MORE THAN THE POSITIVE ONE. Widening a fence's reach is how a fence
# quietly stops asking anything, so the group must END at a blank line or any non-assignment.
# =============================================================================================


def test_one_block_documents_the_whole_contiguous_group(tmp_path):
    """The defect. Three constants, one derivation block, no blank lines between them."""
    r = _mod(tmp_path,
             "#: simulated over 250 days: 25 paired reads, 50 hard stop, |t|>=1.7 one-sided\n"
             "DECIDE_N = 25\n"
             "HARD_N = 50\n"
             "T_BAR = 1.7\n")
    assert r["state"] == "OK", r["undocumented"]
    assert r["n_bad"] == 0


def test_a_blank_line_ends_the_group_and_the_next_constant_is_on_its_own(tmp_path):
    """THE GUARD. Without this the walk would reach back through a whole file and credit a
    comment written about something else -- a fence that passes everything asks nothing."""
    r = _mod(tmp_path,
             "#: simulated over 250 days: 25 paired reads gives P(miss) = 4%\n"
             "DECIDE_N = 25\n"
             "\n"
             "UNRELATED = 0.42\n")
    assert r["state"] == "UNJUSTIFIED-CONSTANTS"
    names = [u["name"] for u in r["undocumented"]]
    assert names == ["UNRELATED"], names


def test_any_non_assignment_ends_the_group(tmp_path):
    """A function, an import, an `if` -- anything that is not a sibling constant closes it."""
    r = _mod(tmp_path,
             "#: measured over 250 days: 25 paired reads gives P(miss) = 4%\n"
             "DECIDE_N = 25\n"
             "def helper():\n"
             "    return 1\n"
             "AFTER_CODE = 0.42\n")
    names = [u["name"] for u in r["undocumented"]]
    assert names == ["AFTER_CODE"], names


def test_a_comment_never_credits_the_constant_ABOVE_it(tmp_path):
    """Direction matters: `#:` documents what FOLLOWS. Reaching upward would credit a constant
    with a justification written about a different one."""
    r = _mod(tmp_path,
             "BEFORE_BLOCK = 0.42\n"
             "#: measured over 250 days: 25 paired reads gives P(miss) = 4%\n"
             "DECIDE_N = 25\n")
    names = [u["name"] for u in r["undocumented"]]
    assert names == ["BEFORE_BLOCK"], names


def test_the_widened_vocabulary_still_rejects_a_number_picked_by_feel(tmp_path):
    """The fifth false-positive class was widened for; the fence must still bite on taste."""
    r = _mod(tmp_path, "#: 1.7 felt about right and nobody objected\nT_BAR = 1.7\n")
    assert r["state"] == "UNJUSTIFIED-CONSTANTS", r


def test_alpha_is_deliberately_absent_from_the_vocabulary() -> None:
    """This desk says `alpha` on nearly every line; admitting it would pass everything."""
    from scripts.check_sizing_derivation import _DERIVATION_WORDS

    assert "alpha" not in _DERIVATION_WORDS, (
        "'alpha' means edge in almost every comment this desk writes -- as a derivation keyword "
        "it would make the fence unconditionally green, which is a gate carrying zero information"
    )
