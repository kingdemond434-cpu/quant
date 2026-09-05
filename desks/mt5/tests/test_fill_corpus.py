"""The fill corpus: the join, the capture-gap report, and the writer that may never stall an order.

Pinned here:

  * a record round-trips through `to_row`/`record_from_row`, and BOTH directions of schema drift
    survive -- an unknown key from a newer writer is ignored, a missing key from an older row
    takes its default. An append-only corpus that cannot be read by the code that follows it is
    not a corpus;
  * `build_records` joins a twin case to the decision ledger, the counterfactual dataset, the
    excursions and the deal, and a field NO ledger carries stays None rather than being defaulted
    to zero;
  * `completeness` names the HANDOFF for every empty column and does not name one for a column
    that is empty by construction (a rejected order has no fill price);
  * markouts are signed in the trade's direction and refuse to answer past the end of the tape;
  * MAE is positive-is-worse and MFE positive-is-better, both against the fill;
  * `CorpusWriter.submit` never blocks and never raises: a full queue DROPS and counts the drop,
    an unwritable path counts an error, and neither costs the caller a millisecond. This is the
    rule the gateway depends on -- a recorder that can stall an order loses money.
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import pytest

_DESK = Path(__file__).resolve().parents[1]
_ROOT = _DESK.parent.parent
for _p in (str(_DESK), str(_DESK / "research"), str(_ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from libs.execution import fill_corpus as fc  # noqa: E402
from libs.execution.digital_twin import join_cases  # noqa: E402

PX = 3000.0
T = "2026-09-05T09:00:00+00:00"


def _case(**over):
    """One TwinCase, through the real join so the test never invents the shape it asserts on."""
    intent = {"time": T, "sleeve": "gold", "symbol": "XAUUSD", "side": "buy", "lot": 0.1,
              "intended": PX, "sl": PX * 0.99, "tp": PX * 1.02, "ticket": 4242,
              "retcode": 10009, "decision_bid": PX - 0.3, "decision_ask": PX,
              "spread_at_decision": 0.3}
    intent.update(over)
    outcome = {"at": T, "algo": "market", "symbol": "XAUUSD", "side": "buy", "lots": 0.1,
               "filled_lots": 0.1, "expected_cost": 1e-4, "realised_cost": 3e-4,
               "filled_frac": 1.0, "expected_p_fill": 1.0}
    cases = join_cases([intent], [outcome], [], asof=T)
    assert len(cases) == 1
    return cases[0]


# --------------------------------------------------------------------------- the record
def test_the_row_round_trips_and_survives_schema_drift_in_both_directions() -> None:
    rec = fc.FillRecord(intent_id="i1", symbol="XAUUSD", realized_r=0.4, slip_r=0.02,
                        alt_exits=[{"exit": "trail", "r": 0.9}])
    back = fc.record_from_row(rec.to_row())
    assert back == rec
    # a newer writer's column is ignored rather than fatal
    row = rec.to_row() | {"a_field_from_next_year": 7}
    assert fc.record_from_row(row).intent_id == "i1"
    # an older writer's row takes defaults for everything it never had
    thin = fc.record_from_row({"intent_id": "i2"})
    assert thin.intent_id == "i2" and thin.realized_r is None and thin.alt_exits == []


def test_the_key_is_stable_and_the_resolution_changes_only_when_the_outcome_does() -> None:
    a = fc.FillRecord(intent_id="i1", filled_at=T, status="UNRESOLVED")
    b = fc.FillRecord(intent_id="i1", filled_at=T, status="FILLED", realized_r=0.4)
    assert a.key == b.key
    assert a.resolution != b.resolution


# --------------------------------------------------------------------------- the join
def test_the_join_pulls_every_ledger_onto_one_row_and_invents_nothing() -> None:
    c = _case()
    recs = fc.build_records(
        [c],
        decisions=[{"intent_id": c.intent_id, "decision_id": "d1", "sleeve": "gold",
                    "symbol": "XAUUSD", "time": T, "reason": "asia_range_break",
                    "strategy_id": "gold_asia", "strategy_dna": {"family": "range_break", "k": 2},
                    "posterior_edge_r": 0.25, "signal_bps": 8.0, "modelled_cost_bps": 1.5,
                    "release_id": "sha", "ticket": 4242, "regime": "trend"}],
        deals=[{"order": 4242, "deal": 99, "symbol": "XAUUSD", "entry_time": T,
                "exit_time": "2026-09-05T11:00:00+00:00", "fill_price": PX + 0.9,
                "exit_reason": "tp", "r_multiple": 0.41, "commission_r": 0.01}],
        # THE SHAPE counterfactual_world.price_row ACTUALLY WRITES: one `alternatives` list,
        # every arm carrying the alpha class it belongs to.
        # `minute` verbatim as decision_dataset writes it: a FULL offset-aware ISO string, not a
        # truncated one. Truncating without normalising is how the join silently misses.
        dataset_rows=[{"row_id": "r1", "sleeve": "gold", "symbol": "XAUUSD", "side": "buy",
                       "minute": T, "world_state": {"cross_asset": {"dxy_z": 1.2}},
                       "counterfactual_outcomes": {"status": "PRICED", "n_arms": 4,
                           "alternatives": [
                               {"class": "SIZING_ALPHA", "arm": "0.5x", "status": "PRICED",
                                "r": 0.2, "d_r": -0.21, "d_elog": -0.001},
                               {"class": "VETO_ALPHA", "arm": "skipped", "status": "PRICED",
                                "r": 0.0, "d_r": -0.41, "d_elog": -0.002},
                               {"class": "EXIT_ALPHA", "arm": "trail", "status": "PRICED",
                                "r": 0.9, "d_r": 0.49, "d_elog": 0.003},
                               {"class": "EXECUTION_ALPHA", "arm": "limit", "status": "PRICED",
                                "r": 0.55, "d_r": 0.14, "d_elog": 0.001},
                               {"class": "EXIT_ALPHA", "arm": "hold",
                                "status": "NOT_TRIGGERED", "r": None}]}}],
        excursions=[{"sleeve": "gold", "entry_time": T, "mfe_r": 1.4, "mae_r": 0.3}],
        release_id="sha")
    assert len(recs) == 1
    r = recs[0]
    assert r.entry_reason == "asia_range_break" and r.strategy_dna["family"] == "range_break"
    assert r.posterior_edge_r == 0.25 and r.signal_bps == 8.0
    assert r.exit_reason == "tp" and r.realized_r == 0.41 and r.deal == 99
    assert r.mfe_r == 1.4 and r.mae_r == 0.3
    assert r.cross_asset == {"dxy_z": 1.2}
    # the exit arm with no R is DROPPED, not written as a null a model would learn from
    assert {a["exit"] for a in r.alt_exits} == {"trail"}
    assert r.alt_exits[0]["d_elog"] == pytest.approx(0.003)
    assert {a["action"] for a in r.alt_entries} == {"0.5x", "skipped"}
    assert {a["style"] for a in r.alt_styles} == {"limit"}
    assert r.prediction_error_r == pytest.approx(0.41 - 0.25)
    assert r.status == "FILLED" and "decision_ledger" in r.sources
    # NOT INVENTED: nothing on this desk records a 5-minute markout yet
    assert r.markout_5m_r is None and r.predicted_r_sd is None


def test_the_minute_join_survives_the_three_timestamp_spellings_the_ledgers_use() -> None:
    """`excursions.jsonl` writes "2026-09-05 09:00:00+00:00" with a SPACE; `decision_dataset`
    writes the offset-aware ISO; the twin's case time is an isoformat(). Truncating each to
    sixteen characters without normalising gives keys that never meet, and the symptom is a
    corpus whose MAE/MFE and counterfactual columns are empty for no visible reason."""
    c = _case()
    r = fc.build_records(
        [c],
        excursions=[{"sleeve": "gold", "entry_time": "2026-09-05 09:00:00+00:00",
                     "mfe_r": 1.4, "mae_r": 0.3}],
        dataset_rows=[{"sleeve": "gold", "symbol": "XAUUSD", "side": "buy_stop",
                       "minute": "2026-09-05T09:00:00+00:00",
                       "counterfactual_outcomes": {"alternatives": [
                           {"class": "EXIT_ALPHA", "arm": "trail", "r": 0.9}]}}])[0]
    assert r.mfe_r == 1.4 and r.mae_r == 0.3
    assert [a["exit"] for a in r.alt_exits] == ["trail"]
    assert r.join_keys["excursions"] == "sleeve_entry_minute"
    assert r.join_keys["dataset"] == "sleeve_symbol_side_min"


def test_a_bracket_s_two_legs_do_not_swap_counterfactuals_in_the_same_minute() -> None:
    """A sleeve places a buy_stop and a sell_stop in the SAME minute. A key without the side
    hands the buy leg's alternatives to the sell leg."""
    buy = _case(side="buy_stop", ticket=1)
    sell = _case(side="sell_stop", ticket=2)
    ds = [{"sleeve": "gold", "symbol": "XAUUSD", "side": s, "minute": T,
           "counterfactual_outcomes": {"alternatives": [
               {"class": "EXIT_ALPHA", "arm": arm, "r": 0.9}]}}
          for s, arm in (("buy_stop", "trail"), ("sell_stop", "hold"))]
    recs = fc.build_records([buy, sell], dataset_rows=ds)
    got = {r.side: [a["exit"] for a in r.alt_exits] for r in recs}
    assert got == {"buy": ["trail"], "sell": ["hold"]}


def test_a_legitimate_zero_is_kept_and_not_replaced_by_a_fallback() -> None:
    """`a or b` discards an exact 0.0. A break-even trade, a momentum z-score sitting on its mean
    and an edge estimate of zero are all real values, and reaching past them for another ledger's
    number puts somebody else's data in the column."""
    c = _case()
    r = fc.build_records(
        [c],
        decisions=[{"sleeve": "gold", "symbol": "XAUUSD", "time": T, "momentum_z": 0.0,
                    "features": {"momentum_z": 9.9}, "predicted_r_mean": 0.0,
                    "posterior_edge_r": 7.7, "ticket": 4242}],
        deals=[{"order": 4242, "r_multiple": 0.0, "holding_s": 0.0}],
        excursions=[{"sleeve": "gold", "entry_time": T, "mae_r": 5.5, "mfe_r": 5.5,
                     "r_multiple": 3.3}],
        tickets={c.intent_id: 4242})[0]
    assert r.momentum_z == 0.0                    # not 9.9
    assert r.realized_r == 0.0                    # not 3.3
    assert r.predicted_r_mean == 0.0              # not 7.7
    assert r.holding_s == 0.0
    assert r.prediction_error_r == 0.0


def test_the_regime_column_reads_the_allocator_s_mixture_as_its_modal_label() -> None:
    """`pf_forecast_log` writes `regime` as a probability mixture over labels, not as a label. A
    reader that looked for a "label" key would leave the column empty forever and the emptiness
    would look like a capture gap rather than a wrong key."""
    r = fc.build_records([_case()], dataset_rows=[
        {"sleeve": "gold", "symbol": "XAUUSD", "side": "buy", "minute": T,
         "world_state": {"allocator": {"regime": {"bull/low_vol": 0.41, "bull/high_vol": 0.20,
                                                  "bull/mid_vol": 0.39}}}}])[0]
    assert r.regime == "bull/low_vol"
    # a decision row that names the regime outright still wins
    r2 = fc.build_records([_case()], decisions=[
        {"sleeve": "gold", "symbol": "XAUUSD", "time": T, "regime": "trend"}])[0]
    assert r2.regime == "trend"
    assert fc.build_records([_case()])[0].regime == ""


def test_a_legacy_flat_counterfactual_block_still_reads() -> None:
    """A corpus reader that only understands today's writer breaks on its own history."""
    c = _case()
    recs = fc.build_records([c], dataset_rows=[
        {"sleeve": "gold", "symbol": "XAUUSD", "minute": T, "side": "buy",
         "counterfactual_outcomes": {"exit": {"trail": {"r": 0.9}},
                                     "execution": {"limit": 0.55},
                                     "entry": {"skip": 0.0}}}])
    r = recs[0]
    assert [a["exit"] for a in r.alt_exits] == ["trail"]
    assert [a["style"] for a in r.alt_styles] == ["limit"]
    assert [a["action"] for a in r.alt_entries] == ["skip"]


def test_a_case_with_no_other_ledger_is_still_a_row_with_the_columns_left_empty() -> None:
    recs = fc.build_records([_case()])
    r = recs[0]
    assert r.symbol == "XAUUSD" and r.slip_r is not None
    assert r.realized_r is None and r.alt_exits == [] and r.strategy_dna == {}


def test_the_ticket_map_is_what_lets_a_deal_reach_the_row() -> None:
    """A TwinCase carries no ticket, so without the map the EXIT half of every row is empty."""
    c = _case()
    deal = [{"order": 4242, "deal": 7, "r_multiple": 0.5, "exit_reason": "sl"}]
    assert fc.build_records([c], deals=deal)[0].realized_r is None
    joined = fc.build_records([c], deals=deal, tickets={c.intent_id: 4242})[0]
    assert joined.realized_r == 0.5 and joined.exit_reason == "sl"


# --------------------------------------------------------------------------- completeness
def test_completeness_names_the_handoff_for_an_empty_column_and_not_for_a_conditional_one():
    comp = fc.completeness(fc.build_records([_case()]))
    assert comp["n_records"] == 1
    assert comp["fields"]["symbol"]["share"] == 1.0
    # a tape column: empty, and the report says WHO has to start writing it
    assert "tick tape" in comp["fields"]["markout_5m_r"]["handoff"]
    assert any("markout_5m_r" in g for g in comp["gaps"])
    # a conditional column: empty because this row is not a closed trade, and NOT a handoff
    assert "handoff" not in comp["fields"]["realized_r"]
    assert not any("realized_r" in g for g in comp["gaps"])
    assert comp["n_trainable"] == 0


# --------------------------------------------------------------------------- tape arithmetic
def _tape(n: int = 400, step_ms: int = 1000, drift: float = 0.0):
    t = [1_000_000 + i * step_ms for i in range(n)]
    bid = [PX + drift * i - 0.1 for i in range(n)]
    ask = [PX + drift * i + 0.1 for i in range(n)]
    return t, bid, ask


def test_a_markout_is_signed_in_the_trade_direction() -> None:
    t, bid, ask = _tape(drift=0.01)          # price rises
    up = fc.markouts_from_ticks(t, bid, ask, fill_ms=t[0], fill_price=PX, direction=1,
                                stop_distance=30.0)
    dn = fc.markouts_from_ticks(t, bid, ask, fill_ms=t[0], fill_price=PX, direction=-1,
                                stop_distance=30.0)
    assert up["markout_5s_r"] > 0 and dn["markout_5s_r"] < 0
    assert up["markout_5s_r"] == pytest.approx(-dn["markout_5s_r"])


def test_a_horizon_past_the_end_of_the_tape_is_none_not_the_last_tick() -> None:
    t, bid, ask = _tape(n=10, drift=0.01)    # ten seconds of tape
    m = fc.markouts_from_ticks(t, bid, ask, fill_ms=t[0], fill_price=PX, direction=1,
                               stop_distance=30.0)
    assert m["markout_1s_r"] is not None and m["markout_5s_r"] is not None
    assert m["markout_30s_r"] is None and m["markout_5m_r"] is None


def test_excursions_are_signed_worse_is_positive_for_mae_and_the_path_is_sampled() -> None:
    t = [0, 1000, 2000, 3000, 4000]
    bid = [PX, PX - 3.1, PX + 6.1, PX - 0.1, PX + 1.9]
    ask = [PX, PX - 2.9, PX + 6.3, PX + 0.1, PX + 2.1]
    e = fc.excursions_from_ticks(t, bid, ask, fill_ms=0, exit_ms=4000, fill_price=PX,
                                 direction=1, stop_distance=10.0)
    assert e["mfe_r"] == pytest.approx(0.62)         # +6.2 on a 10.0 stop
    assert e["mae_r"] == pytest.approx(0.30)         # -3.0 against, reported POSITIVE
    assert len(e["path_r"]) == 5 and e["path_r"][0] == [0.0, 0.0]


def test_a_zero_stop_or_unknown_direction_yields_nothing_rather_than_a_division() -> None:
    t, bid, ask = _tape()
    assert all(v is None for v in
               fc.markouts_from_ticks(t, bid, ask, fill_ms=t[0], fill_price=PX, direction=0,
                                      stop_distance=30.0).values())
    e = fc.excursions_from_ticks(t, bid, ask, fill_ms=t[0], exit_ms=None, fill_price=PX,
                                 direction=1, stop_distance=0.0)
    assert e == {"mfe_r": None, "mae_r": None, "path_r": []}


# --------------------------------------------------------------------------- the writer
def test_the_writer_lands_every_row_it_accepts(tmp_path: Path) -> None:
    p = tmp_path / "corpus.jsonl"
    w = fc.CorpusWriter(p)
    for i in range(50):
        assert w.submit(fc.FillRecord(intent_id=f"i{i}")) is True
    w.close(timeout_s=10.0)
    rows = [json.loads(ln) for ln in p.read_text("utf-8").splitlines()]
    assert len(rows) == 50 and rows[0]["intent_id"] == "i0"
    assert w.stats["dropped"] == 0 and w.stats["lossy"] is False


def test_flush_waits_for_the_bytes_not_merely_for_an_empty_queue(tmp_path: Path) -> None:
    """A row popped off the queue for writing is out of the queue and NOT yet on disk. Flushing
    on `queue.empty()` would return before the last batch landed and a shutdown that trusted it
    would lose exactly the rows written last."""
    p = tmp_path / "c.jsonl"
    w = fc.CorpusWriter(p, batch=8)
    for i in range(200):
        w.submit(fc.FillRecord(intent_id=f"i{i}"))
    assert w.flush(timeout_s=10.0) is True
    assert len(p.read_text("utf-8").splitlines()) == 200
    assert w.stats["written"] == 200
    w.close(timeout_s=5.0)


def test_a_full_queue_drops_and_counts_rather_than_blocking_the_caller(tmp_path: Path) -> None:
    """THE RULE THE GATEWAY DEPENDS ON. A one-slot queue with a wedged drain must still return
    from `submit` immediately -- a stalled order costs more than any record is worth -- and the
    loss must be COUNTED, because a silently lossy corpus is worse than a small one."""
    w = fc.CorpusWriter(tmp_path / "c.jsonl", maxsize=1)
    w._closed = True                     # the drain never starts: every put lands on a full queue
    t0 = time.monotonic()
    ok = [w.submit(fc.FillRecord(intent_id=f"i{i}")) for i in range(500)]
    assert time.monotonic() - t0 < 2.0
    assert ok.count(False) >= 499        # one slot may be taken; the rest are dropped
    assert w.stats["dropped"] >= 499 and w.stats["lossy"] is True


def test_the_writer_never_raises_when_the_path_cannot_be_written(tmp_path: Path) -> None:
    blocker = tmp_path / "not_a_dir"
    blocker.write_text("x", "utf-8")
    w = fc.CorpusWriter(blocker / "corpus.jsonl")
    assert w.submit(fc.FillRecord(intent_id="i1")) is True     # the CALLER never learns
    w.close(timeout_s=5.0)
    assert w.stats["errors"] >= 1 and w.stats["written"] == 0


def test_submit_never_raises_on_a_record_that_cannot_serialise(tmp_path: Path) -> None:
    w = fc.CorpusWriter(tmp_path / "c.jsonl")
    assert w.submit(object()) is False                          # type: ignore[arg-type]
    assert w.stats["errors"] == 1
    w.close(timeout_s=2.0)


def test_append_and_read_are_the_two_halves_of_one_file(tmp_path: Path) -> None:
    p = tmp_path / "c.jsonl"
    assert fc.append_rows(p, []) == 0 and fc.read_rows(p) == []
    fc.append_rows(p, [fc.FillRecord(intent_id="i1"), {"intent_id": "i2"}])
    p.write_text(p.read_text("utf-8") + "{torn\n", "utf-8")      # a torn tail is skipped
    assert [r["intent_id"] for r in fc.read_rows(p)] == ["i1", "i2"]
