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

    def opener(req, timeout, context):
        calls.append(req.full_url)
        if len(calls) == 1:
            raise _http_error(req.full_url, 503)
        return _Resp(b"<html>ok</html>", headers={"Content-Type": "text/html; charset=utf-8"})

    pf.reset_stats("t1")
    r = pf.get("https://a.test/x", leg="t1", opener=opener, gate=None, sleep=lambda s: None)
    assert r.ok and r.text == "<html>ok</html>" and r.attempts == 2 and len(calls) == 2
    s = pf.stats("t1")
    assert s["fetches"] == 2 and s["ok"] == 1 and s["http_errors"] == 1 and s["retries"] == 1


def test_a_404_is_deterministic_and_is_not_hammered() -> None:
    calls: list[int] = []

    def opener(req, timeout, context):
        calls.append(1)
        raise _http_error(req.full_url, 404)

    r = pf.get("https://a.test/moved", opener=opener, gate=None, sleep=lambda s: None, retries=3)
    assert not r.ok and r.status == 404 and len(calls) == 1


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
    monkeypatch.setattr(dfm, "_feed_frontier", lambda urls: len(urls))
    monkeypatch.setattr(dfm, "_universe", lambda: {"XAUUSD", "EURUSD"})
    monkeypatch.setattr(dfm.time, "sleep", lambda s: None)
    monkeypatch.setattr(dfm._Run, "rendered", lambda self, url: "")
    import research.regime_coverage as rc
    monkeypatch.setattr(rc, "_merge_into_queue", lambda tasks, source="x": None)
    monkeypatch.setattr(ady, "COMPUTE_LEDGER", tmp_path / "none.jsonl")
    monkeypatch.setattr(ady, "COVERAGE", tmp_path / "none.json")


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
    hc._producer_impl("deep_forest_miner", "research/deep_forest_miner.py", ("--budget-s", "900"))
    assert seen["env"]["QUANT_LEG_BUDGET_S"] == "1020" and seen["timeout"] == 1020


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
