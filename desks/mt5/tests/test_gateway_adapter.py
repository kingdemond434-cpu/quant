"""The gateway is the thin venue adapter: what it keeps is wiring, and the wiring is pinned here.

After the split (2026-09-05) `gateway.py` holds the MetaTrader5 calls, the state and ledger
writes, and a handful of adapters that bind the desk's paths and the terminal's readings to
`mt5desk.decision_core`. Those adapters cannot be imported on this host -- the module still
imports MetaTrader5 at the top, deliberately, because it is the Windows venue adapter -- so they
are AST-extracted from the source and exec'd against the REAL core with the venue faked, the same
technique the rest of this directory uses. What that proves is that the gateway calls the core
with the right inputs and does the right thing with its answers: the sizing delegates are the
core's laws and nothing else; the heat cap is budgeted from the allocator verdict the gateway
reads; the allocator book is read once and parsed by the core; the roster's retirement notes are
logged; the family executor marks, logs, sizes and sends exactly as the core's step says.
"""
from __future__ import annotations

import ast
import json
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pandas as pd
import pytest

_DESK = Path(__file__).resolve().parents[1]
_ROOT = _DESK.parent.parent
for p in (str(_DESK), str(_DESK / "research"), str(_ROOT)):
    if p not in sys.path:
        sys.path.insert(0, p)

from mt5desk import config as _cfg  # noqa: E402
from mt5desk import decision_core as dc  # noqa: E402
from mt5desk.sizing import decay_factor  # noqa: E402

_GW_SRC = (_DESK / "mt5desk" / "gateway.py").read_text("utf-8")
_GW_TREE = ast.parse(_GW_SRC)


def _is_literal(node: ast.AST) -> bool:
    """A module-level assignment safe to carry into the harness: literals only, no calls."""
    try:
        ast.literal_eval(node)
    except (ValueError, SyntaxError, TypeError):
        return False
    return True


def _exec(names: tuple[str, ...], ns: dict) -> dict:
    """Exec the named gateway functions over a namespace seeded with the real decision core, so
    a bare name the adapter uses resolves to the same object the gateway imports.

    MODULE-LEVEL LITERAL CONSTANTS COME TOO, and they did not before. The harness carried only
    FunctionDefs, so a gateway function that read a module constant raised NameError inside
    `<gw>` -- which is a harness gap reported as a product failure, and it reads exactly like the
    change under test being broken. Measured 2026-09-05: `run_family_sleeves` gained
    `_family_chart` (which reads `_FAMILY_TF_ATTR`, `_BARS_PER_HOUR`, `_FAMILY_H1_BARS`,
    `_FAMILY_MAX_BARS`) and two passing tests began failing on a NameError for the helper, not for
    anything either test was about.

    Restricted to `ast.literal_eval`-able values on purpose: a module-level `Path(...)` or a
    computed constant would need the gateway's own imports, and quietly evaluating arbitrary
    module-level code here would make this harness a second, divergent copy of the gateway's
    import machinery. Anything non-literal a test needs is still seeded explicitly through `ns`.
    """
    seed = {k: v for k, v in vars(dc).items() if not k.startswith("__")}
    seed["_core"] = dc
    for node in _GW_TREE.body:
        if isinstance(node, ast.Assign) and len(node.targets) == 1 \
                and isinstance(node.targets[0], ast.Name) and _is_literal(node.value):
            seed.setdefault(node.targets[0].id, ast.literal_eval(node.value))
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name) \
                and node.value is not None and _is_literal(node.value):
            seed.setdefault(node.target.id, ast.literal_eval(node.value))
    seed.update(ns)
    keep = [n for n in _GW_TREE.body if isinstance(n, ast.FunctionDef) and n.name in names]
    assert {n.name for n in keep} == set(names), f"missing from gateway.py: {set(names)}"
    exec(compile(ast.Module(body=keep, type_ignores=[]), "<gw>", "exec"), seed)
    return seed


# ------------------------------------------------------------------------- the sizing delegates

def test_the_sizing_delegates_are_the_cores_laws_and_nothing_else() -> None:
    """`auto_lot`, `realised_q` and `promoted_lot` stay as defs in the gateway because the L1.67
    fence (scripts/check_risk_units.py) audits this file's sizing FunctionDefs by name. Their
    whole body must be one call into the core with every argument passed through."""
    ns = _exec(("auto_lot", "realised_q", "promoted_lot"), {})
    for eq, stop, sym in ((1683.89, 0.5, "CADJPY"), (25_000.0, 53.4, "XAUUSD")):
        assert ns["auto_lot"](eq, stop, sym) == dc.auto_lot(eq, stop, sym)
        assert ns["auto_lot"](eq, stop, sym, None, q=0.05) == dc.auto_lot(eq, stop, sym, q=0.05)
        assert ns["realised_q"](eq, stop, sym) == dc.realised_q(eq, stop, sym)
        assert ns["realised_q"](eq, stop, sym, None, lot=0.2) == dc.realised_q(
            eq, stop, sym, lot=0.2)
        for kw in ({}, {"from_book": True}):
            assert ns["promoted_lot"](eq, 3, stop, sym, None, 0.017, None, **kw) == \
                dc.promoted_lot(eq, 3, stop, sym, None, 0.017, None, **kw)
    assert ns["auto_lot"](25_000.0) == dc.auto_lot(25_000.0)          # gold by default, still
    for name in ("auto_lot", "realised_q", "promoted_lot"):
        fn = next(n for n in _GW_TREE.body if isinstance(n, ast.FunctionDef) and n.name == name)
        body = [s for s in fn.body if not (isinstance(s, ast.Expr)
                                           and isinstance(s.value, ast.Constant))]
        assert len(body) == 1 and isinstance(body[0], ast.Return), f"{name} is not a delegate"
        call = body[0].value
        assert isinstance(call, ast.Call) and isinstance(call.func, ast.Attribute)
        assert call.func.attr == name and call.func.value.id == "_core"


def test_the_ledger_and_file_readers_are_bound_to_the_desks_paths(tmp_path) -> None:
    ledger = tmp_path / "live_ledger.jsonl"
    ledger.write_text('{"sleeve": "a", "r_multiple": 1.0}\n{"sleeve": "b"}\n', "utf-8")
    sleeves = tmp_path / "sleeves.json"
    sleeves.write_text(json.dumps({"sleeves": [{"name": "x", "status": "LIVE"}]}), "utf-8")
    retired = tmp_path / "GOLD_RETIRED.json"
    retired.write_text('{"gold_asia": {"reason": "r"}}', "utf-8")
    ns = _exec(("sleeve_live_n", "load_sleeves", "_load_retired_gold", "ledger_rows"),
               {"LEDGER": ledger, "SLEEVES_FILE": sleeves, "GOLD_RETIRED_FILE": retired})
    assert ns["sleeve_live_n"]("a") == 1 and ns["sleeve_live_n"]("zzz") == 0
    assert ns["load_sleeves"]() == [{"name": "x", "status": "LIVE"}]
    assert ns["_load_retired_gold"]() == {"gold_asia": {"reason": "r"}}
    assert ns["ledger_rows"]() == [{"sleeve": "a", "r_multiple": 1.0}, {"sleeve": "b"}]


# ------------------------------------------------------------------------------- the heat cap

def test_cap_by_heat_is_budgeted_from_the_allocator_verdict_the_gateway_reads() -> None:
    sl = [{"name": "a", "q_charge": 0.08}, {"name": "b", "q_charge": 0.08}]
    ns = _exec(("cap_by_heat",), {"allocator_heat": lambda: (0.10, "allocator book (ok)"),
                                  "allocator_rank": lambda base: None, "BASE": Path("/x")})
    admitted, note = ns["cap_by_heat"](sl, 1683.89)
    assert [s["name"] for s in admitted] == ["a"] and "[allocator book (ok)]" in note
    # The allocator's ranking reaches the cap too.
    ns["allocator_rank"] = lambda base: {"b": 0.9, "a": 0.1}
    admitted, _ = ns["cap_by_heat"](sl, 1683.89)
    assert [s["name"] for s in admitted] == ["b"]
    # Unusable verdict: the derived budget, named as such.
    ns["allocator_heat"] = lambda: (None, "no pf_allocation.json")
    admitted, note = ns["cap_by_heat"](sl, 1683.89, None, None)
    assert len(admitted) == 2 and note is None
    sl6 = [{"name": f"s{i}", "q_charge": 0.05} for i in range(6)]
    _, note = ns["cap_by_heat"](sl6, 1683.89)
    assert "derived (allocator unusable: no pf_allocation.json)" in note
    # The scalar override and k_eff still pass through.
    admitted, _ = ns["cap_by_heat"](sl, 1683.89, 0.01, 2.26)
    assert len(admitted) == 2


def test_allocator_heat_reads_under_the_desk_root(tmp_path) -> None:
    ns = _exec(("allocator_heat",), {"BASE": tmp_path})
    assert ns["allocator_heat"]() == (None, "allocator not armed (data/PF_ALLOCATOR_ARMED absent)")


def test_allocator_book_reads_once_and_lets_the_core_decide(tmp_path, monkeypatch) -> None:
    import libs.portfolio.allocator_proof as ap
    (tmp_path / "reports").mkdir()
    art = {"heat": {"total": 0.2, "certified": True}, "growth": {"annual_growth_pct": 12.0},
           "book": {"a": 0.12, "b": 0.08},
           "book_fallback": {"name": "inverse_vol", "book": {"a": 0.09, "b": 0.11}}}
    (tmp_path / "reports" / "pf_allocation.json").write_text(json.dumps(art))
    ns = _exec(("allocator_book",), {"BASE": tmp_path,
                                     "allocator_heat": lambda: (0.2, "allocator book (ok)")})
    monkeypatch.setattr(ap, "read_certificate", lambda root: (None, "proof failed"))
    book, why = ns["allocator_book"]()
    assert book == {"a": 0.09, "b": 0.11} and "inverse_vol" in why and "withheld" in why
    monkeypatch.setattr(ap, "read_certificate", lambda root: ({"passed": True}, "proof 1h old"))
    book, why = ns["allocator_book"]()
    assert book == {"a": 0.12, "b": 0.08} and "proof 1h old" in why
    # No fallback carried and no proof: rank but do not size.
    art["book_fallback"] = {}
    (tmp_path / "reports" / "pf_allocation.json").write_text(json.dumps(art))
    monkeypatch.setattr(ap, "read_certificate", lambda root: (None, "proof failed"))
    assert ns["allocator_book"]()[0] is None
    # Every read fails closed with its own reason.
    (tmp_path / "reports" / "pf_allocation.json").write_text("{ nope")
    monkeypatch.setattr(ap, "read_certificate", lambda root: ({"passed": True}, "ok"))
    assert ns["allocator_book"]()[1] == "pf_allocation unreadable (JSONDecodeError)"

    def _boom(root):
        raise OSError("disk")
    monkeypatch.setattr(ap, "read_certificate", _boom)
    assert ns["allocator_book"]()[1] == "proof unreadable (OSError: disk)"
    ns["allocator_heat"] = lambda: (None, "no pf_allocation.json")
    assert ns["allocator_book"]() == (None, "no allocator book: no pf_allocation.json")


def test_the_book_is_the_allocator_that_won_in_this_state(tmp_path, monkeypatch) -> None:
    """A*_t. The certificate carries a per-state verdict; the gateway sizes with the allocator
    that won in the state the desk is in NOW, not the one that won the average.

    A state the dynamic allocator LOST is sized from the winning challenger's own book at the
    contest's equalised heat, and it is not called certified -- the global proof certified the
    dynamic weights, not this one. A state it WON is byte-for-byte what this returned before
    per-state scoring existed, and so is an artifact with no `by_state` at all.
    """
    import libs.portfolio.allocator_proof as ap
    (tmp_path / "reports").mkdir()
    art = {"heat": {"total": 0.2, "certified": True, "state": "asia|calm|MON"},
           "book": {"a": 0.12, "b": 0.08},
           "book_fallback": {"name": "inverse_vol", "book": {"a": 0.09, "b": 0.11}}}
    (tmp_path / "reports" / "pf_allocation.json").write_text(json.dumps(art))
    ns = _exec(("allocator_book",), {"BASE": tmp_path,
                                     "allocator_heat": lambda: (0.2, "allocator book (ok)")})
    cert = {"passed": True, "why": "global ok", "best_baseline": "risk_parity",
            "books": {"risk_parity": {"a": 0.05, "b": 0.15}},
            "by_state": {"asia|calm|MON": {"passed": False, "best": "risk_parity",
                                           "scores": {"risk_parity": 0.004}, "n_worlds": 96,
                                           "why": "risk_parity beat it here"}}}
    monkeypatch.setattr(ap, "read_certificate", lambda root: (cert, "proof 1h old"))
    book, why = ns["allocator_book"]()
    assert book == {"a": 0.05, "b": 0.15}, "the state's winner did not size the book"
    assert "state-conditioned" in why and "risk_parity" in why
    assert "authoritative" not in why, "a challenger's book is not the certified one"

    # The same state, won by the dynamic allocator: the certified book, exactly as before.
    cert["by_state"]["asia|calm|MON"] = {"passed": True, "n_worlds": 96, "why": "dynamic won"}
    book, why = ns["allocator_book"]()
    assert book == {"a": 0.12, "b": 0.08} and "authoritative" in why and "proof 1h old" in why

    # No per-state bucket at all -> the global verdict, which is what the desk had before.
    cert["by_state"] = {}
    book, why = ns["allocator_book"]()
    assert book == {"a": 0.12, "b": 0.08} and "authoritative" in why

    # The state's winner has no finite score: `select` refuses, and a refusal sizes the
    # artifact's own baseline at the floor rather than the least ruinous wreck.
    cert["by_state"] = {"asia|calm|MON": {"passed": False, "best": "risk_parity",
                                          "scores": {"risk_parity": float("nan")},
                                          "n_worlds": 96, "why": "all wiped out"}}
    book, why = ns["allocator_book"]()
    assert book == {"a": 0.09, "b": 0.11} and "inverse_vol" in why and "withheld" in why


# ---------------------------------------------------------------------------- roster and regime

def test_sleeve_set_logs_the_retirement_notes_and_returns_the_roster() -> None:
    logs: list[str] = []
    ns = _exec(("sleeve_set",), {
        "log": logs.append,
        "_load_retired_gold": lambda: {"gold_asia": {"reason": "roll20"}},
        "load_sleeves": lambda: [{"name": "fam", "symbol": "EURUSD", "exec": "family_market"}]})
    sleeves = ns["sleeve_set"]()
    assert [s["name"] for s in sleeves] == ["gold_london_am", "gold_afternoon", "fam"]
    assert logs == ["GOLD gold_asia: RETIRED (roll20); not emitted this pass"]


def test_regime_hibernate_reads_the_monitors_file_and_fails_open(tmp_path) -> None:
    (tmp_path / "data").mkdir()
    ns = _exec(("regime_hibernate",), {"BASE": tmp_path})
    sleeves = [{"name": "gold_asia"}, {"name": "CADJPY.asia"}]
    assert ns["regime_hibernate"](sleeves) == set()
    f = tmp_path / "data" / "regime_state.json"
    f.write_text(json.dumps({"sleeves": {"XAUUSD|asia": {"flag": "hibernate"}}}), "utf-8")
    assert ns["regime_hibernate"](sleeves) == {"gold_asia"}
    f.write_text("{ nope", "utf-8")
    assert ns["regime_hibernate"](sleeves) == set()


# ------------------------------------------------------------------------ the family executor

_NAME = "eurusd_fam"


def _rows(n: int = 70) -> list[dict]:
    """Hourly broker rows ending with the FORMING bar of the CURRENT hour.

    ANCHORED TO THE WALL CLOCK, not to a fixed date, because the executor is: it writes
    `open_ttl_until = last_bar + (ttl_bars + 1)h` and then, in the same pass, closes anything
    already past its deadline. Bars dated in the past therefore place an order whose TTL has
    already expired -- the executor is right to close it, and a test asserting the key survives
    was measuring the calendar rather than the code. The last CLOSED bar here is one hour ago,
    which is what the gateway sees on a live pass.
    """
    idx = pd.date_range(end=pd.Timestamp.now(tz="UTC").floor("h"), periods=n, freq="h")
    base = 1.1000 + np.linspace(0, 0.01, n)
    return [{"time": int(t.timestamp()), "open": b, "high": b + 0.001, "low": b - 0.001,
             "close": b + 0.0002, "tick_volume": 50.0} for t, b in zip(idx, base, strict=True)]


def _sig_hour(rows: list[dict], *, off: bool = False) -> int:
    """The signal hour the executor will match on these bars -- the last CLOSED bar's hour --
    or, with `off`, an hour that deliberately does not match it."""
    hour = int(dc.h1_frame(rows).index[-2].hour)
    return (hour + 1) % 24 if off else hour


def _signal(bar, stop=1.1050, target=1.1150, ttl_bars=12):
    return SimpleNamespace(time=bar, stop=stop, target=target, ttl_bars=ttl_bars)


def _fake_mt5(rows: list[dict]) -> SimpleNamespace:
    sent: list[dict] = []
    return SimpleNamespace(
        TIMEFRAME_H1=16385, TRADE_ACTION_DEAL=1, ORDER_TYPE_BUY=0, ORDER_TYPE_SELL=1, sent=sent,
        copy_rates_from_pos=lambda symbol, tf, start, count: rows,
        symbol_info_tick=lambda symbol: SimpleNamespace(bid=1.1100, ask=1.1102),
        symbol_info=lambda symbol: SimpleNamespace(volume_min=0.01, volume_step=0.01),
        order_send=lambda req: (sent.append(req) or SimpleNamespace(retcode=10009, order=9,
                                                                    comment="done",
                                                                    price=1.1103)),
    )


def _family_ns(tmp_path: Path, mt5: SimpleNamespace, monkeypatch, *, armed_file: bool,
               sig_hour: int = 7, signals=None, states=None) -> dict:
    logs: list[str] = []
    intents: list[dict] = []
    book: list[tuple] = []
    closes: list[tuple] = []
    enable = tmp_path / "GENERIC_EXEC_ENABLED"
    # THE ARM FILE IS SET *AND* CLEARED. `tmp_path` is one directory per test, so a namespace
    # built armed leaves the flag on disk for the next one built in the same test -- which is
    # how an "unarmed" executor was measured sending real closes.
    if armed_file:
        enable.write_text("", "utf-8")
    else:
        enable.unlink(missing_ok=True)
    fam = signals or (lambda closed, side: [_signal(closed.index[-1])])
    hunt16 = SimpleNamespace(FAMILIES={"fam": fam},
                             WINDOWS={"asia": {"signal_at": sig_hour, "range_start": 0}})
    monkeypatch.setitem(sys.modules, "research.run_hunt16", hunt16)
    # THE RESOLVER READS IT UNPREFIXED. `run_family_sleeves` imports `research.run_hunt16`, but it
    # now resolves the constructor through `mt5desk.executables`, whose `hunt16_families()` does
    # `from run_hunt16 import FAMILIES` -- the spelling the desk box's sys.path gives it. Stubbing
    # only the prefixed name left `population_of("fam")` returning None, so the harness's family
    # was refused as an orphan and every family test failed for a path reason.
    monkeypatch.setitem(sys.modules, "run_hunt16", hunt16)
    monkeypatch.setitem(sys.modules, "research.run_hunt12", SimpleNamespace(
        day_states=states or (lambda closed: {})))
    ns = {"mt5": mt5, "log": logs.append, "MAGIC": 1, "GENERIC_EXEC_ENABLED": enable,
          "NEW_RISK_OK": True, "promoted_lot": lambda *a, **k: 0.12,
          "sleeve_live_n": lambda name: 0, "margin_ok": lambda *a, **k: True,
          "_record_intent": lambda **row: intents.append(row),
          "_policy_advice": lambda *a, **k: {"policy": "MARKET"},
          "_book_target": lambda *a, **k: book.append(("target", *a)),
          "_book_fill": lambda *a, **k: book.append(("fill", *a)),
          "_record_exec_outcome": lambda *a, **k: book.append(("outcome", *a)),
          "close_positions": lambda st, symbol: closes.append(("close", symbol)),
          "_logs": logs, "_intents": intents, "_book": book, "_closes": closes}
    # `_sleeve_identity` rides along because the send site spreads it onto the intent row; it is
    # pure over the sleeve dict and the harness would otherwise report the adapter broken.
    return _exec(("run_family_sleeves", "_family_chart", "_family_constructor",
                  "_family_takes_side", "_family_call_params", "_sleeve_identity"), ns)


def _sleeve(**over) -> dict:
    return {"name": _NAME, "symbol": "EURUSD", "exec": "family_market", "family": "fam",
            "selector": "asia", "side": "LONG", "risk_frac": 0.03, "lot": "auto_ramp", **over}


def test_unarmed_the_family_executor_logs_the_exact_order_and_marks_the_bar(tmp_path,
                                                                          monkeypatch) -> None:
    rows = _rows()
    mt5 = _fake_mt5(rows)
    ns = _family_ns(tmp_path, mt5, monkeypatch, armed_file=False, sig_hour=_sig_hour(rows))
    st = {"armed": True}
    ns["run_family_sleeves"](st, [_sleeve()], 10_000.0)
    assert mt5.sent == []
    last_bar = dc.h1_frame(rows).index[-2]
    ttl = dc.family_ttl_until(last_bar, 12)
    (line,) = [x for x in ns["_logs"] if "WOULD PLACE" in x]
    assert line == (f"[{_NAME}] WOULD PLACE (generic exec not armed; enable=GENERIC_EXEC_ENABLED): "
                    f"BUY 0.12 EURUSD @market sl=1.10500 tp=1.11500 ttl_until={ttl}")
    assert st["generic"][_NAME] == {"last_signal_bar": str(last_bar)}
    # The theoretical book saw the intent, armed or not.
    assert ns["_book"] == [("target", _NAME, "EURUSD", 0.12, "family_market/fam/asia")]


def test_armed_the_family_executor_sends_the_signals_levels_once_per_bar(tmp_path,
                                                                        monkeypatch) -> None:
    rows = _rows()
    mt5 = _fake_mt5(rows)
    ns = _family_ns(tmp_path, mt5, monkeypatch, armed_file=True, sig_hour=_sig_hour(rows))
    st = {"armed": True}
    ns["run_family_sleeves"](st, [_sleeve()], 10_000.0)
    (req,) = mt5.sent
    assert req["type"] == mt5.ORDER_TYPE_BUY and req["volume"] == 0.12
    assert req["price"] == 1.1102 and req["sl"] == 1.1050 and req["tp"] == 1.1150
    assert req["comment"] == f"DW{_NAME}"
    (intent,) = ns["_intents"]
    assert intent["sleeve"] == _NAME and intent["retcode"] == 10009 and intent["ticket"] == 9
    # The wall clock around the send, on the row and nowhere else: a float in milliseconds.
    assert isinstance(intent["latency_ms"], float) and intent["latency_ms"] >= 0.0
    # A roster row without identity keys places exactly as before and claims none.
    assert "certificate" not in intent and "sleeve_id" not in intent
    last_bar = dc.h1_frame(rows).index[-2]
    assert st["generic"][_NAME]["open_ttl_until"] == dc.family_ttl_until(last_bar, 12)
    assert [b[0] for b in ns["_book"]] == ["target", "fill", "outcome"]
    assert ns["_book"][1][3] == 0.12 and ns["_book"][1][4] == 1.1103      # the venue's fill
    assert any("FAMILY-EXEC ORDER -> retcode=10009" in x for x in ns["_logs"])
    # The same bar again places nothing.
    ns["run_family_sleeves"](st, [_sleeve()], 10_000.0)
    assert len(mt5.sent) == 1


# ------------------------------------------------------------- the bracket lane's theoretical book

class _BracketTerminal:
    """Positions and deal history only. There is deliberately NO order_send here: the bracket
    book is read-only against the venue, and a send would fail loudly as an AttributeError."""
    DEAL_ENTRY_OUT = 1

    def __init__(self):
        self.positions: list = []
        self.history: dict[int, list] = {}

    def positions_get(self, symbol=None):
        return [p for p in self.positions if symbol is None or p.symbol == symbol]

    def history_deals_get(self, position=None):
        return list(self.history.get(position, []))


def _bracket_book_ns(tmp_path: Path, term: _BracketTerminal) -> dict:
    from mt5desk import netting

    book = netting.TheoreticalBook(tmp_path / "theoretical_positions.jsonl")
    logs: list[str] = []
    ns = _exec(("_book_bracket_lane", "_closing_fill", "_sleeve_positions", "_book_target",
                "_book_fill"),
               {"mt5": term, "log": logs.append, "_netting_book": lambda: book})
    ns["_book"], ns["_logs"], ns["netting"] = book, logs, netting
    return ns


def _open_position(ticket: int, kind: int, volume: float, price: float, sleeve: str):
    return SimpleNamespace(ticket=ticket, type=kind, volume=volume, price_open=price,
                           symbol="XAUUSD", comment=f"DW{sleeve}")


def test_the_bracket_lane_books_a_fill_once_and_its_exit_from_the_closing_deal(tmp_path):
    term = _BracketTerminal()
    ns = _bracket_book_ns(tmp_path, term)
    book, ledger = ns["_book"], tmp_path / "theoretical_positions.jsonl"
    sleeves = [{"name": "gold_asia", "symbol": "XAUUSD", "lot": "auto"},
               {"name": "fam", "symbol": "EURUSD", "exec": "family_market"},
               {"name": "sc", "symbol": "XAUUSD", "exec": "scalp_market"}]
    st: dict = {"armed": True}

    # Nothing open: a flat bracket sleeve is not a position and the ledger stays unwritten.
    ns["_book_bracket_lane"](st, sleeves)
    assert not ledger.exists() and st["netting_booked"] == {}

    # A filled sell stop: -0.06 at the venue's own open, booked as target AND fill, once.
    term.positions = [_open_position(7, 1, 0.06, 1995.0, "gold_asia")]
    ns["_book_bracket_lane"](st, sleeves)
    rows = [json.loads(ln) for ln in ledger.read_text("utf-8").splitlines()]
    assert [(r["kind"], r["sleeve"], r["lots"], r.get("price"), r.get("reason")) for r in rows] == [
        ("fill", "gold_asia", -0.06, 1995.0, None),
        ("target", "gold_asia", -0.06, 1995.0, "bracket_fill")]
    assert st["netting_booked"] == {"7": {"sleeve": "gold_asia", "symbol": "XAUUSD",
                                          "lots": -0.06}}
    assert book.delta("XAUUSD") == 0.0, "target and fill agree: nothing outstanding to route"
    ns["_book_bracket_lane"](st, sleeves)                          # the same pass again
    assert book.rows == 2, "re-asserting an unchanged book appends nothing"

    # Closed at the broker with no closing deal recorded yet: the ticket stays booked, the
    # target stays where it was, no exit is invented, and the route carries no phantom order.
    term.positions = []
    ns["_book_bracket_lane"](st, sleeves)
    assert "7" in st["netting_booked"] and book.rows == 2
    assert book.delta("XAUUSD") == 0.0 and book.theoretical("XAUUSD") == {"gold_asia": -0.06}
    assert any("no closing deal yet" in x for x in ns["_logs"])

    # The closing deal appears (two partial OUT deals): the exit is booked at their VWAP and
    # the sleeve's target goes flat; the route then has nothing to send.
    term.history[7] = [SimpleNamespace(entry=0, volume=0.06, price=1995.0),
                       SimpleNamespace(entry=1, volume=0.04, price=1980.0),
                       SimpleNamespace(entry=1, volume=0.02, price=1971.0)]
    ns["_book_bracket_lane"](st, sleeves)
    rows = [json.loads(ln) for ln in ledger.read_text("utf-8").splitlines()]
    assert rows[2]["kind"] == "fill" and rows[2]["lots"] == 0.06
    assert rows[2]["price"] == pytest.approx(1977.0)
    assert rows[3] == {**rows[3], "kind": "target", "lots": 0.0, "reason": "bracket_flat"}
    assert st["netting_booked"] == {} and book.account_position("XAUUSD") == 0.0
    r = ns["netting"].route(book, "XAUUSD", 1975.0)
    assert r["side"] == "flat" and r["lots"] == 0.0
    # The family and scalp lanes are never asserted here: their own executors own them.
    assert {r["sleeve"] for r in rows} == {"gold_asia"}
    assert not [x for x in ns["_logs"] if "unmeasured" in x]


def test_the_bracket_book_survives_a_terminal_fault_and_costs_only_its_measurement(tmp_path):
    term = _BracketTerminal()
    ns = _bracket_book_ns(tmp_path, term)

    def _boom(symbol=None):
        raise RuntimeError("terminal gone")

    term.positions_get = _boom
    st = {"netting_booked": {"9": {"sleeve": "gold_asia", "symbol": "XAUUSD", "lots": 0.06}}}
    ns["_book_bracket_lane"](st, [{"name": "gold_asia", "symbol": "XAUUSD"}])
    assert any("bracket book unmeasured" in x for x in ns["_logs"])
    assert st["netting_booked"] == {"9": {"sleeve": "gold_asia", "symbol": "XAUUSD",
                                          "lots": 0.06}}, "a fault never drops a booked ticket"


def test_main_routes_every_sleeves_symbol_with_the_bracket_book_asserted_first() -> None:
    """The set handed to `_net_routes` carries no lane filter, and the bracket lane's book is
    asserted before it -- pinned on the AST, so a re-added `exec` filter fails here."""
    main = next(n for n in _GW_TREE.body if isinstance(n, ast.FunctionDef) and n.name == "main")
    calls = [n for n in ast.walk(main) if isinstance(n, ast.Call)
             and isinstance(n.func, ast.Name)
             and n.func.id in ("_net_routes", "_book_bracket_lane")]
    order = [c.func.id for c in sorted(calls, key=lambda c: c.lineno)]
    assert order == ["_book_bracket_lane", "_net_routes"], order
    (route,) = [c for c in calls if c.func.id == "_net_routes"]
    (arg,) = route.args
    assert isinstance(arg, ast.SetComp) and all(g.ifs == [] for g in arg.generators), (
        "the symbol set handed to _net_routes is filtered again; the bracket book, the only "
        "book that has ever traded, would drop out of the netting measurement")


def test_the_family_intent_carries_the_sleeves_certificate_and_id_when_the_row_has_them(
        tmp_path, monkeypatch) -> None:
    """Read with .get, never required: the promoter writes `certificate` and `sleeve_id` onto
    sleeves.json in its own wave, and a row that carries them is attributable above its name."""
    rows = _rows()
    mt5 = _fake_mt5(rows)
    ns = _family_ns(tmp_path, mt5, monkeypatch, armed_file=True, sig_hour=_sig_hour(rows))
    ns["run_family_sleeves"]({"armed": True},
                             [_sleeve(certificate="EURUSD.fam.asia", sleeve_id="1903a4cc")],
                             10_000.0)
    (req,) = mt5.sent
    # THE ORDER IS UNCHANGED: the identity is recorded, never sent.
    assert set(req) == {"action", "symbol", "volume", "type", "price", "sl", "tp", "deviation",
                        "magic", "comment"}
    (intent,) = ns["_intents"]
    assert intent["certificate"] == "EURUSD.fam.asia" and intent["sleeve_id"] == "1903a4cc"
    # An empty or absent value is not an identity.
    assert ns["_sleeve_identity"]({"certificate": "", "sleeve_id": None}) == {}
    assert ns["_sleeve_identity"](None) == {}


def test_a_state_mismatch_is_marked_and_named_and_a_failed_signal_is_not_marked(
        tmp_path, monkeypatch) -> None:
    rows = _rows()
    last_bar = dc.h1_frame(rows).index[-2]
    ns = _family_ns(tmp_path, _fake_mt5(rows), monkeypatch, armed_file=True,
                    sig_hour=_sig_hour(rows),
                    states=lambda closed: {last_bar.date(): "NORMAL_DAY"})
    st = {"armed": True}
    ns["run_family_sleeves"](st, [_sleeve(state="FAILED_BREAK")], 10_000.0)
    assert f"[{_NAME}] no trade: day state NORMAL_DAY != FAILED_BREAK" in ns["_logs"]
    assert st["generic"][_NAME] == {"last_signal_bar": str(last_bar)}

    def _boom(closed, side):
        raise ValueError("no such column")
    ns = _family_ns(tmp_path, _fake_mt5(rows), monkeypatch, armed_file=True,
                    sig_hour=_sig_hour(rows), signals=_boom)
    st = {"armed": True}
    ns["run_family_sleeves"](st, [_sleeve()], 10_000.0)
    assert (f"[{_NAME}] FAMILY-EXEC signal computation failed (no such column); skipped"
            in ns["_logs"])
    assert st["generic"][_NAME] == {}                # considered, so the next pass retries


def test_off_the_signal_hour_the_executor_touches_no_state(tmp_path, monkeypatch) -> None:
    rows = _rows()
    ns = _family_ns(tmp_path, _fake_mt5(rows), monkeypatch, armed_file=True,
                    sig_hour=_sig_hour(rows, off=True))   # the sleeve's hour is not this bar's
    st = {"armed": True}
    ns["run_family_sleeves"](st, [_sleeve()], 10_000.0)
    assert st["generic"] == {} and ns["_logs"] == []


def test_the_executor_refuses_what_it_cannot_replay_exactly(tmp_path, monkeypatch) -> None:
    rows = _rows()
    ns = _family_ns(tmp_path, _fake_mt5(rows), monkeypatch, armed_file=True,
                    sig_hour=_sig_hour(rows))
    st = {"armed": True}
    ns["run_family_sleeves"](st, [_sleeve(family="nope"), _sleeve(selector="nope")], 10_000.0)
    # TWO CAUSES, TWO MESSAGES. This asserted one line ("family/selector has no exact executable")
    # for both, which sends the reader to the wrong place half the time: an unresolvable family is
    # an ORPHAN CERTIFICATE -- no code on this tree answers to the name -- while an unknown
    # selector is a hunt16 WINDOW that was never wired. Different defects, different fixes, and
    # the universal executor made the distinction load-bearing: a non-hunt16 family legitimately
    # has no window and must not be refused for lacking one.
    assert (f"[{_NAME}] FAMILY-EXEC refused: no constructor for family 'nope' on this box"
            in ns["_logs"])
    assert (f"[{_NAME}] FAMILY-EXEC refused: hunt16 selector 'nope' has no window"
            in ns["_logs"])
    short = _fake_mt5(_rows(n=10))
    ns = _family_ns(tmp_path, short, monkeypatch, armed_file=True, sig_hour=_sig_hour(rows))
    ns["run_family_sleeves"]({"armed": True}, [_sleeve()], 10_000.0)
    # The chart is NAMED in this message now that the executor runs the whole M1..D1 ladder.
    # "bars unavailable" on a desk hunting seven charts does not say which bars, and the first
    # question about a missing read is always which chart it was for.
    assert f"[{_NAME}] FAMILY-EXEC: H1 bars unavailable; skipped" in ns["_logs"]
    # A degenerate stop and a zero lot each stop the order before the venue.
    flat = _fake_mt5(rows)
    ns = _family_ns(tmp_path, flat, monkeypatch, armed_file=True, sig_hour=_sig_hour(rows),
                    signals=lambda closed, side: [_signal(closed.index[-1], stop=1.1102)])
    ns["run_family_sleeves"]({"armed": True}, [_sleeve()], 10_000.0)
    assert f"[{_NAME}] FAMILY-EXEC: degenerate stop distance; skipped" in ns["_logs"]
    ns = _family_ns(tmp_path, _fake_mt5(rows), monkeypatch, armed_file=True,
                    sig_hour=_sig_hour(rows))
    ns["promoted_lot"] = lambda *a, **k: 0.0
    ns["run_family_sleeves"]({"armed": True}, [_sleeve()], 10_000.0)
    assert f"[{_NAME}] FAMILY-EXEC: allocator gave this sleeve no heat; skipped" in ns["_logs"]


def test_the_time_exit_closes_the_position_and_tells_the_book(tmp_path, monkeypatch) -> None:
    rows = _rows()
    off = _sig_hour(rows, off=True)                  # off the signal hour: only the TTL runs
    past = (datetime.now(tz=UTC) - timedelta(minutes=1)).isoformat()
    ns = _family_ns(tmp_path, _fake_mt5(rows), monkeypatch, armed_file=True, sig_hour=off)
    st = {"armed": True, "generic": {_NAME: {"open_ttl_until": past}}}
    ns["run_family_sleeves"](st, [_sleeve()], 10_000.0)
    assert ns["_closes"] == [("close", "EURUSD")]
    assert ns["_book"] == [("target", _NAME, "EURUSD", 0.0, "ttl")]
    assert "open_ttl_until" not in st["generic"][_NAME]
    ns = _family_ns(tmp_path, _fake_mt5(rows), monkeypatch, armed_file=False, sig_hour=off)
    st = {"armed": True, "generic": {_NAME: {"open_ttl_until": past}}}
    ns["run_family_sleeves"](st, [_sleeve()], 10_000.0)
    assert ns["_closes"] == [] and f"[{_NAME}] SHADOW would TTL-close open position(s)" in ns["_logs"]


# --------------------------------------------------------------------------------- the fences

def test_the_source_fences_the_desk_runs_still_hold_on_the_adapter() -> None:
    """The immutable governance fence and the L1.67 units fence read THIS file's source. The
    split moved the laws out; the wiring they name stays here as real code."""
    assert "solved, why = allocator_heat()" in _GW_SRC
    assert "from_book: bool = False" in _GW_SRC and "if from_book:" in _GW_SRC
    assert _GW_SRC.count('from_book=(s.get("sized_by") == "allocator_book")') == 3
    assert 'art.get("book_fallback")' in _GW_SRC
    assert "import MetaTrader5 as mt5" in _GW_SRC
    assert "from mt5desk import decision_core as _core" in _GW_SRC


@pytest.mark.parametrize("name", ["cap_by_heat", "promoted_lot", "auto_lot", "realised_q",
                                  "heat_budget", "stop_distance", "diagnose", "entry_is_legal",
                                  "state_allows", "bracket_deadline", "day_range",
                                  "bracket_spec", "roster", "hibernated", "release_gate"])
def test_every_decision_the_gateway_relies_on_lives_in_the_core(name: str) -> None:
    assert callable(getattr(dc, name)), f"decision_core has no {name}"


# ------------------------------------------------- the gold book's day end vs the scalp lane
def _positions_mt5(positions: list[SimpleNamespace]) -> SimpleNamespace:
    sent: list[dict] = []
    return SimpleNamespace(
        positions_get=lambda symbol=None: [p for p in positions if p.symbol == symbol],
        symbol_info_tick=lambda symbol: SimpleNamespace(bid=100.0, ask=100.1),
        order_send=lambda req: (sent.append(req) or SimpleNamespace(retcode=10009, comment="")),
        TRADE_ACTION_DEAL=1, ORDER_TYPE_SELL=1, ORDER_TYPE_BUY=0, POSITION_TYPE_BUY=0,
        sent=sent)


def _pos(ticket: int, comment: str, symbol: str = "XAUUSD") -> SimpleNamespace:
    return SimpleNamespace(ticket=ticket, symbol=symbol, volume=0.02, type=0, comment=comment)


def test_the_end_of_day_close_leaves_the_scalp_lane_s_positions_to_their_own_exit(
) -> None:
    """MEASURED 2026-09-08 on the tree: `close_positions(st, symbol)` at CLOSE_HOUR closed every
    XAUUSD position -- a scalp basket opened at 19:31 by an 'all'-session M15 sleeve was flat
    at 19:32, spread paid for nothing, while its forward clock had certified holding to the
    time exit. The close is now scoped by the lane's order-comment tag."""
    logs: list[str] = []
    mt5 = _positions_mt5([_pos(1, "DWgold_london_am"), _pos(2, "DWxau_m15_anti_momentum_all"),
                          _pos(3, "DWgold_afternoon")])
    ns = _exec(("close_positions", "scalp_position_tags"),
               {"mt5": mt5, "log": logs.append, "MAGIC": 1})
    sleeves = [{"name": "gold_london_am", "symbol": "XAUUSD"},
               {"name": "xau_m15_anti_momentum_all", "symbol": "XAUUSD", "exec": "scalp_market"}]
    keep = ns["scalp_position_tags"](sleeves)
    assert keep == frozenset({"DWxau_m15_anti_momentum_all"})
    ns["close_positions"]({"armed": True}, "XAUUSD", keep_tags=keep)
    assert sorted(r["position"] for r in mt5.sent) == [1, 3]        # the gold book, both legs
    # Friday's weekend close is every lane's: no keep set, every position goes flat.
    mt5.sent.clear()
    ns["close_positions"]({"armed": True}, "XAUUSD")
    assert sorted(r["position"] for r in mt5.sent) == [1, 2, 3]


def test_the_scalp_tag_is_the_lane_s_own_and_only_the_scalp_lane_s() -> None:
    ns = _exec(("scalp_position_tags",), {})
    assert ns["scalp_position_tags"]([{"name": "gold_asia"}, {"name": "x", "exec": "family_market"},
                                      {"exec": "scalp_market"}]) == frozenset()
    tag = ns["scalp_position_tags"]([{"name": "a" * 40, "exec": "scalp_market"}])
    assert tag == frozenset({("DW" + "a" * 40)[:31]})            # the venue's 31-char comment


def test_main_scopes_the_daily_close_and_not_the_friday_one() -> None:
    """Pinned on the source: the daily backstop passes the scalp tags, the weekend close does
    not, and the daily one comes first."""
    daily = _GW_SRC.index('close_positions(st, s["symbol"], keep_tags=keep)')
    friday = _GW_SRC.index("Friday: weekend close, EVERY lane")
    assert daily < friday
    assert "keep = scalp_position_tags(sleeves)" in _GW_SRC[:daily]
    after = _GW_SRC[friday:friday + 200]
    assert 'close_positions(st, s["symbol"])' in after and "keep_tags" not in after


def test_no_bracket_is_sent_at_or_after_the_cancel_hour() -> None:
    """The bracket loop had a lower bound (the signal hour) and no upper one: a gateway armed
    at 22:40 broker sent two real brackets and cancelled them in the same pass."""
    loop = _GW_SRC[_GW_SRC.index('if st["last_bracket_date"] == day_key:'):]
    sig = loop.index('if hour < s["sig_hour"]:')
    cancel = loop.index("if _past_cancel_hour(hour):")
    assert sig < cancel < loop.index("sym = mt5.symbol_info(s[\"symbol\"])")
    assert "st[\"placement_pass\"] = tnow.isoformat()" in _GW_SRC


# ------------------------------------------- main(): the pause file and placement idempotence
#
# `main()` is exec'd from the source over the real core with the venue, the clock and every
# file-touching adapter faked, so the two properties the audit found untested (E13) are run
# rather than read: a present pause file sends nothing and writes nothing, and the once-per-day
# guard and the recovery match are what stop a second pass from sending a bracket twice.

#: A Tuesday, 09:30 UTC: past the asia window's 07:00 signal hour, before london_am (13:00),
#: afternoon (17:00), the 19:30 close and the 20:30 cancel. `main()` dates the tick against the
#: wall clock, so the clock it reads is pinned here too.
_WHEN = datetime(2026, 9, 8, 9, 30, tzinfo=UTC)
_DAY = "2026-09-08"


class _Clock(datetime):
    @classmethod
    def now(cls, tz=None):
        return _WHEN.astimezone(tz) if tz else _WHEN.replace(tzinfo=None)


def _gold_rows(n: int = 400) -> list[dict]:
    """Hourly XAUUSD rows ending on the bar forming at _WHEN: a two-dollar range around a slow
    drift, so the asia range (00:00-06:59) is formed and the ATR is measurable."""
    idx = pd.date_range(end=pd.Timestamp(_WHEN).floor("h"), periods=n, freq="h")
    base = 2000.0 + np.linspace(0, 4.0, n)
    return [{"time": int(t.timestamp()), "open": b, "high": b + 1.0, "low": b - 1.0,
             "close": b + 0.2, "tick_volume": 50.0} for t, b in zip(idx, base, strict=True)]


def _quote(rows: list[dict]) -> tuple[float, float]:
    """A bid/ask inside the asia range, clear of the 20-point freeze band on both edges, so the
    bracket's two pending stops are legal and `place_bracket` sends both."""
    hi, lo, _ = dc.bracket_from_bars(dc.h1_frame(rows), None, 7, 0.01, 20)
    mid = (hi + lo) / 2.0
    return mid - 0.05, mid + 0.05


class _Terminal:
    """A venue that answers every read `main()` makes and records every order it is sent."""

    TIMEFRAME_H1 = 16385
    TRADE_ACTION_PENDING, TRADE_ACTION_DEAL = 5, 1
    ORDER_TYPE_BUY, ORDER_TYPE_SELL, ORDER_TYPE_BUY_STOP, ORDER_TYPE_SELL_STOP = 0, 1, 4, 5
    ORDER_FILLING_RETURN, ORDER_TIME_GTC, ORDER_TIME_SPECIFIED = 2, 0, 1
    SYMBOL_EXPIRATION_SPECIFIED = 4

    def __init__(self, rows: list[dict], bid: float, ask: float) -> None:
        self.rows, self.bid, self.ask = rows, bid, ask
        self.pending: list[SimpleNamespace] = []
        self.sent: list[dict] = []

    def terminal_info(self):
        return SimpleNamespace(connected=True)

    def initialize(self, **kw):
        return True

    def shutdown(self):
        return None

    def last_error(self):
        return (0, "")

    def symbol_info_tick(self, symbol):
        return SimpleNamespace(time=int(_WHEN.timestamp()), bid=self.bid, ask=self.ask)

    def account_info(self):
        return SimpleNamespace(equity=10_000.0, margin_free=9_000.0, login=1, server="demo")

    def positions_get(self, symbol=None):
        return []

    def symbol_info(self, symbol):
        return SimpleNamespace(trade_tick_size=0.01, trade_stops_level=20, point=0.01,
                               volume_min=0.01, volume_step=0.01, expiration_mode=0)

    def copy_rates_from_pos(self, symbol, tf, start, count):
        return self.rows

    def orders_get(self, symbol=None):
        return list(self.pending)

    def order_send(self, req):
        self.sent.append(req)
        return SimpleNamespace(retcode=10009, order=len(self.sent), comment="done")


def _main_ns(tmp_path: Path, monkeypatch, mt5: _Terminal, *, paused: bool,
             state: dict | None) -> dict:
    """`main` and the placement path exec'd from the source, over the real core, with the
    pause file read by THE REAL READER (`mt5desk.config.gateway_paused`) pointed at a private
    data/ directory, and every venue read, file write and sibling adapter faked."""
    data = tmp_path / "data"
    data.mkdir(exist_ok=True)
    pause = data / "GATEWAY_PAUSED"
    monkeypatch.setattr(_cfg, "PAUSE_FILE", pause)
    if paused:
        pause.write_text("paused by test", "utf-8")
    state_file = data / "gateway_state.json"
    if state is not None:
        state_file.write_text(json.dumps({"brackets": {}, "position": None,
                                          "last_bracket_date": None, **state}), "utf-8")
    logs: list[str] = []
    decisions: list[dict] = []
    intents: list[dict] = []
    calls: list[str] = []
    ns = {
        "gateway_paused": _cfg.gateway_paused, "mt5": mt5, "datetime": _Clock, "json": json,
        "STATE": state_file, "PAUSED": pause, "log": logs.append, "decay_factor": decay_factor,
        "connect": lambda: calls.append("connect") or True,
        "sleeve_set": lambda: dc.roster({}, [])[0],
        "manage_open_positions": lambda st, sleeves: None,
        "release_gate": lambda: (True, "release identity ok (test)"),
        "regime_hibernate": lambda sleeves: set(),
        "load_sleeves": lambda: [],
        "ledger_rows": lambda: [],
        "measure_from_ledger": lambda rows, acc, exposures=None: (None, "k_eff unmeasured"),
        "_prov": SimpleNamespace(current_account=lambda info: {}),
        "allocator_book": lambda: (None, "no allocator book (test)"),
        "cap_by_heat": lambda sleeves, equity, per_sleeve_q=None, k_eff=None: (sleeves, None),
        "run_family_sleeves": lambda st, sleeves, equity: None,
        "run_scalp_sleeves": lambda st, sleeves, equity: None,
        "_net_routes": lambda symbols: None,
        "gold_lot": lambda *a, **k: 0.02, "gold_min_lot": lambda: 0.02, "min_lot": lambda: 0.01,
        "promoted_lot": lambda *a, **k: 0.01, "realised_q": lambda *a, **k: 0.0075,
        "sleeve_live_n": lambda name: 0,
        "margin_ok": lambda symbol, lot, price: True,
        "_record_decision": lambda **row: decisions.append(row),
        "_record_intent": lambda **row: intents.append(row),
        "_record_vetoed_bracket": lambda *a, **k: False,
        "_expiry_request": lambda symbol, sleeve="", window=None: {"type_time": 0},
        "expire_stale_brackets": lambda st: 0,
        "cancel_pending": lambda st, symbol: None,
        "close_positions": lambda st, symbol, keep_tags=frozenset(): None,
        "scalp_position_tags": lambda sleeves: frozenset(),
        "record_trades": lambda st, sleeves: None,
        "reconcile": lambda st: {**st, "position": [], "pending": []},
        "_logs": logs, "_decisions": decisions, "_intents": intents, "_calls": calls,
        "_state_file": state_file,
    }
    # `_sleeve_identity` rides along for the same reason it does in the family harness above: the
    # send site spreads it onto the intent row and it is pure over the sleeve dict.
    #
    # IT WAS MISSING AND THE GAP WAS INVISIBLE (found 2026-09-09 while routing the allocator's
    # fraction into the gold book). The gold branch used to call `gold_lot`, a `def` in
    # gateway.py that is NOT in this name list, so it raised NameError inside the placement
    # try/except on EVERY pass, logged SKIPPED and continued -- and this test's "sends nothing"
    # passed because nothing was ever sized, not because the recovery worked. The moment the
    # branch called an IMPORTED helper instead, the slice resolved it, the real path ran, and the
    # missing name surfaced. A green test that never reached the code it names is worse than a
    # red one.
    return _exec(("main", "_past_cancel_hour", "place_bracket", "note_placement",
                  "_rejection_streak_expired", "load_state", "save_state", "now",
                  "_sleeve_identity"), ns)


def test_main_with_the_pause_file_present_sends_nothing_and_writes_no_state(
        tmp_path, monkeypatch) -> None:
    """The pause is consulted before the terminal is touched: no connect, no read, no order,
    no state file, one log line saying why."""
    rows = _gold_rows()
    mt5 = _Terminal(rows, *_quote(rows))
    ns = _main_ns(tmp_path, monkeypatch, mt5, paused=True, state=None)
    assert _cfg.gateway_paused() is True
    ns["main"]()
    assert mt5.sent == [] and ns["_calls"] == []
    assert not ns["_state_file"].exists()
    assert ns["_decisions"] == [] and ns["_intents"] == []
    assert ns["_logs"] == ["gateway paused (data/GATEWAY_PAUSED present); no trading this pass"]


def test_a_second_pass_in_one_day_recovers_the_bracket_the_terminal_holds_and_sends_nothing(
        tmp_path, monkeypatch) -> None:
    """Three mechanisms, run: the first pass places asia's two legs; the same pass again is
    stopped by the once-per-day guard; a pass that has LOST its state (a restart) against a
    terminal still holding both pending orders takes the `recovered` path and sends nothing."""
    rows = _gold_rows()
    mt5 = _Terminal(rows, *_quote(rows))
    ns = _main_ns(tmp_path, monkeypatch, mt5, paused=False, state={"armed": True})
    ns["main"]()
    assert [r["type"] for r in mt5.sent] == [mt5.ORDER_TYPE_BUY_STOP, mt5.ORDER_TYPE_SELL_STOP]
    assert {r["comment"] for r in mt5.sent} == {"DWgold_asia"}   # 09:30 is asia's hour alone
    st = json.loads(ns["_state_file"].read_text("utf-8"))
    placed = st["brackets"]["gold_asia"]
    assert placed["date"] == _DAY and "recovered" not in placed
    assert [o["retcode"] for o in placed["result"]["orders"]] == [10009, 10009]
    assert st["last_bracket_date"] == _DAY and ns["_calls"] == ["connect"]

    ns["main"]()                                          # same day, state intact: the guard
    assert len(mt5.sent) == 2

    mt5.pending = [SimpleNamespace(ticket=i + 1, symbol="XAUUSD", price_open=r["price"])
                   for i, r in enumerate(mt5.sent)]
    ns["_state_file"].write_text(json.dumps({"armed": True, "brackets": {},
                                             "last_bracket_date": None}), "utf-8")
    ns["main"]()                                          # state lost, orders still resting
    assert len(mt5.sent) == 2, "a bracket the terminal already holds was sent again"
    st = json.loads(ns["_state_file"].read_text("utf-8"))
    recovered = st["brackets"]["gold_asia"]
    assert recovered["recovered"] is True and recovered["date"] == _DAY
    assert recovered["spec"]["buy_stop"]["price"] == placed["spec"]["buy_stop"]["price"]
    assert f"recovered [gold_asia] bracket for {_DAY}" in ns["_logs"]


def test_the_pause_file_readers_look_under_data_and_main_consults_gateway_paused(
        tmp_path, monkeypatch) -> None:
    """THE PATH FACTS THE AUDIT MEASURED (E13, 2026-09-08). Every reader of the pause flag --
    config.py:54 `PAUSE_FILE = DATA / "GATEWAY_PAUSED"`, gateway.py:97 `PAUSED = BASE / "data" /
    "GATEWAY_PAUSED"` -- opens desks/mt5/data/GATEWAY_PAUSED, and `main()`'s first statement
    consults `gateway_paused()`. A file is also TRACKED at desks/mt5/GATEWAY_PAUSED, the desk
    root: no reader opens it. This test pins the reader path and the consult and NOTHING about
    that root file -- it must not be moved, copied or "fixed" into data/, because a file at the
    reader's path pauses the live desk.
    """
    import inspect
    assert _cfg.PAUSE_FILE == _cfg.DATA / "GATEWAY_PAUSED"
    assert _cfg.desk_root() / "data" == _cfg.DATA
    assert "return PAUSE_FILE.exists()" in inspect.getsource(_cfg.gateway_paused)
    assert 'PAUSED = BASE / "data" / "GATEWAY_PAUSED"' in _GW_SRC
    assert "from mt5desk.config import desk_root, gateway_paused, terminal_path" in _GW_SRC
    main = next(n for n in _GW_TREE.body if isinstance(n, ast.FunctionDef) and n.name == "main")
    first = main.body[0]
    assert isinstance(first, ast.If) and isinstance(first.test, ast.Call)
    assert first.test.func.id == "gateway_paused" and first.test.args == []
    assert any(isinstance(s, ast.Return) for s in first.body)
    # The reader's path is under data/, and it is not the desk root the stale file sits at.
    assert _cfg.PAUSE_FILE.parent.name == "data"
    assert _cfg.PAUSE_FILE != _DESK / "GATEWAY_PAUSED"
    monkeypatch.setattr(_cfg, "PAUSE_FILE", tmp_path / "data" / "GATEWAY_PAUSED")
    assert _cfg.gateway_paused() is False
