"""The theoretical-position netting engine and the execution-algorithm registry.

What is pinned:

  * two sleeves long and short one symbol net to FLAT at the venue (route sends nothing) while
    each sleeve's attribution is whole and opposite -- netting changes what the broker sees,
    never what an edge is credited with;
  * `delta` is net target less account position and follows partial fills exactly; `route`
    sends the remainder and only the remainder;
  * re-stating a target a sleeve already holds appends nothing, so a per-minute re-assertion
    does not grow the ledger; the ledger replays to the same book after a restart and counts,
    rather than guesses at, unreadable rows;
  * `route` rounds to the lot step and refuses (lots 0, why) under the minimum lot, carrying
    the remainder forward; every distinct decision is recorded once;
  * `book_savings` / `savings_report(book)` report gross, opposing, share, spread saved, the
    carried opposition and the routing tally, and reach the same verdict vocabulary as the
    intent-ledger report;
  * TWAP splits lots evenly across slices and sums to the parent, on the lot grid when given
    one; iceberg never displays more than `display_lots`; sniper is a wait then a market child;
  * with no edge every algorithm's utility is at or below zero, SKIP wins and `compete` reports
    no positive algorithm; with edge, the competition ranks and `execution_policy.choose` carries
    the registry's summary additively when -- and only when -- a surface is supplied;
  * the surface is consulted (a duck-typed one changes the ranking) and `scoreboard` aggregates
    recorded outcomes per algorithm, with a never-filled algorithm showing null, not zero.
"""
from __future__ import annotations

import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest

_DESK = Path(__file__).resolve().parents[1]
if str(_DESK) not in sys.path:
    sys.path.insert(0, str(_DESK))

from mt5desk import execution_policy, execution_registry, fill_surface, netting  # noqa: E402

T0 = datetime(2026, 9, 1, 10, tzinfo=UTC)
T1 = datetime(2026, 9, 1, 11, tzinfo=UTC)
T2 = datetime(2026, 9, 3, 11, tzinfo=UTC)


def _intent(lots: float = 0.2, *, edge_r: float = 0.3, spread_frac: float = 1e-4
            ) -> execution_registry.Intent:
    return execution_registry.Intent("XAUUSD", "buy", lots, 3000.0, stop_frac=0.004,
                                     edge_r=edge_r, spread_frac=spread_frac, atr_frac=0.003,
                                     hour=10, sleeve="A")


class _SizeAwareSurface:
    """A duck-typed surface where slip grows with size and resting orders fill half the time:
    enough to show the schedulers consult it rather than the spread prior."""

    note = "stub: size-aware"

    def expected_slip(self, row: dict[str, Any], spread_frac_prior: float) -> tuple[float, float]:
        return 1e-5 + 5e-4 * float(row["lot"]), spread_frac_prior

    def p_fill(self, row: dict[str, Any]) -> float:
        return 0.5


# --------------------------------------------------------------------------- netting engine
def test_opposite_sleeves_net_to_flat_while_attribution_keeps_both_whole(tmp_path) -> None:
    book = netting.TheoreticalBook(tmp_path / "ledger.jsonl")
    book.set_target("A", "XAUUSD", 0.2, "trend long", T0, price=3000.0)
    book.set_target("B", "XAUUSD", -0.2, "carry short", T1, price=3000.0)
    assert book.theoretical("XAUUSD") == {"A": 0.2, "B": -0.2}
    assert book.net_target("XAUUSD") == 0.0 and book.delta("XAUUSD") == 0.0
    rt = netting.route(book, "XAUUSD", 3010.0, lot_step=0.01, lot_min=0.01)
    assert rt["side"] == "flat" and rt["lots"] == 0.0 and "net to flat" in rt["why"]
    assert rt["gross_lots"] == pytest.approx(0.4) and rt["netted_lots"] == pytest.approx(0.4)
    assert {c["sleeve"]: c["outstanding"] for c in rt["sleeves"]} == {"A": 0.2, "B": -0.2}
    # Each sleeve is marked from its own entry: equal and opposite, account shows none.
    attr = book.attribution("XAUUSD", 3010.0, point_value=100.0)
    assert attr["A"] == pytest.approx(200.0) and attr["B"] == pytest.approx(-200.0)
    assert book.account_position("XAUUSD") == 0.0
    snap = book.snapshot()["symbols"]["XAUUSD"]
    assert snap["net_target"] == 0.0 and snap["sleeves"]["B"]["avg_entry"] == 3000.0


def test_delta_follows_partial_fills_and_route_sends_only_the_remainder() -> None:
    book = netting.TheoreticalBook(persist=False)
    book.set_target("A", "XAUUSD", 0.2, "long", T0, price=3000.0)
    book.set_target("B", "XAUUSD", -0.05, "short", T0, price=3000.0)
    assert book.delta("XAUUSD") == pytest.approx(0.15)
    # One net fill from the venue is allocated to the sleeve whose outstanding has its sign.
    rows = book.allocate_fill("XAUUSD", 0.10, 3000.5, T0)
    assert [(r["sleeve"], r["lots"]) for r in rows] == [("A", 0.1)]
    assert book.account_position("XAUUSD") == pytest.approx(0.10)
    assert book.delta("XAUUSD") == pytest.approx(0.05)
    rt = netting.route(book, "XAUUSD", 3000.5)
    assert rt["side"] == "buy" and rt["lots"] == pytest.approx(0.05) and rt["why"] is None
    book.fill("A", "XAUUSD", 0.05, 3000.6, T0)
    assert book.delta("XAUUSD") == 0.0
    out = {c["sleeve"]: c["outstanding"] for c in book.contributions("XAUUSD")}
    assert out == {"A": pytest.approx(0.05), "B": pytest.approx(-0.05)}    # sum == delta == 0
    assert book.theoretical("XAUUSD") == {"A": 0.2, "B": -0.05}            # ledger stays whole
    assert book.fill("A", "XAUUSD", 0.0, 3000.0) is None                    # a zero fill: no row


def test_targets_are_idempotent_and_the_ledger_replays(tmp_path) -> None:
    path = tmp_path / "ledger.jsonl"
    book = netting.TheoreticalBook(path)
    assert book.set_target("A", "XAUUSD", 0.2, "long", T0, price=3000.0)["appended"]
    assert not book.set_target("A", "XAUUSD", 0.2, "long", T1, price=3001.0)["appended"]
    assert not book.set_target("Z", "XAUUSD", 0.0, "never held", T1)["appended"]
    assert book.rows == 1 and len(path.read_text("utf-8").splitlines()) == 1
    assert book.set_target("A", "XAUUSD", 0.3, "add", T1, price=3010.0)["appended"]
    book.fill("A", "XAUUSD", 0.1, 3000.2, T1)
    with path.open("a", encoding="utf-8") as f:
        f.write("{not json\n")
    again = netting.TheoreticalBook(path)
    assert again.rows == 3 and again.unreadable == 1
    assert again.theoretical("XAUUSD") == book.theoretical("XAUUSD")
    assert again.delta("XAUUSD") == book.delta("XAUUSD") == pytest.approx(0.2)
    # Lot-weighted entry survives the restart: 0.2 @ 3000 + 0.1 @ 3010 -> 3003.333...
    assert again.attribution("XAUUSD", 3003.3333333) == pytest.approx({"A": 0.0}, abs=1e-6)
    assert again.snapshot()["unreadable"] == 1
    unmarked = netting.TheoreticalBook(persist=False)
    unmarked.set_target("U", "EURUSD", 0.1, "no mark", T0)
    assert unmarked.attribution("EURUSD", 1.1) == {}                        # omitted, not zero
    assert unmarked.snapshot()["symbols"]["EURUSD"]["unmarked"] == ["U"]


def test_route_rounds_to_the_lot_step_and_refuses_under_lot_min() -> None:
    book = netting.TheoreticalBook(persist=False)
    book.set_target("A", "EURUSD", 0.117, "x", T0)
    book.set_target("B", "EURUSD", -0.05, "y", T0)
    assert netting.route(book, "EURUSD", 1.1, lot_step=0.01)["lots"] == pytest.approx(0.07)
    book.set_target("A", "EURUSD", 0.104, "x", T0)
    book.set_target("B", "EURUSD", -0.10, "y", T0)
    refused = netting.route(book, "EURUSD", 1.1, lot_step=0.01, lot_min=0.01)
    assert refused["lots"] == 0.0 and refused["delta"] == pytest.approx(0.004)
    assert "under lot_min" in refused["why"] and "carried forward" in refused["why"]
    book.set_target("A", "EURUSD", 0.106, "x", T0)
    sent = netting.route(book, "EURUSD", 1.1, lot_step=0.01, lot_min=0.01)
    assert sent["lots"] == pytest.approx(0.01) and sent["why"] is None
    assert netting.route(book, "EURUSD", 1.1, lot_step=0.01, lot_min=0.05)["lots"] == 0.0
    # The same decision twice is one recorded route; a changed one is another.
    netting.route(book, "EURUSD", 1.1, lot_step=0.01, lot_min=0.05)
    assert len(book.routes) == 4


def test_book_savings_report_numbers(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(netting, "REPORT_BOOK", tmp_path / "NETTING_BOOK.json")
    book = netting.TheoreticalBook(persist=False)
    book.set_target("A", "XAUUSD", 0.2, "long", T0, price=3000.0)
    book.set_target("B", "XAUUSD", -0.1, "short", T1, price=3000.0)
    book.set_target("B", "XAUUSD", -0.2, "more short", T2, price=3000.0)   # outside the window
    book.set_target("D", "EURUSD", 0.1, "long", T0, price=1.1)
    netting.route(book, "XAUUSD", 3000.0)
    rep = netting.book_savings(book, write=True, spread_frac={"XAUUSD": 1e-4})
    xau = rep["per_symbol"]["XAUUSD"]
    assert xau["gross_lots"] == pytest.approx(0.4) and xau["opposing_lots"] == pytest.approx(0.2)
    assert xau["share"] == pytest.approx(0.5)
    assert xau["spread_saved_frac"] == pytest.approx(0.2 * 1e-4)
    assert rep["per_symbol"]["EURUSD"]["spread_saved_frac"] is None      # no spread supplied
    assert rep["gross_lots"] == pytest.approx(0.5) and rep["opposing_lots"] == pytest.approx(0.2)
    assert rep["opposing_share"] == pytest.approx(0.4)
    assert rep["carried"]["XAUUSD"] == {"gross_lots": 0.4, "net_lots": 0.0, "saved_lots": 0.4,
                                        "opposing": True}
    assert rep["carried"]["EURUSD"]["opposing"] is False
    assert rep["routed"] == {"n": 1, "sent_lots": 0.0, "netted_lots": 0.4, "refused": 1}
    assert rep["verdict"] == "NETTING_WORTH_ROUTING" and rep["source"] == "theoretical_book"
    written = json.loads((tmp_path / "NETTING_BOOK.json").read_text("utf-8"))
    assert written["rows"] == 4 and written["ledger"] is None          # in-memory book, 4 rows
    # The intent-ledger entry point dispatches on the book and keeps its own semantics intact.
    via = netting.savings_report(book, write=False)
    assert via["source"] == "theoretical_book" and via["verdict"] == rep["verdict"]
    assert netting.savings_report([], write=False)["verdict"] == "UNMEASURED"


# --------------------------------------------------------------------------- algorithm registry
def test_registry_lists_every_scheduler_and_none_touches_the_terminal() -> None:
    assert set(execution_registry.REGISTRY) == {"market", "twap", "iceberg", "sniper", "pullback"}
    assert all(callable(fn) for fn in execution_registry.REGISTRY.values())
    for mod in (netting, execution_registry, execution_policy):
        assert "MetaTrader5" not in Path(mod.__file__).read_text("utf-8")


def test_twap_splits_evenly_and_sums_to_the_parent() -> None:
    fs = fill_surface.FillSurface()
    plan = execution_registry.twap(_intent(0.2), slices=4, horizon_s=600, surface=fs)
    assert plan.algo == "twap" and len(plan.children) == 4
    assert [c["lots"] for c in plan.children] == [0.05] * 4
    assert sum(c["lots"] for c in plan.children) == pytest.approx(plan.lots) == pytest.approx(0.2)
    assert [c["at_offset_s"] for c in plan.children] == [0.0, 150.0, 300.0, 450.0]
    assert all(c["kind"] == "market" for c in plan.children)
    assert plan.children[0]["condition"] is None and plan.children[1]["condition"] == "clock"
    assert 0.0 < plan.edge_kept < 1.0 and plan.p_fill == 1.0
    on_grid = execution_registry.twap(_intent(0.1), slices=4, lot_step=0.01, surface=fs)
    assert [c["lots"] for c in on_grid.children] == [0.03, 0.03, 0.02, 0.02]
    assert sum(c["lots"] for c in on_grid.children) == pytest.approx(0.1)


def test_iceberg_never_displays_more_than_display_lots() -> None:
    fs = fill_surface.FillSurface()
    plan = execution_registry.iceberg(_intent(0.1), display_lots=0.03, surface=fs)
    shown = [c for c in plan.children if c["kind"] == "limit"]
    assert len(shown) == len(plan.children) == 4
    assert max(c["lots"] for c in shown) <= 0.03
    assert sum(c["lots"] for c in plan.children) == pytest.approx(0.1)
    assert [c["condition"] for c in plan.children][1:] == ["after_fill:0", "after_fill:1",
                                                            "after_fill:2"]
    assert plan.detail["display_lots"] == 0.03 and plan.detail["replenish"] is True
    sweep = execution_registry.iceberg(_intent(0.1), display_lots=0.03, replenish=False,
                                       surface=fs)
    assert [(c["kind"], c["lots"]) for c in sweep.children] == [("limit", 0.03), ("market", 0.07)]
    whole = execution_registry.iceberg(_intent(0.1), display_lots=0.5, surface=fs)
    assert len(whole.children) == 1 and whole.children[0]["lots"] == 0.1


def test_sniper_waits_then_markets_and_pullback_rests_then_markets() -> None:
    fs = fill_surface.FillSurface()
    wide = execution_registry.sniper(_intent(0.1, spread_frac=3e-4), max_spread_frac=1e-4,
                                     timeout_s=300, surface=fs)
    assert [c["kind"] for c in wide.children] == ["wait", "market"]
    assert wide.children[0]["lots"] == 0.0 and wide.children[1]["lots"] == 0.1
    assert wide.children[1]["at_offset_s"] == 300.0
    assert "spread_frac<=" in wide.children[0]["condition"]
    assert "timeout:300" in wide.children[1]["condition"]
    assert wide.detail["expected_wait_s"] > 0 and wide.edge_kept < 1.0
    inside = execution_registry.sniper(_intent(0.1), surface=fs)
    assert [c["kind"] for c in inside.children] == ["wait", "market"]
    assert inside.children[1]["at_offset_s"] == 0.0 and inside.edge_kept == 1.0
    pb = execution_registry.pullback(_intent(0.1), offset_frac=0.001, timeout_s=600, surface=fs)
    assert [c["kind"] for c in pb.children] == ["limit", "market"]
    assert pb.children[0]["price_offset_frac"] == 0.001 and pb.children[1]["at_offset_s"] == 600.0
    mk = execution_registry.market(_intent(0.1), surface=fs)
    assert len(mk.children) == 1 and mk.children[0]["kind"] == "market" and mk.p_fill == 1.0


def test_no_edge_means_skip_for_every_algorithm() -> None:
    fs = fill_surface.FillSurface()
    dead = execution_registry.compete(_intent(0.1, edge_r=0.0), fs)
    assert dead["best"] == execution_registry.SKIP and dead["would_trade"] is False
    assert dead["positive"] == [] and dead["errors"] == {}
    assert all(u <= 0.0 for u in dead["utilities"].values())
    assert set(dead["utilities"]) == set(execution_registry.REGISTRY) | {execution_registry.SKIP}
    assert execution_registry.best(_intent(0.1), fs, edge_r=-0.2).algo == execution_registry.SKIP
    # The override path: the same intent with edge trades, and the ranking is by utility.
    live = execution_registry.compete(_intent(0.1, edge_r=0.0), fs, edge_r=0.3)
    assert live["would_trade"] and live["best"] != execution_registry.SKIP
    assert live["best"] == live["ranked"][0] == live["positive"][0]
    us = [live["utilities"][a] for a in live["ranked"]]
    assert us == sorted(us, reverse=True)
    assert execution_registry.summary(live)["best"] == live["best"]


def test_the_surface_is_consulted_and_choose_reports_the_registry_additively() -> None:
    stub = _SizeAwareSurface()
    mk = execution_registry.market(_intent(0.2), surface=stub)
    tw = execution_registry.twap(_intent(0.2), slices=4, horizon_s=60, surface=stub)
    assert tw.cost_frac < mk.cost_frac                      # smaller prints, less modelled slip
    ice = execution_registry.iceberg(_intent(0.2), display_lots=0.1, surface=stub)
    assert ice.p_fill == pytest.approx(0.5)
    comp = execution_registry.compete(_intent(0.2), stub, params={"twap": {"slices": 8}})
    assert comp["plans"]["twap"].detail["slices"] == 8 and comp["surface"] == stub.note
    broken = execution_registry.compete(_intent(0.2), stub, params={"twap": {"nope": 1}})
    assert "twap" in broken["errors"] and "twap" not in broken["utilities"]
    C = execution_policy.Context
    live = C("XAUUSD", "buy", 3000.0, spread_frac=1e-4, atr_frac=0.003, stop_frac=0.004,
             edge_r=0.3, hour=10, lot=0.1)
    bare = execution_policy.choose(live)
    assert "registry" not in bare
    with_surface = execution_policy.choose(live, fill_surface.FillSurface())
    assert set(with_surface) == set(bare) | {"registry"}
    reg = with_surface["registry"]
    assert reg["best"] in execution_registry.REGISTRY and reg["would_trade"]
    assert set(reg["utilities"]) == set(execution_registry.REGISTRY) | {execution_registry.SKIP}
    json.dumps(with_surface)                                # the ledger needs a JSON-safe row
    dead = C("XAUUSD", "buy", 3000.0, spread_frac=1e-3, atr_frac=0.003, stop_frac=0.004,
             edge_r=0.0, hour=10, lot=0.1)
    d = execution_policy.choose(dead, fill_surface.FillSurface())
    assert d["policy"] == "SKIP" and d["registry"]["best"] == execution_registry.SKIP
    assert execution_policy.intent_of(live).price == 3000.0


def test_scoreboard_aggregates_outcomes(tmp_path) -> None:
    path = tmp_path / "outcomes.jsonl"
    fs = fill_surface.FillSurface()
    mk = execution_registry.market(_intent(0.2), surface=fs)
    r1 = execution_registry.record_outcome(mk, [(0.1, 3000.3), (0.1, 3000.6)], path=path, at=T0)
    assert r1["realised_cost"] == pytest.approx(0.00015) and r1["filled_frac"] == 1.0
    r2 = execution_registry.record_outcome(mk, [{"lots": 0.1, "price": 3000.15}], path=path)
    assert r2["realised_cost"] == pytest.approx(5e-5) and r2["filled_frac"] == pytest.approx(0.5)
    tw = execution_registry.twap(_intent(0.2), surface=fs)
    r3 = execution_registry.record_outcome(tw, [], path=path)
    assert r3["realised_cost"] is None and r3["filled_frac"] == 0.0
    assert len(path.read_text("utf-8").splitlines()) == 3
    board = execution_registry.scoreboard(path)
    assert board["n"] == 3 and board["path"] == str(path)
    m = board["algos"]["market"]
    assert m["n"] == 2 and m["n_filled"] == 2
    assert m["mean_realised_cost"] == pytest.approx(1e-4)
    assert m["mean_expected_cost"] == pytest.approx(mk.cost_frac)
    assert m["mean_filled_frac"] == pytest.approx(0.75)
    assert m["mean_surprise"] == pytest.approx(1e-4 - mk.cost_frac)
    t = board["algos"]["twap"]
    assert t["n"] == 1 and t["mean_realised_cost"] is None and t["mean_filled_frac"] == 0.0
    assert execution_registry.scoreboard(rows=[{"algo": "x", "filled_frac": 1.0}])["algos"]["x"] \
        == {"n": 1, "mean_realised_cost": None, "mean_expected_cost": None,
            "mean_filled_frac": 1.0, "mean_surprise": None, "n_filled": 0}
