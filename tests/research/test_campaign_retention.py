"""R0270: the campaign observation-retention fence must fire on the regressions it exists for.

THE TEST THAT CARRIES THE WEIGHT is `test_min_length_fallback_is_not_read_as_inclusive`. The
fallback drives n_untested to ZERO while collapsing retention, so the naive check the row asked
for -- fire when untested RISES -- would have read the desk's realistic failure mode as an
improvement. That property is pinned here so no future simplification restores it.
"""
from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pytest
from scripts.check_campaign_retention import _verdict, build

from libs.research.campaign_retention import (
    MIN_CAMPAIGNS_FOR_BAND,
    SUBJECT_DB,
    audit_dbs,
    newest_reading,
)
from libs.validation.campaign_window import CAMPAIGN_ALPHA

_SCHEMA = """
CREATE TABLE audit_log (
    seq INTEGER PRIMARY KEY, id TEXT, created_at TEXT, decision_type TEXT, actor TEXT,
    inputs_json TEXT, rationale TEXT, outcome TEXT, prev_hash TEXT, row_hash TEXT
)
"""

#: The live campaign, 2026-08-05: 810 candidates, k=32, 85.8% of observations retained.
_HEALTHY = {
    "campaign_id": "camp_live", "n_candidates": 810, "n_tested": 513, "n_untested": 297,
    "obs_retained": 1_259_957, "obs_available": 1_468_341,
    "strata_alpha": CAMPAIGN_ALPHA / 32, "expected_discoveries": 326.06,
}
_HEALTHY_OUTCOME = ("32 strata, windows 4594, 3199; 513/810 candidates tested; "
                    "1,259,957/1,468,341 observations used (85.8%)")


def _make_db(path: Path, rows: list[tuple[str, dict, str]]) -> None:
    con = sqlite3.connect(path)
    con.execute(_SCHEMA)
    for i, (created, inputs, outcome) in enumerate(rows, start=1):
        con.execute(
            "INSERT INTO audit_log (seq, id, created_at, decision_type, actor, inputs_json, "
            "rationale, outcome, prev_hash, row_hash) VALUES (?,?,?,?,?,?,?,?,?,?)",
            (i, f"a{i}", created, "campaign_strata", "autodiscovery_lab",
             json.dumps(inputs), None, outcome, "p", "h"))
    con.commit()
    con.close()


@pytest.fixture
def root(tmp_path: Path) -> Path:
    (tmp_path / "data").mkdir()
    return tmp_path


def _floors(root: Path, **vals: float) -> None:
    (root / "data" / "ratchet_floors.json").write_text(
        json.dumps({k: {"value": v} for k, v in vals.items()}), "utf-8")


def _now_row(inputs: dict, outcome: str) -> tuple[str, dict, str]:
    """A row stamped far in the future, so staleness never confounds a retention assertion."""
    return ("2099-01-01T00:00:00Z", inputs, outcome)


# ---------------------------------------------------------------- reading


def test_audit_dbs_discovers_only_stores_that_have_the_table(root: Path) -> None:
    """Scope is DISCOVERED. A sqlite file without an audit_log is not an audit store."""
    _make_db(root / "data" / "real.sqlite", [_now_row(_HEALTHY, _HEALTHY_OUTCOME)])
    other = sqlite3.connect(root / "data" / "unrelated.sqlite")
    other.execute("CREATE TABLE bars (t INT)")
    other.commit()
    other.close()

    found = [p.name for p in audit_dbs(root)]
    assert found == ["real.sqlite"]


def test_newest_row_wins_across_stores(root: Path) -> None:
    _make_db(root / "data" / "a.sqlite", [("2026-08-01T00:00:00Z", _HEALTHY, "old")])
    newer = dict(_HEALTHY, campaign_id="camp_newer")
    _make_db(root / "data" / "b.sqlite", [("2026-08-05T00:00:00Z", newer, "new")])

    rd, n_dbs, n_rows = newest_reading(root)
    assert rd is not None and rd.campaign_id == "camp_newer"
    assert (n_dbs, n_rows) == (2, 2)


def test_k_strata_recovered_from_the_alpha_the_writer_emits(root: Path) -> None:
    _make_db(root / "data" / "a.sqlite", [_now_row(_HEALTHY, _HEALTHY_OUTCOME)])
    rd, _, _ = newest_reading(root)
    assert rd is not None
    assert rd.k_strata == 32
    assert rd.retained_fraction == pytest.approx(0.8580820, abs=1e-6)


# ---------------------------------------------------------------- verdicts


def test_healthy_campaign_at_its_floor_passes(root: Path) -> None:
    _make_db(root / "data" / "a.sqlite", [_now_row(_HEALTHY, _HEALTHY_OUTCOME)])
    _floors(root, campaign_obs_retained=0.858)

    rd, n_dbs, n_rows = newest_reading(root)
    status, why, _ = _verdict(rd, n_dbs, n_rows, 0.858)
    assert status == "OK", why


def test_retention_below_floor_regresses(root: Path) -> None:
    """The 82.9%-discard coming back, in its plainest form."""
    truncated = dict(_HEALTHY, obs_retained=250_000)          # 17.0% of available
    _make_db(root / "data" / "a.sqlite", [_now_row(truncated, "some other plan")])

    rd, n_dbs, n_rows = newest_reading(root)
    status, why, _ = _verdict(rd, n_dbs, n_rows, 0.858)
    assert status == "REGRESSED"
    assert "17.0%" in why and "85.8%" in why


def test_min_length_fallback_is_not_read_as_inclusive(root: Path) -> None:
    """THE LOAD-BEARING CASE (R0270).

    `plan_strata`'s fallback tests EVERY candidate at min-length: n_untested goes to 0 and
    n_tested rises to n_candidates. A fence watching for untested RISING sees that as the campaign
    covering more ground. It is the opposite -- an underpowered single stratum over truncated
    history -- and it must be named as the fallback, not as a generic regression.
    """
    fallback = dict(_HEALTHY, n_tested=810, n_untested=0, obs_retained=250_000,
                    strata_alpha=CAMPAIGN_ALPHA)              # k = 1
    outcome = ("NO stratification met the floors (min_obs=250, min_cohort=12) -- fell back to "
               "min-length 309. This campaign is underpowered and a null result from it must not "
               "be read as evidence about the price space.")
    _make_db(root / "data" / "a.sqlite", [_now_row(fallback, outcome)])

    rd, n_dbs, n_rows = newest_reading(root)
    assert rd is not None
    # The naive check the row asked for would have stayed silent here...
    assert rd.n_untested == 0 and rd.n_tested == rd.n_candidates
    # ...and the fence names it anyway.
    status, why, _ = _verdict(rd, n_dbs, n_rows, 0.858)
    assert status == "FALLBACK"
    assert "TRUNCATED TO MIN-LENGTH" in why


def test_unlabelled_single_stratum_with_retention_loss_is_still_the_fallback(root: Path) -> None:
    """Structural backstop: a row written before the planner's text existed still gets caught."""
    fallback = dict(_HEALTHY, n_tested=810, n_untested=0, obs_retained=250_000,
                    strata_alpha=CAMPAIGN_ALPHA)
    _make_db(root / "data" / "a.sqlite", [_now_row(fallback, "")])

    rd, n_dbs, n_rows = newest_reading(root)
    status, _, _ = _verdict(rd, n_dbs, n_rows, 0.858)
    assert status == "FALLBACK"


def test_legitimate_single_stratum_at_full_retention_is_not_a_fallback(root: Path) -> None:
    """The structural signal is never used bare -- a k=1 plan that kept its data is healthy."""
    single = dict(_HEALTHY, n_tested=810, n_untested=0, obs_retained=1_468_341,
                  strata_alpha=CAMPAIGN_ALPHA)
    _make_db(root / "data" / "a.sqlite", [_now_row(single, "1 stratum, windows 2119")])

    rd, n_dbs, n_rows = newest_reading(root)
    status, _, _ = _verdict(rd, n_dbs, n_rows, 0.858)
    assert status == "OK"


def test_absent_and_unmeasured_are_distinct(root: Path) -> None:
    """L1.55: 'no campaign has run' and 'no store to look in' send you to different organs."""
    status_no_store, _, _ = _verdict(None, 0, 0, 0.858)
    assert status_no_store == "UNMEASURED"

    _make_db(root / "data" / "a.sqlite", [])                  # a store, no campaign rows
    rd, n_dbs, n_rows = newest_reading(root)
    status_no_campaign, why, _ = _verdict(rd, n_dbs, n_rows, 0.858)
    assert status_no_campaign == "ABSENT"
    assert "has ever written" in why


def test_malformed_row_is_not_read_past_to_a_greener_one(root: Path) -> None:
    """L2.4: a row missing the judged fields fails; it does not fall through to an older row."""
    _make_db(root / "data" / "a.sqlite", [_now_row({"campaign_id": "camp_broken"}, "x")])

    rd, n_dbs, n_rows = newest_reading(root)
    assert rd is None and n_rows == 1
    status, why, _ = _verdict(rd, n_dbs, n_rows, 0.858, n_malformed=1)
    assert status == "ABSENT"
    assert "malformed" in why


def test_stale_plan_fires(root: Path) -> None:
    _make_db(root / "data" / "a.sqlite",
             [("2020-01-01T00:00:00Z", _HEALTHY, _HEALTHY_OUTCOME)])
    rd, n_dbs, n_rows = newest_reading(root)
    status, why, _ = _verdict(rd, n_dbs, n_rows, 0.858)
    assert status == "STALE"
    assert "48h" in why


def test_no_floor_is_reported_rather_than_assumed(root: Path) -> None:
    """A metric with no recorded floor cannot regress, and must not pretend it passed one."""
    _make_db(root / "data" / "a.sqlite", [_now_row(_HEALTHY, _HEALTHY_OUTCOME)])
    rd, n_dbs, n_rows = newest_reading(root)
    status, _, nxt = _verdict(rd, n_dbs, n_rows, None)
    assert status == "NO-FLOOR"
    assert "--ratchet" in nxt


def test_zero_available_observations_has_no_denominator(root: Path) -> None:
    """L1.57: a percentage over a zero denominator is an opinion, not a measurement."""
    empty = dict(_HEALTHY, obs_available=0, obs_retained=0)
    _make_db(root / "data" / "a.sqlite", [_now_row(empty, "x")])
    rd, n_dbs, n_rows = newest_reading(root)
    status, why, _ = _verdict(rd, n_dbs, n_rows, 0.858)
    assert status == "ABSENT"
    assert "denominator" in why


def test_artifact_carries_the_untested_share_it_does_not_fence(root: Path) -> None:
    """Published so the band can be calibrated later (R0435) -- unmeasured is not omitted."""
    _make_db(root / "data" / SUBJECT_DB, [_now_row(_HEALTHY, _HEALTHY_OUTCOME)])
    _floors(root, campaign_obs_retained=0.858)
    rep = build(root)
    assert rep["untested_fraction"] == pytest.approx(297 / 810)
    assert rep["k_strata"] == 32
    assert rep["n_audit_dbs"] == 1


# ------------------------------------------------- R0435: two populations, one event name


#: A research-lake plan: one stratum over everyone at full retention. Untested is 0.0 BY
#: CONSTRUCTION, which is what makes this population useless for calibrating a band.
_LAKE = {
    "campaign_id": "camp_lake", "n_candidates": 27, "n_tested": 27, "n_untested": 0,
    "obs_retained": 8_019, "obs_available": 8_019, "strata_alpha": CAMPAIGN_ALPHA,
}


class TestTheSubjectCannotBeOutbidByAnotherPopulation:
    """THE LIVE DEFECT (measured 2026-08-13). The lake writes ~90 rows a day and the crypto
    factory one; the fence took the newest row across ALL stores, so it reported a 23h-old lake
    plan at 100% retention while its actual subject had been silent for SEVEN DAYS.
    """

    def test_a_fresher_foreign_plan_does_not_hide_a_stale_subject(self, root: Path) -> None:
        """The exact shape of the defect: subject old, other population fresh."""
        _make_db(root / "data" / SUBJECT_DB, [("2020-01-01T00:00:00Z", _HEALTHY, "old plan")])
        _make_db(root / "data" / "sor_research.sqlite", [_now_row(_LAKE, "1 strata")])

        rep = build(root)
        assert rep["status"] == "STALE", rep["detail"]
        assert rep["campaign"]["db"] == SUBJECT_DB
        # ...and the pre-fix reading is still available, so nothing was lost, only re-subjected.
        newest, _, _ = newest_reading(root)
        assert newest is not None and newest.db == "sor_research.sqlite"

    def test_a_foreign_population_alone_is_absent_not_healthy(self, root: Path) -> None:
        """L1.28a: 92 campaigns from somewhere else is not evidence about the subject."""
        _make_db(root / "data" / "sor_research.sqlite", [_now_row(_LAKE, "1 strata")])
        rep = build(root)
        assert rep["status"] == "ABSENT"
        assert SUBJECT_DB in rep["detail"]

    def test_a_floor_the_subject_has_never_reached_is_refused_not_called_a_regression(
            self, root: Path) -> None:
        """THE FLOOR CAME FROM THE OTHER POPULATION (live: 100% floor, 99.96% subject best).

        Without this the re-subjected fence would publish REGRESSED -- a true-sounding verdict
        with the wrong cause, sending the reader to audit a length distribution that is fine.
        """
        _make_db(root / "data" / SUBJECT_DB, [_now_row(_HEALTHY, _HEALTHY_OUTCOME)])
        _floors(root, campaign_obs_retained=1.0)
        rep = build(root)
        assert rep["status"] == "FLOOR-MIS-SUBJECTED", rep["detail"]
        assert rep["floor_mis_subjected"] is True
        assert "--ratchet" in rep["next_action"]

    def test_the_mis_subjecting_is_published_even_when_staleness_outranks_it(
            self, root: Path) -> None:
        """L1.60: a ladder reports the FIRST true thing, and here two are true at once.

        If the mis-subjecting were only ever a status, fixing the staleness would surface it as a
        surprise REGRESSED on a campaign that never changed.
        """
        _make_db(root / "data" / SUBJECT_DB, [("2020-01-01T00:00:00Z", _HEALTHY, "old")])
        _floors(root, campaign_obs_retained=1.0)
        rep = build(root)
        assert rep["status"] == "STALE"
        assert rep["floor_mis_subjected"] is True

    def test_a_reachable_floor_is_not_flagged(self, root: Path) -> None:
        """The refusal must not fire on an ordinary floor, or it is noise on every healthy run."""
        _make_db(root / "data" / SUBJECT_DB, [_now_row(_HEALTHY, _HEALTHY_OUTCOME)])
        _floors(root, campaign_obs_retained=0.858)
        rep = build(root)
        assert rep["floor_mis_subjected"] is False
        assert rep["status"] == "OK", rep["detail"]


class TestTheUntestedBandIsCalibratedPerPopulationOrNotAtAll:
    """R0435 asked for a band once ~10 campaigns exist. 95 now exist and the band is STILL not
    settable, which is the finding: 92 of them have zero variance by construction.
    """

    def test_a_degenerate_population_is_not_calibratable_however_many_rows_it_has(
            self, root: Path) -> None:
        """THE TRAP: the count clears the bar and the evidence does not."""
        rows = [(f"2026-08-{d:02d}T00:00:00Z", dict(_LAKE, campaign_id=f"c{d}"), "1 strata")
                for d in range(1, 21)]
        _make_db(root / "data" / "sor_research.sqlite", rows)
        rep = build(root)
        [lake] = [p for p in rep["populations"] if p["db"] == "sor_research.sqlite"]
        assert lake["n_campaigns"] == 20 >= MIN_CAMPAIGNS_FOR_BAND
        assert lake["untested_sd"] == 0.0
        assert lake["untested_band_verdict"].startswith("DEGENERATE")
        assert rep["untested_band"]["n_populations_calibratable"] == 0

    def test_a_short_population_reports_its_shortfall_in_campaigns_not_days(
            self, root: Path) -> None:
        """L1.48 -- evidence is the clock. The shortfall is a COUNT, never a wait."""
        _make_db(root / "data" / SUBJECT_DB, [_now_row(_HEALTHY, _HEALTHY_OUTCOME)])
        [subj] = [p for p in build(root)["populations"] if p["is_subject"]]
        assert subj["untested_band_verdict"] == (
            f"UNMEASURED-BAND (1/{MIN_CAMPAIGNS_FOR_BAND} campaigns)")

    def test_real_variance_over_enough_campaigns_reads_calibratable(self, root: Path) -> None:
        """The positive control: the band becomes settable when the evidence actually arrives."""
        rows = [(f"2026-08-{d:02d}T00:00:00Z",
                 dict(_HEALTHY, campaign_id=f"c{d}", n_untested=200 + 10 * d), "32 strata")
                for d in range(1, 13)]
        _make_db(root / "data" / SUBJECT_DB, rows)
        rep = build(root)
        [subj] = [p for p in rep["populations"] if p["is_subject"]]
        assert subj["untested_band_verdict"].startswith("CALIBRATABLE")
        assert subj["untested_sd"] > 0
        assert rep["untested_band"]["n_populations_calibratable"] == 1
        # Measured, published -- and still NOT wired. Publishing a band is not enforcing one.
        assert rep["untested_band"]["wired"] is False
        assert subj["untested_band_wired"] is False

    def test_pooling_the_two_populations_is_not_what_gets_measured(self, root: Path) -> None:
        """The whole point: a pooled sd measures the population MIX, not any campaign's drift."""
        _make_db(root / "data" / SUBJECT_DB, [_now_row(_HEALTHY, _HEALTHY_OUTCOME)])
        _make_db(root / "data" / "sor_research.sqlite",
                 [(f"2026-08-{d:02d}T00:00:00Z", dict(_LAKE, campaign_id=f"c{d}"), "1 strata")
                  for d in range(1, 21)])
        pops = {p["db"]: p for p in build(root)["populations"]}
        assert pops[SUBJECT_DB]["untested_mean"] == pytest.approx(297 / 810)
        assert pops["sor_research.sqlite"]["untested_mean"] == 0.0
        # A pooled mean would be ~0.017 and belong to neither population.
        assert len(pops) == 2
