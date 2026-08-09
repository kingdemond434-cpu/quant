"""The alpha factory's production caller. The properties worth locking are the ones that made
the first two runs LOOK fine while doing nothing: silent category loss, and prose where a number
was expected."""

from __future__ import annotations

import json

import pytest
import scripts.run_alpha_factory as af

from libs.alpha_factory.models import AlphaCategory


class TestNovelty:
    def test_an_exact_killed_family_scores_zero(self) -> None:
        assert af._novelty("funding_carry on perps", ["funding_carry", "ts_trend"]) == 0.0

    def test_hyphens_and_underscores_are_the_same_name(self) -> None:
        assert af._novelty("funding-carry basis", ["funding_carry"]) == 0.0

    def test_something_genuinely_new_scores_high(self) -> None:
        assert af._novelty("lunar eclipse basis dislocation", ["funding_carry"]) > 0.9

    def test_an_empty_killed_list_never_penalises(self) -> None:
        assert af._novelty("anything at all", []) == 1.0

    def test_novelty_stays_in_range(self) -> None:
        killed = [f"family_{i}" for i in range(200)]
        assert 0.0 <= af._novelty("family_1 family_2 family_3", killed) <= 1.0


class TestCategoryMapping:
    def test_known_families_map_to_the_enum(self) -> None:
        cats, unmapped = af._categories(
            {"alphas": [{"category": "derivative-data"}]},
            {"queue_ranked_by_expected_research_roi": [{"family": "options"}]},
        )
        assert unmapped == []
        assert AlphaCategory.MICROSTRUCTURE in cats and AlphaCategory.OPTIONS in cats

    def test_an_unknown_family_is_REPORTED_not_swallowed(self) -> None:
        """The first version caught the exception and continued, producing '7 candidates over 0
        categories' -- a research budget allocated across nothing, printed as a clean run."""
        cats, unmapped = af._categories(
            {}, {"queue_ranked_by_expected_research_roi": [{"family": "quantum-astrology"}]})
        assert unmapped == ["quantum-astrology"]
        assert cats == [AlphaCategory.OTHER]

    def test_the_literal_string_None_is_not_a_family(self) -> None:
        cats, unmapped = af._categories(
            {}, {"queue_ranked_by_expected_research_roi": [{"family": None}]})
        assert unmapped == [] and cats == []


class TestCandidateParsing:
    def test_a_prose_rank_sorts_to_the_back_instead_of_raising(self) -> None:
        """Real data: rank is sometimes 'low-rank (near-miss; re-estimate at panel)'. Treating
        that as rank 1 would promote exactly the ideas the desk was unsure about."""
        q = {"queue_ranked_by_expected_research_roi": [
            {"id": "a", "family": "options", "rank": 1},
            {"id": "b", "family": "options", "rank": "low-rank (near-miss)"}]}
        cands = af._candidates(q, [], [])
        by = {c.idea_id: c for c in cands}
        assert by["a"].expected_edge > by["b"].expected_edge

    def test_a_deployed_family_is_not_a_portfolio_gap(self) -> None:
        q = {"queue_ranked_by_expected_research_roi": [{"id": "a", "family": "carry"}]}
        assert af._candidates(q, ["carry"], [])[0].portfolio_need == 0.0
        assert af._candidates(q, [], [])[0].portfolio_need == 1.0

    def test_non_dict_queue_entries_are_skipped(self) -> None:
        q = {"queue_ranked_by_expected_research_roi": ["oops", {"id": "a", "family": "options"}]}
        assert [c.idea_id for c in af._candidates(q, [], [])] == ["a"]

    def test_candidate_fields_respect_the_models_0_1_bounds(self) -> None:
        q = {"queue_ranked_by_expected_research_roi": [
            {"id": f"i{i}", "family": "options", "rank": i} for i in range(1, 12)]}
        for c in af._candidates(q, [], ["options"]):
            for v in (c.expected_edge, c.expected_robustness, c.novelty, c.portfolio_need):
                assert 0.0 <= v <= 1.0


class TestEndToEnd:
    def test_a_full_run_writes_a_recommendation_artifact(self, tmp_path, monkeypatch) -> None:
        agenda = {"queue_ranked_by_expected_research_roi": [
            {"rank": 1, "id": "oi_ls_liq_forward", "family": "derivative-microstructure",
             "mechanism": "open-interest and long/short imbalance"},
            {"rank": 2, "id": "opt_skew", "family": "options", "mechanism": "skew term structure"}],
            "do_not_repeat": ["funding_carry", "ts_trend"]}
        pipeline = {"alphas": [{"alpha": "crypto::cash_and_carry", "category": "crypto-sleeve",
                                "expected_sharpe": 1.2, "crowding_risk": "medium"}],
                    "deployed": ["cash_and_carry"]}
        (tmp_path / "research_agenda.json").write_text(json.dumps(agenda), "utf-8")
        (tmp_path / "alpha_pipeline.json").write_text(json.dumps(pipeline), "utf-8")
        out = tmp_path / "web" / "alpha_factory.json"
        monkeypatch.setattr(af, "_AGENDA", tmp_path / "research_agenda.json")
        monkeypatch.setattr(af, "_PIPELINE", tmp_path / "alpha_pipeline.json")
        monkeypatch.setattr(af, "_OUT", out)

        assert af.main() == 0
        d = json.loads(out.read_text("utf-8"))
        assert d["n_candidates"] == 2 and d["n_categories"] >= 1
        assert d["n_killed_families_screened"] == 2
        assert len(d["research_priorities"]) == 2
        assert len(d["assessments"]) == 2
        # every assessment must carry the engines' output, not just a ranking
        for a in d["assessments"]:
            assert "research_score" in a and "crowding_score" in a and "scalability_score" in a

    def test_missing_input_files_exit_cleanly(self, tmp_path, monkeypatch) -> None:
        monkeypatch.setattr(af, "_AGENDA", tmp_path / "nope.json")
        monkeypatch.setattr(af, "_PIPELINE", tmp_path / "also-nope.json")
        assert af.main() == 0

    def test_an_empty_queue_is_not_an_error(self, tmp_path, monkeypatch) -> None:
        (tmp_path / "a.json").write_text(json.dumps({"do_not_repeat": []}), "utf-8")
        monkeypatch.setattr(af, "_AGENDA", tmp_path / "a.json")
        monkeypatch.setattr(af, "_PIPELINE", tmp_path / "nope.json")
        assert af.main() == 0


class TestGovernanceHolds:
    def test_the_factory_still_refuses_to_promote_or_allocate_capital(self) -> None:
        """The new methods must not have opened a door the governance guards closed."""
        from libs.alpha_factory.alpha_factory_controller import AlphaFactoryController
        from libs.alpha_factory.errors import AlphaFactoryGovernanceError
        from libs.store.connection import Database
        ctl = AlphaFactoryController(Database(":memory:"))
        for fn in (ctl.promote_alpha, ctl.retire_alpha, ctl.allocate_production_capital,
                   ctl.change_risk_limit, ctl.change_validation_threshold):
            with pytest.raises(AlphaFactoryGovernanceError):
                fn()
