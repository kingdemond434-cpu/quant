"""The desk's registry, the organ, and the drift tests: manifest vs specs, RESIDENTS vs specs,
the leg on its clock and in its layer, every mandatory edge endpoint registered."""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

DESK = Path(__file__).resolve().parents[1]
ROOT = DESK.parents[1]
for p in (str(ROOT), str(DESK), str(DESK / "research")):
    if p not in sys.path:
        sys.path.insert(0, p)

from libs.ops.control_plane import edges, scheduler_gen  # noqa: E402
from libs.ops.control_plane.specs import UNMEASURED, derive_max_silence  # noqa: E402


def _load(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


comp = _load(DESK / "ops" / "components.py", "_t_components")
REG = comp.registry(ROOT)


def test_every_executable_has_a_spec_and_the_registry_does_not_lie():
    c = comp.census(ROOT)
    assert c["coverage"] == 1.0 and c["executables_unclaimed"] == []
    assert c["problems"] == []
    assert c["components"] >= c["executables"]


def test_specs_are_derived_from_every_declared_clock():
    kinds = {s.kind for s in REG}
    assert {"leg", "daily_step", "task", "resident", "timer", "executable"} <= kinds
    leg = REG.get("leg:control_plane")
    assert leg is not None and leg.schedule == "hourly_cycle:control_plane"
    assert leg.owner == "department:meta" and leg.timeout_s == 660
    assert leg.production_args == ("--once", "--budget-s", "600")
    assert "desks/mt5/research/control_plane.py" in leg.code_paths
    assert REG.get("daily:promoter") is not None
    assert REG.get("task:MT5-Gateway").criticality == "required"
    assert REG.get("component:control_plane").schedule == "MT5-ClockFixer"
    gauntlet = REG.get("leg:external_gauntlet")
    # DERIVED, NEVER ASSERTED. This read `== 2 * 3600` -- a literal that happened to equal the
    # derivation only while the judge's cycle budget was under 3,600 s. When the budget was
    # raised to 8,640 (2026-09-24: measured full pass ~134 min, and the leg had recorded ZERO
    # successful outcomes on six separate days) the freshness window correctly widened to
    # timeout + cadence, and a correct widening failed a test. The rule is what is pinned.
    assert gauntlet is not None
    assert gauntlet.max_silence_s == derive_max_silence(gauntlet.cadence_s, gauntlet.timeout_s)
    assert gauntlet.max_silence_s >= 2 * 3600


def test_residents_are_derived_and_silence_is_per_family():
    r = comp.residents()
    assert r["dept_discovery"] == ("MT5-Hourly", "MT5-Hourly.log", 14_400)
    assert r["dept_data"] == ("MT5-Dept-Data", "MT5-Dept-Data.log", 11_400)
    assert r["dept_korea"][0] == "MT5-Forest-Korea"
    assert r["moat_exploit"] == ("MT5-Moat-Exploit", "MT5-Moat-Exploit.log", 2_520)
    assert all(v[2] != 4 * 3600 for v in r.values() if v[0] != "MT5-Hourly")


def test_clock_fixer_residents_are_the_specs_not_a_copy():
    import clock_fixer as cf
    assert comp.residents() == cf.RESIDENTS
    src = (DESK / "research" / "clock_fixer.py").read_text(encoding="utf-8")
    assert "RESIDENTS: dict[str, tuple[str, str, int]] = {" not in src


def test_second_registries_agree_with_the_specs():
    scheduled = {s.schedule for s in REG if s.scheduled}
    for task in comp.swarm_tasks().values():
        assert task in scheduled
    from libs.research import forests
    for fid, task in forests.FOREST_TASKS.items():
        if fid in forests.RIDES:
            continue
        assert task in scheduled, fid


def test_manifest_is_generated_output_and_does_not_drift():
    d = scheduler_gen.manifest_drift(REG)
    assert d["missing"] == [] and d["mismatched"] == []
    assert scheduler_gen.timer_validate(REG)["ok"]


def test_write_manifest_preserves_comments_and_is_idempotent(tmp_path: Path):
    src = DESK / "ops" / "box_tasks.manifest"
    copy = tmp_path / "box_tasks.manifest"
    copy.write_text(src.read_text(encoding="utf-8"), encoding="utf-8")
    before = copy.read_text(encoding="utf-8")
    res = scheduler_gen.write_manifest(REG, copy)
    after = copy.read_text(encoding="utf-8")
    assert res["rows_added"] == [] and res["rows_rewritten"] == 0
    assert [ln for ln in before.splitlines() if ln.startswith("#")] == \
           [ln for ln in after.splitlines() if ln.startswith("#")]
    # a resident the registry knows and the manifest lost is appended under the generated block
    stripped = "\n".join(ln for ln in before.splitlines() if 'name="MT5-Moat-Explore"' not in ln)
    copy.write_text(stripped + "\n", encoding="utf-8")
    assert scheduler_gen.manifest_drift(REG, copy)["missing"] == ["MT5-Moat-Explore"]
    res = scheduler_gen.write_manifest(REG, copy)
    assert res["rows_added"] == ["MT5-Moat-Explore"]
    assert scheduler_gen.GENERATED_BANNER in copy.read_text(encoding="utf-8")
    assert scheduler_gen.manifest_drift(REG, copy)["missing"] == []


def test_task_xml_is_system_ignorenew_with_the_specs_limit(tmp_path: Path):
    s = REG.get("resident:dept_data")
    xml = scheduler_gen.task_xml(s)
    assert "<UserId>S-1-5-18</UserId>" in xml and "IgnoreNew" in xml
    assert "<ExecutionTimeLimit>PT3H</ExecutionTimeLimit>" in xml
    assert "<BootTrigger>" in xml and "<Interval>PT10M</Interval>" in xml
    assert "--dept data" in xml
    p = scheduler_gen.write_xml(s, tmp_path)
    assert p.read_bytes()[:2] in (b"\xff\xfe", b"\xfe\xff")           # UTF-16 BOM


def test_live_validation_names_missing_extra_disabled_and_wrong_trigger():
    live = {"MT5-Dept-Data": {"Scheduled Task State": "Disabled", "Repeat: Every": "0:10:00"},
            "MT5-Gateway": {"Scheduled Task State": "Enabled", "Repeat: Every": "1:00:00"},
            "MT5-Ghost": {"Scheduled Task State": "Enabled", "Repeat: Every": "0:05:00"}}
    v = scheduler_gen.validate(REG, live=live)
    assert v["measured"] and "MT5-Dept-Data" in v["disabled"] and "MT5-Ghost" in v["extra"]
    assert "MT5-ClockFixer" in v["missing"] and v["ok"] is False
    off = scheduler_gen.validate(REG, live=None, runner=lambda: "")
    assert off["measured"] is False and "UNMEASURED" in off["why"]
    assert scheduler_gen.apply(REG, confirm=False)["applied"] is False


def test_every_mandatory_edge_endpoint_is_a_registered_component():
    missing = sorted({cid for e in edges.REQUIRED_EDGES for cid in (e.producer, e.consumer)
                      if REG.get(cid) is None})
    assert missing == []


def test_the_leg_is_on_the_clock_in_its_department_and_layer():
    hc = _load(DESK / "research" / "hourly_cycle.py", "_t_hourly_cycle")
    assert hc.LEG_DEPARTMENT["control_plane"] == "meta"
    assert hc.LEG_BUDGET_SEC["control_plane"] >= 600
    src = (DESK / "research" / "hourly_cycle.py").read_text(encoding="utf-8")
    assert '_costed("control_plane"' in src and '"control_plane": cp' in src
    from libs.research import layers
    assert layers.LEG_LAYER["control_plane"] == "meta"
    assert "control_plane" in layers.scheduled_legs(ROOT)


def test_the_organ_observes_and_exits_zero_without_writing(capsys):
    import control_plane as organ
    rc = organ.main(["--once", "--budget-s", "30", "--no-write", "--dry-run"])
    out = capsys.readouterr().out
    assert rc == 0 and "DESK_CLOSED_AND_HEALTHY=" in out
    for name in ("component_coverage", "closed_loop_proof", "first broken invariant"):
        assert name in out
    rc2 = organ.main(["--once", "--budget-s", "30", "--no-write", "--strict"])
    assert rc2 in (0, 2)


def test_unclocked_executables_are_named_never_hidden():
    exes = [s for s in REG.by_kind("executable")]
    assert exes and all(s.schedule == UNMEASURED and s.cadence_s is None for s in exes)
    assert all(s.criticality == "optional" for s in exes)
