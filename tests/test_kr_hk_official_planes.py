"""The Korea and Hong Kong official planes (asia directive PARTS X / XI, 2026-10-06).

BOK ECOS and HKMA Open API rows of `alt_proxies` parse their documented wire formats into PIT
series carrying the five alpha objects; the KRX and HKEX lanes are refused on their own terms and
never fetched; one ECOS key name is canonical; the Korea department registers nothing it cannot
run; and the department loop (`global_research_os`) reads the planes through each pack's miners.

Fixtures are SYNTHETIC values in the documented format (tests/fixtures/alt_proxies/
README_kr_hk_planes.md); nothing here is a measurement.
"""
from __future__ import annotations

import json
import sys
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest

ROOT = Path(__file__).resolve().parents[1]
DESK = ROOT / "desks" / "mt5"
for _p in (str(ROOT), str(DESK), str(DESK / "research")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from libs.data import key_aliases  # noqa: E402
from research import alt_proxies as A  # noqa: E402

FIX = ROOT / "tests" / "fixtures" / "alt_proxies"
NOW = datetime(2026, 9, 30, 12, tzinfo=UTC)
PLANE_IDS = tuple(s.id for s in A.KR_HK_PLANE_SOURCES)


def _obs(sid: str) -> list[A.Obs]:
    parse = A.BY_ID[sid].parse
    assert parse is not None
    return parse((FIX / f"{sid}.json").read_bytes(), A.Ctx(fetched_at=NOW))


def _fixture_pass(tmp_path: Path) -> A.Paths:
    paths = A.Paths(tmp_path / "desk")
    A.run(paths, fixtures=FIX, donate=False, now=NOW)
    return paths


# ---------------------------------------------------------------------------- parsing
def test_ecos_rows_parse_by_cycle() -> None:
    base = {(o.series, o.period): o.value for o in _obs("kr_ecos_base_rate")}
    assert base[("base_rate", date(2026, 8, 27))] == pytest.approx(2.25)
    res = {o.period for o in _obs("kr_ecos_fx_reserves")}
    assert date(2026, 8, 31) in res                         # YYYYMM -> month end
    assert A.make_ecos_parser("x")(b'{"RESULT":{"CODE":"INFO-200","MESSAGE":"no data"}}',
                                   A.Ctx()) == []


def test_hkma_records_carry_currency_board_semantics() -> None:
    got = {(o.series, o.period): o.value for o in _obs("hk_hkma_interbank_liquidity")}
    assert got[("aggregate_balance_hkd_mn", date(2026, 8, 27))] == pytest.approx(54123)
    assert got[("cu_forex_trans_t1_hkd_mn", date(2026, 8, 25))] == pytest.approx(-1570)
    hib = {(o.series, o.period): o.value for o in _obs("hk_hkma_hibor_fixing")}
    spread = hib[("hibor_3m_on_spread", date(2026, 8, 27))]
    assert spread == pytest.approx(hib[("hibor_3m", date(2026, 8, 27))]
                                   - hib[("hibor_on", date(2026, 8, 27))])
    assert A.parse_hkma_liquidity(b'{"header":{"success":false},"result":{}}', A.Ctx()) == []


def test_hkma_never_freezes_today() -> None:
    ctx = A.Ctx(fetched_at=datetime(2026, 8, 27, 9, tzinfo=UTC))
    obs = A.parse_hkma_monetary_base((FIX / "hk_hkma_monetary_base.json").read_bytes(), ctx)
    assert obs and max(o.period for o in obs) < date(2026, 8, 27)


def test_hkma_requests_page_once_backfilled() -> None:
    src = A.BY_ID["hk_hkma_hibor_fixing"]
    state: dict[str, Any] = {}
    first = A.requests_for(src, NOW, state)
    assert len(first) == A.HKMA_BACKFILL_PAGES and "segment=hibor.fixing&pagesize=" in first[0].url
    assert all("sortby=end_of_day" in r.url for r in first)
    assert len(A.requests_for(src, NOW, {"full_done": True})) == 1


def test_ecos_url_fills_dates_and_key_is_redacted(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ECOS_API_KEY", "sekret")
    src = A.BY_ID["kr_ecos_base_rate"]
    (req,) = A.requests_for(src, NOW, {})
    assert "/20260930/0101000" in req.url and "{" not in req.url
    assert "sekret" not in A._redact(req.url, src)


# ---------------------------------------------------------------------------- the five objects
def test_points_carry_level_change_acceleration_surprise_and_s25_names(tmp_path: Path) -> None:
    src = A.BY_ID["hk_hkma_hibor_fixing"]
    store: dict[str, Any] = {}
    A.merge_vintages(store, src, _obs(src.id), NOW)
    pts = A.build_points(src, store)["hibor_1m"]
    p2, p1, p0 = pts[2], pts[1], pts[0]
    assert p1["delta"] == pytest.approx(p1["value"] - p0["value"])
    assert p2["acceleration"] == pytest.approx(p2["delta"] - p1["delta"])
    for k in ("knowable_at", "publication_time", "received_at", "expected_value",
              "raw_surprise", "percentile", "revision_of", "source_id", "metric"):
        assert k in p2
    assert p2["knowable_at"] == p2["available_time"]
    # the first print revises nothing: no revision_delta and no revision_of on it, ever
    later = datetime(2026, 10, 2, tzinfo=UTC)
    A.merge_vintages(store, src, [A.Obs("hibor_1m", date(2026, 8, 27), 9.0)], later)
    first = next(p for p in A.build_points(src, store)["hibor_1m"] if p["d"] == "2026-08-27")
    assert first["value"] != 9.0
    assert first["revision_delta"] is None and first["revision_of"] is None
    assert first["revision_time"] is None
    # the revision is its own vintage, knowable only from the instant it was seen
    (rev,) = A.revision_points(src, store)["hibor_1m"]
    assert rev["d"] == "2026-08-27" and rev["value"] == 9.0
    assert rev["knowable_at"] == rev["available_time"] == later.isoformat(timespec="seconds")
    assert rev["revision_delta"] == pytest.approx(9.0 - first["value"])
    assert rev["revision_of"] == first["vintage_id"] and rev["vintage_n"] == 1


def _jan_store() -> tuple[A.Source, dict[str, Any]]:
    """One point for 2026-01-05, published and first seen 01-06; a revision first seen 03-01."""
    src = A.BY_ID["hk_hkma_hibor_fixing"]
    store: dict[str, Any] = {}
    A.merge_vintages(store, src, [A.Obs("hibor_1m", date(2026, 1, 5), 3.0)],
                     datetime(2026, 1, 6, 6, tzinfo=UTC))
    A.merge_vintages(store, src, [A.Obs("hibor_1m", date(2026, 1, 5), 3.5)],
                     datetime(2026, 3, 1, tzinfo=UTC))
    A.merge_vintages(store, src, [A.Obs("hibor_1m", date(2026, 1, 5), 3.25)],
                     datetime(2026, 4, 1, tzinfo=UTC))
    return src, store


def test_a_revision_first_seen_in_march_is_invisible_in_february() -> None:
    src, store = _jan_store()
    pts = A.build_points(src, store)
    revs = A.revision_points(src, store)
    feb = datetime(2026, 2, 28, 23, 59, tzinfo=UTC)
    seen = {**A.as_of(pts, feb), **{f"{k}#rev": v for k, v in A.as_of(revs, feb).items()}}
    assert seen["hibor_1m"][0]["value"] == 3.0                 # the first print is knowable
    assert all(p["revision_delta"] is None for p in seen["hibor_1m"])
    assert "hibor_1m#rev" not in seen                           # the 03-01 revision is not
    mar = A.as_of(revs, datetime(2026, 3, 1, tzinfo=UTC))["hibor_1m"]
    assert [p["value"] for p in mar] == [3.5]


def test_every_revision_vintage_is_kept_and_differenced_on_its_predecessor() -> None:
    src, store = _jan_store()
    (row,) = store.values()
    assert [v["value"] for v in row["vintages"]] == [3.5, 3.25]          # appended, never lost
    assert row["value_first"] == 3.0 and row["first_seen_at"].startswith("2026-01-06")
    r1, r2 = A.revision_points(src, store)["hibor_1m"]
    assert r1["revision_delta"] == pytest.approx(0.5)
    assert r1["knowable_at"].startswith("2026-03-01")
    assert r2["revision_delta"] == pytest.approx(-0.25)
    assert r2["knowable_at"].startswith("2026-04-01")
    assert r2["revision_of"] == r1["vintage_id"] and r2["vintage_n"] == 2
    # a row written before vintages existed keeps its one recorded revision, at its own stamp
    legacy = {"k": {"series": "hibor_1m", "period": "2026-01-05", "value_first": 3.0,
                    "value_last": 3.25, "first_seen_at": "2026-01-06T06:00:00+00:00",
                    "published_time": "2026-01-06T04:00:00+00:00",
                    "revision_time": "2026-04-01T00:00:00+00:00", "n_revisions": 2}}
    (lr,) = A.revision_points(src, legacy)["hibor_1m"]
    assert lr["knowable_at"] == "2026-04-01T00:00:00+00:00" and lr["reconstructed"]


def test_release_rules_are_late_biased() -> None:
    for sid in PLANE_IDS:
        t = A.BY_ID[sid].rule(date(2026, 8, 27))
        assert t > datetime(2026, 8, 27, tzinfo=UTC), sid
    assert A.BY_ID["hk_hkma_hibor_fixing"].rule(date(2026, 8, 27)).hour >= 4   # after 11:15 HKT


def test_release_rules_never_land_on_a_weekend_or_a_local_holiday() -> None:
    # Friday 2026-09-04: a T+1 rule landed on Saturday -- look-ahead for the Sunday FX open.
    fri = date(2026, 9, 4)
    for sid in ("hk_hkma_interbank_liquidity", "hk_hkma_monetary_base", "kr_ecos_call_rate"):
        t = A.BY_ID[sid].rule(fri)
        assert t.date() == date(2026, 9, 7) and t.weekday() == 0, sid
    # HK National Day (Thu 2026-10-01): a 09-30 print rolls past it to Friday 10-02
    assert A.BY_ID["hk_hkma_interbank_liquidity"].rule(date(2026, 9, 30)).date() == date(
        2026, 10, 2)
    # Korea: Chuseok (09-24/25) then the weekend -- a 09-23 call-rate print waits for 09-28;
    # 2026-10-05 is the National Foundation Day substitute, so a Friday 10-02 print waits to 10-06
    assert A.BY_ID["kr_ecos_call_rate"].rule(date(2026, 9, 23)).date() == date(2026, 9, 28)
    assert A.BY_ID["kr_ecos_call_rate"].rule(date(2026, 10, 2)).date() == date(2026, 10, 6)
    # every plane row, every day of a year: never a weekend, never a tabulated holiday
    for sid in PLANE_IDS:
        rule = A.BY_ID[sid].rule
        cal = rule.calendar  # type: ignore[attr-defined]
        assert cal in ("KR", "HK"), sid
        d = date(2026, 1, 1)
        while d.year == 2026:
            t = rule(d)
            closed = A._closed_days(cal, t.year) or frozenset()
            assert t.weekday() < 5 and t.date().isoformat() not in closed, (sid, d)
            d += timedelta(days=1)


def test_without_a_calendar_the_stamp_is_never_before_first_seen(
        monkeypatch: pytest.MonkeyPatch) -> None:
    src = A.BY_ID["hk_hkma_hibor_fixing"]
    monkeypatch.setattr(A, "_closed_days", lambda cal, year: None)   # no calendar at all
    assert not A.release_calendar_known("HK", 2031)
    seen = datetime(2031, 6, 20, 9, tzinfo=UTC)
    store: dict[str, Any] = {}
    A.merge_vintages(store, src, [A.Obs("hibor_1m", date(2031, 6, 2), 4.0)], seen)
    (row,) = store.values()
    assert row["published_time"] == seen.isoformat(timespec="seconds")
    assert row["published_basis"] == "first_seen_no_calendar"


# ---------------------------------------------------------------------------- terms and keys
def test_plane_terms_are_quoted_or_fenced_and_refused_hosts_are_not_sources() -> None:
    for sid in PLANE_IDS:
        ev = A.KR_HK_TERMS_EVIDENCE[sid]
        assert ev["terms_url"].startswith("https://") and ev["checked_at"] == "2026-10-06"
        if sid.startswith("kr_ecos_"):
            # the ECOS terms were never read: fenced, never confirmed without a quoted clause
            assert A.BY_ID[sid].terms == "to_confirm", sid
            assert A.status_of(A.BY_ID[sid]) == "BLOCKED_ON_TERMS:to_confirm"
        else:
            assert A.BY_ID[sid].terms == "confirmed", sid
            assert "commercial" in ev["terms_quote"] and ev["listing_url"].startswith(
                "https://apidocs.hkma.gov.hk/")
    assert A.BY_ID["kr_bok_card_spend"].terms == "to_confirm"
    assert A.terms_gate("https://ecos.bok.or.kr/api/StatisticSearch/x")[0] == "to_confirm"
    # each HKMA row cites its OWN dataset's listing, not the end-of-period rate table
    listings = {A.KR_HK_TERMS_EVIDENCE[s]["listing_url"] for s in PLANE_IDS
                if s.startswith("hk_hkma_")}
    assert len(listings) == 3 and not any("endperiod" in u for u in listings)
    for sid in ("kr_krx_market_data", "hk_hkex_stock_connect"):
        assert sid not in A.BY_ID                              # no fetcher exists to run
        assert A.KR_HK_TERMS_EVIDENCE[sid]["decision"] == "refused"
        assert A.KR_HK_REFUSED[sid]["status"] == "BLOCKED_ON_TERMS:refused"
        assert A.terms_gate(sid)[0] == "refused"
    assert set(A.KR_HK_REFUSED["kr_krx_market_data"]["directive_rows"]) == {
        "ASIA-0465", "ASIA-0466", "ASIA-0467"}
    assert all(v.startswith("BLOCKED") for v in
               A.KR_HK_REFUSED["kr_krx_market_data"]["directive_rows"].values())


def test_every_confirmed_gate_row_quotes_its_permitting_clause() -> None:
    for ref, (state, _why) in A.GATE_TERMS.items():
        ev = A.GATE_TERMS_EVIDENCE[ref]
        assert ev["decision"] == state and ev["checked_at"], ref
        if state == "confirmed":
            assert ev["terms_url"].startswith("https://") and not ev["terms_quote"].startswith(
                "("), ref


def test_one_ecos_key_name_with_the_old_name_as_alias(monkeypatch: pytest.MonkeyPatch) -> None:
    env = {"BOK_API_KEY": "v"}
    assert key_aliases.adopt(env) == ["BOK_API_KEY->ECOS_API_KEY"]
    assert env["ECOS_API_KEY"] == "v"
    env2 = {"BOK_API_KEY": "old", "ECOS_API_KEY": "new"}
    assert key_aliases.adopt(env2) == [] and env2["ECOS_API_KEY"] == "new"
    reg = json.loads((DESK / "data" / "asia_sources.json").read_text("utf-8"))
    row = next(r for r in reg["sources"] if r["id"] == "bok_ecos")
    assert row["key_env"] == "ECOS_API_KEY" and row["key_env_aliases"] == ["BOK_API_KEY"]
    assert {s.key_env for s in A.SOURCES if s.id.startswith("kr_ecos_")} == {"ECOS_API_KEY"}
    monkeypatch.delenv("ECOS_API_KEY", raising=False)
    # terms come first: fenced on terms even before the key question is asked
    assert A.status_of(A.BY_ID["kr_ecos_call_rate"]) == "BLOCKED_ON_TERMS:to_confirm"
    from dataclasses import replace
    assert A.status_of(replace(A.BY_ID["kr_ecos_call_rate"], terms="confirmed"),
                       {}) == "BLOCKED_ON_KEY:ECOS_API_KEY"


def test_refused_registry_rows_are_refused_not_relabelled() -> None:
    reg = json.loads((DESK / "data" / "asia_sources.json").read_text("utf-8"))
    rows = {r["id"]: r for r in reg["sources"]}
    for sid in ("krx_open_api", "krx_derivatives_stats", "hkex_data"):
        r = rows[sid]
        assert r["terms"] == "refused" and r["terms_note"] and "access_label" not in r, sid
        assert A.terms_gate(r["terms_ref"])[0] == "refused"
        assert A.terms_gate(r["url"])[0] == "refused"          # the host alone is enough
    for sid in ("krx_open_api", "krx_derivatives_stats"):
        assert set(rows[sid]["directive_rows"]) == {"ASIA-0465", "ASIA-0466", "ASIA-0467"}


# ---------------------------------------------------------------------------- the collector gate
def _collector() -> Any:
    from research import asia_collector as C
    return C


class _Resp:
    status = 200

    def __init__(self) -> None:
        self.headers = {"Content-Type": "application/json"}
        self.body = b'{"ok": [1, 2, 3], "padding": "' + b"x" * 80 + b'"}'

    def read(self, n: int = -1) -> bytes:
        return self.body

    def __enter__(self) -> _Resp:
        return self

    def __exit__(self, *a: Any) -> None:
        return None


def _patch_net(monkeypatch: pytest.MonkeyPatch, C: Any, tmp_path: Path) -> list[str]:
    sent: list[str] = []

    def fake_urlopen(req: Any, *a: Any, **k: Any) -> _Resp:
        url = req.full_url if hasattr(req, "full_url") else str(req)
        hdrs = dict(getattr(req, "header_items", lambda: [])())
        sent.append(url + " " + json.dumps(hdrs) + " " + str(getattr(req, "data", b"")))
        return _Resp()

    monkeypatch.setattr(C.urllib.request, "urlopen", fake_urlopen)
    monkeypatch.setattr(C, "_vault", lambda *a, **k: {"path": "x"})
    monkeypatch.setattr(C, "_parse", lambda *a, **k: {"parsed": False, "why": "test"})
    monkeypatch.setattr(C, "VAULT", tmp_path / "vault")
    return sent


def test_every_collector_fetch_path_is_behind_the_terms_gate(
        monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    C = _collector()
    sent = _patch_net(monkeypatch, C, tmp_path)
    reg = json.loads((DESK / "data" / "asia_sources.json").read_text("utf-8"))
    rows = [r for r in reg["sources"] if str(r.get("role") or "") != "transport"]
    for r in rows:
        state, _ = C._terms_state(r, C._resolve_url(r))
        before = len(sent)
        rec = C.collect_one(r)
        if state not in ("confirmed", "ungoverned"):
            # robots.txt included: a refused / to_confirm row sends NOTHING at all
            assert len(sent) == before and rec["status"] == "BLOCKED_ON_TERMS", r["id"]
    blocked = {r["id"] for r in rows
               if C._terms_state(r, C._resolve_url(r))[0] not in ("confirmed", "ungoverned")}
    assert {"krx_open_api", "krx_derivatives_stats", "hkex_data", "bok_ecos",
            "baidu_index"} <= blocked
    for host in ("krx.co.kr", "hkex.com.hk", "ecos.bok.or.kr", "index.baidu.com"):
        assert not any(host in s.split(" ")[0] for s in sent), host
    # a derived child inherits its parent's terms decision
    child = {"id": "krx_open_api__ep1", "url": "https://elsewhere.example/x.csv",
             "terms": "refused", "terms_ref": "kr_krx_market_data", "access": "public"}
    assert C.collect_one(child)["status"] == "BLOCKED_ON_TERMS"


def test_a_keyed_source_without_confirmed_terms_sends_no_credential(
        monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    C = _collector()
    sent = _patch_net(monkeypatch, C, tmp_path)
    reg = json.loads((DESK / "data" / "asia_sources.json").read_text("utf-8"))
    keyed = [r for r in reg["sources"] if C._is_keyed(r)]
    secrets: dict[str, str] = {}
    for r in keyed:
        if r.get("key_env"):
            secrets[r["key_env"]] = f"SECRET-{r['id']}-{len(secrets)}"
            monkeypatch.setenv(r["key_env"], secrets[r["key_env"]])
    verdicts = {}
    for r in keyed:
        before = len(sent)
        rec = C.collect_one(r)
        state = C._terms_state(r, C._resolve_url(r))[0]
        verdicts[r["id"]] = state
        if state != "confirmed":
            assert rec["status"] == "BLOCKED_ON_TERMS" and len(sent) == before, r["id"]
    assert not any(v in s for v in secrets.values() for s in sent)
    assert "ungoverned" not in verdicts.values()               # a keyed row is always judged
    for sid in ("tushare", "bok_ecos", "collective2", "darwinex", "banxico_series"):
        assert verdicts[sid] == "to_confirm", sid
    assert verdicts["baidu_index"] == "refused"
    for sid in ("eia_energy", "nasa_firms", "estat_jp_customs"):
        assert verdicts[sid] == "confirmed", sid
    # an unknown keyed host with no terms_ref is fenced too
    assert C._terms_state({"access": "key", "key_env": "X"}, "https://new.example/api")[0] \
        == "to_confirm"


# ---------------------------------------------------------------------------- cells and routing
def test_plane_cells_route_through_the_lane_policy() -> None:
    from research import universe_policy
    for sid in PLANE_IDS:
        src = A.BY_ID[sid]
        for s in src.signal_series:
            for sym in src.instruments_for(s):
                assert not universe_policy.is_equity(sym), (sid, sym)
                assert A.may_mint(sym), (sid, sym)


def test_fixture_pass_publishes_axes_and_never_mints(tmp_path: Path) -> None:
    paths = A.Paths(tmp_path / "desk")
    rep = A.run(paths, fixtures=FIX, donate=False, now=NOW)
    assert rep["direct_cells"]["n"] == 0                     # fixtures never mint
    for sid in PLANE_IDS:
        axis = json.loads((paths.axes / f"alt_{sid}.json").read_text("utf-8"))
        assert any(k.endswith(".delta") for k in axis["series"]), sid
    # allocation intel needs a surprise_z, i.e. enough history: a synthetic 40-day HIBOR path
    src = A.BY_ID["hk_hkma_hibor_fixing"]
    store: dict[str, Any] = {}
    obs = [A.Obs("hibor_1m", date(2026, 8, 1) + timedelta(days=k), 3.0 + 0.1 * ((k * 7) % 5))
           for k in range(40)]
    A.merge_vintages(store, src, obs, NOW)
    intel = A.allocation_intel({src.id: A.build_points(src, store)}, {}, NOW)
    assert {"HK50", "USDHKD", "USDCNH"} <= set(intel["instruments"])


# ---------------------------------------------------------------------------- departments
def test_kr_plane_reports_lanes_refusals_and_export_events(tmp_path: Path) -> None:
    from countries.kr import official_plane as K
    paths = _fixture_pass(tmp_path)
    out = tmp_path / "KR.json"
    doc = K.run(paths=paths, report_default=out, now=NOW)
    assert json.loads(out.read_text("utf-8"))["country"] == "kr"
    lanes = {r["dataset"]: r for r in doc["lanes"]}
    assert lanes["kr_exports_early"]["status"] == "PARSED"
    for sid in ("kr_ecos_base_rate", "kr_ecos_call_rate", "kr_ecos_fx_reserves",
                "kr_ecos_export_prices"):
        assert lanes[sid]["status"] == "BLOCKED_ON_TERMS:to_confirm", sid     # fenced
    assert lanes["kr_krx_market_data"]["status"] == "BLOCKED_ON_TERMS:refused"
    assert lanes["kr_krx_market_data"]["terms_quote"]
    kinds = {(e["event"], e["lifecycle"]) for e in doc["events"]}
    assert ("kr_exports_20d", "RELEASED") in kinds and ("kr_exports_10d", "SCHEDULED") in kinds


def test_hk_plane_emits_cu_events(tmp_path: Path) -> None:
    from countries.hk import official_plane as H
    paths = _fixture_pass(tmp_path)
    doc = H.run(paths=paths, report_default=tmp_path / "HK.json", now=NOW)
    lanes = {r["dataset"]: r for r in doc["lanes"]}
    assert lanes["hk_hkma_interbank_liquidity"]["status"] == "PARSED"
    assert lanes["hk_hkex_stock_connect"]["status"] == "BLOCKED_ON_TERMS:refused"
    sides = {e["side"] for e in doc["events"]}
    assert sides == {"WEAK_SIDE"}                     # the fixture's two CU legs are purchases


def test_korea_registers_nothing_it_cannot_run() -> None:
    from countries.kr import miners as M
    M.refresh()
    assert not M.MISSING
    assert set(M.MINERS) == set(M.NAMES) and "official_plane" in M.MINERS
    for name, module, _a in M.BOX_SPECS:
        present = (Path(M.__file__).parent / f"{module}.py").exists()
        assert (name in M.NOT_IN_REPO) is (not present), name


def test_global_research_os_reads_both_planes() -> None:
    from research import global_research_os as G
    for code in ("kr", "hk"):
        miners, problem = G._load_extra(code)
        assert problem == "" and "official_plane" in miners, code


def test_department_miner_runs_dry(tmp_path: Path) -> None:
    from countries.kr import miners as M
    ctx = M.make_ctx(None, 30.0, dry_run=True)
    res = M.run_miner("official_plane", ctx)
    assert res["status"] == "RAN" and "lane(s)" in res["why"]
