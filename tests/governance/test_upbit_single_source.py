"""R0060 fence: the Upbit close-date alignment policy has exactly ONE copy.

The 2026-07-29 fix declared "both scripts now import the single source" while two more
copies (fusion_engine, signal_halflife) kept keying candle_date_time_utc -- the OPEN
stamp, ~15h look-ahead -- and one of them printed a contaminated "kimchi STRENGTHENING"
row during the very audit that had refuted kimchi at depth. A copy of an alignment
policy is a leak waiting to be re-found; this pins the count at one, permanently.
"""
from __future__ import annotations

from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
_SINGLE_SOURCE = "libs/research/upbit_data.py"


def test_candle_date_time_utc_has_exactly_one_copy() -> None:
    offenders = []
    for base in ("libs", "scripts"):
        for p in sorted((_ROOT / base).rglob("*.py")):
            try:
                text = p.read_text(encoding="utf-8", errors="ignore")
            except OSError:
                continue
            if "candle_date_time_utc" in text:
                offenders.append(p.relative_to(_ROOT).as_posix())
    assert offenders == [_SINGLE_SOURCE], (
        f"Upbit open-stamp keying must live ONLY in {_SINGLE_SOURCE}; found: {offenders}. "
        "Import upbit_daily_close_keyed() instead of re-deriving the join (R0060)."
    )
