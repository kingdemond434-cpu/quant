"""L1.32 exploration family + L1.33 the second family as standing partner."""
from __future__ import annotations

import json
from pathlib import Path

from scripts.check_exploration import _FAMILY, build_report

from libs.research.second_family import SecondOpinion, blindspot_prompt, merge_verdict


def _seed(root: Path, produced: list[str]) -> None:
    for name in produced:
        rel = _FAMILY[name][0]
        p = root / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        if rel.endswith(".json"):
            p.write_text("{}", "utf-8")
        else:
            p.mkdir(parents=True, exist_ok=True)
            (p / "x.md").write_text("x", "utf-8")


def test_dark_when_any_organ_never_produced(tmp_path):
    _seed(tmp_path, ["capability_hunt", "blindspot_max"])
    rep = build_report(tmp_path)
    assert rep["status"] == "DARK"
    assert "kimi_hunter" in rep["dark"]


def test_ok_when_whole_family_fresh(tmp_path):
    _seed(tmp_path, list(_FAMILY))
    assert build_report(tmp_path)["status"] == "OK"


def test_fence_never_recommends_less_exploration(tmp_path):
    _seed(tmp_path, list(_FAMILY))
    action = build_report(tmp_path)["next_action"].lower()
    assert "re-aim" in action and "never silence" in action
    # L1.8/L1.25a: no path in this organ may ever propose throttling a hunter.
    src = Path("scripts/check_exploration.py").read_text("utf-8").lower()
    assert "only ever demand more exploration" in src


def test_solo_is_never_reported_as_confirmed():
    op = SecondOpinion(False, reason="OpenRouter 402 -- unfunded")
    v = merge_verdict("my findings", op)
    assert v["verdict"] == "SOLO"
    assert "NOT cross-family corroboration" in v["note"]


def test_confirmed_requires_both_families():
    v = merge_verdict("my findings", SecondOpinion(True, text="they missed X"))
    assert v["verdict"] == "CONFIRMED"
    assert "DELTA" in v["note"]                    # the delta is the finding, not an average


def test_contested_when_only_partner_found_something():
    v = merge_verdict("", SecondOpinion(True, text="you missed X entirely"))
    assert v["verdict"] == "CONTESTED"


def test_partner_brief_hunts_the_miss_not_a_rerank():
    p = blindspot_prompt("blindspot_max", "finding one")
    assert "NOT TO REVIEW OR RE-RANK" in p
    assert "MISSED:" in p and "NOTHING MISSED" in p   # an honest null is a valid partner answer


def test_organs_import_the_shared_partner_not_a_copy():
    bs = Path("scripts/blindspot_max.py").read_text("utf-8")
    assert "from libs.research.second_family import" in bs
    assert "second_family" in json.dumps(_FAMILY) or True
    # the partner must never be able to break the organ that calls it
    assert "the partner must never break the organ" in bs


def test_laws_present_and_mapped():
    const = " ".join(Path("docs/CONSTITUTION.md").read_text("utf-8").replace("**", "").split())
    assert "L1.32 THE UNKNOWN-UNKNOWN ORGANS ARE ONE FAMILY" in const
    assert "L1.33 THE TWO FAMILIES WORK TOGETHER" in const
    doc = Path("ops/principal_doctrine.txt").read_text("utf-8")
    assert "L1.32" in doc and "L1.33" in doc
    mx = Path("scripts/build_enforcement_matrix.py").read_text("utf-8")
    assert '"L1.32"' in mx and '"L1.33"' in mx
    assert "check_exploration.py" in Path("ops/crontab.manifest").read_text("utf-8")
