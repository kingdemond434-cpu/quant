from __future__ import annotations

import json
from pathlib import Path

import scripts.run_alpha_frontier as runner


def test_empty_frontier_is_measured_as_missing_not_clean(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(runner, "ROOT", tmp_path)
    report = runner.build()
    assert report["factory"]["mechanism_half_life"]["status"] == "UNMEASURED"
    assert report["factory"]["continuous_null_factory"]["promotion_blocked"] is True
    assert report["practitioner_frontier"]["new_mechanisms"] == []


def test_runner_consumes_hunter_items_and_writes_daily_artifact(
    tmp_path: Path, monkeypatch
) -> None:
    p = tmp_path / "data" / "intelligence"
    p.mkdir(parents=True)
    (p / "public_strategy_items.json").write_text(
        json.dumps(
            {
                "items": [
                    {
                        "mission": "VIDEO_TRANSCRIPT",
                        "mechanism": "liquidation queue depletion",
                        "evidence_class": "VERIFIED",
                    }
                ]
            }
        ),
        "utf-8",
    )
    out = p / "daily_alpha_frontier.json"
    monkeypatch.setattr(runner, "ROOT", tmp_path)
    monkeypatch.setattr(runner, "OUT", out)
    assert runner.main() == 0
    saved = json.loads(out.read_text("utf-8"))
    assert saved["practitioner_frontier"]["new_mechanisms"] == ["liquidation queue depletion"]


def test_frontier_invokes_transfer_state_and_return_decomposition(
    tmp_path: Path, monkeypatch
) -> None:
    (tmp_path / "data").mkdir()
    (tmp_path / "web").mkdir()
    (tmp_path / "data" / "mechanism_transfer.json").write_text(
        json.dumps(
            {
                "transfers": [
                    {
                        "mechanism_id": "m1",
                        "transfer_class": "ASSET_FAMILY",
                        "target": {"asset": "BTC"},
                        "constraints": {"asset": ["BTC", "ETH"]},
                    }
                ]
            }
        ),
        "utf-8",
    )
    (tmp_path / "web" / "regime.json").write_text(
        json.dumps(
            {
                "as_of": "2026-08-08",
                "structural": {"inflation": "high"},
                "tactical": {"trend": "up"},
                "fast": {"vol": "low"},
                "microstructure": {"spread": "tight"},
            }
        ),
        "utf-8",
    )
    (tmp_path / "data" / "return_source_claims.json").write_text(
        json.dumps(
            {
                "claims": [
                    {
                        "total_return": 1.0,
                        "beta_return": 0.2,
                        "carry_return": 0.1,
                        "leverage_multiplier": 3.0,
                        "concentration_return": 0.2,
                        "convexity_return": 0.1,
                        "external_flows": 0.0,
                    }
                ]
            }
        ),
        "utf-8",
    )
    monkeypatch.setattr(runner, "ROOT", tmp_path)
    report = runner.build()
    assert report["factory"]["mechanism_transfer"]["rows"][0]["eligible"] is True
    assert report["factory"]["multi_timescale_state"]["measured_layers"] == 4
    row = report["factory"]["return_source_decomposition"]["rows"][0]
    assert row["leverage_multiplier"] == 3.0
    import pytest

    assert row["components"]["unexplained_alpha_or_luck"] == pytest.approx(0.4)
