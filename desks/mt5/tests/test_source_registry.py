"""W1 source registry: provenance, result-based reputation, and an intelligence-ROI allocator.

Every fixture here is synthetic and every path is monkeypatched, so the suite never reads or writes
the desk's own grounds file, graph, credit report or registry.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

DESK = Path(__file__).resolve().parents[1]
for _p in (str(DESK.parents[1]), str(DESK), str(DESK / "research")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import source_registry as sr  # noqa: E402

GROUNDS_DOC = {
    "regions": {"cn": {"name": "China", "cluster": "cn", "languages": ["zh"]},
                "us": {"name": "United States", "cluster": "west", "languages": ["en"]}},
    "grounds": [
        {"name": "期货日报 实盘大赛", "region": "cn", "language": "zh", "route": "http",
         "kind": "competition", "weight": 1.5, "why": "competition records",
         "url": "https://example-qhrb.invalid/dasai/"},
        {"name": "知乎 quant", "region": "cn", "language": "zh", "route": "search",
         "kind": "qa", "weight": 0.9, "why": "403 direct", "site": "example-zhihu.invalid",
         "queries": ["黄金 日内"], "snippets_only": True},
        {"name": "CNKI paywalled", "region": "cn", "language": "zh", "route": "unreachable",
         "kind": "academic", "weight": 0.0, "why": "paywalled; recorded so the gap is visible",
         "site": "example-cnki.invalid"},
        {"name": "FRED releases", "region": "us", "language": "en", "route": "http",
         "kind": "dataset", "weight": 1.0, "why": "official series",
         "url": "https://example-fred.invalid/", "dataset_class": "macro_vintages"},
    ],
}


def _write(path: Path, doc) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(doc, ensure_ascii=False), encoding="utf-8")


def _jsonl(path: Path, rows) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows),
                    encoding="utf-8")


@pytest.fixture
def desk(tmp_path, monkeypatch):
    """A whole synthetic desk: grounds, seats, provenance, graph, docket, gates, credit, novelty."""
    d = tmp_path
    _write(d / "deep_forest_sources.json", GROUNDS_DOC)
    seats = d / "intelligence"
    for name in ("kimi", "forexfactory", "github"):
        (seats / name).mkdir(parents=True)
        (seats / name / "discoveries_1.json").write_text("[]", encoding="utf-8")

    # A PRESTIGIOUS, ZERO-YIELD source and an ANONYMOUS, HIGH-YIELD one.
    _jsonl(d / "mined_sources.jsonl",
           [{"at": "2026-09-01T00:00:00+00:00", "repo": "FRED releases", "url": "u"}] * 40
           + [{"at": "2026-09-02T00:00:00+00:00", "repo": "期货日报 实盘大赛", "url": "u"}] * 30)
    graph = ([{"id": f"f{i}", "source": "ground:us:fred_releases", "fate": "FAILED",
               "at": "2026-09-03T00:00:00+00:00"} for i in range(60)]
             + [{"id": f"c{i}", "source": "期货日报 实盘大赛", "fate": "CERTIFIED",
                 "at": "2026-09-03T00:00:00+00:00"} for i in range(4)]
             + [{"id": "x1", "source": "edge_search:XAUUSD", "fate": "BORN",
                 "at": "2026-09-03T00:00:00+00:00"}]
             + [{"id": "k1", "source": "miner:kimi", "fate": "BORN",
                 "at": "2026-09-03T00:00:00+00:00"}])
    _jsonl(d / "hypothesis_graph.jsonl", graph)
    _write(d / "external_survivors.json",
           [{"source": "期货日报 实盘大赛", "first_seen": "2026-09-02T00:00:00+00:00"}] * 20
           + [{"source": "ground:us:fred_releases", "first_seen": "2026-09-02T00:00:00+00:00"}] * 2)
    _jsonl(d / "gate_verdict_ledger.jsonl",
           [{"cell": f"c{i}", "passed": i < 3} for i in range(100)])
    _write(d / "CREDIT_ASSIGNMENT.json",
           {"evidence_source": "forward",
            "by_scientist": [{"source": "期货日报 实盘大赛", "realised_r": 12.0,
                              "n_trades": 30, "n_certificates": 4}]})
    _write(d / "NOVELTY_GATE.json",
           {"at": "x", "by_source": {"期货日报 实盘大赛": {"novel": 24},
                                     "ground:us:fred_releases": {"novel": 1}}})

    monkeypatch.setattr(sr, "GROUNDS", d / "deep_forest_sources.json")
    monkeypatch.setattr(sr, "PROVENANCE", d / "mined_sources.jsonl")
    monkeypatch.setattr(sr, "GRAPH", d / "hypothesis_graph.jsonl")
    monkeypatch.setattr(sr, "DOCKET", d / "external_survivors.json")
    monkeypatch.setattr(sr, "GATES", d / "gate_verdict_ledger.jsonl")
    monkeypatch.setattr(sr, "CREDIT", d / "CREDIT_ASSIGNMENT.json")
    monkeypatch.setattr(sr, "NOVELTY", d / "NOVELTY_GATE.json")
    monkeypatch.setattr(sr, "UNSEEN", d / "UNSEEN_FRONTIER.json")
    # data/ and reports/ as on the desk: on Windows one directory would make these ONE file
    monkeypatch.setattr(sr, "REGISTRY", d / "data" / "source_registry.json")
    monkeypatch.setattr(sr, "REPORT", d / "reports" / "SOURCE_REGISTRY.json")
    monkeypatch.setattr(sr, "SEAT_ROOTS", (seats,))
    return d


CN_COMP = "ground:cn:期货日报_实盘大赛"


def _cn(rows):
    """The competition ground's row, found by its ground name rather than its slug (the slug keeps
    non-ASCII, and the test should not have to spell it)."""
    hit = [r for r in rows.values() if r.get("ground") == "期货日报 实盘大赛"]
    assert len(hit) == 1
    return hit[0]


def _fred(rows):
    return rows["ground:us:fred_releases"]


# ---------------------------------------------------------------- seeding and merging

def test_registry_is_seeded_from_grounds_seats_and_the_graph(desk):
    registry, report = sr.build()
    rows = registry["sources"]
    assert _cn(rows)["kind"] == "competition" and _cn(rows)["language"] == "zh"
    assert _fred(rows)["kind"] == "official"
    assert _fred(rows)["fetch_clock"] == sr.CLOCK_DEEP_FOREST
    # the forest cluster rows exist beside the grounds they contain
    assert "src:deep_forest" in rows and "src:deep_forest_west" in rows
    # seats are registered from the intelligence directories, both name forms aliased
    assert rows["seat:kimi"]["kind"] == "seat"
    assert rows["seat:github"]["kind"] == "code"
    assert "miner:kimi" in rows["seat:kimi"]["aliases"]
    # a stamped source with no ground on file is registered UNKNOWN with a task to declare it
    unknown = rows["src:edge_search"]
    assert unknown["kind"] == "unknown" and unknown["cost"] is None
    assert "DECLARE THIS SOURCE" in unknown["task"]
    assert report["unmeasured"]["n_sources_without_a_ground"] >= 1


def test_graph_rows_reach_the_seat_they_were_stamped_for(desk):
    rows, _ = sr.build()
    assert rows["sources"]["seat:kimi"]["n_leads"] == 1     # "miner:kimi" -> seat:kimi


def test_counts_accumulate_across_runs_and_first_seen_is_kept(desk):
    first, _ = sr.build()
    sr._atomic(sr.REGISTRY, first)
    cn0 = _cn(first["sources"])
    assert cn0["n_runs"] == 1
    assert cn0["n_leads"] == 34                             # 30 provenance claims + 4 graph rows
    assert cn0["first_seen"].startswith("2026-09-02")

    # the append-only ledgers grow, and the earliest timestamp moves EARLIER in the graph
    with sr.PROVENANCE.open("a", encoding="utf-8") as fh:
        for _ in range(5):
            fh.write(json.dumps({"at": "2026-08-20T00:00:00+00:00",
                                 "repo": "期货日报 实盘大赛"}, ensure_ascii=False) + "\n")
    second, _ = sr.build()
    cn1 = _cn(second["sources"])
    assert cn1["n_leads"] == cn0["n_leads"] + 5
    assert cn1["n_runs"] == 2
    assert cn1["first_seen"] < cn0["first_seen"]            # earlier evidence is adopted
    assert cn1["last_seen"] >= cn0["last_seen"]


def test_a_truncated_ledger_never_revises_history_downwards(desk):
    first, _ = sr.build()
    sr._atomic(sr.REGISTRY, first)
    n0 = _cn(first["sources"])["n_leads"]
    sr.PROVENANCE.write_text("", encoding="utf-8")          # the ledger is rotated away
    second, _ = sr.build()
    cn = _cn(second["sources"])
    assert cn["n_leads"] == n0 and cn["first_seen"] is not None


# ---------------------------------------------------------------- reputation and ROI

def test_wilson_lower_bounds_are_conservative_and_carry_n():
    assert sr.wilson_lower(0, 0) == 0.0
    assert sr.wilson_lower(0, 50) == 0.0
    assert sr.wilson_lower(5, 10) < 0.5                     # always below the point estimate
    assert sr.wilson_lower(500, 1000) < 0.5
    assert sr.wilson_lower(5, 10) < sr.wilson_lower(500, 1000)   # more n -> tighter, higher LB
    assert sr._rep(None, 10) is None
    entry = sr._rep(3, 40)
    assert entry["n"] == 40 and entry["k"] == 3.0 and 0.0 < entry["p"] < 3 / 40


def test_reputation_entries_are_wilson_bounds_with_their_n(desk):
    registry, _ = sr.build()
    rep = _cn(registry["sources"])["reputation"]
    for key in ("p_novel", "p_testable", "p_survivor", "p_independent_survivor"):
        assert rep[key] is not None and rep[key]["n"] > 0
        assert 0.0 <= rep[key]["p"] <= 1.0
    cn = _cn(registry["sources"])
    assert rep["p_novel"]["p"] < cn["n_novel"] / cn["n_leads"]
    assert rep["dElogW_per_lead"] == pytest.approx(12.0 / cn["n_leads"], rel=1e-6)
    assert _fred(registry["sources"])["reputation"]["dElogW_per_lead"] is None


def test_a_high_yield_anonymous_source_outranks_a_prestigious_zero_yield_one(desk):
    registry, report = sr.build()
    rows = registry["sources"]
    cn, fred = _cn(rows), _fred(rows)
    # the official ground is cheaper per lead and has MORE leads; it has produced nothing
    assert fred["cost"] < cn["cost"] and fred["n_leads"] > cn["n_leads"]
    assert fred["n_certified"] == 0 and cn["n_certified"] == 4
    assert cn["intel_roi"] > fred["intel_roi"]
    assert cn["share"] > fred["share"]
    assert report["top_by_roi"][0]["source_id"] == cn["source_id"]
    assert "credibility and alpha yield are separate variables" in report["rule"]


def test_an_unmeasured_cost_is_never_zero_and_never_ranked(desk):
    registry, report = sr.build()
    rows = registry["sources"]
    unknown = rows["src:edge_search"]
    assert unknown["cost"] is None and unknown["intel_roi"] is None
    assert "Never read as 0" in unknown["cost_note"]
    assert report["unmeasured"]["n_sources_without_a_cost"] >= 1
    assert unknown["source_id"] not in {r["source_id"] for r in report["top_by_roi"]}
    # the price list is published so it can be argued with
    assert report["cost_table"]["per_lead_by_kind"]["unknown"] is None
    assert report["cost_table"]["per_lead_by_kind"]["forum"] > \
        report["cost_table"]["per_lead_by_kind"]["official"]


def test_an_unreachable_ground_is_recorded_and_never_funded(desk):
    registry, _ = sr.build()
    row = next(r for r in registry["sources"].values() if r["ground"] == "CNKI paywalled")
    assert row["cost"] is None and row["share"] == 0.0
    assert "NOT FETCHABLE" in row["licence_note"]


def test_snippet_only_and_licence_notes_are_carried(desk):
    registry, _ = sr.build()
    zhihu = next(r for r in registry["sources"].values() if r["ground"] == "知乎 quant")
    assert "SNIPPETS ONLY" in zhihu["licence_note"] and zhihu["url"].startswith("site:")
    assert zhihu["cost"] == pytest.approx(sr.COST_PER_LEAD["forum"] * sr.ROUTE_COST["search"])


# ---------------------------------------------------------------- shares

def test_the_exploration_floor_gives_thin_sources_a_share(desk):
    registry, report = sr.build()
    rows = registry["sources"]
    thin = [s for s, r in rows.items()
            if int(r["n_leads"] or 0) < sr.THIN_LEADS and r["route"] != "unreachable"]
    assert thin, "the fixture must contain thin sources for the floor to have work to do"
    for s in thin:
        assert rows[s]["share"] > 0.0, f"{s} was cut to zero -- L1.52 forbids it"
    assert sum(rows[s]["share"] for s in thin) >= sr.EXPLORATION_SHARE - 1e-6
    assert report["exploration_floor"] == sr.EXPLORATION_SHARE
    assert abs(sum(r["share"] for r in rows.values()) - 1.0) < 1e-6


def test_unseen_frontier_estimates_steer_the_exploration_pool(desk):
    baseline, _ = sr.build()
    fred0 = _fred(baseline["sources"])["share"]
    _write(sr.UNSEEN, {"by_source": {"ground:us:fred_releases": {"unseen_estimate": 90.0}}})
    after, report = sr.build()
    assert _fred(after["sources"])["unseen_estimate"] == 90.0
    assert _fred(after["sources"])["share"] > fred0
    assert report["unmeasured"]["unseen_frontier"] == "UNSEEN_FRONTIER.json"


def test_an_absent_unseen_frontier_is_unmeasured_not_zero(desk):
    assert not sr.UNSEEN.exists()
    _, report = sr.build()
    assert report["unmeasured"]["unseen_frontier"].startswith("UNMEASURED")


def test_novelty_without_a_per_source_block_is_unmeasured(desk):
    _write(sr.NOVELTY, {"at": "x", "n_screened": 5000, "by_dimension": {"feature": {}}})
    registry, report = sr.build()
    assert report["unmeasured"]["novelty_per_source"].startswith("UNMEASURED")
    cn = _cn(registry["sources"])
    assert cn["n_novel"] is None and cn["n_independent_certified"] is None
    assert "independence UNMEASURED" in cn["roi_basis"]
    assert cn["intel_roi"] is not None                      # falls back to certified, not to zero


# ---------------------------------------------------------------- language map

def test_language_gaps_are_listed_and_no_url_is_invented(desk):
    _, report = sr.build()
    assert report["language_gaps"] == [lang for lang in sr.NATIVE_LANGUAGES if lang != "zh"]
    assert "zh" in report["by_language"] and report["by_language"]["zh"] >= 3
    assert "invented" not in json.dumps(report["top_by_roi"])
    assert "no URL is ever invented" in report["language_gap_note"]


def test_a_language_with_a_ground_leaves_the_gap_list(desk, monkeypatch):
    doc = json.loads(json.dumps(GROUNDS_DOC, ensure_ascii=False))
    doc["regions"]["ru"] = {"name": "Russia", "cluster": "ru", "languages": ["ru"]}
    doc["grounds"].append({"name": "smart-lab", "region": "ru", "language": "ru", "route": "http",
                           "kind": "forum", "weight": 1.0, "why": "RU practitioner board",
                           "url": "https://example-smartlab.invalid/"})
    _write(sr.GROUNDS, doc)
    _, report = sr.build()
    assert "ru" not in report["language_gaps"] and "ja" in report["language_gaps"]


# ---------------------------------------------------------------- artifacts and CLI

def test_build_writes_both_artifacts_and_prints_eight_lines(desk, capsys):
    assert sr.main([]) == 0
    out = capsys.readouterr().out.strip().splitlines()
    assert len(out) == 8, out
    assert sr.REGISTRY.exists() and sr.REPORT.exists()
    report = json.loads(sr.REPORT.read_text(encoding="utf-8"))
    for key in ("at", "n_sources", "by_kind", "by_language", "language_gaps", "top_by_roi",
                "top_by_reputation", "shares", "exploration_floor", "unmeasured", "rule"):
        assert key in report, key
    registry = json.loads(sr.REGISTRY.read_text(encoding="utf-8"))
    assert registry["n_sources"] == report["n_sources"]
    row = _cn(registry["sources"])
    for key in ("source_id", "name", "kind", "language", "region", "licence_note", "url",
                "fetch_clock", "cost", "first_seen", "last_seen", "n_leads", "n_novel",
                "n_testable", "n_certified", "n_independent_certified", "realised_r",
                "reputation", "unseen_estimate", "intel_roi", "share"):
        assert key in row, key


def test_cli_dry_run_writes_nothing(desk, capsys):
    assert sr.main(["--dry-run"]) == 0
    out = capsys.readouterr().out
    assert "DRY RUN, wrote nothing" in out
    assert len(out.strip().splitlines()) == 8
    assert not sr.REGISTRY.exists() and not sr.REPORT.exists()


def test_the_gate_ledger_is_used_for_the_pooled_rate_and_its_missing_column_is_named(desk):
    _, report = sr.build()
    judged = report["judged"]
    assert judged["n_cells_judged"] == 100 and judged["n_passed"] == 3
    assert judged["pooled_pass_rate"] == pytest.approx(0.03)
    assert "carries no `source` column" in judged["why"]


def test_every_source_routes_to_a_bandit_arm(desk):
    registry, _ = sr.build()
    for row in registry["sources"].values():
        assert isinstance(row["arm"], str) and row["arm"]


# ---------------------------------------------------------------- the two bugs the desk data found

def test_non_ascii_ground_names_get_distinct_ids(desk):
    """An ASCII-only slug collapsed all 30 Chinese grounds onto `ground:cn:unnamed` and silently
    merged them. The registry's whole promise is that it never merges two sources."""
    doc = json.loads(json.dumps(GROUNDS_DOC, ensure_ascii=False))
    doc["grounds"].append({"name": "七禾网 期货人物专访", "region": "cn", "language": "zh",
                           "route": "http", "kind": "interview", "weight": 1.5,
                           "why": "long-form interviews", "url": "https://example-7hcn.invalid/"})
    _write(sr.GROUNDS, doc)
    registry, _ = sr.build()
    rows = registry["sources"]
    assert CN_COMP in rows and "ground:cn:七禾网_期货人物专访" in rows
    assert not [s for s in rows if s.endswith("unnamed")]
    assert sr._slug("期货日报 实盘大赛") == "期货日报_实盘大赛"
    assert sr._slug("---") != "unnamed"                     # a name with no word chars hashes


def test_a_thin_source_is_unmeasured_rather_than_ranked_on_price(desk):
    """A one-lead news ground outranked everything the desk owns, because the shrunk prior over a
    cheap kind is a PRICE. Below the lead floor the roi is UNMEASURED and the floor funds it."""
    doc = json.loads(json.dumps(GROUNDS_DOC, ensure_ascii=False))
    doc["grounds"].append({"name": "one hit wonder", "region": "us", "language": "en",
                           "route": "http", "kind": "column", "weight": 1.0, "why": "one page",
                           "url": "https://example-onehit.invalid/"})
    _write(sr.GROUNDS, doc)
    with sr.PROVENANCE.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps({"at": "2026-09-05T00:00:00+00:00", "repo": "one hit wonder"}) + "\n")
    registry, report = sr.build()
    thin = registry["sources"]["ground:us:one_hit_wonder"]
    assert thin["n_leads"] == 1 and thin["cost"] is not None
    assert thin["intel_roi"] is None and "price is not evidence" in thin["roi_basis"]
    assert thin["source_id"] not in {r["source_id"] for r in report["top_by_roi"]}
    assert thin["share"] > 0.0                              # funded by the floor, never cut to zero


def test_the_softmax_is_flat_until_something_has_survived(desk):
    """Evidence, not price, allocates: with nothing certified anywhere the ranking would be the
    declared price list, so the exploit pool is spread evenly and the report says which regime."""
    assert sr.build()[1]["roi_regime"] == "EVIDENCE"        # the fixture has 4 certified rows
    rows = [json.loads(line) for line in
            sr.GRAPH.read_text(encoding="utf-8").splitlines() if line.strip()]
    for r in rows:
        r["fate"] = "FAILED"
    _jsonl(sr.GRAPH, rows)
    flat, report2 = sr.build()
    assert report2["roi_regime"] == "PRIOR_AND_PRICE"
    measured = [r["share"] for r in flat["sources"].values() if r["intel_roi"] is not None]
    assert len(measured) >= 2 and max(measured) == pytest.approx(min(measured), rel=1e-6)


def test_no_rankable_less_source_is_ever_cut_to_zero(desk):
    """`src:external` -- the desk's largest producer -- had a share of 0.0 because its kind is
    undeclared: it could not enter the softmax and was not thin enough for the floor. A source that
    cannot be RANKED must be EXPLORED (L1.52), never silently defunded."""
    registry, _ = sr.build()
    rows = registry["sources"]
    for sid, r in rows.items():
        if r["route"] == "unreachable":
            continue
        assert r["share"] > 0.0, f"{sid} cut to zero with intel_roi={r['intel_roi']}"
    assert rows["src:edge_search"]["intel_roi"] is None and rows["src:edge_search"]["share"] > 0.0


def test_a_unique_first_token_aliases_the_ground_it_names(desk):
    """The provenance ledger stamps the short name ("七禾网") where the grounds file carries the
    long one. The prefix is aliased ONLY where it names exactly one ground."""
    doc = json.loads(json.dumps(GROUNDS_DOC, ensure_ascii=False))
    doc["grounds"].append({"name": "七禾网 期货人物专访", "region": "cn", "language": "zh",
                           "route": "http", "kind": "interview", "weight": 1.5,
                           "why": "interviews", "url": "https://example-7hcn.invalid/"})
    doc["grounds"] += [{"name": f"PTT {board}", "region": "cn", "language": "zh", "route": "http",
                        "kind": "forum", "weight": 1.0, "why": "an ambiguous prefix",
                        "url": f"https://example-ptt.invalid/{board}"}
                       for board in ("Stock", "Option")]
    _write(sr.GROUNDS, doc)
    with sr.PROVENANCE.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps({"at": "2026-09-06T00:00:00+00:00", "repo": "七禾网"},
                            ensure_ascii=False) + "\n")
    rows = sr.build()[0]["sources"]
    assert rows["ground:cn:七禾网_期货人物专访"]["n_leads"] == 1     # the short name resolved
    assert "PTT" not in rows["ground:cn:ptt_stock"]["aliases"]     # the ambiguous prefix refused
    assert "PTT" not in rows["ground:cn:ptt_option"]["aliases"]
