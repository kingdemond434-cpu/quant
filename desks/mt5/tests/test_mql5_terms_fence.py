"""THE MQL5 TERMS FENCE: no process opens an mql5.com URL, and every refusal is recorded.

MQL5's Terms of Use 3.7, 3.9 and 3.13 prohibit automated access, reproduction and derivative
works, and the desk holds no permitting agreement (desks/mt5/side_channels/mql5_terms.py). These
tests replace every HTTP door a harvester could use -- `urllib.request.urlopen`, `requests` and
`http.client` -- with a recorder that FAILS the test on any mql5.com URL, then drive each
harvester's real entry point and assert that nothing was asked for and that the refusal was
written where the hourly schedule will see it.
"""
from __future__ import annotations

import http.client
import importlib
import importlib.util
import json
import sys
import types
import urllib.request
from pathlib import Path
from typing import Any

import pytest
import requests

DESK = Path(__file__).resolve().parents[1]
ROOT = DESK.parents[1]
for _p in (str(ROOT), str(ROOT / "scripts"), str(DESK), str(DESK / "side_channels"),
           str(DESK / "research")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from side_channels import mql5_terms  # noqa: E402

#: harvester module -> (the source it stamps, its mining function)
HARVESTERS: dict[str, tuple[str, str | None]] = {
    "mql5_signals": ("mql5_signals", "mine_signals"),
    "mql5_survivor_hunter": ("mql5_survivors", None),
    "mql5_forum": ("mql5_forum", "mine_forum"),
    "mql5_articles": ("mql5_articles", "mine_articles"),
    "mql5_codebase": ("mql5_codebase", "mine_codebase"),
}


@pytest.fixture
def no_network(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    """Every HTTP door recorded; an mql5.com URL fails the test outright."""
    attempts: list[str] = []

    def _record(url: Any) -> None:
        attempts.append(str(url))
        if mql5_terms.is_mql5_url(url) or "mql5.com" in str(url):
            pytest.fail(f"a request to mql5.com was attempted: {url}")
        raise OSError("network disabled in this test")

    def _urlopen(req: Any, *_a: Any, **_k: Any) -> Any:
        _record(getattr(req, "full_url", req))

    def _session_request(_self: Any, _method: str, url: Any, *_a: Any, **_k: Any) -> Any:
        _record(url)

    def _requests_get(url: Any, *_a: Any, **_k: Any) -> Any:
        _record(url)

    def _requests_request(_method: str, url: Any, *_a: Any, **_k: Any) -> Any:
        _record(url)

    def _conn_request(self: Any, _method: str, url: str, *_a: Any, **_k: Any) -> Any:
        _record(f"https://{self.host}{url}")

    def _connect(self: Any) -> Any:
        _record(f"https://{self.host}/")

    monkeypatch.setattr(urllib.request, "urlopen", _urlopen)
    monkeypatch.setattr(requests.Session, "request", _session_request)
    monkeypatch.setattr(requests, "get", _requests_get)
    monkeypatch.setattr(requests, "request", _requests_request)
    monkeypatch.setattr(http.client.HTTPConnection, "request", _conn_request)
    monkeypatch.setattr(http.client.HTTPConnection, "connect", _connect)
    monkeypatch.setattr(http.client.HTTPSConnection, "connect", _connect)
    return attempts


def _harvester(name: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Any:
    module = importlib.import_module("side_channels." + name)
    monkeypatch.setattr(module, "OUT", tmp_path)
    monkeypatch.setattr(module, "REFUSAL", tmp_path / module.REFUSAL.name)
    if hasattr(module, "SHORTLIST"):
        monkeypatch.setattr(module, "SHORTLIST", tmp_path / "survivor_shortlist.json")
    return module


# ------------------------------------------------------------------------- the five harvesters
@pytest.mark.parametrize("name", sorted(HARVESTERS))
def test_each_harvester_refuses_without_a_request_and_records_it(
        name: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
        no_network: list[str]) -> None:
    source, _miner = HARVESTERS[name]
    module = _harvester(name, tmp_path, monkeypatch)

    emitted = module.run_and_save()

    assert no_network == [], "a harvester attempted a request"
    assert emitted == [], "a refused hour yields no discoveries"
    written = sorted(tmp_path.glob("*.json"))
    assert [p.name for p in written] == [module.REFUSAL.name], "only the refusal is written"
    rows = json.loads(written[0].read_text("utf-8"))
    assert len(rows) == 1
    row = rows[0]
    assert row["source"] == source
    assert row["kind"] == "walled", "the compiler and miner-health read `walled` as operational"
    assert row["verdict"] == row["status"] == "BLOCKED_TERMS"
    assert row["reason"] == "MQL5 ToU 3.7/3.9/3.13: automated access not permitted"
    assert row["url"] == mql5_terms.TERMS_URL
    assert row["payload_hash"], "the refusal passes the canonical provenance door"
    assert not (tmp_path / "survivor_shortlist.json").exists(), "the shortlist is never rebuilt"


@pytest.mark.parametrize("name", sorted(n for n, (_s, m) in HARVESTERS.items() if m))
def test_the_mining_function_itself_refuses_before_a_request(
        name: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
        no_network: list[str]) -> None:
    module = _harvester(name, tmp_path, monkeypatch)
    with pytest.raises(mql5_terms.MQL5TermsRefused):
        getattr(module, HARVESTERS[name][1] or "")()
    assert no_network == []


def test_the_survivor_hunters_fetch_helpers_refuse(tmp_path: Path,
                                                   monkeypatch: pytest.MonkeyPatch,
                                                   no_network: list[str]) -> None:
    module = _harvester("mql5_survivor_hunter", tmp_path, monkeypatch)
    monkeypatch.setattr(module.time, "sleep", lambda _s: pytest.fail("slept before refusing"))
    with pytest.raises(mql5_terms.MQL5TermsRefused):
        module.fetch("https://www.mql5.com/en/signals/mt5/page1")
    with pytest.raises(mql5_terms.MQL5TermsRefused):
        module.deep_stats("123456")
    assert no_network == []


# ---------------------------------------------------------------------- the other fetch paths
def test_strategy_source_miners_refuse(tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
                                       no_network: list[str]) -> None:
    """Unscheduled, and they import bs4 -- stubbed where it is absent, so the fence is still
    exercised; the parser is never reached because nothing is fetched."""
    if importlib.util.find_spec("bs4") is None:
        stub = types.ModuleType("bs4")
        stub.BeautifulSoup = object  # type: ignore[attr-defined]
        monkeypatch.setitem(sys.modules, "bs4", stub)
    from side_channels.sources.strategy import (
        mql5_articles,
        mql5_codebase,
        mql5_forum,
        mql5_signals,
    )
    for mod, cls in ((mql5_articles, "MQL5ArticlesMiner"), (mql5_codebase, "MQL5CodeBaseMiner"),
                     (mql5_forum, "MQL5ForumMiner"), (mql5_signals, "MQL5SignalsMiner")):
        miner = getattr(mod, cls)(tmp_path)
        assert miner.discover({}, None) == []
        with pytest.raises(mql5_terms.MQL5TermsRefused):
            miner.session.get("https://www.mql5.com/en/code")
    assert no_network == []


def test_seed_miners_wall_every_mql5_seat_and_never_probe(no_network: list[str]) -> None:
    import seed_miners as sm
    for seat in mql5_terms.MQL5_SEATS:
        wall = sm.SOURCE_WALLS[seat]
        assert wall["verdict"] == "BLOCKED_TERMS" and wall["probe"] == "never"
        assert sm._wall_due(seat, {}) is False, "a written prohibition is never re-probed"
        lifted, note = sm._probe_wall(seat, wall)
        assert lifted is False and "BLOCKED_TERMS" in note
    with pytest.raises(mql5_terms.MQL5TermsRefused):
        sm.fetch("https://www.mql5.com/en/signals/mt5")
    with pytest.raises(mql5_terms.MQL5TermsRefused):
        sm.mine_mql5_signals()
    assert no_network == []


def test_run_all_miners_reports_blocked_terms(tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
                                              no_network: list[str]) -> None:
    import run_all_miners as ram
    entries = []
    for name, (source, _m) in HARVESTERS.items():
        if source not in mql5_terms.HARVESTERS or name == "mql5_survivor_hunter":
            continue
        module = importlib.import_module(name)
        monkeypatch.setattr(module, "REFUSAL", tmp_path / module.REFUSAL.name)
        entries.append((source, module.run_and_save))
    monkeypatch.setattr(ram, "ALL_MINERS", entries)

    out = ram.run_all_miners()

    assert no_network == []
    assert out["summary"]["blocked_terms"] == sorted(s for s, _f in entries)
    for source, _f in entries:
        assert out[source]["status"] == "BLOCKED_TERMS" and out[source]["count"] == 0
    assert len(list(tmp_path.glob("discoveries_blocked_terms_*.json"))) == len(entries)


def test_shared_http_clients_refuse_mql5(monkeypatch: pytest.MonkeyPatch,
                                         no_network: list[str]) -> None:
    from libs.data import polite_fetch as pf

    def _opener(*_a: Any, **_k: Any) -> Any:
        pytest.fail("polite_fetch opened a connection for a terms-refused host")

    for url in ("https://www.mql5.com/en/code", "https://mql5.com/ru/forum",
                "https://ru.mql5.com/x"):
        r = pf.get(url, opener=_opener, gate=None, sleep=lambda _s: None)
        assert not r.ok and r.error.startswith("BLOCKED_TERMS")
    assert pf.terms_refusal("https://example.mql5.community/") == ""

    import world_crawler as wc
    raw, why = wc.fetch("https://www.mql5.com/en/code/mt5/experts")
    assert raw is None and why.startswith("BLOCKED_TERMS")
    assert not any(mql5_terms.is_mql5_url(u) for u in wc.SEEDS)

    import global_survivor_frontier as gsf
    assert gsf.score_source("https://www.mql5.com/en/signals")["error"] == "BLOCKED_TERMS"

    import moat_collectors as mc
    body, _status, err = mc.fetch_bytes("https://www.mql5.com/en/articles")
    assert body == b"" and err.startswith("BLOCKED_TERMS")
    text, _status, err = mc.fetch_text("https://www.mql5.com/en/articles")
    assert text == "" and "BLOCKED_TERMS" in err

    import asia_collector as ac
    rec = ac.collect_one({"id": "mql5_ru", "url": "https://www.mql5.com/ru/articles"})
    assert rec["status"] == "BLOCKED_TERMS"
    assert no_network == []


# ---------------------------------------------------------------------- the evidence record
def test_the_evidence_record_carries_the_prohibiting_quote() -> None:
    rec = mql5_terms.MQL5_TERMS
    assert rec["host"] == "www.mql5.com" and "mql5.com" in rec["hosts"]
    assert rec["verdict"] == "PROHIBITS"
    assert rec["terms_url"] == "https://www.mql5.com/en/about/terms"
    assert rec["checked_at"] == "2026-10-06"
    assert rec["permitting_clause"] is None
    quote = rec["prohibiting_quote"]
    for clause in ("3.7", "3.9", "3.13"):
        assert f'{clause}: "' in quote
    assert ("You specifically agree not to access the website www.mql5.com through any "
            "automated means, including use of scripts, crawlers, or similar "
            "technologies.") in quote
    assert "You agree that You will not reproduce, duplicate, copy, sell, trade or resell" in quote
    assert "prepare derivative works from" in quote


def test_the_shared_client_mirrors_the_record() -> None:
    from libs.data import polite_fetch as pf
    assert set(pf.TERMS_REFUSED_HOSTS) == set(mql5_terms.HOSTS)
    assert set(pf.TERMS_REFUSED_HOSTS.values()) == {mql5_terms.REASON}


# --------------------------------------------------------- downstream: BLOCKED, never unfed
def test_censuses_count_mql5_seats_as_blocked_terms(tmp_path: Path,
                                                    monkeypatch: pytest.MonkeyPatch) -> None:
    from libs.ops import producer_census as pc
    assert set(pc.terms_blocked_seats()) == set(mql5_terms.MQL5_SEATS)
    for seat in ("mql5", "mql5_signals", "mql5_survivors"):
        d = tmp_path / "desks" / "mt5" / "data" / "intelligence" / seat
        d.mkdir(parents=True)
        (d / "discoveries_old.json").write_text("[]", encoding="utf-8")
    rows = {r.producer: r for r in pc.seat_rows(root=tmp_path, clocks={}, derived={},
                                                 retired={}, runs_here=True)}
    for seat in ("mql5", "mql5_signals", "mql5_survivors"):
        assert rows[seat].verdict == pc.BLOCKED_TERMS
        assert "3.7/3.9/3.13" in rows[seat].why and rows[seat].repair is None

    import check_producer_yield as cpy
    monkeypatch.setattr(cpy, "_seat_output",
                        lambda _w: {"mql5_signals": 0, "mql5": 0, "fxblue": 40})
    doc = cpy.audit(window_days=3.0)
    verdicts = {r["producer"]: r["verdict"] for r in doc["producers"]}
    assert verdicts["mql5_signals"] == verdicts["mql5"] == "BLOCKED_TERMS"
    assert all("mql5" not in r["producer"] for r in doc["dead_without_a_declared_replacement"])
    assert doc["median_rows"] == 40, "a refused seat never drags the peers' median down"

    import check_miner_health as cmh
    walls = cmh._walled()
    assert {s for s in mql5_terms.MQL5_SEATS if walls.get(s, {}).get("verdict") ==
            "BLOCKED_TERMS"} == set(mql5_terms.MQL5_SEATS)


# ------------------------------------------------- redirects, wrappers and compatibility forms
WRAPPED = ("https://web.archive.org/web/2024/https://www.mql5.com/en/signals/1",
           "https://r.jina.ai/https://www.mql5.com/en/articles",
           "https://translate.goog/?u=https%3A%2F%2Fwww.mql5.com%2Fen%2Fcode",
           "https://archive.ph/newest/https://mql5.com/ru/forum",
           "https://" + "".join(chr(0xFF4D + d) for d in (0, 4, -1)) + chr(0xFF15)
           + ".com/en/signals")


@pytest.mark.parametrize("url", WRAPPED)
def test_wrapped_and_fullwidth_mql5_urls_are_refused(url: str) -> None:
    from libs.data import polite_fetch as pf
    assert mql5_terms.is_mql5_url(url)
    assert pf.terms_refusal(url).startswith("BLOCKED_TERMS")
    with pytest.raises(mql5_terms.MQL5TermsRefused):
        mql5_terms.guard(url)


@pytest.mark.parametrize("url", ("https://example.com/mql5.community",
                                 "https://github.com/x/mql5-tools",
                                 "https://fred.stlouisfed.org/series/DGS10"))
def test_lookalikes_are_not_refused(url: str) -> None:
    from libs.data import polite_fetch as pf
    assert not mql5_terms.is_mql5_url(url) and pf.terms_refusal(url) == ""


@pytest.fixture
def redirect_server(monkeypatch: pytest.MonkeyPatch) -> Any:
    """A local server whose every path 302s onto www.mql5.com; any TLS connect fails the test."""
    import http.server
    import threading

    class _Redirect(http.server.BaseHTTPRequestHandler):
        def do_GET(self) -> None:
            self.send_response(302)
            self.send_header("Location", "https://www.mql5.com/en/signals/1")
            self.end_headers()

        def log_message(self, *_a: Any) -> None:
            return

    def _connect(self: Any) -> Any:
        pytest.fail(f"a TLS connection was opened to {self.host} after a redirect")

    for var in ("http_proxy", "HTTP_PROXY", "https_proxy", "HTTPS_PROXY"):
        monkeypatch.delenv(var, raising=False)
    monkeypatch.setenv("no_proxy", "*")
    monkeypatch.setenv("NO_PROXY", "*")
    monkeypatch.setattr(http.client.HTTPSConnection, "connect", _connect)
    srv = http.server.HTTPServer(("127.0.0.1", 0), _Redirect)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{srv.server_address[1]}/moved"
    srv.shutdown()
    srv.server_close()


def test_polite_fetch_refuses_a_redirect_into_mql5(redirect_server: str) -> None:
    from libs.data import polite_fetch as pf
    r = pf.get(redirect_server, gate=None, retries=2, sleep=lambda _s: None)
    assert not r.ok and r.error.startswith("BLOCKED_TERMS")
    assert r.attempts == 1                         # deterministic: never retried


def test_polite_fetch_refuses_an_opener_that_landed_on_mql5() -> None:
    from libs.data import polite_fetch as pf

    class _Landed:
        status, url, headers = 200, "https://www.mql5.com/en/signals/1", {}

        def __enter__(self) -> Any:
            return self

        def __exit__(self, *_a: Any) -> None:
            return None

        def read(self, _n: int) -> bytes:
            return b"<html>signal</html>"

    r = pf.get("https://example.org/x", opener=lambda *_a, **_k: _Landed(), gate=None)
    assert not r.ok and r.error.startswith("BLOCKED_TERMS") and r.text == ""


def test_acquire_datasets_refuses_a_redirect_into_mql5(redirect_server: str) -> None:
    import acquire_datasets as ad
    raw, why = ad._fetch(redirect_server)
    assert raw is None and why.startswith("BLOCKED_TERMS")


def test_seed_miners_fetch_refuses_a_redirect_into_mql5(redirect_server: str) -> None:
    import seed_miners as sm
    with pytest.raises(mql5_terms.MQL5TermsRefused):
        sm.fetch(redirect_server)


def test_a_fenced_session_refuses_a_redirect_into_mql5(redirect_server: str) -> None:
    session = mql5_terms.fence_session(requests.Session())
    with pytest.raises(mql5_terms.MQL5TermsRefused):
        session.get(redirect_server, timeout=5)


def test_cohort_never_refetches_an_mql5_member(tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
                                               no_network: list[str]) -> None:
    from side_channels import cohort_and_identity as ci
    monkeypatch.setattr(ci, "OBS", tmp_path / "observations.jsonl")
    monkeypatch.setattr(ci.time, "sleep", lambda _s: None)
    t0 = "2025-01-01T00:00:00+00:00"
    reg = {f"m{i}": {"t0": t0, "frozen": {"url": u, "source": "mql5_signals"},
                     "status": "ALIVE", "observations": 0, "next_due_d": 30}
           for i, u in enumerate(("https://www.mql5.com/en/signals/1",
                                  "https://web.archive.org/web/2024/https://www.mql5.com/x"))}
    assert ci.observe_due(reg) == 2
    assert {m["status"] for m in reg.values()} == {mql5_terms.STATUS}
    assert no_network == []
    assert ci.observe_due(reg) == 0                # retired: never due again
    rows = [json.loads(x) for x in ci.OBS.read_text("utf-8").splitlines()]
    assert {r["verdict"] for r in rows} == {mql5_terms.STATUS}
