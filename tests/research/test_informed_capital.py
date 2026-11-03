"""Informed capital: parsers on recorded shapes, the observable clock, the aggregate and odds
transmissions, the family's entry rule, the cell screen, the fence and the issue-board wiring.

* every event is placed at its OBSERVABLE instant -- the SEC acceptance datetime (Eastern ->
  UTC), a date-only filing at the next UTC day 04:00 (+ a posting lag for Congress), or the
  venue's price stamp -- and never at the transaction date;
* only open-market P and S are signed; 10b5-1 plan trades, grants and amendments are not;
* a share CFD reaches the docket only through the news lane, and the main targets (indices,
  FX, gold) come from the aggregate and odds relations;
* the fence is RED on a point-in-time violation or a failing source and UNMEASURED when empty.
"""
from __future__ import annotations

import io
import json
import sys
import zipfile
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
from mt5desk import family_informed_flow as fif  # noqa: E402

from libs.research import analyst_views as av  # noqa: E402
from libs.research import informed_capital as ic  # noqa: E402
from research import informed_capital as organ  # noqa: E402
from research import issue_board  # noqa: E402
from research import orthogonal_sweep as osw  # noqa: E402
from research import universe_policy as up  # noqa: E402

FORM4_TXT = """<SEC-DOCUMENT>0000950170-26-001234.txt : 20260715
<SEC-HEADER>0000950170-26-001234.hdr.sgml : 20260715
<ACCEPTANCE-DATETIME>20260715163015
ACCESSION NUMBER:		0000950170-26-001234
CONFORMED SUBMISSION TYPE:	4
</SEC-HEADER>
<DOCUMENT>
<TYPE>4
<TEXT>
<XML>
<?xml version="1.0"?>
<ownershipDocument>
  <documentType>4</documentType>
  <issuer><issuerCik>0000320193</issuerCik><issuerName>Apple Inc.</issuerName>
    <issuerTradingSymbol>AAPL</issuerTradingSymbol></issuer>
  <reportingOwner>
    <reportingOwnerId><rptOwnerCik>0001234567</rptOwnerCik><rptOwnerName>Doe Jane</rptOwnerName>
    </reportingOwnerId>
    <reportingOwnerRelationship><isOfficer>1</isOfficer>
      <officerTitle>Chief Financial Officer</officerTitle></reportingOwnerRelationship>
  </reportingOwner>
  <nonDerivativeTable>
    <nonDerivativeTransaction>
      <transactionDate><value>2026-07-13</value></transactionDate>
      <transactionCoding><transactionCode>P</transactionCode></transactionCoding>
      <transactionAmounts><transactionShares><value>1000</value></transactionShares>
        <transactionPricePerShare><value>200.5</value></transactionPricePerShare>
      </transactionAmounts>
    </nonDerivativeTransaction>
    <nonDerivativeTransaction>
      <transactionDate><value>2026-07-13</value></transactionDate>
      <transactionCoding><transactionCode>S</transactionCode><aff10b5One>1</aff10b5One>
      </transactionCoding>
      <transactionAmounts><transactionShares><value>9000</value></transactionShares>
        <transactionPricePerShare><value>201</value></transactionPricePerShare>
      </transactionAmounts>
    </nonDerivativeTransaction>
    <nonDerivativeTransaction>
      <transactionDate><value>2026-07-14</value></transactionDate>
      <transactionCoding><transactionCode>A</transactionCode></transactionCoding>
      <transactionAmounts><transactionShares><value>5000</value></transactionShares>
      </transactionAmounts>
    </nonDerivativeTransaction>
  </nonDerivativeTable>
</ownershipDocument>
</XML>
</TEXT>
</DOCUMENT>
</SEC-DOCUMENT>
"""

_IDX = [("3", "NEW INSIDER CORP", "1111111", "edgar/data/1111111/0001111111-26-000001.txt"),
        ("4", "APPLE INC", "320193", "edgar/data/320193/0000950170-26-001234.txt"),
        ("4", "DOE JANE", "1234567", "edgar/data/320193/0000950170-26-001234.txt"),
        ("SC 13D", "TARGET CO", "777", "edgar/data/777/0000999999-26-000777.txt"),
        ("SC 13D", "ACTIVIST FUND LP", "888", "edgar/data/777/0000999999-26-000777.txt"),
        ("SC 13D/A", "TARGET CO", "777", "edgar/data/777/0000999999-26-000778.txt"),
        ("13F-HR", "BIG FUND LLC", "4444", "edgar/data/4444/0000004444-26-000010.txt")]
#: The fixed-width shape of EDGAR's daily form.idx (12 / 62 / 12 / 12 columns, then the path).
FORM_IDX = ("Description:           Daily Index of EDGAR Dissemination Feed by Form Type\n"
            "Form Type   Company Name" + " " * 50 + "CIK         Date Filed  File Name\n"
            + "-" * 140 + "\n"
            + "".join(f"{f:<12}{c:<62}{k:<12}{'20260715':<12}{fn}\n" for f, c, k, fn in _IDX))


def test_eastern_acceptance_converts_to_utc_in_both_seasons() -> None:
    assert ic.parse_acceptance("20260715163015") == datetime(2026, 7, 15, 20, 30, 15, tzinfo=UTC)
    assert ic.parse_acceptance("20260115163015") == datetime(2026, 1, 15, 21, 30, 15, tzinfo=UTC)
    assert ic.parse_acceptance("garbage") is None
    assert ic.utc_to_eastern_date(datetime(2026, 7, 16, 1, 0, tzinfo=UTC)) == date(2026, 7, 15)


def test_form_index_parses_and_queues_by_accession() -> None:
    rows = ic.parse_form_idx(FORM_IDX)
    forms = [r["form"] for r in rows]
    assert forms.count("4") == 2 and "SC 13D" in forms and "SC 13D/A" in forms
    r4 = next(r for r in rows if r["form"] == "4")
    assert r4["accession"] == "0000950170-26-001234" and r4["date"] == "2026-07-15"


def test_form4_signs_open_market_only_and_dates_at_acceptance() -> None:
    rows = ic.parse_ownership(FORM4_TXT, filed_date="2026-07-15", accession="0000950170-26-001234")
    assert len(rows) == 1
    r = rows[0]
    assert r["role"] == "cfo" and r["ticker"] == "AAPL" and r["owner"] == "1234567"
    # The 9,000-share sale was a 10b5-1 plan: set aside, never signed. The grant is not a trade.
    assert r["direction"] == 1 and r["planned_shares"] == 9000.0 and r["sell_shares"] == 0.0
    at, prec = ic.knowable_at(r)
    assert prec == "datetime" and at == datetime(2026, 7, 15, 20, 30, 15, tzinfo=UTC)
    assert r["txn_date"] == "2026-07-13"
    assert ic.oracle_at(r) < at                 # the oracle clock is earlier: that is the point


def test_amendments_and_doctype_payloads_are_refused() -> None:
    amended = FORM4_TXT.replace("<documentType>4</documentType>",
                                "<documentType>4/A</documentType>")
    assert ic.parse_ownership(amended) == []
    bomb = FORM4_TXT.replace("<?xml version=\"1.0\"?>", "<!DOCTYPE x [<!ENTITY a 'b'>]>")
    assert ic.parse_ownership(bomb.replace("<ownershipDocument>",
                                           "<ownershipDocument>&a;")) == []


def test_role_classes() -> None:
    assert ic.role_class(title="Chief Executive Officer") == "ceo"
    assert ic.role_class(title="EVP, Chief Operating Officer") == "coo"
    assert ic.role_class(title="Vice President, Sales", is_officer=True) == "officer"
    assert ic.role_class(is_director=True) == "director"
    assert ic.role_class(relationship="TenPercentOwner") == "10pct"
    assert ic.senior(["director", "cfo", "10pct"]) == "cfo"


def test_header_reads_both_spellings() -> None:
    txt = ("ACCEPTANCE-DATETIME:\t20260715090000\nCONFORMED SUBMISSION TYPE:\tSC 13D\n"
           "SUBJECT COMPANY:\n\tCOMPANY DATA:\n\t\tCENTRAL INDEX KEY:\t\t0000000777\n"
           "FILED BY:\n\tCOMPANY DATA:\n\t\tCENTRAL INDEX KEY:\t\t0000000888\n")
    h = ic.parse_header(txt)
    assert h["subject_cik"] == "777" and h["filer_cik"] == "888" and h["form"] == "SC 13D"
    assert h["accepted_at"] == "2026-07-15T13:00:00+00:00"
    sgml = ("<ACCEPTANCE-DATETIME>20260715090000\n<TYPE>SC 13D\n<SUBJECT-COMPANY>\n"
            "<COMPANY-DATA>\n<CIK>0000000777\n</COMPANY-DATA>\n<FILED-BY>\n<CIK>0000000888\n")
    h2 = ic.parse_header(sgml)
    assert h2["subject_cik"] == "777" and h2["filer_cik"] == "888"


def _ds_zip() -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("SUBMISSION.tsv", "ACCESSION_NUMBER\tFILING_DATE\tDOCUMENT_TYPE\tISSUERCIK\t"
                   "ISSUERTRADINGSYMBOL\tAFF10B5ONE\n"
                   "A-1\t02-JAN-2026\t4\t0000320193\tAAPL\t0\n"
                   "A-2\t02-JAN-2026\t4/A\t0000320193\tAAPL\t0\n"
                   "A-3\t05-JAN-2026\t4\t0000789019\tMSFT\t1\n")
        z.writestr("REPORTINGOWNER.tsv", "ACCESSION_NUMBER\tRPTOWNERCIK\tRPTOWNER_RELATIONSHIP"
                   "\tRPTOWNER_TITLE\nA-1\t0000000042\tDirector,Officer\tCEO\n")
        z.writestr("NONDERIV_TRANS.tsv", "ACCESSION_NUMBER\tTRANS_DATE\tTRANS_CODE\tTRANS_SHARES"
                   "\tTRANS_PRICEPERSHARE\nA-1\t30-DEC-2025\tS\t100\t10\n"
                   "A-2\t30-DEC-2025\tP\t100\t10\nA-3\t03-JAN-2026\tS\t50\t10\n")
    return buf.getvalue()


def test_dataset_backfill_is_date_precision_next_day_04z() -> None:
    rows, census = ic.parse_form345_dataset(_ds_zip())
    assert [r["accession"] for r in rows] == ["A-1"]
    assert census["amendment"] == 1 and census["planned_10b5_1"] == 1
    r = rows[0]
    assert r["role"] == "ceo" and r["direction"] == -1 and r["owner"] == "42"
    assert ic.knowable_at(r) == (datetime(2026, 1, 3, 4, 0, tzinfo=UTC), "date")


def test_live_acceptance_supersedes_the_dataset_row() -> None:
    ds = ic._filing_row(family="form345_ds", accession="X", owner="1", role="ceo", ticker="AAPL",
                        issuer_cik="", doc_type="4", direction=1, accepted_at=None,
                        filed_date="2026-01-02", txn_date="2026-01-01", value_usd=1.0)
    live = {**ds, "family": "form4", "accepted_at": "2026-01-02T15:00:00+00:00"}
    assert ic.latest_rows([live, ds]) == [live]
    assert ic.latest_rows([ds, live]) == [live]


def test_schedule_rows_name_the_quoted_subject_and_skip_amendments() -> None:
    rows = ic.schedule_rows(ic.parse_form_idx(FORM_IDX), {"777": "TGT"})
    assert len(rows) == 1
    r = rows[0]
    assert r["ticker"] == "TGT" and r["owner"] == "888" and r["family"] == "sc13d"


def test_13f_diff() -> None:
    cur = ic.parse_13f_table(
        '<informationTable xmlns="http://www.sec.gov/edgar/document/thirteenf/informationtable">'
        "<infoTable><nameOfIssuer>APPLE INC</nameOfIssuer><cusip>037833100</cusip>"
        "<shrsOrPrnAmt><sshPrnamt>1500</sshPrnamt><sshPrnamtType>SH</sshPrnamtType>"
        "</shrsOrPrnAmt></infoTable>"
        "<infoTable><nameOfIssuer>NEWCO</nameOfIssuer><cusip>111111111</cusip>"
        "<shrsOrPrnAmt><sshPrnamt>10</sshPrnamt><sshPrnamtType>SH</sshPrnamtType>"
        "</shrsOrPrnAmt></infoTable>"
        "<infoTable><nameOfIssuer>APPLE INC</nameOfIssuer><cusip>037833100</cusip>"
        "<shrsOrPrnAmt><sshPrnamt>99</sshPrnamt><sshPrnamtType>SH</sshPrnamtType></shrsOrPrnAmt>"
        "<putCall>Put</putCall></infoTable></informationTable>")
    assert cur["037833100"]["shares"] == 1500.0          # the put is not ownership
    old = {"037833100": {"name": "APPLE INC", "shares": 1000.0},
           "222222222": {"name": "GONE", "shares": 5.0}}
    d = {x["cusip"]: x["direction"] for x in ic.diff_13f(cur, old)}
    assert d == {"037833100": 1, "111111111": 1, "222222222": -1}
    assert ic.normalise_name("Apple Inc.") == ic.normalise_name("APPLE INC COM") == "apple"


HOUSE_TEXT = """ID Owner Asset Transaction Type Date Notification Date Amount
SP Apple Inc. - Common Stock (AAPL) [ST] P 06/02/2026 06/20/2026 $1,001 - $15,000
F S : New
JT NVIDIA Corporation (NVDA)
[ST] S (partial) 06/03/2026 06/20/2026 $15,001 - $50,000
Microsoft (MSFT) [ST] S 06/04/2026 06/20/2026 $1,001 - $15,000
Microsoft (MSFT) [ST] P 06/05/2026 06/20/2026 $1,001 - $15,000
"""


def test_house_ptr_text_nets_per_ticker() -> None:
    rows = ic.parse_house_ptr_text(HOUSE_TEXT, doc_id="20012345", filed_date="2026-06-25")
    got = {r["ticker"]: r["direction"] for r in rows}
    assert got == {"AAPL": 1, "NVDA": -1}               # MSFT nets to zero
    r = next(x for x in rows if x["ticker"] == "AAPL")
    # filed 06-25 -> next day + one posting-lag day, at 04:00 UTC
    assert ic.knowable_at(r)[0] == datetime(2026, 6, 27, 4, 0, tzinfo=UTC)
    assert r["txn_date"] == "2026-06-02"


def test_senate_parsers() -> None:
    html = ("<table><tr><th>#</th></tr><tr><td>1</td><td>10/15/2026</td><td>Self</td>"
            "<td><a href='x'>AAPL</a></td><td>Apple Inc</td><td>Stock</td><td>Purchase</td>"
            "<td>$1,001 - $15,000</td><td>--</td></tr>"
            "<tr><td>2</td><td>10/16/2026</td><td>Spouse</td><td>--</td><td>Muni bond</td>"
            "<td>Municipal Security</td><td>Sale (Full)</td><td>$1,001</td><td>--</td></tr>"
            "</table>")
    rows = ic.parse_senate_ptr_html(html, report_id="abc", filed_date="2026-10-20")
    assert [(r["ticker"], r["direction"]) for r in rows] == [("AAPL", 1)]
    rid = "1a2b3c4d-0000-1111-2222-333344445555"
    doc = {"data": [["A", "B", "Sen", f'<a href="/search/view/ptr/{rid}/">PTR</a>', "10/20/2026"],
                    ["A", "B", "Sen", '<a href="/search/view/paper/X/">paper</a>', "10/20/2026"]]}
    assert ic.parse_senate_search(doc) == [{"report_id": rid, "filed_date": "2026-10-20"}]


def test_odds_parsers_category_polarity_and_events() -> None:
    assert ic.odds_category("Will the Fed cut rates in December?") == "fed"
    assert ic.odds_polarity("Will the Fed cut rates in December?") == -1
    assert ic.odds_polarity("Fed funds rate above 4.25%?") == 1
    assert ic.odds_category("Who wins the Oscar?") is None
    candles = {"candlesticks": [
        {"end_period_ts": 1_780_000_000, "price": {"close": 40}},
        {"end_period_ts": 1_780_086_400, "price": {"close": 52}},
        {"end_period_ts": 1_780_172_800, "price": {"close_dollars": "0.53"}}]}
    pts = ic.parse_kalshi_candles(candles)
    assert [round(p, 2) for _, p in pts] == [0.4, 0.52, 0.53]
    ev = ic.odds_events("kalshi", "KXFED-26DEC-T4.25", "Fed funds rate above 4.25%", pts)
    assert len(ev) == 1 and ev[0]["direction"] == 1 and ev[0]["category"] == "fed"
    assert ev[0]["observed_at"] == pts[1][0].isoformat()
    gamma = [{"id": "9", "question": "Fed decreases rates by 25 bps?",
              "outcomes": '["Yes","No"]', "clobTokenIds": '["tok1","tok2"]'}]
    assert ic.parse_polymarket_markets(gamma)[0]["token"] == "tok1"
    hist = ic.parse_clob_history({"history": [{"t": 1_780_000_000, "p": 0.3}]})
    assert hist[0][1] == 0.3


def test_pit_violation_is_detected() -> None:
    bad = ic._filing_row(family="form4", accession="Z", owner="1", role="cfo", ticker="AAPL",
                         issuer_cik="", doc_type="4", direction=1,
                         accepted_at="2026-01-01T15:00:00+00:00", filed_date="",
                         txn_date="2026-01-05", value_usd=None)
    assert ic.pit_violations([bad])[0]["event_id"] == "Z|1"


def _day_rows(day: date, buys: int, sells: int) -> list[dict[str, Any]]:
    out = []
    for i in range(buys + sells):
        acc = f"{day.isoformat()}-{i}"
        out.append(ic._filing_row(
            family="form4", accession=acc, owner=str(i), role="director", ticker=f"T{i}",
            issuer_cik=str(i), doc_type="4", direction=1 if i < buys else -1,
            accepted_at=datetime(day.year, day.month, day.day, 14 + (i % 6),
                                 tzinfo=UTC).isoformat(),
            filed_date=day.isoformat(), txn_date=(day - timedelta(days=1)).isoformat(),
            value_usd=1.0))
    return out


def test_aggregate_breadth_fires_on_an_abnormal_day_at_its_last_acceptance() -> None:
    rows: list[dict[str, Any]] = []
    d0 = date(2026, 3, 2)
    rng = np.random.default_rng(1)
    for k in range(40):
        rows += _day_rows(d0 + timedelta(days=k), int(rng.integers(2, 4)), 7)
    spike = d0 + timedelta(days=40)
    rows += _day_rows(spike, 9, 1)
    ev = ic.aggregate_days(rows, prefix="form4_agg", group="all")
    assert ev and ev[-1][1] == 1 and ev[-1][2]["day"] == spike.isoformat()
    assert ev[-1][0] == datetime(spike.year, spike.month, spike.day, 19, tzinfo=UTC)
    obs, _ = ic.observations(rows, universe={"US500", "NAS100"})
    agg = [o for o in obs if o.relation == "aggregate"]
    assert {o.target for o in agg} == {"US500", "NAS100"}
    assert {o.source for o in agg} >= {"form4_agg:all", "form4_agg:director"}


def test_observations_map_direct_odds_and_the_oracle_clock() -> None:
    f4 = ic.parse_ownership(FORM4_TXT, filed_date="2026-07-15", accession="0000950170-26-001234")
    f4 = [{**r, "instrument": "Apple"} for r in f4]
    odds = ic.odds_events("polymarket", "9", "Will the Fed cut rates?",
                          [(datetime(2026, 7, 1, tzinfo=UTC), 0.2),
                           (datetime(2026, 7, 2, tzinfo=UTC), 0.4)])
    obs, _ = ic.observations([*f4, *odds], universe={"Apple", "EURUSD", "XAUUSD"})
    direct = [o for o in obs if o.relation == "direct"]
    assert [(o.target, o.source, o.direction) for o in direct] == [("Apple", "form4:cfo", 1)]
    assert direct[0].at == datetime(2026, 7, 15, 20, 30, 15, tzinfo=UTC)
    od = [o for o in obs if o.relation == "odds"]
    assert {o.target for o in od} == {"EURUSD", "XAUUSD"}
    assert all(o.direction == -1 and o.source == "polymarket:fed" for o in od)
    oracle, _ = ic.observations([*f4, *odds], universe={"Apple"}, clock="oracle")
    assert [o.at for o in oracle] == [datetime(2026, 7, 13, 21, tzinfo=UTC)]


# ------------------------------------------------------------------------------ the family
T0 = datetime(2026, 7, 1, tzinfo=UTC)


def _h1(days: int = 60) -> pd.DataFrame:
    idx = pd.date_range(T0, T0 + timedelta(days=days), freq="1h", tz="UTC", inclusive="left")
    rng = np.random.default_rng(3)
    close = 100 * np.exp(np.cumsum(rng.normal(0, 0.002, len(idx))))
    return pd.DataFrame({"open": close, "high": close * 1.002, "low": close * 0.998,
                         "close": close}, index=idx)


@pytest.fixture
def store(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    path = tmp_path / "events.jsonl"
    monkeypatch.setenv("QUANT_INFORMED_CAPITAL_STORE", str(path))
    monkeypatch.setattr(av, "bar_clock", lambda: av.identity_clock)
    fif._CACHE.clear()
    return path


def test_family_enters_on_the_first_bar_opening_after_acceptance(store: Path) -> None:
    rows = ic.parse_ownership(FORM4_TXT, filed_date="2026-07-15", accession="0000950170-26-001234")
    store.write_text("\n".join(json.dumps({**r, "instrument": "Apple"}) for r in rows) + "\n")
    sig = fo.ORTHOGONAL_FAMILIES["informed_flow_drift"](
        _h1(), symbol="Apple", source="form4:cfo", relation="direct", side=1)
    assert len(sig) == 1
    assert sig[0].time == pd.Timestamp("2026-07-15 21:00", tz="UTC")   # 20:30:15 -> next open
    assert sig[0].side == 1
    flipped = fif.family_informed_flow_drift(_h1(), symbol="Apple", source="form4:cfo",
                                             relation="direct", side=-1)
    assert flipped[0].side == -1
    assert fif.family_informed_flow_drift(_h1(), symbol="Apple", source="form4:cfo",
                                          relation="bogus") == []
    assert fif.family_informed_flow_drift(_h1(), symbol="Apple", source="form4:ceo",
                                          relation="direct") == []


def test_family_is_registered_unsuppliable_and_in_the_news_lane() -> None:
    fn = fo.ORTHOGONAL_FAMILIES["informed_flow_drift"]
    assert osw._unsuppliable(fn, {}) == "symbol, source, relation"
    assert "informed_flow_drift" in osw.NOT_SOURCED_HERE
    assert "informed_flow_drift" in fo.FAMILY_INPUTS
    assert "informed_flow_drift" in up.NEWS_LANE_FAMILIES
    if up.is_equity("Apple"):
        assert up.may_hypothesise("Apple", "informed_flow_drift")
        assert not up.may_hypothesise("Apple", "trend")


# ------------------------------------------------------------------------------ the organ
def test_cell_screen_needs_bonferroni_and_its_own_placebo() -> None:
    good = {"target": "US500", "source": "form4_agg:exec", "relation": "aggregate",
            "lead": "form4_agg:exec",
            "5d": {"status": "MEASURED", "t": 6.0, "n": 80, "mean_bp": 35.0, "sd_bp": 50.0,
                   "hit": 0.6}}
    weak = {**good, "target": "NAS100", "5d": {**good["5d"], "t": 2.1}}
    no_gate = {**good, "target": "US30"}
    gate = {"5d": {"US500|form4_agg:exec|aggregate|form4_agg:exec": {"status": "ADMIT"},
                   "US30|form4_agg:exec|aggregate|form4_agg:exec": {"status": "REJECT"}}}
    cands, trials, refused = organ.cell_rows([good, weak, no_gate], gate)
    assert trials == 3 and [c["symbol"] for c in cands] == ["US500"]
    c = cands[0]
    assert c["family"] == "informed_flow_drift" and c["params"]["side"] == 1
    assert c["params"]["relation"] == "aggregate" and c["params"]["hold_days"] == 5
    assert any("US30" in r["cell"] for r in refused)
    assert organ.cell_rows([good], None)[0] == []


class FakeHttp:
    def __init__(self, pages: dict[str, Any]) -> None:
        self.pages = pages
        self.calls: list[str] = []

    def _find(self, url: str) -> Any:
        self.calls.append(url)
        for k, v in self.pages.items():
            if k in url:
                return v
        return None

    def text(self, url: str, **_kw: Any) -> tuple[int | None, str, str]:
        v = self._find(url)
        return (200, v, "") if isinstance(v, str) else (404, "", "HTTP 404")

    def bytes(self, url: str, **_kw: Any) -> tuple[int | None, bytes, str]:
        v = self._find(url)
        return (200, v, "") if isinstance(v, bytes) else (404, b"", "HTTP 404")

    def post(self, url: str, data: Any, **_kw: Any) -> tuple[int | None, str, str]:
        return self.text(url)

    def cookie(self, _name: str) -> str:
        return ""


@pytest.fixture
def paths(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setattr(organ, "STATE", tmp_path / "state.json")
    monkeypatch.setattr(organ, "REPORT", tmp_path / "INFORMED_CAPITAL.json")
    monkeypatch.setattr(organ, "TICKERS_CACHE", tmp_path / "tickers.json")
    monkeypatch.setattr(organ, "_donate", lambda c, n: None)
    monkeypatch.setattr(av, "bar_clock", lambda: av.identity_clock)
    monkeypatch.setattr(organ, "MISSED_GROWTH", tmp_path / "missed_growth.jsonl")
    monkeypatch.delenv("QUANT_CONGRESS_ATTEST", raising=False)
    return tmp_path


def test_one_pass_collects_stores_and_reports(paths: Path,
                                              monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("QUANT_EDGAR_UA", "desk research ops@example.com")
    now = datetime(2026, 7, 17, 12, tzinfo=UTC)
    (paths / "state.json").write_text(json.dumps({"index_next": "2026-07-15",
                                                  "ds_done": [f"{y}q{q}" for y in (2024, 2025,
                                                                                   2026)
                                                              for q in (1, 2, 3, 4)]}))
    http = FakeHttp({
        "company_tickers.json": json.dumps({"0": {"cik_str": 320193, "ticker": "AAPL",
                                                  "title": "Apple Inc."},
                                            "1": {"cik_str": 777, "ticker": "TGT",
                                                  "title": "Target Co"}}),
        "form.20260715.idx": FORM_IDX,
        "0000950170-26-001234.txt": FORM4_TXT,
        "0000999999-26-000777.hdr.sgml": ("<ACCEPTANCE-DATETIME>20260715090000\n"
                                          "<SUBJECT-COMPANY>\n<CIK>0000000777\n<FILED-BY>\n"
                                          "<CIK>0000000888\n"),
        "/series?category=Economics": json.dumps({"series": [{"ticker": "KXFED",
                                                              "title": "Fed funds rate"}]}),
        "markets?series_ticker=KXFED": json.dumps({"markets": [
            {"ticker": "KXFED-T4.25", "title": "Fed funds rate above 4.25%"}]}),
        "candlesticks": json.dumps({"candlesticks": [
            {"end_period_ts": 1_783_000_000, "price": {"close": 30}},
            {"end_period_ts": 1_783_086_400, "price": {"close": 45}}]}),
    })
    store = paths / "events.jsonl"
    rep = organ.run(now=now, http=http, store=store, loader=lambda _s: None,
                    universe_doc={"Apple": {"asset_class": "Equities"}, "US500": {},
                                  "EURUSD": {}, "XAUUSD": {}},
                    only=["sec_form4", "sec_13d", "kalshi", "senate_ptr"], n_placebo=5)
    fams = rep["store"]["by_family"]
    assert fams.get("form4") == 1 and fams.get("sc13d") == 1 and fams.get("kalshi") == 1
    assert rep["sources"]["senate_ptr"]["status"] == "AWAITING_PRINCIPAL"
    assert rep["sources"]["sec_form4"]["status"] == "FETCHED"
    assert rep["sources"]["kalshi"]["terms"]["allowed"] is True
    written = json.loads((paths / "INFORMED_CAPITAL.json").read_text())
    assert written["fence"]["fence"] in ("GREEN", "UNMEASURED")
    assert written["fence"]["pit_violations"] == 0
    stored = organ.store_rows(store)
    sc = next(r for r in stored if r["family"] == "sc13d")
    assert sc["accepted_at"] == "2026-07-15T13:00:00+00:00" and sc["ticker"] == "TGT"
    f4 = next(r for r in stored if r["family"] == "form4")
    assert f4["instrument"] == "Apple" and f4["first_seen_at"] == now.isoformat()
    # A second identical pass adds nothing: the store is append-only and content-deduplicated.
    again = organ.append(stored, now=now, path=store)
    assert again["added"] == 0
    assert not any("efdsearch" in u for u in http.calls)        # the Senate was never touched
    census = written["odds_listing_census"]["kalshi"]["KXFED"]
    assert census["open"] == 1 and census["settled"] == 1 and census["page_capped"] is False
    assert any("status=settled" in u for u in http.calls)       # resolved contracts are read


def test_no_congressional_fetch_without_the_switch_and_the_gate_is_billed(
        paths: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    now = datetime(2026, 7, 17, 12, tzinfo=UTC)
    http = FakeHttp({"FD.zip": b"PK", "ptr-pdfs": b"%PDF", "efdsearch": "x"})
    rep = organ.run(now=now, http=http, store=paths / "events.jsonl", loader=lambda _s: None,
                    universe_doc={}, only=["house_ptr", "senate_ptr"], n_placebo=5)
    assert rep["sources"]["house_ptr"]["status"] == "AWAITING_PRINCIPAL"
    assert rep["sources"]["senate_ptr"]["status"] == "AWAITING_PRINCIPAL"
    assert http.calls == []                                     # not one congressional request
    lines = [json.loads(x) for x in (paths / "missed_growth.jsonl").read_text().splitlines()]
    assert {x["cell"] for x in lines} == {"house:member", "senate:member", "congress_agg:all"}
    assert all(x["rail"] == "congress_attestation_gate" and x["status"] == "UNMEASURED"
               for x in lines)
    organ.run(now=now, http=http, store=paths / "events.jsonl", loader=lambda _s: None,
              universe_doc={}, only=["house_ptr"], n_placebo=5)
    again = (paths / "missed_growth.jsonl").read_text().splitlines()
    assert len(again) == 3                                      # one bill per cell per day
    monkeypatch.setenv("QUANT_CONGRESS_ATTEST", "1")
    assert organ.congress_missed_growth(now, path=paths / "other.jsonl") == []
    _rows, house = organ.collect_house(http, {}, 1e18, now)
    assert house["status"] != "AWAITING_PRINCIPAL" and any("FD.zip" in u for u in http.calls)


def test_polymarket_reads_resolved_markets_and_publishes_a_census() -> None:
    gamma = json.dumps([{"id": "9", "question": "Fed decreases rates by 25 bps?",
                         "outcomes": '["Yes","No"]', "clobTokenIds": '["tok1","tok2"]'},
                        {"id": "10", "question": "Who wins the Oscar?",
                         "outcomes": '["Yes","No"]', "clobTokenIds": '["t3","t4"]'}])
    http = FakeHttp({"gamma-api": gamma,
                     "prices-history": json.dumps({"history": [{"t": 1_780_000_000, "p": 0.2},
                                                               {"t": 1_780_086_400, "p": 0.5}]})})
    _rows, rep = organ.collect_polymarket(http, {}, 1e18, datetime(2026, 7, 17, tzinfo=UTC))
    c = rep["listing_census"]
    assert c["active"]["listed"] == 2 and c["resolved"]["listed"] == 2
    assert c["resolved"]["by_category"] == {"fed": 1, "non_macro": 1}
    assert any("closed=true" in u for u in http.calls)


def test_sec_without_user_agent_is_unconfigured_not_zero(paths: Path,
                                                         monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("QUANT_EDGAR_UA", raising=False)
    monkeypatch.delenv("EDGAR_UA", raising=False)
    http = FakeHttp({})
    _rows, rep, _st = organ.collect(now=datetime(2026, 7, 17, tzinfo=UTC), budget_s=5,
                                    http=http, only=["sec_form4"])
    assert rep["sec_form4"]["status"] == "UNCONFIGURED" and http.calls == []


def test_fence_red_on_pit_violation_and_failures_unmeasured_when_empty() -> None:
    now = datetime(2026, 7, 17, tzinfo=UTC)
    assert organ.fence(rows=[], sources={}, state={}, now=now)["fence"] == "UNMEASURED"
    bad = {**ic._filing_row(family="form4", accession="Z", owner="1", role="cfo", ticker="AAPL",
                            issuer_cik="", doc_type="4", direction=1,
                            accepted_at="2026-01-01T15:00:00+00:00", filed_date="",
                            txn_date="2026-01-05", value_usd=None),
           "first_seen_at": now.isoformat()}
    f = organ.fence(rows=[bad], sources={"sec_form4": {"status": "FETCHED"}}, state={},
                    now=now)
    assert f["fence"] == "RED" and f["pit_violations"] == 1
    ok = {**bad, "txn_date": "2025-12-30"}
    f2 = organ.fence(rows=[ok], sources={"kalshi": {"status": "FAILED"}},
                     state={"failures": {"kalshi": 3}}, now=now)
    assert f2["fence"] == "RED" and "kalshi" in f2["red"][0]
    f3 = organ.fence(rows=[ok], sources={"kalshi": {"status": "FETCHED"}}, state={}, now=now)
    assert f3["fence"] == "GREEN"


def test_check_exits_red_on_missing_or_stale(tmp_path: Path) -> None:
    now = datetime(2026, 7, 17, tzinfo=UTC)
    assert organ.check(tmp_path / "nope.json", now=now)[0] == 1
    p = tmp_path / "r.json"
    p.write_text(json.dumps({"at": now.isoformat(), "fence": {"fence": "GREEN"}}))
    assert organ.check(p, now=now) == (0, "GREEN")
    p.write_text(json.dumps({"at": (now - timedelta(hours=5)).isoformat(),
                             "fence": {"fence": "GREEN"}}))
    assert organ.check(p, now=now)[0] == 1


def test_issue_board_reads_the_fence(tmp_path: Path) -> None:
    rep = tmp_path / issue_board.INFORMED_CAPITAL
    rep.parent.mkdir(parents=True)
    rep.write_text(json.dumps({"fence": {"fence": "RED", "red": ["kalshi has FAILED 3"]}}))
    issues = issue_board.informed_capital_issues(tmp_path)
    assert [i.key for i in issues] == ["informed_capital:red"]
    assert any(name == "informed_capital" for name, *_ in issue_board.CADENCE)


def test_hourly_leg_and_layer_are_wired() -> None:
    src = (DESK / "research" / "hourly_cycle.py").read_text(encoding="utf-8")
    assert '"research/informed_capital.py", "--once"' in src
    assert '"informed_capital": icap' in src
    from libs.research import layers
    assert "informed_capital" in layers.__dict__.get("LEG_LAYER", {}) or \
        '"informed_capital": "information"' in (ROOT / "libs" / "research" / "layers.py"
                                               ).read_text(encoding="utf-8")


def test_congress_gate_lines_reach_missed_growth_json_as_unmeasured(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """The gate is not a registered rail (the register is sealed), and `missed_growth.run` reads
    the ledger per registered rail -- so its lines are CARRIED into MISSED_GROWTH.json, with
    value None and verdict UNMEASURED, never a zero cost."""
    from research import missed_growth as mg
    ledger = tmp_path / "missed_growth.jsonl"
    monkeypatch.setattr(organ, "MISSED_GROWTH", ledger)
    monkeypatch.delenv("QUANT_CONGRESS_ATTEST", raising=False)
    organ.congress_missed_growth(datetime(2026, 7, 17, tzinfo=UTC))
    monkeypatch.setattr(mg, "LEDGER", ledger)
    monkeypatch.setattr(mg, "OUT", tmp_path / "MISSED_GROWTH.json")
    monkeypatch.setattr(mg, "CALIBRATION", tmp_path / "rail_calibration.json")
    monkeypatch.setattr(mg, "RAILS", ())
    mg.run(write=True, today="2026-07-17")
    doc = json.loads((tmp_path / "MISSED_GROWTH.json").read_text())
    gate = doc["published_gate_lines"]["congress_attestation_gate"]
    assert gate["verdict"] == "UNMEASURED" and gate["value_logw_per_day"] is None
    assert gate["n_lines"] == 3 and gate["n_unpriced"] == 3
    assert set(gate["cells"]) == {"house:member", "senate:member", "congress_agg:all"}
    assert all(x["value"] is None for x in gate["lines"])
    assert mg.ledger_gate_lines([], "congress_attestation_gate")["verdict"] == "NOT_BINDING"
