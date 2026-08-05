"""Ordered schema migrations for the SQLite system of record.

Add a new ``mNNNN_*.py`` module per change and append its ``MIGRATION`` to :data:`MIGRATIONS`.
Migrations are additive and forward-only.
"""

from __future__ import annotations

from libs.store.migrations import Migration
from migrations.m0001_core import MIGRATION as M0001_CORE
from migrations.m0002_alpha import MIGRATION as M0002_ALPHA
from migrations.m0003_research import MIGRATION as M0003_RESEARCH
from migrations.m0004_monitoring import MIGRATION as M0004_MONITORING
from migrations.m0005_autodiscovery import MIGRATION as M0005_AUTODISCOVERY
from migrations.m0006_orchestration import MIGRATION as M0006_ORCHESTRATION
from migrations.m0007_candidate_returns import MIGRATION as M0007_CANDIDATE_RETURNS

MIGRATIONS: tuple[Migration, ...] = (
    M0001_CORE,
    M0002_ALPHA,
    M0003_RESEARCH,
    M0004_MONITORING,
    M0005_AUTODISCOVERY,
    M0006_ORCHESTRATION,
    M0007_CANDIDATE_RETURNS,
)

__all__ = ["MIGRATIONS"]
