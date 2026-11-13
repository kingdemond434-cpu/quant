"""US rates from their primary publishers (Treasury, NY Fed), replacing FRED's copies."""
from __future__ import annotations

import json
import sys
from datetime import date
from pathlib import Path

from libs.data import us_primary_rates as P

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(ROOT / "scripts"))

NOM = (b'Date,"1 Mo","2 Yr","5 Yr","10 Yr","30 Yr"\n'
       b"12/31/2025,3.74,3.47,3.73,4.18,4.84\n12/30/2025,3.65,3.45,,4.14,4.81\n")
REAL = b'Date,"5 YR","10 YR"\n12/31/2025,1.47,1.93\n12/30/2025,1.43,1.90\n'
SOFR = json.dumps({"refRates": [{"effectiveDate": "2026-11-12", "type": "SOFR",
                                 "percentRate": 3.90}]}).encode()


def _get(seen: list[str]):
    def get(url: str) -> tuple[int | None, bytes]:
        seen.append(url)
        if url.endswith("/robots.txt"):
            return 200, b"User-agent: *\nAllow: /\n"
        if "daily_treasury_real_yield_curve" in url:
            return 200, REAL
        if "daily_treasury_yield_curve" in url:
            return 200, NOM
        if "sofr" in url:
            return 200, SOFR
        return 404, b""
    return get


def test_treasury_csv_parses_and_a_blank_cell_is_absent() -> None:
    cols = P.parse_treasury(NOM)
    assert cols["10 yr"]["2025-12-31"] == 4.18
    assert "2025-12-30" not in cols["5 yr"]


def test_fred_ids_are_served_with_fred_definitions() -> None:
    seen: list[str] = []
    got, why = P.series(["DGS10", "T10Y2Y", "DFII10", "T10YIE", "SOFR", "VIXCLS"],
                        date(2025, 12, 1), get=_get(seen), today=date(2025, 12, 31))
    assert got["DGS10"]["2025-12-31"] == 4.18
    assert got["T10Y2Y"]["2025-12-31"] == round(4.18 - 3.47, 4)
    assert got["T10YIE"]["2025-12-30"] == round(4.14 - 1.90, 4)
    assert got["SOFR"] == {"2026-11-12": 3.90}
    assert "VIXCLS" not in got and "no primary-publisher route" in why["VIXCLS"]
    assert not any("stlouisfed" in u for u in seen)


def test_robots_refusal_sends_no_data_request() -> None:
    seen: list[str] = []

    def get(url: str) -> tuple[int | None, bytes]:
        seen.append(url)
        return (200, b"User-agent: *\nDisallow: /\n") if url.endswith("robots.txt") \
            else (200, NOM)
    got, why = P.series(["DGS10", "DFF"], date(2025, 1, 1), get=get, today=date(2025, 2, 1))
    assert got == {} and all("ROBOTS_REFUSED" in w for w in why.values())
    assert all(u.endswith("/robots.txt") for u in seen)


def test_unreadable_robots_fails_closed() -> None:
    gate = P.robots_refusal(lambda u: (403, b""))
    assert gate("https://home.treasury.gov/x")
    html = P.robots_refusal(lambda u: (200, b"<html>login</html>"))
    assert html("https://markets.newyorkfed.org/api/x")
    missing = P.robots_refusal(lambda u: (404, b""))
    assert missing("https://home.treasury.gov/x") is None


def test_collector_refreshes_mapped_series_and_keeps_held_ones(monkeypatch, tmp_path) -> None:
    import collect_fred_macro as C
    long_ = tmp_path / "fred_macro_long.json"
    long_.write_text(json.dumps({"series": {"VIXCLS": [["2024-01-02", 13.2]],
                                            "DGS10": [["2024-01-02", 3.9]]}}), "utf-8")
    monkeypatch.setattr(C, "_ROOT", tmp_path)
    monkeypatch.setattr(C, "_ARCHIVE", tmp_path / "fred_macro.json")
    monkeypatch.setattr(C, "_ARCHIVE_LONG", long_)
    monkeypatch.setattr(C, "_WEB", tmp_path / "web.json")
    monkeypatch.setattr(C, "_SERIES", ("DGS10", "VIXCLS"))
    monkeypatch.setattr(P, "series", lambda ids, start, **k: (
        {"DGS10": {"2026-11-12": 4.1}}, {"VIXCLS": "no primary-publisher route mapped"}))
    C.main()
    doc = json.loads(long_.read_text("utf-8"))
    assert doc["series"]["DGS10"] == [["2026-11-12", 4.1]]
    assert doc["series"]["VIXCLS"] == [["2024-01-02", 13.2]]          # held, never dropped
    assert doc["sources"]["DGS10"].startswith("US Treasury")
    assert "held copy" in doc["sources"]["VIXCLS"]
