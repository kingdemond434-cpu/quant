"""§26(4) ALIGNMENT: the cross-venue funding join must bucket on the PAYMENT stamp.

WHY A TEST AND NOT A SCREEN RUN. The defect is currently LATENT, not live: the screen reports
NO-DATA because `data/binance_funding.jsonl` is absent, so the only venue with rows (bitmex,
11,148) has nothing to join against. A live run therefore CANNOT demonstrate the repair -- it
would print the same NO-DATA before and after. The moment the Binance collector lands, an
unfixed join would silently compare a BitMEX rate that pays one period LATE against a Binance
rate that pays immediately: a full 8h cross-venue misalignment, on the exact series the screen
is built from, with no symptom in the output. These tests are what makes the repair provable
today rather than the day it starts mattering.
"""

from __future__ import annotations

import json

import pytest
from scripts.screen_funding_spread import (
    _NOMINAL_INTERVAL_H,
    _hour_key,
    load_venue,
    venue_alignment,
)

_STAMP = "2026-08-01T00:00:00.000Z"


def test_bitmex_is_shifted_a_full_period_and_binance_is_not():
    """THE DEFECT, DIRECTLY. Same wall-clock stamp must NOT land in the same bucket."""
    bitmex_shift, bitmex_why = venue_alignment("bitmex")
    binance_shift, binance_why = venue_alignment("binance")

    assert bitmex_shift == pytest.approx(_NOMINAL_INTERVAL_H)
    assert bitmex_why == "PAYMENT-LAGGED"
    assert binance_shift == 0.0
    assert binance_why == "IMMEDIATE"

    assert _hour_key(_STAMP, bitmex_shift) == "2026-08-01T08"
    assert _hour_key(_STAMP, binance_shift) == "2026-08-01T00"
    assert _hour_key(_STAMP, bitmex_shift) != _hour_key(_STAMP, binance_shift)


def test_an_unread_venue_is_reported_not_silently_given_binance_mechanics():
    """The assumption that CAUSED the bug must not be the fallback that survives it."""
    shift, why = venue_alignment("hyperliquid")
    assert why == "UNREAD"
    assert shift == 0.0


def test_hour_key_default_is_unshifted_so_the_shift_is_always_explicit():
    assert _hour_key(_STAMP) == "2026-08-01T00"


def test_epoch_millisecond_stamps_shift_identically_to_iso_stamps():
    """The reader accepts three stamp formats; a shift that only worked on one would be worse
    than none -- it would misalign some rows and not others, inside a single venue."""
    epoch_ms = "1785542400000"                     # 2026-08-01T00:00:00Z
    assert _hour_key(epoch_ms) == _hour_key(_STAMP)
    assert _hour_key(epoch_ms, 8.0) == _hour_key(_STAMP, 8.0) == "2026-08-01T08"


def test_load_venue_applies_the_lag_to_real_rows(tmp_path):
    """End-to-end through the loader: the key a row lands under is its PAYMENT hour."""
    d = tmp_path / "data"
    d.mkdir()
    (d / "bitmex_funding.jsonl").write_text(
        json.dumps({"symbol": "XBTUSD", "timestamp": _STAMP, "fundingRate": 0.0003}) + "\n",
        "utf-8")
    got = load_venue(tmp_path, "bitmex")
    assert got == {("BTC", "2026-08-01T08"): pytest.approx(0.0003)}


def test_a_malformed_stamp_still_refuses_rather_than_shifting_garbage():
    assert _hour_key("not-a-date", 8.0) is None
    assert _hour_key(None, 8.0) is None


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(pytest.main([__file__, "-q"]))
