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

from mt5desk import decision_core as dc  # noqa: E402

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
    monkeypatch.setitem(sys.modules, "research.run_hunt16", SimpleNamespace(
        FAMILIES={"fam": fam}, WINDOWS={"asia": {"signal_at": sig_hour, "range_start": 0}}))
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
    return _exec(("run_family_sleeves", "_family_chart"), ns)


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
    last_bar = dc.h1_frame(rows).index[-2]
    assert st["generic"][_NAME]["open_ttl_until"] == dc.family_ttl_until(last_bar, 12)
    assert [b[0] for b in ns["_book"]] == ["target", "fill", "outcome"]
    assert ns["_book"][1][3] == 0.12 and ns["_book"][1][4] == 1.1103      # the venue's fill
    assert any("FAMILY-EXEC ORDER -> retcode=10009" in x for x in ns["_logs"])
    # The same bar again places nothing.
    ns["run_family_sleeves"](st, [_sleeve()], 10_000.0)
    assert len(mt5.sent) == 1


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
    assert ns["_logs"].count(f"[{_NAME}] FAMILY-EXEC refused: family/selector has no exact "
                             "executable") == 2
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
