"""SMARD load, residual load and generation by type (research/smard_power.py, in alt_proxies).

No network: every GET goes through an injected getter and robots.txt through an injected
robots_getter; the answers are the chart_data fixtures under tests/fixtures/alt_proxies."""
from __future__ import annotations

import io
import json
import sys
import urllib.error
import urllib.request
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest

ROOT = Path(__file__).resolve().parents[1]
DESK = ROOT / "desks" / "mt5"
for _p in (str(ROOT), str(DESK), str(DESK / "research")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from research import alt_proxies as A  # noqa: E402
from research import entsoe_power as E  # noqa: E402
from research import smard_power as S  # noqa: E402

FIX = ROOT / "tests" / "fixtures" / "alt_proxies"
NOW = datetime(2026, 10, 3, 12, tzinfo=UTC)
WEEK = 1790546400000                      # Mon 2026-09-28 00:00 Berlin, the fixture's week
HTML = b"<!doctype html><html><head><title>Access denied</title></head><body>WAF</body></html>"
COMPLETE = [date(2026, 9, 28) + timedelta(days=i) for i in range(5)]   # 09-28 .. 10-02


def _fx(slug: str) -> dict[str, Any]:
    return dict(json.loads((FIX / f"smard_power.{slug}.json").read_text("utf-8")))


def _http(code: int) -> urllib.error.HTTPError:
    return urllib.error.HTTPError("https://www.smard.de/app/chart_data/x", code, "refused", {},  # type: ignore[arg-type]
                                  io.BytesIO(b""))


class Getter:
    """Serves the index and the fixture week by URL; `script` overrides call by call."""

    def __init__(self, script: list[Any] | None = None, stamps: list[int] | None = None,
                 missing: set[str] | None = None) -> None:
        self.calls: list[str] = []
        self.script = list(script) if script is not None else None
        self.stamps = stamps or [WEEK]
        self.missing = missing or set()

    def __call__(self, url: str) -> tuple[bytes, str]:
        self.calls.append(url)
        if self.script:
            item = self.script.pop(0)
            if isinstance(item, BaseException):
                raise item
            return item, "application/json"
        filt, region, name = url.rsplit("/", 3)[1:]
        if any(m in url for m in self.missing):
            raise _http(404)
        if name.startswith("index_"):
            return json.dumps({"timestamps": self.stamps}).encode(), "application/json"
        doc = _fx("de_lu" if region == "DE-LU" else "de")
        week = doc.get(filt)
        if week is None or not name.endswith(f"_{WEEK}.json"):
            raise _http(404)
        return json.dumps(week).encode(), "application/json"


def _robots(body: bytes = b"User-agent: *\nAllow: /\n") -> Any:
    def get(url: str) -> tuple[bytes, str]:
        assert url == "https://www.smard.de/robots.txt"
        return body, "text/plain"
    return get


def _collect(tmp: Path, getter: Getter, *, sst: dict[str, Any] | None = None,
             store: dict[str, Any] | None = None, deadline: float = float("inf"),
             clock: Any = None, robots: Any = None, now: datetime = NOW,
             sleep: Any = None) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    sst = {"cursor": {"DE-LU": WEEK, "DE": WEEK}} if sst is None else sst
    store = {} if store is None else store
    rec = S.collect(A, A.Paths(tmp / "desk"), S.make_source(A), sst, store, now, fetch=True,
                    fixtures=None, deadline=deadline, getter=getter,
                    robots_getter=robots or _robots(), sleep=sleep or (lambda s: None),
                    clock=clock or (lambda: now))
    return rec, sst, store


def _comps(slug: str) -> dict[str, list[tuple[datetime, float]]]:
    out = {}
    for f, week in _fx(slug).items():
        pts = S.parse_week(json.dumps(week).encode())
        if pts is not None:
            out[S._component(int(f))] = pts
    return out


# ---------------------------------------------------------------- parse and fold
def test_fixture_weeks_fold_to_complete_berlin_days_only() -> None:
    rows = S.fold_days("de_lu", _comps("de_lu"), [*COMPLETE, date(2026, 10, 3)], A.cet_offset_h)
    assert {d for _s, d, _v in rows} == set(COMPLETE)            # 10-03 is partial: absent
    names = {s for s, _d, _v in rows}
    assert {"de_lu_load_mean", "de_lu_residual_load", "de_lu_gen_gas", "de_lu_gen_lignite",
            "de_lu_gen_hard_coal", "de_lu_gen_wind_on", "de_lu_gen_wind_off", "de_lu_gen_pv",
            "de_lu_ren_share"} == names
    assert "de_lu_gen_nuclear" not in names                     # all-null is absent, never zero
    share = [v for s, _d, v in rows if s == "de_lu_ren_share"]
    assert all(0 < v < 100 for v in share)


def test_a_type_covering_part_of_a_day_makes_the_mix_incomplete() -> None:
    comps = _comps("de_lu")
    day = date(2026, 10, 1)
    a, _b = E.day_bounds(day, A.cet_offset_h)
    comps["gas"] = [(t, v) for t, v in comps["gas"] if t != a + timedelta(hours=5)]
    rows = {(s, d) for s, d, _v in S.fold_days("de_lu", comps, [day, date(2026, 10, 2)],
                                                A.cet_offset_h)}
    assert ("de_lu_load_mean", day) in rows
    assert ("de_lu_gen_gas", day) not in rows and ("de_lu_ren_share", day) not in rows
    assert ("de_lu_gen_gas", date(2026, 10, 2)) in rows


def test_non_json_bodies_are_never_parsed() -> None:
    assert S.parse_week(HTML) is None and S.parse_index(HTML) is None
    assert S.parse_week(b"[1,2]") is None
    assert S.parse_index(b'{"timestamps": [3, 1, 2]}') == [1, 2, 3]
    assert S.parse_week(b'{"series": [[0, null], [3600000, 5.5]]}') == [
        (datetime(1970, 1, 1, 1, tzinfo=UTC), 5.5)]


# ---------------------------------------------------------------- fetch discipline
def test_requests_are_the_chart_data_urls_spaced_once_each_with_the_desk_ua(
        tmp_path: Path, monkeypatch: Any) -> None:
    seen_ua: list[str] = []

    def fake_open(req: Any, timeout: float, context: Any) -> Any:
        seen_ua.append(req.headers["User-agent"])
        raise _http(404)
    monkeypatch.setattr(urllib.request, "urlopen", fake_open)
    with pytest.raises(urllib.error.HTTPError):
        S.http_get(S.index_url(S.LOAD, "DE-LU"), E._ua(A))
    assert "quant-mt5-research-desk" in seen_ua[0]

    g = Getter()
    sleeps: list[float] = []
    rec, _sst, _store = _collect(tmp_path, g, sleep=sleeps.append)
    assert rec["outcome"] == "OK", rec
    assert g.calls[0] == "https://www.smard.de/app/chart_data/410/DE-LU/index_hour.json"
    assert f"https://www.smard.de/app/chart_data/4071/DE-LU/4071_DE-LU_hour_{WEEK}.json" in g.calls
    assert len(g.calls) == len(set(g.calls)) == 1 + 14 + 1 + 2  # retries=0, nothing twice
    assert len(sleeps) == len(g.calls) - 1 and min(sleeps) >= S.MIN_INTERVAL_S
    assert rec["unmeasured_windows"] == []


def test_a_robots_crawl_delay_above_the_floor_is_honoured(tmp_path: Path) -> None:
    sleeps: list[float] = []
    rec, _s, _st = _collect(tmp_path, Getter(), sleep=sleeps.append,
                            robots=_robots(b"User-agent: *\nCrawl-delay: 7\nAllow: /\n"))
    assert rec["outcome"] == "OK" and set(sleeps) == {7.0}


@pytest.mark.parametrize("code", [401, 403, 429])
def test_a_refusal_is_held_for_a_person_in_the_shared_shape(code: int, tmp_path: Path) -> None:
    rec, sst, _store = _collect(tmp_path, Getter([_http(code)]))
    assert rec["outcome"] == "FAILED:HARD_STOP"
    h = sst["hard_stop"]
    assert h["key"] == f"site:{S.HOST}" and h["host"] == S.HOST and h["status"] == code
    assert h["verdict"] == S.BLOCK_VERDICT[code]
    assert h["released_by"] is None and h["released_at"] is None
    assert h["missed_growth"]["delta_elogw"] == "UNMEASURED"
    g = Getter()
    rec2, _s, _st = _collect(tmp_path, g, sst=sst, now=NOW + timedelta(days=365))
    assert rec2["outcome"] == "HELD:HARD_STOP" and g.calls == []
    sst["hard_stop"]["released_by"] = "auditor"
    rec3, _s, _st = _collect(tmp_path, Getter(), sst=sst)
    assert rec3["outcome"] == "OK"


def test_a_waf_page_is_a_hard_stop(tmp_path: Path) -> None:
    rec, sst, _store = _collect(tmp_path, Getter([HTML]))
    assert rec["outcome"] == "FAILED:WAF"
    assert sst["hard_stop"]["status"] == "WAF"
    assert sst["hard_stop"]["verdict"] == "METHOD_BLOCKED"


def test_robots_decides_every_pass(tmp_path: Path) -> None:
    g = Getter()
    rec, _s, _st = _collect(tmp_path, g, robots=_robots(b"User-agent: *\nDisallow: /app/\n"))
    assert rec["outcome"] == "FAILED:ROBOTS_DISALLOW" and g.calls == []

    def unreadable(url: str) -> tuple[bytes, str]:
        raise OSError("down")
    g2 = Getter()
    rec2, _s, _st = _collect(tmp_path, g2, robots=unreadable)
    assert rec2["outcome"] == "FAILED:ROBOTS_UNREADABLE" and g2.calls == []

    def forbidden(url: str) -> tuple[bytes, str]:
        raise _http(403)
    rec3, sst3, _st = _collect(tmp_path, Getter(), robots=forbidden)
    assert rec3["outcome"] == "FAILED:HARD_STOP" and sst3["hard_stop"]["status"] == 403


# ---------------------------------------------------------------- PIT
def test_each_point_is_available_at_max_of_fetch_and_end_plus_one_hour() -> None:
    end = datetime(2026, 10, 1, 10, tzinfo=UTC)
    assert S.point_available_at(end, end) == end + timedelta(hours=1)
    late = end + timedelta(days=3)
    assert S.point_available_at(end, late) == late
    assert timedelta(hours=1) <= S.PUBLICATION_LAG and "spätestens eine Stunde" in S.LAG_SOURCE


def test_daily_stamp_is_day_end_plus_one_hour_floored_at_the_read(tmp_path: Path) -> None:
    soon = datetime(2026, 10, 2, 22, 20, tzinfo=UTC)         # 20 min after 10-02 ended
    _rec, _sst, store = _collect(tmp_path, Getter(), clock=lambda: soon,
                                 now=datetime(2026, 10, 3, 0, 30, tzinfo=UTC))
    assert store["de_lu_load_mean|2026-10-02"]["published_time"] == "2026-10-02T23:00:00+00:00"
    later = datetime(2026, 10, 9, 8, tzinfo=UTC)
    _rec, _sst, store2 = _collect(tmp_path / "b", Getter(), clock=lambda: later)
    row = store2["de_lu_gen_gas|2026-10-01"]
    assert row["published_time"] == later.isoformat(timespec="seconds")
    assert row["published_basis"] == "first_read"
    assert row["rule_time"] == "2026-10-01T23:00:00+00:00"


def test_a_consumer_sees_only_stamped_rows_of_earlier_days(tmp_path: Path) -> None:
    later = datetime(2026, 10, 9, 8, tzinfo=UTC)
    _rec, _sst, store = _collect(tmp_path, Getter(), clock=lambda: later)
    sp = tmp_path / "store.json"
    sp.write_text(json.dumps(store), "utf-8")
    assert S.smard_asof(A, later - timedelta(seconds=1), sp)["status"] == "UNMEASURED"
    got = S.smard_asof(A, later, sp)
    assert got["series"]["de_lu_load_mean"]["period"] == "2026-10-02"
    assert got["credit"] == S.CREDIT
    # A decision on 2026-10-02 never sees 10-02 itself, even if stamped earlier.
    store["de_lu_load_mean|2026-10-02"]["published_time"] = "2026-10-02T00:00:00+00:00"
    sp.write_text(json.dumps(store), "utf-8")
    same_day = S.smard_asof(A, datetime(2026, 10, 2, 23, 59, tzinfo=UTC), sp)
    assert all(r["period"] < "2026-10-02" for r in same_day["series"].values())


def test_a_non_live_row_answers_no_values(tmp_path: Path, monkeypatch: Any) -> None:
    monkeypatch.setitem(S.SOURCE_POLICY_ROW[S.POLICY_KEY], "status", S.IDEAS_ONLY)
    got = S.smard_asof(A, NOW, tmp_path / "none.json")
    assert got["status"] == S.IDEAS_ONLY and got["series"] == {}


# ---------------------------------------------------------------- outcomes and cursors
def test_an_all_404_pass_is_failed_never_zero(tmp_path: Path) -> None:
    rec, _s, store = _collect(tmp_path, Getter(missing={"chart_data"}))
    assert rec["outcome"] == "FAILED:ALL_WINDOWS_404" and store == {}
    assert all(w["status"] == "UNMEASURED" for w in rec["unmeasured_windows"])


def test_a_missing_index_is_partial_and_names_the_region(tmp_path: Path) -> None:
    rec, _s, store = _collect(tmp_path, Getter(missing={"/DE/index_"}))
    assert rec["outcome"] == "PARTIAL:INDEX_404" and "DE" in rec["why"]
    assert store


def test_a_missing_filter_week_is_unmeasured_not_zero(tmp_path: Path) -> None:
    rec, _s, store = _collect(tmp_path, Getter(missing={"/4071/DE-LU/4071_"}))
    assert rec["outcome"] == "OK"
    assert [w["what"] for w in rec["unmeasured_windows"]] == [f"DE-LU 4071 week {WEEK}"]
    assert not any(k.startswith("de_lu_gen_gas|") for k in store)
    # The share needs every generation file read: a 404 leaves the total unknown, never a
    # gas-free share. Load and the other types are still published.
    assert not any(k.startswith("de_lu_ren_share|") for k in store)
    assert any(k.startswith("de_lu_gen_lignite|") for k in store)


def test_a_reread_with_nothing_new_is_unchanged(tmp_path: Path) -> None:
    rec, sst, store = _collect(tmp_path, Getter())
    assert rec["outcome"] == "OK" and rec["merge"]["added"] > 0
    assert sst["cursor"] == {"DE-LU": WEEK, "DE": WEEK}          # caught up: re-read recent
    rec2, _s, _st = _collect(tmp_path, Getter(), sst=sst, store=store)
    assert rec2["outcome"] == "UNCHANGED"


def test_a_budget_cut_is_partial_and_keeps_the_cursor(tmp_path: Path, monkeypatch: Any) -> None:
    clock = {"t": 0.0}

    class FakeTime:
        @staticmethod
        def monotonic() -> float:
            return clock["t"]

    def sleep(s: float) -> None:
        clock["t"] += s
    monkeypatch.setattr(S, "time", FakeTime)
    sst: dict[str, Any] = {"cursor": {"DE-LU": WEEK, "DE": WEEK - 1}}
    rec = S.collect(A, A.Paths(tmp_path / "desk"), S.make_source(A), sst, {}, NOW, fetch=True,
                    fixtures=None, deadline=S.MIN_INTERVAL_S * 15.5, getter=Getter(),
                    robots_getter=_robots(), sleep=sleep, clock=lambda: NOW)
    assert rec["outcome"] == "PARTIAL:BUDGET"                   # DE-LU read, DE owed
    assert rec["caught_up"] == {"DE-LU": True, "DE": False}
    assert sst["cursor"]["DE"] == WEEK - 1 and rec["parsed"] > 0


def test_a_pass_cut_before_any_window_completes_is_failed_budget(tmp_path: Path) -> None:
    rec, sst, _st = _collect(tmp_path, Getter(), deadline=float("-inf"))
    assert rec["outcome"] == "FAILED:BUDGET" and sst["cursor"]["DE-LU"] == WEEK


def test_a_first_pass_starts_at_the_week_containing_the_depth(tmp_path: Path) -> None:
    wk = 7 * 86_400_000
    stamps = [WEEK - wk * i for i in range(60)][::-1]
    g = Getter(stamps=stamps)
    rec, sst, _st = _collect(tmp_path, g, sst={})
    floor = int((NOW - timedelta(days=S.DEPTH_D)).timestamp() * 1000)
    first = max(t for t in stamps if t <= floor)
    weeks = [u for u in g.calls if "/410/DE-LU/410_" in u]
    assert weeks[0].endswith(f"_{first}.json") and weeks[-1].endswith(f"_{WEEK}.json")
    assert rec["caught_up"] == {"DE-LU": True, "DE": True}
    assert sst["cursor"]["DE-LU"] == WEEK


# ---------------------------------------------------------------- terms
def test_the_terms_row_is_live_on_verbatim_cc_by_clauses_with_attribution() -> None:
    row = S.policy()
    assert row["status"] == S.API_PERMITTED and S.live_input()
    cl = row["terms"]["clauses"]
    assert "licensed under a Creative Commons Attribution 4.0 International Licence" in \
        cl["data_use_cc_by"]
    assert "Market data visuals" in cl["data_use_cc_by"]
    assert "\"Electricity generation\", \"Electricity consumption\"" in cl["download_categories"]
    assert "'Bundesnetzagentur | SMARD.de'" in cl["data_use_attribution"]
    assert "spätestens eine Stunde" in cl["manual_p47_load_lag"]
    assert row["terms"]["checked_at"] == "2026-10-20"
    assert all(v.startswith("COVERED") for v in row["terms"]["scope"].values())
    assert row["missed_growth"]["delta_elogw"] == "UNMEASURED"
    assert row["hosts"] == (S.HOST,) and "automated access" in row["open_points"]
    assert "Bundesnetzagentur | SMARD.de" in S.CREDIT and "CC BY 4.0" in S.CREDIT


def test_a_live_pass_writes_the_axis_with_its_credit(tmp_path: Path) -> None:
    paths = A.Paths(tmp_path / "desk")
    rep = S.run_pass(A, paths, {}, NOW, fetch=False, fixtures=FIX, deadline=float("inf"),
                     donate=False)
    assert rep["outcome"] == "OK" and rep["terms"]["live_input"] is True
    assert rep["credit"] == S.CREDIT and rep["filters"]["410"].startswith("Stromverbrauch")
    axis = json.loads((paths.axes / f"alt_{S.SOURCE_ID}.json").read_text("utf-8"))
    assert axis["credit"] == S.CREDIT


def test_ideas_only_measures_but_never_donates_or_writes_live_series(tmp_path: Path,
                                                                     monkeypatch: Any) -> None:
    monkeypatch.setitem(S.SOURCE_POLICY_ROW[S.POLICY_KEY], "status", S.IDEAS_ONLY)
    calls: list[Any] = []

    def spy(*a: Any, **k: Any) -> dict[str, Any]:
        calls.append(a)
        return {"donated": 0}
    monkeypatch.setattr(A, "_donate", spy)
    paths = A.Paths(tmp_path / "desk")
    rep = S.run_pass(A, paths, {}, NOW, fetch=False, fixtures=FIX, deadline=float("inf"))
    assert rep["outcome"] == "OK" and rep["terms"]["live_input"] is False
    assert rep["terms"]["missed_growth"]["delta_elogw"] == "UNMEASURED"
    assert calls and calls[0][2] == []
    assert not (paths.axes / f"alt_{S.SOURCE_ID}.json").exists()


# ---------------------------------------------------------------- cells
def test_cells_map_to_the_entsoe_de_lu_instruments() -> None:
    src = S.make_source(A)
    assert src.instruments_for("de_lu_load_mean") == {"GER40": 1, "EURUSD": 1}
    assert src.instruments_for("de_lu_residual_load") == {"XNGUSD": 1}
    assert src.instruments_for("de_lu_gen_gas") == {"XNGUSD": 1}
    assert src.instruments_for("de_lu_ren_share") == {"XNGUSD": -1}
    assert src.instruments_for("de_load_mean") == {}             # DE is measured, not a cell


def test_cells_are_judged_by_the_canonical_tier_s_helper_and_carry_credit(
        tmp_path: Path, monkeypatch: Any) -> None:
    import numpy as np
    import pandas as pd

    from libs.research.release_gain import tier_s_t_required
    src = S.make_source(A)
    start = datetime(2024, 1, 1, tzinfo=UTC)
    idx = pd.date_range(start, periods=24 * 800, freq="h", tz="UTC")
    rng = np.random.default_rng(7)
    close = pd.Series(100 * np.exp(np.cumsum(rng.normal(0, 1e-3, len(idx)))), index=idx)
    monkeypatch.setattr(A, "_bars_close", lambda paths, sym: close)
    monkeypatch.setattr(A, "may_mint", lambda sym, family=A.DIRECT_FAMILY: True)
    pts = {"de_lu_residual_load": [
        {"available_time": (start + timedelta(days=7 * i)).isoformat(),
         "surprise_z": float(rng.normal())} for i in range(100)]}
    gains = S.gain_tests(A, A.Paths(tmp_path), src, pts)
    g = gains[f"{S.SOURCE_ID}|de_lu_residual_load|XNGUSD"]
    assert g["t_bar_judge"] == "libs.research.release_gain.tier_s_t_required"
    assert g["t_bar"] >= round(tier_s_t_required(int(g["n"])), 4)
    assert g["live_input"] is True
    assert "2.84" not in (DESK / "research" / "smard_power.py").read_text("utf-8")
    fake = {f"{S.SOURCE_ID}|de_lu_gen_gas|XNGUSD": {"verdict": "PASS", "ic": 0.2, "n": 90}}
    out = S.cells(A, src, fake, NOW)
    assert len(out) == 1 and out[0]["source"] == S.SOURCE_ID and out[0]["credit"] == S.CREDIT
    assert out[0]["provenance"]["terms_row"] == S.POLICY_KEY and out[0]["live_input"] is True


def test_alt_proxies_run_carries_the_smard_section(tmp_path: Path, monkeypatch: Any) -> None:
    paths = A.Paths(tmp_path / "desk")
    rep = A.run(paths, fixtures=FIX, donate=False, now=NOW, dry_run=True)
    sec = rep["smard_power"]
    assert sec["outcome"] == "OK" and sec["series"]["de_lu_residual_load"] == 5
    assert sec["terms"]["status"] == S.API_PERMITTED and sec["credit"] == S.CREDIT

    def boom(*a: Any, **k: Any) -> dict[str, Any]:
        raise RuntimeError("secret detail")
    monkeypatch.setattr(S, "run_pass", boom)
    rep2 = A._smard_pass(paths, {}, NOW, fetch=True, fixtures=None, deadline=float("inf"),
                         dry_run=True, donate=False)
    assert rep2["outcome"] == "FAILED:EXCEPTION" and "secret detail" not in json.dumps(rep2)
