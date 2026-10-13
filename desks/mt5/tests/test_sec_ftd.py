"""SEC fails-to-deliver: collected point-in-time, mapped to MT5 CFDs, judged through the
registered alt-series families. Fixtures only -- no network.

Pinned here:
  * only the listing's own hrefs are fetched, newest missing first, at most `max_files` a pass;
  * no QUANT_EDGAR_UA -> NEEDS_KEY and nothing fetched; the agent is sent and never echoed;
  * requests are spaced at least half a second apart (<= 2 per second);
  * available_time = max(schedule bound, a plausible Last-Modified); a re-upload's late stamp
    does not erase history; each vintage is written once and never rewritten;
  * ETFs map to index/metal CFDs and single names to share CFDs; unmapped tickers are dropped;
  * the consuming family reads the series on its own clock, behind its publication-day lag.
"""
from __future__ import annotations

import io
import itertools
import json
import sys
import zipfile
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pandas as pd
import pytest

_DESK = Path(__file__).resolve().parents[1]
for _p in (str(_DESK.parents[1]), str(_DESK), str(_DESK / "research")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import sec_ftd as ftd  # noqa: E402

REGISTRY = {"US500": {"asset_class": "Indices"}, "XAUUSD": {"asset_class": "Commodities"},
            "Apple": {"asset_class": "Equities"}, "EURUSD": {"asset_class": "Forex"}}


def ftd_zip(year: int, month: int, half: str, *, scale: float = 1.0) -> bytes:
    """One FTD file as the SEC publishes it: header, pipe rows, a '.' price, a trailer."""
    days = range(1, 15) if half == "a" else range(16, 28)
    lines = ["SETTLEMENT DATE|CUSIP|SYMBOL|QUANTITY (FAILS)|DESCRIPTION|PRICE"]
    for d in days:
        dt = f"{year}{month:02d}{d:02d}"
        lines += [f"{dt}|78462F103|SPY|{int(1000 * scale * d)}|SPDR S&P 500 ETF|500.00",
                  f"{dt}|78463V107|GLD|{int(200 * scale)}|SPDR GOLD SHARES|180.0",
                  f"{dt}|037833100|AAPL|{int(50 * scale)}|APPLE INC|.",
                  f"{dt}|000000000|ZZZQ|999999|NOT MAPPED|1.0"]
    lines += ["Trailer record count 4", ""]
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr(f"cnsfails{year}{month:02d}{half}.txt", "\n".join(lines))
    return buf.getvalue()


def periods(n: int, end: tuple[int, int] = (2026, 8)) -> list[tuple[int, int, str]]:
    y, m = end
    out: list[tuple[int, int, str]] = []
    while len(out) < n:
        out += [(y, m, "b"), (y, m, "a")]
        y, m = (y - 1, 12) if m == 1 else (y, m - 1)
    return out[:n]


class FakeSEC:
    """The listing and its files. Records every URL asked for and the headers' presence."""

    def __init__(self, ps: list[tuple[int, int, str]], *, extra_html: str = "",
                 last_modified: dict[str, str] | None = None) -> None:
        self.files = {f"cnsfails{y}{m:02d}{h}.zip": ftd_zip(y, m, h, scale=1 + (i % 5))
                      for i, (y, m, h) in enumerate(ps)}
        self.lm = last_modified or {}
        self.html = "".join(f'<a href="/files/data/fails-deliver-data/{n}">{n}</a>'
                            for n in self.files) + extra_html
        self.asked: list[str] = []

    def __call__(self, url: str, accept: str) -> tuple[bytes, dict[str, str]]:
        self.asked.append(url)
        if url == ftd.LISTING_URL:
            return self.html.encode(), {}
        name = url.rsplit("/", 1)[-1]
        if name not in self.files:
            raise OSError("404")
        lm = self.lm.get(name)
        return self.files[name], ({"last-modified": lm} if lm else {})


# ----------------------------------------------------------------------------- the listing
def test_listing_reads_only_the_pages_own_hrefs() -> None:
    html = ('<a href="/files/data/fails-deliver-data/cnsfails202608b.zip">b</a>'
            '<a href="https://www.sec.gov/files/data/fails-deliver-data/cnsfails202308b_0.zip">'
            'x</a><a href="https://elsewhere.example/cnsfails202301a.zip">off-site</a>'
            '<a href="/files/other.zip">no</a>')
    got = ftd.listing(html)
    assert [r["name"] for r in got] == ["cnsfails202308b_0.zip", "cnsfails202608b.zip"]
    assert got[1]["url"] == ("https://www.sec.gov/files/data/fails-deliver-data/"
                             "cnsfails202608b.zip")
    assert got[0]["vintage"] == 0 and got[1]["vintage"] == -1
    assert got[1]["period"] == "202608b"


# ----------------------------------------------------------------------------- point in time
def test_available_time_is_the_schedule_bound_or_a_plausible_late_posting() -> None:
    assert ftd.schedule_bound(2026, 8, "a") == datetime(2026, 9, 5, tzinfo=UTC)
    assert ftd.schedule_bound(2026, 8, "b") == datetime(2026, 9, 20, tzinfo=UTC)
    assert ftd.schedule_bound(2025, 12, "b") == datetime(2026, 1, 20, tzinfo=UTC)
    at, basis = ftd.available_time(2026, 8, "a", None)
    assert at == datetime(2026, 9, 5, tzinfo=UTC) and "no Last-Modified" in basis
    # posted early: the bound still stands (never earlier than the stated schedule allows)
    at, _ = ftd.available_time(2026, 8, "a", "Mon, 31 Aug 2026 18:00:00 GMT")
    assert at == datetime(2026, 9, 5, tzinfo=UTC)
    # posted late: the server's stamp is later than the bound, so it governs
    at, basis = ftd.available_time(2026, 8, "b", "Tue, 29 Sep 2026 14:00:00 GMT")
    assert at == datetime(2026, 9, 29, 14, tzinfo=UTC) and "late posting" in basis
    # an old file re-uploaded years later keeps its history on the bound
    at, basis = ftd.available_time(2019, 3, "a", "Tue, 29 Sep 2026 14:00:00 GMT")
    assert at == datetime(2019, 4, 5, tzinfo=UTC) and "re-upload" in basis


def test_parse_skips_header_and_trailer_and_reads_a_dot_price_as_unknown() -> None:
    f = ftd.parse_ftd(ftd_zip(2026, 8, "a"))
    assert set(f["symbol"]) == {"SPY", "GLD", "AAPL", "ZZZQ"}
    assert len(f) == 14 * 4
    assert f.loc[f["symbol"] == "AAPL", "price"].isna().all()
    assert f["settlement_date"].min() == pd.Timestamp("2026-08-01", tz="UTC")


# ----------------------------------------------------------------------------- collection
def test_no_user_agent_is_needs_key_and_fetches_nothing(tmp_path: Path,
                                                         monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv(ftd.UA_ENV, raising=False)

    def boom(*a: Any, **k: Any) -> Any:
        raise AssertionError("nothing may be fetched without a declared User-Agent")
    import urllib.request
    monkeypatch.setattr(urllib.request, "urlopen", boom)
    out = ftd.collect(store=tmp_path / "s")
    assert out["status"] == "NEEDS_KEY" and out["fetched"] == 0
    assert ftd.UA_ENV in out["why"]


def test_requests_carry_the_agent_are_spaced_and_never_echo_it(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    declared = "Desk Research ops-contact@example.invalid"
    monkeypatch.setenv(ftd.UA_ENV, declared)
    sec = FakeSEC(periods(3))
    clock = {"t": 1000.0}
    sleeps: list[float] = []
    seen: list[tuple[float, str]] = []

    class Resp:
        def __init__(self, body: bytes, headers: dict[str, str]) -> None:
            self._b, self.headers, self.status = body, headers, 200

        def __enter__(self) -> Resp:
            return self

        def __exit__(self, *a: Any) -> None:
            return None

        def read(self, n: int = -1) -> bytes:
            return self._b

    def fake_urlopen(req: Any, timeout: float = 0) -> Resp:
        seen.append((clock["t"], req.get_header("User-agent")))
        body, headers = sec(req.full_url, "")
        return Resp(body, headers)

    def fake_sleep(s: float) -> None:
        sleeps.append(s)
        clock["t"] += s
    import urllib.request
    monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)
    monkeypatch.setattr(ftd.time, "monotonic", lambda: clock["t"])
    monkeypatch.setattr(ftd.time, "sleep", fake_sleep)
    out = ftd.collect(store=tmp_path / "s", max_files=3)
    assert out["fetched"] == 3 and len(seen) == 4
    assert all(ua == declared for _, ua in seen)
    gaps = [b[0] - a[0] for a, b in itertools.pairwise(seen)]
    assert min(gaps) >= ftd.MIN_INTERVAL_S - 1e-9          # <= 2 requests a second
    assert declared not in json.dumps(out)
    for p in (tmp_path / "s").iterdir():
        assert declared not in p.read_bytes().decode("latin-1")


def test_newest_missing_first_capped_and_each_vintage_written_once(tmp_path: Path) -> None:
    store = tmp_path / "s"
    sec = FakeSEC(periods(6))
    out = ftd.collect(store=store, fetch=sec, max_files=2)
    assert out["fetched"] == 2 and out["missing"] == 6
    assert out["planned"] == ["cnsfails202608b.zip", "cnsfails202608a.zip"]
    # a second pass fetches the next two and never re-asks for a held file
    sec.asked.clear()
    out2 = ftd.collect(store=store, fetch=sec, max_files=2)
    assert out2["planned"] == ["cnsfails202607b.zip", "cnsfails202607a.zip"]
    assert not any(u.endswith("cnsfails202608b.zip") for u in sec.asked)
    # the vintage is never rewritten, even if handed different content
    pq = store / "cnsfails202608b.parquet"
    before = pq.read_bytes()
    item = next(r for r in ftd.listing(sec.html) if r["name"] == "cnsfails202608b.zip")
    ftd.store_file(store, item, ftd.parse_ftd(ftd_zip(2026, 8, "b", scale=9)), {},
                   datetime.now(tz=UTC))
    assert pq.read_bytes() == before
    meta = json.loads((store / "cnsfails202608b.json").read_text())
    assert meta["available_time"] == "2026-09-20T00:00:00+00:00"


def test_dry_run_reads_the_listing_only(tmp_path: Path) -> None:
    sec = FakeSEC(periods(4))
    out = ftd.collect(store=tmp_path / "s", fetch=sec, dry_run=True)
    assert out["status"] == "DRY_RUN" and len(out["planned"]) == 4
    assert sec.asked == [ftd.LISTING_URL]
    assert not (tmp_path / "s").exists()


# ----------------------------------------------------------------------------- the series
def test_series_maps_etfs_and_shares_and_is_stamped(tmp_path: Path) -> None:
    store, series = tmp_path / "s", tmp_path / "series"
    sec = FakeSEC(periods(4), last_modified={"cnsfails202608b.zip":
                                             "Tue, 29 Sep 2026 14:00:00 GMT"})
    ftd.collect(store=store, fetch=sec, max_files=10)
    summary = ftd.build_series(store=store, series_dir=series, registry=REGISTRY)
    assert set(summary) == {"US500", "XAUUSD", "Apple"}         # ZZZQ is mapped to nothing
    assert summary["US500"]["tickers"] == ["SPY"] and summary["US500"]["periods"] == 4
    f = pd.read_parquet(series / "ftd_US500.parquet")
    assert {"event_time", "available_time", "published_time", "retrieval_time", "source_id",
            "vintage_id", "ftd_value_usd", "ftd_value_log"} <= set(f.columns)
    assert (pd.to_datetime(f["available_time"], utc=True)
            > pd.to_datetime(f["event_time"], utc=True)).all()
    late = f[f["vintage_id"] == "cnsfails202608b"].iloc[0]
    assert pd.Timestamp(late["available_time"]) == pd.Timestamp("2026-09-29 14:00", tz="UTC")
    # AAPL's price is unknown ('.'), so its dollar value is zero, never a guess
    a = pd.read_parquet(series / "ftd_Apple.parquet")
    assert (a["ftd_value_usd"] == 0).all() and (a["ftd_shares"] > 0).all()


def test_the_family_reads_the_series_behind_its_own_lag(tmp_path: Path) -> None:
    from mt5desk.family_exogenous_conditioner import DEFAULT_LAG_HOURS, conditioner
    store, series = tmp_path / "s", tmp_path / "series"
    ftd.collect(store=store, fetch=FakeSEC(periods(40)), max_files=40)
    ftd.build_series(store=store, series_dir=series, registry=REGISTRY)
    f = pd.read_parquet(series / "ftd_US500.parquet")
    c = conditioner("ftd_US500", "ftd_value_log", "raw", root=series)
    assert c is not None and len(c) == len(f)
    avail = pd.to_datetime(f["available_time"], utc=True).sort_values()
    assert c.index.min() == avail.min() + pd.Timedelta(hours=DEFAULT_LAG_HOURS)
    assert (c.index > pd.DatetimeIndex(avail)).all()
