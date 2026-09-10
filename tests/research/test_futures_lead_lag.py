"""A 0.10 correlation between COMEX gold and a gold CFD is not a lead. It is a clock.

WHAT HAPPENED, because the tests exist to stop it happening again. The first version of this
module asked whether COMEX gold prices the metal before the CFD does -- an entry in the
`cross_asset_lead_lag` cluster, which `alpha_breadth` reports empty in both the traded and the
certified book. It answered: contemporaneous correlation 0.10, with a spike at minus three bars.
Two series on the same metal cannot correlate 0.10 within the hour, and chasing that spike would
have produced a certified sleeve that traded a timezone.

The desk's H1 parquet index is BROKER time carrying a UTC tzinfo, and the offset is +2 in winter
and +3 in summer. With the per-season offsets applied the correlation is 0.978 (gold) and 0.988
(silver) at lag 0 and NOISE at every other lag -- so the honest answer to the original question is
a clean null at H1, and the valuable finding is the clock.

THE PROPERTIES PINNED HERE:

    A SHIFT IS IN TIME, NEVER IN ROWS. `Series.shift(n)` moves n POSITIONS, and on an index with
    weekend and session gaps a position is not an hour: a row shift compares Friday's close with
    Monday's open at some lags and not others.

    A LOW POOLED CORRELATION IS EVIDENCE FOR DST, NOT A REASON TO STOP. When the offset differs
    between seasons no single whole-hour shift fits the whole sample -- the regimes split the
    correlation between two adjacent shifts, which is the 0.615 the pooled fit returns against
    0.91-0.99 within each season.

    NO LEAD IS REPORTED UNTIL THE ALIGNMENT IS RESOLVED. An unresolved alignment produces exactly
    the pattern a lead would -- near zero at lag 0, a spike a few bars out -- so the floor on the
    aligned lag-0 correlation is what separates a finding from an artifact.

    SHOULDER MONTHS ARE DROPPED, NOT GUESSED. March, April, October and November lie between the
    season windows and which offset applies depends on a changeover date this does not measure.
    Assigning them a neighbour's offset would bury an hour of error in a third of every year while
    looking like full coverage.
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))
_DESK = _ROOT / "desks" / "mt5"
for _p in (str(_DESK), str(_DESK / "research")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from desks.mt5.research import futures_lead_lag as fll  # noqa: E402

_RNG = np.random.default_rng(20260910)


def _walk(n: int, start: str = "2025-01-01", freq: str = "1h") -> pd.Series:
    idx = pd.date_range(start, periods=n, freq=freq, tz="UTC", name="time")
    return pd.Series(100.0 * np.exp(np.cumsum(_RNG.normal(0, 1e-3, n))), index=idx)


def test_a_pure_offset_is_recovered_exactly():
    """The whole method in one assertion: shift a series and the fit finds the shift."""
    truth = _walk(3000)
    shifted = truth.copy()
    shifted.index = shifted.index - pd.Timedelta(hours=3)      # "broker" bars stamped 3h early
    off, corr, n, _ = fll.align(fll._clean_returns(shifted), fll._clean_returns(truth))
    assert off == 3
    assert corr > 0.99 and n > fll.MIN_OVERLAP


def test_the_shift_is_in_time_and_not_in_rows():
    """With gaps, a row is not an hour -- and a row shift silently compares across weekends."""
    truth = _walk(3000)
    holed = truth.drop(truth.index[500:800])                   # a long session gap
    shifted = holed.copy()
    shifted.index = shifted.index - pd.Timedelta(hours=2)
    off, corr, _, _ = fll.align(fll._clean_returns(shifted), fll._clean_returns(truth))
    assert off == 2, "the gap moved the answer, so the shift was positional"
    assert corr > 0.99


def test_returns_never_span_a_gap():
    """A weekend return is not an hourly return, and a handful of enormous observations is enough
    to move a correlation made of small ones."""
    s = _walk(200)
    holed = s.drop(s.index[100])
    r = fll._clean_returns(holed)
    gaps = holed.index.to_series().diff()
    assert not any(gaps.loc[r.index] != pd.Timedelta("1h"))
    assert len(r) == len(holed) - 2      # the dropped bar removes its own return and the next


def test_a_dst_clock_defeats_the_pooled_fit_and_that_is_the_finding():
    """Two regimes split the correlation between two adjacent shifts, so the pooled best fit is
    weak by construction. Treating that as failure loses the answer."""
    truth = _walk(9000, start="2024-12-01")
    broker = truth.copy()
    summer = broker.index.month.isin(range(5, 10))
    idx = broker.index.to_series()
    idx[summer] -= pd.Timedelta(hours=3)
    idx[~summer] -= pd.Timedelta(hours=2)
    broker.index = pd.DatetimeIndex(idx)
    broker = broker.sort_index()

    _, pooled_corr, _, _ = fll.align(fll._clean_returns(broker), fll._clean_returns(truth))
    seasons = fll.seasonal_offsets(fll._clean_returns(broker), fll._clean_returns(truth))
    assert seasons["summer"]["offset_h"] == 3 and seasons["summer"]["agrees"]
    assert seasons["winter"]["offset_h"] == 2 and seasons["winter"]["agrees"]
    assert pooled_corr < max(r["corr"] for r in seasons["summer"]["readings"]), (
        "the pooled fit should be WORSE than either season's, which is the DST signature")


def test_applying_the_clock_drops_the_shoulder_months_and_says_how_many():
    """Which offset applies in March depends on a changeover date this does not measure."""
    r = fll._clean_returns(_walk(9000, start="2024-12-01"))
    seasons = {"summer": {"offset_h": 3, "agrees": True},
               "winter": {"offset_h": 2, "agrees": True}}
    out, applied = fll.apply_clock(r, seasons)
    # Assert on the SELECTION, undoing the shift: a bar legitimately inside a window can land in
    # the next month once shifted, and that is the shift working rather than a leak.
    picked = {(t.month, t.day) for t in (out.index - pd.Timedelta(hours=2))}
    assert not {m for m, _ in picked} & {4, 11}, "a shoulder month was guessed"
    # The windows end mid-month, so the days the fit excluded must be excluded here too.
    assert not [(m, d) for m, d in picked if m == 9 and d > 16], "September past the window end"
    assert 0.0 < applied["covered"] < 1.0
    assert applied["offsets"] == {"summer": 3, "winter": 2}


def test_an_unresolved_season_applies_nothing_rather_than_half_a_clock():
    r = fll._clean_returns(_walk(3000))
    out, applied = fll.apply_clock(r, {"summer": {"offset_h": None, "agrees": False},
                                       "winter": {"offset_h": None, "agrees": False}})
    assert out.empty and applied["covered"] == 0.0 and applied["offsets"] == {}


def test_no_lead_is_reported_while_the_alignment_is_unresolved(monkeypatch, tmp_path):
    """An unresolved alignment produces exactly the pattern a lead would."""
    a, b = _walk(3000), _walk(3000)                    # independent walks: nothing to align
    monkeypatch.setattr(fll, "fetch_bars", lambda *a_, **k: None)
    monkeypatch.setattr(fll, "cached", lambda s: pd.DataFrame({"close": a}))
    monkeypatch.setattr(fll, "desk_bars", lambda s: pd.DataFrame({"close": b}))
    r = fll.read_pair("X=F", "XXXUSD", "why", fetch=False)
    assert r.status == "CLOCK_UNRESOLVED"
    assert all(v is None for v in r.by_lag.values()), "a lead was reported from a bad alignment"
    assert r.best_lead is None


def test_a_resolved_clock_leaves_lag_zero_high_and_the_rest_noise(monkeypatch):
    """The live result: gold 0.978 at lag 0 and |corr| < 0.05 everywhere else."""
    truth = _walk(9000, start="2024-12-01")
    broker = truth.copy()
    idx = broker.index.to_series()
    summer = broker.index.month.isin(range(5, 10))
    idx[summer] -= pd.Timedelta(hours=3)
    idx[~summer] -= pd.Timedelta(hours=2)
    broker.index = pd.DatetimeIndex(idx)

    monkeypatch.setattr(fll, "fetch_bars", lambda *a_, **k: None)
    monkeypatch.setattr(fll, "cached", lambda s: pd.DataFrame({"close": broker.sort_index()}))
    monkeypatch.setattr(fll, "desk_bars", lambda s: pd.DataFrame({"close": truth}))
    r = fll.read_pair("X=F", "XXXUSD", "why", fetch=False)
    assert r.status == "MEASURED"
    assert r.by_lag[0] > 0.95
    assert all(abs(v) < 0.1 for k, v in r.by_lag.items() if k != 0 and v is not None)
    assert r.applied["offsets"] == {"summer": 3, "winter": 2}


def test_a_failed_fetch_never_touches_the_cache(monkeypatch, tmp_path):
    """A partial write shortens the sample without saying so, and a clock measured on a silently
    shorter window is a different measurement wearing the same name."""
    monkeypatch.setattr(fll, "CACHE", tmp_path / "ref")
    monkeypatch.setattr(fll.urllib.request, "urlopen",
                        lambda *a, **k: (_ for _ in ()).throw(OSError("down")))
    assert fll.fetch_bars("GC=F") is None
    assert not (tmp_path / "ref").exists()


def test_epoch_seconds_are_parsed_as_utc(monkeypatch):
    """This feed can measure a clock precisely because it carries no convention to be wrong
    about: epoch seconds are UTC by definition."""
    import io
    import json as _json
    doc = {"chart": {"result": [{"timestamp": [0, 3600],
                                 "indicators": {"quote": [{"close": [1.0, 2.0]}]}}]}}

    class _R(io.BytesIO):
        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

    monkeypatch.setattr(fll.urllib.request, "urlopen",
                        lambda *a, **k: _R(_json.dumps(doc).encode()))
    frame = fll.fetch_bars("GC=F")
    assert str(frame.index[0]) == "1970-01-01 00:00:00+00:00"
    assert str(frame.index.tz) == "UTC"


def test_the_clock_verdict_names_the_stored_scalar_it_contradicts():
    """`broker_clock_measured.json` records offset_by_trough 2 against offset_by_peak 3 on all
    ten symbols and stores the trough's answer. Both are right, in different seasons."""
    rows = [fll.Reading("X=F", "XXXUSD", "w", "MEASURED", 3, 0.98, 9000, {},
                        {"summer": {"offset_h": 3, "agrees": True},
                         "winter": {"offset_h": 2, "agrees": True}},
                        {"offsets": {"summer": 3, "winter": 2}, "covered": 0.66},
                        dict.fromkeys(fll.LAGS, 0.0), "")]
    v = fll.clock_verdict(rows)
    assert v["per_season"]["summer"]["offset_h"] == 3
    assert v["per_season"]["winter"]["offset_h"] == 2
    assert v["varies_with_dst"] is True
    assert "half of every year" in v["why"]


def test_the_module_writes_only_reports_and_its_own_cache():
    """Zero promotion authority: it fetches reference data and publishes two reports."""
    src = (_DESK / "research" / "futures_lead_lag.py").read_text(encoding="utf-8")
    for forbidden in ("universe.json", "sleeves.json", "subprocess", "def promote", "def size"):
        assert forbidden not in src, f"futures_lead_lag reached for {forbidden}"
    assert fll.OUT_REL.startswith("desks/mt5/reports/")
    assert fll.CLOCK_REL.startswith("desks/mt5/reports/")


@pytest.mark.parametrize("future,symbol,_why", fll.PAIRS)
def test_every_pair_prices_an_mt5_instrument(future, symbol, _why):
    """MANDATE: the futures side is reference data informing an MT5 instrument, never a hunted
    universe of its own."""
    assert future.endswith("=F"), future
    assert symbol.isalpha() and symbol.isupper(), symbol
