"""Tests for probe_language_moat (R0594).

NO NETWORK. `search` is monkeypatched everywhere: a test that reaches GitHub would be measuring
GitHub's rate limiter rather than this organ, and would go red for reasons that have nothing to
do with the code under test.
"""

from __future__ import annotations

import pytest

from scripts import probe_language_moat as plm

_SPEC = {"keys": ["native-a", "native-b"], "location": "japan", "control": "EN control"}


def _answers(monkeypatch, native, devs, control):
    calls = []

    def fake(kind, query, **_kw):
        calls.append((kind, query))
        if kind == "users":
            return devs
        if query == _SPEC["control"]:
            return control
        return native.pop(0) if native else 0

    monkeypatch.setattr(plm, "search", fake)
    monkeypatch.setattr(plm.time, "sleep", lambda _s: None)
    return calls


def test_A_POPULATION_WITHOUT_NATIVE_OUTPUT_IS_MOAT_UNSUPPORTED(monkeypatch) -> None:
    """THE AR RESULT, which is the measurement that produced this organ: 0 native repositories
    while ~99 region developers write about trading. The output exists and is in English, so it
    is already inside the EN seat's ground."""
    _answers(monkeypatch, [0, 0], 113, 469)
    rec = plm.probe_region("ar", _SPEC)
    assert rec["verdict"] == "MOAT-UNSUPPORTED"
    assert "RE-AIM" in rec["why"]
    assert "not grounds for cutting it" in rec["why"]


def test_NATIVE_OUTPUT_SUPPORTS_THE_MOAT(monkeypatch) -> None:
    """The other verdict, and the organ must be able to return it or its UNSUPPORTED carries no
    information (L1.63: a partition that cannot produce the other group is welded). CN measured
    1174 native repositories on the crypto vocabulary -- this is that shape."""
    _answers(monkeypatch, [900, 274], 300, 469)
    assert plm.probe_region("cn", _SPEC)["verdict"] == "MOAT-SUPPORTED"


def test_A_RATE_LIMITED_QUERY_IS_NEVER_READ_AS_A_ZERO(monkeypatch) -> None:
    """WS-005 on the one axis that would retire a region's ground by accident. A 403 and a genuine
    absence of native output are the same integer if the failure is coerced, and they are opposite
    facts."""
    _answers(monkeypatch, ["HTTP-403 (rate limit -- NOT a zero)", "HTTP-403"], 113, 469)
    rec = plm.probe_region("ar", _SPEC)
    assert rec["verdict"] == "UNMEASURED"
    assert rec["native_total"] is None


def test_A_DEAD_CONTROL_INVALIDATES_EVERY_ZERO_BESIDE_IT(monkeypatch) -> None:
    """The control is the instrument check. If the EN sibling for the same concept also returns
    nothing, the query shape is wrong and a native zero says nothing about the language."""
    _answers(monkeypatch, [0, 0], 113, 0)
    rec = plm.probe_region("jp", _SPEC)
    assert rec["verdict"] == "INSTRUMENT-BROKEN"
    assert "before reading anything else" in rec["why"]


def test_NO_OUTPUT_AND_NO_PEOPLE_IS_A_STATEMENT_ABOUT_THE_PROBE(monkeypatch) -> None:
    """Neither half established. That is not a finding about the region -- it is this probe
    failing to reach it, and it must not be reported as a moat verdict either way."""
    _answers(monkeypatch, [0, 0], 3, 469)
    assert plm.probe_region("jp", _SPEC)["verdict"] == "THIN-EVERYWHERE"


def test_THE_LOCATION_IS_QUOTED(monkeypatch) -> None:
    """A live-run repair, pinned. Unquoted, `location:united arab emirates trading` parses as
    location:united plus three loose words and returned ZERO developers for the AR region -- a
    malformed query rendering as an empty population, which is exactly the instrument fault this
    organ exists to avoid committing."""
    calls = _answers(monkeypatch, [0, 0], 113, 469)
    plm.probe_region("ar", {**_SPEC, "location": "united arab emirates"})
    user_q = next(q for kind, q in calls if kind == "users")
    assert user_q == 'location:"united arab emirates" trading'


def test_A_RUN_THAT_GRADED_NOTHING_IS_UNMEASURED_NEVER_OK(monkeypatch) -> None:
    """L1.57. A verdict about language moats earned over zero graded regions is vacuous, and here
    it would argue for leaving every seat exactly as it is."""
    _answers(monkeypatch, ["HTTP-403", "HTTP-403"], 113, 469)
    rep = plm.report({"ar": _SPEC})
    assert rep["status"] == "UNMEASURED"
    assert rep["n_graded"] == 0
    assert "does NOT say every" in rep["next_action"]


def test_the_probe_never_recommends_cutting_a_seat() -> None:
    """L1.25a: a null streak throttles nothing, anywhere. A negative result here re-aims a seat at
    where its population actually writes; it is not evidence that the region is dead, and the
    organ's own text must not be readable as though it were."""
    src = plm.__doc__ or ""
    assert "never grounds for cutting a seat" in src
    assert "L1.25a" in src


@pytest.mark.parametrize("region", sorted(plm.REGIONS))
def test_every_region_carries_all_three_queries(region: str) -> None:
    """The three-query shape IS the measurement: without the control a zero is unreadable, and
    without the location query "no output" cannot be told from "no people"."""
    spec = plm.REGIONS[region]
    assert spec["keys"] and spec["location"] and spec["control"]
