"""FOREST ATTEMPTS: every registered ground attempted daily, or LOW_EV_RETIRED with its evidence.

Pins the four things the order asked for: per-ground attempt state (last attempt, last yield,
failure reason, the delta cursor), retirement only on measured evidence with a named reopen
condition, the scheduler's daily floor (overdue before recently attempted, retired last and never
dropped), and the fence that turns RED when never-attempted does not fall.
"""
from __future__ import annotations

import json
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

_DESK = Path(__file__).resolve().parents[1]
for _p in (str(_DESK), str(_DESK / "research"), str(_DESK.parent.parent)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from libs.research import hunt_frontier as hf  # noqa: E402
from research import deep_forest_miner as dfm  # noqa: E402
from research import forest_attempts as fa  # noqa: E402

NOW = datetime(2026, 9, 30, 12, 0, tzinfo=UTC)


def _iso(d: datetime) -> str:
    return d.isoformat(timespec="seconds")


def _g(name: str, region: str = "cn", lang: str = "zh") -> dict[str, Any]:
    return {"name": name, "region": region, "language": lang, "route": "http", "weight": 1.0,
            "kind": "story", "url": f"https://{name}.example"}


def _files(tmp: Path, grounds: list[dict[str, Any]], vectors: dict[str, Any],
           stats: dict[str, Any], stats_updated: str = "") -> dict[str, Path]:
    src, fr, st = tmp / "sources.json", tmp / "frontier.json", tmp / "stats.json"
    src.write_text(json.dumps({"grounds": grounds}), "utf-8")
    fr.write_text(json.dumps({"vectors": vectors}), "utf-8")
    st.write_text(json.dumps({"updated": stats_updated or _iso(NOW), "vectors": stats}), "utf-8")
    return {"sources": src, "frontier": fr, "stats": st}


def _dead_stats(attempts: int = 7, days: float = 8.0, last_ago_d: float = 1.0) -> dict[str, Any]:
    last = NOW - timedelta(days=last_ago_d)
    return {"attempts": attempts, "successes": 0, "rows": 0, "datasets": 0,
            "counted_since": _iso(last - timedelta(days=days)), "last_attempt": _iso(last),
            "last_status": "REACHED_NO_CLAIMS", "failure_reason": "", "empty_delta_streak": 7}


def test_counts_name_never_attempted_yielded_and_overdue(tmp_path):
    grounds = [_g("a"), _g("b"), _g("c")]
    vectors = {"a": {"outcome": "NAMED_ONLY", "attempts": 0},
               "b": {"outcome": "YIELDED", "attempts": 2, "findings": 3,
                     "last_attempt": _iso(NOW - timedelta(hours=2))},
               "c": {"outcome": "EMPTY", "attempts": 1,
                     "last_attempt": _iso(NOW - timedelta(days=3))}}
    doc = fa.build(now=NOW, **_files(tmp_path, grounds, vectors, {}))
    s = doc["summary"]
    assert (s["named"], s["never_attempted"], s["attempted_ever"]) == (3, 1, 2)
    assert s["yielded"] == 1 and s["retired"] == 0
    assert s["attempted_24h"] == 1
    assert s["overdue_24h"] == 2                      # a (never) and c (3 days ago)
    assert doc["grounds"]["a"]["failure_reason"].startswith("never attempted")


def test_a_ground_is_retired_only_on_evidence_and_says_how_it_reopens(tmp_path):
    grounds = [_g("dead"), _g("young"), _g("few")]
    stats = {"dead": _dead_stats(), "young": _dead_stats(days=2.0),
             "few": _dead_stats(attempts=3)}
    vectors = {n: {"outcome": "EMPTY", "attempts": stats[n]["attempts"],
                   "last_attempt": stats[n]["last_attempt"]} for n in stats}
    doc = fa.build(now=NOW, **_files(tmp_path, grounds, vectors, stats))
    rows = doc["grounds"]
    assert rows["dead"]["state"] == fa.LOW_EV_RETIRED
    ret = rows["dead"]["retirement"]
    assert ret["evidence"]["attempts"] == 7 and ret["evidence"]["claims"] == 0
    assert "sibling" in ret["reopen_condition"] and not ret["reopen_due"]
    assert rows["young"]["state"] != fa.LOW_EV_RETIRED   # too short a span
    assert rows["few"]["state"] != fa.LOW_EV_RETIRED     # too few attempts
    assert not rows["dead"]["overdue_24h"]               # retired: exempt from the daily floor


def test_retirement_reopens_after_the_reprobe_window_or_a_sibling_yield(tmp_path):
    grounds = [_g("old"), _g("dead"), _g("sib")]
    stats = {"old": _dead_stats(last_ago_d=31.0), "dead": _dead_stats(last_ago_d=2.0),
             "sib": {"attempts": 1, "successes": 1, "rows": 2, "datasets": 0,
                     "counted_since": _iso(NOW - timedelta(hours=1)),
                     "last_attempt": _iso(NOW - timedelta(hours=1)),
                     "last_success": _iso(NOW - timedelta(hours=1))}}
    vectors = {n: {"outcome": "EMPTY", "attempts": s["attempts"], "last_attempt": s["last_attempt"]}
               for n, s in stats.items()}
    paths = _files(tmp_path, grounds, vectors, stats)
    doc = fa.build(now=NOW, **paths)
    assert doc["grounds"]["old"]["retirement"]["reopen_due"]
    assert "re-probe" in doc["grounds"]["old"]["retirement"]["reopen_why"]
    assert doc["grounds"]["dead"]["retirement"]["reopen_due"]          # sib yielded after it
    assert fa.retired_names(grounds, frontier=paths["frontier"], stats=paths["stats"],
                            now=NOW) == set()


def _hist(tmp: Path, rows: list[tuple[float, int, int]]) -> list[dict[str, Any]]:
    return [{"at": _iso(NOW - timedelta(hours=h)),
             "summary": {"never_attempted": n, "overdue_24h": o}} for h, n, o in rows]


def test_the_fence_is_red_when_never_attempted_does_not_fall(tmp_path):
    doc = {"summary": {"never_attempted": 400, "overdue_24h": 400}}
    v = fa.judge(doc, _hist(tmp_path, [(24.0, 400, 400)]), NOW, stats_updated=_iso(NOW))
    assert v["status"] == "RED" and v["exit"] == 1
    assert any("NEVER-ATTEMPTED DID NOT FALL" in r for r in v["reasons"])


def test_the_fence_is_green_when_both_counts_fall_and_unmeasured_when_too_young(tmp_path):
    doc = {"summary": {"never_attempted": 100, "overdue_24h": 120}}
    v = fa.judge(doc, _hist(tmp_path, [(48.0, 450, 460), (24.0, 400, 400)]), NOW,
                 stats_updated=_iso(NOW))
    assert v["status"] == "GREEN" and v["exit"] == 0
    young = fa.judge(doc, _hist(tmp_path, [(2.0, 450, 460)]), NOW, stats_updated=_iso(NOW))
    assert young["status"] == "UNMEASURED" and young["exit"] == 0


def test_a_silent_miner_turns_the_fence_red(tmp_path):
    doc = {"summary": {"never_attempted": 10, "overdue_24h": 10}}
    v = fa.judge(doc, [], NOW, stats_updated=_iso(NOW - timedelta(hours=9)))
    assert v["status"] == "RED" and any("MINER SILENT" in r for r in v["reasons"])


def test_publish_appends_one_history_line_per_pass(tmp_path):
    paths = _files(tmp_path, [_g("a")], {"a": {"outcome": "NAMED_ONLY"}}, {})
    hp, out = tmp_path / "hist.jsonl", tmp_path / "FOREST_ATTEMPTS.json"
    fa.publish(out=out, history_path=hp, now=NOW, **paths)
    fa.publish(out=out, history_path=hp, now=NOW + timedelta(hours=1), **paths)
    lines = hp.read_text("utf-8").splitlines()
    assert len(lines) == 2 and json.loads(lines[-1])["summary"]["never_attempted"] == 1
    assert json.loads(out.read_text("utf-8"))["fence"]["status"] in ("UNMEASURED", "RED")


def test_an_absent_registry_is_unmeasured_never_zero(tmp_path):
    doc = fa.build(now=NOW, sources=tmp_path / "absent.json", frontier=tmp_path / "f.json",
                   stats=tmp_path / "s.json")
    assert doc["status"] == fa.UNMEASURED
    assert doc["summary"]["never_attempted"] == fa.UNMEASURED


def test_the_scheduler_holds_the_daily_floor_and_puts_retired_last(tmp_path):
    now = datetime.now(tz=UTC)
    state = hf.VectorState()
    for name, outcome, ago_h in (("fresh", "EMPTY", 1.0), ("stale", "EMPTY", 30.0),
                                 ("retired", "EMPTY", 48.0), ("blocked", "BLOCKED", 50.0)):
        state.upsert(hf.Vector(name=name, outcome=outcome, attempts=3,
                               last_attempt=_iso(now - timedelta(hours=ago_h))))
    grounds = [_g(n) for n in ("fresh", "retired", "stale", "blocked", "new")]
    order = [g["name"] for g in dfm.schedule(grounds, frontier_state=state,
                                             retired={"retired"})]
    assert order[0] == "new"                                  # NAMED_ONLY first
    assert order.index("stale") < order.index("fresh")        # overdue before attempted-today
    assert order.index("blocked") < order.index("fresh")      # a 2-day-old block is overdue
    assert order[-1] == "retired" and len(order) == 5         # retired last, never dropped


def test_the_vector_stats_carry_the_delta_cursor_and_standing_failure(tmp_path, monkeypatch):
    monkeypatch.setattr(dfm, "SEEN", tmp_path / "deep_forest_seen.json")
    monkeypatch.setattr(dfm, "LOCKS", tmp_path / "locks")
    base = {"ground": "g", "region": "cn", "language": "zh", "route": "http", "datasets": 0}
    dfm._record_vector_stats([{**base, "status": "REACHED_NO_CLAIMS", "claims": 0,
                               "delta": {"urls_new": 0, "claims_new": 0,
                                         "claims_seen_before": 2}}])
    dfm._record_vector_stats([{**base, "status": "BLOCKED", "claims": 0,
                               "errors": ["HTTP 403"],
                               "delta": {"urls_new": 0, "claims_new": 0,
                                         "claims_seen_before": 0}}])
    e = json.loads((tmp_path / dfm.VECTOR_STATS_NAME).read_text("utf-8"))["vectors"]["g"]
    assert e["empty_delta_streak"] == 2 and e["failure_reason"] == "HTTP 403"
    dfm._record_vector_stats([{**base, "status": "PRODUCTIVE", "claims": 2,
                               "delta": {"urls_new": 5, "claims_new": 2,
                                         "claims_seen_before": 0}}])
    e = json.loads((tmp_path / dfm.VECTOR_STATS_NAME).read_text("utf-8"))["vectors"]["g"]
    assert e["empty_delta_streak"] == 0 and e["last_new_content_at"]
    assert e["failure_reason"] == "" and e["last_error"] == "HTTP 403"   # history stays
    assert e["last_success"] and e["last_delta"]["urls_new"] == 5
