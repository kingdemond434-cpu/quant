"""The judge must resolve the same existing constructors as forward execution."""
import inspect

import pytest
from mt5desk import families
from mt5desk.executables import hunt16_families, resolve_family


@pytest.mark.parametrize("name", [
    "dav_range_filter_adx", "dav_macd_qqe", "dav_supertrend_trail", "dav_abc_structure",
])
def test_original_constructor_is_visible_to_the_judge(name):
    original = hunt16_families()[name]
    exported = getattr(families, f"family_{name}")
    # The judge's export WRAPS the forward engine's constructor only to read a cell's `side`
    # param ("SHORT") as a direction (test_hunt16_side_param.py); the constructor underneath, its
    # signature and its signals are the forward engine's own.
    assert exported.__wrapped__ is original
    assert exported.__wrapped__ is resolve_family(name)
    assert inspect.signature(exported) == inspect.signature(original)


def test_unknown_family_stays_missing():
    assert getattr(families, "family_no_such_strategy", None) is None
    with pytest.raises(AttributeError):
        families.no_such_attribute
