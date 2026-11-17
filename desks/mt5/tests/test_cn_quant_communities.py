"""The five CN retail-quant communities: attempted through the gate, or refused by name.

JoinQuant, RiceQuant, Uqer, myquant and BigQuant read NAMED_ONLY with zero attempts on the
committed frontier. Pinned here, with no network: every one of them is a registered ground the
scheduler reaches; BigQuant (whose terms forbid bots) is refused on EVERY route with a named
reason and a missed-growth line, and builds no request; a render-route community whose page
never rendered is a named wall (JS_SHELL_UNRENDERED), never a silent "reached, no claims"; and
FOREST_ATTEMPTS.json raises an idle alarm for any ground or miner ledger untouched for 7 days.
"""
from __future__ import annotations

import json
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest

_DESK = Path(__file__).resolve().parents[1]
for _p in (str(_DESK), str(_DESK / "research"), str(_DESK.parent.parent)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from libs.data import polite_fetch as pf  # noqa: E402
from research import deep_forest_miner as dfm  # noqa: E402
from research import forest_attempts as fa  # noqa: E402

NOW = datetime(2026, 11, 17, 12, 0, tzinfo=UTC)
COMMUNITIES = ("聚宽 JoinQuant 社区", "米筐 RiceQuant 社区", "优矿 Uqer 社区",
               "掘金量化 myquant 论坛", "BigQuant 社区")


def _iso(d: datetime) -> str:
    return d.isoformat(timespec="seconds")


def _registered() -> dict[str, dict[str, Any]]:
    doc = json.loads((_DESK / "data" / "deep_forest_sources.json").read_text("utf-8"))
    return {str(g.get("name")): g for g in doc["grounds"] if isinstance(g, dict)}


@pytest.fixture(autouse=True)
def _fresh_cache():
    dfm._ROBOTS.clear()
    yield
    dfm._ROBOTS.clear()


def test_all_five_communities_are_registered_and_scheduled() -> None:
    reg = _registered()
    for name in COMMUNITIES:
        assert name in reg, name
        assert reg[name]["route"] in dfm.ROUTES
    order = dfm.schedule(list(reg.values()), only={"cn"})
    names = [str(g.get("name")) for g in order]
    for name in COMMUNITIES:
        assert name in names                       # never dropped by the scheduler


def test_bigquant_is_refused_by_name_and_the_other_four_are_not() -> None:
    reg = _registered()
    why = dfm.ground_refusal(reg["BigQuant 社区"])
    assert why and why.startswith("TERMS_REFUSED: bigquant.com")
    for name in COMMUNITIES[:4]:
        assert dfm.ground_refusal(reg[name]) is None, name
    # a `site:` ground on a refused host is refused too, so no engine route reads it
    assert dfm.ground_refusal({"site": "www.bigquant.com"})


def _run(monkeypatch, tmp_path: Path) -> dfm._Run:
    monkeypatch.setattr(dfm, "SEEN", tmp_path / "seen.json")
    monkeypatch.setattr(dfm, "_universe", lambda: set())
    run = dfm._Run(60.0, True, None, None)
    run._net_ok = lambda: True                                    # type: ignore[method-assign]
    return run


def test_a_refused_ground_builds_no_request_on_any_route(monkeypatch, tmp_path) -> None:
    calls: list[str] = []
    monkeypatch.setattr(dfm.pf, "get", lambda url, **_k: calls.append(url) or pf.Response(
        url=url, status=200, text="x"))
    monkeypatch.setattr(dfm, "engine_search", lambda *a, **k: calls.append("engine") or (
        [], "", []))
    run = _run(monkeypatch, tmp_path)
    for route in ("render", "search", "http"):
        run.work({**_registered()["BigQuant 社区"], "route": route,
                  "site": "bigquant.com", "queries": ["因子"]})
    assert calls == []
    rows = [s for s in run.status if "ground" in s]
    assert [s["status"] for s in rows] == ["REFUSED"] * 3
    assert all(s["why"].startswith("TERMS_REFUSED") for s in rows)
    assert all(s["missed_growth"].startswith("missed_growth:") for s in rows)


def test_a_refusal_is_not_recorded_as_an_attempt(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(dfm, "SEEN", tmp_path / "seen.json")
    recorded: list[Any] = []
    monkeypatch.setattr(dfm, "_record_frontier", lambda sts, _g: recorded.append(sts))
    monkeypatch.setattr(dfm, "_record_vector_stats", lambda sts: recorded.append(sts))
    run = _run(monkeypatch, tmp_path)
    f = run.fork()
    f.status.append({"ground": "BigQuant 社区", "status": "REFUSED", "why": "TERMS_REFUSED: x"})
    dfm._checkpoint(run, f, {"last_seen_save": 0.0})
    assert recorded == []


def test_an_unrendered_js_shell_is_a_named_wall_not_a_reached_ground(monkeypatch,
                                                                      tmp_path) -> None:
    from libs.data import render_fetch as rf

    def fake_get(url, **_k):
        if url.endswith("/robots.txt"):
            return pf.Response(url=url, status=404)
        return pf.Response(url=url, status=200,
                           text="<html><script>app()</script><div id=app>加载中</div></html>")
    monkeypatch.setattr(dfm.pf, "get", fake_get)
    monkeypatch.setattr(rf, "render", lambda url, **kw: ("", "renderer absent on this host"))
    run = _run(monkeypatch, tmp_path)
    g = _registered()["聚宽 JoinQuant 社区"]
    run.work(g)
    row = [s for s in run.status if s.get("ground") == g["name"]][-1]
    assert row["status"] == "BLOCKED"                 # attempted, through the gate, failed closed
    assert row["why"].startswith("JS_SHELL_UNRENDERED")
    assert row["missed_growth"].startswith("this ground's claims stay unread")


def test_a_robots_disallow_stops_a_community_before_its_page(monkeypatch, tmp_path) -> None:
    calls: list[str] = []

    def fake_get(url, **_k):
        calls.append(url)
        if url.endswith("/robots.txt"):
            return pf.Response(url=url, status=200, text="User-agent: *\nDisallow: /\n")
        return pf.Response(url=url, status=200, text="<p>never</p>")
    monkeypatch.setattr(dfm.pf, "get", fake_get)
    run = _run(monkeypatch, tmp_path)
    g = _registered()["掘金量化 myquant 论坛"]
    run.work(g)
    assert all(u.endswith("/robots.txt") for u in calls)
    row = [s for s in run.status if s.get("ground") == g["name"]][-1]
    assert row["status"] == "BLOCKED" and row["why"].startswith("ROBOTS_REFUSED")


# ------------------------------------------------------------------------------ idle alarm
def _files(tmp: Path, grounds: list[dict[str, Any]], vectors: dict[str, Any],
           stats: dict[str, Any], *, fr_updated: str, st_updated: str) -> dict[str, Path]:
    src, fr, st = tmp / "sources.json", tmp / "frontier.json", tmp / "stats.json"
    src.write_text(json.dumps({"grounds": grounds}), "utf-8")
    fr.write_text(json.dumps({"updated": fr_updated, "vectors": vectors}), "utf-8")
    st.write_text(json.dumps({"updated": st_updated, "vectors": stats}), "utf-8")
    return {"sources": src, "frontier": fr, "stats": st}


def _g(name: str, url: str) -> dict[str, Any]:
    return {"name": name, "region": "cn", "language": "zh", "route": "http", "url": url}


def test_idle_grounds_and_stale_ledgers_raise_the_alarm_and_turn_the_fence_red(tmp_path):
    grounds = [_g("fresh", "https://a.example/"), _g("stale", "https://b.example/"),
               _g("never", "https://c.example/"), _g("BigQuant 社区", "https://bigquant.com/w")]
    vectors = {
        "fresh": {"outcome": "EMPTY", "attempts": 3,
                  "last_attempt": _iso(NOW - timedelta(hours=3))},
        "stale": {"outcome": "EMPTY", "attempts": 3,
                  "last_attempt": _iso(NOW - timedelta(days=9))},
        "never": {"outcome": "NAMED_ONLY", "attempts": 0,
                  "first_seen": _iso(NOW - timedelta(days=60))},
        "BigQuant 社区": {"outcome": "NAMED_ONLY", "attempts": 0,
                        "first_seen": _iso(NOW - timedelta(days=60))},
    }
    paths = _files(tmp_path, grounds, vectors, {},
                   fr_updated=_iso(NOW - timedelta(days=66)), st_updated=_iso(NOW))
    doc = fa.build(now=NOW, **paths)
    alarm = doc["idle_alarm"]
    assert alarm["status"] == "ALARM"
    assert {x["ground"] for x in alarm["grounds"]} == {"stale", "never"}
    assert [x["ledger"] for x in alarm["stale_ledgers"]] == ["frontier"]
    assert alarm["missed_growth"].startswith("missed_growth:")
    # the refused ground is named, exempt from idle, never-attempted and overdue
    row = doc["grounds"]["BigQuant 社区"]
    assert row["state"] == fa.REFUSED and row["refusal"].startswith("TERMS_REFUSED")
    assert "BigQuant 社区" in alarm["exempt"] and not row["overdue_24h"]
    assert doc["summary"]["never_attempted"] == 1 and doc["summary"]["refused"] == 1
    assert doc["summary"]["idle_7d"] == 2
    v = fa.judge(doc, [], NOW, stats_updated=_iso(NOW))
    assert v["status"] == "RED" and any("SOURCES IDLE" in r for r in v["reasons"])


def test_the_alarm_clears_only_on_evidence(tmp_path):
    grounds = [_g("a", "https://a.example/")]
    fresh = {"a": {"outcome": "EMPTY", "attempts": 1,
                   "last_attempt": _iso(NOW - timedelta(days=2))}}
    doc = fa.build(now=NOW, **_files(tmp_path, grounds, fresh, {},
                                     fr_updated=_iso(NOW), st_updated=_iso(NOW)))
    assert doc["idle_alarm"]["status"] == "CLEAR"
    # a never-attempted ground with no naming stamp has an UNMEASURED age -- never CLEAR
    unstamped = {"a": {"outcome": "NAMED_ONLY", "attempts": 0}}
    doc = fa.build(now=NOW, **_files(tmp_path, grounds, unstamped, {},
                                     fr_updated=_iso(NOW), st_updated=_iso(NOW)))
    assert doc["idle_alarm"]["status"] == fa.UNMEASURED
    assert fa.judge(doc, [], NOW, stats_updated=_iso(NOW))["status"] != "GREEN"


def test_the_alarm_is_on_the_published_artifact_and_the_history_line(tmp_path):
    grounds = [_g("stale", "https://b.example/")]
    vectors = {"stale": {"outcome": "EMPTY", "attempts": 1,
                         "last_attempt": _iso(NOW - timedelta(days=8))}}
    paths = _files(tmp_path, grounds, vectors, {}, fr_updated=_iso(NOW), st_updated=_iso(NOW))
    out, hp = tmp_path / "FOREST_ATTEMPTS.json", tmp_path / "hist.jsonl"
    fa.publish(out=out, history_path=hp, now=NOW, **paths)
    art = json.loads(out.read_text("utf-8"))
    assert art["idle_alarm"]["status"] == "ALARM" and art["fence"]["status"] == "RED"
    line = json.loads(hp.read_text("utf-8").splitlines()[-1])
    assert line["summary"]["idle_7d"] == 1 and line["summary"]["idle_alarm"] == "ALARM"


def test_the_alarm_rides_an_hourly_leg() -> None:
    src = (_DESK / "research" / "hourly_cycle.py").read_text("utf-8")
    assert '_costed("forest_attempts"' in src
    assert "scripts/check_forest_attempts.py" in src
