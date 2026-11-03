"""Three defects from the 2026-10-14 INTEL_SHIP audit, each pinned on fixtures with no network.

1. `axis_ingest` mapped CFTC rows to MT5 symbols by NAME PREFIX, so "EURO FX/BRITISH POUND XRATE"
   and "EURO FX/JAPANESE YEN XRATE" were EURUSD too and the `(symbol, as_of)` dedupe kept
   whichever row the CFTC file listed first. It now maps by CFTC contract market code.
2. The deepening queue accepted share CFDs (Airbnb, Pfizer seasonality rows) for statistical
   extraction. The compiler refuses them at enqueue, and the worker purges what was queued before.
3. The compiler's seasonality branch never fired for current rows (`"3M_H1"`, `"bullish"`).

    python -m pytest desks/mt5/tests/test_cot_axis_and_deepening_lane.py -q
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

_DESK = Path(__file__).resolve().parents[1]
for _p in (str(_DESK), str(_DESK / "research"), str(_DESK.parent.parent)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import axis_ingest  # noqa: E402
import deepening_worker as dw  # noqa: E402
import miner_candidate_compiler as mcc  # noqa: E402

# ------------------------------------------------------------------ fixtures


def _legacy_row(name: str, code: str, date: str, oi: int, nc_long: int, nc_short: int) -> str:
    """One `deafut.txt` row in the CFTC legacy layout: name, yymmdd, date, CODE (col 3),
    market code, region, commodity code, OI (col 7), NC long/short/spread, comm long/short."""
    yymmdd = date[2:4] + date[5:7] + date[8:10]
    return (f'"{name}",{yymmdd},{date},{code},CME ,00,{code[:3]} ,{oi},{nc_long},{nc_short},'
            f"0,1000,2000,0,0")


_WEEK = "2026-10-06"
_CROSSES_FIRST = [
    _legacy_row("EURO FX/BRITISH POUND XRATE - CHICAGO MERCANTILE EXCHANGE", "299741",
                _WEEK, 9_000, 100, 200),
    _legacy_row("EURO FX/JAPANESE YEN XRATE - CHICAGO MERCANTILE EXCHANGE", "399741",
                _WEEK, 7_000, 300, 100),
    _legacy_row("GOLD -1 TROY OUNCE - COINBASE DERIVATIVES, LLC", "088LM1",
                _WEEK, 5_000, 10, 20),
    _legacy_row("EURO FX - CHICAGO MERCANTILE EXCHANGE", "099741", _WEEK, 850_000,
                250_000, 150_000),
    _legacy_row("GOLD - COMMODITY EXCHANGE INC.", "088691", _WEEK, 500_000, 300_000, 50_000),
    _legacy_row("NZ DOLLAR - CHICAGO MERCANTILE EXCHANGE", "112741", _WEEK, 60_000,
                10_000, 30_000),
]


def _ingest(monkeypatch, lines: list[str]) -> dict:
    monkeypatch.setattr(axis_ingest, "_fetch", lambda url: "\n".join(lines) + "\n")
    monkeypatch.setattr(axis_ingest, "_cot_history_text", lambda years: [])
    return axis_ingest.ingest_cot()


@pytest.fixture
def registry(tmp_path, monkeypatch):
    """A broker registry with one class per lane, so the lane tests do not read the box's."""
    reg = tmp_path / "universe.json"
    reg.write_text(json.dumps({
        "EURUSD": {"asset_class": "Forex"}, "XAUUSD": {"asset_class": "Commodities"},
        "US500": {"asset_class": "Indices"},
        "Airbnb": {"asset_class": "Equities"}, "Pfizer": {"asset_class": "Equities"},
        "3M": {"asset_class": "Equities"},
    }), "utf-8")
    seen = set()
    for mod in (mcc, dw):
        up = sys.modules[mod.lane_split.__module__]._universe_policy()
        if id(up) not in seen:
            seen.add(id(up))
            monkeypatch.setattr(up, "UNIVERSE", reg)
    return {"EURUSD", "XAUUSD", "US500", "Airbnb", "Pfizer", "3M"}


# ------------------------------------------------------------------ 1. CFTC by contract code


@pytest.mark.parametrize("order", ["crosses_first", "outright_first", "reversed"])
def test_eurusd_takes_euro_fx_open_interest_whatever_the_row_order(monkeypatch, order) -> None:
    lines = list(_CROSSES_FIRST)
    if order == "outright_first":
        lines = [lines[3], *lines[:3], *lines[4:]]
    elif order == "reversed":
        lines = lines[::-1]
    doc = _ingest(monkeypatch, lines)
    eur = [r for r in doc["rows"] if r["symbol"] == "EURUSD"]
    assert len(eur) == 1, eur
    assert eur[0]["open_interest"] == 850_000
    assert eur[0]["net_pct_oi"] == round(100_000 / 850_000, 6)
    gold = [r for r in doc["rows"] if r["symbol"] == "XAUUSD"]
    assert len(gold) == 1 and gold[0]["open_interest"] == 500_000
    # The CFTC's current name for NZD ("NZ DOLLAR") was missed by the old prefix entirely.
    assert {r["symbol"] for r in doc["rows"]} == {"EURUSD", "XAUUSD", "NZDUSD"}
    assert doc["name_mismatches"] == {}
    assert doc["n_unmapped"] == 3


def test_the_code_decides_and_a_renamed_market_is_counted_not_dropped(monkeypatch) -> None:
    doc = _ingest(monkeypatch, [_legacy_row("EURO CURRENCY - CME", "099741", _WEEK,
                                            800_000, 1, 0),
                                _legacy_row("EURO FX - CHICAGO MERCANTILE EXCHANGE", "999999",
                                            _WEEK, 1, 1, 0)])
    assert [r["symbol"] for r in doc["rows"]] == ["EURUSD"]
    assert doc["rows"][0]["open_interest"] == 800_000
    assert doc["name_mismatches"] == {"099741": "EURO CURRENCY"}


def test_no_cftc_name_is_matched_by_prefix_any_more() -> None:
    sym, _ok = axis_ingest._symbol_for("299741", "EURO FX/BRITISH POUND XRATE - CME")
    assert sym is None
    assert axis_ingest._symbol_for("099741", "EURO FX - CME") == ("EURUSD", True)
    assert len({sym for sym, _ in axis_ingest.COT_CODES.values()}) == len(axis_ingest.COT_CODES)


# ------------------------------------------------------------------ 2. deepening lane


def _run_compiler(tmp_path, monkeypatch, universe: set[str], rows: dict[str, list[dict]]):
    import libs.ops.repair_invoke as ri
    import libs.research.hypothesis_graph as hg
    root = tmp_path / "intel"
    for src, rs in rows.items():
        p = root / src / "discoveries_1.json"
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps({"discoveries": rs}), "utf-8")
    for name, value in (("INTEL_ROOTS", (root,)), ("OUT", tmp_path / "out.json"),
                        ("DEEPEN", tmp_path / "deepen.json"),
                        ("DEEPEN_WORKED", tmp_path / "deepening_worked.jsonl"),
                        ("DEEPENED", tmp_path / "deepened.json"),
                        ("CURSOR", tmp_path / "cursor.json")):
        monkeypatch.setattr(mcc, name, value)
    monkeypatch.setattr(mcc, "known_symbols", lambda: set(universe))
    monkeypatch.setattr(mcc, "structurally_untestable_families", lambda: {})
    monkeypatch.setattr(mcc, "expand_axes", lambda rs: rs)
    monkeypatch.setattr(mcc, "_graph_snapshot", lambda: (_ for _ in ()).throw(RuntimeError("x")))
    monkeypatch.setattr(hg, "record_candidates", lambda *a, **k: 0)
    monkeypatch.setattr(ri, "request_repair", lambda reason, **kw: False)
    assert mcc.main() == 0
    return (json.loads((tmp_path / "out.json").read_text("utf-8")),
            json.loads((tmp_path / "deepen.json").read_text("utf-8")))


def test_a_share_cfd_task_is_refused_at_enqueue_with_its_reason(
        tmp_path, monkeypatch, registry) -> None:
    out, deepen = _run_compiler(tmp_path, monkeypatch, registry, {"world": [
        {"title": "Airbnb drifts higher into summer bookings", "symbols": ["Airbnb"],
         "url": "https://example.invalid/a"},
        {"title": "EURUSD drifts in a way nobody named", "symbols": ["EURUSD", "Pfizer"],
         "url": "https://example.invalid/b"},
    ]})
    titles = {t["title"]: t for t in deepen["tasks"]}
    assert "Airbnb drifts higher into summer bookings" not in titles
    mixed = titles["EURUSD drifts in a way nobody named"]
    assert mixed["symbols"] == ["EURUSD"]
    assert [h["symbol"] for h in mixed["lane_held"]] == ["Pfizer"]
    assert deepen["n_lane_refused"] == 1
    refused = deepen["lane_refused"][0]
    assert refused["held"][0]["symbol"] == "Airbnb"
    assert "share CFD" in refused["held"][0]["reason"]
    assert out["per_source"]["world"]["lane_refused"] == 1


def test_an_unclassified_symbol_is_refused_too(registry) -> None:
    allowed, held = mcc.lane_split(["EURUSD", "NOTREAL"])
    assert allowed == ["EURUSD"]
    assert held[0]["symbol"] == "NOTREAL" and "UNCLASSIFIED" in held[0]["reason"]


def test_the_worker_purges_queued_share_cfd_tasks_at_start(
        tmp_path, monkeypatch, registry) -> None:
    queue = tmp_path / "deepen.json"
    worked = tmp_path / "worked.jsonl"
    tasks = [
        {"source": "seasonality", "disposition": "NEEDS_EXACT_RULE_EXTRACTION",
         "title": "Airbnb_H1 historically bullish in month 10", "url": "", "symbols": ["Airbnb"]},
        {"source": "seasonality", "disposition": "NEEDS_EXACT_RULE_EXTRACTION",
         "title": "Pfizer_H1 historically bearish in month 10", "url": "", "symbols": ["Pfizer"]},
        {"source": "sec_edgar", "disposition": "NEEDS_EXACT_RULE_EXTRACTION",
         "title": "fund 13F", "url": "", "symbols": ["US500"]},
        {"source": "world", "disposition": "NEEDS_SYMBOL_EXTRACTION",
         "title": "no instrument yet", "url": "", "symbols": []},
    ]
    queue.write_text(json.dumps({"built_at": "x", "tasks": tasks}), "utf-8")
    monkeypatch.setattr(dw, "DEEPEN", queue)
    monkeypatch.setattr(dw, "WORKED", worked)
    note = dw.purge_off_lane()
    assert note["purged"] == 2 and note["status"] == "PURGED"
    after = json.loads(queue.read_text("utf-8"))
    assert [t["title"] for t in after["tasks"]] == ["fund 13F", "no instrument yet"]
    assert after["n_lane_refused"] == 2
    assert {r["held"][0]["symbol"] for r in after["lane_refused"]} == {"Airbnb", "Pfizer"}
    ledger = [json.loads(x) for x in worked.read_text("utf-8").splitlines()]
    assert len(ledger) == 2
    assert all(r["disposition"].startswith("REFUSED_LANE:") for r in ledger)
    assert {r["id"] for r in ledger} == {dw.task_id(t) for t in tasks[:2]}
    # ONE-SHOT: a second pass finds nothing and writes nothing.
    before = queue.read_bytes()
    assert dw.purge_off_lane() == {"purged": 0, "struck": 0, "waiting": 0, "status": "CLEAN"}
    assert queue.read_bytes() == before


@pytest.fixture(autouse=True)
def _private_job_locks(tmp_path, monkeypatch):
    """The purge takes the compiler's job lock; keep it out of the real data/.job_locks."""
    import job_lock
    monkeypatch.setattr(job_lock, "LOCK_ROOT", tmp_path / "job_locks")


def _queue(tmp_path, monkeypatch, tasks: list[dict]):
    queue = tmp_path / "deepen.json"
    worked = tmp_path / "worked.jsonl"
    queue.write_text(json.dumps({"built_at": "x", "tasks": tasks}), "utf-8")
    monkeypatch.setattr(dw, "DEEPEN", queue)
    monkeypatch.setattr(dw, "WORKED", worked)
    return queue, worked


_MIXED = [
    {"source": "seasonality", "title": "XAUUSD_H1 bullish in month 10", "url": "",
     "symbols": ["XAUUSD"]},
    {"source": "world", "title": "EURUSD drifts", "url": "", "symbols": ["EURUSD"]},
    {"source": "seasonality", "title": "Airbnb_H1 bullish in month 10", "url": "",
     "symbols": ["Airbnb"]},
]


@pytest.mark.parametrize("state", ["missing", "unreadable", "mid_write", "not_an_object"])
def test_an_empty_registry_purges_nothing_and_writes_no_final_line(
        tmp_path, monkeypatch, state) -> None:
    """MF1 (audit COT_AXIS_DEEPENING_31eb89f3d): with no registry every symbol reads
    UNCLASSIFIED, and gold/EURUSD were refused for good. Now it is UNMEASURED: nothing purged,
    nothing written, the queue untouched."""
    up = mcc._universe_policy()
    reg = tmp_path / "universe.json"
    if state == "unreadable":
        reg.write_bytes(b"\xff\xfe not json")
    elif state == "mid_write":
        reg.write_text('{"XAUUSD": {"asset_class": "Comm', "utf-8")
    elif state == "not_an_object":
        reg.write_text("[]", "utf-8")
    monkeypatch.setattr(up, "UNIVERSE", reg)
    queue, worked = _queue(tmp_path, monkeypatch, _MIXED)
    before = queue.read_bytes()
    note = dw.purge_off_lane()
    assert note["status"].startswith("UNMEASURED") and note["purged"] == 0
    assert queue.read_bytes() == before
    assert not worked.exists()
    # And the worker's own in-memory filter refuses nothing either: the tasks WAIT this pass.
    kept, refused, waiting = dw.split_off_lane(_MIXED)
    assert refused == [] and len(waiting) == 3 and kept == []
    assert dw.ledger_ids() == (set(), set())


def test_an_unclassified_task_waits_and_is_retried_once_classified(
        tmp_path, monkeypatch, registry) -> None:
    """UNCLASSIFIED is retryable, like a seat outage: one non-terminal line with a remedy, the
    task stays queued, and it is worked on the first pass the registry classifies it."""
    up = mcc._universe_policy()
    task = {"source": "world", "title": "NEWSYM rallies into the fix", "url": "",
            "symbols": ["NEWSYM"]}
    queue, worked = _queue(tmp_path, monkeypatch, [task])
    note = dw.purge_off_lane()
    assert note["purged"] == 0 and note["waiting"] == 1
    assert [t["title"] for t in json.loads(queue.read_text("utf-8"))["tasks"]] == [task["title"]]
    lines = [json.loads(x) for x in worked.read_text("utf-8").splitlines()]
    assert len(lines) == 1 and dw.is_lane_wait(lines[0]["disposition"])
    assert "remedy: none" not in lines[0]["disposition"]
    assert "classifies" in lines[0]["retry_action"]
    # NOT terminal for the worker, the deep-forest reader or the compiler's index.
    terminal, outage = dw.ledger_ids()
    assert dw.task_id(task) not in terminal | outage
    assert dw.task_id(task) not in dw.worked_ids()
    monkeypatch.setattr(mcc, "DEEPEN_WORKED", worked)
    assert dw.task_id(task) not in mcc._deepening_state()[0]
    # Written ONCE: a second pass adds no line.
    dw.purge_off_lane()
    assert len(worked.read_text("utf-8").splitlines()) == 1
    # Classified as Forex -> worked; classified as a share CFD -> then refused finally.
    reg = json.loads(up.UNIVERSE.read_text("utf-8"))
    up.UNIVERSE.write_text(json.dumps({**reg, "NEWSYM": {"asset_class": "Forex"}}), "utf-8")
    kept, refused, waiting = dw.split_off_lane([task])
    assert [t["title"] for t in kept] == [task["title"]] and not refused and not waiting
    up.UNIVERSE.write_text(json.dumps({**reg, "NEWSYM": {"asset_class": "Equities"}}), "utf-8")
    assert dw.purge_off_lane()["purged"] == 1
    assert json.loads(queue.read_text("utf-8"))["tasks"] == []


def test_a_share_cfd_task_is_still_refused_finally(tmp_path, monkeypatch, registry) -> None:
    queue, worked = _queue(tmp_path, monkeypatch, _MIXED)
    note = dw.purge_off_lane()
    assert note["purged"] == 1 and note["status"] == "PURGED"
    lines = [json.loads(x) for x in worked.read_text("utf-8").splitlines()]
    assert [r["disposition"].split(":")[0] for r in lines] == ["REFUSED_LANE"]
    assert dw.task_id(_MIXED[2]) in dw.ledger_ids()[0]
    assert [t["title"] for t in json.loads(queue.read_text("utf-8"))["tasks"]] == [
        "XAUUSD_H1 bullish in month 10", "EURUSD drifts"]


def test_the_purge_defers_while_the_compiler_holds_the_queue_writer_lock(
        tmp_path, monkeypatch, registry) -> None:
    import job_lock
    queue, worked = _queue(tmp_path, monkeypatch, _MIXED)
    before = queue.read_bytes()
    with job_lock.exclusive_job("miner_candidate_compiler", account=False) as held:
        assert held
        note = dw.purge_off_lane()
    assert note["status"].startswith("DEFERRED") and note["purged"] == 0
    assert queue.read_bytes() == before and not worked.exists()
    assert dw.purge_off_lane()["status"] == "PURGED"


def test_the_purge_lock_never_writes_the_compilers_admission_ledger(
        tmp_path, monkeypatch) -> None:
    import job_lock
    monkeypatch.setattr(job_lock, "_peaks_path", lambda name: tmp_path / f"{name}.peaks.json")
    with job_lock.exclusive_job("miner_candidate_compiler", account=False) as held:
        assert held
    assert not (tmp_path / "miner_candidate_compiler.peaks.json").exists()


def test_the_compiler_with_an_empty_registry_refuses_nothing(tmp_path, monkeypatch) -> None:
    """SF: an empty registry at enqueue refused every task for that pass. Now nothing is
    refused, `lane_check` says UNMEASURED, and a seasonality row is held, not minted."""
    up = mcc._universe_policy()
    monkeypatch.setattr(up, "UNIVERSE", tmp_path / "absent_universe.json")
    assert mcc.lane_split(["XAUUSD", "Airbnb", "NOTREAL"]) == (["XAUUSD", "Airbnb", "NOTREAL"], [])
    out, deepen = _run_compiler(tmp_path, monkeypatch, {"EURUSD", "XAUUSD", "Airbnb"}, {
        "world": [{"title": "EURUSD drifts in a way nobody named", "symbols": ["EURUSD"],
                   "url": "https://example.invalid/b"},
                  {"title": "Airbnb drifts higher into summer bookings", "symbols": ["Airbnb"],
                   "url": "https://example.invalid/a"}],
        "seasonality": [_season("XAUUSD_H1", "bullish")]})
    assert deepen["n_lane_refused"] == 0 and deepen["lane_refused"] == []
    assert deepen["lane_check"].startswith("UNMEASURED")
    titles = {t["title"] for t in deepen["tasks"]}
    assert {"EURUSD drifts in a way nobody named",
            "Airbnb drifts higher into summer bookings"} <= titles
    assert out["hypotheses"] == []                         # no cell minted on an absence
    assert "lane_refused" not in out["per_source"]["world"]


def test_the_compiler_queues_an_unclassified_task_waiting_not_refused(
        tmp_path, monkeypatch, registry) -> None:
    _out, deepen = _run_compiler(tmp_path, monkeypatch, registry | {"NOTREAL"}, {"world": [
        {"title": "NOTREAL rallies", "symbols": ["NOTREAL"], "url": "https://example.invalid/n"}]})
    assert deepen["n_lane_refused"] == 0 and deepen["lane_check"] == "MEASURED"
    [task] = deepen["tasks"]
    assert task["lane_waiting"] == ["NOTREAL"] and task["symbols"] == ["NOTREAL"]


def test_a_dry_run_purge_writes_nothing(tmp_path, monkeypatch, registry) -> None:
    queue = tmp_path / "deepen.json"
    queue.write_text(json.dumps({"tasks": [{"source": "s", "title": "t", "url": "",
                                            "symbols": ["Airbnb"]}]}), "utf-8")
    before = queue.read_bytes()
    monkeypatch.setattr(dw, "DEEPEN", queue)
    monkeypatch.setattr(dw, "WORKED", tmp_path / "worked.jsonl")
    assert dw.purge_off_lane(dry_run=True)["status"] == "DRY_RUN"
    assert queue.read_bytes() == before and not (tmp_path / "worked.jsonl").exists()


# ------------------------------------------------------------------ 3. current seasonality rows


def _season(symbol: str, direction: str, month: int = 10) -> dict:
    return {"source": "seasonality", "type": "historical_pattern", "symbol": symbol,
            "month": month, "avg_return": 0.03, "direction": direction, "symbols": [symbol],
            "confidence": 0.6,
            "description": f"{symbol} historically {direction} in month {month} (avg 0.03%)"}


def test_strip_timeframe() -> None:
    assert mcc.strip_timeframe("XAUUSD_M15") == "XAUUSD"
    assert mcc.strip_timeframe("3M_H1") == "3M"
    assert mcc.strip_timeframe("EURUSD") == "EURUSD"
    assert mcc.strip_timeframe("US500_mn1") == "US500"


@pytest.mark.parametrize(("symbol", "direction", "want", "side"), [
    ("XAUUSD_H1", "bullish", "XAUUSD", 1),
    ("EURUSD_M15", "bearish", "EURUSD", -1),
])
def test_a_current_format_row_compiles_on_a_hypothesis_lane_symbol(
        registry, symbol, direction, want, side) -> None:
    rows, disposition = mcc.compile_row("seasonality", _season(symbol, direction), registry)
    assert disposition == "STRUCTURED_CALENDAR"
    assert [(r["symbol"], r["family"], r["params"]) for r in rows] == [
        (want, "calendar_month", {"active_month": 10, "side_bias": side})]


@pytest.mark.parametrize("symbol", ["3M_H1", "Airbnb_H1", "Pfizer_M15"])
def test_a_share_cfd_seasonality_row_is_held_not_compiled(registry, symbol) -> None:
    rows, disposition = mcc.compile_row("seasonality", _season(symbol, "bullish"), registry)
    assert rows == [] and disposition == "LANE_HELD"


def test_a_held_seasonality_row_is_a_named_refusal_and_never_deepened(
        tmp_path, monkeypatch, registry) -> None:
    out, deepen = _run_compiler(tmp_path, monkeypatch, registry, {"seasonality": [
        _season("Airbnb_H1", "bullish"), _season("XAUUSD_H1", "bearish")]})
    stats = out["per_source"]["seasonality"]
    assert stats["lane_held"] == 1 and stats["valid_refusals"] == 1
    assert stats["candidates"] == 1
    assert [(h["symbol"], h["family"]) for h in out["hypotheses"]] == [
        ("XAUUSD", "calendar_month")]
    assert deepen["tasks"] == []
