"""bl888m adapter (REBUILT) -- prediction-market/smart-participant provenance rebuilt as an AXIS
PROVENANCE MEASUREMENT. The upstream's real claim is that an information source is only usable
when its RESOLUTION TRUTH is stamped; this adapter measures exactly that on the bundle's own
axes: available_time, basis, point count and staleness against the bar watermark. An axis
without an available_time is named, never silently used."""
from __future__ import annotations

from typing import Any

from libs.research import adapters as A
from libs.research.external_federation import ExternalResearchPacket

SYSTEM = "bl888m"
CAPABILITY_FAMILY = "information_acquisition"
LICENCE_EXPECTED = "N/A (method only)"
RUNS_WITHOUT_LIBRARY = True


def run(bundle: A.ResearchBundle) -> ExternalResearchPacket:
    axes = dict(bundle.axes)
    if not axes:
        return A.unmeasured(SYSTEM, bundle, "this bundle carries no axis series to measure")
    rows: list[dict[str, Any]] = []
    for key, ax in sorted(axes.items()):
        rows.append({"axis": ax.axis, "series": ax.series, "key": key,
                     "n_points": len(ax.points),
                     "available_time": ax.available_time or None,
                     "stamped": bool(ax.available_time), "basis": ax.basis or None,
                     "basis_declared": bool(ax.basis),
                     "last_point": ax.points[-1][0] if ax.points else None})
    stamped = [r for r in rows if r["stamped"] and r["basis_declared"]]
    return A.packet(
        SYSTEM, bundle, trials=len(rows),
        representations=[{
            "kind": "axis_provenance_coverage", "system": SYSTEM, "n_axes": len(rows),
            "n_usable": len(stamped), "coverage": round(len(stamped) / max(len(rows), 1), 4),
            "watermark": bundle.watermark(), "axes": rows,
            "representation": ("resolution truth per axis: an axis is usable only when its "
                               "available_time and basis are both stamped; the rest are named")}],
        research_methods=[{
            "kind": "provenance_rule", "system": SYSTEM,
            "rule": "no axis without an available_time enters a hypothesis",
            "n_refused": len(rows) - len(stamped)}],
        note=f"axis provenance {len(stamped)}/{len(rows)} stamped")


if __name__ == "__main__":
    raise SystemExit(A.cli(run, SYSTEM))
