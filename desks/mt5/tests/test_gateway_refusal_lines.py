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


def _journal(path: Path, rows: list[tuple[str, str, timedelta]]) -> None:
    path.write_text("".join(json.dumps({"time": (NOW - age).isoformat(), "sleeve": sleeve,
                                        "symbol": "BTCUSD", "side": "buy", "stage": stage,
                                        "why": "refused"}) + "\n"
                            for sleeve, stage, age in rows), encoding="utf-8")


def test_a_missing_journal_is_unmeasured(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(mg, "REFUSALS", tmp_path / "absent.jsonl")
    doc = mg.gateway_refusal_lines(NOW)
    assert doc["verdict"] == mg.UNMEASURED and doc["lines"] == []


def test_each_stage_is_counted_and_priced_by_the_refused_sleeve(tmp_path, monkeypatch) -> None:
    journal, sleeves = tmp_path / "refused.jsonl", tmp_path / "sleeves.json"
    _journal(journal, [("paid", "panel_store_lag", timedelta(hours=1)),
                       ("paid", "panel_store_lag", timedelta(hours=2)),
                       ("young", "not_live_reproducible", timedelta(hours=1)),
                       ("paid", "short_history", timedelta(days=9))])     # outside the window
    sleeves.write_text(json.dumps([
        {"name": "paid", "shadow_exp": 0.2, "risk_frac": 0.005, "shadow_n": 40},
        {"name": "young", "shadow_exp": 0.5, "risk_frac": 0.005, "shadow_n": 3}]), "utf-8")
    monkeypatch.setattr(mg, "REFUSALS", journal)
    monkeypatch.setattr(mg, "SLEEVES", sleeves)
    doc = mg.gateway_refusal_lines(NOW)
    by = {x["stage"]: x for x in doc["lines"]}
    assert set(by) == {"panel_store_lag", "not_live_reproducible"}
    assert by["panel_store_lag"]["n"] == 2 and by["panel_store_lag"]["n_priced"] == 2
    assert abs(by["panel_store_lag"]["logw_forgone"] - 2 * 0.2 * 0.005) < 1e-12
    assert by["panel_store_lag"]["verdict"] == mg.COSTS
    assert by["not_live_reproducible"]["verdict"] == mg.UNMEASURED      # too few forward trades
    assert doc["verdict"] == mg.COSTS


def test_the_bill_is_published_beside_the_rails() -> None:
    src = (_DESK / "research" / "missed_growth.py").read_text("utf-8")
    assert '"gateway_refusals": gateway_refusal_lines()' in src
