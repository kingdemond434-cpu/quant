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


def test_record_intent_stamps_the_state_and_never_raises(tmp_path):
    env = _gateway_func("_record_intent",
                        ns={"INTENTS": tmp_path / "intents.jsonl",
                            "_state_vector_id": lambda: "sv999"})
    env["_record_intent"](sleeve="S", symbol="XAUUSD", intended=1.0)
    row = json.loads((tmp_path / "intents.jsonl").read_text("utf-8").strip())
    assert row["state_vector_id"] == "sv999"
    assert "time" in row

    # An unwritable path must be swallowed: telemetry may never break the money path.
    env["INTENTS"] = Path("/proc/definitely/not/writable/x.jsonl")
    env["_record_intent"](sleeve="S")


def test_markout_still_reports_slippage_as_a_share_of_the_edge():
    """The number that decides whether an edge is worth trading, not just a cost to note."""
    m = markout.compute([_intent(1, 100.0)], [_deal(1, 100.5)], book_edge_r=0.159)
    assert m.n_matched == 1
    assert m.edge_share == pytest.approx(0.05 / 0.159, rel=1e-6)
