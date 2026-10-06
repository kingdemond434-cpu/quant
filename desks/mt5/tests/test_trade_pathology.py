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
