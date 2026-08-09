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

from libs.research.campaign_retention import audit_dbs, newest_reading
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
    status, why, _ = _verdict(rd, n_dbs, n_rows, 0.858)
    assert status == "ABSENT"
    assert "malformed" in why or "none carried the fields" in why


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
    _make_db(root / "data" / "a.sqlite", [_now_row(_HEALTHY, _HEALTHY_OUTCOME)])
    _floors(root, campaign_obs_retained=0.858)
    rep = build(root)
    assert rep["untested_fraction"] == pytest.approx(297 / 810)
    assert rep["k_strata"] == 32
    assert rep["n_audit_dbs"] == 1
