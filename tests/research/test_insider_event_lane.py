"""The insider / politician / buyback event lane: Form 4 clusters at acceptance, the congress
switch, the buyback blackout feature, the hard stop, and the family -- all offline.

Every input is a fixture: no network, no tracked file touched.
"""
from __future__ import annotations

import json
import sys
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any

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

from research import buyback_blackout as bb  # noqa: E402
from research import form4_lane as fl  # noqa: E402
from research import insider_event_lane as iel  # noqa: E402
from research import universe_policy as up  # noqa: E402

NOW = datetime(2026, 10, 14, 12, tzinfo=UTC)
UA = "quant-desk research test@example.invalid"
NAMES = {"Apple": "AAPL"}
OFF: dict[str, str] = {}


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
EARNINGS = ["2026-01-29T16:30:00.000Z", "2026-04-30T16:30:00.000Z", "2026-07-30T16:30:00.000Z"]


def _submissions() -> dict[str, Any]:
    n = len(FILINGS)
    return {"filings": {"recent": {
        "form": ["4"] * n + ["8-K"] * len(EARNINGS) + ["8-K", "10-Q"],
        "items": [""] * n + ["2.02,9.01"] * len(EARNINGS) + ["5.02", ""],
        "accessionNumber": [f[0] for f in FILINGS]
        + [f"0001-26-1000{i}" for i in range(len(EARNINGS))] + ["0001-26-200000",
                                                                 "0001-26-300000"],
        "acceptanceDateTime": [f[1] for f in FILINGS] + EARNINGS
        + ["2026-05-05T10:00:00.000Z", "2026-08-01T16:05:00.000Z"],
        "primaryDocument": [f"xslF345X05/doc{i}.xml" for i in range(n)]
        + ["e.htm"] * len(EARNINGS) + ["x.htm", "q.htm"],
    }}}


CONCEPT = {"units": {"USD": [
    {"start": "2024-10-01", "end": "2025-09-30", "val": 90e9, "accn": "0001-25-1",
     "form": "10-K", "filed": "2025-10-31"},
    {"start": "2024-10-01", "end": "2025-06-30", "val": 70e9, "accn": "0001-26-300000",
     "form": "10-Q", "filed": "2026-08-01"},
    {"start": "2025-10-01", "end": "2026-06-30", "val": 80e9, "accn": "0001-26-300000",
     "form": "10-Q", "filed": "2026-08-01"},
]}}


def _edgar(calls: list[str], *, robots: bytes = b"", refuse: tuple[int, str] | None = None):
    sub = _submissions()
    docs = {f"doc{i}.xml": _xml(f[2], f[3], f[4], f[5]) for i, f in enumerate(FILINGS)}

    def get(url: str, headers: dict[str, str]) -> tuple[int, bytes, dict[str, str]]:
        calls.append(url)
        if url.endswith("/robots.txt"):
            return (200, robots, {}) if robots else (404, b"", {})
        if refuse and refuse[1] in url:
            return refuse[0], b"", {"Retry-After": "120"}
        if url == fl.TICKER_MAP_URL:
            return 200, json.dumps({"fields": ["cik", "name", "ticker", "exchange"],
                                    "data": [[320193, "Apple Inc.", "AAPL", "Nasdaq"]]}
                                   ).encode(), {}
        if "submissions/CIK0000320193" in url:
            return 200, json.dumps(sub).encode(), {}
        if "companyconcept/CIK0000320193" in url:
            return 200, json.dumps(CONCEPT).encode(), {}
        for name, body in docs.items():
            if url.endswith(name):
                assert "xslF345X05" not in url       # the raw XML, never the rendered page
                return 200, body, {}
        return 404, b"", {}
    return get


def _run(tmp_path: Path, get, **kw: Any) -> dict[str, Any]:
    kw.setdefault("env", {fl.UA_ENV: UA})
    return iel.run(get=get, now=kw.pop("now", NOW), state_dir=tmp_path / "ev",
                   series_root=tmp_path / "series", report_path=tmp_path / "REPORT.json",
                   names=kw.pop("names", NAMES), dry_run=kw.pop("dry_run", True),
                   budget_s=kw.pop("budget_s", 60.0), **kw)


# ------------------------------------------------------------------------------- parsing

def test_acceptance_is_read_as_eastern_and_moved_late() -> None:
    assert fl.accepted_utc("2026-09-02T17:00:00.000Z") == datetime(2026, 9, 2, 22, tzinfo=UTC)
    assert fl.accepted_utc("garbage") is None


def test_parse_keeps_codes_and_roles() -> None:
    rows = fl.parse_form4(_xml("Cook Tim", "CEO", "P", "2026-09-01"))
    assert rows == [{"issuer_ticker": "AAPL", "insider": "Cook Tim", "title": "CEO",
                     "txn_date": "2026-09-01", "code": "P", "shares": 1000.0, "price": 50.0,
                     "acquired_disposed": "A", "shares_after": 9000.0}]
    assert fl.parse_form4(b"<not-xml") == []


def test_submissions_split_form4_earnings_and_periodic() -> None:
    sub = fl.submissions(json.dumps(_submissions()).encode())
    assert [f["accession"] for f in sub["form4"]] == ["0001-26-000003", "0001-26-000002",
                                                      "0001-26-000001"]
    # only item 2.02 8-Ks are earnings; the 5.02 8-K is not
    assert sub["earnings"] == [fl.accepted_utc(e).isoformat() for e in EARNINGS]
    assert sub["periodic"] == {"0001-26-300000": "2026-08-01T21:05:00+00:00"}


def test_only_broker_listed_equities_are_issuers(tmp_path: Path) -> None:
    uni = tmp_path / "universe.json"
    uni.write_text(json.dumps({"Apple": {"asset_class": "Equities"},
                               "Adobe": {"asset_class": "Indices"},
                               "US500": {"asset_class": "Indices"}}), encoding="utf-8")
    assert fl.issuers(uni) == {"Apple": "AAPL"}


# ------------------------------------------------------------------------------- the pass

def test_a_pass_fetches_clusters_at_acceptance_and_never_shows_the_ua(tmp_path: Path) -> None:
    calls: list[str] = []
    rep = _run(tmp_path, _edgar(calls))
    f4 = rep["form4"]
    assert rep["fetch"]["status"] == "FETCHED"
    assert f4["fetch"]["filings_read"] == 3 and f4["transactions"] == 3
    assert f4["clusters"] == 1                       # the grant (code A) is not a decision
    cl = fl.read_jsonl(tmp_path / "ev" / "clusters.jsonl")
    assert cl[0]["symbol"] == "Apple" and cl[0]["n_buyers"] == 2
    assert cl[0]["knowable_at"] == "2026-09-03T21:00:00+00:00"   # LATEST acceptance, late UTC
    calls.clear()
    rep2 = _run(tmp_path, _edgar(calls))
    assert rep2["form4"]["fetch"]["filings_read"] == 0 and rep2["form4"]["clusters_new"] == 0
    blob = json.dumps(rep) + json.dumps(rep2) + (tmp_path / "ev" / "state.json").read_text()
    assert "example.invalid" not in blob


def test_without_a_user_agent_nothing_is_fetched(tmp_path: Path) -> None:
    rep = iel.run(now=NOW, state_dir=tmp_path / "ev", series_root=tmp_path / "s",
                  names=NAMES, dry_run=True, env={})
    assert rep["fetch"]["status"] == "UNCONFIGURED" and rep["status"] == "UNMEASURED"
    rep = iel.run(now=NOW, state_dir=tmp_path / "ev", series_root=tmp_path / "s",
                  names=NAMES, dry_run=True, env={fl.UA_ENV: "nocontact"})
    assert rep["fetch"]["status"] == "UNCONFIGURED" and "nocontact" not in json.dumps(rep)


@pytest.mark.parametrize("status", [401, 403, 429])
def test_a_refusal_holds_until_a_person_releases_it(tmp_path: Path, status: int) -> None:
    calls: list[str] = []
    rep = _run(tmp_path, _edgar(calls, refuse=(status, "submissions")), dry_run=False)
    assert rep["fetch"]["status"] == "HELD"
    assert sum("submissions" in c for c in calls) == 1          # no retry around it
    state = json.loads((tmp_path / "ev" / "state.json").read_text())
    assert state["hold"]["status"] == status and state["hold"]["released_by"] is None
    calls.clear()
    rep = _run(tmp_path, _edgar(calls), dry_run=False, now=NOW + timedelta(days=30))
    assert rep["fetch"]["status"] == "HELD" and calls == []      # no timer releases it
    state["hold"]["released_by"] = "a person"
    (tmp_path / "ev" / "state.json").write_text(json.dumps(state))
    rep = _run(tmp_path, _edgar(calls), dry_run=False)
    assert rep["fetch"]["status"] == "FETCHED" and calls


def test_robots_disallow_is_respected(tmp_path: Path) -> None:
    calls: list[str] = []
    robots = b"User-agent: *\nDisallow: /Archives/\n"
    rep = _run(tmp_path, _edgar(calls, robots=robots))
    assert not any("/Archives/" in c for c in calls)
    assert rep["fetch"]["robots_disallowed"] >= 1 and rep["form4"]["transactions"] == 0


def test_a_later_filing_never_reshapes_a_frozen_cluster() -> None:
    def row(who: str, day: str, filed: str, acc: str) -> dict[str, Any]:
        return {"symbol": "Apple", "insider": who, "title": "Director", "txn_date": day,
                "filed_at": filed, "code": "P", "shares": 100, "price": 10.0, "accession": acc}
    probe = [row("A", "2026-05-04", "2026-05-05T22:00:00+00:00", "a"),
             row("B", "2026-05-05", "2026-05-06T22:00:00+00:00", "b"),
             row("C", "2026-05-06", "2026-05-20T22:00:00+00:00", "c")]
    early, _n, _c = fl.score(probe[:2])
    full, new, _c = fl.score(probe, early)
    assert new == [] and full == early
    assert [(c["knowable_at"], c["n_buyers"]) for c in early] == [
        ("2026-05-06T22:00:00+00:00", 2)]


def test_cells_wait_for_events_and_are_donated_once() -> None:
    clusters = [{"symbol": "Apple"}] * fl.MIN_EVENTS + [{"symbol": "Adobe"}]
    ev, accruing = fl.event_cells(clusters)
    assert [c["symbol"] for c in ev] == ["Apple"] and accruing == {"Adobe": 1}
    assert ev[0]["family"] == "insider_cluster_drift" and ev[0]["lane"] == "event"
    state: dict[str, Any] = {"donated": [iel._identity(ev[0])]}
    assert iel.donate_new(ev, state, dry_run=True) == {"new": 0, "already": 1}


# ------------------------------------------------------------------------------- congress

def _congress_series(root: Path) -> None:
    root.mkdir(parents=True, exist_ok=True)
    pd.DataFrame({"period_end": ["2026-09-01", "2026-09-02"],
                  "available_time": ["2026-09-01T12:00:00+00:00", "2026-09-03T06:00:00+00:00"],
                  "net_AAPL": [2, -1], "net_all": [5, 1]}).to_csv(root / "fs_congress_trades.csv",
                                                               index=False)


def test_congress_is_held_unless_the_principal_attests(tmp_path: Path,
                                                       monkeypatch: pytest.MonkeyPatch) -> None:
    _congress_series(tmp_path / "series")
    rep = _run(tmp_path, _edgar([]), env={fl.UA_ENV: UA})
    assert rep["congress"]["status"] == "AWAITING_PRINCIPAL"
    assert rep["congress"]["reading"] == "UNMEASURED"
    assert not (tmp_path / "ev" / iel.CONGRESS_EVENTS).exists()
    assert iel.congress_attested({iel.CONGRESS_ENV: "yes"})["on"] is False
    rep = _run(tmp_path, _edgar([]), env={fl.UA_ENV: UA, iel.CONGRESS_ENV: "1"})
    assert rep["congress"]["status"] == "READ" and rep["congress"]["events"] == 1
    ev = fl.read_jsonl(tmp_path / "ev" / iel.CONGRESS_EVENTS)
    # dated no earlier than the END of the disclosure day, and only the net BUY
    assert ev == [{"kind": "CONGRESS_NET_BUY", "symbol": "Apple",
                   "at": "2026-09-02T00:00:00+00:00", "knowable_at": "2026-09-02T00:00:00+00:00",
                   "score": 2.0, "disclosed": "2026-09-01", "source": "congress_trades"}]
    # the family refuses congressional events while the switch is off, whatever is on disk
    monkeypatch.delenv(iel.CONGRESS_ENV, raising=False)
    assert fic.event_times("Apple", source="congress",
                           path=tmp_path / "ev" / iel.CONGRESS_EVENTS) == []


# ------------------------------------------------------------------------------- buyback

def test_repurchase_facts_are_known_at_acceptance_or_late() -> None:
    periodic = {"0001-26-300000": "2026-08-01T21:05:00+00:00"}
    facts = bb.parse_concept(json.dumps(CONCEPT).encode(), periodic)
    assert facts[0]["known_at"] == "2025-11-01T00:00:00+00:00"     # not in the index: day after
    assert facts[2]["known_at"] == "2026-08-01T21:05:00+00:00"
    before = datetime(2026, 8, 1, 21, tzinfo=UTC)
    after = datetime(2026, 8, 2, tzinfo=UTC)
    assert bb.ttm_repurchase(facts, before) == 90e9                # only the 10-K was public
    assert bb.ttm_repurchase(facts, after) == pytest.approx(90e9 + 80e9 - 70e9)
    assert bb.ttm_repurchase(facts, datetime(2025, 1, 1, tzinfo=UTC)) is None


def test_the_blackout_window_uses_only_releases_public_by_that_day() -> None:
    e = [fl.accepted_utc(x).isoformat() for x in EARNINGS]
    # 2026-07-29: the 07-30 release is not yet public; next is PROJECTED from the 01-29 and
    # 04-30 releases (gap 91d -> 07-30) and the day is inside the 35-day pre-window
    w = bb.window_at(e, date(2026, 7, 29))
    assert w["in_blackout"] is True and w["last"].startswith("2026-04-30")
    assert bb.window_at(e, date(2026, 6, 1))["in_blackout"] is False
    assert bb.window_at(e, date(2026, 7, 31))["in_blackout"] is True     # within 48h after
    assert bb.window_at(e, date(2026, 8, 3))["in_blackout"] is False
    assert bb.window_at(e, date(2025, 12, 1)) is None


def test_the_next_release_is_projected_from_the_issuers_own_cadence() -> None:
    e = ["2026-01-01T21:00:00+00:00", "2026-03-02T21:00:00+00:00", "2026-05-01T21:00:00+00:00"]
    w = bb.window_at(e, date(2026, 6, 1))                # gaps 60d, 60d -> next 06-30
    assert w["next"].startswith("2026-06-30") and w["in_blackout"] is True
    assert bb.window_at(e, date(2026, 5, 20))["in_blackout"] is False


def test_the_pass_publishes_the_blackout_feature_and_no_index_cell(tmp_path: Path) -> None:
    rep = _run(tmp_path, _edgar([]))
    series = rep["buyback_blackout"]["series"]
    assert series["points"] > 0 and "FEATURE" in series["role"]
    df = pd.read_csv(tmp_path / "series" / f"{bb.SERIES}.csv")
    row = df.set_index("event_time").loc["2026-07-29"]
    assert row["share_NAS100"] == 1.0 and row["n_US30"] == 1 and row["wshare_US500"] == 1.0
    assert df.set_index("event_time").loc["2026-06-01"]["share_US500"] == 0.0
    assert (pd.to_datetime(df["available_time"]) > pd.to_datetime(df["event_time"], utc=True)
            ).all()
    assert all(c["symbol"] not in bb.INDICES for c in fl.event_cells(
        fl.read_jsonl(tmp_path / "ev" / "clusters.jsonl"))[0])
    assert "Apple" in json.loads((tmp_path / "ev" / "blackout_windows.json").read_text()
                                 )["windows"][0]["symbol"]


# ------------------------------------------------------------------------------- the family

def test_the_event_family_is_registered_in_the_news_lane() -> None:
    assert fo.ORTHOGONAL_FAMILIES["insider_cluster_drift"] is fic.family_insider_cluster_drift
    assert "insider_cluster_drift" in up.NEWS_LANE_FAMILIES
    from research.axis_registry import classify_family
    assert classify_family("insider_cluster_drift")[:2] == ("trend_persistence", "event")


def test_the_event_family_enters_the_first_bar_after_acceptance(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    at = datetime(2024, 3, 20, 21, 30, tzinfo=UTC)
    (tmp_path / "clusters.jsonl").write_text(json.dumps(
        {"symbol": "Apple", "knowable_at": at.isoformat(), "score": 2.0}) + "\n", "utf-8")
    monkeypatch.setenv("QUANT_INSIDER_EVENTS_DIR", str(tmp_path))
    import libs.research.bar_clock as bc
    monkeypatch.setattr(bc, "to_bar_time", lambda w, root=None, fallback=False:
                        (w + timedelta(hours=2), "OK", ""))
    t0 = datetime(2024, 3, 4, tzinfo=UTC)
    idx = pd.date_range(t0, t0 + timedelta(days=40), freq="1h", tz="UTC", inclusive="left")
    close = 100 * np.exp(np.cumsum(np.random.default_rng(3).normal(0, 0.002, len(idx))))
    df = pd.DataFrame({"open": close, "high": close * 1.002, "low": close * 0.998,
                       "close": close}, index=idx)
    sigs = fic.family_insider_cluster_drift(df, symbol="Apple")
    assert len(sigs) == 1 and sigs[0].side == 1
    assert sigs[0].time == pd.Timestamp(at + timedelta(hours=2)).ceil("1h")
    assert fic.family_insider_cluster_drift(df, symbol="Adobe") == []


# ------------------------------------------------------------------------------- the clock

def test_the_lane_rides_the_alpha_capture_leg_inside_its_budget(
        monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    import time as _t

    from research import alpha_capture as ac
    seen: list[float] = []

    def fake(**kw: Any) -> dict[str, Any]:
        seen.append(float(kw["budget_s"]))
        return {"status": "UNMEASURED", "fetch": {"status": "UNCONFIGURED"}}
    monkeypatch.setattr(iel, "run", fake)
    ac._event_lane(300.0, _t.monotonic())
    ac._event_lane(300.0, _t.monotonic() - 379.5)      # the leg used its budget and headroom
    assert seen[0] == iel.DEFAULT_BUDGET_S and seen[1] <= 1.0
    assert "event_lane UNMEASURED" in capsys.readouterr().out

    def boom(**_kw: Any) -> dict[str, Any]:
        raise RuntimeError("x")
    monkeypatch.setattr(iel, "run", boom)
    ac._event_lane(300.0, _t.monotonic())                # never takes the leg down
    assert "event_lane FAILED" in capsys.readouterr().out
