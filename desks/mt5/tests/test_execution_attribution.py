"""Execution error must be a number once fills exist, and the world it was paid in must be recorded.

`allocator_attribution._execution_term` returned UNMEASURED with the reason "per-fill slippage
capture not yet wired (needs requested vs filled price on the ledger row)". That was stale:
`mt5desk.markout` has joined `order_intents.jsonl` to `live_ledger.jsonl` by order ticket and
reported requested-versus-filled per fill since the first trade. The capture was wired; the reader
was not. These pin that the reader now reads it, that the sign is a subtraction from edge, and
that a demo/live mixed ledger is refused rather than averaged.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

_DESK = Path(__file__).resolve().parents[1]
_ROOT = _DESK.parent.parent
for p in (str(_DESK), str(_DESK / "research"), str(_ROOT)):
    if p not in sys.path:
        sys.path.insert(0, p)

from mt5desk import markout  # noqa: E402
from research import allocator_attribution as attr  # noqa: E402

UNMEASURED = attr.UNMEASURED


def _intent(ticket: int, intended: float, side: str = "buy_stop") -> dict:
    return {"ticket": ticket, "intended": intended, "side": side, "sleeve": "S", "symbol": "XAUUSD"}


def _deal(ticket: int, fill: float, risk: float = 10.0, login: int = 1,
          server: str = "Fusion-Live", kind: str = "live") -> dict:
    return {"order": ticket, "fill_price": fill, "risk_quote": risk, "sleeve": "S",
            "symbol": "XAUUSD", "side": "buy_stop", "deal": ticket * 10,
            "login": login, "server": server, "account_kind": kind}


def _wire(monkeypatch, tmp_path, intents, deals):
    (tmp_path / "order_intents.jsonl").write_text(
        "\n".join(json.dumps(r) for r in intents), "utf-8")
    (tmp_path / "live_ledger.jsonl").write_text(
        "\n".join(json.dumps(r) for r in deals), "utf-8")
    monkeypatch.setattr(attr, "BASE", tmp_path.parent)
    monkeypatch.setattr(tmp_path.parent, "__class__", tmp_path.parent.__class__, raising=False)


def test_shadow_basis_still_refuses_because_it_would_measure_the_model_on_itself():
    out = attr._execution_term("shadow_forward")
    assert out["value"] == UNMEASURED
    assert "cost model measured against itself" in out["why"]


def test_a_live_basis_with_no_fills_says_so_with_counts_rather_than_a_zero():
    out = attr._execution_term("live")
    assert out["value"] == UNMEASURED
    assert "NOT a clean bill of health" in out["why"]
    assert "n_unfilled_intents" in out
    assert "not yet wired" not in out["why"], "the stale reason is back"


def test_slippage_becomes_a_signed_number_once_fills_exist(tmp_path, monkeypatch):
    data = tmp_path / "data"
    data.mkdir()
    intents = [_intent(1, 100.0), _intent(2, 200.0)]
    # Both fills are 0.5 WORSE than intended on a long, at 10.0 of risk -> 0.05 R each.
    deals = [_deal(1, 100.5), _deal(2, 200.5)]
    (data / "order_intents.jsonl").write_text("\n".join(json.dumps(r) for r in intents), "utf-8")
    (data / "live_ledger.jsonl").write_text("\n".join(json.dumps(r) for r in deals), "utf-8")
    monkeypatch.setattr(attr, "BASE", tmp_path)

    out = attr._execution_term("live")
    assert isinstance(out["value"], float)
    assert out["mean_slip_r"] == pytest.approx(0.05, abs=1e-9)
    # SIGN: slippage is a subtraction from edge, so the TERM is negative.
    assert out["value"] == pytest.approx(-0.05, abs=1e-9)
    assert out["n_matched_fills"] == 2


def test_a_favourable_fill_is_reported_as_a_positive_term(tmp_path, monkeypatch):
    data = tmp_path / "data"
    data.mkdir()
    (data / "order_intents.jsonl").write_text(json.dumps(_intent(1, 100.0)), "utf-8")
    (data / "live_ledger.jsonl").write_text(json.dumps(_deal(1, 99.8)), "utf-8")
    monkeypatch.setattr(attr, "BASE", tmp_path)
    out = attr._execution_term("live")
    assert out["value"] > 0


def test_a_mixed_demo_and_live_ledger_is_refused_not_averaged(tmp_path, monkeypatch):
    """Demo stops fill at the trigger, so blending drags the mean toward 'no slippage'."""
    data = tmp_path / "data"
    data.mkdir()
    intents = [_intent(1, 100.0), _intent(2, 100.0)]
    deals = [_deal(1, 100.5, login=1, server="Fusion-Live", kind="live"),
             _deal(2, 100.0, login=2, server="Fusion-Demo", kind="demo")]
    (data / "order_intents.jsonl").write_text("\n".join(json.dumps(r) for r in intents), "utf-8")
    (data / "live_ledger.jsonl").write_text("\n".join(json.dumps(r) for r in deals), "utf-8")
    monkeypatch.setattr(attr, "BASE", tmp_path)
    out = attr._execution_term("live")
    assert out["value"] == UNMEASURED
    assert "MIXED" in out["why"]


def test_an_unfilled_intent_is_never_counted_as_a_zero_slippage_fill(tmp_path, monkeypatch):
    data = tmp_path / "data"
    data.mkdir()
    intents = [_intent(1, 100.0), _intent(2, 100.0), _intent(3, 100.0)]
    (data / "order_intents.jsonl").write_text("\n".join(json.dumps(r) for r in intents), "utf-8")
    (data / "live_ledger.jsonl").write_text(json.dumps(_deal(1, 100.5)), "utf-8")
    monkeypatch.setattr(attr, "BASE", tmp_path)
    out = attr._execution_term("live")
    assert out["n_matched_fills"] == 1
    assert out["n_unfilled_intents"] == 2
    assert out["mean_slip_r"] == pytest.approx(0.05, abs=1e-9), \
        "unfilled brackets must not dilute the mean toward zero"


def test_the_reader_actually_goes_through_markout(monkeypatch):
    """Behavioural, not a text match: break markout and the reason must surface from there."""
    def _boom(*_a, **_k):
        raise RuntimeError("markout was reached")

    monkeypatch.setattr(markout, "compute", _boom)
    out = attr._execution_term("live")
    assert out["value"] == UNMEASURED
    assert "markout was reached" in out["why"]


# ------------------------------------------------------------------------------------------
# The decision context recorded at placement
# ------------------------------------------------------------------------------------------

# gateway.py imports MetaTrader5 and cannot be imported off Windows, so these read its source --
# the same adaptation test_cancel_pending_api.py and test_risk_units.py use. The two functions
# under test touch no mt5 symbol, so they are executed in an isolated namespace rather than
# merely pattern-matched: a text assertion would pass on code that raises.
_GATEWAY_SRC = (_DESK / "mt5desk" / "gateway.py").read_text("utf-8")


def _gateway_func(*names: str, ns: dict | None = None) -> dict:
    import ast

    tree = ast.parse(_GATEWAY_SRC)
    wanted = set(names)
    body = [n for n in tree.body
            if isinstance(n, ast.FunctionDef) and n.name in wanted]
    assert len(body) == len(wanted), f"missing from gateway.py: {wanted - {b.name for b in body}}"
    env: dict = {"json": json, "Path": Path, "_SV_CACHE": (0.0, ""), "now": lambda: "T",
                 "log": lambda *_a, **_k: None}
    env.update(ns or {})
    exec(compile(ast.Module(body=body, type_ignores=[]), "<gateway>", "exec"), env)  # noqa: S102
    return env


class _FakeMT5:
    """Just enough of the terminal for `_position_entry`: a position opened by pending order 7
    (entry deal 71 at 2000.5) and closed by the server's order 7001."""
    DEAL_ENTRY_IN = 0
    DEAL_ENTRY_OUT = 1

    class _O:
        def __init__(self, ticket, sl, tp, comment):
            self.ticket, self.sl, self.tp, self.comment = ticket, sl, tp, comment

    class _D:
        def __init__(self, ticket, order, entry, price):
            self.ticket, self.order, self.entry, self.price = ticket, order, entry, price

    @staticmethod
    def history_orders_get(position=None):
        assert position == 7
        return [_FakeMT5._O(7, 1981.4, 2038.2, "DWgold_asia"), _FakeMT5._O(7001, 0.0, 0.0, "")]

    @staticmethod
    def history_deals_get(position=None):
        assert position == 7
        return [_FakeMT5._D(71, 7, 0, 2000.5), _FakeMT5._D(72, 7001, 1, 2019.1)]


def test_the_position_entry_returns_the_bridge_to_the_intent():
    """Executed, not pattern-matched: the closing deal's position id yields the entry order (the
    intent's ticket), the entry deal, the entry fill and the stop -- the whole key chain."""
    env = _gateway_func("_position_entry", "_position_context", ns={"mt5": _FakeMT5})
    out = env["_position_entry"](7)
    assert out["entry_order"] == 7 and out["entry_deal"] == 71
    assert out["entry_price"] == 2000.5 and out["sl"] == 1981.4 and out["tp"] == 2038.2
    assert out["comment"] == "DWgold_asia"
    assert env["_position_entry"](None)["entry_order"] is None

    class _Deal:
        position_id = 7

    assert env["_position_context"](_Deal()) == (2000.5, 1981.4, 2038.2, "DWgold_asia")


def test_the_intent_row_carries_the_market_it_was_sent_into():
    """Slippage without the conditions it was paid in averages over every situation at once."""
    import ast

    tree = ast.parse(_GATEWAY_SRC)
    fn = next(n for n in ast.walk(tree)
              if isinstance(n, ast.FunctionDef) and n.name == "place_bracket")
    src = ast.get_source_segment(_GATEWAY_SRC, fn) or ""
    for field in ("decision_bid", "decision_ask", "spread_at_decision", "order_type"):
        assert field in src, f"placement intent does not record {field}"


def test_the_state_vector_id_is_stamped_and_never_raises(tmp_path):
    env = _gateway_func("_state_vector_id", ns={"BASE": tmp_path})
    sid = env["_state_vector_id"]

    env["_SV_CACHE"] = (0.0, "")
    assert sid() == "", "a missing artifact must cost an empty string"

    (tmp_path / "data").mkdir()
    (tmp_path / "data" / "state_vector.json").write_text(json.dumps({"id": "abc123"}), "utf-8")
    env["_SV_CACHE"] = (0.0, "")
    assert sid() == "abc123"

    (tmp_path / "data" / "state_vector.json").write_text("{ not json", "utf-8")
    env["_SV_CACHE"] = (0.0, "")
    assert sid() == "", "a corrupt artifact must not reach the money path"


#: The names the id helpers need beyond `_gateway_func`'s seed: the gateway's own imports.
_ID_NS = {"contextlib": __import__("contextlib"), "hashlib": __import__("hashlib"),
          "datetime": __import__("datetime").datetime, "UTC": __import__("datetime").UTC}
_STAMP = "2026-09-08T10:15:33+00:00"


def test_record_intent_stamps_the_state_and_never_raises(tmp_path):
    env = _gateway_func("_record_intent", "_intent_id", "_minute_of",
                        ns={"INTENTS": tmp_path / "intents.jsonl",
                            "_state_vector_id": lambda: "sv999", "now": lambda: _STAMP,
                            **_ID_NS})
    iid = env["_record_intent"](sleeve="S", symbol="XAUUSD", side="buy_stop", intended=1.0)
    row = json.loads((tmp_path / "intents.jsonl").read_text("utf-8").strip())
    assert row["state_vector_id"] == "sv999"
    assert row["time"] == _STAMP
    # THE ADDRESS: derived from the row's own time and returned to the caller, so the decision
    # written beside the placement can carry the identical key.
    assert row["intent_id"] == iid and len(iid) == 16

    # An unwritable path must be swallowed: telemetry may never break the money path.
    env["INTENTS"] = Path("/proc/definitely/not/writable/x.jsonl")
    assert env["_record_intent"](sleeve="S") is None


def test_the_intent_id_is_the_decision_datasets_row_id():
    """Formula parity, executed: the gateway's copy must hash exactly what `decision_dataset`
    hashes, including the minute floor, the 'Z' and naive spellings, and a side-less refusal."""
    from libs.research.decision_dataset import minute_of, row_id

    env = _gateway_func("_intent_id", "_minute_of", ns=_ID_NS)
    for stamp in (_STAMP, "2026-09-08T10:15:33Z", "2026-09-08T10:15:33",
                  "2026-09-08T12:15:33.250+02:00"):
        want = row_id("XAUUSD", "gold_asia", "buy_stop", minute_of(stamp))
        assert env["_intent_id"]("XAUUSD", "gold_asia", "buy_stop", stamp) == want, stamp
    assert env["_intent_id"]("XAUUSD", "gold_asia", None, _STAMP) == \
        row_id("XAUUSD", "gold_asia", "", minute_of(_STAMP))
    # Two stamps inside one minute share the address; the next minute is another one.
    a = env["_intent_id"]("X", "s", "buy", "2026-09-08T10:15:01+00:00")
    assert a == env["_intent_id"]("X", "s", "buy", "2026-09-08T10:15:59+00:00")
    assert a != env["_intent_id"]("X", "s", "buy", "2026-09-08T10:16:00+00:00")
    # A stamp the helper cannot parse raises here and is suppressed by the recorders.
    with pytest.raises(ValueError):
        env["_intent_id"]("X", "s", "buy", "T")


class _BracketMT5:
    """A terminal that accepts a pending stop and remembers exactly what it was asked for."""
    TRADE_ACTION_PENDING = 5
    ORDER_TYPE_BUY_STOP = 4
    ORDER_TYPE_SELL_STOP = 5
    ORDER_FILLING_RETURN = 2

    def __init__(self):
        self.sent = []

    @staticmethod
    def symbol_info_tick(symbol):
        from types import SimpleNamespace
        return SimpleNamespace(bid=2000.0, ask=2000.3)

    @staticmethod
    def symbol_info(symbol):
        from types import SimpleNamespace
        return SimpleNamespace(point=0.01, trade_stops_level=0)

    def order_send(self, req):
        from types import SimpleNamespace
        self.sent.append(dict(req))
        return SimpleNamespace(retcode=10009, order=700 + len(self.sent), comment="done")


def _bracket_env(tmp_path, mt5):
    import time
    decisions: list[dict] = []
    env = _gateway_func("place_bracket", "_record_intent", "_intent_id", "_minute_of",
                        "_sleeve_identity",
                        ns={"mt5": mt5, "time": time, "MAGIC": 341953, "now": lambda: _STAMP,
                            "INTENTS": tmp_path / "intents.jsonl",
                            "_state_vector_id": lambda: "sv1", "_release_id": lambda: "rel1",
                            "entry_is_legal": lambda *a: (True, ""),
                            "diagnose": lambda *a: "",
                            "_expiry_request": lambda *a, **k: {},
                            "_record_decision": lambda **row: decisions.append(row),
                            "note_placement": lambda *a: True, **_ID_NS})
    env["_decisions"] = decisions
    return env


_SPEC = {"buy_stop": {"price": 2005.0, "sl": 1995.0, "tp": 2025.0},
         "sell_stop": {"price": 1995.0, "sl": 2005.0, "tp": 1975.0}}


def test_place_bracket_sends_the_same_request_and_records_latency_identity_and_one_address(
        tmp_path):
    """Executed, not pattern-matched. The request dict that reaches the venue keeps exactly the
    keys it had; the intent row gains `latency_ms`, the sleeve's `certificate` and `sleeve_id`,
    and an `intent_id`; and the decision written beside it carries that same id."""
    mt5 = _BracketMT5()
    env = _bracket_env(tmp_path, mt5)
    row = {"name": "gold_asia", "symbol": "XAUUSD", "certificate": "XAUUSD.session_bracket.asia",
           "sleeve_id": "1903a4cc90212b4c29d5"}
    out = env["place_bracket"]({"armed": True}, _SPEC, "gold_asia", "XAUUSD", 0.06,
                               sleeve_row=row)
    assert [o["retcode"] for o in out["orders"]] == [10009, 10009]
    for req in mt5.sent:
        assert set(req) == {"action", "symbol", "volume", "type", "price", "sl", "tp",
                            "type_filling", "deviation", "magic", "comment"}
        assert req["volume"] == 0.06 and req["comment"] == "DWgold_asia"
    intents = [json.loads(ln) for ln in
               (tmp_path / "intents.jsonl").read_text("utf-8").splitlines() if ln.strip()]
    assert [i["side"] for i in intents] == ["buy_stop", "sell_stop"]
    for i in intents:
        assert isinstance(i["latency_ms"], float) and i["latency_ms"] >= 0.0
        assert i["certificate"] == row["certificate"] and i["sleeve_id"] == row["sleeve_id"]
        assert i["order_type"] == "pending_stop" and i["decision_bid"] == 2000.0
    # ONE ADDRESS: the decision row beside each leg carries the intent's own id, and the two
    # legs of one bracket are two addresses (the side is in the key).
    placed = [d for d in env["_decisions"] if d["reason"] == "placed"]
    assert [d["intent_id"] for d in placed] == [i["intent_id"] for i in intents]
    assert intents[0]["intent_id"] != intents[1]["intent_id"]


def test_place_bracket_without_a_roster_row_claims_no_identity(tmp_path):
    mt5 = _BracketMT5()
    env = _bracket_env(tmp_path, mt5)
    env["place_bracket"]({"armed": True}, _SPEC, "gold_asia", "XAUUSD", 0.06)
    intents = [json.loads(ln) for ln in
               (tmp_path / "intents.jsonl").read_text("utf-8").splitlines() if ln.strip()]
    assert len(intents) == 2 and len(mt5.sent) == 2
    for i in intents:
        assert "certificate" not in i and "sleeve_id" not in i
        assert i["intent_id"] and "latency_ms" in i


def test_a_decision_row_carries_the_intent_id_through_the_ledger_writer(tmp_path):
    """The writer normalises the gateway's keyword dict; the address must survive it, and a
    refusal recorded with no intent derives the same formula from its own row."""
    from libs.research.decision_ledger import write_decision

    path = tmp_path / "decisions.jsonl"
    assert write_decision(path, {"sleeve": "s", "symbol": "X", "side": "buy_stop", "taken": True,
                                 "reason": "placed", "time": _STAMP, "intent_id": "abc"})
    assert json.loads(path.read_text("utf-8").strip())["intent_id"] == "abc"

    env = _gateway_func("_record_decision", "_intent_id", "_minute_of",
                        ns={"DECISIONS": path, "now": lambda: _STAMP,
                            "_state_vector_id": lambda: "sv1", "_release_id": lambda: "rel1",
                            "_decision_portfolio_context": lambda s: {}, **_ID_NS})
    env["_record_decision"](sleeve="gold_asia", symbol="XAUUSD", side="buy_stop", lot=0.06,
                            price=1.0, sl=0.9, tp=1.2, taken=False, reason="margin_guard")
    veto = json.loads(path.read_text("utf-8").splitlines()[-1])
    assert veto["intent_id"] == env["_intent_id"]("XAUUSD", "gold_asia", "buy_stop", _STAMP)
    assert veto["taken"] is False and veto["veto_reason"] == "margin_guard"


def test_markout_still_reports_slippage_as_a_share_of_the_edge():
    """The number that decides whether an edge is worth trading, not just a cost to note."""
    m = markout.compute([_intent(1, 100.0)], [_deal(1, 100.5)], book_edge_r=0.159)
    assert m.n_matched == 1
    assert m.edge_share == pytest.approx(0.05 / 0.159, rel=1e-6)
