"""Every mined mechanism is hunted intraday, in every session (principal 2026-09-16)."""
from __future__ import annotations

import sys
from pathlib import Path

_DESK = Path(__file__).resolve().parents[1]
for p in (str(_DESK), str(_DESK / "research"), str(_DESK.parent.parent)):
    if p not in sys.path:
        sys.path.insert(0, p)

from research import miner_candidate_compiler as mcc  # noqa: E402


def _cand(params: dict | None = None) -> dict:
    return {"symbol": "EURUSD", "family": "trend_ma_cross", "params": dict(params or {}),
            "source": "miner:reddit", "mechanism_status": "NAMED"}


def test_a_compiled_candidate_becomes_every_intraday_chart_in_every_session(tmp_path,
                                                                            monkeypatch):
    uni = tmp_path / "universe"
    uni.mkdir()
    for tf in ("M5", "M15", "H1"):                 # no M30 bars on disk for this symbol
        (uni / f"EURUSD_{tf}.parquet").write_bytes(b"")
    monkeypatch.setattr(mcc, "UNIVERSE", uni)
    out = mcc.expand_axes([_cand({"fast": 10})])
    charts = sorted({v["axis"]["chart"] for v in out})
    sessions = sorted({v["axis"]["session"] for v in out})
    assert charts == ["H1", "M15", "M5"] and sessions == ["all", "asia", "london", "ny"]
    assert len(out) == 3 * 4
    m5_asia = next(v for v in out if v["axis"] == {"chart": "M5", "session": "asia"})
    assert m5_asia["params"] == {"fast": 10, "timeframe": "M5", "session": "asia"}
    h1_all = next(v for v in out if v["axis"] == {"chart": "H1", "session": "all"})
    assert h1_all["params"] == {"fast": 10} and h1_all["priority"] == 1
    assert all(v["priority"] == 0 for v in out if v["axis"]["chart"] != "H1")
    # Distinct identities per variant, so the docket merge keeps them all.
    assert len({v.get("genome_id") for v in out}) == len(out)


def test_a_source_that_named_its_chart_or_session_is_left_as_written() -> None:
    fixed = [_cand({"timeframe": "M15"}), _cand({"session": "london"})]
    assert mcc.expand_axes(fixed) == fixed
