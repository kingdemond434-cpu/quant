"""A converted row never names a family whose constructor needs evidence it cannot carry.

Measured on the box 2026-11-14: `moat_factory` rows claiming a softs `weather_window` were mapped
to `seasonal_window`, spread to 288 symbols, and every one reached the docket with params `{}`.
`family_seasonal_window` REQUIRES its window and side, so each raised TypeError in every sweep's
pre-warm. The converter carries a family, a symbol and a session only, so such a row is left for
the model instead of being converted into a cell that can never execute.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

DESK = Path(__file__).resolve().parents[1]
for p in (DESK, DESK.parents[1]):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

from research import local_converter as lc  # noqa: E402


def test_seasonal_window_names_its_required_window() -> None:
    assert set(lc._required_evidence("seasonal_window")) == {"start_md", "end_md", "side_bias"}


def test_a_family_with_defaults_needs_nothing() -> None:
    assert lc._required_evidence("session_range_breakout") == ()
    assert lc._required_evidence("no_such_family") == ()


def test_a_window_less_seasonal_row_is_left_for_the_model(tmp_path, monkeypatch) -> None:
    (tmp_path / "moat_factory").mkdir()
    (tmp_path / "moat_factory" / "a.jsonl").write_text(
        json.dumps({"family": "seasonal_window", "symbols": ["AUDCAD"], "title": "weather"})
        + "\n"
        + json.dumps({"family": "session_range_breakout", "symbols": ["XAUUSD"],
                      "title": "london"}) + "\n", "utf-8")
    monkeypatch.setattr(lc, "SOURCES", [tmp_path])
    monkeypatch.setattr(lc, "_known_symbols", lambda: {"AUDCAD", "XAUUSD"})
    monkeypatch.setattr(lc, "_known_families",
                        lambda: {"seasonal_window", "session_range_breakout"})
    out, stats = lc.convert(100)
    assert [c["family"] for c in out] == ["session_range_breakout"]
    assert stats["family_needs_evidence"] == 1
    assert stats["converted"] == 1
