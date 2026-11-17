"""Every miner runs 24/7 and never finishes (principal, 2026-11-03): a CDX walk wraps into
new-capture polling. The YouTube corpus tests left with the box YouTube collector (#662)."""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

import pytest

ROOT = Path(__file__).resolve().parents[2]
for p in (str(ROOT / "scripts"), str(ROOT / "desks" / "mt5"),
          str(ROOT / "desks" / "mt5" / "side_channels")):
    if p not in sys.path:
        sys.path.insert(0, p)



def test_a_cdx_walk_wraps_into_new_capture_polling(tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch) -> None:
    import seed_miners as sm
    monkeypatch.setattr(sm, "STATE", tmp_path / "st.json")
    pages = [json.dumps([["h"], ["k", "20260101", "darwinex.com/darwin/ABC"]]), "[]",
             json.dumps([["h"]])]
    asked: list[str] = []
    monkeypatch.setattr(sm, "fetch", lambda url, **kw: (asked.append(url), pages.pop(0))[1])
    st: dict[str, Any] = {}
    assert len(sm._cdx_page(st, "darwinex_cdx", "darwinex.com/darwin/*")) == 2
    assert st["darwinex_cdx_offset"] == 1
    sm._cdx_page(st, "darwinex_cdx", "darwinex.com/darwin/*")      # empty page: lap ends
    assert st["darwinex_cdx_offset"] == 0 and st["darwinex_cdx_laps"] == 1
    sm._cdx_page(st, "darwinex_cdx", "darwinex.com/darwin/*")
    assert "&from=" in asked[-1], "the next lap polls only captures made since the last began"
