"""Every gateway refusal is billed beside the rails (audit of #403 at 5341bfe53).

The state-gate refusals (`not_live_reproducible`, `short_history`, `panel_store_lag`) are
journalled by the gateway, and `missed_growth.gateway_refusal_lines` prices each stage at the
refused sleeve's forward expectancy x risk fraction. An unpriced stage reads UNMEASURED with its
count, and a missing journal reads UNMEASURED, never a clean zero.
"""
from __future__ import annotations

import json
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

_DESK = Path(__file__).resolve().parents[1]
for _p in (str(_DESK), str(_DESK / "research"), str(_DESK.parent.parent)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import missed_growth as mg  # noqa: E402

NOW = datetime(2026, 10, 20, 12, tzinfo=UTC)


def _journal(path: Path, rows: list[tuple[str, str, timedelta, str, bool | None]]) -> None:
    path.write_text("".join(json.dumps({"time": (NOW - age).isoformat(), "sleeve": sleeve,
                                        "symbol": "BTCUSD", "side": "buy", "stage": stage,
                                        "why": "refused", "bar": bar,
                                        "signal_due": due}) + "\n"
                            for sleeve, stage, age, bar, due in rows), encoding="utf-8")


def test_a_missing_journal_is_unmeasured(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(mg, "REFUSALS", tmp_path / "absent.jsonl")
    doc = mg.gateway_refusal_lines(NOW)
    assert doc["verdict"] == mg.UNMEASURED and doc["lines"] == []


def test_each_stage_is_counted_once_per_bar_and_priced_only_where_due(tmp_path,
                                                                     monkeypatch) -> None:
    journal, sleeves = tmp_path / "refused.jsonl", tmp_path / "sleeves.json"
    h = timedelta(hours=1)
    _journal(journal, [
        # one panel-lag bar journalled on three passes: ONE refused bar, no signal known
        ("paid", "panel_store_lag", h, "b1", None),
        ("paid", "panel_store_lag", h, "b1", None),
        ("paid", "panel_store_lag", h, "b1", None),
        ("paid", "panel_store_lag", 2 * h, "b2", None),
        # a refusal that stopped a real signal, twice on the same bar: priced once
        ("paid", "stale_signal", h, "b1", True),
        ("paid", "stale_signal", h, "b1", True),
        ("young", "stale_signal", h, "b1", True),                 # too few forward trades
        ("paid", "short_history", timedelta(days=9), "b0", None)])  # outside the window
    sleeves.write_text(json.dumps([
        {"name": "paid", "shadow_exp": 0.2, "risk_frac": 0.005, "shadow_n": 40},
        {"name": "young", "shadow_exp": 0.5, "risk_frac": 0.005, "shadow_n": 3}]), "utf-8")
    monkeypatch.setattr(mg, "REFUSALS", journal)
    monkeypatch.setattr(mg, "SLEEVES", sleeves)
    doc = mg.gateway_refusal_lines(NOW)
    by = {x["stage"]: x for x in doc["lines"]}
    assert set(by) == {"panel_store_lag", "stale_signal"}
    lag = by["panel_store_lag"]
    assert (lag["n"], lag["n_lines"], lag["n_priced"]) == (2, 4, 0)
    assert lag["verdict"] == mg.UNMEASURED and lag["logw_forgone"] == 0.0
    stale = by["stale_signal"]
    assert (stale["n"], stale["n_lines"], stale["n_priced"]) == (2, 3, 1)
    assert abs(stale["logw_forgone"] - 0.2 * 0.005) < 1e-12
    assert stale["verdict"] == mg.COSTS and doc["verdict"] == mg.COSTS


def test_the_gateway_journals_each_bar_once_and_says_whether_a_signal_was_due() -> None:
    src = (_DESK / "mt5desk" / "gateway.py").read_text("utf-8")
    assert "_REFUSED_BARS" in src and '"signal_due": signal_due' in src
    for stage in ("not_live_reproducible", "short_history", "panel_store_lag"):
        i = src.index(f'"{stage}", ')
        call = src[i:src.index(")", src.index("bar=", i))]
        assert "bar=" in call and "signal_due=True" not in call, stage


def test_the_bill_is_published_beside_the_rails() -> None:
    src = (_DESK / "research" / "missed_growth.py").read_text("utf-8")
    assert '"gateway_refusals": gateway_refusal_lines()' in src
