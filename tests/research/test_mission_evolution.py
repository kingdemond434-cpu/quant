"""Evolving missions: deterministic from a yield fixture, and an append-only version chain."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from libs.research import mission_evolution as ME  # noqa: E402

YIELD = ME.Yield(terms={"oil": 3, "gold": 0}, sources={"a": 2},
                 tried_terms=["oil", "gold", "zinc"], tried_sources=["a", "b"],
                 harvest={"XAUUSD": 2, "policy": 1})


def _seed():
    m = ME.seed("t", "base mission.", ["oil", "gold"], ["a", "b"], stamp="s0")
    return ME.Mission(**{**m.__dict__, "terms": {**m.terms, "zinc": 0.06}})


def test_evolution_is_deterministic_given_a_yield_fixture():
    a, da, ca = ME.evolve(_seed(), YIELD, "s1")
    b, db, cb = ME.evolve(_seed(), YIELD, "s1")
    assert ca and cb and a.as_row(da) == b.as_row(db)
    assert a.terms["oil"] > 1.0 and a.terms["gold"] < 1.0       # paid grows, tried-dead decays
    assert "zinc" in a.retired and "zinc" not in a.terms         # non-seed below floor retires
    assert set(da["added"]) == {"xauusd", "policy"}              # claims' vocabulary expands
    assert a.sources["a"] > 1.0 and a.sources["b"] < 1.0
    assert a.parent == _seed().version and a.generation == 1
    assert a.text != _seed().text and "oil" in a.text


def test_a_seed_term_is_held_at_the_floor_never_retired():
    m = _seed()
    for i in range(30):
        m, _d, _c = ME.evolve(m, ME.Yield(tried_terms=["gold"]), f"s{i}")
    assert m.terms["gold"] == ME.FLOOR and "gold" not in m.retired


def test_nothing_tried_holds_the_mission():
    m = _seed()
    child, diff, changed = ME.evolve(m, ME.Yield(), "s1")
    assert not changed and child is m and "held" in diff


def test_version_log_is_append_only_and_verifiable(tmp_path):
    log = tmp_path / "m.jsonl"
    s0 = _seed()
    ME.append(log, s0)
    s1, d1, _ = ME.evolve(s0, YIELD, "s1")
    ME.append(log, s1, d1)
    assert ME.verify_chain(log) == {"ok": True, "rows": 2, "head": s1.version}
    assert ME.head(log).version == s1.version
    with pytest.raises(ValueError, match="append-only"):
        ME.append(log, s1, d1)                     # same parent again: a fork, refused
    with pytest.raises(ValueError, match="append-only"):
        ME.append(log, s0)                         # rewriting the root, refused
    rows = [json.loads(x) for x in log.read_text().splitlines()]
    rows[0]["terms"]["oil"] = 9.0                  # tampering is detected
    log.write_text("\n".join(json.dumps(r) for r in rows) + "\n")
    assert ME.verify_chain(log)["ok"] is False
