"""moat_clock splits the moat's skew into zone offset, clock drift and quote staleness."""
from __future__ import annotations

import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "moat"))
import moat_clock as mc  # noqa: E402

HOUR = mc.HOUR_MS


def _samples(offset_ms: int, n: int = 1000, seed: int = 7) -> list[int]:
    rnd = random.Random(seed)
    fresh = [offset_ms + rnd.randint(0, 150) for _ in range(n // 4)]          # active symbols
    quiet = [offset_ms + rnd.randint(0, 600_000) for _ in range(n - n // 4)]  # quiet symbols
    return fresh + quiet


def test_a_utc_plus_2_broker_reads_as_zone_2_with_small_drift() -> None:
    out = mc.split_skew(_samples(-2 * HOUR + 40))
    assert out["clock_split"] == "MEASURED" and out["zone_offset_h"] == 2
    assert 40 <= out["clock_drift_ms"] <= 200 and not out["drift_ambiguous"]
    assert out["quote_staleness_ms_p50"] > 100_000        # quiet symbols are stale, not skewed


def test_summer_zone_and_a_box_clock_running_behind() -> None:
    out = mc.split_skew(_samples(-3 * HOUR - 2_500))
    assert out["zone_offset_h"] == 3 and -2_500 <= out["clock_drift_ms"] <= -2_300


def test_staleness_never_moves_the_clock() -> None:
    calm, busy = _samples(-2 * HOUR + 40, seed=1), _samples(-2 * HOUR + 40, seed=2)
    busy = [v + 900_000 if i % 3 else v for i, v in enumerate(busy)]    # many staler quotes
    a, b = mc.split_skew(calm), mc.split_skew(busy)
    assert abs(a["clock_drift_ms"] - b["clock_drift_ms"]) < 200
    assert b["quote_staleness_ms_p50"] > a["quote_staleness_ms_p50"]


def test_one_mis_stamped_tick_cannot_set_the_clock() -> None:
    s = _samples(-2 * HOUR + 40) + [-5 * HOUR]
    assert mc.split_skew(s)["zone_offset_h"] == 2


def test_too_few_samples_is_unmeasured_never_a_guess() -> None:
    out = mc.split_skew([-2 * HOUR + 10] * (mc.MIN_SAMPLES - 1))
    assert out["clock_split"] == "UNMEASURED" and out["clock_drift_ms"] is None
    assert out["quote_staleness_ms_p50"] is None
