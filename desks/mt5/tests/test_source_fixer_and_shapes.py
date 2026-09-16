"""The source fixer's URL variants and the parser bank's shape sniffing (2026-09-16)."""
from __future__ import annotations

import sys
from pathlib import Path

_DESK = Path(__file__).resolve().parents[1]
for p in (str(_DESK), str(_DESK / "research")):
    if p not in sys.path:
        sys.path.insert(0, p)

import asia_parser  # noqa: E402
import source_fixer  # noqa: E402


def test_candidate_urls_are_the_webmasters_variants_and_never_the_original() -> None:
    url = "http://www.example.gov/data/stats.htm?x=1"
    cands = source_fixer.candidate_urls(url)
    assert url not in cands and len(cands) == len(set(cands))
    assert "https://www.example.gov/data/stats.htm?x=1" in cands        # scheme swap
    assert "http://example.gov/data/stats.htm?x=1" in cands             # www dropped
    assert "http://www.example.gov/data/stats.htm" in cands             # query stripped
    assert source_fixer.candidate_urls("not a url") == []


def test_acceptable_answers_match_the_declared_shape() -> None:
    ok, _ = source_fixer._acceptable("json", "text/html", b'{"a": 1}')
    assert ok
    ok, _ = source_fixer._acceptable("csv", "text/html", b"<!doctype html><html>")
    assert not ok
    ok, _ = source_fixer._acceptable("any", "text/html", b"x" * 100)
    assert ok
    ok, _ = source_fixer._acceptable("any", "text/html", b"")
    assert not ok


def test_sniff_reads_the_bytes_not_the_registry() -> None:
    assert asia_parser._sniff(b'<?xml version="1.0"?><r/>', "text/html", "https://x/a") == "xml"
    assert asia_parser._sniff(b'  {"a": 1}', "text/html", "https://x/api?format=jsondata") == "json"
    assert asia_parser._sniff(b"date,value\n2026-01-01,1\n2026-01-02,2\n2026-01-03,3\n",
                              "text/plain", "https://x/data.csv") == "csv"
    assert asia_parser._sniff(b"<!doctype html><html>", "text/html", "https://x/") == "html"
    assert asia_parser._sniff(b"%PDF-1.4", "application/octet-stream", "https://x/r.pdf") == "pdf"


def test_xml_rows_become_a_frame(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(asia_parser, "SERIES", tmp_path)
    body = (b'<?xml version="1.0" encoding="utf-8"?><data><row id="1"><date>2026-09-01</date>'
            b"<close>10.5</close></row><row id=\"2\"><date>2026-09-02</date><close>10.7</close>"
            b"</row><row id=\"3\"><date>2026-09-03</date><close>10.9</close></row></data>")
    rec = asia_parser._parse_xml(body, "cffex_test")
    assert rec["status"] == "PARSED" and rec["rows"] == [3]
    import pandas as pd
    df = pd.read_parquet(tmp_path / rec["files"][0])
    assert list(df.columns) == ["@id", "date", "close"] and len(df) == 3


def test_csv_and_pit_stamp_land_on_the_frame(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(asia_parser, "SERIES", tmp_path)
    body = b"date,value\n2026-07-31,1\n2026-08-31,2\n2026-09-14,3\n"
    rec = asia_parser._parse_csv(body, "src_monthly")
    assert rec["status"] == "PARSED"
    registry = {"src_monthly": {"id": "src_monthly", "cadence": "monthly",
                                "pit": {"publication_lag_days": 20}}}
    asia_parser._stamp_pit(rec, "src_monthly", {"fetched_utc": "2026-09-16T00:00:00+00:00"},
                           registry)
    assert rec["pit"]["status"] == "STAMPED" and rec["pit"]["lag_days"] == 20
    import pandas as pd
    df = pd.read_parquet(tmp_path / rec["files"][0])
    assert str(df["available_time"].iloc[1])[:10] == "2026-09-20"
    assert (tmp_path / "src_monthly.pit.json").exists()
