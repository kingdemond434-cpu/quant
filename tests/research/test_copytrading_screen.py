"""R0140 copytrading screen -- Stage A, and mostly a machine for refusing a tempting number.

The naive backward test on leaderboard data returns a persuasive +0.33 persistence. It is an
artifact of selecting on the outcome and of survivorship. These tests pin that the screen says so
every time, that the only unbiased design is gated behind a real forward panel, and that the
crowding gauge does not quietly report its own tail as its centre.
"""
from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta

from scripts.screen_copytrading import (
    COPIER_PROFIT_SHARE,
    MIN_COHORT,
    MIN_PANEL_GAP_DAYS,
    build_report,
    contaminated_persistence,
    crowding_index,
    forward_persistence,
)


def _trader(code, ratios):
    return {"uniqueCode": code, "nickName": code, "pnlRatio": ratios[-1], "aum": "1000",
            "copyTraderNum": "5", "leadDays": "100", "winRatio": "0.6",
            "pnlRatios": [{"beginTs": str(1_780_000_000_000 + i * 432_000_000),
                           "pnlRatio": str(r)} for i, r in enumerate(ratios)]}


def _pos(side, margin, lever, upl):
    return {"posSide": side, "margin": margin, "lever": lever, "uplRatio": upl, "upl": 0.0}


def test_the_backward_persistence_number_is_always_disqualified():
    # It is COMPUTED rather than suppressed -- a hidden statistic gets recomputed by the next
    # person without the warning attached -- but it can never read as evidence.
    leaders = [_trader(f"c{i}", [0, 0.1 * i, 0.2 * i, 0.3 * i, 0.4 * i, 0.5 * i,
                                 0.6 * i, 0.7 * i, 0.8 * i, 0.9 * i, 1.0 * i, 1.1 * i])
               for i in range(1, 12)]
    r = contaminated_persistence(leaders)
    assert r["state"] == "CONTAMINATED -- NOT EVIDENCE"
    assert len(r["disqualifiers"]) >= 4
    assert any("SELECTED ON THE OUTCOME" in d for d in r["disqualifiers"])
    assert any("SURVIVORSHIP" in d for d in r["disqualifiers"])
    assert "FORWARD panel" in r["only_valid_design"]


def test_a_single_snapshot_cannot_measure_persistence(tmp_path):
    assert forward_persistence(tmp_path)["state"] == "NO-DATA"
    (tmp_path / "data").mkdir()
    (tmp_path / "data/copytrading_panel.jsonl").write_text(json.dumps(
        {"at": datetime.now(tz=UTC).isoformat(), "traders": [_trader("a", [0, 1])]}) + "\n")
    assert forward_persistence(tmp_path)["state"] == "NO-DATA"


def test_snapshots_too_close_together_are_refused(tmp_path):
    # A shorter gap re-reads one datapoint twice and calls it two observations.
    (tmp_path / "data").mkdir()
    now = datetime.now(tz=UTC)
    rows = [{"at": (now - timedelta(days=1)).isoformat(),
             "traders": [_trader(f"c{i}", [0, 1]) for i in range(MIN_COHORT + 5)]},
            {"at": now.isoformat(),
             "traders": [_trader(f"c{i}", [0, 1]) for i in range(MIN_COHORT + 5)]}]
    (tmp_path / "data/copytrading_panel.jsonl").write_text(
        "\n".join(json.dumps(r) for r in rows) + "\n")
    r = forward_persistence(tmp_path)
    assert r["state"] == "NO-DATA" and r["gap_days"] < MIN_PANEL_GAP_DAYS


def test_traders_that_disappear_are_counted_as_failures(tmp_path):
    # THE SURVIVORSHIP FIX. Dropping them is the bug that makes the in-sample number look like an
    # edge; a lead trader who vanishes did not go on holiday.
    (tmp_path / "data").mkdir()
    now = datetime.now(tz=UTC)
    cohort = [_trader(f"c{i}", [0, 1]) for i in range(MIN_COHORT + 10)]
    rows = [{"at": (now - timedelta(days=30)).isoformat(), "traders": cohort},
            {"at": now.isoformat(), "traders": cohort[:-8]}]      # 8 vanished
    (tmp_path / "data/copytrading_panel.jsonl").write_text(
        "\n".join(json.dumps(r) for r in rows) + "\n")
    r = forward_persistence(tmp_path)
    assert r["state"] == "MEASURED"
    assert r["exited_counted_as_failures"] == 8
    assert r["exit_rate"] > 0 and "FAILURES" in r["note"]
    assert str(int(COPIER_PROFIT_SHARE * 100)) in r["hurdle"]


def test_an_undersized_cohort_reports_underpowered_not_a_number(tmp_path):
    (tmp_path / "data").mkdir()
    now = datetime.now(tz=UTC)
    small = [_trader(f"c{i}", [0, 1]) for i in range(5)]
    rows = [{"at": (now - timedelta(days=30)).isoformat(), "traders": small},
            {"at": now.isoformat(), "traders": small}]
    (tmp_path / "data/copytrading_panel.jsonl").write_text(
        "\n".join(json.dumps(r) for r in rows) + "\n")
    r = forward_persistence(tmp_path)
    assert r["state"] == "UNDERPOWERED" and "forward_spearman" not in r


def test_one_way_positions_are_not_silently_dropped_from_the_skew():
    # posSide can be "net". Counting a skew over the directional fraction while presenting it as
    # the book's skew is the quiet wrongness this desk keeps finding.
    c = crowding_index([_pos("long", 100, 10, -0.05), _pos("short", 100, 10, -0.05),
                        _pos("net", 800, 10, -0.05)])
    assert c["net_mode_share"] > 0.7
    assert c["skew"] == 0.0                              # long and short balance
    assert "excluded from the denominator" in c["skew_basis"]
    assert "UNREADABLE DIRECTION" in c["reading"]


def test_outlier_domination_is_published_not_hidden():
    # First live run: margin-weighted uplRatio read -0.97 while the MEDIAN position was -0.078.
    c = crowding_index([_pos("long", 1, 10, -0.05) for _ in range(20)]
                       + [_pos("long", 500, 50, -3.0)])
    assert c["outlier_dominated"] is True
    assert abs(c["median_uplRatio"] + 0.05) < 0.01
    assert c["margin_weighted_uplRatio"] < c["median_uplRatio"]
    assert "read the median as the centre" in c["outlier_note"]


def test_no_positions_is_blind_not_flat():
    c = crowding_index([])
    assert c["state"] == "UNMEASURED" and "not the same as flat" in c["why"]


def test_the_screen_carries_zero_promotion_authority():
    rep = build_report(leaders=[], positions=[])
    assert "never capital" in rep["authority"] and "STAGE A ONLY" in rep["authority"]
    assert "places no orders and copies no trader" in rep["authority"]
    assert "E[log wealth]" in rep["objective_test"]      # judged against the actual objective
