"""The Reddit terms fence (project coordinator ruling 2026-09-30) and its lawful substitutes.

Reddit's User Agreement and Data API terms cover every automated reader -- RSS and the anonymous
JSON included -- and require an agreement for commercial use. These tests pin that NO Reddit route
in the tree opens a connection, that the compiler refuses Reddit rows with a counted reason, that
existing cells are labelled rather than deleted, and that the attention substitutes mint charged
cells from Wikipedia pageviews and GDELT. No network anywhere: every connection is intercepted.
"""
from __future__ import annotations

import json
import socket
import sys
import urllib.request
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest

ROOT = Path(__file__).resolve().parents[2]
DESK = ROOT / "desks" / "mt5"
for _p in (str(ROOT), str(DESK), str(DESK / "research"), str(DESK / "side_channels")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from libs.data import polite_fetch as pf  # noqa: E402
from libs.data import terms_fence as tf  # noqa: E402

NOW = datetime(2026, 9, 30, 14, tzinfo=UTC)


class _Tripwire:
    """Records every attempt to open a connection or a URL, and refuses it."""

    def __init__(self) -> None:
        self.hosts: list[str] = []

    def urlopen(self, req: Any, *a: Any, **k: Any) -> Any:
        url = req.full_url if hasattr(req, "full_url") else str(req)
        self.hosts.append(url)
        raise OSError("network disabled in tests")

    def connect(self, addr: Any, *a: Any, **k: Any) -> Any:
        self.hosts.append(str(addr[0]))
        raise OSError("network disabled in tests")

    def reddit(self) -> list[str]:
        return [h for h in self.hosts if "reddit" in h.lower() or "redd.it" in h.lower()]


@pytest.fixture
def wire(monkeypatch: pytest.MonkeyPatch) -> _Tripwire:
    w = _Tripwire()
    monkeypatch.setattr(urllib.request, "urlopen", w.urlopen)
    monkeypatch.setattr(socket, "create_connection", w.connect)
    try:
        import requests  # noqa: F401
        monkeypatch.setattr("requests.sessions.Session.request",
                            lambda self, method, url, *a, **k: w.urlopen(url))
    except ImportError:
        pass
    return w


# ---------------------------------------------------------------------------- the fence ----
def test_hosts_match_the_platform_and_every_subdomain_and_nothing_else() -> None:
    for u in ("https://www.reddit.com/r/Forex/.rss", "https://old.reddit.com/r/x/.json",
              "reddit.com/r/Kenya", "https://redd.it/abc", "https://i.redditmedia.com/x.png"):
        assert tf.platform_of_url(u) == "reddit", u
    assert tf.platform_of_url("https://api.stocktwits.com/api/2/streams/symbol/SPY.json") \
        == "stocktwits"
    for u in ("https://notreddit.com/", "https://example.com/?u=reddit.com", "",
              "https://wikimedia.org/api/rest_v1/", "https://api.gdeltproject.org/api/v2/"):
        assert tf.platform_of_url(u) is None, u
    assert "agreement" in (tf.fenced_url("https://www.reddit.com/") or "")
    with pytest.raises(tf.TermsFenced):
        tf.check_url("https://www.reddit.com/r/algotrading/hot.json")


def test_every_fenced_platform_names_its_reason_status_and_substitutes() -> None:
    rows = {r["platform"]: r for r in tf.registry_rows()}
    assert rows["reddit"]["status"] == tf.BLOCKED_WITH_SUBSTITUTE
    assert rows["reddit"]["label"] == "reddit_fenced"
    assert {"wikipedia_pageviews", "gdelt_doc_timeline"} <= set(rows["reddit"]["substitutes"])
    assert "Discord" in rows["reddit"]["reason"] and "commercial" in rows["reddit"]["reason"]
    assert "automated" in rows["stocktwits"]["reason"]


def test_rows_are_recognised_by_source_route_url_and_contribution() -> None:
    assert tf.fenced_row({}, "reddit") == "reddit"
    assert tf.fenced_row({"source": "ext_reddit_EURUSD_session_range_breakout"}) == "reddit"
    assert tf.fenced_row({"route": "reddit", "ground": "r/Forex"}) == "reddit"
    assert tf.fenced_row({"url": "https://old.reddit.com/r/x/comments/1"}, "world") == "reddit"
    assert tf.fenced_row({"source": "forexfactory", "url": "https://forexfactory.com"}) is None
    shared = {"source": "miner:forexfactory", "contributing_sources": ["forexfactory", "reddit"]}
    assert tf.fenced_row(shared) is None, "the compiler refuses the ROW, not a shared cell"
    assert tf.touched_row(shared) == "reddit", "the labeller marks the cell a fenced row touched"


def test_label_row_stamps_without_touching_identity_or_a_provenance_dict() -> None:
    row = {"symbol": "EURUSD", "family": "session_range_breakout", "params": {"rr": 1.5},
           "source": "miner:reddit", "provenance": {"input_version_id": "v1"}}
    before = {k: row[k] for k in ("symbol", "family", "params", "provenance")}
    assert tf.label_row(row) == "reddit_fenced"
    assert row["provenance_label"] == "reddit_fenced"
    assert {k: row[k] for k in before} == before
    assert tf.label_row({"source": "miner:forexfactory"}) is None


# ------------------------------------------------------------- no Reddit route fetches -----
def test_no_reddit_route_opens_a_connection(wire: _Tripwire, tmp_path: Path,
                                            monkeypatch: pytest.MonkeyPatch) -> None:
    """THE PIN. Every Reddit route the tree carried -- the side-channel miner, deep_forest's
    reddit ground, free_data.reddit_hot / _get, polite_fetch, the world crawler and the hourly
    `mine` seeds -- is driven here and none of them may open a connection to a Reddit host."""
    import deep_forest_miner as dfm
    import free_data as fd
    import reddit_miner as rm
    import world_crawler as wc

    monkeypatch.setattr(rm, "FENCE_OUT", tmp_path / "reddit_miner.json")
    assert rm.run_and_save() == []
    assert rm.mine_all() == [] and rm.mine_subreddit("Forex") == []
    fence = json.loads((tmp_path / "reddit_miner.json").read_text("utf-8"))
    assert fence["status"] == tf.BLOCKED_WITH_SUBSTITUTE and fence["fetched"] == 0
    assert fence["written_to_intelligence"] is False

    assert fd.reddit_hot("algotrading") == []
    with pytest.raises(tf.TermsFenced):
        fd._get("https://www.reddit.com/r/algotrading/hot.json")

    out = dfm._Run.ground_reddit(object(), {"subs": ["Forex", "Gold"]})  # type: ignore[arg-type]
    assert out["status"] == tf.BLOCKED_WITH_SUBSTITUTE and out["claims"] == 0
    assert dfm.fenced_ground({"route": "reddit", "subs": ["x"]}) == "reddit"
    ca = "https://www.reddit.com/r/CanadianInvestor/"
    assert dfm.fenced_ground({"route": "http", "url": ca}) == "reddit"
    assert dfm.fenced_ground({"route": "http", "url": "https://forum.valuepickr.com/"}) is None

    r = pf.get("https://old.reddit.com/r/algotrading/top/.json", leg="test_fence")
    assert not r.ok and "BLOCKED_WITH_SUBSTITUTE" in r.error and r.attempts == 0

    raw, why = wc.fetch("https://www.reddit.com/r/algotrading/top/?t=week")
    assert raw is None and why.startswith("BLOCKED_WITH_SUBSTITUTE")
    assert not [s for s in wc.SEEDS if tf.platform_of_url(s)], "a Reddit seed is back"

    import hourly_cycle as hc
    monkeypatch.setattr(hc, "BASE", tmp_path)
    (tmp_path / "data").mkdir(exist_ok=True)
    hc.mine()

    assert wire.reddit() == [], f"a Reddit route reached the network: {wire.reddit()}"


def test_crowding_miner_reads_the_attention_substitute_not_reddit(
        monkeypatch: pytest.MonkeyPatch) -> None:
    import crowding_miner as cm
    import free_data as fd

    def fake_get(url: str, timeout: int = 25, headers: dict | None = None) -> bytes:
        tf.check_url(url)
        assert "wikimedia.org" in url
        start = datetime(2026, 8, 1)
        items = [{"timestamp": (start + timedelta(days=i)).strftime("%Y%m%d00"),
                  "views": 1000 + (i % 5) * 20 + (400 if i >= 53 else 0)} for i in range(60)]
        return json.dumps({"items": items}).encode()

    monkeypatch.setattr(fd, "_get", fake_get)
    att = fd.attention_proxy()
    assert att["status"] == "MEASURED" and att["source"] == "wikipedia_pageviews"
    assert att["z_7d"] is not None and att["z_7d"] > 0
    fence = cm.reddit_fence()
    assert fence["status"] == tf.BLOCKED_WITH_SUBSTITUTE and fence["platform"] == "reddit"
    src = Path(cm.__file__).read_text("utf-8")
    assert "fd.reddit_hot(" not in src and "fd.attention_proxy()" in src


def test_attention_proxy_is_unmeasured_never_zero_when_nothing_answers(
        monkeypatch: pytest.MonkeyPatch) -> None:
    import free_data as fd

    def dead(url: str, timeout: int = 25, headers: dict | None = None) -> bytes:
        raise OSError("down")

    monkeypatch.setattr(fd, "_get", dead)
    assert fd.attention_proxy()["status"] == "UNMEASURED"


# ----------------------------------------------------------- existing cells: label only ----
def test_the_docket_labeller_counts_and_changes_nothing_else() -> None:
    import merge_hypotheses as mh
    rows = [{"symbol": "EURUSD", "family": "session_range_breakout", "params": {"rr": 1.5},
             "source": "ext_reddit_EURUSD_session_range_breakout", "t_stat": 3.17},
            {"symbol": "XAUUSD", "family": "overnight_gap_decay", "params": {},
             "source": "miner:reddit", "contributing_sources": ["reddit"]},
            {"symbol": "GBPUSD", "family": "overnight_gap_decay", "params": {},
             "source": "miner:forexfactory"}]
    order = [r["symbol"] for r in rows]
    rep = mh.label_terms_fenced(rows)
    assert rep["labelled"] == {"reddit_fenced": 2} and rep["total"] == 2
    assert [r["symbol"] for r in rows] == order and rows[0]["t_stat"] == 3.17
    assert "provenance_label" not in rows[2]


# -------------------------------------------------------------------- the substitutes ----
def _fake_fetch(calls: list[str]) -> Any:
    def fetch(url: str) -> tuple[int | None, str]:
        calls.append(url)
        assert tf.platform_of_url(url) is None
        if "wikimedia.org" in url:
            start = NOW - timedelta(days=120)
            items = [{"timestamp": (start + timedelta(days=i)).strftime("%Y%m%d00"),
                      "views": 1000 + (i % 7) * 10 + (500 if i % 29 == 0 else 0)}
                     for i in range(120)]
            return 200, json.dumps({"items": items})
        if "gdeltproject.org" in url:
            start = NOW - timedelta(days=90)
            data = [{"date": (start + timedelta(hours=6 * i)).strftime("%Y%m%dT%H%M%SZ"),
                     "value": 5 + i % 11} for i in range(4 * 90)]
            return 200, json.dumps({"timeline": [{"series": "Article Count", "data": data}]})
        return 404, "HTTP 404"
    return fetch


def test_substitutes_publish_pit_lake_series_and_charge_every_minted_cell(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    import attention_substitutes as A
    import proposer_common as pc

    paths = A.Paths(tmp_path)
    paths.universe.parent.mkdir(parents=True)
    paths.universe.write_text(json.dumps({"XAUUSD": {}, "EURUSD": {}}), "utf-8")
    donated: dict[str, Any] = {}

    def fake_donate(source: str, cands: list[dict], tests_run: int) -> Path:
        donated.update({"source": source, "n": len(cands), "tests_run": tests_run,
                        "rows": cands})
        return tmp_path / "intel" / source / "discoveries_x.json"

    monkeypatch.setattr(pc, "donate", fake_donate)
    monkeypatch.setattr(pc, "donation_counts",
                        lambda: {"donated": donated.get("n", 0)})
    monkeypatch.setattr(A, "ROSTER", {k: A.ROSTER[k] for k in ("XAUUSD", "EURUSD", "US500")})
    calls: list[str] = []
    doc = A.run(fetch=_fake_fetch(calls), paths=paths, now=NOW)

    assert calls and not [c for c in calls if tf.platform_of_url(c)]
    lake = sorted(p.name for p in paths.series.glob("*.csv"))
    assert "attn_wiki__en_Gold_as_an_investment.csv" in lake and "attn_gdelt__xauusd.csv" in lake
    # POINT-IN-TIME: every value is available no earlier than its day's end + LAG_H.
    import csv
    with (paths.series / "attn_gdelt__xauusd.csv").open(encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh))
    for r in rows:
        ev = datetime.fromisoformat(r["event_time"])
        av = datetime.fromisoformat(r["available_time"])
        assert av >= ev + timedelta(hours=A.LAG_H)
    assert all(r["event_time"][:10] <= NOW.strftime("%Y-%m-%d") for r in rows), \
        "today's partial day is never published"
    # A day first seen on a LATER fetch is never available before the desk saw it.
    later = NOW + timedelta(days=2)
    fresh = A.merge_obs(paths, "attn_gdelt__xauusd", {"2026-09-30": 7.0, "2026-10-01": 9.0}, later)
    new_row = next(r for r in fresh if r["event_time"].startswith("2026-10-02"))
    assert datetime.fromisoformat(new_row["available_time"]) >= later
    # The conditioner family can load what was published.
    from mt5desk.family_exogenous_conditioner import conditioner
    s = conditioner("attn_wiki__en_Gold_as_an_investment", "value", "level_z",
                    root=paths.series)
    assert s is not None and len(s) > 30
    # CELLS: US500 is not in this registry, so only XAUUSD and EURUSD series mint.
    cells = doc["cells"]
    assert cells["grid"] > 0 and cells["minted"] == cells["built"] == donated["n"]
    assert donated["tests_run"] == donated["n"] == cells["trials_charged"], \
        "every minted cell is charged to the trial census"
    assert donated["source"] == "attention_substitutes"
    assert {c["symbol"] for c in donated["rows"]} <= {"XAUUSD", "EURUSD"}
    assert all(c["family"] == "exogenous_conditioner" for c in donated["rows"])
    assert any("US500" in why for why in cells["skipped"].values())
    assert json.loads(paths.report.read_text("utf-8"))["status"] == "RAN"


def test_volume_is_measured_before_and_after_and_unmeasured_is_named(tmp_path: Path) -> None:
    import attention_substitutes as A
    paths = A.Paths(tmp_path)
    assert A.attention_volume(paths, NOW)["volume_held"] == "UNMEASURED"
    red = paths.intel / "reddit"
    red.mkdir(parents=True)
    for d in ("20260905_0101", "20260906_0101"):
        (red / f"discoveries_{d}.json").write_text(json.dumps([{}] * 10), "utf-8")
    sub = paths.intel / "attention_substitutes"
    sub.mkdir(parents=True)
    (sub / "discoveries_20260929_1200.json").write_text(
        json.dumps({"discoveries": [{}] * 240}), "utf-8")
    vol = A.attention_volume(paths, NOW)
    assert vol["reddit_rows_per_active_day"] == 10.0
    assert vol["substitute_cells_per_day"] == round(240 / 7, 2)
    assert vol["volume_held"] is True


def test_an_unreachable_door_is_a_named_status_and_mints_nothing(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    import attention_substitutes as A
    paths = A.Paths(tmp_path)
    monkeypatch.setattr(A, "ROSTER", {"XAUUSD": A.ROSTER["XAUUSD"]})
    doc = A.run(fetch=lambda url: (503, "HTTP 503"), paths=paths, now=NOW, dry_run=True)
    assert {r["status"] for r in doc["series"].values()} == {"HTTP 503"}
    assert doc["cells"]["grid"] == 0 and doc["cells"]["minted"] == 0
