"""Hourly leg `tool_registry`: verify the desk's analytics tool catalogue and publish it.

Writes `desks/mt5/reports/TOOL_REGISTRY.json`. Logic lives in `libs/research/tool_registry.py`.
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from libs.research.tool_registry import main  # noqa: E402

if __name__ == "__main__":
    raise SystemExit(main())
