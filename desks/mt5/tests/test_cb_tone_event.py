"""`cb_tone_event`: central-bank speech tone as a dated event the sealed gauntlet can judge.

  0. only a row from a source whose own terms allow trading use is read: the BIS extract is
     noncommercial and a row shaped like it is refused and counted;
  1. a speech is keyed on its PUBLICATION day (`published_utc`), never its delivery date, and
     a stamp that cannot be trusted drops the row;
  2. no entry can precede the day after publication plus the largest broker offset;
  3. the surprise basis reads each day against the bank's own PRIOR language only;
  4. an absent corpus is a named refusal through the sealed builder, not a never-firing cell;
  5. the family, its proposer and the hourly leg are wired.
"""
from __future__ import annotations

import itertools
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

DESK = Path(__file__).resolve().parents[1]
ROOT = DESK.parent.parent
for _p in (str(DESK / "scripts"), str(DESK), str(ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from mt5desk import family_cb_tone as F  # noqa: E402


def _bars(n: int = 6000, end: str = "2026-06-30 23:00") -> pd.DataFrame:
    idx = pd.date_range(end=end, periods=n, freq="h", tz="UTC")
    rng = np.random.default_rng(5)
    close = pd.Series(1.1 + np.cumsum(rng.normal(0, 0.0006, n)), index=idx)
    return pd.DataFrame({"open": close.shift(1).fillna(close.iloc[0]), "high": close + 0.001,
                         "low": close - 0.001, "close": close, "tick_volume": 100.0}, index=idx)


_N = itertools.count()


def _speech(delivered: str, stamp: str, hawk: int, dove: int, ccy: str = "USD",
            source: str = "fed_board", terms: str = "permitted", access: str = "PUBLIC",
            url: str = "") -> dict:
    """One speech row; `stamp` is the publication day as YYMMDD."""
    return {"source": source, "terms": terms, "access": access,
            "terms_basis": "clause read on the bank's page",
            "bank": "Fed", "currency": ccy, "delivered": delivered,
            "published_utc": f"20{stamp[:2]}-{stamp[2:4]}-{stamp[4:6]}T14:30:00+00:00",
            "hawk": hawk, "dove": dove, "chars": 9000,
            "url": url or f"https://www.federalreserve.gov/newsevents/speech/"
                          f"{next(_N)}.htm", "title": "t"}


@pytest.fixture
def corpus(tmp_path, monkeypatch):
    path = tmp_path / "official_speech_tone.jsonl"

    def write(rows: list[dict]) -> Path:
        path.write_text("\n".join(json.dumps(r) for r in rows) + "\n", "utf-8")
        F._tone_days.cache_clear()
        return path
    monkeypatch.setattr(F, "SPEECHES", path)
    F._tone_days.cache_clear()
    yield write
    F._tone_days.cache_clear()


def test_the_publication_day_is_the_banks_own_stamp_or_the_row_is_dropped():
    row = _speech("2026-06-19", "260624", 1, 0)
    assert F.published_day(row) == pd.Timestamp("2026-06-24", tz="UTC")
    # a bare date has no hour: it may be a US-evening speech, so it is placed a day later
    assert F.published_day({"published_utc": "2026-06-24"}) == pd.Timestamp("2026-06-25", tz="UTC")
    assert F.published_day({"published_utc": "2026-06-24T22:30:00-05:00"}) == \
        pd.Timestamp("2026-06-25", tz="UTC")
    # no stamp, an unreadable one, or public BEFORE it was spoken: not placeable, never guessed
    assert F.published_day({"delivered": "2026-06-19"}) is None
    assert F.published_day({"published_utc": "soon"}) is None
    assert F.published_day({"published_utc": "2026-06-18", "delivered": "2026-06-19"}) is None


def test_only_a_permitted_row_from_a_registered_source_is_ever_read(corpus):
    bis_shaped = {"date": "2026-05-04", "bank": "Fed", "currency": "USD", "hawk": 9, "dove": 0,
                  "chars": 9000, "url": "https://www.bis.org/review/r260505a.htm", "title": "t"}
    corpus([bis_shaped,
            _speech("2026-05-04", "260505", 9, 0, terms="research_only"),
            _speech("2026-05-04", "260505", 9, 0, terms="unverified", source="rba"),
            _speech("2026-05-04", "260505", 9, 0, source="bis"),        # labelled, unregistered
            _speech("2026-05-04", "260505", 9, 0, source="snb")])
    assert F.tone_days("USD") is None
    assert F.LAST_DROPPED == {"terms_not_permitted": 3, "source_not_registered": 2}
    corpus([_speech("2026-05-04", "260505", 9, 0, access="LOGIN")])
    assert F.tone_days("USD") is None and F.LAST_DROPPED == {"access_not_public": 1}
    with pytest.raises(F.CbToneUnavailable, match=F.NO_PERMITTED_CORPUS):
        F.family_cb_tone_event(_bars(), currency="USD", tone="hawk", direction="long")
    # two keys: the registry holds only sources someone read the terms of, and never the BIS
    assert set(F.PERMITTED_SOURCES) == {"fed_board", "boc"}
    assert F.refusal(_speech("2026-05-04", "260505", 1, 0)) is None
    # neither the family nor its proposer opens the BIS extract
    for rel in ("mt5desk/family_cb_tone.py", "research/cb_tone_proposer.py"):
        assert "bis_speech_tone" not in (DESK / rel).read_text("utf-8")
    assert F.SPEECHES.name == "official_speech_tone.jsonl"


def test_a_speech_listed_twice_is_counted_once_and_a_bare_date_waits_a_day_longer(corpus):
    u = "https://www.federalreserve.gov/newsevents/speech/dup.htm"
    bare = _speech("2026-05-11", "260511", hawk=4, dove=0)
    bare["published_utc"] = "2026-05-11"
    corpus([_speech("2026-05-04", "260505", hawk=6, dove=0, url=u),
            _speech("2026-05-04", "260505", hawk=0, dove=60, url=u),     # second copy: ignored
            bare])
    s = F.tone_days("USD")
    assert s is not None and list(s.index) == [pd.Timestamp("2026-05-05", tz="UTC"),
                                               pd.Timestamp("2026-05-12", tz="UTC")]
    assert s.iloc[0] == 1.0 and F.LAST_DROPPED == {"duplicate_url": 1}
    times = F.event_times("USD", "hawk", 0.5)
    # full instant on D: knowable D+1 00:00 (+3h broker); bare date D: D+2 00:00 (+3h)
    assert times == [pd.Timestamp("2026-05-06 03:00", tz="UTC"),
                     pd.Timestamp("2026-05-13 03:00", tz="UTC")]


def test_no_entry_precedes_the_day_after_publication_plus_the_broker_offset(corpus):
    # delivered 2026-05-04, published 2026-05-18: fourteen days in which it did not exist
    corpus([_speech("2026-05-04", "260518", hawk=6, dove=0)])
    sig = F.family_cb_tone_event(_bars(), currency="USD", tone="hawk", min_abs=0.5,
                                 direction="short", hold_bars=24)
    assert len(sig) == 1
    floor = pd.Timestamp("2026-05-19 03:00", tz="UTC")
    assert sig[0].time >= floor and sig[0].time < floor + pd.Timedelta(hours=2)
    assert sig[0].side == -1 and sig[0].ttl_bars == 24
    # the delivery-date reading (the old screen's two-day lag) would have entered here
    assert sig[0].time > pd.Timestamp("2026-05-06", tz="UTC") + pd.Timedelta(days=10)


def test_same_day_speeches_pool_and_the_side_and_threshold_select(corpus):
    corpus([_speech("2026-05-11", "260512", hawk=1, dove=5),
            _speech("2026-05-11", "260512", hawk=0, dove=4),
            _speech("2026-05-20", "260521", hawk=3, dove=2),          # +0.2: below 0.5
            _speech("2026-05-25", "260526", hawk=0, dove=0),          # no directional language
            _speech("2026-05-27", "260528", hawk=2, dove=0, ccy="EUR")])
    s = F.tone_days("USD")
    assert s is not None and len(s) == 2
    assert s.iloc[0] == pytest.approx((1 - 9) / 10)
    assert F.LAST_DROPPED == {"no_directional_language": 1}
    dove = F.family_cb_tone_event(_bars(), currency="USD", tone="dove", min_abs=0.5,
                                  direction="long", hold_bars=24)
    hawk = F.family_cb_tone_event(_bars(), currency="USD", tone="hawk", min_abs=0.5,
                                  direction="long", hold_bars=24)
    assert len(dove) == 1 and hawk == []
    assert F.family_cb_tone_event(_bars(), currency="USD", tone="hawk", min_abs=0.1,
                                  direction="long", hold_bars=24) != []


def test_the_surprise_reads_each_day_against_its_own_past_only():
    idx = pd.date_range("2025-01-01", periods=30, freq="D", tz="UTC")
    s = pd.Series(np.linspace(-1, 1, 30), index=idx)
    z = F.tone_surprise(s, obs=5)
    assert z.index.min() == idx[5]
    assert z.iloc[0] == pytest.approx(s.iloc[5] - s.iloc[:5].mean())
    changed = s.copy()
    changed.iloc[20:] = 9.0                       # the future moves; the past reading does not
    assert F.tone_surprise(changed, obs=5).iloc[:14].equals(z.iloc[:14])


def test_an_absent_corpus_is_a_named_refusal_through_the_sealed_builder(corpus, tmp_path):
    import external_gauntlet as G
    with pytest.raises(F.CbToneUnavailable, match="USD"):
        F.family_cb_tone_event(_bars(), currency="USD", tone="hawk", direction="long")
    params = {"currency": "USD", "tone": "hawk", "min_abs": 0.5, "basis": "level",
              "direction": "long", "hold_bars": 24}
    assert G.build_cell("EURUSD", "cb_tone_event", params, {}, h1_override=_bars()) is None
    assert "CbToneUnavailable" in str(G.LAST_BUILD_FAILURE)
    corpus([_speech("2026-05-04", "260505", hawk=6, dove=0, ccy="EUR")])
    with pytest.raises(F.CbToneUnavailable):      # a corpus with no speech of this currency
        F.family_cb_tone_event(_bars(), currency="USD", tone="hawk", direction="long")
    # a malformed identity is the family's own [], as everywhere else
    assert F.family_cb_tone_event(_bars(), currency="", tone="hawk") == []
    assert F.family_cb_tone_event(_bars(), currency="EUR", tone="neutral") == []
    assert F.family_cb_tone_event(_bars(), currency="EUR", direction="flat") == []


def test_the_sealed_gauntlet_and_the_forward_clock_build_the_same_cell(corpus):
    import external_gauntlet as G
    from mt5desk import families_orthogonal as fo
    from mt5desk.family_call import signals
    corpus([_speech(f"2026-0{m}-0{d}", f"260{m}0{d + 2}", hawk=0, dove=5)
            for m in (3, 4, 5) for d in (2, 5)])
    params = {"currency": "USD", "tone": "dove", "min_abs": 0.5, "basis": "level",
              "direction": "long", "hold_bars": 24}
    df = _bars()
    a = G.build_cell("EURUSD", "cb_tone_event", dict(params), {}, h1_override=df)
    b = G.build_cell("EURUSD", "cb_tone_event", dict(params), {}, h1_override=df)
    assert a is not None and b is not None, G.LAST_BUILD_FAILURE
    sa = [(s.time, s.side, s.ttl_bars) for s in a["sigs"]]
    assert len(sa) == 6 and sa == [(s.time, s.side, s.ttl_bars) for s in b["sigs"]]
    assert {s[1] for s in sa} == {1}
    fwd = signals(fo.ORTHOGONAL_FAMILIES["cb_tone_event"], df, side=-1, params=params)
    assert [(s.time, s.side) for s in fwd] == [(t, sd) for t, sd, _ in sa]


def test_the_family_is_registered_and_passes_the_judges_own_preflight():
    import external_gauntlet as G
    from mt5desk import families_orthogonal as fo

    from research import family_policy, orthogonal_sweep
    assert fo.ORTHOGONAL_FAMILIES["cb_tone_event"] is F.family_cb_tone_event
    assert "cb_tone_event" in fo.FAMILY_INPUTS
    # every chart: the entry is an instant, and a restriction is an exception with a reason
    assert "cb_tone_event" not in fo.FAMILY_TIMEFRAMES
    assert "cb_tone_event" in orthogonal_sweep.NOT_SOURCED_HERE
    assert not family_policy.family_banned("cb_tone_event")
    spec = {"sym": "XAUUSD", "family": "cb_tone_event",
            "params": {"currency": "USD", "tone": "dove", "min_abs": 0.5, "basis": "surprise",
                       "direction": "long", "hold_bars": 72}}
    assert G.modifier_preflight(dict(spec)) is None
    assert G.economic_prior(dict(spec))["passed"]


def test_a_symbol_reads_the_central_banks_it_is_priced_in():
    from research import cb_tone_proposer as P
    held = {"USD", "EUR", "JPY", "GBP"}
    assert P.currencies_for("EURUSD", {"asset_class": "Forex", "currency_profit": "USD"},
                            held) == ["EUR", "USD"]
    assert P.currencies_for("XAUUSD", {"asset_class": "Commodities", "currency_profit": "USD"},
                            held) == ["USD"]
    assert P.currencies_for("USDZAR", {"asset_class": "Forex", "currency_profit": "ZAR"},
                            held) == ["USD"]
    assert P.currencies_for("AUS200", {"asset_class": "Indices", "currency_profit": "AUD"},
                            held) == []


def test_the_proposer_reports_unmeasured_without_a_corpus(corpus, tmp_path, monkeypatch):
    from research import cb_tone_proposer as P
    monkeypatch.setattr(P, "REPORT", tmp_path / "CB_TONE_PROPOSER.json")
    r = P.run(budget_s=5, donate=False)
    assert r["status"] == "UNMEASURED" and r["tests_run"] == "UNMEASURED"
    assert "no permitted central-bank tone corpus" in r["why"]
    assert r["parked_reason"] == "bis_terms_noncommercial"
    assert isinstance(r["symbols_parked"], int)
    assert json.loads((tmp_path / "CB_TONE_PROPOSER.json").read_text("utf-8"))["status"] == \
        "UNMEASURED"


def test_the_proposer_screens_the_grid_and_carries_its_cursor(corpus, tmp_path, monkeypatch):
    from research import cb_tone_proposer as P
    from research import proposer_common as pc
    corpus([_speech("2026-05-04", "260505", hawk=0, dove=5)])
    monkeypatch.setattr(P, "REPORT", tmp_path / "CB_TONE_PROPOSER.json")
    monkeypatch.setattr(pc, "universe_meta", lambda: {
        "EURUSD": {"asset_class": "Forex", "currency_profit": "USD"},
        "XAUUSD": {"asset_class": "Commodities", "currency_profit": "USD"}})
    monkeypatch.setattr(P, "_symbols", lambda meta: sorted(meta))
    monkeypatch.setattr(pc, "bars", lambda sym: _bars())
    monkeypatch.setattr(pc, "cost_frac", lambda sym, meta, close: 0.0001)
    seen: list[dict] = []

    def screen(d, sig, cost, unf):
        seen.append({"n": len(sig)})
        return None
    monkeypatch.setattr(pc, "screen", screen)
    r = P.run(budget_s=60, donate=False)
    grid = len(P.BASES) * len(F.TONES) * len(P.DIRECTIONS) * len(P.HOLDS)
    assert r["status"] == "OK" and r["symbols_swept"] == 2 and len(seen) == 2 * grid
    assert r["tests_run"] == 0 and r["cells_proposed"] == 0 and r["donated"] == 0
    assert r["corpus"]["currencies"]["USD"]["last_published"] == "2026-05-05"
    assert r["cursor_next"] == 0 and "corpus_age_days" in r


def test_the_hourly_cycle_runs_the_proposer_and_the_layer_ledger_knows_it():
    src = (DESK / "research" / "hourly_cycle.py").read_text("utf-8")
    assert 'cbt = _costed("cb_tone_proposer"' in src
    assert '"cb_tone_proposer": cbt' in src and '"cb_tone_proposer": 700' in src
    assert '"cb_tone_proposer": "regions"' in src
    layers = (ROOT / "libs" / "research" / "layers.py").read_text("utf-8")
    assert '"cb_tone_proposer": "prediction"' in layers
