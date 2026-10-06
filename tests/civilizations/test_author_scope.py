"""NO AUTHOR IS MONITORED (2026-09-17) with ONE scoped exception (2026-10-06).

The principal's Roman Paolucci / Quant Guild directive of 2026-10-06
(/mnt/project-files/mandates/ROMAN_QUANT_GUILD_DIRECTIVE_2026-10-06.md, "PERMANENT SOURCE DELTA
MINER": "monitor Roman's public GitHub") is the later, specific order. It wins for that author
only; everyone else stays under the 2026-09-17 rule. These tests pin the scope so neither side
can widen silently.
"""
from __future__ import annotations

import importlib
import re
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
SC = ROOT / "desks" / "mt5" / "research" / "source_civilizations.py"
ROSTER = ROOT / "desks" / "mt5" / "data" / "source_rosters" / "civilizations.yaml"


def _sc():  # type: ignore[no-untyped-def]
    desk = ROOT / "desks" / "mt5"
    for p in (str(desk), str(desk / "research")):
        if p not in sys.path:
            sys.path.insert(0, p)
    return importlib.import_module("research.source_civilizations")


def test_exactly_one_author_exception_scoped_to_public_github() -> None:
    sc = _sc()
    assert set(sc.MONITORED_AUTHOR_EXCEPTIONS) == {"romanmichaelpaolucci"}
    row = sc.MONITORED_AUTHOR_EXCEPTIONS["romanmichaelpaolucci"]
    assert row["order"].startswith("principal 2026-10-06")
    assert "public GitHub" in row["scope"] and "ten gates" in row["output"]
    doc = sc.__doc__ or ""
    assert "NO AUTHOR IS MONITORED" in doc and "ONE SCOPED EXCEPTION, 2026-10-06" in doc
    assert "rule\nabove stands for every other author" in doc


def test_no_civilization_lane_follows_a_named_author() -> None:
    """An arXiv author feed (`au:`) is a crawler pointed at a person: forbidden on every lane
    unless the author is a recorded exception."""
    allowed = {k.lower() for k in _sc().MONITORED_AUTHOR_EXCEPTIONS}
    rows = (yaml.safe_load(ROSTER.read_text("utf-8")) or {}).get("sources") or []
    hits = []
    for r in rows:
        for url in [str(r.get("url") or ""), *((r.get("config") or {}).get("feeds") or [])]:
            for au in re.findall(r"au:([\w%.-]+)", str(url)):
                if au.lower() not in allowed:
                    hits.append((r["id"], au))
    assert hits == []
