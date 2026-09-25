"""The IL pack's own miners. Today: the structured data plane, which had no clock at all.

MEASURED 2026-09-23: `data_plane.py` here declares `run()` and a REPORT path and this package
held NO `miners.py`, which is the only file `global_research_os` reads to find a country's own
miners -- so the writer ran nowhere and IL_DATA_PLANE.json had never existed. The adapter lives in
`countries/_data_plane_miner.py` so the fix is the same shape for every pack of this class.
"""
from __future__ import annotations

from collections.abc import Callable
from typing import Any

from countries._data_plane_miner import data_plane_miner

from . import data_plane as _dp

CODE = "il"
MINERS: dict[str, Callable[..., dict[str, Any]]] = {
    "data_plane": data_plane_miner(CODE, _dp.run, _dp.LANES, _dp.REPORT),
}
#: The loop step this miner runs under, in `region_department.MINER_STEP`'s vocabulary.
MINER_KIND: dict[str, str] = {"data_plane": "data"}
NAMES: tuple[str, ...] = tuple(MINERS)

mine_data_plane = MINERS["data_plane"]

__all__ = ["CODE", "MINERS", "MINER_KIND", "NAMES", "mine_data_plane"]
