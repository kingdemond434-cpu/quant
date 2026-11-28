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


def test_a_family_that_takes_session_keeps_every_session_distinct() -> None:
    """Auditor HOLD 2026-11-11: `family_scalp` and the joint-window families read `session`
    themselves; new_york, overlap and all must never collapse onto the all-hours identity, and
    their london is not the shared table's (8, 16)."""
    from research.cert_duplicates import executable_identity

    def scalp(symbol: str = "", session: str = "all", lookback: int = 5) -> None:
        return None

    def joint(symbol: str = "", session: str = "any") -> None:
        return None

    ids = {s: executable_identity("EURUSD", "scalp", {"session": s}, fn=scalp)
           for s in ("all", "london", "new_york", "overlap")}
    assert len(set(ids.values())) == 4
    assert (executable_identity("EURUSD", "joint", {"session": "london"}, fn=joint)
            != executable_identity("EURUSD", "joint", {"session": "any"}, fn=joint))
    assert '"session":["kwarg","london"]' in ids["london"]


def test_a_session_name_outside_the_shared_table_is_kept_raw() -> None:
    from research.cert_duplicates import executable_identity

    def plain(symbol: str = "", lookback: int = 20) -> None:
        return None

    overlap = executable_identity("EURUSD", "plain", {"session": "overlap"}, fn=plain)
    allh = executable_identity("EURUSD", "plain", {"session": "all"}, fn=plain)
    none = executable_identity("EURUSD", "plain", {}, fn=plain)
    ny = executable_identity("EURUSD", "plain", {"session": "ny"}, fn=plain)
    assert allh == none != overlap != ny
    assert '"session":[14,22]' in ny
