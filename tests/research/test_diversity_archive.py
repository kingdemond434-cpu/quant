import pytest

from libs.research import diversity_archive as QD


def test_archive_preserves_distinct_niches_and_failures() -> None:
    rows = [
        {"experiment_id": "a", "source": "weather", "family": "seasonality",
         "chart": "D1", "behavior": "continuation", "asset_class": "softs",
         "verdict": "FAILED", "falsifier": "no PIT effect"},
        {"experiment_id": "b", "source": "execution", "family": "spread_state",
         "chart": "M1", "behavior": "reversal", "asset_class": "fx",
         "status": "FORWARD", "forward_r": 0.1},
    ]
    got = QD.update({}, rows)
    assert got["counts"] == {"items": 2, "occupied_niches": 2,
                              "failed_preserved": 1, "blocked_preserved": 0}
    assert got["items"]["a"]["descriptor"]["evidence_state"] == "FAILED"
    assert "archive only" in got["items"]["a"]["authority"]


def test_niche_champion_uses_evidence_then_value_without_deleting_history() -> None:
    base = {"source": "physical", "family": "inventory", "chart": "D1",
            "behavior": "reversal", "asset_class": "energy"}
    archive = QD.update({}, [{"experiment_id": "old", **base, "status": "FORWARD",
                              "forward_r": 0.1, "delta_elogw": 0.01}])
    archive = QD.update(archive, [{"experiment_id": "new", **base, "status": "FORWARD",
                                   "forward_r": 0.2, "delta_elogw": 0.02}])
    assert archive["counts"]["items"] == 2
    niche = next(iter(archive["niches"].values()))
    assert niche["champion"] == "new" and set(niche["members"]) == {"old", "new"}


def test_blocked_is_an_evidence_state_not_silent_loss() -> None:
    got = QD.update({}, [{"experiment_id": "x", "source": "filing",
                          "family": "event", "blockers": ["ACCESS_RIGHTS_UNKNOWN"]}])
    assert got["counts"]["blocked_preserved"] == 1
    assert got["items"]["x"]["descriptor"]["evidence_state"] == "ACCESS_BLOCKED"


def test_enrollment_is_not_evidence_and_failure_overrides_lifecycle() -> None:
    assert QD.evidence_state({"status": "SHADOW"}) == "UNTESTED"
    assert QD.evidence_state({"status": "FORWARD", "forward_r": -1.0,
                              "verdict": "FAILED"}) == "FAILED"
    assert QD.evidence_state({"status": "LIVE", "verdict": "FAILED"}) == "FAILED"
    assert QD.evidence_state({"status": "LIVE", "forward_r": 0.2,
                              "n_forward": 5}) == "FORWARD_SUPPORTED"
    assert QD.evidence_state({"status": "LIVE", "forward_r": 0.2,
                              "n_forward": 5, "live_supported": True}) == "LIVE_SUPPORTED"


@pytest.mark.parametrize("result", [None, "", "nan", "inf", True, -1, 0])
def test_trade_count_does_not_invent_positive_forward_evidence(result) -> None:
    row = {"status": "LIVE", "n_forward": 5, "forward_r": result,
           "live_supported": True}
    assert QD.evidence_state(row) not in {"LIVE_SUPPORTED", "FORWARD_SUPPORTED"}


@pytest.mark.parametrize("count", [None, "bad", "inf", -1, 0, True, 0.5])
def test_positive_result_requires_a_valid_measured_sample(count) -> None:
    assert QD.evidence_state({"status": "SHADOW", "forward_r": 1,
                              "forward_trades": count}) != "FORWARD_SUPPORTED"


def test_changed_verdict_removes_old_niche_without_erasing_history() -> None:
    row = {"experiment_id": "a", "family": "trend", "verdict": "CERTIFIED"}
    archive = QD.update({}, [row])
    archive = QD.update(archive, [{**row, "verdict": "FAILED"}])
    assert archive["counts"]["occupied_niches"] == 1
    assert next(iter(archive["niches"].values()))["descriptor"]["evidence_state"] == "FAILED"
    assert archive["items"]["a"]["history"][0]["verdict"] == "CERTIFIED"
