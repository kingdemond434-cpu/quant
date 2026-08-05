"""THE CHAIN BETWEEN MINING AND A SURVIVOR -- every link that failed silently, pinned.

WHY THIS FILE EXISTS. On 2026-08-05 the desk held 120 scored screen cells, twelve forward slots,
and had never started a single forward clock in its life. Four independent defects, each failing
CLOSED and each reporting nothing:

  1. NO CONVERTER. `finalize_axis_screens` speaks one schema; every newer screen writes its own.
     114 of 120 cells were unreadable -- not refuted, UNREAD.
  2. ADMISSION GATED ON A STAGE-A VERDICT. `verdict_adjusted.startswith("SCREEN-INTERESTING")`,
     which the two-stage law forbids: Stage A is a ranking device with ZERO promotion authority,
     so gating on it hands the ranking device exactly the authority the law withholds.
  3. ABSENT READ AS UNKNOWN. Eight state files that had never been written marked the cohort
     `complete=False`, and `free_slots` collapses to zero on an incomplete cohort -- permanently.
  4. EVIDENCE MAP HARDCODED. Eight names, eight artifacts; a sleeve spawned afterwards could never
     publish a day count, so it could never accrue and never resolve.

The desk then read the silence as "no edges exist". It was reading its own closed door. Every test
below fails if any link closes again, and none of them asserts anything about an effect SIZE -- a
desk with zero real edges must pass this file completely.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from libs.research.paper_sleeves import (
    NON_ADMISSIBLE_PREFIXES,
    Candidate,
    decide,
    family_root,
    free_slots,
    parse_screen_verdicts,
)
from libs.research.screen_conversion import canonical_row, convert_all, discover, is_scored_row
from libs.research.slot_admission import MAX_RESOLVE_DAYS, forward_resolution_days, rank


def _cell(**kw: object) -> dict:
    base = {"name": "sig_a", "n": 1000, "n_eff": 1000.0, "ic": 0.05, "horizon_days": 1.0,
            "sharpe_momentum": 0.8, "sharpe_reversal": -0.8, "verdict": "SCREEN-WEAK",
            "decontam_passed": True, "implausible_leak": False}
    base.update(kw)
    return base


def _screen(tmp: Path, axis: str, trials: list[dict], **top: object) -> Path:
    d = tmp / "reports/axis_screens"
    d.mkdir(parents=True, exist_ok=True)
    p = d / f"{axis}.json"
    p.write_text(json.dumps({"axis": axis, "trials": trials, **top}), "utf-8")
    return p


class TestLink1Conversion:
    """A screen that writes its own schema must not be invisible."""

    def test_a_foreign_schema_is_discovered_without_being_named(self, tmp_path: Path) -> None:
        """THE REGRESSION. Discovery walks the tree and tests rows for the scoring signature. A
        screen invented tomorrow under a name nobody anticipated must be found by the same walk --
        an artifact allow-list is how 114 cells went unread for the desk's whole life."""
        (tmp_path / "data").mkdir()
        (tmp_path / "data/some_screen_nobody_listed.json").write_text(
            json.dumps({"mechanism_class": "novel", "whatever_key": [_cell(name=f"c{i}")
                                                                    for i in range(5)]}), "utf-8")
        hits = discover(tmp_path)
        assert [h["key"] for h in hits] == ["whatever_key"]
        assert hits[0]["n_rows"] == 5

    def test_rows_the_screen_declined_to_score_do_not_delete_the_ones_it_scored(
            self, tmp_path: Path) -> None:
        """A plain majority test cost a whole artifact: unlock_event_screen holds 27 cells of which
        the screen itself declined to score 15 ('UNDERPOWERED: <20 events', no t-stat emitted), so
        12 < 15 discarded the file and the 12 REAL measurements vanished behind the 15 the screen
        had already judged unscoreable. 'Not scored' and 'not a screen' are different facts."""
        (tmp_path / "data").mkdir()
        scored = [_cell(name=f"s{i}", category="x", window_days=1) for i in range(12)]
        declined = [{"category": "x", "window_days": 1, "n_events": 3, "verdict": "UNDERPOWERED"}
                    for _ in range(15)]
        (tmp_path / "data/unlockish.json").write_text(
            json.dumps({"cells": scored + declined}), "utf-8")
        hits = discover(tmp_path)
        assert len(hits) == 1, "the scored cells must survive their unscoreable siblings"
        assert hits[0]["n_rows"] == 12
        assert hits[0]["n_unscored"] == 15, "and the shortfall must be COUNTED, never silent"

    def test_a_config_block_is_not_mistaken_for_a_screen(self, tmp_path: Path) -> None:
        (tmp_path / "data").mkdir()
        (tmp_path / "data/conf.json").write_text(
            json.dumps({"settings": [{"n": 1, "ic": 2}, {"unrelated": True}, {"other": 1}]}),
            "utf-8")
        assert discover(tmp_path) == []

    def test_every_converted_name_is_unique_within_its_artifact(self, tmp_path: Path) -> None:
        """A NAME THAT IS NOT UNIQUE IS NOT AN IDENTITY. Omitting `target` collapsed all 66
        vol-risk-premium cells to 33 names, so each forward clock re-found whichever of two
        hypotheses came first in the file -- one testing short-vol carry, the other the
        underlying's return -- and nothing said so, because both rows parse cleanly."""
        (tmp_path / "data").mkdir()
        rows = [_cell(name=None, market="AVAX:t90", construction="iv_level",
                      target=t, level="per_market", ic=0.2)
                for t in ("short_vol_carry", "underlying_return")]
        for r in rows:
            r.pop("name")
        (tmp_path / "data/vrpish.json").write_text(json.dumps({"rows": rows}), "utf-8")
        trials = convert_all(tmp_path)["payloads"][0]["trials"]
        names = [t["name"] for t in trials]
        assert len(set(names)) == len(names), f"colliding identities: {names}"

    def test_indistinguishable_rows_are_marked_rather_than_silently_renumbered(
            self, tmp_path: Path) -> None:
        (tmp_path / "data").mkdir()
        rows = [{"n": 100, "n_eff": 100.0, "ic": 0.1, "horizon_days": 1.0} for _ in range(3)]
        (tmp_path / "data/twins.json").write_text(json.dumps({"rows": rows}), "utf-8")
        trials = convert_all(tmp_path)["payloads"][0]["trials"]
        assert all("name_collision" in t for t in trials), (
            "a suffix by position is NOT a stable identity and the artifact must say so")

    def test_a_derived_ic_is_flagged_and_never_laundered(self) -> None:
        row = {"t_stat": 2.0, "n_effective": 100.0, "window_days": 1}
        out = canonical_row(row, 0)
        assert out["ic"] == pytest.approx(0.2)
        assert "ic_derived_from" in out, "a reconstructed number must never read as a measured one"

    def test_an_unmeasured_sharpe_is_zero_so_it_can_never_promote(self) -> None:
        out = canonical_row({"ic": 0.9, "n": 100, "n_eff": 100.0}, 0)
        assert out["sharpe_momentum"] == 0.0 and out["sharpe_reversal"] == 0.0
        assert any("Sharpe" in u for u in out["unmapped"])

    def test_a_declared_lookahead_control_is_disqualified_at_conversion(self) -> None:
        out = canonical_row(_cell(alignment={"is_lookahead_control": True}), 0)
        assert out["is_candidate"] is False
        assert "conversion_disqualified" in out

    def test_a_broken_verdict_is_disqualified_but_a_weak_one_is_not(self) -> None:
        """THE MEDALLION LINE. TIMING-ARTIFACT means the number does not mean what it says.
        SCREEN-UNDERPOWERED means the screen could not SEE -- of 228 recorded negatives only 50
        were powered, and refusing those a forward clock is how a desk guarantees zero
        discoveries."""
        assert canonical_row(_cell(verdict="TIMING-ARTIFACT"), 0)["is_candidate"] is False
        for weak in ("SCREEN-WEAK", "SCREEN-UNDERPOWERED", "SCREEN-UNRATED"):
            assert canonical_row(_cell(verdict=weak), 0).get("is_candidate") is not False, weak

    def test_a_scored_row_needs_both_an_effect_and_a_size(self) -> None:
        assert is_scored_row({"ic": 0.1, "n": 10})
        assert not is_scored_row({"ic": 0.1})
        assert not is_scored_row({"n": 10})


class TestLink2Admission:
    """Stage A ranks. It does not promote, and it does not gate promotion either."""

    def test_a_weak_candidate_is_admissible(self, tmp_path: Path) -> None:
        """THE REGRESSION THAT COST EVERYTHING: admission required verdict_adjusted to start with
        SCREEN-INTERESTING. Of 120 scored cells NONE carried it, so zero were ever admitted, so
        ten of twelve slots sat idle and no clock ever started."""
        _screen(tmp_path, "ax", [{**_cell(), "verdict_adjusted": "SCREEN-WEAK",
                                  "is_candidate": True}])
        got = parse_screen_verdicts(tmp_path / "reports/axis_screens")
        assert got["status"] == "OK", got.get("why")
        assert [c.trial for c in got["candidates"]] == ["sig_a"]

    def test_an_underpowered_candidate_is_admissible(self, tmp_path: Path) -> None:
        _screen(tmp_path, "ax", [{**_cell(), "verdict_adjusted": "SCREEN-UNDERPOWERED",
                                  "is_candidate": True}])
        assert parse_screen_verdicts(tmp_path / "reports/axis_screens")["status"] == "OK"

    @pytest.mark.parametrize("bad", NON_ADMISSIBLE_PREFIXES)
    def test_a_broken_measurement_is_never_admissible(self, tmp_path: Path, bad: str) -> None:
        _screen(tmp_path, "ax", [{**_cell(), "verdict_adjusted": f"{bad} (whatever)",
                                  "is_candidate": True}])
        got = parse_screen_verdicts(tmp_path / "reports/axis_screens")
        assert got["status"] == "NO-CANDIDATES", f"{bad} must never reach a forward slot"

    def test_a_control_flagged_upstream_is_never_admissible(self, tmp_path: Path) -> None:
        _screen(tmp_path, "ax", [{**_cell(), "verdict_adjusted": "SCREEN-WEAK",
                                  "is_candidate": False}])
        assert parse_screen_verdicts(tmp_path / "reports/axis_screens")["status"] == "NO-CANDIDATES"

    def test_horizons_and_parameters_of_one_signal_are_one_family(self) -> None:
        """Six rows of one hypothesis would otherwise consume SIX of twelve slots and charge the
        cohort six times for one bet."""
        roots = {family_root(f"liq_reversion_BTCUSDT_{h}_S={s}")
                 for h in ("5m", "15m", "30m") for s in ("order-side", "position-side")}
        assert roots == {"liq_reversion_btcusdt"}

    def test_distinct_assets_and_constructions_are_NOT_one_family(self) -> None:
        """THE OPPOSITE ERROR, and it cost more. Taking the first segment assumed segment one is
        the signal name -- false for `per_market|AVAX:t90|iv_level|short_vol_carry`, which begins
        with the LEVEL. All 64 market/construction/target combinations collapsed to the single
        root `per_market`, so 64 independent hypotheses fought over ONE slot."""
        names = ["per_market|AVAX:t90|iv_level|short_vol_carry",
                 "per_market|AVAX:t90|iv_level|underlying_return",
                 "per_market|BTC:t180|vrp_log_ratio|short_vol_carry",
                 "pooled|book|vrp_log_ratio|underlying_return"]
        assert len({family_root(n) for n in names}) == len(names)

    def test_a_causal_build_and_its_control_share_a_family(self) -> None:
        assert (family_root("etf_creation_pressure|causal|h1d")
                == family_root("etf_creation_pressure|lookahead_control|h5d"))


class TestLink3SlotsAndTheBoundedUnknown:
    def test_absent_sources_do_not_freeze_admission(self) -> None:
        """An unknown that can be RESOLVED must be resolved (L1.54). Eight state files that had
        never been written marked the cohort incomplete, and free_slots collapses to zero on an
        incomplete cohort -- so ten idle slots could never be filled, for ever."""
        n, why = free_slots({"cap": 12, "m_concurrent": 2, "m_upper": 2, "complete": True})
        assert n == 10, why

    def test_an_unreadable_source_is_bounded_not_surrendered_to(self) -> None:
        """m_upper adds each unreadable source's own maximum, so the slots it frees are free NO
        MATTER what those sources hold -- and the bar is computed from the worst case."""
        n, why = free_slots({"cap": 12, "m_concurrent": 2, "m_upper": 5, "complete": False,
                             "unknown_sources": ["a", "b", "c"]})
        assert n == 7 and "bounded" in why

    def test_the_cap_is_never_breached_on_a_saturating_bound(self) -> None:
        n, _ = free_slots({"cap": 12, "m_concurrent": 2, "m_upper": 14, "complete": False})
        assert n == 0

    def test_a_legacy_payload_without_the_bound_keeps_the_old_refusal(self) -> None:
        """Fail-safe direction preserved: a registry that cannot bound its unknown must not have
        that read as permission."""
        n, _ = free_slots({"cap": 12, "m_concurrent": 2, "complete": False})
        assert n == 0

    def test_the_bar_is_computed_from_the_upper_bound_never_the_counted_one(self) -> None:
        """UNDERSTATING m LOOSENS EVERY BAR -- the phantom-edge direction. `complete=False` was
        published NEXT TO the loose number rather than instead of it, and every caller kept using
        the loose one."""
        import libs.research.slot_registry as sr
        src = Path(sr.__file__).read_text("utf-8")
        body = src.split("def concurrent_m", 1)[1].split("def ", 1)[0]
        code = "\n".join(ln for ln in body.splitlines() if not ln.strip().startswith("#"))
        assert "m_upper" in code and "m_concurrent" not in code


class TestLink4EVRankingIsByTimeNotStrength:
    def test_a_weak_effect_on_a_fast_bar_outranks_a_strong_one_on_a_slow_bar(self) -> None:
        """The whole reordering. A slot's scarce resource is CALENDAR TIME: the 5-minute
        liquidation cell at |ic| 0.0172 settles in 45 days; a daily cell at |ic| 0.10 needs years.
        Significance-ranking inverts that exactly."""
        fast, _, _ = forward_resolution_days(0.0172, 5 / (60 * 24))
        slow, _, _ = forward_resolution_days(0.10, 1.0)
        assert fast < slow

    def test_a_zero_effect_is_unresolvable_rather_than_instant(self) -> None:
        """Rounding a measured nothing to a finite wait would let it outrank a measured
        something."""
        days, needed, _ = forward_resolution_days(0.0, 1.0)
        assert days == float("inf") and needed == float("inf")

    def test_an_unaffordable_candidate_is_excluded_with_a_cost_reason_not_a_strength_one(
            self) -> None:
        out = rank([{"name": "slow", "ic": 1e-4, "horizon_days": 1.0, "n_eff": 10}], n_slots=5)
        assert out["admitted"] == []
        why = out["excluded"][0]["why"]
        assert "UNAFFORDABLE" in why and "COST fence, not a strength bar" in why

    def test_the_cost_fence_is_a_decade_not_a_significance_threshold(self) -> None:
        assert MAX_RESOLVE_DAYS >= 3650.0

    def test_one_mechanism_cannot_take_every_slot(self) -> None:
        """Twelve clocks on one mechanism is ONE bet measured twelve times."""
        cands = [{"name": f"c{i}", "ic": 0.3, "horizon_days": 1.0, "n_eff": 100,
                  "mechanism_class": "vrp"} for i in range(10)]
        cands += [{"name": "other", "ic": 0.3, "horizon_days": 1.0, "n_eff": 100,
                   "mechanism_class": "flow"}]
        out = rank(cands, n_slots=6)
        used = [r["mechanism"] for r in out["admitted"]]
        assert used.count("vrp") <= out["mechanism_cap"]
        assert "flow" in used, "the orthogonal mechanism must not be crowded out"

    def test_the_mechanism_cap_is_derived_not_hardcoded(self) -> None:
        wide = rank([{"name": f"c{i}", "ic": 0.3, "horizon_days": 1.0, "n_eff": 99,
                      "mechanism_class": f"m{i}"} for i in range(8)], n_slots=8)
        assert wide["mechanism_cap"] == 1
        narrow = rank([{"name": f"c{i}", "ic": 0.3, "horizon_days": 1.0, "n_eff": 99,
                        "mechanism_class": "one"} for i in range(8)], n_slots=8)
        assert narrow["mechanism_cap"] == 8

    def test_a_contaminated_cell_never_outranks_a_clean_one_that_settles_as_fast(self) -> None:
        """Spending a slot on a contaminated cell buys a confident answer about an artifact."""
        out = rank([{"name": "dirty", "ic": 0.2, "horizon_days": 1.0, "n_eff": 50,
                     "decontam_passed": False},
                    {"name": "clean", "ic": 0.2, "horizon_days": 1.0, "n_eff": 50}], n_slots=1)
        assert [r["name"] for r in out["admitted"]] == ["clean"]

    def test_every_unadmitted_candidate_carries_its_reason(self) -> None:
        out = rank([{"name": f"c{i}", "ic": 0.3, "horizon_days": 1.0, "n_eff": 99,
                     "mechanism_class": "m"} for i in range(4)], n_slots=1)
        assert all(r["deferred_because"] for r in out["deferred"])
        assert len(out["admitted"]) + len(out["deferred"]) + len(out["excluded"]) == 4

    def test_a_cell_with_no_measurable_horizon_is_last_in_line_not_refuted(self) -> None:
        """UNMEASURED COST AND MEASURED-TOO-HIGH COST ARE DIFFERENT FACTS (L1.41). The second is
        excluded on economics; the first is only unjudged, so it sorts behind every candidate with
        a known wait and takes a slot that would otherwise sit IDLE."""
        out = rank([{"name": "x", "ic": 0.2, "n_eff": 10}], n_slots=3)
        assert [r["name"] for r in out["admitted"]] == ["x"]
        assert "UNRANKED" in out["admitted"][0]["why"]
        assert "not a judgement on the hypothesis" in out["admitted"][0]["why"].lower()

    def test_an_unranked_cell_never_jumps_ahead_of_one_with_a_known_wait(self) -> None:
        out = rank([{"name": "unranked", "ic": 0.2, "n_eff": 10},
                    {"name": "known", "ic": 0.2, "horizon_days": 1.0, "n_eff": 10}], n_slots=1)
        assert [r["name"] for r in out["admitted"]] == ["known"]


class TestTheChainEndToEnd:
    def test_a_weak_but_fast_candidate_reaches_a_slot(self, tmp_path: Path) -> None:
        """The end-to-end assertion the desk could not make for its entire life: a SCREEN-WEAK cell
        on an idle cohort becomes a spawned forward clock."""
        _screen(tmp_path, "ax", [{**_cell(ic=0.05, horizon_days=1.0),
                                  "verdict_adjusted": "SCREEN-WEAK", "is_candidate": True}],
                mechanism_class="m")
        parsed = parse_screen_verdicts(tmp_path / "reports/axis_screens")
        out = decide(parsed["candidates"], set(),
                     {"cap": 12, "m_concurrent": 2, "m_upper": 2, "complete": True})
        assert [c.trial for c in out["spawn"]] == ["sig_a"], out["why_free"]

    def test_a_candidate_carries_the_provenance_a_forward_runner_needs(self,
                                                                      tmp_path: Path) -> None:
        """A sleeve that cannot name its origin is a clock nobody can run: born, registered,
        paying multiplicity, never breathing."""
        _screen(tmp_path, "ax", [{**_cell(), "verdict_adjusted": "SCREEN-WEAK",
                                  "is_candidate": True}],
                converted_from="data/src.json", converted_key="rows")
        c = parse_screen_verdicts(tmp_path / "reports/axis_screens")["candidates"][0]
        assert c.origin_artifact == "data/src.json" and c.origin_key == "rows"

    def test_two_cells_from_one_converted_artifact_are_not_duplicates_of_each_other(
            self, tmp_path: Path) -> None:
        """Axis was once a dedupe key. With conversion in place a single artifact carries dozens of
        independent hypotheses under one axis name, so the first spawn would have blocked every
        other cell in its own file."""
        _screen(tmp_path, "ax", [
            {**_cell(name="alpha_one"), "verdict_adjusted": "SCREEN-WEAK", "is_candidate": True},
            {**_cell(name="beta_two"), "verdict_adjusted": "SCREEN-WEAK", "is_candidate": True}])
        parsed = parse_screen_verdicts(tmp_path / "reports/axis_screens")
        out = decide(parsed["candidates"], set(),
                     {"cap": 12, "m_concurrent": 0, "m_upper": 0, "complete": True})
        assert len(out["spawn"]) == 2, out["duplicates"]

    def test_a_standing_hypothesis_is_never_spawned_twice(self, tmp_path: Path) -> None:
        _screen(tmp_path, "ax", [{**_cell(), "verdict_adjusted": "SCREEN-WEAK",
                                  "is_candidate": True}])
        parsed = parse_screen_verdicts(tmp_path / "reports/axis_screens")
        c: Candidate = parsed["candidates"][0]
        out = decide(parsed["candidates"], {c.root},
                     {"cap": 12, "m_concurrent": 0, "m_upper": 0, "complete": True})
        assert out["spawn"] == [] and out["duplicates"]


class TestLink5AccrualActuallyAdvances:
    """The last link, and the one it is easiest to claim without ever having seen it work.

    A spawned clock that reports NO-EVIDENCE forever looks identical whether the runner is correct
    and the source simply has not regenerated, or the runner is broken. Only feeding it a GROWN
    source distinguishes those, and until that is done "the pipeline works" is an assertion.
    """

    @staticmethod
    def _sleeve(tmp: Path, *, n: float, ic: float, base_n: float, base_ic: float) -> dict:
        import scripts.run_paper_sleeve_forward as F

        (tmp / "data").mkdir(parents=True, exist_ok=True)
        (tmp / "data/src.json").write_text(json.dumps({"rows": [
            {"name": "sig_a", "n": n, "n_eff": n, "ic": ic, "horizon_days": 1.0},
            {"name": "other", "n": 10, "n_eff": 10.0, "ic": 0.01, "horizon_days": 1.0}]}), "utf-8")
        (tmp / "data/shadow_sleeves.json").write_text(json.dumps(["s1"]), "utf-8")
        (tmp / "data/s1_shadow_state.json").write_text(json.dumps({
            "shadow_start": "2026-08-01T00:00:00+00:00", "trial": "sig_a",
            "origin_artifact": "data/src.json", "origin_key": "rows",
            "baseline": {"n_eff": base_n, "ic": base_ic, "horizon_days": 1.0}}), "utf-8")
        return F.run(tmp)["sleeves"]["s1"]

    def test_a_grown_source_makes_the_clock_accrue(self, tmp_path: Path) -> None:
        row = self._sleeve(tmp_path, n=150.0, ic=0.20, base_n=100.0, base_ic=0.10)
        assert row["evidence"] == "ACCRUING"
        assert row["rows_added"] == 50.0
        # (150*0.20 - 100*0.10) / 50 = 0.40 -- the increment implied by the two sample statistics
        assert row["ic_forward_estimate"] == pytest.approx(0.40)
        assert "DERIVED BY DIFFERENCE" in row["ic_forward_basis"], (
            "an estimate that reads as a measurement is the phantom-edge direction")
        assert 0.0 < row["progress_to_resolution"] <= 1.0

    def test_an_ungrown_source_is_no_evidence_not_zero_effect(self, tmp_path: Path) -> None:
        """Day one, and every day a collector did not run. An IC over an empty window is a
        fabricated number, so none is reported."""
        row = self._sleeve(tmp_path, n=100.0, ic=0.10, base_n=100.0, base_ic=0.10)
        assert row["evidence"] == "NO-EVIDENCE"
        assert "ic_forward_estimate" not in row
        assert row["n_needed_for_forward_rejection"] > 0

    def test_a_vanished_cell_is_unknown_not_a_measured_zero(self, tmp_path: Path) -> None:
        """A fail-open here would turn a broken reference into 'no effect found' -- a false
        negative wearing a result's clothes. It caught seven real ones on 2026-08-05."""
        import scripts.run_paper_sleeve_forward as F

        self._sleeve(tmp_path, n=150.0, ic=0.2, base_n=100.0, base_ic=0.1)
        (tmp_path / "data/src.json").write_text(json.dumps({"rows": [
            {"name": "renamed", "n": 150, "n_eff": 150.0, "ic": 0.2, "horizon_days": 1.0}]}),
            "utf-8")
        row = F.run(tmp_path)["sleeves"]["s1"]
        assert row["evidence"] == "SOURCE-GONE"
        assert "rows_added" not in row, "a vanished source must not report an accrual of any size"

    def test_progress_is_measured_against_the_cohorts_own_holm_bar(self, tmp_path: Path) -> None:
        """The wait must be priced at the bar the clock will ACTUALLY have to clear, not a
        friendlier one -- otherwise 'progress' counts down to a threshold nobody enforces."""
        import scripts.run_paper_sleeve_forward as F

        from libs.validation.forward_stats import holm_bar

        self._sleeve(tmp_path, n=150.0, ic=0.20, base_n=100.0, base_ic=0.10)
        payload = F.run(tmp_path)
        row = payload["sleeves"]["s1"]
        # Read m from the PAYLOAD, not from a default in the assertion: a test that supplies its
        # own fallback for the number under test can pass while the runner supplies nothing.
        assert payload["m_cohort"] >= 1
        assert row["forward_bar_z"] == holm_bar(payload["m_cohort"], 1)
        expected = (holm_bar(payload["m_cohort"], 1) / 0.20) ** 2
        assert row["n_needed_for_forward_rejection"] == pytest.approx(expected, rel=1e-3)

    def test_the_observation_ledger_is_append_only(self, tmp_path: Path) -> None:
        """A forward clock whose history can be silently rewritten is not evidence."""
        import scripts.run_paper_sleeve_forward as F

        self._sleeve(tmp_path, n=150.0, ic=0.2, base_n=100.0, base_ic=0.1)
        F.run(tmp_path)
        lines = (tmp_path / F.LEDGER).read_text("utf-8").strip().splitlines()
        assert len(lines) == 2, "each pass must APPEND its reading, never replace the history"
