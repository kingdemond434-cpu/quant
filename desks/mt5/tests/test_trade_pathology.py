"""Trade pathology classifies closed trades from the ledger joined to their intents; a class no
trade could have tripped reads UNMEASURED, never zero."""
from __future__ import annotations

import json
import sys
from pathlib import Path

_DESK = Path(__file__).resolve().parents[1]
_ROOT = _DESK.parent.parent
for p in (str(_DESK), str(_ROOT)):
    if p not in sys.path:
        sys.path.insert(0, p)

from research import trade_pathology as tp  # noqa: E402


def _jsonl(p: Path, rows: list[dict]) -> Path:
    p.write_text("".join(json.dumps(r) + "\n" for r in rows), "utf-8")
    return p


def test_empty_ledger_is_unmeasured(tmp_path: Path) -> None:
    doc = tp.build(ledger=tmp_path / "none.jsonl", intents_p=tmp_path / "i.jsonl",
                   corpus=tmp_path / "c.jsonl", universe=tmp_path / "u.json")
    assert doc["status"] == tp.UNMEASURED
    assert all(v["status"] == tp.UNMEASURED for v in doc["classes"].values())


def test_direction_from_stop_then_side() -> None:
    assert tp.direction({"entry_price": 100, "sl": 99}) == 1
    assert tp.direction({"entry_price": 100, "sl": 101}) == -1


def test_classes_on_a_joined_book(tmp_path: Path) -> None:
    deals = [
        # long, stopped 1R past the stop within one bar, entry 0.5R off the signal
        {"deal": 1, "symbol": "XAUUSD", "sleeve": "g", "entry_order": 11, "entry_price": 100.5,
         "sl": 99.5, "fill_price": 98.5, "time": "2026-09-29T10:30:00+00:00",
         "r_multiple": -2.0},
        # short, clean target, no intent
        {"deal": 2, "symbol": "XAUUSD", "sleeve": "g", "entry_price": 100.0, "sl": 101.0,
         "fill_price": 98.0, "time": "2026-09-29T12:00:00+00:00", "r_multiple": 2.0},
    ]
    intents = [{"ticket": 11, "time": "2026-09-29T10:00:00+00:00", "intended": 100.0,
                "spread_at_decision": 0.5, "point": 0.01}]
    uni = {"XAUUSD": {"point": 0.01, "median_spread_pts": 10}}
    (tmp_path / "u.json").write_text(json.dumps(uni), "utf-8")
    doc = tp.build(ledger=_jsonl(tmp_path / "l.jsonl", deals),
                   intents_p=_jsonl(tmp_path / "i.jsonl", intents),
                   corpus=_jsonl(tmp_path / "c.jsonl", [{"status": "REJECTED", "retcode": 10006,
                                                         "rejected": True}]),
                   universe=tmp_path / "u.json")
    assert doc["status"] == tp.MEASURED and doc["n_trades"] == 2 and doc["n_joined"] == 1
    c = doc["classes"]
    assert c["STOP_SLIPPAGE"]["count"] == 1
    assert c["EARLY_STOPOUT"]["count"] == 1
    assert c["FAR_FROM_SIGNAL"]["count"] == 1
    assert c["SPREAD_SPIKE"]["count"] == 1          # 50 pts against a 10-pt median
    assert c["SLIPPAGE_OUTLIER"]["status"] == tp.UNMEASURED   # under 5 slips: no MAD bar
    assert doc["orders"]["reject_retcodes"] == {"10006": 1}


def test_main_writes_artifact(tmp_path: Path) -> None:
    out = tmp_path / "TRADE_PATHOLOGY.json"
    assert tp.main(["--once", "--out", str(out)]) == 0
    assert json.loads(out.read_text("utf-8"))["schema"] == tp.SCHEMA


def _book(n_deals: int, n_joined: int) -> tuple[list[dict], list[dict]]:
    deals, intents = [], []
    for k in range(n_deals):
        d = {"deal": k, "symbol": "XAUUSD", "sleeve": "g", "entry_price": 100.0, "sl": 99.0,
             "fill_price": 101.0, "time": "2026-09-29T12:00:00+00:00", "r_multiple": 1.0}
        if k < n_joined:
            d["entry_order"] = 1000 + k
            intents.append({"ticket": 1000 + k, "time": "2026-09-29T10:00:00+00:00",
                            "intended": 100.0, "spread_at_decision": 0.1, "point": 0.01})
        deals.append(d)
    return deals, intents


def _run_book(tmp_path: Path, n_deals: int, n_joined: int) -> dict:
    deals, intents = _book(n_deals, n_joined)
    (tmp_path / "u.json").write_text(json.dumps({"XAUUSD": {"point": 0.01,
                                                            "median_spread_pts": 10}}), "utf-8")
    return tp.build(ledger=_jsonl(tmp_path / "l.jsonl", deals),
                    intents_p=_jsonl(tmp_path / "i.jsonl", intents),
                    corpus=tmp_path / "c.jsonl", universe=tmp_path / "u.json")


def test_a_two_percent_join_is_partial_never_measured(tmp_path: Path) -> None:
    """LIVE 2026-10-06: 3 of 151 deals joined and the reading said MEASURED."""
    doc = _run_book(tmp_path, 151, 3)
    assert doc["status"] == tp.PARTIAL
    assert doc["join_rate"] == round(3 / 151, 6) and doc["min_join_coverage"] == 0.5
    assert "below" in doc["why"]
    assert doc["classes"]["SPREAD_SPIKE"]["status"] == tp.PARTIAL
    assert doc["classes"]["STOP_SLIPPAGE"]["status"] == tp.MEASURED   # needs no join


def test_no_join_at_all_is_unmeasured_and_full_join_measured(tmp_path: Path) -> None:
    assert _run_book(tmp_path, 10, 0)["status"] == tp.UNMEASURED
    doc = _run_book(tmp_path, 10, 10)
    assert doc["status"] == tp.MEASURED and doc["join_rate"] == 1.0
