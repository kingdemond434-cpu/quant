"""A reproduction (`external_gauntlet.py --only/--spec`) writes its own report and nothing else.

Desk health refused the yen-breakout reproduction on 2026-10-28 because `--only` still appended
the gate ledger, wrote the hypothesis graph, stamped SEEN_CELLS and rewrote BUILD_CURSOR: the
first two are what the trial charge is counted from, the last two steer the sweep's rotation.
These tests pin that a reproduction leaves every one of them byte-identical, that an exact
`--spec` is judged even when the docket no longer holds it, and that the full sweep still writes.
"""
import hashlib
import json
import sys
from pathlib import Path

import pytest

DESK = Path(__file__).resolve().parents[1]
for p in (DESK, DESK / "scripts", DESK / "research"):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

import external_gauntlet as eg  # noqa: E402

SPEC = {"symbol": "GBPJPY", "family": "session_range_breakout",
        "params": {"rr": 1.5, "wait_bars": 12}}


def _tree(root: Path) -> dict[str, str]:
    return {str(f.relative_to(root)): hashlib.sha256(f.read_bytes()).hexdigest()
            for f in sorted(root.rglob("*")) if f.is_file()}


@pytest.fixture
def sandbox(tmp_path, monkeypatch):
    base = tmp_path / "base"
    reports = base / "desks" / "mt5" / "reports"
    hyp = base / "desks" / "mt5" / "data" / "hypotheses"
    uni = base / "desks" / "mt5" / "data" / "universe"
    for d in (reports, hyp, uni):
        d.mkdir(parents=True)
    (uni / "universe.json").write_text("{}", encoding="utf-8")
    # the docket holds an unrelated cell only: the spec under test is NOT in it
    (hyp / "external_survivors.json").write_text(json.dumps(
        [{"symbol": "EURUSD", "family": "carry", "params": {}}]), encoding="utf-8")
    ledger, index = hyp / "gate_verdict_ledger.jsonl", hyp / "gate_verdict_index.json"
    seen, cursor = hyp / "gauntlet_seen_cells.json", hyp / "gauntlet_build_cursor.json"
    ledger.write_text('{"cell": "old"}\n', encoding="utf-8")
    index.write_text('{"old": 1}', encoding="utf-8")
    seen.write_text('{"old": "2026-10-01T00:00:00+00:00"}', encoding="utf-8")
    cursor.write_text('{"EURUSD": "2026-10-01T00:00:00+00:00"}', encoding="utf-8")
    for name, value in (("BASE", base), ("REPORTS", reports), ("HYP", hyp), ("UNI", uni),
                        ("CACHE_DIR", reports / "gauntlet_cache"), ("GATE_LEDGER", ledger),
                        ("GATE_INDEX", index), ("SEEN_CELLS", seen), ("BUILD_CURSOR", cursor),
                        ("PRE_FILTER_LEDGER", base / "data" / "pre_filter_ledger.jsonl"),
                        ("PRIORITY_REMINT", hyp / "priority_remint.json"), ("WORKERS", 1),
                        ("_SHARD", None)):
        monkeypatch.setattr(eg, name, value)
    judged: list[list[str]] = []

    def fake_build(specs, meta, t0, stage0, stage0_verdicts, built_syms, blocked):
        built_syms |= {sp["sym"] for sp in specs}
        return {"cell_objs": [dict(sp) for sp in specs], "deferred": [], "cache_hits": 0,
                "built_fresh": len(specs), "mem_deferred": 0}

    def fake_gauntlet(cells, hunt, meta):
        judged.append([f"{c['sym']}.{c['family']}" for c in cells])
        return {"hunt": hunt, "cells_evaluated": len(cells), "n_trials": 109, "gate_fails": {},
                "verdicts": [{"cell": eg.cell_id({"sym": c["sym"], "family": c["family"],
                                                  "params": c["params"]}),
                              "sym": c["sym"], "family": c["family"], "passed": False,
                              "terminal_gate": "deflated_sharpe", "stages": {}}
                             for c in cells]}

    monkeypatch.setattr(eg, "judge_refusal", lambda verb, target: None)
    monkeypatch.setattr(eg, "partition_at_economic_prior", lambda specs, meta: (specs, []))
    monkeypatch.setattr(eg, "modifier_preflight", lambda spec: None)
    monkeypatch.setattr(eg, "_build_specs", fake_build)
    monkeypatch.setattr(eg, "run_gauntlet", fake_gauntlet)
    monkeypatch.setattr(eg, "_stamped_but_unjudged", lambda: set())
    monkeypatch.setattr(eg, "remint_cells", lambda path=None: (set(), set()))
    return {"base": base, "judged": judged, "ledger": ledger, "index": index, "seen": seen,
            "cursor": cursor, "monkeypatch": monkeypatch}


def test_a_reproduction_writes_its_report_and_nothing_else(sandbox, tmp_path) -> None:
    mp = sandbox["monkeypatch"]

    def forbidden(*_a, **_k):
        raise AssertionError("a reproduction reached a shared writer")

    mp.setattr(eg, "record_gauntlet_verdicts", forbidden)
    mp.setattr(eg, "_ack_docket", forbidden)
    mp.setattr(eg, "_progress_watermark", forbidden)
    out = tmp_path / "out" / "repro.json"
    mp.setattr(eg, "_REPRO", {"only": None, "specs": [SPEC], "report_to": str(out)})
    before = _tree(sandbox["base"])
    eg.main()
    assert _tree(sandbox["base"]) == before          # ledger, index, graph, seen, cursor, reports
    assert sandbox["judged"] == [["GBPJPY.session_range_breakout"]]
    doc = json.loads(out.read_text(encoding="utf-8"))
    assert doc["result"]["preregistration"] == {"skipped": "reproduction"}
    assert doc["result"]["verdicts"][0]["sym"] == "GBPJPY"


def test_a_normal_sweep_still_writes_every_shared_record(sandbox) -> None:
    """The audit's mutation: a guard flipped to `if True:` would silently stop every sweep
    charging its trials. The same sandbox with no reproduction must move all four records."""
    mp = sandbox["monkeypatch"]
    calls: list[str] = []
    mp.setattr(eg, "record_gauntlet_verdicts", lambda *a, **k: calls.append("graph") or {})
    mp.setattr(eg, "_ack_docket", lambda path: calls.append("ack"))
    mp.setattr(eg, "_progress_watermark", lambda *a, **k: calls.append("watermark"))
    mp.setattr(eg, "_REPRO", None)
    before = {k: sandbox[k].read_bytes() for k in ("ledger", "index", "seen", "cursor")}
    eg.main()
    assert {k for k in before if sandbox[k].read_bytes() != before[k]} == set(before)
    assert "graph" in calls and "ack" in calls
    assert sandbox["judged"] == [["EURUSD.carry"]]


def test_the_docket_record_wins_over_a_spec_and_a_spec_only_cell_is_flagged(sandbox,
                                                                            tmp_path) -> None:
    """Gate 0 reads mechanism_status from the docket row: a spec must not soften it."""
    mp = sandbox["monkeypatch"]
    hyp = sandbox["ledger"].parent
    (hyp / "external_survivors.json").write_text(json.dumps(
        [{"symbol": "EURUSD", "family": "carry", "params": {}, "mechanism_status": "UNNAMED"}]),
        encoding="utf-8")
    seen_status: dict[str, object] = {}

    def gate0(specs, meta):
        seen_status.update({sp["sym"]: sp.get("mechanism_status") for sp in specs})
        return specs, []

    mp.setattr(eg, "partition_at_economic_prior", gate0)
    mp.setattr(eg, "record_gauntlet_verdicts", lambda *a, **k: {})
    out = tmp_path / "repro.json"
    mp.setattr(eg, "_REPRO", {"only": None, "report_to": str(out), "specs": [
        {"symbol": "EURUSD", "family": "carry", "params": {}, "mechanism_status": "NAMED"},
        SPEC]})
    eg.main()
    assert seen_status == {"EURUSD": "UNNAMED", "GBPJPY": None}
    doc = json.loads(out.read_text(encoding="utf-8"))
    assert sorted(doc["cell_source"].values()) == ["docket", "spec_only"]
    assert doc["program_level"]["pbo"].startswith("NOT_REPRODUCED")


def test_report_to_outside_reports_repro_is_refused(sandbox, monkeypatch) -> None:
    monkeypatch.setattr(eg, "REPRO_DIR", sandbox["base"] / "desks" / "mt5" / "reports" / "repro")
    target = sandbox["base"] / "desks" / "mt5" / "reports" / "UNIVERSAL_SURVIVORS.json"
    monkeypatch.setattr(sys, "argv", ["external_gauntlet.py", "--spec", json.dumps(SPEC),
                                      "--report-to", str(target)])
    monkeypatch.setattr(eg, "_REPRO", None)
    assert eg._cli_main() == 2
    assert eg._REPRO is None and not target.exists()


def test_a_guest_on_the_lane_leaves_its_admission_history_alone(tmp_path, monkeypatch) -> None:
    import job_lock as jl
    monkeypatch.setattr(jl, "LOCK_ROOT", tmp_path)
    with jl.exclusive_job("lane_x", need_mb=0) as ok:
        assert ok
    history = (tmp_path / "lane_x.peaks.json").read_bytes()
    with jl.exclusive_job("lane_x", need_mb=300, record=False) as ok:
        assert ok
    assert (tmp_path / "lane_x.peaks.json").read_bytes() == history


def test_the_writers_refuse_on_their_own_under_reproduction(sandbox) -> None:
    sandbox["monkeypatch"].setattr(eg, "_REPRO", {"only": "x", "specs": [], "report_to": ""})
    before = _tree(sandbox["base"])
    got = eg._append_gate_ledger(
        [{"cell": "new", "sym": "GBPJPY", "family": "f", "passed": False, "stages": {}}], [])
    eg._save_seen_cells({}, {"new"})
    eg._save_build_cursor({}, {"GBPJPY"})
    assert got.get("appended") == 0
    assert _tree(sandbox["base"]) == before


def test_the_full_sweep_still_writes_the_rotation_and_the_seen_stamp(sandbox) -> None:
    sandbox["monkeypatch"].setattr(eg, "_REPRO", None)
    eg._save_seen_cells({}, {"new"})
    eg._save_build_cursor({}, {"GBPJPY"})
    assert "new" in json.loads(sandbox["seen"].read_text(encoding="utf-8"))
    assert "GBPJPY" in json.loads(sandbox["cursor"].read_text(encoding="utf-8"))


def test_spec_rows_key_exactly_as_the_docket_does() -> None:
    cells = eg._repro_cells([SPEC, {"symbol": "X"}, "junk"])
    key = 'GBPJPY.session_range_breakout.{"rr": 1.5, "wait_bars": 12}'
    assert list(cells) == [key]
    assert cells[key]["params"] == {"rr": 1.5, "wait_bars": 12}
