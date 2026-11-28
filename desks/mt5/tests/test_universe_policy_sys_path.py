"""asset_class_of must not grow sys.path per call (box stack samples 2026-11-10)."""
from __future__ import annotations

import json
import sys

import universe_policy as U


def _classless_registry(tmp_path, monkeypatch):
    uni = tmp_path / "universe.json"
    rows = {"WALGREENS": {"path": "Shares\\US"}, "EURUSD": {"asset_class": "forex"}}
    uni.write_text(json.dumps(rows), "utf-8")
    monkeypatch.setattr(U, "UNIVERSE", uni)
    U._registry.cache_clear()
    return uni


def test_a_classless_symbol_does_not_grow_sys_path_per_call(tmp_path, monkeypatch):
    _classless_registry(tmp_path, monkeypatch)
    U.asset_class_of("WALGREENS")
    before = len(sys.path)
    for _ in range(500):
        U.asset_class_of("WALGREENS")
    assert len(sys.path) == before
    U._registry.cache_clear()


def test_the_classifier_fallback_still_answers(tmp_path, monkeypatch):
    _classless_registry(tmp_path, monkeypatch)
    assert U.asset_class_of("WALGREENS") == U._norm(U._pattern_classifier()("WALGREENS"))
    assert U.asset_class_of("EURUSD") == U._norm("forex")
    assert U.asset_class_of("NOTREAL") == ""
    U._registry.cache_clear()


def test_base_is_on_sys_path_at_most_once_more():
    base = str(U.BASE)
    U._pattern_classifier.cache_clear()
    n = sys.path.count(base)
    U._pattern_classifier()
    U._pattern_classifier()
    assert sys.path.count(base) == max(n, 1)
