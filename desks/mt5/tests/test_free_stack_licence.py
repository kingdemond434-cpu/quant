"""DATA-24: the AKShare / TuShare / BaoStock upstreams of the free stack pass the ONE terms gate
(`research.alt_proxies.terms_gate`) before any request, fail closed.

Every fetch here is a RECORDING fake: a fenced upstream must make zero calls. The hunter writes to
a temp store, so nothing lands in the desk's own data or reports.
"""
from __future__ import annotations

import json
import sys
import types
import urllib.parse
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest

_DESK = Path(__file__).resolve().parents[1]
_ROOT = _DESK.parent.parent
for _p in (str(_DESK), str(_DESK / "research"), str(_ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from libs.data import free_stack as fs  # noqa: E402
from research import alt_proxies as ap  # noqa: E402

NOW = datetime(2026, 10, 7, 12, 0, tzinfo=UTC)


class Recorder:
    def __init__(self) -> None:
        self.calls: list[str] = []

    def __call__(self, url: str, headers: Any = None, body: Any = None) -> bytes:
        self.calls.append(url)
        return b""


def _host(url: str) -> str:
    return urllib.parse.urlsplit(url).netloc.lower()


def _sid_of_host(host: str) -> str | None:
    return next((v for k, v in ap.TERMS_HOSTS.items() if host == k or host.endswith("." + k)),
                None)


# ------------------------------------------------------------------- every host governed ---
def test_every_upstream_host_maps_to_a_gate_terms_entry() -> None:
    hosts = {_host(u) for u in fs.ROUTE_URL.values()} | {_host(u) for u in
                                                        fs.ROUTE_REFERER.values()}
    hosts |= {_host(fs.TUSHARE_API), "push2his.eastmoney.com", "quote.eastmoney.com",
              "stock2.finance.sina.com.cn", "finance.sina.com.cn", "api.tushare.pro",
              "www.baostock.com"}
    for up in fs.CN_AGGREGATOR_UPSTREAMS:
        hosts |= set(up["also_governs"])
    for h in hosts:
        sid = _sid_of_host(h)
        assert sid in ap.GATE_TERMS, h
        assert ap.GATE_TERMS[sid][0] in ap.TERMS_VALUES, h
    gate_ids = {_sid_of_host(_host(str(u["gate"]))) if "://" in str(u["gate"]) else u["gate"]
                for u in fs.CN_AGGREGATOR_UPSTREAMS}
    assert gate_ids == {"cn_eastmoney_quotes", "cn_sina_finance", "cn_akshare_data",
                        "asia_tushare", "cn_baostock", "cn_jqdatasdk"}
    for gid in gate_ids:
        ev = ap.GATE_TERMS_EVIDENCE[str(gid)]
        assert ev["terms_url"].startswith("http") and ev["checked_at"] and ev["box_action"], gid
        assert ev["terms_quote"], gid                    # a quote, or WHY none could be read


def test_no_cn_aggregator_upstream_is_confirmed_on_judgement() -> None:
    """Expected outcome of DATA-24: everything read is refused or unread -> fenced."""
    for up in fs.CN_AGGREGATOR_UPSTREAMS:
        state, why = fs.terms_verdict(str(up["gate"]))
        assert state in ("refused", "to_confirm"), (up["route"], state)
        assert why


# ------------------------------------------------------------- a fence makes zero calls ---
def test_fenced_akshare_routes_make_zero_fetch_calls() -> None:
    rec = Recorder()
    h = fs.fetch_akshare_direct(rec, {"id": "akshare"}, {}, NOW)
    assert rec.calls == [] and h.requests == 0 and not h.obs
    assert h.status.startswith("BLOCKED_ON_TERMS:")
    assert set(h.status.split(":", 1)[1].split("+")) == {"refused", "to_confirm"}
    assert "eastmoney" in h.detail and "sina" in h.detail      # every fenced source named
    assert h.cursor == {}                                       # the cursor does not advance


def test_akshare_package_route_never_imports_or_calls_the_package(monkeypatch) -> None:
    called: list[str] = []
    fake = types.ModuleType("akshare")
    fake.stock_zh_index_daily = lambda **kw: called.append("data")  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "akshare", fake)
    rec = Recorder()
    h = fs.fetch_akshare_package(rec, {"id": "akshare"}, {}, NOW)
    assert called == [] and rec.calls == []
    assert h.status.startswith("BLOCKED_ON_TERMS:") and "akshare package data" in h.detail


def test_fenced_tushare_sends_no_request_and_no_token(monkeypatch) -> None:
    monkeypatch.setenv("TUSHARE_TOKEN", "not-a-real-token")
    rec = Recorder()
    h = fs.fetch_tushare(rec, {"id": "tushare", "key_env": "TUSHARE_TOKEN"}, {}, NOW)
    assert rec.calls == [] and h.requests == 0
    assert h.status == "BLOCKED_ON_TERMS:refused" and "tushare" in h.detail
    assert "not-a-real-token" not in h.detail


@pytest.mark.parametrize(("pkg", "verdict"), [("baostock", "to_confirm"),
                                              ("jqdatasdk", "to_confirm"),
                                              ("someotherpkg", "to_confirm")])
def test_fenced_package_route_never_opens_its_socket(monkeypatch, pkg: str, verdict: str) -> None:
    logins: list[str] = []
    fake = types.ModuleType(pkg)
    fake.login = lambda: logins.append("login")  # type: ignore[attr-defined]
    fake.auth = lambda *a: logins.append("auth")  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, pkg, fake)
    monkeypatch.setenv("JQ_USER", "u")
    monkeypatch.setenv("JQ_PASS", "p")
    h = fs.fetch_package_route(Recorder(), {"id": pkg, "package": pkg}, {}, NOW)
    assert logins == []
    assert h.status == f"BLOCKED_ON_TERMS:{verdict}" and pkg in h.detail


# --------------------------------------------------------- confirmed needs a quoted clause ---
def test_confirmed_requires_a_verbatim_terms_quote(monkeypatch) -> None:
    gid = "cn_sina_finance"
    monkeypatch.setitem(ap.GATE_TERMS, gid, ("confirmed", "judgement only"))
    # the evidence row still holds no quote -> still fenced, still zero calls
    assert fs.terms_verdict(fs.ROUTE_URL["sina"].format(code=""))[0] == "to_confirm"
    rec = Recorder()
    h = fs.fetch_akshare_direct(rec, {"id": "akshare"}, {}, NOW)
    assert not [u for u in rec.calls if "sina" in u]
    # with a quoted permitting clause the gate opens, and only that route is fetched
    monkeypatch.setitem(ap.GATE_TERMS_EVIDENCE, gid, {
        **ap.GATE_TERMS_EVIDENCE[gid], "terms_quote": "TEST: a permitting clause"})
    assert fs.terms_verdict(fs.ROUTE_URL["sina"].format(code=""))[0] == "confirmed"
    rec2 = Recorder()
    h = fs.fetch_akshare_direct(rec2, {"id": "akshare"}, {}, NOW)
    assert rec2.calls and all("sina.com.cn" in u for u in rec2.calls)
    assert not h.status.startswith("BLOCKED_ON_TERMS")        # a partial fence is a note
    assert any("eastmoney" in n for n in h.notes)
    for gid2, (state, _w) in ap.GATE_TERMS.items():
        if state == "confirmed" and gid2 != gid:
            q = (ap.GATE_TERMS_EVIDENCE.get(gid2) or {}).get("terms_quote", "")
            assert q and not q.startswith("("), gid2


def test_an_unimportable_terms_table_fails_closed(monkeypatch) -> None:
    def boom() -> Any:
        raise ImportError("no table")
    monkeypatch.setattr(fs, "_terms_table", boom)
    assert fs.terms_verdict("cn_baostock")[0] == "unreadable"
    rec = Recorder()
    assert fs.fetch_akshare_direct(rec, {"id": "akshare"}, {}, NOW).status == (
        "BLOCKED_ON_TERMS:unreadable") and rec.calls == []


# ------------------------------------------------------------------ MIT code vs the data ---
def test_mit_covers_the_code_never_the_data() -> None:
    ev = ap.GATE_TERMS_EVIDENCE["cn_akshare_data"]
    assert ev["code_licence_quote"].startswith("MIT License")
    assert "academic research" in ev["terms_quote"]
    assert "SOFTWARE" in ev["code_vs_data"] and "DATA" in ev["code_vs_data"]
    assert ap.GATE_TERMS["cn_akshare_data"][0] == "refused"
    rep = fs.licence_validation(NOW)
    assert "DATA" in rep["code_vs_data"]
    pkg = next(u for u in rep["upstreams"] if u["route"] == "akshare_package")
    assert pkg["code_licence_url"].endswith("/LICENSE") and pkg["verdict"] == "refused"


# ---------------------------------------------------------------------------- the report ---
def test_the_hunter_pass_writes_the_licence_report(tmp_path: Path, monkeypatch) -> None:
    from free_stack_hunter import Store, run
    st = Store(tmp_path)
    (tmp_path / "data" / "universe").mkdir(parents=True)
    (tmp_path / "data" / "universe" / "universe.json").write_text(
        (_DESK / "data" / "universe" / "universe.json").read_text("utf-8"), "utf-8")
    doc = json.loads((_DESK / "data" / "free_stack_sources.json").read_text("utf-8"))
    roster = tmp_path / "roster.json"
    roster.write_text(json.dumps({"sources": [r for r in doc["sources"]
                                              if r["id"] == "akshare"]}), "utf-8")
    rec = Recorder()
    rep = run(budget_s=60, fetch=rec, store=st, roster=roster, now=NOW, live=False)
    assert rec.calls == []
    assert rep["per_source"]["akshare"]["status"].startswith("BLOCKED_ON_TERMS:")
    cur = json.loads(st.cursor.read_text("utf-8"))["akshare"]
    assert "cursor" not in cur                                   # nothing advanced
    lic = json.loads(st.licence.read_text("utf-8"))
    assert st.licence.name == "CN_AGGREGATOR_LICENCE.json"
    assert st.licence.parent == tmp_path / "reports"
    for row in lic["upstreams"]:
        for k in ("host", "verdict", "terms_url", "quote", "checked_at", "box_action"):
            assert k in row, (row["route"], k)
        assert row["verdict"] != "confirmed" and row["fetch_allowed"] is False
        assert row["quote"] or row["unread_because"]                  # quote, or why not
    by = {r["terms_ref"]: r for r in lic["upstreams"]}
    assert "非商业目的" in by["asia_tushare"]["quote"]
    assert "非商业环境" in by["cn_eastmoney_quotes"]["quote"]
    assert by["cn_sina_finance"]["quote"] is None
    assert set(lic["fenced_columns"]) == set(fs.LICENCE_SOURCE_IDS)


def test_substitutes_exist_in_their_registries_and_are_unmeasured() -> None:
    rep = fs.licence_validation(NOW)
    asia = json.loads((_DESK / "data" / "asia_sources.json").read_text("utf-8"))
    asia_ids = {r.get("id") for r in (asia["sources"] if isinstance(asia, dict) else asia)}
    fsr = {r["id"] for r in json.loads((_DESK / "data" / "free_stack_sources.json")
                                       .read_text("utf-8"))["sources"]}
    keys = {k for k, _c, _r, _t in fs.CN_MARKET} | {"shibor"}
    assert set(rep["substitutes"]) == keys
    for key, s in rep["substitutes"].items():
        assert s["status"] in ("UNMEASURED", "NO_LAWFUL_SUBSTITUTE"), key
        for c in s["candidates"]:
            reg, cid = c["id"].split(":", 1)
            assert c["agreement"] == "UNMEASURED"
            assert cid in {"alt_proxies": set(ap.BY_ID), "asia_sources": asia_ids,
                           "free_stack_sources": fsr}[reg], c["id"]
        if not s["candidates"]:
            assert s["why"]


# --------------------------------------------------------------- the consumer reads it ---
def test_proposer_fences_archived_columns_by_the_licence_report(monkeypatch) -> None:
    import free_stack_proposer as P
    monkeypatch.setattr(P, "series_exists", lambda sid: True)
    cols = {"akshare": {"csi300_ret": {"hypothesis": ["CHINAH"], "event": [], "why": "t"}},
            "reddit": {"GOLD_tone": {"hypothesis": ["XAUUSD"], "event": [], "why": "t"}}}
    rep = fs.licence_validation(NOW)
    grid, skipped = P.build_grid(cols, P.roster_rows(), P.licence_fence(rep))
    assert {c["params"]["source"] for c in grid} == {"fs_reddit"}
    assert skipped["akshare"].startswith("BLOCKED_ON_TERMS")
    # the proposer reads the report from its declared path; no report -> fail closed
    monkeypatch.setattr(P, "LICENCE", Path("/nonexistent/CN_AGGREGATOR_LICENCE.json"))
    fence = P.licence_fence()
    assert all(fence[s] == ["*"] for s in fs.LICENCE_SOURCE_IDS)
    grid2, skipped2 = P.build_grid(cols, P.roster_rows())
    assert "akshare" in skipped2 and {c["params"]["source"] for c in grid2} == {"fs_reddit"}
