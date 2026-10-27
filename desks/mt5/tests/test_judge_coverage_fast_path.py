"""The pass memo changes how often judge_coverage reads its inputs, never what it computes.

On the trading box the hourly leg timed out three times on 2026-10-20 against its 120 s budget:
one pass parsed the gate ledger five times, the gauntlet report seven times and the unrunnable
bank three times. These tests pin the fast path to the slow one. Each reader inside a pass memo
must return what it returns outside one, over the awkward inputs a real ledger holds. The
reworked variant split and the head-limited interleave must equal the orders they replaced. And
a pass killed by the cycle's timeout must leave the old report reading its own age, so the
fence's STALE_H lease is what marks it stale.
"""
from __future__ import annotations

import gc
import json
import random
import subprocess
import sys
import textwrap
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

DESK = Path(__file__).resolve().parents[1]
ROOT = DESK.parent.parent
for _p in (str(DESK), str(ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from research import judge_coverage as jc  # noqa: E402

sys.path.insert(0, str(ROOT / "scripts"))
import check_judge_coverage as fence  # noqa: E402

NOW = datetime(2026, 10, 20, 20, 0, tzinfo=UTC)


@pytest.fixture(autouse=True)
def _desk_state_in_tmp(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from libs.research import research_priors
    monkeypatch.setattr(jc, "UNRUNNABLE_BANK", tmp_path / "unrunnable_specs.json")
    monkeypatch.setattr(jc, "RATCHET", tmp_path / "judge_backlog_ratchet.json")
    monkeypatch.setattr(jc, "REPORT", tmp_path / "JUDGE_COVERAGE.json")
    monkeypatch.setattr(jc, "CONVERSION_HANDOFF", tmp_path / "conversion_handoff.json")
    monkeypatch.setattr(research_priors, "STATE_DIR", tmp_path / "research_priors")


def _awkward_ledger(path: Path, n: int = 23_000) -> None:
    """Every shape a real ledger line takes, and several it should never take."""
    rnd = random.Random(7)  # noqa: S311 -- a reproducible fixture, not a secret
    lines: list[str] = []
    for i in range(n):
        at = (NOW - timedelta(minutes=rnd.randrange(0, 60 * 24 * 9))).isoformat(
            timespec="seconds")
        k = i % 23
        if k == 0:
            lines.append("")                                       # blank line
        elif k == 1:
            lines.append("{not json")                              # malformed
        elif k == 2:
            lines.append("[1, 2]")                                 # not a dict
        elif k == 3:
            lines.append(json.dumps({"at": at, "cell": f"c{i}", "family": "f1",
                                     "passed": None, "terminal_gate": "",
                                     "downstream_status": "NOT_RUN_BUILD_FAILED"}))
        elif k == 4:
            lines.append(json.dumps({"at": "garbage", "cell": f"c{i}", "family": "f2",
                                     "passed": False, "terminal_gate": "cpcv"}))
        elif k == 5:
            lines.append(json.dumps({"cell": f"c{i}", "family": "f2", "passed": True,
                                     "terminal_gate": "PASSED"}))  # no stamp at all
        elif k == 6:
            lines.append(json.dumps({"at": at, "cell": f"c{i}", "family": "",
                                     "passed": False, "terminal_gate": "lockbox"}))
        elif k == 7:
            lines.append(json.dumps({"at": at, "cell": "", "family": "f3",
                                     "passed": "true", "terminal_gate": "UNKNOWN"}))
        elif k == 8:
            lines.append(json.dumps({"at": at + "Z" if "+" not in at else at,
                                     "cell": f"c{i}", "family": "f3", "passed": "true",
                                     "terminal_gate": "deflated_sharpe"}))
        else:
            gate = rnd.choice(["UNKNOWN", "UNKNOWN", "in_sample_screen", "deflated_sharpe",
                               "PASSED", ""])
            lines.append(json.dumps({"at": at, "cell": f"c{rnd.randrange(4000)}",
                                     "family": f"f{rnd.randrange(9)}",
                                     "passed": gate == "PASSED", "terminal_gate": gate,
                                     "downstream_status": "REJECTED", "sym": "EURUSD"}))
    # CRLF line ends, as the Windows box writes them, and no newline after the last row.
    path.write_bytes("\r\n".join(lines).encode("utf-8"))


def _readers(ledger: Path, state_dir: Path) -> dict[str, object]:
    out: dict[str, object] = {}
    out["judged_index"] = jc.judged_index(ledger, now=NOW)
    out["judged_index_6h"] = jc.judged_index(ledger, now=NOW, window_h=6.0)
    out["capacity"] = jc.measured_capacity({"f1": 48_000}, ledger, now=NOW)
    out["capacity_small"] = jc.measured_capacity({}, ledger, now=NOW)
    out["sustained"] = jc.sustained_rate(ledger, now=NOW)
    out["realised"] = jc.realised_pass_rates(ledger)
    out["learn"] = jc.learn_priors(ledger, since="", state_dir=state_dir)
    out["learn_small"] = jc.learn_priors(ledger, since="", limit=500, state_dir=state_dir)
    return out


def test_every_ledger_reader_agrees_inside_and_outside_a_pass(tmp_path: Path) -> None:
    ledger = tmp_path / "gate.jsonl"
    _awkward_ledger(ledger)
    plain = _readers(ledger, tmp_path / "priors_plain")
    with jc._pass_memo():
        fast = _readers(ledger, tmp_path / "priors_fast")
    # MERGE RESOLUTION (image companions onto speed train r2, 2026-10-22): the readers now answer
    # from judge-rate's incremental ledger index, held once per path across the pass (and across
    # passes, from its byte watermark), instead of one `_LedgerScan` per pass in the memo.
    idx = jc._LEDGER_INDEXES.get(str(ledger))
    assert idx is not None and idx.complete, "one index holds the ledger, caught up to EOF"
    assert fast == plain

    def _taught(d: Path) -> object:
        doc = json.loads((d / "beta.json").read_text("utf-8"))

        def strip(x: object) -> object:          # wall-clock stamps are not what was taught
            if isinstance(x, dict):
                return {k: strip(v) for k, v in x.items() if k not in ("last_at", "updated_at")}
            return x
        return strip(doc.get("dimensions"))
    assert _taught(tmp_path / "priors_fast") == _taught(tmp_path / "priors_plain")


def test_an_absent_ledger_takes_every_reader_s_own_unreadable_branch(tmp_path: Path) -> None:
    missing = tmp_path / "absent.jsonl"
    plain = _readers(missing, tmp_path / "p1")
    with jc._pass_memo():
        fast = _readers(missing, tmp_path / "p2")
    assert fast == plain
    assert plain["sustained"] == {"status": "UNMEASURED", "why": "gate ledger unreadable"}
    assert plain["learn"]["status"] == "UNMEASURED"


def test_the_pass_memo_never_outlives_its_pass_and_restores_the_collector(
        tmp_path: Path) -> None:
    ledger = tmp_path / "gate.jsonl"
    ledger.write_text(json.dumps({"at": NOW.isoformat(), "cell": "a", "family": "f",
                                  "passed": False, "terminal_gate": "cpcv"}) + "\n", "utf-8")
    assert gc.isenabled()
    with jc._pass_memo():
        assert not gc.isenabled()
        assert jc.judged_index(ledger, now=NOW)[1] == {"f": 1}
    assert jc._PASS is None and gc.isenabled()
    # A changed ledger is read afresh by the next pass, and by a reader outside any pass.
    with ledger.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps({"at": NOW.isoformat(), "cell": "b", "family": "f",
                             "passed": False, "terminal_gate": "cpcv"}) + "\n")
    assert jc.judged_index(ledger, now=NOW)[1] == {"f": 2}
    with jc._pass_memo():
        assert jc.judged_index(ledger, now=NOW)[1] == {"f": 2}


def _legacy_variant_split(rows: list[dict], unjudged_ids: set[str] | None = None) -> dict:
    """The variant split as it stood before 2026-10-21, kept here as the reference."""
    ids = unjudged_ids or set()

    def _fresh(row: dict) -> int:
        cid = str(row.get("_cell") or "")
        return 0 if (not ids or cid in ids) else 1

    order = sorted(range(len(rows)),
                   key=lambda i: (_fresh(rows[i]), str(rows[i].get("first_seen") or "9999"), i))
    seen: set[str] = set()
    grid_seen: set[str] = set()
    variants = 0
    for i in order:
        cell = jc.structural_cell(rows[i])
        is_variant = 1 if cell in seen else 0
        seen.add(cell)
        grid_seen.add(jc.grid_cell(rows[i]))
        rows[i]["_variant"] = is_variant
        variants += is_variant
    return {"rows": len(rows), "unseen_mechanisms": len(rows) - variants, "variants": variants,
            "distinct_grid_cells": len(grid_seen),
            "distinct_structural_cells": len(seen),
            "variant_share": round(variants / len(rows), 4) if rows else None,
            "collapse_raw_per_grid_cell": (round(len(rows) / len(grid_seen), 3)
                                           if grid_seen else None)}


def _random_rows(n: int, seed: int) -> list[dict]:
    rnd = random.Random(seed)  # noqa: S311 -- a reproducible fixture, not a secret
    out = []
    for _ in range(n):
        params: dict = {"rr": rnd.choice([1, 2, 3])}
        if rnd.random() < 0.5:
            params["timeframe"] = rnd.choice(["H1", "m15", " M5 ", "", None])
        if rnd.random() < 0.3:
            params["session"] = rnd.choice(["asia", "LONDON", "  ", 0])
        row = {"family": rnd.choice(["a", "b", "C ", "", None]),
               "symbol": rnd.choice(["EURUSD", "xauusd", "", None]),
               "params": params, "_cell": f"cell{rnd.randrange(n)}",
               "first_seen": rnd.choice(["2026-10-01T00:00:00+00:00",
                                         "2026-10-02T00:00:00+00:00", "", None,
                                         "2026-09-30T12:00:00+00:00"])}
        for k in ("regime", "direction", "side", "representation", "horizon", "timeframe"):
            if rnd.random() < 0.2:
                row[k] = rnd.choice(["long", "Short", "", 0, False, "trend"])
        out.append(row)
    return out


@pytest.mark.parametrize("seed", [1, 2, 3])
@pytest.mark.parametrize("with_ids", [True, False])
def test_the_variant_split_marks_exactly_what_the_legacy_split_marked(
        seed: int, with_ids: bool) -> None:
    a = _random_rows(3_000, seed)
    b = json.loads(json.dumps(a))
    ids = {f"cell{i}" for i in range(0, 3_000, 3)} if with_ids else None
    assert jc.variant_split(a, ids) == _legacy_variant_split(b, ids)
    assert [r["_variant"] for r in a] == [r["_variant"] for r in b]


@pytest.mark.parametrize("limit", [0, 1, 7, 150, 2_999, 3_000, 10_000])
def test_a_head_limited_interleave_is_the_prefix_of_the_full_one(limit: int) -> None:
    rows = _random_rows(3_000, 11)
    jc.variant_split(rows, None)
    quota = {"a": 40, "b": 3, "C ": 0, "": 900}
    full = jc.coverage_order(rows, quota, {f"cell{i}" for i in range(0, 3_000, 2)})
    head = jc.coverage_order(rows, quota, {f"cell{i}" for i in range(0, 3_000, 2)},
                             limit=limit)
    assert [id(r) for r in head] == [id(r) for r in full[:limit]]


def test_name_unknowns_is_one_table_per_report_version_in_a_pass(tmp_path: Path,
                                                                 monkeypatch) -> None:
    report = tmp_path / "gates.json"
    report.write_text(json.dumps({"verdicts": [
        {"cell": "S.f.p=1", "sym": "S", "family": "f", "unmeasured": True, "days": 0},
        {"cell": "S.f.p=2", "sym": "S", "family": "f", "unmeasured": True, "days": 4,
         "unknown_reason": "lockbox_consumed_history"},
        {"cell": "S.f.p=3", "sym": "S", "family": "f", "passed": None,
         "downstream_status": "NOT_RUN_DATA_MISSING", "why": "no M15 parquet"}]}), "utf-8")
    stats: list[tuple[str, str]] = []
    monkeypatch.setattr(jc, "_bar_bytes", lambda s, t="H1": stats.append((s, t)) or 10)
    plain = (jc.name_unknowns(report), jc.name_not_run(report), jc.unknown_breakdown(report))
    stats.clear()
    with jc._pass_memo():
        fast = (jc.name_unknowns(report), jc.name_not_run(report), jc.unknown_breakdown(report))
        first = jc.name_unknowns(report)
        first.clear()                                   # a caller's copy is its own
        assert jc.name_unknowns(report) == fast[0]
    assert fast == plain
    assert len(stats) == len(set(stats)), "each chart is measured once in a pass"


def test_a_timed_out_pass_leaves_the_report_reading_its_own_age(tmp_path: Path) -> None:
    """THE TIMEOUT IS HONEST. The cycle kills an overrunning leg (`subprocess.run(timeout=)`),
    so `main` never reaches `write`: the previous report and ratchet are left byte-for-byte as
    they were, still stamped with the hour they describe. Nothing restamps them, so the fence
    reads their real age, and past STALE_H the report is stale, never current."""
    rows = [{"symbol": f"S{i}", "family": "alpha", "params": {"rr": i},
             "first_seen": (NOW - timedelta(hours=3)).isoformat()} for i in range(30)]
    doc = jc.build(rows, ledger=tmp_path / "absent.jsonl", ratchet=tmp_path / "none.json",
                   now=NOW)
    report, ratchet = tmp_path / "JUDGE_COVERAGE.json", tmp_path / "judge_backlog_ratchet.json"
    jc.write(doc, report=report, ratchet=ratchet)
    before = (report.read_bytes(), ratchet.read_bytes())

    # A pass that overruns: `build` blocks, and the parent kills it at its timeout, as
    # hourly_cycle._producer_impl does.
    child = textwrap.dedent(f"""
        import sys, time
        from pathlib import Path
        sys.path[:0] = [{str(DESK)!r}, {str(ROOT)!r}]
        from research import judge_coverage as jc
        jc.REPORT = Path({str(report)!r})
        jc.RATCHET = Path({str(ratchet)!r})
        jc.build = lambda *a, **k: time.sleep(60)
        print("started", flush=True)
        jc.main(["--once", "--budget-s", "120"])
    """)
    with pytest.raises(subprocess.TimeoutExpired):
        subprocess.run([sys.executable, "-c", child], capture_output=True, text=True,
                       timeout=5, check=False)
    assert (report.read_bytes(), ratchet.read_bytes()) == before, (
        "a killed pass must not touch the report or the ratchet")
    assert json.loads(report.read_text("utf-8"))["at"] == NOW.isoformat(timespec="seconds")

    # Inside the lease the old report is judged on its own content; past it, it is STALE.
    inside = fence.judge(report, now=NOW + timedelta(hours=fence.STALE_H - 1))
    assert not any(c.get("metric") == "freshness" for c in inside["checks"])
    late = NOW + timedelta(hours=fence.STALE_H + 0.5)
    exported = fence.judge(report, now=late)
    assert exported["verdict"] == "UNMEASURED"
    assert any(c["metric"] == "freshness" and c["state"] == "WARN" for c in exported["checks"])
    live = fence.judge(report, now=late, require_state=True)
    assert any(c["metric"] == "freshness" and c["state"] == "FAIL" for c in live["checks"])
