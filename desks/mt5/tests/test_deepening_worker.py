"""The deepening queue had no reader, and a reader that invents rules is worse than none.

    python -m pytest desks/mt5/tests/test_deepening_worker.py -q

705 tasks sat at status None because the only module naming the queue file was the one that
WRITES it. Adding a reader is easy; adding one that cannot fabricate is the job. An LLM shown
"Build adaptive algorithmic trading bots ... for MetaTrader 5 scalping" will happily return a
complete EURUSD scalping rule with parameters, and every field of it would be invention wearing
the miner's provenance.

WHAT MUST NOT REGRESS, in order of what it would cost:

  1. an extraction whose `evidence` is not verbatim in the source text is REJECTED
  2. a symbol outside the desk universe cannot be admitted by naming it
  3. nothing reaches the candidate store except through `compile_row`
  4. a task is billed once -- a decision, including a rejection, is final
  5. one bad row does not end the batch
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

DESK = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(DESK / "research"))

import deepening_worker as dw  # noqa: E402

_TASK = {
    "source": "world_crawler",
    "disposition": "NEEDS_SYMBOL_EXTRACTION",
    "title": "EURUSD London open range breakout, 20-bar lookback",
    "url": "https://example.invalid/post",
    "symbols": [],
    "mechanism_tags": ["breakout"],
}


def _chat(payload: dict | str):
    """A seat that returns exactly what the test dictates."""
    body = payload if isinstance(payload, str) else json.dumps(payload)

    def chat(prompt, **kw):        # noqa: ARG001
        return body, ""
    return chat


# ------------------------------------------------- 1. fabrication is caught, not trusted

def test_an_evidence_span_absent_from_the_source_is_rejected() -> None:
    """The one guard that matters: a confident answer the text does not support."""
    found, why = dw.extract(_TASK, chat=_chat({
        "symbols": ["EURUSD"], "family": "session_range_breakout",
        "params": {"lookback": 20},
        "evidence": "the author backtested this over 11 years of tick data",
    }))
    assert found == {}
    assert "fabricated quote" in why


def test_a_verbatim_span_is_accepted() -> None:
    found, why = dw.extract(_TASK, chat=_chat({
        "symbols": ["EURUSD"], "family": "session_range_breakout",
        "params": {"lookback": 20},
        "evidence": "EURUSD London open range breakout",
    }))
    assert why == ""
    assert found["symbols"] == ["EURUSD"]


def test_requoting_with_different_whitespace_still_counts() -> None:
    """Models re-wrap lines while quoting faithfully; that is not a fabrication."""
    found, why = dw.extract(_TASK, chat=_chat({
        "symbols": ["EURUSD"], "family": None, "params": None,
        "evidence": "EURUSD   London\n  open range breakout",
    }))
    assert why == "", why
    assert found["symbols"] == ["EURUSD"]


# ------------------------------------------------- 2. the model cannot widen the desk's sets

def test_a_symbol_outside_the_universe_cannot_be_admitted_by_naming_it() -> None:
    found, why = dw.validate(
        {"symbols": ["DOGEUSD"], "family": None, "params": None, "evidence": "DOGEUSD"},
        "DOGEUSD is the instrument", {"EURUSD", "XAUUSD"})
    assert found == {}
    assert "outside the desk universe" in why


def test_nested_params_are_refused() -> None:
    found, why = dw.validate(
        {"symbols": ["EURUSD"], "family": "f", "params": {"a": {"b": 1}}, "evidence": "x"},
        "x", {"EURUSD"})
    assert found == {} and "flat scalars" in why


def test_an_empty_extraction_is_a_result_not_an_error() -> None:
    found, why = dw.validate(
        {"symbols": [], "family": None, "params": None, "why_not": "no instrument named"},
        "text", {"EURUSD"})
    assert found == {}
    assert "no instrument named" in why


# ------------------------------------------------- 3. only compile_row may mint a candidate

def test_a_recovered_row_goes_back_through_the_compiler(monkeypatch) -> None:
    """The reader must not be a second admission door into the candidate store."""
    seen: dict = {}

    def fake_compile(source, row, universe):     # noqa: ARG001
        seen["row"] = row
        return [{"symbol": "EURUSD", "family": "session_range_breakout"}], "EXACT_RECIPE"

    monkeypatch.setattr(dw, "compile_row", fake_compile)
    out, disposition = dw.work_task(_TASK, {"EURUSD"}, chat=_chat({
        "symbols": ["EURUSD"], "family": "session_range_breakout",
        "params": {"lookback": 20}, "evidence": "20-bar lookback",
    }))
    assert disposition == "RECOVERED_EXACT_RECIPE"
    assert out and out[0]["deepened"] is True
    assert seen["row"]["symbols"] == ["EURUSD"], "the recovered symbol must reach the compiler"
    assert seen["row"]["url"] == _TASK["url"], "the original row must be carried, not replaced"


def test_the_compiler_may_still_refuse_a_recovered_row(monkeypatch) -> None:
    """Recovery is not admission. The compiler's verdict stands."""
    monkeypatch.setattr(dw, "compile_row",
                        lambda *a, **k: ([], "NEEDS_EXACT_RULE_EXTRACTION"))
    out, disposition = dw.work_task(_TASK, {"EURUSD"}, chat=_chat({
        "symbols": ["EURUSD"], "family": None, "params": None,
        "evidence": "EURUSD London open range breakout",
    }))
    assert out == []
    assert disposition == "STILL_NEEDS_EXACT_RULE_EXTRACTION"


def test_a_rejected_extraction_never_reaches_the_compiler(monkeypatch) -> None:
    called = []
    monkeypatch.setattr(dw, "compile_row", lambda *a, **k: called.append(1) or ([], "X"))
    out, disposition = dw.work_task(_TASK, {"EURUSD"}, chat=_chat({
        "symbols": ["EURUSD"], "family": None, "params": None,
        "evidence": "a sentence that is nowhere in the row",
    }))
    assert out == [] and disposition.startswith("REJECTED")
    assert not called, "a rejected extraction must not be compiled"


# ------------------------------------------------- 4. a decision is paid for once

def test_a_task_id_is_stable_across_queue_rebuilds() -> None:
    """The queue is rewritten hourly; identity must come from the row, not its position."""
    a = dict(_TASK)
    b = dict(_TASK)
    b["disposition"] = "NEEDS_EXACT_RULE_EXTRACTION"      # compiler re-dispositioned it
    assert dw.task_id(a) == dw.task_id(b)
    c = dict(_TASK, url="https://example.invalid/other")
    assert dw.task_id(c) != dw.task_id(a)


def test_worked_ids_survives_a_corrupt_line(tmp_path, monkeypatch) -> None:
    led = tmp_path / "worked.jsonl"
    led.write_text('{"id":"aaa"}\nnot json\n{"no_id":1}\n{"id":"bbb"}\n', encoding="utf-8")
    monkeypatch.setattr(dw, "WORKED", led)
    assert dw.worked_ids() == {"aaa", "bbb"}


# ------------------------------------------------- 5. robustness of the batch

def test_a_reply_that_is_not_json_is_a_rejection_not_a_crash() -> None:
    found, why = dw.extract(_TASK, chat=_chat("I think you should trade EURUSD!"))
    assert found == {} and "not a JSON object" in why


def test_a_fenced_json_reply_is_still_read() -> None:
    body = '```json\n{"symbols":["EURUSD"],"family":null,"params":null,' \
           '"evidence":"20-bar lookback"}\n```'
    found, why = dw.extract(_TASK, chat=_chat(body))
    assert why == "", why
    assert found["symbols"] == ["EURUSD"]


def test_a_seat_error_is_reported_never_raised() -> None:
    def chat(prompt, **kw):        # noqa: ARG001
        return "", "budget exhausted"
    found, why = dw.extract(_TASK, chat=chat)
    assert found == {} and "budget exhausted" in why
