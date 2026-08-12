"""Gate item 16 / mandate V-A: durable checkpoint-resume, and the four ways it must refuse.

The tests that matter most are the REFUSALS. A checkpoint that resumes is a convenience; a
checkpoint that cannot tell a fresh start from a lost one, or that welds two experiments together,
is worse than having none -- it launders destroyed computation as a clean run.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from libs.ops.checkpoint import (
    CheckpointCorrupt,
    _path,
    clear,
    load,
    restart_waste,
    run,
    save,
    signature_of,
)


def _work_counter():
    calls: list[str] = []

    def work(unit):
        calls.append(str(unit))
        return {"unit": str(unit), "value": len(str(unit))}

    return work, calls


# ------------------------------------------------------------------ the happy path
def test_a_resumed_sweep_does_not_redo_completed_units(tmp_path: Path) -> None:
    """THE WHOLE POINT. The miner issues ~200 rate-limited network units; refetching a host that
    just 429'd is how a temporary refusal becomes a durable block."""
    units = ["a", "b", "c", "d"]
    sig = signature_of(units)
    save("sweep", sig, {"a": 1, "b": 2}, root=tmp_path)

    work, calls = _work_counter()
    out = run("sweep", units, work, signature=sig, root=tmp_path, clear_on_success=False)

    assert calls == ["c", "d"], "a and b must not be re-executed"
    assert out.resumed == ["a", "b"] and out.executed == ["c", "d"]
    assert set(out.results) == {"a", "b", "c", "d"}


def test_no_checkpoint_is_a_fresh_start_not_a_loss(tmp_path: Path) -> None:
    work, calls = _work_counter()
    out = run("new", ["a", "b"], work, root=tmp_path)
    assert out.load_status == "NONE" and calls == ["a", "b"]
    assert out.restart_waste == 0.0, "nothing existed to reuse -- that is not waste"


def test_a_completed_sweep_clears_its_checkpoint(tmp_path: Path) -> None:
    """A finished sweep has nothing to resume, and a stale success record is the fastest route to
    a spliced next run."""
    work, _ = _work_counter()
    run("done", ["a"], work, root=tmp_path)
    assert not _path("done", tmp_path).exists()


# ----------------------------------------------------------- refusal 1: silent restart from zero
def test_a_corrupt_checkpoint_refuses_loudly_by_default(tmp_path: Path) -> None:
    """THE DEFECT THIS EXISTS TO KILL. A truncated file that reads as 'nothing to resume' hands
    back a clean-looking full rerun, and the caller cannot tell a fresh start from a lost one."""
    p = _path("torn", tmp_path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text('{"v": 1, "done": {"a": 1}, "sig', "utf-8")           # torn mid-write
    work, _ = _work_counter()
    with pytest.raises(CheckpointCorrupt):
        run("torn", ["a", "b"], work, root=tmp_path)


def test_corrupt_is_a_distinct_state_from_absent(tmp_path: Path) -> None:
    """L1.41: unknown is not zero, and 'we lost work' is not 'there was none'."""
    p = _path("torn", tmp_path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text("not json at all", "utf-8")
    assert load("torn", root=tmp_path).status == "CORRUPT"
    assert load("never-existed", root=tmp_path).status == "NONE"


def test_a_tampered_payload_fails_its_content_hash(tmp_path: Path) -> None:
    """Hand-editing a checkpoint is not a supported repair. Without the hash, a half-flushed write
    that still parses as JSON would be accepted as completed work."""
    sig = signature_of(["a"])
    p = save("edited", sig, {"a": 1}, root=tmp_path)
    doc = json.loads(p.read_text("utf-8"))
    doc["done"]["a"] = 999                                             # payload changed, hash not
    p.write_text(json.dumps(doc), "utf-8")
    st = load("edited", sig, root=tmp_path)
    assert st.status == "CORRUPT" and "hash" in st.why


def test_restart_after_corruption_is_explicit_and_still_recorded(tmp_path: Path) -> None:
    p = _path("torn", tmp_path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text("{{{", "utf-8")
    work, calls = _work_counter()
    out = run("torn", ["a"], work, root=tmp_path, on_corrupt="RESTART", clear_on_success=False)
    assert calls == ["a"]
    assert out.load_status == "CORRUPT", "the loss must survive into the report"
    assert out.restart_waste is None, "UNMEASURED, never 0.0 -- the file was too damaged to say"


# ------------------------------------------------------------------ refusal 2: spliced experiments
def test_a_changed_work_signature_refuses_to_resume(tmp_path: Path) -> None:
    """Resuming a sweep whose inputs changed welds half of one experiment onto half of another."""
    save("sweep", signature_of(["a", "b"]), {"a": 1}, root=tmp_path)
    st = load("sweep", signature_of(["a", "b", "c"]), root=tmp_path)
    assert st.status == "STALE_SIGNATURE" and st.done == {}
    assert "splice" in st.why


def test_run_recomputes_everything_after_a_signature_change(tmp_path: Path) -> None:
    save("sweep", signature_of(["a"]), {"a": 1}, root=tmp_path)
    work, calls = _work_counter()
    run("sweep", ["a", "b"], work, signature=signature_of(["a", "b"]), root=tmp_path)
    assert calls == ["a", "b"], "the stale 'a' must not be trusted"


# ------------------------------------------------------------------ refusal 3: stale resume
def test_an_expired_checkpoint_is_not_resumable(tmp_path: Path) -> None:
    """A checkpoint from days ago is a time machine serving old observations as fresh ones."""
    sig = signature_of(["a"])
    save("old", sig, {"a": 1}, root=tmp_path)
    st = load("old", sig, root=tmp_path, max_age_h=0.0)
    assert st.status == "EXPIRED" and st.done == {}


def test_an_unparseable_saved_time_reads_as_infinitely_old(tmp_path: Path) -> None:
    """L1.41 again: unknown age must not read as fresh, which would resume anything forever."""
    sig = signature_of(["a"])
    p = save("weird", sig, {"a": 1}, root=tmp_path)
    doc = json.loads(p.read_text("utf-8"))
    doc["saved_utc"] = "not-a-date"
    doc["sha256"] = json.loads(p.read_text("utf-8"))["sha256"]         # payload itself unchanged
    p.write_text(json.dumps(doc), "utf-8")
    assert load("weird", sig, root=tmp_path).status == "EXPIRED"


# ------------------------------------------------------------ refusal 4: failure is not completion
def test_a_failed_unit_is_not_checkpointed_and_is_retried(tmp_path: Path) -> None:
    """A checkpoint that cannot tell failure from completion turns a transient 429 into a
    permanently skipped query -- silent, and invisible in the next run's output."""
    def flaky(unit):
        if unit == "b":
            raise RuntimeError("429 rate limited")
        return unit

    out = run("f", ["a", "b", "c"], flaky, root=tmp_path, clear_on_success=False)
    assert out.failed and "b" in out.failed and "429" in out.failed["b"]

    work, calls = _work_counter()
    run("f", ["a", "b", "c"], work, root=tmp_path, clear_on_success=False)
    assert calls == ["b"], "only the failed unit should be retried"


def test_a_partial_sweep_keeps_its_checkpoint(tmp_path: Path) -> None:
    def flaky(unit):
        if unit == "c":
            raise RuntimeError("boom")
        return unit

    run("p", ["a", "b", "c"], flaky, root=tmp_path)
    assert _path("p", tmp_path).exists(), "an incomplete sweep must remain resumable"


# ------------------------------------------------------------------ atomicity + the V-B metric
def test_save_is_atomic_and_leaves_no_temp_files(tmp_path: Path) -> None:
    """os.replace is atomic only WITHIN a filesystem, which is why the temp file is created in the
    destination directory rather than the system temp dir."""
    save("atom", signature_of(["a"]), {"a": 1}, root=tmp_path)
    leftovers = [p.name for p in _path("atom", tmp_path).parent.iterdir() if ".tmp." in p.name]
    assert leftovers == []


def test_an_interrupted_save_cannot_destroy_the_previous_checkpoint(tmp_path: Path) -> None:
    sig = signature_of(["a"])
    save("keep", sig, {"a": 1}, root=tmp_path)
    before = _path("keep", tmp_path).read_text("utf-8")
    (_path("keep", tmp_path).parent / "keep.json.tmp.99999").write_text("half written", "utf-8")
    assert _path("keep", tmp_path).read_text("utf-8") == before
    assert load("keep", sig, root=tmp_path).resumable


def test_restart_waste_reports_counts_not_just_a_ratio() -> None:
    """100% waste on a 2-unit sweep is noise; 30% on a 200-unit rate-limited sweep is a source
    being hammered. The ratio alone hides which one you have."""
    m = restart_waste(units_total=200, units_executed=60)
    assert m["restart_waste"] == 0.3 and m["units_reused"] == 140
    assert restart_waste(units_total=0, units_executed=0)["restart_waste"] == 0.0


def test_clear_is_idempotent(tmp_path: Path) -> None:
    assert clear("nothing-here", root=tmp_path) is False


# ------------------------------------------------------------- the controlled benchmark (item 15)
def test_controlled_benchmark_checkpointing_beats_restart_from_zero(tmp_path: Path) -> None:
    """GATE ITEM 15's CONTROLLED TEST, measured rather than asserted.

    Two arms, identical work and identical failure point: arm A has no durable state and restarts
    from zero; arm B resumes. The measured quantity is UNITS EXECUTED -- for the miner each unit
    is a rate-limited network request, so this is the real cost, not a proxy for it.
    """
    units = [f"q{i}" for i in range(20)]
    fail_at = 12

    def make(calls):
        def work(unit):
            if unit == units[fail_at] and unit not in calls.get("survived", set()):
                calls.setdefault("survived", set()).add(unit)
                raise RuntimeError("simulated 429 mid-sweep")
            calls.setdefault("n", [0])[0] += 1
            return unit
        return work

    # ARM A -- no checkpoint: attempt 1 dies at unit 12, attempt 2 starts again at unit 0.
    a_calls: dict = {}
    work_a = make(a_calls)
    for _ in range(2):
        for u in units:
            try:
                work_a(u)
            except RuntimeError:
                break
    baseline_units = a_calls["n"][0]

    # ARM B -- checkpointed: attempt 2 resumes at the failed unit.
    b_calls: dict = {}
    work_b = make(b_calls)
    run("bench", units, work_b, root=tmp_path, clear_on_success=False)
    run("bench", units, work_b, root=tmp_path, clear_on_success=False)
    candidate_units = b_calls["n"][0]

    assert candidate_units < baseline_units, (
        f"checkpointed arm executed {candidate_units} units vs baseline {baseline_units} -- "
        "no measured saving means the capability does not earn its complexity")
    saved = (baseline_units - candidate_units) / baseline_units
    assert saved > 0.25, f"only {saved:.1%} of units saved"
