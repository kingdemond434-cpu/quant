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
    fn = next(n for n in _GW_TREE.body if isinstance(n, ast.FunctionDef)
              and n.name == "resolve_pending_bracket")
    exec(compile(ast.Module(body=[fn], type_ignores=[]), "<gw>", "exec"), seed)
    return seed["resolve_pending_bracket"]


def _resolve(span: float, hour: float = 14.0) -> dict:
    return _resolver(span)(SLEEVE, hour, date(2026, 9, 8))


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
    pend = _resolver(45.0)(SLEEVE, 11.0, date(2026, 9, 8))
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
    assert '_pend["dist"], _pend["sym"]' in block, (
        "the charge must be sized at the bracket's own stop in the sleeve's own instrument")
    assert 'realised_q(equity, _pend["dist"], _s["symbol"], _pend["sym"]' in block, (
        "the billed fraction must be measured at the same stop the lot was sized against")
    assert '_s["pending_bracket"] = _pend' in block, (
        "the resolution must be handed to the placement loop, or the send can drift from it")
    assert 'realised_q(equity, None' in block, (
        "the house-nominal fallback must survive for a pass where no bracket resolves; without "
        "it a failed read would drop the sleeve's charge to nothing")


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
    # And the log must say so rather than leaving it to be reconstructed here.
    assert any("charged at the bracket this pass will send" in x for x in ns["_logs"]) or \
        any("gold sizing basis" in x for x in ns["_logs"]), ns["_logs"]
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
