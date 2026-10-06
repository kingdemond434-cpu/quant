"""The Alpha Capture substitute: five public sources parsed from recorded payload shapes, one
offline pass end to end, and the cell schema the compiler and the gauntlet read.

NOTHING HERE TOUCHES THE NETWORK. The build container's policy refuses all five hosts, so the
fixtures under `fixtures/alpha_capture/` are hand-written in each source's published payload
shape (Yahoo quoteSummary, EDGAR full-text search, eastmoney report/list JSON and JSONP, Naver's
EUC-KR research tables, the yanoshin TDnet list). Live yield stays UNMEASURED until the trading
box runs the organ; these tests prove the parsers, the PIT rule and the doors, not the yield.
"""
from __future__ import annotations

import json
import sys
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse

import numpy as np
import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[2]
DESK = ROOT / "desks" / "mt5"
for _p in (str(ROOT), str(DESK), str(DESK / "research")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import alpha_capture as ac  # noqa: E402

from libs.research import analyst_views as av  # noqa: E402

FIX = Path(__file__).resolve().parent / "fixtures" / "alpha_capture"
UNIVERSE_DOC: dict[str, Any] = json.loads((DESK / "data" / "universe" / "universe.json")
                                          .read_text("utf-8"))


def _fx(name: str) -> str:
    return (FIX / name).read_text("utf-8")


# ------------------------------------------------------------------------------ parsers
def test_yahoo_fixture() -> None:
    views = ac.parse_yahoo("NVIDIA", json.loads(_fx("yahoo_quotesummary_nvda.json")))
    assert len(views) == 5
    up = views[0]
    assert (up.instrument, up.broker, up.action, up.rating_old, up.rating_new) == (
        "NVIDIA", "Morgan Stanley", "up", 3, 4)
    assert up.target_change_pct == 25.0 and up.direction == 1
    assert up.published_precision == "date"
    maint = views[1]
    assert maint.action == "reiterate" and maint.target_old is None      # 0 is absence
    assert maint.target_change_pct is None and maint.direction == 0
    assert views[2].direction == -1 and views[3].action == "init" and views[3].direction == 1
    assert len({v.event_id for v in views}) == 5


def test_sec_fixture() -> None:
    views = ac.parse_sec_efts({1: [json.loads(_fx("sec_efts_raises.json"))],
                               -1: [json.loads(_fx("sec_efts_lowers.json"))]})
    by = {v.issuer: v for v in views}
    assert by["NVDA"].instrument == "NVIDIA" and by["NVDA"].direction == 1
    assert by["INTC"].instrument == "Intel" and by["INTC"].direction == -1
    assert by["PFE"].action == av.UNMEASURED and by["PFE"].direction == 0   # matched both
    assert by["ZZZZ"].instrument is None                                   # not quoted
    assert by["NVDA"].published_precision == "date" and by["NVDA"].kind == "company_guidance"


def test_eastmoney_fixtures_json_and_jsonp() -> None:
    stock = ac.parse_eastmoney(json.loads(_fx("eastmoney_stock.json")), 0)
    ind = ac.parse_eastmoney(ac._jsonp(_fx("eastmoney_industry.jsonp")), 1)
    baba = stock[0]
    assert baba.instrument == "AlibabaGroup" and baba.action == "up" and baba.target_new == 120.5
    assert "cn_market" in baba.leads and "cn_internet" in baba.leads
    assert stock[1].direction == 0                          # 维持买入 is a reiteration
    assert stock[2].action == "init" and "cn_semis" in stock[2].leads
    assert stock[2].published_precision == "datetime"
    assert stock[2].published_at == "2024-09-25T02:30:00+00:00"          # CST -> UTC
    assert ind[0].leads == ["cn_semis"] and ind[0].direction == 1
    assert ind[1].leads == ["cn_auto"] and ind[1].direction == -1


def test_naver_fixtures() -> None:
    rows = (ac.parse_naver_list(_fx("naver_company_list.html"), "company")
            + ac.parse_naver_list(_fx("naver_industry_list.html"), "industry"))
    assert [r["nid"] for r in rows] == ["78001", "78002", "33001", "33002"]
    assert rows[0]["code"] == "000660" and rows[0]["broker"] == "한국투자증권"
    assert rows[0]["date"] == "24.09.26"
    target, opinion = ac.parse_naver_detail(_fx("naver_company_read.html"))
    assert target == 260000.0 and opinion == "매수"
    views = ac.naver_views(rows, {"78001": (target, opinion)})
    assert views[0].leads == ["kr_semis"] and views[0].rating_new == 4
    assert views[1].leads == ["kr_market"] and views[1].target_new is None
    assert views[2].leads == ["kr_semis"] and views[3].leads == ["kr_market"]
    assert all(v.direction == 0 for v in views)      # direction needs the broker's prior view
    assert views[0].published_at == "2024-09-26T00:00:00+00:00"


def test_tdnet_fixture() -> None:
    views = ac.parse_tdnet(json.loads(_fx("tdnet_recent.json")))
    assert [v.issuer for v in views] == ["72030", "67580", "80580"]      # buyback skipped
    toyota = views[0]
    assert toyota.instrument == "Toyota" and toyota.direction == 1
    assert toyota.published_at == "2024-09-26T06:00:00+00:00"             # JST -> UTC
    assert views[1].direction == -1 and views[2].action == av.UNMEASURED
    assert all(v.leads == ["jp_market"] for v in views)


# ------------------------------------------------------------------------------ the maps
def test_every_mapped_symbol_is_quoted() -> None:
    equities = {k for k, v in UNIVERSE_DOC.items()
                if isinstance(v, dict) and v.get("asset_class") == "Equities"}
    assert set(ac.TICKERS) == equities
    for targets in av.LEAD_TARGETS.values():
        assert set(targets) <= set(UNIVERSE_DOC)
    assert set(ac.CN_NAMES.values()) <= set(UNIVERSE_DOC)
    assert ac.BENCHMARK in UNIVERSE_DOC


def test_the_news_lane_admits_these_families_for_share_cfds_only() -> None:
    from research import universe_policy as up
    assert up.may_hypothesise("Apple", "analyst_revision_drift")
    assert up.may_hypothesise("NVIDIA", "analyst_cross_market_lead")
    assert not up.may_hypothesise("Apple", "trend_ma_cross")
    assert up.may_hypothesise("USDKRW", "analyst_cross_market_lead")


def test_roster_rows_carry_every_field_and_feed_all_three_uses() -> None:
    rows = ac.roster_rows()
    assert [r["id"] for r in rows] == list(ac.SOURCES)
    need = {"id", "name", "url", "region", "language", "cadence", "auth", "licence", "cursor",
            "pit", "uses", "consumer", "status", "source_culture", "participant_structure",
            "failure_mode_hypothesis", "crowding_prior"}
    for r in rows:
        assert need <= set(r)
        assert r["uses"] == ["direct_cells", "indirect_cells", "allocation_intel"]
        assert r["status"] == ac.UNMEASURED_LIVE_YIELD
        assert r["auth"] in ("none", "key", "cookie")
        assert r["crowding_prior"] in ("low", "medium", "high")


# ------------------------------------------------------------------------------ cells
def _group(target: str, source: str, relation: str, lead: str, t: float,
           mean: float) -> dict[str, Any]:
    s = {"n": 40, "mean_bp": mean, "sd_bp": 100.0, "t": t, "hit": 0.6, "status": "MEASURED"}
    thin = {"n": 3, "status": av.UNMEASURED}
    return {"target": target, "source": source, "relation": relation, "lead": lead,
            "n_up": 20, "n_down": 20, "1d": thin, "5d": s, "21d": thin}


def test_cell_schema() -> None:
    groups = [_group("NVIDIA", "yahoo_upgrades", "direct", "", 4.0, 55.0),
              _group("USDKRW", "naver_research", "lead", "kr_semis", -3.9, -40.0),
              _group("Apple", "yahoo_upgrades", "direct", "", 0.5, 5.0)]
    admit = {"5d": {"NVIDIA|yahoo_upgrades|direct|": {"status": "ADMIT", "p_placebo": 0.01},
                    "USDKRW|naver_research|lead|kr_semis": {"status": "ADMIT"},
                    "Apple|yahoo_upgrades|direct|": {"status": "ADMIT"}}}
    cands, trials, refused = ac.cell_rows(groups, {"yahoo_upgrades": {"status": "ADMIT"}},
                                          cell_placebo=admit)
    assert trials == 3 and not refused and len(cands) == 2
    nv, krw = cands
    assert nv["family"] == "analyst_revision_drift" and nv["params"]["side"] == 1
    assert nv["params"]["symbol"] == "NVIDIA" and nv["params"]["hold_days"] == 5
    assert krw["family"] == "analyst_cross_market_lead" and krw["params"]["side"] == -1
    assert krw["params"]["lead"] == "kr_semis"
    for c in cands:
        for k in ("mechanism", "payer", "constraint", "source_culture", "participant_structure",
                  "failure_mode_hypothesis", "crowding_prior", "declared_width", "evidence",
                  "structured", "provenance"):
            assert c.get(k), k
        assert c["kind"] == "hypothesis" and c["symbols"] == [c["symbol"]]
        assert c["provenance"]["source_culture"] == c["source_culture"]
    assert krw["source_culture"] == "KR/ko" and krw["crowding_prior"] == "low"
    assert nv["evidence"]["contract_status"] == "ADMIT"
    assert nv["evidence"]["cell_placebo"]["status"] == "ADMIT"
    # the families the cells name are registered where the compiler and the gauntlet look
    from mt5desk import families_orthogonal as fo
    for c in cands:
        assert c["family"] in fo.ORTHOGONAL_FAMILIES


def test_cells_pass_the_real_donation_door(tmp_path: Path, monkeypatch: pytest.MonkeyPatch
                                           ) -> None:
    from research import proposer_common as pc
    monkeypatch.setattr(pc, "INTEL", tmp_path / "intel")
    monkeypatch.setattr(pc, "_record_in_registry", lambda *_a, **_k: None)
    monkeypatch.setattr(pc, "_preregister", lambda *_a, **_k: {"preregistered": 0, "failed": 0})
    cands, trials, _ = ac.cell_rows(
        [_group("Apple", "yahoo_upgrades", "direct", "", 4.0, 55.0)], {},
        cell_placebo={"5d": {"Apple|yahoo_upgrades|direct|": {"status": "ADMIT"}}})
    path = pc.donate("alpha_capture", cands, trials)
    assert path is not None
    doc = json.loads(Path(path).read_text("utf-8"))
    assert doc["counts"]["donated"] == 1 and doc["counts"]["refused_wrong_lane"] == 0
    row = doc["discoveries"][0]
    assert row["available_time"] and row["payload_hash"]


def test_a_high_t_cell_is_not_donated_without_its_own_placebo_admit() -> None:
    groups = [_group("NVIDIA", "yahoo_upgrades", "direct", "", 6.0, 80.0),
              _group("Apple", "yahoo_upgrades", "direct", "", 6.0, 80.0),
              _group("Meta", "yahoo_upgrades", "direct", "", 6.0, 80.0)]
    gate = {"5d": {"NVIDIA|yahoo_upgrades|direct|": {"status": "REJECT"},
                   "Apple|yahoo_upgrades|direct|": {"status": av.UNMEASURED}}}
    for placebo in (gate, None):                 # REJECT, UNMEASURED, absent: none is a pass
        cands, trials, refused = ac.cell_rows(groups, {}, cell_placebo=placebo)
        assert not cands and trials == 3 and len(refused) == 3
        assert all("placebo gate" in r["why"] for r in refused)


def test_the_report_never_collides_with_execution_intelligence() -> None:
    import re
    ei = (DESK / "research" / "execution_intelligence.py").read_text("utf-8")
    theirs = re.search(r'CAPTURE_REPORT = _DESK / "reports" / "([^"]+)"', ei)
    assert theirs is not None and theirs.group(1) == "ALPHA_CAPTURE.json"
    ours = {ac.REPORT.name, ac.CONTRACT.name, ac.INTEL.name}
    assert theirs.group(1) not in ours
    assert ac.REPORT.name == "ANALYST_VIEWS.json"
    assert ac.CONTRACT.name == "ANALYST_VIEWS_CONTRACT.json"
    state = json.loads((ROOT / "docs" / "research" / "runtime_state.json").read_text("utf-8"))
    rows = [r for r in state.get("organs") or state.get("rows") or []
            if isinstance(r, dict) and r.get("organ") == "leg:alpha_capture"]
    assert rows and "desks/mt5/research/alpha_capture.py" in rows[0]["code"]
    assert rows[0]["artifact_declared"] == "desks/mt5/reports/ANALYST_VIEWS.json"


# ------------------------------------------------------------------------------ one pass
@dataclass
class _Resp:
    url: str
    status: int
    text: str = ""
    error: str = ""

    @property
    def ok(self) -> bool:
        return 200 <= self.status < 400 and not self.error


def _fake_get(calls: list[str]) -> Any:
    def get(url: str, **_kw: Any) -> _Resp:
        calls.append(url)
        u = urlparse(url)
        q = parse_qs(u.query)
        if u.netloc == "fc.yahoo.com":
            return _Resp(url, 404, error="HTTP 404")
        if u.path.endswith("/getcrumb"):
            return _Resp(url, 200, "AbC.dEf123")
        if "quoteSummary" in u.path:       # one pass covers 35 tickers round-robin; each gets
            return _Resp(url, 200, _fx("yahoo_quotesummary_nvda.json"))  # the same history
        if u.netloc == "efts.sec.gov":
            phrase = q.get("q", [""])[0]
            up = any(w in phrase for w in ("raise", "increase"))
            return _Resp(url, 200, _fx("sec_efts_raises.json" if up else "sec_efts_lowers.json"))
        if u.netloc == "reportapi.eastmoney.com":
            if q.get("qType", ["0"])[0] == "0":
                return _Resp(url, 200, _fx("eastmoney_stock.json"))
            return _Resp(url, 200, _fx("eastmoney_industry.jsonp"))
        if u.netloc == "finance.naver.com":
            if "company_list" in u.path:
                return _Resp(url, 200, _fx("naver_company_list.html"))
            if "industry_list" in u.path:
                return _Resp(url, 200, _fx("naver_industry_list.html"))
            if "company_read" in u.path:
                return _Resp(url, 200, _fx("naver_company_read.html"))
            return _Resp(url, 200, "<table></table>")
        if u.netloc == "webapi.yanoshin.jp":
            return _Resp(url, 200, _fx("tdnet_recent.json"))
        return _Resp(url, 404, error="HTTP 404")
    return get


def _loader(sym: str) -> pd.DataFrame:
    rng = np.random.default_rng(sum(ord(c) for c in sym))
    idx = pd.date_range("2024-06-01 13:00", "2024-12-31 20:00", freq="1h", tz="UTC")
    idx = idx[(idx.hour >= 13) & (idx.hour <= 20) & (idx.dayofweek < 5)]
    close = 100 * np.exp(np.cumsum(rng.normal(0, 0.002, len(idx))))
    return pd.DataFrame({"open": close, "high": close * 1.001, "low": close * 0.999,
                         "close": close}, index=idx)


@pytest.fixture
def desk(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> dict[str, Any]:
    for name in ("STORE", "STATE", "AXIS", "REPORT", "CONTRACT", "INTEL", "DIGEST"):
        monkeypatch.setattr(ac, name, tmp_path / f"{name.lower()}.out")
    (tmp_path / "axes").mkdir()
    monkeypatch.setattr(ac, "AXIS", tmp_path / "axes" / "analyst_views.json")
    donated: list[Any] = []
    monkeypatch.setattr(ac, "_donate", lambda c, n: donated.append((c, n)) or tmp_path / "d")
    monkeypatch.setenv("QUANT_EDGAR_UA", "quant-desk research test@example.invalid")
    return {"tmp": tmp_path, "donated": donated}


def test_one_offline_pass_writes_every_artifact(desk: dict[str, Any]) -> None:
    calls: list[str] = []
    now = datetime(2024, 9, 27, 3, 0, tzinfo=UTC)
    rep = ac.run(budget_s=120, now=now, get=_fake_get(calls), loader=_loader,
                 clock=av.identity_clock, universe_doc=UNIVERSE_DOC, n_placebo=30,
                 yahoo_opener=object())
    for sid in ac.SOURCES:
        s = rep["sources"][sid]
        assert s["status"] == "FETCHED", (sid, s)
        assert s["live_yield"]["status"] == "MEASURED"
        assert s["rows_in_store"] > 0, sid
    assert rep["store"]["added"] >= 20 and rep["store"]["refused_unstamped"] == 0
    rows = av.AnalystViewStore(ac.STORE).rows()
    assert all(r["first_seen_at"] == now.isoformat(timespec="seconds") for r in rows)
    assert all(r.get("payload_hash") and r.get("available_time") for r in rows)
    # every artifact of the three uses exists and is readable
    axis = json.loads(ac.AXIS.read_text("utf-8"))
    assert axis["rows"] and {"symbol", "knowable_at", "net_breadth"} <= set(axis["rows"][0])
    from libs.research.alpha_dsl import axis_fields
    fields = axis_fields(ac.AXIS.parent)
    assert any(f.name.startswith("analyst_views.") and f.causal() for f in fields)
    intel = json.loads(ac.INTEL.read_text("utf-8"))
    assert intel["kind"] == "evidence" and ac.TICKERS and intel["instruments"]
    contract = json.loads(ac.CONTRACT.read_text("utf-8"))
    statuses = {sid: v["status"] for sid, v in contract["sources"].items()}
    # a random-walk bar set admits nothing; a thin source is UNMEASURED, never a clean verdict
    assert set(statuses.values()) <= {"REJECT", av.UNMEASURED} and statuses
    assert statuses.get("sec_8k_guidance") == av.UNMEASURED
    assert rep["cells"]["candidates"] == 0          # a day of history clears nothing, honestly
    assert not desk["donated"]
    # the small COMMITTED digest carries this organ's section (reports/ is gitignored)
    dig = json.loads(ac.DIGEST.read_text("utf-8"))["organs"]["alpha_capture"]
    assert dig["status"] == "LIVE" and dig["rows"] == rep["store"]["rows_total"]
    assert set(dig["measured"]) == set(ac.SOURCES) and not dig["unmeasured"]
    assert dig["gain"]["sec_8k_guidance"] == av.UNMEASURED
    assert dig["cells"]["donated"] == 0
    # the SEC request carried the declared User-Agent path, Yahoo went through the crumb
    assert any("getcrumb" in c for c in calls) and any("efts.sec.gov" in c for c in calls)
    # a second pass inside the cadence fetches nothing
    calls.clear()
    rep2 = ac.run(budget_s=60, now=now + timedelta(minutes=5), get=_fake_get(calls),
                  loader=_loader, clock=av.identity_clock, universe_doc=UNIVERSE_DOC,
                  n_placebo=10, yahoo_opener=object())
    assert not calls
    assert all(s["status"] == "NOT_DUE" for s in rep2["sources"].values())
    assert all(s["live_yield"]["status"] == ac.UNMEASURED_LIVE_YIELD
               for s in rep2["sources"].values())


def test_sec_without_a_user_agent_is_unconfigured_not_fetched(
        desk: dict[str, Any], monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("QUANT_EDGAR_UA")
    calls: list[str] = []
    rep = ac.run(budget_s=30, now=datetime(2024, 9, 27, tzinfo=UTC), get=_fake_get(calls),
                 loader=_loader, clock=av.identity_clock, universe_doc=UNIVERSE_DOC,
                 only=["sec_8k_guidance"], n_placebo=10)
    assert rep["sources"]["sec_8k_guidance"]["status"] == "UNCONFIGURED"
    assert not calls


def test_a_failing_source_never_takes_the_others_down(desk: dict[str, Any]) -> None:
    def get(url: str, **kw: Any) -> Any:
        if "naver" in url:
            raise RuntimeError("boom")
        return _fake_get([])(url, **kw)
    rep = ac.run(budget_s=60, now=datetime(2024, 9, 27, tzinfo=UTC), get=get, loader=_loader,
                 clock=av.identity_clock, universe_doc=UNIVERSE_DOC, n_placebo=10,
                 yahoo_opener=object())
    assert rep["sources"]["naver_research"]["status"] == "FAILED"
    assert rep["sources"]["tdnet_revisions"]["status"] == "FETCHED"
    assert rep["sources"]["naver_research"]["live_yield"]["status"] == ac.UNMEASURED_LIVE_YIELD
