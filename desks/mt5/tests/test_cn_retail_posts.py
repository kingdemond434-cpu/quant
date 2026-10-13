"""CN RETAIL POSTS AND CN PUBLIC STATE PAGES, ON FIXTURES ONLY -- no test here touches the network.

Boards: robots honoured before any request, a challenge page recorded METHOD_BLOCKED with its
evidence, raw rows landed point-in-time with every ugly row kept, the tone corpus in the cb_tone
convention, hourly series only over OBSERVED hours, the daily frame the attention admission test
reads, and the per-board artifact. State pages: Eastmoney Connect / limit pools / institutional
holdings and JiSiLu through the free-stack fetcher, with UNMEASURED never read as zero.
"""
from __future__ import annotations

import json
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

_DESK = Path(__file__).resolve().parents[1]
_ROOT = _DESK.parent.parent
for _p in (str(_DESK), str(_DESK / "research"), str(_ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import cn_retail_posts as crp  # noqa: E402

from libs.data import cn_sources as cn  # noqa: E402
from libs.data import free_stack as fs  # noqa: E402

FIX = _DESK / "tests" / "fixtures" / "cn_retail"
NOW = datetime(2026, 10, 13, 12, 0, tzinfo=UTC)          # 20:00 Beijing


def _fx(name: str) -> bytes:
    return (FIX / name).read_bytes()


class NoSleepPacer(crp.Pacer):
    def __init__(self) -> None:
        self.waits: list[tuple[str, float]] = []
        self.t = 0.0
        super().__init__(sleep=self._sleep, clock=lambda: self.t)

    def _sleep(self, s: float) -> None:
        self.waits.append(("sleep", s))
        self.t += s


def _boards(tmp: Path) -> Path:
    doc = {"targets": {
        "CN50": {"boards": [
            {"site": "guba", "board": "sz50_index", "role": "index", "codes": ["zssh000016"]},
            {"site": "guba", "board": "a50_moutai", "role": "constituent", "codes": ["600519"]},
            {"site": "xueqiu", "board": "xq_sz50", "role": "index", "codes": ["SH000016"]}]},
        "HK50": {"boards": [
            {"site": "guba", "board": "hsi_tencent", "role": "constituent",
             "codes": ["hk00700"]}]},
        "USDCNH": {"boards": [
            {"site": "guba", "board": "cnh", "role": "fx", "codes": ["USDCNH"]}]}}}
    p = tmp / "boards.json"
    p.write_text(json.dumps(doc, ensure_ascii=False), "utf-8")
    return p


class FakeNet:
    """Routes by URL; records every request so a test can prove what was NOT requested."""

    def __init__(self, network_down: tuple[str, ...] = ()) -> None:
        self.calls: list[str] = []
        self.network_down = network_down

    def __call__(self, url: str) -> tuple[int, bytes]:
        self.calls.append(url)
        for needle in self.network_down:
            if needle in url:
                raise OSError("Tunnel connection failed: 403 Forbidden")
        if url == "https://xueqiu.com/robots.txt":
            return 200, _fx("robots_xueqiu.recorded.txt")
        if url == "https://guba.eastmoney.com/robots.txt":
            return 200, _fx("robots_eastmoney.recorded.txt")
        if "list,zssh000016" in url:
            return 200, _fx("guba_list_json.synthetic.html") if url.endswith(
                "zssh000016.html") else b"<html><body></body></html>"
        if "list,600519" in url:
            return 200, _fx("guba_identity_check.synthetic.html")
        if "list,hk00700" in url:
            return 200, _fx("guba_list_table.synthetic.html") if url.endswith(
                "hk00700.html") else b"<html></html>"
        if "xueqiu.com" in url:
            return 200, _fx("xueqiu_waf.synthetic.html")
        return 404, b""


# ----------------------------------------------------------------------------- parsers ----
def test_robots_xueqiu_disallows_every_post_route_and_allows_html() -> None:
    txt = _fx("robots_xueqiu.recorded.txt").decode()
    assert not cn.robots_allows(txt, crp._list_url("xueqiu", "SH000016", 1))
    assert not cn.robots_allows(txt, "https://xueqiu.com/query/v1/search/status.json?q=x")
    assert not cn.robots_allows(txt, "https://xueqiu.com/stock/abc")
    assert cn.robots_allows(txt, "https://xueqiu.com/S/SH000016")
    assert not cn.robots_allows(txt, "https://xueqiu.com/S/SH000016", agent="ClaudeBot")
    em = _fx("robots_eastmoney.recorded.txt").decode()
    assert cn.robots_allows(em, "https://guba.eastmoney.com/list,600519.html")


def test_challenge_markers() -> None:
    assert "身份核实" in str(cn.challenge_of(_fx("guba_identity_check.synthetic.html")))
    assert "aliyun_waf" in str(cn.challenge_of(_fx("xueqiu_waf.synthetic.html")))
    assert cn.challenge_of(_fx("guba_list_json.synthetic.html")) is None


def test_guba_json_layout_keeps_ugly_rows_and_converts_beijing_time() -> None:
    rows = cn.parse_guba_list(_fx("guba_list_json.synthetic.html"), NOW)
    assert len(rows) == 8                                   # every row, ugly ones included
    r = next(x for x in rows if x["post_id"] == "1002")
    assert r["published_time"] == "2026-10-13T11:50:00+00:00"
    assert r["read_count"] == 1520 and r["reply_count"] == 12
    assert r["url"] == "https://guba.eastmoney.com/news,zssh000016,1002.html"
    assert next(x for x in rows if x["post_id"] == "1003")["read_count"] == 12000
    ugly = next(x for x in rows if x["post_id"] == "1005")
    assert ugly["published_time"] is None
    assert {"time_unparsed", "read_count_missing", "reply_count_missing",
            "title_empty"} <= set(ugly["parse_flags"])


def test_guba_html_layout_flags_last_update_time_and_inferred_year() -> None:
    rows = cn.parse_guba_list(_fx("guba_list_table.synthetic.html"), NOW)
    assert len(rows) == 2
    a, b = rows
    assert a["title"] == "腾讯&回购继续" and a["read_count"] == 2310 and a["post_id"] == "555"
    assert {"time_is_last_update", "year_inferred"} <= set(a["parse_flags"])
    assert a["published_time"] == "2026-10-13T11:30:00+00:00"
    assert b["read_count"] is None and "time_unparsed" in b["parse_flags"]


def test_free_stack_guba_parser_is_the_shared_one() -> None:
    raw = (_DESK / "tests" / "fixtures" / "free_stack" / "guba_list.synthetic.html").read_bytes()
    posts = fs.parse_guba(raw, NOW)
    assert [p["id"] for p in posts] == ["gb900", "gb901"]
    assert posts[0]["created"] == "2026-09-21T13:00:00+00:00"


def test_pacer_holds_three_seconds_per_host() -> None:
    p = NoSleepPacer()
    p.wait("a.example")
    p.wait("b.example")
    p.wait("a.example")
    assert p.waits == [("sleep", 3.0)]


# ---------------------------------------------------------------------------- the pass ----
@pytest.fixture()
def paths(tmp_path: Path) -> dict[str, Path]:
    return {"store": tmp_path / "store", "series": tmp_path / "series",
            "out": tmp_path / "CN_RETAIL_POSTS.json", "boards": _boards(tmp_path)}


def _run(paths: dict[str, Path], net: FakeNet, now: datetime = NOW) -> dict:
    return crp.run(now, fetch=net, store=paths["store"], boards_path=paths["boards"],
                   series_dir=paths["series"], out=paths["out"], pacer=NoSleepPacer())


def test_pass_statuses_evidence_and_what_was_never_requested(paths) -> None:
    net = FakeNet(network_down=("list,USDCNH",))
    rep = _run(paths, net)
    by = {r["board"]: r for r in rep["boards"]}
    assert by["sz50_index"]["status"] == "COLLECTING"
    assert by["sz50_index"]["posts_landed"] == 8
    assert by["a50_moutai"]["status"] == "METHOD_BLOCKED"
    assert "身份核实" in by["a50_moutai"]["evidence"] and "sha256" in by["a50_moutai"]["evidence"]
    # Xueqiu: robots disallows the post route, so no request was ever made to it
    assert by["xq_sz50"]["status"] == "METHOD_BLOCKED"
    assert "robots.txt" in by["xq_sz50"]["evidence"]
    assert not [u for u in net.calls if "xueqiu.com/query" in u]
    # a network failure is UNMEASURED, never a verdict and never zero
    assert by["cnh"]["status"] == "UNMEASURED" and "network" in by["cnh"]["evidence"]
    assert by["cnh"]["series_length_hours"] == "UNMEASURED"
    assert json.loads(paths["out"].read_text("utf-8"))["boards"]
    assert rep["sites"]["xueqiu"]["terms_quote"] and rep["sites"]["guba"]["basis"]


def test_raw_rows_are_pit_stamped_and_the_tone_corpus_matches_cb_tone(paths) -> None:
    _run(paths, FakeNet())
    raw = [json.loads(x) for x in (paths["store"] / "raw" / "2026-10-13.jsonl")
           .read_text("utf-8").splitlines()]
    assert len(raw) == 8 + 2                       # json board + html board, ugly rows kept
    for r in raw:
        assert r["available_time"] == "2026-10-13T12:00:00+00:00"
        assert len(r["source_hash"]) == 64 and "published_time" in r
    assert any(r["parse_flags"] for r in raw)
    corpus = [json.loads(x) for x in (paths["store"] / "posts.jsonl").read_text("utf-8")
              .splitlines()]
    for need in ("date", "title", "url", "published_utc", "link", "instruments", "text",
                 "available_time", "source_hash", "lang"):
        assert all(need in c for c in corpus), need
    html_row = next(c for c in corpus if c["board"] == "hsi_tencent" and c["post_id"] == "555")
    assert html_row["published_utc"] is None        # a last-update time is not a publish time


def test_hourly_series_counts_only_observed_hours_and_dedups(paths) -> None:
    _run(paths, FakeNet())
    rep2 = _run(paths, FakeNet(), NOW + timedelta(hours=1))
    assert all(r["posts_landed_this_pass"] == 0 for r in rep2["boards"])   # seen before
    import pandas as pd
    hourly = pd.read_parquet(paths["series"] / "cn_retail_CN50_hourly.parquet")
    # window start = max(third-oldest publish 08:10, third-oldest last reply 08:40) UTC -- the
    # pinned 2025 post is ignored -- so 09:00 is the first fully observed hour; the HTML
    # (last-update) board observes nothing
    assert hourly["period"].iloc[0] == "2026-10-13T09:00:00+00:00"
    assert hourly["period"].iloc[-1] == "2026-10-13T12:00:00+00:00"
    first = hourly.iloc[0]
    assert first["posts"] == 1 and first["available_time"] == "2026-10-13T12:00:00+00:00"
    eleven = hourly[hourly["period"] == "2026-10-13T11:00:00+00:00"].iloc[0]
    assert eleven["posts"] == 2 and eleven["replies"] == 52
    assert not (paths["series"] / "cn_retail_HK50_hourly.parquet").exists()


def test_hours_no_fetch_covered_are_absent_not_zero() -> None:
    log = [{"site": "guba", "board": "b", "at": "2026-10-13T12:00:00+00:00", "state": "OK",
            "n_rows": 3, "n_publish_time": 3, "window_start": "2026-10-13T10:30:00+00:00"},
           {"site": "guba", "board": "b", "at": "2026-10-13T20:00:00+00:00", "state": "OK",
            "n_rows": 3, "n_publish_time": 3, "window_start": "2026-10-13T18:00:00+00:00"}]
    cov = crp.board_hours(log)[("guba", "b")]
    hours = sorted(h.hour for h in cov)
    assert hours == [11, 18, 19]                       # 12:00-17:59 never observed


def test_daily_frame_needs_observed_hours_and_history() -> None:
    rows = []
    for d in range(14):
        for h in range(24):
            ts = datetime(2026, 9, 1 + d, h, tzinfo=UTC)
            rows.append({"period": ts.isoformat(), "available_time": ts.isoformat(),
                         "posts": 2 + (10 if d == 13 else 0), "boards_observed": 1,
                         "posts_per_board": 2 + (10 if d == 13 else 0)})
    rows = [r for r in rows if not (r["period"].startswith("2026-09-05")
                                    and int(r["period"][11:13]) < 6)]
    days = crp.daily_frame(rows)
    assert "2026-09-05" not in {d["day"] for d in days}       # 18 observed hours < 20
    assert days[-1]["post_volume_z"] is None or days[-1]["post_volume_z"] > 0
    assert all(d["post_volume_z"] is None for d in days[:crp.Z_MIN_PRIOR])


def test_attention_grid_reads_the_cn_retail_frame(tmp_path: Path) -> None:
    import nlp_social_cells as nsc
    import pandas as pd
    days = [{"day": f"2026-09-{d:02d}", "available_time": f"2026-09-{d:02d}T23:00:00+00:00",
             "post_volume_z": 0.1 * d} for d in range(1, 21)]
    pd.DataFrame(days).to_parquet(tmp_path / "cn_retail_HK50.parquet", index=False)
    _indices, pairs, history = nsc.build_grid(tmp_path)
    assert ("cnr:HK50.post_volume_z", "HK50") in pairs
    _ready, waiting = nsc.declared_cells(history, {"tests": []})
    cell = next(c for c in waiting if c["index"] == "cnr:HK50.post_volume_z")
    assert cell["not_ready"] == "WAITING_FOR_HISTORY"
    assert cell["params"]["transform"] == "level_z" and cell["params"]["side_when_high"] == -1


# ----------------------------------------------------------------------- state pages ----
def _state_fetch(routes: dict[str, bytes | Exception]):
    calls: list[str] = []

    def fetch(url, headers=None, body=None):
        calls.append(url)
        if url.endswith("/robots.txt"):
            raise fs.FetchError("http_404", url)
        for needle, out in routes.items():
            if needle in url:
                if isinstance(out, Exception):
                    raise out
                return out
        raise fs.FetchError("http_404", url)
    fetch.calls = calls  # type: ignore[attr-defined]
    return fetch


@pytest.fixture(autouse=True)
def _no_pace(monkeypatch) -> None:
    monkeypatch.setattr(fs, "CN_HOST_GAP_S", 0.0)


def test_connect_flows_tag_eastmoney_and_never_zero_a_missing_northbound_day() -> None:
    f = _state_fetch({"%22005%22": _fx("em_connect_north.synthetic.json"),
                      "%22006%22": _fx("em_connect_south.synthetic.json"),
                      "RPT_MUTUAL_DEAL_HISTORY": _fx("em_null_result.synthetic.json")})
    h = fs.fetch_cn_public_state(f, {"id": "em_connect_flows", "route": "em_connect"}, {}, NOW)
    assert h.status == "OK"
    keys = {o["key"] for o in h.obs}
    assert keys == {"south_net"}                            # northbound undisclosed: no zero
    assert any("UNMEASURED" in n for n in h.notes)
    assert all(r["source"] == "eastmoney" for r in h.raw)
    assert "source=eastmoney" in h.columns["south_net"]["why"]


def test_limit_pools_count_and_cursor() -> None:
    f = _state_fetch({"getTopicZTPool": _fx("em_zt_pool.synthetic.json"),
                      "getTopicDTPool": _fx("em_dt_pool.synthetic.json")})
    row = {"id": "em_limit_pools", "route": "em_limit_pools", "dates_per_pass": 2}
    h = fs.fetch_cn_public_state(f, row, {}, NOW)
    net = [o for o in h.obs if o["key"] == "limit_net"]
    assert [o["value"] for o in net] == [2.0, 2.0]
    assert "2026-10-13" not in h.cursor["dates_done"]      # today re-read until closed
    f2 = _state_fetch({"getTopicZTPool": _fx("em_pool_none.synthetic.json"),
                       "getTopicDTPool": _fx("em_pool_none.synthetic.json")})
    h2 = fs.fetch_cn_public_state(f2, row, {}, NOW)
    assert h2.obs == [] and h2.status == "EMPTY"           # no pool is not zero limit moves


def test_orghold_and_jisilu_index_and_guest_list() -> None:
    f = _state_fetch({"RPT_MAIN_ORGHOLD": _fx("em_orghold.synthetic.json"),
                      "index_history": _fx("jsl_index.synthetic.json"),
                      "cb_list_new": _fx("jsl_list_guest.synthetic.json")})
    h = fs.fetch_cn_public_state(f, {"id": "em_institution_hold", "route": "em_orghold",
                                     "codes": ["600519"]}, {}, NOW)
    assert {o["period_end"] for o in h.obs if o["key"] == "orghold_value"} == {
        "2026-06-30", "2026-03-31"}
    j = fs.fetch_cn_public_state(f, {"id": "jsl_cb_index", "route": "jsl_cb_index"}, {}, NOW)
    mid = {o["period_end"]: o["value"] for o in j.obs if o["key"] == "cb_mid_premium"}
    assert mid == {"2026-10-09": 30.1, "2026-10-12": 31.4}
    g = fs.fetch_cn_public_state(f, {"id": "jsl_cb_list", "route": "jsl_cb_list"}, {}, NOW)
    assert g.status == "METHOD_BLOCKED" and "游客" in g.detail
    ok = _state_fetch({"cb_list_new": _fx("jsl_list_ok.synthetic.json")})
    g2 = fs.fetch_cn_public_state(ok, {"id": "jsl_cb_list", "route": "jsl_cb_list"}, {}, NOW)
    vals = {o["key"]: o["value"] for o in g2.obs}
    assert vals["cbl_share_below_par"] == pytest.approx(1 / 3, abs=1e-3)
    assert vals["cbl_median_premium_rt"] == 25.0


def test_robots_refusal_and_challenge_are_method_blocked() -> None:
    def fetch(url, headers=None, body=None):
        if url.endswith("/robots.txt"):
            return b"User-agent: *\nDisallow: /webapi/\n"
        return _fx("xueqiu_waf.synthetic.html")
    h = fs.fetch_cn_public_state(fetch, {"id": "jsl_cb_index", "route": "jsl_cb_index"}, {},
                                 NOW)
    assert h.status == "METHOD_BLOCKED" and "disallows /webapi/" in h.detail
    h2 = fs.fetch_cn_public_state(fetch, {"id": "em_limit_pools", "route": "em_limit_pools",
                                          "dates_per_pass": 1}, {}, NOW)
    assert h2.status == "METHOD_BLOCKED" and "aliyun_waf" in h2.detail


def test_network_failure_is_unmeasured() -> None:
    f = _state_fetch({"index_history": fs.FetchError("proxy", "x")})
    h = fs.fetch_cn_public_state(f, {"id": "jsl_cb_index", "route": "jsl_cb_index"}, {}, NOW)
    assert h.status == "UNMEASURED"


def test_roster_registers_every_state_source_and_tushare_reads_needs_key(tmp_path) -> None:
    doc = json.loads((_DESK / "data" / "free_stack_sources.json").read_text("utf-8"))
    ids = {r["id"]: r for r in doc["sources"]}
    for sid in crp.CN_STATE_IDS:
        assert sid in ids, sid
    for sid in ("em_connect_flows", "em_limit_pools", "em_institution_hold", "jsl_cb_index",
                "jsl_cb_list"):
        assert ids[sid]["kind"] == "cn_public_state" and ids[sid]["route"]
    assert "cn_public_state" in fs.FETCHERS
    y = tmp_path / "y.json"
    y.write_text(json.dumps({"per_source": {
        "jsl_cb_list": {"status": "METHOD_BLOCKED", "last_error": "guest-limited"},
        "em_limit_pools": {"status": "OK", "obs_total": 12, "columns": 3}}}), "utf-8")
    rows = {r["id"]: r for r in crp.state_sources(yield_path=y, env={})}
    assert rows["tushare"]["access_state"] == "NEEDS_KEY"
    assert rows["jsl_cb_list"]["access_state"] == "METHOD_BLOCKED"
    assert rows["em_limit_pools"]["access_state"] == "COLLECTING"
    assert rows["em_connect_flows"]["access_state"] == "UNMEASURED"


def test_no_exchange_hosts_in_this_lane() -> None:
    text = (Path(crp.__file__).read_text("utf-8")
            + (_DESK / "data" / "cn_retail_boards.json").read_text("utf-8")).lower()
    for host in ("binance", "bybit", "okx.com", "hyperliquid"):
        assert host not in text
