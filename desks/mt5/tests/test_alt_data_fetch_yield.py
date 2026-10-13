"""Alt-data miners that actually yield (2026-09-30): polite concurrent fetch, the regional
resolution chain, the deep-forest checkpoint + least-recently-attempted scheduler, the forest legs
mining their own grounds, and ALT_DATA_YIELD.json. No test opens a socket: every fetch seam is
replaced by a fixture."""
from __future__ import annotations

import gzip
import io
import json
import ssl
import sys
import threading
import time
import urllib.error
from datetime import UTC, datetime
from pathlib import Path

import pytest

_DESK = Path(__file__).resolve().parents[1]
_ROOT = _DESK.parents[1]
for _p in (str(_DESK), str(_DESK / "research"), str(_DESK / "side_channels"), str(_ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import regional_survivor_hunters as rsh  # noqa: E402

from libs.data import polite_fetch as pf  # noqa: E402
from libs.research import hunt_frontier as hf  # noqa: E402
from research import alt_data_yield as ady  # noqa: E402
from research import deep_forest_miner as dfm  # noqa: E402
from research import forest_runner as fr  # noqa: E402


# ----------------------------------------------------------------------------- polite_fetch
class _Resp(io.BytesIO):
    def __init__(self, body: bytes, status: int = 200, headers: dict | None = None,
                 url: str = "") -> None:
        super().__init__(body)
        self.status = status
        self.url = url
        self.headers = headers or {}

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


def _http_error(url: str, code: int, headers: dict | None = None) -> urllib.error.HTTPError:
    return urllib.error.HTTPError(url, code, f"HTTP {code}", headers or {}, None)  # type: ignore[arg-type]


def test_get_retries_a_503_then_reads_the_page_and_counts_it() -> None:
    calls: list[str] = []
    errors: list[urllib.error.HTTPError] = []

    def opener(req, timeout, context):
        calls.append(req.full_url)
        if len(calls) == 1:
            errors.append(_http_error(req.full_url, 503))
            raise errors[-1]
        return _Resp(b"<html>ok</html>", headers={"Content-Type": "text/html; charset=utf-8"})

    pf.reset_stats("t1")
    r = pf.get("https://a.test/x", leg="t1", opener=opener, gate=None, sleep=lambda s: None)
    assert r.ok and r.text == "<html>ok</html>" and r.attempts == 2 and len(calls) == 2
    s = pf.stats("t1")
    assert s["fetches"] == 2 and s["ok"] == 1 and s["http_errors"] == 1 and s["retries"] == 1
    assert errors[0].fp.closed


def test_a_404_is_deterministic_and_is_not_hammered() -> None:
    calls: list[int] = []
    errors: list[urllib.error.HTTPError] = []

    def opener(req, timeout, context):
        calls.append(1)
        errors.append(_http_error(req.full_url, 404))
        raise errors[-1]

    r = pf.get("https://a.test/moved", opener=opener, gate=None, sleep=lambda s: None, retries=3)
    assert not r.ok and r.status == 404 and len(calls) == 1
    assert errors[0].fp.closed


def test_a_certificate_the_trust_stores_reject_is_reported_not_retried() -> None:
    calls: list[int] = []

    def opener(req, timeout, context):
        calls.append(1)
        assert isinstance(context, ssl.SSLContext) and context.verify_mode == ssl.CERT_REQUIRED
        raise urllib.error.URLError(ssl.SSLCertVerificationError(1, "bad chain"))

    r = pf.get("https://tls.test/", opener=opener, gate=None, sleep=lambda s: None, retries=3)
    assert not r.ok and "SSLCertVerificationError" in r.error and len(calls) == 1


def test_gbk_and_gzip_pages_decode_by_their_own_charset() -> None:
    page = '<html><meta charset="gbk"><p>黄金夜盘做多</p></html>'.encode("gbk")
    assert "黄金夜盘做多" in pf.decode_body(page)
    assert "黄金夜盘做多" in pf.decode_body(gzip.compress(page), "", "gzip")
    sj = "ドル円 仲値".encode("shift_jis")
    assert pf.decode_body(sj, "text/html; charset=Shift_JIS") == "ドル円 仲値"


def test_the_host_gate_spaces_one_host_and_leaves_others_free() -> None:
    gate = pf.HostGate(default_s=5.0)
    assert gate.reserve("a.test") == 0.0
    assert gate.reserve("a.test") > 4.0          # second call to the same host waits its turn
    assert gate.reserve("b.test") == 0.0         # another host does not


def test_run_concurrently_overlaps_waits() -> None:
    t0 = time.monotonic()
    out = pf.run_concurrently(range(8), lambda i: (time.sleep(0.2), i)[1], workers=8)
    assert [o[1] for o in out] == list(range(8)) and time.monotonic() - t0 < 1.0


# ----------------------------------------------------------------------------- regional
_NEXT = ('<html><script id="__NEXT_DATA__" type="application/json">'
         + json.dumps({"props": {"pageProps": {"providers": [
             {"nickname": "AlphaFX", "profitPercent": 42.5, "maxDrawdown": 11.0,
              "followers": 120},
             {"nickname": "Beta", "profitPercent": 9.1, "maxDrawdown": 3.2, "followers": 7}]}}})
         + "</script></html>")


def test_a_js_app_is_read_from_its_own_hydration_payload() -> None:
    recs = rsh.embedded_records(_NEXT)
    rows = rsh.records_to_rows("equiti_copy", recs, "MENA", "A", "en")
    assert [r["title"] for r in rows] == ["AlphaFX", "Beta"]
    assert rows[0]["stats"]["return_pct"] == 42.5 and rows[0]["stats"]["drawdown_pct"] == 11.0


def test_a_js_app_without_payload_is_resolved_through_the_api_its_bundle_names(monkeypatch) -> None:
    shell = '<html><div id="root"></div><script src="/static/app.123.js"></script></html>'
    bundle = 'fetch("/api/v2/rating/traders?limit=50");fetch("/api/auth/login")'
    api = json.dumps({"data": {"items": [{"name": "Gamma", "gain": 31.0, "drawdown": 8.0}]}})
    seen: list[str] = []

    def fake(url, timeout=0, *, referer="", accept_json=False):
        seen.append(url)
        if url.endswith(".js"):
            return bundle
        if "/api/v2/rating/traders" in url:
            return api
        raise rsh.FetchError(url, 404, "HTTP 404")

    monkeypatch.setattr(rsh, "fetch", fake)
    eps = rsh.discover_endpoints("https://copy.test/", shell)
    assert eps[0].startswith("https://copy.test/api/v2/rating/traders")   # ranked over auth
    recs = rsh.try_json_routes("https://copy.test/", shell)
    assert recs and recs[0]["name"] == "Gamma"


def test_tables_and_repeated_cards_are_read_in_any_language() -> None:
    table = ("<table><tr><th>Трейдер</th><th>Доходность</th><th>Просадка</th></tr>"
             "<tr><td><a href='/t/1'>Ivan</a></td><td>55.2%</td><td>12%</td></tr>"
             "<tr><td>Olga</td><td>18.0%</td><td>4%</td></tr></table>")
    rows = rsh.parse_tables("share4you", table, "https://s.test/", "CIS")
    assert [r["title"] for r in rows] == ["Ivan", "Olga"]
    assert rows[0]["stats"].get("return_pct") == 55.2 and rows[0]["url"] == "https://s.test/t/1"
    cards = "".join(f'<div class="trader-box"><span>Trader{i}</span><b>Retorno</b> {10 + i}.5%'
                    f"</div>" for i in range(4))
    got = rsh.parse_repeated_cards("mylivefx_br", "<html>" + cards + "</html>",
                                   "https://m.test/", "Brazil")
    assert len(got) == 4 and got[0]["title"] == "Trader0" and got[0]["nearby_pcts"][0] == 10.5


def test_a_moved_listing_is_resolved_through_an_alternate_and_remembered(monkeypatch,
                                                                          tmp_path) -> None:
    for name in ("STATE", "COVERAGE", "BLOCKED", "RUNS", "INTEL", "YIELD_OUT"):
        target = tmp_path / ("intel" if name == "INTEL" else f"{name.lower()}.json")
        monkeypatch.setattr(rsh, name, target)
    (tmp_path / "intel").mkdir()
    table = ("<table><tr><th>Trader</th><th>Profit</th></tr>"
             "<tr><td>Leader1</td><td>21%</td></tr><tr><td>Leader2</td><td>7%</td></tr></table>")

    def fake(url, timeout=0, *, referer="", accept_json=False):
        if url.startswith("https://www.share4you.com/en/leaders?page="):
            raise rsh.FetchError(url, 404, "HTTP 404")
        if url == "https://www.share4you.com/en/leaders/":
            return table
        if "fbs.com" in url:
            return "<html></html>"
        raise rsh.FetchError(url, 403, "HTTP 403")

    monkeypatch.setattr(rsh, "fetch", fake)
    monkeypatch.setattr(rsh, "SOURCES", {k: rsh.SOURCES[k] for k in ("share4you", "hfm_pamm")})
    import research.alt_data_yield as ady_mod
    monkeypatch.setattr(ady_mod, "COMPUTE_LEDGER", tmp_path / "none.jsonl")
    res = rsh.run_and_save(budget_s=60, workers=2)
    assert res["share4you"]["count"] == 2 and res["hfm_pamm"]["count"] == 0
    st = json.loads((tmp_path / "state.json").read_text("utf-8"))
    assert st["_resolved"]["share4you"] == "https://www.share4you.com/en/leaders/"
    cov = json.loads((tmp_path / "coverage.json").read_text("utf-8"))["platforms"]
    assert cov["share4you"]["successes"] == 1 and cov["share4you"]["rows_total"] == 2
    assert cov["share4you"]["last_via"] == "table" and cov["share4you"]["last_error"] == ""
    assert cov["hfm_pamm"]["successes"] == 0 and "403" in cov["hfm_pamm"]["last_error"]
    blocked = json.loads((tmp_path / "blocked.json").read_text("utf-8"))
    assert "hfm_pamm" in blocked["sources"] and "share4you" not in blocked["sources"]
    run = json.loads((tmp_path / "runs.json").read_text("utf-8").splitlines()[-1])
    assert run["leg"] == "regional_survivor_hunters" and run["rows"] == 2
    art = json.loads((tmp_path / "yield_out.json").read_text("utf-8"))
    assert art["platforms"]["rows_by_platform"]["share4you"]["rows"] == 2
    assert (tmp_path / "intel" / "share4you").is_dir()      # the compiler's donation root


# ----------------------------------------------------------------------------- deep forest
def _isolate(monkeypatch, tmp_path: Path) -> None:
    for name, fname in (("CLAIMS", "claims.jsonl"), ("SEEN", "seen.json"),
                        ("REPORT", "DEEP_FOREST.json"), ("PROVENANCE", "mined.jsonl"),
                        ("DATASETS", "datasets.jsonl"), ("WORLD", "world"),
                        ("SOURCES", "src.json")):
        monkeypatch.setattr(dfm, name, tmp_path / fname)
    monkeypatch.setattr(dfm, "RAW_VAULT", tmp_path / "vault")
    monkeypatch.setattr(dfm, "_feed_frontier", lambda urls: len(urls))
    monkeypatch.setattr(dfm, "_universe", lambda: {"XAUUSD", "EURUSD"})
    monkeypatch.setattr(dfm.time, "sleep", lambda s: None)
    monkeypatch.setattr(dfm._Run, "rendered", lambda self, url: "")
    import research.regime_coverage as rc
    monkeypatch.setattr(rc, "_merge_into_queue", lambda tasks, source="x": None)
    monkeypatch.setattr(ady, "COMPUTE_LEDGER", tmp_path / "none.jsonl")
    monkeypatch.setattr(ady, "COVERAGE", tmp_path / "none.json")
    monkeypatch.setattr(ady, "ACQUIRED", tmp_path / "none_registry.json")
    monkeypatch.setattr(ady, "CANDIDATES", tmp_path / "none_candidates.json")
    dfm._CC_STATE.clear()


_PAGE = ("<html><title>t</title><body><p>"
         + "黄金在夜盘开盘后前30分钟顺势做多。次日延续上涨概率高。" * 60 + "</p></body></html>")


def test_least_recently_attempted_ground_is_scheduled_first_inside_a_bucket() -> None:
    grounds = [{"name": n, "region": "cn", "route": "http", "url": f"https://{n}.test/"}
               for n in ("fresh", "old", "older")]
    state = hf.VectorState(vectors={
        "fresh": hf.Vector("fresh", outcome="EMPTY", first_seen="2026-09-01T00:00:00+00:00",
                           last_attempt="2026-09-29T00:00:00+00:00", attempts=3),
        "old": hf.Vector("old", outcome="EMPTY", first_seen="2026-09-01T00:00:00+00:00",
                         last_attempt="2026-09-10T00:00:00+00:00", attempts=1),
        "older": hf.Vector("older", outcome="EMPTY", first_seen="2026-09-01T00:00:00+00:00",
                           last_attempt="2026-09-02T00:00:00+00:00", attempts=1)})
    for cursor in range(3):                      # whatever the cursor, oldest first
        order = [g["name"] for g in dfm.schedule(grounds, cursor, frontier_state=state)]
        assert order == ["older", "old", "fresh"], order


def test_a_concurrent_run_reaches_every_ground_and_checkpoints_each_one(monkeypatch,
                                                                          tmp_path) -> None:
    _isolate(monkeypatch, tmp_path)
    grounds = [{"name": f"g{i}", "region": "cn", "language": "zh", "route": "http",
                "url": f"https://h{i}.test/", "kind": "forum"} for i in range(24)]
    (tmp_path / "src.json").write_text(json.dumps({"grounds": grounds}), "utf-8")
    active = {"now": 0, "peak": 0}
    lock = threading.Lock()

    def slow(url, **kw):
        with lock:
            active["now"] += 1
            active["peak"] = max(active["peak"], active["now"])
        threading.Event().wait(0.05)     # time.sleep is patched out by _isolate
        with lock:
            active["now"] -= 1
        return _PAGE

    monkeypatch.setattr(dfm, "_http", slow)
    doc = dfm.run(budget_s=120, fetch=True, workers=6)
    assert doc["grounds_worked"] == 24 and active["peak"] > 1        # really concurrent
    st = hf.load(tmp_path / "deep_forest_frontier.json")
    assert all(st.vectors[f"g{i}"].outcome != "NAMED_ONLY" for i in range(24))
    assert sum(v.attempts for v in st.vectors.values()) == 24       # checkpoint + end: once each
    stats = json.loads((tmp_path / dfm.VECTOR_STATS_NAME).read_text("utf-8"))["vectors"]
    assert len(stats) == 24 and sum(v["successes"] for v in stats.values()) >= 1
    claims = [json.loads(x) for x in (tmp_path / "claims.jsonl").read_text("utf-8").splitlines()]
    assert len(claims) == doc["claims_new"]
    assert len({c["claim_hash"] for c in claims}) == len(claims)
    run_line = json.loads((tmp_path / "alt_fetch_runs.jsonl").read_text("utf-8").splitlines()[-1])
    assert run_line["leg"] == "deep_forest_miner" and run_line["grounds_worked"] == 24
    art = json.loads((tmp_path / "ALT_DATA_YIELD.json").read_text("utf-8"))
    assert art["vectors"]["attempted_this_week"] == 24 and art["vectors"]["never_attempted"] == 0
    assert art["platforms"]["status"] == "UNMEASURED"                 # absent, never zero


def test_the_miner_self_stops_inside_the_cap_the_cycle_exported(monkeypatch, tmp_path) -> None:
    _isolate(monkeypatch, tmp_path)
    (tmp_path / "src.json").write_text(json.dumps({"grounds": []}), "utf-8")
    monkeypatch.setenv("QUANT_LEG_BUDGET_S", "600")
    doc = dfm.run(budget_s=900, fetch=True)
    assert doc["budget_s"] == 600 - dfm.WRITE_RESERVE_S
    assert doc["scheduler"]["requested_budget_s"] == 900 and doc["scheduler"]["cycle_cap_s"] == 600


def test_a_box_without_network_leaves_grounds_named_only(monkeypatch, tmp_path) -> None:
    _isolate(monkeypatch, tmp_path)
    grounds = [{"name": f"n{i}", "region": "cn", "route": "http", "url": f"https://n{i}.test/",
                "kind": "forum"} for i in range(6)]
    (tmp_path / "src.json").write_text(json.dumps({"grounds": grounds}), "utf-8")

    def dead(url, **kw):
        raise OSError("no route")

    monkeypatch.setattr(dfm, "_http", dead)
    doc = dfm.run(budget_s=60, fetch=True, workers=1)
    assert doc["network"] is False
    st = hf.load(tmp_path / "deep_forest_frontier.json")
    no_net = [s["ground"] for s in doc["grounds"] if s["status"] == "NO_NETWORK"]
    assert no_net and all(st.vectors[n].outcome == "NAMED_ONLY" for n in no_net)


# ----------------------------------------------------------------------------- forest legs
def test_a_forest_leg_mines_its_own_grounds_with_its_idle_seconds(monkeypatch) -> None:
    calls: list[dict] = []

    def fake_run(**kw):
        calls.append(kw)
        return {"grounds_scheduled": len(kw["only"]), "grounds_worked": 3, "productive": 1,
                "claims_new": 5, "datasets_new": 0, "tasks_queued": 2, "network": True,
                "fetch_stats": {"fetches": 9}}

    monkeypatch.setattr(dfm, "run", fake_run)
    import libs.research.forests as F
    run = fr.Run(forest="latam", allocation=F.Allocation(forest="latam", workers=4, budget_s=3000),
                 mine_grounds=True)
    res = fr.RoleResult(role="practitioner")
    fr._mine_grounds(run, res, 360.0)
    assert calls and calls[0]["write"] is True and calls[0]["leg"] == "forest_latam"
    assert calls[0]["budget_s"] >= 360.0 and calls[0]["budget_s"] <= 3000 * 0.9
    assert set(calls[0]["only"]) == {str(g["name"]) for g in fr._grounds(run)}
    assert res.detail["ground_mining"]["claims_new"] == 5


def test_every_forest_leg_is_scheduled_with_ground_mining_and_the_miner_has_a_cap() -> None:
    src = (_DESK / "research" / "hourly_cycle.py").read_text("utf-8")
    import re
    legs = re.findall(r'forests_out\["(forest_[a-z_]+)"\] = _costed\(.*?\)\)', src, re.S)
    assert len(legs) >= 15
    for block in re.findall(r'forests_out\["forest_[a-z_]+"\] = _costed\(.*?\)\)', src, re.S):
        assert '"--mine-grounds"' in block, block
    from research import hourly_cycle as hc
    assert hc.LEG_BUDGET_SEC["deep_forest_miner"] > 900
    assert '"deep_forest_miner", "research/deep_forest_miner.py", "--budget-s", "900"' in src


def test_the_cycle_exports_its_cap_to_the_child(monkeypatch) -> None:
    from research import hourly_cycle as hc
    seen: dict = {}

    class _Done:
        returncode, stdout, stderr = 0, "", ""

    def fake_tree(argv, **kw):
        seen.update(kw)
        return _Done()

    monkeypatch.setattr(hc, "_run_tree", fake_tree)
    monkeypatch.setattr(hc, "_priced_budget", lambda name, base: (base, {}))
    args = ("--budget-s", "900")
    hc._producer_impl("deep_forest_miner", "research/deep_forest_miner.py", args)
    # The cap is the leg's own cap, raised to the organ's self-stop floor (its budget plus the
    # write margin) when that is higher -- and the child is told exactly the cap it runs under.
    cap = max(hc.LEG_BUDGET_SEC["deep_forest_miner"], hc._self_stop_floor_s(args))
    assert cap == 1035
    assert seen["env"]["QUANT_LEG_BUDGET_S"] == str(cap) and seen["timeout"] == cap


def test_child_cpu_is_counted_where_os_times_cannot() -> None:
    from libs.ops import compute_ledger as cl
    from libs.ops import proctree as pt
    assert isinstance(pt.children_cpu_seconds(), float)
    assert cl._cpu_seconds() >= 0.0


@pytest.mark.parametrize("attempts, expect", [(0, 0), (4, "UNMEASURED")])
def test_a_vector_without_counts_is_unmeasured_never_zero(attempts, expect) -> None:
    from datetime import UTC, datetime
    frontier = {"vectors": {"v": {"outcome": "NAMED_ONLY" if not attempts else "EMPTY",
                                  "attempts": attempts, "findings": 0,
                                  "last_attempt": "2026-09-29T00:00:00+00:00"}}}
    out = ady.vectors(frontier, None, datetime(2026, 9, 30, tzinfo=UTC))
    assert out["rows_by_vector"]["v"]["successes"] == expect


# ----------------------------------------------------------------------------- where rows land
def test_a_regional_track_record_compiles_to_a_registered_non_banned_family() -> None:
    """The regional rows reach the gauntlet through the compiler's STRUCTURED_TRACK_RECORD door
    (miner_candidate_compiler.compile_row), NEVER through edge_search's banned `discovered`."""
    from research import family_policy as fp
    from research import miner_candidate_compiler as mcc
    row = rsh.row("share4you", "track_record", "Ivan", "https://s.test/t/1", region="CIS",
                  stats={"return_pct": 55.2}, mechanism_tags=["trend", "gold"])
    cands, disp = mcc.compile_row("share4you", row, {"XAUUSD", "EURUSD"})
    assert disp == "STRUCTURED_TRACK_RECORD" and cands
    fams = {c["family"] for c in cands}
    assert fams == {"trend_ma_cross"} and not any(fp.family_banned(f) for f in fams)
    assert all(mcc._registered_cached(f) for f in fams)


def test_deep_forest_tasks_carry_no_banned_family() -> None:
    from research import family_policy as fp
    rows = [{"claim": "黄金夜盘突破后次日延续上涨概率高。", "claim_hash": "h1", "ground": "g",
             "url": "https://x/1", "lang": "zh", "quantities": ["突破"], "score": 2.0,
             "source": "deep_forest", "instruments": {"analogues": ["XAUUSD"],
                                                      "transfer_only": []}}]
    tasks = dfm.build_tasks(rows)
    assert tasks and all(t["kind"] == "story_mechanism" for t in tasks)
    assert not any(fp.family_banned(t.get("family")) for t in tasks)


# ======================================================= forest yield rules (2026-10-13)
def _grounds(tmp_path: Path, grounds: list[dict]) -> None:
    (tmp_path / "src.json").write_text(json.dumps({"grounds": grounds}, ensure_ascii=False),
                                       "utf-8")


_DATA_PAGE = ("<html><title>Stats</title><body><p>Monthly reserves.</p>"
              "<a href='/stats/reserves.csv'>csv</a><a href='/stats/fx.json'>json</a>"
              "</body></html>")
_BARE_PAGE = "<html><title>Stats</title><body><p>Monthly reserves.</p></body></html>"


# ---- 1. the yield rule follows the ground's kind, and never inflates
def test_endpoints_yield_a_dataset_ground_and_a_zero_endpoint_page_does_not(monkeypatch,
                                                                            tmp_path) -> None:
    _isolate(monkeypatch, tmp_path)
    _grounds(tmp_path, [
        {"name": "eps", "region": "za", "language": "en", "route": "http", "kind": "dataset",
         "url": "https://eps.test/stats"},
        {"name": "bare", "region": "za", "language": "en", "route": "http", "kind": "dataset",
         "url": "https://bare.test/stats"}])
    monkeypatch.setattr(dfm, "_http",
                        lambda url, **kw: _DATA_PAGE if "eps.test" in url else _BARE_PAGE)
    doc = dfm.run(budget_s=60, fetch=True, workers=1)
    st = {g["ground"]: g for g in doc["grounds"]}
    assert st["eps"]["status"] == "PRODUCTIVE" and st["eps"]["yield_rule"] == "endpoints"
    assert st["eps"]["endpoints"] == 2 and st["eps"]["claims"] == 0
    # A dataset row with 0 endpoints is a PAGE: reached, counted, never a yield.
    assert st["bare"]["status"] == "REACHED_NO_CLAIMS" and st["bare"]["datasets"] == 1
    assert "yield_rule" not in st["bare"] and st["bare"]["endpoints"] == 0
    fr = hf.load(tmp_path / "deep_forest_frontier.json")
    assert fr.vectors["eps"].outcome == "YIELDED" and fr.vectors["bare"].outcome == "EMPTY"
    stats = json.loads((tmp_path / dfm.VECTOR_STATS_NAME).read_text("utf-8"))["vectors"]
    assert stats["eps"]["successes"] == 1 and stats["eps"]["last_yield_rule"] == "endpoints"
    assert stats["bare"]["successes"] == 0 and stats["bare"]["datasets"] == 1
    art = json.loads((tmp_path / "ALT_DATA_YIELD.json").read_text("utf-8"))
    assert art["vectors"]["yielded_by_rule"] == {"endpoints": 1}
    assert art["summary"]["yielded_by_rule"] == {"endpoints": 1}


def test_papers_yield_an_academic_ground_without_a_claim(monkeypatch, tmp_path) -> None:
    _isolate(monkeypatch, tmp_path)
    from libs.data import papers

    class _P:
        title, url, published, searchable = ("A note", "https://arxiv.org/abs/9", "2026-09-01",
                                             "An ordinary sentence with no mechanism.")
    monkeypatch.setattr(papers, "arxiv", lambda q, **kw: ([_P()], None))
    _grounds(tmp_path, [{"name": "arXiv", "region": "institutional", "language": "en",
                         "route": "papers", "fn": "arxiv", "queries": ["x"],
                         "kind": "academic"}])
    doc = dfm.run(budget_s=60, fetch=True, workers=1)
    g = doc["grounds"][0]
    assert g["claims"] == 0 and g["papers"] == 1
    assert g["status"] == "PRODUCTIVE" and g["yield_rule"] == "papers"
    assert dfm.yield_rule(0, 0, 0) == "" and dfm.yield_rule(2, 5, 1) == "claims"


# ---- 2. a blocked ground names its cause, and per-URL rows stay off the status list
@pytest.mark.parametrize("errors, status, expect", [
    ([{"url": "u", "http": 403}], "BLOCKED", ("HTTP_4xx", 403)),
    ([{"url": "u", "http": 503}], "BLOCKED", ("HTTP_5xx", 503)),
    (["HTTPError: HTTP Error 429: HTTP 429"], "BLOCKED", ("HTTP_429", 429)),
    ([{"url": "u", "error": "URLError: timed out"}], "BLOCKED", ("TRANSPORT", None)),
    (["bing: bing returned no parseable results (94518 bytes -- an anti-bot shell or a "
      "layout change, not an empty forest)", {"url": "u", "http": 404}], "BLOCKED",
     ("ANTI_BOT", None)),
    ([{"url": "u", "anti_bot": "cf-chl"}], "BLOCKED", ("ANTI_BOT", None)),
    ([{"url": "u", "held": "METHOD_BLOCKED"}], "BLOCKED", ("METHOD_BLOCKED", None)),
    ([{"url": "u", "held": "NEEDS_KEY"}], "HELD", ("NEEDS_KEY", None)),
    ([{"url": "u", "render": "playwright missing"}], "BLOCKED", ("RENDER_FAILED", None)),
    ([], "NO_ADDRESS", ("NO_ADDRESS", None)),
    ([], "NO_NETWORK", ("NO_NETWORK", None)),
    ([], "BUDGET_EXHAUSTED", ("BUDGET", None)),
    (["something nobody named"], "BLOCKED", ("UNCLASSIFIED", None)),
])
def test_every_blocker_falls_into_the_closed_cause_enum(errors, status, expect) -> None:
    got = ady.classify_cause(status, errors)
    assert got == expect
    assert got[0] in (*ady.BLOCK_CAUSES, ady.UNCLASSIFIED)
    assert ady.classify_cause("BLOCKED", [], over_budget=True) == ("BUDGET", None)


def test_a_403_ground_records_its_cause_on_the_frontier_and_the_stats(monkeypatch,
                                                                      tmp_path) -> None:
    _isolate(monkeypatch, tmp_path)
    _grounds(tmp_path, [{"name": "walled", "region": "us", "language": "en", "route": "http",
                         "kind": "forum", "url": "https://walled.test/"}])

    def forbidden(url, **kw):
        raise _http_error(url, 403)
    monkeypatch.setattr(dfm, "_http", forbidden)
    doc = dfm.run(budget_s=60, fetch=True, workers=1)
    # Every status row is a GROUND row; the per-URL error rode on the ground's own row.
    assert all("ground" in s for s in doc["grounds"]) and len(doc["grounds"]) == 1
    g = doc["grounds"][0]
    assert g["status"] == "BLOCKED" and g["cause"] == "HTTP_4xx" and g["http_code"] == 403
    assert any("HTTP 403" in e for e in g["errors"]) and g["fetch_errors"][0]["http"] == 403
    assert doc["fetch_notes"] and doc["fetch_notes"][0]["http"] == 403
    assert doc["blocked_causes"] == {"HTTP_4xx": 1}
    fr = hf.load(tmp_path / "deep_forest_frontier.json")
    assert fr.vectors["walled"].blocker.startswith("HTTP_4xx(403)")
    stats = json.loads((tmp_path / dfm.VECTOR_STATS_NAME).read_text("utf-8"))["vectors"]
    assert stats["walled"]["last_cause"] == "HTTP_4xx" and stats["walled"]["last_http_code"] == 403
    art = json.loads((tmp_path / "ALT_DATA_YIELD.json").read_text("utf-8"))
    assert art["vectors"]["blocked_by_cause"] == {"HTTP_4xx": 1}
    assert art["vectors"]["blocked_http_codes"] == {"403": 1}


# ---- 3. no source is banned: per-source policy, HELD only for METHOD_BLOCKED / NEEDS_KEY
@pytest.mark.parametrize("url, status", [
    ("https://www.reddit.com/r/algotrading/.rss", "IDEAS_ONLY"),
    ("https://oauth.reddit.com/r/x/new", "NEEDS_KEY"),
    ("https://t.me/s/markettwits", "IDEAS_ONLY"),
    ("https://x.com/someone/status/1", "IDEAS_ONLY"),
    ("https://api.x.com/2/tweets/search/recent", "NEEDS_KEY"),
    ("https://nitter.poast.org/search?q=x", "METHOD_BLOCKED"),
    ("https://xcancel.com/search?q=x", "METHOD_BLOCKED"),
    ("https://www.mql5.com/en/articles", "IDEAS_ONLY"),
    ("https://finance.yahoo.co.jp/cm/x", "IDEAS_ONLY"),
    ("https://stocktwits.com/symbol/XAUUSD", "IDEAS_ONLY"),
    ("https://discord.com/channels/1", "METHOD_BLOCKED"),
    ("https://www.taifex.com.tw/x", "PUBLIC_PAGE"),
])
def test_every_source_has_a_per_source_status_and_none_is_banned(monkeypatch, url,
                                                                status) -> None:
    for k in ("X_BEARER_TOKEN", "REDDIT_CLIENT_ID", "REDDIT_CLIENT_SECRET"):
        monkeypatch.delenv(k, raising=False)
    p = dfm.policy_of_url(url)
    assert p["status"] == status and p["why"]
    assert all(r["why"] and r["status"] in ("API_PERMITTED", "PUBLIC_PAGE", "IDEAS_ONLY",
                                            "METHOD_BLOCKED")
               for r in dfm.SOURCE_POLICY.values())


def test_a_present_key_turns_needs_key_into_api_permitted(monkeypatch) -> None:
    monkeypatch.setenv("REDDIT_CLIENT_ID", "x")
    monkeypatch.setenv("REDDIT_CLIENT_SECRET", "y")
    assert dfm.policy_of_url("https://oauth.reddit.com/r/x")["status"] == "API_PERMITTED"


def test_only_method_blocked_or_needs_key_grounds_are_held_and_the_rest_are_fetched(
        monkeypatch, tmp_path) -> None:
    _isolate(monkeypatch, tmp_path)
    monkeypatch.delenv("X_BEARER_TOKEN", raising=False)
    grounds = [
        {"name": "X (nitter) FX", "region": "us", "language": "en", "route": "nitter",
         "kind": "social", "queries": ["x"], "mirrors": ["nitter.net"]},
        {"name": "xcancel search", "region": "us", "language": "en", "route": "search",
         "kind": "social", "site": "xcancel.com", "queries": ["x"]},
        {"name": "r/algotrading", "region": "us", "language": "en", "route": "reddit",
         "kind": "community", "subs": ["algotrading"]},
        {"name": "Telegram RU", "region": "ru", "language": "ru", "route": "telegram",
         "kind": "social", "channels": ["c"]},
        {"name": "MQL5 articles", "region": "global", "language": "en", "route": "http",
         "kind": "forum", "url": "https://www.mql5.com/en/articles"}]
    _grounds(tmp_path, grounds)
    fetched: list[str] = []

    def spy(url, **kw):
        fetched.append(url)
        return _PAGE + "<a href='/data/x.csv'>csv</a>"
    monkeypatch.setattr(dfm, "_http", spy)
    doc = dfm.run(budget_s=60, fetch=True, workers=1)
    # RE-ADMITTED: reddit feeds, Telegram previews and mql5 pages are fetched for ideas.
    assert any("reddit.com/r/algotrading" in u for u in fetched)
    assert any("t.me/s/c" in u for u in fetched)
    assert any("mql5.com" in u for u in fetched)
    assert not any("nitter" in u or "xcancel" in u for u in fetched)
    assert doc["held"] == {"X (nitter) FX": "METHOD_BLOCKED", "xcancel search": "METHOD_BLOCKED"}
    fr = hf.load(tmp_path / "deep_forest_frontier.json")
    for n in ("X (nitter) FX", "xcancel search"):
        v = fr.vectors[n]
        assert v.outcome == "HELD" and v.attempts == 0 and v.blocker.startswith("METHOD_BLOCKED")
        assert v.huntable(datetime.now(tz=UTC))[0] is False
    for n in ("r/algotrading", "Telegram RU", "MQL5 articles"):
        assert fr.vectors[n].outcome in ("YIELDED", "EMPTY")
    # IDEAS_ONLY: the claims carry the label; no endpoint is registered as live input data.
    claims = [json.loads(x) for x in (tmp_path / "claims.jsonl").read_text("utf-8").splitlines()]
    assert claims and all("source_policy" in c for c in claims)
    ds = tmp_path / "datasets.jsonl"
    rows = [json.loads(x) for x in ds.read_text("utf-8").splitlines()] if ds.exists() else []
    assert not [d for d in rows if "mql5.com" in d["url"] and d["n_endpoints"]]
    summ = hf.summarise(fr)
    assert summ["held"] == 2
    art = json.loads((tmp_path / "ALT_DATA_YIELD.json").read_text("utf-8"))
    assert art["vectors"]["by_outcome"]["HELD"] == 2
    assert art["vectors"]["held_by"] == {"METHOD_BLOCKED": 2}
    r = dfm._Run(10, True, None)
    assert r.ground_nitter(grounds[0])["held_by"] == "METHOD_BLOCKED"
    assert r.ground_nitter(grounds[0])["permitted_route"] == "x_api"
    assert r.page("https://nitter.net/search?q=x") == ""
    assert r.fetch_errors[-1]["held"] == "METHOD_BLOCKED"


def test_a_ground_an_older_policy_held_is_re_admitted(monkeypatch, tmp_path) -> None:
    _isolate(monkeypatch, tmp_path)
    st = hf.VectorState()
    hf.record(st, "r/algotrading", outcome="HELD", blocker="TERMS_HELD: reddit")
    hf.save(st, tmp_path / "deep_forest_frontier.json")
    dfm._record_frontier([], [{"name": "r/algotrading", "route": "reddit", "subs": ["a"]}])
    assert hf.load(tmp_path / "deep_forest_frontier.json").vectors[
        "r/algotrading"].outcome == "NAMED_ONLY"


def test_a_held_vector_never_changes_a_rollup_row_that_has_none() -> None:
    st = hf.VectorState()
    hf.record(st, "a", outcome="EMPTY", language="zh")
    assert hf.rollup(st, "language")["zh"] == {"NAMED_ONLY": 0, "BLOCKED": 0, "EMPTY": 1,
                                               "YIELDED": 0, "findings": 0, "vectors": 1}
    hf.record(st, "b", outcome="HELD", language="zh")
    assert hf.rollup(st, "language")["zh"]["HELD"] == 1


# ---- 4. the search route: anti-bot is the cause, the Common Crawl index is the fallback
_ANTIBOT = "<html><body>" + "x" * 90_000 + "</body></html>"


def _cc_fake(calls: list, *, robots: str = "User-agent: *\nAllow: /\n"):
    def fake(url: str) -> pf.Response:
        calls.append(url)
        if url.endswith("/robots.txt"):
            return pf.Response(url=url, status=200, text=robots)
        if url.endswith("collinfo.json"):
            return pf.Response(url=url, status=200, text=json.dumps([
                {"id": "CC-MAIN-2026-39",
                 "cdx-api": "https://index.commoncrawl.org/CC-MAIN-2026-39-index"}]))
        lines = [json.dumps({"url": f"https://forum.test/t/{i}", "mime": "text/html",
                             "status": "200"}) for i in range(3)]
        lines.append(json.dumps({"url": "https://forum.test/a.png", "mime": "image/png",
                                 "status": "200"}))
        return pf.Response(url=url, status=200, text="\n".join(lines))
    return fake


def test_an_anti_bot_engine_falls_back_to_the_common_crawl_index(monkeypatch, tmp_path) -> None:
    _isolate(monkeypatch, tmp_path)
    _grounds(tmp_path, [{"name": "Forum", "region": "us", "language": "en", "route": "search",
                         "kind": "forum", "site": "forum.test", "queries": ["a", "b"]}])
    calls: list[str] = []
    monkeypatch.setattr(dfm, "_cc_get", _cc_fake(calls))
    pages: list[str] = []

    def http(url, **kw):
        if "bing.com" in url:
            return _ANTIBOT
        if "duckduckgo" in url:
            return ""
        pages.append(url)
        return _PAGE
    monkeypatch.setattr(dfm, "_http", http)
    doc = dfm.run(budget_s=60, fetch=True, workers=1)
    g = doc["grounds"][0]
    cdx = [u for u in calls if "-index?" in u]
    assert len(cdx) == 1                                 # ONE query per ground per pass
    assert "url=forum.test/*" in cdx[0] and "limit=15" in cdx[0]
    assert g["route_used"] == "search:ccindex" and g["ccindex"] == 3
    assert pages and all(u.startswith("https://forum.test/t/") for u in pages)
    assert g["status"] == "PRODUCTIVE" and g["yield_rule"] == "claims"
    claims = [json.loads(x) for x in (tmp_path / "claims.jsonl").read_text("utf-8").splitlines()]
    assert claims and {c["route"] for c in claims} == {"search:ccindex"}
    assert "Mozilla" not in dfm.CCINDEX_UA["User-Agent"]          # an honest agent
    assert "commoncrawl.org/terms-of-use" in dfm.TERMS_EVIDENCE["commoncrawl_index"]["terms_url"]


def test_a_robots_disallow_stands_the_index_down_and_the_cause_stays_anti_bot(monkeypatch,
                                                                             tmp_path) -> None:
    _isolate(monkeypatch, tmp_path)
    _grounds(tmp_path, [{"name": "Forum", "region": "us", "language": "en", "route": "search",
                         "kind": "forum", "site": "forum.test", "queries": ["a"]}])
    calls: list[str] = []
    monkeypatch.setattr(dfm, "_cc_get",
                        _cc_fake(calls, robots="User-agent: *\nDisallow: /*-index\n"))
    monkeypatch.setattr(dfm, "_http",
                        lambda url, **kw: _ANTIBOT if "bing.com" in url else "")
    doc = dfm.run(budget_s=60, fetch=True, workers=1)
    g = doc["grounds"][0]
    assert not [u for u in calls if "-index?" in u]               # never queried
    assert g["status"] == "BLOCKED" and g["cause"] == "ANTI_BOT"
    assert any("robots" in e for e in g["errors"])
    assert dfm.parse_cdx('{"url": "https://a.test/x", "status": "404"}\nnot json') == []


# ---- 5. the artifact: HELD apart, causes, rules and the conversion ladder
def test_the_yield_artifact_reports_outcomes_causes_rules_and_the_conversion_ladder(
        tmp_path) -> None:
    now = "2026-10-13T00:00:00+00:00"
    frontier = {"vectors": {
        "nitter FX": {"outcome": "BLOCKED", "attempts": 3, "blocker": "BLOCKED",
                      "last_attempt": now},
        "legacy": {"outcome": "BLOCKED", "attempts": 2, "blocker": "BLOCKED",
                   "last_attempt": now},
        "bingwall": {"outcome": "BLOCKED", "attempts": 1, "blocker": "BLOCKED",
                     "last_attempt": now},
        "walled": {"outcome": "BLOCKED", "attempts": 1, "blocker": "HTTP_4xx(403): x",
                   "last_attempt": now},
        "stats": {"outcome": "YIELDED", "attempts": 1, "findings": 0, "last_attempt": now},
        "story": {"outcome": "YIELDED", "attempts": 4, "findings": 7, "last_attempt": now},
        "never": {"outcome": "NAMED_ONLY", "attempts": 0}}}
    stats = {"vectors": {
        "bingwall": {"successes": 0, "rows": 0, "last_error": "bing: bing returned no "
                     "parseable results (94518 bytes -- an anti-bot shell)"},
        "stats": {"successes": 1, "rows": 0, "datasets": 1, "last_yield_rule": "endpoints"}}}
    grounds = {"grounds": [
        {"name": "nitter FX", "route": "nitter", "mirrors": ["nitter.net"]},
        {"name": "stats", "route": "http", "url": "https://stats.test/data", "kind": "dataset"},
        {"name": "story", "route": "http", "url": "https://story.test/"}]}
    datasets = [{"ground": "stats", "endpoints": ["https://stats.test/a.csv"], "n_endpoints": 1},
                {"ground": "story", "endpoints": [], "n_endpoints": 0}]
    for name, obj in (("f.json", frontier), ("s.json", stats), ("g.json", grounds),
                      ("reg.json", {"by_url": {"https://stats.test/a.csv": {}}}),
                      ("cand.json", {"hypotheses": [{"source_title": "story"}]})):
        (tmp_path / name).write_text(json.dumps(obj), "utf-8")
    (tmp_path / "d.jsonl").write_text("\n".join(json.dumps(r) for r in datasets), "utf-8")
    common = {"frontier": tmp_path / "f.json", "vector_stats": tmp_path / "s.json",
              "runs": tmp_path / "none", "compute_ledger": tmp_path / "none",
              "coverage": tmp_path / "none", "sources": tmp_path / "g.json",
              "datasets": tmp_path / "d.jsonl", "acquired": tmp_path / "reg.json"}
    doc = ady.write(out=tmp_path / "out.json", candidates=tmp_path / "cand.json", **common)
    v = doc["vectors"]
    assert v["by_outcome"] == {"HELD": 1, "BLOCKED": 3, "YIELDED": 2, "NAMED_ONLY": 1}
    assert v["rows_by_vector"]["nitter FX"]["outcome_recorded"] == "BLOCKED"
    # A bare "BLOCKED" from before causes were kept is UNMEASURED, never a guessed cause.
    assert v["blocked_by_cause"] == {"UNMEASURED": 1, "ANTI_BOT": 1, "HTTP_4xx": 1}
    assert v["yielded_by_rule"] == {"endpoints": 1, "claims": 1}
    lad = {n: r["conversion"]["deepest"] for n, r in v["rows_by_vector"].items()}
    assert lad["stats"] == "collected" and lad["story"] == "cell_generating"
    assert lad["never"] == "named" and lad["walled"] == "attempted"
    assert doc["summary"]["conversion"]["collected"] == 2           # stats + story beneath
    # An absent source artifact is UNMEASURED with its reason -- never 0.
    doc2 = ady.write(out=tmp_path / "out2.json", candidates=tmp_path / "absent.json", **common)
    assert doc2["summary"]["conversion"]["cell_generating"] == "UNMEASURED"
    assert "absent" in doc2["vectors"]["conversion"]["unmeasured"]["cell_generating"]
    assert doc2["vectors"]["rows_by_vector"]["story"]["conversion"]["cell_generating"] \
        == "UNMEASURED"


@pytest.mark.parametrize("robots, path, allowed", [
    ("User-agent: *\nDisallow: /*-index\n", "/CC-MAIN-1-index?url=a/*", False),
    ("User-agent: *\nDisallow: /*-index\nAllow: /CC-MAIN-1-index?url\n",
     "/CC-MAIN-1-index?url=a/*", True),
    ("User-agent: *\nDisallow: /\n", "/x", False),
    ("User-agent: *\nDisallow:\n", "/x", True),
    ("User-agent: quant-desk-deep-forest\nDisallow: /\nUser-agent: *\nAllow: /\n", "/x", False),
    ("User-agent: *\nDisallow: /*.json$\n", "/collinfo.json", False),
    ("", "/x", True),
])
def test_robots_wildcards_are_read(robots, path, allowed) -> None:
    assert dfm.robots_allows(robots, dfm.CCINDEX_AGENT, path) is allowed


# ---- 6. ugly data is landed raw (principal 2026-10-13 16:39Z), never counted as a yield
_CSV = b"date,value\n2026-09-01,1.5\n2026-09-02,1.7\n"


def test_a_page_dropped_for_its_form_lands_raw_and_is_not_a_yield(monkeypatch,
                                                                  tmp_path) -> None:
    _isolate(monkeypatch, tmp_path)
    _grounds(tmp_path, [
        {"name": "csv", "region": "za", "language": "en", "route": "http", "kind": "forum",
         "url": "https://csv.test/data.csv"},
        {"name": "short", "region": "za", "language": "en", "route": "http", "kind": "forum",
         "url": "https://short.test/"},
        {"name": "bare", "region": "za", "language": "en", "route": "http", "kind": "dataset",
         "url": "https://bare.test/stats"},
        {"name": "ideas", "region": "us", "language": "en", "route": "http", "kind": "forum",
         "url": "https://www.reddit.com/r/Gold/"},
        {"name": "bot", "region": "us", "language": "en", "route": "http", "kind": "forum",
         "url": "https://bot.test/"}])

    def fake(url: str, **kw: object) -> str:
        if "csv.test" in url:
            dfm._LAST.resp = pf.Response(url=url, status=200, text=_CSV.decode(),
                                         content_type="text/csv", body=_CSV)
            return _CSV.decode()
        if "bot.test" in url:
            return "<html><title>Just a moment...</title>Checking your browser</html>"
        if "bare.test" in url:                 # long enough to read, and no endpoint in it
            return "<html><body><p>" + "Monthly reserves, table below. " * 80 + "</p></html>"
        return _BARE_PAGE

    monkeypatch.setattr(dfm, "_http", fake)
    doc = dfm.run(budget_s=60, fetch=True, workers=1)
    st = {g["ground"]: g for g in doc["grounds"]}
    assert st["csv"]["landed_raw"] >= 1 and st["short"]["landed_raw"] >= 1
    assert st["bare"]["landed_raw"] >= 1
    assert st["ideas"]["landed_raw"] == 0, "an IDEAS_ONLY page is never landed as data"
    assert st["bot"]["landed_raw"] == 0, "an anti-bot page is recorded, never landed"
    for name in ("csv", "short", "bare"):
        assert "yield_rule" not in st[name] and st[name]["status"] != "PRODUCTIVE", name
    metas = [json.loads(p.read_text("utf-8")) for p in (tmp_path / "vault").glob("*/*.meta.json")]
    csv_meta = next(m for m in metas if m["url"] == "https://csv.test/data.csv")
    assert csv_meta["reason"] == "format:text/csv" and csv_meta["content_type"] == "text/csv"
    assert csv_meta["available_time"] and csv_meta["source_hash"] == csv_meta["sha256"]
    blob = next((tmp_path / "vault").glob(f"{csv_meta['source_id']}/*.gz"))
    assert gzip.decompress(blob.read_bytes()) == _CSV
    assert {m["reason"] for m in metas} >= {"format:text/csv", "short_page",
                                            "dataset_no_endpoints"}
    # The desk's existing raw -> series parser reads the landing like any collected source.
    from research import asia_parser as ap
    monkeypatch.setattr(ap, "VAULT", tmp_path / "vault")
    assert csv_meta["source_id"] in ap._blobs()
    # The ladder counts it beside the rungs, never as one.
    stats = json.loads((tmp_path / dfm.VECTOR_STATS_NAME).read_text("utf-8"))["vectors"]
    assert stats["csv"]["landed_raw"] >= 1 and stats["csv"]["successes"] == 0
    art = json.loads((tmp_path / "ALT_DATA_YIELD.json").read_text("utf-8"))
    assert art["vectors"]["rows_by_vector"]["csv"]["conversion"]["landed_raw"] >= 1
    assert art["vectors"]["rows_by_vector"]["csv"]["conversion"]["deepest"] != "yielded"
    assert art["summary"]["landed_raw"]["pages"] >= 3
    assert art["summary"]["landed_raw"]["vectors"] == 3


def test_the_same_bytes_land_once(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(dfm, "RAW_VAULT", tmp_path / "vault")
    g = {"name": "x"}
    first = dfm.land_raw("https://a.test/x.csv", _CSV, "text/csv", ground=g, reason="r")
    again = dfm.land_raw("https://a.test/x.csv", _CSV, "text/csv", ground=g, reason="r")
    assert first and first["new"] and again and not again["new"]
    assert len(list((tmp_path / "vault").glob("*/*.gz"))) == 1
    assert dfm.land_raw("https://a.test/y", b"", "", ground=g, reason="r") is None


def test_landed_raw_is_unmeasured_without_vector_stats() -> None:
    frontier = {"vectors": {"g": {"outcome": "EMPTY", "attempts": 2}}}
    v = ady.vectors(frontier, None, datetime(2026, 10, 13, tzinfo=UTC))
    assert v["rows_by_vector"]["g"]["conversion"]["landed_raw"] == ady.UNMEASURED
    assert v["conversion"]["landed_raw"]["status"] == ady.UNMEASURED


def test_a_compressed_body_is_inflated_only_up_to_the_cap() -> None:
    bomb = gzip.compress(b"0" * 5_000_000)
    assert len(pf.inflate(bomb, "gzip", cap=1000)) == 1000
    assert pf.inflate(b"plain", "") == b"plain"
    assert pf.decode_body(gzip.compress("héllo".encode()), "text/plain; charset=utf-8",
                          "gzip") == "héllo"
