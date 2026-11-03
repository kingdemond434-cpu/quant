"""THE LOSS LEARNER: a diagnosed loss mode mints one-step variants on the parameter it names and
nothing else, every variant is a lineage trial, the replacement bar gets HARDER as the lineage
grows, a parent is retired only once its variant is LIVE with capital, a gateway window is never
edited (a request is written instead), and a dry run writes nothing."""
from __future__ import annotations

import json
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

_DESK = Path(__file__).resolve().parents[1]
_ROOT = _DESK.parent.parent
for _p in (str(_ROOT), str(_DESK), str(_DESK / "research")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from research import loss_learner as LL  # noqa: E402

T0 = datetime(2026, 10, 1, 0, 0, tzinfo=UTC)


def _bars(path: list[float], start: datetime = T0) -> pd.DataFrame:
    """H1 bars whose high/low bracket each close by 0.5."""
    idx = pd.date_range(start, periods=len(path), freq="h", tz="UTC")
    c = np.asarray(path, dtype=float)
    return pd.DataFrame({"open": c, "high": c + 0.5, "low": c - 0.5, "close": c}, index=idx)


def _trade(entry: float, sl: float, tp: float, exit_px: float, t_in: int, t_out: int,
           **kw: object) -> dict:
    return {"entry_price": entry, "sl": sl, "tp": tp, "fill_price": exit_px,
            "entry_time": (T0 + timedelta(hours=t_in, minutes=5)).isoformat(),
            "exit_time": (T0 + timedelta(hours=t_out, minutes=5)).isoformat(), **kw}


def test_stop_then_target_is_named() -> None:
    # Long at 100, stop 90, target 120: stopped at hour 3, then price runs to 125.
    path = [100, 99, 95, 90, 100, 110, 125, 125, 125, 125, 125, 125, 125, 125]
    d = LL.diagnose(_trade(100, 90, 120, 90, 0, 3), _bars(path), hold_bars=12)
    assert d["exit_kind"] == "stop" and d["mode"] == "STOP_THEN_TARGET"


def test_giveback_to_stop_and_ran_past_target() -> None:
    gb = [100, 110, 112, 100, 90] + [90] * 10
    d = LL.diagnose(_trade(100, 90, 130, 90, 0, 4), _bars(gb), hold_bars=12)
    assert d["mode"] == "GIVEBACK_TO_STOP" and d["mfe_r"] >= 1.0
    run = [100, 110, 120] + [140] * 12
    d = LL.diagnose(_trade(100, 90, 120, 120, 0, 2), _bars(run), hold_bars=12)
    assert d["mode"] == "RAN_PAST_TARGET"


def test_time_exit_continuation_and_short_side() -> None:
    # Short at 100 (stop 110, target 80), time exit at 98, price then falls to 85.
    path = [100, 99, 98, 90, 85] + [85] * 10
    d = LL.diagnose(_trade(100, 110, 80, 98, 0, 2), _bars(path), hold_bars=12)
    assert d["exit_kind"] == "time" and d["mode"] == "TIME_EXIT_CONTINUATION"
    assert d["r"] == pytest.approx(0.2)


def test_a_trade_without_a_stop_is_unmeasured_not_a_clean_read() -> None:
    d = LL.diagnose(_trade(100, 0, 120, 95, 0, 2), _bars([100] * 10), hold_bars=12)
    assert d["mode"] is None and d["why"].startswith("UNMEASURED")


def test_bar_offset_is_measured_from_the_entry_prices() -> None:
    bars = _bars([100 + i for i in range(48)])
    # Entries priced at the bar two hours LATER than their stamped time.
    trades = [{"entry_time": (T0 + timedelta(hours=h)).isoformat(), "entry_price": 102 + h}
              for h in (1, 5, 9, 20)]
    assert LL.bar_offset_hours(trades, bars) == 2


def test_modes_need_support_before_they_act() -> None:
    read = [{"mode": "RAN_PAST_TARGET", "exit_kind": "target"}] * 2 + \
           [{"mode": None, "exit_kind": "stop"}] * 8
    assert not LL.active_modes(read)["RAN_PAST_TARGET"]["active"]
    read = [{"mode": "RAN_PAST_TARGET", "exit_kind": "target"}] * 3 + \
           [{"mode": None, "exit_kind": "stop"}] * 7
    assert LL.active_modes(read)["RAN_PAST_TARGET"]["active"]


IDENT = {"clock": "XAUUSD.asia", "symbol": "XAUUSD", "family": "session_range_breakout",
         "selector": "asia", "params": {"range_start": 7, "rr": 2.0, "ttl_bars": 12,
                                        "wait_bars": 12}}


def test_variants_step_only_the_named_role_and_skip_history() -> None:
    modes = {"RAN_PAST_TARGET": {"episodes": 4, "of": 10, "share": 0.4, "active": True},
             "STOP_THEN_TARGET": {"episodes": 5, "of": 10, "share": 0.5, "active": True}}
    vs, unmapped = LL.make_variants(IDENT, modes, set(), {"rr": [1.5, 2.0, 2.5, 3.0]})
    assert [v["operator"] for v in vs] == ["loss_rr_up"]
    assert vs[0]["params"] == {**IDENT["params"], "rr": 2.5}
    # The breakout's stop is the range itself: no parameter, so the mode is named unmapped.
    assert any(u.startswith("STOP_THEN_TARGET") for u in unmapped)
    again, _ = LL.make_variants(IDENT, modes, {vs[0]["id"]}, {"rr": [1.5, 2.0, 2.5, 3.0]})
    assert again == []


def test_integer_hold_steps_stay_integers() -> None:
    modes = {"TIME_EXIT_CONTINUATION": {"episodes": 6, "of": 10, "share": 0.6, "active": True}}
    vs, _ = LL.make_variants(IDENT, modes, set(), None)
    assert vs[0]["params"]["ttl_bars"] == 15 and isinstance(vs[0]["params"]["ttl_bars"], int)


def _series(rs: list[float], start: datetime = T0) -> list[tuple[datetime, float]]:
    return [(start + timedelta(days=i), r) for i, r in enumerate(rs)]


def test_replacement_needs_forward_superiority_and_the_lineage_raises_the_bar() -> None:
    rng = np.random.default_rng(7)
    n = 60
    parent = list(rng.normal(0.05, 0.4, n))
    variant = [p + 0.35 for p in parent]          # same days, clearly better every day
    v = LL.replacement_verdict(_series(parent), _series(variant), 0.01, lineage_n=1)
    assert v["verdict"] == "REPLACE", v
    # The same evidence charged for a long lineage: alpha shrinks, the bound with it.
    hard = LL.replacement_verdict(_series(parent), _series(variant), 0.01, lineage_n=10_000)
    assert hard["alpha"] < v["alpha"] and hard["lower_bound_r"] < v["lower_bound_r"]


def test_immature_and_equal_variants_never_replace() -> None:
    p = _series([0.1, -0.1] * 5)
    assert LL.replacement_verdict(p, p, 0.01, 1)["verdict"] == "IMMATURE"
    rng = np.random.default_rng(3)
    same = list(rng.normal(0.1, 0.5, 60))
    assert LL.replacement_verdict(_series(same), _series(same), 0.01, 1)["verdict"] \
        == "HOLD_PARENT"


def test_variant_rows_before_its_own_start_are_not_its_evidence() -> None:
    parent = _series([1.0] * 80)                  # parent's strong early run...
    variant = _series([0.2] * 40, start=T0 + timedelta(days=40))
    v = LL.replacement_verdict(parent, variant, 0.01, 1)
    assert v["parent_forward_n"] == 40            # ...only its days inside the variant's window


def _roster(tmp: Path, variant_live: bool, frac: float) -> Path:
    p = tmp / "sleeves.json"
    p.write_text(json.dumps({"sleeves": [
        {"name": "PARENT", "status": "LIVE", "risk_frac": 0.01},
        {"name": "VAR.clock", "status": "LIVE" if variant_live else "STANDBY",
         "risk_frac": frac}]}), "utf-8")
    return p


def _report(window: bool = False) -> dict:
    return {"replacements": {"verdicts": [{"verdict": "REPLACE", "parent": "P.clock",
                                           "parent_sleeve": "PARENT", "parent_window": window,
                                           "variant_clock": "VAR.clock", "why": "beat it"}]}}


@pytest.fixture
def _out(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setattr(LL, "ACTIONS", tmp_path / "replacements.jsonl")
    monkeypatch.setattr(LL, "WINDOW_REQUESTS", tmp_path / "WINDOW_REPLACEMENTS.json")
    return tmp_path


def test_act_moves_capital_never_drops_it(_out: Path) -> None:
    sp = _roster(_out, variant_live=False, frac=0.0)
    res = LL.act(_report(), sleeves_path=sp)
    assert res["done"][0]["action"] == "PENDING_VARIANT_LIVE"
    assert json.loads(sp.read_text())["sleeves"][0]["status"] == "LIVE"
    sp = _roster(_out, variant_live=True, frac=0.012)
    res = LL.act(_report(), sleeves_path=sp)
    assert res["done"][0]["action"] == "RETIRED_PARENT"
    rows = {r["name"]: r for r in json.loads(sp.read_text())["sleeves"]}
    assert rows["PARENT"]["status"] == "RETIRED" and rows["PARENT"]["retired_by"] == LL.SOURCE
    assert rows["VAR.clock"]["status"] == "LIVE"
    assert "PARENT" in json.loads((_out / "RETIRED_CLOSE_QUEUE.json").read_text())["names"]


def test_a_window_parent_is_requested_never_edited(_out: Path) -> None:
    sp = _roster(_out, variant_live=True, frac=0.012)
    before = sp.read_text()
    res = LL.act(_report(window=True), sleeves_path=sp)
    assert res["window_requests"] == 1 and sp.read_text() == before
    req = json.loads((_out / "WINDOW_REPLACEMENTS.json").read_text())["requests"]
    assert req[0]["variant_clock"] == "VAR.clock"


def test_lineage_counts_every_variant_of_a_parent() -> None:
    now = T0 + timedelta(days=3)
    rows = [{"parent": "A", "at": (T0 + timedelta(days=d)).isoformat()} for d in (0, 1, 3)] + \
           [{"parent": "B", "at": T0.isoformat()}]
    assert LL.lifetime_trials("A", rows) == 3
    assert LL.minted_today("A", rows, now) == 1


def test_identity_resolves_windows_pins_and_says_why_when_not() -> None:
    reg = {"XAUUSD.asia": {"identity": {**{k: IDENT[k] for k in ("symbol", "family",
                                                                  "selector", "params")}}},
           "USDJPY.asia#rr=2.5": {"identity": {"symbol": "USDJPY",
                                               "family": "session_range_breakout",
                                               "params": {"rr": 2.5}}}}
    ident, how = LL.resolve_identity("gold_asia", None, reg)
    assert ident and ident["clock"] == "XAUUSD.asia" and how == "gateway gold window"
    ident, how = LL.resolve_identity("USDJPY_srb", None, reg,
                                     {"USDJPY_srb": "certificate x, clock USDJPY.asia#rr=2.5 "
                                                    "(alias y)"})
    assert ident and ident["symbol"] == "USDJPY" and how == "cert-book pin"
    ident, how = LL.resolve_identity("nobody", None, reg)
    assert ident is None and how.startswith("UNRESOLVED")


def test_live_set_is_the_current_books_only() -> None:
    live = LL.live_sleeves({"sleeves": [{"name": "R", "status": "RETIRED"},
                                        {"name": "L", "status": "LIVE", "risk_frac": 0.01}]},
                           {"e8": {"gold_asia": 0.006, "z": 0.0}, "ftmo": {"gold_asia": 0.009}},
                           {"enabled": True, "target_risk": 0.0075, "sleeves": ["gold_asia"]})
    assert set(live) == {"L", "gold_asia"}
    assert live["gold_asia"]["books"] == {"e8", "ftmo", "fusion"}
    assert live["gold_asia"]["frac"] == pytest.approx(0.009)


def test_dry_run_writes_nothing(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    for name in ("REPORT", "LINEAGE", "ACTIONS", "WINDOW_REQUESTS"):
        monkeypatch.setattr(LL, name, tmp_path / name)
    monkeypatch.setattr(LL, "SLEEVES", tmp_path / "none.json")
    monkeypatch.setattr(LL, "CERT_BOOK", tmp_path / "none.json")
    monkeypatch.setattr(LL, "MINLOT", tmp_path / "none.json")
    monkeypatch.setattr(LL, "FUSION_LEDGER", tmp_path / "live_ledger.jsonl")
    monkeypatch.setattr(LL, "PROP_LEDGER", tmp_path / "prop.jsonl")
    monkeypatch.setattr(LL, "_graph_state", lambda: (set(), {}, "stub"))
    rep = LL.run(dry_run=True)
    assert rep["books"]["e8"].startswith("UNMEASURED")
    assert list(tmp_path.iterdir()) == []
