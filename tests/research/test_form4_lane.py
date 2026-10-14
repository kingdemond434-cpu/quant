"""The Form 4 lane: fetch through a fake EDGAR, parse, cluster at acceptance, publish the breadth
series and the event store, donate each cell once -- and never show the User-Agent.

Every input is a fixture: no network, no tracked file touched.
"""
from __future__ import annotations

import json
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[2]
DESK = ROOT / "desks" / "mt5"
for _p in (str(ROOT), str(DESK), str(DESK / "research")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from mt5desk import families_orthogonal as fo  # noqa: E402
from mt5desk import family_insider_cluster as fic  # noqa: E402

from research import form4_lane as fl  # noqa: E402
from research import universe_policy as up  # noqa: E402

NOW = datetime(2026, 10, 14, 12, tzinfo=UTC)


def _xml(name: str, title: str, code: str, day: str, shares: float = 1000,
         price: float = 50.0) -> bytes:
    return f"""<?xml version="1.0"?>
<ownershipDocument>
 <issuer><issuerCik>0000320193</issuerCik><issuerTradingSymbol>AAPL</issuerTradingSymbol></issuer>
 <reportingOwner>
  <reportingOwnerId><rptOwnerName>{name}</rptOwnerName></reportingOwnerId>
  <reportingOwnerRelationship><isOfficer>1</isOfficer><officerTitle>{title}</officerTitle>
  </reportingOwnerRelationship>
 </reportingOwner>
 <nonDerivativeTable><nonDerivativeTransaction>
  <transactionDate><value>{day}</value></transactionDate>
  <transactionCoding><transactionCode>{code}</transactionCode></transactionCoding>
  <transactionAmounts><transactionShares><value>{shares}</value></transactionShares>
   <transactionPricePerShare><value>{price}</value></transactionPricePerShare>
   <transactionAcquiredDisposedCode><value>A</value></transactionAcquiredDisposedCode>
  </transactionAmounts>
  <postTransactionAmounts><sharesOwnedFollowingTransaction><value>9000</value>
  </sharesOwnedFollowingTransaction></postTransactionAmounts>
 </nonDerivativeTransaction></nonDerivativeTable>
</ownershipDocument>""".encode()


FILINGS = [  # (accession, acceptance wall clock, owner, title, code, txn day)
    ("0001-26-000001", "2026-09-02T17:00:00.000Z", "Cook Tim", "CEO", "P", "2026-09-01"),
    ("0001-26-000002", "2026-09-03T16:00:00.000Z", "Smith Jo", "CFO", "P", "2026-09-02"),
    ("0001-26-000003", "2026-09-03T18:00:00.000Z", "Grant Al", "Director", "A", "2026-09-02"),
]


def _edgar(calls: list[str]):
    sub = {"filings": {"recent": {
        "form": ["4"] * len(FILINGS) + ["10-K"],
        "accessionNumber": [f[0] for f in FILINGS] + ["0001-26-000099"],
        "acceptanceDateTime": [f[1] for f in FILINGS] + ["2026-09-04T10:00:00.000Z"],
        "primaryDocument": [f"xslF345X05/doc{i}.xml" for i in range(len(FILINGS))] + ["k.htm"],
    }}}
    docs = {f"doc{i}.xml": _xml(f[2], f[3], f[4], f[5]) for i, f in enumerate(FILINGS)}

    def get(url: str, headers: dict[str, str]) -> tuple[int, bytes]:
        calls.append(url)
        if url == fl.TICKER_MAP_URL:
            return 200, json.dumps({"0": {"cik_str": 320193, "ticker": "AAPL"}}).encode()
        if "submissions/CIK0000320193" in url:
            return 200, json.dumps(sub).encode()
        for name, body in docs.items():
            if url.endswith(name):
                assert "xslF345X05" not in url       # the raw XML, never the rendered page
                return 200, body
        return 404, b""
    return get


def test_acceptance_is_read_as_eastern_and_moved_late() -> None:
    at = fl.accepted_utc("2026-09-02T17:00:00.000Z")
    assert at == datetime(2026, 9, 2, 22, tzinfo=UTC)


def test_parse_keeps_codes_and_roles() -> None:
    rows = fl.parse_form4(_xml("Cook Tim", "CEO", "P", "2026-09-01"))
    assert rows == [{"issuer_ticker": "AAPL", "insider": "Cook Tim", "title": "CEO",
                     "txn_date": "2026-09-01", "code": "P", "shares": 1000.0, "price": 50.0,
                     "acquired_disposed": "A", "shares_after": 9000.0}]
    assert fl.parse_form4(b"<not-xml") == []


def test_a_pass_fetches_parses_clusters_and_publishes(tmp_path: Path,
                                                      monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(fl, "us_issuers", lambda: {"Apple": "AAPL"})
    calls: list[str] = []
    rep = fl.run(get=_edgar(calls), now=NOW, state_dir=tmp_path / "f4",
                 series_root=tmp_path / "series", dry_run=True)
    assert rep["fetch"]["filings_read"] == 3 and rep["transactions"] == 3
    # the grant (code A) is not a decision: one cluster of two P-code buyers
    assert rep["clusters"] == 1
    cl = [json.loads(x) for x in (tmp_path / "f4" / "clusters.jsonl").read_text().splitlines()]
    assert cl[0]["symbol"] == "Apple" and cl[0]["n_buyers"] == 2
    # dated at the LATEST acceptance in the cluster, moved late to UTC
    assert cl[0]["knowable_at"] == "2026-09-03T21:00:00+00:00"
    assert rep["backfill"]["complete"] is True
    # second pass: nothing re-read
    calls.clear()
    rep2 = fl.run(get=_edgar(calls), now=NOW, state_dir=tmp_path / "f4",
                  series_root=tmp_path / "series", dry_run=True)
    assert rep2["fetch"]["filings_read"] == 0 and rep2["transactions"] == 3


def test_the_breadth_point_knows_a_cluster_only_after_its_day_ends() -> None:
    cl = [{"knowable_at": "2026-09-03T21:00:00+00:00", "score": 2.0}]
    pts = fl.breadth_points(cl, datetime(2026, 9, 6, 1, tzinfo=UTC))
    by_day = {p["event_time"]: p for p in pts}
    assert by_day["2026-09-03"]["cluster_score_30d"] == 2.0
    assert by_day["2026-09-03"]["available_time"] == "2026-09-04T00:00:00+00:00"
    assert "2026-09-02" not in by_day                        # nothing before the first cluster
    assert pts[-1]["event_time"] == "2026-09-05"             # only complete days


def test_cells_wait_for_backfill_and_events_and_are_donated_once() -> None:
    assert fl.breadth_cells(fl.MIN_POINTS, False)[0] == []
    assert fl.breadth_cells(fl.MIN_POINTS - 1, True)[0] == []
    cells, why = fl.breadth_cells(fl.MIN_POINTS, True)
    assert why == "OK" and [c["symbol"] for c in cells] == ["US500", "NAS100", "US2000"]
    assert all(c["family"] == "exogenous_conditioner" for c in cells)
    clusters = [{"symbol": "Apple"}] * fl.MIN_EVENTS + [{"symbol": "Adobe"}]
    ev, accruing = fl.event_cells(clusters)
    assert [c["symbol"] for c in ev] == ["Apple"] and accruing == {"Adobe": 1}
    assert ev[0]["family"] == "insider_cluster_drift"
    state: dict = {"donated": [fl._identity(ev[0])]}
    assert fl.donate_new(ev + cells, state, dry_run=True) == {"new": 3, "already": 1}


def test_without_a_user_agent_nothing_is_fetched_and_the_ua_is_never_written(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv(fl.UA_ENV, raising=False)
    rep = fl.run(now=NOW, state_dir=tmp_path / "f4", series_root=tmp_path / "s",
                 dry_run=True)
    assert rep["fetch"]["status"] == "UNCONFIGURED" and rep["status"] == "UNMEASURED"
    secret = "Desk Research secret-contact@example.invalid"
    monkeypatch.setenv(fl.UA_ENV, secret)
    monkeypatch.setattr(fl, "us_issuers", lambda: {"Apple": "AAPL"})
    rep = fl.run(get=_edgar([]), now=NOW, state_dir=tmp_path / "f4b",
                 series_root=tmp_path / "s", dry_run=True)
    assert secret not in json.dumps(rep, default=str)
    for p in (tmp_path / "f4b").rglob("*"):
        if p.is_file():
            assert secret not in p.read_text(encoding="utf-8")


def test_the_event_family_is_registered_in_the_news_lane() -> None:
    assert fo.ORTHOGONAL_FAMILIES["insider_cluster_drift"] is fic.family_insider_cluster_drift
    assert "insider_cluster_drift" in up.NEWS_LANE_FAMILIES
    from research.axis_registry import classify_family
    assert classify_family("insider_cluster_drift")[:2] == ("trend_persistence", "event")


def test_the_event_family_enters_the_first_bar_after_acceptance(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    store = tmp_path / "clusters.jsonl"
    at = datetime(2024, 3, 20, 21, 30, tzinfo=UTC)
    store.write_text(json.dumps({"symbol": "Apple", "knowable_at": at.isoformat(),
                                 "score": 2.0}) + "\n", encoding="utf-8")
    monkeypatch.setenv("QUANT_FORM4_STORE", str(store))
    import libs.research.bar_clock as bc
    monkeypatch.setattr(bc, "to_bar_time", lambda w, root=None: (w + timedelta(hours=2),
                                                                 "OK", ""))
    t0 = datetime(2024, 3, 4, tzinfo=UTC)
    idx = pd.date_range(t0, t0 + timedelta(days=40), freq="1h", tz="UTC", inclusive="left")
    close = 100 * np.exp(np.cumsum(np.random.default_rng(3).normal(0, 0.002, len(idx))))
    df = pd.DataFrame({"open": close, "high": close * 1.002, "low": close * 0.998,
                       "close": close}, index=idx)
    sigs = fic.family_insider_cluster_drift(df, symbol="Apple")
    assert len(sigs) == 1 and sigs[0].side == 1
    assert sigs[0].time == pd.Timestamp(at + timedelta(hours=2)).ceil("1h")
    assert fic.family_insider_cluster_drift(df, symbol="Adobe") == []
