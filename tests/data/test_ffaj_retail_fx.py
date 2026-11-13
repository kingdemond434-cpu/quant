"""FFAJ monthly retail FX positioning parses to point-in-time net shares, robots first."""
from __future__ import annotations

from libs.data import ffaj_retail_fx as FF


class _Sheet:
    def __init__(self, name: str, rows: list[list[object]]) -> None:
        self.name, self.rows = name, rows


def test_sheet_prefers_base_currency_and_skips_headers() -> None:
    rows: list[list[object]] = [
        ["月", "年", "取引高", "売", "買", "計"],
        [9.0, 2026.0, 1.0, 26.0, 34.0, 60.0, 7.0, 16.0, 24.0, 40.0],   # base cols win
        [8.0, 2026.0, 1.0, 30.0, 10.0, 40.0],                           # JPY cols only
        [13.0, 2026.0, 1.0, 1.0, 1.0, 2.0],                             # not a month
    ]
    out = FF.parse_sheet("USDJPY", rows)
    assert [r["month_end"] for r in out] == ["2026-09-30", "2026-08-31"]
    assert abs(out[0]["net"] - (24 - 16) / 40) < 1e-12
    assert abs(out[1]["net"] - (10 - 30) / 40) < 1e-12
    assert out[0]["available_at"] == "2026-10-20"


def test_workbook_keeps_only_tradable_pairs() -> None:
    row = [12.0, 2025.0, 1.0, 1.0, 3.0, 4.0]
    df = FF.parse_workbook([_Sheet("USDJPY", [row]), _Sheet("ALL(TOTAL)", [row]),
                            _Sheet("note", [["x"]])])
    assert list(df["pair"]) == ["USDJPY"]
    s = FF.net_series(df, "USDJPY")
    assert str(s.index.tz) == "UTC" and abs(float(s.iloc[0]) - 0.5) < 1e-12


def test_fetch_refuses_before_any_request_when_robots_refuses() -> None:
    asked: list[str] = []

    def get(url: str) -> tuple[int | None, bytes]:
        asked.append(url)
        return 200, b""
    df, why = FF.fetch(get, lambda u: "disallowed")
    assert df.empty and why.startswith("ROBOTS_REFUSED") and asked == []


def test_fetch_picks_the_uploads_workbook_not_navigation_files() -> None:
    page = (b'<a href="/wp-content/themes/nav.pdf">x</a>'
            b'<a href="/wp-content/uploads/2026/10/trading_vol_and_position.xls">f</a>')
    asked: list[str] = []

    def get(url: str) -> tuple[int | None, bytes]:
        asked.append(url)
        return (200, page) if url == FF.INDEX else (404, b"")
    df, why = FF.fetch(get, lambda u: None)
    assert asked[1] == ("https://www.ffaj.or.jp/wp-content/uploads/2026/10/"
                        "trading_vol_and_position.xls")
    assert df.empty and why == "workbook HTTP 404"


def test_fetch_refuses_a_workbook_link_on_another_host() -> None:
    page = b'<a href="https://evil.example/wp-content/uploads/trading_vol_and_position.xls">f</a>'
    asked: list[str] = []

    def get(url: str) -> tuple[int | None, bytes]:
        asked.append(url)
        return 200, page
    df, why = FF.fetch(get, lambda u: None)
    assert df.empty and "off the FFAJ host" in why and asked == [FF.INDEX]
