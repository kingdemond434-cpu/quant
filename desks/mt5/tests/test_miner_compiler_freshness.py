"""miner_candidates.json is judged by its CONTENT stamp, end to end (2026-10-29).

The artifact sat at one `compiled_at` for weeks on the trading box while every task returned 0:
the compiler's bounded compile was followed by an UNBOUNDED hypothesis-graph pass that ran BEFORE
the write, so a pass killed at its cap published nothing and saved no cursor; the leg never
compared the artifact before and after; and every freshness check read the mtime, which the
artifact's readers keep refreshing. These pin the four repairs:

  * the compiler publishes before the graph pass, so a kill there still leaves a fresh artifact
  * a leg that exits 0 (or is killed) without advancing `compiled_at` reports FAILED, named
  * a lock-held refusal and a memory stand-down are different SKIPPED reasons
  * the fence reads `compiled_at` from the file head and fails on stale, missing or unreadable
"""
from __future__ import annotations

import json
import os
import sys
import time
from contextlib import contextmanager
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

_DESK = Path(__file__).resolve().parents[1]
_REPO = _DESK.parent.parent
for _p in (str(_DESK), str(_DESK / "research"), str(_REPO), str(_REPO / "ops")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import hourly_cycle as hc  # noqa: E402
import miner_candidate_compiler as mcc  # noqa: E402
import organ_contract as oc  # noqa: E402
import process_health as ph  # noqa: E402

from libs.ops.content_stamp import read_head_stamp, stamp_age_min  # noqa: E402

ORGAN = "MT5-Hourly (miner compiler)"
REL = "desks/mt5/data/hypotheses/miner_candidates.json"


def _artifact(path: Path, compiled_at: str, n: int = 2000) -> Path:
    """A miner_candidates-shaped file whose stamp is the first key and whose body is large."""
    path.parent.mkdir(parents=True, exist_ok=True)
    doc = {"compiled_at": compiled_at,
           "hypotheses": [{"symbol": "EURUSD", "family": "overnight_gap_decay", "i": i}
                          for i in range(n)]}
    path.write_text(json.dumps(doc, indent=1), encoding="utf-8")
    return path


# ------------------------------------------------------------------------------ head-stamp read

def test_head_stamp_is_read_without_parsing_the_body(tmp_path: Path) -> None:
    p = _artifact(tmp_path / "m.json", "2026-10-29T10:00:00+00:00")
    # Truncate mid-body: a full json.load would fail; the head read must not care.
    raw = p.read_bytes()
    p.write_bytes(raw[: len(raw) // 2])
    stamp, how = read_head_stamp(p, "compiled_at")
    assert stamp == datetime(2026, 10, 29, 10, 0, tzinfo=UTC)
    assert "file head" in how


def test_head_stamp_absent_missing_and_garbage_are_unmeasured(tmp_path: Path) -> None:
    assert read_head_stamp(tmp_path / "nope.json", "compiled_at")[0] is None
    q = tmp_path / "nokey.json"
    q.write_text(json.dumps({"built_at": "2026-10-29T10:00:00+00:00"}), encoding="utf-8")
    s, why = read_head_stamp(q, "compiled_at")
    assert s is None and why.startswith("UNMEASURED")
    r = tmp_path / "bad.json"
    r.write_text('{"compiled_at": "yesterday-ish"}', encoding="utf-8")
    s, why = read_head_stamp(r, "compiled_at")
    assert s is None and "ISO-8601" in why


def test_naive_stamp_is_utc_and_future_stamp_is_unmeasured(tmp_path: Path) -> None:
    p = tmp_path / "n.json"
    p.write_text('{"compiled_at": "2026-10-29T10:00:00"}', encoding="utf-8")
    assert read_head_stamp(p, "compiled_at")[0] == datetime(2026, 10, 29, 10, tzinfo=UTC)
    now = datetime(2026, 10, 29, 9, 0, tzinfo=UTC)
    age, why = stamp_age_min(p, "compiled_at", now)
    assert age is None and "future" in why


# ------------------------------------------------------------------------------ the fence

def _tree(tmp_path: Path, compiled_at: str | None) -> Path:
    root = tmp_path / "repo"
    if compiled_at is not None:
        _artifact(root / REL, compiled_at, n=10)
    return root


def test_fence_fails_on_a_stale_stamp_even_when_the_mtime_is_fresh(tmp_path: Path) -> None:
    old = (datetime.now(UTC) - timedelta(days=30)).isoformat(timespec="seconds")
    root = _tree(tmp_path, old)
    os.utime(root / REL, (time.time(), time.time()))      # a reader just rewrote it
    rep = oc.check(only=ORGAN, root=root)
    (row,) = rep["rows"]
    assert rep["status"] == "FAILING" and row["verdict"] == "STALE"
    assert row["age_basis"] == "compiled_at" and row["age_min"] > 40000
    assert REL in row["why"] and "180 min" in row["why"]
    causes = " | ".join(row["likely_cause"])
    for source in ("last attempt", "compute ledger", "job lock"):
        assert source in causes


def test_fence_names_the_cause_it_can_read(tmp_path: Path) -> None:
    old = (datetime.now(UTC) - timedelta(hours=9)).isoformat(timespec="seconds")
    root = _tree(tmp_path, old)
    desk = root / "desks" / "mt5"
    (desk / "reports").mkdir(parents=True)
    (desk / "reports" / "MINER_COMPILER_ATTEMPT.json").write_text(json.dumps(
        {"at": "2026-10-29T11:00:00+00:00", "leg": "intake_catchup", "status": "SKIPPED",
         "skip_reason": "MEMORY_STAND_DOWN", "why": "memory stand-down"}), encoding="utf-8")
    (desk / "reports" / "LEG_ROTATION.json").write_text(json.dumps(
        {"generated": "2026-10-29T11:00:00+00:00", "deferred_this_pass": ["compile_candidates"]}),
        encoding="utf-8")
    (desk / "data").mkdir(parents=True, exist_ok=True)
    (desk / "data" / "compute_ledger.jsonl").write_text(json.dumps(
        {"at": "2026-10-29T10:00:00+00:00", "run": "compile_candidates",
         "outcome": "TIMEOUT", "wall_s": 723.0}) + "\n", encoding="utf-8")
    (desk / "data" / ".job_locks").mkdir()
    (desk / "data" / ".job_locks" / "miner_candidate_compiler.json").write_text(
        json.dumps({"pid": 4242, "started_at": "2026-10-29T10:58:00+00:00"}), encoding="utf-8")
    (row,) = oc.check(only=ORGAN, root=root)["rows"]
    causes = " | ".join(row["likely_cause"])
    assert "MEMORY_STAND_DOWN" in causes
    assert "compile_candidates last 2026-10-29T10:00:00+00:00 outcome=TIMEOUT" in causes
    assert "deferred_this_pass" in causes
    assert "job lock HELD" in causes and "4242" in causes


def test_fence_fails_unmeasured_on_a_missing_or_unstamped_artifact(tmp_path: Path) -> None:
    root = _tree(tmp_path, None)
    (row,) = oc.check(only=ORGAN, root=root)["rows"]
    assert row["verdict"] == "UNMEASURED" and row["age_min"] is None
    (root / REL).parent.mkdir(parents=True)
    (root / REL).write_text('{"hypotheses": []}', encoding="utf-8")
    (row,) = oc.check(only=ORGAN, root=root)["rows"]
    assert row["verdict"] == "UNMEASURED"


def test_fence_passes_on_a_fresh_stamp_under_an_old_mtime(tmp_path: Path) -> None:
    now = datetime.now(UTC).isoformat(timespec="seconds")
    root = _tree(tmp_path, now)
    os.utime(root / REL, (time.time() - 86400 * 9, time.time() - 86400 * 9))
    rep = oc.check(only=ORGAN, root=root)
    assert rep["status"] == "OK" and rep["rows"][0]["verdict"] == "OK"


def test_fence_cli_exits_nonzero_and_never_overwrites_the_board(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    old = (datetime.now(UTC) - timedelta(days=3)).isoformat(timespec="seconds")
    root = _tree(tmp_path, old)
    board = tmp_path / "board.json"
    monkeypatch.setattr(oc, "ROOT", root)
    monkeypatch.setattr(oc, "OUT", board)
    out = tmp_path / "fresh.json"
    assert oc.main(["--only", ORGAN, "--out", str(out)]) == 1
    assert json.loads(out.read_text("utf-8"))["rows"][0]["verdict"] == "STALE"
    assert not board.exists(), "a one-row pass must not replace the whole contract board"
    assert oc.main(["--only", "no such organ"]) == 2


def test_process_health_ages_the_stamped_contract_by_its_content(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    old = (datetime.now(UTC) - timedelta(days=3)).isoformat(timespec="seconds")
    root = _tree(tmp_path, old)
    os.utime(root / REL, (time.time(), time.time()))
    monkeypatch.setattr(ph, "ROOT", root)
    age, basis = ph._contract_age(ORGAN, REL)
    assert age is not None and age > 3 * 24 * 60 - 5 and "compiled_at" in basis
    (root / REL).write_text('{"hypotheses": []}', encoding="utf-8")
    age, basis = ph._contract_age(ORGAN, REL)
    assert age is None and basis.startswith("UNMEASURED")


def test_the_contract_is_a_component_of_the_hourly_task() -> None:
    rel, max_age, _ = oc.CONTRACTS[ORGAN]
    assert rel == REL and max_age == 180 and ORGAN.split(" (", 1)[0] == "MT5-Hourly"
    assert oc.STAMPS[ORGAN]["key"] == "compiled_at"


# ------------------------------------------------------------------------------ the leg checks

def test_exit_zero_without_advancing_compiled_at_is_failed(tmp_path: Path) -> None:
    p = _artifact(tmp_path / "m.json", "2026-10-03T10:00:00+00:00", n=1)
    before, _ = hc._compiled_at(p)
    out = hc._require_compiled_at_advance({"exit_code": 0, "tail": ""}, before, p)
    assert out["status"] == "FAILED" and "without advancing compiled_at" in out["why"]
    assert out["compiled_at_advanced"] is False


def test_killed_before_publishing_is_failed_with_its_cap(tmp_path: Path) -> None:
    p = _artifact(tmp_path / "m.json", "2026-10-03T10:00:00+00:00", n=1)
    before, _ = hc._compiled_at(p)
    out = hc._require_compiled_at_advance({"exit_code": None, "timeout_s": 720}, before, p)
    assert out["status"] == "FAILED" and "killed at its 720s cap before publishing" in out["why"]


def test_killed_after_publishing_keeps_timeout_and_says_it_advanced(tmp_path: Path) -> None:
    p = _artifact(tmp_path / "m.json", "2026-10-03T10:00:00+00:00", n=1)
    before, _ = hc._compiled_at(p)
    _artifact(p, "2026-10-29T10:00:00+00:00", n=1)
    out = hc._require_compiled_at_advance({"exit_code": None, "timeout_s": 720}, before, p)
    assert "status" not in out and out["compiled_at_advanced"] is True and "AFTER" in out["note"]


def test_unreadable_after_is_failed_and_a_crash_is_left_a_crash(tmp_path: Path) -> None:
    p = tmp_path / "m.json"
    out = hc._require_compiled_at_advance({"exit_code": 0}, None, p)
    assert out["status"] == "FAILED" and "unreadable" in out["why"]
    crash = hc._require_compiled_at_advance({"exit_code": 1}, None, p)
    assert "status" not in crash and crash["exit_code"] == 1


def _refusing_lock(reason: str):
    from research import job_lock

    @contextmanager
    def _ex(name: str, need_mb: int = 0, **_kw):
        job_lock.LAST_REFUSAL[name] = {"reason": reason, "detail": f"{reason} detail"}
        yield False
    return _ex


@pytest.mark.parametrize("reason,needle", [
    ("MEMORY_STAND_DOWN", "memory stand-down"),
    ("LOCK_HELD", "already owned"),
])
def test_catch_up_names_memory_and_lock_refusals_apart(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch, reason: str, needle: str) -> None:
    from research import job_lock
    monkeypatch.setattr(job_lock, "exclusive_job", _refusing_lock(reason))
    monkeypatch.setattr(hc, "MINER_COMPILER_ATTEMPT", tmp_path / "attempt.json")
    out = hc.catch_up_intake()
    assert out["status"] == "SKIPPED" and out["skip_reason"] == reason and needle in out["why"]
    rec = json.loads((tmp_path / "attempt.json").read_text("utf-8"))
    assert rec["skip_reason"] == reason and rec["leg"] == "intake_catchup"


def test_catch_up_withholds_the_merge_when_the_compile_did_not_advance(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from research import job_lock

    @contextmanager
    def _ok(name: str, need_mb: int = 0, **_kw):
        yield True
    monkeypatch.setattr(job_lock, "exclusive_job", _ok)
    monkeypatch.setattr(hc, "MINER_COMPILER_ATTEMPT", tmp_path / "attempt.json")
    monkeypatch.setattr(hc, "MINER_CANDIDATES",
                        _artifact(tmp_path / "m.json", "2026-10-03T10:00:00+00:00", n=1))
    calls: list[str] = []

    def _fake_producer(name: str, *_a, **_k) -> dict:
        calls.append(name)
        return {"exit_code": 0}
    monkeypatch.setattr(hc, "_producer", _fake_producer)
    out = hc.catch_up_intake()
    assert out["status"] == "FAILED" and "silent no-op" in out["why"]
    assert calls == ["miner_candidate_compiler"], "the stale artifact must not be merged"


def test_job_lock_records_why_it_refused(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from research import job_lock
    monkeypatch.setattr(job_lock, "LOCK_ROOT", tmp_path)
    (tmp_path / "x.json").write_text(json.dumps({"pid": os.getpid()}), encoding="utf-8")
    with job_lock.exclusive_job("x") as got:
        assert got is False
    assert job_lock.LAST_REFUSAL["x"]["reason"] == "LOCK_HELD"
    monkeypatch.setattr(job_lock, "free_mb", lambda: 10)
    monkeypatch.setattr(job_lock, "measured_need_mb", lambda n, d: (d, "declared"))
    monkeypatch.setattr(job_lock, "ADMIT_PATIENCE_SECONDS", 0)
    monkeypatch.setattr(job_lock.time, "sleep", lambda s: None)
    with job_lock.exclusive_job("y", need_mb=5000) as got:
        assert got is False
    assert job_lock.LAST_REFUSAL["y"]["reason"] == "MEMORY_STAND_DOWN"
    assert job_lock.LAST_REFUSAL["y"]["free_mb"] == 10


def test_the_fence_is_a_core_hourly_leg_with_a_layer() -> None:
    from libs.research import layers
    src = Path(hc.__file__).read_text("utf-8")
    assert "miner_compiler_fresh" in hc.CORE_LEGS
    assert '_costed("miner_compiler_fresh", miner_compiler_fresh)' in src
    assert '"miner_compiler_fresh": mcf' in src
    assert layers.LEG_LAYER.get("miner_compiler_fresh") == "meta"


# ------------------------------------------------------------------------------ the compiler

class _Killed(BaseException):
    """Stands in for the leg's cap killing the process inside the graph pass."""


class _GraphStub:
    def prior_failures(self, *_a, **_k):
        return {"n_failed": 0, "region": ""}

    def rows(self):
        return []


def test_a_pass_killed_in_the_graph_pass_has_already_published(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    import libs.ops.repair_invoke as ri
    import libs.research.hypothesis_graph as hg
    root = tmp_path / "intel"
    (root / "deepseek").mkdir(parents=True)
    (root / "deepseek" / "discoveries_1.json").write_text(json.dumps([
        {"kind": "hypothesis", "family": "overnight_gap_decay", "symbols": ["XAUUSD"],
         "title": "structured"}]), encoding="utf-8")
    monkeypatch.setattr(mcc, "INTEL_ROOTS", (root,))
    for attr, name in (("OUT", "out.json"), ("DEEPEN", "deepen.json"),
                       ("DEEPEN_WORKED", "deepening_worked.jsonl"),
                       ("DEEPENED", "deepened.json"), ("CURSOR", "cursor.json")):
        monkeypatch.setattr(mcc, attr, tmp_path / name)
    monkeypatch.setattr(mcc, "known_symbols", lambda: {"XAUUSD", "EURUSD"})
    monkeypatch.setattr(mcc, "structurally_untestable_families", lambda: {})
    monkeypatch.setattr(mcc, "expand_axes", lambda rows: rows)
    monkeypatch.setattr(hg, "Graph", _GraphStub)
    monkeypatch.setattr(ri, "request_repair", lambda reason, **kw: False)
    # Keep the pass inside tmp_path: the build-failure bank and the lineage sidecar otherwise
    # write desks/mt5/data/build_failures.jsonl and lineage.sqlite in the working tree.
    from research import build_failure_bank as bfb
    monkeypatch.setattr(bfb, "LEDGER", tmp_path / "build_failures.jsonl")
    monkeypatch.setattr(mcc, "_lineage", lambda out: None)

    def _die():
        raise _Killed()
    monkeypatch.setattr(mcc, "_graph_snapshot", _die)
    with pytest.raises(_Killed):
        mcc.main()
    out = json.loads((tmp_path / "out.json").read_text("utf-8"))
    assert out["compiled_at"] and out["executable_candidates"] == 1
    assert out["graph"]["updated"] is False and "pending" in out["graph"]
    assert (tmp_path / "deepen.json").exists()


def test_record_candidates_writes_the_batch_in_one_open(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    import libs.research.hypothesis_graph as hg
    g = hg.Graph(tmp_path / "graph.jsonl")
    opens: list[int] = []
    real_append_rows = hg.Graph.append_rows

    def _count(self, rows):
        opens.append(len(rows))
        return real_append_rows(self, rows)
    monkeypatch.setattr(hg.Graph, "append_rows", _count)
    monkeypatch.setattr(hg.Graph, "append",
                        lambda self, node: pytest.fail("per-row append is the old path"))
    n = hg.record_candidates([
        {"symbol": "EURUSD", "family": "overnight_gap_decay", "params": {"k": i}}
        for i in range(5)], source="miner_candidate_compiler", graph=g)
    assert n == 5 and opens == [5]
    assert len((tmp_path / "graph.jsonl").read_text("utf-8").splitlines()) == 5
