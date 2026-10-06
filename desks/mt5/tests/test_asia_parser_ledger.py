"""The generic parser keeps HISTORY and REVISIONS (audit 2026-10-06 row 52), and the China
official adapters read the shapes the generic heuristic could not (rows 1-5, 7).

Fixtures under fixtures/cn_official reproduce the published layouts (see their README); the
values are illustrative and nothing here is presented as a measured China statistic.
"""
from __future__ import annotations

import gzip
import hashlib
import json
import sys
from pathlib import Path

import pandas as pd
import pytest

_DESK = Path(__file__).resolve().parents[1]
for _p in (str(_DESK), str(_DESK.parent.parent)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from research import asia_parser as AP  # noqa: E402
from research import cn_official_tables as C  # noqa: E402

FIX = Path(__file__).resolve().parent / "fixtures" / "cn_official"


def _vault(tmp: Path, sid: str, body: bytes, fetched: str, url: str,
           ctype: str = "application/json") -> None:
    d = tmp / "vault" / sid
    d.mkdir(parents=True, exist_ok=True)
    sha = hashlib.sha256(body).hexdigest()
    (d / f"{sha[:16]}.gz").write_bytes(gzip.compress(body))
    (d / f"{sha[:16]}.meta.json").write_text(json.dumps({
        "source_id": sid, "url": url, "content_type": ctype, "sha256": sha,
        "bytes": len(body), "fetched_utc": fetched}), encoding="utf-8")


@pytest.fixture()
def lake(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setattr(AP, "VAULT", tmp_path / "vault")
    monkeypatch.setattr(AP, "SERIES", tmp_path / "series")
    monkeypatch.setattr(AP, "HISTORY", tmp_path / "series" / "history")
    monkeypatch.setattr(AP, "FOUND", tmp_path / "endpoints")
    monkeypatch.setattr(AP, "_registry_rows", lambda: {
        "cfets_fixing": {"id": "cfets_fixing", "country": "cn", "adapter": "chinamoney",
                         "cadence": "daily", "pit": {"publication_lag_days": 0}},
        "plain_table": {"id": "plain_table", "country": "kr", "cadence": "daily"},
        "safe_fx_settlement": {"id": "safe_fx_settlement", "country": "cn", "adapter": "safe",
                               "cadence": "monthly", "pit": {"publication_lag_days": 20}},
    })
    return tmp_path


def _ccpr(date: str, usd: str) -> bytes:
    doc = json.loads((FIX / "ccpr.json").read_text(encoding="utf-8"))
    doc["data"]["lastDate"] = f"{date} 9:15"
    doc["records"][0]["price"] = usd
    return json.dumps(doc, ensure_ascii=False).encode()


URL = "https://www.chinamoney.com.cn/r/cms/www/chinamoney/data/fx/ccpr.json"


def test_daily_snapshots_accumulate_into_a_history_not_an_overwrite(lake: Path) -> None:
    _vault(lake, "cfets_fixing", _ccpr("2026-10-05", "7.1040"), "2026-10-05T01:20:00+00:00", URL)
    _vault(lake, "cfets_fixing", _ccpr("2026-10-06", "7.1012"), "2026-10-06T01:20:00+00:00", URL)
    doc = AP.parse_all()
    led = doc["ledger"]["per_root"]["cfets_fixing"]
    assert led["vintages_read"] == 2 and led["new"] == 8 and led["revised"] == 0
    wide = pd.read_parquet(lake / "series" / "cfets_fixing.parquet")
    assert len(wide) == 2                                   # two days, not the newest one
    usd = wide["central_parity|USD/CNY"].tolist()
    assert usd == [7.1040, 7.1012]
    # THE RELEASE INSTANT, NOT THE FETCH: 09:15 Beijing = 01:15 UTC on each day
    assert str(wide["available_time"].iloc[1]).startswith("2026-10-06 01:15")
    pit = json.loads((lake / "series" / "cfets_fixing.pit.json").read_text(encoding="utf-8"))
    assert pit["frames"][0]["status"] == "STAMPED" and pit["n_rows"] == 2
    # a second pass reads nothing new and writes nothing
    again = AP.parse_all()["ledger"]["per_root"]["cfets_fixing"]
    assert again["vintages_read"] == 0 and again["ledger_rows"] == 8


def test_a_revision_appends_and_the_first_release_view_keeps_the_original(lake: Path) -> None:
    _vault(lake, "cfets_fixing", _ccpr("2026-10-06", "7.1012"), "2026-10-06T01:20:00+00:00", URL)
    AP.parse_all()
    _vault(lake, "cfets_fixing", _ccpr("2026-10-06", "7.1020"), "2026-10-06T05:00:00+00:00", URL)
    AP.parse_all()
    rows = AP.read_ledger("cfets_fixing")
    rev = [r for r in rows if r["revision_number"] == 1]
    assert len(rev) == 1
    first = next(r for r in rows if r["observation_id"] == rev[0]["revision_of"])
    assert first["value"] == pytest.approx(7.1012)
    assert rev[0]["revision_delta"] == pytest.approx(0.0008)
    # the revision is knowable at its own receipt, never back-dated to the original release
    assert rev[0]["knowable_at"] <= "2026-10-06T05:00:00+00:00"
    assert rev[0]["knowable_at"] >= first["knowable_at"]
    wide = pd.read_parquet(lake / "series" / "cfets_fixing.parquet")
    assert wide["central_parity|USD/CNY"].tolist() == [7.1012]     # first release only
    # every contract field the sensor ledger names is present on the row (None where n/a)
    for f in C.CONTRACT_FIELDS:
        assert f in rev[0]
    assert rev[0]["provenance_hash"] and rev[0]["raw_pointer"]


def test_generic_snapshot_tables_become_a_series(lake: Path) -> None:
    for i, (day, val) in enumerate((("2026-10-01", "10"), ("2026-10-02", "12"))):
        body = f"member,volume\nA,{val}\nB,{int(val) + 1}\nC,{int(val) + 2}\n".encode()
        _vault(lake, "plain_table", body, f"{day}T08:00:0{i}+00:00",
               "https://example.kr/x.csv", "text/csv")
    doc = AP.parse_all()
    led = doc["ledger"]["per_root"]["plain_table"]
    assert led["new"] == 6
    wide = pd.read_parquet(lake / "series" / "plain_table.parquet")
    assert len(wide) == 2 and "volume|A" in wide.columns


def test_a_json_document_is_not_read_as_csv(lake: Path) -> None:
    """The cfets_fixing tokenizer error (source_drain.py:177): a JSON blob handed to read_csv."""
    rec = {"status": "PARSED", "files": ["x.json"]}
    AP._stamp_pit(rec, "x", {"fetched_utc": "2026-10-06T01:20:00+00:00"}, {})
    assert rec["pit"]["status"] == "UNSTAMPED"
    assert "tokeniz" not in json.dumps(rec).lower()


def test_safe_index_hands_back_release_articles_and_the_article_parses(lake: Path) -> None:
    idx = C.parse("safe", (FIX / "safe_index.html").read_bytes(), "text/html",
                  "https://www.safe.gov.cn/safe/whxsdsj/index.html", "safe_fx_settlement")
    assert idx is not None and idx.status == "INDEX_PAGE"
    assert idx.endpoints[0].endswith("/safe/2026/0919/26911.html")
    art = C.parse("safe", (FIX / "safe_article.html").read_bytes(), "text/html",
                  idx.endpoints[0], "safe_fx_settlement__ep1")
    assert art is not None and art.status == "PARSED"
    assert art.publication_time == "2026-09-19T08:00:00+00:00"     # 16:00 Beijing, printed
    by = {(o["metric"], o["period"]): o["value"] for o in art.observations}
    assert by[("settlement", "2026-08")] == 13560.0
    assert by[("customer_sales", "2026-08")] == 12055.0           # section kept apart
    assert by[("forward_settlement", "2026-08")] == 1910.0
    assert {o["unit"] for o in art.observations} == {"亿元人民币"}
    assert art.endpoints and art.endpoints[0].endswith(".xlsx")


def test_chinamoney_history_nbs_omo_and_customs_shapes() -> None:
    hist = C.parse("chinamoney", (FIX / "ccpr_history.json").read_bytes(), "", "u", "s")
    assert hist is not None and hist.status == "PARSED" and len(hist.observations) == 9
    shib = C.parse("chinamoney", (FIX / "shibor.json").read_bytes(), "",
                   "https://www.chinamoney.com.cn/r/cms/www/chinamoney/data/shibor/shibor.json",
                   "s")
    assert shib is not None and {o["metric"] for o in shib.observations} == {"shibor"}
    assert shib.observations[0]["event_time"] == "2026-10-06T03:00:00+00:00"   # 11:00 Beijing
    nbs = C.parse("nbs_easyquery", (FIX / "nbs_pmi.json").read_bytes(), "", "u", "nbs_pmi")
    assert nbs is not None and nbs.status == "PARSED"
    metrics = {o["metric"] for o in nbs.observations}
    assert {"new_orders", "new_export_orders", "finished_goods_inventory", "input_prices",
            "employment", "pmi"} <= metrics
    aug = next(o for o in nbs.observations if o["metric"] == "pmi" and o["period"] == "2026-08")
    assert aug["scheduled_time"] == "2026-08-31T01:30:00+00:00"          # 09:30 Beijing
    omo = C.parse("pboc_omo", (FIX / "pboc_omo_article.html").read_bytes(), "", "u", "omo")
    assert omo is not None and omo.status == "PARSED"
    net = next(o for o in omo.observations if o["metric"] == "omo_net_injection")
    assert net["value"] == -1700.0
    cus = C.parse("customs", (FIX / "customs_import_table.html").read_bytes(), "", "u", "cc")
    assert cus is not None and cus.status == "PARSED"
    ore = {o["metric"]: o["value"] for o in cus.observations if o["entity"] == "铁矿砂及其精矿"}
    assert ore["import_quantity"] == 10523.0
    assert ore["import_unit_value"] == pytest.approx(5612300.0 / 10523.0)


def test_xlsx_reader_needs_no_third_party_engine() -> None:
    import io
    import zipfile
    sheet = ('<?xml version="1.0"?><worksheet xmlns="http://schemas.openxmlformats.org/'
             'spreadsheetml/2006/main"><sheetData>'
             '<row r="1"><c r="A1" t="s"><v>0</v></c><c r="B1"><v>2026.06</v></c>'
             '<c r="C1"><v>2026.07</v></c><c r="D1"><v>2026.08</v></c></row>'
             '<row r="2"><c r="A2" t="s"><v>1</v></c><c r="B2"><v>33000</v></c>'
             '<c r="C2"><v>33100</v></c><c r="D2"><v>33250</v></c></row>'
             '</sheetData></worksheet>')
    shared = ('<?xml version="1.0"?><sst xmlns="http://schemas.openxmlformats.org/spreadsheetml/'
              '2006/main"><si><t>项目</t></si><si><t>外汇储备</t></si></sst>')
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("xl/worksheets/sheet1.xml", sheet)
        z.writestr("xl/sharedStrings.xml", shared)
    res = C.parse("safe", buf.getvalue(), "", "https://www.safe.gov.cn/x.xlsx", "safe_reserves")
    assert res is not None and res.status == "PARSED"
    assert [o["metric"] for o in res.observations] == ["fx_reserves"] * 3
    assert res.observations[-1]["value"] == 33250.0
    xls = C.parse("safe", b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1" + b"\0" * 64, "",
                  "https://www.safe.gov.cn/x.xls", "safe_reserves")
    assert xls is not None and xls.status == "NEEDS_PARSER" and "xlrd" in xls.why


def test_printed_dates_are_read_in_the_pages_own_clock() -> None:
    dt, basis = C.parse_local_datetime("2026-09-19 16:00", 8)
    assert dt is not None and dt.isoformat() == "2026-09-19T16:00:00+08:00"
    dt2, basis2 = C.parse_local_datetime("2026年9月19日", 8)
    assert dt2 is not None and dt2.hour == 23 and "date only" in basis2
    dt3, basis3 = C.parse_local_datetime("2026-09-19 16:00", None)
    assert dt3 is not None and "unknown" in basis3                   # never a guessed offset
