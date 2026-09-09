"""The heat cap admits the EXACT gold trade the gateway then sends.

THE DEFECT (external audit, 2026-09-09, second round). Closing the P1 semantic break made the
charge call the same sizer the send calls -- but with different arguments. Before `cap_by_heat`
the gateway had no bracket yet, so it charged
`realised_q(equity, None, ...)` at the HOUSE NOMINAL stop (`DIST_USD`, 19.1 USD/oz); minutes of
code later the placement loop built the real bracket, took `stop_distance(spec)` and sent
`realised_q(equity, dist, ...)`. `auto_lot` is a function of the stop distance, so those are two
different trades, and the desk's own source records what that class of gap costs: "sizing from
the house DIST_USD while the real bracket was in hand made every wide-session sleeve trade
2.5-2.8x its budget".

WHY `max(h_i lot, gold_lot)` DOES NOT PAPER OVER IT. With the principal's 0.02 floor binding,
BOTH calls return the identical lot -- and the realised fraction of that identical lot is
`lot * dist * eur_per_unit / equity`, which is LINEAR IN THE STOP. A 60 USD/oz bracket therefore
runs ~3.1x the fraction a 19.1 USD/oz nominal reserved for it, at the same lot, with the log and
the state file both saying the budget was respected. That is the reading `cap_by_heat` exists to
end, arriving through the one door it had left.

THE FIX PINNED HERE. `gateway.resolve_pending_bracket` resolves the bracket IN FRONT of the cap;
the roster loop sizes and charges at that bracket's own `dist` and live `symbol_info`, caches the
resolution on the sleeve row, and the placement loop sends that same resolution unchanged. The
invariant is therefore an identity and not an approximation:

    q_charge == realised_q(equity, actual_stop_dist, symbol, live_symbol_info, lot=final_lot)

for every admitted gold order. These tests drive it across stop distances from tight to very
wide, at fractions from far below the floor to far above it, and assert BOTH that the identity
holds and that the pre-fix arithmetic would have broken it -- a test that cannot fail on the old
code is not a regression test.
"""
from __future__ import annotations

import ast
import sys
from datetime import date
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pandas as pd
import pytest

_DESK = Path(__file__).resolve().parents[1]
#: This directory joins the path too: the end-to-end test below reuses `test_gateway_adapter`'s
#: terminal fake and `main` harness rather than growing a second, divergent copy of them, and
#: pytest's import mode does not reliably make a sibling test module importable by name.
for _p in (str(Path(__file__).resolve().parent), str(_DESK), str(_DESK.parent.parent)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from mt5desk import decision_core as dc  # noqa: E402

_GW_SRC = (_DESK / "mt5desk" / "gateway.py").read_text("utf-8")
_GW_TREE = ast.parse(_GW_SRC)

#: The gold row the gateway's `"auto"` branch is (`decision_core.roster` gives `"auto"` to the
#: three GOLD_WINDOWS rows and nothing else). `rng=None` means "hours [0, sig_hour)".
SLEEVE = {"name": "gold_london_am", "symbol": "XAUUSD", "lot": "auto", "rng": None,
          "sig_hour": 13}


class _GoldInfo:
    """XAUUSD as a Fusion five-digit CFD feed reports it. `trade_tick_value / trade_tick_size`
    is the only current answer for EUR per price unit, and it is 86.41 for gold."""

    trade_tick_value = 0.8641
    trade_tick_size = 0.01
    trade_stops_level = 20
    volume_min = 0.01
    volume_step = 0.01
    volume_max = 100.0
    digits = 2


def _bars(span: float, n: int = 200) -> list[dict]:
    """Gold H1 bars whose LAST calendar day has a high-low range of `span` USD/oz.

    `bracket_spec` sets the stop at `max(1.2 * ATR, span)`, so widening the session range is how
    a caller varies the stop distance the bracket will actually carry -- which is the whole
    quantity this file is about. Anchored to a FIXED timestamp, not the wall clock: `day_range`
    reads the last bar's calendar date, and a test whose bracket depends on the hour it runs at
    measures the clock rather than the code.
    """
    idx = pd.date_range(end=pd.Timestamp("2026-09-08 20:00", tz="UTC"), periods=n, freq="h")
    base = 2400.0 + np.linspace(0.0, 4.0, n)
    rows = []
    for i, (t, b) in enumerate(zip(idx, base, strict=True)):
        hi, lo = b + 0.5, b - 0.5
        # One bar in the last day's range window carries the span, so `day_range` returns it.
        if i == n - 12:
            hi, lo = b + span / 2.0, b - span / 2.0
        rows.append({"time": int(t.timestamp()), "open": b, "high": hi, "low": lo,
                     "close": b + 0.1, "tick_volume": 100.0})
    return rows


def _fake_mt5(span: float) -> SimpleNamespace:
    return SimpleNamespace(
        TIMEFRAME_H1=16385,
        symbol_info=lambda symbol: _GoldInfo(),
        copy_rates_from_pos=lambda symbol, tf, start, count: _bars(span),
        last_error=lambda: (0, "ok"))


def _resolver(span: float):
    """`gateway.resolve_pending_bracket`, exec'd against the REAL core with the venue faked.

    `gateway.py` imports MetaTrader5 at the top -- deliberately, it is the Windows venue adapter
    -- so it cannot be imported on this host; the same AST-extraction the rest of this directory
    uses runs the function itself rather than a paraphrase of it.
    """
    seed = {k: v for k, v in vars(dc).items() if not k.startswith("__")}
    seed["mt5"] = _fake_mt5(span)
    # The gateway's `sleeve_live_n` is a one-argument adapter bound to the desk's ledger path;
    # the core's same-named function takes the ledger. Stubbed at zero live trades, which is the
    # bottom of the authority ramp and therefore the conservative end of promoted sizing.
    seed["sleeve_live_n"] = lambda name: 0
    # `_past_cancel_hour` rides along: the resolver checks the day's backstop itself now, so the
    # cap only ever prices orders that are eligible to reach the venue. Left out of the slice it
    # is a NameError on every call -- the same harness gap that hid a live NameError in the gold
    # placement path for a whole session.
    keep = [n for n in _GW_TREE.body if isinstance(n, ast.FunctionDef)
            and n.name in ("resolve_pending_bracket", "_past_cancel_hour", "bracket_lane_lot")]
    assert len(keep) == 3, [n.name for n in keep]
    exec(compile(ast.Module(body=keep, type_ignores=[]), "<gw>", "exec"), seed)
    return seed


def _resolve(span: float, hour: float = 14.0) -> dict:
    return _resolver(span)["resolve_pending_bracket"](SLEEVE, hour, date(2026, 9, 8))


#: Session ranges from a quiet Asia morning to a CPI-day London range. Chosen to straddle the
#: house nominal (19.1) in both directions, because the sign of the error flips there.
SPANS = (6.0, 12.0, 19.0, 28.0, 45.0, 70.0, 110.0)


def _charge_and_send(equity: float, span: float, h_i: object,
                     faded: object = None) -> tuple[float, float, float, float]:
    """(q_charge, q_send, lot, dist) exactly as the gateway computes them.

    The charge is the roster loop's: resolve the bracket, size at its `dist` and live `sym`,
    bill `realised_q` at that lot. The send is the placement loop's: REUSE that resolution.
    Written as two separate expressions on purpose -- if the gateway ever goes back to charging
    on one set of arguments and sending on another, this file must be what says so.
    """
    pend = _resolve(span)
    assert pend["ok"], pend
    lot, _basis = dc.gold_book_lot(equity, pend["dist"], pend["sym"], h_i, faded)
    q_charge = dc.realised_q(equity, pend["dist"], SLEEVE["symbol"], pend["sym"], lot=lot)
    send_lot, _ = dc.gold_book_lot(equity, pend["dist"], pend["sym"], h_i, faded)
    q_send = dc.realised_q(equity, pend["dist"], SLEEVE["symbol"], pend["sym"], lot=send_lot)
    assert send_lot == lot
    return q_charge, q_send, lot, pend["dist"]


# --------------------------------------------------------------- the resolver is what it claims
def test_the_resolver_returns_the_bracket_and_its_own_stop() -> None:
    pend = _resolve(45.0)
    assert pend["ok"] and pend["stage"] == "ok"
    assert pend["hi"] > pend["lo"]
    assert pend["dist"] == dc.stop_distance(pend["spec"])
    assert pend["dist"] > 0


def test_a_wider_session_range_carries_a_wider_stop() -> None:
    """The premise the whole defect rests on: the bracket's stop is NOT a constant, so charging
    at a constant and sending at the bracket is charging for a different trade."""
    dists = [_resolve(span)["dist"] for span in SPANS]
    assert dists == sorted(dists), dists
    assert len(set(dists)) == len(dists), "the spans must produce distinct stops"
    assert min(dists) < dc.DIST_USD < max(dists), (
        "the sweep must straddle the house nominal, or it only measures one side of the error")


def test_the_resolver_refuses_before_the_signal_hour_and_names_the_stage() -> None:
    pend = _resolve(45.0, hour=11.0)
    assert not pend["ok"] and pend["stage"] == "signal_hour"


def test_the_resolver_writes_nothing() -> None:
    """It runs TWICE per pass in the worst case (once to charge, once at the placement site when
    nothing was cached), so it must be pure: no state, no ledger, no order. Pinned on the AST
    because "read-only" is a property of the code and not of one execution of it."""
    fn = next(n for n in _GW_TREE.body if isinstance(n, ast.FunctionDef)
              and n.name == "resolve_pending_bracket")
    called = {n.func.id for n in ast.walk(fn)
              if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)}
    assert not called & {"save_state", "_record_decision", "_record_intent",
                         "_record_vetoed_bracket", "place_bracket", "log"}, called
    assert not [n for n in ast.walk(fn) if isinstance(n, ast.Attribute)
                and isinstance(n.value, ast.Name) and n.value.id == "mt5"
                and n.attr in ("order_send", "order_check")]


# ------------------------------------------------------------------------------ THE INVARIANT
def test_the_charge_equals_the_send_at_every_stop_distance_and_every_fraction() -> None:
    """`q_charge == realised_q(equity, actual_stop_dist, symbol, live_symbol_info, lot=final_lot)`
    for every admitted gold order -- the auditor's required invariant, driven across the whole
    grid it has to hold on."""
    for equity in (2_000.0, 8_000.0, 20_000.0, 75_000.0):
        for span in SPANS:
            for h_i in (None, 0.0, 1e-6, 0.002, 0.0075, 0.02, 0.10, 0.5):
                for faded in (None, True):
                    q_charge, q_send, lot, dist = _charge_and_send(equity, span, h_i, faded)
                    assert q_charge == q_send, (equity, span, h_i, faded, q_charge, q_send)
                    assert abs(q_charge - lot * dist * 86.41 / equity) < 1e-9, (
                        "the billed fraction is not the fraction this lot runs at this stop")


def _old_and_new(equity: float, span: float) -> tuple[float, float, float, float]:
    """(old_charge, new_charge, nominal_lot, exact_lot) -- the previous HEAD's arithmetic beside
    this one's, at the same equity and the same bracket."""
    pend = _resolve(span)
    nominal_lot, _ = dc.gold_book_lot(equity, None, None, None)
    exact_lot, _ = dc.gold_book_lot(equity, pend["dist"], pend["sym"], None)
    return (dc.realised_q(equity, None, SLEEVE["symbol"], lot=nominal_lot),
            dc.realised_q(equity, pend["dist"], SLEEVE["symbol"], pend["sym"], lot=exact_lot),
            nominal_lot, exact_lot)


def test_the_old_house_nominal_charge_understated_a_wide_bracket_on_a_small_account() -> None:
    """THE TEST THAT WOULD HAVE FAILED ON THE PREVIOUS HEAD, which is the only kind worth
    writing here, and the auditor's exact scenario: with the principal's 0.02 gold floor binding,
    BOTH calls return the SAME lot -- so no lot comparison catches this -- and the billed
    fraction differs by the ratio of the stops, because `realised_q` is linear in the stop.

    Measured at E=1,500 across this sweep: a 110 USD/oz session bracket runs 12.70% of equity on
    ONE gold leg while the cap reserved 2.20% for it. Three windows of that is a ~38% book
    against a 20-30% budget, admitted unanimously, with every log line saying the budget held.
    """
    equity = 1_500.0
    worst, worst_span = 1.0, 0.0
    for span in SPANS:
        old, new, nominal_lot, exact_lot = _old_and_new(equity, span)
        pend = _resolve(span)
        if pend["dist"] <= dc.DIST_USD:
            continue
        assert nominal_lot == exact_lot == dc.gold_min_lot(), (
            span, nominal_lot, exact_lot, "the floor must bind at both stops here, or this test "
            "is measuring lot arithmetic rather than the accounting gap")
        assert new > old, (span, pend["dist"], old, new)
        if new / old > worst:
            worst, worst_span = new / old, span
    assert worst > 5.0, (
        f"the widest bracket in the sweep understated its heat by only {worst:.2f}x (span "
        f"{worst_span}); the sweep no longer reaches the range where this defect bites")


def test_where_the_floor_does_not_bind_the_old_charge_was_accidentally_right() -> None:
    """WHY IT HID FOR SO LONG, stated rather than left to be rediscovered. On a large account
    the lot is set by policy at BOTH stops, so both charges land on Q_OPT and the two arithmetics
    agree to a lot step. The old charge was not correct -- it was correct only in the regime the
    desk was not in, and the desk trades a small account with a hard lot floor.
    """
    equity = 75_000.0
    for span in SPANS:
        old, new, _nominal_lot, exact_lot = _old_and_new(equity, span)
        assert exact_lot > dc.gold_min_lot(), (span, exact_lot, "policy must set the size here")
        assert abs(new - dc.Q_OPT) / dc.Q_OPT < 0.05, (span, new)
        assert abs(new - old) / old < 0.05, (span, old, new)


def test_the_exact_charge_also_stops_over_reserving_and_that_frees_book() -> None:
    """The other direction, and it is a GAIN, not a cost. At E=8,000 a 45 USD/oz bracket sizes
    to the 0.02 floor and runs 0.98% -- while the house nominal reserved 1.23% for it. The old
    accounting held back budget the trade was never going to use, which could defer a validated
    leg. Nothing about the lot changes; only the number the cap reads."""
    old, new, _, exact_lot = _old_and_new(8_000.0, 45.0)
    assert exact_lot == dc.gold_min_lot()
    assert new < old, (old, new)


def test_the_exact_charge_never_cuts_the_size_the_desk_sends() -> None:
    """THE STANDING ORDER, re-checked at the new charge. Making the accounting exact must not
    become a size cut through the back door: the lot at the real stop is still `max(allocator,
    policy, floor)` and the floor still binds where it bound before."""
    for equity in (1_500.0, 8_000.0, 20_000.0):
        for span in SPANS:
            pend = _resolve(span)
            lot, _ = dc.gold_book_lot(equity, pend["dist"], pend["sym"], None)
            assert lot >= dc.gold_min_lot() - 1e-12, (equity, span, lot)
            assert lot == dc.gold_lot(equity, pend["dist"], pend["sym"])


# ---------------------------------------------------------------------------- the gateway wiring
def _main() -> ast.FunctionDef:
    return next(n for n in _GW_TREE.body if isinstance(n, ast.FunctionDef) and n.name == "main")


def test_the_bracket_is_resolved_before_the_heat_cap_runs() -> None:
    """The structural half. If `resolve_pending_bracket` ever moves back behind `cap_by_heat`,
    the cap is once again pricing a trade it has not seen."""
    calls = [n for n in ast.walk(_main()) if isinstance(n, ast.Call)
             and isinstance(n.func, ast.Name)
             and n.func.id in ("resolve_pending_bracket", "cap_by_heat")]
    order = [c.func.id for c in sorted(calls, key=lambda c: c.lineno)]
    assert order and order[0] == "resolve_pending_bracket", order
    assert "cap_by_heat" in order
    assert order.index("resolve_pending_bracket") < order.index("cap_by_heat")


def test_the_charge_site_bills_at_the_resolved_stop_and_the_live_symbol_info() -> None:
    block = _GW_SRC.split("from_book = _book is not None", 1)[1] \
                   .split("sleeves, heat_note = cap_by_heat(sleeves", 1)[0]
    assert 'resolve_pending_bracket(_s, hour, datetime.now(tz=UTC).date())' in block, (
        "the charge must ask about the same day the placement loop will, or the two sites can "
        "disagree across midnight and the charge site silently becomes the trading rule")
    assert '_s, equity, _pend["dist"], _pend["sym"]' in block, (
        "the charge must be sized at the bracket's own stop in the sleeve's own instrument")
    assert 'realised_q(equity, _pend["dist"], _s["symbol"],' in block \
        and '_pend["sym"], lot=_lot_charge)' in block, (
        "the billed fraction must be measured at the same stop the lot was sized against, in "
        "the sleeve's own instrument, at the lot that will be sent")
    assert "bracket_lane_lot(" in block, (
        "the charge must go through the one sizer the send calls, for EVERY lane -- gold, "
        "promoted and fixed-lot -- not just for gold")
    assert '_s["pending_bracket"] = _pend' in block, (
        "the resolution must be handed to the placement loop, or the send can drift from it")
    # THE HOUSE-NOMINAL FALLBACK IS GONE, DELIBERATELY (external audit round 3, 2026-09-09).
    # It was what let an unresolved sleeve be charged an approximation and then placed anyway
    # when the placement site's second attempt succeeded -- an order whose exact risk the cap
    # had never seen. A sleeve that cannot be resolved before the cap is now charged NOTHING and
    # marked not placeable, which costs no size: the next pass prices it properly from the start.
    assert 'realised_q(equity, None' not in block, (
        "the house-nominal fallback is back in the bracket lane's charge; an unresolved sleeve "
        "can be charged an approximation and then sent")
    assert '_s["q_charge"] = 0.0' in block and '_s["placeable"] = False' in block, (
        "an unresolvable sleeve must be charged nothing and refused the venue for this pass")
    assert "NOT PLACEABLE THIS PASS" in block, "the refusal must say so on the row"


def test_the_placement_site_sends_the_resolution_the_cap_admitted() -> None:
    # The BRACKET LOOP only: it ends where the hibernated sleeves are walked for their veto
    # records, which is a different path with its own reasons for reading bars.
    block = _GW_SRC.split("sleeves, heat_note = cap_by_heat(sleeves", 1)[1] \
                   .split("for s in _hibernated:", 1)[0]
    assert '_pend = s.get("pending_bracket")' in block, (
        "the placement loop must reuse the resolution rather than rebuild the range; a bar can "
        "close between the two loops and the send would then be a trade the cap never saw")
    assert 'sym, df = _pend["sym"], _pend["df"]' in block
    assert 'hi, lo, spec, dist = _pend["hi"], _pend["lo"], _pend["spec"], _pend["dist"]' in block
    assert "HEAT RECONCILE" in block, "a drift between charge and send must be logged, loudly"
    # The old inline resolution must be gone, or two copies of the guards can diverge.
    assert 'h1 = mt5.copy_rates_from_pos(s["symbol"], mt5.TIMEFRAME_H1, 0, 400)' not in block, \
        "the placement loop re-reads bars again; it must go through resolve_pending_bracket"


# ------------------------------------------------- the invariant MEASURED, not read off source
def test_main_charges_the_heat_cap_exactly_what_it_sends_to_the_venue(tmp_path,
                                                                     monkeypatch) -> None:
    """THE OPERATIONAL PROOF, and the only one that settles the question. Every test above either
    exercises the arithmetic or reads the wiring; this one runs `main()` over a faked terminal
    with the REAL sizing functions, catches the sleeve rows at the moment `cap_by_heat` is handed
    them, and compares each gold row's `q_charge` against the fraction of equity the order that
    actually reached `order_send` runs at the bracket's own stop.

    `test_gateway_adapter` already owns the machinery for running `main` off the source with the
    venue faked; only the sizing stubs are swapped back for the core's own functions, because
    stubbing `realised_q` to a constant is exactly what would make this test unable to see the
    defect it exists to catch.
    """
    tga = pytest.importorskip("test_gateway_adapter")
    mt5 = tga._Terminal(tga._gold_rows(), *tga._quote(tga._gold_rows()))
    ns = tga._main_ns(tmp_path, monkeypatch, mt5, paused=False, state={"armed": True})
    # The core's real laws, in place of the harness's constants.
    for name in ("realised_q", "gold_lot", "gold_min_lot", "min_lot", "promoted_lot"):
        ns[name] = getattr(dc, name)
    charged: dict[str, float] = {}

    def _cap(sleeves, equity, per_sleeve_q=None, k_eff=None):
        charged.update({s["name"]: s.get("q_charge") for s in sleeves
                        if s.get("q_charge") is not None})
        return sleeves, None

    ns["cap_by_heat"] = _cap
    ns["main"]()

    equity = float(mt5.account_info().equity)
    info = mt5.symbol_info("XAUUSD")
    _hi, _lo, spec = dc.bracket_from_bars(dc.h1_frame(mt5.rows), None, 7, 0.01, 20)
    dist = dc.stop_distance(spec)
    volumes = {float(r["volume"]) for r in mt5.sent}
    assert len(volumes) == 1, f"the pass sent {volumes}; expected one bracket at one lot"
    sent_lot = volumes.pop()
    q_sent = dc.realised_q(equity, dist, "XAUUSD", info, lot=sent_lot)

    assert "gold_asia" in charged, (
        f"no gold row reached the cap with a charge; charged={charged}, "
        f"logs={ns['_logs']}")
    assert charged["gold_asia"] == q_sent, (
        f"the cap reserved {charged['gold_asia']:.6%} and the venue got {sent_lot} lots at a "
        f"{dist:.5g} stop, which runs {q_sent:.6%}")
    # And the log must name the basis that set the size rather than leaving it to be
    # reconstructed here -- the number and the reason travel together or neither is auditable.
    assert any("sizing basis" in x for x in ns["_logs"]), ns["_logs"]
    assert any("realised q" in x for x in ns["_logs"]), ns["_logs"]
    assert not [x for x in ns["_logs"] if "HEAT RECONCILE" in x], (
        "the charge and the send diverged on a clean pass: " + str(ns["_logs"]))


def test_the_reconciliation_tripwire_compares_the_fraction_not_the_lot() -> None:
    """The lot is the wrong quantity to reconcile on, and that is the whole lesson of this
    defect: the floor makes two different trades share one lot. The check must be on the
    fraction of equity the order actually runs."""
    body = _GW_SRC.split("_billed_q = s.get(\"q_charge\")", 1)[1].split("margin guard", 1)[0]
    assert "abs(float(_billed_q) - q_real)" in body
    assert "HEAT RECONCILE" in body


def test_the_reconciliation_tripwire_never_refuses_a_trade() -> None:
    """The principal's standing order: never reduce the aggressiveness, only the dynamicness.
    The charge/send check reports a drift, it does not veto, resize or defer one."""
    # The tripwire's OWN `if`, found by its test rather than by the string in its body: several
    # enclosing `if`s also contain it, and walking one of those would pass on any code at all.
    stmt = next(n for n in ast.walk(_main()) if isinstance(n, ast.If)
                and "_billed_q" in ast.dump(n.test))
    for node in ast.walk(stmt):
        assert not isinstance(node, (ast.Continue, ast.Break, ast.Return)), (
            "the heat tripwire skips or stops a trade; it may only report")
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
            assert node.func.id in ("log", "float", "isinstance", "abs"), node.func.id


# ============================================================ round 3: the invariant goes universal
# The second audit closed gold on its normal path. The third found three ways it was still not a
# universal statement, and each is pinned here.


def test_the_cancel_hour_is_part_of_the_resolution_not_of_the_send():
    """THE CAP MUST SEE ONLY ORDERS THAT CAN REACH THE VENUE. The day's backstop was checked in
    the placement loop alone, so after it passed the pre-cap phase could resolve a good bracket,
    have the cap RESERVE budget for it, and then watch the loop refuse to place it. Nothing
    unsafe -- heat held for an impossible order, and a better sleeve possibly deferred behind
    it. That is a growth cost, and growth is the objective."""
    pend = _resolve(45.0, hour=float(dc.CANCEL_HOUR) + 0.5)
    assert not pend["ok"] and pend["stage"] == "past_cancel_hour"
    assert "taken back by this same pass" in pend["why"]
    # And it is still resolvable an hour before the backstop, or the guard has eaten the session.
    assert _resolve(45.0, hour=float(dc.CANCEL_HOUR) - 1.0)["ok"]


def test_a_sleeve_the_cap_did_not_price_cannot_be_placed_later_in_the_same_pass():
    """THE UNIVERSALITY FIX. The old shape was: pre-cap resolution fails -> charge the house
    nominal -> the placement site resolves AGAIN -> it succeeds -> the order is sent and a
    tripwire logs the breach. The invariant then held on the normal path and not universally.

    The placement site now consumes the pre-cap resolution and never resolves, so an order the
    cap did not price cannot be sent at all. It is not a size cut: the sleeve is resolved and
    charged properly on the next pass, minutes later."""
    block = _GW_SRC.split("sleeves, heat_note = cap_by_heat(sleeves", 1)[1] \
                   .split("for s in _hibernated:", 1)[0]
    assert 'resolve_pending_bracket(' not in block, (
        "the placement loop resolves the bracket again; a sleeve the cap never priced can reach "
        "the venue whenever that second attempt happens to succeed")
    assert "no pre-cap resolution this pass" in block, (
        "an unresolved sleeve must be refused the venue and told why")
    assert 'lot = float(_pend["lot"])' in block and 'q_real = float(_pend["q_real"])' in block, (
        "the send must use the admitted numbers, not recompute its own")


def test_the_whole_bracket_lane_is_priced_at_its_order_not_just_gold():
    """`auto_ramp` had the same defect one lane over: charged `ramped_fraction`, a fraction
    fixed before the stop existed, and sent `promoted_lot` at the real stop with the venue's lot
    floor applied on top. One sizer now serves the whole lane."""
    ns = _resolver(45.0)
    pend = _resolve(45.0)
    equity = 8_000.0
    gold = dict(SLEEVE)
    assert ns["bracket_lane_lot"](gold, equity, pend["dist"], pend["sym"])[0] > 0

    promoted = {"name": "eurusd_asia", "symbol": "XAUUSD", "lot": "auto_ramp",
                "risk_frac": 0.03, "rng": None, "sig_hour": 13}
    lot, basis = ns["bracket_lane_lot"](promoted, equity, pend["dist"], pend["sym"])
    assert lot > 0 and "promoted_lot" in basis and "risk_frac" in basis

    fixed = {"name": "fixed", "symbol": "XAUUSD", "lot": 0.07, "rng": None, "sig_hour": 13}
    assert ns["bracket_lane_lot"](fixed, equity, pend["dist"], pend["sym"]) == (
        0.07, "fixed lot 0.07 from the sleeve row")


def test_a_promoted_rows_charge_is_its_realised_risk_and_not_its_requested_fraction():
    """THE NUMBER THE THIRD AUDIT ASKED FOR. `ramped_fraction` is what the sleeve REQUESTED;
    `realised_q` at the resolved stop and the floored lot is what the order RUNS. On a small
    account the venue's minimum lot is the whole difference, and it moves the risk UP."""
    ns = _resolver(110.0)
    pend = _resolve(110.0)
    equity = 1_500.0
    promoted = {"name": "eurusd_asia", "symbol": "XAUUSD", "lot": "auto_ramp",
                "risk_frac": 0.03, "rng": None, "sig_hour": 13}
    lot, _ = ns["bracket_lane_lot"](promoted, equity, pend["dist"], pend["sym"])
    exact = dc.realised_q(equity, pend["dist"], "XAUUSD", pend["sym"], lot=lot)
    requested = dc.ramped_fraction(promoted["risk_frac"], 0, None)
    assert exact > 0 and requested > 0
    assert abs(exact - requested) > 1e-6, (
        f"the requested fraction {requested:.4%} and the realised risk {exact:.4%} agree on this "
        f"fixture, so it no longer demonstrates the gap it was written for")


def test_the_charge_site_covers_every_lane_and_names_the_one_it_does_not():
    """Gold, promoted and fixed-lot are all charged at their resolved order; the family lane is
    charged at ITS resolved order; the scalp lane is still charged a fraction and the source
    says so out loud rather than leaving it to be rediscovered by a fourth audit."""
    block = _GW_SRC.split("from_book = _book is not None", 1)[1] \
                   .split("sleeves, heat_note = cap_by_heat(sleeves", 1)[0]
    assert 'if _s.get("exec") not in ("family_market", "scalp_market"):' in block
    assert 'elif _s.get("exec") == "family_market":' in block
    assert "resolve_family_order(" in block, "the family lane is not priced at its order"
    # ROUND 4 CLOSED THE LAST ONE. Every lane that sends an order now has a resolver, so the
    # `from_book` fraction branch is reached by no sending lane at all.
    assert 'elif _s.get("exec") == "scalp_market":' in block and "resolve_scalp_order(" in block
    assert "THE SCALP LANE IS STILL CHARGED A FRACTION" not in block, (
        "the scalp lane is back on an abstract fraction")


def test_the_family_lane_charges_what_its_executor_sends():
    """The family resolver returns the lot the executor will send, so the charge is
    `realised_q` at that lot and the executor never sizes again."""
    src = _GW_SRC.split("def resolve_family_order(", 1)[1].split("\ndef ", 1)[0]
    assert "promoted_lot(equity, n_live, dist" in src
    assert 'from_book=(s.get("sized_by") == "allocator_book")' in src, (
        "the allocator book's fraction must reach the venue un-re-shrunk (governance G3)")
    sender = _GW_SRC.split("def run_family_sleeves(", 1)[1].split("\ndef ", 1)[0]
    assert "promoted_lot(" not in sender, (
        "the family executor sizes again; it must send the lot the cap admitted")
    assert 'plan = s.get("pending_order")' in sender
    assert "no pre-cap resolution this pass" in sender


def test_the_family_resolver_writes_no_state():
    """It runs before the cap, and the cap may reject what it resolved. Marking a signal bar
    there would consume a signal the sleeve then never traded, and the bar would never come
    back -- so the mark is reported and applied only by an executor that acted."""
    fn = next(n for n in _GW_TREE.body if isinstance(n, ast.FunctionDef)
              and n.name == "resolve_family_order")
    called = {n.func.id for n in ast.walk(fn)
              if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)}
    assert not called & {"save_state", "_record_intent", "_book_target", "_book_fill", "log"}
    assert not [n for n in ast.walk(fn) if isinstance(n, ast.Attribute)
                and isinstance(n.value, ast.Name) and n.value.id == "mt5"
                and n.attr in ("order_send", "order_check")]
    # `setdefault` would CREATE the sleeve's pass-state record; the resolver only ever reads.
    assert "gstate.setdefault" not in _GW_SRC.split("def resolve_family_order(", 1)[1] \
        .split("\ndef ", 1)[0]


def test_an_open_bracket_is_charged_at_the_lot_the_venue_holds():
    """Re-sizing an order the book already has prices a trade the book does not have: equity
    has moved since it was placed. The bracket record now carries its own lot."""
    assert _GW_SRC.count('"lot": lot') == 3, (
        "a bracket write site stopped recording the lot it placed")
    block = _GW_SRC.split("from_book = _book is not None", 1)[1] \
                   .split("sleeves, heat_note = cap_by_heat(sleeves", 1)[0]
    assert '"placed_lot"' in block and "already on the book" in block


# ================================================== round 4: the last lane charges an order too
def _scalp_ns():
    """`scalp_open_basket_q` over the real core, so the basket arithmetic is the desk's own
    `realised_q` and not a second copy of it."""
    seed = {k: v for k, v in vars(dc).items() if not k.startswith("__")}
    fn = next(n for n in _GW_TREE.body if isinstance(n, ast.FunctionDef)
              and n.name == "scalp_open_basket_q")
    exec(compile(ast.Module(body=[fn], type_ignores=[]), "<gw>", "exec"), seed)
    return seed


def test_an_open_scalp_basket_is_charged_slice_by_slice_at_each_slices_own_stop_distance():
    """THE HALF OF THE SCALP CHARGE THAT IS NOT A NEW ORDER. A scalp sleeve can hold four slices
    at four prices against one stop; that exposure is real whether or not this pass adds to it,
    and `ramped_fraction` -- the number this lane was billed until 2026-09-09 -- describes
    neither the slices nor the stop. A four-slice basket must be charged four times."""
    ns = _scalp_ns()
    equity, info = 20_000.0, _GoldInfo()
    st = {"scalp": {"xau_scalp": {"basket": {
        "side": 1, "stop": 2400.0,
        "entries": [[2410.0, 0.02], [2415.0, 0.02], [2420.0, 0.02], [2425.0, 0.02]]}}}}
    sleeve = {"name": "xau_scalp", "symbol": "XAUUSD", "exec": "scalp_market"}
    q, why = ns["scalp_open_basket_q"](st, sleeve, equity, info)
    expected = sum(dc.realised_q(equity, abs(p - 2400.0), "XAUUSD", info, lot=u)
                   for p, u in st["scalp"]["xau_scalp"]["basket"]["entries"])
    assert q == pytest.approx(expected) and q > 0
    assert "4 open slice(s)" in why
    # A slice further from the stop costs more, which a single fraction cannot express.
    one = dict(st)
    one["scalp"] = {"xau_scalp": {"basket": {"side": 1, "stop": 2400.0,
                                             "entries": [[2410.0, 0.02]]}}}
    q1, _ = ns["scalp_open_basket_q"](one, sleeve, equity, info)
    assert q > 3 * q1, (q, q1)


def test_a_sleeve_with_no_open_basket_is_charged_nothing_for_one():
    ns = _scalp_ns()
    for st in ({}, {"scalp": {}}, {"scalp": {"xau_scalp": {}}},
               {"scalp": {"xau_scalp": {"basket": {"stop": 1.0, "entries": []}}}}):
        q, why = ns["scalp_open_basket_q"](st, {"name": "xau_scalp", "symbol": "XAUUSD"},
                                           20_000.0, _GoldInfo())
        assert q == 0.0 and why


def test_an_unpriceable_basket_charges_zero_and_says_so_rather_than_raising():
    """A charge that raises takes the whole pass down with it, and the pass is what manages
    open positions."""
    ns = _scalp_ns()
    st = {"scalp": {"x": {"basket": {"stop": "not a number", "entries": [[1.0, 0.02]]}}}}
    q, why = ns["scalp_open_basket_q"](st, {"name": "x", "symbol": "XAUUSD"}, 20_000.0, _GoldInfo())
    assert q == 0.0 and "unpriceable" in why


def test_the_scalp_charge_is_the_slice_plus_the_basket_and_the_source_says_which():
    block = _GW_SRC.split("from_book = _book is not None", 1)[1] \
                   .split("sleeves, heat_note = cap_by_heat(sleeves", 1)[0]
    assert 'elif _s.get("exec") == "scalp_market":' in block
    assert "resolve_scalp_order(" in block and "scalp_open_basket_q(" in block
    assert '_s["q_charge"] = _open_q + _new_q' in block, (
        "the scalp charge must carry both halves: the slice this pass sends and the exposure "
        "the open basket already holds")
    assert '_s["q_charge"] = _open_q' in block, (
        "a pass with no new slice must still charge the open basket, not zero")
    # And the fraction it used to be billed no longer SIZES anything here: the branch's own
    # comment still names `ramped_fraction` to say what it replaced, so the check is on code.
    lane = block.split('elif _s.get("exec") == "scalp_market":', 1)[1] \
                .split("elif from_book:", 1)[0]
    code = "\n".join(x for x in lane.split("\n") if not x.strip().startswith("#"))
    assert "ramped_fraction" not in code, (
        "the scalp charge is computed from a requested fraction again")


def test_the_scalp_resolver_writes_no_state_and_management_runs_before_the_cap():
    """The resolver runs before `cap_by_heat` and the cap may reject what it resolved, so a mark
    consumed here would throw away a bar the sleeve never traded. And the basket cleanup had to
    move OUT of the executor: behind the cap, a declined sleeve kept an orphaned basket whose
    time exit never ran."""
    fn = next(n for n in _GW_TREE.body if isinstance(n, ast.FunctionDef)
              and n.name == "resolve_scalp_order")
    called = {n.func.id for n in ast.walk(fn)
              if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)}
    assert not called & {"log", "save_state", "_record_intent", "_book_target", "_book_fill",
                         "close_sleeve_positions", "_retarget_sleeve_positions"}
    assert not [n for n in ast.walk(fn) if isinstance(n, ast.Attribute)
                and isinstance(n.value, ast.Name) and n.value.id == "mt5"
                and n.attr in ("order_send", "order_check")]
    src = _GW_SRC.split("def resolve_scalp_order(", 1)[1].split("\ndef ", 1)[0]
    assert "setdefault" not in src, "the resolver creates pass state; it may only read"
    # Management before the cap, and on the UNFILTERED roster.
    main_src = _GW_SRC.split("def main(", 1)[1]
    assert main_src.index("manage_scalp_baskets(st, sleeves)") < \
        main_src.index("sleeves, heat_note = cap_by_heat(sleeves")
    assert main_src.index("manage_scalp_baskets(st, sleeves)") < \
        main_src.index("reg_killed = regime_hibernate(sleeves)"), (
        "a hibernated sleeve's open basket must still reach its time exit")


def test_the_scalp_executor_sends_the_slice_the_cap_admitted_and_sizes_nothing():
    sender = _GW_SRC.split("def run_scalp_sleeves(", 1)[1].split("\ndef ", 1)[0]
    assert "promoted_lot(" not in sender and "slice_lot(" not in sender, (
        "the scalp executor sizes again; it must send the slice the cap admitted")
    assert 'plan = s.get("pending_order")' in sender
    assert "no pre-cap resolution this pass" in sender
    assert 'per, side, price = float(plan["per"])' in sender
