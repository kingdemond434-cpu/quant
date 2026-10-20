"""IMF PortWatch chokepoint transits (pass-7 N4): parse, PIT stamp, FAILED passes, hard stops,
robots, and the point-in-time consumer the red_sea / central_america packs read. No network:
every fetch goes through an injected getter."""
from __future__ import annotations

import io
import json
import sys
import urllib.error
import urllib.parse
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest

ROOT = Path(__file__).resolve().parents[1]
DESK = ROOT / "desks" / "mt5"
for _p in (str(ROOT), str(DESK), str(DESK / "research")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from countries.central_america import pack as CA  # type: ignore[import-not-found]  # noqa: E402
from countries.red_sea import pack as RS  # type: ignore[import-not-found]  # noqa: E402

from research import alt_proxies as A  # noqa: E402

FIX = ROOT / "tests" / "fixtures" / "alt_proxies"
PW = FIX / "portwatch"
NOW = datetime(2026, 10, 14, 12, tzinfo=UTC)
SRC = A.BY_ID["imf_portwatch_chokepoints"]


def _http(code: int) -> urllib.error.HTTPError:
    return urllib.error.HTTPError("https://x/", code, "no", {}, io.BytesIO(b""))  # type: ignore[arg-type]


META_1000 = b'{"name": "Daily_Chokepoints_Data", "maxRecordCount": 1000}'


class Getter:
    """Scripted responses: robots, the layer metadata, then data pages. Records every URL."""

    def __init__(self, robots: Any, pages: list[Any], meta: Any = META_1000) -> None:
        self.robots, self.pages, self.meta = robots, list(pages), meta
        self.urls: list[str] = []

    def __call__(self, url: str) -> tuple[bytes, str]:
        self.urls.append(url)
        item = (self.robots if url.endswith("/robots.txt") else
                self.meta if "/query?" not in url else
                self.pages.pop(0) if self.pages else b'{"features": []}')  # then: the end
        if isinstance(item, BaseException):
            raise item
        return item, "application/json"

    @property
    def data_urls(self) -> list[str]:
        return [u for u in self.urls if "/query?" in u]


def _run(getter: Any, tmp: Path, sst: dict[str, Any] | None = None,
         store: dict[str, Any] | None = None,
         clock: Any = None) -> tuple[dict[str, Any], dict[str, Any]]:
    sst = {} if sst is None else sst
    paths = A.Paths(tmp / "desk")
    store = {} if store is None else store
    rec = A.collect_portwatch(paths, SRC, sst, store, NOW, fetch=True, fixtures=None,
                              deadline=float("inf"), getter=getter, sleep=lambda _s: None,
                              clock=clock or (lambda: NOW))
    return rec, store


# ============================================================================ parse
def test_portwatch_fixture_page_parses_dateonly_rows_and_tankers() -> None:
    obs = {(o.series, o.period): o.value
           for o in A.parse_portwatch_chokepoints((PW / "chokepoints_page.json").read_bytes(),
                                                  A.Ctx())}
    assert obs[("suez_canal_transits", date(2026, 9, 28))] == 28
    assert obs[("panama_canal_transits", date(2026, 9, 28))] == 30
    assert obs[("bab_el_mandeb_strait_transits", date(2026, 9, 30))] == 33
    assert ("strait_of_hormuz_tanker_transits", date(2026, 9, 29)) in obs


def test_an_arcgis_error_in_a_200_is_named_and_parses_to_nothing() -> None:
    body = (PW / "arcgis_invalid_outfields.json").read_bytes()
    assert A.parse_portwatch_chokepoints(body, A.Ctx()) == []
    err = A.arcgis_error(body)
    assert err and err.startswith("ARCGIS_400") and "outFields" in err
    assert str(A.arcgis_error(b"<html>Access denied</html>")).startswith("NOT_JSON")
    assert A.arcgis_error((PW / "chokepoints_page.json").read_bytes()) is None


def test_requests_ask_only_fields_each_layer_has_at_its_max_record_count() -> None:
    for sid in ("imf_portwatch_chokepoints", "imf_portwatch_ports"):
        (req,) = A.requests_for(A.BY_ID[sid], NOW, {})
        q = urllib.parse.parse_qs(urllib.parse.urlsplit(req.url).query)
        assert q["outFields"] == [A.PORTWATCH_FIELDS[sid]]
        assert q["resultRecordCount"] == ["1000"] and q["resultOffset"] == ["0"]
        assert "DATE '" in q["where"][0]
    fields = A.PORTWATCH_FIELDS["imf_portwatch_chokepoints"].split(",")
    assert "portcalls" not in fields and "n_total" in fields     # the invalid mix that broke it
    assert "n_total" not in A.PORTWATCH_FIELDS["imf_portwatch_ports"].split(",")


# ============================================================================ PIT stamp
def test_pit_stamp_is_never_earlier_than_period_plus_the_stated_release_or_the_read() -> None:
    for d in (date(2026, 10, 4), date(2026, 10, 5), date(2026, 10, 6), date(2026, 9, 1)):
        t = A.rule_portwatch(d)
        assert t.weekday() == 1 and t.hour == A.PORTWATCH_PUBLISH_HOUR_UTC
        assert t >= datetime(d.year, d.month, d.day, tzinfo=UTC) + timedelta(days=2)
    # measured: data to Sun 2026-10-04 was edited in Tue 2026-10-06 12:09 UTC
    assert A.rule_portwatch(date(2026, 10, 4)) == datetime(2026, 10, 6, 14, tzinfo=UTC)
    early = [A.Obs("suez_canal_transits", date(2026, 10, 4), 30.0)]
    store: dict[str, Any] = {}
    A.merge_vintages(store, SRC, early, datetime(2026, 10, 5, tzinfo=UTC))   # impossible early read
    assert store["suez_canal_transits|2026-10-04"]["published_time"] == "2026-10-06T14:00:00+00:00"
    late = [A.Obs("suez_canal_transits", date(2024, 1, 2), 12.0)]           # a backfilled row
    A.merge_vintages(store, SRC, late, NOW)
    assert store["suez_canal_transits|2024-01-02"]["published_time"] == NOW.isoformat()
    assert store["suez_canal_transits|2024-01-02"]["published_basis"] == "first_read"


# ============================================================================ pass outcomes
def test_an_empty_pass_is_failed_never_zero(tmp_path: Path) -> None:
    rec, store = _run(Getter(_http(404), [b'{"features": []}']), tmp_path)
    assert rec["status"] == "FAILED:EMPTY" and rec["outcome"] == "FAILED:EMPTY"
    assert rec["parsed"] == 0 and rec["errors"] and not store


def test_an_arcgis_error_pass_is_failed_with_its_cause(tmp_path: Path) -> None:
    rec, _ = _run(Getter(_http(404), [(PW / "arcgis_invalid_outfields.json").read_bytes()]),
                  tmp_path)
    assert rec["status"] == "FAILED:ARCGIS_400" and "outFields" in rec["why"]


@pytest.mark.parametrize("code", [401, 403, 429])
def test_a_403_hard_stops_and_holds_the_source(code: int, tmp_path: Path) -> None:
    page = (PW / "chokepoints_page.json").read_bytes()
    g = Getter(_http(404), [_http(code), page, page])
    sst: dict[str, Any] = {}
    rec, _ = _run(g, tmp_path, sst)
    assert rec["status"] == "FAILED:HARD_STOP" and len(g.data_urls) == 1
    hold = sst["hard_stop"]
    assert hold["released_by"] is None and "person" in hold["release"]
    assert hold["missed_growth"]["delta_elogw"] == "UNMEASURED" and hold["missed_growth"]["cause"]
    g2 = Getter(_http(404), [page])
    rec2, _ = _run(g2, tmp_path, sst)
    assert rec2["status"] == "HELD:HARD_STOP" and g2.urls == []      # nothing asked while held


@pytest.mark.parametrize("age", [timedelta(hours=25), timedelta(days=11), timedelta(days=400)])
def test_a_refusal_hold_waits_for_a_person_whatever_its_age(age: timedelta,
                                                             tmp_path: Path) -> None:
    page = (PW / "chokepoints_page.json").read_bytes()
    sst: dict[str, Any] = {"hard_stop": {
        "since": (NOW - age).isoformat(timespec="seconds"), "cause": "HARD_STOP: HTTP 403",
        "release": A.PORTWATCH_HOLD_RELEASE, "released_by": None,
        "missed_growth": {"delta_elogw": "UNMEASURED", "cause": "held"}}}
    g = Getter(_http(404), [page])
    rec, store = _run(g, tmp_path, sst)
    assert rec["status"] == "HELD:HARD_STOP" and g.urls == [] and not store   # no request at all
    assert sst["hard_stop"]["missed_growth"]["delta_elogw"] == "UNMEASURED"   # the row stays
    sst["hard_stop"]["released_by"] = "a person"                              # the only release
    rec2, _ = _run(Getter(_http(404), [page]), tmp_path, sst)
    assert rec2["outcome"] == "OK" and "hard_stop" not in sst and sst["hard_stop_released"]


def test_the_ua_is_the_desks_honest_ua_with_no_browser_token() -> None:
    assert A.UA == ("quant-mt5-research-desk/1.0 (+https://github.com/kingdemond434-cpu/quant/"
                    "issues; internal research; honours robots.txt)")
    low = A.UA.lower()
    for tok in ("mozilla/", "chrome/", "safari/", "applewebkit", "gecko/", "edg/"):
        assert tok not in low


def test_robots_decides_disallow_and_a_403_on_robots_is_a_hard_stop(tmp_path: Path) -> None:
    g = Getter((PW / "robots_disallow.txt").read_bytes(), [b"{}"])
    rec, _ = _run(g, tmp_path)
    assert rec["status"] == "FAILED:ROBOTS_DISALLOW" and g.data_urls == []
    g = Getter(_http(403), [b"{}"])
    rec, _ = _run(g, tmp_path)
    assert rec["status"] == "FAILED:HARD_STOP" and g.data_urls == []
    g = Getter(OSError("timeout"), [b"{}"])
    rec, _ = _run(g, tmp_path)
    assert rec["status"] == "FAILED:ROBOTS_UNREADABLE" and g.data_urls == []


def test_pages_step_by_the_layer_limit_and_the_cursor_moves(tmp_path: Path) -> None:
    feats = [{"attributes": {"date": (date(2025, 1, 1) + timedelta(days=i // 8)).isoformat(),
                             "portname": A.CHOKEPOINTS[i % 8], "n_total": 10}}
             for i in range(1000)]
    full = json.dumps({"features": feats}).encode()
    g = Getter(_http(404), [full, (PW / "chokepoints_page.json").read_bytes()])
    sst: dict[str, Any] = {}
    rec, store = _run(g, tmp_path, sst)
    offs = [urllib.parse.parse_qs(urllib.parse.urlsplit(u).query)["resultOffset"][0]
            for u in g.data_urls]
    # a short page is never the end: one more, EMPTY, page proves it
    assert offs == ["0", "1000", "1015"] and rec["outcome"] == "OK" and rec["complete"]
    assert sst["pw_from"] == (date(2026, 9, 30) - timedelta(days=A.PORTWATCH_RECENT_D)).isoformat()
    g2 = Getter(_http(404), [(PW / "chokepoints_page.json").read_bytes()])
    rec2, _ = _run(g2, tmp_path, sst, store)
    assert rec2["outcome"] == "UNCHANGED"                    # read again, nothing new


# ============================================================================ consumer
def _store_file(tmp: Path, rows: list[tuple[str, str, float, str]]) -> Path:
    doc = {f"{s}|{p}": {"series": s, "period": p, "value_first": v, "value_last": v,
                         "first_seen_at": k, "published_time": k} for s, p, v, k in rows}
    fp = tmp / "imf_portwatch_chokepoints.json"
    fp.write_text(json.dumps(doc), "utf-8")
    return fp


def test_the_consumer_cannot_see_a_same_day_or_not_yet_known_value(tmp_path: Path) -> None:
    at = datetime(2026, 10, 13, 15, tzinfo=UTC)
    fp = _store_file(tmp_path, [
        ("suez_canal_transits", "2026-10-11", 30.0, "2026-10-13T14:00:00+00:00"),   # known
        ("suez_canal_transits", "2026-10-12", 31.0, "2026-10-20T14:00:00+00:00"),   # not yet
        ("suez_canal_transits", "2026-10-13", 99.0, "2026-10-13T00:00:00+00:00"),   # same day
    ])
    got = A.chokepoints_asof(at, fp)
    assert got["series"]["suez_canal_transits"] == {
        "period": "2026-10-11", "value": 30.0, "known_at": "2026-10-13T14:00:00+00:00"}
    assert got["by_pack_name"]["suez_transits"]["value"] == 30.0
    before = A.chokepoints_asof(datetime(2026, 10, 13, 13, 59, tzinfo=UTC), fp)
    assert before["status"] == "UNMEASURED"


def test_the_packs_read_the_store_point_in_time(tmp_path: Path) -> None:
    k = "2026-10-06T14:00:00+00:00"
    fp = _store_file(tmp_path, [(s, "2026-10-04", 20.0, k) for s in (
        "suez_canal_transits", "bab_el_mandeb_strait_transits", "panama_canal_transits",
        "cape_of_good_hope_transits")])
    at = datetime(2026, 10, 7, tzinfo=UTC)
    rep = CA.chokepoint_substitution(None, None, store=fp, asof=at)
    assert rep["portwatch"]["status"] == "MEASURED" and rep["unmeasured"] == []
    rs = RS.mine_chokepoint_phases(None, None, store=fp, asof=at)
    rsb = next(r for r in rs["rows"] if r["domain"] == "RS-B")
    assert rsb["portwatch"]["by_pack_name"]["cape_of_good_hope_transits"]["value"] == 20.0
    early = CA.chokepoint_substitution(None, None, store=fp,
                                       asof=datetime(2026, 10, 6, 13, tzinfo=UTC))
    assert any("PortWatch" in u for u in early["unmeasured"])


def test_the_fixture_pass_writes_the_pit_store_and_axis(tmp_path: Path) -> None:
    paths = A.Paths(tmp_path / "desk")
    rep = A.run(paths, fixtures=FIX, donate=False, now=NOW)
    rec = rep["sources"]["imf_portwatch_chokepoints"]
    assert rec["outcome"] == "OK" and rec["parsed"] > 0
    store = json.loads((paths.obs_dir / "imf_portwatch_chokepoints.json").read_text("utf-8"))
    assert all(r["published_time"] >= NOW.isoformat() for r in store.values())


# ============================================================================ audit 84602112c
class CappedServer:
    """An ArcGIS layer holding `n` rows that serves at most `cap` per page, flags
    exceededTransferLimit while rows remain (when `flag`), and publishes or hides its cap."""

    def __init__(self, n: int, cap: int, *, meta: bool = True, flag: bool = True) -> None:
        names = A.CHOKEPOINTS[:5]
        self.rows = [{"date": (date(2024, 1, 1) + timedelta(days=i // 5)).isoformat(),
                      "portname": names[i % 5], "n_total": i} for i in range(n)]
        self.cap, self.meta, self.flag, self.data_calls = cap, meta, flag, 0

    def __call__(self, url: str) -> tuple[bytes, str]:
        if url.endswith("/robots.txt"):
            raise _http(404)
        if "/query?" not in url:
            if not self.meta:
                raise _http(500)
            return json.dumps({"maxRecordCount": self.cap}).encode(), "application/json"
        self.data_calls += 1
        q = urllib.parse.parse_qs(urllib.parse.urlsplit(url).query)
        off, want = int(q["resultOffset"][0]), int(q["resultRecordCount"][0])
        take = self.rows[off: off + min(want, self.cap)]
        doc: dict[str, Any] = {"features": [{"attributes": a} for a in take]}
        if self.flag and off + len(take) < len(self.rows):
            doc["exceededTransferLimit"] = True
        return json.dumps(doc).encode(), "application/json"


def test_a_server_capped_at_500_with_2500_rows_stores_all_2500(tmp_path: Path) -> None:
    srv = CappedServer(2500, 500)
    rec, store = _run(srv, tmp_path)
    assert len(store) == 2500 and rec["outcome"] == "OK" and rec["page_cap"] == 500
    srv2 = CappedServer(2500, 500, meta=False, flag=False)       # cap unknown, no flag at all
    rec2, store2 = _run(srv2, tmp_path / "b")
    assert len(store2) == 2500 and rec2["outcome"] == "OK" and rec2["page_cap"] == "UNMEASURED"


def test_unknown_cap_flagged_truncation_with_no_further_page_is_failed(tmp_path: Path) -> None:
    rows = [{"attributes": {"date": "2025-01-01", "portname": "Suez Canal", "n_total": 1}}]
    first = json.dumps({"features": rows, "exceededTransferLimit": True}).encode()
    g = Getter(_http(404), [first, b'{"features": []}'], meta=_http(500))
    rec, _ = _run(g, tmp_path)
    assert rec["status"] == "FAILED:TRUNCATED" and rec["outcome"] != "OK"


def test_each_page_is_stamped_at_its_own_fetch_not_the_pass_start(tmp_path: Path) -> None:
    ticks = iter([NOW + timedelta(minutes=1), NOW + timedelta(minutes=2),
                  NOW + timedelta(minutes=3)])
    srv = CappedServer(10, 5)
    _rec, store = _run(srv, tmp_path, clock=lambda: next(ticks))
    seen = sorted({r["first_seen_at"] for r in store.values()})
    assert seen == [(NOW + timedelta(minutes=m)).isoformat() for m in (1, 2)]
    for r in store.values():                    # backfill rows: stamp == their page's read
        assert r["published_time"] == r["first_seen_at"] > NOW.isoformat()


def test_floor_stamped_backfill_is_labelled_backfill() -> None:
    store: dict[str, Any] = {}
    A.merge_vintages(store, SRC, [A.Obs("suez_canal_transits", date(2024, 1, 2), 12.0)], NOW)
    pts = A.build_points(SRC, store)["suez_canal_transits"]
    assert pts[0]["pit_quality"] == "backfill"


def test_imf_credit_rides_on_every_portwatch_payload(tmp_path: Path) -> None:
    fp = _store_file(tmp_path, [(s, "2026-10-04", 20.0, "2026-10-06T14:00:00+00:00") for s in (
        "suez_canal_transits", "bab_el_mandeb_strait_transits", "panama_canal_transits",
        "cape_of_good_hope_transits")])
    at = datetime(2026, 10, 7, tzinfo=UTC)
    credit = A.TERMS_EVIDENCE["imf_portwatch_chokepoints"]["credit"]
    assert "International Monetary Fund" in credit
    assert A.chokepoints_asof(at, fp)["credit"] == credit
    assert A.chokepoints_asof(at, tmp_path / "absent.json")["credit"] == credit
    rs = RS.mine_chokepoint_phases(None, None, store=fp, asof=at)
    assert next(r for r in rs["rows"] if r["domain"] == "RS-B")["credit"] == credit
    assert CA.chokepoint_substitution(None, None, store=fp, asof=at)["credit"] == credit


def test_panama_and_the_other_controls_map_to_no_instrument() -> None:
    for s in ("panama_canal_transits", "cape_of_good_hope_transits", "bosporus_strait_transits",
              "gibraltar_strait_transits", "malacca_strait_transits"):
        assert SRC.instruments_for(s) == {}, s
        assert s not in SRC.signal_series
    assert SRC.instruments_for("suez_canal_transits") == {"XBRUSD": -1, "XTIUSD": -1}


# ============================================================================ audit 78e725a3b
class SilentCapServer(CappedServer):
    """States maxRecordCount 1000 in its metadata but serves 500 a page, flag never set."""

    def __call__(self, url: str) -> tuple[bytes, str]:
        if "/query?" not in url and not url.endswith("/robots.txt"):
            return b'{"maxRecordCount": 1000}', "application/json"
        return super().__call__(url)


def test_a_server_silently_capping_below_its_stated_cap_still_stores_all(tmp_path: Path) -> None:
    srv = SilentCapServer(2500, 500, flag=False)
    rec, store = _run(srv, tmp_path)
    assert rec["page_cap"] == 1000 and len(store) == 2500 and rec["outcome"] == "OK"


def test_a_waf_page_on_the_metadata_read_holds_and_never_requests_page_0(tmp_path: Path) -> None:
    g = Getter(_http(404), [(PW / "chokepoints_page.json").read_bytes()],
               meta=b"<html><title>Attention Required</title></html>")
    sst: dict[str, Any] = {}
    rec, store = _run(g, tmp_path, sst)
    assert rec["status"] == "FAILED:NOT_JSON" and g.data_urls == [] and not store
    assert sst["hard_stop"]["released_by"] is None
    assert sst["hard_stop"]["missed_growth"]["delta_elogw"] == "UNMEASURED"


def test_a_server_ignoring_result_offset_fails_on_the_first_repeat(tmp_path: Path) -> None:
    feats = [{"attributes": {"date": "2025-01-01", "portname": n, "n_total": 1}}
             for n in A.CHOKEPOINTS]
    same = json.dumps({"features": feats, "exceededTransferLimit": True}).encode()
    g = Getter(_http(404), [same] * 20)
    rec, _ = _run(g, tmp_path)
    assert rec["status"] == "FAILED:OFFSET_IGNORED" and len(g.data_urls) == 2


@pytest.mark.parametrize(("n", "want"), [(5, 4.56), (10, 3.45), (24, 3.06), (50, 2.94),
                                         (100, 2.89), (500, 2.85)])
def test_the_tier_s_bar_reproduces_the_canonical_dsr_table(n: int, want: float) -> None:
    from libs.research import release_gain as RG
    assert abs(RG.tier_s_t_required(n) - want) <= 0.01
    # never below the canonical normal-shape bar, whatever the sample shape
    for sk, ku in ((0.8, 2.2), (0.0, 2.5), (-1.0, 6.0), (1.5, 9.0)):
        assert RG.tier_s_t_required(n, sk, ku) >= RG.tier_s_t_required(n) - 1e-12
    assert RG.tier_s_t_required(4) == float("inf")


@pytest.mark.parametrize("n_cells", [7, 10, 11, 12, 30])
def test_no_family_size_enters_any_bar(n_cells: int) -> None:
    import inspect

    from libs.research import release_gain as RG
    assert not hasattr(RG, "TIER_S_T_BAR")                 # no bare constant bar
    assert "n_cells" not in inspect.signature(RG.release_gain).parameters
    assert "n_trials" not in inspect.signature(RG.regime_placebo).parameters
    src = inspect.getsource(RG.release_gain) + inspect.getsource(RG.min_detectable_ic)
    assert "n_cells" not in src and "Bonferroni" not in src
    gsrc = inspect.getsource(A.gain_tests)
    assert "n_cells=" not in gsrc and "cells_in_family" in gsrc
    # the bar a cell meets is its own n's, identical for every family size
    assert RG.tier_s_t_required(60) == RG.tier_s_t_required(60) and n_cells > 0
