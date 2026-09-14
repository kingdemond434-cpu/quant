"""The machinery mandate reaches midnight and the universal research entry point."""
from pathlib import Path


def test_breadth_machinery_is_injected_and_universal():
    target = "docs/research/BREADTH_MACHINERY_MANDATE.md"
    assert f"cat {target}" in Path("ops/run_midnight_codex_controller.sh").read_text("utf-8")
    assert target in Path("docs/RESEARCH.md").read_text("utf-8")
    mandate = Path(target).read_text("utf-8")
    for term in ("ADVISORY ONLY", "UNMEASURED", "Point-in-time", "Forced-flow",
                 "Cross-asset generators", "Axis-aware", "597", "mint no certificate",
                 "supersedes", "approved adoption", "falsifier"):
        assert term in mandate
