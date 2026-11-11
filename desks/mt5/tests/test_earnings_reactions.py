"""Earnings reactions: 8-K item 2.02 acceptance times joined to share-CFD reactions (event lane).

All offline: a faked `polite_fetch.get`, synthetic broker-stamped bars, a tmp desk.
"""
from __future__ import annotations

import json
import sys
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any

import pandas as pd
import pytest

DESK = Path(__file__).resolve().parent.parent
for _p in (str(DESK), str(DESK.parent.parent)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from research import earnings_reactions as er  # noqa: E402

NOW = datetime(2024, 2, 5, 12, 0, tzinfo=UTC)
FILING_DAY = date(2024, 1, 10)                     # Wed; 16:30 ET is post-market
AAPL_CIK, GOOG_CIK = 320193, 1652044


# ------------------------------------------------------------------------------ synthetic bars
def _weekdays(start: date, end: date) -> list[date]:
    out, d = [], start
    while d <= end:
        if d.weekday() < 5:
            out.append(d)
        d += timedelta(days=1)
    return out


def _broker(d: date, hour: int) -> pd.Timestamp:
    """The stamp MetaTrader writes: New York wall time + 7 h, labelled UTC."""
    return pd.Timestamp(datetime(d.year, d.month, d.day, hour, tzinfo=UTC)) + pd.Timedelta(hours=7)


def _equity_frame() -> pd.DataFrame:
    rows, idx = [], []
    for d in _weekdays(date(2024, 1, 2), date(2024, 1, 31)):
        for h in range(9, 16):                       # bars opening 09:00 .. 15:00 ET
            if d <= FILING_DAY:
                o = c = 100.0
            elif d == date(2024, 1, 11):
                o = 105.0 if h == 9 else 108.0
                c = 106.0 if h == 9 else 108.0
            elif d < date(2024, 1, 17):
                o = c = 110.0
            else:
                o = c = 120.0
            vol = 30 if d == date(2024, 1, 11) else 10
            idx.append(_broker(d, h))
            rows.append({"open": o, "high": max(o, c), "low": min(o, c), "close": c,
                         "tick_volume": vol, "spread": 1, "real_volume": 0})
    return pd.DataFrame(rows, index=pd.DatetimeIndex(idx, name="time"))


def _bench_frame() -> pd.DataFrame:
    rows, idx = [], []
    for d in _weekdays(date(2024, 1, 2), date(2024, 1, 31)):
        for h in range(24):
            if d <= FILING_DAY:
                c = 1000.0
            elif d < date(2024, 1, 17):
                c = 1010.0
            else:
                c = 1020.0
            idx.append(_broker(d, h))
            rows.append({"open": c, "high": c, "low": c, "close": c, "tick_volume": 5})
    return pd.DataFrame(rows, index=pd.DatetimeIndex(idx, name="time"))


EQ, BENCH = _equity_frame(), _bench_frame()


def _loader(missing: tuple[str, ...] = ()) -> Any:
    def load(sym: str, tf: str) -> pd.DataFrame | None:
        if tf != "H1" or sym in missing:
            return None
        if sym == "US500":
            return BENCH
        if sym in ("Apple", "Alphabet-A", "Alphabet-C"):
            return EQ
        return None
    return load


# ------------------------------------------------------------------------------ fake SEC
def _submissions(accessions: list[tuple[str, str, str, str]]) -> dict[str, Any]:
    """[(accession, form, items, acceptanceDateTime)] -> the submissions API's parallel arrays."""
    return {"name": "X", "filings": {"recent": {
        "accessionNumber": [a for a, _, _, _ in accessions],
        "form": [f for _, f, _, _ in accessions],
        "items": [i for _, _, i, _ in accessions],
        "acceptanceDateTime": [t for _, _, _, t in accessions],
        "filingDate": [t[:10] for _, _, _, t in accessions]}}}


SEC_TICKERS = {"0": {"cik_str": AAPL_CIK, "ticker": "AAPL", "title": "Apple Inc."},
               "1": {"cik_str": GOOG_CIK, "ticker": "GOOGL", "title": "Alphabet Inc."},
               "2": {"cik_str": GOOG_CIK, "ticker": "GOOG", "title": "Alphabet Inc."}}
SUBS = {
    AAPL_CIK: _submissions([
        ("0000320193-24-000001", "8-K", "2.02,9.01", "2024-01-10T16:30:00.000Z"),
        ("0000320193-24-000002", "8-K", "5.02", "2024-01-12T08:00:00.000Z"),
        ("0000320193-24-000003", "10-Q", "", "2024-01-12T08:00:00.000Z")]),
    GOOG_CIK: _submissions([
        ("0001652044-24-000001", "8-K", "2.02", "2024-01-10T07:00:00.000Z")]),
}


class FakeResp:
    def __init__(self, status: int, body: Any = None) -> None:
        self.status = status
        self.text = json.dumps(body) if body is not None else ""
        self.error = "" if 200 <= status < 400 else f"HTTP {status}"

    @property
    def ok(self) -> bool:
        return 200 <= self.status < 400


class FakeGet:
    def __init__(self, refuse: dict[str, int] | None = None) -> None:
        self.calls: list[dict[str, Any]] = []
        self.refuse = refuse or {}

    def __call__(self, url: str, **kw: Any) -> FakeResp:
        self.calls.append({"url": url, **kw})
        for frag, status in self.refuse.items():
            if frag in url:
                return FakeResp(status)
        if url == er.TICKERS_URL:
            return FakeResp(200, SEC_TICKERS)
        for cik, doc in SUBS.items():
            if f"CIK{cik:010d}" in url:
                return FakeResp(200, doc)
        return FakeResp(404)


UNIVERSE = {"Apple": {"asset_class": "Equities"}, "Alphabet-A": {"asset_class": "Equities"},
            "Alphabet-C": {"asset_class": "Equities"}, "NoTicker": {"asset_class": "Equities"},
            "EURUSD": {"asset_class": "Forex"}, "US500": {"asset_class": "Indices"}}
TABLE = {"Apple": "AAPL", "Alphabet-A": "GOOGL", "Alphabet-C": "GOOG"}


@pytest.fixture
def desk(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> er.Paths:
    (tmp_path / "data" / "universe").mkdir(parents=True)
    (tmp_path / "data" / "universe" / "universe.json").write_text(json.dumps(UNIVERSE))
    monkeypatch.setattr(er, "machine_use", lambda url: (True, "test"))
    monkeypatch.delenv(er.UA_ENV, raising=False)
    return er.Paths(desk=tmp_path)


def _run(paths: er.Paths, get: FakeGet, now: datetime = NOW, **kw: Any) -> dict[str, Any]:
    return er.run(budget_s=60, paths=paths, getter=get, loader=kw.pop("loader", _loader()),
                  is_equity=lambda s: UNIVERSE[s]["asset_class"] == "Equities",
                  ticker_table=TABLE, now=now, sleep=lambda s: None, **kw)


# ------------------------------------------------------------------------------ tests
def test_only_8k_rows_carrying_item_2_02_are_kept() -> None:
    doc = _submissions([("a1", "8-K", "2.02,9.01", "2024-01-10T16:30:00.000Z"),
                        ("a2", "8-K", "5.02,9.01", "2024-01-10T16:30:00.000Z"),
                        ("a3", "8-K", "12.02", "2024-01-10T16:30:00.000Z"),
                        ("a4", "10-Q", "2.02", "2024-01-10T16:30:00.000Z"),
                        ("a5", "8-K/A", "2.02", "2024-01-10T16:30:00.000Z")])
    got = er.parse_submissions(doc)
    assert [r["accession"] for r in got] == ["a1", "a5"]
    assert got[0]["acceptance_raw"] == "2024-01-10T16:30:00.000Z"


def test_acceptance_is_read_as_eastern_and_converted_to_utc() -> None:
    # summer (EDT, UTC-4): the trailing Z is NOT an offset
    assert er.acceptance_to_utc("2024-08-01T16:30:42.000Z") == \
        datetime(2024, 8, 1, 20, 30, 42, tzinfo=UTC)
    # winter (EST, UTC-5)
    assert er.acceptance_to_utc("2024-01-25T16:30:00.000Z") == \
        datetime(2024, 1, 25, 21, 30, tzinfo=UTC)
    assert er.acceptance_to_utc("20240801163042") == datetime(2024, 8, 1, 20, 30, 42, tzinfo=UTC)
    assert er.acceptance_to_utc("") is None and er.acceptance_to_utc("garbage") is None


def test_session_bucket_uses_the_eastern_session() -> None:
    def at(h: int, m: int) -> datetime:
        return er.acceptance_to_utc(f"2024-01-10T{h:02d}:{m:02d}:00.000Z") or NOW
    assert er.session_bucket(at(7, 0)) == er.PRE
    assert er.session_bucket(at(9, 29)) == er.PRE
    assert er.session_bucket(at(9, 30)) == er.INTRA
    assert er.session_bucket(at(15, 59)) == er.INTRA
    assert er.session_bucket(at(16, 0)) == er.POST
    assert er.session_bucket(at(20, 5)) == er.POST


def test_reaction_maths_on_a_post_market_filing() -> None:
    acc = er.acceptance_to_utc("2024-01-10T16:30:00.000Z")
    assert acc is not None
    rx = er.reaction(acc, er.to_chart(EQ, "H1"), er.to_chart(BENCH, "H1"))
    assert rx["unmeasured"] == {}
    assert rx["pre_close"] == 100.0
    assert rx["next_open_date"] == "2024-01-11" and rx["day0"] == "2024-01-11"
    approx = pytest.approx
    assert rx["gap"] == approx(0.05)
    assert rx["ret_open"] == approx(0.06)
    assert rx["ret_1h"] == approx(0.08)            # the bar holding 10:30 ET
    assert rx["ret_1d"] == approx(0.08)
    assert rx["ret_5d"] == approx(0.20)            # Jan 11, 12, 15, 16, 17
    assert rx["abn_gap"] == approx(0.04)
    assert rx["abn_ret_open"] == approx(0.05)
    assert rx["abn_ret_1d"] == approx(0.07)
    assert rx["abn_ret_5d"] == approx(0.18)
    assert rx["volume_ratio"] == approx(3.0)


def test_pre_market_filing_reacts_the_same_day() -> None:
    acc = er.acceptance_to_utc("2024-01-11T07:00:00.000Z")
    assert acc is not None
    rx = er.reaction(acc, er.to_chart(EQ, "H1"), er.to_chart(BENCH, "H1"))
    assert rx["next_open_date"] == "2024-01-11" and rx["pre_close"] == 100.0
    assert rx["ret_open"] == pytest.approx(0.06)


def test_missing_bars_are_unmeasured_never_zero() -> None:
    acc = er.acceptance_to_utc("2024-01-10T16:30:00.000Z")
    assert acc is not None
    rx = er.reaction(acc, None, None)
    for k in (*er.WINDOWS, "pre_close", "volume_ratio"):
        assert rx[k] is None and rx["unmeasured"][k]
    # bars exist but the benchmark does not: own returns measured, abnormal unmeasured
    rx = er.reaction(acc, er.to_chart(EQ, "H1"), None)
    assert rx["ret_open"] == pytest.approx(0.06)
    assert rx["abn_ret_open"] is None and "US500" in rx["unmeasured"]["abn_ret_open"]
    # a filing before the bar history
    early = er.acceptance_to_utc("2023-06-01T16:30:00.000Z")
    assert early is not None
    rx = er.reaction(early, er.to_chart(EQ, "H1"), None)
    assert rx["ret_open"] is None and "predates" in rx["unmeasured"]["ret_open"]
    # a filing whose horizons are past the last bar: PENDING, so it is re-measured later
    late = er.acceptance_to_utc("2024-01-29T16:30:00.000Z")
    assert late is not None
    rx = er.reaction(late, er.to_chart(EQ, "H1"), er.to_chart(BENCH, "H1"))
    assert rx["ret_open"] is not None
    assert rx["ret_5d"] is None and rx["unmeasured"]["ret_5d"].startswith(er.PENDING)


def test_a_403_is_a_hard_stop_with_no_retry_and_a_cooldown(desk: er.Paths) -> None:
    get = FakeGet(refuse={f"CIK{AAPL_CIK:010d}": 403})
    c = _run(desk, get)
    assert all(call["retries"] == 0 for call in get.calls)
    urls = [call["url"] for call in get.calls]
    stop = urls.index(er.SUBMISSIONS_URL.format(cik=AAPL_CIK))
    assert stop == len(urls) - 1, "nothing is fetched after the refusal"
    assert c["refused"] and c["refused"][0]["status"] == 403
    state = json.loads(desk.state.read_text())
    assert state["cooldown_until"] > NOW.isoformat()
    # the next pass inside the cooldown touches no network
    get2 = FakeGet()
    c2 = _run(desk, get2, now=NOW + timedelta(hours=1))
    assert get2.calls == [] and not c2["network"]["used"]
    assert "cooling down" in c2["network"]["why_not"]


def test_the_user_agent_is_declared(desk: er.Paths, monkeypatch: pytest.MonkeyPatch) -> None:
    get = FakeGet()
    _run(desk, get)
    assert {c["headers"]["User-Agent"] for c in get.calls} == {er.FALLBACK_UA}
    monkeypatch.setenv(er.UA_ENV, "desk research ops@example.org")
    get2 = FakeGet()
    _run(desk, get2, now=NOW + timedelta(days=2))
    assert {c["headers"]["User-Agent"] for c in get2.calls} == {"desk research ops@example.org"}


def test_full_pass_dedupes_by_accession_and_is_incremental(desk: er.Paths) -> None:
    get = FakeGet()
    c = _run(desk, get)
    assert c["mapped"] == {"Alphabet-A": "GOOGL", "Alphabet-C": "GOOG", "Apple": "AAPL"}
    assert "NoTicker" in c["unmapped"] and "EURUSD" not in c["unmapped"]
    rows = er.read_rows(desk.rows)
    accs = [r["accession"] for r in rows]
    assert sorted(accs) == ["0000320193-24-000001", "0001652044-24-000001"]
    goog = next(r for r in rows if r["cik"] == GOOG_CIK)
    assert goog["symbol"] == "Alphabet-A" and goog["also_symbols"] == ["Alphabet-C"]
    assert goog["session_bucket"] == er.PRE
    aapl = next(r for r in rows if r["cik"] == AAPL_CIK)
    assert aapl["final"] and aapl["revision"] == 0 and aapl["ret_open"] == pytest.approx(0.06)
    # a second pass an hour later: caches are fresh (<20h), nothing re-fetched, nothing appended
    get2 = FakeGet()
    c2 = _run(desk, get2, now=NOW + timedelta(hours=1))
    assert [x["url"] for x in get2.calls] == []
    assert c2["rows_appended"] == 0 and len(er.read_rows(desk.rows)) == 2
    assert c2["join"].get("already_final") == 2


def test_a_pending_row_is_revised_by_appending(desk: er.Paths) -> None:
    short = EQ[EQ.index < _broker(date(2024, 1, 15), 0)]

    def early(sym: str, tf: str) -> pd.DataFrame | None:
        return None if tf != "H1" else (BENCH if sym == "US500" else short)
    _run(desk, FakeGet(), loader=early)
    first = {r["accession"]: r for r in er.read_rows(desk.rows)}
    assert not first["0000320193-24-000001"]["final"]
    _run(desk, FakeGet(), now=NOW + timedelta(hours=1))
    rows = [r for r in er.read_rows(desk.rows) if r["accession"] == "0000320193-24-000001"]
    assert [r["revision"] for r in rows] == [0, 1]
    assert rows[-1]["final"] and rows[-1]["ret_5d"] == pytest.approx(0.20)


def test_daily_breadth_aggregate() -> None:
    def row(acc: str, cik: int, us: str, nxt: str, bucket: str, abn: float | None) -> dict:
        return {"accession": acc, "cik": cik, "us_date": us, "next_open_date": nxt,
                "session_bucket": bucket, "abn_ret_open": abn, "abn_ret_1d": abn}
    latest = {r["accession"]: r for r in (
        row("a", 1, "2024-01-10", "2024-01-11", er.POST, 0.04),
        row("b", 2, "2024-01-10", "2024-01-11", er.POST, -0.02),
        row("c", 3, "2024-01-10", "2024-01-10", er.PRE, 0.01),
        row("d", 4, "2024-01-11", "2024-01-11", er.INTRA, None))}
    bd = er.breadth(latest, NOW)
    d = bd["days"]["2024-01-10"]
    assert d["filers"] == 3 and d["n_measured"] == 3
    assert d["share_positive_abnormal"] == pytest.approx(2 / 3)
    assert d["mean_abnormal"] == pytest.approx(0.01)
    assert d["median_abnormal"] == pytest.approx(0.01)
    assert d["by_session"] == {er.PRE: 1, er.INTRA: 0, er.POST: 2}
    d11 = bd["days"]["2024-01-11"]
    assert d11["n_measured"] == 0 and d11["share_positive_abnormal"] is None
    assert "unmeasured" in d11
    rx = bd["by_reaction_date"]["2024-01-11"]
    assert rx["filings"] == 3 and rx["n_measured"] == 2


def test_no_hypothesis_or_candidate_is_ever_emitted_for_an_equity(desk: er.Paths) -> None:
    before = {p for p in desk.desk.rglob("*") if p.is_file()}
    c = _run(desk, FakeGet())
    after = {p for p in desk.desk.rglob("*") if p.is_file()}
    written = {p.relative_to(desk.desk).as_posix() for p in after - before}
    assert written == {
        "data/earnings_reactions.jsonl", "data/earnings_breadth_daily.json",
        "reports/EARNINGS_REACTIONS.json", "data/edgar_cache/earnings/state.json",
        "data/edgar_cache/earnings/company_tickers.json",
        f"data/edgar_cache/earnings/CIK{AAPL_CIK:010d}.json",
        f"data/edgar_cache/earnings/CIK{GOOG_CIK:010d}.json"}
    assert c["mints_hypotheses"] is False
    for r in er.read_rows(desk.rows):
        assert r["lane"] == "event"
        assert not {"family", "kind", "hypothesis", "candidate", "trial"} & set(r)
    assert not any(w.startswith(("data/intelligence", "data/hypotheses")) for w in written)


def test_rotation_caps_and_resumes(desk: er.Paths) -> None:
    ciks = list(range(1, 11))
    due, cursor = er.due_ciks(desk, ciks, 0, NOW, cap=4)
    assert due == [1, 2, 3, 4] and cursor == 4
    due2, cursor2 = er.due_ciks(desk, ciks, cursor, NOW, cap=4)
    assert due2 == [5, 6, 7, 8] and cursor2 == 8
    due3, _ = er.due_ciks(desk, ciks, cursor2, NOW, cap=4)
    assert due3 == [9, 10, 1, 2]
