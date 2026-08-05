"""Autonomous research daemon: the worker loop, the supervisor maintenance, and the research loop.

  Research Memory -> Campaign Generator -> Discovery -> Validation -> Audit -> Research Ledger
  -> Next Campaign ...  (forever)

A :class:`ResearchWorker` leases campaigns and runs them through the existing ``AutoDiscoveryLab``
(no validation logic is changed). A :class:`Supervisor` keeps the queue full and reclaims work from
dead workers. Process-level spawning/restart lives in ``scripts/run_supervisor.py``; this module is
the deterministic, unit-testable core. Executors are injected so the loop is testable without data.
"""

from __future__ import annotations

import time
from collections.abc import Callable, Iterable, Sequence
from pathlib import Path
from typing import Any

import numpy as np

from libs.autodiscovery.models import Family, MarketSeries
from libs.autodiscovery.novelty import NoveltyGate
from libs.autodiscovery.orchestrator import AutoDiscoveryLab
from libs.data.instruments import AssetClass, InstrumentSpec, register_instrument
from libs.data.lake import Layer, ParquetLake
from libs.data.timeframe import Timeframe
from libs.ops.campaign_queue import CampaignQueue
from libs.ops.workers import WorkerRegistry
from libs.store.connection import Database

# Executor: (worker db, campaign spec) -> result dict. Injected for testability.
CampaignExecutor = Callable[[Database, dict[str, Any]], dict[str, Any]]
_COST_PER_SIDE = {AssetClass.FX: 8e-5, AssetClass.METAL: 1.5e-4, AssetClass.ENERGY: 2e-4}


class ResearchWorker:
    """Leases and runs campaigns in a crash-safe loop. One worker == one process/connection."""

    def __init__(
        self,
        db: Database,
        worker_id: str,
        executor: CampaignExecutor,
        *,
        lease_seconds: int = 600,
        poll_seconds: float = 3.0,
        pid: int = 0,
    ) -> None:
        self.db = db
        self.worker_id = worker_id
        self.executor = executor
        self.lease_seconds = lease_seconds
        self.poll_seconds = poll_seconds
        self.queue = CampaignQueue(db)
        self.registry = WorkerRegistry(db)
        self.registry.register(worker_id, pid=pid)

    def run_once(self) -> str:
        """Lease + run a single campaign. Returns 'idle' | 'done' | 'failed'."""
        self.registry.beat(self.worker_id, status="idle")
        lease = self.queue.lease(self.worker_id, lease_seconds=self.lease_seconds)
        if lease is None:
            return "idle"
        cid = lease["id"]
        self.registry.beat(self.worker_id, status="running", current_campaign=cid)
        try:
            result = self.executor(self.db, lease["spec"])
        except Exception as exc:  # never let one bad campaign kill the worker
            status = self.queue.fail(cid, self.worker_id, f"{type(exc).__name__}: {exc}")
            self.registry.beat(self.worker_id, status="idle")
            return "failed" if status == "failed" else "retry"
        self.queue.complete(cid, self.worker_id, result)
        self.registry.beat(self.worker_id, status="idle", completed=True)
        return "done"

    def run_forever(self, *, stop: Callable[[], bool] | None = None) -> None:
        stop = stop or (lambda: False)
        while not stop():
            outcome = self.run_once()
            if outcome == "idle":
                time.sleep(self.poll_seconds)


class Supervisor:
    """Keeps the system live: reclaims dead-worker leases, prunes workers, refills the queue."""

    def __init__(
        self,
        db: Database,
        *,
        generator: Callable[[], Iterable[dict[str, Any]]],
        min_queue_depth: int = 8,
        worker_stale_seconds: int = 120,
        cleanup_days: int = 7,
    ) -> None:
        self.db = db
        self.queue = CampaignQueue(db)
        self.registry = WorkerRegistry(db)
        self.generator = generator
        self.min_queue_depth = min_queue_depth
        self.worker_stale_seconds = worker_stale_seconds
        self.cleanup_days = cleanup_days

    def ensure_queue(self) -> int:
        """Top up the queue from the campaign generator when it runs low. Returns # enqueued."""
        if self.queue.stats()["depth"] >= self.min_queue_depth:
            return 0
        enq = 0
        for spec in self.generator():
            if self.queue.enqueue(spec) is not None:
                enq += 1
        return enq

    def maintain(self) -> dict[str, int]:
        """One maintenance pass: reclaim stale leases, prune dead workers, cleanup, refill."""
        reclaimed = self.queue.reclaim_stale()
        pruned = self.registry.prune(stale_seconds=self.worker_stale_seconds * 10)
        cleaned = self.queue.cleanup(keep_days=self.cleanup_days)
        enqueued = self.ensure_queue()
        return {"reclaimed": reclaimed, "pruned": pruned, "cleaned": cleaned, "enqueued": enqueued}


# --- production executor + generator over the Parquet lake (no live MT5 dependency) -------------
def _lake_symbols(lake_dir: str) -> dict[str, AssetClass]:
    base = Path(lake_dir) / "bronze"
    out: dict[str, AssetClass] = {}
    if not base.exists():
        return out
    for ac_dir in base.iterdir():
        try:
            ac = AssetClass(ac_dir.name)
        except ValueError:
            continue
        for sym in ac_dir.iterdir():
            if (sym / Timeframe.D1.value).exists():
                out[sym.name] = ac
    return out


def make_lake_executor(lake_dir: str = "data/lake") -> CampaignExecutor:
    """Executor that runs a campaign's symbols/families through the lab on lake history."""
    available = _lake_symbols(lake_dir)
    for sym, ac in available.items():
        register_instrument(InstrumentSpec(symbol=sym, asset_class=ac, description=sym))
    lake = ParquetLake(lake_dir)

    def executor(db: Database, spec: dict[str, Any]) -> dict[str, Any]:
        symbols: list[str] = [s for s in spec.get("symbols", []) if s in available]
        families = [Family(f) for f in spec.get("families", [])] or None
        frames = {s: lake.read_bars(Layer.BRONZE, s, Timeframe.D1).set_index("timestamp")
                  for s in symbols}

        def provider(symbol: str) -> MarketSeries | None:
            df = frames.get(symbol)
            if df is None or len(df) < 250:
                return None
            return MarketSeries(
                close=df["close"].to_numpy("float64"), high=df["high"].to_numpy("float64"),
                low=df["low"].to_numpy("float64"), volume=df["volume"].to_numpy("float64"),
                hour=np.array([t.hour for t in df.index], dtype="float64"),
            )

        def cost_provider(symbol: str) -> float:
            return _COST_PER_SIDE.get(available.get(symbol, AssetClass.FX), 1e-4)

        lab = AutoDiscoveryLab(db, provider, cost_provider=cost_provider, families=families,
                               novelty=NoveltyGate.from_corpus())
        res = lab.cycle(symbols)
        return {"campaign_id": res.campaign_id, "tested": res.tested,
                "survivors": res.survivors, "rejected": res.rejected}

    return executor


def lake_campaign_specs(
    lake_dir: str = "data/lake",
    *,
    families: Sequence[str] | None = None,
    batch: int = 1,
) -> list[dict[str, Any]]:
    """Generate one campaign per symbol-batch over the lake (the research loop's fuel)."""
    fams = list(families) if families is not None else [f.value for f in Family]
    syms = sorted(_lake_symbols(lake_dir))
    specs: list[dict[str, Any]] = []
    for i in range(0, len(syms), batch):
        chunk = syms[i: i + batch]
        if chunk:
            specs.append({"symbols": chunk, "families": fams, "source": "lake", "timeframe": "D1"})
    return specs
