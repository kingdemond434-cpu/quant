"""The weekly COT refresher: verified, robots-gated, incremental, lossless, exact-market."""
from __future__ import annotations

import json
import ssl
import sys
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

import pandas as pd
import pytest

_DESK = Path(__file__).resolve().parents[1]
for _p in (str(_DESK), str(_DESK.parent.parent)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from libs.data import cftc_socrata as S  # noqa: E402
from mt5desk import cot_refresh as R  # noqa: E402

ROBOTS = b"User-agent: *\nCrawl-delay: 1\nDisallow: /OData.svc/\nDisallow: /api/odata/\n"


class Fake:
    """Serves robots and Socrata rows; records every request."""

    def __init__(self, rows_by_name: dict[str, list[dict]]) -> None:
        self.rows_by_name = rows_by_name
        self.urls: list[str] = []

    def __call__(self, url: str) -> bytes:
        self.urls.append(url)
        if url.endswith("/robots.txt"):
            return ROBOTS
        q = parse_qs(urlsplit(url).query)
        where = q["$where"][0]
        out = [r for name, rows in self.rows_by_name.items() if f"'{name}'" in where
               for r in rows]
        if ">=" in where:
            since = where.split(">= '")[1][:10]
            out = [r for r in out if r["report_date_as_yyyy_mm_dd"][:10] >= since]
        offset = int(q["$offset"][0])
        return json.dumps(out[offset:offset + S.PAGE]).encode()


def _legacy(date: str, oi: int, name: str = "GOLD") -> dict:
    return {"report_date_as_yyyy_mm_dd": f"{date}T00:00:00.000", "commodity_name": name,
            "contract_market_name": name, "open_interest_all": str(oi),
            "noncomm_positions_long_all": "10", "noncomm_positions_short_all": "5",
            "comm_positions_long_all": "3", "comm_positions_short_all": "8",
            "change_in_noncomm_long_all": "1", "change_in_noncomm_short_all": "0",
            "change_in_open_interest_all": "2"}


def _client(fake: Fake) -> S.Client:
    return S.Client(get=fake, sleep=lambda s: None)


def _only(target_slug: str, family: str, monkeypatch) -> None:
    monkeypatch.setattr(R, "TARGETS", tuple(t for t in R.TARGETS
                                            if t.slug == target_slug and t.family == family))


def test_tls_is_verified_never_disabled() -> None:
    ctx = S.tls_context()
    assert ctx.verify_mode == ssl.CERT_REQUIRED and ctx.check_hostname
    src = Path(S.__file__).read_text("utf-8") + Path(R.__file__).read_text("utf-8")
    assert "verify_mode = ssl.CERT_NONE" not in src and "check_hostname = False" not in src
    assert '"User-Agent": "Mozilla' not in src and "Mozilla" not in S.AGENT


def test_latest_release_waits_for_friday() -> None:
    thu = datetime(2026, 11, 12, 12, tzinfo=UTC)
    fri_early = datetime(2026, 11, 13, 15, tzinfo=UTC)
    fri_late = datetime(2026, 11, 13, 22, tzinfo=UTC)
    assert str(R.latest_release(thu).date()) == "2026-11-03"
    assert str(R.latest_release(fri_early).date()) == "2026-11-03"
    assert str(R.latest_release(fri_late).date()) == "2026-11-10"


def test_incremental_merge_keeps_every_held_date_and_restates(tmp_path, monkeypatch) -> None:
    _only("gold", "legacy", monkeypatch)
    old = R.frame(R.TARGETS[0], [_legacy("2026-07-28", 100), _legacy("2026-08-04", 101),
                                 _legacy("2026-08-11", 102)])
    R.write_parquet(old, tmp_path / "cot" / "gold.parquet")
    fake = Fake({"GOLD": [_legacy("2026-08-11", 999), _legacy("2026-11-10", 120)]})
    doc = R.refresh(client=_client(fake), now=datetime(2026, 11, 14, tzinfo=UTC),
                    data=tmp_path, report=tmp_path / "r.json")
    row = doc["slugs"][0]
    assert row["status"] == "REFRESHED" and row["newest"] == "2026-11-10" and row["added"] == 1
    got = pd.read_parquet(tmp_path / "cot" / "gold.parquet")
    assert list(got.columns) == list(old.columns)
    assert len(got) == 4                                       # nothing held was dropped
    assert got.set_index("report_date").loc["2026-08-11", "open_interest_all"] == 999
    assert (tmp_path / "cot_gold.parquet").exists()             # the legacy alias
    assert any(">= '2026-06-16" in u.replace("%27", "'").replace("+", " ") or
               "2026-06-16" in u for u in fake.urls)            # eight weeks of overlap


def test_fresh_files_send_no_request(tmp_path, monkeypatch) -> None:
    _only("gold", "legacy", monkeypatch)
    R.write_parquet(R.frame(R.TARGETS[0], [_legacy("2026-11-10", 1)]),
                    tmp_path / "cot" / "gold.parquet")
    fake = Fake({})
    doc = R.refresh(client=_client(fake), now=datetime(2026, 11, 14, tzinfo=UTC),
                    data=tmp_path, report=None)
    assert doc["slugs"][0]["status"] == "FRESH" and fake.urls == []


def test_a_failed_fetch_leaves_the_held_file_untouched(tmp_path, monkeypatch) -> None:
    _only("gold", "legacy", monkeypatch)
    p = tmp_path / "cot" / "gold.parquet"
    R.write_parquet(R.frame(R.TARGETS[0], [_legacy("2026-08-11", 1)]), p)
    before = p.read_bytes()

    def boom(url: str) -> bytes:
        if url.endswith("/robots.txt"):
            return ROBOTS
        raise OSError("down")
    doc = R.refresh(client=S.Client(get=boom, sleep=lambda s: None),
                    now=datetime(2026, 11, 14, tzinfo=UTC), data=tmp_path, report=None)
    assert doc["slugs"][0]["status"] == "FAILED" and p.read_bytes() == before


def test_robots_refusal_and_unreadable_robots_fail_closed() -> None:
    def disallow(url: str) -> bytes:
        return b"User-agent: *\nDisallow: /resource/\n" if url.endswith("robots.txt") else b"[]"
    with pytest.raises(S.Refused):
        S.Client(get=disallow, sleep=lambda s: None).fetch(S.HOST + "/resource/x.json")

    def html(url: str) -> bytes:
        return b"<html>blocked</html>" if url.endswith("robots.txt") else b"[]"
    with pytest.raises(S.Refused):
        S.Client(get=html, sleep=lambda s: None).fetch(S.HOST + "/resource/x.json")


def test_crawl_delay_is_obeyed() -> None:
    waits: list[float] = []
    c = S.Client(get=lambda u: ROBOTS if u.endswith("robots.txt") else b"[]", sleep=waits.append)
    c.fetch(S.HOST + "/resource/a.json")
    c.fetch(S.HOST + "/resource/b.json")
    assert waits and 0 < waits[0] <= 1.0


def test_a_contaminated_tff_file_is_rebuilt_from_exact_markets(tmp_path, monkeypatch) -> None:
    _only("eur", "tff", monkeypatch)
    t = R.TARGETS[0]
    dirty = pd.DataFrame({"report_date": pd.to_datetime(["2026-08-04", "2026-08-11"], utc=True),
                          "market": ["EURO FX - CHICAGO MERCANTILE EXCHANGE",
                                     "EURO FX/JAPANESE YEN XRATE - CHICAGO MERCANTILE EXCHANGE"],
                          "oi": [1, 2], "dealer_l": [0, 0], "dealer_s": [0, 0], "am_l": [0, 0],
                          "am_s": [0, 0], "lm_l": [0, 0], "lm_s": [0, 0]})
    R.write_parquet(dirty, tmp_path / "cot_tff" / "eur.parquet")
    assert R.contaminated(t, dirty)

    def tff(date: str, oi: int) -> dict:
        return {"report_date_as_yyyy_mm_dd": f"{date}T00:00:00.000",
                "market_and_exchange_names": "EURO FX - CHICAGO MERCANTILE EXCHANGE",
                "open_interest_all": str(oi), "dealer_positions_long_all": "1",
                "dealer_positions_short_all": "2", "asset_mgr_positions_long": "3",
                "asset_mgr_positions_short": "4", "lev_money_positions_long": "5",
                "lev_money_positions_short": "6"}
    fake = Fake({"EURO FX - CHICAGO MERCANTILE EXCHANGE": [tff("2026-08-11", 50),
                                                           tff("2026-11-10", 60)]})
    doc = R.refresh(client=_client(fake), now=datetime(2026, 11, 14, tzinfo=UTC),
                    data=tmp_path, report=None)
    assert doc["slugs"][0]["status"] == "REBUILT"
    got = pd.read_parquet(tmp_path / "cot_tff" / "eur.parquet")
    assert set(got["market"]) == {"EURO FX - CHICAGO MERCANTILE EXCHANGE"}
    assert list(got.columns) == ["report_date", "market", "oi", "dealer_l", "dealer_s",
                                 "am_l", "am_s", "lm_l", "lm_s"]
    assert not any(">=" in u for u in fake.urls if "resource" in u)   # full history


def test_the_box_task_runs_the_refresher() -> None:
    cmd = (_DESK.parent.parent / "ops" / "run_side_channel_miners.cmd").read_text("utf-8")
    assert "-m mt5desk.cot_refresh" in cmd


def test_first_seen_time_is_recorded_and_never_moved_by_a_restatement(tmp_path,
                                                                      monkeypatch) -> None:
    _only("gold", "legacy", monkeypatch)
    old = R.frame(R.TARGETS[0], [_legacy("2026-08-04", 1), _legacy("2026-08-11", 2)])
    R.write_parquet(old, tmp_path / "cot" / "gold.parquet")
    first = datetime(2026, 11, 14, tzinfo=UTC)
    fake = Fake({"GOLD": [_legacy("2026-08-11", 5), _legacy("2026-11-10", 6)]})
    R.refresh(client=_client(fake), now=first, data=tmp_path, report=None)
    got = pd.read_parquet(tmp_path / "cot" / "gold.parquet").set_index("report_date")
    assert pd.isna(got.loc["2026-08-04", R.SEEN])            # never seen: not invented
    assert got.loc["2026-11-10", R.SEEN] == pd.Timestamp(first)
    later = datetime(2026, 11, 21, 22, tzinfo=UTC)
    fake = Fake({"GOLD": [_legacy("2026-11-10", 7), _legacy("2026-11-17", 8)]})
    R.refresh(client=_client(fake), now=later, data=tmp_path, report=None)
    got = pd.read_parquet(tmp_path / "cot" / "gold.parquet").set_index("report_date")
    assert got.loc["2026-11-10", "open_interest_all"] == 7          # the restatement lands
    assert got.loc["2026-11-10", R.SEEN] == pd.Timestamp(first)    # first sight stays
    assert got.loc["2026-11-17", R.SEEN] == pd.Timestamp(later)


def test_a_redirect_to_another_host_is_refused_and_never_followed() -> None:
    import http.client
    import io
    import urllib.request
    sent: list[str] = []

    class Handler(urllib.request.HTTPSHandler):
        def https_open(self, req):  # type: ignore[no-untyped-def]
            sent.append(req.full_url)
            msg = http.client.HTTPMessage()
            msg["Location"] = "https://fred.stlouisfed.org/x"
            resp = urllib.request.addinfourl(io.BytesIO(b""), msg, req.full_url, 302)
            resp.msg = "Found"
            return resp

    op = urllib.request.build_opener(S._SameHostRedirects(), Handler())
    with pytest.raises(S.CrossHostRedirect):
        op.open(S.HOST + "/resource/x.json")
    assert sent == [S.HOST + "/resource/x.json"]


def test_the_in_tree_held_schemas_match_what_the_refresher_writes() -> None:
    for t in R.TARGETS:
        df = R.held(t)
        if df is None:
            continue
        cols = set(df.columns) - {R.SEEN}
        want = {"tff": set(R.TFF_RENAME.values())}.get(t.family, set(
            ("report_date," + R.SELECT[t.family].split(",", 1)[1]).split(",")))
        assert cols == want, (t.family, t.slug, cols ^ want)
