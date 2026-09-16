"""E8 halves a mechanism the MT5 lane has faded or measured doing bad (2026-09-16).

The E8 book is built from certificates alone; on 2026-09-16 its entire order flow was the
`discovered` EURCHF/AUDCAD/AUDNZD sleeves that the MT5 lane had measured 0-for-9 live. The
twin fade reads MT5's roster flags and live ledger for the same (symbol, family) and is
two-sided: it returns to 1.0 when the twins are unfaded and the record turns.
"""
from __future__ import annotations

import json
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

_DESK = Path(__file__).resolve().parents[1]
if str(_DESK) not in sys.path:
    sys.path.insert(0, str(_DESK))

from prop import e8_executor as ex  # noqa: E402


def _files(tmp_path: Path, monkeypatch, *, faded: bool, rs: list[float]) -> None:
    roster = {"sleeves": [{"name": "eurchf_discovered_asia_p_6c7943b997558157", "status": "LIVE",
                           **({"decay_faded": "2026-09-16T08:00:00+00:00"} if faded else {})}]}
    (tmp_path / "sleeves.json").write_text(json.dumps(roster), "utf-8")
    t0 = datetime.now(tz=UTC) - timedelta(days=1)
    with (tmp_path / "ledger.jsonl").open("w", encoding="utf-8") as fh:
        for i, r in enumerate(rs):
            fh.write(json.dumps({"time": (t0 + timedelta(minutes=i)).isoformat(),
                                 "sleeve": "eurchf_discovered_asia_p_6c", "r_multiple": r}) + "\n")
    monkeypatch.setattr(ex, "MT5_SLEEVES", tmp_path / "sleeves.json")
    monkeypatch.setattr(ex, "MT5_LEDGER", tmp_path / "ledger.jsonl")


def test_a_faded_twin_halves_the_e8_lot(tmp_path, monkeypatch) -> None:
    _files(tmp_path, monkeypatch, faded=True, rs=[0.4, -0.5])
    m, why = ex.twin_fade("EURCHF", "discovered")
    assert m == 0.5 and "faded by the decay monitor" in why


def test_a_pooled_zero_for_five_record_halves_it_too(tmp_path, monkeypatch) -> None:
    _files(tmp_path, monkeypatch, faded=False, rs=[-0.3, -0.5, -0.2, -0.4, -0.6])
    m, why = ex.twin_fade("EURCHF", "discovered")
    assert m == 0.5 and "0-for-5" in why


def test_a_healthy_twin_is_full_size_and_other_symbols_are_untouched(tmp_path, monkeypatch) -> None:
    _files(tmp_path, monkeypatch, faded=False, rs=[0.4, -0.2, 0.6, 0.1, -0.3, 0.5])
    assert ex.twin_fade("EURCHF", "discovered")[0] == 1.0
    assert ex.twin_fade("AUDCAD", "discovered")[0] == 1.0
    assert ex.twin_fade("EURCHF", "session_range_breakout")[0] == 1.0


def test_unreadable_files_read_as_full_size(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(ex, "MT5_SLEEVES", tmp_path / "missing.json")
    monkeypatch.setattr(ex, "MT5_LEDGER", tmp_path / "missing.jsonl")
    m, why = ex.twin_fade("EURCHF", "discovered")
    assert m == 1.0 and "n=0" in why
