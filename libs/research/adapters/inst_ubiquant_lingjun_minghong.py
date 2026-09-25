"""Ubiquant/Lingjun/Minghong-style adapter (REBUILT) -- the published capability is the DATA-LAB
split: breadth of inputs as an institution-level asset. The adapter measures this bundle's own
input breadth -- instruments, timeframes, bar counts, axis series with their provenance stamps,
and the cost rows that exist for each symbol. Breadth that is not measured is breadth the desk
cannot claim."""
from __future__ import annotations

from libs.research import adapters as A
from libs.research.external_federation import ExternalResearchPacket

SYSTEM = "inst_ubiquant_lingjun_minghong"
CAPABILITY_FAMILY = "institutional_capability"
LICENCE_EXPECTED = "N/A (public architecture)"
RUNS_WITHOUT_LIBRARY = True


def run(bundle: A.ResearchBundle) -> ExternalResearchPacket:
    import numpy as np
    bars = list(bundle.bars.values())
    if not bars:
        return A.unmeasured(SYSTEM, bundle, "this bundle carries no bar frames")
    tfs = sorted({f.timeframe for f in bars})
    per_symbol = [{"symbol": f.symbol, "timeframe": f.timeframe, "n_bars": len(f),
                   "first": f.time[0] if f.time else None,
                   "last": f.time[-1] if f.time else None,
                   "has_cost_row": f.symbol in bundle.costs}
                  for f in sorted(bars, key=lambda f: (f.symbol, f.timeframe))]
    axes = [{"axis": a.axis, "series": a.series, "n_points": len(a.points),
             "stamped": bool(a.available_time), "basis": a.basis or None}
            for a in bundle.axes.values()]
    return A.packet(
        SYSTEM, bundle, trials=len(bars) + len(axes),
        representations=[{
            "kind": "input_breadth", "system": SYSTEM,
            "n_frames": len(bars), "n_symbols": len({f.symbol for f in bars}),
            "timeframes": tfs, "universe_declared": len(bundle.universe),
            "median_bars": float(np.median([len(f) for f in bars])),
            "n_axes": len(axes), "n_axes_stamped": sum(1 for a in axes if a["stamped"]),
            "n_cost_rows": len(bundle.costs), "frames": per_symbol, "axes": axes,
            "representation": ("the data lab's own inventory: what this research hour could "
                               "see at all, by instrument, timeframe, axis and cost row")}],
        note=f"{len(bars)} frames, {len(axes)} axes, {len(bundle.costs)} cost rows")


if __name__ == "__main__":
    raise SystemExit(A.cli(run, SYSTEM))
