"""Tests for panel evidence asymmetry + dissent scoring.

The properties that decide whether this is worth anything: a small roster is never blinded, the
same seat is not permanently the blind one, and agreement is only credited as INDEPENDENT when it
actually crossed an evidence partition."""

from __future__ import annotations

from libs.research.panel_diversity import (
    PROFILES,
    assign_profiles,
    compose_dossier,
    diversity_report,
    partition_plan,
    theme_splits,
)

_BLOCKS = {
    "narrative": "## DOSSIER\nthe desk says it is fine",
    "rulings": "## RULINGS\nprior verdicts",
    "graveyard": "## GRAVEYARD\ndead ideas",
    "source": "## SOURCE\ndef f(): ...",
}


class TestPartitionPlan:
    def test_small_roster_is_never_blinded(self) -> None:
        # with few seats every one is load-bearing for cross-referencing
        for n in (0, 1, 3, 4):
            assert partition_plan(n) == ()

    def test_partition_grows_with_roster(self) -> None:
        assert len(partition_plan(6)) == 1
        assert len(partition_plan(11)) == 2
        assert len(partition_plan(13)) == 4

    def test_majority_always_stays_full(self) -> None:
        for n in (6, 11, 13, 20):
            assert len(partition_plan(n)) < n / 2


class TestAssignment:
    def test_small_roster_all_full(self) -> None:
        seats = ["a", "b", "c"]
        assert set(assign_profiles(seats, run_key="r1").values()) == {"full"}

    def test_every_seat_gets_exactly_one_profile(self) -> None:
        seats = [f"m{i}" for i in range(13)]
        got = assign_profiles(seats, run_key="r1")
        assert set(got) == set(seats)
        assert all(v in PROFILES for v in got.values())

    def test_deterministic_within_a_run(self) -> None:
        seats = [f"m{i}" for i in range(13)]
        assert assign_profiles(seats, run_key="same") == assign_profiles(seats, run_key="same")

    def test_rotates_between_runs(self) -> None:
        # a permanently-blind seat would confound "this seat dissents" with "this seat is blind"
        seats = [f"m{i}" for i in range(13)]
        blind = set()
        for k in range(12):
            got = assign_profiles(seats, run_key=f"run{k}")
            blind |= {s for s, p in got.items() if p != "full"}
        assert len(blind) > 4, "the blind role must move around the roster"

    def test_majority_remain_full(self) -> None:
        seats = [f"m{i}" for i in range(13)]
        got = assign_profiles(seats, run_key="r")
        assert sum(1 for v in got.values() if v == "full") > len(seats) / 2


class TestComposeDossier:
    def test_full_profile_gets_everything(self) -> None:
        text = compose_dossier(_BLOCKS, "full")
        assert all(b in text for b in ("DOSSIER", "RULINGS", "GRAVEYARD", "SOURCE"))

    def test_raw_profile_sees_no_narrative(self) -> None:
        # the auditee cannot frame what it does not get to write
        text = compose_dossier(_BLOCKS, "raw")
        assert "SOURCE" in text
        assert "the desk says it is fine" not in text

    def test_narrative_profile_sees_no_source(self) -> None:
        text = compose_dossier(_BLOCKS, "narrative")
        assert "DOSSIER" in text and "def f()" not in text

    def test_profile_is_declared_to_the_seat(self) -> None:
        # a seat that does not know it is partial will hedge instead of judging
        assert "EVIDENCE PROFILE: RAW" in compose_dossier(_BLOCKS, "raw")

    def test_never_sends_an_empty_payload(self) -> None:
        text = compose_dossier({"narrative": "only this"}, "raw")
        assert "only this" in text  # falls back rather than sending a seat nothing to read

    def test_unknown_profile_degrades_to_full(self) -> None:
        assert "SOURCE" in compose_dossier(_BLOCKS, "nonsense")


class TestDissentScoring:
    def test_unanimous_theme_scores_zero_dissent(self) -> None:
        seats = {f"m{i}": ["basis"] for i in range(4)}
        (s,) = theme_splits(seats, dict.fromkeys(seats, "full"))
        assert s.n_raised == 4 and s.dissent == 0.0

    def test_even_split_scores_maximum_dissent(self) -> None:
        seats = {"a": ["x"], "b": ["x"], "c": [], "d": []}
        (s,) = theme_splits(seats, dict.fromkeys(seats, "full"))
        assert s.dissent == 1.0

    def test_lone_voice_is_low_dissent_not_high(self) -> None:
        # 1-of-12 is near-unanimous DISAGREEMENT, not a split room
        seats = {f"m{i}": (["x"] if i == 0 else []) for i in range(12)}
        (s,) = theme_splits(seats, dict.fromkeys(seats, "full"))
        assert s.dissent < 0.25

    def test_same_profile_agreement_is_not_independent(self) -> None:
        seats = {"a": ["x"], "b": ["x"]}
        (s,) = theme_splits(seats, {"a": "full", "b": "full"})
        assert s.cross_profile is False
        assert s.independent_corroboration is False

    def test_cross_profile_agreement_is_independent(self) -> None:
        # this is the entire return on partitioning the evidence
        seats = {"a": ["x"], "b": ["x"]}
        (s,) = theme_splits(seats, {"a": "full", "b": "raw"})
        assert s.independent_corroboration is True

    def test_single_seat_never_counts_as_corroboration(self) -> None:
        seats = {"a": ["x"]}
        (s,) = theme_splits(seats, {"a": "raw"})
        assert s.independent_corroboration is False


class TestDiversityReport:
    def test_unpartitioned_roster_is_called_out(self) -> None:
        seats = {f"m{i}": ["basis"] for i in range(5)}
        rep = diversity_report(seats, dict.fromkeys(seats, "full"))
        assert "one dossier read many times" in rep.verdict

    def test_partitioned_roster_reports_corroboration(self) -> None:
        seats = {"a": ["basis"], "b": ["basis"], "c": ["statistics"]}
        rep = diversity_report(seats, {"a": "full", "b": "raw", "c": "outcomes"})
        assert rep.n_independently_corroborated == 1
        assert "independent corroboration" in rep.verdict

    def test_contested_themes_are_counted(self) -> None:
        seats = {"a": ["x"], "b": ["x"], "c": [], "d": []}
        rep = diversity_report(seats, {"a": "full", "b": "raw", "c": "full", "d": "full"})
        assert rep.n_contested == 1

    def test_profile_counts_are_reported(self) -> None:
        rep = diversity_report({"a": ["x"]}, {"a": "raw", "b": "full", "c": "full"})
        assert rep.profile_counts == {"raw": 1, "full": 2}

    def test_empty_panel_owes_nothing(self) -> None:
        assert "nothing to score" in diversity_report({}, {}).verdict
