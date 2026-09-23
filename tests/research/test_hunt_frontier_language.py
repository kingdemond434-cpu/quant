"""Per-language frontier accounting (Tier-1 I17): a vector may carry its ground's language and
region, and the four outcomes roll up per language. Legacy coverage files carry neither field
and must load unchanged and report the rollup as UNMEASURED, never as "every language empty".
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from libs.research import hunt_frontier as hf


def test_language_and_region_round_trip_and_survive_a_call_that_omits_them(tmp_path: Path):
    st = hf.VectorState()
    hf.record(st, "七禾网", outcome="NAMED_ONLY", language="zh", region="cn")
    hf.record(st, "七禾网", outcome="YIELDED", findings=4)          # no language given: kept
    hf.record(st, "smart-lab", outcome="BLOCKED", blocker="paywall", language="ru", region="ru")
    f = tmp_path / "frontier.json"
    hf.save(st, f)
    back = hf.load(f)
    assert back.vectors["七禾网"].language == "zh" and back.vectors["七禾网"].region == "cn"
    assert back.vectors["七禾网"].outcome == "YIELDED" and back.vectors["七禾网"].findings == 4
    assert back.vectors["smart-lab"].language == "ru"
    raw = json.loads(f.read_text("utf-8"))["vectors"]["smart-lab"]
    assert raw["language"] == "ru" and raw["region"] == "ru"


def test_a_legacy_file_loads_and_reports_per_language_as_unmeasured(tmp_path: Path):
    f = tmp_path / "legacy.json"
    f.write_text(json.dumps({"vectors": {"a": {"first_seen": "2026-08-01T00:00:00+00:00"},
                                         "b": {"outcome": "YIELDED", "findings": 2}}}), "utf-8")
    st = hf.load(f)
    assert st.vectors["a"].language == "" and st.vectors["a"].region == ""
    s = hf.summarise(st)
    assert s["by_language"] is None and s["by_region"] is None
    assert s["languages_yielded"] is None
    assert "UNMEASURED" in s["by_language_note"]
    assert hf.rollup(st, "language") is None


def test_the_rollup_counts_every_outcome_per_language_largest_first():
    st = hf.VectorState()
    hf.record(st, "a", outcome="YIELDED", findings=3, language="zh", region="cn")
    hf.record(st, "b", outcome="EMPTY", language="zh", region="cn")
    hf.record(st, "c", outcome="NAMED_ONLY", language="zh", region="tw")
    hf.record(st, "d", outcome="BLOCKED", blocker="paywall", language="ja", region="jp")
    hf.record(st, "e", outcome="NAMED_ONLY", language="ja", region="jp")
    hf.record(st, "f", outcome="NAMED_ONLY")                           # unstated language
    by = hf.rollup(st, "language")
    assert list(by) == ["zh", "ja", "UNSTATED"]
    assert by["zh"] == {"NAMED_ONLY": 1, "BLOCKED": 0, "EMPTY": 1, "YIELDED": 1,
                        "findings": 3, "vectors": 3}
    assert by["ja"]["BLOCKED"] == 1 and by["ja"]["vectors"] == 2
    s = hf.summarise(st)
    assert s["by_language"] == by
    assert s["languages_yielded"] == ["zh"]
    assert s["languages_named_only"] == ["UNSTATED"], "ja has a BLOCKED attempt: not named-only"
    assert s["by_region"]["cn"]["vectors"] == 2 and s["by_language_note"] is None
    with pytest.raises(ValueError):
        hf.rollup(st, "outcome")


def test_the_existing_report_keys_are_untouched():
    st = hf.VectorState()
    hf.record(st, "a", outcome="YIELDED", findings=1, language="en")
    s = hf.summarise(st)
    for k in ("vectors", "unhunted", "blocked", "off_cooldown", "picked_over",
              "total_findings", "yield_rate", "should_hunt", "why", "headline", "note"):
        assert k in s
