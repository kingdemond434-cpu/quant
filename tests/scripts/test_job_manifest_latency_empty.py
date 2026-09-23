"""EMPTY payloads and research latency on the job manifest (Tier-1 E11, I5).

The registry gauged only ARTIFACT AGE, so execution_quality.json rewritten on time with zero
decisions read OK. Pinned: a row may carry an emptiness predicate and then reads EMPTY rather than
OK; EMPTY is counted and printed, never alarmed, and never outranks STALE / FROZEN / IDLE. And the
three research-latency rows are computed from the hypothesis graph's own timestamps, name what
they join, read UNMEASURED with the counts when no node has both ends, and never alarm.
"""
from __future__ import annotations

import importlib.util
import json
import os
import sys
import time
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "check_job_manifest.py"


@pytest.fixture()
def mod(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    spec = importlib.util.spec_from_file_location("check_job_manifest_latency_ut", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    monkeypatch.setattr(module, "STATE", tmp_path / "job_manifest.json")
    monkeypatch.setattr(module, "ALARM", tmp_path / "ALARM.txt")
    monkeypatch.setattr(module, "ROOT", tmp_path)
    monkeypatch.setattr(module, "GRAPH", tmp_path / "graph.jsonl")
    monkeypatch.setattr(module, "request_repair", lambda *a, **k: None)
    yield module
    sys.modules.pop(spec.name, None)


def _state(mod) -> dict:
    return json.loads(mod.STATE.read_text(encoding="utf-8"))


def _write(path: Path, doc, *, age_h: float = 0.0) -> None:
    path.write_text(json.dumps(doc), encoding="utf-8")
    if age_h:
        t = time.time() - age_h * 3600
        os.utime(path, (t, t))


# ------------------------------------------------------------------------------ predicates
def test_the_three_predicates_read_their_producers_payloads(mod) -> None:
    assert mod._empty_execution_quality({"decisions": 0}) == \
        "decisions=0: no shadow decision to measure execution on"
    assert "filled=0 of 7" in mod._empty_execution_quality({"decisions": 7, "filled": 0})
    assert mod._empty_execution_quality({"decisions": 7, "filled": 3}) is None
    assert mod._empty_decay_live({"roster_state": "UNMEASURED", "roster_why": "no roster"}) \
        == "roster_state=UNMEASURED: no roster"
    assert "live_sleeves=0" in mod._empty_decay_live({"roster_state": "READ", "live_sleeves": 0})
    assert mod._empty_decay_live({"roster_state": "READ", "live_sleeves": 3}) is None
    assert mod._empty_counterfactual({"status": "UNMEASURED", "why": "no bars"}) == \
        "status=UNMEASURED: no bars"
    assert "rows_priced=0" in mod._empty_counterfactual({"status": "UNCHANGED",
                                                        "dataset": {"rows_priced": 0}})
    assert mod._empty_counterfactual({"status": "MEASURED",
                                      "dataset": {"rows_priced": 12}}) is None
    assert mod._empty_execution_quality("not json") is None


def test_the_real_registry_carries_the_predicates_on_the_three_artifacts(mod) -> None:
    rows = {rel: mod._job_row(v) for rel, v in mod.JOBS.items()}
    assert rows["desks/mt5/reports/execution_quality.json"][2] is mod._empty_execution_quality
    assert rows["desks/mt5/data/decay_live.json"][2] is mod._empty_decay_live
    assert rows["desks/mt5/reports/COUNTERFACTUAL_WORLD.json"][2] is mod._empty_counterfactual
    assert rows["web/desk_state.json"][2] is None                  # a two-element row still works
    assert rows["web/desk_state.json"][:2] == (0.5, "dashboard (Dell/phone)")


# ------------------------------------------------------------------------------ EMPTY verdict
def test_an_on_time_artifact_with_nothing_in_it_reads_empty_not_ok(mod, monkeypatch) -> None:
    monkeypatch.setattr(mod, "JOBS", {"eq.json": (36.0, "promoter", mod._empty_execution_quality),
                                      "ok.json": (36.0, "someone")})
    _write(mod.ROOT / "eq.json", {"decisions": 0, "filled": 0})
    _write(mod.ROOT / "ok.json", {"a": 1})
    rc = mod.main()
    st = _state(mod)
    assert st["jobs"]["eq.json"]["status"] == "EMPTY"
    assert st["jobs"]["ok.json"]["status"] == "OK"
    assert st["summary"] == {"EMPTY": 1, "OK": 1}
    assert rc == 0 and not mod.ALARM.exists(), "EMPTY is counted, never alarmed"
    assert st["jobs"]["eq.json"].get("last_valid_at") is None, "empty payload is not valid output"
    # the same artifact with a measured payload reads OK again
    _write(mod.ROOT / "eq.json", {"decisions": 9, "filled": 4})
    mod.main()
    assert _state(mod)["jobs"]["eq.json"]["status"] == "OK"


def test_empty_never_outranks_stale_or_frozen(mod, monkeypatch) -> None:
    monkeypatch.setattr(mod, "JOBS", {"eq.json": (1.0, "promoter", mod._empty_execution_quality)})
    _write(mod.ROOT / "eq.json", {"decisions": 0}, age_h=5.0)
    assert mod.main() == 1
    assert _state(mod)["jobs"]["eq.json"]["status"] == "STALE"
    assert "STALE eq.json" in mod.ALARM.read_text("utf-8")
    # fresh but byte-identical for longer than its window: FROZEN, and still alarmed
    _write(mod.ROOT / "eq.json", {"decisions": 0})
    st = _state(mod)
    st["jobs"]["eq.json"].update(hash=mod._hash(mod.ROOT / "eq.json"), hash_runs=50)
    mod.STATE.write_text(json.dumps(st), "utf-8")
    assert mod.main() == 1
    assert _state(mod)["jobs"]["eq.json"]["status"] == "FROZEN"


# ------------------------------------------------------------------------------ latency
def _graph(path: Path, t0: datetime) -> None:
    def row(nid: str, fate: str, at: datetime) -> str:
        return json.dumps({"id": nid, "fate": fate, "at": at.isoformat(), "symbol": "X",
                           "family": "f", "params": {}})
    h = timedelta(hours=1)
    lines = [
        row("A", "BORN", t0), row("A", "FAILED", t0 + 2 * h),
        row("B", "BORN", t0), row("B", "JUDGED", t0 + 0.5 * h), row("B", "CERTIFIED", t0 + 30 * h),
        row("C", "FAILED", t0 - 24 * h), row("C", "BORN", t0),          # backfill: unordered
        row("D", "BORN", t0 - 100 * h),                                   # open, 100h old
        row("D", "BORN", t0),                                             # a later BORN: first wins
        json.dumps({"id": "E", "fate": "BORN", "at": "not a time"}),      # skipped, not fatal
        "",
    ]
    path.write_text("\n".join(lines) + "\n", "utf-8")


def test_latency_rows_join_born_to_the_first_later_row_of_each_kind(mod) -> None:
    t0 = datetime(2026, 9, 1, tzinfo=UTC)
    _graph(mod.GRAPH, t0)
    rows = mod.latency_rows(now=t0 + timedelta(hours=100))
    screen, verdict, cert = (rows["time_to_first_screen"], rows["time_to_gauntlet_verdict"],
                             rows["time_to_certificate"])
    assert screen["n"] == 2 and screen["p50_h"] == 1.25 and screen["max_h"] == 2.0
    assert screen["status"] == "SLOW" and screen["target_h"] == 1.0
    assert screen["unordered"] == 1 and screen["open"] == 1 and screen["oldest_open_h"] == 200.0
    assert screen["born_nodes"] == 4 and screen["graph_rows"] == 10
    assert verdict["n"] == 2 and verdict["max_h"] == 30.0 and verdict["status"] == "SLOW"
    assert "p90" in verdict["why"] and "24" in verdict["why"]
    assert cert["n"] == 1 and cert["p50_h"] == 30.0 and cert["status"] == "NO_TARGET"
    # A failed, C failed-then-reborn, D never judged: none has a CERTIFIED end, so all three are
    # open for this row (C is unordered only for the rows whose end set includes FAILED)
    assert cert["target_h"] is None and cert["open"] == 3 and cert["unordered"] == 0
    for r in rows.values():
        assert "BORN.at" in r["basis"] and r["consumer"]


def test_latency_is_unmeasured_with_the_counts_when_no_node_has_both_ends(mod) -> None:
    t0 = datetime(2026, 9, 1, tzinfo=UTC)
    mod.GRAPH.write_text(json.dumps({"id": "A", "fate": "BORN", "at": t0.isoformat()}) + "\n"
                         + json.dumps({"id": "B", "fate": "FAILED",
                                       "at": (t0 - timedelta(hours=3)).isoformat()}) + "\n"
                         + json.dumps({"id": "B", "fate": "BORN", "at": t0.isoformat()}) + "\n",
                         "utf-8")
    rows = mod.latency_rows(now=t0 + timedelta(hours=1))
    assert all(r["status"] == "UNMEASURED" and r["n"] == 0 for r in rows.values())
    assert rows["time_to_gauntlet_verdict"]["why"].endswith(
        "1 open, 1 unordered (verdict not later than BORN)")
    absent = mod.latency_rows(graph_path=mod.ROOT / "nope.jsonl")
    assert all(r["status"] == "UNMEASURED" and "absent" in r["why"] for r in absent.values())
    assert absent["time_to_first_screen"]["target_h"] == 1.0


def test_main_publishes_latency_and_a_slow_row_is_never_an_alarm(mod, monkeypatch, capsys):
    monkeypatch.setattr(mod, "JOBS", {"ok.json": (26.0, "someone")})
    _write(mod.ROOT / "ok.json", {"a": 1})
    _graph(mod.GRAPH, datetime(2026, 9, 1, tzinfo=UTC))
    assert mod.main() == 0 and not mod.ALARM.exists()
    lat = _state(mod)["research_latency"]
    assert set(lat) == {"time_to_first_screen", "time_to_gauntlet_verdict", "time_to_certificate"}
    assert lat["time_to_gauntlet_verdict"]["status"] == "SLOW"
    out = capsys.readouterr().out
    assert "LATENCY time_to_gauntlet_verdict: SLOW" in out
    assert "LATENCY time_to_certificate: NO_TARGET" in out
