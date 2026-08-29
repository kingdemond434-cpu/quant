from __future__ import annotations

from pathlib import Path

DESK = Path(__file__).resolve().parents[1]


def test_shadow_forward_keeps_only_one_symbols_bars_resident() -> None:
    source = (DESK / "research" / "shadow_forward.py").read_text("utf-8")
    assert "enrolled.sort(" in source
    assert "if cached_symbol != sym:" in source
    assert "h1_cache.clear()" in source


def test_price_native_discoveries_do_not_build_the_external_universe() -> None:
    inputs = (DESK / "mt5desk" / "family_inputs.py").read_text("utf-8")
    gauntlet = (DESK / "scripts" / "external_gauntlet.py").read_text("utf-8")
    assert 'if "ext_" not in feature:' in inputs
    assert 'if "ext_" in feature:' in gauntlet
