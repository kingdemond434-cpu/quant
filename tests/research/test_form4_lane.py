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


# ------------------------------------------------------------------------------- the hard stop

def _refusing(calls: list[str], status: int, on: str, retry_after: str | None = None):
    """The fake EDGAR, except every URL containing `on` answers `status`. robots.txt answers 404
    (no file: unrestricted) and is NOT counted in `calls`, which counts the SEC data requests;
    the robots reads are pinned by the robots tests at the end of this file."""
    inner = _edgar([])

    def get(url: str, headers: dict[str, str]):
        if url.endswith("/robots.txt"):
            return 404, b"", {}
        calls.append(url)
        if on in url:
            return status, b"", ({"Retry-After": retry_after} if retry_after else {})
        return inner(url, headers)
    return get


def _seed_register(path: Path) -> None:
    path.write_text(json.dumps({"note": "n", "sources": {"other": {"diagnosis": "X"}}}),
                    encoding="utf-8")


def test_a_403_holds_until_a_person_releases_it_and_the_release_keeps_history(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """A 403 places a hold that NO TIMER releases: passes at +25h, +11d and +400d each send 0
    requests. A person's release lets the next pass fetch; a second refusal places a new hold
    and the released one is kept in the register's history."""
    monkeypatch.setattr(fl, "us_issuers", lambda: {"Apple": "AAPL", "Zeta": "AAPL"})
    reg = tmp_path / "blocked_sources.json"
    _seed_register(reg)
    calls: list[str] = []
    rep = fl.run(get=_refusing(calls, 403, "/Archives/"), now=NOW, state_dir=tmp_path / "f4",
                 series_root=tmp_path / "s", dry_run=True, register=reg)
    # ticker map, submissions, then the refused document -- and nothing after it
    assert "/Archives/" in calls[-1] and len(calls) == 3
    assert rep["fetch"]["status"] == "METHOD_BLOCKED" and rep["status"] == fl.UNMEASURED
    assert rep["new_data"] == fl.UNMEASURED
    blk = rep["fetch"]["block"]
    assert set(blk) == {"key", "verdict", "status", "host", "url", "held_at", "released_by",
                        "released_at"}
    assert (blk["key"], blk["verdict"], blk["status"], blk["host"]) == (
        "site:www.sec.gov", "HARD_STOP", 403, "www.sec.gov")
    assert blk["held_at"] == NOW.timestamp() and blk["released_by"] is None
    doc = json.loads(reg.read_text(encoding="utf-8"))
    assert "other" in doc["sources"]                         # appended, never replaced
    assert doc["holds"]["site:www.sec.gov"]["released_by"] is None
    entry = doc["sources"][fl.REGISTER_KEY]
    assert entry["diagnosis"] == "HARD_STOP" and "HTTP 403" in entry["error"]
    assert "blocked_until" not in entry

    for later in (timedelta(hours=25), timedelta(days=11), timedelta(days=400)):
        calls.clear()
        rep2 = fl.run(get=_edgar(calls), now=NOW + later, state_dir=tmp_path / "f4",
                      series_root=tmp_path / "s", dry_run=True, register=reg)
        assert calls == [] and rep2["fetch"]["skipped"] is True, later
        assert rep2["fetch"]["status"] == "METHOD_BLOCKED" and rep2["status"] == fl.UNMEASURED

    fl._hs.release(reg, "site:www.sec.gov", "tester", now=NOW + timedelta(days=400, hours=1))
    calls.clear()
    rep3 = fl.run(get=_refusing(calls, 403, "submissions"), now=NOW + timedelta(days=401),
                  state_dir=tmp_path / "f4", series_root=tmp_path / "s", dry_run=True,
                  register=reg)
    assert calls and "submissions" in calls[-1]            # released: the next pass fetches
    assert rep3["fetch"]["block"]["key"] == "site:data.sec.gov"
    doc = json.loads(reg.read_text())
    kept = doc["holds"]["site:www.sec.gov"]                # the released hold keeps its record
    assert kept["released_by"] == "tester" and kept["held_at"] == NOW.timestamp()
    assert doc["holds"]["site:data.sec.gov"]["released_by"] is None
    # the same host refusing again moves the released row into history
    fl._hs.release(reg, "site:data.sec.gov", "tester", now=NOW + timedelta(days=402))
    fl.run(get=_refusing([], 403, "submissions"), now=NOW + timedelta(days=403),
           state_dir=tmp_path / "f4", series_root=tmp_path / "s", dry_run=True, register=reg)
    doc = json.loads(reg.read_text())
    assert doc["holds"]["site:data.sec.gov"]["released_by"] is None
    assert [(r["key"], r["released_by"]) for r in doc["hold_history"]] == [
        ("site:data.sec.gov", "tester")]


def test_a_429_records_retry_after_but_it_releases_nothing(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(fl, "us_issuers", lambda: {"Apple": "AAPL"})
    reg = tmp_path / "blocked_sources.json"
    sd = tmp_path / "f4"
    fl.run(get=_edgar([]), now=NOW, state_dir=sd, series_root=tmp_path / "s", dry_run=True,
           register=reg)                                     # one clean pass collects data
    state = json.loads((sd / "state.json").read_text())
    state["seen"] = []                                       # make the documents owed again
    state["backfilled"] = []
    (sd / "state.json").write_text(json.dumps(state))
    calls: list[str] = []
    rep = fl.run(get=_refusing(calls, 429, "submissions", retry_after="120"),
                 now=NOW, state_dir=sd, series_root=tmp_path / "s", dry_run=True, register=reg)
    assert len(calls) == 1 and "submissions" in calls[0]
    blk = rep["fetch"]["block"]
    assert (blk["verdict"], blk["status"], blk["key"]) == ("HARD_STOP", 429, "site:data.sec.gov")
    assert rep["fetch"]["retry_after_s"] == 120.0            # recorded ...
    assert rep["transactions"] == 3 and rep["clusters"] == 1   # held data still scored
    calls.clear()
    rep2 = fl.run(get=_edgar(calls), now=NOW + timedelta(seconds=121),
                  state_dir=sd, series_root=tmp_path / "s", dry_run=True, register=reg)
    assert calls == [] and rep2["clusters"] == 1             # ... and it released nothing
    assert rep2["new_data"] == fl.UNMEASURED


def test_a_401_reads_needs_key_and_only_a_release_lets_a_pass_fetch(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(fl, "us_issuers", lambda: {"Apple": "AAPL"})
    reg = tmp_path / "blocked_sources.json"
    calls: list[str] = []
    rep = fl.run(get=_refusing(calls, 401, "company_tickers"), now=NOW,
                 state_dir=tmp_path / "f4", series_root=tmp_path / "s", dry_run=True,
                 register=reg)
    assert len(calls) == 1 and rep["fetch"]["status"] == "NEEDS_KEY"
    assert json.loads(reg.read_text())["sources"][fl.REGISTER_KEY]["diagnosis"] == "HARD_STOP"
    held = fl.run(get=_edgar(calls), now=NOW + timedelta(hours=2), state_dir=tmp_path / "f4",
                  series_root=tmp_path / "s", dry_run=True, register=reg)
    assert held["fetch"]["skipped"] is True and len(calls) == 1
    fl._hs.release(reg, "site:www.sec.gov", "tester", now=NOW + timedelta(hours=3))
    rep2 = fl.run(get=_edgar([]), now=NOW + timedelta(hours=4), state_dir=tmp_path / "f4",
                  series_root=tmp_path / "s", dry_run=True, register=reg)
    assert rep2["fetch"]["status"] == "FETCHED" and rep2["status"] == "OK"
    assert "block" not in json.loads((tmp_path / "f4" / "state.json").read_text())


def test_a_hold_whose_register_write_failed_still_holds_until_released(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """The lane's own copy of its hold holds the next pass even when the register write failed;
    a person's release of the same key (made after it) releases that copy too."""
    monkeypatch.setattr(fl, "us_issuers", lambda: {"Apple": "AAPL"})
    reg = tmp_path / "blocked_sources.json"
    sd = tmp_path / "f4"
    real = fl._hs.place_hold

    def boom(*_a: object, **_k: object) -> None:
        raise OSError("disk full")
    monkeypatch.setattr(fl._hs, "place_hold", boom)
    rep = fl.run(get=_refusing([], 429, "company_tickers"), now=NOW, state_dir=sd,
                 series_root=tmp_path / "s", dry_run=True, register=reg)
    assert "disk full" in rep["fetch"]["persist_error"] and not reg.exists()
    monkeypatch.setattr(fl._hs, "place_hold", real)
    calls: list[str] = []
    fl.run(get=_edgar(calls), now=NOW + timedelta(days=30), state_dir=sd,
           series_root=tmp_path / "s", dry_run=True, register=reg)
    assert calls == []
    fl._hs.release(reg, "site:www.sec.gov", "tester", now=NOW + timedelta(days=31))
    fl.run(get=_edgar(calls), now=NOW + timedelta(days=32), state_dir=sd,
           series_root=tmp_path / "s", dry_run=True, register=reg)
    assert calls


def test_retry_after_reads_seconds_and_http_dates() -> None:
    assert fl.retry_after_s("30", NOW) == 30.0
    assert fl.retry_after_s("Wed, 14 Oct 2026 13:00:00 GMT", NOW) == 3600.0
    assert fl.retry_after_s("soon", NOW) is None and fl.retry_after_s(None, NOW) is None


# ------------------------------------------------------------------------------- audit 2026-10-14

def _row(insider: str, txn: str, filed: str, acc: str) -> dict:
    return {"symbol": "Apple", "insider": insider, "title": "Director", "txn_date": txn,
            "filed_at": filed, "code": "P", "shares": 1000.0, "price": 50.0,
            "accession": acc, "shares_after": 5000.0}


PROBE = [_row("A", "2026-05-01", "2026-05-05T22:00:00+00:00", "a1"),
         _row("B", "2026-05-04", "2026-05-06T22:00:00+00:00", "b1"),
         _row("C", "2026-05-02", "2026-05-20T22:00:00+00:00", "c1")]


def test_a_later_filing_never_reshapes_a_frozen_cluster() -> None:
    """The auditor's probe: A and B public on 05-06; C (transaction inside the window) filed on
    05-20. The 05-06 cluster stays where it was, and the 05-06..05-09 breadth points built on
    05-10 are exactly those built with C on file."""
    asof = [r for r in PROBE if r["filed_at"] <= "2026-05-10"]
    early, _new, _ = fl.score(asof)
    assert [(c["knowable_at"], c["n_buyers"]) for c in early] == [
        ("2026-05-06T22:00:00+00:00", 2)]
    full, new, _ = fl.score(PROBE, early)                  # the next pass, frozen store in hand
    assert new == [] and full == early
    rebuilt, _n, _ = fl.score(PROBE)                        # and from scratch, the same
    assert [(c["knowable_at"], c["buyers"]) for c in rebuilt] == [
        ("2026-05-06T22:00:00+00:00", ["A", "B"])]
    days = {f"2026-05-0{d}" for d in (6, 7, 8, 9)}
    p_early = {p["event_time"]: p for p in fl.breadth_points(early, datetime(2026, 5, 10,
                                                                             tzinfo=UTC))}
    p_full = {p["event_time"]: p for p in fl.breadth_points(rebuilt, datetime(2026, 5, 25,
                                                                              tzinfo=UTC))}
    assert all(p_early[d] == p_full[d] for d in days)
    assert all(p_full[d]["n_clusters_30d"] == 1 for d in days)


def test_a_new_cluster_is_appended_and_old_lines_are_never_rewritten(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(fl, "us_issuers", lambda: {"Apple": "AAPL"})
    sd = tmp_path / "f4"
    sd.mkdir()
    (sd / "transactions.jsonl").write_text(
        "".join(json.dumps(r) + "\n" for r in PROBE[:2]), encoding="utf-8")
    fl.run(get=_edgar([]), now=NOW, state_dir=sd, series_root=tmp_path / "s", dry_run=True)
    first = (sd / "clusters.jsonl").read_text(encoding="utf-8")
    more = [_row("D", "2026-07-01", "2026-07-02T22:00:00+00:00", "d1"),
            _row("E", "2026-07-02", "2026-07-03T22:00:00+00:00", "e1"), PROBE[2]]
    with (sd / "transactions.jsonl").open("a", encoding="utf-8") as fh:
        fh.writelines(json.dumps(r) + "\n" for r in more)
    rep = fl.run(get=_edgar([]), now=NOW, state_dir=sd, series_root=tmp_path / "s",
                 dry_run=True)
    after = (sd / "clusters.jsonl").read_text(encoding="utf-8")
    assert after.startswith(first) and rep["clusters_new"] >= 1


@pytest.mark.parametrize("status", [500, 0, 503])
def test_a_pass_with_no_200_is_unmeasured(tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
                                          status: int) -> None:
    monkeypatch.setattr(fl, "us_issuers", lambda: {"Apple": "AAPL"})
    calls: list[str] = []
    rep = fl.run(get=_refusing(calls, status, "sec.gov"), now=NOW, state_dir=tmp_path / "f4",
                 series_root=tmp_path / "s", dry_run=True, register=tmp_path / "r.json")
    assert rep["fetch"]["status"] == "FAILED"
    assert rep["status"] == fl.UNMEASURED and rep["new_data"] == fl.UNMEASURED
    assert not (tmp_path / "r.json").exists()          # a failure is not a block


def test_every_submissions_request_5xx_is_unmeasured(tmp_path: Path,
                                                     monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(fl, "us_issuers", lambda: {"Apple": "AAPL", "Zeta": "AAPL"})
    sd = tmp_path / "f4"
    sd.mkdir()
    (sd / "state.json").write_text(json.dumps({"ciks": {"AAPL": 320193}}))
    rep = fl.run(get=_refusing([], 502, "submissions"), now=NOW, state_dir=sd,
                 series_root=tmp_path / "s", dry_run=True)
    # data.sec.gov's robots.txt (one read a pass) and the two submissions requests
    assert rep["fetch"]["requests"] == 3 and rep["fetch"]["ok_responses"] == 0
    assert rep["status"] == fl.UNMEASURED and rep["new_data"] == fl.UNMEASURED


def test_a_user_agent_without_contact_is_unconfigured_and_never_echoed(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
        ) -> None:
    bare = "DeskResearchBot-without-contact"
    monkeypatch.setenv(fl.UA_ENV, bare)
    rep = fl.run(now=NOW, state_dir=tmp_path / "f4", series_root=tmp_path / "s", dry_run=True)
    assert rep["fetch"]["status"] == "UNCONFIGURED" and rep["status"] == fl.UNMEASURED
    assert bare not in json.dumps(rep, default=str) and bare not in capsys.readouterr().out
    assert fl.ua_has_contact("Desk Research ops@example.org")
    assert fl.ua_has_contact("Desk Research (+https://example.org/contact)")
    assert not fl.ua_has_contact("Desk Research")


def test_breadth_cells_carry_the_survivorship_caveat() -> None:
    cells, _ = fl.breadth_cells(fl.MIN_POINTS, True)
    assert all(any("SURVIVORSHIP" in c for c in cell["caveats"]) for cell in cells)


# ------------------------------------------------------------------------------- audit 2b4cd0942

ORDERED = [  # (accession, acceptance wall clock, owner, code, txn day) -- oldest first
    ("0002-26-000001", "2026-05-02T17:00:00.000Z", "Ann A", "P", "2026-05-01"),
    ("0002-26-000002", "2026-05-04T17:00:00.000Z", "Ben B", "P", "2026-05-03"),
    ("0002-26-000003", "2026-05-21T17:00:00.000Z", "Cat C", "P", "2026-05-20"),
    ("0002-26-000004", "2026-05-23T17:00:00.000Z", "Dan D", "P", "2026-05-22"),
    ("0002-26-000005", "2026-06-11T17:00:00.000Z", "Eve E", "P", "2026-06-10"),
    ("0002-26-000006", "2026-06-12T17:00:00.000Z", "Fay F", "P", "2026-06-11"),
]


def _edgar_listing(filings: list[tuple[str, str, str, str, str]], calls: list[str]):
    sub = {"filings": {"recent": {
        "form": ["4"] * len(filings),
        "accessionNumber": [f[0] for f in filings],
        "acceptanceDateTime": [f[1] for f in filings],
        "primaryDocument": [f"xslF345X05/d{f[0][-1]}.xml" for f in filings]}}}
    docs = {f"d{f[0][-1]}.xml": _xml(f[2], "Director", f[3], f[4]) for f in filings}

    def get(url: str, headers: dict[str, str]):
        calls.append(url)
        if url == fl.TICKER_MAP_URL:
            return 200, json.dumps({"0": {"cik_str": 320193, "ticker": "AAPL"}}).encode()
        if "submissions/CIK0000320193" in url:
            return 200, json.dumps(sub).encode()
        for name, body in docs.items():
            if url.endswith(name):
                return 200, body
        return 404, b""
    return get


@pytest.mark.parametrize("order", ["newest_first", "oldest_first"])
def test_the_frozen_store_equals_a_full_replay_whatever_the_fetch_order(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch, order: str) -> None:
    """EDGAR is read newest first, a few filings a pass. Nothing is frozen until the issuer's
    backfill completes, so the store is the full replay -- buyers and baselines both."""
    monkeypatch.setattr(fl, "us_issuers", lambda: {"Apple": "AAPL"})
    monkeypatch.setattr(fl, "DOCS_PER_ISSUER", 2)
    listing = list(reversed(ORDERED)) if order == "newest_first" else list(ORDERED)
    sd = tmp_path / "f4"
    now = datetime(2026, 7, 1, tzinfo=UTC)
    stores = []
    for k in range(6):
        rep = fl.run(get=_edgar_listing(listing, []), now=now + timedelta(hours=k),
                     state_dir=sd, series_root=tmp_path / "s", dry_run=True)
        stores.append((rep["backfill"]["complete"],
                       (sd / "clusters.jsonl").read_text("utf-8")
                       if (sd / "clusters.jsonl").exists() else ""))
        if rep["backfill"]["complete"]:
            break
    assert stores[-1][0] is True and len(stores) > 1
    assert all(text == "" for done, text in stores if not done), "nothing frozen mid-backfill"
    rows = fl._jsonl(sd / "transactions.jsonl")
    assert len(rows) == len(ORDERED)
    replay = fl.freeze_clusters(rows, [])
    stored = fl._jsonl(sd / "clusters.jsonl")
    assert stored == json.loads(json.dumps(replay)) and len(stored) == 3


def test_a_first_pass_with_every_submissions_request_failing_is_failed(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(fl, "us_issuers", lambda: {"Apple": "AAPL"})
    rep = fl.run(get=_refusing([], 503, "submissions"), now=NOW, state_dir=tmp_path / "f4",
                 series_root=tmp_path / "s", dry_run=True)
    assert rep["fetch"]["ok_responses"] == 1                  # the ticker map answered
    assert rep["fetch"]["status"] == "FAILED" and rep["status"] == fl.UNMEASURED


# ------------------------------------------------------------------------------- audit 0b66b08de

BASELINE = [  # backfilled first: the issuer's earlier buying, which sets its baseline
    ("0003-26-000001", "2026-05-02T17:00:00.000Z", "Ann A", "P", "2026-05-01"),
    ("0003-26-000002", "2026-05-04T17:00:00.000Z", "Ben B", "P", "2026-05-03"),
]
BURST = [  # then a burst larger than DOCS_PER_ISSUER, after the backfill completed
    ("0003-26-000003", "2026-06-02T17:00:00.000Z", "Cat C", "P", "2026-06-01"),
    ("0003-26-000004", "2026-06-03T17:00:00.000Z", "Dan D", "P", "2026-06-02"),
    ("0003-26-000005", "2026-06-04T17:00:00.000Z", "Eve E", "P", "2026-06-03"),
    ("0003-26-000006", "2026-06-05T17:00:00.000Z", "Fay F", "P", "2026-06-04"),
    ("0003-26-000007", "2026-06-06T17:00:00.000Z", "Gus G", "P", "2026-06-05"),
]


def _burst_store(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, per_pass: int
                 ) -> tuple[list[dict], list[list[dict]]]:
    """Backfill BASELINE, then read BURST `per_pass` filings a pass (newest first) until done.
    Returns the final store and the store after every burst pass."""
    monkeypatch.setattr(fl, "us_issuers", lambda: {"Apple": "AAPL"})
    sd = tmp_path / f"f4_{per_pass}"
    now = datetime(2026, 7, 1, tzinfo=UTC)
    monkeypatch.setattr(fl, "DOCS_PER_ISSUER", 100)
    rep = fl.run(get=_edgar_listing(BASELINE, []), now=now, state_dir=sd,
                 series_root=tmp_path / "s", dry_run=True)
    assert rep["backfill"]["complete"] is True
    monkeypatch.setattr(fl, "DOCS_PER_ISSUER", per_pass)
    snaps: list[list[dict]] = []
    for k in range(1, 10):
        fl.run(get=_edgar_listing(BASELINE + BURST, []), now=now + timedelta(hours=k),
               state_dir=sd, series_root=tmp_path / "s", dry_run=True)
        snaps.append(fl._jsonl(sd / "clusters.jsonl"))
        if not (fl._read_json(sd / "state.json", {}).get("unread_floor") or {}):
            break
    return fl._jsonl(sd / "clusters.jsonl"), snaps


def test_a_post_backfill_burst_freezes_the_same_store_whatever_the_fetch_order(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """The auditor's probe (residual MF2): a burst larger than DOCS_PER_ISSUER after the backfill,
    read newest first, froze the NEWER cluster without its older filings -- a different buyer
    set, score and rarity from the full replay. Freezing now stops at the acceptance time of the
    oldest filing still unread, so the store, every score and every rarity are identical to a
    store that read the whole burst in one pass, and to a full replay."""
    piecewise, snaps = _burst_store(tmp_path, monkeypatch, per_pass=2)
    whole, _ = _burst_store(tmp_path, monkeypatch, per_pass=100)
    assert len(snaps) >= 3                       # the burst really took several passes
    assert piecewise == whole
    rows = fl._jsonl(tmp_path / "f4_2" / "transactions.jsonl")
    assert piecewise == json.loads(json.dumps(fl.freeze_clusters(rows, [])))
    key = [(c["knowable_at"], c["buyers"], c["score"], c["components"]["rarity"])
           for c in piecewise]
    assert key == [(c["knowable_at"], c["buyers"], c["score"], c["components"]["rarity"])
                   for c in whole]
    assert len(piecewise) >= 2
    # and every intermediate store is a prefix of the final one: nothing frozen early and wrong
    assert all(snap == whole[:len(snap)] for snap in snaps)


def _edgar_with_robots(calls: list[str], robots: dict[str, tuple[int, bytes]]):
    """The fake EDGAR, with each host's robots.txt answering as `robots` says (default 404)."""
    inner = _edgar([])

    def get(url: str, headers: dict[str, str]):
        calls.append(url)
        if url.endswith("/robots.txt"):
            host = url.split("/")[2]
            return robots.get(host, (404, b""))
        return inner(url, headers)
    return get


def test_robots_is_read_per_host_before_the_first_request_to_it(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(fl, "us_issuers", lambda: {"Apple": "AAPL"})
    calls: list[str] = []
    rep = fl.run(get=_edgar_with_robots(calls, {}), now=NOW, state_dir=tmp_path / "f4",
                 series_root=tmp_path / "s", dry_run=True)
    robots = [u for u in calls if u.endswith("/robots.txt")]
    assert robots == ["https://www.sec.gov/robots.txt", "https://data.sec.gov/robots.txt"]
    assert calls[0] == "https://www.sec.gov/robots.txt"          # before any request to it
    assert rep["fetch"]["status"] == "FETCHED"
    assert rep["fetch"]["robots"] == {"www.sec.gov": "ABSENT", "data.sec.gov": "ABSENT"}


def test_a_robots_disallow_for_our_agent_is_not_fetched_and_robots_is_reread_daily(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """ROBOTS (principal's scope rule 2026-10-13): the group naming the desk's product bars the
    submissions path -- the '*' group allows it -- so it is never requested. A Disallow is not a
    person hold: robots.txt is kept a day (no re-read inside 24h) and re-read after, which is how
    a change of mind is picked up. The SEC UA is never written."""
    monkeypatch.setattr(fl, "us_issuers", lambda: {"Apple": "AAPL"})
    monkeypatch.setenv(fl.UA_ENV, "TestDesk research test@example.org")
    reg = tmp_path / "blocked.json"
    _seed_register(reg)
    robots = {"data.sec.gov": (200, f"User-agent: *\nAllow: /\n\nUser-agent: "
                                    f"{fl._hs.DESK_UA_PRODUCT}\nDisallow: /submissions/\n"
                               .encode())}
    calls: list[str] = []
    sd = tmp_path / "f4"
    rep = fl.run(get=_edgar_with_robots(calls, robots), now=NOW, state_dir=sd,
                 series_root=tmp_path / "s", dry_run=True, register=reg)
    assert not any("submissions/CIK" in u for u in calls)
    assert rep["fetch"]["status"] == "ROBOTS_DISALLOWED"
    assert rep["fetch"]["robots"]["data.sec.gov"] == "DISALLOWED"
    doc = json.loads(reg.read_text())
    assert doc["sources"][fl.REGISTER_KEY]["diagnosis"] == "ROBOTS_DISALLOW"
    assert not doc.get("holds")                                  # not a person hold
    state_text = (sd / "state.json").read_text("utf-8")
    assert "test@example.org" not in json.dumps(rep, default=str) + state_text
    calls.clear()
    fl.run(get=_edgar_with_robots(calls, robots), now=NOW + timedelta(hours=23),
           state_dir=sd, series_root=tmp_path / "s", dry_run=True, register=reg)
    assert calls == []                                           # robots kept a day
    robots["data.sec.gov"] = (200, b"User-agent: *\nAllow: /\n")   # the site changes its mind
    fl.run(get=_edgar_with_robots(calls, robots), now=NOW + timedelta(hours=25),
           state_dir=sd, series_root=tmp_path / "s", dry_run=True, register=reg)
    assert calls[0] == "https://data.sec.gov/robots.txt"
    assert any("submissions/CIK" in u for u in calls)


def test_the_sent_uas_own_group_is_honoured_too(tmp_path: Path,
                                                monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(fl, "us_issuers", lambda: {"Apple": "AAPL"})
    monkeypatch.setenv(fl.UA_ENV, "TestDesk research test@example.org")
    robots = {"data.sec.gov": (200, b"User-agent: testdesk\nDisallow: /submissions/\n")}
    calls: list[str] = []
    fl.run(get=_edgar_with_robots(calls, robots), now=NOW, state_dir=tmp_path / "f4",
           series_root=tmp_path / "s", dry_run=True, register=tmp_path / "r.json")
    assert not any("submissions/CIK" in u for u in calls)


@pytest.mark.parametrize(("status", "state", "fetched"), [
    (503, "UNAVAILABLE", False), (404, "ABSENT", True)])
def test_a_5xx_robots_stops_the_pass_and_a_404_robots_allows(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch, status: int, state: str,
        fetched: bool) -> None:
    monkeypatch.setattr(fl, "us_issuers", lambda: {"Apple": "AAPL"})
    calls: list[str] = []
    sd = tmp_path / "f4"
    rep = fl.run(get=_edgar_with_robots(calls, {"www.sec.gov": (status, b"")}), now=NOW,
                 state_dir=sd, series_root=tmp_path / "s", dry_run=True,
                 register=tmp_path / "r.json")
    assert (fl.TICKER_MAP_URL in calls) is fetched
    assert rep["fetch"]["robots"]["www.sec.gov"] == state
    if not fetched:
        assert rep["fetch"]["status"] == "ROBOTS_UNAVAILABLE"
        assert not (tmp_path / "r.json").exists()                # no hold for a 5xx
        calls.clear()
        fl.run(get=_edgar_with_robots(calls, {}), now=NOW + timedelta(minutes=5),
               state_dir=sd, series_root=tmp_path / "s", dry_run=True,
               register=tmp_path / "r.json")
        assert calls[0] == "https://www.sec.gov/robots.txt"      # re-read on the next pass
        assert fl.TICKER_MAP_URL in calls


def test_a_403_on_robots_itself_is_a_person_hold(tmp_path: Path,
                                                 monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(fl, "us_issuers", lambda: {"Apple": "AAPL"})
    calls: list[str] = []
    reg = tmp_path / "r.json"
    rep = fl.run(get=_edgar_with_robots(calls, {"www.sec.gov": (403, b"")}), now=NOW,
                 state_dir=tmp_path / "f4", series_root=tmp_path / "s", dry_run=True,
                 register=reg)
    assert calls == ["https://www.sec.gov/robots.txt"]
    assert rep["fetch"]["status"] == "METHOD_BLOCKED"
    blk = rep["fetch"]["block"]
    assert (blk["verdict"], blk["key"], blk["url"]) == (
        "ROBOTS_HOLD", "site:www.sec.gov", "https://www.sec.gov/robots.txt")
    calls.clear()
    fl.run(get=_edgar_with_robots(calls, {}), now=NOW + timedelta(days=11),
           state_dir=tmp_path / "f4", series_root=tmp_path / "s", dry_run=True, register=reg)
    assert calls == []


def test_a_waf_challenge_page_is_a_hold(tmp_path: Path,
                                        monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(fl, "us_issuers", lambda: {"Apple": "AAPL"})
    inner = _edgar([])

    def get(url: str, headers: dict[str, str]):
        if "submissions" in url:
            return 200, b"<html><script src='/cdn-cgi/challenge-platform/x.js'></script></html>"
        return inner(url, headers)
    rep = fl.run(get=get, now=NOW, state_dir=tmp_path / "f4", series_root=tmp_path / "s",
                 dry_run=True, register=tmp_path / "r.json")
    assert rep["fetch"]["block"]["verdict"] == "WAF_CHALLENGE"
    assert rep["fetch"]["status"] == "CHALLENGED"


def test_the_real_getter_returns_every_header_and_the_error_body(monkeypatch) -> None:
    """Retry-After and a WAF challenge travel with a refusal (audit b323f23a9 SF): the getter
    hands back the response's headers and error body, not a filtered subset."""
    import email.message
    import io
    import urllib.error

    msg = email.message.Message()
    msg["Retry-After"] = "120"
    msg["cf-mitigated"] = "challenge"

    def boom(req, timeout=None):
        raise urllib.error.HTTPError(req.full_url, 403, "Forbidden", msg,
                                     io.BytesIO(b"<title>Just a moment...</title>"))

    monkeypatch.setattr(fl.urllib.request, "urlopen", boom)
    monkeypatch.setattr(fl, "SPACING_S", 0.0)
    status, body, headers = fl._call(fl.urllib_getter("desk research contact@example.com"),
                                     "https://www.sec.gov/x")
    assert status == 403
    assert headers.get("retry-after") == "120"
    assert headers.get("cf-mitigated") == "challenge"
    assert b"Just a moment" in body
