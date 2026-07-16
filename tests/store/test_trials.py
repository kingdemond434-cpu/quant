"""Tests for the append-only, hash-chained trials ledger."""

from __future__ import annotations

import sqlite3

import pytest

from libs.store.connection import Database
from libs.store.trials import TrialsLedger, verify_trials_chain


def test_append_and_counts(db: Database) -> None:
    ledger = TrialsLedger(db)
    ledger.append("hyp_1", "trend", "grid", {"lookback": 20}, in_sample_metric=1.2)
    ledger.append("hyp_1", "trend", "grid", {"lookback": 50}, in_sample_metric=0.9)
    ledger.append("hyp_2", "mean_rev", "grid", {"z": 2.0})
    assert ledger.count() == 3
    assert ledger.count_for_hypothesis("hyp_1") == 2


def test_records_carry_params_and_metric(db: Database) -> None:
    ledger = TrialsLedger(db)
    record = ledger.append(
        "hyp_1", "trend", "cpcv", {"lookback": 20, "vol": True}, in_sample_metric=1.5,
        git_commit="abc123",
    )
    assert record.params == {"lookback": 20, "vol": True}
    assert record.in_sample_metric == 1.5
    assert record.git_commit == "abc123"


def test_chain_verifies(db: Database) -> None:
    ledger = TrialsLedger(db)
    for i in range(5):
        ledger.append("hyp", "trend", "grid", {"i": i})
    result = verify_trials_chain(db)
    assert result.ok
    assert result.length == 5


def test_ledger_is_append_only(db: Database) -> None:
    TrialsLedger(db).append("hyp", "trend", "grid", {"i": 1})
    with pytest.raises(sqlite3.Error):
        db.execute("UPDATE trials_ledger SET family = 'x' WHERE seq = 1")
    with pytest.raises(sqlite3.Error):
        db.execute("DELETE FROM trials_ledger WHERE seq = 1")


def test_tamper_detection(db: Database) -> None:
    ledger = TrialsLedger(db)
    ledger.append("hyp", "trend", "grid", {"i": 1})
    ledger.append("hyp", "trend", "grid", {"i": 2})
    db.execute("DROP TRIGGER trials_ledger_no_update")
    db.execute("UPDATE trials_ledger SET in_sample_metric = 99.0 WHERE seq = 2")
    result = verify_trials_chain(db)
    assert not result.ok
    assert result.broken_seq == 2
