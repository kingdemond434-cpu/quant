"""The Upbit day-candle boundary, pinned to primary evidence instead of belief.

WHY THIS FILE EXISTS. On 2026-07-29 libs/research/upbit_data.py acquired a `+ 1 day` shift on the
stated premise that `candle_date_time_utc` is a KST-day OPEN stamp. Nobody ever measured that
premise -- it was carried over from bithumb_kr_premium_lookahead, a real kill on a DIFFERENT venue
-- and it is false for Upbit. The shift silently 24h-mispaired every kimchi leg for three days.

The root cause was not the wrong belief; it was that an alignment policy had NO artifact behind its
factual claim, so nothing could contradict it. That is what these tests are: the claim, executable.

test_no_shift_regression is UNCONDITIONAL and offline -- it is the guard that fails the instant
anyone re-introduces a shift. test_boundary_from_primary_hourly needs the network and SKIPS when
it is unavailable, because a fence that cries wolf on a CI network blip gets switched off.
"""
from __future__ import annotations

import sys
import urllib.error
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from libs.research import upbit_data


def test_no_shift_regression(monkeypatch: pytest.MonkeyPatch) -> None:
    """The candle's label IS its UTC key. A `+1 day` (or any) shift fails here."""
    rows = [
        {"candle_date_time_utc": "2026-07-31T00:00:00", "trade_price": 90360000.0},
        {"candle_date_time_utc": "2026-07-30T00:00:00", "trade_price": 91620000.0},
    ]
    monkeypatch.setattr(upbit_data, "_fetch", lambda *a, **k: rows)

    keyed = upbit_data.upbit_daily_utc_keyed("KRW-BTC", 2)

    assert keyed == {"2026-07-31": 90360000.0, "2026-07-30": 91620000.0}, (
        "Upbit day candles are UTC-midnight-boundary: the candle labelled D closes at 24:00 UTC D, "
        "so the label is the key and NO shift is correct. See libs/research/upbit_data.py."
    )


def test_history_shares_the_one_keying(monkeypatch: pytest.MonkeyPatch) -> None:
    """The paginated deep-history form must key identically to the live form.

    A backfill that keys differently from the collector is the shape that let the 07-29 fix reach
    the live series while the history it was screened against kept the old join (R0068).
    """
    pages = [
        [{"candle_date_time_utc": "2026-07-31T00:00:00", "trade_price": 90360000.0}],
        [{"candle_date_time_utc": "2026-07-30T00:00:00", "trade_price": 91620000.0}],
        [],
    ]
    monkeypatch.setattr(upbit_data, "_fetch", lambda *a, **k: pages.pop(0))
    monkeypatch.setattr(upbit_data._time, "sleep", lambda _s: None)

    assert upbit_data.upbit_daily_history("KRW-BTC", pages=5) == {
        "2026-07-31": 90360000.0, "2026-07-30": 91620000.0,
    }


def test_partial_history_is_announced_not_silently_truncated(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str],
) -> None:
    """Pagination truncation is the failure mode that never throws -- it must be loud."""
    def _boom(*_a: object, **_k: object) -> list:
        raise urllib.error.URLError("simulated page failure")

    monkeypatch.setattr(upbit_data, "_fetch", _boom)
    out = upbit_data.upbit_daily_history("KRW-BTC", pages=3)

    assert out == {}
    assert "upbit page failed" in capsys.readouterr().out


@pytest.mark.parametrize("day", ["2026-07-30", "2026-07-31"])
def test_boundary_from_primary_hourly(day: str) -> None:
    """PRIMARY EVIDENCE: the daily close for D equals Upbit's own hourly close at 24:00 UTC D.

    The 23:00 UTC bar on D closes at 24:00 UTC D. If Upbit dailies were KST-day candles (opening
    15:00 UTC D-1), the daily close would instead match the 14:00 UTC bar -- the bar closing at
    15:00 UTC D. This asserts BOTH directions, so it fails whichever way the truth moves.
    """
    try:
        daily = upbit_data.upbit_daily_utc_keyed("KRW-BTC", 200)
        hourly = upbit_data.upbit_hourly_utc("KRW-BTC", 200, to=f"{day}T23:59:59Z")
    except (urllib.error.URLError, OSError, TimeoutError) as e:
        pytest.skip(f"Upbit unreachable ({e!r}) -- primary-evidence check needs the network")

    if day not in daily or f"{day}T23:00:00" not in hourly:
        pytest.skip(f"{day} outside the returned window (daily n={len(daily)})")

    close_2400 = hourly[f"{day}T23:00:00"]
    close_1500 = hourly.get(f"{day}T14:00:00")

    assert daily[day] == close_2400, (
        f"Upbit daily {day} close {daily[day]} != its own 24:00 UTC hourly close {close_2400}. "
        "The UTC-midnight-boundary premise in libs/research/upbit_data.py no longer holds -- "
        "re-derive the keying from primary data before trusting any Upbit join."
    )
    assert daily[day] != close_1500, (
        f"Upbit daily {day} close equals the 15:00 UTC price -- that is the KST-day-open "
        "signature. If this ever fires, Upbit changed its day boundary and the keying must shift."
    )
