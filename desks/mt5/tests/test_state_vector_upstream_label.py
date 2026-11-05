"""The summary print must not crash on conditioning rows that carry no src (actor/latent rows)."""
from __future__ import annotations

from research.state_vector_build import _upstream_label


def test_causal_hint_row_keeps_its_old_shape():
    assert _upstream_label({"src": "USDX", "lag": 3, "clock": "H1", "weight": 0.5}) == \
        "USDX@3H1 w=0.50"


def test_actor_row_without_src_does_not_raise():
    assert _upstream_label({"actor": "trend_followers", "weight": -0.25}) == \
        "trend_followers w=-0.25"


def test_row_with_nothing_still_prints():
    assert _upstream_label({}) == "? w=?"
