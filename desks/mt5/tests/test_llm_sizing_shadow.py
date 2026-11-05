"""LLM sizing shadow: forward-only deliberation, sanitized packets, E[log W] verdicts."""
from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta

import pandas as pd
import pytest

from research import llm_sizing_shadow as L

NOW = datetime(2026, 11, 3, 6, 0, tzinfo=UTC)


def _intent(t: datetime, **kw) -> dict:
    row = {"sleeve": "gold_asia", "symbol": "XAUUSD", "side": "sell_stop", "lot": 0.01,
           "intended": 3990.0, "sl": 4026.0, "tp": 3918.0, "ticket": 243283176,
           "time": t.isoformat(), "intent_id": "abc", "account_key": "sha256:secretish",
           "server": "FusionMarkets-Live"}
    row.update(kw)
    return row


@pytest.fixture(autouse=True)
def _paths(tmp_path, monkeypatch):
    monkeypatch.setattr(L, "OUT_DIR", tmp_path / "llm_sizing")
    monkeypatch.setattr(L, "TRANSCRIPTS", tmp_path / "llm_sizing" / "transcripts.jsonl")
    monkeypatch.setattr(L, "REPORT", tmp_path / "LLM_SIZING_SHADOW.json")
    monkeypatch.setattr(L, "INTENTS", tmp_path / "order_intents.jsonl")
    monkeypatch.setattr(L, "FUSION_LEDGER", tmp_path / "live_ledger.jsonl")
    monkeypatch.setattr(L, "PROP_LEDGER", tmp_path / "live_ledger_prop.jsonl")
    return tmp_path


def _bars(end: datetime, n: int = 80) -> pd.DataFrame:
    idx = pd.date_range(end=end.replace(tzinfo=None), periods=n, freq="h")
    px = [4000.0 + i for i in range(n)]
    return pd.DataFrame({"open": px, "high": [p + 2 for p in px], "low": [p - 2 for p in px],
                         "close": [p + 1 for p in px]}, index=idx)


def test_packet_is_sanitized_and_uses_only_closed_bars():
    t = NOW - timedelta(minutes=30)
    pk = L.packet(_intent(t), _bars(NOW + timedelta(hours=5)))
    text = json.dumps(pk)
    for leak in ("account", "ticket", "server", "lot", "2026", "intent_id"):
        assert leak not in text
    assert pk["direction"] == "short" and pk["target_r"] == 2.0
    # The bar opening at 05:00 closes at 06:00, after the 05:30 send: excluded.
    bars = _bars(NOW + timedelta(hours=5))
    closed = bars[(bars.index + timedelta(hours=1)) <= t.replace(tzinfo=None)]
    assert len(pk["recent_h1_bars_pct_of_last_close"]) == L.CONTEXT_BARS
    assert pk["recent_h1_bars_pct_of_last_close"][-1][3] == 0.0
    assert closed.index[-1] == pd.Timestamp("2026-11-03 04:00")


def test_multipliers_shrink_only_never_adds_symmetric_is_capped():
    assert L.multipliers(1.8) == {"baseline": 1.0, "shrink_only": 1.0,
                                  "symmetric": L.SYMMETRIC_MAX}
    assert L.multipliers(0.4) == {"baseline": 1.0, "shrink_only": 0.4, "symmetric": 0.4}


def test_parse_clamps_and_rejects_garbage():
    got = L._parse('ok {"size_multiplier": 9, "stance": "add", "arguments": '
                   '[{"claim": "trend", "direction": "for"}]}')
    assert got["size_multiplier"] == 2.0 and got["stance"] == "add"
    assert L._parse("no json") is None
    assert L._parse('{"size_multiplier": "big"}') is None


def test_pending_only_young_placed_gold_intents_once_per_signal():
    rows = [_intent(NOW - timedelta(hours=1)),
            _intent(NOW - timedelta(minutes=50), intent_id="ftmo-copy"),
            _intent(NOW - timedelta(hours=9)),
            _intent(NOW - timedelta(hours=1), sleeve="usdnok_carry"),
            _intent(NOW - timedelta(hours=1), sleeve="gold_afternoon", status="SKIPPED")]
    got = L.pending(NOW, rows, done=set())
    assert [r["intent_id"] for r in got] == ["abc"]
    assert L.pending(NOW, rows, done={"gold_asia|2026-11-03"}) == []


def _panel(mults):
    return [(f"m{i}", (lambda p, m=m: (json.dumps({"size_multiplier": m, "stance": "cut" if m < 1
                                                   else "add", "arguments": []}), None)))
            for i, m in enumerate(mults)]


def test_run_writes_transcript_keyed_to_trade_and_never_raises():
    L.INTENTS.write_text(json.dumps(_intent(NOW - timedelta(hours=1))) + "\n")
    doc = L.run(NOW, panel=_panel([0.5, 1.2, 1.4]), bars_loader=lambda s: None)
    assert doc["deliberated_this_pass"] == 1
    row = json.loads(L.TRANSCRIPTS.read_text().splitlines()[0])
    assert row["key"] == "gold_asia|2026-11-03" and row["median"] == 1.2
    assert row["multipliers"] == {"baseline": 1.0, "shrink_only": 1.0, "symmetric": 1.2}
    assert len(row["seats"]) == 3
    # Second pass: already deliberated.
    assert L.run(NOW, panel=_panel([1.0]), bars_loader=lambda s: None)["deliberated_this_pass"] == 0
    # A failing panel never raises.
    L.TRANSCRIPTS.unlink()
    doc = L.run(NOW, panel=[("x", lambda p: (_ for _ in ()).throw(RuntimeError("down")))],
                bars_loader=lambda s: None)
    assert doc["error"]


def _transcript(day: int, mult: float, at: datetime) -> dict:
    return {"key": f"gold_asia|2026-10-{day:02d}", "deliberated_at": at.isoformat(),
            "multipliers": L.multipliers(mult),
            "seats": [{"model": "m", "stance": "add" if mult > 1 else "cut",
                       "size_multiplier": mult,
                       "arguments": [{"claim": "x", "direction": "for"}]}]}


def test_score_ignores_deliberations_written_after_close_and_drops_timid_veto():
    trs, outs = [], {}
    for d in range(1, 32):
        t = datetime(2026, 10, d, 7, tzinfo=UTC)
        r = 2.0 if d % 2 else -1.0
        # A veto that always cuts winners: shrink-only loses growth.
        trs.append(_transcript(d, 0.5 if r > 0 else 1.0, t))
        outs[f"gold_asia|2026-10-{d:02d}"] = {"r": r, "exit_time": t + timedelta(hours=5)}
    trs.append({**_transcript(30, 2.0, datetime(2026, 10, 30, 23, tzinfo=UTC)),
                "key": "gold_asia|2026-10-30"})
    rep = L.score(trs, outs)
    assert rep["written_after_close"] == 1 and rep["scored"] == 31
    assert rep["variants"]["shrink_only"]["verdict"] == "DROP"
    assert rep["variants"]["baseline"]["verdict"] == "REFERENCE"
    assert rep["argument_scores"]["by_direction"]["for"]["n"] == 31


def test_score_keeps_a_symmetric_committee_that_sizes_up_winners():
    trs, outs = [], {}
    for d in range(1, 32):
        t = datetime(2026, 10, d, 7, tzinfo=UTC)
        r = 2.0 if d % 3 else -1.0
        trs.append(_transcript(d, 1.5 if r > 0 else 0.5, t))
        outs[f"gold_asia|2026-10-{d:02d}"] = {"r": r, "exit_time": t + timedelta(hours=5)}
    rep = L.score(trs, outs)
    assert rep["variants"]["symmetric"]["verdict"] == "KEEP"
    assert rep["argument_scores"]["by_model_stance"]["m"] == {"n": 31, "right": 31}


def test_outcomes_join_books_on_signal_key_with_earliest_exit():
    e = "2026-10-30T07:41:52+00:00"
    L.FUSION_LEDGER.write_text(json.dumps({"sleeve": "gold_asia", "entry_time": e,
                                           "exit_time": "2026-10-30T13:39:44+00:00",
                                           "r_multiple": 1.0}) + "\n")
    L.PROP_LEDGER.write_text(json.dumps({"sleeve": "gold_asia", "entry_time": e, "book": "e8",
                                         "exit_time": "2026-10-30T12:00:00+00:00",
                                         "r_multiple": 2.0}) + "\n")
    o = L.outcomes()["gold_asia|2026-10-30"]
    assert o["r"] == 1.5 and o["exit_time"].hour == 12
