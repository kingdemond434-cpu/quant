"""The JP pack's own miners. Today: the Japan official plane (MOF flows and intervention, BOJ).

`global_research_os` reads a pack's `miners.py` to find its own miners. Japan is a conversion-door
pack (`NON_LAB_PACKS`: no CountryPack research specification), so the loop runs these miners as a
DEPARTMENT row of its own rather than through the country lab; the plane reads the alt-data
factory's stores and writes JP_OFFICIAL_PLANE.json.
"""
from __future__ import annotations

import importlib
from collections.abc import Callable
from typing import Any


def _load(name: str) -> Any:
    """A sibling module of the country packages, under whichever root this process resolves."""
    last: Exception | None = None
    for root in ("countries", "research.countries", "desks.mt5.research.countries"):
        try:
            return importlib.import_module(f"{root}.{name}")
        except ImportError as exc:
            last = exc
    raise ImportError(f"{name}: {last}")


_dpm: Any = _load("_data_plane_miner")
_op: Any = _load("jp.official_plane")

CODE = "jp"
MINERS: dict[str, Callable[..., dict[str, Any]]] = {
    "official_plane": _dpm.data_plane_miner(CODE, _op.run, _op.LANES, _op.REPORT),
}
#: The loop step this miner runs under, in `region_department.MINER_STEP`'s vocabulary.
MINER_KIND: dict[str, str] = {"official_plane": "data"}
NAMES: tuple[str, ...] = tuple(MINERS)

mine_official_plane = MINERS["official_plane"]

__all__ = ["CODE", "MINERS", "MINER_KIND", "NAMES", "mine_official_plane"]
