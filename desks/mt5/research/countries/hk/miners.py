"""The HK pack's own miners. Today: the HKMA official plane (currency board, HIBOR, EFBN).

`global_research_os` reads a pack's `miners.py` to find its own miners; Hong Kong had none, so
its official series ran on the alt-data factory's clock and nothing on the department's side
read them back. The plane reads the factory's stores and writes HK_OFFICIAL_PLANE.json.
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
_op: Any = _load("hk.official_plane")

CODE = "hk"
MINERS: dict[str, Callable[..., dict[str, Any]]] = {
    "official_plane": _dpm.data_plane_miner(CODE, _op.run, _op.LANES, _op.REPORT),
}
#: The loop step this miner runs under, in `region_department.MINER_STEP`'s vocabulary.
MINER_KIND: dict[str, str] = {"official_plane": "data"}
NAMES: tuple[str, ...] = tuple(MINERS)

mine_official_plane = MINERS["official_plane"]

__all__ = ["CODE", "MINERS", "MINER_KIND", "NAMES", "mine_official_plane"]
