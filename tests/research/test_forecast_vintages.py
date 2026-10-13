"""DATA-45: every forecast vintage is kept, and revisions at 1h/6h/1d/3d read only the past.

The store is `libs/research/vintage` -- append-only, keyed by (series, target period, vintage) --
and these tests pin the two new readers on it: the fixed-lag revision (value at vintage v minus
the value at the nearest vintage <= v - lag, for the same target) and its momentum.
"""
from __future__ import annotations

import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from libs.research import vintage as V  # noqa: E402

T0 = datetime(2026, 9, 1, tzinfo=UTC)


def _iso(hours: float) -> str:
    return (T0 + timedelta(hours=hours)).isoformat()


def _issue(root: Path, values: dict[float, float], target: str = "2026-09-10") -> None:
    for hours, value in sorted(values.items()):
        V.record(root, "fc", {target: value}, vintage=_iso(hours))


def test_the_store_keeps_every_vintage_append_only(tmp_path: Path) -> None:
    _issue(tmp_path, {0: 10.0, 1: 11.0, 2: 11.0, 3: 12.5})
    rows = V.read_log(tmp_path, "fc")
    assert [r["value"] for r in rows] == [10.0, 11.0, 12.5], "unchanged re-issue costs nothing"
    _issue(tmp_path, {4: 13.0})
    assert [r["value"] for r in V.read_log(tmp_path, "fc")][:3] == [10.0, 11.0, 12.5]


def test_revision_at_each_fixed_lag_is_against_the_nearest_vintage_at_or_before_v_minus_lag(
        tmp_path: Path) -> None:
    _issue(tmp_path, {0: 10.0, 5: 11.0, 23: 14.0, 30: 15.0, 80: 20.0})
    rows = V.read_log(tmp_path, "fc")
    one_h = {r["vintage"]: r["revision"] for r in V.forecast_revisions(rows, 3_600)}
    assert one_h[_iso(5)] == pytest.approx(1.0)      # 11 - value at 4h (=10, vintage 0)
    assert one_h[_iso(30)] == pytest.approx(1.0)     # 15 - value at 29h (=14)
    assert _iso(0) not in one_h, "a target first issued inside the lag has nothing to revise"
    one_d = {r["vintage"]: r["revision"] for r in V.forecast_revisions(rows, 86_400)}
    assert one_d[_iso(30)] == pytest.approx(4.0)     # 15 - value at 6h (=11)
    three_d = {r["vintage"]: r["revision"] for r in V.forecast_revisions(rows, 259_200)}
    assert three_d[_iso(80)] == pytest.approx(9.0)   # 20 - value at 8h (=11, vintage 5h)
    six_h = {r["vintage"]: r["revision"] for r in V.forecast_revisions(rows, 21_600)}
    assert six_h[_iso(80)] == pytest.approx(5.0)     # 20 - value at 74h (=15, vintage 30h)
    assert set(V.FORECAST_LAGS_S) == {"1h", "6h", "1d", "3d"}


def test_momentum_is_the_change_in_the_revision(tmp_path: Path) -> None:
    _issue(tmp_path, {0: 10.0, 1: 11.0, 2: 13.0})
    rows = V.read_log(tmp_path, "fc")
    mom = {r["vintage"]: r["momentum"] for r in V.revision_momentum(rows, 3_600)}
    assert mom[_iso(2)] == pytest.approx((13.0 - 11.0) - (11.0 - 10.0))
    assert _iso(1) not in mom, "needs the target knowable two lags back"


def test_a_vintage_issued_later_never_moves_a_revision_already_stamped(tmp_path: Path) -> None:
    """Future corruption: append wild vintages after v; every revision stamped <= v is unchanged,
    including a BACKFILLED vintage written at the end of the file but published later than v."""
    _issue(tmp_path, {0: 10.0, 5: 11.0, 23: 14.0, 30: 15.0})
    rows = V.read_log(tmp_path, "fc")
    cut = T0.timestamp() + 30 * 3600
    before = {lag: [r for r in V.forecast_revisions(rows, s) if r["vintage_s"] <= cut]
              for lag, s in V.FORECAST_LAGS_S.items()}
    _issue(tmp_path, {31: -9e9, 100: 9e9, 30.5: 123.0})
    rows2 = V.read_log(tmp_path, "fc")
    for lag, s in V.FORECAST_LAGS_S.items():
        after = [r for r in V.forecast_revisions(rows2, s) if r["vintage_s"] <= cut]
        assert after == before[lag], lag
    mom_before = [r for r in V.revision_momentum(rows, 3_600) if r["vintage_s"] <= cut]
    mom_after = [r for r in V.revision_momentum(rows2, 3_600) if r["vintage_s"] <= cut]
    assert mom_after == mom_before
