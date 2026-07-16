"""Stage 15 research audit logging (immutable, hash-chained)."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest
from migrations import MIGRATIONS
from tests.stage15.conftest import passing_candidate

from libs.stage15.audit import ResearchAudit
from libs.stage15.orchestrator import ResearchOrchestrator
from libs.store.audit import verify_audit_chain
from libs.store.connection import Database
from libs.store.migrations import run_migrations


@pytest.fixture
def db(tmp_path: Path) -> Iterator[Database]:
    database = Database(tmp_path / "sor.sqlite")
    run_migrations(database, MIGRATIONS)
    yield database
    database.close()


def test_orchestrator_writes_immutable_audit(db: Database) -> None:
    engine = ResearchOrchestrator(min_allocation_quality=60.0, audit=ResearchAudit(db))
    result = engine.run([passing_candidate("a"), passing_candidate("b", dsr_passed=False)])
    assert result.allocated == ["a"]
    assert result.rejected == ["b"]
    chain = verify_audit_chain(db)
    assert chain.ok
    # one entry per pipeline record + one summary entry
    assert chain.length == len(result.records) + 1


def test_audit_records_research_halt(db: Database) -> None:
    engine = ResearchOrchestrator(audit=ResearchAudit(db))
    result = engine.run([passing_candidate("a")], false_discovery_rate=0.9)
    assert result.kill.halt
    assert verify_audit_chain(db).ok
