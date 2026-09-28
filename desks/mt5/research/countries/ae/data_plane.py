"""UAE declared-data plane; acquisition is owned by the canonical hourly acquirer."""
from __future__ import annotations

from typing import Any

from countries._declared_data_plane import declared_lanes, report_path
from countries._declared_data_plane import run as _run

CODE = "ae"
LANES = declared_lanes(CODE)
REPORT = report_path(CODE)

def run(**kwargs: Any) -> dict[str, Any]:
    return _run(code=CODE, **kwargs)
