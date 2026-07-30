"""The timidity fence must FIRE, and must not fire on healthy text.

Both directions matter. A fence that never fires protects nothing; a fence that fires on the
aggressive clauses gets acknowledged into silence within a week, which is exactly how
check_orphan_code nearly died. So: an unclassified restraint trips it, a quoted-aggressive clause
does not, and an exemption whose proving phrase was rewritten away STOPS being an exemption.
"""

from __future__ import annotations

import pytest

from scripts import check_timidity_language as tl


@pytest.fixture
def const(tmp_path, monkeypatch):
    def write(body: str):
        p = tmp_path / "CONSTITUTION.md"
        p.write_text(body, "utf-8")
        monkeypatch.setattr(tl, "_CONST", p)
        return p
    return write


def test_unclassified_scope_restraint_is_caught(const):
    const("**L9.1 SOMETHING NEW.** The desk should minimise the number of subsystems it builds.\n")
    rep = tl.audit()
    assert rep["unclassified"] == ["L9.1"]


def test_clause_with_no_restraint_language_is_clean(const):
    const("**L9.2 HUNT.** Pursue every mechanism to its capacity quota, in parallel, always.\n")
    rep = tl.audit()
    assert not rep["unclassified"]
    assert rep["rows"][0]["status"] == "NO-RESTRAINT"


def test_inline_declaration_classifies(const):
    const("**L9.3 LEAN.** Minimise noise. This is not a licence for timidity: no ceiling on "
          "valuable output.\n")
    assert not tl.audit()["unclassified"]


def test_disambiguation_table_classifies(const):
    """A row in L1.28's table is what retires a genuinely misreadable principle."""
    const("**L9.4 SPARE.** Reject complexity that does not compound.\n\n"
          "**L1.28 TIMIDITY IS A SCORED DEFECT.** Table: | **L9.4** spare | misread | correct |\n")
    rep = tl.audit()
    assert not rep["unclassified"]
    assert {r["principle"]: r["status"] for r in rep["rows"]}["L9.4"] == "CLASSIFIED"


def test_aggressive_exemption_dies_when_its_proof_phrase_is_rewritten(const, monkeypatch):
    """THE SUBTLE ONE. An exemption list that outlives the text justifying it is a permanent hole:
    the clause can be rewritten into something genuinely timid while the fence keeps waving it
    through on a quote that is no longer there."""
    monkeypatch.setitem(tl._AGGRESSIVE_CONTEXT, "L9.5", "never defers hunting a mechanism")
    const("**L9.5 CAPACITY.** The desk never defers hunting a mechanism, and rejects nothing "
          "for being small.\n")
    assert not tl.audit()["unclassified"], "exemption should hold while its phrase is present"

    const("**L9.5 CAPACITY.** The desk defers small mechanisms and rejects thin edges.\n")
    rep = tl.audit()
    assert rep["unclassified"] == ["L9.5"], "exemption must lapse once its proof phrase is gone"
    assert "GONE" in next(r["via"] for r in rep["rows"] if r["principle"] == "L9.5")


def test_evidence_restraint_is_declared_not_inferred(const, monkeypatch):
    """Evidence/risk bars stay strict and need no anti-timidity rider -- but they must be DECLARED,
    so 'this one is about evidence' can never be an ad-hoc excuse for an unclassified clause."""
    const("**L9.6 BARS.** Kill weak ideas; limit what may be believed to what survived.\n")
    assert tl.audit()["unclassified"] == ["L9.6"]
    monkeypatch.setitem(tl._EVIDENCE_RESTRAINT, "L9.6", "confirmation bar")
    assert not tl.audit()["unclassified"]


def test_the_live_constitution_has_no_unclassified_restraint():
    """The real artifact: every principle in force today states which kind of restraint it is."""
    rep = tl.audit()
    assert not rep["unclassified"], (
        f"unclassified scope restraint in force: {rep['unclassified']} -- each defaults to the "
        "timid reading in practice")
    assert rep["counts"].get("CLASSIFIED", 0) >= 10, "the L1.28 table lost rows"
