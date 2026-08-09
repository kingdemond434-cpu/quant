"""Gap #39 on the SECOND venue: the Bybit tape must follow the traded book too."""
from __future__ import annotations

from scripts.run_recorder_bybit import _FALLBACK, _MAX_SYMBOLS, _universe


def _stub(listed):
    return lambda p, q: {"result": {"list": [{"symbol": s} for s in listed]}}


def test_universe_follows_the_traded_book_and_drops_unlisted():
    """#39 was closed on run_recorder.py while this second-venue tape kept a hardcoded list, so
    the two drifted and this one could intersect the traded book at ZERO -- the precise defect
    #39 named, still live on the venue nobody re-checked."""
    listed = {"BTCUSDT", "ETHUSDT", "SOLUSDT", "BNBUSDT", "XRPUSDT", "DOGEUSDT", "ADAUSDT"}
    u = _universe(http=_stub(listed))
    assert u != _FALLBACK
    assert all(s in listed for s in u)          # never poll a contract the venue does not list
    assert u[0] == "BTCUSDT"                    # benchmark first -- order is priority
    assert len(u) <= _MAX_SYMBOLS


def test_an_unreachable_venue_falls_back_rather_than_recording_nothing():
    """The asymmetry is deliberate and inverted from the rest of the desk: the 'action' here is
    reading public data with no key and no money at risk, while NOT acting is permanent -- an
    unrecorded day cannot be bought back at any price."""
    assert _universe(http=lambda p, q: None) == _FALLBACK
    assert _universe(http=_stub([])) == _FALLBACK


def test_a_universe_with_no_listed_overlap_falls_back_never_empty():
    """An empty symbol list would start the recorder polling nothing while reporting healthy."""
    u = _universe(http=_stub({"SOMETHINGELSE"}))
    assert u == _FALLBACK and len(u) > 0
