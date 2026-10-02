"""Breadth proposals must name the family in the schema the judge consumes."""

from __future__ import annotations

import sys
from pathlib import Path


DESK = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(DESK))
from research import frontier_ceo  # noqa: E402


def test_ceo_breadth_family_reaches_judge_schema(monkeypatch) -> None:
    monkeypatch.setattr(frontier_ceo, "_missing_families",
                        lambda: [{"family": "vol_transition", "needs": "price only"}])
    monkeypatch.setattr(frontier_ceo, "_orphans", lambda: [])
    monkeypatch.setattr(frontier_ceo, "_audit_rows", lambda: {"admitted": []})
    monkeypatch.setattr(frontier_ceo, "_frontier_scout", lambda: {})
    proposals = frontier_ceo.propose()
    row = next(p for p in proposals if p.get("id") == "breadth:vol_transition")
    assert row["family"] == "vol_transition"
    assert row["blocked_on"] is None
