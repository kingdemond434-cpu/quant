"""BACKLOG 609: FRED is refused for every automated fetch (terms ruling 2026-11-13), and the four
usd_liquidity series come from their primary publishers instead.

Asserted as behaviour, with no network anywhere in this file:

* `free_data.fred_series` never builds a request to FRED -- not when the refused list is patched
  empty, not when that list cannot be imported -- and records BLOCKED_ON_TERMS with its
  missed-growth line;
* the callers (vol_archive, macro_desk, ops_redundancy) degrade to their existing "no data" path
  and say BLOCKED_ON_TERMS where they can, never crash and never read a refusal as data;
* each primary-publisher parser reads a tiny synthetic fixture, and the door obeys robots, hard
  stops on 401/403/429/451 and on an HTML wall;
* a fence: no non-test module carries a FRED data-endpoint URL without a refusal gate in it.
"""
from __future__ import annotations

import json
import re
import sys
import urllib.error
import urllib.request
from datetime import date
from pathlib import Path
from typing import Any

import pytest

DESK = Path(__file__).resolve().parents[1]
ROOT = DESK.parent.parent
for _p in (str(ROOT), str(DESK), str(DESK / "research")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

FIX = Path(__file__).resolve().parent / "fixtures" / "usd_liquidity"


@pytest.fixture
def wire(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    """Every URL anything tries to open. Each attempt raises, so nothing reaches a socket."""
    seen: list[str] = []

    def boom(req: Any, *a: Any, **k: Any) -> Any:
        seen.append(req.full_url if hasattr(req, "full_url") else str(req))
        raise AssertionError("network touched")

    class _Opener:
        def open(self, req: Any, *a: Any, **k: Any) -> Any:
            return boom(req)

    monkeypatch.setattr(urllib.request, "urlopen", boom)
    monkeypatch.setattr(urllib.request, "build_opener", lambda *a, **k: _Opener())
    return seen


@pytest.fixture
def fd(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Any:
    from research import free_data
    monkeypatch.setattr(free_data, "CACHE", tmp_path)
    free_data.FRED_REFUSALS.clear()
    return free_data


# ------------------------------------------------------------------------------ fred_series
@pytest.mark.parametrize("sid,vintage", [("VIXCLS", None), ("DGS10", None),
                                         ("PAYEMS", "2020-01-01")])
def test_fred_series_never_contacts_fred_even_with_the_list_empty(
        fd: Any, wire: list[str], monkeypatch: pytest.MonkeyPatch, sid: str,
        vintage: str | None) -> None:
    from libs.data import refused_hosts
    monkeypatch.setattr(refused_hosts, "REFUSED_HOSTS", {})
    out = fd.fred_series(sid, vintage=vintage)
    assert out is None                    # no mirror reachable here: the failed-fetch value
    assert not [u for u in wire if "stlouisfed" in u]
    rec = fd.FRED_REFUSALS[sid]
    assert rec["status"] == "BLOCKED_ON_TERMS"
    assert rec["missed_growth"]["verdict"] == "a gap, not a zero"


def test_fred_series_fails_closed_when_the_refused_list_cannot_import(
        fd: Any, wire: list[str], monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setitem(sys.modules, "libs.data.refused_hosts", None)
    assert "fail closed" in (fd._refusal("https://example.org/data.csv") or "")
    with pytest.raises(urllib.error.URLError, match="BLOCKED_ON_TERMS"):
        fd._get("https://example.org/data.csv")
    assert fd.fred_series("DGS2") is None
    assert fd.FRED_REFUSALS["DGS2"]["status"] == "BLOCKED_ON_TERMS"
    assert wire == []


def test_the_shared_get_refuses_every_refused_host_before_the_wire(fd: Any,
                                                                   wire: list[str]) -> None:
    for url in ("https://fred.stlouisfed.org/graph/fredgraph.csv?id=DGS10",
                "https://query1.finance.yahoo.com/v8/finance/chart/%5EVIX"):
        with pytest.raises(urllib.error.URLError, match="BLOCKED_ON_TERMS"):
            fd._get(url)
    assert fd.yahoo_daily("^VIX") is None
    assert wire == []


def test_the_gated_transports_refuse_fred(wire: list[str]) -> None:
    from libs.data.keyed_sources import keyed_urlopen
    from libs.data.off_limits import off_limits
    from libs.data.refused_hosts import RefusedSource
    url = "https://api.stlouisfed.org/fred/series/observations?series_id=DGS10"
    assert (off_limits(url) or "").startswith("BLOCKED_ON_TERMS")
    assert off_limits("") is None             # an empty roster field is not a request
    with pytest.raises(RefusedSource):
        keyed_urlopen(urllib.request.Request(url), timeout=5)
    assert wire == []


# ---------------------------------------------------------------------------------- callers
def test_vol_archive_records_the_cboe_indices_blocked_with_no_request(wire: list[str],
                                                                      tmp_path: Path) -> None:
    from recorders import vol_archive as va
    src = va.YahooVolSource()
    assert src.series("^VIX") is None
    assert src.refused["^VIX"].startswith("BLOCKED_ON_TERMS")
    cycle = va.observe(src, {"US500": {}, "XAUUSD": {}}, tmp_path)
    by = {o.vol_ticker: o for o in cycle}
    for t in ("^VIX", "^GVZ", "^OVX", "^VXN"):
        assert by[t].status == "BLOCKED_ON_TERMS"
        assert "missed_growth" in by[t].reason
        assert by[t].implied_vol is None
    assert wire == []


def test_macro_desk_names_the_refusal(fd: Any, wire: list[str]) -> None:
    from research import macro_desk
    st = macro_desk.series_state("VIXCLS")
    assert st["ok"] is False and st["status"] == "BLOCKED_ON_TERMS"
    assert not [u for u in wire if "stlouisfed" in u]


def test_ops_redundancy_degrades_to_no_source(fd: Any, wire: list[str]) -> None:
    from research import ops_redundancy
    closes, source = ops_redundancy._independent_closes("EURUSD")
    assert closes == {} and source == "none"
    assert wire == []


def test_data_alternates_fred_route_raises_before_the_wire(wire: list[str]) -> None:
    sys.path.insert(0, str(ROOT / "scripts"))
    import data_alternates

    from libs.data.refused_hosts import RefusedSource
    with pytest.raises(RefusedSource, match="BLOCKED_ON_TERMS"):
        data_alternates.fred_route("DGS10")
    assert "fred" not in [n for n, _f in data_alternates.MACRO_ROUTES]
    assert wire == []


def test_collect_fred_macro_is_refused_and_writes_nothing(tmp_path: Path,
                                                         monkeypatch: pytest.MonkeyPatch) -> None:
    import importlib.util
    spec = importlib.util.spec_from_file_location("collect_fred_macro_t",
                                                  ROOT / "scripts" / "collect_fred_macro.py")
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    monkeypatch.setattr(mod, "_ARCHIVE", tmp_path / "fred_macro.json")
    monkeypatch.setattr(mod, "_key", lambda: "never-used")
    monkeypatch.setattr(mod, "_fetch", lambda *a: pytest.fail("FRED fetched"))
    mod.main()
    assert not (tmp_path / "fred_macro.json").exists()


# ------------------------------------------------------------------------ the replacements
def test_h41_parser_reads_the_week_average_column() -> None:
    import usd_liquidity_primary as U
    pts = U.parse_h41_csv((FIX / "h41.csv").read_text(encoding="utf-8"))
    assert pts == [(date(2026, 11, 4), 3000000.0), (date(2026, 11, 18), 3100000.0)]


def test_nyfed_rrp_parser_sums_reverse_repo_only() -> None:
    import usd_liquidity_primary as U
    pts = U.parse_nyfed_rrp(json.loads((FIX / "rrp.json").read_text(encoding="utf-8")))
    assert pts == [(date(2026, 11, 16), 150000000.0), (date(2026, 11, 17), 70000000.0)]


def test_nyfed_sofr_parser() -> None:
    import usd_liquidity_primary as U
    pts = U.parse_nyfed_sofr(json.loads((FIX / "sofr.json").read_text(encoding="utf-8")))
    assert pts == [(date(2026, 11, 13), 3.91), (date(2026, 11, 16), 3.93)]


def test_dts_parser_reads_the_tga_closing_balance_in_both_eras() -> None:
    import usd_liquidity_primary as U
    pts = U.parse_dts_tga(json.loads((FIX / "dts.json").read_text(encoding="utf-8")))
    assert pts == [(date(2021, 3, 1), 1500.0), (date(2026, 11, 17), 812345.0)]


def test_available_time_is_the_publication_time_never_the_event_date() -> None:
    import usd_liquidity_primary as U
    # Wednesday 2026-11-25 week -> Thanksgiving Thursday is a holiday -> Friday.
    assert U.available_h41(date(2026, 11, 25)) == "2026-11-27T21:30:00+00:00"
    assert U.available_rrp(date(2026, 11, 17)) == "2026-11-17T18:30:00+00:00"
    assert U.available_sofr(date(2026, 11, 13)) == "2026-11-16T13:30:00+00:00"   # Fri -> Mon
    assert U.available_dts(date(2026, 11, 17)) == "2026-11-18T21:30:00+00:00"


def _fixture_opener(codes: dict[str, int] | None = None, robots: bytes | None = None,
                    ctype: str | None = None) -> tuple[Any, list[str]]:
    seen: list[str] = []
    body = {"federalreserve.gov": (FIX / "h41.csv").read_bytes(),
            "reverserepo": (FIX / "rrp.json").read_bytes(),
            "secured/sofr": (FIX / "sofr.json").read_bytes(),
            "fiscaldata": (FIX / "dts.json").read_bytes()}

    def open_(req: urllib.request.Request, timeout: float) -> tuple[int, str, bytes]:
        url = req.full_url
        seen.append(url)
        assert req.get_header("User-agent", "").startswith("quant-desk-research/")
        if url.endswith("/robots.txt"):
            return (200, "text/plain", robots) if robots is not None else (404, "", b"")
        for k, b in body.items():
            if k in url:
                code = (codes or {}).get(k, 200)
                ct = ctype or ("text/csv" if k == "federalreserve.gov" else "application/json")
                return code, ct, b if code == 200 else b""
        raise AssertionError(f"unexpected url {url}")
    return open_, seen


def test_ingest_reads_all_four_from_fixtures_with_no_network(wire: list[str]) -> None:
    import usd_liquidity_primary as U
    open_, seen = _fixture_opener()
    doc = U.ingest(U.Door(open_))
    assert doc["n_series"] == 4 and doc["failed"] == {}
    assert not [u for u in seen if "stlouisfed" in u]
    p = doc["series"]["SOFR"]["points"][0]
    assert p["event_time"] == "2026-11-13" and p["available_time"] == p["knowable_at"]
    assert "DTCC" in doc["series"]["SOFR"]["attribution"]
    assert all(doc["series"][s]["terms"]["clause"] for s in doc["series"])
    assert wire == []


def test_shadow_institutional_reads_the_new_axis(tmp_path: Path) -> None:
    import shadow_institutional as S
    import usd_liquidity_primary as U
    open_, _seen = _fixture_opener()
    doc = U.ingest(U.Door(open_))
    (tmp_path / "usd_liquidity.json").write_text(json.dumps(doc), encoding="utf-8")
    pts = S.read_axis_points(tmp_path, "usd_liquidity", "SOFR")
    assert pts == [("2026-11-16", 3.91), ("2026-11-17", 3.93)]     # dated by publication
    rows = {s.sensor_id: s for s in S.SENSORS} if hasattr(S, "SENSORS") else {}
    for sid in ("us_reserve_balances", "us_tga", "us_rrp", "us_sofr_iorb"):
        if rows:
            assert rows[sid].axis_file == "usd_liquidity"


@pytest.mark.parametrize("code", [401, 403, 429, 451])
def test_a_refusal_status_is_a_hard_stop_with_missed_growth(code: int) -> None:
    import usd_liquidity_primary as U
    open_, seen = _fixture_opener(codes={"reverserepo": code})
    door = U.Door(open_)
    doc = U.ingest(door)
    assert doc["failed"]["RRPONTSYD"]["status"] == "HARD_STOP"
    assert doc["failed"]["RRPONTSYD"]["missed_growth"]["verdict"] == "a gap, not a zero"
    # the host is stopped for the pass: SOFR on the same host is not requested afterwards
    assert doc["failed"]["SOFR"]["status"] == "HARD_STOP"
    assert not [u for u in seen if "secured/sofr" in u]
    assert doc["n_series"] == 2


def test_robots_disallow_and_html_walls_are_refused() -> None:
    import usd_liquidity_primary as U
    open_, seen = _fixture_opener(robots=b"User-agent: *\nDisallow: /\n")
    doc = U.ingest(U.Door(open_))
    assert doc["n_series"] == 0
    assert {v["status"] for v in doc["failed"].values()} == {"BLOCKED_ON_TERMS"}
    assert all(u.endswith("/robots.txt") for u in seen)
    open_, _ = _fixture_opener(ctype="text/html")
    doc = U.ingest(U.Door(open_))
    assert {v["status"] for v in doc["failed"].values()} == {"HARD_STOP"}


def test_unreadable_robots_is_not_permission() -> None:
    import usd_liquidity_primary as U

    def open_(req: urllib.request.Request, timeout: float) -> tuple[int, str, bytes]:
        if req.full_url.endswith("/robots.txt"):
            return 500, "", b""
        raise AssertionError("data fetched behind unreadable robots")
    doc = U.ingest(U.Door(open_))
    assert doc["n_series"] == 0


def test_the_ingester_is_on_the_axis_table_and_the_battery() -> None:
    import axis_ingest

    from research import batteries
    assert "usd_liquidity" in axis_ingest.INGESTERS
    entries = [e for group in (getattr(batteries, n) for n in dir(batteries))
               if isinstance(group, tuple) for e in group if hasattr(e, "path")]
    hit = [e for e in entries if e.path.endswith("usd_liquidity_primary.py")]
    assert hit and "--apply" in hit[0].argv


# ------------------------------------------------------------------------------------ fence
#: A FRED data endpoint written as a URL: fredgraph.csv, the FRED/ALFRED API, an ALFRED graph.
#: A bare root ("https://api.stlouisfed.org/fred/") in a declarative source catalogue is not an
#: endpoint; the crawlers that read those catalogues (acquire_datasets) refuse the host themselves.
_FRED_ENDPOINT = re.compile(r"stlouisfed\.org/(?:graph/fredgraph|fred/(?:series|release))")
#: Tokens that put a refusal check in front of the wire: the list itself, or a transport that
#: consults it (polite_fetch.get -> off_limits; keyed_urlopen -> guard).
_GATES = ("refused_hosts", "polite_fetch", "keyed_urlopen")
_SKIP = {"tests", "test", "_retired", "node_modules", ".git", "backups", "dist"}


def test_fence_no_module_carries_a_fred_endpoint_without_a_refusal_gate() -> None:
    offenders = []
    paths = [p for top in ("libs", "desks", "scripts", "ops", "api", "app")
             for p in (ROOT / top).rglob("*.py")] + list(ROOT.glob("*.py"))
    for path in paths:
        rel = path.relative_to(ROOT)
        if _SKIP & set(rel.parts) or path.name.startswith("test_") or path.name == "conftest.py":
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        if not _FRED_ENDPOINT.search(text):
            continue
        if not any(g in text for g in _GATES):
            offenders.append(str(rel))
    assert offenders == [], ("modules that build a FRED URL with no refusal gate in front of "
                             f"the wire (BACKLOG 609): {offenders}")


def test_fence_catches_an_ungated_fred_fetch() -> None:
    src = ('import urllib.request\n'
           'urllib.request.urlopen("https://fred.stlouisfed.org/graph/fredgraph.csv?id=X")\n')
    assert _FRED_ENDPOINT.search(src) and not any(g in src for g in _GATES)


def test_sofr_is_stamped_on_the_sifma_calendar_not_the_federal_one() -> None:
    import usd_liquidity_primary as U
    # Thursday 2026-04-02: Good Friday 04-03 is a SIFMA close, so the print lands Monday 04-06.
    assert U.available_sofr(date(2026, 4, 2)) == "2026-04-06T13:30:00+00:00"
    # Tuesday 2018-12-04: 2018-12-05 was a SIFMA full close (national day of mourning).
    assert U.available_sofr(date(2018, 12, 4)) == "2018-12-06T13:30:00+00:00"


def test_the_liquidity_user_agent_names_no_person_or_repository() -> None:
    import usd_liquidity_primary as U
    assert "github" not in U.UA.lower() and "http" not in U.UA.lower()
    assert U.UA.startswith("quant-desk-research/")


def test_an_html_page_served_as_robots_is_not_permission() -> None:
    # A soft-404 or challenge page at /robots.txt with HTTP 200 parses as allow-all; it is unread.
    import usd_liquidity_primary as U
    open_, seen = _fixture_opener(robots=b"<!DOCTYPE html><html><body>Not found</body></html>")
    doc = U.ingest(U.Door(open_))
    assert doc["n_series"] == 0
    assert all(u.endswith("/robots.txt") for u in seen)


def test_data_alternates_refuses_an_html_robots_page(monkeypatch: pytest.MonkeyPatch) -> None:
    import io
    import sys as _sys
    _sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "scripts"))
    import data_alternates as DA

    class _R(io.BytesIO):
        def __enter__(self) -> _R:
            return self

        def __exit__(self, *a: object) -> None:
            self.close()

    monkeypatch.setattr(DA, "_ROBOTS", {})
    monkeypatch.setattr(DA.urllib.request, "urlopen",
                        lambda req, timeout: _R(b"<html><body>hi</body></html>"))
    with pytest.raises(PermissionError, match="answered HTML"):
        DA._robots_allows("https://api.db.nomics.world/v22/series")
    monkeypatch.setattr(DA, "_ROBOTS", {})
    monkeypatch.setattr(DA.urllib.request, "urlopen",
                        lambda req, timeout: _R(b"User-agent: *\nAllow: /\n"))
    DA._robots_allows("https://api.db.nomics.world/v22/series")


@pytest.mark.parametrize("page", ["<head><title>x</title></head>", "<body>blocked</body>",
                                  '<?xml version="1.0"?><error/>', "<!-- waf -->\n<div>no</div>",
                                  "\n\n<!DOCTYPE html>", "x\n<html><body>hi</body></html>"])
def test_any_markup_page_served_as_robots_is_unread(page: str) -> None:
    import usd_liquidity_primary as U
    assert U._looks_like_html(page)
    assert not U._looks_like_html("User-agent: *\nDisallow: /private\n")
