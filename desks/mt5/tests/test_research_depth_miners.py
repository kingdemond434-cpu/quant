"""Research feeds and GitHub depth: every dialect parsed, every failure visible, the rate limit
obeyed, and the seed-miner state no longer reset by the end of its own sweep."""
from __future__ import annotations

import base64
import json
import sys
from pathlib import Path
from typing import Any

import pytest

DESK = Path(__file__).resolve().parents[1]
for _p in (str(DESK), str(DESK / "side_channels"), str(DESK.parent.parent)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import research_depth_miners as rdm  # noqa: E402


def _row(source: str, kind: str, title: str, url: str = "", text: str = "",
         symbols: list | None = None, **extra: Any) -> dict[str, Any]:
    return {"source": source, "kind": kind, "title": title, "url": url, "text": text,
            "symbols": symbols or [], **extra}


RSS2 = """<?xml version="1.0"?><rss version="2.0"><channel><title>NBER</title>
<item><title>Carry and Crash Risk in FX</title><link>https://www.nber.org/papers/w1</link>
<description>&lt;p&gt;We show currency &lt;b&gt;carry&lt;/b&gt; crashes.&lt;/p&gt;</description>
<pubDate>Mon, 09 Nov 2026 00:00:00 GMT</pubDate></item></channel></rss>"""

RDF = """<?xml version="1.0"?><rdf:RDF xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#"
 xmlns="http://purl.org/rss/1.0/" xmlns:dc="http://purl.org/dc/elements/1.1/">
<channel rdf:about="x"><title>BIS</title><items><rdf:Seq/></items></channel>
<item rdf:about="https://www.bis.org/publ/work1.htm"><title>FX dealer inventories</title>
<link>https://www.bis.org/publ/work1.htm</link><description>Order flow.</description>
<dc:creator>A. Author</dc:creator><dc:date>2026-11-08</dc:date></item></rdf:RDF>"""

ATOM = """<?xml version="1.0"?><feed xmlns="http://www.w3.org/2005/Atom"
 xmlns:arxiv="http://arxiv.org/schemas/atom">
<entry><id>http://arxiv.org/abs/2611.00001v1</id><title>Limit order book
 resilience</title><summary>Microstructure study.</summary><published>2026-11-07</published>
<author><name>B. Writer</name></author><link href="http://arxiv.org/abs/2611.00001v1"
 rel="alternate"/><arxiv:primary_category term="q-fin.TR"/></entry></feed>"""


def test_one_parser_reads_rss2_rdf_and_atom() -> None:
    a = rdm.parse_feed(RSS2)[0]
    assert a["title"] == "Carry and Crash Risk in FX"
    assert a["url"].endswith("/w1") and a["text"] == "We show currency carry crashes."
    b = rdm.parse_feed(RDF)
    assert len(b) == 1 and b[0]["authors"] == "A. Author" and b[0]["published"] == "2026-11-08"
    c = rdm.parse_feed(ATOM)[0]
    assert c["title"] == "Limit order book resilience" and c["category"] == "q-fin.TR"
    assert c["authors"] == "B. Writer" and c["url"].endswith("2611.00001v1")


def test_a_feed_declaring_entities_or_a_doctype_anywhere_is_refused() -> None:
    with pytest.raises(ValueError):
        rdm.parse_feed('<?xml version="1.0"?><!DOCTYPE r [<!ENTITY a "x">]><rss/>')
    late = "<!-- " + "x" * 9000 + ' -->\n<!doctype r [<!entity a "x">]><rss/>'
    with pytest.raises(ValueError):
        rdm.parse_feed(late)


def test_a_feed_without_recorded_terms_is_never_fetched() -> None:
    st: dict[str, Any] = {}
    asked: list[str] = []

    def get(url: str) -> str:
        asked.append(url)
        return _get(url)

    rdm.mine_research_feeds(st, get, _row, _cfg(), sleep=lambda s: None)
    assert "https://u/rss" not in asked
    assert st["rf_status"]["unknown_terms"]["status"] == "closed"
    shipped = rdm.load_feed_config()
    assert all(f["terms"] in ("open", "unrecorded") and f.get("terms_note")
               for f in shipped["feeds"])


def test_the_feed_pass_defers_what_its_deadline_cannot_reach() -> None:
    st: dict[str, Any] = {}
    ticks = iter(range(0, 10_000, 400))
    rdm.mine_research_feeds(st, _get, _row, _cfg(), sleep=lambda s: None,
                            clock=lambda: float(next(ticks)), deadline_s=600)
    assert any(v["status"] == "deferred" for v in st["rf_status"].values())


def _cfg() -> dict[str, Any]:
    return {"feeds": [{"name": "nber_new", "url": "https://n/rss", "kind": "working_paper",
                       "institution": "NBER", "terms": "open"},
                      {"name": "dead", "url": "https://dead/rss", "terms": "open"},
                      {"name": "blank", "url": "https://blank/rss", "terms": "open"},
                      {"name": "unknown_terms", "url": "https://u/rss"}],
            "arxiv": {"categories": ["q-fin.TR", "q-fin.ST"], "page_size": 50,
                      "backfill_depth": 120, "terms": "open"}}


def _get(url: str) -> str:
    if "dead" in url:
        raise RuntimeError("HTTP 404")
    if "blank" in url:
        return "<rss><channel/></rss>"
    if "arxiv" in url:
        return ATOM
    return RSS2


def test_feeds_dedup_report_dead_urls_and_walk_the_arxiv_backfill() -> None:
    st: dict[str, Any] = {}
    out = rdm.mine_research_feeds(st, _get, _row, _cfg(), sleep=lambda s: None)
    kinds = [r["kind"] for r in out]
    assert kinds.count("working_paper") == 1 and kinds.count("paper") == 1  # arXiv deduped
    err = [r for r in out if r["kind"] == "fetch_error"]
    assert len(err) == 1 and err[0]["needs_selector_work"] and err[0]["feed"] == "dead"
    assert st["rf_status"]["dead"]["status"] == "error"
    assert st["rf_status"]["blank"]["status"] == "empty"
    assert st["rf_status"]["nber_new"] == {**st["rf_status"]["nber_new"], "status": "ok",
                                           "items": 1, "new": 1}
    assert st["rf_arxiv_back"] == 100                   # walked one page deeper
    again = rdm.mine_research_feeds(st, _get, _row, _cfg(), sleep=lambda s: None)
    assert [r["kind"] for r in again] == ["fetch_error"]   # nothing re-emitted, dead still loud
    assert st["rf_arxiv_back"] == 150
    rdm.mine_research_feeds(st, _get, _row, _cfg(), sleep=lambda s: None)
    assert st["rf_arxiv_back"] == 50 + 50               # past the depth: page 2 read, then 3


def test_every_arxiv_qfin_category_is_configured() -> None:
    cats = set(rdm.load_feed_config()["arxiv"]["categories"])
    assert cats == {f"q-fin.{c}" for c in ("CP", "EC", "GN", "MF", "PM", "PR", "RM", "ST", "TR")}


class _Resp:
    def __init__(self, body: Any, status: int = 200, left: int | None = 4000) -> None:
        self._b, self.status_code = body, status
        self.headers = {} if left is None else {"X-RateLimit-Remaining": str(left)}

    def json(self) -> Any:
        return self._b


class _GitHub:
    def __init__(self, remaining: int = 4000, left: int = 4000) -> None:
        self.remaining, self.left, self.calls = remaining, left, []

    def __call__(self, url: str, headers: dict[str, str] | None = None, timeout: int = 20,
                 method: str = "GET", payload: Any = None) -> _Resp:
        self.calls.append((method, url, dict(headers or {})))
        if url.endswith("/rate_limit"):
            return _Resp({"resources": {"core": {"remaining": self.remaining}}}, left=None)
        if url.endswith("/graphql"):
            return _Resp({"data": {"repository": {"discussions": {"nodes": [
                {"title": "Does the London open fade work?", "url": "https://d/1", "body": "b",
                 "updatedAt": "2026-11-09T00:00:00Z", "category": {"name": "Ideas"}}]}}}})
        if "/readme" in url:
            return _Resp({"sha": "r1", "content": base64.b64encode(b"# Gold scalper").decode()},
                         left=self.left)
        if "/commits" in url:
            return _Resp([{"sha": "c2", "html_url": "https://c/2",
                           "commit": {"message": "tighten ATR stop\n\ndetail",
                                      "committer": {"date": "2026-11-09"}}}], left=self.left)
        if "/issues" in url:
            return _Resp([{"title": "Loses on NFP", "html_url": "https://i/1", "body": "x",
                           "state": "open"},
                          {"title": "a PR", "pull_request": {}, "html_url": "https://p/1"}],
                         left=self.left)
        if "/forks" in url:
            return _Resp([{"full_name": "bob/scalper", "stargazers_count": 9,
                           "html_url": "https://f/1"},
                          {"full_name": "zero/scalper", "stargazers_count": 0}], left=self.left)
        return _Resp(None, 404)


def test_github_depth_reads_readme_commits_issues_forks_without_a_token() -> None:
    st: dict[str, Any] = {}
    gh = _GitHub()
    out = rdm.mine_github_depth(st, gh, _row, {"alice/scalper": 40}, token=None)
    kinds = sorted(r["kind"] for r in out)
    assert kinds == ["code_change", "repo_fork", "repo_issue", "repo_readme"]  # 0-star fork out
    assert "a PR" not in json.dumps(out)                        # pull requests skipped
    assert st["gd_fork_pool"] == {"bob/scalper": 9}             # a starred fork joins the pool
    assert st["gd_status"]["discussions"].startswith("UNMEASURED")
    assert not any(m == "POST" for m, _, _ in gh.calls)         # no GraphQL without a token
    assert not any("Authorization" in h for _, _, h in gh.calls)
    assert st["gd_status"]["repos_read"] == 1
    rdm.mine_github_depth(st, _GitHub(), _row, {"alice/scalper": 40}, token=None)
    assert "bob/scalper" in st["gd_repos"]                      # the fork is read next pass


def test_a_second_pass_emits_only_what_changed() -> None:
    st: dict[str, Any] = {}
    rdm.mine_github_depth(st, _GitHub(), _row, {"alice/scalper": 40}, token=None)
    out = rdm.mine_github_depth(st, _GitHub(), _row, {"alice/scalper": 40}, token=None)
    kinds = {r["kind"] for r in out if r.get("repo") == "alice/scalper"}
    assert "repo_readme" not in kinds and "code_change" not in kinds and "repo_fork" not in kinds


def test_discussions_are_read_only_with_a_token_and_the_token_is_never_stored() -> None:
    st: dict[str, Any] = {}
    gh = _GitHub()
    out = rdm.mine_github_depth(st, gh, _row, {"alice/scalper": 40}, token="tok-SECRET")  # noqa: S106 - fake
    assert any(r["kind"] == "repo_discussion" for r in out)
    assert st["gd_status"]["discussions"] == "measured" and st["gd_status"]["token"] is True
    assert "tok-SECRET" not in json.dumps(st) and "tok-SECRET" not in json.dumps(out)


def test_the_rate_floor_stops_the_pass_before_it_starts_and_mid_pass() -> None:
    st: dict[str, Any] = {}
    gh = _GitHub(remaining=rdm.GH_FLOOR_ANON + 3)
    out = rdm.mine_github_depth(st, gh, _row, {"a/b": 1}, token=None)
    assert [r["kind"] for r in out] == ["unmeasured"] and not out[0]["needs_selector_work"]
    assert st["gd_status"]["stopped"].startswith("rate floor")
    assert [u for _, u, _ in gh.calls] == [f"{rdm.GH_API}/rate_limit"]
    st = {}
    gh = _GitHub(left=rdm.GH_FLOOR_ANON - 1)
    rdm.mine_github_depth(st, gh, _row, {"a/b": 1, "c/d": 2}, token=None)
    assert st["gd_status"]["stopped"].startswith("rate floor")
    assert len(gh.calls) == 2                                   # rate_limit + the first call


def test_topic_repos_keeps_trading_topics_only(tmp_path: Path) -> None:
    d = tmp_path / "github_topics"
    d.mkdir()
    (d / "discoveries_20261110_0100.json").write_text(json.dumps([
        {"title": "alice/scalper", "topic": "mql5", "stars": 40},
        {"title": "x/agents", "topic": "ai-agents", "stars": 900}]))
    assert rdm.topic_repos(tmp_path) == {"alice/scalper": 40}


def test_the_sweep_no_longer_resets_cursors_its_miners_advanced(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    import seed_miners
    state = tmp_path / "seed_miners_state.json"
    state.write_text(json.dumps({"gh_topic_cursor": 0}))
    monkeypatch.setattr(seed_miners, "STATE", state)
    monkeypatch.setattr(seed_miners, "INTEL", tmp_path)

    def advance() -> list[dict]:
        st = seed_miners._state()
        st["gh_topic_cursor"] = 4
        seed_miners.STATE.write_text(json.dumps(st))
        return [seed_miners.row("t", "repo", "a/b")]

    monkeypatch.setattr(seed_miners, "MINERS", {"t": advance})
    monkeypatch.setattr(seed_miners, "SOURCE_WALLS", {})
    import types

    from libs.research import proposer_seat
    monkeypatch.setattr(proposer_seat, "ask", lambda *a, **k: (_ for _ in ()).throw(OSError()))
    monkeypatch.setitem(sys.modules, "cohort_and_identity",
                        types.SimpleNamespace(run_and_save=lambda: None))
    seed_miners.run_and_save()
    assert json.loads(state.read_text())["gh_topic_cursor"] == 4


def test_both_miners_are_on_the_seed_miner_clock() -> None:
    import seed_miners
    assert seed_miners.MINERS["research_feeds"] is seed_miners.mine_research_feeds
    assert seed_miners.MINERS["github_depth"] is seed_miners.mine_github_depth


def test_crypto_exchange_repos_and_forks_are_never_read(tmp_path: Path) -> None:
    d = tmp_path / "github_topics"
    d.mkdir()
    (d / "discoveries_20261110_0100.json").write_text(json.dumps([
        {"title": "freqtrade/freqtrade", "topic": "trading-bot", "stars": 9},
        {"title": "x/grid", "topic": "algorithmic-trading", "stars": 9,
         "text": "Binance grid bot using ccxt"},
        {"title": "y/ea", "topic": "mql5", "stars": 3, "text": "London breakout EA for XAUUSD"}]))
    assert rdm.topic_repos(tmp_path) == {"y/ea": 3}
    for name in ("hummingbot/hummingbot", "a/bybit-scalper", "a/defi-arb", "a/okx-bot"):
        assert rdm.is_crypto(name)
    assert not rdm.is_crypto("a/gold-breakout", "EURUSD mean reversion", "metatrader5")
    st: dict[str, Any] = {"gd_fork_pool": {"z/binance-fork": 50}}
    gh = _GitHub()
    rdm.mine_github_depth(st, gh, _row, {"y/ea": 3}, token=None)
    assert not any("binance" in u for _, u, _ in gh.calls)


def test_an_unreadable_rate_limit_is_unmeasured_and_spends_nothing() -> None:
    def broken(url: str, **kw: Any) -> _Resp:
        return _Resp(None, 500, left=None)

    st: dict[str, Any] = {}
    out = rdm.mine_github_depth(st, broken, _row, {"a/b": 1}, token=None)
    assert out[0]["kind"] == "unmeasured" and "UNMEASURED" in out[0]["title"]
    assert st["gd_status"]["remaining_start"] == "UNMEASURED"


def test_github_state_is_bounded(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(rdm, "FORK_POOL_CAP", 3)
    monkeypatch.setattr(rdm, "VISITED_CAP", 2)
    st: dict[str, Any] = {"gd_fork_pool": {f"f/{i}": i for i in range(10)},
                          "gd_repos": {f"r/{i}": {"visited": f"2026-11-0{i}"} for i in range(5)}}
    rdm._bound(st)
    assert set(st["gd_fork_pool"]) == {"f/9", "f/8", "f/7"}
    assert set(st["gd_repos"]) == {"r/4", "r/3"}


def test_discussions_pause_below_the_graphql_floor() -> None:
    class _Low(_GitHub):
        def __call__(self, url: str, **kw: Any) -> _Resp:
            if url.endswith("/graphql"):
                self.calls.append(("POST", url, {}))
                return _Resp({"data": {"rateLimit": {"remaining": 5}, "repository": None}})
            return super().__call__(url, **kw)

    st: dict[str, Any] = {}
    gh = _Low()
    rdm.mine_github_depth(st, gh, _row, {"a/b": 3, "c/d": 2}, token="t")  # noqa: S106 - fake
    assert sum(1 for m, _, _ in gh.calls if m == "POST") == 1
    assert st["gd_status"]["discussions"].startswith("paused")


def test_the_token_is_read_from_the_environment_only(monkeypatch: pytest.MonkeyPatch,
                                                     tmp_path: Path) -> None:
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)
    monkeypatch.setenv("HOME", str(tmp_path))
    (tmp_path / ".gh_token").write_text("file-token")
    assert rdm.github_token() is None
    monkeypatch.setenv("GITHUB_TOKEN", " env-token ")
    assert rdm.github_token() == "env-token"


def test_state_writes_are_atomic(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    import seed_miners
    state = tmp_path / "seed_miners_state.json"
    monkeypatch.setattr(seed_miners, "STATE", state)
    seed_miners._write_state({"gh_topic_cursor": 4})
    seed_miners._merge_state({"rf_seen": ["k"]})
    assert json.loads(state.read_text()) == {"gh_topic_cursor": 4, "rf_seen": ["k"]}
    assert [p.name for p in tmp_path.iterdir()] == ["seed_miners_state.json"]  # no temp left
