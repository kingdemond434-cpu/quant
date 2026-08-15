"""The forward panel, pinned on the three ways a leaderboard study lies to itself.

ONE: dropping the traders who disappeared. They left for a reason and the common reason is a
drawdown, so removing them manufactures persistence out of nothing. TWO: writing an empty snapshot
when a fetch fails, which turns a network timeout into a 100% exit rate. THREE: publishing a rank
statistic on a cohort too small to carry one, where anything under ~0.4 is indistinguishable from
noise and will nonetheless be quoted.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

from libs.research.leaderboard_panel import (
    MIN_COHORT,
    append_snapshot,
    forward_persistence,
    read_snapshots,
    spearman,
)


def _cohort(n: int, *, roi: float = 1.0, start: int = 0) -> list[dict[str, object]]:
    return [{"trader_id": f"T{i}", "roi": roi + i * 0.01} for i in range(start, start + n)]


def _panel(tmp: Path, snaps: list[tuple[int, list[dict[str, object]]]]) -> Path:
    p = tmp / "v.jsonl"
    base = datetime(2026, 1, 1, tzinfo=UTC)
    for day, traders in snaps:
        append_snapshot(p, "v", traders, at=base + timedelta(days=day))
    return p


def test_AN_EMPTY_COHORT_IS_NEVER_ARCHIVED(tmp_path: Path) -> None:
    """A failed fetch archived as an empty snapshot makes every trader in the previous one look
    like they exited. That converts a network timeout into a 100% exit rate -- a spectacular false
    finding, which is worse than the missing one it replaced."""
    p = tmp_path / "v.jsonl"
    assert append_snapshot(p, "v", []) is False
    assert not p.exists()
    assert append_snapshot(p, "v", _cohort(3)) is True
    assert len(read_snapshots(p)) == 1


def test_ONE_SNAPSHOT_IS_NO_DATA_NOT_NO_PERSISTENCE(tmp_path: Path) -> None:
    """L1.28a. UNMEASURED must never resolve to a clean verdict, and 'the clock is running' is a
    different statement from 'these traders have no persistence'."""
    p = _panel(tmp_path, [(0, _cohort(40))])
    r = forward_persistence(p)
    assert r["state"] == "NO-DATA"
    assert "clock is running" in r["why"]


def test_A_SHORT_GAP_IS_REFUSED(tmp_path: Path) -> None:
    """Two snapshots a day apart re-read one venue datapoint twice and call it two observations --
    inflating n without adding evidence, which is how a panel lies about its own power."""
    p = _panel(tmp_path, [(0, _cohort(40)), (1, _cohort(40))])
    r = forward_persistence(p)
    assert r["state"] == "NO-DATA" and r["gap_days"] == 1


def test_A_SMALL_COHORT_IS_UNDERPOWERED_NOT_MEASURED(tmp_path: Path) -> None:
    p = _panel(tmp_path, [(0, _cohort(10)), (30, _cohort(10))])
    r = forward_persistence(p)
    assert r["state"] == "UNDERPOWERED" and r["cohort"] == 10


def test_EXITS_ARE_COUNTED_AS_FAILURES_NOT_DROPPED(tmp_path: Path) -> None:
    """THE ONE THAT MATTERS. Half the cohort disappears; the exit rate must say so, and the two
    rank statistics must differ -- the gap between them IS the survivorship effect."""
    first = _cohort(MIN_COHORT + 10)
    survivors = first[: (MIN_COHORT + 10) // 2]
    # forward returns must VARY: a constant forward series has no rank variance, and the honest
    # answer there is None. A fixture that hands every survivor the same delta would be testing
    # the degenerate case while claiming to test survivorship.
    later = [dict(t, roi=float(t["roi"]) + 0.1 * i) for i, t in enumerate(survivors)]
    p = _panel(tmp_path, [(0, first), (30, later)])
    r = forward_persistence(p)
    assert r["state"] == "MEASURED"
    assert r["exited_counted_as_failures"] == len(first) - len(survivors)
    assert 0.4 < r["exit_rate"] < 0.6
    assert r["spearman_survivors_only"] is not None
    assert r["spearman_exits_ranked_last"] is not None
    assert r["spearman_survivors_only"] != r["spearman_exits_ranked_last"], (
        "with half the cohort gone the two statistics cannot agree -- if they do, the exits are "
        "being dropped rather than ranked, which is the survivorship bug this module exists for")


def test_BOTH_RHOS_ARE_PUBLISHED_AND_THE_NOTE_SAYS_WHY(tmp_path: Path) -> None:
    """Neither figure is publishable alone: a reader who sees only the survivors-only number is
    reading the selection, not the traders."""
    first = _cohort(MIN_COHORT + 5)
    later = [dict(t, roi=float(t["roi"]) * (1.0 + 0.05 * i)) for i, t in enumerate(first[:-3])]
    p = _panel(tmp_path, [(0, first), (30, later)])
    r = forward_persistence(p)
    assert "spearman_survivors_only" in r and "spearman_exits_ranked_last" in r
    assert r["survivorship_effect"] is not None
    assert "BIASED UPWARD" in r["note"]


def test_A_MALFORMED_LINE_DOES_NOT_COST_THE_PANEL(tmp_path: Path) -> None:
    """A panel is weeks of calendar time that cannot be re-acquired. One bad write must not be
    fatal to all of it."""
    p = _panel(tmp_path, [(0, _cohort(40))])
    with p.open("a", encoding="utf-8") as fh:
        fh.write("{not json\n")
    append_snapshot(p, "v", _cohort(40), at=datetime(2026, 2, 1, tzinfo=UTC))
    assert len(read_snapshots(p)) == 2


def test_SNAPSHOTS_ARE_APPEND_ONLY(tmp_path: Path) -> None:
    """The panel's whole value is that earlier rows were written before anyone knew what happened
    next. A rewrite destroys that while looking like an improvement."""
    p = _panel(tmp_path, [(0, _cohort(3)), (10, _cohort(3))])
    lines = p.read_text("utf-8").strip().split("\n")
    assert len(lines) == 2
    assert json.loads(lines[0])["at"] < json.loads(lines[1])["at"]


def test_SPEARMAN_IS_NONE_WHEN_UNDEFINED_NEVER_ZERO() -> None:
    """0.0 reads as 'measured, no relation'. That is the wrong claim when the answer is 'not
    measurable', and it is the desk's most-repeated defect class."""
    assert spearman([1.0], [1.0]) is None
    assert spearman([1.0, 2.0, 3.0], [5.0, 5.0, 5.0]) is None
    rho = spearman([1.0, 2.0, 3.0], [1.0, 2.0, 3.0])
    assert rho is not None and abs(rho - 1.0) < 1e-9


def test_TIES_GET_MIDRANKS() -> None:
    """Exits are all assigned ONE shared value, so they are always a tie block. Ranking them
    against each other would invent an ordering the data does not contain -- in the direction the
    sort happened to be stable on -- and the resulting correlation would be an artifact of it."""
    assert spearman([1.0, 2.0, 3.0, 4.0], [1.0, 1.0, 1.0, 2.0]) is not None
    # a perfectly tied series has no rank variance: undefined, not 1.0 and not 0.0
    assert spearman([1.0, 2.0, 3.0, 4.0], [7.0, 7.0, 7.0, 7.0]) is None
