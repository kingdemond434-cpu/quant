"""Two certificates for one executable rule are found; distinct rules never are (BR1)."""
from __future__ import annotations

from research import cert_duplicates as cd


def carry(df, *, symbol="", min_edge_bp_per_day=0.5, atr_n=20, hold_bars=120, stop_atr=2.0,
          rr=1.5, require_quiet=True):
    return []


def _id(params, sym="CHFNOK", **kw):
    return cd.executable_identity(sym, "carry", params, fn=carry, **kw)


def test_own_symbol_input_and_spelled_defaults_are_the_same_rule():
    base = _id({"timeframe": "M30"})
    assert _id({"input_symbol": "CHFNOK", "timeframe": "M30"}) == base
    assert _id({"timeframe": "m30", "rr": 1.5, "hold_bars": 120.0}) == base
    assert _id({"timeframe": "M30", "session": "all"}) == base
    assert _id({"timeframe": "M30", "regime": "unconditional", "representation": "x"}) == base


def test_what_changes_the_trades_keeps_cells_apart():
    base = _id({"timeframe": "M30"})
    assert _id({"timeframe": "M30", "session": "ny"}) != base
    assert _id({"timeframe": "M15"}) != base
    assert _id({"timeframe": "M30", "require_quiet": False}) != base
    assert _id({"timeframe": "M30", "input_symbol": "EURNOK"}) != base
    assert _id({"timeframe": "M30"}, sym="EURNOK") != base
    assert _id({"timeframe": "M30", "regime": "high_vol"}) != base
    assert _id({"timeframe": "M30", "mechanism_genome": {"a": 1}}) != base   # unreduced, visible


def _row(params, gated, sym="CHFNOK"):
    return {"sym": sym, "gated_at": gated,
            "shadow_spec": {"symbol": sym, "family": "carry", "params": params}}


def test_sweep_names_the_earliest_as_original(monkeypatch):
    monkeypatch.setattr(cd, "_family_fn", lambda fam: carry)
    surv = {"survivors": {
        "external.CHFNOK@M30.carry.p=ce4c": _row({"input_symbol": "CHFNOK", "timeframe": "M30"},
                                                 "2026-10-02"),
        "external.CHFNOK@M30.carry.p=6c59": _row({"timeframe": "M30"}, "2026-10-01"),
        "external.CHFNOK@M30.carry.p=4a55": _row({"timeframe": "M30", "session": "ny"},
                                                 "2026-10-03"),
        "external.X.carry.p=none": {"sym": "X", "shadow_spec": {"family": "carry"}},
    }}
    out = cd.sweep(surv)
    assert out["status"] == "MEASURED" and out["certificates"] == 4
    assert out["duplicate_groups"] == 1 and out["duplicate_certificates"] == 1
    g = out["groups"][0]
    assert g["original"].endswith("6c59")
    assert g["duplicates"] == ["external.CHFNOK@M30.carry.p=ce4c"]
    assert out["by_family"] == {"carry": 1}
    assert out["unrunnable"]["n"] == 1


def test_no_survivors_file_is_unmeasured():
    assert cd.sweep(None)["status"] == cd.UNMEASURED
