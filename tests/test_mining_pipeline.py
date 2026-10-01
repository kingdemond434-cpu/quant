"""MT5_GLOBAL_MINING_V1 acceptance tests, plus the pipeline's end-to-end wiring.

The seven named in the spec come first; the rest pin the pieces they depend on (fetcher parsers,
the roster's intake of other lanes' rows, stage-skipping, translations, compile-stage kills and
the metrics contract).
"""
from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import sys
import textwrap
import time
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest

from libs.mining import acquirer as acq
from libs.mining import dedup, extractor, prereg, rejection
from libs.mining.pit_store import PitStore, RawRecord, iso
from libs.mining.registry import Cell, CellRegistry, IllegalTransitionError

ROOT = Path(__file__).resolve().parents[1]
T0 = datetime(2026, 9, 30, 12, 0, tzinfo=UTC)


def _supervisor() -> Any:
    path = ROOT / "desks" / "mt5" / "research" / "mining_supervisor.py"
    spec = importlib.util.spec_from_file_location("mining_supervisor_under_test", path)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


MS = _supervisor()

EA_RSI = ("input int RSI_Period = 14;\ninput int RSI_Oversold = 25;\n"
          "input int RSI_Overbought = 75;\nint h = iRSI(_Symbol, PERIOD_H1, RSI_Period, 0);\n")
EA_RSI_RENAMED = ("// Совершенно другое имя: Oscillator Bounce Pro\n"
                  "input int rsi_len_period = 14;\ninput int rsi_buy_low = 25;\n"
                  "input int rsi_sell_high = 75;\ndouble x = iRSI(NULL, PERIOD_H1, 14, 0);\n")


def _cell(cid: str = "mc_x", status: str = "TESTABLE", **kw: Any) -> Cell:
    base: dict[str, Any] = {
        "cell_id": cid, "source_id": "s", "source_uri": "u", "source_version": "v1",
        "content_hash": "h", "publication_time": None, "acquisition_time": iso(T0),
        "available_for_decision_at": iso(T0), "original_language": "en",
        "translation_provenance": "original", "mechanism_family": "reversion",
        "mechanism_subtype": "rsi_reversion", "status": status}
    base.update(kw)
    return Cell(**base)


def _pipe(tmp: Path, sources: list[acq.Source] | None = None, **hook_kw: Any) -> Any:
    donated: list[dict[str, Any]] = []

    def donate(rows: list[dict[str, Any]]) -> tuple[bool, str]:
        donated.extend(rows)
        return True, json.dumps({"donated": len(rows)})
    hooks = MS.Hooks(universe={"EURUSD", "XAUUSD", "GBPUSD", "USDJPY"}, donate=donate,
                     **hook_kw)
    roster = sources if sources is not None else [
        acq.Source(id="codebase", fetcher="external_feed", kind="code", priority=1,
                   uses=["direct_cells", "indirect_cells"]),
        acq.Source(id="forum_ru", fetcher="external_feed", kind="text", priority=1,
                   uses=["direct_cells", "indirect_cells"]),
        acq.Source(id="cold_source", fetcher="rss", kind="text", priority=2,
                   uses=["direct_cells", "indirect_cells"])]
    pipe = MS.Pipeline(tmp / "mining", tmp / "reports", roster=roster, hooks=hooks,
                       gate_ledger=tmp / "gate_verdict_ledger.jsonl", root=tmp)
    pipe._donated = donated
    return pipe


def _put(pipe: Any, source_id: str, uri: str, body: str, *, kind: str = "code",
         title: str = "", lang: str = "en", now: datetime = T0) -> str:
    res = pipe.store.put(RawRecord(source_id=source_id, source_uri=uri, body=body,
                                   title=title, acquisition_time=iso(now),
                                   original_language=lang, meta={"kind": kind}), now=now)
    return str(res.record_id)


# =============================================================== the seven acceptance tests
def test_pit_invisible_future(tmp_path: Path) -> None:
    store = PitStore(tmp_path / "m.db")
    past = RawRecord(source_id="broker", source_uri="https://b/specs", body="swap long -3.1",
                     acquisition_time=iso(T0 - timedelta(days=2)))
    store.put(past, now=T0 - timedelta(days=2))
    # A planted observation dated a week in the future, fetched now.
    future = RawRecord(source_id="broker", source_uri="https://b/future", body="swap long -9",
                       publication_time=iso(T0 + timedelta(days=7)), acquisition_time=iso(T0),
                       immutable_time=True)
    res = store.put(future, now=T0)
    assert "future_dated" in res.flags
    seen_now = {r["source_uri"] for r in store.as_of(T0)}
    assert "https://b/specs" in seen_now
    assert "https://b/future" not in seen_now, "a future-dated record leaked into the past"
    assert "https://b/future" in {r["source_uri"] for r in store.as_of(T0 + timedelta(days=8))}
    # A revision is visible only from its own acquisition, never backdated.
    store.put(RawRecord(source_id="broker", source_uri="https://b/specs", body="swap long -4.0",
                        acquisition_time=iso(T0)), now=T0)
    before = store.as_of(T0 - timedelta(hours=1), source_uri="https://b/specs")
    after = store.as_of(T0, source_uri="https://b/specs")
    assert [r["body"] for r in before] == ["swap long -3.1"]
    assert [r["body"] for r in after] == ["swap long -4.0"]


def test_prereg_immutable(tmp_path: Path) -> None:
    ps = prereg.PreregStore(tmp_path / "preregistrations")
    contract = {"cell_id": "mc_a", "spec": {"sym": "EURUSD", "family": "mean_reversion_rsi",
                                            "params": {"rsi_n": 14}, "timeframe": "H1"},
                "falsifier": "H0: mean <= 0", "trial_family_id": "tf_1"}
    sha = ps.seal(contract, now=T0)
    assert ps.seal(contract, now=T0 + timedelta(hours=1)) == sha      # idempotent re-seal
    with pytest.raises(prereg.PreregMutationError):
        ps.seal({**contract, "spec": {**contract["spec"], "params": {"rsi_n": 7}}})
    # Mutation on disk after the seal: load must refuse it.
    p = ps.path("mc_a")
    os.chmod(p, 0o644)
    doc = json.loads(p.read_text("utf-8"))
    doc["contract"]["spec"]["params"]["rsi_n"] = 2
    p.write_text(json.dumps(doc), "utf-8")
    with pytest.raises(prereg.PreregMutationError):
        ps.load("mc_a")
    ok, why = ps.verify("mc_a", contract["spec"])
    assert not ok and "mutated" in why


def test_trial_lineage(tmp_path: Path) -> None:
    ps = prereg.PreregStore(tmp_path / "p")
    tf = prereg.trial_family_id("reversion", "rsi_reversion", "mean_reversion_rsi")
    ps.seal({"cell_id": "mc_parent", "spec": {"sym": "EURUSD", "family": "mean_reversion_rsi",
                                             "params": {"rsi_n": 14}, "timeframe": "H1"},
             "falsifier": "f", "trial_family_id": tf})
    child_id, _ = ps.amend("mc_parent", {"spec": {"sym": "EURUSD",
                                                  "family": "mean_reversion_rsi",
                                                  "params": {"rsi_n": 21}, "timeframe": "H1"}},
                           new_cell_id="mc_child")
    child = ps.load(child_id)
    assert child["parent_cell_id"] == "mc_parent"
    assert child["trial_family_id"] == tf
    grandchild_id, _ = ps.amend(child_id, {"trial_family_id": "tf_other"},
                                new_cell_id="mc_grandchild")
    assert ps.load(grandchild_id)["trial_family_id"] == tf, "a descendant left its family"
    # Through the pipeline: an EA naming no instrument transfers to two symbols, one family.
    pipe = _pipe(tmp_path)
    _put(pipe, "codebase", "https://mql5/code/1", EA_RSI.replace("PERIOD_H1", "PERIOD_H1"))
    pipe.process(now=T0)
    q = pipe.cells.by_status("QUEUED")
    direct = [c for c in q if c.use == "direct_cells"]
    assert len(direct) == 2
    assert len({c.trial_family_id for c in q}) == 1, "transfers and regime children left the family"
    parent = [c for c in direct if not c.parent_cell_id]
    kids = [c for c in direct if c.parent_cell_id]
    assert len(parent) == 1 and len(kids) == 1 and kids[0].parent_cell_id == parent[0].cell_id
    indirect = [c for c in q if c.use == "indirect_cells"]
    assert indirect and all(c.parent_cell_id in {d.cell_id for d in direct} for c in indirect)


def test_duplicate_mechanism_rejected(tmp_path: Path) -> None:
    pipe = _pipe(tmp_path)
    _put(pipe, "codebase", "https://mql5/code/1", EA_RSI, title="RSI Reversal EA EURUSD")
    _put(pipe, "forum_ru", "https://mql5/ru/forum/2", EA_RSI_RENAMED,
         title="Oscillator Bounce Pro EURUSD", lang="ru", kind="code")
    pipe.process(now=T0)
    dups = pipe.cells.by_status("BLOCKED_DUPLICATE_MECHANISM")
    assert dups, "same mechanism under a different name and language was not folded"
    assert all(c.rejection_reason == "DUPLICATE_MECHANISM" for c in dups)
    owners = {c.cell_id for c in pipe.cells.by_status("QUEUED")}
    assert all(c.duplicate_of in owners for c in dups)
    rows = [r for r in pipe.ledger.rows() if r["reason"] == "DUPLICATE_MECHANISM"]
    assert {r["subject_id"] for r in rows} == {c.cell_id for c in dups}
    # Surface text never enters the hash.
    a = dedup.mechanism_hash(mechanism_family="reversion",
                             spec={"sym": "EURUSD", "family": "mean_reversion_rsi",
                                   "params": {"rsi_n": 14, "name": "A"}, "timeframe": "H1"})
    b = dedup.mechanism_hash(mechanism_family="REVERSION",
                             spec={"sym": "eurusd", "family": "mean_reversion_rsi",
                                   "params": {"rsi_n": "14.0", "label": "B"}})
    assert a == b


def test_cursor_resume(tmp_path: Path) -> None:
    """Kill the acquirer mid-batch with SIGKILL, restart it, and lose and double nothing."""
    script = tmp_path / "run_acquire.py"
    script.write_text(textwrap.dedent(f"""
        import sys, time
        sys.path.insert(0, {str(ROOT)!r})
        from pathlib import Path
        from libs.mining import acquirer as acq
        from libs.mining.pit_store import PitStore
        DELAY = float(sys.argv[1])

        def slow(src, cursor, ctx):
            start = int(cursor.get("next", 0))
            for i in range(start, 20):
                time.sleep(DELAY)
                yield acq.Item(uri=f"https://src/item/{{i}}", body=f"body {{i}}",
                               cursor_update={{"next": i + 1}})
        acq.FETCHERS["slow"] = slow
        src = acq.Source(id="slow_src", fetcher="slow", cadence_minutes=1)
        store = PitStore(Path({str(tmp_path)!r}) / "m.db")
        cursors = acq.CursorStore(Path({str(tmp_path)!r}) / "cursors")
        ctx = acq.FetchContext(http_get=lambda u, h: acq.HttpResult(200, ""),
                               deadline=time.monotonic() + 60, max_items=1000)
        rep = acq.acquire(src, store, cursors, ctx, force=True)
        print(rep.outcome, rep.fetched, rep.new)
    """), "utf-8")
    proc = subprocess.Popen([sys.executable, str(script), "0.15"], stdout=subprocess.DEVNULL,
                            stderr=subprocess.DEVNULL)
    store = PitStore(tmp_path / "m.db")
    deadline = time.monotonic() + 30
    while time.monotonic() < deadline and store.count() < 6:
        time.sleep(0.05)
    proc.kill()
    proc.wait(timeout=10)
    mid = store.count()
    assert 6 <= mid < 20, f"kill did not land mid-batch ({mid} stored)"
    cursor = acq.CursorStore(tmp_path / "cursors").get("slow_src")
    assert int(cursor.get("next", 0)) in (mid, mid - 1), "cursor not durable per record"
    out = subprocess.run([sys.executable, str(script), "0"], capture_output=True, text=True,
                         timeout=60, check=True)
    assert out.stdout.split()[0] == "ok"
    uris = [r["source_uri"] for r in store.as_of(T0 + timedelta(days=3650))]
    assert sorted(uris) == sorted(f"https://src/item/{i}" for i in range(20)), \
        "records lost or doubled across the kill"
    assert store.state_counts()["ACQUIRED"] == 20        # every record has a state


def test_rejection_reasons_logged(tmp_path: Path) -> None:
    pipe = _pipe(tmp_path)
    _put(pipe, "codebase", "https://mql5/code/1", EA_RSI, title="RSI EA")
    _put(pipe, "forum_ru", "https://x/2", EA_RSI_RENAMED, kind="code", title="EURUSD")
    _put(pipe, "forum_ru", "https://x/3", "Hello, I am new here. Nice weather today.",
         kind="text")
    _put(pipe, "codebase", "https://mql5/code/4",
         "double z = iCustom(NULL,0,\"ZigZag\",12,5,3); if (z > 0) OrderSend(); iRSI(NULL,0,14,0)",
         title="ZigZag EA")
    pipe.process(now=T0)
    pipe.donate(now=T0)
    q = pipe.cells.by_status("EVALUATING")
    ledger = tmp_path / "gate_verdict_ledger.jsonl"
    with ledger.open("a", encoding="utf-8") as fh:
        for i, c in enumerate(q):
            gate = ["stress_costs", "walk_forward"][i % 2]
            fh.write(json.dumps({"at": iso(T0), "cell": c.gauntlet_cell, "passed": False,
                                 "terminal_gate": gate}) + "\n")
    assert pipe.join_verdicts(now=T0) == len(q) > 0
    rejected = [c for c in pipe.cells.all_cells() if c.rejection_reason]
    assert rejected
    for c in rejected:
        assert c.rejection_reason in rejection.REASON_CODES
        assert c.rejection_stage in rejection.STAGES
    codes = {c.rejection_reason for c in rejected}
    assert {"DUPLICATE_MECHANISM", "LEAKAGE_LOOKAHEAD", "COST_EXCEEDS_EDGE",
            "REGIME_FRAGILE"} <= codes
    # the no-mechanism record is a record-level kill, also coded
    rec_kills = [r for r in pipe.ledger.rows() if r["subject_kind"] == "record"]
    assert [r["reason"] for r in rec_kills] == ["NO_ECONOMIC_MECHANISM"]
    with pytest.raises(rejection.UnknownReasonError):
        pipe.ledger.reject("mc_z", "BECAUSE", "gauntlet")
    # every fetched record has a state
    states = pipe.store.state_counts()
    assert states["ACQUIRED"] == 0 and sum(states.values()) == 4


def test_no_source_covered_without_consumer(tmp_path: Path) -> None:
    pipe = _pipe(tmp_path)
    _put(pipe, "codebase", "https://mql5/code/1", EA_RSI, title="RSI EA EURUSD")
    # cold_source fetched plenty, but nothing it produced was ever evaluated.
    for i in range(5):
        _put(pipe, "cold_source", f"https://cold/{i}", f"random text {i}", kind="text")
    pipe.process(now=T0)
    st = pipe.source_status(T0)
    assert st["cold_source"]["status"] == "COLD" and st["cold_source"]["records_total"] == 5
    assert st["codebase"]["status"] == "COLD", "QUEUED is not a consumer receipt"
    pipe.donate(now=T0)
    c = pipe.cells.by_status("EVALUATING")[0]
    (tmp_path / "gate_verdict_ledger.jsonl").write_text(
        json.dumps({"at": iso(T0), "cell": c.gauntlet_cell, "passed": False,
                    "terminal_gate": "deflated_sharpe"}) + "\n", "utf-8")
    pipe.join_verdicts(now=T0)
    assert pipe.source_status(T0)["codebase"]["status"] == "ACTIVE"
    assert pipe.source_status(T0)["cold_source"]["status"] == "COLD"
    # ...and the receipt expires after 30 days.
    assert pipe.source_status(T0 + timedelta(days=31))["codebase"]["status"] == "COLD"


# ================================================================= pipeline wiring
def test_end_to_end_trace_and_metrics(tmp_path: Path) -> None:
    pipe = _pipe(tmp_path)
    _put(pipe, "codebase", "https://www.mql5.com/en/code/123", EA_RSI + "// EURUSD only",
         title="RSI EA for EURUSD")
    m0 = pipe.run_pass(60, fetch=False, now=T0)
    assert m0["trace"]["stage_reached"] == "EVALUATING"
    evaluating = pipe.cells.by_status("EVALUATING")
    c = next(x for x in evaluating if x.use == "direct_cells")
    rows = [{"at": iso(T0), "cell": x.gauntlet_cell, "passed": x.cell_id == c.cell_id,
             "terminal_gate": "PASSED" if x.cell_id == c.cell_id else "walk_forward"}
            for x in evaluating]
    (tmp_path / "gate_verdict_ledger.jsonl").write_text(
        "".join(json.dumps(r) + "\n" for r in rows), "utf-8")
    m = pipe.run_pass(60, fetch=False, now=T0 + timedelta(hours=1))
    tr = m["trace"]
    assert tr["complete"]
    assert tr["source_uri"] == "https://www.mql5.com/en/code/123"
    assert tr["preregistration_sha256"] == pipe.prereg.sha(tr["cell_id"])
    for k in ("sources_active", "sources_total", "cells_acquired_24h", "cells_compiled_24h",
              "cells_preregistered_24h", "cells_evaluated_24h", "cells_rejected_24h",
              "cells_rejected_24h_by_reason", "cells_survived_24h", "rejection_rate",
              "median_time_source_to_evaluation_hours", "queue_age_p95_days",
              "binding_constraint"):
        assert k in m, k
    n = len(evaluating)
    assert m["cells_survived_24h"] == 1 and m["cells_evaluated_24h"] == n
    assert m["rejection_rate"] == round((n - 1) / n, 4)
    assert any("too loose" in w for w in m["warnings"])
    by_use = m["cells_by_use_24h"]
    assert by_use["direct_cells"]["created"] == 1 and by_use["indirect_cells"]["created"] >= 2
    assert by_use["direct_cells"]["survived"] == 1
    assert set(by_use) == {"direct_cells", "indirect_cells", "allocation_intel"}
    assert any("degraded" in w for w in m["warnings"])
    assert (tmp_path / "reports" / f"metrics_{T0 + timedelta(hours=1):%Y-%m-%d}.json").exists()
    donated = pipe._donated[0]
    assert donated["preregistration_id"] and donated["mechanism_status"] == "NAMED"
    assert donated["available_time"]


def test_verdict_against_mutated_contract_fails_prereg(tmp_path: Path) -> None:
    pipe = _pipe(tmp_path)
    _put(pipe, "codebase", "https://mql5/code/1", EA_RSI + "// EURUSD", title="EURUSD")
    pipe.process(now=T0)
    pipe.donate(now=T0)
    c = pipe.cells.by_status("EVALUATING")[0]
    p = pipe.prereg.path(c.cell_id)
    os.chmod(p, 0o644)
    doc = json.loads(p.read_text("utf-8"))
    doc["contract"]["falsifier"] = "changed after evaluation started"
    p.write_text(json.dumps(doc), "utf-8")
    (tmp_path / "gate_verdict_ledger.jsonl").write_text(
        json.dumps({"cell": c.gauntlet_cell, "passed": True, "terminal_gate": "PASSED"}) + "\n",
        "utf-8")
    pipe.join_verdicts(now=T0)
    got = pipe.cells.get(c.cell_id)
    assert got is not None and got.rejection_reason == "FAILS_PREREG"


def test_no_stage_can_be_skipped(tmp_path: Path) -> None:
    reg = CellRegistry(tmp_path / "r.db")
    reg.add(_cell("mc_1"), stage="compile", now=T0)
    with pytest.raises(IllegalTransitionError):
        reg.transition("mc_1", "EVALUATED", stage="gauntlet")
    with pytest.raises(IllegalTransitionError):
        reg.transition("mc_1", "EVALUATING", stage="gauntlet")
    with pytest.raises(IllegalTransitionError):
        reg.add(_cell("mc_2", status="EVALUATED"), stage="gauntlet")
    reg.transition("mc_1", "QUEUED", stage="preregister")
    reg.transition("mc_1", "EVALUATING", stage="gauntlet")
    reg.transition("mc_1", "EVALUATED", stage="gauntlet")
    with pytest.raises(IllegalTransitionError):
        reg.transition("mc_1", "QUEUED", stage="preregister")


def test_translation_is_not_an_independent_cell(tmp_path: Path) -> None:
    pipe = _pipe(tmp_path)
    en = "On EURUSD, when RSI(14) drops below 25 buy and hold until RSI above 75."
    ru = "На EURUSD, когда RSI(14) ниже 25 покупаем и держим, пока RSI выше 75."  # noqa: RUF001
    _put(pipe, "forum_ru", "https://f/en", en, kind="text", lang="en")
    _put(pipe, "forum_ru", "https://f/ru", ru, kind="text", lang="ru")
    pipe.process(now=T0)
    queued = pipe.cells.by_status("QUEUED")
    assert len([c for c in queued if c.use == "direct_cells"]) == 1
    dups = pipe.cells.by_status("BLOCKED_DUPLICATE_MECHANISM")
    assert len(dups) == len(queued), "every cell of the translation folds onto the original"


def test_prior_art_in_the_gauntlet_is_a_duplicate(tmp_path: Path) -> None:
    pipe = _pipe(tmp_path, prior_verdict=lambda g: "deflated_sharpe|0")
    _put(pipe, "codebase", "https://mql5/code/1", EA_RSI + "// EURUSD", title="EURUSD")
    pipe.process(now=T0)
    assert not pipe.cells.by_status("QUEUED")
    d = pipe.cells.by_status("BLOCKED_DUPLICATE_MECHANISM")
    assert d and d[0].duplicate_of.startswith("gauntlet:")


def test_backdated_revision_is_leakage(tmp_path: Path) -> None:
    store = PitStore(tmp_path / "m.db")
    pub = iso(T0 - timedelta(days=30))
    store.put(RawRecord(source_id="gh", source_uri="https://gh/r", body="v1",
                        publication_time=pub, immutable_time=True,
                        acquisition_time=iso(T0 - timedelta(days=1))), now=T0 - timedelta(days=1))
    res = store.put(RawRecord(source_id="gh", source_uri="https://gh/r", body="v2 edited",
                              publication_time=pub, immutable_time=True,
                              acquisition_time=iso(T0)), now=T0)
    assert "backdated_revision" in res.flags
    rec = store.get(res.record_id)
    assert rec and rec["state"] == "REJECTED" and rec["state_reason"] == "LEAKAGE_REVISION"
    # The source's clock is no longer trusted: its next record is stamped at acquisition.
    nxt = store.put(RawRecord(source_id="gh", source_uri="https://gh/other", body="x",
                              publication_time=pub, immutable_time=True,
                              acquisition_time=iso(T0)), now=T0)
    assert store.get(nxt.record_id)["available_for_decision_at"] == iso(T0)


def test_mechanics_pages_feed_risk_with_change_detection(tmp_path: Path) -> None:
    src = acq.Source(id="prop_rules", fetcher="page_snapshot", kind="mechanics",
                     feeds=["risk_model"])
    pipe = _pipe(tmp_path, sources=[src])
    pipe.store.put(RawRecord(source_id="prop_rules", source_uri="https://e8/rules",
                             body="Maximum daily loss 5%. Max drawdown 8%. Profit target 12%.",
                             acquisition_time=iso(T0 - timedelta(days=1)),
                             meta={"kind": "mechanics"}), now=T0 - timedelta(days=1))
    pipe.process(now=T0)
    pipe.store.put(RawRecord(source_id="prop_rules", source_uri="https://e8/rules",
                             body="Maximum daily loss 4%. Max drawdown 8%. Profit target 12%.",
                             acquisition_time=iso(T0), meta={"kind": "mechanics"}), now=T0)
    pipe.process(now=T0)
    rows = [json.loads(x) for x in pipe.feed.read_text("utf-8").splitlines()]
    assert rows[0]["facts"]["max_daily_loss_pct"] == 5.0
    assert rows[1]["changed_fields"] == ["max_daily_loss_pct"] and rows[1]["vintage"] == 1
    assert rows[1]["feeds_to"] == ["risk_model"]
    assert pipe.store.state_counts()["FEED_PUBLISHED"] == 2


def test_claims_nothing_compiles_are_handed_to_deepening(tmp_path: Path) -> None:
    tasks: list[dict[str, Any]] = []

    def handoff(t: list[dict[str, Any]]) -> int:
        tasks.extend(t)
        return len(t)
    pipe = _pipe(tmp_path, handoff=handoff)
    _put(pipe, "forum_ru", "https://f/1",
         "XAUUSD tends to rally for 3 days after a Fed rate cut.", kind="text")
    pipe.process(now=T0)
    assert pipe.cells.by_status("RESEARCH_ONLY")
    assert pipe.handoff_deepening() == 1
    assert tasks[0]["kind"] == "story_mechanism" and tasks[0]["source"] == "global_mining"


# ================================================================= roster and fetchers
def test_roster_loads_and_ingests_other_lanes_rows(tmp_path: Path) -> None:
    roster = acq.load_roster(root=ROOT)
    ids = {s.id for s in roster}
    assert len(ids) == len(roster) >= 40
    for s in roster:
        assert s.fetcher in acq.FETCHERS, (s.id, s.fetcher)
        assert s.kind in extractor.KINDS
        assert s.auth in acq.AUTH_KINDS
    prios = {s.priority for s in roster}
    assert {1, 2, 3, 4, 5} <= prios
    # another lane's rows, as they are
    ext = tmp_path / "desks" / "mt5" / "data" / "source_rosters"
    ext.mkdir(parents=True)
    (ext / "breadth.jsonl").write_text("\n".join(json.dumps(r) for r in [
        {"source_id": "edinet", "cadence_s": 3600, "auth": "keyless", "license": "public",
         "lang": "ja", "region": "jp", "url": "https://disclosure.edinet-fsa.go.jp/"},
        {"id": "mql5_codebase_en", "cadence": "daily"},          # cannot redefine ours
        {"id": "wind", "cadence": "hourly", "auth": "paid", "auth_env": "WIND_KEY"},
    ]), "utf-8")
    roster_file = tmp_path / "libs" / "mining" / "sources.yaml"
    roster_file.parent.mkdir(parents=True)
    roster_file.write_text((ROOT / "libs" / "mining" / "sources.yaml").read_text("utf-8"),
                           "utf-8")
    got = {s.id: s for s in acq.load_roster(roster_file, root=tmp_path)}
    assert got["edinet"].cadence_minutes == 60 and got["edinet"].auth == "none"
    assert got["edinet"].language == "ja" and got["edinet"].licence == "public"
    assert got["mql5_codebase_en"].origin.endswith("sources.yaml")
    assert got["wind"].auth == "key" and got["wind"].cadence_minutes == 60
    assert acq.auth_missing(got["wind"])


def _fake_http(pages: dict[str, str]) -> acq.HttpGet:
    def get(url: str, headers: Any) -> acq.HttpResult:
        if url in pages:
            return acq.HttpResult(200, pages[url])
        return acq.HttpResult(404, "", "HTTP 404")
    return get


def test_html_listing_walks_the_index_and_resumes(tmp_path: Path) -> None:
    src = acq.Source(id="cb", fetcher="html_listing", kind="code", config={
        "listing": [{"url": "https://m/code/page{page}", "page1": "https://m/code"}],
        "item_regex": r"/code/\d+$", "pages_per_run": 1})
    pages = {
        "https://m/code": '<a href="/code/1">a</a><a href="/code/2">b</a>',
        "https://m/code/page2": '<a href="/code/3">c</a>',
        "https://m/code/1": "<title>EA one</title><p>iRSI(NULL,PERIOD_H1,14,0)</p>",
        "https://m/code/2": "<title>EA two</title><p>text</p>",
        "https://m/code/3": "<title>EA three</title><p>more</p>",
    }
    store = PitStore(tmp_path / "m.db")
    cursors = acq.CursorStore(tmp_path / "c")
    ctx = acq.FetchContext(http_get=_fake_http(pages), deadline=time.monotonic() + 30, now=T0)
    rep = acq.acquire(src, store, cursors, ctx, force=True)
    assert rep.outcome == "ok" and rep.new == 3
    cur = cursors.get("cb")
    assert cur["page"]["0"] == 3 and len(cur["seen"]) == 3
    rep2 = acq.acquire(src, store, cursors, acq.FetchContext(
        http_get=_fake_http(pages), deadline=time.monotonic() + 30, now=T0), force=True)
    assert rep2.new == 0
    assert cursors.get("cb")["page"]["0"] == 2, "walked off the end: deep cursor wraps"


def test_fetch_outcomes_are_never_silent(tmp_path: Path) -> None:
    store = PitStore(tmp_path / "m.db")
    cursors = acq.CursorStore(tmp_path / "c")
    blocked = acq.Source(id="xq", fetcher="json_api", auth="login", auth_env="NOPE_NOT_SET")
    refused = acq.Source(id="ff", fetcher="html_listing", config={"listing": ["https://ff/x"]})
    for s in (blocked, refused):
        acq.acquire(s, store, cursors, acq.FetchContext(
            http_get=_fake_http({}), deadline=time.monotonic() + 5, now=T0), force=True)
    runs = store.last_runs()
    assert runs["xq"]["outcome"] == "BLOCKED_AUTH"
    assert runs["ff"]["outcome"] == "BLOCKED_FETCH" and "404" in runs["ff"]["detail"]


def test_reddit_telegram_and_rss_parsers(tmp_path: Path) -> None:
    reddit = json.dumps({"data": {"children": [
        {"data": {"created_utc": 1_790_000_100, "permalink": "/r/algotrading/p/2",
                  "title": "London breakout on GBPUSD", "selftext": "Asian range breakout"}},
        {"data": {"created_utc": 1_790_000_000, "permalink": "/r/algotrading/p/1",
                  "title": "hi", "selftext": ""}}]}})
    tg = ('<div data-post="fxalgo/41"><div class="tgme_widget_message_text">RSI(2) below 10 '
          'on XAUUSD</div><time datetime="2026-09-29T10:00:00+00:00"></time></div>')
    rss = ("<rss><channel><item><title>EA review</title><link>https://b/1</link>"
           "<guid>g1</guid><pubDate>Mon, 28 Sep 2026 10:00:00 GMT</pubDate>"
           "<description>Bollinger 20, 2 fade</description></item></channel></rss>")
    pages = {"https://www.reddit.com/r/algotrading/new.json?limit=100&raw_json=1": reddit,
             "https://t.me/s/fxalgo": tg, "https://b/feed": rss}
    store = PitStore(tmp_path / "m.db")
    cursors = acq.CursorStore(tmp_path / "c")
    for s in (acq.Source(id="rd", fetcher="reddit_json", immutable_time=True,
                         config={"subs": ["algotrading"]}),
              acq.Source(id="tg", fetcher="telegram_preview", config={"channels": ["fxalgo"]}),
              acq.Source(id="rs", fetcher="rss", config={"feeds": ["https://b/feed"]})):
        rep = acq.acquire(s, store, cursors, acq.FetchContext(
            http_get=_fake_http(pages), deadline=time.monotonic() + 5, now=T0), force=True)
        assert rep.outcome == "ok", (s.id, rep.detail)
    uris = {r["source_uri"] for r in store.as_of(T0)}
    assert {"https://www.reddit.com/r/algotrading/p/1", "https://www.reddit.com/r/algotrading/p/2",
            "https://t.me/fxalgo/41", "https://b/1"} <= uris
    assert cursors.get("rd")["created"]["sub:algotrading"] == 1_790_000_100
    assert cursors.get("tg")["last_id"]["fxalgo"] == 41


def test_extractor_reads_code_and_prose() -> None:
    code = extractor.read_code(
        "input int FastMA=12; input int SlowMA=26; iMA(NULL,PERIOD_H4,FastMA,0,MODE_EMA,0);"
        "iBands(NULL,PERIOD_H4,20,0,2.5,PRICE_CLOSE,MODE_UPPER,0);")
    assert code["indicators"]["ma"] == {"fast": 12, "slow": 26}
    assert code["indicators"]["bb"] == {"n": 20, "k": 2.5}
    assert code["timeframe"] == "H4"
    prose = extractor.read_text("Buy EURUSD on the H1 chart when RSI(7) drops below 20; "
                                "exit on the London close. Filter with EMA 20/50.")
    assert prose["indicators"]["rsi"]["n"] == 7 and prose["indicators"]["rsi"]["lo"] == 20
    assert prose["indicators"]["ma"] == {"fast": 20, "slow": 50}
    assert "london_close" in prose["patterns"] and prose["timeframe"] == "H1"
    facts = extractor.read_facts("Leverage up to 1:500. Swap long -6.2, swap short 1.1. "
                                 "Commission $4.5 per lot.")
    assert facts == {"leverage": 500.0, "swap_long": -6.2, "swap_short": 1.1,
                     "commission_per_lot": 4.5}


def test_every_source_declares_uses_and_useless_is_cold(tmp_path: Path) -> None:
    for s in acq.load_roster(root=ROOT):
        assert s.uses and set(s.uses) <= set(acq.USES), s.id
    srcs = [acq.Source(id="useless", fetcher="rss", uses=[]),
            acq.Source(id="alloc", fetcher="page_snapshot", kind="mechanics",
                       uses=["allocation_intel"])]
    st = _pipe(tmp_path, sources=srcs).source_status(T0)
    assert st["useless"]["status"] == "COLD" and st["useless"]["cold_reason"] == "serves no use"
    assert st["alloc"]["status"] == "COLD"
    assert st["alloc"]["cold_reason"] == "no cell EVALUATED in 30 days"


def test_regime_stated_in_text_becomes_an_indirect_cell(tmp_path: Path) -> None:
    pipe = _pipe(tmp_path)
    _put(pipe, "forum_ru", "https://f/1", "On EURUSD H1, RSI(14) below 25 is a buy, but only "
         "at month end and in high volatility.", kind="text")
    pipe.process(now=T0)
    regimes = {c.spec["params"].get("regime") for c in pipe.cells.by_status("QUEUED")
               if c.use == "indirect_cells" and c.spec}
    assert {"month_end", "high_vol"} <= regimes
    assert regimes <= {"high_vol", "low_vol", "month_end", "quarter_end"}


def test_robots_txt_is_obeyed_for_page_crawls(tmp_path: Path) -> None:
    pages = {"https://m.example/robots.txt": "User-agent: *\nDisallow: /code/viewcode\n",
             "https://m.example/code": '<a href="/code/viewcode/7">x</a><a href="/code/8">y</a>',
             "https://m.example/code/viewcode/7": "source", "https://m.example/code/8": "page"}
    src = acq.Source(id="cb", fetcher="html_listing", respect_robots=True, config={
        "listing": ["https://m.example/code"], "item_regex": r"/code/(viewcode/)?\d+$"})
    store = PitStore(tmp_path / "m.db")
    rep = acq.acquire(src, store, acq.CursorStore(tmp_path / "c"), acq.FetchContext(
        http_get=_fake_http(pages), deadline=time.monotonic() + 5, now=T0), force=True)
    assert rep.new == 1
    assert {r["source_uri"] for r in store.as_of(T0)} == {"https://m.example/code/8"}
    blocked = acq.Source(id="all", fetcher="page_snapshot", respect_robots=True,
                         config={"pages": ["https://m.example/code/viewcode/7"]})
    rep2 = acq.acquire(blocked, store, acq.CursorStore(tmp_path / "c"), acq.FetchContext(
        http_get=_fake_http(pages), deadline=time.monotonic() + 5, now=T0), force=True)
    assert rep2.outcome == "BLOCKED_ROBOTS"


def test_other_lanes_rosters_are_absorbed_as_owned_rows(tmp_path: Path) -> None:
    got = {s.id: s for s in acq.load_roster(root=ROOT)}
    asia = [s for s in got.values() if s.origin.endswith("asia_thread_sources.yaml")]
    assert asia and all(s.fetcher == "owned" and s.uses for s in asia)
    y = got.get("yahoo_upgrades")
    assert y is not None and y.cadence_minutes == 60 and y.auth == "none"
    assert y.consumer.endswith("alpha_capture.py")
    # breadth's files, in their own shapes (grounds / sources / rows)
    d = tmp_path / "desks" / "mt5" / "data"
    d.mkdir(parents=True)
    (d / "cell_emitter_sources.json").write_text(json.dumps({"grounds": [
        {"id": "vnpy_cta", "cadence": "hourly (leg cell_emitter)", "auth": "none (token used)",
         "license": "MIT", "language": "python", "region": "cn"}]}), "utf-8")
    (d / "world_factory_sources.json").write_text(json.dumps({"sources": [
        {"id": "news_event_stream", "kind": "news", "organ": "desks/mt5/research/x.py",
         "cadence": "hourly"}]}), "utf-8")
    (d / "alt_dataset_sources.json").write_text(json.dumps({"rows": [
        {"id": "alt_power_iowa", "class": "satellite", "url": "https://power"}]}), "utf-8")
    roster_file = tmp_path / "libs" / "mining" / "sources.yaml"
    roster_file.parent.mkdir(parents=True)
    roster_file.write_text((ROOT / "libs" / "mining" / "sources.yaml").read_text("utf-8"),
                           "utf-8")
    got2 = {s.id: s for s in acq.load_roster(roster_file, root=tmp_path)}
    v = got2["vnpy_cta"]
    assert v.fetcher == "owned" and v.cadence_minutes == 60 and v.auth == "none"
    assert v.licence == "MIT" and v.uses == ["direct_cells", "indirect_cells"]
    w = got2["news_event_stream"]
    assert w.kind == "text" and w.consumer == "desks/mt5/research/x.py"
    assert got2["alt_power_iowa"].uses == ["indirect_cells", "allocation_intel"]
    rep = acq.acquire(v, PitStore(tmp_path / "m.db"), acq.CursorStore(tmp_path / "c"),
                      acq.FetchContext(http_get=_fake_http({}), deadline=time.monotonic() + 5,
                                       now=T0), force=True)
    assert rep.outcome == "OWNED" and rep.fetched == 0


def test_keyed_sources_accept_the_pasted_formats(monkeypatch: pytest.MonkeyPatch) -> None:
    roster = {s.id: s for s in acq.load_roster(root=ROOT)}
    xq, kk = roster["xueqiu"], roster["kakao_public"]
    for raw, want in (("abc", "xq_a_token=abc"), ("xq_a_token=abc", "xq_a_token=abc"),
                      ("Cookie: xq_a_token=abc; u=9", "xq_a_token=abc; u=9")):
        monkeypatch.setenv(xq.auth_env, raw)
        assert acq.auth_headers(xq) == {"Cookie": want}
    for raw in ("k1", "KakaoAK k1"):
        monkeypatch.setenv(kk.auth_env, raw)
        assert acq.auth_headers(kk) == {"Authorization": "KakaoAK k1"}
    monkeypatch.delenv(kk.auth_env)
    assert acq.auth_headers(kk) == {} and acq.auth_missing(kk)


def test_json_api_sends_the_secret_and_reads_epoch_ms(tmp_path: Path,
                                                      monkeypatch: pytest.MonkeyPatch) -> None:
    src = acq.Source(id="xq", fetcher="json_api", kind="text", auth="login",
                     auth_env="XQ_TEST", config={
                         "auth_style": "cookie", "cookie_name": "xq_a_token",
                         "url": "https://x/s?q={q}&page={page}", "items_path": "list",
                         "uri_template": "https://x{target}",
                         "fields": {"target": "target", "title": "title", "body": "text",
                                    "time": "created_at"},
                         "queries": ["gold"]})
    monkeypatch.setenv("XQ_TEST", "tok")
    sent: list[Any] = []

    def get(url: str, headers: Any) -> acq.HttpResult:
        sent.append(dict(headers))
        if url.endswith("page=1"):
            return acq.HttpResult(200, json.dumps({"list": [
                {"target": "/1/2", "title": "", "text": "<p>XAUUSD RSI(14) below 30</p>",
                 "created_at": 1727700000000}]}))
        return acq.HttpResult(200, json.dumps({"list": []}))
    ctx = acq.FetchContext(http_get=get, deadline=time.monotonic() + 30, max_items=50,
                           now=T0, root=tmp_path)
    items = [i for i in acq.fetch_json_api(src, {}, ctx) if i.uri]
    assert [i.uri for i in items] == ["https://x/1/2"]
    assert items[0].publication_time == "2024-09-30T12:40:00+00:00"
    assert "RSI(14)" in items[0].body
    assert sent[0]["Cookie"] == "xq_a_token=tok"


def test_gauntlet_kills_carry_the_asia_kill_class() -> None:
    assert rejection.kill_class("deflated_sharpe") == "confident_kill"
    assert rejection.kill_class("lockbox") == "fail_closed"
    assert rejection.kill_class("economic_prior") == "screen_reject"
    assert rejection.kill_class("not_run") == "unconfident"
    assert rejection.GATE_REASON["swap_cost"] is rejection.Reason.INSUFFICIENT_SAMPLE


def test_fixture_trace_runs_the_real_sealed_gauntlet(tmp_path: Path) -> None:
    """No fabricated verdict: `external_gauntlet.build_cell` / `run_gauntlet` judge the cell."""
    m = MS.fixture_trace(tmp_path / "fx")
    tr = m["trace"]
    assert tr["complete"] and tr["source_uri"].startswith("fixture://mql5.com/")
    assert tr["preregistration_sha256"]
    assert tr["verdict"]["terminal_gate"] not in ("", "UNKNOWN", None)
    assert tr["outcome"] == "SURVIVOR" or tr["outcome"] in rejection.REASON_CODES
    # the gauntlet's own cell id IS the mining cell's sealed gauntlet_cell: the ledger row
    # carries the judged id, and a mismatch would have read FAILS_PREREG
    assert tr["outcome"] != "FAILS_PREREG"
    assert tr["verdict"]["gauntlet_cell"] == tr["gauntlet_cell"]
    ledger = [json.loads(x) for x in
              (tmp_path / "fx" / "fixture_gate_ledger.jsonl").read_text("utf-8").splitlines()]
    assert ledger and all(r["cell"] == r["judged_cell"] for r in ledger)
    digest = json.loads((tmp_path / "fx" / "mining_digest.json").read_text("utf-8"))
    ch = digest["chains"]
    assert ch and all(c["source_url"].startswith("fixture://") for c in ch)
    assert all(datetime.fromisoformat(c["prereg_sealed_at"])
               < datetime.fromisoformat(c["verdict_at"]) for c in ch)
    assert digest["metrics"]["docket_cells_judged_24h"] == len(ch)


def test_join_follows_the_docket_axis_expansion(tmp_path: Path) -> None:
    donated: list[dict[str, Any]] = []
    pipe = _pipe(tmp_path)
    pipe.hooks.donate = lambda rows: (donated.extend(rows) or True, "{}")
    _put(pipe, "codebase", "https://www.mql5.com/en/code/9", EA_RSI + "// EURUSD only",
         title="RSI EA for EURUSD")
    pipe.process(now=T0)
    pipe.donate(now=T0)
    assert donated and all(r["url"] == "https://www.mql5.com/en/code/9" for r in donated)
    c = next(x for x in pipe.cells.by_status("EVALUATING") if x.use == "direct_cells")
    expanded = pipe.prereg.load(c.cell_id)["gauntlet_cells_expanded"]
    assert len(expanded) == 16 and "M15/london" in expanded
    stranger = pipe.hooks.gauntlet_cell({**(c.spec or {}), "params": {"rsi_n": 99}})
    rows = [{"at": iso(T0), "cell": expanded["M5/asia"], "passed": False,
             "terminal_gate": "walk_forward"},
            {"at": iso(T0 + timedelta(minutes=1)), "cell": expanded["M15/london"],
             "passed": True, "terminal_gate": "PASSED"},
            {"at": iso(T0 + timedelta(minutes=2)), "cell": expanded["M15/london"],
             "passed": True, "terminal_gate": "PASSED"},            # a replayed row
            {"at": iso(T0), "cell": stranger, "passed": True, "terminal_gate": "PASSED"}]
    (tmp_path / "gate_verdict_ledger.jsonl").write_text(
        "".join(json.dumps(r) + "\n" for r in rows), "utf-8")
    assert pipe.join_verdicts(now=T0) == 2
    got = pipe.cells.get(c.cell_id)
    assert got is not None and got.status == "EVALUATED"
    assert got.rejection_reason == "REGIME_FRAGILE"                  # the first judged axis
    assert got.verdict["survivor"] and got.verdict["survivor_axis"]["axis"] == "M15/london"
    m = pipe.metrics(T0 + timedelta(hours=1))
    assert m["docket_cells_judged_24h"] == 2 and m["docket_cells_passed_24h"] == 1
    assert m["cells_survived_24h"] == 1
    kills = [r for r in pipe.ledger.rows() if r["stage"] == "gauntlet"]
    assert [r["kill_class"] for r in kills] == ["confident_kill"]


def test_digest_is_written_even_when_acquire_raises(tmp_path: Path) -> None:
    pipe = _pipe(tmp_path)

    def boom(*a: Any, **k: Any) -> Any:
        raise RuntimeError("network stack gone")
    pipe.acquire = boom
    m = pipe.run_pass(60, fetch=True, now=T0)
    assert any(e.startswith("acquire: RuntimeError") for e in m["last_pass"]["errors"])
    assert json.loads((tmp_path / "mining_digest.json").read_text("utf-8"))["generated_at"]

    def metrics_boom(t: Any) -> Any:
        raise ValueError("metrics broke")
    pipe.metrics = metrics_boom
    with pytest.raises(ValueError):
        pipe.run_pass(60, fetch=False, now=T0 + timedelta(hours=1))
    d = json.loads((tmp_path / "mining_digest.json").read_text("utf-8"))
    assert d["generated_at"] == iso(T0 + timedelta(hours=1))
    assert d["metrics"]["publish"] == "FAILED before metrics"


def test_mechanics_feed_becomes_conditioner_series_and_cells(tmp_path: Path) -> None:
    src = acq.Source(id="broker_specs", fetcher="page_snapshot", kind="mechanics",
                     uses=["allocation_intel"], config={"targets": ["XAUUSD"]})
    pipe = _pipe(tmp_path, sources=[src])
    uri = "https://broker/xauusd-spec"
    for i in range(MS.COND_MIN_OBS - 1):
        _put(pipe, "broker_specs", uri, f"Swap long -{6 + i * 0.1:.1f}, swap short 1.1. "
             f"Commission ${4 + i % 3}.5 per lot. Maximum daily loss of {4 + i % 2}%.",
             kind="mechanics", now=T0 + timedelta(days=i))
        pipe.process(now=T0 + timedelta(days=i))
    rep = pipe.conditioners(now=T0 + timedelta(days=40))
    sid = MS.Pipeline.series_id("broker_specs", uri)
    st = json.loads(pipe.cells.kv_get("conditioners", "{}"))[sid]
    assert rep["cells_minted"] == 0 and st["status"].startswith("UNMEASURED")
    last = T0 + timedelta(days=MS.COND_MIN_OBS - 1)
    _put(pipe, "broker_specs", uri, "Swap long -9.9, swap short 1.1. Commission $4.5 per lot.",
         kind="mechanics", now=last)
    pipe.process(now=last)
    rep = pipe.conditioners(now=last)
    lines = (tmp_path / "lake" / "series" / f"{sid}.csv").read_text("utf-8").splitlines()
    assert lines[0].startswith("available_time,vintage_id,source_id")
    assert len(lines) == 1 + MS.COND_MIN_OBS
    times = [ln.split(",")[0] for ln in lines[1:]]
    assert times == sorted(times) and times[-1] == iso(last)
    st = json.loads(pipe.cells.kv_get("conditioners", "{}"))[sid]
    assert st["status"] == "MINTING" and st["varying"] == ["swap_long"]
    cells = [c for c in pipe.cells.all_cells() if c.use == "allocation_intel"]
    assert rep["cells_minted"] == len(cells) == len(MS.COND_TRANSFORMS)
    assert {c.spec["family"] for c in cells} == {"exogenous_conditioner"}
    assert {c.spec["params"]["source"] for c in cells} == {sid}
    assert all(c.status == "QUEUED" and c.preregistration_id for c in cells)
    assert pipe.conditioners(now=last)["cells_minted"] == 0          # minted once
    # commission and the prop-rule limit changed too, and went to the cost/risk input instead
    facts = json.loads((tmp_path / "mechanics_facts.json").read_text("utf-8"))["pages"][sid]
    assert facts["cost"] == {"commission_per_lot": 4.5} and facts["financing"]["swap_long"] == -9.9
    assert "max_daily_loss_pct" not in facts["prop_rules"]          # the last page omitted it
    assert set(facts["last_changed_at"]) >= {"swap_long", "commission_per_lot"}
    assert not any(c.spec["params"]["signal"] != "swap_long" for c in cells)


def test_digest_carries_the_whole_rejection_ledger(tmp_path: Path) -> None:
    pipe = _pipe(tmp_path)
    for i in range(5):
        pipe.ledger.reject(f"mc_{i}", "DUPLICATE_MECHANISM" if i % 2 else "COST_EXCEEDS_EDGE",
                           "dedup" if i % 2 else "gauntlet", source_id="codebase",
                           kill_class="" if i % 2 else "confident_kill", now=T0)
    pipe.run_pass(60, fetch=False, now=T0)
    d = json.loads((tmp_path / "mining_digest.json").read_text("utf-8"))["rejection_ledger"]
    raw = (tmp_path / "mining" / "rejections.jsonl").read_bytes()
    import hashlib
    assert d["rows"] == 5 and d["sha256"] == hashlib.sha256(raw).hexdigest()
    assert d["by"]["reason"] == {"COST_EXCEEDS_EDGE": 3, "DUPLICATE_MECHANISM": 2}
    assert d["by"]["kill_class"] == {"confident_kill": 3}


def test_experiment_ledger_reads_mining_trial_families(tmp_path: Path,
                                                        monkeypatch: pytest.MonkeyPatch) -> None:
    from libs.research import experiment_ledger as el
    pipe = _pipe(tmp_path)
    _put(pipe, "codebase", "https://www.mql5.com/en/code/7", EA_RSI + "// EURUSD only")
    pipe.process(now=T0)
    pipe.donate(now=T0)
    c = next(x for x in pipe.cells.by_status("EVALUATING") if x.use == "direct_cells")
    (tmp_path / "gate_verdict_ledger.jsonl").write_text(json.dumps(
        {"at": iso(T0), "cell": c.gauntlet_cell, "passed": False,
         "terminal_gate": "pbo"}) + "\n", "utf-8")
    pipe.run_pass(60, fetch=False, now=T0)
    fams = pipe.cells.trial_families()
    assert fams[c.trial_family_id]["docket_judged"] == 1
    assert fams[c.trial_family_id]["families"] == ["mean_reversion_rsi"]
    desk = tmp_path / "desk"
    (desk / "data").mkdir(parents=True)
    (desk / "data" / "mining_digest.json").write_bytes(
        (tmp_path / "mining_digest.json").read_bytes())
    monkeypatch.setattr(el, "DESK", desk)
    got = el._mining_trial_families()
    assert got["status"] == "MEASURED" and got["docket_judged"] == 1
    assert got["trial_families"] == len(fams)
    monkeypatch.setattr(el, "DESK", tmp_path / "absent")
    assert el._mining_trial_families()["status"].startswith("UNMEASURED")


def test_one_registry_names_every_lane_once(tmp_path: Path) -> None:
    """Unnamed rows get durable ids (the W1 `ground:` form for grounds), the same thing on the
    same page from two rosters is one source with an alias, and a different thing on the same
    page stays a second source linked by shares_page."""
    d = tmp_path / "desks" / "mt5" / "data"
    d.mkdir(parents=True)
    (d / "grounds.json").write_text(json.dumps({"grounds": [
        {"name": "七禾网 专访", "region": "cn", "url": "https://www.7hcn.com/list"},
        {"name": "Stats Portal", "region": "cn", "url": "https://stats.example.cn/sj/"}]}),
        "utf-8")
    (d / "lane.json").write_text(json.dumps({"sources": [
        {"id": "hcn_interviews", "name": "七禾网 专访", "region": "cn",
         "url": "http://7hcn.com/list/"},
        {"id": "cn_rail", "name": "rail freight", "url": "https://stats.example.cn/sj"},
        {"id": "shfe_kx", "name": "a", "url": "https://s.cn/d.html?paramid=kx"},
        {"id": "shfe_pm", "name": "b", "url": "https://s.cn/d.html?paramid=pm"}]}), "utf-8")
    roster = tmp_path / "sources.yaml"
    roster.write_text(textwrap.dedent("""
        external_rosters:
          - path: desks/mt5/data/grounds.json
            rows: grounds
            id_style: ground
            defaults: {fetcher: owned, owner: deep_forest}
          - path: desks/mt5/data/lane.json
            rows: sources
            defaults: {fetcher: owned, owner: lane}
        sources: []
        """), "utf-8")
    got = {s.id: s for s in acq.load_roster(roster, root=tmp_path)}
    ground = got["ground:cn:七禾网_专访"]
    assert ground.owner == "deep_forest" and ground.aliases == ["hcn_interviews"]
    assert "hcn_interviews" not in got
    portal, rail = got["ground:cn:stats_portal"], got["cn_rail"]
    assert portal.shares_page == ["cn_rail"] and rail.shares_page == [portal.id]
    assert {"shfe_kx", "shfe_pm"} <= got.keys()          # the query separates two datasets


def test_two_countries_naming_one_vendor_page_stay_two_sources(tmp_path: Path) -> None:
    d = tmp_path / "r"
    d.mkdir()
    (d / "bo.json").write_text(json.dumps({"sources": [
        {"id": "pack_bo_la", "name": "licensed assessments", "region": "bo",
         "url": "https://vendor.com/assess"}]}), "utf-8")
    (d / "pe.json").write_text(json.dumps({"sources": [
        {"id": "pack_pe_la", "name": "licensed assessments", "region": "pe",
         "url": "https://vendor.com/assess"}]}), "utf-8")
    roster = tmp_path / "sources.yaml"
    roster.write_text("external_rosters:\n  - path: r/*.json\n    defaults: {fetcher: owned}\n"
                      "  - path: r/absent.json\n  - path: r/later.json\n"
                      "    pending: branch not merged\nsources: []\n", "utf-8")
    got = {s.id: s for s in acq.load_roster(roster, root=tmp_path)}
    assert {"pack_bo_la", "pack_pe_la"} <= got.keys() and not got["pack_bo_la"].aliases
    states = {r["path"]: r["state"] for r in acq.roster_files(roster, root=tmp_path)}
    assert states == {"r/*.json": "OK", "r/absent.json": "MISSING", "r/later.json": "PENDING"}


def test_the_live_roster_names_no_missing_file() -> None:
    bad = [r for r in acq.roster_files(root=ROOT) if r["state"] in ("MISSING", "BROKEN")]
    assert not bad, bad


def test_a_country_pack_that_will_not_load_is_loud(tmp_path: Path, monkeypatch: Any) -> None:
    """A pack that raises is an error on the roster entry (BROKEN), never a silent zero; a
    pack_cells-shape pack (no PACK export) is simply not a source table."""
    from libs.research import country_lab
    for cc, body in (("zz", "PACK = None\n"), ("yy", "KNOWN_GROUNDS = ()\n")):
        (tmp_path / "c" / cc).mkdir(parents=True)
        (tmp_path / "c" / cc / "pack.py").write_text(body, "utf-8")
    monkeypatch.setattr(country_lab, "resolve_pack",
                        lambda cc: (_ for _ in ()).throw(ImportError(f"no {cc}")))
    errs: list[dict[str, str]] = []
    assert acq.pack_rows(tmp_path / "c", errs) == []
    assert errs == [{"pack": "zz", "error": "ImportError: no zz"}]
    doc = {"external_rosters": [{"packs": "c"}]}
    (tmp_path / "r.yaml").write_text(json.dumps(doc), "utf-8")
    got = acq.roster_files(tmp_path / "r.yaml", root=tmp_path)
    assert got[0]["state"] == "BROKEN" and got[0]["failed"] == 1


def test_one_video_is_one_url_key_and_an_endpoint_is_no_scope() -> None:
    for u in ("https://m.youtube.com/watch?v=AbC&t=3", "https://youtu.be/AbC?t=1",
              "https://www.youtube.com/shorts/AbC", "youtube.com/watch?v=AbC"):
        assert acq.canonical_url(u) == "youtube.com/watch?v=AbC", u
    idx = {"youtube.com": [("youtube.com/watch", "corpus")],
           "boj.or.jp": [("boj.or.jp/x/index.htm", "boj")]}
    assert MS.Pipeline.attribute_url("https://youtu.be/AbC", idx) == ""   # not a catch-all
    assert MS.Pipeline.attribute_url("https://boj.or.jp/x", idx) == "boj"  # the index's dir


def test_a_pinned_family_row_names_the_judges_chart() -> None:
    """`lvc_asia_london` is judged on M5 whatever its row says; its docket row must name the same
    cell (the 13 rows that never joined, audit 2026-09-30)."""
    fi = importlib.import_module("research.frontier_identity")
    src = (ROOT / "desks" / "mt5" / "scripts" / "external_gauntlet.py").read_text("utf-8")
    import ast
    pinned = next(ast.literal_eval(n.value) for n in ast.parse(src).body
                  if isinstance(n, ast.Assign) and getattr(n.targets[0], "id", "")
                  == "_PINNED_TIMEFRAME")
    assert pinned == fi.PINNED_TIMEFRAME
    row = {"symbol": "GBPJPY", "family": "lvc_asia_london", "params": {}}
    assert fi.docket_cell_id(row).startswith("GBPJPY@M5.lvc_asia_london.p=")
    judge = {"sym": "GBPJPY", "family": "lvc_asia_london", "params": {}, "timeframe": "M5"}
    assert fi.docket_cell_id(row) == fi.cell_id(judge)


def test_a_lane_owned_source_is_active_only_through_a_judged_docket_cell(tmp_path: Path) -> None:
    """Credit comes from a DECLARED seat or the longest proper URL prefix; a host-only registry
    URL never captures other pages, a cross-jurisdiction tie credits nobody, one page within one
    jurisdiction is its first definer's, an undeclared seat is nobody's -- and ACTIVE also needs
    the source's own fetcher to have run."""
    def src(sid: str, key: str, **kw: Any) -> acq.Source:
        return acq.Source(id=sid, fetcher=kw.pop("fetcher", "owned"), kind="text",
                          uses=["direct_cells"], url_key=key, **kw)
    owned = [src("rbnz_series", "rbnz.govt.nz/statistics", seats=["miner:asia:rbnz_series"]),
             src("smart_lab_blog", "smart-lab.ru/blog"),
             src("smart_lab_home", "smart-lab.ru"),
             src("twin_a", "x.org/p", region="pe"),
             src("twin_b", "x.org/p", region="bo"),
             src("dup_a", "y.org/q", region="cn"),
             src("dup_b", "y.org/q"),
             src("boj_listing", "boj.or.jp/en/statistics", fetcher="html_listing")]
    pipe = _pipe(tmp_path, sources=owned)
    rows = [
        {"symbol": "NZDUSD", "family": "carry", "params": {"k": 1},
         "source": "miner:asia:rbnz_series", "source_url": "https://www.rbnz.govt.nz/x"},
        {"symbol": "EURUSD", "family": "carry", "params": {"k": 2},
         "source": "miner:world_crawler", "source_url": "https://smart-lab.ru/blog/123.php"},
        {"symbol": "EURUSD", "family": "carry", "params": {"k": 3},
         "source": "miner:world_crawler", "source_url": "https://smart-lab.ru/forum/9"},
        {"symbol": "EURUSD", "family": "carry", "params": {"k": 4},
         "source": "miner:discovery_compiler", "source_url": "https://x.org/p/1"},
        {"symbol": "EURUSD", "family": "carry", "params": {"k": 5},
         "source": "miner:smart_lab_blog", "source_url": ""},
        {"symbol": "EURUSD", "family": "carry", "params": {"k": 6},
         "source": "orthogonal_sweep:carry", "source_url": "https://y.org/q/7"},
        {"symbol": "USDJPY", "family": "carry", "params": {"k": 7},
         "source": "miner:world_crawler", "source_url": "https://www.boj.or.jp/en/statistics/a"}]
    pipe.docket.write_text(json.dumps(rows), "utf-8")
    assert pipe.source_status(T0)["rbnz_series"]["status"] == "COLD"   # nothing judged yet
    pipe.gate_ledger.write_text("".join(json.dumps(
        {"cell": pipe.hooks.gauntlet_cell(r), "passed": False, "terminal_gate": "pbo",
         "at": iso(T0 - timedelta(days=2))}) + "\n" for r in rows), "utf-8")
    pipe.index_judged(now=T0)
    st = pipe.source_status(T0)
    assert st["rbnz_series"]["evaluated_via"] == {"mining": 0, "docket": 1}   # by its seat
    assert st["smart_lab_blog"]["evaluated_cells_30d"] == 1   # the URL; not the undeclared seat
    assert st["smart_lab_blog"]["fetch_evidence"] == "producer:world_crawler"
    assert st["smart_lab_home"]["status"] == "COLD"           # host-only is not a wildcard
    assert st["twin_a"]["status"] == st["twin_b"]["status"] == "COLD"      # a tie credits nobody
    assert st["dup_a"]["status"] == "ACTIVE" and st["dup_b"]["evaluated_cells_30d"] == 0
    # judged and credited, but its registered fetcher (the pipeline) never ran it
    assert st["boj_listing"]["evaluated_cells_30d"] == 1
    assert st["boj_listing"]["cold_reason"] == "no fetcher of it ran in 30 days"
    att = pipe._attribution
    assert att["credited_by"] == {"seat": 1, "url": 3}
    assert att["producer_map_error"] == ""
    asia = MS.producer_of("miner:asia:rbnz_series", MS._scout_seats())
    assert att["by_producer"][asia] == {"judged": 1, "credited": 1}
    assert att["by_producer"]["orthogonal_sweep"] == {"judged": 1, "credited": 1}
    assert st["rbnz_series"]["producers"] == {asia: 1}
    assert MS.producer_of("miner:world:x", {"world": "world_crawler"}) == "world_crawler"
    assert MS.producer_of("ext_forexfactory_GBPUSD_srb", MS._scout_seats()) == \
        "convert_to_hypotheses_v4"
    assert att["unattributed_judged_rows"] == 3
    assert att["unattributed_top_producers"] == {"miner:world_crawler": 1,
                                                 "miner:discovery_compiler": 1,
                                                 "miner:smart_lab_blog": 1}
    pipe.store.log_run("boj_listing", "ok", 3, 3, "", now=T0 - timedelta(days=1))
    assert pipe.source_status(T0)["boj_listing"]["status"] == "ACTIVE"
    assert pipe.source_status(T0 + timedelta(days=40))["rbnz_series"]["status"] == "COLD"
    assert pipe.register_cursors(now=T0) == 8 and pipe.register_cursors(now=T0) == 0
    assert pipe.cursors.get("twin_a")["registered"]["canonical_id"] == "twin_a"
    st = pipe.source_status(T0)
    summary = pipe.registry_summary(st)
    assert summary["active"] == 4 and summary["schema"].endswith("source_registry.schema.json")
    assert summary["cold_by_reason"]["no cell EVALUATED in 30 days"] == [
        "dup_b", "smart_lab_home", "twin_a", "twin_b"]
    col = summary["url_collisions"]
    assert (col["keys"], col["rows"], col["same_region_owned"], col["cross_region_ties"]) == (
        2, 4, 1, 1)
    assert col["by_source"]["dup_b"] == [{"url_key": "y.org/q", "owner": "dup_a",
                                          "with": "dup_a"}]
    assert col["by_source"]["twin_a"][0]["owner"] == ""


def test_the_producer_map_names_real_organs_and_fails_loudly(monkeypatch: Any) -> None:
    """Every internal producer seat names a file that exists and stamps that seat; a map that
    will not load is an error in the attribution basis, never an all-`unmapped` silence."""
    doc = json.loads(MS.PRODUCER_ORGANS.read_text("utf-8"))
    for seat, path in {**doc["seats"], **doc["prefixes"]}.items():
        text = (ROOT / path).read_text("utf-8")
        assert f'"{seat}' in text or f"'{seat}" in text, (seat, path)
    organ_of = MS._scout_seats()
    assert MS.producer_of("miner:broker_swaps", organ_of) == "seed_miners"
    assert MS.producer_of("miner:world_crawler", organ_of) == "world_crawler"
    assert MS.producer_of("miner:central_bank", organ_of) == "central_bank_miner"
    assert MS.producer_of("session_chart_equivalent:ny_mid@H1", organ_of) == \
        "session_chart_equivalents"
    monkeypatch.setattr(MS, "PRODUCER_ORGANS", ROOT / "no" / "such.json")
    with pytest.raises(OSError):
        MS._scout_seats()


def test_the_live_roster_is_one_registry() -> None:
    got = acq.load_roster(root=ROOT)
    ids = [s.id for s in got]
    assert len(ids) == len(set(ids))
    owners = {s.owner.split("/")[0] for s in got}
    assert {"deep_forest", "asia_desk", "firm_mining", "country_pack",
            "global_mining"} <= owners
    schema = json.loads((ROOT / "libs" / "mining" / "source_registry.schema.json")
                        .read_text("utf-8"))
    assert schema["schema"] == "source_registry/1"


def test_archive_captures_config_urls_and_named_seats_on_the_same_site(tmp_path: Path) -> None:
    """An archive capture is judged as the page it archived; the pipeline's own rows are keyed
    by the URLs in their fetcher config; a seat named as a registry id credits it only when the
    row's URL is on that source's own site."""
    row = {"id": "mql5_forum_en", "fetcher": "html_listing", "config": {"listing": [
        {"url": "https://www.mql5.com/en/forum/page{page}",
         "page1": "https://www.mql5.com/en/forum"}]}}
    src = acq.normalise_row(row, origin="t")
    assert src is not None and "mql5.com/en/forum" in src.url_keys
    darwinex = acq.Source(id="darwinex", fetcher="owned", url_key="api.darwinex.com",
                          url_keys=["api.darwinex.com"])
    pipe = _pipe(tmp_path, sources=[src, darwinex])
    idx, seats = pipe._url_index(), pipe._seat_index()
    assert pipe.attribute_url("https://web.archive.org/web/2019/https://www.mql5.com/en/forum/9",
                              idx) == "mql5_forum_en"
    assert pipe.attribute_url("https://www.mql5.com/en/code/1", idx) == ""
    boj = {"boj.or.jp": [("boj.or.jp/en/statistics/index.htm", "boj_stats")]}
    # an index page scopes its directory
    assert pipe.attribute_url("http://www.boj.or.jp/en/statistics/set/x.pdf", boj) == "boj_stats"
    dx = "https://web.archive.org/web/20191210165044/https://www.darwinex.com/darwin/AJG.4.21"
    assert pipe.attribute_source({"source": "miner:darwinex", "source_url": dx}, idx, seats) \
        == ("darwinex", "seat+site")
    assert pipe.attribute_source({"source": "miner:darwinex", "source_url":
                                  "https://youtube.com/watch?v=1"}, idx, seats) == ("", "")


def test_a_derived_docket_row_traces_to_its_parents_declared_seat(tmp_path: Path) -> None:
    """discovery_compiler's donation carries its parent's URL and seat; the candidate compiler
    keeps them; the registry credits the parent's DECLARED seat, never an undeclared one."""
    dc = importlib.import_module("research.discovery_compiler")
    mcc = importlib.import_module("research.miner_candidate_compiler")
    parent = {"discovery_id": "d1", "symbol": "NZDUSD", "source_url": "https://rbnz.govt.nz/a",
              "lineage_intake": "intel:asia_rbnz:x.json", "lineage_generator": "seat:asia_rbnz"}
    child = {"family": "carry", "symbol": "NZDUSD", "chart": "H1", "content_hash": "h"}
    don = dc._donation_row(child, parent)
    assert (don["url"], don["origin_seat"], don["origin_intake"]) == (
        "https://rbnz.govt.nz/a", "asia_rbnz", "intel:asia_rbnz:x.json")
    cand = mcc._candidate("NZDUSD", "carry", {}, "discovery_compiler", don, "carry")
    assert cand["source_url"] == "https://rbnz.govt.nz/a" and cand["origin_seat"] == "asia_rbnz"
    pipe = _pipe(tmp_path, sources=[acq.Source(
        id="rbnz", fetcher="owned", kind="text", uses=["direct_cells"],
        seats=["miner:asia_rbnz"])])
    row = {"source": "miner:discovery_compiler", "source_url": "", "origin_seat": "asia_rbnz"}
    seats = pipe._seat_index()
    assert pipe.attribute_source(row, pipe._url_index(), seats) == ("rbnz", "lineage")
    assert pipe.attribute_source({**row, "origin_seat": "nobody"}, pipe._url_index(),
                                 seats) == ("", "")


def test_a_lane_that_describes_its_uses_by_key_keeps_them() -> None:
    """The free stack writes `uses: {direct: {...}, indirect: {...}, allocation: {...}}`; read
    as a list it filtered to nothing and every free-stack source served no use."""
    row = acq.normalise_row({"id": "x", "uses": {"direct": {"families": ["a"]}, "indirect": {},
                                                  "allocation": {"organ": "o"}}},
                            origin="t", defaults={"fetcher": "owned", "kind": "text"})
    assert row is not None and row.uses == ["direct_cells", "allocation_intel"]
