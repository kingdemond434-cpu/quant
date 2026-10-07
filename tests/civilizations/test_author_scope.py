"""NO AUTHOR IS MONITORED (2026-09-17) with ONE scoped exception (2026-10-06).

The principal's Roman Paolucci / Quant Guild directive of 2026-10-06
(/mnt/project-files/mandates/ROMAN_QUANT_GUILD_DIRECTIVE_2026-10-06.md, "PERMANENT SOURCE DELTA
MINER") orders five monitors: Roman's public GitHub, Quant Guild library updates, new public video
descriptions/transcripts when accessible, public research/papers, and public Quant Guild
letters/posts. It is the later, specific order and wins for that author only; everyone else stays
under the 2026-09-17 rule. These tests pin the scope so neither side can widen silently, and pin
that every lane the exception names exists and every web surface sits behind the terms gate.
"""
from __future__ import annotations

import importlib
import re
import sys
from pathlib import Path
from typing import Any

import yaml

from libs.mining import acquirer as acq

ROOT = Path(__file__).resolve().parents[2]
SC = ROOT / "desks" / "mt5" / "research" / "source_civilizations.py"
ROSTER = ROOT / "desks" / "mt5" / "data" / "source_rosters" / "civilizations.yaml"
#: every place a source lane can be declared
ROSTER_GLOBS = ("libs/mining/sources.yaml", "libs/mining/rosters/**/*",
                "desks/mt5/data/source_rosters/**/*",
                # the other organs' own source lists (audit 2026-10-07)
                "desks/mt5/data/deep_forest_sources.json", "desks/mt5/data/asia_sources.json",
                "desks/mt5/data/free_stack_sources.json",
                "desks/mt5/data/event_consensus_sources.json")
#: every fetcher that reaches the network; only `owned` holders fetch nothing
FETCHING = {"html_listing", "rss", "page_snapshot", "sitemap", "search_route",
            "youtube_channel", "json_api", "github_search", "git_mirror"}


def _sc() -> Any:
    desk = ROOT / "desks" / "mt5"
    for p in (str(desk), str(desk / "research")):
        if p not in sys.path:
            sys.path.insert(0, p)
    return importlib.import_module("research.source_civilizations")


def _rows() -> list[dict[str, Any]]:
    return list((yaml.safe_load(ROSTER.read_text("utf-8")) or {}).get("sources") or [])


def test_exactly_one_author_exception_scoped_to_the_five_public_surfaces() -> None:
    sc = _sc()
    assert set(sc.MONITORED_AUTHOR_EXCEPTIONS) == {"romanmichaelpaolucci"}
    row = sc.MONITORED_AUTHOR_EXCEPTIONS["romanmichaelpaolucci"]
    assert row["order"].startswith("principal 2026-10-06")
    scope = row["scope"]
    assert scope.startswith("public output only")
    for surface in ("public GitHub", "Quant Guild GitHub organisation", "Quant Guild library",
                    "YouTube descriptions", "papers", "letters/Medium/LinkedIn",
                    "terms gate", "fails closed"):
        assert surface in scope, surface
    assert "ten gates" in row["output"] and "nothing follows a post" in row["output"]
    doc = sc.__doc__ or ""
    assert "NO AUTHOR IS MONITORED" in doc and "ONE SCOPED EXCEPTION, 2026-10-06" in doc
    assert "rule\nabove stands for every other author" in doc


def test_every_named_lane_exists_and_every_quant_guild_lane_is_named() -> None:
    how = _sc().MONITORED_AUTHOR_EXCEPTIONS["romanmichaelpaolucci"]["how"]
    named = set(re.findall(r"civ_qg_\w+", how))
    rows = {r["id"]: r for r in _rows()}
    assert named and named <= set(rows), named - set(rows)
    qg = {i for i, r in rows.items() if r.get("civilization") == "quant_guild"}
    assert qg == named
    # the five directive monitors, each with at least one lane
    lanes = {rows[i]["lane"] for i in qg}
    assert {"qg_github", "qg_library", "qg_video", "qg_papers", "qg_letters",
            "qg_posts"} <= lanes


def test_every_quant_guild_lane_that_fetches_is_behind_the_terms_gate() -> None:
    fetching = [r for r in _rows() if r.get("civilization") == "quant_guild"
                and r.get("fetcher") != "owned"]
    assert {r["fetcher"] for r in fetching} <= FETCHING and len(fetching) == 8
    for r in fetching:
        terms = (r.get("config") or {}).get("terms")
        assert isinstance(terms, dict) and terms.get("url"), r["id"]
        src = acq.normalise_row(r, origin="t")
        assert src is not None
        refusal = acq.terms_refusal(src)
        if str(terms.get("status")).upper() == "PERMITTED":
            assert refusal is None and terms.get("clause"), r["id"]
        else:
            assert refusal is not None, r["id"]


def test_no_lane_in_any_roster_follows_a_named_author() -> None:
    """An arXiv author feed (`au:`) is a crawler pointed at a person: forbidden in EVERY roster
    unless the author is a recorded exception. A GitHub `user:` query or a YouTube channel is
    the same thing on the civilizations roster, allowed only on the exception's own lanes."""
    allowed = {k.lower() for k in _sc().MONITORED_AUTHOR_EXCEPTIONS}
    files = sorted({p for g in ROSTER_GLOBS for p in ROOT.glob(g) if p.is_file()
                    and p.suffix in (".yaml", ".yml", ".json", ".jsonl")})
    assert ROSTER in files
    for g in ROSTER_GLOBS[3:]:
        assert ROOT / g in files, g
    hits = [(str(p.relative_to(ROOT)), au)
            for p in files for au in re.findall(r"(?<![\w])au:([\w%.-]+)",
                                                p.read_text("utf-8", errors="replace"))
            if au.lower() not in allowed]
    assert hits == []
    for r in _rows():
        cfg = r.get("config") or {}
        personal = cfg.get("channel_id") or any(
            re.search(r"(?<![\w])user:", str(q)) for q in cfg.get("queries") or [])
        if personal:
            assert r.get("civilization") == "quant_guild", r["id"]
