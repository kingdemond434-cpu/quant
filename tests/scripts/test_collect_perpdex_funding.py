"""Unit normalisation, clock snapping and dedup for the perp-DEX funding collector (R0100 axis 5).

A wrong unit or a flipped sign here does not fail loudly. It writes a PLAUSIBLE number into an
append-only corpus that every downstream Aster/Lighter-vs-Binance spread build then reads as
truth, so the error is only discoverable by re-deriving the whole archive. These tests pin the two
conversions carrying that risk:

  * `lighter_rate_decimal` -- Lighter publishes PERCENT PER HOUR plus a `direction` field
    ("long" = longs pay = positive by CEX convention). Both the /100 and the sign flip are pinned,
    and the scale is anchored against a known Binance-comparable magnitude.
  * `_snap_ms` -- Aster settlement stamps carry +-6ms venue jitter (observed 1700006400002).
    Unsnapped, the SAME settlement reprints under two dedup keys and duplicates the corpus.

NO NETWORK. The only I/O-entangled function exercised (`fetch_lighter_funding`, `collect`) is
driven through the module's own `_get_json` / fetcher seams with monkeypatched payloads, and
`time.sleep` is neutralised so the paging loops are instant.
"""
from __future__ import annotations

import json
import time
from datetime import UTC, datetime

import pytest

from scripts import collect_perpdex_funding as pdf


def _ms(iso: str) -> int:
    return int(datetime.fromisoformat(iso).timestamp() * 1000)


# --------------------------------------------------------------- Lighter percent-per-hour units

def test_lighter_percent_per_hour_becomes_a_signed_decimal():
    """0.00125 %/h is 1.25e-5 per hour, NOT 0.00125 and NOT 1.25e-7."""
    got = pdf.lighter_rate_decimal(0.00125, "long")
    assert got == pytest.approx(1.25e-5, rel=1e-12)
    assert got != pytest.approx(0.00125), "raw percent passed through un-divided"
    assert got != pytest.approx(1.25e-7), "divided by 100 twice"


def test_lighter_hourly_rate_scales_to_the_binance_eight_hour_convention():
    """The whole point of the normalisation is cross-venue comparability: 0.00125 %/h summed over
    an 8h settlement window is exactly 0.0001 = 1bp, Binance's own base funding rate. If this
    assertion ever moves, the Aster/Lighter-vs-Binance spread is comparing different units."""
    hourly = pdf.lighter_rate_decimal(0.00125, "long")
    assert hourly * 8 == pytest.approx(1e-4, rel=1e-12)


def test_direction_short_flips_the_sign():
    """CEX convention: positive = longs pay. direction='short' means shorts pay -> negative."""
    assert pdf.lighter_rate_decimal(0.0125, "short") == pytest.approx(-1.25e-4, rel=1e-12)


@pytest.mark.parametrize("pct", [0.0, 0.00125, 0.05, 1.0])
def test_the_two_documented_directions_are_exact_mirrors(pct: float):
    assert pdf.lighter_rate_decimal(pct, "short") == pytest.approx(
        -pdf.lighter_rate_decimal(pct, "long"))


def test_an_unrecognised_direction_must_not_silently_mean_short():
    """REGRESSION (fixed 2026-08-05). Was `sign = 1.0 if direction == "long" else -1.0`, which
    mapped a MISSING field, a renamed value or a capitalised "Long" to NEGATIVE -- silently
    inverting rows in a 131k-row corpus, where the sign IS the mechanism. Now it refuses."""
    for bad in ("", "Long", "LONG", "longs", "unknown"):
        with pytest.raises(ValueError):
            pdf.lighter_rate_decimal(0.00125, bad)


# ---------------------------------------------------------------------- hour-grid clock snapping

def test_snap_ms_kills_the_observed_venue_jitter():
    """1700006400002 is the real Aster stamp the organ's docstring cites."""
    assert pdf._snap_ms(1_700_006_400_002) == 1_700_006_400_000
    assert pdf._snap_ms(1_700_006_399_998) == 1_700_006_400_000
    assert pdf._snap_ms(1_700_006_400_000) == 1_700_006_400_000


def test_snap_ms_is_idempotent_and_lands_on_the_grid():
    for jitter in (-6, -1, 0, 1, 6):
        snapped = pdf._snap_ms(1_700_006_400_000 + jitter)
        assert snapped % pdf._H1_MS == 0
        assert pdf._snap_ms(snapped) == snapped


def test_snap_ms_honours_an_eight_hour_grid():
    t0 = _ms("2026-08-01T00:00:00+00:00")
    assert t0 % pdf._H8_MS == 0, "fixture: UTC midnight is on the 8h settlement grid"
    assert pdf._snap_ms(t0 + 2, pdf._H8_MS) == t0
    assert pdf._snap_ms(t0 + pdf._H8_MS - 2, pdf._H8_MS) == t0 + pdf._H8_MS


# ------------------------------------------------------------------------- archive keys + dedup

def _row(venue: str, symbol: str, t: int, rate: float = 0.0001) -> dict:
    return {"t": t, "c": "venue", "r": t + 5, "venue": venue, "symbol": symbol,
            "kind": "funding", "rate": rate}


def test_a_jittered_reprint_of_the_same_settlement_is_one_row_not_two(tmp_path):
    """The corpus-duplication guard: +-6ms of venue jitter must collapse to a single key."""
    out = tmp_path / "perpdex.jsonl"
    t = _ms("2026-08-01T08:00:00+00:00")
    keys: set = set()
    assert pdf._append_new(out, [_row("aster", "BTCUSDT", t)], keys) == 1
    assert pdf._append_new(out, [_row("aster", "BTCUSDT", t + 2)], keys) == 0
    assert pdf._append_new(out, [_row("aster", "BTCUSDT", t - 6)], keys) == 0
    assert len(out.read_text("utf-8").strip().splitlines()) == 1


def test_dedup_does_not_collide_across_venues_or_symbols(tmp_path):
    out = tmp_path / "perpdex.jsonl"
    t = _ms("2026-08-01T08:00:00+00:00")
    keys: set = set()
    n = pdf._append_new(out, [_row("aster", "BTCUSDT", t), _row("lighter", "BTCUSDT", t),
                              _row("aster", "ETHUSDT", t)], keys)
    assert n == 3


def test_load_keys_and_max_snaps_keys_but_resumes_from_the_raw_stamp(tmp_path):
    """Dedup uses the SNAPPED stamp; the resume cursor must use the RAW one, or a jittered-late
    stamp would be re-requested forever (or, worse, skipped)."""
    out = tmp_path / "perpdex.jsonl"
    t = _ms("2026-08-01T08:00:00+00:00")
    out.write_text("".join(json.dumps(r) + "\n" for r in
                           (_row("aster", "BTCUSDT", t + 2), _row("aster", "BTCUSDT", t - 3))),
                   "utf-8")
    keys, maxes = pdf._load_keys_and_max(out)
    assert keys == {("aster", "BTCUSDT", t)}
    assert maxes[("aster", "BTCUSDT")] == t + 2


def test_a_corrupt_line_does_not_poison_the_archive_read(tmp_path):
    out = tmp_path / "perpdex.jsonl"
    t = _ms("2026-08-01T08:00:00+00:00")
    out.write_text("\n".join([json.dumps(_row("aster", "BTCUSDT", t)),
                              "{not json",
                              json.dumps({"venue": "aster"}),          # missing symbol/t
                              json.dumps(_row("lighter", "BTC", t))]) + "\n", "utf-8")
    keys, maxes = pdf._load_keys_and_max(out)
    assert keys == {("aster", "BTCUSDT", t), ("lighter", "BTC", t)}
    assert set(maxes) == {("aster", "BTCUSDT"), ("lighter", "BTC")}


def test_read_funding_ignores_kline_rows_and_snaps_its_keys(tmp_path):
    out = tmp_path / "perpdex.jsonl"
    t = _ms("2026-08-01T08:00:00+00:00")
    lines = [json.dumps(_row("aster", "BTCUSDT", t + 2, rate=0.0003)),
             json.dumps({"t": t, "venue": "aster", "symbol": "BTCUSDT",
                         "kind": "kline_8h", "close": 100.0})]
    out.write_text("\n".join(lines) + "\n", "utf-8")
    series = pdf._read_funding(out)
    assert series == {("aster", "BTCUSDT"): {t: 0.0003}}


# --------------------------------------------------------------------- daily bucketing (Lighter)

def test_daily_sums_puts_the_midnight_print_in_the_day_it_opens():
    """Declared in _ALIGNMENT (c): the d+1 00:00 boundary print belongs to d+1, never to d, so
    day d's signal is complete at its last INTRA-day print."""
    prints = {_ms("2026-08-05T00:00:00+00:00"): 1.0,
              _ms("2026-08-05T08:00:00+00:00"): 2.0,
              _ms("2026-08-05T16:00:00+00:00"): 4.0,
              _ms("2026-08-06T00:00:00+00:00"): 8.0}
    got = pdf.daily_sums(prints)
    assert got["2026-08-05"] == pytest.approx(7.0)
    assert got["2026-08-06"] == pytest.approx(8.0)


# -------------------------------------------------------------------------- 8h grid alignment

def _grid(n: int, t0: int) -> list[int]:
    return [t0 + i * pdf._H8_MS for i in range(n)]


def test_align_8h_returns_the_period_ending_at_the_settlement():
    """align_8h yields the return of [T-8h, T); stage_a_screen then rolls the target forward one
    period, so the print at T is scored against [T, T+8h) exactly as _ALIGNMENT (b) declares."""
    t0 = _ms("2026-08-01T00:00:00+00:00")
    g = _grid(4, t0)
    kl = {g[0]: 100.0, g[1]: 110.0, g[2]: 121.0}
    dex = {g[2]: 0.0005, g[3]: 0.0006}
    cex = {g[2]: 0.0001, g[3]: 0.0002}
    ts, dr, cr, rets, gaps = pdf.align_8h(dex, cex, kl)
    assert ts == [g[2], g[3]]
    assert dr == [0.0005, 0.0006] and cr == [0.0001, 0.0002]
    assert rets[0] == pytest.approx(0.10)          # kl[g1]/kl[g0]-1, the bar ENDING at g[2]
    assert rets[1] == pytest.approx(0.10)
    assert gaps == 0


def test_align_8h_counts_grid_gaps_rather_than_hiding_them():
    t0 = _ms("2026-08-01T00:00:00+00:00")
    g = _grid(7, t0)
    kl = {g[0]: 100.0, g[1]: 110.0, g[2]: 121.0, g[3]: 130.0, g[4]: 140.0, g[5]: 150.0}
    dex = {g[2]: 0.1, g[3]: 0.1, g[6]: 0.1}        # g[4], g[5] missing -> one 24h jump
    cex = dict(dex)
    ts, _, _, _, gaps = pdf.align_8h(dex, cex, kl)
    assert ts == [g[2], g[3], g[6]]
    assert gaps == 1


def test_align_8h_requires_both_venues_to_have_printed():
    t0 = _ms("2026-08-01T00:00:00+00:00")
    g = _grid(4, t0)
    kl = {g[0]: 100.0, g[1]: 110.0, g[2]: 121.0}
    ts, _, _, _, _ = pdf.align_8h({g[2]: 0.1, g[3]: 0.1}, {g[3]: 0.1}, kl)
    assert ts == [g[3]], "a settlement only one venue printed cannot enter the spread"


def test_align_8h_drops_a_non_positive_previous_close():
    """A zero/negative close would make the return infinite or sign-inverted -- never emitted."""
    t0 = _ms("2026-08-01T00:00:00+00:00")
    g = _grid(4, t0)
    kl = {g[0]: 0.0, g[1]: 110.0, g[2]: 121.0}
    dex = {g[2]: 0.1, g[3]: 0.1}
    ts, dr, cr, rets, _ = pdf.align_8h(dex, dict(dex), kl)
    assert ts == [g[3]]
    assert len(dr) == len(cr) == len(rets) == 1


# --------------------------------------------------- Lighter fetcher: normalisation end-to-end

def test_fetch_lighter_funding_normalises_and_retains_the_raw_fields(monkeypatch):
    """The raw percent and direction must survive onto every row, or the normalisation stops
    being auditable against the source (organ docstring, UNITS paragraph)."""
    now_s = int(datetime.now(tz=UTC).timestamp())
    page = {"fundings": [
        {"timestamp": now_s - 3600, "rate": "0.00125", "direction": "long", "value": "1234.5"},
        {"timestamp": now_s - 1800, "rate": "0.0025", "direction": "short", "value": "9.5"},
        {"timestamp": now_s - 900, "rate": "oops", "direction": "long"},   # malformed -> skipped
    ]}
    urls: list[str] = []

    def fake(url: str):
        urls.append(url)
        return page, ""

    monkeypatch.setattr(pdf, "_get_json", fake)
    monkeypatch.setattr(time, "sleep", lambda *_: None)
    rows, err = pdf.fetch_lighter_funding("BTC", 1, now_s - 7200)

    assert err == "" and len(urls) == 1
    assert "market_id=1" in urls[0] and "resolution=1h" in urls[0]
    assert len(rows) == 2, "the malformed row is skipped, the page is kept"
    long_row, short_row = rows
    assert long_row["rate"] == pytest.approx(1.25e-5, rel=1e-12)
    assert long_row["rate_pct_raw"] == pytest.approx(0.00125)
    assert long_row["direction"] == "long"
    assert short_row["rate"] == pytest.approx(-2.5e-5, rel=1e-12)
    assert short_row["direction"] == "short"
    # clock provenance L1.46: venue settlement stamp in ms, c="venue", r=our receipt
    assert long_row["t"] == (now_s - 3600) * 1000
    assert long_row["c"] == "venue" and long_row["r"] >= long_row["t"]
    assert long_row["venue"] == "lighter" and long_row["symbol"] == "BTC"


def test_fetch_lighter_funding_advances_through_empty_pre_listing_windows(monkeypatch):
    """cursor must advance on an empty page or the backfill stalls at the epoch forever."""
    starts: list[int] = []

    def fake(url: str):
        starts.append(int(url.split("start_timestamp=")[1].split("&")[0]))
        return {"fundings": []}, ""

    monkeypatch.setattr(pdf, "_get_json", fake)
    monkeypatch.setattr(time, "sleep", lambda *_: None)
    rows, err = pdf.fetch_lighter_funding("BTC", 1, 0)
    assert rows == [] and err == ""
    assert len(starts) > 10
    assert starts == sorted(starts) and len(set(starts)) == len(starts)


def test_fetch_lighter_funding_surfaces_a_transport_error_and_keeps_partial_rows(monkeypatch):
    now_s = int(datetime.now(tz=UTC).timestamp())
    monkeypatch.setattr(pdf, "_get_json", lambda url: (None, "URLError: <urlopen error>"))
    monkeypatch.setattr(time, "sleep", lambda *_: None)
    rows, err = pdf.fetch_lighter_funding("BTC", 1, now_s - 7200)
    assert rows == []
    assert err.startswith("URLError"), "a dead venue must be REPORTED, never read as no history"


# --------------------------------------------------------------------- collect() refusal ladder

def _stub_fetchers(monkeypatch, *, aster_err: str = "", lighter_err: str = "",
                   lighter_bad: tuple[str, ...] = ()):
    t = _ms("2026-08-01T08:00:00+00:00")

    def aster(symbol, since_ms):
        if aster_err:
            return [], aster_err
        return [_row("aster", symbol, t)], ""

    def klines(symbol, since_ms):
        if aster_err:
            return [], aster_err
        return [{"t": t, "close_t": t + pdf._H8_MS, "c": "venue", "r": t, "venue": "aster",
                 "symbol": symbol, "kind": "kline_8h", "close": 100.0}], ""

    def lighter(symbol, market_id, since_s):
        if lighter_err or symbol in lighter_bad:
            return [], lighter_err or "URLError: down"
        return [_row("lighter", symbol, t)], ""

    monkeypatch.setattr(pdf, "fetch_aster_funding", aster)
    monkeypatch.setattr(pdf, "fetch_aster_klines_8h", klines)
    monkeypatch.setattr(pdf, "fetch_lighter_funding", lighter)
    monkeypatch.setattr(time, "sleep", lambda *_: None)


def test_collect_refuses_to_call_a_total_outage_a_quiet_day(monkeypatch, tmp_path):
    _stub_fetchers(monkeypatch, aster_err="URLError: down", lighter_err="URLError: down")
    rep = pdf.collect(tmp_path)
    assert rep["status"] == "ALL-VENUES-DOWN"
    assert rep["n_archive_rows"] == 0
    assert len(rep["venue_errors"]) == len(pdf.ASTER_SYMBOLS) * 2 + len(pdf.LIGHTER_MARKETS)


def test_collect_reports_a_single_dead_stream_as_degraded(monkeypatch, tmp_path):
    _stub_fetchers(monkeypatch, lighter_bad=("BTC",))
    rep = pdf.collect(tmp_path)
    assert rep["status"] == "DEGRADED", "one dead stream must not read as OK"
    assert list(rep["venue_errors"]) == ["lighter:BTC"]
    assert rep["appended"]["aster"] == len(pdf.ASTER_SYMBOLS)
    assert rep["appended"]["lighter"] == len(pdf.LIGHTER_MARKETS) - 1


def test_collect_is_idempotent_and_says_so(monkeypatch, tmp_path):
    _stub_fetchers(monkeypatch)
    first = pdf.collect(tmp_path)
    assert first["status"] == "OK" and sum(first["appended"].values()) > 0
    second = pdf.collect(tmp_path)
    assert second["status"] == "OK-UP-TO-DATE"
    assert sum(second["appended"].values()) == 0
    assert second["n_archive_rows"] == first["n_archive_rows"]


def test_collect_declares_the_clock_provenance_in_its_artifact(monkeypatch, tmp_path):
    _stub_fetchers(monkeypatch)
    rep = pdf.collect(tmp_path)
    assert "L1.46" in rep["clock_provenance"]
    assert "venue" in rep["clock_provenance"]


# ------------------------------------------------------------------------ declared screen floor

def test_the_harness_minimum_matches_the_screen_it_defers_to():
    """51 = zwin(20) + n_min(30) + 1. If axis_screen's floor moves, the refusal message here
    starts lying about when the axis becomes screenable."""
    assert pdf._HARNESS_MIN_PERIODS == 20 + 30 + 1
