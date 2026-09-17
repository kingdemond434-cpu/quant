"""M8 scout swarm: the plan, the steering, the harvest, the expansion edges and the crawl gate.

NOTHING HERE STARTS A PROCESS. `scout_swarm.run_organ` is stubbed in every test that runs a pass,
so the suite records WHICH organ would have been run with WHICH arguments instead of launching a
crawler from a unit test. The organ paths are the REAL ones off `scout_roster.DECLARED_BEATS`,
because the point of the steering test is that `deep_forest_miner` actually declares `--region`
today and `china_miner` actually declares nothing -- a synthetic path would make the test agree
with itself and tell the desk nothing about its own tree.

Everything else is synthetic and under tmp_path: the registry (`registry.set_path` plus a
monkeypatched `BACKUP`, so the desk's own sqlite is never opened), the seat directories, the lock
and the artifact.
"""
from __future__ import annotations

import json
import sys
import time
from collections import Counter
from pathlib import Path
from typing import Any

import pytest

DESK = Path(__file__).resolve().parents[1]
ROOT = DESK.parents[1]
for _p in (str(DESK / "research"), str(DESK), str(ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import scout_swarm as sw  # noqa: E402
import source_frontier as sf  # noqa: E402

from libs.moat import registry as R  # noqa: E402

#: A real steerable organ (--region/--only), a real unsteerable one (no argparse at all), and the
#: seat the roster maps to it. Both files exist in this tree and neither is executed.
FOREST = "desks/mt5/research/deep_forest_miner.py"
CHINA = "desks/mt5/side_channels/china_miner.py"

BEATS: tuple[dict[str, Any], ...] = (
    {"beat": "ChinaScout", "organs": (FOREST, CHINA), "languages": ("zh",), "regions": ("cn",),
     "kinds": (), "scope": "grounds"},
    {"beat": "KoreaScout", "organs": (CHINA,), "languages": ("ko",), "regions": ("kr",),
     "kinds": (), "scope": "grounds"},
)

PLANTED_ROWS = [
    {"source": "china", "kind": "story", "title": "carry desk note",
     "text": "A study by Jane Smith shows the overnight carry premium; code at "
             "https://github.com/quantdesk/carrylab and data at "
             "https://fred.stlouisfed.org/series/DTWEXBGS . Discussion on "
             "https://www.reddit.com/r/algotrading/comments/abc . See arXiv:2401.01234 . "
             "The kurtosis of the kurtosis regime is what the kurtosis screen reads.",
     "url": "https://www.7hcn.com/article/1.html"},
    {"source": "china", "kind": "story", "title": "second note",
     "text": "The same kurtosis idea again, cited from 10.1234/abcd.5678"},
]


@pytest.fixture
def swarm(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    tmp = Path(str(tmp_path))
    monkeypatch.setattr(R, "BACKUP", tmp / "no_backup")
    R.set_path(tmp / "alpha_registry.sqlite")
    seats = tmp / "intelligence"
    (seats / "china").mkdir(parents=True)
    monkeypatch.setattr(sw, "SEAT_ROOTS", (seats,))
    monkeypatch.setattr(sw, "OUT", tmp / "SCOUT_SWARM.json")
    monkeypatch.setattr(sw, "LOCKS", tmp / "locks")
    monkeypatch.setattr(sw, "LOCK", tmp / "locks" / "scout_swarm.lock")
    monkeypatch.setattr(sf, "GROUNDS", tmp / "absent_grounds.json")
    monkeypatch.setattr(sf, "REGISTRY_JSON", (tmp / "absent_registry.json",))
    monkeypatch.setattr(sf, "_mechanism_class", lambda text: "carry")
    yield tmp
    R.set_path(None)


@pytest.fixture
def runs(monkeypatch: pytest.MonkeyPatch) -> list[dict[str, Any]]:
    """Stub the subprocess runner: record the call, launch nothing."""
    calls: list[dict[str, Any]] = []

    def _fake(organ: str, args: list[str], timeout_s: float) -> dict[str, Any]:
        calls.append({"organ": organ, "args": list(args), "timeout_s": timeout_s})
        return {"status": "ok", "rc": 0, "seconds": 0.01, "tail": "stub"}

    monkeypatch.setattr(sw, "run_organ", _fake)
    return calls


def _plant_seat_rows(tmp: Path, rows: list[dict[str, Any]], seat: str = "china") -> Path:
    p = tmp / "intelligence" / seat / "discoveries_test.json"
    p.write_text(json.dumps(rows, ensure_ascii=False), encoding="utf-8")
    now = time.time()
    import os
    os.utime(p, (now, now))
    return p


def _plant_sources() -> None:
    sf.register_source("ground:cn:cn_forum", kind="forum", language="zh", country="cn",
                       discovered_via="seed", url="https://example.cn/f")
    sf.register_source("ground:kr:kr_board", kind="community", language="ko", country="kr",
                       discovered_via="seed", url="https://example.kr/b")
    sf.register_source("seat:china", kind="seat", language="zh", country="cn",
                       discovered_via="seed")


# --------------------------------------------------------------------------------- the plan

def test_plan_gives_every_beat_its_floor_and_splits_the_rest_by_measured_roi(swarm):
    _plant_sources()
    sf.bump_source_yield("ground:cn:cn_forum", leads=20, mechanisms=10, candidates=12)
    rows = sw.plan(600.0, beats=BEATS)
    by = {r["beat"]: r for r in rows}
    assert by["ChinaScout"]["measured"] is True and by["ChinaScout"]["roi"] > 0
    assert by["KoreaScout"]["measured"] is False
    assert sf.UNMEASURED in by["KoreaScout"]["basis"]
    floor = min(sw.BEAT_FLOOR, 1.0 / len(BEATS))
    assert all(r["share"] >= floor - 1e-9 for r in rows)
    assert by["ChinaScout"]["share"] > by["KoreaScout"]["share"]
    assert sum(r["share"] for r in rows) == pytest.approx(1.0, abs=1e-5)
    assert sum(r["budget_s"] for r in rows) == pytest.approx(600.0, abs=0.05)


def test_an_unmeasured_swarm_splits_evenly_rather_than_starving_every_beat(swarm):
    _plant_sources()
    rows = sw.plan(100.0, beats=BEATS)
    assert all(not r["measured"] for r in rows)
    assert rows[0]["share"] == pytest.approx(rows[1]["share"], abs=1e-6)


# ------------------------------------------------------------------------------- the steering

def test_a_steerable_organ_is_pointed_at_the_chosen_cells_and_an_unsteerable_one_says_so(swarm):
    cells = [{"cell": "zh|cn|forum|fx|carry", "mode": "exploration",
              "axes": {"language": "zh", "country": "cn", "source_type": "forum",
                       "asset_class": "fx", "mechanism_class": "carry"}, "why": "planted"}]
    args, used = sw.steer_args(FOREST, cells, 120.0)
    assert "--region" in args and args[args.index("--region") + 1] == "cn"
    assert "--only" in args and "zh" in args
    assert set(used) == {"region", "grounds"}
    assert sw.steer_args(CHINA, cells, 120.0) == ([], [])
    # The table is checked against the organ's OWN argparse, so a renamed flag drops out.
    assert "--region" in sw.organ_flags(FOREST)
    assert sw.organ_flags(CHINA) == frozenset()


def test_a_cell_whose_axes_are_unmeasured_never_becomes_a_steering_argument(swarm):
    cells = [{"cell": "unmeasured|unmeasured|seat|unmeasured|unmeasured", "mode": "cold",
              "axes": {"language": "UNMEASURED", "country": "unmeasured",
                       "source_type": "seat", "asset_class": "unmeasured",
                       "mechanism_class": "unmeasured"}, "why": "cold"}]
    args, used = sw.steer_args(FOREST, cells, 90.0)
    assert used == []                                  # budget only, never a fabricated region
    assert "--region" not in args and "--only" not in args
    assert args[:1] == ["--budget-s"]


# ------------------------------------------------------------------------------- the expansions

def test_expansion_edges_find_the_author_the_repo_the_dataset_the_community_and_the_term(swarm):
    conn = R.connect()
    try:
        df, n_docs = sw.desk_vocabulary(conn)
        edges = sw.expansion_edges(PLANTED_ROWS, df, n_docs)
    finally:
        conn.close()
    assert "Jane Smith" in edges["authors"]
    assert any("github.com/quantdesk/carrylab" in u for u in edges["repos"])
    assert any("fred.stlouisfed.org" in u for u in edges["datasets"])
    assert any("reddit.com" in u for u in edges["communities"])
    assert any("2401.01234" in c or "10.1234" in c for c in edges["citations"])
    terms = [t["term"] for t in edges["terminology"]]
    assert "kurtosis" in terms
    assert all(t not in terms for t in ("market", "trading", "https"))


def test_terminology_is_tf_idf_against_the_vocabulary_the_desk_already_has(swarm):
    df = Counter({"carry": 500, "kurtosis": 0})
    scored = {t["term"]: t["tfidf"] for t in sw.terminology(
        ["carry carry kurtosis kurtosis"], df, 500)}
    assert scored["kurtosis"] > scored["carry"]        # same tf, but the desk has never said it


def test_crypto_exchange_ground_is_refused_by_the_mandate_and_never_registered(swarm):
    _plant_sources()
    sf.bump_source_yield("seat:china", leads=50, candidates=30)
    conn = R.connect()
    try:
        edges = {"repos": ["https://github.com/ok/fine"],
                 "communities": ["https://www.binance.com/en/support/faq"],
                 "datasets": ["https://api.bybit.com/v2/public/tickers"],
                 "citations": [], "authors": [], "terminology": []}
        got = sw.register_expansions("seat:china", edges, conn)
        rows = sf.sources(conn=conn)
    finally:
        conn.close()
    assert got["refused_by_mandate"] == 2
    assert got["registered"] == 1
    assert not any("binance" in s or "bybit" in s for s in rows)


def test_candidate_sources_are_registered_with_their_parent_and_never_crawled(swarm):
    _plant_sources()
    sf.bump_source_yield("seat:china", leads=50, candidates=30)       # P(testable) ~ 0.60
    conn = R.connect()
    try:
        edges = {"repos": ["https://github.com/quantdesk/carrylab"], "communities": [],
                 "datasets": [], "citations": [], "authors": ["Jane Smith"],
                 "terminology": [{"term": "kurtosis", "tf": 3, "tfidf": 9.0}]}
        got = sw.register_expansions("seat:china", edges, conn)
        rows = sf.sources(conn=conn)
    finally:
        conn.close()
    assert got["registered"] == 3 and got["crawl_allowed"] is True
    repo = rows["repo:github.com/quantdesk/carrylab"]
    assert repo["status"] == "candidate"
    assert repo["discovered_from"] == "seat:china"
    assert repo["discovered_via"] == "expansion:repos"
    assert repo["last_crawled"] is None                # registration is not permission to fetch
    assert json.loads(repo["meta_json"])["crawl_allowed"] is True
    assert "author:Jane_Smith" in rows and "term:kurtosis" in rows
    assert rows["term:kurtosis"]["kind"] == "terminology"


def test_a_prior_only_parent_never_opens_the_crawl_gate(swarm):
    _plant_sources()
    conn = R.connect()
    try:
        got = sw.register_expansions("seat:china", {"repos": ["https://github.com/a/b"]}, conn)
        meta = json.loads(sf.sources(conn=conn)["repo:github.com/a/b"]["meta_json"])
    finally:
        conn.close()
    assert got["crawl_allowed"] is False
    assert sf.UNMEASURED in got["gate"]
    assert got["registered"] == 1                      # recorded, but not opened
    assert meta["crawl_allowed"] is False


# ------------------------------------------------------------------------------------ the pass

def test_one_pass_runs_the_stubbed_organs_with_the_chosen_cells_and_pays_the_sources(swarm, runs):
    _plant_sources()
    _plant_seat_rows(swarm, PLANTED_ROWS)
    sf.bump_source_yield("ground:cn:cn_forum", leads=20, mechanisms=10, candidates=12)
    doc = sw.run_pass(budget_s=60.0, beats=BEATS)

    assert [r["organ"] for r in runs].count(FOREST) == 1
    assert [r["organ"] for r in runs].count(CHINA) == 2
    forest = next(r for r in runs if r["organ"] == FOREST)
    assert "--budget-s" in forest["args"]

    china = next(b for b in doc["beats"] if b["beat"] == "ChinaScout")
    assert china["status"] == "ok"
    assert china["cells"] and china["leads"] == len(PLANTED_ROWS)
    assert china["leads_by_source"] == {"seat:china": 2}
    assert china["new_sources"] >= 1
    assert china["steerable"] is True and "region" in china["steered_by"]
    korea = next(b for b in doc["beats"] if b["beat"] == "KoreaScout")
    assert korea["steerable"] is False and korea["steering_note"]

    roi = sf.source_roi("seat:china")
    assert roi["leads"] == 2.0                          # the pass paid the seat for its two leads
    workers = {w["worker_id"]: w for w in R.workers_alive()}
    assert workers["scout:ChinaScout"]["kind"] == "scout"
    assert workers["scout:ChinaScout"]["beat"] == "ChinaScout"
    assert workers["scout:KoreaScout"]["beat"] == "KoreaScout"


def test_the_report_carries_the_rule_the_expansions_and_the_cold_floor(swarm, runs):
    _plant_sources()
    _plant_seat_rows(swarm, PLANTED_ROWS)
    doc = sw.run_pass(budget_s=60.0, beats=BEATS)
    assert doc["rule"].startswith("every productive source spawns searches")
    assert doc["cold_floor"] == sf.COLD_FLOOR
    assert doc["cold_share_actual"] is None or doc["cold_share_actual"] >= sf.COLD_FLOOR
    assert set(doc["expansions"]) == {"authors", "citations", "repos", "communities", "datasets",
                                      "terminology"}
    assert any("github.com" in u for u in doc["expansions"]["repos"])
    assert doc["unmeasured"]["n_beats_unsteerable"] == 1
    assert "P(testable)" in doc["unmeasured"]["crawl_gate"]
    sf._atomic(sw.OUT, doc)
    assert json.loads(sw.OUT.read_text(encoding="utf-8"))["rule"] == doc["rule"]


def test_a_scouted_cell_is_stamped_so_exploration_moves_on_next_pass(swarm, runs):
    _plant_sources()
    sf.bump_source_yield("ground:cn:cn_forum", leads=5)
    doc = sw.run_pass(budget_s=60.0, beats=BEATS)
    worked = {c for b in doc["beats"] for c in b["cells"]}
    conn = R.connect()
    try:
        stamped = {str(r["cell"]) for r in conn.execute(
            "SELECT cell FROM frontier_map WHERE last_scouted IS NOT NULL")}
    finally:
        conn.close()
    assert worked and worked <= stamped


def test_dry_run_plans_everything_and_runs_nothing(swarm, runs):
    _plant_sources()
    _plant_seat_rows(swarm, PLANTED_ROWS)
    doc = sw.run_pass(budget_s=60.0, dry=True, beats=BEATS)
    assert runs == []
    assert all(o["status"] == "DRY_RUN" for b in doc["beats"] for o in b["organs_run"])
    assert doc["pass"]["dry_run"] is True
    conn = R.connect()
    try:
        rows = sf.sources(conn=conn)
        n_workers = conn.execute("SELECT COUNT(*) FROM workers").fetchone()[0]
        n_yield = conn.execute("SELECT COUNT(*) FROM source_yield").fetchone()[0]
        n_map = conn.execute("SELECT COUNT(*) FROM frontier_map").fetchone()[0]
    finally:
        conn.close()
    assert not any(r["status"] == "candidate" for r in rows.values())
    assert n_workers == 0 and n_yield == 0
    assert n_map == 0                                   # not even the durable map is refreshed
    assert not sw.OUT.exists()


def test_the_cli_dry_run_writes_no_artifact(swarm, runs, capsys):
    _plant_sources()
    assert sw.main(["--dry-run", "--budget-s", "5"]) == 0
    assert runs == []
    assert not sw.OUT.exists()
    assert "DRY RUN" in capsys.readouterr().out


def test_only_one_swarm_holds_the_slot(swarm):
    first = sw.claim_singleton(sw.LOCK)
    assert first is not None
    try:
        assert sw.claim_singleton(sw.LOCK) is None
    finally:
        first.close()
    second = sw.claim_singleton(sw.LOCK)
    assert second is not None
    second.close()


def test_a_beat_whose_organs_have_no_seat_says_its_harvest_is_unattributable(swarm, runs):
    _plant_sources()
    forest_only = ({"beat": "ForumScout", "organs": (FOREST,), "languages": ("*",),
                    "regions": ("*",), "kinds": (), "scope": "grounds"},)
    doc = sw.run_pass(budget_s=30.0, beats=forest_only)
    beat = doc["beats"][0]
    assert sw.seats_of(FOREST) == ()
    assert sf.UNMEASURED in beat["harvest_basis"]
    assert beat["leads"] == 0
