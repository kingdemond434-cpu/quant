"""MT5_GLOBAL_MINING_V1 tests, continued from tests/test_mining_pipeline.py (split for size): the
roster and its fetchers, the registry, the digest and the verdict join.
"""
from __future__ import annotations

import importlib.util
import json
import textwrap
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

import pytest

from libs.mining import acquirer as acq
from libs.mining import extractor, rejection
from libs.mining.pit_store import PitStore, iso
from tests.test_mining_pipeline import EA_RSI, MS, ROOT, T0, _pipe, _put


# ================================================================= roster and fetchers
def test_roster_loads_and_ingests_other_lanes_rows(tmp_path: Path) -> None:
    roster = acq.load_roster(root=ROOT)
    ids = {s.id for s in roster}
    assert len(ids) == len(roster) >= 40
    for s in roster:
        assert s.fetcher in acq.FETCHERS, (s.id, s.fetcher)
        assert s.kind in extractor.KINDS
        assert s.auth in acq.AUTH_KINDS
    prios = {s.priority for s in roster}
    assert {1, 2, 3, 4, 5} <= prios
    # another lane's rows, as they are
    ext = tmp_path / "desks" / "mt5" / "data" / "source_rosters"
    ext.mkdir(parents=True)
    (ext / "breadth.jsonl").write_text("\n".join(json.dumps(r) for r in [
        {"source_id": "edinet", "cadence_s": 3600, "auth": "keyless", "license": "public",
         "lang": "ja", "region": "jp", "url": "https://disclosure.edinet-fsa.go.jp/"},
        {"id": "mql5_codebase_en", "cadence": "daily"},          # cannot redefine ours
        {"id": "wind", "cadence": "hourly", "auth": "paid", "auth_env": "WIND_KEY"},
    ]), "utf-8")
    roster_file = tmp_path / "libs" / "mining" / "sources.yaml"
    roster_file.parent.mkdir(parents=True)
    roster_file.write_text((ROOT / "libs" / "mining" / "sources.yaml").read_text("utf-8"),
                           "utf-8")
    got = {s.id: s for s in acq.load_roster(roster_file, root=tmp_path)}
    assert got["edinet"].cadence_minutes == 60 and got["edinet"].auth == "none"
    assert got["edinet"].language == "ja" and got["edinet"].licence == "public"
    assert got["mql5_codebase_en"].origin.endswith("sources.yaml")
    assert got["wind"].auth == "key" and got["wind"].cadence_minutes == 60
    assert acq.auth_missing(got["wind"])


def _fake_http(pages: dict[str, str]) -> acq.HttpGet:
    def get(url: str, headers: Any) -> acq.HttpResult:
        if url in pages:
            return acq.HttpResult(200, pages[url])
        return acq.HttpResult(404, "", "HTTP 404")
    return get


def test_html_listing_walks_the_index_and_resumes(tmp_path: Path) -> None:
    src = acq.Source(id="cb", fetcher="html_listing", kind="code", config={
        "listing": [{"url": "https://m/code/page{page}", "page1": "https://m/code"}],
        "item_regex": r"/code/\d+$", "pages_per_run": 1})
    pages = {
        "https://m/code": '<a href="/code/1">a</a><a href="/code/2">b</a>',
        "https://m/code/page2": '<a href="/code/3">c</a>',
        "https://m/code/1": "<title>EA one</title><p>iRSI(NULL,PERIOD_H1,14,0)</p>",
        "https://m/code/2": "<title>EA two</title><p>text</p>",
        "https://m/code/3": "<title>EA three</title><p>more</p>",
    }
    store = PitStore(tmp_path / "m.db")
    cursors = acq.CursorStore(tmp_path / "c")
    ctx = acq.FetchContext(http_get=_fake_http(pages), deadline=time.monotonic() + 30, now=T0)
    rep = acq.acquire(src, store, cursors, ctx, force=True)
    assert rep.outcome == "ok" and rep.new == 3
    cur = cursors.get("cb")
    assert cur["page"]["0"] == 3 and len(cur["seen"]) == 3
    rep2 = acq.acquire(src, store, cursors, acq.FetchContext(
        http_get=_fake_http(pages), deadline=time.monotonic() + 30, now=T0), force=True)
    assert rep2.new == 0
    assert cursors.get("cb")["page"]["0"] == 2, "walked off the end: deep cursor wraps"


def test_fetch_outcomes_are_never_silent(tmp_path: Path) -> None:
    store = PitStore(tmp_path / "m.db")
    cursors = acq.CursorStore(tmp_path / "c")
    blocked = acq.Source(id="xq", fetcher="json_api", auth="login", auth_env="NOPE_NOT_SET")
    refused = acq.Source(id="ff", fetcher="html_listing", config={"listing": ["https://ff/x"]})
    for s in (blocked, refused):
        acq.acquire(s, store, cursors, acq.FetchContext(
            http_get=_fake_http({}), deadline=time.monotonic() + 5, now=T0), force=True)
    runs = store.last_runs()
    assert runs["xq"]["outcome"] == "BLOCKED_AUTH"
    assert runs["ff"]["outcome"] == "BLOCKED_FETCH" and "404" in runs["ff"]["detail"]


def test_reddit_telegram_and_rss_parsers(tmp_path: Path) -> None:
    reddit = json.dumps({"data": {"children": [
        {"data": {"created_utc": 1_790_000_100, "permalink": "/r/algotrading/p/2",
                  "title": "London breakout on GBPUSD", "selftext": "Asian range breakout"}},
        {"data": {"created_utc": 1_790_000_000, "permalink": "/r/algotrading/p/1",
                  "title": "hi", "selftext": ""}}]}})
    tg = ('<div data-post="fxalgo/41"><div class="tgme_widget_message_text">RSI(2) below 10 '
          'on XAUUSD</div><time datetime="2026-09-29T10:00:00+00:00"></time></div>')
    rss = ("<rss><channel><item><title>EA review</title><link>https://b/1</link>"
           "<guid>g1</guid><pubDate>Mon, 28 Sep 2026 10:00:00 GMT</pubDate>"
           "<description>Bollinger 20, 2 fade</description></item></channel></rss>")
    pages = {"https://www.reddit.com/r/algotrading/new.json?limit=100&raw_json=1": reddit,
             "https://t.me/s/fxalgo": tg, "https://b/feed": rss}
    store = PitStore(tmp_path / "m.db")
    cursors = acq.CursorStore(tmp_path / "c")
    for s in (acq.Source(id="rd", fetcher="reddit_json", immutable_time=True,
                         config={"subs": ["algotrading"]}),
              acq.Source(id="tg", fetcher="telegram_preview", config={"channels": ["fxalgo"]}),
              acq.Source(id="rs", fetcher="rss", config={"feeds": ["https://b/feed"]})):
        rep = acq.acquire(s, store, cursors, acq.FetchContext(
            http_get=_fake_http(pages), deadline=time.monotonic() + 5, now=T0), force=True)
        assert rep.outcome == "ok", (s.id, rep.detail)
    uris = {r["source_uri"] for r in store.as_of(T0)}
    assert {"https://www.reddit.com/r/algotrading/p/1", "https://www.reddit.com/r/algotrading/p/2",
            "https://t.me/fxalgo/41", "https://b/1"} <= uris
    assert cursors.get("rd")["created"]["sub:algotrading"] == 1_790_000_100
    assert cursors.get("tg")["last_id"]["fxalgo"] == 41


def test_extractor_reads_code_and_prose() -> None:
    code = extractor.read_code(
        "input int FastMA=12; input int SlowMA=26; iMA(NULL,PERIOD_H4,FastMA,0,MODE_EMA,0);"
        "iBands(NULL,PERIOD_H4,20,0,2.5,PRICE_CLOSE,MODE_UPPER,0);")
    assert code["indicators"]["ma"] == {"fast": 12, "slow": 26}
    assert code["indicators"]["bb"] == {"n": 20, "k": 2.5}
    assert code["timeframe"] == "H4"
    prose = extractor.read_text("Buy EURUSD on the H1 chart when RSI(7) drops below 20; "
                                "exit on the London close. Filter with EMA 20/50.")
    assert prose["indicators"]["rsi"]["n"] == 7 and prose["indicators"]["rsi"]["lo"] == 20
    assert prose["indicators"]["ma"] == {"fast": 20, "slow": 50}
    assert "london_close" in prose["patterns"] and prose["timeframe"] == "H1"
    facts = extractor.read_facts("Leverage up to 1:500. Swap long -6.2, swap short 1.1. "
                                 "Commission $4.5 per lot.")
    assert facts == {"leverage": 500.0, "swap_long": -6.2, "swap_short": 1.1,
                     "commission_per_lot": 4.5}


def test_every_source_declares_uses_and_useless_is_cold(tmp_path: Path) -> None:
    for s in acq.load_roster(root=ROOT):
        assert s.uses and set(s.uses) <= set(acq.USES), s.id
    srcs = [acq.Source(id="useless", fetcher="rss", uses=[]),
            acq.Source(id="alloc", fetcher="page_snapshot", kind="mechanics",
                       uses=["allocation_intel"])]
    st = _pipe(tmp_path, sources=srcs).source_status(T0)
    assert st["useless"]["status"] == "COLD" and st["useless"]["cold_reason"] == "serves no use"
    assert st["alloc"]["status"] == "COLD"
    assert st["alloc"]["cold_reason"] == "no cell EVALUATED in 30 days"


def test_regime_stated_in_text_becomes_an_indirect_cell(tmp_path: Path) -> None:
    pipe = _pipe(tmp_path)
    _put(pipe, "forum_ru", "https://f/1", "On EURUSD H1, RSI(14) below 25 is a buy, but only "
         "at month end and in high volatility.", kind="text")
    pipe.process(now=T0)
    regimes = {c.spec["params"].get("regime") for c in pipe.cells.by_status("QUEUED")
               if c.use == "indirect_cells" and c.spec}
    assert {"month_end", "high_vol"} <= regimes
    assert regimes <= {"high_vol", "low_vol", "month_end", "quarter_end"}


def test_robots_txt_is_obeyed_for_page_crawls(tmp_path: Path) -> None:
    pages = {"https://m.example/robots.txt": "User-agent: *\nDisallow: /code/viewcode\n",
             "https://m.example/code": '<a href="/code/viewcode/7">x</a><a href="/code/8">y</a>',
             "https://m.example/code/viewcode/7": "source", "https://m.example/code/8": "page"}
    src = acq.Source(id="cb", fetcher="html_listing", respect_robots=True, config={
        "listing": ["https://m.example/code"], "item_regex": r"/code/(viewcode/)?\d+$"})
    store = PitStore(tmp_path / "m.db")
    rep = acq.acquire(src, store, acq.CursorStore(tmp_path / "c"), acq.FetchContext(
        http_get=_fake_http(pages), deadline=time.monotonic() + 5, now=T0), force=True)
    assert rep.new == 1
    assert {r["source_uri"] for r in store.as_of(T0)} == {"https://m.example/code/8"}
    blocked = acq.Source(id="all", fetcher="page_snapshot", respect_robots=True,
                         config={"pages": ["https://m.example/code/viewcode/7"]})
    rep2 = acq.acquire(blocked, store, acq.CursorStore(tmp_path / "c"), acq.FetchContext(
        http_get=_fake_http(pages), deadline=time.monotonic() + 5, now=T0), force=True)
    assert rep2.outcome == "BLOCKED_ROBOTS"


def test_other_lanes_rosters_are_absorbed_as_owned_rows(tmp_path: Path) -> None:
    got = {s.id: s for s in acq.load_roster(root=ROOT)}
    asia = [s for s in got.values() if s.origin.endswith("asia_thread_sources.yaml")]
    assert asia and all(s.fetcher == "owned" and s.uses for s in asia)
    y = got.get("yahoo_upgrades")
    assert y is not None and y.cadence_minutes == 60 and y.auth == "none"
    assert y.consumer.endswith("alpha_capture.py")
    # breadth's files, in their own shapes (grounds / sources / rows)
    d = tmp_path / "desks" / "mt5" / "data"
    d.mkdir(parents=True)
    (d / "cell_emitter_sources.json").write_text(json.dumps({"grounds": [
        {"id": "vnpy_cta", "cadence": "hourly (leg cell_emitter)", "auth": "none (token used)",
         "license": "MIT", "language": "python", "region": "cn"}]}), "utf-8")
    (d / "world_factory_sources.json").write_text(json.dumps({"sources": [
        {"id": "news_event_stream", "kind": "news", "organ": "desks/mt5/research/x.py",
         "cadence": "hourly"}]}), "utf-8")
    (d / "alt_dataset_sources.json").write_text(json.dumps({"rows": [
        {"id": "alt_power_iowa", "class": "satellite", "url": "https://power"}]}), "utf-8")
    roster_file = tmp_path / "libs" / "mining" / "sources.yaml"
    roster_file.parent.mkdir(parents=True)
    roster_file.write_text((ROOT / "libs" / "mining" / "sources.yaml").read_text("utf-8"),
                           "utf-8")
    got2 = {s.id: s for s in acq.load_roster(roster_file, root=tmp_path)}
    v = got2["vnpy_cta"]
    assert v.fetcher == "owned" and v.cadence_minutes == 60 and v.auth == "none"
    assert v.licence == "MIT" and v.uses == ["direct_cells", "indirect_cells"]
    w = got2["news_event_stream"]
    assert w.kind == "text" and w.consumer == "desks/mt5/research/x.py"
    assert got2["alt_power_iowa"].uses == ["indirect_cells", "allocation_intel"]
    rep = acq.acquire(v, PitStore(tmp_path / "m.db"), acq.CursorStore(tmp_path / "c"),
                      acq.FetchContext(http_get=_fake_http({}), deadline=time.monotonic() + 5,
                                       now=T0), force=True)
    assert rep.outcome == "OWNED" and rep.fetched == 0


def test_keyed_sources_accept_the_pasted_formats(monkeypatch: pytest.MonkeyPatch) -> None:
    roster = {s.id: s for s in acq.load_roster(root=ROOT)}
    xq, kk = roster["xueqiu"], roster["kakao_public"]
    for raw, want in (("abc", "xq_a_token=abc"), ("xq_a_token=abc", "xq_a_token=abc"),
                      ("Cookie: xq_a_token=abc; u=9", "xq_a_token=abc; u=9")):
        monkeypatch.setenv(xq.auth_env, raw)
        assert acq.auth_headers(xq) == {"Cookie": want}
    for raw in ("k1", "KakaoAK k1"):
        monkeypatch.setenv(kk.auth_env, raw)
        assert acq.auth_headers(kk) == {"Authorization": "KakaoAK k1"}
    monkeypatch.delenv(kk.auth_env)
    assert acq.auth_headers(kk) == {} and acq.auth_missing(kk)


def test_json_api_sends_the_secret_and_reads_epoch_ms(tmp_path: Path,
                                                      monkeypatch: pytest.MonkeyPatch) -> None:
    src = acq.Source(id="xq", fetcher="json_api", kind="text", auth="login",
                     auth_env="XQ_TEST", config={
                         "auth_style": "cookie", "cookie_name": "xq_a_token",
                         "url": "https://x/s?q={q}&page={page}", "items_path": "list",
                         "uri_template": "https://x{target}",
                         "fields": {"target": "target", "title": "title", "body": "text",
                                    "time": "created_at"},
                         "queries": ["gold"]})
    monkeypatch.setenv("XQ_TEST", "tok")
    sent: list[Any] = []

    def get(url: str, headers: Any) -> acq.HttpResult:
        sent.append(dict(headers))
        if url.endswith("page=1"):
            return acq.HttpResult(200, json.dumps({"list": [
                {"target": "/1/2", "title": "", "text": "<p>XAUUSD RSI(14) below 30</p>",
                 "created_at": 1727700000000}]}))
        return acq.HttpResult(200, json.dumps({"list": []}))
    ctx = acq.FetchContext(http_get=get, deadline=time.monotonic() + 30, max_items=50,
                           now=T0, root=tmp_path)
    items = [i for i in acq.fetch_json_api(src, {}, ctx) if i.uri]
    assert [i.uri for i in items] == ["https://x/1/2"]
    assert items[0].publication_time == "2024-09-30T12:40:00+00:00"
    assert "RSI(14)" in items[0].body
    assert sent[0]["Cookie"] == "xq_a_token=tok"


def test_gauntlet_kills_carry_the_asia_kill_class() -> None:
    assert rejection.kill_class("deflated_sharpe") == "confident_kill"
    assert rejection.kill_class("lockbox") == "fail_closed"
    assert rejection.kill_class("economic_prior") == "screen_reject"
    assert rejection.kill_class("not_run") == "unconfident"
    assert rejection.GATE_REASON["swap_cost"] is rejection.Reason.INSUFFICIENT_SAMPLE


def test_fixture_trace_runs_the_real_sealed_gauntlet(tmp_path: Path) -> None:
    """No fabricated verdict: `external_gauntlet.build_cell` / `run_gauntlet` judge the cell."""
    m = MS.fixture_trace(tmp_path / "fx")
    tr = m["trace"]
    assert tr["complete"] and tr["source_uri"].startswith("fixture://mql5.com/")
    assert tr["preregistration_sha256"]
    assert tr["verdict"]["terminal_gate"] not in ("", "UNKNOWN", None)
    assert tr["outcome"] == "SURVIVOR" or tr["outcome"] in rejection.REASON_CODES
    # the gauntlet's own cell id IS the mining cell's sealed gauntlet_cell: the ledger row
    # carries the judged id, and a mismatch would have read FAILS_PREREG
    assert tr["outcome"] != "FAILS_PREREG"
    assert tr["verdict"]["gauntlet_cell"] == tr["gauntlet_cell"]
    ledger = [json.loads(x) for x in
              (tmp_path / "fx" / "fixture_gate_ledger.jsonl").read_text("utf-8").splitlines()]
    assert ledger and all(r["cell"] == r["judged_cell"] for r in ledger)
    digest = json.loads((tmp_path / "fx" / "mining_digest.json").read_text("utf-8"))
    ch = digest["chains"]
    assert ch and all(c["source_url"].startswith("fixture://") for c in ch)
    assert all(datetime.fromisoformat(c["prereg_sealed_at"])
               < datetime.fromisoformat(c["verdict_at"]) for c in ch)
    assert digest["metrics"]["docket_cells_judged_24h"] == len(ch)


def test_join_follows_the_docket_axis_expansion(tmp_path: Path) -> None:
    donated: list[dict[str, Any]] = []
    pipe = _pipe(tmp_path)
    pipe.hooks.donate = lambda rows: (donated.extend(rows) or True, "{}")
    _put(pipe, "codebase", "https://www.mql5.com/en/code/9", EA_RSI + "// EURUSD only",
         title="RSI EA for EURUSD")
    pipe.process(now=T0)
    pipe.donate(now=T0)
    assert donated and all(r["url"] == "https://www.mql5.com/en/code/9" for r in donated)
    c = next(x for x in pipe.cells.by_status("EVALUATING") if x.use == "direct_cells")
    expanded = pipe.prereg.load(c.cell_id)["gauntlet_cells_expanded"]
    assert len(expanded) == 16 and "M15/london" in expanded
    stranger = pipe.hooks.gauntlet_cell({**(c.spec or {}), "params": {"rsi_n": 99}})
    rows = [{"at": iso(T0), "cell": expanded["M5/asia"], "passed": False,
             "terminal_gate": "walk_forward"},
            {"at": iso(T0 + timedelta(minutes=1)), "cell": expanded["M15/london"],
             "passed": True, "terminal_gate": "PASSED"},
            {"at": iso(T0 + timedelta(minutes=2)), "cell": expanded["M15/london"],
             "passed": True, "terminal_gate": "PASSED"},            # a replayed row
            {"at": iso(T0), "cell": stranger, "passed": True, "terminal_gate": "PASSED"}]
    (tmp_path / "gate_verdict_ledger.jsonl").write_text(
        "".join(json.dumps(r) + "\n" for r in rows), "utf-8")
    assert pipe.join_verdicts(now=T0) == 2
    got = pipe.cells.get(c.cell_id)
    assert got is not None and got.status == "EVALUATED"
    assert got.rejection_reason == "REGIME_FRAGILE"                  # the first judged axis
    assert got.verdict["survivor"] and got.verdict["survivor_axis"]["axis"] == "M15/london"
    m = pipe.metrics(T0 + timedelta(hours=1))
    assert m["docket_cells_judged_24h"] == 2 and m["docket_cells_passed_24h"] == 1
    assert m["cells_survived_24h"] == 1
    kills = [r for r in pipe.ledger.rows() if r["stage"] == "gauntlet"]
    assert [r["kill_class"] for r in kills] == ["confident_kill"]


def test_digest_is_written_even_when_acquire_raises(tmp_path: Path) -> None:
    pipe = _pipe(tmp_path)

    def boom(*a: Any, **k: Any) -> Any:
        raise RuntimeError("network stack gone")
    pipe.acquire = boom
    m = pipe.run_pass(60, fetch=True, now=T0)
    assert any(e.startswith("acquire: RuntimeError") for e in m["last_pass"]["errors"])
    assert json.loads((tmp_path / "mining_digest.json").read_text("utf-8"))["generated_at"]

    def metrics_boom(t: Any) -> Any:
        raise ValueError("metrics broke")
    pipe.metrics = metrics_boom
    with pytest.raises(ValueError):
        pipe.run_pass(60, fetch=False, now=T0 + timedelta(hours=1))
    d = json.loads((tmp_path / "mining_digest.json").read_text("utf-8"))
    assert d["generated_at"] == iso(T0 + timedelta(hours=1))
    assert d["metrics"]["publish"] == "FAILED before metrics"


def test_mechanics_feed_becomes_conditioner_series_and_cells(tmp_path: Path) -> None:
    src = acq.Source(id="broker_specs", fetcher="page_snapshot", kind="mechanics",
                     uses=["allocation_intel"], config={"targets": ["XAUUSD"]})
    pipe = _pipe(tmp_path, sources=[src])
    uri = "https://broker/xauusd-spec"
    for i in range(MS.COND_MIN_OBS - 1):
        _put(pipe, "broker_specs", uri, f"Swap long -{6 + i * 0.1:.1f}, swap short 1.1. "
             f"Commission ${4 + i % 3}.5 per lot. Maximum daily loss of {4 + i % 2}%.",
             kind="mechanics", now=T0 + timedelta(days=i))
        pipe.process(now=T0 + timedelta(days=i))
    rep = pipe.conditioners(now=T0 + timedelta(days=40))
    sid = MS.Pipeline.series_id("broker_specs", uri)
    st = json.loads(pipe.cells.kv_get("conditioners", "{}"))[sid]
    assert rep["cells_minted"] == 0 and st["status"].startswith("UNMEASURED")
    last = T0 + timedelta(days=MS.COND_MIN_OBS - 1)
    _put(pipe, "broker_specs", uri, "Swap long -9.9, swap short 1.1. Commission $4.5 per lot.",
         kind="mechanics", now=last)
    pipe.process(now=last)
    rep = pipe.conditioners(now=last)
    lines = (tmp_path / "lake" / "series" / f"{sid}.csv").read_text("utf-8").splitlines()
    assert lines[0].startswith("available_time,vintage_id,source_id")
    assert len(lines) == 1 + MS.COND_MIN_OBS
    times = [ln.split(",")[0] for ln in lines[1:]]
    assert times == sorted(times) and times[-1] == iso(last)
    st = json.loads(pipe.cells.kv_get("conditioners", "{}"))[sid]
    assert st["status"] == "MINTING" and st["varying"] == ["swap_long"]
    cells = [c for c in pipe.cells.all_cells() if c.use == "allocation_intel"]
    assert rep["cells_minted"] == len(cells) == len(MS.COND_TRANSFORMS)
    assert {c.spec["family"] for c in cells} == {"exogenous_conditioner"}
    assert {c.spec["params"]["source"] for c in cells} == {sid}
    assert all(c.status == "QUEUED" and c.preregistration_id for c in cells)
    assert pipe.conditioners(now=last)["cells_minted"] == 0          # minted once
    # commission and the prop-rule limit changed too, and went to the cost/risk input instead
    facts = json.loads((tmp_path / "mechanics_facts.json").read_text("utf-8"))["pages"][sid]
    assert facts["cost"] == {"commission_per_lot": 4.5} and facts["financing"]["swap_long"] == -9.9
    assert "max_daily_loss_pct" not in facts["prop_rules"]          # the last page omitted it
    assert set(facts["last_changed_at"]) >= {"swap_long", "commission_per_lot"}
    assert not any(c.spec["params"]["signal"] != "swap_long" for c in cells)


def test_digest_carries_the_whole_rejection_ledger(tmp_path: Path) -> None:
    pipe = _pipe(tmp_path)
    for i in range(5):
        pipe.ledger.reject(f"mc_{i}", "DUPLICATE_MECHANISM" if i % 2 else "COST_EXCEEDS_EDGE",
                           "dedup" if i % 2 else "gauntlet", source_id="codebase",
                           kill_class="" if i % 2 else "confident_kill", now=T0)
    pipe.run_pass(60, fetch=False, now=T0)
    d = json.loads((tmp_path / "mining_digest.json").read_text("utf-8"))["rejection_ledger"]
    raw = (tmp_path / "mining" / "rejections.jsonl").read_bytes()
    import hashlib
    assert d["rows"] == 5 and d["sha256"] == hashlib.sha256(raw).hexdigest()
    assert d["by"]["reason"] == {"COST_EXCEEDS_EDGE": 3, "DUPLICATE_MECHANISM": 2}
    assert d["by"]["kill_class"] == {"confident_kill": 3}


def test_digest_carries_the_mining_trial_family_view(tmp_path: Path) -> None:
    pipe = _pipe(tmp_path)
    _put(pipe, "codebase", "https://www.mql5.com/en/code/7", EA_RSI + "// EURUSD only")
    pipe.process(now=T0)
    pipe.donate(now=T0)
    c = next(x for x in pipe.cells.by_status("EVALUATING") if x.use == "direct_cells")
    (tmp_path / "gate_verdict_ledger.jsonl").write_text(json.dumps(
        {"at": iso(T0), "cell": c.gauntlet_cell, "passed": False,
         "terminal_gate": "pbo"}) + "\n", "utf-8")
    pipe.run_pass(60, fetch=False, now=T0)
    fams = pipe.cells.trial_families()
    assert fams[c.trial_family_id]["docket_judged"] == 1
    assert fams[c.trial_family_id]["families"] == ["mean_reversion_rsi"]
    got = json.loads((tmp_path / "mining_digest.json").read_text("utf-8"))[
        "trial_family_summary"]
    assert got["status"] == "MEASURED" and got["docket_judged"] == 1
    assert got["trial_families"] == len(fams)
    assert MS.trial_family_summary({})["status"].startswith("UNMEASURED")


def test_one_registry_names_every_lane_once(tmp_path: Path) -> None:
    """Unnamed rows get durable ids (the W1 `ground:` form for grounds), the same thing on the
    same page from two rosters is one source with an alias, and a different thing on the same
    page stays a second source linked by shares_page."""
    d = tmp_path / "desks" / "mt5" / "data"
    d.mkdir(parents=True)
    (d / "grounds.json").write_text(json.dumps({"grounds": [
        {"name": "七禾网 专访", "region": "cn", "url": "https://www.7hcn.com/list"},
        {"name": "Stats Portal", "region": "cn", "url": "https://stats.example.cn/sj/"}]}),
        "utf-8")
    (d / "lane.json").write_text(json.dumps({"sources": [
        {"id": "hcn_interviews", "name": "七禾网 专访", "region": "cn",
         "url": "http://7hcn.com/list/"},
        {"id": "cn_rail", "name": "rail freight", "url": "https://stats.example.cn/sj"},
        {"id": "shfe_kx", "name": "a", "url": "https://s.cn/d.html?paramid=kx"},
        {"id": "shfe_pm", "name": "b", "url": "https://s.cn/d.html?paramid=pm"}]}), "utf-8")
    roster = tmp_path / "sources.yaml"
    roster.write_text(textwrap.dedent("""
        external_rosters:
          - path: desks/mt5/data/grounds.json
            rows: grounds
            id_style: ground
            defaults: {fetcher: owned, owner: deep_forest}
          - path: desks/mt5/data/lane.json
            rows: sources
            defaults: {fetcher: owned, owner: lane}
        sources: []
        """), "utf-8")
    got = {s.id: s for s in acq.load_roster(roster, root=tmp_path)}
    ground = got["ground:cn:七禾网_专访"]
    assert ground.owner == "deep_forest" and ground.aliases == ["hcn_interviews"]
    assert "hcn_interviews" not in got
    portal, rail = got["ground:cn:stats_portal"], got["cn_rail"]
    assert portal.shares_page == ["cn_rail"] and rail.shares_page == [portal.id]
    assert {"shfe_kx", "shfe_pm"} <= got.keys()          # the query separates two datasets


def test_two_countries_naming_one_vendor_page_stay_two_sources(tmp_path: Path) -> None:
    d = tmp_path / "r"
    d.mkdir()
    (d / "bo.json").write_text(json.dumps({"sources": [
        {"id": "pack_bo_la", "name": "licensed assessments", "region": "bo",
         "url": "https://vendor.com/assess"}]}), "utf-8")
    (d / "pe.json").write_text(json.dumps({"sources": [
        {"id": "pack_pe_la", "name": "licensed assessments", "region": "pe",
         "url": "https://vendor.com/assess"}]}), "utf-8")
    roster = tmp_path / "sources.yaml"
    roster.write_text("external_rosters:\n  - path: r/*.json\n    defaults: {fetcher: owned}\n"
                      "  - path: r/absent.json\n  - path: r/later.json\n"
                      "    pending: branch not merged\nsources: []\n", "utf-8")
    got = {s.id: s for s in acq.load_roster(roster, root=tmp_path)}
    assert {"pack_bo_la", "pack_pe_la"} <= got.keys() and not got["pack_bo_la"].aliases
    states = {r["path"]: r["state"] for r in acq.roster_files(roster, root=tmp_path)}
    assert states == {"r/*.json": "OK", "r/absent.json": "MISSING", "r/later.json": "PENDING"}


def test_the_live_roster_names_no_missing_file() -> None:
    bad = [r for r in acq.roster_files(root=ROOT) if r["state"] in ("MISSING", "BROKEN")]
    assert not bad, bad


def test_a_country_pack_that_will_not_load_is_loud(tmp_path: Path, monkeypatch: Any) -> None:
    """A pack that raises is an error on the roster entry (BROKEN), never a silent zero; a
    pack_cells-shape pack (no PACK export) is simply not a source table."""
    from libs.research import country_lab
    for cc, body in (("zz", "PACK = None\n"), ("yy", "KNOWN_GROUNDS = ()\n")):
        (tmp_path / "c" / cc).mkdir(parents=True)
        (tmp_path / "c" / cc / "pack.py").write_text(body, "utf-8")
    monkeypatch.setattr(country_lab, "resolve_pack",
                        lambda cc: (_ for _ in ()).throw(ImportError(f"no {cc}")))
    errs: list[dict[str, str]] = []
    assert acq.pack_rows(tmp_path / "c", errs) == []
    assert errs == [{"pack": "zz", "error": "ImportError: no zz"}]
    doc = {"external_rosters": [{"packs": "c"}]}
    (tmp_path / "r.yaml").write_text(json.dumps(doc), "utf-8")
    got = acq.roster_files(tmp_path / "r.yaml", root=tmp_path)
    assert got[0]["state"] == "BROKEN" and got[0]["failed"] == 1


def test_one_video_is_one_url_key_and_an_endpoint_is_no_scope() -> None:
    for u in ("https://m.youtube.com/watch?v=AbC&t=3", "https://youtu.be/AbC?t=1",
              "https://www.youtube.com/shorts/AbC", "youtube.com/watch?v=AbC"):
        assert acq.canonical_url(u) == "youtube.com/watch?v=AbC", u
    idx = {"youtube.com": [("youtube.com/watch", "corpus")],
           "boj.or.jp": [("boj.or.jp/x/index.htm", "boj")]}
    assert MS.Pipeline.attribute_url("https://youtu.be/AbC", idx) == ""   # not a catch-all
    assert MS.Pipeline.attribute_url("https://boj.or.jp/x", idx) == "boj"  # the index's dir
