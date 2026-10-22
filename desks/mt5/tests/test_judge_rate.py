"""Judging rate, made measurable and cheaper to reach (2026-10-14).

Pins: the incremental gate-ledger index answers every reader EXACTLY as the full scans it replaced
(the reference implementations below are the pre-change code, verbatim through ast.unparse); the
--budget-s deadline is real and leaves work queued; the 150k/day judging-rate block and its fence;
the deterministic build-failure memo (cell x bars x build code, one canary per signature); the
resident judge's priority parity with the miners and its no-idle-gap backoff.
"""
# ruff: noqa: E501, S311  -- the reference readers are the pre-change code as ast.unparse emits it;
# the seeded generators build synthetic ledgers, nothing cryptographic.
from __future__ import annotations

import json
import math
import os
import random
import sys
import time
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest

DESK = Path(__file__).resolve().parents[1]
ROOT = DESK.parent.parent
for _p in (str(DESK), str(ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from research.gate_ledger_index import LedgerIndex  # noqa: E402
from research.judge_coverage import (  # noqa: E402
    CAPACITY_FLOOR,
    CAPACITY_LOOKBACK_H,
    GATE_LEDGER,
    NOT_JUDGED_PREFIX,
    WINDOW_H,
    _ts,
)

from research import judge_coverage as jc  # noqa: E402
from scripts import run_sharded_gauntlet as runner  # noqa: E402

sys.path.insert(0, str(ROOT / "scripts"))
import check_judge_coverage as fence  # noqa: E402

NOW = datetime(2026, 10, 14, 12, 0, tzinfo=UTC)
_ = (math, GATE_LEDGER)


@pytest.fixture(autouse=True)
def _desk_state_in_tmp(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from libs.research import research_priors
    monkeypatch.setattr(jc, "UNRUNNABLE_BANK", tmp_path / "unrunnable_specs.json")
    monkeypatch.setattr(jc, "RATCHET", tmp_path / "judge_backlog_ratchet.json")
    monkeypatch.setattr(jc, "REPORT", tmp_path / "JUDGE_COVERAGE.json")
    monkeypatch.setattr(jc, "CONVERSION_HANDOFF", tmp_path / "conversion_handoff.json")
    monkeypatch.setattr(jc, "GATES_REPORT", tmp_path / "universal_gates_external.json")
    monkeypatch.setattr(jc, "TAPE_DIR", tmp_path / "no_tape")
    monkeypatch.setattr(research_priors, "STATE_DIR", tmp_path / "research_priors")
    monkeypatch.setattr(runner, "RESIDENT_STATE", tmp_path / "JUDGE_RESIDENT.json")
    monkeypatch.setattr(runner, "RESIDENT_STOP", tmp_path / "RESIDENT_STOP")
    monkeypatch.setattr(runner, "SWEEP_PHASE", tmp_path / "JUDGE_SWEEP_PHASE.json")
    monkeypatch.delenv("QUANT_LAWGATE_SOURCE_VIEW", raising=False)


# ------------------------------------------------------------- the pre-change readers, verbatim
def _ref_judged_index(path: Path | None=None, *, now: datetime | None=None, window_h: float=WINDOW_H) -> tuple[set[str], dict[str, int], dict[str, int]]:
    seen: set[str] = set()
    total: dict[str, int] = {}
    in_window: dict[str, int] = {}
    cutoff = (now or datetime.now(tz=UTC)).timestamp() - window_h * 3600.0
    try:
        with (path or GATE_LEDGER).open('r', encoding='utf-8', errors='replace') as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    row = json.loads(line)
                except ValueError:
                    continue
                if not isinstance(row, dict):
                    continue
                if str(row.get('downstream_status') or '').startswith(NOT_JUDGED_PREFIX):
                    continue
                if row.get('passed') is not True and str(row.get('terminal_gate') or '') in ('', 'UNKNOWN'):
                    continue
                fam = str(row.get('family') or '')
                cell = str(row.get('cell') or '')
                if cell:
                    seen.add(cell)
                if not fam:
                    continue
                total[fam] = total.get(fam, 0) + 1
                at = _ts(row.get('at'))
                if at is not None and at.timestamp() >= cutoff:
                    in_window[fam] = in_window.get(fam, 0) + 1
    except OSError:
        pass
    return (seen, total, in_window)


def _ref_measured_capacity(judged_total: dict[str, int], ledger: Path | None=None, *, now: datetime | None=None) -> int:
    best = 0
    cutoff = (now or datetime.now(tz=UTC)).timestamp() - CAPACITY_LOOKBACK_H * 3600.0
    per_hour: dict[str, int] = {}
    try:
        with (ledger or GATE_LEDGER).open('r', encoding='utf-8', errors='replace') as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    row = json.loads(line)
                except ValueError:
                    continue
                if not isinstance(row, dict):
                    continue
                if str(row.get('downstream_status') or '').startswith(NOT_JUDGED_PREFIX):
                    continue
                if row.get('passed') is not True and str(row.get('terminal_gate') or '') in ('', 'UNKNOWN'):
                    continue
                at = _ts(row.get('at'))
                if at is None or at.timestamp() < cutoff:
                    continue
                key = at.strftime('%Y-%m-%dT%H')
                per_hour[key] = per_hour.get(key, 0) + 1
    except OSError:
        per_hour = {}
    if per_hour:
        best = max(per_hour.values())
    return max(best, CAPACITY_FLOOR, sum(judged_total.values()) // 24)


def _ref_sustained_rate(ledger: Path | None=None, *, now: datetime | None=None) -> dict[str, Any]:
    t = now or datetime.now(tz=UTC)
    cuts = {'24h': t.timestamp() - 24 * 3600.0, '7d': t.timestamp() - 168 * 3600.0}
    counts = {'24h': 0, '7d': 0}
    unknown = {'24h': 0, '7d': 0}
    try:
        with (ledger or GATE_LEDGER).open('r', encoding='utf-8', errors='replace') as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    row = json.loads(line)
                except ValueError:
                    continue
                if not isinstance(row, dict):
                    continue
                if str(row.get('downstream_status') or '').startswith(NOT_JUDGED_PREFIX):
                    continue
                at = _ts(row.get('at'))
                if at is None:
                    continue
                _unk = row.get('passed') is not True and str(row.get('terminal_gate') or '') in ('', 'UNKNOWN')
                for w, cut in cuts.items():
                    if at.timestamp() >= cut:
                        counts[w] += 1
                        unknown[w] += int(_unk)
    except OSError:
        return {'status': 'UNMEASURED', 'why': 'gate ledger unreadable'}
    return {'status': 'MEASURED', 'counts': counts, 'per_hour_24h': round(counts['24h'] / 24.0, 3), 'per_hour_7d': round(counts['7d'] / 168.0, 3), 'unknown_counts': unknown, 'unknown_share_24h': round(unknown['24h'] / counts['24h'], 6) if counts['24h'] else None, 'unknown_share_7d': round(unknown['7d'] / counts['7d'], 6) if counts['7d'] else None, 'named_per_hour_24h': round((counts['24h'] - unknown['24h']) / 24.0, 3)}


def _ref_realised_pass_rates(path: Path | None=None) -> dict[str, dict[str, float]]:
    judged: dict[str, int] = {}
    passed: dict[str, int] = {}
    try:
        with (path or GATE_LEDGER).open('r', encoding='utf-8', errors='replace') as fh:
            lines = fh.readlines()
    except OSError:
        return {}
    for line in lines:
        line = line.strip()
        if not line:
            continue
        try:
            row = json.loads(line)
        except ValueError:
            continue
        if not isinstance(row, dict):
            continue
        if str(row.get('downstream_status') or '').startswith(NOT_JUDGED_PREFIX):
            continue
        fam = str(row.get('family') or '')
        if not fam:
            continue
        ok = row.get('passed')
        gate = str(row.get('terminal_gate') or '')
        if ok is not True and gate in ('', 'UNKNOWN'):
            continue
        judged[fam] = judged.get(fam, 0) + 1
        if ok is True or str(ok).lower() == 'true':
            passed[fam] = passed.get(fam, 0) + 1
    out: dict[str, dict[str, float]] = {}
    for fam, n in judged.items():
        k = passed.get(fam, 0)
        a, b = (1.0 + k, 1.0 + (n - k))
        mean = a / (a + b)
        sd = math.sqrt(max(mean * (1.0 - mean) / (a + b + 1.0), 0.0))
        out[fam] = {'judged': float(n), 'passed': float(k), 'pass_rate': k / n if n else 0.0, 'mean': mean, 'hi': min(1.0, mean + 1.96 * sd)}
    return out


def _ref_fired_pairs(path: Path | None=None) -> set[tuple[str, str]]:
    out: set[tuple[str, str]] = set()
    try:
        with (path or GATE_LEDGER).open('r', encoding='utf-8', errors='replace') as fh:
            for line in fh:
                if '"UNKNOWN"' in line or not line.strip():
                    continue
                try:
                    row = json.loads(line)
                except ValueError:
                    continue
                if isinstance(row, dict) and row.get('terminal_gate'):
                    out.add((str(row.get('family') or ''), str(row.get('sym') or '')))
    except OSError:
        pass
    return out


# ------------------------------------------------------------------------ synthetic ledgers
def _random_rows(rng: random.Random, n: int, *, stamps: list[str]) -> list[str]:
    fams = ["alpha", "beta", "gamma", ""]
    gates = ["deflated_sharpe", "cpcv", "UNKNOWN", "", "expected_value", None]
    out: list[str] = []
    for i in range(n):
        roll = rng.random()
        if roll < 0.03:
            out.append("{not json")
            continue
        if roll < 0.05:
            out.append(json.dumps([1, 2]))
            continue
        if roll < 0.07:
            out.append("")
            continue
        row: dict[str, Any] = {"cell": rng.choice([f"S{i % 37}.alpha.p={i % 53}", ""]),
                               "family": rng.choice(fams), "sym": f"S{i % 11}",
                               "terminal_gate": rng.choice(gates),
                               "passed": rng.choice([True, False, "true", None, "True"]),
                               "downstream_status": rng.choice(
                                   [None, None, "NOT_RUN_BUILD_BUDGET_DEFERRED", "JUDGED"])}
        if rng.random() > 0.05:
            row["at"] = rng.choice(stamps)
        out.append(json.dumps(row))
    return out


def _stamps(rng: random.Random) -> list[str]:
    base = NOW - timedelta(hours=200)
    st = [(base + timedelta(minutes=rng.randint(0, 210 * 60))).isoformat(timespec="seconds")
          for _ in range(40)]
    return [*st, "2026-10-14T11:30:00Z", "garbage", "2026-10-14T11:59:59"]


def _assert_same(path: Path) -> None:
    for window in (1.0, 6.0):
        assert jc.judged_index(path, now=NOW, window_h=window) == \
            _ref_judged_index(path, now=NOW, window_h=window)
    total = _ref_judged_index(path, now=NOW)[1]
    assert jc.measured_capacity(total, path, now=NOW) == _ref_measured_capacity(total, path,
                                                                               now=NOW)
    assert jc.sustained_rate(path, now=NOW) == _ref_sustained_rate(path, now=NOW)
    assert jc.realised_pass_rates(path) == _ref_realised_pass_rates(path)
    assert jc.fired_pairs(path) == _ref_fired_pairs(path)


@pytest.mark.parametrize("seed", [1, 2, 3, 4])
def test_index_answers_every_reader_exactly_as_the_full_scan(tmp_path: Path, seed: int) -> None:
    rng = random.Random(seed)
    stamps = _stamps(rng)
    path = tmp_path / "ledger.jsonl"
    path.write_text("\n".join(_random_rows(rng, 400, stamps=stamps)) + "\n", "utf-8")
    _assert_same(path)
    # An append is folded incrementally and still agrees; a half-written tail waits.
    with path.open("a", encoding="utf-8") as fh:
        fh.write("\n".join(_random_rows(rng, 150, stamps=stamps)) + "\n")
        fh.write('{"at": "2026-10-14T11:00:00+00:00", "cell": "half')
    idx = jc.ledger_index(path)
    assert idx.behind_bytes > 0 and idx.complete           # a writer mid-line is not skipped work
    with path.open("a", encoding="utf-8") as fh:
        fh.write('", "family": "alpha", "terminal_gate": "cpcv"}\n')
    _assert_same(path)


def test_an_unterminated_final_row_is_still_counted(tmp_path: Path) -> None:
    path = tmp_path / "ledger.jsonl"
    rows = [json.dumps({"at": NOW.isoformat(), "cell": f"c{i}", "family": "f",
                        "terminal_gate": "cpcv", "passed": False}) for i in range(3)]
    path.write_text("\n".join(rows), "utf-8")
    _assert_same(path)
    assert len(jc.judged_index(path, now=NOW)[0]) == 3


def test_persisted_index_resumes_and_a_rewritten_ledger_is_reindexed(tmp_path: Path) -> None:
    rng = random.Random(9)
    stamps = _stamps(rng)
    path, state = tmp_path / "ledger.jsonl", tmp_path / "idx.pkl"
    path.write_text("\n".join(_random_rows(rng, 300, stamps=stamps)) + "\n", "utf-8")
    a = LedgerIndex.load(path, state)
    a.catch_up()
    a.save(state)
    with path.open("a", encoding="utf-8") as fh:
        fh.write("\n".join(_random_rows(rng, 50, stamps=stamps)) + "\n")
    b = LedgerIndex.load(path, state)
    assert b.offset == a.offset
    done = b.catch_up()
    assert not done["rebuilt"] and 0 < done["consumed_bytes"] < path.stat().st_size
    fresh = LedgerIndex(path)
    fresh.catch_up()
    assert (b.judged_cells, b.judged_total, b.passed_total, b.buckets, b.fired) == \
        (fresh.judged_cells, fresh.judged_total, fresh.passed_total, fresh.buckets, fresh.fired)
    b.save(state)
    # Rewritten under the watermark (same length, different bytes): re-indexed from zero.
    text = path.read_text("utf-8")
    path.write_text(text.replace('"cpcv"', '"CPCV"'), "utf-8")
    c = LedgerIndex.load(path, state)
    assert c.catch_up()["rebuilt"] or text.count('"cpcv"') == 0
    again = LedgerIndex(path)
    again.catch_up()
    assert c.judged_total == again.judged_total and c.fired == again.fired


def test_catch_up_honours_its_deadline_and_leaves_the_rest_queued(tmp_path: Path,
                                                                   monkeypatch) -> None:
    import research.gate_ledger_index as gli
    monkeypatch.setattr(gli, "CHUNK_BYTES", 512)
    path = tmp_path / "ledger.jsonl"
    path.write_text("".join(json.dumps({"at": NOW.isoformat(), "cell": f"c{i}", "family": "f",
                                        "terminal_gate": "cpcv"}) + "\n" for i in range(200)),
                    "utf-8")
    idx = LedgerIndex(path)
    ticks = iter(range(10_000))
    done = idx.catch_up(deadline=3.0, clock=lambda: float(next(ticks)))
    assert done["deadline_hit"] and not idx.complete and idx.behind_bytes > 0
    assert 0 < len(idx.judged_cells) < 200
    idx.catch_up()                                    # the next pass resumes at the watermark
    assert idx.complete and len(idx.judged_cells) == 200 and idx.behind_bytes == 0


@pytest.mark.parametrize("body", ["a\nb\nc\n", "a\r\nb\r\nc", "\n\nx\n\n", "only", "",
                                  "é\n" * 5000 + "tail"])
@pytest.mark.parametrize("limit", [1, 2, 3, 7, 20_000])
def test_tail_lines_is_readlines_tail(tmp_path: Path, body: str, limit: int) -> None:
    p = tmp_path / "f.txt"
    p.write_bytes(body.encode("utf-8"))
    with p.open("r", encoding="utf-8", errors="replace") as fh:
        want = fh.readlines()[-limit:]
    assert jc._tail_lines(p, limit) == want


# ----------------------------------------------------------------------------- judging rate
def _ledger(tmp: Path, rows: list[dict]) -> Path:
    p = tmp / "gate_verdict_ledger.jsonl"
    p.write_text("".join(json.dumps(r) + "\n" for r in rows), "utf-8")
    return p


def test_judging_rate_counts_named_verdicts_in_24h_with_an_hourly_series(tmp_path: Path) -> None:
    rows = ([{"at": (NOW - timedelta(hours=2)).isoformat(), "cell": f"a{i}", "family": "f",
              "terminal_gate": "cpcv", "passed": False} for i in range(30)]
            + [{"at": (NOW - timedelta(hours=2)).isoformat(), "cell": f"u{i}", "family": "f",
                "terminal_gate": "UNKNOWN", "passed": False} for i in range(7)]
            + [{"at": (NOW - timedelta(hours=30)).isoformat(), "cell": f"o{i}", "family": "f",
                "terminal_gate": "cpcv"} for i in range(5)]
            + [{"at": NOW.isoformat(), "cell": "n", "family": "f", "terminal_gate": "cpcv",
                "downstream_status": "NOT_RUN_BUILD_BUDGET_DEFERRED"}])
    jr = jc.judging_rate(_ledger(tmp_path, rows), now=NOW)
    assert jr["status"] == "MEASURED" and jr["verdicts_24h"] == 30 and jr["unknown_24h"] == 7
    assert jr["target_per_day"] == 150_000 and jr["meets_target"] is False
    assert jr["shortfall_per_day"] == 150_000 - 30
    assert len(jr["per_hour"]) == 24 and sum(h["verdicts"] for h in jr["per_hour"]) == 30
    assert jr["per_hour"][-1]["hour"] == "2026-10-14T12"


def test_judging_rate_without_a_ledger_is_unmeasured(tmp_path: Path) -> None:
    jr = jc.judging_rate(tmp_path / "absent.jsonl", now=NOW)
    assert jr["status"] == "UNMEASURED" and "verdicts_24h" not in jr


def test_the_fence_and_the_organ_share_one_target() -> None:
    assert fence.JUDGING_RATE_TARGET_PER_DAY == jc.JUDGING_RATE_TARGET_PER_DAY == 150_000


def _doc(jr: dict | None) -> dict:
    d: dict[str, Any] = {"at": NOW.isoformat(), "families": {"f": {"mined": 0}}}
    if jr is not None:
        d["judging_rate"] = jr
    return d


def test_fence_fails_below_target_on_the_box_and_warns_in_a_source_view(monkeypatch) -> None:
    low = {"status": "MEASURED", "verdicts_24h": 12_000, "target_per_day": 150_000}
    assert fence.judging_rate(_doc(low), require_state=True, armed=True)["state"] == "FAIL"
    monkeypatch.setenv("QUANT_LAWGATE_SOURCE_VIEW", "1")
    out = fence.judging_rate(_doc(low), require_state=False, armed=fence._armed(False))
    assert out["state"] == "WARN" and out["shortfall_per_day"] == 138_000
    ok = {"status": "MEASURED", "verdicts_24h": 150_000}
    assert fence.judging_rate(_doc(ok), require_state=True, armed=True)["state"] == "OK"


def test_fence_missing_rate_is_unmeasured_and_fails_under_require_state() -> None:
    for jr in (None, {"status": "UNMEASURED", "why": "ledger absent"},
               {"status": "PARTIAL", "verdicts_24h": 10}):
        assert fence.judging_rate(_doc(jr), require_state=True, armed=True)["state"] == "FAIL"
        assert fence.judging_rate(_doc(jr), require_state=False,
                                  armed=False)["state"] == "UNMEASURED"
    # A partial count already over the floor is a pass: a lower bound cannot hide a shortfall.
    part = {"status": "PARTIAL", "verdicts_24h": 160_000}
    assert fence.judging_rate(_doc(part), require_state=True, armed=True)["state"] == "OK"


def test_fence_cannot_be_satisfied_by_a_lowered_published_target() -> None:
    cheat = {"status": "MEASURED", "verdicts_24h": 20_000, "target_per_day": 10_000}
    assert fence.judging_rate(_doc(cheat), require_state=True, armed=True)["state"] == "FAIL"


def test_judge_wires_the_rate_check_into_the_verdict(tmp_path: Path) -> None:
    rep = tmp_path / "JUDGE_COVERAGE.json"
    rep.write_text(json.dumps(_doc({"status": "MEASURED", "verdicts_24h": 5})), "utf-8")
    out = fence.judge(rep, require_state=True, now=NOW)
    assert any(c["metric"] == "judging_rate" and c["state"] == "FAIL" for c in out["checks"])
    assert out["verdict"] == "FAIL" and "judging_rate" in out["why"]


# ------------------------------------------------------------------------- --budget-s is real
def test_budget_defers_named_stages_and_still_writes_the_report(tmp_path: Path,
                                                                monkeypatch) -> None:
    rows = [{"symbol": f"S{i}", "family": "f", "params": {"rr": 1.0 + i},
             "first_seen": (NOW - timedelta(hours=5)).isoformat()} for i in range(5)]
    ledger = _ledger(tmp_path, [{"at": NOW.isoformat(), "cell": "x", "family": "f",
                                 "terminal_gate": "cpcv"}])
    jc.RATCHET.write_text(json.dumps({"priors_cursor": "2026-10-01T00:00:00+00:00"}), "utf-8")
    doc = jc.build(rows, ledger=ledger, now=NOW, deadline=time.monotonic() - 1.0)
    assert doc["budget"]["deadline_hit"] is True
    assert set(doc["budget"]["deferred_stages"]) == set(jc.DEFERRABLE_STAGES)
    assert doc["priors_learned"]["status"] == "DEFERRED"
    assert doc["priors_learned"]["cursor"] == "2026-10-01T00:00:00+00:00"   # queued, not lost
    assert doc["keff_order"]["status"] == "DEFERRED"
    assert doc["judging_rate"]["verdicts_24h"] == 1 and doc["families"]
    free = jc.build(rows, ledger=ledger, now=NOW)
    assert free["budget"]["deferred_stages"] == []


def test_a_deferred_never_judged_step_is_published_deferred_not_zero(tmp_path: Path) -> None:
    """Audit of 0bf4ce83e: with the stage skipped, `families_never_judged` read 0 -- a claim
    the pass never measured."""
    rows = [{"symbol": f"S{i}", "family": "f", "params": {"rr": 1.0 + i},
             "first_seen": (NOW - timedelta(hours=500)).isoformat()} for i in range(5)]
    ledger = _ledger(tmp_path, [{"at": NOW.isoformat(), "cell": "x", "family": "g",
                                 "terminal_gate": "cpcv"}])
    late = jc.build(rows, ledger=ledger, now=NOW, deadline=time.monotonic() - 1.0)
    assert "never_judged" in late["budget"]["deferred_stages"]
    assert late["totals"]["families_never_judged"] == "DEFERRED"
    assert late["never_judged_status"] == "DEFERRED"
    on_time = jc.build(rows, ledger=ledger, now=NOW)
    assert on_time["never_judged_status"] == "MEASURED"
    assert on_time["totals"]["families_never_judged"] == 1


@pytest.mark.parametrize("bad", [math.inf, -math.inf, math.nan])
def test_fence_reads_a_non_finite_rate_as_unmeasured(bad: float) -> None:
    jr = {"status": "MEASURED", "verdicts_24h": bad, "target_per_day": bad}
    loose = fence.judging_rate(_doc(jr), require_state=False, armed=False)
    assert loose["state"] == "UNMEASURED" and loose["verdicts_24h"] is None
    assert fence.judging_rate(_doc(jr), require_state=True, armed=True)["state"] == "FAIL"


def test_main_enforces_budget_s(tmp_path: Path, monkeypatch) -> None:
    seen: dict[str, Any] = {}

    def fake_build(**kw: Any) -> dict:
        seen.update(kw)
        return {"at": NOW.isoformat(), "verdict": "UNMEASURED", "why": "x", "families": {},
                "totals": {}, "quota": {}}

    monkeypatch.setattr(jc, "build", fake_build)
    t = time.monotonic()
    assert jc.main(["--once", "--budget-s", "100", "--no-write", "--json"]) == 0
    assert t + 99 <= seen["deadline"] <= time.monotonic() + 100
    assert seen["ledger_deadline"] < seen["deadline"]


# --------------------------------------------------------------------- the build-failure memo
def test_build_code_identity_restates_the_sealed_replay_identity() -> None:
    from desks.mt5.scripts import external_gauntlet as G
    assert jc.sealed_replay_identity() == G._replay_code_identity()
    assert jc.build_code_identity() and len(str(jc.build_code_identity())) == 24


def _named(cell: str, *, sym: str = "XAUUSD", why: str = "TypeError: unexpected 'chart'",
           reason: str = "build_failed") -> dict:
    return {"reason": reason, "sym": sym, "family": "cot_net_fade", "tf": "H1", "days": 0,
            "bar_bytes": 1000, "why": f"NOT_RUN_BUILD_FAILED: {why}"}


def _bank_update(named: dict, at: datetime, code: str, mtime: float,
                 judged: set[str] | None = None) -> dict:
    return jc.update_unrunnable_bank(named, at=at.isoformat(), code_fp=code, judged=judged,
                                     report_mtime=mtime)


_LAST: dict[str, Any] = {}


def _certain(code: str, t0: datetime) -> datetime:
    """Three report generations, six hours apart, under `code`: the identity is CERTAIN on the
    third, and any canary for it is set on that pass (its result is kept in `_LAST`)."""
    for k in range(3):
        _LAST["out"] = _bank_update({}, t0 + timedelta(hours=3 * k), code, 1000.0 + k)
    return t0 + timedelta(hours=6)


def test_a_failure_parked_under_an_uncertain_identity_keeps_the_weekly_timer() -> None:
    _bank_update({"c1": _named("c1")}, NOW, "A", 1.0)
    row = json.loads(jc.UNRUNNABLE_BANK.read_text())["c1"]
    assert "code_fp" not in row


def test_memoised_failure_is_not_rebuilt_weekly_on_unchanged_code(monkeypatch) -> None:
    monkeypatch.setattr(jc, "_bar_bytes", lambda *_a, **_k: 1000)
    t = _certain("A", NOW)
    _bank_update({f"c{i}": _named(f"c{i}") for i in range(5)}, t, "A", 2000.0)
    bank = json.loads(jc.UNRUNNABLE_BANK.read_text())
    assert all(bank[f"c{i}"]["code_fp"] == "A" for i in range(5))
    later = t + timedelta(days=jc.BUILD_FAILED_RETRY_DAYS + 1)
    out = _bank_update({}, later, "A", 2001.0)
    assert out["readmitted_on_bar_growth"] == 0 and out["bank_size"] == 5
    assert out["build_failure_memo"]["held_by_memo"] == 5
    # Bars growing past the rule still re-admit: the data half of the fingerprint.
    monkeypatch.setattr(jc, "_bar_bytes", lambda *_a, **_k: 2000)
    assert _bank_update({}, later, "A", 2002.0)["readmitted_on_bar_growth"] == 5


def test_a_code_change_sends_one_canary_and_a_repeat_failure_keeps_siblings_parked(
        monkeypatch) -> None:
    monkeypatch.setattr(jc, "_bar_bytes", lambda *_a, **_k: 1000)
    t = _certain("A", NOW)
    _bank_update({f"c{i}": _named(f"c{i}") for i in range(6)}, t, "A", 2000.0)
    tb = _certain("B", t + timedelta(hours=1))
    out = _LAST["out"]
    memo = out["build_failure_memo"]
    assert memo["canaries_started"] == 1 and memo["readmitted"] == 1 and out["bank_size"] == 5
    state = json.loads((jc.UNRUNNABLE_BANK.parent / jc.MEMO_STATE_NAME).read_text())
    (canary,) = next(iter(state["canaries"].values()))["cells"]
    # The first report after it was set may predate it: too early, judged again, not parked.
    out = _bank_update({canary: _named(canary)}, tb + timedelta(hours=1), "B", 3001.0)
    assert canary not in json.loads(jc.UNRUNNABLE_BANK.read_text())
    assert out["build_failure_memo"]["canaries_waiting"] == 1
    # The second: it failed the same way under B -- siblings re-stamped B, still parked.
    out = _bank_update({canary: _named(canary)}, tb + timedelta(hours=2), "B", 3002.0)
    bank = json.loads(jc.UNRUNNABLE_BANK.read_text())
    assert out["build_failure_memo"]["canaries_confirmed"] == 1
    assert len(bank) == 6 and all(r["code_fp"] == "B" for r in bank.values())


def test_a_canary_that_is_judged_releases_every_sibling(monkeypatch) -> None:
    monkeypatch.setattr(jc, "_bar_bytes", lambda *_a, **_k: 1000)
    t = _certain("A", NOW)
    _bank_update({f"c{i}": _named(f"c{i}") for i in range(4)}, t, "A", 2000.0)
    tb = _certain("B", t + timedelta(hours=1))
    state = json.loads((jc.UNRUNNABLE_BANK.parent / jc.MEMO_STATE_NAME).read_text())
    (canary,) = next(iter(state["canaries"].values()))["cells"]
    out = _bank_update({}, tb + timedelta(hours=1), "B", 3001.0, judged={canary})
    assert out["build_failure_memo"]["siblings_released"] == 3 and out["bank_size"] == 0


def test_different_failures_are_different_canaries(monkeypatch) -> None:
    monkeypatch.setattr(jc, "_bar_bytes", lambda *_a, **_k: 1000)
    t = _certain("A", NOW)
    named = {**{f"a{i}": _named(f"a{i}") for i in range(3)},
             **{f"b{i}": _named(f"b{i}", sym="EURUSD") for i in range(3)},
             **{f"n{i}": _named(f"n{i}", reason="no_series", why="no series") for i in range(2)}}
    _bank_update(named, t, "A", 2000.0)
    _certain("B", t + timedelta(hours=1))
    assert _LAST["out"]["build_failure_memo"]["canaries_started"] == 3


def test_without_a_code_identity_the_bank_is_unchanged(monkeypatch) -> None:
    monkeypatch.setattr(jc, "_bar_bytes", lambda *_a, **_k: 1000)
    out = jc.update_unrunnable_bank({"c": _named("c")}, at=NOW.isoformat())
    assert out["build_failure_memo"]["status"] == "OFF"
    later = NOW + timedelta(days=jc.BUILD_FAILED_RETRY_DAYS + 1)
    assert jc.update_unrunnable_bank({}, at=later.isoformat())["readmitted_on_bar_growth"] == 1


# --------------------------------------------------------------- the resident judge's standing
# MERGE RESOLUTION (image companions onto speed train r2, 2026-10-22): judge-rate's own
# `priority_parity` (the miners' MODAL class) is superseded by the train's audited fair-share
# rule, `scripts/judge_priority.py` (the miners' LOWEST class, capped below the live E8 clocks
# and at NORMAL, every raise billed a missed-growth line). Two rules setting one creation flag
# cannot both stand; the sweep child now takes its class from `_judge_flags` alone, and the
# rule's own behaviour is pinned by the fair-share suite (test_judge_cpu_fair_share.py).
def test_sweep_child_takes_its_class_from_the_one_priority_authority(monkeypatch) -> None:
    import subprocess

    seen: dict[str, Any] = {}

    class _Child:
        pid = 1

        def wait(self, timeout: float | None = None) -> int:
            return 0

    def popen(*a: Any, **k: Any) -> _Child:
        seen.update(k)
        return _Child()

    monkeypatch.setattr(sys, "platform", "win32")
    monkeypatch.setattr(runner, "_judge_flags", lambda: 0x20)
    monkeypatch.setattr(runner, "_record_launch_raise", lambda flags, pid: {})
    monkeypatch.setattr(runner, "_sweep_env", lambda: dict(os.environ))
    monkeypatch.setattr(subprocess, "Popen", popen)
    assert runner._one_sweep_child(5.0) == 0
    assert seen["creationflags"] == 0x20
    assert not hasattr(runner, "priority_parity") and not hasattr(runner, "_PRIORITY_DOC")


class _Clock:
    def __init__(self) -> None:
        self.t = 0.0

    def __call__(self) -> float:
        return self.t


def test_a_failure_after_a_long_sweep_starts_the_next_sweep_at_once() -> None:
    clock, slept = _Clock(), []
    seq = iter([1, 0])

    def sweep() -> int:
        clock.t += 1800.0
        return next(seq)

    runner.resident(sweep=sweep, sleep=slept.append, clock=clock, limit_s=None, max_sweeps=2)
    assert slept == []                       # the sweep already paid the pause


def test_an_instant_failure_still_backs_off() -> None:
    clock, slept = _Clock(), []
    seq = iter([1, 0])

    def sweep() -> int:
        clock.t += 5.0
        return next(seq)

    runner.resident(sweep=sweep, sleep=slept.append, clock=clock, limit_s=None, max_sweeps=2)
    assert slept == [runner.RESIDENT_BACKOFF_S[0] - 5.0]
