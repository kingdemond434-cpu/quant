"""M10 source frontier: seeding, Chao1, cold cells, the three assignment modes and source ROI.

EVERY TEST RUNS AGAINST A REGISTRY IN tmp_path. `registry.set_path(tmp)` moves the canonical
sqlite file and `registry.BACKUP` is monkeypatched to a path that does not exist, so a fresh empty
registry is built for each test and the desk's own `data/alpha_registry.sqlite` is never opened,
never restored from the moat backup and never written.

The grounds file and the source registry JSON are synthetic too. The claims, the source_yield
counters and the generator yields are PLANTED with known frequencies, because Chao1 and a Jeffreys
posterior are the whole claim this organ makes: a hand-rolled estimator that is subtly wrong is
worse than none, and the only way to know is to check it against its closed form on a table whose
answer can be computed by hand.
"""
from __future__ import annotations

import json
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest

DESK = Path(__file__).resolve().parents[1]
ROOT = DESK.parents[1]
for _p in (str(DESK / "research"), str(DESK), str(ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import source_frontier as sf  # noqa: E402

from libs.moat import registry as R  # noqa: E402

GROUNDS_DOC = {
    "grounds": [
        {"name": "cn forum", "region": "cn", "language": "zh", "kind": "forum",
         "route": "http", "weight": 1.5, "url": "https://example.cn/forum", "why": "x"},
        {"name": "jp blog", "region": "jp", "language": "ja", "kind": "blog",
         "route": "http", "weight": 1.0, "url": "https://example.jp/blog", "why": "y"},
    ],
}
REGISTRY_DOC = {"sources": {
    "ground:cn:cn_forum": {"source_id": "ground:cn:cn_forum", "name": "cn forum",
                           "kind": "forum", "language": "zh", "region": "cn",
                           "url": "https://example.cn/forum", "n_leads": 20, "n_testable": 4,
                           "n_certified": 1},
    "seat:quiet": {"source_id": "seat:quiet", "name": "quiet", "kind": "seat", "language": "en",
                   "region": "us", "n_leads": 0, "n_testable": 0, "n_certified": 0},
}}


@pytest.fixture
def frontier(tmp_path: pytest.TempPathFactory, monkeypatch: pytest.MonkeyPatch) -> Path:
    """A whole synthetic desk: tmp registry, tmp grounds, tmp source registry, tmp artifact."""
    tmp = Path(str(tmp_path))
    monkeypatch.setattr(R, "BACKUP", tmp / "no_backup")
    R.set_path(tmp / "alpha_registry.sqlite")
    grounds = tmp / "deep_forest_sources.json"
    grounds.write_text(json.dumps(GROUNDS_DOC), encoding="utf-8")
    registry_json = tmp / "source_registry.json"
    registry_json.write_text(json.dumps(REGISTRY_DOC), encoding="utf-8")
    monkeypatch.setattr(sf, "GROUNDS", grounds)
    monkeypatch.setattr(sf, "REGISTRY_JSON", (registry_json,))
    monkeypatch.setattr(sf, "OUT", tmp / "SOURCE_FRONTIER.json")
    # The mechanism classifier is `mechanism_claims`' job, not this organ's: pinning it keeps a
    # cell key deterministic without testing somebody else's vocabulary.
    monkeypatch.setattr(sf, "_mechanism_class",
                        lambda text: "carry" if "carry" in str(text) else "positioning")
    yield tmp
    R.set_path(None)


def _plant_source(sid: str, **cols: Any) -> None:
    sf.register_source(sid, kind=cols.get("kind", "forum"), language=cols.get("language", "zh"),
                       country=cols.get("country", "cn"), url=cols.get("url", ""),
                       discovered_via=cols.get("discovered_via", "seed"),
                       discovered_from=cols.get("discovered_from", "test"),
                       status=cols.get("status", "active"),
                       last_crawled=cols.get("last_crawled"))


def _plant_claim(claim_id: str, source_id: str, mechanism_id: str, *, text: str = "carry trade",
                 at: str | None = None, instruments: list[str] | None = None) -> None:
    conn = R.connect()
    try:
        conn.execute("INSERT INTO claims(claim_id, created_at, doc_id, source_id, text, language, "
                     "mechanism_id, instruments_json, kind) VALUES(?,?,?,?,?,?,?,?,?)",
                     (claim_id, at or sf.now(), "doc", source_id, text, "zh", mechanism_id,
                      json.dumps(instruments or []), "story"))
        conn.commit()
    finally:
        conn.close()


# --------------------------------------------------------------------------------- the seeding

def test_seeding_reads_both_grounds_and_registry_and_marks_the_founder_population(frontier):
    got = sf.seed_sources()
    assert got["grounds"] == 2 and got["registry_rows"] == 2
    rows = sf.sources()
    assert "ground:cn:cn_forum" in rows and "ground:jp:jp_blog" in rows and "seat:quiet" in rows
    assert all(r["discovered_via"] == "seed" for r in rows.values())
    assert rows["ground:jp:jp_blog"]["language"] == "ja"
    assert rows["ground:jp:jp_blog"]["country"] == "jp"
    # A re-seed is idempotent and never overwrites what the swarm learned since.
    again = sf.seed_sources()
    assert again["inserted"] == 0
    assert len(sf.sources()) == len(rows)


def test_seeding_carries_the_registrys_measured_counters_so_a_yielding_ground_is_not_cold(
        frontier):
    """A ground with 20 measured leads published as "no lead ever" is not a degenerate start, it
    is a false statement that would send the cold lane at ground that is already yielding."""
    sf.seed_sources()
    roi = sf.source_roi("ground:cn:cn_forum")
    assert roi["leads"] == 20.0
    assert roi["p_testable"]["k"] == 4.0 and not roi["p_testable"]["prior_only"]
    assert sf.source_roi("seat:quiet")["p_testable"]["prior_only"] is True
    cold = {c["cell"] for c in sf.build_cells() if c["cold"]}
    assert not any(c.startswith("zh|cn|forum") for c in cold)


# ------------------------------------------------------------------------------- the estimators

def test_chao1_on_a_planted_singleton_and_doubleton_mix_equals_its_closed_form():
    # f1 = 2 singletons, f2 = 1 doubleton -> 2^2 / (2 * 1) = 2.0
    assert sf.chao1_unseen([1, 1, 2, 5]) == pytest.approx(2.0)
    # f2 = 0, so the bias-corrected branch: f1 (f1 - 1) / 2 = 3 * 2 / 2 = 3.0
    assert sf.chao1_unseen([1, 1, 1, 3]) == pytest.approx(3.0)
    # A cell that only ever repeats itself is exhausted: no singleton, no unseen mass.
    assert sf.chao1_unseen([3, 3, 4]) == pytest.approx(0.0)
    assert sf.chao1_unseen([]) == pytest.approx(0.0)


def test_cells_carry_chao1_singletons_doubletons_and_the_discovery_curve(frontier):
    _plant_source("s1", kind="forum", language="zh", country="cn")
    plan = ["m1", "m2", "m3", "m3", "m4", "m4", "m4", "m4", "m4"]
    for i, mech in enumerate(plan):
        _plant_claim(f"c{i:02d}", "s1", mech, at=f"2026-09-1{i // 5}T0{i % 5}:00:00+00:00")
    cells = {c["cell"]: c for c in sf.build_cells()}
    key = sf.cell_key("zh", "cn", "forum", sf.UNMEASURED, "carry")
    cell = cells[key]
    assert cell["n_leads"] == 9 and cell["n_distinct"] == 4
    assert cell["n_singletons"] == 2 and cell["n_doubletons"] == 1     # m1, m2 once; m3 twice
    assert cell["chao1_unseen"] == pytest.approx(2.0)
    assert cell["cold"] is False
    curve = cell["discovery_curve"]
    assert curve[0] == {"leads": 9, "new_mechanisms": 4, "distinct_so_far": 4}
    assert cell["last_scouted"] == "2026-09-11T03:00:00+00:00"     # the newest planted claim


def test_a_source_that_never_produced_a_lead_is_a_cold_cell_with_no_unseen_mass(frontier):
    _plant_source("busy", kind="forum", language="zh", country="cn")
    _plant_source("silent", kind="community", language="ko", country="kr")
    _plant_claim("c1", "busy", "m1")
    cells = {c["cell"]: c for c in sf.build_cells()}
    cold_key = sf.cell_key("ko", "kr", "community", sf.UNMEASURED, sf.UNMEASURED)
    assert cells[cold_key]["cold"] is True
    assert cells[cold_key]["n_leads"] == 0
    assert cells[cold_key]["chao1_unseen"] is None                 # nobody looked: not a zero
    assert cells[cold_key]["discovery_curve"] is None
    assert cells[sf.cell_key("zh", "cn", "forum", sf.UNMEASURED, "carry")]["cold"] is False


# ------------------------------------------------------------------------------- the assignment

def test_exploration_takes_the_highest_unseen_mass_and_skips_a_freshly_scouted_cell(frontier):
    _plant_source("rich", kind="forum", language="zh", country="cn")
    _plant_source("poor", kind="blog", language="ja", country="jp")
    old = "2026-01-01T00:00:00+00:00"                             # long outside the recent window
    for i, mech in enumerate(["a", "b", "c", "d", "e", "e"]):     # f1=4, f2=1 -> 8.0
        _plant_claim(f"r{i}", "rich", mech, at=old)
    for i, mech in enumerate(["x", "y", "y"]):                    # f1=1, f2=1 -> 0.5
        _plant_claim(f"p{i}", "poor", mech, text="positioning", at=old)
    cells = sf.build_cells()
    first = sf.assign(1, "exploration", cells=cells)
    assert first[0]["cell"].startswith("zh|cn|forum")
    assert "unseen mass 8.00" in first[0]["why"]
    # Scouted a minute ago, so exploration must move on to the next-best cell.
    now = datetime.now(tz=UTC)
    for cell in cells:
        if cell["cell"].startswith("zh|cn|forum"):
            cell["last_scouted"] = (now - timedelta(seconds=60)).isoformat()
    moved = sf.assign(1, "exploration", cells=cells, now_dt=now)
    assert moved[0]["cell"].startswith("ja|jp|blog")
    # And when EVERY cell was just scouted, exploration still answers -- and says it is a fallback.
    for cell in cells:
        cell["last_scouted"] = (now - timedelta(seconds=60)).isoformat()
    last = sf.assign(1, "exploration", cells=cells, now_dt=now)
    assert last[0]["cell"].startswith("zh|cn|forum") and "FALLBACK" in last[0]["why"]


def test_exploitation_goes_to_the_neighbourhood_of_the_best_posterior_source(frontier):
    _plant_source("good", kind="forum", language="zh", country="cn")
    _plant_source("meh", kind="blog", language="ja", country="jp")
    _plant_claim("g1", "good", "m1")
    _plant_claim("m1", "meh", "m2", text="positioning")
    sf.bump_source_yield("good", leads=10, mechanisms=6, candidates=8, judged=4, survivors=2)
    sf.bump_source_yield("meh", leads=10, mechanisms=0, candidates=0, judged=4, survivors=0)
    rows = sf.assign(3, "exploitation", cells=sf.build_cells())
    assert rows and rows[0]["mode"] == "exploitation"
    assert rows[0]["cell"].startswith("zh|cn|forum")
    assert "good P(testable)" in rows[0]["why"]


def test_cold_mode_returns_only_cells_that_never_yielded_and_the_mix_keeps_its_floor(frontier):
    _plant_source("busy", kind="forum", language="zh", country="cn")
    _plant_claim("c1", "busy", "m1")
    for i in range(4):
        _plant_source(f"silent{i}", kind="community", language="ko", country=f"k{i}")
    cells = sf.build_cells()
    cold = sf.assign(4, "cold", cells=cells)
    assert cold and all(r["mode"] == "cold" for r in cold)
    by_key = {c["cell"]: c for c in cells}
    assert all(by_key[r["cell"]]["cold"] for r in cold)
    assert all("never bid away" in r["why"] for r in cold)
    rows = sf.suggest(10, cells)
    share = sum(1 for r in rows if r["mode"] == "cold") / max(1, len(rows))
    assert share >= sf.COLD_FLOOR


def test_a_policy_that_zeroes_cold_is_raised_back_to_the_constitutional_floor(
        frontier, monkeypatch):
    import research_os_archive as roa
    monkeypatch.setattr(roa, "active_policy", lambda: {
        "miner": {"search_mix": {"exploration": 0.40, "exploitation": 0.60, "cold": 0.0}}})
    mix = sf.search_mix()
    assert mix["cold"] >= sf.COLD_FLOOR
    assert sum(mix.values()) == pytest.approx(1.0, abs=1e-6)


# ------------------------------------------------------------------------------ the ROI posterior

def test_roi_posteriors_are_jeffreys_and_marginal_growth_is_unmeasured_until_a_yield_carries_it(
        frontier):
    sf.bump_source_yield("s1", leads=10, mechanisms=2, candidates=4, judged=4, survivors=1,
                         independent_survivors=0)
    roi = sf.source_roi("s1")
    assert roi["p_novel"]["p"] == pytest.approx((2 + 0.5) / (10 + 1), abs=1e-6)
    assert roi["p_testable"]["p"] == pytest.approx((4 + 0.5) / (10 + 1), abs=1e-6)
    assert roi["p_survivor"]["p"] == pytest.approx((1 + 0.5) / (4 + 1), abs=1e-6)
    assert roi["p_independent_survivor"]["p"] == pytest.approx(0.5 / 5, abs=1e-6)
    assert roi["roi_score"] == pytest.approx(roi["p_novel"]["p"] * roi["p_testable"]["p"],
                                             abs=1e-6)
    assert roi["expected_marginal_log_growth"] == sf.UNMEASURED
    assert sf.UNMEASURED in roi["elogw_basis"]
    R.generator_yield_update("miner", survivors=3, delta_elogw=0.004)
    priced = sf.source_roi("s1")
    assert priced["expected_marginal_log_growth"] == pytest.approx(1 * 0.004)


def test_a_source_with_nothing_measured_is_prior_only_and_never_reads_as_evidence(frontier):
    roi = sf.source_roi("never_seen")
    assert roi["p_testable"] == {"p": 0.5, "k": 0.0, "n": 0.0, "prior_only": True}
    assert roi["measured"] is False
    allowed, why = sf.may_crawl("never_seen")
    assert allowed is False and sf.UNMEASURED in why


def test_the_crawl_gate_opens_only_on_measured_leads_above_the_threshold(frontier):
    sf.bump_source_yield("weak", leads=100, candidates=2)          # P(testable) ~ 0.025
    sf.bump_source_yield("strong", leads=100, candidates=40)       # P(testable) ~ 0.40
    weak_ok, weak_why = sf.may_crawl("weak")
    strong_ok, strong_why = sf.may_crawl("strong")
    assert weak_ok is False and "<=" in weak_why
    assert strong_ok is True and ">" in strong_why


# ----------------------------------------------------------------------------- the durable map

def test_frontier_map_rows_upsert_rather_than_multiply(frontier):
    _plant_source("s1", kind="forum", language="zh", country="cn")
    _plant_claim("c1", "s1", "m1")
    cells = sf.build_cells()
    assert sf.write_frontier_map(cells) == len(cells)
    sf.write_frontier_map(sf.build_cells())
    conn = R.connect()
    try:
        n = conn.execute("SELECT COUNT(*) FROM frontier_map").fetchone()[0]
        row = conn.execute("SELECT * FROM frontier_map WHERE cold=0").fetchone()
    finally:
        conn.close()
    assert n == len(cells)
    assert row["language"] == "zh" and row["country"] == "cn" and row["source_type"] == "forum"
    assert row["n_leads"] == 1


def test_mark_scouted_stamps_the_cell_the_swarm_worked(frontier):
    _plant_source("s1")
    _plant_claim("c1", "s1", "m1")
    cells = sf.build_cells()
    sf.write_frontier_map(cells)
    sf.mark_scouted(cells[0]["cell"], at="2026-09-17T00:00:00+00:00")
    conn = R.connect()
    try:
        got = conn.execute("SELECT last_scouted FROM frontier_map WHERE cell=?",
                           (cells[0]["cell"],)).fetchone()["last_scouted"]
    finally:
        conn.close()
    assert got == "2026-09-17T00:00:00+00:00"


def test_build_publishes_the_rule_the_cold_cells_and_what_it_could_not_measure(frontier):
    doc = sf.build(top=5)
    assert doc["rule"] == "scouts go where the unseen mass is, never to saturated English finance"
    assert doc["n_cells"] >= 1
    assert set(doc["search_mix"]) == {"exploration", "exploitation", "cold"}
    assert doc["unmeasured"]["claims_rows"] == 0
    assert sf.UNMEASURED in doc["unmeasured"]["claims_basis"]
    assert sf.UNMEASURED in doc["unmeasured"]["marginal_log_growth"]
    assert doc["n_cold_cells"] >= 1
    sf._atomic(sf.OUT, doc)
    assert json.loads(sf.OUT.read_text(encoding="utf-8"))["rule"] == doc["rule"]


def test_the_cli_writes_nothing_on_a_dry_run(frontier, capsys):
    assert sf.main(["--dry-run", "--top", "3"]) == 0
    assert not sf.OUT.exists()
    assert "DRY RUN" in capsys.readouterr().out
    assert sf.main(["--top", "3"]) == 0
    assert sf.OUT.exists()
