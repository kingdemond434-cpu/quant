"""THE FREE STACK, END TO END ON FIXTURES -- the parsers, the PIT store, the yield artifact, the
catalogue feed, the allocation state, the two alt families and the proposer's grid.

Every network response here is a FIXTURE (`fixtures/free_stack/MANIFEST.json` says which were
recorded live and which are hand-built in the documented response shape). The hunter is pointed
at a temp store, so nothing a test writes lands in the desk's own data or reports.
"""
from __future__ import annotations

import io
import json
import sys
import zipfile
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

_DESK = Path(__file__).resolve().parents[1]
_ROOT = _DESK.parent.parent
for _p in (str(_DESK), str(_DESK / "research"), str(_ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from libs.data import free_stack as fs  # noqa: E402

FIX = _DESK / "tests" / "fixtures" / "free_stack"
NOW = datetime(2026, 9, 30, 12, 0, tzinfo=UTC)


def _fx(name: str) -> bytes:
    return (FIX / name).read_bytes()


def _house_zip() -> bytes:
    xml = ("<FinancialDisclosure><Member><Last>X</Last><FilingType>P</FilingType>"
           "<FilingDate>9/21/2026</FilingDate><DocID>1</DocID></Member><Member><Last>Y</Last>"
           "<FilingType>O</FilingType><FilingDate>9/21/2026</FilingDate><DocID>2</DocID>"
           "</Member><Member><Last>Z</Last><FilingType>P</FilingType><FilingDate>9/22/2026"
           "</FilingDate><DocID>3</DocID></Member></FinancialDisclosure>")
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("2026FD.xml", xml)
    return buf.getvalue()


ROUTES: list[tuple[str, object]] = [
    ("rss.applemarketingtools.com", "apple_rss.synthetic.json"),
    ("m.weibo.cn", "weibo_search.synthetic.json"),
    ("xueqiu.com", "xueqiu_waf.synthetic.html"),
    ("zhihu.sogou.com", "sogou_zhihu.synthetic.html"),
    ("guba.eastmoney.com", "guba_list.synthetic.html"),
    ("example-ir.jp/ir/library/2026q1", "ir_doc_q1.synthetic.html"),
    ("example-ir.jp/ir/2025q4", "ir_doc_q4.synthetic.html"),
    ("example-ir.jp/ir/", "ir_page.synthetic.html"),
    ("trends.google.com/trends/api/explore", "trends_explore.synthetic.txt"),
    ("trends.google.com/trends/api/widgetdata", "trends_multiline.synthetic.txt"),
    ("disclosures-clerk.house.gov", _house_zip),
    ("house-stock-watcher", "stockwatcher.synthetic.json"),
    ("api.coinpaprika.com/v1/tickers/btc", "paprika_btc.synthetic.json"),
    ("api.coinpaprika.com/v1/global", "paprika_global.synthetic.json"),
    ("reddit.com", "reddit_new.synthetic.json"),
    ("t.me/s/", "telegram_preview.synthetic.html"),
    ("push2his.eastmoney.com", "eastmoney_kline.synthetic.json"),
    ("finance.sina.com.cn", "sina_futures.synthetic.txt"),
    ("api.tushare.pro", "tushare_index.synthetic.json"),
    ("awesome-alternative-data", "awesome_alt_data_README.recorded.md"),
    ("awesome-public-datasets", "awesome_public_datasets_economics.recorded.rst"),
]


def fixture_fetch(url: str, headers=None, body=None) -> bytes:
    for needle, target in ROUTES:
        if needle in url:
            return target() if callable(target) else _fx(str(target))
    raise fs.FetchError("http_403", url)


@pytest.fixture()
def store(tmp_path: Path):
    from free_stack_hunter import Store
    st = Store(tmp_path)
    (tmp_path / "data" / "universe").mkdir(parents=True)
    real = json.loads((_DESK / "data" / "universe" / "universe.json").read_text("utf-8"))
    (tmp_path / "data" / "universe" / "universe.json").write_text(json.dumps(real), "utf-8")
    return st


def _roster(tmp_path: Path, ids: list[str]) -> Path:
    doc = json.loads((_DESK / "data" / "free_stack_sources.json").read_text("utf-8"))
    rows = [r for r in doc["sources"] if r["id"] in ids]
    for r in rows:
        if r["id"] == "jp_ir_transcripts":
            r["companies"] = [{"name": "Toyota", "cfd": "Toyota",
                               "ir_url": "https://example-ir.jp/ir/index.html"}]
        if r["id"] == "coinpaprika":
            pass
    p = tmp_path / "roster.json"
    p.write_text(json.dumps({"sources": rows}, ensure_ascii=False), "utf-8")
    return p


# ------------------------------------------------------------------------------ roster ----
def test_roster_rows_carry_every_required_field_and_culture() -> None:
    from free_stack_hunter import load_roster
    rows, bad = load_roster()
    assert not bad
    ids = {r["id"] for r in rows}
    for need in ("app_rank_apple", "cn_weibo", "cn_xueqiu", "cn_zhihu", "jp_ir_transcripts",
                 "jp_patents", "gtrends", "congress_trades", "coinpaprika", "reddit",
                 "telegram", "akshare", "tushare", "baostock", "jqdatasdk",
                 "dataset_catalogues"):
        assert need in ids
    for r in rows:
        for k in ("source_culture", "participant_structure", "failure_mode_hypothesis"):
            assert r.get(k), (r["id"], k)
        assert r["participant_structure"] in (
            "retail_heavy", "institutional", "tax_driven", "policy_driven",
            "settlement_constrained", "physical_flow", "broker_specific", "mixed", "UNMEASURED")
        assert set(r["uses"]) >= {"direct", "indirect", "allocation"}
        for use in r["uses"].values():
            assert use.get("organ") or use.get("artifact")


def test_no_exchange_universe_in_the_roster() -> None:
    text = (_DESK / "data" / "free_stack_sources.json").read_text("utf-8").lower()
    for host in ("binance.com", "bybit.com", "okx.com", "hyperliquid"):
        assert host not in text


# ----------------------------------------------------------------------------- parsers ----
def test_app_ranks_map_publishers_to_cfds_and_proxies() -> None:
    rows = fs.parse_apple_rss(_fx("apple_rss.synthetic.json"), "us", "top-free")
    comp, idx, meta = fs.app_rank_scores(rows)
    assert comp["co_Alphabet-A"] == pytest.approx(99 / 100)
    assert "co_Pdd" in comp and "co_Nintendo" in comp and "co_AlibabaGroup" in comp
    assert meta["co_AlibabaGroup"]["event"] == ["AlibabaGroup"]
    assert "CHINAH" in meta["co_AlibabaGroup"]["hypothesis"]
    assert meta["co_Nintendo"]["hypothesis"][0] == "JPN225"
    assert "idx_US500" in idx and "idx_JPN225" in idx
    assert not any("Indie" in k for k in comp)


def test_bot_filter_drops_promotion_and_floods_and_counts_them() -> None:
    posts = [{"text": "加微信进群 牛股推荐", "author": "a"},
             *({"text": "same spam text here", "author": f"b{i}"} for i in range(3)),
             {"text": "黄金突破新高 看多", "author": "c", "followers": 300, "statuses": 50},
             {"text": "x", "author": "d"},
             {"text": "real post about oil", "author": "e", "followers": 3, "statuses": 9000}]
    kept, stats = fs.bot_filter(posts)
    assert [p["author"] for p in kept] == ["c"]
    assert stats["promotional_contact_bait"] == 1 and stats["copy_paste_flood"] == 3
    assert stats["empty_or_too_short"] == 1 and stats["follower_starved_high_volume"] == 1


def test_cn_sentiment_is_longest_match_and_names_its_method() -> None:
    score, method = fs.sentiment_cn("暴跌")
    assert score == -1.0
    if not fs.snownlp_available():
        assert method == "lexicon_cn_v1"
    assert fs.lexicon_counts("暴跌 下跌 大涨", fs.CN_POS, fs.CN_NEG) == (1, 2)


def test_weekly_index_publishes_closed_weeks_only() -> None:
    rows = [{"topic": "BABA", "day": "2026-09-22", "score": 0.5},
            {"topic": "BABA", "day": "2026-09-23", "score": -0.5},
            {"topic": "BABA", "day": "2026-09-29", "score": 1.0}]
    out = fs.weekly_index(rows, date(2026, 9, 30))
    assert {o["period_end"] for o in out} == {"2026-09-27"}
    posts = next(o for o in out if o["key"] == "BABA_posts")
    assert posts["value"] == 2


def test_trends_column_is_a_within_response_log_change() -> None:
    pts = fs.parse_trends_multiline(_fx("trends_multiline.synthetic.txt"))
    assert len(pts) == 5                       # the partial last point is dropped
    assert fs.parse_trends_explore(_fx("trends_explore.synthetic.txt")).get("token") == "TOK"


def test_congress_is_dated_by_disclosure_and_mapped() -> None:
    tx = fs.parse_stockwatcher(_fx("stockwatcher.synthetic.json"))
    assert {t["disclosed"] for t in tx} == {"2026-09-21", "2026-09-22"}
    assert len(fs.parse_house_fd_index(_house_zip())) == 3


def test_catalogue_refuses_exchange_hosts_and_reads_rst_and_md() -> None:
    md = fs.parse_catalogue(_fx("awesome_alt_data_README.recorded.md"), "alt")
    rst = fs.parse_catalogue(_fx("awesome_public_datasets_economics.recorded.rst"), "apd")
    assert len(md) > 20 and len(rst) > 5
    assert not any("/apd-core/" in d["url"] for d in rst)
    assert fs.score_dataset({"url": "https://www.binance.com/api", "name": "x"})[1]
    assert fs.score_dataset({"url": "https://fred.stlouisfed.org", "name": "macro rates"})[0] > 0


def test_patent_momentum_per_company_is_month_end_dated() -> None:
    rows = fs.parse_patent_table(_fx("patents.synthetic.tsv"))
    obs, meta = fs.patent_momentum(rows)
    toy = [o for o in obs if o["key"] == "Toyota_mom"]
    assert toy and all(o["period_end"].endswith(("-30", "-31", "-28", "-29")) for o in toy)
    assert meta["Toyota_mom"]["event"] == ["Toyota"]
    assert "JPN225" in meta["jp_all_mom"]["hypothesis"]


# ------------------------------------------------------------------------------ PIT store ----
def test_pit_store_backfill_then_watched_then_revision(tmp_path: Path) -> None:
    from free_stack_hunter import first_vintage_frame, load_obs, merge_obs
    p = tmp_path / "o.jsonl"
    c1 = merge_obs(p, [{"key": "a", "period_end": "2026-09-01", "value": 1.0}], now=NOW,
                   lag_h=24)
    assert c1 == {"added": 1}
    later = NOW + timedelta(days=1)
    merge_obs(p, [{"key": "a", "period_end": "2026-09-01", "value": 2.0},
                  {"key": "a", "period_end": "2026-09-29", "value": 3.0}], now=later, lag_h=24)
    rows = load_obs(p)
    assert rows[0]["vintage"] == "backfill"
    assert rows[0]["available_time"].startswith("2026-09-02")          # period end + lag
    assert rows[1]["vintage"] == "revision"
    new = next(r for r in rows if r["period_end"] == "2026-09-29")
    assert new["available_time"] >= later.isoformat()[:19]          # cannot precede first sight
    df = first_vintage_frame(p)
    assert float(df.loc[df["period_end"] == "2026-09-01", "a"].iloc[0]) == 1.0   # first vintage


# ------------------------------------------------------------------------------- the pass ----
def test_hunter_pass_on_fixtures_writes_yield_series_catalogue_and_state(store, tmp_path,
                                                                         monkeypatch) -> None:
    from free_stack_hunter import run
    monkeypatch.delenv("TUSHARE_TOKEN", raising=False)
    ids = ["app_rank_apple", "cn_weibo", "cn_xueqiu", "cn_guba", "cn_zhihu",
           "jp_ir_transcripts", "jp_patents", "gtrends", "congress_trades", "coinpaprika",
           "reddit", "telegram", "akshare", "tushare", "baostock", "dataset_catalogues"]
    roster = _roster(tmp_path, ids)
    rep = run(budget_s=120, fetch=fixture_fetch, store=store, roster=roster, now=NOW,
              live=False)
    per = rep["per_source"]
    assert per["app_rank_apple"]["status"] == "OK"
    # the access classifier reads an authenticated route as PRIVATE (hard boundary); the pass
    # shows that verdict and never runs the source
    for sid in ("tushare", "jp_patents", "baostock"):
        assert per[sid]["status"] == "REFUSED_HARD_BOUNDARY", sid
        assert per[sid]["attempts"] == 0 and per[sid]["last_error"], sid
    # DATA-24: AKShare's upstreams pass the terms gate first. Eastmoney is refused and Sina
    # unread, so the route sends nothing and says why -- never a silent empty, never a fixture yield
    assert per["akshare"]["status"].startswith("BLOCKED_ON_TERMS:"), per["akshare"]["status"]
    assert per["akshare"]["requests"] == 0 and "eastmoney" in per["akshare"]["last_error"]
    # every fetcher asks the gate first: guba (Eastmoney, refused), Reddit (project ban) and
    # Telegram (ToS bars scraping) are fenced at the roster row and never run
    for sid in ("cn_guba", "reddit", "telegram"):
        assert per[sid]["status"] == "BLOCKED_ON_TERMS:refused", sid
        assert per[sid]["requests"] == 0, sid
    assert "BANNED_BY_PROJECT" in per["reddit"]["last_error"]
    lic = json.loads(store.licence.read_text("utf-8"))
    assert {u["source_id"] for u in lic["upstreams"]} >= {"akshare", "tushare", "baostock"}
    assert per["congress_trades"]["status"] == "OK"
    assert per["coinpaprika"]["status"] == "OK"
    assert per["dataset_catalogues"]["status"] == "OK"
    # a live yield is never claimed from a fixture run
    assert per["app_rank_apple"]["yield_24h"] == "UNMEASURED"
    assert not store.runs.exists()
    # series the families read
    assert (store.series / "fs_app_rank_apple.parquet").exists()
    cols = json.loads(store.columns.read_text("utf-8"))
    from research.universe_policy import may_hypothesise
    for sid, cs in cols.items():
        for meta in cs.values():
            assert all(may_hypothesise(s) for s in meta["hypothesis"]), sid
    assert "AlibabaGroup" not in cols["app_rank_apple"]["co_AlibabaGroup"]["hypothesis"]
    # catalogue into the #92 queue and the scout/prospector file, each row with its uses
    q = json.loads(store.world_queue.read_text("utf-8"))
    assert q["rows"] and all(set(r["uses"]) == {"direct", "indirect", "allocation"}
                             for r in q["rows"])
    assert all("source_culture" in r for r in q["rows"])
    cat = json.loads(store.catalogue.read_text("utf-8"))
    assert len(cat["rows"]) == len(q["rows"])
    # allocation state exists and is a state, never a size
    st = json.loads(store.alt_state.read_text("utf-8"))
    assert "never a size" in st["rule"]
    # the cursor holds the forum's seen ids; a second pass on the same fixtures adds no posts
    cur = json.loads(store.cursor.read_text("utf-8"))
    assert cur["cn_weibo"]["cursor"]["seen_ids"]
    rep2 = run(budget_s=120, fetch=fixture_fetch, store=store, roster=roster,
               now=NOW + timedelta(hours=5), only=["cn_weibo"], live=False)
    assert rep2["ran_this_pass"][0]["raw_rows"] == 0


def test_jp_patents_parse_a_bulk_file_from_the_inbox(store, tmp_path) -> None:
    inbox = store.inbox / "jp_patents"
    inbox.mkdir(parents=True)
    h = fs.fetch_jp_patents(fixture_fetch, {"id": "jp_patents"}, {}, NOW, inbox=inbox)
    assert h.status == "NEEDS_BULK_FILE"
    (inbox / "extract.tsv").write_bytes(_fx("patents.synthetic.tsv"))
    h = fs.fetch_jp_patents(fixture_fetch, {"id": "jp_patents"}, {}, NOW, inbox=inbox)
    assert h.status == "OK" and h.obs


def test_ir_tone_delta_needs_two_documents(store, tmp_path) -> None:
    row = {"id": "jp_ir_transcripts", "companies": [
        {"name": "Toyota", "cfd": "Toyota", "ir_url": "https://example-ir.jp/ir/index.html"}]}
    h = fs.fetch_jp_ir(fixture_fetch, row, {}, NOW)
    assert len(h.raw) == 2 and len(h.obs) == 1
    assert h.obs[0]["value"] < 0          # Q1 positive, then Q4 negative


# ------------------------------------------------------------------------------ families ----
def _bars(n: int = 900) -> pd.DataFrame:
    idx = pd.date_range("2026-01-01", periods=n, freq="h", tz="UTC")
    rng = np.random.default_rng(3)
    close = 100 + np.cumsum(rng.normal(0, 0.2, n))
    return pd.DataFrame({"open": close, "high": close + 0.3, "low": close - 0.3,
                         "close": close, "volume": 1.0}, index=idx)


def _series(root: Path, name: str, n: int = 80) -> None:
    days = pd.date_range("2026-01-01", periods=n, freq="D", tz="UTC")
    v = np.zeros(n)
    v[40:] = 5.0                                    # one step change -> one momentum crossing
    v += np.random.default_rng(1).normal(0, 0.05, n)
    df = pd.DataFrame({"period_end": days.strftime("%Y-%m-%d"),
                       "available_time": [d.isoformat() for d in days], "x": v})
    root.mkdir(parents=True, exist_ok=True)
    df.to_parquet(root / f"{name}.parquet", index=False)


def test_alt_series_momentum_fires_on_the_crossing_after_the_lag(tmp_path: Path) -> None:
    from mt5desk.family_alt_series import family_alt_series_momentum
    _series(tmp_path, "fs_t")
    sigs = family_alt_series_momentum(_bars(1600), source="fs_t", signal="x", lookback=1,
                                      threshold=2.0, z_window=30, series_root=tmp_path)
    assert sigs
    # 1600 hourly bars reach 2026-03-08, past the step. The step is published 2026-02-10 and
    # held back one publication day: the crossing fires
    # exactly at availability and never inside the lag (noise crossings elsewhere are allowed)
    step = pd.Timestamp("2026-02-10", tz="UTC")
    step_avail = step + pd.Timedelta(hours=24)
    times = [s.time for s in sigs]
    assert step_avail in times
    assert not [t for t in times if step <= t < step_avail]
    assert family_alt_series_momentum(_bars(), source="absent", signal="x",
                                      series_root=tmp_path) == []


def test_alt_conditioned_is_a_subset_of_its_base(tmp_path: Path) -> None:
    from mt5desk.families import get_family_func
    from mt5desk.family_alt_series import family_alt_conditioned
    _series(tmp_path, "fs_t")
    bars = _bars()
    base = get_family_func("trend_ma_cross")(bars)
    hi = family_alt_conditioned(bars, base_family="trend_ma_cross", source="fs_t", signal="x",
                                regime="high", threshold=0.5, z_window=30, series_root=tmp_path)
    base_times = {s.time for s in base}
    assert all(s.time in base_times for s in hi)
    assert family_alt_conditioned(bars, base_family="carry", source="fs_t", signal="x",
                                  series_root=tmp_path) == []


def test_families_are_registered_where_the_gauntlet_looks() -> None:
    from mt5desk.families_orthogonal import ORTHOGONAL_FAMILIES
    from research.axis_registry import FAMILY_TABLE
    for fam in ("alt_series_momentum", "alt_conditioned"):
        assert fam in ORTHOGONAL_FAMILIES and fam in FAMILY_TABLE


# ------------------------------------------------------------------------------ proposer ----
def test_proposer_grid_has_direct_and_indirect_arms_with_culture(monkeypatch, tmp_path) -> None:
    import free_stack_proposer as P
    monkeypatch.setattr(P, "series_exists", lambda sid: True)
    cols = {"gtrends": {"GOLD_tone": {"hypothesis": ["XAUUSD"], "event": [], "why": "t"}}}
    grid, skipped = P.build_grid(cols, P.roster_rows())
    assert not skipped
    fams = {c["family"] for c in grid}
    assert fams == {"exogenous_conditioner", "alt_series_momentum", "alt_conditioned"}
    assert len(grid) == len(P.CHARTS) * (8 + 8 + len(P.BASES) * len(P.REGIMES))
    for c in grid:
        assert c["source_culture"] == "US" and c["participant_structure"] == "retail_heavy"
        assert c["failure_mode_hypothesis"]
        assert c["params"]["source"] == "fs_gtrends" and c["symbol"] == "XAUUSD"
    # Reddit is a standing project ban: its archived columns never mint
    grid2, skipped2 = P.build_grid({"reddit": cols["gtrends"]}, P.roster_rows())
    assert not grid2 and skipped2["reddit"].startswith("BLOCKED_ON_TERMS:refused")


# --------------------------------------------------------------------------- benchmark ----
def test_factory_throughput_reads_the_factory_report_and_journal() -> None:
    import factory_throughput as T
    rep = {"status": "RAN", "seconds": 180.0, "generated_at": "x",
           "cells": {"tier0": {"evaluated": 3600}, "tier1": {"evaluated": 1800},
                     "deferred_to_judge": 1790, "survivors": 10},
           "stage_seconds": {"evaluate": 90.0, "tier1_backtest_oos": 30.0}}
    t = datetime(2026, 9, 30, tzinfo=UTC)
    rows = [{"key": "k1", "at": t.isoformat(), "to": "SCREENED"},
            {"key": "k1", "at": (t + timedelta(minutes=1)).isoformat(), "to": "QUEUED"},
            {"key": "k1", "at": (t + timedelta(hours=30)).isoformat(), "to": "FAILED"},
            {"key": "k2", "at": t.isoformat(), "to": "QUEUED"}]
    doc = T.build(t + timedelta(hours=48), report=rep, rows=rows)
    assert doc["factory"]["per_compute_hour"]["backtested_oos"] == 36000
    assert doc["benchmark"]["candidates_per_hour"] == 32
    assert doc["latency"]["judged"] == 1 and doc["latency"]["awaiting_verdict"]["n"] == 1
    assert doc["bottleneck"]["where"].startswith("judge queue")
    assert T.build(report=None, rows=[])["factory"]["status"] == "UNMEASURED"


def test_pick_parent_weights_are_unchanged_by_the_cache() -> None:
    import expression_factory as X

    from libs.research import alpha_dsl as dsl
    from libs.research import alpha_grammar as ag
    fams = X.FamilyTrials(Path("/nonexistent/trial_families.json"))
    parents = [X.Parent(f"canon:{k}", e, "canon") for k, e in list(ag.CANON.items())[:6]]
    fams.charge(parents[0].expr, n=3)
    archive = {X.Cell(p.expr, "", X.HORIZONS[0]).descriptor(): {} for p in parents[:2]}
    for p in parents:
        d = X.Cell(p.expr, "", X.HORIZONS[0]).mechanism().split("/")[0]
        n = sum(1 for k in archive if k.startswith(d))
        compute = 1.0 + ag.complexity(p.expr) / 10.0
        data = 1.0 + len(ag.terminals_in(p.expr) & set(ag.EXTERNAL_TERMINALS))
        trial = 1.0 + np.log1p(fams.pass_charges.get(dsl.family_key(p.expr), 0))
        want = (0.5 / 10.0) * 1e-4 * (1.0 / (1 + n)) * 0.5 * 1.0 / (compute + data + trial + 1.0)
        assert p.value(fams, n) == pytest.approx(want)
        assert p.static_terms()[3] == d


def test_data_scout_and_prospector_read_the_discovered_catalogue(tmp_path, monkeypatch) -> None:
    import data_prospector as DP
    import data_scout as DS
    f = tmp_path / "cat.json"
    f.write_text(json.dumps({"rows": [{
        "source": "Some macro dataset (awesome)", "name": "Some macro dataset",
        "catalogue": "awesome", "access": "free", "pit_status": "UNMEASURED until ingested",
        "cadence": "unknown", "cost": 2.0, "how_to_fetch": "queue", "observables": ["macro"],
        "observable_class": "discovered_catalogue", "expected_alpha_value": 0.02,
        "url": "https://x.org/data"}]}), "utf-8")
    monkeypatch.setattr(DS, "DISCOVERED_CATALOGUE", f)
    monkeypatch.setattr(DP, "DISCOVERED", f)
    usable, _ = DS.validate_catalogue()
    assert any(r["source"] == "Some macro dataset (awesome)" for r in usable)
    assert any(r["name"].startswith("Some macro dataset") for r in DP._catalogue())
