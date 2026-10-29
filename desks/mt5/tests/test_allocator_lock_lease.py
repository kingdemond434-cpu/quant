"""The allocator lock is a LEASE, the heavy pass has a wall clock, and a long hold is RED.

2026-10-29: `pf_allocator --mode heavy` (PID 28696) held the allocator lock for 6.5 hours. The
admission scan had a per-candidate budget and none for the pass, and the lock let a living owner
keep it forever, so every fast pass stood down and MT5-AllocatorFast went 381 minutes stale.
What is pinned:

  * a living owner whose lease expired no longer blocks the next writer, and the late holder is
    told it no longer holds the lock (`holds` -> False) so it cannot publish over its successor;
  * a living owner inside its lease, or with no lease, is still never robbed;
  * the admission scan stops starting re-solves at its pass deadline and carries the rest as
    UNSCORED (never refused, never admitted);
  * allocator liveness goes RED past twice the expected heavy run, pinned to the allocator's own
    budget; BLAS pools are sized before numpy loads, and an explicit setting is kept.
"""
from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

import pytest

_DESK = Path(__file__).resolve().parents[1]
for _p in (str(_DESK), str(_DESK / "research"), str(_DESK.parent.parent)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from research import job_lock as JL  # noqa: E402


@pytest.fixture
def locks(tmp_path, monkeypatch):
    monkeypatch.setattr(JL, "LOCK_ROOT", tmp_path)
    return tmp_path


def _alive_lock(path: Path, *, lease_until: float | None) -> None:
    row = {"token": "other", "pid": os.getpid(), "host": JL.socket.gethostname(),
           "started_at": "2026-10-29T11:26:49+00:00"}
    if lease_until is not None:
        row["lease_until"] = lease_until
    path.write_text(json.dumps(row), "utf-8")


def test_an_expired_lease_is_reclaimed_from_a_living_owner(locks) -> None:
    _alive_lock(locks / "job.json", lease_until=time.time() - 1)
    with JL.exclusive_job("job") as go:
        assert go is True and JL.holds("job") is True
    assert JL.holds("job") is None                      # released


def test_a_living_owner_inside_its_lease_or_without_one_is_never_robbed(locks) -> None:
    _alive_lock(locks / "job.json", lease_until=time.time() + 600)
    with JL.exclusive_job("job") as go:
        assert go is False
    _alive_lock(locks / "job.json", lease_until=None)
    with JL.exclusive_job("job") as go:
        assert go is False


def test_a_holder_whose_lock_was_reclaimed_is_told_it_no_longer_holds_it(locks) -> None:
    with JL.exclusive_job("job", lease_s=0.01) as go:
        assert go is True and JL.holds("job") is True
        row = json.loads((locks / "job.json").read_text("utf-8"))
        assert row["lease_s"] == 0.01 and row["lease_until"] > 0
        successor = {**row, "token": "successor"}
        (locks / "job.json").write_text(json.dumps(successor), "utf-8")
        assert JL.holds("job") is False
    # the successor's lock is never deleted by the late holder on exit
    owner = json.loads((locks / "job.json").read_text("utf-8"))["token"]
    assert owner == successor["token"]


def test_the_allocator_refuses_to_publish_on_a_lost_lease(monkeypatch) -> None:
    from research import pf_allocator as pa
    monkeypatch.setattr(JL, "_HELD", {"pf_allocator": (Path("/nonexistent/lock.json"), "t")})
    with pytest.raises(pa.LeaseLost):
        pa._lease_guard("publish")
    monkeypatch.setattr(JL, "_HELD", {})
    pa._lease_guard("publish")                          # never took the lock: not stopped
    src = (_DESK / "research" / "pf_allocator.py").read_text(encoding="utf-8").replace("\r\n", "\n")
    # MF1: the certificate is written only after the final guard, beside the book, and both
    # carry the pass's lock token; nothing certifies ~460 lines before the publish any more.
    g = src.index('    _lease_guard("publish")\n')
    tail = src[g:g + 2000]
    assert "certify(cert_pending[0], root=ROOT, book=cert_pending[1])" in tail
    assert 'art["lock_token"] = _lock_token()' in tail and "_replace_retry(_tmp, OUT)" in tail
    assert src.count("certify(") == 1
    # MF2: a lost lease is never swallowed as a failed contest
    assert "    except LeaseLost:\n        raise" in src
    assert "lease_s=HEAVY_LEASE_S if args.mode == \"heavy\" else None" in src
    assert "pass_deadline=t0 + HEAVY_ADMISSION_BUDGET_S" in src


def test_the_admission_scan_carries_the_rest_as_unscored_past_its_deadline() -> None:
    import numpy as np

    from libs.portfolio.robust_elog import SleeveEvidence, WorldConfig, sample_worlds
    from research import pf_allocator as pa
    rng = np.random.default_rng(0)
    ev = [SleeveEvidence(f"s{i}", rng.normal(0.002, 0.01, 300)) for i in range(4)]
    cfg = WorldConfig(n_worlds=32, n_rows=64)
    worlds = sample_worlds(ev, cfg)
    doc = pa.marginal_admission(ev, worlds, cfg, incumbent={"s0": 0.05},
                                bounds={e.name: 0.1 for e in ev}, total_heat=0.05,
                                pass_deadline=time.time() - 1)
    assert set(doc["unscored"]) == {"s1", "s2", "s3"}
    assert all("pass deadline" in why for why in doc["unscored"].values())
    assert not doc.get("refused")
    # MF3: a deadline-cut scan says it is incomplete, so the hourly cycle runs heavy again
    assert doc["deadline_cut"] == 3 and doc["complete"] is False and doc["status"] == "MEASURED"
    hc = (_DESK / "research" / "hourly_cycle.py").read_text(encoding="utf-8")
    assert hc.count('adm.get("complete") is False') == 2


def test_liveness_is_red_past_twice_the_expected_heavy_run(tmp_path, monkeypatch) -> None:
    from research import allocator_liveness as AL
    from research import pf_allocator as pa
    assert AL.LOCK_EXPECTED_S == pa.HEAVY_ADMISSION_BUDGET_S + 5 * 60
    assert pa.HEAVY_LEASE_S < AL.LOCK_HELD_RED_S
    monkeypatch.setattr(AL, "DATA", tmp_path)
    (tmp_path / ".job_locks").mkdir()
    lock = tmp_path / ".job_locks" / "pf_allocator.json"
    assert AL._lock_held(time.time())["status"] == "FREE"
    from datetime import UTC, datetime, timedelta
    old = (datetime.now(UTC) - timedelta(hours=6, minutes=30)).isoformat()
    lock.write_text(json.dumps({"pid": 28696, "started_at": old}), "utf-8")
    red = AL._lock_held(time.time())
    assert red["status"] == "HELD_TOO_LONG" and "28696" in red["why"]
    lock.write_text(json.dumps({"pid": 1, "started_at": datetime.now(UTC).isoformat()}), "utf-8")
    assert AL._lock_held(time.time())["status"] == "HELD"


def test_blas_pools_are_sized_before_numpy_and_an_explicit_setting_is_kept(monkeypatch) -> None:
    from research import pf_allocator as pa
    for var in ("OPENBLAS_NUM_THREADS", "OMP_NUM_THREADS", "MKL_NUM_THREADS"):
        monkeypatch.delenv(var, raising=False)
    monkeypatch.setenv("MKL_NUM_THREADS", "3")
    n = pa._cap_blas_threads()
    if n is None:
        pytest.skip("cpu affinity unreadable on this host")
    assert 1 <= n <= pa.BLAS_THREAD_CAP
    assert os.environ["OPENBLAS_NUM_THREADS"] == str(n) and os.environ["MKL_NUM_THREADS"] == "3"
    src = (_DESK / "research" / "pf_allocator.py").read_text(encoding="utf-8")
    assert src.index("_cap_blas_threads()\n") < src.index("import numpy as np")


def test_the_gateway_certifies_only_the_book_the_certificate_names() -> None:
    from mt5desk.decision_core import book_pair_matches
    assert book_pair_matches({"a": 0.0123456, "b": 0.0}, {"a": 0.012346})
    assert not book_pair_matches({"a": 0.01}, {"a": 0.01, "b": 0.02})     # a newer book
    assert not book_pair_matches(None, {"a": 0.01})
    assert not book_pair_matches({"a": "x"}, {"a": 0.01})


def test_the_publish_replace_retries_a_held_destination(tmp_path, monkeypatch) -> None:
    from research import pf_allocator as pa
    monkeypatch.setattr(pa, "REPLACE_BACKOFF_S", (0.0, 0.0))
    calls = []
    real = os.replace

    def flaky(a, b):
        calls.append(1)
        if len(calls) < 3:
            raise PermissionError("held by a reader")
        real(a, b)
    monkeypatch.setattr(pa.os, "replace", flaky)
    src, dst = tmp_path / "s", tmp_path / "d"
    src.write_text("x")
    pa._replace_retry(src, dst)
    assert dst.read_text() == "x" and len(calls) == 3
    calls.clear()
    monkeypatch.setattr(pa.os, "replace", lambda a, b: (_ for _ in ()).throw(PermissionError()))
    with pytest.raises(PermissionError):
        pa._replace_retry(src, dst)


def test_a_reclaimer_never_deletes_a_lock_it_did_not_judge(locks) -> None:
    path = locks / "pf_allocator.json"
    path.write_text(json.dumps({"token": "fresh"}), "utf-8")
    JL._reclaim(path, "expired")                       # a successor already replaced it
    assert json.loads(path.read_text("utf-8"))["token"] == "fresh"  # noqa: S105
    JL._reclaim(path, "fresh")
    assert not path.exists() and not list(locks.glob("*.reclaim"))
    JL._reclaim(path, "fresh")                         # already gone: nothing to do


def test_the_deadline_and_lease_lines_are_published_both_ways(tmp_path, monkeypatch) -> None:
    from research import missed_growth as MG
    from research import pf_allocator as pa
    assert MG.ADMISSION_DEADLINE_S == pa.HEAVY_ADMISSION_BUDGET_S
    assert MG.admission_deadline_line({})["verdict"] == MG.UNMEASURED
    ok = MG.admission_deadline_line({"admission": {"deadline_cut": 0, "elapsed_s": 900}})
    assert ok["verdict"] == MG.NOT_BINDING and ok["lock_returned_in_budget"] is True
    cut = MG.admission_deadline_line({"admission": {"deadline_cut": 4, "elapsed_s": 1210}})
    assert cut["verdict"] == MG.UNMEASURED and cut["deferred_unscored"] == 4
    monkeypatch.setattr(MG, "LEASE_LOST", tmp_path / "ALLOCATOR_LEASE_LOST.json")
    assert MG.lock_lease_line({})["verdict"] == MG.NOT_BINDING
    MG.LEASE_LOST.write_text(json.dumps({"at": "2026-10-29T12:00:00+00:00"}), "utf-8")
    assert MG.lock_lease_line({"generated_utc": "2026-10-29T11:00:00+00:00"})["n"] == 1
    aged = MG.lock_lease_line({"generated_utc": "2026-10-29T13:00:00+00:00"})
    assert aged["verdict"] == MG.NOT_BINDING and aged["recovered"] is True
    src = (_DESK / "research" / "missed_growth.py").read_text(encoding="utf-8")
    assert '"admission_deadline": admission_deadline_line(alloc)' in src
    assert '"allocator_lock_lease": lock_lease_line(alloc)' in src
    assert "def measure_admission_deadline" not in src and "def measure_lock_lease" not in src
