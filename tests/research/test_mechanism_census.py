"""The census is a measurement instrument, so these tests pin its MEASUREMENT properties.

Four properties carry the whole instrument, and each is a way it could quietly lie:

  1. A REPARAMETERISATION IS NOT A SECOND MECHANISM. If 20-day and 50-day breakout ever read as
     two classes, every number downstream inflates and the census reports coverage the desk does
     not have -- which is the exact illusion it was built to remove.
  2. DIVERSITY MUST FALL WHEN SUPPLY CONCENTRATES, and must not rise merely because volume did.
  3. AN UNTESTED CLASS MUST NEVER READ AS A FAILED ONE. "We looked and found nothing" and
     "nobody has looked" are different states; conflating them turns a starved funnel into a
     closed question.
  4. THE SCHEMA MUST BE STABLE, because the artifact is read by things that are not this test.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import ClassVar

import pytest

from libs.research.mechanism_census import (
    CLASS_BY_ID,
    DEPTH_MIN_CONSTRUCTIONS,
    SCHEMA_VERSION,
    TAXONOMY,
    CandidateEvidence,
    CensusReport,
    ClassCensus,
    Coverage,
    DataAvailability,
    Verdict,
    _class_census,
    census,
    classify,
    collect_evidence,
    measure_diversity,
    rank_gaps,
)

ROOT = Path(__file__).resolve().parents[2]


# --------------------------------------------------------------------------------- helpers ----
def _cls(source: CensusReport | list[ClassCensus], class_id: str) -> ClassCensus:
    rows = source.classes if isinstance(source, CensusReport) else source
    match = [c for c in rows if c.class_id == class_id]
    assert match, f"no census row for {class_id}"
    return match[0]


def _report_from(rows: list[CandidateEvidence]) -> list[ClassCensus]:
    return [_class_census(cls, [r for r in rows if r.class_id == cls.id], ())
            for cls in TAXONOMY]


# --------------------------------------------------------------------------------- fixtures ---
def _campaign(root: Path, rows: list[dict[str, object]]) -> None:
    path = root / "reports/real_campaign.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"pooled_by_mechanism": {"n_mechanisms": len(rows),
                                                        "rows": rows}}), "utf-8")


def _pooled(subtype: str, params: str, family: str, oos: float = 0.0,
            failed: list[str] | None = None) -> dict[str, object]:
    return {"name": f"POOLED:{subtype}:{params}", "family": family, "oos_sharpe": oos,
            "failed_gates": failed if failed is not None else ["reality_check"]}


def _ev(class_id: str, construction: str, params: str = "",
        verdict: Verdict = Verdict.REFUTED) -> CandidateEvidence:
    return CandidateEvidence(candidate_id=f"{construction}{params}", class_id=class_id,
                             construction=construction, params=params, verdict=verdict,
                             source="test")


# ---------------------------------------------------- 1. one mechanism, many parameterisations --
def test_two_parameterisations_of_one_mechanism_are_one_class(tmp_path: Path) -> None:
    """20-day and 50-day breakout: ONE class, ONE construction, TWO parameterisations."""
    _campaign(tmp_path, [_pooled("donchian", "window=20", "breakout"),
                         _pooled("donchian", "window=55", "breakout")])
    report = census(tmp_path)
    occupied = [c for c in report.classes if c.n_candidates > 0]

    assert len(occupied) == 1, f"expected one class, got {[c.class_id for c in occupied]}"
    cen = occupied[0]
    assert cen.class_id == "price_continuation"
    assert cen.n_constructions == 1, "two windows of one rule are ONE construction"
    assert cen.n_parameterisations == 2, "both parameterisations must still be counted"
    assert cen.n_candidates == 2
    assert report.diversity.n_classes_occupied == 1
    assert report.diversity.effective_classes == pytest.approx(1.0)


def test_a_whole_family_of_price_rules_collapses_to_two_classes(tmp_path: Path) -> None:
    """Eight named constructions, eight parameter settings -- and two economic mechanisms."""
    _campaign(tmp_path, [
        _pooled("ma_cross", "fast=20/slow=50", "trend"),
        _pooled("ma_cross", "fast=50/slow=200", "trend"),
        _pooled("time_series_mom", "lookback=40", "momentum"),
        _pooled("donchian", "window=20", "breakout"),
        _pooled("vwap_trend", "window=50", "trend"),
        _pooled("ict_mss_follow", "confirm=3/hold=20", "trend"),
        _pooled("zscore_fade", "window=20/z_entry=2", "mean_reversion"),
        _pooled("wyckoff_spring", "window=40/hold=5", "liquidity"),
        _pooled("ict_sweep_reversal", "confirm=2/hold=5", "liquidity"),
        _pooled("vwap_reversion", "window=50/z=1.5", "mean_reversion"),
    ])
    report = census(tmp_path)
    occupied = {c.class_id: c for c in report.classes if c.n_candidates > 0}

    assert set(occupied) == {"price_continuation", "liquidity_provision_immediacy"}
    assert occupied["price_continuation"].n_parameterisations == 6
    assert occupied["liquidity_provision_immediacy"].n_parameterisations == 4
    # ten candidates, six declared FAMILIES, two economic mechanisms: the whole point
    assert report.diversity.n_candidates == 10
    assert report.diversity.n_classes_occupied == 2


def test_declared_family_never_beats_the_implementation() -> None:
    """`drift_proxy` ships under the `carry` family and is a 200-day momentum rule.

    generators.py labels it "PROXY: no swap/rate data" in its own edge_source. Classifying it as
    carry would credit the desk with a carry test it never ran.
    """
    class_id, matched = classify("drift_proxy carry", construction="drift_proxy")
    assert class_id == "price_continuation"
    assert matched == ("construction:drift_proxy",)


def test_depth_is_denominated_in_constructions_not_candidates() -> None:
    """Reparameterising one construction can never reach TESTED-DEEP."""
    many_params = [_ev("volatility_risk_premium", "vrp_carry", f"tenor={n}")
                   for n in range(DEPTH_MIN_CONSTRUCTIONS * 5)]
    report = _report_from(many_params)
    cen = _cls(report, "volatility_risk_premium")
    assert cen.n_parameterisations >= DEPTH_MIN_CONSTRUCTIONS * 5
    assert cen.n_constructions == 1
    assert cen.coverage is Coverage.TESTED_SHALLOW

    spread = [_ev("volatility_risk_premium", f"vrp_build_{i}")
              for i in range(DEPTH_MIN_CONSTRUCTIONS)]
    assert _cls(_report_from(spread), "volatility_risk_premium").coverage is Coverage.TESTED_DEEP


# ------------------------------------------------------------------------------- 2. diversity --
def test_diversity_is_low_when_concentrated_and_high_when_spread() -> None:
    concentrated = [_ev("price_continuation", f"c{i}") for i in range(200)]
    concentrated += [_ev("liquidity_provision_immediacy", f"m{i}") for i in range(150)]
    concentrated += [_ev("market_risk_premium", f"r{i}") for i in range(50)]
    spread = [_ev(cls.id, f"{cls.id}_{i}") for cls in TAXONOMY for i in range(20)]

    low = measure_diversity(concentrated)
    high = measure_diversity(spread)

    assert low.n_candidates == 400
    assert low.n_classes_occupied == 3
    assert low.effective_classes < 3.0
    assert low.diversity < 0.15
    assert high.diversity == pytest.approx(1.0, abs=1e-6)
    assert high.diversity > low.diversity * 5


def test_diversity_is_volume_invariant() -> None:
    """Ten times the candidates in the same three classes is not ten times the search."""
    small = [_ev(c, f"{c}_{i}") for c in ("price_continuation", "derivative_carry_basis",
                                          "informed_order_flow") for i in range(4)]
    large = [_ev(c, f"{c}_{i}") for c in ("price_continuation", "derivative_carry_basis",
                                          "informed_order_flow") for i in range(40)]
    assert measure_diversity(large).diversity == pytest.approx(measure_diversity(small).diversity)
    assert measure_diversity(large).effective_classes == pytest.approx(3.0)


def test_diversity_of_an_empty_set_is_zero_not_one() -> None:
    empty = measure_diversity([])
    assert empty.n_candidates == 0
    assert empty.effective_classes == 0.0
    assert empty.diversity == 0.0


# ------------------------------------------------- 3. an untested class is never a failed one ---
def test_a_class_with_no_evidence_reads_untested_never_failed(tmp_path: Path) -> None:
    _campaign(tmp_path, [_pooled("donchian", "window=20", "breakout")])
    report = census(tmp_path)
    cen = _cls(report, "scheduled_event_diffusion")

    assert cen.coverage is Coverage.NO_CANDIDATE
    assert cen.n_candidates == 0
    assert cen.n_tested == 0
    assert cen.verdicts == {}, "an untested class has no verdict distribution at all"
    assert cen.best_oos_sharpe is None, "best OOS must be null, never 0.0, when nobody looked"
    assert "untested, not failed" in cen.note
    assert str(Verdict.REFUTED) not in json.dumps(cen.to_dict())


def test_every_untested_state_carries_zero_tests_and_zero_conclusive_verdicts() -> None:
    """The invariant, checked against the real tree rather than a fixture."""
    report = census(ROOT)
    untested = {Coverage.NO_CANDIDATE, Coverage.NAMED_UNTESTED, Coverage.NOT_READABLE_HERE}
    for cen in report.classes:
        if cen.coverage in untested:
            assert cen.n_tested == 0, f"{cen.class_id} is {cen.coverage} but reports tests"
            assert cen.best_oos_sharpe is None
            for verdict in (Verdict.SURVIVED, Verdict.REFUTED, Verdict.ARTIFACT):
                assert str(verdict) not in cen.verdicts, (
                    f"{cen.class_id} is {cen.coverage} yet carries a {verdict} verdict")


def test_ev_rejection_and_naming_are_refusals_to_test_not_results() -> None:
    rows = [_ev("macro_liquidity_transmission", f"axis_{i}", verdict=Verdict.EV_REJECTED)
            for i in range(6)]
    rows.append(_ev("macro_liquidity_transmission", "queued", verdict=Verdict.NAMED_ONLY))
    cen = _cls(_report_from(rows), "macro_liquidity_transmission")

    assert cen.n_candidates == 7
    assert cen.n_tested == 0
    assert cen.coverage is Coverage.NAMED_UNTESTED
    assert measure_diversity([r for r in rows if r.tested]).n_candidates == 0


def test_external_priors_do_not_count_as_desk_tests() -> None:
    rows = [_ev("cross_sectional_risk_premium", f"lit_{i}", verdict=Verdict.EXTERNAL_PRIOR)
            for i in range(DEPTH_MIN_CONSTRUCTIONS + 2)]
    cen = _cls(_report_from(rows), "cross_sectional_risk_premium")
    assert cen.n_external_priors == DEPTH_MIN_CONSTRUCTIONS + 2
    assert cen.n_tested == 0
    assert cen.coverage is Coverage.NAMED_UNTESTED


def test_a_missing_runtime_artifact_is_not_readable_here_not_zero(tmp_path: Path) -> None:
    _campaign(tmp_path, [_pooled("donchian", "window=20", "breakout")])
    report = census(tmp_path)

    absent = [s for s in report.sources if not s.readable]
    assert absent, "a bare tree must report its missing screen artifacts"
    assert all(s.to_dict()["status"] == "NOT-READABLE-HERE" for s in absent)

    blind = _cls(report, "informed_order_flow")
    assert blind.coverage is Coverage.NOT_READABLE_HERE
    assert blind.unreadable_sources, "the class must name the artifact it cannot see"
    assert "never zero" in blind.note
    # and it must not be RANKED, because its gap size is not visible from here
    assert blind.class_id not in {g.class_id for g in report.gaps}
    assert blind.class_id in {g.class_id for g in report.unrankable}


def test_an_empty_tree_reports_ignorance_not_failure(tmp_path: Path) -> None:
    """The extreme case: nothing on disk must produce nothing-known, never nothing-works."""
    report = census(tmp_path)
    counts = report.coverage_counts()

    assert str(Coverage.TESTED_DEEP) not in counts
    assert str(Coverage.TESTED_SHALLOW) not in counts
    assert counts[str(Coverage.NO_CANDIDATE)] + counts[str(Coverage.NOT_READABLE_HERE)] == len(
        report.classes)
    assert all(c.n_tested == 0 and c.best_oos_sharpe is None for c in report.classes)
    assert all(not c.verdicts for c in report.classes)
    assert report.diversity.diversity == 0.0
    # every class with a declared screen artifact says it cannot see it, and is left unranked
    assert {g.class_id for g in report.unrankable} == {
        c.class_id for c in report.classes if c.coverage is Coverage.NOT_READABLE_HERE}


def test_a_kill_note_cannot_talk_a_candidate_into_the_survivor_column(tmp_path: Path) -> None:
    """A real graveyard row reports that "4 survived manual review" -- of 15,256 arb SIGNALS."""
    doc = tmp_path / "docs/graveyard.md"
    doc.parent.mkdir(parents=True, exist_ok=True)
    doc.write_text(
        "| Hypothesis | Verdict | Tag | Lesson |\n"
        "|---|---|---|---|\n"
        "| retail cross venue scan arb | 15,256 signals detected, 4 survived manual review "
        "| `costs_killed_edge` | the spread IS the closed withdrawal rail, priced |\n", "utf-8")
    rows, _ = collect_evidence(tmp_path)
    assert rows, "the row must be read"
    assert all(r.verdict is not Verdict.SURVIVED for r in rows)


def test_a_not_refuted_artifact_is_not_read_as_a_kill(tmp_path: Path) -> None:
    """The unlock screen states "NOT REFUTED, NOT SUPPORTED -- UNMEASURED at the threshold"."""
    path = tmp_path / "data/unlock_event_screen.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({
        "verdict": "NOT REFUTED, NOT SUPPORTED -- UNMEASURED at the threshold that carries "
                   "the mechanism",
        "cells": [{"window_days": n} for n in range(27)]}), "utf-8")
    rows, _ = collect_evidence(tmp_path)
    unlock = [r for r in rows if r.class_id == "mechanical_supply_release"]
    assert len(unlock) == 1
    assert unlock[0].verdict is Verdict.UNDERPOWERED
    assert unlock[0].n_parameterisations == 27, "27 cells of one construction, still counted"


def test_unmatched_records_are_reported_not_invented(tmp_path: Path) -> None:
    doc = tmp_path / "docs/graveyard.md"
    doc.parent.mkdir(parents=True, exist_ok=True)
    doc.write_text(
        "| Hypothesis | Verdict | Tag | Lesson |\n"
        "|---|---|---|---|\n"
        "| zzqq wibble frobnicator | died | `unknowable` | nothing here names a mechanism |\n",
        "utf-8")
    report = census(tmp_path)
    assert [r.candidate_id for r in report.unclassified] == ["zzqq_wibble_frobnicator"]
    assert all(c.n_candidates == 0 for c in report.classes), (
        "an unclassifiable record must never be filed under the nearest plausible class")
    assert classify("zzqq wibble frobnicator") == (None, ())


# --------------------------------------------------------------------------- 4. schema stable --
_TOP_KEYS = frozenset({
    "schema_version", "generated_utc", "authority", "taxonomy_size", "depth_bar", "totals",
    "coverage_counts", "diversity", "campaign_diversity", "classes", "gaps", "unrankable_gaps",
    "sources", "unclassified", "taxonomy", "honesty_rails",
})
_CLASS_KEYS = frozenset({
    "class_id", "name", "payer", "coverage", "n_candidates", "n_tested", "n_constructions",
    "n_parameterisations", "n_external_priors", "best_oos_sharpe", "verdicts", "constructions",
    "unreadable_sources", "note",
})
_GAP_KEYS = frozenset({
    "rank", "class_id", "name", "coverage", "gap_score", "plausibility", "orthogonality",
    "feasibility", "depth_deficit", "payer", "data_required", "prior_kills", "why",
})


def test_payload_schema_is_stable() -> None:
    payload = census(ROOT).to_dict()
    assert payload["schema_version"] == SCHEMA_VERSION
    assert set(payload) == _TOP_KEYS
    assert payload["taxonomy_size"] == len(TAXONOMY)
    assert len(payload["classes"]) == len(TAXONOMY)
    for row in payload["classes"]:
        assert set(row) == _CLASS_KEYS
    for row in payload["gaps"] + payload["unrankable_gaps"]:
        assert set(row) == _GAP_KEYS
        assert set(row["data_required"]) == {"datasets", "availability", "feasibility", "note"}
        assert row["data_required"]["datasets"], "every gap must name the data it needs"
    for row in payload["sources"]:
        assert set(row) == {"path", "status", "n_records", "detail"}
        assert row["status"] in {"READABLE", "NOT-READABLE-HERE"}
    assert json.loads(json.dumps(payload)) == payload, "payload must be JSON round-trippable"


def test_payload_is_timezone_aware_utc() -> None:
    stamp = census(ROOT).to_dict()["generated_utc"]
    assert stamp.endswith("+00:00"), f"naive or non-UTC timestamp: {stamp}"


def test_taxonomy_is_well_formed() -> None:
    assert len({c.id for c in TAXONOMY}) == len(TAXONOMY)
    assert len({c.priority for c in TAXONOMY}) == len(TAXONOMY), "ties must break deterministically"
    for cls in TAXONOMY:
        assert 0.0 <= cls.plausibility <= 1.0
        assert 0.0 <= cls.orthogonality <= 1.0
        assert cls.signatures, f"{cls.id} has no signatures and can never be matched"
        assert cls.payer and cls.economic_definition
        assert cls.data.datasets
        assert CLASS_BY_ID[cls.id] is cls


def test_gap_ranking_is_ordered_and_excludes_classes_tested_to_depth() -> None:
    report = census(ROOT)
    scores = [g.gap_score for g in report.gaps]
    assert scores == sorted(scores, reverse=True)
    assert [g.rank for g in report.gaps] == list(range(1, len(report.gaps) + 1))
    deep = {c.class_id for c in report.classes if c.coverage is Coverage.TESTED_DEEP}
    assert deep.isdisjoint({g.class_id for g in report.gaps}), (
        "a class already tested to depth is not a gap")
    assert all(g.gap_score > 0.0 for g in report.gaps)


def test_the_real_tree_reads_and_the_campaign_is_concentrated() -> None:
    """The finding itself: the maximum-power campaign occupies very few economic classes.

    SKIPS RATHER THAN FAILS WHEN THE ARTIFACT IS ABSENT. `reports/` is gitignored, so a clone has
    no campaign file and this asserted `n_candidates > 0` -- reporting "the campaign is not
    concentrated" when the truth is "there is no campaign here to read". Its sibling in
    tests/validation/test_screen_admission.py already skips on exactly this absence; one of them
    was wrong, and it was this one. An absent artifact is UNMEASURED (L1.28a), and a red suite
    that means "you are on a clone" trains the desk to ignore red.
    """
    report = census(ROOT)
    campaign = report.campaign_diversity
    if campaign.n_candidates == 0:
        pytest.skip("reports/real_campaign.json absent (reports/ is gitignored) -- UNMEASURED "
                    "on this host, not a campaign that failed to concentrate")
    assert campaign.n_classes_occupied < campaign.n_classes_in_taxonomy / 3
    assert campaign.diversity < 0.30
    assert report.gaps, "there must be at least one ranked gap"


def test_rank_gaps_helper_matches_the_full_report() -> None:
    report = census(ROOT)
    ranked, unrankable = rank_gaps(report.classes, report.evidence)
    assert [g.class_id for g in ranked] == [g.class_id for g in report.gaps]
    assert [g.class_id for g in unrankable] == [g.class_id for g in report.unrankable]


class TestTheSixClassesTheTaxonomyHadNeverNamed:
    """Added 2026-08-05, answering the CRO brief's hardest question with the seat DARK.

    The census can only rank what it has named, so an absent class is not low-ranked -- it is
    INVISIBLE, and every coverage figure the desk quotes is computed against a denominator that
    silently excludes it. With the binding constraint measured as DISTINCT MECHANISM SUPPLY (44
    candidates covering 2.787 effective classes; cross-mechanism N_eff 4.08 against the ~100 a
    weak-edge portfolio needs), widening what CAN be ranked is worth more than another candidate
    inside a class already occupied.

    THE ARITHMETIC RUNS THE UNFLATTERING WAY, which is the point: 2.787 of 20 reads 13.9%, and
    2.787 of 26 reads 10.7%. Naming six classes the desk was not testing made its headline
    coverage WORSE. A coverage ratio is trivially improved by declining to name things (L1.53),
    so a taxonomy that only grows when a screen is ready is a denominator managed for appearance.

    Each entry is pinned by ID and by the DISTINCTION it claims, because the failure mode is not
    deletion -- it is somebody deciding a class is "just" an existing one and quietly merging it,
    which restores the blind spot while the class count still looks healthy.
    """

    _NEW: ClassVar[dict[str, str]] = {
        "index_reconstitution_flow": "primary_market_creation_flow",
        "treasury_cost_base_liquidation": "mechanical_supply_release",
        "estate_liquidation_distribution": "holder_cost_basis_capitulation",
        "collateral_rule_deleveraging": "positioning_crowding_unwind",
        "settlement_expiry_mechanics": "volatility_risk_premium",
        "fiscal_calendar_flow": "attention_sentiment_overreaction",
    }

    def test_all_six_are_present(self) -> None:
        missing = sorted(set(self._NEW) - {c.id for c in TAXONOMY})
        assert not missing, f"class(es) removed from the taxonomy: {missing}"

    def test_each_names_a_payer_compelled_by_something_other_than_an_opinion(self) -> None:
        """The admission test. A payer who is merely WRONG is a pattern, not a mechanism, however
        well it backtests -- so each of these must name a balance sheet, a court or a rule."""
        compelled = ("cannot", "must", "forced", "mandate", "court", "statute", "obligation",
                     "compelled", "rule", "contract", "does not")
        for cid in self._NEW:
            cls = CLASS_BY_ID[cid]
            assert any(w in cls.payer.lower() for w in compelled), (
                f"{cid}: the payer story does not name a compulsion")
            assert len(cls.payer) > 120, f"{cid}: payer story too thin to be falsifiable"

    def test_each_records_why_it_is_not_the_class_it_most_resembles(self) -> None:
        """The merge guard. Every one of these will face 'isn't that just X?', and the answer must
        live in the file rather than in whoever wrote it."""
        for cid, resembles in self._NEW.items():
            note = CLASS_BY_ID[cid].data.note.lower()
            assert resembles.split("_")[0] in note or "not " in note, (
                f"{cid} does not record how it differs from {resembles}")

    def test_each_is_testable_on_free_data(self) -> None:
        """A class the desk cannot afford to test widens the denominator without widening the
        hunt -- honest, but it would make coverage unreachable rather than merely low."""
        for cid in self._NEW:
            cls = CLASS_BY_ID[cid]
            assert cls.data.availability is DataAvailability.FREE_ACQUIRABLE, (
                f"{cid} is not free-acquirable")
            assert cls.data.datasets, f"{cid} names no datasets"

    def test_the_specific_classes_still_outrank_the_generic_price_ones(self) -> None:
        """Priority is tie-break ORDER: a promiscuous price word must never outbid a specific
        economic one. The six are data-specific, so all must sort before the price-only tail."""
        pri = {c.id: c.priority for c in TAXONOMY}
        generic = max(pri["market_risk_premium"], pri["price_continuation"])
        for cid in self._NEW:
            assert pri[cid] < generic, f"{cid} sorts after a generic price class"

    def test_priorities_remain_unique_after_the_insertion(self) -> None:
        pris = [c.priority for c in TAXONOMY]
        assert len(set(pris)) == len(pris), "ties must break deterministically"


class TestMt5NativeClasses:
    """The 2026-08-18 MT5 batch: the forced-participant classes a crypto-worded census left
    INVISIBLE. Same guard as the 2026-08-05 six -- a class added without a named compulsion, a
    merge-guard note and free data is a coverage number inflated on paper, and a class that sorts
    after a promiscuous price word is a specific mechanism a generic one can silently outbid.
    """

    _NEW_MT5: ClassVar[dict[str, str]] = {
        "fx_carry_rate_differential": "derivative_carry_basis",
        "central_bank_event_surprise": "macro_liquidity_transmission",
        "session_fix_liquidity": "liquidity_provision_immediacy",
        "commodity_inventory_supply": "mechanical_supply_release",
        "overnight_gap_risk_premium": "volatility_risk_premium",
        "producer_hedging_flow": "treasury_cost_base_liquidation",
    }

    def test_all_present(self) -> None:
        missing = sorted(set(self._NEW_MT5) - {c.id for c in TAXONOMY})
        assert not missing, f"MT5-native class(es) missing from the taxonomy: {missing}"

    def test_each_names_a_compelled_payer(self) -> None:
        compelled = ("cannot", "must", "forced", "mandate", "mandated", "court", "statute",
                     "obligation", "compelled", "rule", "contract", "does not", "regardless")
        for cid in self._NEW_MT5:
            cls = CLASS_BY_ID[cid]
            assert any(w in cls.payer.lower() for w in compelled), (
                f"{cid}: the payer story does not name a compulsion")
            assert len(cls.payer) > 120, f"{cid}: payer story too thin to be falsifiable"

    def test_each_records_why_it_is_not_the_class_it_most_resembles(self) -> None:
        for cid, resembles in self._NEW_MT5.items():
            note = CLASS_BY_ID[cid].data.note.lower()
            assert resembles.split("_")[0] in note or "not " in note, (
                f"{cid} does not record how it differs from {resembles}")

    def test_each_is_testable_on_free_data(self) -> None:
        for cid in self._NEW_MT5:
            cls = CLASS_BY_ID[cid]
            assert cls.data.availability is DataAvailability.FREE_ACQUIRABLE, (
                f"{cid} is not free-acquirable")
            assert cls.data.datasets, f"{cid} names no datasets"

    def test_they_are_mt5_native_not_crypto_reworded(self) -> None:
        """The point of the batch: each must speak an FX/metals/macro mechanism, and none may be a
        crypto class with the venue words swapped out."""
        banned = ("perp", "perpetual", "on-chain", "onchain", "binance", "bybit", "kimchi",
                  "miner reward", "block reward", "stablecoin", "wallet")
        for cid in self._NEW_MT5:
            cls = CLASS_BY_ID[cid]
            hay = (cls.payer + cls.economic_definition + " ".join(cls.signatures)).lower()
            hit = [b for b in banned if b in hay]
            assert not hit, f"{cid} still speaks crypto: {hit}"

    def test_the_specific_classes_still_outrank_the_generic_price_ones(self) -> None:
        pri = {c.id: c.priority for c in TAXONOMY}
        generic = max(pri["market_risk_premium"], pri["liquidity_provision_immediacy"],
                      pri["price_continuation"])
        for cid in self._NEW_MT5:
            assert pri[cid] < generic, f"{cid} sorts after a generic price class"

    def test_priorities_remain_unique(self) -> None:
        pris = [c.priority for c in TAXONOMY]
        assert len(set(pris)) == len(pris), "ties must break deterministically"
