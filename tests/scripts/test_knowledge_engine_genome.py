"""R0094 (DI-16): the knowledge engine's data-lineage layer is GENERATED from the registry
build_data_registry.py writes -- the hand-written version covered 4 of ~60 sources and could
only rot. An asset's lineage is known when a collector or at least one consumer is named."""

from __future__ import annotations

from scripts.knowledge_engine import data_genome


def test_lineage_known_from_collector_or_consumer() -> None:
    assets = [
        {"id": "a", "collector": "scripts/collect_a.py", "consumers": [],
         "span": {"days": 100, "status": "measured"}},
        {"id": "b", "collector": None, "consumers": ["scripts/read_b.py"],
         "span": {"days": 50, "status": "measured"}},
        {"id": "c", "collector": None, "consumers": [], "span": {}},
    ]
    dg = data_genome(assets)
    assert dg["assets"] == 3
    assert dg["lineage_known"] == 2
    assert dg["coverage"] == round(2 / 3, 3)
    assert dg["orphans"] == ["c"], "an asset nothing writes and nothing reads is an orphan"


def test_empty_registry_is_zero_coverage_not_a_crash() -> None:
    dg = data_genome([])
    assert dg["assets"] == 0 and dg["coverage"] == 0.0
