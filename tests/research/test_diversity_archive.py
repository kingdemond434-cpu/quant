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
