from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

DESK = Path(__file__).resolve().parents[1]
ROOT = DESK.parents[1]
for path in (str(DESK), str(DESK / "research"), str(ROOT)):
    if path not in sys.path:
        sys.path.insert(0, path)

from libs.research import country_lab as CL  # noqa: E402


def _global_os():
    path = DESK / "research" / "global_research_os.py"
    spec = importlib.util.spec_from_file_location("test_global_research_os_module", path)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_mapping_style_custom_miners_keep_their_entry_and_full_spec() -> None:
    pack = CL.CountryPack(
        code="zz", name="Zed", region_command="asia", currency="ZZZ",
        executable_instruments=("EURUSD",), native_languages=("zz",),
        custom_miners=({"name": "native_flow", "kind": "flow",
                        "domain_ids": ("ZZ-A",),
                        "entry": "research.countries.zz.miners:native_flow"},),
        domains=({"id": "ZZ-A", "title": "forced flow", "instruments": ("EURUSD",),
                  "conditions": ("month end",), "controls": ("ordinary days",)},))
    assert pack.custom_miners == ("research.countries.zz.miners:native_flow",)
    assert pack.custom_miner_specs[0]["name"] == "native_flow"
    assert pack.miner_domains["native_flow"] == ("ZZ-A",)


def test_absent_native_module_activates_hypothesis_only_adapter() -> None:
    pack = CL.CountryPack(
        code="zz", name="Zed", region_command="asia", currency="ZZZ",
        executable_instruments=("EURUSD",), native_languages=("zz",),
        custom_miners=({"name": "native_flow", "kind": "flow",
                        "domain_ids": ("ZZ-A",),
                        "entry": "research.countries.zz.miners:native_flow"},),
        domains=({"id": "ZZ-A", "title": "forced flow", "instruments": ("EURUSD",),
                  "conditions": ("month end",), "controls": ("ordinary days",)},))
    miners, notes = CL.load_custom_miners(pack)
    assert set(miners) == {"custom:native_flow"}
    assert any("hypothesis-only" in row for row in notes)
    ctx = CL.LabCtx(code="zz", dry_run=True)
    ctx.miner = "custom:native_flow"
    result = miners["custom:native_flow"](pack, ctx)
    assert result["implementation"] == "DECLARED_SPEC_ADAPTER"
    assert result["outcome"] == CL.OK


def test_global_os_conserves_every_discovered_pack_under_a_tiny_budget(tmp_path: Path) -> None:
    mod = _global_os()
    report, cursor = tmp_path / "report.json", tmp_path / "cursor.json"
    doc = mod.run(budget_s=0.01, dry_run=True, report=report, cursor=cursor)
    assert doc["conservation"]["identity_holds"] is True
    assert doc["packs_total"] == doc["packs_run"] + doc["conservation"]["deferred_to_cursor"]
    assert report.exists() and cursor.exists()
    assert json.loads(report.read_text("utf-8"))["next_index"] == doc["next_index"]
    assert doc["conservation"]["miner_identity_holds"] is True
    assert doc["conservation"]["declared_miners"] == doc["conservation"][
        "miners_with_disposition"]


def test_repository_has_a_real_global_country_surface() -> None:
    mod = _global_os()
    codes = mod.pack_codes()
    assert "sg" in codes and "ca" in codes and "kr" in codes
    assert len(codes) >= 70


def test_global_os_refuses_an_overlapping_pass(tmp_path: Path) -> None:
    mod = _global_os()
    lock = tmp_path / "country.lock"
    with mod.singleton(lock) as first:
        assert first is True
        with mod.singleton(lock) as second:
            assert second is False
