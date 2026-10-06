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
from datetime import UTC, date, datetime
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
    # a revision is its own stamped fact beside the first value, never back-dated
    later = datetime(2026, 10, 2, tzinfo=UTC)
    A.merge_vintages(store, src, [A.Obs("hibor_1m", date(2026, 8, 27), 9.0)], later)
    rev = [p for p in A.build_points(src, store)["hibor_1m"] if p["d"] == "2026-08-27"][0]
    assert rev["value"] != 9.0 and rev["revision_delta"] == pytest.approx(9.0 - rev["value"])
    assert rev["revision_of"]


def test_release_rules_are_late_biased() -> None:
    for sid in PLANE_IDS:
        t = A.BY_ID[sid].rule(date(2026, 8, 27))
        assert t > datetime(2026, 8, 27, tzinfo=UTC), sid
    assert A.BY_ID["hk_hkma_hibor_fixing"].rule(date(2026, 8, 27)).hour >= 4   # after 11:15 HKT


# ---------------------------------------------------------------------------- terms and keys
def test_plane_rows_are_confirmed_with_evidence_and_refused_hosts_are_not_sources() -> None:
    for sid in PLANE_IDS:
        assert A.BY_ID[sid].terms == "confirmed" and sid in A.KR_HK_TERMS_EVIDENCE, sid
        ev = A.KR_HK_TERMS_EVIDENCE[sid]
        assert ev["terms_url"].startswith("https://") and ev["checked_at"] == "2026-10-06"
    for sid in ("kr_krx_market_data", "hk_hkex_stock_connect"):
        assert sid not in A.BY_ID                              # no fetcher exists to run
        assert A.KR_HK_TERMS_EVIDENCE[sid]["decision"] == "refused"
        assert A.KR_HK_REFUSED[sid]["status"] == "BLOCKED_ON_TERMS:refused"


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
    assert A.status_of(A.BY_ID["kr_ecos_call_rate"]) == "BLOCKED_ON_KEY:ECOS_API_KEY"


def test_refused_registry_rows_carry_the_terms_label() -> None:
    reg = json.loads((DESK / "data" / "asia_sources.json").read_text("utf-8"))
    rows = {r["id"]: r for r in reg["sources"]}
    for sid in ("krx_open_api", "krx_derivatives_stats", "hkex_data"):
        assert rows[sid]["access_label"] == "PUBLIC_WITH_TERMS" and rows[sid]["terms_note"]


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
    intel = json.loads(paths.allocation_intel.read_text("utf-8"))
    assert intel["instruments"]


# ---------------------------------------------------------------------------- departments
def test_kr_plane_reports_lanes_refusals_and_export_events(tmp_path: Path) -> None:
    from countries.kr import official_plane as K
    paths = _fixture_pass(tmp_path)
    out = tmp_path / "KR.json"
    doc = K.run(paths=paths, report_default=out, now=NOW)
    assert json.loads(out.read_text("utf-8"))["country"] == "kr"
    lanes = {r["dataset"]: r for r in doc["lanes"]}
    for sid in ("kr_ecos_base_rate", "kr_ecos_call_rate", "kr_ecos_fx_reserves",
                "kr_ecos_export_prices", "kr_exports_early"):
        assert lanes[sid]["status"] == "PARSED", sid
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
