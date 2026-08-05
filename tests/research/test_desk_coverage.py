"""THE WEEKLY WHOLE-DESK GRADE -- coverage that is PROVEN and an aggregate that cannot be gamed.

TWO WAYS A DESK GRADE LIES, and this file exists to stop both.

FIRST, AN ASSERTED ASPECT LIST. `capability_ratchet.ASPECTS` is a hardcoded tuple of 26. An aspect
nobody wrote into it is invisible: it scores nothing and drags no number down. Measured on the live
repo the first time this ran -- 59 of 327 surfaces rated, 268 UNRATED, including ALL NINE
constitutional laws and 150 of 158 scheduled organs. A grade reporting 5.82/10 over that surface is
not a grade of the desk, it is a grade of the part somebody remembered to list.

SECOND, AN ARITHMETIC MEAN. On the desk's own numbers it reads 5.82 while `alerting_pager` sits at
0.0 -- a desk whose pager has never delivered a page. An average lets two 10s pay for a zero, which
is backwards: capability is a CHAIN. The harmonic mean on the same numbers reads 0.98.
"""
from __future__ import annotations

from pathlib import Path

from libs.research.desk_coverage import (
    CEILING,
    SurfaceItem,
    desk_grade,
    enumerate_surface,
    harmonic,
    unclaimed,
    worklist,
)


def _aspect(key: str, score: float, artifacts: list[str] | None = None) -> dict:
    return {"key": key, "score": score, "artifacts": artifacts or [],
            "components": [], "binding_constraint": f"fix {key}", "ceiling": f"{key} at ceiling"}


class TestTheAggregateCannotBeGamedByStrongAspects:
    def test_one_zero_crushes_a_field_of_tens(self) -> None:
        """THE WHOLE POINT. A desk with a dead pager is not a 9.6/10 desk."""
        scores = [0.0, *([10.0] * 25)]
        assert sum(scores) / len(scores) > 9.5
        assert harmonic(scores) < 1.5

    def test_the_harmonic_mean_tracks_the_weakest_member(self) -> None:
        assert harmonic([10.0, 10.0, 10.0]) > 9.9
        assert harmonic([10.0, 10.0, 2.0]) < 4.5

    def test_an_empty_field_is_zero_not_an_error(self) -> None:
        assert harmonic([]) == 0.0

    def test_coverage_MULTIPLIES_the_grade_it_does_not_merely_join_it(self) -> None:
        """THE FIX MY OWN TEST FORCED. Adding coverage as one more term in the harmonic mean
        DILUTED it: five aspects at 10.0 with nine of ten surfaces unrated still graded 4.09,
        which says a desk measured on a tenth of itself is middling. It is not -- it is a desk
        nobody has measured. A score computed over 10% of the surface is worth 10% of its face
        value, and multiplying says exactly that."""
        aspects = [_aspect(f"a{i}", 10.0) for i in range(5)]
        surface = [SurfaceItem("organ", f"o{i}") for i in range(10)]
        unrated = [SurfaceItem("organ", f"o{i}") for i in range(9)]
        g = desk_grade(aspects, surface, unrated)
        assert g.arithmetic == 10.0, "every aspect is perfect"
        assert g.coverage_score <= 1.5, "and 9 of 10 surfaces are unrated"
        assert g.grade <= 1.1, "so the desk grade is a tenth of a perfect one"

    def test_zero_coverage_is_a_zero_grade_however_good_the_aspects_look(self) -> None:
        g = desk_grade([_aspect("a", 10.0)], [SurfaceItem("organ", "x")],
                       [SurfaceItem("organ", "x")])
        assert g.grade == 0.0

    def test_full_coverage_and_full_scores_do_reach_the_ceiling(self) -> None:
        """A grade that can never be 10 is as useless as one that always is."""
        aspects = [_aspect(f"a{i}", 10.0) for i in range(5)]
        surface = [SurfaceItem("organ", "o1")]
        g = desk_grade(aspects, surface, [])
        assert g.coverage_score == CEILING and g.grade > 9.9


class TestCoverageIsDerivedNotDeclared:
    def test_every_surface_kind_is_enumerated_from_the_repo(self, tmp_path: Path) -> None:
        (tmp_path / "ops").mkdir()
        (tmp_path / "ops/crontab.manifest").write_text(
            "# a comment naming scripts/not_scheduled.py\n"
            "0 5 * * * cd x && python scripts/real_organ.py\n", "utf-8")
        (tmp_path / "libs/thing").mkdir(parents=True)
        (tmp_path / "data").mkdir()
        (tmp_path / "data/some_state.json").write_text("{}", "utf-8")
        (tmp_path / "docs").mkdir()
        (tmp_path / "docs/CONSTITUTION.md").write_text("## L1.99 A LAW\ntext\n", "utf-8")
        got = {(i.kind, i.name) for i in enumerate_surface(tmp_path)}
        assert ("organ", "real_organ") in got
        assert ("subsystem", "libs/thing") in got
        assert ("artifact", "data/some_state.json") in got
        assert ("law", "L1.99") in got

    def test_a_commented_organ_is_not_counted_as_scheduled(self, tmp_path: Path) -> None:
        """A DOCUMENTED organ is not a running one, and counting prose as coverage is how a
        manifest starts lying about what the desk does."""
        (tmp_path / "ops").mkdir()
        (tmp_path / "ops/crontab.manifest").write_text(
            "# 0 5 * * * python scripts/only_in_a_comment.py\n", "utf-8")
        assert not [i for i in enumerate_surface(tmp_path) if i.kind == "organ"]

    def test_an_unclaimed_surface_is_unrated_by_default(self) -> None:
        surface = [SurfaceItem("organ", "nobody_grades_me")]
        out = unclaimed(surface, [_aspect("alerting_pager", 5.0)])
        assert [i.name for i in out] == ["nobody_grades_me"]
        assert "UNRATED SURFACE" in out[0].why_unclaimed

    def test_an_explicit_artifact_claim_is_honoured(self) -> None:
        surface = [SurfaceItem("artifact", "data/alert_canary_state.json")]
        out = unclaimed(surface, [_aspect("alerting_pager", 5.0,
                                          ["data/alert_canary_state.json"])])
        assert out == [], "an aspect that names the artifact claims it"

    def test_one_shared_word_is_not_a_claim(self) -> None:
        """`run.py` and `research_discipline` sharing a letter is not coverage. Two real words in
        common is the bar, because a loose matcher manufactures coverage out of coincidence."""
        surface = [SurfaceItem("organ", "run_something_unrelated")]
        assert unclaimed(surface, [_aspect("research_discipline", 5.0)])


class TestTheWorklistPushesEverythingAtOnce:
    def test_every_aspect_below_ceiling_appears(self) -> None:
        """The daily ratchet names ONE binding constraint. A weekly plan plans the whole surface,
        or it is the same day repeated seven times."""
        rows = worklist([_aspect("a", 1.0), _aspect("b", 9.9), _aspect("c", 10.0)], [])
        assert {r["target"] for r in rows} == {"a", "b"}

    def test_an_unrated_surface_outranks_every_low_score(self) -> None:
        """A part of the desk nobody grades cannot be KNOWN to be broken, so it is worse than a
        known 0.0."""
        rows = worklist([_aspect("worst", 0.0)],
                        [SurfaceItem("law", "L1.99", why_unclaimed="UNRATED SURFACE: ...")])
        assert rows[0]["target"] == "L1.99"
        assert rows[0]["score"] is None and "RATE IT" in rows[0]["action"]

    def test_every_row_carries_a_concrete_action(self) -> None:
        rows = worklist([_aspect("a", 3.0)], [SurfaceItem("organ", "x", why_unclaimed="w")])
        assert all(r["action"] and r["distance"] > 0 for r in rows)

    def test_an_aspect_at_ceiling_is_not_busywork(self) -> None:
        assert worklist([_aspect("done", 10.0)], []) == []
