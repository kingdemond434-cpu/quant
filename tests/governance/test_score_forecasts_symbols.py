"""The forecast scorer must parse the symbols the desk actually forecasts (R0367).

Two failure directions, and the quiet one is the dangerous one:

  * `S2USDT` matched nothing, so 46 forecasts aged past their deadline ungraded. An ungraded
    forecast never counts its miss, so the measured hit-rate can only rise -- and that bias feeds
    `calibrated_confidence` and from there Kelly leverage.
  * `1000PEPEUSDT` matched, but yielded `PEPEUSDT` -- a DIFFERENT contract priced 1000x apart.
    The forecast would have been resolved against the wrong series and scored confidently.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]


def _load():
    spec = importlib.util.spec_from_file_location(
        "_score_forecasts_under_test", ROOT / "scripts/score_forecasts.py")
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


@pytest.mark.parametrize(("claim", "symbol"), [
    ("Will S2USDT trade ABOVE 102.0 in 24 hours' time?", "S2USDT"),
    ("Will 1000PEPEUSDT trade ABOVE 0.0123 in 24 hours' time?", "1000PEPEUSDT"),
    ("Will BTCUSDT trade ABOVE 63216.2 in 24 hours' time?", "BTCUSDT"),
    ("Will 1000SHIBUSDC trade ABOVE 0.5 in 24 hours' time?", "1000SHIBUSDC"),
])
def test_digit_bearing_symbols_parse_exactly(claim: str, symbol: str) -> None:
    m = _load()._ABOVE.search(claim)
    assert m is not None, f"{claim!r} did not parse -- it would age out ungraded"
    assert m.group(1) == symbol, "parsed a DIFFERENT instrument than the claim names"


def test_multiplier_prefix_is_never_silently_dropped() -> None:
    """The regression that cost the most: a wrong answer that looks like a right one."""
    m = _load()._ABOVE.search("Will 1000PEPEUSDT trade ABOVE 0.0123 in 24 hours' time?")
    assert m is not None
    assert m.group(1) != "PEPEUSDT"


@pytest.mark.parametrize(("text", "symbol"), [
    ("SHORT 1000PEPEUSDT @7.34x stop 1.63% (... 73.47 cap ...)", "1000PEPEUSDT"),
    ("LONG S2USDT @13.97x stop 0.86% (below the 4h shelf at 62441.9)", "S2USDT"),
])
def test_conviction_patterns_take_digits_too(text: str, symbol: str) -> None:
    mod = _load()
    pat = mod._CONVICTION_SHORT if text.startswith("SHORT") else mod._CONVICTION
    m = pat.search(text)
    assert m is not None and m.group(1) == symbol
