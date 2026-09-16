"""The semantic hop has to answer the two questions it exists for, on a corpus we control.

Every source here is SYNTHETIC and lives in tmp_path: the point is not that the index can be
built (it can, 11k documents in four seconds) but that the ranking is the one the desk would
act on -- the failed cell of the SAME mechanism before an unrelated one, the survivor that makes
a candidate redundant flagged STRUCTURALLY rather than by cosine alone, and an absent ledger
counted as UNMEASURED instead of silently reading as "nothing failed like this".

The round-trip test is the one that would catch the quiet defect: a vectoriser that used
Python's salted `hash()` would score identically inside one process and differently in the next,
so an index built by a scheduled leg would disagree with the same query asked here, and neither
run would look wrong.
"""
from __future__ import annotations

import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path

import numpy as np
import pytest

_DESK = Path(__file__).resolve().parents[1]
_ROOT = _DESK.parent.parent
for _p in (str(_DESK), str(_DESK / "research"), str(_ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import semantic_memory as sm  # noqa: E402

LESSONS = [
    {"id": "L0001", "learned": "2026-09-01", "source": "incident",
     "lesson": "A same-bar limit fill is lookahead, never an execution: the bar that produced "
               "the signal cannot also fill the order at its own extreme.",
     "evidence": "shadow_forward filled at the signal bar low for 40 trades", "tags": ["fills"]},
    {"id": "L0002", "learned": "2026-09-02", "source": "incident",
     "lesson": "The resolved heat is filled, never reported short; a floor that is not filled "
               "is a cap wearing a floor's name.",
     "evidence": "cap_by_heat stopped under the 20% floor", "tags": ["growth"]},
    {"id": "L0003", "learned": "2026-09-03", "source": "audit",
     "lesson": "Paginate every venue history endpoint; truncation never throws.",
     "evidence": "income endpoint serves 1000 rows per call", "tags": ["data"]},
]
HYPOTHESES = [
    {"id": "h1", "symbol": "XAUUSD", "family": "session_range_breakout", "fate": "FAILED",
     "params": {"window_bars": 8, "rr": 1.5}, "source": "external",
     "why": "the Asian session range breaks at the London open and the break continues",
     "gates": {"in_sample_screen": {"passed": True}, "deflated_sharpe": {"passed": False}}},
    # h2 shares "the London open" with the probe ON PURPOSE: an unrelated failure that scores
    # zero would prove only that the filter works. This one is reachable and must rank BELOW.
    {"id": "h2", "symbol": "EURUSD", "family": "carry", "fate": "FAILED",
     "params": {"lookback": 60}, "source": "external",
     "why": "the funded leg earns the rate differential held through the London open",
     "gates": {"pbo": {"passed": False}}},
    {"id": "h3", "symbol": "USDJPY", "family": "session_range_breakout", "fate": "BORN",
     "params": {"window_bars": 12}, "source": "miner",
     "why": "session range breakout, not yet judged", "gates": {}},
    {"id": "h4", "symbol": "CHFNOK", "family": "overnight_gap_decay", "fate": "CERTIFIED",
     "params": {"horizon": 1}, "source": "miner", "why": "the gap decays into the session",
     "gates": {}},
]
VERDICTS = [
    {"at": "2026-09-10T00:00:00+00:00", "cell": "XAUUSD.session_range_breakout.p=aa",
     "sym": "XAUUSD", "family": "session_range_breakout", "passed": False,
     "terminal_gate": "deflated_sharpe", "downstream_status": None},
    {"at": "2026-09-10T00:00:00+00:00", "cell": "EURUSD.carry.p=bb", "sym": "EURUSD",
     "family": "carry", "passed": False, "terminal_gate": "pbo", "downstream_status": None},
    {"at": "2026-09-10T00:00:00+00:00", "cell": "GBPUSD.carry.p=cc", "sym": "GBPUSD",
     "family": "carry", "passed": True, "terminal_gate": "expected_value",
     "downstream_status": "UNIVERSAL"},
]
SURVIVORS = {"n": 3, "note": "UNIVERSAL 10-GATE PASS ONLY.", "survivors": {
    "external.XAUUSD.session_range_breakout": {
        "hunt": "external_discoveries", "cell": "XAUUSD.session_range_breakout", "days": 2101,
        "status": "UNIVERSAL",
        "shadow_spec": {"symbol": "XAUUSD", "family": "session_range_breakout",
                        "selector": "asia", "condition": None}},
    "external.USDJPY.session_range_breakout": {
        "hunt": "external_discoveries", "cell": "USDJPY.session_range_breakout", "days": 2107,
        "status": "UNIVERSAL",
        "shadow_spec": {"symbol": "USDJPY", "family": "session_range_breakout",
                        "selector": "asia", "condition": None}},
    "qquant.GBPUSD.carry": {
        "hunt": "hunt16.json", "cell": "GBPUSD carry london", "days": 179, "status": "UNIVERSAL",
        "shadow_spec": {"symbol": "GBPUSD", "family": "carry", "selector": "london",
                        "condition": "NORMAL_DAY"}}}}
CLAIMS = {"claims_total": 2, "top_claims": [
    {"title": "gold breaks the Asian range and trends into London", "symbols": ["XAUUSD"],
     "mechanism_class": "breakout", "channel": "direct", "evidence_grade": "COMMUNITY_POST",
     "url": "https://example.invalid/a"},
    {"title": "雪球: 金价在亚洲时段窄幅波动", "symbols": ["XAUUSD"], "mechanism_class": "momentum",
     "channel": "direct", "evidence_grade": "COMMUNITY_POST", "url": "https://example.invalid/b"}]}
GENOME = {"n_sleeves": 2, "genome": {
    "external.XAUUSD.session_range_breakout": {
        "symbol": "XAUUSD", "asset_class": "Commodities", "family": "session_range_breakout",
        "mechanism": "breakout", "direction_bias": "with", "clock": "asia", "legs": ["USD"],
        "factor_roles": ["USD"], "source": "external_discoveries", "status": "PASS"},
    "qquant.GBPUSD.carry": {
        "symbol": "GBPUSD", "asset_class": "Forex", "family": "carry", "mechanism": "carry",
        "direction_bias": "neutral", "clock": "london", "legs": ["GBP", "USD"],
        "factor_roles": ["RATES"], "source": "qquant", "status": "PASS"}}}
LEDGER = [
    {"time": "2026-09-07T17:04:15+00:00", "sleeve": "gold_asia", "symbol": "XAUUSD",
     "r_multiple": 0.8, "pl_quote": 37.68},
    {"time": "2026-09-07T18:04:15+00:00", "sleeve": "gold_asia", "symbol": "XAUUSD",
     "r_multiple": -0.3, "pl_quote": -11.0},
    {"time": "2026-09-07T19:04:15+00:00", "sleeve": "gbpusd_carry_london", "symbol": "GBPUSD",
     "r_multiple": -0.5, "pl_quote": -12.5},
]
LLM_ROWS = [
    {"kind": "hypothesis", "family": "session_range_breakout", "symbols": ["XAUUSD"],
     "why": "the Asian range break persists through the London open", "source": "kimi"},
    {"type": "academic_paper", "title": "Overnight gap decay in currency futures",
     "summary": "gaps close within the session", "symbols": ["EURUSD"], "source": "arxiv"},
]
UNIVERSE = {"XAUUSD": {"asset_class": "Commodities"}, "EURUSD": {"asset_class": "Forex"},
            "GBPUSD": {"asset_class": "Forex"}, "USDJPY": {"asset_class": "Forex"},
            "CHFNOK": {"asset_class": "Forex Exotics"}}
EXPECTED = {"lesson": 3, "hypothesis": 4, "verdict": 3, "survivor": 3, "claim": 2,
            "llm_hypothesis": 2, "genome": 2, "commit": 2, "trade_outcome": 2}


def _jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows), "utf-8")


def _dump(path: Path, blob: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(blob, ensure_ascii=False), "utf-8")


def write_corpus(root: Path, kinds: set[str] | None = None) -> Path:
    """The whole synthetic corpus under `root`, or only `kinds` of it. Returns the desk root."""
    want = kinds or set(EXPECTED)
    desk = root / "desks" / "mt5"
    if "lesson" in want:
        _jsonl(root / "docs" / "desk_lessons.jsonl", LESSONS)
    if "hypothesis" in want:
        _jsonl(desk / "data" / "hypothesis_graph.jsonl", HYPOTHESES)
    if "verdict" in want:
        _jsonl(desk / "data" / "hypotheses" / "gate_verdict_ledger.jsonl", VERDICTS)
    if "survivor" in want:
        _dump(desk / "reports" / "UNIVERSAL_SURVIVORS.json", SURVIVORS)
    if "claim" in want:
        _dump(desk / "reports" / "DEEP_FOREST.json", CLAIMS)
    if "genome" in want:
        _dump(desk / "reports" / "ALPHA_GENOME.json", GENOME)
    if "trade_outcome" in want:
        _jsonl(desk / "data" / "live_ledger.jsonl", LEDGER)
    if "llm_hypothesis" in want:
        _dump(desk / "data" / "intelligence" / "kimi" / "discoveries_20260916_0001.json",
              LLM_ROWS)
    _dump(desk / "data" / "universe" / "universe.json", UNIVERSE)
    return desk


@pytest.fixture
def desk(tmp_path, monkeypatch):
    """A whole synthetic desk, with git stubbed so the counts are the corpus's and not the box's."""
    root = tmp_path / "quant"
    write_corpus(root)
    for var in ("QUANT_SEMANTIC_DESK", "QUANT_SEMANTIC_REPO", "QUANT_SEMANTIC_HOME"):
        monkeypatch.delenv(var, raising=False)
    monkeypatch.setattr(sm, "BASE", root / "desks" / "mt5")
    monkeypatch.setattr(sm, "ROOT", root)
    monkeypatch.setattr(sm, "_read_commits", lambda repo, limit: (
        [sm.Doc("commit:aaa1111", "commit", "Family lane: lay the bracket from the entry",
                {"sha": "aaa1111", "outcome": "COMMIT"}),
         sm.Doc("commit:bbb2222", "commit", "cap_by_heat: fill to the 20% floor",
                {"sha": "bbb2222", "outcome": "COMMIT"})], "READ"))
    return root


def test_build_counts_every_kind_and_writes_the_three_files(desk):
    man = sm.build(limit_per_kind=5000)
    assert man.by_kind == EXPECTED
    assert man.n_docs == sum(EXPECTED.values())
    assert man.absent == []
    out = sm.home()
    assert (out / "index.npz").is_file() and (out / "docs.jsonl").is_file()
    written = json.loads((out / "manifest.json").read_text("utf-8"))
    assert written["by_kind"] == EXPECTED and written["vocab_hash"] == man.vocab_hash
    assert datetime.fromisoformat(man.at).tzinfo is not None
    assert len((out / "docs.jsonl").read_text("utf-8").strip().splitlines()) == man.n_docs
    assert man.sources["lesson"]["status"] == "READ" and man.sources["lesson"]["n"] == 3


def test_query_reaches_the_same_bar_fill_lesson_from_other_words(desk):
    sm.build()
    hits = sm.Memory.load().query("fill lookahead", k=5)
    assert hits, "a lexical miss here is the whole reason this organ exists"
    assert hits[0].doc_id == "lesson:L0001"
    assert hits[0].kind == "lesson" and hits[0].score > 0.0


def test_query_honours_the_structured_filters(desk):
    sm.build()
    mem = sm.Memory.load()
    assert [h.kind for h in mem.query("session range breakout", k=20, kinds=("survivor",))] == [
        "survivor"] * 2
    for h in mem.query("carry", k=20, symbol="GBPUSD"):
        assert h.meta["symbol"] == "GBPUSD"
    for h in mem.query("breakout", k=20, family="session_range_breakout"):
        assert h.meta["family"] == "session_range_breakout"


def test_similar_failures_puts_the_same_mechanism_first_and_names_the_stage(desk):
    sm.build()
    hits = sm.Memory.load().similar_failures(
        {"symbol": "XAUUSD", "family": "session_range_breakout",
         "why": "the Asian session range breaks at the London open"}, k=10)
    ids = [h.doc_id for h in hits]
    assert "hypothesis:h1" in ids, "the failed cell of the same mechanism must be reachable"
    assert "hypothesis:h2" in ids, "the unrelated failure must be reachable, so rank decides"
    assert ids.index("hypothesis:h1") < ids.index("hypothesis:h2"), ids
    assert next(h for h in hits if h.doc_id == "hypothesis:h1").meta["stage"] == "deflated_sharpe"
    assert next(h for h in hits if h.kind == "verdict").meta["stage"]


def test_similar_failures_never_returns_a_pass(desk):
    sm.build()
    hits = sm.Memory.load().similar_failures("carry on a funded leg, session range breakout", k=20)
    assert hits
    assert {h.kind for h in hits} <= {"verdict", "hypothesis", "lesson"}
    for h in hits:
        assert h.doc_id != "hypothesis:h3", "a BORN hypothesis has not failed yet"
        assert h.doc_id != "hypothesis:h4", "a CERTIFIED hypothesis is not a failure"
        assert not (h.kind == "verdict" and h.meta["passed"]), h.doc_id


def test_redundant_with_flags_the_same_family_same_symbol_survivor(desk):
    sm.build()
    hits = sm.Memory.load().redundant_with(
        {"symbol": "XAUUSD", "family": "session_range_breakout", "asset_class": "Commodities"},
        k=5)
    assert {h.kind for h in hits} <= {"survivor", "trade_outcome"}
    top = hits[0]
    assert top.doc_id == "survivor:external.XAUUSD.session_range_breakout"
    assert top.structural is True and top.score > 0.0
    other = next(h for h in hits if h.doc_id == "survivor:external.USDJPY.session_range_breakout")
    assert other.structural is False, "same family, different symbol AND different asset class"


def test_redundant_with_flags_the_same_family_same_asset_class(desk):
    sm.build()
    # No asset_class on the candidate: it is resolved from the index's own symbol -> class map.
    hits = sm.Memory.load().redundant_with({"symbol": "EURUSD", "family": "carry"}, k=5)
    match = next(h for h in hits if h.doc_id == "survivor:qquant.GBPUSD.carry")
    assert match.structural is True, "carry on Forex is carry on Forex whatever the pair"


def test_absent_sources_are_counted_and_never_fatal(tmp_path, monkeypatch):
    root = tmp_path / "thin"
    write_corpus(root, kinds={"lesson", "survivor"})
    for var in ("QUANT_SEMANTIC_DESK", "QUANT_SEMANTIC_REPO", "QUANT_SEMANTIC_HOME"):
        monkeypatch.delenv(var, raising=False)
    monkeypatch.setattr(sm, "BASE", root / "desks" / "mt5")
    monkeypatch.setattr(sm, "ROOT", root)
    monkeypatch.setattr(sm, "_read_commits", lambda repo, limit: ([], "UNMEASURED: stubbed"))
    man = sm.build()
    assert man.by_kind == {"lesson": 3, "survivor": 3}
    assert set(man.absent) == {"hypothesis", "verdict", "claim", "llm_hypothesis", "genome",
                               "trade_outcome", "commit"}
    assert man.sources["hypothesis"]["status"] == "ABSENT"
    assert man.sources["commit"]["status"].startswith("UNMEASURED")
    assert sm.Memory.load().query("same bar fill lookahead", k=3)


def test_a_git_that_will_not_run_is_unmeasured_not_zero_commits(tmp_path, monkeypatch):
    def boom(*_args, **_kwargs):
        raise OSError("git is not on this box")

    monkeypatch.setattr(sm.subprocess, "run", boom)
    docs, status = sm._read_commits(tmp_path, 400)
    assert docs == [] and status.startswith("UNMEASURED")
    assert sm._read_commits(tmp_path / "not-a-repo", 400)[1].startswith("UNMEASURED") is True


def test_the_index_round_trips_to_identical_scores(desk):
    first = sm.build()
    a, b = sm.Memory.load(), sm.Memory.load()
    probe = "session range breakout on gold at the Asian open"
    assert np.array_equal(a.scores(probe), b.scores(probe))
    assert [d.doc_id for d in a.docs] == [d.doc_id for d in b.docs]
    kept = a.scores(probe)
    second = sm.build()                      # a rebuild is the same index, bucket for bucket
    assert second.vocab_hash == first.vocab_hash
    assert np.array_equal(sm.Memory.load().scores(probe), kept)
    assert [(h.doc_id, h.score) for h in a.query(probe, k=5)] == [
        (h.doc_id, h.score) for h in sm.Memory.load().query(probe, k=5)]


def test_unknown_combinations_names_pairs_with_zero_documents(desk):
    sm.build()
    pairs = sm.Memory.load().unknown_combinations("mechanism", "asset_class")
    assert ("carry", "Commodities") in pairs, "nothing in this corpus carries gold"
    assert ("breakout", "Commodities") not in pairs
    assert all(a and b for a, b in pairs)


def test_the_cli_builds_and_queries(desk, tmp_path, monkeypatch):
    home = tmp_path / "cli_home"
    env = {**dict(__import__("os").environ), "QUANT_SEMANTIC_DESK": str(desk / "desks" / "mt5"),
           "QUANT_SEMANTIC_REPO": str(desk), "QUANT_SEMANTIC_HOME": str(home),
           "PYTHONIOENCODING": "utf-8"}
    module = str(Path(sm.__file__))
    built = subprocess.run([sys.executable, module, "build", "--limit-per-kind", "50"],
                           capture_output=True, encoding="utf-8", env=env, timeout=300,
                           check=False)
    assert built.returncode == 0, built.stderr
    assert "SEMANTIC MEMORY" in built.stdout and (home / "index.npz").is_file()
    assert "lesson" in built.stdout
    asked = subprocess.run([sys.executable, module, "query", "fill lookahead", "--k", "3"],
                           capture_output=True, encoding="utf-8", env=env, timeout=300,
                           check=False)
    assert asked.returncode == 0, asked.stderr
    assert "lesson:L0001" in asked.stdout
    failed = subprocess.run([sys.executable, module, "failures", "session range breakout"],
                            capture_output=True, encoding="utf-8", env=env, timeout=300,
                            check=False)
    assert failed.returncode == 0, failed.stderr
    assert "stage=" in failed.stdout
