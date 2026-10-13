"""The `lanes` producer: a new data version becomes information work, which invalidates only its
lineage dependents in the strategy lane -- read from BOTH lineage stores -- and drains with no
idle gap. Fixture tree only; no network."""
from __future__ import annotations

import json
import sqlite3
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from libs.ops import queue_cycle  # noqa: E402
from libs.ops.task_queue import INFORMATION, STRATEGY, TaskQueue  # noqa: E402


def _tree(root: Path, *, rows_s1: int = 300) -> None:
    data = root / "desks" / "mt5" / "data"
    (data / "acquired").mkdir(parents=True)
    (data / "acquired" / "registry.json").write_text(json.dumps({
        "by_url": {},
        "series": {
            "s1": {"host": "stats.example.org", "rows": rows_s1, "last": "2026-10-01",
                   "acquired_at": "2026-10-06T08:30:00+00:00"},
            "s2": {"host": "stats.example.org", "rows": 500, "last": "2026-10-01",
                   "acquired_at": "2026-10-06T08:30:00+00:00"}}}), "utf-8")
    (data / "feature_genome").mkdir(parents=True)
    (data / "feature_genome" / "lineage.jsonl").write_text(
        json.dumps({"feature_id": "f_s1", "dataset_id": "s1"}) + "\n"
        + json.dumps({"feature_id": "f_s2", "dataset_id": "s2"}) + "\n", "utf-8")
    conn = sqlite3.connect(str(data / "lineage.sqlite"))
    conn.execute("CREATE TABLE lineage_artifacts (artifact_id TEXT, producer_component_id TEXT, "
                 "producer_run_id TEXT, created_at TEXT, input_artifact_ids TEXT)")
    conn.execute("INSERT INTO lineage_artifacts VALUES ('cell:c_s1', 'leg:x', 'r1', 't', "
                 "'feature:f_s1')")
    conn.commit()
    conn.close()
    (data / "catalog_routes").mkdir(parents=True)
    (data / "catalog_routes" / "roster.json").write_text(json.dumps({
        "defaults": {"min_gap_s": 2.0},
        "portals": [{"id": "p", "base": "https://stats.example.org", "route": "ckan"}]}), "utf-8")


def test_a_new_version_reaches_only_its_dependents(tmp_path):
    _tree(tmp_path)
    q = TaskQueue(tmp_path / "q.jsonl")
    first = queue_cycle._lanes(tmp_path, q)
    assert sorted(first["queued"]) == ["dataset:s1", "dataset:s2"]
    assert first["drained_information"] == 2              # drained, not left waiting
    assert first["lineage_rows"] == 3
    strat = [t for t in q.tasks().values() if t.lane == STRATEGY]
    by_cause: dict[str, set[str]] = {}
    for t in strat:
        by_cause.setdefault(t.payload["because"], set()).add(t.payload["artifact_id"])
    assert by_cause == {"dataset:s1": {"feature:f_s1", "cell:c_s1"},
                        "dataset:s2": {"feature:f_s2"}}
    assert q.rate_limits()["stats.example.org"]["per_s"] == 0.5

    # an unchanged pass queues nothing; a NEW version of s1 touches only s1's lineage
    assert queue_cycle._lanes(tmp_path, q)["queued"] == []
    _tree_dir = tmp_path / "desks" / "mt5" / "data" / "acquired" / "registry.json"
    reg = json.loads(_tree_dir.read_text("utf-8"))
    reg["series"]["s1"]["rows"] = 301
    _tree_dir.write_text(json.dumps(reg), "utf-8")
    before = {t.id for t in q.tasks().values()}
    third = queue_cycle._lanes(tmp_path, q)
    assert third["queued"] == ["dataset:s1"]
    new = [t for t in q.tasks().values() if t.id not in before and t.lane == STRATEGY]
    assert {t.payload["artifact_id"] for t in new} == {"feature:f_s1", "cell:c_s1"}
    assert third["untouched_total"] >= 1                   # f_s2 left alone and counted


def test_information_tasks_carry_the_release_time(tmp_path):
    _tree(tmp_path)
    q = TaskQueue(tmp_path / "q.jsonl")
    queue_cycle._lanes(tmp_path, q)
    info = [t for t in q.tasks().values() if t.lane == INFORMATION]
    assert info and all(t.not_before.startswith("2026-10-06T08:30") for t in info)


def test_the_lanes_producer_is_on_the_hourly_pass():
    assert "lanes" in queue_cycle.PRODUCERS and "lanes" in queue_cycle._IMPL


def test_the_lanes_sidecars_never_leave_the_box():
    ignore = (_ROOT / ".gitignore").read_text(encoding="utf-8")
    for suffix in ("links.json", "limits.json", "buckets.json"):
        assert f"desks/mt5/data/task_queue.{suffix}" in ignore


# ---------------------------------------------------------------- the strategy-lane consumers
# Auditor HOLD on #289: `invalidate` and `screen_class` had no consumer, so READY rows piled up.

def _genome_and_repr(root: Path) -> None:
    data = root / "desks" / "mt5" / "data"
    (data / "feature_genome" / "genomes.json").write_text(json.dumps({
        "n": 2, "genomes": {"f_s1": {"feature_id": "f_s1"}, "f_s2": {"feature_id": "f_s2"}}}),
        "utf-8")
    rs = data / "representations"
    rs.mkdir(parents=True)
    (rs / "f_s1.json").write_text("{}", "utf-8")
    (rs / "manifest.json").write_text(json.dumps({"n": 1, "representations": [
        {"id": "f_s1", "file": "f_s1.json"}]}), "utf-8")


def test_invalidate_tasks_are_consumed_and_drop_only_the_stale_artifacts(tmp_path):
    _tree(tmp_path)
    _genome_and_repr(tmp_path)
    data = tmp_path / "desks" / "mt5" / "data"
    # the real control-plane schema carries `valid_until`; give the fixture store it
    conn = sqlite3.connect(str(data / "lineage.sqlite"))
    conn.execute("ALTER TABLE lineage_artifacts ADD COLUMN valid_until TEXT")
    conn.execute("UPDATE lineage_artifacts SET valid_until = '2099-01-01T00:00:00+00:00'")
    conn.commit()
    conn.close()
    q = TaskQueue(tmp_path / "q.jsonl")
    queue_cycle._lanes(tmp_path, q)
    ready = [t for t in q.tasks().values() if t.kind == "invalidate" and t.state == "READY"]
    assert len(ready) == 3
    res = queue_cycle.consume(tmp_path, queue=q)
    assert res["completed"]["invalidate"] == 3 and res["ready_left"] == 0 and not res["failed"]
    assert all(t.state == "DONE" for t in q.tasks().values() if t.kind == "invalidate")
    genomes = json.loads((data / "feature_genome" / "genomes.json").read_text("utf-8"))
    assert set(genomes["genomes"]) == set()                 # both features' versions moved
    manifest = json.loads((data / "representations" / "manifest.json").read_text("utf-8"))
    assert manifest["representations"] == [] and not (data / "representations" / "f_s1.json"
                                                      ).exists()
    conn = sqlite3.connect(str(data / "lineage.sqlite"))
    (until,) = conn.execute("SELECT valid_until FROM lineage_artifacts "
                            "WHERE artifact_id = 'cell:c_s1'").fetchone()
    conn.close()
    assert until < "2099"                                   # the cell's lease ended now
    log = [json.loads(x) for x in (data / "feature_genome" / "invalidations.jsonl")
           .read_text("utf-8").splitlines()]
    assert {r["artifact_id"] for r in log} == {"feature:f_s1", "feature:f_s2", "cell:c_s1"}


def test_an_invalidation_of_an_artifact_no_store_holds_is_not_held_and_still_completes(tmp_path):
    q = TaskQueue(tmp_path / "q.jsonl")
    q.submit("invalidate", lane=STRATEGY, payload={"artifact_id": "feature:ghost",
                                                   "because": "dataset:x", "version": "v"})
    res = queue_cycle.consume(tmp_path, queue=q)
    assert res["outcomes"] == {"invalidate:NOT_HELD": 1} and res["ready_left"] == 0


def _class_registry(root: Path, rows: int, authority: bool = True) -> None:
    acq = root / "desks" / "mt5" / "data" / "acquired"
    acq.mkdir(parents=True, exist_ok=True)
    (acq / "registry.json").write_text(json.dumps({"series": {
        "bank_rate_jp": {"host": "www.boj.example.jp", "rows": rows, "pit_authority": authority},
        "unrelated": {"host": "other.example.org", "rows": 900, "pit_authority": True}}}),
        "utf-8")


def test_a_met_mission_spawns_a_class_screen_that_is_consumed(tmp_path):
    _class_registry(tmp_path, rows=500)
    q = TaskQueue(tmp_path / "q.jsonl")
    q.link("acquire_class", "screen_class")
    t = q.submit("acquire_class", lane=INFORMATION,
                 payload={"key": "information:policy_rates", "terms": "policy rate"},
                 dedupe_key="acquire_class|information:policy_rates")
    assert q.complete(t.id, produced={"source": "boj.example.jp"})
    res = queue_cycle.consume(tmp_path, queue=q)
    assert res["outcomes"] == {"screen_class:SCREENED": 1} and res["ready_left"] == 0
    screen = json.loads((tmp_path / "desks" / "mt5" / "reports" / "CLASS_SCREEN.json")
                        .read_text("utf-8"))["classes"]["information:policy_rates"]
    assert screen["vocabulary"] == ["ext_bank_rate_jp"]      # by host; `unrelated` not taken
    assert screen["screens"] == ["anomaly_miner", "family_discovered"]


def test_a_class_not_yet_eligible_is_rescreened_later_not_left_ready(tmp_path):
    _class_registry(tmp_path, rows=50)
    q = TaskQueue(tmp_path / "q.jsonl")
    q.submit("screen_class", lane=STRATEGY,
             payload={"key": "information:policy_rates", "produced": {"source": "boj.example.jp"}})
    res = queue_cycle.consume(tmp_path, queue=q)
    assert res["outcomes"] == {"screen_class:NOT_YET_ELIGIBLE": 1} and res["rearmed"] == 1
    assert res["ready_left"] == 0                           # the re-screen waits for its release
    again = [t for t in q.tasks().values() if t.kind == "screen_class" and t.state == "READY"]
    assert len(again) == 1 and again[0].not_before and again[0].payload["rearm"] == 1


def test_the_consumers_are_wired_into_the_hourly_cycle():
    src = (_ROOT / "desks" / "mt5" / "research" / "hourly_cycle.py").read_text("utf-8")
    assert 'qcons = _costed("queue_consumers", lambda: _producer(' in src
    assert '"queue_consumers", "research/queue_consumers.py"))' in src
    assert '"queue_consumers": qcons' in src and '"queue_consumers": 300' in src
    from libs.research.layers import LEG_LAYER
    assert LEG_LAYER["queue_consumers"] == "meta"
    assert set(queue_cycle.CONSUMED_KINDS) == {"invalidate", "screen_class"}


def test_every_claim_call_names_only_kinds_in_the_derived_claim_set():
    """CLAIMED_KINDS is what the no-queues fence breaches on; it must be the consumers' OWN
    claim lists. A claim call that names a literal kind (or a kind outside the set) would make
    the fence and the consumers disagree, so the claim sites are read here by AST."""
    import ast
    sources = [_ROOT / "libs" / "ops" / "queue_cycle.py",
               _ROOT / "desks" / "mt5" / "research" / "hourly_cycle.py"]
    sites = 0
    for path in sources:
        tree = ast.parse(path.read_text("utf-8"))
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            name = getattr(node.func, "attr", getattr(node.func, "id", ""))
            if name == "_claim_one" and node.args:
                sites += 1
                arg = node.args[0]
                assert not isinstance(arg, ast.Constant), f"{path.name}:{node.lineno} literal"
            elif name == "claim":
                kinds = next((k.value for k in node.keywords if k.arg == "kinds"), None)
                names = ({n.id for n in ast.walk(kinds) if isinstance(n, ast.Name)}
                         if kinds is not None else set())
                if kinds is None or (names and names <= {"kind", "kinds"}
                                     and not any(isinstance(n, ast.Constant)
                                                 for n in ast.walk(kinds))):
                    continue      # a generic helper (`_claim_one`'s body): its callers are checked
                sites += 1
                assert not any(isinstance(n, ast.Constant) for n in ast.walk(kinds)), (
                    f"{path.name}:{node.lineno}: claim names a literal kind")
                assert isinstance(kinds, ast.Name) and kinds.id in (
                    "CONSUMED_KINDS", "LANES_CLAIMS", "RECERTIFY_CLAIMS"), ast.dump(kinds)
    assert sites >= 3
    derived = frozenset((*queue_cycle.RECERTIFY_CLAIMS, *queue_cycle.LANES_CLAIMS,
                         *queue_cycle.CONSUMED_KINDS))
    assert derived == queue_cycle.CLAIMED_KINDS


def test_queue_json_lists_unconsumed_kinds(tmp_path):
    q = TaskQueue(tmp_path / "q.jsonl")
    q.submit("wire", payload={})
    doc = queue_cycle.run(tmp_path, queue=q)
    assert [r["kind"] for r in doc["unconsumed_kinds"]] == ["wire"]
    assert "invalidate" in doc["claimed_kinds"]


# ------------------------------------------ every submitted kind is consumed or declared (#289)

def _dynamic_sites():
    """Submit sites whose kind is computed: (file, enclosing function) -> the kinds it can
    produce. Each list is derived from the source of the values, never typed as a promise."""
    from libs.ops import wiring_campaign as WC
    from libs.ops.org import DESK_ROLES, ESCALATION_KIND, HUMAN_INBOX
    return {
        # forwards its caller's kind; every delegate() caller is a checked site below
        ("libs/ops/org.py", "delegate"): (),
        ("libs/ops/org.py", "escalate"): (HUMAN_INBOX, *{
            f"{ESCALATION_KIND}:{r.escalates_to}" for r in DESK_ROLES if r.escalates_to}),
        # the strategy kind of a link(); every link() caller is a checked site below
        ("libs/ops/task_queue.py", "_spawn"): (),
        # `kind` defaults to "invalidate" and no production caller overrides it
        ("libs/ops/task_queue.py", "invalidate"): ("invalidate",),
        # a subscribe() task_kind; the test asserts no production code subscribes
        ("libs/ops/task_queue.py", "drain_events"): (),
        ("libs/ops/wiring_campaign.py", "enqueue"): (WC.WIRE_KIND, WC.RETIRE_KIND),
    }


def _const_str(node, strings, imported):
    import ast
    import importlib
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    if isinstance(node, ast.Name):
        if node.id in strings:
            return strings[node.id]
        if node.id in imported:
            mod, name = imported[node.id]
            val = getattr(importlib.import_module(mod), name, None)
            return val if isinstance(val, str) else None
    return None


def test_every_submitted_kind_is_claimed_or_declared_consumer_less():
    """AUDITOR MUST on #289: a kind a producer submits that no consumer claims and nobody
    declared consumer-less is a queue. Every production submit / delegate / link site in a file
    that touches the task queue is read by AST; its kind must be in CLAIMED_KINDS |
    NO_CONSUMER_KINDS, and a computed kind must sit at a declared dynamic site whose possible
    kinds are themselves in that set."""
    import ast
    import subprocess
    allowed = set(queue_cycle.CLAIMED_KINDS) | set(queue_cycle.NO_CONSUMER_KINDS)
    dynamic = _dynamic_sites()
    files = subprocess.run(
        ["git", "grep", "-l", "-E", r"task_queue|desk_org|TaskQueue", "--", "libs/*.py",
         "desks/mt5/*.py", "scripts/*.py"], cwd=_ROOT, capture_output=True, text=True,
        check=True).stdout.split()
    files = [f for f in files if "/tests/" not in f and "/_retired/" not in f
             and not f.rsplit("/", 1)[-1].startswith("test_")]
    seen: dict[str, str] = {}
    for rel in files:
        tree = ast.parse((_ROOT / rel).read_text("utf-8"))
        strings = {t.id: n.value.value for n in tree.body if isinstance(n, ast.Assign)
                   and isinstance(n.value, ast.Constant) and isinstance(n.value.value, str)
                   for t in n.targets if isinstance(t, ast.Name)}
        imported = {a.asname or a.name: (n.module, a.name) for n in ast.walk(tree)
                    if isinstance(n, ast.ImportFrom) and n.module and n.level == 0
                    for a in n.names}
        funcs = {n.name for n in ast.walk(tree)
                 if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))}
        parent = {c: p for p in ast.walk(tree) for c in ast.iter_child_nodes(p)}
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Attribute):
                continue
            if node.func.attr == "subscribe" and "task_queue.py" not in rel:
                raise AssertionError(f"{rel}:{node.lineno}: a production subscribe() -- its "
                                     f"task_kind must be added to this test's checked sites")
            if node.func.attr == "invalidate":
                for kw in node.keywords:
                    if kw.arg == "kind":
                        k = _const_str(kw.value, strings, imported)
                        assert k is not None, f"{rel}:{node.lineno}: computed invalidate kind"
                        seen[k] = f"{rel}:{node.lineno}"
            pos = {"submit": 0, "delegate": 1, "link": 1}.get(node.func.attr)
            if pos is None or len(node.args) <= pos:
                continue
            arg = node.args[pos]
            if node.func.attr == "submit" and (
                    isinstance(arg, (ast.Lambda, ast.Attribute))
                    or (isinstance(arg, ast.Name) and arg.id in funcs)):
                continue                          # an executor's pool.submit(fn, ...)
            kind = _const_str(arg, strings, imported)
            if kind is not None:
                seen[kind] = f"{rel}:{node.lineno}"
                continue
            fn = node
            while fn in parent and not isinstance(fn, (ast.FunctionDef, ast.AsyncFunctionDef)):
                fn = parent[fn]
            site = (rel, getattr(fn, "name", "<module>"))
            if node.func.attr == "submit" and site not in dynamic and not (
                    isinstance(arg, ast.Name) and arg.id in ("kind", "k", "task_kind")):
                continue                          # pool.submit(worker) in a queue-aware file
            assert site in dynamic, f"{rel}:{node.lineno}: computed kind at an undeclared site"
            for k in dynamic[site]:
                seen[k] = f"{rel}:{node.lineno} (dynamic)"
    stray = {k: where for k, where in seen.items() if k not in allowed}
    assert stray == {}, f"kinds with no consumer and no declared reason: {stray}"
    assert {"recertify", "acquire_class", "screen_class", "wire", "generate",
            "ingest_version", "invalidate"} <= set(seen)
    assert all(queue_cycle.NO_CONSUMER_KINDS.values())
    assert not set(queue_cycle.NO_CONSUMER_KINDS) & set(queue_cycle.CLAIMED_KINDS)


def test_screen_min_rows_is_the_acquirers_min_rows():
    import importlib
    ad = importlib.import_module("desks.mt5.research.acquire_datasets")
    assert queue_cycle.SCREEN_MIN_ROWS == ad.MIN_ROWS


def test_class_terms_are_matched_literally_never_compiled(tmp_path, monkeypatch):
    """AUDITOR SHOULD on #289: the payload's terms were compiled as a regex. They are now word
    sequences: the class's own `\\bpolicy\\W+rate\\b` form still matches, and a pathological
    pattern is inert data -- re.compile is never called on it."""
    assert queue_cycle.class_terms(r"\bpolicy\W+rate\b|bank\W+rate") == (
        ("policy", "rate"), ("bank", "rate"))
    assert queue_cycle._names_term("jp_policy_rate_1m", queue_cycle.class_terms(
        r"\bpolicy\W+rate\b"))
    assert not queue_cycle._names_term("policy_x_rate", queue_cycle.class_terms(
        r"\bpolicy\W+rate\b"))
    _class_registry(tmp_path, rows=500)
    import re as _re
    compiled = []
    real = _re.compile
    monkeypatch.setattr(queue_cycle.re, "compile",
                        lambda *a, **k: compiled.append(a) or real(*a, **k))
    res = queue_cycle.screen_class(tmp_path, {"key": "k", "terms": "(a+)+$" + "|bank_rate"})
    assert compiled == [] and res["outcome"] == "SCREENED"
    assert [r["series"] for r in res["series"]] == ["bank_rate_jp"]


def test_a_failed_consume_backs_off_before_its_next_attempt(tmp_path):
    """AUDITOR SHOULD on #289: a failure went straight back to READY, so one drain pass could
    spend all three attempts on one transient fault and send the task DEAD. It now waits 1 h,
    then 4 h, before its next attempt."""
    from datetime import UTC, datetime, timedelta
    q = TaskQueue(tmp_path / "q.jsonl")
    t = q.submit("invalidate", lane=STRATEGY, payload={})          # no artifact_id: fails
    now = datetime(2026, 10, 13, 12, tzinfo=UTC)
    res = queue_cycle.consume(tmp_path, queue=q, now=now)
    assert res["claimed"] == 1 and len(res["failed"]) == 1          # ONE attempt this pass
    got = q.tasks()[t.id]
    assert got.state == "READY" and got.attempts == 1
    assert datetime.fromisoformat(got.not_before) >= now + timedelta(hours=1) - timedelta(
        seconds=1)
    assert queue_cycle.retry_backoff(1) == timedelta(hours=1)
    assert queue_cycle.retry_backoff(2) == timedelta(hours=4)
