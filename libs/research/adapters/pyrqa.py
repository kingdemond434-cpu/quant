"""PyRQA adapter -- recurrence quantification of the return path -> recurrence-state
representations.

Each (symbol, radius) is one charged trial. PyRQA is OpenCL-backed and sdist-only on PyPI, so
on most hosts this adapter reports UNMEASURED by name -- which is the measurement the ledger
needs, and the reason the row can be routed rather than assumed.
"""
from __future__ import annotations

from typing import Any

from libs.research import adapters as A
from libs.research.external_federation import ExternalResearchPacket

SYSTEM = "pyrqa"
RADII: tuple[float, ...] = (0.5, 1.0)
N, EMBED = 400, 3


def run(bundle: A.ResearchBundle) -> ExternalResearchPacket:
    mods = {name: A.library(f"pyrqa.{name}") for name in
            ("time_series", "settings", "analysis_type", "neighbourhood", "metric",
             "computation")}
    if any(m is None for m in mods.values()):
        return A.unmeasured(SYSTEM, bundle, "pyrqa is not importable in this environment "
                                            "(sdist-only on PyPI; OpenCL runtime required)")
    M: dict[str, Any] = dict(mods)
    deadline = A.Deadline(bundle.compute_budget_s)
    trials = 0
    reps: list[dict[str, Any]] = []
    for f in bundle.frames("H1"):
        r = f.log_returns()
        if r.shape[0] < N:
            continue
        x = r[-N:]
        x = (x - x.mean()) / max(float(x.std()), 1e-12)
        for radius in RADII:
            if deadline.expired():
                break
            trials += 1
            try:
                ts = M["time_series"].TimeSeries(x.tolist(), embedding_dimension=EMBED,
                                                    time_delay=1)
                settings = M["settings"].Settings(
                    ts, analysis_type=M["analysis_type"].Classic,
                    neighbourhood=M["neighbourhood"].FixedRadius(radius),
                    similarity_measure=M["metric"].EuclideanMetric, theiler_corrector=1)
                result = M["computation"].RQAComputation.create(settings,
                                                                   verbose=False).run()
                reps.append({"kind": "recurrence_state", "symbol": f.symbol,
                             "timeframe": f.timeframe, "n": N, "embedding": EMBED,
                             "radius": radius,
                             "recurrence_rate": float(result.recurrence_rate),
                             "determinism": float(result.determinism),
                             "laminarity": float(result.laminarity),
                             "average_diagonal_line": float(result.average_diagonal_line),
                             "entropy_diagonal_lines": float(result.entropy_diagonal_lines)})
            except Exception as exc:
                reps.append({"kind": "UNMEASURED", "symbol": f.symbol, "radius": radius,
                             "why": f"{type(exc).__name__}: {exc}"[:200]})
    return A.packet(SYSTEM, bundle, trials=trials, representations=reps)


if __name__ == "__main__":
    raise SystemExit(A.cli(run, SYSTEM))
