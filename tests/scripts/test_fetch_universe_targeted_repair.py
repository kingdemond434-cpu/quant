"""Targeted bar repair must preserve the full-universe ledger and merge into the registry."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "desks" / "mt5" / "research" / "fetch_universe.py"


def test_targeted_symbol_filter_is_additive_and_has_its_own_receipt() -> None:
    src = SOURCE.read_text("utf-8")
    code = "\n".join(line for line in src.splitlines()
                     if not line.lstrip().startswith("#"))
    assert '"--symbols"' in src
    assert "candidates = [s for s in candidates if s.upper() in requested]" in src
    assert 'coverage_name = "bar_coverage_targeted.json" if requested else' in src
    assert '"status": "INIT_FAILED"' in src
    assert "raise SystemExit(2)" in src
    assert "registry = merge(registry, summary" in src
    assert "registry.update(summary)" not in code
