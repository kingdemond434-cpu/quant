"""parameter_stability_engine — reject sharp peaks, require wide robust plateaus.

An alpha may not pass validation if its performance depends on a narrow parameter region.
Evaluates a performance function over a neighborhood of the base parameters and rejects
configurations whose neighbors collapse (a spike) rather than holding (a plateau).
"""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from typing import Any

from pydantic import BaseModel, ConfigDict

PerfFn = Callable[[Mapping[str, Any]], float]


class ParameterStabilityResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    plateau_score: float  # 0-100, higher = wider plateau
    robust: bool
    base_performance: float
    neighbor_mean: float
    neighbor_min: float
    sharp_peak: bool

    def __bool__(self) -> bool:
        return self.robust


def parameter_stability(
    perf_fn: PerfFn,
    base: Mapping[str, Any],
    sweep: Mapping[str, Sequence[Any]],
    *,
    retention: float = 0.5,
    threshold: float = 60.0,
) -> ParameterStabilityResult:
    """Score how well performance holds across the parameter neighborhood."""
    base_perf = perf_fn(base)
    neighbors: list[float] = []
    for key, values in sweep.items():
        for value in values:
            params = dict(base)
            params[key] = value
            neighbors.append(perf_fn(params))

    if not neighbors:
        plateau = 1.0
    elif base_perf <= 0:
        plateau = 0.0
    else:
        held = sum(1 for n in neighbors if n >= retention * base_perf)
        plateau = held / len(neighbors)

    neighbor_mean = sum(neighbors) / len(neighbors) if neighbors else base_perf
    neighbor_min = min(neighbors) if neighbors else base_perf
    sharp_peak = bool(base_perf > 0 and neighbors and max(neighbors) < 0.5 * base_perf)
    score = plateau * 100.0
    return ParameterStabilityResult(
        plateau_score=score,
        robust=score >= threshold and not sharp_peak,
        base_performance=base_perf,
        neighbor_mean=neighbor_mean,
        neighbor_min=neighbor_min,
        sharp_peak=sharp_peak,
    )
