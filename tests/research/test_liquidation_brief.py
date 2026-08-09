"""R0245 -- the liquidation feed both LLM sleeves asked for and neither has ever had.

The defect was a SPELLING: two readers named ``data/liquidations.jsonl`` inside a swallow-on-
missing block while the producer wrote ``data/liquidations.parquet``. Nothing crashed, nothing
alerted, and both briefs recorded "ABSENT on this host" -- the same string a genuinely dead
collector would produce. So the regression test that matters is not "does the summary work"; it
is "can the two spellings drift apart again".
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from libs.research import liquidation_brief as lb

NOW = pd.Timestamp("2026-08-05T12:00:00Z")
_ROOT = Path(__file__).resolve().parents[2]


def _tape(root: Path, rows: list[dict]) -> None:
    (root / "data").mkdir(parents=True, exist_ok=True)
    pd.DataFrame(rows, columns=["ts", "symbol", "side", "qty", "price", "notional"]).to_parquet(
        root / lb.REL)


def _ev(minutes_ago: float, symbol: str = "BTCUSDT", side: str = "Sell",
        notional: float = 1000.0) -> dict:
    return {"ts": NOW - pd.Timedelta(minutes=minutes_ago), "symbol": symbol, "side": side,
            "qty": 0.01, "price": 65000.0, "notional": notional}


class TestTheThreeWaysThereIsNoNumber:
    """ABSENT, UNREADABLE and EMPTY demand different responses, so they stay different states."""

    def test_absent_names_the_path_nothing_wrote(self, tmp_path) -> None:
        w = lb.summarize(tmp_path, now=NOW)
        assert w.status == "ABSENT"
        assert lb.REL in w.detail

    def test_unreadable_is_not_absent(self, tmp_path) -> None:
        """A producer that ran and wrote garbage is a different organ to debug than one that has
        never run (L1.55). Collapsing them sends the desk to the wrong file."""
        (tmp_path / "data").mkdir()
        (tmp_path / lb.REL).write_text("this is not parquet", "utf-8")
        w = lb.summarize(tmp_path, now=NOW)
        assert w.status == "UNREADABLE"
        assert "ABSENT" not in w.detail

    def test_a_connected_listener_archiving_nothing_says_so(self, tmp_path) -> None:
        """The desk has already lost 14 days to a listener holding a fresh heartbeat while
        archiving zero events. An empty tape must not read as a quiet market."""
        _tape(tmp_path, [])
        w = lb.summarize(tmp_path, now=NOW)
        assert w.status == "EMPTY"
        assert "ZERO events" in w.detail


class TestTheSummaryIsWorthReading:
    def test_the_window_is_priced_against_its_own_baseline(self, tmp_path) -> None:
        """A dollar total with no baseline cannot say CASCADE, which is the only thing a sleeve
        would act on. 10x the hourly median must be visible as 10x."""
        rows = [_ev(m, notional=100.0) for m in range(61, 61 + 23 * 60, 60)]   # ~100/h baseline
        rows += [_ev(m, notional=250.0) for m in range(0, 60, 15)]             # 1000 in the hour
        _tape(tmp_path, rows)
        w = lb.summarize(tmp_path, now=NOW, window_min=60, baseline_h=24)
        assert w.status == "MEASURED"
        assert w.n_events == 4
        assert "10.0x" in w.lines[0], w.lines[0]

    def test_a_quiet_window_reports_the_age_of_the_tape(self, tmp_path) -> None:
        """"No liquidations this hour" and "the collector died six hours ago" are opposite facts
        and both produce an empty window."""
        _tape(tmp_path, [_ev(360.0)])
        w = lb.summarize(tmp_path, now=NOW, window_min=60)
        assert w.status == "MEASURED" and w.n_events == 0
        assert "6.0h old" in w.detail and "CHECK THE LISTENER" in w.detail

    def test_the_side_field_is_never_translated_into_a_direction(self, tmp_path) -> None:
        """screen_liquidation_reversion records that Bybit carried order-side in one stream
        generation and position-side in another, and that they are exact opposites. Handing a
        sleeve "longs liquidated" from an uncalibrated field is a coin-flip stated as a fact."""
        _tape(tmp_path, [_ev(5.0, side="Sell")])
        w = lb.summarize(tmp_path, now=NOW)
        blob = " ".join(w.lines)
        assert "venue-side=Sell" in blob
        assert "UNCALIBRATED" in blob
        for invented in ("longs liquidated", "shorts liquidated", "long liquidation"):
            assert invented not in blob.lower()

    def test_a_baseline_built_from_the_window_itself_is_refused(self, tmp_path) -> None:
        """The self-reference trap, and this test is what found it. A tape whose only events ARE
        the current window used to yield "1.0x the hourly median" -- a comparison against itself,
        reading NORMAL on a tape with no history whatsoever (L1.51: a ratio and its own reference
        may never share a source)."""
        _tape(tmp_path, [_ev(5.0, notional=500.0)])
        w = lb.summarize(tmp_path, now=NOW, baseline_h=24)
        assert "no baseline yet" in w.lines[0], w.lines[0]
        assert "1.0x" not in w.lines[0]

    def test_a_two_hour_tape_is_not_a_baseline(self, tmp_path) -> None:
        rows = [_ev(m, notional=100.0) for m in (75.0, 135.0)] + [_ev(5.0, notional=900.0)]
        _tape(tmp_path, rows)
        w = lb.summarize(tmp_path, now=NOW, baseline_h=24)
        assert "no baseline yet" in w.lines[0] and "2h of prior tape" in w.lines[0]


class TestTheSpellingCannotDriftAgain:
    """The actual R0245 defect, fenced. Everything above tests a module that did not exist when
    the bug did; only this class would have caught the bug itself."""

    def test_the_module_names_the_path_the_producer_writes(self) -> None:
        producer = (_ROOT / "scripts/liquidation_listener.py").read_text("utf-8")
        assert f'_OUT = Path("{lb.REL}")' in producer, (
            f"the listener no longer writes {lb.REL}; this module and its two readers are now "
            f"pointed at a path with no producer, which is the exact defect R0245 recorded")

    @pytest.mark.parametrize("rel", ["scripts/run_llm_trader.py",
                                     "scripts/run_conviction_trader.py"])
    def test_neither_sleeve_reads_the_path_that_never_existed(self, rel: str) -> None:
        src = (_ROOT / rel).read_text("utf-8")
        offending = [ln for ln in src.splitlines()
                     if "liquidations.jsonl" in ln and not ln.lstrip().startswith("#")]
        assert not offending, (
            f"{rel} reads data/liquidations.jsonl again -- a path nothing has ever written, "
            f"inside a block that swallows the failure: {offending}")
        assert "liquidation_brief" in src, f"{rel} no longer wires the liquidation feed at all"
