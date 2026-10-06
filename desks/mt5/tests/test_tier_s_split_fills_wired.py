"""S23: `split_fills` is consumed by the SCHEDULED path (verifier gap C, 2026-09-30).

Until now only tests called it. The hourly `execution_science` leg now joins the fill corpus
(requested price, entry fill) to the live ledger's closing deal and splits every real fill into
signal alpha and execution drag, in `live_fill_calibration` of reports/EXECUTION_SCIENCE.json.
"""
from __future__ import annotations

import inspect
import json
import sys
from pathlib import Path

import pytest

_DESK = Path(__file__).resolve().parents[1]
_ROOT = _DESK.parent.parent
for _p in (str(_DESK), str(_DESK / "research"), str(_ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import execution_science as xs  # noqa: E402


def _write(p: Path, rows: list[dict]) -> Path:
    p.write_text("".join(json.dumps(r) + "\n" for r in rows), "utf-8")
    return p


def _fixtures(tmp_path: Path, n: int = 3) -> tuple[Path, Path]:
    corpus, ledger = [], []
    for i in range(n):
        # a buy asked at 1.1000, filled 1.1002 (2 pips worse), stop 1.0980, exited 1.1040
        corpus.append({"status": "FILLED", "sleeve": "eurusd_orb", "symbol": "EURUSD",
                       "direction": 1, "requested_price": 1.1000, "fill_price": 1.1002,
                       "deal": 900 + i, "ticket": 500 + i,
                       "join_keys": {"position_id": str(500 + i)}})
        ledger.append({"deal": 900 + i, "position_id": 500 + i, "entry_order": 500 + i,
                       "sleeve": "eurusd_orb", "symbol": "EURUSD", "side": 1,
                       "fill_price": 1.1040, "entry_price": 1.1002, "sl": 1.0982,
                       "commission": -1.0, "swap": 0.0, "volume": 0.1,
                       "contract_size": 100000.0})
    corpus.append({"status": "UNFILLED", "requested_price": 1.1, "fill_price": None})
    corpus.append({"status": "FILLED", "requested_price": 1.1, "fill_price": 1.1,
                   "deal": 12345, "direction": -1})                       # no closing deal
    return _write(tmp_path / "corpus.jsonl", corpus), _write(tmp_path / "ledger.jsonl", ledger)


def test_live_fills_are_split_exactly_on_the_scheduled_path(tmp_path: Path) -> None:
    corpus, ledger = _fixtures(tmp_path)
    cal = xs._live_fill_calibration(corpus, ledger)
    assert cal["join"] == {"corpus_filled": 4, "joined": 3, "unjoined": 1, "no_request": 0}
    split = cal["split"]
    assert split["status"] == "MEASURED" and split["n"] == 3
    sd = 1.1002 - 1.0982
    alpha = (1.1040 - 1.1000) / sd
    drag = (1.1002 - 1.1000) / sd + (1.0 / (0.1 * 100000.0)) / sd
    assert split["mean_signal_alpha_r"] == pytest.approx(alpha, abs=1e-6)
    assert split["mean_execution_drag_r"] == pytest.approx(drag, abs=1e-6)
    assert split["mean_net_r"] == pytest.approx(alpha - drag, abs=1e-6)
    assert cal["by_sleeve"]["eurusd_orb"]["n"] == 3
    assert cal["status"] == "UNMEASURED", "3 fills split, but 3 is not a calibration"


def test_enough_fills_read_as_measured(tmp_path: Path) -> None:
    corpus, ledger = _fixtures(tmp_path, n=xs.MIN_CALIBRATION_FILLS)
    assert xs._live_fill_calibration(corpus, ledger)["status"] == "MEASURED"


def test_the_hourly_leg_reaches_split_fills() -> None:
    """The leg `execution_science` runs `execution_science.py --apply`, whose report -- OK or
    UNMEASURED alike -- carries `_live_fill_calibration()`, which calls `split_fills`."""
    import hourly_cycle
    assert "research/execution_science.py" in inspect.getsource(hourly_cycle.execution_science)
    assert "split_fills(" in inspect.getsource(xs._live_fill_calibration)
    assert "_live_fill_calibration()" in inspect.getsource(xs.summarise)
    assert "_live_fill_calibration()" in inspect.getsource(xs._unmeasured)
