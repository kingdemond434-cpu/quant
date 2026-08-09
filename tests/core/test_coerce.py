from __future__ import annotations

import math

from libs.core.coerce import finite_float, integer, object_mapping, object_sequence


def test_numeric_boundary_coercion_is_finite_and_fail_closed() -> None:
    assert finite_float(2) == 2.0
    assert finite_float(True, 7.0) == 7.0
    assert finite_float("2", 7.0) == 7.0
    assert finite_float(math.inf, 7.0) == 7.0

    assert integer(2.0) == 2
    assert integer(False, 7) == 7
    assert integer(2.5, 7) == 7
    assert integer(math.nan, 7) == 7


def test_collection_boundary_coercion_rejects_text_and_non_string_keys() -> None:
    value = {"alpha": 1}
    assert object_mapping(value) is value
    assert object_mapping({1: "alpha"}) == {}
    assert object_mapping([("alpha", 1)]) == {}

    items = ["alpha", 1]
    assert object_sequence(items) is items
    assert object_sequence("alpha") == ()
    assert object_sequence(1) == ()
