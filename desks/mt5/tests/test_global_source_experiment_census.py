"""Global regional acquisition and source-to-experiment wiring invariants."""

from __future__ import annotations

import sys
from pathlib import Path

DESK = Path(__file__).resolve().parents[1]
ROOT = DESK.parents[1]
for path in (DESK, DESK / "research", ROOT):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from research.countries.ae import data_plane as ae_plane  # noqa: E402
from research.countries.il import data_plane as il_plane  # noqa: E402
from research.countries.sa import data_plane as sa_plane  # noqa: E402
from research.countries.za import pack as za  # noqa: E402

from libs.research import country_lab as CL  # noqa: E402
from research import source_experiment_census as census  # noqa: E402


def test_broken_country_data_plane_dependencies_are_real_modules() -> None:
    for code, plane in (("ae", ae_plane), ("il", il_plane), ("sa", sa_plane)):
        assert code == plane.CODE
        doc = plane.run(dry_run=True, no_fetch=True)
        assert doc["acquisition_owner"].endswith("acquire_datasets")
        assert doc["no_fetch_is_owned"] is True
        assert isinstance(doc["lanes"], list)


def test_one_census_scope_includes_every_global_region() -> None:
    commands = {CL.resolve_pack(code).region_command for code in census._codes()
                if CL.resolve_pack(code) is not None}
    # The canonical command names are intentionally broad; this assertion prevents a later
    # regional optimization from silently narrowing the census to one continent.
    joined = " ".join(sorted(commands)).lower()
    for token in ("africa", "asia", "europe", "america", "mea", "oceania"):
        assert token in joined, (token, sorted(commands))


def test_south_africa_policy_target_is_versioned_not_backfilled() -> None:
    regimes = za.INFLATION_TARGET_REGIMES
    assert regimes[0]["effective_to"] == "2025-11-11"
    assert regimes[0]["lower_pct"] == 3.0 and regimes[0]["upper_pct"] == 6.0
    assert regimes[1]["effective_from"] == "2025-11-12"
    assert regimes[1]["point_pct"] == 3.0 and regimes[1]["tolerance_pp"] == 1.0


def test_hourly_cycle_runs_global_census_after_country_os() -> None:
    source = (DESK / "research" / "hourly_cycle.py").read_text("utf-8")
    os_at = source.index('gro = _costed("global_research_os"')
    acquire_at = source.index('acq = _costed("acquire_datasets"')
    census_at = source.index('sxc = _costed("source_experiment_census"')
    assert os_at < acquire_at < census_at
    assert '"acquire_datasets": acq' in source
    assert '"source_experiment_census": sxc' in source


def test_global_source_chain_has_one_resident_owner_and_enough_time_to_publish() -> None:
    source = (DESK / "research" / "hourly_cycle.py").read_text("utf-8")
    assert '"global_research_os", "acquire_datasets", "source_experiment_census"' in source
    assert '"acquire_datasets": 1_100' in source
