"""`news_reaction`: unscheduled-headline drift/reversal, point-in-time, offline."""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import pytest

DESK = Path(__file__).resolve().parents[1]
for _p in (str(DESK), str(DESK.parents[1])):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from mt5desk import families  # noqa: E402
from mt5desk import family_news_reaction as nr  # noqa: E402
from mt5desk.family_alt_release import to_broker  # noqa: E402

START = pd.Timestamp("2026-01-05 00:00", tz="UTC")  # broker-frame labels
N = 1200


def _bars(jumps: dict[int, float] | None = None) -> pd.DataFrame:
    rng = np.random.default_rng(7)
    steps = rng.normal(0, 0.0005, N)
    for i, v in (jumps or {}).items():
        steps[i] += v
    close = 1.10 + np.cumsum(steps)
    opn = np.r_[close[0], close[:-1]]
    idx = pd.date_range(START, periods=N, freq="h")
    return pd.DataFrame({"open": opn, "high": np.maximum(opn, close) + 0.0002,
                         "low": np.minimum(opn, close) - 0.0002, "close": close,
                         "volume": 1.0}, index=idx)


def _utc_for_bar(df: pd.DataFrame, i: int, minutes: int = 10) -> pd.Timestamp:
    """A UTC instant that lands `minutes` into bar i once moved into the broker frame."""
    target = df.index[i] + pd.Timedelta(minutes=minutes)
    guess = target - pd.Timedelta(hours=2)
    for h in range(-12, 13):
        t = guess + pd.Timedelta(hours=h)
        if to_broker(t) == target:
            return t
    raise AssertionError("no UTC instant maps there")


def _row(eid: str, known: pd.Timestamp, *, seen: pd.Timestamp | None = None,
         at: pd.Timestamp | None = None, asset: str = "EURUSD",
         basis: str = "unscheduled: the world did not know it was coming") -> dict[str, Any]:
    return {"id": eid, "kind": "war_escalation", "surprise": 1.0, "surprise_basis": basis,
            "affected": [{"asset": asset, "horizon": "hours", "state_vars": []}],
            "knowable_at": known.isoformat(), "seen_at": (seen or known).isoformat(),
            "at": (at or seen or known).isoformat()}


def _write(tmp_path: Path, rows: list[dict[str, Any]]) -> Path:
    p = tmp_path / "events.jsonl"
    p.write_text("".join(json.dumps(r) + "\n" for r in rows), "utf-8")
    return p


def _events(df: pd.DataFrame, bars: list[int]) -> list[dict[str, Any]]:
    return [_row(f"ev{k}", _utc_for_bar(df, b)) for k, b in enumerate(bars)]


BARS = list(range(100, 1100, 60))  # 17 headlines


def test_registered_with_a_declared_16_cell_grid_and_classified_into_news_reaction() -> None:
    from libs.research.alpha_clusters import classify_family
    assert "news_reaction" in families.live_family_names()
    grid = families.get_param_grid("news_reaction")
    assert grid["mode"] == ["drift", "reversal"]
    assert int(np.prod([len(v) for v in grid.values()])) == 16
    assert classify_family("news_reaction") == "news_reaction"


def test_sealed_judge_can_build_it_without_a_gauntlet_branch() -> None:
    from research.gauntlet_buildability import (  # type: ignore[import-not-found]
        BUILDABLE,
        cell_verdict,
        family_verdict,
    )
    assert family_verdict("news_reaction")[0] == BUILDABLE
    assert cell_verdict("news_reaction", {"mode": "drift"})[0] != BUILDABLE  # no symbol
    assert cell_verdict("news_reaction", {"symbol": "EURUSD"})[0] == BUILDABLE


def test_absent_log_is_no_signals_never_a_fallback(tmp_path: Path) -> None:
    assert nr.news_reaction_signals(_bars(), symbol="EURUSD",
                                    event_log=tmp_path / "none.jsonl") == []


def test_entry_is_strictly_after_the_usable_instant(tmp_path: Path) -> None:
    df = _bars(dict.fromkeys(BARS, 0.004))
    log = _write(tmp_path, _events(df, BARS))
    sigs = nr.news_reaction_signals(df, symbol="EURUSD", size_q=0.0, event_log=log)
    assert sigs, "up-jump headlines past MIN_HISTORY must propose"
    idx = list(df.index)
    for s in sigs:
        i0 = idx.index(s.time)
        assert i0 in BARS  # decision bar contains the usable instant
        assert s.side == 1  # drift with an up reaction
    # nothing traded before MIN_HISTORY earlier reactions exist
    assert idx.index(sigs[0].time) >= BARS[nr.MIN_HISTORY]


def test_a_late_desk_stamp_delays_the_decision_bar(tmp_path: Path) -> None:
    df = _bars({**dict.fromkeys(BARS, 0.004), BARS[-1]: 0.008})
    rows = _events(df, BARS)
    last = rows[-1]
    late = _utc_for_bar(df, BARS[-1] + 2)
    last["seen_at"] = late.isoformat()
    last["at"] = late.isoformat()
    log = _write(tmp_path, rows)
    sigs = nr.news_reaction_signals(df, symbol="EURUSD", size_q=0.0, event_log=log)
    times = [list(df.index).index(s.time) for s in sigs]
    assert BARS[-1] not in times and BARS[-1] + 2 in times


def test_reversal_fades_and_sign_filter_selects(tmp_path: Path) -> None:
    df = _bars(dict.fromkeys(BARS, 0.004))
    log = _write(tmp_path, _events(df, BARS))
    rev = nr.news_reaction_signals(df, symbol="EURUSD", mode="reversal", size_q=0.0,
                                   event_log=log)
    assert rev and all(s.side == -1 for s in rev)
    assert nr.news_reaction_signals(df, symbol="EURUSD", surprise_sign=-1, size_q=0.0,
                                    event_log=log) == []


def test_scheduled_rows_other_symbols_and_echoes_are_not_headlines(tmp_path: Path) -> None:
    df = _bars()
    t = _utc_for_bar(df, 200)
    rows = [_row("a", t, basis="consensus z over the release's own surprise sigma (1)"),
            _row("b", t, asset="USDJPY"), _row("c", t), _row("c", t + pd.Timedelta(hours=3))]
    got = nr.headlines("EURUSD", rows)
    assert [e for _h, _u, e in got] == ["c"]


@pytest.mark.parametrize("q", [0.5, 0.8])
def test_size_quantile_reads_only_earlier_events(tmp_path: Path, q: float) -> None:
    jumps = {b: (0.004 if k % 2 else 0.0005) for k, b in enumerate(BARS)}
    df = _bars(jumps)
    log = _write(tmp_path, _events(df, BARS))
    sigs = nr.news_reaction_signals(df, symbol="EURUSD", size_q=q, event_log=log)
    big = {b for k, b in enumerate(BARS) if k % 2}
    assert sigs and all(list(df.index).index(s.time) in big for s in sigs)


def test_family_wrapper_reads_the_stream_log(tmp_path: Path,
                                             monkeypatch: pytest.MonkeyPatch) -> None:
    df = _bars(dict.fromkeys(BARS, 0.004))
    monkeypatch.setattr(nr, "EVENT_LOG", _write(tmp_path, _events(df, BARS)))
    sigs = families.family_news_reaction(df, symbol="EURUSD", size_q=0.0)
    assert sigs and all(s.tag.startswith("news_reaction:drift:") for s in sigs)
