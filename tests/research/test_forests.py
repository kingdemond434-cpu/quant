"""The forest federation registry: the seventeen civilizations, the eleven roles, the tasks, and
the allocation contract -- including the two things the allocator is not allowed to do."""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from libs.research import forests as F  # noqa: E402

EXPECTED_IDS = {
    "japan", "korea", "china", "russia_cis", "south_asia", "asean", "oceania", "europe",
    "north_america", "latam", "mena", "africa",
    "global_macro", "global_web", "global_academic_code", "global_physical_data",
    "global_market_data",
}


def test_the_federation_is_exactly_the_declared_forests() -> None:
    assert set(F.FORESTS) == EXPECTED_IDS
    assert {f.id for f in F.REGIONAL_FORESTS} | {f.id for f in F.GLOBAL_FORESTS} == EXPECTED_IDS
    assert len(F.REGIONAL_FORESTS) == 12 and len(F.GLOBAL_FORESTS) == 5
    for fid, f in F.FORESTS.items():
        assert f.id == fid and f.name and f.mission
        assert f.kind in ("regional", "global")
        assert f.languages, f"{fid} reads nothing: a forest with no language is not a forest"


def test_the_eleven_roles_are_exact_and_the_scout_is_one_of_them() -> None:
    assert F.ROLES == (
        "source_scouts", "official_data", "practitioner", "academic", "code", "archive",
        "failure_miners", "mechanism_extractors", "data_agents", "candidate_compilers",
        "source_roi")
    assert len(F.ROLES) == 11 and len(set(F.ROLES)) == 11
    assert F.SCOUT_ROLE in F.ROLES
    assert set(F.ROLE_SHARE) == set(F.ROLES)
    assert abs(sum(F.ROLE_SHARE.values()) - 1.0) < 1e-9


def test_every_regional_country_belongs_to_exactly_one_forest() -> None:
    seen: dict[str, str] = {}
    for f in F.REGIONAL_FORESTS:
        for cc in f.countries:
            assert cc not in seen, f"{cc} is hunted by both {seen.get(cc)} and {f.id}"
            seen[cc] = f.id
        assert not any(c for c in F.GLOBAL_FORESTS if c.countries), \
            "a global forest carries no country list: its ground is a layer, not a place"
    assert F.forest_of_country("KR") == "korea"
    assert F.forest_of_country("br") == "latam"
    assert F.forest_of_country("ZZ") == "", "an unclaimed country is a gap, never a default"


def test_task_names_are_composed_camel_case_and_resident_tasks_tell_the_truth() -> None:
    assert F.camel("russia_cis") == "RussiaCis"
    assert F.camel("global_academic_code") == "GlobalAcademicCode"
    assert F.FOREST_TASKS["russia_cis"] == f"{F.TASK_PREFIX}-RussiaCis"
    assert set(F.FOREST_TASKS) == EXPECTED_IDS
    # Japan and macro were resident before the federation existed; the global LAYERS ride regions.
    assert F.resident_task("japan") == "MT5-Dept-Japan"
    assert F.resident_task("global_macro") == "MT5-Dept-Macro"
    assert F.resident_task("global_web") == "MT5-Dept-Regions"
    assert F.resident_task("korea") == "MT5-Forest-Korea"
    assert len(F.OWN_RESIDENT) == 11 and "japan" not in F.OWN_RESIDENT


def test_the_manifest_and_the_clock_fixer_declare_every_own_resident() -> None:
    manifest = (ROOT / "desks" / "mt5" / "ops" / "box_tasks.manifest").read_text("utf-8")
    fixer = (ROOT / "desks" / "mt5" / "research" / "clock_fixer.py").read_text("utf-8")
    for fid in F.OWN_RESIDENT:
        task = F.FOREST_TASKS[fid]
        assert f'name="{task}"' in manifest, f"{task} has no manifest line: unwired is a defect"
        assert f'"dept_{fid}"' in fixer, f"dept_{fid} is not a resident the clock fixer heals"
        assert task in fixer


def test_absent_packs_are_unmeasured_by_name_never_a_silent_zero() -> None:
    rows = F.unmeasured_packs("north_america")
    assert rows == [], "north_america declares no pack, so nothing is missing -- it has none"
    assert F.forest("north_america").packs == ()
    paths = F.pack_paths("korea")
    assert set(paths) == {"kr"} and paths["kr"].name == "pack.py"
    missing = F.unmeasured_packs("russia_cis")
    for row in missing:
        assert row["why"].startswith(F.UNMEASURED) and row["path"].endswith("pack.py")
        assert row["pack"] in F.forest("russia_cis").packs


def test_allocation_defaults_when_the_file_is_absent(tmp_path: Path) -> None:
    alloc = F.allocation_for("korea", tmp_path / "nothing.json")
    assert alloc.workers == F.DEFAULT_WORKERS == 4
    assert alloc.budget_s == F.DEFAULT_BUDGET_S == 3000
    assert alloc.scout_floor is True
    assert alloc.roi is None and F.UNMEASURED in alloc.why


def test_allocation_reads_the_roi_organs_contract(tmp_path: Path) -> None:
    p = tmp_path / "forest_allocation.json"
    p.write_text(json.dumps({
        "at": "2026-09-17T00:00:00+00:00", "rule": "workers by measured survivor yield",
        "forests": {"china": {"workers": 9, "budget_s": 4200, "scout_floor": True,
                              "roi": 0.31, "why": "three independent survivors this week"}}}),
        encoding="utf-8")
    alloc = F.allocation_for("china", p)
    assert (alloc.workers, alloc.budget_s, alloc.roi) == (9, 4200, 0.31)
    assert alloc.scout_floor is True and alloc.overrides == ()
    assert "survivors" in alloc.why and alloc.source == p.name
    # a forest the file is silent about keeps the federation's defaults, and says so
    other = F.allocation_for("korea", p)
    assert other.workers == 4 and F.UNMEASURED in other.why


def test_the_allocator_may_not_zero_a_forest_nor_silence_its_scout(tmp_path: Path) -> None:
    p = tmp_path / "forest_allocation.json"
    p.write_text(json.dumps({"forests": {"africa": {"workers": 0, "budget_s": 1,
                                                    "scout_floor": False, "roi": 0.0,
                                                    "why": "no survivor yet"}}}),
                 encoding="utf-8")
    alloc = F.allocation_for("africa", p)
    assert alloc.workers == 1, "a forest is never allocated zero workers"
    assert alloc.scout_floor is True, "the source scout always runs, whatever the allocator says"
    assert alloc.budget_s >= 11 * 5
    assert len(alloc.overrides) == 3
    assert any("refund" in o for o in alloc.overrides)


def test_role_plan_funds_all_eleven_scout_first_and_never_below_the_floor() -> None:
    alloc = F.allocation_for("korea", Path("nothing.json"))
    plan = F.role_plan("korea", alloc)
    assert [r for r, _s in plan] == [F.SCOUT_ROLE, *[r for r in F.ROLES if r != F.SCOUT_ROLE]]
    assert len(plan) == 11
    assert all(s >= F.MIN_ROLE_S for _r, s in plan)
    assert sum(s for _r, s in plan) <= alloc.budget_s + 1e-6
    tiny = F.Allocation(forest="korea", workers=1, budget_s=11 * int(F.MIN_ROLE_S))
    small = F.role_plan("korea", tiny)
    assert small[0][0] == F.SCOUT_ROLE and all(s >= F.MIN_ROLE_S for _r, s in small)


def test_census_names_the_rule_it_is_a_census_of() -> None:
    doc = F.census()
    assert doc["n_forests"] == 17 and doc["n_regional"] == 12 and doc["n_global"] == 5
    assert doc["roles"] == list(F.ROLES)
    assert doc["n_countries"] > 40
    assert "ja" in doc["languages"] and "ko" in doc["languages"] and "zh" in doc["languages"]
    assert "compute" in doc["rule"] and "scout" in doc["rule"]
