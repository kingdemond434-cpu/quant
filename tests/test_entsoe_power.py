"""ENTSO-E load and generation per type (research/entsoe_power.py, registered in alt_proxies).

No network: every POST goes through an injected poster and robots.txt through an injected
getter. The token is a FAKE, and every test that could leak it scans what was written."""
from __future__ import annotations

import io
import json
import sys
import time
import urllib.error
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

FIX = ROOT / "tests" / "fixtures" / "alt_proxies"
FAKE = "fake-entsoe+token/abc=="          # carries +, / and = so every encoded form is tested
ENV = {E.KEY_NAME: FAKE}
NOW = datetime(2026, 10, 3, 12, tzinfo=UTC)
ACK_999 = (b'<?xml version="1.0" encoding="UTF-8"?><Acknowledgement_MarketDocument '
           b'xmlns="urn:iec62325.351:tc57wg16:451-1:acknowledgementdocument:7:0"><mRID>x</mRID>'
           b"<Reason><code>999</code><text>No matching data found for Data item ACTUAL_TOTAL_"
           b"LOAD_R3</text></Reason></Acknowledgement_MarketDocument>")
HTML = b"<!doctype html><html><head><title>Access denied</title></head><body>WAF</body></html>"


def _fx(slug: str, kind: str) -> bytes:
    return (FIX / f"entsoe_power.{slug}.{kind}.xml").read_bytes()


def _http(code: int, text: str = "") -> urllib.error.HTTPError:
    return urllib.error.HTTPError(f"https://web-api.tp.entsoe.eu/api?securityToken={FAKE}",
                                  code, f"refused {text}", {}, io.BytesIO(b""))  # type: ignore[arg-type]


class Poster:
    """Answers by data item and zone read from the POSTed document; `script` overrides."""

    def __init__(self, script: list[Any] | None = None) -> None:
        self.calls: list[tuple[str, bytes, dict[str, str]]] = []
        self.script = list(script) if script is not None else None

    def __call__(self, url: str, body: bytes, headers: dict[str, str]) -> tuple[bytes, str]:
        self.calls.append((url, body, dict(headers)))
        if self.script is not None:
            item = self.script.pop(0)
            if isinstance(item, BaseException):
                raise item
            return item, "text/xml"
        slug = "de_lu" if b"10Y1001A1001A82H" in body else "fr"
        kind = "load" if b"A65" in body else "gen"
        return _fx(slug, kind), "text/xml"


def _robots(body: bytes = b"User-agent: *\nAllow: /\n") -> Any:
    def get(url: str) -> tuple[bytes, str]:
        assert url.endswith("/robots.txt")
        return body, "text/plain"
    return get


def _collect(tmp: Path, poster: Poster, *, sst: dict[str, Any] | None = None,
             store: dict[str, Any] | None = None, environ: dict[str, str] | None = None,
             deadline: float = float("inf"), clock: Any = None, getter: Any = None,
             now: datetime = NOW) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    sst = {"cursor": {"DE-LU": "2026-10-01", "FR": "2026-10-01"}} if sst is None else sst
    store = {} if store is None else store
    paths = A.Paths(tmp / "desk")
    rec = E.collect(A, paths, E.make_source(A), sst, store, now, fetch=True, fixtures=None,
                    deadline=deadline, poster=poster, getter=getter or _robots(),
                    environ=ENV if environ is None else environ, sleep=lambda s: None,
                    clock=clock or (lambda: now))
    return rec, sst, store


def _no_token_written(tmp: Path) -> None:
    for p in tmp.rglob("*"):
        if p.is_file():
            raw = p.read_bytes()
            for form in E._forms((FAKE,)):
                assert form.encode() not in raw, f"token form leaked into {p}"


# ---------------------------------------------------------------- parse and fold
def test_fixtures_parse_and_fold_complete_local_days_only() -> None:
    load, gen = E.parse_answer(_fx("de_lu", "load")), E.parse_answer(_fx("de_lu", "gen"))
    assert load.kind == gen.kind == "doc"
    assert {s.psr for s in gen.series} >= {"B04", "B16", "B18", "B19"}
    assert any(s.consumption for s in gen.series)              # pumped-storage load is flagged
    rows = E.fold_days("de_lu", load, gen, [date(2026, 9, 30), date(2026, 10, 1),
                                            date(2026, 10, 2), date(2026, 10, 3)],
                       A.cet_offset_h)
    days = {d for _s, d, _v in rows}
    assert days == {date(2026, 10, 1), date(2026, 10, 2)}       # the edges are not complete
    names = {s for s, _d, _v in rows}
    assert names == {"de_lu_load_mean", "de_lu_gen_gas", "de_lu_ren_share",
                     "de_lu_residual_load"}
    assert "de_lu_gen_nuclear" not in names                     # absent is absent, never zero


def test_a_production_type_covering_part_of_a_day_makes_generation_incomplete() -> None:
    gen = E.parse_answer(_fx("fr", "gen"))
    cut = E.Answer("doc", series=tuple(
        E.Series(s.psr, s.consumption, s.points[:-3] if s.psr == "B14" else s.points)
        for s in gen.series))
    rows = E.fold_days("fr", E.parse_answer(_fx("fr", "load")), cut,
                       [date(2026, 10, 1), date(2026, 10, 2)], A.cet_offset_h)
    by_day = {(s, d) for s, d, _v in rows}
    assert ("fr_load_mean", date(2026, 10, 2)) in by_day
    assert ("fr_gen_nuclear", date(2026, 10, 2)) not in by_day
    assert ("fr_gen_nuclear", date(2026, 10, 1)) in by_day


def test_ack_html_and_dtd_bodies_are_classified_and_never_parsed() -> None:
    ack = E.parse_answer(ACK_999)
    assert (ack.kind, ack.reason) == ("ack", "999")
    assert E.parse_answer(HTML).kind == "not_xml"
    bomb = b'<?xml version="1.0"?><!DOCTYPE x [<!ENTITY a "aaaa">]><x>&a;</x>'
    assert E.parse_answer(bomb).kind == "not_xml"


# ---------------------------------------------------------------- the key
def test_the_token_travels_only_in_the_security_token_header(tmp_path: Path) -> None:
    p = Poster()
    rec, _sst, _store = _collect(tmp_path, p)
    assert rec["outcome"] == "OK", rec
    assert len(p.calls) == 4                                    # 2 zones x (load, gen)
    for url, body, headers in p.calls:
        assert url == E.API_URL and "?" not in url
        assert headers[E.TOKEN_HEADER] == FAKE
        for form in E._forms((FAKE,)):
            assert form.encode() not in body and form not in url
        assert "securityToken" not in url
        assert "quant-mt5-research-desk" in headers["User-Agent"]
        assert b"<type>A59</type>" in body and b"StatusRequest_MarketDocument" in body


def test_a_missing_token_is_needs_key_and_sends_nothing(tmp_path: Path) -> None:
    p = Poster()
    rec, _sst, _store = _collect(tmp_path, p, environ={})
    assert rec["outcome"] == f"NEEDS_KEY:{E.KEY_NAME}"
    assert rec["missed_growth"]["delta_elogw"] == "UNMEASURED"
    assert p.calls == []


def test_a_redirect_is_refused_never_followed() -> None:
    import urllib.request
    h = E._NoRedirect()
    req = urllib.request.Request(E.API_URL, data=b"x", headers={E.TOKEN_HEADER: FAKE})
    with pytest.raises(E.RedirectRefused):
        h.redirect_request(req, io.BytesIO(b""), 302, "Found", {}, "https://elsewhere.example/")


def test_a_redirect_answer_fails_the_pass_without_a_hold(tmp_path: Path) -> None:
    redirect = E.RedirectRefused(E.API_URL, 302, "redirect refused", {}, io.BytesIO(b""))  # type: ignore[arg-type]
    rec, sst, _store = _collect(tmp_path, Poster([redirect]))
    assert rec["outcome"] == "FAILED:REDIRECT_REFUSED"
    assert "hard_stop" not in sst


# ---------------------------------------------------------------- holds
@pytest.mark.parametrize("code", [401, 403, 429])
def test_a_refusal_is_held_for_a_person_in_the_shared_shape(code: int, tmp_path: Path) -> None:
    rec, sst, _store = _collect(tmp_path, Poster([_http(code, FAKE)]))
    assert rec["outcome"] == "FAILED:HARD_STOP"
    h = sst["hard_stop"]
    assert h["key"] == f"site:{E.HOST}" and h["host"] == E.HOST and h["status"] == code
    assert h["verdict"] == E.BLOCK_VERDICT[code]
    assert h["released_by"] is None and h["released_at"] is None
    assert isinstance(h["held_at"], float)
    assert h["missed_growth"]["delta_elogw"] == "UNMEASURED"
    assert "recheck_after_ts" not in h
    assert FAKE not in json.dumps(rec) and FAKE not in json.dumps(sst)
    # The next pass, a year later, still sends nothing: no clock releases it.
    p = Poster()
    rec2, _s, _st = _collect(tmp_path, p, sst=sst, now=NOW + timedelta(days=365))
    assert rec2["outcome"] == "HELD:HARD_STOP" and p.calls == []
    # A person's release lets the following pass run.
    sst["hard_stop"]["released_by"] = "auditor"
    rec3, _s, _st = _collect(tmp_path, Poster(), sst=sst)
    assert rec3["outcome"] == "OK"


def test_a_waf_page_is_a_hard_stop(tmp_path: Path) -> None:
    rec, sst, _store = _collect(tmp_path, Poster([HTML]))
    assert rec["outcome"] == "FAILED:WAF"
    assert sst["hard_stop"]["status"] == "WAF"
    assert sst["hard_stop"]["verdict"] == "METHOD_BLOCKED"


def test_robots_decides_every_pass(tmp_path: Path) -> None:
    p = Poster()
    rec, _s, _st = _collect(tmp_path, p, getter=_robots(b"User-agent: *\nDisallow: /api\n"))
    assert rec["outcome"] == "FAILED:ROBOTS_DISALLOW" and p.calls == []

    def unreadable(url: str) -> tuple[bytes, str]:
        raise OSError("down")
    p2 = Poster()
    rec2, _s, _st = _collect(tmp_path, p2, getter=unreadable)
    assert rec2["outcome"] == "FAILED:ROBOTS_UNREADABLE" and p2.calls == []

    def forbidden(url: str) -> tuple[bytes, str]:
        raise _http(403)
    rec3, sst3, _st = _collect(tmp_path, Poster(), getter=forbidden)
    assert rec3["outcome"] == "FAILED:HARD_STOP" and sst3["hard_stop"]["status"] == 403


# ---------------------------------------------------------------- PIT
def test_each_point_is_available_at_max_of_fetch_and_end_plus_one_hour() -> None:
    end = datetime(2026, 10, 1, 10, tzinfo=UTC)
    assert E.point_available_at("load", end, end) == end + timedelta(hours=1)
    late = end + timedelta(days=3)
    assert E.point_available_at("gen", end, late) == late


def test_daily_stamp_is_day_end_plus_one_hour_floored_at_the_read(tmp_path: Path) -> None:
    # Read 20 minutes after local day 2026-10-02 ended (22:00Z): the deadline wins.
    soon = datetime(2026, 10, 2, 22, 20, tzinfo=UTC)
    _rec, _sst, store = _collect(tmp_path, Poster(), clock=lambda: soon,
                                 now=datetime(2026, 10, 3, 0, 30, tzinfo=UTC))
    row = store["de_lu_load_mean|2026-10-02"]
    assert row["published_time"] == "2026-10-02T23:00:00+00:00"
    # Read days later: the read wins, and the stated deadline is kept beside it.
    later = datetime(2026, 10, 9, 8, tzinfo=UTC)
    _rec, _sst, store2 = _collect(tmp_path / "b", Poster(), clock=lambda: later)
    row2 = store2["fr_load_mean|2026-10-01"]
    assert row2["published_time"] == later.isoformat(timespec="seconds")
    assert row2["published_basis"] == "first_read"
    assert row2["rule_time"] == "2026-10-01T23:00:00+00:00"


def test_a_cell_cannot_see_a_value_before_its_stamp(tmp_path: Path) -> None:
    later = datetime(2026, 10, 9, 8, tzinfo=UTC)
    _rec, _sst, store = _collect(tmp_path, Poster(), clock=lambda: later)
    sp = tmp_path / "store.json"
    sp.write_text(json.dumps(store), "utf-8")
    before = A.series_asof(E.SOURCE_ID, later - timedelta(seconds=1), sp)
    assert before["status"] == "UNMEASURED"
    after = A.series_asof(E.SOURCE_ID, later, sp)
    assert after["series"]["de_lu_load_mean"]["period"] == "2026-10-02"
    # The consumer refuses IDEAS_ONLY data outright.
    assert E.entsoe_asof(A, later, sp)["status"] == E.IDEAS_ONLY


# ---------------------------------------------------------------- outcomes
def test_an_all_empty_pass_is_failed_never_zero(tmp_path: Path) -> None:
    rec, _s, store = _collect(tmp_path, Poster([ACK_999] * 4))
    assert rec["outcome"] == "FAILED:ALL_WINDOWS_EMPTY" and store == {}
    assert all(w["status"] == "UNMEASURED" for w in rec["unmeasured_windows"])


def test_another_acknowledgement_fails_with_its_reason(tmp_path: Path) -> None:
    bad = ACK_999.replace(b"<code>999</code>", b"<code>A04</code>")
    rec, _s, _st = _collect(tmp_path, Poster([bad]))
    assert rec["outcome"] == "FAILED:ACK_A04"


def test_a_reread_with_nothing_new_is_unchanged(tmp_path: Path) -> None:
    rec, sst, store = _collect(tmp_path, Poster())
    assert rec["outcome"] == "OK" and rec["merge"]["added"] > 0
    sst["cursor"] = {"DE-LU": "2026-10-01", "FR": "2026-10-01"}
    rec2, _s, _st = _collect(tmp_path, Poster(), sst=sst, store=store)
    assert rec2["outcome"] == "UNCHANGED"


def test_a_budget_cut_is_partial_and_keeps_the_cursor(tmp_path: Path) -> None:
    class Slow(Poster):
        def __call__(self, url: str, body: bytes, headers: dict[str, str]) -> tuple[bytes, str]:
            out = super().__call__(url, body, headers)
            self.t = time.monotonic()
            return out
    p = Slow()
    deadline = time.monotonic() + E.MIN_INTERVAL_S * 2.5      # room for DE-LU only
    rec, sst, _st = _collect(tmp_path, p, deadline=deadline)
    assert rec["outcome"] == "PARTIAL:BUDGET"
    assert rec["caught_up"] == {"DE-LU": True, "FR": False}
    assert sst["cursor"]["FR"] == "2026-10-01"


def test_a_pass_cut_before_any_window_completes_is_failed_budget(tmp_path: Path) -> None:
    rec, sst, _st = _collect(tmp_path, Poster(), deadline=float("-inf"))
    assert rec["outcome"] == "FAILED:BUDGET"
    assert sst["cursor"]["DE-LU"] == "2026-10-01"


def test_the_cursor_walks_whole_local_day_windows_from_depth(tmp_path: Path) -> None:
    p = Poster([ACK_999] * 400)
    rec, sst, _st = _collect(tmp_path, p, sst={})
    first = p.calls[0][1].decode()
    start = (NOW - timedelta(days=E.DEPTH_D)).date()
    a = E.day_bounds(start, A.cet_offset_h)[0].strftime("%Y-%m-%dT%H:%MZ")
    assert f"<attributeValue>{a}/" in first
    n_windows = -(-((NOW - timedelta(days=1)).date() - start).days // E.CHUNK_D)
    assert len(p.calls) == 2 * 2 * (n_windows + (1 if ((NOW - timedelta(days=1)).date()
                                                      - start).days % E.CHUNK_D == 0 else 0))
    assert rec["caught_up"] == {"DE-LU": True, "FR": True}
    y = (NOW - timedelta(days=1)).date()
    assert sst["cursor"]["FR"] == (y - timedelta(days=E.RECENT_D - 1)).isoformat()


# ---------------------------------------------------------------- the token never lands
def test_no_written_artifact_log_or_exception_carries_the_token(tmp_path: Path) -> None:
    echo = _fx("de_lu", "load").replace(b"<mRID>fixture</mRID>",
                                        f"<mRID>{FAKE}</mRID>".encode())
    p = Poster([echo, _fx("de_lu", "gen"), _fx("fr", "load"), _fx("fr", "gen")])
    paths = A.Paths(tmp_path / "desk")
    state: dict[str, Any] = {"sources": {E.SOURCE_ID: {"cursor": {"DE-LU": "2026-10-01",
                                                                 "FR": "2026-10-01"}}}}
    rep = E.run_pass(A, paths, state, NOW, fetch=True, fixtures=None, deadline=float("inf"),
                     poster=p, getter=_robots(), environ=ENV, sleep=lambda s: None,
                     clock=lambda: NOW, donate=False)
    assert rep["outcome"] == "OK"
    (tmp_path / "report.json").write_text(json.dumps(rep, default=str), "utf-8")
    (tmp_path / "state.json").write_text(json.dumps(state, default=str), "utf-8")
    # A refusal whose URL and reason carry the token, and a transport error quoting it.
    for exc in (_http(403, FAKE), OSError(f"reset while sending {FAKE}")):
        st: dict[str, Any] = {"cursor": {"DE-LU": "2026-10-01"}}
        rec = E.collect(A, paths, E.make_source(A), st, {}, NOW, fetch=True, fixtures=None,
                        deadline=float("inf"), poster=Poster([exc]), getter=_robots(),
                        environ=ENV, sleep=lambda s: None, clock=lambda: NOW)
        assert rec["outcome"].startswith("FAILED")
        (tmp_path / f"rec_{type(exc).__name__}.json").write_text(json.dumps([rec, st]), "utf-8")
    _no_token_written(tmp_path)
    assert any((paths.vault / f"alt_{E.SOURCE_ID}").iterdir())


def test_the_registered_producer_never_lets_an_exception_text_out(tmp_path: Path,
                                                                  monkeypatch: Any) -> None:
    def boom(*a: Any, **k: Any) -> dict[str, Any]:
        raise RuntimeError(f"header {FAKE}")
    monkeypatch.setattr(E, "run_pass", boom)
    rep = A._entsoe_pass(A.Paths(tmp_path), {}, NOW, fetch=True, fixtures=None,
                         deadline=float("inf"), dry_run=True, donate=False)
    assert rep["outcome"] == "FAILED:EXCEPTION" and FAKE not in json.dumps(rep)


# ---------------------------------------------------------------- terms
def test_the_terms_row_is_ideas_only_with_verbatim_clauses_and_attribution() -> None:
    row = E.policy()
    assert row["status"] == E.IDEAS_ONLY and not E.live_input()
    cl = row["terms"]["clauses"]
    assert "for any purpose whatsoever" in cl["use_3_1"]
    assert "seek the prior agreement" in cl["prejudice_3_1"]
    assert cl["api_header"] == "Token has be present in http header. Key is SECURITY_TOKEN."
    assert row["terms"]["checked_at"] == "2026-10-20"
    assert all(v.startswith("ABSENT") for v in row["terms"]["free_list_membership"].values())
    assert row["missed_growth"]["delta_elogw"] == "UNMEASURED"
    assert row["hosts"] == (E.HOST,) and row["key_env"] == (E.KEY_NAME,)
    assert "ENTSO-E Transparency Platform" in E.CREDIT


def test_ideas_only_measures_but_never_donates_or_writes_live_series(tmp_path: Path,
                                                                     monkeypatch: Any) -> None:
    calls: list[Any] = []

    def spy(*a: Any, **k: Any) -> dict[str, Any]:
        calls.append(a)
        return {"donated": 0}
    monkeypatch.setattr(A, "_donate", spy)
    paths = A.Paths(tmp_path / "desk")
    rep = E.run_pass(A, paths, {}, NOW, fetch=False, fixtures=FIX, deadline=float("inf"))
    assert rep["outcome"] == "OK" and rep["terms"]["status"] == E.IDEAS_ONLY
    assert rep["terms"]["missed_growth"]["delta_elogw"] == "UNMEASURED"
    assert rep["credit"] == E.CREDIT
    assert calls and calls[0][2] == []                          # nothing offered to donate
    assert not (paths.axes / f"alt_{E.SOURCE_ID}.json").exists()
    assert not paths.series.exists() or not any(paths.series.glob("*entsoe*"))


def test_a_live_row_writes_the_axis_with_its_credit(tmp_path: Path, monkeypatch: Any) -> None:
    monkeypatch.setitem(E.SOURCE_POLICY_ROW[E.POLICY_KEY], "status", "API_PERMITTED")
    assert E.live_input()
    paths = A.Paths(tmp_path / "desk")
    rep = E.run_pass(A, paths, {}, NOW, fetch=False, fixtures=FIX, deadline=float("inf"),
                     donate=False)
    assert rep["terms"]["live_input"] is True
    axis = json.loads((paths.axes / f"alt_{E.SOURCE_ID}.json").read_text("utf-8"))
    assert axis["credit"] == E.CREDIT


# ---------------------------------------------------------------- cells
def test_cells_map_to_the_named_instruments() -> None:
    src = E.make_source(A)
    assert src.instruments_for("de_lu_residual_load") == {"XNGUSD": 1}
    assert src.instruments_for("fr_gen_nuclear") == {"XNGUSD": -1}
    assert src.instruments_for("de_lu_load_mean") == {"GER40": 1, "EURUSD": 1}
    assert src.instruments_for("fr_load_mean") == {"FRA40": 1, "EURUSD": 1}
    syms = {s for m in E.SERIES_INSTRUMENTS.values() for s in m}
    assert syms == {"XNGUSD", "GER40", "FRA40", "EURUSD"}


def test_cells_are_judged_by_the_canonical_tier_s_helper(tmp_path: Path,
                                                         monkeypatch: Any) -> None:
    import numpy as np
    import pandas as pd

    from libs.research.release_gain import tier_s_t_required
    src = E.make_source(A)
    start = datetime(2024, 1, 1, tzinfo=UTC)
    idx = pd.date_range(start, periods=24 * 800, freq="h", tz="UTC")
    rng = np.random.default_rng(7)
    close = pd.Series(100 * np.exp(np.cumsum(rng.normal(0, 1e-3, len(idx)))), index=idx)
    monkeypatch.setattr(A, "_bars_close", lambda paths, sym: close)
    monkeypatch.setattr(A, "may_mint", lambda sym, family=A.DIRECT_FAMILY: True)
    pts = {"de_lu_residual_load": [
        {"available_time": (start + timedelta(days=7 * i)).isoformat(),
         "surprise_z": float(rng.normal())} for i in range(100)]}
    gains = E.gain_tests(A, A.Paths(tmp_path), src, pts)
    g = gains[f"{E.SOURCE_ID}|de_lu_residual_load|XNGUSD"]
    assert g["t_bar_judge"] == "libs.research.release_gain.tier_s_t_required"
    assert g["t_bar"] is not None and g["t_bar"] >= tier_s_t_required(int(g["n"])) - 1e-9
    assert g["live_input"] is False
    text = (DESK / "research" / "entsoe_power.py").read_text("utf-8")
    assert "2.84" not in text                                   # no bare bar literal


def test_alt_proxies_fixture_run_carries_the_entsoe_section(tmp_path: Path) -> None:
    paths = A.Paths(tmp_path / "desk")
    rep = A.run(paths, fixtures=FIX, donate=False, now=NOW, dry_run=True)
    sec = rep["entsoe_power"]
    assert sec["outcome"] == "OK" and sec["series"]["de_lu_residual_load"] == 2
    assert sec["terms"]["status"] == E.IDEAS_ONLY
    assert sec["key"]["placement"] == "header SECURITY_TOKEN"
