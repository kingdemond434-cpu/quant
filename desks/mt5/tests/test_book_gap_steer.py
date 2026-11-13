"""The compiler converts first what the LIVE book holds least of (book_gap_steer, 2026-11-13)."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

DESK = Path(__file__).resolve().parents[1]
for _p in (str(DESK), str(DESK.parent.parent)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from research import book_gap_steer as bg  # noqa: E402

# the gap tests label NOK pairs plain forex so the exotic quota does not move them;
# the quota tests below use the broker's real label
CLASSES = {"USDNOK": "forex", "EURNOK": "forex", "USDCHF": "forex",
           "EURJPY": "forex", "US500": "indices", "XAUUSD": "commodities"}


def _class_of(s: str) -> str:
    return CLASSES.get(s, "")


def _book(tmp_path: Path, rows: list[dict]) -> Path:
    p = tmp_path / "sleeves.json"
    p.write_text(json.dumps({"sleeves": rows}), "utf-8")
    return p


def _cand(sym: str, net: float | None, session: str = "london") -> dict:
    return {"symbol": sym, "family": "f", "params": {"session": session}, "net_edge": net}


NOK_BOOK = [{"symbol": "USDNOK", "status": "LIVE", "session": "london"},
            {"symbol": "EURNOK", "status": "LIVE", "session": "london"},
            {"symbol": "USDCHF", "status": "LIVE", "session": "ny"},
            {"symbol": "XAUUSD", "status": "RETIRED", "session": "asia"}]


def test_gaps_rise_and_the_crowded_bucket_keeps_its_rank(tmp_path: Path) -> None:
    ordered = [_cand("USDNOK", 0.9), _cand("EURNOK", 0.8), _cand("USDCHF", 0.7),
               _cand("US500", 0.6), _cand("XAUUSD", 0.5, "asia"), _cand("EURJPY", 0.4)]
    out, rep = bg.apply(ordered, sleeves=_book(tmp_path, NOK_BOOK), class_of=_class_of)
    syms = [c["symbol"] for c in out]
    assert syms.index("XAUUSD") < syms.index("USDCHF")      # gold in Asia: rank 5 -> ahead of 3
    assert syms.index("US500") < syms.index("USDCHF")
    assert syms[-1] != "XAUUSD" and sorted(syms) == sorted(c["symbol"] for c in ordered)
    assert rep["status"] == "APPLIED" and rep["live_sleeves"] == 3      # RETIRED is not held
    assert rep["candidates_by_ask"] == {"gold": 1, "index": 1, "usd_jpy_eur_cross": 1,
                                        "asia_entry": 1}


def test_unpriced_never_jumps_a_priced_candidate(tmp_path: Path) -> None:
    ordered = [_cand("USDNOK", 0.9), _cand("XAUUSD", None, "asia")]
    out, _ = bg.apply(ordered, sleeves=_book(tmp_path, NOK_BOOK), class_of=_class_of)
    assert [c["symbol"] for c in out] == ["USDNOK", "XAUUSD"]


def test_no_readable_book_leaves_the_order_and_says_unmeasured(tmp_path: Path) -> None:
    ordered = [_cand("USDNOK", 0.9), _cand("XAUUSD", 0.1, "asia")]
    out, rep = bg.apply(ordered, sleeves=tmp_path / "absent.json", class_of=_class_of)
    assert out == ordered and rep["status"].startswith("UNMEASURED")


def test_revert_switch(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("QUANT_BOOK_GAP_STEER", "0")
    ordered = [_cand("USDNOK", 0.9), _cand("XAUUSD", 0.1, "asia")]
    out, rep = bg.apply(ordered, sleeves=_book(tmp_path, NOK_BOOK), class_of=_class_of)
    assert out == ordered and rep["status"].startswith("OFF")


def test_the_compiler_carries_the_steer() -> None:
    src = (DESK / "research" / "miner_candidate_compiler.py").read_text("utf-8")
    assert "book_gap_steer as _bg" in src and '"book_gap_steer": gap_note' in src


EXOTIC = {"USDNOK": "forex exotics", "USDZAR": "forex exotics", "EURUSD": "forex"}


def _exo_class(s: str) -> str:
    return EXOTIC.get(s, "")


def test_exotics_never_exceed_ten_percent_of_any_leading_slice(tmp_path: Path) -> None:
    ordered = ([_cand("USDNOK", 1.0 - i / 100) for i in range(10)]
               + [_cand("EURUSD", 0.5 - i / 1000) for i in range(40)])
    out, rep = bg.apply(ordered, sleeves=tmp_path / "absent.json", class_of=_exo_class,
                        top_n=20)
    exo = 0
    for n, c in enumerate(out, start=1):
        exo += c["symbol"] == "USDNOK"
        if n <= 40:                                    # while non-exotics remain to place
            assert exo <= 0.10 * n, (n, exo)
    assert len(out) == 50                              # nothing dropped
    assert rep["exotic_quota"]["deferred"] == 6        # 4 fit in 40 non-exotic slots
    assert all(c.get("exotic_quota_deferred") for c in out[-6:])
    assert rep["exotic_quota"]["first_20"]["exotic"] == 2
    assert rep["exotic_quota"]["before_quota_first_20"]["exotic"] == 10


def test_the_quota_holds_with_the_steer_switched_off(tmp_path: Path,
                                                     monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("QUANT_BOOK_GAP_STEER", "0")
    ordered = [_cand("USDZAR", 0.9)] + [_cand("EURUSD", 0.5) for _ in range(9)]
    out, rep = bg.apply(ordered, sleeves=tmp_path / "absent.json", class_of=_exo_class)
    assert out[0]["symbol"] == "EURUSD" and out[-1]["symbol"] == "USDZAR"
    assert rep["status"].startswith("OFF") and rep["exotic_quota"]["all"]["exotic_share"] == 0.1
