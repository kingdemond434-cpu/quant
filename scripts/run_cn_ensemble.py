#!/usr/bin/env python3
"""Hourly runner for the Chinese-model research ensemble (`libs/ops/cn_ensemble.py`).

Runs after the DeepSeek cycle in the MT5-DeepSeek box task. Always exits 0: a dark provider or a
failed call is a row in desks/mt5/reports/CN_MODEL_ENSEMBLE.json, never a failed scheduler run.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from libs.ops import cn_ensemble  # noqa: E402


def main() -> int:
    try:
        rep = cn_ensemble.run()
    except Exception as exc:
        print(json.dumps({"cn_ensemble": "ERROR", "why": f"{type(exc).__name__}: {exc}"}))
        return 0
    print(json.dumps({"cn_ensemble": "RAN", "calls": rep["calls"], "ok": rep["ok_calls"],
                      "distinct_ideas": rep["distinct_ideas"],
                      "multi_model_ideas": rep["multi_model_ideas"],
                      "lit": [k for k, v in rep["providers"].items() if v["lit"]]}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
