"""Hourly leg `datahub_coverage`: which DataHub contracts are refreshed and reach judged cells.

Writes `desks/mt5/reports/DATAHUB_COVERAGE.json`. A thin entry point: run as a script from the
repo root, `libs/data/` must not lead `sys.path` (it holds a `calendar.py` that shadows the
standard library), so the logic lives in `libs/data/datahub_desk.py` and is imported from here.
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from libs.data.datahub_desk import main  # noqa: E402

if __name__ == "__main__":
    raise SystemExit(main())
