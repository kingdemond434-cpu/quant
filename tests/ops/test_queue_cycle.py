"""The queue had five modules, full test coverage, and no process that had ever opened it.

MEASURED 2026-09-10:  grep -rn 'TaskQueue(' --include=*.py . | grep -v tests  ->  no results

`task_queue`, `worker`, `org`, `wiring_campaign` and `research.coverage_governor` form a complete
loop -- produce, claim, fail, escalate, reach a person -- and nothing on this desk had ever
constructed the queue outside a test. These tests pin the properties that decide whether the clock
added to that loop is real rather than decorative:

    A BROKEN PRODUCER MUST NOT SKIP THE SWEEP. The sweep is the only thing that tells a person
    work died. If a producer raising took the pass down, the failure that most needs escalating --
    the one that broke the producer -- would be the one guaranteed not to be reported. So a
    producer exception is caught, named in the artifact, and the pass continues.

    THE HUMAN INBOX MUST SURFACE. `org.HUMAN_INBOX` is owned by no role deliberately, so it can
    never be claimed and never disappears from a census. That is only useful if something reads
    it: `needs_a_person` is the number, and it is what an alert would fire on.

    THE PASS RUNS NOTHING. A producer that also executes cannot be audited, and on this desk the
    queued work includes edits to money-path source. Pinned by inspection of the module, the same
    way `wiring_campaign` is pinned.

    IT IS IDEMPOTENT ACROSS PASSES. The clock is hourly. Producers dedupe by key, so a second
    pass with the same inputs must not double the queue -- otherwise the census reads as work in
    flight when nothing is moving.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from libs.ops import queue_cycle  # noqa: E402
from libs.ops.org import HUMAN_INBOX, desk_org  # noqa: E402
from libs.ops.task_queue import TaskQueue  # noqa: E402


@pytest.fixture
def q(tmp_path) -> TaskQueue:
    return TaskQueue(tmp_path / "q.jsonl")


@pytest.fixture
def quiet(monkeypatch):
    """Both real producers off. Each has its own tests; these are about the pass around them."""
    monkeypatch.setattr(queue_cycle, "PRODUCERS", ())
    return None


def test_a_producer_that_raises_is_named_and_does_not_take_the_pass(tmp_path, q, monkeypatch):
    """The failure that breaks a producer is exactly the one that most needs to be escalated."""
    def boom(root, queue):
        raise RuntimeError("the audit walked into a symlink loop")

    monkeypatch.setattr(queue_cycle, "PRODUCERS", ("boom", "ok"))
    monkeypatch.setitem(queue_cycle._IMPL, "boom", boom)
    monkeypatch.setitem(queue_cycle._IMPL, "ok", lambda root, queue: {"queued": ["x"]})

    doc = queue_cycle.run(tmp_path, queue=q)
    assert "boom" in doc["producers_failed"]
    assert "symlink loop" in doc["producers_failed"]["boom"]
    assert doc["produced"]["ok"] == {"queued": ["x"]}
    assert "queue" in doc and "org" in doc, "the sweep and the census still ran"


def test_dead_work_reaches_a_person_and_is_counted(tmp_path, q, quiet):
    """A task owned by the TOP role has no supervisor, so it goes to a kind nobody can claim."""
    org = desk_org()
    task = org.delegate(q, "wire", frm="ops", payload={"module": "libs/research/alpha_rl.py"})
    assert task is not None
    for _ in range(task.max_attempts):
        got = q.claim("w", kinds=("wire",))
        assert got is not None
        q.fail(got.id, "w", why="no consumer chosen")
    assert q.tasks()[task.id].state == "DEAD"

    doc = queue_cycle.run(tmp_path, queue=q)
    assert doc["needs_a_person"] == 1
    assert doc["human_inbox"][0]["id"] in {t.id for t in q.tasks().values()}
    assert any(t.kind == HUMAN_INBOX for t in q.tasks().values())


def test_a_quiet_pass_asks_for_nothing(tmp_path, q, quiet):
    doc = queue_cycle.run(tmp_path, queue=q)
    assert doc["needs_a_person"] == 0 and doc["human_inbox"] == []
    assert doc["queue"]["total"] == 0


def test_inbox_hides_the_routing_keys_and_orders_oldest_first(tmp_path, q, quiet):
    """An operator reads the work, not the org chart's bookkeeping."""
    org = desk_org()
    made = []
    for i in range(2):
        t = org.delegate(q, "wire", frm="ops", payload={"module": f"m{i}.py"},
                         dedupe_key=f"wire:m{i}")
        for _ in range(t.max_attempts):
            got = q.claim("w", kinds=("wire",))
            q.fail(got.id, "w", why=f"failure {i}")
        made.append(t.id)
    doc = queue_cycle.run(tmp_path, queue=q)
    assert doc["needs_a_person"] == 2
    rows = doc["human_inbox"]
    assert [r["created_at"] for r in rows] == sorted(r["created_at"] for r in rows)
    assert all(not k.startswith("_") for r in rows for k in r["payload"])


def test_second_pass_does_not_double_the_queue(tmp_path, q, monkeypatch):
    """The clock is hourly; a producer whose dedupe failed would read as work in flight."""
    org = desk_org()
    monkeypatch.setattr(queue_cycle, "PRODUCERS", ("once",))
    monkeypatch.setitem(
        queue_cycle._IMPL, "once",
        lambda root, queue: {"queued": [org.delegate(queue, "wire", frm="ops",
                                                     payload={"module": "m.py"},
                                                     dedupe_key="wire:m.py")]})
    queue_cycle.run(tmp_path, queue=q)
    queue_cycle.run(tmp_path, queue=q)
    assert len(q.tasks()) == 1


def test_the_escalation_is_never_itself_escalated_across_passes(tmp_path, q, quiet):
    """`sweep_dead`'s marker is existence, not liveness -- otherwise the pair regenerate forever."""
    org = desk_org()
    t = org.delegate(q, "wire", frm="ops", payload={"module": "m.py"})
    for _ in range(t.max_attempts):
        got = q.claim("w", kinds=("wire",))
        q.fail(got.id, "w", why="nope")
    before = None
    for _ in range(4):
        queue_cycle.run(tmp_path, queue=q)
        n = len(q.tasks())
        if before is not None:
            assert n == before, "a pass added a task with no new input"
        before = n


def test_main_writes_the_fold_and_not_the_journal(tmp_path, q, quiet, monkeypatch, capsys):
    """A reader that folded the journal to answer 'is anything dead' re-implements the queue."""
    monkeypatch.setattr(queue_cycle, "queue_path", lambda root: tmp_path / "q.jsonl")
    assert queue_cycle.main(["--root", str(tmp_path)]) == 0
    out = tmp_path / Path(*queue_cycle.OUT_REL.split("/"))
    doc = json.loads(out.read_text(encoding="utf-8"))
    assert set(doc) >= {"at", "queue", "org", "produced", "human_inbox", "needs_a_person"}
    assert "wrote" in capsys.readouterr().out


def test_the_pass_runs_no_task_it_queued():
    """A `wire` task edits source, some of it on money paths. A producer that also executes
    cannot be audited, and the choice of consumer and call site is a design decision."""
    src = (_ROOT / "libs" / "ops" / "queue_cycle.py").read_text(encoding="utf-8")
    for forbidden in ("subprocess", "os.system", "exec(", "eval(", "\nfrom libs.ops.worker",
                      "import worker"):
        assert forbidden not in src, f"the clock reached for {forbidden}"


def test_the_queue_file_is_never_shared_between_machines():
    """The journal records leases naming processes that exist on one box. Folded elsewhere, a
    dead container's leases would make the live box refuse to hand out work nobody is doing."""
    ignore = (_ROOT / ".gitignore").read_text(encoding="utf-8")
    assert queue_cycle.QUEUE_REL in ignore
