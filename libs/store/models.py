"""Row models for the SQLite system of record.

Read models are frozen: a row handed back from the store is an immutable snapshot, never
a live handle. Writes go only through the store's typed insert/update functions.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict


class _Frozen(BaseModel):
    model_config = ConfigDict(frozen=True)


class AuditEntry(_Frozen):
    """One immutable, hash-chained decision record."""

    seq: int
    id: str
    created_at: str
    decision_type: str
    actor: str
    inputs: dict[str, Any]
    rationale: str | None
    outcome: str | None
    prev_hash: str
    row_hash: str


class TrialRecord(_Frozen):
    """One immutable, hash-chained research-trial record."""

    seq: int
    id: str
    created_at: str
    hypothesis_id: str
    family: str
    method: str
    params: dict[str, Any]
    data_snapshot: str | None
    in_sample_metric: float | None
    git_commit: str | None
    prev_hash: str
    row_hash: str


class ResearchRun(_Frozen):
    id: str
    created_at: str
    updated_at: str
    hypothesis_id: str | None
    name: str | None
    git_commit: str
    snapshot_id: str | None
    config_hash: str
    seed: int
    status: str
    metrics: dict[str, Any] | None


class Alpha(_Frozen):
    id: str
    created_at: str
    updated_at: str
    name: str
    instruments: list[str]
    status: str
    card: dict[str, Any] | None
    owner: str | None
    deploy_date: str | None
    retire_date: str | None


class RiskRecord(_Frozen):
    id: str
    created_at: str
    kind: str
    scope: str | None
    metric: str | None
    threshold: float | None
    observed: float | None
    action: str | None
    target_ref: str | None
    detail: dict[str, Any] | None
    active: bool


class Order(_Frozen):
    id: str
    created_at: str
    updated_at: str
    instrument: str
    side: str
    qty: float
    order_type: str
    intended_price: float | None
    alpha_id: str | None
    risk_approval_id: str
    status: str
    idempotency_key: str | None
    mt5_ticket: int | None


class Fill(_Frozen):
    id: str
    order_id: str
    created_at: str
    fill_price: float
    fill_qty: float
    commission: float
    mt5_deal_id: int | None


class Position(_Frozen):
    instrument: str
    qty: float
    avg_price: float
    realized_pnl: float
    unrealized_pnl: float
    updated_at: str


class SnapshotRecord(_Frozen):
    id: str
    created_at: str
    kind: str
    label: str | None
    path: str | None
    sha256: str | None
    row_counts: dict[str, Any] | None
    meta: dict[str, Any] | None


class ConfigVersion(_Frozen):
    id: str
    created_at: str
    config_hash: str
    environment: str | None
    content: dict[str, Any]
    note: str | None


class ChainVerification(_Frozen):
    """The result of verifying a hash-chained table."""

    ok: bool
    length: int
    broken_seq: int | None
    message: str

    def __bool__(self) -> bool:
        return self.ok
