"""R0257 -- dated rows that are not observations, and the verdict that must never be FAILING.

THE CLASS. Every staleness check the desk owns asks whether the collector RAN. Three of the four
live forward clocks answered yes while producing no new evidence, each in a different way, and all
three read ACCRUING:

  * `walcl_reserve_impulse`  -- deriver on a daily cron, FRED publishes WALCL weekly, so it
    re-stamped one 2026-07-29 measurement under a fresh date key: 3 dated rows, 1 distinct payload,
    reported "2/20 obs".
  * `defi_utilisation`       -- z20 was 0.0 until its window filled, and `sign(0) == 0`, so no
    position was taken on 4 of 5 days. Reported "5/20 obs" from 1 real bet.
  * `cny_premium`            -- 14 dated rows whose signal field was null in every single one.
    Reported "0/20 obs" and would have gone on doing so forever.

WHY IT MATTERS MORE THAN THE ROW SAID. The row framed this as clocks that "look ACCRUING". The
worse outcome is downstream: an all-zero return series is ACCRUING only while n < MIN_OBS and
turns FAILING at n >= 20 through the `t <= 0.0` branch. A clock that never measured anything would
have retired its own research ground as a REFUTED hypothesis -- a false null, the one direction
that raises no alarm anywhere on this desk, and precisely the L1.25 ordered diagnostic ("is the
instrument broken?") arriving too late to be asked.

These tests exercise `_evaluate` end to end against synthetic clock files. The existing two test
files drive `_stage_b_verdict` with `rng.normal` fixtures only -- variance strictly positive by
construction, so they are structurally incapable of expressing this bug.
"""
from __future__ import annotations

import json

import pytest
import scripts.run_axis_shadows as ras


def _clock(tmp_path, rows: list[dict], name: str = "clock.jsonl") -> str:
    p = tmp_path / name
    p.write_text("\n".join(json.dumps(r) for r in rows), "utf-8")
    return name


def _closes(dates: list[str], step: float = 0.01) -> dict[str, float]:
    """A steadily rising tape -- any real position produces a nonzero return."""
    return {d: 100.0 * (1.0 + step) ** i for i, d in enumerate(dates)}


@pytest.fixture
def patched(tmp_path, monkeypatch):
    monkeypatch.setattr(ras, "_ROOT", tmp_path)
    return tmp_path


def _dates(n: int) -> list[str]:
    return [f"2026-07-{d:02d}" for d in range(1, n + 1)]


def test_a_restamped_clock_is_degenerate_not_accruing(patched, monkeypatch):
    # walcl_reserve_impulse exactly: one measurement, re-emitted under three date keys.
    dates = _dates(3)
    rows = [{"date": d, "z20": -0.5487, "asof": "2026-07-29", "impulse": 0.002024} for d in dates]
    monkeypatch.setattr(ras, "_closes", lambda *_a, **_k: _closes(dates))
    r = ras._evaluate("walcl", _clock(patched, rows), "BTCUSDT", "z20", +1, 12)
    assert r["verdict"] == "DEGENERATE"
    assert r["dated_rows"] == 3 and r["distinct_observations"] == 1 and r["restamped"] == 1
    # The pre-fix reading was "2/20 obs" -- two forward days from one measurement.
    assert r["forward_days"] == 1


def test_a_signal_that_never_takes_a_position_is_degenerate(patched, monkeypatch):
    # defi_utilisation's z20 = [0, 0, 0, 0, ...]: sign(0) == 0, so no bet was ever placed.
    dates = _dates(6)
    rows = [{"date": d, "z20": 0.0, "utilisation": 0.45 + i / 1000} for i, d in enumerate(dates)]
    monkeypatch.setattr(ras, "_closes", lambda *_a, **_k: _closes(dates))
    r = ras._evaluate("defi", _clock(patched, rows), "BTCUSDT", "z20", -1, 12)
    assert r["verdict"] == "DEGENERATE"
    # Payloads are all DISTINCT here (utilisation moves daily), so de-duplication alone would miss
    # this entirely. Flat positions are a separate failure mode and need their own counter.
    assert r["restamped"] == 0 and r["flat_position"] == 5 and r["distinct_observations"] == 0


def test_a_null_signal_field_is_degenerate_however_long_it_collects(patched, monkeypatch):
    # cny_premium: 14 dated rows, z20 null in every one, reported "ACCRUING 0/20" indefinitely.
    dates = _dates(14)
    rows = [{"date": d, "z20": None, "premium": 0.01} for d in dates]
    monkeypatch.setattr(ras, "_closes", lambda *_a, **_k: _closes(dates))
    r = ras._evaluate("cny", _clock(patched, rows), "BTCUSDT", "z20", +1, 12)
    assert r["verdict"] == "DEGENERATE"
    assert r["dated_rows"] == 14 and r["unusable"] == 13 and r["distinct_observations"] == 0


def test_a_degenerate_clock_can_never_be_reported_as_a_refuted_hypothesis(patched, monkeypatch):
    """THE LOAD-BEARING ONE. Pre-fix, this exact input returned FAILING.

    30 dated rows, every position flat, so every realised return is exactly 0.0. That series has
    t == 0.0, which satisfies the `n >= MIN_OBS and t <= 0.0` branch -- so an instrument that has
    never measured anything would publish the same verdict as a hypothesis the market refuted.
    """
    dates = _dates(30)
    rows = [{"date": d, "z20": 0.0} for d in dates]
    monkeypatch.setattr(ras, "_closes", lambda *_a, **_k: _closes(dates))
    r = ras._evaluate("dead", _clock(patched, rows), "BTCUSDT", "z20", +1, 12)
    assert r["verdict"] == "DEGENERATE", "a broken instrument must not read as a refuted axis"
    assert r["verdict"] != "FAILING"


def test_a_healthy_clock_is_completely_unaffected(patched, monkeypatch):
    """NOTHING LOOSENS AND NOTHING MOVES. On a clock with no re-stamps and no flat days the new
    counters are all zero and every published statistic is what it was before."""
    dates = _dates(25)
    rows = [{"date": d, "z20": (1.0 if i % 2 else -1.0), "n": i} for i, d in enumerate(dates)]
    monkeypatch.setattr(ras, "_closes", lambda *_a, **_k: _closes(dates))
    r = ras._evaluate("healthy", _clock(patched, rows), "BTCUSDT", "z20", +1, 12)
    assert r["verdict"] in ("ACCRUING", "ELIGIBLE", "FAILING")
    assert r["restamped"] == 0 and r["flat_position"] == 0 and r["unusable"] == 0
    # Every dated pair survived as an observation -- the filter took nothing from a clean clock.
    assert r["distinct_observations"] == len(rows) - 1 == r["forward_days"]


def test_degenerate_rows_can_only_subtract_observations(patched, monkeypatch):
    """The safety property, stated as a comparison rather than asserted in prose.

    Injecting re-stamps and flat days into a healthy clock must never RAISE the observation count
    the promotion gate reads. This is what makes the change safe to put on a live path: it can
    move an axis further from ELIGIBLE and never closer.
    """
    dates = _dates(25)
    clean = [{"date": d, "z20": (1.0 if i % 2 else -1.0), "n": i} for i, d in enumerate(dates)]
    monkeypatch.setattr(ras, "_closes", lambda *_a, **_k: _closes(dates))
    base = ras._evaluate("a", _clock(patched, clean, "a.jsonl"), "BTCUSDT", "z20", +1, 12)

    dirty = [dict(r) for r in clean]
    for i in (5, 6, 7):
        dirty[i] = {**dirty[i - 1], "date": dirty[i]["date"]}     # verbatim re-stamps
    for i in (15, 16):
        dirty[i] = {**dirty[i], "z20": 0.0}                        # flat days
    got = ras._evaluate("b", _clock(patched, dirty, "b.jsonl"), "BTCUSDT", "z20", +1, 12)
    assert got["forward_days"] < base["forward_days"]
    assert got["restamped"] == 3 and got["flat_position"] == 2


def test_a_clock_that_just_started_is_not_called_degenerate(patched, monkeypatch):
    """A two-row clock yields at most one observation by arithmetic, not by fault. Calling that
    an instrument failure would fire on every axis on its first day -- a fence red from birth is
    a fence that gets switched off (L1.43)."""
    dates = _dates(2)
    rows = [{"date": d, "z20": 0.0} for d in dates]
    monkeypatch.setattr(ras, "_closes", lambda *_a, **_k: _closes(dates))
    r = ras._evaluate("new", _clock(patched, rows), "BTCUSDT", "z20", +1, 12)
    assert r["verdict"] == "ACCRUING"
