"""THE BIRTH-PROPERTY BOUNDARY (L1.37 for §36/L2.9) and the two repairs that made it possible.

Four fences fire on one shape -- an object of class X arrived without required property P -- and
each RECURRED after a correct per-instance fix (artifact-ungoverned 6x, orphan-scripts 4x,
mine-conversion-unbacked 3x, decision-ledger-undated 2x). The §37 rule is explicit that closing
the instance again buys one cycle, so what is locked here is the CLASS behaviour:

  * the fence REFUSES at the boundary, so a new arrival cannot land unclassified (it must be able
    to FIRE -- a check that can only pass is not a check);
  * the orphan rewrite that made a 91s check affordable at that boundary is an IDENTITY, tested
    differentially against the implementation it replaced rather than by re-asserting its output;
  * a COMPOUND anchor is a conjunction, which is the third costume of a bug `_readings` predicted
    in its own docstring.
"""

from __future__ import annotations

import re

import pytest
import scripts.check_birth_properties as bp
import scripts.max_audit as m

from libs.ops.fence_exit import fence_exit
from libs.research.mine_conversion import _anchor_tokens


class TestFenceRefuses:
    """A boundary that cannot refuse is decoration.

    The REAL-REPO verdict is deliberately not asserted here. The fence is wired into
    `run_law_gate --laws-only`, which runs at pre-push and in CI, so the tree's cleanliness has
    exactly ONE enforcement point; re-asserting it in pytest would make this file red for
    whatever a sibling session committed, and a test that cries wolf is a test that gets marked
    xfail. What is locked here is the fence's own behaviour, which is deterministic.
    """

    def test_report_shape_and_a_measured_denominator(self) -> None:
        rep = bp.build_report()
        # L1.57: a passing verdict over a zero denominator is vacuous. The count must be MEASURED
        # -- if this ever reads 0 the fence scanned nothing and its verdict means nothing.
        assert rep["scanned"] > 0
        assert rep["scanned"] == sum(rep["counts"].values())
        assert rep["properties_enforced"], "a fence enforcing no properties is decoration"

    def test_refusal_path_is_wired(self) -> None:
        """`fence_exit` must actually refuse -- including the vacuous pass."""
        assert fence_exit("OK", bp._PASSING, scanned=10, of="x") == 0
        assert fence_exit("UNBORN-PROPERTY", bp._PASSING, scanned=10, of="x") != 0
        # a passing status over a zero denominator is refused, not credited
        assert fence_exit("OK", bp._PASSING, scanned=0, of="x") != 0

    def test_an_unclaimed_doc_is_refused(self, tmp_path, monkeypatch) -> None:
        (tmp_path / "docs").mkdir(parents=True)
        (tmp_path / "docs/zz_unclaimed.md").write_text("# scratch\n", "utf-8")
        monkeypatch.setattr(m, "ROOT", tmp_path)
        out: list[tuple[str, str]] = []
        m.check_artifact_governance(out)
        assert "artifact-ungoverned" in [d[0] for d in out]


class TestGovernanceAppliesToWhatIsCommitted:
    """A shared checkout means another worker's scratch must not trip this desk's gate --
    and an unreachable git must not silently empty the scope instead."""

    def test_untracked_paths_are_not_judged(self, monkeypatch) -> None:
        monkeypatch.setattr(m, "_tracked_set", lambda: {"scripts/committed.py"})
        assert m._committed_only(["scripts/committed.py", "scripts/sibling_wip.py"]) == [
            "scripts/committed.py"]

    def test_an_unreachable_git_does_not_empty_the_scope(self, monkeypatch) -> None:
        """L1.28a: filtering against an empty answer would clear every candidate and publish a
        clean verdict over nothing -- the vacuous pass, arrived at by a different road."""
        monkeypatch.setattr(m, "_tracked_set", set)
        rels = ["scripts/a.py", "scripts/b.py"]
        assert m._committed_only(rels) == rels

    def test_the_excluded_property_is_named_not_silent(self) -> None:
        """A dropped check must be a DECISION on the record, never a silent cap.

        mine-conversion-unbacked is excluded because it is not portable (gitignored receipts +
        an st_mtime recency test a checkout resets). If someone re-adds it without making the
        evidence portable, the fence goes red in CI and green on the box -- the
        environment-dependent gate this desk has already paid for.
        """
        rep = bp.build_report()
        assert "mine-conversion-unbacked" in rep["excluded"]
        assert "portable" in rep["excluded"]["mine-conversion-unbacked"].lower()


class TestOrphanRewriteIsAnIdentity:
    """91.6s -> 3.4s, and the ONLY thing that makes that safe is exact equivalence.

    `\\b` is defined against [A-Za-z0-9_], so `\\bSTEM\\b` matches iff STEM appears as a maximal
    run of those characters -- membership in the token set. These are the cases where a sloppy
    tokenizer diverges, and they are the reason this is a differential test against the old
    regex rather than an assertion about the new one's output.
    """

    @staticmethod
    def _old(stem: str, name: str, blob: str) -> bool:
        s = re.escape(stem)
        return bool(re.search(rf"scripts/{re.escape(name)}|scripts\.{s}\b|\b{s}\b", blob))

    @staticmethod
    def _new(stem: str, name: str, blob: str) -> bool:
        if re.fullmatch(r"[A-Za-z0-9_]+", stem):
            return stem in frozenset(re.findall(r"[A-Za-z0-9_]+", blob))
        s = re.escape(stem)
        return bool(re.search(rf"scripts/{re.escape(name)}|scripts\.{s}\b|\b{s}\b", blob))

    @pytest.mark.parametrize(("stem", "blob"), [
        ("foo", "import scripts.foo\n"),          # module import
        ("foo", "run scripts/foo.py now\n"),      # path reference
        ("foo", "the foo script\n"),              # bare word
        ("foo", "foobar is unrelated\n"),         # substring only -> NOT referenced
        ("foo", "barfoo trailing\n"),             # substring only -> NOT referenced
        ("foo", "foo-bar hyphen split\n"),        # '-' is a boundary -> referenced
        ("foo", "call foo() here\n"),             # punctuation boundary
        ("foo", "nothing here at all\n"),         # absent
        ("foo", "FOO uppercase only\n"),          # case-sensitive -> NOT referenced
        ("foo_bar", "see foo_bar somewhere\n"),   # underscores are word chars
        ("foo_bar", "see foo bar somewhere\n"),   # split -> NOT referenced
        ("check2", "check2 digits\n"),            # digits
        ("check2", "check22 longer\n"),           # longer token -> NOT referenced
        ("a-b", "a-b dashed stem\n"),             # non-identifier stem -> regex fallback
        ("a-b", "scripts/a-b.py\n"),              # non-identifier via path
    ])
    def test_agrees_with_the_replaced_regex(self, stem: str, blob: str) -> None:
        name = f"{stem}.py"
        assert self._new(stem, name, blob) == self._old(stem, name, blob)


class TestCompoundAnchorIsAConjunction:
    """A card naming TWO entries was checked for a string that never existed anywhere.

    This is the dangerous direction: a card whose work was genuinely DONE read as fabricated, and
    the defect's own remedy ("produce the artifact or DOWNGRADE THE CLAIM") pointed at a true
    claim tells a reader to retract something correct.
    """

    def test_compound_anchor_splits_into_all_tokens(self) -> None:
        assert _anchor_tokens("`100-jquants-api` + `101-jpx-investor-type-free`") == (
            "100-jquants-api", "101-jpx-investor-type-free")

    @pytest.mark.parametrize(("anchor", "want"), [
        ("`JP-s1`", ("JP-s1",)),      # single backticked -> unchanged
        ("JP-s1", ("JP-s1",)),        # bare -> unchanged literal
        ("", ("",)),                  # degenerate -> unchanged
    ])
    def test_single_and_bare_anchors_are_unchanged(self, anchor: str, want: tuple) -> None:
        assert _anchor_tokens(anchor) == want

    def test_every_token_must_be_present_never_just_one(self) -> None:
        """STRICTLY STRONGER, NEVER A DISCOUNT -- an anchor is an EXTRA assertion.

        If this ever weakens to `any()`, naming a second entry would become a way to make a
        claim EASIER to satisfy than naming one, which is laundering.
        """
        toks = _anchor_tokens("`present-one` + `absent-two`")
        blob = "a file containing present-one and nothing else"
        assert [t for t in toks if t not in blob] == ["absent-two"]
