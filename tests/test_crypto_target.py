"""Executor-path tests for the live crypto target decision (scripts/run_crypto_target.py).

Covers the two pieces that decide what the testnet executor holds: cross-sleeve capital weighting
(`_sleeve_weights`) and the merge into one gross-normalized net book (`merge_sleeve_books`). Pure
logic only — no venue calls, no lake reads.
"""

from __future__ import annotations

import json

import pytest
from scripts.run_crypto_target import _sleeve_weights, merge_sleeve_books


def test_merge_is_gross_normalized_to_one() -> None:
    named = {
        "funding": {"BTCUSDT": 0.5, "ETHUSDT": -0.5},
        "momentum": {"ETHUSDT": 0.5, "SOLUSDT": -0.5},
    }
    sleeve_w = {"funding": 0.5, "momentum": 0.5}
    out = merge_sleeve_books(named, sleeve_w)
    assert sum(abs(v) for v in out.values()) == pytest.approx(1.0, abs=1e-4)


def test_merge_preserves_dollar_neutrality() -> None:
    # each sleeve is dollar-neutral (+0.5 / -0.5); the merged net book must stay ~neutral
    named = {
        "funding": {"BTCUSDT": 0.5, "ETHUSDT": -0.5},
        "momentum": {"SOLUSDT": 0.5, "XRPUSDT": -0.5},
    }
    out = merge_sleeve_books(named, {"funding": 0.5, "momentum": 0.5})
    assert sum(out.values()) == pytest.approx(0.0, abs=1e-4)


def test_merge_nets_offsetting_positions_and_drops_dust() -> None:
    # BTC is +0.5 in one sleeve and -0.5 in the other at equal capital -> nets to ~0 -> dropped
    named = {"a": {"BTCUSDT": 0.5, "ETHUSDT": -0.5}, "b": {"BTCUSDT": -0.5, "SOLUSDT": 0.5}}
    out = merge_sleeve_books(named, {"a": 0.5, "b": 0.5})
    assert "BTCUSDT" not in out
    assert set(out) == {"ETHUSDT", "SOLUSDT"}


def test_merge_empty_and_zero_gross_return_empty() -> None:
    assert merge_sleeve_books({}, {}) == {}
    # a single sleeve that nets to zero gross -> empty book, no ZeroDivision
    assert merge_sleeve_books({"a": {"BTCUSDT": 0.0}}, {"a": 1.0}) == {}


def test_sleeve_weights_equal_fallback_when_no_file(tmp_path, monkeypatch) -> None:
    import scripts.run_crypto_target as mod
    monkeypatch.setattr(mod, "_SLEEVE_W", tmp_path / "missing.json")
    w = _sleeve_weights(["funding", "momentum", "basis"])
    assert w == pytest.approx({"funding": 1 / 3, "momentum": 1 / 3, "basis": 1 / 3})


def test_sleeve_weights_uses_config_when_it_covers_the_set(tmp_path, monkeypatch) -> None:
    import scripts.run_crypto_target as mod
    p = tmp_path / "sleeve_weights.json"
    p.write_text(json.dumps({"weights": {"funding": 3.0, "momentum": 1.0}}), "utf-8")
    monkeypatch.setattr(mod, "_SLEEVE_W", p)
    w = _sleeve_weights(["funding", "momentum"])
    assert w == pytest.approx({"funding": 0.75, "momentum": 0.25})  # normalized from 3:1


def test_sleeve_weights_falls_back_when_config_misses_a_name(tmp_path, monkeypatch) -> None:
    import scripts.run_crypto_target as mod
    p = tmp_path / "sleeve_weights.json"
    p.write_text(json.dumps({"weights": {"funding": 3.0}}), "utf-8")  # missing 'momentum'
    monkeypatch.setattr(mod, "_SLEEVE_W", p)
    w = _sleeve_weights(["funding", "momentum"])
    assert w == pytest.approx({"funding": 0.5, "momentum": 0.5})  # equal fallback
