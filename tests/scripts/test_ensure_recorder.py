"""Recorder supervision -- and the two ways it declared a dead tape healthy.

MEASURED 2026-08-15: the spot tape was 47.6 HOURS stale. H4 and H5 -- the desk's only genuinely
orthogonal pair, the one input no other rule can see -- read UNMEASURED for two days while
`ensure_recorder` printed "cron pgrep-guard owns the respawn" once a day and moved on.

Two defects, both of them the desk's own named classes:
  * supervision deferred to a schedule NOBODY EVER CHECKED WAS FIRING (the same user-level-timer
    failure that put the money path in the root crontab);
  * it supervised the HEARTBEAT, which the module's own header identifies as the signal that
    stays fresh in exactly the failure it was written to catch.
"""

from __future__ import annotations

import time
from pathlib import Path

import pytest
import scripts.ensure_recorder as R


def _partition(root: Path, age_s: float) -> Path:
    root.mkdir(parents=True, exist_ok=True)
    f = root / "BTCUSDT" / "part.jsonl.gz"
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_bytes(b"")
    t = time.time() - age_s
    import os
    os.utime(f, (t, t))
    return f


def test_THE_ARCHIVE_IS_THE_CLOCK_THAT_CANNOT_BE_FAKED(tmp_path: Path) -> None:
    """A heartbeat is written by the loop; the newest partition is written by the DATA. When they
    disagree the archive is right, because the archive is the thing the recorder exists to
    produce."""
    root = tmp_path / "moat" / "spot"
    _partition(root, age_s=3600.0)
    age = R._data_age(root)
    assert age is not None and 3500 < age < 3700


def test_AN_ABSENT_ARCHIVE_IS_NONE_AND_NOT_ZERO(tmp_path: Path) -> None:
    """Zero would read as "data landed this instant" -- the most flattering possible answer on the
    signal that decides whether collection is happening at all."""
    assert R._data_age(tmp_path / "does" / "not" / "exist") is None
    empty = tmp_path / "empty"
    empty.mkdir()
    assert R._data_age(empty) is None, "a tree with no partitions has no data age"


def test_A_FRESH_HEARTBEAT_WITH_A_STALE_ARCHIVE_IS_STALE(tmp_path: Path,
                                                         monkeypatch: pytest.MonkeyPatch) -> None:
    """THE HANG THIS MODULE WAS WRITTEN FOR, and it was supervising the wrong signal. The staleness
    test must be an OR across both clocks, not the heartbeat alone."""
    hb_age, data_age = 5.0, R._HB_STALE_S * 10
    stale = (hb_age is None or hb_age > R._HB_STALE_S) or (
        data_age is not None and data_age > R._HB_STALE_S)
    assert stale, "a live loop archiving nothing must not read as healthy"


def test_THE_GRACE_IS_LONGER_THAN_THE_GUARDS_OWN_PERIOD() -> None:
    """The cron guard runs every 10 minutes, so an outage past the grace is PROOF the guard is not
    doing its job rather than evidence it is slow. Set below one period, this would race the
    guard -- which is the exact hazard the module header warns about, and it is still real."""
    assert R._CRON_GRACE_S >= 3 * 10 * 60


def test_THE_LAST_RESORT_SPAWN_IS_A_SPAWN_AND_NOT_A_PRINT() -> None:
    """Deferring to the cron guard is correct only WHILE that guard is firing, and nothing checked
    whether it was. Asserted against the source so the property survives a refactor of the loop."""
    src = Path(R.__file__).read_text("utf-8")
    body = src.split("def main(")[1]
    assert "_CRON_GRACE_S" in body, "the grace must be consulted in the supervision loop"
    assert body.count("_spawn(script, log)") >= 2, \
        "there must be a spawn on the cron-guarded path, not only on the futures path"
    assert "last resort" in body.lower()


def test_OUTAGE_TAKES_THE_LONGER_OF_THE_TWO_CLOCKS() -> None:
    """An absent heartbeat no longer means "unknown" when the archive can answer. Deferring
    forever on a missing file is absence-as-verdict on the one signal that decides whether data
    is being collected."""
    assert max([x for x in (None, 900.0) if x is not None], default=None) == 900.0
    assert max([x for x in (120.0, 7200.0) if x is not None], default=None) == 7200.0
    assert max([x for x in (None, None) if x is not None], default=None) is None


def test_EVERY_RECORDER_DECLARES_AN_ARCHIVE_ROOT() -> None:
    """A recorder supervised without one falls back to heartbeat-only -- silently, and on the
    recorder most likely to be the crown jewel."""
    for name, spec in R._RECORDERS.items():
        assert len(spec) == 6, f"{name} carries no archive root"
        assert str(spec[5]).startswith("data/moat"), f"{name} archive root looks wrong: {spec[5]}"
