"""The canonical experiment object: the three constructors, the compile contract, the defect
that a prose-only row becomes, and the campaign row it enqueues as."""
from __future__ import annotations

from pathlib import Path

import pytest

from libs.moat import registry as R
from libs.research import experiment_spec as S


@pytest.fixture
def reg(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(R, "BACKUP", tmp_path / "no_backup")
    R.set_path(tmp_path / "alpha_registry.sqlite")
    yield tmp_path
    R.set_path(None)


def _discovery_row(**over: object) -> dict[str, object]:
    row = {
        "discovery_id": "disc_1", "source_type": "forum_thread", "source_id": "src_7ho",
        "generator": "deep_forest_miner", "origin": "EXTERNAL",
        "mechanism": "carry_unwind on JPY crosses -> fade",
        "assets_json": '["AUDJPY"]', "horizons_json": '["1d"]', "sessions_json": '["asia"]',
        "regimes_json": '["high_vol"]',
        "required_data_json": '["desks/mt5/data/universe/AUDJPY_H1.parquet"]',
        "pit_requirements_json": '["bars"]',
        "falsifier": "the same rule on later bars no longer clears the ten gates",
        "exact_rule": '{"family": "carry_unwind", "lookback": 20}',
        "payload_json": '{"family": "carry_unwind", "chart": "H1"}',
        "information": "positioning", "state": "UNPROCESSED", "novelty": 0.8,
        "confidence": 0.4, "economic_rationale": "leveraged carry books unwind into asia",
        "created_at": "2026-09-20T00:00:00+00:00",
    }
    row.update(over)
    return row


def test_from_discovery_compiles_every_axis_the_row_declares() -> None:
    spec = S.from_discovery(_discovery_row())
    assert isinstance(spec, S.ExperimentSpec)
    assert spec.kind == "world_lead"           # a forum thread is a world-miner lead
    assert spec.symbols == ("AUDJPY",)
    assert spec.family == "carry_unwind"
    assert spec.horizon == "1d" and spec.session == "asia" and spec.regime == "high_vol"
    assert spec.representation == "positioning"
    assert spec.source == "src_7ho" and spec.generator == "deep_forest_miner"
    assert spec.data_snapshot.datasets == ("desks/mt5/data/universe/AUDJPY_H1.parquet",)
    assert spec.data_snapshot.snapshot_hash                      # identity is DERIVED
    assert spec.target == S.DEFAULT_TARGET and spec.target_basis == "derived"
    assert spec.spec_hash() == S.from_discovery(_discovery_row()).spec_hash()


def test_a_prose_only_row_is_a_recorded_defect_with_its_reason() -> None:
    """NO PROSE-ONLY RESEARCH: the row does not vanish, it becomes a named blocker."""
    row = _discovery_row(assets_json=None, exact_rule=None, payload_json="{}",
                         mechanism="the Bank of Japan intervenes when the yen is weak")
    out = S.from_discovery(row)
    assert isinstance(out, S.CompileDefect)
    assert out.reason == "PROSE_ONLY"
    assert out.row_id == "disc_1" and out.generator == "deep_forest_miner"
    assert "instrument" in out.detail
    assert out.reason in S.DEFECT_REASONS


@pytest.mark.parametrize(("over", "reason"), [
    ({"assets_json": None}, "NO_INSTRUMENT"),
    ({"exact_rule": None, "payload_json": "{}", "mechanism": "flows are big"}, "NO_FAMILY"),
    ({"falsifier": None}, "NO_FALSIFIER"),
    ({"required_data_json": None}, "NO_DATA"),
    ({"assets_json": '["BTCUSDT"]', "source_id": "binance_funding"}, "OFF_UNIVERSE"),
])
def test_each_missing_half_names_its_own_blocker(over: dict[str, object], reason: str) -> None:
    out = S.from_discovery(_discovery_row(**over))
    assert isinstance(out, S.CompileDefect)
    assert out.reason == reason


def test_from_candidate_round_trips_the_lineage_a_spec_wrote() -> None:
    spec = S.from_discovery(_discovery_row())
    assert isinstance(spec, S.ExperimentSpec)
    camp = spec.to_campaign()
    # what the registry would hold, fed straight back in
    row = {"id": camp["candidate_id"], "content_hash": "h", "grid_cell": "c",
           "family": camp["family"], "symbol": camp["symbol"], "params_json": "{}",
           "origin": camp["origin"], "mechanism": camp["mechanism"],
           "falsifier": camp["falsifier"], "chart": camp["chart"], "horizon": camp["horizon"],
           "regime": camp["regime"], "session": camp["session"],
           "required_data_json": '["desks/mt5/data/universe/AUDJPY_H1.parquet"]',
           "lineage_json": __import__("json").dumps(camp["lineage"]),
           "status": "queued"}
    back = S.from_candidate(row)
    assert isinstance(back, S.ExperimentSpec)
    assert back.experiment_id == spec.experiment_id
    assert back.family == spec.family and back.symbols == spec.symbols
    assert back.status == "QUEUED"


def test_from_claim_reads_the_key_names_the_organs_actually_write() -> None:
    spec = S.from_claim({"instruments": ["EURUSD"], "family": "session_range_breakout",
                         "timeframe": "M15", "falsifier": "no edge after costs on later bars",
                         "data": ["desks/mt5/data/universe/EURUSD_M15.parquet"],
                         "mechanism": "london open range", "producer": "forest_europe"},
                        kind="country_mechanism", source="forest:eu")
    assert isinstance(spec, S.ExperimentSpec)
    assert spec.kind == "country_mechanism" and spec.chart == "M15"
    assert spec.generator == "forest_europe" and spec.symbols == ("EURUSD",)


def test_compile_row_routes_by_the_keys_the_row_carries() -> None:
    assert isinstance(S.compile_row(_discovery_row()), S.ExperimentSpec)
    assert isinstance(S.compile_row("not a mapping"), S.CompileDefect)
    assert S.compile_row(42).reason == "UNREADABLE"          # type: ignore[union-attr]


def test_to_campaign_carries_full_provenance_and_enqueue_links_the_dag(reg: Path) -> None:
    spec = S.from_discovery(_discovery_row())
    assert isinstance(spec, S.ExperimentSpec)
    camp = spec.to_campaign()
    for key in ("family", "symbol", "params", "origin", "mechanism", "discovery_id",
                "source_id", "generator", "falsifier", "trial_family", "lineage"):
        assert key in camp
    assert camp["lineage"]["spec_hash"] == spec.spec_hash()
    cid, created = S.enqueue(spec)
    assert created is True
    rows = R.candidates(limit=10)
    assert rows and rows[0]["id"] == cid
    edges = R.provenance_of("cell", cid)
    assert any(e["from_kind"] == "experiment" for e in edges)
    # the same experiment enqueued twice is ONE candidate
    cid2, created2 = S.enqueue(spec)
    assert cid2 == cid and created2 is False


def test_data_snapshot_identity_is_content_addressed() -> None:
    a = S.DataSnapshot(vintage="2026-09-01", datasets=("a", "b"), pit_status="bars").resolved()
    b = S.DataSnapshot(vintage="2026-09-01", datasets=("b", "a"), pit_status="bars").resolved()
    c = S.DataSnapshot(vintage="2026-09-02", datasets=("a", "b"), pit_status="bars").resolved()
    assert a.snapshot_hash == b.snapshot_hash != c.snapshot_hash
