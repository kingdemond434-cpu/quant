"""BEHAVIOURAL tests for the decision dataset: eleven ledgers in, one versioned row per decision.

Pinned here, because each one is a way the join can be quietly wrong:

  * one row per (sleeve, symbol, side, minute), and a side-less refusal carrying a bracket in
    `detail` becomes one row per LEG -- the release identity refuses two orders, not one;
  * an intent with no decision row at its key IS the decision (the family and scalp lanes never
    write a decision row), and an intent that a decision row already claimed is not a second row;
  * provenance names every ledger that contributed, by physical line offset, so any number on a
    row can be walked back to the line it came from;
  * a re-run over unchanged ledgers writes ZERO lines -- both because the watermark skips the
    primary lines it consumed and because `append` refuses a fingerprint already on file;
  * an outcome that RESOLVES later is a new VERSION of the same row_id, and `latest` is the
    truth; `read` filters by schema version so a consumer can pin the shape it was written for.
"""
from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from libs.research.decision_dataset import (
    JOIN_RULES,
    LEDGER_FILES,
    LEDGER_NAMES,
    SCHEMA_VERSION,
    DatasetRow,
    Watermark,
    append,
    join,
    latest,
    ledger_counts,
    load_ledgers,
    minute_of,
    pending_ids,
    read,
    row_id,
)

T0 = datetime(2026, 9, 1, 10, 0, tzinfo=UTC)


def _iso(minutes: float = 0.0) -> str:
    return (T0 + timedelta(minutes=minutes)).isoformat()


def _write(base: Path, name: str, rows: list[dict[str, Any]]) -> None:
    p = base / LEDGER_FILES[name]
    p.parent.mkdir(parents=True, exist_ok=True)
    if p.suffix == ".json":
        p.write_text(json.dumps(rows[0]), "utf-8")
        return
    p.write_text("".join(json.dumps(r) + "\n" for r in rows), "utf-8")


def desk(base: Path) -> Path:
    """A synthetic box: three decisions (one taken, one vetoed, one side-less refusal), one lone
    scalp intent, and every world-state and outcome ledger the join rules name."""
    _write(base, "decision_ledger", [
        {"time": _iso(0), "sleeve": "gold_break", "symbol": "XAUUSD", "side": "buy_stop",
         "lot": 0.1, "price": 2000.0, "sl": 1990.0, "tp": 2020.0, "taken": True,
         "reason": "placed", "ticket": 5001, "state_vector_id": "sv1", "release_id": "rel1"},
        {"time": _iso(1), "sleeve": "gold_break", "symbol": "XAUUSD", "side": "sell_stop",
         "lot": 0.1, "price": 1980.0, "sl": 1990.0, "tp": 1960.0, "taken": False,
         "reason": "regime_hibernate", "state_vector_id": "sv1"},
        # the release identity refusing new risk: no side, the whole bracket in `detail`
        {"time": _iso(2), "sleeve": "fx_break", "symbol": "EURUSD", "taken": False,
         "reason": "release_identity_refused",
         "detail": {"buy_stop": {"price": 1.10, "sl": 1.09, "tp": 1.12},
                    "sell_stop": {"price": 1.08, "sl": 1.09, "tp": 1.06}}},
    ])
    _write(base, "order_intents", [
        {"time": _iso(0), "sleeve": "gold_break", "symbol": "XAUUSD", "side": "buy_stop",
         "lot": 0.1, "intended": 2000.0, "sl": 1990.0, "tp": 2020.0, "ticket": 5001,
         "retcode": 10008, "decision_bid": 1995.0, "decision_ask": 1995.3,
         "spread_at_decision": 0.3, "order_type": "pending_stop", "state_vector_id": "sv1",
         "policy_advice": {"policy": "PENDING", "utility": 0.12,
                           "alternatives": {"market": 0.10, "limit": 0.11}}},
        # the scalp lane: an intent with no decision row is itself the decision
        {"time": _iso(5), "sleeve": "scalp_x", "symbol": "EURUSD", "side": "buy", "lot": 0.05,
         "intended": 1.1000, "sl": 1.0950, "tp": 1.1100, "ticket": 6001, "retcode": 10009,
         "order_type": "market"},
    ])
    _write(base, "live_ledger", [
        {"time": _iso(180), "sleeve": "gold_break", "symbol": "XAUUSD", "side": 0, "order": 5001,
         "entry_price": 2000.5, "fill_price": 2020.0, "volume": 0.1, "r_multiple": 1.95,
         "pl_quote": 195.0, "deal": 9001, "commission": 0.45, "swap": 0.0},
    ])
    _write(base, "theoretical_positions", [
        {"kind": "target", "at": _iso(-60), "sleeve": "gold_break", "symbol": "XAUUSD",
         "lots": 0.0, "reason": "flat", "price": 1995.0},
    ])
    _write(base, "execution_algo_outcomes", [
        {"at": _iso(0.03), "algo": "market", "symbol": "XAUUSD", "side": "buy", "lots": 0.1,
         "expected_cost": 1e-4, "realised_cost": 3e-4, "filled_frac": 1.0,
         "expected_p_fill": 1.0},
    ])
    _write(base, "broker_clock", [{"utc_offset_hours": 3.0}])
    _write(base, "pf_forecast_log", [
        {"t": _iso(-120), "mode": "live", "total_heat": 0.2, "binding": "ceiling",
         "expected_log_per_day": 0.0011, "book": {"gold_break": 0.02, "scalp_x": 0.01},
         "regime": {"risk_on": 0.6}},
    ])
    _write(base, "capital_modifier_ledger", [
        {"t": _iso(-30), "sleeve": "gold_break", "category": "NORMAL", "multiplier": 1.0,
         "state": "trend_up", "n_state": 41},
    ])
    _write(base, "counterfactuals", [
        {"sleeve": "gold_break", "side": "sell_stop", "time": _iso(1), "status": "REPLAYED",
         "r": -0.8, "exit_reason": "stop"},
    ])
    _write(base, "action_counterfactuals", [
        {"sleeve": "gold_break", "entry_time": _iso(0), "hold": "WORSE", "bars_held": 10,
         "opposite_r": -1.2},
    ])
    _write(base, "excursions", [
        {"sleeve": "gold_break", "entry_time": _iso(0), "mfe_r": 2.1, "mae_r": -0.4},
    ])
    return base


# ------------------------------------------------------------------ the join

def test_every_ledger_has_a_written_join_rule() -> None:
    """The contract is stated at runtime, not only in prose: a ledger added without a rule is a
    join nobody can audit."""
    assert set(JOIN_RULES) == set(LEDGER_NAMES) == set(LEDGER_FILES)


def test_one_row_per_decision_minute_with_provenance(tmp_path: Path) -> None:
    rows = join(load_ledgers(desk(tmp_path)))
    keys = {(r.sleeve, r.symbol, r.side, r.minute) for r in rows}
    assert len(rows) == len(keys) == 5, [r.to_row()["chosen_action"]["reason"] for r in rows]
    assert ("gold_break", "XAUUSD", "buy_stop", minute_of(_iso(0))) in keys
    # the side-less refusal became one row per LEG
    assert ("fx_break", "EURUSD", "buy_stop", minute_of(_iso(2))) in keys
    assert ("fx_break", "EURUSD", "sell_stop", minute_of(_iso(2))) in keys
    # the lone scalp intent IS a decision
    assert ("scalp_x", "EURUSD", "buy", minute_of(_iso(5))) in keys

    taken = next(r for r in rows if r.sleeve == "gold_break" and r.side == "buy_stop")
    assert taken.row_id == row_id("XAUUSD", "gold_break", "buy_stop", minute_of(_iso(0)) or "")
    # every ledger that contributed is named, by physical line offset
    for name in ("decision_ledger", "order_intents", "live_ledger", "theoretical_positions",
                 "execution_algo_outcomes", "broker_clock", "pf_forecast_log",
                 "capital_modifier_ledger", "action_counterfactuals", "excursions"):
        assert taken.provenance[name] == [0], name
    assert taken.provenance["source"] == "decision_ledger"


def test_the_row_carries_world_state_choice_and_outcome(tmp_path: Path) -> None:
    rows = join(load_ledgers(desk(tmp_path)))
    taken = next(r for r in rows if r.sleeve == "gold_break" and r.side == "buy_stop")
    ws = taken.world_state
    assert taken.world_state_id == "sv1"
    assert ws["allocator"]["h"] == 0.02 and ws["allocator"]["binding"] == "ceiling"
    assert ws["broker_hour"] == 13 and ws["broker_utc_offset_hours"] == 3.0
    assert ws["capital_modifier"]["category"] == "NORMAL"
    assert ws["quote"]["spread"] == 0.3 and ws["position"]["lots"] == 0.0
    chosen = taken.chosen_action
    assert chosen["kind"] == "enter" and chosen["policy"] == "PENDING"
    assert chosen["execution"] == "pending_stop" and chosen["ticket"] == 5001
    out = taken.outcome
    assert out["status"] == "RESOLVED" and out["join_key"] == "ticket"
    assert out["r_multiple"] == 1.95 and out["deal"] == 9001
    assert out["execution"]["realised_cost_frac"] == 3e-4
    assert out["mfe_r"] == 2.1 and out["prior_hold"]["hold"] == "WORSE"
    # the candidate menu is on the row, alternatives and all
    assert {c["kind"] for c in taken.candidate_actions} == {"enter", "skip"}
    enter = next(c for c in taken.candidate_actions if c["kind"] == "enter")
    assert enter["policy_alternatives"] == {"market": 0.10, "limit": 0.11}

    vetoed = next(r for r in rows if r.side == "sell_stop" and r.sleeve == "gold_break")
    assert vetoed.chosen_action["kind"] == "skip"
    assert vetoed.chosen_action["veto_reason"] == "regime_hibernate"
    assert vetoed.outcome["status"] == "NOT_APPLICABLE"
    assert vetoed.outcome["prior_counterfactual"]["r"] == -0.8


def test_an_intent_a_decision_already_claimed_is_not_a_second_row(tmp_path: Path) -> None:
    rows = join(load_ledgers(desk(tmp_path)))
    at_minute = [r for r in rows if r.minute == minute_of(_iso(0))]
    assert len(at_minute) == 1
    assert at_minute[0].provenance["order_intents"] == [0]


# ------------------------------------------------------------------ the watermark

def test_a_rerun_over_unchanged_ledgers_writes_nothing(tmp_path: Path) -> None:
    base = desk(tmp_path)
    ledgers = load_ledgers(base)
    path = base / "data" / "decision_dataset.jsonl"
    rows = join(ledgers)
    assert append(rows, path) == len(rows)

    counts = ledger_counts(ledgers)
    # the watermark skips every primary line it consumed, so a settled pass costs nothing...
    assert join(ledgers, since=counts, pending=[]) == []
    # ...while a row still PENDING or UNPRICED is deliberately re-joined, because its outcome or
    # its counterfactual can only arrive later. That re-join must still not double count:
    mark = Watermark(ledger_lines=counts, pending=pending_ids(r.to_row() for r in rows))
    assert len(join(ledgers, since=mark.ledger_lines, pending=mark.pending)) == len(rows)
    assert append(join(ledgers, since=mark.ledger_lines, pending=mark.pending), path) == 0
    # and even ignoring the watermark entirely, identical content appends nothing
    assert append(join(ledgers), path) == 0
    assert len(list(read(path))) == len(rows)


def test_the_watermark_knows_when_a_pass_would_find_no_work(tmp_path: Path) -> None:
    ledgers = load_ledgers(desk(tmp_path))
    counts = ledger_counts(ledgers)
    assert not Watermark().unchanged(counts)          # never run: there is work
    assert Watermark(ledger_lines=counts).unchanged(counts)
    assert not Watermark(ledger_lines=counts, pending=["abc"]).unchanged(counts)
    grew = {**counts, "decision_ledger": counts["decision_ledger"] + 1}
    assert not Watermark(ledger_lines=counts).unchanged(grew)


def test_the_watermark_round_trips_through_a_file(tmp_path: Path) -> None:
    p = tmp_path / "wm.json"
    Watermark(ledger_lines={"decision_ledger": 3}, pending=["a"], rows_written=5, runs=2,
              last_run_utc="2026-09-01T10:00:00+00:00").save(p)
    back = Watermark.load(p)
    assert back.ledger_lines == {"decision_ledger": 3} and back.pending == ["a"]
    assert back.rows_written == 5 and back.runs == 2
    assert Watermark.load(tmp_path / "absent.json").ledger_lines == {}


def test_a_ledger_line_that_grows_produces_exactly_the_new_row(tmp_path: Path) -> None:
    base = desk(tmp_path)
    ledgers = load_ledgers(base)
    counts = ledger_counts(ledgers)
    path = base / "data" / "decision_dataset.jsonl"
    append(join(ledgers), path)

    with (base / LEDGER_FILES["decision_ledger"]).open("a", encoding="utf-8") as fh:
        fh.write(json.dumps({"time": _iso(9), "sleeve": "gold_break", "symbol": "XAUUSD",
                             "side": "buy_stop", "price": 2010.0, "sl": 2000.0, "taken": False,
                             "reason": "margin_guard"}) + "\n")
    fresh = join(load_ledgers(base), since=counts, pending=[])
    assert [r.minute for r in fresh] == [minute_of(_iso(9))]
    assert append(fresh, path) == 1


# ------------------------------------------------------------------ versions

def test_a_resolved_outcome_is_a_new_version_and_latest_is_the_truth(tmp_path: Path) -> None:
    path = tmp_path / "dataset.jsonl"
    base = DatasetRow(row_id="abc", minute=minute_of(_iso(0)) or "", symbol="XAUUSD",
                      sleeve="gold_break", side="buy_stop", world_state_id="sv1",
                      world_state={}, candidate_actions=[], chosen_action={"kind": "enter"},
                      outcome={"status": "PENDING"})
    assert append([base], path) == 1
    assert append([base], path) == 0                                  # nothing changed
    resolved = DatasetRow(**{**base.__dict__, "outcome": {"status": "RESOLVED",
                                                          "r_multiple": 1.9}})
    assert append([resolved], path) == 1
    rows = list(read(path))
    assert [r["version"] for r in rows] == [1, 2]
    assert latest(path)["abc"]["outcome"]["r_multiple"] == 1.9
    # PENDING outcome and UNPRICED counterfactual are BOTH reasons to revisit: a row is only
    # finished when the deal has closed AND the alternatives have been priced.
    assert pending_ids(rows) == ["abc"]
    done = {**rows[1], "counterfactual_outcomes": {"status": "PRICED"}}
    assert pending_ids([done]) == []


def test_the_reader_yields_rows_by_schema_version(tmp_path: Path) -> None:
    path = tmp_path / "dataset.jsonl"
    append([DatasetRow(row_id="v1", minute=_iso(0), symbol="X", sleeve="s", side="buy",
                       world_state_id="", world_state={}, candidate_actions=[],
                       chosen_action={}, outcome={})], path)
    assert len(list(read(path, schema_version=SCHEMA_VERSION))) == 1
    assert list(read(path, schema_version=SCHEMA_VERSION + 99)) == []
    assert list(read(tmp_path / "absent.jsonl")) == []


# ------------------------------------------------------------------ the gateway's own writer

def test_the_ledger_writer_produces_a_line_this_join_reads(tmp_path: Path) -> None:
    """THE GATEWAY HANDOFF. `_record_decision`'s replacement is one `write_decision` call, and
    the line it writes must satisfy two readers at once: this join, and `counterfactual_markout`,
    which is keyed on the LEGACY names (`time`, `state_vector_id`, `taken`). Both are pinned
    here, because a writer that silences one of them costs a whole feedback engine."""
    from libs.research.decision_ledger import read as read_decisions
    from libs.research.decision_ledger import write_decision

    path = tmp_path / LEDGER_FILES["decision_ledger"]
    # exactly the keyword dict the gateway calls with, plus the fields the counterfactual world
    # needs and the gateway now defaults
    assert write_decision(path, {
        "sleeve": "gold_break", "symbol": "XAUUSD", "side": "buy_stop", "lot": 0.1,
        "price": 2000.0, "sl": 1990.0, "tp": 2020.0, "taken": False,
        "reason": "regime_hibernate", "detail": "sleeve hibernated for the day",
        "decided_at": _iso(0), "state_vector_id": "sv1", "release_id": "rel1",
        "size_mult": 0.5, "execution": "pending_stop", "exit_rule": "fixed_tp",
        "portfolio_context": {"total_heat": 0.2, "h": 0.02}})

    line = json.loads(path.read_text("utf-8").splitlines()[0])
    # the legacy names counterfactual_markout joins on, kept verbatim beside the canonical ones
    assert line["time"] == _iso(0) and line["state_vector_id"] == "sv1"
    assert line["taken"] is False and line["detail"] == "sleeve hibernated for the day"
    # the full record the counterfactual world needs
    assert line["size_mult"] == 0.5 and line["exit_rule"] == "fixed_tp"
    assert line["veto_reason"] == "regime_hibernate"
    assert line["portfolio_context"]["h"] == 0.02
    assert line["outcome"] == "SIGNAL_REJECTED"

    back = read_decisions(path)
    assert len(back) == 1 and back[0].rejected and back[0].size_mult == 0.5

    # and the dataset's join reads the very same line
    rows = join({"decision_ledger": [(0, line)]})
    assert len(rows) == 1
    assert rows[0].chosen_action["size_mult"] == 0.5
    assert rows[0].chosen_action["veto_reason"] == "regime_hibernate"
    assert rows[0].world_state_id == "sv1"


def test_the_writer_never_raises_on_the_money_path(tmp_path: Path) -> None:
    """A ledger fault must cost a row and never an order."""
    from libs.research.decision_ledger import write_decision

    said: list[str] = []
    # a directory where the file should be: the append cannot succeed, and must not raise
    blocked = tmp_path / "blocked.jsonl"
    blocked.mkdir()
    assert write_decision(blocked, {"sleeve": "s", "taken": True, "reason": "placed"},
                          log=said.append) is False
    assert said and "non-fatal" in said[0]


def test_a_torn_line_is_skipped_and_never_fatal(tmp_path: Path) -> None:
    base = desk(tmp_path)
    with (base / LEDGER_FILES["decision_ledger"]).open("a", encoding="utf-8") as fh:
        fh.write('{"time": "2026-09-01T10:0')                          # a half-written line
    rows = join(load_ledgers(base))
    assert len(rows) == 5
