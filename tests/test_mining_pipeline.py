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
        acq.Source(id="codebase", fetcher="external_feed", kind="code", priority=1),
        acq.Source(id="forum_ru", fetcher="external_feed", kind="text", priority=1),
        acq.Source(id="cold_source", fetcher="rss", kind="text", priority=2)]
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
    assert len(q) == 2
    fams = {c.trial_family_id for c in q}
    assert len(fams) == 1
    parent = [c for c in q if not c.parent_cell_id]
    kids = [c for c in q if c.parent_cell_id]
    assert len(parent) == 1 and len(kids) == 1 and kids[0].parent_cell_id == parent[0].cell_id


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
    c = pipe.cells.by_status("EVALUATING")[0]
    (tmp_path / "gate_verdict_ledger.jsonl").write_text(
        json.dumps({"at": iso(T0), "cell": c.gauntlet_cell, "passed": True,
                    "terminal_gate": "PASSED"}) + "\n", "utf-8")
    m = pipe.run_pass(60, fetch=False, now=T0 + timedelta(hours=1))
    tr = m["trace"]
    assert tr["complete"] and tr["outcome"] == "SURVIVOR"
    assert tr["source_uri"] == "https://www.mql5.com/en/code/123"
    assert tr["preregistration_sha256"] == pipe.prereg.sha(tr["cell_id"])
    for k in ("sources_active", "sources_total", "cells_acquired_24h", "cells_compiled_24h",
              "cells_preregistered_24h", "cells_evaluated_24h", "cells_rejected_24h",
              "cells_rejected_24h_by_reason", "cells_survived_24h", "rejection_rate",
              "median_time_source_to_evaluation_hours", "queue_age_p95_days",
              "binding_constraint"):
        assert k in m, k
    assert m["cells_survived_24h"] == 1 and m["rejection_rate"] == 0.0
    assert any("too loose" in w for w in m["warnings"])
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
    assert len(pipe.cells.by_status("QUEUED")) == 1
    assert len(pipe.cells.by_status("BLOCKED_DUPLICATE_MECHANISM")) == 1


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
