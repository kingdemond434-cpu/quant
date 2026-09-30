"""A producer's null passes are trials: `*_TRIALS.jsonl` rows are charged to their family, dry runs
are not, and a censused producer's discovery files are not charged a second time."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from libs.research import experiment_ledger as el


def test_trials_census_is_charged_once(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    desk = tmp_path
    (desk / "data" / "intelligence" / "regime_split_miner").mkdir(parents=True)
    (desk / "data" / "intelligence" / "kimi").mkdir(parents=True)
    rows = [{"family": "regime_split", "cells_screened": 103, "source": "regime_split_miner"},
            {"family": "regime_split", "cells_screened": 50, "source": "regime_split_miner",
             "dry_run": True},
            {"family": "regime_split", "cells_screened": 7, "source": "regime_split_miner"}]
    (desk / "data" / "REGIME_SPLIT_TRIALS.jsonl").write_text(
        "\n".join(json.dumps(r) for r in rows) + "\n")
    disc = {"tests_run": 999, "discoveries": [{"family": "regime_split"}]}
    (desk / "data" / "intelligence" / "regime_split_miner" / "discoveries_1.json").write_text(
        json.dumps(disc))
    (desk / "data" / "intelligence" / "kimi" / "discoveries_1.json").write_text(
        json.dumps({"tests_run": 4, "discoveries": [{"family": "carry"}]}))
    monkeypatch.setattr(el, "DESK", desk)
    total, fam = el._proposer_counts()
    assert fam == {"regime_split": 110, "carry": 4}
    assert total == 114


def test_no_intelligence_dir_still_reads_the_census(tmp_path: Path,
                                                     monkeypatch: pytest.MonkeyPatch) -> None:
    (tmp_path / "data").mkdir()
    (tmp_path / "data" / "X_TRIALS.jsonl").write_text(
        json.dumps({"family": "f", "cells_screened": 3}) + "\n")
    monkeypatch.setattr(el, "DESK", tmp_path)
    assert el._proposer_counts() == (3, {"f": 3})
