"""Research dashboard exports — aggregate factory state for monitoring.

Pure, deterministic aggregation over research memory (and optional allocation). No I/O.
"""

from __future__ import annotations

from typing import Any

from libs.alpha_factory.models import AllocationResult, ResearchResult
from libs.alpha_factory.research_memory import ResearchMemory


def build_research_dashboard(
    memory: ResearchMemory, *, allocation: AllocationResult | None = None
) -> dict[str, Any]:
    """Summarize research productivity and knowledge for dashboards."""
    records = memory.all()
    categories = sorted({r.category for r in records})
    decided = [r for r in records if r.result is not ResearchResult.PENDING]
    return {
        "n_ideas": len(records),
        "n_decided": len(decided),
        "n_success": sum(1 for r in records if r.result is ResearchResult.SUCCESS),
        "n_failure": sum(1 for r in records if r.result is ResearchResult.FAILURE),
        "overall_success_rate": memory.success_rate(),
        "success_rate_by_category": {c: memory.success_rate(c) for c in categories},
        "failure_cause_histogram": memory.failure_cause_histogram(),
        "allocation": dict(allocation.allocations) if allocation is not None else {},
    }
